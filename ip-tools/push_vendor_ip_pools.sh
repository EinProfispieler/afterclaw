#!/usr/bin/env bash
set -euo pipefail

# One-shot workflow:
# 1) Pull source_ip_pools from AfterClaw /api/app-config
# 2) Write data/vendor-ip-pools/*.txt
# 3) Commit only these files
# 4) Push to GitHub

ALLOWED_USER="${FCC_ALLOWED_USER:-$(id -un)}"
if [[ "$(id -un)" != "${ALLOWED_USER}" ]]; then
  echo "This script is restricted to user: ${ALLOWED_USER}" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="${FCC_REPO_DIR:-$(cd "${SCRIPT_DIR}/.." && pwd)}"
BASE_URL="${FCC_BASE_URL:-http://127.0.0.1:1288}"
OUTPUT_DIR="${FCC_VENDOR_POOL_DIR:-${REPO_DIR}/data/vendor-ip-pools}"
GIT_REMOTE="${FCC_GIT_REMOTE:-origin}"
GIT_BRANCH="${FCC_GIT_BRANCH:-}"
COMMIT_PREFIX="${FCC_COMMIT_MSG_PREFIX:-chore(ip-pools): sync vendor-ip-pools}"
DRY_RUN="${FCC_DRY_RUN:-0}"
EXPECTED_SOURCE="${FCC_EXPECTED_SOURCE:-github:EinProfispieler/afterclaw/data/vendor-ip-pools}"
ALLOW_SOURCE_MISMATCH="${FCC_ALLOW_SOURCE_MISMATCH:-0}"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required" >&2
  exit 1
fi

if ! command -v git >/dev/null 2>&1; then
  echo "git is required" >&2
  exit 1
fi

if ! git -C "${REPO_DIR}" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Not a git repository: ${REPO_DIR}" >&2
  exit 1
fi

mkdir -p "${OUTPUT_DIR}"
summary_file="$(mktemp)"
trap 'rm -f "${summary_file}"' EXIT

python3 - "${BASE_URL}" "${OUTPUT_DIR}" > "${summary_file}" <<'PY'
import datetime
import ipaddress
import json
import os
import sys
import urllib.request

base, out_dir = sys.argv[1], sys.argv[2]

def get_json(url: str):
    with urllib.request.urlopen(url, timeout=15) as resp:
        return json.load(resp)

def sort_key(raw: str):
    try:
        net = ipaddress.ip_network(raw, strict=False)
        return (net.version, int(net.network_address), int(net.prefixlen), raw)
    except Exception:
        return (99, raw)

payload = get_json(base.rstrip("/") + "/api/app-config")
cfg = payload.get("config") or payload or {}
http_cfg = cfg.get("http_service") or {}
pools = dict(http_cfg.get("source_ip_pools") or {})
source = str(http_cfg.get("source_ip_pool_source") or "").strip()

known_keys = ["baidu", "guangya", "aliyun"]
keys = sorted(set(list(pools.keys()) + known_keys))
written_files = []
counts = {}

for key in keys:
    rows = pools.get(key) or []
    uniq = []
    seen = set()
    for row in rows:
        v = str(row or "").strip()
        if not v:
            continue
        if v in seen:
            continue
        seen.add(v)
        uniq.append(v)
    uniq.sort(key=sort_key)

    dst = os.path.join(out_dir, f"{key}.txt")
    body = "\n".join(uniq)
    with open(dst, "w", encoding="utf-8") as f:
        if body:
            f.write(body + "\n")
        else:
            f.write("")
    written_files.append(dst)
    counts[key] = len(uniq)

print(
    json.dumps(
        {
            "base_url": base,
            "repo_dir": os.path.abspath(os.path.join(out_dir, "..", "..")),
            "output_dir": out_dir,
            "source_ip_pool_source": source,
            "written_files": written_files,
            "counts": counts,
            "generated_at_utc": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        ensure_ascii=False,
    )
)
PY

stage_files_raw="$(
python3 - "${summary_file}" <<'PY'
import json
import sys

summary = json.load(open(sys.argv[1], encoding="utf-8"))
for path in summary.get("written_files") or []:
    print(path)
PY
)"

stage_files=()
while IFS= read -r line; do
  [[ -n "${line}" ]] && stage_files+=("${line}")
done <<< "${stage_files_raw}"

actual_source="$(python3 - "${summary_file}" <<'PY'
import json, sys
summary = json.load(open(sys.argv[1], encoding="utf-8"))
print((summary.get("source_ip_pool_source") or "").strip())
PY
)"

if [[ -n "${EXPECTED_SOURCE}" && "${actual_source}" != "${EXPECTED_SOURCE}" && "${ALLOW_SOURCE_MISMATCH}" != "1" ]]; then
  echo "Source mismatch." >&2
  echo "Expected: ${EXPECTED_SOURCE}" >&2
  echo "Actual:   ${actual_source}" >&2
  echo "If you still want to continue, set FCC_ALLOW_SOURCE_MISMATCH=1" >&2
  exit 1
fi

if [[ "${#stage_files[@]}" -eq 0 ]]; then
  echo "No files generated."
  exit 0
fi

git -C "${REPO_DIR}" add -- "${stage_files[@]}"

if git -C "${REPO_DIR}" diff --cached --quiet -- "${stage_files[@]}"; then
  echo "No vendor IP pool changes to commit."
  python3 - "${summary_file}" <<'PY'
import json
import sys
summary = json.load(open(sys.argv[1], encoding="utf-8"))
counts = summary.get("counts") or {}
parts = [f"{k}:{counts.get(k, 0)}" for k in sorted(counts)]
print("Current counts:", ", ".join(parts))
PY
  exit 0
fi

if [[ -z "${GIT_BRANCH}" ]]; then
  GIT_BRANCH="$(git -C "${REPO_DIR}" rev-parse --abbrev-ref HEAD)"
fi
if [[ -z "${GIT_BRANCH}" || "${GIT_BRANCH}" == "HEAD" ]]; then
  echo "Cannot determine target branch. Set FCC_GIT_BRANCH." >&2
  exit 1
fi

counts_line="$(python3 - "${summary_file}" <<'PY'
import json
import sys
summary = json.load(open(sys.argv[1], encoding="utf-8"))
counts = summary.get("counts") or {}
parts = [f"{k}:{counts.get(k, 0)}" for k in sorted(counts)]
print(", ".join(parts))
PY
)"

commit_msg="${COMMIT_PREFIX} (${counts_line})"

if [[ "${DRY_RUN}" == "1" ]]; then
  echo "[DRY RUN] commit message: ${commit_msg}"
  echo "[DRY RUN] target remote/branch: ${GIT_REMOTE}/${GIT_BRANCH}"
  git -C "${REPO_DIR}" diff --cached -- "${stage_files[@]}" || true
  exit 0
fi

git -C "${REPO_DIR}" commit -m "${commit_msg}" -- "${stage_files[@]}"
git -C "${REPO_DIR}" push "${GIT_REMOTE}" "HEAD:${GIT_BRANCH}"

echo "Done."
echo "Pushed to ${GIT_REMOTE}/${GIT_BRANCH}"
echo "Summary: ${counts_line}"
