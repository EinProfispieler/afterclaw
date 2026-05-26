"""Lightweight status/read-only GET API dispatch helpers."""

from __future__ import annotations


def dispatch_get(
    handler,
    parsed,
    app_root,
    load_app_config,
    normalize_rel_dir_setting,
    build_terminal_launch_meta,
    ui_theme_payload,
    active_web_port,
    default_public_scheme,
    default_public_host,
    app_version_text,
    app_version,
    parse_qs,
) -> bool:
    path = str(getattr(parsed, "path", "") or "")

    if path == "/api/base":
        if not handler._require_lan():
            return True
        app_cfg = load_app_config(app_root)
        http_cfg = (app_cfg or {}).get("http_service") or {}
        http_root = handler._http_root_dir(app_cfg)
        handler._send_json(
            {
                "storage_root": str(http_root),
                "http_root_dir": str(http_root),
                "web_port": active_web_port,
                "public_base_url": f"{default_public_scheme}://{default_public_host}",
                "downloads_enabled": handler._downloads_effective_enabled(),
                "default_http_dir": normalize_rel_dir_setting(http_cfg.get("default_dir", ".")),
                "terminal": build_terminal_launch_meta(app_cfg),
                "ui_theme": ui_theme_payload(app_cfg, app_root),
            }
        )
        return True

    if path == "/api/speed":
        if not handler._require_lan():
            return True
        handler._send_json(handler._speed_snapshot())
        return True

    if path == "/api/metrics/history":
        if not handler._require_lan():
            return True
        handler._send_json(handler._metrics_history_payload())
        return True

    if path == "/api/process-net":
        if not handler._require_lan():
            return True
        source_ip_pools = handler._http_source_ip_pools()
        data = handler.process_detail_sampler.detailed_snapshot(
            lambda row: handler._infer_process_source_by_row(row, source_ip_pools)
        ) or {}
        payload = {
            **(data if isinstance(data, dict) else {}),
            "current_version": app_version_text,
            "app_version": app_version,
        }
        handler._send_json(payload, cors=True)
        return True

    if path == "/api/transfers":
        if not handler._require_lan():
            return True
        handler._send_json(handler._transfer_snapshot())
        return True

    if path == "/api/control/status":
        if not handler._require_lan():
            return True
        query = parse_qs(parsed.query)
        client = str(query.get("client", [""])[0] or "").strip().lower()
        handler._send_json(handler._control_status_payload(client))
        return True

    return False
