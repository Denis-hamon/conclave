"""
examples/render_demo.py

Render the dry-run demo to a static SVG (terminal screenshot) for the README.

Unlike examples/demo.py, this variant:
  - Uses a recording rich.Console (no pacing delays)
  - Writes output to examples/demo.svg
  - Is meant to be run once when the demo script changes

For a real animated GIF, use examples/demo.tape with `vhs`.
See examples/DEMO_RECORDING.md.
"""
from __future__ import annotations
import json
import time
from pathlib import Path

from rich.console import Console

# Patch the bus console BEFORE importing anything that uses it.
import conclave.bus as _bus_mod
recording = Console(record=True, width=100)
_bus_mod.console = recording

from conclave.dry_run import DryRunClient
from conclave.org import load_org
from conclave.bus import ConclaveBus
from rich.panel import Panel


class DemoClient(DryRunClient):
    _ROTATION = [
        {"novelty": 0.2, "complexity": 0.2, "is_repetitive": True,
         "needs_filesystem": False, "rationale": "repetitive"},
        {"novelty": 0.8, "complexity": 0.7, "is_repetitive": False,
         "needs_filesystem": False, "rationale": "strategic"},
        {"novelty": 0.3, "complexity": 0.3, "is_repetitive": True,
         "needs_filesystem": False, "rationale": "templated"},
        {"novelty": 0.7, "complexity": 0.8, "is_repetitive": False,
         "needs_filesystem": False, "rationale": "deliberation"},
    ]

    def __init__(self):
        super().__init__()
        self._idx = 0

    def _synthesize(self, *, system: str, messages: list, model: str) -> str:
        sys_lower = (system or "").lower()
        if "classifier" in sys_lower or "routing" in sys_lower:
            payload = self._ROTATION[self._idx % len(self._ROTATION)]
            self._idx += 1
            return json.dumps(payload)
        return super()._synthesize(system=system, messages=messages, model=model)


def main():
    recording.print()
    recording.print(Panel(
        "[bold cyan]Conclave · Dry-run demo[/bold cyan]\n\n"
        "3 agents (CPO → TechLead → QA_Engineer) deliberate on a real goal.\n"
        "Routing alternates Haiku (repetitive) / Sonnet (strategic).\n\n"
        "[dim]Zero API calls · zero config[/dim]",
        border_style="cyan",
    ))

    org_yaml = Path(__file__).parent / "product_squad.yml"
    client = DemoClient()
    agents, org_name, delib, entry = load_org(org_yaml, client)
    for a in agents.values():
        a.executor = "native"

    trail_dir = Path(".conclave")
    trail_dir.mkdir(exist_ok=True)
    trail_path = trail_dir / f"svg_trail_{time.strftime('%Y%m%d_%H%M%S')}.jsonl"

    bus = ConclaveBus(
        agents=agents, deliberation=delib,
        trail_path=trail_path, max_turns=8,
    )
    bus.run(goal="Design and spec a new checkout API with idempotency support",
            entry_agent=entry)

    out = Path(__file__).parent / "demo.svg"
    recording.save_svg(str(out), title="conclave run --dry-run")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
