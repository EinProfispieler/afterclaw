"""DNSPod（腾讯云）DDNS：A/AAAA 多域名更新，使用 API Token 鉴权。"""

from __future__ import annotations

import json
import urllib.request
from typing import Optional, Tuple

from ..domain_split import split_fqdn

_API = "https://dnsapi.cn/"


def _call(token: str, action: str, params: dict) -> dict:
    data = {"login_token": token, "format": "json", "lang": "cn", **params}
    body = urllib.parse.urlencode(data).encode("utf-8")  # type: ignore[attr-defined]
    req = urllib.request.Request(_API + action, data=body, headers={"User-Agent": "storage-ctrl-ddns/2 (randypku@github)"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode("utf-8", errors="replace"))


def _get_record(token: str, domain: str, sub: str, rtype: str) -> Optional[dict]:
    res = _call(token, "Record.List", {"domain": domain, "sub_domain": sub, "record_type": rtype, "length": "20"})
    for rec in (res.get("records") or []):
        if rec.get("type", "").upper() == rtype.upper() and rec.get("name") == sub:
            return rec
    return None


def _update_one(token: str, ttl: int, fqdn: str, rtype: str, ip: str) -> None:
    p = split_fqdn(fqdn)
    if not p:
        raise ValueError(f"无法解析 FQDN: {fqdn!r}")
    sub, zone = p
    sub = sub if sub and sub != "@" else "@"
    existing = _get_record(token, zone, sub, rtype)
    if existing:
        if str(existing.get("value", "")).strip() == ip:
            return
        _call(token, "Record.Modify", {"domain": zone, "record_id": existing["id"], "sub_domain": sub, "record_type": rtype, "value": ip, "record_line": "默认", "ttl": str(ttl)})
    else:
        _call(token, "Record.Create", {"domain": zone, "sub_domain": sub, "record_type": rtype, "value": ip, "record_line": "默认", "ttl": str(ttl)})


import urllib.parse


def update(cfg: dict, ipv4: Optional[str], ipv6: Optional[str]) -> Tuple[bool, str]:
    c = (cfg or {}).get("dnspod") or {}
    token = (c.get("token") or "").strip()
    if not token:
        raise ValueError("DNSPod 需要 API Token（格式：ID,Token）")
    ttl = int((cfg or {}).get("ttl") or 600)
    dom4 = [x.strip() for x in ((cfg or {}).get("ipv4_domains") or []) if x.strip()]
    dom6 = [x.strip() for x in ((cfg or {}).get("ipv6_domains") or []) if x.strip()]
    parts = []
    if ipv4 and dom4:
        for fqdn in dom4:
            _update_one(token, ttl, fqdn, "A", ipv4)
        parts.append(f"v4 {ipv4}")
    if ipv6 and dom6:
        for fqdn in dom6:
            _update_one(token, ttl, fqdn, "AAAA", ipv6)
        parts.append(f"v6 {ipv6}")
    if not parts:
        return True, "无变更"
    return True, " / ".join(parts)
