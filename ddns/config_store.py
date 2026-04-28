"""ddns_config.json 的读写、合并与轻量版本迁移。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Tuple

from .defaults import CONFIG_FILE_NAME, DEFAULT_V4_URLS, DEFAULT_V6_URLS

# re-exported for app
def config_path(app_root) -> Path:
    return Path(app_root) / CONFIG_FILE_NAME


def _default() -> dict[str, Any]:
    return {
        "version": 2,
        "enabled": False,
        "interval_sec": 300,
        "provider": "trafficroute",
        "ttl": 600,
        "ipv4": {
            "enabled": True,
            "gettype": "url",
            "urls": list(DEFAULT_V4_URLS),
            "interface": "",
        },
        "ipv6": {
            "enabled": False,
            "gettype": "url",
            "urls": list(DEFAULT_V6_URLS),
            "interface": "",
        },
        "ipv4_domains": [],
        "ipv6_domains": [],
        "domains": {"ipv4": [], "ipv6": []},
        "duckdns": {"domain": "", "token": ""},
        "cloudflare": {"zone_id": "", "record_id": "", "api_token": "", "proxied": False, "ttl": 1},
        "aliyun": {"access_key_id": "", "access_key_secret": ""},
        "dnspod": {"token": ""},
        "noip": {"username": "", "password": "", "hostname": ""},
        "godaddy": {"api_key": "", "api_secret": ""},
        "namecheap": {"dynamic_password": ""},
        "namesilo": {"api_key": ""},
        "porkbun": {"api_key": "", "secret_api_key": ""},
        "ddnsgo": {"base_url": "http://127.0.0.1:9876"},
        "url": {"template": ""},
        "trafficroute": {
            "access_key_id": "",
            "secret_access_key": "",
            "domain": "",
            "ttl": 600,
        },
    }


def _merge_section(base: dict, key: str, patch: Any) -> None:
    if not isinstance(patch, dict) or not isinstance(base.get(key), dict):
        return
    base[key] = {**base[key], **patch}


def load_config(app_root) -> dict:
    p = config_path(app_root)
    if not p.exists():
        return _default()
    try:
        with open(p, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except Exception:
        return _default()
    if not isinstance(raw, dict):
        return _default()
    return migrate(raw, app_root)


def migrate(raw: dict, app_root) -> dict:
    base = _default()
    base.update(
        {
            k: raw[k]
            for k in base
            if k in raw
            and k
            not in (
                "duckdns",
                "cloudflare",
                "url",
                "ipv4",
                "ipv6",
                "domains",
                "trafficroute",
                "aliyun",
                "dnspod",
                "noip",
                "godaddy",
                "namecheap",
                "namesilo",
                "porkbun",
                "ddnsgo",
            )
        }
    )
    for sub in (
        "duckdns",
        "cloudflare",
        "url",
        "ipv4",
        "ipv6",
        "domains",
        "trafficroute",
        "aliyun",
        "dnspod",
        "noip",
        "godaddy",
        "namecheap",
        "namesilo",
        "porkbun",
        "ddnsgo",
    ):
        if isinstance(raw.get(sub), dict):
            base[sub] = {**base[sub], **raw[sub]}
    if (raw.get("version") or 0) < 2:
        d = (raw.get("duckdns") or {}).get("domain", "")
        if d and not base.get("ipv4_domains"):
            suf = (raw.get("provider") or "").lower()
            if suf == "duckdns":
                base["ipv4_domains"] = [f"{d}.duckdns.org"]
        if (raw.get("provider") or "").lower() == "trafficroute" and (base.get("trafficroute") or {}).get("domain"):
            fq = (base.get("trafficroute") or {}).get("domain", "").strip()
            if isinstance(fq, str) and fq and not base.get("ipv4_domains"):
                base["ipv4_domains"] = [fq]
    base["version"] = 2
    for k in ("ipv4_domains", "ipv6_domains"):
        if not isinstance(base.get(k), list):
            base[k] = []
    doms = (base.get("domains") or {})
    if not isinstance(doms, dict):
        base["domains"] = {"ipv4": [], "ipv6": []}
    else:
        for kk in ("ipv4", "ipv6"):
            if not isinstance(doms.get(kk), list):
                doms[kk] = []
    return base


def save_config(app_root, cfg: dict) -> None:
    p = config_path(app_root)
    p.parent.mkdir(parents=True, exist_ok=True)
    cfg = {**cfg, "version": 2}
    with open(p, "w", encoding="utf-8") as f:
        f.write(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n")


def apply_config_from_body(app_root, body: dict) -> Tuple[bool, str]:
    if not isinstance(body, dict):
        return False, "请求体需为 JSON 对象"
    base = load_config(app_root)
    for k in (
        "enabled",
        "interval_sec",
        "provider",
        "ttl",
    ):
        if k in body:
            if k == "enabled":
                base["enabled"] = bool(body[k])
            elif k in ("interval_sec", "ttl"):
                try:
                    base[k] = max(60, int(body[k] or 300)) if k == "interval_sec" else int(body[k] or 600)
                except (TypeError, ValueError):
                    pass
            else:
                base["provider"] = str(body.get("provider") or "duckdns").strip().lower()
    if isinstance((body or {}).get("ttl"), (int, float, str)) and (body or {}).get("ttl") is not None:
        try:
            t = int(body["ttl"])
            base["ttl"] = t
            if isinstance(base.get("trafficroute"), dict):
                base["trafficroute"]["ttl"] = t
        except (TypeError, ValueError):
            pass
    for sub in (
        "duckdns",
        "cloudflare",
        "url",
        "ipv4",
        "ipv6",
        "domains",
        "trafficroute",
        "aliyun",
        "dnspod",
        "noip",
        "godaddy",
        "namecheap",
        "namesilo",
        "porkbun",
        "ddnsgo",
    ):
        if isinstance(body.get(sub), dict):
            _merge_section(base, sub, body[sub])
    if isinstance(body.get("ipv4_domains"), list):
        base["ipv4_domains"] = [str(x).strip() for x in body["ipv4_domains"] if str(x).strip()]
    if isinstance(body.get("ipv6_domains"), list):
        base["ipv6_domains"] = [str(x) for x in body["ipv6_domains"]]
    if isinstance((body.get("domains") or {}).get("ipv4"), list) or isinstance(
        (body.get("domains") or {}).get("ipv6"), list
    ):
        base["domains"] = {**(base.get("domains") or {}), **(body.get("domains") or {})}
    if "trafficroute" in body and isinstance(body["trafficroute"], dict) and "domain" in body["trafficroute"]:
        v = (body["trafficroute"] or {}).get("domain")
        if isinstance(v, str) and v.strip() and not body.get("ipv4_domains"):
            base.setdefault("ipv4_domains", [])
            if not base["ipv4_domains"]:
                base["ipv4_domains"] = [v.strip()]
    save_config(app_root, base)
    return True, "已保存"
