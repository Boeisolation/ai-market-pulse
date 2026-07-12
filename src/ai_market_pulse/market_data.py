from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, replace
from datetime import date, timedelta
from typing import Callable
import os

import pandas as pd

from .market_cache import CachedHistory, MarketDataCache
from .models import Asset, PriceSnapshot, is_otc_fund_symbol

logger = logging.getLogger(__name__)


class MarketDataError(RuntimeError):
    pass


Provider = Callable[[Asset, int], tuple[Asset, PriceSnapshot, pd.DataFrame]]
IncrementalProvider = Callable[[Asset, date], pd.DataFrame]

# Overlap window re-fetched on incremental updates so late data revisions heal.
_INCREMENTAL_OVERLAP_DAYS = 7

# baostock keeps login state in module-level globals, so concurrent fetches
# must serialize around login/logout.
_BAOSTOCK_LOCK = threading.Lock()

# fund_name_em downloads the full ~20k-fund directory (one static JS file);
# fetch it once per process and share it across worker threads.
_FUND_DIRECTORY_LOCK = threading.Lock()
_FUND_DIRECTORY: dict[str, tuple[str, str]] | None = None


@dataclass(frozen=True)
class ProviderSpec:
    name: str
    fetch: Provider
    can_handle: Callable[[Asset], bool]
    aliases: tuple[str, ...] = ()
    markets: tuple[str, ...] = ()
    fetch_since: IncrementalProvider | None = None


_PROVIDERS: dict[str, ProviderSpec] = {}
_BUILTINS_READY = False


def register_provider(spec: ProviderSpec, *, replace_existing: bool = False) -> None:
    names = (spec.name, *spec.aliases)
    keys = [name.strip().lower() for name in names if name.strip()]
    if not keys:
        raise ValueError("Provider must define a name.")
    conflicts = [key for key in keys if key in _PROVIDERS]
    if conflicts and not replace_existing:
        raise ValueError(f"Provider already registered: {', '.join(conflicts)}")
    for key in keys:
        _PROVIDERS[key] = spec


def get_provider(name: str) -> ProviderSpec | None:
    _ensure_builtin_providers()
    return _PROVIDERS.get(name.strip().lower())


def fetch_history(
    asset: Asset,
    lookback_days: int,
    providers: list[str] | tuple[str, ...] | None = None,
    *,
    cache: MarketDataCache | None = None,
) -> tuple[Asset, PriceSnapshot, pd.DataFrame]:
    provider_names = list(providers or ["akshare", "yfinance"])
    cached = cache.load(asset.symbol) if cache else None

    if cache and cached and cache.is_fresh(cached) and _cache_covers(cached, lookback_days):
        return _result_from_cache(asset, cached, lookback_days)

    errors: list[str] = []
    for provider_name in provider_names:
        spec = get_provider(provider_name)
        if spec is None:
            errors.append(f"{provider_name}: unsupported provider")
            continue
        if not spec.can_handle(asset):
            errors.append(f"{provider_name}: does not support {asset.market} asset {asset.symbol}")
            continue
        try:
            if (
                cached is not None
                and spec.fetch_since is not None
                and cached.source == spec.name
                and _cache_covers(cached, lookback_days)
            ):
                hydrated, snapshot, history, merged = _incremental_fetch(spec, asset, cached, lookback_days)
            else:
                hydrated, snapshot, history = spec.fetch(asset, lookback_days)
                merged = history
            if cache:
                cache.store(
                    asset.symbol,
                    merged,
                    source=spec.name,
                    name=hydrated.name,
                    currency=hydrated.currency,
                    lookback_days=lookback_days,
                )
            return hydrated, snapshot, history
        except MarketDataError as exc:
            errors.append(f"{provider_name}: {exc}")
        except Exception as exc:
            # Network stacks raise far more than MarketDataError (TLS errors,
            # DNS failures, provider bugs). Degrade to the next provider or the
            # stale cache instead of killing the whole run.
            errors.append(f"{provider_name}: unexpected {type(exc).__name__}: {exc}")

    if cached is not None:
        logger.warning(
            "All providers failed for %s; serving stale cache from %s (%s rows).",
            asset.symbol,
            cached.last_date.date() if cached.last_date is not None else "unknown",
            len(cached.history),
        )
        return _result_from_cache(asset, cached, lookback_days)
    raise MarketDataError(f"No provider returned data for {asset.symbol}. " + " | ".join(errors))


def _cache_covers(cached: CachedHistory, lookback_days: int) -> bool:
    return len(cached.history) >= lookback_days or cached.lookback_days >= lookback_days


