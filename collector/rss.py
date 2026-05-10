import asyncio
import logging
from datetime import datetime, timezone
from time import struct_time

import feedparser
import httpx

from .collector import RawItem

logger = logging.getLogger(__name__)


def _parse_time(t: struct_time | None) -> datetime | None:
    if t is None:
        return None
    try:
        return datetime(*t[:6], tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


async def fetch_rss_items(source: dict) -> list[RawItem]:
    max_items = source.get("max_items", 10)
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        resp = await client.get(source["url"], headers={"User-Agent": "WeChatArticleBot/1.0"})
        resp.raise_for_status()

    feed = await asyncio.to_thread(feedparser.parse, resp.text)
    items = []

    for entry in feed.entries[:max_items]:
        content = ""
        if hasattr(entry, "content") and entry.content:
            content = entry.content[0].get("value", "")
        elif hasattr(entry, "summary"):
            content = entry.summary or ""

        items.append(RawItem(
            title=entry.get("title", "").strip(),
            url=entry.get("link", ""),
            summary=entry.get("summary", "")[:500],
            content=content,
            source=source["name"],
            category=source.get("category", ""),
            published_at=_parse_time(entry.get("published_parsed")),
        ))

    return items
