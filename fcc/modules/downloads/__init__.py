"""Download runtime state helpers."""

from __future__ import annotations

import os
import threading

from fcc.modules import Module, register


_state_lock = threading.Lock()
_downloads_enabled = True
_http_cut_epoch = 0


def init_from_env() -> None:
    global _downloads_enabled
    raw = str(os.environ.get("DOWNLOADS_ENABLED", "1")).strip().lower()
    enabled = raw not in {"0", "false", "off", "no"}
    with _state_lock:
        _downloads_enabled = enabled


def is_downloads_enabled() -> bool:
    with _state_lock:
        return bool(_downloads_enabled)


def set_downloads_enabled(enabled: bool) -> None:
    global _downloads_enabled
    with _state_lock:
        _downloads_enabled = bool(enabled)


def cut_http_downloads() -> int:
    global _http_cut_epoch
    with _state_lock:
        _http_cut_epoch += 1
        return _http_cut_epoch


def get_cut_epoch() -> int:
    with _state_lock:
        return int(_http_cut_epoch)


def is_http_module_enabled(cfg: dict | None = None) -> bool:
    if not isinstance(cfg, dict):
        return True
    mods = cfg.get("modules") or {}
    if "http" in mods:
        return bool(mods.get("http"))
    if "http_monitor" in mods:
        return bool(mods.get("http_monitor"))
    return True


module = Module(name="http", display_name="HTTP Downloads", description="Runtime HTTP download gate")
register(module)
