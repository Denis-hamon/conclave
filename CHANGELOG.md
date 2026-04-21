# Changelog

All notable changes to Conclave are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **`conclave replay`** — re-run a past Decision Trail through the org, optionally with a different deliberation strategy (`--deliberation consensus`, etc.). Useful to ask "what if CPO had used consensus instead of hierarchy?" or to regression-test a persona change against a known scenario. Lands a new trail as `replay_of_<original>_<ts>.jsonl` so originals stay immutable.
- **Trail meta entry** — every new run now writes a `{"type":"meta","goal":...,"deliberation":...,"entry_agent":...,"roles":[...]}` line as the first JSONL record. Legacy trails keep working via a best-effort `infer_goal_from_trail` fallback that picks up the first `user → entry_agent` delegation.
- **`conclave trail view`** — render a Decision Trail as a Mermaid `sequenceDiagram` (default) or ASCII timeline. The diagram renders natively on GitHub, Notion, Obsidian, making the JSONL audit log instantly diffable and shareable. `--latest` picks the newest trail in `.conclave/` automatically.
- **`claude-code-squad` org template** — Planner / Implementer / Reviewer / Tester, with personas written for devs using Claude Code. Available via `conclave init --template claude-code-squad` and as `examples/claude_code_squad.yml`.
- 6 unit tests covering trail → Mermaid rendering, content sanitization, empty-trail handling, and ASCII timeline output.
- **Dashboard v2** — full control-plane UI built on the Claude / Anthropic design system (see `dashboard-ui/DESIGN.md`). Adds:
  - Top-line **MetricCards** (agents, deliberations today, spend, routing savings).
  - 14-day **ChartCards** (run activity, handoff types, cost by role, model routing split).
  - Dual **feed** (live activity stream via SSE + recent outputs).
  - Warm-toned dark theme (terracotta brand, parchment-on-dark text, serif headlines).
- `dashboard-ui/DESIGN.md` generated via `npx getdesign add claude` — source of truth for future React rewrite.
- New backend endpoints: `/api/metrics`, `/api/charts`, `/api/activity`.
- `ConclaveBus`, `ConclaveAgent`, `CostMeter`, `TaskRouter`, `load_org` and friends are now direct imports from the top-level `conclave` package, with an explicit `__all__`.
- `conclave/py.typed` marker — downstream projects now benefit from the package's type hints.
- `benchmarks/run.py` + `benchmarks/README.md` — reproducible regeneration of `benchmarks/results.json` for CI or scripted runs.
- `.github/workflows/release.yml` — tag `v*.*.*` triggers a build + PyPI publish via trusted publishing (OIDC). Verifies the tag matches the `pyproject.toml` version before building.
- `SECURITY.md` — private vulnerability reporting via GitHub advisories, explicit threat-model scope.
- `.github/dependabot.yml` — weekly grouped pip updates + monthly github-actions updates.
- `.github/ISSUE_TEMPLATE/` — structured templates for bug reports, persona proposals, and deliberation strategies, with a config routing security reports to the private channel.
- `.github/PULL_REQUEST_TEMPLATE.md` aligned to the four contribution tracks in `CONTRIBUTING.md`.
- Three missing org templates (`startup_5.yml`, `growth_squad.yml`, `creative_agency.yml`) — the README referenced them but only `product_squad.yml` shipped.

### Changed
- **Breaking (pre-1.0):** class renamed `Conclavebus` → `ConclaveBus` (PEP 8). Update imports: `from conclave.bus import ConclaveBus`.
- CI now runs ruff lint + format as a separate job, and tests matrix over Python 3.11, 3.12, and 3.13.
- `pyproject.toml` gains `[tool.ruff]` and `[tool.pytest.ini_options]` config blocks.
- README Quickstart now points at source-based install (`git clone` + `pip install -e .`) until the package is published on PyPI.
- `CONTRIBUTING.md` no longer references the nonexistent `conclave/mcp/` directory.

### Removed
- PyPI badge from README — re-added when 0.1.0 is published.

### Fixed
- `conclave/certification/simulator.py`: replaced an E731 lambda with a proper `def` (no behavior change).

## [0.1.0] — 2026-04-19

Initial alpha release.

### Added
- Core agent bus + deliberation engine (`hierarchy`, `consensus`, `first-valid`).
- Decision Trail written as JSONL.
- YAML-based org definition.
- Routing policy: Haiku self-correction loop vs Sonnet, classifier-driven.
- Certification pipeline (`observatory` → `skillset` → `simulator` → `certifier`).
- Dashboard stub (FastAPI + single-file HTML).
- Benchmark harness over 20 tasks across 4 categories.
- MCP-ready tool declarations in the YAML.

[Unreleased]: https://github.com/Denis-hamon/conclave/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Denis-hamon/conclave/releases/tag/v0.1.0
