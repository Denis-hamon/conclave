# Conclave benchmarks

`results.json` is the published output of the cost/quality benchmark used to
back the claims in the README (routing savings vs all-Sonnet, quality parity,
per-category breakdown).

## Reproduce

The benchmark runs the fixed task set in `conclave/benchmark_tasks.py` in three
configurations — **all-Haiku**, **all-Sonnet**, and **Conclave routing** — then
records cost per category and a quality score from a Haiku evaluator.

### Dry run (no API key, fake tokens)

Quick sanity check that the pipeline wires up. Produces a `results.json` with
deterministic fake costs — **do not publish this version**.

```bash
pip install -e ".[dev]"
conclave benchmark --dry-run
```

### Real run (requires `ANTHROPIC_API_KEY`)

This is what regenerates the published `results.json`. Expect ~60 API calls and
a few dollars of spend.

```bash
export ANTHROPIC_API_KEY=sk-ant-...
conclave benchmark --output benchmarks/results.json
```

### Programmatic (for CI / scripted regeneration)

```bash
python benchmarks/run.py
```

Equivalent to `conclave benchmark` but importable and easy to hook into a
nightly workflow.

## Interpreting results

- `summary.conclave_saving_vs_sonnet_pct` — negative numbers mean Conclave
  spent more than all-Sonnet. This happens when the task mix is heavily skewed
  toward novel work (classifier correctly escalates most tasks to Sonnet and
  the classifier itself adds overhead).
- `summary.conclave_quality_vs_sonnet_pct` — Haiku evaluator pass rate vs the
  Sonnet reference output. 100% means Conclave's Haiku outputs were judged
  equivalent to Sonnet on every task.
- `by_category` — workload mix matters. The headline savings figure in the
  README (~37% on a product-squad run, up to ~70% on workloads with more
  repetitive handoffs) is a composition of per-category cost deltas weighted
  by task count.
