"""
conclave/trail_view.py

Render a Decision Trail JSONL file as a Mermaid sequenceDiagram.

Why: the trail is Conclave's audit asset, but raw JSONL is hard to scan.
Mermaid renders natively on GitHub, Notion, Obsidian, and most docs engines —
copy-pasting the output into a README turns an audit log into a diagram.

Example:

    conclave trail view .conclave/trail_20260420_120000.jsonl > trail.md
    conclave trail view --latest                                 # auto-pick newest
    conclave trail view --timeline                               # ASCII timeline
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class TrailEntry:
    ts: str
    from_role: str
    to_role: str
    msg_type: str
    content: str
    reasoning: str = ""

    @classmethod
    def from_dict(cls, d: dict[str, object]) -> TrailEntry:
        return cls(
            ts=str(d.get("ts", "")),
            from_role=str(d.get("from", "?")),
            to_role=str(d.get("to", "?")),
            msg_type=str(d.get("type", "message")),
            content=str(d.get("content", "")),
            reasoning=str(d.get("reasoning", "")),
        )


def load_trail(path: Path) -> list[TrailEntry]:
    entries: list[TrailEntry] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(TrailEntry.from_dict(json.loads(line)))
        except json.JSONDecodeError:
            continue
    return entries


def latest_trail(trail_dir: Path) -> Path | None:
    if not trail_dir.exists():
        return None
    candidates = sorted(
        trail_dir.glob("*trail*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True
    )
    return candidates[0] if candidates else None


# ─── Mermaid ────────────────────────────────────────────────────────────────

# Map Conclave message types to Mermaid sequenceDiagram arrow syntax.
# Ref: https://mermaid.js.org/syntax/sequenceDiagram.html
_ARROWS = {
    "delegation": "->>",   # solid arrow with head
    "handoff":    "-->>",  # dashed arrow with head
    "escalation": "->>",   # solid — visually highlighted via Note over
    "output":     "-)",    # async arrow (open head) — signals "final artifact"
    "message":    "->>",
}


def _sanitize(text: str, limit: int = 120) -> str:
    """Mermaid sequenceDiagram is line-based; collapse newlines and escape pipes."""
    t = " ".join(text.split())
    t = t.replace("|", "\\|").replace(":", "：")  # Mermaid reserves ':' for labels
    return t[:limit] + ("…" if len(t) > limit else "")


def _roles(entries: list[TrailEntry]) -> list[str]:
    seen: list[str] = []
    for e in entries:
        for r in (e.from_role, e.to_role):
            if r and r not in seen:
                seen.append(r)
    return seen


def to_mermaid(entries: list[TrailEntry], title: str | None = None) -> str:
    """Render entries as a Mermaid sequenceDiagram string."""
    if not entries:
        return "```mermaid\nsequenceDiagram\n  Note over Conclave: (empty trail)\n```"

    lines: list[str] = ["```mermaid", "sequenceDiagram"]
    if title:
        lines.append("  autonumber")
        lines.append(f"  Note over {_roles(entries)[0]}: {_sanitize(title, 80)}")

    for role in _roles(entries):
        lines.append(f"  participant {role}")

    for e in entries:
        arrow = _ARROWS.get(e.msg_type, "->>")
        label_parts = [e.msg_type]
        if e.content:
            label_parts.append(_sanitize(e.content, 80))
        label = ": ".join(label_parts)
        lines.append(f"  {e.from_role} {arrow} {e.to_role}: {label}")

        if e.msg_type == "escalation":
            # Highlight the escalator (who raised the alarm) rather than the recipient.
            lines.append(f"  Note over {e.from_role}: escalation")
        if e.reasoning:
            lines.append(f"  Note right of {e.from_role}: {_sanitize(e.reasoning, 80)}")

    lines.append("```")
    return "\n".join(lines)


# ─── ASCII timeline ─────────────────────────────────────────────────────────


def _fmt_time(ts: str) -> str:
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.strftime("%H:%M:%S")
    except ValueError:
        return ts[:8] if ts else "—"


def to_timeline(entries: list[TrailEntry]) -> str:
    """Render entries as an ASCII timeline, one line per message."""
    if not entries:
        return "(empty trail)"

    role_width = max((len(r) for r in _roles(entries)), default=4)
    lines: list[str] = []
    for e in entries:
        arrow = {
            "delegation": "──>",
            "handoff":    "─ ─>",
            "escalation": "══>",
            "output":     "─◆",
            "message":    "───",
        }.get(e.msg_type, "───")
        left = e.from_role.ljust(role_width)
        right = e.to_role.ljust(role_width)
        content = _sanitize(e.content, 80) if e.content else e.msg_type
        lines.append(f"  {_fmt_time(e.ts)}  {left} {arrow} {right}  {content}")
    return "\n".join(lines)
