"""
conclave/cli.py

$ conclave run "Launch checkout API" --org conclave.yml
$ conclave observe
$ conclave simulate TechLead write_ticket
$ conclave certify  TechLead write_ticket
$ conclave status

Or from Claude Code: /conclave
"""

import os
import time
from pathlib import Path

import anthropic
import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


def _client() -> anthropic.Anthropic:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise click.ClickException("ANTHROPIC_API_KEY not set.")
    return anthropic.Anthropic(api_key=key)


@click.group()
def cli():
    """◆ Conclave — the organizational layer for enterprise multi-agent systems."""
    pass


# ─── RUN ──────────────────────────────────────────────────────────────────────


@cli.command()
@click.argument("goal")
@click.option("--org", default="conclave.yml", show_default=True)
@click.option("--deliberation", default=None)
@click.option("--max-turns", default=20, show_default=True)
@click.option("--trail-dir", default=".conclave", show_default=True)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Simulate deliberation with no API calls.",
)
def run(goal, org, deliberation, max_turns, trail_dir, dry_run):
    """Run a goal through the org and produce a Decision Trail."""
    from .bus import ConclaveBus
    from .org import load_org

    if dry_run:
        from .dry_run import DryRunClient

        client = DryRunClient()
        console.print("[bold yellow]⚠ [DRY RUN — no API calls made][/bold yellow]")
    else:
        client = _client()
    agents, org_name, default_delib, entry_role = load_org(org, client)
    if dry_run:
        # Force native executor so DeepAgents is bypassed in simulation mode.
        for a in agents.values():
            a.executor = "native"
    prefix = "dry_run_trail" if dry_run else "trail"
    trail_path = Path(trail_dir) / f"{prefix}_{time.strftime('%Y%m%d_%H%M%S')}.jsonl"

    ConclaveBus(
        agents=agents,
        deliberation=deliberation or default_delib,
        trail_path=trail_path,
        max_turns=max_turns,
    ).run(goal=goal, entry_agent=entry_role)


# ─── INIT ─────────────────────────────────────────────────────────────────────


@cli.command()
@click.option(
    "--template",
    default="product-squad",
    type=click.Choice(
        [
            "startup-5",
            "product-squad",
            "growth-squad",
            "creative-agency",
            "claude-code-squad",
        ]
    ),
)
def init(template):
    """Initialize a conclave.yml from a template."""
    templates = {
        "product-squad": _product_squad(),
        "startup-5": _startup_5(),
        "growth-squad": _growth_squad(),
        "creative-agency": _creative_agency(),
        "claude-code-squad": _claude_code_squad(),
    }
    out = Path("conclave.yml")
    if out.exists():
        raise click.ClickException("conclave.yml already exists.")
    out.write_text(templates[template])
    console.print(f"[green]✓[/green] Created conclave.yml — template: [bold]{template}[/bold]")
    console.print('  Next: [bold]conclave run "your goal"[/bold]')


# ─── OBSERVE ──────────────────────────────────────────────────────────────────


@cli.command()
@click.option("--org", default="conclave.yml", show_default=True)
def observe(org):
    """Show what the observatory has recorded."""
    from .certification import Observatory
    from .org import load_org

    client = _client()
    _, org_name, _, _ = load_org(org, client)
    obs = Observatory(org_name)
    stats = obs.stats()

    console.print()
    console.print(
        Panel(
            f"[bold]Actions recorded:[/bold]  {stats['total_actions']}\n"
            f"[bold]Prod cost logged:[/bold]  ${stats['total_cost_usd']:.4f}",
            title="[bold cyan]◆ Conclave · Observatory[/bold cyan]",
            border_style="cyan",
        )
    )

    if stats["task_types"]:
        t = Table(show_header=True, header_style="bold")
        t.add_column("Role")
        t.add_column("Task types observed")
        for role, tasks in stats["task_types"].items():
            t.add_row(role, ", ".join(tasks))
        console.print(t)
        console.print("\n[dim]→ conclave simulate <role> <task>[/dim]")
    else:
        console.print("[yellow]No actions yet. Run conclave run first.[/yellow]")


# ─── SIMULATE ─────────────────────────────────────────────────────────────────


