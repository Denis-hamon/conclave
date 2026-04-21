"""Unit tests for DryRunClient — the zero-API-call stand-in."""

from __future__ import annotations

import json

from conclave.dry_run import FAKE_CLASSIFIER, FAKE_EVALUATOR, DryRunClient


def test_init_stores_fake_key() -> None:
    c = DryRunClient()
    assert c.api_key == "dry-run"
    c2 = DryRunClient(api_key="explicit")
    assert c2.api_key == "explicit"


def test_create_returns_anthropic_shaped_response() -> None:
    """The response must quack like anthropic.Message so callers don't branch."""
    c = DryRunClient()
    resp = c.messages.create(
        model="claude-sonnet-4-6",
        system="You are Planner.",
        messages=[{"role": "user", "content": "Start the work"}],
    )
    assert hasattr(resp, "content")
    assert hasattr(resp, "usage")
    assert hasattr(resp, "model")
    assert hasattr(resp, "stop_reason")
    assert resp.model == "claude-sonnet-4-6"
    assert resp.content[0].type == "text"
    assert isinstance(resp.content[0].text, str)
    assert resp.content[0].text  # non-empty
    assert resp.usage.input_tokens > 0
    assert resp.usage.output_tokens > 0


def test_classifier_system_prompt_routes_to_fake_classifier() -> None:
    c = DryRunClient()
    resp = c.messages.create(
        model="claude-haiku-4-5-20251001",
        system="You are the routing classifier. Decide haiku vs sonnet.",
        messages=[{"role": "user", "content": "task"}],
    )
    parsed = json.loads(resp.content[0].text)
    assert parsed == FAKE_CLASSIFIER


def test_evaluator_system_prompt_routes_to_fake_evaluator() -> None:
    c = DryRunClient()
    resp = c.messages.create(
        model="claude-haiku-4-5-20251001",
        system="You are an evaluator scoring haiku output against sonnet reference.",
        messages=[{"role": "user", "content": "grade this"}],
    )
    parsed = json.loads(resp.content[0].text)
    assert parsed == FAKE_EVALUATOR


def test_generic_agent_prompt_produces_non_empty_text() -> None:
    c = DryRunClient()
    resp = c.messages.create(
        model="claude-sonnet-4-6",
        system="You are QA_Engineer. You report to TechLead.",
        messages=[{"role": "user", "content": "Review the spec."}],
    )
    text = resp.content[0].text
    assert text.strip(), "generic agent synthesis must return text"


def test_unused_kwargs_do_not_crash() -> None:
    """The real SDK takes many kwargs (temperature, tools, ...); we must be tolerant."""
    c = DryRunClient()
    resp = c.messages.create(
        model="claude-haiku-4-5-20251001",
        system="",
        messages=[],
        temperature=0.5,
        tools=[{"name": "x"}],
        metadata={"user_id": "u"},
    )
    assert resp.model == "claude-haiku-4-5-20251001"
