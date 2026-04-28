"""对外的更新循环、与 systemd 卡片的合并、worker 启动。"""

from __future__ import annotations

import threading
import time
import urllib.error
import urllib.request
from typing import Any, Optional, Tuple

from . import state
from .config_store import apply_config_from_body, config_path, load_config, save_config
from .defaults import IP_FAIL_BACKOFF
from .ip.detect import get_ipv4_from_interface, get_ipv6_from_interface, get_public_ipv4, get_public_ipv6
from .providers import registry
from .validation import validate_config


def _is_ddnsgo_native(cfg: dict) -> bool:
    prov = str((cfg or {}).get("provider") or "").strip().lower()
    return prov in ("ddnsgo", "ddns-go", "native")


def _ddnsgo_base_url(cfg: dict) -> str:
    base = str((((cfg or {}).get("ddnsgo") or {}).get("base_url") or "")).strip()
    return base or "http://127.0.0.1:9876"


def _ddnsgo_ping(base_url: str) -> tuple[bool, str]:
    u = base_url.rstrip("/") + "/"
    req = urllib.request.Request(u, headers={"User-Agent": "storage-ctrl-ddns/2"})
    try:
        with urllib.request.urlopen(req, timeout=4) as resp:
            code = int(resp.getcode() or 0)
            if code in (200, 302, 401, 403):
                return True, f"ddns-go 在线（HTTP {code}）"
            return False, f"ddns-go 返回 HTTP {code}"
    except urllib.error.URLError as e:
        return False, f"ddns-go 不可达: {e}"
    except Exception as e:
        return False, f"ddns-go 不可达: {e}"


def _ipv4_get(cfg: dict) -> str:
    b = (cfg or {}).get("ipv4")
    if not isinstance(b, dict) or b.get("enabled", True) is False:
        raise ValueError("IPv4 已关闭")
    g = (b or {}).get("gettype", "url") or "url"
    urls = list((b or {}).get("urls") or [])
    if g in ("if", "interface", "netinterface", "net") and (b or {}).get("interface", "").strip():
        return get_ipv4_from_interface(str((b or {}).get("interface")).strip())
    return get_public_ipv4(urls)


def _ipv6_get(cfg: dict) -> str:
    b = (cfg or {}).get("ipv6")
    if not isinstance(b, dict) or b.get("enabled", False) is not True:
        raise ValueError("IPv6 已关闭")
    g = (b or {}).get("gettype", "url") or "url"
    urls = list((b or {}).get("urls") or [])
    if g in ("if", "interface", "netinterface", "net") and (b or {}).get("interface", "").strip():
        return get_ipv6_from_interface(str((b or {}).get("interface")).strip())
    return get_public_ipv6(urls)


def do_update_once(app_root) -> Tuple[bool, str, str | None]:
    cfg = load_config(app_root)
    if not (cfg or {}).get("enabled"):
        return False, "内置 DDNS 未启用", None
    err0 = validate_config(cfg)
    if err0:
        return False, err0, None
    if _is_ddnsgo_native(cfg):
        ok_ping, msg_ping = _ddnsgo_ping(_ddnsgo_base_url(cfg))
        if ok_ping:
            state.set_ok(None, None)
            return True, msg_ping, None
        state.set_error(msg_ping)
        return False, msg_ping, None
    v4: Optional[str] = None
    v6: Optional[str] = None
    v4e = (cfg or {}).get("ipv4", {})
    v4e = v4e.get("enabled", True) if isinstance(v4e, dict) else True
    v6e = (cfg or {}).get("ipv6", {})
    v6e = v6e.get("enabled", False) if isinstance(v6e, dict) else bool(v6e) if v6e else False
    try:
        if v4e:
            v4 = _ipv4_get(cfg)
    except Exception as e:
        v4 = None
        e4 = str(e)
    else:
        e4 = None
    try:
        if v6e:
            v6 = _ipv6_get(cfg)
    except Exception as e:
        v6 = None
        e6 = str(e)
    else:
        e6 = None
    if not v4 and not v6 and (e4 or e6):
        m = (e4 or e6) or "无法取公网地址"
        state.set_error(m)
        return False, m, None
    ok, msg = registry.run_update(cfg, v4, v6)
    if not ok:
        state.set_error(msg)
        return False, msg, v4 or v6
    state.set_ok(v4, v6)
    return True, msg, v4 or v6 or ""


