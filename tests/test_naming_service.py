from __future__ import annotations

from http import HTTPStatus

from fcc.modules.naming import service as naming_service


class _PlanItem:
    def __init__(self, old_rel, new_rel, kind="file", skip=False, error=""):
        self.old_rel = old_rel
        self.new_rel = new_rel
        self.kind = kind
        self.skip = skip
        self.error = error


def test_clean_preview_rejects_invalid_target():
    result = naming_service.clean_preview("/tmp", {"target": "bad"}, lambda *a, **k: [])
    assert result.ok is False
    assert result.status == int(HTTPStatus.BAD_REQUEST)


def test_clean_preview_success_payload_shape():
    result = naming_service.clean_preview(
        "/tmp",
        {"dir": ".", "target": "both"},
        lambda *a, **k: [_PlanItem("a", "b")],
    )
    assert result.ok is True
    assert result.payload and len(result.payload["moves"]) == 1


def test_apply_moves_requires_non_empty_array():
    result = naming_service.apply_moves("/tmp", {"moves": []}, lambda *a, **k: [], error_prefix="Execution failed")
    assert result.ok is False
    assert result.status == int(HTTPStatus.BAD_REQUEST)


def test_subtitles_upload_requires_json_object():
    result = naming_service.subtitles_upload(
        None,
        app_root=".",
        http_root_dir="/tmp",
        load_app_config=lambda _r: {},
        safe_relative_path=lambda x: x,
        handle_upload_payload=lambda *a, **k: {"ok": True},
    )
    assert result.ok is False
    assert result.status == int(HTTPStatus.BAD_REQUEST)
