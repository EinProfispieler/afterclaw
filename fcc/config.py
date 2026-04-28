"""Unified config helpers for FCC.

This module is intentionally lightweight and stdlib-only so both the
legacy runtime and future modular runtime can share it.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

APP_CONFIG_FILE_NAME = "app_config.json"

_APP_ROOT = Path(
    os.environ.get("APP_ROOT", Path(__file__).resolve().parent.parent)
).expanduser().resolve()

WEB_PORT = int(os.environ.get("WEB_PORT", "1288"))
STORAGE_ROOT = Path(os.environ.get("STORAGE_ROOT", "/srv/Storage")).expanduser().resolve()
PUBLIC_SCHEME = os.environ.get("PUBLIC_SCHEME", "http").strip() or "http"
PUBLIC_HOST = (
    os.environ.get("PUBLIC_HOST", f"home.rxotc.cn:{WEB_PORT}").strip()
    or f"home.rxotc.cn:{WEB_PORT}"
)


def app_root() -> Path:
    return _APP_ROOT


def set_app_root(path: Path | str) -> Path:
    global _APP_ROOT
    _APP_ROOT = Path(path).expanduser().resolve()
    return _APP_ROOT


def app_config_path(root: Path | None = None) -> Path:
    base = Path(root or app_root())
    return base / APP_CONFIG_FILE_NAME


def _normalize_rel_dir_setting(value) -> str:
    v = str(value or ".").strip().replace("\\", "/")
    if v.startswith("/"):
        v = v[1:]
    while v.endswith("/") and v != ".":
        v = v[:-1]
    if not v:
        return "."
    return v


def _normalize_ssh_port(value, default: int = 22) -> int:
    try:
        p = int(value)
    except Exception:
        return int(default)
    if p <= 0 or p > 65535:
        return int(default)
    return p


def _normalize_terminal_key_file_name(value) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    p = Path(raw)
    if p.name != raw or raw in {".", ".."}:
        return ""
    return raw


def default_app_config() -> dict:
    return {
        "version": 1,
        "modules": {
            "qbt": True,
            "ddns": True,
            "shareclip": True,
            "http": True,
        },
        "qbt": {"monitor_enabled": True},
        "http_service": {"default_dir": "."},
        "terminal": {
            "enabled": True,
            "host": os.environ.get("TERMINAL_SSH_HOST", "127.0.0.1").strip() or "127.0.0.1",
            "port": _normalize_ssh_port(os.environ.get("TERMINAL_SSH_PORT", "22"), 22),
            "user": os.environ.get("TERMINAL_SSH_USER", "root").strip() or "root",
            "auth_mode": (
                os.environ.get("TERMINAL_AUTH_MODE", "key").strip().lower() or "key"
            ),
            "key_path": os.environ.get("TERMINAL_KEY_PATH", "").strip(),
            "key_file": _normalize_terminal_key_file_name(
                os.environ.get("TERMINAL_KEY_FILE", "").strip()
            ),
        },
    }


def normalize_app_config(raw) -> dict:
    base = default_app_config()
    if isinstance(raw, dict):
        mods = raw.get("modules")
        if isinstance(mods, dict):
            for k in ("qbt", "ddns", "shareclip", "http"):
                if k in mods:
                    base["modules"][k] = bool(mods.get(k))
            if "http" not in mods and "http_monitor" in mods:
                base["modules"]["http"] = bool(mods.get("http_monitor"))

        qbt = raw.get("qbt")
        if isinstance(qbt, dict) and "monitor_enabled" in qbt:
            base["qbt"]["monitor_enabled"] = bool(qbt.get("monitor_enabled"))

        http_service = raw.get("http_service")
        if isinstance(http_service, dict) and "default_dir" in http_service:
            base["http_service"]["default_dir"] = _normalize_rel_dir_setting(
                http_service.get("default_dir")
            )
        elif "http_default_dir" in raw:
            base["http_service"]["default_dir"] = _normalize_rel_dir_setting(
                raw.get("http_default_dir")
            )

        terminal = raw.get("terminal")
        if isinstance(terminal, dict):
            if "enabled" in terminal:
                base["terminal"]["enabled"] = bool(terminal.get("enabled"))
            if "host" in terminal:
                host = str(terminal.get("host", "") or "").strip()
                if host:
                    base["terminal"]["host"] = host
            if "port" in terminal:
                base["terminal"]["port"] = _normalize_ssh_port(
                    terminal.get("port"), base["terminal"]["port"]
                )
            if "user" in terminal:
                user = str(terminal.get("user", "") or "").strip()
                if user:
                    base["terminal"]["user"] = user
            if "auth_mode" in terminal:
                mode = str(terminal.get("auth_mode", "") or "").strip().lower()
                if mode in ("key", "password"):
                    base["terminal"]["auth_mode"] = mode
            if "key_path" in terminal:
                base["terminal"]["key_path"] = str(terminal.get("key_path", "") or "").strip()
            if "key_file" in terminal:
                base["terminal"]["key_file"] = _normalize_terminal_key_file_name(
                    terminal.get("key_file", "")
                )

    if base["terminal"]["auth_mode"] not in ("key", "password"):
        base["terminal"]["auth_mode"] = "key"
    base["terminal"]["port"] = _normalize_ssh_port(base["terminal"]["port"], 22)
    base["terminal"]["key_file"] = _normalize_terminal_key_file_name(
        base["terminal"].get("key_file", "")
    )
    base["http_service"]["default_dir"] = _normalize_rel_dir_setting(
        base["http_service"]["default_dir"]
    )
    base["version"] = 1
    return base


def load_app_config(root: Path | None = None) -> dict:
    p = app_config_path(root)
    if not p.exists():
        return default_app_config()
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default_app_config()
    return normalize_app_config(raw)


def save_app_config(cfg: dict, root: Path | None = None) -> dict:
    normalized = normalize_app_config(cfg)
    p = app_config_path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(normalized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return normalized