def _result_from_cache(
    asset: Asset,
    cached: CachedHistory,
    lookback_days: int,
) -> tuple[Asset, PriceSnapshot, pd.DataFrame]:
    history = cached.history.tail(lookback_days).reset_index(drop=True)
    name = asset.name or cached.name or asset.symbol
    currency = asset.currency or cached.currency
    snapshot = _snapshot(asset.symbol, name, currency, history, source=cached.source or "cache")
    return replace(asset, name=name, currency=currency), snapshot, history


def _incremental_fetch(
    spec: ProviderSpec,
    asset: Asset,
    cached: CachedHistory,
    lookback_days: int,
) -> tuple[Asset, PriceSnapshot, pd.DataFrame, pd.DataFrame]:
    assert spec.fetch_since is not None
    last_date = cached.last_date
    since = (last_date - pd.Timedelta(days=_INCREMENTAL_OVERLAP_DAYS)).date() if last_date is not None else None
    if since is None:
        raise MarketDataError(f"Cache for {asset.symbol} has no usable dates.")
    fresh_rows = spec.fetch_since(asset, since)
    merged = pd.concat([cached.history, fresh_rows], ignore_index=True)
    merged["Date"] = pd.to_datetime(merged["Date"])
    merged = merged.drop_duplicates(subset="Date", keep="last").sort_values("Date").reset_index(drop=True)
    history = merged.tail(lookback_days).reset_index(drop=True)
    name = asset.name or cached.name or asset.symbol
    currency = asset.currency or cached.currency
    snapshot = _snapshot(asset.symbol, name, currency, history, source=spec.name)
    return replace(asset, name=name, currency=currency), snapshot, history, merged


def _provider(name: str) -> Provider | None:
    spec = get_provider(name)
    return spec.fetch if spec else None


def _fetch_yfinance(asset: Asset, lookback_days: int) -> tuple[Asset, PriceSnapshot, pd.DataFrame]:
    try:
        import yfinance as yf
    except ImportError as exc:
        raise MarketDataError("yfinance is required for market data. Run `pip install -e .`.") from exc

    ticker = yf.Ticker(asset.symbol)
    # lookback_days is a trading-day target, but yfinance `period` counts calendar days.
    # Widen the window (~1.7x + buffer) so long rolling windows like SMA200 have enough
    # rows; otherwise 220 calendar days yields only ~150 trading rows and SMA200 is never
    # computed. Trim back to lookback_days for parity with the A-share providers.
    calendar_days = max(int(lookback_days * 1.7) + 15, lookback_days)
    history = ticker.history(period=f"{calendar_days}d", auto_adjust=False)
    if history.empty:
        raise MarketDataError(f"No market data returned for {asset.symbol}.")

    history = history.reset_index()
    history.columns = [str(column).split(" ")[0] for column in history.columns]
    history = _normalize_history(history, asset.symbol).tail(lookback_days).reset_index(drop=True)

    name = asset.name
    currency = asset.currency
    if not name or not currency:
        # fast_info is a cheap quote lookup; ticker.info triggers a slow full
        # scrape, so only fall back to it when the name is still unknown.
        fast = _fast_info(ticker)
        currency = currency or fast.get("currency")
        if not name:
            slow = _slow_info(ticker)
            name = slow.get("shortName") or slow.get("longName")
            currency = currency or slow.get("currency")
    name = name or asset.symbol
    snapshot = _snapshot(asset.symbol, name, currency, history, source="yfinance")
    return replace(asset, name=name, currency=currency), snapshot, history


def _fetch_yfinance_since(asset: Asset, since: date) -> pd.DataFrame:
    try:
        import yfinance as yf
    except ImportError as exc:
        raise MarketDataError("yfinance is required for market data. Run `pip install -e .`.") from exc

    ticker = yf.Ticker(asset.symbol)
    history = ticker.history(start=since.isoformat(), auto_adjust=False)
    if history.empty:
        return pd.DataFrame(columns=["Date", "Open", "High", "Low", "Close", "Volume"])
    history = history.reset_index()
    history.columns = [str(column).split(" ")[0] for column in history.columns]
    return _normalize_history(history, asset.symbol)


