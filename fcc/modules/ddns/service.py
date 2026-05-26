"""DDNS domain service helpers."""

from __future__ import annotations

import ddns


def config_payload(app_root) -> dict:
    cfg = ddns.load_config(app_root)
    st = ddns.status_for_api(app_root)
    return {
        "config": cfg,
        "status": st,
        "config_path": str(ddns.config_path(app_root)),
    }


def apply_config(app_root, body) -> tuple[bool, str, dict]:
    ok, msg = ddns.apply_config_from_body(app_root, body)
    if not ok:
        return False, msg, {}
    return True, "", {"ok": True, "config": ddns.load_config(app_root), "status": ddns.status_for_api(app_root)}


def run_once(app_root) -> tuple[bool, str, dict]:
    ok, msg, ip = ddns.do_update_once(app_root)
    if not ok:
        return False, msg, {}
    return True, "", {"ok": True, "message": msg, "ip": ip}


def run_service_action(app_root, action: str) -> tuple[bool, str]:
    if not ddns.config_path(app_root).exists():
        return False, "ddns config missing"
    return ddns.service_action(app_root, action)
