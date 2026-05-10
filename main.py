import asyncio
import logging
from pathlib import Path

import yaml
from dotenv import load_dotenv

from collector import collect_articles
from writer import generate_article
from wechat.draft import create_draft
from notifier import send_review_notification
from db.models import init_db, save_article

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

ROOT = Path(__file__).parent
CONFIG_PATH = ROOT / "config.yaml"


def load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


async def run():
    config = load_config()
    db = init_db(ROOT / "data.db")

    logger.info("Step 1: 采集内容")
    materials = await collect_articles(config, db)
    if not materials:
        logger.warning("今日无可用素材，跳过生成")
        return

    logger.info("Step 2: AI 生成推文 (素材数: %d)", len(materials))
    article = await generate_article(config, materials)

    logger.info("Step 3: 创建微信草稿")
    media_id = await create_draft(config, article)

    logger.info("Step 4: 保存记录")
    article_id = save_article(db, article, media_id)

    logger.info("Step 5: 发送审核通知")
    await send_review_notification(config, article, article_id)

    logger.info("完成！等待人工审核发布。")


def main():
    asyncio.run(run())


if __name__ == "__main__":
    main()
