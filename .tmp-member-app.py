from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import json, os, sqlite3, time, uuid
import requests

DB_PATH = os.environ.get("MEMBER_DB_PATH", "/opt/afterclaw-member/member.db")
KOFI_VERIFICATION_TOKEN = os.environ.get("KOFI_VERIFICATION_TOKEN", "")
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "").strip()
MAIL_FROM = os.environ.get("MAIL_FROM", "AfterClaw <no-reply@mail.afterclaw.xyz>").strip()
MEMBER_PORTAL_URL = os.environ.get("MEMBER_PORTAL_URL", "https://ddns.afterclaw.xyz").strip()

app = FastAPI(title="AfterClaw Member API")


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()
    conn.execute("""
    CREATE TABLE IF NOT EXISTS kofi_events(
      id TEXT PRIMARY KEY,
      received_at INTEGER NOT NULL,
      verification_token TEXT,
      event_type TEXT,
      email TEXT,
      payload_json TEXT NOT NULL
    )
    """)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS mail_log(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      created_at INTEGER NOT NULL,
      event_id TEXT,
      email TEXT,
      ok INTEGER NOT NULL,
      detail TEXT
    )
    """)
    conn.commit()
    conn.close()


def _send_activation_email(email: str, event_id: str, event_type: str) -> tuple[bool, str]:
    if not email:
        return False, "missing_email"
    if not RESEND_API_KEY:
        return False, "resend_key_not_set"
    subject = "AfterClaw Member Access"
    html = (
        f"<p>Hi,</p>"
        f"<p>We received your Ko-fi support ({event_type}).</p>"
        f"<p>Please open <a href=\"{MEMBER_PORTAL_URL}\">{MEMBER_PORTAL_URL}</a> and click Member to verify your account.</p>"
        f"<p>If this is your first time, we will issue your member credentials after verification.</p>"
        f"<p>Reference: <code>{event_id}</code></p>"
    )
    payload = {
        "from": MAIL_FROM,
        "to": [email],
        "subject": subject,
        "html": html,
    }
    try:
        r = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=20,
        )
        if not r.ok:
            return False, f"resend_http_{r.status_code}:{r.text[:300]}"
        data = r.json() if r.content else {}
        return True, str(data.get("id") or "sent")
    except Exception as e:
        return False, f"send_error:{e}"


def _log_mail(event_id: str, email: str, ok: bool, detail: str) -> None:
    conn = db()
    conn.execute(
        "INSERT INTO mail_log(created_at, event_id, email, ok, detail) VALUES(?,?,?,?,?)",
        (int(time.time()), event_id, email, 1 if ok else 0, str(detail or "")),
    )
    conn.commit()
    conn.close()


@app.on_event("startup")
def _startup():
    init_db()


@app.get("/healthz")
def healthz():
    return {"ok": True, "service": "afterclaw-member", "ts": int(time.time())}


@app.post("/webhooks/kofi")
async def kofi_webhook(request: Request):
    raw = await request.body()
    ctype = (request.headers.get("content-type") or "").lower()

    data = None
    if "application/json" in ctype:
        data = json.loads(raw.decode("utf-8") or "{}")
    else:
        form = await request.form()
        payload = form.get("data")
        if payload is None:
            payload = form.get("payload")
        if payload:
            data = json.loads(str(payload))
        else:
            try:
                data = json.loads(raw.decode("utf-8") or "{}")
            except Exception:
                data = {}

    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="invalid payload")

    token = str(data.get("verification_token") or "").strip()
    if KOFI_VERIFICATION_TOKEN and token != KOFI_VERIFICATION_TOKEN:
        raise HTTPException(status_code=401, detail="invalid verification token")

    event_id = str(data.get("message_id") or data.get("kofi_transaction_id") or uuid.uuid4())
    event_type = str(data.get("type") or data.get("event") or "unknown")
    email = str(data.get("email") or data.get("from_email") or "").strip().lower()

    conn = db()
    conn.execute(
        "INSERT OR REPLACE INTO kofi_events(id, received_at, verification_token, event_type, email, payload_json) VALUES(?,?,?,?,?,?)",
        (event_id, int(time.time()), token, event_type, email, json.dumps(data, ensure_ascii=False)),
    )
    conn.commit()
    conn.close()

    mail_ok, mail_detail = _send_activation_email(email, event_id, event_type)
    _log_mail(event_id, email, mail_ok, mail_detail)
    return JSONResponse(
        {
            "ok": True,
            "saved": True,
            "event_id": event_id,
            "event_type": event_type,
            "email": email,
            "mail_sent": mail_ok,
            "mail_detail": mail_detail,
        }
    )


@app.get("/api/kofi/events/latest")
def latest_events(limit: int = 20):
    limit = max(1, min(int(limit), 100))
    conn = db()
    rows = conn.execute(
        "SELECT id, received_at, verification_token, event_type, email FROM kofi_events ORDER BY received_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return {"ok": True, "items": [dict(r) for r in rows]}


@app.get("/api/mail/latest")
def latest_mails(limit: int = 20):
    limit = max(1, min(int(limit), 100))
    conn = db()
    rows = conn.execute(
        "SELECT id, created_at, event_id, email, ok, detail FROM mail_log ORDER BY id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return {"ok": True, "items": [dict(r) for r in rows]}