def _fetch_akshare(asset: Asset, lookback_days: int) -> tuple[Asset, PriceSnapshot, pd.DataFrame]:
    code = _a_share_code(asset)
    if not code:
        raise MarketDataError("AkShare provider only handles mainland A-share symbols.")
    try:
        import akshare as ak
    except ImportError as exc:
        raise MarketDataError("akshare is not installed. Run `pip install -e .[cn]` to enable it.") from exc

    end_date = date.today()
    start_date = end_date - timedelta(days=max(lookback_days * 2, 90))
    try:
        raw = ak.stock_zh_a_hist(
            symbol=code,
            period="daily",
            start_date=start_date.strftime("%Y%m%d"),
            end_date=end_date.strftime("%Y%m%d"),
            adjust="",
        )
    except Exception as exc:
        raise MarketDataError(f"AkShare request failed: {exc}") from exc
    if raw is None or raw.empty:
        raise MarketDataError(f"No AkShare data returned for {asset.symbol}.")

    history = raw.rename(columns=_AKSHARE_COLUMNS)
    history = _normalize_history(history, asset.symbol).tail(lookback_days)
    name = asset.name or asset.symbol
    currency = asset.currency or "CNY"
    snapshot = _snapshot(asset.symbol, name, currency, history, source="akshare")
    return replace(asset, name=name, currency=currency), snapshot, history


_AKSHARE_COLUMNS = {
    "日期": "Date",
    "开盘": "Open",
    "最高": "High",
    "最低": "Low",
    "收盘": "Close",
    "成交量": "Volume",
}


def _fetch_akshare_since(asset: Asset, since: date) -> pd.DataFrame:
    code = _a_share_code(asset)
    if not code:
        raise MarketDataError("AkShare provider only handles mainland A-share symbols.")
    try:
        import akshare as ak
    except ImportError as exc:
        raise MarketDataError("akshare is not installed. Run `pip install -e .[cn]` to enable it.") from exc
    try:
        raw = ak.stock_zh_a_hist(
            symbol=code,
            period="daily",
            start_date=since.strftime("%Y%m%d"),
            end_date=date.today().strftime("%Y%m%d"),
            adjust="",
        )
    except Exception as exc:
        raise MarketDataError(f"AkShare request failed: {exc}") from exc
    if raw is None or raw.empty:
        return pd.DataFrame(columns=["Date", "Open", "High", "Low", "Close", "Volume"])
    return _normalize_history(raw.rename(columns=_AKSHARE_COLUMNS), asset.symbol)


def _fund_code(asset: Asset) -> str | None:
    symbol = asset.symbol.strip().upper()
    return symbol[:6] if is_otc_fund_symbol(symbol) else None


def _fund_directory() -> dict[str, tuple[str, str]]:
    global _FUND_DIRECTORY
    with _FUND_DIRECTORY_LOCK:
        if _FUND_DIRECTORY is None:
            try:
                import akshare as ak

                raw = ak.fund_name_em()
                _FUND_DIRECTORY = {
                    str(code): (str(name), str(kind))
                    for code, name, kind in zip(raw["基金代码"], raw["基金简称"], raw["基金类型"])
                }
            except Exception as exc:
                # Directory is best-effort: without it funds lose their display
                # name and the money-fund guard, but NAV fetching still works.
                logger.warning("Fund directory lookup failed: %s", exc)
                _FUND_DIRECTORY = {}
    return _FUND_DIRECTORY


def _fetch_akshare_fund(asset: Asset, lookback_days: int) -> tuple[Asset, PriceSnapshot, pd.DataFrame]:
    code = _fund_code(asset)
    if not code:
        raise MarketDataError("AkShare fund provider only handles 6-digit `.OF` fund symbols.")
    try:
        import akshare as ak
    except ImportError as exc:
        raise MarketDataError("akshare is not installed. Run `pip install -e .[cn]` to enable it.") from exc

    directory_name, fund_type = _fund_directory().get(code, (None, ""))
    if fund_type and ("货币" in fund_type or "理财" in fund_type):
        raise MarketDataError(
            f"{code} 是{fund_type}基金：净值恒定在 1 元附近，技术面分析无意义，请当作现金处理。"
        )
    try:
        raw = ak.fund_open_fund_info_em(symbol=code, indicator="单位净值走势")
    except Exception as exc:
        raise MarketDataError(f"AkShare fund NAV request failed: {exc}") from exc
    if raw is None or raw.empty:
        raise MarketDataError(f"No fund NAV data returned for {asset.symbol}.")

    history = _fund_nav_to_history(raw, asset.symbol).tail(lookback_days).reset_index(drop=True)
    name = asset.name or directory_name or asset.symbol
    currency = asset.currency or "CNY"
    snapshot = _snapshot(asset.symbol, name, currency, history, source="akshare_fund")
    return replace(asset, name=name, currency=currency, market="CN"), snapshot, history


