from __future__ import annotations

from pathlib import Path


def _app_source() -> str:
    root = Path(__file__).resolve().parent.parent
    return (root / "app.py").read_text(encoding="utf-8")


def test_backup_ui_and_api_surface_removed_from_app():
    src = _app_source()
    assert "tabBackupBtn" not in src
    assert "panel-backup" not in src
    assert "/api/backup/" not in src
