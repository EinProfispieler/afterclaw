from __future__ import annotations

from http import HTTPStatus
from pathlib import Path
from urllib.parse import urlparse

from fcc.modules.services import api as services_api


class _FakeHandler:
    def __init__(self):
        self.lan_ok = True
        self.body = {}
        self.errors = []
        self.sent = []
        self.qbt_enabled = True
        self.ddns_enabled = True
        self.restart_result = (True, "")
        self.shutdown_result = (True, "")
        self.service_result = (True, "")

    def _require_lan(self):
        return self.lan_ok

    def _parse_body(self):
        return self.body

    def _error(self, message, status=HTTPStatus.BAD_REQUEST):
        self.errors.append((int(status), str(message)))

    def _send_json(self, payload):
        self.sent.append(payload)

    def _qbt_module_enabled(self):
        return self.qbt_enabled

    def _ddns_module_enabled(self):
        return self.ddns_enabled

    def _schedule_restart(self):
        return self.restart_result

    def _qbt_shutdown_once(self):
        return self.shutdown_result

    def _qbt_reset_stats_cache(self):
        return None

    def _control_status_payload(self, client_override=""):
        return {"qbt": {"unit": "qbt.service", "load_state": "loaded"}, "client": client_override}

    def _service_action(self, unit, action):
        return self.service_result


def test_services_dispatch_rejects_invalid_service():
    handler = _FakeHandler()
    handler.body = {"service": "bad", "action": "restart"}
    handled = services_api.dispatch_post(handler, urlparse("/api/control/service"), Path("."))
    assert handled is True
    assert handler.errors == [(int(HTTPStatus.BAD_REQUEST), "Invalid service parameter")]


def test_services_dispatch_self_restart():
    handler = _FakeHandler()
    handler.body = {"service": "self", "action": "restart"}
    handled = services_api.dispatch_post(handler, urlparse("/api/control/service"), Path("."))
    assert handled is True
    assert not handler.errors
    assert handler.sent == [{"queued": True}]


def test_services_dispatch_qbt_quit_success():
    handler = _FakeHandler()
    handler.body = {"service": "qbt", "action": "quit", "client": "local"}
    handled = services_api.dispatch_post(handler, urlparse("/api/control/service"), Path("."))
    assert handled is True
    assert not handler.errors
    assert handler.sent
    assert handler.sent[-1]["client"] == "local"


def test_services_dispatch_ddns_builtin_path(monkeypatch):
    handler = _FakeHandler()
    handler.body = {"service": "ddns", "action": "restart"}
    monkeypatch.setattr(
        services_api.services_service,
        "execute_control_action",
        lambda **_kwargs: (True, {"ddns": "ok"}, int(HTTPStatus.OK)),
    )

    handled = services_api.dispatch_post(handler, urlparse("/api/control/service"), Path("."))
    assert handled is True
    assert not handler.errors
    assert handler.sent == [{"ddns": "ok"}]
