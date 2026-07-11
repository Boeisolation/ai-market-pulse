from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from ai_market_pulse.alerts import evaluate_alerts
from ai_market_pulse.config import AlertSettings
from ai_market_pulse.models import Asset, AssetAnalysis, DailyReport, PriceSnapshot, SignalScore


def _report(score: int, risk: str, change: float) -> DailyReport:
    analysis = AssetAnalysis(
        asset=Asset(symbol="AAA"),
        snapshot=PriceSnapshot("AAA", "AAA", "USD", 10, 9, change, "2026-01-01", "2026-07-10", 100),
        metrics={},
        signal=SignalScore(score, "watch", risk, ["reason"]),
        news=[],
    )
    return DailyReport("Pulse", datetime(2026, 7, 10), "UTC", "en-US", [analysis], "brief")


def test_alerts_baseline_then_detect_and_dedupe_changes() -> None:
    settings = AlertSettings(enabled=True, score_change=10, daily_move=0.05)
    first_events, first_state = evaluate_alerts(_report(50, "low", 0.01), {}, settings)
    assert first_events == []

    second_events, second_state = evaluate_alerts(_report(70, "high", 0.08), first_state, settings)
    assert {event.kind for event in second_events} == {"score-change", "risk-upgrade", "daily-move"}

    third_events, _ = evaluate_alerts(_report(70, "high", 0.08), second_state, settings)
    assert third_events == []


def test_alert_state_keeps_independent_reports_immutable() -> None:
    report = _report(50, "low", 0.01)
    updated = replace(report, title="Other")
    assert report.title == "Pulse"
    assert updated.title == "Other"
