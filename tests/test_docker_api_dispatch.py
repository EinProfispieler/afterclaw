from __future__ import annotations

from http import HTTPStatus
from urllib.parse import urlparse

import pytest

from fcc.modules.docker import api as docker_api
from fcc.modules.docker import service as docker_service


@pytest.fixture(autouse=True)
def _isolated_docker_ops_history(monkeypatch, tmp_path):
    monkeypatch.setenv("DOCKER_OPS_HISTORY_FILE", str(tmp_path / "docker_ops_history.jsonl"))
    monkeypatch.setattr(docker_service, "_DOCKER_OPS_LOADED", False)
    docker_service._DOCKER_OPS_HISTORY.clear()
    yield
    docker_service._DOCKER_OPS_HISTORY.clear()


class _FakeHandler:
    def __init__(self):
        self.lan_ok = True
        self.module_enabled = True
        self.body = {}
        self.errors = []
        self.sent = []
        self.sent_status = []
        self.last_action = ("", "")
        self.last_created = None
        self.last_removed = ("", False)
        self.last_upgrade = ("", "", True, False)

    def _require_lan(self):
        return self.lan_ok

    def _error(self, message, status=HTTPStatus.BAD_REQUEST):
        self.errors.append((int(status), str(message)))

    def _send_json(self, payload, status=HTTPStatus.OK, cors=False, extra_headers=None):
        self.sent.append(payload)
        self.sent_status.append(int(status))

    def _parse_body(self):
        return self.body

    def _docker_module_enabled(self):
        return self.module_enabled

    def _docker_status_payload(self, include_stats=True):
        return {
            "ok": True,
            "summary": {"total": 1},
            "containers": [{"name": "qbt", "image": "lscr.io/linuxserver/qbittorrent:latest"}],
            "include_stats": include_stats,
        }

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
        self.last_created = dict(body or {})
        return True, "created"

    def _docker_remove_container(self, name, force=False):
        self.last_removed = (str(name or ""), bool(force))
        return True, "removed"

    def _docker_remove_image(self, image, force=False):
        return True, "removed"

    def _docker_container_logs(self, name, tail=160):
        return True, f"logs:{name}:{tail}"

    def _docker_safe_image(self, image):
        return str(image or "").strip()

    def _docker_upgrade_container(self, name, image, restart_after_pull=True, allow_offline_local=False):
        self.last_upgrade = (
            str(name or ""),
            str(image or ""),
            bool(restart_after_pull),
            bool(allow_offline_local),
        )
        return True, {
            "recreated": True,
            "pulled": True,
            "pull_skipped": False,
            "rollback_attempted": False,
            "rollback_ok": False,
            "backup_id": f"{name}-preupgrade-123",
        }

    def _client_ip(self):
        return "127.0.0.1"


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


def test_dispatch_post_basic_op_restart_success():
    handler = _FakeHandler()
    handler.body = {"action": "restart", "name": "qbt"}
    handled = docker_api.dispatch_post(handler, urlparse("/api/docker/basic-op"))
    assert handled is True
    assert not handler.errors
    assert handler.sent[-1]["ok"] is True
    assert handler.last_action == ("qbt", "restart")


def test_dispatch_post_basic_op_upgrade_resolves_image_from_status():
    handler = _FakeHandler()

    def _status(include_stats=True):
        return {
            "ok": True,
            "containers": [{"name": "inkos", "image": "inkos/app:latest"}],
            "summary": {"total": 1},
        }

    handler._docker_status_payload = _status
    handler.body = {"action": "upgrade", "name": "inkos"}
    handled = docker_api.dispatch_post(handler, urlparse("/api/docker/basic-op"))
    assert handled is True
    assert not handler.errors
    assert handler.sent[-1]["ok"] is True
    assert handler.sent[-1]["image"] == "inkos/app:latest"
    assert handler.sent[-1]["recreated"] is True
    assert handler.last_upgrade == ("inkos", "inkos/app:latest", True, False)


def test_dispatch_post_basic_op_upgrade_passes_allow_offline_local_flag():
    handler = _FakeHandler()
    handler.body = {
        "action": "upgrade",
        "name": "inkos",
        "image": "inkos/app:latest",
        "allow_offline_local": True,
    }
    handled = docker_api.dispatch_post(handler, urlparse("/api/docker/basic-op"))
    assert handled is True
    assert not handler.errors
    assert handler.sent[-1]["ok"] is True
    assert handler.last_upgrade == ("inkos", "inkos/app:latest", True, True)


