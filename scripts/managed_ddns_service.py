#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import ipaddress
import json
import secrets
import sqlite3
import sys
import time
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from ddns.domain_split import split_fqdn
from ddns.volc import traffic_api


def now_ts() -> int:
    return int(time.time())


def ensure_db(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tokens (
          token TEXT PRIMARY KEY,
          donor_id TEXT NOT NULL,
          fqdn TEXT NOT NULL,
          enabled INTEGER NOT NULL DEFAULT 1,
          min_interval_sec INTEGER NOT NULL DEFAULT 60,
          created_at INTEGER NOT NULL,
          expires_at INTEGER,
          last_update_at INTEGER
        )
        """
    )
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(tokens)").fetchall()}
    if "status" not in cols:
        conn.execute("ALTER TABLE tokens ADD COLUMN status TEXT NOT NULL DEFAULT 'active'")
    if "last_payment_at" not in cols:
        conn.execute("ALTER TABLE tokens ADD COLUMN last_payment_at INTEGER")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS update_logs (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          token TEXT NOT NULL,
          fqdn TEXT NOT NULL,
          ipv4 TEXT,
          ipv6 TEXT,
          ok INTEGER NOT NULL,
          message TEXT NOT NULL,
          created_at INTEGER NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS webhook_events (
          message_id TEXT PRIMARY KEY,
          donor_id TEXT,
          event_type TEXT,
          raw_json TEXT NOT NULL,
          processed_at INTEGER NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def issue_token(conn: sqlite3.Connection, donor_id: str, fqdn: str, days: int | None, min_interval_sec: int) -> str:
    token = secrets.token_urlsafe(24)
    created = now_ts()
    expires = created + days * 86400 if days else None
    conn.execute(
        """
        INSERT INTO tokens (token, donor_id, fqdn, enabled, min_interval_sec, created_at, expires_at)
        VALUES (?, ?, ?, 1, ?, ?, ?)
        """,
        (token, donor_id.strip(), fqdn.strip().lower(), int(min_interval_sec), created, expires),
    )
    conn.commit()
    return token


def revoke_token(conn: sqlite3.Connection, token: str) -> bool:
    cur = conn.execute("UPDATE tokens SET enabled=0 WHERE token=?", (token.strip(),))
    conn.commit()
    return cur.rowcount > 0


def get_token(conn: sqlite3.Connection, token: str) -> sqlite3.Row | None:
    cur = conn.execute("SELECT * FROM tokens WHERE token=?", (token.strip(),))
    row = cur.fetchone()
    return row


def is_valid_ip(value: str, family: str) -> bool:
    try:
        ip = ipaddress.ip_address(value.strip())
    except ValueError:
        return False
    if family == "v4":
        return isinstance(ip, ipaddress.IPv4Address)
    return isinstance(ip, ipaddress.IPv6Address)


def update_dns(ak: str, sk: str, fqdn: str, ipv4: str | None, ipv6: str | None, ttl: int = 600) -> str:
    parsed = split_fqdn(fqdn)
    if not parsed:
        raise ValueError(f"Invalid FQDN: {fqdn}")
    sub, zone = parsed
    host = sub if sub else "@"
    zid = traffic_api.get_zone_id(ak, sk, zone)
    parts: list[str] = []
    if ipv4:
        recs = traffic_api.list_records(ak, sk, zid, "A", host)
        rec = recs[0] if recs else None
        if rec is None:
            traffic_api.create_record(ak, sk, zid, host, "A", ipv4, ttl)
        elif str(rec.get("Value", "")).strip() != ipv4:
            traffic_api.update_record(ak, sk, {**rec, "ZID": int(zid)}, ipv4, ttl)
        parts.append(f"A={ipv4}")
    if ipv6:
        recs6 = traffic_api.list_records(ak, sk, zid, "AAAA", host)
        rec6 = recs6[0] if recs6 else None
        if rec6 is None:
            traffic_api.create_record(ak, sk, zid, host, "AAAA", ipv6, ttl)
        elif str(rec6.get("Value", "")).strip() != ipv6:
            traffic_api.update_record(ak, sk, {**rec6, "ZID": int(zid)}, ipv6, ttl)
        parts.append(f"AAAA={ipv6}")
    if not parts:
        raise ValueError("No valid IP input")
    return " ".join(parts)


@dataclass
class ServerConfig:
    ak: str
    sk: str
    external_base_url: str
    ttl: int
    kofi_verification_token: str
    billing_days: int
    grace_days: int


class ManagedDDNSHandler(BaseHTTPRequestHandler):
    server_version = "AfterClawManagedDDNS/0.1"

    def _conn(self) -> sqlite3.Connection:
        return self.server.db  # type: ignore[attr-defined]

    def _cfg(self) -> ServerConfig:
        return self.server.cfg  # type: ignore[attr-defined]

    def _json(self, status: int, payload: dict[str, Any]) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _html(self, status: int, html_body: str) -> None:
        data = html_body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _parse_body_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or "0")
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {}

    def _raw_body(self) -> bytes:
        length = int(self.headers.get("Content-Length") or "0")
        if length <= 0:
            return b""
        return self.rfile.read(length)

    def _parse_kofi_payload(self, raw: bytes) -> dict[str, Any]:
        ctype = (self.headers.get("Content-Type") or "").lower()
        text = raw.decode("utf-8", errors="replace")
        if "application/json" in ctype:
            try:
                obj = json.loads(text)
                return obj if isinstance(obj, dict) else {}
            except Exception:
                return {}
        form = parse_qs(text, keep_blank_values=True)
        if "data" in form and form["data"]:
            try:
                obj = json.loads(form["data"][0])
                return obj if isinstance(obj, dict) else {}
            except Exception:
                return {}
        return {}

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self._json(200, {"ok": True, "service": "managed-ddns"})
            return
        if parsed.path == "/setup":
            self._html(200, self._setup_page())
            return
        if parsed.path.startswith("/u/"):
            token = parsed.path.split("/u/", 1)[1].strip("/")
            self._serve_user_page(token)
            return
        self._json(404, {"ok": False, "error": "not_found"})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/v1/ddns/update":
            self._handle_update()
            return
        if parsed.path == "/v1/kofi/webhook":
            self._handle_kofi_webhook()
            return
        self._json(404, {"ok": False, "error": "not_found"})

    def _setup_page(self) -> str:
        return """
<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>AfterClaw DDNS Setup</title><style>body{font-family:system-ui,sans-serif;max-width:720px;margin:40px auto;padding:0 16px}input,button{padding:10px;font-size:14px}input{width:100%;box-sizing:border-box}button{margin-top:10px}</style></head>
<body><h1>AfterClaw DDNS Setup</h1><p>Paste your donor token to open your setup page.</p>
<input id='tok' placeholder='Paste token'><button onclick='go()'>Open Setup</button>
<script>function go(){var t=document.getElementById("tok").value.trim();if(!t){return;}location.href="/u/"+encodeURIComponent(t);}</script></body></html>
"""

    def _serve_user_page(self, token: str) -> None:
        row = get_token(self._conn(), token)
        if not row:
            self._html(404, "<h1>Token not found</h1>")
            return
        if not int(row["enabled"]):
            self._html(403, "<h1>Token revoked</h1>")
            return
        fqdn = html.escape(str(row["fqdn"]))
        base = self._cfg().external_base_url.rstrip("/")
        update_url = f"{base}/v1/ddns/update?token={token}&ipv4={{ip}}"
        body = f"""
<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>AfterClaw DDNS Setup</title><style>body{{font-family:system-ui,sans-serif;max-width:900px;margin:40px auto;padding:0 16px;line-height:1.45}}code,pre{{background:#f5f5f5;padding:3px 6px;border-radius:4px}}pre{{padding:12px;overflow:auto}}</style></head>
<body><h1>AfterClaw Donor DDNS</h1>
<p><strong>Domain:</strong> <code>{fqdn}</code></p>
<p><strong>Token status:</strong> active</p>
<h2>AfterClaw quick config (IPv4)</h2>
<p>In DDNS provider, choose <code>HTTP GET template</code> and use:</p>
<pre>{html.escape(update_url)}</pre>
<p>Template requirement is <code>{{ip}}</code> for current IP.</p>
<h2>Manual test</h2>
<pre>curl '{base}/v1/ddns/update?token={token}&ipv4=1.2.3.4'</pre>
</body></html>
"""
        self._html(200, body)

    def _handle_update(self) -> None:
        parsed = urlparse(self.path)
        q = parse_qs(parsed.query)
        body = self._parse_body_json()
        token = (q.get("token", [None])[0] or body.get("token") or "").strip()
        if not token:
            self._json(400, {"ok": False, "error": "missing_token"})
            return
        row = get_token(self._conn(), token)
        if not row:
            self._json(403, {"ok": False, "error": "invalid_token"})
            return
        if not int(row["enabled"]):
            self._json(403, {"ok": False, "error": "token_revoked"})
            return
        if str(row["status"] or "active") != "active":
            self._json(403, {"ok": False, "error": "token_not_active"})
            return
        expires_at = row["expires_at"]
        if expires_at and now_ts() > int(expires_at):
            self._json(403, {"ok": False, "error": "token_expired"})
            return

        last = row["last_update_at"]
        min_interval = int(row["min_interval_sec"] or 60)
        now = now_ts()
        if last and now - int(last) < min_interval:
            wait_sec = min_interval - (now - int(last))
            self._json(429, {"ok": False, "error": "rate_limited", "retry_after_sec": wait_sec})
            return

        ipv4 = (q.get("ipv4", [None])[0] or body.get("ipv4") or "").strip()
        ipv6 = (q.get("ipv6", [None])[0] or body.get("ipv6") or "").strip()
        if ipv4 and not is_valid_ip(ipv4, "v4"):
            self._json(400, {"ok": False, "error": "invalid_ipv4"})
            return
        if ipv6 and not is_valid_ip(ipv6, "v6"):
            self._json(400, {"ok": False, "error": "invalid_ipv6"})
            return
        if not ipv4 and not ipv6:
            self._json(400, {"ok": False, "error": "missing_ip"})
            return

        try:
            msg = update_dns(self._cfg().ak, self._cfg().sk, str(row["fqdn"]), ipv4 or None, ipv6 or None, self._cfg().ttl)
            self._conn().execute("UPDATE tokens SET last_update_at=? WHERE token=?", (now, token))
            self._conn().execute(
                "INSERT INTO update_logs(token,fqdn,ipv4,ipv6,ok,message,created_at) VALUES(?,?,?,?,?,?,?)",
                (token, str(row["fqdn"]), ipv4 or None, ipv6 or None, 1, msg, now),
            )
            self._conn().commit()
            self._json(200, {"ok": True, "fqdn": str(row["fqdn"]), "message": msg})
        except Exception as exc:
            err = str(exc)
            self._conn().execute(
                "INSERT INTO update_logs(token,fqdn,ipv4,ipv6,ok,message,created_at) VALUES(?,?,?,?,?,?,?)",
                (token, str(row["fqdn"]), ipv4 or None, ipv6 or None, 0, err, now),
            )
            self._conn().commit()
            self._json(500, {"ok": False, "error": "dns_update_failed", "detail": err})

    def _kofi_donor_id(self, payload: dict[str, Any]) -> str:
        email = str(payload.get("email") or "").strip().lower()
        if email:
            return email
        sender = str(payload.get("from_name") or payload.get("sender_name") or "").strip()
        if sender:
            return sender.lower()
        return ""

    def _kofi_message_id(self, payload: dict[str, Any]) -> str:
        for key in ("message_id", "kofi_transaction_id", "transaction_id"):
            value = str(payload.get(key) or "").strip()
            if value:
                return value
        return ""

    def _is_payment_event(self, payload: dict[str, Any]) -> bool:
        ptype = str(payload.get("type") or "").strip().lower()
        if ptype in {"donation", "subscription", "shop_order", "commission"}:
            return True
        return bool(payload.get("amount"))

    def _handle_kofi_webhook(self) -> None:
        raw = self._raw_body()
        payload = self._parse_kofi_payload(raw)
        if not payload:
            self._json(400, {"ok": False, "error": "invalid_payload"})
            return
        expected = self._cfg().kofi_verification_token.strip()
        got = str(payload.get("verification_token") or "").strip()
        if not expected or got != expected:
            self._json(403, {"ok": False, "error": "bad_verification_token"})
            return

        message_id = self._kofi_message_id(payload)
        donor_id = self._kofi_donor_id(payload)
        event_type = str(payload.get("type") or "").strip().lower()
        if not message_id:
            self._json(400, {"ok": False, "error": "missing_message_id"})
            return
        if not donor_id:
            self._json(400, {"ok": False, "error": "missing_donor_id"})
            return
        conn = self._conn()
        exists = conn.execute("SELECT 1 FROM webhook_events WHERE message_id=?", (message_id,)).fetchone()
        if exists:
            self._json(200, {"ok": True, "duplicate": True, "message_id": message_id})
            return

        affected = 0
        now = now_ts()
        if self._is_payment_event(payload):
            rows = conn.execute(
                "SELECT token, expires_at FROM tokens WHERE donor_id=?",
                (donor_id,),
            ).fetchall()
            delta = self._cfg().billing_days * 86400
            grace = self._cfg().grace_days * 86400
            for r in rows:
                current_exp = int(r["expires_at"] or 0)
                base = max(now, current_exp - grace) if current_exp > 0 else now
                next_exp = base + delta + grace
                conn.execute(
                    "UPDATE tokens SET enabled=1,status='active',expires_at=?,last_payment_at=? WHERE token=?",
                    (next_exp, now, str(r["token"])),
                )
                affected += 1

        conn.execute(
            "INSERT INTO webhook_events(message_id, donor_id, event_type, raw_json, processed_at) VALUES (?,?,?,?,?)",
            (message_id, donor_id, event_type, json.dumps(payload, ensure_ascii=False), now),
        )
        conn.commit()
        self._json(
            200,
            {
                "ok": True,
                "message_id": message_id,
                "donor_id": donor_id,
                "affected_tokens": affected,
            },
        )


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="AfterClaw managed DDNS token service")
    p.add_argument("--db", default="data/managed_ddns.sqlite3")
    sub = p.add_subparsers(dest="cmd", required=True)

    serve = sub.add_parser("serve", help="Run HTTP API server")
    serve.add_argument("--host", default="0.0.0.0")
    serve.add_argument("--port", type=int, default=8098)
    serve.add_argument("--ak", required=True, help="Volcengine AccessKeyId")
    serve.add_argument("--sk", required=True, help="Volcengine SecretAccessKey")
    serve.add_argument("--external-base-url", required=True, help="Public URL, e.g. https://ddns.afterclaw.xyz")
    serve.add_argument("--ttl", type=int, default=600)
    serve.add_argument("--kofi-verification-token", required=True, help="Ko-fi webhook verification token")
    serve.add_argument("--billing-days", type=int, default=30, help="Paid period days per valid payment")
    serve.add_argument("--grace-days", type=int, default=7, help="Grace period days after paid period")

    issue = sub.add_parser("issue", help="Issue token for donor")
    issue.add_argument("--donor-id", required=True)
    issue.add_argument("--fqdn", required=True, help="e.g. alice.afterclaw.xyz")
    issue.add_argument("--days", type=int, default=30)
    issue.add_argument("--min-interval-sec", type=int, default=60)

    revoke = sub.add_parser("revoke", help="Revoke token")
    revoke.add_argument("--token", required=True)

    ls_cmd = sub.add_parser("list", help="List tokens")
    ls_cmd.add_argument("--all", action="store_true")
    sub.add_parser("expire-scan", help="Disable expired tokens")
    return p.parse_args()


def cmd_issue(conn: sqlite3.Connection, args: argparse.Namespace) -> int:
    token = issue_token(conn, args.donor_id, args.fqdn, args.days, args.min_interval_sec)
    print(json.dumps({"ok": True, "token": token, "fqdn": args.fqdn, "donor_id": args.donor_id}, ensure_ascii=False))
    return 0


def cmd_revoke(conn: sqlite3.Connection, args: argparse.Namespace) -> int:
    ok = revoke_token(conn, args.token)
    print(json.dumps({"ok": ok, "token": args.token}, ensure_ascii=False))
    return 0 if ok else 1


def cmd_list(conn: sqlite3.Connection, args: argparse.Namespace) -> int:
    if args.all:
        rows = conn.execute(
            "SELECT token, donor_id, fqdn, enabled, created_at, expires_at, last_update_at FROM tokens ORDER BY created_at DESC"
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT token, donor_id, fqdn, enabled, status, created_at, expires_at, last_update_at FROM tokens WHERE enabled=1 ORDER BY created_at DESC"
        ).fetchall()
    out = [dict(r) for r in rows]
    print(json.dumps({"ok": True, "items": out}, ensure_ascii=False))
    return 0


def cmd_expire_scan(conn: sqlite3.Connection) -> int:
    now = now_ts()
    cur = conn.execute(
        "UPDATE tokens SET enabled=0,status='expired' WHERE enabled=1 AND expires_at IS NOT NULL AND expires_at>0 AND expires_at<?",
        (now,),
    )
    conn.commit()
    print(json.dumps({"ok": True, "expired_count": int(cur.rowcount)}, ensure_ascii=False))
    return 0


def cmd_serve(conn: sqlite3.Connection, args: argparse.Namespace) -> int:
    cfg = ServerConfig(
        ak=args.ak.strip(),
        sk=args.sk.strip(),
        external_base_url=args.external_base_url.strip().rstrip("/"),
        ttl=int(args.ttl),
        kofi_verification_token=args.kofi_verification_token.strip(),
        billing_days=int(args.billing_days),
        grace_days=int(args.grace_days),
    )
    httpd = ThreadingHTTPServer((args.host, args.port), ManagedDDNSHandler)
    httpd.db = conn  # type: ignore[attr-defined]
    httpd.cfg = cfg  # type: ignore[attr-defined]
    print(f"managed-ddns listening on http://{args.host}:{args.port}")
    httpd.serve_forever()
    return 0


def main() -> int:
    args = parse_args()
    db = Path(args.db).expanduser().resolve()
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = ensure_db(db)
    if args.cmd == "issue":
        return cmd_issue(conn, args)
    if args.cmd == "revoke":
        return cmd_revoke(conn, args)
    if args.cmd == "list":
        return cmd_list(conn, args)
    if args.cmd == "expire-scan":
        return cmd_expire_scan(conn)
    return cmd_serve(conn, args)


if __name__ == "__main__":
    raise SystemExit(main())
