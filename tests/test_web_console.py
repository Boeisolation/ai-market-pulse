from __future__ import annotations

import os
import time

import yaml

from ai_market_pulse.web import latest_outputs, load_saved_portfolio, save_console_portfolio

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
