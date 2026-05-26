"""File browsing, HTTP distribution, speed monitoring, and transfer tracking."""

import mimetypes
import os
import threading
import time
from http import HTTPStatus
from pathlib import Path
from urllib.parse import quote, unquote, parse_qs

from fcc.config import (
    STORAGE_ROOT, WEB_PORT, PUBLIC_SCHEME, PUBLIC_HOST,
    load_app_config, app_root, _normalize_rel_dir_setting,
)
from fcc.modules import Module, register
from fcc.modules.downloads import is_downloads_enabled, get_cut_epoch
from fcc.security import ensure_under_root, safe_relative_path


module = Module()
module.name = "files"
module.display_name = "Files"
module.description = "File browsing and HTTP distribution"


def human_size(size: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(size)
    idx = 0
    while value >= 1024 and idx < len(units) - 1:
        value /= 1024.0
        idx += 1
    if idx == 0:
        return f"{int(value)}{units[idx]}"
    return f"{value:.1f}{units[idx]}"


# --------------- Speed tracking state ---------------
_speed_lock = threading.Lock()
_speed_state = {"iface": None, "last_ts": 0.0, "last_tx": 0, "tx_mibps": 0.0, "tx_mbps": 0.0}

_transfers_lock = threading.Lock()
_active_transfers: dict[str, dict] = {}


def _detect_default_iface():
    try:
        with open("/proc/net/route", "r") as f:
            lines = f.readlines()[1:]
        for line in lines:
            cols = line.strip().split()
            if len(cols) >= 3 and cols[1] == "00000000":
                return cols[0]
    except Exception:
        return None
    return None


def _read_iface_tx_bytes(iface: str) -> int:
    if not iface:
        return 0
    try:
        with open("/proc/net/dev", "r") as f:
            for line in f:
                if f"{iface}:" not in line:
                    continue
                left, right = line.split(":", 1)
                if left.strip() != iface:
                    continue
                parts = right.split()
                if len(parts) >= 10:
                    return int(parts[8])
    except Exception:
        pass
    return 0


def _count_established_conn() -> int:
    target_port = f"{WEB_PORT:04X}"

    def count_file(path: str) -> int:
        total = 0
        try:
            with open(path, "r") as f:
                for line in f.readlines()[1:]:
                    cols = line.strip().split()
                    if len(cols) < 4:
                        continue
                    local = cols[1]
                    state = cols[3]
                    if state != "01":
                        continue
                    if ":" in local and local.split(":", 1)[1].upper() == target_port:
                        total += 1
        except Exception:
            pass
        return total

    return count_file("/proc/net/tcp") + count_file("/proc/net/tcp6")


def speed_snapshot() -> dict:
    with _speed_lock:
        now = time.time()
        iface = _speed_state.get("iface")
        if not iface:
            iface = _detect_default_iface()
            _speed_state["iface"] = iface
        tx_now = _read_iface_tx_bytes(iface)
        last_ts = float(_speed_state.get("last_ts", 0.0) or 0.0)
        last_tx = int(_speed_state.get("last_tx", 0) or 0)
        tx_mibps = float(_speed_state.get("tx_mibps", 0.0) or 0.0)
        tx_mbps = float(_speed_state.get("tx_mbps", 0.0) or 0.0)
        if last_ts > 0 and tx_now >= last_tx and now > last_ts:
            delta_bytes = tx_now - last_tx
            delta_sec = now - last_ts
            tx_mibps = delta_bytes / 1024.0 / 1024.0 / delta_sec
            tx_mbps = delta_bytes * 8.0 / 1024.0 / 1024.0 / delta_sec
        _speed_state.update(last_ts=now, last_tx=tx_now, tx_mibps=tx_mibps, tx_mbps=tx_mbps)
        return {
            "iface": iface or "",
            "tx_mibps": tx_mibps,
            "tx_mbps": tx_mbps,
            "active_conn_1288": _count_established_conn(),
        }


def transfer_snapshot() -> dict:
    now = time.time()
    with _transfers_lock:
        items = []
        for tid, t in _active_transfers.items():
            elapsed = max(now - float(t.get("started_at", now)), 0.001)
            sent = int(t.get("sent_bytes", 0))
            total = int(t.get("total_bytes", 0))
            mibps = sent / 1024.0 / 1024.0 / elapsed
            items.append({
                "id": tid,
                "client_ip": t.get("client_ip", ""),
                "relative_path": t.get("relative_path", ""),
                "filename": t.get("filename", ""),
                "sent_bytes": sent,
                "sent_human": human_size(sent),
                "total_bytes": total,
                "total_human": human_size(total),
                "progress_pct": (sent * 100.0 / total) if total > 0 else 0.0,
                "speed_mibps": mibps,
                "started_at": float(t.get("started_at", now)),
            })
    items.sort(key=lambda x: x["started_at"], reverse=True)
    return {"items": items, "count": len(items)}


def build_http_url(relative_path: str) -> str:
    encoded_path = quote(relative_path, safe="/")
    return f"{PUBLIC_SCHEME}://{PUBLIC_HOST}/http-files/{encoded_path}"


def list_child_directories(storage_root: Path, rel_dir: str) -> list[str]:
    target_dir = ensure_under_root(storage_root, storage_root / rel_dir)
    if not target_dir.exists() or not target_dir.is_dir():
        raise FileNotFoundError("目录不存在")
    children = []
    for entry in target_dir.iterdir():
        if not entry.is_dir() or entry.name.startswith("."):
            continue
        rel = entry.relative_to(storage_root).as_posix()
        children.append(rel)
    return sorted(children)


def directory_stats(storage_root: Path, rel_dir: str) -> dict:
    target_dir = ensure_under_root(storage_root, storage_root / rel_dir)
    if not target_dir.exists() or not target_dir.is_dir():
        raise FileNotFoundError("目录不存在")
    total_files = total_dirs = total_size = 0
    for root, dirnames, filenames in os.walk(target_dir):
        visible_dirs = [d for d in dirnames if not d.startswith(".")]
        dirnames[:] = visible_dirs
        visible_files = [f for f in filenames if not f.startswith(".")]
        total_dirs += len(visible_dirs)
        total_files += len(visible_files)
        for name in visible_files:
            fp = Path(root) / name
            try:
                total_size += int(fp.stat().st_size)
            except Exception:
                continue
    return {
        "total_files": total_files,
        "total_dirs": total_dirs,
        "total_size": total_size,
        "total_size_human": human_size(total_size),
    }


# --------------- Route handlers ---------------

def _handle_base(handler, parsed, params, body):
    if not handler._require_lan():
        return
    app_cfg = load_app_config(app_root())
    http_cfg = (app_cfg or {}).get("http_service") or {}
    from fcc.modules.terminal.service import build_terminal_launch_meta
    handler._send_json({
        "storage_root": str(STORAGE_ROOT),
        "web_port": WEB_PORT,
        "public_base_url": f"{PUBLIC_SCHEME}://{PUBLIC_HOST}",
        "downloads_enabled": is_downloads_enabled(),
        "default_http_dir": _normalize_rel_dir_setting(http_cfg.get("default_dir", ".")),
        "terminal": build_terminal_launch_meta(app_cfg),
    })


def _handle_speed(handler, parsed, params, body):
    if not handler._require_lan():
        return
    handler._send_json(speed_snapshot())


def _handle_transfers(handler, parsed, params, body):
    if not handler._require_lan():
        return
    # Keep transfer payload aligned with app-wide snapshot logic so
    # dashboard/workload widgets show the same active+recent semantics.
    handler._send_json(handler._transfer_snapshot())


def _handle_directories(handler, parsed, params, body):
    if not handler._require_lan():
        return
    try:
        query = parse_qs(parsed.query)
        rel_dir = safe_relative_path(query.get("dir", ["."])[0])
        directories = list_child_directories(STORAGE_ROOT, rel_dir)
        stats = directory_stats(STORAGE_ROOT, rel_dir)
        handler._send_json({"directories": directories, "current_dir": rel_dir, "stats": stats})
    except ValueError as exc:
        handler._error(str(exc), status=HTTPStatus.FORBIDDEN)
    except FileNotFoundError as exc:
        handler._error(str(exc), status=HTTPStatus.NOT_FOUND)
    except Exception as exc:
        handler._error(f"目录查询失败: {exc}", status=HTTPStatus.INTERNAL_SERVER_ERROR)


def _handle_files(handler, parsed, params, body):
    if not handler._require_lan():
        return
    try:
        query = parse_qs(parsed.query)
        rel_dir = safe_relative_path(query.get("dir", ["."])[0])
        target_dir = ensure_under_root(STORAGE_ROOT, STORAGE_ROOT / rel_dir)
        if not target_dir.exists() or not target_dir.is_dir():
            handler._error("目录不存在", status=HTTPStatus.NOT_FOUND)
            return
        items = []
        for root, _, files in os.walk(target_dir):
            for filename in files:
                full_path = Path(root) / filename
                rel_file = full_path.relative_to(STORAGE_ROOT).as_posix()
                file_size = full_path.stat().st_size
                items.append({
                    "relative_path": rel_file,
                    "size": file_size,
                    "size_human": human_size(file_size),
                    "http_url": build_http_url(rel_file),
                })
        items.sort(key=lambda x: x["relative_path"])
        handler._send_json({"items": items})
    except ValueError as exc:
        handler._error(str(exc), status=HTTPStatus.FORBIDDEN)
    except Exception as exc:
        handler._error(f"扫描失败: {exc}", status=HTTPStatus.INTERNAL_SERVER_ERROR)


def _handle_http_file(handler, parsed, params, body, send_body=True):
    if not is_downloads_enabled():
        handler._error("外网下载已关闭", status=HTTPStatus.FORBIDDEN)
        return
    try:
        rel_file = unquote(parsed.path[len("/http-files/"):]).lstrip("/")
        rel_file = safe_relative_path(rel_file)
        target_file = ensure_under_root(STORAGE_ROOT, STORAGE_ROOT / rel_file)
        _send_file(handler, target_file, send_body=send_body)
    except ValueError as exc:
        handler._error(str(exc), status=HTTPStatus.FORBIDDEN)
    except Exception as exc:
        handler._error(f"下载失败: {exc}", status=HTTPStatus.INTERNAL_SERVER_ERROR)


def _handle_http_file_get(handler, parsed, params, body):
    _handle_http_file(handler, parsed, params, body, send_body=True)


def _handle_http_file_head(handler, parsed, params, body):
    _handle_http_file(handler, parsed, params, body, send_body=False)


def _handle_dashboard_css(handler, parsed, params, body):
    if not handler._require_lan():
        return
    p = Path(app_root()) / "web" / "dashboard.css"
    if not p.is_file():
        handler._error("未找到资源", status=HTTPStatus.NOT_FOUND)
        return
    data = p.read_bytes()
    handler.send_response(HTTPStatus.OK)
    handler.send_header("Content-Type", "text/css; charset=utf-8")
    handler.send_header("Cache-Control", "private, max-age=60")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def _handle_static_vendor(handler, parsed, params, body):
    if not handler._require_lan():
        return
    rel = parsed.path.lstrip("/")
    web_root = (Path(app_root()) / "web").resolve()
    try:
        target = ensure_under_root(web_root, web_root / rel)
    except ValueError:
        handler._error("路径非法", status=HTTPStatus.FORBIDDEN)
        return
    if not target.exists() or not target.is_file():
        handler._error("未找到资源", status=HTTPStatus.NOT_FOUND)
        return
    content_type, _ = mimetypes.guess_type(str(target))
    content_type = content_type or "application/octet-stream"
    data = target.read_bytes()
    handler.send_response(HTTPStatus.OK)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Cache-Control", "private, max-age=300")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def _send_file(handler, file_path: Path, send_body: bool = True):
    if not file_path.exists() or not file_path.is_file():
        handler._error("文件不存在", status=HTTPStatus.NOT_FOUND)
        return
    try:
        content_type, _ = mimetypes.guess_type(str(file_path))
        content_type = content_type or "application/octet-stream"
        file_size = file_path.stat().st_size
        filename = quote(file_path.name)
        start = 0
        end = file_size - 1
        status_code = HTTPStatus.OK
        range_header = (handler.headers.get("Range") or "").strip()
        if range_header.startswith("bytes="):
            try:
                range_spec = range_header[6:].strip()
                if "," in range_spec:
                    handler.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                    handler.send_header("Content-Range", f"bytes */{file_size}")
                    handler.send_header("Content-Length", "0")
                    handler.send_header("Accept-Ranges", "bytes")
                    handler.end_headers()
                    return
                if range_spec.startswith("-"):
                    suffix = int(range_spec[1:] or "0")
                    if suffix <= 0:
                        handler.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                        handler.send_header("Content-Range", f"bytes */{file_size}")
                        handler.send_header("Content-Length", "0")
                        handler.send_header("Accept-Ranges", "bytes")
                        handler.end_headers()
                        return
                    start = max(file_size - suffix, 0)
                else:
                    if "-" in range_spec:
                        left, right = range_spec.split("-", 1)
                    else:
                        left, right = range_spec, ""
                    start = int(left or "0")
                    if right.strip():
                        end = int(right)
            except ValueError:
                handler.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                handler.send_header("Content-Range", f"bytes */{file_size}")
                handler.send_header("Content-Length", "0")
                handler.send_header("Accept-Ranges", "bytes")
                handler.end_headers()
                return
            if start < 0 or start >= file_size:
                handler.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                handler.send_header("Content-Range", f"bytes */{file_size}")
                handler.send_header("Content-Length", "0")
                handler.send_header("Accept-Ranges", "bytes")
                handler.end_headers()
                return
            end = min(end, file_size - 1)
            if end < start:
                handler.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                handler.send_header("Content-Range", f"bytes */{file_size}")
                handler.send_header("Content-Length", "0")
                handler.send_header("Accept-Ranges", "bytes")
                handler.end_headers()
                return
            status_code = HTTPStatus.PARTIAL_CONTENT

        content_len = end - start + 1
        handler.send_response(status_code)
        handler.send_header("Content-Type", content_type)
        handler.send_header("Content-Length", str(content_len))
        handler.send_header("Content-Disposition", f"inline; filename*=UTF-8''{filename}")
        handler.send_header("Accept-Ranges", "bytes")
        if status_code == HTTPStatus.PARTIAL_CONTENT:
            handler.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
        handler.end_headers()
        if send_body:
            try:
                rel_path = file_path.relative_to(STORAGE_ROOT).as_posix()
            except Exception:
                rel_path = file_path.name
            transfer_id = f"{threading.get_ident()}-{int(time.time() * 1000)}"
            cut_epoch = get_cut_epoch()
            with _transfers_lock:
                _active_transfers[transfer_id] = {
                    "client_ip": handler._client_ip(),
                    "relative_path": rel_path,
                    "filename": file_path.name,
                    "sent_bytes": 0,
                    "total_bytes": content_len,
                    "started_at": time.time(),
                    "cut_epoch": cut_epoch,
                }
            with file_path.open("rb") as f:
                f.seek(start)
                remaining = content_len
                try:
                    while remaining > 0:
                        now_epoch = get_cut_epoch()
                        if now_epoch != cut_epoch:
                            handler.close_connection = True
                            break
                        chunk = f.read(1024 * 1024)
                        if not chunk:
                            break
                        if len(chunk) > remaining:
                            chunk = chunk[:remaining]
                        handler.wfile.write(chunk)
                        sent_now = len(chunk)
                        remaining -= sent_now
                        with _transfers_lock:
                            tr = _active_transfers.get(transfer_id)
                            if tr is not None:
                                tr["sent_bytes"] = int(tr.get("sent_bytes", 0)) + sent_now
                finally:
                    with _transfers_lock:
                        _active_transfers.pop(transfer_id, None)
    except Exception as exc:
        handler._error(f"文件读取失败: {exc}", status=HTTPStatus.INTERNAL_SERVER_ERROR)


# --------------- Register routes ---------------

module.add_route("GET", "/api/base", _handle_base)
module.add_route("GET", "/api/speed", _handle_speed)
module.add_route("GET", "/api/transfers", _handle_transfers)
module.add_route("GET", "/api/directories", _handle_directories)
module.add_route("GET", "/api/files", _handle_files)
module.add_route("GET", "/dashboard.css", _handle_dashboard_css)

register(module)
