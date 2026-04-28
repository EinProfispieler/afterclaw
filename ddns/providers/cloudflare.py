"""Cloudflare DDNS：支持 A/AAAA 多域名，自动按 zone 分组。"""

from __future__ import annotations

import json
import urllib.request
from typing import Optional, Tuple

from ..domain_split import split_fqdn


def _req(method: str, url: str, data: bytes | None, headers: dict) -> tuple[int, str]:
    req = urllib.request.Request(url, data=data, method=method, headers={**headers, "User-Agent": "storage-ctrl-ddns/2"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.getcode() or 0, (r.read() or b"").decode("utf-8", errors="replace")


def _get_zone_id(tok: str, zone_name: str) -> str:
    code, body = _req("GET", f"https://api.cloudflare.com/client/v4/zones?name={zone_name}&status=active", None, {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"})
    j = json.loads(body)
    if not j.get("success") or not j.get("result"):
        raise RuntimeError(f"Cloudflare 未找到 zone {zone_name!r}")
    return j["result"][0]["id"]


def _get_record(tok: str, zone_id: str, name: str, rtype: str) -> Optional[dict]:
    code, body = _req("GET", f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records?name={name}&type={rtype}", None, {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"})
    j = json.loads(body)
    result = j.get("result") or []
    return result[0] if result else None


def _update_one(tok: str, fqdn: str, rtype: str, ip: str, ttl: int = 1, proxied: bool = False) -> None:
    p = split_fqdn(fqdn)
    if not p:
        raise ValueError(f"无法解析 FQDN: {fqdn!r}")
    _, zone = p
    zone_id = _get_zone_id(tok, zone)
    existing = _get_record(tok, zone_id, fqdn, rtype)
    payload = json.dumps({"type": rtype, "name": fqdn, "content": ip, "ttl": ttl, "proxied": proxied}, ensure_ascii=False).encode("utf-8")
    hdrs = {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}
    if existing:
        if str(existing.get("content", "")).strip() == ip:
            return
        code, body = _req("PUT", f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records/{existing['id']}", payload, hdrs)
    else:
        code, body = _req("POST", f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records", payload, hdrs)
    pj = json.loads(body) if body else {}
    if code not in (200, 201) or not pj.get("success"):
        raise RuntimeError(f"Cloudflare 更新失败: HTTP {code} {body[:300]}")


# Legacy single-record interface kept for backward compat
def update_a(cfg: dict, ip: str) -> bool:
    c = cfg.get("cloudflare") or {}
    zid = (c.get("zone_id") or "").strip()
    rid = (c.get("record_id") or "").strip()
    tok = (c.get("api_token") or "").strip()
    import json as _json
    u = f"https://api.cloudflare.com/client/v4/zones/{zid}/dns_records/{rid}"
    get_code, get_body = _req("GET", u, None, {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"})
    if get_code != 200:
        raise RuntimeError(f"Cloudflare 读取失败: HTTP {get_code} {get_body[:200]}")
    j = _json.loads(get_body)
    if not j.get("success"):
        raise RuntimeError("Cloudflare(读): " + get_body[:200])
    rec = j.get("result") or {}
    payload = _json.dumps({"type": rec.get("type") or "A", "name": rec.get("name") or "", "content": ip, "ttl": rec.get("ttl", 1), "proxied": bool(rec.get("proxied", False))}, ensure_ascii=False).encode("utf-8")
    put_code, put_body = _req("PUT", u, payload, {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"})
    pj = _json.loads(put_body) if put_body else {}
    if put_code != 200 or not pj.get("success"):
        raise RuntimeError(f"Cloudflare 更新失败: HTTP {put_code} {put_body[:300]}")
    return True


def update(cfg: dict, ipv4: Optional[str], ipv6: Optional[str]) -> Tuple[bool, str]:
    c = (cfg or {}).get("cloudflare") or {}
    tok = (c.get("api_token") or "").strip()
    if not tok:
        raise ValueError("Cloudflare 需要 API Token")
    ttl = int((c.get("ttl") or (cfg or {}).get("ttl") or 1))
    proxied = bool(c.get("proxied", False))
    dom4 = [x.strip() for x in ((cfg or {}).get("ipv4_domains") or []) if x.strip()]
    dom6 = [x.strip() for x in ((cfg or {}).get("ipv6_domains") or []) if x.strip()]
    # Fallback: legacy single record_id mode
    if not dom4 and not dom6:
        if ipv4:
            update_a(cfg, ipv4)
            return True, f"IPv4={ipv4}"
        raise ValueError("Cloudflare 需配置 ipv4_domains 或 ipv6_domains")
    parts = []
    if ipv4 and dom4:
        for fqdn in dom4:
            _update_one(tok, fqdn, "A", ipv4, ttl, proxied)
        parts.append(f"v4 {ipv4}")
    if ipv6 and dom6:
        for fqdn in dom6:
            _update_one(tok, fqdn, "AAAA", ipv6, ttl, proxied)
        parts.append(f"v6 {ipv6}")
    if not parts:
        return True, "无变更"
    return True, " / ".join(parts)
