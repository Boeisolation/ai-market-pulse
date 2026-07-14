from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from .market_data import fund_directory_lookup, fund_name_similarity, match_fund_by_name, normalize_cn_code
from .models import infer_market as _infer_market
from .models import is_otc_fund_symbol
from .sample import SAMPLE_CONFIGS

# A claimed .OF code is accepted only when the directory name for that code
# still resembles the transcribed name; below this the code is treated as a
# model hallucination and re-resolved from the name.
_FUND_CODE_NAME_MIN_SIMILARITY = 0.55


COLUMN_ALIASES = {
    "symbol": {"symbol", "ticker", "code", "stock", "证券代码", "股票代码", "代码"},
    "name": {"name", "asset", "security", "stock_name", "证券名称", "股票名称", "名称"},
    "market": {"market", "exchange", "市场", "交易所"},
    "currency": {"currency", "ccy", "币种", "货币"},
    "quantity": {"quantity", "qty", "shares", "position", "holding", "持仓", "数量", "股数"},
    "cost_basis": {
        "cost_basis",
        "avg_cost",
        "average_cost",
        "cost",
        "entry_price",
        "成本价",
        "持仓成本",
        "平均成本",
    },
    "tags": {"tags", "tag", "labels", "标签"},
    "note": {"note", "notes", "comment", "备注"},
}


class PortfolioImportError(RuntimeError):
    pass


def import_portfolio_config(
    input_path: str | Path,
    output_path: str | Path,
    template: str = "default",
    title: str | None = None,
) -> Path:
    assets = read_portfolio_assets(input_path)
    if not assets:
        raise PortfolioImportError("No valid assets found in portfolio file.")

    config = _template_config(template)
    config["assets"] = assets
    if title:
        config["title"] = title

    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return target


def read_portfolio_assets(input_path: str | Path) -> list[dict[str, Any]]:
    path = Path(input_path)
    if not path.exists():
        raise PortfolioImportError(f"Portfolio file not found: {path}")
    frame = _read_frame(path)
    if frame.empty:
        return []

    normalized_columns = {_normalize_column(column): column for column in frame.columns}
    resolved = _resolve_columns(normalized_columns)
    if "symbol" not in resolved:
        raise PortfolioImportError("Portfolio file must include a symbol/ticker/code column.")

    assets: list[dict[str, Any]] = []
    for _, row in frame.iterrows():
        symbol = _symbol_text(row.get(resolved["symbol"]))
        if not symbol:
            continue
        name_column = resolved.get("name")
        row_name = _clean_text(row.get(name_column)) if name_column else None
        normalized_symbol = _normalize_symbol(symbol, row_name)
        asset: dict[str, Any] = {
            "symbol": normalized_symbol,
            "market": _clean_text(row.get(resolved.get("market"))) or _infer_market(normalized_symbol),
        }
        for key in ["name", "currency", "note"]:
            column = resolved.get(key)
            value = _clean_text(row.get(column)) if column else None
            if value:
                asset[key] = value
        for key in ["quantity", "cost_basis"]:
            column = resolved.get(key)
            value = _number(row.get(column)) if column else None
            if value is not None:
                asset[key] = value
        tags_column = resolved.get("tags")
        tags = _tags(row.get(tags_column)) if tags_column else []
        if tags:
            asset["tags"] = tags
        assets.append(asset)
    return assets


def _has_cjk(text: str) -> bool:
    return bool(re.search(r"[一-鿿]", text))


