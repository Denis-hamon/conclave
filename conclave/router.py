"""
conclave/router.py

The Conclave task router.

Persistent agents are token gluttons by nature — their entire conversation
history accumulates with every turn. This module answers one question before
each agent call:

  "Is this task genuinely complex, or can Haiku nail it with a few iterations?"

Classification axes:
  - NOVELTY   : Is this a new/ambiguous problem, or a known pattern?
  - COMPLEXITY: Does this require deep reasoning, or reliable execution?

Routing matrix:
                     HIGH NOVELTY
                          │
          Sonnet           │   Sonnet + DeepAgents
          (deliberate)     │   (deliberate + execute)
                          │
  LOW ───────────────────┼─────────────────────── HIGH
  COMPLEXITY             │                        COMPLEXITY
                          │
          Haiku loop       │   Haiku loop + DeepAgents
          (iterate cheap)  │   (iterate + execute)
                          │
                     LOW NOVELTY

Token cost reality check (as of April 2026, per 1M tokens):
  claude-haiku-4-5:      $0.80 input  / $4.00 output
  claude-sonnet-4-6:     $3.00 input  / $15.00 output
  claude-opus-4-6:       $15.00 input / $75.00 output

A Haiku correction loop (3 iterations) costs ~0.3x a single Sonnet call.
For repetitive tasks, the savings compound across every agent turn.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import anthropic

# ---------------------------------------------------------------------------
# Model tiers
# ---------------------------------------------------------------------------


class ModelTier(str, Enum):
    HAIKU = "claude-haiku-4-5-20251001"  # cheap, fast, iterative
    SONNET = "claude-sonnet-4-6"  # deliberation, strategy
    OPUS = "claude-opus-4-6"  # only when explicitly required


# Cost per 1M tokens (USD, April 2026)
MODEL_COST = {
    ModelTier.HAIKU: {"input": 0.80, "output": 4.00},
    ModelTier.SONNET: {"input": 3.00, "output": 15.00},
    ModelTier.OPUS: {"input": 15.00, "output": 75.00},
}


# ---------------------------------------------------------------------------
# Executor types
# ---------------------------------------------------------------------------


class ExecutorType(str, Enum):
    NATIVE = "native"  # Conclave's own agent loop
    DEEPAGENTS = "deepagents"  # delegate to LangChain DeepAgents


# ---------------------------------------------------------------------------
# Routing decision
# ---------------------------------------------------------------------------


@dataclass
class RoutingDecision:
    model: ModelTier
    executor: ExecutorType
    use_loop: bool  # True → Haiku correction loop
    max_retries: int  # loop retries before escalation
    rationale: str  # why this decision was made
    novelty: float  # 0.0–1.0
    complexity: float  # 0.0–1.0


# ---------------------------------------------------------------------------
# Task classifier
# ---------------------------------------------------------------------------

CLASSIFIER_PROMPT = """
You are a task routing classifier for a multi-agent system.

Analyze the task below and return a JSON object with exactly these fields:

{
  "novelty": <float 0.0-1.0>,       // 0 = known pattern, 1 = genuinely new problem
  "complexity": <float 0.0-1.0>,    // 0 = mechanical execution, 1 = deep reasoning
  "is_repetitive": <bool>,          // true if this task is likely to recur often
  "needs_filesystem": <bool>,       // true if task requires file/code/shell operations
  "rationale": "<one sentence>"     // explain the classification
}

Scoring guidance:
- "Write a summary of X" → novelty 0.1, complexity 0.2
- "Draft a test plan for the auth flow" → novelty 0.3, complexity 0.4
- "Define our Q3 strategy given market shifts" → novelty 0.8, complexity 0.9
- "Format this JSON as a markdown table" → novelty 0.0, complexity 0.1
- "Analyze why our churn increased" → novelty 0.7, complexity 0.8

Return ONLY the JSON object. No markdown, no explanation outside the JSON.
""".strip()


class TaskRouter:
    """
    Classifies a task and returns a RoutingDecision.

    The classifier itself runs on Haiku — ironic, intentional, and cheap.
    """

    # Thresholds for routing decisions
    NOVELTY_THRESHOLD = 0.5
    COMPLEXITY_THRESHOLD = 0.5

    def __init__(self, client: anthropic.Anthropic):
        self.client = client

    def route(self, task: str, role: str, executor_override: str | None = None) -> RoutingDecision:
        """Classify the task and return a routing decision."""
        import json

        prompt = f"ROLE: {role}\nTASK: {task}"

        resp = self.client.messages.create(
            model=ModelTier.HAIKU,  # classifier always runs on Haiku
            max_tokens=256,
            system=CLASSIFIER_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )

        try:
            clf = json.loads(resp.content[0].text.strip())
        except Exception:
            # Fallback to safe defaults if parsing fails
            clf = {
                "novelty": 0.6,
                "complexity": 0.6,
                "is_repetitive": False,
                "needs_filesystem": False,
                "rationale": "classification failed, defaulting to Sonnet",
            }

        novelty = float(clf.get("novelty", 0.6))
        complexity = float(clf.get("complexity", 0.6))
        repetitive = bool(clf.get("is_repetitive", False))
        needs_fs = bool(clf.get("needs_filesystem", False))
        rationale = clf.get("rationale", "")

        # --- Executor decision ---
        if executor_override:
            executor = ExecutorType(executor_override)
        elif needs_fs:
            executor = ExecutorType.DEEPAGENTS
        else:
            executor = ExecutorType.NATIVE

        # --- Model tier decision ---
        high_novelty = novelty >= self.NOVELTY_THRESHOLD
        high_complexity = complexity >= self.COMPLEXITY_THRESHOLD

        if high_novelty or high_complexity:
            # Complex/novel → Sonnet deliberates
            model = ModelTier.SONNET
            use_loop = False
            retries = 0
            rationale = f"[→ Sonnet] {rationale}"
        else:
            # Simple/repetitive → Haiku iterates
            model = ModelTier.HAIKU
            use_loop = True
            retries = 4 if repetitive else 3
            rationale = f"[→ Haiku loop ×{retries}] {rationale}"

        return RoutingDecision(
            model=model,
            executor=executor,
            use_loop=use_loop,
            max_retries=retries,
            rationale=rationale,
            novelty=novelty,
            complexity=complexity,
        )
