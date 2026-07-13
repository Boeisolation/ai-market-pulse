from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import time
from dataclasses import replace
from pathlib import Path
import urllib.error
import urllib.request
from typing import Any

from .config import LLMSettings
from .models import AssetAnalysis, DailyReport

logger = logging.getLogger(__name__)

_RETRYABLE_STATUS = {429, 500, 502, 503, 504}
_MAX_ATTEMPTS = 3


def summarize_with_llm(analysis: AssetAnalysis, settings: LLMSettings, language: str) -> str | None:
    user_prompt = _render_prompt_template(
        settings,
        "asset.md",
        _asset_prompt(analysis, language),
        {
            "context": _asset_context(analysis, language),
        },
    )
    messages = [
        {
            "role": "system",
            "content": _system_prompt(settings, "asset_system.md", "You are a cautious market research analyst. Write concise research notes, avoid promises, avoid financial advice, and emphasize risk controls."),
        },
        {
            "role": "user",
            "content": user_prompt,
        },
    ]
    return _chat_completion(messages, settings)


def summarize_portfolio_with_llm(report: DailyReport, settings: LLMSettings) -> str | None:
    user_prompt = _render_prompt_template(
        settings,
        "portfolio.md",
        _portfolio_prompt(report),
        {
            "context": _portfolio_context(report),
        },
    )
    messages = [
        {
            "role": "system",
            "content": _system_prompt(settings, "portfolio_system.md", "You are a cautious portfolio research analyst. Your job is to summarize risk, position impact, and watch items. Do not give buy/sell instructions."),
        },
        {
            "role": "user",
            "content": user_prompt,
        },
    ]
    return _chat_completion(messages, settings)


def _vision_settings(settings: LLMSettings) -> LLMSettings:
    """Route image requests to the vision overrides when any are configured."""
    if not (settings.vision_base_url or settings.vision_model or settings.vision_api_key_env):
        return settings
    return replace(
        settings,
        base_url=settings.vision_base_url or settings.base_url,
        model=settings.vision_model or settings.model,
        api_key_env=settings.vision_api_key_env or settings.api_key_env,
    )


def extract_portfolio_from_image(
    image: bytes,
    media_type: str,
    settings: LLMSettings,
) -> list[dict[str, Any]]:
    _require_llm(settings)
    settings = _vision_settings(settings)
    if media_type not in {"image/png", "image/jpeg", "image/webp"}:
        raise ValueError("Portfolio image must be PNG, JPEG, or WebP.")
    encoded = base64.b64encode(image).decode("ascii")
    messages: list[dict[str, Any]] = [
        {
            "role": "system",
            "content": (
                "Extract portfolio holdings from a brokerage or fund-app screenshot. Return JSON only as "
                '{"assets":[{"symbol":"AAPL","name":"Apple","market":"US","quantity":10,'
                '"cost_basis":185,"tags":[]}]}. This is strict transcription: NEVER invent any value that '
                "is not visible in the image — no guessed codes, quantities, or costs; use null instead. "
                "Mainland China rules: exchange-listed stocks keep the bare six-digit code. "
                "OTC mutual funds (场外基金) use the six-digit fund code with suffix .OF and market CN, but "
                "ONLY when the code is actually visible; fund-app holding lists (支付宝/蚂蚁财富, 天天基金, "
                "bank wealth apps) usually show names without codes — then set symbol to null and copy the "
                "exact fund name into name. Recognize funds by context: fund names typically contain "
                "混合, 债券, 指数, 股票型, 联接, QDII, FOF, 增强 or 持有期. "
                "Money-market funds (货币基金, e.g. 余额宝) are cash equivalents: skip them entirely. "
                "Amounts labelled 金额/市值/持有金额 are position values, not share counts: leave quantity "
                "null unless 份额/持有份额 is explicitly shown."
            ),
        },
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Read every visible holding. Ignore cash, account numbers, totals, and buttons."},
                {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{encoded}"}},
            ],
        },
    ]
    content = _chat_completion(messages, settings)
    if not content:
        raise RuntimeError("The AI provider did not return a portfolio extraction.")
    parsed = _parse_json(content)
    assets = parsed.get("assets") if isinstance(parsed, dict) else parsed
    if not isinstance(assets, list):
        raise RuntimeError("The AI response did not contain an assets list.")
    return [item for item in assets if isinstance(item, dict)]


