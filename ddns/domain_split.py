"""将 FQDN 拆为 (子域标签, 注册区名)，与 ddns-go 的 publicsuffix+标签规则对齐。"""

from __future__ import annotations

from typing import Optional, Tuple

SplitResult = Tuple[str, str]  # subdomain label(s), eTLD+1 / zone name


def split_fqdn(fqdn: str) -> Optional[SplitResult]:
    s = (fqdn or "").strip().lower()
    if not s or s.startswith("."):
        return None
    if "://" in s:
        return None
    if ":" in s and s.count(":") < 2:
        a, b = s.split(":", 1)
        a, b = a.strip(), b.strip()
        if a and b and "." in b:
            if a == "@" or a:
                return (a, b)

    try:
        import tldextract  # type: ignore

        ext = tldextract.extract(s)
        if not ext.suffix:
            return None
        zone = f"{ext.domain}.{ext.suffix}"
        if not ext.subdomain:
            return ("@", zone)
        return (ext.subdomain, zone)
    except Exception:
        return _split_manual(s)


def _split_manual(fqdn: str) -> Optional[SplitResult]:
    parts = fqdn.split(".")
    if len(parts) < 2:
        return None
    if len(parts) == 2:
        return ("@", f"{parts[0]}.{parts[1]}")
    return (".".join(parts[:-2]), f"{parts[-2]}.{parts[-1]}")
