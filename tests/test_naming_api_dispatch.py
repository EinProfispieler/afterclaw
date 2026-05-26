from __future__ import annotations

from http import HTTPStatus
from pathlib import Path
from urllib.parse import urlparse

from fcc.modules.naming import api as naming_api


class _FakeHandler:
    def __init__(self):
        self.storage_root = Path(".")
        self.lan_ok = True
        self.body = {}
        self.errors = []
        self.sent = []

    def _require_lan(self):
        return self.lan_ok

    def _parse_body(self):
        return self.body

    def _http_root_dir(self):
        return Path(".")

    def _error(self, message, status=HTTPStatus.BAD_REQUEST):
        self.errors.append((int(status), str(message)))

    def _send_json(self, payload):
        self.sent.append(payload)


def test_naming_dispatch_clean_preview_success(monkeypatch):
    handler = _FakeHandler()
    monkeypatch.setattr(
        naming_api.naming_service,
        "clean_preview",
        lambda *a, **k: naming_api.naming_service.NamingResult(ok=True, payload={"moves": []}),
    )
    handled = naming_api.dispatch_post(handler, urlparse("/api/clean/preview"), Path("."), lambda _r: {}, lambda x: x)
    assert handled is True
    assert handler.sent == [{"moves": []}]


def test_naming_dispatch_subtitle_upload_error(monkeypatch):
    handler = _FakeHandler()
    monkeypatch.setattr(
        naming_api.naming_service,
        "subtitles_upload",
        lambda *a, **k: naming_api.naming_service.NamingResult(
            ok=False, error="bad upload", status=int(HTTPStatus.BAD_REQUEST)
        ),
    )
    handled = naming_api.dispatch_post(handler, urlparse("/api/subtitles/upload"), Path("."), lambda _r: {}, lambda x: x)
    assert handled is True
    assert handler.errors == [(int(HTTPStatus.BAD_REQUEST), "bad upload")]


def test_naming_dispatch_unknown_route_returns_false():
    handler = _FakeHandler()
    handled = naming_api.dispatch_post(handler, urlparse("/api/naming/none"), Path("."), lambda _r: {}, lambda x: x)
    assert handled is False
