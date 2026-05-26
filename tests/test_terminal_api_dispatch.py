from __future__ import annotations

from http import HTTPStatus
from pathlib import Path
from urllib.parse import urlparse

from fcc.modules.terminal import api as terminal_api


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

    def _client_ip(self):
        return "127.0.0.1"

    def _error(self, message, status=HTTPStatus.BAD_REQUEST):
        self.errors.append((int(status), str(message)))

    def _send_json(self, payload):
        self.sent.append(payload)

    def _terminal_start_session(self, cols, rows, client_ip):
        return "sid-1", {"cols": cols, "rows": rows, "client_ip": client_ip}

    def _terminal_list_sessions(self):
        return {"sessions": []}

    def _terminal_get_history(self, limit, keyword, client_ip, session_id):
        return {"items": [], "limit": limit}

    def _terminal_clear_history(self):
        return {"ok": True, "cleared": 1}

    def _terminal_read_session(self, session_id, max_bytes):
        return {"ok": True, "session_id": session_id, "data": "", "max_bytes": max_bytes}

    def _terminal_write_session(self, session_id, data):
        return {"ok": True, "session_id": session_id, "written": len(str(data))}

    def _terminal_resize_session(self, session_id, cols, rows):
        return {"ok": True, "session_id": session_id, "cols": cols, "rows": rows}

    def _terminal_close_session(self, session_id):
        return {"ok": True, "closed": bool(session_id)}


def test_terminal_start_dispatch_success():
    handler = _FakeHandler()
    handler.body = {"cols": 100, "rows": 40}
    handled = terminal_api.dispatch_post(handler, urlparse("/api/terminal/start"), Path("."))
    assert handled is True
    assert not handler.errors
    assert handler.sent[-1]["ok"] is True
    assert handler.sent[-1]["session_id"] == "sid-1"


def test_terminal_revoke_missing_session_id():
    handler = _FakeHandler()
    handler.body = {}
    handled = terminal_api.dispatch_post(handler, urlparse("/api/terminal/revoke"), Path("."))
    assert handled is True
    assert handler.errors == [(int(HTTPStatus.BAD_REQUEST), "Missing session_id")]


def test_terminal_write_error_is_bad_request():
    handler = _FakeHandler()
    handler.body = {"session_id": "s1", "data": "ls"}

    def _raise_write(_sid, _data):
        raise RuntimeError("write failed")

    handler._terminal_write_session = _raise_write
    handled = terminal_api.dispatch_post(handler, urlparse("/api/terminal/write"), Path("."))
    assert handled is True
    assert handler.errors
    assert handler.errors[-1][0] == int(HTTPStatus.BAD_REQUEST)
    assert "Write failed" in handler.errors[-1][1]


def test_terminal_non_matching_path_returns_false():
    handler = _FakeHandler()
    handled = terminal_api.dispatch_post(handler, urlparse("/api/terminal/not-found"), Path("."))
    assert handled is False


def test_terminal_key_file_dispatch_success(monkeypatch):
    handler = _FakeHandler()
    handler.body = {"file_name": "id_ed25519", "content_b64": "abc"}
    monkeypatch.setattr(
        terminal_api.terminal_service,
        "upload_key_file",
        lambda _body, _root: {"ok": True, "file_name": "id_ed25519", "size": 3},
    )
    handled = terminal_api.dispatch_post(handler, urlparse("/api/terminal/key-file"), Path("."))
    assert handled is True
    assert handler.sent[-1]["ok"] is True
