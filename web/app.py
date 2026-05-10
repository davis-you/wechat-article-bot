import os
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path

import yaml
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from db.models import get_article, update_article_status, init_db
from wechat.publish import publish_article

ROOT = Path(__file__).parent.parent
CONFIG_PATH = ROOT / "config.yaml"
DB_PATH = ROOT / "data.db"

_db: sqlite3.Connection | None = None
_config: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _db, _config
    _db = init_db(DB_PATH)
    with open(CONFIG_PATH) as f:
        _config = yaml.safe_load(f)
    yield
    if _db:
        _db.close()


app = FastAPI(title="WeChat Article Review", lifespan=lifespan)
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def verify_token(token: str) -> None:
    expected = os.environ.get("WEB_SECRET_TOKEN", "")
    if not expected:
        return
    if token != expected:
        raise HTTPException(status_code=403, detail="Invalid token")


@app.get("/review/{article_id}", response_class=HTMLResponse)
async def review_page(request: Request, article_id: int, token: str = Query("")):
    verify_token(token)
    article = get_article(_db, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    return templates.TemplateResponse("review.html", {
        "request": request,
        "article": article,
        "token": token,
    })


@app.post("/publish/{article_id}")
async def publish(article_id: int, token: str = Query("")):
    verify_token(token)
    article = get_article(_db, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    if article["status"] == "published":
        return {"message": "已发布", "status": "published"}

    media_id = article["wechat_media_id"]
    if not media_id:
        raise HTTPException(status_code=400, detail="No draft media_id")

    result = await publish_article(_config, media_id)
    update_article_status(_db, article_id, "published")
    return {"message": "发布成功", "publish_id": result.get("publish_id")}


@app.post("/skip/{article_id}")
async def skip(article_id: int, token: str = Query("")):
    verify_token(token)
    update_article_status(_db, article_id, "skipped")
    return {"message": "已跳过"}


@app.get("/action/publish/{article_id}", response_class=HTMLResponse)
async def action_publish_page(request: Request, article_id: int, token: str = Query("")):
    verify_token(token)
    article = get_article(_db, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    return templates.TemplateResponse("action.html", {
        "request": request,
        "article": article,
        "token": token,
        "action": "publish",
        "action_label": "确认发布",
        "action_desc": "确认后将立即发布到公众号",
        "icon": "🚀",
        "btn_color": "#07c160",
    })


@app.get("/action/skip/{article_id}", response_class=HTMLResponse)
async def action_skip_page(request: Request, article_id: int, token: str = Query("")):
    verify_token(token)
    article = get_article(_db, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    return templates.TemplateResponse("action.html", {
        "request": request,
        "article": article,
        "token": token,
        "action": "skip",
        "action_label": "拒绝发布",
        "action_desc": "跳过今天的推文，不会发布",
        "icon": "🚫",
        "btn_color": "#ff4d4f",
    })
