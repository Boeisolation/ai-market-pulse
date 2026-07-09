from __future__ import annotations

from datetime import datetime

from ai_market_pulse import notify
from ai_market_pulse.config import NotificationTarget
from ai_market_pulse.models import Asset, AssetAnalysis, DailyReport, PriceSnapshot, SignalScore


def _report() -> DailyReport:
    return DailyReport(
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
                    change_pct=0.1,
                    start_date="2026-01-01",
                    end_date="2026-07-08",
                    rows=2,
                    source="unit",
                ),
                metrics={},
                signal=SignalScore(score=70, stance="watch bullish", risk_level="low", reasons=["r"]),
                news=[],
            )
        ],
    )


def test_compact_message_never_leaks_local_path() -> None:
    message = notify._compact_message(_report(), None)

    assert "Report:" not in message
    assert ".html" not in message
    assert "AAA" in message


def test_compact_message_includes_public_url() -> None:
    message = notify._compact_message(_report(), "https://example.github.io/site/")

    assert "https://example.github.io/site/" in message


def test_compact_message_ignores_non_http_url() -> None:
    message = notify._compact_message(_report(), "/tmp/reports/market-pulse.html")

    assert "Report:" not in message
    assert "/tmp/reports" not in message


def test_send_notifications_posts_webhook_with_url(monkeypatch) -> None:
    sent: dict[str, object] = {}

    def fake_post(url, payload):
        sent["url"] = url
        sent["payload"] = payload

    monkeypatch.setattr(notify, "_post_json", fake_post)
    target = NotificationTarget(
        type="webhook", name="hook", enabled=True, settings={"url": "https://hook.example/x"}
    )

    results = notify.send_notifications(
        _report(), [target], html_path=None, report_url="https://pages.example/r"
    )

    assert results and "sent" in results[0]
    assert sent["url"] == "https://hook.example/x"
    assert "https://pages.example/r" in sent["payload"]["text"]


def test_send_notifications_skips_disabled_targets(monkeypatch) -> None:
    monkeypatch.setattr(notify, "_post_json", lambda url, payload: None)
    target = NotificationTarget(
        type="webhook", name="hook", enabled=False, settings={"url": "https://hook.example/x"}
    )

    results = notify.send_notifications(_report(), [target])

    assert results == []
