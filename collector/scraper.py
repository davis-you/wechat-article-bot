import logging

import httpx
from bs4 import BeautifulSoup

from .collector import RawItem

logger = logging.getLogger(__name__)

PARSERS = {}


def register_parser(name: str):
    def decorator(fn):
        PARSERS[name] = fn
        return fn
    return decorator


@register_parser("weibo_hot")
def parse_weibo_hot(data: dict) -> list[RawItem]:
    items = []
    realtime = data.get("data", {}).get("realtime", [])
    for entry in realtime[:10]:
        word = entry.get("word", "")
        if not word:
            continue
        items.append(RawItem(
            title=word,
            url=f"https://s.weibo.com/weibo?q=%23{word}%23",
            summary=entry.get("label_name", ""),
            content="",
            source="微博热搜",
            category="热点",
        ))
    return items


@register_parser("default")
def parse_default_html(html: str, source: dict) -> list[RawItem]:
    soup = BeautifulSoup(html, "lxml")
    items = []
    for article in soup.find_all("article")[:source.get("max_items", 10)]:
        title_el = article.find(["h1", "h2", "h3", "a"])
        if not title_el:
            continue
        title = title_el.get_text(strip=True)
        link = title_el.get("href", "")
        summary = article.get_text(strip=True)[:300]
        items.append(RawItem(
            title=title,
            url=link,
            summary=summary,
            content="",
            source=source["name"],
            category=source.get("category", ""),
        ))
    return items


async def fetch_web_items(source: dict) -> list[RawItem]:
    parser_name = source.get("parser", "default")
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        resp = await client.get(
            source["url"],
            headers={"User-Agent": "WeChatArticleBot/1.0"},
        )
        resp.raise_for_status()

    parser = PARSERS.get(parser_name)
    if not parser:
        logger.warning("未知 parser: %s，使用 default", parser_name)
        parser = PARSERS["default"]

    if parser_name == "weibo_hot":
        return parser(resp.json())
    else:
        return parser(resp.text, source)
