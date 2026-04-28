from __future__ import annotations

import json
import mimetypes
import os
import re
import threading
import uuid
from datetime import datetime
from pathlib import Path

from flask import Flask, Response, jsonify, request, send_from_directory

app = Flask(__name__)

APP_NAME = "ShareClip"
AUTHOR_NAME = "RandyPKU"
AUTHOR_EMAIL = "mengke@pku.org.cn"
REPO_URL = "https://github.com/EinProfispieler/shareclip"
LICENSE_NAME = "Apache License 2.0"

BASE_DIR = Path(__file__).resolve().parent
LEGACY_STORAGE_ROOT = Path("/storage").resolve()
STORAGE_ROOT = Path(os.getenv("SHARECLIP_STORAGE_ROOT", str(BASE_DIR / "storage"))).expanduser().resolve()
CONFIG_FILE = STORAGE_ROOT / "config.json"

DEFAULT_PORT = 8888
DEFAULT_ID = "pub"
MAX_HISTORY = 200
ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

LOCK = threading.Lock()
runtime_config: dict[str, object] = {"port": DEFAULT_PORT, "default_id": DEFAULT_ID}
runtime_port = DEFAULT_PORT

INDEX_HTML = """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ShareClip</title><style>
body{margin:0;padding:clamp(14px,2.5vw,22px);min-height:100vh;background:linear-gradient(165deg,#dce4f2 0%,#e8ecf4 38%,#eef1f8 100%);background-attachment:fixed;color:#1c2333;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC",sans-serif;font-size:15px;line-height:1.45}
.g{width:min(calc(100vw - clamp(24px,5vw,56px)),1680px);max-width:calc(100vw - clamp(24px,5vw,56px));margin:0 auto;display:grid;gap:14px;grid-template-columns:repeat(auto-fit,minmax(min(100%,300px),1fr))}
.c{background:#fff;border:1px solid rgba(28,35,51,.12);border-radius:14px;padding:16px 18px;box-shadow:0 4px 24px rgba(15,23,42,.08)}
h1,h2{margin:0 0 10px;font-weight:750;color:#1c2333}.r{display:flex;gap:8px;flex-wrap:wrap;margin:8px 0}p,label{color:#5c6578;margin:6px 0;font-size:14px}
input,textarea{width:100%;padding:10px 12px;border:1px solid rgba(28,35,51,.12);border-radius:10px;background:#f8fafc;color:#1c2333;font-size:15px}
textarea{min-height:110px;resize:vertical}.paste{min-height:74px;border:1.5px dashed rgba(37,99,235,.35);border-radius:12px;display:flex;align-items:center;justify-content:center;text-align:center;color:#5c6578;background:#f1f5f9;cursor:pointer}
button{border:0;border-radius:10px;padding:9px 14px;background:#2563eb;color:#fff;cursor:pointer;font-weight:600;font-size:14px}
button:hover{filter:brightness(.95)}button.s{background:#f1f5f9;color:#475569;border:1px solid rgba(28,35,51,.12)}button.d{background:linear-gradient(135deg,#dc2626,#b91c1c);color:#fff;border:0}
.panel{min-height:100px;background:#f8fafc;border:1px solid rgba(28,35,51,.12);border-radius:10px;padding:12px;overflow:auto;color:#1c2333}
.hist{max-height:450px;overflow:auto;display:grid;gap:8px}.item{padding:10px;border:1px solid rgba(28,35,51,.12);border-radius:10px;background:#fff}
.meta{font-size:12px;color:#5c6578;word-break:break-all}.t{font-size:13px;white-space:pre-wrap;word-break:break-word;background:#fff;border:1px solid rgba(28,35,51,.12);border-radius:8px;padding:8px;max-height:86px;overflow:auto;color:#1c2333}
img{max-width:100%;max-height:280px;border:1px solid rgba(28,35,51,.12);border-radius:10px;background:#fff}
#status{font-size:13px;min-height:18px}#status.ok{color:#059669}#status.warn{color:#d97706}
code{background:#eef2ff;border-radius:6px;padding:2px 8px;color:#1e40af;font-size:13px}a{color:#2563eb;text-decoration:none}a:hover{text-decoration:underline}
.f{width:min(calc(100vw - clamp(24px,5vw,56px)),1680px);max-width:calc(100vw - clamp(24px,5vw,56px));margin:16px auto 0;color:#5c6578;font-size:12px;text-align:center;padding-bottom:8px}
</style></head><body>
<div class="g">
<section class="c"><h1>ShareClip</h1><p>Per-ID temporary clip sharing in LAN.</p><div class="r"><a href="/config">Config</a></div>
<label>ID</label><input id="idInput" placeholder="Example: Randy or team_alpha"><div class="r"><button id="switchBtn">Switch ID</button></div>
<p>Current ID: <code id="curId">-</code></p>
<h2>Publish</h2><label>Text</label><textarea id="txt"></textarea><div id="paste" class="paste" tabindex="0">Click then Ctrl+V (image/text)</div>
<label>Image</label><input id="img" type="file" accept="image/*"><div class="r"><button id="send">Send</button><button id="read" class="s">Read Clipboard</button></div><div id="status"></div></section>
<section class="c"><h2>Latest</h2><div class="r"><button id="rf">Refresh</button><a id="raw" target="_blank" rel="noopener">Raw</a></div><p id="lmeta">No content</p><div id="lview" class="panel">No content</div></section>
<section class="c"><h2>History</h2><div class="r"><button id="rh">Refresh History</button></div><p id="hmeta">Loading...</p><div id="hlist" class="hist"></div></section>
</div>
<div class="f">Author: <a href="mailto:mengke@pku.org.cn">RandyPKU</a> | License: Apache License 2.0 | <a href="https://github.com/EinProfispieler/shareclip" target="_blank" rel="noopener">GitHub</a></div>
<script>
const idRe=/^[A-Za-z0-9_-]{1,64}$/;const $=id=>document.getElementById(id);let curId="",clipImg=null;
const S=(m,l="ok")=>{$("status").textContent=m;$("status").className=l};
const U=(p)=>{const u=new URL(p,location.origin);if(curId)u.searchParams.set("id",curId);return u.toString()};
function setId(id){if(!idRe.test(id||""))throw new Error("ID must be 1-64 chars: letters/numbers/_/-");curId=id;$("curId").textContent=id;$("idInput").value=id;$("raw").href=U("/api/clip/raw");localStorage.setItem("shareclip_id",id);const u=new URL(location.href);u.searchParams.set("id",id);history.replaceState({}, "", u.toString())}
function show(c){if(!c||c.type==="empty"){$("lmeta").textContent="No content";$("lview").textContent="No content";return}const t=c.updated_at||"unknown";if(c.type==="text"){$("lmeta").textContent=`text | ${t} | ${c.id||""}`;$("lview").innerHTML="<pre></pre>";$("lview").querySelector("pre").textContent=c.text||"";return}$("lmeta").textContent=`image(${c.image_filename||"unknown"}) | ${t} | ${c.id||""}`;$("lview").innerHTML="";const im=document.createElement("img");im.src=(c.image_url||"")+"?t="+Date.now();$("lview").appendChild(im)}
async function rf(){const r=await fetch(U("/api/clip"));if(!r.ok)throw new Error("refresh latest failed");const d=await r.json();show(d.clip)}
async function rh(){const r=await fetch(U("/api/history?limit=200"));if(!r.ok)throw new Error("refresh history failed");const d=await r.json();const items=d.items||[];$("hmeta").textContent=`total ${items.length}`;$("hlist").innerHTML="";if(!items.length){$("hlist").textContent="No history";return}for(const it of items){const e=document.createElement("div");e.className="item";const m=document.createElement("div");m.className="meta";m.textContent=`${it.type||"unknown"} | ${it.updated_at||""} | ${it.id||""}`;e.appendChild(m);if(it.type==="text"){const t=document.createElement("div");t.className="t";t.textContent=it.text||"";e.appendChild(t)}else if(it.image_url){const im=document.createElement("img");im.src=it.image_url+"?t="+Date.now();e.appendChild(im)}const row=document.createElement("div");row.className="r";const v=document.createElement("button");v.className="s";v.textContent="View";v.onclick=()=>show(it);const del=document.createElement("button");del.className="d";del.textContent="Delete";del.onclick=async()=>{if(!it.id)return;if(!confirm("Delete this record?"))return;const rr=await fetch(U("/api/history/"+encodeURIComponent(it.id)),{method:"DELETE"});if(!rr.ok){const er=await rr.json().catch(()=>({}));throw new Error(er.error||"delete failed")}S("Deleted");await Promise.all([rf(),rh()])};row.appendChild(v);row.appendChild(del);e.appendChild(row);$("hlist").appendChild(e)}}
async function send(){const fd=new FormData();fd.append("id",curId);const f=$("img").files?.[0]||clipImg,t=($("txt").value||"").trim();if(f)fd.append("image",f,f.name||"clip.png");else if(t)fd.append("text",t);else throw new Error("Paste text or image first");const r=await fetch("/api/clip",{method:"POST",body:fd});const d=await r.json().catch(()=>({}));if(!r.ok)throw new Error(d.error||"upload failed");clipImg=null;$("img").value="";$("txt").value="";S("Sent");show(d.clip);await rh()}
async function onPaste(cd){const items=Array.from((cd&&cd.items)||[]);const im=items.find(x=>x.type&&x.type.startsWith("image/"));if(im){const b=im.getAsFile();if(b){const ext=(b.type.split("/")[1]||"png").replace("jpeg","jpg");clipImg=new File([b],`clipboard-${Date.now()}.${ext}`,{type:b.type});$("img").value="";S("Image captured");return}}const tx=items.find(x=>x.kind==="string"&&x.type==="text/plain");if(tx){tx.getAsString(v=>{$("txt").value=v||"";clipImg=null;S("Text captured")})}}
$("switchBtn").onclick=async()=>{try{setId(($("idInput").value||"").trim());S("ID switched");await Promise.all([rf(),rh()])}catch(e){S(e.message||String(e),"warn")}};
$("rf").onclick=()=>rf().catch(e=>S(e.message||String(e),"warn"));$("rh").onclick=()=>rh().catch(e=>S(e.message||String(e),"warn"));
$("send").onclick=()=>send().catch(e=>S(e.message||String(e),"warn"));
$("paste").addEventListener("paste",e=>{e.preventDefault();onPaste(e.clipboardData).catch(er=>S(er.message||String(er),"warn"))});$("txt").addEventListener("paste",e=>onPaste(e.clipboardData).catch(er=>S(er.message||String(er),"warn")));
$("read").onclick=async()=>{if(!navigator.clipboard||!navigator.clipboard.read){S("Browser clipboard API not supported","warn");return}try{const items=await navigator.clipboard.read();for(const it of items){const t=it.types.find(x=>x.startsWith("image/"));if(t){const b=await it.getType(t);const ext=(t.split("/")[1]||"png").replace("jpeg","jpg");clipImg=new File([b],`clipboard-${Date.now()}.${ext}`,{type:t});$("img").value="";S("Image read from system clipboard");return}if(it.types.includes("text/plain")){const b=await it.getType("text/plain");$("txt").value=await b.text();clipImg=null;S("Text read from system clipboard");return}}S("Clipboard has no supported content","warn")}catch(e){S("Clipboard read failed: "+(e.message||e),"warn")}};
(async()=>{try{const conf=await (await fetch("/api/config")).json();const id=(new URL(location.href).searchParams.get("id")||localStorage.getItem("shareclip_id")||conf.default_id||"").trim();setId(id);await Promise.all([rf(),rh()]);setInterval(()=>rf().catch(()=>{}),3000)}catch(e){S(e.message||String(e),"warn")}})();
</script></body></html>"""

