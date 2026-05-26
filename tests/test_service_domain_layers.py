from __future__ import annotations

from http import HTTPStatus
from pathlib import Path

from fcc.modules.ddns import service as ddns_service
from fcc.modules.services import service as services_service


class _FakeHandler:
    def __init__(self):
        self.reset_calls = 0

    def _schedule_restart(self):
        return True, ""

    def _qbt_shutdown_once(self):
        return True, ""

    def _qbt_reset_stats_cache(self):
        self.reset_calls += 1

    def _control_status_payload(self, client_override=""):
        return {
            "qbt": {"unit": "qbt.service", "load_state": "loaded"},
            "ddns": {"unit": "ddns.service", "load_state": "loaded"},
            "client": client_override,
        }

    def _service_action(self, unit, action):
        return True, f"{unit}:{action}"


def test_services_validate_request():
    ok, msg, code = services_service.validate_request("qbt", "restart")
    assert ok is True
    assert msg == ""
    assert code == int(HTTPStatus.OK)

    ok, msg, code = services_service.validate_request("bad", "restart")
    assert ok is False
    assert code == int(HTTPStatus.BAD_REQUEST)
    assert "Invalid service" in msg


def test_services_execute_self_restart():
    handler = _FakeHandler()
    ok, payload, code = services_service.execute_control_action(
        handler=handler,
        app_root=Path("."),
        service="self",
        action="restart",
        client_override="",
    )
    assert ok is True
    assert code == int(HTTPStatus.OK)
    assert payload == {"queued": True}


def test_services_execute_ddns_fallback_to_unit(monkeypatch):
    handler = _FakeHandler()
    monkeypatch.setattr(services_service.ddns_service, "run_service_action", lambda _root, _action: (False, "ddns config missing"))
    ok, payload, code = services_service.execute_control_action(
        handler=handler,
        app_root=Path("."),
        service="ddns",
        action="restart",
        client_override="lan",
    )
    assert ok is True
    assert code == int(HTTPStatus.OK)
    assert payload["client"] == "lan"


def test_ddns_service_run_once_success(monkeypatch):
    monkeypatch.setattr(ddns_service.ddns, "do_update_once", lambda _root: (True, "done", "1.2.3.4"))
    ok, msg, payload = ddns_service.run_once(Path("."))
    assert ok is True
    assert msg == ""
    assert payload == {"ok": True, "message": "done", "ip": "1.2.3.4"}
