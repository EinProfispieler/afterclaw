"""App config GET/POST API dispatch helpers."""

from __future__ import annotations

from http import HTTPStatus

from fcc import config_schema


def dispatch_get(handler, parsed, app_root, load_app_config) -> bool:
    path = str(getattr(parsed, "path", "") or "")
    if path != "/api/app-config":
        return False
    if not handler._require_lan():
        return True
    handler._send_json({"config": load_app_config(app_root)})
    return True


def dispatch_post(
    handler,
    parsed,
    app_root,
    load_app_config,
    save_app_config,
    normalize_web_port,
    normalize_rel_dir_setting,
    normalize_source_ip_pools,
    normalize_source_ip_pool_source,
    normalize_transfer_recent_ttl,
    normalize_http_keepalive_idle_timeout,
    normalize_ssh_port,
    normalize_terminal_key_file_name,
    normalize_ui_hero_preset,
    normalize_source_policy,
    ensure_under_root,
    ui_theme_payload,
    default_web_port,
    active_web_port,
    default_transfer_recent_ttl_sec,
    default_http_keepalive_idle_timeout_sec,
    ddns_mod,
) -> bool:
    path = str(getattr(parsed, "path", "") or "")
    if path != "/api/app-config":
        return False

    if not handler._require_lan():
        return True
    body = handler._parse_body()
    if not isinstance(body, dict):
        handler._error("Request body must be a JSON object", status=HTTPStatus.BAD_REQUEST)
        return True

    current = load_app_config(app_root)
    prev_qbt_enabled = handler._qbt_module_enabled(current)
    prev_ddns_enabled = handler._ddns_module_enabled(current)
    prev_shareclip_enabled = handler._shareclip_module_enabled(current)
    prev_http_enabled = handler._http_module_enabled(current)

    if "web_port" in body:
        web_port_raw = body.get("web_port")
        try:
            web_port_new = int(web_port_raw)
        except Exception:
            handler._error("Service port must be an integer in 1-65535", status=HTTPStatus.BAD_REQUEST)
            return True
        if web_port_new <= 0 or web_port_new > 65535:
            handler._error("Service port must be an integer in 1-65535", status=HTTPStatus.BAD_REQUEST)
            return True
        current["web_port"] = web_port_new

    if isinstance(body.get("modules"), dict):
        mods = current.setdefault("modules", {})
        incoming = body["modules"]
        for key in config_schema.MODULE_KEYS:
            if key in body["modules"]:
                mods[key] = bool(body["modules"].get(key))
        if "http" not in incoming and "http_monitor" in incoming:
            mods["http"] = bool(incoming.get("http_monitor"))

    if isinstance(body.get("qbt"), dict):
        qbt_cfg = current.setdefault("qbt", {})
        if "monitor_enabled" in body["qbt"]:
            qbt_cfg["monitor_enabled"] = bool(body["qbt"].get("monitor_enabled"))
        if "client" in body["qbt"]:
            client = str(body["qbt"].get("client", "") or "").strip().lower()
            if client in set(config_schema.QBT_CLIENT_KEYS):
                qbt_cfg["client"] = client
        if "service_unit" in body["qbt"]:
            qbt_cfg["service_unit"] = str(body["qbt"].get("service_unit", "") or "").strip()
        if "docker_container" in body["qbt"]:
            qbt_cfg["docker_container"] = str(body["qbt"].get("docker_container", "") or "").strip()
        if "api_url" in body["qbt"]:
            qbt_cfg["api_url"] = str(body["qbt"].get("api_url", "") or "").strip()
        if "homepage_clients_enabled" in body["qbt"] and isinstance(body["qbt"]["homepage_clients_enabled"], dict):
            enabled_map = qbt_cfg.get("homepage_clients_enabled")
            if not isinstance(enabled_map, dict):
                enabled_map = {}
            for key in config_schema.QBT_CLIENT_KEYS:
                if key in body["qbt"]["homepage_clients_enabled"]:
                    enabled_map[key] = bool(body["qbt"]["homepage_clients_enabled"].get(key))
            qbt_cfg["homepage_clients_enabled"] = enabled_map
        if "homepage_clients_order" in body["qbt"] and isinstance(body["qbt"]["homepage_clients_order"], list):
            out = []
            seen = set()
            for item in body["qbt"]["homepage_clients_order"]:
                x = str(item or "").strip().lower()
                if x in set(config_schema.QBT_CLIENT_KEYS) and x not in seen:
                    seen.add(x)
                    out.append(x)
            for x in config_schema.QBT_CLIENT_KEYS:
                if x not in seen:
                    out.append(x)
            qbt_cfg["homepage_clients_order"] = out

    http_path_cfg_changed = False
    if isinstance(body.get("http_service"), dict):
        http_cfg = current.setdefault("http_service", {})
        incoming_http = body["http_service"]
        if "root_dir" in incoming_http:
            root_dir = handler._http_root_from_raw(
                incoming_http.get("root_dir"),
                app_cfg=current,
                require_exists=True,
            )
            http_cfg["root_dir"] = str(root_dir)
            http_path_cfg_changed = True
        if "default_dir" in incoming_http:
            http_cfg["default_dir"] = normalize_rel_dir_setting(incoming_http.get("default_dir"))
            http_path_cfg_changed = True
        if "source_ip_pools" in incoming_http:
            http_cfg["source_ip_pools"] = normalize_source_ip_pools(incoming_http.get("source_ip_pools"))
        if "source_ip_pool_source" in incoming_http:
            http_cfg["source_ip_pool_source"] = normalize_source_ip_pool_source(incoming_http.get("source_ip_pool_source"))
        if "transfer_recent_ttl_sec" in incoming_http:
            http_cfg["transfer_recent_ttl_sec"] = normalize_transfer_recent_ttl(
                incoming_http.get("transfer_recent_ttl_sec"),
                http_cfg.get("transfer_recent_ttl_sec", default_transfer_recent_ttl_sec),
            )
        if "keepalive_idle_timeout_sec" in incoming_http:
            http_cfg["keepalive_idle_timeout_sec"] = normalize_http_keepalive_idle_timeout(
                incoming_http.get("keepalive_idle_timeout_sec"),
                http_cfg.get(
                    "keepalive_idle_timeout_sec",
                    default_http_keepalive_idle_timeout_sec,
                ),
            )

    if http_path_cfg_changed:
        http_cfg = current.setdefault("http_service", {})
        root_for_check = handler._http_root_from_raw(
            http_cfg.get("root_dir"),
            app_cfg=current,
            require_exists=True,
        )
        rel_default = normalize_rel_dir_setting(http_cfg.get("default_dir", "."))
        default_target = ensure_under_root(root_for_check, root_for_check / rel_default)
        if not default_target.exists() or not default_target.is_dir():
            handler._error(
                f"DefaultDirectory does not exist或不可访问: {default_target}",
                status=HTTPStatus.BAD_REQUEST,
            )
            return True

    if isinstance(body.get("terminal"), dict):
        term_cfg = current.setdefault("terminal", {})
        incoming_term = body["terminal"]
        if "enabled" in incoming_term:
            term_cfg["enabled"] = bool(incoming_term.get("enabled"))
        if "host" in incoming_term:
            host = str(incoming_term.get("host", "") or "").strip()
            if host:
                term_cfg["host"] = host
        if "port" in incoming_term:
            term_cfg["port"] = normalize_ssh_port(incoming_term.get("port"), 22)
        if "user" in incoming_term:
            user = str(incoming_term.get("user", "") or "").strip()
            if user:
                term_cfg["user"] = user
        if "auth_mode" in incoming_term:
            mode = str(incoming_term.get("auth_mode", "") or "").strip().lower()
            if mode in ("key", "password"):
                term_cfg["auth_mode"] = mode
        if "key_path" in incoming_term:
            term_cfg["key_path"] = str(incoming_term.get("key_path", "") or "").strip()
        if "key_file" in incoming_term:
            term_cfg["key_file"] = normalize_terminal_key_file_name(incoming_term.get("key_file", ""))

    if isinstance(body.get("ui"), dict):
        ui_cfg = current.setdefault("ui", {})
        incoming_ui = body["ui"]
        if "hero_preset" in incoming_ui:
            ui_cfg["hero_preset"] = normalize_ui_hero_preset(incoming_ui.get("hero_preset"))
        if "system_name" in incoming_ui:
            ui_cfg["system_name"] = str(incoming_ui.get("system_name", "") or "").strip()[:64]
        if "brand_logo_url" in incoming_ui:
            ui_cfg["brand_logo_url"] = str(incoming_ui.get("brand_logo_url", "") or "").strip()[:1024]
        ui_cfg["hero_custom_bg_file"] = ""

    if isinstance(body.get("netdisk_sources"), dict):
        nd_cfg = current.setdefault("netdisk_sources", {})
        incoming_nd = body["netdisk_sources"]
        for key in config_schema.NETDISK_SOURCE_KEYS:
            if key in incoming_nd:
                nd_cfg[key] = bool(incoming_nd.get(key))

    if isinstance(body.get("source_policy"), dict):
        current["source_policy"] = normalize_source_policy(body.get("source_policy"))

    saved = save_app_config(current, app_root)
    saved_http_cfg = (saved.get("http_service") or {}) if isinstance(saved, dict) else {}
    handler.__class__.transfer_recent_ttl_sec = normalize_transfer_recent_ttl(
        saved_http_cfg.get("transfer_recent_ttl_sec", default_transfer_recent_ttl_sec),
        default_transfer_recent_ttl_sec,
    )
    handler.__class__.http_keepalive_idle_timeout_sec = normalize_http_keepalive_idle_timeout(
        saved_http_cfg.get(
            "keepalive_idle_timeout_sec", default_http_keepalive_idle_timeout_sec
        ),
        default_http_keepalive_idle_timeout_sec,
    )

    web_port_restart_required = normalize_web_port(saved.get("web_port"), default_web_port) != active_web_port
    new_qbt_enabled = handler._qbt_module_enabled(saved)
    new_ddns_enabled = handler._ddns_module_enabled(saved)
    new_shareclip_enabled = handler._shareclip_module_enabled(saved)
    new_http_enabled = handler._http_module_enabled(saved)
    disconnect_triggered = False
    module_actions = []

    if prev_http_enabled and not new_http_enabled:
        with handler.control_lock:
            handler.downloads_enabled = False
            handler.__class__.downloads_enabled = False
        handler._cut_http_downloads_once()
        disconnect_triggered = True
        module_actions.append(
            {
                "module": "http",
                "action": "disable-downloads",
                "ok": True,
                "message": "HTTP module is disabled，已禁用上传并中断本程序上传Connect",
            }
        )
    elif not new_http_enabled:
        with handler.control_lock:
            handler.downloads_enabled = False
            handler.__class__.downloads_enabled = False
        module_actions.append(
            {
                "module": "http",
                "action": "disable-downloads",
                "ok": True,
                "message": "HTTP module is disabled，上传保持禁用",
            }
        )

    if prev_qbt_enabled and not new_qbt_enabled:
        qbt_info = handler._resolve_existing_unit(handler.qbt_candidates)
        if qbt_info.get("load_state") == "not-found":
            qbt_info = (
                handler._discover_unit_by_keywords(
                    handler._bt_service_keywords(((saved or {}).get("qbt") or {}).get("client", "qbittorrent"))
                )
                or qbt_info
            )
        qbt_unit = str((qbt_info or {}).get("unit", "") or "").strip()
        qbt_active = str((qbt_info or {}).get("active_state", "") or "").strip() == "active"
        if qbt_unit and qbt_active:
            ok, msg = handler._service_action(qbt_unit, "stop")
            module_actions.append(
                {
                    "module": "qbt",
                    "action": "stop-service",
                    "unit": qbt_unit,
                    "ok": bool(ok),
                    "message": "qB 服务已停止" if ok else f"停止 qB 服务失败：{msg}",
                }
            )
        elif qbt_unit:
            module_actions.append(
                {
                    "module": "qbt",
                    "action": "stop-service",
                    "unit": qbt_unit,
                    "ok": True,
                    "message": "qB 服务已是停止状态",
                }
            )
        else:
            module_actions.append(
                {
                    "module": "qbt",
                    "action": "stop-service",
                    "ok": False,
                    "message": "未找到 qB 服务",
                }
            )
        handler._qbt_reset_stats_cache()

    if prev_ddns_enabled and not new_ddns_enabled:
        if ddns_mod.config_path(app_root).exists():
            ok, msg = ddns_mod.service_action(app_root, "stop")
            module_actions.append(
                {
                    "module": "ddns",
                    "action": "stop-builtin",
                    "ok": bool(ok),
                    "message": "内置 DDNS 已停止" if ok else f"停止内置 DDNS failed: {msg}",
                }
            )
        ext_ddns = handler._resolve_existing_unit(handler.ddns_candidates)
        if ext_ddns.get("load_state") == "not-found":
            ext_ddns = (
                handler._discover_unit_by_keywords(["ddns", "duckdns", "cloudflare", "dnspod", "ddns-go"])
                or ext_ddns
            )
        ext_unit = str((ext_ddns or {}).get("unit", "") or "").strip()
        ext_active = str((ext_ddns or {}).get("active_state", "") or "").strip() == "active"
        if ext_unit and ext_active:
            ok, msg = handler._service_action(ext_unit, "stop")
            module_actions.append(
                {
                    "module": "ddns",
                    "action": "stop-service",
                    "unit": ext_unit,
                    "ok": bool(ok),
                    "message": "DDNS 服务已停止" if ok else f"停止 DDNS 服务失败：{msg}",
                }
            )

    if prev_shareclip_enabled and not new_shareclip_enabled:
        module_actions.append(
            {
                "module": "shareclip",
                "action": "disable-routes",
                "ok": True,
                "message": "ShareClip 接口已关闭",
            }
        )
        shareclip_svc = handler._discover_unit_by_keywords(["shareclip", "file-control-shareclip"])
        shareclip_unit = str((shareclip_svc or {}).get("unit", "") or "").strip()
        shareclip_active = str((shareclip_svc or {}).get("active_state", "") or "").strip() == "active"
        if shareclip_unit and shareclip_active:
            ok, msg = handler._service_action(shareclip_unit, "stop")
            module_actions.append(
                {
                    "module": "shareclip",
                    "action": "stop-service",
                    "unit": shareclip_unit,
                    "ok": bool(ok),
                    "message": "ShareClip 服务已停止" if ok else f"停止 ShareClip 服务失败：{msg}",
                }
            )

    handler._send_json(
        {
            "ok": True,
            "config": saved,
            "running_web_port": active_web_port,
            "web_port_restart_required": bool(web_port_restart_required),
            "http_disconnect_triggered": bool(disconnect_triggered),
            "module_actions": module_actions,
            "ui_theme": ui_theme_payload(saved, app_root),
        }
    )
    return True
