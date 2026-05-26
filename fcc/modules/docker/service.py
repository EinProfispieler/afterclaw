"""Docker domain service helpers.

This module keeps Docker domain logic out of app.py while preserving
existing payload shapes and error semantics.
"""

from __future__ import annotations

from collections import deque
import json
import os
from pathlib import Path
import re
import shlex
import threading
import time

from fcc.config import app_root
from fcc.runtime.adapters import docker_adapter


def _env_int(name: str, default: int, minimum: int = 1, maximum: int = 20000) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        val = int(str(raw).strip())
    except Exception:
        return default
    return max(minimum, min(maximum, val))


def _env_float(name: str, default: float, minimum: float = 0.0, maximum: float = 60.0) -> float:
    raw = os.environ.get(name)
    if raw is None:
        return float(default)
    try:
        val = float(str(raw).strip())
    except Exception:
        return float(default)
    if val < minimum:
        return minimum
    if val > maximum:
        return maximum
    return val


_DOCKER_OPS_HISTORY_MAX = _env_int("DOCKER_OPS_HISTORY_MAX", 2000, minimum=100, maximum=20000)
_UPGRADE_RECREATE_DELAY_SEC = _env_float("DOCKER_UPGRADE_RECREATE_DELAY_SEC", 0.0, minimum=0.0, maximum=30.0)
_DOCKER_OPS_LOCK = threading.Lock()
_DOCKER_OPS_HISTORY = deque(maxlen=_DOCKER_OPS_HISTORY_MAX)
_DOCKER_OPS_LOADED = False
_DOCKER_OPS_FILE_NAME = "docker_ops_history.jsonl"


def _operation_history_path() -> Path:
    configured = str(os.environ.get("DOCKER_OPS_HISTORY_FILE", "") or "").strip()
    if configured:
        return Path(configured).expanduser()
    return app_root() / _DOCKER_OPS_FILE_NAME


def _ensure_operation_history_loaded_locked() -> None:
    global _DOCKER_OPS_LOADED
    if _DOCKER_OPS_LOADED:
        return
    path = _operation_history_path()
    try:
        lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
        for line in lines[-_DOCKER_OPS_HISTORY_MAX:]:
            try:
                row = json.loads(line)
            except Exception:
                continue
            if isinstance(row, dict):
                _DOCKER_OPS_HISTORY.append(row)
    except Exception:
        pass
    _DOCKER_OPS_LOADED = True


