from __future__ import annotations

import sys
import types

import pandas as pd
import pytest

from ai_market_pulse import market_data
from ai_market_pulse.config import LLMSettings, NewsSettings, load_config
from ai_market_pulse.market_data import (
    MarketDataError,
    _fund_code,
    _fund_nav_to_history,
    fetch_history,
    get_provider,
)
from ai_market_pulse.models import Asset, is_otc_fund_symbol
from ai_market_pulse.portfolio_import import normalize_portfolio_assets


def test_is_otc_fund_symbol_detects_suffix() -> None:
    assert is_otc_fund_symbol("005827.OF")
    assert is_otc_fund_symbol("005827.of")
    assert not is_otc_fund_symbol("600519.SS")
    assert not is_otc_fund_symbol("005827")
    assert not is_otc_fund_symbol("ABCDEF.OF")
    assert not is_otc_fund_symbol("05827.OF")


def test_fund_code_and_provider_routing() -> None:
    fund = Asset(symbol="005827.OF")
    stock = Asset(symbol="600519.SS")
    assert _fund_code(fund) == "005827"
    assert _fund_code(stock) is None
    assert get_provider("akshare_fund").can_handle(fund)
    assert get_provider("fund").can_handle(fund)
    assert not get_provider("akshare").can_handle(fund)
    # Yahoo has no OTC fund data; the spec must skip funds instead of failing.
    assert not get_provider("yfinance").can_handle(fund)
    assert get_provider("yfinance").can_handle(stock)


def test_fund_nav_adjusts_dividends_and_anchors_last_nav() -> None:
    # Ex-dividend day: raw NAV collapses 1.10 -> 0.66 but the true (adjusted)
    # return that day is +20%, which is what 天天基金's 日增长率 reports.
    raw = pd.DataFrame(
        {
            "净值日期": ["2026-01-02", "2026-01-05", "2026-01-06"],
            "单位净值": [1.0, 1.10, 0.66],
            "日增长率": [None, 10.0, 20.0],
        }
    )
    history = _fund_nav_to_history(raw, "005827.OF")

    closes = history["Close"].tolist()
    assert closes[-1] == pytest.approx(0.66)  # anchored to the published NAV
    assert closes[-1] / closes[-2] - 1 == pytest.approx(0.20)  # dividend-adjusted return
    assert closes[-2] / closes[-3] - 1 == pytest.approx(0.10)
    assert (history["Open"] == history["Close"]).all()
    assert (history["High"] == history["Close"]).all()
    assert history["Volume"].isna().all()


def _install_fake_akshare(monkeypatch, *, nav_frame: pd.DataFrame, directory: pd.DataFrame) -> dict:
    calls: dict[str, object] = {}
    fake = types.ModuleType("akshare")

    def fund_open_fund_info_em(symbol: str, indicator: str) -> pd.DataFrame:
        calls["symbol"] = symbol
        calls["indicator"] = indicator
        return nav_frame

    fake.fund_open_fund_info_em = fund_open_fund_info_em
    fake.fund_name_em = lambda: directory
    monkeypatch.setitem(sys.modules, "akshare", fake)
    monkeypatch.setattr(market_data, "_FUND_DIRECTORY", None)
    return calls


_DIRECTORY = pd.DataFrame(
    {
        "基金代码": ["005827", "000198"],
        "基金简称": ["易方达蓝筹精选混合", "天弘余额宝货币"],
        "基金类型": ["混合型-偏股", "货币型-普通货币"],
    }
)


def _nav_frame(rows: int = 60) -> pd.DataFrame:
    dates = pd.date_range("2026-01-01", periods=rows, freq="B").strftime("%Y-%m-%d")
    navs = [round(1.0 + 0.01 * i, 4) for i in range(rows)]
    growth = [None] + [round((navs[i] / navs[i - 1] - 1) * 100, 4) for i in range(1, rows)]
    return pd.DataFrame({"净值日期": dates, "单位净值": navs, "日增长率": growth})


