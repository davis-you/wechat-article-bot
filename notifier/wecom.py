import logging
import os

import httpx

from db.models import Article

logger = logging.getLogger(__name__)


def _get_public_base_url() -> str:
    url = os.environ.get("WEB_PUBLIC_URL", "").rstrip("/")
    if not url:
        raise RuntimeError("未配置 WEB_PUBLIC_URL 环境变量，无法生成审核链接")
    return url


async def send_review_notification(
    config: dict, article: Article, article_id: int
) -> None:
    webhook_url = os.environ.get("WECOM_WEBHOOK_URL")
    if not webhook_url:
        logger.warning("未配置 WECOM_WEBHOOK_URL，跳过通知")
        return

    base_url = _get_public_base_url()
    token = os.environ.get("WEB_SECRET_TOKEN", "")
    qs = f"?token={token}" if token else ""

    review_url = f"{base_url}/review/{article_id}{qs}"
    publish_url = f"{base_url}/action/publish/{article_id}{qs}"
    skip_url = f"{base_url}/action/skip/{article_id}{qs}"

    digest = (article.digest or article.content_md[:150]).replace("\n", " ")

    content = (
        f"## 📝 今日推文待审核\n"
        f"**标题**: {article.title}\n"
        f"**摘要**: {digest[:120]}...\n\n"
        f"> [👀 查看全文]({review_url})\n"
        f"> [✅ 确认发布]({publish_url})\n"
        f"> [❌ 拒绝]({skip_url})"
    )

    payload = {
        "msgtype": "markdown",
        "markdown": {"content": content},
    }

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(webhook_url, json=payload)
        resp.raise_for_status()
        result = resp.json()

    if result.get("errcode", 0) != 0:
        logger.error("企业微信通知发送失败: %s", result)
    else:
        logger.info("审核通知已发送到企业微信")
