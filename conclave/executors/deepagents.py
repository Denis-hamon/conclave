"""
conclave/executors/deepagents.py

DeepAgents executor integration.

When a Conclave agent needs to perform heavy execution work
(code generation, file operations, shell commands, multi-step research),
it delegates to a DeepAgents harness rather than trying to do it
itself in a conversational loop.

This decoupling is intentional:
  - Conclave agents THINK like a role (persona, memory, deliberation)
  - DeepAgents EXECUTE like a capable worker (filesystem, shell, sub-agents)

A TechLead in Conclave deliberates and writes a spec.
A DeepAgents worker takes that spec and writes the actual code.
"""
from __future__ import annotations
from typing import Optional


def is_deepagents_available() -> bool:
    try:
        import deepagents  # noqa: F401
        return True
    except ImportError:
        return False


def run_deepagents(
    task: str,
    role: str,
    model: str = "claude-sonnet-4-6",
    tools: Optional[list] = None,
    system_prompt: Optional[str] = None,
) -> str:
    """
    Delegate a task to a DeepAgents harness.

    Returns the final text output of the agent run.
    Falls back gracefully if deepagents is not installed.
    """
    if not is_deepagents_available():
        return (
            "[DeepAgents not installed — install with: pip install deepagents]\n\n"
            f"Task that would have been delegated:\n{task}"
        )

    from deepagents import create_deep_agent
    from langchain.chat_models import init_chat_model

    system = system_prompt or (
        f"You are executing a task on behalf of the {role} in an organization. "
        f"Be precise and complete. Produce the requested output and nothing else."
    )

    agent = create_deep_agent(
        model=init_chat_model(f"anthropic:{model}"),
        tools=tools or [],
        system_prompt=system,
    )

    result = agent.invoke({
        "messages": [{"role": "user", "content": task}]
    })

    # DeepAgents returns a dict with "messages" — extract the last assistant message
    messages = result.get("messages", [])
    for msg in reversed(messages):
        role_field = getattr(msg, "role", None) or (msg.get("role") if isinstance(msg, dict) else None)
        if role_field == "assistant":
            content = getattr(msg, "content", None) or (msg.get("content") if isinstance(msg, dict) else "")
            if isinstance(content, list):
                # Handle tool-use blocks
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        return block["text"]
            return str(content)

    return str(result)
