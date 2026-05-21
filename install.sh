#!/usr/bin/env bash
set -euo pipefail

SCRIPT_SOURCE="${BASH_SOURCE[0]:-$0}"
SCRIPT_DIR="$(cd "$(dirname "${SCRIPT_SOURCE}")" && pwd)"

AFTERCLAW_REPO="${AFTERCLAW_REPO:-https://github.com/EinProfispieler/afterclaw.git}"
AFTERCLAW_BRANCH="${AFTERCLAW_BRANCH:-main}"
AFTERCLAW_SRC="${AFTERCLAW_SRC:-/opt/afterclaw}"
SERVICE_LABEL="com.fcc.afterclaw"
SERVICE_SYSTEMD="storage-http-link-web.service"
LATEST_REF_LABEL="unknown"

IS_TTY=0
if [[ -t 0 && -t 1 ]]; then
  IS_TTY=1
fi
HAS_TTY=0
if [[ -r /dev/tty && -w /dev/tty ]]; then
  HAS_TTY=1
fi

if [[ "${IS_TTY}" -eq 1 ]]; then
  C_RESET=$'\033[0m'
  C_INFO=$'\033[1;34m'
  C_OK=$'\033[1;32m'
  C_WARN=$'\033[1;33m'
  C_ERR=$'\033[1;31m'
else
  C_RESET=""
  C_INFO=""
  C_OK=""
  C_WARN=""
  C_ERR=""
fi

log_info() { echo "${C_INFO}[INFO]${C_RESET} $*"; }
log_ok() { echo "${C_OK}[OK]${C_RESET} $*"; }
log_warn() { echo "${C_WARN}[WARN]${C_RESET} $*"; }
log_err() { echo "${C_ERR}[ERROR]${C_RESET} $*" >&2; }

show_banner() {
  cat <<'EOF' > /dev/tty
   ___   __ _             ____ _                
  / _ | / _| |_ ___ _ _  / ___| | __ ___      __
 / __ |  _|  _/ -_) '_| | |   | |/ _` \ \ /\ / /
/_/ |_|_|  \__\___|_|   | |___| | (_| |\ V  V / 
                            \____|_|\__,_| \_/\_/  
EOF
  echo "AfterClaw Installer (${AFTERCLAW_BRANCH}@${LATEST_REF_LABEL})" > /dev/tty
}

confirm_action() {
  local action="$1"
  local ans
  if [[ "${HAS_TTY}" -ne 1 ]]; then
    return 0
  fi
  printf "Proceed with %s? [Y/n]: " "${action}" > /dev/tty
  read -r ans < /dev/tty
  case "${ans:-Y}" in
    y|Y|yes|YES|"") return 0 ;;
    *) return 1 ;;
  esac
}

is_afterclaw_installed() {
  case "$(uname -s)" in
    Linux)
      if command -v systemctl >/dev/null 2>&1; then
        systemctl list-unit-files 2>/dev/null | grep -q "^${SERVICE_SYSTEMD}"
        return $?
      fi
      return 1
      ;;
    Darwin)
      if [[ "${EUID}" -eq 0 ]]; then
        [[ -f "/Library/LaunchDaemons/${SERVICE_LABEL}.plist" ]]
        return $?
      fi
      [[ -f "${HOME}/Library/LaunchAgents/${SERVICE_LABEL}.plist" ]]
      return $?
      ;;
    *)
      return 1
      ;;
  esac
}

run_doctor() {
  log_info "Running environment checks..."
  echo "OS                : $(uname -s)"
  echo "User              : $(id -un)"
  echo "EUID              : ${EUID}"
  echo "Script source     : ${SCRIPT_SOURCE}"
  echo "Repo source path  : ${AFTERCLAW_SRC}"
  echo "Latest upstream   : ${AFTERCLAW_BRANCH}@${LATEST_REF_LABEL}"
  echo "Git available     : $(command -v git >/dev/null 2>&1 && echo yes || echo no)"
  echo "Python3 available : $(command -v python3 >/dev/null 2>&1 && echo yes || echo no)"
  case "$(uname -s)" in
    Linux)
      echo "Systemd available : $(command -v systemctl >/dev/null 2>&1 && echo yes || echo no)"
      echo "Installed service : $(is_afterclaw_installed && echo yes || echo no)"
      ;;
    Darwin)
      echo "Launchd plist     : $(is_afterclaw_installed && echo yes || echo no)"
      ;;
  esac
  log_ok "Doctor finished."
}