CONFIG_HTML = """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ShareClip Config</title><style>
body{margin:0;padding:clamp(14px,2.5vw,22px);min-height:100vh;background:linear-gradient(165deg,#dce4f2 0%,#e8ecf4 38%,#eef1f8 100%);background-attachment:fixed;color:#1c2333;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC",sans-serif;font-size:15px}
.c{width:min(calc(100vw - clamp(24px,5vw,56px)),760px);max-width:calc(100vw - clamp(24px,5vw,56px));margin:0 auto;background:#fff;border:1px solid rgba(28,35,51,.12);border-radius:14px;padding:18px 20px;box-shadow:0 4px 24px rgba(15,23,42,.08)}
input{width:100%;padding:10px 12px;border:1px solid rgba(28,35,51,.12);border-radius:10px;background:#f8fafc;color:#1c2333;font-size:15px}
button{border:0;border-radius:10px;padding:9px 14px;background:#2563eb;color:#fff;cursor:pointer;font-weight:600}a{color:#2563eb;text-decoration:none;margin-left:8px}
code{background:#eef2ff;border-radius:6px;padding:2px 8px;color:#1e40af;font-size:13px}#msg.ok{color:#059669}#msg.warn{color:#d97706}.f{margin-top:14px;color:#5c6578;font-size:12px}
</style></head><body><section class="c"><h2>ShareClip Config</h2><p>Update default port and default ID.</p>
<label>Default port</label><input id="port" type="number" min="1" max="65535"><label>Default ID</label><input id="did" type="text" placeholder="pub">
<p><button id="save">Save</button><a href="/">Back</a></p><p id="msg"></p><p id="hint"></p>
<div class="f">Author: <a href="mailto:mengke@pku.org.cn">RandyPKU</a> | License: Apache License 2.0 | <a href="https://github.com/EinProfispieler/shareclip" target="_blank" rel="noopener">GitHub</a></div>
</section><script>
const re=/^[A-Za-z0-9_-]{1,64}$/;const msg=(t,l="ok")=>{const e=document.getElementById("msg");e.textContent=t;e.className=l};
async function load(){const r=await fetch("/api/config");if(!r.ok)throw new Error("load config failed");const d=await r.json();port.value=d.port;did.value=d.default_id;hint.textContent=`Current running port: ${d.running_port}. Restart service to apply port change.`}
save.onclick=async()=>{try{const p=Number(port.value),i=(did.value||"").trim();if(!re.test(i))throw new Error("Default ID must be 1-64 chars: letters/numbers/_/-");const r=await fetch("/api/config",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({port:p,default_id:i})});const d=await r.json().catch(()=>({}));if(!r.ok)throw new Error(d.error||"save failed");msg(d.message||"saved");hint.textContent=d.restart_required?"Saved. Port change will be active after service restart.":"Saved."}catch(e){msg(e.message||String(e),"warn")}};
load().catch(e=>msg(e.message||String(e),"warn"));
</script></body></html>"""


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def make_record_id() -> str:
    return f"clip_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"


