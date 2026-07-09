from __future__ import annotations

import pytest

from ai_market_pulse.web import options_from_payload, render_console_html


def test_render_console_html_contains_visual_symbol_form() -> None:
    html = render_console_html()

    assert "data-run-form" in html
    assert 'name="symbols"' in html
    assert 'value="我的自选股每日分析报告"' in html
    assert 'data-default-en="My Daily Stock Analysis Report"' in html
    assert "/api/analyze" in html
    assert "分析任意股票池" in html


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


def test_options_from_payload_rejects_empty_symbols() -> None:
    with pytest.raises(ValueError, match="symbol"):
        options_from_payload({"symbols": ""})
