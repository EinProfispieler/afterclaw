from __future__ import annotations

from urllib.parse import urlparse

from fcc.modules.member import api as member_api


class _FakeHandler:
    def __init__(self):
        self.calls = []

    def _member_route_profile_get(self):
        self.calls.append("profile_get")
        return True

    def _member_route_prefix_check_get(self, _parsed):
        self.calls.append("prefix_check_get")
        return True

    def _member_route_login_post(self):
        self.calls.append("login_post")
        return True

    def _member_route_register_post(self):
        self.calls.append("register_post")
        return True

    def _member_route_profile_update_post(self):
        self.calls.append("profile_update_post")
        return True

    def _member_route_logout_post(self):
        self.calls.append("logout_post")
        return True

    def _member_route_email_change_request_post(self):
        self.calls.append("email_change_post")
        return True

    def _member_route_password_reset_request_post(self):
        self.calls.append("password_reset_post")
        return True

    def _member_route_ddns_config_post(self):
        self.calls.append("ddns_config_post")
        return True


def test_member_get_profile_dispatch():
    handler = _FakeHandler()
    handled = member_api.dispatch_get(handler, urlparse("/api/member/profile"))
    assert handled is True
    assert handler.calls == ["profile_get"]

    handled = member_api.dispatch_get(handler, urlparse("/api/member/ddns/prefix-check?prefix=abc"))
    assert handled is True
    assert handler.calls[-1] == "prefix_check_get"


def test_member_post_dispatches_known_routes():
    handler = _FakeHandler()
    assert member_api.dispatch_post(handler, urlparse("/api/member/login")) is True
    assert member_api.dispatch_post(handler, urlparse("/api/member/register")) is True
    assert member_api.dispatch_post(handler, urlparse("/api/member/profile/update")) is True
    assert member_api.dispatch_post(handler, urlparse("/api/member/logout")) is True
    assert member_api.dispatch_post(handler, urlparse("/api/member/email-change/request")) is True
    assert member_api.dispatch_post(handler, urlparse("/api/member/password-reset/request")) is True
    assert member_api.dispatch_post(handler, urlparse("/api/member/ddns/config")) is True
    assert handler.calls == [
        "login_post",
        "register_post",
        "profile_update_post",
        "logout_post",
        "email_change_post",
        "password_reset_post",
        "ddns_config_post",
    ]


def test_member_dispatch_unknown_route_returns_false():
    handler = _FakeHandler()
    assert member_api.dispatch_get(handler, urlparse("/api/member/unknown")) is False
    assert member_api.dispatch_post(handler, urlparse("/api/member/unknown")) is False
