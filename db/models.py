import hashlib
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class Article:
    title: str
    content_md: str
    content_html: str = ""
    cover_url: str = ""
    digest: str = ""


SCHEMA = """
CREATE TABLE IF NOT EXISTS collected_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url_hash TEXT UNIQUE NOT NULL,
    source TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    collected_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    content_md TEXT NOT NULL,
    content_html TEXT,
    wechat_media_id TEXT,
    status TEXT DEFAULT 'draft',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    published_at DATETIME
);
"""


def init_db(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def url_hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def is_url_collected(conn: sqlite3.Connection, url: str) -> bool:
    cur = conn.execute(
        "SELECT 1 FROM collected_items WHERE url_hash = ?", (url_hash(url),)
    )
    return cur.fetchone() is not None


def mark_url_collected(
    conn: sqlite3.Connection, url: str, source: str, title: str
) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO collected_items (url_hash, source, title, url) VALUES (?, ?, ?, ?)",
        (url_hash(url), source, title, url),
    )
    conn.commit()


def save_article(
    conn: sqlite3.Connection, article: Article, media_id: str
) -> int:
    cur = conn.execute(
        "INSERT INTO articles (title, content_md, content_html, wechat_media_id) VALUES (?, ?, ?, ?)",
        (article.title, article.content_md, article.content_html, media_id),
    )
    conn.commit()
    return cur.lastrowid


def update_article_status(
    conn: sqlite3.Connection, article_id: int, status: str
) -> None:
    published_at = datetime.now().isoformat() if status == "published" else None
    conn.execute(
        "UPDATE articles SET status = ?, published_at = ? WHERE id = ?",
        (status, published_at, article_id),
    )
    conn.commit()


def get_article(conn: sqlite3.Connection, article_id: int) -> dict | None:
    cur = conn.execute("SELECT * FROM articles WHERE id = ?", (article_id,))
    row = cur.fetchone()
    return dict(row) if row else None
