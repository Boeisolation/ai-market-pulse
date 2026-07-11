from __future__ import annotations

import importlib.util
import os
from dataclasses import dataclass

from .config import AppConfig
from .market_data import provider_can_handle, supported_providers
from .models import Asset


@dataclass(frozen=True)
class DoctorCheck:
    name: str
    status: str
    detail: str


def run_doctor(config: AppConfig) -> list[DoctorCheck]:
    checks: list[DoctorCheck] = []
    providers = config.data.providers
    for provider in providers:
        checks.append(_provider_check(provider))
    unknown = [provider for provider in providers if provider.lower() not in supported_providers()]
    for provider in unknown:
        checks.append(DoctorCheck(f"provider:{provider}", "fail", "Unsupported provider name."))
    for asset in config.assets:
        capable = [provider for provider in providers if provider_can_handle(provider, asset)]
        status = "ok" if capable else "fail"
        detail = ", ".join(capable) if capable else "No configured provider can handle this symbol."
        checks.append(DoctorCheck(f"asset:{asset.symbol}", status, detail))
    if config.benchmarks.enabled:
        for asset in _benchmark_assets(config):
            capable = [provider for provider in providers if provider_can_handle(provider, asset)]
            status = "ok" if capable else "fail"
            detail = ", ".join(capable) if capable else "No configured provider can handle this benchmark."
            checks.append(DoctorCheck(f"benchmark:{asset.symbol}", status, detail))
    checks.append(_llm_check(config))
    return checks


def format_doctor(checks: list[DoctorCheck]) -> str:
    lines = ["AI Market Pulse Doctor", ""]
    for check in checks:
        marker = {"ok": "OK", "warn": "WARN", "fail": "FAIL"}.get(check.status, check.status.upper())
        lines.append(f"[{marker}] {check.name}: {check.detail}")
    return "\n".join(lines)


def _provider_check(provider: str) -> DoctorCheck:
    name = provider.strip().lower()
    if name in {"yfinance", "yf"}:
        return _module_check("provider:yfinance", "yfinance", "Install with `pip install -e .`.")
    if name == "akshare":
        return _module_check("provider:akshare", "akshare", "Optional. Install with `pip install -e .[cn]`.")
    if name == "baostock":
        return _module_check("provider:baostock", "baostock", "Optional. Install with `pip install -e .[cn]`.")
    if name == "tushare":
        module = _module_check("provider:tushare", "tushare", "Optional. Install with `pip install -e .[tushare]`.")
        if module.status != "ok":
            return module
        if not os.getenv("TUSHARE_TOKEN"):
            return DoctorCheck("provider:tushare", "warn", "Installed, but TUSHARE_TOKEN is not configured.")
        return DoctorCheck("provider:tushare", "ok", "Installed and token is configured.")
    return DoctorCheck(f"provider:{provider}", "fail", "Unsupported provider.")


def _module_check(name: str, module: str, hint: str) -> DoctorCheck:
    if importlib.util.find_spec(module):
        return DoctorCheck(name, "ok", "Installed.")
    return DoctorCheck(name, "warn", f"Not installed. {hint}")


def _llm_check(config: AppConfig) -> DoctorCheck:
    if not config.llm.enabled:
        return DoctorCheck("llm", "warn", "Disabled. Reports will use rule-based summaries only.")
    key = os.getenv(config.llm.api_key_env)
    if not key:
        return DoctorCheck("llm", "warn", f"Enabled, but {config.llm.api_key_env} is not configured.")
    if not config.llm.model:
        return DoctorCheck("llm", "warn", "Enabled, but model is empty.")
    return DoctorCheck("llm", "ok", f"Configured for model {config.llm.model}.")


def _benchmark_assets(config: AppConfig) -> list[Asset]:
    symbols: list[str] = []
    symbols.extend(config.benchmarks.symbols)
    symbols.extend(config.benchmarks.compare.values())
    markets = {asset.market.upper() for asset in config.assets}
    symbols.extend(
        benchmark
        for market, benchmark in config.benchmarks.default_by_market.items()
        if market.upper() in markets
    )
    seen: set[str] = set()
    assets: list[Asset] = []
    for symbol in symbols:
        key = symbol.upper()
        if key in seen:
            continue
        seen.add(key)
        assets.append(Asset(symbol=symbol, market=_infer_market(symbol)))
    return assets


def _infer_market(symbol: str) -> str:
    upper = symbol.upper()
    if upper.endswith((".SS", ".SZ")) or upper.startswith(("000", "399")):
        return "CN"
    if upper.endswith(".HK") or upper.startswith("^HSI"):
        return "HK"
    if upper.endswith("-USD"):
        return "CRYPTO"
    return "US"
