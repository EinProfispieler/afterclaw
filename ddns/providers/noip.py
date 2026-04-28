"""No-IP DDNS：HTTP Basic Auth 更新接口。"""

from __future__ import annotations

import urllib.request
from base64 import b64encode
from typing import Optional, Tuple


def update(cfg: dict, ipv4: Optional[str], ipv6: Optional[str]) -> Tuple[bool, str]:
    c = (cfg or {}).get("noip") or {}
    username = (c.get("username") or "").strip()
    password = (c.get("password") or "").strip()
    hostname = (c.get("hostname") or "").strip()
    if not username or not password or not hostname:
        raise ValueError("No-IP 需要 username、password、hostname")
    ip = ipv4 or ipv6
    if not ip:
        raise ValueError("No-IP 需要至少一个公网地址")
    creds = b64encode(f"{username}:{password}".encode()).decode()
    url = f"https://dynupdate.no-ip.com/nic/update?hostname={hostname}&myip={ip}"
    req = urllib.request.Request(url, headers={"Authorization": f"Basic {creds}", "User-Agent": "storage-ctrl-ddns/2 randypku@github"})
    with urllib.request.urlopen(req, timeout=25) as r:
        body = r.read().decode("utf-8", errors="replace").strip()
    if body.startswith("good") or body.startswith("nochg"):
        return True, f"ip={ip}"
    raise RuntimeError(f"No-IP 返回: {body[:200]}")
