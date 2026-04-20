"""
examples/demo.py

Zero-config demo of a Conclave Product Squad deliberating on a checkout API.
Uses DryRunClient — no API key required.

Run:
    python examples/demo.py
"""
from __future__ import annotations
import json
import random
import time
from pathlib import Path
from types import SimpleNamespace

from conclave.dry_run import DryRunClient
from conclave.org import load_org
from conclave.bus import ConclaveBus
from rich.console import Console
from rich.panel import Panel

console = Console()


class DemoClient(DryRunClient):
    """Variant of DryRunClient that produces a realistic mix of routing decisions,
    so the demo shows meaningful cost savings versus an all-Sonnet baseline."""

    _ROUTE_ROTATION = [
        {"novelty": 0.2, "complexity": 0.2, "is_repetitive": True,  "needs_filesystem": False,
         "rationale": "repetitive — Haiku loop"},
        {"novelty": 0.8, "complexity": 0.7, "is_repetitive": False, "needs_filesystem": False,
         "rationale": "novel and complex — Sonnet"},
        {"novelty": 0.3, "complexity": 0.3, "is_repetitive": True,  "needs_filesystem": False,
         "rationale": "templated task — Haiku loop"},
        {"novelty": 0.7, "complexity": 0.8, "is_repetitive": False, "needs_filesystem": False,
         "rationale": "deliberation required — Sonnet"},
    ]

    def __init__(self):
        super().__init__()
        self._classifier_idx = 0
        self._pacing = 0.35

    def _synthesize(self, *, system: str, messages: list, model: str) -> str:
        sys_lower = (system or "").lower()
        if "classifier" in sys_lower or "routing" in sys_lower:
            payload = self._ROUTE_ROTATION[self._classifier_idx % len(self._ROUTE_ROTATION)]
            self._classifier_idx += 1
            return json.dumps(payload)
        # Pace agent responses only
        time.sleep(self._pacing)
        return super()._synthesize(system=system, messages=messages, model=model)


def main():
    random.seed(42)

    console.print()
    console.print(Panel(
        "[bold cyan]Conclave · Live dry-run demo[/bold cyan]\n\n"
        "3 agents (CPO → TechLead → QA_Engineer) deliberate on a real product goal.\n"
        "Routing decisions alternate between Haiku (repetitive) and Sonnet (strategic).\n\n"
        "[dim]No API calls. No API key. Zero config.[/dim]",
        border_style="cyan",
    ))
    time.sleep(0.5)

    org_yaml = Path(__file__).parent / "product_squad.yml"
    client = DemoClient()

    agents, org_name, delib, entry = load_org(org_yaml, client)
    for a in agents.values():
        a.executor = "native"  # bypass DeepAgents in demo mode

    trail_dir = Path(".conclave")
    trail_dir.mkdir(exist_ok=True)
    trail_path = trail_dir / f"demo_trail_{time.strftime('%Y%m%d_%H%M%S')}.jsonl"

    bus = ConclaveBus(
        agents=agents,
        deliberation=delib,
        trail_path=trail_path,
        max_turns=8,
    )

    goal = "Design and spec a new checkout API with idempotency support"
    bus.run(goal=goal, entry_agent=entry)

    # Final recap
    console.print()
    console.print(Panel(
        "[bold green]◆ Demo complete[/bold green]\n\n"
        f"Trail saved to: [cyan]{trail_path}[/cyan]\n"
        "Run [bold]conclave run \"your goal\" --dry-run[/bold] to try it yourself.\n"
        "Add an [bold]ANTHROPIC_API_KEY[/bold] env var to run for real.",
        border_style="green",
    ))


if __name__ == "__main__":
    main()
