"""
conclave/dashboard/server.py

FastAPI backend for the Conclave dashboard.

Endpoints:
  GET  /              serve index.html
  GET  /api/org       current org structure
  GET  /api/trail     last N entries from the most recent Decision Trail
  GET  /api/status    certification routing policy + cost summary
  GET  /api/events    SSE stream of new trail entries
"""
from __future__ import annotations
import asyncio
import json
import time
from pathlib import Path
from typing import Optional

import yaml
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

_STATIC_DIR = Path(__file__).parent


def _latest_trail(trail_dir: Path) -> Optional[Path]:
    if not trail_dir.exists():
        return None
    candidates = sorted(trail_dir.glob("*trail*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


def _load_trail_entries(trail_path: Path, limit: int = 200) -> list[dict]:
    if not trail_path or not trail_path.exists():
        return []
    lines = trail_path.read_text().splitlines()
    entries = []
    for line in lines[-limit:]:
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def _org_payload(org_path: Path) -> dict:
    if not org_path.exists():
        return {"name": "unknown", "agents": []}
    cfg = yaml.safe_load(org_path.read_text())
    org = cfg.get("org", {})
    agents = []
    for a in org.get("agents", []):
        agents.append({
            "role": a["role"],
            "reports_to": a.get("reports_to"),
            "tools": a.get("tools", []),
        })
    return {"name": org.get("name", "Conclave Org"), "agents": agents}


def _status_payload(trail_dir: Path) -> dict:
    """Aggregate cost across the latest trail (best effort — derived from tokens_saved_usd)."""
    from ..cost import COST_TABLE, BASELINE_MODEL
    trail = _latest_trail(trail_dir)
    entries = _load_trail_entries(trail, limit=1000) if trail else []

    total = 0.0
    baseline = 0.0
    for e in entries:
        # Trails don't store raw tokens, so we estimate from tokens_saved_usd if present.
        saved = float(e.get("tokens_saved_usd") or 0)
        baseline += saved  # approximation
        total += 0.0

    # Attempt to read certifications
    certifications = []
    certified = 0
    policy_path = Path(".conclave/routing_policy.json")
    if policy_path.exists():
        try:
            data = json.loads(policy_path.read_text())
            certifications = data.get("certifications", [])
            certified = sum(1 for c in certifications if c.get("status") == "certified")
        except Exception:
            pass

    total_policies = len(certifications) or 1
    certified_share = round(certified / total_policies * 100, 1)

    savings_pct = 0.0
    if baseline > 0:
        savings_pct = round((baseline - total) / baseline * 100, 1)

    return {
        "certifications": certifications,
        "certified_share_pct": certified_share,
        "total_cost_usd": round(total, 4),
        "baseline_cost_usd": round(baseline, 4),
        "savings_pct": savings_pct,
    }


def create_app(org_path: Path, trail_dir: Path) -> FastAPI:
    app = FastAPI(title="Conclave Dashboard")

    @app.get("/")
    def index():
        return FileResponse(_STATIC_DIR / "index.html")

    @app.get("/api/org")
    def api_org():
        return JSONResponse(_org_payload(org_path))

    @app.get("/api/trail")
    def api_trail(limit: int = 200):
        trail = _latest_trail(trail_dir)
        entries = _load_trail_entries(trail, limit=limit)
        return JSONResponse({
            "trail": entries,
            "trail_file": str(trail) if trail else None,
        })

    @app.get("/api/status")
    def api_status():
        return JSONResponse(_status_payload(trail_dir))

    @app.get("/api/events")
    async def api_events():
        async def event_stream():
            last_sig = None
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
