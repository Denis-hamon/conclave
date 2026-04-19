# Contributing to Conclave

Conclave is early. The highest-leverage contributions right now are not code — they're **personas and org configs** that actually work.

## What we need most

### 1. Org templates
Real team structures that produce useful deliberation. If your squad has a dynamic that works well, encode it.  
→ Add a YAML to `examples/` and open a PR.

### 2. Persona library
The quality of an agent is almost entirely in its persona. A well-written persona produces dramatically better deliberation than a vague one.  
→ Good personas are specific, opinionated, and describe *how the role thinks*, not just what it does.

**Example of a weak persona:**
```yaml
persona: "You are a product manager. You manage products."
```

**Example of a strong persona:**
```yaml
persona: |
  You are a PM who has shipped three B2B SaaS products.
  You write one-pagers before anything else. You push back on scope creep
  immediately. You never say yes to a feature without asking "what do we cut?"
  You are direct in writing and flag ambiguity before it becomes a blocker.
```

### 3. Deliberation strategies
Beyond `hierarchy`, `consensus`, and `first-valid` — what other org coordination patterns are worth implementing?  
→ Open an issue with the pattern name, a description of when it's useful, and pseudocode.

### 4. MCP connectors
Each tool in an agent's `tools:` list maps to an MCP server. Help us expand coverage.  
→ See `conclave/mcp/` for the connector interface.

## Code contributions

- Python 3.11+
- Run `pip install -e ".[dev]"` for dev dependencies
- `pytest tests/` before opening a PR
- Keep it simple. Conclave's core is 4 files. Don't bloat it.

## Philosophy

> An org isn't a DAG. It's a living system of accountabilities.

Every design decision in Conclave flows from this. We model *organizational behavior*, not just task pipelines.

If a proposed change makes Conclave more like LangGraph or CrewAI, it's probably wrong.
