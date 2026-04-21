# v0.1.0 — Initial alpha release

> *A bureau of Claude agents that deliberates, decides, and delivers.*

Conclave 0.1.0 is the first published alpha of an opinionated multi-agent framework built natively on [Anthropic Managed Agents](https://docs.anthropic.com/managed-agents). Where other frameworks model **tasks** or **graphs**, Conclave models **roles** — with persistent accountability, structured deliberation, and a JSONL audit trail that doubles as a replay format.

## Highlights

### Define an org in YAML, not Python
Five production-ready templates ship out of the box — `product-squad`, `startup-5`, `growth-squad`, `creative-agency`, and a Claude-Code-specific `claude-code-squad` (Planner / Implementer / Reviewer / Tester). Add your own with a few lines of YAML and `conclave init --template <name>`.

### Three deliberation modes
Pick the coordination pattern that matches your team dynamic: `hierarchy` (each agent defers upward), `consensus` (everyone agrees before moving on), `first-valid` (race to a complete output).

### Token-aware routing by default
A classifier runs on Haiku 4.5 and decides per task whether to route to Haiku (cheap, iterative) or Sonnet 4.6 (novel, strategic). Production-typical workloads save 60–80% vs all-Sonnet. The `conclave benchmark` harness reproduces the numbers on 20 canonical tasks across 4 categories.

### Always-on Decision Trail
Every inter-agent message lands in a JSONL file with sender, recipient, type, content, and reasoning. Render it as a Mermaid `sequenceDiagram` with `conclave trail view --latest` for GitHub, Notion, or Obsidian — postmortem-ready in one command.

### Replay past runs with a different strategy
`conclave replay --latest --deliberation consensus` re-runs a stored trail under a new coordination pattern. Originals stay immutable; replays write to `replay_of_<original>_<ts>.jsonl`. Useful for "what if CPO had pushed for consensus?" and for regression-testing persona changes.

### Live control-plane dashboard
Ships with a single-file FastAPI + SSE dashboard built on the Claude / Anthropic design system (`dashboard-ui/DESIGN.md`, via `npx getdesign add claude`). Four MetricCards, four 14-day ChartCards, a dual live feed, and a warm dark palette with terracotta accent. Launch with `conclave dashboard`.

### Certification loop
Observe production runs (`conclave observe`), distill a Haiku-reproducible skillset (`conclave simulate`), certify the policy (`conclave certify`) — evidence-based promotion of repetitive tasks from Sonnet to Haiku.

### Managed Agents-first, with a graceful fallback
`conclave/backends/managed_agents.py` targets the Anthropic Managed Agents beta (`anthropic-beta: managed-agents-2026-04-01`). If the beta is not enabled on the account, it falls back transparently to `AnthropicDirectBackend` with a one-time warning, so user code keeps working.

## Installing

```bash
pip install conclave-agents
```

Quickstart:

```bash
conclave init --template product-squad          # or claude-code-squad
conclave run "Ship the auth rewrite" --dry-run  # no API key needed
conclave trail view --latest                    # Mermaid diagram
conclave dashboard                              # live UI at :7777
```

## Quality

- 40 tests, green on Python 3.11 / 3.12 / 3.13
- `mypy --strict` clean on `conclave.cost`, `conclave.replay`, `conclave.router`, `conclave.trail_view`
- Ruff lint + format gate in CI
- CodeQL Python security analysis on every push
- Dependabot weekly grouped updates for pip + github-actions
- MIT license, private vulnerability reporting via GitHub Advisories

## What's next

See the [Roadmap](https://github.com/Denis-hamon/conclave#roadmap) — four buckets by owner: Us (Pyodide demo, React dashboard), Community (personas, deliberation strategies), Anthropic (multi-session GA), Release plumbing.

## Credits

Built on [Managed Agents](https://docs.anthropic.com/managed-agents), [Model Context Protocol](https://modelcontextprotocol.io), Claude Haiku 4.5 / Sonnet 4.6, [getdesign](https://www.npmjs.com/package/getdesign) for the dashboard tokens, and the patience of the one-person-conclave reviewing every line of the Decision Trail.

---

**Full changelog**: https://github.com/Denis-hamon/conclave/blob/main/CHANGELOG.md
