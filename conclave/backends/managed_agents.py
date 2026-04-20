"""
conclave/backends/managed_agents.py

Anthropic Managed Agents backend (beta).

Semantics:
  - Each role gets a long-lived server-side session.
  - Only the new turn is sent per call; history lives on Anthropic's side.
  - Cost/latency profile: lower input-token bill across long deliberations,
    one round-trip per message.

Beta header:
    anthropic-beta: managed-agents-2026-04-01

If the beta is not available on the account, the backend falls back to
AnthropicDirectBackend so user code keeps working. The fallback is loud —
a single warning is emitted the first time it happens.
"""

from __future__ import annotations

import os
import sys
import warnings

import httpx

from .anthropic_direct import AnthropicDirectBackend
from .base import AgentBackend, BackendResponse

BETA_HEADER = "managed-agents-2026-04-01"
DEFAULT_BASE_URL = "https://api.anthropic.com"


class ManagedAgentsBackend(AgentBackend):
    name = "managed_agents"

    def __init__(
        self,
        client,
        api_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        http_timeout: float = 60.0,
    ):
        self.client = client
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.base_url = base_url.rstrip("/")
        self._timeout = http_timeout
        self._agent_ids: dict[str, str] = {}  # role → agent_id
        self._fell_back = False
        self._fallback = AnthropicDirectBackend(client=client)
        self._http = httpx.Client(timeout=http_timeout, headers=self._headers())

    # ------------------------------------------------------------------
    def _headers(self) -> dict:
        return {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "anthropic-beta": BETA_HEADER,
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------
    def create_session(self, role: str, system: str, model: str) -> str:
        """POST /v1/agents then POST /v1/sessions. Fall back on 4xx/5xx."""
        try:
            # 1. Create agent definition (idempotent on role name)
            agent_id = self._agent_ids.get(role)
            if not agent_id:
                r = self._http.post(
                    f"{self.base_url}/v1/agents",
                    json={"name": role, "system": system, "model": model},
                )
                self._raise_for_beta(r)
                agent_id = r.json().get("id") or r.json().get("agent_id")
                if not agent_id:
                    raise RuntimeError("Managed Agents: no agent_id in response")
                self._agent_ids[role] = agent_id

            # 2. Create session
            r = self._http.post(
                f"{self.base_url}/v1/sessions",
                json={"agent_id": agent_id, "model": model},
            )
            self._raise_for_beta(r)
            sid = r.json().get("id") or r.json().get("session_id")
            if not sid:
                raise RuntimeError("Managed Agents: no session_id in response")
            return f"managed:{sid}"
        except Exception as exc:
            self._fallback_once(exc)
            return self._fallback.create_session(role, system, model)

    # ------------------------------------------------------------------
    def send(
        self,
        session_id: str,
        messages: list[dict],
        model: str,
        system: str,
        max_tokens: int = 1024,
    ) -> BackendResponse:
        if not session_id.startswith("managed:"):
            # We fell back earlier — stay in fallback mode for consistency.
            return self._fallback.send(session_id, messages, model, system, max_tokens)

        sid = session_id.removeprefix("managed:")
        # Only send the newest user turn — the server keeps history.
        last_user = next(
            (m for m in reversed(messages) if m.get("role") == "user"),
            messages[-1] if messages else {"role": "user", "content": ""},
        )
        try:
            r = self._http.post(
                f"{self.base_url}/v1/sessions/{sid}/messages",
                json={
                    "content": last_user.get("content", ""),
                    "max_tokens": max_tokens,
                },
            )
            self._raise_for_beta(r)
            data = r.json()
            # Expected shape (subject to GA): {"content":[{"text":...}], "usage":{"input_tokens":..,"output_tokens":..}}
            content_blocks = data.get("content") or []
            text = ""
            for block in content_blocks:
                if isinstance(block, dict) and block.get("type", "text") == "text":
                    text = block.get("text", "")
                    break
            usage = data.get("usage") or {}
            return BackendResponse(
                text=text,
                input_tokens=int(usage.get("input_tokens", 0)),
                output_tokens=int(usage.get("output_tokens", 0)),
                model=data.get("model", model),
            )
        except Exception as exc:
            self._fallback_once(exc)
            return self._fallback.send(session_id, messages, model, system, max_tokens)

    # ------------------------------------------------------------------
    def close_session(self, session_id: str) -> None:
        if not session_id.startswith("managed:"):
            return self._fallback.close_session(session_id)
        sid = session_id.removeprefix("managed:")
        try:
            self._http.delete(f"{self.base_url}/v1/sessions/{sid}")
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _raise_for_beta(self, r: httpx.Response) -> None:
        if r.status_code == 404 or r.status_code == 403:
            raise RuntimeError(
                f"Managed Agents beta unavailable on this account "
                f"(HTTP {r.status_code}). Falling back to anthropic_direct."
            )
        r.raise_for_status()

    def _fallback_once(self, exc: Exception) -> None:
        if self._fell_back:
            return
        self._fell_back = True
        msg = (
            f"[conclave.managed_agents] {exc}\n"
            f"[conclave.managed_agents] Falling back to anthropic_direct for the rest of this run.\n"
        )
        print(msg, file=sys.stderr)
        warnings.warn(str(exc), RuntimeWarning, stacklevel=2)
