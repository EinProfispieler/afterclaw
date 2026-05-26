"""Service control domain helpers."""

from __future__ import annotations

from http import HTTPStatus

from fcc.modules.ddns import service as ddns_service


def validate_request(service: str, action: str) -> tuple[bool, str, int]:
    if service not in {"qbt", "ddns", "self"}:
        return False, "Invalid service parameter", int(HTTPStatus.BAD_REQUEST)
    if action not in {"start", "stop", "restart", "quit"}:
        return False, "Invalid action parameter", int(HTTPStatus.BAD_REQUEST)
    return True, "", int(HTTPStatus.OK)


def execute_control_action(handler, app_root, service: str, action: str, client_override: str):
    if service == "self":
        if action != "restart":
            return False, {"error": "self only supports restart"}, int(HTTPStatus.BAD_REQUEST)
        queued, reason = handler._schedule_restart()
        payload = {"queued": bool(queued)}
        if reason:
            payload["error"] = str(reason)
        return True, payload, int(HTTPStatus.OK)

    if action == "quit" and service != "qbt":
        return False, {"error": "Only qbt supports quit"}, int(HTTPStatus.BAD_REQUEST)

    if service == "qbt" and action == "quit":
        ok, msg = handler._qbt_shutdown_once()
        if not ok:
            return False, {"error": f"quit failed: {msg}"}, int(HTTPStatus.INTERNAL_SERVER_ERROR)
        handler._qbt_reset_stats_cache()
        return True, handler._control_status_payload(client_override), int(HTTPStatus.OK)

    if service == "ddns":
        ok, msg = ddns_service.run_service_action(app_root, action)
        if ok:
            return True, handler._control_status_payload(client_override), int(HTTPStatus.OK)
        if msg != "ddns config missing":
            return False, {"error": f"{action} failed: {msg}"}, int(HTTPStatus.INTERNAL_SERVER_ERROR)

    status_now = handler._control_status_payload(client_override)
    target_info = status_now.get(service) or {}
    unit = str(target_info.get("unit", "")).strip()
    if not unit or target_info.get("load_state") == "not-found":
        return False, {"error": f"{service} service not found"}, int(HTTPStatus.NOT_FOUND)

    ok, msg = handler._service_action(unit, action)
    if not ok:
        return False, {"error": f"{action} failed: {msg}"}, int(HTTPStatus.INTERNAL_SERVER_ERROR)
    if service == "qbt":
        handler._qbt_reset_stats_cache()
    return True, handler._control_status_payload(client_override), int(HTTPStatus.OK)
