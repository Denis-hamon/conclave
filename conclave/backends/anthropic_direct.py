"""
conclave/backends/anthropic_direct.py

Stateless backend that wraps anthropic.Anthropic.messages.create().
This is the current default and the reference implementation.

Full history is re-sent on every turn. It is the simplest possible backend
and it is intentionally stable: Managed Agents is the forward path, this one
is the baseline everything else is compared to.
"""

from __future__ import annotations

import uuid

from .base import AgentBackend, BackendResponse


class AnthropicDirectBackend(AgentBackend):
    name = "anthropic_direct"

    def __init__(self, client):
        self.client = client
        # No server-side session — we just track systems/models per local id.
        self._sessions: dict[str, dict] = {}

    def create_session(self, role: str, system: str, model: str) -> str:
        sid = f"local-{role}-{uuid.uuid4().hex[:8]}"
        self._sessions[sid] = {"role": role, "system": system, "model": model}
        return sid

    def send(
        self,
        session_id: str,
        messages: list[dict],
        model: str,
        system: str,
        max_tokens: int = 1024,
    ) -> BackendResponse:
        resp = self.client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
        )
        return BackendResponse(
            text=resp.content[0].text,
            input_tokens=resp.usage.input_tokens,
            output_tokens=resp.usage.output_tokens,
            model=model,
        )

    def close_session(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
