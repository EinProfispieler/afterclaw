#!/usr/bin/env bash
set -euo pipefail

OS="$(uname -s)"
SERVICE_LABEL="com.fcc.afterclaw"
if [[ "$OS" == "Linux" ]]; then
  if [[ $EUID -ne 0 ]]; then
    echo "Linux 卸载请使用 sudo" >&2
    exit 1
  fi
  systemctl disable --now storage-http-link-web >/dev/null 2>&1 || true
  rm -f /etc/systemd/system/storage-http-link-web.service
  systemctl daemon-reload
  echo "已移除 systemd 服务（程序目录和数据目录未删除）"
  exit 0
fi

if [[ "$OS" == "Darwin" ]]; then
  if [[ $EUID -eq 0 ]]; then
    PLIST="/Library/LaunchDaemons/${SERVICE_LABEL}.plist"
    launchctl bootout "system/${SERVICE_LABEL}" >/dev/null 2>&1 || true
  else
    PLIST="${HOME}/Library/LaunchAgents/${SERVICE_LABEL}.plist"
    launchctl bootout "gui/$(id -u)/${SERVICE_LABEL}" >/dev/null 2>&1 || true
  fi
  rm -f "${PLIST}"
  echo "已移除 launchd 服务（程序目录和数据目录未删除）"
  exit 0
fi

echo "不支持的系统: $OS"
exit 1
