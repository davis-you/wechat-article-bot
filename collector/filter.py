from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .collector import RawItem

logger = logging.getLogger(__name__)


def filter_items(items: list["RawItem"], filter_config: dict) -> list["RawItem"]:
    keywords_include = [k.lower() for k in filter_config.get("keywords_include", [])]
    keywords_exclude = [k.lower() for k in filter_config.get("keywords_exclude", [])]
    min_length = filter_config.get("min_length", 0)

    result = []
    for item in items:
        text = f"{item.title} {item.summary} {item.content}".lower()

        if min_length and len(item.content or item.summary) < min_length:
            continue

        if keywords_exclude and any(kw in text for kw in keywords_exclude):
            continue

        if keywords_include and not any(kw in text for kw in keywords_include):
            continue

        result.append(item)

    return result
