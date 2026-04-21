"""
conclave/replay.py

Re-run a past Decision Trail through the org, optionally with a different
deliberation strategy. The original trail's meta entry (first JSONL line)
supplies the goal and entry agent; the current `conclave.yml` supplies the
agent definitions.

Use cases:
- "What if CPO had used consensus instead of hierarchy?"
- Regression-test a persona change against a known scenario.
- Reproduce a postmortem run to try an alternative deliberation path.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ReplayMeta:
    goal: str
    deliberation: str
    entry_agent: str
    roles: list[str]
    max_turns: int


def extract_meta(trail_path: Path) -> ReplayMeta | None:
    """Read the first JSONL line and return the meta block if present."""
    if not trail_path.exists():
        return None
    first = trail_path.read_text().splitlines()[:1]
    if not first:
        return None
    try:
        entry = json.loads(first[0])
    except json.JSONDecodeError:
        return None
    if entry.get("type") != "meta":
        return None
    return ReplayMeta(
        goal=str(entry.get("goal", "")),
        deliberation=str(entry.get("deliberation", "hierarchy")),
        entry_agent=str(entry.get("entry_agent", "")),
        roles=list(entry.get("roles", [])),
        max_turns=int(entry.get("max_turns", 20)),
    )


def infer_goal_from_trail(trail_path: Path) -> str | None:
    """Legacy fallback for trails written before the meta entry existed.

    The seed message is injected by the user as a delegation to the entry
    agent. We can't perfectly reconstruct it from a post-meta trail, but if
    the first non-meta entry is a delegation from the user we recover it.
    """
    if not trail_path.exists():
        return None
    for line in trail_path.read_text().splitlines():
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if entry.get("type") == "meta":
            continue
        if entry.get("from") == "user":
            return str(entry.get("content", "")) or None
        return None
    return None
