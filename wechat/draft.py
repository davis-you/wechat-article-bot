import logging

import httpx
import markdown
from premailer import transform

from db.models import Article
from .auth import get_access_token
from .media import process_images_in_html

logger = logging.getLogger(__name__)

DRAFT_ADD_URL = "https://api.weixin.qq.com/cgi-bin/draft/add"

WECHAT_CSS = """
<style>
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; font-size: 16px; line-height: 1.8; color: #333; padding: 0 16px; }
h1 { font-size: 22px; font-weight: bold; margin: 24px 0 16px; }
h2 { font-size: 20px; font-weight: bold; margin: 20px 0 12px; border-left: 4px solid #07c160; padding-left: 12px; }
h3 { font-size: 18px; font-weight: bold; margin: 16px 0 8px; }
p { margin: 12px 0; }
blockquote { border-left: 4px solid #ddd; padding-left: 16px; color: #666; margin: 12px 0; }
code { background: #f5f5f5; padding: 2px 6px; border-radius: 3px; font-size: 14px; }
pre { background: #f5f5f5; padding: 16px; border-radius: 6px; overflow-x: auto; }
img { max-width: 100%; height: auto; border-radius: 4px; margin: 12px 0; }
a { color: #576b95; text-decoration: none; }
</style>
"""


def md_to_wechat_html(md_content: str) -> str:
    """Convert Markdown to WeChat-compatible HTML with inline styles."""
    html_body = markdown.markdown(
        md_content,
        extensions=["extra", "codehilite", "nl2br"],
    )
    full_html = f"<html><head>{WECHAT_CSS}</head><body>{html_body}</body></html>"
    inlined = transform(full_html, remove_classes=True)
    # Extract body content only
    if "<body" in inlined:
        start = inlined.index(">", inlined.index("<body")) + 1
        end = inlined.index("</body>")
        return inlined[start:end]
    return inlined


async def create_draft(config: dict, article: Article) -> str:
    """Create a WeChat draft and return media_id."""
    html = md_to_wechat_html(article.content_md)
    html = await process_images_in_html(config, html)
    article.content_html = html

    token = await get_access_token(config)

    payload = {
        "articles": [
            {
                "title": article.title,
                "author": "",
                "digest": article.digest or article.content_md[:120],
                "content": html,
                "content_source_url": "",
                "need_open_comment": 1,
                "only_fans_can_comment": 0,
            }
        ]
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            DRAFT_ADD_URL,
            params={"access_token": token},
            json=payload,
        )
        resp.raise_for_status()
        result = resp.json()

    if "media_id" not in result:
        raise RuntimeError(f"创建草稿失败: {result}")

    logger.info("草稿创建成功, media_id: %s", result["media_id"])
    return result["media_id"]
