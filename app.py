#!/usr/bin/env python3
from __future__ import annotations

import base64
import configparser
import http.cookiejar
import fcntl
import json
import ipaddress
import mimetypes
import os
import pwd
import pty
import re
import shlex
import shutil
import struct
import subprocess
import tarfile
import tempfile
import threading
import time
import termios
import urllib.error
import urllib.request
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlencode, urlparse

import ddns
from fcc import __version__ as FCC_APP_VERSION, __branch__ as FCC_APP_BRANCH
from fcc.modules.monitor.process_net import ProcessSourceSpeedSampler
from fcc.modules import REGISTRY as MODULE_REGISTRY
import fcc.http_access as http_access
import fcc.subtitle_uploads as subtitle_uploads
import fcc.subtitle_align as subtitle_align
from ddns.web import load_ddns_settings_page
from naming.clean_names import apply_rename_plan, build_rename_plan

# Backup feature temporarily disabled (v0.9.11): module intentionally not
# imported so its routes are never registered. Re-import to re-enable.

_CODE_DIR = Path(__file__).resolve().parent
_LEGACY_APP_ROOT_DIR = _CODE_DIR.parent
# 兼容旧版本：此前错误地把 app_root 指向了Parent目录（如 /opt）。
_APP_ROOT_DIR = _CODE_DIR if (_CODE_DIR / "web").is_dir() else _LEGACY_APP_ROOT_DIR
os.environ.setdefault(
    "SHARECLIP_STORAGE_ROOT",
    str(_APP_ROOT_DIR / "shareclip" / "storage"),
)

_shareclip_app = None
_shareclip_import_lock = threading.Lock()


def get_shareclip_app():
    """惰性加载 ShareClip（Flask），与同进程Control服务共用，无需单独监听 8888。"""
    global _shareclip_app
    if _shareclip_app is None:
        with _shareclip_import_lock:
            if _shareclip_app is None:
                import importlib.util

                spec = importlib.util.spec_from_file_location(
                    "shareclip_impl",
                    str(_APP_ROOT_DIR / "shareclip" / "app.py"),
                )
                mod = importlib.util.module_from_spec(spec)
                assert spec.loader is not None
                spec.loader.exec_module(mod)
                _shareclip_app = mod.app
    return _shareclip_app


DEFAULT_STORAGE_ROOT = Path(os.environ.get("STORAGE_ROOT", "/srv/Storage")).resolve()
DEFAULT_WEB_PORT = int(os.environ.get("WEB_PORT", "1288"))
ACTIVE_WEB_PORT = DEFAULT_WEB_PORT
DEFAULT_PUBLIC_SCHEME = os.environ.get("PUBLIC_SCHEME", "http").strip() or "http"
DEFAULT_PUBLIC_HOST = (
    os.environ.get("PUBLIC_HOST", f"127.0.0.1:{DEFAULT_WEB_PORT}").strip()
    or f"127.0.0.1:{DEFAULT_WEB_PORT}"
)
DEFAULT_QBT_SERVICE = os.environ.get("QBT_SERVICE", "").strip()
DEFAULT_QBT_API_URL = (
    os.environ.get("QBT_API_URL", "http://127.0.0.1:8080").strip()
    or "http://127.0.0.1:8080"
)
DEFAULT_QBT_API_USERNAME = os.environ.get("QBT_API_USERNAME", "").strip()
DEFAULT_QBT_API_PASSWORD = os.environ.get("QBT_API_PASSWORD", "").strip()
DEFAULT_QBT_DOCKER_CONTAINERS = tuple(
    x.strip()
    for x in os.environ.get(
        "QBT_DOCKER_CONTAINERS", "qbittorrent,qbittorrent-nox,qbt,qbt-nox"
    ).split(",")
    if x.strip()
)
DEFAULT_DDNS_SERVICE = os.environ.get("DDNS_SERVICE", "").strip()
APP_CONFIG_FILE_NAME = "app_config.json"
TERMINAL_KEYS_DIR_NAME = "terminal_keys"
TERMINAL_KEY_UPLOAD_MAX_BYTES = int(
    os.environ.get("TERMINAL_KEY_UPLOAD_MAX_BYTES", "1048576")
)
THEME_ASSETS_DIR_NAME = "theme-assets"
THEME_BG_UPLOAD_MAX_BYTES = int(
    os.environ.get("THEME_BG_UPLOAD_MAX_BYTES", str(12 * 1024 * 1024))
)
THEME_HERO_PRESETS = (
    "default",
    "aurora",
    "sunset",
    "frost",
    "afterclaw_clouds",
)
THEME_BG_ALLOWED_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".gif",
    ".avif",
}
SOURCE_POOL_KEYS = ("baidu", "guangya", "aliyun")
SOURCE_POOL_LABELS = {
    "baidu": "Baidu Netdisk",
    "guangya": "Guangya Netdisk",
    "aliyun": "Aliyun Drive",
}
SOURCE_POOL_KEY_ALIASES = {
    "baidu": "baidu",
    "百度": "baidu",
    "Baidu Netdisk": "baidu",
    "xpan": "baidu",
    "pan.baidu": "baidu",
    "netdisk": "baidu",
    "guangya": "guangya",
    "光鸭": "guangya",
    "Guangya Netdisk": "guangya",
    "aliyun": "aliyun",
    "alipan": "aliyun",
    "阿里": "aliyun",
    "阿里云": "aliyun",
    "Aliyun Drive": "aliyun",
}
DEFAULT_SOURCE_IP_POOL_SOURCE = (
    os.environ.get("SOURCE_IP_POOL_SOURCE", "").strip()
    or "github:EinProfispieler/afterclaw/data/vendor-ip-pools"
)
SOURCE_POOL_REMOTE_MAX_FILES = 200
SOURCE_POOL_REMOTE_TIMEOUT = float(
    os.environ.get("SOURCE_POOL_REMOTE_TIMEOUT", "12").strip() or "12"
)
DEFAULT_UPGRADE_GITHUB_REPO = (
    os.environ.get("UPGRADE_GITHUB_REPO", "").strip() or "EinProfispieler/afterclaw"
)
DEFAULT_UPGRADE_BRANCH = (
    os.environ.get("UPGRADE_BRANCH", "").strip().lower() or "main"
)
DEFAULT_NIGHTLY_LOCAL_ROOT = (
    os.environ.get("UPGRADE_NIGHTLY_LOCAL_ROOT", "").strip() or "/opt/afterclaw-nightly"
)
UPGRADE_HTTP_TIMEOUT = float(
    os.environ.get("UPGRADE_HTTP_TIMEOUT", "20").strip() or "20"
)
UPGRADE_STATUS_FILE_NAME = "upgrade_status.json"
UPGRADE_STATUS_LOCK = threading.Lock()
APP_VERSION = str(FCC_APP_VERSION or "").strip() or "unknown"
APP_VERSION_TEXT = (
    f"v{APP_VERSION}"
    if APP_VERSION and APP_VERSION.lower() != "unknown"
    else str(APP_VERSION or "unknown")
)
_raw_app_branch = str(FCC_APP_BRANCH or "").strip().lower()
if _raw_app_branch in {"main", "stable"}:
    APP_BRANCH = "main"
elif _raw_app_branch == "nightly":
    APP_BRANCH = "nightly"
elif ".dev" in APP_VERSION:
    APP_BRANCH = "nightly"
else:
    APP_BRANCH = "main"
DEFAULT_TRANSFER_RECENT_TTL_SEC = float(
    os.environ.get("TRANSFER_RECENT_TTL_SEC", "15").strip() or "15"
)
DEFAULT_SUBTITLE_OWNER_UID = int(os.environ.get("SUBTITLE_OWNER_UID", "501"))
DEFAULT_SUBTITLE_OWNER_GID = int(os.environ.get("SUBTITLE_OWNER_GID", "20"))
DEFAULT_SUBTITLE_FILE_MODE = os.environ.get("SUBTITLE_FILE_MODE", "664").strip() or "664"
DEFAULT_SUBTITLE_DIR_MODE = os.environ.get("SUBTITLE_DIR_MODE", "2775").strip() or "2775"


def _normalize_subtitle_mode(value, default: str) -> str:
    raw = str(value if value is not None else default).strip().lower()
    if raw.startswith("0o"):
        raw = raw[2:]
    if not raw:
        raw = str(default).strip().lower() or "664"
    if not re.fullmatch(r"[0-7]{3,4}", raw):
        raw = str(default).strip().lower() or "664"
    return raw


def _normalize_subtitle_uid_gid(value, default: int) -> int:
    try:
        v = int(str(value).strip())
        return v if v >= 0 else int(default)
    except Exception:
        return int(default)


def _page_title_with_version(title: str) -> str:
    base = str(title or "").strip() or "AfterClaw"
    return base


def _inject_page_title(html: str, title: str) -> str:
    src = f"<title>{title}</title>"
    dst = f"<title>{_page_title_with_version(title)}</title>"
    if src in html:
        return html.replace(src, dst, 1)
    return re.sub(r"<title>.*?</title>", dst, html, count=1, flags=re.IGNORECASE | re.DOTALL)


def _migrate_legacy_state_once():
    # 仅当当前根目录与旧错误根目录不同才迁移。
    if _APP_ROOT_DIR == _LEGACY_APP_ROOT_DIR:
        return
    try:
        old_cfg = _LEGACY_APP_ROOT_DIR / APP_CONFIG_FILE_NAME
        new_cfg = _APP_ROOT_DIR / APP_CONFIG_FILE_NAME
        if old_cfg.exists() and old_cfg.is_file():
            should_copy = (not new_cfg.exists()) or (
                old_cfg.stat().st_mtime > new_cfg.stat().st_mtime
            )
            if should_copy:
                new_cfg.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(old_cfg, new_cfg)
    except Exception:
        pass
    try:
        old_keys = _LEGACY_APP_ROOT_DIR / TERMINAL_KEYS_DIR_NAME
        new_keys = _APP_ROOT_DIR / TERMINAL_KEYS_DIR_NAME
        if old_keys.exists() and old_keys.is_dir():
            new_keys.mkdir(parents=True, exist_ok=True)
            for src in old_keys.iterdir():
                try:
                    if not src.is_file() or src.name.startswith("."):
                        continue
                    dst = new_keys / src.name
                    if not dst.exists():
                        shutil.copy2(src, dst)
                    os.chmod(str(dst), 0o600)
                except Exception:
                    continue
    except Exception:
        pass


def app_config_path(app_root: Path = _APP_ROOT_DIR) -> Path:
    return Path(app_root) / APP_CONFIG_FILE_NAME


def terminal_keys_dir(app_root: Path = _APP_ROOT_DIR) -> Path:
    return Path(app_root) / TERMINAL_KEYS_DIR_NAME


def theme_assets_dir(app_root: Path = _APP_ROOT_DIR) -> Path:
    return Path(app_root) / "web" / THEME_ASSETS_DIR_NAME


def upgrade_status_path(app_root: Path = _APP_ROOT_DIR) -> Path:
    return Path(app_root) / UPGRADE_STATUS_FILE_NAME


def _utc_now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _normalize_upgrade_repo(value, default: str = DEFAULT_UPGRADE_GITHUB_REPO) -> str:
    raw = str(value or default).strip().strip("/")
    if not raw:
        raw = str(default or "").strip().strip("/")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", raw):
        raise ValueError("仓库格式无效（应为 owner/repo）")
    return raw


def _normalize_upgrade_tag(value) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    if len(raw) > 80:
        raise ValueError("Tag 过长")
    if not re.fullmatch(r"[A-Za-z0-9._-]+", raw):
        raise ValueError("Tag 格式无效")
    return raw


def _normalize_upgrade_branch(value, default: str = DEFAULT_UPGRADE_BRANCH) -> str:
    raw = str(value or default).strip().lower()
    if raw in {"stable", "main"}:
        return "main"
    if raw == "nightly":
        return "nightly"
    if str(default).strip().lower() in {"stable", "main"}:
        return "main"
    if str(default).strip().lower() == "nightly":
        return "nightly"
    return "main"


def _to_version_text(value) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    if raw.lower().startswith("v"):
        return raw
    return f"v{raw}"


def _default_upgrade_status() -> dict:
    return {
        "supported": bool(os.name == "posix"),
        "running": False,
        "state": "idle",
        "current_version": APP_VERSION_TEXT,
        "repo": DEFAULT_UPGRADE_GITHUB_REPO,
        "branch": _normalize_upgrade_branch(DEFAULT_UPGRADE_BRANCH, "main"),
        "requested_tag": "",
        "target_tag": "",
        "release_url": "",
        "message": "",
        "error": "",
        "started_at": "",
        "finished_at": "",
        "updated_at": _utc_now_iso(),
    }


def _read_upgrade_status(app_root: Path = _APP_ROOT_DIR) -> dict:
    base = _default_upgrade_status()
    path = upgrade_status_path(app_root)
    if not path.exists() or not path.is_file():
        return base
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return base
    if not isinstance(raw, dict):
        return base
    for key, val in raw.items():
        base[key] = val
    try:
        base["repo"] = _normalize_upgrade_repo(base.get("repo"), DEFAULT_UPGRADE_GITHUB_REPO)
    except Exception:
        base["repo"] = DEFAULT_UPGRADE_GITHUB_REPO
    base["branch"] = _normalize_upgrade_branch(base.get("branch"), DEFAULT_UPGRADE_BRANCH)
    base["requested_tag"] = str(base.get("requested_tag", "") or "").strip()
    base["target_tag"] = str(base.get("target_tag", "") or "").strip()
    base["running"] = bool(base.get("running"))
    base["state"] = str(base.get("state", "idle") or "idle").strip() or "idle"
    return base


def _write_upgrade_status(status: dict, app_root: Path = _APP_ROOT_DIR) -> dict:
    base = _default_upgrade_status()
    if isinstance(status, dict):
        base.update(status)
    try:
        base["repo"] = _normalize_upgrade_repo(base.get("repo"), DEFAULT_UPGRADE_GITHUB_REPO)
    except Exception:
        base["repo"] = DEFAULT_UPGRADE_GITHUB_REPO
    base["branch"] = _normalize_upgrade_branch(base.get("branch"), DEFAULT_UPGRADE_BRANCH)
    base["requested_tag"] = str(base.get("requested_tag", "") or "").strip()
    base["target_tag"] = str(base.get("target_tag", "") or "").strip()
    base["running"] = bool(base.get("running"))
    base["state"] = str(base.get("state", "idle") or "idle").strip() or "idle"
    base["updated_at"] = _utc_now_iso()
    path = upgrade_status_path(app_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with UPGRADE_STATUS_LOCK:
        tmp.write_text(
            json.dumps(base, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        tmp.replace(path)
    return base


def _normalize_terminal_key_file_name(value) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    p = Path(raw)
    # 仅允许配置目录下单文件名，避免路径穿越。
    if p.name != raw or raw in {".", ".."}:
        return ""
    return raw


def _list_terminal_key_files(app_root: Path = _APP_ROOT_DIR) -> list[str]:
    d = terminal_keys_dir(app_root)
    if not d.exists() or not d.is_dir():
        return []
    names = []
    for e in d.iterdir():
        try:
            if not e.is_file():
                continue
        except Exception:
            continue
        if e.name.startswith("."):
            continue
        names.append(e.name)
    names.sort()
    return names


def _save_terminal_key_file(file_name, content_b64, app_root: Path = _APP_ROOT_DIR):
    name = _normalize_terminal_key_file_name(file_name)
    if not name:
        raise ValueError("key 文件名不合法（仅支持单文件名）")
    raw_b64 = str(content_b64 or "").strip()
    if not raw_b64:
        raise ValueError("key 文件内容为空")
    try:
        payload = base64.b64decode(raw_b64.encode("ascii"), validate=True)
    except Exception:
        raise ValueError("key 文件内容不是合法 Base64")
    if not payload:
        raise ValueError("key 文件内容为空")
    if len(payload) > TERMINAL_KEY_UPLOAD_MAX_BYTES:
        raise ValueError(
            f"key 文件过大（最大 {TERMINAL_KEY_UPLOAD_MAX_BYTES} bytes）"
        )
    key_dir = terminal_keys_dir(app_root)
    key_dir.mkdir(parents=True, exist_ok=True)
    key_dir = key_dir.resolve()
    target = ensure_under_root(key_dir, key_dir / name)
    with open(target, "wb") as f:
        f.write(payload)
    try:
        os.chmod(str(target), 0o600)
    except Exception:
        pass
    return name, len(payload)


def _normalize_theme_bg_file_name(value) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    p = Path(raw)
    if p.name != raw or raw in {".", ".."}:
        return ""
    ext = p.suffix.lower()
    if ext not in THEME_BG_ALLOWED_EXTENSIONS:
        return ""
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", p.name)
    if safe in {"", ".", ".."}:
        return ""
    return safe


def _normalize_ui_hero_preset(value) -> str:
    raw = str(value or "default").strip().lower()
    if raw in THEME_HERO_PRESETS:
        return raw
    return "default"


def _save_theme_bg_file(file_name, content_b64, app_root: Path = _APP_ROOT_DIR):
    name = _normalize_theme_bg_file_name(file_name)
    if not name:
        raise ValueError("背景图片文件名不合法（支持 png/jpg/jpeg/webp/gif/avif）")
    raw_b64 = str(content_b64 or "").strip()
    if not raw_b64:
        raise ValueError("背景图片内容为空")
    try:
        payload = base64.b64decode(raw_b64.encode("ascii"), validate=True)
    except Exception:
        raise ValueError("背景图片内容不是合法 Base64")
    if not payload:
        raise ValueError("背景图片内容为空")
    if len(payload) > THEME_BG_UPLOAD_MAX_BYTES:
        raise ValueError(
            f"背景图片过大（最大 {THEME_BG_UPLOAD_MAX_BYTES} bytes）"
        )
    assets_dir = theme_assets_dir(app_root)
    assets_dir.mkdir(parents=True, exist_ok=True)
    assets_dir = assets_dir.resolve()
    target = ensure_under_root(assets_dir, assets_dir / name)
    with open(target, "wb") as f:
        f.write(payload)
    return name, len(payload)


def _ui_theme_payload(cfg: dict | None, app_root: Path = _APP_ROOT_DIR) -> dict:
    ui = (cfg or {}).get("ui") if isinstance(cfg, dict) else {}
    if not isinstance(ui, dict):
        ui = {}
    preset = _normalize_ui_hero_preset(ui.get("hero_preset", "default"))
    custom_file = ""
    custom_url = ""
    return {
        "hero_preset": preset,
        "hero_custom_bg_file": custom_file,
        "hero_custom_bg_url": custom_url,
        "hero_presets": list(THEME_HERO_PRESETS),
    }


def _normalize_rel_dir_setting(value) -> str:
    v = str(value or ".").strip().replace("\\", "/")
    if v.startswith("/"):
        v = v[1:]
    while v.endswith("/") and v != ".":
        v = v[:-1]
    if not v:
        return "."
    return v


def _normalize_abs_dir_setting(value, fallback: str = "/") -> str:
    raw = str(value or "").strip().replace("\\", "/")
    if not raw:
        raw = str(fallback or "/")
    raw = os.path.expanduser(raw)
    p = Path(raw)
    if not p.is_absolute():
        p = Path("/") / raw.lstrip("/")
    try:
        p = p.resolve()
    except Exception:
        p = p.absolute()
    return str(p)


def _normalize_source_pool_key(value) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    lower = raw.lower()
    if lower in SOURCE_POOL_KEY_ALIASES:
        return SOURCE_POOL_KEY_ALIASES[lower]
    if raw in SOURCE_POOL_KEY_ALIASES:
        return SOURCE_POOL_KEY_ALIASES[raw]
    key = lower.replace("_", "").replace("-", "").replace(" ", "")
    if key in SOURCE_POOL_KEY_ALIASES:
        return SOURCE_POOL_KEY_ALIASES[key]
    return ""


def _iter_ip_pool_tokens(value):
    if isinstance(value, (list, tuple, set)):
        for item in value:
            yield from _iter_ip_pool_tokens(item)
        return
    text = str(value or "").strip()
    if not text:
        return
    normalized = (
        text.replace("，", ",")
        .replace("；", ";")
        .replace("\n", " ")
        .replace("\t", " ")
        .replace("|", " ")
    )
    for token in re.split(r"[,\s;]+", normalized):
        t = token.strip()
        if t:
            yield t


def _normalize_ip_pool_token(token) -> str:
    text = str(token or "").strip()
    if not text:
        return ""
    if text.startswith("[") and text.endswith("]"):
        text = text[1:-1].strip()
    if text.startswith("http://") or text.startswith("https://"):
        try:
            parsed = urlparse(text)
            text = (parsed.hostname or "").strip()
        except Exception:
            text = ""
    if not text:
        return ""
    if text.count(":") == 1 and "." in text and "/" not in text:
        host, port = text.split(":", 1)
        if port.isdigit():
            text = host.strip()
    if "%" in text and ":" in text:
        text = text.split("%", 1)[0].strip()
    try:
        if "/" in text:
            net = ipaddress.ip_network(text, strict=False)
            host_prefix = 32 if net.version == 4 else 128
            if net.prefixlen == host_prefix:
                return str(net.network_address)
            return str(net)
        ip_obj = ipaddress.ip_address(text)
        return str(ip_obj)
    except ValueError:
        return ""


def _default_source_ip_pools() -> dict:
    return {k: [] for k in SOURCE_POOL_KEYS}


def _default_source_ip_pool_source() -> str:
    return DEFAULT_SOURCE_IP_POOL_SOURCE


def _normalize_source_ip_pool_source(raw) -> str:
    text = str(raw or "").strip()
    if len(text) > 500:
        text = text[:500].strip()
    return text or _default_source_ip_pool_source()


def _normalize_source_ip_pools(raw) -> dict:
    pools = _default_source_ip_pools()
    if not isinstance(raw, dict):
        return pools
    for key, value in raw.items():
        pool_key = _normalize_source_pool_key(key)
        if not pool_key:
            continue
        rows = []
        seen = set()
        for token in _iter_ip_pool_tokens(value):
            norm = _normalize_ip_pool_token(token)
            if not norm or norm in seen:
                continue
            seen.add(norm)
            rows.append(norm)
        pools[pool_key] = rows
    return pools


def _merge_source_ip_pools(base_raw, incoming_raw) -> dict:
    base = _normalize_source_ip_pools(base_raw)
    incoming = _normalize_source_ip_pools(incoming_raw)
    merged = _default_source_ip_pools()
    for key in SOURCE_POOL_KEYS:
        rows = []
        seen = set()
        for token in list(base.get(key, [])) + list(incoming.get(key, [])):
            norm = _normalize_ip_pool_token(token)
            if not norm or norm in seen:
                continue
            seen.add(norm)
            rows.append(norm)
        merged[key] = rows
    return merged


def _guess_source_pool_key_from_hint(hint: str, fallback: str = "") -> str:
    raw = str(hint or "").strip()
    if not raw:
        return _normalize_source_pool_key(fallback)
    candidates = [raw]
    try:
        p = Path(raw)
        candidates.extend([p.name, p.stem, p.parent.name])
    except Exception:
        pass
    for base in list(candidates):
        for part in re.split(r"[/\\._\-\s]+", str(base or "")):
            token = part.strip()
            if token:
                candidates.append(token)
    for item in candidates:
        key = _normalize_source_pool_key(item)
        if key:
            return key
    return _normalize_source_pool_key(fallback)


def _append_source_pool_token(pools: dict, pool_key: str, token: str) -> int:
    key = _normalize_source_pool_key(pool_key)
    if not key:
        return 0
    norm = _normalize_ip_pool_token(token)
    if not norm:
        return 0
    rows = pools.setdefault(key, [])
    if norm in rows:
        return 0
    rows.append(norm)
    return 1


def _apply_source_pool_payload(pools: dict, payload, default_key: str = "") -> int:
    total_added = 0
    default_pool_key = _normalize_source_pool_key(default_key)
    if payload is None:
        return 0
    if isinstance(payload, dict):
        for key, value in payload.items():
            hinted = _guess_source_pool_key_from_hint(str(key), default_pool_key)
            total_added += _apply_source_pool_payload(pools, value, hinted)
        return total_added
    if isinstance(payload, (list, tuple, set)):
        for item in payload:
            total_added += _apply_source_pool_payload(pools, item, default_pool_key)
        return total_added

    text = str(payload or "").strip()
    if not text:
        return 0
    if text.startswith("{") or text.startswith("["):
        try:
            parsed = json.loads(text)
            return _apply_source_pool_payload(pools, parsed, default_pool_key)
        except Exception:
            pass

    for raw_line in text.splitlines():
        line = str(raw_line or "").strip()
        if not line:
            continue
        if line.startswith("#") or line.startswith("//"):
            continue
        alias_key = ""
        alias_payload = ""
        if ":" in line and not line.lower().startswith(("http://", "https://")):
            left, right = line.split(":", 1)
            alias_key = _normalize_source_pool_key(left)
            alias_payload = right.strip()
        if alias_key and alias_payload:
            total_added += _apply_source_pool_payload(pools, alias_payload, alias_key)
            continue
        if default_pool_key:
            for token in _iter_ip_pool_tokens(line):
                total_added += _append_source_pool_token(
                    pools, default_pool_key, token
                )
    return total_added


def _http_fetch_json(
    url: str,
    timeout: float = SOURCE_POOL_REMOTE_TIMEOUT,
    headers: dict | None = None,
):
    req_headers = {
        "Accept": "application/json",
        "User-Agent": "afterclaw-ip-sync/1.0",
    }
    if isinstance(headers, dict):
        for key, value in headers.items():
            if not key:
                continue
            req_headers[str(key)] = str(value)
    req = urllib.request.Request(str(url or "").strip(), headers=req_headers)
    with urllib.request.urlopen(req, timeout=max(float(timeout), 3.0)) as resp:
        raw = resp.read() or b"{}"
    return json.loads(raw.decode("utf-8", errors="replace"))


def _http_fetch_text(
    url: str,
    timeout: float = SOURCE_POOL_REMOTE_TIMEOUT,
    headers: dict | None = None,
) -> str:
    req_headers = {"User-Agent": "afterclaw-ip-sync/1.0"}
    if isinstance(headers, dict):
        for key, value in headers.items():
            if not key:
                continue
            req_headers[str(key)] = str(value)
    req = urllib.request.Request(str(url or "").strip(), headers=req_headers)
    with urllib.request.urlopen(req, timeout=max(float(timeout), 3.0)) as resp:
        raw = resp.read() or b""
    return raw.decode("utf-8", errors="replace")


def _http_download_file(
    url: str,
    target: Path,
    timeout: float = UPGRADE_HTTP_TIMEOUT,
    headers: dict | None = None,
) -> int:
    req_headers = {"User-Agent": "afterclaw-updater/1.0"}
    if isinstance(headers, dict):
        for key, value in headers.items():
            if not key:
                continue
            req_headers[str(key)] = str(value)
    req = urllib.request.Request(str(url or "").strip(), headers=req_headers)
    total = 0
    target.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(req, timeout=max(float(timeout), 3.0)) as resp:
        with open(target, "wb") as f:
            while True:
                chunk = resp.read(1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)
                total += len(chunk)
    return int(total)


def _github_release_payload(repo: str, tag: str = "") -> dict:
    safe_repo = _normalize_upgrade_repo(repo, DEFAULT_UPGRADE_GITHUB_REPO)
    safe_tag = _normalize_upgrade_tag(tag)
    owner, name = safe_repo.split("/", 1)
    if safe_tag:
        api_url = (
            f"https://api.github.com/repos/{quote(owner)}/{quote(name)}"
            f"/releases/tags/{quote(safe_tag)}"
        )
    else:
        api_url = (
            f"https://api.github.com/repos/{quote(owner)}/{quote(name)}"
            "/releases/latest"
        )
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "afterclaw-updater/1.0"}
    try:
        data = _http_fetch_json(api_url, timeout=UPGRADE_HTTP_TIMEOUT, headers=headers)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            if safe_tag:
                raise ValueError(f"未找到发布版本：{safe_tag}") from exc
            raise ValueError("仓库暂无可用 Release") from exc
        raise RuntimeError(f"GitHub API 错误（HTTP {exc.code}）") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Connect GitHub failed: {exc}") from exc
    except Exception as exc:
        raise RuntimeError(f"读取 GitHub Release failed: {exc}") from exc
    if not isinstance(data, dict):
        raise RuntimeError("GitHub Release 返回格式异常")
    return data


def _github_branch_payload(repo: str, branch: str = "main") -> dict:
    safe_repo = _normalize_upgrade_repo(repo, DEFAULT_UPGRADE_GITHUB_REPO)
    safe_branch = _normalize_upgrade_branch(branch, "main")
    owner, name = safe_repo.split("/", 1)
    tarball_url = (
        f"https://api.github.com/repos/{quote(owner)}/{quote(name)}"
        f"/tarball/{quote(safe_branch)}"
    )
    html_url = (
        f"https://github.com/{quote(owner)}/{quote(name)}/tree/{quote(safe_branch)}"
    )
    return {
        "tag_name": f"{safe_branch}-branch",
        "tarball_url": tarball_url,
        "html_url": html_url,
    }


def _github_branch_version_payload(repo: str, branch: str = "nightly") -> dict:
    safe_repo = _normalize_upgrade_repo(repo, DEFAULT_UPGRADE_GITHUB_REPO)
    safe_branch = _normalize_upgrade_branch(branch, "nightly")
    owner, name = safe_repo.split("/", 1)
    raw_url = (
        f"https://raw.githubusercontent.com/{quote(owner)}/{quote(name)}"
        f"/{quote(safe_branch)}/fcc/__init__.py"
    )
    tree_url = (
        f"https://github.com/{quote(owner)}/{quote(name)}"
        f"/tree/{quote(safe_branch)}"
    )
    try:
        text = _http_fetch_text(
            raw_url,
            timeout=max(float(UPGRADE_HTTP_TIMEOUT), 30.0),
            headers={"User-Agent": "afterclaw-updater/1.0"},
        )
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"读取 {safe_branch} 分支版本失败（HTTP {exc.code}）") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"连接 GitHub 失败: {exc}") from exc
    except Exception as exc:
        raise RuntimeError(f"读取 {safe_branch} 分支版本失败: {exc}") from exc
    match = re.search(r'__version__\s*=\s*"([^"]+)"', str(text or ""))
    version_raw = str(match.group(1) if match else "").strip()
    if not version_raw:
        raise RuntimeError(f"未在 {safe_branch} 分支解析到 __version__")
    return {
        "branch": safe_branch,
        "version_raw": version_raw,
        "version_text": _to_version_text(version_raw),
        "html_url": tree_url,
        "raw_url": raw_url,
    }


def _local_branch_version_payload(repo: str, branch: str = "nightly") -> dict:
    safe_repo = _normalize_upgrade_repo(repo, DEFAULT_UPGRADE_GITHUB_REPO)
    safe_branch = _normalize_upgrade_branch(branch, "nightly")
    if safe_branch != "nightly":
        raise RuntimeError("本地版本读取仅支持 nightly 分支")
    owner, name = safe_repo.split("/", 1)
    tree_url = (
        f"https://github.com/{quote(owner)}/{quote(name)}"
        f"/tree/{quote(safe_branch)}"
    )
    local_root = Path(DEFAULT_NIGHTLY_LOCAL_ROOT).expanduser()
    init_file = local_root / "fcc" / "__init__.py"
    if not init_file.exists() or not init_file.is_file():
        raise RuntimeError(f"本地 nightly 版本文件不存在：{init_file}")
    try:
        text = init_file.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        raise RuntimeError(f"读取本地 nightly 版本文件失败：{exc}") from exc
    match = re.search(r'__version__\s*=\s*"([^"]+)"', str(text or ""))
    version_raw = str(match.group(1) if match else "").strip()
    if not version_raw:
        raise RuntimeError(f"未在本地 nightly 文件解析到 __version__：{init_file}")
    return {
        "branch": safe_branch,
        "version_raw": version_raw,
        "version_text": _to_version_text(version_raw),
        "html_url": tree_url,
        "raw_url": str(init_file),
    }


def _parse_github_source_spec(source: str) -> dict:
    raw = str(source or "").strip()
    if not raw.lower().startswith("github:"):
        raise ValueError("GitHub 源格式应为 github:owner/repo/path")
    spec = raw.split(":", 1)[1].strip().strip("/")
    if not spec:
        raise ValueError("GitHub 源不能为空")
    parts = [p for p in spec.split("/") if p]
    if len(parts) < 3:
        raise ValueError("GitHub 源至少需要 owner/repo/path")
    owner = parts[0].strip()
    repo_part = parts[1].strip()
    if not owner or not repo_part:
        raise ValueError("GitHub 源中的 owner/repo 无效")
    repo = repo_part
    ref = ""
    if "@" in repo_part:
        repo, ref = repo_part.split("@", 1)
        repo = repo.strip()
        ref = ref.strip()
    path = "/".join(parts[2:]).strip("/")
    if not repo or not path:
        raise ValueError("GitHub 源中的仓库名或路径无效")
    return {
        "owner": owner,
        "repo": repo,
        "path": path,
        "ref": ref,
        "display": f"github:{owner}/{repo}{('@' + ref) if ref else ''}/{path}",
    }


def _fetch_source_ip_pools_from_github_spec(source: str) -> dict:
    parsed = _parse_github_source_spec(source)
    owner = parsed["owner"]
    repo = parsed["repo"]
    root_path = parsed["path"]
    ref = parsed["ref"]
    pools = _default_source_ip_pools()
    files_used = []
    queue = [root_path]
    seen_dirs = set()

    while queue and len(files_used) < SOURCE_POOL_REMOTE_MAX_FILES:
        rel_path = str(queue.pop(0) or "").strip("/")
        if not rel_path:
            continue
        if rel_path in seen_dirs:
            continue
        seen_dirs.add(rel_path)
        api_url = (
            f"https://api.github.com/repos/{quote(owner)}/{quote(repo)}"
            f"/contents/{quote(rel_path, safe='/')}"
        )
        if ref:
            api_url += "?ref=" + quote(ref, safe="")
        try:
            payload = _http_fetch_json(api_url)
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                raise ValueError(f"GitHub 路径不存在：{rel_path}") from exc
            raise RuntimeError(f"GitHub API 错误（HTTP {exc.code}）") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"GitHub Connect失败：{exc}") from exc
        except Exception as exc:
            raise RuntimeError(f"读取 GitHub 目录失败：{exc}") from exc

        entries = payload if isinstance(payload, list) else [payload]
        for entry in entries:
            if len(files_used) >= SOURCE_POOL_REMOTE_MAX_FILES:
                break
            if not isinstance(entry, dict):
                continue
            item_type = str(entry.get("type", "") or "").strip().lower()
            item_path = str(entry.get("path", "") or "").strip()
            if not item_path:
                continue
            if item_type == "dir":
                queue.append(item_path)
                continue
            if item_type != "file":
                continue
            pool_key = _guess_source_pool_key_from_hint(item_path, "")
            if not pool_key:
                continue
            text_payload = ""
            content_b64 = str(entry.get("content", "") or "")
            encoding = str(entry.get("encoding", "") or "").strip().lower()
            if content_b64 and encoding == "base64":
                try:
                    text_payload = base64.b64decode(content_b64).decode(
                        "utf-8", errors="replace"
                    )
                except Exception:
                    text_payload = ""
            if not text_payload:
                download_url = str(entry.get("download_url", "") or "").strip()
                if download_url:
                    try:
                        text_payload = _http_fetch_text(download_url)
                    except Exception:
                        text_payload = ""
            if not text_payload:
                continue
            added = _apply_source_pool_payload(pools, text_payload, pool_key)
            if added > 0:
                files_used.append(item_path)

    normalized = _normalize_source_ip_pools(pools)
    if not any(normalized.get(k) for k in SOURCE_POOL_KEYS):
        raise ValueError("GitHub 源中未发现可识别的Source IP 文件（需包含 baidu/guangya/aliyun 命名）")
    return {
        "source": parsed["display"],
        "pools": normalized,
        "files_used": files_used,
        "meta": {"type": "github", "root": root_path, "ref": ref or ""},
    }


def _fetch_source_ip_pools_from_url(source: str) -> dict:
    url = str(source or "").strip()
    if not url.startswith(("http://", "https://")):
        raise ValueError("URL 源仅支持 http:// 或 https://")
    pools = _default_source_ip_pools()
    payload_text = _http_fetch_text(url)
    added = _apply_source_pool_payload(pools, payload_text, "")
    if added <= 0:
        try:
            payload_json = json.loads(payload_text)
        except Exception:
            payload_json = None
        if payload_json is not None:
            _apply_source_pool_payload(pools, payload_json, "")
    normalized = _normalize_source_ip_pools(pools)
    if not any(normalized.get(k) for k in SOURCE_POOL_KEYS):
        raise ValueError("源文件中未解析到任何可用 IP/CIDR")
    return {
        "source": url,
        "pools": normalized,
        "files_used": [url],
        "meta": {"type": "url"},
    }


def _fetch_source_ip_pools_from_source(source: str) -> dict:
    raw = _normalize_source_ip_pool_source(source)
    if raw.lower().startswith("github:"):
        return _fetch_source_ip_pools_from_github_spec(raw)
    if raw.startswith(("http://", "https://")):
        return _fetch_source_ip_pools_from_url(raw)
    raise ValueError("仅支持 github:owner/repo/path 或 http(s) URL")


def _match_source_label_by_ip(client_ip: str, source_ip_pools: dict | None) -> str:
    text = str(client_ip or "").strip()
    if not text:
        return ""
    try:
        ip_obj = ipaddress.ip_address(text)
    except ValueError:
        return ""
    pools = _normalize_source_ip_pools(source_ip_pools)
    for key in SOURCE_POOL_KEYS:
        label = SOURCE_POOL_LABELS.get(key, "")
        if not label:
            continue
        for entry in pools.get(key, []):
            try:
                if "/" in entry:
                    net = ipaddress.ip_network(entry, strict=False)
                else:
                    host_prefix = "32" if ip_obj.version == 4 else "128"
                    net = ipaddress.ip_network(f"{entry}/{host_prefix}", strict=False)
            except ValueError:
                continue
            if ip_obj in net:
                return label
    return ""


def _normalize_ssh_port(value, default: int = 22) -> int:
    try:
        p = int(value)
    except Exception:
        return int(default)
    if p <= 0 or p > 65535:
        return int(default)
    return p


def _normalize_web_port(value, default: int = DEFAULT_WEB_PORT) -> int:
    try:
        p = int(value)
    except Exception:
        return int(default)
    if p <= 0 or p > 65535:
        return int(default)
    return p


def _normalize_transfer_recent_ttl(value, default: float = DEFAULT_TRANSFER_RECENT_TTL_SEC) -> float:
    try:
        sec = float(value)
    except Exception:
        sec = float(default)
    if sec != sec or sec in (float("inf"), float("-inf")):
        sec = float(default)
    sec = max(0.0, min(sec, 600.0))
    return round(sec, 1)


def _build_terminal_launch_meta(cfg: dict) -> dict:
    term = ((cfg or {}).get("terminal") or {}) if isinstance(cfg, dict) else {}
    enabled = bool(term.get("enabled", True))
    host = str(term.get("host", "") or "").strip()
    user = str(term.get("user", "root") or "").strip() or "root"
    port = _normalize_ssh_port(term.get("port", 22), 22)
    auth_mode = str(term.get("auth_mode", "key") or "key").strip().lower()
    if auth_mode not in ("key", "password"):
        auth_mode = "key"
    key_path = str(term.get("key_path", "") or "").strip()
    key_file = _normalize_terminal_key_file_name(term.get("key_file", ""))
    key_dir = terminal_keys_dir(_APP_ROOT_DIR)
    key_from_config_dir = str((key_dir / key_file)) if key_file else ""
    key_effective = key_from_config_dir or key_path
    display = ""
    link = ""
    command = ""
    if host:
        display = f"{user}@{host}:{port}"
        link = f"ssh://{quote(user, safe='')}@{host}:{port}"
        base_cmd = f"ssh -p {port} {shlex.quote(user + '@' + host)}"
        if auth_mode == "key" and key_effective:
            command = f"ssh -i {shlex.quote(key_effective)} -p {port} {shlex.quote(user + '@' + host)}"
        else:
            command = base_cmd
    tip = (
        "密码模式不会Save密码，点击后在终端内手工输入。"
        if auth_mode == "password"
        else (
            "推荐使用私钥模式；确保目标机器已授权该公钥。"
            if not key_file
            else f"已启用配置目录 key：{key_file}（目录 {key_dir}）"
        )
    )
    return {
        "enabled": enabled,
        "host": host,
        "user": user,
        "port": port,
        "auth_mode": auth_mode,
        "key_path": key_path,
        "key_file": key_file,
        "key_dir": str(key_dir),
        "key_files": _list_terminal_key_files(_APP_ROOT_DIR),
        "key_effective": key_effective,
        "display": display,
        "link": link,
        "command": command,
        "tip": tip,
    }


def _build_terminal_ssh_argv(cfg: dict) -> tuple[list[str], dict]:
    meta = _build_terminal_launch_meta(cfg)
    if not meta.get("enabled", True):
        raise ValueError("Terminal 模块未启用")
    host = str(meta.get("host", "") or "").strip()
    user = str(meta.get("user", "root") or "").strip() or "root"
    port = _normalize_ssh_port(meta.get("port", 22), 22)
    if not host:
        raise ValueError("Not configured Terminal Host")
    argv = ["ssh", "-p", str(port)]
    auth_mode = str(meta.get("auth_mode", "key") or "key").strip().lower()
    key_file = _normalize_terminal_key_file_name(meta.get("key_file", ""))
    key_path = str(meta.get("key_path", "") or "").strip()
    if auth_mode == "key":
        key_target: Path | None = None
        if key_file:
            key_dir = terminal_keys_dir(_APP_ROOT_DIR)
            key_dir.mkdir(parents=True, exist_ok=True)
            key_target = ensure_under_root(key_dir, key_dir / key_file)
        elif key_path:
            key_target = Path(os.path.expanduser(key_path))
        if key_target is None:
            raise ValueError("Not configured SSH key（可填 key_path，或配置目录 key 文件名）")
        if not key_target.exists() or not key_target.is_file():
            raise ValueError(f"SSH key File does not exist: {key_target}")
        try:
            os.chmod(str(key_target), 0o600)
        except Exception:
            pass
        argv.extend(["-i", str(key_target)])
    argv.append(f"{user}@{host}")
    return argv, meta


def default_app_config() -> dict:
    return {
        "version": 1,
        "web_port": DEFAULT_WEB_PORT,
        "modules": {
            "qbt": True,
            "ddns": True,
            "shareclip": True,
            "http": True,
        },
        "qbt": {
            "monitor_enabled": True,
            "client": "qbittorrent",
            "service_unit": "",
            "docker_container": "",
            "api_url": "",
            "homepage_clients_enabled": {
                "qbittorrent": True,
                "deluge": False,
                "transmission": False,
                "rtorrent": False,
            },
            "homepage_clients_order": [
                "qbittorrent",
                "deluge",
                "transmission",
                "rtorrent",
            ],
        },
        "http_service": {
            "root_dir": str(DEFAULT_STORAGE_ROOT),
            "default_dir": ".",
            "subtitle_permissions": {
                "owner_uid": DEFAULT_SUBTITLE_OWNER_UID,
                "owner_gid": DEFAULT_SUBTITLE_OWNER_GID,
                "file_mode": _normalize_subtitle_mode(DEFAULT_SUBTITLE_FILE_MODE, "664"),
                "dir_mode": _normalize_subtitle_mode(DEFAULT_SUBTITLE_DIR_MODE, "2775"),
            },
            "source_ip_pools": _default_source_ip_pools(),
            "source_ip_pool_source": _default_source_ip_pool_source(),
            "transfer_recent_ttl_sec": _normalize_transfer_recent_ttl(
                DEFAULT_TRANSFER_RECENT_TTL_SEC
            ),
        },
        "http_access": http_access.default_policy(),
        "terminal": {
            "enabled": True,
            "host": os.environ.get("TERMINAL_SSH_HOST", "127.0.0.1").strip()
            or "127.0.0.1",
            "port": _normalize_ssh_port(os.environ.get("TERMINAL_SSH_PORT", "22"), 22),
            "user": os.environ.get("TERMINAL_SSH_USER", "root").strip() or "root",
            "auth_mode": (
                os.environ.get("TERMINAL_AUTH_MODE", "key").strip().lower() or "key"
            ),
            "key_path": os.environ.get("TERMINAL_KEY_PATH", "~/.ssh/id_ed25519").strip(),
            "key_file": _normalize_terminal_key_file_name(
                os.environ.get("TERMINAL_KEY_FILE", "").strip()
            ),
        },
        "ui": {
            "hero_preset": "default",
            "hero_custom_bg_file": "",
        },
        "netdisk_sources": {
            "baidu": True,
            "ali": True,
            "guangya": True,
            "dropbox": False,
            "mega": False,
            "onedrive": False,
            "gdrive": False,
        },
    }


def normalize_app_config(raw) -> dict:
    base = default_app_config()
    if isinstance(raw, dict):
        if "web_port" in raw:
            base["web_port"] = _normalize_web_port(
                raw.get("web_port"), base.get("web_port", DEFAULT_WEB_PORT)
            )
        mods = raw.get("modules")
        if isinstance(mods, dict):
            for k in ("qbt", "ddns", "shareclip", "http"):
                if k in mods:
                    base["modules"][k] = bool(mods.get(k))
            if "http" not in mods and "http_monitor" in mods:
                base["modules"]["http"] = bool(mods.get("http_monitor"))
        qbt = raw.get("qbt")
        if isinstance(qbt, dict):
            if "monitor_enabled" in qbt:
                base["qbt"]["monitor_enabled"] = bool(qbt.get("monitor_enabled"))
            if "client" in qbt:
                c = str(qbt.get("client", "") or "").strip().lower()
                if c in {"qbittorrent", "deluge", "transmission", "rtorrent"}:
                    base["qbt"]["client"] = c
            if "service_unit" in qbt:
                base["qbt"]["service_unit"] = str(qbt.get("service_unit", "") or "").strip()
            if "docker_container" in qbt:
                base["qbt"]["docker_container"] = str(qbt.get("docker_container", "") or "").strip()
            if "api_url" in qbt:
                base["qbt"]["api_url"] = str(qbt.get("api_url", "") or "").strip()
            en = qbt.get("homepage_clients_enabled")
            if isinstance(en, dict):
                for k in ("qbittorrent", "deluge", "transmission", "rtorrent"):
                    if k in en:
                        base["qbt"]["homepage_clients_enabled"][k] = bool(en.get(k))
            od = qbt.get("homepage_clients_order")
            if isinstance(od, list):
                out = []
                seen = set()
                for item in od:
                    x = str(item or "").strip().lower()
                    if x in {"qbittorrent", "deluge", "transmission", "rtorrent"} and x not in seen:
                        seen.add(x)
                        out.append(x)
                for x in ("qbittorrent", "deluge", "transmission", "rtorrent"):
                    if x not in seen:
                        out.append(x)
                base["qbt"]["homepage_clients_order"] = out
        http_service = raw.get("http_service")
        if isinstance(http_service, dict):
            if "root_dir" in http_service:
                base["http_service"]["root_dir"] = _normalize_abs_dir_setting(
                    http_service.get("root_dir"), str(DEFAULT_STORAGE_ROOT)
                )
            if "default_dir" in http_service:
                base["http_service"]["default_dir"] = _normalize_rel_dir_setting(
                    http_service.get("default_dir")
                )
            sub_perm = http_service.get("subtitle_permissions")
            if isinstance(sub_perm, dict):
                cur = base["http_service"].setdefault("subtitle_permissions", {})
                if "owner_uid" in sub_perm:
                    cur["owner_uid"] = _normalize_subtitle_uid_gid(
                        sub_perm.get("owner_uid"), DEFAULT_SUBTITLE_OWNER_UID
                    )
                if "owner_gid" in sub_perm:
                    cur["owner_gid"] = _normalize_subtitle_uid_gid(
                        sub_perm.get("owner_gid"), DEFAULT_SUBTITLE_OWNER_GID
                    )
                if "file_mode" in sub_perm:
                    cur["file_mode"] = _normalize_subtitle_mode(
                        sub_perm.get("file_mode"), "664"
                    )
                if "dir_mode" in sub_perm:
                    cur["dir_mode"] = _normalize_subtitle_mode(
                        sub_perm.get("dir_mode"), "2775"
                    )
            if "source_ip_pools" in http_service:
                base["http_service"]["source_ip_pools"] = _normalize_source_ip_pools(
                    http_service.get("source_ip_pools")
                )
            if "source_ip_pool_source" in http_service:
                base["http_service"]["source_ip_pool_source"] = (
                    _normalize_source_ip_pool_source(
                        http_service.get("source_ip_pool_source")
                    )
                )
            if "transfer_recent_ttl_sec" in http_service:
                base["http_service"]["transfer_recent_ttl_sec"] = (
                    _normalize_transfer_recent_ttl(
                        http_service.get("transfer_recent_ttl_sec"),
                        base["http_service"].get(
                            "transfer_recent_ttl_sec", DEFAULT_TRANSFER_RECENT_TTL_SEC
                        ),
                    )
                )
        elif "http_root_dir" in raw:
            base["http_service"]["root_dir"] = _normalize_abs_dir_setting(
                raw.get("http_root_dir"), str(DEFAULT_STORAGE_ROOT)
            )
        elif "http_default_dir" in raw:
            base["http_service"]["default_dir"] = _normalize_rel_dir_setting(
                raw.get("http_default_dir")
            )
        if "http_access" in raw:
            base["http_access"] = http_access.normalize_policy(raw.get("http_access"))
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
                base["terminal"]["key_path"] = str(
                    terminal.get("key_path", "") or ""
                ).strip()
            if "key_file" in terminal:
                base["terminal"]["key_file"] = _normalize_terminal_key_file_name(
                    terminal.get("key_file", "")
                )
        ui = raw.get("ui")
        if isinstance(ui, dict):
            if "hero_preset" in ui:
                base["ui"]["hero_preset"] = _normalize_ui_hero_preset(
                    ui.get("hero_preset")
                )
        nd = raw.get("netdisk_sources")
        if isinstance(nd, dict):
            nd_cfg = base.setdefault("netdisk_sources", {})
            for k in ("baidu", "ali", "guangya", "dropbox", "mega", "onedrive", "gdrive"):
                if k in nd:
                    nd_cfg[k] = bool(nd.get(k))
    if base["terminal"]["auth_mode"] not in ("key", "password"):
        base["terminal"]["auth_mode"] = "key"
    base["http_service"]["root_dir"] = _normalize_abs_dir_setting(
        base["http_service"].get("root_dir", str(DEFAULT_STORAGE_ROOT)),
        str(DEFAULT_STORAGE_ROOT),
    )
    base["http_service"]["default_dir"] = _normalize_rel_dir_setting(
        base["http_service"]["default_dir"]
    )
    sub_perm = base["http_service"].setdefault("subtitle_permissions", {})
    sub_perm["owner_uid"] = _normalize_subtitle_uid_gid(
        sub_perm.get("owner_uid"), DEFAULT_SUBTITLE_OWNER_UID
    )
    sub_perm["owner_gid"] = _normalize_subtitle_uid_gid(
        sub_perm.get("owner_gid"), DEFAULT_SUBTITLE_OWNER_GID
    )
    sub_perm["file_mode"] = _normalize_subtitle_mode(sub_perm.get("file_mode"), "664")
    sub_perm["dir_mode"] = _normalize_subtitle_mode(sub_perm.get("dir_mode"), "2775")
    base["http_service"]["source_ip_pools"] = _normalize_source_ip_pools(
        base["http_service"].get("source_ip_pools")
    )
    base["http_service"]["source_ip_pool_source"] = _normalize_source_ip_pool_source(
        base["http_service"].get("source_ip_pool_source")
    )
    base["http_service"]["transfer_recent_ttl_sec"] = _normalize_transfer_recent_ttl(
        base["http_service"].get(
            "transfer_recent_ttl_sec", DEFAULT_TRANSFER_RECENT_TTL_SEC
        ),
        DEFAULT_TRANSFER_RECENT_TTL_SEC,
    )
    base["terminal"]["port"] = _normalize_ssh_port(base["terminal"]["port"], 22)
    base["terminal"]["key_file"] = _normalize_terminal_key_file_name(
        base["terminal"].get("key_file", "")
    )
    base["web_port"] = _normalize_web_port(
        base.get("web_port", DEFAULT_WEB_PORT), DEFAULT_WEB_PORT
    )
    base["ui"]["hero_preset"] = _normalize_ui_hero_preset(
        (base.get("ui") or {}).get("hero_preset", "default")
    )
    base["ui"]["hero_custom_bg_file"] = ""
    base["version"] = 1
    return base


def load_app_config(app_root: Path = _APP_ROOT_DIR) -> dict:
    p = app_config_path(app_root)
    if not p.exists():
        return default_app_config()
    try:
        with open(p, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except Exception:
        return default_app_config()
    return normalize_app_config(raw)


def save_app_config(cfg: dict, app_root: Path = _APP_ROOT_DIR) -> dict:
    normalized = normalize_app_config(cfg)
    p = app_config_path(app_root)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(json.dumps(normalized, ensure_ascii=False, indent=2) + "\n")
    return normalized


def ensure_under_root(root: Path, candidate: Path) -> Path:
    resolved = candidate.resolve()
    if root not in [resolved, *resolved.parents]:
        raise ValueError("路径不在允许范围内")
    return resolved


def safe_relative_path(value: str) -> str:
    value = (value or ".").strip().replace("\\", "/")
    if value.startswith("/"):
        value = value[1:]
    return value or "."


def build_pub_embed_css() -> str:
    """ShareClip 内嵌页：与Control台Theme变量一致，随 data-theme 切换深浅色。"""
    return """/* ShareClip embed — link with Control panel data-theme */
:root, :root[data-theme="light"] {
  --bg: #e8ecf4;
  --text: #1c2333;
  --text-muted: #5c6578;
  --border: rgba(28, 35, 51, 0.12);
  --accent: #2563eb;
  --accent-soft: rgba(37, 99, 235, 0.12);
  --card: rgba(255, 255, 255, 0.7);
  --surface-soft: #f8fafc;
  --surface-elevated: #ffffff;
  --surface-hover: #eef2f7;
  --panel: rgba(248, 250, 252, 0.78);
  --secondary: #475569;
  --secondary-bg: rgba(241, 245, 249, 0.72);
  --secondary-bg-hover: #e2e8f0;
  --radius: 16px;
  --shell-gap: clamp(24px, 5vw, 56px);
  --shell-pad: clamp(14px, 2.5vw, 24px);
  --glass-blur: 12px;
}
:root[data-theme="dark"] {
  --bg: #0f1419;
  --text: #e8ecf4;
  --text-muted: #94a3b8;
  --border: rgba(255, 255, 255, 0.1);
  --accent: #60a5fa;
  --accent-soft: rgba(96, 165, 250, 0.22);
  --card: rgba(26, 35, 50, 0.65);
  --surface-soft: rgba(15, 23, 42, 0.55);
  --surface-elevated: rgba(15, 23, 42, 0.8);
  --surface-hover: rgba(51, 65, 85, 0.5);
  --panel: rgba(15, 20, 25, 0.72);
  --secondary: #cbd5e1;
  --secondary-bg: rgba(51, 65, 85, 0.6);
  --secondary-bg-hover: rgba(71, 85, 105, 0.75);
}
body {
  background: transparent !important;
}
.FC_ClipCard {
  background: var(--card) !important;
  backdrop-filter: blur(var(--glass-blur)) !important;
  -webkit-backdrop-filter: blur(var(--glass-blur)) !important;
  border: 1px solid var(--border) !important;
  border-radius: var(--radius) !important;
  box-shadow: 0 4px 16px rgba(15, 23, 42, 0.05) !important;
}
.FC_Panel {
  background: var(--panel) !important;
  backdrop-filter: blur(var(--glass-blur)) !important;
  -webkit-backdrop-filter: blur(var(--glass-blur)) !important;
  border: 1px solid var(--border) !important;
  border-radius: var(--radius) !important;
}
html {
  box-sizing: border-box;
  -webkit-text-size-adjust: 100%;
}
*, *::before, *::after { box-sizing: inherit; }
body {
  margin: 0 !important;
  padding: var(--shell-pad) !important;
  min-height: 100vh !important;
  width: min(calc(100vw - var(--shell-gap)), 1680px) !important;
  max-width: calc(100vw - var(--shell-gap)) !important;
  margin-left: auto !important;
  margin-right: auto !important;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Helvetica Neue", sans-serif !important;
  font-size: 15px !important;
  line-height: 1.45 !important;
  color: var(--text) !important;
  background: linear-gradient(135deg, #e0e7ff 0%, #fae8ff 100%) fixed !important;
  background-attachment: fixed !important;
}
:root[data-theme="dark"] body {
  background: linear-gradient(165deg, #1e293b 0%, var(--bg) 40%, #0c1018 100%) fixed !important;
}
.g .c, section.c {
  background: var(--card) !important;
  border-color: var(--border) !important;
  color: var(--text) !important;
  box-shadow: 0 4px 24px rgba(0,0,0,.12) !important;
}
.panel, .hist .item, .t {
  background: var(--panel) !important;
  border-color: var(--border) !important;
  color: var(--text) !important;
}
.hist .item:hover, .t:hover, .list-item:hover, .item:hover {
  background: var(--surface-hover) !important;
}
.f {
  display: none !important;
}
input, textarea {
  background: var(--surface-soft) !important;
  border-color: var(--border) !important;
  color: var(--text) !important;
}
.paste {
  background: var(--panel) !important;
  border-color: var(--accent) !important;
  color: var(--text-muted) !important;
}
#root, #app, main, .app, .layout, .page, .container {
  max-width: 100% !important;
}
a { color: var(--accent) !important; }
a:hover { opacity: 0.88; }
button, .btn, [role="button"], input[type="submit"], input[type="button"], input[type="reset"] {
  background: var(--accent) !important;
  color: #fff !important;
  border: 1px solid transparent !important;
  border-radius: 10px !important;
  font-family: inherit !important;
}
button:hover, .btn:hover, [role="button"]:hover, input[type="submit"]:hover, input[type="button"]:hover, input[type="reset"]:hover {
  filter: brightness(0.96);
}
.btn.secondary, .btn-secondary, .btn-ghost, .btn-outline {
  background: var(--secondary-bg) !important;
  color: var(--secondary) !important;
  border: 1px solid var(--border) !important;
}
.btn.secondary:hover, .btn-secondary:hover, .btn-ghost:hover, .btn-outline:hover {
  background: var(--secondary-bg-hover) !important;
  color: var(--text) !important;
}
input, textarea, select {
  border-radius: 10px !important;
  font-size: 15px !important;
}
input:focus, textarea:focus, select:focus {
  outline: none !important;
  border-color: var(--accent) !important;
  box-shadow: 0 0 0 3px var(--accent-soft) !important;
}
table { border-collapse: collapse; width: 100%; }
p, label, .meta { color: var(--text-muted) !important; }
h1, h2 { color: var(--text) !important; }
"""


def _inject_pub_theme_link(html: str) -> str:
    if "/pub/embed.css" in html:
        return html
    link = (
        '<link rel="stylesheet" href="/pub/embed.css" />\n'
        '<script>(function(){try{var t=localStorage.getItem("fc-theme");'
        'if(!t) { t = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"; }'
        'document.documentElement.setAttribute("data-theme",t);}catch(e){}})();'
        'window.addEventListener("message", function(e) { if(e.data.type === "theme-change") { document.documentElement.setAttribute("data-theme", e.data.theme); localStorage.setItem("fc-theme", e.data.theme); } });'
        '</script>\n'
    )
    spa_script = """
    <script>
    document.addEventListener("DOMContentLoaded", function() {
        document.body.addEventListener("submit", async function(e) {
            const form = e.target;
            if (form.method.toLowerCase() !== "post") return;
            e.preventDefault();
            const submitBtn = form.querySelector('button[type="submit"], input[type="submit"]');
            const originalText = submitBtn ? (submitBtn.textContent || submitBtn.value) : "";
            if (submitBtn) {
                if (submitBtn.tagName === 'BUTTON') submitBtn.textContent = '. . .\;
                else submitBtn.value = '. . .\;
                submitBtn.disabled = true;
            }
            try {
                const formData = new FormData(form);
                const response = await fetch(form.action, {
                    method: 'POST',
                    body: formData,
                    headers: { 'X-Requested-With': 'XMLHttpRequest' }
                });
                if (response.ok) {
                    const htmlResponse = await fetch(window.location.href);
                    const htmlText = await htmlResponse.text();
                    const parser = new DOMParser();
                    const doc = parser.parseFromString(htmlText, 'text/html');
                    document.body.innerHTML = doc.body.innerHTML;
                    if (window.parent !== window) {
                        window.parent.postMessage({ type: 'toast', msg: '操作成功', msgType: 'success' }, '*');
                    }
                } else {
                    if (window.parent !== window) {
                        window.parent.postMessage({ type: 'toast', msg: '操作失败', msgType: 'error' }, '*');
                    }
                }
            } catch (err) {
                console.error("Submit error:", err);
            } finally {
                if (submitBtn && document.body.contains(submitBtn)) {
                    if (submitBtn.tagName === 'BUTTON') submitBtn.textContent = originalText;
                    else submitBtn.value = originalText;
                    submitBtn.disabled = false;
                }
            }
        });
    });
    </script>
    """
    
    lower = html.lower()
    
    # Inject link into head
    pos = lower.rfind("</head>")
    if pos >= 0:
        html = html[:pos] + link + html[pos:]
    else:
        pos = lower.find("<head>")
        if pos >= 0:
            gt = html.find(">", pos)
            if gt >= 0:
                html = html[: gt + 1] + link + html[gt + 1 :]
        else:
            html = '<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"/>' + link + "</head><body>" + html + "</body></html>"
            
    # Re-evaluate lower after html mutation
    lower = html.lower()
    pos_body = lower.rfind("</body>")
    if pos_body >= 0:
        html = html[:pos_body] + spa_script + html[pos_body:]
    else:
        html += spa_script

    # 避免与Control台 /config 冲突：ShareClip 配置页改走 /clip-config 代理入口。
    html = html.replace('href="/config"', 'href="/clip-config"')
    html = html.replace("href='/config'", "href='/clip-config'")
    html = html.replace('action="/config"', 'action="/clip-config"')
    html = html.replace("action='/config'", "action='/clip-config'")

    return html


_PROXY_SKIP_RESPONSE_HEADERS = frozenset(
    {"transfer-encoding", "connection", "content-length", "content-encoding"}
)
_PROXY_FORWARD_REQUEST_HEADERS = frozenset(
    {"content-type", "authorization", "cookie", "accept", "accept-language"}
)


def shareclip_route_match(path: str, query_id_pub: bool) -> bool:
    """与 ShareClip（Flask）路由对齐；`/?id=pub` 为剪贴首页，其余为 API/静态文件。"""
    path = path or "/"
    if path == "/" and query_id_pub:
        return True
    if path == "/clip-config":
        return True
    if path.startswith("/api/clip"):
        return True
    if path.startswith("/api/history"):
        return True
    if path == "/api/config":
        return True
    if path.startswith("/clips/"):
        return True
    return False


def ddnsgo_route_match(path: str) -> bool:
    path = path or "/"
    return path == "/ddns-go" or path.startswith("/ddns-go/")


def _rewrite_ddnsgo_html(html: str) -> str:
    out = html
    out = out.replace('href="/', 'href="/ddns-go/')
    out = out.replace('src="/', 'src="/ddns-go/')
    out = out.replace('action="/', 'action="/ddns-go/')
    out = out.replace('fetch("/', 'fetch("/ddns-go/')
    out = out.replace("fetch('/", "fetch('/ddns-go/")
    out = out.replace('window.location="/', 'window.location="/ddns-go/')
    out = out.replace("window.location='/", "window.location='/ddns-go/")
    while "/ddns-go/ddns-go/" in out:
        out = out.replace("/ddns-go/ddns-go/", "/ddns-go/")
    return out


def _rewrite_ddnsgo_location(location: str, base_url: str) -> str:
    loc = (location or "").strip()
    if not loc:
        return loc
    b = base_url.rstrip("/")
    if loc.startswith(b):
        suffix = loc[len(b) :]
        if not suffix.startswith("/"):
            suffix = "/" + suffix
        return "/ddns-go" + suffix
    if loc.startswith("/"):
        return "/ddns-go" + loc
    return loc


def build_frontend_html() -> str:
    html = """<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>AfterClaw</title>
  <script>
    (function(){
      try {
        var t = localStorage.getItem("fc-theme");
        var hero = localStorage.getItem("fc-hero-preset");
        if (!t) { t = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"; }
        document.documentElement.setAttribute("data-theme", t);
        if (hero) { document.documentElement.setAttribute("data-hero-preset", hero); }
      } catch(e){}
    })();
  </script>
  <link rel="stylesheet" href="/dashboard.css" />
  <script src="/i18n.js?v=20260430d"></script>
</head>
<body>
  <div class="wrap">
  <header class="page-head page-head-dashboard">
    <div class="head-row head-row-dashboard">
      <div class="head-main">
        <h1>AfterClaw</h1>
      </div>
    </div>
  </header>

  <div class="tabs-row">
    <div class="tabs">
      <button id="tabMonitorBtn" class="tab-btn active" type="button">Control</button>
      <button id="tabDirBtn" class="tab-btn" type="button">Directory Service</button>
      <button id="tabBackupBtn" class="tab-btn" type="button" style="display:none">Backup</button>
      <button id="tabPubBtn" class="tab-btn" type="button">ShareClip</button>
    </div>
    <div class="tabs-actions">
      <a id="terminalQuickLink" href="/terminal" class="gear-btn terminal-btn" title="Terminal" aria-label="Terminal"><svg class="ui-icon term-icon" viewBox="0 0 24 24" aria-hidden="true"><rect x="4.5" y="5.5" width="15" height="13" rx="2.4"></rect><path d="M8 10.2 L10.8 12 L8 13.8"></path><line x1="12.8" y1="13.9" x2="16" y2="13.9"></line></svg></a>
      <a href="/config" class="gear-btn" title="Config" aria-label="Config"><svg class="ui-icon" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="3.2"></circle><path d="M19.4 15a1.7 1.7 0 0 0 .34 1.87l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06A1.7 1.7 0 0 0 15 19.4a1.7 1.7 0 0 0-1 .74 1.7 1.7 0 0 0-.2 1v.2a2 2 0 1 1-4 0v-.2a1.7 1.7 0 0 0-.2-1 1.7 1.7 0 0 0-1-.74 1.7 1.7 0 0 0-1.87.34l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.7 1.7 0 0 0 4.6 15a1.7 1.7 0 0 0-.74-1 1.7 1.7 0 0 0-1-.2h-.2a2 2 0 1 1 0-4h.2a1.7 1.7 0 0 0 1-.2 1.7 1.7 0 0 0 .74-1 1.7 1.7 0 0 0-.34-1.87l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.7 1.7 0 0 0 9 4.6a1.7 1.7 0 0 0 1-.74 1.7 1.7 0 0 0 .2-1v-.2a2 2 0 1 1 4 0v.2a1.7 1.7 0 0 0 .2 1 1.7 1.7 0 0 0 1 .74 1.7 1.7 0 0 0 1.87-.34l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.7 1.7 0 0 0 19.4 9a1.7 1.7 0 0 0 .74 1 1.7 1.7 0 0 0 1 .2h.2a2 2 0 1 1 0 4h-.2a1.7 1.7 0 0 0-1 .2 1.7 1.7 0 0 0-.74 1z"></path></svg></a>
      <button type="button" id="themeToggleBtn" class="gear-btn" title="Toggle theme"><svg class="ui-icon" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4.2"></circle><path d="M12 2.5v2.2M12 19.3v2.2M4.7 4.7l1.6 1.6M17.7 17.7l1.6 1.6M2.5 12h2.2M19.3 12h2.2M4.7 19.3l1.6-1.6M17.7 6.3l1.6-1.6"></path></svg></button>
      <select id="langSelect" class="lang-select" title="Language">
        <option value="zh-CN">简体中文</option>
        <option value="zh-TW">繁體中文</option>
        <option value="en">English</option>
        <option value="de">Deutsch</option>
        <option value="fr">Français</option>
        <option value="ja">日本語</option>
      </select>
    </div>
  </div>

  <div id="tabDirPanel" class="tab-panel">
  <div class="card">
    <span class="card-title">Directory & Bulk HTTP Links</span>
    <div class="kv-line"><strong>存储根目录</strong><span id="storageText">-</span></div>
    <div class="kv-line"><strong>公开访问域名</strong><span id="publicBaseText">-</span></div>
    <div class="kv-line"><strong>当前目录</strong><span id="currentDirText">.</span></div>
    <div class="toolbar">
      <div class="toolbar-left">
        <button id="refreshBtn" class="secondary">Refresh Directory</button>
        <button id="backBtn" class="secondary">Parent Directory</button>
        <button id="listBtn">Generate HTTP Link</button>
        <button id="copyBtn" class="secondary">Copy All Links</button>
        <button id="copyDirNameBtn" class="secondary">Copy Directory Name</button>
      </div>
    </div>
    <label>Subdirectories (click to open)</label>
    <div id="dirList" class="dir-list"></div>
    <div class="status-row">
      <div id="status" class="status-bar muted"></div>
      <div id="dirStatsText" class="status-bar muted dir-summary">Files 0 · Dirs 0 · Size 0B</div>
    </div>
  </div>

  <div class="card">
    <details class="card-fold">
      <summary class="card-collapse-btn">
        <span class="card-title" style="margin-bottom:0;">Filename & Subtitle Tools</span>
        <span class="card-collapse-arrow" aria-hidden="true">▶</span>
      </summary>
      <div id="cleanBody" class="card-fold-body">
      <div class="tabs" style="margin:0 0 12px 0;justify-content:flex-start;">
        <button type="button" class="tab-btn active" id="cleanModeRenameBtn">Cleanup / Rename</button>
        <button type="button" class="tab-btn" id="cleanModeSubtitleBtn">Sub Management</button>
      </div>
      <div id="cleanRenamePanel">
        <p class="muted" style="margin:0 0 10px;">在<strong>当前相对目录</strong>下重命名；先Preview再执行。可去掉宣传段、中文，并将 <code>S02</code> 季号挪到「首个 20xx 年」前（点分节）。</p>
        <label for="cleanSubstrings">Substrings to remove (one per line)</label>
        <textarea id="cleanSubstrings" style="min-height:72px;font-size:12px;" placeholder="e.g. full segment: ￡cXcY@FRDS"></textarea>
        <div class="row" style="margin-top:8px;align-items:flex-start;">
          <label class="inline-check" style="margin-top:0"><input type="checkbox" id="cleanStripCjk" /> Strip CJK (Chinese/full-width blocks)</label>
          <label class="inline-check" style="margin-top:0"><input type="checkbox" id="cleanMoveSeason" checked /> Move season S## before first year 20xx</label>
        </div>
        <div class="row" style="margin-top:4px;">
          <label for="cleanTarget" style="margin:0;align-self:center;">Target</label>
          <select id="cleanTarget" class="small-inp" style="min-width:140px;">
            <option value="both" selected>文件 + 子文件夹</option>
            <option value="files">仅文件</option>
            <option value="dirs">仅子文件夹</option>
          </select>
          <label class="inline-check" style="margin-top:0"><input type="checkbox" id="cleanRecursive" /> Include subdirectories (rename bottom-up)</label>
        </div>
        <div class="row" style="margin-top:8px;">
          <button type="button" class="secondary" id="cleanPreviewBtn">Preview</button>
          <button type="button" id="cleanApplyBtn" disabled>Apply rename by preview</button>
        </div>
        <div id="cleanPreview" class="clean-preview" style="display:none" aria-live="polite"></div>
        <div id="cleanStatus" class="status-bar muted" style="margin-top:6px"></div>
      </div>
      <div id="cleanSubtitlePanel" style="display:none">
        <div class="sub-mgmt-layout">
          <div class="sub-mgmt-left">
            <p class="muted" style="margin:0 0 10px;">字幕对齐：按同目录文件名优先匹配；若文件名不一致，则按 <code>SxxExx</code>（如 <code>S01E02</code>）匹配视频并重命名字幕。</p>
            <label class="inline-check" style="margin-top:0"><input type="checkbox" id="subtitleAlignRecursive" /> Include subdirectories (align bottom-up)</label>
            <div class="row" style="margin-top:8px;">
              <button type="button" class="secondary" id="subtitleAlignPreviewBtn">Preview align</button>
              <button type="button" id="subtitleAlignApplyBtn" disabled>Apply align by preview</button>
            </div>
            <div id="subtitleAlignStatus" class="status-bar muted" style="margin-top:6px"></div>
            <p class="muted" style="margin:14px 0 8px;">Subtitle upload: upload <code>.srt</code>, <code>.ass</code>, <code>.ssa</code>, <code>.vtt</code>, or archives such as <code>.zip</code>, <code>.rar</code>, <code>.7z</code>, <code>.gz</code>.</p>
            <p style="margin:0 0 10px;color:var(--danger);font-weight:700;">Archive files are deleted after extraction (not kept).</p>
            <label for="subtitleUploadInput">Subtitle files or archives</label>
            <input id="subtitleUploadInput" type="file" multiple accept=".srt,.ass,.ssa,.vtt,.sub,.idx,.zip,.rar,.7z,.gz,.tgz,.tar,.tbz2,.txz,.bz2,.xz" />
            <div class="row" style="margin-top:8px;">
              <button type="button" id="subtitleUploadBtn">Upload subtitles</button>
            </div>
            <div id="subtitleUploadStatus" class="status-bar muted" style="margin-top:6px"></div>
          </div>
          <div class="sub-mgmt-right">
            <label style="margin:0 0 6px;display:block;">Preview</label>
            <div id="subtitleAlignPreview" class="clean-preview" style="display:none" aria-live="polite"></div>
            <div id="subtitleUploadResult" class="clean-preview" style="display:none" aria-live="polite"></div>
          </div>
        </div>
      </div>
      </div>
    </details>
  </div>

  <div class="card">
    <span class="card-title">Bulk Text (one HTTP link per line)</span>
    <textarea id="bulkText" readonly></textarea>
  </div>
  </div>

  <div id="tabBackupPanel" class="tab-panel">
  <div class="card">
    <span class="card-title">Backup Management</span>
    <div class="kv-line"><strong>Config Path</strong><span id="backupConfigPath">-</span></div>
    <div class="kv-line"><strong>Database</strong><span id="backupDbStatus">-</span></div>
    <div class="kv-line"><strong>Snapshots</strong><span id="backupSnapshotCount">-</span></div>
    <div class="kv-line"><strong>Total Size</strong><span id="backupTotalSize">-</span></div>
    <div class="kv-line"><strong>Last Backup</strong><span id="backupLastTime">-</span></div>
    <div class="toolbar">
      <div class="toolbar-left">
        <button id="backupRunBtn">Run Backup Now</button>
        <button id="backupRefreshBtn" class="secondary">Refresh Status</button>
        <button id="backupConfigBtn" class="secondary">Edit Config</button>
      </div>
    </div>
    <div id="backupResult" class="status-bar muted" style="margin-top:10px;"></div>
    <details class="card-fold" style="margin-top:20px;">
      <summary class="card-collapse-btn">
        <span class="card-title" style="margin-bottom:0;">Snapshot History</span>
        <span class="card-collapse-arrow" aria-hidden="true">▶</span>
      </summary>
      <div class="card-fold-body">
        <div id="backupSnapshotList" style="max-height:400px;overflow-y:auto;"></div>
      </div>
    </details>
  </div>
  </div>

  <div id="tabPubPanel" class="tab-panel">
  <div class="card">
    <div class="pub-head">
      <button id="openPubNewBtn" class="secondary" type="button">Open in new window</button>
    </div>
    <div class="clip-grid">
      <section class="clip-card">
        <h3 class="clip-title" id="clipCardTitle">ShareClip</h3>
        <div class="clip-sub" id="clipSubText">Per-ID temporary clip sharing in LAN.</div>
        <label id="clipIdLabel" for="clipIdInput">ID</label>
        <input id="clipIdInput" placeholder="Example: team_alpha or group01" value="pub" />
        <div class="clip-meta"><span id="clipCurrentLabel">Current ID:</span> <code id="clipCurrentId">pub</code></div>
        <h4 id="clipPublishTitle" style="margin:10px 0 6px;">Publish</h4>
        <label id="clipTextLabel" for="clipTextInput">Text</label>
        <textarea id="clipTextInput"></textarea>
        <div id="clipPasteZone" class="clip-paste" tabindex="0">Click then Ctrl+V (image/text)</div>
        <label id="clipImageLabel" for="clipImageInput">Image</label>
        <input id="clipImageInput" type="file" accept="image/*" />
        <div class="clip-row" style="margin-top:8px;">
          <button id="clipSendBtn" type="button">Send</button>
          <button id="clipReadBtn" class="secondary" type="button">Read Clipboard</button>
        </div>
        <div id="clipStatus" class="clip-status"></div>
      </section>
      <section class="clip-card">
        <h3 class="clip-title" id="clipLatestTitle">Latest</h3>
        <div class="clip-row">
          <button id="clipRefreshLatestBtn" class="secondary" type="button">Refresh</button>
          <a id="clipRawLink" href="#" target="_blank" rel="noopener">Raw</a>
        </div>
        <div id="clipLatestMeta" class="clip-meta">No content</div>
        <div id="clipLatestView" class="clip-panel">No content</div>
      </section>
      <section class="clip-card">
        <h3 class="clip-title" id="clipHistoryTitle">History</h3>
        <div class="clip-row">
          <button id="clipRefreshHistoryBtn" class="secondary" type="button">Refresh History</button>
        </div>
        <div id="clipHistoryMeta" class="clip-meta">Loading...</div>
        <div id="clipHistoryList" class="clip-history"></div>
      </section>
    </div>
  </div>
  </div>

  <div id="tabMonitorPanel" class="tab-panel active">
  <div class="card">
    <span class="card-title">Control Status & Actions</span>
    <div id="sysStatus" class="sys-strip muted">系统状态加载中...</div>
    <div class="svc-grid">
      <div class="svc-card" id="qbtSvcCard">
        <div class="svc-name">BitTorrent Service</div>
        <div id="qbtClientTabBarWrap" style="display:flex;justify-content:flex-start;margin:6px 0 8px;"></div>
        <div id="qbtStatusText" class="svc-meta">加载中...</div>
        <div class="row">
          <button id="qbtStartBtn" class="secondary">Start</button>
          <button id="qbtStopBtn" class="secondary">Stop</button>
          <button id="qbtRestartBtn" class="secondary">Restart</button>
        </div>
      </div>
      <div class="svc-card" id="ddnsSvcCard">
        <div class="svc-name">DDNS Service</div>
        <div id="ddnsStatusText" class="svc-meta">加载中...</div>
        <div id="ddnsDomainText" class="svc-meta">Sync Domains: -</div>
        <div class="row">
          <button id="ddnsToggleBtn" class="secondary">Toggle</button>
          <button id="ddnsRestartBtn" class="secondary">Restart</button>
        </div>
      </div>
      <div class="svc-card" id="httpSvcCard">
        <div class="svc-name">HTTPD Service</div>
        <div id="selfStatusText" class="svc-meta">加载中...</div>
        <div id="httpAccessText" class="svc-meta">Access: …</div>
        <div class="http-actions-grid">
          <button type="button" id="toggleDownloadBtn" class="secondary">Lan</button>
          <button type="button" id="restartServiceBtn" class="secondary">Restart</button>
          <button type="button" id="httpAccessAlwaysBtn" class="danger-btn">Timed</button>
          <select id="httpAccessDuration" class="http-duration-select">
            <option value="0" id="httpNoDurationOption" disabled hidden>No Duration</option>
            <option value="3600">1 hour</option>
            <option value="28800" selected>8 hours</option>
            <option value="86400">24 hours</option>
          </select>
        </div>
      </div>
    </div>
    <div id="monitorStatus" class="status-bar muted"></div>
  </div>

  <div class="card" id="httpSpeedCard">
    <div class="speed-card-head">
      <span id="httpSpeedCardTitle" class="card-title">Aggregate HTTP Throughput</span>
      <span class="speed-card-conn">
        <span id="connText" class="speed-card-conn-num">-</span>
        <span class="speed-card-conn-label">active connections</span>
      </span>
    </div>
    <div id="speedText" class="speed-totals" role="button" tabindex="0" aria-label="Click to switch units">-</div>
    <div id="sourceSpeedText" class="speed-sources">Loading source speeds...</div>
  </div>

  <div class="card" id="netdiskCard">
    <div id="ndTabBarWrap" style="display:flex;align-items:center;justify-content:center;gap:10px;margin-bottom:12px;"></div>

    <span id="netdiskTransferCardTitle" class="card-title">Aggregate HTTP Session Activity</span>
    <div class="xfer-head">
      <div id="xferSummary" class="xfer-summary">Active Sessions 0</div>
      <div class="xfer-toolbar">
        <span class="xfer-sort-label">Sort</span>
        <div class="xfer-sort-group">
          <button type="button" class="xfer-sort-btn active" data-sort="speed">Speed</button>
          <button type="button" class="xfer-sort-btn" data-sort="progress">Progress</button>
          <button type="button" class="xfer-sort-btn" data-sort="name">Name</button>
          <button type="button" class="xfer-sort-btn" data-sort="source">Source</button>
        </div>
      </div>
    </div>
    <div id="xferList" class="xfer-list"></div>

    <div id="ndDetailArea"></div>
    <div id="ndStatusText" class="status-bar muted">Preparing...</div>
  </div>
  </div>

  <footer class="global-footer">AfterClaw __APP_VERSION_TEXT__ by RandyPKU</footer>
  </div>

  <div id="toastContainer"></div>

  <script>
    const i18nReady = (window.fccI18n && window.fccI18n.initPage)
      ? window.fccI18n.initPage({ selectId: "langSelect" }).catch(() => {})
      : Promise.resolve();
    const tabDirBtn = document.getElementById("tabDirBtn");
    const tabMonitorBtn = document.getElementById("tabMonitorBtn");
    const tabBackupBtn = document.getElementById("tabBackupBtn");
    const tabPubBtn = document.getElementById("tabPubBtn");
    const tabDirPanel = document.getElementById("tabDirPanel");
    const tabMonitorPanel = document.getElementById("tabMonitorPanel");
    const tabBackupPanel = document.getElementById("tabBackupPanel");
    const tabPubPanel = document.getElementById("tabPubPanel");
    const storageText = document.getElementById("storageText");
    const publicBaseText = document.getElementById("publicBaseText");
    const speedText = document.getElementById("speedText");
    const connText = document.getElementById("connText");
    const sourceSpeedText = document.getElementById("sourceSpeedText");
    const httpSvcCard = document.getElementById("httpSvcCard");
    const httpSpeedCard = document.getElementById("httpSpeedCard");
    const httpSpeedCardTitle = document.getElementById("httpSpeedCardTitle");
    const netdiskCard = document.getElementById("netdiskCard");
    const netdiskTransferCardTitle = document.getElementById("netdiskTransferCardTitle");
    const toggleDownloadBtn = document.getElementById("toggleDownloadBtn");
    const qbtStatusText = document.getElementById("qbtStatusText");
    const qbtClientTabBarWrap = document.getElementById("qbtClientTabBarWrap");
    const ddnsStatusText = document.getElementById("ddnsStatusText");
    const ddnsDomainText = document.getElementById("ddnsDomainText");
    const selfStatusText = document.getElementById("selfStatusText");
    const httpAccessText = document.getElementById("httpAccessText");
    const sysStatus = document.getElementById("sysStatus");
    const statusEl = document.getElementById("status");
    const dirStatsText = document.getElementById("dirStatsText");
    const monitorStatusEl = document.getElementById("monitorStatus");
    const dirList = document.getElementById("dirList");
    const xferSummary = document.getElementById("xferSummary");
    const xferList = document.getElementById("xferList");
    const xferSortButtons = Array.from(document.querySelectorAll(".xfer-sort-btn"));
    const bulkText = document.getElementById("bulkText");
    const currentDirText = document.getElementById("currentDirText");
    const clipIdInput = document.getElementById("clipIdInput");
    const clipCurrentLabel = document.getElementById("clipCurrentLabel");
    const clipCurrentId = document.getElementById("clipCurrentId");
    const clipCardTitle = document.getElementById("clipCardTitle");
    const clipSubText = document.getElementById("clipSubText");
    const clipIdLabel = document.getElementById("clipIdLabel");
    const clipPublishTitle = document.getElementById("clipPublishTitle");
    const clipTextLabel = document.getElementById("clipTextLabel");
    const clipImageLabel = document.getElementById("clipImageLabel");
    const clipLatestTitle = document.getElementById("clipLatestTitle");
    const clipHistoryTitle = document.getElementById("clipHistoryTitle");
    const clipTextInput = document.getElementById("clipTextInput");
    const clipImageInput = document.getElementById("clipImageInput");
    const clipPasteZone = document.getElementById("clipPasteZone");
    const clipStatus = document.getElementById("clipStatus");
    const clipLatestMeta = document.getElementById("clipLatestMeta");
    const clipLatestView = document.getElementById("clipLatestView");
    const clipHistoryMeta = document.getElementById("clipHistoryMeta");
    const clipHistoryList = document.getElementById("clipHistoryList");
    const clipRawLink = document.getElementById("clipRawLink");
    const clipSendBtn = document.getElementById("clipSendBtn");
    const clipReadBtn = document.getElementById("clipReadBtn");
    const clipRefreshLatestBtn = document.getElementById("clipRefreshLatestBtn");
    const clipRefreshHistoryBtn = document.getElementById("clipRefreshHistoryBtn");
    const terminalQuickLink = document.getElementById("terminalQuickLink");
    const langSelect = document.getElementById("langSelect");
    
    // Backup elements
    const backupConfigPath = document.getElementById("backupConfigPath");
    const backupDbStatus = document.getElementById("backupDbStatus");
    const backupSnapshotCount = document.getElementById("backupSnapshotCount");
    const backupTotalSize = document.getElementById("backupTotalSize");
    const backupLastTime = document.getElementById("backupLastTime");
    const backupResult = document.getElementById("backupResult");
    const backupSnapshotList = document.getElementById("backupSnapshotList");
    const backupRunBtn = document.getElementById("backupRunBtn");
    const backupRefreshBtn = document.getElementById("backupRefreshBtn");
    const backupConfigBtn = document.getElementById("backupConfigBtn");
    const cleanModeRenameBtn = document.getElementById("cleanModeRenameBtn");
    const cleanModeSubtitleBtn = document.getElementById("cleanModeSubtitleBtn");
    const cleanRenamePanel = document.getElementById("cleanRenamePanel");
    const cleanSubtitlePanel = document.getElementById("cleanSubtitlePanel");
    const subtitleAlignRecursive = document.getElementById("subtitleAlignRecursive");
    const subtitleAlignPreviewBtn = document.getElementById("subtitleAlignPreviewBtn");
    const subtitleAlignApplyBtn = document.getElementById("subtitleAlignApplyBtn");
    const subtitleAlignPreview = document.getElementById("subtitleAlignPreview");
    const subtitleAlignStatus = document.getElementById("subtitleAlignStatus");
    const subtitleUploadInput = document.getElementById("subtitleUploadInput");
    const subtitleUploadBtn = document.getElementById("subtitleUploadBtn");
    const subtitleUploadStatus = document.getElementById("subtitleUploadStatus");
    const subtitleUploadResult = document.getElementById("subtitleUploadResult");
    const httpAccessDuration = document.getElementById("httpAccessDuration");
    const httpNoDurationOption = document.getElementById("httpNoDurationOption");
    const httpAccessAlwaysBtn = document.getElementById("httpAccessAlwaysBtn");
    let currentDir = ".";
    let defaultHttpDir = ".";
    let lastCleanMoves = null;
    let lastSubtitleAlignMoves = null;
    let latestLinks = [];
    let downloadsEnabled = true;
    let transferSortMode = "speed";
    let transferSortAscending = false;
    let latestTransfers = [];
    let latestSourceStats = [];
    let latestTotalDownMiBps = 0;
    let latestTotalUpMiBps = 0;
    let latestTotalDownMbps = 0;
    let latestTotalUpMbps = 0;
    let speedDisplayUnit = "MiB/s";
    let speedValueReady = false;
    let latestTransferOverview = { count: 0, recent_count: 0, overall_progress_pct: 0 };
    let heroTheme = { hero_preset: "default", hero_custom_bg_file: "", hero_custom_bg_url: "" };
    let clipCurrent = "pub";
    let clipCapturedImage = null;
    let qbtControlOn = false;
    let httpPublicPersistent = false;
    let httpAccessPublic = false;
    let lastTimedDurationSec = 28800;
    let lastHttpAccessState = null;
    let btActiveClient = "qbittorrent";
    let btHomepageEnabled = { qbittorrent: true, deluge: false, transmission: false, rtorrent: false };
    let btHomepageOrder = ["qbittorrent", "deluge", "transmission", "rtorrent"];
    let ddnsControlOn = false;
    let httpModuleOn = true;

    const THEME_KEY = "fc-theme";
    const HERO_THEME_KEY = "fc-hero-preset";
    let dashboardPauseUntil = 0;

    function pauseRealtime(ms = 4000) {
      const ttl = Math.max(300, Number(ms) || 0);
      dashboardPauseUntil = Math.max(dashboardPauseUntil, Date.now() + ttl);
    }

    function isRealtimePaused() {
      if (Date.now() < dashboardPauseUntil) return true;
      const ae = document.activeElement;
      return !!ae && ae.tagName === "SELECT";
    }

    function getStoredTheme() {
      return localStorage.getItem(THEME_KEY) || "light";
    }

    function applyTheme(theme) {
      document.documentElement.setAttribute("data-theme", theme);
      localStorage.setItem(THEME_KEY, theme);
    }

    function showToast(msg, type = "success") {
      const container = document.getElementById("toastContainer");
      if (!container) return;
      const t = document.createElement("div");
      t.className = "toast " + type;
      t.textContent = msg;
      container.appendChild(t);
      setTimeout(() => {
        if (t.parentNode) t.parentNode.removeChild(t);
      }, 3000);
    }

    function toggleTheme() {
      const next = getStoredTheme() === "dark" ? "light" : "dark";
      applyTheme(next);
      showToast("切换为" + (next === "dark" ? "深色" : "浅色") + "Theme");
      
    }

    function normalizeHeroPreset(v) {
      const x = String(v || "").trim().toLowerCase();
      if (x === "aurora" || x === "sunset" || x === "frost" || x === "afterclaw_clouds") return x;
      return "default";
    }

    function applyHeroTheme(uiTheme) {
      const t = uiTheme || {};
      const preset = normalizeHeroPreset(t.hero_preset || "default");
      heroTheme = {
        hero_preset: preset,
        hero_custom_bg_file: "",
        hero_custom_bg_url: "",
      };
      document.documentElement.setAttribute("data-hero-preset", preset);
      try { localStorage.setItem(HERO_THEME_KEY, preset); } catch (e) {}
      document.documentElement.style.removeProperty("--hero-custom-url");
    }

    function clipUrl(path) {
      const u = new URL(path, window.location.origin);
      if (clipCurrent) u.searchParams.set("id", clipCurrent);
      return u.toString();
    }

    function applyShareclipLocaleUI() {
      if (clipCardTitle) clipCardTitle.textContent = "ShareClip";
      if (clipSubText) clipSubText.textContent = "Per-ID temporary clip sharing in LAN.";
      if (clipIdLabel) clipIdLabel.textContent = "ID";
      if (clipCurrentLabel) clipCurrentLabel.textContent = "Current ID:";
      if (clipPublishTitle) clipPublishTitle.textContent = "Publish";
      if (clipTextLabel) clipTextLabel.textContent = "Text";
      if (clipImageLabel) clipImageLabel.textContent = "Image";
      if (clipLatestTitle) clipLatestTitle.textContent = "Latest";
      if (clipHistoryTitle) clipHistoryTitle.textContent = "History";
      if (clipPasteZone) clipPasteZone.textContent = "Click then Ctrl+V (image/text)";
      if (clipSendBtn) clipSendBtn.textContent = "Send";
      if (clipReadBtn) clipReadBtn.textContent = "Read Clipboard";
      if (clipRefreshLatestBtn) clipRefreshLatestBtn.textContent = "Refresh";
      if (clipRefreshHistoryBtn) clipRefreshHistoryBtn.textContent = "Refresh History";
      if (clipRawLink) clipRawLink.textContent = "Raw";
      if (clipIdInput) clipIdInput.placeholder = "Example: team_alpha or group01";
      if (window.fccI18n && typeof window.fccI18n.apply === "function" && tabPubPanel) {
        window.fccI18n.apply(tabPubPanel);
      }
    }

    function setClipStatus(text, isError = false) {
      clipStatus.textContent = trRaw(text);
      clipStatus.classList.toggle("err", isError);
      showToast(trRaw(text), isError ? "error" : "success");
    }

    function normalizeClipId(v) {
      const id = String(v || "").trim();
      if (!/^[A-Za-z0-9_-]{1,64}$/.test(id)) {
        throw new Error("ID can only contain letters/numbers/_/- with length 1-64");
      }
      return id;
    }

    function escapeHtml(s) {
      return String(s || "").replace(/[&<>"']/g, (c) => {
        if (c === "&") return "&amp;";
        if (c === "<") return "&lt;";
        if (c === ">") return "&gt;";
        if (c === '"') return "&quot;";
        return "&#39;";
      });
    }

    function renderClipLatest(rec) {
      if (!rec || rec.type === "empty") {
        clipLatestMeta.textContent = trRaw("No content");
        clipLatestView.textContent = trRaw("No content");
        return;
      }
      const t = rec.updated_at || "unknown";
      if (rec.type === "text") {
        clipLatestMeta.textContent = `text | ${t} | ${rec.id || ""}`;
        clipLatestView.innerHTML = `<pre style="margin:0;white-space:pre-wrap;word-break:break-word;">${escapeHtml(rec.text || "")}</pre>`;
        return;
      }
      clipLatestMeta.textContent = `image(${rec.image_filename || "unknown"}) | ${t} | ${rec.id || ""}`;
      clipLatestView.innerHTML = "";
      const img = document.createElement("img");
      img.className = "clip-img";
      img.src = `${rec.image_url || ""}?t=${Date.now()}`;
      clipLatestView.appendChild(img);
    }

    function renderClipHistory(items) {
      const rows = Array.isArray(items) ? items : [];
      clipHistoryMeta.textContent = trRaw(`Total ${rows.length} items`);
      clipHistoryList.innerHTML = "";
      if (!rows.length) {
        clipHistoryList.textContent = trRaw("No history yet");
        return;
      }
      for (const it of rows) {
        const box = document.createElement("div");
        box.className = "clip-item";
        const meta = document.createElement("div");
        meta.className = "clip-meta";
        meta.textContent = `${it.type || "unknown"} | ${it.updated_at || ""} | ${it.id || ""}`;
        box.appendChild(meta);
        if (it.type === "text") {
          const txt = document.createElement("div");
          txt.className = "clip-item-text";
          txt.textContent = it.text || "";
          box.appendChild(txt);
        } else if (it.image_url) {
          const img = document.createElement("img");
          img.className = "clip-img";
          img.src = `${it.image_url}?t=${Date.now()}`;
          box.appendChild(img);
        }
        const row = document.createElement("div");
        row.className = "clip-row";
        row.style.marginTop = "8px";
        const viewBtn = document.createElement("button");
        viewBtn.type = "button";
        viewBtn.className = "secondary";
        viewBtn.textContent = trRaw("View");
        viewBtn.addEventListener("click", () => renderClipLatest(it));
        const delBtn = document.createElement("button");
        delBtn.type = "button";
        delBtn.className = "secondary";
        delBtn.textContent = trRaw("Delete");
        delBtn.addEventListener("click", async () => {
          if (!it.id) return;
          if (!confirm(trRaw("Delete this record?"))) return;
          try {
            const r = await fetch(`/api/history/${encodeURIComponent(it.id)}?id=${encodeURIComponent(clipCurrent)}`, { method: "DELETE" });
            const d = await r.json().catch(() => ({}));
            if (!r.ok) throw new Error(d.error || "Delete failed");
            setClipStatus("Deleted");
            await refreshClipAll();
          } catch (err) {
            setClipStatus(`Delete failed: ${err.message || err}`, true);
          }
        });
        row.appendChild(viewBtn);
        row.appendChild(delBtn);
        box.appendChild(row);
        clipHistoryList.appendChild(box);
      }
    }

    async function loadClipLatest() {
      const d = await getJson(`/api/clip?id=${encodeURIComponent(clipCurrent)}`);
      renderClipLatest(d.clip || { type: "empty" });
      clipRawLink.href = clipUrl("/api/clip/raw");
    }

    async function loadClipHistory() {
      const d = await getJson(`/api/history?id=${encodeURIComponent(clipCurrent)}&limit=200`);
      renderClipHistory(d.items || []);
    }

    async function refreshClipAll() {
      await Promise.all([loadClipLatest(), loadClipHistory()]);
    }

    async function applyClipIdFromInput(showSuccess = false) {
      try {
        clipCurrent = normalizeClipId(clipIdInput.value);
        clipIdInput.value = clipCurrent;
        clipCurrentId.textContent = clipCurrent;
        localStorage.setItem("shareclip_id", clipCurrent);
        await refreshClipAll();
        if (showSuccess) {
          setClipStatus("ID saved and switched");
        }
      } catch (err) {
        setClipStatus(err.message || String(err), true);
      }
    }

    async function handleClipPasteData(cd) {
      const items = Array.from((cd && cd.items) || []);
      const im = items.find((x) => x.type && x.type.startsWith("image/"));
      if (im) {
        const b = im.getAsFile();
        if (b) {
          const ext = (b.type.split("/")[1] || "png").replace("jpeg", "jpg");
          clipCapturedImage = new File([b], `clipboard-${Date.now()}.${ext}`, { type: b.type });
          clipImageInput.value = "";
          setClipStatus("Image captured");
          return;
        }
      }
      const tx = items.find((x) => x.kind === "string" && x.type === "text/plain");
      if (tx) {
        tx.getAsString((v) => {
          clipTextInput.value = v || "";
          clipCapturedImage = null;
          setClipStatus("Text captured");
        });
      }
    }

    async function sendClip() {
      try {
        const fd = new FormData();
        fd.append("id", clipCurrent);
        const file = clipImageInput.files?.[0] || clipCapturedImage;
        const txt = (clipTextInput.value || "").trim();
        if (file) fd.append("image", file, file.name || "clip.png");
        else if (txt) fd.append("text", txt);
        else throw new Error("Please enter text or paste an image first");
        const r = await fetch("/api/clip", { method: "POST", body: fd });
        const d = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(d.error || "Upload failed");
        clipCapturedImage = null;
        clipImageInput.value = "";
        clipTextInput.value = "";
        setClipStatus("Sent");
        renderClipLatest(d.clip);
        await loadClipHistory();
      } catch (err) {
        setClipStatus(`Send failed: ${err.message || err}`, true);
      }
    }

    window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", e => {
      if (!localStorage.getItem("fc-theme")) {
        const newTheme = e.matches ? "dark" : "light";
        applyTheme(newTheme);
      }
    });

    applyTheme(getStoredTheme());

    if (langSelect) {
      const hold = () => pauseRealtime(30000);
      ["mousedown", "focus", "click", "touchstart", "keydown", "pointerdown"].forEach((evt) => {
        langSelect.addEventListener(evt, hold, { passive: true });
      });
      langSelect.addEventListener("change", () => pauseRealtime(8000));
      langSelect.addEventListener("blur", () => pauseRealtime(1200));
    }

    function setStatus(text, isError = false) {
      statusEl.textContent = text;
      statusEl.classList.toggle("err", isError);
      if (monitorStatusEl) {
        monitorStatusEl.textContent = text;
        monitorStatusEl.classList.toggle("err", isError);
      }
      showToast(text, isError ? "error" : "success");
    }

    function switchTab(which) {
      [tabDirBtn, tabMonitorBtn, tabBackupBtn, tabPubBtn].forEach((b) => b.classList.remove("active"));
      [tabDirPanel, tabMonitorPanel, tabBackupPanel, tabPubPanel].forEach((p) => p.classList.remove("active"));
      if (which === "dir") {
        tabDirBtn.classList.add("active");
        tabDirPanel.classList.add("active");
      } else if (which === "backup") {
        tabBackupBtn.classList.add("active");
        tabBackupPanel.classList.add("active");
        loadBackupStatus();
      } else if (which === "pub") {
        tabPubBtn.classList.add("active");
        tabPubPanel.classList.add("active");
      } else {
        tabMonitorBtn.classList.add("active");
        tabMonitorPanel.classList.add("active");
      }
    }

    async function getJson(url, options = {}) {
      const res = await fetch(url, options);
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || "请求失败");
      }
      return data;
    }

    function renderTerminalQuickLink(meta) {
      if (!terminalQuickLink) return;
      const term = meta || {};
      const enabled = term.enabled !== false;
      const host = String(term.host || "").trim();
      const display = String(term.display || "").trim();
      if (enabled && host) {
        terminalQuickLink.href = "/terminal";
        terminalQuickLink.target = "_self";
        terminalQuickLink.rel = "";
        terminalQuickLink.classList.remove("inactive");
      } else {
        terminalQuickLink.href = "/config#terminal";
        terminalQuickLink.target = "_self";
        terminalQuickLink.rel = "";
        terminalQuickLink.classList.add("inactive");
      }
      if (!enabled) {
        terminalQuickLink.title = "Terminal (disabled, click to configure in Config)";
      } else if (!host) {
        terminalQuickLink.title = "Terminal (host not configured, click to configure in Config)";
      } else {
        terminalQuickLink.title = "Web Terminal · " + (display || host);
      }
    }

    function renderDirStats(stats) {
      if (!dirStatsText) return;
      const s = stats || {};
      const files = Number(s.total_files || 0);
      const dirs = Number(s.total_dirs || 0);
      const sizeHuman = String(s.total_size_human || "0B");
      dirStatsText.textContent = `Files ${files} · Dirs ${dirs} · Size ${sizeHuman}`;
    }

    function renderLinks(items) {
      latestLinks = [];
      if (!items.length) {
        bulkText.value = "";
        return;
      }
      for (const item of items) {
        latestLinks.push(item.http_url);
      }
      bulkText.value = latestLinks.join("\\n");
    }

    async function copyTextSmart(text) {
      const value = String(text ?? "");
      if (!value) return false;
      try {
        if (navigator.clipboard && window.isSecureContext) {
          await navigator.clipboard.writeText(value);
          return true;
        }
      } catch (err) {
        // ignore and fallback
      }
      try {
        const ta = document.createElement("textarea");
        ta.value = value;
        ta.setAttribute("readonly", "");
        ta.style.position = "fixed";
        ta.style.top = "-9999px";
        ta.style.left = "-9999px";
        ta.style.opacity = "0";
        document.body.appendChild(ta);
        ta.focus();
        ta.select();
        const ok = document.execCommand("copy");
        document.body.removeChild(ta);
        return !!ok;
      } catch (err) {
        return false;
      }
    }

    async function loadBaseAndDirs(resetDir = false) {
      const base = await getJson("/api/base");
      applyHeroTheme(base.ui_theme || {});
      defaultHttpDir = normalizeDirInput(base.default_http_dir || ".");
      if (resetDir) {
        currentDir = defaultHttpDir;
      }
      storageText.textContent = base.storage_root;
      publicBaseText.textContent = base.public_base_url;
      downloadsEnabled = !!base.downloads_enabled;
      renderTerminalQuickLink(base.terminal || {});
      renderDownloadSwitch();
      currentDirText.textContent = currentDir;
      let dirData;
      try {
        dirData = await getJson(`/api/directories?dir=${encodeURIComponent(currentDir)}`);
      } catch (err) {
        if (resetDir && currentDir !== ".") {
          currentDir = ".";
          currentDirText.textContent = currentDir;
          dirData = await getJson(`/api/directories?dir=${encodeURIComponent(currentDir)}`);
          setStatus("Default目录不可访问，已回退到根目录。", true);
        } else {
          throw err;
        }
      }
      renderDirStats((dirData && dirData.stats) || {});
      dirList.innerHTML = "";
      for (const dir of dirData.directories) {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "dir-item";
        btn.dataset.dir = dir;
        const parts = dir.split("/").filter(Boolean);
        const nameSpan = document.createElement("span");
        nameSpan.className = "dir-name";
        nameSpan.textContent = parts.length ? parts[parts.length - 1] : dir;
        const pathSpan = document.createElement("span");
        pathSpan.className = "dir-path";
        pathSpan.textContent = dir;
        btn.appendChild(nameSpan);
        btn.appendChild(pathSpan);
        btn.title = dir;
        btn.addEventListener("click", () => enterChildDir(dir));
        dirList.appendChild(btn);
      }
      if (!dirData.directories.length) {
        const empty = document.createElement("div");
        empty.className = "muted";
        empty.textContent = "(No subdirectories in current directory)";
        dirList.appendChild(empty);
      }
    }

    function makeSpeedSpan(cls, text, ariaHidden) {
      const el = document.createElement("span");
      el.className = cls;
      if (text != null) el.textContent = text;
      if (ariaHidden) el.setAttribute("aria-hidden", "true");
      return el;
    }
    function makeSpeedSide(arrow, num, unit) {
      const side = document.createElement("span");
      side.className = "speed-side";
      side.appendChild(makeSpeedSpan("speed-arrow", arrow, true));
      side.appendChild(makeSpeedSpan("speed-num", num));
      side.appendChild(makeSpeedSpan("speed-unit", unit));
      return side;
    }
    function renderSpeedValue() {
      if (!speedText) return;
      const isMbps = speedDisplayUnit === "Mbps";
      const unit = isMbps ? "Mbps" : "MiB/s";
      const down = isMbps ? latestTotalDownMbps : latestTotalDownMiBps;
      const up = isMbps ? latestTotalUpMbps : latestTotalUpMiBps;
      while (speedText.firstChild) speedText.removeChild(speedText.firstChild);
      speedText.appendChild(makeSpeedSide("↓", down.toFixed(2), unit));
      speedText.appendChild(makeSpeedSpan("speed-sep", null, true));
      speedText.appendChild(makeSpeedSide("↑", up.toFixed(2), unit));
      speedText.title = `Click to switch units (current ${speedDisplayUnit}）`;
      speedText.style.cursor = "pointer";
    }

    async function loadSpeed() {
      if (!httpModuleOn) {
        speedText.textContent = "-";
        speedText.title = "Click to switch units";
        connText.textContent = "-";
        speedValueReady = false;
        latestTotalDownMiBps = 0;
        latestTotalUpMiBps = 0;
        latestTotalDownMbps = 0;
        latestTotalUpMbps = 0;
        if (sourceSpeedText) sourceSpeedText.textContent = "Per-source throughput unavailable: module disabled";
        return;
      }
      if (isRealtimePaused()) return;
      const reqTs = Date.now();
      try {
        const data = await getJson("/api/speed");
        if (isRealtimePaused() || reqTs < dashboardPauseUntil) return;
        const rxMiBps = Number(data.rx_mibps || 0);
        const rxMbps = Number(data.rx_mbps || 0);
        const txMiBps = Number(data.tx_mibps || 0);
        const txMbps = Number(data.tx_mbps || 0);
        // 按“用户本机视角”显示：下载=本机接收(rx)，上传=本机发送(tx)。
        latestTotalDownMiBps = rxMiBps;
        latestTotalUpMiBps = txMiBps;
        latestTotalDownMbps = rxMbps;
        latestTotalUpMbps = txMbps;
        speedValueReady = true;
        renderSpeedValue();
        renderSourceSpeeds(latestSourceStats);
        connText.textContent = String(data.active_conn_1288);
      } catch (err) {
        speedText.textContent = "Failed";
        speedText.title = "Click to switch units";
        connText.textContent = "-";
        speedValueReady = false;
        latestTotalDownMiBps = 0;
        latestTotalUpMiBps = 0;
        latestTotalDownMbps = 0;
        latestTotalUpMbps = 0;
        if (sourceSpeedText) sourceSpeedText.textContent = "Per-source throughput unavailable";
      }
    }

    function normalizeSourceName(source) {
      const raw = String(source || "").trim();
      if (!raw) return "Direct HTTP";
      const s = raw.toLowerCase();
      if (s.includes("guangya") || s.includes("光鸭") || s.includes("clouddrive") || s.includes("cloud drive")) return "Guangya Drive";
      if (s.includes("aliyun") || s.includes("alipan") || s.includes("阿里")) return "Aliyun Drive";
      if (s.includes("baidu") || s.includes("pan.baidu") || s.includes("xpan") || s.includes("baiduyun") || s.includes("yun.baidu") || s.includes("pcs") || s.includes("百度")) return "Baidu Netdisk";
      if (s.includes("dropbox")) return "Dropbox";
      if (s.includes("mega")) return "MEGA";
      if (s.includes("onedrive")) return "OneDrive";
      if ((s.includes("google") && s.includes("drive")) || s.includes("gdrive")) return "Google Drive";
      if (s === "http-direct" || s === "direct http" || s === "http") return "Direct HTTP";
      return raw;
    }

    const SOURCE_LABEL_TO_KEY = {
      "Baidu Netdisk": "baidu",
      "Aliyun Drive": "ali",
      "Aliyun Netdisk": "ali",
      "Guangya Drive": "guangya",
      "Guangya Netdisk": "guangya",
      "Dropbox": "dropbox",
      "MEGA": "mega",
      "OneDrive": "onedrive",
      "Google Drive": "gdrive",
    };
    function isSourceEnabledByConfig(label) {
      const key = SOURCE_LABEL_TO_KEY[label];
      if (!key) return true;
      const map = (typeof ndEnabledSources === "object" && ndEnabledSources) ? ndEnabledSources : null;
      if (!map) return true;
      return map[key] !== false;
    }
    function makeSourceCard(r) {
      const isActive = r.down > 0 || r.up > 0 || r.count > 0;
      const card = document.createElement("div");
      card.className = "speed-source-card " + (isActive ? "is-active" : "is-zero");
      const name = document.createElement("div");
      name.className = "speed-source-card-name";
      name.textContent = r.name;
      card.appendChild(name);
      const stat = document.createElement("div");
      stat.className = "speed-source-card-stat";
      const mkRate = (arrow, num) => {
        const rate = document.createElement("span");
        rate.className = "speed-source-card-rate";
        const a = document.createElement("span");
        a.className = "speed-source-card-arrow";
        a.setAttribute("aria-hidden", "true");
        a.textContent = arrow;
        const v = document.createElement("span");
        v.className = "speed-source-card-num";
        v.textContent = num;
        rate.appendChild(a);
        rate.appendChild(v);
        return rate;
      };
      stat.appendChild(mkRate("↓", r.down.toFixed(2)));
      stat.appendChild(mkRate("↑", r.up.toFixed(2)));
      if (r.count > 0) {
        const conn = document.createElement("span");
        conn.className = "speed-source-card-conn";
        conn.textContent = "· " + r.count;
        conn.title = r.count + " connection" + (r.count === 1 ? "" : "s");
        stat.appendChild(conn);
      }
      card.appendChild(stat);
      return card;
    }
    function renderSourceSpeeds(sourceStats) {
      if (!sourceSpeedText) return;
      const rows = Array.isArray(sourceStats) ? sourceStats : [];
      const buckets = new Map([
        ["Baidu Netdisk", { down: 0, up: 0, count: 0 }],
        ["Guangya Drive", { down: 0, up: 0, count: 0 }],
        ["Aliyun Drive", { down: 0, up: 0, count: 0 }],
        ["Dropbox", { down: 0, up: 0, count: 0 }],
        ["MEGA", { down: 0, up: 0, count: 0 }],
        ["OneDrive", { down: 0, up: 0, count: 0 }],
        ["Google Drive", { down: 0, up: 0, count: 0 }],
      ]);
      for (const item of rows) {
        const source = normalizeSourceName(item.source);
        const bucket = buckets.get(source);
        if (!bucket) continue;
        bucket.down += Number(item.download_mibps || 0);
        bucket.up += Number(item.upload_mibps || 0);
        bucket.count += Number(item.count || 0);
      }
      let knownDown = 0;
      let knownUp = 0;
      const displayRows = [];
      for (const [name, v] of buckets.entries()) {
        if (!isSourceEnabledByConfig(name)) continue;
        knownDown += v.down;
        knownUp += v.up;
        displayRows.push({ name, down: v.down, up: v.up, count: Math.floor(v.count) });
      }
      const otherDown = Math.max(0, latestTotalDownMiBps - knownDown);
      const otherUp = Math.max(0, latestTotalUpMiBps - knownUp);
      if (otherDown > 0 || otherUp > 0) {
        displayRows.push({ name: "Other sources", down: otherDown, up: otherUp, count: 0 });
      }

      while (sourceSpeedText.firstChild) sourceSpeedText.removeChild(sourceSpeedText.firstChild);
      if (displayRows.length === 0) {
        const empty = document.createElement("div");
        empty.className = "speed-sources-empty";
        empty.textContent = "No netdisks enabled in config";
        sourceSpeedText.appendChild(empty);
        return;
      }
      const wrap = document.createElement("div");
      wrap.className = "speed-sources-cards";
      for (const r of displayRows) wrap.appendChild(makeSourceCard(r));
      sourceSpeedText.appendChild(wrap);
      sourceSpeedText.removeAttribute("title");
    }

    function sortTransfers(items) {
      const rows = [...items];
      const dir = transferSortAscending ? 1 : -1;
      if (transferSortMode === "progress") {
        rows.sort((a, b) => ((a.progress_pct || 0) - (b.progress_pct || 0)) * dir);
        return rows;
      }
      if (transferSortMode === "name") {
        rows.sort((a, b) => {
          const an = String(a.filename || a.relative_path || "");
          const bn = String(b.filename || b.relative_path || "");
          return an.localeCompare(bn, "zh-Hans-CN", { sensitivity: "base" }) * dir;
        });
        return rows;
      }
      if (transferSortMode === "source") {
        rows.sort((a, b) => {
          const as = normalizeSourceName(a.source);
          const bs = normalizeSourceName(b.source);
          const sourceCmp = as.localeCompare(bs, "zh-Hans-CN", { sensitivity: "base" }) * dir;
          if (sourceCmp !== 0) return sourceCmp;
          const an = String(a.filename || a.relative_path || "");
          const bn = String(b.filename || b.relative_path || "");
          return an.localeCompare(bn, "zh-Hans-CN", { sensitivity: "base" }) * dir;
        });
        return rows;
      }
      rows.sort((a, b) => ((a.speed_mibps || 0) - (b.speed_mibps || 0)) * dir);
      return rows;
    }

    function syncTransferSortButtons() {
      for (const btn of xferSortButtons) {
        const mode = btn.dataset.sort || "";
        if (!btn.dataset.baseLabel) {
          btn.dataset.baseLabel = btn.textContent.trim();
        }
        const isActive = mode === transferSortMode;
        btn.classList.toggle("active", isActive);
        const baseLabel = btn.dataset.baseLabel || btn.textContent.trim();
        if (!isActive) {
          btn.textContent = baseLabel;
          continue;
        }
        if (mode === "name" || mode === "source") {
          btn.textContent = `${baseLabel} ${transferSortAscending ? "A-Z" : "Z-A"}`;
        } else {
          btn.textContent = `${baseLabel} ${transferSortAscending ? "↑" : "↓"}`;
        }
      }
    }

    function formatTransferMeta(it) {
      const ip = it.client_ip || "-";
      const sent = it.sent_human || "0B";
      const total = it.total_human || "0B";
      const pct = Math.max(0, Math.min(100, Number(it.progress_pct || 0)));
      const fileTotalBytes = Number(it.file_total_bytes || 0);
      const fileTotalHuman = it.file_total_human || "0B";
      if (it.is_partial && fileTotalBytes > 0) {
        return `${ip} | Chunk ${sent} / ${total} (${pct.toFixed(1)}%) | File total ${fileTotalHuman}`;
      }
      return `${ip} | ${sent} / ${total} | ${pct.toFixed(1)}%`;
    }

    function renderTransfers(data) {
      const prevScrollTop = xferList ? xferList.scrollTop : 0;
      const prevScrollHeight = xferList ? xferList.scrollHeight : 0;
      const prevClientHeight = xferList ? xferList.clientHeight : 0;
      const stickToBottom = prevScrollHeight > 0 && (prevScrollHeight - prevClientHeight - prevScrollTop) <= 2;
      const allItems = Array.isArray(data.items) ? data.items : [];
      let activeItems = allItems.filter((it) => !it.done);
      if (ndActiveTab) {
        const tabSource = ND_ALL_SOURCES.find(s => s.key === ndActiveTab);
        if (tabSource) {
          activeItems = activeItems.filter(it => normalizeSourceName(it.source) === tabSource.label);
        }
      }
      const items = sortTransfers(activeItems);
      const count = Number(data.count || items.length || 0);
      const recentCount = Number(data.recent_count || 0);
      const overall = Number(data.overall_progress_pct || 0);
      xferSummary.textContent = `Active Sessions ${count} · Recently Completed ${recentCount} · Overall Progress ${Math.max(0, Math.min(100, overall)).toFixed(1)}%`;
      xferList.innerHTML = "";
      if (!items.length) {
        const empty = document.createElement("div");
        empty.className = "xfer-item muted";
        empty.textContent = "No active HTTP transfer jobs.";
        xferList.appendChild(empty);
        xferList.scrollTop = 0;
        return;
      }

      const fragment = document.createDocumentFragment();
      for (const it of items) {
        const row = document.createElement("div");
        row.className = "xfer-item";
        row.title = it.relative_path || it.filename || "";
        const main = document.createElement("div");
        main.className = "xfer-main";
        const source = document.createElement("div");
        source.className = "xfer-source";
        source.textContent = normalizeSourceName(it.source);
        const file = document.createElement("div");
        file.className = "xfer-file";
        file.textContent = it.filename || it.relative_path || "(Unknown file)";
        const speed = document.createElement("div");
        speed.className = "xfer-speed";
        speed.textContent = it.done ? "Done" : `${(it.speed_mibps || 0).toFixed(2)} MiB/s`;
        main.appendChild(source);
        main.appendChild(file);
        main.appendChild(speed);
        const meta = document.createElement("div");
        meta.className = "xfer-meta";
        meta.textContent = formatTransferMeta(it);
        row.appendChild(main);
        row.appendChild(meta);
        fragment.appendChild(row);
      }
      xferList.appendChild(fragment);

      if (stickToBottom) {
        xferList.scrollTop = xferList.scrollHeight;
      } else {
        const maxTop = Math.max(0, xferList.scrollHeight - xferList.clientHeight);
        xferList.scrollTop = Math.max(0, Math.min(prevScrollTop, maxTop));
      }
    }

    async function loadTransfers() {
      if (!httpModuleOn) {
        xferSummary.textContent = "Module disabled";
        xferList.innerHTML = "";
        latestTransfers = [];
        latestSourceStats = [];
        latestTransferOverview = { count: 0, recent_count: 0, overall_progress_pct: 0 };
        renderSourceSpeeds(latestSourceStats);
        return;
      }
      if (isRealtimePaused()) return;
      const reqTs = Date.now();
      try {
        const data = await getJson("/api/transfers");
        if (isRealtimePaused() || reqTs < dashboardPauseUntil) return;
        latestTransfers = data.items || [];
        latestSourceStats = data.source_stats || [];
        latestTransferOverview = {
          count: Number(data.count || latestTransfers.length || 0),
          recent_count: Number(data.recent_count || 0),
          overall_progress_pct: Number(data.overall_progress_pct || 0),
        };
        renderSourceSpeeds(latestSourceStats);
        renderTransfers(data);
      } catch (err) {
        xferSummary.textContent = "Active -";
        if (sourceSpeedText) sourceSpeedText.textContent = "Per-source throughput unavailable";
      }
    }

    function renderDownloadSwitch() {
      toggleDownloadBtn.textContent = httpAccessPublic ? "Lan+Wan" : "Lan";
      toggleDownloadBtn.className = httpAccessPublic ? "" : "secondary";
      toggleDownloadBtn.title = httpAccessPublic ? "WAN mode (Public)" : "LAN mode (LAN-only)";
    }

    function trRaw(src) {
      try {
        if (window.fccI18n && typeof window.fccI18n.translateRaw === "function") {
          return window.fccI18n.translateRaw(src) || src;
        }
      } catch (e) {}
      return src;
    }

    function svcText(svc) {
      if (!svc) return '<span class="svc-dot bad"></span>' + trRaw("Unknown");
      const isActive = svc.active_state === "active";
      const mark = trRaw(isActive ? "Running" : "Stopped");
      const unit = trRaw(String(svc.unit || "-"));
      const dotClass = isActive ? "ok" : "bad";
      if (svc.detail) {
        const detail = trRaw(String(svc.detail));
      const isBt = /Seeding|Downloading|DHT|Connect|Connections|↓|↑/.test(detail) || /qBittorrent|BitTorrent/i.test(unit);
        const detailHtml = isBt ? formatBtDetail(detail) : escapeHtml(String(detail));
        return '<span class="svc-dot ' + dotClass + '"></span>' + mark + ' | ' + escapeHtml(String(unit)) + '<br><span class="svc-meta" style="font-size:12px; line-height:1.4;">' + detailHtml + '</span>';
      }
      return '<span class="svc-dot ' + dotClass + '"></span>' + mark + ' | ' + escapeHtml(String(unit));
    }

    function formatBtDetail(detail) {
      const text = String(detail || "");
      const chunks = text.split("|").map((x) => x.trim()).filter(Boolean);
      if (!chunks.length) return escapeHtml(text);
      const speedRaw = chunks.shift() || "";
      const speedHtml = speedRaw
        .replace(/↓\s*([^·|]+)/, '<span class="bt-down">↓ $1</span>')
        .replace(/↑\s*([^·|]+)/, '<span class="bt-up">↑ $1</span>')
        .replace(/·/g, '<span class="bt-sep">·</span>');
      const statsHtml = chunks.map((s) => {
        const m = s.match(/^([A-Za-z]+)\s+(.+)$/);
        if (!m) return `<span class="bt-pill">${escapeHtml(s)}</span>`;
        return `<span class="bt-pill"><span class="k">${escapeHtml(m[1])}</span> <span class="v">${escapeHtml(m[2])}</span></span>`;
      }).join("");
      return `<div class="bt-speed-row">${speedHtml}</div><div class="bt-stat-row">${statsHtml}</div>`;
    }

    function btClientLabel(key) {
      const map = {
        qbittorrent: "qBittorrent",
        deluge: "Deluge",
        transmission: "Transmission",
        rtorrent: "rTorrent",
      };
      return map[String(key || "").toLowerCase()] || String(key || "");
    }

    function btEnabledClients() {
      const out = [];
      const order = Array.isArray(btHomepageOrder) ? btHomepageOrder : ["qbittorrent", "deluge", "transmission", "rtorrent"];
      for (const k of order) {
        if (btHomepageEnabled && btHomepageEnabled[k]) out.push(k);
      }
      return out;
    }

    function ddnsSyncSummary(ddnsSvc) {
      const domains = Array.isArray(ddnsSvc && ddnsSvc.sync_domains) ? ddnsSvc.sync_domains : [];
      const cleaned = [];
      for (const x of domains) {
        const v = String(x || "").trim();
        if (v && !cleaned.includes(v)) cleaned.push(v);
      }
      if (cleaned.length) {
        if (cleaned.length <= 3) return cleaned.join(", ");
        return cleaned.slice(0, 3).join(", ") + ` (+${cleaned.length - 3})`;
      }
      const detail = String((ddnsSvc && ddnsSvc.detail) || "").trim();
      return detail ? detail : "-";
    }

    function formatByteRate(bps) {
      let n = Math.max(0, Number(bps || 0));
      const units = ["B", "KB", "MB", "GB", "TB"];
      let idx = 0;
      while (n >= 1024 && idx < units.length - 1) {
        n = n / 1024;
        idx += 1;
      }
      return (n >= 100 || idx === 0 ? n.toFixed(0) : n.toFixed(1)) + units[idx];
    }

    function buildBtOverallQbt(clientMap) {
      const keys = Object.keys(clientMap || {});
      if (!keys.length) return null;
      let activeAny = false;
      let dl = 0;
      let up = 0;
      let seeding = 0;
      let downloading = 0;
      let active = 0;
      let total = 0;
      let peers = 0;
      let dht = 0;
      for (const k of keys) {
        const svc = clientMap[k] || {};
        if (svc.active_state === "active") activeAny = true;
        const st = svc.stats || {};
        dl += Number(st.dl_bps || 0);
        up += Number(st.up_bps || 0);
        seeding += Number(st.seeding || 0);
        downloading += Number(st.downloading || 0);
        active += Number(st.active || 0);
        total += Number(st.total || 0);
        peers += Number(st.peers || 0);
        dht += Number(st.dht_nodes || 0);
      }
      const detail = `↓ ${formatByteRate(dl)}/s · ↑ ${formatByteRate(up)}/s | Seeding ${seeding} · Downloading ${downloading} · Active ${active} · Total ${total}` +
        (peers > 0 ? ` · Connections ${peers}` : "") +
        (dht > 0 ? ` · DHT ${dht}` : "");
      return {
        unit: "BitTorrent overall",
        active_state: activeAny ? "active" : "inactive",
        detail: detail,
      };
    }

    function renderBtClientTabs() {
      if (!qbtClientTabBarWrap) return;
      const keys = btEnabledClients();
      if (!keys.length) {
        qbtClientTabBarWrap.innerHTML = "";
        qbtClientTabBarWrap.style.display = "none";
        return;
      }
      qbtClientTabBarWrap.style.display = "flex";
      const tabKeys = keys.length > 1 ? ["overall"].concat(keys) : keys.slice();
      if (!tabKeys.includes(btActiveClient)) btActiveClient = tabKeys[0];
      const bar = document.createElement("div");
      bar.className = "xfer-sort-group";
      for (const k of tabKeys) {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "xfer-sort-btn" + (k === btActiveClient ? " active" : "");
        btn.textContent = k === "overall" ? "Overall" : btClientLabel(k);
        btn.addEventListener("click", async () => {
          if (btActiveClient === k) return;
          btActiveClient = k;
          renderBtClientTabs();
          await loadControlStatus();
        });
        bar.appendChild(btn);
      }
      qbtClientTabBarWrap.innerHTML = "";
      qbtClientTabBarWrap.appendChild(bar);
    }

    function renderControlStatus(data, btClientStatusMap) {
      sysStatus.className = "sys-strip";
      const s = data.system || {};
      const cpuText = `CPU Load (1m): ${Number(s.load1 || 0).toFixed(2)}`;
      const restText = `Memory: ${s.mem_used_human || "-"} / ${s.mem_total_human || "-"} | Disk: ${s.disk_used_human || "-"} / ${s.disk_total_human || "-"} | Uptime: ${s.uptime_human || "-"}`;
      sysStatus.innerHTML = `<div class="sys-status-line">${cpuText}</div><div class="sys-status-line">${restText}</div>`;
      const btMap = btClientStatusMap || {};
      const btOverall = buildBtOverallQbt(btMap);
      let qbtSvc = data.qbt;
      if (btActiveClient === "overall" && btOverall) {
        qbtSvc = btOverall;
      } else if (btMap[btActiveClient]) {
        qbtSvc = btMap[btActiveClient];
      }
      qbtStatusText.innerHTML = svcText(qbtSvc);
      ddnsStatusText.innerHTML = svcText(data.ddns);
      selfStatusText.innerHTML = svcText(data.self);
      renderHttpAccess(data.http_access);
      const appCfg = data.app_config || {};
      const qbtCfg = appCfg.qbt || {};
      const en = qbtCfg.homepage_clients_enabled || {};
      btHomepageEnabled = {
        qbittorrent: en.qbittorrent !== false,
        deluge: !!en.deluge,
        transmission: !!en.transmission,
        rtorrent: !!en.rtorrent,
      };
      const od = Array.isArray(qbtCfg.homepage_clients_order) ? qbtCfg.homepage_clients_order : [];
      const allowed = ["qbittorrent", "deluge", "transmission", "rtorrent"];
      const outOrder = [];
      for (const x of od) {
        const k = String(x || "").toLowerCase();
        if (allowed.includes(k) && !outOrder.includes(k)) outOrder.push(k);
      }
      for (const k of allowed) if (!outOrder.includes(k)) outOrder.push(k);
      btHomepageOrder = outOrder;
      if (qbtCfg.client) btActiveClient = String(qbtCfg.client).toLowerCase();
      renderBtClientTabs();
      if (ddnsDomainText) ddnsDomainText.textContent = "Sync Domains: " + ddnsSyncSummary(data.ddns);
      const mods = appCfg.modules || {};
      const showQbtModule = mods.qbt !== false;
      const showDdnsModule = mods.ddns !== false;
      const showShareclipModule = mods.shareclip !== false;
      const showHttpModule = mods.http !== false;
      httpModuleOn = !!showHttpModule;
      const qbtSvcCard = document.getElementById("qbtSvcCard");
      const btEnabledCount = btEnabledClients().length;
      if (qbtSvcCard) qbtSvcCard.style.display = (showQbtModule && btEnabledCount > 0) ? "" : "none";
      if (tabPubBtn) tabPubBtn.style.display = showShareclipModule ? "" : "none";
      if (tabPubPanel) tabPubPanel.style.display = showShareclipModule ? "" : "none";
      if (httpSvcCard) httpSvcCard.style.display = showHttpModule ? "" : "none";
      if (httpSpeedCard) httpSpeedCard.style.display = showHttpModule ? "" : "none";
      if (!showShareclipModule && tabPubBtn && tabPubBtn.classList.contains("active")) {
        switchTab("monitor");
      }
      const ndCfg = appCfg.netdisk_sources || {};
      const prevEnabled = JSON.stringify(ndEnabledSources);
      ndEnabledSources = ndCfg;
      if (JSON.stringify(ndEnabledSources) !== prevEnabled) {
        const enabledKeys = {};
        ndGetEnabledList().forEach(s => { enabledKeys[s.key] = true; });
        if (ndActiveTab && !enabledKeys[ndActiveTab]) ndActiveTab = "";
        ndRenderTabs();
      }
      ndUpdateSectionTitles();
      const qbtActive = qbtSvc && qbtSvc.active_state === "active";
      qbtControlOn = !!qbtActive;
      const ddnsBuiltin = data.ddns && data.ddns.source === "builtin";
      const ddnsActive = ddnsBuiltin ? !!data.ddns.enabled : (data.ddns && data.ddns.active_state === "active");
      ddnsControlOn = !!ddnsActive;
      const qbtStartBtn = document.getElementById("qbtStartBtn");
      const qbtStopBtn = document.getElementById("qbtStopBtn");
      if (qbtStartBtn) qbtStartBtn.disabled = qbtActive;
      if (qbtStopBtn) qbtStopBtn.disabled = !qbtActive;
      document.getElementById("ddnsToggleBtn").textContent = trRaw(ddnsActive ? "Stop" : "Start");
      const rbtn = document.getElementById("ddnsRestartBtn");
      if (rbtn) rbtn.textContent = trRaw((data.ddns && data.ddns.source === "builtin") ? "Sync now" : "Restart");
      // 内置 DDNS 有配置就显示卡片；外部 DDNS 也显示
      const ddnsSvcCard = document.getElementById("ddnsSvcCard");
      if (ddnsSvcCard) {
        const builtinConfigured = data.ddns && data.ddns.source === "builtin";
        const externalDdns = data.ddns && data.ddns.source !== "builtin";
        ddnsSvcCard.style.display = (showDdnsModule && (builtinConfigured || externalDdns)) ? "" : "none";
      }
    }

    async function loadControlStatus() {
      if (isRealtimePaused()) return;
      const reqTs = Date.now();
      try {
        const activeClients = btEnabledClients();
        const selectedClient = (btActiveClient && btActiveClient !== "overall") ? btActiveClient : (activeClients[0] || "qbittorrent");
        const statusUrl = activeClients.length
          ? ("/api/control/status?client=" + encodeURIComponent(selectedClient))
          : "/api/control/status";
        const data = await getJson(statusUrl);
        const btClientStatusMap = {};
        if (selectedClient) btClientStatusMap[selectedClient] = data.qbt;
        if (activeClients.length > 1) {
          const pending = activeClients
            .filter((k) => k !== selectedClient)
            .map(async (k) => {
              const d = await getJson("/api/control/status?client=" + encodeURIComponent(k));
              btClientStatusMap[k] = d.qbt;
            });
          await Promise.allSettled(pending);
        }
        if (isRealtimePaused() || reqTs < dashboardPauseUntil) return;
        renderControlStatus(data, btClientStatusMap);
      } catch (err) {
        sysStatus.className = "sys-strip";
        sysStatus.innerHTML = `<div class="sys-status-line" style="color:var(--danger);">Status fetch failed: ${err.message}</div>`;
      }
    }

    async function controlService(service, action) {
      try {
        const data = await getJson("/api/control/service", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ service, action, client: (btActiveClient && btActiveClient !== "overall") ? btActiveClient : (btEnabledClients()[0] || "qbittorrent") }),
        });
        if (service === "self" && action === "restart") {
          setStatus("已发送Restart命令，服务即将Restart。");
          setTimeout(loadControlStatus, 1500);
          return;
        }
        renderControlStatus(data);
        setStatus(`${service} 已执行 ${action}`);
      } catch (err) {
        setStatus(`操作失败：${err.message}`, true);
      }
    }

    function qbtConfirmAction(action) {
      if (action === "stop") {
        return confirm(trRaw("Confirm stop qBittorrent? Active tasks may be interrupted."));
      }
      if (action === "restart") {
        return confirm(trRaw("Confirm restart qBittorrent? Active tasks may be interrupted."));
      }
      return true;
    }

    async function listLinks() {
      setStatus(`正在扫描目录：${currentDir}`);
      try {
        const data = await getJson(`/api/files?dir=${encodeURIComponent(currentDir)}`);
        renderLinks(data.items);
        setStatus(`共找到 ${data.items.length} 个文件`);
      } catch (err) {
        setStatus(err.message, true);
      }
    }

    async function enterChildDir(child) {
      if (!child) {
        setStatus("当前目录没有可进入的子目录", true);
        return;
      }
      currentDir = child;
      await loadBaseAndDirs(false);
      setStatus(`已进入目录：${currentDir}`);
    }

    function normalizeDirInput(raw) {
      let v = (raw || "").trim().replaceAll("\\\\", "/");
      if (!v || v === "/") return ".";
      if (v.startsWith("/")) v = v.slice(1);
      while (v.endsWith("/") && v !== ".") v = v.slice(0, -1);
      return v || ".";
    }

    async function goParentDir() {
      if (currentDir === ".") {
        setStatus("已在根目录");
        return;
      }
      const parts = currentDir.split("/").filter(Boolean);
      parts.pop();
      currentDir = parts.length ? parts.join("/") : ".";
      await loadBaseAndDirs(false);
      setStatus(`已返回目录：${currentDir}`);
    }

    async function copyAllLinks() {
      if (!latestLinks.length) {
        setStatus("没有可复制的链接，请先生成", true);
        return;
      }
      const text = latestLinks.join("\\n");
      const ok = await copyTextSmart(text);
      if (ok) {
        setStatus(`已复制 ${latestLinks.length} 条链接`);
        return;
      }
      bulkText.focus();
      bulkText.select();
      setStatus("复制失败：已帮你选中批量文本，请按 Cmd/Ctrl+C", true);
    }

    async function copyCurrentDirName() {
      const parts = currentDir.split("/").filter(Boolean);
      if (!parts.length) {
        setStatus("当前是根目录，目录名为空", true);
        return;
      }
      const dirName = parts[parts.length - 1];
      const ok = await copyTextSmart(dirName);
      if (ok) {
        setStatus(`已复制目录名：${dirName}`);
        return;
      }
      bulkText.value = dirName;
      bulkText.focus();
      bulkText.select();
      setStatus("复制失败：已将目录名填入输入框并选中，请按 Cmd/Ctrl+C", true);
    }

    async function runCleanPreview() {
      const st = document.getElementById("cleanStatus");
      const prev = document.getElementById("cleanPreview");
      const sub = document.getElementById("cleanSubstrings");
      const applyBtn = document.getElementById("cleanApplyBtn");
      lastCleanMoves = null;
      applyBtn.disabled = true;
      st.className = "status-bar muted";
      st.textContent = "Previewing...";
      prev.style.display = "none";
      try {
        const data = await getJson("/api/clean/preview", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            dir: currentDir,
            remove_substrings: sub.value,
            strip_cjk: document.getElementById("cleanStripCjk").checked,
            move_season_before_year: document.getElementById("cleanMoveSeason").checked,
            target: document.getElementById("cleanTarget").value,
            recursive: document.getElementById("cleanRecursive").checked,
          }),
        });
        const moves = data.moves || [];
        lastCleanMoves = moves.filter((m) => !m.skip);
        if (!moves.length) {
          st.textContent = "No changes: no items need rename under current rules.";
          return;
        }
        const bad = moves.filter((m) => m.skip);
        prev.innerHTML = moves
          .map(
            (m) =>
              `<div class="clean-row"><div>${m.old_rel}</div><div>${
                m.error ? "跳过: " + m.error : m.new_rel
              }</div></div>`
          )
          .join("");
        prev.style.display = "block";
        st.textContent = `Total ${moves.length} items, executable ${lastCleanMoves.length} items${
          bad.length ? "，" + bad.length + " items冲突" : ""
        }。`;
        applyBtn.disabled = lastCleanMoves.length === 0;
      } catch (e) {
        st.className = "status-bar err";
        st.textContent = "Preview failed: " + e.message;
      }
    }

    async function runCleanApply() {
      if (!lastCleanMoves || !lastCleanMoves.length) return;
      if (!confirm("Apply preview rename for " + lastCleanMoves.length + " items? This action cannot be auto-reverted.")) {
        return;
      }
      const st = document.getElementById("cleanStatus");
      st.className = "status-bar muted";
      st.textContent = "Applying...";
      try {
        const data = await getJson("/api/clean/apply", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            moves: lastCleanMoves.map((m) => ({ old_rel: m.old_rel, new_rel: m.new_rel })),
          }),
        });
        const results = data.results || [];
        const okN = results.filter((r) => r.ok === "true").length;
        st.textContent = "Done: success " + okN + ", failed " + (results.length - okN) + ".";
        if (okN) showToast("已重命名 " + okN + " items", "success");
        lastCleanMoves = null;
        document.getElementById("cleanApplyBtn").disabled = true;
        await loadBaseAndDirs(false);
      } catch (e) {
        st.className = "status-bar err";
        st.textContent = "Apply failed: " + e.message;
      }
    }

    function switchCleanMode(mode) {
      const m = String(mode || "rename");
      const isSubtitle = m === "subtitle";
      if (cleanRenamePanel) cleanRenamePanel.style.display = isSubtitle ? "none" : "";
      if (cleanSubtitlePanel) cleanSubtitlePanel.style.display = isSubtitle ? "" : "none";
      if (cleanModeRenameBtn) cleanModeRenameBtn.className = isSubtitle ? "tab-btn" : "tab-btn active";
      if (cleanModeSubtitleBtn) cleanModeSubtitleBtn.className = isSubtitle ? "tab-btn active" : "tab-btn";
    }

    async function runSubtitleAlignPreview() {
      if (!subtitleAlignStatus || !subtitleAlignPreview || !subtitleAlignApplyBtn) return;
      subtitleAlignStatus.className = "status-bar muted";
      subtitleAlignStatus.textContent = "Previewing align...";
      subtitleAlignPreview.style.display = "none";
      subtitleAlignPreview.innerHTML = "";
      subtitleAlignApplyBtn.disabled = true;
      lastSubtitleAlignMoves = null;
      try {
        const data = await getJson("/api/subtitle-align/preview", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            dir: currentDir,
            recursive: !!(subtitleAlignRecursive && subtitleAlignRecursive.checked),
          }),
        });
        const moves = data.moves || [];
        const runnable = moves.filter((m) => !m.skip && m.old_rel !== m.new_rel);
        const skipped = moves.filter((m) => !!m.skip);
        lastSubtitleAlignMoves = runnable;
        if (!moves.length) {
          subtitleAlignStatus.textContent = "No subtitle rename needed.";
          return;
        }
        subtitleAlignPreview.innerHTML = moves.map((m) => {
          const fromText = escapeHtml(String(m.old_rel || ""));
          if (m.skip) {
            const reason = escapeHtml(String(m.error || "not match"));
            return `<div class="sub-align-row is-skip"><div class="sub-align-src">${fromText}</div><div class="sub-align-arrow">skip</div><div class="sub-align-dst">${reason}</div></div>`;
          }
          const toText = escapeHtml(String(m.new_rel || ""));
          return `<div class="sub-align-row"><div class="sub-align-src">${fromText}</div><div class="sub-align-arrow">to</div><div class="sub-align-dst">${toText}</div></div>`;
        }).join("");
        subtitleAlignPreview.style.display = "block";
        subtitleAlignStatus.textContent = `Total ${moves.length}, executable ${runnable.length}, skipped ${skipped.length}.`;
        subtitleAlignApplyBtn.disabled = runnable.length === 0;
      } catch (e) {
        subtitleAlignStatus.className = "status-bar err";
        subtitleAlignStatus.textContent = "Preview failed: " + e.message;
      }
    }

    async function runSubtitleAlignApply() {
      if (!subtitleAlignStatus || !subtitleAlignApplyBtn) return;
      if (!lastSubtitleAlignMoves || !lastSubtitleAlignMoves.length) return;
      if (!confirm("Apply subtitle align for " + lastSubtitleAlignMoves.length + " items?")) return;
      subtitleAlignStatus.className = "status-bar muted";
      subtitleAlignStatus.textContent = "Applying align...";
      try {
        const data = await getJson("/api/subtitle-align/apply", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            moves: lastSubtitleAlignMoves.map((m) => ({ old_rel: m.old_rel, new_rel: m.new_rel })),
          }),
        });
        const rows = data.results || [];
        const okN = rows.filter((x) => x.ok === "true").length;
        subtitleAlignStatus.textContent = "Done: success " + okN + ", failed " + (rows.length - okN) + ".";
        subtitleAlignApplyBtn.disabled = true;
        lastSubtitleAlignMoves = null;
        if (okN) {
          showToast("字幕对齐完成 " + okN + " items", "success");
          await loadBaseAndDirs(false);
        }
      } catch (e) {
        subtitleAlignStatus.className = "status-bar err";
        subtitleAlignStatus.textContent = "Apply failed: " + e.message;
      }
    }

    function readFileAsBase64(file) {
      return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onerror = () => reject(new Error("Failed to read " + file.name));
        reader.onload = () => {
          const text = String(reader.result || "");
          const idx = text.indexOf(",");
          resolve(idx >= 0 ? text.slice(idx + 1) : text);
        };
        reader.readAsDataURL(file);
      });
    }

    function renderSubtitleUploadResult(data) {
      if (!subtitleUploadResult) return;
      subtitleUploadResult.style.display = "none";
      subtitleUploadResult.innerHTML = "";
    }

    async function uploadSubtitles() {
      if (!subtitleUploadInput || !subtitleUploadBtn || !subtitleUploadStatus) return;
      const files = Array.from(subtitleUploadInput.files || []);
      if (!files.length) {
        subtitleUploadStatus.className = "status-bar err";
        subtitleUploadStatus.textContent = "Select subtitle files or archives first.";
        return;
      }
      subtitleUploadBtn.disabled = true;
      subtitleUploadStatus.className = "status-bar muted";
      subtitleUploadStatus.textContent = "Reading files...";
      if (subtitleUploadResult) {
        subtitleUploadResult.style.display = "none";
        subtitleUploadResult.innerHTML = "";
      }
      try {
        const payloadFiles = [];
        for (const f of files) {
          payloadFiles.push({
            name: f.name,
            size: f.size,
            content_b64: await readFileAsBase64(f),
          });
        }
        subtitleUploadStatus.textContent = "Uploading...";
        const data = await getJson("/api/subtitles/upload", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ dir: currentDir, files: payloadFiles }),
        });
        renderSubtitleUploadResult(data);
        subtitleUploadStatus.className = data.failed_count ? "status-bar err" : "status-bar muted";
        subtitleUploadStatus.textContent = "Done: success " + (data.success_count || 0) + ", failed " + (data.failed_count || 0) + ".";
        if (data.success_count) {
          showToast("已上传/解压字幕 " + data.success_count + " items", "success");
          await loadBaseAndDirs(false);
        }
      } catch (e) {
        subtitleUploadStatus.className = "status-bar err";
        subtitleUploadStatus.textContent = "Upload failed: " + e.message;
      } finally {
        subtitleUploadBtn.disabled = false;
      }
    }

    async function toggleDownloads() {
      const targetPublic = !httpAccessPublic;
      try {
        const sel = document.getElementById("httpAccessDuration");
        let dur = sel ? parseInt(sel.value, 10) : 28800;
        if (!dur || dur <= 0) dur = lastTimedDurationSec || 28800;
        const data = await getJson("/api/control/http-access", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(
            targetPublic
              ? { action: "open_public", duration_sec: dur }
              : { action: "close" }
          ),
        });
        if (!targetPublic) {
          try {
            await getJson("/api/control/downloads", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ enabled: false }),
            });
          } catch (_e) {}
        }
        renderHttpAccess(data);
        renderDownloadSwitch();
        setStatus(targetPublic ? "已切换到 WAN (Public) 模式" : "已切换到 LAN-only 模式");
      } catch (err) {
        setStatus(`切换失败：${err.message}`, true);
      }
    }

    function renderHttpAccess(ha) {
      if (!httpAccessText) return;
      ha = ha || {};
      lastHttpAccessState = ha;
      const eff = ha.effective_mode || "lan_only";
      let label;
      if (eff === "public") {
        label = "Public";
      } else if (eff === "limited") {
        label = "Limited (" + Number(ha.allowlist_count || 0) + " allowed)";
      } else {
        label = "LAN-only";
      }
      httpAccessPublic = eff === "public";
      const persistent = !!ha.public_persistent;
      httpPublicPersistent = persistent;
      const secs = Math.max(0, Number(ha.public_seconds_remaining || 0));
      const h = Math.floor(secs / 3600);
      const m = Math.floor((secs % 3600) / 60);
      const timerText = (h > 0 ? h + "h " : "") + m + "m";
      if (eff === "public") {
        const durationText = persistent ? "No Duration" : timerText;
        httpAccessText.textContent = "File Access: Public · Duration: " + durationText;
      } else {
        httpAccessText.textContent = "File Access: " + label;
      }
      if (httpAccessDuration) httpAccessDuration.disabled = persistent;
      if (httpAccessDuration) {
        if (persistent) {
          if (httpNoDurationOption) httpNoDurationOption.hidden = false;
          httpAccessDuration.value = "0";
          httpAccessDuration.title = "No Duration";
        } else if (eff === "public" && secs > 0) {
          if (httpNoDurationOption) httpNoDurationOption.hidden = true;
          if (httpAccessDuration.value === "0") httpAccessDuration.value = "28800";
          if (httpAccessDuration.value && httpAccessDuration.value !== "0") {
            lastTimedDurationSec = parseInt(httpAccessDuration.value, 10) || lastTimedDurationSec;
          }
          httpAccessDuration.title = "Ends in " + timerText;
        } else {
          if (httpNoDurationOption) httpNoDurationOption.hidden = true;
          if (httpAccessDuration.value === "0") httpAccessDuration.value = "28800";
          if (httpAccessDuration.value && httpAccessDuration.value !== "0") {
            lastTimedDurationSec = parseInt(httpAccessDuration.value, 10) || lastTimedDurationSec;
          }
          httpAccessDuration.title = "Select timer duration";
        }
      }
      if (httpAccessAlwaysBtn) {
        httpAccessAlwaysBtn.classList.toggle("is-active", persistent);
        httpAccessAlwaysBtn.textContent = persistent ? "Persistent" : "Timed";
        httpAccessAlwaysBtn.title = persistent ? "Persistent public access mode" : "Timed public access mode";
      }
      renderDownloadSwitch();
    }

    async function openHttpWindow() {
      const sel = document.getElementById("httpAccessDuration");
      const dur = sel ? parseInt(sel.value, 10) : 28800;
      if (!dur || dur <= 0) return;
      lastTimedDurationSec = dur;
      try {
        const data = await getJson("/api/control/http-access", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ action: "open_public", duration_sec: dur }),
        });
        renderHttpAccess(data);
        setStatus("公网访问窗口已开启");
      } catch (err) {
        setStatus(`开启失败：${err.message}`, true);
      }
    }

    async function openHttpAlways() {
      const wasPublic = !!httpAccessPublic;
      const wasPersistent = !!httpPublicPersistent;
      if (httpAccessAlwaysBtn) httpAccessAlwaysBtn.disabled = true;
      try {
        if (!wasPublic) {
          setStatus("Enable Public mode first, then switch Timed/Persistent.", true);
          return;
        }
        const sel = document.getElementById("httpAccessDuration");
        let dur = sel ? parseInt(sel.value, 10) : 28800;
        if (!dur || dur <= 0) dur = lastTimedDurationSec || 28800;
        const action = wasPersistent ? "open_public" : "open_public_persistent";
        const data = await getJson("/api/control/http-access", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(
            action === "open_public"
              ? { action: action, duration_sec: dur }
              : { action: action }
          ),
        });
        renderHttpAccess(data);
        if (wasPersistent) {
          setStatus("已切换为定时 Public 模式");
        } else {
          setStatus("已切换为无限期 Public 模式");
        }
      } catch (err) {
        setStatus(`切换失败：${err.message}`, true);
      } finally {
        if (httpAccessAlwaysBtn) httpAccessAlwaysBtn.disabled = false;
      }
    }

    async function restartService() {
      const restartConfirmText = (window.fccI18n && typeof window.fccI18n.translateRaw === "function")
        ? (window.fccI18n.translateRaw("确认Restart Service？这会中断当前所有上传Connect。") || "确认Restart Service？这会中断当前所有上传Connect。")
        : "确认Restart Service？这会中断当前所有上传Connect。";
      if (!confirm(restartConfirmText)) {
        return;
      }
      try {
        await getJson("/api/control/restart", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ reason: "manual-ui" }),
        });
        setStatus("已发送Restart命令，当前上传Connect会被中断。");
      } catch (err) {
        setStatus(`Restart失败：${err.message}`, true);
      }
    }

    document.getElementById("refreshBtn").addEventListener("click", () => loadBaseAndDirs(false));
    document.getElementById("backBtn").addEventListener("click", goParentDir);
    document.getElementById("listBtn").addEventListener("click", listLinks);
    document.getElementById("copyBtn").addEventListener("click", copyAllLinks);
    document.getElementById("copyDirNameBtn").addEventListener("click", copyCurrentDirName);
    document.getElementById("cleanPreviewBtn").addEventListener("click", runCleanPreview);
    document.getElementById("cleanApplyBtn").addEventListener("click", runCleanApply);
    if (cleanModeRenameBtn) cleanModeRenameBtn.addEventListener("click", () => switchCleanMode("rename"));
    if (cleanModeSubtitleBtn) cleanModeSubtitleBtn.addEventListener("click", () => switchCleanMode("subtitle"));
    if (subtitleAlignPreviewBtn) subtitleAlignPreviewBtn.addEventListener("click", runSubtitleAlignPreview);
    if (subtitleAlignApplyBtn) subtitleAlignApplyBtn.addEventListener("click", runSubtitleAlignApply);
    if (subtitleUploadBtn) subtitleUploadBtn.addEventListener("click", uploadSubtitles);
    document.getElementById("toggleDownloadBtn").addEventListener("click", toggleDownloads);
    document.getElementById("restartServiceBtn").addEventListener("click", restartService);
    if (httpAccessDuration) httpAccessDuration.addEventListener("change", openHttpWindow);
    if (httpAccessAlwaysBtn) httpAccessAlwaysBtn.addEventListener("click", openHttpAlways);
    document.getElementById("qbtStartBtn").addEventListener("click", () => {
      controlService("qbt", "start");
    });
    document.getElementById("qbtStopBtn").addEventListener("click", () => {
      if (!qbtConfirmAction("stop")) return;
      controlService("qbt", "stop");
    });
    document.getElementById("qbtRestartBtn").addEventListener("click", () => {
      if (!qbtConfirmAction("restart")) return;
      controlService("qbt", "restart");
    });
    document.getElementById("ddnsToggleBtn").addEventListener("click", () => {
      controlService("ddns", ddnsControlOn ? "stop" : "start");
    });
    document.getElementById("ddnsRestartBtn").addEventListener("click", () => controlService("ddns", "restart"));
    document.getElementById("themeToggleBtn").addEventListener("click", toggleTheme);
    switchCleanMode("rename");
    document.getElementById("openPubNewBtn").addEventListener("click", () => {
      window.open("/?id=pub", "_blank", "noopener,noreferrer");
    });
    document.getElementById("clipSendBtn").addEventListener("click", sendClip);
    document.getElementById("clipReadBtn").addEventListener("click", async () => {
      if (!navigator.clipboard || !navigator.clipboard.read) {
        setClipStatus("Clipboard read API is not supported by this browser", true);
        return;
      }
      try {
        const items = await navigator.clipboard.read();
        for (const it of items) {
          const t = it.types.find((x) => x.startsWith("image/"));
          if (t) {
            const b = await it.getType(t);
            const ext = (t.split("/")[1] || "png").replace("jpeg", "jpg");
            clipCapturedImage = new File([b], `clipboard-${Date.now()}.${ext}`, { type: t });
            clipImageInput.value = "";
            setClipStatus("Image read from system clipboard");
            return;
          }
          if (it.types.includes("text/plain")) {
            const b = await it.getType("text/plain");
            clipTextInput.value = await b.text();
            clipCapturedImage = null;
            setClipStatus("Text read from system clipboard");
            return;
          }
        }
        setClipStatus("No usable content in clipboard", true);
      } catch (err) {
        setClipStatus("Clipboard read failed: " + (err.message || err), true);
      }
    });
    document.getElementById("clipRefreshLatestBtn").addEventListener("click", () => loadClipLatest().catch((err) => setClipStatus(err.message || String(err), true)));
    document.getElementById("clipRefreshHistoryBtn").addEventListener("click", () => loadClipHistory().catch((err) => setClipStatus(err.message || String(err), true)));
    clipPasteZone.addEventListener("paste", (e) => {
      e.preventDefault();
      handleClipPasteData(e.clipboardData).catch((err) => setClipStatus(err.message || String(err), true));
    });
    clipTextInput.addEventListener("paste", (e) => {
      handleClipPasteData(e.clipboardData).catch((err) => setClipStatus(err.message || String(err), true));
    });
    clipPasteZone.addEventListener("click", () => clipPasteZone.focus());
    clipIdInput.addEventListener("keydown", (event) => {
      if (event.key === "Enter") applyClipIdFromInput(true);
    });
    clipIdInput.addEventListener("change", () => applyClipIdFromInput(false));
    tabDirBtn.addEventListener("click", () => switchTab("dir"));
    tabMonitorBtn.addEventListener("click", () => switchTab("monitor"));
    tabBackupBtn.addEventListener("click", () => switchTab("backup"));
    tabPubBtn.addEventListener("click", () => switchTab("pub"));
    xferSortButtons.forEach((btn) => {
      btn.addEventListener("click", () => {
        const nextMode = btn.dataset.sort || "speed";
        if (transferSortMode === nextMode) {
          transferSortAscending = !transferSortAscending;
        } else {
          transferSortMode = nextMode;
          transferSortAscending = nextMode === "name" || nextMode === "source";
        }
        syncTransferSortButtons();
        renderTransfers({
          items: latestTransfers,
          count: latestTransferOverview.count,
          recent_count: latestTransferOverview.recent_count,
          overall_progress_pct: latestTransferOverview.overall_progress_pct,
        });
      });
    });
    if (speedText) {
      speedText.title = "Click to switch units (current MiB/s）";
      speedText.style.cursor = "pointer";
      speedText.addEventListener("click", () => {
        if (!speedValueReady) return;
        speedDisplayUnit = speedDisplayUnit === "MiB/s" ? "Mbps" : "MiB/s";
        renderSpeedValue();
      });
    }

    const ndDetailArea = document.getElementById("ndDetailArea");
    const ndStatusText = document.getElementById("ndStatusText");
    const ndTabBarWrap = document.getElementById("ndTabBarWrap");
    const ND_ALL_SOURCES = [
      { key: "baidu", label: "Baidu Netdisk" },
      { key: "ali", label: "Aliyun Drive" },
      { key: "guangya", label: "Guangya Drive" },
      { key: "dropbox", label: "Dropbox" },
      { key: "mega", label: "MEGA" },
      { key: "onedrive", label: "OneDrive" },
      { key: "gdrive", label: "Google Drive" },
    ];
    let ndPolling = false;
    let ndTimer = 0;
    let ndActiveTab = "";
    let ndLastSourceStats = [];
    let ndLastItems = [];
    let ndEnabledSources = { baidu: true, ali: true, guangya: true, dropbox: false, mega: false, onedrive: false, gdrive: false };
    const ndShowAllBySource = {};

    function ndSourceLabelToKey(label) {
      const raw = String(label || "").trim();
      if (!raw) return "";
      const normalized = normalizeSourceName(raw);
      if (SOURCE_LABEL_TO_KEY[normalized]) return SOURCE_LABEL_TO_KEY[normalized];
      if (SOURCE_LABEL_TO_KEY[raw]) return SOURCE_LABEL_TO_KEY[raw];
      const sl = raw.toLowerCase();
      if (sl.includes("guangya") || sl.includes("光鸭") || sl.includes("clouddrive") || sl.includes("cloud drive")) return "guangya";
      if (sl.includes("aliyun") || sl.includes("alipan") || sl.includes("阿里")) return "ali";
      if (sl.includes("baidu") || sl.includes("pan.baidu") || sl.includes("xpan") || sl.includes("baiduyun") || sl.includes("yun.baidu") || sl.includes("pcs") || sl.includes("百度")) return "baidu";
      if (sl.includes("dropbox")) return "dropbox";
      if (sl.includes("mega")) return "mega";
      if (sl.includes("onedrive")) return "onedrive";
      if ((sl.includes("google") && sl.includes("drive")) || sl.includes("gdrive")) return "gdrive";
      for (const s of ND_ALL_SOURCES) {
        if (sl === s.label.toLowerCase() || sl === s.key.toLowerCase()) return s.key;
      }
      return "";
    }
    function ndGetEnabledList() {
      return ND_ALL_SOURCES.filter(s => ndEnabledSources[s.key] !== false);
    }
    function ndUpdateSectionTitles() {
      const activeSource = ndActiveTab
        ? ND_ALL_SOURCES.find((s) => s.key === ndActiveTab)
        : null;
      if (httpSpeedCardTitle) {
        httpSpeedCardTitle.textContent = activeSource
          ? activeSource.label + " HTTP Throughput"
          : "Aggregate HTTP Throughput";
      }
      if (netdiskTransferCardTitle) {
        netdiskTransferCardTitle.textContent = activeSource
          ? activeSource.label + " HTTP Sessions"
          : "Aggregate HTTP Session Activity";
      }
    }

    function ndEsc(v) {
      return String(v == null ? "" : v).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
    }
    function ndFmt(v, d) {
      const n = Number(v || 0);
      return Number.isFinite(n) ? n.toFixed(d) : "0." + "0".repeat(d);
    }
    function ndRenderTabs() {
      if (!ndTabBarWrap) return;
      const enabled = ndGetEnabledList();
      let html = '<div style="display:flex;flex-wrap:wrap;align-items:center;gap:6px;padding:6px;background:var(--bg-card);border-radius:999px;border:1px solid var(--border);box-shadow:0 4px 16px rgba(15,23,42,0.08);">';
      html += '<button type="button" class="nd-filter-tab" data-ndtab="" style="background:' + (!ndActiveTab ? "var(--hero-tone,var(--accent));color:#fff;box-shadow:0 2px 10px rgba(0,0,0,0.15);" : "transparent;color:var(--text-muted);") + 'border:none;padding:8px 16px;border-radius:999px;font-weight:600;font-size:13px;cursor:pointer;white-space:nowrap;">All</button>';
      for (const s of enabled) {
        const isActive = ndActiveTab === s.key;
        html += '<button type="button" class="nd-filter-tab" data-ndtab="' + ndEsc(s.key) + '" style="background:' + (isActive ? "var(--hero-tone,var(--accent));color:#fff;box-shadow:0 2px 10px rgba(0,0,0,0.15);" : "transparent;color:var(--text-muted);") + 'border:none;padding:8px 16px;border-radius:999px;font-weight:600;font-size:13px;cursor:pointer;white-space:nowrap;">' + ndEsc(s.label) + '</button>';
      }
      html += '<a href="/config#netdisk" class="nd-filter-tab" style="margin-left:auto;background:transparent;color:var(--text-muted);border:none;padding:6px 12px;border-radius:999px;font-size:16px;cursor:pointer;text-decoration:none;white-space:nowrap;" title="Configure visible sources">⚙️</a>';
      html += '</div>';
      ndTabBarWrap.innerHTML = html;
      ndTabBarWrap.querySelectorAll(".nd-filter-tab[data-ndtab]").forEach(btn => {
        btn.addEventListener("click", () => {
          ndActiveTab = btn.dataset.ndtab || "";
          ndUpdateSectionTitles();
          ndRenderTabs();
          ndRenderCombined();
          reRenderFilteredTransfers();
        });
      });
    }
    function reRenderFilteredTransfers() {
      if (!latestTransfers) return;
      renderTransfers({ items: latestTransfers, count: latestTransferOverview.count, recent_count: latestTransferOverview.recent_count, overall_progress_pct: latestTransferOverview.overall_progress_pct });
    }
    function ndRenderCombined() {
      if (!ndDetailArea) return;
      const sourceStats = Array.isArray(ndLastSourceStats) ? ndLastSourceStats : [];
      const items = Array.isArray(ndLastItems) ? ndLastItems : [];
      const activeText = trRaw("Active");
      const deactiveText = trRaw("Deactive");
      const showAllText = trRaw("Show All");
      const estabText = trRaw("Estab");
      const enabled = ndGetEnabledList();
      let sourcesToShow = ndActiveTab
        ? enabled.filter(s => s.key === ndActiveTab)
        : enabled;
      if (!sourcesToShow.length) {
        ndDetailArea.innerHTML = '<div style="color:var(--text-muted);font-size:13px;padding:16px;text-align:center;">No enabled sources</div>';
        return;
      }
      const cardStyle = 'margin:12px 0;padding:14px 16px;background:var(--surface-soft);border:1px solid var(--border);border-radius:12px;';
      const headerStyle = 'display:flex;align-items:center;flex-wrap:wrap;gap:10px;margin-bottom:10px;padding-bottom:10px;border-bottom:1px solid var(--border);';
      const titleStyle = 'font-weight:750;font-size:15px;color:var(--text);letter-spacing:0.2px;';
      const badgeStyle = 'display:inline-flex;align-items:center;gap:4px;padding:3px 10px;border-radius:999px;background:color-mix(in srgb, #16a34a 18%, transparent);color:#22c55e;font-size:11px;font-weight:600;';
      const deactivedBadgeStyle = 'display:inline-flex;align-items:center;gap:4px;padding:3px 10px;border-radius:999px;background:color-mix(in srgb, #ef4444 16%, transparent);color:#ef4444;font-size:11px;font-weight:600;';
      const statRowStyle = 'display:flex;align-items:center;gap:18px;font-size:12px;color:var(--text-muted);';
      const statItemStyle = 'display:inline-flex;align-items:center;gap:4px;';
      const valStyle = 'color:var(--text);font-weight:600;font-variant-numeric:tabular-nums;';
      const tableWrapStyle = 'border:1px solid var(--border);border-radius:10px;max-height:360px;overflow:auto;background:var(--bg-card,var(--surface));';
      const tableStyle = 'width:100%;border-collapse:collapse;min-width:860px;';
      const thStyle = 'border-bottom:1px solid var(--border);padding:9px 12px;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.4px;color:var(--text-muted);background:var(--surface-soft);';
      const tdStyle = 'border-bottom:1px solid var(--border);padding:9px 12px;font-size:13px;color:var(--text);vertical-align:middle;';
      const monoFont = 'ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace';
      const emptyStyle = 'color:var(--text-muted);font-size:13px;padding:16px;text-align:center;font-style:italic;';
      const isCloseWaitState = (stateVal) => {
        const norm = String(stateVal || "").toUpperCase().replace(/[-\s]/g, "_");
        return norm === "CLOSE_WAIT";
      };
      let html = '';
      for (const src of sourcesToShow) {
        const stat = sourceStats.find(s => ndSourceLabelToKey(s.source) === src.key);
        const rawConns = items.filter(x => ndSourceLabelToKey(x.source) === src.key);
        const showAll = !!ndShowAllBySource[src.key];
        const conns = showAll
          ? rawConns
          : rawConns.filter((x) => !isCloseWaitState((x || {}).state));
        const connCount = conns.length;
        const estab = stat ? Number(stat.estab_count || 0) : 0;
        const dl = stat ? ndFmt(stat.download_mibps, 2) : "0.00";
        const ul = stat ? ndFmt(stat.upload_mibps, 2) : "0.00";
        const isActive = (Number(dl) > 0 || Number(ul) > 0 || estab > 0);
        const hasAppRuntime = rawConns.length > 0;
        html += '<div style="' + cardStyle + '">';
        html += '<div style="' + headerStyle + '">';
        html += '<span style="' + titleStyle + '">' + ndEsc(src.label) + ' <span style="opacity:0.55;font-weight:600;font-size:12px;">HTTP</span></span>';
        if (isActive) html += '<span style="' + badgeStyle + '"><span style="color:#22c55e;">●</span> ' + ndEsc(activeText) + '</span>';
        else if (!hasAppRuntime) html += '<span style="' + deactivedBadgeStyle + '"><span style="color:#ef4444;">●</span> ' + ndEsc(deactiveText) + '</span>';
        html += '<label style="display:inline-flex;align-items:center;gap:6px;padding:3px 10px;border-radius:999px;border:1px solid var(--border);font-size:11px;color:var(--text-muted);white-space:nowrap;cursor:pointer;">';
        html += '<input type="checkbox" class="nd-show-all-toggle" data-ndsrc="' + ndEsc(src.key) + '" ' + (showAll ? "checked" : "") + ' style="margin:0;" />';
        html += '<span>' + ndEsc(showAllText) + '</span>';
        html += '</label>';
        html += '<span style="flex:1 1 auto;"></span>';
        html += '<span style="' + statRowStyle + '">';
        html += '<span style="' + statItemStyle + '">Connections <span style="' + valStyle + '">' + connCount + '</span></span>';
        html += '<span style="' + statItemStyle + '">' + ndEsc(estabText) + ' <span style="' + valStyle + '">' + estab + '</span></span>';
        html += '<span style="' + statItemStyle + '">↓ <span style="' + valStyle + '">' + dl + '</span> MiB/s</span>';
        html += '<span style="' + statItemStyle + '">↑ <span style="' + valStyle + '">' + ul + '</span> MiB/s</span>';
        html += '</span>';
        html += '</div>';
        if (!conns.length) {
          html += '<div style="' + emptyStyle + '">No active TCP connections</div>';
        } else {
          html += '<div style="' + tableWrapStyle + '">';
          html += '<table style="' + tableStyle + '">';
          html += '<thead><tr>';
          html += '<th style="' + thStyle + 'text-align:left;">Source</th>';
          html += '<th style="' + thStyle + 'text-align:left;">Process</th>';
          html += '<th style="' + thStyle + 'text-align:right;">PID</th>';
          html += '<th style="' + thStyle + 'text-align:left;">State</th>';
          html += '<th style="' + thStyle + 'text-align:left;">Local endpoint</th>';
          html += '<th style="' + thStyle + 'text-align:left;">Remote endpoint</th>';
          html += '<th style="' + thStyle + 'text-align:right;">↓ MiB/s</th>';
          html += '<th style="' + thStyle + 'text-align:right;">↑ MiB/s</th>';
          html += '</tr></thead><tbody>';
          for (const r of conns) {
            const state = String(r.state || "-").toUpperCase();
            const isEstab = state === 'ESTAB';
            const displayState = isEstab ? estabText : state;
            const stateBadge = isEstab
              ? 'display:inline-block;padding:2px 8px;border-radius:6px;background:color-mix(in srgb, #16a34a 18%, transparent);color:#16a34a;font-size:11px;font-weight:700;font-family:' + monoFont + ';letter-spacing:0.3px;'
              : 'display:inline-block;padding:2px 8px;border-radius:6px;background:color-mix(in srgb, var(--text-muted) 14%, transparent);color:var(--text-muted);font-size:11px;font-weight:700;font-family:' + monoFont + ';letter-spacing:0.3px;';
            const dlR = ndFmt(r.download_mibps, 2);
            const ulR = ndFmt(r.upload_mibps, 2);
            const dlEm = Number(dlR) > 0 ? 'color:var(--accent);font-weight:600;' : 'color:var(--text-muted);';
            const ulEm = Number(ulR) > 0 ? 'color:var(--accent);font-weight:600;' : 'color:var(--text-muted);';
            html += '<tr>';
            html += '<td style="' + tdStyle + '">' + ndEsc(r.source || "-") + '</td>';
            html += '<td style="' + tdStyle + 'font-weight:500;">' + ndEsc(r.process || "-") + '</td>';
            html += '<td style="' + tdStyle + 'text-align:right;font-variant-numeric:tabular-nums;color:var(--text-muted);">' + Number(r.pid || 0) + '</td>';
            html += '<td style="' + tdStyle + '"><span style="' + stateBadge + '">' + ndEsc(displayState) + '</span></td>';
            html += '<td style="' + tdStyle + 'font-family:' + monoFont + ';font-size:12px;color:var(--text-muted);">' + ndEsc(r.local_ep || "-") + '</td>';
            html += '<td style="' + tdStyle + 'font-family:' + monoFont + ';font-size:12px;">' + ndEsc(r.peer_ep || "-") + '</td>';
            html += '<td style="' + tdStyle + 'text-align:right;font-variant-numeric:tabular-nums;' + dlEm + '">' + dlR + '</td>';
            html += '<td style="' + tdStyle + 'text-align:right;font-variant-numeric:tabular-nums;' + ulEm + '">' + ulR + '</td>';
            html += '</tr>';
          }
          html += '</tbody></table></div>';
        }
        html += '</div>';
      }
      ndDetailArea.innerHTML = html;
      ndDetailArea.querySelectorAll(".nd-show-all-toggle").forEach((el) => {
        el.addEventListener("change", () => {
          const key = String(el.getAttribute("data-ndsrc") || "");
          if (!key) return;
          ndShowAllBySource[key] = !!el.checked;
          ndRenderCombined();
        });
      });
    }
    async function ndLoadData() {
      const res = await fetch(location.origin + "/api/process-net", { cache: "no-store" });
      const d = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error((d && d.error) || "Request failed " + res.status);
      ndLastSourceStats = d.source_stats || [];
      ndLastItems = d.items || [];
      ndRenderCombined();
      const count = Number(d.count || 0);
      const delta = Number(d.delta_sec || 0);
      const sample = Number(d.sample_ts || 0);
      const when = sample > 0 ? new Date(sample * 1000).toLocaleTimeString() : "-";
      if (ndStatusText) {
        ndStatusText.textContent = "Connections " + count + " | Interval " + ndFmt(delta, 2) + "s | Last sample " + when;
        ndStatusText.className = "status-bar muted";
      }
    }
    function startNdPolling() {
      if (ndPolling) return;
      ndPolling = true;
      ndUpdateSectionTitles();
      ndRenderTabs();
      function tick() {
        ndLoadData().catch(err => {
          if (ndStatusText) {
            ndStatusText.textContent = "Load failed: " + (err.message || err);
            ndStatusText.className = "status-bar err";
          }
        }).finally(() => {
          if (ndPolling) ndTimer = setTimeout(tick, 2000);
        });
      }
      tick();
    }

    // Backup functions
    function formatBytes(bytes) {
      if (bytes === 0) return '0 B';
      const k = 1024;
      const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
      const i = Math.floor(Math.log(bytes) / Math.log(k));
      return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    async function loadBackupStatus() {
      try {
        const data = await getJson('/api/backup/status');
        if (data.success) {
          if (backupConfigPath) backupConfigPath.textContent = data.config_path || '-';
          if (backupDbStatus) backupDbStatus.textContent = data.db_exists ? '✓ Exists' : '✗ Not initialized';
          if (data.storage_stats) {
            if (backupSnapshotCount) backupSnapshotCount.textContent = data.storage_stats.snapshot_count || '0';
            if (backupTotalSize) backupTotalSize.textContent = formatBytes(data.storage_stats.total_size || 0);
            if (backupLastTime) {
              if (data.storage_stats.newest_snapshot) {
                backupLastTime.textContent = new Date(data.storage_stats.newest_snapshot).toLocaleString();
              } else {
                backupLastTime.textContent = 'Never';
              }
            }
          }
          await loadBackupSnapshots();
        }
      } catch (err) {
        console.error('Failed to load backup status:', err);
      }
    }

    async function loadBackupSnapshots() {
      try {
        const data = await getJson('/api/backup/list');
        if (data.success && backupSnapshotList) {
          if (data.snapshots.length === 0) {
            backupSnapshotList.innerHTML = '<p style="color:var(--text-muted);padding:10px;">No snapshots found</p>';
            return;
          }
          let html = '<table style="width:100%;border-collapse:collapse;"><thead><tr style="border-bottom:1px solid var(--border);">';
          html += '<th style="text-align:left;padding:8px;">Snapshot ID</th>';
          html += '<th style="text-align:left;padding:8px;">Time</th>';
          html += '<th style="text-align:right;padding:8px;">Files</th>';
          html += '<th style="text-align:right;padding:8px;">Size</th>';
          html += '</tr></thead><tbody>';
          data.snapshots.forEach(s => {
            html += '<tr style="border-bottom:1px solid var(--border);">';
            html += '<td style="padding:8px;"><code>' + s.id + '</code></td>';
            html += '<td style="padding:8px;">' + new Date(s.timestamp).toLocaleString() + '</td>';
            html += '<td style="padding:8px;text-align:right;">' + s.file_count + '</td>';
            html += '<td style="padding:8px;text-align:right;">' + formatBytes(s.total_size) + '</td>';
            html += '</tr>';
          });
          html += '</tbody></table>';
          backupSnapshotList.innerHTML = html;
        }
      } catch (err) {
        console.error('Failed to load snapshots:', err);
      }
    }

    if (backupRunBtn) {
      backupRunBtn.addEventListener('click', async () => {
        backupRunBtn.disabled = true;
        backupRunBtn.textContent = 'Running...';
        if (backupResult) backupResult.textContent = 'Backup in progress...';
        try {
          const data = await getJson('/api/backup/run', { method: 'POST' });
          if (data.success) {
            if (backupResult) {
              backupResult.textContent = `✓ Backup completed: ${data.files_processed} files, ${formatBytes(data.bytes_transferred)}`;
              backupResult.style.color = 'var(--success)';
            }
            await loadBackupStatus();
          } else {
            if (backupResult) {
              backupResult.textContent = `✗ Backup failed: ${data.error || 'Unknown error'}`;
              backupResult.style.color = 'var(--error)';
            }
          }
        } catch (err) {
          if (backupResult) {
            backupResult.textContent = `✗ Error: ${err.message || err}`;
            backupResult.style.color = 'var(--error)';
          }
        } finally {
          backupRunBtn.disabled = false;
          backupRunBtn.textContent = 'Run Backup Now';
        }
      });
    }

    if (backupRefreshBtn) {
      backupRefreshBtn.addEventListener('click', () => loadBackupStatus());
    }

    if (backupConfigBtn) {
      backupConfigBtn.addEventListener('click', () => {
        window.location.href = '/config#backup';
      });
    }

    Promise.resolve(i18nReady).finally(() => {
      loadBaseAndDirs(true).catch((err) => setStatus(err.message, true));
      try {
        const storedClipId = localStorage.getItem("shareclip_id");
        if (storedClipId) clipCurrent = normalizeClipId(storedClipId);
      } catch (e) {}
      clipIdInput.value = clipCurrent;
      clipCurrentId.textContent = clipCurrent;
      clipRawLink.href = clipUrl("/api/clip/raw");
      applyShareclipLocaleUI();
      refreshClipAll().catch((err) => setClipStatus(err.message || String(err), true));
      syncTransferSortButtons();
      loadSpeed();
      loadTransfers();
      loadControlStatus();
      setInterval(loadSpeed, 2000);
      setInterval(loadTransfers, 2000);
      setInterval(loadControlStatus, 5000);
      startNdPolling();
    });

    document.addEventListener("fcc:lang-changed", () => {
      pauseRealtime(1200);
      applyShareclipLocaleUI();
      refreshClipAll().catch(() => {});
      loadControlStatus();
      loadSpeed();
      loadTransfers();
    });
  </script>
</body>
</html>
"""
    html = html.replace("__APP_VERSION_TEXT__", APP_VERSION_TEXT)
    return _inject_page_title(html, "AfterClaw")


def build_ddns_settings_html() -> str:
    return _inject_page_title(load_ddns_settings_page(), "DDNS Settings")


def build_config_html() -> str:
    html = """<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Config</title>
  <script>
    (function(){
      try {
        var t = localStorage.getItem("fc-theme");
        var hero = localStorage.getItem("fc-hero-preset");
        if (!t) { t = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"; }
        document.documentElement.setAttribute("data-theme", t);
        if (hero) { document.documentElement.setAttribute("data-hero-preset", hero); }
      } catch(e){}
    })();
  </script>
  <link rel="stylesheet" href="/dashboard.css" />
  <script src="/i18n.js?v=20260430d"></script>
  <style>
    .cfg-tabs-row {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
      align-items: center;
      gap: 12px;
      margin: 0 0 16px;
    }
    .cfg-tabs {
      display:flex;
      gap:10px;
      margin: 0;
      flex-wrap: wrap;
      grid-column: 2;
      justify-content: center;
      justify-self: center;
    }
    .cfg-tabs-actions {
      grid-column: 3;
      justify-self: end;
      display: flex;
      align-items: center;
      justify-content: flex-end;
      gap: 8px;
      flex-wrap: wrap;
    }
    .cfg-tabs-actions .secondary { white-space: nowrap; }
    .page-head .back-link,
    .cfg-tabs-actions .back-link {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 10px 14px;
      border-radius: 12px;
      border: 1px solid color-mix(in srgb, var(--border) 84%, #ffffff 16%);
      background: color-mix(in srgb, var(--surface-soft) 86%, #0b1220 14%);
      color: var(--text);
      font-weight: 700;
      text-decoration: none;
      line-height: 1;
      white-space: nowrap;
    }
    .page-head .back-link { margin-bottom: 10px; }
    .page-head .back-link:hover,
    .cfg-tabs-actions .back-link:hover {
      background: color-mix(in srgb, var(--surface-hover) 82%, transparent);
      border-color: color-mix(in srgb, var(--border) 66%, #ffffff 34%);
      color: var(--text);
    }
    .cfg-tab {
      border: 1px solid var(--tab-chip-border, var(--border));
      border-radius: 12px;
      padding: 10px 14px;
      background: var(--tab-chip-bg, var(--surface-soft));
      cursor: pointer;
      font-weight: 600;
      color: var(--tab-chip-text, var(--text));
    }
    .cfg-tab.active {
      background: var(--tab-chip-active-bg, var(--accent));
      color: var(--tab-chip-active-text, #fff);
      border-color: var(--tab-chip-active-border, var(--accent));
      box-shadow: 0 0 0 1px color-mix(in srgb, var(--tab-chip-active-bg, var(--accent)) 38%, transparent);
    }
    .cfg-panel { display:none; }
    .cfg-panel.active { display:block; }
    .cfg-grid {
      display:grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      gap: 14px;
    }
    .cfg-module-list { display:flex; flex-direction:column; gap:14px; margin-top:14px; }
    .cfg-module-item {
      border: 1px solid color-mix(in srgb, var(--panel-border-accent, var(--accent-soft)) 42%, var(--border) 58%);
      border-radius: 12px;
      padding: 14px 16px;
      background:
        linear-gradient(
          145deg,
          color-mix(in srgb, var(--panel-tint-strong, var(--accent-soft)) 34%, transparent) 0%,
          transparent 68%
        ),
        color-mix(in srgb, var(--surface-soft) 84%, var(--panel-tint, var(--accent-soft)) 16%);
      display: grid;
      grid-template-columns: auto 1fr;
      gap: 12px;
      align-items: center;
      cursor: pointer;
    }
    .cfg-switch-input {
      position: absolute;
      width: 1px;
      height: 1px;
      padding: 0;
      margin: -1px;
      overflow: hidden;
      clip: rect(0, 0, 0, 0);
      white-space: nowrap;
      border: 0;
    }
    .cfg-switch {
      width: 44px;
      height: 26px;
      border-radius: 999px;
      background: color-mix(in srgb, var(--surface-hover) 80%, transparent);
      border: 1px solid var(--border);
      box-shadow: inset 0 2px 5px rgba(2, 6, 23, 0.22);
      position: relative;
      transition: background 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
      flex: 0 0 auto;
    }
    .cfg-switch::after {
      content: "";
      position: absolute;
      top: 2px;
      left: 2px;
      width: 20px;
      height: 20px;
      border-radius: 50%;
      background: #f8fafc;
      box-shadow: 0 2px 6px rgba(2, 6, 23, 0.35);
      transition: transform 0.2s ease, background 0.2s ease;
    }
    .cfg-switch-input:checked + .cfg-switch {
      background: color-mix(in srgb, var(--hero-tone, var(--accent)) 82%, #0f172a 18%);
      border-color: color-mix(in srgb, var(--hero-tone, var(--accent)) 70%, var(--border) 30%);
      box-shadow: 0 0 0 1px color-mix(in srgb, var(--hero-tone, var(--accent)) 32%, transparent), inset 0 2px 6px rgba(2, 6, 23, 0.25);
    }
    .cfg-switch-input:checked + .cfg-switch::after {
      transform: translateX(18px);
      background: #ffffff;
    }
    .cfg-switch-input:focus-visible + .cfg-switch {
      outline: 2px solid color-mix(in srgb, var(--hero-tone, var(--accent)) 65%, transparent);
      outline-offset: 2px;
    }
    .cfg-module-title { font-weight: 700; font-size: 15px; color: var(--text); margin: 0; }
    .cfg-module-desc { margin: 4px 0 0; font-size: 13px; color: var(--text-muted); line-height: 1.45; }
    .cfg-item {
      border: 1px solid color-mix(in srgb, var(--panel-border-accent, var(--accent-soft)) 36%, var(--border) 64%);
      border-radius: 10px;
      padding: 12px;
      background:
        linear-gradient(
          142deg,
          color-mix(in srgb, var(--panel-tint, var(--accent-soft)) 24%, transparent) 0%,
          transparent 72%
        ),
        var(--surface-soft);
    }
    .cfg-item .title { font-weight: 700; margin-bottom: 6px; }
    .cfg-actions { display:flex; gap:10px; flex-wrap:wrap; margin-top:14px; }
    .cfg-status {
      margin-top: 10px;
      font-size: 14px;
      color: var(--text-muted);
      line-height: 1.45;
    }
    .cfg-status.err { color: var(--danger); font-weight: 600; }
    .cfg-help { margin: 0; font-size: 13px; color: var(--text-muted); line-height: 1.5; }
    .cfg-code {
      margin-top: 8px;
      border: 1px solid var(--border);
      border-radius: 10px;
      background: var(--surface-elevated);
      padding: 10px 12px;
      font-family: ui-monospace, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
      font-size: 12px;
      line-height: 1.5;
      color: var(--text);
      word-break: break-all;
    }
    .terminal-btn.inactive {
      opacity: 0.55;
    }
    .ddns-frame-wrap {
      border: 1px solid color-mix(in srgb, var(--panel-border-accent, var(--accent-soft)) 34%, var(--border) 66%);
      border-radius: 12px;
      overflow: hidden;
      background:
        linear-gradient(
          140deg,
          color-mix(in srgb, var(--panel-tint, var(--accent-soft)) 22%, transparent) 0%,
          transparent 72%
        ),
        var(--surface-soft);
      min-height: 70vh;
    }
    #ddnsFrame {
      width: 100%;
      min-height: 70vh;
      border: 0;
      display: block;
      background: transparent;
    }
    .brush-icon {
      width: 15px;
      height: 15px;
      margin-right: 6px;
      vertical-align: -2px;
      stroke: currentColor;
      fill: none;
      stroke-width: 1.8;
      stroke-linecap: round;
      stroke-linejoin: round;
    }
    #cfgThemeStatus.err { color: var(--danger); font-weight: 600; }
    #cfgThemeMeta { margin: 0; }
    @media (max-width: 900px) {
      .cfg-tabs-row {
        grid-template-columns: 1fr;
        gap: 10px;
      }
      .cfg-tabs {
        grid-column: auto;
        justify-self: center;
        justify-content: center;
      }
      .cfg-tabs-actions {
        grid-column: auto;
        justify-self: center;
        justify-content: center;
      }
    }
  </style>
</head>
<body>
  <div class="wrap">
    <header class="page-head">
      <div class="head-row">
        <div>
          <h1 data-i18n="config.title" data-i18n-fallback="Configuration">Configuration</h1>
          <p class="page-sub" data-i18n="config.subtitle" data-i18n-fallback="General Settings (module toggles) / HTTP / BitTorrent / Terminal / DDNS">General Settings (module toggles) / HTTP / BitTorrent / Terminal / DDNS</p>
        </div>
      </div>
    </header>

    <div class="cfg-tabs-row">
      <div class="cfg-tabs">
        <button class="cfg-tab active" type="button" data-tab="general" data-i18n="config.tab.general" data-i18n-fallback="General">General</button>
        <button class="cfg-tab" type="button" data-tab="http" data-i18n="config.tab.http" data-i18n-fallback="HTTP">HTTP</button>
        <button class="cfg-tab" type="button" data-tab="qbt" data-i18n="config.tab.bt" data-i18n-fallback="BitTorrent">BitTorrent</button>
        <button class="cfg-tab" type="button" data-tab="terminal" data-i18n="config.tab.terminal" data-i18n-fallback="Terminal">Terminal</button>
        <button class="cfg-tab" type="button" data-tab="ddns" data-i18n="config.tab.ddns" data-i18n-fallback="DDNS">DDNS</button>
        <button class="cfg-tab" type="button" data-tab="backup" data-i18n="config.tab.backup" data-i18n-fallback="Backup" style="display:none">Backup</button>
        <button class="cfg-tab" type="button" data-tab="netdisk" data-i18n="config.tab.netdisk" data-i18n-fallback="Netdisk">Netdisk</button>
      </div>
      <div class="cfg-tabs-actions">
        <a href="/" class="back-link" data-i18n="← Back to AfterClaw" data-i18n-fallback="← Back to AfterClaw">← Back to AfterClaw</a>
        <a id="terminalHeadLink" href="/terminal" class="gear-btn terminal-btn" title="Terminal" aria-label="Terminal"><svg class="ui-icon term-icon" viewBox="0 0 24 24" aria-hidden="true"><rect x="4.5" y="5.5" width="15" height="13" rx="2.4"></rect><path d="M8 10.2 L10.8 12 L8 13.8"></path><line x1="12.8" y1="13.9" x2="16" y2="13.9"></line></svg></a>
        <button type="button" id="themeToggleBtn" class="gear-btn" title="Toggle theme"><svg class="ui-icon" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4.2"></circle><path d="M12 2.5v2.2M12 19.3v2.2M4.7 4.7l1.6 1.6M17.7 17.7l1.6 1.6M2.5 12h2.2M19.3 12h2.2M4.7 19.3l1.6-1.6M17.7 6.3l1.6-1.6"></path></svg></button>
        <select id="langSelect" class="lang-select" title="Language">
          <option value="zh-CN">简体中文</option>
          <option value="zh-TW">繁體中文</option>
          <option value="en">English</option>
          <option value="de">Deutsch</option>
          <option value="fr">Français</option>
          <option value="ja">日本語</option>
        </select>
      </div>
    </div>

    <section id="panel-general" class="cfg-panel active">
      <div class="card">
        <span class="card-title">Unified Module Configuration</span>
        <div class="cfg-module-list">
          <label class="cfg-module-item">
            <input type="checkbox" id="modHttp" class="cfg-switch-input" checked />
            <span class="cfg-switch" aria-hidden="true"></span>
            <div>
              <p class="cfg-module-title">HTTP Module</p>
              <p class="cfg-module-desc">Controls the homepage "HTTPD Service" card and HTTP monitoring area. Disabling it forcibly interrupts one upload connection and turns uploads off.</p>
            </div>
          </label>
          <label class="cfg-module-item">
            <input type="checkbox" id="modQbt" class="cfg-switch-input" checked />
            <span class="cfg-switch" aria-hidden="true"></span>
            <div>
              <p class="cfg-module-title">BitTorrent Module</p>
              <p class="cfg-module-desc">Shows BitTorrent status card and control actions on homepage.</p>
            </div>
          </label>
          <label class="cfg-module-item">
            <input type="checkbox" id="modDdns" class="cfg-switch-input" checked />
            <span class="cfg-switch" aria-hidden="true"></span>
            <div>
              <p class="cfg-module-title">DDNS Module</p>
              <p class="cfg-module-desc">Shows DDNS status card on homepage and keeps DDNS settings entry in Config.</p>
            </div>
          </label>
          <label class="cfg-module-item">
            <input type="checkbox" id="modShareclip" class="cfg-switch-input" checked />
            <span class="cfg-switch" aria-hidden="true"></span>
            <div>
              <p class="cfg-module-title">ShareClip Module</p>
              <p class="cfg-module-desc">Controls ShareClip tab visibility on homepage.</p>
            </div>
          </label>
        </div>
        <div class="cfg-actions">
          <button type="button" id="saveModulesBtn">Save Unified Config</button>
          <button type="button" id="restartCfgServiceBtn" class="secondary">Restart Service</button>
        </div>
        <p id="generalStatus" class="cfg-status"></p>
      </div>
      <div class="card">
        <span class="card-title">Auto Update</span>
        <p class="cfg-help">Fetches release package from GitHub and runs local <code>install.sh</code>. During upgrade, service may restart and temporary disconnection is expected.</p>
        <div class="cfg-grid" style="margin-top:12px;">
          <label class="cfg-item">
            <div class="title">Update Branch</div>
            <select id="upgradeBranchSelect">
              <option value="main">main (Stable)</option>
              <option value="nightly">nightly (Development)</option>
            </select>
          </label>
        </div>
        <div class="cfg-actions">
          <button type="button" id="runUpgradeBtn">Run Auto Update</button>
          <button type="button" id="refreshUpgradeStatusBtn" class="secondary">Check Server Version</button>
        </div>
        <p id="upgradeStatus" class="cfg-status"></p>
        <p id="upgradeMeta" class="cfg-help"></p>
      </div>
      <div class="card">
        <span class="card-title">
          <svg class="brush-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M14.2 4.2l5.6 5.6-9.8 9.8-6.7 1 1-6.7 9.9-9.7z"></path><path d="M12.1 6.3l5.6 5.6"></path></svg>
          Theme
        </span>
        <div class="theme-panel" style="margin-top:10px;">
          <div class="theme-preset-group">
            <button type="button" class="theme-preset-btn" data-hero-preset="default">Default</button>
            <button type="button" class="theme-preset-btn" data-hero-preset="aurora">Aurora</button>
            <button type="button" class="theme-preset-btn" data-hero-preset="sunset">Sunset</button>
            <button type="button" class="theme-preset-btn" data-hero-preset="frost">Frost</button>
            <button type="button" class="theme-preset-btn" data-hero-preset="afterclaw_clouds">Clouds at Dusk</button>
          </div>
          <p id="cfgThemeMeta" class="cfg-help">Current theme: Default</p>
          <p id="cfgThemeStatus" class="cfg-help">Presets only switch tab background colors.</p>
        </div>
      </div>
    </section>

    <section id="panel-http" class="cfg-panel">
      <div class="card">
        <span class="card-title">HTTP Configuration</span>
        <div class="cfg-grid" style="margin-top:12px;">
          <label class="cfg-item">
            <div class="title">Service Port</div>
            <p class="cfg-help">Default is 1288. Restart service after saving HTTP settings to switch listening port.</p>
            <input id="webPortInput" type="number" min="1" max="65535" placeholder="1288" />
            <p id="webPortHint" class="cfg-help" style="margin-top:8px;">Current runtime port: 1288</p>
          </label>
          <label class="cfg-item">
            <div class="title">Completed transfer retention</div>
            <p class="cfg-help">Real-time Public Transfer keeps completed items for this many seconds. Recommended default: 15s.</p>
            <select id="transferRecentTtlSec">
              <option value="5">5s</option>
              <option value="10">10s</option>
              <option value="15">15s (Recommended)</option>
              <option value="30">30s</option>
              <option value="60">60s</option>
              <option value="120">120s</option>
            </select>
          </label>
        </div>
        <p class="cfg-help">Current HTTP root: <strong id="httpStorageRoot">-</strong></p>
        <div class="cfg-grid" style="margin-top:12px;">
          <label class="cfg-item">
            <div class="title">HTTP Root Directory (any path under / is allowed)</div>
            <p class="cfg-help">Use an absolute path, e.g. <code>/</code>, <code>/srv/Storage</code>, <code>/home/user</code>.</p>
            <input id="httpRootDir" placeholder="e.g. /srv/Storage or /" />
            <div class="row" style="margin-top:8px;">
              <button type="button" id="httpScanRootBtn" class="secondary">Validate (scan)</button>
            </div>
            <p id="httpScanResult" class="cfg-help" style="margin-top:8px;"></p>
          </label>
          <label class="cfg-item">
            <div class="title">Default directory (relative to HTTP root)</div>
            <p class="cfg-help">When opening "Directory Service" on homepage, it jumps to this default directory.</p>
            <input id="httpDefaultDir" placeholder="e.g. BT/TV or ." />
          </label>
          <div class="cfg-item" style="grid-column: 1 / -1;">
            <div class="title">Source IP pools (1288 training)</div>
            <p class="cfg-help">Maintain source pools with one IP/CIDR per line. Matched IPs are labeled by source before UA/Referer keyword matching.</p>
            <div class="cfg-grid" style="margin-top:10px; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));">
              <label class="cfg-item">
                <div class="title">Baidu Netdisk IP Pool</div>
                <textarea id="httpPoolBaidu" rows="7" placeholder="e.g. &#10;112.80.248.0/21&#10;220.181.38.0/24"></textarea>
              </label>
              <label class="cfg-item">
                <div class="title">Guangya Netdisk IP Pool</div>
                <textarea id="httpPoolGuangya" rows="7" placeholder="e.g. &#10;203.0.113.0/24"></textarea>
              </label>
              <label class="cfg-item">
                <div class="title">Aliyun Drive IP Pool</div>
                <textarea id="httpPoolAliyun" rows="7" placeholder="e.g. &#10;47.0.0.0/8"></textarea>
              </label>
            </div>
            <div class="cfg-item" style="margin-top:10px;">
              <div class="title">Updatable sources (GitHub/URL)</div>
              <p class="cfg-help">Supports <code>github:owner/repo/path</code>, e.g. <code>github:EinProfispieler/afterclaw/data/vendor-ip-pools</code>.</p>
              <div class="row" style="margin-top:8px;">
                <input id="httpPoolSource" class="grow" placeholder="e.g. github:EinProfispieler/afterclaw/data/vendor-ip-pools" />
                <button type="button" id="syncHttpPoolSourceBtn" class="secondary">Update IP pools from source</button>
              </div>
              <p id="httpPoolSourceMeta" class="cfg-help" style="margin-top:8px;"></p>
            </div>
          </div>
          <div class="cfg-item">
            <div class="title">Directory Browser (target server)</div>
            <div class="row" style="margin-top:8px;">
              <input id="httpBrowseDir" class="grow" placeholder="e.g. ." />
              <button type="button" id="httpBrowseLoadBtn" class="secondary">Load subdirectories</button>
              <button type="button" id="httpBrowseParentBtn" class="secondary">Parent</button>
            </div>
            <p class="cfg-help" style="margin-top:8px;">Click a subdirectory below to set it as default quickly.</p>
            <div id="httpDirList" class="dir-list" style="max-height:230px;"></div>
          </div>
        </div>
        <div class="cfg-actions">
          <button type="button" id="saveHttpBtn">Save HTTP Configuration</button>
        </div>
        <p id="httpStatus" class="cfg-status"></p>
      </div>
    </section>

    <section id="panel-qbt" class="cfg-panel">
      <div class="card">
        <span class="card-title" data-i18n="BitTorrent Service" data-i18n-fallback="BitTorrent Service">BitTorrent Service</span>
        <div class="cfg-grid" style="margin-top:12px;">
          <div class="cfg-item" style="grid-column: 1 / -1;">
            <div class="title" data-i18n="Clients (show/hide + drag to sort + click to edit)" data-i18n-fallback="Clients (show/hide + drag to sort + click to edit)">Clients (show/hide + drag to sort + click to edit)</div>
            <div id="qbtHomeClientList" class="row" style="gap:10px;flex-wrap:wrap;align-items:center;"></div>
          </div>
          <label class="cfg-item">
            <div class="title">Systemd service unit</div>
            <select id="qbtServiceUnit"></select>
          </label>
          <label class="cfg-item">
            <div class="title">Docker container name</div>
            <select id="qbtDockerContainer"></select>
          </label>
          <label class="cfg-item">
            <div class="title">Web API URL</div>
            <select id="qbtApiUrl"></select>
          </label>
        </div>
        <div class="cfg-actions">
          <button type="button" id="saveQbtBtn" data-i18n="Save BitTorrent settings" data-i18n-fallback="Save BitTorrent settings">Save BitTorrent settings</button>
          <button type="button" id="qbtDetectBtn" class="secondary" data-i18n="Detect available options" data-i18n-fallback="Detect available options">Detect available options</button>
          <button type="button" id="qbtCheckUpdateBtn" class="secondary">Check Client Update</button>
          <button type="button" id="qbtUpgradeBtn">Upgrade Client</button>
          <button type="button" id="qbtOptimizeBtn" data-i18n="Optimize Configuration" data-i18n-fallback="Optimize Configuration">Optimize Configuration</button>
          <button type="button" id="qbtFixPermBtn" class="secondary" data-i18n="Fix monitoring permissions" data-i18n-fallback="Fix monitoring permissions">Fix monitoring permissions</button>
          <button type="button" id="qbtRestartSvcBtn" class="secondary" data-i18n="Restart service" data-i18n-fallback="Restart service">Restart service</button>
        </div>
        <p id="qbtOptimizeTarget" class="cfg-help"></p>
        <p id="qbtUpgradeStatus" class="cfg-help"></p>
        <p id="qbtRuntimeStatus" class="cfg-status muted"></p>
        <p id="qbtStatus" class="cfg-status"></p>
      </div>
    </section>

    <section id="panel-terminal" class="cfg-panel">
      <div class="card">
        <span class="card-title">Terminal / SSH</span>
        <div class="cfg-grid" style="margin-top:12px;">
          <label class="cfg-item inline-check">
            <input type="checkbox" id="termEnabled" />
            <span class="title">Enable Terminal icon on homepage</span>
          </label>
          <label class="cfg-item">
            <div class="title">Host</div>
            <input id="termHost" placeholder="e.g. 127.0.0.1" />
          </label>
          <label class="cfg-item">
            <div class="title">User</div>
            <input id="termUser" placeholder="e.g. root" />
          </label>
          <label class="cfg-item">
            <div class="title">Port</div>
            <input id="termPort" type="number" min="1" max="65535" placeholder="22" />
          </label>
          <label class="cfg-item">
            <div class="title">Authentication mode</div>
            <select id="termAuthMode">
              <option value="key">key (recommended)</option>
              <option value="password">password (not stored)</option>
            </select>
          </label>
          <label class="cfg-item" id="termKeyFileItem">
            <div class="title">Key filename in config directory (optional)</div>
            <input id="termKeyFile" list="termKeyFileList" placeholder="e.g. id_ed25519" />
            <datalist id="termKeyFileList"></datalist>
            <p class="cfg-help" style="margin-top:6px;">Config directory: <code id="termKeyDirText">terminal_keys</code></p>
            <div class="row" style="margin-top:8px;">
              <button type="button" id="termPickKeyBtn" class="secondary">Select & Upload key</button>
              <button type="button" id="termRefreshKeyListBtn" class="secondary">Refresh key list</button>
              <input id="termKeyUploadInput" type="file" accept=".pem,.key,.txt,application/x-pem-file,application/octet-stream,text/plain" style="display:none;" />
            </div>
            <p class="cfg-help" style="margin-top:6px;">You can select a private key file from this device and upload it to the config directory.</p>
          </label>
          <label class="cfg-item" id="termKeyPathItem">
            <div class="title">Private key path (key mode)</div>
            <input id="termKeyPath" placeholder="e.g. ~/.ssh/id_ed25519" />
            <p class="cfg-help" style="margin-top:6px;">Uses this path when "Key filename in config directory" is empty.</p>
          </label>
        </div>
        <div class="cfg-item" style="margin-top:12px;">
          <div class="title">ConnectPreview</div>
          <p id="terminalTip" class="cfg-help"></p>
          <p class="cfg-help" style="margin-top:8px;">Terminal Link:
            <a id="terminalPreviewLink" href="#terminal" target="_blank" rel="noopener">Not configured</a>
          </p>
          <p class="cfg-help" style="margin-top:6px;">Web terminal entry:
            <a id="terminalWebLink" href="/terminal">Open /terminal</a>
          </p>
          <div id="terminalPreviewCmd" class="cfg-code">Not configured</div>
        </div>
        <div class="cfg-actions">
          <button type="button" id="saveTerminalBtn">Save Terminal config</button>
          <button type="button" id="copyTerminalCmdBtn" class="secondary">Copy SSH command</button>
        </div>
        <p id="terminalStatus" class="cfg-status"></p>
      </div>
    </section>

    <section id="panel-ddns" class="cfg-panel">
      <div class="card">
        <span class="card-title">DDNS</span>
        <div class="ddns-frame-wrap">
          <iframe id="ddnsFrame" src="/ddns?embed=1" title="DDNS Config"></iframe>
        </div>
      </div>
    </section>

    <section id="panel-backup" class="cfg-panel">
      <div class="card">
        <span class="card-title">Backup Configuration</span>
        <p class="cfg-help">Configure backup sources, targets, and retention policies. Config file: <code id="backupCfgPath">-</code></p>
        
        <div class="cfg-grid" style="margin-top:16px;">
          <label class="cfg-item">
            <div class="title">Backup Target Path</div>
            <input id="backupTargetPath" placeholder="e.g. ~/.afterclaw/backup or /mnt/backup" />
            <div class="cfg-help">Local directory to store backup snapshots</div>
          </label>
        </div>
        
        <div class="cfg-grid">
          <label class="cfg-item">
            <div class="title">Source Directories (one per line)</div>
            <textarea id="backupSourceDirs" rows="4" placeholder="~/Projects&#10;~/Documents&#10;/opt/data"></textarea>
            <div class="cfg-help">Directories to backup, one per line. Use ~ for home directory.</div>
          </label>
        </div>
        
        <div class="cfg-grid" style="grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));">
          <label class="cfg-item">
            <div class="title">Daily Retention</div>
            <input type="number" id="backupRetentionDaily" min="0" max="365" value="7" />
            <div class="cfg-help">Keep daily snapshots (days)</div>
          </label>
          <label class="cfg-item">
            <div class="title">Weekly Retention</div>
            <input type="number" id="backupRetentionWeekly" min="0" max="52" value="4" />
            <div class="cfg-help">Keep weekly snapshots (weeks)</div>
          </label>
          <label class="cfg-item">
            <div class="title">Monthly Retention</div>
            <input type="number" id="backupRetentionMonthly" min="0" max="120" value="12" />
            <div class="cfg-help">Keep monthly snapshots (months)</div>
          </label>
        </div>
        
        <div class="cfg-actions">
          <button type="button" id="saveBackupConfigBtn">Save Backup Config</button>
          <button type="button" id="loadBackupConfigBtn" class="secondary">Load Current Config</button>
          <button type="button" id="testBackupBtn" class="secondary">Test Backup Now</button>
        </div>
        <p id="backupCfgStatus" class="cfg-status"></p>
        
        <details class="card-fold" style="margin-top:20px;">
          <summary class="card-collapse-btn">
            <span class="card-title" style="margin-bottom:0;">Advanced Settings</span>
            <span class="card-collapse-arrow" aria-hidden="true">▶</span>
          </summary>
          <div class="card-fold-body">
            <div class="cfg-grid">
              <label class="cfg-item">
                <div class="title">Exclude Patterns (one per line)</div>
                <textarea id="backupExcludePatterns" rows="4" placeholder="**/node_modules/**&#10;**/.venv/**&#10;**/__pycache__/**"></textarea>
                <div class="cfg-help">Glob patterns to exclude from backup</div>
              </label>
            </div>
            <label class="cfg-module-item" style="margin-top:12px;">
              <input type="checkbox" id="backupCompressionEnabled" class="cfg-switch-input" checked />
              <span class="cfg-switch" aria-hidden="true"></span>
              <div>
                <p class="cfg-module-title">Enable Compression</p>
                <p class="cfg-module-desc">Compress backup files to save space</p>
              </div>
            </label>
          </div>
        </details>
      </div>
    </section>

    <section id="panel-netdisk" class="cfg-panel">
      <div class="card">
        <span class="card-title">Netdisk Sources</span>
        <p class="card-desc" style="margin:0 0 12px;font-size:13px;color:var(--text-muted);">Select netdisk sources to monitor. Once enabled, homepage and process-network details will show per-source connection and throughput stats.</p>
        <div class="cfg-module-list">
          <label class="cfg-module-item">
            <input type="checkbox" id="ndBaidu" class="cfg-switch-input" checked />
            <span class="cfg-switch" aria-hidden="true"></span>
            <div><p class="cfg-module-title">Baidu Netdisk</p><p class="cfg-module-desc">BaiduNetdisk</p></div>
          </label>
          <label class="cfg-module-item">
            <input type="checkbox" id="ndAli" class="cfg-switch-input" checked />
            <span class="cfg-switch" aria-hidden="true"></span>
            <div><p class="cfg-module-title">Aliyun Drive</p><p class="cfg-module-desc">aDrive / alipan</p></div>
          </label>
          <label class="cfg-module-item">
            <input type="checkbox" id="ndGuangya" class="cfg-switch-input" checked />
            <span class="cfg-switch" aria-hidden="true"></span>
            <div><p class="cfg-module-title">Guangya Netdisk</p><p class="cfg-module-desc">CloudDrive</p></div>
          </label>
          <label class="cfg-module-item">
            <input type="checkbox" id="ndDropbox" class="cfg-switch-input" />
            <span class="cfg-switch" aria-hidden="true"></span>
            <div><p class="cfg-module-title">Dropbox</p><p class="cfg-module-desc">Dropbox client</p></div>
          </label>
          <label class="cfg-module-item">
            <input type="checkbox" id="ndMega" class="cfg-switch-input" />
            <span class="cfg-switch" aria-hidden="true"></span>
            <div><p class="cfg-module-title">MEGA</p><p class="cfg-module-desc">MEGA / MEGAsync</p></div>
          </label>
          <label class="cfg-module-item">
            <input type="checkbox" id="ndOnedrive" class="cfg-switch-input" />
            <span class="cfg-switch" aria-hidden="true"></span>
            <div><p class="cfg-module-title">OneDrive</p><p class="cfg-module-desc">Microsoft OneDrive</p></div>
          </label>
          <label class="cfg-module-item">
            <input type="checkbox" id="ndGdrive" class="cfg-switch-input" />
            <span class="cfg-switch" aria-hidden="true"></span>
            <div><p class="cfg-module-title">Google Drive</p><p class="cfg-module-desc">Google Drive client</p></div>
          </label>
        </div>
        <div class="cfg-save-row" style="margin-top:16px;">
          <button id="saveNetdiskBtn" type="button">Save Netdisk config</button>
          <span id="netdiskStatus" class="status-bar muted"></span>
        </div>
      </div>
    </section>
  </div>
  <div id="toastContainer"></div>

  <script>
  (function(){
    "use strict";
    var __i18nReady = (window.fccI18n && window.fccI18n.initPage)
      ? window.fccI18n.initPage({ selectId: "langSelect" }).catch(function(){})
      : Promise.resolve();
    var THEME_KEY = "fc-theme";
    var HERO_THEME_KEY = "fc-hero-preset";
    var TAB_KEY = "fc-config-tab";
    var cfg = {
      web_port: 1288,
      modules: { qbt: true, ddns: true, shareclip: true, http: true },
      qbt: { monitor_enabled: true, client: "qbittorrent" },
      http_service: {
        root_dir: "/srv/Storage",
        default_dir: ".",
        source_ip_pools: { baidu: [], guangya: [], aliyun: [] },
        source_ip_pool_source: "github:EinProfispieler/afterclaw/data/vendor-ip-pools",
        transfer_recent_ttl_sec: 15
      },
      ui: {
        hero_preset: "default",
        hero_custom_bg_file: ""
      },
      terminal: {
        enabled: true,
        host: "127.0.0.1",
        user: "root",
        port: 22,
        auth_mode: "key",
        key_path: "~/.ssh/id_ed25519",
        key_file: ""
      },
      netdisk_sources: {
        baidu: true,
        ali: true,
        guangya: true,
        dropbox: false,
        mega: false,
        onedrive: false,
        gdrive: false
      }
    };
    var runtimeWebPort = 1288;
    var qbtDiscoverCache = null;
    var qbtSavedSignature = "";
    var qbtDragClient = "";
    var btConfigClient = "qbittorrent";
    var heroTheme = { hero_preset: "default", hero_custom_bg_file: "", hero_custom_bg_url: "" };
    var upgradeState = { supported: false, running: false, state: "idle", current_version: "", branch: "main", target_tag: "", release_url: "", message: "", error: "" };
    var upgradePollTimer = 0;

    function byId(id){ return document.getElementById(id); }
    function trRaw(text){
      var src = String(text || "");
      try {
        if (window.fccI18n && typeof window.fccI18n.translateRaw === "function") {
          return window.fccI18n.translateRaw(src) || src;
        }
      } catch (e) {}
      return src;
    }
    function showToast(msg, type){
      var text = String(msg || "").trim();
      if (!text) return;
      var container = byId("toastContainer");
      if (!container) return;
      var t = document.createElement("div");
      t.className = "toast " + (type === "error" ? "error" : "success");
      t.textContent = text;
      container.appendChild(t);
      setTimeout(function(){
        if (t.parentNode) t.parentNode.removeChild(t);
      }, 3000);
    }
    function setStatus(id, msg, isErr) {
      var el = byId(id);
      if (!el) return;
      var text = String(msg || "");
      el.textContent = text;
      el.className = isErr ? "cfg-status err" : "cfg-status";
      if (text.trim()) showToast(text, isErr ? "error" : "success");
    }
    function summarizeModuleActions(actions){
      var rows = Array.isArray(actions) ? actions : [];
      var msgs = [];
      var hasErr = false;
      rows.forEach(function(item){
        var m = String((item && item.message) || "").trim();
        if (m) msgs.push(m);
        if (item && item.ok === false) hasErr = true;
      });
      return { text: msgs.join("；"), has_error: hasErr };
    }
    function safeLocalGet(key, fallback){
      try {
        var v = localStorage.getItem(key);
        return v == null ? fallback : v;
      } catch (e) {
        return fallback;
      }
    }
    function getTheme(){ return safeLocalGet(THEME_KEY, "light"); }
    function applyTheme(t){
      document.documentElement.setAttribute("data-theme", t);
      try { localStorage.setItem(THEME_KEY, t); } catch (e) {}
    }
    function normalizeHeroPreset(v){
      var x = String(v || "").trim().toLowerCase();
      if (x === "aurora" || x === "sunset" || x === "frost" || x === "afterclaw_clouds") return x;
      return "default";
    }
    function setHeroThemeStatus(msg, isErr){
      var el = byId("cfgThemeStatus");
      if (!el) return;
      var text = String(msg || "");
      el.textContent = text;
      el.classList.toggle("err", !!isErr);
      if (text.trim()) showToast(text, isErr ? "error" : "success");
    }
    function syncHeroPresetButtons(){
      var preset = normalizeHeroPreset(heroTheme.hero_preset);
      Array.prototype.slice.call(document.querySelectorAll('#panel-general .theme-preset-btn')).forEach(function(btn){
        var p = normalizeHeroPreset(btn.getAttribute("data-hero-preset"));
        btn.classList.toggle("active", p === preset);
      });
    }
    function applyHeroTheme(uiTheme){
      var t = uiTheme || {};
      var preset = normalizeHeroPreset(t.hero_preset || "default");
      heroTheme = {
        hero_preset: preset,
        hero_custom_bg_file: "",
        hero_custom_bg_url: ""
      };
      document.documentElement.setAttribute("data-hero-preset", preset);
      try { localStorage.setItem(HERO_THEME_KEY, preset); } catch (e) {}
      document.documentElement.style.removeProperty("--hero-custom-url");
      var meta = byId("cfgThemeMeta");
      if (meta) {
        var labels = { default: "Default", aurora: "Aurora", sunset: "Sunset", frost: "Frost", afterclaw_clouds: "Clouds at Dusk" };
        meta.textContent = trRaw("Current theme: ") + trRaw(labels[preset] || "Default");
      }
      syncHeroPresetButtons();
    }
    async function apiJson(url, opts){
      var r = await fetch(url, opts || {});
      var d = await r.json().catch(function(){ return {}; });
      if (!r.ok) throw new Error((d && d.error) || ("Request failed " + r.status));
      return d;
    }
    function normalizeDirInput(raw){
      var v = String(raw || "").trim().replace(/\\\\/g, "/");
      if (!v || v === "/") return ".";
      if (v.startsWith("/")) v = v.slice(1);
      while (v.endsWith("/") && v !== ".") v = v.slice(0, -1);
      return v || ".";
    }
    function normalizeRootInput(raw){
      var v = String(raw || "").trim().replace(/\\\\/g, "/");
      if (!v) return "/";
      if (!v.startsWith("/")) v = "/" + v;
      v = v.replace(/\/+/g, "/");
      while (v.length > 1 && v.endsWith("/")) v = v.slice(0, -1);
      return v || "/";
    }
    function normalizeIpPoolEntries(value){
      var text = Array.isArray(value) ? value.join("\\n") : String(value || "");
      text = text.replace(/[，；]/g, ",").replace(/\|/g, " ");
      var rows = text.split(/[\\n,\\s;]+/g).map(function(s){ return String(s || "").trim(); }).filter(Boolean);
      var out = [];
      var seen = {};
      rows.forEach(function(item){
        if (!seen[item]) {
          seen[item] = true;
          out.push(item);
        }
      });
      return out;
    }
    function poolRowsToText(value){
      return normalizeIpPoolEntries(value).join("\\n");
    }
    function applySourceIpPoolsInputs(rawPools){
      var pools = rawPools || {};
      byId("httpPoolBaidu").value = poolRowsToText(pools.baidu || pools["Baidu Netdisk"] || []);
      byId("httpPoolGuangya").value = poolRowsToText(pools.guangya || pools["Guangya Netdisk"] || []);
      byId("httpPoolAliyun").value = poolRowsToText(pools.aliyun || pools["Aliyun Drive"] || []);
    }
    function collectSourceIpPoolsDraft(){
      return {
        baidu: normalizeIpPoolEntries(byId("httpPoolBaidu").value),
        guangya: normalizeIpPoolEntries(byId("httpPoolGuangya").value),
        aliyun: normalizeIpPoolEntries(byId("httpPoolAliyun").value)
      };
    }
    function normalizeSourceIpPoolSource(raw){
      var v = String(raw || "").trim();
      if (!v) v = "github:EinProfispieler/afterclaw/data/vendor-ip-pools";
      if (v.length > 500) v = v.slice(0, 500).trim();
      return v;
    }
    function applySourceIpPoolSourceInput(source){
      var el = byId("httpPoolSource");
      if (!el) return;
      el.value = normalizeSourceIpPoolSource(source);
    }
    function renderSourceIpPoolMeta(meta){
      var el = byId("httpPoolSourceMeta");
      if (!el) return;
      el.textContent = String(meta || "");
    }
    async function syncSourceIpPoolsFromRemote(){
      var sourceInput = byId("httpPoolSource");
      var source = normalizeSourceIpPoolSource(sourceInput ? sourceInput.value : "");
      if (sourceInput) sourceInput.value = source;
      setStatus("httpStatus", "Syncing source IP pools...");
      var d = await apiJson("/api/http/source-ip-pools/sync", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ source: source, merge: true })
      });
      applyCfg((d && d.config) || d);
      var counts = (d && d.counts) || {};
      var remoteCounts = (d && d.remote_counts) || {};
      var mode = String((d && d.mode) || "merge");
      var summary = "Source sync completed: Baidu " + Number(counts.baidu || 0)
        + " · Guangya " + Number(counts.guangya || 0)
        + " · Aliyun " + Number(counts.aliyun || 0);
      var files = (d && Array.isArray(d.files_used)) ? d.files_used : [];
      var meta = "Current source: " + source;
      if (files.length) {
        meta += " | matched files " + files.length;
      }
      if (mode === "merge") {
        meta += " | merge mode (remote additions: Baidu " + Number(remoteCounts.baidu || 0)
          + " · Guangya " + Number(remoteCounts.guangya || 0)
          + " · Aliyun " + Number(remoteCounts.aliyun || 0) + ")";
      }
      renderSourceIpPoolMeta(meta);
      setStatus("httpStatus", summary);
    }
    function currentHttpRoot(){
      var input = byId("httpRootDir");
      var fromInput = input ? String(input.value || "").trim() : "";
      if (fromInput) return normalizeRootInput(fromInput);
      var shown = byId("httpStorageRoot");
      var fromShown = shown ? String(shown.textContent || "").trim() : "";
      return normalizeRootInput(fromShown || "/");
    }
    function normalizePort(raw, fallback){
      var f = Number(fallback);
      if (!Number.isFinite(f)) f = 22;
      f = Math.trunc(f);
      if (f < 1 || f > 65535) f = 22;
      var n = Number(raw);
      if (!Number.isFinite(n)) return f;
      n = Math.trunc(n);
      if (n < 1 || n > 65535) return f;
      return n;
    }
    function parsePort(raw){
      return normalizePort(raw, 22);
    }
    function parseWebPort(raw, fallback){
      return normalizePort(raw, fallback || 1288);
    }
    function parseTransferRecentTtlSec(raw, fallback){
      var f = Number(fallback);
      if (!Number.isFinite(f)) f = 15;
      var n = Number(raw);
      if (!Number.isFinite(n)) n = f;
      n = Math.round(n * 10) / 10;
      if (n < 0) n = 0;
      if (n > 600) n = 600;
      return n;
    }
    function updateWebPortHint(){
      var hint = byId("webPortHint");
      if (!hint) return;
      var desired = parseWebPort(byId("webPortInput") ? byId("webPortInput").value : cfg.web_port, cfg.web_port || 1288);
      var msg = "Current runtime port: " + String(runtimeWebPort) + ".";
      if (desired !== runtimeWebPort) {
        msg += " Restart required after save; will switch to: " + String(desired) + ".";
      } else {
        msg += " Saved value matches the runtime port.";
      }
      hint.textContent = msg;
    }
    function normalizeUpgradeBranchInput(raw){
      var v = String(raw || "").trim().toLowerCase();
      if (v === "nightly") return "nightly";
      return "main";
    }
    function stopUpgradePolling(){
      if (upgradePollTimer) {
        clearTimeout(upgradePollTimer);
        upgradePollTimer = 0;
      }
    }
    function renderUpgradeStatus(status){
      var s = status || {};
      upgradeState = {
        supported: !!s.supported,
        running: !!s.running,
        state: String(s.state || (s.running ? "running" : "idle")),
        current_version: String(s.current_version || ""),
        branch: normalizeUpgradeBranchInput(s.branch || "main"),
        target_tag: String(s.target_tag || ""),
        release_url: String(s.release_url || ""),
        message: String(s.message || ""),
        error: String(s.error || ""),
        support_reason: String(s.support_reason || "")
      };
      if (byId("upgradeBranchSelect")) {
        byId("upgradeBranchSelect").value = normalizeUpgradeBranchInput(upgradeState.branch || "main");
      }
      var statusText = "";
      var isErr = false;
      if (!upgradeState.supported) {
        statusText = "Auto-update unavailable" + (upgradeState.support_reason ? "：" + upgradeState.support_reason : "");
        isErr = true;
      } else if (upgradeState.running) {
        statusText = "Update in progress";
        if (upgradeState.target_tag) statusText += "：" + upgradeState.target_tag;
        if (upgradeState.message) statusText += " · " + upgradeState.message;
      } else if (upgradeState.state === "success") {
        statusText = upgradeState.message || ("Update completed: " + (upgradeState.target_tag || "latest"));
      } else if (upgradeState.state === "error") {
        statusText = upgradeState.error ? ("Update failed: " + upgradeState.error) : "Update failed";
        isErr = true;
      } else {
        statusText = upgradeState.message || "Waiting to run update";
      }
      var statusEl = byId("upgradeStatus");
      if (statusEl) {
        statusEl.textContent = statusText;
        statusEl.className = isErr ? "cfg-status err" : "cfg-status";
      }
      var meta = [];
      if (upgradeState.branch) meta.push("Update branch: " + upgradeState.branch);
      if (upgradeState.target_tag) meta.push("Target tag: " + upgradeState.target_tag);
      if (s.started_at) meta.push("Started: " + String(s.started_at));
      if (s.finished_at) meta.push("Finished: " + String(s.finished_at));
      if (upgradeState.release_url) meta.push("Release：" + upgradeState.release_url);
      if (byId("upgradeMeta")) byId("upgradeMeta").textContent = meta.join(" | ");
      if (byId("runUpgradeBtn")) {
        byId("runUpgradeBtn").disabled = (!upgradeState.supported) || !!upgradeState.running;
      }
      if (byId("refreshUpgradeStatusBtn")) {
        byId("refreshUpgradeStatusBtn").disabled = false;
      }
    }
    async function loadUpgradeStatus(silent){
      var d = await apiJson("/api/upgrade/status");
      renderUpgradeStatus(d || {});
      if (!silent && upgradeState.running) {
        setStatus("upgradeStatus", "Upgrade is in progress. Please keep this page open.");
      }
      if (upgradeState.running) {
        stopUpgradePolling();
        upgradePollTimer = setTimeout(function(){
          loadUpgradeStatus(true).catch(function(){});
        }, 2000);
      } else {
        stopUpgradePolling();
      }
      return d || {};
    }
    async function checkServerVersion(){
      var branch = normalizeUpgradeBranchInput(byId("upgradeBranchSelect") ? byId("upgradeBranchSelect").value : "main");
      var d = await apiJson("/api/upgrade/check-version?branch=" + encodeURIComponent(branch));
      var latest = String((d && d.available_version) || "-");
      var running = String((d && d.current_version) || "-");
      var currentBranch = normalizeUpgradeBranchInput((d && d.current_branch) || "");
      var selectedLabel = branch === "nightly" ? "nightly" : "main";
      var currentLabel = currentBranch === "nightly" ? "nightly" : "main";
      if (d && d.ok === false) {
        setStatus("upgradeStatus", "Version check failed: " + String(d.error || "unknown error"), true);
      } else if (currentBranch !== branch) {
        setStatus(
          "upgradeStatus",
          "Selected " + selectedLabel + " latest: " + latest + ". Current server is " + currentLabel + ": " + running + ".",
          false
        );
      } else {
        setStatus(
          "upgradeStatus",
          "Selected " + selectedLabel + " latest: " + latest + ". Current server: " + running + ".",
          false
        );
      }
      var meta = [];
      meta.push("Selected branch: " + branch);
      meta.push("Selected latest: " + latest);
      meta.push("Current branch: " + currentLabel);
      meta.push("Current server: " + running);
      if (currentBranch !== branch) meta.push("Note: current branch differs from selected branch");
      if (d && d.release_url) meta.push("URL: " + String(d.release_url));
      if (d && d.checked_at) meta.push("Checked: " + String(d.checked_at));
      if (byId("upgradeMeta")) byId("upgradeMeta").textContent = meta.join(" | ");
      return d || {};
    }
    async function runAutoUpgrade(){
      var branch = normalizeUpgradeBranchInput(byId("upgradeBranchSelect") ? byId("upgradeBranchSelect").value : "main");
      var branchLabel = branch === "nightly" ? "nightly branch" : "main branch";
      if (!window.confirm("Confirm auto-update? Will pull " + branchLabel + " from default repository and run install.sh (service may restart).")) {
        return null;
      }
      setStatus("upgradeStatus", "Submitting update job...");
      var d = await apiJson("/api/upgrade/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ branch: branch })
      });
      renderUpgradeStatus((d && d.status) || {});
      if (d && d.queued) {
        setStatus("upgradeStatus", "Update job queued and running.");
      } else {
        setStatus("upgradeStatus", "An update task is already running, or auto-update is unsupported in current environment.", true);
      }
      if (upgradeState.running) {
        stopUpgradePolling();
        upgradePollTimer = setTimeout(function(){
          loadUpgradeStatus(true).catch(function(){});
        }, 1200);
      }
      return d;
    }
    function shellQuote(s){
      var v = String(s || "");
      if (!v) return "''";
      // POSIX shell safe single-quote escaping: abc'd -> 'abc'\''d'
      return "'" + v.replace(/'/g, "'\\\\''") + "'";
    }
    function parentDirOf(dir){
      var v = normalizeDirInput(dir);
      if (v === ".") return ".";
      var arr = v.split("/").filter(Boolean);
      arr.pop();
      return arr.length ? arr.join("/") : ".";
    }
    async function copyTextSmart(text){
      var value = String(text || "");
      if (!value) return false;
      try {
        if (navigator.clipboard && window.isSecureContext) {
          await navigator.clipboard.writeText(value);
          return true;
        }
      } catch (e) {}
      try {
        var ta = document.createElement("textarea");
        ta.value = value;
        ta.setAttribute("readonly", "");
        ta.style.position = "fixed";
        ta.style.top = "-9999px";
        ta.style.left = "-9999px";
        document.body.appendChild(ta);
        ta.focus();
        ta.select();
        var ok = document.execCommand("copy");
        document.body.removeChild(ta);
        return !!ok;
      } catch (e) {
        return false;
      }
    }
    function applyTerminalKeyMeta(meta){
      var m = meta || {};
      if (byId("termKeyDirText")) {
        byId("termKeyDirText").textContent = String(m.key_dir || "terminal_keys");
      }
      var fileList = byId("termKeyFileList");
      if (fileList) {
        fileList.innerHTML = "";
        (m.key_files || []).forEach(function(name){
          var opt = document.createElement("option");
          opt.value = String(name || "");
          fileList.appendChild(opt);
        });
      }
    }
    function bytesToBase64(bytes){
      var out = "";
      var chunkSize = 0x8000;
      for (var i = 0; i < bytes.length; i += chunkSize) {
        var chunk = bytes.subarray(i, i + chunkSize);
        out += String.fromCharCode.apply(null, chunk);
      }
      return btoa(out);
    }
    function uiThemeFromConfigPayload(payload){
      var c = ((payload || {}).config || payload || {});
      var ui = (c && c.ui) || {};
      return {
        hero_preset: normalizeHeroPreset(ui.hero_preset || "default"),
        hero_custom_bg_file: String(ui.hero_custom_bg_file || ""),
        hero_custom_bg_url: heroTheme.hero_custom_bg_url || ""
      };
    }
    async function setHeroPresetFromConfig(preset){
      var p = normalizeHeroPreset(preset);
      var d = await apiJson("/api/app-config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ui: { hero_preset: p } })
      });
      applyCfg((d && d.config) || d);
      applyHeroTheme((d && d.ui_theme) || uiThemeFromConfigPayload(d));
      var labels = { default: "Default", aurora: "Aurora", sunset: "Sunset", frost: "Frost", afterclaw_clouds: "Clouds at Dusk" };
      setHeroThemeStatus(trRaw("Switched theme: ") + trRaw(labels[p] || "Default"));
    }
    async function uploadHeroImageFromFile(file){
      if (!file) throw new Error("Please select a local image first");
      var name = String(file.name || "").trim();
      if (!/\\.(png|jpe?g|webp|gif|avif)$/i.test(name)) {
        throw new Error("Only PNG/JPG/WEBP/GIF/AVIF are supported");
      }
      var maxBytes = 12 * 1024 * 1024;
      if (file.size > maxBytes) throw new Error("Image is too large (max 12MB)");
      var bytes = new Uint8Array(await file.arrayBuffer());
      var b64 = bytesToBase64(bytes);
      var d = await apiJson("/api/ui/theme-background", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ file_name: name, content_b64: b64, apply: true })
      });
      applyCfg((d && d.config) || d);
      applyHeroTheme((d && d.ui_theme) || uiThemeFromConfigPayload(d));
      setHeroThemeStatus("Background updated: " + name);
    }
    async function resetHeroToDefault(){
      var d = await apiJson("/api/app-config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ui: { hero_preset: "default", hero_custom_bg_file: "" } })
      });
      applyCfg((d && d.config) || d);
      applyHeroTheme((d && d.ui_theme) || uiThemeFromConfigPayload(d));
      if (byId("cfgThemeBgFileInput")) byId("cfgThemeBgFileInput").value = "";
      setHeroThemeStatus("Background restored to default");
    }
    async function uploadTerminalKeyFromFile(file){
      if (!file) return;
      var maxBytes = 1024 * 1024;
      if (file.size > maxBytes) {
        throw new Error("Key file is too large (max 1MB)");
      }
      var fileName = String(file.name || "").trim();
      if (!fileName) {
        throw new Error("Unable to read key filename");
      }
      var bytes = new Uint8Array(await file.arrayBuffer());
      var b64 = bytesToBase64(bytes);
      var d = await apiJson("/api/terminal/key-file", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ file_name: fileName, content_b64: b64 })
      });
      if (d.terminal) {
        applyTerminalKeyMeta(d.terminal);
        renderTerminalLinks(d.terminal);
        byId("terminalPreviewCmd").textContent = d.terminal.command || byId("terminalPreviewCmd").textContent;
      } else {
        await loadBaseInfo();
      }
      if (byId("termKeyFile")) {
        byId("termKeyFile").value = String(d.file_name || fileName);
      }
      refreshTerminalPreview();
      setStatus("terminalStatus", "Key file uploaded: " + String(d.file_name || fileName));
    }
    function collectTerminalDraft(){
      return {
        enabled: !!byId("termEnabled").checked,
        host: String(byId("termHost").value || "").trim(),
        user: String(byId("termUser").value || "").trim() || "root",
        port: parsePort(byId("termPort").value),
        auth_mode: String(byId("termAuthMode").value || "key"),
        key_path: String(byId("termKeyPath").value || "").trim(),
        key_file: String(byId("termKeyFile").value || "").trim()
      };
    }
    function buildTerminalMetaFromDraft(term){
      var t = term || {};
      var enabled = t.enabled !== false;
      var host = String(t.host || "").trim();
      var user = String(t.user || "").trim() || "root";
      var port = parsePort(t.port);
      var auth = String(t.auth_mode || "key").toLowerCase();
      if (auth !== "password") auth = "key";
      var keyPath = String(t.key_path || "").trim();
      var keyFile = String(t.key_file || "").trim();
      var keyDir = String((byId("termKeyDirText") && byId("termKeyDirText").textContent) || "terminal_keys");
      var keyFromConfigDir = keyFile ? (keyDir.replace(/\/$/, "") + "/" + keyFile) : "";
      var keyEffective = keyFromConfigDir || keyPath;
      var display = "";
      var link = "";
      var command = "";
      if (host) {
        display = user + "@" + host + ":" + port;
        link = "ssh://" + encodeURIComponent(user) + "@" + host + ":" + port;
        if (auth === "key" && keyEffective) {
          command = "ssh -i " + shellQuote(keyEffective) + " -p " + port + " " + shellQuote(user + "@" + host);
        } else {
          command = "ssh -p " + port + " " + shellQuote(user + "@" + host);
        }
      }
      return {
        enabled: enabled,
        host: host,
        user: user,
        port: port,
        auth_mode: auth,
        key_path: keyPath,
        key_file: keyFile,
        key_dir: keyDir,
        display: display,
        link: link,
        command: command,
        tip: auth === "password"
          ? "Password mode does not store password. Enter it manually in terminal."
          : (keyFile ? ("Using config-directory key: " + keyFile) : "Key mode is recommended. Make sure your public key is authorized on target host.")
      };
    }
    function renderTerminalLinks(meta){
      var m = meta || {};
      var preview = byId("terminalPreviewLink");
      var head = byId("terminalHeadLink");
      var webLink = byId("terminalWebLink");
      var enabled = m.enabled !== false;
      var host = String(m.host || "").trim();
      if (preview) {
        if (m.enabled && m.link) {
          preview.href = m.link;
          preview.textContent = m.display || m.link;
        } else {
          preview.href = "#terminal";
          preview.textContent = "Not configured";
        }
      }
      if (webLink) {
        if (enabled && host) {
          webLink.href = "/terminal";
          webLink.textContent = "Open /terminal";
        } else {
          webLink.href = "#terminal";
          webLink.textContent = "Configure and enable Terminal first";
        }
      }
      if (head) {
        if (enabled && host) {
          head.href = "/terminal";
          head.target = "_self";
          head.rel = "";
          head.classList.remove("inactive");
        } else {
          head.href = "#terminal";
          head.target = "_self";
          head.rel = "";
          head.classList.add("inactive");
        }
        head.title = m.enabled
          ? (m.command ? ("Terminal: " + m.command) : "Terminal")
          : "Terminal (disabled)";
      }
    }
    function refreshTerminalPreview(){
      var draft = collectTerminalDraft();
      var m = buildTerminalMetaFromDraft(draft);
      byId("terminalTip").textContent = m.tip;
      byId("terminalPreviewCmd").textContent = m.command || "Not configured";
      byId("termKeyFileItem").style.display = m.auth_mode === "key" ? "" : "none";
      byId("termKeyPathItem").style.display = m.auth_mode === "key" ? "" : "none";
      renderTerminalLinks(m);
    }
    function renderHttpDirList(currentDir, dirs){
      var wrap = byId("httpDirList");
      if (!wrap) return;
      wrap.innerHTML = "";
      var rows = Array.isArray(dirs) ? dirs : [];
      if (!rows.length) {
        var empty = document.createElement("div");
        empty.className = "muted";
        empty.textContent = "(No subdirectories in current directory)";
        wrap.appendChild(empty);
        return;
      }
      rows.forEach(function(dir){
        var btn = document.createElement("button");
        btn.type = "button";
        btn.className = "dir-item";
        btn.dataset.dir = dir;
        var parts = String(dir).split("/").filter(Boolean);
        var nameSpan = document.createElement("span");
        nameSpan.className = "dir-name";
        nameSpan.textContent = parts.length ? parts[parts.length - 1] : dir;
        var pathSpan = document.createElement("span");
        pathSpan.className = "dir-path";
        pathSpan.textContent = dir;
        btn.appendChild(nameSpan);
        btn.appendChild(pathSpan);
        btn.addEventListener("click", function(){
          byId("httpDefaultDir").value = dir;
          loadHttpDirBrowser(dir, true).catch(function(err){
            setStatus("httpStatus", "Load failed: " + err.message, true);
          });
          setStatus("httpStatus", "Selected default directory: " + dir);
        });
        wrap.appendChild(btn);
      });
    }
    function renderHttpScanResult(d){
      var el = byId("httpScanResult");
      if (!el) return;
      if (!d) { el.textContent = ""; return; }
      var parts = [];
      parts.push("Path: " + String(d.path || "-"));
      if (!d.exists) {
        parts.push("Not found");
      } else if (!d.is_dir) {
        parts.push("Not a directory");
      } else {
        var perm = (d.can_read ? "r" : "-") + (d.can_write ? "w" : "-") + (d.can_exec ? "x" : "-");
        parts.push("Permissions(" + perm + ")");
        if (d.can_list) {
          parts.push("Subdirs " + String(d.child_dir_count || 0) + " · Files " + String(d.child_file_count || 0) + (d.truncated ? " (truncated)" : ""));
        } else {
          parts.push("Cannot list directory");
        }
        if (d.fs_total_human && d.fs_avail_human) {
          parts.push("Available " + d.fs_avail_human + " / Total " + d.fs_total_human);
        }
      }
      if (d.error) parts.push("Note: " + String(d.error));
      if (Array.isArray(d.sample_dirs) && d.sample_dirs.length) {
        parts.push("Sample subdirectories: " + d.sample_dirs.slice(0, 6).join(", "));
      }
      el.textContent = parts.join(" | ");
    }
    async function scanHttpRootPath(silent){
      var root = normalizeRootInput(byId("httpRootDir").value || "/");
      var d = await apiJson("/api/http/path-scan?path=" + encodeURIComponent(root));
      var scanned = normalizeRootInput((d && d.path) || root);
      byId("httpRootDir").value = scanned;
      byId("httpStorageRoot").textContent = scanned;
      renderHttpScanResult(d);
      if (!silent) {
        if (d && d.ok) setStatus("httpStatus", "Path validation passed, usable as HTTP root");
        else setStatus("httpStatus", "Path validation failed: " + String((d && d.error) || "inaccessible"), true);
      }
      return d || {};
    }
    async function loadHttpDirBrowser(dir, silent){
      var target = normalizeDirInput(dir || byId("httpBrowseDir").value || byId("httpDefaultDir").value || ".");
      var root = currentHttpRoot();
      var d;
      try {
        d = await apiJson("/api/directories?stats=0&root_dir=" + encodeURIComponent(root) + "&dir=" + encodeURIComponent(target));
      } catch (err) {
        if (target !== ".") {
          target = ".";
          d = await apiJson("/api/directories?stats=0&root_dir=" + encodeURIComponent(root) + "&dir=" + encodeURIComponent(target));
          setStatus("httpStatus", "Default directory is inaccessible, fallback to root.", true);
        } else {
          throw err;
        }
      }
      var cur = normalizeDirInput((d && d.current_dir) || target);
      var effectiveRoot = normalizeRootInput((d && d.http_root_dir) || root);
      byId("httpStorageRoot").textContent = effectiveRoot;
      if (byId("httpRootDir")) byId("httpRootDir").value = effectiveRoot;
      byId("httpBrowseDir").value = cur;
      renderHttpDirList(cur, (d && d.directories) || []);
      if (!silent) setStatus("httpStatus", "Loaded directory: " + effectiveRoot + " / " + cur);
    }
    function setSelectOptions(selectId, rows, selectedValue){
      var el = byId(selectId);
      if (!el) return;
      var list = Array.isArray(rows) ? rows : [];
      var selected = String(selectedValue || "");
      el.innerHTML = "";
      list.forEach(function(item){
        var opt = document.createElement("option");
        var val = String((item && item.value) || "");
        var label = String((item && item.label) || val || "(auto)");
        opt.value = val;
        opt.textContent = label;
        if (val === selected) opt.selected = true;
        el.appendChild(opt);
      });
      if (!el.value && list.length) el.value = String((list[0] && list[0].value) || "");
    }
    function qbtDraftPayload(){
      var en = qbtHomeEnabledMap(((cfg.qbt || {}).homepage_clients_enabled) || {});
      var order = normalizeQbtHomeOrder(((cfg.qbt || {}).homepage_clients_order) || []);
      return {
        client: String(btConfigClient || "qbittorrent").trim(),
        service_unit: (byId("qbtServiceUnit").value || "").trim(),
        docker_container: (byId("qbtDockerContainer").value || "").trim(),
        api_url: (byId("qbtApiUrl").value || "").trim(),
        homepage_clients_enabled: en,
        homepage_clients_order: order
      };
    }
    function qbtSignatureFromPayload(payload){
      var p = payload || {};
      return JSON.stringify({
        client: String(p.client || "qbittorrent"),
        service_unit: String(p.service_unit || ""),
        docker_container: String(p.docker_container || ""),
        api_url: String(p.api_url || ""),
        homepage_clients_enabled: qbtHomeEnabledMap(p.homepage_clients_enabled || {}),
        homepage_clients_order: normalizeQbtHomeOrder(p.homepage_clients_order || [])
      });
    }
    function updateQbtOptimizeState(){
      var btn = byId("qbtOptimizeBtn");
      if (!btn) return;
      var dirty = qbtSignatureFromPayload(qbtDraftPayload()) !== qbtSavedSignature;
      btn.dataset.dirty = dirty ? "1" : "0";
      btn.title = dirty ? trRaw("Save settings first, then optimize.") : "";
      updateQbtOptimizeTargetText();
    }
    function qbtClientLabel(k){
      var map = { qbittorrent: "qBittorrent", deluge: "Deluge", transmission: "Transmission", rtorrent: "rTorrent" };
      return map[String(k || "").toLowerCase()] || String(k || "");
    }
    function updateQbtOptimizeTargetText(){
      var el = byId("qbtOptimizeTarget");
      var btn = byId("qbtOptimizeBtn");
      if (!el || !btn) return;
      var client = String(btConfigClient || "qbittorrent").trim();
      var svc = String((byId("qbtServiceUnit") && byId("qbtServiceUnit").value) || "").trim() || "auto";
      var docker = String((byId("qbtDockerContainer") && byId("qbtDockerContainer").value) || "").trim() || "auto";
      el.textContent = trRaw("Optimize target: ") + qbtClientLabel(client) + " | " + trRaw("service") + " " + svc + " | " + trRaw("docker") + " " + docker;
      btn.textContent = trRaw("Optimize") + " " + qbtClientLabel(client);
    }
    function normalizeQbtHomeOrder(orderRaw){
      var allowed = ["qbittorrent","deluge","transmission","rtorrent"];
      var out = [];
      var seen = {};
      var list = Array.isArray(orderRaw) ? orderRaw : [];
      list.forEach(function(x){
        var k = String(x || "").trim().toLowerCase();
        if (allowed.indexOf(k) >= 0 && !seen[k]) {
          seen[k] = true;
          out.push(k);
        }
      });
      allowed.forEach(function(k){ if (!seen[k]) out.push(k); });
      return out;
    }
    function qbtHomeEnabledMap(raw){
      var m = raw || {};
      return {
        qbittorrent: !!m.qbittorrent,
        deluge: !!m.deluge,
        transmission: !!m.transmission,
        rtorrent: !!m.rtorrent
      };
    }
    function renderQbtHomeClientList(){
      var wrap = byId("qbtHomeClientList");
      if (!wrap) return;
      var q = cfg.qbt || {};
      var order = normalizeQbtHomeOrder(q.homepage_clients_order || []);
      var enabled = qbtHomeEnabledMap(q.homepage_clients_enabled || {});
      wrap.innerHTML = "";
      order.forEach(function(k){
        var chip = document.createElement("div");
        chip.className = "xfer-sort-group" + (k === btConfigClient ? " active" : "");
        chip.draggable = true;
        chip.dataset.client = k;
        chip.style.padding = "10px 16px";
        chip.style.borderRadius = "999px";
        chip.style.display = "flex";
        chip.style.alignItems = "center";
        chip.style.gap = "8px";
        chip.style.userSelect = "none";
        chip.style.cursor = "pointer";
        if (k === btConfigClient) {
          chip.style.background = "linear-gradient(135deg, rgba(37,99,235,0.28), rgba(37,99,235,0.16))";
          chip.style.borderColor = "rgba(37,99,235,0.9)";
          chip.style.boxShadow = "0 0 0 1px rgba(37,99,235,0.65) inset";
        }
        chip.innerHTML = '<label style="display:flex;align-items:center;gap:8px;cursor:pointer;"><input type="checkbox" class="qbt-home-client-check" data-client="' + k + '"' + (enabled[k] ? ' checked' : '') + ' /> <span>' + qbtClientLabel(k) + '</span></label><span class="muted" style="font-size:12px;">↔</span>';
        chip.addEventListener("click", async function(e){
          if (e && e.target && String(e.target.tagName || "").toLowerCase() === "input") return;
          if (btConfigClient === k) return;
          btConfigClient = k;
          qbtDiscoverCache = null;
          renderQbtHomeClientList();
          updateQbtOptimizeState();
          try { await loadQbtDiscover(true); } catch (err) { setStatus("qbtStatus", "Detect failed: " + err.message, true); }
        });
        chip.addEventListener("dragstart", function(){ qbtDragClient = k; });
        chip.addEventListener("dragover", function(e){ e.preventDefault(); });
        chip.addEventListener("drop", function(e){
          e.preventDefault();
          var from = qbtDragClient;
          var to = k;
          if (!from || from === to) return;
          var arr = normalizeQbtHomeOrder((cfg.qbt || {}).homepage_clients_order || []);
          var i = arr.indexOf(from), j = arr.indexOf(to);
          if (i < 0 || j < 0) return;
          arr.splice(i, 1);
          arr.splice(j, 0, from);
          cfg.qbt.homepage_clients_order = arr;
          renderQbtHomeClientList();
          updateQbtOptimizeState();
        });
        wrap.appendChild(chip);
      });
      Array.prototype.slice.call(wrap.querySelectorAll(".qbt-home-client-check")).forEach(function(el){
        el.addEventListener("change", function(){
          var key = String(el.getAttribute("data-client") || "").trim().toLowerCase();
          if (!cfg.qbt.homepage_clients_enabled) cfg.qbt.homepage_clients_enabled = {};
          cfg.qbt.homepage_clients_enabled[key] = !!el.checked;
          updateQbtOptimizeState();
        });
      });
    }
    function applyQbtDiscoverOptions(data, currentCfg){
      var d = data || {};
      var c = currentCfg || cfg.qbt || {};
      var noneOpt = [{ value: "", label: "Auto detect (recommended)" }];
      var svc = noneOpt.concat((d.service_units || []).map(function(v){
        var x = String(v || "");
        return { value: x, label: x };
      }));
      var docker = noneOpt.concat((d.docker_containers || []).map(function(v){
        var x = String(v || "");
        return { value: x, label: x };
      }));
      var urls = noneOpt.concat((d.api_urls || []).map(function(v){
        var x = String(v || "");
        return { value: x, label: x };
      }));
      setSelectOptions("qbtServiceUnit", svc, String(c.service_unit || ""));
      setSelectOptions("qbtDockerContainer", docker, String(c.docker_container || ""));
      setSelectOptions("qbtApiUrl", urls, String(c.api_url || ""));
    }
    async function loadQbtDiscover(forceRefresh){
      if (!forceRefresh && qbtDiscoverCache) {
        applyQbtDiscoverOptions(qbtDiscoverCache, cfg.qbt || {});
        return qbtDiscoverCache;
      }
      var client = String(btConfigClient || (cfg.qbt && cfg.qbt.client) || "qbittorrent").trim();
      var d = await apiJson("/api/qbt/discover?client=" + encodeURIComponent(client));
      qbtDiscoverCache = d || {};
      applyQbtDiscoverOptions(qbtDiscoverCache, cfg.qbt || {});
      return qbtDiscoverCache;
    }
    function applyCfg(data){
      var c = data || {};
      cfg.web_port = parseWebPort(c.web_port, cfg.web_port || 1288);
      cfg.modules = c.modules || cfg.modules;
      cfg.qbt = c.qbt || cfg.qbt;
      cfg.http_service = c.http_service || cfg.http_service;
      cfg.ui = c.ui || cfg.ui;
      cfg.terminal = c.terminal || cfg.terminal;
      cfg.netdisk_sources = c.netdisk_sources || cfg.netdisk_sources;
      if (byId("webPortInput")) byId("webPortInput").value = String(cfg.web_port);
      byId("modQbt").checked = cfg.modules.qbt !== false;
      byId("modDdns").checked = cfg.modules.ddns !== false;
      byId("modShareclip").checked = cfg.modules.shareclip !== false;
      byId("modHttp").checked = cfg.modules.http !== false;
      btConfigClient = String(cfg.qbt.client || "qbittorrent").toLowerCase();
      if (!["qbittorrent","deluge","transmission","rtorrent"].includes(btConfigClient)) btConfigClient = "qbittorrent";
      cfg.qbt.homepage_clients_enabled = qbtHomeEnabledMap(cfg.qbt.homepage_clients_enabled || {});
      cfg.qbt.homepage_clients_order = normalizeQbtHomeOrder(cfg.qbt.homepage_clients_order || []);
      applyQbtDiscoverOptions(qbtDiscoverCache || {}, cfg.qbt || {});
      updateQbtOptimizeTargetText();
      renderQbtHomeClientList();
      qbtSavedSignature = qbtSignatureFromPayload({
        client: String(cfg.qbt.client || "qbittorrent"),
        service_unit: String(cfg.qbt.service_unit || ""),
        docker_container: String(cfg.qbt.docker_container || ""),
        api_url: String(cfg.qbt.api_url || ""),
        homepage_clients_enabled: cfg.qbt.homepage_clients_enabled,
        homepage_clients_order: cfg.qbt.homepage_clients_order
      });
      updateQbtOptimizeState();
      byId("httpRootDir").value = normalizeRootInput((cfg.http_service || {}).root_dir || "/srv/Storage");
      byId("httpDefaultDir").value = normalizeDirInput((cfg.http_service || {}).default_dir || ".");
      cfg.http_service.transfer_recent_ttl_sec = parseTransferRecentTtlSec((cfg.http_service || {}).transfer_recent_ttl_sec, 15);
      if (byId("transferRecentTtlSec")) {
        byId("transferRecentTtlSec").value = String(cfg.http_service.transfer_recent_ttl_sec);
      }
      applySourceIpPoolsInputs((cfg.http_service || {}).source_ip_pools || {});
      applySourceIpPoolSourceInput((cfg.http_service || {}).source_ip_pool_source || "");
      renderSourceIpPoolMeta("Current source: " + normalizeSourceIpPoolSource((cfg.http_service || {}).source_ip_pool_source || ""));
      byId("httpBrowseDir").value = byId("httpDefaultDir").value;
      var term = cfg.terminal || {};
      byId("termEnabled").checked = term.enabled !== false;
      byId("termHost").value = String(term.host || "");
      byId("termUser").value = String(term.user || "root");
      byId("termPort").value = String(parsePort(term.port || 22));
      byId("termAuthMode").value = String(term.auth_mode || "key") === "password" ? "password" : "key";
      byId("termKeyPath").value = String(term.key_path || "");
      byId("termKeyFile").value = String(term.key_file || "");
      refreshTerminalPreview();
      applyHeroTheme({
        hero_preset: normalizeHeroPreset((cfg.ui || {}).hero_preset || "default"),
        hero_custom_bg_file: String((cfg.ui || {}).hero_custom_bg_file || ""),
        hero_custom_bg_url: heroTheme.hero_custom_bg_url || ""
      });
      var ns = cfg.netdisk_sources || {};
      byId("ndBaidu").checked = ns.baidu !== false;
      byId("ndAli").checked = ns.ali !== false;
      byId("ndGuangya").checked = ns.guangya !== false;
      byId("ndDropbox").checked = ns.dropbox !== false;
      byId("ndMega").checked = ns.mega !== false;
      byId("ndOnedrive").checked = ns.onedrive !== false;
      byId("ndGdrive").checked = ns.gdrive !== false;
      updateWebPortHint();
    }
    async function loadCfg(){
      var d = await apiJson("/api/app-config");
      applyCfg(d.config || d);
      await loadQbtDiscover(false);
    }
    async function loadBaseInfo(){
      var d = await apiJson("/api/base");
      runtimeWebPort = parseWebPort(d.web_port, runtimeWebPort || cfg.web_port || 1288);
      var root = normalizeRootInput(d.http_root_dir || d.storage_root || "/");
      byId("httpStorageRoot").textContent = root;
      if (byId("httpRootDir")) {
        byId("httpRootDir").value = root;
      }
      if (d.terminal) {
        applyTerminalKeyMeta(d.terminal);
        if (byId("termKeyFile") && !(byId("termKeyFile").value || "").trim()) {
          byId("termKeyFile").value = String(d.terminal.key_file || "");
        }
        renderTerminalLinks(d.terminal);
        byId("terminalPreviewCmd").textContent = d.terminal.command || byId("terminalPreviewCmd").textContent;
      }
      applyHeroTheme(d.ui_theme || {
        hero_preset: normalizeHeroPreset(((cfg.ui || {}).hero_preset || "default")),
        hero_custom_bg_file: String(((cfg.ui || {}).hero_custom_bg_file || "")),
        hero_custom_bg_url: ""
      });
      updateWebPortHint();
    }
    async function loadQbtRuntime(){
      try {
        var d = await apiJson("/api/control/status");
        var q = d.qbt || {};
        var line = (q.active_state === "active" ? "Running" : "Stopped") + " | " + (q.unit || "-");
        if (q.detail) line += " | " + q.detail;
        byId("qbtRuntimeStatus").textContent = trRaw(line);
      } catch (err) {
        byId("qbtRuntimeStatus").textContent = trRaw("Load failed:") + " " + err.message;
      }
    }
    async function loadQbtUpgradeStatus(silent){
      try {
        var d = await apiJson("/api/qbt/client-upgrade/status");
        renderQbtUpgradeStatus(d || {});
      } catch (err) {
        if (!silent) setStatus("qbtStatus", "Load client upgrade status failed: " + err.message, true);
      }
    }
    function qbtUpgradePayload(){
      return {
        client: String(btConfigClient || "qbittorrent").trim(),
        docker_container: String((byId("qbtDockerContainer") && byId("qbtDockerContainer").value) || "").trim()
      };
    }
    function renderQbtUpgradeStatus(d){
      var el = byId("qbtUpgradeStatus");
      if (!el) return;
      var rec = d || {};
      var parts = [];
      if (rec.client) parts.push("Client: " + qbtClientLabel(rec.client));
      if (rec.container) parts.push("Container: " + rec.container);
      if (rec.image) parts.push("Image: " + rec.image);
      if (typeof rec.updatable === "boolean") parts.push(rec.updatable ? "Update available" : "Already latest");
      var msg = String(rec.message || "").trim();
      var err = String(rec.error || "").trim();
      if (msg) parts.push(msg);
      if (err) parts.push("Error: " + err);
      if (rec.checked_at) parts.push("Checked: " + rec.checked_at);
      el.textContent = parts.join(" | ");
      var running = !!rec.running;
      if (byId("qbtCheckUpdateBtn")) byId("qbtCheckUpdateBtn").disabled = running;
      if (byId("qbtUpgradeBtn")) byId("qbtUpgradeBtn").disabled = running;
    }
    async function checkQbtClientUpdate(){
      setStatus("qbtStatus", "Checking client image update...");
      var d = await apiJson("/api/qbt/client-upgrade/check", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(qbtUpgradePayload())
      });
      renderQbtUpgradeStatus(d || {});
      if (d && d.error) setStatus("qbtStatus", "Update check failed: " + d.error, true);
      else setStatus("qbtStatus", (d && d.message) ? d.message : "Update check completed");
    }
    async function runQbtClientUpgrade(){
      if (!window.confirm("Confirm upgrading selected BitTorrent docker client? Container will be recreated by docker compose and existing mapped config will be preserved.")) return;
      setStatus("qbtStatus", "Starting client upgrade...");
      var d = await apiJson("/api/qbt/client-upgrade/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(qbtUpgradePayload())
      });
      renderQbtUpgradeStatus(d || {});
      if (d && d.state === "error") setStatus("qbtStatus", "Client upgrade failed: " + String(d.error || "unknown"), true);
      else setStatus("qbtStatus", (d && d.message) ? d.message : "Client upgrade completed");
      await loadQbtRuntime();
    }
    function switchTab(name){
      var tab = (name || "").trim() || "general";
      var valid = { general:1, http:1, qbt:1, terminal:1, ddns:1, netdisk:1 };
      if (!valid[tab]) tab = "general";
      var btns = Array.prototype.slice.call(document.querySelectorAll(".cfg-tab"));
      for (var i = 0; i < btns.length; i++) {
        var b = btns[i];
        b.classList.toggle("active", b.getAttribute("data-tab") === tab);
      }
      ["general","http","qbt","terminal","ddns","netdisk"].forEach(function(t){
        var p = byId("panel-" + t);
        if (p) p.classList.toggle("active", t === tab);
      });
      try { localStorage.setItem(TAB_KEY, tab); } catch (e) {}
      try { history.replaceState(null, "", "#"+tab); } catch (e) {}
    }

    Array.prototype.slice.call(document.querySelectorAll(".cfg-tab")).forEach(function(btn){
      btn.addEventListener("click", function(){ switchTab(btn.getAttribute("data-tab")); });
    });

    byId("themeToggleBtn").addEventListener("click", function(){
      applyTheme(getTheme() === "dark" ? "light" : "dark");
    });
    Array.prototype.slice.call(document.querySelectorAll('#panel-general .theme-preset-btn')).forEach(function(btn){
      btn.addEventListener("click", async function(){
        try {
          await setHeroPresetFromConfig(btn.getAttribute("data-hero-preset"));
        } catch (err) {
          setHeroThemeStatus("Switch failed: " + err.message, true);
        }
      });
    });
    window.__cfgThemePresetWired = true;
    if (byId("cfgThemeBgUploadBtn")) {
      byId("cfgThemeBgUploadBtn").addEventListener("click", async function(){
        try {
          var file = byId("cfgThemeBgFileInput") && byId("cfgThemeBgFileInput").files
            ? byId("cfgThemeBgFileInput").files[0]
            : null;
          await uploadHeroImageFromFile(file);
        } catch (err) {
          setHeroThemeStatus("Upload failed: " + err.message, true);
        }
      });
    }
    if (byId("cfgThemeBgClearBtn")) {
      byId("cfgThemeBgClearBtn").addEventListener("click", async function(){
        try {
          await resetHeroToDefault();
        } catch (err) {
          setHeroThemeStatus("Restore failed: " + err.message, true);
        }
      });
    }

    byId("saveModulesBtn").addEventListener("click", async function(){
      try {
        var payload = {
          modules: {
            qbt: byId("modQbt").checked,
            ddns: byId("modDdns").checked,
            shareclip: byId("modShareclip").checked,
            http: byId("modHttp").checked
          }
        };
        var d = await apiJson("/api/app-config", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        applyCfg(d.config || d);
        updateWebPortHint();
        var actionSummary = summarizeModuleActions((d && d.module_actions) || []);
        if (actionSummary.text) {
          setStatus("generalStatus", "General settings saved: " + actionSummary.text, actionSummary.has_error);
        } else if (payload.modules.http === false) {
          setStatus("generalStatus", d.http_disconnect_triggered ? "General settings saved: HTTP module is disabled. One upload connection was interrupted and uploads were turned off." : "General settings saved: HTTP module is disabled and uploads are turned off.", false);
        } else {
          setStatus("generalStatus", "General settings saved", false);
        }
      } catch (err) {
        setStatus("generalStatus", "Save failed: " + err.message, true);
      }
    });

    byId("saveNetdiskBtn").addEventListener("click", async function(){
      try {
        var payload = {
          netdisk_sources: {
            baidu: byId("ndBaidu").checked,
            ali: byId("ndAli").checked,
            guangya: byId("ndGuangya").checked,
            dropbox: byId("ndDropbox").checked,
            mega: byId("ndMega").checked,
            onedrive: byId("ndOnedrive").checked,
            gdrive: byId("ndGdrive").checked
          }
        };
        var d = await apiJson("/api/app-config", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        applyCfg(d.config || d);
        setStatus("netdiskStatus", "Netdisk settings saved", false);
      } catch (err) {
        setStatus("netdiskStatus", "Save failed: " + err.message, true);
      }
    });

    byId("restartCfgServiceBtn").addEventListener("click", async function(){
      if (!window.confirm(trRaw("Confirm restarting service? Port changes take effect after restart."))) return;
      try {
        setStatus("generalStatus", "Sending restart command...");
        var d = await apiJson("/api/control/restart", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ reason: "config-page-restart" })
        });
        if (d && d.queued === false) {
          setStatus("generalStatus", "Restart job was not queued. Please try again.", true);
          return;
        }
        setStatus("generalStatus", "Restart command sent. Port-related changes will take effect after restart.");
      } catch (err) {
        setStatus("generalStatus", "Restart failed: " + err.message, true);
      }
    });

    if (byId("runUpgradeBtn")) {
      byId("runUpgradeBtn").addEventListener("click", async function(){
        try {
          await runAutoUpgrade();
        } catch (err) {
          setStatus("upgradeStatus", "Failed to start update: " + err.message, true);
        }
      });
    }
    if (byId("refreshUpgradeStatusBtn")) {
      byId("refreshUpgradeStatusBtn").addEventListener("click", async function(){
        try {
          await checkServerVersion();
        } catch (err) {
          setStatus("upgradeStatus", "Version check failed: " + err.message, true);
        }
      });
    }
    if (byId("qbtCheckUpdateBtn")) {
      byId("qbtCheckUpdateBtn").addEventListener("click", async function(){
        try {
          await checkQbtClientUpdate();
        } catch (err) {
          setStatus("qbtStatus", "Update check failed: " + err.message, true);
        }
      });
    }
    if (byId("qbtUpgradeBtn")) {
      byId("qbtUpgradeBtn").addEventListener("click", async function(){
        try {
          await runQbtClientUpgrade();
        } catch (err) {
          setStatus("qbtStatus", "Client upgrade failed: " + err.message, true);
        }
      });
    }

    byId("saveHttpBtn").addEventListener("click", async function(){
      try {
        var webPort = parseWebPort(byId("webPortInput") ? byId("webPortInput").value : cfg.web_port, cfg.web_port || 1288);
        var scan = await scanHttpRootPath(true);
        if (!scan.ok) throw new Error(String(scan.error || "HTTP root directory is inaccessible"));
        var root = normalizeRootInput((scan && scan.path) || byId("httpRootDir").value || "/");
        var target = normalizeDirInput(byId("httpDefaultDir").value);
        var pools = collectSourceIpPoolsDraft();
        var source = normalizeSourceIpPoolSource(byId("httpPoolSource").value);
        var transferRecentTtlSec = parseTransferRecentTtlSec(
          byId("transferRecentTtlSec") ? byId("transferRecentTtlSec").value : (cfg.http_service || {}).transfer_recent_ttl_sec,
          (cfg.http_service || {}).transfer_recent_ttl_sec
        );
        await apiJson("/api/directories?stats=0&root_dir=" + encodeURIComponent(root) + "&dir=" + encodeURIComponent(target));
        var d = await apiJson("/api/app-config", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ web_port: webPort, http_service: { root_dir: root, default_dir: target, source_ip_pools: pools, source_ip_pool_source: source, transfer_recent_ttl_sec: transferRecentTtlSec } })
        });
        applyCfg(d.config || d);
        byId("httpBrowseDir").value = target;
        await loadHttpDirBrowser(target, true);
        var restartMsg = (d && d.web_port_restart_required)
          ? (" Service port will switch to " + String(parseWebPort(((d.config || {}).web_port), webPort)) + " after restart.")
          : "";
        setStatus("httpStatus", "HTTP settings saved." + restartMsg);
      } catch (err) {
        setStatus("httpStatus", "Save failed: " + err.message, true);
      }
    });

    byId("httpScanRootBtn").addEventListener("click", async function(){
      try {
        var d = await scanHttpRootPath(false);
        if (d && d.ok) {
          await loadHttpDirBrowser(".", true);
        }
      } catch (err) {
        setStatus("httpStatus", "Path validation failed: " + err.message, true);
      }
    });

    byId("httpBrowseLoadBtn").addEventListener("click", async function(){
      try {
        await loadHttpDirBrowser(byId("httpBrowseDir").value, false);
      } catch (err) {
        setStatus("httpStatus", "Directory load failed: " + err.message, true);
      }
    });

    byId("httpBrowseParentBtn").addEventListener("click", async function(){
      try {
        var p = parentDirOf(byId("httpBrowseDir").value);
        byId("httpBrowseDir").value = p;
        await loadHttpDirBrowser(p, false);
      } catch (err) {
        setStatus("httpStatus", "Directory load failed: " + err.message, true);
      }
    });

    byId("httpBrowseDir").addEventListener("keydown", function(event){
      if (event.key === "Enter") {
        byId("httpBrowseLoadBtn").click();
      }
    });
    byId("httpRootDir").addEventListener("keydown", function(event){
      if (event.key === "Enter") {
        byId("httpScanRootBtn").click();
      }
    });
    if (byId("syncHttpPoolSourceBtn")) {
      byId("syncHttpPoolSourceBtn").addEventListener("click", async function(){
        try {
          await syncSourceIpPoolsFromRemote();
        } catch (err) {
          setStatus("httpStatus", "Source sync failed: " + err.message, true);
        }
      });
    }
    if (byId("httpPoolSource")) {
      byId("httpPoolSource").addEventListener("keydown", function(event){
        if (event.key === "Enter") {
          event.preventDefault();
          if (byId("syncHttpPoolSourceBtn")) byId("syncHttpPoolSourceBtn").click();
        }
      });
    }

    async function saveQbtSettings(silent){
      var draft = qbtDraftPayload();
      var payload = { qbt: draft };
      var d = await apiJson("/api/app-config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      applyCfg(d.config || d);
      qbtSavedSignature = qbtSignatureFromPayload(draft);
      updateQbtOptimizeState();
      if (!silent) setStatus("qbtStatus", "BitTorrent settings saved");
      await loadQbtRuntime();
      return payload.qbt;
    }

    byId("saveQbtBtn").addEventListener("click", async function(){
      try {
        await saveQbtSettings(false);
      } catch (err) {
        setStatus("qbtStatus", "Save failed: " + err.message, true);
      }
    });
    byId("qbtDetectBtn").addEventListener("click", async function(){
      try {
        await loadQbtDiscover(true);
        setStatus("qbtStatus", "Detected available options");
      } catch (err) {
        setStatus("qbtStatus", "Detect failed: " + err.message, true);
      }
    });
    ["qbtServiceUnit","qbtDockerContainer","qbtApiUrl"].forEach(function(id){
      var el = byId(id);
      if (!el) return;
      el.addEventListener("input", updateQbtOptimizeState);
      el.addEventListener("change", updateQbtOptimizeState);
    });

    byId("qbtOptimizeBtn").addEventListener("click", async function(){
      updateQbtOptimizeState();
      if (String(byId("qbtOptimizeBtn").dataset.dirty || "0") === "1") {
        setStatus("qbtStatus", trRaw("Please save current BitTorrent settings before optimization."), true);
        return;
      }
      if (!window.confirm(trRaw("Will comment current related config and apply optimized parameters. Continue?"))) return;
      try {
        setStatus("qbtStatus", trRaw("Optimizing configuration..."));
        var selected = qbtDraftPayload();
        var d = await apiJson("/api/qbt/optimize-config", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ qbt: selected })
        });
        setStatus("qbtStatus", (d && d.message) || trRaw("BitTorrent optimization completed"));
        await loadQbtRuntime();
      } catch (err) {
        setStatus("qbtStatus", trRaw("Optimization failed: ") + err.message, true);
      }
    });

    byId("qbtFixPermBtn").addEventListener("click", async function(){
      try {
        setStatus("qbtStatus", trRaw("Fixing BitTorrent settings and permissions..."));
        var d = await apiJson("/api/qbt/fix-monitor", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: "{}"
        });
        setStatus("qbtStatus", (d && d.message) || trRaw("BitTorrent fix completed"));
        await loadQbtRuntime();
      } catch (err) {
        setStatus("qbtStatus", trRaw("Fix failed: ") + err.message, true);
      }
    });

    byId("qbtRestartSvcBtn").addEventListener("click", async function(){
      if (!window.confirm(trRaw("Confirm restart BitTorrent service? Active tasks may be interrupted."))) return;
      try {
        var curClient = String(btConfigClient || (cfg.qbt && cfg.qbt.client) || "qbittorrent").trim();
        await apiJson("/api/control/service", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ service: "qbt", action: "restart", client: curClient })
        });
        setStatus("qbtStatus", trRaw("BitTorrent service restarted"));
        await loadQbtRuntime();
      } catch (err) {
        setStatus("qbtStatus", "Restart failed: " + err.message, true);
      }
    });

    byId("termPickKeyBtn").addEventListener("click", function(){
      var fi = byId("termKeyUploadInput");
      if (!fi) return;
      fi.click();
    });

    byId("termRefreshKeyListBtn").addEventListener("click", async function(){
      try {
        await loadBaseInfo();
        refreshTerminalPreview();
        setStatus("terminalStatus", "Key list refreshed");
      } catch (err) {
        setStatus("terminalStatus", "Refresh failed: " + err.message, true);
      }
    });

    byId("termKeyUploadInput").addEventListener("change", async function(){
      var file = this.files && this.files[0];
      this.value = "";
      if (!file) return;
      try {
        setStatus("terminalStatus", "Uploading key file...");
        await uploadTerminalKeyFromFile(file);
      } catch (err) {
        setStatus("terminalStatus", "Upload failed: " + err.message, true);
      }
    });

    byId("saveTerminalBtn").addEventListener("click", async function(){
      try {
        var draft = collectTerminalDraft();
        if (draft.enabled && !draft.host) {
          throw new Error("Host cannot be empty when Terminal is enabled");
        }
        var d = await apiJson("/api/app-config", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ terminal: draft })
        });
        applyCfg(d.config || d);
        setStatus("terminalStatus", "Terminal settings saved");
      } catch (err) {
        setStatus("terminalStatus", "Save failed: " + err.message, true);
      }
    });

    byId("copyTerminalCmdBtn").addEventListener("click", async function(){
      var m = buildTerminalMetaFromDraft(collectTerminalDraft());
      if (!m.command) {
        setStatus("terminalStatus", "Please fill Host/User connection info first", true);
        return;
      }
      var ok = await copyTextSmart(m.command);
      if (ok) {
        setStatus("terminalStatus", "SSH command copied");
      } else {
        setStatus("terminalStatus", "Copy failed, please copy preview command manually", true);
      }
    });

    ["termEnabled","termHost","termUser","termPort","termAuthMode","termKeyPath","termKeyFile"].forEach(function(id){
      var el = byId(id);
      if (!el) return;
      el.addEventListener("input", refreshTerminalPreview);
      el.addEventListener("change", refreshTerminalPreview);
    });
    if (byId("webPortInput")) {
      byId("webPortInput").addEventListener("input", updateWebPortHint);
      byId("webPortInput").addEventListener("change", updateWebPortHint);
    }

    applyTheme(getTheme());
    var initialTab = (window.location.hash || "").replace("#", "") || "general";
    switchTab(initialTab);
    loadCfg()
      .then(function(){ return Promise.all([loadBaseInfo(), scanHttpRootPath(true), loadHttpDirBrowser(byId("httpBrowseDir").value, true), loadQbtRuntime(), loadQbtUpgradeStatus(true), loadUpgradeStatus(true)]); })
      .catch(function(err){ setStatus("generalStatus", "Config load failed: " + err.message, true); });
    window.addEventListener("beforeunload", stopUpgradePolling);
    window.__cfgMainReady = true;
  })();
  </script>
  <script>
  (function(){
    "use strict";
    // Fallback binder: if main config script fails early, theme controls still work.
    if (window.__cfgThemePresetWired) return;
    if (window.fccI18n && window.fccI18n.initPage) {
      window.fccI18n.initPage({ selectId: "langSelect" }).catch(function(){});
    }
    function byId(id){ return document.getElementById(id); }
    function showToast(msg, type){
      var text = String(msg || "").trim();
      if (!text) return;
      var container = byId("toastContainer");
      if (!container) return;
      var t = document.createElement("div");
      t.className = "toast " + (type === "error" ? "error" : "success");
      t.textContent = text;
      container.appendChild(t);
      setTimeout(function(){
        if (t.parentNode) t.parentNode.removeChild(t);
      }, 3000);
    }
    function normalizeHeroPreset(v){
      var x = String(v || "").trim().toLowerCase();
      if (x === "aurora" || x === "sunset" || x === "frost" || x === "afterclaw_clouds") return x;
      return "default";
    }
    function setStatus(msg, isErr){
      var el = byId("cfgThemeStatus");
      if (!el) return;
      var text = String(msg || "");
      el.textContent = text;
      el.classList.toggle("err", !!isErr);
      if (text.trim()) showToast(text, isErr ? "error" : "success");
    }
    function bytesToBase64(bytes){
      var out = "";
      var chunkSize = 0x8000;
      for (var i = 0; i < bytes.length; i += chunkSize) {
        var chunk = bytes.subarray(i, i + chunkSize);
        out += String.fromCharCode.apply(null, chunk);
      }
      return btoa(out);
    }
    async function apiJson(url, opts){
      var r = await fetch(url, opts || {});
      var d = await r.json().catch(function(){ return {}; });
      if (!r.ok) throw new Error((d && d.error) || ("Request failed " + r.status));
      return d;
    }
    function applyUiTheme(uiTheme){
      var t = uiTheme || {};
      var preset = normalizeHeroPreset(t.hero_preset || "default");
      document.documentElement.setAttribute("data-hero-preset", preset);
      try { localStorage.setItem("fc-hero-preset", preset); } catch (e) {}
      document.documentElement.style.removeProperty("--hero-custom-url");
      var labels = { default: "Default", aurora: "Aurora", sunset: "Sunset", frost: "Frost", afterclaw_clouds: "Clouds at Dusk" };
      var meta = byId("cfgThemeMeta");
      if (meta) {
        meta.textContent = trRaw("Current theme: ") + trRaw(labels[preset] || "Default");
      }
      Array.prototype.slice.call(document.querySelectorAll('#panel-general .theme-preset-btn')).forEach(function(btn){
        var p = normalizeHeroPreset(btn.getAttribute("data-hero-preset"));
        btn.classList.toggle("active", p === preset);
      });
    }
    async function setPreset(preset){
      var p = normalizeHeroPreset(preset);
      var d = await apiJson("/api/app-config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ui: { hero_preset: p } })
      });
      applyUiTheme((d && d.ui_theme) || {});
      var labels = { default: "Default", aurora: "Aurora", sunset: "Sunset", frost: "Frost", afterclaw_clouds: "Clouds at Dusk" };
      setStatus(trRaw("Switched theme: ") + trRaw(labels[p] || "Default"), false);
    }
    async function uploadThemeImage(file){
      if (!file) throw new Error("Please select a local image first");
      var name = String(file.name || "").trim();
      if (!/\.(png|jpe?g|webp|gif|avif)$/i.test(name)) {
        throw new Error("Only PNG/JPG/WEBP/GIF/AVIF are supported");
      }
      var maxBytes = 12 * 1024 * 1024;
      if (file.size > maxBytes) throw new Error("Image is too large (max 12MB)");
      var bytes = new Uint8Array(await file.arrayBuffer());
      var b64 = bytesToBase64(bytes);
      var d = await apiJson("/api/ui/theme-background", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ file_name: name, content_b64: b64, apply: true })
      });
      applyUiTheme((d && d.ui_theme) || {});
      setStatus("Background updated: " + name, false);
    }
    async function resetThemeDefault(){
      var d = await apiJson("/api/app-config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ui: { hero_preset: "default", hero_custom_bg_file: "" } })
      });
      applyUiTheme((d && d.ui_theme) || {});
      var fileInput = byId("cfgThemeBgFileInput");
      if (fileInput) fileInput.value = "";
      setStatus("Background restored to default", false);
    }
    Array.prototype.slice.call(document.querySelectorAll('#panel-general .theme-preset-btn')).forEach(function(btn){
      btn.addEventListener("click", async function(){
        try {
          await setPreset(btn.getAttribute("data-hero-preset"));
        } catch (err) {
          setStatus("Switch failed: " + ((err && err.message) || err), true);
        }
      });
    });
    var uploadBtn = byId("cfgThemeBgUploadBtn");
    if (uploadBtn) {
      uploadBtn.addEventListener("click", async function(){
        try {
          var input = byId("cfgThemeBgFileInput");
          var file = input && input.files ? input.files[0] : null;
          await uploadThemeImage(file);
        } catch (err) {
          setStatus("Upload failed: " + ((err && err.message) || err), true);
        }
      });
    }
    var clearBtn = byId("cfgThemeBgClearBtn");
    if (clearBtn) {
      clearBtn.addEventListener("click", async function(){
        try {
          await resetThemeDefault();
        } catch (err) {
          setStatus("Restore failed: " + ((err && err.message) || err), true);
        }
      });
    }
    window.__cfgThemePresetWired = true;
  })();
  </script>
  <script>
  (function(){
    "use strict";
    if (window.__cfgMainReady) return;
    if (window.__cfgCoreFallbackWired) return;
    window.__cfgCoreFallbackWired = true;
    if (window.fccI18n && window.fccI18n.initPage) {
      window.fccI18n.initPage({ selectId: "langSelect" }).catch(function(){});
    }

    var TAB_KEY = "fc-config-tab";
    function byId(id){ return document.getElementById(id); }
    function trRaw(text){
      var src = String(text || "");
      try {
        if (window.fccI18n && typeof window.fccI18n.translateRaw === "function") {
          return window.fccI18n.translateRaw(src) || src;
        }
      } catch (e) {}
      return src;
    }
    function showToast(msg, type){
      var text = String(msg || "").trim();
      if (!text) return;
      var container = byId("toastContainer");
      if (!container) return;
      var t = document.createElement("div");
      t.className = "toast " + (type === "error" ? "error" : "success");
      t.textContent = text;
      container.appendChild(t);
      setTimeout(function(){
        if (t.parentNode) t.parentNode.removeChild(t);
      }, 3000);
    }
    function safeLocalGet(key, fallback){
      try {
        var v = localStorage.getItem(key);
        return v == null ? fallback : v;
      } catch (e) {
        return fallback;
      }
    }
    function safeLocalSet(key, value){
      try { localStorage.setItem(key, value); } catch (e) {}
    }
    function setStatus(id, msg, isErr){
      var el = byId(id);
      if (!el) return;
      var text = String(msg || "");
      el.textContent = text;
      el.className = isErr ? "cfg-status err" : "cfg-status";
      if (text.trim()) showToast(text, isErr ? "error" : "success");
    }
    function summarizeModuleActions(actions){
      var rows = Array.isArray(actions) ? actions : [];
      var msgs = [];
      var hasErr = false;
      rows.forEach(function(item){
        var m = String((item && item.message) || "").trim();
        if (m) msgs.push(m);
        if (item && item.ok === false) hasErr = true;
      });
      return { text: msgs.join("; "), has_error: hasErr };
    }
    function parseWebPort(raw, fallback){
      var f = Number(fallback);
      if (!Number.isFinite(f)) f = 1288;
      f = Math.trunc(f);
      if (f < 1 || f > 65535) f = 1288;
      var n = Number(raw);
      if (!Number.isFinite(n)) return f;
      n = Math.trunc(n);
      if (n < 1 || n > 65535) return f;
      return n;
    }
    async function apiJson(url, opts){
      var r = await fetch(url, opts || {});
      var d = await r.json().catch(function(){ return {}; });
      if (!r.ok) throw new Error((d && d.error) || ("Request failed " + r.status));
      return d;
    }
    function switchTab(name){
      var tab = (name || "").trim() || "general";
      var valid = { general:1, http:1, qbt:1, terminal:1, ddns:1 };
      if (!valid[tab]) tab = "general";
      Array.prototype.slice.call(document.querySelectorAll(".cfg-tab")).forEach(function(btn){
        btn.classList.toggle("active", btn.getAttribute("data-tab") === tab);
      });
      ["general","http","qbt","terminal","ddns"].forEach(function(t){
        var p = byId("panel-" + t);
        if (p) p.classList.toggle("active", t === tab);
      });
      safeLocalSet(TAB_KEY, tab);
      try { history.replaceState(null, "", "#" + tab); } catch (e) {}
    }
    function applyModuleConfig(cfg){
      var modules = ((cfg || {}).modules) || {};
      if (byId("modQbt")) byId("modQbt").checked = modules.qbt !== false;
      if (byId("modDdns")) byId("modDdns").checked = modules.ddns !== false;
      if (byId("modShareclip")) byId("modShareclip").checked = modules.shareclip !== false;
      if (byId("modHttp")) byId("modHttp").checked = modules.http !== false;
      var wp = parseWebPort((cfg || {}).web_port, 1288);
      if (byId("webPortInput")) byId("webPortInput").value = String(wp);
      if (byId("webPortHint")) byId("webPortHint").textContent = "Saved port: " + String(wp) + " (restart required after change)";
    }
    async function loadModuleConfig(){
      var d = await apiJson("/api/app-config");
      applyModuleConfig((d && d.config) || d || {});
    }
    async function saveModuleConfig(){
      var webPort = parseWebPort(byId("webPortInput") ? byId("webPortInput").value : 1288, 1288);
      var payload = {
        web_port: webPort,
        modules: {
          qbt: !!(byId("modQbt") && byId("modQbt").checked),
          ddns: !!(byId("modDdns") && byId("modDdns").checked),
          shareclip: !!(byId("modShareclip") && byId("modShareclip").checked),
          http: !!(byId("modHttp") && byId("modHttp").checked),
        }
      };
      var d = await apiJson("/api/app-config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      applyModuleConfig((d && d.config) || d || {});
      var actionSummary = summarizeModuleActions((d && d.module_actions) || []);
      if (actionSummary.text) {
        setStatus("generalStatus", "General settings saved: " + actionSummary.text, actionSummary.has_error);
      } else if (payload.modules.http === false) {
        setStatus("generalStatus", d.http_disconnect_triggered ? "General settings saved: HTTP module is disabled. One upload connection was interrupted and uploads were turned off." : "General settings saved: HTTP module is disabled and uploads are turned off.", false);
      } else {
        setStatus("generalStatus", "General settings saved", false);
      }
    }

    Array.prototype.slice.call(document.querySelectorAll(".cfg-tab")).forEach(function(btn){
      btn.addEventListener("click", function(){ switchTab(btn.getAttribute("data-tab")); });
    });
    if (byId("saveModulesBtn")) {
      byId("saveModulesBtn").addEventListener("click", function(){
        saveModuleConfig().catch(function(err){
          setStatus("generalStatus", "Save failed: " + ((err && err.message) || err), true);
        });
      });
    }
    if (byId("restartCfgServiceBtn")) {
      byId("restartCfgServiceBtn").addEventListener("click", function(){
        if (!window.confirm(trRaw("Confirm restarting service? Port changes take effect after restart."))) return;
        apiJson("/api/control/restart", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ reason: "config-page-restart" })
        }).then(function(d){
          if (d && d.queued === false) {
            setStatus("generalStatus", "Restart job was not queued. Please try again.", true);
            return;
          }
          setStatus("generalStatus", "Restart command sent. Port-related changes will take effect after restart.", false);
        }).catch(function(err){
          setStatus("generalStatus", "Restart failed: " + ((err && err.message) || err), true);
        });
      });
    }
    switchTab((window.location.hash || "").replace("#", "") || "general");
    loadModuleConfig().catch(function(err){
      setStatus("generalStatus", "Config load failed: " + ((err && err.message) || err), true);
    });
  })();
  </script>
</body>
</html>
"""
    return _inject_page_title(html, "Config")



def build_terminal_html() -> str:
    html = """<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Web Terminal</title>
  <script>
    (function(){
      try {
        var t = localStorage.getItem("fc-theme");
        if (!t) { t = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"; }
        document.documentElement.setAttribute("data-theme", t);
      } catch(e){}
    })();
  </script>
  <link rel="stylesheet" href="/dashboard.css" />
  <script src="/i18n.js?v=20260430d"></script>
  <link rel="stylesheet" href="/vendor/xterm/xterm.css" />
  <style>
    .term-toolbar { display:flex; align-items:center; gap:10px; flex-wrap:wrap; margin-bottom:10px; }
    .term-target { font-weight:700; color: var(--text); }
    .term-shell {
      border: 1px solid var(--border);
      border-radius: 12px;
      background: #0b1220;
      overflow: hidden;
      height: clamp(420px, 68vh, 860px);
    }
    .term-note {
      margin-top: 8px;
      font-size: 12px;
      color: var(--text-muted);
    }
    .term-code {
      margin-top: 8px;
      border: 1px solid var(--border);
      border-radius: 10px;
      background: var(--surface-soft);
      padding: 8px 10px;
      font-family: ui-monospace, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
      font-size: 12px;
      word-break: break-all;
      line-height: 1.45;
      color: var(--text);
    }
    .term-link-line { font-size: 13px; color: var(--text-muted); margin-top: 8px; }
    .term-link-line a { color: var(--accent); text-decoration: none; }
    .term-link-line a:hover { text-decoration: underline; }
  </style>
</head>
<body>
  <div class="wrap">
    <header class="page-head">
      <div class="head-row">
        <div>
          <a href="/" class="back-link">← Back to AfterClaw</a>
          <h1>Web Terminal</h1>
          <p class="page-sub">浏览器内 SSH 终端（xterm.js）</p>
        </div>
        <div class="head-actions">
          <a href="/config#terminal" class="gear-btn" title="Config / Terminal" aria-label="Config / Terminal">⚙️</a>
          <button type="button" id="themeToggleBtn" class="secondary">Theme</button>
          <select id="langSelect" class="lang-select" title="Language">
            <option value="zh-CN">简体中文</option>
            <option value="zh-TW">繁體中文</option>
            <option value="en">English</option>
            <option value="de">Deutsch</option>
            <option value="fr">Français</option>
            <option value="ja">日本語</option>
          </select>
        </div>
      </div>
    </header>

    <div class="card">
      <div class="term-toolbar">
        <span class="term-target">目标：<span id="termTarget">加载中...</span></span>
        <button type="button" id="connectBtn">Connect</button>
        <button type="button" id="disconnectBtn" class="secondary">Disconnect</button>
        <button type="button" id="copyCmdBtn" class="secondary">Copy SSH command</button>
        <button type="button" id="clearBtn" class="secondary">Clear</button>
      </div>
      <div id="termStatus" class="status-bar muted">Ready</div>
      <div id="termView" class="term-shell"></div>
      <div class="term-link-line">外部终端直连：<a id="sshLaunchLink" href="#" target="_blank" rel="noopener">-</a></div>
      <div id="termCmdPreview" class="term-code">-</div>
      <div class="term-note">Powered by <a href="https://github.com/xtermjs/xterm.js" target="_blank" rel="noopener">xterm.js</a></div>
    </div>
  </div>

  <script src="/vendor/xterm/xterm.js"></script>
  <script src="/vendor/xterm/addon-fit.js"></script>
  <script>
  (function(){
    "use strict";
    var __i18nReady = (window.fccI18n && window.fccI18n.initPage)
      ? window.fccI18n.initPage({ selectId: "langSelect" }).catch(function(){})
      : Promise.resolve();
    var THEME_KEY = "fc-theme";
    var termTargetEl = document.getElementById("termTarget");
    var termStatusEl = document.getElementById("termStatus");
    var sshLaunchLinkEl = document.getElementById("sshLaunchLink");
    var termCmdPreviewEl = document.getElementById("termCmdPreview");
    var connectBtn = document.getElementById("connectBtn");
    var disconnectBtn = document.getElementById("disconnectBtn");
    var copyCmdBtn = document.getElementById("copyCmdBtn");
    var clearBtn = document.getElementById("clearBtn");
    var termViewEl = document.getElementById("termView");
    var sessionId = "";
    var pollTimer = null;
    var flushTimer = null;
    var writeBuffer = "";
    var terminalMeta = null;
    var term = null;
    var fitAddon = null;

    function getTheme(){ return localStorage.getItem(THEME_KEY) || "light"; }
    function applyTheme(t){
      document.documentElement.setAttribute("data-theme", t);
      try { localStorage.setItem(THEME_KEY, t); } catch (e) {}
      if (term) {
        term.options.theme = t === "dark"
          ? { background: "#0b1220", foreground: "#dbe5f5", cursor: "#60a5fa" }
          : { background: "#0f172a", foreground: "#e2e8f0", cursor: "#60a5fa" };
      }
    }
    function setStatus(msg, isErr){
      termStatusEl.textContent = msg || "";
      termStatusEl.className = isErr ? "status-bar err" : "status-bar muted";
    }
    async function apiJson(url, opts){
      var r = await fetch(url, opts || {});
      var d = await r.json().catch(function(){ return {}; });
      if (!r.ok) throw new Error((d && d.error) || ("Request failed " + r.status));
      return d;
    }
    async function copyTextSmart(text){
      var value = String(text || "");
      if (!value) return false;
      try {
        if (navigator.clipboard && window.isSecureContext) {
          await navigator.clipboard.writeText(value);
          return true;
        }
      } catch (e) {}
      try {
        var ta = document.createElement("textarea");
        ta.value = value;
        ta.setAttribute("readonly", "");
        ta.style.position = "fixed";
        ta.style.top = "-9999px";
        ta.style.left = "-9999px";
        document.body.appendChild(ta);
        ta.focus();
        ta.select();
        var ok = document.execCommand("copy");
        document.body.removeChild(ta);
        return !!ok;
      } catch (e) {
        return false;
      }
    }
    function renderMeta(){
      var m = terminalMeta || {};
      var display = String(m.display || "-");
      var link = String(m.link || "").trim();
      var cmd = String(m.command || "-");
      termTargetEl.textContent = display;
      if (link) {
        sshLaunchLinkEl.href = link;
        sshLaunchLinkEl.textContent = link;
      } else {
        sshLaunchLinkEl.href = "#";
        sshLaunchLinkEl.textContent = "-";
      }
      termCmdPreviewEl.textContent = cmd;
      connectBtn.disabled = !m.enabled || !m.host;
      if (!m.enabled) {
        setStatus("Terminal 模块未启用，请到 Config -> Terminal 开启。", true);
      } else if (!m.host) {
        setStatus("Not configured Terminal Host，请到 Config -> Terminal 设置。", true);
      } else {
        setStatus("准备Connect到 " + display);
      }
    }
    function ensureTerminalReady(){
      if (term) return true;
      if (!window.Terminal || !window.FitAddon) {
        setStatus("xterm.js 资源加载失败，请检查 /vendor/xterm 资源后Refresh。", true);
        return false;
      }
      term = new Terminal({
        cursorBlink: true,
        fontSize: 13,
        fontFamily: "ui-monospace, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace",
        convertEol: false,
        scrollback: 3000,
      });
      fitAddon = new window.FitAddon.FitAddon();
      term.loadAddon(fitAddon);
      term.open(termViewEl);
      fitAddon.fit();
      term.focus();
      term.onData(function(data){
        if (!sessionId) return;
        writeBuffer += data;
        if (!flushTimer) {
          flushTimer = window.setTimeout(flushWrite, 40);
        }
      });
      window.addEventListener("resize", function(){
        if (!fitAddon) return;
        fitAddon.fit();
        sendResize().catch(function(){});
      });
      applyTheme(getTheme());
      return true;
    }
    async function flushWrite(){
      flushTimer = null;
      if (!sessionId || !writeBuffer) return;
      var chunk = writeBuffer;
      writeBuffer = "";
      try {
        await apiJson("/api/terminal/write", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ session_id: sessionId, data: chunk })
        });
      } catch (err) {
        setStatus("输入发送失败：" + err.message, true);
      }
    }
    async function sendResize(){
      if (!sessionId || !term) return;
      var cols = Math.max(20, Number(term.cols || 120));
      var rows = Math.max(8, Number(term.rows || 30));
      await apiJson("/api/terminal/resize", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, cols: cols, rows: rows })
      });
    }
    async function readLoop(){
      if (!sessionId) return;
      try {
        var d = await apiJson("/api/terminal/read", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ session_id: sessionId })
        });
        if (d.output && term) {
          term.write(String(d.output));
        }
        if (!d.alive) {
          var code = (d.exit_code === null || d.exit_code === undefined) ? "-" : String(d.exit_code);
          setStatus("会话已结束，退出码：" + code, true);
          sessionId = "";
          return;
        }
      } catch (err) {
        setStatus("Read failed: " + err.message, true);
        sessionId = "";
        return;
      }
      pollTimer = window.setTimeout(readLoop, 80);
    }
    async function connectSession(){
      if (sessionId) return;
      if (!ensureTerminalReady()) return;
      try {
        fitAddon.fit();
        var cols = Math.max(20, Number(term.cols || 120));
        var rows = Math.max(8, Number(term.rows || 30));
        var d = await apiJson("/api/terminal/start", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ cols: cols, rows: rows })
        });
        sessionId = String(d.session_id || "");
        if (!sessionId) throw new Error("会话 ID 无效");
        term.clear();
        term.focus();
        setStatus("已Connect，输入命令即可。");
        if (pollTimer) window.clearTimeout(pollTimer);
        pollTimer = window.setTimeout(readLoop, 30);
      } catch (err) {
        setStatus("Connect失败：" + err.message, true);
      }
    }
    async function disconnectSession(){
      if (!sessionId) {
        setStatus("当前无活动会话");
        return;
      }
      var sid = sessionId;
      sessionId = "";
      if (pollTimer) {
        window.clearTimeout(pollTimer);
        pollTimer = null;
      }
      try {
        await apiJson("/api/terminal/close", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ session_id: sid })
        });
      } catch (err) {
        // ignore close error
      }
      setStatus("会话已Disconnect");
    }
    async function loadBase(){
      var d = await apiJson("/api/base");
      terminalMeta = d.terminal || {};
      renderMeta();
    }

    connectBtn.addEventListener("click", function(){ connectSession(); });
    disconnectBtn.addEventListener("click", function(){ disconnectSession(); });
    clearBtn.addEventListener("click", function(){
      if (!ensureTerminalReady()) return;
      term.clear();
      term.focus();
    });
    copyCmdBtn.addEventListener("click", async function(){
      var cmd = String((terminalMeta && terminalMeta.command) || "");
      if (!cmd) {
        setStatus("没有可复制的 SSH 命令", true);
        return;
      }
      var ok = await copyTextSmart(cmd);
      if (ok) setStatus("SSH 命令已复制");
      else setStatus("复制失败：请手工复制下方命令", true);
    });
    document.getElementById("themeToggleBtn").addEventListener("click", function(){
      applyTheme(getTheme() === "dark" ? "light" : "dark");
    });
    window.addEventListener("beforeunload", function(){
      if (!sessionId) return;
      fetch("/api/terminal/close", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId }),
        keepalive: true
      });
    });

    applyTheme(getTheme());
    loadBase().catch(function(err){
      setStatus("配置加载失败：" + err.message, true);
    });
    ensureTerminalReady();
  })();
  </script>
</body>
</html>
"""
    return _inject_page_title(html, "Web Terminal")


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


class AppHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    storage_root = DEFAULT_STORAGE_ROOT
    downloads_enabled = os.environ.get("DOWNLOADS_ENABLED", "1").strip() not in (
        "0",
        "false",
        "False",
    )
    speed_lock = threading.Lock()
    control_lock = threading.Lock()
    upgrade_lock = threading.Lock()
    qbt_upgrade_lock = threading.Lock()
    transfers_lock = threading.Lock()
    http_cut_lock = threading.Lock()
    restart_queued = False
    upgrade_running = False
    qbt_upgrade_running = False
    qbt_upgrade_status = {
        "running": False,
        "state": "idle",
        "client": "",
        "container": "",
        "image": "",
        "message": "",
        "error": "",
        "checked_at": "",
        "updated_at": "",
        "updatable": None,
    }
    http_cut_epoch = 0
    speed_state = {
        "iface": None,
        "last_ts": 0.0,
        "last_rx": 0,
        "last_tx": 0,
        "rx_mibps": 0.0,
        "rx_mbps": 0.0,
        "tx_mibps": 0.0,
        "tx_mbps": 0.0,
    }
    transfer_source_rules = (
        # Keep Guangya/Aliyun ahead of Baidu and avoid generic netdisk keyword.
        ("Guangya Netdisk", ("光鸭", "guangya", "clouddrive", "cloud drive")),
        ("Aliyun Drive", ("阿里", "aliyun", "alipan", "Aliyun Drive")),
        ("Baidu Netdisk", ("百度", "baidu", "pan.baidu", "xpan", "baiduyun", "yun.baidu", "pcs")),
        ("Dropbox", ("dropbox",)),
        ("MEGA", ("mega",)),
        ("OneDrive", ("onedrive",)),
        ("Google Drive", ("google drive", "gdrive")),
    )
    process_source_rules = (
        ("Baidu Netdisk", ("baidunetdisk", "xpan")),
        ("Guangya Netdisk", ("guangya", "clouddrive", "clouddrive2", "cloudfs", "httpd", "apache2")),
        ("Aliyun Drive", ("aliyundrive", "alipan", "aliyun")),
        ("Dropbox", ("dropbox",)),
        ("MEGA", ("megasync", "mega")),
        ("OneDrive", ("onedrive",)),
        ("Google Drive", ("googledrivesync", "gdrive")),
    )
    process_speed_sampler = ProcessSourceSpeedSampler(process_source_rules)
    process_detail_sampler = ProcessSourceSpeedSampler(process_source_rules)
    active_transfers = {}
    transfer_recent_ttl_sec = DEFAULT_TRANSFER_RECENT_TTL_SEC
    qbt_candidates = [
        DEFAULT_QBT_SERVICE,
        "qbittorrent-nox",
        "qbt-nox",
    ]
    qbt_docker_candidates = list(DEFAULT_QBT_DOCKER_CONTAINERS)
    ddns_candidates = [
        DEFAULT_DDNS_SERVICE,
        "ddns",
        "ddclient",
        "inadyn",
    ]
    qbt_stats_lock = threading.Lock()
    qbt_stats_cache = {"ts": 0.0, "data": None}
    shareclip_dispatch_lock = threading.Lock()
    ddnsgo_dispatch_lock = threading.Lock()
    terminal_lock = threading.Lock()
    terminal_sessions = {}
    terminal_session_ttl_sec = 30 * 60
    terminal_max_sessions = 6

    @staticmethod
    def _is_hidden_system_name(name: str) -> bool:
        n = str(name or "").strip()
        if not n:
            return True
        if n.startswith("."):
            return True
        if n.lower() == "__macosx":
            return True
        return False

    def _dispatch_module_route(self, parsed, method: str) -> bool:
        """Dispatch request to registered modules.
        
        Args:
            parsed: Parsed URL
            method: HTTP method (GET, POST, etc.)
        
        Returns:
            True if route was handled, False otherwise
        """
        for module in MODULE_REGISTRY.values():
            for route in module.routes:
                params = route.match(method, parsed.path)
                if params is not None:
                    # Route matched, check LAN access
                    if not self._require_lan():
                        return True
                    
                    # Call handler
                    try:
                        body = None
                        if method in {"POST", "PUT", "PATCH"}:
                            body = self._parse_body()
                        route.handler(self, parsed.path, params, body)
                        return True
                    except Exception as e:
                        self._error(f"Module route error: {e}", status=HTTPStatus.INTERNAL_SERVER_ERROR)
                        return True
        
        return False

    def _dispatch_shareclip_flask(self, parsed, command: str, send_body: bool) -> bool:
        path = parsed.path or "/"
        target_path = "/config" if path == "/clip-config" else path
        qs = parse_qs(parsed.query)
        query_id_pub = qs.get("id", [""])[0] == "pub"
        if not shareclip_route_match(path, query_id_pub):
            return False
        if not self._shareclip_module_enabled():
            self._error("ShareClip module is disabled", status=HTTPStatus.FORBIDDEN)
            return True
        if not self._require_lan():
            return True

        url = target_path
        if parsed.query:
            url = f"{target_path}?{parsed.query}"

        body_data = None
        if command in {"POST", "PUT", "PATCH"}:
            length = int(self.headers.get("Content-Length", "0") or "0")
            body_data = self.rfile.read(length) if length > 0 else b""
        elif command == "DELETE":
            length = int(self.headers.get("Content-Length", "0") or "0")
            body_data = self.rfile.read(length) if length > 0 else None

        hdrs = {}
        for hk, hv in self.headers.items():
            lk = hk.lower()
            if lk in _PROXY_FORWARD_REQUEST_HEADERS:
                hdrs[hk] = hv

        try:
            with AppHandler.shareclip_dispatch_lock:
                cli = get_shareclip_app().test_client()
                open_kw = {
                    "method": command,
                    "headers": hdrs,
                    "buffered": True,
                    "follow_redirects": False,
                }
                if body_data is not None:
                    open_kw["data"] = body_data
                resp = cli.open(url, **open_kw)
                if command == "HEAD":
                    self.send_response(resp.status_code)
                    for key, value in resp.headers.items():
                        if key.lower() in _PROXY_SKIP_RESPONSE_HEADERS:
                            continue
                        self.send_header(key, value)
                    self.end_headers()
                    return True

                raw = resp.get_data()
                ct = (resp.headers.get("Content-Type") or "").lower()
                out = raw
                inject_ok = (
                    send_body
                    and raw
                    and "text/html" in ct
                    and (path == "/clip-config" or (path == "/" and query_id_pub))
                )
                if inject_ok:
                    try:
                        html = raw.decode("utf-8", errors="replace")
                        html = _inject_pub_theme_link(html)
                        out = html.encode("utf-8")
                    except Exception:
                        out = raw

                self.send_response(resp.status_code)
                for key, value in resp.headers.items():
                    if key.lower() in _PROXY_SKIP_RESPONSE_HEADERS:
                        continue
                    self.send_header(key, value)
                self.send_header("Content-Length", str(len(out)))
                self.end_headers()
                if send_body:
                    self.wfile.write(out)
            return True
        except Exception as exc:
            self._error(f"ShareClip handling failed: {exc}", status=HTTPStatus.BAD_GATEWAY)
            return True

    def _dispatch_ddnsgo_proxy(self, parsed, command: str, send_body: bool) -> bool:
        path = parsed.path or "/"
        if not ddnsgo_route_match(path):
            return False
        if not self._ddns_module_enabled():
            self._error("DDNS module is disabled", status=HTTPStatus.FORBIDDEN)
            return True
        if not self._require_lan():
            return True

        try:
            cfg = ddns.load_config(_APP_ROOT_DIR)
            base_url = str((((cfg or {}).get("ddnsgo") or {}).get("base_url") or "")).strip()
            if not base_url:
                base_url = "http://127.0.0.1:9876"
            up = urlparse(base_url)
            if up.scheme not in ("http", "https") or not up.netloc:
                self._error("ddns-go base_url is invalid, please fix in DDNS Settings", status=HTTPStatus.BAD_REQUEST)
                return True

            sub_path = path[len("/ddns-go") :] if path.startswith("/ddns-go") else path
            if not sub_path:
                sub_path = "/"
            if not sub_path.startswith("/"):
                sub_path = "/" + sub_path
            target_url = base_url.rstrip("/") + sub_path
            if parsed.query:
                target_url += "?" + parsed.query

            body_data = None
            if command in {"POST", "PUT", "PATCH"}:
                length = int(self.headers.get("Content-Length", "0") or "0")
                body_data = self.rfile.read(length) if length > 0 else b""
            elif command == "DELETE":
                length = int(self.headers.get("Content-Length", "0") or "0")
                body_data = self.rfile.read(length) if length > 0 else None

            hdrs = {}
            for hk, hv in self.headers.items():
                lk = hk.lower()
                if lk in _PROXY_FORWARD_REQUEST_HEADERS:
                    hdrs[hk] = hv
            hdrs["User-Agent"] = hdrs.get("User-Agent", "storage-ctrl-ddns/2")

            req = urllib.request.Request(
                target_url,
                data=body_data,
                method=command,
                headers=hdrs,
            )

            with AppHandler.ddnsgo_dispatch_lock:
                try:
                    resp = urllib.request.urlopen(req, timeout=25)
                    status_code = int(resp.getcode() or 200)
                    resp_headers = list(resp.headers.items())
                    raw = resp.read() if command != "HEAD" else b""
                    resp.close()
                except urllib.error.HTTPError as e:
                    status_code = int(e.code or 502)
                    resp_headers = list(e.headers.items()) if e.headers else []
                    raw = e.read() if command != "HEAD" else b""

            if command == "HEAD":
                self.send_response(status_code)
                for key, value in resp_headers:
                    low = key.lower()
                    if low in _PROXY_SKIP_RESPONSE_HEADERS:
                        continue
                    if low == "location":
                        value = _rewrite_ddnsgo_location(value, base_url)
                    self.send_header(key, value)
                self.end_headers()
                return True

            out = raw
            ct = ""
            for key, value in resp_headers:
                if key.lower() == "content-type":
                    ct = (value or "").lower()
                    break
            if send_body and raw and "text/html" in ct:
                try:
                    html = raw.decode("utf-8", errors="replace")
                    html = _rewrite_ddnsgo_html(html)
                    out = html.encode("utf-8")
                except Exception:
                    out = raw

            self.send_response(status_code)
            for key, value in resp_headers:
                low = key.lower()
                if low in _PROXY_SKIP_RESPONSE_HEADERS:
                    continue
                if low == "location":
                    value = _rewrite_ddnsgo_location(value, base_url)
                self.send_header(key, value)
            self.send_header("Content-Length", str(len(out)))
            self.end_headers()
            if send_body:
                self.wfile.write(out)
            return True
        except Exception as exc:
            self._error(f"ddns-go proxy failed: {exc}", status=HTTPStatus.BAD_GATEWAY)
            return True

    def _client_ip(self) -> str:
        return (self.client_address[0] or "").strip()

    def _http_source_ip_pools(self, app_cfg: dict | None = None) -> dict:
        cfg = app_cfg if isinstance(app_cfg, dict) else load_app_config(_APP_ROOT_DIR)
        http_cfg = (cfg.get("http_service") or {}) if isinstance(cfg, dict) else {}
        return _normalize_source_ip_pools(http_cfg.get("source_ip_pools"))

    def _infer_process_source_by_row(
        self, row: dict | None, source_ip_pools: dict | None = None
    ) -> str:
        if not isinstance(row, dict):
            return ""

        def _host_from_endpoint(value: str) -> str:
            text = str(value or "").strip()
            if not text or text == "-":
                return ""
            if text.startswith("["):
                end = text.find("]")
                if end > 1:
                    return text[1:end].strip()
            if text.count(":") == 1:
                return text.rsplit(":", 1)[0].strip()
            return text

        for key in ("peer_host", "peer_ep", "local_host", "local_ep"):
            raw = str(row.get(key, "") or "").strip()
            if not raw:
                continue
            host = raw if key.endswith("_host") else _host_from_endpoint(raw)
            if not host:
                continue
            label = _match_source_label_by_ip(host, source_ip_pools)
            if label:
                return label
        return ""

    def _infer_transfer_source(
        self,
        relative_path: str,
        filename: str = "",
        user_agent: str = "",
        referer: str = "",
        client_ip: str = "",
        source_ip_pools: dict | None = None,
    ) -> str:
        rel = str(relative_path or "")
        name = str(filename or "")
        ua = str(user_agent or "")
        ref = str(referer or "")
        merged = f"{ua} {ref} {rel}/{name}".lower()
        for source, keywords in self.transfer_source_rules:
            if any(str(k).lower() in merged for k in keywords):
                return str(source)
        ip_source = _match_source_label_by_ip(client_ip, source_ip_pools)
        if ip_source:
            return ip_source
        return "Direct HTTP"

    def _is_lan_client(self) -> bool:
        ip_text = self._client_ip()
        if not ip_text:
            return False
        try:
            ip_obj = ipaddress.ip_address(ip_text)
        except ValueError:
            return False
        return (
            ip_obj.is_private
            or ip_obj.is_loopback
            or ip_obj.is_link_local
        )

    def _require_lan(self) -> bool:
        if self._is_lan_client():
            return True
        self._error("LAN-only access allowed for this page/API", status=HTTPStatus.FORBIDDEN)
        return False

    @staticmethod
    def _http_access_policy(app_cfg: dict | None = None) -> dict:
        cfg = app_cfg if isinstance(app_cfg, dict) else load_app_config(_APP_ROOT_DIR)
        return http_access.normalize_policy((cfg or {}).get("http_access"))

    def _require_http_access(self) -> bool:
        """Enforce the LAN-first access policy on public /http-files/ routes."""
        policy = self._http_access_policy()
        if http_access.is_allowed(policy, self._client_ip()):
            return True
        mode = http_access.effective_mode(policy).replace("_", "-")
        self._error(
            f"HTTP file service is {mode}; this address is not permitted",
            status=HTTPStatus.FORBIDDEN,
        )
        return False

    @classmethod
    def _http_access_status(cls, app_cfg: dict | None = None) -> dict:
        policy = cls._http_access_policy(app_cfg)
        return {
            "mode": policy["mode"],
            "effective_mode": http_access.effective_mode(policy),
            "public_until": policy["public_until"],
            "public_seconds_remaining": http_access.public_seconds_remaining(policy),
            "public_persistent": bool(
                policy.get("mode") == "public" and policy.get("public_until") is None
            ),
            "allowlist_count": len(policy["allowlist"]),
        }

    def _send_json(self, data: dict, status: int = HTTPStatus.OK, cors: bool = False):
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        if cors:
            self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(payload)

    def _send_html(self, html: str):
        payload = html.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        # 配置/Control页包含内联脚本，禁用缓存可避免前端逻辑更新后仍命中旧页面。
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _send_static_asset(
        self, rel_path: str, send_body: bool = True, cache_control: str = "private, max-age=300"
    ) -> bool:
        try:
            safe_rel = str(rel_path or "").strip().lstrip("/")
            if not safe_rel:
                return False
            web_root = (_APP_ROOT_DIR / "web").resolve()
            target = ensure_under_root(web_root, (web_root / safe_rel))
            if not target.exists() or not target.is_file():
                return False
            content_type, _ = mimetypes.guess_type(str(target))
            content_type = content_type or "application/octet-stream"
            data = target.read_bytes() if send_body else b""
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", str(cache_control or "private, max-age=300"))
            self.send_header("Content-Length", str(target.stat().st_size))
            self.end_headers()
            if send_body:
                self.wfile.write(data)
            return True
        except ValueError:
            self._error("Invalid static resource path", status=HTTPStatus.FORBIDDEN)
            return True
        except Exception as exc:
            self._error(f"Static resource read failed: {exc}", status=HTTPStatus.INTERNAL_SERVER_ERROR)
            return True

    def _error(self, message: str, status: int = HTTPStatus.BAD_REQUEST):
        self._send_json({"error": message}, status=status)

    @classmethod
    def _http_root_dir(cls, app_cfg=None) -> Path:
        cfg = app_cfg if isinstance(app_cfg, dict) else load_app_config(_APP_ROOT_DIR)
        http_cfg = (cfg.get("http_service") or {}) if isinstance(cfg, dict) else {}
        root_raw = http_cfg.get("root_dir", str(cls.storage_root))
        root = Path(_normalize_abs_dir_setting(root_raw, str(cls.storage_root)))
        if not root.exists() or not root.is_dir():
            return cls.storage_root
        return root

    @classmethod
    def _http_root_from_raw(cls, raw, app_cfg=None, require_exists: bool = True) -> Path:
        fallback = cls._http_root_dir(app_cfg)
        root = Path(_normalize_abs_dir_setting(raw, str(fallback)))
        if require_exists and (not root.exists() or not root.is_dir()):
            raise ValueError(f"HTTP 根Directory does not exist或不可访问: {root}")
        return root

    @classmethod
    def _qbt_reset_stats_cache(cls):
        with cls.qbt_stats_lock:
            cls.qbt_stats_cache["ts"] = 0.0
            cls.qbt_stats_cache["data"] = None

    @classmethod
    def _human_size(cls, size: int) -> str:
        units = ["B", "KB", "MB", "GB", "TB"]
        value = float(size)
        idx = 0
        while value >= 1024 and idx < len(units) - 1:
            value /= 1024.0
            idx += 1
        if idx == 0:
            return f"{int(value)}{units[idx]}"
        return f"{value:.1f}{units[idx]}"

    @classmethod
    def _systemd_show(cls, unit: str):
        if not unit:
            return None
        try:
            out = subprocess.run(
                ["systemctl", "show", unit, "--no-page", "--property=LoadState,ActiveState,SubState"],
                capture_output=True,
                text=True,
                check=False,
            )
            if out.returncode != 0:
                return None
            data = {}
            for line in out.stdout.splitlines():
                if "=" not in line:
                    continue
                k, v = line.split("=", 1)
                data[k] = v
            return {
                "unit": unit,
                "load_state": data.get("LoadState", "unknown"),
                "active_state": data.get("ActiveState", "unknown"),
                "sub_state": data.get("SubState", "unknown"),
            }
        except Exception:
            return None

    @classmethod
    def _resolve_existing_unit(cls, candidates):
        for unit in candidates:
            if not unit:
                continue
            info = cls._systemd_show(unit)
            if info and info.get("load_state") != "not-found":
                return info
        # fallback to first non-empty candidate as "not found"
        for unit in candidates:
            if unit:
                return {
                    "unit": unit,
                    "load_state": "not-found",
                    "active_state": "unknown",
                    "sub_state": "unknown",
                }
        return {
            "unit": "",
            "load_state": "not-found",
            "active_state": "unknown",
            "sub_state": "unknown",
        }

    @classmethod
    def _discover_unit_by_keywords(cls, keywords):
        keys = [k.lower() for k in keywords if k]
        if not keys:
            return None
        try:
            out = subprocess.run(
                ["systemctl", "list-units", "--type=service", "--all", "--no-legend", "--no-pager"],
                capture_output=True,
                text=True,
                check=False,
            )
            if out.returncode != 0:
                return None
            for line in out.stdout.splitlines():
                parts = line.split()
                if not parts:
                    continue
                unit = parts[0]
                low = unit.lower()
                if any(k in low for k in keys):
                    info = cls._systemd_show(unit)
                    if info:
                        return info
        except Exception:
            return None
        return None

    @classmethod
    def _qbt_runtime_settings(cls, app_cfg: dict | None = None) -> dict:
        cfg = app_cfg if isinstance(app_cfg, dict) else load_app_config(_APP_ROOT_DIR)
        qbt_cfg = (cfg.get("qbt") or {}) if isinstance(cfg, dict) else {}
        client = str(qbt_cfg.get("client", "") or "").strip().lower()
        if client not in {"qbittorrent", "deluge", "transmission", "rtorrent"}:
            client = "qbittorrent"
        return {
            "client": client,
            "service_unit": str(qbt_cfg.get("service_unit", "") or "").strip(),
            "docker_container": str(qbt_cfg.get("docker_container", "") or "").strip(),
            "api_url": str(qbt_cfg.get("api_url", "") or "").strip(),
            "api_username": DEFAULT_QBT_API_USERNAME,
            "api_password": DEFAULT_QBT_API_PASSWORD,
        }

    @classmethod
    def _bt_service_keywords(cls, client: str) -> tuple[str, ...]:
        c = str(client or "").strip().lower()
        return {
            "qbittorrent": ("qbit", "qbittorrent"),
            "deluge": ("deluge", "deluged"),
            "transmission": ("transmission",),
            "rtorrent": ("rtorrent",),
        }.get(c, ("qbit", "qbittorrent"))

    @classmethod
    def _qbt_discover_options(cls, app_cfg: dict | None = None) -> dict:
        settings = cls._qbt_runtime_settings(app_cfg)
        client = str(settings.get("client", "qbittorrent") or "qbittorrent")
        profile = {
            "qbittorrent": {
                "svc_keywords": cls._bt_service_keywords("qbittorrent"),
                "docker_keywords": ("qbit", "qbittorrent"),
            },
            "deluge": {
                "svc_keywords": cls._bt_service_keywords("deluge"),
                "docker_keywords": ("deluge",),
            },
            "transmission": {
                "svc_keywords": cls._bt_service_keywords("transmission"),
                "docker_keywords": ("transmission",),
            },
            "rtorrent": {
                "svc_keywords": cls._bt_service_keywords("rtorrent"),
                "docker_keywords": ("rtorrent",),
            },
        }.get(client, {"svc_keywords": cls._bt_service_keywords("qbittorrent"), "docker_keywords": ("qbit", "qbittorrent")})
        svc_keywords = tuple(str(x).lower() for x in profile["svc_keywords"])
        docker_keywords = tuple(str(x).lower() for x in profile["docker_keywords"])
        service_units = []
        seen_units = set()
        try:
            out = subprocess.run(
                ["systemctl", "list-unit-files", "--type=service", "--no-legend", "--no-pager"],
                capture_output=True,
                text=True,
                check=False,
            )
            if out.returncode == 0:
                for line in out.stdout.splitlines():
                    parts = line.split()
                    if not parts:
                        continue
                    unit = str(parts[0] or "").strip()
                    low = unit.lower()
                    if any(k in low for k in svc_keywords):
                        if unit not in seen_units:
                            seen_units.add(unit)
                            service_units.append(unit)
        except Exception:
            pass
        try:
            out = subprocess.run(
                ["systemctl", "list-units", "--type=service", "--all", "--no-legend", "--no-pager"],
                capture_output=True,
                text=True,
                check=False,
            )
            if out.returncode == 0:
                for line in out.stdout.splitlines():
                    parts = line.split()
                    if not parts:
                        continue
                    unit = str(parts[0] or "").strip()
                    low = unit.lower()
                    if any(k in low for k in svc_keywords):
                        if unit not in seen_units:
                            seen_units.add(unit)
                            service_units.append(unit)
        except Exception:
            pass

        docker_names = []
        seen_docker = set()
        try:
            out = subprocess.run(
                ["docker", "ps", "-a", "--format", "{{.Names}}"],
                capture_output=True,
                text=True,
                check=False,
            )
            if out.returncode == 0:
                for raw in out.stdout.splitlines():
                    name = str(raw or "").strip()
                    if not name:
                        continue
                    low = name.lower()
                    if any(k in low for k in docker_keywords) and name not in seen_docker:
                        seen_docker.add(name)
                        docker_names.append(name)
        except Exception:
            pass

        api_urls = []
        seen_urls = set()
        for base in cls._qbt_candidate_base_urls():
            x = str(base or "").strip()
            if not x or x in seen_urls:
                continue
            seen_urls.add(x)
            api_urls.append(x)

        return {
            "service_units": service_units,
            "docker_containers": docker_names,
            "api_urls": api_urls,
        }

    @classmethod
    def _qbt_effective_unit_from_settings(cls, app_cfg: dict | None = None) -> str:
        svc = cls._resolve_existing_unit(cls._qbt_service_candidates(app_cfg))
        if svc.get("load_state") != "not-found":
            return str(svc.get("unit", "") or "").strip()
        docker = cls._docker_qbt_container_info(app_cfg)
        if docker:
            return str(docker.get("unit", "") or "").strip()
        return str(svc.get("unit", "") or "").strip()

    @classmethod
    def _torrent_profile_write_paths(cls, client: str, user_home: Path) -> list[Path]:
        c = str(client or "").strip().lower()
        if c == "transmission":
            return [
                Path("/var/lib/transmission-daemon/info/settings.json"),
                user_home / ".config" / "transmission-daemon" / "settings.json",
            ]
        if c == "deluge":
            return [
                Path("/var/lib/deluged/config/core.conf"),
                user_home / ".config" / "deluge" / "core.conf",
            ]
        if c == "rtorrent":
            return [
                user_home / ".rtorrent.rc",
                Path("/etc/rtorrent.rc"),
            ]
        return []

    @classmethod
    def _optimize_torrent_non_qb(cls, client: str, unit: str) -> tuple[bool, str, dict]:
        c = str(client or "").strip().lower()
        svc = cls._resolve_existing_unit([unit]) if unit and not unit.startswith("docker:") else {"active_state": "unknown"}
        was_active = str((svc or {}).get("active_state", "") or "").strip() == "active"
        if unit and not was_active:
            cls._service_action(unit, "start")
            time.sleep(0.8)
        changed_path = ""
        try:
            user = "root"
            if unit and not unit.startswith("docker:"):
                props = cls._systemd_show_properties(unit, ["User"])
                user = str(props.get("User", "") or "").strip() or "root"
            try:
                user_home = Path(pwd.getpwnam(user).pw_dir).resolve()
            except Exception:
                user_home = Path("/root" if user == "root" else f"/home/{user}")
            for path in cls._torrent_profile_write_paths(c, user_home):
                p = Path(path)
                if c in {"transmission", "deluge"} and p.exists() and p.is_file():
                    raw = p.read_text(encoding="utf-8", errors="replace").strip()
                    data = {}
                    if raw:
                        if c == "deluge":
                            dec = json.JSONDecoder()
                            idx = 0
                            last_obj = None
                            while idx < len(raw):
                                while idx < len(raw) and raw[idx].isspace():
                                    idx += 1
                                if idx >= len(raw):
                                    break
                                obj, end = dec.raw_decode(raw, idx)
                                idx = end
                                if isinstance(obj, dict):
                                    last_obj = obj
                            data = last_obj or {}
                        else:
                            data = json.loads(raw)
                    if not isinstance(data, dict):
                        continue
                    if c == "transmission":
                        data["speed-limit-up-enabled"] = False
                        data["speed-limit-down-enabled"] = False
                        data["alt-speed-enabled"] = False
                        data["peer-limit-global"] = int(data.get("peer-limit-global", 500) or 500)
                    else:
                        data["max_upload_speed"] = -1.0
                        data["max_download_speed"] = -1.0
                        data["max_connections_global"] = int(data.get("max_connections_global", 500) or 500)
                    if c == "deluge":
                        header = {"file": 1, "format": 1}
                        payload = json.dumps(header, ensure_ascii=False, indent=4) + json.dumps(data, ensure_ascii=False, indent=4) + "\n"
                    else:
                        payload = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
                    p.write_text(payload, encoding="utf-8")
                    changed_path = str(p)
                    break
                if c == "rtorrent":
                    marker_start = "# --- afterclaw-rtorrent-optimize:start ---"
                    marker_end = "# --- afterclaw-rtorrent-optimize:end ---"
                    old = p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""
                    if marker_start in old and marker_end in old:
                        changed_path = str(p)
                        break
                    block = (
                        "\n"
                        + marker_start
                        + "\n"
                        + "throttle.global_down.max_rate.set_kb = 0\n"
                        + "throttle.global_up.max_rate.set_kb = 0\n"
                        + marker_end
                        + "\n"
                    )
                    p.write_text(old.rstrip() + block, encoding="utf-8")
                    changed_path = str(p)
                    break
        except Exception as exc:
            return False, str(exc), {"client": c, "unit": unit}
        if unit:
            cls._service_action(unit, "restart")
            time.sleep(0.8)
        return True, f"{c} optimization applied", {"client": c, "unit": unit, "changed_path": changed_path}

    @classmethod
    def _qbt_service_candidates(cls, app_cfg: dict | None = None) -> list[str]:
        settings = cls._qbt_runtime_settings(app_cfg)
        client = str(settings.get("client", "qbittorrent") or "qbittorrent")
        defaults_map = {
            "qbittorrent": [DEFAULT_QBT_SERVICE, "qbittorrent-nox", "qbt-nox"],
            "deluge": ["deluged", "deluge-web"],
            "transmission": ["transmission-daemon"],
            "rtorrent": ["rtorrent"],
        }
        out = []
        seen = set()
        for raw in [settings.get("service_unit", "")] + defaults_map.get(client, defaults_map["qbittorrent"]):
            unit = str(raw or "").strip()
            if not unit or unit in seen:
                continue
            seen.add(unit)
            out.append(unit)
        return out

    @classmethod
    def _qbt_docker_name_candidates(cls, app_cfg: dict | None = None) -> list[str]:
        names = []
        seen = set()
        settings = cls._qbt_runtime_settings(app_cfg)
        client = str(settings.get("client", "qbittorrent") or "qbittorrent")
        defaults_map = {
            "qbittorrent": list(DEFAULT_QBT_DOCKER_CONTAINERS),
            "deluge": ["deluge", "deluged"],
            "transmission": ["transmission", "transmission-daemon"],
            "rtorrent": ["rtorrent"],
        }

        def add(raw: str):
            text = str(raw or "").strip()
            if not text:
                return
            if text.endswith(".service"):
                text = text[: -len(".service")]
            if not text or text in seen:
                return
            seen.add(text)
            names.append(text)

        saved_container = str(settings.get("docker_container", "") or "").strip()
        if client == "qbittorrent":
            add(saved_container)
        elif saved_container:
            low_saved = saved_container.lower()
            allowed = {
                "deluge": ("deluge",),
                "transmission": ("transmission",),
                "rtorrent": ("rtorrent",),
            }.get(client, ())
            if any(k in low_saved for k in allowed):
                add(saved_container)
        for item in defaults_map.get(client, defaults_map["qbittorrent"]):
            add(item)
        for item in cls._qbt_service_candidates(app_cfg):
            add(item)
        return names

    @classmethod
    def _docker_qbt_container_info(cls, app_cfg: dict | None = None):
        names = cls._qbt_docker_name_candidates(app_cfg)

        for name in names:
            try:
                out = subprocess.run(
                    ["docker", "inspect", "-f", "{{.State.Status}}", name],
                    capture_output=True,
                    text=True,
                    check=False,
                )
            except Exception:
                return None
            if out.returncode != 0:
                continue
            status = str((out.stdout or "").strip() or "unknown").lower()
            active_state = "active" if status == "running" else "inactive"
            return {
                "unit": f"docker:{name}",
                "load_state": "loaded",
                "active_state": active_state,
                "sub_state": status,
                "detail": f"Docker container {name}: {status}",
            }

        try:
            out = subprocess.run(
                ["docker", "ps", "-a", "--format", "{{.Names}}\t{{.Status}}"],
                capture_output=True,
                text=True,
                check=False,
            )
        except Exception:
            return None
        if out.returncode != 0:
            return None
        lookup = {str(x).strip().lower() for x in names if str(x).strip()}
        for line in out.stdout.splitlines():
            text = str(line or "").strip()
            if not text or "\t" not in text:
                continue
            name, status_text = text.split("\t", 1)
            low = name.lower()
            if low not in lookup:
                continue
            st = str(status_text or "").strip().lower()
            active_state = "active" if st.startswith("up") else "inactive"
            return {
                "unit": f"docker:{name}",
                "load_state": "loaded",
                "active_state": active_state,
                "sub_state": st or "unknown",
                "detail": f"Docker container {name}: {status_text}",
            }
        return None

    @classmethod
    def _docker_container_action(cls, name: str, action: str):
        cname = str(name or "").strip()
        if not cname:
            return False, "docker 容器名为空"
        if action not in {"start", "stop", "restart"}:
            return False, "不支持的动作"
        try:
            out = subprocess.run(
                ["docker", action, cname],
                capture_output=True,
                text=True,
                check=False,
            )
        except Exception as exc:
            return False, str(exc)
        if out.returncode == 0:
            return True, ""
        msg = (out.stderr or out.stdout or "").strip()[:200]
        return False, msg or "docker 执行失败"

    @classmethod
    def _qbt_upgrade_snapshot(cls) -> dict:
        with cls.qbt_upgrade_lock:
            return dict(cls.qbt_upgrade_status or {})

    @classmethod
    def _set_qbt_upgrade_status(cls, **kwargs) -> dict:
        with cls.qbt_upgrade_lock:
            cur = dict(cls.qbt_upgrade_status or {})
            cur.update(kwargs)
            cur["updated_at"] = _utc_now_iso()
            cls.qbt_upgrade_status = cur
            return dict(cur)

    @classmethod
    def _qbt_upgrade_compose_meta(cls, container_name: str) -> dict:
        out = subprocess.run(
            ["docker", "inspect", container_name],
            capture_output=True,
            text=True,
            check=False,
        )
        if out.returncode != 0:
            raise RuntimeError((out.stderr or out.stdout or "docker inspect failed").strip())
        arr = json.loads(out.stdout or "[]")
        if not isinstance(arr, list) or not arr:
            raise RuntimeError("docker inspect returned empty result")
        obj = arr[0] if isinstance(arr[0], dict) else {}
        cfg = obj.get("Config") if isinstance(obj.get("Config"), dict) else {}
        labels = cfg.get("Labels") if isinstance(cfg.get("Labels"), dict) else {}
        image_ref = str(cfg.get("Image") or "").strip()
        project = str(labels.get("com.docker.compose.project") or "").strip()
        service = str(labels.get("com.docker.compose.service") or "").strip()
        working_dir = str(labels.get("com.docker.compose.project.working_dir") or "").strip()
        config_files_raw = str(labels.get("com.docker.compose.project.config_files") or "").strip()
        files = [x.strip() for x in config_files_raw.split(",") if x.strip()]
        if not (project and service and working_dir and files):
            raise RuntimeError("Container is not managed by docker compose labels")
        return {
            "image": image_ref,
            "project": project,
            "service": service,
            "working_dir": working_dir,
            "config_files": files,
        }

    @classmethod
    def _qbt_compose_cmd(cls, meta: dict, action: str) -> list[str]:
        cmd = ["docker", "compose"]
        wd = str(meta.get("working_dir") or "").strip()
        files = meta.get("config_files") or []
        if wd:
            cmd.extend(["--project-directory", wd])
        for f in files:
            if f:
                cmd.extend(["-f", str(f)])
        cmd.extend(["--project-name", str(meta.get("project") or "").strip()])
        service = str(meta.get("service") or "").strip()
        if action == "pull":
            cmd.extend(["pull", service])
        elif action == "up":
            cmd.extend(["up", "-d", "--no-deps", service])
        else:
            raise ValueError("unsupported compose action")
        return cmd

    @classmethod
    def _docker_image_id(cls, image_ref: str) -> str:
        ref = str(image_ref or "").strip()
        if not ref:
            return ""
        out = subprocess.run(
            ["docker", "image", "inspect", "-f", "{{.Id}}", ref],
            capture_output=True,
            text=True,
            check=False,
        )
        if out.returncode != 0:
            return ""
        return str(out.stdout or "").strip()

    @classmethod
    def _resolve_qbt_upgrade_target(cls, app_cfg: dict | None = None, client_hint: str = "", container_hint: str = "") -> dict:
        cfg = dict(app_cfg or {})
        qbt_cfg = cfg.get("qbt") if isinstance(cfg.get("qbt"), dict) else {}
        if not isinstance(qbt_cfg, dict):
            qbt_cfg = {}
        c = str(client_hint or qbt_cfg.get("client") or "qbittorrent").strip().lower()
        if c not in {"qbittorrent", "deluge", "transmission", "rtorrent"}:
            c = "qbittorrent"
        if container_hint:
            container = str(container_hint).strip()
        else:
            qbt_cfg2 = dict(qbt_cfg)
            qbt_cfg2["client"] = c
            cfg["qbt"] = qbt_cfg2
            info = cls._docker_qbt_container_info(cfg) or {}
            unit = str(info.get("unit") or "").strip()
            container = unit.split(":", 1)[1] if unit.startswith("docker:") else ""
        if not container:
            raise RuntimeError("No docker container detected for selected client")
        return {"client": c, "container": container}

    @classmethod
    def _qbt_upgrade_check(cls, app_cfg: dict | None = None, client_hint: str = "", container_hint: str = "") -> dict:
        target = cls._resolve_qbt_upgrade_target(app_cfg, client_hint, container_hint)
        meta = cls._qbt_upgrade_compose_meta(target["container"])
        before_id = cls._docker_image_id(meta.get("image", ""))
        pull_cmd = cls._qbt_compose_cmd(meta, "pull")
        pull = subprocess.run(pull_cmd, capture_output=True, text=True, check=False)
        if pull.returncode != 0:
            raise RuntimeError((pull.stderr or pull.stdout or "docker compose pull failed").strip())
        after_id = cls._docker_image_id(meta.get("image", ""))
        updatable = bool(before_id and after_id and before_id != after_id)
        output_text = ((pull.stdout or "") + "\n" + (pull.stderr or "")).strip()
        if not output_text:
            output_text = "Pull completed"
        msg = "Update available" if updatable else "Already up to date"
        return {
            "client": target["client"],
            "container": target["container"],
            "image": str(meta.get("image") or ""),
            "updatable": updatable,
            "message": msg,
            "detail": output_text[-1200:],
        }

    @classmethod
    def _qbt_upgrade_run(cls, app_cfg: dict | None = None, client_hint: str = "", container_hint: str = "") -> dict:
        with cls.qbt_upgrade_lock:
            if cls.qbt_upgrade_running:
                return dict(cls.qbt_upgrade_status or {})
            cls.qbt_upgrade_running = True
        try:
            target = cls._resolve_qbt_upgrade_target(app_cfg, client_hint, container_hint)
            cls._set_qbt_upgrade_status(
                running=True,
                state="running",
                client=target["client"],
                container=target["container"],
                message="Pulling latest image...",
                error="",
            )
            meta = cls._qbt_upgrade_compose_meta(target["container"])
            before_id = cls._docker_image_id(meta.get("image", ""))
            pull_cmd = cls._qbt_compose_cmd(meta, "pull")
            pull = subprocess.run(pull_cmd, capture_output=True, text=True, check=False)
            if pull.returncode != 0:
                raise RuntimeError((pull.stderr or pull.stdout or "docker compose pull failed").strip())
            mid_id = cls._docker_image_id(meta.get("image", ""))
            cls._set_qbt_upgrade_status(
                running=True,
                state="running",
                image=str(meta.get("image") or ""),
                message="Recreating container with updated image...",
            )
            up_cmd = cls._qbt_compose_cmd(meta, "up")
            up = subprocess.run(up_cmd, capture_output=True, text=True, check=False)
            if up.returncode != 0:
                raise RuntimeError((up.stderr or up.stdout or "docker compose up failed").strip())
            after_id = cls._docker_image_id(meta.get("image", ""))
            changed = bool(before_id and mid_id and before_id != mid_id)
            msg = "Client upgraded successfully" if changed else "Client recreated (already latest image)"
            detail = ((pull.stdout or "") + "\n" + (pull.stderr or "") + "\n" + (up.stdout or "") + "\n" + (up.stderr or "")).strip()
            return cls._set_qbt_upgrade_status(
                running=False,
                state="success",
                image=str(meta.get("image") or ""),
                message=msg,
                error="",
                updatable=changed,
                checked_at=_utc_now_iso(),
                detail=detail[-1200:],
                before_image_id=before_id,
                after_image_id=after_id,
            )
        except Exception as exc:
            return cls._set_qbt_upgrade_status(
                running=False,
                state="error",
                message="Upgrade failed",
                error=str(exc),
            )
        finally:
            with cls.qbt_upgrade_lock:
                cls.qbt_upgrade_running = False

    @classmethod
    def _service_action(cls, unit: str, action: str):
        if not unit:
            return False, "服务Not configured"
        if action not in {"start", "stop", "restart"}:
            return False, "不支持的动作"
        if str(unit).startswith("docker:"):
            cname = str(unit).split(":", 1)[1]
            return cls._docker_container_action(cname, action)
        try:
            out = subprocess.run(
                ["systemctl", action, unit],
                capture_output=True,
                text=True,
                check=False,
            )
            if out.returncode == 0:
                return True, ""
            msg = (out.stderr or out.stdout or "").strip()[:200]
            return False, msg or "systemctl 执行失败"
        except Exception as exc:
            return False, str(exc)

    @classmethod
    def _systemd_show_properties(cls, unit: str, properties: list[str]) -> dict:
        if not unit:
            return {}
        props = [str(x or "").strip() for x in (properties or []) if str(x or "").strip()]
        if not props:
            return {}
        try:
            out = subprocess.run(
                [
                    "systemctl",
                    "show",
                    unit,
                    "--no-page",
                    f"--property={','.join(props)}",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            if out.returncode != 0:
                return {}
            data = {}
            for line in out.stdout.splitlines():
                if "=" not in line:
                    continue
                k, v = line.split("=", 1)
                data[k.strip()] = v.strip()
            return data
        except Exception:
            return {}

    @classmethod
    def _qbt_service_meta(cls) -> dict:
        info = cls._resolve_existing_unit(cls._qbt_service_candidates())
        if info.get("load_state") == "not-found":
            settings = cls._qbt_runtime_settings()
            info = cls._discover_unit_by_keywords(cls._bt_service_keywords(settings.get("client", "qbittorrent"))) or info
        unit = str((info or {}).get("unit", "") or "").strip()
        if not unit or info.get("load_state") == "not-found":
            raise RuntimeError("未找到 qB 服务（systemd unit）")

        props = cls._systemd_show_properties(unit, ["User", "Environment", "ExecStart"])
        user = str(props.get("User", "") or "").strip() or "root"
        try:
            user_home = Path(pwd.getpwnam(user).pw_dir).resolve()
        except Exception:
            user_home = Path("/root" if user == "root" else f"/home/{user}")

        env_raw = str(props.get("Environment", "") or "")
        env_map = {}
        try:
            for token in shlex.split(env_raw):
                if "=" not in token:
                    continue
                k, v = token.split("=", 1)
                env_map[k.strip()] = v.strip()
        except Exception:
            env_map = {}
        env_home = str(env_map.get("HOME", "") or "").strip()
        exec_start = str(props.get("ExecStart", "") or "")

        profile_dirs = []
        for m in re.finditer(r"--profile(?:=|\s+)([^ ;\"']+)", exec_start):
            raw = str(m.group(1) or "").strip().strip("\"'")
            if not raw:
                continue
            try:
                profile_dirs.append(Path(os.path.expanduser(raw)).resolve())
            except Exception:
                continue

        candidates = []
        for pdir in profile_dirs:
            candidates.extend(
                [
                    pdir / "qBittorrent" / "config" / "qBittorrent.conf",
                    pdir / "qBittorrent" / "qBittorrent.conf",
                    pdir / "qBittorrent.conf",
                ]
            )
        home_candidates = []
        if env_home:
            home_candidates.append(Path(os.path.expanduser(env_home)))
        home_candidates.append(user_home)
        home_candidates.append(Path("/root"))
        for h in home_candidates:
            candidates.extend(
                [
                    h / ".config" / "qBittorrent" / "qBittorrent.conf",
                    h / ".config" / "qbittorrent" / "qBittorrent.conf",
                ]
            )

        seen = set()
        ordered = []
        for p in candidates:
            key = str(p)
            if key in seen:
                continue
            seen.add(key)
            ordered.append(p)
        if not ordered:
            ordered = [user_home / ".config" / "qBittorrent" / "qBittorrent.conf"]

        conf_path = None
        for c in ordered:
            try:
                if c.exists() and c.is_file():
                    conf_path = c
                    break
            except Exception:
                continue
        if conf_path is None:
            conf_path = ordered[0]

        return {
            "unit": unit,
            "active_state": str((info or {}).get("active_state", "") or "").strip(),
            "user": user,
            "home": str(user_home),
            "config_path": conf_path,
        }

    @classmethod
    def _qbt_fix_monitor_config(cls) -> tuple[bool, str, dict]:
        meta = cls._qbt_service_meta()
        unit = str(meta["unit"])
        user = str(meta["user"])
        conf_path = Path(meta["config_path"])
        was_active = str(meta.get("active_state", "") or "") == "active"
        stopped = False
        backup_path = ""
        changed_keys = []

        try:
            if was_active:
                ok, msg = cls._service_action(unit, "stop")
                if not ok:
                    raise RuntimeError(f"停止 qB 服务失败：{msg}")
                stopped = True
                time.sleep(0.6)

            conf_path.parent.mkdir(parents=True, exist_ok=True)
            prev_stat = conf_path.stat() if conf_path.exists() else None
            parser = configparser.ConfigParser(interpolation=None)
            parser.optionxform = str
            if conf_path.exists():
                raw = conf_path.read_text(encoding="utf-8", errors="replace")
                if raw.strip():
                    parser.read_string(raw)
            if not parser.has_section("Preferences"):
                parser.add_section("Preferences")
            prefs = parser["Preferences"]

            port_raw = str(prefs.get("WebUI\\Port", "") or "").strip()
            try:
                webui_port = int(port_raw)
                if webui_port <= 0 or webui_port > 65535:
                    webui_port = 8080
            except Exception:
                webui_port = 8080

            desired = {
                "WebUI\\Enabled": "true",
                "WebUI\\Address": "127.0.0.1",
                "WebUI\\Port": str(webui_port),
                "WebUI\\LocalHostAuth": "false",
            }
            for k, v in desired.items():
                old = str(prefs.get(k, "") or "")
                if old != v:
                    changed_keys.append(k)
                prefs[k] = v

            lines = []
            for section in parser.sections():
                lines.append(f"[{section}]")
                for k, v in parser.items(section):
                    lines.append(f"{k}={v}")
                lines.append("")
            payload = "\n".join(lines).rstrip() + "\n"

            if conf_path.exists():
                backup = conf_path.parent / f"{conf_path.name}.bak.{int(time.time())}"
                shutil.copy2(conf_path, backup)
                backup_path = str(backup)

            tmp = conf_path.parent / f"{conf_path.name}.tmp"
            tmp.write_text(payload, encoding="utf-8")
            try:
                if prev_stat is not None:
                    os.chmod(str(tmp), prev_stat.st_mode & 0o777)
                    os.chown(str(tmp), prev_stat.st_uid, prev_stat.st_gid)
                else:
                    pw = pwd.getpwnam(user)
                    os.chmod(str(tmp), 0o600)
                    os.chown(str(tmp), pw.pw_uid, pw.pw_gid)
            except Exception:
                pass
            os.replace(str(tmp), str(conf_path))

            if was_active:
                ok, msg = cls._service_action(unit, "start")
                if not ok:
                    raise RuntimeError(f"qB 服务启动失败：{msg}")
                stopped = False
                time.sleep(1.0)

            cls._qbt_reset_stats_cache()
            verify = cls._qbt_stats_snapshot() if was_active else {}
            verify_ok = bool((verify or {}).get("ok", False))
            detail = str((verify or {}).get("detail", "") or "").strip()
            msg = "qB Monitoring权限修复完成"
            if was_active and verify_ok:
                msg += "，已验证监控可用"
            elif was_active and detail:
                msg += f"，但监控仍提示：{detail[:180]}"
            return True, msg, {
                "unit": unit,
                "user": user,
                "config_path": str(conf_path),
                "backup_path": backup_path,
                "changed_keys": changed_keys,
                "was_active": was_active,
                "verify_ok": verify_ok,
                "verify_detail": detail,
            }
        except Exception as exc:
            if was_active and stopped:
                cls._service_action(unit, "start")
            return False, str(exc), {
                "unit": unit,
                "user": user,
                "config_path": str(conf_path),
                "backup_path": backup_path,
                "changed_keys": changed_keys,
                "was_active": was_active,
            }

    @classmethod
    def _qbt_optimize_config(cls, selected_qbt: dict | None = None) -> tuple[bool, str, dict]:
        selected = selected_qbt if isinstance(selected_qbt, dict) else {}
        merged_cfg = load_app_config(_APP_ROOT_DIR)
        if not isinstance(merged_cfg, dict):
            merged_cfg = {}
        qbt_cfg = dict((merged_cfg.get("qbt") or {}) if isinstance(merged_cfg.get("qbt"), dict) else {})
        for key in ("service_unit", "docker_container", "api_url"):
            if key in selected:
                qbt_cfg[key] = str(selected.get(key, "") or "").strip()
        if "client" in selected:
            client = str(selected.get("client", "") or "").strip().lower()
            if client in {"qbittorrent", "deluge", "transmission", "rtorrent"}:
                qbt_cfg["client"] = client
        merged_cfg["qbt"] = qbt_cfg
        client = str(qbt_cfg.get("client", "qbittorrent") or "qbittorrent")

        unit = cls._qbt_effective_unit_from_settings(merged_cfg)
        if unit:
            info = cls._resolve_existing_unit([unit]) if not unit.startswith("docker:") else {
                "active_state": "inactive"
            }
            active = str((info or {}).get("active_state", "") or "").strip() == "active"
            if not active:
                cls._service_action(unit, "start")
                time.sleep(0.8)

        if client != "qbittorrent":
            return cls._optimize_torrent_non_qb(client, unit)

        if str(unit).startswith("docker:"):
            desired = {
                "web_ui_upnp": False,
                "web_ui_host_header_validation_enabled": False,
                "web_ui_csrf_protection_enabled": False,
                "max_connec": -1,
                "max_connec_per_torrent": -1,
                "max_uploads": -1,
                "max_uploads_per_torrent": -1,
            }
            last_err = ""
            for base in cls._qbt_candidate_base_urls():
                try:
                    payload = json.dumps(desired, ensure_ascii=False).encode("utf-8")
                    cls._qbt_api_call_with_auth(
                        base,
                        "/api/v2/app/setPreferences",
                        method="POST",
                        body=urlencode({"json": payload.decode("utf-8")}).encode("utf-8"),
                        content_type="application/x-www-form-urlencoded",
                    )
                    cls._qbt_reset_stats_cache()
                    verify = cls._qbt_stats_snapshot()
                    return True, "BitTorrent optimization completed (Docker qBittorrent)", {
                        "unit": unit,
                        "mode": "docker-webapi",
                        "base_url": base,
                        "verify_ok": bool((verify or {}).get("ok", False)),
                        "verify_detail": str((verify or {}).get("detail", "") or "").strip(),
                    }
                except Exception as exc:
                    last_err = str(exc)
            return False, (last_err or "WebUI 不可达，无法优化 Docker qB"), {"unit": unit, "mode": "docker-webapi"}

        meta = cls._qbt_service_meta()
        unit = str(meta["unit"])
        user = str(meta["user"])
        conf_path = Path(meta["config_path"])
        was_active = str(meta.get("active_state", "") or "") == "active"
        stopped = False
        backup_path = ""
        try:
            if was_active:
                ok, msg = cls._service_action(unit, "stop")
                if not ok:
                    raise RuntimeError(f"停止 qB 服务失败：{msg}")
                stopped = True
                time.sleep(0.6)
            conf_path.parent.mkdir(parents=True, exist_ok=True)
            prev_stat = conf_path.stat() if conf_path.exists() else None
            raw = conf_path.read_text(encoding="utf-8", errors="replace") if conf_path.exists() else ""
            marker_start = "# --- fcc-qb-optimize:start ---"
            marker_end = "# --- fcc-qb-optimize:end ---"
            raw_lines = raw.splitlines()
            start_idx, end_idx = -1, -1
            for idx, line in enumerate(raw_lines):
                if line.strip() == marker_start:
                    start_idx = idx
                    break
            if start_idx >= 0:
                for idx in range(start_idx + 1, len(raw_lines)):
                    if raw_lines[idx].strip() == marker_end:
                        end_idx = idx
                        break
            cleaned_lines = raw_lines[:start_idx] + raw_lines[end_idx + 1 :] if (start_idx >= 0 and end_idx > start_idx) else raw_lines
            cleaned_raw = "\n".join(cleaned_lines).rstrip() + ("\n" if cleaned_lines else "")
            parser = configparser.ConfigParser(interpolation=None)
            parser.optionxform = str
            if cleaned_raw.strip():
                parser.read_string(cleaned_raw)
            if not parser.has_section("Preferences"):
                parser.add_section("Preferences")
            prefs = parser["Preferences"]
            try:
                webui_port = int(str(prefs.get("WebUI\\Port", "") or "").strip())
                if webui_port <= 0 or webui_port > 65535:
                    webui_port = 8080
            except Exception:
                webui_port = 8080
            desired = {
                "WebUI\\Enabled": "true",
                "WebUI\\Address": "127.0.0.1",
                "WebUI\\Port": str(webui_port),
                "WebUI\\LocalHostAuth": "false",
                "Connection\\GlobalDLLimit": "0",
                "Connection\\GlobalUPLimit": "0",
                "Connection\\GlobalDLLimitAlt": "0",
                "Connection\\GlobalUPLimitAlt": "0",
            }
            desired_keys = set(desired.keys())
            old_lines = cleaned_raw.splitlines() or ["[Preferences]"]
            rewritten_lines, commented_keys = [], set()
            in_preferences, preferences_exists = False, False
            for line in old_lines:
                stripped = line.strip()
                if stripped.startswith("[") and stripped.endswith("]"):
                    in_preferences = stripped.lower() == "[preferences]"
                    if in_preferences:
                        preferences_exists = True
                    rewritten_lines.append(line)
                    continue
                if in_preferences and stripped and not stripped.startswith(("#", ";")):
                    key = (line.split("=", 1)[0] if "=" in line else "").strip()
                    if key in desired_keys:
                        rewritten_lines.append(f"# {line}")
                        commented_keys.add(key)
                        continue
                rewritten_lines.append(line)
            if not preferences_exists:
                if rewritten_lines and rewritten_lines[-1].strip():
                    rewritten_lines.append("")
                rewritten_lines.append("[Preferences]")
            pref_start, pref_end = None, len(rewritten_lines)
            for idx, line in enumerate(rewritten_lines):
                if line.strip().lower() == "[preferences]":
                    pref_start = idx
                    break
            if pref_start is None:
                raise RuntimeError("Write failed: 未找到 [Preferences] 分组")
            for idx in range(pref_start + 1, len(rewritten_lines)):
                stripped = rewritten_lines[idx].strip()
                if stripped.startswith("[") and stripped.endswith("]"):
                    pref_end = idx
                    break
            optimize_block = ["", marker_start, "# managed by afterclaw"]
            optimize_block.extend([f"{k}={v}" for k, v in desired.items()])
            optimize_block.extend([marker_end, ""])
            payload = "\n".join((rewritten_lines[:pref_end] + optimize_block + rewritten_lines[pref_end:])).rstrip() + "\n"
            if conf_path.exists():
                backup = conf_path.parent / f"{conf_path.name}.bak.{int(time.time())}"
                shutil.copy2(conf_path, backup)
                backup_path = str(backup)
            tmp = conf_path.parent / f"{conf_path.name}.tmp"
            tmp.write_text(payload, encoding="utf-8")
            try:
                if prev_stat is not None:
                    os.chmod(str(tmp), prev_stat.st_mode & 0o777)
                    os.chown(str(tmp), prev_stat.st_uid, prev_stat.st_gid)
                else:
                    pw = pwd.getpwnam(user)
                    os.chmod(str(tmp), 0o600)
                    os.chown(str(tmp), pw.pw_uid, pw.pw_gid)
            except Exception:
                pass
            os.replace(str(tmp), str(conf_path))
            if was_active:
                ok, msg = cls._service_action(unit, "start")
                if not ok:
                    raise RuntimeError(f"qB 服务启动失败：{msg}")
                stopped = False
                time.sleep(1.0)
            cls._qbt_reset_stats_cache()
            verify = cls._qbt_stats_snapshot() if was_active else {}
            verify_ok = bool((verify or {}).get("ok", False))
            detail = str((verify or {}).get("detail", "") or "").strip()
            msg = "BitTorrent optimization completed"
            if was_active and verify_ok:
                msg += "，监控已恢复"
            elif was_active and detail:
                msg += f"，但监控仍提示：{detail[:180]}"
            return True, msg, {
                "unit": unit,
                "user": user,
                "config_path": str(conf_path),
                "backup_path": backup_path,
                "desired_keys": list(desired.keys()),
                "commented_keys": sorted(commented_keys),
                "was_active": was_active,
                "verify_ok": verify_ok,
                "verify_detail": detail,
            }
        except Exception as exc:
            if was_active and stopped:
                cls._service_action(unit, "start")
            return False, str(exc), {
                "unit": unit,
                "user": user,
                "config_path": str(conf_path),
                "backup_path": backup_path,
                "was_active": was_active,
            }

    @classmethod
    def _system_status(cls):
        now = time.time()
        # load average
        try:
            load1, load5, load15 = os.getloadavg()
        except Exception:
            load1, load5, load15 = 0.0, 0.0, 0.0
        # memory
        mem_total = 0
        mem_avail = 0
        try:
            with open("/proc/meminfo", "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        mem_total = int(line.split()[1]) * 1024
                    elif line.startswith("MemAvailable:"):
                        mem_avail = int(line.split()[1]) * 1024
        except Exception:
            pass
        mem_used = max(mem_total - mem_avail, 0)
        # disk
        try:
            root_for_disk = cls._http_root_dir()
            st = os.statvfs(str(root_for_disk))
            disk_total = st.f_frsize * st.f_blocks
            disk_free = st.f_frsize * st.f_bavail
            disk_used = max(disk_total - disk_free, 0)
        except Exception:
            disk_total = disk_used = 0
        # uptime
        uptime_sec = 0.0
        try:
            with open("/proc/uptime", "r", encoding="utf-8") as f:
                uptime_sec = float((f.read().split() or ["0"])[0])
        except Exception:
            pass
        days = int(uptime_sec // 86400)
        hours = int((uptime_sec % 86400) // 3600)
        minutes = int((uptime_sec % 3600) // 60)
        uptime_human = f"{days}d {hours}h {minutes}m"
        return {
            "timestamp": now,
            "load1": load1,
            "load5": load5,
            "load15": load15,
            "mem_total": mem_total,
            "mem_used": mem_used,
            "mem_total_human": cls._human_size(mem_total),
            "mem_used_human": cls._human_size(mem_used),
            "disk_total": disk_total,
            "disk_used": disk_used,
            "disk_total_human": cls._human_size(disk_total),
            "disk_used_human": cls._human_size(disk_used),
            "uptime_seconds": uptime_sec,
            "uptime_human": uptime_human,
        }

    @classmethod
    def _qbt_api_join(cls, base_url: str, path: str) -> str:
        base = (base_url or "").strip().rstrip("/")
        if not base:
            base = "http://127.0.0.1:8080"
        if not base.startswith(("http://", "https://")):
            base = "http://" + base
        api_path = path if path.startswith("/") else "/" + path
        if base.endswith("/api/v2"):
            if api_path.startswith("/api/v2/"):
                return base + api_path[len("/api/v2") :]
            if api_path == "/api/v2":
                return base
        return base + api_path

    @classmethod
    def _qbt_rate_text(cls, bps: int) -> str:
        n = max(0, int(bps or 0))
        return f"{cls._human_size(n)}/s"

    @classmethod
    def _qbt_to_int(cls, value, default: int = 0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @classmethod
    def _qbt_base_url(cls) -> str:
        settings = cls._qbt_runtime_settings()
        base = str(settings.get("api_url", "") or "").strip() or (DEFAULT_QBT_API_URL or "").strip()
        if not base:
            base = "http://127.0.0.1:8080"
        if not base.startswith(("http://", "https://")):
            base = "http://" + base
        return base.rstrip("/")

    @classmethod
    def _qbt_candidate_base_urls(cls) -> list[str]:
        urls = []
        seen = set()

        def add(raw: str):
            base = str(raw or "").strip()
            if not base:
                return
            if not base.startswith(("http://", "https://")):
                base = "http://" + base
            base = base.rstrip("/")
            if base in seen:
                return
            seen.add(base)
            urls.append(base)

        env_base = cls._qbt_base_url()
        add(env_base)
        try:
            parsed_env = urlparse(env_base)
            if parsed_env.port:
                add(f"{parsed_env.scheme or 'http'}://127.0.0.1:{parsed_env.port}")
        except Exception:
            pass

        try:
            meta = cls._qbt_service_meta()
            conf_path = Path(meta.get("config_path", ""))
            if conf_path.exists() and conf_path.is_file():
                parser = configparser.ConfigParser(interpolation=None)
                parser.optionxform = str
                raw = conf_path.read_text(encoding="utf-8", errors="replace")
                if raw.strip():
                    parser.read_string(raw)
                prefs = parser["Preferences"] if parser.has_section("Preferences") else {}
                addr = str(prefs.get("WebUI\\Address", "") or "").strip()
                port_raw = str(prefs.get("WebUI\\Port", "") or "").strip()
                try:
                    port = int(port_raw)
                    if port <= 0 or port > 65535:
                        port = 8080
                except Exception:
                    port = 8080

                local_aliases = {"", "*", "0.0.0.0", "::", "::0", "::1", "localhost", "127.0.0.1"}
                if addr in local_aliases:
                    add(f"http://127.0.0.1:{port}")
                else:
                    if ":" in addr and not addr.startswith("["):
                        add(f"http://[{addr}]:{port}")
                    else:
                        add(f"http://{addr}:{port}")
                    add(f"http://127.0.0.1:{port}")
        except Exception:
            pass

        add("http://127.0.0.1:8080")
        return urls

    @classmethod
    def _qbt_fetch_maindata_at_base(cls, base: str) -> dict:
        settings = cls._qbt_runtime_settings()
        api_user = str(settings.get("api_username", "") or "").strip()
        api_pass = str(settings.get("api_password", "") or "").strip()
        jar = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
        headers = {
            "User-Agent": "storage-ctrl-qbt/1",
            "Accept": "application/json",
        }

        def fetch_maindata() -> dict:
            url = cls._qbt_api_join(base, "/api/v2/sync/maindata?rid=0")
            req = urllib.request.Request(url, headers=headers)
            with opener.open(req, timeout=6) as resp:
                raw = (resp.read() or b"").decode("utf-8", errors="replace")
            data = json.loads(raw or "{}")
            if not isinstance(data, dict):
                raise RuntimeError("qBittorrent 返回了异常数据")
            return data

        try:
            return fetch_maindata()
        except urllib.error.HTTPError as e:
            if e.code not in (401, 403):
                raise RuntimeError(f"WebUI HTTP {e.code}") from e
            if not (api_user and api_pass):
                raise RuntimeError(
                    "WebUI 需要登录，请配置 QBT_API_USERNAME / QBT_API_PASSWORD"
                ) from e

        login_url = cls._qbt_api_join(base, "/api/v2/auth/login")
        login_body = urlencode(
            {
                "username": api_user,
                "password": api_pass,
            }
        ).encode("utf-8")
        login_headers = {
            "User-Agent": "storage-ctrl-qbt/1",
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": (base.rstrip("/") + "/"),
        }
        req = urllib.request.Request(
            login_url,
            data=login_body,
            method="POST",
            headers=login_headers,
        )
        try:
            with opener.open(req, timeout=6) as resp:
                text = (resp.read() or b"").decode("utf-8", errors="replace").strip()
            if text != "Ok.":
                raise RuntimeError("WebUI 登录失败（用户名或密码错误）")
            return fetch_maindata()
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"WebUI 登录失败（HTTP {e.code}）") from e
        except urllib.error.URLError as e:
            raise RuntimeError(f"WebUI 不可达: {e}") from e

    @classmethod
    def _qbt_api_call_with_auth(
        cls,
        base: str,
        api_path: str,
        method: str = "GET",
        body: bytes | None = None,
        content_type: str | None = None,
    ) -> tuple[int, str]:
        settings = cls._qbt_runtime_settings()
        api_user = str(settings.get("api_username", "") or "").strip()
        api_pass = str(settings.get("api_password", "") or "").strip()
        jar = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
        headers = {"User-Agent": "storage-ctrl-qbt/1"}
        if content_type:
            headers["Content-Type"] = str(content_type)
        req = urllib.request.Request(
            cls._qbt_api_join(base, api_path),
            data=body,
            method=str(method or "GET").upper(),
            headers=headers,
        )
        try:
            with opener.open(req, timeout=6) as resp:
                return int(resp.getcode() or 200), (
                    (resp.read() or b"").decode("utf-8", errors="replace")
                )
        except urllib.error.HTTPError as e:
            if e.code not in (401, 403):
                raise
            if not (api_user and api_pass):
                raise RuntimeError("WebUI 需要登录，请配置 QBT_API_USERNAME / QBT_API_PASSWORD") from e
        login_body = urlencode({"username": api_user, "password": api_pass}).encode("utf-8")
        login_req = urllib.request.Request(
            cls._qbt_api_join(base, "/api/v2/auth/login"),
            data=login_body,
            method="POST",
            headers={
                "User-Agent": "storage-ctrl-qbt/1",
                "Content-Type": "application/x-www-form-urlencoded",
                "Referer": (base.rstrip("/") + "/"),
            },
        )
        with opener.open(login_req, timeout=6) as resp:
            text = (resp.read() or b"").decode("utf-8", errors="replace").strip()
        if text != "Ok.":
            raise RuntimeError("WebUI 登录失败（用户名或密码错误）")
        with opener.open(req, timeout=6) as resp:
            return int(resp.getcode() or 200), (
                (resp.read() or b"").decode("utf-8", errors="replace")
            )

    @classmethod
    def _qbt_fetch_maindata_once(cls) -> dict:
        errors = []
        for base in cls._qbt_candidate_base_urls():
            try:
                return cls._qbt_fetch_maindata_at_base(base)
            except Exception as exc:
                errors.append(f"{base}: {exc}")
        if not errors:
            raise RuntimeError("WebUI 不可达")
        raise RuntimeError(" | ".join(errors[:3])[:260])

    @classmethod
    def _qbt_shutdown_at_base(cls, base: str) -> tuple[bool, str]:
        settings = cls._qbt_runtime_settings()
        api_user = str(settings.get("api_username", "") or "").strip()
        api_pass = str(settings.get("api_password", "") or "").strip()
        jar = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
        headers = {
            "User-Agent": "storage-ctrl-qbt/1",
            "Referer": (base + "/"),
        }

        def shutdown_call() -> None:
            url = cls._qbt_api_join(base, "/api/v2/app/shutdown")
            req = urllib.request.Request(url, data=b"", method="POST", headers=headers)
            with opener.open(req, timeout=6):
                return

        try:
            shutdown_call()
            return True, "已发送 Quit qB指令"
        except urllib.error.HTTPError as e:
            if e.code not in (401, 403):
                return False, f"WebUI HTTP {e.code}"
            if not (api_user and api_pass):
                return False, "WebUI 需要登录，请配置 QBT_API_USERNAME / QBT_API_PASSWORD"
        except urllib.error.URLError as e:
            return False, f"WebUI 不可达: {e}"
        except Exception as e:
            return False, str(e)

        login_url = cls._qbt_api_join(base, "/api/v2/auth/login")
        login_body = urlencode(
            {
                "username": api_user,
                "password": api_pass,
            }
        ).encode("utf-8")
        login_headers = {
            "User-Agent": "storage-ctrl-qbt/1",
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": (base + "/"),
        }
        req = urllib.request.Request(
            login_url,
            data=login_body,
            method="POST",
            headers=login_headers,
        )
        try:
            with opener.open(req, timeout=6) as resp:
                text = (resp.read() or b"").decode("utf-8", errors="replace").strip()
            if text != "Ok.":
                return False, "WebUI 登录失败（用户名或密码错误）"
            shutdown_call()
            return True, "已发送 Quit qB指令"
        except urllib.error.HTTPError as e:
            return False, f"WebUI 登录失败（HTTP {e.code}）"
        except urllib.error.URLError as e:
            return False, f"WebUI 不可达: {e}"
        except Exception as e:
            return False, str(e)

    @classmethod
    def _qbt_shutdown_once(cls) -> tuple[bool, str]:
        last_msg = "WebUI 不可达"
        for base in cls._qbt_candidate_base_urls():
            ok, msg = cls._qbt_shutdown_at_base(base)
            if ok:
                return True, msg
            last_msg = msg
            if "需要登录" in msg or "登录失败" in msg:
                return False, msg
        return False, last_msg

    @classmethod
    def _qbt_stats_snapshot(cls) -> dict:
        now = time.time()
        with cls.qbt_stats_lock:
            cached = cls.qbt_stats_cache.get("data")
            cached_ts = float(cls.qbt_stats_cache.get("ts", 0.0) or 0.0)
            if cached and (now - cached_ts) < 4.0:
                return dict(cached)

        try:
            payload = cls._qbt_fetch_maindata_once()
            server = payload.get("server_state") if isinstance(payload, dict) else {}
            server = server if isinstance(server, dict) else {}
            torrents_raw = payload.get("torrents") if isinstance(payload, dict) else {}
            if isinstance(torrents_raw, dict):
                torrents = list(torrents_raw.values())
            elif isinstance(torrents_raw, list):
                torrents = torrents_raw
            else:
                torrents = []

            dl_states = {
                "downloading",
                "forceddl",
                "metadl",
                "stalleddl",
                "queueddl",
                "checkingdl",
                "pauseddl",
                "allocating",
                "moving",
            }
            up_states = {
                "uploading",
                "forcedup",
                "stalledup",
                "queuedup",
                "checkingup",
                "pausedup",
            }
            downloading = 0
            seeding = 0
            paused = 0
            errored = 0
            active = 0
            for item in torrents:
                state = str((item or {}).get("state") or "").strip().lower()
                if not state:
                    continue
                if state in dl_states:
                    downloading += 1
                if state in up_states:
                    seeding += 1
                if state.startswith("paused"):
                    paused += 1
                if "error" in state or state in {"missingfiles", "unknown"}:
                    errored += 1
                if (not state.startswith("paused")) and (state not in {"error", "unknown"}):
                    active += 1

            dl_bps = cls._qbt_to_int(server.get("dl_info_speed"))
            up_bps = cls._qbt_to_int(server.get("up_info_speed"))
            peers = cls._qbt_to_int(server.get("total_peer_connections"))
            dht_nodes = cls._qbt_to_int(server.get("dht_nodes"))
            detail = (
                f"↓ {cls._qbt_rate_text(dl_bps)} · ↑ {cls._qbt_rate_text(up_bps)}"
                f" | Seeding {seeding} · Downloading {downloading} · Active {active} · Total {len(torrents)}"
            )
            if peers > 0:
                detail += f" · Connections {peers}"
            if dht_nodes > 0:
                detail += f" · DHT {dht_nodes}"
            version = str(
                server.get("qbittorrent_version")
                or server.get("qbt_version")
                or payload.get("version", "")
                or ""
            ).strip()
            if version:
                detail += f" · v{version}"

            data = {
                "ok": True,
                "detail": detail,
                "dl_bps": dl_bps,
                "up_bps": up_bps,
                "seeding": seeding,
                "downloading": downloading,
                "active": active,
                "paused": paused,
                "errored": errored,
                "total": len(torrents),
                "peers": peers,
                "dht_nodes": dht_nodes,
                "version": version,
            }
        except Exception as exc:
            msg = str(exc) or "未知错误"
            data = {
                "ok": False,
                "detail": f"WebUI 统计不可用: {msg[:180]}",
                "error": msg[:180],
            }

        with cls.qbt_stats_lock:
            cls.qbt_stats_cache["ts"] = time.time()
            cls.qbt_stats_cache["data"] = data
        return dict(data)

    @classmethod
    def _control_status_payload(cls, client_override: str = ""):
        app_cfg = load_app_config(_APP_ROOT_DIR)
        if isinstance(app_cfg, dict):
            qcfg = app_cfg.get("qbt")
            if not isinstance(qcfg, dict):
                qcfg = {}
            co = str(client_override or "").strip().lower()
            if co in {"qbittorrent", "deluge", "transmission", "rtorrent"}:
                qcfg = dict(qcfg)
                qcfg["client"] = co
                app_cfg["qbt"] = qcfg
        qbt_cfg = (app_cfg or {}).get("qbt") or {}
        bt_client = str(qbt_cfg.get("client", "qbittorrent") or "qbittorrent").strip().lower()
        http_module_on = cls._http_module_enabled()
        qbt = cls._resolve_existing_unit(cls._qbt_service_candidates(app_cfg))
        if qbt.get("load_state") == "not-found":
            qbt = cls._discover_unit_by_keywords(cls._bt_service_keywords(bt_client)) or qbt
        docker_qbt = cls._docker_qbt_container_info(app_cfg)
        if docker_qbt:
            systemd_active = str(qbt.get("active_state", "") or "").strip() == "active"
            docker_active = (
                str(docker_qbt.get("active_state", "") or "").strip() == "active"
            )
            if (
                (qbt.get("load_state") == "not-found")
                or (not systemd_active)
                or docker_active
            ):
                qbt = docker_qbt
        if qbt.get("active_state") == "active" and bt_client == "qbittorrent":
            qbt_stats = cls._qbt_stats_snapshot()
            if qbt_stats.get("detail"):
                qbt["detail"] = qbt_stats.get("detail")
            if qbt_stats.get("ok"):
                qbt["stats"] = qbt_stats
        elif qbt.get("active_state") == "active" and bt_client != "qbittorrent":
            client_label = {
                "deluge": "Deluge",
                "transmission": "Transmission",
                "rtorrent": "rTorrent",
            }.get(bt_client, "BitTorrent")
            qbt_stats = {
                "ok": True,
                "detail": "↓ 0B/s · ↑ 0B/s | Seeding 0 · Downloading 0 · Active 0 · Total 0",
                "dl_bps": 0,
                "up_bps": 0,
                "seeding": 0,
                "downloading": 0,
                "active": 0,
                "paused": 0,
                "errored": 0,
                "total": 0,
                "peers": 0,
                "dht_nodes": 0,
                "version": "",
            }
            qbt["detail"] = f"{client_label} · {qbt_stats['detail']}"
            qbt["stats"] = qbt_stats
        ddns_svc = ddns.merge_builtin_into_systemd_shape(_APP_ROOT_DIR)
        if ddns_svc is None:
            ddns_svc = cls._resolve_existing_unit(cls.ddns_candidates)
            if ddns_svc.get("load_state") == "not-found":
                ddns_svc = cls._discover_unit_by_keywords(
                    ["ddns", "duckdns", "cloudflare", "dnspod", "ddns-go"]
                ) or ddns_svc
        self_svc = cls._systemd_show("storage-http-link-web") or {
            "unit": "storage-http-link-web",
            "load_state": "unknown",
            "active_state": "unknown",
            "sub_state": "unknown",
        }
        if not http_module_on:
            self_svc["detail"] = "HTTP module is disabled（仅本程序 /http-files 上传节点被禁用）"
        return {
            "system": cls._system_status(),
            "qbt": qbt,
            "ddns": ddns_svc,
            "self": self_svc,
            "http_access": cls._http_access_status(app_cfg),
            "app_config": app_cfg,
        }

    def _transfer_snapshot(self):
        now = time.time()
        source_ip_pools = self._http_source_ip_pools()
        with self.transfers_lock:
            items = []
            source_agg = {}
            total_sent_all = 0
            total_size_all = 0
            active_count = 0
            recent_count = 0
            stale_ids = []
            recent_ttl = float(
                getattr(self, "transfer_recent_ttl_sec", DEFAULT_TRANSFER_RECENT_TTL_SEC)
                or DEFAULT_TRANSFER_RECENT_TTL_SEC
            )
            for tid, t in self.active_transfers.items():
                done = bool(t.get("done", False))
                started_at = float(t.get("started_at", now))
                ended_at = float(t.get("ended_at", 0.0) or 0.0)
                if done and ended_at > 0 and (now - ended_at) > recent_ttl:
                    stale_ids.append(tid)
                    continue
                if done:
                    recent_count += 1
                else:
                    active_count += 1
                elapsed_end = ended_at if done and ended_at > 0 else now
                elapsed = max(elapsed_end - started_at, 0.001)
                sent = int(t.get("sent_bytes", 0))
                total = int(t.get("total_bytes", 0))
                file_total = int(t.get("file_total_bytes", total))
                if file_total <= 0:
                    file_total = total
                is_partial = bool(t.get("is_partial", False))
                range_start = int(t.get("range_start", 0))
                range_end = int(t.get("range_end", max(total - 1, 0)))
                if range_end < range_start:
                    range_end = range_start
                mibps = sent / 1024.0 / 1024.0 / elapsed
                stored_source = str(t.get("source", "") or "").strip()
                source = (
                    stored_source
                    if stored_source and stored_source != "Direct HTTP"
                    else self._infer_transfer_source(
                        str(t.get("relative_path", "") or ""),
                        str(t.get("filename", "") or ""),
                        str(t.get("user_agent", "") or ""),
                        str(t.get("referer", "") or ""),
                        str(t.get("client_ip", "") or ""),
                        source_ip_pools,
                    )
                )
                if not done:
                    total_sent_all += sent
                    total_size_all += total
                    source_row = source_agg.setdefault(
                        source,
                        {
                            "source": source,
                            "count": 0,
                            "sent_bytes": 0,
                            "total_bytes": 0,
                            "speed_mibps": 0.0,
                        },
                    )
                    source_row["count"] = int(source_row.get("count", 0)) + 1
                    source_row["sent_bytes"] = int(source_row.get("sent_bytes", 0)) + sent
                    source_row["total_bytes"] = int(source_row.get("total_bytes", 0)) + total
                    source_row["speed_mibps"] = float(source_row.get("speed_mibps", 0.0)) + mibps
                items.append(
                    {
                        "id": tid,
                        "done": done,
                        "started_at": started_at,
                        "ended_at": ended_at if done else 0.0,
                        "source": source,
                        "client_ip": t.get("client_ip", ""),
                        "relative_path": t.get("relative_path", ""),
                        "filename": t.get("filename", ""),
                        "sent_bytes": sent,
                        "sent_human": self._human_size(sent),
                        "total_bytes": total,
                        "total_human": self._human_size(total),
                        "file_total_bytes": file_total,
                        "file_total_human": self._human_size(file_total),
                        "is_partial": is_partial,
                        "range_start": range_start,
                        "range_end": range_end,
                        "progress_pct": (sent * 100.0 / total) if total > 0 else 0.0,
                        "speed_mibps": mibps,
                    }
                )
            for tid in stale_ids:
                self.active_transfers.pop(tid, None)
        items.sort(key=lambda x: max(float(x.get("ended_at", 0.0) or 0.0), float(x.get("started_at", 0.0) or 0.0)), reverse=True)
        source_stats = []
        for source, row in source_agg.items():
            sent = int(row.get("sent_bytes", 0))
            total = int(row.get("total_bytes", 0))
            speed_mibps = float(row.get("speed_mibps", 0.0))
            source_stats.append(
                {
                    "source": source,
                    "count": int(row.get("count", 0)),
                    "sent_bytes": sent,
                    "sent_human": self._human_size(sent),
                    "total_bytes": total,
                    "total_human": self._human_size(total),
                    "progress_pct": (sent * 100.0 / total) if total > 0 else 0.0,
                    # HTTP 外链下载表示“本机向外发送”，按本机视角应计入上传。
                    "download_mibps": 0.0,
                    "upload_mibps": speed_mibps,
                }
            )
        # 合并“非 1288 通道”的Netdisk App 进程流量（如 baidunetdisk）。
        process_speeds = self.process_speed_sampler.source_speed_snapshot(
            lambda row: self._infer_process_source_by_row(row, source_ip_pools)
        )
        if process_speeds:
            idx = {str(x.get("source", "")): x for x in source_stats}
            for source, row in process_speeds.items():
                src = str(source or "").strip()
                if not src:
                    continue
                down = float(row.get("download_mibps", 0.0) or 0.0)
                up = float(row.get("upload_mibps", 0.0) or 0.0)
                cnt = int(row.get("count", 0) or 0)
                if src in idx:
                    cur = idx[src]
                    cur["download_mibps"] = float(cur.get("download_mibps", 0.0)) + down
                    cur["upload_mibps"] = float(cur.get("upload_mibps", 0.0)) + up
                    cur["count"] = int(cur.get("count", 0)) + cnt
                else:
                    merged = {
                        "source": src,
                        "count": cnt,
                        "sent_bytes": 0,
                        "sent_human": "0B",
                        "total_bytes": 0,
                        "total_human": "0B",
                        "progress_pct": 0.0,
                        "download_mibps": down,
                        "upload_mibps": up,
                    }
                    source_stats.append(merged)
                    idx[src] = merged
        source_stats.sort(key=lambda x: (-float(x.get("download_mibps", 0.0)), str(x.get("source", ""))))
        return {
            "items": items,
            "count": active_count,
            "recent_count": recent_count,
            "overall_progress_pct": (total_sent_all * 100.0 / total_size_all) if total_size_all > 0 else 0.0,
            "source_stats": source_stats,
        }

    def _parse_body(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length > 0 else b"{}"
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {}

    @classmethod
    def _terminal_normalize_size(cls, cols, rows):
        try:
            c = int(cols)
        except Exception:
            c = 120
        try:
            r = int(rows)
        except Exception:
            r = 30
        c = max(20, min(c, 320))
        r = max(8, min(r, 120))
        return c, r

    @classmethod
    def _terminal_set_winsize(cls, fd: int, cols: int, rows: int):
        c, r = cls._terminal_normalize_size(cols, rows)
        buf = struct.pack("HHHH", r, c, 0, 0)
        try:
            fcntl.ioctl(fd, termios.TIOCSWINSZ, buf)
        except Exception:
            pass

    @classmethod
    def _terminal_close_session_locked(cls, sid: str):
        sess = cls.terminal_sessions.pop(sid, None)
        if not sess:
            return False
        fd = sess.get("fd")
        if isinstance(fd, int):
            try:
                os.close(fd)
            except Exception:
                pass
        proc = sess.get("proc")
        if proc is not None:
            try:
                if proc.poll() is None:
                    proc.terminate()
                    try:
                        proc.wait(timeout=0.4)
                    except Exception:
                        proc.kill()
            except Exception:
                pass
        return True

    @classmethod
    def _terminal_cleanup_locked(cls):
        now = time.time()
        for sid in list(cls.terminal_sessions.keys()):
            sess = cls.terminal_sessions.get(sid) or {}
            proc = sess.get("proc")
            last = float(sess.get("last_active", now) or now)
            should_close = (now - last) > float(cls.terminal_session_ttl_sec)
            dead = (proc is None) or (proc.poll() is not None)
            if dead:
                dead_since = float(sess.get("dead_since", 0.0) or 0.0)
                if dead_since <= 0:
                    sess["dead_since"] = now
                    continue
                # 保留一小段时间，允许前端读到退出输出和状态。
                if (now - dead_since) < 180:
                    continue
                should_close = True
            if should_close:
                cls._terminal_close_session_locked(sid)

    @classmethod
    def _terminal_start_session(cls, cols, rows):
        cfg = load_app_config(_APP_ROOT_DIR)
        argv, meta = _build_terminal_ssh_argv(cfg)
        c, r = cls._terminal_normalize_size(cols, rows)
        with cls.terminal_lock:
            cls._terminal_cleanup_locked()
            if len(cls.terminal_sessions) >= int(cls.terminal_max_sessions):
                raise RuntimeError("终端会话过多，请先关闭不用的会话")

        master_fd = None
        slave_fd = None
        proc = None
        try:
            master_fd, slave_fd = pty.openpty()
            cls._terminal_set_winsize(slave_fd, c, r)
            proc = subprocess.Popen(
                argv,
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                close_fds=True,
                start_new_session=True,
            )
            os.close(slave_fd)
            slave_fd = None
            os.set_blocking(master_fd, False)
            sid = uuid.uuid4().hex
            now = time.time()
            with cls.terminal_lock:
                cls.terminal_sessions[sid] = {
                    "id": sid,
                    "fd": master_fd,
                    "proc": proc,
                    "meta": meta,
                    "created_at": now,
                    "last_active": now,
                }
            return sid, meta
        except Exception:
            if slave_fd is not None:
                try:
                    os.close(slave_fd)
                except Exception:
                    pass
            if master_fd is not None:
                try:
                    os.close(master_fd)
                except Exception:
                    pass
            if proc is not None:
                try:
                    if proc.poll() is None:
                        proc.terminate()
                except Exception:
                    pass
            raise

    @classmethod
    def _terminal_read_session(cls, sid: str, max_bytes: int = 131072):
        sid = str(sid or "").strip()
        if not sid:
            raise ValueError("缺少 session_id")
        with cls.terminal_lock:
            cls._terminal_cleanup_locked()
            sess = cls.terminal_sessions.get(sid)
            if not sess:
                raise ValueError("终端会话不存在或已结束")
            fd = int(sess.get("fd"))
            proc = sess.get("proc")
            sess["last_active"] = time.time()

        chunks = []
        total = 0
        limit = max(1024, min(int(max_bytes), 512 * 1024))
        while total < limit:
            try:
                data = os.read(fd, min(8192, limit - total))
            except BlockingIOError:
                break
            except OSError:
                break
            if not data:
                break
            chunks.append(data)
            total += len(data)

        out = b"".join(chunks).decode("utf-8", errors="replace")
        exit_code = proc.poll() if proc is not None else 0
        alive = exit_code is None
        return {"output": out, "alive": bool(alive), "exit_code": exit_code}

    @classmethod
    def _terminal_write_session(cls, sid: str, data: str):
        sid = str(sid or "").strip()
        if not sid:
            raise ValueError("缺少 session_id")
        text = str(data or "")
        if not text:
            return {"ok": True, "written": 0}
        with cls.terminal_lock:
            cls._terminal_cleanup_locked()
            sess = cls.terminal_sessions.get(sid)
            if not sess:
                raise ValueError("终端会话不存在或已结束")
            fd = int(sess.get("fd"))
            proc = sess.get("proc")
            if proc is not None and proc.poll() is not None:
                raise ValueError("终端会话已结束")
            sess["last_active"] = time.time()

        payload = text.encode("utf-8", errors="ignore")
        written = 0
        while written < len(payload):
            n = os.write(fd, payload[written:])
            if n <= 0:
                break
            written += int(n)
        return {"ok": True, "written": written}

    @classmethod
    def _terminal_resize_session(cls, sid: str, cols, rows):
        sid = str(sid or "").strip()
        if not sid:
            raise ValueError("缺少 session_id")
        with cls.terminal_lock:
            cls._terminal_cleanup_locked()
            sess = cls.terminal_sessions.get(sid)
            if not sess:
                raise ValueError("终端会话不存在或已结束")
            fd = int(sess.get("fd"))
            sess["last_active"] = time.time()
        cls._terminal_set_winsize(fd, cols, rows)
        c, r = cls._terminal_normalize_size(cols, rows)
        return {"ok": True, "cols": c, "rows": r}

    @classmethod
    def _terminal_close_session(cls, sid: str):
        sid = str(sid or "").strip()
        if not sid:
            raise ValueError("缺少 session_id")
        with cls.terminal_lock:
            existed = cls._terminal_close_session_locked(sid)
        return {"ok": True, "closed": bool(existed)}

    @classmethod
    def _schedule_restart(cls):
        with cls.control_lock:
            if cls.restart_queued:
                return False
            cls.restart_queued = True

        def _worker():
            try:
                time.sleep(0.3)
                subprocess.run(
                    ["systemctl", "restart", "storage-http-link-web"],
                    check=False,
                )
            finally:
                with cls.control_lock:
                    cls.restart_queued = False

        threading.Thread(target=_worker, daemon=True).start()
        return True

    @classmethod
    def _upgrade_supported(cls) -> tuple[bool, str]:
        if os.name != "posix":
            return False, "当前仅支持 Linux 自动更新"
        if not shutil.which("systemctl"):
            return False, "当前环境未检测到 systemctl，暂不支持自动更新"
        try:
            if os.geteuid() != 0:
                return False, "当前服务无 root 权限，无法执行 install.sh"
        except Exception:
            return False, "无法确认当前权限，暂不支持自动更新"
        return True, ""

    @classmethod
    def _upgrade_status_payload(cls) -> dict:
        status = _read_upgrade_status(_APP_ROOT_DIR)
        ok, reason = cls._upgrade_supported()
        with cls.upgrade_lock:
            running = bool(cls.upgrade_running)
        stale_running = bool(status.get("running")) and (not running)
        status["running"] = bool(running)
        if running:
            status["state"] = "running"
        elif stale_running and str(status.get("state", "")) == "running":
            status["state"] = "unknown"
            status["message"] = "Update task triggered a service restart; please verify current version manually."
            status["finished_at"] = _utc_now_iso()
            _write_upgrade_status(status, _APP_ROOT_DIR)
        status["supported"] = bool(ok)
        status["support_reason"] = str(reason or "")
        status["current_version"] = APP_VERSION_TEXT
        try:
            status["repo"] = _normalize_upgrade_repo(
                status.get("repo"), DEFAULT_UPGRADE_GITHUB_REPO
            )
        except Exception:
            status["repo"] = DEFAULT_UPGRADE_GITHUB_REPO
        status["branch"] = _normalize_upgrade_branch(
            status.get("branch"), DEFAULT_UPGRADE_BRANCH
        )
        return status

    @classmethod
    def _upgrade_branch_version_payload(cls, branch_raw) -> dict:
        status = cls._upgrade_status_payload()
        repo = DEFAULT_UPGRADE_GITHUB_REPO
        branch = _normalize_upgrade_branch(
            branch_raw if branch_raw is not None else status.get("branch"),
            DEFAULT_UPGRADE_BRANCH,
        )
        payload = {
            "ok": True,
            "repo": repo,
            "branch": branch,
            "current_version": APP_VERSION_TEXT,
            "current_branch": APP_BRANCH,
            "available_version": "",
            "release_url": "",
            "source": "",
            "checked_at": _utc_now_iso(),
            "error": "",
        }
        try:
            if branch == "nightly":
                try:
                    info = _local_branch_version_payload(repo, "nightly")
                    payload["source"] = "nightly-local-file"
                except Exception:
                    info = _github_branch_version_payload(repo, "nightly")
                    payload["source"] = "nightly-branch-head"
                payload["available_version"] = str(info.get("version_text") or "")
                payload["release_url"] = str(info.get("html_url") or "")
            else:
                release = _github_release_payload(repo, "")
                payload["available_version"] = _to_version_text(
                    str(release.get("tag_name") or "").strip()
                )
                payload["release_url"] = str(release.get("html_url") or "").strip()
                payload["source"] = "main-latest-release"
        except Exception as exc:
            payload["ok"] = False
            payload["error"] = str(exc)
        return payload

    @classmethod
    def _schedule_upgrade(cls, branch_raw):
        ok, reason = cls._upgrade_supported()
        if not ok:
            status = _write_upgrade_status(
                {
                    "supported": False,
                    "running": False,
                    "state": "error",
                    "message": "Auto-update unavailable",
                    "error": str(reason or "当前环境不支持"),
                    "branch": _normalize_upgrade_branch(branch_raw, DEFAULT_UPGRADE_BRANCH),
                },
                _APP_ROOT_DIR,
            )
            status["support_reason"] = str(reason or "")
            return False, status
        repo = DEFAULT_UPGRADE_GITHUB_REPO
        branch = _normalize_upgrade_branch(branch_raw, DEFAULT_UPGRADE_BRANCH)
        tag = ""
        with cls.upgrade_lock:
            if cls.upgrade_running:
                status = _read_upgrade_status(_APP_ROOT_DIR)
                status["support_reason"] = ""
                return False, status
            cls.upgrade_running = True
            status = _write_upgrade_status(
                {
                    "supported": True,
                    "running": True,
                    "state": "running",
                    "repo": repo,
                    "branch": branch,
                    "requested_tag": tag,
                    "target_tag": "",
                    "release_url": "",
                    "message": f"升级任务已启动，正在拉取 {branch} 信息",
                    "error": "",
                    "started_at": _utc_now_iso(),
                    "finished_at": "",
                },
                _APP_ROOT_DIR,
            )

        def _worker():
            temp_dir = None
            try:
                if branch == "nightly":
                    release = _github_branch_payload(repo, "nightly")
                else:
                    release = _github_release_payload(repo, "")
                target_tag = str(release.get("tag_name") or "").strip()
                tarball_url = str(release.get("tarball_url") or "").strip()
                release_url = str(release.get("html_url") or "").strip()
                if not target_tag:
                    target_tag = tag or "latest"
                if not tarball_url:
                    raise RuntimeError("Release 缺少 tarball 下载地址")

                status_now = _read_upgrade_status(_APP_ROOT_DIR)
                status_now.update(
                    {
                        "running": True,
                        "state": "running",
                        "repo": repo,
                        "branch": branch,
                        "requested_tag": tag,
                        "target_tag": target_tag,
                        "release_url": release_url,
                        "message": f"已获取 {branch} 版本 {target_tag}，开始下载",
                        "error": "",
                    }
                )
                _write_upgrade_status(status_now, _APP_ROOT_DIR)

                temp_dir = Path(tempfile.mkdtemp(prefix="afterclaw-upgrade-"))
                archive_path = temp_dir / "release.tar.gz"
                _http_download_file(
                    tarball_url,
                    archive_path,
                    timeout=UPGRADE_HTTP_TIMEOUT,
                    headers={
                        "Accept": "application/octet-stream",
                        "User-Agent": "afterclaw-updater/1.0",
                    },
                )

                src_root = temp_dir / "src"
                src_root.mkdir(parents=True, exist_ok=True)
                with tarfile.open(archive_path, "r:gz") as tf:
                    tf.extractall(path=src_root)
                children = [p for p in src_root.iterdir() if p.is_dir()]
                if not children:
                    raise RuntimeError("解压失败：未发现源码目录")
                pkg_dir = children[0]
                install_script = pkg_dir / "install.sh"
                if not install_script.exists():
                    raise RuntimeError("升级包缺少 install.sh")

                status_now = _read_upgrade_status(_APP_ROOT_DIR)
                status_now.update(
                    {
                        "running": True,
                        "state": "running",
                        "message": f"已下载 {target_tag}（{branch}），执行安装脚本中",
                        "error": "",
                    }
                )
                _write_upgrade_status(status_now, _APP_ROOT_DIR)

                run_env = os.environ.copy()
                run_env["APP_ROOT"] = str(_APP_ROOT_DIR)
                cfg = load_app_config(_APP_ROOT_DIR)
                web_port = _normalize_web_port(
                    (cfg or {}).get("web_port"), DEFAULT_WEB_PORT
                )
                run_env["WEB_PORT"] = str(web_port)
                run_env.setdefault("STORAGE_ROOT", str(DEFAULT_STORAGE_ROOT))
                run_env.setdefault("PUBLIC_HOST", str(DEFAULT_PUBLIC_HOST))
                run_env.setdefault("PUBLIC_SCHEME", str(DEFAULT_PUBLIC_SCHEME))
                proc = subprocess.run(
                    ["bash", "install.sh"],
                    cwd=str(pkg_dir),
                    env=run_env,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if proc.returncode != 0:
                    err = (proc.stderr or proc.stdout or "").strip()
                    if err:
                        err = err[-1200:]
                    raise RuntimeError(err or f"install.sh 执行失败（exit {proc.returncode}）")

                _write_upgrade_status(
                    {
                        "supported": True,
                        "running": False,
                        "state": "success",
                        "repo": repo,
                        "branch": branch,
                        "requested_tag": tag,
                        "target_tag": target_tag,
                        "release_url": release_url,
                        "message": f"Update completed: {target_tag}",
                        "error": "",
                        "finished_at": _utc_now_iso(),
                    },
                    _APP_ROOT_DIR,
                )
            except Exception as exc:
                status_now = _read_upgrade_status(_APP_ROOT_DIR)
                status_now.update(
                    {
                        "running": False,
                        "state": "error",
                        "repo": repo,
                        "branch": branch,
                        "requested_tag": tag,
                        "message": "自动更新失败",
                        "error": str(exc),
                        "finished_at": _utc_now_iso(),
                    }
                )
                _write_upgrade_status(status_now, _APP_ROOT_DIR)
            finally:
                with cls.upgrade_lock:
                    cls.upgrade_running = False
                if temp_dir is not None:
                    try:
                        shutil.rmtree(temp_dir, ignore_errors=True)
                    except Exception:
                        pass

        threading.Thread(target=_worker, daemon=True).start()
        status["support_reason"] = ""
        return True, status

    def _list_child_directories(self, rel_dir: str, root_dir: Path | None = None):
        root = Path(root_dir or self._http_root_dir())
        target_dir = ensure_under_root(root, root / rel_dir)
        if not target_dir.exists() or not target_dir.is_dir():
            raise FileNotFoundError("Directory does not exist")

        children = []
        for entry in target_dir.iterdir():
            if not entry.is_dir():
                continue
            if self._is_hidden_system_name(entry.name):
                continue
            rel = entry.relative_to(root).as_posix()
            children.append(rel)
        return sorted(children)

    def _directory_stats(self, rel_dir: str, root_dir: Path | None = None):
        root = Path(root_dir or self._http_root_dir())
        target_dir = ensure_under_root(root, root / rel_dir)
        if not target_dir.exists() or not target_dir.is_dir():
            raise FileNotFoundError("Directory does not exist")

        total_files = 0
        total_dirs = 0
        total_size = 0

        for root, dirnames, filenames in os.walk(target_dir):
            visible_dirs = [d for d in dirnames if not self._is_hidden_system_name(d)]
            dirnames[:] = visible_dirs
            visible_files = [f for f in filenames if not self._is_hidden_system_name(f)]
            total_dirs += len(visible_dirs)
            total_files += len(visible_files)
            for name in visible_files:
                fp = Path(root) / name
                try:
                    total_size += int(fp.stat().st_size)
                except Exception:
                    continue

        return {
            "total_files": int(total_files),
            "total_dirs": int(total_dirs),
            "total_size": int(total_size),
            "total_size_human": self._human_size(int(total_size)),
        }

    def _http_path_scan(self, path_raw: str):
        candidate = self._http_root_from_raw(path_raw, require_exists=False)
        info = {
            "path": str(candidate),
            "exists": False,
            "is_dir": False,
            "can_read": False,
            "can_exec": False,
            "can_write": False,
            "can_list": False,
            "child_dir_count": 0,
            "child_file_count": 0,
            "sample_dirs": [],
            "truncated": False,
            "ok": False,
            "error": "",
        }
        try:
            exists = candidate.exists()
        except Exception:
            exists = False
        info["exists"] = bool(exists)
        if not exists:
            info["error"] = "路径不存在"
            return info

        try:
            is_dir = candidate.is_dir()
        except Exception:
            is_dir = False
        info["is_dir"] = bool(is_dir)
        if not is_dir:
            info["error"] = "目标不是目录"
            return info

        info["can_read"] = bool(os.access(candidate, os.R_OK))
        info["can_exec"] = bool(os.access(candidate, os.X_OK))
        info["can_write"] = bool(os.access(candidate, os.W_OK))

        try:
            st = os.statvfs(str(candidate))
            total = int(st.f_frsize * st.f_blocks)
            avail = int(st.f_frsize * st.f_bavail)
            info["fs_total"] = total
            info["fs_avail"] = avail
            info["fs_total_human"] = self._human_size(total)
            info["fs_avail_human"] = self._human_size(avail)
        except Exception:
            pass

        max_entries = 600
        try:
            dir_count = 0
            file_count = 0
            sample_dirs = []
            for idx, entry in enumerate(candidate.iterdir()):
                if idx >= max_entries:
                    info["truncated"] = True
                    break
                if self._is_hidden_system_name(entry.name):
                    continue
                try:
                    is_entry_dir = entry.is_dir()
                except Exception:
                    continue
                if is_entry_dir:
                    dir_count += 1
                    if len(sample_dirs) < 20:
                        sample_dirs.append(entry.name)
                else:
                    file_count += 1
            info["child_dir_count"] = int(dir_count)
            info["child_file_count"] = int(file_count)
            info["sample_dirs"] = sample_dirs
            info["can_list"] = True
        except PermissionError:
            info["error"] = "权限不足：无法列出目录内容（需要目录 r+x）"
            return info
        except Exception as exc:
            info["error"] = f"Scan failed: {exc}"
            return info

        info["ok"] = bool(info["can_read"] and info["can_exec"] and info["can_list"])
        if not info["ok"] and not info["error"]:
            info["error"] = "权限不足：至少需要目录 r+x"
        return info

    @classmethod
    def _detect_default_iface(cls):
        try:
            with open("/proc/net/route", "r", encoding="utf-8") as f:
                lines = f.readlines()[1:]
            for line in lines:
                cols = line.strip().split()
                if len(cols) < 3:
                    continue
                # Destination 00000000 means default route.
                if cols[1] == "00000000":
                    return cols[0]
        except Exception:
            return None
        return None

    @classmethod
    def _read_iface_bytes(cls, iface: str) -> tuple[int, int]:
        if not iface:
            return 0, 0
        try:
            with open("/proc/net/dev", "r", encoding="utf-8") as f:
                lines = f.readlines()
            for line in lines:
                if f"{iface}:" not in line:
                    continue
                left, right = line.split(":", 1)
                if left.strip() != iface:
                    continue
                parts = right.split()
                if len(parts) < 10:
                    return 0, 0
                rx_bytes = int(parts[0])
                tx_bytes = int(parts[8])
                return rx_bytes, tx_bytes
        except Exception:
            return 0, 0
        return 0, 0

    @classmethod
    def _count_established_conn_1288(cls) -> int:
        target_port = f"{ACTIVE_WEB_PORT:04X}"

        def count_file(path: str) -> int:
            total = 0
            try:
                with open(path, "r", encoding="utf-8") as f:
                    for line in f.readlines()[1:]:
                        cols = line.strip().split()
                        if len(cols) < 4:
                            continue
                        local = cols[1]
                        state = cols[3]
                        if state != "01":  # ESTABLISHED
                            continue
                        if ":" not in local:
                            continue
                        local_port = local.split(":", 1)[1]
                        if local_port.upper() == target_port:
                            total += 1
            except Exception:
                return total
            return total

        return count_file("/proc/net/tcp") + count_file("/proc/net/tcp6")

    @classmethod
    def _speed_snapshot(cls):
        with cls.speed_lock:
            now = time.time()
            iface = cls.speed_state.get("iface")
            if not iface:
                iface = cls._detect_default_iface()
                cls.speed_state["iface"] = iface
            rx_now, tx_now = cls._read_iface_bytes(iface)

            last_ts = float(cls.speed_state.get("last_ts", 0.0) or 0.0)
            last_rx = int(cls.speed_state.get("last_rx", 0) or 0)
            last_tx = int(cls.speed_state.get("last_tx", 0) or 0)
            rx_mibps = float(cls.speed_state.get("rx_mibps", 0.0) or 0.0)
            rx_mbps = float(cls.speed_state.get("rx_mbps", 0.0) or 0.0)
            tx_mibps = float(cls.speed_state.get("tx_mibps", 0.0) or 0.0)
            tx_mbps = float(cls.speed_state.get("tx_mbps", 0.0) or 0.0)

            if last_ts > 0 and now > last_ts:
                delta_sec = now - last_ts
                if rx_now >= last_rx:
                    delta_rx = rx_now - last_rx
                    rx_mibps = delta_rx / 1024.0 / 1024.0 / delta_sec
                    rx_mbps = delta_rx * 8.0 / 1024.0 / 1024.0 / delta_sec
                if tx_now >= last_tx:
                    delta_tx = tx_now - last_tx
                    tx_mibps = delta_tx / 1024.0 / 1024.0 / delta_sec
                    tx_mbps = delta_tx * 8.0 / 1024.0 / 1024.0 / delta_sec

            cls.speed_state["last_ts"] = now
            cls.speed_state["last_rx"] = rx_now
            cls.speed_state["last_tx"] = tx_now
            cls.speed_state["rx_mibps"] = rx_mibps
            cls.speed_state["rx_mbps"] = rx_mbps
            cls.speed_state["tx_mibps"] = tx_mibps
            cls.speed_state["tx_mbps"] = tx_mbps

            return {
                "iface": iface or "",
                "rx_mibps": rx_mibps,
                "rx_mbps": rx_mbps,
                "tx_mibps": tx_mibps,
                "tx_mbps": tx_mbps,
                "active_conn_1288": cls._count_established_conn_1288(),
            }

    @classmethod
    def _module_enabled(
        cls, module_key: str, default: bool = True, app_cfg: dict | None = None
    ) -> bool:
        cfg = app_cfg if isinstance(app_cfg, dict) else load_app_config(_APP_ROOT_DIR)
        mods = (cfg or {}).get("modules") or {}
        key = str(module_key or "").strip().lower()
        if not key:
            return bool(default)
        if key == "http":
            if "http" in mods:
                return bool(mods.get("http"))
            # 兼容历史键名
            if "http_monitor" in mods:
                return bool(mods.get("http_monitor"))
            return bool(default)
        if key in mods:
            return bool(mods.get(key))
        return bool(default)

    @classmethod
    def _http_module_enabled(cls, app_cfg: dict | None = None) -> bool:
        return cls._module_enabled("http", True, app_cfg)

    @classmethod
    def _qbt_module_enabled(cls, app_cfg: dict | None = None) -> bool:
        return cls._module_enabled("qbt", True, app_cfg)

    @classmethod
    def _ddns_module_enabled(cls, app_cfg: dict | None = None) -> bool:
        return cls._module_enabled("ddns", True, app_cfg)

    @classmethod
    def _shareclip_module_enabled(cls, app_cfg: dict | None = None) -> bool:
        return cls._module_enabled("shareclip", True, app_cfg)

    @classmethod
    def _downloads_effective_enabled(cls) -> bool:
        return bool(cls.downloads_enabled and cls._http_module_enabled())

    @classmethod
    def _cut_http_downloads_once(cls) -> int:
        with cls.http_cut_lock:
            cls.http_cut_epoch = int(cls.http_cut_epoch) + 1
            return cls.http_cut_epoch

    def _build_http_url(self, relative_file_path: str) -> str:
        encoded_path = quote(relative_file_path, safe="/")
        return f"{DEFAULT_PUBLIC_SCHEME}://{DEFAULT_PUBLIC_HOST}/http-files/{encoded_path}"

    def _send_file(self, file_path: Path, send_body: bool = True, http_root: Path | None = None):
        if not file_path.exists() or not file_path.is_file():
            self._error("File does not exist", status=HTTPStatus.NOT_FOUND)
            return
        try:
            content_type, _ = mimetypes.guess_type(str(file_path))
            content_type = content_type or "application/octet-stream"
            file_size = file_path.stat().st_size
            filename = quote(file_path.name)
            start = 0
            end = file_size - 1
            status_code = HTTPStatus.OK
            range_header = (self.headers.get("Range") or "").strip()
            if range_header.startswith("bytes="):
                try:
                    range_spec = range_header[6:].strip()
                    # 仅支持单个 range
                    if "," in range_spec:
                        self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                        self.send_header("Content-Range", f"bytes */{file_size}")
                        self.send_header("Content-Length", "0")
                        self.send_header("Accept-Ranges", "bytes")
                        self.end_headers()
                        return

                    if range_spec.startswith("-"):
                        suffix = int(range_spec[1:] or "0")
                        if suffix <= 0:
                            self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                            self.send_header("Content-Range", f"bytes */{file_size}")
                            self.send_header("Content-Length", "0")
                            self.send_header("Accept-Ranges", "bytes")
                            self.end_headers()
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
                    self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                    self.send_header("Content-Range", f"bytes */{file_size}")
                    self.send_header("Content-Length", "0")
                    self.send_header("Accept-Ranges", "bytes")
                    self.end_headers()
                    return

                if start < 0 or start >= file_size:
                    self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                    self.send_header("Content-Range", f"bytes */{file_size}")
                    self.send_header("Content-Length", "0")
                    self.send_header("Accept-Ranges", "bytes")
                    self.end_headers()
                    return
                end = min(end, file_size - 1)
                if end < start:
                    self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                    self.send_header("Content-Range", f"bytes */{file_size}")
                    self.send_header("Content-Length", "0")
                    self.send_header("Accept-Ranges", "bytes")
                    self.end_headers()
                    return
                status_code = HTTPStatus.PARTIAL_CONTENT

            content_len = end - start + 1
            self.send_response(status_code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(content_len))
            self.send_header(
                "Content-Disposition", f"inline; filename*=UTF-8''{filename}"
            )
            self.send_header("Accept-Ranges", "bytes")
            if status_code == HTTPStatus.PARTIAL_CONTENT:
                self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
            self.end_headers()
            if send_body:
                root_for_rel = Path(http_root or self._http_root_dir())
                try:
                    rel_path = file_path.relative_to(root_for_rel).as_posix()
                except Exception:
                    rel_path = file_path.name
                client_ip = self._client_ip()
                user_agent = str(self.headers.get("User-Agent", "") or "")
                referer = str(self.headers.get("Referer", "") or "")
                source_ip_pools = self._http_source_ip_pools()
                source = self._infer_transfer_source(
                    rel_path,
                    file_path.name,
                    user_agent,
                    referer,
                    client_ip,
                    source_ip_pools,
                )
                transfer_id = f"{threading.get_ident()}-{int(time.time() * 1000)}"
                with self.http_cut_lock:
                    cut_epoch = int(self.http_cut_epoch)
                with self.transfers_lock:
                    self.active_transfers[transfer_id] = {
                        "source": source,
                        "client_ip": client_ip,
                        "relative_path": rel_path,
                        "filename": file_path.name,
                        "user_agent": user_agent[:256],
                        "referer": referer[:512],
                        "sent_bytes": 0,
                        "total_bytes": content_len,
                        "file_total_bytes": file_size,
                        "is_partial": bool(status_code == HTTPStatus.PARTIAL_CONTENT),
                        "range_start": start,
                        "range_end": end,
                        "started_at": time.time(),
                        "done": False,
                        "ended_at": 0.0,
                        "cut_epoch": cut_epoch,
                    }
                with file_path.open("rb") as f:
                    f.seek(start)
                    remaining = content_len
                    try:
                        while remaining > 0:
                            with self.http_cut_lock:
                                now_epoch = int(self.http_cut_epoch)
                            if now_epoch != cut_epoch:
                                # 仅中断 /http-files 数据流，不影响控制页/API。
                                self.close_connection = True
                                break
                            chunk = f.read(1024 * 1024)
                            if not chunk:
                                break
                            if len(chunk) > remaining:
                                chunk = chunk[:remaining]
                            self.wfile.write(chunk)
                            sent_now = len(chunk)
                            remaining -= sent_now
                            with self.transfers_lock:
                                tr = self.active_transfers.get(transfer_id)
                                if tr is not None:
                                    tr["sent_bytes"] = int(tr.get("sent_bytes", 0)) + sent_now
                    finally:
                        with self.transfers_lock:
                            tr = self.active_transfers.get(transfer_id)
                            if tr is not None:
                                tr["done"] = True
                                tr["ended_at"] = time.time()
        except Exception as exc:
            self._error(f"File read failed: {exc}", status=HTTPStatus.INTERNAL_SERVER_ERROR)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/pub/embed.css":
            if not self._require_lan():
                return
            css_bytes = build_pub_embed_css().encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/css; charset=utf-8")
            self.send_header("Cache-Control", "private, max-age=120")
            self.send_header("Content-Length", str(len(css_bytes)))
            self.end_headers()
            self.wfile.write(css_bytes)
            return
        if parsed.path == "/dashboard.css":
            if not self._require_lan():
                return
            p = _APP_ROOT_DIR / "web" / "dashboard.css"
            if not p.is_file():
                self._error("Resource not found", status=HTTPStatus.NOT_FOUND)
                return
            data = p.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/css; charset=utf-8")
            self.send_header("Cache-Control", "private, max-age=60")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if parsed.path == "/i18n.js":
            if not self._require_lan():
                return
            if self._send_static_asset(
                "i18n.js", send_body=True, cache_control="no-store, max-age=0"
            ):
                return
            self._error("Resource not found", status=HTTPStatus.NOT_FOUND)
            return
        if parsed.path.startswith("/locales/"):
            if not self._require_lan():
                return
            if self._send_static_asset(
                parsed.path.lstrip("/"),
                send_body=True,
                cache_control="no-store, max-age=0",
            ):
                return
            self._error("Resource not found", status=HTTPStatus.NOT_FOUND)
            return
        if parsed.path.startswith(f"/{THEME_ASSETS_DIR_NAME}/"):
            if not self._require_lan():
                return
            if self._send_static_asset(parsed.path.lstrip("/"), send_body=True):
                return
            self._error("Resource not found", status=HTTPStatus.NOT_FOUND)
            return
        if parsed.path.startswith("/vendor/"):
            if not self._require_lan():
                return
            if self._send_static_asset(parsed.path.lstrip("/"), send_body=True):
                return
            self._error("Resource not found", status=HTTPStatus.NOT_FOUND)
            return
        if parsed.path == "/config":
            if not self._require_lan():
                return
            self._send_html(build_config_html())
            return
        if parsed.path == "/terminal":
            if not self._require_lan():
                return
            self._send_html(build_terminal_html())
            return
        if parsed.path == "/process-net":
            if not self._require_lan():
                return
            if self._send_static_asset(
                "process-net.html",
                send_body=True,
                cache_control="no-store, max-age=0",
            ):
                return
            self._error("Resource not found", status=HTTPStatus.NOT_FOUND)
            return
        if self._dispatch_ddnsgo_proxy(parsed, "GET", True):
            return
        if self._dispatch_shareclip_flask(parsed, "GET", True):
            return
        
        # Try module routes
        if self._dispatch_module_route(parsed, "GET"):
            return
        
        if parsed.path == "/":
            if not self._require_lan():
                return
            self._send_html(build_frontend_html())
            return

        if parsed.path == "/ddns":
            if not self._require_lan():
                return
            if not self._ddns_module_enabled():
                self._error("DDNS module is disabled", status=HTTPStatus.FORBIDDEN)
                return
            self._send_html(build_ddns_settings_html())
            return

        if parsed.path.startswith("/http-files/"):
            if not self._downloads_effective_enabled():
                self._error("Public upload is disabled", status=HTTPStatus.FORBIDDEN)
                return
            if not self._require_http_access():
                return
            try:
                http_root = self._http_root_dir()
                rel_file = unquote(parsed.path[len("/http-files/") :]).lstrip("/")
                rel_file = safe_relative_path(rel_file)
                target_file = ensure_under_root(http_root, http_root / rel_file)
                self._send_file(target_file, send_body=True, http_root=http_root)
                return
            except ValueError as exc:
                self._error(str(exc), status=HTTPStatus.FORBIDDEN)
                return
            except Exception as exc:
                self._error(f"Download failed: {exc}", status=HTTPStatus.INTERNAL_SERVER_ERROR)
                return

        if parsed.path == "/api/base":
            if not self._require_lan():
                return
            app_cfg = load_app_config(_APP_ROOT_DIR)
            http_cfg = (app_cfg or {}).get("http_service") or {}
            http_root = self._http_root_dir(app_cfg)
            self._send_json(
                {
                    "storage_root": str(http_root),
                    "http_root_dir": str(http_root),
                    "web_port": ACTIVE_WEB_PORT,
                    "public_base_url": f"{DEFAULT_PUBLIC_SCHEME}://{DEFAULT_PUBLIC_HOST}",
                    "downloads_enabled": self._downloads_effective_enabled(),
                    "default_http_dir": _normalize_rel_dir_setting(
                        http_cfg.get("default_dir", ".")
                    ),
                    "terminal": _build_terminal_launch_meta(app_cfg),
                    "ui_theme": _ui_theme_payload(app_cfg, _APP_ROOT_DIR),
                }
            )
            return

        if parsed.path == "/api/speed":
            if not self._require_lan():
                return
            self._send_json(self._speed_snapshot())
            return

        if parsed.path == "/api/process-net":
            if not self._require_lan():
                return
            source_ip_pools = self._http_source_ip_pools()
            data = self.process_detail_sampler.detailed_snapshot(
                lambda row: self._infer_process_source_by_row(row, source_ip_pools)
            ) or {}
            payload = {
                **(data if isinstance(data, dict) else {}),
                "current_version": APP_VERSION_TEXT,
                "app_version": APP_VERSION,
            }
            self._send_json(payload, cors=True)
            return

        if parsed.path == "/api/transfers":
            if not self._require_lan():
                return
            self._send_json(self._transfer_snapshot())
            return

        if parsed.path == "/api/control/status":
            if not self._require_lan():
                return
            query = parse_qs(parsed.query)
            client = str(query.get("client", [""])[0] or "").strip().lower()
            self._send_json(self._control_status_payload(client))
            return

        if parsed.path == "/api/app-config":
            if not self._require_lan():
                return
            self._send_json({"config": load_app_config(_APP_ROOT_DIR)})
            return

        if parsed.path == "/api/qbt/discover":
            if not self._require_lan():
                return
            query = parse_qs(parsed.query)
            client = str(query.get("client", [""])[0] or "").strip().lower()
            app_cfg = load_app_config(_APP_ROOT_DIR)
            if client in {"qbittorrent", "deluge", "transmission", "rtorrent"}:
                if not isinstance(app_cfg, dict):
                    app_cfg = {}
                qbt_cfg = app_cfg.get("qbt")
                if not isinstance(qbt_cfg, dict):
                    qbt_cfg = {}
                qbt_cfg = dict(qbt_cfg)
                qbt_cfg["client"] = client
                app_cfg["qbt"] = qbt_cfg
            self._send_json(self._qbt_discover_options(app_cfg))
            return

        if parsed.path == "/api/qbt/client-upgrade/status":
            if not self._require_lan():
                return
            self._send_json(self._qbt_upgrade_snapshot())
            return

        if parsed.path == "/api/upgrade/status":
            if not self._require_lan():
                return
            self._send_json(self._upgrade_status_payload())
            return

        if parsed.path == "/api/upgrade/check-version":
            if not self._require_lan():
                return
            query = parse_qs(parsed.query)
            branch_raw = str(query.get("branch", [""])[0] or "").strip()
            self._send_json(self._upgrade_branch_version_payload(branch_raw))
            return

        if parsed.path == "/api/ddns/config":
            if not self._require_lan():
                return
            if not self._ddns_module_enabled():
                self._error("DDNS module is disabled", status=HTTPStatus.FORBIDDEN)
                return
            cfg = ddns.load_config(_APP_ROOT_DIR)
            st = ddns.status_for_api(_APP_ROOT_DIR)
            self._send_json(
                {
                    "config": cfg,
                    "status": st,
                    "config_path": str(ddns.config_path(_APP_ROOT_DIR)),
                }
            )
            return

        if parsed.path == "/api/http/path-scan":
            if not self._require_lan():
                return
            query = parse_qs(parsed.query)
            path_raw = str(query.get("path", [""])[0] or "").strip()
            if not path_raw:
                self._error("Missing path parameter", status=HTTPStatus.BAD_REQUEST)
                return
            try:
                info = self._http_path_scan(path_raw)
                self._send_json(info)
                return
            except Exception as exc:
                self._error(f"Path scan failed: {exc}", status=HTTPStatus.INTERNAL_SERVER_ERROR)
                return

        if parsed.path == "/api/directories":
            if not self._require_lan():
                return
            try:
                query = parse_qs(parsed.query)
                root_raw = query.get("root_dir", [None])[0]
                http_root = (
                    self._http_root_from_raw(root_raw, require_exists=True)
                    if root_raw is not None
                    else self._http_root_dir()
                )
                stats_raw = str(query.get("stats", ["1"])[0] or "1").strip().lower()
                with_stats = stats_raw not in {"0", "false", "no", "off"}
                rel_dir = safe_relative_path(query.get("dir", ["."])[0])
                directories = self._list_child_directories(rel_dir, root_dir=http_root)
                stats = self._directory_stats(rel_dir, root_dir=http_root) if with_stats else {}
                self._send_json(
                    {
                        "directories": directories,
                        "current_dir": rel_dir,
                        "stats": stats,
                        "http_root_dir": str(http_root),
                    }
                )
                return
            except ValueError as exc:
                self._error(str(exc), status=HTTPStatus.FORBIDDEN)
                return
            except FileNotFoundError as exc:
                self._error(str(exc), status=HTTPStatus.NOT_FOUND)
                return
            except Exception as exc:
                self._error(f"Directory query failed: {exc}", status=HTTPStatus.INTERNAL_SERVER_ERROR)
                return

        if parsed.path == "/api/files":
            if not self._require_lan():
                return
            try:
                query = parse_qs(parsed.query)
                root_raw = query.get("root_dir", [None])[0]
                http_root = (
                    self._http_root_from_raw(root_raw, require_exists=True)
                    if root_raw is not None
                    else self._http_root_dir()
                )
                rel_dir = safe_relative_path(query.get("dir", ["."])[0])
                target_dir = ensure_under_root(http_root, http_root / rel_dir)
                if not target_dir.exists() or not target_dir.is_dir():
                    self._error("Directory does not exist", status=HTTPStatus.NOT_FOUND)
                    return

                items = []
                for root, dirnames, files in os.walk(target_dir):
                    dirnames[:] = [d for d in dirnames if not self._is_hidden_system_name(d)]
                    for filename in files:
                        if self._is_hidden_system_name(filename):
                            continue
                        full_path = Path(root) / filename
                        rel_file = full_path.relative_to(http_root).as_posix()
                        file_size = full_path.stat().st_size
                        items.append(
                            {
                                "relative_path": rel_file,
                                "size": file_size,
                                "size_human": human_size(file_size),
                                "http_url": self._build_http_url(rel_file),
                            }
                        )
                items.sort(key=lambda x: x["relative_path"])
                self._send_json({"items": items, "http_root_dir": str(http_root)})
                return
            except ValueError as exc:
                self._error(str(exc), status=HTTPStatus.FORBIDDEN)
                return
            except Exception as exc:
                self._error(f"Scan failed: {exc}", status=HTTPStatus.INTERNAL_SERVER_ERROR)
                return

        self._error("Resource not found", status=HTTPStatus.NOT_FOUND)

    def do_HEAD(self):
        parsed = urlparse(self.path)
        if parsed.path == "/pub/embed.css":
            if not self._require_lan():
                return
            css_bytes = build_pub_embed_css().encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/css; charset=utf-8")
            self.send_header("Cache-Control", "private, max-age=120")
            self.send_header("Content-Length", str(len(css_bytes)))
            self.end_headers()
            return
        if parsed.path == "/dashboard.css":
            if not self._require_lan():
                return
            p = _APP_ROOT_DIR / "web" / "dashboard.css"
            if not p.is_file():
                self._error("Resource not found", status=HTTPStatus.NOT_FOUND)
                return
            n = p.stat().st_size
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/css; charset=utf-8")
            self.send_header("Cache-Control", "private, max-age=60")
            self.send_header("Content-Length", str(n))
            self.end_headers()
            return
        if parsed.path == "/i18n.js":
            if not self._require_lan():
                return
            if self._send_static_asset(
                "i18n.js", send_body=False, cache_control="no-store, max-age=0"
            ):
                return
            self._error("Resource not found", status=HTTPStatus.NOT_FOUND)
            return
        if parsed.path.startswith("/locales/"):
            if not self._require_lan():
                return
            if self._send_static_asset(
                parsed.path.lstrip("/"),
                send_body=False,
                cache_control="no-store, max-age=0",
            ):
                return
            self._error("Resource not found", status=HTTPStatus.NOT_FOUND)
            return
        if parsed.path.startswith(f"/{THEME_ASSETS_DIR_NAME}/"):
            if not self._require_lan():
                return
            if self._send_static_asset(parsed.path.lstrip("/"), send_body=False):
                return
            self._error("Resource not found", status=HTTPStatus.NOT_FOUND)
            return
        if parsed.path.startswith("/vendor/"):
            if not self._require_lan():
                return
            if self._send_static_asset(parsed.path.lstrip("/"), send_body=False):
                return
            self._error("Resource not found", status=HTTPStatus.NOT_FOUND)
            return
        if parsed.path == "/terminal":
            if not self._require_lan():
                return
            payload = build_terminal_html().encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            return
        if parsed.path == "/process-net":
            if not self._require_lan():
                return
            if self._send_static_asset(
                "process-net.html",
                send_body=False,
                cache_control="no-store, max-age=0",
            ):
                return
            self._error("Resource not found", status=HTTPStatus.NOT_FOUND)
            return
        if self._dispatch_ddnsgo_proxy(parsed, "HEAD", True):
            return
        if self._dispatch_shareclip_flask(parsed, "HEAD", True):
            return
        if parsed.path.startswith("/http-files/"):
            if not self._downloads_effective_enabled():
                self._error("Public upload is disabled", status=HTTPStatus.FORBIDDEN)
                return
            if not self._require_http_access():
                return
            try:
                http_root = self._http_root_dir()
                rel_file = unquote(parsed.path[len("/http-files/") :]).lstrip("/")
                rel_file = safe_relative_path(rel_file)
                target_file = ensure_under_root(http_root, http_root / rel_file)
                self._send_file(target_file, send_body=False, http_root=http_root)
                return
            except ValueError as exc:
                self._error(str(exc), status=HTTPStatus.FORBIDDEN)
                return
            except Exception as exc:
                self._error(f"Download failed: {exc}", status=HTTPStatus.INTERNAL_SERVER_ERROR)
                return

        self._error("Resource not found", status=HTTPStatus.NOT_FOUND)

    def do_POST(self):
        parsed = urlparse(self.path)

        if self._dispatch_ddnsgo_proxy(parsed, "POST", True):
            return
        if self._dispatch_shareclip_flask(parsed, "POST", True):
            return
        
        # Try module routes
        if self._dispatch_module_route(parsed, "POST"):
            return

        if parsed.path == "/api/terminal/start":
            if not self._require_lan():
                return
            body = self._parse_body()
            try:
                sid, meta = self._terminal_start_session(
                    body.get("cols", 120), body.get("rows", 30)
                )
            except Exception as exc:
                self._error(f"Terminal connection failed: {exc}", status=HTTPStatus.BAD_REQUEST)
                return
            self._send_json({"ok": True, "session_id": sid, "meta": meta})
            return

        if parsed.path == "/api/terminal/read":
            if not self._require_lan():
                return
            body = self._parse_body()
            try:
                data = self._terminal_read_session(
                    body.get("session_id"), body.get("max_bytes", 131072)
                )
            except Exception as exc:
                self._error(f"Read failed: {exc}", status=HTTPStatus.BAD_REQUEST)
                return
            self._send_json(data)
            return

        if parsed.path == "/api/terminal/write":
            if not self._require_lan():
                return
            body = self._parse_body()
            try:
                data = self._terminal_write_session(
                    body.get("session_id"), body.get("data", "")
                )
            except Exception as exc:
                self._error(f"Write failed: {exc}", status=HTTPStatus.BAD_REQUEST)
                return
            self._send_json(data)
            return

        if parsed.path == "/api/terminal/resize":
            if not self._require_lan():
                return
            body = self._parse_body()
            try:
                data = self._terminal_resize_session(
                    body.get("session_id"), body.get("cols", 120), body.get("rows", 30)
                )
            except Exception as exc:
                self._error(f"Resize failed: {exc}", status=HTTPStatus.BAD_REQUEST)
                return
            self._send_json(data)
            return

        if parsed.path == "/api/terminal/close":
            if not self._require_lan():
                return
            body = self._parse_body()
            try:
                data = self._terminal_close_session(body.get("session_id"))
            except Exception as exc:
                self._error(f"Close failed: {exc}", status=HTTPStatus.BAD_REQUEST)
                return
            self._send_json(data)
            return

        if parsed.path == "/api/terminal/key-file":
            if not self._require_lan():
                return
            body = self._parse_body()
            if not isinstance(body, dict):
                self._error("Request body must be a JSON object", status=HTTPStatus.BAD_REQUEST)
                return
            try:
                file_name, size = _save_terminal_key_file(
                    body.get("file_name", ""),
                    body.get("content_b64", ""),
                    _APP_ROOT_DIR,
                )
            except ValueError as exc:
                self._error(str(exc), status=HTTPStatus.BAD_REQUEST)
                return
            except Exception as exc:
                self._error(f"Key file save failed: {exc}", status=HTTPStatus.INTERNAL_SERVER_ERROR)
                return
            current = load_app_config(_APP_ROOT_DIR)
            term_cfg = current.setdefault("terminal", {})
            term_cfg["auth_mode"] = "key"
            term_cfg["key_file"] = file_name
            saved = save_app_config(current, _APP_ROOT_DIR)
            self._send_json(
                {
                    "ok": True,
                    "file_name": file_name,
                    "size": int(size),
                    "config": saved,
                    "terminal": _build_terminal_launch_meta(saved),
                }
            )
            return

        if parsed.path == "/api/subtitles/upload":
            if not self._require_lan():
                return
            body = self._parse_body()
            if not isinstance(body, dict):
                self._error("Request body must be a JSON object", status=HTTPStatus.BAD_REQUEST)
                return
            try:
                rel_dir = safe_relative_path(str(body.get("dir", ".") or "."))
                cfg = load_app_config(_APP_ROOT_DIR)
                http_cfg = (cfg or {}).get("http_service") if isinstance(cfg, dict) else {}
                perm = (
                    (http_cfg or {}).get("subtitle_permissions", {})
                    if isinstance(http_cfg, dict)
                    else {}
                )
                result = subtitle_uploads.handle_upload_payload(
                    self._http_root_dir(), rel_dir, body, perm
                )
            except FileNotFoundError as exc:
                self._error(str(exc), status=HTTPStatus.NOT_FOUND)
                return
            except ValueError as exc:
                self._error(str(exc), status=HTTPStatus.BAD_REQUEST)
                return
            except Exception as exc:
                self._error(f"Subtitle upload failed: {exc}", status=HTTPStatus.INTERNAL_SERVER_ERROR)
                return
            self._send_json(result)
            return

        if parsed.path == "/api/ui/theme-background":
            if not self._require_lan():
                return
            self._error(
                "Custom background upload is disabled. Use built-in presets only.",
                status=HTTPStatus.FORBIDDEN,
            )
            return

        if parsed.path == "/api/http/source-ip-pools/sync":
            if not self._require_lan():
                return
            body = self._parse_body()
            if body is None:
                body = {}
            if not isinstance(body, dict):
                self._error("Request body must be a JSON object", status=HTTPStatus.BAD_REQUEST)
                return
            current = load_app_config(_APP_ROOT_DIR)
            http_cfg = current.setdefault("http_service", {})
            raw_source = (
                body.get("source")
                if "source" in body
                else http_cfg.get("source_ip_pool_source")
            )
            source = _normalize_source_ip_pool_source(raw_source)
            merge_raw = body.get("merge", True)
            if isinstance(merge_raw, str):
                lv = merge_raw.strip().lower()
                if lv in {"0", "false", "no", "off", "replace"}:
                    merge_mode = False
                else:
                    merge_mode = True
            else:
                merge_mode = bool(merge_raw)
            try:
                pulled = _fetch_source_ip_pools_from_source(source)
            except ValueError as exc:
                self._error(str(exc), status=HTTPStatus.BAD_REQUEST)
                return
            except Exception as exc:
                self._error(f"Source sync failed: {exc}", status=HTTPStatus.BAD_GATEWAY)
                return
            local_pools = _normalize_source_ip_pools(http_cfg.get("source_ip_pools"))
            remote_pools = _normalize_source_ip_pools((pulled or {}).get("pools"))
            pools = (
                _merge_source_ip_pools(local_pools, remote_pools)
                if merge_mode
                else remote_pools
            )
            http_cfg["source_ip_pools"] = pools
            http_cfg["source_ip_pool_source"] = source
            saved = save_app_config(current, _APP_ROOT_DIR)
            counts = {k: len((pools or {}).get(k, [])) for k in SOURCE_POOL_KEYS}
            remote_counts = {
                k: len((remote_pools or {}).get(k, [])) for k in SOURCE_POOL_KEYS
            }
            local_counts = {
                k: len((local_pools or {}).get(k, [])) for k in SOURCE_POOL_KEYS
            }
            self._send_json(
                {
                    "ok": True,
                    "source": source,
                    "mode": "merge" if merge_mode else "replace",
                    "counts": counts,
                    "remote_counts": remote_counts,
                    "local_counts": local_counts,
                    "files_used": (pulled or {}).get("files_used", []),
                    "meta": (pulled or {}).get("meta", {}),
                    "pools": pools,
                    "config": saved,
                }
            )
            return

        if parsed.path == "/api/app-config":
            if not self._require_lan():
                return
            body = self._parse_body()
            if not isinstance(body, dict):
                self._error("Request body must be a JSON object", status=HTTPStatus.BAD_REQUEST)
                return
            current = load_app_config(_APP_ROOT_DIR)
            prev_qbt_enabled = self._qbt_module_enabled(current)
            prev_ddns_enabled = self._ddns_module_enabled(current)
            prev_shareclip_enabled = self._shareclip_module_enabled(current)
            prev_http_enabled = self._http_module_enabled(current)
            if "web_port" in body:
                web_port_raw = body.get("web_port")
                try:
                    web_port_new = int(web_port_raw)
                except Exception:
                    self._error("Service port must be an integer in 1-65535", status=HTTPStatus.BAD_REQUEST)
                    return
                if web_port_new <= 0 or web_port_new > 65535:
                    self._error("Service port must be an integer in 1-65535", status=HTTPStatus.BAD_REQUEST)
                    return
                current["web_port"] = web_port_new
            if isinstance(body.get("modules"), dict):
                mods = current.setdefault("modules", {})
                incoming = body["modules"]
                for k in ("qbt", "ddns", "shareclip", "http"):
                    if k in body["modules"]:
                        mods[k] = bool(body["modules"].get(k))
                # 兼容旧键名
                if "http" not in incoming and "http_monitor" in incoming:
                    mods["http"] = bool(incoming.get("http_monitor"))
            if isinstance(body.get("qbt"), dict):
                qbt_cfg = current.setdefault("qbt", {})
                if "monitor_enabled" in body["qbt"]:
                    qbt_cfg["monitor_enabled"] = bool(body["qbt"].get("monitor_enabled"))
                if "client" in body["qbt"]:
                    client = str(body["qbt"].get("client", "") or "").strip().lower()
                    if client in {"qbittorrent", "deluge", "transmission", "rtorrent"}:
                        qbt_cfg["client"] = client
                if "service_unit" in body["qbt"]:
                    qbt_cfg["service_unit"] = str(
                        body["qbt"].get("service_unit", "") or ""
                    ).strip()
                if "docker_container" in body["qbt"]:
                    qbt_cfg["docker_container"] = str(
                        body["qbt"].get("docker_container", "") or ""
                    ).strip()
                if "api_url" in body["qbt"]:
                    qbt_cfg["api_url"] = str(body["qbt"].get("api_url", "") or "").strip()
                if "homepage_clients_enabled" in body["qbt"] and isinstance(body["qbt"]["homepage_clients_enabled"], dict):
                    en = qbt_cfg.get("homepage_clients_enabled")
                    if not isinstance(en, dict):
                        en = {}
                    for k in ("qbittorrent", "deluge", "transmission", "rtorrent"):
                        if k in body["qbt"]["homepage_clients_enabled"]:
                            en[k] = bool(body["qbt"]["homepage_clients_enabled"].get(k))
                    qbt_cfg["homepage_clients_enabled"] = en
                if "homepage_clients_order" in body["qbt"] and isinstance(body["qbt"]["homepage_clients_order"], list):
                    out = []
                    seen = set()
                    for item in body["qbt"]["homepage_clients_order"]:
                        x = str(item or "").strip().lower()
                        if x in {"qbittorrent", "deluge", "transmission", "rtorrent"} and x not in seen:
                            seen.add(x)
                            out.append(x)
                    for x in ("qbittorrent", "deluge", "transmission", "rtorrent"):
                        if x not in seen:
                            out.append(x)
                    qbt_cfg["homepage_clients_order"] = out
            http_path_cfg_changed = False
            if isinstance(body.get("http_service"), dict):
                http_cfg = current.setdefault("http_service", {})
                incoming_http = body["http_service"]
                if "root_dir" in incoming_http:
                    root_dir = self._http_root_from_raw(
                        incoming_http.get("root_dir"), app_cfg=current, require_exists=True
                    )
                    http_cfg["root_dir"] = str(root_dir)
                    http_path_cfg_changed = True
                if "default_dir" in incoming_http:
                    http_cfg["default_dir"] = _normalize_rel_dir_setting(
                        incoming_http.get("default_dir")
                    )
                    http_path_cfg_changed = True
                if "source_ip_pools" in incoming_http:
                    http_cfg["source_ip_pools"] = _normalize_source_ip_pools(
                        incoming_http.get("source_ip_pools")
                    )
                if "source_ip_pool_source" in incoming_http:
                    http_cfg["source_ip_pool_source"] = _normalize_source_ip_pool_source(
                        incoming_http.get("source_ip_pool_source")
                    )
                if "transfer_recent_ttl_sec" in incoming_http:
                    http_cfg["transfer_recent_ttl_sec"] = _normalize_transfer_recent_ttl(
                        incoming_http.get("transfer_recent_ttl_sec"),
                        http_cfg.get(
                            "transfer_recent_ttl_sec", DEFAULT_TRANSFER_RECENT_TTL_SEC
                        ),
                    )
            if http_path_cfg_changed:
                http_cfg = current.setdefault("http_service", {})
                root_for_check = self._http_root_from_raw(
                    http_cfg.get("root_dir"), app_cfg=current, require_exists=True
                )
                rel_default = _normalize_rel_dir_setting(http_cfg.get("default_dir", "."))
                default_target = ensure_under_root(root_for_check, root_for_check / rel_default)
                if not default_target.exists() or not default_target.is_dir():
                    self._error(
                        f"DefaultDirectory does not exist或不可访问: {default_target}",
                        status=HTTPStatus.BAD_REQUEST,
                    )
                    return
            if isinstance(body.get("terminal"), dict):
                term_cfg = current.setdefault("terminal", {})
                incoming_term = body["terminal"]
                if "enabled" in incoming_term:
                    term_cfg["enabled"] = bool(incoming_term.get("enabled"))
                if "host" in incoming_term:
                    host = str(incoming_term.get("host", "") or "").strip()
                    if host:
                        term_cfg["host"] = host
                if "port" in incoming_term:
                    term_cfg["port"] = _normalize_ssh_port(incoming_term.get("port"), 22)
                if "user" in incoming_term:
                    user = str(incoming_term.get("user", "") or "").strip()
                    if user:
                        term_cfg["user"] = user
                if "auth_mode" in incoming_term:
                    mode = str(incoming_term.get("auth_mode", "") or "").strip().lower()
                    if mode in ("key", "password"):
                        term_cfg["auth_mode"] = mode
                if "key_path" in incoming_term:
                    term_cfg["key_path"] = str(
                        incoming_term.get("key_path", "") or ""
                    ).strip()
                if "key_file" in incoming_term:
                    term_cfg["key_file"] = _normalize_terminal_key_file_name(
                        incoming_term.get("key_file", "")
                    )
            if isinstance(body.get("ui"), dict):
                ui_cfg = current.setdefault("ui", {})
                incoming_ui = body["ui"]
                if "hero_preset" in incoming_ui:
                    ui_cfg["hero_preset"] = _normalize_ui_hero_preset(
                        incoming_ui.get("hero_preset")
                    )
                ui_cfg["hero_custom_bg_file"] = ""
            if isinstance(body.get("netdisk_sources"), dict):
                nd_cfg = current.setdefault("netdisk_sources", {})
                incoming_nd = body["netdisk_sources"]
                for k in ("baidu", "ali", "guangya", "dropbox", "mega", "onedrive", "gdrive"):
                    if k in incoming_nd:
                        nd_cfg[k] = bool(incoming_nd.get(k))
            saved = save_app_config(current, _APP_ROOT_DIR)
            saved_http_cfg = (saved.get("http_service") or {}) if isinstance(saved, dict) else {}
            AppHandler.transfer_recent_ttl_sec = _normalize_transfer_recent_ttl(
                saved_http_cfg.get(
                    "transfer_recent_ttl_sec", DEFAULT_TRANSFER_RECENT_TTL_SEC
                ),
                DEFAULT_TRANSFER_RECENT_TTL_SEC,
            )
            web_port_restart_required = (
                _normalize_web_port(saved.get("web_port"), DEFAULT_WEB_PORT)
                != ACTIVE_WEB_PORT
            )
            new_qbt_enabled = self._qbt_module_enabled(saved)
            new_ddns_enabled = self._ddns_module_enabled(saved)
            new_shareclip_enabled = self._shareclip_module_enabled(saved)
            new_http_enabled = self._http_module_enabled(saved)
            disconnect_triggered = False
            module_actions = []
            if prev_http_enabled and not new_http_enabled:
                with self.control_lock:
                    self.downloads_enabled = False
                    AppHandler.downloads_enabled = False
                # 仅中断本程序 /http-files 上传Connect，不Restart Service。
                self._cut_http_downloads_once()
                disconnect_triggered = True
                module_actions.append(
                    {
                        "module": "http",
                        "action": "disable-downloads",
                        "ok": True,
                        "message": "HTTP module is disabled，已禁用上传并中断本程序上传Connect",
                    }
                )
            elif not new_http_enabled:
                with self.control_lock:
                    self.downloads_enabled = False
                    AppHandler.downloads_enabled = False
                module_actions.append(
                    {
                        "module": "http",
                        "action": "disable-downloads",
                        "ok": True,
                        "message": "HTTP module is disabled，上传保持禁用",
                    }
                )

            if prev_qbt_enabled and not new_qbt_enabled:
                qbt_info = self._resolve_existing_unit(self.qbt_candidates)
                if qbt_info.get("load_state") == "not-found":
                    qbt_info = (
                        self._discover_unit_by_keywords(
                            self._bt_service_keywords(
                                ((saved or {}).get("qbt") or {}).get("client", "qbittorrent")
                            )
                        )
                        or qbt_info
                    )
                qbt_unit = str((qbt_info or {}).get("unit", "") or "").strip()
                qbt_active = str((qbt_info or {}).get("active_state", "") or "").strip() == "active"
                if qbt_unit and qbt_active:
                    ok, msg = self._service_action(qbt_unit, "stop")
                    module_actions.append(
                        {
                            "module": "qbt",
                            "action": "stop-service",
                            "unit": qbt_unit,
                            "ok": bool(ok),
                            "message": "qB 服务已停止"
                            if ok
                            else f"停止 qB 服务失败：{msg}",
                        }
                    )
                elif qbt_unit:
                    module_actions.append(
                        {
                            "module": "qbt",
                            "action": "stop-service",
                            "unit": qbt_unit,
                            "ok": True,
                            "message": "qB 服务已是停止状态",
                        }
                    )
                else:
                    module_actions.append(
                        {
                            "module": "qbt",
                            "action": "stop-service",
                            "ok": False,
                            "message": "未找到 qB 服务",
                        }
                    )
                self._qbt_reset_stats_cache()

            if prev_ddns_enabled and not new_ddns_enabled:
                if ddns.config_path(_APP_ROOT_DIR).exists():
                    ok, msg = ddns.service_action(_APP_ROOT_DIR, "stop")
                    module_actions.append(
                        {
                            "module": "ddns",
                            "action": "stop-builtin",
                            "ok": bool(ok),
                            "message": "内置 DDNS 已停止"
                            if ok
                            else f"停止内置 DDNS failed: {msg}",
                        }
                    )
                ext_ddns = self._resolve_existing_unit(self.ddns_candidates)
                if ext_ddns.get("load_state") == "not-found":
                    ext_ddns = (
                        self._discover_unit_by_keywords(
                            ["ddns", "duckdns", "cloudflare", "dnspod", "ddns-go"]
                        )
                        or ext_ddns
                    )
                ext_unit = str((ext_ddns or {}).get("unit", "") or "").strip()
                ext_active = str((ext_ddns or {}).get("active_state", "") or "").strip() == "active"
                if ext_unit and ext_active:
                    ok, msg = self._service_action(ext_unit, "stop")
                    module_actions.append(
                        {
                            "module": "ddns",
                            "action": "stop-service",
                            "unit": ext_unit,
                            "ok": bool(ok),
                            "message": "DDNS 服务已停止"
                            if ok
                            else f"停止 DDNS 服务失败：{msg}",
                        }
                    )

            if prev_shareclip_enabled and not new_shareclip_enabled:
                module_actions.append(
                    {
                        "module": "shareclip",
                        "action": "disable-routes",
                        "ok": True,
                        "message": "ShareClip 接口已关闭",
                    }
                )
                shareclip_svc = self._discover_unit_by_keywords(
                    ["shareclip", "file-control-shareclip"]
                )
                shareclip_unit = str((shareclip_svc or {}).get("unit", "") or "").strip()
                shareclip_active = (
                    str((shareclip_svc or {}).get("active_state", "") or "").strip() == "active"
                )
                if shareclip_unit and shareclip_active:
                    ok, msg = self._service_action(shareclip_unit, "stop")
                    module_actions.append(
                        {
                            "module": "shareclip",
                            "action": "stop-service",
                            "unit": shareclip_unit,
                            "ok": bool(ok),
                            "message": "ShareClip 服务已停止"
                            if ok
                            else f"停止 ShareClip 服务失败：{msg}",
                        }
                    )
            self._send_json(
                {
                    "ok": True,
                    "config": saved,
                    "running_web_port": ACTIVE_WEB_PORT,
                    "web_port_restart_required": bool(web_port_restart_required),
                    "http_disconnect_triggered": bool(disconnect_triggered),
                    "module_actions": module_actions,
                    "ui_theme": _ui_theme_payload(saved, _APP_ROOT_DIR),
                }
            )
            return

        if parsed.path == "/api/control/downloads":
            if not self._require_lan():
                return
            body = self._parse_body()
            enabled = bool(body.get("enabled", True))
            if enabled and not self._http_module_enabled():
                self._error("HTTP module is disabled; cannot enable upload", status=HTTPStatus.BAD_REQUEST)
                return
            with self.control_lock:
                self.downloads_enabled = enabled
                AppHandler.downloads_enabled = enabled
            self._send_json({"downloads_enabled": self._downloads_effective_enabled()})
            return

        if parsed.path == "/api/control/http-access":
            if not self._require_lan():
                return
            body = self._parse_body()
            action = str((body or {}).get("action", "") or "").strip().lower()
            cfg = load_app_config(_APP_ROOT_DIR)
            policy = http_access.normalize_policy((cfg or {}).get("http_access"))
            if action == "open_public":
                try:
                    duration = int((body or {}).get("duration_sec", 0))
                except (TypeError, ValueError):
                    duration = 0
                if duration <= 0 or duration > 7 * 24 * 3600:
                    self._error(
                        "duration_sec must be between 1 and 604800",
                        status=HTTPStatus.BAD_REQUEST,
                    )
                    return
                policy["mode"] = "public"
                policy["public_until"] = time.time() + duration
            elif action == "open_public_persistent":
                policy["mode"] = "public"
                policy["public_until"] = None
            elif action == "close":
                policy["mode"] = "lan_only"
                policy["public_until"] = None
            else:
                self._error(
                    "Unknown action; expected 'open_public', 'open_public_persistent', or 'close'",
                    status=HTTPStatus.BAD_REQUEST,
                )
                return
            cfg["http_access"] = http_access.normalize_policy(policy)
            save_app_config(cfg, _APP_ROOT_DIR)
            self._send_json(self._http_access_status(cfg))
            return

        if parsed.path == "/api/control/restart":
            if not self._require_lan():
                return
            queued = self._schedule_restart()
            self._send_json({"queued": queued})
            return

        if parsed.path == "/api/upgrade/run":
            if not self._require_lan():
                return
            body = self._parse_body()
            if body is None:
                body = {}
            if not isinstance(body, dict):
                self._error("Request body must be a JSON object", status=HTTPStatus.BAD_REQUEST)
                return
            try:
                queued, status = self._schedule_upgrade(body.get("branch"))
            except ValueError as exc:
                self._error(str(exc), status=HTTPStatus.BAD_REQUEST)
                return
            except Exception as exc:
                self._error(f"Failed to start update: {exc}", status=HTTPStatus.INTERNAL_SERVER_ERROR)
                return
            self._send_json({"queued": bool(queued), "status": status})
            return

        if parsed.path == "/api/qbt/client-upgrade/check":
            if not self._require_lan():
                return
            body = self._parse_body()
            if not isinstance(body, dict):
                body = {}
            try:
                app_cfg = load_app_config(_APP_ROOT_DIR)
                info = self._qbt_upgrade_check(
                    app_cfg,
                    client_hint=str(body.get("client", "") or ""),
                    container_hint=str(body.get("docker_container", "") or ""),
                )
                info["running"] = False
                info["state"] = "checked"
                info["checked_at"] = _utc_now_iso()
                self._set_qbt_upgrade_status(**info)
                self._send_json(self._qbt_upgrade_snapshot())
            except Exception as exc:
                rec = self._set_qbt_upgrade_status(
                    running=False,
                    state="error",
                    message="Update check failed",
                    error=str(exc),
                )
                self._send_json(rec)
            return

        if parsed.path == "/api/qbt/client-upgrade/run":
            if not self._require_lan():
                return
            body = self._parse_body()
            if not isinstance(body, dict):
                body = {}
            app_cfg = load_app_config(_APP_ROOT_DIR)
            rec = self._qbt_upgrade_run(
                app_cfg,
                client_hint=str(body.get("client", "") or ""),
                container_hint=str(body.get("docker_container", "") or ""),
            )
            self._send_json(rec)
            return

        if parsed.path == "/api/ddns/config":
            if not self._require_lan():
                return
            if not self._ddns_module_enabled():
                self._error("DDNS module is disabled", status=HTTPStatus.FORBIDDEN)
                return
            body = self._parse_body()
            ok, msg = ddns.apply_config_from_body(_APP_ROOT_DIR, body)
            if not ok:
                self._error(msg, status=HTTPStatus.BAD_REQUEST)
                return
            self._send_json(
                {
                    "ok": True,
                    "config": ddns.load_config(_APP_ROOT_DIR),
                    "status": ddns.status_for_api(_APP_ROOT_DIR),
                }
            )
            return

        if parsed.path == "/api/ddns/run":
            if not self._require_lan():
                return
            if not self._ddns_module_enabled():
                self._error("DDNS module is disabled", status=HTTPStatus.FORBIDDEN)
                return
            ok, msg, ip = ddns.do_update_once(_APP_ROOT_DIR)
            if not ok:
                self._error(msg, status=HTTPStatus.BAD_REQUEST)
                return
            self._send_json({"ok": True, "message": msg, "ip": ip})
            return

        if parsed.path == "/api/clean/preview":
            if not self._require_lan():
                return
            body = self._parse_body()
            rel = str(body.get("dir", ".") or ".")
            target = str(body.get("target", "both") or "both")
            if target not in ("both", "files", "dirs"):
                self._error("target must be both / files / dirs", status=HTTPStatus.BAD_REQUEST)
                return
            try:
                plan = build_rename_plan(
                    self.storage_root,
                    rel,
                    target=target,
                    recursive=bool(body.get("recursive", False)),
                    remove_substrings=str(body.get("remove_substrings", "") or ""),
                    strip_cjk=bool(body.get("strip_cjk", False)),
                    move_season_before_year=bool(
                        body.get("move_season_before_year")
                        or body.get("reorder_season", False)
                    ),
                )
            except FileNotFoundError as e:
                self._error(str(e), status=HTTPStatus.NOT_FOUND)
                return
            except ValueError as e:
                self._error(str(e), status=HTTPStatus.BAD_REQUEST)
                return
            except Exception as exc:
                self._error(f"Preview failed: {exc}", status=HTTPStatus.INTERNAL_SERVER_ERROR)
                return
            self._send_json(
                {
                    "moves": [
                        {
                            "old_rel": x.old_rel,
                            "new_rel": x.new_rel,
                            "kind": x.kind,
                            "skip": x.skip,
                            "error": x.error,
                        }
                        for x in plan
                    ]
                }
            )
            return

        if parsed.path == "/api/subtitle-align/preview":
            if not self._require_lan():
                return
            body = self._parse_body()
            try:
                rel = str((body or {}).get("dir", ".") or ".")
                recursive = bool((body or {}).get("recursive", False))
                plan = subtitle_align.build_alignment_plan(
                    self.storage_root,
                    rel,
                    recursive=recursive,
                )
            except FileNotFoundError as exc:
                self._error(str(exc), status=HTTPStatus.NOT_FOUND)
                return
            except ValueError as exc:
                self._error(str(exc), status=HTTPStatus.BAD_REQUEST)
                return
            except Exception as exc:
                self._error(f"Subtitle align preview failed: {exc}", status=HTTPStatus.INTERNAL_SERVER_ERROR)
                return
            self._send_json({"moves": subtitle_align.simplify_plan(plan)})
            return

        if parsed.path == "/api/clean/apply":
            if not self._require_lan():
                return
            body = self._parse_body()
            moves = body.get("moves")
            if not isinstance(moves, list) or not moves:
                self._error("moves must be a non-empty array", status=HTTPStatus.BAD_REQUEST)
                return
            try:
                results = apply_rename_plan(self.storage_root, moves)
            except Exception as exc:
                self._error(f"Execution failed: {exc}", status=HTTPStatus.INTERNAL_SERVER_ERROR)
                return
            self._send_json({"results": results})
            return

        if parsed.path == "/api/subtitle-align/apply":
            if not self._require_lan():
                return
            body = self._parse_body()
            moves = (body or {}).get("moves")
            if not isinstance(moves, list) or not moves:
                self._error("moves must be a non-empty array", status=HTTPStatus.BAD_REQUEST)
                return
            try:
                results = apply_rename_plan(self.storage_root, moves)
            except Exception as exc:
                self._error(f"Subtitle align apply failed: {exc}", status=HTTPStatus.INTERNAL_SERVER_ERROR)
                return
            self._send_json({"results": results})
            return

        if parsed.path == "/api/control/service":
            if not self._require_lan():
                return
            body = self._parse_body()
            service = str(body.get("service", "")).strip().lower()
            action = str(body.get("action", "")).strip().lower()
            client_override = str(body.get("client", "") or "").strip().lower()
            if service not in {"qbt", "ddns", "self"}:
                self._error("Invalid service parameter", status=HTTPStatus.BAD_REQUEST)
                return
            if action not in {"start", "stop", "restart", "quit"}:
                self._error("Invalid action parameter", status=HTTPStatus.BAD_REQUEST)
                return
            if service == "qbt" and (not self._qbt_module_enabled()) and action != "stop":
                self._error(
                    "qB module is disabled，请在 Config 中开启后再操作",
                    status=HTTPStatus.FORBIDDEN,
                )
                return
            if service == "ddns" and (not self._ddns_module_enabled()) and action != "stop":
                self._error(
                    "DDNS module is disabled，请在 Config 中开启后再操作",
                    status=HTTPStatus.FORBIDDEN,
                )
                return

            if service == "self":
                if action != "restart":
                    self._error("self only supports restart", status=HTTPStatus.BAD_REQUEST)
                    return
                queued = self._schedule_restart()
                self._send_json({"queued": queued})
                return

            if action == "quit" and service != "qbt":
                self._error("Only qbt supports quit", status=HTTPStatus.BAD_REQUEST)
                return

            if service == "qbt" and action == "quit":
                ok, msg = self._qbt_shutdown_once()
                if not ok:
                    self._error(f"quit failed: {msg}", status=HTTPStatus.INTERNAL_SERVER_ERROR)
                    return
                self._qbt_reset_stats_cache()
                self._send_json(self._control_status_payload(client_override))
                return

            if service == "ddns" and ddns.config_path(
                _APP_ROOT_DIR
            ).exists():
                ok, msg = ddns.service_action(_APP_ROOT_DIR, action)
                if not ok:
                    self._error(
                        f"{action} failed: {msg}", status=HTTPStatus.INTERNAL_SERVER_ERROR
                    )
                    return
                self._send_json(self._control_status_payload(client_override))
                return

            status_now = self._control_status_payload(client_override)
            target_info = status_now.get(service) or {}
            unit = str(target_info.get("unit", "")).strip()
            if not unit or target_info.get("load_state") == "not-found":
                self._error(f"{service} service not found", status=HTTPStatus.NOT_FOUND)
                return

            ok, msg = self._service_action(unit, action)
            if not ok:
                self._error(f"{action} failed: {msg}", status=HTTPStatus.INTERNAL_SERVER_ERROR)
                return
            if service == "qbt":
                self._qbt_reset_stats_cache()
            self._send_json(self._control_status_payload(client_override))
            return

        if parsed.path == "/api/qbt/fix-monitor":
            if not self._require_lan():
                return
            if not self._qbt_module_enabled():
                self._error(
                    "qB module is disabled，请在 Config 中开启后再操作",
                    status=HTTPStatus.FORBIDDEN,
                )
                return
            ok, msg, detail = self._qbt_fix_monitor_config()
            if not ok:
                self._error(f"qB fix failed: {msg}", status=HTTPStatus.INTERNAL_SERVER_ERROR)
                return
            status_payload = self._control_status_payload()
            self._send_json(
                {
                    "ok": True,
                    "message": msg,
                    "detail": detail,
                    "status": status_payload.get("qbt", {}),
                }
            )
            return

        if parsed.path == "/api/qbt/optimize-config":
            if not self._require_lan():
                return
            if not self._qbt_module_enabled():
                self._error(
                    "qB module is disabled，请在 Config 中开启后再操作",
                    status=HTTPStatus.FORBIDDEN,
                )
                return
            body = self._parse_body()
            selected = (body.get("qbt") or {}) if isinstance(body, dict) else {}
            ok, msg, detail = self._qbt_optimize_config(selected if isinstance(selected, dict) else {})
            if not ok:
                self._error(f"qB optimize failed: {msg}", status=HTTPStatus.INTERNAL_SERVER_ERROR)
                return
            status_payload = self._control_status_payload()
            self._send_json(
                {
                    "ok": True,
                    "message": msg,
                    "detail": detail,
                    "status": status_payload.get("qbt", {}),
                }
            )
            return

        self._error("Resource not found", status=HTTPStatus.NOT_FOUND)

    def do_DELETE(self):
        parsed = urlparse(self.path)
        if self._dispatch_shareclip_flask(parsed, "DELETE", True):
            return
        self._error("Resource not found", status=HTTPStatus.NOT_FOUND)

    def log_message(self, fmt: str, *args):
        return


def main():
    global ACTIVE_WEB_PORT
    _migrate_legacy_state_once()
    startup_cfg = load_app_config(_APP_ROOT_DIR)
    ACTIVE_WEB_PORT = _normalize_web_port(
        (startup_cfg or {}).get("web_port"), DEFAULT_WEB_PORT
    )
    startup_http_cfg = (
        (startup_cfg or {}).get("http_service", {})
        if isinstance(startup_cfg, dict)
        else {}
    )
    AppHandler.transfer_recent_ttl_sec = _normalize_transfer_recent_ttl(
        startup_http_cfg.get("transfer_recent_ttl_sec", DEFAULT_TRANSFER_RECENT_TTL_SEC),
        DEFAULT_TRANSFER_RECENT_TTL_SEC,
    )
    AppHandler.storage_root = DEFAULT_STORAGE_ROOT
    AppHandler.storage_root.mkdir(parents=True, exist_ok=True)
    ddns.start_worker(_APP_ROOT_DIR)
    server = ThreadingHTTPServer(("0.0.0.0", ACTIVE_WEB_PORT), AppHandler)
    print(
        f"Web 服务已启动: http://0.0.0.0:{ACTIVE_WEB_PORT} "
        f"(storage={AppHandler.storage_root})"
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
