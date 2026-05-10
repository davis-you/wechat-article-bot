import logging

import httpx

from .auth import get_access_token

logger = logging.getLogger(__name__)

PUBLISH_URL = "https://api.weixin.qq.com/cgi-bin/freepublish/submit"


async def publish_article(config: dict, media_id: str) -> dict:
    """Submit a draft for publishing. Returns publish_id."""
    token = await get_access_token(config)

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            PUBLISH_URL,
            params={"access_token": token},
            json={"media_id": media_id},
        )
        resp.raise_for_status()
        result = resp.json()

    if result.get("errcode", 0) != 0:
        raise RuntimeError(f"发布失败: {result}")

    logger.info("发布提交成功, publish_id: %s", result.get("publish_id"))
    return result
