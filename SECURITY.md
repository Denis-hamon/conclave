# Security Policy

## Supported versions

Conclave is pre-1.0. Security fixes are applied to the `main` branch and the latest release only.

| Version | Supported |
|---------|-----------|
| 0.1.x   | ✅        |
| < 0.1   | ❌        |

## Reporting a vulnerability

**Please do not open a public GitHub issue for security vulnerabilities.**

Report privately via GitHub's [private vulnerability reporting](https://github.com/Denis-hamon/conclave/security/advisories/new) (preferred) or email the maintainer directly.

Include:

- A description of the issue and its potential impact
- Steps to reproduce (minimal repro if possible)
- The Conclave version and Python version
- Any suggested mitigation

You can expect an acknowledgement within 72 hours and a status update within 7 days.

## Scope

Conclave handles `ANTHROPIC_API_KEY` via the standard environment variable and writes a Decision Trail containing agent inputs and outputs to the local filesystem. Common areas of concern:

- API key exposure through logs, error messages, or Decision Trail files
- Prompt injection via agent outputs that are re-fed to other agents
- Arbitrary YAML execution (we use `yaml.safe_load` exclusively — report any `yaml.load` regression)
- Path traversal in `--trail-dir`, `--org`, or observatory paths
- Denial of service via unbounded deliberation loops (bounded today by `--max-turns`)

## Out of scope

- Issues in `anthropic`, `httpx`, `pyyaml`, or other upstream dependencies — please report to those projects directly. We track these via Dependabot.
- Attacks that require the attacker to have write access to `conclave.yml`, `.conclave/`, or the local filesystem.
