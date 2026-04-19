"""Unit tests for Conclavebus."""
from __future__ import annotations
import json
from pathlib import Path
from conclave.agent import ConclaveAgent, Message
from conclave.bus import Conclavebus


def _classifier_payload():
    return json.dumps({
        "novelty": 0.9, "complexity": 0.9,
        "is_repetitive": False, "needs_filesystem": False,
        "rationale": "complex"
    })


def _agent(mock_client, role, reports_to=None):
    return ConclaveAgent(
        role=role, persona=f"{role} persona", org_name="TestOrg", tools=[],
        reports_to=reports_to, org_structure=f"{role}", deliberation="hierarchy",
        client=mock_client,
    )


def test_single_turn_routing(mock_client, tmp_path: Path):
    mock_client.messages.create.side_effect = [
        mock_client._make_response(_classifier_payload()),
        mock_client._make_response("[TO: Worker]\nDo this"),
        mock_client._make_response(_classifier_payload()),
        mock_client._make_response("[OUTPUT: result.md]\nDone"),
    ]
    lead = _agent(mock_client, "Lead")
    worker = _agent(mock_client, "Worker", reports_to="Lead")
    bus = Conclavebus(
        agents={"Lead": lead, "Worker": worker},
        deliberation="hierarchy",
        trail_path=tmp_path / "trail.jsonl",
        max_turns=5,
    )
    outputs = bus.run("Goal", entry_agent="Lead")
    assert len(outputs) == 1


def test_decision_trail_written(mock_client, tmp_path: Path):
    mock_client.messages.create.side_effect = [
        mock_client._make_response(_classifier_payload()),
        mock_client._make_response("[OUTPUT: x.md]\nDone"),
    ]
    lead = _agent(mock_client, "Lead")
    trail = tmp_path / "trail.jsonl"
    bus = Conclavebus(
        agents={"Lead": lead}, deliberation="hierarchy",
        trail_path=trail, max_turns=2,
    )
    bus.run("Goal", entry_agent="Lead")
    assert trail.exists()
    for line in trail.read_text().splitlines():
        entry = json.loads(line)
        assert "from" in entry
        assert "to" in entry
        assert "type" in entry
        assert "content" in entry


def test_max_turns_stops_loop(mock_client, tmp_path: Path):
    # Each turn = 2 API calls (classifier + agent). Loop should stop at 2 turns.
    responses = []
    for _ in range(10):
        responses.append(mock_client._make_response(_classifier_payload()))
        responses.append(mock_client._make_response("[TO: Worker]\nMore"))
        responses.append(mock_client._make_response(_classifier_payload()))
        responses.append(mock_client._make_response("[TO: Lead]\nMore"))
    mock_client.messages.create.side_effect = responses

    lead = _agent(mock_client, "Lead")
    worker = _agent(mock_client, "Worker", reports_to="Lead")
    bus = Conclavebus(
        agents={"Lead": lead, "Worker": worker},
        deliberation="hierarchy",
        trail_path=tmp_path / "trail.jsonl",
        max_turns=2,
    )
    bus.run("Goal", entry_agent="Lead")
    # Trail captures one entry per turn
    assert len(bus.trail) == 2
