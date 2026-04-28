"""Security helpers shared across FCC modules."""

from __future__ import annotations

import ipaddress
from pathlib import Path


def is_lan(ip: str) -> bool:
    raw = str(ip or "").strip()
    if not raw:
        return False
    try:
        ip_obj = ipaddress.ip_address(raw)
    except ValueError:
        return False
    return ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local


def ensure_under_root(root: Path, candidate: Path) -> Path:
    root_resolved = Path(root).resolve()
    resolved = Path(candidate).resolve()
    if root_resolved not in [resolved, *resolved.parents]:
        raise ValueError("路径不在允许范围内")
    return resolved


def safe_relative_path(value: str) -> str:
    text = (value or ".").strip().replace("\\", "/")
    if text.startswith("/"):
        text = text[1:]
    # keep behavior compatible with existing app: sanitize absolute prefix,
    # actual boundary checks are enforced by ensure_under_root.
    return text or "."
