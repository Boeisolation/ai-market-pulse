from __future__ import annotations

from datetime import datetime

from ai_market_pulse.models import Asset, AssetAnalysis, DailyReport, NewsItem, PriceSnapshot, SignalScore, ThemeSummary
from ai_market_pulse.reporting import render_html, render_markdown


def test_render_markdown_includes_ai_portfolio_brief_and_source() -> None:
    report = DailyReport(
        title="Pulse",
        generated_at=datetime(2026, 7, 8, 8, 0),
        timezone="UTC",
        language="en-US",
        market_brief="brief",
        portfolio_ai_summary="Portfolio state: calm.",
        themes=[
            ThemeSummary(
                tag="ai",
                symbols=["AAA"],
                average_score=70,
                weighted_score=None,
                return_20d=0.1,
                return_60d=0.2,
                relative_return_20d=0.03,
                relative_return_60d=0.04,
                high_risk_count=0,
                positioned_count=0,
            )
        ],
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
    assert "## Theme Research" in markdown
    assert "| ai |" in markdown


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
    assert "信号总览" in html
    assert "data-theme-choice" in html


def test_signal_overview_uses_signal_stance_and_flags_missing_freshness() -> None:
    report = DailyReport(
        title="Pulse",
        generated_at=datetime(2026, 7, 8, 8, 0),
        timezone="UTC",
        language="en-US",
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
                metrics={},
                signal=SignalScore(score=42, stance="defensive", risk_level="low", reasons=[]),
                news=[],
            )
        ],
    )

    rendered = render_html(report)
    overview = rendered[rendered.index('<section class="signal-board">') : rendered.index("</section>", rendered.index('<section class="signal-board">'))]

    neutral_start = overview.index('<div class="distribution-item neutral">')
    defensive_start = overview.index('<div class="distribution-item defensive">')
    neutral = overview[neutral_start:defensive_start]
    defensive = overview[defensive_start:]

    assert 'style="width:0.0%"' in neutral
    assert "<strong>0</strong>" in neutral
    assert 'style="width:100.0%"' in defensive
    assert "<strong>1</strong>" in defensive
    assert '<strong class="data-amber">1</strong>' in overview
