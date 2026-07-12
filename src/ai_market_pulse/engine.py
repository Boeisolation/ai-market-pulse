from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime
from zoneinfo import ZoneInfo

from .benchmarks import attach_benchmark_comparisons, build_data_freshness, fetch_benchmarks
from .config import AppConfig, DataSettings
from .group_stats import build_theme_summaries
from .insights import build_insights
from .indicators import calculate_indicators
from .llm import summarize_portfolio_with_llm, summarize_with_llm
from .market_cache import MarketDataCache
from .market_data import MarketDataError, fetch_history
from .models import Asset, AssetAnalysis, DailyReport, DataFreshness, PriceSnapshot
from .news import fetch_news
from .portfolio import enrich_portfolio
from .scoring import score_asset


def run_analysis(config: AppConfig, config_path: str | None = None) -> DailyReport:
    generated_at = datetime.now(ZoneInfo(config.timezone))
    cache = _build_cache(config.data)
    workers = _worker_count(config.data, len(config.assets))

    def analyze(asset: Asset) -> AssetAnalysis:
        try:
            hydrated_asset, snapshot, history = fetch_history(
                asset,
                config.analysis.lookback_days,
                config.data.providers,
                cache=cache,
            )
            metrics = calculate_indicators(history)
            freshness = build_data_freshness(snapshot, generated_at.date(), config.benchmarks.stale_after_days)
            warnings = _warnings(snapshot, config.analysis.min_history_rows, freshness)
            signal = score_asset(metrics, config.scoring)
            news = fetch_news(hydrated_asset, config.news)
            return AssetAnalysis(
                asset=hydrated_asset,
                snapshot=snapshot,
                metrics=metrics,
                signal=signal,
                news=news,
                warnings=warnings,
                freshness=freshness,
            )
        except MarketDataError as exc:
            return _failed_analysis(asset, str(exc))
        except Exception as exc:
            # One asset's unexpected failure must not take down the report.
            return _failed_analysis(asset, f"Unexpected {type(exc).__name__}: {exc}")

    # Per-asset work is dominated by network I/O (quotes + news), so a thread
    # pool gives near-linear speedup. executor.map preserves input order.
    with ThreadPoolExecutor(max_workers=workers) as pool:
        analyses = list(pool.map(analyze, config.assets))

    benchmark_data, benchmark_snapshots = fetch_benchmarks(
        [analysis.asset for analysis in analyses],
        config.benchmarks,
        config.data.providers,
        config.analysis.lookback_days,
        generated_at.date(),
        cache=cache,
        max_workers=workers,
    )
    analyses = attach_benchmark_comparisons(analyses, benchmark_data, config.benchmarks)
    analyses, portfolio = enrich_portfolio(analyses)
    if config.llm.enabled:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            summaries = list(
                pool.map(
                    lambda analysis: summarize_with_llm(analysis, config.llm, config.analysis.language),
                    analyses,
                )
            )
        analyses = [replace(analysis, ai_summary=summary) for analysis, summary in zip(analyses, summaries)]
    report = DailyReport(
        title=config.title,
        generated_at=generated_at,
        timezone=config.timezone,
        language=config.analysis.language,
        analyses=analyses,
        market_brief=_market_brief(analyses),
        portfolio=portfolio,
        themes=build_theme_summaries(analyses),
        insights=build_insights(analyses),
        benchmarks=benchmark_snapshots,
        config_path=config_path,
    )
    if config.llm.enabled:
        report = replace(report, portfolio_ai_summary=summarize_portfolio_with_llm(report, config.llm))
    return report


def _build_cache(data: DataSettings) -> MarketDataCache | None:
    if not data.cache_enabled:
        return None
    return MarketDataCache(data.cache_dir, ttl_minutes=data.cache_ttl_minutes)


def _worker_count(data: DataSettings, task_count: int) -> int:
    return max(1, min(data.max_workers, max(task_count, 1)))


def _warnings(snapshot: PriceSnapshot, min_rows: int, freshness: DataFreshness | None = None) -> list[str]:
    warnings: list[str] = []
    if snapshot.rows < min_rows:
        warnings.append(f"Only {snapshot.rows} rows of price history are available.")
    if snapshot.change_pct is not None and abs(snapshot.change_pct) > 0.08:
        warnings.append("Single-day move is unusually large; verify corporate actions or data quality.")
    if freshness and freshness.status in {"stale", "missing", "unknown"}:
        warnings.append(f"Data freshness: {freshness.message}")
    return warnings


def _failed_analysis(asset, message: str) -> AssetAnalysis:
    freshness = DataFreshness(
        latest_date="",
        age_days=None,
        source=None,
        rows=0,
        status="missing",
        message=message,
    )
    snapshot = PriceSnapshot(
        symbol=asset.symbol,
        name=asset.name or asset.symbol,
        currency=asset.currency,
        last_close=0,
        previous_close=None,
        change_pct=None,
        start_date="",
        end_date="",
        rows=0,
    )
    return AssetAnalysis(
        asset=asset,
        snapshot=snapshot,
        metrics={},
        signal=score_asset({}),
        news=[],
        ai_summary=None,
        warnings=[message],
        freshness=freshness,
    )


def _market_brief(analyses: list[AssetAnalysis]) -> str:
    valid = [item for item in analyses if item.snapshot.rows > 0]
    if not valid:
        return "No valid market data was available."
    average_score = sum(item.signal.score for item in valid) / len(valid)
    high_risk = sum(1 for item in valid if item.signal.risk_level == "high")
    constructive = sum(1 for item in valid if item.signal.score >= 60)
    return (
        f"{len(valid)} assets analyzed. Average signal score is {average_score:.1f}/100. "
        f"{constructive} assets are constructive or watch-bullish. "
        f"{high_risk} assets are flagged as high risk."
    )
