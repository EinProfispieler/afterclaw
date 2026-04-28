#!/usr/bin/env bash
set -euo pipefail

SERVICE=shareclip

echo "[shareclip] starting service: ${SERVICE}"
sudo systemctl start "${SERVICE}"
sudo systemctl --no-pager --full status "${SERVICE}" | sed -n '1,16p'
