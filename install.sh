#!/usr/bin/env bash
set -euo pipefail

# Unified installer entrypoint (Phase 1 scaffold)
SCRIPT_SOURCE="${BASH_SOURCE[0]:-$0}"
SCRIPT_DIR="$(cd "$(dirname "${SCRIPT_SOURCE}")" && pwd)"

# --- Standalone bootstrap --------------------------------------------------
# When this script runs on its own (e.g. piped from `curl ... | sudo bash`),
# the sibling `scripts/` directory is not present. In that case, fetch the
# repository and re-exec the installer from inside the working tree.
AFTERCLAW_REPO="${AFTERCLAW_REPO:-https://github.com/EinProfispieler/afterclaw.git}"
AFTERCLAW_BRANCH="${AFTERCLAW_BRANCH:-main}"
AFTERCLAW_SRC="${AFTERCLAW_SRC:-/opt/afterclaw}"

prompt_action_ascii() {
  local choice=""
  MENU_ACTION=""
  while true; do
    echo "+--------------------------------------+"
    echo "|          AfterClaw Installer         |"
    echo "+--------------------------------------+"
    echo "|  1) Install                          |"
    echo "|  2) Update                           |"
    echo "|  3) Uninstall                        |"
    echo "|  q) Quit                             |"
    echo "+--------------------------------------+"
    printf "Select an option [1/2/3/q]: "
    read -r choice
    case "${choice}" in
      1)
        MENU_ACTION="install"
        return 0
        ;;
      2)
        MENU_ACTION="update"
        return 0
        ;;
      3)
        MENU_ACTION="uninstall"
        return 0
        ;;
      q|Q)
        echo "Canceled."
        exit 0
        ;;
      *)
        echo "Invalid option: ${choice}"
        echo
        ;;
    esac
  done
}

if [[ "$#" -eq 0 && -t 0 && -t 1 ]]; then
  prompt_action_ascii
  case "${MENU_ACTION}" in
    update)
      set -- --update
      ;;
    uninstall)
      set -- --uninstall
      ;;
    *)
      set --
      ;;
  esac
fi

ACTION="install"
for arg in "$@"; do
  case "${arg}" in
    --uninstall|-u)
      ACTION="uninstall"
      ;;
    --update)
      ACTION="update"
      ;;
  esac
done

is_afterclaw_installed() {
  local os
  os="$(uname -s)"
  case "${os}" in
    Linux)
      if command -v systemctl >/dev/null 2>&1; then
        systemctl list-unit-files 2>/dev/null | grep -q '^storage-http-link-web\.service'
        return $?
      fi
      return 1
      ;;
    Darwin)
      if [[ -f "/Library/LaunchDaemons/com.fcc.afterclaw.plist" ]]; then
        return 0
      fi
      if [[ -f "${HOME}/Library/LaunchAgents/com.fcc.afterclaw.plist" ]]; then
        return 0
      fi
      return 1
      ;;
    *)
      return 1
      ;;
  esac
}

if [[ "${ACTION}" == "uninstall" ]]; then
  if [[ -x "${SCRIPT_DIR}/scripts/uninstall.sh" ]]; then
    exec bash "${SCRIPT_DIR}/scripts/uninstall.sh"
  fi
fi

if [[ ! -d "${SCRIPT_DIR}/scripts" ]]; then
  if ! command -v git >/dev/null 2>&1; then
    echo "git is required to bootstrap AfterClaw. Install git and retry." >&2
    exit 1
  fi
  if [[ -d "${AFTERCLAW_SRC}/.git" ]]; then
    echo "Updating existing AfterClaw checkout in ${AFTERCLAW_SRC} ..."
    git -C "${AFTERCLAW_SRC}" pull --ff-only
  else
    echo "Fetching AfterClaw into ${AFTERCLAW_SRC} ..."
    git clone --depth 1 --branch "${AFTERCLAW_BRANCH}" "${AFTERCLAW_REPO}" "${AFTERCLAW_SRC}"
  fi
  if [[ "${ACTION}" == "uninstall" ]]; then
    if [[ ! -x "${AFTERCLAW_SRC}/scripts/uninstall.sh" ]]; then
      echo "Bootstrap failed: uninstall script not found at ${AFTERCLAW_SRC}/scripts/uninstall.sh" >&2
      exit 1
    fi
    exec bash "${AFTERCLAW_SRC}/scripts/uninstall.sh"
  fi
  if [[ "${ACTION}" == "update" ]]; then
    if is_afterclaw_installed; then
      echo "AfterClaw detected. Applying update..."
    else
      echo "AfterClaw is not installed yet. Running fresh install instead of update..."
    fi
    exec bash "${AFTERCLAW_SRC}/install.sh"
  fi
  exec bash "${AFTERCLAW_SRC}/install.sh" "$@"
fi
# ---------------------------------------------------------------------------

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
  MINGW*|MSYS*|CYGWIN*|Windows_NT)
    echo "Windows detected. Please run PowerShell installer instead:" >&2
    echo "  powershell -ExecutionPolicy Bypass -File .\\install.ps1" >&2
    exit 1
    ;;
  *)
    echo "不支持的操作系统: ${OS}" >&2
    exit 1
    ;;
esac
