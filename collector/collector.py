import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .rss import fetch_rss_items
from .scraper import fetch_web_items
from .filter import filter_items
from db.models import is_url_collected, mark_url_collected

logger = logging.getLogger(__name__)


@dataclass
class RawItem:
    title: str
    url: str
    summary: str
    content: str
    source: str
    category: str
    published_at: datetime | None = None


async def collect_articles(config: dict, db: sqlite3.Connection) -> list[RawItem]:
    all_items: list[RawItem] = []

    for source in config["sources"]:
        try:
            if source["type"] == "rss":
                items = await fetch_rss_items(source)
            elif source["type"] == "web_scrape":
                items = await fetch_web_items(source)
            else:
                logger.warning("未知源类型: %s", source["type"])
                continue
            logger.info("从 %s 采集到 %d 条", source["name"], len(items))
            all_items.extend(items)
        except Exception as e:
            logger.error("采集 %s 失败: %s", source["name"], e)

    # 去重：排除已采集过的
    new_items = []
    for item in all_items:
        if not is_url_collected(db, item.url):
            new_items.append(item)

    # 时间过滤 + 关键词过滤
    max_age = timedelta(hours=config["content_filter"].get("max_age_hours", 48))
    cutoff = datetime.now(timezone.utc) - max_age
    new_items = [
        it for it in new_items
        if it.published_at is None or it.published_at > cutoff
    ]

    filtered = filter_items(new_items, config["content_filter"])
    logger.info("过滤后剩余 %d 条素材", len(filtered))

    # 标记为已采集
    for item in filtered:
        mark_url_collected(db, item.url, item.source, item.title)

    return filtered
