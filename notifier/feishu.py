import logging
import os

import httpx

from db.models import Article

logger = logging.getLogger(__name__)


async def send_review_notification(
    config: dict, article: Article, article_id: int
) -> None:
    webhook_url = os.environ.get("FEISHU_WEBHOOK_URL")
    if not webhook_url:
        logger.warning("未配置 FEISHU_WEBHOOK_URL，跳过通知")
        return

    web_cfg = config.get("web", {})
    host = web_cfg.get("host", "0.0.0.0")
    port = web_cfg.get("port", 8080)
    token = os.environ.get("WEB_SECRET_TOKEN", "")
    review_url = f"http://{host}:{port}/review/{article_id}?token={token}"

    card = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": "📝 今日推文待审核"},
                "template": "blue",
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**标题**: {article.title}\n\n**摘要**: {article.digest[:150]}...",
                    },
                },
                {"tag": "hr"},
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "查看并发布"},
                            "url": review_url,
                            "type": "primary",
                        }
                    ],
                },
            ],
        },
    }

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(webhook_url, json=card)
        resp.raise_for_status()

    logger.info("审核通知已发送")