def _detail_line(cfg: dict) -> str:
    st = state.get_state()
    prov = (cfg.get("provider") or "duckdns").strip()
    if _is_ddnsgo_native(cfg):
        return f"ddns-go 原生接管 · {_ddnsgo_base_url(cfg)}"
    err = st.get("last_error")
    v4, v6 = st.get("last_v4"), st.get("last_v6")
    ok = st.get("last_ok")
    if err:
        return f"{prov} · 错误: {(str(err) or '')[:160]}"
    if ok and (v4 or v6):
        ago = int(time.time() - float(ok or 0))
        bits = []
        if v4:
            bits.append(f"v4 {v4}")
        if v6:
            bits.append(f"v6 {v6}")
        return f"{prov} · {' / '.join(bits)}（{ago}s 前）"
    if v4 or v6:
        p = f"{v4 or '-'} {v6 or ''}".strip()
        return f"{prov} · 最近 {p}"
    return f"{prov} · 尚未成功同步"


def status_for_api(app_root) -> dict[str, Any]:
    p = config_path(app_root)
    if not p.exists():
        return {"source": "none", "file": False}
    cfg = load_config(app_root)
    en = bool(cfg.get("enabled"))
    v_err = validate_config(cfg) if en else None
    native = _is_ddnsgo_native(cfg)
    ping_ok, ping_msg = (True, "native") if not native else _ddnsgo_ping(_ddnsgo_base_url(cfg))
    is_run = en and (v_err is None) and (ping_ok if native else True)
    return {
        "source": "builtin",
        "file": True,
        "unit": "内置 DDNS",
        "load_state": "loaded",
        "active_state": "active" if is_run else "inactive",
        "sub_state": "ok" if is_run else ("invalid" if (en and v_err) else ("error" if (en and native and not ping_ok) else "off")),
        "enabled": en,
        "valid": is_run,
        "validation_error": v_err if v_err else (None if (not native or ping_ok) else ping_msg),
        "provider": cfg.get("provider") or "duckdns",
        "detail": ping_msg if (native and not ping_ok) else _detail_line(cfg),
    }


def merge_builtin_into_systemd_shape(app_root):
    if not config_path(app_root).exists():
        return None
    cfg = load_config(app_root)
    en = bool(cfg.get("enabled"))
    v_err = validate_config(cfg) if en else None
    native = _is_ddnsgo_native(cfg)
    ping_ok, ping_msg = (True, "native") if not native else _ddnsgo_ping(_ddnsgo_base_url(cfg))
    is_run = en and (v_err is None) and (ping_ok if native else True)
    dline = _detail_line(cfg)
    if en and v_err:
        dline = f"配置未就绪: {v_err}"
    elif en and native and not ping_ok:
        dline = ping_msg
    return {
        "unit": "内置 DDNS",
        "load_state": "loaded",
        "active_state": "active" if is_run else "inactive",
        "sub_state": "ready",
        "source": "builtin",
        "enabled": en,
        "detail": dline,
    }


def _worker(app_root) -> None:
    fail = 0
    while True:
        try:
            cfg = load_config(app_root)
            itv = max(60, int((cfg or {}).get("interval_sec") or 300))
            if not (cfg or {}).get("enabled"):
                time.sleep(min(30, itv))
                continue
            if validate_config(cfg):
                time.sleep(30)
                continue
            do_update_once(app_root)
            fail = 0
            time.sleep(itv)
        except Exception as e:
            state.set_error(str(e))
            fail = min(fail + 1, len(IP_FAIL_BACKOFF) - 1)
            time.sleep(IP_FAIL_BACKOFF[fail])


def start_worker(app_root) -> None:
    if not state.mark_thread_started():
        return
    threading.Thread(
        target=_worker, args=(app_root,), name="ddns-worker", daemon=True
    ).start()


def service_action(app_root, act: str) -> Tuple[bool, str]:
    if not config_path(app_root).exists():
        return False, "缺少 ddns_config.json"
    if act in ("start", "stop"):
        c = load_config(app_root)
        c["enabled"] = act == "start"
        save_config(app_root, c)
        return True, "ok" if act == "start" else "stopped"
    if act == "restart":
        ok, msg, _ = do_update_once(app_root)
        return (ok, msg) if ok else (False, msg)
    return False, "不支持的操作"
