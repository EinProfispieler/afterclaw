"""Process-level network speed sampling helpers.

This module keeps parser/state logic out of the monolithic app runtime.
"""

from __future__ import annotations

import re
import subprocess
import threading
import time
from typing import Iterable, Sequence


SourceRules = Sequence[tuple[str, Iterable[str]]]


class ProcessSourceSpeedSampler:
    """Sample per-source upload/download speeds by parsing `ss -tinpH`."""

    def __init__(self, source_rules: SourceRules):
        self.source_rules: tuple[tuple[str, tuple[str, ...]], ...] = tuple(
            (
                str(source),
                tuple(str(keyword or "").strip() for keyword in (keywords or []) if str(keyword or "").strip()),
            )
            for source, keywords in (source_rules or [])
            if str(source or "").strip()
        )
        self._lock = threading.Lock()
        self._state = {"last_ts": 0.0, "socket_counters": {}}

    def _infer_source_by_process_name(self, process_name: str) -> str:
        pname = str(process_name or "").strip().lower()
        if not pname:
            return ""
        for source, keywords in self.source_rules:
            if any(str(k).lower() in pname for k in keywords):
                return str(source)
        return ""

    def _collect_process_socket_counters(self) -> dict:
        try:
            proc = subprocess.run(
                ["ss", "-tinpH"],
                capture_output=True,
                text=True,
                timeout=2.0,
                check=False,
            )
            if proc.returncode != 0:
                return {}
            lines = proc.stdout.splitlines()
        except Exception:
            return {}

        out = {}
        i = 0
        while i < len(lines):
            header = str(lines[i] or "")
            if not header.strip():
                i += 1
                continue
            detail = ""
            if i + 1 < len(lines) and lines[i + 1].startswith("\t"):
                detail = str(lines[i + 1] or "")
                i += 2
            else:
                i += 1

            user_matches = re.findall(r'\("([^"]+)",pid=(\d+),fd=(\d+)\)', header)
            if not user_matches:
                continue
            endpoint_match = re.match(r"^\S+\s+\d+\s+\d+\s+(\S+)\s+(\S+)", header)
            if endpoint_match:
                local_ep, peer_ep = endpoint_match.group(1), endpoint_match.group(2)
            else:
                local_ep, peer_ep = "-", "-"
            state = (header.split(None, 1)[0] or "").strip().upper()

            combo = f"{header} {detail}"
            acked_match = re.search(r"bytes_acked:(\d+)", combo)
            recv_match = re.search(r"bytes_received:(\d+)", combo)
            acked = int(acked_match.group(1)) if acked_match else 0
            received = int(recv_match.group(1)) if recv_match else 0

            for process_name, pid, _fd in user_matches:
                source = self._infer_source_by_process_name(process_name)
                if not source:
                    continue
                socket_key = f"{source}|{pid}|{local_ep}|{peer_ep}"
                out[socket_key] = {
                    "source": source,
                    "pid": int(pid),
                    "process": str(process_name),
                    "state": state,
                    "local_ep": str(local_ep),
                    "peer_ep": str(peer_ep),
                    "acked": acked,
                    "received": received,
                }
        return out

    def source_speed_snapshot(self) -> dict:
        now = time.time()
        current = self._collect_process_socket_counters()
        source_speed = {}
        for row in current.values():
            source = str((row or {}).get("source", "") or "").strip()
            if not source:
                continue
            agg = source_speed.setdefault(
                source,
                {
                    "source": source,
                    "count": 0,
                    "conn_count": 0,
                    "active_count": 0,
                    "download_mibps": 0.0,
                    "upload_mibps": 0.0,
                },
            )
            if str((row or {}).get("state", "") or "").upper() == "ESTAB":
                agg["conn_count"] = int(agg.get("conn_count", 0)) + 1

        with self._lock:
            last_ts = float(self._state.get("last_ts", 0.0) or 0.0)
            last = self._state.get("socket_counters") or {}
            self._state["last_ts"] = now
            self._state["socket_counters"] = current

        if not current or last_ts <= 0 or now <= last_ts:
            return source_speed
        delta_sec = now - last_ts
        if delta_sec <= 0:
            return source_speed

        for socket_key, row in current.items():
            if str((row or {}).get("state", "") or "").upper() != "ESTAB":
                continue
            prev = last.get(socket_key) if isinstance(last, dict) else None
            if not isinstance(prev, dict):
                continue
            acked_now = int(row.get("acked", 0) or 0)
            recv_now = int(row.get("received", 0) or 0)
            acked_prev = int(prev.get("acked", 0) or 0)
            recv_prev = int(prev.get("received", 0) or 0)
            delta_send = max(acked_now - acked_prev, 0)
            delta_recv = max(recv_now - recv_prev, 0)
            if delta_send <= 0 and delta_recv <= 0:
                continue
            source = str(row.get("source", "") or "").strip()
            if not source:
                continue
            agg = source_speed[source]
            # Download = process received bytes; upload = process acknowledged bytes.
            agg["download_mibps"] = float(agg.get("download_mibps", 0.0)) + (
                delta_recv / 1024.0 / 1024.0 / delta_sec
            )
            agg["upload_mibps"] = float(agg.get("upload_mibps", 0.0)) + (
                delta_send / 1024.0 / 1024.0 / delta_sec
            )
            agg["active_count"] = int(agg.get("active_count", 0)) + 1
        for agg in source_speed.values():
            agg["count"] = int(agg.get("active_count", 0) or 0)
        return source_speed

    def detailed_snapshot(self) -> dict:
        now = time.time()
        current = self._collect_process_socket_counters()
        with self._lock:
            last_ts = float(self._state.get("last_ts", 0.0) or 0.0)
            last = self._state.get("socket_counters") or {}
            self._state["last_ts"] = now
            self._state["socket_counters"] = current
        delta_sec = (now - last_ts) if (last_ts > 0 and now > last_ts) else 0.0

        source_agg = {}
        items = []
        for row in current.values():
            source = str((row or {}).get("source", "") or "").strip()
            if not source:
                continue
            state = str((row or {}).get("state", "") or "").strip().upper()
            local_ep = str((row or {}).get("local_ep", "") or "")
            peer_ep = str((row or {}).get("peer_ep", "") or "")
            pid = int((row or {}).get("pid", 0) or 0)
            process_name = str((row or {}).get("process", "") or "")
            acked_now = int((row or {}).get("acked", 0) or 0)
            recv_now = int((row or {}).get("received", 0) or 0)

            delta_send = 0
            delta_recv = 0
            if delta_sec > 0:
                socket_key = f"{source}|{pid}|{local_ep}|{peer_ep}"
                prev = last.get(socket_key) if isinstance(last, dict) else None
                if isinstance(prev, dict):
                    acked_prev = int(prev.get("acked", 0) or 0)
                    recv_prev = int(prev.get("received", 0) or 0)
                    delta_send = max(acked_now - acked_prev, 0)
                    delta_recv = max(recv_now - recv_prev, 0)

            download_mibps = (
                (delta_recv / 1024.0 / 1024.0 / delta_sec) if delta_sec > 0 else 0.0
            )
            upload_mibps = (
                (delta_send / 1024.0 / 1024.0 / delta_sec) if delta_sec > 0 else 0.0
            )
            items.append(
                {
                    "source": source,
                    "pid": pid,
                    "process": process_name,
                    "state": state,
                    "local_ep": local_ep,
                    "peer_ep": peer_ep,
                    "acked": acked_now,
                    "received": recv_now,
                    "delta_sent_bytes": int(delta_send),
                    "delta_received_bytes": int(delta_recv),
                    "download_mibps": float(download_mibps),
                    "upload_mibps": float(upload_mibps),
                }
            )
            agg = source_agg.setdefault(
                source,
                {
                    "source": source,
                    "conn_count": 0,
                    "estab_count": 0,
                    "download_mibps": 0.0,
                    "upload_mibps": 0.0,
                },
            )
            agg["conn_count"] = int(agg.get("conn_count", 0)) + 1
            if state == "ESTAB":
                agg["estab_count"] = int(agg.get("estab_count", 0)) + 1
            agg["download_mibps"] = float(agg.get("download_mibps", 0.0)) + float(
                download_mibps
            )
            agg["upload_mibps"] = float(agg.get("upload_mibps", 0.0)) + float(
                upload_mibps
            )

        source_stats = list(source_agg.values())
        source_stats.sort(
            key=lambda x: (
                -float(x.get("download_mibps", 0.0)),
                -float(x.get("upload_mibps", 0.0)),
                str(x.get("source", "")),
            )
        )
        items.sort(
            key=lambda x: (
                -float(x.get("download_mibps", 0.0)),
                -float(x.get("upload_mibps", 0.0)),
                str(x.get("source", "")),
                int(x.get("pid", 0)),
            )
        )
        return {
            "sample_ts": float(now),
            "delta_sec": float(delta_sec),
            "count": len(items),
            "source_stats": source_stats,
            "items": items,
        }
