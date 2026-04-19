# Conclave

> *A bureau of Claude agents that deliberates, decides, and delivers.*

**Conclave** is an open-source multi-agent framework built natively on [Anthropic Managed Agents](https://docs.anthropic.com/managed-agents).  
Define your organization in YAML. Give it a goal. Watch your agents deliberate.

```bash
pip install conclave-agents
conclave run "Launch a new checkout API" --org examples/product_squad.yml
```

```
◆ Conclave · product_squad · 3 agents

  [CPO]       Received brief. Clarifying scope before delegating.
  [CPO → TechLead]  "I need a spec covering auth, idempotency, and rollback. Budget: 2 sprints."
  [TechLead]  Drafting spec. Flagging dependency on payment-service v3.
  [TechLead → QA]   "Spec attached. Prioritize payment flow edge cases."
  [QA]        Test plan generated. 3 blockers found, escalating.
  [QA → CPO]  "Blocker: payment-service v3 not yet in staging."

◆ Decision Trail saved → .conclave/trail_20260418.jsonl
◆ Artifacts → spec.md · test_plan.md · blockers.md
```

---

## Why Conclave

Anthropic built the managed agent.  
**Conclave builds the org chart.**

| | LangGraph / CrewAI | Conclave |
|---|---|---|
| Agent primitive | Task / Role | **Organizational role** |
| Coordination | DAG or fixed sequence | **Dynamic deliberation** |
| Memory | Per-run context | **Persistent per-role memory** |
| Infrastructure | You manage | **Managed Agents native** |
| Audit | Optional | **Decision Trail, always on** |
| Config | Python code | **YAML org definition** |

Conclave is the reference implementation of **org-native multi-agent coordination** — the pattern Anthropic has signaled as the next frontier of Managed Agents, made concrete today.

---

## Define your org in YAML

```yaml
# examples/product_squad.yml
org:
  name: "Product Squad"
  deliberation: consensus          # consensus | hierarchy | first-valid

  agents:
    - role: CPO
      persona: |
        Strategic and data-driven. Defines scope, validates business value.
        Asks clarifying questions before delegating. Never skips the "why".
      tools: [notion, slack]
      memory: persistent

    - role: TechLead
      persona: |
        Pragmatic. Writes tight specs, challenges assumptions, flags blockers early.
        Prefers two options over one recommendation.
      reports_to: CPO
      tools: [github, linear]
      memory: persistent

    - role: QA_Engineer
      persona: |
        Defensive thinker. Finds edge cases. Escalates blockers immediately.
      reports_to: TechLead
      tools: [github, browserbase]
```

---

## How it works

Conclave maps directly onto the Anthropic Managed Agents primitives:

```
conclave.yml
    │
    ├──► Managed Agent Session "CPO"        ← long-running, persistent state
    ├──► Managed Agent Session "TechLead"   ← long-running, persistent state
    ├──► Managed Agent Session "QA"         ← long-running, persistent state
    │
    └──► Conclave Bus (the coordination layer Managed Agents doesn't ship yet)
              │
              ├── Routes messages between agents
              ├── Applies deliberation strategy (consensus / hierarchy)
              └── Writes every handoff to the Decision Trail
```

Each agent is a **Claude Managed Agent session** with:
- Its own persona and toolset (via MCP servers)
- Persistent memory scoped to its role
- A structured inbox/outbox for inter-agent messages

---

## Decision Trail

Every action is logged with full provenance:

```jsonl
{"ts":"2026-04-18T09:01:12Z","from":"CPO","to":"TechLead","type":"delegation","content":"Need a spec covering auth, idempotency, and rollback. Budget: 2 sprints.","reasoning":"Business value validated. TechLead owns technical scope."}
{"ts":"2026-04-18T09:03:44Z","from":"TechLead","to":"QA","type":"handoff","content":"Spec attached. Prioritize payment flow edge cases.","reasoning":"Spec complete. QA gate before CPO review."}
{"ts":"2026-04-18T09:07:21Z","from":"QA","to":"CPO","type":"escalation","content":"Blocker: payment-service v3 not yet in staging.","reasoning":"Cannot validate end-to-end without staging parity. Requires CPO decision."}
```

Human-readable audit. Replayable. Debuggable.

---

## Deliberation modes

```bash
# Hierarchy: each agent defers to its manager
conclave run "Redesign onboarding" --deliberation hierarchy

# Consensus: agents iterate until all roles agree
conclave run "Define Q3 priorities" --deliberation consensus

# First-valid: first agent to produce a complete output wins
conclave run "Fix this bug" --deliberation first-valid
```

---

## MCP Integrations

Conclave agents use the same MCP servers as Claude Code and CoWork:

| Integration | Roles that use it |
|---|---|
| Notion | CPO, PM |
| Linear / Jira | TechLead, PM |
| GitHub | TechLead, QA, SWE |
| Slack | All roles |
| Browserbase | QA, Growth |
| Sentry | TechLead, QA |

---

## Org templates

```bash
conclave init --template startup-5         # CEO, CPO, TechLead, Designer, QA
conclave init --template product-squad     # CPO, PM, TechLead, QA
conclave init --template growth-squad      # CMO, Growth, Designer, Analyst
conclave init --template creative-agency   # CD, Copywriter, Art Director, PM
```

---

## Roadmap

- [x] Core agent bus + deliberation engine
- [x] Decision Trail
- [x] YAML org definition
- [x] MCP integrations (Notion, Linear, GitHub, Slack)
- [ ] `conclave simulate` — dry-run mode, no tools fired
- [ ] Org memory dashboard (local web UI)
- [ ] Role marketplace (community-contributed personas)
- [ ] Native Managed Agents multi-session API (in sync with Anthropic GA)
- [ ] `conclave replay` — re-run a past trail with a different deliberation strategy

---

## Philosophy

Most multi-agent frameworks define agents by **task**.  
Conclave defines agents by **role** — with the organizational context, persistent memory, and deliberation patterns that make enterprise coordination actually work.

An org isn't a DAG. It's a living system of accountabilities.  
Conclave models that.

---

## Contributing

Conclave is early. The best contributions right now:

- **Org templates** — battle-tested YAML configs for your team structure
- **Persona library** — role definitions that actually behave like the role
- **MCP connectors** — new integrations via the MCP server spec
- **Deliberation strategies** — new coordination patterns beyond the three built-ins

See [CONTRIBUTING.md](CONTRIBUTING.md).

---

## Built on

- [Anthropic Managed Agents](https://docs.anthropic.com/managed-agents)
- [Model Context Protocol](https://modelcontextprotocol.io)
- Claude Sonnet 4

---

*Conclave. From latin* cum clave *— locked in deliberation until the decision is made.*
