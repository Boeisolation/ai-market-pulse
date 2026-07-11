from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, timedelta
from typing import Callable
import os

import pandas as pd

from .models import Asset, PriceSnapshot


class MarketDataError(RuntimeError):
    pass


Provider = Callable[[Asset, int], tuple[Asset, PriceSnapshot, pd.DataFrame]]


@dataclass(frozen=True)
class ProviderSpec:
    name: str
    fetch: Provider
    can_handle: Callable[[Asset], bool]
    aliases: tuple[str, ...] = ()
    markets: tuple[str, ...] = ()


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
) -> tuple[Asset, PriceSnapshot, pd.DataFrame]:
    provider_names = list(providers or ["akshare", "yfinance"])
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
            return spec.fetch(asset, lookback_days)
        except MarketDataError as exc:
            errors.append(f"{provider_name}: {exc}")
    raise MarketDataError(f"No provider returned data for {asset.symbol}. " + " | ".join(errors))


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

    info = _safe_info(ticker)
    name = asset.name or info.get("shortName") or info.get("longName") or asset.symbol
    currency = asset.currency or info.get("currency")
    snapshot = _snapshot(asset.symbol, name, currency, history, source="yfinance")
    return replace(asset, name=name, currency=currency), snapshot, history


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

    mapping = {
        "日期": "Date",
        "开盘": "Open",
        "最高": "High",
        "最低": "Low",
        "收盘": "Close",
        "成交量": "Volume",
    }
    history = raw.rename(columns=mapping)
    history = _normalize_history(history, asset.symbol).tail(lookback_days)
    name = asset.name or asset.symbol
    currency = asset.currency or "CNY"
    snapshot = _snapshot(asset.symbol, name, currency, history, source="akshare")
    return replace(asset, name=name, currency=currency), snapshot, history


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
    register_provider(ProviderSpec("akshare", _fetch_akshare, mainland, markets=("CN",)))
    register_provider(ProviderSpec("baostock", _fetch_baostock, mainland, markets=("CN",)))
    register_provider(ProviderSpec("tushare", _fetch_tushare, mainland, markets=("CN",)))
    register_provider(
        ProviderSpec(
            "yfinance",
            _fetch_yfinance,
            lambda asset: True,
            aliases=("yf",),
            markets=("US", "CN", "HK", "CRYPTO"),
        )
    )
    _BUILTINS_READY = True


def _safe_info(ticker: object) -> dict:
    try:
        return dict(getattr(ticker, "fast_info", {}) or {}) | dict(getattr(ticker, "info", {}) or {})
    except Exception:
        return {}
