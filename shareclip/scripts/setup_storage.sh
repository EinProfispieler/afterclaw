#!/usr/bin/env bash
set -euo pipefail

ROOT=""
SERVICE_USER=""
SERVICE_GROUP=""
PORT="8888"
DEFAULT_ID="pub"
SERVICE_NAME="shareclip"
APPLY_SYSTEMD="0"

usage() {
  cat <<'EOF'
Usage:
  setup_storage.sh --root <path> --user <user> [options]

Options:
  --group <group>         Service group (default: same as --user)
  --port <1-65535>        Default app port in config.json (default: 8888)
  --default-id <id>       Default ID in config.json (default: pub)
  --service <name>        Systemd service name (default: shareclip)
  --apply-systemd         Write systemd override env and restart service
  -h, --help              Show this help

Examples:
  ./scripts/setup_storage.sh --root /var/lib/shareclip --user randy --group randy --apply-systemd
  ./scripts/setup_storage.sh --root /home/randy/shareclip/storage --user randy --port 8888 --default-id pub
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --root) ROOT="${2:-}"; shift 2 ;;
    --user) SERVICE_USER="${2:-}"; shift 2 ;;
    --group) SERVICE_GROUP="${2:-}"; shift 2 ;;
    --port) PORT="${2:-}"; shift 2 ;;
    --default-id) DEFAULT_ID="${2:-}"; shift 2 ;;
    --service) SERVICE_NAME="${2:-}"; shift 2 ;;
    --apply-systemd) APPLY_SYSTEMD="1"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage; exit 1 ;;
  esac
done

if [[ -z "$ROOT" || -z "$SERVICE_USER" ]]; then
  echo "Error: --root and --user are required." >&2
  usage
  exit 1
fi

if ! [[ "$PORT" =~ ^[0-9]+$ ]] || (( PORT < 1 || PORT > 65535 )); then
  echo "Error: --port must be an integer in 1-65535." >&2
  exit 1
fi

if ! [[ "$DEFAULT_ID" =~ ^[A-Za-z0-9_-]{1,64}$ ]]; then
  echo "Error: --default-id must match [A-Za-z0-9_-]{1,64}." >&2
  exit 1
fi

if ! id "$SERVICE_USER" >/dev/null 2>&1; then
  echo "Error: user '$SERVICE_USER' does not exist." >&2
  exit 1
fi

if [[ -z "$SERVICE_GROUP" ]]; then
  SERVICE_GROUP="$SERVICE_USER"
fi

if ! getent group "$SERVICE_GROUP" >/dev/null 2>&1; then
  echo "Error: group '$SERVICE_GROUP' does not exist." >&2
  exit 1
fi

run_root() {
  if [[ "$(id -u)" -eq 0 ]]; then
    "$@"
  else
    sudo "$@"
  fi
}

echo "[setup] storage root: $ROOT"
echo "[setup] service user: $SERVICE_USER"
echo "[setup] service group: $SERVICE_GROUP"

run_root mkdir -p "$ROOT"
run_root chown -R "$SERVICE_USER:$SERVICE_GROUP" "$ROOT"

# Directory 750, files 640.
run_root find "$ROOT" -type d -exec chmod 750 {} +
run_root find "$ROOT" -type f -exec chmod 640 {} +

TMP_CFG="$(mktemp)"
cat > "$TMP_CFG" <<EOF
{
  "port": $PORT,
  "default_id": "$DEFAULT_ID"
}
EOF

run_root install -m 640 -o "$SERVICE_USER" -g "$SERVICE_GROUP" "$TMP_CFG" "$ROOT/config.json"
rm -f "$TMP_CFG"

echo "[setup] wrote: $ROOT/config.json"

if [[ "$APPLY_SYSTEMD" == "1" ]]; then
  OVERRIDE_DIR="/etc/systemd/system/${SERVICE_NAME}.service.d"
  OVERRIDE_FILE="${OVERRIDE_DIR}/10-storage.conf"
  TMP_OVR="$(mktemp)"
  cat > "$TMP_OVR" <<EOF
[Service]
Environment="SHARECLIP_STORAGE_ROOT=$ROOT"
EOF
  run_root mkdir -p "$OVERRIDE_DIR"
  run_root install -m 644 -o root -g root "$TMP_OVR" "$OVERRIDE_FILE"
  rm -f "$TMP_OVR"
  run_root systemctl daemon-reload
  run_root systemctl restart "$SERVICE_NAME"
  echo "[setup] systemd override updated: $OVERRIDE_FILE"
  echo "[setup] restarted service: $SERVICE_NAME"
else
  echo "[setup] To apply this root in systemd, add:"
  echo "        Environment=\"SHARECLIP_STORAGE_ROOT=$ROOT\""
fi

echo "[setup] done."