def test_dispatch_post_basic_op_upgrade_failure_returns_rollback_fields():
    handler = _FakeHandler()

    def _fail_upgrade(name, image, restart_after_pull=True, allow_offline_local=False):
        return False, {
            "error": "docker recreate failed: conflict",
            "pulled": False,
            "pull_skipped": True,
            "rollback_attempted": True,
            "rollback_ok": True,
            "backup_id": "inkos-preupgrade-123",
        }

    handler._docker_upgrade_container = _fail_upgrade
    handler.body = {
        "action": "upgrade",
        "name": "inkos",
        "image": "inkos/app:latest",
        "allow_offline_local": True,
    }
    handled = docker_api.dispatch_post(handler, urlparse("/api/docker/basic-op"))
    assert handled is True
    assert not handler.errors
    assert handler.sent_status[-1] == int(HTTPStatus.INTERNAL_SERVER_ERROR)
    payload = handler.sent[-1]
    assert payload["ok"] is False
    assert payload["rollback_attempted"] is True
    assert payload["rollback_ok"] is True
    assert payload["pull_skipped"] is True


def test_dispatch_post_basic_op_invalid_action():
    handler = _FakeHandler()
    handler.body = {"action": "exec", "name": "inkos"}
    handled = docker_api.dispatch_post(handler, urlparse("/api/docker/basic-op"))
    assert handled is True
    assert handler.errors == [(int(HTTPStatus.BAD_REQUEST), "Invalid Docker basic action")]


def test_dispatch_post_basic_op_status_by_name_success():
    handler = _FakeHandler()
    handler.body = {"action": "status", "name": "qbt"}
    handled = docker_api.dispatch_post(handler, urlparse("/api/docker/basic-op"))
    assert handled is True
    assert not handler.errors
    assert handler.sent[-1]["ok"] is True
    assert handler.sent[-1]["container"]["name"] == "qbt"


def test_dispatch_post_basic_op_install_success():
    handler = _FakeHandler()
    handler.body = {"action": "install", "name": "inkos", "image": "inkos/app:latest"}
    handled = docker_api.dispatch_post(handler, urlparse("/api/docker/basic-op"))
    assert handled is True
    assert not handler.errors
    assert handler.sent[-1]["ok"] is True
    assert handler.last_created["name"] == "inkos"


def test_dispatch_post_basic_op_uninstall_calls_remove_with_force_default():
    handler = _FakeHandler()
    handler.body = {"action": "uninstall", "name": "inkos"}
    handled = docker_api.dispatch_post(handler, urlparse("/api/docker/basic-op"))
    assert handled is True
    assert not handler.errors
    assert handler.sent[-1]["ok"] is True
    assert handler.last_removed == ("inkos", True)


def test_dispatch_get_ops_history_and_export_and_clear():
    docker_service.clear_operation_history()
    docker_service.record_operation("restart", ok=True, name="qbt", source="/api/docker/action", client_ip="127.0.0.1")
    docker_service.record_operation("upgrade", ok=False, name="inkos", source="/api/docker/basic-op", client_ip="127.0.0.1")

    handler = _FakeHandler()
    handled = docker_api.dispatch_get(handler, urlparse("/api/docker/ops/history?limit=10"), [])
    assert handled is True
    assert not handler.errors
    assert handler.sent[-1]["ok"] is True
    assert handler.sent[-1]["count"] >= 2

    handler_export = _FakeHandler()
    handled_export = docker_api.dispatch_get(handler_export, urlparse("/api/docker/ops/export?format=jsonl&limit=10"), [])
    assert handled_export is True
    assert not handler_export.errors
    assert handler_export.sent[-1]["ok"] is True
    assert handler_export.sent[-1]["format"] == "jsonl"
    assert "content" in handler_export.sent[-1]

    handler_clear = _FakeHandler()
    handled_clear = docker_api.dispatch_post(handler_clear, urlparse("/api/docker/ops/history/clear"))
    assert handled_clear is True
    assert not handler_clear.errors
    assert handler_clear.sent[-1]["ok"] is True
