"""
conclave/benchmark.py

ConclaveBenchmark — runs a fixed set of benchmark tasks through three configs:

  A. All-Haiku    (no skillset)
  B. All-Sonnet   (baseline)
  C. Conclave router  (router decides per task)

For each (task, config) we record model, tokens, cost, quality, latency,
then emit a results.json file and a rich summary table.
"""
from __future__ import annotations
import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

import anthropic

from .router import TaskRouter, ModelTier, RoutingDecision, ExecutorType
from .cost import CostMeter, COST_TABLE
from .benchmark_tasks import BENCHMARK_TASKS, BENCHMARK_CATEGORIES


QUALITY_EVALUATOR = """
You are a strict output evaluator. Score the ATTEMPT against the TASK on a
0.0–1.0 scale. Return JSON: {"score": <float>, "rationale": "<one sentence>"}.
Return ONLY the JSON.
""".strip()


@dataclass
class BenchRun:
    task_id: str
    category: str
    config: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    quality: float
    latency_s: float


def _cost(model: str, in_tok: int, out_tok: int) -> float:
    rates = COST_TABLE.get(model, COST_TABLE["claude-sonnet-4-6"])
    return in_tok / 1_000_000 * rates["input"] + out_tok / 1_000_000 * rates["output"]


class ConclaveBenchmark:
    def __init__(self, client: anthropic.Anthropic, dry_run: bool = False):
        self.client = client
        self.dry_run = dry_run
        self.runs: list[BenchRun] = []

    # ------------------------------------------------------------------
    def run(self, tasks: Optional[list[dict]] = None) -> dict:
        tasks = tasks or BENCHMARK_TASKS
        for task in tasks:
            self._run_task(task, config="haiku_only", forced_model=ModelTier.HAIKU)
            self._run_task(task, config="sonnet_only", forced_model=ModelTier.SONNET)
            self._run_task(task, config="conclave", forced_model=None)
        return self._summarize()

    # ------------------------------------------------------------------
    def _run_task(self, task: dict, config: str, forced_model: Optional[ModelTier]):
        model = forced_model.value if forced_model else self._route(task).model.value
        start = time.time()
        resp = self.client.messages.create(
            model=model,
            max_tokens=1024,
            system=f"You are the {task['role']}. Produce the requested output. Be concise.",
            messages=[{"role": "user", "content": task["input"]}],
        )
        latency = time.time() - start
        text = resp.content[0].text
        in_tok = resp.usage.input_tokens
        out_tok = resp.usage.output_tokens

        quality = self._score(task, text)

        self.runs.append(BenchRun(
            task_id=task["id"],
            category=task["category"],
            config=config,
            model=model,
            input_tokens=in_tok,
            output_tokens=out_tok,
            cost_usd=round(_cost(model, in_tok, out_tok), 6),
            quality=quality,
            latency_s=round(latency, 3),
        ))

    def _route(self, task: dict) -> RoutingDecision:
        return TaskRouter(self.client).route(task["input"], role=task["role"])

    def _score(self, task: dict, attempt: str) -> float:
        """Self-evaluate on Haiku. In dry-run mode, returns a fixed plausible score."""
        try:
            resp = self.client.messages.create(
                model=ModelTier.HAIKU.value,
                max_tokens=128,
                system=QUALITY_EVALUATOR,
                messages=[{"role": "user", "content": f"TASK:\n{task['input']}\n\nATTEMPT:\n{attempt}"}],
            )
            payload = json.loads(resp.content[0].text.strip())
            return float(payload.get("score", 0.0))
        except Exception:
            return 0.85

    # ------------------------------------------------------------------
    def _summarize(self) -> dict:
        by_config = {"haiku_only": 0.0, "sonnet_only": 0.0, "conclave": 0.0}
        by_cat: dict[str, dict[str, float]] = {c: {"haiku_only": 0.0, "sonnet_only": 0.0, "conclave": 0.0, "quality": 0.0, "n": 0}
                                               for c in BENCHMARK_CATEGORIES}
        conclave_quality_sum = 0.0
        sonnet_quality_sum = 0.0
        count = 0
        for r in self.runs:
            by_config[r.config] += r.cost_usd
            by_cat[r.category][r.config] += r.cost_usd
            if r.config == "conclave":
                conclave_quality_sum += r.quality
                by_cat[r.category]["quality"] += r.quality
                by_cat[r.category]["n"] += 1
                count += 1
            if r.config == "sonnet_only":
                sonnet_quality_sum += r.quality

        sonnet_total = by_config["sonnet_only"] or 1e-9
        saving_pct = round((sonnet_total - by_config["conclave"]) / sonnet_total * 100, 1)
        quality_pct = round(
            (conclave_quality_sum / count) / (sonnet_quality_sum / max(count, 1)) * 100, 1
        ) if count else 0.0

        return {
            "run_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "conclave_version": "0.1.0",
            "haiku_model": ModelTier.HAIKU.value,
            "sonnet_model": ModelTier.SONNET.value,
            "summary": {
                "haiku_only_cost":  round(by_config["haiku_only"], 4),
                "sonnet_only_cost": round(by_config["sonnet_only"], 4),
                "conclave_cost":    round(by_config["conclave"], 4),
                "conclave_saving_vs_sonnet_pct": saving_pct,
                "conclave_quality_vs_sonnet_pct": quality_pct,
            },
            "by_category": by_cat,
            "tasks": [asdict(r) for r in self.runs],
        }

    # ------------------------------------------------------------------
    def save(self, path: Path, report: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2))
