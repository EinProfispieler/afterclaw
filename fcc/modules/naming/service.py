"""Naming and subtitles domain service helpers."""

from __future__ import annotations

from dataclasses import dataclass
from http import HTTPStatus


@dataclass(frozen=True)
class NamingResult:
    ok: bool
    payload: dict | None = None
    error: str = ""
    status: int = int(HTTPStatus.OK)


def _ok(payload: dict) -> NamingResult:
    return NamingResult(ok=True, payload=payload)


def _err(message: str, status: int) -> NamingResult:
    return NamingResult(ok=False, error=str(message), status=int(status))


def clean_preview(storage_root, body: dict, build_rename_plan) -> NamingResult:
    rel = str((body or {}).get("dir", ".") or ".")
    target = str((body or {}).get("target", "both") or "both")
    if target not in ("both", "files", "dirs"):
        return _err("target must be both / files / dirs", int(HTTPStatus.BAD_REQUEST))
    try:
        plan = build_rename_plan(
            storage_root,
            rel,
            target=target,
            recursive=bool((body or {}).get("recursive", False)),
            remove_substrings=str((body or {}).get("remove_substrings", "") or ""),
            strip_cjk=bool((body or {}).get("strip_cjk", False)),
            move_season_before_year=bool(
                (body or {}).get("move_season_before_year")
                or (body or {}).get("reorder_season", False)
            ),
        )
    except FileNotFoundError as exc:
        return _err(str(exc), int(HTTPStatus.NOT_FOUND))
    except ValueError as exc:
        return _err(str(exc), int(HTTPStatus.BAD_REQUEST))
    except Exception as exc:
        return _err(f"Preview failed: {exc}", int(HTTPStatus.INTERNAL_SERVER_ERROR))
    return _ok(
        {
            "moves": [
                {
                    "old_rel": x.old_rel,
                    "new_rel": x.new_rel,
                    "kind": x.kind,
                    "skip": x.skip,
                    "error": x.error,
                }
                for x in plan
            ]
        }
    )


def subtitle_align_preview(storage_root, body: dict, build_alignment_plan, simplify_plan) -> NamingResult:
    try:
        rel = str((body or {}).get("dir", ".") or ".")
        recursive = bool((body or {}).get("recursive", False))
        plan = build_alignment_plan(storage_root, rel, recursive=recursive)
    except FileNotFoundError as exc:
        return _err(str(exc), int(HTTPStatus.NOT_FOUND))
    except ValueError as exc:
        return _err(str(exc), int(HTTPStatus.BAD_REQUEST))
    except Exception as exc:
        return _err(f"Subtitle align preview failed: {exc}", int(HTTPStatus.INTERNAL_SERVER_ERROR))
    return _ok({"moves": simplify_plan(plan)})


def apply_moves(storage_root, body: dict, apply_rename_plan, *, error_prefix: str) -> NamingResult:
    moves = (body or {}).get("moves")
    if not isinstance(moves, list) or not moves:
        return _err("moves must be a non-empty array", int(HTTPStatus.BAD_REQUEST))
    try:
        results = apply_rename_plan(storage_root, moves)
    except Exception as exc:
        return _err(f"{error_prefix}: {exc}", int(HTTPStatus.INTERNAL_SERVER_ERROR))
    return _ok({"results": results})


def subtitles_upload(
    body: dict,
    *,
    app_root,
    http_root_dir,
    load_app_config,
    safe_relative_path,
    handle_upload_payload,
) -> NamingResult:
    if not isinstance(body, dict):
        return _err("Request body must be a JSON object", int(HTTPStatus.BAD_REQUEST))
    try:
        rel_dir = safe_relative_path(str(body.get("dir", ".") or "."))
        cfg = load_app_config(app_root)
        http_cfg = (cfg or {}).get("http_service") if isinstance(cfg, dict) else {}
        perm = (
            (http_cfg or {}).get("subtitle_permissions", {})
            if isinstance(http_cfg, dict)
            else {}
        )
        result = handle_upload_payload(http_root_dir, rel_dir, body, perm)
    except FileNotFoundError as exc:
        return _err(str(exc), int(HTTPStatus.NOT_FOUND))
    except ValueError as exc:
        return _err(str(exc), int(HTTPStatus.BAD_REQUEST))
    except Exception as exc:
        return _err(f"Subtitle upload failed: {exc}", int(HTTPStatus.INTERNAL_SERVER_ERROR))
    return _ok(result)