def save_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def load_json(path: Path, default: object) -> object:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def normalize_port(value: object) -> int:
    try:
        p = int(value)
    except (TypeError, ValueError):
        raise ValueError("Port must be integer.")
    if p < 1 or p > 65535:
        raise ValueError("Port must be in 1-65535.")
    return p


def normalize_id(value: object, fallback: bool = True) -> str:
    raw = str(value).strip() if value is not None else ""
    if not raw and fallback:
        raw = str(runtime_config.get("default_id", DEFAULT_ID))
    if not ID_RE.fullmatch(raw):
        raise ValueError("Invalid id. Use letters/numbers/_/-, length 1-64.")
    return raw


def profile_paths(profile_id: str) -> dict[str, Path]:
    base = STORAGE_ROOT / profile_id
    legacy_base = LEGACY_STORAGE_ROOT / profile_id
    return {
        "dir": base,
        "images": base / "images",
        "state": base / "state.json",
        "legacy_latest": legacy_base / "latest.json",
        "legacy_history": legacy_base / "history.json",
        "legacy_state": legacy_base / "state.json",
    }


def empty_record() -> dict[str, object]:
    return {"type": "empty", "updated_at": None}


def normalize_record(record: dict[str, object], profile_id: str) -> dict[str, object]:
    if record.get("type") not in {"text", "image"}:
        return empty_record()
    out = dict(record)
    out["id"] = out.get("id") or make_record_id()
    out["profile_id"] = profile_id
    out["updated_at"] = out.get("updated_at") or now_iso()
    if out.get("type") == "text":
        out["text"] = str(out.get("text", ""))
    else:
        name = str(out.get("image_filename", "")).strip()
        if not name and out.get("image_path"):
            name = Path(str(out["image_path"])).name
        out["image_filename"] = name
    return out


