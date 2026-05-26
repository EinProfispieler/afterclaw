from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qs, urlparse

from fcc.modules.status import api as status_api


class _FakeSampler:
    def detailed_snapshot(self, _fn):
        return {"rows": 3}


class _FakeHandler:
    def __init__(self):
        self.lan_ok = True
        self.sent = []
        self.process_detail_sampler = _FakeSampler()

    def _require_lan(self):
        return self.lan_ok

    def _send_json(self, payload, cors=False):
        self.sent.append((payload, bool(cors)))

    def _http_root_dir(self, _app_cfg=None):
        return Path("/tmp/http-root")

    def _downloads_effective_enabled(self):
        return True

    def _speed_snapshot(self):
        return {"speed": 10}

    def _metrics_history_payload(self):
        return {"history": [1, 2]}

    def _http_source_ip_pools(self):
        return {"isp_a": []}

    def _infer_process_source_by_row(self, _row, _pools):
        return "isp_a"

    def _transfer_snapshot(self):
        return {"transfers": []}

    def _control_status_payload(self, client_override=""):
        return {"client": client_override}


def _dispatch(handler, path: str):
    return status_api.dispatch_get(
        handler,
        urlparse(path),
        Path("."),
        lambda _root: {"http_service": {"default_dir": "downloads"}},
        lambda value: str(value),
        lambda _cfg: {"terminal": "meta"},
        lambda _cfg, _root: {"theme": "ok"},
        18090,
        "http",
        "localhost:18090",
        "1.0.0",
        "1.0.0",
        parse_qs,
    )


def test_status_base_dispatch():
    handler = _FakeHandler()
    handled = _dispatch(handler, "/api/base")
    assert handled is True
    payload, cors = handler.sent[-1]
    assert cors is False
    assert payload["web_port"] == 18090
    assert payload["public_base_url"] == "http://localhost:18090"
    assert payload["default_http_dir"] == "downloads"


def test_status_process_net_dispatch_with_cors():
    handler = _FakeHandler()
    handled = _dispatch(handler, "/api/process-net")
    assert handled is True
    payload, cors = handler.sent[-1]
    assert cors is True
    assert payload["rows"] == 3
    assert payload["current_version"] == "1.0.0"


def test_status_control_state_dispatch_client_query():
    handler = _FakeHandler()
    handled = _dispatch(handler, "/api/control/status?client=QBittorrent")
    assert handled is True
    payload, _cors = handler.sent[-1]
    assert payload["client"] == "qbittorrent"


def test_status_unknown_route_returns_false():
    handler = _FakeHandler()
    handled = _dispatch(handler, "/api/unknown")
    assert handled is False
