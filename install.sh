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
LATEST_RELEASE_LABEL="unknown"

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
log_line() {
  echo "$*"
}

term_cols() {
  local cols
  cols="$(tput cols 2>/dev/null || echo 80)"
  if [[ -z "${cols}" || "${cols}" -lt 40 ]]; then
    cols=80
  fi
  echo "${cols}"
}

print_centered_tty() {
  local text="$1"
  local cols pad
  cols="$(term_cols)"
  if [[ "${#text}" -ge "${cols}" ]]; then
    echo "${text}" > /dev/tty
    return
  fi
  pad=$(( (cols - ${#text}) / 2 ))
  printf "%*s%s\n" "${pad}" "" "${text}" > /dev/tty
}

show_banner() {
  print_centered_tty "      _    __ _            ____ _                "
  print_centered_tty "     / \\  / _| |_ ___ _ _ / ___| | __ ___      __"
  print_centered_tty "    / _ \\| |_| __/ _ \\ '__| |   | |/ _\` \\ \\ /\\ / /"
  print_centered_tty "   / ___ \\  _| ||  __/ |  | |___| | (_| |\\ V  V / "
  print_centered_tty "  /_/   \\_\\_|  \\__\\___|_|   \\____|_|\\__,_| \\_/\\_/  "
  print_centered_tty ""
  print_centered_tty "AfterClaw Installer (${LATEST_RELEASE_LABEL})"
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
  local issues=0
  local installed_ver
  log_info "Running environment checks..."
  echo "OS                : $(uname -s)"
  echo "User              : $(id -un)"
  echo "EUID              : ${EUID}"
  echo "Script source     : ${SCRIPT_SOURCE}"
  echo "Repo source path  : ${AFTERCLAW_SRC}"
  echo "Latest upstream   : ${AFTERCLAW_BRANCH}@${LATEST_REF_LABEL}"
  echo "Latest release    : ${LATEST_RELEASE_LABEL}"
  installed_ver="$(installed_release_label)"
  echo "Installed release : ${installed_ver}"
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
  doctor_check_integrity || issues=1
  if [[ "${issues}" -eq 0 ]]; then
    log_ok "Doctor finished. No integrity issues found."
  else
    log_warn "Doctor finished with integrity warnings."
  fi
}

doctor_check_integrity() {
  local os app_root app_py unit_file plist_file missing=0
  os="$(uname -s)"
  log_line "Integrity check   :"

  case "${os}" in
    Linux)
      unit_file="/etc/systemd/system/${SERVICE_SYSTEMD}"
      if [[ ! -f "${unit_file}" ]]; then
        log_line "  - WARN: missing service file ${unit_file}"
        return 1
      fi
      app_root="$(awk -F= '/^WorkingDirectory=/{print $2; exit}' "${unit_file}")"
      app_py="$(awk -F= '/^ExecStart=/{print $2; exit}' "${unit_file}" | awk '{print $NF}')"
      ;;
    Darwin)
      if [[ "${EUID}" -eq 0 ]]; then
        plist_file="/Library/LaunchDaemons/${SERVICE_LABEL}.plist"
      else
        plist_file="${HOME}/Library/LaunchAgents/${SERVICE_LABEL}.plist"
      fi
      if [[ ! -f "${plist_file}" ]]; then
        log_line "  - WARN: missing plist ${plist_file}"
        return 1
      fi
      app_root="$(awk 'prev && /<string>/{gsub(/.*<string>|<\\/string>.*/,""); print; exit} /<key>WorkingDirectory<\\/key>/{prev=1}' "${plist_file}")"
      app_py="$(awk '/app\.py<\\/string>/{gsub(/.*<string>|<\\/string>.*/,""); print; exit}' "${plist_file}")"
      ;;
    *)
      log_line "  - WARN: unsupported OS for integrity check"
      return 1
      ;;
  esac

  if [[ -z "${app_root}" ]]; then
    log_line "  - WARN: unable to detect app root from service config"
    missing=1
  elif [[ ! -d "${app_root}" ]]; then
    log_line "  - WARN: app root not found: ${app_root}"
    missing=1
  else
    for path in "app.py" "fcc" "web" "shareclip"; do
      if [[ ! -e "${app_root}/${path}" ]]; then
        log_line "  - WARN: missing ${app_root}/${path}"
        missing=1
      else
        log_line "  - OK: ${app_root}/${path}"
      fi
    done
  fi

  if [[ -n "${app_py}" && ! -f "${app_py}" ]]; then
    log_line "  - WARN: configured app entry not found: ${app_py}"
    missing=1
  elif [[ -n "${app_py}" ]]; then
    log_line "  - OK: entrypoint ${app_py}"
  fi

  if [[ "${missing}" -eq 0 ]]; then
    log_line "  - OK: installed copy looks complete"
    return 0
  fi
  return 1
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

refresh_latest_release_label() {
  local tag
  LATEST_RELEASE_LABEL="unknown"
  if ! command -v git >/dev/null 2>&1; then
    return 0
  fi
  tag="$(git ls-remote --tags --refs "${AFTERCLAW_REPO}" 'v*' 2>/dev/null | awk -F'/' '{print $NF}' | sort -V | tail -n1)"
  if [[ -n "${tag}" ]]; then
    LATEST_RELEASE_LABEL="${tag}"
  fi
}

installed_release_label() {
  local tag=""
  if [[ ! -d "${AFTERCLAW_SRC}/.git" ]]; then
    echo "unknown"
    return 0
  fi
  tag="$(git -C "${AFTERCLAW_SRC}" describe --tags --abbrev=0 2>/dev/null || true)"
  if [[ -n "${tag}" ]]; then
    echo "${tag}"
  else
    echo "unknown"
  fi
}

installed_commit_label() {
  if [[ ! -d "${AFTERCLAW_SRC}/.git" ]]; then
    echo "unknown"
    return 0
  fi
  git -C "${AFTERCLAW_SRC}" rev-parse --short HEAD 2>/dev/null || echo "unknown"
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
      log_info "Running: git -C ${AFTERCLAW_SRC} pull --ff-only --quiet"
      if ! git -C "${AFTERCLAW_SRC}" pull --ff-only --quiet; then
        log_warn "Quiet update failed, retrying with full output..."
        log_info "Running: git -C ${AFTERCLAW_SRC} pull --ff-only"
        git -C "${AFTERCLAW_SRC}" pull --ff-only
      fi
    else
      log_info "Fetching AfterClaw into ${AFTERCLAW_SRC} ..."
      log_info "Running: git clone --depth 1 --branch ${AFTERCLAW_BRANCH} --quiet ${AFTERCLAW_REPO} ${AFTERCLAW_SRC}"
      if ! git clone --depth 1 --branch "${AFTERCLAW_BRANCH}" --quiet "${AFTERCLAW_REPO}" "${AFTERCLAW_SRC}"; then
        log_warn "Quiet clone failed, retrying with full output..."
        log_info "Running: git clone --depth 1 --branch ${AFTERCLAW_BRANCH} ${AFTERCLAW_REPO} ${AFTERCLAW_SRC}"
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
          log_info "Running: bash ${SCRIPT_DIR}/scripts/uninstall.sh"
          bash "${SCRIPT_DIR}/scripts/uninstall.sh"
          ;;
        update)
          local installed_ver installed_commit latest_commit
          installed_ver="$(installed_release_label)"
          installed_commit="$(installed_commit_label)"
          latest_commit="${LATEST_REF_LABEL}"
          if [[ "${installed_commit}" != "unknown" && "${latest_commit}" != "unknown" && "${installed_commit}" == "${latest_commit}" ]]; then
            log_ok "Already on latest commit (${installed_commit}). Update skipped."
            return 0
          fi
          if [[ "${installed_ver}" != "unknown" && "${LATEST_RELEASE_LABEL}" != "unknown" && "${installed_ver}" == "${LATEST_RELEASE_LABEL}" ]]; then
            log_ok "Already on latest release (${installed_ver}). Update skipped."
            return 0
          fi
          log_info "AfterClaw detected. InstalledRelease=${installed_ver}, LatestRelease=${LATEST_RELEASE_LABEL}, InstalledCommit=${installed_commit}, LatestCommit=${latest_commit}. Applying update..."
          case "${ID:-}" in
            ubuntu|debian) bash "${SCRIPT_DIR}/scripts/install_ubuntu.sh" ;;
            linuxmint) bash "${SCRIPT_DIR}/scripts/install_mint.sh" ;;
            *) log_err "不支持的 Linux 发行版: ${ID:-unknown}"; return 1 ;;
          esac
          ;;
        install)
          case "${ID:-}" in
            ubuntu|debian) log_info "Running: bash ${SCRIPT_DIR}/scripts/install_ubuntu.sh"; bash "${SCRIPT_DIR}/scripts/install_ubuntu.sh" ;;
            linuxmint) log_info "Running: bash ${SCRIPT_DIR}/scripts/install_mint.sh"; bash "${SCRIPT_DIR}/scripts/install_mint.sh" ;;
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
        uninstall) log_info "Running: bash ${SCRIPT_DIR}/scripts/uninstall.sh"; bash "${SCRIPT_DIR}/scripts/uninstall.sh" ;;
        update)
          local installed_ver installed_commit latest_commit
          installed_ver="$(installed_release_label)"
          installed_commit="$(installed_commit_label)"
          latest_commit="${LATEST_REF_LABEL}"
          if [[ "${installed_commit}" != "unknown" && "${latest_commit}" != "unknown" && "${installed_commit}" == "${latest_commit}" ]]; then
            log_ok "Already on latest commit (${installed_commit}). Update skipped."
            return 0
          fi
          if [[ "${installed_ver}" != "unknown" && "${LATEST_RELEASE_LABEL}" != "unknown" && "${installed_ver}" == "${LATEST_RELEASE_LABEL}" ]]; then
            log_ok "Already on latest release (${installed_ver}). Update skipped."
            return 0
          fi
          log_info "AfterClaw detected. InstalledRelease=${installed_ver}, LatestRelease=${LATEST_RELEASE_LABEL}, InstalledCommit=${installed_commit}, LatestCommit=${latest_commit}. Applying update..."
          log_info "Running: bash ${SCRIPT_DIR}/scripts/install_macos.sh"
          bash "${SCRIPT_DIR}/scripts/install_macos.sh"
          ;;
        install)
          log_info "Running: bash ${SCRIPT_DIR}/scripts/install_macos.sh"
          bash "${SCRIPT_DIR}/scripts/install_macos.sh"
          ;;
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
  while true; do
    installed=0
    if is_afterclaw_installed; then
      installed=1
    fi
    if [[ "${HAS_TTY}" -eq 1 ]]; then
      printf '\033[2J\033[H' > /dev/tty
    fi
    show_banner
    print_centered_tty "+--------------------------------------+"
    if [[ "${installed}" -eq 1 ]]; then
      print_centered_tty "|  1) Update                           |"
      print_centered_tty "|  2) Uninstall                        |"
    else
      print_centered_tty "|  1) Install                          |"
    fi
    print_centered_tty "|  4) Doctor                           |"
    print_centered_tty "|  q) Quit                             |"
    print_centered_tty "+--------------------------------------+"
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
      echo "Exited AfterClaw installer."
      exit 0
    fi
    if [[ "${action}" != "doctor" ]] && ! confirm_action "${action}"; then
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
  refresh_latest_release_label
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
refresh_latest_release_label
bootstrap_if_needed "$@"
run_platform_action "${ACTION}"
