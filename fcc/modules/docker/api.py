"""Docker API dispatch helpers.

Keeps Docker route logic out of app.py while preserving existing
route contracts, response formats, and error semantics.
"""

from __future__ import annotations

from http import HTTPStatus
from urllib.parse import parse_qs


def dispatch_get(handler, parsed, recommendations) -> bool:
    path = str(getattr(parsed, "path", "") or "")

    if path == "/api/docker/containers":
        if not handler._require_lan():
            return True
        handler._send_json(handler._docker_status_payload())
        return True

    if path == "/api/docker/logs":
        if not handler._require_lan():
            return True
        if not handler._docker_module_enabled():
            handler._error("Docker module is disabled", status=HTTPStatus.FORBIDDEN)
            return True
        query = parse_qs(parsed.query)
        name = str(query.get("name", [""])[0] or "").strip()
        tail_raw = str(query.get("tail", ["160"])[0] or "160").strip()
        try:
            tail = int(tail_raw)
        except Exception:
            tail = 160
        ok, text = handler._docker_container_logs(name, tail=tail)
        if not ok:
            handler._error(text, status=HTTPStatus.BAD_REQUEST)
            return True
        handler._send_json({"ok": True, "name": name, "logs": text})
        return True

    if path == "/api/docker/recommendations":
        if not handler._require_lan():
            return True
        handler._send_json(
            {
                "ok": True,
                "items": recommendations,
                "categories": sorted(
                    {str(x.get("category", "") or "other") for x in recommendations}
                ),
            }
        )
        return True

    if path == "/api/docker/images":
        if not handler._require_lan():
            return True
        if not handler._docker_module_enabled():
            handler._error("Docker module is disabled", status=HTTPStatus.FORBIDDEN)
            return True
        payload = handler._docker_images_payload()
        if not payload.get("ok"):
            handler._error(
                str(payload.get("error") or "Docker image query failed"),
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )
            return True
        handler._send_json(payload)
        return True

    return False


def dispatch_post(handler, parsed) -> bool:
    path = str(getattr(parsed, "path", "") or "")

    if path == "/api/docker/action":
        if not handler._require_lan():
            return True
        if not handler._docker_module_enabled():
            handler._error("Docker module is disabled", status=HTTPStatus.FORBIDDEN)
            return True
        body = handler._parse_body()
        name = handler._docker_safe_name(str((body or {}).get("name", "") or ""))
        action = str((body or {}).get("action", "") or "").strip().lower()
        if not name:
            handler._error("Invalid container name", status=HTTPStatus.BAD_REQUEST)
            return True
        if action not in {"start", "stop", "restart"}:
            handler._error("Invalid Docker action", status=HTTPStatus.BAD_REQUEST)
            return True
        ok, msg = handler._docker_container_action(name, action)
        if not ok:
            handler._error(
                f"docker {action} failed: {msg}",
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )
            return True
        handler._send_json(handler._docker_status_payload())
        return True

    if path == "/api/docker/image/pull":
        if not handler._require_lan():
            return True
        if not handler._docker_module_enabled():
            handler._error("Docker module is disabled", status=HTTPStatus.FORBIDDEN)
            return True
        body = handler._parse_body()
        image = str((body or {}).get("image", "") or "").strip()
        ok, msg = handler._docker_pull_image(image)
        if not ok:
            handler._error(
                f"docker pull failed: {msg}",
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )
            return True
        handler._send_json(
            {
                "ok": True,
                "message": f"pulled {image}",
                "status": handler._docker_status_payload(include_stats=False).get(
                    "summary", {}
                ),
                "images": handler._docker_images_payload(),
            }
        )
        return True

    if path == "/api/docker/container/create":
        if not handler._require_lan():
            return True
        if not handler._docker_module_enabled():
            handler._error("Docker module is disabled", status=HTTPStatus.FORBIDDEN)
            return True
        body = handler._parse_body() or {}
        ok, msg = handler._docker_create_container(body)
        if not ok:
            handler._error(
                f"docker create failed: {msg}",
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )
            return True
        handler._send_json(handler._docker_status_payload())
        return True

    if path == "/api/docker/container/remove":
        if not handler._require_lan():
            return True
        if not handler._docker_module_enabled():
            handler._error("Docker module is disabled", status=HTTPStatus.FORBIDDEN)
            return True
        body = handler._parse_body()
        name = str((body or {}).get("name", "") or "").strip()
        force = bool((body or {}).get("force", False))
        ok, msg = handler._docker_remove_container(name, force=force)
        if not ok:
            handler._error(
                f"docker rm failed: {msg}",
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )
            return True
        handler._send_json(handler._docker_status_payload())
        return True

    if path == "/api/docker/image/remove":
        if not handler._require_lan():
            return True
        if not handler._docker_module_enabled():
            handler._error("Docker module is disabled", status=HTTPStatus.FORBIDDEN)
            return True
        body = handler._parse_body()
        image = str((body or {}).get("image", "") or "").strip()
        force = bool((body or {}).get("force", False))
        ok, msg = handler._docker_remove_image(image, force=force)
        if not ok:
            handler._error(
                f"docker rmi failed: {msg}",
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )
            return True
        handler._send_json(handler._docker_images_payload())
        return True

    return False
