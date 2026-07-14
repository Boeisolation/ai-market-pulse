from __future__ import annotations

import sys
import types

import pandas as pd

from ai_market_pulse.market_data import (
    ProviderSpec,
    _a_share_code,
    _fetch_yfinance,
    _normalize_history,
    _snapshot,
    fetch_history,
    register_provider,
)
from ai_market_pulse.models import Asset, PriceSnapshot


def test_a_share_code_detects_common_symbols() -> None:
    assert _a_share_code(Asset(symbol="600519.SS")) == "600519"
    assert _a_share_code(Asset(symbol="000001.SZ")) == "000001"
    assert _a_share_code(Asset(symbol="300750", market="CN")) == "300750"
    assert _a_share_code(Asset(symbol="AAPL", market="US")) is None


def test_normalize_history_accepts_ohlc_and_builds_snapshot() -> None:
    raw = pd.DataFrame(
        [
            {"Date": "2026-01-02", "Open": "10", "High": "12", "Low": "9", "Close": "11", "Volume": "100"},
            {"Date": "2026-01-03", "Open": "11", "High": "13", "Low": "10", "Close": "12", "Volume": "120"},
        ]
    )

    history = _normalize_history(raw, "TEST")
    snapshot = _snapshot("TEST", "Test Asset", "USD", history, source="unit")

    assert list(history.columns) == ["Date", "Open", "High", "Low", "Close", "Volume"]
    assert snapshot.last_close == 12
    assert snapshot.change_pct == 0.090909
    assert snapshot.source == "unit"


def test_fetch_yfinance_widens_calendar_window_and_tails(monkeypatch) -> None:
    calls: dict[str, str] = {}

    class FakeTicker:
        def __init__(self, symbol: str) -> None:
            self.symbol = symbol

        def history(self, period: str, auto_adjust: bool) -> pd.DataFrame:
            calls["period"] = period
            rows = 300
            index = pd.date_range("2024-01-01", periods=rows, freq="B")
            index.name = "Date"
            close = [float(i + 1) for i in range(rows)]
            return pd.DataFrame(
                {"Open": close, "High": close, "Low": close, "Close": close, "Volume": [100] * rows},
                index=index,
            )

        @property
        def fast_info(self) -> dict:
            return {}

        @property
        def info(self) -> dict:
            return {"shortName": "Fake Co", "currency": "USD"}

    fake_module = types.ModuleType("yfinance")
    fake_module.Ticker = FakeTicker  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "yfinance", fake_module)

    asset, snapshot, history = _fetch_yfinance(Asset(symbol="AAA"), 220)

    # yfinance period must be widened well beyond the 220 trading-day target.
    assert int(calls["period"].rstrip("d")) > 300
    # history is trimmed back to the trading-day target, which is enough for SMA200.
    assert len(history) == 220
    assert snapshot.source == "yfinance"
    assert asset.currency == "USD"


def test_custom_provider_can_be_registered() -> None:
    def fetch(asset: Asset, lookback: int):
        frame = pd.DataFrame([{"Date": "2026-07-10", "Open": 1, "High": 1, "Low": 1, "Close": 1}])
        return asset, PriceSnapshot(asset.symbol, asset.symbol, "USD", 1, None, None, "2026-07-10", "2026-07-10", 1), frame

    register_provider(ProviderSpec("unit-provider", fetch, lambda asset: asset.market == "US"))
    _, snapshot, _ = fetch_history(Asset("UNIT"), 1, ["unit-provider"])
    assert snapshot.last_close == 1


def test_fetch_baostock_honors_explicit_exchange_suffix(monkeypatch) -> None:
    # 000300.SS (CSI 300 index) shares its 000xxx range with SZ stocks; prefix
    # guessing sent it to sz.000300 and the benchmark silently went missing.
    from ai_market_pulse.market_data import _fetch_baostock

    captured: dict[str, str] = {}

    class FakeQuery:
        def __init__(self) -> None:
            self._rows = [["2026-07-10", "1", "1", "1", "1", "100"]]

        def next(self) -> bool:
            return bool(self._rows)

        def get_row_data(self) -> list[str]:
            return self._rows.pop()

    class FakeResult:
        error_code = "0"
        error_msg = ""

    fake_module = types.ModuleType("baostock")
    fake_module.login = lambda: FakeResult()  # type: ignore[attr-defined]
    fake_module.logout = lambda: None  # type: ignore[attr-defined]

    def fake_query(code, fields, **kwargs):
        captured["code"] = code
        return FakeQuery()

    fake_module.query_history_k_data_plus = fake_query  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "baostock", fake_module)

    _fetch_baostock(Asset(symbol="000300.SS", market="CN"), 30)
    assert captured["code"] == "sh.000300"

    _fetch_baostock(Asset(symbol="000001.SZ", market="CN"), 30)
    assert captured["code"] == "sz.000001"
