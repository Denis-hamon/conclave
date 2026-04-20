"""Unit tests for TaskRouter."""

from __future__ import annotations

import json

from conclave.router import ExecutorType, ModelTier, TaskRouter


def _set_classifier(mock_client, payload):
    text = json.dumps(payload) if isinstance(payload, dict) else payload
    mock_client.messages.create.return_value = mock_client._make_response(text)


def test_routes_novel_task_to_sonnet(mock_client):
    _set_classifier(
        mock_client,
        {
            "novelty": 0.8,
            "complexity": 0.7,
            "is_repetitive": False,
            "needs_filesystem": False,
            "rationale": "novel strategic task",
        },
    )
    router = TaskRouter(mock_client)
    decision = router.route("Define Q3 strategy", role="CPO")
    assert decision.model == ModelTier.SONNET
    assert decision.use_loop is False
    assert decision.executor == ExecutorType.NATIVE


def test_routes_repetitive_task_to_haiku(mock_client):
    _set_classifier(
        mock_client,
        {
            "novelty": 0.1,
            "complexity": 0.2,
            "is_repetitive": True,
            "needs_filesystem": False,
            "rationale": "repetitive formatting",
        },
    )
    router = TaskRouter(mock_client)
    decision = router.route("Format this JSON", role="Worker")
    assert decision.model == ModelTier.HAIKU
    assert decision.use_loop is True
    assert decision.max_retries == 4


def test_routes_filesystem_task_to_deepagents(mock_client):
    _set_classifier(
        mock_client,
        {
            "novelty": 0.5,
            "complexity": 0.5,
            "is_repetitive": False,
            "needs_filesystem": True,
            "rationale": "needs repo access",
        },
    )
    router = TaskRouter(mock_client)
    decision = router.route("Refactor the auth module", role="TechLead")
    assert decision.executor == ExecutorType.DEEPAGENTS


def test_classifier_parse_error_fallback(mock_client):
    _set_classifier(mock_client, "not json at all {{{")
    router = TaskRouter(mock_client)
    decision = router.route("Some task", role="Lead")
    # Fallback defaults: novelty=0.6, complexity=0.6 → Sonnet
    assert decision.model == ModelTier.SONNET
    assert decision.novelty == 0.6
    assert decision.complexity == 0.6


def test_force_model_override(mock_client):
    """force_model is applied at the agent layer, but we verify router output is independent."""
    from conclave.agent import ConclaveAgent, Message

    # Classifier says: Sonnet
    _set_classifier(
        mock_client,
        {
            "novelty": 0.9,
            "complexity": 0.9,
            "is_repetitive": False,
            "needs_filesystem": False,
            "rationale": "complex",
        },
    )
    # After classifier call, subsequent call returns an agent response
    mock_client.messages.create.side_effect = [
        mock_client._make_response(
            json.dumps(
                {
                    "novelty": 0.9,
                    "complexity": 0.9,
                    "is_repetitive": False,
                    "needs_filesystem": False,
                    "rationale": "complex",
                }
            )
        ),
        mock_client._make_response("[TO: Worker]\nDelegated."),
    ]
    agent = ConclaveAgent(
        role="Lead",
        persona="lead",
        org_name="T",
        tools=[],
        reports_to=None,
        org_structure="Lead",
        deliberation="hierarchy",
        client=mock_client,
        force_model="claude-haiku-4-5-20251001",
    )
    msg = Message(sender="user", recipient="Lead", content="anything")
    resp = agent.receive(msg)
    assert resp.model_used == "claude-haiku-4-5-20251001"
