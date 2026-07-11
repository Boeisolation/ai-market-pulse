from __future__ import annotations

from pathlib import Path

import yaml

from ai_market_pulse.cli import _load_run_config, main
from ai_market_pulse.sample import custom_watchlist_config, parse_symbols


def test_custom_watchlist_config_normalizes_symbols_and_markets() -> None:
    config = yaml.safe_load(
        custom_watchlist_config(
            ["aapl", "600519", "0700.HK", "BTC-USD"],
            title="Client Watchlist",
            providers=["yfinance"],
        )
    )

    assert config["title"] == "Client Watchlist"
    assert config["data"]["providers"] == ["yfinance"]
    assert config["assets"] == [
        {"symbol": "AAPL", "market": "US"},
        {"symbol": "600519.SS", "market": "CN"},
        {"symbol": "0700.HK", "market": "HK"},
        {"symbol": "BTC-USD", "market": "CRYPTO"},
    ]
    assert config["benchmarks"]["compare"]["AAPL"] == "QQQ"


def test_parse_symbols_accepts_commas_spaces_and_chinese_commas() -> None:
    assert parse_symbols("AAPL, MSFT  NVDA，600519") == ["AAPL", "MSFT", "NVDA", "600519"]


def test_init_symbols_writes_custom_watchlist(tmp_path: Path) -> None:
    output = tmp_path / "watchlist.yaml"

    main(["init", "--symbols", "AAPL,MSFT,600519", "--path", str(output), "--title", "Real Portfolio"])

    config = yaml.safe_load(output.read_text(encoding="utf-8"))
    assert config["title"] == "Real Portfolio"
    assert [asset["symbol"] for asset in config["assets"]] == ["AAPL", "MSFT", "600519.SS"]


def test_run_symbols_builds_inline_config() -> None:
    config, label = _load_run_config(
        Path("unused.yaml"),
        "AAPL,MSFT,600519",
        "Inline Pulse",
        "Asia/Shanghai",
        "zh-CN",
        "yfinance",
    )

    assert label == "inline --symbols"
    assert config.title == "Inline Pulse"
    assert config.timezone == "Asia/Shanghai"
    assert [asset.symbol for asset in config.assets] == ["AAPL", "MSFT", "600519.SS"]
    assert [asset.market for asset in config.assets] == ["US", "US", "CN"]
