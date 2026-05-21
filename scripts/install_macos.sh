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
SERVICE_LABEL="com.fcc.afterclaw"
PLIST=""
PYTHON_BIN="${PYTHON_BIN:-}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ "${EUID}" -eq 0 ]]; then
  PLIST_DIR="/Library/LaunchDaemons"
  SERVICE_TARGET="system/${SERVICE_LABEL}"
  BOOTSTRAP_DOMAIN="system"
else
  PLIST_DIR="${HOME}/Library/LaunchAgents"
  SERVICE_TARGET="gui/$(id -u)/${SERVICE_LABEL}"
  BOOTSTRAP_DOMAIN="gui/$(id -u)"
fi
PLIST="${PLIST_DIR}/${SERVICE_LABEL}.plist"

if [[ -z "${PYTHON_BIN}" ]] && command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python3)"
fi

if [[ -z "${PYTHON_BIN}" ]]; then
  if ! command -v brew >/dev/null 2>&1; then
    echo "未检测到 python3，且 brew 不可用，请先安装 Homebrew 或 Python3" >&2
    exit 1
  fi
  brew install python
  PYTHON_BIN="$(command -v python3)"
fi

if [[ -z "${PYTHON_BIN}" || ! -x "${PYTHON_BIN}" ]]; then
  echo "未找到可执行 Python 解释器，请通过 PYTHON_BIN 指定" >&2
  exit 1
fi

PY_OK="$("${PYTHON_BIN}" - <<'PY'
import sys
print("1" if sys.version_info >= (3, 10) else "0")
PY
)"
if [[ "${PY_OK}" != "1" ]]; then
  for candidate in python3.13 python3.12 python3.11 python3.10; do
    if command -v "${candidate}" >/dev/null 2>&1; then
      cbin="$(command -v "${candidate}")"
      PY_OK="$("${cbin}" - <<'PY'
import sys
print("1" if sys.version_info >= (3, 10) else "0")
PY
)"
      if [[ "${PY_OK}" == "1" ]]; then
        PYTHON_BIN="${cbin}"
        break
      fi
    fi
  done
fi

if [[ "${PY_OK}" != "1" ]]; then
  echo "需要 Python 3.10+，当前解释器不满足：${PYTHON_BIN}" >&2
  echo "可通过环境变量指定，例如：PYTHON_BIN=\$HOME/.local/bin/python3.11 bash install.sh" >&2
  exit 1
fi

mkdir -p "${APP_ROOT}" "${STORAGE_ROOT}" "${PLIST_DIR}"
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
    <key>Label</key><string>${SERVICE_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
      <string>${PYTHON_BIN}</string>
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

if [[ "${EUID}" -eq 0 ]]; then
  chown root:wheel "${PLIST}"
  chmod 644 "${PLIST}"
fi

launchctl bootout "${SERVICE_TARGET}" >/dev/null 2>&1 || true
launchctl bootstrap "${BOOTSTRAP_DOMAIN}" "${PLIST}"
launchctl enable "${SERVICE_TARGET}" >/dev/null 2>&1 || true
launchctl kickstart -k "${SERVICE_TARGET}" >/dev/null 2>&1 || true

echo "安装完成。"
echo "管理页面: http://127.0.0.1:${WEB_PORT}"
echo "Python: ${PYTHON_BIN}"
echo "launchctl 状态: launchctl list | grep com.fcc.afterclaw"
