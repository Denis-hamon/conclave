"""
conclave/dashboard/server.py

FastAPI backend for the Conclave dashboard.

Endpoints:
  GET  /                  serve index.html
  GET  /api/org           current org structure (hierarchy tree)
  GET  /api/trail         last N entries from the most recent Decision Trail
  GET  /api/metrics       top-line metric cards (agents, deliberations, cost, savings)
  GET  /api/charts        chart data bundle (14d activity, handoffs, cost-by-role, routing)
  GET  /api/activity      recent activity feed (live) + recent tasks feed
  GET  /api/status        certification routing policy + cost summary
  GET  /api/events        SSE stream of new trail entries
"""

from __future__ import annotations

import asyncio
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

_STATIC_DIR = Path(__file__).parent


def _latest_trail(trail_dir: Path) -> Path | None:
    if not trail_dir.exists():
        return None
    candidates = sorted(
        trail_dir.glob("*trail*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True
    )
    return candidates[0] if candidates else None


def _all_trails(trail_dir: Path) -> list[Path]:
    if not trail_dir.exists():
        return []
    return sorted(trail_dir.glob("*trail*.jsonl"), key=lambda p: p.stat().st_mtime)


def _load_trail_entries(trail_path: Path | None, limit: int = 200) -> list[dict]:
    if not trail_path or not trail_path.exists():
        return []
    lines = trail_path.read_text().splitlines()
    entries: list[dict] = []
    for line in lines[-limit:]:
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def _load_all_entries(trail_dir: Path, since: datetime | None = None) -> list[dict]:
    """Walk every trail file, optionally filtered by timestamp."""
    entries: list[dict] = []
    for trail in _all_trails(trail_dir):
        for line in trail.read_text().splitlines():
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if since:
                ts = entry.get("ts")
                if ts:
                    try:
                        entry_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                        if entry_dt < since:
                            continue
                    except ValueError:
                        pass
            entries.append(entry)
    return entries


def _org_payload(org_path: Path) -> dict[str, Any]:
    if not org_path.exists():
        return {"name": "unknown", "agents": []}
    cfg = yaml.safe_load(org_path.read_text())
    org = cfg.get("org", {})
    agents = []
    for a in org.get("agents", []):
        agents.append(
            {
                "role": a["role"],
                "reports_to": a.get("reports_to"),
                "tools": a.get("tools", []),
            }
        )
    return {"name": org.get("name", "Conclave Org"), "agents": agents}


def _parse_policy(policy_path: Path) -> tuple[list[dict], int]:
    if not policy_path.exists():
        return [], 0
    try:
        data = json.loads(policy_path.read_text())
    except (json.JSONDecodeError, OSError):
        return [], 0
    certs = data.get("certifications", [])
    certified = sum(1 for c in certs if c.get("status") == "certified")
    return certs, certified


def _metrics_payload(org_path: Path, trail_dir: Path) -> dict[str, Any]:
    """Top-line metric cards."""
    org = _org_payload(org_path)
    agents_count = len(org["agents"])

    since_today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    today = _load_all_entries(trail_dir, since=since_today)
    # A deliberation ~= a single trail file; approximate by unique goal/run keys.
    trails_today = len({t.name for t in _all_trails(trail_dir) if t.stat().st_mtime >= since_today.timestamp()})

    cost_today = 0.0
    saved_today = 0.0
    for e in today:
        cost_today += float(e.get("cost_usd") or 0)
        saved_today += float(e.get("tokens_saved_usd") or 0)

    baseline = cost_today + saved_today
    savings_pct = round((saved_today / baseline) * 100, 1) if baseline > 0 else 0.0

    _, certified = _parse_policy(Path(".conclave/routing_policy.json"))

    return {
        "agents_total": agents_count,
        "deliberations_today": trails_today,
        "cost_today_usd": round(cost_today, 4),
        "baseline_today_usd": round(baseline, 4),
        "savings_pct": savings_pct,
        "certified_task_types": certified,
    }


def _charts_payload(trail_dir: Path) -> dict[str, Any]:
    """Data for the 4 ChartCards."""
    since_14d = datetime.now(UTC) - timedelta(days=14)
    entries = _load_all_entries(trail_dir, since=since_14d)

    # 1. Daily activity counts (14 buckets)
    buckets: dict[str, int] = defaultdict(int)
    for e in entries:
        ts = e.get("ts", "")
        try:
            d = datetime.fromisoformat(ts.replace("Z", "+00:00")).date().isoformat()
            buckets[d] += 1
        except ValueError:
            continue
    today = datetime.now(UTC).date()
    activity_14d = []
    for i in range(14):
        day = (today - timedelta(days=13 - i)).isoformat()
        activity_14d.append({"date": day, "count": buckets.get(day, 0)})

    # 2. Handoff breakdown by msg type
    handoff_counter: Counter[str] = Counter(e.get("type", "message") for e in entries)
    handoffs = [{"type": t, "count": c} for t, c in handoff_counter.most_common()]

    # 3. Cost by role
    cost_by_role: dict[str, float] = defaultdict(float)
    for e in entries:
        role = e.get("from") or e.get("role") or "unknown"
        cost_by_role[role] += float(e.get("cost_usd") or 0)
    cost_roles = sorted(
        [{"role": r, "cost_usd": round(c, 4)} for r, c in cost_by_role.items()],
        key=lambda x: x["cost_usd"],
        reverse=True,
    )

    # 4. Routing split (haiku/sonnet/opus)
    tier_counter: Counter[str] = Counter()
    for e in entries:
        model = (e.get("model_used") or "").lower()
        if "haiku" in model:
            tier_counter["haiku"] += 1
        elif "sonnet" in model:
            tier_counter["sonnet"] += 1
        elif "opus" in model:
            tier_counter["opus"] += 1
    routing = [{"tier": t, "count": c} for t, c in tier_counter.most_common()]

    return {
        "activity_14d": activity_14d,
        "handoffs": handoffs,
        "cost_by_role": cost_roles,
        "routing_split": routing,
    }


def _activity_payload(trail_dir: Path, limit: int = 12) -> dict[str, Any]:
    """Dual feed: recent activity + recent task-like outputs."""
    entries = _load_all_entries(trail_dir)
    entries.reverse()

    activity = entries[:limit]
    tasks = [e for e in entries if e.get("type") == "output"][:limit]

    return {"activity": activity, "tasks": tasks}


def create_app(org_path: Path, trail_dir: Path) -> FastAPI:
    app = FastAPI(title="Conclave Dashboard")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(_STATIC_DIR / "index.html")

    @app.get("/api/org")
    def api_org() -> JSONResponse:
        return JSONResponse(_org_payload(org_path))

    @app.get("/api/trail")
    def api_trail(limit: int = 200) -> JSONResponse:
        trail = _latest_trail(trail_dir)
        entries = _load_trail_entries(trail, limit=limit)
        return JSONResponse(
            {"trail": entries, "trail_file": str(trail) if trail else None}
        )

    @app.get("/api/metrics")
    def api_metrics() -> JSONResponse:
        return JSONResponse(_metrics_payload(org_path, trail_dir))

    @app.get("/api/charts")
    def api_charts() -> JSONResponse:
        return JSONResponse(_charts_payload(trail_dir))

    @app.get("/api/activity")
    def api_activity(limit: int = 12) -> JSONResponse:
        return JSONResponse(_activity_payload(trail_dir, limit=limit))

    @app.get("/api/status")
    def api_status() -> JSONResponse:
        certs, certified = _parse_policy(Path(".conclave/routing_policy.json"))
        total = len(certs) or 1
        return JSONResponse(
            {
                "certifications": certs,
                "certified_share_pct": round(certified / total * 100, 1),
            }
        )

    @app.get("/api/events")
    async def api_events() -> StreamingResponse:
        async def event_stream() -> Any:
            last_sig: tuple | None = None
            while True:
                trail = _latest_trail(trail_dir)
                if trail:
                    stat = trail.stat()
                    sig = (str(trail), stat.st_mtime, stat.st_size)
                    if sig != last_sig:
                        last_sig = sig
                        entries = _load_trail_entries(trail, limit=1)
                        if entries:
                            yield f"data: {json.dumps(entries[-1])}\n\n"
                await asyncio.sleep(0.5)

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    return app
