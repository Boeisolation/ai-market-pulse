from __future__ import annotations

from ai_market_pulse.config import AppConfig, DataSettings
from ai_market_pulse.doctor import format_doctor, run_doctor
from ai_market_pulse.models import Asset


def test_doctor_reports_asset_provider_capability() -> None:
    config = AppConfig(
        title="Doctor",
        timezone="UTC",
        assets=[Asset(symbol="AAPL"), Asset(symbol="600519.SS")],
        data=DataSettings(providers=["yfinance"]),
    )

    output = format_doctor(run_doctor(config))

    assert "asset:AAPL" in output
    assert "asset:600519.SS" in output
    assert "provider:yfinance" in output