def answer_report_question(
    report: dict[str, Any],
    question: str,
    settings: LLMSettings,
    language: str = "zh-CN",
) -> str:
    _require_llm(settings)
    clean_question = question.strip()
    if not clean_question:
        raise ValueError("Enter a question about the report.")
    context = _report_question_context(report)
    messages: list[dict[str, Any]] = [
        {
            "role": "system",
            "content": (
                "You answer questions using only the supplied AI Market Pulse report JSON. "
                "Cite concrete symbols, scores, returns, risk reasons, and freshness fields. "
                "If the report lacks evidence, say so. Do not issue buy/sell orders or promise returns. "
                f"Reply in {'Chinese' if language.lower().startswith('zh') else 'English'}."
            ),
        },
        {
            "role": "user",
            "content": f"Question: {clean_question}\n\nReport context:\n{json.dumps(context, ensure_ascii=False)}",
        },
    ]
    content = _chat_completion(messages, settings)
    if not content:
        raise RuntimeError("The AI provider did not return an answer.")
    return content


def _chat_completion(messages: list[dict[str, Any]], settings: LLMSettings) -> str | None:
    if not settings.enabled:
        return None
    api_key = os.getenv(settings.api_key_env)
    if not api_key or not settings.model:
        return None

    payload = {
        "model": settings.model,
        "temperature": settings.temperature,
        "messages": messages,
    }
    cached = _read_cache(payload, settings)
    if cached is not None:
        return cached
    body = json.dumps(payload).encode("utf-8")
    url = settings.base_url.rstrip("/") + "/chat/completions"

    result: dict[str, Any] | None = None
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        request = urllib.request.Request(
            url,
            data=body,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "ai-market-pulse/0.1",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=settings.timeout_seconds) as response:
                result = json.loads(response.read().decode("utf-8"))
            break
        except urllib.error.HTTPError as exc:
            if exc.code in _RETRYABLE_STATUS and attempt < _MAX_ATTEMPTS:
                delay = 2 ** (attempt - 1)
                logger.warning("LLM request got HTTP %s; retrying in %ss (attempt %s/%s).", exc.code, delay, attempt, _MAX_ATTEMPTS)
                time.sleep(delay)
                continue
            logger.warning("LLM request failed: HTTP %s from %s. Check the API key, model, and quota.", exc.code, url)
            return None
        except Exception as exc:
            if attempt < _MAX_ATTEMPTS:
                delay = 2 ** (attempt - 1)
                logger.warning("LLM request error (%s); retrying in %ss (attempt %s/%s).", exc, delay, attempt, _MAX_ATTEMPTS)
                time.sleep(delay)
                continue
            logger.warning("LLM request failed after %s attempts: %s", _MAX_ATTEMPTS, exc)
            return None
    if result is None:
        return None

    content = _extract_message(result)
    if content:
        _write_cache(payload, settings, content)
    else:
        logger.warning("LLM response from %s contained no message content.", url)
    return content


def _require_llm(settings: LLMSettings) -> None:
    if not settings.enabled:
        raise RuntimeError("AI is disabled.")
    if not os.getenv(settings.api_key_env):
        raise RuntimeError(f"{settings.api_key_env} is not configured.")
    if not settings.model:
        raise RuntimeError("OPENAI_MODEL or llm.model is not configured.")


def _parse_json(content: str) -> Any:
    text = content.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        text = text.rsplit("```", 1)[0].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        starts = [index for index in (text.find("{"), text.find("[")) if index >= 0]
        if not starts:
            raise RuntimeError("The AI response was not valid JSON.")
        start = min(starts)
        end = max(text.rfind("}"), text.rfind("]"))
        if end < start:
            raise RuntimeError("The AI response was not valid JSON.")
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise RuntimeError("The AI response was not valid JSON.") from exc


def _report_question_context(report: dict[str, Any]) -> dict[str, Any]:
    analyses = []
    for item in report.get("analyses", [])[:80]:
        if not isinstance(item, dict):
            continue
        analyses.append(
            {
                "asset": item.get("asset"),
                "snapshot": item.get("snapshot"),
                "metrics": item.get("metrics"),
                "signal": item.get("signal"),
                "position": item.get("position"),
                "benchmark": item.get("benchmark"),
                "freshness": item.get("freshness"),
                "warnings": item.get("warnings"),
                "news": (item.get("news") or [])[:3],
            }
        )
    return {
        "title": report.get("title"),
        "generated_at": report.get("generated_at"),
        "market_brief": report.get("market_brief"),
        "portfolio": report.get("portfolio"),
        "themes": report.get("themes"),
        "insights": report.get("insights"),
        "benchmarks": report.get("benchmarks"),
        "analyses": analyses,
    }


