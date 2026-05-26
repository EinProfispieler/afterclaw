from __future__ import annotations

from http import HTTPStatus

from fcc.modules.upgrade import service as upgrade_service


def test_upgrade_service_status_and_check_version():
    status = upgrade_service.status_payload(lambda: {"ok": True, "state": "idle"})
    version = upgrade_service.check_version_payload("main", lambda b: {"ok": True, "branch": b})
    assert status.ok is True
    assert status.payload and status.payload["state"] == "idle"
    assert version.ok is True
    assert version.payload and version.payload["branch"] == "main"


def test_upgrade_service_run_bad_body():
    result = upgrade_service.run_upgrade("bad", lambda _b, _s: (True, {}))
    assert result.ok is False
    assert result.status == int(HTTPStatus.BAD_REQUEST)


def test_upgrade_service_run_success():
    result = upgrade_service.run_upgrade({"branch": "nightly"}, lambda b, s: (True, {"branch": b, "script_source": s or ""}))
    assert result.ok is True
    assert result.payload and result.payload["queued"] is True
