from __future__ import annotations

from datetime import date

from ai_market_pulse.benchmarks import BenchmarkData, attach_benchmark_comparisons, build_data_freshness
from ai_market_pulse.config import BenchmarkSettings
from ai_market_pulse.models import Asset, AssetAnalysis, PriceSnapshot, SignalScore


def test_attach_benchmark_comparison_marks_outperformance() -> None:
    analysis = AssetAnalysis(
        asset=Asset(symbol="AAA", market="US"),
        snapshot=_snapshot("AAA"),
        metrics={"return_20d": 0.12, "return_60d": 0.18},
        signal=SignalScore(score=70, stance="constructive", risk_level="low", reasons=[]),
        news=[],
    )
    benchmark = BenchmarkData(
        asset=Asset(symbol="SPY", name="S&P 500 ETF", market="US"),
        snapshot=_snapshot("SPY"),
        metrics={"return_20d": 0.04, "return_60d": 0.08},
        freshness=build_data_freshness(_snapshot("SPY"), date(2026, 7, 8)),
    )

    enriched = attach_benchmark_comparisons([analysis], {"SPY": benchmark}, BenchmarkSettings())

    assert enriched[0].benchmark is not None
    assert enriched[0].benchmark.symbol == "SPY"
    assert enriched[0].benchmark.relative_return_20d == 0.08
    assert enriched[0].benchmark.verdict == "outperforming"


def test_build_data_freshness_flags_stale_data() -> None:
    freshness = build_data_freshness(_snapshot("AAA", end_date="2026-06-30"), date(2026, 7, 8), stale_after_days=4)

    assert freshness.status == "stale"
    assert freshness.age_days == 8
    assert "verify data freshness" in freshness.message


def _snapshot(symbol: str, end_date: str = "2026-07-08") -> PriceSnapshot:
    return PriceSnapshot(
        symbol=symbol,
        name=symbol,
        currency="USD",
        last_close=100,
        previous_close=99,
        change_pct=0.01,
        start_date="2026-01-01",
        end_date=end_date,
        rows=120,
        source="unit",
    )
