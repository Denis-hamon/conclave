"""Unit tests for CostMeter."""

from __future__ import annotations

import pytest

from conclave.cost import CostMeter
from conclave.router import ModelTier


def test_record_and_total():
    meter = CostMeter()
    meter.record(ModelTier.HAIKU, 1_000_000, 1_000_000)
    # Haiku: 0.80 input + 4.00 output = 4.80
    assert meter.total_cost == pytest.approx(4.80, rel=1e-4)


def test_baseline_always_sonnet():
    meter = CostMeter()
    meter.record(ModelTier.HAIKU, 1_000_000, 1_000_000)
    # Sonnet baseline: 3.00 + 15.00 = 18.00
    assert meter.baseline_cost == pytest.approx(18.00, rel=1e-4)


def test_savings_pct():
    meter = CostMeter()
    meter.record(ModelTier.HAIKU, 1_000_000, 1_000_000)
    # (18 - 4.80) / 18 = 73.33%
    assert meter.savings_pct == pytest.approx(73.33, rel=1e-2)


def test_merge():
    a = CostMeter()
    a.record(ModelTier.HAIKU, 100, 200)
    b = CostMeter()
    b.record(ModelTier.HAIKU, 300, 400)
    b.record(ModelTier.SONNET, 500, 600)

    a.merge(b)
    # Haiku merged: 400 in, 600 out
    haiku_key = "claude-haiku-4-5-20251001"
    assert a._usage[haiku_key].input_tokens == 400
    assert a._usage[haiku_key].output_tokens == 600
    assert "claude-sonnet-4-6" in a._usage


def test_summary_lines_format():
    meter = CostMeter()
    meter.record(ModelTier.HAIKU, 1000, 500)
    meter.record(ModelTier.SONNET, 2000, 1000)
    lines = meter.summary_lines()
    assert isinstance(lines, list)
    assert all(isinstance(ln, str) for ln in lines)
    joined = "\n".join(lines)
    assert "haiku" in joined
    assert "sonnet" in joined
    assert "$" in joined
