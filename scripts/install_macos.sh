#!/usr/bin/env bash
set -euo pipefail

WEB_PORT="${WEB_PORT:-1288}"
APP_ROOT="${APP_ROOT:-/usr/local/opt/fcc}"
STORAGE_ROOT="${STORAGE_ROOT:-${HOME}/fcc-data/Storage}"
PUBLIC_SCHEME="${PUBLIC_SCHEME:-http}"
PUBLIC_HOST="${PUBLIC_HOST:-127.0.0.1:${WEB_PORT}}"
DOWNLOADS_ENABLED="${DOWNLOADS_ENABLED:-1}"
QBT_SERVICE="${QBT_SERVICE:-qbittorrent-nox}"
QBT_API_URL="${QBT_API_URL:-http://127.0.0.1:8080}"
QBT_API_USERNAME="${QBT_API_USERNAME:-}"
QBT_API_PASSWORD="${QBT_API_PASSWORD:-}"
DDNS_SERVICE="${DDNS_SERVICE:-ddns-go.service}"
SHARECLIP_STORAGE_ROOT="${SHARECLIP_STORAGE_ROOT:-${APP_ROOT}/shareclip/storage}"
PLIST="${HOME}/Library/LaunchAgents/com.fcc.afterclaw.plist"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if ! command -v python3 >/dev/null 2>&1; then
  if ! command -v brew >/dev/null 2>&1; then
    echo "未检测到 python3，且 brew 不可用，请先安装 Homebrew 或 Python3" >&2
    exit 1
  fi
  brew install python
fi

mkdir -p "${APP_ROOT}" "${STORAGE_ROOT}" "${HOME}/Library/LaunchAgents"
cp "${SCRIPT_DIR}/app.py" "${APP_ROOT}/app.py"
[[ -d "${SCRIPT_DIR}/fcc" ]] && { rm -rf "${APP_ROOT}/fcc"; cp -a "${SCRIPT_DIR}/fcc" "${APP_ROOT}/fcc"; }
[[ -d "${SCRIPT_DIR}/ddns" ]] && { rm -rf "${APP_ROOT}/ddns"; cp -a "${SCRIPT_DIR}/ddns" "${APP_ROOT}/ddns"; }
[[ -d "${SCRIPT_DIR}/web" ]] && { rm -rf "${APP_ROOT}/web"; cp -a "${SCRIPT_DIR}/web" "${APP_ROOT}/web"; }
[[ -d "${SCRIPT_DIR}/naming" ]] && { rm -rf "${APP_ROOT}/naming"; cp -a "${SCRIPT_DIR}/naming" "${APP_ROOT}/naming"; }
[[ -d "${SCRIPT_DIR}/shareclip" ]] && { rm -rf "${APP_ROOT}/shareclip"; cp -a "${SCRIPT_DIR}/shareclip" "${APP_ROOT}/shareclip"; }
chmod +x "${APP_ROOT}/app.py"

cat > "${PLIST}" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
  <dict>
    <key>Label</key><string>com.fcc.afterclaw</string>
    <key>ProgramArguments</key>
    <array>
      <string>/usr/bin/env</string>
      <string>python3</string>
      <string>${APP_ROOT}/app.py</string>
    </array>
    <key>EnvironmentVariables</key>
    <dict>
      <key>WEB_PORT</key><string>${WEB_PORT}</string>
      <key>STORAGE_ROOT</key><string>${STORAGE_ROOT}</string>
      <key>PUBLIC_SCHEME</key><string>${PUBLIC_SCHEME}</string>
      <key>PUBLIC_HOST</key><string>${PUBLIC_HOST}</string>
      <key>DOWNLOADS_ENABLED</key><string>${DOWNLOADS_ENABLED}</string>
      <key>QBT_SERVICE</key><string>${QBT_SERVICE}</string>
      <key>QBT_API_URL</key><string>${QBT_API_URL}</string>
      <key>QBT_API_USERNAME</key><string>${QBT_API_USERNAME}</string>
      <key>QBT_API_PASSWORD</key><string>${QBT_API_PASSWORD}</string>
      <key>DDNS_SERVICE</key><string>${DDNS_SERVICE}</string>
      <key>SHARECLIP_STORAGE_ROOT</key><string>${SHARECLIP_STORAGE_ROOT}</string>
    </dict>
    <key>WorkingDirectory</key><string>${APP_ROOT}</string>
    <key>RunAtLoad</key><true/>
    <key>KeepAlive</key><true/>
    <key>StandardOutPath</key><string>${HOME}/Library/Logs/fcc.out.log</string>
    <key>StandardErrorPath</key><string>${HOME}/Library/Logs/fcc.err.log</string>
  </dict>
</plist>
EOF

launchctl unload "${PLIST}" >/dev/null 2>&1 || true
launchctl load "${PLIST}"

echo "安装完成。"
echo "管理页面: http://127.0.0.1:${WEB_PORT}"
echo "launchctl 状态: launchctl list | grep com.fcc.afterclaw"