@cli.command()
@click.argument("role")
@click.argument("task_type")
@click.option("--org", default="conclave.yml", show_default=True)
@click.option("--runs", default=50, show_default=True)
@click.option("--skillset-version", default="1.0")
def simulate(role, task_type, org, runs, skillset_version):
    """Replay observed actions with Haiku + skillset and score quality."""
    from .certification import Observatory, Simulator, Skillset, SkillsetBuilder
    from .org import load_org

    client = _client()
    _, org_name, _, _ = load_org(org, client)
    obs = Observatory(org_name)
    actions = obs.load_for_task(role, task_type, limit=runs)

    if not actions:
        console.print(f"[red]No actions for {role}/{task_type}. Run conclave run first.[/red]")
        return

    console.print(f"\n[cyan]◆ Building skillset {role} · {task_type}...[/cyan]")
    skillset = Skillset.load(role, task_type, version=skillset_version)
    if not skillset:
        skillset = SkillsetBuilder(client).build(role, task_type, actions, version=skillset_version)
        skillset.save()
        console.print(f"  [green]✓[/green] Skillset v{skillset_version} distilled and saved")

    console.print(f"[cyan]◆ Simulating {min(len(actions), runs)} actions with Haiku...[/cyan]\n")
    report = Simulator(client).run(role, task_type, skillset, actions, max_runs=runs)

    color = "green" if report.pass_rate >= 0.85 else "yellow" if report.pass_rate >= 0.70 else "red"
    console.print(
        Panel(
            f"[bold]Pass rate:[/bold]     [{color}]{report.pass_rate:.0%}[/{color}]  ({report.passed_runs}/{report.total_runs})\n"
            f"[bold]Avg quality:[/bold]  {report.avg_overall:.2f}\n"
            f"  structural    {report.avg_structural:.2f}\n"
            f"  completeness  {report.avg_completeness:.2f}\n"
            f"  coherence     {report.avg_coherence:.2f}\n\n"
            f"[bold]Cost saving:[/bold]  [green]{report.cost_meter.savings_pct:.0f}%[/green] vs all-Sonnet",
            title=f"[bold cyan]◆ Simulation · {role} / {task_type}[/bold cyan]",
            border_style="cyan",
        )
    )

    if report.pass_rate >= 0.70:
        console.print(f"\n[dim]→ conclave certify {role} {task_type}[/dim]")
    else:
        console.print("\n[yellow]Pass rate too low. Refine the skillset and re-simulate.[/yellow]")


# ─── CERTIFY ──────────────────────────────────────────────────────────────────


@cli.command()
@click.argument("role")
@click.argument("task_type")
@click.option("--skillset-version", default="1.0")
def certify(role, task_type, skillset_version):
    """Certify a task for Haiku routing and update the routing policy."""
    from .certification import (
        Certifier,
        CertStatus,
        Observatory,
        RoutingPolicy,
        Simulator,
        Skillset,
    )

    client = _client()
    obs = Observatory("default")
    actions = obs.load_for_task(role, task_type)

    if not actions:
        console.print("[red]No actions. Run conclave run first.[/red]")
        return

    skillset = Skillset.load(role, task_type, version=skillset_version)
    if not skillset:
        console.print("[red]No skillset. Run conclave simulate first.[/red]")
        return

    report = Simulator(client).run(role, task_type, skillset, actions)
    cert = Certifier().certify(report)
    RoutingPolicy().rebuild()

    icons = {
        CertStatus.CERTIFIED: "[green]✓ CERTIFIED[/green]",
        CertStatus.CONDITIONAL: "[yellow]~ CONDITIONAL[/yellow]",
        CertStatus.REJECTED: "[red]✗ REJECTED[/red]",
    }
    console.print(
        Panel(
            f"[bold]Status:[/bold]    {icons[cert.status]}\n"
            f"[bold]Pass rate:[/bold] {cert.pass_rate:.0%}  ({cert.sample_size} runs)\n"
            f"[bold]Saving:[/bold]    [green]{cert.cost_saving_pct:.0f}%[/green]\n"
            f"[bold]Expires:[/bold]   {cert.expires_at}"
            + (f"\n\n[dim]{cert.notes}[/dim]" if cert.notes else ""),
            title=f"[bold cyan]◆ Certificate · {role} / {task_type}[/bold cyan]",
            border_style="cyan",
        )
    )

    if cert.status != CertStatus.REJECTED:
        console.print("\n[dim]Routing policy updated → conclave status[/dim]")


# ─── STATUS ───────────────────────────────────────────────────────────────────


