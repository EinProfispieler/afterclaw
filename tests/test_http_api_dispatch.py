from __future__ import annotations

from http import HTTPStatus
from pathlib import Path
from urllib.parse import urlparse

from fcc.modules.http import api as http_api


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


def _dispatch(handler, parsed_path: str, fetch_fn):
    def _load(_root):
        return {
            "http_service": {
                "source_ip_pools": {"baidu": ["1.1.1.1"], "guangya": [], "aliyun": []},
                "source_ip_pool_source": "github",
            }
        }

    def _save(cfg, _root):
        return cfg

    def _norm_source(raw):
        return str(raw or "github")

    def _norm_pools(raw):
        base = {"baidu": [], "guangya": [], "aliyun": []}
        if isinstance(raw, dict):
            for k in base:
                v = raw.get(k, [])
                if isinstance(v, list):
                    base[k] = [str(x) for x in v]
        return base

    def _merge(local_raw, remote_raw):
        out = _norm_pools(local_raw)
        remote = _norm_pools(remote_raw)
        for k in out:
            out[k] = list(dict.fromkeys(out[k] + remote[k]))
        return out

    return http_api.dispatch_post(
        handler,
        urlparse(parsed_path),
        Path("."),
        _load,
        _save,
        _norm_source,
        fetch_fn,
        _norm_pools,
        _merge,
        ("baidu", "guangya", "aliyun"),
    )


def test_http_source_sync_success_merge():
    handler = _FakeHandler()
    handler.body = {"source": "github", "merge": True}

    def _fetch(_source):
        return {"pools": {"baidu": ["2.2.2.2"]}, "files_used": ["a"], "meta": {"ok": True}}

    handled = _dispatch(handler, "/api/http/source-ip-pools/sync", _fetch)
    assert handled is True
    assert not handler.errors
    assert handler.sent and handler.sent[-1]["ok"] is True
    assert handler.sent[-1]["mode"] == "merge"
    assert "2.2.2.2" in handler.sent[-1]["pools"]["baidu"]


def test_http_source_sync_bad_body_type():
    handler = _FakeHandler()
    handler.body = ["bad"]
    handled = _dispatch(handler, "/api/http/source-ip-pools/sync", lambda _source: {})
    assert handled is True
    assert handler.errors == [(int(HTTPStatus.BAD_REQUEST), "Request body must be a JSON object")]


def test_http_source_sync_fetch_value_error_maps_400():
    handler = _FakeHandler()
    handler.body = {"source": "bad"}

    def _fetch(_source):
        raise ValueError("unsupported source")

    handled = _dispatch(handler, "/api/http/source-ip-pools/sync", _fetch)
    assert handled is True
    assert handler.errors == [(int(HTTPStatus.BAD_REQUEST), "unsupported source")]


def test_http_source_sync_fetch_runtime_error_maps_502():
    handler = _FakeHandler()
    handler.body = {"source": "github"}

    def _fetch(_source):
        raise RuntimeError("network down")

    handled = _dispatch(handler, "/api/http/source-ip-pools/sync", _fetch)
    assert handled is True
    assert handler.errors == [(int(HTTPStatus.BAD_GATEWAY), "Source sync failed: network down")]
