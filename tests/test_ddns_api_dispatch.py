from __future__ import annotations

from http import HTTPStatus
from pathlib import Path
from urllib.parse import urlparse

from fcc.modules.ddns import api as ddns_api


class _FakeHandler:
    def __init__(self):
        self.lan_ok = True
        self.module_enabled = True
        self.body = {}
        self.errors = []
        self.sent = []

    def _require_lan(self):
        return self.lan_ok

    def _ddns_module_enabled(self):
        return self.module_enabled

    def _parse_body(self):
        return self.body

    def _error(self, message, status=HTTPStatus.BAD_REQUEST):
        self.errors.append((int(status), str(message)))

    def _send_json(self, payload):
        self.sent.append(payload)


def test_ddns_get_config_success(monkeypatch):
    handler = _FakeHandler()
    monkeypatch.setattr(
        ddns_api.ddns_service,
        "config_payload",
        lambda _root: {"config": {"enabled": True}, "status": {"ok": True}, "config_path": "/tmp/ddns.json"},
    )

    handled = ddns_api.dispatch_get(handler, urlparse("/api/ddns/config"), Path("."))
    assert handled is True
    assert not handler.errors
    assert handler.sent
    assert handler.sent[-1]["config_path"] == "/tmp/ddns.json"


def test_ddns_post_config_validation_error(monkeypatch):
    handler = _FakeHandler()
    monkeypatch.setattr(
        ddns_api.ddns_service,
        "apply_config",
        lambda _root, _body: (False, "bad payload", {}),
    )

    handled = ddns_api.dispatch_post(handler, urlparse("/api/ddns/config"), Path("."))
    assert handled is True
    assert handler.errors == [(int(HTTPStatus.BAD_REQUEST), "bad payload")]


def test_ddns_post_run_success(monkeypatch):
    handler = _FakeHandler()
    monkeypatch.setattr(
        ddns_api.ddns_service,
        "run_once",
        lambda _root: (True, "", {"ok": True, "message": "done", "ip": "1.2.3.4"}),
    )

    handled = ddns_api.dispatch_post(handler, urlparse("/api/ddns/run"), Path("."))
    assert handled is True
    assert not handler.errors
    assert handler.sent == [{"ok": True, "message": "done", "ip": "1.2.3.4"}]


def test_ddns_disabled_returns_forbidden():
    handler = _FakeHandler()
    handler.module_enabled = False
    handled = ddns_api.dispatch_get(handler, urlparse("/api/ddns/config"), Path("."))
    assert handled is True
    assert handler.errors == [(int(HTTPStatus.FORBIDDEN), "DDNS module is disabled")]
