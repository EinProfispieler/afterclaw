"""线程安全的运行状态。"""

from __future__ import annotations

import threading
import time
from typing import Any

_LOCK = threading.RLock()
_STATE: dict[str, Any] = {
    "thread_started": False,
    "last_ok": None,
    "last_v4": None,
    "last_v6": None,
    "last_error": None,
    "last_run_ts": 0.0,
}


def lock():
    return _LOCK


def get_state() -> dict[str, Any]:
    with _LOCK:
        return dict(_STATE)


def mark_thread_started() -> bool:
    with _LOCK:
        if _STATE.get("thread_started"):
            return False
        _STATE["thread_started"] = True
        return True


def set_error(err: str | None) -> None:
    with _LOCK:
        _STATE["last_error"] = err
        _STATE["last_run_ts"] = time.time()


def set_ok(v4: str | None, v6: str | None) -> None:
    with _LOCK:
        t = time.time()
        _STATE["last_error"] = None
        _STATE["last_ok"] = t
        _STATE["last_run_ts"] = t
        if v4 is not None:
            _STATE["last_v4"] = v4
        if v6 is not None:
            _STATE["last_v6"] = v6
