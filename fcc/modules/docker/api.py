"""Docker API dispatch helpers.

Keeps Docker route logic out of app.py while preserving existing
route contracts, response formats, and error semantics.
"""

from __future__ import annotations

from http import HTTPStatus
from urllib.parse import parse_qs

from . import service as docker_service


def _audit(
    handler,
    *,
    action: str,
    ok: bool,
    source: str,
    name: str = "",
    image: str = "",
    message: str = "",
    extra: dict | None = None,
) -> None:
    client_ip = ""
    try:
        if hasattr(handler, "_client_ip"):
            client_ip = str(handler._client_ip() or "").strip()
    except Exception:
        client_ip = ""
    docker_service.record_operation(
        action,
        ok=ok,
        source=source,
        name=name,
        image=image,
        message=message,
        client_ip=client_ip,
        extra=extra,
    )


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

    if path == "/api/docker/ops/history":
        if not handler._require_lan():
            return True
        if not handler._docker_module_enabled():
            handler._error("Docker module is disabled", status=HTTPStatus.FORBIDDEN)
            return True
        query = parse_qs(parsed.query)
        limit_raw = str(query.get("limit", ["200"])[0] or "200").strip()
        action = str(query.get("action", [""])[0] or "").strip()
        name = str(query.get("name", [""])[0] or "").strip()
        ok_raw = str(query.get("ok", [""])[0] or "").strip().lower()
        ok_flag = None
        if ok_raw in {"1", "true", "yes", "y"}:
            ok_flag = True
        elif ok_raw in {"0", "false", "no", "n"}:
            ok_flag = False
        try:
            limit = int(limit_raw)
        except Exception:
            limit = 200
        handler._send_json(
            {
                "ok": True,
                **docker_service.list_operation_history(
                    limit=limit,
                    action=action,
                    name=name,
                    ok=ok_flag,
                ),
            }
        )
        return True

    if path == "/api/docker/ops/export":
        if not handler._require_lan():
            return True
        if not handler._docker_module_enabled():
            handler._error("Docker module is disabled", status=HTTPStatus.FORBIDDEN)
            return True
        query = parse_qs(parsed.query)
        limit_raw = str(query.get("limit", ["5000"])[0] or "5000").strip()
        fmt = str(query.get("format", ["jsonl"])[0] or "jsonl").strip().lower()
        try:
            limit = int(limit_raw)
        except Exception:
            limit = 5000
        payload = docker_service.export_operation_history(fmt=fmt, limit=limit)
        handler._send_json(payload)
        return True

    return False


