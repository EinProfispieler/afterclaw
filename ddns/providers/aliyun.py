"""阿里云 DNS（公网 DNS API）：A/AAAA 多域名更新。"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import urllib.parse
import urllib.request
import uuid
from base64 import b64encode
from typing import Optional, Tuple

from ..domain_split import split_fqdn

_ENDPOINT = "https://alidns.aliyuncs.com/"


def _sign(secret: str, string_to_sign: str) -> str:
    key = (secret + "&").encode("utf-8")
    h = hmac.new(key, string_to_sign.encode("utf-8"), hashlib.sha1)
    return b64encode(h.digest()).decode("utf-8")


def _call(ak: str, sk: str, params: dict) -> dict:
    base = {
        "Format": "JSON",
        "Version": "2015-01-09",
        "AccessKeyId": ak,
        "SignatureMethod": "HMAC-SHA1",
        "Timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "SignatureVersion": "1.0",
        "SignatureNonce": str(uuid.uuid4()),
    }
    base.update(params)
    sorted_params = sorted(base.items())
    query = "&".join(f"{urllib.parse.quote(k, safe='')}={urllib.parse.quote(str(v), safe='')}" for k, v in sorted_params)
    sts = "GET&%2F&" + urllib.parse.quote(query, safe="")
    sig = _sign(sk, sts)
    url = _ENDPOINT + "?" + query + "&Signature=" + urllib.parse.quote(sig, safe="")
    req = urllib.request.Request(url, headers={"User-Agent": "storage-ctrl-ddns/2"})
    with urllib.request.urlopen(req, timeout=25) as r:
        body = r.read().decode("utf-8", errors="replace")
    return json.loads(body)


def _get_record(ak: str, sk: str, domain: str, rr: str, rtype: str) -> Optional[dict]:
    data = _call(ak, sk, {"Action": "DescribeDomainRecords", "DomainName": domain, "RRKeyWord": rr, "Type": rtype, "PageSize": "20"})
    for rec in (data.get("DomainRecords") or {}).get("Record") or []:
        if rec.get("RR") == rr and rec.get("Type") == rtype:
            return rec
    return None


def _update_one(ak: str, sk: str, ttl: int, fqdn: str, rtype: str, ip: str) -> None:
    p = split_fqdn(fqdn)
    if not p:
        raise ValueError(f"无法解析 FQDN: {fqdn!r}")
    sub, zone = p
    rr = sub if sub and sub != "@" else "@"
    existing = _get_record(ak, sk, zone, rr, rtype)
    if existing:
        if str(existing.get("Value", "")).strip() == ip:
            return
        _call(ak, sk, {"Action": "UpdateDomainRecord", "RecordId": existing["RecordId"], "RR": rr, "Type": rtype, "Value": ip, "TTL": str(ttl)})
    else:
        _call(ak, sk, {"Action": "AddDomainRecord", "DomainName": zone, "RR": rr, "Type": rtype, "Value": ip, "TTL": str(ttl)})


def update(cfg: dict, ipv4: Optional[str], ipv6: Optional[str]) -> Tuple[bool, str]:
    c = (cfg or {}).get("aliyun") or {}
    ak = (c.get("access_key_id") or "").strip()
    sk = (c.get("access_key_secret") or "").strip()
    if not ak or not sk:
        raise ValueError("阿里云 DNS 需 AccessKeyId 与 AccessKeySecret")
    ttl = int((cfg or {}).get("ttl") or 600)
    dom4 = [x.strip() for x in ((cfg or {}).get("ipv4_domains") or []) if x.strip()]
    dom6 = [x.strip() for x in ((cfg or {}).get("ipv6_domains") or []) if x.strip()]
    parts = []
    if ipv4 and dom4:
        for fqdn in dom4:
            _update_one(ak, sk, ttl, fqdn, "A", ipv4)
        parts.append(f"v4 {ipv4}")
    if ipv6 and dom6:
        for fqdn in dom6:
            _update_one(ak, sk, ttl, fqdn, "AAAA", ipv6)
        parts.append(f"v6 {ipv6}")
    if not parts:
        return True, "无变更"
    return True, " / ".join(parts)
