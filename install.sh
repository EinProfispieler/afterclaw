#!/usr/bin/env bash
set -euo pipefail

# Unified installer entrypoint (Phase 1 scaffold)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

OS="$(uname -s)"
case "$OS" in
  Linux)
    if [[ -f /etc/os-release ]]; then
      . /etc/os-release
      case "${ID:-}" in
        ubuntu|debian)
          exec bash "${SCRIPT_DIR}/scripts/install_ubuntu.sh" "$@"
          ;;
        linuxmint)
          exec bash "${SCRIPT_DIR}/scripts/install_mint.sh" "$@"
          ;;
        *)
          echo "不支持的 Linux 发行版: ${ID:-unknown}" >&2
          exit 1
          ;;
      esac
    fi
    echo "未找到 /etc/os-release，无法识别发行版" >&2
    exit 1
    ;;
  Darwin)
    exec bash "${SCRIPT_DIR}/scripts/install_macos.sh" "$@"
    ;;
  *)
    echo "不支持的操作系统: ${OS}" >&2
    exit 1
    ;;
esac
