from __future__ import annotations

from http import HTTPStatus
from pathlib import Path
import threading
from urllib.parse import urlparse

import fcc.http_access as http_access_policy
from fcc.modules.control import api as control_api


class _FakeTime:
    @staticmethod
    def time():
        return 1000.0


class _FakeHandler:
    def __init__(self):
        self.lan_ok = True
        self.body = {}
        self.sent = []
        self.errors = []
        self.restart_result = (True, "")
        self.http_module_enabled = True
        self.downloads_enabled = False
        self.control_lock = threading.Lock()

    def _require_lan(self):
        return self.lan_ok

    def _parse_body(self):
        return self.body

    def _send_json(self, payload):
        self.sent.append(payload)

    def _error(self, message, status=HTTPStatus.BAD_REQUEST):
        self.errors.append((int(status), str(message)))

    def _schedule_restart(self):
        return self.restart_result

    def _http_access_status(self, cfg):
        return {"mode": ((cfg or {}).get("http_access") or {}).get("mode", "lan_only")}

    def _http_module_enabled(self):
        return self.http_module_enabled

    def _downloads_effective_enabled(self):
        return bool(self.downloads_enabled)


def test_control_dispatch_healthz_restart():
    handler = _FakeHandler()
    cfg = {"http_access": {"mode": "lan_only", "public_until": None}}

    handled = control_api.dispatch_post(
        handler,
        urlparse("/healthz/restart"),
        Path("."),
        lambda _root: cfg,
        lambda _cfg, _root: _cfg,
        http_access_policy,
        _FakeTime,
    )
    assert handled is True
    assert handler.sent and handler.sent[-1]["ok"] is True
    assert handler.sent[-1]["queued"] is True


def test_control_dispatch_api_restart_with_reason():
    handler = _FakeHandler()
    handler.restart_result = (False, "unsupported restart backend")
    cfg = {"http_access": {"mode": "lan_only", "public_until": None}}

    handled = control_api.dispatch_post(
        handler,
        urlparse("/api/control/restart"),
        Path("."),
        lambda _root: cfg,
        lambda _cfg, _root: _cfg,
        http_access_policy,
        _FakeTime,
    )
    assert handled is True
    assert handler.sent == [{"queued": False, "error": "unsupported restart backend"}]


def test_control_dispatch_http_access_invalid_duration():
    handler = _FakeHandler()
    handler.body = {"action": "open_public", "duration_sec": 0}
    cfg = {"http_access": {"mode": "lan_only", "public_until": None}}

    handled = control_api.dispatch_post(
        handler,
        urlparse("/api/control/http-access"),
        Path("."),
        lambda _root: cfg,
        lambda _cfg, _root: _cfg,
        http_access_policy,
        _FakeTime,
    )
    assert handled is True
    assert handler.errors and handler.errors[-1][0] == 400


def test_control_dispatch_http_access_open_persistent():
    handler = _FakeHandler()
    handler.body = {"action": "open_public_persistent"}
    cfg = {"http_access": {"mode": "lan_only", "public_until": None}}
    saved = {}

    def _save(next_cfg, _root):
        saved.clear()
        saved.update(next_cfg)
        return next_cfg

    handled = control_api.dispatch_post(
        handler,
        urlparse("/api/control/http-access"),
        Path("."),
        lambda _root: cfg,
        _save,
        http_access_policy,
        _FakeTime,
    )
    assert handled is True
    assert saved["http_access"]["mode"] == "public"
    assert saved["http_access"]["public_until"] is None
    assert handler.sent and handler.sent[-1]["mode"] == "public"


def test_control_dispatch_non_matching_route_returns_false():
    handler = _FakeHandler()
    handled = control_api.dispatch_post(
        handler,
        urlparse("/api/control/unknown"),
        Path("."),
        lambda _root: {},
        lambda _cfg, _root: _cfg,
        http_access_policy,
        _FakeTime,
    )
    assert handled is False


def test_control_dispatch_downloads_enable_success():
    handler = _FakeHandler()
    handler.body = {"enabled": True}
    handled = control_api.dispatch_post(
        handler,
        urlparse("/api/control/downloads"),
        Path("."),
        lambda _root: {},
        lambda _cfg, _root: _cfg,
        http_access_policy,
        _FakeTime,
    )
    assert handled is True
    assert not handler.errors
    assert handler.sent == [{"downloads_enabled": True}]


def test_control_dispatch_downloads_enable_rejected_when_http_disabled():
    handler = _FakeHandler()
    handler.http_module_enabled = False
    handler.body = {"enabled": True}
    handled = control_api.dispatch_post(
        handler,
        urlparse("/api/control/downloads"),
        Path("."),
        lambda _root: {},
        lambda _cfg, _root: _cfg,
        http_access_policy,
        _FakeTime,
    )
    assert handled is True
    assert handler.errors and handler.errors[-1][0] == 400
