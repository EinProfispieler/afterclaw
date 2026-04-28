from __future__ import annotations

import urllib.parse
import urllib.request


def _http_get(url: str, timeout: float = 30.0) -> tuple[int, bytes]:
    req = urllib.request.Request(url, headers={"User-Agent": "storage-ctrl-ddns/2"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.getcode() or 0, r.read() or b""


def update_get(cfg: dict, ip: str) -> bool:
    t = (cfg.get("url") or {}).get("template") or ""
    if not t.strip() or "{ip}" not in t:
        raise ValueError("URL 模板需包含 {ip}")
    url = t.replace("{ip}", urllib.parse.quote(ip, safe="."))
    code, _ = _http_get(url)
    if 200 <= code < 300:
        return True
    raise RuntimeError(f"HTTP {code}")
