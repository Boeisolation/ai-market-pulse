from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class Asset:
    symbol: str
    name: str | None = None
    market: str = "US"
    currency: str | None = None
    tags: list[str] = field(default_factory=list)
    quantity: float | None = None
    cost_basis: float | None = None
    note: str | None = None


@dataclass(frozen=True)
class NewsItem:
    title: str
    link: str
    source: str | None = None
    published: str | None = None


@dataclass(frozen=True)
class PriceSnapshot:
    symbol: str
    name: str
    currency: str | None
    last_close: float
    previous_close: float | None
    change_pct: float | None
    start_date: str
    end_date: str
    rows: int
    source: str | None = None


@dataclass(frozen=True)
class DataFreshness:
    latest_date: str
    age_days: int | None
    source: str | None
    rows: int
    status: str
    message: str


@dataclass(frozen=True)
class BenchmarkSnapshot:
    symbol: str
    name: str
    market: str
    currency: str | None
    last_close: float | None
    change_pct: float | None
    return_20d: float | None
    return_60d: float | None
    source: str | None
    freshness: DataFreshness


@dataclass(frozen=True)
class BenchmarkComparison:
    symbol: str
    name: str
    market: str
    source: str | None
    latest_date: str
    asset_return_20d: float | None
    benchmark_return_20d: float | None
    relative_return_20d: float | None
    asset_return_60d: float | None
    benchmark_return_60d: float | None
    relative_return_60d: float | None
    verdict: str


@dataclass(frozen=True)
class SignalScore:
    score: int
    stance: str
    risk_level: str
    reasons: list[str]


@dataclass(frozen=True)
class PositionMetrics:
    symbol: str
    currency: str
    quantity: float
    cost_basis: float | None
    cost_value: float | None
    market_value: float
    day_pnl: float | None
    unrealized_pnl: float | None
    unrealized_pnl_pct: float | None
    allocation_pct: float | None = None


@dataclass(frozen=True)
class PortfolioSummary:
    currency: str
    positions: int
    market_value: float
    cost_value: float | None
    day_pnl: float | None
    unrealized_pnl: float | None
    unrealized_pnl_pct: float | None


@dataclass(frozen=True)
class ThemeSummary:
    tag: str
    symbols: list[str]
    average_score: float
    weighted_score: float | None
    return_20d: float | None
    return_60d: float | None
    relative_return_20d: float | None
    relative_return_60d: float | None
    high_risk_count: int
    positioned_count: int
    market_value_by_currency: dict[str, float] = field(default_factory=dict)
    allocation_by_currency: dict[str, float] = field(default_factory=dict)
    day_pnl_by_currency: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class HistoryPoint:
    date: str
    symbol: str
    close: float | None
    score: int
    stance: str
    risk_level: str
    currency: str | None = None
    change_pct: float | None = None
    market_value: float | None = None
    day_pnl: float | None = None
    unrealized_pnl: float | None = None
    unrealized_pnl_pct: float | None = None
    benchmark_symbol: str | None = None
    relative_return_20d: float | None = None
    relative_return_60d: float | None = None
    latest_data_date: str | None = None
    data_age_days: int | None = None
    freshness_status: str | None = None
    tags: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RiskFinding:
    symbol: str
    severity: str
    rule: str
    message: str
    value: float | str | None = None


@dataclass(frozen=True)
class AttentionItem:
    symbol: str
    priority: int
    reason: str
    has_position: bool
    risk_level: str
    day_pnl: float | None = None
    unrealized_pnl: float | None = None


@dataclass(frozen=True)
class ContributionItem:
    symbol: str
    currency: str
    day_pnl: float | None
    unrealized_pnl: float | None
    market_value: float | None
    allocation_pct: float | None


@dataclass(frozen=True)
class ChecklistItem:
    text: str
    priority: str = "normal"
    symbol: str | None = None


@dataclass(frozen=True)
class InsightSummary:
    attention: list[AttentionItem] = field(default_factory=list)
    risk_findings: list[RiskFinding] = field(default_factory=list)
    day_contributors: list[ContributionItem] = field(default_factory=list)
    unrealized_contributors: list[ContributionItem] = field(default_factory=list)
    checklist: list[ChecklistItem] = field(default_factory=list)


@dataclass(frozen=True)
class AssetAnalysis:
    asset: Asset
    snapshot: PriceSnapshot
    metrics: dict[str, float | int | str | None]
    signal: SignalScore
    news: list[NewsItem]
    position: PositionMetrics | None = None
    ai_summary: str | None = None
    warnings: list[str] = field(default_factory=list)
    benchmark: BenchmarkComparison | None = None
    freshness: DataFreshness | None = None


@dataclass(frozen=True)
class DailyReport:
    title: str
    generated_at: datetime
    timezone: str
    language: str
    analyses: list[AssetAnalysis]
    market_brief: str
    portfolio: list[PortfolioSummary] = field(default_factory=list)
    themes: list[ThemeSummary] = field(default_factory=list)
    history: dict[str, list[HistoryPoint]] = field(default_factory=dict)
    insights: InsightSummary = field(default_factory=InsightSummary)
    benchmarks: list[BenchmarkSnapshot] = field(default_factory=list)
    portfolio_ai_summary: str | None = None
    config_path: str | None = None

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "generated_at": self.generated_at.isoformat(),
            "timezone": self.timezone,
            "language": self.language,
            "market_brief": self.market_brief,
            "portfolio": [item.__dict__ for item in self.portfolio],
            "themes": [item.__dict__ for item in self.themes],
            "history": {
                symbol: [point.__dict__ for point in points]
                for symbol, points in self.history.items()
            },
            "insights": {
                "attention": [item.__dict__ for item in self.insights.attention],
                "risk_findings": [item.__dict__ for item in self.insights.risk_findings],
                "day_contributors": [item.__dict__ for item in self.insights.day_contributors],
                "unrealized_contributors": [item.__dict__ for item in self.insights.unrealized_contributors],
                "checklist": [item.__dict__ for item in self.insights.checklist],
            },
            "benchmarks": [
                {
                    **item.__dict__,
                    "freshness": item.freshness.__dict__,
                }
                for item in self.benchmarks
            ],
            "portfolio_ai_summary": self.portfolio_ai_summary,
            "analyses": [
                {
                    "asset": analysis.asset.__dict__,
                    "snapshot": analysis.snapshot.__dict__,
                    "metrics": analysis.metrics,
                    "signal": analysis.signal.__dict__,
                    "position": analysis.position.__dict__ if analysis.position else None,
                    "news": [item.__dict__ for item in analysis.news],
                    "ai_summary": analysis.ai_summary,
                    "warnings": analysis.warnings,
                    "benchmark": analysis.benchmark.__dict__ if analysis.benchmark else None,
                    "freshness": analysis.freshness.__dict__ if analysis.freshness else None,
                }
                for analysis in self.analyses
            ],
        }
