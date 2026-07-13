from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .models import Asset, is_otc_fund_symbol


ENV_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)(?::-(.*?))?\}")


@dataclass(frozen=True)
class LLMSettings:
    enabled: bool = False
    base_url: str = "https://api.openai.com/v1"
    api_key_env: str = "OPENAI_API_KEY"
    model: str | None = None
    temperature: float = 0.2
    timeout_seconds: int = 45
    cache_enabled: bool = True
    cache_dir: str = "data/ai-cache"
    prompts_dir: str | None = None
    # Optional overrides for image tasks (screenshot import). Text-only
    # providers such as DeepSeek cannot accept images, so vision requests can
    # be routed to a different endpoint/model/key; unset fields fall back to
    # the main settings above.
    vision_base_url: str | None = None
    vision_model: str | None = None
    vision_api_key_env: str | None = None


@dataclass(frozen=True)
class NewsSettings:
    enabled: bool = True
    items_per_asset: int = 5
    language: str = "en-US"
    region: str = "US"
    lookback_days: int = 2


@dataclass(frozen=True)
class AnalysisSettings:
    lookback_days: int = 220
    language: str = "zh-CN"
    risk_free_rate: float = 0.02
    min_history_rows: int = 45


@dataclass(frozen=True)
class DataSettings:
    providers: list[str] = field(default_factory=lambda: ["akshare", "akshare_fund", "yfinance"])
    cache_enabled: bool = True
    cache_dir: str = "data/market-cache"
    cache_ttl_minutes: int = 30
    max_workers: int = 8


@dataclass(frozen=True)
class BenchmarkSettings:
    enabled: bool = True
    symbols: list[str] = field(default_factory=lambda: ["SPY", "QQQ", "000300.SS", "^HSI"])
    default_by_market: dict[str, str] = field(
        default_factory=lambda: {
            "US": "SPY",
            "CN": "000300.SS",
            "HK": "^HSI",
            "CRYPTO": "BTC-USD",
        }
    )
    compare: dict[str, str] = field(default_factory=dict)
    names: dict[str, str] = field(
        default_factory=lambda: {
            "SPY": "S&P 500 ETF",
            "QQQ": "Nasdaq 100 ETF",
            "000300.SS": "CSI 300",
            "399300.SZ": "CSI 300",
            "^HSI": "Hang Seng Index",
            "BTC-USD": "Bitcoin",
        }
    )
    stale_after_days: int = 4


@dataclass(frozen=True)
class ScoringSettings:
    """Point weights applied by score_asset. Defaults reproduce the original
    hardcoded model, so omitting the `scoring` config section changes nothing."""

    sma20_above: int = 8
    sma20_below: int = 6
    sma50_above: int = 8
    sma50_below: int = 7
    sma200_above: int = 5
    sma200_below: int = 8
    trend_alignment: int = 5
    trend_misalignment: int = 4
    rsi_balanced: int = 6
    rsi_soft: int = 1
    rsi_oversold: int = 3
    rsi_strong: int = 2
    rsi_overheated: int = 7
    macd_above: int = 5
    macd_below: int = 4
    ret20_strong: int = 5
    ret20_weak: int = 6
    ret60_strong: int = 4
    ret60_weak: int = 5
    drawdown_large: int = 8
    drawdown_medium: int = 4
    atr_elevated: int = 4
    volume_confirmation: int = 3


@dataclass(frozen=True)
class AlertSettings:
    enabled: bool = False
    score_change: int = 10
    daily_move: float = 0.05
    relative_20d_drop: float = 0.05
    risk_upgrade: bool = True
    stale_data: bool = True


@dataclass(frozen=True)
class NotificationTarget:
    type: str
    name: str | None = None
    enabled: bool = True
    settings: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AppConfig:
    title: str
    timezone: str
    assets: list[Asset]
    analysis: AnalysisSettings = field(default_factory=AnalysisSettings)
    data: DataSettings = field(default_factory=DataSettings)
    benchmarks: BenchmarkSettings = field(default_factory=BenchmarkSettings)
    news: NewsSettings = field(default_factory=NewsSettings)
    llm: LLMSettings = field(default_factory=LLMSettings)
    scoring: ScoringSettings = field(default_factory=ScoringSettings)
    alerts: AlertSettings = field(default_factory=AlertSettings)
    notifications: list[NotificationTarget] = field(default_factory=list)


def load_config(path: str | Path) -> AppConfig:
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    return load_config_from_mapping(raw)


def load_config_from_mapping(raw: dict[str, Any]) -> AppConfig:
    raw = _expand_env(raw)
    assets = [_parse_asset(item) for item in raw.get("assets", [])]
    if not assets:
        raise ValueError("Config must define at least one asset.")

    analysis_raw = raw.get("analysis", {}) or {}
    data_raw = raw.get("data", {}) or {}
    benchmarks_raw = raw.get("benchmarks", {}) or {}
    news_raw = raw.get("news", {}) or {}
    llm_raw = raw.get("llm", {}) or {}
    scoring_raw = raw.get("scoring", {}) or {}
    alerts_raw = raw.get("alerts", {}) or {}

    return AppConfig(
        title=raw.get("title", "AI Market Pulse"),
        timezone=raw.get("timezone", "America/Los_Angeles"),
        assets=assets,
        analysis=AnalysisSettings(**_filter_dataclass(AnalysisSettings, analysis_raw)),
        data=DataSettings(**_filter_dataclass(DataSettings, data_raw)),
        benchmarks=BenchmarkSettings(**_filter_dataclass(BenchmarkSettings, benchmarks_raw)),
        news=NewsSettings(**_filter_dataclass(NewsSettings, news_raw)),
        llm=LLMSettings(**_filter_dataclass(LLMSettings, llm_raw)),
        scoring=ScoringSettings(**_filter_dataclass(ScoringSettings, scoring_raw)),
        alerts=AlertSettings(**_filter_dataclass(AlertSettings, alerts_raw)),
        notifications=[
            NotificationTarget(
                type=item["type"],
                name=item.get("name"),
                enabled=item.get("enabled", True),
                settings={k: v for k, v in item.items() if k not in {"type", "name", "enabled"}},
            )
            for item in raw.get("notifications", []) or []
        ],
    )


def _parse_asset(item: dict[str, Any] | str) -> Asset:
    if isinstance(item, str):
        return Asset(symbol=item, market=_default_market(item))
    return Asset(
        symbol=item["symbol"],
        name=item.get("name"),
        market=item.get("market", _default_market(item["symbol"])),
        currency=item.get("currency"),
        tags=list(item.get("tags", []) or []),
        quantity=item.get("quantity"),
        cost_basis=item.get("cost_basis"),
        note=item.get("note"),
    )


def _default_market(symbol: str) -> str:
    # OTC funds (`.OF`) are mainland-only; without this a bare string entry
    # would default to "US" and be benchmarked against SPY.
    return "CN" if is_otc_fund_symbol(str(symbol)) else "US"


def _filter_dataclass(cls: type, values: dict[str, Any]) -> dict[str, Any]:
    fields = set(cls.__dataclass_fields__.keys())
    return {key: value for key, value in values.items() if key in fields}


def _expand_env(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _expand_env(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_expand_env(item) for item in value]
    if isinstance(value, str):
        return ENV_PATTERN.sub(lambda match: os.getenv(match.group(1), match.group(2) or ""), value)
    return value
