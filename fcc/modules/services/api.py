"""Service control API dispatch helpers."""

from __future__ import annotations

from http import HTTPStatus

from fcc.modules.services import service as services_service


def dispatch_post(handler, parsed, app_root) -> bool:
    path = str(getattr(parsed, "path", "") or "")
    if path != "/api/control/service":
        return False

    if not handler._require_lan():
        return True
    body = handler._parse_body()
    service = str(body.get("service", "")).strip().lower()
    action = str(body.get("action", "")).strip().lower()
    client_override = str(body.get("client", "") or "").strip().lower()
    ok_req, msg_req, status_req = services_service.validate_request(service, action)
    if not ok_req:
        handler._error(msg_req, status=status_req)
        return True
    if service == "qbt" and (not handler._qbt_module_enabled()) and action != "stop":
        handler._error(
            "qB module is disabled，请在 Config 中开启后再操作",
            status=HTTPStatus.FORBIDDEN,
        )
        return True
    if service == "ddns" and (not handler._ddns_module_enabled()) and action != "stop":
        handler._error(
            "DDNS module is disabled，请在 Config 中开启后再操作",
            status=HTTPStatus.FORBIDDEN,
        )
        return True

    ok, payload, status_code = services_service.execute_control_action(
        handler=handler,
        app_root=app_root,
        service=service,
        action=action,
        client_override=client_override,
    )
    if not ok:
        handler._error(str((payload or {}).get("error") or "service control failed"), status=status_code)
        return True
    handler._send_json(payload)
    return True
