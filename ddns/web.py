"""内嵌的 DDNS 设置页 HTML 模板（独立文件，避免塞满 app.py）。"""

from __future__ import annotations

from pathlib import Path

_TEMPLATE: Path = Path(__file__).resolve().parent / "templates" / "ddns_settings.html"


def load_ddns_settings_page() -> str:
    return _TEMPLATE.read_text(encoding="utf-8")