def dispatch_post(handler, parsed) -> bool:
    path = str(getattr(parsed, "path", "") or "")

    if path == "/api/docker/basic-op":
        if not handler._require_lan():
            return True
        if not handler._docker_module_enabled():
            handler._error("Docker module is disabled", status=HTTPStatus.FORBIDDEN)
            return True
        body = handler._parse_body() or {}
        action = str((body or {}).get("action", "") or "").strip().lower()
        name = handler._docker_safe_name(str((body or {}).get("name", "") or ""))
        if action not in {"status", "start", "stop", "restart", "install", "uninstall", "upgrade"}:
            handler._error("Invalid Docker basic action", status=HTTPStatus.BAD_REQUEST)
            return True

        if action == "status":
            payload = handler._docker_status_payload(include_stats=False)
            if name:
                containers = list((payload or {}).get("containers") or [])
                item = next((x for x in containers if str(x.get("name", "")).strip() == name), None)
                if item is None:
                    _audit(
                        handler,
                        action="status",
                        ok=False,
                        source=path,
                        name=name,
                        message="container not found",
                    )
                    handler._error("Container not found", status=HTTPStatus.NOT_FOUND)
                    return True
                _audit(handler, action="status", ok=True, source=path, name=name)
                handler._send_json({"ok": True, "container": item})
                return True
            _audit(handler, action="status", ok=True, source=path)
            handler._send_json(payload)
            return True

        if action in {"start", "stop", "restart"}:
            if not name:
                _audit(
                    handler,
                    action=action,
                    ok=False,
                    source=path,
                    message="invalid container name",
                )
                handler._error("Invalid container name", status=HTTPStatus.BAD_REQUEST)
                return True
            ok, msg = handler._docker_container_action(name, action)
            if not ok:
                _audit(handler, action=action, ok=False, source=path, name=name, message=msg)
                handler._error(f"docker {action} failed: {msg}", status=HTTPStatus.INTERNAL_SERVER_ERROR)
                return True
            _audit(handler, action=action, ok=True, source=path, name=name)
            handler._send_json({"ok": True, "action": action, "name": name})
            return True

        if action == "install":
            ok, msg = handler._docker_create_container(body)
            if not ok:
                _audit(
                    handler,
                    action="install",
                    ok=False,
                    source=path,
                    name=name,
                    image=str((body or {}).get("image", "") or ""),
                    message=msg,
                )
                handler._error(f"docker create failed: {msg}", status=HTTPStatus.INTERNAL_SERVER_ERROR)
                return True
            _audit(
                handler,
                action="install",
                ok=True,
                source=path,
                name=name,
                image=str((body or {}).get("image", "") or ""),
            )
            handler._send_json({"ok": True, "action": "install", "message": msg or "created"})
            return True

        if action == "uninstall":
            if not name:
                _audit(
                    handler,
                    action="uninstall",
                    ok=False,
                    source=path,
                    message="invalid container name",
                )
                handler._error("Invalid container name", status=HTTPStatus.BAD_REQUEST)
                return True
            force = bool((body or {}).get("force", True))
            ok, msg = handler._docker_remove_container(name, force=force)
            if not ok:
                _audit(handler, action="uninstall", ok=False, source=path, name=name, message=msg)
                handler._error(f"docker rm failed: {msg}", status=HTTPStatus.INTERNAL_SERVER_ERROR)
                return True
            image = handler._docker_safe_image(str((body or {}).get("image", "") or ""))
            remove_image = bool((body or {}).get("remove_image", False))
            if remove_image and image:
                ok_img, msg_img = handler._docker_remove_image(image, force=True)
                if not ok_img:
                    _audit(
                        handler,
                        action="uninstall",
                        ok=False,
                        source=path,
                        name=name,
                        image=image,
                        message=f"remove image failed: {msg_img}",
                    )
                    handler._error(f"docker rmi failed: {msg_img}", status=HTTPStatus.INTERNAL_SERVER_ERROR)
                    return True
            _audit(handler, action="uninstall", ok=True, source=path, name=name, image=image)
            handler._send_json({"ok": True, "action": "uninstall", "name": name})
            return True

        if action == "upgrade":
            image = handler._docker_safe_image(str((body or {}).get("image", "") or ""))
            restart_after_pull = bool((body or {}).get("restart", True))
            if not image and name:
                status = handler._docker_status_payload(include_stats=False)
                for item in list((status or {}).get("containers") or []):
                    if str(item.get("name", "")).strip() == name:
                        image = handler._docker_safe_image(str(item.get("image", "") or ""))
                        break
            if not image:
                _audit(
                    handler,
                    action="upgrade",
                    ok=False,
                    source=path,
                    name=name,
                    message="invalid image reference",
                )
                handler._error("Invalid image reference", status=HTTPStatus.BAD_REQUEST)
                return True
            if name and restart_after_pull and hasattr(handler, "_docker_upgrade_container"):
                ok_upgrade, detail = handler._docker_upgrade_container(
                    name=name,
                    image=image,
                    restart_after_pull=restart_after_pull,
                )
                if not ok_upgrade:
                    message = str((detail or {}).get("error", "") or "docker upgrade failed").strip()
                    _audit(
                        handler,
                        action="upgrade",
                        ok=False,
                        source=path,
                        name=name,
                        image=image,
                        message=message,
                        extra={
                            "rollback_attempted": bool((detail or {}).get("rollback_attempted", False)),
                            "rollback_ok": bool((detail or {}).get("rollback_ok", False)),
                        },
                    )
                    handler._error(message, status=HTTPStatus.INTERNAL_SERVER_ERROR)
                    return True
                _audit(
                    handler,
                    action="upgrade",
                    ok=True,
                    source=path,
                    name=name,
                    image=image,
                    extra={
                        "recreated": bool((detail or {}).get("recreated", False)),
                        "rollback_attempted": bool((detail or {}).get("rollback_attempted", False)),
                        "rollback_ok": bool((detail or {}).get("rollback_ok", False)),
                        "backup_id": str((detail or {}).get("backup_id", "") or ""),
                    },
                )
                handler._send_json(
                    {
                        "ok": True,
                        "action": "upgrade",
                        "name": name,
                        "image": image,
                        "restarted": True,
                        "recreated": bool((detail or {}).get("recreated", False)),
                        "rollback_attempted": bool((detail or {}).get("rollback_attempted", False)),
                        "rollback_ok": bool((detail or {}).get("rollback_ok", False)),
                        "backup_id": str((detail or {}).get("backup_id", "") or ""),
                    }
                )
                return True
            ok_pull, msg_pull = handler._docker_pull_image(image)
            if not ok_pull:
                _audit(handler, action="upgrade", ok=False, source=path, name=name, image=image, message=msg_pull)
                handler._error(f"docker pull failed: {msg_pull}", status=HTTPStatus.INTERNAL_SERVER_ERROR)
                return True
            if name and restart_after_pull:
                ok_restart, msg_restart = handler._docker_container_action(name, "restart")
                if not ok_restart:
                    _audit(
                        handler,
                        action="upgrade",
                        ok=False,
                        source=path,
                        name=name,
                        image=image,
                        message=f"restart failed: {msg_restart}",
                    )
                    handler._error(
                        f"docker restart failed: {msg_restart}",
                        status=HTTPStatus.INTERNAL_SERVER_ERROR,
                    )
                    return True
            _audit(
                handler,
                action="upgrade",
                ok=True,
                source=path,
                name=name,
                image=image,
                extra={"restarted": bool(name and restart_after_pull)},
            )
            handler._send_json(
                {
                    "ok": True,
                    "action": "upgrade",
                    "name": name,
                    "image": image,
                    "restarted": bool(name and restart_after_pull),
                }
            )
            return True

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
            _audit(
                handler,
                action=action or "action",
                ok=False,
                source=path,
                message="invalid container name",
            )
            handler._error("Invalid container name", status=HTTPStatus.BAD_REQUEST)
            return True
        if action not in {"start", "stop", "restart"}:
            _audit(handler, action=action or "action", ok=False, source=path, name=name, message="invalid action")
            handler._error("Invalid Docker action", status=HTTPStatus.BAD_REQUEST)
            return True
        ok, msg = handler._docker_container_action(name, action)
        if not ok:
            _audit(handler, action=action, ok=False, source=path, name=name, message=msg)
            handler._error(
                f"docker {action} failed: {msg}",
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )
            return True
        _audit(handler, action=action, ok=True, source=path, name=name)
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
            _audit(handler, action="pull", ok=False, source=path, image=image, message=msg)
            handler._error(
                f"docker pull failed: {msg}",
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )
            return True
        _audit(handler, action="pull", ok=True, source=path, image=image)
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
            _audit(
                handler,
                action="install",
                ok=False,
                source=path,
                name=str((body or {}).get("name", "") or ""),
                image=str((body or {}).get("image", "") or ""),
                message=msg,
            )
            handler._error(
                f"docker create failed: {msg}",
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )
            return True
        _audit(
            handler,
            action="install",
            ok=True,
            source=path,
            name=str((body or {}).get("name", "") or ""),
            image=str((body or {}).get("image", "") or ""),
        )
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
            _audit(handler, action="uninstall", ok=False, source=path, name=name, message=msg)
            handler._error(
                f"docker rm failed: {msg}",
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )
            return True
        _audit(handler, action="uninstall", ok=True, source=path, name=name)
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
            _audit(handler, action="image-remove", ok=False, source=path, image=image, message=msg)
            handler._error(
                f"docker rmi failed: {msg}",
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )
            return True
        _audit(handler, action="image-remove", ok=True, source=path, image=image)
        handler._send_json(handler._docker_images_payload())
        return True

    if path == "/api/docker/ops/history/clear":
        if not handler._require_lan():
            return True
        if not handler._docker_module_enabled():
            handler._error("Docker module is disabled", status=HTTPStatus.FORBIDDEN)
            return True
        payload = docker_service.clear_operation_history()
        handler._send_json(payload)
        return True

    return False