def _persist_operation_history_locked() -> bool:
    path = _operation_history_path()
    temp = path.with_name(f".{path.name}.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        content = "\n".join(json.dumps(x, ensure_ascii=False) for x in _DOCKER_OPS_HISTORY)
        if content:
            content += "\n"
        temp.write_text(content, encoding="utf-8")
        temp.replace(path)
        return True
    except Exception:
        try:
            temp.unlink(missing_ok=True)
        except Exception:
            pass
        return False


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


def _load_source_policy() -> dict:
    try:
        path = app_root() / "app_config.json"
        if not path.is_file():
            return {}
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            sp = data.get("source_policy")
            return dict(sp) if isinstance(sp, dict) else {}
    except Exception:
        return {}
    return {}


def _docker_source_host_from_policy(source_policy: dict | None) -> str:
    sp = dict(source_policy or {})
    profile = str(sp.get("docker_source_profile", "official") or "official").strip().lower()
    presets = {
        "official": "",
        "china": "docker.1ms.run",
        # AWS presets are templates for pull-through cache hosts.
        "aws_us": "111122223333.dkr.ecr.us-east-1.amazonaws.com/docker-hub",
        "aws_eu": "111122223333.dkr.ecr.eu-west-1.amazonaws.com/docker-hub",
        "aws_ap": "111122223333.dkr.ecr.ap-southeast-1.amazonaws.com/docker-hub",
    }
    return str(presets.get(profile, "") or "").strip("/")


def _apply_docker_source_policy(image: str, source_policy: dict | None) -> str:
    ref = safe_image(image)
    if not ref:
        return ""
    mirror_host = _docker_source_host_from_policy(source_policy)
    if not mirror_host:
        return ref
    if "/" not in ref:
        return f"{mirror_host}/library/{ref}"
    first = ref.split("/", 1)[0].lower()
    if "." in first or ":" in first:
        # Already explicit registry, leave unchanged.
        return ref
    return f"{mirror_host}/{ref}"


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
    source_policy = _load_source_policy()
    effective_ref = _apply_docker_source_policy(ref, source_policy)
    return run(["docker", "pull", effective_ref], timeout=180.0)


def image_exists(image: str) -> bool:
    ref = safe_image(image)
    if not ref:
        return False
    out = docker_adapter.execute_docker(["image", "inspect", ref], timeout=20.0)
    return bool(out.ok)


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


def _restart_policy_value(value: str) -> str:
    v = str(value or "").strip().lower()
    return v if v in {"no", "always", "unless-stopped", "on-failure"} else ""


def snapshot_container(name: str) -> tuple[bool, dict | str]:
    cname = safe_name(name)
    if not cname:
        return False, "invalid container name"
    out = docker_adapter.execute_docker(["inspect", cname], timeout=12.0)
    if not out.ok:
        return False, str(out.message or out.stderr or out.stdout or "docker inspect failed").strip()
    try:
        payload = json.loads(str(out.stdout or "[]"))
        if not isinstance(payload, list) or not payload or not isinstance(payload[0], dict):
            return False, "invalid inspect payload"
        raw = payload[0]
    except Exception as exc:
        return False, f"invalid inspect json: {exc}"

    config = dict(raw.get("Config") or {})
    host = dict(raw.get("HostConfig") or {})
    state = dict(raw.get("State") or {})
    mounts = list(raw.get("Mounts") or [])
    port_bindings = dict(host.get("PortBindings") or {})

    volumes: list[str] = []
    for m in mounts:
        if not isinstance(m, dict):
            continue
        src = str(m.get("Source", "") or "").strip()
        dst = str(m.get("Destination", "") or "").strip()
        if not src or not dst:
            continue
        rw = bool(m.get("RW", True))
        mode = "rw" if rw else "ro"
        volumes.append(f"{src}:{dst}:{mode}")

    ports: list[str] = []
    for container_port, bindings in port_bindings.items():
        cport = str(container_port or "").strip()
        if not cport:
            continue
        if not isinstance(bindings, list):
            continue
        for binding in bindings:
            if not isinstance(binding, dict):
                continue
            hport = str(binding.get("HostPort", "") or "").strip()
            if not hport:
                continue
            hip = str(binding.get("HostIp", "") or "").strip()
            if hip and hip not in {"0.0.0.0", "::"}:
                ports.append(f"{hip}:{hport}:{cport}")
            else:
                ports.append(f"{hport}:{cport}")

    cmd = config.get("Cmd")
    cmd_parts = [str(x) for x in cmd] if isinstance(cmd, list) else []
    command = " ".join(shlex.quote(x) for x in cmd_parts if x)

    image_ref = str(config.get("Image", "") or "").strip()
    restart_policy = _restart_policy_value(str((host.get("RestartPolicy") or {}).get("Name", "") or ""))
    network_mode = str(host.get("NetworkMode", "") or "").strip()
    if network_mode == "default":
        network_mode = "bridge"
    env = [str(x) for x in list(config.get("Env") or []) if str(x or "").strip()]
    running = bool((state or {}).get("Running", False))

    return True, {
        "name": cname,
        "image": image_ref,
        "running": running,
        "restart": restart_policy or "unless-stopped",
        "network": network_mode or "bridge",
        "ports": ports,
        "volumes": volumes,
        "env": env,
        "command": command,
    }


def create_container_from_snapshot(snapshot: dict, image: str) -> tuple[bool, str]:
    body = {
        "name": str((snapshot or {}).get("name", "") or "").strip(),
        "image": str(image or "").strip(),
        "ports": list((snapshot or {}).get("ports") or []),
        "volumes": list((snapshot or {}).get("volumes") or []),
        "env": list((snapshot or {}).get("env") or []),
        "restart": str((snapshot or {}).get("restart", "unless-stopped") or "unless-stopped"),
        "network": str((snapshot or {}).get("network", "bridge") or "bridge"),
        "command": str((snapshot or {}).get("command", "") or "").strip(),
    }
    return create_container(body)


def upgrade_container_with_rollback(
    name: str,
    image: str,
    restart_after_pull: bool = True,
    allow_offline_local: bool = False,
) -> tuple[bool, dict]:
    cname = safe_name(name)
    ref = safe_image(image)
    if not cname:
        return False, {"error": "invalid container name"}
    if not ref:
        return False, {"error": "invalid image reference"}

    ok_snapshot, snapshot_or_err = snapshot_container(cname)
    if not ok_snapshot:
        return False, {"error": f"snapshot failed: {snapshot_or_err}"}
    snapshot = dict(snapshot_or_err or {})
    previous_image = str(snapshot.get("image", "") or "").strip()
    previous_running = bool(snapshot.get("running", False))

    ok_pull, msg_pull = pull_image(ref)
    pulled = bool(ok_pull)
    pull_skipped = False
    if not ok_pull:
        if allow_offline_local and image_exists(ref):
            pull_skipped = True
        else:
            return False, {"error": f"docker pull failed: {msg_pull}"}
    if not restart_after_pull:
        return True, {
            "name": cname,
            "image": ref,
            "pulled": pulled,
            "pull_skipped": pull_skipped,
            "recreated": False,
            "rollback_attempted": False,
            "rollback_ok": False,
            "backup_id": "",
        }

    backup_id = f"{cname}-preupgrade-{int(time.time())}"

    if previous_running:
        ok_stop, msg_stop = container_action(cname, "stop")
        if not ok_stop:
            return False, {"error": f"docker stop failed: {msg_stop}"}

    ok_rename_old, msg_rename_old = run(["docker", "rename", cname, backup_id], timeout=30.0)
    if not ok_rename_old:
        if previous_running:
            container_action(cname, "start")
        return False, {"error": f"docker rename failed: {msg_rename_old}"}

    # Drill helper: widen the race window for failure-injection rehearsals.
    if _UPGRADE_RECREATE_DELAY_SEC > 0:
        time.sleep(_UPGRADE_RECREATE_DELAY_SEC)

    ok_new, msg_new = create_container_from_snapshot(snapshot, ref)
    if ok_new:
        if not previous_running:
            container_action(cname, "stop")
        remove_container(backup_id, force=True)
        return True, {
            "name": cname,
            "image": ref,
            "pulled": pulled,
            "pull_skipped": pull_skipped,
            "recreated": True,
            "rollback_attempted": False,
            "rollback_ok": False,
            "backup_id": backup_id,
        }

    rollback_ok = False
    rollback_error = ""
    run(["docker", "rm", "-f", cname], timeout=45.0)
    ok_rename_back, msg_rename_back = run(["docker", "rename", backup_id, cname], timeout=30.0)
    if not ok_rename_back:
        rollback_error = f"rename rollback failed: {msg_rename_back}"
    else:
        if previous_running:
            ok_start, msg_start = container_action(cname, "start")
            if not ok_start:
                rollback_error = f"rollback start failed: {msg_start}"
            else:
                rollback_ok = True
        else:
            rollback_ok = True

    err = f"docker recreate failed: {msg_new}"
    if rollback_error:
        err = f"{err}; rollback error: {rollback_error}"
    return False, {
        "error": err,
        "name": cname,
        "image": ref,
        "pulled": pulled,
        "pull_skipped": pull_skipped,
        "recreated": False,
        "rollback_attempted": True,
        "rollback_ok": rollback_ok,
        "backup_id": backup_id,
        "previous_image": previous_image,
    }


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


def record_operation(
    action: str,
    *,
    ok: bool,
    source: str = "",
    name: str = "",
    image: str = "",
    message: str = "",
    client_ip: str = "",
    extra: dict | None = None,
) -> None:
    item = {
        "ts": int(time.time()),
        "action": str(action or "").strip().lower(),
        "ok": bool(ok),
        "source": str(source or "").strip(),
        "name": str(name or "").strip(),
        "image": str(image or "").strip(),
        "message": str(message or "").strip()[:800],
        "client_ip": str(client_ip or "").strip(),
    }
    if isinstance(extra, dict) and extra:
        safe_extra = {}
        for k, v in extra.items():
            key = str(k or "").strip()
            if not key:
                continue
            if isinstance(v, (str, int, float, bool)) or v is None:
                safe_extra[key] = v
            else:
                safe_extra[key] = str(v)
        if safe_extra:
            item["extra"] = safe_extra
    with _DOCKER_OPS_LOCK:
        _ensure_operation_history_loaded_locked()
        _DOCKER_OPS_HISTORY.append(item)
        _persist_operation_history_locked()


def list_operation_history(
    *,
    limit: int = 200,
    action: str = "",
    name: str = "",
    ok: bool | None = None,
) -> dict:
    try:
        n = int(limit)
    except Exception:
        n = 200
    n = max(1, min(10000, n))
    act = str(action or "").strip().lower()
    cname = str(name or "").strip().lower()
    with _DOCKER_OPS_LOCK:
        _ensure_operation_history_loaded_locked()
        rows = list(_DOCKER_OPS_HISTORY)
    if act:
        rows = [x for x in rows if str(x.get("action", "")).lower() == act]
    if cname:
        rows = [x for x in rows if cname in str(x.get("name", "")).lower()]
    if ok is not None:
        rows = [x for x in rows if bool(x.get("ok")) is bool(ok)]
    if len(rows) > n:
        rows = rows[-n:]
    rows.reverse()
    return {"items": rows, "count": len(rows), "max": _DOCKER_OPS_HISTORY_MAX}


def clear_operation_history() -> dict:
    with _DOCKER_OPS_LOCK:
        _ensure_operation_history_loaded_locked()
        removed = len(_DOCKER_OPS_HISTORY)
        _DOCKER_OPS_HISTORY.clear()
        persisted = _persist_operation_history_locked()
    return {"ok": True, "removed": int(removed), "persisted": bool(persisted)}


def export_operation_history(*, fmt: str = "jsonl", limit: int = 5000) -> dict:
    data = list_operation_history(limit=limit)
    rows = list(data.get("items") or [])
    format_text = str(fmt or "jsonl").strip().lower()
    if format_text not in {"jsonl", "json"}:
        format_text = "jsonl"
    if format_text == "json":
        content = json.dumps(rows, ensure_ascii=False, indent=2)
        filename = "afterclaw-docker-ops-history.json"
    else:
        content = "\n".join(json.dumps(x, ensure_ascii=False) for x in rows)
        if content:
            content += "\n"
        filename = "afterclaw-docker-ops-history.jsonl"
    return {
        "ok": True,
        "format": format_text,
        "filename": filename,
        "line_count": len(rows),
        "content": content,
    }
