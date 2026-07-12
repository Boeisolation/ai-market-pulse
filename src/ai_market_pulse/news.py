from __future__ import annotations

import html
import logging
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from .config import NewsSettings
from .market_data import _a_share_code
from .models import Asset, NewsItem

logger = logging.getLogger(__name__)


def fetch_news(asset: Asset, settings: NewsSettings) -> list[NewsItem]:
    if not settings.enabled:
        return []

    items: list[NewsItem] = []
    code = _a_share_code(asset)
    if code:
        # Google News queries like "600519.SS stock" return poor results for
        # mainland names; East Money's per-stock feed (via akshare) is the
        # native source. Fall through to Google News when unavailable.
        items = _fetch_eastmoney_news(code, settings)
    if not items:
        items = _fetch_google_news(asset, settings)
    return _rank_and_dedupe(items, asset, settings.items_per_asset)


def _fetch_google_news(asset: Asset, settings: NewsSettings) -> list[NewsItem]:
    query_parts = [asset.symbol]
    if asset.name and asset.name != asset.symbol:
        query_parts.append(asset.name)
    query_parts.extend(["stock", f"when:{settings.lookback_days}d"])
    query = urllib.parse.quote(" ".join(query_parts))
    language = settings.language or "en-US"
    region = settings.region or "US"
    url = (
        "https://news.google.com/rss/search?"
        f"q={query}&hl={urllib.parse.quote(language)}&gl={urllib.parse.quote(region)}"
        f"&ceid={urllib.parse.quote(region)}:{urllib.parse.quote(language.split('-')[0])}"
    )

    request = urllib.request.Request(url, headers={"User-Agent": "ai-market-pulse/0.1"})
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            payload = response.read()
    except Exception:
        return []

    try:
        root = ET.fromstring(payload)
    except ET.ParseError:
        return []

    items: list[NewsItem] = []
    for item in root.findall("./channel/item")[: settings.items_per_asset]:
        title = _text(item, "title")
        link = _text(item, "link")
        source = _text(item, "source")
        published = _text(item, "pubDate")
        if title:
            items.append(
                NewsItem(
                    title=html.unescape(title),
                    link=link or "",
                    source=html.unescape(source) if source else None,
                    published=published,
                )
            )
    return items


def _fetch_eastmoney_news(code: str, settings: NewsSettings) -> list[NewsItem]:
    try:
        import akshare as ak
    except ImportError:
        return []
    try:
        raw = ak.stock_news_em(symbol=code)
    except Exception as exc:
        logger.debug("East Money news lookup failed for %s: %s", code, exc)
        return []
    if raw is None or raw.empty:
        return []

    title_column = _first_column(raw, ["新闻标题", "标题", "title"])
    link_column = _first_column(raw, ["新闻链接", "链接", "url"])
    source_column = _first_column(raw, ["文章来源", "来源", "source"])
    published_column = _first_column(raw, ["发布时间", "时间", "datetime"])
    if title_column is None:
        return []

    items: list[NewsItem] = []
    for _, row in raw.head(settings.items_per_asset * 2).iterrows():
        title = str(row.get(title_column) or "").strip()
        if not title:
            continue
        items.append(
            NewsItem(
                title=title,
                link=str(row.get(link_column) or "") if link_column else "",
                source=str(row.get(source_column) or "").strip() or None if source_column else None,
                published=str(row.get(published_column) or "").strip() or None if published_column else None,
            )
        )
    return items


def _rank_and_dedupe(items: list[NewsItem], asset: Asset, limit: int) -> list[NewsItem]:
    needles = {asset.symbol.lower()}
    root = asset.symbol.split(".")[0].lower()
    if root:
        needles.add(root)
    if asset.name:
        needles.add(asset.name.lower())

    seen: set[str] = set()
    unique: list[NewsItem] = []
    for item in items:
        key = " ".join(item.title.lower().split())
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)

    def relevance(item: NewsItem) -> int:
        title = item.title.lower()
        return 0 if any(needle in title for needle in needles) else 1

    unique.sort(key=relevance)  # stable: keeps feed order within each tier
    return unique[:limit]


def _first_column(frame: object, candidates: list[str]) -> str | None:
    columns = list(getattr(frame, "columns", []))
    for candidate in candidates:
        if candidate in columns:
            return candidate
    return None


def _text(parent: ET.Element, tag: str) -> str | None:
    element = parent.find(tag)
    if element is None or element.text is None:
        return None
    return element.text.strip()
