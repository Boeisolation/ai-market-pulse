from __future__ import annotations

from collections import defaultdict

from .models import AssetAnalysis, ThemeSummary


def build_theme_summaries(analyses: list[AssetAnalysis]) -> list[ThemeSummary]:
    grouped: dict[str, list[AssetAnalysis]] = defaultdict(list)
    for analysis in analyses:
        if analysis.snapshot.rows <= 0:
            continue
        for tag in _clean_tags(analysis.asset.tags):
            grouped[tag].append(analysis)

    summaries = [_summarize(tag, items) for tag, items in grouped.items()]
    return sorted(
        summaries,
        key=lambda item: (-item.positioned_count, -len(item.symbols), item.tag.casefold()),
    )


def _summarize(tag: str, analyses: list[AssetAnalysis]) -> ThemeSummary:
    positions = [item.position for item in analyses if item.position]
    currencies = {position.currency for position in positions}
    weighted_score = None
    if positions and len(currencies) == 1:
        total_value = sum(abs(position.market_value) for position in positions)
        if total_value:
            scores = {item.asset.symbol: item.signal.score for item in analyses}
            weighted_score = sum(scores[position.symbol] * abs(position.market_value) for position in positions) / total_value

    market_values: dict[str, float] = defaultdict(float)
    allocations: dict[str, float] = defaultdict(float)
    day_pnl: dict[str, float] = defaultdict(float)
    for position in positions:
        market_values[position.currency] += position.market_value
        if position.allocation_pct is not None:
            allocations[position.currency] += position.allocation_pct
        if position.day_pnl is not None:
            day_pnl[position.currency] += position.day_pnl

    return ThemeSummary(
        tag=tag,
        symbols=sorted({item.asset.symbol for item in analyses}),
        average_score=round(sum(item.signal.score for item in analyses) / len(analyses), 2),
        weighted_score=_round(weighted_score),
        return_20d=_average_metric(analyses, "return_20d"),
        return_60d=_average_metric(analyses, "return_60d"),
        relative_return_20d=_average_relative(analyses, "relative_return_20d"),
        relative_return_60d=_average_relative(analyses, "relative_return_60d"),
        high_risk_count=sum(1 for item in analyses if item.signal.risk_level == "high"),
        positioned_count=len(positions),
        market_value_by_currency=_rounded_dict(market_values),
        allocation_by_currency=_rounded_dict(allocations),
        day_pnl_by_currency=_rounded_dict(day_pnl),
    )


def _clean_tags(tags: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for tag in tags:
        value = str(tag).strip()
        key = value.casefold()
        if not value or key == "benchmark" or key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def _average_metric(analyses: list[AssetAnalysis], key: str) -> float | None:
    values = [_number(item.metrics.get(key)) for item in analyses]
    return _average([value for value in values if value is not None])


def _average_relative(analyses: list[AssetAnalysis], key: str) -> float | None:
    values = [
        _number(getattr(item.benchmark, key, None))
        for item in analyses
        if item.benchmark is not None
    ]
    return _average([value for value in values if value is not None])


def _average(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 6)


def _number(value: object) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _round(value: float | None) -> float | None:
    return round(value, 2) if value is not None else None


def _rounded_dict(values: dict[str, float]) -> dict[str, float]:
    return {key: round(value, 6) for key, value in sorted(values.items())}
