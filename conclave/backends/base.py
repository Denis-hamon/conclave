"""
conclave/backends/base.py

Abstract base for agent execution backends.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class BackendResponse:
    text: str
    input_tokens: int
    output_tokens: int
    model: str


class AgentBackend(ABC):
    """
    A backend is responsible for producing assistant responses for one role.

    Lifecycle:
      1. create_session(role, system_prompt) → session_id
      2. send(session_id, messages)         → BackendResponse
      3. (optionally) close_session(session_id)

    Stateless backends (AnthropicDirectBackend) ignore session_id and send the
    full history each call. Stateful backends (ManagedAgentsBackend) persist
    the history server-side and only send the new turn.
    """

    #: Human-readable name used in logs.
    name: str = "base"

    @abstractmethod
    def create_session(self, role: str, system: str, model: str) -> str:
        """Return an opaque session_id for this role."""

    @abstractmethod
    def send(self, session_id: str, messages: list[dict], model: str,
             system: str, max_tokens: int = 1024) -> BackendResponse:
        """Send a turn and return the assistant response + usage."""

    def close_session(self, session_id: str) -> None:
        """Optional cleanup — default is a no-op."""
        return None
