"""Unit tests for trail_view module."""

from __future__ import annotations

import json
from pathlib import Path

from conclave.trail_view import (
    TrailEntry,
    load_trail,
    to_mermaid,
    to_timeline,
)


def _write_trail(tmp_path: Path, entries: list[dict]) -> Path:
    path = tmp_path / "trail.jsonl"
    path.write_text("\n".join(json.dumps(e) for e in entries) + "\n")
    return path


def test_load_trail_skips_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "trail.jsonl"
    path.write_text(
        '{"ts":"2026-04-20T10:00:00Z","from":"A","to":"B","type":"delegation","content":"x"}\n'
        "not json at all\n"
        '{"ts":"2026-04-20T10:00:01Z","from":"B","to":"C","type":"handoff","content":"y"}\n'
    )
    entries = load_trail(path)
    assert len(entries) == 2
    assert entries[0].from_role == "A"
    assert entries[1].msg_type == "handoff"


def test_mermaid_renders_participants_and_arrows(tmp_path: Path) -> None:
    path = _write_trail(
        tmp_path,
        [
            {
                "ts": "2026-04-20T10:00:00Z",
                "from": "CPO",
                "to": "TechLead",
                "type": "delegation",
                "content": "Build auth",
            },
            {
                "ts": "2026-04-20T10:00:05Z",
                "from": "TechLead",
                "to": "QA",
                "type": "handoff",
                "content": "Review spec",
            },
            {
                "ts": "2026-04-20T10:00:10Z",
                "from": "QA",
                "to": "CPO",
                "type": "escalation",
                "content": "Blocker",
            },
        ],
    )
    out = to_mermaid(load_trail(path))
    # Fenced code block
    assert out.startswith("```mermaid")
    assert out.endswith("```")
    # All roles declared as participants
    assert "participant CPO" in out
    assert "participant TechLead" in out
    assert "participant QA" in out
    # Arrow mapping
    assert "CPO ->> TechLead" in out  # delegation
    assert "TechLead -->> QA" in out  # handoff (dashed)
    # Escalation gets an extra Note
    assert "Note over QA: escalation" in out


def test_mermaid_sanitizes_content(tmp_path: Path) -> None:
    path = _write_trail(
        tmp_path,
        [
            {
                "ts": "t",
                "from": "A",
                "to": "B",
                "type": "delegation",
                "content": "multi\nline | piped: colons",
            },
        ],
    )
    out = to_mermaid(load_trail(path))
    # Newlines collapsed
    assert "multi line" in out
    # Pipe escaped
    assert "\\|" in out
    # Colon substituted (Mermaid treats ':' as label separator after arrow)
    assert "：" in out


def test_mermaid_empty_trail() -> None:
    out = to_mermaid([])
    assert "empty trail" in out
    assert out.startswith("```mermaid")


def test_timeline_renders_one_line_per_entry(tmp_path: Path) -> None:
    path = _write_trail(
        tmp_path,
        [
            {
                "ts": "2026-04-20T10:00:00Z",
                "from": "A",
                "to": "B",
                "type": "delegation",
                "content": "go",
            },
            {
                "ts": "2026-04-20T10:00:05Z",
                "from": "B",
                "to": "C",
                "type": "handoff",
                "content": "over",
            },
        ],
    )
    out = to_timeline(load_trail(path))
    lines = [ln for ln in out.splitlines() if ln.strip()]
    assert len(lines) == 2
    assert "A" in lines[0] and "B" in lines[0]
    # Distinct arrow for handoff
    assert "─ ─>" in lines[1] or "──>" in lines[1]


def test_trail_entry_from_dict_with_missing_fields() -> None:
    e = TrailEntry.from_dict({"ts": "t"})
    assert e.from_role == "?"
    assert e.to_role == "?"
    assert e.msg_type == "message"
    assert e.content == ""
