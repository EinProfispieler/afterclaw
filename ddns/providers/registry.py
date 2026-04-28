from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from . import (
    aliyun,
    cloudflare,
    custom_url,
    dnspod,
    duckdns,
    godaddy,
    namecheap,
    namesilo,
    noip,
    porkbun,
    trafficroute,
)

Pair = Tuple[bool, str]


def run_update(
    cfg: Dict[str, Any],
    ipv4: Optional[str],
    ipv6: Optional[str],
) -> Pair:
    prov = (cfg.get("provider") or "duckdns").strip().lower()
    try:
        if prov == "trafficroute":
            return trafficroute.update(cfg, ipv4, ipv6)
        if prov == "duckdns":
            if not ipv4:
                return False, "DuckDNS 需要 IPv4"
            duckdns.update_a(cfg, ipv4)
            return True, f"IPv4={ipv4}"
        if prov == "cloudflare":
            return cloudflare.update(cfg, ipv4, ipv6)
        if prov in ("url", "custom", "get"):
            ipu = ipv4 or ipv6
            if not ipu:
                return False, "自定义 URL 需要至少一个公网地址"
            custom_url.update_get(cfg, ipu)
            return True, f"ip={ipu}"
        if prov in ("aliyun", "alidns"):
            return aliyun.update(cfg, ipv4, ipv6)
        if prov in ("dnspod", "tencentdns"):
            return dnspod.update(cfg, ipv4, ipv6)
        if prov == "noip":
            return noip.update(cfg, ipv4, ipv6)
        if prov in ("godaddy", "go_daddy"):
            return godaddy.update(cfg, ipv4, ipv6)
        if prov in ("namecheap", "name_cheap"):
            return namecheap.update(cfg, ipv4, ipv6)
        if prov in ("namesilo", "name_silo"):
            return namesilo.update(cfg, ipv4, ipv6)
        if prov == "porkbun":
            return porkbun.update(cfg, ipv4, ipv6)
    except Exception as e:
        return False, str(e)
    return False, f"未知 provider: {prov!r}"
