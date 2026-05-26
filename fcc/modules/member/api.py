"""Member API dispatch helpers."""

from __future__ import annotations


def dispatch_get(handler, parsed) -> bool:
    path = str(getattr(parsed, "path", "") or "")
    if path == "/api/member/profile":
        return bool(handler._member_route_profile_get())
    if path == "/api/member/ddns/prefix-check":
        return bool(handler._member_route_prefix_check_get(parsed))
    return False


def dispatch_post(handler, parsed) -> bool:
    path = str(getattr(parsed, "path", "") or "")
    if path == "/api/member/login":
        return bool(handler._member_route_login_post())
    if path == "/api/member/register":
        return bool(handler._member_route_register_post())
    if path == "/api/member/profile/update":
        return bool(handler._member_route_profile_update_post())
    if path == "/api/member/logout":
        return bool(handler._member_route_logout_post())
    if path == "/api/member/email-change/request":
        return bool(handler._member_route_email_change_request_post())
    if path == "/api/member/password-reset/request":
        return bool(handler._member_route_password_reset_request_post())
    if path == "/api/member/ddns/config":
        return bool(handler._member_route_ddns_config_post())
    return False
