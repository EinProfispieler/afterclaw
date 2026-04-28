from __future__ import annotations

import urllib.parse
import urllib.request


def _http_get(url: str, timeout: float = 20.0) -> tuple[int, bytes]:
    req = urllib.request.Request(url, headers={"User-Agent": "storage-ctrl-ddns/2"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.getcode() or 0, r.read() or b""


def update_a(cfg: dict, ip: str) -> bool:
    d = cfg.get("duckdns") or {}
    dom = urllib.parse.quote((d.get("domain") or "").strip(), safe="")
    tok = urllib.parse.quote((d.get("token") or "").strip(), safe="")
    u = f"https://www.duckdns.org/update?domains={dom}&token={tok}&ip={ip}"
    code, body = _http_get(u)
    b = (body or b"").decode("utf-8", errors="replace").strip()
    if code == 200 and b == "OK":
        return True
    raise RuntimeError(f"DuckDNS 返回 HTTP {code}: {b[:200]}")
