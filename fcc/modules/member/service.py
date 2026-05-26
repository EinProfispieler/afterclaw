"""Member domain service helpers."""

from __future__ import annotations

from dataclasses import dataclass
from http import HTTPStatus
from urllib.parse import parse_qs


@dataclass(frozen=True)
class MemberResult:
    ok: bool
    payload: dict | None = None
    error: str = ""
    status: int = int(HTTPStatus.OK)
    cookie_token: str | None = None
    clear_cookie: bool = False


def _ok(payload: dict, *, cookie_token: str | None = None, clear_cookie: bool = False) -> MemberResult:
    return MemberResult(ok=True, payload=payload, cookie_token=cookie_token, clear_cookie=clear_cookie)


def _err(message: str, status: int) -> MemberResult:
    return MemberResult(ok=False, error=str(message), status=int(status))


def _session_or_unauthorized(token: str, get_session) -> tuple[dict | None, MemberResult | None]:
    sess = get_session(token)
    if not sess:
        return None, _err("Member session invalid", int(HTTPStatus.UNAUTHORIZED))
    return sess, None


def profile_get(token: str, get_session) -> MemberResult:
    sess, err = _session_or_unauthorized(token, get_session)
    if err:
        return err
    member = sess.get("member") if isinstance(sess.get("member"), dict) else {}
    if not member:
        member = {
            "member_id": str(sess.get("member_id", "") or ""),
            "email": str(sess.get("email", "") or ""),
        }
    return _ok({"ok": True, "member": member})


def login_post(body: dict, remote_json, issue_session) -> MemberResult:
    member_id = str((body or {}).get("member_id", "") or "").strip()
    password = str((body or {}).get("password", "") or "").strip()
    if not member_id or not password:
        return _err("member_id and password are required", int(HTTPStatus.BAD_REQUEST))
    status, remote = remote_json(
        "/api/member/login",
        method="POST",
        payload={"member_id": member_id, "password": password},
    )
    if status < 200 or status >= 300:
        msg = str((remote or {}).get("detail") or (remote or {}).get("error") or "Invalid member credentials")
        return _err(msg, status if status in {400, 401, 403, 404, 429} else int(HTTPStatus.FORBIDDEN))
    remote_member = (remote or {}).get("member") if isinstance((remote or {}).get("member"), dict) else {}
    remote_member_id = str((remote_member or {}).get("member_id", "") or "").strip()
    remote_email = str((remote_member or {}).get("email", "") or "").strip()
    upstream_token = str((remote or {}).get("session_token", "") or "").strip()
    if not remote_member_id:
        return _err("Remote auth payload invalid", int(HTTPStatus.BAD_GATEWAY))
    session_token = issue_session(
        remote_member_id,
        remote_email,
        member=remote_member,
        upstream_token=upstream_token,
    )
    return _ok(
        {
            "ok": True,
            "session_token": session_token,
            "member": remote_member,
        },
        cookie_token=session_token,
    )


def register_post(body: dict, remote_json) -> MemberResult:
    password = str((body or {}).get("password", "") or "").strip()
    display_name = str((body or {}).get("display_name", "") or "").strip()
    email = str((body or {}).get("email", "") or "").strip()
    avatar_color = int((body or {}).get("avatar_color", 0) or 0)
    if not password or not display_name:
        return _err("password and display_name are required", int(HTTPStatus.BAD_REQUEST))
    if len(password) < 6:
        return _err("password length must be >= 6", int(HTTPStatus.BAD_REQUEST))
    if len(display_name) > 64:
        return _err("display_name too long", int(HTTPStatus.BAD_REQUEST))
    if len(email) > 128:
        return _err("email too long", int(HTTPStatus.BAD_REQUEST))
    if avatar_color < 0 or avatar_color > 7:
        avatar_color = 0
    status, remote = remote_json(
        "/api/member/register",
        method="POST",
        payload={
            "password": password,
            "display_name": display_name,
            "email": email,
            "avatar_color": avatar_color,
        },
    )
    if status < 200 or status >= 300:
        msg = str((remote or {}).get("detail") or (remote or {}).get("error") or "Registration failed")
        return _err(msg, status if status in {400, 401, 403, 404, 409, 429} else int(HTTPStatus.BAD_GATEWAY))
    return _ok(remote)


def profile_update_post(token: str, body: dict, get_session, remote_json, issue_session) -> MemberResult:
    sess, err = _session_or_unauthorized(token, get_session)
    if err:
        return err
    display_name = str((body or {}).get("display_name", "") or "").strip()
    email = str((body or {}).get("email", "") or "").strip()
    avatar_color = int((body or {}).get("avatar_color", 0) or 0)
    if not display_name:
        return _err("display_name is required", int(HTTPStatus.BAD_REQUEST))
    if len(display_name) > 64:
        return _err("display_name too long", int(HTTPStatus.BAD_REQUEST))
    if len(email) > 128:
        return _err("email too long", int(HTTPStatus.BAD_REQUEST))
    if avatar_color < 0 or avatar_color > 7:
        avatar_color = 0
    upstream_token = str(sess.get("upstream_token", "") or "").strip()
    if not upstream_token:
        return _err("Upstream session missing, please login again", int(HTTPStatus.UNAUTHORIZED))
    status, remote = remote_json(
        "/api/member/profile/update",
        method="POST",
        payload={"display_name": display_name, "email": email, "avatar_color": avatar_color},
        headers={"X-Member-Session": upstream_token},
    )
    if status < 200 or status >= 300:
        msg = str((remote or {}).get("detail") or (remote or {}).get("error") or "Profile update failed")
        return _err(msg, status if status in {400, 401, 403, 404, 429} else int(HTTPStatus.BAD_GATEWAY))
    remote_member = (remote or {}).get("member") if isinstance((remote or {}).get("member"), dict) else {}
    remote_member_id = str((remote_member or {}).get("member_id", "") or str(sess.get("member_id", ""))).strip()
    remote_email = str((remote_member or {}).get("email", "") or email or str(sess.get("email", ""))).strip()
    new_upstream_token = str((remote or {}).get("session_token", "") or upstream_token).strip()
    session_token = issue_session(
        remote_member_id,
        remote_email,
        member=remote_member,
        upstream_token=new_upstream_token,
    )
    return _ok(
        {"ok": True, "session_token": session_token, "member": remote_member},
        cookie_token=session_token,
    )