def test_fetch_history_hydrates_fund_via_akshare_fund(monkeypatch) -> None:
    calls = _install_fake_akshare(monkeypatch, nav_frame=_nav_frame(), directory=_DIRECTORY)

    asset, snapshot, history = fetch_history(Asset(symbol="005827.OF"), 30, ["akshare_fund"])

    assert calls["symbol"] == "005827"
    assert calls["indicator"] == "单位净值走势"
    assert asset.name == "易方达蓝筹精选混合"
    assert asset.currency == "CNY"
    assert asset.market == "CN"
    assert snapshot.source == "akshare_fund"
    assert len(history) == 30


def test_money_market_funds_are_rejected(monkeypatch) -> None:
    _install_fake_akshare(monkeypatch, nav_frame=_nav_frame(), directory=_DIRECTORY)

    with pytest.raises(MarketDataError, match="货币"):
        fetch_history(Asset(symbol="000198.OF"), 30, ["akshare_fund"])


def test_directory_failure_degrades_to_symbol_name(monkeypatch) -> None:
    fake = types.ModuleType("akshare")
    fake.fund_open_fund_info_em = lambda symbol, indicator: _nav_frame()
    def broken_directory() -> pd.DataFrame:
        raise RuntimeError("blocked")
    fake.fund_name_em = broken_directory
    monkeypatch.setitem(sys.modules, "akshare", fake)
    monkeypatch.setattr(market_data, "_FUND_DIRECTORY", None)

    asset, snapshot, _ = fetch_history(Asset(symbol="005827.OF"), 30, ["akshare_fund"])

    assert asset.name == "005827.OF"
    assert snapshot.source == "akshare_fund"


def test_config_defaults_fund_market_to_cn(tmp_path) -> None:
    config_path = tmp_path / "watchlist.yaml"
    config_path.write_text(
        "assets:\n  - '005827.OF'\n  - symbol: '161725.OF'\n  - symbol: AAPL\n",
        encoding="utf-8",
    )
    config = load_config(config_path)
    markets = {asset.symbol: asset.market for asset in config.assets}
    assert markets["005827.OF"] == "CN"
    assert markets["161725.OF"] == "CN"
    assert markets["AAPL"] == "US"
    assert "akshare_fund" in config.data.providers


def test_screenshot_import_keeps_of_suffix_and_infers_cn_market() -> None:
    records = [
        {"symbol": "005827.of", "name": "易方达蓝筹精选混合", "quantity": 100.5},
        {"symbol": "600519", "name": "贵州茅台"},
    ]
    assets = normalize_portfolio_assets(records)
    by_symbol = {item["symbol"]: item for item in assets}
    assert by_symbol["005827.OF"]["market"] == "CN"
    # Stock behaviour is unchanged: bare six-digit codes still map to exchanges.
    assert "600519.SS" in by_symbol


def test_extract_prompt_teaches_of_suffix(monkeypatch) -> None:
    from ai_market_pulse import llm

    captured: dict[str, list] = {}

    def fake_chat(messages, settings):
        captured["messages"] = messages
        return '{"assets": [{"symbol": "005827.OF"}]}'

    monkeypatch.setattr(llm, "_chat_completion", fake_chat)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    settings = LLMSettings(enabled=True, model="test-model")

    records = llm.extract_portfolio_from_image(b"fake-image", "image/png", settings)

    system_prompt = captured["messages"][0]["content"]
    assert ".OF" in system_prompt
    assert "货币基金" in system_prompt
    assert records == [{"symbol": "005827.OF"}]


def test_fund_news_uses_name_query_or_skips(monkeypatch) -> None:
    from ai_market_pulse import news

    captured: dict[str, list[str]] = {}

    def fake_query(query_parts, settings):
        captured["parts"] = query_parts
        return []

    monkeypatch.setattr(news, "_fetch_google_news_query", fake_query)
    settings = NewsSettings(enabled=True)

    named = Asset(symbol="005827.OF", name="易方达蓝筹精选混合")
    assert news.fetch_news(named, settings) == []
    assert captured["parts"][0] == "易方达蓝筹精选混合"
    assert "基金" in captured["parts"]

    captured.clear()
    anonymous = Asset(symbol="005827.OF")
    assert news.fetch_news(anonymous, settings) == []
    assert "parts" not in captured  # no network query without a usable name
