from __future__ import annotations

import math

import pandas as pd

from ai_market_pulse.backtest import format_backtest, run_backtest
from ai_market_pulse.config import ScoringSettings
from ai_market_pulse.scoring import score_asset


def _history(rows: int, trend: float) -> pd.DataFrame:
    closes = [100.0]
    for index in range(rows - 1):
        wiggle = math.sin(index / 5) * 0.3
        closes.append(max(closes[-1] * (1 + trend) + wiggle, 1.0))
    return pd.DataFrame(
        {
            "Date": pd.date_range("2024-01-01", periods=rows, freq="B"),
            "Open": closes,
            "High": [value * 1.01 for value in closes],
            "Low": [value * 0.99 for value in closes],
            "Close": closes,
            "Volume": [1000] * rows,
        }
    )


def test_run_backtest_produces_buckets_and_correlation() -> None:
    histories = {
        "UP": _history(320, trend=0.002),
        "DOWN": _history(320, trend=-0.002),
    }

    result = run_backtest(histories, horizon_days=20, step_days=10)

    assert result.samples > 0
    assert len(result.buckets) == 5
    assert sum(bucket.samples for bucket in result.buckets) == result.samples
    assert {item.symbol for item in result.symbols} == {"UP", "DOWN"}

    rendered = format_backtest(result)
    assert "Score bucket" in rendered
    assert "diagnostic" in rendered


def test_run_backtest_handles_short_history() -> None:
    result = run_backtest({"TINY": _history(60, trend=0.001)}, horizon_days=20, step_days=5)
    assert result.samples == 0
    assert result.correlation is None


def test_score_asset_honors_custom_weights() -> None:
    metrics = {
        "last_close": 120,
        "sma20": 115,
        "sma50": 110,
        "sma200": 90,
        "rsi14": 58,
        "macd": 1.2,
        "macd_signal": 0.7,
        "return_20d": 0.08,
        "return_60d": 0.15,
        "drawdown_60d": -0.04,
        "atr_pct": 0.02,
        "volume_ratio_20d": 1.6,
    }

    default_signal = score_asset(metrics)
    boosted = ScoringSettings(sma20_above=30, sma50_above=30, sma200_above=30)
    boosted_signal = score_asset(metrics, boosted)

    assert boosted_signal.score > default_signal.score
    assert score_asset(metrics, ScoringSettings()) == default_signal