@cli.command()
def status():
    """Show routing policy, certifications, and cost savings."""
    from .certification import CertStatus, RoutingPolicy

    rows = RoutingPolicy().status_table()
    if not rows:
        console.print("[yellow]No certifications yet. Run simulate + certify.[/yellow]")
        return

    t = Table(show_header=True, header_style="bold cyan", border_style="dim")
    t.add_column("Role", style="bold")
    t.add_column("Task")
    t.add_column("Status")
    t.add_column("Saving", justify="right")
    t.add_column("Expires")

    certified = 0
    for row in rows:
        st = row["status"]
        if st == CertStatus.CERTIFIED.value:
            icon = "[green]✓ CERTIFIED[/green]"
            certified += 1
        elif st == CertStatus.CONDITIONAL.value:
            icon = "[yellow]~ CONDITIONAL[/yellow]"
        else:
            icon = "[red]✗ REJECTED[/red]"

        saving = (
            f"[green]{row['cost_saving_pct']:.0f}%[/green]"
            if st != CertStatus.REJECTED.value
            else "—"
        )
        t.add_row(row["role"], row["task_type"], icon, saving, row.get("expires_at", "—"))

    share = certified / len(rows) * 100 if rows else 0
    console.print()
    console.print(t)
    console.print(
        f"\n  Certified workload share : [bold green]{share:.0f}%[/bold green]  ({certified}/{len(rows)} task types)"
    )
    console.print()


# ─── TEMPLATES ────────────────────────────────────────────────────────────────


def _product_squad():
    return """org:
  name: "Product Squad"
  deliberation: hierarchy

  agents:
    - role: CPO
      persona: |
        Strategic and data-driven. Defines scope, validates business value.
        Always asks "why now?" Never skips the why.
      tools: [notion, slack]
      force_model: claude-sonnet-4-6

    - role: TechLead
      persona: |
        Pragmatic. Tight specs, challenges assumptions, flags blockers early.
        Always offers two options, never one.
      reports_to: CPO
      tools: [github, linear]
      executor: deepagents

    - role: QA_Engineer
      persona: |
        Defensive thinker. Adversarial by nature.
        Never approves without a test plan. Escalates immediately.
      reports_to: TechLead
      tools: [github, browserbase]
"""


def _startup_5():
    return """org:
  name: "Startup"
  deliberation: consensus

  agents:
    - role: CEO
      persona: Visionary but pragmatic. Sets direction, removes blockers.
      tools: [notion, slack]

    - role: CPO
      persona: User-obsessed. Ruthless about scope.
      reports_to: CEO
      tools: [notion, figma]

    - role: CTO
      persona: Systems thinker. Prefers boring technology. Flags debt early.
      reports_to: CEO
      tools: [github, linear]
      executor: deepagents

    - role: Designer
      persona: Craft-obsessed. Always asks about the user journey.
      reports_to: CPO
      tools: [figma, notion]

    - role: QA
      persona: Last line of defense. Thinks adversarially.
      reports_to: CTO
      tools: [github, browserbase]
"""


def _growth_squad():
    return """org:
  name: "Growth Squad"
  deliberation: consensus

  agents:
    - role: CMO
      persona: Narrative-driven. Connects business goals to audience insight.
      tools: [notion, slack]

    - role: GrowthLead
      persona: Experiment-minded. Builds funnels, proposes A/B tests.
      reports_to: CMO
      tools: [amplitude, notion]

    - role: ContentStrategist
      persona: Audience-first. Writes for clarity, edits ruthlessly.
      reports_to: CMO
      tools: [notion, slack]

    - role: DataAnalyst
      persona: Numbers before narratives. Validates hypotheses.
      reports_to: GrowthLead
      tools: [amplitude, notion]
"""


def _creative_agency():
    return """org:
  name: "Creative Agency"
  deliberation: hierarchy

  agents:
    - role: CreativeDirector
      persona: Taste-maker. Protects the work from mediocrity.
      tools: [notion, figma]

    - role: Copywriter
      persona: Words first. Never uses jargon. Always drafts three options.
      reports_to: CreativeDirector
      tools: [notion]

    - role: ArtDirector
      persona: Visual systems thinker. Knows when to break the grid.
      reports_to: CreativeDirector
      tools: [figma, notion]

    - role: PM
      persona: Client translator. Protects scope. Focused on deliverables.
      reports_to: CreativeDirector
      tools: [notion, slack]
"""


