from __future__ import annotations

from datetime import datetime

import pytest

from ai_market_pulse import cli
from ai_market_pulse.config import (
    AnalysisSettings,
    AppConfig,
    BenchmarkSettings,
    DataSettings,
    LLMSettings,
    NewsSettings,
    NotificationTarget,
)
from ai_market_pulse.models import Asset, AssetAnalysis, DailyReport, PriceSnapshot, SignalScore


def _failed_report() -> DailyReport:
    return DailyReport(
        title="Test",
        generated_at=datetime(2026, 7, 8, 8, 0),
        timezone="UTC",
        language="en-US",
        market_brief="No valid market data was available.",
        analyses=[
            AssetAnalysis(
                asset=Asset(symbol="ZZZ"),
                snapshot=PriceSnapshot(
                    symbol="ZZZ",
                    name="ZZZ",
                    currency=None,
                    last_close=0,
                    previous_close=None,
                    change_pct=None,
                    start_date="",
                    end_date="",
                    rows=0,
                ),
                metrics={},
                signal=SignalScore(score=50, stance="neutral", risk_level="low", reasons=[]),
                news=[],
                warnings=["boom"],
            )
        ],
    )


def test_run_aborts_and_skips_notify_when_no_valid_data(tmp_path, monkeypatch) -> None:
    config = AppConfig(
        title="Test",
        timezone="UTC",
        assets=[Asset(symbol="ZZZ")],
        analysis=AnalysisSettings(),
        data=DataSettings(),
        benchmarks=BenchmarkSettings(enabled=False),
        news=NewsSettings(enabled=False),
        llm=LLMSettings(enabled=False),
        notifications=[NotificationTarget(type="webhook", settings={"url": "https://x"})],
    )
    monkeypatch.setattr(cli, "load_config", lambda path: config)
    monkeypatch.setattr(cli, "run_analysis", lambda config, label: _failed_report())

    attempted: list[object] = []
    monkeypatch.setattr(
        cli, "send_notifications", lambda *args, **kwargs: attempted.append(args) or []
    )

    with pytest.raises(SystemExit):
        cli._run(
            config_path=tmp_path / "watchlist.yaml",
            output_dir=tmp_path / "reports",
            history_path=tmp_path / "history.jsonl",
            no_history=False,
            no_notify=False,
            no_ai=False,
            ai_only=False,
        )

    # The circuit breaker must prevent publishing a broken report and history.
    assert attempted == []
    assert not (tmp_path / "history.jsonl").exists()
