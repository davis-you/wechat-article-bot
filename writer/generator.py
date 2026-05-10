import json
import logging
import os

import anthropic

from collector.collector import RawItem
from db.models import Article

logger = logging.getLogger(__name__)

TOPIC_SYSTEM = "你是一位经验丰富的微信公众号编辑，擅长从多条素材中选择最有传播力的话题并组织成清晰的文章大纲。"

TOPIC_PROMPT = """以下是今天采集到的 {count} 条素材：

{materials}

请从中选择最有价值的 {select_n} 条素材，策划一篇微信公众号推文。

输出严格的 JSON 格式：
{{
  "title": "推文标题（20字以内，有吸引力）",
  "selected_indices": [0, 2, 4],
  "outline": [
    {{"section": "引子", "brief": "用什么切入"}},
    {{"section": "核心内容1", "brief": "素材X的要点"}},
    {{"section": "核心内容2", "brief": "素材Y的要点"}},
    {{"section": "总结观点", "brief": "升华或引导互动"}}
  ]
}}"""

ARTICLE_SYSTEM = "你是一位微信公众号资深作者。根据大纲和素材写出高质量推文。"

ARTICLE_PROMPT = """请根据以下大纲和素材，撰写一篇微信公众号推文。

## 写作要求
- 风格：{style}
- 字数：{length}
- 输出纯 Markdown 格式（不要包裹在代码块中）
- 段落间留空行，适当使用小标题
- 关键信息标注来源
- 结尾引导读者留言互动

## 大纲
{outline}

## 素材原文
{sources}"""


def _format_materials(items: list[RawItem]) -> str:
    parts = []
    for i, item in enumerate(items):
        text = item.content[:800] if item.content else item.summary
        parts.append(f"[{i}] 【{item.source}】{item.title}\n{text}")
    return "\n\n---\n\n".join(parts)


async def generate_article(config: dict, materials: list[RawItem]) -> Article:
    writer_cfg = config["writer"]
    client = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    model = writer_cfg["model"]
    max_retries = writer_cfg.get("max_retries", 2)

    # Phase 1: Topic selection + outline
    materials_text = _format_materials(materials)
    topic_prompt = TOPIC_PROMPT.format(
        count=len(materials),
        materials=materials_text,
        select_n=writer_cfg.get("select_top_n", 3),
    )

    outline_data = None
    for attempt in range(max_retries + 1):
        resp = await client.messages.create(
            model=model,
            max_tokens=1024,
            system=TOPIC_SYSTEM,
            messages=[{"role": "user", "content": topic_prompt}],
        )
        text = resp.content[0].text.strip()
        # Extract JSON from possible markdown code block
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
        try:
            outline_data = json.loads(text)
            break
        except json.JSONDecodeError:
            logger.warning("选题输出 JSON 解析失败 (attempt %d)", attempt + 1)

    if not outline_data:
        raise RuntimeError("AI 选题失败：无法解析 JSON 输出")

    logger.info("选题完成: %s", outline_data["title"])

    # Phase 2: Article generation
    selected_indices = outline_data.get("selected_indices", list(range(min(3, len(materials)))))
    selected_materials = [materials[i] for i in selected_indices if i < len(materials)]

    article_prompt = ARTICLE_PROMPT.format(
        style=writer_cfg.get("style", "专业易懂"),
        length=writer_cfg.get("article_length", "1500-2500字"),
        outline=json.dumps(outline_data["outline"], ensure_ascii=False, indent=2),
        sources=_format_materials(selected_materials),
    )

    content_md = ""
    for attempt in range(max_retries + 1):
        resp = await client.messages.create(
            model=model,
            max_tokens=4096,
            system=ARTICLE_SYSTEM,
            messages=[{"role": "user", "content": article_prompt}],
        )
        content_md = resp.content[0].text.strip()
        if len(content_md) > 500:
            break
        logger.warning("生成内容过短 (%d字), 重试 (attempt %d)", len(content_md), attempt + 1)

    if len(content_md) < 500:
        raise RuntimeError("AI 生成失败：内容过短")

    logger.info("文章生成完成，长度: %d 字", len(content_md))

    return Article(
        title=outline_data["title"],
        content_md=content_md,
        digest=content_md[:120].replace("\n", " "),
    )
