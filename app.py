#!/usr/bin/env python3
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
from fcc import __version__ as FCC_APP_VERSION
from fcc import __branch__ as FCC_APP_BRANCH
from ddns.web import load_ddns_settings_page
from naming.clean_names import apply_rename_plan, build_rename_plan

_CODE_DIR = Path(__file__).resolve().parent
_LEGACY_APP_ROOT_DIR = _CODE_DIR.parent
# 兼容旧版本：此前错误地把 app_root 指向了上级目录（如 /opt）。
_APP_ROOT_DIR = _CODE_DIR if (_CODE_DIR / "web").is_dir() else _LEGACY_APP_ROOT_DIR
os.environ.setdefault(
    "SHARECLIP_STORAGE_ROOT",
    str(_APP_ROOT_DIR / "shareclip" / "storage"),
)

_shareclip_app = None
_shareclip_import_lock = threading.Lock()


def get_shareclip_app():
    """惰性加载 ShareClip（Flask），与同进程中控服务共用，无需单独监听 8888。"""
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
    os.environ.get("PUBLIC_HOST", f"home.rxotc.cn:{DEFAULT_WEB_PORT}").strip()
    or f"home.rxotc.cn:{DEFAULT_WEB_PORT}"
)
DEFAULT_QBT_SERVICE = os.environ.get("QBT_SERVICE", "").strip()
DEFAULT_QBT_API_URL = (
    os.environ.get("QBT_API_URL", "http://127.0.0.1:8080").strip()
    or "http://127.0.0.1:8080"
)
DEFAULT_QBT_API_USERNAME = os.environ.get("QBT_API_USERNAME", "").strip()
DEFAULT_QBT_API_PASSWORD = os.environ.get("QBT_API_PASSWORD", "").strip()
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
    "custom",
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
    "baidu": "百度网盘",
    "guangya": "光鸭网盘",
    "aliyun": "阿里云盘",
}
SOURCE_POOL_KEY_ALIASES = {
    "baidu": "baidu",
    "百度": "baidu",
    "百度网盘": "baidu",
    "xpan": "baidu",
    "pan.baidu": "baidu",
    "netdisk": "baidu",
    "guangya": "guangya",
    "光鸭": "guangya",
    "光鸭网盘": "guangya",
    "aliyun": "aliyun",
    "alipan": "aliyun",
    "阿里": "aliyun",
    "阿里云": "aliyun",
    "阿里云盘": "aliyun",
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
APP_BRANCH = str(FCC_APP_BRANCH or "").strip() or "stable"


def _page_title_with_version(title: str) -> str:
    base = str(title or "").strip() or "AfterClaw"
    return f"{base} · {APP_VERSION_TEXT}"


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


def _default_upgrade_status() -> dict:
    return {
        "supported": bool(os.name == "posix"),
        "running": False,
        "state": "idle",
        "current_version": APP_VERSION_TEXT,
        "repo": DEFAULT_UPGRADE_GITHUB_REPO,
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
    custom_file = _normalize_theme_bg_file_name(ui.get("hero_custom_bg_file", ""))
    custom_url = ""
    if custom_file:
        try:
            assets_dir = theme_assets_dir(app_root).resolve()
            target = ensure_under_root(assets_dir, assets_dir / custom_file)
            if target.exists() and target.is_file():
                ver = int(target.stat().st_mtime)
                custom_url = f"/{THEME_ASSETS_DIR_NAME}/{quote(custom_file)}?v={ver}"
        except Exception:
            custom_url = ""
    if preset == "custom" and not custom_url:
        preset = "default"
    return {
        "hero_preset": preset,
        "hero_custom_bg_file": custom_file if custom_url else "",
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


def _github_release_payload(repo: str, tag: str = "", branch: str = "stable") -> dict:
    safe_repo = _normalize_upgrade_repo(repo, DEFAULT_UPGRADE_GITHUB_REPO)
    safe_tag = _normalize_upgrade_tag(tag)
    owner, name = safe_repo.split("/", 1)
    safe_branch = str(branch or "stable").strip().lower()
    if safe_branch not in ("stable", "nightly"):
        safe_branch = "stable"
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "afterclaw-updater/1.0"}
    if safe_tag:
        api_url = (
            f"https://api.github.com/repos/{quote(owner)}/{quote(name)}"
            f"/releases/tags/{quote(safe_tag)}"
        )
        try:
            data = _http_fetch_json(api_url, timeout=UPGRADE_HTTP_TIMEOUT, headers=headers)
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                raise ValueError(f"未找到发布版本：{safe_tag}") from exc
            raise RuntimeError(f"GitHub API 错误（HTTP {exc.code}）") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"连接 GitHub 失败：{exc}") from exc
        except Exception as exc:
            raise RuntimeError(f"读取 GitHub Release 失败：{exc}") from exc
        if not isinstance(data, dict):
            raise RuntimeError("GitHub Release 返回格式异常")
        return data
    if safe_branch == "nightly":
        api_url = (
            f"https://api.github.com/repos/{quote(owner)}/{quote(name)}"
            "/releases?per_page=30"
        )
        try:
            releases = _http_fetch_json(api_url, timeout=UPGRADE_HTTP_TIMEOUT, headers=headers)
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"GitHub API 错误（HTTP {exc.code}）") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"连接 GitHub 失败：{exc}") from exc
        except Exception as exc:
            raise RuntimeError(f"读取 GitHub Release 失败：{exc}") from exc
        if not isinstance(releases, list):
            raise RuntimeError("GitHub Release 返回格式异常")
        for rel in releases:
            tag_name = str(rel.get("tag_name") or "").lower()
            is_pre = bool(rel.get("prerelease"))
            if is_pre or "nightly" in tag_name:
                return rel
        raise ValueError("仓库暂无可用 nightly Release")
    api_url = (
        f"https://api.github.com/repos/{quote(owner)}/{quote(name)}"
        "/releases/latest"
    )
    try:
        data = _http_fetch_json(api_url, timeout=UPGRADE_HTTP_TIMEOUT, headers=headers)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise ValueError("仓库暂无可用 Release") from exc
        raise RuntimeError(f"GitHub API 错误（HTTP {exc.code}）") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"连接 GitHub 失败：{exc}") from exc
    except Exception as exc:
        raise RuntimeError(f"读取 GitHub Release 失败：{exc}") from exc
    if not isinstance(data, dict):
        raise RuntimeError("GitHub Release 返回格式异常")
    return data


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
            raise RuntimeError(f"GitHub 连接失败：{exc}") from exc
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
        raise ValueError("GitHub 源中未发现可识别的来源 IP 文件（需包含 baidu/guangya/aliyun 命名）")
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
        "密码模式不会保存密码，点击后在终端内手工输入。"
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
        raise ValueError("未配置 Terminal Host")
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
            raise ValueError("未配置 SSH key（可填 key_path，或配置目录 key 文件名）")
        if not key_target.exists() or not key_target.is_file():
            raise ValueError(f"SSH key 文件不存在: {key_target}")
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
        },
        "http_service": {
            "root_dir": str(DEFAULT_STORAGE_ROOT),
            "default_dir": ".",
            "source_ip_pools": _default_source_ip_pools(),
            "source_ip_pool_source": _default_source_ip_pool_source(),
        },
        "terminal": {
            "enabled": True,
            "host": os.environ.get("TERMINAL_SSH_HOST", "192.168.1.30").strip()
            or "192.168.1.30",
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
        if isinstance(qbt, dict) and "monitor_enabled" in qbt:
            base["qbt"]["monitor_enabled"] = bool(qbt.get("monitor_enabled"))
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
        elif "http_root_dir" in raw:
            base["http_service"]["root_dir"] = _normalize_abs_dir_setting(
                raw.get("http_root_dir"), str(DEFAULT_STORAGE_ROOT)
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
            if "hero_custom_bg_file" in ui:
                base["ui"]["hero_custom_bg_file"] = _normalize_theme_bg_file_name(
                    ui.get("hero_custom_bg_file")
                )
    if base["terminal"]["auth_mode"] not in ("key", "password"):
        base["terminal"]["auth_mode"] = "key"
    base["http_service"]["root_dir"] = _normalize_abs_dir_setting(
        base["http_service"].get("root_dir", str(DEFAULT_STORAGE_ROOT)),
        str(DEFAULT_STORAGE_ROOT),
    )
    base["http_service"]["default_dir"] = _normalize_rel_dir_setting(
        base["http_service"]["default_dir"]
    )
    base["http_service"]["source_ip_pools"] = _normalize_source_ip_pools(
        base["http_service"].get("source_ip_pools")
    )
    base["http_service"]["source_ip_pool_source"] = _normalize_source_ip_pool_source(
        base["http_service"].get("source_ip_pool_source")
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
    base["ui"]["hero_custom_bg_file"] = _normalize_theme_bg_file_name(
        (base.get("ui") or {}).get("hero_custom_bg_file", "")
    )
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
    """ShareClip 内嵌页：与中控台主题变量一致，随 data-theme 切换深浅色。"""
    return """/* ShareClip embed — 与中控台联动 data-theme */
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

    # 避免与中控台 /config 冲突：ShareClip 配置页改走 /clip-config 代理入口。
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
  <title>文件中控台</title>
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
        <h1>文件中控台</h1>
      </div>
    </div>
  </header>

  <div class="tabs-row">
    <div class="tabs">
      <button id="tabMonitorBtn" class="tab-btn active" type="button">中控</button>
      <button id="tabDirBtn" class="tab-btn" type="button">目录服务</button>
      <button id="tabPubBtn" class="tab-btn" type="button">ShareClip</button>
    </div>
    <div class="tabs-actions">
      <a id="terminalQuickLink" href="/terminal" class="gear-btn terminal-btn" title="Terminal" aria-label="Terminal"><svg class="term-icon" viewBox="0 0 24 24" aria-hidden="true"><rect x="3.5" y="4.5" width="17" height="12" rx="2"></rect><path d="M7.5 10.5 L10 12.5 L7.5 14.5"></path><line x1="11.5" y1="14.5" x2="15.8" y2="14.5"></line><line x1="9" y1="19.5" x2="15" y2="19.5"></line></svg></a>
      <a href="/config" class="gear-btn" title="Config" aria-label="Config">&#9881;</a>
      <button type="button" id="themeToggleBtn" class="secondary">浅色模式</button>
      <select id="langSelect" class="lang-select" title="Language">
        <option value="en">English</option>
        <option value="zh-CN">简体中文</option>
        <option value="zh-TW">繁體中文</option>
        <option value="de">Deutsch</option>
        <option value="fr">Français</option>
        <option value="ja">日本語</option>
      </select>
    </div>
  </div>

  <div id="tabDirPanel" class="tab-panel">
  <div class="card">
    <span class="card-title">目录与批量链接</span>
    <div class="kv-line"><strong>存储根目录</strong><span id="storageText">-</span></div>
    <div class="kv-line"><strong>公开访问域名</strong><span id="publicBaseText">-</span></div>
    <div class="kv-line"><strong>当前目录</strong><span id="currentDirText">.</span></div>
    <div class="toolbar">
      <div class="toolbar-left">
        <button id="refreshBtn" class="secondary">刷新目录</button>
        <button id="backBtn" class="secondary">返回上级</button>
        <button id="copyDirNameBtn" class="secondary">复制当前目录名</button>
        <button id="listBtn">生成当前目录所有文件 HTTP 链接</button>
        <button id="copyBtn" class="secondary">复制全部链接</button>
      </div>
    </div>
    <label>子目录（点击直接进入）</label>
    <div id="dirList" class="dir-list"></div>
    <div class="status-row">
      <div id="status" class="status-bar muted"></div>
      <div id="dirStatsText" class="status-bar muted dir-summary">文件 0 · 目录 0 · 大小 0B</div>
    </div>
  </div>

  <div class="card">
    <details class="card-fold">
      <summary class="card-collapse-btn">
        <span class="card-title" style="margin-bottom:0;">目录名清洗 / 批量重命名</span>
        <span class="card-collapse-arrow" aria-hidden="true">▶</span>
      </summary>
      <div id="cleanBody" class="card-fold-body">
      <p class="muted" style="margin:0 0 10px;">在<strong>当前相对目录</strong>下重命名；先预览再执行。可去掉宣传段、中文，并将 <code>S02</code> 季号挪到「首个 20xx 年」前（点分节）。</p>
      <label for="cleanSubstrings">要删除的子串（每行一个）</label>
      <textarea id="cleanSubstrings" style="min-height:72px;font-size:12px;" placeholder="例如整段：￡cXcY@FRDS"></textarea>
      <div class="row" style="margin-top:8px;align-items:flex-start;">
        <label class="inline-check" style="margin-top:0"><input type="checkbox" id="cleanStripCjk" /> 去掉中文（CJK / 全角块）</label>
        <label class="inline-check" style="margin-top:0"><input type="checkbox" id="cleanMoveSeason" checked /> 季号 S## 挪到首个年份 20xx 前</label>
      </div>
      <div class="row" style="margin-top:4px;">
        <label for="cleanTarget" style="margin:0;align-self:center;">对象</label>
        <select id="cleanTarget" class="small-inp" style="min-width:140px;">
          <option value="both" selected>文件 + 子文件夹</option>
          <option value="files">仅文件</option>
          <option value="dirs">仅子文件夹</option>
        </select>
        <label class="inline-check" style="margin-top:0"><input type="checkbox" id="cleanRecursive" /> 含子目录（自底向上改名）</label>
      </div>
      <div class="row" style="margin-top:8px;">
        <button type="button" class="secondary" id="cleanPreviewBtn">预览</button>
        <button type="button" id="cleanApplyBtn" disabled>按预览执行重命名</button>
      </div>
      <div id="cleanPreview" class="clean-preview" style="display:none" aria-live="polite"></div>
      <div id="cleanStatus" class="status-bar muted" style="margin-top:6px"></div>
      </div>
    </details>
  </div>

  <div class="card">
    <span class="card-title">批量文本（每行一个 HTTP 链接）</span>
    <textarea id="bulkText" readonly></textarea>
  </div>
  </div>

  <div id="tabPubPanel" class="tab-panel">
  <div class="card">
    <div class="pub-head">
      <button id="openPubNewBtn" class="secondary" type="button">新窗口打开</button>
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
    <span class="card-title">中控状态与操作</span>
    <div id="sysStatus" class="sys-strip muted">系统状态加载中...</div>
    <div class="svc-grid">
      <div class="svc-card" id="qbtSvcCard">
        <div class="svc-name">qBittorrent-nox</div>
        <div id="qbtStatusText" class="svc-meta">加载中...</div>
        <div class="row">
          <button id="qbtToggleBtn" class="secondary">开/关</button>
          <button id="qbtRestartBtn" class="secondary">重启</button>
        </div>
      </div>
      <div class="svc-card" id="ddnsSvcCard">
        <div class="svc-name">DDNS 服务</div>
        <div id="ddnsStatusText" class="svc-meta">加载中...</div>
        <div class="row">
          <button id="ddnsToggleBtn" class="secondary">开/关</button>
          <button id="ddnsRestartBtn" class="secondary">重启</button>
          <button id="ddnsConfigBtn" class="secondary">CONFIG</button>
        </div>
      </div>
      <div class="svc-card" id="httpSvcCard">
        <div class="svc-name">当前 HTTP 服务</div>
        <div id="selfStatusText" class="svc-meta">加载中...</div>
        <div class="row">
          <button id="toggleDownloadBtn" class="secondary">切换上传开关</button>
          <button id="restartServiceBtn" class="secondary">重启服务并中断上传</button>
        </div>
      </div>
    </div>
    <div id="monitorStatus" class="status-bar muted"></div>
  </div>

  <div class="card" id="httpSpeedCard">
    <span class="card-title">实时公网传输</span>
    <div class="speed-strip">
      <span>速度 <span id="speedText" class="hl">-</span></span>
      <span>活跃连接 <span id="connText" class="hl">-</span></span>
    </div>
    <div id="sourceSpeedText" class="speed-source muted">来源速度加载中...</div>
  </div>

  <div class="card" id="httpTransfersCard">
    <span class="card-title">当前传输（HTTP）</span>
    <div class="xfer-head">
      <div id="xferSummary" class="xfer-summary">活跃 0 个</div>
      <div class="xfer-toolbar">
        <span class="xfer-sort-label">排序</span>
        <div class="xfer-sort-group">
          <button type="button" class="xfer-sort-btn active" data-sort="speed">速度</button>
          <button type="button" class="xfer-sort-btn" data-sort="progress">进度</button>
          <button type="button" class="xfer-sort-btn" data-sort="name">名称</button>
          <button type="button" class="xfer-sort-btn" data-sort="source">来源</button>
        </div>
      </div>
    </div>
    <div id="xferList" class="xfer-list"></div>
  </div>
  </div>
  <footer class="global-footer">
    AfterClaw by
    <a href="mailto:mengke@pku.org.cn">Support</a>
    · Apache License 2.0 ·
    <a href="https://github.com/EinProfispieler/afterclaw" target="_blank" rel="noopener">GitHub</a>
  </footer>
  </div>

  <div id="toastContainer"></div>

  <script>
    const i18nReady = (window.fccI18n && window.fccI18n.initPage)
      ? window.fccI18n.initPage({ selectId: "langSelect" }).catch(() => {})
      : Promise.resolve();
    const tabDirBtn = document.getElementById("tabDirBtn");
    const tabMonitorBtn = document.getElementById("tabMonitorBtn");
    const tabPubBtn = document.getElementById("tabPubBtn");
    const tabDirPanel = document.getElementById("tabDirPanel");
    const tabMonitorPanel = document.getElementById("tabMonitorPanel");
    const tabPubPanel = document.getElementById("tabPubPanel");
    const storageText = document.getElementById("storageText");
    const publicBaseText = document.getElementById("publicBaseText");
    const speedText = document.getElementById("speedText");
    const connText = document.getElementById("connText");
    const sourceSpeedText = document.getElementById("sourceSpeedText");
    const httpSvcCard = document.getElementById("httpSvcCard");
    const httpSpeedCard = document.getElementById("httpSpeedCard");
    const httpTransfersCard = document.getElementById("httpTransfersCard");
    const toggleDownloadBtn = document.getElementById("toggleDownloadBtn");
    const qbtStatusText = document.getElementById("qbtStatusText");
    const ddnsStatusText = document.getElementById("ddnsStatusText");
    const selfStatusText = document.getElementById("selfStatusText");
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
    let currentDir = ".";
    let defaultHttpDir = ".";
    let lastCleanMoves = null;
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
      const btn = document.getElementById("themeToggleBtn");
      if (btn) {
        btn.textContent = theme === "dark" ? "浅色模式" : "深色模式";
      }
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
      showToast("切换为" + (next === "dark" ? "深色" : "浅色") + "主题");
      
    }

    function normalizeHeroPreset(v) {
      const x = String(v || "").trim().toLowerCase();
      if (x === "aurora" || x === "sunset" || x === "frost" || x === "afterclaw_clouds" || x === "custom") return x;
      return "default";
    }

    function applyHeroTheme(uiTheme) {
      const t = uiTheme || {};
      const preset = normalizeHeroPreset(t.hero_preset || "default");
      const customUrl = String(t.hero_custom_bg_url || "").trim();
      const customFile = String(t.hero_custom_bg_file || "").trim();
      const effectivePreset = (preset === "custom" && !customUrl) ? "default" : preset;
      heroTheme = {
        hero_preset: effectivePreset,
        hero_custom_bg_file: customFile,
        hero_custom_bg_url: customUrl,
      };
      document.documentElement.setAttribute("data-hero-preset", effectivePreset);
      try { localStorage.setItem(HERO_THEME_KEY, effectivePreset); } catch (e) {}
      if (customUrl) {
        const safeUrl = customUrl.replace(/"/g, '\\"');
        document.documentElement.style.setProperty("--hero-custom-url", `url("${safeUrl}")`);
      } else {
        document.documentElement.style.removeProperty("--hero-custom-url");
      }
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
      const showMonitor = which === "monitor";
      const showDir = which === "dir";
      const showPub = which === "pub";
      tabDirBtn.classList.toggle("active", showDir);
      tabMonitorBtn.classList.toggle("active", showMonitor);
      tabPubBtn.classList.toggle("active", showPub);
      tabDirPanel.classList.toggle("active", showDir);
      tabMonitorPanel.classList.toggle("active", showMonitor);
      tabPubPanel.classList.toggle("active", showPub);
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
        terminalQuickLink.title = "Terminal（未启用，点击去 Config 配置）";
      } else if (!host) {
        terminalQuickLink.title = "Terminal（未配置 Host，点击去 Config 配置）";
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
      dirStatsText.textContent = `文件 ${files} · 目录 ${dirs} · 大小 ${sizeHuman}`;
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
          setStatus("默认目录不可访问，已回退到根目录。", true);
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
        empty.textContent = "(当前目录无子目录)";
        dirList.appendChild(empty);
      }
    }

    function renderSpeedValue() {
      if (!speedText) return;
      if (speedDisplayUnit === "Mbps") {
        speedText.textContent = `↓ ${latestTotalDownMbps.toFixed(2)} Mbps / ↑ ${latestTotalUpMbps.toFixed(2)} Mbps`;
      } else {
        speedText.textContent = `↓ ${latestTotalDownMiBps.toFixed(2)} MiB/s / ↑ ${latestTotalUpMiBps.toFixed(2)} MiB/s`;
      }
      speedText.title = `点击切换单位（当前 ${speedDisplayUnit}）`;
      speedText.style.cursor = "pointer";
    }

    async function loadSpeed() {
      if (!httpModuleOn) {
        speedText.textContent = "-";
        speedText.title = "点击切换单位";
        connText.textContent = "-";
        speedValueReady = false;
        latestTotalDownMiBps = 0;
        latestTotalUpMiBps = 0;
        latestTotalDownMbps = 0;
        latestTotalUpMbps = 0;
        if (sourceSpeedText) sourceSpeedText.textContent = "来源速度：模块已关闭";
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
        speedText.textContent = "获取失败";
        speedText.title = "点击切换单位";
        connText.textContent = "-";
        speedValueReady = false;
        latestTotalDownMiBps = 0;
        latestTotalUpMiBps = 0;
        latestTotalDownMbps = 0;
        latestTotalUpMbps = 0;
        if (sourceSpeedText) sourceSpeedText.textContent = "来源速度获取失败";
      }
    }

    function normalizeSourceName(source) {
      const raw = String(source || "").trim();
      if (!raw) return "HTTP直连";
      const s = raw.toLowerCase();
      if (s.includes("百度") || s.includes("baidu") || s.includes("pan.baidu") || s.includes("xpan") || s.includes("netdisk") || s.includes("baiduyun") || s.includes("yun.baidu") || s.includes("pcs")) return "百度网盘";
      if (s.includes("光鸭") || s.includes("guangya")) return "光鸭网盘";
      if (s.includes("阿里") || s.includes("aliyun") || s.includes("alipan")) return "阿里云盘";
      if (s === "http直连" || s === "http-direct" || s === "http") return "HTTP直连";
      return "HTTP直连";
    }

    function renderSourceSpeeds(sourceStats) {
      if (!sourceSpeedText) return;
      const rows = Array.isArray(sourceStats) ? sourceStats : [];
      const buckets = new Map([
        ["百度网盘", { down: 0, up: 0, count: 0 }],
        ["光鸭网盘", { down: 0, up: 0, count: 0 }],
        ["阿里云盘", { down: 0, up: 0, count: 0 }],
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
      const chunks = [];
      for (const [name, v] of buckets.entries()) {
        const countText = v.count > 0 ? `（${Math.floor(v.count)}）` : "";
        knownDown += v.down;
        knownUp += v.up;
        chunks.push(`${name}${countText} ↓${v.down.toFixed(2)} ↑${v.up.toFixed(2)} MiB/s`);
      }
      const otherDown = Math.max(0, latestTotalDownMiBps - knownDown);
      const otherUp = Math.max(0, latestTotalUpMiBps - knownUp);
      chunks.push(`其他来源 ↓${otherDown.toFixed(2)} ↑${otherUp.toFixed(2)} MiB/s`);
      sourceSpeedText.textContent = `来源速度：${chunks.join(" | ")}`;
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
        return `${ip} | 片段 ${sent} / ${total} (${pct.toFixed(1)}%) | 文件总长 ${fileTotalHuman}`;
      }
      return `${ip} | ${sent} / ${total} | ${pct.toFixed(1)}%`;
    }

    function renderTransfers(data) {
      const allItems = Array.isArray(data.items) ? data.items : [];
      const items = sortTransfers(allItems.filter((it) => !it.done));
      const count = Number(data.count || items.length || 0);
      const recentCount = Number(data.recent_count || 0);
      const overall = Number(data.overall_progress_pct || 0);
      xferSummary.textContent = `活跃 ${count} 个 · 最近完成 ${recentCount} 个 · 总完成度 ${Math.max(0, Math.min(100, overall)).toFixed(1)}%`;
      xferList.innerHTML = "";
      if (!items.length) {
        const empty = document.createElement("div");
        empty.className = "xfer-item muted";
        empty.textContent = "当前没有活跃 HTTP 传输任务。";
        xferList.appendChild(empty);
        return;
      }
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
        file.textContent = it.filename || it.relative_path || "(未知文件)";
        const speed = document.createElement("div");
        speed.className = "xfer-speed";
        speed.textContent = it.done ? "已完成" : `${(it.speed_mibps || 0).toFixed(2)} MiB/s`;
        main.appendChild(source);
        main.appendChild(file);
        main.appendChild(speed);
        const meta = document.createElement("div");
        meta.className = "xfer-meta";
        meta.textContent = formatTransferMeta(it);
        row.appendChild(main);
        row.appendChild(meta);
        xferList.appendChild(row);
      }
    }

    async function loadTransfers() {
      if (!httpModuleOn) {
        xferSummary.textContent = "模块已关闭";
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
        xferSummary.textContent = "活跃 -";
        if (sourceSpeedText) sourceSpeedText.textContent = "来源速度获取失败";
      }
    }

    function renderDownloadSwitch() {
      toggleDownloadBtn.textContent = downloadsEnabled ? "关闭外网上传" : "开启外网上传";
      toggleDownloadBtn.className = downloadsEnabled ? "secondary" : "";
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
        return '<span class="svc-dot ' + dotClass + '"></span>' + mark + ' | ' + escapeHtml(String(unit)) + '<br><span class="svc-meta" style="font-size:12px; line-height:1.4;">' + escapeHtml(String(detail)) + '</span>';
      }
      return '<span class="svc-dot ' + dotClass + '"></span>' + mark + ' | ' + escapeHtml(String(unit));
    }

    function renderControlStatus(data) {
      sysStatus.className = "sys-strip";
      const s = data.system || {};
      const cpuText = `CPU负载(1m): ${Number(s.load1 || 0).toFixed(2)}`;
      const restText = `内存: ${s.mem_used_human || "-"} / ${s.mem_total_human || "-"} | 磁盘: ${s.disk_used_human || "-"} / ${s.disk_total_human || "-"} | 运行: ${s.uptime_human || "-"}`;
      sysStatus.innerHTML = `<div class="sys-status-line">${cpuText}</div><div class="sys-status-line">${restText}</div>`;
      qbtStatusText.innerHTML = svcText(data.qbt);
      ddnsStatusText.innerHTML = svcText(data.ddns);
      selfStatusText.innerHTML = svcText(data.self);
      const appCfg = data.app_config || {};
      const mods = appCfg.modules || {};
      const showQbtModule = mods.qbt !== false;
      const showDdnsModule = mods.ddns !== false;
      const showShareclipModule = mods.shareclip !== false;
      const showHttpModule = mods.http !== false;
      httpModuleOn = !!showHttpModule;
      const qbtSvcCard = document.getElementById("qbtSvcCard");
      if (qbtSvcCard) qbtSvcCard.style.display = showQbtModule ? "" : "none";
      if (tabPubBtn) tabPubBtn.style.display = showShareclipModule ? "" : "none";
      if (tabPubPanel) tabPubPanel.style.display = showShareclipModule ? "" : "none";
      if (httpSvcCard) httpSvcCard.style.display = showHttpModule ? "" : "none";
      if (httpSpeedCard) httpSpeedCard.style.display = showHttpModule ? "" : "none";
      if (httpTransfersCard) httpTransfersCard.style.display = showHttpModule ? "" : "none";
      if (!showShareclipModule && tabPubBtn && tabPubBtn.classList.contains("active")) {
        switchTab("monitor");
      }
      const qbtActive = data.qbt && data.qbt.active_state === "active";
      qbtControlOn = !!qbtActive;
      const ddnsBuiltin = data.ddns && data.ddns.source === "builtin";
      const ddnsActive = ddnsBuiltin ? !!data.ddns.enabled : (data.ddns && data.ddns.active_state === "active");
      ddnsControlOn = !!ddnsActive;
      document.getElementById("qbtToggleBtn").textContent = trRaw(qbtActive ? "Stop" : "Start");
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
        const data = await getJson("/api/control/status");
        if (isRealtimePaused() || reqTs < dashboardPauseUntil) return;
        renderControlStatus(data);
      } catch (err) {
        sysStatus.className = "sys-strip";
        sysStatus.innerHTML = `<div class="sys-status-line" style="color:var(--danger);">状态获取失败：${err.message}</div>`;
      }
    }

    async function controlService(service, action) {
      try {
        const data = await getJson("/api/control/service", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ service, action }),
        });
        if (service === "self" && action === "restart") {
          setStatus("已发送重启命令，服务即将重启。");
          setTimeout(loadControlStatus, 1500);
          return;
        }
        renderControlStatus(data);
        setStatus(`${service} 已执行 ${action}`);
      } catch (err) {
        setStatus(`操作失败：${err.message}`, true);
      }
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
      st.textContent = "正在预览…";
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
          st.textContent = "无变更：当前规则下没有需要重命名的项。";
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
        st.textContent = `共 ${moves.length} 项，可执行 ${lastCleanMoves.length} 项${
          bad.length ? "，" + bad.length + " 项冲突" : ""
        }。`;
        applyBtn.disabled = lastCleanMoves.length === 0;
      } catch (e) {
        st.className = "status-bar err";
        st.textContent = "预览失败：" + e.message;
      }
    }

    async function runCleanApply() {
      if (!lastCleanMoves || !lastCleanMoves.length) return;
      if (!confirm("确定按预览对 " + lastCleanMoves.length + " 项重命名？此操作不可自动撤销。")) {
        return;
      }
      const st = document.getElementById("cleanStatus");
      st.className = "status-bar muted";
      st.textContent = "正在执行…";
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
        st.textContent = "完成：成功 " + okN + "，失败 " + (results.length - okN) + "。";
        if (okN) showToast("已重命名 " + okN + " 项", "success");
        lastCleanMoves = null;
        document.getElementById("cleanApplyBtn").disabled = true;
        await loadBaseAndDirs(false);
      } catch (e) {
        st.className = "status-bar err";
        st.textContent = "执行失败：" + e.message;
      }
    }

    async function toggleDownloads() {
      const targetEnabled = !downloadsEnabled;
      try {
        const data = await getJson("/api/control/downloads", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ enabled: targetEnabled }),
        });
        downloadsEnabled = !!data.downloads_enabled;
        renderDownloadSwitch();
        setStatus(`外网上传已${downloadsEnabled ? "开启" : "关闭"}`);
      } catch (err) {
        setStatus(`切换失败：${err.message}`, true);
      }
    }

    async function restartService() {
      const restartConfirmText = (window.fccI18n && typeof window.fccI18n.translateRaw === "function")
        ? (window.fccI18n.translateRaw("确认重启服务？这会中断当前所有上传连接。") || "确认重启服务？这会中断当前所有上传连接。")
        : "确认重启服务？这会中断当前所有上传连接。";
      if (!confirm(restartConfirmText)) {
        return;
      }
      try {
        await getJson("/api/control/restart", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ reason: "manual-ui" }),
        });
        setStatus("已发送重启命令，当前上传连接会被中断。");
      } catch (err) {
        setStatus(`重启失败：${err.message}`, true);
      }
    }

    document.getElementById("refreshBtn").addEventListener("click", () => loadBaseAndDirs(false));
    document.getElementById("backBtn").addEventListener("click", goParentDir);
    document.getElementById("listBtn").addEventListener("click", listLinks);
    document.getElementById("copyBtn").addEventListener("click", copyAllLinks);
    document.getElementById("copyDirNameBtn").addEventListener("click", copyCurrentDirName);
    document.getElementById("cleanPreviewBtn").addEventListener("click", runCleanPreview);
    document.getElementById("cleanApplyBtn").addEventListener("click", runCleanApply);
    document.getElementById("toggleDownloadBtn").addEventListener("click", toggleDownloads);
    document.getElementById("restartServiceBtn").addEventListener("click", restartService);
    document.getElementById("qbtToggleBtn").addEventListener("click", () => {
      controlService("qbt", qbtControlOn ? "stop" : "start");
    });
    document.getElementById("qbtRestartBtn").addEventListener("click", () => controlService("qbt", "restart"));
    document.getElementById("ddnsToggleBtn").addEventListener("click", () => {
      controlService("ddns", ddnsControlOn ? "stop" : "start");
    });
    document.getElementById("ddnsRestartBtn").addEventListener("click", () => controlService("ddns", "restart"));
    document.getElementById("ddnsConfigBtn").addEventListener("click", () => {
      window.location.href = "/config#ddns";
    });
    document.getElementById("themeToggleBtn").addEventListener("click", toggleTheme);
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
      speedText.title = "点击切换单位（当前 MiB/s）";
      speedText.style.cursor = "pointer";
      speedText.addEventListener("click", () => {
        if (!speedValueReady) return;
        speedDisplayUnit = speedDisplayUnit === "MiB/s" ? "Mbps" : "MiB/s";
        renderSpeedValue();
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
    return _inject_page_title(html, "文件中控台")


def build_ddns_settings_html() -> str:
    return _inject_page_title(load_ddns_settings_page(), "DDNS 设置")


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
    .cfg-tab {
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 10px 14px;
      background: var(--surface-soft);
      cursor: pointer;
      font-weight: 600;
      color: var(--text);
    }
    .cfg-tab.active {
      background: color-mix(in srgb, var(--hero-tone-soft, var(--accent-soft)) 82%, transparent);
      color: var(--hero-tone, var(--accent));
      border-color: color-mix(in srgb, var(--hero-tone, var(--accent)) 68%, var(--border) 32%);
      box-shadow: 0 0 0 1px color-mix(in srgb, var(--hero-tone, var(--accent)) 32%, transparent);
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
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 14px 16px;
      background: var(--surface-soft);
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
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 12px;
      background: var(--surface-soft);
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
      border: 1px solid var(--border);
      border-radius: 12px;
      overflow: hidden;
      background: var(--surface-soft);
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
          <a href="/" class="back-link">← Back to AfterClaw</a>
          <h1 data-i18n="config.title" data-i18n-fallback="Configuration">Configuration</h1>
          <p class="page-sub" data-i18n="config.subtitle" data-i18n-fallback="General Settings (module toggles) / HTTP / qB / Terminal / DDNS">General Settings (module toggles) / HTTP / qB / Terminal / DDNS</p>
        </div>
      </div>
    </header>

    <div class="cfg-tabs-row">
      <div class="cfg-tabs">
        <button class="cfg-tab active" type="button" data-tab="general" data-i18n="config.tab.general" data-i18n-fallback="General">General</button>
        <button class="cfg-tab" type="button" data-tab="http" data-i18n="config.tab.http" data-i18n-fallback="HTTP">HTTP</button>
        <button class="cfg-tab" type="button" data-tab="qbt" data-i18n="config.tab.qb" data-i18n-fallback="qB">qB</button>
        <button class="cfg-tab" type="button" data-tab="terminal" data-i18n="config.tab.terminal" data-i18n-fallback="Terminal">Terminal</button>
        <button class="cfg-tab" type="button" data-tab="ddns" data-i18n="config.tab.ddns" data-i18n-fallback="DDNS">DDNS</button>
      </div>
      <div class="cfg-tabs-actions">
        <a id="terminalHeadLink" href="/terminal" class="gear-btn terminal-btn" title="Terminal" aria-label="Terminal"><svg class="term-icon" viewBox="0 0 24 24" aria-hidden="true"><rect x="3.5" y="4.5" width="17" height="12" rx="2"></rect><path d="M7.5 10.5 L10 12.5 L7.5 14.5"></path><line x1="11.5" y1="14.5" x2="15.8" y2="14.5"></line><line x1="9" y1="19.5" x2="15" y2="19.5"></line></svg></a>
        <button type="button" id="themeToggleBtn" class="secondary">主题</button>
        <select id="langSelect" class="lang-select" title="Language">
          <option value="en">English</option>
          <option value="zh-CN">简体中文</option>
          <option value="zh-TW">繁體中文</option>
          <option value="de">Deutsch</option>
          <option value="fr">Français</option>
          <option value="ja">日本語</option>
        </select>
      </div>
    </div>

    <section id="panel-general" class="cfg-panel active">
      <div class="card">
        <span class="card-title">综合配置（开关各模块）</span>
        <div class="cfg-module-list">
          <label class="cfg-module-item">
            <input type="checkbox" id="modHttp" class="cfg-switch-input" checked />
            <span class="cfg-switch" aria-hidden="true"></span>
            <div>
              <p class="cfg-module-title">HTTP 模块</p>
              <p class="cfg-module-desc">控制主页面“当前 HTTP 服务”与 HTTP 监控区域。关闭时会强制断开一次连接并关闭上传。</p>
            </div>
          </label>
          <label class="cfg-module-item">
            <input type="checkbox" id="modQbt" class="cfg-switch-input" checked />
            <span class="cfg-switch" aria-hidden="true"></span>
            <div>
              <p class="cfg-module-title">qB 模块</p>
              <p class="cfg-module-desc">主页面显示 qB 状态卡及 qB 相关控制入口。</p>
            </div>
          </label>
          <label class="cfg-module-item">
            <input type="checkbox" id="modDdns" class="cfg-switch-input" checked />
            <span class="cfg-switch" aria-hidden="true"></span>
            <div>
              <p class="cfg-module-title">DDNS 模块</p>
              <p class="cfg-module-desc">主页面显示 DDNS 状态卡，并保留 Config 内 DDNS 设置入口。</p>
            </div>
          </label>
          <label class="cfg-module-item">
            <input type="checkbox" id="modShareclip" class="cfg-switch-input" checked />
            <span class="cfg-switch" aria-hidden="true"></span>
            <div>
              <p class="cfg-module-title">ShareClip 模块</p>
              <p class="cfg-module-desc">控制主页面 ShareClip 标签页显示。</p>
            </div>
          </label>
        </div>
        <div class="cfg-actions">
          <button type="button" id="saveModulesBtn">保存综合配置</button>
          <button type="button" id="restartCfgServiceBtn" class="secondary">重启服务</button>
        </div>
        <p id="generalStatus" class="cfg-status"></p>
      </div>
      <div class="card">
        <span class="card-title">自动升级（GitHub Release）</span>
        <p class="cfg-help">从 GitHub 拉取发布包并执行本地 <code>install.sh</code>。升级过程中服务可能重启，页面短暂断开属于正常现象。</p>
        <p class="cfg-help" style="margin-top:6px;">当前服务器版本：<code id="upgradeCurrentVersion">-</code></p>
        <div class="cfg-grid" style="margin-top:12px;">
          <label class="cfg-item">
            <div class="title">仓库（owner/repo）</div>
            <input id="upgradeRepoInput" placeholder="例如：EinProfispieler/afterclaw" />
          </label>
          <label class="cfg-item">
            <div class="title">升级分支</div>
            <select id="upgradeBranchSelect">
              <option value="stable">stable（稳定版）</option>
              <option value="nightly">nightly（开发版）</option>
            </select>
          </label>
          <label class="cfg-item">
            <div class="title">目标 Tag（可选）</div>
            <input id="upgradeTagInput" placeholder="留空则升级到所选分支的 latest release" />
          </label>
        </div>
        <div class="cfg-actions">
          <button type="button" id="runUpgradeBtn">执行自动升级</button>
          <button type="button" id="refreshUpgradeStatusBtn" class="secondary">刷新升级状态</button>
        </div>
        <p id="upgradeStatus" class="cfg-status"></p>
        <p id="upgradeMeta" class="cfg-help"></p>
      </div>
      <div class="card">
        <span class="card-title">
          <svg class="brush-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M14.2 4.2l5.6 5.6-9.8 9.8-6.7 1 1-6.7 9.9-9.7z"></path><path d="M12.1 6.3l5.6 5.6"></path></svg>
          主题背景
        </span>
        <p class="cfg-help">这里设置主页顶栏背景，不再在主页常驻显示配置面板。</p>
        <div class="theme-panel" style="margin-top:10px;">
          <div class="theme-preset-group">
            <button type="button" class="theme-preset-btn" data-hero-preset="default">默认</button>
            <button type="button" class="theme-preset-btn" data-hero-preset="aurora">极光</button>
            <button type="button" class="theme-preset-btn" data-hero-preset="sunset">落日</button>
            <button type="button" class="theme-preset-btn" data-hero-preset="frost">冰川</button>
            <button type="button" class="theme-preset-btn" data-hero-preset="afterclaw_clouds">云海暮光</button>
            <button type="button" class="theme-preset-btn" data-hero-preset="custom">自定义</button>
          </div>
          <div class="theme-upload-row">
            <input id="cfgThemeBgFileInput" type="file" accept="image/png,image/jpeg,image/webp,image/gif,image/avif" />
            <button type="button" id="cfgThemeBgUploadBtn" class="secondary">上传并应用</button>
            <button type="button" id="cfgThemeBgClearBtn" class="secondary">恢复默认</button>
          </div>
          <p id="cfgThemeMeta" class="cfg-help">当前背景：默认</p>
          <p id="cfgThemeStatus" class="cfg-help">支持 PNG/JPG/WEBP/GIF/AVIF，最大 12MB。</p>
        </div>
      </div>
    </section>

    <section id="panel-http" class="cfg-panel">
      <div class="card">
        <span class="card-title">HTTP 配置</span>
        <div class="cfg-grid" style="margin-top:12px;">
          <label class="cfg-item">
            <div class="title">程序端口</div>
            <p class="cfg-help">默认 1288。保存 HTTP 配置后需重启程序才会切换监听端口。</p>
            <input id="webPortInput" type="number" min="1" max="65535" placeholder="1288" />
            <p id="webPortHint" class="cfg-help" style="margin-top:8px;">当前运行端口：1288</p>
          </label>
        </div>
        <p class="cfg-help">当前 HTTP 根目录：<strong id="httpStorageRoot">-</strong></p>
        <div class="cfg-grid" style="margin-top:12px;">
          <label class="cfg-item">
            <div class="title">HTTP 根目录（允许 / 下任意目录）</div>
            <p class="cfg-help">填写绝对路径，例如：<code>/</code>、<code>/srv/Storage</code>、<code>/home/user</code>。</p>
            <input id="httpRootDir" placeholder="例如：/srv/Storage 或 /" />
            <div class="row" style="margin-top:8px;">
              <button type="button" id="httpScanRootBtn" class="secondary">验证（扫描）</button>
            </div>
            <p id="httpScanResult" class="cfg-help" style="margin-top:8px;"></p>
          </label>
          <label class="cfg-item">
            <div class="title">默认目录（相对 HTTP 根目录）</div>
            <p class="cfg-help">主页面“目录服务”打开时会默认跳转到此目录。</p>
            <input id="httpDefaultDir" placeholder="例如：BT/TV 或 ." />
          </label>
          <div class="cfg-item" style="grid-column: 1 / -1;">
            <div class="title">来源 IP 池（1288 训练）</div>
            <p class="cfg-help">按“每行一个 IP/CIDR”维护来源池。命中后优先标记为对应来源（高于 UA/Referer 关键词）。</p>
            <div class="cfg-grid" style="margin-top:10px; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));">
              <label class="cfg-item">
                <div class="title">百度网盘 IP 池</div>
                <textarea id="httpPoolBaidu" rows="7" placeholder="例如：&#10;112.80.248.0/21&#10;220.181.38.0/24"></textarea>
              </label>
              <label class="cfg-item">
                <div class="title">光鸭网盘 IP 池</div>
                <textarea id="httpPoolGuangya" rows="7" placeholder="例如：&#10;203.0.113.0/24"></textarea>
              </label>
              <label class="cfg-item">
                <div class="title">阿里云盘 IP 池</div>
                <textarea id="httpPoolAliyun" rows="7" placeholder="例如：&#10;47.0.0.0/8"></textarea>
              </label>
            </div>
            <div class="cfg-item" style="margin-top:10px;">
              <div class="title">可更新来源（GitHub/URL）</div>
              <p class="cfg-help">支持 <code>github:owner/repo/path</code>，例如：<code>github:EinProfispieler/afterclaw/data/vendor-ip-pools</code>。</p>
              <div class="row" style="margin-top:8px;">
                <input id="httpPoolSource" class="grow" placeholder="例如：github:EinProfispieler/afterclaw/data/vendor-ip-pools" />
                <button type="button" id="syncHttpPoolSourceBtn" class="secondary">从源更新 IP 池</button>
              </div>
              <p id="httpPoolSourceMeta" class="cfg-help" style="margin-top:8px;"></p>
            </div>
          </div>
          <div class="cfg-item">
            <div class="title">目录浏览器（目标服务器）</div>
            <div class="row" style="margin-top:8px;">
              <input id="httpBrowseDir" class="grow" placeholder="例如：." />
              <button type="button" id="httpBrowseLoadBtn" class="secondary">加载子目录</button>
              <button type="button" id="httpBrowseParentBtn" class="secondary">上级</button>
            </div>
            <p class="cfg-help" style="margin-top:8px;">点击下方子目录可快速设为默认目录。</p>
            <div id="httpDirList" class="dir-list" style="max-height:230px;"></div>
          </div>
        </div>
        <div class="cfg-actions">
          <button type="button" id="saveHttpBtn">保存 HTTP 配置</button>
        </div>
        <p id="httpStatus" class="cfg-status"></p>
      </div>
    </section>

    <section id="panel-qbt" class="cfg-panel">
      <div class="card">
        <span class="card-title">qB 配置</span>
        <div class="cfg-grid" style="margin-top:12px;">
          <label class="cfg-item inline-check">
            <input type="checkbox" id="qbtMonitorEnabled" /> <span class="title">qB 监控</span>
          </label>
        </div>
        <div class="cfg-actions">
          <button type="button" id="saveQbtBtn">保存 qB 配置</button>
          <button type="button" id="qbtOptimizeBtn">一键优化配置</button>
          <button type="button" id="qbtFixPermBtn" class="secondary">修复 qB 监控权限</button>
          <button type="button" id="qbtRestartSvcBtn" class="secondary">qB 服务重启</button>
          <button type="button" id="qbtQuitBtn" class="secondary">qB 退出</button>
        </div>
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
            <span class="title">启用主页 Terminal 图标</span>
          </label>
          <label class="cfg-item">
            <div class="title">Host</div>
            <input id="termHost" placeholder="例如：192.168.1.30" />
          </label>
          <label class="cfg-item">
            <div class="title">User</div>
            <input id="termUser" placeholder="例如：root" />
          </label>
          <label class="cfg-item">
            <div class="title">Port</div>
            <input id="termPort" type="number" min="1" max="65535" placeholder="22" />
          </label>
          <label class="cfg-item">
            <div class="title">认证方式</div>
            <select id="termAuthMode">
              <option value="key">key（推荐）</option>
              <option value="password">password（不保存密码）</option>
            </select>
          </label>
          <label class="cfg-item" id="termKeyFileItem">
            <div class="title">配置目录 Key 文件名（可选）</div>
            <input id="termKeyFile" list="termKeyFileList" placeholder="例如：id_ed25519" />
            <datalist id="termKeyFileList"></datalist>
            <p class="cfg-help" style="margin-top:6px;">配置目录：<code id="termKeyDirText">terminal_keys</code></p>
            <div class="row" style="margin-top:8px;">
              <button type="button" id="termPickKeyBtn" class="secondary">选择并上传 key</button>
              <button type="button" id="termRefreshKeyListBtn" class="secondary">刷新 key 列表</button>
              <input id="termKeyUploadInput" type="file" accept=".pem,.key,.txt,application/x-pem-file,application/octet-stream,text/plain" style="display:none;" />
            </div>
            <p class="cfg-help" style="margin-top:6px;">可从当前设备选择私钥文件并上传到配置目录。</p>
          </label>
          <label class="cfg-item" id="termKeyPathItem">
            <div class="title">私钥路径（key 模式）</div>
            <input id="termKeyPath" placeholder="例如：~/.ssh/id_ed25519" />
            <p class="cfg-help" style="margin-top:6px;">未填“配置目录 Key 文件名”时使用此路径。</p>
          </label>
        </div>
        <div class="cfg-item" style="margin-top:12px;">
          <div class="title">连接预览</div>
          <p id="terminalTip" class="cfg-help"></p>
          <p class="cfg-help" style="margin-top:8px;">Terminal Link:
            <a id="terminalPreviewLink" href="#terminal" target="_blank" rel="noopener">未配置</a>
          </p>
          <p class="cfg-help" style="margin-top:6px;">网页终端入口：
            <a id="terminalWebLink" href="/terminal">打开 /terminal</a>
          </p>
          <div id="terminalPreviewCmd" class="cfg-code">未配置</div>
        </div>
        <div class="cfg-actions">
          <button type="button" id="saveTerminalBtn">保存 Terminal 配置</button>
          <button type="button" id="copyTerminalCmdBtn" class="secondary">复制 SSH 命令</button>
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
      qbt: { monitor_enabled: true },
      http_service: {
        root_dir: "/srv/Storage",
        default_dir: ".",
        source_ip_pools: { baidu: [], guangya: [], aliyun: [] },
        source_ip_pool_source: "github:EinProfispieler/afterclaw/data/vendor-ip-pools"
      },
      ui: {
        hero_preset: "default",
        hero_custom_bg_file: ""
      },
      terminal: {
        enabled: true,
        host: "192.168.1.30",
        user: "root",
        port: 22,
        auth_mode: "key",
        key_path: "~/.ssh/id_ed25519",
        key_file: ""
      }
    };
    var runtimeWebPort = 1288;
    var heroTheme = { hero_preset: "default", hero_custom_bg_file: "", hero_custom_bg_url: "" };
    var upgradeState = { supported: false, running: false, state: "idle", current_version: "", current_branch: "", repo: "EinProfispieler/afterclaw", requested_tag: "", target_tag: "", release_url: "", message: "", error: "" };
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
      var b = byId("themeToggleBtn");
      if (b) b.textContent = t === "dark" ? "浅色模式" : "深色模式";
    }
    function normalizeHeroPreset(v){
      var x = String(v || "").trim().toLowerCase();
      if (x === "aurora" || x === "sunset" || x === "frost" || x === "afterclaw_clouds" || x === "custom") return x;
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
      var customUrl = String(t.hero_custom_bg_url || "").trim();
      var customFile = String(t.hero_custom_bg_file || "").trim();
      var effective = (preset === "custom" && !customUrl) ? "default" : preset;
      heroTheme = {
        hero_preset: effective,
        hero_custom_bg_file: customFile,
        hero_custom_bg_url: customUrl
      };
      document.documentElement.setAttribute("data-hero-preset", effective);
      try { localStorage.setItem(HERO_THEME_KEY, effective); } catch (e) {}
      if (customUrl) {
        var safeUrl = customUrl.replace(/"/g, '\\"');
        document.documentElement.style.setProperty("--hero-custom-url", 'url("' + safeUrl + '")');
      } else {
        document.documentElement.style.removeProperty("--hero-custom-url");
      }
      var meta = byId("cfgThemeMeta");
      if (meta) {
        var labels = { default: "默认", aurora: "极光", sunset: "落日", frost: "冰川", afterclaw_clouds: "云海暮光", custom: "自定义图片" };
        meta.textContent = "当前背景：" + (labels[effective] || "默认");
      }
      syncHeroPresetButtons();
    }
    async function apiJson(url, opts){
      var r = await fetch(url, opts || {});
      var d = await r.json().catch(function(){ return {}; });
      if (!r.ok) throw new Error((d && d.error) || ("请求失败 " + r.status));
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
      byId("httpPoolBaidu").value = poolRowsToText(pools.baidu || pools["百度网盘"] || []);
      byId("httpPoolGuangya").value = poolRowsToText(pools.guangya || pools["光鸭网盘"] || []);
      byId("httpPoolAliyun").value = poolRowsToText(pools.aliyun || pools["阿里云盘"] || []);
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
      setStatus("httpStatus", "正在从来源同步 IP 池...");
      var d = await apiJson("/api/http/source-ip-pools/sync", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ source: source, merge: true })
      });
      applyCfg((d && d.config) || d);
      var counts = (d && d.counts) || {};
      var remoteCounts = (d && d.remote_counts) || {};
      var mode = String((d && d.mode) || "merge");
      var summary = "来源同步完成：百度 " + Number(counts.baidu || 0)
        + " · 光鸭 " + Number(counts.guangya || 0)
        + " · 阿里云 " + Number(counts.aliyun || 0);
      var files = (d && Array.isArray(d.files_used)) ? d.files_used : [];
      var meta = "当前来源：" + source;
      if (files.length) {
        meta += " | 命中文件 " + files.length + " 个";
      }
      if (mode === "merge") {
        meta += " | 合并模式（远端新增：百度 " + Number(remoteCounts.baidu || 0)
          + " · 光鸭 " + Number(remoteCounts.guangya || 0)
          + " · 阿里云 " + Number(remoteCounts.aliyun || 0) + "）";
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
    function updateWebPortHint(){
      var hint = byId("webPortHint");
      if (!hint) return;
      var desired = parseWebPort(byId("webPortInput") ? byId("webPortInput").value : cfg.web_port, cfg.web_port || 1288);
      var msg = "当前运行端口：" + String(runtimeWebPort) + "。";
      if (desired !== runtimeWebPort) {
        msg += " 保存后需重启程序，重启后切换到：" + String(desired) + "。";
      } else {
        msg += " 当前保存值与运行端口一致。";
      }
      hint.textContent = msg;
    }
    function normalizeUpgradeRepoInput(raw){
      var v = String(raw || "").trim().replace(/^https?:\/\/github\.com\//i, "").replace(/\/+$/g, "");
      return v;
    }
    function normalizeUpgradeTagInput(raw){
      return String(raw || "").trim();
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
        current_branch: String(s.current_branch || "stable"),
        repo: String(s.repo || "EinProfispieler/afterclaw"),
        requested_tag: String(s.requested_tag || ""),
        target_tag: String(s.target_tag || ""),
        release_url: String(s.release_url || ""),
        message: String(s.message || ""),
        error: String(s.error || ""),
        support_reason: String(s.support_reason || "")
      };
      if (byId("upgradeRepoInput")) {
        if (!String(byId("upgradeRepoInput").value || "").trim()) {
          byId("upgradeRepoInput").value = upgradeState.repo;
        }
      }
      if (byId("upgradeBranchSelect")) {
        byId("upgradeBranchSelect").value = upgradeState.current_branch;
      }
      if (byId("upgradeTagInput")) {
        var preferredTag = upgradeState.requested_tag || upgradeState.target_tag || "";
        if (!String(byId("upgradeTagInput").value || "").trim() && preferredTag) {
          byId("upgradeTagInput").value = preferredTag;
        }
      }
      var statusText = "";
      var isErr = false;
      if (!upgradeState.supported) {
        statusText = "自动升级不可用" + (upgradeState.support_reason ? "：" + upgradeState.support_reason : "");
        isErr = true;
      } else if (upgradeState.running) {
        statusText = "升级进行中";
        if (upgradeState.target_tag) statusText += "：" + upgradeState.target_tag;
        if (upgradeState.message) statusText += " · " + upgradeState.message;
      } else if (upgradeState.state === "success") {
        statusText = upgradeState.message || ("升级完成：" + (upgradeState.target_tag || "latest"));
      } else if (upgradeState.state === "error") {
        statusText = upgradeState.error ? ("升级失败：" + upgradeState.error) : "升级失败";
        isErr = true;
      } else {
        statusText = upgradeState.message || "等待执行升级";
      }
      var statusEl = byId("upgradeStatus");
      if (statusEl) {
        statusEl.textContent = statusText;
        statusEl.className = isErr ? "cfg-status err" : "cfg-status";
      }
      if (byId("upgradeCurrentVersion")) {
        byId("upgradeCurrentVersion").textContent = upgradeState.current_version || "-";
      }
      var meta = [];
      if (upgradeState.current_version) meta.push("当前服务器版本：" + upgradeState.current_version);
      if (upgradeState.current_branch) meta.push("当前分支：" + upgradeState.current_branch);
      if (upgradeState.repo) meta.push("仓库：" + upgradeState.repo);
      if (upgradeState.requested_tag) meta.push("请求 Tag：" + upgradeState.requested_tag);
      if (upgradeState.target_tag) meta.push("目标版本：" + upgradeState.target_tag);
      if (s.started_at) meta.push("开始：" + String(s.started_at));
      if (s.finished_at) meta.push("结束：" + String(s.finished_at));
      if (upgradeState.release_url) meta.push("Release：" + upgradeState.release_url);
      if (byId("upgradeMeta")) byId("upgradeMeta").textContent = meta.join(" | ");
      var branchSelect = byId("upgradeBranchSelect");
      var selectedBranch = branchSelect ? String(branchSelect.value || "stable") : "stable";
      var tagInput = byId("upgradeTagInput");
      var tagValue = tagInput ? String(tagInput.value || "").trim() : "";
      var branchMatchesCurrent = (selectedBranch === upgradeState.current_branch) && !tagValue;
      if (byId("runUpgradeBtn")) {
        byId("runUpgradeBtn").disabled = (!upgradeState.supported) || !!upgradeState.running || branchMatchesCurrent;
      }
      if (byId("refreshUpgradeStatusBtn")) {
        byId("refreshUpgradeStatusBtn").disabled = false;
      }
    }
    async function loadUpgradeStatus(silent){
      var d = await apiJson("/api/upgrade/status");
      renderUpgradeStatus(d || {});
      if (!silent && upgradeState.running) {
        setStatus("upgradeStatus", "升级任务进行中，请勿关闭页面。");
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
    async function runAutoUpgrade(){
      var repo = normalizeUpgradeRepoInput(byId("upgradeRepoInput") ? byId("upgradeRepoInput").value : "");
      var tag = normalizeUpgradeTagInput(byId("upgradeTagInput") ? byId("upgradeTagInput").value : "");
      var branch = byId("upgradeBranchSelect") ? String(byId("upgradeBranchSelect").value || "stable") : "stable";
      if (!repo) {
        throw new Error("请先填写仓库 owner/repo");
      }
      var hintTag = tag ? ("Tag " + tag) : (branch + " latest release");
      if (!window.confirm("确认执行自动升级？将从 " + repo + " 拉取 " + hintTag + " 并执行 install.sh（过程中服务可能重启）。")) {
        return null;
      }
      setStatus("upgradeStatus", "正在提交升级任务...");
      var d = await apiJson("/api/upgrade/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ repo: repo, tag: tag, branch: branch })
      });
      renderUpgradeStatus((d && d.status) || {});
      if (d && d.queued) {
        setStatus("upgradeStatus", "升级任务已入队，正在执行。");
      } else {
        setStatus("upgradeStatus", "已有升级任务在执行或当前环境不支持自动升级。", true);
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
      var labels = { default: "默认", aurora: "极光", sunset: "落日", frost: "冰川", afterclaw_clouds: "云海暮光", custom: "自定义图片" };
      setHeroThemeStatus("已切换背景：" + (labels[p] || "默认"));
    }
    async function uploadHeroImageFromFile(file){
      if (!file) throw new Error("请先选择一张本地图片");
      var name = String(file.name || "").trim();
      if (!/\\.(png|jpe?g|webp|gif|avif)$/i.test(name)) {
        throw new Error("仅支持 PNG/JPG/WEBP/GIF/AVIF");
      }
      var maxBytes = 12 * 1024 * 1024;
      if (file.size > maxBytes) throw new Error("图片过大（最大 12MB）");
      var bytes = new Uint8Array(await file.arrayBuffer());
      var b64 = bytesToBase64(bytes);
      var d = await apiJson("/api/ui/theme-background", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ file_name: name, content_b64: b64, apply: true })
      });
      applyCfg((d && d.config) || d);
      applyHeroTheme((d && d.ui_theme) || uiThemeFromConfigPayload(d));
      setHeroThemeStatus("背景已更新：" + name);
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
      setHeroThemeStatus("已恢复默认背景");
    }
    async function uploadTerminalKeyFromFile(file){
      if (!file) return;
      var maxBytes = 1024 * 1024;
      if (file.size > maxBytes) {
        throw new Error("key 文件过大（最大 1MB）");
      }
      var fileName = String(file.name || "").trim();
      if (!fileName) {
        throw new Error("无法读取 key 文件名");
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
      setStatus("terminalStatus", "key 文件已上传：" + String(d.file_name || fileName));
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
          ? "密码模式不会保存密码，点击后在终端中手工输入。"
          : (keyFile ? ("使用配置目录 key：" + keyFile) : "推荐使用 key 模式；确保目标主机已授权你的公钥。")
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
          preview.textContent = "未配置";
        }
      }
      if (webLink) {
        if (enabled && host) {
          webLink.href = "/terminal";
          webLink.textContent = "打开 /terminal";
        } else {
          webLink.href = "#terminal";
          webLink.textContent = "请先配置并启用 Terminal";
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
          : "Terminal（未启用）";
      }
    }
    function refreshTerminalPreview(){
      var draft = collectTerminalDraft();
      var m = buildTerminalMetaFromDraft(draft);
      byId("terminalTip").textContent = m.tip;
      byId("terminalPreviewCmd").textContent = m.command || "未配置";
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
        empty.textContent = "(当前目录无子目录)";
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
            setStatus("httpStatus", "加载失败：" + err.message, true);
          });
          setStatus("httpStatus", "已选择默认目录：" + dir);
        });
        wrap.appendChild(btn);
      });
    }
    function renderHttpScanResult(d){
      var el = byId("httpScanResult");
      if (!el) return;
      if (!d) { el.textContent = ""; return; }
      var parts = [];
      parts.push("路径：" + String(d.path || "-"));
      if (!d.exists) {
        parts.push("不存在");
      } else if (!d.is_dir) {
        parts.push("不是目录");
      } else {
        var perm = (d.can_read ? "r" : "-") + (d.can_write ? "w" : "-") + (d.can_exec ? "x" : "-");
        parts.push("权限(" + perm + ")");
        if (d.can_list) {
          parts.push("子目录 " + String(d.child_dir_count || 0) + " · 文件 " + String(d.child_file_count || 0) + (d.truncated ? "（已截断）" : ""));
        } else {
          parts.push("无法列目录");
        }
        if (d.fs_total_human && d.fs_avail_human) {
          parts.push("可用 " + d.fs_avail_human + " / 总 " + d.fs_total_human);
        }
      }
      if (d.error) parts.push("提示：" + String(d.error));
      if (Array.isArray(d.sample_dirs) && d.sample_dirs.length) {
        parts.push("示例子目录：" + d.sample_dirs.slice(0, 6).join(", "));
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
        if (d && d.ok) setStatus("httpStatus", "路径验证通过，可用于 HTTP 根目录");
        else setStatus("httpStatus", "路径验证失败：" + String((d && d.error) || "不可访问"), true);
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
          setStatus("httpStatus", "默认目录不可访问，已回退到根目录。", true);
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
      if (!silent) setStatus("httpStatus", "已加载目录：" + effectiveRoot + " / " + cur);
    }
    function applyCfg(data){
      var c = data || {};
      cfg.web_port = parseWebPort(c.web_port, cfg.web_port || 1288);
      cfg.modules = c.modules || cfg.modules;
      cfg.qbt = c.qbt || cfg.qbt;
      cfg.http_service = c.http_service || cfg.http_service;
      cfg.ui = c.ui || cfg.ui;
      cfg.terminal = c.terminal || cfg.terminal;
      if (byId("webPortInput")) byId("webPortInput").value = String(cfg.web_port);
      byId("modQbt").checked = cfg.modules.qbt !== false;
      byId("modDdns").checked = cfg.modules.ddns !== false;
      byId("modShareclip").checked = cfg.modules.shareclip !== false;
      byId("modHttp").checked = cfg.modules.http !== false;
      byId("qbtMonitorEnabled").checked = cfg.qbt.monitor_enabled !== false;
      byId("httpRootDir").value = normalizeRootInput((cfg.http_service || {}).root_dir || "/srv/Storage");
      byId("httpDefaultDir").value = normalizeDirInput((cfg.http_service || {}).default_dir || ".");
      applySourceIpPoolsInputs((cfg.http_service || {}).source_ip_pools || {});
      applySourceIpPoolSourceInput((cfg.http_service || {}).source_ip_pool_source || "");
      renderSourceIpPoolMeta("当前来源：" + normalizeSourceIpPoolSource((cfg.http_service || {}).source_ip_pool_source || ""));
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
      updateWebPortHint();
    }
    async function loadCfg(){
      var d = await apiJson("/api/app-config");
      applyCfg(d.config || d);
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
        var line = (q.active_state === "active" ? "运行中" : "未运行") + " | " + (q.unit || "-");
        if (q.detail) line += " | " + q.detail;
        byId("qbtRuntimeStatus").textContent = trRaw(line);
      } catch (err) {
        byId("qbtRuntimeStatus").textContent = trRaw("加载失败:") + " " + err.message;
      }
    }
    function switchTab(name){
      var tab = (name || "").trim() || "general";
      var valid = { general:1, http:1, qbt:1, terminal:1, ddns:1 };
      if (!valid[tab]) tab = "general";
      var btns = Array.prototype.slice.call(document.querySelectorAll(".cfg-tab"));
      for (var i = 0; i < btns.length; i++) {
        var b = btns[i];
        b.classList.toggle("active", b.getAttribute("data-tab") === tab);
      }
      ["general","http","qbt","terminal","ddns"].forEach(function(t){
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
          setHeroThemeStatus("切换失败：" + err.message, true);
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
          setHeroThemeStatus("上传失败：" + err.message, true);
        }
      });
    }
    if (byId("cfgThemeBgClearBtn")) {
      byId("cfgThemeBgClearBtn").addEventListener("click", async function(){
        try {
          await resetHeroToDefault();
        } catch (err) {
          setHeroThemeStatus("恢复失败：" + err.message, true);
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
          setStatus("generalStatus", "综合配置已保存：" + actionSummary.text, actionSummary.has_error);
        } else if (payload.modules.http === false) {
          setStatus("generalStatus", d.http_disconnect_triggered ? "综合配置已保存：HTTP 模块已关闭，已中断本程序上传连接并关闭上传。" : "综合配置已保存：HTTP 模块已关闭，上传已禁用。", false);
        } else {
          setStatus("generalStatus", "综合配置已保存", false);
        }
      } catch (err) {
        setStatus("generalStatus", "保存失败：" + err.message, true);
      }
    });

    byId("restartCfgServiceBtn").addEventListener("click", async function(){
      if (!window.confirm(trRaw("确认重启服务？端口等变更将在重启后生效。"))) return;
      try {
        setStatus("generalStatus", "正在发送重启指令...");
        var d = await apiJson("/api/control/restart", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ reason: "config-page-restart" })
        });
        if (d && d.queued === false) {
          setStatus("generalStatus", "重启任务未入队，请稍后重试。", true);
          return;
        }
        setStatus("generalStatus", "已发送重启命令，端口等变更将在重启后生效。");
      } catch (err) {
        setStatus("generalStatus", "重启失败：" + err.message, true);
      }
    });

    if (byId("runUpgradeBtn")) {
      byId("runUpgradeBtn").addEventListener("click", async function(){
        try {
          await runAutoUpgrade();
        } catch (err) {
          setStatus("upgradeStatus", "启动升级失败：" + err.message, true);
        }
      });
    }
    if (byId("refreshUpgradeStatusBtn")) {
      byId("refreshUpgradeStatusBtn").addEventListener("click", async function(){
        try {
          await loadUpgradeStatus(false);
        } catch (err) {
          setStatus("upgradeStatus", "刷新失败：" + err.message, true);
        }
      });
    }
    if (byId("upgradeRepoInput")) {
      byId("upgradeRepoInput").addEventListener("blur", function(){
        this.value = normalizeUpgradeRepoInput(this.value);
      });
    }
    if (byId("upgradeTagInput")) {
      byId("upgradeTagInput").addEventListener("blur", function(){
        this.value = normalizeUpgradeTagInput(this.value);
      });
      byId("upgradeTagInput").addEventListener("input", function(){
        renderUpgradeStatus(upgradeState);
      });
    }
    if (byId("upgradeBranchSelect")) {
      byId("upgradeBranchSelect").addEventListener("change", function(){
        renderUpgradeStatus(upgradeState);
      });
    }

    byId("saveHttpBtn").addEventListener("click", async function(){
      try {
        var webPort = parseWebPort(byId("webPortInput") ? byId("webPortInput").value : cfg.web_port, cfg.web_port || 1288);
        var scan = await scanHttpRootPath(true);
        if (!scan.ok) throw new Error(String(scan.error || "HTTP 根目录不可访问"));
        var root = normalizeRootInput((scan && scan.path) || byId("httpRootDir").value || "/");
        var target = normalizeDirInput(byId("httpDefaultDir").value);
        var pools = collectSourceIpPoolsDraft();
        var source = normalizeSourceIpPoolSource(byId("httpPoolSource").value);
        await apiJson("/api/directories?stats=0&root_dir=" + encodeURIComponent(root) + "&dir=" + encodeURIComponent(target));
        var d = await apiJson("/api/app-config", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ web_port: webPort, http_service: { root_dir: root, default_dir: target, source_ip_pools: pools, source_ip_pool_source: source } })
        });
        applyCfg(d.config || d);
        byId("httpBrowseDir").value = target;
        await loadHttpDirBrowser(target, true);
        var restartMsg = (d && d.web_port_restart_required)
          ? (" 程序端口将在重启后切换为 " + String(parseWebPort(((d.config || {}).web_port), webPort)) + "。")
          : "";
        setStatus("httpStatus", "HTTP 配置已保存" + restartMsg);
      } catch (err) {
        setStatus("httpStatus", "保存失败：" + err.message, true);
      }
    });

    byId("httpScanRootBtn").addEventListener("click", async function(){
      try {
        var d = await scanHttpRootPath(false);
        if (d && d.ok) {
          await loadHttpDirBrowser(".", true);
        }
      } catch (err) {
        setStatus("httpStatus", "路径验证失败：" + err.message, true);
      }
    });

    byId("httpBrowseLoadBtn").addEventListener("click", async function(){
      try {
        await loadHttpDirBrowser(byId("httpBrowseDir").value, false);
      } catch (err) {
        setStatus("httpStatus", "目录加载失败：" + err.message, true);
      }
    });

    byId("httpBrowseParentBtn").addEventListener("click", async function(){
      try {
        var p = parentDirOf(byId("httpBrowseDir").value);
        byId("httpBrowseDir").value = p;
        await loadHttpDirBrowser(p, false);
      } catch (err) {
        setStatus("httpStatus", "目录加载失败：" + err.message, true);
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
          setStatus("httpStatus", "来源同步失败：" + err.message, true);
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

    byId("saveQbtBtn").addEventListener("click", async function(){
      try {
        var payload = { qbt: { monitor_enabled: byId("qbtMonitorEnabled").checked } };
        var d = await apiJson("/api/app-config", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        applyCfg(d.config || d);
        setStatus("qbtStatus", "qB 配置已保存");
        await loadQbtRuntime();
      } catch (err) {
        setStatus("qbtStatus", "保存失败：" + err.message, true);
      }
    });

    byId("qbtOptimizeBtn").addEventListener("click", async function(){
      if (!window.confirm("将注释当前相关配置并写入优化参数，继续吗？")) return;
      try {
        setStatus("qbtStatus", "正在优化 qB 配置...");
        var d = await apiJson("/api/qbt/optimize-config", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: "{}"
        });
        setStatus("qbtStatus", (d && d.message) || "qB 配置优化完成");
        await loadQbtRuntime();
      } catch (err) {
        setStatus("qbtStatus", "优化失败：" + err.message, true);
      }
    });

    byId("qbtFixPermBtn").addEventListener("click", async function(){
      try {
        setStatus("qbtStatus", "正在修复 qB 配置与权限...");
        var d = await apiJson("/api/qbt/fix-monitor", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: "{}"
        });
        setStatus("qbtStatus", (d && d.message) || "qB 修复完成");
        await loadQbtRuntime();
      } catch (err) {
        setStatus("qbtStatus", "修复失败：" + err.message, true);
      }
    });

    byId("qbtRestartSvcBtn").addEventListener("click", async function(){
      try {
        await apiJson("/api/control/service", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ service: "qbt", action: "restart" })
        });
        setStatus("qbtStatus", "qB 服务已重启");
        await loadQbtRuntime();
      } catch (err) {
        setStatus("qbtStatus", "重启失败：" + err.message, true);
      }
    });

    byId("qbtQuitBtn").addEventListener("click", async function(){
      if (!window.confirm("确定要执行 qB 退出吗？")) return;
      try {
        await apiJson("/api/control/service", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ service: "qbt", action: "quit" })
        });
        setStatus("qbtStatus", "已发送 qB 退出指令");
        await loadQbtRuntime();
      } catch (err) {
        setStatus("qbtStatus", "退出失败：" + err.message, true);
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
        setStatus("terminalStatus", "key 列表已刷新");
      } catch (err) {
        setStatus("terminalStatus", "刷新失败：" + err.message, true);
      }
    });

    byId("termKeyUploadInput").addEventListener("change", async function(){
      var file = this.files && this.files[0];
      this.value = "";
      if (!file) return;
      try {
        setStatus("terminalStatus", "正在上传 key 文件...");
        await uploadTerminalKeyFromFile(file);
      } catch (err) {
        setStatus("terminalStatus", "上传失败：" + err.message, true);
      }
    });

    byId("saveTerminalBtn").addEventListener("click", async function(){
      try {
        var draft = collectTerminalDraft();
        if (draft.enabled && !draft.host) {
          throw new Error("启用 Terminal 时 Host 不能为空");
        }
        var d = await apiJson("/api/app-config", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ terminal: draft })
        });
        applyCfg(d.config || d);
        setStatus("terminalStatus", "Terminal 配置已保存");
      } catch (err) {
        setStatus("terminalStatus", "保存失败：" + err.message, true);
      }
    });

    byId("copyTerminalCmdBtn").addEventListener("click", async function(){
      var m = buildTerminalMetaFromDraft(collectTerminalDraft());
      if (!m.command) {
        setStatus("terminalStatus", "请先填写 Host/User 等连接信息", true);
        return;
      }
      var ok = await copyTextSmart(m.command);
      if (ok) {
        setStatus("terminalStatus", "SSH 命令已复制");
      } else {
        setStatus("terminalStatus", "复制失败，请手工复制预览命令", true);
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
      .then(function(){ return Promise.all([loadBaseInfo(), scanHttpRootPath(true), loadHttpDirBrowser(byId("httpBrowseDir").value, true), loadQbtRuntime(), loadUpgradeStatus(true)]); })
      .catch(function(err){ setStatus("generalStatus", "配置加载失败：" + err.message, true); });
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
      if (x === "aurora" || x === "sunset" || x === "frost" || x === "afterclaw_clouds" || x === "custom") return x;
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
      if (!r.ok) throw new Error((d && d.error) || ("请求失败 " + r.status));
      return d;
    }
    function applyUiTheme(uiTheme){
      var t = uiTheme || {};
      var preset = normalizeHeroPreset(t.hero_preset || "default");
      var customUrl = String(t.hero_custom_bg_url || "").trim();
      var effective = (preset === "custom" && !customUrl) ? "default" : preset;
      document.documentElement.setAttribute("data-hero-preset", effective);
      try { localStorage.setItem("fc-hero-preset", effective); } catch (e) {}
      if (customUrl) {
        var safeUrl = customUrl.replace(/"/g, '\\"');
        document.documentElement.style.setProperty("--hero-custom-url", 'url("' + safeUrl + '")');
      } else {
        document.documentElement.style.removeProperty("--hero-custom-url");
      }
      var labels = { default: "默认", aurora: "极光", sunset: "落日", frost: "冰川", afterclaw_clouds: "云海暮光", custom: "自定义图片" };
      var meta = byId("cfgThemeMeta");
      if (meta) {
        meta.textContent = "当前背景：" + (labels[effective] || "默认");
      }
      Array.prototype.slice.call(document.querySelectorAll('#panel-general .theme-preset-btn')).forEach(function(btn){
        var p = normalizeHeroPreset(btn.getAttribute("data-hero-preset"));
        btn.classList.toggle("active", p === effective);
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
      var labels = { default: "默认", aurora: "极光", sunset: "落日", frost: "冰川", afterclaw_clouds: "云海暮光", custom: "自定义图片" };
      setStatus("已切换背景：" + (labels[p] || "默认"), false);
    }
    async function uploadThemeImage(file){
      if (!file) throw new Error("请先选择一张本地图片");
      var name = String(file.name || "").trim();
      if (!/\.(png|jpe?g|webp|gif|avif)$/i.test(name)) {
        throw new Error("仅支持 PNG/JPG/WEBP/GIF/AVIF");
      }
      var maxBytes = 12 * 1024 * 1024;
      if (file.size > maxBytes) throw new Error("图片过大（最大 12MB）");
      var bytes = new Uint8Array(await file.arrayBuffer());
      var b64 = bytesToBase64(bytes);
      var d = await apiJson("/api/ui/theme-background", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ file_name: name, content_b64: b64, apply: true })
      });
      applyUiTheme((d && d.ui_theme) || {});
      setStatus("背景已更新：" + name, false);
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
      setStatus("已恢复默认背景", false);
    }
    Array.prototype.slice.call(document.querySelectorAll('#panel-general .theme-preset-btn')).forEach(function(btn){
      btn.addEventListener("click", async function(){
        try {
          await setPreset(btn.getAttribute("data-hero-preset"));
        } catch (err) {
          setStatus("切换失败：" + ((err && err.message) || err), true);
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
          setStatus("上传失败：" + ((err && err.message) || err), true);
        }
      });
    }
    var clearBtn = byId("cfgThemeBgClearBtn");
    if (clearBtn) {
      clearBtn.addEventListener("click", async function(){
        try {
          await resetThemeDefault();
        } catch (err) {
          setStatus("恢复失败：" + ((err && err.message) || err), true);
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
      return { text: msgs.join("；"), has_error: hasErr };
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
      if (!r.ok) throw new Error((d && d.error) || ("请求失败 " + r.status));
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
      if (byId("webPortHint")) byId("webPortHint").textContent = "当前保存端口：" + String(wp) + "（修改后需重启生效）";
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
        setStatus("generalStatus", "综合配置已保存：" + actionSummary.text, actionSummary.has_error);
      } else if (payload.modules.http === false) {
        setStatus("generalStatus", d.http_disconnect_triggered ? "综合配置已保存：HTTP 模块已关闭，已中断本程序上传连接并关闭上传。" : "综合配置已保存：HTTP 模块已关闭，上传已禁用。", false);
      } else {
        setStatus("generalStatus", "综合配置已保存", false);
      }
    }

    Array.prototype.slice.call(document.querySelectorAll(".cfg-tab")).forEach(function(btn){
      btn.addEventListener("click", function(){ switchTab(btn.getAttribute("data-tab")); });
    });
    if (byId("saveModulesBtn")) {
      byId("saveModulesBtn").addEventListener("click", function(){
        saveModuleConfig().catch(function(err){
          setStatus("generalStatus", "保存失败：" + ((err && err.message) || err), true);
        });
      });
    }
    if (byId("restartCfgServiceBtn")) {
      byId("restartCfgServiceBtn").addEventListener("click", function(){
        if (!window.confirm(trRaw("确认重启服务？端口等变更将在重启后生效。"))) return;
        apiJson("/api/control/restart", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ reason: "config-page-restart" })
        }).then(function(d){
          if (d && d.queued === false) {
            setStatus("generalStatus", "重启任务未入队，请稍后重试。", true);
            return;
          }
          setStatus("generalStatus", "已发送重启命令，端口等变更将在重启后生效。", false);
        }).catch(function(err){
          setStatus("generalStatus", "重启失败：" + ((err && err.message) || err), true);
        });
      });
    }
    switchTab((window.location.hash || "").replace("#", "") || "general");
    loadModuleConfig().catch(function(err){
      setStatus("generalStatus", "配置加载失败：" + ((err && err.message) || err), true);
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
          <a href="/config#terminal" class="gear-btn" title="Config / Terminal" aria-label="Config / Terminal">&#9881;</a>
          <button type="button" id="themeToggleBtn" class="secondary">主题</button>
          <select id="langSelect" class="lang-select" title="Language">
            <option value="en">English</option>
            <option value="zh-CN">简体中文</option>
            <option value="zh-TW">繁體中文</option>
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
        <button type="button" id="connectBtn">连接</button>
        <button type="button" id="disconnectBtn" class="secondary">断开</button>
        <button type="button" id="copyCmdBtn" class="secondary">复制 SSH 命令</button>
        <button type="button" id="clearBtn" class="secondary">清屏</button>
      </div>
      <div id="termStatus" class="status-bar muted">准备就绪</div>
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
      var b = document.getElementById("themeToggleBtn");
      if (b) b.textContent = t === "dark" ? "浅色模式" : "深色模式";
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
      if (!r.ok) throw new Error((d && d.error) || ("请求失败 " + r.status));
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
        setStatus("未配置 Terminal Host，请到 Config -> Terminal 设置。", true);
      } else {
        setStatus("准备连接到 " + display);
      }
    }
    function ensureTerminalReady(){
      if (term) return true;
      if (!window.Terminal || !window.FitAddon) {
        setStatus("xterm.js 资源加载失败，请检查 /vendor/xterm 资源后刷新。", true);
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
        setStatus("读取失败：" + err.message, true);
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
        setStatus("已连接，输入命令即可。");
        if (pollTimer) window.clearTimeout(pollTimer);
        pollTimer = window.setTimeout(readLoop, 30);
      } catch (err) {
        setStatus("连接失败：" + err.message, true);
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
      setStatus("会话已断开");
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
    transfers_lock = threading.Lock()
    http_cut_lock = threading.Lock()
    restart_queued = False
    upgrade_running = False
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
        ("百度网盘", ("百度", "baidu", "pan.baidu", "xpan", "netdisk", "baiduyun", "yun.baidu", "pcs")),
        ("光鸭网盘", ("光鸭", "guangya")),
        ("阿里云盘", ("阿里", "aliyun", "alipan", "阿里云盘")),
    )
    process_source_rules = (
        ("百度网盘", ("baidunetdisk", "netdisk", "xpan")),
        ("光鸭网盘", ("guangya",)),
        ("阿里云盘", ("aliyundrive", "alipan", "aliyun")),
    )
    active_transfers = {}
    transfer_recent_ttl_sec = 8.0
    process_net_lock = threading.Lock()
    process_net_state = {"last_ts": 0.0, "socket_counters": {}}
    qbt_candidates = [
        DEFAULT_QBT_SERVICE,
        "qbittorrent-nox",
        "qbt-nox",
    ]
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

    def _dispatch_shareclip_flask(self, parsed, command: str, send_body: bool) -> bool:
        path = parsed.path or "/"
        target_path = "/config" if path == "/clip-config" else path
        qs = parse_qs(parsed.query)
        query_id_pub = qs.get("id", [""])[0] == "pub"
        if not shareclip_route_match(path, query_id_pub):
            return False
        if not self._shareclip_module_enabled():
            self._error("ShareClip 模块已关闭", status=HTTPStatus.FORBIDDEN)
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
            self._error(f"ShareClip 处理失败：{exc}", status=HTTPStatus.BAD_GATEWAY)
            return True

    def _dispatch_ddnsgo_proxy(self, parsed, command: str, send_body: bool) -> bool:
        path = parsed.path or "/"
        if not ddnsgo_route_match(path):
            return False
        if not self._ddns_module_enabled():
            self._error("DDNS 模块已关闭", status=HTTPStatus.FORBIDDEN)
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
                self._error("ddns-go base_url 无效，请在 DDNS 设置中修正", status=HTTPStatus.BAD_REQUEST)
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
            self._error(f"ddns-go 代理失败：{exc}", status=HTTPStatus.BAD_GATEWAY)
            return True

    def _client_ip(self) -> str:
        return (self.client_address[0] or "").strip()

    def _http_source_ip_pools(self, app_cfg: dict | None = None) -> dict:
        cfg = app_cfg if isinstance(app_cfg, dict) else load_app_config(_APP_ROOT_DIR)
        http_cfg = (cfg.get("http_service") or {}) if isinstance(cfg, dict) else {}
        return _normalize_source_ip_pools(http_cfg.get("source_ip_pools"))

    @classmethod
    def _infer_source_by_process_name(cls, process_name: str) -> str:
        pname = str(process_name or "").strip().lower()
        if not pname:
            return ""
        for source, keywords in cls.process_source_rules:
            if any(str(k).lower() in pname for k in keywords):
                return str(source)
        return ""

    @classmethod
    def _collect_process_socket_counters(cls) -> dict:
        try:
            proc = subprocess.run(
                ["ss", "-tinpH"],
                capture_output=True,
                text=True,
                timeout=2.0,
                check=False,
            )
            if proc.returncode != 0:
                return {}
            lines = proc.stdout.splitlines()
        except Exception:
            return {}

        out = {}
        i = 0
        while i < len(lines):
            header = str(lines[i] or "")
            if not header.strip():
                i += 1
                continue
            detail = ""
            if i + 1 < len(lines) and lines[i + 1].startswith("\t"):
                detail = str(lines[i + 1] or "")
                i += 2
            else:
                i += 1

            user_matches = re.findall(r'\("([^"]+)",pid=(\d+),fd=(\d+)\)', header)
            if not user_matches:
                continue
            endpoint_match = re.match(r"^\S+\s+\d+\s+\d+\s+(\S+)\s+(\S+)", header)
            if endpoint_match:
                local_ep, peer_ep = endpoint_match.group(1), endpoint_match.group(2)
            else:
                local_ep, peer_ep = "-", "-"
            state = (header.split(None, 1)[0] or "").strip().upper()

            combo = f"{header} {detail}"
            acked_match = re.search(r"bytes_acked:(\d+)", combo)
            recv_match = re.search(r"bytes_received:(\d+)", combo)
            acked = int(acked_match.group(1)) if acked_match else 0
            received = int(recv_match.group(1)) if recv_match else 0

            for process_name, pid, fd in user_matches:
                source = cls._infer_source_by_process_name(process_name)
                if not source:
                    continue
                socket_key = f"{source}|{pid}|{local_ep}|{peer_ep}"
                out[socket_key] = {
                    "source": source,
                    "pid": int(pid),
                    "process": str(process_name),
                    "state": state,
                    "acked": acked,
                    "received": received,
                }
        return out

    @classmethod
    def _process_source_speed_snapshot(cls) -> dict:
        now = time.time()
        current = cls._collect_process_socket_counters()
        source_speed = {}
        for row in current.values():
            source = str((row or {}).get("source", "") or "").strip()
            if not source:
                continue
            agg = source_speed.setdefault(
                source,
                {
                    "source": source,
                    "count": 0,
                    "conn_count": 0,
                    "active_count": 0,
                    "download_mibps": 0.0,
                    "upload_mibps": 0.0,
                },
            )
            if str((row or {}).get("state", "") or "").upper() == "ESTAB":
                agg["conn_count"] = int(agg.get("conn_count", 0)) + 1
        with cls.process_net_lock:
            last_ts = float(cls.process_net_state.get("last_ts", 0.0) or 0.0)
            last = cls.process_net_state.get("socket_counters") or {}
            cls.process_net_state["last_ts"] = now
            cls.process_net_state["socket_counters"] = current

        if not current or last_ts <= 0 or now <= last_ts:
            return source_speed
        delta_sec = now - last_ts
        if delta_sec <= 0:
            return source_speed
        for socket_key, row in current.items():
            if str((row or {}).get("state", "") or "").upper() != "ESTAB":
                continue
            prev = last.get(socket_key) if isinstance(last, dict) else None
            if not isinstance(prev, dict):
                continue
            acked_now = int(row.get("acked", 0) or 0)
            recv_now = int(row.get("received", 0) or 0)
            acked_prev = int(prev.get("acked", 0) or 0)
            recv_prev = int(prev.get("received", 0) or 0)
            delta_send = max(acked_now - acked_prev, 0)
            delta_recv = max(recv_now - recv_prev, 0)
            if delta_send <= 0 and delta_recv <= 0:
                continue
            source = str(row.get("source", "") or "").strip()
            if not source:
                continue
            agg = source_speed[source]
            # 下载=进程接收；上传=进程发送。
            agg["download_mibps"] = float(agg.get("download_mibps", 0.0)) + (
                delta_recv / 1024.0 / 1024.0 / delta_sec
            )
            agg["upload_mibps"] = float(agg.get("upload_mibps", 0.0)) + (
                delta_send / 1024.0 / 1024.0 / delta_sec
            )
            agg["active_count"] = int(agg.get("active_count", 0)) + 1
        for agg in source_speed.values():
            agg["count"] = int(agg.get("active_count", 0) or 0)
        return source_speed

    def _infer_transfer_source(
        self,
        relative_path: str,
        filename: str = "",
        user_agent: str = "",
        referer: str = "",
        client_ip: str = "",
        source_ip_pools: dict | None = None,
    ) -> str:
        ip_source = _match_source_label_by_ip(client_ip, source_ip_pools)
        if ip_source:
            return ip_source
        rel = str(relative_path or "")
        name = str(filename or "")
        ua = str(user_agent or "")
        ref = str(referer or "")
        merged = f"{ua} {ref} {rel}/{name}".lower()
        for source, keywords in self.transfer_source_rules:
            if any(str(k).lower() in merged for k in keywords):
                return str(source)
        return "HTTP直连"

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
        self._error("仅允许局域网访问该页面/API", status=HTTPStatus.FORBIDDEN)
        return False

    def _send_json(self, data: dict, status: int = HTTPStatus.OK):
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _send_html(self, html: str):
        payload = html.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        # 配置/中控页包含内联脚本，禁用缓存可避免前端逻辑更新后仍命中旧页面。
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
            self._error("静态资源路径非法", status=HTTPStatus.FORBIDDEN)
            return True
        except Exception as exc:
            self._error(f"静态资源读取失败：{exc}", status=HTTPStatus.INTERNAL_SERVER_ERROR)
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
            raise ValueError(f"HTTP 根目录不存在或不可访问: {root}")
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
    def _service_action(cls, unit: str, action: str):
        if not unit:
            return False, "服务未配置"
        if action not in {"start", "stop", "restart"}:
            return False, "不支持的动作"
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
        info = cls._resolve_existing_unit(cls.qbt_candidates)
        if info.get("load_state") == "not-found":
            info = cls._discover_unit_by_keywords(["qbit", "qbittorrent"]) or info
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

            tmp = conf_path.parent / f"{conf_path.name}.tmp.codex"
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
            msg = "qB 监控权限修复完成"
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
    def _qbt_optimize_config(cls) -> tuple[bool, str, dict]:
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
            raw = ""
            if conf_path.exists():
                raw = conf_path.read_text(encoding="utf-8", errors="replace")

            marker_start = "# --- fcc-qb-optimize:start ---"
            marker_end = "# --- fcc-qb-optimize:end ---"
            raw_lines = raw.splitlines()
            start_idx = -1
            end_idx = -1
            for idx, line in enumerate(raw_lines):
                if line.strip() == marker_start:
                    start_idx = idx
                    break
            if start_idx >= 0:
                for idx in range(start_idx + 1, len(raw_lines)):
                    if raw_lines[idx].strip() == marker_end:
                        end_idx = idx
                        break
            if start_idx >= 0 and end_idx > start_idx:
                cleaned_lines = raw_lines[:start_idx] + raw_lines[end_idx + 1 :]
            else:
                cleaned_lines = raw_lines
            cleaned_raw = "\n".join(cleaned_lines).rstrip() + ("\n" if cleaned_lines else "")

            parser = configparser.ConfigParser(interpolation=None)
            parser.optionxform = str
            if cleaned_raw.strip():
                parser.read_string(cleaned_raw)
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
                "Connection\\GlobalDLLimit": "0",
                "Connection\\GlobalUPLimit": "0",
                "Connection\\GlobalDLLimitAlt": "0",
                "Connection\\GlobalUPLimitAlt": "0",
            }
            desired_keys = set(desired.keys())
            old_lines = cleaned_raw.splitlines()
            if not old_lines:
                old_lines = ["[Preferences]"]
            rewritten_lines = []
            in_preferences = False
            preferences_exists = False
            commented_keys = set()

            for line in old_lines:
                stripped = line.strip()
                if stripped.startswith("[") and stripped.endswith("]"):
                    in_preferences = stripped.lower() == "[preferences]"
                    if in_preferences:
                        preferences_exists = True
                    rewritten_lines.append(line)
                    continue
                if in_preferences and stripped and not stripped.startswith(("#", ";")):
                    key_part = line.split("=", 1)[0] if "=" in line else ""
                    key = key_part.strip()
                    if key in desired_keys:
                        rewritten_lines.append(f"# {line}")
                        commented_keys.add(key)
                        continue
                rewritten_lines.append(line)

            if not preferences_exists:
                if rewritten_lines and rewritten_lines[-1].strip():
                    rewritten_lines.append("")
                rewritten_lines.append("[Preferences]")

            pref_start = None
            pref_end = len(rewritten_lines)
            for idx, line in enumerate(rewritten_lines):
                if line.strip().lower() == "[preferences]":
                    pref_start = idx
                    break
            if pref_start is None:
                raise RuntimeError("写入失败：未找到 [Preferences] 分组")
            for idx in range(pref_start + 1, len(rewritten_lines)):
                stripped = rewritten_lines[idx].strip()
                if stripped.startswith("[") and stripped.endswith("]"):
                    pref_end = idx
                    break

            optimize_block = [
                "",
                marker_start,
                "# managed by afterclaw",
            ]
            optimize_block.extend([f"{k}={v}" for k, v in desired.items()])
            optimize_block.extend([marker_end, ""])
            merged = (
                rewritten_lines[:pref_end] + optimize_block + rewritten_lines[pref_end:]
            )
            payload = "\n".join(merged).rstrip() + "\n"

            if conf_path.exists():
                backup = conf_path.parent / f"{conf_path.name}.bak.{int(time.time())}"
                shutil.copy2(conf_path, backup)
                backup_path = str(backup)

            tmp = conf_path.parent / f"{conf_path.name}.tmp.codex"
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
            msg = "qB 配置优化完成"
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
        base = (DEFAULT_QBT_API_URL or "").strip()
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
            if not (DEFAULT_QBT_API_USERNAME and DEFAULT_QBT_API_PASSWORD):
                raise RuntimeError(
                    "WebUI 需要登录，请配置 QBT_API_USERNAME / QBT_API_PASSWORD"
                ) from e

        login_url = cls._qbt_api_join(base, "/api/v2/auth/login")
        login_body = urlencode(
            {
                "username": DEFAULT_QBT_API_USERNAME,
                "password": DEFAULT_QBT_API_PASSWORD,
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
            return True, "已发送 qB 退出指令"
        except urllib.error.HTTPError as e:
            if e.code not in (401, 403):
                return False, f"WebUI HTTP {e.code}"
            if not (DEFAULT_QBT_API_USERNAME and DEFAULT_QBT_API_PASSWORD):
                return False, "WebUI 需要登录，请配置 QBT_API_USERNAME / QBT_API_PASSWORD"
        except urllib.error.URLError as e:
            return False, f"WebUI 不可达: {e}"
        except Exception as e:
            return False, str(e)

        login_url = cls._qbt_api_join(base, "/api/v2/auth/login")
        login_body = urlencode(
            {
                "username": DEFAULT_QBT_API_USERNAME,
                "password": DEFAULT_QBT_API_PASSWORD,
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
            return True, "已发送 qB 退出指令"
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
                f" | 做种 {seeding} · 下载 {downloading} · 活跃 {active} · 总计 {len(torrents)}"
            )
            if peers > 0:
                detail += f" · 连接 {peers}"
            if dht_nodes > 0:
                detail += f" · DHT {dht_nodes}"

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
    def _control_status_payload(cls):
        app_cfg = load_app_config(_APP_ROOT_DIR)
        qbt_cfg = (app_cfg or {}).get("qbt") or {}
        qbt_monitor_enabled = bool(qbt_cfg.get("monitor_enabled", True))
        http_module_on = cls._http_module_enabled()
        qbt = cls._resolve_existing_unit(cls.qbt_candidates)
        if qbt.get("load_state") == "not-found":
            qbt = cls._discover_unit_by_keywords(["qbit", "qbittorrent"]) or qbt
        if qbt.get("active_state") == "active" and qbt_monitor_enabled:
            qbt_stats = cls._qbt_stats_snapshot()
            if qbt_stats.get("detail"):
                qbt["detail"] = qbt_stats.get("detail")
            if qbt_stats.get("ok"):
                qbt["stats"] = qbt_stats
        elif qbt.get("active_state") == "active" and not qbt_monitor_enabled:
            qbt["detail"] = "qB 监控已关闭（可在 Config -> qB 中开启）"
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
            self_svc["detail"] = "HTTP 模块已关闭（仅本程序 /http-files 上传节点被禁用）"
        return {
            "system": cls._system_status(),
            "qbt": qbt,
            "ddns": ddns_svc,
            "self": self_svc,
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
            recent_ttl = float(getattr(self, "transfer_recent_ttl_sec", 30.0) or 30.0)
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
                    if stored_source and stored_source != "HTTP直连"
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
        # 合并“非 1288 通道”的网盘 App 进程流量（如 baidunetdisk）。
        process_speeds = self._process_source_speed_snapshot()
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
            return False, "当前仅支持 Linux 自动升级"
        if not shutil.which("systemctl"):
            return False, "当前环境未检测到 systemctl，暂不支持自动升级"
        try:
            if os.geteuid() != 0:
                return False, "当前服务无 root 权限，无法执行 install.sh"
        except Exception:
            return False, "无法确认当前权限，暂不支持自动升级"
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
            status["message"] = "升级任务触发了服务重启，请手动确认当前版本。"
            status["finished_at"] = _utc_now_iso()
            _write_upgrade_status(status, _APP_ROOT_DIR)
        status["supported"] = bool(ok)
        status["support_reason"] = str(reason or "")
        status["current_version"] = APP_VERSION_TEXT
        status["current_branch"] = APP_BRANCH
        try:
            status["repo"] = _normalize_upgrade_repo(
                status.get("repo"), DEFAULT_UPGRADE_GITHUB_REPO
            )
        except Exception:
            status["repo"] = DEFAULT_UPGRADE_GITHUB_REPO
        return status

    @classmethod
    def _schedule_upgrade(cls, repo_raw, tag_raw, branch_raw="stable"):
        ok, reason = cls._upgrade_supported()
        if not ok:
            status = _write_upgrade_status(
                {
                    "supported": False,
                    "running": False,
                    "state": "error",
                    "message": "自动升级不可用",
                    "error": str(reason or "当前环境不支持"),
                },
                _APP_ROOT_DIR,
            )
            status["support_reason"] = str(reason or "")
            return False, status
        repo = _normalize_upgrade_repo(repo_raw, DEFAULT_UPGRADE_GITHUB_REPO)
        tag = _normalize_upgrade_tag(tag_raw)
        branch = str(branch_raw or "stable").strip().lower()
        if branch not in ("stable", "nightly"):
            branch = "stable"
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
                    "requested_tag": tag,
                    "target_tag": "",
                    "release_url": "",
                    "message": "升级任务已启动，正在拉取 Release 信息",
                    "error": "",
                    "started_at": _utc_now_iso(),
                    "finished_at": "",
                },
                _APP_ROOT_DIR,
            )

        def _worker():
            temp_dir = None
            try:
                release = _github_release_payload(repo, tag, branch)
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
                        "requested_tag": tag,
                        "target_tag": target_tag,
                        "release_url": release_url,
                        "message": f"已获取 Release {target_tag}，开始下载",
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
                        "message": f"已下载 {target_tag}，执行安装脚本中",
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
                        "requested_tag": tag,
                        "target_tag": target_tag,
                        "release_url": release_url,
                        "message": f"升级完成：{target_tag}",
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
                        "requested_tag": tag,
                        "message": "自动升级失败",
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
            raise FileNotFoundError("目录不存在")

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
            raise FileNotFoundError("目录不存在")

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
            info["error"] = f"扫描失败：{exc}"
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
            self._error("文件不存在", status=HTTPStatus.NOT_FOUND)
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
            self._error(f"文件读取失败：{exc}", status=HTTPStatus.INTERNAL_SERVER_ERROR)

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
                self._error("未找到资源", status=HTTPStatus.NOT_FOUND)
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
            self._error("未找到资源", status=HTTPStatus.NOT_FOUND)
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
            self._error("未找到资源", status=HTTPStatus.NOT_FOUND)
            return
        if parsed.path.startswith(f"/{THEME_ASSETS_DIR_NAME}/"):
            if not self._require_lan():
                return
            if self._send_static_asset(parsed.path.lstrip("/"), send_body=True):
                return
            self._error("未找到资源", status=HTTPStatus.NOT_FOUND)
            return
        if parsed.path.startswith("/vendor/"):
            if not self._require_lan():
                return
            if self._send_static_asset(parsed.path.lstrip("/"), send_body=True):
                return
            self._error("未找到资源", status=HTTPStatus.NOT_FOUND)
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
        if self._dispatch_ddnsgo_proxy(parsed, "GET", True):
            return
        if self._dispatch_shareclip_flask(parsed, "GET", True):
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
                self._error("DDNS 模块已关闭", status=HTTPStatus.FORBIDDEN)
                return
            self._send_html(build_ddns_settings_html())
            return

        if parsed.path.startswith("/http-files/"):
            if not self._downloads_effective_enabled():
                self._error("外网上传已关闭", status=HTTPStatus.FORBIDDEN)
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
                self._error(f"下载失败：{exc}", status=HTTPStatus.INTERNAL_SERVER_ERROR)
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

        if parsed.path == "/api/transfers":
            if not self._require_lan():
                return
            self._send_json(self._transfer_snapshot())
            return

        if parsed.path == "/api/control/status":
            if not self._require_lan():
                return
            self._send_json(self._control_status_payload())
            return

        if parsed.path == "/api/app-config":
            if not self._require_lan():
                return
            self._send_json({"config": load_app_config(_APP_ROOT_DIR)})
            return

        if parsed.path == "/api/upgrade/status":
            if not self._require_lan():
                return
            self._send_json(self._upgrade_status_payload())
            return

        if parsed.path == "/api/ddns/config":
            if not self._require_lan():
                return
            if not self._ddns_module_enabled():
                self._error("DDNS 模块已关闭", status=HTTPStatus.FORBIDDEN)
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
                self._error("缺少 path 参数", status=HTTPStatus.BAD_REQUEST)
                return
            try:
                info = self._http_path_scan(path_raw)
                self._send_json(info)
                return
            except Exception as exc:
                self._error(f"路径扫描失败：{exc}", status=HTTPStatus.INTERNAL_SERVER_ERROR)
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
                self._error(f"目录查询失败：{exc}", status=HTTPStatus.INTERNAL_SERVER_ERROR)
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
                    self._error("目录不存在", status=HTTPStatus.NOT_FOUND)
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
                self._error(f"扫描失败：{exc}", status=HTTPStatus.INTERNAL_SERVER_ERROR)
                return

        self._error("未找到资源", status=HTTPStatus.NOT_FOUND)

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
                self._error("未找到资源", status=HTTPStatus.NOT_FOUND)
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
            self._error("未找到资源", status=HTTPStatus.NOT_FOUND)
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
            self._error("未找到资源", status=HTTPStatus.NOT_FOUND)
            return
        if parsed.path.startswith(f"/{THEME_ASSETS_DIR_NAME}/"):
            if not self._require_lan():
                return
            if self._send_static_asset(parsed.path.lstrip("/"), send_body=False):
                return
            self._error("未找到资源", status=HTTPStatus.NOT_FOUND)
            return
        if parsed.path.startswith("/vendor/"):
            if not self._require_lan():
                return
            if self._send_static_asset(parsed.path.lstrip("/"), send_body=False):
                return
            self._error("未找到资源", status=HTTPStatus.NOT_FOUND)
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
        if self._dispatch_ddnsgo_proxy(parsed, "HEAD", True):
            return
        if self._dispatch_shareclip_flask(parsed, "HEAD", True):
            return
        if parsed.path.startswith("/http-files/"):
            if not self._downloads_effective_enabled():
                self._error("外网上传已关闭", status=HTTPStatus.FORBIDDEN)
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
                self._error(f"下载失败：{exc}", status=HTTPStatus.INTERNAL_SERVER_ERROR)
                return

        self._error("未找到资源", status=HTTPStatus.NOT_FOUND)

    def do_POST(self):
        parsed = urlparse(self.path)

        if self._dispatch_ddnsgo_proxy(parsed, "POST", True):
            return
        if self._dispatch_shareclip_flask(parsed, "POST", True):
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
                self._error(f"终端连接失败：{exc}", status=HTTPStatus.BAD_REQUEST)
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
                self._error(f"读取失败：{exc}", status=HTTPStatus.BAD_REQUEST)
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
                self._error(f"写入失败：{exc}", status=HTTPStatus.BAD_REQUEST)
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
                self._error(f"调整失败：{exc}", status=HTTPStatus.BAD_REQUEST)
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
                self._error(f"关闭失败：{exc}", status=HTTPStatus.BAD_REQUEST)
                return
            self._send_json(data)
            return

        if parsed.path == "/api/terminal/key-file":
            if not self._require_lan():
                return
            body = self._parse_body()
            if not isinstance(body, dict):
                self._error("请求体需为 JSON 对象", status=HTTPStatus.BAD_REQUEST)
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
                self._error(f"key 文件保存失败：{exc}", status=HTTPStatus.INTERNAL_SERVER_ERROR)
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

        if parsed.path == "/api/ui/theme-background":
            if not self._require_lan():
                return
            body = self._parse_body()
            if not isinstance(body, dict):
                self._error("请求体需为 JSON 对象", status=HTTPStatus.BAD_REQUEST)
                return
            try:
                file_name, size = _save_theme_bg_file(
                    body.get("file_name", ""),
                    body.get("content_b64", ""),
                    _APP_ROOT_DIR,
                )
            except ValueError as exc:
                self._error(str(exc), status=HTTPStatus.BAD_REQUEST)
                return
            except Exception as exc:
                self._error(
                    f"背景图片保存失败：{exc}",
                    status=HTTPStatus.INTERNAL_SERVER_ERROR,
                )
                return
            current = load_app_config(_APP_ROOT_DIR)
            ui_cfg = current.setdefault("ui", {})
            old_file = _normalize_theme_bg_file_name(ui_cfg.get("hero_custom_bg_file", ""))
            ui_cfg["hero_custom_bg_file"] = file_name
            if bool(body.get("apply", True)):
                ui_cfg["hero_preset"] = "custom"
            saved = save_app_config(current, _APP_ROOT_DIR)
            if old_file and old_file != file_name:
                try:
                    assets_dir = theme_assets_dir(_APP_ROOT_DIR).resolve()
                    old_path = ensure_under_root(assets_dir, assets_dir / old_file)
                    if old_path.exists() and old_path.is_file():
                        old_path.unlink()
                except Exception:
                    pass
            self._send_json(
                {
                    "ok": True,
                    "file_name": file_name,
                    "size": int(size),
                    "config": saved,
                    "ui_theme": _ui_theme_payload(saved, _APP_ROOT_DIR),
                }
            )
            return

        if parsed.path == "/api/http/source-ip-pools/sync":
            if not self._require_lan():
                return
            body = self._parse_body()
            if body is None:
                body = {}
            if not isinstance(body, dict):
                self._error("请求体需为 JSON 对象", status=HTTPStatus.BAD_REQUEST)
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
                self._error(f"同步来源失败：{exc}", status=HTTPStatus.BAD_GATEWAY)
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
                self._error("请求体需为 JSON 对象", status=HTTPStatus.BAD_REQUEST)
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
                    self._error("程序端口需为 1-65535 的整数", status=HTTPStatus.BAD_REQUEST)
                    return
                if web_port_new <= 0 or web_port_new > 65535:
                    self._error("程序端口需为 1-65535 的整数", status=HTTPStatus.BAD_REQUEST)
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
            if http_path_cfg_changed:
                http_cfg = current.setdefault("http_service", {})
                root_for_check = self._http_root_from_raw(
                    http_cfg.get("root_dir"), app_cfg=current, require_exists=True
                )
                rel_default = _normalize_rel_dir_setting(http_cfg.get("default_dir", "."))
                default_target = ensure_under_root(root_for_check, root_for_check / rel_default)
                if not default_target.exists() or not default_target.is_dir():
                    self._error(
                        f"默认目录不存在或不可访问: {default_target}",
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
                if "hero_custom_bg_file" in incoming_ui:
                    ui_cfg["hero_custom_bg_file"] = _normalize_theme_bg_file_name(
                        incoming_ui.get("hero_custom_bg_file")
                    )
            saved = save_app_config(current, _APP_ROOT_DIR)
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
                # 仅中断本程序 /http-files 上传连接，不重启服务。
                self._cut_http_downloads_once()
                disconnect_triggered = True
                module_actions.append(
                    {
                        "module": "http",
                        "action": "disable-downloads",
                        "ok": True,
                        "message": "HTTP 模块已关闭，已禁用上传并中断本程序上传连接",
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
                        "message": "HTTP 模块已关闭，上传保持禁用",
                    }
                )

            if prev_qbt_enabled and not new_qbt_enabled:
                qbt_info = self._resolve_existing_unit(self.qbt_candidates)
                if qbt_info.get("load_state") == "not-found":
                    qbt_info = (
                        self._discover_unit_by_keywords(["qbit", "qbittorrent"]) or qbt_info
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
                            else f"停止内置 DDNS 失败：{msg}",
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
                self._error("HTTP 模块已关闭，无法开启上传", status=HTTPStatus.BAD_REQUEST)
                return
            with self.control_lock:
                self.downloads_enabled = enabled
                AppHandler.downloads_enabled = enabled
            self._send_json({"downloads_enabled": self._downloads_effective_enabled()})
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
                self._error("请求体需为 JSON 对象", status=HTTPStatus.BAD_REQUEST)
                return
            try:
                queued, status = self._schedule_upgrade(
                    body.get("repo"), body.get("tag"), body.get("branch")
                )
            except ValueError as exc:
                self._error(str(exc), status=HTTPStatus.BAD_REQUEST)
                return
            except Exception as exc:
                self._error(f"启动升级失败：{exc}", status=HTTPStatus.INTERNAL_SERVER_ERROR)
                return
            self._send_json({"queued": bool(queued), "status": status})
            return

        if parsed.path == "/api/ddns/config":
            if not self._require_lan():
                return
            if not self._ddns_module_enabled():
                self._error("DDNS 模块已关闭", status=HTTPStatus.FORBIDDEN)
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
                self._error("DDNS 模块已关闭", status=HTTPStatus.FORBIDDEN)
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
                self._error("target 须为 both / files / dirs", status=HTTPStatus.BAD_REQUEST)
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
                self._error(f"预览失败：{exc}", status=HTTPStatus.INTERNAL_SERVER_ERROR)
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

        if parsed.path == "/api/clean/apply":
            if not self._require_lan():
                return
            body = self._parse_body()
            moves = body.get("moves")
            if not isinstance(moves, list) or not moves:
                self._error("moves 须为非空数组", status=HTTPStatus.BAD_REQUEST)
                return
            try:
                results = apply_rename_plan(self.storage_root, moves)
            except Exception as exc:
                self._error(f"执行失败：{exc}", status=HTTPStatus.INTERNAL_SERVER_ERROR)
                return
            self._send_json({"results": results})
            return

        if parsed.path == "/api/control/service":
            if not self._require_lan():
                return
            body = self._parse_body()
            service = str(body.get("service", "")).strip().lower()
            action = str(body.get("action", "")).strip().lower()
            if service not in {"qbt", "ddns", "self"}:
                self._error("service 参数无效", status=HTTPStatus.BAD_REQUEST)
                return
            if action not in {"start", "stop", "restart", "quit"}:
                self._error("action 参数无效", status=HTTPStatus.BAD_REQUEST)
                return
            if service == "qbt" and (not self._qbt_module_enabled()) and action != "stop":
                self._error(
                    "qB 模块已关闭，请在 Config 中开启后再操作",
                    status=HTTPStatus.FORBIDDEN,
                )
                return
            if service == "ddns" and (not self._ddns_module_enabled()) and action != "stop":
                self._error(
                    "DDNS 模块已关闭，请在 Config 中开启后再操作",
                    status=HTTPStatus.FORBIDDEN,
                )
                return

            if service == "self":
                if action != "restart":
                    self._error("self 仅支持 restart", status=HTTPStatus.BAD_REQUEST)
                    return
                queued = self._schedule_restart()
                self._send_json({"queued": queued})
                return

            if action == "quit" and service != "qbt":
                self._error("仅 qbt 支持 quit", status=HTTPStatus.BAD_REQUEST)
                return

            if service == "qbt" and action == "quit":
                ok, msg = self._qbt_shutdown_once()
                if not ok:
                    self._error(f"quit 失败：{msg}", status=HTTPStatus.INTERNAL_SERVER_ERROR)
                    return
                self._qbt_reset_stats_cache()
                self._send_json(self._control_status_payload())
                return

            if service == "ddns" and ddns.config_path(
                _APP_ROOT_DIR
            ).exists():
                ok, msg = ddns.service_action(_APP_ROOT_DIR, action)
                if not ok:
                    self._error(
                        f"{action} 失败：{msg}", status=HTTPStatus.INTERNAL_SERVER_ERROR
                    )
                    return
                self._send_json(self._control_status_payload())
                return

            status_now = self._control_status_payload()
            target_info = status_now.get(service) or {}
            unit = str(target_info.get("unit", "")).strip()
            if not unit or target_info.get("load_state") == "not-found":
                self._error(f"{service} 服务未找到", status=HTTPStatus.NOT_FOUND)
                return

            ok, msg = self._service_action(unit, action)
            if not ok:
                self._error(f"{action} 失败：{msg}", status=HTTPStatus.INTERNAL_SERVER_ERROR)
                return
            if service == "qbt":
                self._qbt_reset_stats_cache()
            self._send_json(self._control_status_payload())
            return

        if parsed.path == "/api/qbt/fix-monitor":
            if not self._require_lan():
                return
            if not self._qbt_module_enabled():
                self._error(
                    "qB 模块已关闭，请在 Config 中开启后再操作",
                    status=HTTPStatus.FORBIDDEN,
                )
                return
            ok, msg, detail = self._qbt_fix_monitor_config()
            if not ok:
                self._error(f"qB 修复失败：{msg}", status=HTTPStatus.INTERNAL_SERVER_ERROR)
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
                    "qB 模块已关闭，请在 Config 中开启后再操作",
                    status=HTTPStatus.FORBIDDEN,
                )
                return
            ok, msg, detail = self._qbt_optimize_config()
            if not ok:
                self._error(f"qB 优化失败：{msg}", status=HTTPStatus.INTERNAL_SERVER_ERROR)
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

        self._error("未找到资源", status=HTTPStatus.NOT_FOUND)

    def do_DELETE(self):
        parsed = urlparse(self.path)
        if self._dispatch_shareclip_flask(parsed, "DELETE", True):
            return
        self._error("未找到资源", status=HTTPStatus.NOT_FOUND)

    def log_message(self, fmt: str, *args):
        return


def main():
    global ACTIVE_WEB_PORT
    _migrate_legacy_state_once()
    startup_cfg = load_app_config(_APP_ROOT_DIR)
    ACTIVE_WEB_PORT = _normalize_web_port(
        (startup_cfg or {}).get("web_port"), DEFAULT_WEB_PORT
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
