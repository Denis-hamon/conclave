"""
conclave.backends

Pluggable agent execution backends.

A backend is the mechanism Conclave uses to produce an assistant response for
a role. Today there are two production backends and one mock:

  - AnthropicDirectBackend   stateless messages.create() (current default)
  - ManagedAgentsBackend     Anthropic Managed Agents beta sessions
  - DryRunBackend            wraps DryRunClient, zero API calls

The goal is that when Managed Agents GA ships, switching is a one-line YAML
change (or a drop-in in the agent loop) — no rewrite.
"""

from .anthropic_direct import AnthropicDirectBackend
from .base import AgentBackend, BackendResponse
from .managed_agents import ManagedAgentsBackend


def get_backend(name: str, **kwargs) -> AgentBackend:
    """Resolve a backend by name (used by org.py)."""
    name = (name or "anthropic").lower()
    if name in ("anthropic", "anthropic_direct", "direct"):
        return AnthropicDirectBackend(**kwargs)
    if name in ("managed_agents", "managed", "sessions"):
        return ManagedAgentsBackend(**kwargs)
    raise ValueError(f"Unknown backend: {name!r}")


__all__ = [
    "AgentBackend",
    "BackendResponse",
    "AnthropicDirectBackend",
    "ManagedAgentsBackend",
    "get_backend",
]
