"""Docker domain service helpers.

This module keeps Docker domain logic out of app.py while preserving
existing payload shapes and error semantics.
"""

from __future__ import annotations

import json
import re
import shlex

from fcc.runtime.adapters import docker_adapter


def container_action(name: str, action: str) -> tuple[bool, str]:
    cname = str(name or "").strip()
    if not cname:
        return False, "docker 容器名为空"
    if action not in {"start", "stop", "restart"}:
        return False, "不支持的动作"
    try:
        out = docker_adapter.execute_docker([action, cname])
        if out.ok:
            return True, ""
        msg = str(out.message or "").strip()[:200]
        return False, msg or "docker 执行失败"
    except Exception as exc:
        return False, str(exc)


def safe_name(name: str) -> str:
    text = str(name or "").strip()
    if not text or len(text) > 128:
        return ""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", text):
        return ""
    return text


def safe_image(image: str) -> str:
    text = str(image or "").strip()
    if not text or len(text) > 255:
        return ""
    # docker image refs may include repo, tag and digest.
    if not re.fullmatch(r"[A-Za-z0-9._/@:-]+", text):
        return ""
    return text


def safe_kv(text: str) -> str:
    raw = str(text or "").strip()
    if not raw or len(raw) > 512:
        return ""
    if "\x00" in raw or "\n" in raw or "\r" in raw:
        return ""
    return raw


def collect_list(value) -> list[str]:
    if isinstance(value, list):
        source = value
    elif isinstance(value, str):
        source = [x.strip() for x in value.split(",")]
    else:
        source = []
    out = []
    for item in source:
        text = str(item or "").strip()
        if text:
            out.append(text)
    return out


def run(argv: list[str], timeout: float = 60.0) -> tuple[bool, str]:
    args = [str(x) for x in (argv or [])]
    if args and args[0] == "docker":
        args = args[1:]
    out = docker_adapter.execute_docker(args, timeout=timeout)
    if out.ok:
        return True, (out.stdout or "").strip()
    msg = str(out.message or "").strip()[:1000]
    return False, msg or "docker command failed"


def parse_percent(value) -> float:
    text = str(value or "").strip().replace("%", "")
    try:
        return round(max(0.0, float(text)), 2)
    except Exception:
        return 0.0


def json_lines(argv: list[str], timeout: float = 8.0) -> tuple[list[dict], str]:
    args = [str(x) for x in (argv or [])]
    if args and args[0] == "docker":
        args = args[1:]
    out = docker_adapter.execute_docker(args, timeout=timeout)
    if not out.ok:
        return [], str(out.message or "docker command failed").strip()[:500]
    rows = []
    for line in (out.stdout or "").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
            if isinstance(item, dict):
                rows.append(item)
        except Exception:
            continue
    return rows, ""


def images_payload() -> dict:
    rows, err = json_lines(
        ["docker", "images", "--format", "{{json .}}"],
        timeout=10.0,
    )
    if err:
        return {"ok": False, "available": False, "error": err, "images": []}
    images = []
    for row in rows:
        repo = str(row.get("Repository", "") or "").strip()
        tag = str(row.get("Tag", "") or "").strip()
        image_id = str(row.get("ID", "") or "").strip()
        size = str(row.get("Size", "") or "").strip()
        created = str(row.get("CreatedSince", "") or "").strip()
        ref = f"{repo}:{tag}" if repo and tag and tag != "<none>" else repo or image_id
        images.append(
            {
                "id": image_id,
                "repository": repo,
                "tag": tag,
                "ref": ref,
                "size": size or "-",
                "created": created or "-",
            }
        )
    images.sort(key=lambda x: str(x.get("ref", "")).lower())
    return {"ok": True, "available": True, "error": "", "images": images}


def pull_image(image: str) -> tuple[bool, str]:
    ref = safe_image(image)
    if not ref:
        return False, "invalid image reference"
    return run(["docker", "pull", ref], timeout=180.0)


def remove_image(image: str, force: bool = False) -> tuple[bool, str]:
    ref = safe_image(image)
    if not ref:
        return False, "invalid image reference"
    argv = ["docker", "rmi"]
    if force:
        argv.append("-f")
    argv.append(ref)
    return run(argv, timeout=90.0)


def remove_container(name: str, force: bool = False) -> tuple[bool, str]:
    cname = safe_name(name)
    if not cname:
        return False, "invalid container name"
    argv = ["docker", "rm"]
    if force:
        argv.append("-f")
    argv.append(cname)
    return run(argv, timeout=60.0)


def create_container(body: dict) -> tuple[bool, str]:
    name = safe_name((body or {}).get("name", ""))
    image = safe_image((body or {}).get("image", ""))
    if not name:
        return False, "invalid container name"
    if not image:
        return False, "invalid image reference"
    argv = ["docker", "run", "-d", "--name", name]
    restart_policy = str((body or {}).get("restart", "") or "").strip().lower()
    if restart_policy in {"no", "always", "unless-stopped", "on-failure"}:
        argv.extend(["--restart", restart_policy])
    network = safe_name((body or {}).get("network", "bridge"))
    if network:
        argv.extend(["--network", network])
    for port in collect_list((body or {}).get("ports")):
        safe = safe_kv(port)
        if safe and re.fullmatch(r"[0-9.:/-]+", safe):
            argv.extend(["-p", safe])
    for vol in collect_list((body or {}).get("volumes")):
        safe = safe_kv(vol)
        if safe and ":" in safe:
            argv.extend(["-v", safe])
    for env in collect_list((body or {}).get("env")):
        safe = safe_kv(env)
        if safe and "=" in safe:
            argv.extend(["-e", safe])
    command = str((body or {}).get("command", "") or "").strip()
    argv.append(image)
    if command:
        argv.extend(shlex.split(command))
    return run(argv, timeout=90.0)


