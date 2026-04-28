#!/usr/bin/env bash
set -euo pipefail
echo "[兼容入口] install_on_130.sh 已转发到 install.sh"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "${SCRIPT_DIR}/install.sh"
