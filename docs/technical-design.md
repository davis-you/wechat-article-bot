# 微信公众号每日推文自动生成系统 — 技术方案

> **版本**: v0.1.0 | **最后更新**: 2026-05-11 | **状态**: 设计中

## 1. 系统概览

```
┌─────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  内容采集     │───▶│  AI 改写生成   │───▶│  草稿 + 通知  │───▶│  人工审核发布  │
│  (RSS/爬虫)  │    │  (Claude API) │    │  (微信API)    │    │  (飞书/微信)  │
└─────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
      18:00              18:05              18:10              人工确认后
```

**核心流程**：每天定时采集热点 → AI 改写成推文 → 创建微信草稿 → 通知审核 → 确认后发布。

### 关键约束

| 约束 | 说明 |
|------|------|
| 公众号类型 | 认证订阅号 |
| 内容来源 | RSS/网站聚合 + AI 改写 |
| 发布方式 | 半自动（人工审核后发布） |
| 部署环境 | 轻量云服务器 |

---

## 2. 技术栈

| 组件 | 技术选型 | 理由 |
|------|---------|------|
| 语言 | Python 3.11+ | 生态丰富，RSS/爬虫/API 库齐全 |
| 内容采集 | `feedparser` + `httpx` + `BeautifulSoup` | RSS 解析 + 网页抓取 |
| AI 改写 | Claude API (Sonnet 4.6) | 性价比高，中文写作质量好 |
| 微信接口 | 微信公众平台 API (草稿箱 + 发布) | 认证订阅号可用 |
| 定时调度 | `cron` + `systemd timer` | 轻量服务器原生方案 |
| 审核通知 | 飞书机器人 webhook / 企业微信机器人 | 推送审核链接和预览 |
| 数据存储 | SQLite | 记录已采集/已发布内容，防重复 |
| 审核页面 | FastAPI + Jinja2 | 轻量 Web 预览 + 一键发布 |
| 配置管理 | YAML | 主题、RSS 源、prompt 模板易维护 |

---

## 3. 模块设计

### 3.1 内容采集模块 (`collector/`)

从多个 RSS 源和网站抓取当日热点内容，过滤筛选后作为 AI 改写素材。

**配置示例** (`config.yaml`):

```yaml
sources:
  - type: rss
    name: "36kr"
    url: "https://36kr.com/feed"
    category: "科技"
    max_items: 10

  - type: rss
    name: "少数派"
    url: "https://sspai.com/feed"
    category: "效率"

  - type: web_scrape
    name: "微博热搜"
    url: "https://weibo.com/ajax/side/hotSearch"
    parser: "weibo_hot"  # 对应自定义解析器

content_filter:
  keywords_include: ["AI", "科技", "互联网"]  # 至少命中一个
  keywords_exclude: ["广告", "推广"]
  min_length: 100
```

**核心逻辑**：
- 从多个 RSS 源拉取最新文章，提取标题 + 摘要 + 正文
- 用 SQLite 记录已采集 URL 的 hash，避免重复处理
- 按关键词过滤，筛选出当天 top 5-8 条素材
- 每条素材提取：标题、摘要、正文、来源、发布时间

### 3.2 AI 改写模块 (`writer/`)

采用**两阶段生成**策略，质量显著优于一次性生成。

**阶段 1: 选题 + 大纲**

```
你是一个微信公众号编辑。以下是今天采集到的 {count} 条素材：
{materials}

请从中选择 3 条最有价值的素材，生成一篇推文的大纲：
- 标题（20字以内，有吸引力）
- 结构（引子 → 核心内容 → 观点总结）
- 每个素材如何融合进文章

输出 JSON 格式。
```

**阶段 2: 正文生成**

```
根据以下大纲和素材，撰写一篇微信公众号推文。

要求：
- 风格：{style}（如"专业但不枯燥，适当加入类比"）
- 字数：1500-2500字
- 使用 Markdown 格式
- 每个关键信息标注来源
- 结尾引导读者互动

大纲：{outline}
素材原文：{sources}
```

**关键设计**：
- Prompt 模板化，放在 YAML 配置里，方便调整风格
- 使用 Claude Sonnet 4.6，成本约 ¥0.3-0.5/篇
- 加入重试机制：如果生成内容过短或格式错误，自动重试一次

### 3.3 微信公众号接口模块 (`wechat/`)

认证订阅号可用的关键 API：

| 接口 | 方法 | 用途 |
|------|------|------|
| `/cgi-bin/token` | GET | 获取 access_token |
| `/cgi-bin/media/uploadimg` | POST | 上传图文素材中的图片 |
| `/cgi-bin/draft/add` | POST | 新建草稿 |
| `/cgi-bin/freepublish/submit` | POST | 发布 |