def load_profile_state(profile_id: str) -> tuple[dict[str, object], list[dict[str, object]], Path]:
    paths = profile_paths(profile_id)
    paths["images"].mkdir(parents=True, exist_ok=True)
    state_raw = load_json(paths["state"], {})

    latest_raw: object = empty_record()
    history_raw: object = []
    if isinstance(state_raw, dict) and ("latest" in state_raw or "history" in state_raw):
        latest_raw = state_raw.get("latest", empty_record())
        history_raw = state_raw.get("history", [])
    else:
        # Legacy fallback: migrate from older split files in /storage/<id>.
        legacy_state_raw = load_json(paths["legacy_state"], {})
        if isinstance(legacy_state_raw, dict) and ("latest" in legacy_state_raw or "history" in legacy_state_raw):
            latest_raw = legacy_state_raw.get("latest", empty_record())
            history_raw = legacy_state_raw.get("history", [])
        else:
            latest_raw = load_json(paths["legacy_latest"], empty_record())
            history_raw = load_json(paths["legacy_history"], [])

    latest = normalize_record(latest_raw, profile_id) if isinstance(latest_raw, dict) else empty_record()
    history: list[dict[str, object]] = []
    if isinstance(history_raw, list):
        for item in history_raw:
            if isinstance(item, dict):
                n = normalize_record(item, profile_id)
                if n.get("type") in {"text", "image"}:
                    history.append(n)
    if not history and latest.get("type") in {"text", "image"}:
        history = [latest]
    if latest.get("type") == "empty" and history:
        latest = history[0]
    history = history[:MAX_HISTORY]
    save_json(paths["state"], {"latest": latest, "history": history})
    return latest, history, paths["dir"]


