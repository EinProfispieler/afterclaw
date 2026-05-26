"""DDNS API dispatch helpers."""

from __future__ import annotations

from http import HTTPStatus

from fcc.modules.ddns import service as ddns_service


def dispatch_get(handler, parsed, app_root) -> bool:
    path = str(getattr(parsed, "path", "") or "")
    if path != "/api/ddns/config":
        return False
    if not handler._require_lan():
        return True
    if not handler._ddns_module_enabled():
        handler._error("DDNS module is disabled", status=HTTPStatus.FORBIDDEN)
        return True
    handler._send_json(ddns_service.config_payload(app_root))
    return True


def dispatch_post(handler, parsed, app_root) -> bool:
    path = str(getattr(parsed, "path", "") or "")
    if path == "/api/ddns/config":
        if not handler._require_lan():
            return True
        if not handler._ddns_module_enabled():
            handler._error("DDNS module is disabled", status=HTTPStatus.FORBIDDEN)
            return True
        body = handler._parse_body()
        ok, msg, payload = ddns_service.apply_config(app_root, body)
        if not ok:
            handler._error(msg, status=HTTPStatus.BAD_REQUEST)
            return True
        handler._send_json(payload)
        return True

    if path == "/api/ddns/run":
        if not handler._require_lan():
            return True
        if not handler._ddns_module_enabled():
            handler._error("DDNS module is disabled", status=HTTPStatus.FORBIDDEN)
            return True
        ok, msg, payload = ddns_service.run_once(app_root)
        if not ok:
            handler._error(msg, status=HTTPStatus.BAD_REQUEST)
            return True
        handler._send_json(payload)
        return True

    return False