def _claude_code_squad():
    return """org:
  name: "Claude Code Squad"
  deliberation: hierarchy

  agents:
    - role: Planner
      persona: |
        Breaks ambiguous goals into atomic, verifiable tasks before any code is written.
        Always writes the task list as bullets, never as prose. Challenges scope creep
        on the spot. Refuses to delegate anything vaguer than "change X in file Y so
        that Z holds." Owns the definition of done.
      tools: [github, linear]
      force_model: claude-sonnet-4-6

    - role: Implementer
      persona: |
        Writes the smallest possible change that passes the tests. Reads the file
        before editing it. Never introduces a new dependency without flagging it.
        Prefers explicit over clever. Hands off to Reviewer the moment the
        implementation compiles and its own smoke test passes.
      reports_to: Planner
      tools: [github]
      executor: deepagents

    - role: Reviewer
      persona: |
        Reads the diff line by line. Flags silent failure modes, missing edge cases,
        and anything that looks like a workaround rather than a fix. Will not approve
        until the why of each change is justified in the commit message. Treats
        "it works on my machine" as an escalation.
      reports_to: Planner
      tools: [github]

    - role: Tester
      persona: |
        Writes the tests the Implementer forgot. Thinks adversarially — what input
        would break this? Blocks merge on any regression. Prefers one targeted test
        over three broad ones. Always reports the coverage delta.
      reports_to: Reviewer
      tools: [github, browserbase]
"""


# ─── BENCHMARK ────────────────────────────────────────────────────────────────


@cli.command()
@click.option("--dry-run", is_flag=True, default=False, help="Run with zero API calls.")
@click.option("--output", default="benchmarks/results.json", show_default=True)
def benchmark(dry_run, output):
    """Benchmark Conclave routing vs all-Haiku and all-Sonnet over 20 tasks."""
    from .benchmark import ConclaveBenchmark
    from .benchmark_tasks import BENCHMARK_CATEGORIES

    if dry_run:
        from .dry_run import DryRunClient

        client = DryRunClient()
        console.print("[yellow]⚠ [DRY RUN — no API calls made][/yellow]")
    else:
        client = _client()

    bench = ConclaveBenchmark(client=client, dry_run=dry_run)
    report = bench.run()
    bench.save(Path(output), report)

    s = report["summary"]
    t = Table(show_header=True, header_style="bold cyan")
    t.add_column("Category")
    t.add_column("Haiku", justify="right")
    t.add_column("Sonnet", justify="right")
    t.add_column("Conclave", justify="right")
    t.add_column("Quality", justify="right")
    for cat in BENCHMARK_CATEGORIES:
        row = report["by_category"][cat]
        q = (row["quality"] / row["n"] * 100) if row["n"] else 0.0
        t.add_row(
            cat,
            f"${row['haiku_only']:.3f}",
            f"${row['sonnet_only']:.3f}",
            f"${row['conclave']:.3f}",
            f"{q:.0f}%",
        )
    t.add_row(
        "[bold]TOTAL[/bold]",
        f"[bold]${s['haiku_only_cost']:.3f}[/bold]",
        f"[bold]${s['sonnet_only_cost']:.3f}[/bold]",
        f"[bold]${s['conclave_cost']:.3f}[/bold]",
        f"[bold]{s['conclave_quality_vs_sonnet_pct']:.0f}%[/bold]",
    )

    console.print()
    console.print(t)
    console.print()
    console.print(
        f"[green]Conclave saves {s['conclave_saving_vs_sonnet_pct']:.1f}% vs all-Sonnet "
        f"at {s['conclave_quality_vs_sonnet_pct']:.1f}% quality parity.[/green]"
    )
    console.print(f"[dim]Results written to {output}[/dim]")


# ─── DASHBOARD ────────────────────────────────────────────────────────────────


@cli.command()
@click.option("--org", default="conclave.yml", show_default=True)
@click.option("--trail-dir", default=".conclave", show_default=True)
@click.option("--port", default=7777, show_default=True)
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--no-open", is_flag=True, default=False, help="Do not auto-open the browser.")
def dashboard(org, trail_dir, port, host, no_open):
    """Launch the Conclave dashboard at http://localhost:{port}"""
    import webbrowser

    try:
        import uvicorn
    except ImportError:
        raise click.ClickException(
            "Dashboard requires extras. Install with: pip install 'conclave-agents[dashboard]'"
        )

    from .dashboard.server import create_app

    org_path = Path(org)
    trail_path = Path(trail_dir)
    app = create_app(org_path=org_path, trail_dir=trail_path)

    url = f"http://{host}:{port}"
    console.print(f"[bold cyan]◆ Conclave Dashboard → {url}[/bold cyan]")
    if not no_open:
        try:
            webbrowser.open(url)
        except Exception:
            pass

    uvicorn.run(app, host=host, port=port, log_level="warning")


