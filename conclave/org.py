"""
conclave/org.py
Loads a conclave.yml and instantiates the agent graph.
"""

from __future__ import annotations

from pathlib import Path

import anthropic
import yaml

from .agent import ConclaveAgent


def _build_org_structure(agents_cfg: list[dict[str, object]]) -> str:
    lines = []
    for a in agents_cfg:
        role = a["role"]
        reports_to = a.get("reports_to", "—")
        lines.append(f"  {role} → reports to {reports_to}")
    return "\n".join(lines)


def load_org(
    path: str | Path, client: anthropic.Anthropic
) -> tuple[dict[str, ConclaveAgent], str, str, str]:
    """
    Parse conclave.yml, return (agents_dict, org_name, deliberation, entry_role).
    entry_role = the role with no reports_to (top of hierarchy).
    """
    cfg = yaml.safe_load(Path(path).read_text())
    org = cfg["org"]

    org_name = org.get("name", "Conclave Org")
    deliberation = org.get("deliberation", "hierarchy")
    org_backend = org.get("backend", "anthropic")
    agents_cfg = org["agents"]
    org_structure = _build_org_structure(agents_cfg)

    agents: dict[str, ConclaveAgent] = {}
    entry_role = None

    for a in agents_cfg:
        role = a["role"]
        reports_to = a.get("reports_to")
        if not reports_to:
            entry_role = role

        agents[role] = ConclaveAgent(
            role=role,
            persona=a.get("persona", f"You are the {role}."),
            org_name=org_name,
            tools=a.get("tools", []),
            reports_to=reports_to,
            org_structure=org_structure,
            deliberation=deliberation,
            client=client,
            executor=a.get("executor", "native"),
            force_model=a.get("force_model", None),
            backend=a.get("backend", org_backend),
        )

    if not entry_role:
        entry_role = list(agents.keys())[0]

    return agents, org_name, deliberation, entry_role
