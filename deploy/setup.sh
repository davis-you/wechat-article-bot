#!/bin/bash
set -e

echo "=== WeChat Article Bot 部署脚本 ==="

APP_DIR="/opt/wechat-bot"
REPO_URL="https://github.com/davis-you/wechat-article-bot.git"

# 1. 安装系统依赖
echo "[1/6] 安装系统依赖..."
apt-get update -qq && apt-get install -y -qq python3.11 python3.11-venv git

# 2. 克隆/更新代码
echo "[2/6] 拉取代码..."
if [ -d "$APP_DIR" ]; then
    cd "$APP_DIR" && git pull
else
    git clone "$REPO_URL" "$APP_DIR"
    cd "$APP_DIR"
fi

# 3. 创建虚拟环境 & 安装依赖
echo "[3/6] 安装 Python 依赖..."
python3.11 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt

# 4. 配置环境变量
echo "[4/6] 检查 .env 配置..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo "⚠️  请编辑 /opt/wechat-bot/.env 填入真实密钥"
fi

# 5. 配置 cron
echo "[5/6] 配置定时任务..."
crontab -l 2>/dev/null | grep -v "wechat-bot" | cat - deploy/crontab | crontab -

# 6. 配置 systemd 服务
echo "[6/6] 配置 Web 审核服务..."
cp deploy/wechat-bot-web.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable wechat-bot-web
systemctl restart wechat-bot-web

echo ""
echo "✅ 部署完成！"
echo "   - 审核页面: http://$(hostname -I | awk '{print $1}'):8080"
echo "   - 定时任务: 每天 18:00 自动生成推文"
echo "   - 日志: /var/log/wechat-bot.log"
echo ""
echo "⚠️  别忘了编辑 .env 文件填入微信和 Claude API 密钥"
