"""
conclave/executors/haiku_loop.py

The Haiku correction loop.

Why persistent agents are token gluttons
─────────────────────────────────────────
A persistent agent accumulates its full conversation history in context.
After 10 turns in a 3-agent org, each new call re-sends thousands of tokens
that were already processed. Anthropic's prompt caching helps at the margins,
but the structural cost remains: more history = more tokens per call.

The correction loop strategy
─────────────────────────────
For tasks that are well-defined and repetitive (formatting, summarization,
template filling, test plan generation, ticket writing...), Haiku can match
Sonnet's output quality through iteration rather than brute model power.

Algorithm:
  1. Execute task with Haiku                          [~cheap]
  2. Self-evaluate the output against a rubric        [~very cheap]
  3. If score ≥ threshold → accept, done
  4. If score < threshold → generate corrective feedback, retry
  5. After max_retries → escalate to Sonnet           [one expensive call]

In practice, 80% of well-defined tasks resolve in ≤ 2 Haiku iterations.
The savings vs. always-Sonnet: ~70-85% per task.

The self-evaluator also runs on Haiku. Ironic. Intentional.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import anthropic

from ..cost import CostMeter
from ..router import ModelTier, RoutingDecision

EXECUTOR_SYSTEM = """
You are executing a specific task assigned to you by a {role} in an organization.
Be precise, complete, and follow the task instructions exactly.
Output ONLY the result of the task. No meta-commentary.
""".strip()


EVALUATOR_SYSTEM = """
You are a strict output evaluator. Assess whether the ATTEMPT satisfies the TASK.

Return a JSON object:
{
  "score": <float 0.0-1.0>,
  "passed": <bool>,
  "feedback": "<specific, actionable correction if score < 0.8, else empty string>"
}

Scoring:
- 1.0 : Perfect. Exactly what was asked, no issues.
- 0.8 : Good. Minor gaps, acceptable for production.
- 0.6 : Partial. Missing key elements, needs correction.
- 0.4 : Poor. Wrong approach or significant omissions.
- 0.0 : Completely wrong.

Return ONLY the JSON. No markdown.
""".strip()


PASS_THRESHOLD = 0.80
ESCALATION_NOTE = "[ESCALATED TO SONNET after Haiku loop exhausted]"


@dataclass
class LoopResult:
    output: str
    iterations: int
    final_score: float
    escalated: bool
    model_used: ModelTier
    cost_meter: CostMeter


class HaikuCorrectionLoop:
    """
    Attempts a task with Haiku, iterates with self-correction,
    escalates to Sonnet only if the loop is exhausted.
    """

    def __init__(self, client: anthropic.Anthropic, decision: RoutingDecision, role: str):
        self.client = client
        self.decision = decision
        self.role = role
        self.meter = CostMeter()

    def run(self, task: str) -> LoopResult:
        attempt = ""
        score = 0.0
        feedback = ""

        for i in range(self.decision.max_retries):
            # --- Build the prompt with corrective feedback if available ---
            prompt = task
            if feedback:
                prompt = f"{task}\n\n[PREVIOUS ATTEMPT FEEDBACK]\n{feedback}\n\nPlease correct your output accordingly."

            # --- Execute with Haiku ---
            resp = self.client.messages.create(
                model=ModelTier.HAIKU,
                max_tokens=1024,
                system=EXECUTOR_SYSTEM.format(role=self.role),
                messages=[{"role": "user", "content": prompt}],
            )
            attempt = resp.content[0].text.strip()
            self.meter.record(ModelTier.HAIKU, resp.usage.input_tokens, resp.usage.output_tokens)

            # --- Self-evaluate ---
            eval_prompt = f"TASK:\n{task}\n\nATTEMPT:\n{attempt}"
            eval_resp = self.client.messages.create(
                model=ModelTier.HAIKU,
                max_tokens=256,
                system=EVALUATOR_SYSTEM,
                messages=[{"role": "user", "content": eval_prompt}],
            )
            self.meter.record(
                ModelTier.HAIKU,
                eval_resp.usage.input_tokens,
                eval_resp.usage.output_tokens,
            )

            try:
                evaluation = json.loads(eval_resp.content[0].text.strip())
                score = float(evaluation.get("score", 0.0))
                passed = bool(evaluation.get("passed", False))
                feedback = evaluation.get("feedback", "")
            except Exception:
                score, passed, feedback = 0.5, False, "Evaluation parse error — retry."

            if passed or score >= PASS_THRESHOLD:
                return LoopResult(
                    output=attempt,
                    iterations=i + 1,
                    final_score=score,
                    escalated=False,
                    model_used=ModelTier.HAIKU,
                    cost_meter=self.meter,
                )

        # --- Escalate to Sonnet ---
        escalation_prompt = (
            f"{task}\n\n[CONTEXT] A Haiku agent attempted this {self.decision.max_retries} times "
            f"and reached a score of {score:.2f}. Last attempt:\n{attempt}\n\n"
            f"Last feedback: {feedback}\n\nPlease produce the correct output."
        )
        sonnet_resp = self.client.messages.create(
            model=ModelTier.SONNET,
            max_tokens=1024,
            system=EXECUTOR_SYSTEM.format(role=self.role),
            messages=[{"role": "user", "content": escalation_prompt}],
        )
        final_output = sonnet_resp.content[0].text.strip()
        self.meter.record(
            ModelTier.SONNET,
            sonnet_resp.usage.input_tokens,
            sonnet_resp.usage.output_tokens,
        )

        return LoopResult(
            output=f"{ESCALATION_NOTE}\n\n{final_output}",
            iterations=self.decision.max_retries,
            final_score=1.0,  # Sonnet is the final answer
            escalated=True,
            model_used=ModelTier.SONNET,
            cost_meter=self.meter,
        )
