from __future__ import annotations

from http import HTTPStatus
from urllib.parse import urlparse

from fcc.modules.docker import api as docker_api


class _FakeHandler:
    def __init__(self):
        self.lan_ok = True
        self.module_enabled = True
        self.body = {}
        self.errors = []
        self.sent = []
        self.last_action = ("", "")

    def _require_lan(self):
        return self.lan_ok

    def _error(self, message, status=HTTPStatus.BAD_REQUEST):
        self.errors.append((int(status), str(message)))

    def _send_json(self, payload):
        self.sent.append(payload)

    def _parse_body(self):
        return self.body

    def _docker_module_enabled(self):
        return self.module_enabled

    def _docker_status_payload(self, include_stats=True):
        return {"ok": True, "summary": {"total": 1}, "include_stats": include_stats}

    def _docker_images_payload(self):
        return {"ok": True, "images": [{"ref": "img:latest"}]}

    def _docker_safe_name(self, name):
        return str(name or "").strip()

    def _docker_container_action(self, name, action):
        self.last_action = (name, action)
        return True, ""

    def _docker_pull_image(self, image):
        return True, f"pulled {image}"

    def _docker_create_container(self, body):
        return True, "created"

    def _docker_remove_container(self, name, force=False):
        return True, "removed"

    def _docker_remove_image(self, image, force=False):
        return True, "removed"

    def _docker_container_logs(self, name, tail=160):
        return True, f"logs:{name}:{tail}"


def test_dispatch_get_logs_rejects_when_module_disabled():
    handler = _FakeHandler()
    handler.module_enabled = False
    handled = docker_api.dispatch_get(handler, urlparse("/api/docker/logs?name=qbt"), [])
    assert handled is True
    assert handler.errors == [(int(HTTPStatus.FORBIDDEN), "Docker module is disabled")]


def test_dispatch_post_action_rejects_invalid_action():
    handler = _FakeHandler()
    handler.body = {"name": "qbt", "action": "reload"}
    handled = docker_api.dispatch_post(handler, urlparse("/api/docker/action"))
    assert handled is True
    assert handler.errors == [(int(HTTPStatus.BAD_REQUEST), "Invalid Docker action")]


def test_dispatch_post_pull_success_payload_shape():
    handler = _FakeHandler()
    handler.body = {"image": "nginx:latest"}
    handled = docker_api.dispatch_post(handler, urlparse("/api/docker/image/pull"))
    assert handled is True
    assert not handler.errors
    assert handler.sent
    payload = handler.sent[-1]
    assert payload["ok"] is True
    assert "status" in payload
    assert "images" in payload


def test_dispatch_returns_true_when_lan_rejected():
    handler = _FakeHandler()
    handler.lan_ok = False
    handled = docker_api.dispatch_get(handler, urlparse("/api/docker/containers"), [])
    assert handled is True
    assert not handler.errors
    assert not handler.sent
