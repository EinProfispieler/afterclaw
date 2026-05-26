"""Upgrade API dispatch helpers."""

from __future__ import annotations

from urllib.parse import parse_qs

from fcc.modules.upgrade import service as upgrade_service


def dispatch_get(handler, parsed) -> bool:
    path = str(getattr(parsed, "path", "") or "")

    if path == "/api/upgrade/status":
        if not handler._require_lan():
            return True
        result = upgrade_service.status_payload(handler._upgrade_status_payload)
        handler._send_json(result.payload or {"ok": False})
        return True

    if path == "/api/upgrade/check-version":
        if not handler._require_lan():
            return True
        query = parse_qs(parsed.query)
        branch_raw = str(query.get("branch", [""])[0] or "").strip()
        result = upgrade_service.check_version_payload(
            branch_raw,
            handler._upgrade_branch_version_payload,
        )
        handler._send_json(result.payload or {"ok": False})
        return True

    return False


def dispatch_post(handler, parsed) -> bool:
    path = str(getattr(parsed, "path", "") or "")
    if path != "/api/upgrade/run":
        return False
    if not handler._require_lan():
        return True
    result = upgrade_service.run_upgrade(
        handler._parse_body(),
        handler._schedule_upgrade,
    )
    if not result.ok:
        handler._error(result.error, status=result.status)
        return True
    handler._send_json(result.payload or {"ok": False})
    return True
