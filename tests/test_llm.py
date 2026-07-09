from __future__ import annotations

from ai_market_pulse.config import LLMSettings
from ai_market_pulse.llm import _read_cache, _render_prompt_template, _write_cache


def test_llm_cache_roundtrip(tmp_path) -> None:
    settings = LLMSettings(cache_enabled=True, cache_dir=str(tmp_path))
    payload = {"model": "test", "messages": [{"role": "user", "content": "hello"}]}

    assert _read_cache(payload, settings) is None
    _write_cache(payload, settings, "cached")

    assert _read_cache(payload, settings) == "cached"


def test_prompt_template_renders_context(tmp_path) -> None:
    prompt = tmp_path / "asset.md"
    prompt.write_text("Context:\n{context}", encoding="utf-8")
    settings = LLMSettings(prompts_dir=str(tmp_path))

    rendered = _render_prompt_template(settings, "asset.md", "fallback", {"context": {"a": 1}})

    assert '"a": 1' in rendered
