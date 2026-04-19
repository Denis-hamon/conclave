"""
conclave/agent.py

Each Conclave agent = one persistent organizational role.

Every incoming message is classified by the TaskRouter before execution:
  - Novel / complex tasks     → Sonnet (the role's deliberative brain)
  - Repetitive / simple tasks → Haiku correction loop (cheap, iterative)
  - Filesystem / code tasks   → delegated to DeepAgents

The agent accumulates a persistent conversation history (its "memory").
The router prevents that history from becoming a pure token cost liability
by using cheaper models when the task doesn't warrant Sonnet.
"""
from __future__ import annotations
import time
from dataclasses import dataclass, field
from typing import Optional
import anthropic

from .router import TaskRouter, ModelTier, ExecutorType
from .executors.haiku_loop import HaikuCorrectionLoop
from .executors.deepagents import run_deepagents
from .cost import CostMeter


@dataclass
class Message:
    sender:       str
    recipient:    str
    content:      str
    msg_type:     str = "message"
    reasoning:    Optional[str] = None
    timestamp:    float = field(default_factory=time.time)
    model_used:   Optional[str] = None
    iterations:   Optional[int] = None
    tokens_saved: Optional[float] = None

    def to_dict(self) -> dict:
        d = {
            "ts":        time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.timestamp)),
            "from":      self.sender,
            "to":        self.recipient,
            "type":      self.msg_type,
            "content":   self.content,
            "reasoning": self.reasoning,
        }
        if self.model_used:
            d["model_used"] = self.model_used
        if self.iterations is not None:
            d["iterations"] = self.iterations
        if self.tokens_saved is not None:
            d["tokens_saved_usd"] = round(self.tokens_saved, 5)
        return d


SYSTEM_TEMPLATE = """
You are the {role} in a multi-agent organization called {org_name}.

YOUR PERSONA:
{persona}

YOUR TOOLS: {tools}

DELIBERATION MODE: {deliberation}

PROTOCOL:
- You receive messages from other agents or from the user.
- Send messages TO specific agents: "[TO: RoleName]"
- Escalate to your manager: "[ESCALATE: RoleName]"
- Produce final outputs: "[OUTPUT: filename]"
- State your reasoning: "[REASONING: ...]"
- Be concise. Other agents are waiting.

You report to: {reports_to}
Org hierarchy:
{org_structure}
""".strip()


class ConclaveAgent:
    """
    One role in the organization. Persistent memory. Smart model routing.

    Token cost philosophy:
      The persistent history of this agent grows with every turn.
      We refuse to send that growing context to Sonnet for tasks that
      Haiku can solve with a correction loop. The router decides per task.
    """

    def __init__(
        self,
        role:          str,
        persona:       str,
        org_name:      str,
        tools:         list[str],
        reports_to:    Optional[str],
        org_structure: str,
        deliberation:  str,
        client:        anthropic.Anthropic,
        executor:      str = "native",
        force_model:   Optional[str] = None,
        backend:       str = "anthropic",
    ):
        self.role        = role
        self.persona     = persona
        self.tools       = tools
        self.reports_to  = reports_to or "nobody — you are the top of the hierarchy"
        self.executor    = executor
        self.force_model = force_model
        self.history:    list[dict] = []
        self.client      = client
        self.cost_meter  = CostMeter()
        self._router     = TaskRouter(client)
        self.backend_name = backend
        self._backend   = None
        self._session_id = None

        self._system = SYSTEM_TEMPLATE.format(
            role=role,
            org_name=org_name,
            persona=persona,
            tools=", ".join(tools) if tools else "none",
            deliberation=deliberation,
            reports_to=self.reports_to,
            org_structure=org_structure,
        )

    def receive(self, msg: Message) -> Message:
        user_turn = f"[FROM: {msg.sender}]\n{msg.content}"
        self.history.append({"role": "user", "content": user_turn})

        decision = self._router.route(
            task=msg.content,
            role=self.role,
            executor_override=self.executor if self.executor != "native" else None,
        )

        if self.force_model:
            decision.model    = ModelTier(self.force_model)
            decision.use_loop = False

        if decision.executor == ExecutorType.DEEPAGENTS:
            response_text, iterations, tokens_saved = self._run_deepagents(msg.content, decision)
        elif decision.use_loop:
            response_text, iterations, tokens_saved = self._run_haiku_loop(msg.content, decision)
        else:
            response_text, iterations, tokens_saved = self._run_sonnet(decision)

        self.history.append({"role": "assistant", "content": response_text})
        response = self._parse_response(response_text)
        response.model_used   = decision.model.value
        response.iterations   = iterations
        response.tokens_saved = tokens_saved
        return response

    def _ensure_backend(self, model: str):
        if self._backend is None:
            from .backends import get_backend
            self._backend = get_backend(self.backend_name, client=self.client)
            self._session_id = self._backend.create_session(self.role, self._system, model)
        return self._backend

    def _run_sonnet(self, decision) -> tuple[str, int, float]:
        backend = self._ensure_backend(decision.model.value)
        resp = backend.send(
            session_id=self._session_id,
            messages=self.history,
            model=decision.model.value,
            system=self._system,
            max_tokens=1024,
        )
        self.cost_meter.record(decision.model, resp.input_tokens, resp.output_tokens)
        return resp.text, 1, 0.0

    def _run_haiku_loop(self, task: str, decision) -> tuple[str, int, float]:
        loop   = HaikuCorrectionLoop(self.client, decision, self.role)
        result = loop.run(task)
        self.cost_meter.merge(result.cost_meter)
        return result.output, result.iterations, result.cost_meter.savings

    def _run_deepagents(self, task: str, decision) -> tuple[str, int, float]:
        output = run_deepagents(task=task, role=self.role, model=decision.model.value)
        return output, 1, 0.0

    def _parse_response(self, text: str) -> Message:
        lines, recipient, msg_type, reasoning, content_lines = (
            text.strip().splitlines(), None, "message", None, []
        )
        for line in lines:
            if line.startswith("[TO:"):
                recipient = line.split(":")[1].strip().rstrip("]").strip()
                msg_type  = "handoff"
            elif line.startswith("[ESCALATE:"):
                recipient = line.split(":")[1].strip().rstrip("]").strip()
                msg_type  = "escalation"
            elif line.startswith("[OUTPUT:"):
                msg_type  = "output"
                content_lines.append(line)
            elif line.startswith("[REASONING:"):
                reasoning = line.replace("[REASONING:", "").rstrip("]").strip()
            else:
                content_lines.append(line)

        return Message(
            sender=self.role,
            recipient=recipient or "bus",
            content="\n".join(content_lines).strip(),
            msg_type=msg_type,
            reasoning=reasoning,
        )
