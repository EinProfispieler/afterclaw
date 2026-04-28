"""Namecheap DDNS：动态 DNS 密码模式（仅 IPv4）。"""

from __future__ import annotations

import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Optional, Tuple

from ..domain_split import split_fqdn

_API = "https://dynamicdns.park-your-domain.com/update"


def _update_one(password: str, fqdn: str, ip: str) -> None:
    p = split_fqdn(fqdn)
    if not p:
        raise ValueError(f"无法解析 FQDN: {fqdn!r}")
    sub, zone = p
    host = sub if sub and sub != "@" else "@"
    q = urllib.parse.urlencode(
        {
            "host": host,
            "domain": zone,
            "password": password,
            "ip": ip,
        }
    )
    req = urllib.request.Request(
        f"{_API}?{q}",
        headers={"User-Agent": "storage-ctrl-ddns/2"},
    )
    with urllib.request.urlopen(req, timeout=25) as r:
        body = (r.read() or b"").decode("utf-8", errors="replace")
    root = ET.fromstring(body)
    err_count = (root.findtext(".//ErrCount") or "").strip()
    if err_count == "0":
        return
    err_msg = (
        root.findtext(".//Err1")
        or root.findtext(".//errors")
        or root.findtext(".//Error")
        or body[:240]
    )
    raise RuntimeError(f"Namecheap 更新失败: {err_msg}")


def update(cfg: dict, ipv4: Optional[str], ipv6: Optional[str]) -> Tuple[bool, str]:
    c = (cfg or {}).get("namecheap") or {}
    password = (c.get("dynamic_password") or "").strip()
    if not password:
        raise ValueError("Namecheap 需要 Dynamic DNS Password")
    dom4 = [x.strip() for x in ((cfg or {}).get("ipv4_domains") or []) if x.strip()]
    dom6 = [x.strip() for x in ((cfg or {}).get("ipv6_domains") or []) if x.strip()]
    parts = []
    if ipv4 and dom4:
        for fqdn in dom4:
            _update_one(password, fqdn, ipv4)
        parts.append(f"v4 {ipv4}")
    if ipv6 and dom6:
        parts.append("Namecheap 不支持 AAAA，已跳过")
    if not parts:
        return True, "无变更"
    return True, " / ".join(parts)
