#!/usr/bin/env bash
set -euo pipefail

# Linux Mint follows Ubuntu/Debian flow.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "${SCRIPT_DIR}/install_ubuntu.sh" "$@"
