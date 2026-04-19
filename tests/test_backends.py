"""Unit tests for backend abstraction."""
from __future__ import annotations
from unittest.mock import MagicMock, patch
import httpx
import pytest

from conclave.backends import get_backend, AnthropicDirectBackend, ManagedAgentsBackend


def _resp(text="ok", in_tok=10, out_tok=5):
    r = MagicMock()
    r.content = [MagicMock(text=text)]
    r.usage = MagicMock(input_tokens=in_tok, output_tokens=out_tok)
    return r


def test_get_backend_selector():
    client = MagicMock()
    assert isinstance(get_backend("anthropic", client=client), AnthropicDirectBackend)
    assert isinstance(get_backend("direct", client=client), AnthropicDirectBackend)
    assert isinstance(get_backend("managed_agents", client=client), ManagedAgentsBackend)
    with pytest.raises(ValueError):
        get_backend("nope", client=client)


def test_direct_backend_send_records_usage():
    client = MagicMock()
    client.messages.create.return_value = _resp(text="hello", in_tok=12, out_tok=3)
    be = AnthropicDirectBackend(client=client)
    sid = be.create_session("Lead", "system", "claude-sonnet-4-6")
    out = be.send(sid, [{"role": "user", "content": "hi"}],
                  model="claude-sonnet-4-6", system="system")
    assert out.text == "hello"
    assert out.input_tokens == 12
    assert out.output_tokens == 3


def test_managed_agents_falls_back_on_404():
    client = MagicMock()
    be = ManagedAgentsBackend(client=client, api_key="k")
    # Force the internal httpx client to return 404 on POST /v1/agents
    def _fake_post(url, json=None, **kwargs):
        r = httpx.Response(status_code=404, request=httpx.Request("POST", url))
        return r
    be._http.post = _fake_post
    # Fallback path delegates to AnthropicDirectBackend
    client.messages.create.return_value = _resp("fallback-ok", 8, 2)
    sid = be.create_session("Lead", "sys", "claude-sonnet-4-6")
    out = be.send(sid, [{"role": "user", "content": "hi"}],
                  model="claude-sonnet-4-6", system="sys")
    assert out.text == "fallback-ok"
    assert be._fell_back is True
