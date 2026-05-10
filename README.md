# wechat-article-bot

微信公众号每日推文自动生成系统。

每天定时从 RSS/网站采集热点内容，通过 AI (Claude) 改写生成推文，创建微信草稿并通知人工审核，确认后一键发布。

## 功能

- **内容采集**：RSS 订阅 + 网页爬虫，自动聚合多源热点
- **AI 改写**：两阶段生成（选题→正文），基于 Claude API
- **微信集成**：自动创建草稿，支持一键发布
- **人工审核**：Web 预览页面 + 通知推送，审核后发布
- **去重防刷**：SQLite 记录历史，避免重复内容

## 架构

```
RSS/网站 → 内容采集 → AI改写(Claude) → 微信草稿 → 飞书通知 → Web审核页 → 一键发布
```

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/davis-you/wechat-article-bot.git
cd wechat-article-bot
```

### 2. 安装依赖

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入：
# - WECHAT_APP_ID / WECHAT_APP_SECRET（微信公众平台获取）
# - ANTHROPIC_API_KEY（Anthropic 控制台获取）
# - FEISHU_WEBHOOK_URL（飞书机器人 webhook）
# - WEB_SECRET_TOKEN（自定义审核页面访问密钥）
```

### 4. 自定义配置

编辑 `config.yaml`：
- 添加/修改 RSS 源
- 调整关键词过滤规则
- 修改 AI 写作风格和字数要求

### 5. 手动运行一次

```bash
python main.py
```

### 6. 启动审核 Web 服务

```bash
uvicorn web.app:app --host 0.0.0.0 --port 8080
```

### 7. 服务器部署（一键）

```bash
# 在服务器上执行
sudo bash deploy/setup.sh
```

自动完成：代码拉取、依赖安装、cron 定时任务、systemd 服务配置。

## 项目结构

```
├── main.py              # 入口：串联整个流程
├── config.yaml          # 配置：RSS源、prompt模板、风格参数
├── collector/           # 内容采集（RSS + 爬虫 + 过滤）
├── writer/              # AI 改写（Claude 两阶段生成）
├── wechat/              # 微信API（token、图片、草稿、发布）
├── notifier/            # 审核通知（飞书 webhook）
├── web/                 # 审核页面（FastAPI + 模板）
├── db/                  # 数据存储（SQLite）
├── deploy/              # 部署配置（cron + systemd + 脚本）
└── docs/                # 技术方案文档
```

## 技术方案

详见 [docs/technical-design.md](docs/technical-design.md)

## License

MIT