**核心流程**：

```
Markdown 正文
  → 转换为微信兼容 HTML（内联样式）
  → 提取图片，上传到微信获取 media URL，替换原图链接
  → 调用草稿接口创建草稿
  → 返回 media_id
  → 人工确认后调用发布接口
```

**Markdown → 微信 HTML 注意事项**：
- 微信编辑器不支持标准 HTML，需要用内联 CSS 样式
- 建议自写转换器或使用 `weixin-markdown` 库
- 图片必须上传到微信服务器，外链会被屏蔽

### 3.4 审核通知模块 (`notifier/`)

生成草稿后，推送通知供人工审核。

**通知内容**：
- 推文标题
- 正文摘要（前 200 字）
- 审核页面链接
- 操作选项：确认发布 / 修改后发布 / 跳过今天

**审核方案**：简易 Web 页面（FastAPI），预览推文排版效果，点击按钮调用发布 API。不依赖特定 IM 平台，通用性好。

### 3.5 数据存储 (`db/`)

```sql
CREATE TABLE collected_items (
    id INTEGER PRIMARY KEY,
    url_hash TEXT UNIQUE,
    source TEXT,
    title TEXT,
    content TEXT,
    collected_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE articles (
    id INTEGER PRIMARY KEY,
    title TEXT,
    content_md TEXT,
    content_html TEXT,
    wechat_media_id TEXT,
    status TEXT DEFAULT 'draft',  -- draft / published / skipped
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    published_at DATETIME
);
```

---

## 4. 项目结构

```
wechat-article-bot/
├── main.py                    # 入口：串联整个流程
├── config.yaml                # 配置：RSS源、prompt模板、风格参数
├── requirements.txt
├── collector/
│   ├── __init__.py
│   ├── rss.py                 # RSS 采集
│   ├── scraper.py             # 网页爬虫
│   └── filter.py              # 内容过滤 & 去重
├── writer/
│   ├── __init__.py
│   ├── topic_selector.py      # 选题 (Claude 阶段1)
│   └── article_generator.py   # 正文生成 (Claude 阶段2)
├── wechat/
│   ├── __init__.py
│   ├── auth.py                # access_token 管理
│   ├── media.py               # 图片上传
│   ├── draft.py               # 草稿管理
│   └── publish.py             # 发布
├── notifier/
│   ├── __init__.py
│   └── feishu.py              # 飞书通知 (或 wechat_work.py)
├── web/
│   ├── app.py                 # FastAPI 审核页面
│   └── templates/
│       └── review.html        # 预览 + 发布按钮
├── db/
│   ├── __init__.py
│   └── models.py              # SQLite ORM
└── deploy/
    ├── crontab                # 定时任务配置
    └── wechat-bot-web.service # systemd 配置
```

---

## 5. 部署方案

```
轻量云服务器 (2C2G)
├── /opt/wechat-bot/           # 项目目录
├── crontab: 0 18 * * *        # 每天18:00触发采集+生成
└── systemd: wechat-bot-web    # 审核页面常驻服务
```

### 成本估算

| 项目 | 月费用 |
|------|--------|
| 云服务器 (2C2G) | ~¥50-80 |
| Claude API (Sonnet, 30篇/月) | ~¥10-15 |
| **合计** | **~¥60-95/月** |

---

## 6. 安全和限流

- **access_token 缓存**：微信 token 有效期 2 小时，用文件/内存缓存，避免频繁请求
- **API 调用限流**：微信接口有日调用上限，加 rate limiter（IP + 用户维度）
- **Claude API 限流**：单次任务限制 2-3 次调用，控制成本
- **配置加密**：AppID / AppSecret / API Key 使用环境变量，不进 git
- **爬虫合规**：遵守 robots.txt，请求间隔 ≥2 秒，标注 User-Agent
- **审核页面鉴权**：Web 审核页面加 token 校验，防止未授权访问

---

## 7. 后续扩展

- [ ] **数据分析**：接入阅读量/互动数据，AI 分析选题效果，自动优化选题策略
- [ ] **多账号支持**：配置文件加多组 AppID，同时管理多个公众号
- [ ] **封面图生成**：接入 DALL-E / Stable Diffusion 自动生成封面图
- [ ] **历史素材学习**：分析历史高阅读量文章，提炼风格特征反馈到 prompt

---

## 变更记录

| 日期 | 版本 | 变更内容 |
|------|------|---------|
| 2026-05-11 | v0.1.0 | 初始技术方案 |
