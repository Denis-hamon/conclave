"""Shared pytest fixtures for Conclave tests."""
from __future__ import annotations
from pathlib import Path
from unittest.mock import MagicMock
import pytest


def _mock_response(text: str, input_tokens: int = 100, output_tokens: int = 50):
    resp = MagicMock()
    resp.content = [MagicMock(text=text)]
    resp.usage = MagicMock(input_tokens=input_tokens, output_tokens=output_tokens)
    return resp


@pytest.fixture
def mock_client():
    """MagicMock mimicking anthropic.Anthropic with a default messages.create response."""
    client = MagicMock()
    client.messages.create.return_value = _mock_response("default mock response")
    # Expose helper to build responses inside tests
    client._make_response = _mock_response
    return client


@pytest.fixture
def make_response():
    """Factory fixture to build mock Anthropic responses."""
    return _mock_response


@pytest.fixture
def sample_org_yaml(tmp_path: Path) -> Path:
    content = """org:
  name: "Test Org"
  deliberation: hierarchy
  agents:
    - role: Lead
      persona: "You are a lead agent."
      tools: []
    - role: Worker
      persona: "You are a worker agent."
      reports_to: Lead
      tools: []
"""
    p = tmp_path / "conclave.yml"
    p.write_text(content)
    return p
