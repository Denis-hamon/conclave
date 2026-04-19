"""Integration test: full pipeline with mocked API."""
from __future__ import annotations
import json
from pathlib import Path
from unittest.mock import MagicMock


def _responder(call_counter):
    """Return deterministic responses based on system prompt heuristics."""
    def side_effect(**kwargs):
        system = kwargs.get("system", "") or ""
        resp = MagicMock()
        resp.usage = MagicMock(input_tokens=100, output_tokens=50)
        if "classifier" in system.lower() or "routing" in system.lower():
            text = json.dumps({
                "novelty": 0.8, "complexity": 0.7,
                "is_repetitive": False, "needs_filesystem": False,
                "rationale": "integration test",
            })
        elif "evaluator" in system.lower():
            text = json.dumps({"score": 0.9, "passed": True, "feedback": ""})
        else:
            call_counter["n"] += 1
            if call_counter["n"] >= 2:
                text = "[OUTPUT: spec.md]\nTest spec."
            else:
                text = "[TO: TechLead]\nPlease spec this."
        resp.content = [MagicMock(text=text)]
        return resp
    return side_effect


def test_full_run_product_squad(tmp_path: Path, monkeypatch):
    from conclave.org import load_org
    from conclave.bus import Conclavebus

    # Copy product_squad.yml to tmp
    src = Path(__file__).parent.parent / "examples" / "product_squad.yml"
    if not src.exists():
        # Fall back to writing a minimal org
        yml = tmp_path / "org.yml"
        yml.write_text("""org:
  name: "Product Squad"
  deliberation: hierarchy
  agents:
    - role: CPO
      persona: "CPO."
      tools: []
    - role: TechLead
      persona: "TL."
      reports_to: CPO
      tools: []
""")
    else:
        yml = tmp_path / "org.yml"
        yml.write_text(src.read_text())

    client = MagicMock()
    counter = {"n": 0}
    client.messages.create.side_effect = _responder(counter)

    agents, org_name, delib, entry = load_org(yml, client)
    trail = tmp_path / "trail.jsonl"
    bus = Conclavebus(agents=agents, deliberation=delib, trail_path=trail, max_turns=6)
    bus.run("Design a checkout API", entry_agent=entry)

    assert trail.exists()
    # At least some agent had usage recorded
    total_calls = sum(len(a.cost_meter._usage) for a in agents.values())
    assert total_calls >= 1
