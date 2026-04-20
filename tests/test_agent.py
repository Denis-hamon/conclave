"""Unit tests for ConclaveAgent."""

from __future__ import annotations

import json

from conclave.agent import ConclaveAgent, Message


def _classifier_payload(**overrides):
    base = {
        "novelty": 0.9,
        "complexity": 0.9,
        "is_repetitive": False,
        "needs_filesystem": False,
        "rationale": "complex",
    }
    base.update(overrides)
    return json.dumps(base)


def _make_agent(mock_client, **kwargs):
    defaults = dict(
        role="Lead",
        persona="lead persona",
        org_name="TestOrg",
        tools=[],
        reports_to=None,
        org_structure="Lead",
        deliberation="hierarchy",
        client=mock_client,
    )
    defaults.update(kwargs)
    return ConclaveAgent(**defaults)


def test_receive_returns_message(mock_client):
    mock_client.messages.create.side_effect = [
        mock_client._make_response(_classifier_payload()),
        mock_client._make_response(
            "[TO: Worker]\nHere is the task.\n[REASONING: delegating to worker]"
        ),
    ]
    agent = _make_agent(mock_client)
    msg = Message(sender="user", recipient="Lead", content="do a thing")
    resp = agent.receive(msg)
    assert resp.recipient == "Worker"
    assert resp.msg_type == "handoff"
    assert resp.reasoning is not None
    assert "delegating" in resp.reasoning


def test_history_accumulates(mock_client):
    mock_client.messages.create.side_effect = [
        mock_client._make_response(_classifier_payload()),
        mock_client._make_response("[TO: Worker]\nOne"),
        mock_client._make_response(_classifier_payload()),
        mock_client._make_response("[TO: Worker]\nTwo"),
    ]
    agent = _make_agent(mock_client)
    agent.receive(Message(sender="user", recipient="Lead", content="a"))
    agent.receive(Message(sender="user", recipient="Lead", content="b"))
    assert len(agent.history) == 4


def test_output_parsed(mock_client):
    mock_client.messages.create.side_effect = [
        mock_client._make_response(_classifier_payload()),
        mock_client._make_response("[OUTPUT: spec.md]\n# Spec\ncontent here"),
    ]
    agent = _make_agent(mock_client)
    resp = agent.receive(Message(sender="user", recipient="Lead", content="spec it"))
    assert resp.msg_type == "output"


def test_escalation_parsed(mock_client):
    mock_client.messages.create.side_effect = [
        mock_client._make_response(_classifier_payload()),
        mock_client._make_response("[ESCALATE: Lead]\nNeed authority."),
    ]
    agent = _make_agent(mock_client, role="Worker", reports_to="Lead")
    resp = agent.receive(Message(sender="Lead", recipient="Worker", content="handle"))
    assert resp.msg_type == "escalation"
    assert resp.recipient == "Lead"
