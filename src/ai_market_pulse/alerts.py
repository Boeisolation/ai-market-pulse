from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import AlertSettings
from .models import DailyReport


RISK_RANK = {"low": 1, "medium": 2, "high": 3}


@dataclass(frozen=True)
class AlertEvent:
    symbol: str
    kind: str
    severity: str
    message: str
    current: float | int | str | None = None
    previous: float | int | str | None = None


def load_alert_state(path: str | Path) -> dict[str, Any]:
    state_path = Path(path)
    if not state_path.exists():
        return {}
    try:
        value = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def write_alert_state(path: str | Path, state: dict[str, Any]) -> Path:
    state_path = Path(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return state_path


def evaluate_alerts(
    report: DailyReport,
    previous_state: dict[str, Any],
    settings: AlertSettings,
) -> tuple[list[AlertEvent], dict[str, Any]]:
    previous_symbols = previous_state.get("symbols") or {}
    previous_emitted = previous_state.get("emitted") or {}
    emitted = dict(previous_emitted) if isinstance(previous_emitted, dict) else {}
    current_symbols = [_snapshot(item) for item in report.analyses if item.snapshot.rows > 0]
    current_by_symbol = {item["symbol"]: item for item in current_symbols}
    events: list[AlertEvent] = []

    if isinstance(previous_symbols, dict) and previous_symbols:
        for symbol, current in current_by_symbol.items():
            previous = previous_symbols.get(symbol) if isinstance(previous_symbols.get(symbol), dict) else None
            candidates = _events_for_symbol(symbol, current, previous, settings)
            for event in candidates:
                key = f"{symbol}:{event.kind}"
                fingerprint = _fingerprint(event)
                if emitted.get(key) == fingerprint:
                    continue
                emitted[key] = fingerprint
                events.append(event)

    next_state = {
        "generated_at": report.generated_at.isoformat(),
        "symbols": current_by_symbol,
        "emitted": emitted,
    }
    return events, next_state


def format_alert_message(report: DailyReport, events: list[AlertEvent]) -> str:
    lines = [report.title, f"Market change alerts · {report.generated_at.isoformat()}", ""]
    for event in events:
        lines.append(f"[{event.severity.upper()}] {event.symbol} · {event.message}")
    lines.extend(["", "Research automation only. Not financial advice. No order placement."])
    return "\n".join(lines)


def _snapshot(analysis) -> dict[str, Any]:
    return {
        "symbol": analysis.asset.symbol,
        "score": analysis.signal.score,
        "risk_level": analysis.signal.risk_level,
        "change_pct": analysis.snapshot.change_pct,
        "relative_return_20d": analysis.benchmark.relative_return_20d if analysis.benchmark else None,
        "freshness_status": analysis.freshness.status if analysis.freshness else None,
        "latest_data_date": analysis.freshness.latest_date if analysis.freshness else analysis.snapshot.end_date,
    }


def _events_for_symbol(
    symbol: str,
    current: dict[str, Any],
    previous: dict[str, Any] | None,
    settings: AlertSettings,
) -> list[AlertEvent]:
    events: list[AlertEvent] = []
    if previous:
        score_delta = _number(current.get("score")) - _number(previous.get("score"))
        if abs(score_delta) >= settings.score_change:
            events.append(
                AlertEvent(
                    symbol,
                    "score-change",
                    "medium" if abs(score_delta) < 20 else "high",
                    f"Signal score changed {score_delta:+.0f} to {current.get('score')}/100.",
                    current.get("score"),
                    previous.get("score"),
                )
            )
        current_relative = current.get("relative_return_20d")
        previous_relative = previous.get("relative_return_20d")
        if current_relative is not None and previous_relative is not None:
            relative_delta = float(current_relative) - float(previous_relative)
            if relative_delta <= -settings.relative_20d_drop:
                events.append(
                    AlertEvent(
                        symbol,
                        "relative-drop",
                        "medium",
                        f"20D relative strength deteriorated {relative_delta * 100:.2f} percentage points.",
                        current_relative,
                        previous_relative,
                    )
                )
        risk_increased = RISK_RANK.get(str(current.get("risk_level")), 0) > RISK_RANK.get(
            str(previous.get("risk_level")), 0
        )
        if settings.risk_upgrade and risk_increased:
            events.append(
                AlertEvent(
                    symbol,
                    "risk-upgrade",
                    "high",
                    f"Risk level increased from {previous.get('risk_level')} to {current.get('risk_level')}.",
                    current.get("risk_level"),
                    previous.get("risk_level"),
                )
            )
        if settings.stale_data and current.get("freshness_status") == "stale" and previous.get("freshness_status") != "stale":
            events.append(
                AlertEvent(
                    symbol,
                    "stale-data",
                    "medium",
                    f"Market data became stale; latest trading day {current.get('latest_data_date') or 'unknown'}.",
                    current.get("latest_data_date"),
                    previous.get("latest_data_date"),
                )
            )
    change = current.get("change_pct")
    if change is not None and abs(float(change)) >= settings.daily_move:
        events.append(
            AlertEvent(
                symbol,
                "daily-move",
                "high" if abs(float(change)) >= settings.daily_move * 1.6 else "medium",
                f"Single-day move reached {float(change) * 100:+.2f}%.",
                change,
                previous.get("change_pct") if previous else None,
            )
        )
    return events


def _number(value: object) -> float:
    try:
        return float(value) if value is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def _fingerprint(event: AlertEvent) -> str:
    value = event.current if event.kind in {"daily-move", "risk-upgrade", "stale-data"} else [event.current, event.previous]
    return json.dumps(value, ensure_ascii=False, sort_keys=True)