def save_profile_state(profile_id: str, latest: dict[str, object], history: list[dict[str, object]]) -> None:
    paths = profile_paths(profile_id)
    save_json(paths["state"], {"latest": latest, "history": history})


def delete_image(profile_id: str, record: dict[str, object]) -> None:
    if record.get("type") != "image":
        return
    name = str(record.get("image_filename", "")).strip()
    if not name:
        return
    f = profile_paths(profile_id)["images"] / name
    try:
        if f.exists():
            f.unlink()
    except OSError:
        pass


def public_record(record: dict[str, object]) -> dict[str, object]:
    if record.get("type") == "text":
        return {"id": record.get("id"), "profile_id": record.get("profile_id"), "type": "text", "text": record.get("text", ""), "updated_at": record.get("updated_at")}
    if record.get("type") == "image":
        pid = str(record.get("profile_id", ""))
        name = record.get("image_filename")
        return {"id": record.get("id"), "profile_id": pid, "type": "image", "image_filename": name, "image_url": f"/clips/{pid}/{name}" if name else None, "updated_at": record.get("updated_at")}
    return {"type": "empty", "updated_at": record.get("updated_at")}


def request_profile_id() -> str:
    raw = request.args.get("id")
    if raw is None and request.method in {"POST", "DELETE"}:
        raw = request.form.get("id")
    if raw is None and request.is_json:
        raw = (request.get_json(silent=True) or {}).get("id")
    return normalize_id(raw, fallback=True)


def load_config() -> None:
    global runtime_config, runtime_port
    STORAGE_ROOT.mkdir(parents=True, exist_ok=True)
    conf = load_json(CONFIG_FILE, {})
    if (not conf or not isinstance(conf, dict)) and STORAGE_ROOT != LEGACY_STORAGE_ROOT:
        conf = load_json(LEGACY_STORAGE_ROOT / "config.json", {})
    if not isinstance(conf, dict):
        conf = {}
    try:
        port = normalize_port(conf.get("port", DEFAULT_PORT))
    except ValueError:
        port = DEFAULT_PORT
    try:
        default_id = normalize_id(conf.get("default_id", DEFAULT_ID), fallback=False)
    except ValueError:
        default_id = DEFAULT_ID
    runtime_config = {"port": port, "default_id": default_id}
    runtime_port = port
    save_json(CONFIG_FILE, runtime_config)


@app.get("/")
def index() -> str:
    return INDEX_HTML


@app.get("/config")
def config_page() -> str:
    return CONFIG_HTML


@app.get("/api/config")
def get_config():
    with LOCK:
        conf = dict(runtime_config)
    return jsonify({"port": conf["port"], "default_id": conf["default_id"], "running_port": runtime_port, "max_history": MAX_HISTORY, "author": AUTHOR_NAME, "license": LICENSE_NAME, "repo": REPO_URL})


@app.post("/api/config")
def set_config():
    global runtime_config
    data = request.get_json(silent=True) or {}
    try:
        port = normalize_port(data.get("port", runtime_config["port"]))
        default_id = normalize_id(data.get("default_id", runtime_config["default_id"]), fallback=False)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    with LOCK:
        runtime_config = {"port": port, "default_id": default_id}
        save_json(CONFIG_FILE, runtime_config)
    restart_needed = port != runtime_port
    msg = "Config saved."
    if restart_needed:
        msg += f" Port will change from {runtime_port} to {port} after restart."
    return jsonify({"ok": True, "restart_required": restart_needed, "message": msg, "config": runtime_config})