def _fund_nav_to_history(raw: pd.DataFrame, symbol: str) -> pd.DataFrame:
    data = raw.copy()
    data["净值日期"] = pd.to_datetime(data["净值日期"], errors="coerce")
    data["单位净值"] = pd.to_numeric(data["单位净值"], errors="coerce")
    data = data.dropna(subset=["净值日期", "单位净值"]).sort_values("净值日期").reset_index(drop=True)
    if data.empty:
        raise MarketDataError(f"No usable NAV rows for {symbol}.")

    unit = data["单位净值"].astype(float)
    # East Money's 日增长率 is dividend-adjusted (on ex-dividend days it reports
    # the true return, not the raw NAV drop — verified against 161725 which
    # shows -0.24% growth on a day the raw NAV fell 33%). Compounding it and
    # anchoring at the latest published NAV yields an adjusted series whose
    # last value matches what fund apps display.
    if "日增长率" in data:
        growth = pd.to_numeric(data["日增长率"], errors="coerce") / 100.0
        growth = growth.fillna(unit.pct_change())
    else:
        growth = unit.pct_change()
    growth.iloc[0] = 0.0
    growth = growth.fillna(0.0)
    factor = (1.0 + growth).cumprod()
    adjusted = unit.iloc[-1] * factor / factor.iloc[-1]

    # Degenerate OHLC bars keep the indicator engine untouched: True Range
    # collapses to |Δclose| (a fair daily-volatility proxy for NAV series) and
    # the NaN volume disables volume-based scoring automatically.
    frame = pd.DataFrame(
        {
            "Date": data["净值日期"],
            "Open": adjusted,
            "High": adjusted,
            "Low": adjusted,
            "Close": adjusted,
            "Volume": float("nan"),
        }
    )
    return _normalize_history(frame, symbol)


def _fetch_baostock(asset: Asset, lookback_days: int) -> tuple[Asset, PriceSnapshot, pd.DataFrame]:
    code = _a_share_code(asset)
    if not code:
        raise MarketDataError("Baostock provider only handles mainland A-share symbols.")
    try:
        import baostock as bs
    except ImportError as exc:
        raise MarketDataError("baostock is not installed. Run `pip install -e .[cn]` to enable it.") from exc

    exchange = "sh" if code.startswith(("6", "5", "9")) else "sz"
    bs_code = f"{exchange}.{code}"
    end_date = date.today()
    start_date = end_date - timedelta(days=max(lookback_days * 2, 90))
    with _BAOSTOCK_LOCK:
        login = bs.login()
        if getattr(login, "error_code", "0") != "0":
            raise MarketDataError(f"Baostock login failed: {getattr(login, 'error_msg', '')}")
        try:
            query = bs.query_history_k_data_plus(
                bs_code,
                "date,open,high,low,close,volume",
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat(),
                frequency="d",
                adjustflag="3",
            )
            rows = []
            while query.next():
                rows.append(query.get_row_data())
        finally:
            bs.logout()
    if not rows:
        raise MarketDataError(f"No Baostock data returned for {asset.symbol}.")
    raw = pd.DataFrame(rows, columns=["Date", "Open", "High", "Low", "Close", "Volume"])
    history = _normalize_history(raw, asset.symbol).tail(lookback_days)
    name = asset.name or asset.symbol
    currency = asset.currency or "CNY"
    snapshot = _snapshot(asset.symbol, name, currency, history, source="baostock")
    return replace(asset, name=name, currency=currency), snapshot, history


def _fetch_tushare(asset: Asset, lookback_days: int) -> tuple[Asset, PriceSnapshot, pd.DataFrame]:
    code = _a_share_code(asset)
    if not code:
        raise MarketDataError("Tushare provider only handles mainland A-share symbols.")
    token = os.getenv("TUSHARE_TOKEN")
    if not token:
        raise MarketDataError("TUSHARE_TOKEN is not configured.")
    try:
        import tushare as ts
    except ImportError as exc:
        raise MarketDataError("tushare is not installed. Run `pip install -e .[tushare]` to enable it.") from exc
    suffix = "SH" if code.startswith(("6", "5", "9")) else "SZ"
    ts_code = f"{code}.{suffix}"
    end_date = date.today()
    start_date = end_date - timedelta(days=max(lookback_days * 2, 90))
    pro = ts.pro_api(token)
    try:
        raw = pro.daily(ts_code=ts_code, start_date=start_date.strftime("%Y%m%d"), end_date=end_date.strftime("%Y%m%d"))
    except Exception as exc:
        raise MarketDataError(f"Tushare request failed: {exc}") from exc
    if raw is None or raw.empty:
        raise MarketDataError(f"No Tushare data returned for {asset.symbol}.")
    history = raw.rename(
        columns={
            "trade_date": "Date",
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "vol": "Volume",
        }
    )
    history = _normalize_history(history, asset.symbol).tail(lookback_days)
    name = asset.name or asset.symbol
    currency = asset.currency or "CNY"
    snapshot = _snapshot(asset.symbol, name, currency, history, source="tushare")
    return replace(asset, name=name, currency=currency), snapshot, history


