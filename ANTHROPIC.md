# Conclave × Anthropic

> A note for Anthropic's DevRel and product teams.
> Conclave is built entirely on Claude and Anthropic primitives.
> This document explains *how*, *why*, and *what gap it fills*.

---

## 1 — How Conclave uses Anthropic primitives

### Managed Agents

Each `ConclaveAgent` is designed to map one-to-one onto a Managed Agent
session. Today we emulate the contract (`session_id`, persistent history,
system prompt) using the stateless `messages.create()` API. When Managed
Agents GA ships, the migration is a single-file swap (`conclave/agent.py`) —
see the Sprint 5 backend abstraction in `CLAUDE_CODE_ROADMAP.md`.

The beta header we target:

```http
anthropic-beta: managed-agents-2026-04-01
```

### MCP

Each entry in an agent's `tools:` list maps to an MCP server connector.
An agent declared as:

```yaml
- role: TechLead
  tools: [github, linear]
```

…receives MCP tool access for those servers. Today the mapping is static
(`tools/github.yaml` registry). Roadmap: dynamic MCP server discovery.

### Model tier strategy

Conclave deliberately splits work across the Claude family:

| Layer                   | Model                        | Rationale |
|-------------------------|------------------------------|-----------|
| Task classifier         | `claude-haiku-4-5`           | Cheap, ironic, and intentional — the router that decides who runs runs on the smallest model |
| Simulation evaluator    | `claude-haiku-4-5`           | Fast self-evaluation in the Haiku correction loop |
| Skillset distillation   | `claude-sonnet-4-6`          | Quality-critical: builds the rubric Haiku will follow |
| Agent deliberation      | `claude-sonnet-4-6`          | Default for novel / complex tasks |
| Certified repetitive    | `claude-haiku-4-5`           | Once a skillset is certified, route stays on Haiku permanently |

### Claude Code

The `/conclave` slash command (`.claude/commands/conclave.md`) brings the
entire pipeline into Claude Code: Claude can invoke an org, inspect the
Decision Trail, and route follow-up work back through Conclave.

---

## 2 — The gap Conclave fills

- **Managed Agents ships single-agent today.** Conclave demonstrates
  multi-agent *coordination* — hierarchy, escalation, deliberation modes,
  persistent role memory — natively on top of Anthropic's primitives.

- **No existing tool models org-level accountability.** Conclave treats a
  "role" as a first-class construct: persona, reporting chain, tool access,
  per-role cost accounting, and a Decision Trail that is auditable.

- **The certification pipeline validates the tier strategy.** Observatory
  → Skillset → Simulator → Certifier produces empirical evidence that a
  given repetitive task can run on Haiku at Sonnet quality. This is the
  missing feedback loop that makes model-tier choices rigorous instead of
  vibes-driven.

---

## 3 — What Conclave is not

- **Not a LangChain wrapper.** Zero LangChain in the core path. DeepAgents
  is an optional executor, not a dependency.
- **Not a competitor to Managed Agents.** Conclave is the org layer on top.
  When Managed Agents GA ships, Conclave uses it as the backend.
- **Not a fine-tuning tool.** The certification pipeline distills
  *prompts and rubrics*, not weights.

---

## 4 — Integration roadmap

- **v0.1** — stateless emulation via `messages.create()` (current)
- **v0.2** — Managed Agents backend behind a feature flag
  (see `CLAUDE_CODE_ROADMAP.md` Sprint 5)
- **v0.3** — native streaming, MCP tool discovery, session persistence
- **v0.4** — observability hooks for Anthropic-side telemetry

Conclave is designed to grow *with* the Anthropic platform — we do not want
to recreate primitives Anthropic will eventually ship. We want to be the
reference implementation of the org layer built on top of them.