@app.get("/api/clip")
def get_clip():
    try:
        pid = request_profile_id()
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    with LOCK:
        latest, history, _ = load_profile_state(pid)
    return jsonify({"profile_id": pid, "clip": public_record(latest), "history_count": len(history)})


@app.get("/api/history")
def get_history():
    try:
        pid = request_profile_id()
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    try:
        limit = int(request.args.get("limit", "100"))
    except ValueError:
        limit = 100
    limit = max(1, min(limit, MAX_HISTORY))
    with LOCK:
        _, history, _ = load_profile_state(pid)
    return jsonify({"profile_id": pid, "items": [public_record(x) for x in history[:limit]], "total": len(history)})


@app.post("/api/clip")
def set_clip():
    try:
        pid = request_profile_id()
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    text = (request.form.get("text") or "").strip()
    image = request.files.get("image")
    paths = profile_paths(pid)
    paths["images"].mkdir(parents=True, exist_ok=True)

    if image and image.filename:
        mime = (image.mimetype or "").split(";")[0]
        if not mime.startswith("image/"):
            return jsonify({"error": "Only image uploads are allowed."}), 400
        ext = mimetypes.guess_extension(mime) or Path(image.filename).suffix or ".png"
        if ext == ".jpe":
            ext = ".jpg"
        rid = make_record_id()
        fname = f"{rid}{ext.lower()}"
        target = paths["images"] / fname
        image.save(target)
        rec = normalize_record({"id": rid, "type": "image", "profile_id": pid, "image_filename": fname, "image_path": str(target), "updated_at": now_iso()}, pid)
    elif text:
        rec = normalize_record({"id": make_record_id(), "type": "text", "profile_id": pid, "text": text, "updated_at": now_iso()}, pid)
    else:
        return jsonify({"error": "Please provide text or image."}), 400

    with LOCK:
        _, history, _ = load_profile_state(pid)
        history.insert(0, rec)
        if len(history) > MAX_HISTORY:
            removed = history[MAX_HISTORY:]
            history = history[:MAX_HISTORY]
            for old in removed:
                delete_image(pid, old)
        save_profile_state(pid, rec, history)
    return jsonify({"ok": True, "profile_id": pid, "clip": public_record(rec)})


@app.delete("/api/history/<record_id>")
def delete_history(record_id: str):
    try:
        pid = request_profile_id()
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    with LOCK:
        _, history, _ = load_profile_state(pid)
        idx = next((i for i, x in enumerate(history) if x.get("id") == record_id), None)
        if idx is None:
            return jsonify({"error": f"Record id not found: {record_id}"}), 404
        removed = history.pop(idx)
        delete_image(pid, removed)
        latest = history[0] if history else empty_record()
        save_profile_state(pid, latest, history)
    return jsonify({"ok": True, "deleted_id": record_id, "profile_id": pid, "latest": public_record(latest), "total": len(history)})


@app.get("/api/clip/raw")
def clip_raw():
    try:
        pid = request_profile_id()
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    with LOCK:
        latest, _, _ = load_profile_state(pid)
    if latest.get("type") == "text":
        return Response(str(latest.get("text", "")), mimetype="text/plain; charset=utf-8")
    if latest.get("type") == "image":
        name = str(latest.get("image_filename", "")).strip()
        if not name:
            return jsonify({"error": "No image filename."}), 404
        return send_from_directory(profile_paths(pid)["images"], name)
    return jsonify({"error": "No clip yet."}), 404


@app.get("/clips/<profile_id>/<path:filename>")
def image_file(profile_id: str, filename: str):
    try:
        clean = normalize_id(profile_id, fallback=False)
    except ValueError:
        return jsonify({"error": "Invalid profile id."}), 400
    return send_from_directory(profile_paths(clean)["images"], filename)


load_config()

if __name__ == "__main__":
    print(f"[shareclip] Storage root: {STORAGE_ROOT}")
    print(f"[shareclip] Config file: {CONFIG_FILE}")
    print(f"[shareclip] Default profile id: {runtime_config['default_id']}")
    print(f"[shareclip] Max history per id: {MAX_HISTORY}")
    print(f"[shareclip] Listening on 0.0.0.0:{runtime_port}")
    app.run(host="0.0.0.0", port=runtime_port, debug=False)
