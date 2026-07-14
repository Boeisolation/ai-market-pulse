from __future__ import annotations

import pytest

from ai_market_pulse import web
from ai_market_pulse.web import options_from_payload, render_console_html


def test_render_console_html_contains_visual_symbol_form() -> None:
    html = render_console_html()

    assert "data-run-form" in html
    assert 'name="symbols"' in html
    assert 'value="我的自选股每日分析报告"' in html
    assert 'data-default-en="My Daily Stock Analysis Report"' in html
    assert "/api/analyze" in html
    assert "/api/portfolio/extract" in html
    assert "/api/ask" in html
    assert "导入券商或基金App持仓截图" in html
    assert "清空持仓" in html
    assert "min-width: 0" in html
    assert "新增持仓" in html
    assert 'alerts.join("\\n")' in html
    assert "/api/portfolio/save" in html
    assert "保存持仓" in html
    assert "data-nav-links" in html
    assert "data-holdings-count" in html
    assert "loadSavedPortfolio" in html
    assert "loadLatestOutputs" in html
    assert "data-topup-box" in html
    assert "data-topup-toggle" in html
    assert "批量加仓" in html
    assert "mergeEditorAssets" in html
    assert "确认加仓" in html
    assert "创建今日量化研究任务" in html
    assert "Research workflow" in html
    assert "主题研究" in html


def test_options_from_payload_parses_custom_symbols() -> None:
    options = options_from_payload(
        {
            "symbols": "AAPL MSFT，600519 BTC-USD",
            "title": "Customer",
            "providers": "yfinance",
            "includeNews": False,
            "buildDashboard": True,
        }
    )

    assert options.symbols == ["AAPL", "MSFT", "600519", "BTC-USD"]
    assert options.title == "Customer"
    assert options.providers == ["yfinance"]
    assert options.include_news is False
    assert options.build_dashboard is True
    assert options.assets == []


def test_options_from_payload_prefers_confirmed_portfolio_assets() -> None:
    options = options_from_payload(
        {
            "symbols": "IGNORED",
            "assets": [{"symbol": "600519", "quantity": "2", "cost_basis": "1500", "tags": ["消费"]}],
        }
    )

    assert options.symbols == ["600519.SS"]
    assert options.assets[0]["quantity"] == 2
    assert options.assets[0]["tags"] == ["消费"]


def test_options_from_payload_rejects_empty_symbols() -> None:
    with pytest.raises(ValueError, match="symbol"):
        options_from_payload({"symbols": ""})


def test_extract_portfolio_payload_normalizes_ai_records(monkeypatch) -> None:
    monkeypatch.setattr(
        web,
        "extract_portfolio_from_image",
        lambda image, media_type, settings: [{"symbol": "600519", "quantity": "2", "tags": ["消费"]}],
    )

    result = web._extract_portfolio_payload({"image": "data:image/png;base64,WA=="})

    assert result["assets"] == [{"symbol": "600519.SS", "market": "CN", "quantity": 2.0, "tags": ["消费"]}]


def test_answer_payload_reads_only_generated_json(tmp_path, monkeypatch) -> None:
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "report.json").write_text('{"title":"Pulse","language":"zh-CN"}', encoding="utf-8")
    monkeypatch.setattr(web, "answer_report_question", lambda report, question, settings, language: f"{report['title']}:{question}")

    result = web._answer_payload({"reportPath": "/reports/report.json", "question": "风险？"}, tmp_path)

    assert result == {"answer": "Pulse:风险？"}
