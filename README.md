# wechat-article-bot

微信公众号每日推文自动生成系统。

每天定时从 RSS/网站采集热点内容，通过 AI (Claude) 改写生成推文，创建微信草稿并通知人工审核，确认后一键发布。

## 功能

- **内容采集**：RSS 订阅 + 网页爬虫，自动聚合多源热点
- **AI 改写**：两阶段生成（选题→正文），基于 Claude API
- **微信集成**：自动创建草稿，支持一键发布
- **人工审核**：Web 预览页面 + 通知推送，审核后发布
- **去重防刷**：SQLite 记录历史，避免重复内容

## 技术方案

详见 [docs/technical-design.md](docs/technical-design.md)

## 快速开始

> 🚧 开发中，敬请期待

## License

MIT
