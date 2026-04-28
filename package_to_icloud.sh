#!/usr/bin/env bash
set -euo pipefail

# 在本机打包发布文件，并复制到 iCloud Drive
# 用法：
#   bash package_to_icloud.sh
# 可选环境变量：
#   RELEASE_NAME=storage-http-control
#   ICLOUD_DIR="/Users/<you>/Library/Mobile Documents/com~apple~CloudDocs/你的目录"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DIST_DIR="${SCRIPT_DIR}/dist"
STAMP="$(date +%Y%m%d-%H%M%S)"
RELEASE_NAME="${RELEASE_NAME:-storage-http-control}"
PKG_DIR="${DIST_DIR}/${RELEASE_NAME}-${STAMP}"
ARCHIVE="${DIST_DIR}/${RELEASE_NAME}-${STAMP}.tar.gz"
ICLOUD_DIR="${ICLOUD_DIR:-/Users/randy/Library/Mobile Documents/com~apple~CloudDocs/Randy/NVME}"

mkdir -p "${PKG_DIR}"
mkdir -p "${DIST_DIR}"

cp "${SCRIPT_DIR}/app.py" "${PKG_DIR}/app.py"
if [[ -d "${SCRIPT_DIR}/ddns" ]]; then
  cp -a "${SCRIPT_DIR}/ddns" "${PKG_DIR}/ddns"
fi
if [[ -d "${SCRIPT_DIR}/web" ]]; then
  cp -a "${SCRIPT_DIR}/web" "${PKG_DIR}/web"
fi
if [[ -d "${SCRIPT_DIR}/naming" ]]; then
  cp -a "${SCRIPT_DIR}/naming" "${PKG_DIR}/naming"
fi
cp -f "${SCRIPT_DIR}/requirements.txt" "${PKG_DIR}/requirements.txt" 2>/dev/null || true
cp "${SCRIPT_DIR}/install.sh" "${PKG_DIR}/install.sh"
cp "${SCRIPT_DIR}/install_on_130.sh" "${PKG_DIR}/install_on_130.sh"
cp "${SCRIPT_DIR}/README.md" "${PKG_DIR}/README.md"
cp "${SCRIPT_DIR}/DEPLOY.md" "${PKG_DIR}/DEPLOY.md"
cp "${SCRIPT_DIR}/.env.example" "${PKG_DIR}/.env.example"

if [[ -d "${SCRIPT_DIR}/shareclip" ]]; then
  cp -a "${SCRIPT_DIR}/shareclip" "${PKG_DIR}/shareclip"
fi

chmod +x "${PKG_DIR}/install.sh" "${PKG_DIR}/install_on_130.sh"

tar -C "${DIST_DIR}" -czf "${ARCHIVE}" "$(basename "${PKG_DIR}")"

echo "本地打包完成：${ARCHIVE}"

mkdir -p "${ICLOUD_DIR}"
cp "${ARCHIVE}" "${ICLOUD_DIR}/"
echo "已复制到 iCloud：${ICLOUD_DIR}/$(basename "${ARCHIVE}")"
