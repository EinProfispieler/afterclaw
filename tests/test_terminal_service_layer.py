from __future__ import annotations

from pathlib import Path

from fcc.modules.terminal import service as terminal_service


class _FakeHandler:
    def _terminal_start_session(self, cols, rows, client_ip):
        return "sid", {"cols": cols, "rows": rows, "client_ip": client_ip}

    def _terminal_list_sessions(self):
        return {"sessions": ["sid"]}

    def _terminal_get_history(self, limit, keyword, client_ip, session_id):
        return {"items": [], "limit": limit, "keyword": keyword, "client_ip": client_ip, "session_id": session_id}

    def _terminal_clear_history(self):
        return {"ok": True, "cleared": 1}

    def _terminal_read_session(self, session_id, max_bytes):
        return {"ok": True, "session_id": session_id, "max_bytes": max_bytes}

    def _terminal_write_session(self, session_id, data):
        return {"ok": True, "session_id": session_id, "written": len(str(data))}

    def _terminal_resize_session(self, session_id, cols, rows):
        return {"ok": True, "session_id": session_id, "cols": cols, "rows": rows}

    def _terminal_close_session(self, session_id):
        return {"ok": True, "closed": bool(session_id)}


def test_terminal_service_start_and_list():
    handler = _FakeHandler()
    started = terminal_service.start_session(handler, {"cols": 90, "rows": 20}, "127.0.0.1")
    listed = terminal_service.list_sessions(handler)
    assert started["session_id"] == "sid"
    assert listed["sessions"] == ["sid"]


def test_terminal_service_read_write_resize_close():
    handler = _FakeHandler()
    read = terminal_service.read_session(handler, {"session_id": "sid", "max_bytes": 10})
    wrote = terminal_service.write_session(handler, {"session_id": "sid", "data": "ls"})
    resized = terminal_service.resize_session(handler, {"session_id": "sid", "cols": 100, "rows": 30})
    closed = terminal_service.close_session(handler, {"session_id": "sid"})
    assert read["max_bytes"] == 10
    assert wrote["written"] == 2
    assert resized["cols"] == 100
    assert closed["closed"] is True


def test_terminal_service_revoke_requires_session_id():
    handler = _FakeHandler()
    try:
        terminal_service.revoke_session(handler, {})
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "Missing session_id" in str(exc)


def test_terminal_service_upload_key_file(monkeypatch):
    monkeypatch.setattr(terminal_service.runtime_app, "_save_terminal_key_file", lambda _name, _b64, _root: ("id_ed25519", 8))
    monkeypatch.setattr(terminal_service.runtime_app, "load_app_config", lambda _root: {"terminal": {}})
    monkeypatch.setattr(terminal_service.runtime_app, "save_app_config", lambda cfg, _root: cfg)
    monkeypatch.setattr(terminal_service.runtime_app, "_build_terminal_launch_meta", lambda cfg: {"key_file": cfg["terminal"].get("key_file", "")})
    payload = terminal_service.upload_key_file({"file_name": "id_ed25519", "content_b64": "xxx"}, Path("."))
    assert payload["ok"] is True
    assert payload["file_name"] == "id_ed25519"
