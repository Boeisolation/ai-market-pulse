from __future__ import annotations

from ai_market_pulse import market_data
from ai_market_pulse.market_data import match_fund_by_name
from ai_market_pulse.portfolio_import import resolve_fund_records

# Shapes taken from the real 蚂蚁财富 incident: app display names carry extra
# 中证/(QDII)/低波动 decorations and drop 发起/人民币 suffixes.
_DIRECTORY = {
    "021513": ("富国港股通红利精选混合A", "混合型-偏股"),
    "021514": ("富国港股通红利精选混合C", "混合型-偏股"),
    "012348": ("天弘恒生科技ETF联接A", "指数型-海外股票"),
    "012804": ("广发恒生科技ETF联接(QDII)A", "指数型-海外股票"),
    "007751": ("景顺长城沪港深红利成长低波指数A", "指数型-股票"),
    "007760": ("景顺长城沪港深红利成长低波指数C", "指数型-股票"),
    "021875": ("路博迈资源精选股票发起A", "股票型"),
    "002286": ("中银美元债债券(QDII)人民币A", "QDII-纯债"),
    "002287": ("中银美元债债券(QDII)美元", "QDII-纯债"),
    "110011": ("易方达中证500ETF联接A", "指数型-股票"),
    "110022": ("易方达中证800ETF联接A", "指数型-股票"),
    "005827": ("易方达蓝筹精选混合", "混合型-偏股"),
}


def _patch_directory(monkeypatch) -> None:
    monkeypatch.setattr(market_data, "_FUND_DIRECTORY", dict(_DIRECTORY))


def test_match_exact_name(monkeypatch) -> None:
    _patch_directory(monkeypatch)
    assert match_fund_by_name("富国港股通红利精选混合A") == ("021513", "富国港股通红利精选混合A")


def test_match_survives_app_name_decorations(monkeypatch) -> None:
    _patch_directory(monkeypatch)
    # App shows extra (QDII) / 中证 / 低波动 that the directory omits — and the
    # company prefix guard must stop the closer-looking 广发 candidate.
    assert match_fund_by_name("天弘恒生科技ETF联接(QDII)A") == ("012348", "天弘恒生科技ETF联接A")
    assert match_fund_by_name("景顺长城中证沪港深红利成长低波动指数A") == (
        "007751",
        "景顺长城沪港深红利成长低波指数A",
    )
    assert match_fund_by_name("路博迈资源精选股票A") == ("021875", "路博迈资源精选股票发起A")
    assert match_fund_by_name("中银美元债券(QDII)A") == ("002286", "中银美元债债券(QDII)人民币A")


def test_match_respects_share_class_and_digits(monkeypatch) -> None:
    _patch_directory(monkeypatch)
    match = match_fund_by_name("富国港股通红利精选混合C")
    assert match is not None and match[0] == "021514"
    # 500 vs 800 differ by one character; the digit guard must not cross them.
    assert match_fund_by_name("易方达中证500ETF联接A") == ("110011", "易方达中证500ETF联接A")
    assert match_fund_by_name("易方达中证800ETF联接A") == ("110022", "易方达中证800ETF联接A")


def test_match_rejects_unknown_fund(monkeypatch) -> None:
    _patch_directory(monkeypatch)
    # Directory has no close candidate — a blank symbol beats a wrong fund.
    assert match_fund_by_name("易方达港股通红利低波联接A") is None
    assert match_fund_by_name("基金") is None


def test_resolve_corrects_fabricated_code(monkeypatch) -> None:
    _patch_directory(monkeypatch)
    # Real incident: model copied the prompt's example code 005827 onto a
    # totally different fund. The directory check must catch and re-resolve it.
    records = [{"symbol": "005827.OF", "name": "富国港股通红利精选混合A", "market": "CN"}]
    resolved, unresolved = resolve_fund_records(records)
    assert unresolved == []
    assert resolved[0]["symbol"] == "021513.OF"


def test_resolve_fills_missing_symbol_and_keeps_unmatched(monkeypatch) -> None:
    _patch_directory(monkeypatch)
    records = [
        {"symbol": None, "name": "天弘恒生科技ETF联接(QDII)A", "quantity": 100},
        {"symbol": None, "name": "易方达港股通红利低波联接A", "quantity": 5},
        {"symbol": "AAPL", "name": "Apple", "market": "US"},
        {"symbol": "600519", "name": "贵州茅台"},
    ]
    resolved, unresolved = resolve_fund_records(records)
    symbols = [item.get("symbol") for item in resolved]
    assert "012348.OF" in symbols
    assert "AAPL" in symbols and "600519" in symbols
    assert len(unresolved) == 1
    assert unresolved[0]["symbol"] == ""
    assert unresolved[0]["name"] == "易方达港股通红利低波联接A"
    assert unresolved[0]["market"] == "CN"
    assert unresolved[0]["quantity"] == 5


def test_resolve_trusts_consistent_code(monkeypatch) -> None:
    _patch_directory(monkeypatch)
    records = [{"symbol": "005827.OF", "name": "易方达蓝筹精选混合", "market": "CN"}]
    resolved, unresolved = resolve_fund_records(records)
    assert resolved[0]["symbol"] == "005827.OF"
    assert unresolved == []


def test_prompt_forbids_inventing_codes(monkeypatch) -> None:
    from ai_market_pulse import llm
    from ai_market_pulse.config import LLMSettings

    captured: dict[str, list] = {}

    def fake_chat(messages, settings):
        captured["messages"] = messages
        return "[]"

    monkeypatch.setattr(llm, "_chat_completion", fake_chat)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    llm.extract_portfolio_from_image(b"img", "image/png", LLMSettings(enabled=True, model="m"))

    prompt = captured["messages"][0]["content"]
    assert "NEVER invent" in prompt
    assert "set symbol to null" in prompt
    assert "005827" not in prompt  # example codes get copied by the model
