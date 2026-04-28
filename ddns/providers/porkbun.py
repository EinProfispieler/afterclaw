"""Porkbun DDNS：A/AAAA 多域名更新。"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Optional, Tuple

from ..domain_split import split_fqdn

_API = "https://api.porkbun.com/api/json/v3/dns"


def _post(path: str, payload: dict) -> dict:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"{_API}{path}",
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "User-Agent": "storage-ctrl-ddns/2",
        },
    )
    with urllib.request.urlopen(req, timeout=25) as r:
        text = (r.read() or b"").decode("utf-8", errors="replace")
    return json.loads(text)


def _update_one(key: str, secret: str, ttl: int, fqdn: str, rtype: str, ip: str) -> None:
    p = split_fqdn(fqdn)
    if not p:
        raise ValueError(f"无法解析 FQDN: {fqdn!r}")
    sub, zone = p
    host = "" if sub in ("", "@") else sub
    hz = urllib.parse.quote(zone, safe="")
    hs = urllib.parse.quote(host, safe="")
    base_auth = {"apikey": key, "secretapikey": secret}
    current = _post(
        f"/retrieveByNameType/{hz}/{rtype}/{hs}",
        base_auth,
    )
    if (current.get("status") or "").upper() != "SUCCESS":
        raise RuntimeError(f"Porkbun 查询失败: {json.dumps(current, ensure_ascii=False)[:240]}")
    records = current.get("records") or []
    if records:
        old = str((records[0] or {}).get("content") or "").strip()
        if old == ip:
            return
        resp = _post(
            f"/editByNameType/{hz}/{rtype}/{hs}",
            {
                **base_auth,
                "content": ip,
                "ttl": str(int(ttl)),
            },
        )
    else:
        resp = _post(
            f"/create/{hz}",
            {
                **base_auth,
                "name": host,
                "type": rtype,
                "content": ip,
                "ttl": str(int(ttl)),
            },
        )
    if (resp.get("status") or "").upper() != "SUCCESS":
        raise RuntimeError(f"Porkbun 更新失败: {json.dumps(resp, ensure_ascii=False)[:240]}")


def update(cfg: dict, ipv4: Optional[str], ipv6: Optional[str]) -> Tuple[bool, str]:
    c = (cfg or {}).get("porkbun") or {}
    key = (c.get("api_key") or "").strip()
    secret = (c.get("secret_api_key") or "").strip()
    if not key or not secret:
        raise ValueError("Porkbun 需要 API Key 与 Secret API Key")
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
