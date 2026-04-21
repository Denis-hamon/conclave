"""CLI tests via click's CliRunner — no subprocess, no real API calls."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from conclave.cli import cli


def test_cli_help_lists_every_top_level_command() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    for cmd in ["run", "init", "benchmark", "dashboard", "trail", "replay"]:
        assert cmd in result.output


def test_init_creates_yaml_for_each_template() -> None:
    runner = CliRunner()
    for template in (
        "product-squad",
        "startup-5",
        "growth-squad",
        "creative-agency",
        "claude-code-squad",
    ):
        with runner.isolated_filesystem():
            result = runner.invoke(cli, ["init", "--template", template])
            assert result.exit_code == 0, f"{template} init failed: {result.output}"
            assert Path("conclave.yml").exists()
            content = Path("conclave.yml").read_text()
            assert "org:" in content
            assert "agents:" in content


def test_init_refuses_to_overwrite() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        Path("conclave.yml").write_text("existing: file\n")
        result = runner.invoke(cli, ["init", "--template", "product-squad"])
        assert result.exit_code != 0
        assert "already exists" in result.output


def test_run_dry_run_writes_trail_with_meta_entry(tmp_path: Path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        runner.invoke(cli, ["init", "--template", "product-squad"])
        result = runner.invoke(
            cli,
            [
                "run",
                "Design the onboarding",
                "--dry-run",
                "--trail-dir",
                str(tmp_path),
            ],
        )
        assert result.exit_code == 0
        trails = list(tmp_path.glob("*.jsonl"))
        assert len(trails) == 1
        lines = trails[0].read_text().splitlines()
        # First line must be the meta entry (unblocks `conclave replay`)
        meta = json.loads(lines[0])
        assert meta["type"] == "meta"
        assert meta["goal"] == "Design the onboarding"
        assert meta["entry_agent"] == "CPO"


def test_trail_view_mermaid_on_latest(tmp_path: Path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        runner.invoke(cli, ["init", "--template", "product-squad"])
        runner.invoke(cli, ["run", "Goal A", "--dry-run", "--trail-dir", str(tmp_path)])
        result = runner.invoke(cli, ["trail", "view", "--latest", "--trail-dir", str(tmp_path)])
        assert result.exit_code == 0
        assert result.output.startswith("```mermaid")
        assert "sequenceDiagram" in result.output


def test_trail_view_timeline_format(tmp_path: Path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        runner.invoke(cli, ["init", "--template", "product-squad"])
        runner.invoke(cli, ["run", "Goal B", "--dry-run", "--trail-dir", str(tmp_path)])
        result = runner.invoke(
            cli,
            ["trail", "view", "--latest", "--trail-dir", str(tmp_path), "--format", "timeline"],
        )
        assert result.exit_code == 0
        # Timeline has arrow characters
        assert "─" in result.output or "->" in result.output


def test_trail_view_errors_without_source() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["trail", "view"])
        assert result.exit_code != 0
        assert "--latest" in result.output or "trail file" in result.output


def test_replay_rewrites_trail_with_new_deliberation(tmp_path: Path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        runner.invoke(cli, ["init", "--template", "product-squad"])
        runner.invoke(cli, ["run", "Original goal", "--dry-run", "--trail-dir", str(tmp_path)])

        result = runner.invoke(
            cli,
            [
                "replay",
                "--latest",
                "--trail-dir",
                str(tmp_path),
                "--deliberation",
                "consensus",
            ],
        )
        assert result.exit_code == 0
        # A replay_of_* trail now sits beside the original
        replays = list(tmp_path.glob("replay_of_*.jsonl"))
        assert len(replays) == 1


def test_replay_fails_when_goal_cannot_be_recovered(tmp_path: Path) -> None:
    """A trail with no meta entry and no user seed should error cleanly."""
    runner = CliRunner()
    legacy = tmp_path / "trail.jsonl"
    legacy.write_text(
        json.dumps({"ts": "t", "from": "CPO", "to": "TechLead", "type": "handoff", "content": "go"})
        + "\n"
    )
    with runner.isolated_filesystem():
        runner.invoke(cli, ["init", "--template", "product-squad"])
        result = runner.invoke(cli, ["replay", str(legacy)])
        assert result.exit_code != 0
        assert "goal" in result.output.lower()


def test_benchmark_dry_run(tmp_path: Path) -> None:
    runner = CliRunner()
    out = tmp_path / "results.json"
    result = runner.invoke(cli, ["benchmark", "--dry-run", "--output", str(out)])
    assert result.exit_code == 0
    assert out.exists()
    data = json.loads(out.read_text())
    assert "summary" in data
    assert "by_category" in data
