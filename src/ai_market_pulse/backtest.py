from __future__ import annotations

import statistics
from dataclasses import dataclass, field

import pandas as pd

from .config import ScoringSettings
from .indicators import calculate_indicators
from .scoring import score_asset

# Rows of history required before the first scored sample so long windows
# (SMA200) are populated.
_WARMUP_ROWS = 210

_BUCKETS = [(0, 19), (20, 39), (40, 59), (60, 79), (80, 100)]


@dataclass(frozen=True)
class BucketStat:
    bucket: str
    samples: int
    average_forward_return: float | None
    win_rate: float | None


@dataclass(frozen=True)
class SymbolBacktest:
    symbol: str
    samples: int
    correlation: float | None


@dataclass(frozen=True)
class BacktestResult:
    horizon_days: int
    step_days: int
    samples: int
    correlation: float | None
    buckets: list[BucketStat]
    symbols: list[SymbolBacktest] = field(default_factory=list)


def run_backtest(
    histories: dict[str, pd.DataFrame],
    horizon_days: int = 20,
    step_days: int = 5,
    weights: ScoringSettings | None = None,
) -> BacktestResult:
    """Walk each price history, score the signal at sampled points, and
    compare it with the realized forward return over `horizon_days`.

    This validates whether higher scores actually preceded better returns —
    it is a research diagnostic, not a trading system or a promise of profit.
    """
    scores: list[float] = []
    forwards: list[float] = []
    per_symbol: list[SymbolBacktest] = []

    for symbol, history in histories.items():
        symbol_scores: list[float] = []
        symbol_forwards: list[float] = []
        close = history["Close"].astype(float).reset_index(drop=True)
        length = len(history)
        for end in range(_WARMUP_ROWS, length - horizon_days, step_days):
            window = history.iloc[:end]
            metrics = calculate_indicators(window)
            signal = score_asset(metrics, weights)
            entry = float(close.iloc[end - 1])
            exit_price = float(close.iloc[end - 1 + horizon_days])
            if entry <= 0:
                continue
            symbol_scores.append(float(signal.score))
            symbol_forwards.append(exit_price / entry - 1)
        scores.extend(symbol_scores)
        forwards.extend(symbol_forwards)
        per_symbol.append(
            SymbolBacktest(
                symbol=symbol,
                samples=len(symbol_scores),
                correlation=_correlation(symbol_scores, symbol_forwards),
            )
        )

    buckets: list[BucketStat] = []
    for low, high in _BUCKETS:
        member_returns = [
            forward for score, forward in zip(scores, forwards) if low <= score <= high
        ]
        if member_returns:
            buckets.append(
                BucketStat(
                    bucket=f"{low}-{high}",
                    samples=len(member_returns),
                    average_forward_return=sum(member_returns) / len(member_returns),
                    win_rate=sum(1 for value in member_returns if value > 0) / len(member_returns),
                )
            )
        else:
            buckets.append(BucketStat(bucket=f"{low}-{high}", samples=0, average_forward_return=None, win_rate=None))

    return BacktestResult(
        horizon_days=horizon_days,
        step_days=step_days,
        samples=len(scores),
        correlation=_correlation(scores, forwards),
        buckets=buckets,
        symbols=per_symbol,
    )


def format_backtest(result: BacktestResult) -> str:
    lines = [
        f"Backtest: {result.samples} samples, {result.horizon_days}-day forward return, step {result.step_days}.",
        f"Score/forward-return correlation: "
        + (f"{result.correlation:+.3f}" if result.correlation is not None else "n/a"),
        "",
        f"{'Score bucket':<14}{'Samples':>9}{'Avg fwd return':>17}{'Win rate':>11}",
    ]
    for bucket in result.buckets:
        avg = f"{bucket.average_forward_return:+.2%}" if bucket.average_forward_return is not None else "n/a"
        win = f"{bucket.win_rate:.0%}" if bucket.win_rate is not None else "n/a"
        lines.append(f"{bucket.bucket:<14}{bucket.samples:>9}{avg:>17}{win:>11}")
    lines.append("")
    for item in result.symbols:
        corr = f"{item.correlation:+.3f}" if item.correlation is not None else "n/a"
        lines.append(f"  {item.symbol}: {item.samples} samples, correlation {corr}")
    lines.append("")
    lines.append("Research diagnostic only; past scores do not guarantee future returns.")
    return "\n".join(lines)


def _correlation(scores: list[float], forwards: list[float]) -> float | None:
    if len(scores) < 3:
        return None
    if len(set(scores)) < 2 or len(set(forwards)) < 2:
        return None
    try:
        return statistics.correlation(scores, forwards)
    except statistics.StatisticsError:
        return None
