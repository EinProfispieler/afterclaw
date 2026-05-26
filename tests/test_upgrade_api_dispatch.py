from __future__ import annotations

from http import HTTPStatus
from urllib.parse import urlparse

from fcc.modules.upgrade import api as upgrade_api


class _FakeHandler:
    def __init__(self):
        self.lan_ok = True
        self.body = {}
        self.errors = []
        self.sent = []

    def _require_lan(self):
        return self.lan_ok

    def _parse_body(self):
        return self.body

    def _error(self, message, status=HTTPStatus.BAD_REQUEST):
        self.errors.append((int(status), str(message)))

    def _send_json(self, payload):
        self.sent.append(payload)

    def _upgrade_status_payload(self):
        return {"ok": True, "state": "idle"}

    def _upgrade_branch_version_payload(self, branch_raw):
        return {"ok": True, "branch": branch_raw or "main"}

    def _schedule_upgrade(self, branch, script_source):
        return True, {"branch": branch or "main", "script_source": script_source or ""}


def test_upgrade_dispatch_get_status_and_check_version():
    handler = _FakeHandler()
    assert upgrade_api.dispatch_get(handler, urlparse("/api/upgrade/status")) is True
    assert upgrade_api.dispatch_get(handler, urlparse("/api/upgrade/check-version?branch=nightly")) is True
    assert handler.sent[0]["state"] == "idle"
    assert handler.sent[1]["branch"] == "nightly"


def test_upgrade_dispatch_post_run_bad_body():
    handler = _FakeHandler()
    handler.body = "bad"
    handled = upgrade_api.dispatch_post(handler, urlparse("/api/upgrade/run"))
    assert handled is True
    assert handler.errors == [(int(HTTPStatus.BAD_REQUEST), "Request body must be a JSON object")]


def test_upgrade_dispatch_post_run_success():
    handler = _FakeHandler()
    handler.body = {"branch": "main", "script_source": "https://example.com/hook.sh"}
    handled = upgrade_api.dispatch_post(handler, urlparse("/api/upgrade/run"))
    assert handled is True
    assert not handler.errors
    assert handler.sent[-1]["queued"] is True
