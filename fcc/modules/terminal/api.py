"""Terminal API dispatch helpers."""

from __future__ import annotations

from http import HTTPStatus

from fcc.modules.terminal import service as terminal_service


def dispatch_post(handler, parsed, app_root) -> bool:
    path = str(getattr(parsed, "path", "") or "")

    if path == "/api/terminal/start":
        if not handler._require_lan():
            return True
        body = handler._parse_body()
        try:
            payload = terminal_service.start_session(handler, body, handler._client_ip())
        except Exception as exc:
            handler._error(f"Terminal connection failed: {exc}", status=HTTPStatus.BAD_REQUEST)
            return True
        handler._send_json(payload)
        return True

    if path == "/api/terminal/sessions":
        if not handler._require_lan():
            return True
        try:
            payload = terminal_service.list_sessions(handler)
        except Exception as exc:
            handler._error(f"List sessions failed: {exc}", status=HTTPStatus.BAD_REQUEST)
            return True
        handler._send_json(payload)
        return True

    if path == "/api/terminal/history":
        if not handler._require_lan():
            return True
        body = handler._parse_body()
        try:
            payload = terminal_service.history(handler, body)
        except Exception as exc:
            handler._error(f"History fetch failed: {exc}", status=HTTPStatus.BAD_REQUEST)
            return True
        handler._send_json(payload)
        return True

    if path == "/api/terminal/history/clear":
        if not handler._require_lan():
            return True
        try:
            payload = terminal_service.clear_history(handler)
        except Exception as exc:
            handler._error(f"History clear failed: {exc}", status=HTTPStatus.BAD_REQUEST)
            return True
        handler._send_json(payload)
        return True

    if path == "/api/terminal/read":
        if not handler._require_lan():
            return True
        body = handler._parse_body()
        try:
            payload = terminal_service.read_session(handler, body)
        except Exception as exc:
            handler._error(f"Read failed: {exc}", status=HTTPStatus.BAD_REQUEST)
            return True
        handler._send_json(payload)
        return True

    if path == "/api/terminal/write":
        if not handler._require_lan():
            return True
        body = handler._parse_body()
        try:
            payload = terminal_service.write_session(handler, body)
        except Exception as exc:
            handler._error(f"Write failed: {exc}", status=HTTPStatus.BAD_REQUEST)
            return True
        handler._send_json(payload)
        return True

    if path == "/api/terminal/resize":
        if not handler._require_lan():
            return True
        body = handler._parse_body()
        try:
            payload = terminal_service.resize_session(handler, body)
        except Exception as exc:
            handler._error(f"Resize failed: {exc}", status=HTTPStatus.BAD_REQUEST)
            return True
        handler._send_json(payload)
        return True

    if path == "/api/terminal/close":
        if not handler._require_lan():
            return True
        body = handler._parse_body()
        try:
            payload = terminal_service.close_session(handler, body)
        except Exception as exc:
            handler._error(f"Close failed: {exc}", status=HTTPStatus.BAD_REQUEST)
            return True
        handler._send_json(payload)
        return True

    if path == "/api/terminal/revoke":
        if not handler._require_lan():
            return True
        body = handler._parse_body()
        try:
            payload = terminal_service.revoke_session(handler, body)
        except ValueError as exc:
            handler._error(str(exc), status=HTTPStatus.BAD_REQUEST)
            return True
        except Exception as exc:
            handler._error(f"Revoke failed: {exc}", status=HTTPStatus.BAD_REQUEST)
            return True
        handler._send_json(payload)
        return True

    if path == "/api/terminal/key-file":
        if not handler._require_lan():
            return True
        body = handler._parse_body()
        try:
            payload = terminal_service.upload_key_file(body, app_root)
        except ValueError as exc:
            handler._error(str(exc), status=HTTPStatus.BAD_REQUEST)
            return True
        except Exception as exc:
            handler._error(f"Key file save failed: {exc}", status=HTTPStatus.INTERNAL_SERVER_ERROR)
            return True
        handler._send_json(payload)
        return True

    return False
