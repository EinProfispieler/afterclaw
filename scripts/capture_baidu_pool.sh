#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export FCC_POOL_KEY="baidu"
export FCC_LABELS="百度网盘"
export FCC_INCLUDE_HTTP_DIRECT=0

exec bash "${SCRIPT_DIR}/ip_pool_capture_common.sh"

