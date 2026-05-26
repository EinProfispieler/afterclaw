"""Control API dispatch helpers for restart and HTTP access policy."""

from __future__ import annotations

from http import HTTPStatus


def dispatch_post(
    handler,
    parsed,
    app_root,
    load_app_config,
    save_app_config,
    http_access,
    time_module,
) -> bool:
    path = str(getattr(parsed, "path", "") or "")

    if path == "/healthz/restart":
        if not handler._require_lan():
            return True
        queued, reason = handler._schedule_restart()
        handler._send_json(
            {
                "ok": True,
                "queued": bool(queued),
                "message": "restart scheduled" if queued else str(reason or "restart not scheduled"),
            }
        )
        return True

    if path == "/api/control/http-access":
        if not handler._require_lan():
            return True
        body = handler._parse_body()
        action = str((body or {}).get("action", "") or "").strip().lower()
        cfg = load_app_config(app_root)
        policy = http_access.normalize_policy((cfg or {}).get("http_access"))
        if action == "open_public":
            try:
                duration = int((body or {}).get("duration_sec", 0))
            except (TypeError, ValueError):
                duration = 0
            if duration <= 0 or duration > 7 * 24 * 3600:
                handler._error(
                    "duration_sec must be between 1 and 604800",
                    status=HTTPStatus.BAD_REQUEST,
                )
                return True
            policy["mode"] = "public"
            policy["public_until"] = time_module.time() + duration
        elif action == "open_public_persistent":
            policy["mode"] = "public"
            policy["public_until"] = None
        elif action == "close":
            policy["mode"] = "lan_only"
            policy["public_until"] = None
        else:
            handler._error(
                "Unknown action; expected 'open_public', 'open_public_persistent', or 'close'",
                status=HTTPStatus.BAD_REQUEST,
            )
            return True
        cfg["http_access"] = http_access.normalize_policy(policy)
        save_app_config(cfg, app_root)
        handler._send_json(handler._http_access_status(cfg))
        return True

    if path == "/api/control/restart":
        if not handler._require_lan():
            return True
        queued, reason = handler._schedule_restart()
        payload = {"queued": bool(queued)}
        if reason:
            payload["error"] = str(reason)
        handler._send_json(payload)
        return True

    if path == "/api/control/downloads":
        if not handler._require_lan():
            return True
        body = handler._parse_body()
        enabled = bool((body or {}).get("enabled", True))
        if enabled and not handler._http_module_enabled():
            handler._error(
                "HTTP module is disabled; cannot enable upload",
                status=HTTPStatus.BAD_REQUEST,
            )
            return True
        with handler.control_lock:
            handler.downloads_enabled = enabled
            handler.__class__.downloads_enabled = enabled
        handler._send_json({"downloads_enabled": handler._downloads_effective_enabled()})
        return True

    return False
