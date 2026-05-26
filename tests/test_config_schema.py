from __future__ import annotations

import app
from fcc import config as fcc_config
from fcc import config_schema


def test_config_schema_default_helpers_return_independent_copies():
    a = config_schema.default_modules()
    b = config_schema.default_modules()
    a["qbt"] = False
    assert b["qbt"] is True

    x = config_schema.default_qbt_homepage_clients_enabled()
    y = config_schema.default_qbt_homepage_clients_enabled()
    x["qbittorrent"] = False
    assert y["qbittorrent"] is True


def test_default_configs_reuse_shared_schema_version_and_keys():
    app_cfg = app.default_app_config()
    fcc_cfg = fcc_config.default_app_config()
    assert app_cfg["version"] == config_schema.CONFIG_VERSION
    assert fcc_cfg["version"] == config_schema.CONFIG_VERSION
    assert tuple(app_cfg["modules"].keys()) == config_schema.MODULE_KEYS
    assert tuple(fcc_cfg["modules"].keys()) == config_schema.MODULE_KEYS


def test_default_configs_are_normalized_via_single_path():
    assert app.default_app_config() == app.normalize_app_config({})
    assert fcc_config.default_app_config() == fcc_config.normalize_app_config({})


def test_app_migration_entrypoint_v0_to_v1():
    migrated = app._migrate_app_config_payload(
        {"version": 0, "http_monitor": True, "http_default_dir": "/Private"}
    )
    assert migrated["version"] == 1
    assert migrated["modules"]["http"] is True
    assert migrated["http_service"]["default_dir"] == "/Private"
