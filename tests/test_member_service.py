from __future__ import annotations

from http import HTTPStatus

from fcc.modules.member import service as member_service


def test_member_profile_get_requires_session():
    result = member_service.profile_get("tok", lambda _t: None)
    assert result.ok is False
    assert result.status == int(HTTPStatus.UNAUTHORIZED)


def test_member_login_missing_fields():
    result = member_service.login_post({}, lambda *a, **k: (200, {}), lambda *a, **k: "x")
    assert result.ok is False
    assert result.status == int(HTTPStatus.BAD_REQUEST)


def test_member_login_success_sets_cookie_token():
    def _remote_json(_path, method="POST", payload=None, headers=None):
        _ = method, payload, headers
        return 200, {"member": {"member_id": "AC1", "email": "a@b.c"}, "session_token": "up"}

    result = member_service.login_post(
        {"member_id": "AC1", "password": "secret"},
        _remote_json,
        lambda member_id, email, member=None, upstream_token="": f"sess-{member_id}-{email}-{upstream_token}",
    )
    assert result.ok is True
    assert result.cookie_token
    assert result.payload and result.payload["ok"] is True


def test_member_profile_update_requires_upstream_token():
    def _get_session(_token):
        return {"member_id": "AC1", "email": "a@b.c", "upstream_token": ""}

    result = member_service.profile_update_post(
        "tok",
        {"display_name": "abc", "email": "a@b.c", "avatar_color": 1},
        _get_session,
        lambda *a, **k: (200, {}),
        lambda *a, **k: "sess",
    )
    assert result.ok is False
    assert result.status == int(HTTPStatus.UNAUTHORIZED)


def test_member_prefix_check_invalid_prefix_returns_reason():
    result = member_service.prefix_check_get(
        "prefix=bad",
        "tok",
        lambda _t: {"member_id": "AC1"},
        lambda _raw: (_ for _ in ()).throw(ValueError("bad prefix")),
        lambda: [],
        lambda *a, **k: False,
    )
    assert result.ok is True
    assert result.payload and result.payload["available"] is False
    assert "bad prefix" in result.payload["reason"]


def test_member_email_change_requires_new_email():
    result = member_service.email_change_request_post(
        "tok",
        {},
        lambda _t: {"upstream_token": "up"},
        lambda *a, **k: (200, {}),
    )
    assert result.ok is False
    assert result.status == int(HTTPStatus.BAD_REQUEST)


def test_member_ddns_config_prefix_conflict():
    result = member_service.ddns_config_post(
        "tok",
        {"ddns_enabled": True, "ddns_prefix": "abc"},
        lambda _t: {"member_id": "AC1", "email": "a@b.c"},
        lambda: [{"member_id": "AC1", "email": "a@b.c", "ddns_prefix": "old", "prefix_change_ts": []}],
        lambda accounts, member_id, email: (0, accounts[0]),
        lambda accounts, member_id: (0, accounts[0]),
        lambda: 1700000000,
        lambda raw: raw,
        lambda accounts, prefix, exclude_member_id="": True,
        lambda accounts: None,
        lambda p: f"{p}.example.com",
        lambda item: item,
        2,
    )
    assert result.ok is False
    assert result.status == int(HTTPStatus.CONFLICT)


def test_member_logout_sets_clear_cookie_flag():
    result = member_service.logout_post()
    assert result.ok is True
    assert result.clear_cookie is True
