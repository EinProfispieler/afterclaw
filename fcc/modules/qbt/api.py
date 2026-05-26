"""qBittorrent API dispatch helpers."""

from __future__ import annotations

from urllib.parse import parse_qs

from fcc import config_schema


def dispatch_get(handler, parsed, load_app_config, app_root) -> bool:
    path = str(getattr(parsed, "path", "") or "")
    if path != "/api/qbt/discover":
        return False
    if not handler._require_lan():
        return True
    query = parse_qs(parsed.query)
    client = str(query.get("client", [""])[0] or "").strip().lower()
    app_cfg = load_app_config(app_root)
    if client in config_schema.QBT_CLIENT_KEYS:
        if not isinstance(app_cfg, dict):
            app_cfg = {}
        qbt_cfg = app_cfg.get("qbt")
        if not isinstance(qbt_cfg, dict):
            qbt_cfg = {}
        qbt_cfg = dict(qbt_cfg)
        qbt_cfg["client"] = client
        app_cfg["qbt"] = qbt_cfg
    handler._send_json(handler._qbt_discover_options(app_cfg))
    return True


def dispatch_post(handler, parsed) -> bool:
    path = str(getattr(parsed, "path", "") or "")

    if path == "/api/qbt/fix-monitor":
        if not handler._require_lan():
            return True
        if not handler._qbt_module_enabled():
            handler._error(
                "qB module is disabled，请在 Config 中开启后再操作",
                status=403,
            )
            return True
        ok, msg, detail = handler._qbt_fix_monitor_config()
        if not ok:
            handler._error(f"qB fix failed: {msg}", status=500)
            return True
        status_payload = handler._control_status_payload()
        handler._send_json(
            {
                "ok": True,
                "message": msg,
                "detail": detail,
                "status": status_payload.get("qbt", {}),
            }
        )
        return True

    if path == "/api/qbt/optimize-config":
        if not handler._require_lan():
            return True
        if not handler._qbt_module_enabled():
            handler._error(
                "qB module is disabled，请在 Config 中开启后再操作",
                status=403,
            )
            return True
        body = handler._parse_body()
        selected = (body.get("qbt") or {}) if isinstance(body, dict) else {}
        ok, msg, detail = handler._qbt_optimize_config(
            selected if isinstance(selected, dict) else {}
        )
        if not ok:
            handler._error(f"qB optimize failed: {msg}", status=500)
            return True
        status_payload = handler._control_status_payload()
        handler._send_json(
            {
                "ok": True,
                "message": msg,
                "detail": detail,
                "status": status_payload.get("qbt", {}),
            }
        )
        return True

    return False