refresh_latest_ref_label() {
  local ref
  LATEST_REF_LABEL="unknown"
  if ! command -v git >/dev/null 2>&1; then
    return 0
  fi
  ref="$(git ls-remote --heads "${AFTERCLAW_REPO}" "${AFTERCLAW_BRANCH}" 2>/dev/null | awk 'NR==1{print $1}')"
  if [[ -n "${ref}" ]]; then
    LATEST_REF_LABEL="${ref:0:7}"
  fi
}

bootstrap_if_needed() {
  if [[ -d "${SCRIPT_DIR}/scripts" ]]; then
    return 0
  fi

  if ! command -v git >/dev/null 2>&1; then
    log_err "git is required to bootstrap AfterClaw. Install git and retry."
    exit 1
  fi

  if [[ -d "${AFTERCLAW_SRC}/.git" ]]; then
    log_info "Updating existing AfterClaw checkout in ${AFTERCLAW_SRC} ..."
    if ! git -C "${AFTERCLAW_SRC}" pull --ff-only --quiet; then
      log_warn "Quiet update failed, retrying with full output..."
      git -C "${AFTERCLAW_SRC}" pull --ff-only
    fi
  else
    log_info "Fetching AfterClaw into ${AFTERCLAW_SRC} ..."
    if ! git clone --depth 1 --branch "${AFTERCLAW_BRANCH}" --quiet "${AFTERCLAW_REPO}" "${AFTERCLAW_SRC}"; then
      log_warn "Quiet clone failed, retrying with full output..."
      git clone --depth 1 --branch "${AFTERCLAW_BRANCH}" "${AFTERCLAW_REPO}" "${AFTERCLAW_SRC}"
    fi
  fi

  if [[ ! -x "${AFTERCLAW_SRC}/install.sh" ]]; then
    log_err "Bootstrap failed: ${AFTERCLAW_SRC}/install.sh not found or not executable."
    exit 1
  fi

  SCRIPT_SOURCE="${AFTERCLAW_SRC}/install.sh"
  SCRIPT_DIR="${AFTERCLAW_SRC}"
  return 0
}

run_platform_action() {
  local action="$1"
  local os
  os="$(uname -s)"

  if [[ "${action}" == "doctor" ]]; then
    run_doctor
    return 0
  fi

  case "${os}" in
    Linux)
      if [[ "${action}" == "install" ]] && is_afterclaw_installed; then
        log_warn "AfterClaw is already installed. Use update or uninstall."
        return 1
      fi
      if [[ "${action}" == "update" || "${action}" == "uninstall" ]] && ! is_afterclaw_installed; then
        log_warn "AfterClaw is not installed. Install it first."
        return 1
      fi
      if [[ ! -f /etc/os-release ]]; then
        log_err "未找到 /etc/os-release，无法识别发行版"
        return 1
      fi
      # shellcheck disable=SC1091
      . /etc/os-release
      case "${action}" in
        uninstall)
          bash "${SCRIPT_DIR}/scripts/uninstall.sh"
          ;;
        update)
          if is_afterclaw_installed; then
            log_info "AfterClaw detected. Applying update..."
          else
            log_warn "AfterClaw is not installed yet. Running fresh install instead of update..."
          fi
          case "${ID:-}" in
            ubuntu|debian) bash "${SCRIPT_DIR}/scripts/install_ubuntu.sh" ;;
            linuxmint) bash "${SCRIPT_DIR}/scripts/install_mint.sh" ;;
            *) log_err "不支持的 Linux 发行版: ${ID:-unknown}"; return 1 ;;
          esac
          ;;
        install)
          case "${ID:-}" in
            ubuntu|debian) bash "${SCRIPT_DIR}/scripts/install_ubuntu.sh" ;;
            linuxmint) bash "${SCRIPT_DIR}/scripts/install_mint.sh" ;;
            *) log_err "不支持的 Linux 发行版: ${ID:-unknown}"; return 1 ;;
          esac
          ;;
        *)
          log_err "Unknown action: ${action}"
          return 1
          ;;
      esac
      ;;
    Darwin)
      if [[ "${action}" == "install" ]] && is_afterclaw_installed; then
        log_warn "AfterClaw is already installed. Use update or uninstall."
        return 1
      fi
      if [[ "${action}" == "update" || "${action}" == "uninstall" ]] && ! is_afterclaw_installed; then
        log_warn "AfterClaw is not installed. Install it first."
        return 1
      fi
      case "${action}" in
        uninstall) bash "${SCRIPT_DIR}/scripts/uninstall.sh" ;;
        install|update) bash "${SCRIPT_DIR}/scripts/install_macos.sh" ;;
        *) log_err "Unknown action: ${action}"; return 1 ;;
      esac
      ;;
    MINGW*|MSYS*|CYGWIN*|Windows_NT)
      log_err "Windows detected. Please run PowerShell installer instead:"
      echo "  powershell -ExecutionPolicy Bypass -File .\\install.ps1"
      return 1
      ;;
    *)
      log_err "不支持的操作系统: ${os}"
      return 1
      ;;
  esac
}

