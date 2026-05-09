#!/usr/bin/env bash
set -euo pipefail

# Ubuntu / Debian installer
WEB_PORT="${WEB_PORT:-1288}"
STORAGE_ROOT="${STORAGE_ROOT:-/srv/Storage}"
APP_ROOT="${APP_ROOT:-/opt/afterclaw}"
PUBLIC_HOST="${PUBLIC_HOST:-127.0.0.1:${WEB_PORT}}"
PUBLIC_SCHEME="${PUBLIC_SCHEME:-http}"
DOWNLOADS_ENABLED="${DOWNLOADS_ENABLED:-1}"
QBT_SERVICE="${QBT_SERVICE:-qbittorrent-nox}"
QBT_API_URL="${QBT_API_URL:-http://127.0.0.1:8080}"
QBT_API_USERNAME="${QBT_API_USERNAME:-}"
QBT_API_PASSWORD="${QBT_API_PASSWORD:-}"
DDNS_SERVICE="${DDNS_SERVICE:-ddns-go.service}"
SHARECLIP_STORAGE_ROOT="${SHARECLIP_STORAGE_ROOT:-${APP_ROOT}/shareclip/storage}"
SERVICE_NAME="storage-http-link-web"

if [[ "${EUID}" -ne 0 ]]; then
  echo "请使用 root 权限运行，例如：sudo bash install.sh"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "[1/5] 安装 Python 与依赖..."
apt update
apt install -y python3 python3-flask python3-pip
if [[ -f "${SCRIPT_DIR}/requirements.txt" ]]; then
  python3 -m pip install --no-input -q -r "${SCRIPT_DIR}/requirements.txt" || {
    echo "pip 安装依赖失败，可稍后手动: pip3 install -r requirements.txt" >&2
  }
fi

echo "[2/5] 准备目录..."
mkdir -p "${APP_ROOT}"
mkdir -p "${STORAGE_ROOT}"

echo "[3/5] 复制程序..."
cp "${SCRIPT_DIR}/app.py" "${APP_ROOT}/app.py"
if [[ -d "${SCRIPT_DIR}/fcc" ]]; then
  rm -rf "${APP_ROOT}/fcc"
  cp -a "${SCRIPT_DIR}/fcc" "${APP_ROOT}/fcc"
fi
if [[ -d "${SCRIPT_DIR}/ddns" ]]; then
  rm -rf "${APP_ROOT}/ddns"
  cp -a "${SCRIPT_DIR}/ddns" "${APP_ROOT}/ddns"
fi
if [[ -d "${SCRIPT_DIR}/web" ]]; then
  rm -rf "${APP_ROOT}/web"
  cp -a "${SCRIPT_DIR}/web" "${APP_ROOT}/web"
fi
if [[ -d "${SCRIPT_DIR}/naming" ]]; then
  rm -rf "${APP_ROOT}/naming"
  cp -a "${SCRIPT_DIR}/naming" "${APP_ROOT}/naming"
fi
if [[ -d "${SCRIPT_DIR}/shareclip" ]]; then
  rm -rf "${APP_ROOT}/shareclip"
  cp -a "${SCRIPT_DIR}/shareclip" "${APP_ROOT}/shareclip"
fi
cp -f "${SCRIPT_DIR}/requirements.txt" "${APP_ROOT}/requirements.txt" 2>/dev/null || true
cp -f "${SCRIPT_DIR}/pyproject.toml" "${APP_ROOT}/pyproject.toml" 2>/dev/null || true
chmod +x "${APP_ROOT}/app.py"

echo "[4/5] 创建 systemd 服务..."
cat > "/etc/systemd/system/${SERVICE_NAME}.service" <<EOF
[Unit]
Description=Storage HTTP Control Center
After=network.target

[Service]
Type=simple
Environment=WEB_PORT=${WEB_PORT}
Environment=STORAGE_ROOT=${STORAGE_ROOT}
Environment=PUBLIC_HOST=${PUBLIC_HOST}
Environment=PUBLIC_SCHEME=${PUBLIC_SCHEME}
Environment=DOWNLOADS_ENABLED=${DOWNLOADS_ENABLED}
Environment=QBT_SERVICE=${QBT_SERVICE}
Environment=QBT_API_URL=${QBT_API_URL}
Environment=QBT_API_USERNAME=${QBT_API_USERNAME}
Environment=QBT_API_PASSWORD=${QBT_API_PASSWORD}
Environment=DDNS_SERVICE=${DDNS_SERVICE}
Environment=SHARECLIP_STORAGE_ROOT=${SHARECLIP_STORAGE_ROOT}
WorkingDirectory=${APP_ROOT}
ExecStart=/usr/bin/python3 ${APP_ROOT}/app.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

echo "[5/5] 启动网页服务..."
systemctl daemon-reload
systemctl enable --now "${SERVICE_NAME}"
systemctl restart "${SERVICE_NAME}"

echo "安装完成。"
echo "管理页面（局域网）: http://<LAN_IP>:${WEB_PORT}"
echo "下载前缀（外网）  : ${PUBLIC_SCHEME}://${PUBLIC_HOST}"
echo "ShareClip 已内置在 1288 进程，数据目录: ${SHARECLIP_STORAGE_ROOT}"
echo "服务状态: systemctl status ${SERVICE_NAME}"