def linked_roles(name: str, image: str, app_cfg: dict | None = None) -> list[str]:
    text = f"{name} {image}".lower()
    roles = []
    qbt_cfg = ((app_cfg or {}).get("qbt") or {}) if isinstance(app_cfg, dict) else {}
    qbt_container = str(qbt_cfg.get("docker_container", "") or "").strip().lower()
    if qbt_container and name.lower() == qbt_container:
        roles.append("BitTorrent")
    elif any(k in text for k in ("qbittorrent", "qbit", "deluge", "transmission", "rtorrent")):
        roles.append("BitTorrent")
    if any(k in text for k in ("ddns", "duckdns", "cloudflare-ddns", "ddns-go")):
        roles.append("DDNS")
    if any(k in text for k in ("afterclaw", "storage-http-link-web", "file-control-center")):
        roles.append("AfterClaw")
    return roles


def status_payload(
    app_cfg: dict | None = None,
    include_stats: bool = True,
    module_enabled: bool = True,
) -> dict:
    cfg = app_cfg if isinstance(app_cfg, dict) else {}
    if not module_enabled:
        return {
            "ok": True,
            "available": False,
            "disabled": True,
            "error": "Docker module is disabled",
            "summary": {"running": 0, "stopped": 0, "total": 0, "images": 0},
            "containers": [],
        }

    ps_rows, err = json_lines(
        ["docker", "ps", "-a", "--format", "{{json .}}"],
        timeout=8.0,
    )
    if err:
        return {
            "ok": False,
            "available": False,
            "disabled": False,
            "error": err,
            "summary": {"running": 0, "stopped": 0, "total": 0, "images": 0},
            "containers": [],
        }

    stats_rows = []
    if include_stats:
        stats_rows, _ = json_lines(
            ["docker", "stats", "--no-stream", "--format", "{{json .}}"],
            timeout=10.0,
        )
    stats_by_name = {}
    for item in stats_rows:
        nm = str(item.get("Name", "") or item.get("Container", "") or "").strip()
        if nm:
            stats_by_name[nm] = item

    image_count = 0
    try:
        out = docker_adapter.execute_docker(["images", "-q"], timeout=8.0)
        if out.ok:
            image_count = len({x.strip() for x in out.stdout.splitlines() if x.strip()})
    except Exception:
        image_count = 0

    containers = []
    running = 0
    for row in ps_rows:
        name = str(row.get("Names", "") or row.get("Name", "") or "").strip()
        image = str(row.get("Image", "") or "").strip()
        state = str(row.get("State", "") or "").strip().lower()
        status = str(row.get("Status", "") or "").strip()
        is_running = state == "running" or status.lower().startswith("up")
        if is_running:
            running += 1
        stat = stats_by_name.get(name, {})
        containers.append(
            {
                "id": str(row.get("ID", "") or "").strip(),
                "name": name,
                "image": image,
                "command": str(row.get("Command", "") or "").strip(),
                "status": status,
                "state": state or ("running" if is_running else "stopped"),
                "running": bool(is_running),
                "ports": str(row.get("Ports", "") or "").strip() or "-",
                "uptime": str(row.get("RunningFor", "") or "").strip() or "-",
                "cpu_pct": parse_percent(stat.get("CPUPerc", "")),
                "mem_usage": str(stat.get("MemUsage", "") or "").strip(),
                "mem_pct": parse_percent(stat.get("MemPerc", "")),
                "net_io": str(stat.get("NetIO", "") or "").strip(),
                "block_io": str(stat.get("BlockIO", "") or "").strip(),
                "pids": str(stat.get("PIDs", "") or "").strip(),
                "roles": linked_roles(name, image, cfg),
            }
        )
    containers.sort(key=lambda x: (not bool(x.get("running")), str(x.get("name", "")).lower()))
    total = len(containers)
    return {
        "ok": True,
        "available": True,
        "disabled": False,
        "error": "",
        "summary": {
            "running": running,
            "stopped": max(0, total - running),
            "total": total,
            "images": image_count,
        },
        "containers": containers,
    }


def container_logs(name: str, tail: int = 160) -> tuple[bool, str]:
    cname = safe_name(name)
    if not cname:
        return False, "invalid container name"
    try:
        tail_n = max(20, min(500, int(tail)))
    except Exception:
        tail_n = 160
    out = docker_adapter.execute_docker(
        ["logs", "--tail", str(tail_n), cname],
        timeout=10.0,
    )
    text = ((out.stdout or "") + (out.stderr or "")).strip()
    if not out.ok:
        return False, str(out.message or text[:1000] or "docker logs failed")
    return True, text[-24000:]
