"""公网 IPv4/IPv6 探测，支持多 URL 与（Linux）网卡。"""

from __future__ import annotations

import ipaddress
import re
import subprocess
from typing import List, Optional

import urllib.parse
import urllib.request


def _is_public_v4(s: str) -> bool:
    try:
        ip = ipaddress.ip_address(s.strip())
        return bool(ip.version == 4 and ip.is_global)
    except ValueError:
        return False


def _is_global_v6(s: str) -> bool:
    try:
        ip = ipaddress.ip_address(s.strip())
        return bool(ip.version == 6 and ip.is_global)
    except ValueError:
        return False


def _http_get_text(url: str, timeout: float = 20.0) -> str:
    req = urllib.request.Request(
        url, headers={"User-Agent": "storage-ctrl-ddns/2"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return (r.read() or b"").decode("utf-8", errors="replace").strip()


def get_public_ipv4(urls: List[str] | None) -> str:
    from ..defaults import DEFAULT_V4_URLS

    custom = [u.strip() for u in (urls or []) if (u or "").strip()]
    if custom:
        # 用户自定义列表优先；若全部失败则自动尝试内置兜底 URL。
        seen: set[str] = set()
        chain: List[str] = []
        for u in custom + list(DEFAULT_V4_URLS):
            if not u or u in seen:
                continue
            seen.add(u)
            chain.append(u)
    else:
        chain = list(DEFAULT_V4_URLS)
    last: Optional[Exception] = None
    last_url: str = ""
    for url in chain:
        try:
            t = _http_get_text(url)
            line = t.splitlines()[0].strip() if t else ""
            m = re.search(
                r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b",
                line,
            )
            if m:
                line = m.group(0)
            if not line:
                continue
            if _is_public_v4(line):
                return line
        except Exception as e:
            last = e
            last_url = url
            continue
    if last:
        tail = f"（最后失败 URL: {last_url}）" if last_url else ""
        raise RuntimeError(f"无法获取公网 IPv4: {last!s}{tail}")
    raise RuntimeError("无法获取公网 IPv4")


def get_ipv4_from_interface(iface: str) -> str:
    iface = (iface or "").strip()
    if not iface:
        raise ValueError("未配置网卡名")
    try:
        out = subprocess.check_output(
            ["ip", "-4", "addr", "show", "dev", iface, "scope", "global"],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError) as e:
        raise RuntimeError(f"读取网卡 IPv4 失败: {e}") from e
    for m in re.finditer(
        r"inet ([0-9.]+)/",
        out,
    ):
        a = m.group(1)
        if _is_public_v4(a):
            return a
    raise RuntimeError("该网卡上无可用公网 IPv4")


def get_public_ipv6(urls: List[str] | None) -> str:
    from ..defaults import DEFAULT_V6_URLS

    custom = [u.strip() for u in (urls or []) if (u or "").strip()]
    if custom:
        seen: set[str] = set()
        chain: List[str] = []
        for u in custom + list(DEFAULT_V6_URLS):
            if not u or u in seen:
                continue
            seen.add(u)
            chain.append(u)
    else:
        chain = list(DEFAULT_V6_URLS)
    last: Optional[Exception] = None
    last_url: str = ""
    for url in chain:
        try:
            t = _http_get_text(url, timeout=25.0)
            for line in t.splitlines():
                line = line.strip()
                m = re.search(
                    r"([0-9a-fA-F:]{2,}:[0-9a-fA-F:]{2,}|[0-9a-fA-F:]+::[0-9a-fA-F:]+|::1)",
                    line,
                )
                if m:
                    line = m.group(1)
                if not line or "::1" in line and line == "::1":
                    continue
                if _is_global_v6(line):
                    return line
        except Exception as e:
            last = e
            last_url = url
            continue
    if last:
        tail = f"（最后失败 URL: {last_url}）" if last_url else ""
        raise RuntimeError(f"无法获取公网 IPv6: {last!s}{tail}")
    raise RuntimeError("无法获取公网 IPv6")


def get_ipv6_from_interface(iface: str) -> str:
    iface = (iface or "").strip()
    if not iface:
        raise ValueError("未配置网卡名")
    try:
        out = subprocess.check_output(
            ["ip", "-6", "addr", "show", "dev", iface, "scope", "global"],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError) as e:
        raise RuntimeError(f"读取网卡 IPv6 失败: {e}") from e
    for m in re.finditer(r"inet6 ([0-9a-fA-F:]+)/", out):
        a = m.group(1)
        if a.startswith("fe80:"):
            continue
        if _is_global_v6(a):
            return a
    raise RuntimeError("该网卡上无可用全局 IPv6")