def resolve_fund_records(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Resolve OTC fund codes from transcribed names via the fund directory.

    Fund-app holding lists usually show no codes, and vision models invent
    them when pressed (observed: 6/6 fabricated codes from a real 蚂蚁财富
    screenshot). So: a record with a Chinese name and no symbol gets its code
    looked up by name; a record whose claimed `.OF` code contradicts the
    directory name is treated as fabricated and re-resolved. Returns
    (resolved_records, unresolved_assets) — unresolved funds are surfaced as
    blank-symbol rows for the user to complete instead of being dropped.
    """
    resolved: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    for record in records:
        symbol = _symbol_text(record.get("symbol")) or ""
        name = _clean_text(record.get("name")) or ""
        is_cn_fund_name = bool(name) and _has_cjk(name)

        if symbol and is_otc_fund_symbol(symbol) and is_cn_fund_name:
            entry = fund_directory_lookup(symbol.upper()[:6])
            if entry is None or fund_name_similarity(name, entry[0]) < _FUND_CODE_NAME_MIN_SIMILARITY:
                symbol = ""  # fabricated code; fall through to name matching
        if symbol:
            resolved.append(record)
            continue
        if not is_cn_fund_name:
            continue

        match = match_fund_by_name(name)
        if match:
            fixed = dict(record)
            fixed["symbol"] = f"{match[0]}.OF"
            fixed["market"] = "CN"
            resolved.append(fixed)
        else:
            pending: dict[str, Any] = {"symbol": "", "name": name, "market": "CN"}
            quantity = _number(record.get("quantity"))
            cost_basis = _number(record.get("cost_basis"))
            if quantity is not None:
                pending["quantity"] = quantity
            if cost_basis is not None:
                pending["cost_basis"] = cost_basis
            unresolved.append(pending)
    return resolved, unresolved


def normalize_portfolio_assets(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    assets: list[dict[str, Any]] = []
    index_by_symbol: dict[str, int] = {}
    for record in records:
        symbol = _symbol_text(record.get("symbol"))
        if not symbol:
            continue
        normalized_symbol = _normalize_symbol(symbol, _clean_text(record.get("name")))
        asset: dict[str, Any] = {
            "symbol": normalized_symbol,
            "market": _clean_text(record.get("market")) or _infer_market(normalized_symbol),
        }
        for key in ["name", "currency", "note"]:
            value = _clean_text(record.get(key))
            if value:
                asset[key] = value
        for key in ["quantity", "cost_basis"]:
            value = _number(record.get(key))
            if value is not None:
                asset[key] = value
        raw_tags = record.get("tags")
        tags = [str(item).strip() for item in raw_tags if str(item).strip()] if isinstance(raw_tags, list) else _tags(raw_tags)
        if tags:
            asset["tags"] = tags
        if normalized_symbol in index_by_symbol:
            index = index_by_symbol[normalized_symbol]
            assets[index] = _merge_portfolio_asset(assets[index], asset)
        else:
            index_by_symbol[normalized_symbol] = len(assets)
            assets.append(asset)
    return assets


def _merge_portfolio_asset(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    merged = dict(left)
    left_qty = _number(left.get("quantity"))
    right_qty = _number(right.get("quantity"))
    left_cost = _number(left.get("cost_basis"))
    right_cost = _number(right.get("cost_basis"))
    if left_qty is not None and right_qty is not None:
        total_qty = left_qty + right_qty
        merged["quantity"] = total_qty
        if total_qty and left_cost is not None and right_cost is not None:
            merged["cost_basis"] = round((left_qty * left_cost + right_qty * right_cost) / total_qty, 6)
    for key in ["name", "market", "currency", "note", "quantity", "cost_basis"]:
        if key not in merged and key in right:
            merged[key] = right[key]
    tags = list(dict.fromkeys([*(left.get("tags") or []), *(right.get("tags") or [])]))
    if tags:
        merged["tags"] = tags
    return merged


def _read_frame(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path, dtype=str)
    if suffix == ".tsv":
        return pd.read_csv(path, sep="\t", dtype=str)
    if suffix in {".xlsx", ".xlsm"}:
        try:
            return pd.read_excel(path)
        except ImportError as exc:
            raise PortfolioImportError("Excel import requires openpyxl. Run `pip install -e .[excel]`.") from exc
    raise PortfolioImportError(f"Unsupported portfolio file type: {suffix}. Use .csv, .tsv, or .xlsx.")


def _resolve_columns(columns: dict[str, str]) -> dict[str, str]:
    resolved: dict[str, str] = {}
    for field, aliases in COLUMN_ALIASES.items():
        normalized_aliases = {_normalize_column(alias) for alias in aliases}
        for alias in normalized_aliases:
            if alias in columns:
                resolved[field] = columns[alias]
                break
    return resolved


def _template_config(template: str) -> dict[str, Any]:
    if template not in SAMPLE_CONFIGS:
        names = ", ".join(sorted(SAMPLE_CONFIGS))
        raise PortfolioImportError(f"Unknown template '{template}'. Available templates: {names}")
    return yaml.safe_load(SAMPLE_CONFIGS[template]) or {}


def _normalize_column(value: object) -> str:
    return re.sub(r"[\s_\-./]+", "", str(value).strip().lower())


def _clean_text(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def _symbol_text(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, (int, float)) and float(value).is_integer():
        number = int(value)
        if 0 <= number <= 999999:
            return f"{number:06d}"
    text = str(value).strip()
    if re.fullmatch(r"\d+\.0", text):
        number = int(float(text))
        if 0 <= number <= 999999:
            return f"{number:06d}"
    if re.fullmatch(r"\d{1,6}", text):
        return f"{int(text):06d}"
    return text or None


def _number(value: object) -> float | None:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    text = re.sub(r"[,$¥￥€£\s]", "", text)
    if text.endswith("%"):
        return float(text[:-1]) / 100
    try:
        return float(text)
    except ValueError:
        return None


def _tags(value: object) -> list[str]:
    text = _clean_text(value)
    if not text:
        return []
    return [item.strip() for item in re.split(r"[,;|，；、]", text) if item.strip()]


def _normalize_symbol(symbol: str, name: str | None = None) -> str:
    text = symbol.strip().upper()
    if re.fullmatch(r"\d{6}", text):
        return normalize_cn_code(text, name)
    return text
