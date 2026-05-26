"""Naming and subtitles API dispatch helpers."""

from __future__ import annotations

import fcc.subtitle_align as subtitle_align
import fcc.subtitle_uploads as subtitle_uploads
from naming.clean_names import apply_rename_plan, build_rename_plan

from fcc.modules.naming import service as naming_service


def dispatch_post(handler, parsed, app_root, load_app_config, safe_relative_path) -> bool:
    path = str(getattr(parsed, "path", "") or "")

    if path == "/api/subtitles/upload":
        if not handler._require_lan():
            return True
        result = naming_service.subtitles_upload(
            handler._parse_body(),
            app_root=app_root,
            http_root_dir=handler._http_root_dir(),
            load_app_config=load_app_config,
            safe_relative_path=safe_relative_path,
            handle_upload_payload=subtitle_uploads.handle_upload_payload,
        )
        if not result.ok:
            handler._error(result.error, status=result.status)
            return True
        handler._send_json(result.payload or {"ok": False})
        return True

    if path == "/api/clean/preview":
        if not handler._require_lan():
            return True
        result = naming_service.clean_preview(
            handler.storage_root,
            handler._parse_body(),
            build_rename_plan=build_rename_plan,
        )
        if not result.ok:
            handler._error(result.error, status=result.status)
            return True
        handler._send_json(result.payload or {"ok": False})
        return True

    if path == "/api/subtitle-align/preview":
        if not handler._require_lan():
            return True
        result = naming_service.subtitle_align_preview(
            handler.storage_root,
            handler._parse_body(),
            build_alignment_plan=subtitle_align.build_alignment_plan,
            simplify_plan=subtitle_align.simplify_plan,
        )
        if not result.ok:
            handler._error(result.error, status=result.status)
            return True
        handler._send_json(result.payload or {"ok": False})
        return True

    if path == "/api/clean/apply":
        if not handler._require_lan():
            return True
        result = naming_service.apply_moves(
            handler.storage_root,
            handler._parse_body(),
            apply_rename_plan=apply_rename_plan,
            error_prefix="Execution failed",
        )
        if not result.ok:
            handler._error(result.error, status=result.status)
            return True
        handler._send_json(result.payload or {"ok": False})
        return True

    if path == "/api/subtitle-align/apply":
        if not handler._require_lan():
            return True
        result = naming_service.apply_moves(
            handler.storage_root,
            handler._parse_body(),
            apply_rename_plan=apply_rename_plan,
            error_prefix="Subtitle align apply failed",
        )
        if not result.ok:
            handler._error(result.error, status=result.status)
            return True
        handler._send_json(result.payload or {"ok": False})
        return True

    return False
