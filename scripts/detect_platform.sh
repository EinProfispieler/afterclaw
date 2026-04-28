#!/usr/bin/env bash
set -euo pipefail

OS="$(uname -s)"
if [[ "$OS" == "Linux" ]]; then
  if [[ -f /etc/os-release ]]; then
    . /etc/os-release
    DISTRO_ID="${ID:-unknown}"
    DISTRO_LIKE="${ID_LIKE:-}"
  else
    DISTRO_ID="unknown"
    DISTRO_LIKE=""
  fi
  INIT="unknown"
  [[ -d /run/systemd/system ]] && INIT="systemd"
  PKG="unknown"
  [[ -x /usr/bin/apt ]] && PKG="apt"
  echo "os=linux distro=${DISTRO_ID} like=${DISTRO_LIKE} init=${INIT} pkg=${PKG}"
  exit 0
fi

if [[ "$OS" == "Darwin" ]]; then
  PKG="unknown"
  command -v brew >/dev/null 2>&1 && PKG="brew"
  echo "os=darwin distro=macos like=darwin init=launchd pkg=${PKG}"
  exit 0
fi

echo "os=${OS} distro=unknown like=unknown init=unknown pkg=unknown"