prompt_action_ascii() {
  local choice=""
  local installed=0
  if is_afterclaw_installed; then
    installed=1
  fi
  while true; do
    show_banner
    cat <<'EOF' > /dev/tty
+--------------------------------------+
EOF
    if [[ "${installed}" -eq 1 ]]; then
      cat <<'EOF' > /dev/tty
|  1) Update                           |
|  2) Uninstall                        |
EOF
    else
      cat <<'EOF' > /dev/tty
|  1) Install                          |
EOF
    fi
    cat <<'EOF' > /dev/tty
|  4) Doctor                           |
|  q) Quit                             |
+--------------------------------------+
EOF
    if [[ "${installed}" -eq 1 ]]; then
      printf "Select an option [1/2/4/q]: " > /dev/tty
    else
      printf "Select an option [1/4/q]: " > /dev/tty
    fi
    read -r choice < /dev/tty
    if [[ "${installed}" -eq 1 ]]; then
      case "${choice}" in
        1) echo "update"; return 0 ;;
        2) echo "uninstall"; return 0 ;;
        4) echo "doctor"; return 0 ;;
        q|Q) echo "quit"; return 0 ;;
        *) log_warn "Invalid option: ${choice}"; echo > /dev/tty ;;
      esac
    else
      case "${choice}" in
        1) echo "install"; return 0 ;;
        4) echo "doctor"; return 0 ;;
        q|Q) echo "quit"; return 0 ;;
        *) log_warn "Invalid option: ${choice}"; echo > /dev/tty ;;
      esac
    fi
  done
}

interactive_main() {
  local action rc ans
  while true; do
    action="$(prompt_action_ascii)"
    if [[ "${action}" == "quit" ]]; then
      echo "Canceled."
      exit 0
    fi
    if ! confirm_action "${action}"; then
      log_warn "Canceled ${action}."
      continue
    fi

    if [[ "${action}" != "doctor" ]]; then
      set +e
      bootstrap_if_needed
      rc=$?
      set -e
      if [[ $rc -ne 0 ]]; then
        log_err "bootstrap failed."
        continue
      fi
    fi

    set +e
    run_platform_action "${action}"
    rc=$?
    set -e

    if [[ $rc -eq 0 ]]; then
      log_ok "${action} completed."
      printf "Press Enter to return to menu..." > /dev/tty
      read -r _ < /dev/tty
      continue
    fi

    echo
    log_err "${action} failed."
    printf "Next step: [r]etry / [m]enu / [q]uit: " > /dev/tty
    read -r ans < /dev/tty
    case "${ans}" in
      r|R) ;;
      m|M) continue ;;
      *) exit "${rc}" ;;
    esac
  done
}

if [[ "$#" -eq 0 && "${HAS_TTY}" -eq 1 ]]; then
  refresh_latest_ref_label
  interactive_main
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
    --doctor)
      ACTION="doctor"
      ;;
  esac
done

refresh_latest_ref_label
bootstrap_if_needed "$@"
run_platform_action "${ACTION}"
