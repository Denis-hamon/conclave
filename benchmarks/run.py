"""
Programmatic entry point for the Conclave benchmark.

Equivalent to `conclave benchmark --output benchmarks/results.json`, but
importable so it can be called from CI, scripts, or a pipeline without
spawning the CLI.

Requires ANTHROPIC_API_KEY for a real run. Pass --dry-run to exercise the
pipeline with zero API calls (useful for smoke-testing the harness itself).

Usage:
    python benchmarks/run.py                 # real run
    python benchmarks/run.py --dry-run       # no API calls
    python benchmarks/run.py --output path.json
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import anthropic

from conclave.benchmark import ConclaveBenchmark
from conclave.dry_run import DryRunClient

REPO_ROOT = Path(__file__).parent.parent
DEFAULT_OUTPUT = REPO_ROOT / "benchmarks" / "results.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Regenerate benchmarks/results.json")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip API calls; produce fake but deterministic costs for smoke tests.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Where to write the report (default: {DEFAULT_OUTPUT.relative_to(REPO_ROOT)}).",
    )
    args = parser.parse_args()

    client = DryRunClient() if args.dry_run else anthropic.Anthropic()
    bench = ConclaveBenchmark(client=client, dry_run=args.dry_run)
    report = bench.run()
    bench.save(args.output, report)

    s = report["summary"]
    print(f"Wrote {args.output}")
    print(f"  conclave_cost:                 ${s['conclave_cost']:.4f}")
    print(f"  sonnet_only_cost:              ${s['sonnet_only_cost']:.4f}")
    print(f"  saving_vs_sonnet:              {s['conclave_saving_vs_sonnet_pct']:.1f}%")
    print(f"  quality_vs_sonnet:             {s['conclave_quality_vs_sonnet_pct']:.1f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
