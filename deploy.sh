#!/bin/bash
# 记账本部署脚本 - 适用于 Ubuntu/Debian 云服务器
# 使用方法: sudo bash deploy.sh

set -e

APP_NAME="zhangben"
APP_DIR="/opt/$APP_NAME"
PORT=511

echo "===== 记账本部署脚本 ====="

# 1. 安装依赖
echo "[1/5] 安装系统依赖..."
apt-get update -y
apt-get install -y python3 python3-pip python3-venv

# 2. 创建应用目录
echo "[2/5] 创建应用目录..."
mkdir -p $APP_DIR
cp -r ./* $APP_DIR/

# 3. 创建虚拟环境并安装依赖
echo "[3/5] 安装 Python 依赖..."
cd $APP_DIR
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install gunicorn
deactivate

# 4. 创建 systemd 服务
echo "[4/5] 配置系统服务..."
cat > /etc/systemd/system/$APP_NAME.service << EOF
[Unit]
Description=记账本应用
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$APP_DIR
Environment="PATH=$APP_DIR/venv/bin"
ExecStart=$APP_DIR/venv/bin/gunicorn -w 4 -b 0.0.0.0:$PORT app:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# 5. 启动服务
echo "[5/5] 启动服务..."
systemctl daemon-reload
systemctl enable $APP_NAME
systemctl restart $APP_NAME

echo ""
echo "===== 部署完成 ====="
echo "访问地址: http://服务器IP:$PORT"
echo ""
echo "常用命令:"
echo "  查看状态: systemctl status $APP_NAME"
echo "  查看日志: journalctl -u $APP_NAME -f"
echo "  重启服务: systemctl restart $APP_NAME"
echo "  停止服务: systemctl stop $APP_NAME"
