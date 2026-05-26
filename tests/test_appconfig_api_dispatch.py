from __future__ import annotations

from pathlib import Path
import threading
from urllib.parse import urlparse

from fcc.modules.appconfig import api as appconfig_api


class _FakeDDNS:
    @staticmethod
    def config_path(_root):
        class _Missing:
            @staticmethod
            def exists():
                return False

        return _Missing()

    @staticmethod
    def service_action(_root, _action):
        return True, "ok"


class _FakeHandler:
    transfer_recent_ttl_sec = 0
    downloads_enabled = False

    def __init__(self):
        self.lan_ok = True
        self.body = {}
        self.sent = []
        self.errors = []
        self.control_lock = threading.Lock()
        self.qbt_candidates = []
        self.ddns_candidates = []
        self.downloads_enabled = True

    def _require_lan(self):
        return self.lan_ok

    def _send_json(self, payload):
        self.sent.append(payload)

    def _error(self, message, status=400):
        self.errors.append((int(status), str(message)))

    def _parse_body(self):
        return self.body

    def _qbt_module_enabled(self, _cfg=None):
        return False

    def _ddns_module_enabled(self, _cfg=None):
        return False

    def _shareclip_module_enabled(self, _cfg=None):
        return False

    def _http_module_enabled(self, _cfg=None):
        return True

    def _http_root_from_raw(self, value, app_cfg=None, require_exists=True):
        return Path(value or "/tmp")

    def _cut_http_downloads_once(self):
        return None

    def _resolve_existing_unit(self, _candidates):
        return {"load_state": "not-found"}

    def _discover_unit_by_keywords(self, _keywords):
        return {"load_state": "not-found"}

    def _bt_service_keywords(self, _client):
        return []

    def _service_action(self, _unit, _action):
        return True, "ok"

    def _qbt_reset_stats_cache(self):
        return None


def _dispatch_get(handler, cfg):
    return appconfig_api.dispatch_get(
        handler,
        urlparse("/api/app-config"),
        Path("."),
        lambda _root: cfg,
    )


def _dispatch_post(handler, cfg):
    def _load(_root):
        return cfg

    def _save(next_cfg, _root):
        return next_cfg

    return appconfig_api.dispatch_post(
        handler,
        urlparse("/api/app-config"),
        Path("."),
        _load,
        _save,
        lambda raw, default: int(raw if raw is not None else default),
        lambda value: str(value or "."),
        lambda pools: pools if isinstance(pools, dict) else {},
        lambda source: str(source or "github"),
        lambda raw, default: int(raw if raw is not None else default),
        lambda raw, default: int(raw if raw is not None else default),
        lambda name: str(name or "").strip(),
        lambda preset: str(preset or "default"),
        lambda root, target: target,
        lambda _cfg, _root: {"theme": "ok"},
        18090,
        18090,
        600,
        _FakeDDNS,
    )


def test_appconfig_get_dispatch():
    handler = _FakeHandler()
    cfg = {"web_port": 18090}
    handled = _dispatch_get(handler, cfg)
    assert handled is True
    assert handler.sent == [{"config": cfg}]


def test_appconfig_post_rejects_non_object_body():
    handler = _FakeHandler()
    handler.body = ["bad"]
    handled = _dispatch_post(handler, {"web_port": 18090})
    assert handled is True
    assert handler.errors == [(400, "Request body must be a JSON object")]


def test_appconfig_post_rejects_invalid_web_port():
    handler = _FakeHandler()
    handler.body = {"web_port": "abc"}
    handled = _dispatch_post(handler, {"web_port": 18090})
    assert handled is True
    assert handler.errors == [(400, "Service port must be an integer in 1-65535")]


def test_appconfig_post_minimal_success():
    handler = _FakeHandler()
    handler.body = {}
    handled = _dispatch_post(handler, {"web_port": 18090, "http_service": {"transfer_recent_ttl_sec": 900}})
    assert handled is True
    assert not handler.errors
    assert handler.sent
    payload = handler.sent[-1]
    assert payload["ok"] is True
    assert payload["running_web_port"] == 18090
    assert payload["web_port_restart_required"] is False
