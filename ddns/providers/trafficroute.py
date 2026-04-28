"""火山引擎 TrafficRoute：A/AAAA 与多域名。Host 与 ddns-go 的 GetSubDomain() 一致。"""

from __future__ import annotations

from typing import List, Optional, Tuple

from ..domain_split import split_fqdn
from ..volc import traffic_api


def _host_param(sub: str) -> str:
    if not sub or sub == "@":
        return "@"
    return sub


def _update_one(
    ak: str, sk: str, ttl: int, zone: str, rtype: str, value: str, sub: str
) -> None:
    zid = traffic_api.get_zone_id(ak, sk, zone)
    hp = _host_param(sub)
    recs = traffic_api.list_records(ak, sk, zid, rtype, hp)
    rec = None
    for r in recs:
        if (r or {}).get("Type") == rtype and (r or {}).get("Host") == hp:
            rec = r
            break
    if rec is not None and str((rec or {}).get("Value", "")).strip() == str(value).strip():
        return
    if rec is not None:
        traffic_api.update_record(ak, sk, {**rec, "ZID": int(zid)}, value, ttl)
    else:
        traffic_api.create_record(ak, sk, zid, hp, rtype, value, ttl)


def _domains_list(cfg: dict, key: str) -> List[str]:
    v = (cfg or {}).get(key)
    if v is None and key == "ipv4_domains":
        v = (cfg or {}).get("domains", {}).get("ipv4")
    if v is None and key == "ipv6_domains":
        v = (cfg or {}).get("domains", {}).get("ipv6")
    if isinstance(v, str):
        v = v.strip()
        return [v] if v else []
    if isinstance(v, list):
        return [str(x).strip() for x in v if str(x).strip()]
    return []


def _legacy_v4_fqdn(cfg: dict) -> list[str]:
    t = (cfg or {}).get("trafficroute") or {}
    s = t.get("domain", t.get("domains"))
    if isinstance(s, str) and s.strip():
        return [s.strip()]
    if isinstance(s, list):
        return [str(x).strip() for x in s if str(x).strip()]
    return []


def _ipv4_enabled(cfg: dict) -> bool:
    b = (cfg or {}).get("ipv4")
    if isinstance(b, dict):
        return bool(b.get("enabled", True))
    return True


def _ipv6_enabled(cfg: dict) -> bool:
    b = (cfg or {}).get("ipv6")
    if isinstance(b, dict):
        return bool(b.get("enabled", False))
    return False


def update(
    cfg: dict,
    ipv4: Optional[str],
    ipv6: Optional[str],
) -> Tuple[bool, str]:
    t = (cfg or {}).get("trafficroute") or {}
    ak = (t.get("access_key_id") or t.get("id") or "").strip()
    sk = (t.get("secret_access_key") or t.get("secret") or "").strip()
    if not ak or not sk:
        raise ValueError("TrafficRoute 需 AccessKeyId 与 SecretAccessKey")
    try:
        ttl = int(t.get("ttl", (cfg or {}).get("ttl", 600)) or 600)
    except (TypeError, ValueError):
        ttl = 600

    dom4 = _domains_list(cfg, "ipv4_domains")
    if not dom4:
        dom4 = _legacy_v4_fqdn(cfg)
    dom6 = [x for x in _domains_list(cfg, "ipv6_domains") if (x or "").strip()]

    v4e = _ipv4_enabled(cfg)
    v6e = _ipv6_enabled(cfg)
    parts: list[str] = []
    if v4e and ipv4 and dom4:
        for fq in dom4:
            p = split_fqdn(fq)
            if not p:
                raise ValueError(f"无法解析 FQDN: {fq!r}（可安装 tldextract 以改进识别）")
            sub, zone = p
            _update_one(ak, sk, ttl, zone, "A", ipv4, sub)
        parts.append(f"v4 {ipv4}")
    if v6e and ipv6 and dom6:
        for fq in dom6:
            p = split_fqdn(fq)
            if not p:
                raise ValueError(f"无法解析 FQDN: {fq!r}")
            sub, zone = p
            _update_one(ak, sk, ttl, zone, "AAAA", ipv6, sub)
        parts.append(f"v6 {ipv6}")
    if not parts:
        if (v4e and bool(dom4) and not ipv4) or (v6e and bool(dom6) and not ipv6):
            raise ValueError("已启用但未能取得对应公网地址")
        if v4e and not dom4 and (not v6e or not dom6):
            raise ValueError("请在 ipv4_domains / 或 trafficroute.domain 中配置域名")
        if not (dom4 or dom6):
            raise ValueError("未配置域名")
        return True, "无变更"
    return True, " / ".join(parts)
