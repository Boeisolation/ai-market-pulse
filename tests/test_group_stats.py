from __future__ import annotations

from ai_market_pulse.group_stats import build_theme_summaries
from ai_market_pulse.models import Asset, AssetAnalysis, PositionMetrics, PriceSnapshot, SignalScore


def _analysis(symbol: str, score: int, value: float, tags: list[str], risk: str = "low") -> AssetAnalysis:
    return AssetAnalysis(
        asset=Asset(symbol=symbol, tags=tags),
        snapshot=PriceSnapshot(symbol, symbol, "USD", 10, 9, 0.01, "2026-01-01", "2026-07-10", 100),
        metrics={"return_20d": 0.1, "return_60d": 0.2},
        signal=SignalScore(score, "watch", risk, ["reason"]),
        news=[],
        position=PositionMetrics(symbol, "USD", 1, 8, 8, value, 1, 2, 0.25, value / 400),
    )


def test_theme_summaries_use_tags_and_position_weights() -> None:
    themes = build_theme_summaries(
        [
            _analysis("AAA", 80, 300, ["ai", "mega-cap"]),
            _analysis("BBB", 20, 100, ["ai"], risk="high"),
        ]
    )

    ai = next(item for item in themes if item.tag == "ai")
    assert ai.symbols == ["AAA", "BBB"]
    assert ai.average_score == 50
    assert ai.weighted_score == 65
    assert ai.high_risk_count == 1
    assert ai.market_value_by_currency == {"USD": 400.0}

