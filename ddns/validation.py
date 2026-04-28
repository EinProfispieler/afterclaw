from __future__ import annotations

from urllib.parse import urlparse

from typing import Any, Optional


def validate_config(cfg: dict) -> Optional[str]:
    if not (cfg or {}).get("enabled"):
        return "未启用"
    prov = (cfg.get("provider") or "duckdns").strip().lower()
    if prov == "duckdns":
        d = cfg.get("duckdns") or {}
        if not (d.get("domain") or "").strip() or not (d.get("token") or "").strip():
            return "DuckDNS: 子域名与 Token 必填"
    elif prov == "cloudflare":
        c = cfg.get("cloudflare") or {}
        tok = (c.get("api_token") or "").strip()
        if not tok:
            return "Cloudflare: api_token 必填"
        dom4 = [x.strip() for x in (cfg.get("ipv4_domains") or []) if x.strip()]
        dom6 = [x.strip() for x in (cfg.get("ipv6_domains") or []) if x.strip()]
        if not dom4 and not dom6:
            if not (c.get("zone_id") and c.get("record_id")):
                return "Cloudflare: 未配置 FQDN 列表时，需填写 zone_id + record_id（或改为填写 FQDN 列表）"
    elif prov in ("url", "custom", "get"):
        t = (cfg.get("url") or {}).get("template") or ""
        if "{ip}" not in t or not t.strip():
            return "URL 模式需非空且含 {ip}"
    elif prov in ("ddnsgo", "ddns-go", "native"):
        c = cfg.get("ddnsgo") or {}
        base = (c.get("base_url") or "").strip()
        if not base:
            return "ddns-go 原生模式: 需填写 base_url"
        try:
            u = urlparse(base)
        except Exception:
            return "ddns-go 原生模式: base_url 无效"
        if u.scheme not in ("http", "https") or not u.netloc:
            return "ddns-go 原生模式: base_url 需为 http(s)://host:port"
    elif prov == "trafficroute":
        t = cfg.get("trafficroute") or {}
        ak = (t.get("access_key_id") or t.get("id") or "").strip()
        sk = (t.get("secret_access_key") or t.get("secret") or "").strip()
        if not ak or not sk:
            return "TrafficRoute: 需 AccessKey 与 Secret"
        dom4 = list(cfg.get("ipv4_domains") or [])
        dom4 += list((cfg.get("domains") or {}).get("ipv4") or [])
        dleg = t.get("domain", t.get("domains"))
        if isinstance(dleg, str) and dleg.strip() and dleg not in dom4:
            dom4 = [dleg.strip()] + dom4
        dom6 = [x for x in (list(cfg.get("ipv6_domains") or []) + list((cfg.get("domains") or {}).get("ipv6") or [])) if (x or "").strip()]
        v4e = (cfg.get("ipv4") or {}).get("enabled", True) if isinstance((cfg or {}).get("ipv4"), dict) else True
        v6e = (cfg.get("ipv6") or {}).get("enabled", False) if isinstance((cfg or {}).get("ipv6"), dict) else False
        has4 = bool(dom4) or (isinstance(dleg, str) and dleg.strip() != "")
        if v4e and not has4:
            return "TrafficRoute: 启用 IPv4 时请在 A 记录域名中填写 FQDN（或 trafficroute.domain）"
        if v6e and not dom6:
            return "TrafficRoute: 启用 IPv6 时在 AAAA 域名中至少填一行，或先关闭 IPv6"
    elif prov in ("aliyun", "alidns"):
        c = cfg.get("aliyun") or {}
        ak = (c.get("access_key_id") or "").strip()
        sk = (c.get("access_key_secret") or "").strip()
        if not ak or not sk:
            return "阿里云 DNS: 需 AccessKeyId 与 AccessKeySecret"
        dom4 = [x.strip() for x in (cfg.get("ipv4_domains") or []) if x.strip()]
        dom6 = [x.strip() for x in (cfg.get("ipv6_domains") or []) if x.strip()]
        if not dom4 and not dom6:
            return "阿里云 DNS: 需至少配置一个 FQDN"
    elif prov in ("dnspod", "tencentdns"):
        c = cfg.get("dnspod") or {}
        tok = (c.get("token") or "").strip()
        if not tok:
            return "DNSPod: 需 API Token（格式：ID,Token）"
        dom4 = [x.strip() for x in (cfg.get("ipv4_domains") or []) if x.strip()]
        dom6 = [x.strip() for x in (cfg.get("ipv6_domains") or []) if x.strip()]
        if not dom4 and not dom6:
            return "DNSPod: 需至少配置一个 FQDN"
    elif prov == "noip":
        c = cfg.get("noip") or {}
        if not (c.get("username") or "").strip() or not (c.get("password") or "").strip() or not (c.get("hostname") or "").strip():
            return "No-IP: 需 username、password、hostname"
    elif prov in ("godaddy", "go_daddy"):
        c = cfg.get("godaddy") or {}
        if not (c.get("api_key") or "").strip() or not (c.get("api_secret") or "").strip():
            return "GoDaddy: 需 API Key 与 API Secret"
        dom4 = [x.strip() for x in (cfg.get("ipv4_domains") or []) if x.strip()]
        dom6 = [x.strip() for x in (cfg.get("ipv6_domains") or []) if x.strip()]
        if not dom4 and not dom6:
            return "GoDaddy: 需至少配置一个 FQDN"
    elif prov in ("namecheap", "name_cheap"):
        c = cfg.get("namecheap") or {}
        if not (c.get("dynamic_password") or "").strip():
            return "Namecheap: 需 Dynamic DNS Password"
        dom4 = [x.strip() for x in (cfg.get("ipv4_domains") or []) if x.strip()]
        if not dom4:
            return "Namecheap: 仅支持 IPv4，请至少配置一个 A 记录 FQDN"
        v6e = (cfg.get("ipv6") or {}).get("enabled", False) if isinstance((cfg or {}).get("ipv6"), dict) else False
        dom6 = [x.strip() for x in (cfg.get("ipv6_domains") or []) if x.strip()]
        if v6e and dom6:
            return "Namecheap: 不支持 AAAA 动态更新，请关闭 IPv6 或清空 AAAA 列表"
    elif prov in ("namesilo", "name_silo"):
        c = cfg.get("namesilo") or {}
        if not (c.get("api_key") or "").strip():
            return "NameSilo: 需 API Key"
        dom4 = [x.strip() for x in (cfg.get("ipv4_domains") or []) if x.strip()]
        dom6 = [x.strip() for x in (cfg.get("ipv6_domains") or []) if x.strip()]
        if not dom4 and not dom6:
            return "NameSilo: 需至少配置一个 FQDN"
    elif prov == "porkbun":
        c = cfg.get("porkbun") or {}
        if not (c.get("api_key") or "").strip() or not (c.get("secret_api_key") or "").strip():
            return "Porkbun: 需 API Key 与 Secret API Key"
        dom4 = [x.strip() for x in (cfg.get("ipv4_domains") or []) if x.strip()]
        dom6 = [x.strip() for x in (cfg.get("ipv6_domains") or []) if x.strip()]
        if not dom4 and not dom6:
            return "Porkbun: 需至少配置一个 FQDN"
    else:
        return f"不支持的 provider: {prov}"
    return None
