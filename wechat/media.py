import logging
import re

import httpx

from .auth import get_access_token

logger = logging.getLogger(__name__)

UPLOAD_IMG_URL = "https://api.weixin.qq.com/cgi-bin/media/uploadimg"


async def upload_image_from_url(config: dict, image_url: str) -> str:
    """Download an image and upload it to WeChat, return the WeChat media URL."""
    token = await get_access_token(config)

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        img_resp = await client.get(image_url)
        img_resp.raise_for_status()

    content_type = img_resp.headers.get("content-type", "image/png")
    ext = "png"
    if "jpeg" in content_type or "jpg" in content_type:
        ext = "jpg"
    elif "gif" in content_type:
        ext = "gif"

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            UPLOAD_IMG_URL,
            params={"access_token": token},
            files={"media": (f"image.{ext}", img_resp.content, content_type)},
        )
        resp.raise_for_status()
        result = resp.json()

    if "url" not in result:
        logger.error("图片上传失败: %s", result)
        return image_url

    return result["url"]


async def process_images_in_html(config: dict, html: str) -> str:
    """Find all external image URLs in HTML and replace with WeChat media URLs."""
    img_pattern = re.compile(r'<img[^>]+src="(https?://[^"]+)"')
    urls = img_pattern.findall(html)

    for url in urls:
        try:
            wechat_url = await upload_image_from_url(config, url)
            html = html.replace(url, wechat_url)
        except Exception as e:
            logger.warning("图片处理失败 %s: %s", url, e)

    return html
