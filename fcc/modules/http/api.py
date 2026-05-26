"""HTTP module API dispatch helpers."""

from __future__ import annotations

from http import HTTPStatus


def dispatch_post(
    handler,
    parsed,
    app_root,
    load_app_config,
    save_app_config,
    normalize_source_ip_pool_source,
    fetch_source_ip_pools_from_source,
    normalize_source_ip_pools,
    merge_source_ip_pools,
    source_pool_keys,
) -> bool:
    path = str(getattr(parsed, "path", "") or "")
    if path != "/api/http/source-ip-pools/sync":
        return False

    if not handler._require_lan():
        return True
    body = handler._parse_body()
    if body is None:
        body = {}
    if not isinstance(body, dict):
        handler._error("Request body must be a JSON object", status=HTTPStatus.BAD_REQUEST)
        return True

    current = load_app_config(app_root)
    http_cfg = current.setdefault("http_service", {})
    raw_source = body.get("source") if "source" in body else http_cfg.get("source_ip_pool_source")
    source = normalize_source_ip_pool_source(raw_source)
    merge_raw = body.get("merge", True)
    if isinstance(merge_raw, str):
        lv = merge_raw.strip().lower()
        merge_mode = lv not in {"0", "false", "no", "off", "replace"}
    else:
        merge_mode = bool(merge_raw)
    try:
        pulled = fetch_source_ip_pools_from_source(source)
    except ValueError as exc:
        handler._error(str(exc), status=HTTPStatus.BAD_REQUEST)
        return True
    except Exception as exc:
        handler._error(f"Source sync failed: {exc}", status=HTTPStatus.BAD_GATEWAY)
        return True

    local_pools = normalize_source_ip_pools(http_cfg.get("source_ip_pools"))
    remote_pools = normalize_source_ip_pools((pulled or {}).get("pools"))
    pools = merge_source_ip_pools(local_pools, remote_pools) if merge_mode else remote_pools
    http_cfg["source_ip_pools"] = pools
    http_cfg["source_ip_pool_source"] = source
    saved = save_app_config(current, app_root)
    counts = {k: len((pools or {}).get(k, [])) for k in source_pool_keys}
    remote_counts = {k: len((remote_pools or {}).get(k, [])) for k in source_pool_keys}
    local_counts = {k: len((local_pools or {}).get(k, [])) for k in source_pool_keys}
    handler._send_json(
        {
            "ok": True,
            "source": source,
            "mode": "merge" if merge_mode else "replace",
            "counts": counts,
            "remote_counts": remote_counts,
            "local_counts": local_counts,
            "files_used": (pulled or {}).get("files_used", []),
            "meta": (pulled or {}).get("meta", {}),
            "pools": pools,
            "config": saved,
        }
    )
    return True
