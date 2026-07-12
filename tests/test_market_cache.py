from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd

from ai_market_pulse.market_cache import MarketDataCache
from ai_market_pulse.market_data import (
    MarketDataError,
    ProviderSpec,
    fetch_history,
    register_provider,
)
from ai_market_pulse.models import Asset, PriceSnapshot


def _frame(start: str, rows: int, base: float = 100.0) -> pd.DataFrame:
    dates = pd.date_range(start, periods=rows, freq="B")
    close = [base + index for index in range(rows)]
    return pd.DataFrame(
        {
            "Date": dates,
            "Open": close,
            "High": [value + 1 for value in close],
            "Low": [value - 1 for value in close],
            "Close": close,
            "Volume": [1000] * rows,
        }
    )


def _snapshot_for(asset: Asset, history: pd.DataFrame, source: str) -> PriceSnapshot:
    close = history["Close"]
    return PriceSnapshot(
        symbol=asset.symbol,
        name=asset.name or asset.symbol,
        currency="USD",
        last_close=float(close.iloc[-1]),
        previous_close=float(close.iloc[-2]),
        change_pct=None,
        start_date=str(history["Date"].iloc[0].date()),
        end_date=str(history["Date"].iloc[-1].date()),
        rows=len(history),
        source=source,
    )


def test_cache_store_and_load_roundtrip(tmp_path) -> None:
    cache = MarketDataCache(tmp_path, ttl_minutes=30)
    history = _frame("2026-01-01", 50)

    cache.store("BTC-USD", history, source="yfinance", name="Bitcoin", currency="USD", lookback_days=50)
    cached = cache.load("BTC-USD")

    assert cached is not None
    assert cached.source == "yfinance"
    assert cached.name == "Bitcoin"
    assert len(cached.history) == 50
    assert cache.is_fresh(cached)


def test_cache_ttl_expiry(tmp_path) -> None:
    cache = MarketDataCache(tmp_path, ttl_minutes=30)
    history = _frame("2026-01-01", 10)
    cache.store("AAA", history, source="unit", name=None, currency=None, lookback_days=10)

    cached = cache.load("AAA")
    assert cached is not None

    expired = type(cached)(
        history=cached.history,
        source=cached.source,
        name=cached.name,
        currency=cached.currency,
        fetched_at=datetime.now(timezone.utc) - timedelta(hours=2),
        lookback_days=cached.lookback_days,
    )
    assert not cache.is_fresh(expired)


def test_fresh_cache_skips_provider(tmp_path) -> None:
    calls = {"count": 0}

    def fetch(asset: Asset, lookback: int):
        calls["count"] += 1
        history = _frame("2026-01-01", lookback)
        return asset, _snapshot_for(asset, history, "cached-unit"), history

    register_provider(
        ProviderSpec("cached-unit", fetch, lambda asset: True),
        replace_existing=True,
    )
    cache = MarketDataCache(tmp_path, ttl_minutes=30)

    _, first, _ = fetch_history(Asset("CACHE1"), 20, ["cached-unit"], cache=cache)
    _, second, _ = fetch_history(Asset("CACHE1"), 20, ["cached-unit"], cache=cache)

    assert calls["count"] == 1
    assert first.last_close == second.last_close


def test_stale_cache_serves_when_all_providers_fail(tmp_path) -> None:
    def failing(asset: Asset, lookback: int):
        raise MarketDataError("provider offline")

    register_provider(
        ProviderSpec("offline-unit", failing, lambda asset: True),
        replace_existing=True,
    )
    cache = MarketDataCache(tmp_path, ttl_minutes=0)  # every entry is instantly stale
    history = _frame("2026-01-01", 30)
    cache.store("OFFLINE", history, source="offline-unit", name="Offline Co", currency="USD", lookback_days=30)

    asset, snapshot, served = fetch_history(Asset("OFFLINE"), 30, ["offline-unit"], cache=cache)

    assert snapshot.rows == 30
    assert asset.name == "Offline Co"
    assert len(served) == 30


def test_incremental_fetch_merges_new_rows(tmp_path) -> None:
    calls = {"full": 0, "since": 0}
    old = _frame("2026-01-01", 30)

    def fetch(asset: Asset, lookback: int):
        calls["full"] += 1
        return asset, _snapshot_for(asset, old, "inc-unit"), old

    def fetch_since(asset: Asset, since) -> pd.DataFrame:
        calls["since"] += 1
        last_old = old["Date"].iloc[-1]
        return _frame((last_old + pd.Timedelta(days=1)).strftime("%Y-%m-%d"), 5, base=200.0)

    register_provider(
        ProviderSpec("inc-unit", fetch, lambda asset: True, fetch_since=fetch_since),
        replace_existing=True,
    )
    cache = MarketDataCache(tmp_path, ttl_minutes=0)  # force refresh on second call
    cache.store("INC", old, source="inc-unit", name=None, currency=None, lookback_days=30)

    _, snapshot, history = fetch_history(Asset("INC"), 30, ["inc-unit"], cache=cache)

    assert calls["full"] == 0
    assert calls["since"] == 1
    assert snapshot.last_close == 204.0
    assert len(history) == 30

    cached = cache.load("INC")
    assert cached is not None
    assert len(cached.history) == 35
