"""
conclave/bus.py
The inter-agent message bus — the coordination layer that Managed Agents doesn't ship yet.
Routes messages between agents, applies deliberation strategy, writes the Decision Trail.
"""

from __future__ import annotations

import json
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from .agent import ConclaveAgent, Message

console = Console()

ROLE_COLORS = ["cyan", "magenta", "yellow", "green", "blue", "red", "white"]


class ConclaveBus:
    """
    Routes messages between agents.
    Writes every handoff to the Decision Trail.
    Applies the deliberation strategy to decide when to stop.
    """

    def __init__(
        self,
        agents: dict[str, ConclaveAgent],
        deliberation: str,
        trail_path: Path,
        max_turns: int = 20,
    ):
        self.agents = agents
        self.deliberation = deliberation
        self.trail_path: Path = trail_path
        self.max_turns = max_turns
        self.trail: list[dict] = []
        self.outputs: dict[str, str] = {}
        self._role_colors = {
            role: ROLE_COLORS[i % len(ROLE_COLORS)] for i, role in enumerate(agents.keys())
        }
        self.trail_path.parent.mkdir(parents=True, exist_ok=True)

    def run(self, goal: str, entry_agent: str) -> dict[str, str]:
        """
        Inject the goal into the entry agent and let the org deliberate.
        Returns collected outputs.
        """
        console.print()
        console.print(
            Panel(
                f"[bold white]{goal}[/bold white]",
                title="[bold cyan]◆ Conclave · Deliberation started[/bold cyan]",
                border_style="cyan",
            )
        )
        console.print()

        # Seed message from "user" to the entry agent
        seed = Message(
            sender="user",
            recipient=entry_agent,
            content=goal,
            msg_type="delegation",
        )

        current_msg = seed
        turns = 0

        while turns < self.max_turns:
            turns += 1
            target_role = current_msg.recipient

            if target_role not in self.agents:
                console.print(f"[red]  ✗ Unknown agent: {target_role}. Stopping.[/red]")
                break

            agent = self.agents[target_role]
            self._print_message(current_msg)

            response = agent.receive(current_msg)
            self._log(response)

            if response.msg_type == "output":
                self.outputs[target_role] = response.content
                console.print(f"  [bold green]✓ Output from {target_role}[/bold green]")
                if self._deliberation_complete():
                    break
                # Continue routing if there's a recipient
                if response.recipient == "bus":
                    break

            current_msg = response

            if self.deliberation == "first-valid" and self.outputs:
                break

        self._write_trail()
        self._print_summary()
        return self.outputs

    def _deliberation_complete(self) -> bool:
        if self.deliberation == "first-valid":
            return bool(self.outputs)
        if self.deliberation == "consensus":
            return len(self.outputs) == len(self.agents)
        return True  # hierarchy: first output from top of chain

    def _log(self, msg: Message):
        entry = msg.to_dict()
        self.trail.append(entry)

    def _write_trail(self):
        with self.trail_path.open("w") as f:
            for entry in self.trail:
                f.write(json.dumps(entry) + "\n")

    def _print_message(self, msg: Message):
        color = self._role_colors.get(msg.sender, "white")
        if msg.sender == "user":
            color = "bold white"

        arrow = ""
        if msg.recipient and msg.recipient not in ("bus", "user"):
            target_color = self._role_colors.get(msg.recipient, "white")
            arrow = f" [dim]→[/dim] [{target_color}]{msg.recipient}[/{target_color}]"

        label = Text()
        label.append(f"  [{msg.sender}]", style=f"bold {color}")
        label.append(arrow)

        console.print(label)

        preview = msg.content[:120].replace("\n", " ")
        if len(msg.content) > 120:
            preview += "…"
        console.print(f"    [dim]{preview}[/dim]")

        if msg.reasoning:
            console.print(f"    [italic dim]↳ {msg.reasoning}[/italic dim]")

        console.print()

    def _print_summary(self):
        from .cost import CostMeter

        # Merge all agent cost meters
        global_meter = CostMeter()
        for agent in self.agents.values():
            global_meter.merge(agent.cost_meter)

        cost_lines = "\n".join(global_meter.summary_lines())

        console.print(
            Panel(
                f"[green]Decision Trail → {self.trail_path}[/green]\n"
                f"[green]Turns: {len(self.trail)}  ·  Outputs: {len(self.outputs)} artifact(s)[/green]\n\n"
                f"[bold]Token cost breakdown[/bold]\n{cost_lines}",
                title="[bold cyan]◆ Conclave · Deliberation complete[/bold cyan]",
                border_style="cyan",
            )
        )