def logout_post() -> MemberResult:
    return _ok({"ok": True}, clear_cookie=True)


def prefix_check_get(
    parsed_query: str,
    token: str,
    get_session,
    prefix_sanitize,
    load_accounts,
    prefix_in_use,
) -> MemberResult:
    sess, err = _session_or_unauthorized(token, get_session)
    if err:
        return err
    query = parse_qs(parsed_query)
    prefix_raw = str(query.get("prefix", [""])[0] or "").strip()
    if not prefix_raw:
        return _ok({"ok": True, "available": True, "normalized_prefix": ""})
    try:
        normalized = prefix_sanitize(prefix_raw)
    except ValueError as exc:
        return _ok(
            {"ok": True, "available": False, "normalized_prefix": "", "reason": str(exc)}
        )
    accounts = load_accounts()
    in_use = prefix_in_use(
        accounts,
        normalized,
        exclude_member_id=str(sess.get("member_id", "")),
    )
    return _ok(
        {
            "ok": True,
            "available": (not in_use),
            "normalized_prefix": normalized,
            "reason": ("Prefix already taken" if in_use else ""),
        }
    )


def email_change_request_post(token: str, body: dict, get_session, remote_json) -> MemberResult:
    sess, err = _session_or_unauthorized(token, get_session)
    if err:
        return err
    upstream_token = str((sess or {}).get("upstream_token", "") or "").strip()
    if not upstream_token:
        return _err("Member session invalid", int(HTTPStatus.UNAUTHORIZED))
    new_email = str((body or {}).get("new_email", "") or "").strip()
    if not new_email:
        return _err("new_email is required", int(HTTPStatus.BAD_REQUEST))
    status, remote = remote_json(
        "/api/member/email-change/request",
        method="POST",
        payload={"new_email": new_email},
        headers={"X-Member-Session": upstream_token},
    )
    if status < 200 or status >= 300:
        msg = str((remote or {}).get("detail") or (remote or {}).get("error") or "Email change request failed")
        return _err(msg, status if status in {400, 401, 403, 404, 409, 429} else int(HTTPStatus.BAD_GATEWAY))
    return _ok(remote)


def password_reset_request_post(body: dict, remote_json) -> MemberResult:
    email = str((body or {}).get("email", "") or "").strip()
    if not email:
        return _err("email is required", int(HTTPStatus.BAD_REQUEST))
    status, remote = remote_json(
        "/api/member/password-reset/request",
        method="POST",
        payload={"email": email},
    )
    if status < 200 or status >= 300:
        msg = str((remote or {}).get("detail") or (remote or {}).get("error") or "Password reset request failed")
        return _err(msg, status if status in {400, 401, 403, 404, 429} else int(HTTPStatus.BAD_GATEWAY))
    return _ok(remote)


def ddns_config_post(
    token: str,
    body: dict,
    get_session,
    load_accounts,
    find_account,
    find_account_by_member_id,
    now_ts,
    prefix_sanitize,
    prefix_in_use,
    save_accounts,
    build_fqdn,
    public_payload,
    prefix_change_limit_per_year: int,
) -> MemberResult:
    sess, err = _session_or_unauthorized(token, get_session)
    if err:
        return err
    ddns_enabled = bool((body or {}).get("ddns_enabled", False))
    prefix_raw = str((body or {}).get("ddns_prefix", "") or "").strip()
    accounts = load_accounts()
    idx, item = find_account(
        accounts,
        str(sess.get("member_id", "")),
        str(sess.get("email", "")),
    )
    if item is None or idx is None:
        idx, item = find_account_by_member_id(accounts, str(sess.get("member_id", "")))
    if item is None or idx is None:
        return _err("Member not found", int(HTTPStatus.NOT_FOUND))
    now = now_ts()
    year_start = now - 365 * 24 * 3600
    history = [
        int(x)
        for x in (item.get("prefix_change_ts") or [])
        if isinstance(x, (int, float)) and int(x) >= year_start
    ]
    old_prefix = str(item.get("ddns_prefix", "") or "").strip()
    new_prefix = old_prefix
    if prefix_raw:
        try:
            new_prefix = prefix_sanitize(prefix_raw)
        except ValueError as exc:
            return _err(str(exc), int(HTTPStatus.BAD_REQUEST))
        if prefix_in_use(
            accounts,
            new_prefix,
            exclude_member_id=str(item.get("member_id", "")),
        ):
            return _err("Prefix already taken", int(HTTPStatus.CONFLICT))
        if new_prefix != old_prefix:
            if len(history) >= int(prefix_change_limit_per_year):
                return _err("Domain prefix change limit reached (2/year)", int(HTTPStatus.FORBIDDEN))
            history.append(now)
    item["ddns_enabled"] = ddns_enabled
    item["ddns_prefix"] = new_prefix
    item["ddns_fqdn"] = build_fqdn(new_prefix) if new_prefix else ""
    item["prefix_change_ts"] = history
    item["updated_at"] = now
    item["status"] = str(item.get("status", "active") or "active")
    accounts[idx] = item
    save_accounts(accounts)
    return _ok({"ok": True, "member": public_payload(item)})
