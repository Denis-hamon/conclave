"""
conclave/cost.py

Token cost tracking across all models.
Shows in real-time what each routing decision costs,
and what it would have cost if everything ran on Sonnet.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .router import ModelTier


# Cost per 1M tokens (USD, April 2026)
COST_TABLE = {
    "claude-haiku-4-5-20251001": {"input": 0.80, "output": 4.00},
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
    "claude-opus-4-6": {"input": 15.00, "output": 75.00},
}

BASELINE_MODEL = "claude-sonnet-4-6"  # "what if we had used Sonnet for everything"


@dataclass
class ModelUsage:
    model: str
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def cost_usd(self) -> float:
        rates = COST_TABLE.get(self.model, COST_TABLE[BASELINE_MODEL])
        return (
            self.input_tokens / 1_000_000 * rates["input"]
            + self.output_tokens / 1_000_000 * rates["output"]
        )

    @property
    def baseline_cost_usd(self) -> float:
        rates = COST_TABLE[BASELINE_MODEL]
        return (
            self.input_tokens / 1_000_000 * rates["input"]
            + self.output_tokens / 1_000_000 * rates["output"]
        )


class CostMeter:
    """Accumulates token usage and computes savings vs. always-Sonnet baseline."""

    def __init__(self):
        self._usage: dict[str, ModelUsage] = {}

    def record(self, model: ModelTier, input_tokens: int, output_tokens: int):
        key = str(model.value) if hasattr(model, "value") else str(model)
        if key not in self._usage:
            self._usage[key] = ModelUsage(model=key)
        self._usage[key].input_tokens += input_tokens
        self._usage[key].output_tokens += output_tokens

    def merge(self, other: CostMeter):
        for key, usage in other._usage.items():
            if key not in self._usage:
                self._usage[key] = ModelUsage(model=key)
            self._usage[key].input_tokens += usage.input_tokens
            self._usage[key].output_tokens += usage.output_tokens

    @property
    def total_cost(self) -> float:
        return sum(u.cost_usd for u in self._usage.values())

    @property
    def baseline_cost(self) -> float:
        return sum(u.baseline_cost_usd for u in self._usage.values())

    @property
    def savings(self) -> float:
        return self.baseline_cost - self.total_cost

    @property
    def savings_pct(self) -> float:
        if self.baseline_cost == 0:
            return 0.0
        return self.savings / self.baseline_cost * 100

    @property
    def total_tokens(self) -> int:
        return sum(u.input_tokens + u.output_tokens for u in self._usage.values())

    def summary_lines(self) -> list[str]:
        lines = []
        for model, usage in sorted(self._usage.items()):
            short = model.split("-")[1] if "-" in model else model
            lines.append(
                f"  {short:<10} {usage.input_tokens:>7} in  {usage.output_tokens:>7} out  "
                f"${usage.cost_usd:.4f}"
            )
        lines.append(f"  {'TOTAL':<10} {'':>7}     {'':>7}      ${self.total_cost:.4f}")
        lines.append(f"  {'BASELINE':<10} {'(all-Sonnet)':>15}       ${self.baseline_cost:.4f}")
        if self.savings > 0:
            lines.append(f"  {'SAVED':<10} ${self.savings:.4f}  ({self.savings_pct:.1f}%)")
        return lines
