"""Volcengine TrafficRoute DNS 高层 API。"""

from __future__ import annotations

import json
from typing import Any, List

from .signer import volc_tr_request

_ERR = "error"


def _ok(resp: dict) -> str | None:
    meta = resp.get("ResponseMetadata") or {}
    e = (meta.get("Error") or {}) if isinstance(meta, dict) else {}
    code = (e.get("Code") or "").strip()
    msg = (e.get("Message") or "").strip()
    if code or msg:
        return f"{code} {msg}".strip()
    return None


def list_zones(ak: str, sk: str, key: str) -> list[dict[str, Any]]:
    r: dict = volc_tr_request(
        "GET",
        "ListZones",
        {"Key": [key]},
        None,
        ak,
        sk,
    )
    err = _ok(r)
    if err:
        raise RuntimeError(f"ListZones: {err}")
    return list((r.get("Result") or {}).get("Zones") or [])


def get_zone_id(ak: str, sk: str, zone_name: str) -> int:
    for z in list_zones(ak, sk, zone_name):
        if (z or {}).get("ZoneName") == zone_name:
            return int((z or {}).get("ZID") or 0)
    raise RuntimeError(f"未在 TrafficRoute 中找到域: {zone_name}")


def list_records(ak: str, sk: str, zid: int, rtype: str, host: str) -> list[dict]:
    r: dict = volc_tr_request(
        "GET",
        "ListRecords",
        {
            "ZID": [str(zid)],
            "Type": [rtype],
            "Host": [host],
            "SearchMode": ["exact"],
            "PageNumber": ["1"],
            "PageSize": ["500"],
        },
        None,
        ak,
        sk,
    )
    err = _ok(r)
    if err:
        raise RuntimeError(f"ListRecords: {err}")
    return list((r.get("Result") or {}).get("Records") or [])


def create_record(
    ak: str,
    sk: str,
    zid: int,
    host: str,
    rtype: str,
    value: str,
    ttl: int,
) -> None:
    rec = {
        "ZID": zid,
        "Host": host,
        "Type": rtype,
        "Value": value,
        "TTL": int(ttl),
        "Line": "default",
    }
    b = json.dumps(rec, ensure_ascii=False).encode("utf-8")
    r: dict = volc_tr_request("POST", "CreateRecord", None, b, ak, sk)
    err = _ok(r)
    if err:
        raise RuntimeError(f"CreateRecord: {err}")


def update_record(
    ak: str, sk: str, record: dict, value: str, ttl: int
) -> None:
    record = {**record, "Value": value, "TTL": int(ttl)}
    b = json.dumps(record, ensure_ascii=False).encode("utf-8")
    r: dict = volc_tr_request("POST", "UpdateRecord", None, b, ak, sk)
    err = _ok(r)
    if err:
        raise RuntimeError(f"UpdateRecord: {err}")
