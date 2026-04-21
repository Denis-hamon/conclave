"""
Minimal in-browser Conclave runtime for docs/demo/.

Mirrors the CLI's --dry-run behavior without the I/O that doesn't work in
Pyodide (rich console, file writes, network). Loaded by index.html via
`await pyodide.runPythonAsync(await fetch('./conclave_demo.py').text())`.
"""

import random
from datetime import datetime, timezone

import yaml

# Embedded org templates (match the ones shipped in examples/*.yml).
TEMPLATES = {
    "product-squad": """
org:
  name: "Product Squad"
  deliberation: hierarchy
  agents:
    - role: CPO
      persona: Strategic and data-driven.
    - role: TechLead
      persona: Pragmatic. Writes tight specs.
      reports_to: CPO
    - role: QA
      persona: Defensive thinker. Finds edge cases.
      reports_to: TechLead
""",
    "claude-code-squad": """
org:
  name: "Claude Code Squad"
  deliberation: hierarchy
  agents:
    - role: Planner
      persona: Breaks goals into atomic tasks.
    - role: Implementer
      persona: Writes the smallest change that passes tests.
      reports_to: Planner
    - role: Reviewer
      persona: Reads diffs line by line.
      reports_to: Planner
    - role: Tester
      persona: Writes the tests the Implementer forgot.
      reports_to: Reviewer
""",
    "startup-5": """
org:
  name: "Startup"
  deliberation: consensus
  agents:
    - role: CEO
      persona: Visionary but pragmatic.
    - role: CPO
      persona: User-obsessed.
      reports_to: CEO
    - role: CTO
      persona: Systems thinker.
      reports_to: CEO
    - role: Designer
      persona: Craft-obsessed.
      reports_to: CPO
    - role: QA
      persona: Last line of defense.
      reports_to: CTO
""",
    "growth-squad": """
org:
  name: "Growth Squad"
  deliberation: consensus
  agents:
    - role: CMO
      persona: Narrative-driven.
    - role: GrowthLead
      persona: Experiment-minded.
      reports_to: CMO
    - role: ContentStrategist
      persona: Audience-first.
      reports_to: CMO
    - role: DataAnalyst
      persona: Numbers before narratives.
      reports_to: GrowthLead
""",
    "creative-agency": """
org:
  name: "Creative Agency"
  deliberation: hierarchy
  agents:
    - role: CreativeDirector
      persona: Taste-maker.
    - role: Copywriter
      persona: Words first.
      reports_to: CreativeDirector
    - role: ArtDirector
      persona: Visual systems thinker.
      reports_to: CreativeDirector
    - role: PM
      persona: Client translator.
      reports_to: CreativeDirector
""",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _synth_handoff(from_role: str, to_role: str) -> str:
    options = [
        "Please take this forward. Keep scope tight.",
        "Your turn. Flag blockers early.",
        "Passing this along — focus on the concrete deliverable.",
    ]
    return random.choice(options)


def _synth_output(role: str, goal: str) -> str:
    return (
        f"[OUTPUT: artifact.md]\n"
        f"# {role}\n\n"
        f"Simulated output for: {goal}\n\n"
        f"Produced during dry-run (no API calls)."
    )


def deliberate(org: dict, goal: str, deliberation: str) -> list[dict]:
    """Mirror ConclaveBus.run with the same meta entry + handoff shape."""
    agents = org["agents"]
    roles = [a["role"] for a in agents]
    entry = next((a["role"] for a in agents if not a.get("reports_to")), roles[0])

    trail: list[dict] = [
        {
            "ts": _now(),
            "type": "meta",
            "goal": goal,
            "deliberation": deliberation,
            "entry_agent": entry,
            "roles": roles,
        },
        {
            "ts": _now(),
            "from": "user",
            "to": entry,
            "type": "delegation",
            "content": goal,
            "reasoning": "goal injected by user",
        },
    ]

    # Walk the reporting chain top-down
    chain: list[tuple[str, str]] = []
    current = entry
    seen: set[str] = set()
    for _ in range(len(agents) * 2):
        if current in seen:
            break
        seen.add(current)
        sub = next((a["role"] for a in agents if a.get("reports_to") == current), None)
        if not sub:
            break
        chain.append((current, sub))
        current = sub

    for a, b in chain:
        trail.append(
            {
                "ts": _now(),
                "from": a,
                "to": b,
                "type": "handoff" if deliberation != "first-valid" else "delegation",
                "content": _synth_handoff(a, b),
                "reasoning": f"dry-run — {a} delegating to {b}",
                "model_used": "claude-sonnet-4-6",
            }
        )

    leaf = chain[-1][1] if chain else entry
    trail.append(
        {
            "ts": _now(),
            "from": leaf,
            "to": "bus",
            "type": "output",
            "content": _synth_output(leaf, goal),
            "reasoning": "final artifact",
            "model_used": "claude-sonnet-4-6",
        }
    )

    # Consensus fans out so every role produces an output
    if deliberation == "consensus":
        for role in roles:
            if role == leaf:
                continue
            trail.append(
                {
                    "ts": _now(),
                    "from": role,
                    "to": "bus",
                    "type": "output",
                    "content": _synth_output(role, goal),
                    "reasoning": "consensus turn",
                    "model_used": "claude-sonnet-4-6",
                }
            )

    return trail


# Mirror of conclave/trail_view.py — kept in sync with the real renderer
_ARROWS = {
    "delegation": "->>",
    "handoff": "-->>",
    "escalation": "->>",
    "output": "-)",
    "message": "->>",
}


def _sanitize(text: str, limit: int = 80) -> str:
    t = " ".join(text.split())
    t = t.replace("|", "\\|").replace(":", "：")
    return t[:limit] + ("…" if len(t) > limit else "")


def to_mermaid(entries: list[dict]) -> str:
    msgs = [e for e in entries if e.get("type") != "meta"]
    if not msgs:
        return "```mermaid\nsequenceDiagram\n  Note over Conclave: (empty)\n```"

    seen: list[str] = []
    for e in msgs:
        for r in (e.get("from"), e.get("to")):
            if r and r not in seen:
                seen.append(r)

    lines = ["```mermaid", "sequenceDiagram", "  autonumber"]
    for r in seen:
        lines.append(f"  participant {r}")
    for e in msgs:
        arrow = _ARROWS.get(e.get("type", "message"), "->>")
        content = _sanitize(e.get("content", ""), 80)
        lines.append(f"  {e['from']} {arrow} {e['to']}: {e.get('type', 'msg')}: {content}")
    lines.append("```")
    return "\n".join(lines)


def format_trail(entries: list[dict]) -> str:
    msgs = [e for e in entries if e.get("type") != "meta"]
    out = []
    for e in msgs:
        ts = e.get("ts", "")
        # ts is like "2026-04-21T12:34:56.789012Z" — keep HH:MM:SS
        hm = ts[11:19] if len(ts) >= 19 else ts
        frm = e.get("from", "?")
        to = e.get("to", "?")
        ty = e.get("type", "msg")
        content = e.get("content", "").replace("\n", " ")[:140]
        out.append(f"{hm}  {frm:>16} → {to:<10}  [{ty}] {content}")
    return "\n".join(out)


def format_cost(trail: list[dict], goal: str) -> str:
    msgs = [e for e in trail if e.get("type") != "meta"]
    tokens_in = len(msgs) * 450
    tokens_out = len(msgs) * 180
    cost_sonnet = (tokens_in / 1_000_000) * 3 + (tokens_out / 1_000_000) * 15
    cost_haiku = (tokens_in / 1_000_000) * 0.25 + (tokens_out / 1_000_000) * 1.25
    saved = cost_sonnet - cost_haiku
    pct = (saved / cost_sonnet * 100) if cost_sonnet > 0 else 0
    return (
        f"Goal: {goal}\n"
        f"Messages: {len(msgs)}\n\n"
        f"  sonnet    {tokens_in:>7} in  {tokens_out:>7} out   ${cost_sonnet:.4f}\n"
        f"  haiku     (alternative routing)              ${cost_haiku:.4f}\n"
        f"  ─────────────────────────────────────────────────\n"
        f"  SAVED     ${saved:.4f}  ({pct:.1f}%)\n"
    )


def run_demo(template_name: str, deliberation: str, goal: str) -> dict[str, str]:
    random.seed(hash(goal) & 0xFFFF)
    spec = yaml.safe_load(TEMPLATES[template_name])
    org = spec["org"]
    trail = deliberate(org, goal, deliberation)
    msg_count = len([e for e in trail if e.get("type") != "meta"])
    return {
        "trail_text": format_trail(trail),
        "mermaid": to_mermaid(trail),
        "cost": format_cost(trail, goal),
        "summary": f"{msg_count} messages · {deliberation}",
    }
