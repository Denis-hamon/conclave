"""
conclave/certification/observatory.py

Silently records every agent action in production.
No overhead, no side effects — pure observation.

Each recorded action becomes a candidate for simulation:
the raw material from which skillsets are distilled.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

OBSERVATORY_DIR = Path(".conclave/observatory")


@dataclass
class ObservedAction:
    action_id: str
    role: str
    task_type: str  # inferred label e.g. "write_ticket", "weekly_summary"
    model: str
    input: str
    output: str
    quality_score: float  # self-evaluated by Sonnet at record time
    context_docs: list[str]  # document names used
    input_tokens: int
    output_tokens: int
    cost_usd: float
    ts: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ"))

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def action_id_for(role: str, task_type: str, input_text: str) -> str:
        h = hashlib.sha1(f"{role}{task_type}{input_text}".encode()).hexdigest()[:8]
        ts = time.strftime("%Y%m%d_%H%M%S")
        return f"{role.lower()}_{task_type}_{ts}_{h}"


class Observatory:
    """
    Appended to the message bus — records every agent output.
    Completely transparent to the agent and the user.
    """

    def __init__(self, org_name: str):
        self.org_name = org_name
        self.store_dir = OBSERVATORY_DIR / org_name.lower().replace(" ", "_")
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self._buffer: list[ObservedAction] = []

    def record(self, action: ObservedAction):
        self._buffer.append(action)
        path = self.store_dir / f"{action.action_id}.json"
        path.write_text(json.dumps(action.to_dict(), indent=2))

    def load_for_task(self, role: str, task_type: str, limit: int = 100) -> list[ObservedAction]:
        """Load recorded observations for a specific role + task type."""
        actions = []
        for p in sorted(self.store_dir.glob(f"{role.lower()}_{task_type}_*.json")):
            try:
                data = json.loads(p.read_text())
                actions.append(ObservedAction(**data))
            except Exception:
                continue
            if len(actions) >= limit:
                break
        return actions

    def task_types(self) -> dict[str, list[str]]:
        """Return {role: [task_types]} seen in the observatory."""
        seen: dict[str, set] = {}
        for p in self.store_dir.glob("*.json"):
            parts = p.stem.split("_")
            if len(parts) >= 2:
                role, task = parts[0], parts[1]
                seen.setdefault(role, set()).add(task)
        return {k: sorted(v) for k, v in seen.items()}

    def stats(self) -> dict:
        actions = list(self.store_dir.glob("*.json"))
        total_cost = sum(
            json.loads(p.read_text()).get("cost_usd", 0) for p in actions if p.exists()
        )
        return {
            "total_actions": len(actions),
            "total_cost_usd": round(total_cost, 4),
            "task_types": self.task_types(),
        }
