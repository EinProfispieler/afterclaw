#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export FCC_POOL_KEY="guangya"
export FCC_LABELS="光鸭网盘"
# In this environment, unknown Guagnya upload flows often appear as HTTP direct first.
export FCC_INCLUDE_HTTP_DIRECT="${FCC_INCLUDE_HTTP_DIRECT:-1}"

exec bash "${SCRIPT_DIR}/ip_pool_capture_common.sh"

