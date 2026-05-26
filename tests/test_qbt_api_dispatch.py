from __future__ import annotations

from http import HTTPStatus
from pathlib import Path
from urllib.parse import urlparse

from fcc.modules.qbt import api as qbt_api


class _FakeHandler:
    def __init__(self):
        self.lan_ok = True
        self.qbt_enabled = True
        self.body = {}
        self.sent = []
        self.errors = []

    def _require_lan(self):
        return self.lan_ok

    def _send_json(self, payload):
        self.sent.append(payload)

    def _error(self, message, status=HTTPStatus.BAD_REQUEST):
        self.errors.append((int(status), str(message)))

    def _qbt_discover_options(self, app_cfg):
        return {"ok": True, "cfg_client": ((app_cfg or {}).get("qbt") or {}).get("client", "")}

    def _qbt_module_enabled(self):
        return self.qbt_enabled

    def _qbt_fix_monitor_config(self):
        return True, "fixed", {"patched": True}

    def _control_status_payload(self):
        return {"qbt": {"active_state": "active"}}

    def _parse_body(self):
        return self.body

    def _qbt_optimize_config(self, selected):
        return True, "optimized", {"selected": selected}


def test_qbt_get_discover_dispatch():
    handler = _FakeHandler()
    handled = qbt_api.dispatch_get(
        handler,
        urlparse("/api/qbt/discover?client=qbittorrent"),
        lambda _root: {"qbt": {}},
        Path("."),
    )
    assert handled is True
    assert handler.sent and handler.sent[-1]["ok"] is True


def test_qbt_post_fix_monitor_disabled():
    handler = _FakeHandler()
    handler.qbt_enabled = False
    handled = qbt_api.dispatch_post(handler, urlparse("/api/qbt/fix-monitor"))
    assert handled is True
    assert handler.errors and handler.errors[-1][0] == 403


def test_qbt_post_optimize_success():
    handler = _FakeHandler()
    handler.body = {"qbt": {"service_unit": "qbittorrent.service"}}
    handled = qbt_api.dispatch_post(handler, urlparse("/api/qbt/optimize-config"))
    assert handled is True
    assert handler.sent and handler.sent[-1]["ok"] is True
