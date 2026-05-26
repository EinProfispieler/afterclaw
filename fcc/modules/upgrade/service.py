"""Upgrade domain service helpers."""

from __future__ import annotations

from dataclasses import dataclass
from http import HTTPStatus


@dataclass(frozen=True)
class UpgradeResult:
    ok: bool
    payload: dict | None = None
    error: str = ""
    status: int = int(HTTPStatus.OK)


def _ok(payload: dict) -> UpgradeResult:
    return UpgradeResult(ok=True, payload=payload)


def _err(message: str, status: int) -> UpgradeResult:
    return UpgradeResult(ok=False, error=str(message), status=int(status))


def status_payload(read_status) -> UpgradeResult:
    return _ok(read_status())


def check_version_payload(branch_raw: str, read_branch_payload) -> UpgradeResult:
    return _ok(read_branch_payload(branch_raw))


def run_upgrade(body, schedule_upgrade) -> UpgradeResult:
    payload = {} if body is None else body
    if not isinstance(payload, dict):
        return _err("Request body must be a JSON object", int(HTTPStatus.BAD_REQUEST))
    try:
        queued, status = schedule_upgrade(payload.get("branch"), payload.get("script_source"))
    except ValueError as exc:
        return _err(str(exc), int(HTTPStatus.BAD_REQUEST))
    except Exception as exc:
        return _err(f"Failed to start update: {exc}", int(HTTPStatus.INTERNAL_SERVER_ERROR))
    return _ok({"queued": bool(queued), "status": status})
