from __future__ import annotations

from datetime import datetime

from ai_market_pulse.models import Asset, AssetAnalysis, DailyReport, NewsItem, PriceSnapshot, SignalScore
from ai_market_pulse.reporting import render_html, render_markdown


def test_render_markdown_includes_ai_portfolio_brief_and_source() -> None:
    report = DailyReport(
        title="Pulse",
        generated_at=datetime(2026, 7, 8, 8, 0),
        timezone="UTC",
        language="en-US",
        market_brief="brief",
        portfolio_ai_summary="Portfolio state: calm.",
        analyses=[
            AssetAnalysis(
                asset=Asset(symbol="AAA"),
                snapshot=PriceSnapshot(
                    symbol="AAA",
                    name="AAA Corp",
                    currency="USD",
                    last_close=10,
                    previous_close=9,
                    change_pct=0.111111,
                    start_date="2026-01-01",
                    end_date="2026-07-08",
                    rows=2,
                    source="unit",
                ),
                metrics={"return_20d": 0.1, "return_60d": 0.2, "rsi14": 55, "atr_pct": 0.02},
                signal=SignalScore(score=70, stance="watch bullish", risk_level="low", reasons=["reason"]),
                news=[NewsItem(title="news", link="https://example.com")],
            )
        ],
    )

    markdown = render_markdown(report)

    assert "## AI Portfolio Brief" in markdown
    assert "Portfolio state: calm." in markdown
    assert "unit" in markdown


def test_render_html_includes_language_switch() -> None:
    report = DailyReport(
        title="Pulse",
        generated_at=datetime(2026, 7, 8, 8, 0),
        timezone="UTC",
        language="zh-CN",
        market_brief="brief",
        analyses=[
            AssetAnalysis(
                asset=Asset(symbol="AAA"),
                snapshot=PriceSnapshot(
                    symbol="AAA",
                    name="AAA Corp",
                    currency="USD",
                    last_close=10,
                    previous_close=9,
                    change_pct=0.111111,
                    start_date="2026-01-01",
                    end_date="2026-07-08",
                    rows=2,
                    source="unit",
                ),
                metrics={"return_20d": 0.1, "rsi14": 55},
                signal=SignalScore(score=70, stance="watch bullish", risk_level="low", reasons=["reason"]),
                news=[],
            )
        ],
    )

    html = render_html(report)

    assert 'data-lang="zh"' in html
    assert "data-lang-choice" in html
    assert "每日量化研究简报" in html
