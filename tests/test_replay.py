"""Unit tests for the replay module."""

from __future__ import annotations

import json
from pathlib import Path

from conclave.replay import extract_meta, infer_goal_from_trail


def _write(path: Path, lines: list[dict]) -> Path:
    path.write_text("\n".join(json.dumps(line) for line in lines) + "\n")
    return path


def test_extract_meta_reads_first_line(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "trail.jsonl",
        [
            {
                "ts": "2026-04-21T10:00:00Z",
                "type": "meta",
                "goal": "Spec the checkout API",
                "deliberation": "hierarchy",
                "entry_agent": "CPO",
                "roles": ["CPO", "TechLead", "QA"],
                "max_turns": 10,
            },
            {
                "ts": "2026-04-21T10:00:01Z",
                "from": "user",
                "to": "CPO",
                "type": "delegation",
                "content": "Spec the checkout API",
            },
        ],
    )
    meta = extract_meta(path)
    assert meta is not None
    assert meta.goal == "Spec the checkout API"
    assert meta.deliberation == "hierarchy"
    assert meta.entry_agent == "CPO"
    assert meta.roles == ["CPO", "TechLead", "QA"]
    assert meta.max_turns == 10


def test_extract_meta_returns_none_for_legacy_trail(tmp_path: Path) -> None:
    """Trails without a meta entry (written before this feature) yield None."""
    path = _write(
        tmp_path / "trail.jsonl",
        [
            {"ts": "t", "from": "CPO", "to": "TechLead", "type": "delegation", "content": "go"},
        ],
    )
    assert extract_meta(path) is None


def test_extract_meta_returns_none_for_empty_file(tmp_path: Path) -> None:
    path = tmp_path / "trail.jsonl"
    path.write_text("")
    assert extract_meta(path) is None


def test_extract_meta_returns_none_for_missing_file(tmp_path: Path) -> None:
    assert extract_meta(tmp_path / "does-not-exist.jsonl") is None


def test_infer_goal_from_user_seed(tmp_path: Path) -> None:
    """A pre-meta trail whose first non-meta entry is a user delegation still works."""
    path = _write(
        tmp_path / "trail.jsonl",
        [
            {"ts": "t", "from": "user", "to": "CPO", "type": "delegation", "content": "Ship auth"},
            {"ts": "t", "from": "CPO", "to": "TechLead", "type": "delegation", "content": "go"},
        ],
    )
    assert infer_goal_from_trail(path) == "Ship auth"


def test_infer_goal_skips_meta_then_reads_user(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "trail.jsonl",
        [
            {"type": "meta", "goal": "ignored"},
            {"from": "user", "to": "CPO", "type": "delegation", "content": "Real goal"},
        ],
    )
    # When meta is present, the caller uses extract_meta; infer is the fallback.
    # It still returns the user seed correctly for legacy consumers.
    assert infer_goal_from_trail(path) == "Real goal"


def test_infer_goal_none_when_no_user_seed(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "trail.jsonl",
        [
            {"from": "CPO", "to": "TechLead", "type": "handoff", "content": "x"},
        ],
    )
    assert infer_goal_from_trail(path) is None
