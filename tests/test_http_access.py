from fcc.http_access import (
    default_policy,
    effective_mode,
    is_allowed,
    normalize_policy,
    public_seconds_remaining,
)

NOW = 1_000_000.0


def test_default_is_lan_only():
    pol = default_policy()
    assert pol["mode"] == "lan_only"
    assert effective_mode(pol, NOW) == "lan_only"
    assert is_allowed(pol, "192.168.1.5", NOW)
    assert is_allowed(pol, "127.0.0.1", NOW)
    assert not is_allowed(pol, "8.8.8.8", NOW)


def test_public_window_active_then_expired():
    pol = {"mode": "public", "allowlist": [], "public_until": NOW + 3600}
    assert effective_mode(pol, NOW) == "public"
    assert is_allowed(pol, "8.8.8.8", NOW)
    assert public_seconds_remaining(pol, NOW) == 3600
    # past the window: lazily collapses to lan_only
    assert effective_mode(pol, NOW + 7200) == "lan_only"
    assert not is_allowed(pol, "8.8.8.8", NOW + 7200)
    assert public_seconds_remaining(pol, NOW + 7200) == 0


def test_public_without_until_is_persistent_public():
    pol = {"mode": "public", "allowlist": [], "public_until": None}
    assert effective_mode(pol, NOW) == "public"
    assert is_allowed(pol, "8.8.8.8", NOW)


def test_limited_allowlist():
    pol = {"mode": "limited", "allowlist": ["9.9.9.0/24", "1.1.1.1"]}
    assert is_allowed(pol, "192.168.0.9", NOW)      # LAN always allowed
    assert is_allowed(pol, "9.9.9.55", NOW)         # in CIDR
    assert is_allowed(pol, "1.1.1.1", NOW)          # exact host
    assert not is_allowed(pol, "1.1.1.2", NOW)
    assert not is_allowed(pol, "8.8.8.8", NOW)


def test_normalize_drops_bad_input():
    pol = normalize_policy(
        {"mode": "bogus", "allowlist": ["10.0.0.0/8", "not-an-ip", ""], "public_until": "soon"}
    )
    assert pol["mode"] == "lan_only"
    assert pol["allowlist"] == ["10.0.0.0/8"]
    assert pol["public_until"] is None
