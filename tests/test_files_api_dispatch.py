from __future__ import annotations

from http import HTTPStatus
from pathlib import Path
from urllib.parse import urlparse

from fcc.modules.files import api as files_api


class _FakeHandler:
    def __init__(self, tmp_root: Path):
        self.tmp_root = tmp_root
        self.lan_ok = True
        self.sent = []
        self.errors = []

    def _require_lan(self):
        return self.lan_ok

    def _send_json(self, payload):
        self.sent.append(payload)

    def _error(self, message, status=HTTPStatus.BAD_REQUEST):
        self.errors.append((int(status), str(message)))

    def _http_path_scan(self, path_raw: str):
        return {"ok": True, "path": path_raw}

    def _http_root_from_raw(self, root_raw, require_exists=True):
        return self.tmp_root if root_raw in (None, "", "default") else Path(root_raw)

    def _http_root_dir(self):
        return self.tmp_root

    def _list_child_directories(self, rel_dir: str, root_dir: Path):
        return [{"name": "sub", "relative_path": f"{rel_dir}/sub".strip("/")}]

    def _directory_stats(self, rel_dir: str, root_dir: Path):
        return {"files": 1, "dirs": 1, "base": rel_dir}

    def _is_hidden_system_name(self, name: str):
        return name.startswith(".")

    def _build_http_url(self, rel_file: str):
        return f"/http/{rel_file}"


def _safe_relative_path(value):
    return str(value or ".")


def _ensure_under_root(root: Path, target: Path):
    root_resolved = root.resolve()
    target_resolved = target.resolve()
    if root_resolved == target_resolved or root_resolved in target_resolved.parents:
        return target_resolved
    raise ValueError("Path escapes root")


def _human_size(size: int) -> str:
    return f"{size} B"


def test_files_get_path_scan_missing_path_returns_400(tmp_path: Path):
    handler = _FakeHandler(tmp_path)
    handled = files_api.dispatch_get(
        handler,
        urlparse("/api/http/path-scan"),
        _safe_relative_path,
        _ensure_under_root,
        _human_size,
    )
    assert handled is True
    assert handler.errors and handler.errors[-1][0] == 400


def test_files_get_directories_dispatch_success(tmp_path: Path):
    handler = _FakeHandler(tmp_path)
    handled = files_api.dispatch_get(
        handler,
        urlparse("/api/directories?dir=media&stats=1"),
        _safe_relative_path,
        _ensure_under_root,
        _human_size,
    )
    assert handled is True
    assert handler.sent
    payload = handler.sent[-1]
    assert payload["current_dir"] == "media"
    assert payload["stats"]["files"] == 1
    assert "http_root_dir" in payload


def test_files_get_files_dispatch_success_and_hidden_filtered(tmp_path: Path):
    visible = tmp_path / "a.txt"
    hidden = tmp_path / ".hidden.txt"
    nested = tmp_path / "sub" / "b.txt"
    nested.parent.mkdir(parents=True, exist_ok=True)
    visible.write_text("A", encoding="utf-8")
    hidden.write_text("H", encoding="utf-8")
    nested.write_text("BB", encoding="utf-8")

    handler = _FakeHandler(tmp_path)
    handled = files_api.dispatch_get(
        handler,
        urlparse("/api/files?dir=."),
        _safe_relative_path,
        _ensure_under_root,
        _human_size,
    )
    assert handled is True
    assert handler.sent
    items = handler.sent[-1]["items"]
    rel_paths = [item["relative_path"] for item in items]
    assert rel_paths == ["a.txt", "sub/b.txt"]
    assert all(item["http_url"].startswith("/http/") for item in items)


def test_files_get_files_directory_not_found(tmp_path: Path):
    handler = _FakeHandler(tmp_path)
    handled = files_api.dispatch_get(
        handler,
        urlparse("/api/files?dir=missing"),
        _safe_relative_path,
        _ensure_under_root,
        _human_size,
    )
    assert handled is True
    assert handler.errors and handler.errors[-1][0] == 404
