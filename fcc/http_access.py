"""LAN-first access policy for the AfterClaw HTTP file service.

Pure, dependency-light logic so it can be unit-tested without the runtime.
The policy governs who may reach the public ``/http-files/`` routes:

- ``lan_only`` (default): only RFC1918 / loopback / link-local clients.
- ``limited``: LAN clients plus an explicit IP/CIDR allowlist.
- ``public``: everyone. If ``public_until`` is set, it's a timed window; if
  ``public_until`` is ``None``, it remains public until manually closed.

Timed ``public`` windows are expired lazily: any time the effective mode is
computed, an elapsed ``public_until`` collapses the policy back to
``lan_only``. Nothing relies on a background job to close a public window.
"""

from __future__ import annotations

import ipaddress
import time as _time

from fcc.security import is_lan

MODES = ("lan_only", "limited", "public")


def default_policy() -> dict:
    return {"mode": "lan_only", "allowlist": [], "public_until": None}


def _clean_allowlist(raw) -> list[str]:
    out: list[str] = []
    if isinstance(raw, (list, tuple)):
        for item in raw:
            text = str(item or "").strip()
            if not text:
                continue
            try:
                ipaddress.ip_network(text, strict=False)
            except ValueError:
                continue
            if text not in out:
                out.append(text)
    return out


def normalize_policy(raw) -> dict:
    base = default_policy()
    if isinstance(raw, dict):
        mode = str(raw.get("mode", "") or "").strip().lower()
        if mode in MODES:
            base["mode"] = mode
        base["allowlist"] = _clean_allowlist(raw.get("allowlist"))
        until = raw.get("public_until")
        if isinstance(until, (int, float)) and until > 0:
            base["public_until"] = float(until)
    return base


def effective_mode(policy: dict, now: float | None = None) -> str:
    """Mode actually in force, applying lazy expiry of public windows."""
    pol = normalize_policy(policy)
    if now is None:
        now = _time.time()
    if pol["mode"] == "public":
        until = pol["public_until"]
        if until is None:
            return "public"
        if now >= until:
            return "lan_only"
    return pol["mode"]


def _ip_in_allowlist(client_ip: str, allowlist: list[str]) -> bool:
    try:
        ip_obj = ipaddress.ip_address(str(client_ip or "").strip())
    except ValueError:
        return False
    for entry in allowlist:
        try:
            net = ipaddress.ip_network(entry, strict=False)
        except ValueError:
            continue
        if ip_obj.version == net.version and ip_obj in net:
            return True
    return False


def is_allowed(policy: dict, client_ip: str, now: float | None = None) -> bool:
    """Whether ``client_ip`` may reach the public HTTP file routes."""
    pol = normalize_policy(policy)
    mode = effective_mode(pol, now)
    if mode == "public":
        return True
    if is_lan(client_ip):
        return True
    if mode == "limited":
        return _ip_in_allowlist(client_ip, pol["allowlist"])
    return False


def public_seconds_remaining(policy: dict, now: float | None = None) -> int:
    """Seconds left on an active public window, else 0."""
    pol = normalize_policy(policy)
    if now is None:
        now = _time.time()
    if pol["mode"] == "public" and pol["public_until"] is not None:
        remaining = pol["public_until"] - now
        if remaining > 0:
            return int(remaining)
    return 0
