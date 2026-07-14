from __future__ import annotations

import os
import time

import yaml

from ai_market_pulse import web
from ai_market_pulse.dashboard import build_dashboard_data
from ai_market_pulse.models import HistoryPoint, PriceSnapshot
from ai_market_pulse.web import (
    latest_outputs,
    load_saved_portfolio,
    portfolio_quotes,
    save_console_portfolio,
)

_ASSETS = [
    {"symbol": "160216.OF", "market": "CN", "name": "国泰大宗商品", "quantity": 5615.87, "cost_basis": 0.6526},
    {"symbol": "005827.OF", "market": "CN", "name": "易方达蓝筹精选混合", "quantity": 100.0},
]


def _write_watchlist(path, assets, title="测试报告"):
    mapping = {
        "title": title,
        "timezone": "Asia/Shanghai",
        "data": {"providers": ["akshare", "akshare_fund"]},
        "assets": assets,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(mapping, allow_unicode=True, sort_keys=False), encoding="utf-8")


def test_load_saved_portfolio_prefers_newer_file(tmp_path):
    _write_watchlist(tmp_path / "watchlist.yaml", _ASSETS, title="每日配置")
    _write_watchlist(tmp_path / "data/console-watchlist.yaml", _ASSETS[:1], title="控制台存档")
    old = time.time() - 3600
    os.utime(tmp_path / "watchlist.yaml", (old, old))

    result = load_saved_portfolio(tmp_path)

    assert result["source"] == "console"
    assert result["title"] == "控制台存档"
    assert len(result["assets"]) == 1
    assert result["assets"][0]["symbol"] == "160216.OF"
    assert result["providers"] == ["akshare", "akshare_fund"]
    assert result["updatedAt"]


def test_load_saved_portfolio_falls_back_to_daily_watchlist(tmp_path):
    _write_watchlist(tmp_path / "watchlist.yaml", _ASSETS, title="每日配置")

    result = load_saved_portfolio(tmp_path)

    assert result["source"] == "watchlist"
    assert len(result["assets"]) == 2


def test_load_saved_portfolio_without_files(tmp_path):
    assert load_saved_portfolio(tmp_path) == {"assets": [], "source": None}


def test_load_saved_portfolio_ignores_corrupt_yaml(tmp_path):
    (tmp_path / "watchlist.yaml").write_text("assets: [::not yaml", encoding="utf-8")

    assert load_saved_portfolio(tmp_path)["source"] is None


def test_save_console_portfolio_round_trips(tmp_path):
    payload = {"assets": _ASSETS, "title": "我的持仓", "timezone": "Asia/Shanghai", "providers": "akshare, akshare_fund"}

    result = save_console_portfolio(payload, tmp_path)

    assert result["saved"] == 2
    saved = yaml.safe_load((tmp_path / "data/console-watchlist.yaml").read_text(encoding="utf-8"))
    assert saved["title"] == "我的持仓"
    assert [asset["symbol"] for asset in saved["assets"]] == ["160216.OF", "005827.OF"]
    reloaded = load_saved_portfolio(tmp_path)
    assert reloaded["source"] == "console"
    assert reloaded["assets"][0]["quantity"] == 5615.87


def test_save_console_portfolio_rejects_empty(tmp_path):
    try:
        save_console_portfolio({"assets": [{"symbol": "", "name": "无代码"}]}, tmp_path)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for empty holdings")


def test_latest_outputs_picks_newest_report(tmp_path):
    reports = tmp_path / "reports"
    reports.mkdir()
    for stamp in ("20260713-0900", "20260714-0908"):
        (reports / f"market-pulse-{stamp}.html").write_text("<html></html>", encoding="utf-8")
        (reports / f"market-pulse-{stamp}.json").write_text("{}", encoding="utf-8")
    (reports / "dashboard.html").write_text("<html></html>", encoding="utf-8")
    site = tmp_path / "site"
    site.mkdir()
    (site / "index.html").write_text("<html></html>", encoding="utf-8")

    outputs = latest_outputs(tmp_path)

    assert outputs["html"] == "/reports/market-pulse-20260714-0908.html"
    assert outputs["json"] == "/reports/market-pulse-20260714-0908.json"
    assert outputs["markdown"] is None
    assert outputs["dashboard"] == "/reports/dashboard.html"
    assert outputs["site"] == "/site/index.html"
    assert outputs["generatedAt"]


