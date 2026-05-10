import json
import logging
import os
import time
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

TOKEN_URL = "https://api.weixin.qq.com/cgi-bin/token"


async def get_access_token(config: dict) -> str:
    cache_file = Path(config["wechat"].get("token_cache_file", "/tmp/wechat_token.json"))

    if cache_file.exists():
        data = json.loads(cache_file.read_text())
        if data.get("expires_at", 0) > time.time() + 60:
            return data["access_token"]

    app_id = os.environ["WECHAT_APP_ID"]
    app_secret = os.environ["WECHAT_APP_SECRET"]

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(TOKEN_URL, params={
            "grant_type": "client_credential",
            "appid": app_id,
            "secret": app_secret,
        })
        resp.raise_for_status()
        result = resp.json()

    if "access_token" not in result:
        raise RuntimeError(f"获取 access_token 失败: {result}")

    token_data = {
        "access_token": result["access_token"],
        "expires_at": time.time() + result.get("expires_in", 7200),
    }
    cache_file.write_text(json.dumps(token_data))
    logger.info("access_token 已刷新")

    return result["access_token"]
