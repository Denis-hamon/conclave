"""
conclave/dry_run.py

DryRunClient — drop-in replacement for anthropic.Anthropic that makes zero API calls.

Used by `conclave run --dry-run` and by examples/demo.py so the whole pipeline
can be exercised (including the trail, cost meter, and deliberation flow)
without an API key.
"""

from __future__ import annotations

import json
import random
from types import SimpleNamespace

FAKE_CLASSIFIER = {
    "novelty": 0.6,
    "complexity": 0.6,
    "is_repetitive": False,
    "needs_filesystem": False,
    "rationale": "[dry-run]",
}

FAKE_EVALUATOR = {"score": 0.85, "passed": True, "feedback": ""}


# Rough average tokens — enough to produce realistic-looking cost numbers.
_AVG_INPUT_TOKENS = 450
_AVG_OUTPUT_TOKENS = 180


class _Messages:
    def __init__(self, parent: DryRunClient):
        self._parent = parent

    def create(
        self,
        *,
        model: str,
        system: str = "",
        messages=None,
        max_tokens: int = 1024,
        **kwargs,
    ):
        text = self._parent._synthesize(system=system, messages=messages or [], model=model)
        # Emulate Anthropic SDK response shape
        content = [SimpleNamespace(text=text, type="text")]
        usage = SimpleNamespace(
            input_tokens=_AVG_INPUT_TOKENS + random.randint(-50, 50),
            output_tokens=_AVG_OUTPUT_TOKENS + random.randint(-40, 40),
        )
        return SimpleNamespace(content=content, usage=usage, model=model, stop_reason="end_turn")


class DryRunClient:
    """Drop-in replacement for anthropic.Anthropic with zero API calls."""

    def __init__(self, api_key: str | None = None, **_kwargs):
        self.api_key = api_key or "dry-run"
        self.messages = _Messages(self)
        self._turn = 0

    # ------------------------------------------------------------------
    # Response synthesis
    # ------------------------------------------------------------------
    def _synthesize(self, *, system: str, messages: list, model: str) -> str:
        sys_lower = (system or "").lower()

        if "classifier" in sys_lower or "routing" in sys_lower:
            return json.dumps(FAKE_CLASSIFIER)

        if "evaluator" in sys_lower:
            return json.dumps(FAKE_EVALUATOR)

        # Generic agent response — try to sniff a role and the reporting chain.
        role = self._extract_role(system)
        next_role = self._extract_next_role(system, role)

        self._turn += 1

        if next_role and self._turn < 4:
            return (
                f"[TO: {next_role}]\n"
                f"{self._task_fragment(role, next_role)}\n"
                f"[REASONING: dry-run simulation — {role} delegating to {next_role}]"
            )

        return (
            "[OUTPUT: artifact.md]\n"
            f"# {role or 'Output'}\n\n"
            f"Simulated output produced during dry-run (no API calls made).\n"
            "[REASONING: dry-run simulation — producing final output]"
        )

    # ------------------------------------------------------------------
    # Prompt introspection helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _extract_role(system: str) -> str:
        if not system:
            return "Agent"
        for line in system.splitlines():
            if line.strip().startswith("You are the "):
                # e.g. "You are the CPO in a multi-agent organization called ..."
                tail = line.strip()[len("You are the ") :]
                return tail.split(" ")[0]
        return "Agent"

    @staticmethod
    def _extract_next_role(system: str, current_role: str) -> str | None:
        """Pick a child role from the org hierarchy section (best effort)."""
        if not system:
            return None
        lines = system.splitlines()
        # Hierarchy lines look like: "  RoleA → reports to RoleB"
        for line in lines:
            if "reports to" in line:
                parts = line.split("→")
                if len(parts) == 2:
                    role = parts[0].strip()
                    parent = parts[1].replace("reports to", "").strip()
                    if parent == current_role and role != current_role:
                        return role
        return None

    @staticmethod
    def _task_fragment(role: str, next_role: str) -> str:
        fragments = [
            "Please pick this up and produce the next artifact.",
            "Handing this off — focus on the concrete deliverable.",
            "Your turn. Flag blockers early.",
        ]
        return random.choice(fragments)
