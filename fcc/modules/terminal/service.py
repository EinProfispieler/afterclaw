"""Terminal service bridge.

Bridges modular layer to shared runtime helpers in ``app.py``.
"""

from __future__ import annotations

import app as runtime_app


def build_terminal_launch_meta(cfg: dict) -> dict:
    return runtime_app._build_terminal_launch_meta(cfg)


def build_terminal_ssh_argv(cfg: dict):
    return runtime_app._build_terminal_ssh_argv(cfg)


def start_session(handler, body: dict, client_ip: str) -> dict:
    sid, meta = handler._terminal_start_session(
        body.get("cols", 120), body.get("rows", 30), client_ip
    )
    return {"ok": True, "session_id": sid, "meta": meta}


def list_sessions(handler) -> dict:
    return {"ok": True, **handler._terminal_list_sessions()}


def history(handler, body: dict) -> dict:
    data = handler._terminal_get_history(
        body.get("limit", 200),
        body.get("keyword", ""),
        body.get("client_ip", ""),
        body.get("session_id", ""),
    )
    return {"ok": True, **data}


def clear_history(handler) -> dict:
    return handler._terminal_clear_history()


def read_session(handler, body: dict) -> dict:
    return handler._terminal_read_session(
        body.get("session_id"), body.get("max_bytes", 131072)
    )


def write_session(handler, body: dict) -> dict:
    return handler._terminal_write_session(
        body.get("session_id"), body.get("data", "")
    )


def resize_session(handler, body: dict) -> dict:
    return handler._terminal_resize_session(
        body.get("session_id"), body.get("cols", 120), body.get("rows", 30)
    )


def close_session(handler, body: dict) -> dict:
    return handler._terminal_close_session(body.get("session_id"))


def revoke_session(handler, body: dict) -> dict:
    sid = str(body.get("session_id", "") or "").strip()
    if not sid:
        raise ValueError("Missing session_id")
    data = handler._terminal_close_session(sid)
    return {"ok": True, "revoked": bool(data.get("closed", False)), "session_id": sid}


def upload_key_file(body: dict, app_root) -> dict:
    if not isinstance(body, dict):
        raise ValueError("Request body must be a JSON object")
    file_name, size = runtime_app._save_terminal_key_file(
        body.get("file_name", ""),
        body.get("content_b64", ""),
        app_root,
    )
    current = runtime_app.load_app_config(app_root)
    term_cfg = current.setdefault("terminal", {})
    term_cfg["auth_mode"] = "key"
    term_cfg["key_file"] = file_name
    saved = runtime_app.save_app_config(current, app_root)
    return {
        "ok": True,
        "file_name": file_name,
        "size": int(size),
        "config": saved,
        "terminal": runtime_app._build_terminal_launch_meta(saved),
    }
