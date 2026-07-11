from __future__ import annotations

import json
import threading
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from typing import Iterable

from .models import DailyReport, HistoryPoint


_LOCKS: dict[str, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()


def load_history(path: str | Path) -> list[HistoryPoint]:
    history_path = Path(path)
    if not history_path.exists():
        return []

    records: list[HistoryPoint] = []
    for line in history_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
            records.append(HistoryPoint(**_filter_history(raw)))
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
    return records


def attach_history(report: DailyReport, records: Iterable[HistoryPoint], max_points: int = 30) -> DailyReport:
    merged = list(records) + records_from_report(report)
    by_key: dict[tuple[str, str], HistoryPoint] = {}
    for point in merged:
        by_key[(point.symbol, point.date)] = point

    by_symbol: dict[str, list[HistoryPoint]] = {}
    for point in by_key.values():
        by_symbol.setdefault(point.symbol, []).append(point)

    trimmed = {
        symbol: sorted(points, key=lambda item: item.date)[-max_points:]
        for symbol, points in by_symbol.items()
    }
    return replace(report, history=trimmed)


def append_history(path: str | Path, report: DailyReport) -> None:
    history_path = Path(path)
    history_path.parent.mkdir(parents=True, exist_ok=True)
    with _history_lock(history_path):
        merged = load_history(history_path) + records_from_report(report)
        by_key = {(record.symbol, record.date): record for record in merged}
        ordered = sorted(by_key.values(), key=lambda record: (record.date, record.symbol))
        temporary = history_path.with_suffix(history_path.suffix + ".tmp")
        temporary.write_text(
            "".join(json.dumps(record.__dict__, ensure_ascii=False, sort_keys=True) + "\n" for record in ordered),
            encoding="utf-8",
        )
        temporary.replace(history_path)


def records_from_report(report: DailyReport) -> list[HistoryPoint]:
    report_date = report.generated_at.date().isoformat()
    records: list[HistoryPoint] = []
    for analysis in report.analyses:
        records.append(
            HistoryPoint(
                date=report_date,
                symbol=analysis.asset.symbol,
                close=analysis.snapshot.last_close if analysis.snapshot.rows > 0 else None,
                score=analysis.signal.score,
                stance=analysis.signal.stance,
                risk_level=analysis.signal.risk_level,
                currency=analysis.position.currency if analysis.position else analysis.snapshot.currency,
                change_pct=analysis.snapshot.change_pct,
                market_value=analysis.position.market_value if analysis.position else None,
                day_pnl=analysis.position.day_pnl if analysis.position else None,
                unrealized_pnl=analysis.position.unrealized_pnl if analysis.position else None,
                unrealized_pnl_pct=analysis.position.unrealized_pnl_pct if analysis.position else None,
                benchmark_symbol=analysis.benchmark.symbol if analysis.benchmark else None,
                relative_return_20d=analysis.benchmark.relative_return_20d if analysis.benchmark else None,
                relative_return_60d=analysis.benchmark.relative_return_60d if analysis.benchmark else None,
                latest_data_date=analysis.freshness.latest_date if analysis.freshness else analysis.snapshot.end_date,
                data_age_days=analysis.freshness.age_days if analysis.freshness else None,
                freshness_status=analysis.freshness.status if analysis.freshness else None,
                tags=list(analysis.asset.tags),
            )
        )
    return records


def _filter_history(raw: dict) -> dict:
    allowed = set(HistoryPoint.__dataclass_fields__.keys())
    filtered = {key: raw.get(key) for key in allowed if key in raw}
    filtered["tags"] = list(raw.get("tags") or [])
    return filtered


@contextmanager
def _history_lock(path: Path):
    key = str(path.resolve())
    with _LOCKS_GUARD:
        thread_lock = _LOCKS.setdefault(key, threading.Lock())
    with thread_lock:
        lock_path = path.with_suffix(path.suffix + ".lock")
        with lock_path.open("a+", encoding="utf-8") as lock_file:
            try:
                import fcntl

                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            except ImportError:
                fcntl = None
            try:
                yield
            finally:
                if fcntl is not None:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
