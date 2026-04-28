"""NameSilo DDNS：A/AAAA 多域名更新。"""

from __future__ import annotations

import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Optional, Tuple

from ..domain_split import split_fqdn

_API = "https://www.namesilo.com/api/"


def _call(key: str, action: str, params: dict) -> ET.Element:
    query = urllib.parse.urlencode(
        {"version": "1", "type": "xml", "key": key, **params}
    )
    req = urllib.request.Request(
        f"{_API}{action}?{query}",
        headers={"User-Agent": "storage-ctrl-ddns/2"},
    )
    with urllib.request.urlopen(req, timeout=25) as r:
        body = (r.read() or b"").decode("utf-8", errors="replace")
    try:
        return ET.fromstring(body)
    except ET.ParseError as e:
        raise RuntimeError(f"NameSilo 返回非 XML: {body[:200]}") from e


def _resp_ok(root: ET.Element) -> tuple[bool, str]:
    code = (root.findtext(".//reply/code") or "").strip()
    detail = (root.findtext(".//reply/detail") or "").strip()
    return code == "300", detail


def _list_records(key: str, zone: str) -> list[dict]:
    root = _call(key, "dnsListRecords", {"domain": zone})
    ok, detail = _resp_ok(root)
    if not ok:
        raise RuntimeError(f"NameSilo 查询失败: {detail or '未知错误'}")
    items: list[dict] = []
    for rr in root.findall(".//resource_record"):
        items.append(
            {
                "record_id": (rr.findtext("record_id") or "").strip(),
                "type": (rr.findtext("type") or "").strip().upper(),
                "host": (rr.findtext("host") or "").strip().lower(),
                "value": (rr.findtext("value") or "").strip(),
            }
        )
    return items


def _find_record(records: list[dict], zone: str, sub: str, fqdn: str, rtype: str) -> Optional[dict]:
    rtype = rtype.upper()
    if sub in ("", "@"):
        candidates = {"@", zone.lower(), fqdn.lower()}
    else:
        candidates = {sub.lower(), f"{sub}.{zone}".lower(), fqdn.lower()}
    for rec in records:
        if (rec.get("type") or "").upper() != rtype:
            continue
        host = (rec.get("host") or "").lower()
        if host in candidates:
            return rec
    return None


def _update_one(key: str, ttl: int, fqdn: str, rtype: str, ip: str) -> None:
    p = split_fqdn(fqdn)
    if not p:
        raise ValueError(f"无法解析 FQDN: {fqdn!r}")
    sub, zone = p
    host = sub if sub and sub != "@" else "@"
    records = _list_records(key, zone)
    existing = _find_record(records, zone, host, fqdn, rtype)
    if existing:
        if str(existing.get("value", "")).strip() == ip:
            return
        root = _call(
            key,
            "dnsUpdateRecord",
            {
                "domain": zone,
                "rrhost": host,
                "rrid": existing.get("record_id") or "",
                "rrvalue": ip,
                "rrttl": str(int(ttl)),
            },
        )
    else:
        root = _call(
            key,
            "dnsAddRecord",
            {
                "domain": zone,
                "rrhost": host,
                "rrtype": rtype,
                "rrvalue": ip,
                "rrttl": str(int(ttl)),
            },
        )
    ok, detail = _resp_ok(root)
    if not ok:
        raise RuntimeError(f"NameSilo 更新失败: {detail or '未知错误'}")


def update(cfg: dict, ipv4: Optional[str], ipv6: Optional[str]) -> Tuple[bool, str]:
    c = (cfg or {}).get("namesilo") or {}
    key = (c.get("api_key") or "").strip()
    if not key:
        raise ValueError("NameSilo 需要 API Key")
    ttl = int((cfg or {}).get("ttl") or 600)
    dom4 = [x.strip() for x in ((cfg or {}).get("ipv4_domains") or []) if x.strip()]
    dom6 = [x.strip() for x in ((cfg or {}).get("ipv6_domains") or []) if x.strip()]
    parts = []
    if ipv4 and dom4:
        for fqdn in dom4:
            _update_one(key, ttl, fqdn, "A", ipv4)
        parts.append(f"v4 {ipv4}")
    if ipv6 and dom6:
        for fqdn in dom6:
            _update_one(key, ttl, fqdn, "AAAA", ipv6)
        parts.append(f"v6 {ipv6}")
    if not parts:
        return True, "无变更"
    return True, " / ".join(parts)