# ─── TRAIL ────────────────────────────────────────────────────────────────────


@cli.group()
def trail():
    """Inspect Decision Trail files."""
    pass


@trail.command("view")
@click.argument("trail_file", type=click.Path(exists=True, dir_okay=False), required=False)
@click.option("--latest", is_flag=True, default=False, help="Pick the newest trail in --trail-dir.")
@click.option("--trail-dir", default=".conclave", show_default=True)
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["mermaid", "timeline"]),
    default="mermaid",
    show_default=True,
    help="Mermaid sequenceDiagram (default) or ASCII timeline.",
)
@click.option("--title", default=None, help="Optional title rendered inside the diagram.")
def trail_view(trail_file, latest, trail_dir, fmt, title):
    """Render a trail as a Mermaid sequenceDiagram or ASCII timeline."""
    from .trail_view import latest_trail, load_trail, to_mermaid, to_timeline

    if trail_file:
        path = Path(trail_file)
    elif latest:
        picked = latest_trail(Path(trail_dir))
        if not picked:
            raise click.ClickException(f"No trail file found in {trail_dir}.")
        path = picked
    else:
        raise click.UsageError("Pass a trail file path or --latest.")

    entries = load_trail(path)
    if fmt == "timeline":
        click.echo(to_timeline(entries))
    else:
        click.echo(to_mermaid(entries, title=title))


# ─── REPLAY ───────────────────────────────────────────────────────────────────


@cli.command()
@click.argument("trail_file", type=click.Path(exists=True, dir_okay=False), required=False)
@click.option("--latest", is_flag=True, default=False, help="Pick the newest trail in --trail-dir.")
@click.option("--trail-dir", default=".conclave", show_default=True)
@click.option("--org", default="conclave.yml", show_default=True)
@click.option(
    "--deliberation",
    default=None,
    type=click.Choice(["hierarchy", "consensus", "first-valid"]),
    help="Override the deliberation strategy from the original run.",
)
def replay(trail_file, latest, trail_dir, org, deliberation):
    """Re-run a past Decision Trail, optionally with a different deliberation."""
    from .bus import ConclaveBus
    from .dry_run import DryRunClient
    from .org import load_org
    from .replay import extract_meta, infer_goal_from_trail
    from .trail_view import latest_trail

    if trail_file:
        path = Path(trail_file)
    elif latest:
        picked = latest_trail(Path(trail_dir))
        if not picked:
            raise click.ClickException(f"No trail file found in {trail_dir}.")
        path = picked
    else:
        raise click.UsageError("Pass a trail file path or --latest.")

    meta = extract_meta(path)
    if meta:
        goal = meta.goal
        original_delib = meta.deliberation
        entry_from_meta = meta.entry_agent
    else:
        goal = infer_goal_from_trail(path) or ""
        original_delib = "unknown"
        entry_from_meta = ""

    if not goal:
        raise click.ClickException(
            f"Could not extract a goal from {path}. "
            "The trail predates the meta entry and has no user-seeded message."
        )

    # Use dry-run client — replays are expected to be safe to re-execute without
    # burning API credit. Users who want a real replay can set ANTHROPIC_API_KEY
    # and edit the client construction; the current signature matches `run`.
    client = DryRunClient()
    agents, org_name, default_delib, entry_role = load_org(org, client)

    # Force native executor so DeepAgents is skipped in replay.
    for a in agents.values():
        a.executor = "native"

    final_delib = deliberation or default_delib
    replay_entry = entry_role or entry_from_meta

    out_path = (
        Path(trail_dir) / f"replay_of_{path.stem}_{time.strftime('%Y%m%d_%H%M%S')}.jsonl"
    )

    console.print(
        Panel(
            f"[bold]Replaying[/bold]  {path.name}\n"
            f"[dim]Org:[/dim] {org_name}\n"
            f"[dim]Goal:[/dim] {goal}\n"
            f"[dim]Original deliberation:[/dim] {original_delib}\n"
            f"[dim]Replay deliberation:[/dim] {final_delib}\n"
            f"[dim]New trail:[/dim] {out_path}",
            title="[bold cyan]◆ Conclave · Replay[/bold cyan]",
            border_style="cyan",
        )
    )

    ConclaveBus(
        agents=agents,
        deliberation=final_delib,
        trail_path=out_path,
        max_turns=(meta.max_turns if meta else 20),
    ).run(goal=goal, entry_agent=replay_entry)


if __name__ == "__main__":
    cli()