def test_latest_outputs_empty_workspace(tmp_path):
    outputs = latest_outputs(tmp_path)

    assert outputs["html"] is None
    assert outputs["dashboard"] is None
    assert outputs["site"] is None
    assert outputs["reports"] == []


def test_latest_outputs_lists_all_reports_newest_first(tmp_path):
    reports = tmp_path / "reports"
    reports.mkdir()
    for stamp in ("20260712-0900", "20260714-0908"):
        (reports / f"market-pulse-{stamp}.html").write_text("<html></html>", encoding="utf-8")

    outputs = latest_outputs(tmp_path)

    assert [item["title"] for item in outputs["reports"]] == ["2026-07-14 09:08", "2026-07-12 09:00"]
    assert outputs["reports"][0]["href"] == "/reports/market-pulse-20260714-0908.html"


def test_save_console_portfolio_syncs_daily_watchlist(tmp_path):
    daily = {
        "title": "每日报告",
        "llm": {"enabled": True},
        "assets": [{"symbol": "AAPL", "market": "US"}],
    }
    (tmp_path / "watchlist.yaml").write_text(yaml.safe_dump(daily, allow_unicode=True), encoding="utf-8")

    result = save_console_portfolio({"assets": _ASSETS}, tmp_path)

    assert result["synced"] is True
    updated = yaml.safe_load((tmp_path / "watchlist.yaml").read_text(encoding="utf-8"))
    assert [asset["symbol"] for asset in updated["assets"]] == ["160216.OF", "005827.OF"]
    assert updated["llm"] == {"enabled": True}
    assert updated["title"] == "每日报告"


def test_save_console_portfolio_without_daily_watchlist(tmp_path):
    result = save_console_portfolio({"assets": _ASSETS[:1]}, tmp_path)

    assert result["synced"] is False


def _history_point(symbol, date, close=1.0):
    return HistoryPoint(symbol=symbol, date=date, score=50, risk_level="low", stance="neutral", close=close)


def test_dashboard_filters_to_current_symbols():
    records = [
        _history_point("160216.OF", "2026-07-14"),
        _history_point("NVDA", "2026-07-12"),
        _history_point("AAPL", "2026-07-12"),
    ]

    data = build_dashboard_data(records, symbols={"160216.OF"})

    assert [trend.symbol for trend in data.symbol_trends] == ["160216.OF"]


def test_portfolio_quotes_uses_snapshot(monkeypatch, tmp_path):
    def fake_fetch(asset, lookback_days, providers, cache=None):
        if asset.symbol == "BAD.OF":
            raise RuntimeError("no data")
        snapshot = PriceSnapshot(
            symbol=asset.symbol,
            name=asset.name or asset.symbol,
            currency="CNY",
            last_close=0.623,
            previous_close=0.625,
            change_pct=-0.0032,
            start_date="2026-05-01",
            end_date="2026-07-10",
            rows=45,
        )
        return asset, snapshot, None

    monkeypatch.setattr(web, "fetch_history", fake_fetch)
    payload = {"assets": [{"symbol": "160216.OF", "market": "CN"}, {"symbol": "BAD.OF", "market": "CN"}]}

    result = portfolio_quotes(payload, tmp_path)

    good = result["quotes"]["160216.OF"]
    assert good == {"close": 0.623, "currency": "CNY", "date": "2026-07-10", "changePct": -0.0032}
    assert "error" in result["quotes"]["BAD.OF"]
