"""HTTP file browsing API dispatch helpers."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import parse_qs


def dispatch_get(handler, parsed, safe_relative_path, ensure_under_root, human_size) -> bool:
    path = str(getattr(parsed, "path", "") or "")

    if path == "/api/http/path-scan":
        if not handler._require_lan():
            return True
        query = parse_qs(parsed.query)
        path_raw = str(query.get("path", [""])[0] or "").strip()
        if not path_raw:
            handler._error("Missing path parameter", status=400)
            return True
        try:
            info = handler._http_path_scan(path_raw)
            handler._send_json(info)
            return True
        except Exception as exc:
            handler._error(f"Path scan failed: {exc}", status=500)
            return True

    if path == "/api/directories":
        if not handler._require_lan():
            return True
        try:
            query = parse_qs(parsed.query)
            root_raw = query.get("root_dir", [None])[0]
            http_root = (
                handler._http_root_from_raw(root_raw, require_exists=True)
                if root_raw is not None
                else handler._http_root_dir()
            )
            stats_raw = str(query.get("stats", ["1"])[0] or "1").strip().lower()
            with_stats = stats_raw not in {"0", "false", "no", "off"}
            rel_dir = safe_relative_path(query.get("dir", ["."])[0])
            directories = handler._list_child_directories(rel_dir, root_dir=http_root)
            stats = handler._directory_stats(rel_dir, root_dir=http_root) if with_stats else {}
            handler._send_json(
                {
                    "directories": directories,
                    "current_dir": rel_dir,
                    "stats": stats,
                    "http_root_dir": str(http_root),
                }
            )
            return True
        except ValueError as exc:
            handler._error(str(exc), status=403)
            return True
        except FileNotFoundError as exc:
            handler._error(str(exc), status=404)
            return True
        except Exception as exc:
            handler._error(f"Directory query failed: {exc}", status=500)
            return True

    if path == "/api/files":
        if not handler._require_lan():
            return True
        try:
            query = parse_qs(parsed.query)
            root_raw = query.get("root_dir", [None])[0]
            http_root = (
                handler._http_root_from_raw(root_raw, require_exists=True)
                if root_raw is not None
                else handler._http_root_dir()
            )
            rel_dir = safe_relative_path(query.get("dir", ["."])[0])
            target_dir = ensure_under_root(http_root, http_root / rel_dir)
            if not target_dir.exists() or not target_dir.is_dir():
                handler._error("Directory does not exist", status=404)
                return True

            items = []
            for root, dirnames, files in os.walk(target_dir):
                dirnames[:] = [d for d in dirnames if not handler._is_hidden_system_name(d)]
                for filename in files:
                    if handler._is_hidden_system_name(filename):
                        continue
                    full_path = Path(root) / filename
                    rel_file = full_path.relative_to(http_root).as_posix()
                    file_size = full_path.stat().st_size
                    items.append(
                        {
                            "relative_path": rel_file,
                            "size": file_size,
                            "size_human": human_size(file_size),
                            "http_url": handler._build_http_url(rel_file),
                        }
                    )
            items.sort(key=lambda x: x["relative_path"])
            handler._send_json({"items": items, "http_root_dir": str(http_root)})
            return True
        except ValueError as exc:
            handler._error(str(exc), status=403)
            return True
        except Exception as exc:
            handler._error(f"Scan failed: {exc}", status=500)
            return True

    return False