def _asset_context(analysis: AssetAnalysis, language: str) -> dict[str, Any]:
    return {
        "language": language,
        "asset": analysis.asset.__dict__,
        "snapshot": analysis.snapshot.__dict__,
        "metrics": analysis.metrics,
        "signal": analysis.signal.__dict__,
        "position": analysis.position.__dict__ if analysis.position else None,
        "benchmark": analysis.benchmark.__dict__ if analysis.benchmark else None,
        "freshness": analysis.freshness.__dict__ if analysis.freshness else None,
        "news": [item.__dict__ for item in analysis.news[:5]],
        "warnings": analysis.warnings,
    }


def _asset_prompt(analysis: AssetAnalysis, language: str) -> str:
    context = _asset_context(analysis, language)
    return (
        "Create a daily market note from the JSON context below. "
        "Use 4 short bullets: key move, technical setup, news/risk, watch plan. "
        "Do not tell the reader to buy or sell.\n\n"
        + json.dumps(context, ensure_ascii=False)
    )


def _portfolio_context(report: DailyReport) -> dict[str, Any]:
    return {
        "language": report.language,
        "generated_at": report.generated_at.isoformat(),
        "market_brief": report.market_brief,
        "portfolio": [item.__dict__ for item in report.portfolio],
        "themes": [item.__dict__ for item in report.themes],
        "benchmarks": [
            {
                **item.__dict__,
                "freshness": item.freshness.__dict__,
            }
            for item in report.benchmarks
        ],
        "insights": {
            "attention": [item.__dict__ for item in report.insights.attention],
            "risk_findings": [item.__dict__ for item in report.insights.risk_findings[:20]],
            "day_contributors": [item.__dict__ for item in report.insights.day_contributors],
            "unrealized_contributors": [item.__dict__ for item in report.insights.unrealized_contributors],
            "checklist": [item.__dict__ for item in report.insights.checklist],
        },
        "assets": [
            {
                "symbol": analysis.asset.symbol,
                "name": analysis.snapshot.name,
                "currency": analysis.snapshot.currency,
                "close": analysis.snapshot.last_close,
                "change_pct": analysis.snapshot.change_pct,
                "data_source": analysis.snapshot.source,
                "score": analysis.signal.score,
                "stance": analysis.signal.stance,
                "risk_level": analysis.signal.risk_level,
                "position": analysis.position.__dict__ if analysis.position else None,
                "benchmark": analysis.benchmark.__dict__ if analysis.benchmark else None,
                "freshness": analysis.freshness.__dict__ if analysis.freshness else None,
                "key_reasons": analysis.signal.reasons[:4],
                "warnings": analysis.warnings,
                "news": [item.__dict__ for item in analysis.news[:3]],
            }
            for analysis in report.analyses
        ],
    }


def _portfolio_prompt(report: DailyReport) -> str:
    context = _portfolio_context(report)
    return (
        "Create a portfolio-level daily research brief from the JSON context below. "
        "Use these sections with short bullets: Portfolio state, Largest risks, Notable opportunities, "
        "Data points to verify, Tomorrow watchlist. Avoid buy/sell instructions and avoid guaranteed outcomes.\n\n"
        + json.dumps(context, ensure_ascii=False)
    )


def _system_prompt(settings: LLMSettings, file_name: str, fallback: str) -> str:
    if settings.prompts_dir:
        path = Path(settings.prompts_dir) / file_name
        if path.exists():
            return path.read_text(encoding="utf-8").strip()
    return fallback


def _render_prompt_template(
    settings: LLMSettings,
    file_name: str,
    fallback: str,
    values: dict[str, Any],
) -> str:
    if not settings.prompts_dir:
        return fallback
    path = Path(settings.prompts_dir) / file_name
    if not path.exists():
        return fallback
    template = path.read_text(encoding="utf-8")
    rendered_values = {
        key: json.dumps(value, ensure_ascii=False, indent=2) if not isinstance(value, str) else value
        for key, value in values.items()
    }
    return template.format(**rendered_values)


def _cache_key(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _read_cache(payload: dict[str, Any], settings: LLMSettings) -> str | None:
    if not settings.cache_enabled:
        return None
    path = Path(settings.cache_dir) / f"{_cache_key(payload)}.txt"
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def _write_cache(payload: dict[str, Any], settings: LLMSettings, content: str) -> None:
    if not settings.cache_enabled:
        return
    path = Path(settings.cache_dir) / f"{_cache_key(payload)}.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _extract_message(result: dict[str, Any]) -> str | None:
    choices = result.get("choices") or []
    if not choices:
        return None
    message = choices[0].get("message") or {}
    content = message.get("content")
    if not content:
        return None
    return str(content).strip()
