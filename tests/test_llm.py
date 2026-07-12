from __future__ import annotations

import io
import json
import urllib.error

from ai_market_pulse import llm
from ai_market_pulse.config import LLMSettings
from ai_market_pulse.llm import _chat_completion, _parse_json, _read_cache, _render_prompt_template, _write_cache


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = json.dumps(payload).encode("utf-8")

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None

    def read(self) -> bytes:
        return self._payload


def test_chat_completion_retries_on_429_then_succeeds(tmp_path, monkeypatch) -> None:
    attempts = {"count": 0}

    def fake_urlopen(request, timeout):
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise urllib.error.HTTPError(request.full_url, 429, "Too Many Requests", None, io.BytesIO(b""))
        return _FakeResponse({"choices": [{"message": {"content": "recovered"}}]})

    monkeypatch.setattr(llm.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(llm.time, "sleep", lambda seconds: None)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    settings = LLMSettings(enabled=True, model="test-model", cache_enabled=True, cache_dir=str(tmp_path))
    content = _chat_completion([{"role": "user", "content": "hi"}], settings)

    assert content == "recovered"
    assert attempts["count"] == 3


def test_chat_completion_gives_up_on_auth_error(tmp_path, monkeypatch) -> None:
    attempts = {"count": 0}

    def fake_urlopen(request, timeout):
        attempts["count"] += 1
        raise urllib.error.HTTPError(request.full_url, 401, "Unauthorized", None, io.BytesIO(b""))

    monkeypatch.setattr(llm.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(llm.time, "sleep", lambda seconds: None)
    monkeypatch.setenv("OPENAI_API_KEY", "bad-key")

    settings = LLMSettings(enabled=True, model="test-model", cache_enabled=False, cache_dir=str(tmp_path))
    content = _chat_completion([{"role": "user", "content": "hi"}], settings)

    assert content is None
    assert attempts["count"] == 1  # 401 is not retryable


def test_llm_cache_roundtrip(tmp_path) -> None:
    settings = LLMSettings(cache_enabled=True, cache_dir=str(tmp_path))
    payload = {"model": "test", "messages": [{"role": "user", "content": "hello"}]}

    assert _read_cache(payload, settings) is None
    _write_cache(payload, settings, "cached")

    assert _read_cache(payload, settings) == "cached"


def test_parse_json_accepts_fenced_vision_response() -> None:
    assert _parse_json('```json\n{"assets":[{"symbol":"AAPL"}]}\n```')["assets"][0]["symbol"] == "AAPL"


def test_prompt_template_renders_context(tmp_path) -> None:
    prompt = tmp_path / "asset.md"
    prompt.write_text("Context:\n{context}", encoding="utf-8")
    settings = LLMSettings(prompts_dir=str(tmp_path))

    rendered = _render_prompt_template(settings, "asset.md", "fallback", {"context": {"a": 1}})

    assert '"a": 1' in rendered