def _normalize_history(history: pd.DataFrame, symbol: str) -> pd.DataFrame:
    required = {"Date", "Open", "High", "Low", "Close"}
    missing = required.difference(history.columns)
    if missing:
        raise MarketDataError(f"Missing columns for {symbol}: {', '.join(sorted(missing))}")
    normalized = history.copy()
    normalized["Date"] = pd.to_datetime(normalized["Date"])
    for column in ["Open", "High", "Low", "Close", "Volume"]:
        if column in normalized:
            normalized[column] = pd.to_numeric(normalized[column], errors="coerce")
    normalized = normalized.dropna(subset=["Date", "Open", "High", "Low", "Close"])
    normalized = normalized.sort_values("Date").reset_index(drop=True)
    if normalized.empty:
        raise MarketDataError(f"No usable OHLC rows for {symbol}.")
    return normalized


def _snapshot(
    symbol: str,
    name: str,
    currency: str | None,
    history: pd.DataFrame,
    source: str,
) -> PriceSnapshot:
    close = history["Close"].dropna().astype(float)
    previous_close = float(close.iloc[-2]) if len(close) >= 2 else None
    last_close = float(close.iloc[-1])
    change_pct = None
    if previous_close not in (None, 0):
        change_pct = last_close / previous_close - 1

    start_date = str(pd.to_datetime(history["Date"].iloc[0]).date())
    end_date = str(pd.to_datetime(history["Date"].iloc[-1]).date())
    return PriceSnapshot(
        symbol=symbol,
        name=name,
        currency=currency,
        last_close=round(last_close, 6),
        previous_close=round(previous_close, 6) if previous_close is not None else None,
        change_pct=round(change_pct, 6) if change_pct is not None else None,
        start_date=start_date,
        end_date=end_date,
        rows=int(len(history)),
        source=source,
    )


def _a_share_code(asset: Asset) -> str | None:
    symbol = asset.symbol.upper()
    if symbol.endswith((".SS", ".SZ")) and len(symbol) >= 9:
        code = symbol[:6]
    elif asset.market.upper() in {"CN", "A", "A-SHARE"} and symbol.isdigit() and len(symbol) == 6:
        code = symbol
    else:
        return None
    return code if code.isdigit() and len(code) == 6 else None


def provider_can_handle(provider: str, asset: Asset) -> bool:
    spec = get_provider(provider)
    return bool(spec and spec.can_handle(asset))


def supported_providers() -> list[str]:
    _ensure_builtin_providers()
    return sorted({spec.name for spec in _PROVIDERS.values()})


def _ensure_builtin_providers() -> None:
    global _BUILTINS_READY
    if _BUILTINS_READY:
        return
    def mainland(asset: Asset) -> bool:
        return _a_share_code(asset) is not None
    def otc_fund(asset: Asset) -> bool:
        return _fund_code(asset) is not None
    register_provider(
        ProviderSpec("akshare", _fetch_akshare, mainland, markets=("CN",), fetch_since=_fetch_akshare_since)
    )
    # pingzhongdata returns the full NAV history in one static JS file, so an
    # incremental fetch_since would not save anything — the TTL cache already
    # absorbs repeat calls.
    register_provider(
        ProviderSpec("akshare_fund", _fetch_akshare_fund, otc_fund, aliases=("fund", "eastmoney_fund"), markets=("CN",))
    )
    register_provider(ProviderSpec("baostock", _fetch_baostock, mainland, markets=("CN",)))
    register_provider(ProviderSpec("tushare", _fetch_tushare, mainland, markets=("CN",)))
    register_provider(
        ProviderSpec(
            "yfinance",
            _fetch_yfinance,
            # Yahoo has no data for mainland OTC funds; skip them instead of
            # burning a guaranteed-to-fail network round trip.
            lambda asset: _fund_code(asset) is None,
            aliases=("yf",),
            markets=("US", "CN", "HK", "CRYPTO"),
            fetch_since=_fetch_yfinance_since,
        )
    )
    _BUILTINS_READY = True


def _fast_info(ticker: object) -> dict:
    try:
        return dict(getattr(ticker, "fast_info", {}) or {})
    except Exception:
        return {}


def _slow_info(ticker: object) -> dict:
    try:
        return dict(getattr(ticker, "info", {}) or {})
    except Exception:
        return {}
