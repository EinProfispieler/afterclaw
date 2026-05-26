"""Shared config schema keys/default blocks used across runtime layers."""

from __future__ import annotations

from copy import deepcopy

CONFIG_VERSION = 1

MODULE_KEYS = ("qbt", "ddns", "docker", "shareclip", "http")
QBT_CLIENT_KEYS = ("qbittorrent", "deluge", "transmission", "rtorrent")
NETDISK_SOURCE_KEYS = (
    "baidu",
    "ali",
    "guangya",
    "dropbox",
    "mega",
    "onedrive",
    "gdrive",
)

DEFAULT_QBT_HOMEPAGE_CLIENTS_ENABLED = {
    "qbittorrent": True,
    "deluge": False,
    "transmission": False,
    "rtorrent": False,
}
DEFAULT_QBT_HOMEPAGE_CLIENTS_ORDER = list(QBT_CLIENT_KEYS)
DEFAULT_NETDISK_SOURCES = {
    "baidu": True,
    "ali": True,
    "guangya": True,
    "dropbox": False,
    "mega": False,
    "onedrive": False,
    "gdrive": False,
}
DEFAULT_UI_CONFIG = {
    "hero_preset": "default",
    "hero_custom_bg_file": "",
    "system_name": "",
    "brand_logo_url": "",
}

SOURCE_PROFILE_KEYS = ("official", "china", "aws_us", "aws_eu", "aws_ap")
DEFAULT_SOURCE_POLICY = {
    "docker_source_profile": "official",
    "docker_mirror_custom": "",
    "npm_source_profile": "official",
    "npm_registry_custom": "",
    "github_raw_source_profile": "official",
    "github_raw_base_custom": "",
}


def default_modules() -> dict[str, bool]:
    return {k: True for k in MODULE_KEYS}


def default_qbt_homepage_clients_enabled() -> dict[str, bool]:
    return dict(DEFAULT_QBT_HOMEPAGE_CLIENTS_ENABLED)


def default_qbt_homepage_clients_order() -> list[str]:
    return list(DEFAULT_QBT_HOMEPAGE_CLIENTS_ORDER)


def default_netdisk_sources() -> dict[str, bool]:
    return dict(DEFAULT_NETDISK_SOURCES)


def default_ui_config() -> dict[str, str]:
    return deepcopy(DEFAULT_UI_CONFIG)


def default_source_policy() -> dict[str, str]:
    return deepcopy(DEFAULT_SOURCE_POLICY)
