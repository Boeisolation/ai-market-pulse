from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

_HISTORY_COLUMNS = ["Date", "Open", "High", "Low", "Close", "Volume"]


@dataclass(frozen=True)
class CachedHistory:
    history: pd.DataFrame
    source: str
    name: str | None
    currency: str | None
    fetched_at: datetime
    lookback_days: int

    @property
    def last_date(self) -> pd.Timestamp | None:
        if self.history.empty:
            return None
        return pd.to_datetime(self.history["Date"].iloc[-1])


class MarketDataCache:
    """Per-symbol OHLCV cache stored as CSV + JSON metadata.

    CSV keeps the cache transparent and diffable without adding a parquet
    dependency. Writes are atomic (tmp + replace); concurrent workers touch
    distinct symbols so no cross-file locking is needed.
    """

    def __init__(self, directory: str | Path, ttl_minutes: int = 30) -> None:
        self.directory = Path(directory)
        self.ttl_minutes = ttl_minutes

    def load(self, symbol: str) -> CachedHistory | None:
        csv_path, meta_path = self._paths(symbol)
        if not csv_path.exists() or not meta_path.exists():
            return None
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            history = pd.read_csv(csv_path)
            history["Date"] = pd.to_datetime(history["Date"])
            for column in _HISTORY_COLUMNS[1:]:
                if column in history:
                    history[column] = pd.to_numeric(history[column], errors="coerce")
            fetched_at = datetime.fromisoformat(meta["fetched_at"])
        except (ValueError, KeyError, TypeError, OSError):
            return None
        if history.empty:
            return None
        return CachedHistory(
            history=history,
            source=str(meta.get("source") or ""),
            name=meta.get("name"),
            currency=meta.get("currency"),
            fetched_at=fetched_at,
            lookback_days=int(meta.get("lookback_days") or 0),
        )

    def store(
        self,
        symbol: str,
        history: pd.DataFrame,
        *,
        source: str,
        name: str | None,
        currency: str | None,
        lookback_days: int,
    ) -> None:
        csv_path, meta_path = self._paths(symbol)
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        columns = [column for column in _HISTORY_COLUMNS if column in history.columns]
        payload = history[columns].copy()
        payload["Date"] = pd.to_datetime(payload["Date"]).dt.strftime("%Y-%m-%d")
        tmp_csv = csv_path.with_suffix(".csv.tmp")
        payload.to_csv(tmp_csv, index=False)
        tmp_csv.replace(csv_path)
        meta = {
            "symbol": symbol,
            "source": source,
            "name": name,
            "currency": currency,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "lookback_days": lookback_days,
            "rows": int(len(payload)),
        }
        tmp_meta = meta_path.with_suffix(".json.tmp")
        tmp_meta.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
        tmp_meta.replace(meta_path)

    def is_fresh(self, cached: CachedHistory) -> bool:
        if self.ttl_minutes <= 0:
            return False
        age = datetime.now(timezone.utc) - cached.fetched_at
        return age.total_seconds() < self.ttl_minutes * 60

    def _paths(self, symbol: str) -> tuple[Path, Path]:
        safe = re.sub(r"[^A-Za-z0-9._-]", "_", symbol.strip().upper()) or "_"
        return self.directory / f"{safe}.csv", self.directory / f"{safe}.meta.json"
