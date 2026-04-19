"""
conclave/certification/simulator.py

Replays observed actions with Haiku + skillset in a fully isolated sandbox.
No tools are called. No external systems are touched. Pure inference.

The simulator answers one question:
  "If Haiku had this skillset, could it have produced the same output as Sonnet?"

It evaluates each simulation on three axes:
  - Structural conformance  : does the output match the expected format?
  - Completeness            : does it address all elements of the input?
  - Business coherence      : does it respect the org's implicit standards?

The evaluator also runs on Haiku (cheap, consistent, sufficient for scoring).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import json
import anthropic

from .observatory import ObservedAction
from .skillset import Skillset
from ..cost import CostMeter
from ..router import ModelTier


EVALUATOR_SYSTEM = """
You are evaluating whether a HAIKU OUTPUT matches the quality of a SONNET REFERENCE
for the same input.

Score on three axes (0.0 to 1.0 each):
- structural : Does the format, length, and structure match?
- completeness : Does it address all elements of the input?
- coherence : Is the content accurate, coherent, and professional?

Return JSON only:
{
  "structural": <float>,
  "completeness": <float>,
  "coherence": <float>,
  "overall": <float>,   // weighted average: 0.2 / 0.4 / 0.4
  "passed": <bool>,     // true if overall >= threshold
  "delta_notes": "<one sentence on the main difference vs reference>"
}
""".strip()

PASS_THRESHOLD = 0.82


@dataclass
class SimulationRun:
    action_id:      str
    input:          str
    sonnet_output:  str
    haiku_output:   str
    structural:     float
    completeness:   float
    coherence:      float
    overall:        float
    passed:         bool
    delta_notes:    str


@dataclass
class SimulationReport:
    role:             str
    task_type:        str
    skillset_version: str
    total_runs:       int
    passed_runs:      int
    pass_rate:        float
    avg_overall:      float
    avg_structural:   float
    avg_completeness: float
    avg_coherence:    float
    cost_meter:       CostMeter
    runs:             list[SimulationRun] = field(default_factory=list)

    @property
    def avg_cost_delta_pct(self) -> float:
        """Estimated cost saving vs baseline (Sonnet for everything)."""
        return self.cost_meter.savings_pct


class Simulator:
    """
    Runs a simulation batch: replay N observed actions with Haiku + skillset,
    evaluate each against the Sonnet reference, return a SimulationReport.
    """

    def __init__(self, client: anthropic.Anthropic, threshold: float = PASS_THRESHOLD):
        self.client    = client
        self.threshold = threshold

    def run(
        self,
        role:      str,
        task_type: str,
        skillset:  Skillset,
        actions:   list[ObservedAction],
        max_runs:  int = 50,
    ) -> SimulationReport:

        meter    = CostMeter()
        runs:    list[SimulationRun] = []
        sample   = actions[:max_runs]

        for action in sample:
            # --- Execute with Haiku + skillset ---
            haiku_resp = self.client.messages.create(
                model=ModelTier.HAIKU,
                max_tokens=1024,
                system=skillset.as_system_prompt(),
                messages=[{"role": "user", "content": action.input}],
            )
            haiku_output = haiku_resp.content[0].text.strip()
            meter.record(ModelTier.HAIKU, haiku_resp.usage.input_tokens, haiku_resp.usage.output_tokens)

            # --- Evaluate against Sonnet reference ---
            eval_prompt = (
                f"INPUT:\n{action.input}\n\n"
                f"SONNET REFERENCE:\n{action.output}\n\n"
                f"HAIKU OUTPUT:\n{haiku_output}\n\n"
                f"THRESHOLD: {self.threshold}"
            )
            eval_resp = self.client.messages.create(
                model=ModelTier.HAIKU,
                max_tokens=256,
                system=EVALUATOR_SYSTEM,
                messages=[{"role": "user", "content": eval_prompt}],
            )
            meter.record(ModelTier.HAIKU, eval_resp.usage.input_tokens, eval_resp.usage.output_tokens)

            try:
                ev = json.loads(eval_resp.content[0].text.strip())
            except Exception:
                ev = {"structural": 0.5, "completeness": 0.5, "coherence": 0.5,
                      "overall": 0.5, "passed": False, "delta_notes": "parse error"}

            runs.append(SimulationRun(
                action_id=action.action_id,
                input=action.input,
                sonnet_output=action.output,
                haiku_output=haiku_output,
                structural=ev.get("structural", 0),
                completeness=ev.get("completeness", 0),
                coherence=ev.get("coherence", 0),
                overall=ev.get("overall", 0),
                passed=ev.get("passed", False),
                delta_notes=ev.get("delta_notes", ""),
            ))

        passed     = [r for r in runs if r.passed]
        pass_rate  = len(passed) / len(runs) if runs else 0.0
        avg        = lambda key: sum(getattr(r, key) for r in runs) / len(runs) if runs else 0.0

        return SimulationReport(
            role=role,
            task_type=task_type,
            skillset_version=skillset.version,
            total_runs=len(runs),
            passed_runs=len(passed),
            pass_rate=pass_rate,
            avg_overall=avg("overall"),
            avg_structural=avg("structural"),
            avg_completeness=avg("completeness"),
            avg_coherence=avg("coherence"),
            cost_meter=meter,
            runs=runs,
        )
