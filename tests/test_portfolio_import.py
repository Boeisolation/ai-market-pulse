from __future__ import annotations

from pathlib import Path

import yaml

from ai_market_pulse.portfolio_import import import_portfolio_config, normalize_portfolio_assets, read_portfolio_assets


def test_read_portfolio_assets_supports_aliases_and_symbol_normalization(tmp_path: Path) -> None:
    source = tmp_path / "portfolio.csv"
    source.write_text(
        "ticker,asset,qty,avg_cost,tags\n"
        "AAPL,Apple,10,185,\"tech,mega-cap\"\n"
        "600519,Kweichow Moutai,1,1500,\"a-share,consumer\"\n",
        encoding="utf-8",
    )

    assets = read_portfolio_assets(source)

    assert assets[0]["symbol"] == "AAPL"
    assert assets[0]["quantity"] == 10
    assert assets[0]["cost_basis"] == 185
    assert assets[0]["tags"] == ["tech", "mega-cap"]
    assert assets[1]["symbol"] == "600519.SS"
    assert assets[1]["market"] == "CN"


def test_read_portfolio_assets_supports_chinese_headers_and_zero_padding(tmp_path: Path) -> None:
    source = tmp_path / "portfolio.tsv"
    source.write_text(
        "股票代码\t股票名称\t持仓\t成本价\t标签\t备注\n"
        "1\t平安银行\t100\t12.5\t银行;A股\tleading-zero test\n",
        encoding="utf-8",
    )

    assets = read_portfolio_assets(source)

    assert assets == [
        {
            "symbol": "000001.SZ",
            "market": "CN",
            "name": "平安银行",
            "note": "leading-zero test",
            "quantity": 100,
            "cost_basis": 12.5,
            "tags": ["银行", "A股"],
        }
    ]


def test_import_portfolio_config_writes_watchlist_yaml(tmp_path: Path) -> None:
    source = tmp_path / "portfolio.csv"
    output = tmp_path / "watchlist.yaml"
    source.write_text("symbol,name,quantity,cost_basis\nNVDA,NVIDIA,6,140\n", encoding="utf-8")

    path = import_portfolio_config(source, output, template="us-tech", title="Imported Pulse")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))

    assert data["title"] == "Imported Pulse"
    assert data["data"]["providers"] == ["yfinance"]
    assert data["assets"] == [
        {
            "symbol": "NVDA",
            "market": "US",
            "name": "NVIDIA",
            "quantity": 6,
            "cost_basis": 140,
        }
    ]


def test_normalize_portfolio_assets_merges_duplicate_positions() -> None:
    assets = normalize_portfolio_assets(
        [
            {"symbol": "AAPL", "quantity": 2, "cost_basis": 100, "tags": ["tech"]},
            {"symbol": "aapl", "quantity": 1, "cost_basis": 130, "tags": ["mega-cap"]},
        ]
    )

    assert assets == [
        {
            "symbol": "AAPL",
            "market": "US",
            "quantity": 3.0,
            "cost_basis": 110.0,
            "tags": ["tech", "mega-cap"],
        }
    ]
