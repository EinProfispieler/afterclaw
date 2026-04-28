"""
火山引擎 TrafficRoute (DNS) OpenAPI 请求签名，与 jeessy2/ddns-go util.TrafficRouteSigner 一致。
参考: open.volcengineapi.com, Version 2018-08-01
"""

from __future__ import annotations

import hashlib
import hmac
import time
import urllib.parse
import urllib.request
from typing import Any

from ..defaults import (
    VOLC_TR_HOST,
    VOLC_TR_REGION,
    VOLC_TR_SERVICE,
    VOLC_TR_VERSION,
)

VERSION = VOLC_TR_VERSION
SERVICE = VOLC_TR_SERVICE
REGION = VOLC_TR_REGION
HOST = VOLC_TR_HOST


def _hmac_sha256(key: bytes, content: str) -> bytes:
    return hmac.new(key, content.encode("utf-8"), hashlib.sha256).digest()


def _hash_sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def traffic_route_sign(
    method: str,
    query: dict[str, list[str]] | None,
    ak: str,
    sk: str,
    action: str,
    body: bytes,
) -> tuple[str, dict[str, str]]:
    """返回 (url_with_query, headers)。"""
    q: dict[str, list[str]] = {k: list(v) for k, v in (query or {}).items()}
    q["Action"] = [action]
    q["Version"] = [VERSION]
    # 与 Go url.Values.Encode 一致：键排序后逐项展开
    qlist = []
    for k in sorted(q):
        for v in q[k]:
            qlist.append((k, v))
    raw_query = urllib.parse.urlencode(qlist, doseq=True)

    body = body or b""
    x_date = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    short_x = x_date[:8]
    x_ct_hash = _hash_sha256(body)
    content_type = "application/json"

    canonical = "\n".join(
        [
            method,
            "/",
            raw_query,
            "\n".join(
                [
                    "content-type:" + content_type,
                    "host:" + HOST,
                    "x-content-sha256:" + x_ct_hash,
                    "x-date:" + x_date,
                ]
            ),
            "",
            "content-type;host;x-content-sha256;x-date",
            x_ct_hash,
        ]
    )
    h_canon = _hash_sha256(canonical.encode("utf-8"))
    scope = f"{short_x}/{REGION}/{SERVICE}/request"
    to_sign = "\n".join(
        [
            "HMAC-SHA256",
            x_date,
            scope,
            h_canon,
        ]
    )

    k_date = _hmac_sha256(sk.encode("utf-8"), short_x)
    k_region = _hmac_sha256(k_date, REGION)
    k_service = _hmac_sha256(k_region, SERVICE)
    k_signing = _hmac_sha256(k_service, "request")
    sig = hmac.new(k_signing, to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
    cred = f"{ak}/{scope}"
    auth = (
        f"HMAC-SHA256 Credential={cred}, "
        f"SignedHeaders=content-type;host;x-content-sha256;x-date, "
        f"Signature={sig}"
    )

    url = f"https://{HOST}/?{raw_query}"
    headers = {
        "Host": HOST,
        "Content-Type": content_type,
        "X-Date": x_date,
        "X-Content-Sha256": x_ct_hash,
        "Authorization": auth,
    }
    return url, headers


def volc_tr_request(
    method: str,
    action: str,
    query: dict[str, list[str]] | None,
    body: bytes | None,
    ak: str,
    sk: str,
) -> Any:
    import json

    url, headers = traffic_route_sign(method, query, ak, sk, action, body or b"")
    req = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers=headers,
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read() or b""
    return json.loads(raw.decode("utf-8", errors="replace"))


__all__ = ["traffic_route_sign", "volc_tr_request", "VERSION", "HOST"]
