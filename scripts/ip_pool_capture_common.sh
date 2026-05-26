#!/usr/bin/env bash
set -euo pipefail

# Restricted to a single user by default (can override with FCC_ALLOWED_USER).
ALLOWED_USER="${FCC_ALLOWED_USER:-$(id -un)}"
if [[ "$(id -un)" != "${ALLOWED_USER}" ]]; then
  echo "This script is restricted to user: ${ALLOWED_USER}" >&2
  exit 1
fi

BASE_URL="${FCC_BASE_URL:-http://192.168.1.30:1288}"
POOL_KEY="${FCC_POOL_KEY:-}"
LABELS="${FCC_LABELS:-}"
INCLUDE_HTTP_DIRECT="${FCC_INCLUDE_HTTP_DIRECT:-0}"
MASK_V4="${FCC_MASK_V4:-24}"

if [[ -z "${POOL_KEY}" || -z "${LABELS}" ]]; then
  echo "Missing required env: FCC_POOL_KEY / FCC_LABELS" >&2
  exit 1
fi

python3 - "$BASE_URL" "$POOL_KEY" "$LABELS" "$INCLUDE_HTTP_DIRECT" "$MASK_V4" <<'PY'
import ipaddress
import json
import sys
import urllib.request

base, pool_key, labels_raw, include_http_direct_raw, mask_v4_raw = sys.argv[1:6]
labels = [x.strip() for x in labels_raw.split(",") if x.strip()]
include_http_direct = include_http_direct_raw.strip() in {"1", "true", "True", "yes", "on"}
try:
    mask_v4 = int(mask_v4_raw)
except Exception:
    mask_v4 = 24
if mask_v4 < 8 or mask_v4 > 32:
    mask_v4 = 24

if include_http_direct and "HTTP直连" not in labels:
    labels.append("HTTP直连")

def get_json(url: str):
    with urllib.request.urlopen(url, timeout=10) as resp:
        return json.load(resp)

def canon_source(value: str) -> str:
    s = str(value or "").strip().lower()
    if not s:
        return ""
    if any(k in s for k in ("guangya", "光鸭", "clouddrive", "cloud drive")):
        return "guangya"
    if any(k in s for k in ("baidu", "百度", "xpan", "pan.baidu")):
        return "baidu"
    if any(k in s for k in ("aliyun", "阿里", "alipan")):
        return "aliyun"
    if s in {"http直连", "direct http", "http-direct", "http"}:
        return "http-direct"
    return s

cfg_payload = get_json(base.rstrip("/") + "/api/app-config")
cfg = cfg_payload.get("config") or cfg_payload or {}
http_cfg = cfg.get("http_service") or {}
pools = dict(http_cfg.get("source_ip_pools") or {})
existing = list(pools.get(pool_key) or [])

transfers = get_json(base.rstrip("/") + "/api/transfers")
items = transfers.get("items") or []

target_key = canon_source(pool_key)
allowed_keys = {canon_source(x) for x in labels if str(x or "").strip()}
allowed_keys.discard("")
# Keep compatibility with older localized labels by forcing target pool itself.
allowed_keys.add(target_key)
if include_http_direct:
    allowed_keys.add("http-direct")

targets = set()
for it in items:
    source = canon_source(it.get("source"))
    if source not in allowed_keys:
        continue
    ip = str(it.get("client_ip") or "").strip()
    if not ip:
        continue
    try:
        targets.add(ipaddress.ip_address(ip))
    except Exception:
        continue

existing_nets = []
for raw in existing:
    try:
        existing_nets.append(ipaddress.ip_network(str(raw), strict=False))
    except Exception:
        pass

added = []
for addr in sorted(targets, key=lambda x: (x.version, int(x))):
    if any(addr in net for net in existing_nets):
        continue
    if addr.version == 4:
        net = ipaddress.ip_network(f"{addr}/{mask_v4}", strict=False)
    else:
        net = ipaddress.ip_network(f"{addr}/64", strict=False)
    if net in existing_nets:
        continue
    existing_nets.append(net)
    added.append(str(net))

if added:
    updated = list(existing) + [x for x in added if x not in existing]
    pools[pool_key] = updated
    payload = {
        "http_service": {
            "root_dir": http_cfg.get("root_dir", "/srv/Storage"),
            "default_dir": http_cfg.get("default_dir", "."),
            "source_ip_pools": pools,
        }
    }
    req = urllib.request.Request(
        base.rstrip("/") + "/api/app-config",
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        out = json.load(resp)
    final_pool = (
        (out.get("config") or {})
        .get("http_service", {})
        .get("source_ip_pools", {})
        .get(pool_key, [])
    )
else:
    final_pool = existing

print(json.dumps(
    {
        "pool_key": pool_key,
        "labels": labels,
        "captured_ip_count": len(targets),
        "added_networks": added,
        "final_pool_count": len(final_pool),
    },
    ensure_ascii=False,
))
PY
