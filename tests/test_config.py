import json
from pathlib import Path

from fcc.config import (
    _normalize_rel_dir_setting,
    load_app_config,
    save_app_config,
)


def test_normalize_rel_dir_setting():
    assert _normalize_rel_dir_setting("") == "."
    assert _normalize_rel_dir_setting("/") == "."
    assert _normalize_rel_dir_setting("/BT/TV/") == "BT/TV"


def test_load_save_config_roundtrip(tmp_path: Path):
    cfg = load_app_config(tmp_path)
    cfg["terminal"]["host"] = "127.0.0.1"
    cfg["terminal"]["key_file"] = "id_ed25519.pem"
    saved = save_app_config(cfg, tmp_path)
    p = tmp_path / "app_config.json"
    assert p.exists()
    raw = json.loads(p.read_text(encoding="utf-8"))
    assert raw["terminal"]["host"] == "127.0.0.1"
    assert saved["terminal"]["key_file"] == "id_ed25519.pem"
