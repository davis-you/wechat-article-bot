import json
import logging
import os
import time
from pathlib import Path

import httpx

from db.models import Article

logger = logging.getLogger(__name__)

TOKEN_URL = "https://qyapi.weixin.qq.com/cgi-bin/gettoken"
SEND_URL = "https://qyapi.weixin.qq.com/cgi-bin/message/send"
TOKEN_CACHE_FILE = Path("/tmp/wecom_token.json")


async def _get_access_token() -> str:
    if TOKEN_CACHE_FILE.exists():
        data = json.loads(TOKEN_CACHE_FILE.read_text())
        if data.get("expires_at", 0) > time.time() + 300:
            return data["access_token"]

    corp_id = os.environ["WECHAT_WORK_CORP_ID"]
    secret = os.environ["WECHAT_WORK_SECRET"]

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(TOKEN_URL, params={
            "corpid": corp_id,
            "corpsecret": secret,
        })
        resp.raise_for_status()
        result = resp.json()

    if result.get("errcode", 0) != 0:
        raise RuntimeError(f"获取企业微信 access_token 失败: {result}")

    token = result["access_token"]
    expires_in = result.get("expires_in", 7200)
    TOKEN_CACHE_FILE.write_text(json.dumps({
        "access_token": token,
        "expires_at": time.time() + expires_in,
    }))

    return token


async def _send_message(content: str) -> None:
    admin_user_id = os.environ["WECHAT_WORK_ADMIN_USER_ID"]
    agent_id = int(os.environ["WECHAT_WORK_AGENT_ID"])

    token = await _get_access_token()
    payload = {
        "touser": admin_user_id,
        "msgtype": "text",
        "agentid": agent_id,
        "text": {"content": content},
    }

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            SEND_URL,
            params={"access_token": token},
            json=payload,
        )
        resp.raise_for_status()
        result = resp.json()

    # token 过期，清缓存重试一次
    if result.get("errcode") in (42001, 40014):
        TOKEN_CACHE_FILE.unlink(missing_ok=True)
        token = await _get_access_token()
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                SEND_URL,
                params={"access_token": token},
                json=payload,
            )
            resp.raise_for_status()
            result = resp.json()

    if result.get("errcode", 0) != 0:
        logger.error("企业微信消息发送失败: %s", result)
    else:
        logger.info("企业微信消息发送成功: touser=%s", admin_user_id)


async def send_review_notification(
    config: dict, article: Article, article_id: int
) -> None:
    base_url = os.environ.get("WEB_PUBLIC_URL", "").rstrip("/")
    if not base_url:
        logger.warning("未配置 WEB_PUBLIC_URL，无法生成审核链接")
        return

    token = os.environ.get("WEB_SECRET_TOKEN", "")
    qs = f"?token={token}" if token else ""

    review_url = f"{base_url}/review/{article_id}{qs}"
    publish_url = f"{base_url}/action/publish/{article_id}{qs}"
    skip_url = f"{base_url}/action/skip/{article_id}{qs}"

    digest = (article.digest or article.content_md[:150]).replace("\n", " ")

    content = (
        f"📝 今日推文待审核\n"
        f"标题：{article.title}\n"
        f"摘要：{digest[:120]}...\n\n"
        f"查看全文👇\n{review_url}\n\n"
        f"确认发布👇\n{publish_url}\n\n"
        f"拒绝👇\n{skip_url}"
    )

    await _send_message(content)
