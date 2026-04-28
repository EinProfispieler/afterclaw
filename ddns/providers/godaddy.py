"""GoDaddy DDNS：A/AAAA 多域名更新。"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional, Tuple

from ..domain_split import split_fqdn


def _req(method: str, url: str, data: bytes | None, headers: dict) -> tuple[int, str]:
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={**headers, "User-Agent": "storage-ctrl-ddns/2"},
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.getcode() or 0, (r.read() or b"").decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return int(e.code or 0), (e.read() or b"").decode("utf-8", errors="replace")


def _update_one(key: str, secret: str, ttl: int, fqdn: str, rtype: str, ip: str) -> None:
    p = split_fqdn(fqdn)
    if not p:
        raise ValueError(f"无法解析 FQDN: {fqdn!r}")
    sub, zone = p
    name = sub if sub and sub != "@" else "@"
    payload = json.dumps(
        [{"data": ip, "name": name, "ttl": int(ttl), "type": rtype}],
        ensure_ascii=False,
    ).encode("utf-8")
    z = urllib.parse.quote(zone, safe="")
    n = urllib.parse.quote(name, safe="")
    url = f"https://api.godaddy.com/v1/domains/{z}/records/{rtype}/{n}"
    code, body = _req(
        "PUT",
        url,
        payload,
        {
            "Authorization": f"sso-key {key}:{secret}",
            "Content-Type": "application/json",
        },
    )
    if code not in (200, 202, 204):
        raise RuntimeError(f"GoDaddy 更新失败: HTTP {code} {body[:240]}")


def update(cfg: dict, ipv4: Optional[str], ipv6: Optional[str]) -> Tuple[bool, str]:
    c = (cfg or {}).get("godaddy") or {}
    key = (c.get("api_key") or "").strip()
    secret = (c.get("api_secret") or "").strip()
    if not key or not secret:
        raise ValueError("GoDaddy 需要 API Key 与 API Secret")
    ttl = int((cfg or {}).get("ttl") or 600)
    dom4 = [x.strip() for x in ((cfg or {}).get("ipv4_domains") or []) if x.strip()]
    dom6 = [x.strip() for x in ((cfg or {}).get("ipv6_domains") or []) if x.strip()]
    parts = []
    if ipv4 and dom4:
        for fqdn in dom4:
            _update_one(key, secret, ttl, fqdn, "A", ipv4)
        parts.append(f"v4 {ipv4}")
    if ipv6 and dom6:
        for fqdn in dom6:
            _update_one(key, secret, ttl, fqdn, "AAAA", ipv6)
        parts.append(f"v6 {ipv6}")
    if not parts:
        return True, "无变更"
    return True, " / ".join(parts)
