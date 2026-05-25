/* AfterClaw — hi-fi interactive prototype */
const { useState, useEffect, useRef, useMemo, Fragment } = React;

/* ───── Icons (24x24 lucide-ish, tuned 16) ───── */
const Ic = {
  dash: <svg className="icon-svg" viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="9" /><rect x="14" y="3" width="7" height="5" /><rect x="14" y="12" width="7" height="9" /><rect x="3" y="16" width="7" height="5" /></svg>,
  files: <svg className="icon-svg" viewBox="0 0 24 24"><path d="M3 6a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" /></svg>,
  monitor: <svg className="icon-svg" viewBox="0 0 24 24"><path d="M3 14l4-6 4 4 4-9 4 7 2-2" /></svg>,
  nodes: <svg className="icon-svg" viewBox="0 0 24 24"><rect x="3" y="3" width="8" height="8" /><rect x="13" y="13" width="8" height="8" /><path d="M11 7h6a2 2 0 0 1 2 2v4M13 17H7a2 2 0 0 1-2-2v-4" /></svg>,
  docker: <svg className="icon-svg" viewBox="0 0 24 24"><rect x="3" y="10" width="3" height="3" /><rect x="7" y="10" width="3" height="3" /><rect x="11" y="10" width="3" height="3" /><rect x="7" y="6" width="3" height="3" /><rect x="11" y="6" width="3" height="3" /><rect x="11" y="2" width="3" height="3" /><path d="M2 14c0 4 4 6 8 6s10-2 12-9c-3 1-5 0-6-1" /></svg>,
  term: <svg className="icon-svg" viewBox="0 0 24 24"><path d="M4 7l4 4-4 4M11 16h8" /><rect x="2" y="3" width="20" height="18" rx="2" /></svg>,
  svc: <svg className="icon-svg" viewBox="0 0 24 24"><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33h0a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51h0a1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" /></svg>,
  set: <svg className="icon-svg" viewBox="0 0 24 24"><path d="M4 6h12M4 12h16M4 18h8" /><circle cx="19" cy="6" r="2" /><circle cx="13" cy="18" r="2" /></svg>,
  share: <svg className="icon-svg" viewBox="0 0 24 24"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M17 8l-5-5-5 5M12 3v12" /></svg>,
  search: <svg className="icon-svg" viewBox="0 0 24 24"><circle cx="11" cy="11" r="7" /><path d="M20 20l-3.5-3.5" /></svg>,
  upload: <svg className="icon-svg" viewBox="0 0 24 24"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M17 8l-5-5-5 5M12 3v12" /></svg>,
  plus: <svg className="icon-svg" viewBox="0 0 24 24"><path d="M12 5v14M5 12h14" /></svg>,
  play: <svg className="icon-svg" viewBox="0 0 24 24"><path d="M6 4l14 8-14 8z" fill="currentColor" /></svg>,
  stop: <svg className="icon-svg" viewBox="0 0 24 24"><rect x="6" y="6" width="12" height="12" fill="currentColor" /></svg>,
  restart: <svg className="icon-svg" viewBox="0 0 24 24"><path d="M3 12a9 9 0 0 1 15-6.7L21 8M21 4v4h-4M21 12a9 9 0 0 1-15 6.7L3 16M3 20v-4h4" /></svg>,
  copy: <svg className="icon-svg" viewBox="0 0 24 24"><rect x="9" y="9" width="11" height="11" rx="2" /><path d="M5 15V5a2 2 0 0 1 2-2h10" /></svg>,
  bell: <svg className="icon-svg" viewBox="0 0 24 24"><path d="M18 16v-5a6 6 0 0 0-12 0v5l-2 2h16zM10 21h4" /></svg>,
  user: <svg className="icon-svg" viewBox="0 0 24 24"><circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0 1 16 0" /></svg>
};

/* ───── Helpers ───── */
const cx = (...a) => a.filter(Boolean).join(" ");
const MEMBER_TOKEN_KEY = "memberSessionToken";
const MEMBER_ID_KEY = "memberSessionMemberId";
const MEMBER_EMAIL_KEY = "memberSessionEmail";
const MEMBER_PROFILE_KEY = "memberSessionProfile";
const MEMBER_TOKEN_COOKIE = "afterclaw_member_session";
const MEMBER_COOKIE_MAX_AGE_SEC = 30 * 24 * 3600;
const setMemberTokenCookie = (token) => {
  try {
    const t = String(token || "").trim();
    if (!t) return;
    document.cookie = `${MEMBER_TOKEN_COOKIE}=${encodeURIComponent(t)}; Max-Age=${MEMBER_COOKIE_MAX_AGE_SEC}; Path=/; SameSite=Lax`;
  } catch (_) {}
};
const clearMemberTokenCookie = () => {
  try {
    document.cookie = `${MEMBER_TOKEN_COOKIE}=; Max-Age=0; Path=/; SameSite=Lax`;
  } catch (_) {}
};
const readMemberTokenCookie = () => {
  try {
    const src = String(document.cookie || "");
    if (!src) return "";
    const parts = src.split(";").map((x) => x.trim());
    for (const p of parts) {
      if (p.startsWith(`${MEMBER_TOKEN_COOKIE}=`)) {
        return decodeURIComponent(p.slice(MEMBER_TOKEN_COOKIE.length + 1)).trim();
      }
    }
  } catch (_) {}
  return "";
};
const clearMemberSessionStore = () => {
  try {
    localStorage.removeItem(MEMBER_TOKEN_KEY);
    localStorage.removeItem(MEMBER_ID_KEY);
    localStorage.removeItem(MEMBER_EMAIL_KEY);
    localStorage.removeItem(MEMBER_PROFILE_KEY);
  } catch (_) {}
  clearMemberTokenCookie();
};
const persistMemberSessionStore = (payload, opts = {}) => {
  const keepExisting = opts && opts.keepExistingToken;
  const tokRaw = String((payload && payload.session_token) || "").trim();
  const tok = tokRaw || (keepExisting ? memberSessionToken() : "");
  if (!tok) throw new Error("Missing session token");
  let member = (payload && payload.member) || null;
  if (!member || typeof member !== "object" || !Object.keys(member).length) {
    try {
      const cached = JSON.parse(String(localStorage.getItem(MEMBER_PROFILE_KEY) || "null"));
      if (cached && typeof cached === "object" && Object.keys(cached).length) member = cached;
    } catch (_) {}
  }
  if (!member || typeof member !== "object") member = {};
  localStorage.setItem(MEMBER_TOKEN_KEY, tok);
  localStorage.setItem(MEMBER_ID_KEY, String(member.member_id || ""));
  localStorage.setItem(MEMBER_EMAIL_KEY, String(member.email || ""));
  try { localStorage.setItem(MEMBER_PROFILE_KEY, JSON.stringify(member || {})); } catch (_) {}
  setMemberTokenCookie(tok);
};
const memberSessionToken = () => {
  try {
    const t = String(localStorage.getItem(MEMBER_TOKEN_KEY) || "").trim();
    if (t) return t;
  } catch (_) {}
  return readMemberTokenCookie();
};
const authHeaders = (base) => {
  return { ...(base || {}) };
};
const apiJson = async (url, opts = {}) => {
  const next = { ...(opts || {}) };
  next.headers = authHeaders(next.headers || {});
  const r = await fetch(url, next);
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error((d && (d.detail || d.error)) || `Request failed ${r.status}`);
  return d;
};
const memberApiUrl = (path) => {
  const p = String(path || "");
  if (/^https?:\/\//i.test(p)) return p;
  return p;
};
const fmtBytes = (n) => {
  if (n < 1024) return n + " B";
  if (n < 1024 ** 2) return (n / 1024).toFixed(1) + " KB";
  if (n < 1024 ** 3) return (n / 1024 ** 2).toFixed(1) + " MB";
  if (n < 1024 ** 4) return (n / 1024 ** 3).toFixed(2) + " GB";
  return (n / 1024 ** 4).toFixed(2) + " TB";
};
const fmtRate = (bps) => {
  const n = Number(bps || 0);
  if (!Number.isFinite(n) || n <= 0) return "0 B/s";
  if (n < 1024) return `${Math.round(n)} B/s`;
  if (n < 1024 ** 2) return `${(n / 1024).toFixed(1)} KB/s`;
  if (n < 1024 ** 3) return `${(n / 1024 ** 2).toFixed(1)} MB/s`;
  return `${(n / 1024 ** 3).toFixed(2)} GB/s`;
};
const humanDur = (sec) => {
  const s = Math.max(0, Math.floor(Number(sec) || 0));
  const d = Math.floor(s / 86400);
  const h = Math.floor((s % 86400) / 3600);
  const m = Math.floor((s % 3600) / 60);
  if (d > 0) return `${d}d ${h}h`;
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
};
const diskOwnerOf = (d, live, appCfg) => {
  const mnt = String((d && d.mountpoint) || "").trim();
  const sysName = String((((appCfg || {}).ui) || {}).system_name || "").trim();
  const host = String((((live || {}).system) || {}).hostname || "").trim();
  const base = sysName || host || "System";
  const h3c = /h3c/i.test(base) ? "H3C" : base.split(/[\s\-_.]+/).filter(Boolean)[0] || "System";
  if (mnt === "/") return h3c;
  if (mnt.startsWith("/srv/Storage")) return "Storage";
  if (!mnt) return "Disk";
  const leaf = mnt.split("/").filter(Boolean).pop();
  return leaf || "Disk";
};

/* tiny svg sparkline + area */
function Sparkline({ data, color = "var(--accent)", filled = false, paper = false, unit = "" }) {
  const w = 100,h = 36;
  const max = Math.max(...data),min = Math.min(...data);
  const span = Math.max(0.001, max - min);
  const pts = data.map((v, i) => [i / (data.length - 1) * w, h - (v - min) / span * (h - 4) - 2]);
  const d = pts.map((p, i) => (i ? "L" : "M") + p[0].toFixed(1) + " " + p[1].toFixed(1)).join(" ");
  const wrapRef = useRef(null);
  const [hover, setHover] = useState(null);
  const patternId = useMemo(() => "spk-" + Math.random().toString(36).slice(2, 8), []);
  const onMove = (e) => {
    const r = wrapRef.current.getBoundingClientRect();
    const x = (e.clientX - r.left) / r.width;
    const i = Math.max(0, Math.min(data.length - 1, Math.round(x * (data.length - 1))));
    setHover({ i, v: data[i], xPct: pts[i][0], yPct: pts[i][1] });
  };
  return (
    <div className="spark-wrap" ref={wrapRef}
    onMouseMove={onMove} onMouseLeave={() => setHover(null)}>
      <svg className="spark" viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none">
        <defs>
          {/* paperish stipple — tiny dots in series color */}
          <pattern id={patternId} x="0" y="0" width="3" height="3" patternUnits="userSpaceOnUse">
            <circle cx="1" cy="1" r="0.55" fill={color} opacity="0.55" />
          </pattern>
        </defs>
        {filled && paper &&
        <path d={d + ` L ${w} ${h} L 0 ${h} Z`} fill={`url(#${patternId})`} />
        }
        {filled && !paper &&
        <path d={d + ` L ${w} ${h} L 0 ${h} Z`} fill={color} opacity="0.16" />
        }
        <path d={d} stroke={color} strokeWidth="1.4" fill="none" strokeLinejoin="round"
        vectorEffect="non-scaling-stroke" />
        {hover &&
        <g pointerEvents="none">
            <line x1={hover.xPct} x2={hover.xPct} y1="0" y2={h}
          stroke="var(--ink-3)" strokeWidth="0.6" strokeDasharray="1.4 1.4"
          vectorEffect="non-scaling-stroke" />
            <circle cx={hover.xPct} cy={hover.yPct} r="1.8"
          fill="var(--paper)" stroke={color} strokeWidth="1.2"
          vectorEffect="non-scaling-stroke" />
          </g>
        }
      </svg>
      {hover &&
      <div className="spark-tip"
      style={{ left: `${hover.i / (data.length - 1) * 100}%` }}>
          <b>{hover.v.toFixed(1)}</b>{unit && <span>{unit}</span>}
        </div>
      }
    </div>);

}
function AreaChart({ series, height = 100, max = 100, gridY = [25, 50, 75] }) {
  const w = 100,h = height;
  return (
    <svg className="area" viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" style={{ height: h + "px" }}>
      {gridY.map((g) => <line key={g} x1="0" x2={w} y1={h - g / max * h} y2={h - g / max * h} stroke="var(--rule)" strokeWidth="0.4" strokeDasharray="1 1.5" />)}
      {series.map((s, si) => {
        const pts = s.data.map((v, i) => [i / (s.data.length - 1) * w, h - v / max * (h - 2) - 1]);
        const d = pts.map((p, i) => (i ? "L" : "M") + p[0].toFixed(2) + " " + p[1].toFixed(2)).join(" ");
        return (
          <Fragment key={si}>
            <path d={d + ` L ${w} ${h} L 0 ${h} Z`} fill={s.color} opacity="0.16" />
            <path d={d} stroke={s.color} strokeWidth="1.2" fill="none" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
          </Fragment>);

      })}
    </svg>);

}

/* mock time series */
const wave = (n, base, amp, phase = 0, noise = 0.1) =>
Array.from({ length: n }, (_, i) => Math.max(0, base + Math.sin(i / 3 + phase) * amp + (Math.random() - 0.5) * amp * noise));

window.AfterClaw = function () {

  /* ═════════ Sidebar ═════════ */
  const SECTIONS = [
  { id: "dash", label: "Dashboard", icon: Ic.dash, group: "OVERVIEW" },
  { id: "monitor", label: "System monitor", icon: Ic.monitor, group: "OVERVIEW" },
  { id: "nodes", label: "Nodes", icon: Ic.nodes, group: "OVERVIEW" },
  { id: "files", label: "Files", icon: Ic.files, group: "WORKLOADS" },
  { id: "httpd", label: "HTTPD", icon: Ic.share, group: "TOOLS" },
  { id: "docker", label: "Docker", icon: Ic.docker, group: "WORKLOADS" },
  { id: "services", label: "Services", icon: Ic.svc, group: "WORKLOADS" },
  { id: "term", label: "Web terminal", icon: Ic.term, group: "TOOLS" },
  { id: "share", label: "ShareClip", icon: Ic.share, group: "TOOLS" },
  { id: "settings", label: "Settings", icon: Ic.set, group: "SYSTEM" }];


  function Sidebar({ active, onNav, navCounts }) {
    const groups = [...new Set(SECTIONS.map((s) => s.group))];
    return (
      <aside className="side">
      {groups.map((g) =>
        <div key={g} className="side-grp">
          <div className="side-group">{g}</div>
          {SECTIONS.filter((s) => s.group === g).map((s) =>
          <div key={s.id}
          className={cx("nav-item", active === s.id && "on")}
          onClick={() => onNav(s.id)}>
              <span className="ic">{s.icon}</span>
              <span>{s.label}</span>
              {!!(navCounts && navCounts[s.id] && navCounts[s.id].badge) && <span className="badge">{String(navCounts[s.id].badge)}</span>}
              {!!(navCounts && navCounts[s.id] && navCounts[s.id].alert) && <span className="badge alert">{String(navCounts[s.id].alert)}</span>}
            </div>
          )}
        </div>
        )}
    </aside>);

  }

  /* ═════════ Topbar ═════════ */
  function Topbar({ section, onTweaks, onAccount, live, appCfg, member }) {
    const label = SECTIONS.find((s) => s.id === section)?.label || "";
    const time = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    const hostRaw = String((((live || {}).system) || {}).hostname || "");
    const uiCfg = ((appCfg || {}).ui) || {};
    const host = String(uiCfg.system_name || "").trim() || "System";
    const logoUrl = String(uiCfg.brand_logo_url || "").trim();
    const osId = String((((live || {}).system) || {}).os_id || "").toLowerCase();
    const osLike = String((((live || {}).system) || {}).os_like || "").toLowerCase();
    const sys = `${String((((live || {}).system) || {}).os_pretty || "")} ${String((((live || {}).system) || {}).platform || "")} ${hostRaw} ${osId} ${osLike}`.toLowerCase();
    const presetLogo =
    osId === "ubuntu" || osLike.includes("ubuntu") ? "/ui/logos/ubuntu.svg" :
    osId === "debian" || osLike.includes("debian") ? "/ui/logos/debian.svg" :
    osId === "linuxmint" || osId === "mint" || osLike.includes("mint") ? "/ui/logos/mint.svg" :
    osId === "rhel" || osId === "redhat" || osLike.includes("rhel") || osLike.includes("redhat") ? "/ui/logos/redhat.svg" :
    osId === "fedora" ? "/ui/logos/fedora.svg" :
    osId === "rocky" ? "/ui/logos/rockylinux.svg" :
    osId === "almalinux" ? "/ui/logos/almalinux.svg" :
    osId === "centos" ? "/ui/logos/centos.svg" :
    osId === "arch" || osId === "archlinux" ? "/ui/logos/archlinux.svg" :
    osId.includes("opensuse") || osLike.includes("suse") ? "/ui/logos/opensuse.svg" :
    osId === "raspbian" || osId === "raspberrypi" ? "/ui/logos/raspberrypi.svg" :
    osId === "freebsd" || osId === "openbsd" || osId === "netbsd" ? "/ui/logos/freebsd.svg" :
    sys.includes("synology") ? "/ui/logos/synology.svg" :
    sys.includes("truenas") ? "/ui/logos/truenas.svg" :
    sys.includes("raspberry") || sys.includes("raspbian") ? "/ui/logos/raspberrypi.svg" :
    sys.includes("ubuntu") ? "/ui/logos/ubuntu.svg" :
    sys.includes("debian") ? "/ui/logos/debian.svg" :
    sys.includes("linux mint") || sys.includes("mint") ? "/ui/logos/mint.svg" :
    sys.includes("red hat") || sys.includes("rhel") ? "/ui/logos/redhat.svg" :
    sys.includes("fedora") ? "/ui/logos/fedora.svg" :
    sys.includes("rocky") ? "/ui/logos/rockylinux.svg" :
    sys.includes("alma") ? "/ui/logos/almalinux.svg" :
    sys.includes("centos") ? "/ui/logos/centos.svg" :
    sys.includes("arch") ? "/ui/logos/archlinux.svg" :
    sys.includes("suse") ? "/ui/logos/opensuse.svg" :
    sys.includes("freebsd") || sys.includes("openbsd") || sys.includes("netbsd") || sys.includes("bsd") ? "/ui/logos/freebsd.svg" :
    sys.includes("mac") || sys.includes("darwin") || sys.includes("apple") ? "/ui/logos/apple.svg" :
    sys.includes("win") || sys.includes("microsoft") ? "/ui/logos/windows.svg" :
    "/ui/logos/linux.svg";
    const finalLogo = logoUrl || presetLogo;
    return (
      <header className="topbar">
      <div className="brand">
        <img className="mascot" src={finalLogo} alt="logo" />
        <span>after<b>Claw</b></span>
      </div>
      <div className="crumbs">
        <span>{host}</span>
        <span>›</span>
        <span className="here">{label}</span>
      </div>
      <div className="spacer" />
      <span className="pill lan"><span className="d" />LAN-only</span>
      <span className="pill ok" title="uptime · clock"><span className="d" />up 5d 13h · {time}</span>
      <button className="btn icon" title="Notifications">{Ic.bell}</button>
      <button className="btn" onClick={onTweaks}>Tweaks</button>
      <button className="btn icon" title={member && member.member_id ? `Member: ${member.member_id}` : "Account"} onClick={onAccount}>{Ic.user}</button>
    </header>);

  }

  const MEMBER_AVATAR_COLORS = [
    { label: "Afternoon coral (default)", fill: ["#ff927a", "#dc6859"], text: "#ff927a", avatarInk: "#fff" },
    { label: "Ocean blue", fill: ["oklch(0.52 0.18 260)", "oklch(0.44 0.18 260)"], text: "oklch(0.52 0.18 260)", avatarInk: "#fff" },
    { label: "Signal green", fill: ["oklch(0.55 0.16 165)", "oklch(0.46 0.16 165)"], text: "oklch(0.55 0.16 165)", avatarInk: "#fff" },
    { label: "Violet", fill: ["oklch(0.55 0.18 310)", "oklch(0.46 0.18 310)"], text: "oklch(0.55 0.18 310)", avatarInk: "#fff" },
    { label: "Amber", fill: ["oklch(0.60 0.16 75)", "oklch(0.52 0.16 75)"], text: "oklch(0.60 0.16 75)", avatarInk: "#fff" },
    { label: "Light theme contrast", fill: ["#352f28", "#201c17"], text: "#352f28", avatarInk: "#fff" },
    { label: "Dim theme contrast", fill: ["#d8e2f3", "#a9b9d2"], text: "#d8e2f3", avatarInk: "#1b2433" },
    { label: "Dark theme contrast", fill: ["#ffffff", "#dbe4f1"], text: "#ffffff", avatarInk: "#131a24" }
  ];
  function memberInitials(name) {
    return String(name || "").trim().split(/\s+/).map((w) => w[0]).join("").slice(0, 2).toUpperCase() || "?";
  }
  function MemberModal({ open, onClose, member, setMember, toast, live }) {
    const editing = !!(member && member.member_id);
    const [mode, setMode] = useState(editing ? "edit" : "login");
    const [memberId, setMemberId] = useState("");
    const [password, setPassword] = useState("");
    const [regPassword, setRegPassword] = useState("");
    const [name, setName] = useState("");
    const [email, setEmail] = useState("");
    const [color, setColor] = useState(0);
    const [busy, setBusy] = useState(false);
    useEffect(() => {
      const nextMode = editing ? "edit" : "login";
      setMode(nextMode);
      if (editing) {
        setName(String(member.display_name || member.member_id || ""));
        setEmail(String(member.email || ""));
        setColor(Math.max(0, Math.min(MEMBER_AVATAR_COLORS.length - 1, Number(member.avatar_color || 0))));
      }
    }, [editing, member && member.member_id]);
    if (!open) return null;
    const clearSessionAndBackToLogin = (msg) => {
      clearMemberSessionStore();
      setMember(null);
      setMode("login");
      if (msg) toast(msg);
    };
    const saveSession = (d, opts = {}) => {
      persistMemberSessionStore(d, opts);
      const nextMember = (d && d.member) || member || null;
      setMember(nextMember);
    };
    const doLogin = async () => {
      if (!memberId.trim() || !password.trim()) return toast("请输入 display name/email 和密码");
      setBusy(true);
      try {
        const d = await apiJson(memberApiUrl("/api/member/login"), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ member_id: memberId.trim(), password }) });
        saveSession(d);
        toast("登录成功");
      } catch (e) {toast(`登录失败: ${e.message || e}`);} finally {setBusy(false);}
    };
    const doRegister = async () => {
      if (!name.trim() || !regPassword.trim() || !email.trim()) return toast("display name / password / email 必填");
      setBusy(true);
      try {
        const d = await apiJson(memberApiUrl("/api/member/register"), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ password: regPassword, display_name: name.trim(), email: email.trim(), avatar_color: 0 }) });
        clearMemberSessionStore();
        setMember(null);
        const msg = String((d && d.message) || "注册成功。请先在邮箱完成激活，然后再登录。");
        toast(msg);
        setMode("login");
      } catch (e) {toast(`注册失败: ${e.message || e}`);} finally {setBusy(false);}
    };
    const doUpdate = async () => {
      if (!name.trim()) return toast("display name 不能为空");
      setBusy(true);
      try {
        const d = await apiJson(memberApiUrl("/api/member/profile/update"), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ display_name: name.trim(), email: email.trim(), avatar_color: color }) });
        saveSession(d, { keepExistingToken: true });
        toast("资料已更新");
      } catch (e) {
        const msg = String((e && e.message) || e || "");
        if (/Member session invalid|Request failed 401|401/.test(msg)) {
          clearSessionAndBackToLogin("登录已失效，请重新登录。");
        } else {
          toast(`保存失败: ${msg}`);
        }
      } finally {setBusy(false);}
    };
    const doChangeEmail = async () => {
      const v = String(prompt("New email for verification") || "").trim();
      if (!v) return;
      setBusy(true);
      try {
        const d = await apiJson(memberApiUrl("/api/member/email-change/request"), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ new_email: v }) });
        toast(String((d && d.message) || "Verification email sent."));
      } catch (e) {toast(`修改邮箱失败: ${e.message || e}`);} finally {setBusy(false);}
    };
    const doForgotPassword = async () => {
      const v = String(prompt("Input your account email") || "").trim();
      if (!v) return;
      setBusy(true);
      try {
        const d = await apiJson(memberApiUrl("/api/member/password-reset/request"), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email: v }) });
        toast(String((d && d.message) || "If this email exists, reset mail has been sent."));
      } catch (e) {toast(`重置失败: ${e.message || e}`);} finally {setBusy(false);}
    };
    const doLogout = async () => {
      try { await apiJson(memberApiUrl("/api/member/logout"), { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" }); } catch (_) {}
      clearSessionAndBackToLogin("已退出");
    };
    const onSubmit = async (e) => {
      e.preventDefault();
      if (busy) return;
      if (editing) {
        await doUpdate();
        return;
      }
      if (mode === "login") {
        await doLogin();
        return;
      }
      if (mode === "register") {
        await doRegister();
      }
    };
    const selectedColor = MEMBER_AVATAR_COLORS[Math.max(0, Math.min(MEMBER_AVATAR_COLORS.length - 1, color))];
    const [c1, c2] = selectedColor.fill;
    const systemName = String(((((live || {}).app_config || {}).ui || {}).system_name) || "").trim();
    return (
      <div className="modal-back reg-overlay" onClick={onClose}>
        <div className={cx("reg-modal", editing ? "editing" : "auth")} onClick={(e) => e.stopPropagation()}>
          {editing && <button className="btn sm reg-logout" type="button" onClick={doLogout} disabled={busy}>Logout</button>}
          {editing && <div className="reg-avatar-wrap"><div className="reg-avatar" style={{ background: `linear-gradient(135deg, ${c1}, ${c2})`, color: selectedColor.avatarInk }}><span>{memberInitials(name)}</span></div></div>}
          <div className="reg-head">
            <div className="reg-eyebrow">{systemName ? `AFTERCLAW · ${systemName}` : "AFTERCLAW"}</div>
            <h2 className="reg-title">{editing ? "Edit profile" : mode === "register" ? "Sign up" : "Login"}</h2>
            {editing && <p className="reg-sub">Update your display name or avatar colour.</p>}
          </div>
          <form className="reg-fields" onSubmit={onSubmit}>
            {(editing || mode === "register") && <label className="reg-label"><span>Display name</span><input className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="Display name" /></label>}
            {!editing && mode === "register" && <label className="reg-label"><span>Password</span><input className="input" type="password" value={regPassword} onChange={(e) => setRegPassword(e.target.value)} placeholder="password" /></label>}
            {!editing && mode === "login" && <label className="reg-label"><span>ID or email</span><input className="input" value={memberId} onChange={(e) => setMemberId(e.target.value)} placeholder="ID or email" /></label>}
            {!editing && mode === "login" && <label className="reg-label"><span>Password</span><input className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="password" /></label>}
            {(editing || mode === "register") && <label className="reg-label"><span>Email{editing ? <em className="reg-opt"> (optional)</em> : " *"}</span><input className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder={editing ? "for future notifications" : "for activation"} disabled={editing} /></label>}
            {editing && <button className="reg-inline-action" type="button" onClick={doChangeEmail} disabled={busy}>{busy ? "Sending..." : "Change email address"}</button>}
            {editing && <div className="reg-label"><span>Avatar colour</span><div className="reg-colors">{MEMBER_AVATAR_COLORS.map((item, i) => <button key={item.label} type="button" title={item.label} aria-label={item.label} className={`reg-swatch ${color === i ? "on" : ""}`} style={{ background: `linear-gradient(135deg, ${item.fill[0]}, ${item.fill[1]})` }} onClick={() => setColor(i)} />)}</div></div>}
          </form>
          <div className="reg-actions">
            {editing && <button className="btn primary" type="button" onClick={doUpdate} disabled={busy}>{busy ? "Saving..." : "Save changes"}</button>}
            {!editing && <button className={cx("btn", "reg-auth-action", mode === "login" && "selected")} type="button" onClick={() => mode === "login" ? doLogin() : setMode("login")} disabled={busy}>{mode === "login" ? (busy ? "Logging in..." : "Login") : "Login"}</button>}
            {!editing && <button className={cx("btn", "reg-auth-action", mode === "register" && "selected")} type="button" onClick={() => mode === "register" ? doRegister() : setMode("register")} disabled={busy}>{mode === "register" ? (busy ? "Registering..." : "Sign up") : "Sign up"}</button>}
          </div>
          {!editing && <div className="reg-foot"><button className="btn sm ghost" type="button" onClick={doForgotPassword} disabled={busy}>Reset Password</button></div>}
        </div>
      </div>);
  }

  /* ═════════ Dashboard (variant A — card grid) ═════════ */
  function Dashboard({ services, toggleService, transfers, goto, toast, live, appCfg, metricHist, primaryDisk, selectedDisks, diskVisibleMap, disksPanelOpen, setDisksPanelOpen, member }) {
    const system = (live && live.system) || {};
    const hostName = String((((live || {}).app_config || {}).ui || {}).system_name || "").trim();
    const speed = (live && live.speed) || {};
    const transferMeta = (live && live.transferMeta) || {};
    const cpuValue = Number(system.load1 || 0);
    const memTotal = Number(system.mem_total || 0);
    const memUsed = Number(system.mem_used || 0);
    const memPct = memTotal > 0 ? memUsed * 100 / memTotal : 0;
    const diskRead = Number(speed.disk_read_mibps || 0);
    const diskWrite = Number(speed.disk_write_mibps || 0);
    const diskTotalSel = Number((primaryDisk && primaryDisk.total_bytes) || 0);
    const diskUsedSel = Number((primaryDisk && primaryDisk.used_bytes) || 0);
    const diskFreeSel = Math.max(0, diskTotalSel - diskUsedSel);
    const diskFreeSelHuman = primaryDisk ? fmtBytes(diskFreeSel) : "-";
    const diskTotalSelHuman = primaryDisk ? String(primaryDisk.total_human || fmtBytes(diskTotalSel)) : "-";
    const diskUsedPctSel = primaryDisk ? Number(primaryDisk.used_pct || 0) : 0;
    const netDown = Number(speed.rx_mibps || 0);
    const netUp = Number(speed.tx_mibps || 0);
    const activeTransfers = Number(transferMeta.count || 0);
    const serviceWarnCount = services.filter((s) => !!s.warn).length;
    const localHour = new Date().getHours();
    const greetingPart = localHour < 12 ? "morning" : localHour < 18 ? "afternoon" : "evening";
    const memberLabel = String((member && (member.display_name || "")) || "").trim();
    const memberColorIndex = Math.max(0, Math.min(MEMBER_AVATAR_COLORS.length - 1, Number((member && member.avatar_color) || 0)));
    const memberLabelColor = MEMBER_AVATAR_COLORS[memberColorIndex].text;
    const [tSort, setTSort] = useState("name"); // name | speed
    const sortedTransfers = useMemo(() => {
      const active = transfers.filter((x) => Number(x.pct || 0) < 100);
      const arr = active.length ? active : [...transfers];
      if (tSort === "speed") arr.sort((a, b) => parseFloat(b.speed) - parseFloat(a.speed));else
      arr.sort((a, b) => a.name.localeCompare(b.name));
      return arr;
    }, [transfers, tSort]);
    return (
      <div className="col" style={{ gap: 16 }}>
      <section className="hero-banner">
        <div className="hero-glow" />
        <div className="hero-img" aria-hidden="true" />
        <div className="hero-text">
          <div className="hero-eyebrow">{hostName ? `AFTERCLAW · ${hostName}` : "AFTERCLAW"}</div>
          <h1 className="hero-title">
            Good <span className="accent">{greetingPart}{memberLabel ? "," : "."}</span>
            {memberLabel && <span className="member-name" style={{ color: memberLabelColor }}> {memberLabel}.</span>}
          </h1>
          <p className="hero-sub">
            Everything's quiet on the box.<br />
            <b className="hero-num">{activeTransfers}</b> transfers running, <b className="hero-num warn">{serviceWarnCount}</b> service needs your attention.
          </p>
        </div>
      </section>

      <div className="grid-4">
        <StatCard label="CPU" value={cpuValue.toFixed(2)} unit="" sub={`load1 · uptime ${system.uptime_human || "-"}`} hist={(metricHist && metricHist.cpu) || [0]} unit2="" />
        <StatCard label="Memory" value={system.mem_used_human || "0B"} unit={` / ${system.mem_total_human || "0B"}`} sub={`${memPct.toFixed(1)}% used`} hist={(metricHist && metricHist.mem) || [0]} unit2="%" />
        <StatCard label="Network" value={netDown.toFixed(2)} unit=" MiB/s" sub={`↓ ${netDown.toFixed(2)} · ↑ ${netUp.toFixed(2)} MiB/s`} hist={(metricHist && metricHist.netDown) || [0]} color="var(--good)" paper unit2=" MiB/s" />
        <StatCard label="Storage" value={diskFreeSelHuman} unit={` / ${diskTotalSelHuman}`} sub={`used ${diskUsedPctSel.toFixed(1)}% · io r ${diskRead.toFixed(2)} w ${diskWrite.toFixed(2)} MiB/s`} hist={(metricHist && metricHist.diskIO) || [0]} color="var(--warn)" unit2=" MiB/s" />
      </div>
      {!!primaryDisk &&
      <section className="card">
          <div className="card-h">
            <h3>Disks</h3>
            <div className="spacer" />
            <button className="btn sm" onClick={() => setDisksPanelOpen && setDisksPanelOpen(!disksPanelOpen)}>{disksPanelOpen ? "Collapse" : "Expand"}</button>
          </div>
          {disksPanelOpen &&
          <div className="card-b">
            {(() => {
              const shown = (selectedDisks || []).filter((d) =>
              (!diskVisibleMap || diskVisibleMap[String(d.path || "")] !== false) &&
              String(d.path || "") !== String((primaryDisk || {}).path || "")
              );
              const ordered = [...shown].sort((a, b) => {
                const pa = String(a.path || "") === String((primaryDisk || {}).path || "") ? 0 : 1;
                const pb = String(b.path || "") === String((primaryDisk || {}).path || "") ? 0 : 1;
                return pa - pb;
              });
              if (!ordered.length) {
                return <div style={{ color: "var(--ink-3)" }}>No disk is set to Show.</div>;
              }
              return ordered.map((d, idx) =>
              <div key={String(d.path || d.name)} style={{ marginBottom: 10, paddingBottom: 10, borderBottom: idx < ordered.length - 1 ? "1px dashed var(--rule)" : "0" }}>
                  <div className="row" style={{ gap: 10, fontFamily: "var(--font-mono)", fontSize: 11.5, color: "var(--ink-2)", marginTop: 2, flexWrap: "nowrap", whiteSpace: "nowrap", overflow: "hidden" }}>
                    <span style={{ fontWeight: 600, color: "var(--ink)", overflow: "hidden", textOverflow: "ellipsis" }}>{`${diskOwnerOf(d, live, appCfg)} · ${String(d.path || d.name || "-")}`}</span>
                    <span>·</span>
                    <span>{String(d.mountpoint || "-")}</span>
                    <span>·</span>
                    <span>{String(d.used_human || "-")} / {String(d.total_human || "-")}</span>
                    <span>·</span>
                    <span>{Number(d.used_pct || 0).toFixed(1)}% Used</span>
                    <span>·</span>
                    <span>IO r {diskRead.toFixed(2)} w {diskWrite.toFixed(2)} MiB/s</span>
                  </div>
                  <div className="prog" style={{ marginTop: 8 }}>
                    <i style={{ width: `${Math.max(0, Math.min(100, Number(d.used_pct || 0)))}%` }} />
                  </div>
                </div>
              );
            })()}
          </div>
          }
        </section>
      }

      <div className="ctrl-rack">
        <BTServiceCard toast={toast} live={live} />
        <DDNSServiceCard toast={toast} live={live} />
        <HTTPDServiceCard toast={toast} live={live} />
      </div>

      <NetdiskPanel live={live} />

      <div className="grid-1-1-2">
        {/* Active transfers */}
        <section className="card">
          <div className="card-h">
            <h3>Active transfers</h3>
            <span className="meta">{activeTransfers} running</span>
            <div className="spacer" />
            <div className="seg" role="tablist" aria-label="Sort transfers">
              <button className={cx("seg-b", tSort === "name" && "on")} onClick={() => setTSort("name")}>Name</button>
              <button className={cx("seg-b", tSort === "speed" && "on")} onClick={() => setTSort("speed")}>Speed</button>
            </div>
            <button className="btn sm" onClick={() => goto("files")}>Open files →</button>
          </div>
          <div className="card-b dash-scroll-6" style={{ padding: 0 }}>
            {!sortedTransfers.length &&
              <div style={{ padding: "14px 16px", color: "var(--ink-3)", fontSize: 12 }}>No active transfers.</div>
              }
            {sortedTransfers.map((t, i) =>
              <div key={i} style={{ padding: "12px 16px", borderTop: i ? "1px solid var(--rule)" : "0" }}>
                <div className="row" style={{ justifyContent: "space-between", marginBottom: 6 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 0 }}>
                    <span className={cx("ficon", t.dir && "dir")} />
                    <span style={{ fontWeight: 500, color: "var(--ink)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{t.name}</span>
                    <span className="chip">{t.kind}</span>
                  </div>
                  <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--ink-2)" }}>
                    {t.speed} MB/s · ETA {t.eta}
                  </span>
                </div>
                <div className="prog striped"><i style={{ width: t.pct + "%" }} /></div>
                <div style={{ display: "flex", justifyContent: "space-between", marginTop: 4, fontFamily: "var(--font-mono)", fontSize: 10.5, color: "var(--ink-3)" }}>
                  <span>{fmtBytes(t.done)} / {fmtBytes(t.total)}</span>
                  <span>{t.pct}%</span>
                </div>
              </div>
              )}
          </div>
        </section>

        {/* Services list */}
        <section className="card">
          <div className="card-h">
            <h3>Services</h3>
            <span className="meta">{services.filter((s) => s.on).length}/{services.length} running</span>
            <div className="spacer" />
            <button className="btn sm" onClick={() => goto("services")}>Manage →</button>
          </div>
          <div className="card-b dash-scroll-6" style={{ padding: 0 }}>
            {services.map((s, i) =>
              <div key={s.id} style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 16px", borderTop: i ? "1px solid var(--rule)" : "0" }}>
                <span className={cx("pill", s.on ? s.warn ? "warn" : "ok" : "idle")}>
                  <span className="d" />{s.on ? s.warn ? "warn" : "up" : "off"}
                </span>
                <div style={{ minWidth: 0, flex: 1 }}>
                  <div style={{ fontWeight: 500, color: "var(--ink)" }}>{s.name}</div>
                  <div style={{ fontFamily: "var(--font-mono)", fontSize: 10.5, color: "var(--ink-3)" }}>{s.detail}</div>
                </div>
                <div className={cx("tog", s.on && "on")} onClick={() => toggleService(s.id)} />
              </div>
              )}
          </div>
        </section>
      </div>

      <div className="grid-2">
        {/* Activity log */}
        <section className="card">
          <div className="card-h">
            <h3>Recent activity</h3>
            <div className="spacer" />
            <span className="meta">last 24h</span>
          </div>
          <div className="card-b dash-scroll-8" style={{ padding: "6px 16px 12px" }}>
            <ActivityLog live={live} />
          </div>
        </section>
        {/* ShareClip preview */}
        <section className="card">
          <div className="card-h">
            <h3>Recent ShareClips</h3>
            <div className="spacer" />
            <button className="btn sm" onClick={() => goto("share")}>Open →</button>
          </div>
          <div className="card-b dash-scroll-8" style={{ padding: 0 }}>
            <ShareClipPreview clips={live.clipHistory || []} />
          </div>
        </section>
      </div>
    </div>);

  }

  /* ───── Control rack: BT / DDNS / HTTPD ───── */
  const BT_CLIENTS = [
  { id: "Q", name: "qBittorrent", image: "docker:qbittorrent" },
  { id: "D", name: "Deluge", image: "docker:deluge" },
  { id: "T", name: "Transmission", image: "docker:transmission" },
  { id: "R", name: "rTorrent", image: "docker:rtorrent-rutorrent" }];

  const BT_STATE = {
    Q: { running: true, down: "6.0 MB/s", up: "587 KB/s", seeding: 11, downloading: 2, active: 13, total: 13, conns: 97, dht: 856 },
    D: { running: true, down: "2.4 MB/s", up: "320 KB/s", seeding: 8, downloading: 1, active: 9, total: 14, conns: 62, dht: 412 },
    T: { running: false, down: "—", up: "—", seeding: 0, downloading: 0, active: 0, total: 6, conns: 0, dht: 0 },
    R: { running: true, down: "11.8 MB/s", up: "1.2 MB/s", seeding: 24, downloading: 4, active: 28, total: 31, conns: 184, dht: 1024 }
  };

  function BTServiceCard({ toast, live }) {
    const mapClient = { Q: "qbittorrent", D: "deluge", T: "transmission", R: "rtorrent" };
    const revClient = { qbittorrent: "Q", deluge: "D", transmission: "T", rtorrent: "R" };
    const qcfg = (((live || {}).app_config || {}).qbt || {});
    const defaultClient = revClient[String(qcfg.client || "qbittorrent").toLowerCase()] || "Q";
    const [clientKey, setClientKey] = useState(defaultClient);
    const [qbtView, setQbtView] = useState((live && live.qbt) || {});
    const [clientStateMap, setClientStateMap] = useState({});
    useEffect(() => setQbtView((live && live.qbt) || {}), [live && live.qbt]);
    useEffect(() => {
      const c = mapClient[clientKey] || "qbittorrent";
      let dead = false;
      apiJson(`/api/control/status?client=${encodeURIComponent(c)}`).then((d) => {
        if (!dead) setQbtView((d && d.qbt) || {});
      }).catch(() => {});
      return () => { dead = true; };
    }, [clientKey]);
    useEffect(() => {
      const clients = ["qbittorrent", "deluge", "transmission", "rtorrent"];
      let dead = false;
      (async () => {
        const next = {};
        await Promise.all(clients.map(async (c) => {
          try {
            const d = await apiJson(`/api/control/status?client=${encodeURIComponent(c)}`);
            next[c] = String((((d || {}).qbt || {}).active_state || "")).toLowerCase() === "active";
          } catch (e) {
            next[c] = false;
          }
        }));
        if (!dead) setClientStateMap(next);
      })();
      return () => { dead = true; };
    }, [live && live.qbt, live && live.system]);
    const stats = qbtView.stats || {};
    const running = String(qbtView.active_state || "") === "active";
    const label = String(qbtView.unit || "qBittorrent");
    const clientName = {
      Q: "qBittorrent",
      D: "Deluge",
      T: "Transmission",
      R: "rTorrent",
    }[clientKey] || "BitTorrent";
    const unitTextRaw = String(qbtView.unit || "");
    const unitText = unitTextRaw.toLowerCase().startsWith("docker:") ? unitTextRaw.replace(/^docker:/i, "") : unitTextRaw;
    const down = fmtRate(stats.dl_bps || 0);
    const up = fmtRate(stats.up_bps || 0);
    const enabledMap = Object.assign({ qbittorrent: true, deluge: true, transmission: true, rtorrent: true }, qcfg.homepage_clients_enabled || {});
    const orderRaw = Array.isArray(qcfg.homepage_clients_order) ? qcfg.homepage_clients_order : ["qbittorrent", "deluge", "transmission", "rtorrent"];
    const order = orderRaw.filter((x) => revClient[String(x || "").toLowerCase()]).map((x) => revClient[String(x || "").toLowerCase()]);
    const runAction = async (action) => {
      const c = mapClient[clientKey] || "qbittorrent";
      try {
        await apiJson("/api/control/service", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ service: "qbt", action, client: c }),
        });
        toast(`BitTorrent ${action} requested`);
      } catch (e) {
        toast(`BitTorrent ${action} failed: ${e.message || e}`);
      }
    };
    return (
      <section className="card ctrl bt">
      <div className="card-h">
        <h3>BitTorrent Service</h3>
        <div className="spacer" />
        <div className="bt-switch">
          {order.map((k) => {
            const c = mapClient[k];
            if (!enabledMap[c]) return null;
            const isLive = !!clientStateMap[c];
            return (
              <button key={k} className={cx("bt-pill", clientKey === k && "on", isLive ? "live" : "off")} onClick={() => setClientKey(k)}>{k}</button>
            );
          })}
        </div>
      </div>
      <div className="card-b ctrl-b">
        <div className="row" style={{ gap: 8, alignItems: "center" }}>
          <span className={cx("pill", running ? "ok" : "idle")}><span className="d" />{running ? "Running" : "Stopped"}</span>
          <span style={{ fontFamily: "var(--font-mono)", fontSize: 11.5, color: "var(--ink-2)" }}>{clientName}</span>
          {!!unitText && <span style={{ fontFamily: "var(--font-mono)", fontSize: 11.5, color: "var(--ink-3)" }}>· {unitText}</span>}
        </div>
        <div className="row" style={{ gap: 8, marginTop: 10 }}>
          <span className="speed-tag dn">↓ {down}</span>
          <span className="speed-tag up">↑ {up}</span>
        </div>
        <div className="bt-stats">
          Seeding <b>{Number(stats.seeding || 0)}</b> · Downloading <b>{Number(stats.downloading || 0)}</b> · Active <b>{Number(stats.active || 0)}</b> · Total <b>{Number(stats.total || 0)}</b> · Connections <b>{Number(stats.peers || 0)}</b> · DHT <b>{Number(stats.dht_nodes || 0)}</b>
        </div>
        <div className="row ctrl-actions">
          <button className="btn sm" onClick={() => runAction("start")}>{Ic.play}<span style={{ marginLeft: 4 }}>Start</span></button>
          <button className="btn sm" onClick={() => runAction("stop")}>{Ic.stop}<span style={{ marginLeft: 4 }}>Stop</span></button>
          <button className="btn sm" onClick={() => runAction("restart")}>{Ic.restart}<span style={{ marginLeft: 4 }}>Restart</span></button>
        </div>
      </div>
    </section>);

  }

  function DDNSServiceCard({ toast, live }) {
    const ddns = (live && live.ddns) || {};
    const running = String(ddns.active_state || "") === "active";
    const detail = String(ddns.detail || "Built-in DDNS");
    const domains = Array.isArray(ddns.sync_domains) ? ddns.sync_domains.filter(Boolean) : [];
    const runAction = async (action) => {
      try {
        await apiJson("/api/control/service", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ service: "ddns", action }),
        });
        toast(`DDNS ${action} requested`);
      } catch (e) {
        toast(`DDNS ${action} failed: ${e.message || e}`);
      }
    };
    return (
      <section className="card ctrl ddns">
      <div className="card-h"><h3>DDNS Service</h3></div>
      <div className="card-b ctrl-b">
        <div className="row" style={{ gap: 8 }}>
          <span className={cx("pill", running ? "ok" : "idle")}><span className="d" />{running ? "Running" : "Stopped"}</span>
          <span style={{ fontFamily: "var(--font-mono)", fontSize: 11.5, color: "var(--ink-2)" }}>{String(ddns.unit || "ddns")}</span>
        </div>
        <div className="ctrl-meta">{detail}</div>
        {!!domains.length &&
          <div className="ctrl-meta">Domain: <b style={{ color: "var(--ink)" }}>{domains.join(", ")}</b></div>
          }
        <div className="row ctrl-actions">
          <button className="btn sm" onClick={() => runAction("stop")}>{Ic.stop}<span style={{ marginLeft: 4 }}>Stop</span></button>
          <button className="btn sm" onClick={() => runAction("restart")}>{Ic.restart}<span style={{ marginLeft: 4 }}>Sync now</span></button>
        </div>
      </div>
    </section>);

  }

  function HTTPDServiceCard({ toast, live }) {
    const http = (live && live.self) || {};
    const access = (live && live.http_access) || {};
    const running = String(http.active_state || "") === "active";
    const mode = String(access.effective_mode || "lan_only");
    const modeText = mode === "public" ? "Public" : "LAN-only";
    const isTimed = Number(access.public_seconds_remaining || 0) > 0;
    const [durationSec, setDurationSec] = React.useState(8 * 3600);
    const remain = Math.max(0, Number(access.public_seconds_remaining || 0));
    const remainText = remain > 0 ? humanDur(remain) : "off";
    const runService = async (action) => {
      try {
        await apiJson("/api/control/service", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ service: "self", action }),
        });
        toast(`HTTPD ${action} requested`);
      } catch (e) {
        toast(`HTTPD ${action} failed: ${e.message || e}`);
      }
    };
    const setAccess = async (action, dSec) => {
      try {
        await apiJson("/api/control/http-access", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(dSec ? { action, duration_sec: dSec } : { action }),
        });
        toast("HTTP access mode updated");
      } catch (e) {
        toast(`HTTP access update failed: ${e.message || e}`);
      }
    };
    const toggleTimed = async () => {
      if (mode !== "public") {
        await setAccess("open_public", durationSec);
        return;
      }
      if (isTimed) {
        await setAccess("open_public_persistent");
      } else {
        await setAccess("open_public", durationSec);
      }
    };
    const onDurationChange = async (e) => {
      const v = Number((e && e.target && e.target.value) || 3600) || 3600;
      setDurationSec(v);
      if (mode === "public" && isTimed) {
        try {
          await setAccess("open_public", v);
        } catch (_) {}
      }
    };
    return (
      <section className="card ctrl httpd">
      <div className="card-h"><h3>HTTPD Service</h3></div>
      <div className="card-b ctrl-b">
        <div className="row" style={{ gap: 8 }}>
          <span className={cx("pill", running ? "ok" : "idle")}><span className="d" />{running ? "Running" : "Stopped"}</span>
          <span style={{ fontFamily: "var(--font-mono)", fontSize: 11.5, color: "var(--ink-2)" }}>{String(http.unit || "storage-http-link-web")}</span>
        </div>
        <div className="ctrl-meta">
          File Access: <b style={{ color: "var(--ink)" }}>{modeText}</b>
          {mode === "public" &&
            <span className={cx("http-mode", isTimed ? "timed" : "persistent")}>
              {isTimed ? `Timer ${remainText}` : "Persistent"}
            </span>
            }
        </div>
        <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--ink-3)", marginTop: 4 }}>
          Status: {String(http.detail || "-")}
        </div>
        <div className="row ctrl-actions" style={{ flexWrap: "wrap" }}>
          <button className={cx("btn sm", mode !== "public" && "primary")} onClick={() => setAccess("close")}>Lan only</button>
          <button className={cx("btn sm", mode === "public" && "primary")} onClick={() => setAccess("open_public", durationSec)}>Lan+Wan</button>
          <button
            className={cx("btn sm timed-tog", isTimed && "alive")}
            disabled={mode !== "public"}
            onClick={toggleTimed}>
            <span className="dot" />
            <span style={{ marginLeft: 6 }}>Timed</span>
          </button>
          <select
            className="in ctrl-sel"
            disabled={mode !== "public" || !isTimed}
            value={durationSec}
            onChange={onDurationChange}>
            <option value={3600}>1h</option>
            <option value={8 * 3600}>8h</option>
            <option value={24 * 3600}>24h</option>
            <option value={72 * 3600}>3d</option>
          </select>
          <span className="ctrl-sep" />
          <button className="btn sm" onClick={() => runService("restart")}>{Ic.restart}<span style={{ marginLeft: 4 }}>Restart</span></button>
        </div>
      </div>
    </section>);

  }

  /* ───── Netdisk gauges (round dash meters) ───── */
  const NETDISKS = [
  { id: "all", label: "OVERALL" },
  { id: "baidu", label: "BAIDU" },
  { id: "guangya", label: "GUANGYA" },
  { id: "aliyun", label: "ALIYUN" }];


  function NetdiskGauge({ d, unit, max = 100, onToggleUnit }) {
    const size = 132,r = 52,cx_ = size / 2,cy = size / 2;
    const upRatio = Math.min(1, d.up / max);
    const dnRatio = Math.min(1, d.down / max);
    const idle = d.up + d.down < 0.01;
    // Rotate -90° so the circle path's 0-point (3 o'clock) lands at 12 o'clock.
    // Going clockwise from there gives us the RIGHT half (download).
    const rotateTop = `rotate(-90 ${cx_} ${cy})`;
    // Mirror horizontally so the same "clockwise from top" appears as the LEFT half.
    const mirrorLeft = `translate(${size} 0) scale(-1 1)`;
    return (
      <div className="gauge-card">
      <div className="gauge-head">
        <span className="gauge-title">{d.label}</span>
        <span className={cx("gauge-count", idle && "off")}>{d.count}</span>
      </div>
      <div className="gauge-wrap">
        <svg viewBox={`0 0 ${size} ${size}`} className="gauge-svg" width={size} height={size}>
          {/* dashed clock-face track */}
          <circle cx={cx_} cy={cy} r={r} fill="none"
            stroke="var(--ink-4)" strokeWidth="7"
            strokeDasharray="1.3 2.9"
            opacity="0.55"
            transform={rotateTop} />

          {/* RIGHT half — download (clockwise from top, fills 0..50 of pathLength=100) */}
          {!idle &&
            <circle cx={cx_} cy={cy} r={r} fill="none"
            stroke="var(--good)" strokeWidth="7" strokeLinecap="butt"
            pathLength="100"
            strokeDasharray={`${dnRatio * 50} 100`}
            transform={rotateTop}
            style={{ transition: "stroke-dasharray .4s ease" }} />
            }

          {/* LEFT half — upload (mirror to flip the same arc to the left side) */}
          {!idle &&
            <g transform={mirrorLeft}>
              <circle cx={cx_} cy={cy} r={r} fill="none"
              stroke="var(--accent)" strokeWidth="7" strokeLinecap="butt"
              pathLength="100"
              strokeDasharray={`${upRatio * 50} 100`}
              transform={rotateTop}
              style={{ transition: "stroke-dasharray .4s ease" }} />
            </g>
            }

          {/* TOP split tick at 12 o'clock — slim "start" marker */}
          <line x1={cx_} y1={cy - r - 2.5} x2={cx_} y2={cy - r + 2.5}
            stroke="var(--ink-2)" strokeWidth="1.4" strokeLinecap="round" />

          {/* BOTTOM split tick at 6 o'clock — slim boundary marker */}
          <line x1={cx_} y1={cy + r - 2.5} x2={cx_} y2={cy + r + 2.5}
            stroke="var(--ink-3)" strokeWidth="1.2" strokeLinecap="round" />

          {/* Side identifiers */}
          <text x={cx_ - r + 3} y={cy} textAnchor="start" dominantBaseline="middle"
            fontFamily="var(--font-mono)" fontSize="8" fontWeight="600"
            fill="var(--accent)" letterSpacing="0.06em">↑UP</text>
          <text x={cx_ + r - 3} y={cy} textAnchor="end" dominantBaseline="middle"
            fontFamily="var(--font-mono)" fontSize="8" fontWeight="600"
            fill="var(--good)" letterSpacing="0.06em">DN↓</text>
        </svg>
        <div className="gauge-center">
          <div className="g-line"><span className="g-arrow up">↑</span>{d.up.toFixed(2)}</div>
          <div className="g-line"><span className="g-arrow dn">↓</span>{d.down.toFixed(2)}</div>
          <button className="g-unit-btn" onClick={onToggleUnit}>{unit || "Mbps"}</button>
        </div>
      </div>
    </div>);

  }

  const NETDISK_TABS = [
  { id: "all", label: "All" },
  { id: "baidu", label: "Baidu Netdisk" },
  { id: "aliyun", label: "Aliyun Drive" },
  { id: "guangya", label: "Guangya Drive" }];

  function NetdiskPanel({ live }) {
    const [tab, setTab] = useState("all");
    const [unit, setUnit] = useState(() => {
      try {
        const u = localStorage.getItem("ac-netdisk-unit");
        return u === "MiB/s" ? "MiB/s" : "Mbps";
      } catch (_) {
        return "Mbps";
      }
    });
    const speed = (live && live.speed) || {};
    const transfers = (live && live.transferMeta) || {};
    const sourceRows = Array.isArray(transfers.source_stats) ? transfers.source_stats : [];
    const sourceMap = sourceRows.reduce((acc, row) => {
      const src = String(row.source || "").toLowerCase();
      let key = "";
      if (src.includes("guangya") || src.includes("cloud")) key = "guangya";
      else if (src.includes("baidu")) key = "baidu";
      else if (src.includes("ali")) key = "aliyun";
      if (key) acc[key] = row;
      return acc;
    }, {});
    const dialRowsRaw = NETDISKS.map((d) => {
      if (d.id === "all") {
        return {
          ...d,
          count: Number(speed.active_conn_1288 || 0),
          up: Number(speed.tx_mbps || 0),
          down: Number(speed.rx_mbps || 0),
        };
      }
      const row = sourceMap[d.id] || {};
      return {
        ...d,
        count: Number(row.count || 0),
        up: Number((row.upload_mibps || 0) * 8),
        down: Number((row.download_mibps || 0) * 8),
      };
    });
    const dialRows = dialRowsRaw.map((d) => {
      if (unit === "MiB/s") return { ...d, up: d.up / 8, down: d.down / 8 };
      return { ...d };
    });
    const gaugeMax = unit === "MiB/s" ? 125 : 1000;
    useEffect(() => {
      try {localStorage.setItem("ac-netdisk-unit", unit);} catch (_) {}
    }, [unit]);
    return (
      <section className="card">
      <div className="card-h">
        <h3>Cloud sync · netdisk activity</h3>
        <div className="spacer" />
        <div className="nd-tabs">
          {NETDISK_TABS.map((t) =>
            <button key={t.id} className={cx("nd-tab", tab === t.id && "on")} onClick={() => setTab(t.id)}>{t.label}</button>
            )}
          <button className="btn sm icon" title="Configure providers">{Ic.set}</button>
        </div>
      </div>
      <div className="card-b" style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 14 }}>
        {dialRows.map((d) => <NetdiskGauge key={d.id} d={d} unit={unit} max={gaugeMax} onToggleUnit={() => setUnit((u) => u === "Mbps" ? "MiB/s" : "Mbps")} />)}
      </div>
      <div className="card-h" style={{ borderTop: "1px solid var(--rule)", borderBottom: 0 }}>
        <h3 style={{ fontSize: 12.5 }}>Aggregate HTTP Session Activity</h3>
        <div className="spacer" />
        <button className="btn sm" onClick={() => setUnit((u) => u === "Mbps" ? "MiB/s" : "Mbps")}>{unit}</button>
        <span className="meta">Active {Number(transfers.count || 0)} · Done {Number(transfers.recent_count || 0)} · Progress {Number(transfers.overall_progress_pct || 0).toFixed(1)}%</span>
      </div>
    </section>);

  }

  function StatCard({ label, value, unit, sub, hist, color = "var(--accent)", paper = false, unit2 = "" }) {
    return (
      <div className="card stat">
      <div className="card-b">
        <div className="label">{label}</div>
        <div className="v">{value}<span className="u">{unit}</span></div>
        <div className="sub">{sub}</div>
        <div style={{ marginTop: 8 }}><Sparkline data={hist} color={color} filled paper={paper} unit={unit2} /></div>
      </div>
    </div>);

  }

  function ActivityLog({ live }) {
    const txRows = (((live || {}).transferMeta || {}).items || []).slice(0, 6).map((it) => ({
      t: new Date(((it.ended_at || it.started_at || Date.now() / 1000) * 1000)).toTimeString().slice(0, 5),
      k: "transfer",
      txt: `${it.filename || it.relative_path || "unknown"} · ${(it.progress_pct || 0).toFixed(1)}% · ${(it.speed_mibps || 0).toFixed(2)} MiB/s`,
      tag: it.done ? "ok" : "",
    }));
    const svcRows = [
    { t: "", k: "qbt", txt: String(((live || {}).qbt || {}).detail || "qB status unavailable"), tag: String(((live || {}).qbt || {}).active_state || "") === "active" ? "ok" : "warn" },
    { t: "", k: "ddns", txt: String(((live || {}).ddns || {}).detail || "DDNS status unavailable"), tag: String(((live || {}).ddns || {}).active_state || "") === "active" ? "ok" : "" }];
    const items = [...txRows, ...svcRows].slice(0, 8);

    return (
      <div style={{ display: "flex", flexDirection: "column" }}>
      {!items.length && <div style={{ padding: "8px 0", color: "var(--ink-3)", fontSize: 12 }}>No recent activity.</div>}
      {items.map((it, i) =>
        <div key={i} style={{ display: "flex", alignItems: "baseline", gap: 10, padding: "5px 0", borderTop: i ? "1px solid var(--rule)" : "0" }}>
          <span style={{ fontFamily: "var(--font-mono)", fontSize: 10.5, color: "var(--ink-3)", width: 38 }}>{it.t}</span>
          <span className="chip" style={{ minWidth: 56, textAlign: "center" }}>{it.k}</span>
          <span style={{ fontSize: 12.5, color: "var(--ink-2)", flex: 1 }}>{it.txt}</span>
          {it.tag === "ok" && <span className="pill ok"><span className="d" />ok</span>}
          {it.tag === "warn" && <span className="pill warn"><span className="d" />warn</span>}
        </div>
        )}
    </div>);

  }

  function ShareClipPreview({ clips }) {
    const items = Array.isArray(clips) ? clips : [];
    const quickCopy = async (v) => {
      const text = String(v || "").trim();
      if (!text) return;
      try {
        await navigator.clipboard.writeText(text);
      } catch (_) {}
    };

    return (
      <div>
      {!items.length && <div style={{ padding: "12px 16px", color: "var(--ink-3)", fontSize: 12 }}>No ShareClip history yet.</div>}
      {items.map((m, i) =>
        <div key={m.id || i} style={{ padding: "10px 16px", borderTop: i ? "1px solid var(--rule)" : "0" }}>
          <div style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
            <span style={{ fontWeight: 600, fontSize: 12.5, color: "var(--ink)" }}>{m.who || "shareclip"}</span>
            <span style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--ink-3)" }}>· {m.t || "-"}</span>
          </div>
          <div style={{ fontSize: 12.5, color: "var(--ink-2)", marginTop: 2 }}>{m.text}</div>
          <div className="row" style={{ marginTop: 6, gap: 6 }}>
            <button className="btn sm" onClick={() => quickCopy(m.text || m.attach || "")}>Copy</button>
          </div>
          {m.code &&
          <div style={{ marginTop: 5, fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--ink)", background: "var(--paper-2)", padding: "5px 8px", borderRadius: 6, border: "1px solid var(--rule)" }}>
              {m.code}
            </div>
          }
          {m.attach &&
          <div className="row" style={{ marginTop: 5, padding: "5px 8px", border: "1px solid var(--rule)", borderRadius: 6, background: "var(--paper-2)" }}>
              <span className="ficon" />
              <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--ink-2)" }}>{m.attach}</span>
            </div>
          }
        </div>
        )}
    </div>);

  }

  /* ═════════ Files (variant A — two-pane) ═════════ */
  const TREE = [
  { id: "media", label: "Media", count: 4, kids: [
    { id: "media/movies", label: "Movies", count: 128 },
    { id: "media/series", label: "Series", count: 47 },
    { id: "media/music", label: "Music", count: 2310 },
    { id: "media/photos", label: "Photos", count: 8842 }]
  },
  { id: "projects", label: "Projects", count: 3, open: true, kids: [
    { id: "projects/aurora", label: "aurora-app", count: 64, active: true },
    { id: "projects/sticker-co", label: "sticker-co", count: 29 },
    { id: "projects/render-farm", label: "render-farm", count: 8 }]
  },
  { id: "backups", label: "Backups", count: 12 },
  { id: "share", label: "Public share", count: 3, badge: "public" }];


  const FILES_AURORA = [
  { name: "src", dir: true, size: "—", mod: "today" },
  { name: "assets", dir: true, size: "—", mod: "yesterday" },
  { name: "build", dir: true, size: "—", mod: "Mon" },
  { name: "package.json", size: 4_312, mod: "today" },
  { name: "README.md", size: 12_080, mod: "today" },
  { name: "design-spec.pdf", size: 2_100_000, mod: "Tue" },
  { name: "logo-final.svg", size: 14_290, mod: "Mon" },
  { name: "preview.mp4", size: 184_300_000, mod: "Mon" }];


  function Files({ pushTransfer }) {
    const [sel, setSel] = useState("projects/aurora");
    const [picked, setPicked] = useState(["preview.mp4"]);
    const togglePick = (n) => setPicked((p) => p.includes(n) ? p.filter((x) => x !== n) : [...p, n]);
    const onUpload = () => {
      pushTransfer({
        name: "design-pack-v2.zip", kind: "upload", pct: 4, speed: "11.2",
        eta: "1m 12s", done: 9_400_000, total: 240_000_000
      });
    };
    return (
      <div className="col" style={{ overflowX: "hidden" }}>
      <div>
        <h1 className="h1">Files</h1>
        <p className="sub">Browse, share, and move data across the box.</p>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "240px 1fr", gap: 12, alignItems: "start" }}>
        <aside className="card" style={{ padding: "10px 6px" }}>
          {TREE.map((node) => <TreeNode key={node.id} node={node} sel={sel} setSel={setSel} />)}
        </aside>
        <section className="card">
          <div className="card-h">
            <h3 style={{ fontFamily: "var(--font-mono)", fontSize: 12.5 }}>~/projects/aurora-app</h3>
            <span className="meta">8 items · 186 MB</span>
            <div className="spacer" />
            <button className="btn sm" onClick={onUpload}>{Ic.upload}<span style={{ marginLeft: 4 }}>Upload</span></button>
            <button className="btn sm">{Ic.plus}<span style={{ marginLeft: 4 }}>New</span></button>
            <button className="btn sm primary" disabled={!picked.length}>Share ({picked.length})</button>
          </div>
          <div className="row" style={{ padding: "10px 16px", borderBottom: "1px solid var(--rule)", gap: 8 }}>
            <div style={{ flex: 1, position: "relative" }}>
              <input className="input" placeholder="Search this folder…" style={{ paddingLeft: 30 }} />
              <span style={{ position: "absolute", left: 8, top: 8, color: "var(--ink-3)" }}>{Ic.search}</span>
            </div>
            <button className="btn sm">Sort: modified ▾</button>
          </div>
          <table className="tbl">
            <thead><tr>
              <th style={{ width: 24 }}></th>
              <th>Name</th>
              <th style={{ width: 120, textAlign: "right" }}>Size</th>
              <th style={{ width: 120 }}>Modified</th>
              <th style={{ width: 90 }}></th>
            </tr></thead>
            <tbody>
              {FILES_AURORA.map((f) =>
                <tr key={f.name} className={picked.includes(f.name) ? "sel" : ""}>
                  <td><input type="checkbox" checked={picked.includes(f.name)} onChange={() => togglePick(f.name)} /></td>
                  <td className="k" style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span className={cx("ficon", f.dir && "dir")} />
                    {f.name}
                  </td>
                  <td style={{ textAlign: "right", fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--ink-3)" }}>
                    {f.dir ? "—" : fmtBytes(f.size)}
                  </td>
                  <td style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--ink-3)" }}>{f.mod}</td>
                  <td><button className="btn sm ghost">···</button></td>
                </tr>
                )}
            </tbody>
          </table>
        </section>
      </div>
    </div>);

  }

  function HTTPDBrowser({ toast }) {
    const [rootDir, setRootDir] = useState("/");
    const [relDir, setRelDir] = useState(".");
    const [subdirs, setSubdirs] = useState([]);
    const [scanText, setScanText] = useState("");
    const [files, setFiles] = useState([]);
    const [linksGenerated, setLinksGenerated] = useState(false);
    const [renamePlan, setRenamePlan] = useState([]);
    const [subPlan, setSubPlan] = useState([]);
    const [subtitleFiles, setSubtitleFiles] = useState([]);
    const [subtitleUploading, setSubtitleUploading] = useState(false);
    const [subtitleUploadStatus, setSubtitleUploadStatus] = useState("");
    const [subtitleUploadResult, setSubtitleUploadResult] = useState([]);
    const [removeSub, setRemoveSub] = useState("");
    const [stripCjk, setStripCjk] = useState(false);
    const [reorderSeason, setReorderSeason] = useState(true);
    const [recursive, setRecursive] = useState(false);

    const syncFromConfig = async () => {
      const st = await apiJson("/api/control/status");
      const httpCfg = (((st || {}).app_config || {}).http_service || {});
      const root = String(httpCfg.root_dir || ((st || {}).http_root_dir || "/"));
      const def = String(httpCfg.default_dir || ".");
      setRootDir(root);
      setRelDir(def || ".");
      return { root, def };
    };
    const loadDirs = async (dirArg, rootArg) => {
      const root = String(rootArg || rootDir || "/");
      const target = String(dirArg || relDir || ".");
      const d = await apiJson(`/api/directories?stats=0&root_dir=${encodeURIComponent(root)}&dir=${encodeURIComponent(target)}`);
      const cur = String((d && d.current_dir) || target || ".");
      const effectiveRoot = String((d && d.http_root_dir) || root);
      setRootDir(effectiveRoot);
      setRelDir(cur);
      setSubdirs(Array.isArray(d.directories) ? d.directories : []);
      return d;
    };
    const parentDir = (dir) => {
      const s = String(dir || ".").replace(/^\/+|\/+$/g, "");
      if (!s || s === ".") return ".";
      const parts = s.split("/");
      parts.pop();
      return parts.length ? parts.join("/") : ".";
    };
    const dirName = (dir) => {
      const s = String(dir || ".").replace(/^\/+|\/+$/g, "");
      if (!s || s === ".") return "";
      const parts = s.split("/");
      return parts[parts.length - 1] || "";
    };
    const copyText = async (text, okMsg) => {
      const t = String(text || "").trim();
      if (!t) return;
      try {
        await navigator.clipboard.writeText(t);
        if (okMsg) toast(okMsg);
      } catch (_) {
        try {
          const ta = document.createElement("textarea");
          ta.value = t;
          ta.style.position = "fixed";
          ta.style.left = "-9999px";
          document.body.appendChild(ta);
          ta.focus();
          ta.select();
          const ok = document.execCommand("copy");
          document.body.removeChild(ta);
          if (ok && okMsg) toast(okMsg);
          if (!ok) toast("Copy failed");
        } catch (_) {
          toast("Copy failed");
        }
      }
    };
    const readFileAsBase64 = (file) =>
      new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onerror = () => reject(new Error(`Failed to read ${file.name}`));
        reader.onload = () => {
          const text = String(reader.result || "");
          const idx = text.indexOf(",");
          resolve(idx >= 0 ? text.slice(idx + 1) : text);
        };
        reader.readAsDataURL(file);
      });
    const loadFiles = async (dirArg, rootArg) => {
      const root = String(rootArg || rootDir || "/");
      const dir = String(dirArg || relDir || ".");
      const d = await apiJson(`/api/files?root_dir=${encodeURIComponent(root)}&dir=${encodeURIComponent(dir)}`);
      setFiles(Array.isArray(d.items) ? d.items : []);
      setLinksGenerated(true);
      toast(`Generated ${Array.isArray(d.items) ? d.items.length : 0} links`);
    };
    const scanRoot = async (rootArg) => {
      const root = String(rootArg || rootDir || "/");
      const d = await apiJson(`/api/http/path-scan?path=${encodeURIComponent(root)}`);
      const parts = [];
      parts.push(`Path: ${d.path || "-"}`);
      if (!d.exists) parts.push("Not found");else
      if (!d.is_dir) parts.push("Not a directory");else {
        const perm = `${d.can_read ? "r" : "-"}${d.can_write ? "w" : "-"}${d.can_exec ? "x" : "-"}`;
        parts.push(`Permissions(${perm})`);
        parts.push(`Subdirs ${Number(d.child_dir_count || 0)} · Files ${Number(d.child_file_count || 0)}`);
      }
      if (Array.isArray(d.sample_dirs) && d.sample_dirs.length) parts.push(`Samples: ${d.sample_dirs.slice(0, 6).join(", ")}`);
      setScanText(parts.join(" | "));
    };
    const previewRename = async () => {
      const d = await apiJson("/api/clean/preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          dir: relDir || ".",
          target: "both",
          recursive,
          remove_substrings: removeSub,
          strip_cjk: stripCjk,
          move_season_before_year: reorderSeason,
        }),
      });
      setRenamePlan(Array.isArray(d.moves) ? d.moves : []);
      toast("Rename preview ready");
    };
    const applyRename = async () => {
      if (!renamePlan.length) return;
      await apiJson("/api/clean/apply", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ moves: renamePlan }),
      });
      toast("Rename applied");
      await loadDirs(relDir);
    };
    const previewSubtitle = async () => {
      const d = await apiJson("/api/subtitle-align/preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ dir: relDir || ".", recursive }),
      });
      setSubPlan(Array.isArray(d.moves) ? d.moves : []);
      toast("Subtitle preview ready");
    };
    const applySubtitle = async () => {
      if (!subPlan.length) return;
      await apiJson("/api/subtitle-align/apply", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ moves: subPlan }),
      });
      toast("Subtitle alignment applied");
      await loadDirs(relDir);
    };
    const uploadSubtitles = async () => {
      if (!subtitleFiles.length) {
        setSubtitleUploadStatus("Please choose subtitle files or archives first.");
        return;
      }
      setSubtitleUploading(true);
      setSubtitleUploadStatus("Reading files...");
      setSubtitleUploadResult([]);
      try {
        const payloadFiles = [];
        for (const f of subtitleFiles) {
          payloadFiles.push({
            name: f.name,
            size: f.size,
            content_b64: await readFileAsBase64(f),
          });
        }
        setSubtitleUploadStatus("Uploading...");
        const data = await apiJson("/api/subtitles/upload", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ dir: relDir || ".", files: payloadFiles }),
        });
        const rows = Array.isArray(data.results) ? data.results : [];
        setSubtitleUploadResult(rows);
        setSubtitleUploadStatus(`Done: success ${Number(data.success_count || 0)}, failed ${Number(data.failed_count || 0)}.`);
        if (Number(data.success_count || 0) > 0) {
          await loadDirs(relDir);
          toast(`Uploaded/extracted ${Number(data.success_count || 0)} subtitle item(s)`);
        }
      } catch (e) {
        setSubtitleUploadStatus(`Upload failed: ${e.message || String(e)}`);
      } finally {
        setSubtitleFiles([]);
        setSubtitleUploading(false);
      }
    };

    useEffect(() => {
      let dead = false;
      const boot = async () => {
        try {
          const { root, def } = await syncFromConfig();
          if (dead) return;
          await scanRoot(root);
          if (dead) return;
          await loadDirs(def || ".", root);
        } catch (_) {}
      };
      boot();
      return () => { dead = true; };
    }, []);

    return (
      <div className="col">
      <div>
        <h1 className="h1">HTTPD</h1>
        <p className="sub">Live tools for HTTP links, rename workflow and subtitle matching.</p>
      </div>
      <div className="httpd-top-grid">
      <aside className="card httpd-directory-card">
        <div style={{ padding: "4px 8px", fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--ink-3)" }}>{rootDir}</div>
        <div className="httpd-left-list">
        <button className="btn sm ghost" onClick={() => {
          const p = parentDir(relDir);
          setRelDir(p);
          setFiles([]);
          setLinksGenerated(false);
          loadDirs(p).catch((e) => toast(e.message || String(e)));
        }}>.. (Parent)</button>
        {subdirs.map((d, i) =>
          <button key={i} title={d} className="btn sm ghost" style={{ textAlign: "left" }} onClick={() => {
            setRelDir(d);
            setFiles([]);
            setLinksGenerated(false);
            loadDirs(d).catch((e) => toast(e.message || String(e)));
          }}><span className="httpd-dir-button-text">{d}</span></button>
        )}
        </div>
      </aside>
      <div className="card">
        <div className="card-h httpd-head">
          <div className="row httpd-actions" style={{ gap: 8 }}>
            <button className="btn sm httpd-btn-1" onClick={() => loadFiles().catch((e) => toast(e.message || String(e)))}>Generate links</button>
            <button className="btn sm httpd-btn-2" onClick={() => copyText(files.map((x) => x.http_url).filter(Boolean).join("\n"), "All links copied")}>Copy all links</button>
            <button className="btn sm httpd-btn-3" onClick={() => copyText(dirName(relDir), "Directory name copied")}>Copy dir name</button>
          </div>
          <h3 className="httpd-dir-title" style={{ fontFamily: "var(--font-mono)", fontSize: 12.5 }}>{relDir}</h3>
          <span className="meta httpd-dir-meta">{subdirs.length} subdirectories · {files.length} files</span>
        </div>
        <div className="card-b httpd-main-list" style={{ fontFamily: "var(--font-mono)", fontSize: 11.5 }}>
          {!linksGenerated && <div style={{ color: "var(--ink-3)" }}>Click <b>Generate links</b> to load files.</div>}
          {linksGenerated && !files.length && <div style={{ color: "var(--ink-3)" }}>No links generated yet.</div>}
          {files.slice(0, 2000).map((f, i) =>
            <div key={`f-top-${i}`} style={{ padding: "6px 0", borderTop: i ? "1px solid var(--rule)" : "0" }}>
              <div className="row" style={{ gap: 8 }}>
                <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{f.relative_path}</span>
                <button className="btn sm" onClick={() => copyText(f.http_url, "Link copied")}>Copy link</button>
              </div>
            </div>
          )}
        </div>
      </div>
      </div>
      <div className="grid-2 httpd-tools-grid">
        <div className="card">
          <div className="card-h"><h3>Rename / Clean</h3></div>
          <div className="card-b">
            <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
              <input className="input" style={{ maxWidth: 260 }} value={removeSub} onChange={(e) => setRemoveSub(e.target.value)} placeholder="remove substrings: ad,promo" />
              <label className="chip"><input type="checkbox" checked={stripCjk} onChange={(e) => setStripCjk(e.target.checked)} /> strip CJK</label>
              <label className="chip"><input type="checkbox" checked={reorderSeason} onChange={(e) => setReorderSeason(e.target.checked)} /> season before year</label>
              <label className="chip"><input type="checkbox" checked={recursive} onChange={(e) => setRecursive(e.target.checked)} /> recursive</label>
            </div>
            <div className="row" style={{ gap: 8, marginTop: 8 }}>
              <button className="btn sm" onClick={() => previewRename().catch((e) => toast(e.message || String(e)))}>Preview</button>
              <button className="btn sm primary" onClick={() => applyRename().catch((e) => toast(e.message || String(e)))}>Apply</button>
              <span className="meta">{renamePlan.length} moves</span>
            </div>
          </div>
        </div>
        <div className="card">
          <div className="card-h"><h3>Subtitle Match</h3></div>
          <div className="card-b">
            <div className="row" style={{ gap: 8 }}>
              <button className="btn sm" onClick={() => previewSubtitle().catch((e) => toast(e.message || String(e)))}>Preview</button>
              <button className="btn sm primary" onClick={() => applySubtitle().catch((e) => toast(e.message || String(e)))}>Apply</button>
              <span className="meta">{subPlan.length} moves</span>
            </div>
            <div style={{ marginTop: 10, paddingTop: 10, borderTop: "1px solid var(--rule)" }}>
              <p className="meta" style={{ marginBottom: 8 }}>Subtitle upload supports .srt/.ass/.ssa/.vtt/.sup/.sub/.idx and archives .zip/.rar/.7z/.gz/.tgz/.tar/.bz2/.xz.</p>
              <div className="subtitle-upload-row">
                <input
                  className="input subtitle-upload-input"
                  type="file"
                  multiple
                  accept=".srt,.ass,.ssa,.vtt,.sup,.sub,.idx,.zip,.rar,.7z,.gz,.tgz,.tar,.tbz2,.txz,.bz2,.xz"
                  onChange={(e) => setSubtitleFiles(Array.from(e.target.files || []))}
                />
                <button className="btn sm subtitle-upload-btn" disabled={subtitleUploading} onClick={() => uploadSubtitles().catch((e) => toast(e.message || String(e)))}>
                  {subtitleUploading ? "Uploading..." : "Upload subtitles"}
                </button>
              </div>
              {subtitleFiles.length > 0 && <div className="meta" style={{ marginTop: 6 }}>{subtitleFiles.length} file(s) selected</div>}
              {subtitleUploadStatus && <div className="meta" style={{ marginTop: 6 }}>{subtitleUploadStatus}</div>}
              {!!subtitleUploadResult.length &&
                <div className="card" style={{ marginTop: 8 }}>
                  <div className="card-b" style={{ maxHeight: 140, overflow: "auto", fontFamily: "var(--font-mono)", fontSize: 11.5 }}>
                    {subtitleUploadResult.map((r, i) =>
                      <div key={`sub-upload-${i}`} style={{ padding: "4px 0", borderTop: i ? "1px solid var(--rule)" : "0", color: r && r.ok ? "var(--good)" : "var(--bad)" }}>
                        {r && r.ok ? "OK" : "FAIL"} · {String((r && r.file) || "(unknown)")}
                        {!r?.ok && r?.message ? ` · ${String(r.message)}` : ""}
                      </div>
                    )}
                  </div>
                </div>
              }
            </div>
          </div>
        </div>
      </div>
      <div className="card">
        <div className="card-h"><h3>Preview Moves</h3></div>
        <div className="card-b" style={{ maxHeight: 260, overflow: "auto", fontFamily: "var(--font-mono)", fontSize: 11.5 }}>
          {renamePlan.slice(0, 120).map((m, i) => <div key={`r-${i}`} style={{ padding: "4px 0", borderTop: i ? "1px solid var(--rule)" : "0" }}>{m.old_rel} → {m.new_rel}</div>)}
          {subPlan.slice(0, 120).map((m, i) => <div key={`s-${i}`} style={{ padding: "4px 0", borderTop: "1px solid var(--rule)" }}>{m.old_rel} → {m.new_rel}</div>)}
          {!renamePlan.length && !subPlan.length && <div style={{ color: "var(--ink-3)" }}>No preview yet.</div>}
        </div>
      </div>
    </div>);
  }
  function TreeNode({ node, sel, setSel, depth = 0 }) {
    const [open, setOpen] = useState(node.open || false);
    const isSel = sel === node.id;
    return (
      <>
      <div
          onClick={() => {setSel(node.id);if (node.kids) setOpen((o) => !o);}}
          style={{
            display: "flex", alignItems: "center", gap: 6,
            padding: "5px 8px", borderRadius: 6, cursor: "pointer",
            paddingLeft: 8 + depth * 14,
            background: isSel ? "var(--accent-soft)" : "transparent",
            color: isSel ? "var(--ink)" : "var(--ink-2)",
            fontWeight: isSel ? 600 : 400,
            fontSize: 12.5
          }}>
        {node.kids ? <span style={{ fontSize: 10, color: "var(--ink-3)", width: 10 }}>{open ? "▾" : "▸"}</span> : <span style={{ width: 10 }} />}
        <span className={cx("ficon", "dir")} style={{ marginRight: 2 }} />
        <span>{node.label}</span>
        {node.badge && <span className="pill public" style={{ marginLeft: "auto", fontSize: 9 }}><span className="d" />{node.badge}</span>}
        <span style={{ marginLeft: node.badge ? 4 : "auto", fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--ink-3)" }}>{node.count}</span>
      </div>
      {open && node.kids && node.kids.map((k) => <TreeNode key={k.id} node={k} sel={sel} setSel={setSel} depth={depth + 1} />)}
    </>);

  }

  /* ═════════ System monitor (variant A — stacked timelines) ═════════ */
  function Monitor({ live, appCfg, metricHist, primaryDiskPath, setPrimaryDiskPath, selectedDiskPaths, setSelectedDiskPaths, diskVisibleMap, setDiskVisibleMap }) {
    const ranges = ["5m", "1h", "6h", "24h", "7d"];
    const [r, setR] = useState("1h");
    const system = (live && live.system) || {};
    const speed = (live && live.speed) || {};
    const cpu = (metricHist && metricHist.cpu) || [0];
    const mem = (metricHist && metricHist.mem) || [0];
    const netDown = (metricHist && metricHist.netDown) || [0];
    const netUp = (metricHist && metricHist.netUp) || [0];
    const disk = (metricHist && metricHist.disk) || [0];
    const memUsed = system.mem_used_human || "0B";
    const memTotal = system.mem_total_human || "0B";
    const netDownNow = Number(speed.rx_mibps || 0);
    const netUpNow = Number(speed.tx_mibps || 0);
    const diskReadNow = Number(speed.disk_read_mibps || 0);
    const disks = Array.isArray(system.disks) ? system.disks : [];
    return (
      <div className="col">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div>
          <h1 className="h1">System monitor</h1>
          <p className="sub">Live metrics across CPU, memory, network and storage.</p>
        </div>
        <div className="row">
          <span className="meta" style={{ fontFamily: "var(--font-mono)", fontSize: 10.5, color: "var(--ink-3)" }}>RANGE</span>
          {ranges.map((x) =>
            <button key={x} className={cx("btn sm", r === x && "primary")} onClick={() => setR(x)}>{x}</button>
            )}
        </div>
      </div>

      <div className="grid-2">
        <ChartCard title="CPU" right={`${cpu[cpu.length - 1].toFixed(1)}%`} series={[{ data: cpu, color: "var(--accent)" }]} max={100} />
        <ChartCard title="Memory" right={`${memUsed} / ${memTotal}`} series={[{ data: mem, color: "oklch(0.6 0.13 280)" }]} max={100} />
        <ChartCard title="Network" right={`↓ ${netDownNow.toFixed(2)} · ↑ ${netUpNow.toFixed(2)} MB/s`} series={[
          { data: netDown, color: "var(--good)" }, { data: netUp, color: "var(--accent)" }]
          } max={80} />
        <ChartCard title="Disk I/O" right={`${diskReadNow.toFixed(2)} MB/s read`} series={[{ data: disk, color: "var(--warn)" }]} max={100} />
      </div>
      <div className="card">
        <div className="card-h">
          <h3>Per-disk health</h3>
          <div className="spacer" />
          <span className="meta">{disks.length} disk(s) · select primary + dashboard disks</span>
        </div>
        <div className="card-b">
          {!disks.length && <div style={{ color: "var(--ink-3)" }}>No per-disk data available from runtime.</div>}
          {disks.map((d) =>
          <DiskRow
            key={String(d.path || d.name)}
            d={d}
            owner={diskOwnerOf(d, live, appCfg)}
            primaryChecked={String(primaryDiskPath || "") === String(d.path || "")}
            selectedChecked={Array.isArray(selectedDiskPaths) && selectedDiskPaths.includes(String(d.path || ""))}
            visible={(!diskVisibleMap || diskVisibleMap[String(d.path || "")] !== false)}
            onPickPrimary={() => setPrimaryDiskPath && setPrimaryDiskPath(String(d.path || ""))}
            onToggleSelected={() => {
              const p = String(d.path || "");
              if (!setSelectedDiskPaths) return;
              setSelectedDiskPaths((prev) => {
                const arr = Array.isArray(prev) ? [...prev] : [];
                return arr.includes(p) ? arr.filter((x) => x !== p) : [...arr, p];
              });
            }}
            onToggleVisible={() => {
              const p = String(d.path || "");
              if (!setDiskVisibleMap) return;
              setDiskVisibleMap((prev) => ({ ...(prev || {}), [p]: ((prev || {})[p] === false) }));
            }}
          />
          )}
        </div>
      </div>
    </div>);

  }
  function ChartCard({ title, right, series, max }) {
    return (
      <div className="card">
      <div className="card-h">
        <h3>{title}</h3>
        <div className="spacer" />
        <span className="meta">{right}</span>
      </div>
      <div className="card-b" style={{ padding: "12px 14px" }}>
        <AreaChart series={series} max={max} />
      </div>
    </div>);

  }
  function DiskRow({ d, owner, primaryChecked, selectedChecked, visible, onPickPrimary, onToggleSelected, onToggleVisible }) {
    const pct = Number(d.used_pct || 0);
    const sm = d.smart || {};
    const smartText = sm.available ? `${String(sm.status || "unknown")}${Number.isFinite(Number(sm.temperature_c)) ? ` · ${Number(sm.temperature_c)}°C` : ""}${Number.isFinite(Number(sm.power_on_hours)) ? ` · ${Number(sm.power_on_hours)}h` : ""}${Number.isFinite(Number(sm.reallocated_sectors)) ? ` · realloc ${Number(sm.reallocated_sectors)}` : ""}${Number.isFinite(Number(sm.pending_sectors)) ? ` · pending ${Number(sm.pending_sectors)}` : ""}` : `unavailable${sm.reason ? ` (${String(sm.reason)})` : ""}`;
    return (
      <div style={{ padding: "10px 0", borderBottom: "1px solid var(--rule)" }}>
      <div className="row" style={{ justifyContent: "space-between", marginBottom: 6 }}>
        <div className="row">
          <input type="radio" name="primary-disk" checked={!!primaryChecked} onChange={() => onPickPrimary && onPickPrimary()} title="Primary Storage chart" />
          <input type="checkbox" checked={!!selectedChecked} onChange={() => onToggleSelected && onToggleSelected()} title="Show in Disks panel" />
          <span className="chip">{String(owner || "Disk")}</span>
          <span style={{ fontWeight: 500 }}>{String(d.name || d.path || "-")}</span>
          <span className="chip">{String(d.path || "-")}</span>
          {!!d.fstype && <span className="chip">{String(d.fstype)}</span>}
          <span className={cx("pill", String(d.health || "ok") === "warn" ? "warn" : "ok")}><span className="d" />{String(d.health || "ok")}</span>
          {!!d.mountpoint && <span style={{ fontSize: 11.5, color: "var(--ink-3)" }}>{String(d.mountpoint)}</span>}
        </div>
        <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--ink-2)" }}>
          {String(d.used_human || "-")} / {String(d.total_human || "-")}
        </span>
      </div>
      <div className="prog"><i style={{ width: pct + "%" }} /></div>
      <div style={{ marginTop: 6, fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--ink-3)" }}>
        SMART: {smartText}
      </div>
      <div className="row" style={{ justifyContent: "flex-end", marginTop: 6, gap: 8 }}>
        <span className="meta">{visible ? "Show" : "Hide"}</span>
        <div className={cx("tog", visible && "on")} onClick={() => onToggleVisible && onToggleVisible()} />
      </div>
    </div>);

  }

  /* ═════════ Nodes (live host card) ═════════ */
  function Nodes({ live, appCfg, homeDisk }) {
    const system = (live && live.system) || {};
    const speed = (live && live.speed) || {};
    const qbt = (live && live.qbt) || {};
    const ddns = (live && live.ddns) || {};
    const self = (live && live.self) || {};
    const memTotal = Number(system.mem_total || 0);
    const memUsed = Number(system.mem_used || 0);
    const uiCfg = ((appCfg || {}).ui) || {};
    const node = {
      id: String(uiCfg.system_name || system.hostname || "ubuntu-server"),
      role: "primary",
      os: String(system.os_pretty || system.platform || "Linux server"),
      uptime: String(system.uptime_human || "-"),
      cpu: Math.max(0, Math.min(100, Number(system.load1 || 0) * 10)),
      mem: memTotal > 0 ? Math.max(0, Math.min(100, memUsed * 100 / memTotal)) : 0,
      net: Number(speed.rx_mibps || 0) + Number(speed.tx_mibps || 0),
      services: [qbt, ddns, self].filter((x) => String(x.active_state || "") === "active").length,
      disk: homeDisk ?
      `${String(homeDisk.used_human || "-")} / ${String(homeDisk.total_human || "-")} (${String(homeDisk.path || "-")})` :
      `${system.disk_used_human || "0B"} / ${system.disk_total_human || "0B"}`,
      here: true,
      status: "ok"
    };
    return (
      <div className="col">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div>
          <h1 className="h1">Nodes</h1>
          <p className="sub">Live host status from runtime.</p>
        </div>
      </div>
      <div className="grid-3">
        <NodeCard n={node} />
      </div>
      <div className="card">
        <div className="card-h">
          <h3>Node activity</h3>
          <div className="spacer" />
          <span className="meta">last 1h</span>
        </div>
        <div className="card-b" style={{ padding: 0 }}>
          <NodeActivityRow t={new Date().toTimeString().slice(0, 5)} who={node.id} what={`qB: ${String(qbt.detail || "-")}`} />
          <NodeActivityRow t={new Date().toTimeString().slice(0, 5)} who={node.id} what={`DDNS: ${String(ddns.detail || "-")}`} />
          <NodeActivityRow t={new Date().toTimeString().slice(0, 5)} who={node.id} what={`HTTPD: ${String(self.detail || `${String(self.unit || "storage-http-link-web")} · ${String(self.active_state || "unknown")}`)}`} />
        </div>
      </div>
    </div>);

  }
  function NodeCard({ n }) {
    const cpuPct = Number.isFinite(Number(n.cpu)) ? Math.max(0, Math.min(100, Number(n.cpu))) : 0;
    const memPct = Number.isFinite(Number(n.mem)) ? Math.max(0, Math.min(100, Number(n.mem))) : 0;
    const netMbps = Number.isFinite(Number(n.net)) ? Math.max(0, Number(n.net)) : 0;
    const netBarPct = Math.max(0, Math.min(100, netMbps * 2));
    const fmtPct = (v) => `${Number(v).toFixed(1)}%`;
    const fmtNet = (v) => `${Number(v).toFixed(1)} MB/s`;
    return (
      <div className="card" style={{ cursor: "pointer" }}>
      <div className="card-h">
        <h3 style={{ fontFamily: "var(--font-mono)" }}>{n.id}</h3>
        <span className={cx("pill", n.status === "ok" ? "ok" : "warn")}><span className="d" />{n.status}</span>
        <div className="spacer" />
        {n.here && <span className="chip" style={{ color: "var(--accent)", borderColor: "var(--accent-soft)" }}>· here</span>}
      </div>
      <div className="card-b">
        <div style={{ fontSize: 11.5, color: "var(--ink-3)", marginBottom: 10, fontFamily: "var(--font-mono)" }}>
          {n.role} · {n.os} · up {n.uptime}
        </div>
        <div className="meter"><span className="name">CPU</span><div className="prog"><i style={{ width: cpuPct + "%", background: cpuPct > 70 ? "var(--bad)" : "var(--accent)" }} /></div><span className="v">{fmtPct(cpuPct)}</span></div>
        <div className="meter" style={{ marginTop: 6 }}><span className="name">Memory</span><div className="prog"><i style={{ width: memPct + "%", background: memPct > 85 ? "var(--bad)" : "var(--accent)" }} /></div><span className="v">{fmtPct(memPct)}</span></div>
        <div className="meter" style={{ marginTop: 6 }}><span className="name">Net</span><div className="prog"><i style={{ width: netBarPct + "%", background: "var(--good)" }} /></div><span className="v">{fmtNet(netMbps)}</span></div>
        <div className="row" style={{ marginTop: 12, justifyContent: "space-between", fontFamily: "var(--font-mono)", fontSize: 10.5, color: "var(--ink-3)" }}>
          <span>{n.services} services</span>
          <span>disk {n.disk}</span>
          <span>open →</span>
        </div>
      </div>
    </div>);

  }
  function NodeActivityRow({ t, who, what }) {
    return (
      <div className="row" style={{ padding: "8px 16px", borderBottom: "1px solid var(--rule)", gap: 12 }}>
      <span style={{ fontFamily: "var(--font-mono)", fontSize: 10.5, color: "var(--ink-3)", width: 38 }}>{t}</span>
      <span className="chip" style={{ minWidth: 80, textAlign: "center" }}>{who}</span>
      <span style={{ fontSize: 12.5, color: "var(--ink-2)" }}>{what}</span>
    </div>);

  }

  /* ═════════ Docker (real inventory + safe controls) ═════════ */
  function Docker({ toast, live }) {
    const [tab, setTab] = useState("Containers");
    const [data, setData] = useState(null);
    const [images, setImages] = useState([]);
    const [loading, setLoading] = useState(true);
    const [imagesLoading, setImagesLoading] = useState(false);
    const [err, setErr] = useState("");
    const [busy, setBusy] = useState("");
    const [logs, setLogs] = useState({ name: "", text: "" });
    const [recs, setRecs] = useState([]);
    const [pullImage, setPullImage] = useState("");
    const [installForm, setInstallForm] = useState({
      name: "",
      image: "",
      ports: "",
      volumes: "",
      env: "",
      restart: "unless-stopped",
      network: "bridge",
      command: "",
    });
    const refreshDocker = async (silent = false) => {
      if (!silent) setLoading(true);
      setErr("");
      try {
        const d = await apiJson("/api/docker/containers", { cache: "no-store" });
        setData(d || {});
      } catch (e) {
        setErr(String(e && e.message || e || "Docker load failed"));
      } finally {
        setLoading(false);
      }
    };
    const refreshImages = async (silent = false) => {
      if (!silent) setImagesLoading(true);
      try {
        const d = await apiJson("/api/docker/images", { cache: "no-store" });
        setImages(Array.isArray((d || {}).images) ? d.images : []);
      } catch (e) {
        if (!silent) toast(`Docker images load failed: ${String(e && e.message || e)}`);
      } finally {
        if (!silent) setImagesLoading(false);
      }
    };
    useEffect(() => {
      let dead = false;
      const load = async (silent = false) => {
        if (!silent) setLoading(true);
        setErr("");
        try {
          const d = await apiJson("/api/docker/containers", { cache: "no-store" });
          if (!dead) setData(d || {});
        } catch (e) {
          if (!dead) setErr(String(e && e.message || e || "Docker load failed"));
        } finally {
          if (!dead) setLoading(false);
        }
      };
      load(false);
      const tk = setInterval(() => load(true), 6000);
      return () => { dead = true; clearInterval(tk); };
    }, []);
    useEffect(() => {
      refreshImages(false);
    }, []);
    useEffect(() => {
      let dead = false;
      apiJson("/api/docker/recommendations", { cache: "no-store" }).then((d) => {
        if (!dead) setRecs(Array.isArray((d || {}).items) ? d.items : []);
      }).catch(() => {});
      return () => { dead = true; };
    }, []);
    const runDocker = async (name, action) => {
      setBusy(`${name}:${action}`);
      try {
        const d = await apiJson("/api/docker/action", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name, action })
        });
        setData(d || {});
        toast(`Docker ${action} requested: ${name}`);
      } catch (e) {
        toast(`Docker ${action} failed: ${String(e && e.message || e)}`);
      } finally {
        setBusy("");
      }
    };
    const removeContainer = async (name) => {
      if (!name) return;
      if (!confirm(`Remove container ${name}?`)) return;
      setBusy(`rm:${name}`);
      try {
        const d = await apiJson("/api/docker/container/remove", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name, force: true }),
        });
        setData(d || {});
        toast(`Container removed: ${name}`);
      } catch (e) {
        toast(`Remove container failed: ${String(e && e.message || e)}`);
      } finally {
        setBusy("");
      }
    };
    const pullDockerImage = async (imageRef) => {
      const image = String(imageRef || pullImage || "").trim();
      if (!image) return;
      setBusy(`pull:${image}`);
      try {
        await apiJson("/api/docker/image/pull", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ image }),
        });
        toast(`Image pulled: ${image}`);
        setPullImage("");
        await refreshImages(true);
      } catch (e) {
        toast(`Pull failed: ${String(e && e.message || e)}`);
      } finally {
        setBusy("");
      }
    };
    const removeDockerImage = async (imageRef) => {
      const image = String(imageRef || "").trim();
      if (!image) return;
      if (!confirm(`Remove image ${image}?`)) return;
      setBusy(`rmi:${image}`);
      try {
        const d = await apiJson("/api/docker/image/remove", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ image, force: true }),
        });
        setImages(Array.isArray((d || {}).images) ? d.images : []);
        toast(`Image removed: ${image}`);
      } catch (e) {
        toast(`Remove image failed: ${String(e && e.message || e)}`);
      } finally {
        setBusy("");
      }
    };
    const createContainer = async () => {
      const name = String(installForm.name || "").trim();
      const image = String(installForm.image || "").trim();
      if (!name || !image) {
        toast("Container name and image are required");
        return;
      }
      setBusy(`create:${name}`);
      try {
        const body = {
          name,
          image,
          ports: String(installForm.ports || "").split("\n").map((x) => x.trim()).filter(Boolean),
          volumes: String(installForm.volumes || "").split("\n").map((x) => x.trim()).filter(Boolean),
          env: String(installForm.env || "").split("\n").map((x) => x.trim()).filter(Boolean),
          restart: String(installForm.restart || "unless-stopped"),
          network: String(installForm.network || "bridge"),
          command: String(installForm.command || "").trim(),
        };
        const d = await apiJson("/api/docker/container/create", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        setData(d || {});
        toast(`Container created: ${name}`);
        setTab("Containers");
      } catch (e) {
        toast(`Create container failed: ${String(e && e.message || e)}`);
      } finally {
        setBusy("");
      }
    };
    const fillInstallFromRec = (r) => {
      const safe = String(((r || {}).id || "container")).replace(/[^a-zA-Z0-9_.-]/g, "-");
      setInstallForm({
        name: safe,
        image: String((r && r.image) || ""),
        ports: Array.isArray(r && r.ports) ? r.ports.map((p) => `${p}:${p}`).join("\n") : "",
        volumes: Array.isArray(r && r.volumes) ? r.volumes.join("\n") : "",
        env: "",
        restart: "unless-stopped",
        network: "bridge",
        command: "",
      });
      setPullImage(String((r && r.image) || ""));
      setTab("Install");
    };
    const showLogs = async (name) => {
      setTab("Logs");
      setLogs({ name, text: "Loading logs..." });
      try {
        const d = await apiJson(`/api/docker/logs?name=${encodeURIComponent(name)}&tail=180`, { cache: "no-store" });
        setLogs({ name, text: String((d && d.logs) || "(empty logs)") });
      } catch (e) {
        setLogs({ name, text: `Log load failed: ${String(e && e.message || e)}` });
      }
    };
    const summary = (data && data.summary) || (live && live.docker) || {};
    const containers = Array.isArray(data && data.containers) ? data.containers : [];
    const available = data ? !!data.available : !!summary.available;
    const disabled = data ? !!data.disabled : !!summary.disabled;
    const summaryText = disabled
      ? "Docker module disabled."
      : available
        ? `${Number(summary.running || 0)} running · ${Number(summary.total || 0)} total · ${Number(summary.images || 0)} images.`
        : (err || String(summary.error || "Docker is not available on this host."));
    return (
      <div className="col">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div>
          <h1 className="h1">Docker</h1>
          <p className="sub">{summaryText}</p>
        </div>
        <div className="row">
          <button className="btn" onClick={() => refreshDocker(false)}>{Ic.restart}<span style={{ marginLeft: 4 }}>Refresh</span></button>
        </div>
      </div>
      <div className="card">
        <div className="tablist" style={{ padding: "0 12px" }}>
          {["Containers", "Install", "Recommended", "Images", "Logs"].map((t) =>
            <div key={t} className={cx("tab", tab === t && "on")} onClick={() => setTab(t)}>{t}</div>
            )}
        </div>
        {tab === "Containers" &&
          (loading ? <div className="card-b" style={{ color: "var(--ink-3)" }}>Loading Docker containers...</div> :
          err ? <div className="card-b" style={{ color: "var(--bad)" }}>{err}</div> :
          !available ? <div className="card-b" style={{ color: "var(--ink-3)" }}>{summaryText}</div> :
          <table className="tbl docker-table">
            <thead><tr>
              <th>Name</th><th>Image</th><th>Status</th>
              <th style={{ textAlign: "right" }}>CPU</th>
              <th style={{ textAlign: "right" }}>Memory</th>
              <th>Ports</th><th>Uptime</th><th>Linked</th><th></th>
            </tr></thead>
            <tbody>
              {containers.map((c) =>
              <tr key={c.name}>
                  <td className="k">{c.name}</td>
                  <td style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--ink-3)" }}>{c.image}</td>
                  <td>
                    {c.running && <span className="pill ok"><span className="d" />up</span>}
                    {!c.running && <span className="pill idle"><span className="d" />{String(c.state || "stopped")}</span>}
                  </td>
                  <td style={{ textAlign: "right", fontFamily: "var(--font-mono)", fontSize: 11 }}>{Number(c.cpu_pct || 0).toFixed(1)}%</td>
                  <td style={{ textAlign: "right", fontFamily: "var(--font-mono)", fontSize: 11 }}>{String(c.mem_usage || "-")}</td>
                  <td style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--ink-3)" }}>{c.ports}</td>
                  <td style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--ink-3)" }}>{c.uptime}</td>
                  <td>
                    <div className="row" style={{ gap: 4, flexWrap: "wrap" }}>
                      {(Array.isArray(c.roles) && c.roles.length ? c.roles : ["container"]).map((r) => <span key={r} className="chip">{r}</span>)}
                    </div>
                  </td>
                  <td>
                    <div className="row" style={{ gap: 4, justifyContent: "flex-end" }}>
                      <button className="btn sm icon" title="Restart" disabled={!!busy} onClick={() => runDocker(c.name, "restart")}>{Ic.restart}</button>
                      <button className="btn sm icon" title={c.running ? "Stop" : "Start"} disabled={!!busy} onClick={() => runDocker(c.name, c.running ? "stop" : "start")}>{c.running ? Ic.stop : Ic.play}</button>
                      <button className="btn sm icon" title="Logs" onClick={() => showLogs(c.name)}>{Ic.term}</button>
                      <button className="btn sm danger" title="Remove" disabled={!!busy} onClick={() => removeContainer(c.name)}>remove</button>
                    </div>
                  </td>
                </tr>
              )}
              {!containers.length && <tr><td colSpan="9" style={{ color: "var(--ink-3)", textAlign: "center", padding: 24 }}>No Docker containers found.</td></tr>}
            </tbody>
          </table>)
          }
        {tab === "Logs" &&
          <div className="card-b">
            <div className="row" style={{ justifyContent: "space-between", marginBottom: 10 }}>
              <b>{logs.name ? `Logs · ${logs.name}` : "Select a container log"}</b>
              {logs.name && <button className="btn sm" onClick={() => showLogs(logs.name)}>refresh logs</button>}
            </div>
            <pre className="docker-log">{logs.text || "Use the terminal icon in Containers to load recent logs."}</pre>
          </div>
          }
        {tab === "Install" &&
          <div className="card-b col" style={{ gap: 10 }}>
            <div className="row" style={{ gap: 8 }}>
              <input className="input" value={pullImage} onChange={(e) => setPullImage(e.target.value)} placeholder="Image to pull, e.g. lscr.io/linuxserver/deluge:latest" />
              <button className="btn" disabled={!!busy} onClick={() => pullDockerImage("")}>Pull image</button>
            </div>
            <div className="grid-2">
              <input className="input" value={installForm.name} onChange={(e) => setInstallForm((p) => ({ ...p, name: e.target.value }))} placeholder="Container name (required)" />
              <input className="input" value={installForm.image} onChange={(e) => setInstallForm((p) => ({ ...p, image: e.target.value }))} placeholder="Image reference (required)" />
            </div>
            <div className="grid-2">
              <textarea className="input" style={{ minHeight: 90 }} value={installForm.ports} onChange={(e) => setInstallForm((p) => ({ ...p, ports: e.target.value }))} placeholder={"Ports (one per line)\n8080:8080\n6881:6881/udp"} />
              <textarea className="input" style={{ minHeight: 90 }} value={installForm.volumes} onChange={(e) => setInstallForm((p) => ({ ...p, volumes: e.target.value }))} placeholder={"Volumes (one per line)\n/srv/Storage/BT:/downloads\n/srv/Storage/AppData/app:/config"} />
            </div>
            <textarea className="input" style={{ minHeight: 80 }} value={installForm.env} onChange={(e) => setInstallForm((p) => ({ ...p, env: e.target.value }))} placeholder={"Environment variables (one per line)\nPUID=1000\nPGID=1000"} />
            <div className="grid-2">
              <select className="input" value={installForm.restart} onChange={(e) => setInstallForm((p) => ({ ...p, restart: e.target.value }))}>
                <option value="unless-stopped">Restart: unless-stopped</option>
                <option value="always">Restart: always</option>
                <option value="on-failure">Restart: on-failure</option>
                <option value="no">Restart: no</option>
              </select>
              <input className="input" value={installForm.network} onChange={(e) => setInstallForm((p) => ({ ...p, network: e.target.value }))} placeholder="Network (default bridge)" />
            </div>
            <input className="input" value={installForm.command} onChange={(e) => setInstallForm((p) => ({ ...p, command: e.target.value }))} placeholder="Optional command override" />
            <div className="row">
              <button className="btn primary" disabled={!!busy} onClick={createContainer}>Create container</button>
            </div>
          </div>
          }
        {tab === "Recommended" &&
          <div className="card-b">
            <div className="docker-rec-grid">
              {recs.map((r) =>
                <div key={r.id || r.name} className="docker-rec-card">
                  <div className="row" style={{ justifyContent: "space-between", gap: 8 }}>
                    <b>{r.name}</b>
                    <span className="chip">{r.category || "nas"}</span>
                  </div>
                  <div className="docker-rec-image">{r.image}</div>
                  <p>{r.notes}</p>
                  <div className="docker-rec-meta">
                    <span>Ports: {(Array.isArray(r.ports) && r.ports.length) ? r.ports.join(", ") : "-"}</span>
                    <span>Arch: {(Array.isArray(r.arch) && r.arch.length) ? r.arch.join(", ") : "amd64"}</span>
                    <span>Risk: {r.risk || "lan"}</span>
                  </div>
                  <details>
                    <summary>Suggested volumes</summary>
                    <code>{(Array.isArray(r.volumes) && r.volumes.length) ? r.volumes.join("\n") : "No volume suggestion"}</code>
                  </details>
                  <div className="row" style={{ marginTop: 10, gap: 8 }}>
                    <button className="btn sm" onClick={() => fillInstallFromRec(r)}>Use in Install</button>
                    <button className="btn sm" disabled={!!busy} onClick={() => pullDockerImage(r.image)}>Pull</button>
                  </div>
                </div>
              )}
              {!recs.length && <div style={{ color: "var(--ink-3)" }}>No recommendations loaded.</div>}
            </div>
          </div>
          }
        {tab === "Images" &&
          <div className="card-b">
            {imagesLoading && <div style={{ color: "var(--ink-3)", marginBottom: 10 }}>Loading images...</div>}
            <div className="row" style={{ justifyContent: "space-between", marginBottom: 10 }}>
              <b>Local images</b>
              <button className="btn sm" onClick={() => refreshImages(false)}>Refresh images</button>
            </div>
            <table className="tbl docker-table">
              <thead><tr><th>Image</th><th>Size</th><th>Created</th><th></th></tr></thead>
              <tbody>
                {images.map((im) =>
                  <tr key={im.id || im.ref}>
                    <td className="k">{im.ref || im.id}</td>
                    <td>{im.size || "-"}</td>
                    <td>{im.created || "-"}</td>
                    <td style={{ textAlign: "right" }}>
                      <button className="btn sm danger" disabled={!!busy} onClick={() => removeDockerImage(im.ref || im.id)}>remove</button>
                    </td>
                  </tr>
                )}
                {!images.length && <tr><td colSpan="4" style={{ color: "var(--ink-3)", textAlign: "center", padding: 20 }}>No images found.</td></tr>}
              </tbody>
            </table>
          </div>
        }
      </div>
    </div>);

  }

  /* ═════════ Web terminal (variant A — single shell + keys) ═════════ */
  function Terminal({ toast }) {
    const [tab, setTab] = useState("term");
    const [draftCommand, setDraftCommand] = useState("");
    const [shellSessionId, setShellSessionId] = useState("");
    const [shellLines, setShellLines] = useState([]);
    return (
      <div className="col">
      <div>
        <h1 className="h1">Web terminal</h1>
        <p className="sub">Live SSH terminal integrated with AfterClaw backend.</p>
      </div>
      <div className="card">
        <div className="tablist" style={{ padding: "0 12px" }}>
          <div className={cx("tab", tab === "term" && "on")} onClick={() => setTab("term")}>Shell</div>
          <div className={cx("tab", tab === "keys" && "on")} onClick={() => setTab("keys")}>SSH keys</div>
          <div className={cx("tab", tab === "history" && "on")} onClick={() => setTab("history")}>History</div>
        </div>
        {tab === "term" && <ShellPanel toast={toast} draftCommand={draftCommand} onDraftCommandConsumed={() => setDraftCommand("")} sessionId={shellSessionId} setSessionId={setShellSessionId} lines={shellLines} setLines={setShellLines} />}
        {tab === "keys" && <KeysPanel toast={toast} />}
        {tab === "history" && <HistoryPanel toast={toast} onRun={(cmd) => {setDraftCommand(String(cmd || ""));setTab("term");}} />}
      </div>
    </div>);

  }
  function ShellPanel({ toast, draftCommand, onDraftCommandConsumed, sessionId, setSessionId, lines, setLines }) {
    const [status, setStatus] = useState("Connecting...");
    const [val, setVal] = useState("");
    const inputRef = useRef();
    const termRef = useRef();
    const timerRef = useRef(null);
    const closedRef = useRef(false);

    const pushOutput = (txt) => {
      const s = String(txt || "");
      if (!s) return;
      setLines((prev) => [...prev, { t: "out", v: s }]);
    };

    const scrollToBottom = () => {
      const el = termRef.current;
      if (!el) return;
      try {
        el.scrollTop = el.scrollHeight;
      } catch (_) {}
    };

    const stopPolling = () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    };

    const pollRead = async (sid) => {
      if (!sid || closedRef.current) return;
      try {
        const r = await fetch("/api/terminal/read", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ session_id: sid, max_bytes: 65536 })
        });
        const d = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(d.error || `HTTP ${r.status}`);
        if (d.output) pushOutput(d.output);
        if (d.alive === false) {
          setStatus(`Session ended${typeof d.exit_code === "number" ? ` (${d.exit_code})` : ""}`);
          setSessionId("");
          stopPolling();
        }
      } catch (e) {
        const msg = String(e?.message || e);
        setStatus(`Read failed: ${msg}`);
        if (msg.includes("不存在") || msg.includes("已结束")) {
          setSessionId("");
          stopPolling();
        }
      }
    };

    const sendCommand = async (cmd) => {
      const sid = sessionId;
      const text = String(cmd || "").trim();
      if (!sid || !text) return;
      setLines((prev) => [...prev, { t: "out", v: `$ ${text}\n` }]);
      try {
        const r = await fetch("/api/terminal/write", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ session_id: sid, data: `${text}\n` })
        });
        const d = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(d.error || `HTTP ${r.status}`);
      } catch (e) {
        setStatus(`Write failed: ${String(e?.message || e)}`);
      }
    };

    useEffect(() => {
      let alive = true;
      closedRef.current = false;
      if (sessionId) {
        setStatus("Connected (resumed)");
        timerRef.current = setInterval(() => {pollRead(sessionId);}, 350);
        setTimeout(() => pollRead(sessionId), 80);
        return () => {
          alive = false;
          closedRef.current = true;
          stopPolling();
        };
      }
      (async () => {
        try {
          const r = await fetch("/api/terminal/start", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ cols: 120, rows: 30 })
          });
          const d = await r.json().catch(() => ({}));
          if (!r.ok) throw new Error(d.error || `HTTP ${r.status}`);
          if (!alive) return;
          const sid = String(d.session_id || "");
          if (!sid) throw new Error("Invalid session_id");
          setLines([]);
          setSessionId(sid);
          setStatus(`Connected · ${d?.meta?.display || "terminal"}`);
          timerRef.current = setInterval(() => {pollRead(sid);}, 350);
          setTimeout(() => pollRead(sid), 80);
        } catch (e) {
          if (!alive) return;
          setStatus(`Connect failed: ${String(e?.message || e)}`);
        }
      })();
      return () => {
        alive = false;
        closedRef.current = true;
        stopPolling();
      };
    }, [sessionId, setSessionId]);

    useEffect(() => {
      if (!sessionId || !draftCommand) return;
      setVal(String(draftCommand));
      onDraftCommandConsumed?.();
      inputRef.current?.focus();
    }, [sessionId, draftCommand, onDraftCommandConsumed]);

    useEffect(() => {inputRef.current?.focus();}, [sessionId]);
    useEffect(() => {scrollToBottom();}, [lines]);

    const submit = async (e) => {
      e?.preventDefault?.();
      const text = String(val || "").trim();
      if (!text) return;
      setVal("");
      await sendCommand(text);
      setTimeout(scrollToBottom, 10);
    };

    return (
      <div className="card-b">
      <div className="row" style={{ justifyContent: "space-between", marginBottom: 8 }}>
        <span className="meta" style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--ink-3)" }}>
          {status}
        </span>
      </div>
      <div ref={termRef} className="term term-shell-fit">
        {lines.length === 0 && <div className="dim">No output yet.</div>}
        {lines.map((l, i) => <div key={i} style={{ whiteSpace: "pre-wrap" }}>{l.v}</div>)}
        <form onSubmit={submit} style={{ display: "flex", alignItems: "center" }}>
          <span><span className="acc">$</span><span className="dim"> </span></span>
          <input ref={inputRef} value={val} onChange={(e) => setVal(e.target.value)}
            style={{ flex: 1, background: "transparent", border: 0, outline: 0, font: "inherit", color: "var(--ink)" }} />
        </form>
      </div>
      <div style={{ marginTop: 8, fontFamily: "var(--font-mono)", fontSize: 10.5, color: "var(--ink-3)" }}>
        Commands are executed on the live backend terminal session.
      </div>
    </div>);

  }
  function KeysPanel({ toast }) {
    const [meta, setMeta] = useState(null);
    const [err, setErr] = useState("");
    const [loading, setLoading] = useState(true);
    const [sessions, setSessions] = useState([]);
    const keyFiles = meta?.key_files || [];

    const loadAll = async () => {
      setLoading(true);
      try {
        setErr("");
        const [baseResp, sessResp] = await Promise.all([
        fetch("/api/base", { cache: "no-store" }),
        fetch("/api/terminal/sessions", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" })]);
        const baseData = await baseResp.json().catch(() => ({}));
        const sessData = await sessResp.json().catch(() => ({}));
        if (!baseResp.ok) throw new Error(baseData.error || `HTTP ${baseResp.status}`);
        if (!sessResp.ok) throw new Error(sessData.error || `HTTP ${sessResp.status}`);
        setMeta(baseData?.terminal || {});
        setSessions(Array.isArray(sessData?.items) ? sessData.items : []);
      } catch (e) {
        setErr(String(e?.message || e || "load failed"));
      } finally {
        setLoading(false);
      }
    };

    useEffect(() => {loadAll();}, []);

    if (loading) {
      return <div className="card-b" style={{ color: "var(--ink-3)" }}>Loading terminal data...</div>;
    }
    if (err) {
      return <div className="card-b" style={{ color: "var(--danger)" }}>Failed to load terminal data: {err}</div>;
    }

    return (
      <div className="col" style={{ gap: 10 }}>
      <table className="tbl">
      <thead><tr><th>File name</th><th>Configured</th><th>Auth</th><th></th></tr></thead>
      <tbody>
        {keyFiles.length === 0 &&
          <tr><td colSpan={4} style={{ color: "var(--ink-3)" }}>No uploaded key files in terminal_keys.</td></tr>
        }
        {keyFiles.map((name) =>
          <tr key={name}>
            <td className="k">{name}</td>
            <td style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--ink-3)" }}>
              {meta?.key_file === name ? "active in config" : "-"}
            </td>
            <td style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--ink-3)" }}>{meta?.auth_mode || "-"}</td>
            <td><div className="row" style={{ justifyContent: "flex-end", gap: 4 }}>
              <button className="btn sm" onClick={async () => {
                try {
                  await navigator.clipboard.writeText(name);
                  toast("Key filename copied");
                } catch {
                  toast("Copy failed");
                }
              }}>{Ic.copy}<span style={{ marginLeft: 4 }}>copy name</span></button>
            </div></td>
          </tr>
          )}
      </tbody>
    </table>
      <div className="row" style={{ justifyContent: "space-between", marginTop: 4 }}>
        <div className="meta" style={{ fontFamily: "var(--font-mono)", color: "var(--ink-3)" }}>Login sessions: {sessions.length}</div>
        <button className="btn sm" onClick={loadAll}>refresh</button>
      </div>
      <table className="tbl">
        <thead><tr><th>Session</th><th>Client</th><th>Target</th><th>Last active</th><th></th></tr></thead>
        <tbody>
          {sessions.length === 0 && <tr><td colSpan={5} style={{ color: "var(--ink-3)" }}>No active terminal sessions.</td></tr>}
          {sessions.map((s) =>
            <tr key={s.session_id}>
              <td className="k" style={{ fontFamily: "var(--font-mono)", fontSize: 11 }}>{String(s.session_id || "").slice(0, 12)}...</td>
              <td style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--ink-3)" }}>{s.client_ip || "-"}</td>
              <td style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--ink-3)" }}>{s.target || "-"}</td>
              <td style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--ink-3)" }}>{new Date((s.last_active || 0) * 1000).toLocaleString()}</td>
              <td style={{ textAlign: "right" }}>
                <button className="btn sm danger" onClick={async () => {
                  try {
                    const r = await fetch("/api/terminal/revoke", {
                      method: "POST",
                      headers: { "Content-Type": "application/json" },
                      body: JSON.stringify({ session_id: s.session_id })
                    });
                    const d = await r.json().catch(() => ({}));
                    if (!r.ok) throw new Error(d.error || `HTTP ${r.status}`);
                    toast("Session revoked");
                    await loadAll();
                  } catch (e) {
                    toast(`Revoke failed: ${String(e?.message || e)}`);
                  }
                }}>revoke</button>
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>);

  }
  function HistoryPanel({ toast, onRun }) {
    const [items, setItems] = useState([]);
    const [err, setErr] = useState("");
    const [loading, setLoading] = useState(true);
    const [keyword, setKeyword] = useState("");
    const [clientIp, setClientIp] = useState("");
    const [sessionId, setSessionId] = useState("");

    const loadHistory = async (opts = {}) => {
      setLoading(true);
      try {
        setErr("");
        const payload = {
          limit: 300,
          keyword,
          client_ip: clientIp,
          session_id: sessionId,
          ...(opts || {})
        };
        const r = await fetch("/api/terminal/history", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        const d = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(d.error || `HTTP ${r.status}`);
        setItems(Array.isArray(d.items) ? d.items : []);
      } catch (e) {
        setErr(String(e?.message || e || "load failed"));
      } finally {
        setLoading(false);
      }
    };
    useEffect(() => {loadHistory();}, []);

    if (loading) {
      return <div className="card-b" style={{ color: "var(--ink-3)" }}>Loading command history...</div>;
    }
    if (err) {
      return <div className="card-b" style={{ color: "var(--danger)" }}>Failed to load history: {err}</div>;
    }

    return (
      <div className="col" style={{ gap: 10 }}>
      <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
        <input
          className="in"
          style={{ maxWidth: 240 }}
          placeholder="keyword"
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
        />
        <input
          className="in"
          style={{ maxWidth: 180 }}
          placeholder="client ip"
          value={clientIp}
          onChange={(e) => setClientIp(e.target.value)}
        />
        <input
          className="in"
          style={{ maxWidth: 240 }}
          placeholder="session id"
          value={sessionId}
          onChange={(e) => setSessionId(e.target.value)}
        />
        <button className="btn sm" onClick={() => loadHistory()}>filter</button>
        <button className="btn sm" onClick={() => {setKeyword("");setClientIp("");setSessionId("");loadHistory({ keyword: "", client_ip: "", session_id: "" });}}>reset</button>
        <button className="btn sm danger" onClick={async () => {
          try {
            const r = await fetch("/api/terminal/history/clear", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: "{}"
            });
            const d = await r.json().catch(() => ({}));
            if (!r.ok) throw new Error(d.error || `HTTP ${r.status}`);
            toast(`History cleared (${d.removed || 0})`);
            await loadHistory({ keyword: "", client_ip: "", session_id: "" });
          } catch (e) {
            toast(`Clear failed: ${String(e?.message || e)}`);
          }
        }}>clear history</button>
      </div>
      <table className="tbl">
      <thead><tr><th style={{ width: 170 }}>When</th><th>Command</th><th style={{ width: 120 }}>Client</th><th></th></tr></thead>
      <tbody>{items.length === 0 && <tr><td colSpan={4} style={{ color: "var(--ink-3)" }}>No command history yet.</td></tr>}
        {items.map((it, i) =>
          <tr key={`${it.session_id || "s"}-${it.ts || i}-${i}`}>
          <td style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--ink-3)" }}>{new Date((it.ts || 0) * 1000).toLocaleString()}</td>
          <td className="k">{it.command || ""}</td>
          <td style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--ink-3)" }}>{it.client_ip || "-"}</td>
          <td style={{ textAlign: "right" }}><button className="btn sm" onClick={() => {onRun?.(it.command || "");toast("Command staged in shell");}}>re-run</button></td>
        </tr>
          )}</tbody>
    </table>
    </div>);
  }

  /* ═════════ Services (variant A — service cards) ═════════ */
  function Services({ services, toggleService, goto }) {
    return (
      <div className="col">
      <div>
        <h1 className="h1">Services</h1>
        <p className="sub">Background services running on nas-01.</p>
      </div>
      <div className="grid-3">
        {services.map((s) => <ServiceCard key={s.id} s={s} toggle={() => toggleService(s.id)} goto={goto} />)}
      </div>
    </div>);

  }
  function ServiceCard({ s, toggle, goto }) {
    return (
      <div className="card">
      <div className="card-h">
        <h3>{s.name}</h3>
        <span className={cx("pill", s.on ? s.warn ? "warn" : "ok" : "idle")}><span className="d" />{s.on ? s.warn ? "warn" : "running" : "stopped"}</span>
        <div className="spacer" />
        {s.readOnly ? <button className="btn sm" onClick={() => goto && goto(s.target || s.id)}>open</button> : <div className={cx("tog", s.on && "on")} onClick={toggle} />}
      </div>
      <div className="card-b">
        <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--ink-3)", marginBottom: 8 }}>{s.detail}</div>
        <div className="row" style={{ justifyContent: "space-between" }}>
          <span className="chip">{s.kind}</span>
          {s.exposed && <span className="pill public" title="Reachable from the internet"><span className="d" />public</span>}
          {!s.exposed && <span className="pill lan"><span className="d" />LAN</span>}
        </div>
        <div className="row" style={{ marginTop: 12, gap: 4 }}>
          <button className="btn sm" onClick={s.readOnly ? () => goto && goto(s.target || s.id) : undefined}>{Ic.restart}<span style={{ marginLeft: 4 }}>{s.readOnly ? "open" : "restart"}</span></button>
          <button className="btn sm" onClick={s.readOnly ? () => goto && goto(s.target || s.id) : undefined}>{Ic.term}<span style={{ marginLeft: 4 }}>logs</span></button>
          <button className="btn sm ghost">configure</button>
        </div>
      </div>
    </div>);

  }

  /* ═════════ ShareClip (variant A — chat timeline) ═════════ */
  function ShareClip({ toast }) {
    const [items, setItems] = useState([]);
    const [v, setV] = useState("");
    const [sending, setSending] = useState(false);
    const [previewImage, setPreviewImage] = useState(null);
    const [filterType, setFilterType] = useState("all");
    const [query, setQuery] = useState("");
    const [timeRange, setTimeRange] = useState("all");
    const [sortBy, setSortBy] = useState("newest");
    const [selectedIds, setSelectedIds] = useState([]);
    const fileRef = useRef(null);
    const attachmentRef = useRef(null);
    const sendFile = async (file, fieldName = "image") => {
      if (!file || sending) return;
      setSending(true);
      try {
        const fd = new FormData();
        fd.append("id", "pub");
        fd.append(fieldName, file, file.name || "upload.bin");
        const r = await fetch("/api/clip", { method: "POST", body: fd });
        const d = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(d.error || "Upload failed");
        toast(fieldName === "image" ? "Image uploaded" : "File uploaded");
        await loadHistory();
      } catch (err) {
        toast(`Upload failed: ${err.message || err}`);
      } finally {
        setSending(false);
        if (fileRef.current) fileRef.current.value = "";
        if (attachmentRef.current) attachmentRef.current.value = "";
      }
    };
    const loadHistory = async () => {
      const d = await apiJson("/api/history?id=pub&limit=200");
      const rows = Array.isArray(d.items) ? d.items : [];
      setItems(rows.map((it) => ({
        id: it.id,
        who: "shareclip",
        type: String(it.type || "text"),
        updatedAt: String(it.updated_at || ""),
        t: String(it.updated_at || "").replace("T", " ").slice(5, 16),
        text: it.type === "text" ? String(it.text || "") : "",
        attach: it.type === "image" ? String(it.image_filename || "image") : it.type === "file" ? String(it.file_name || it.file_filename || "file") : "",
        imageUrl: it.type === "image" ? String(it.image_url || "") : "",
        fileUrl: it.type === "file" ? String(it.file_url || "") : "",
        mine: false,
      })));
    };
    const assetUrl = (m) => String((m && (m.imageUrl || m.fileUrl || m.url)) || "").trim();
    const downloadAsset = (m) => {
      const u = assetUrl(m);
      if (!u) return;
      const a = document.createElement("a");
      a.href = u;
      a.download = String((m && m.attach) || "image");
      a.target = "_blank";
      a.rel = "noopener";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    };
    const copyImageToClipboard = async (m) => {
      const u = assetUrl(m);
      if (!u) return;
      try {
        const r = await fetch(u, { cache: "no-store" });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const blob = await r.blob();
        if (!navigator.clipboard || typeof window.ClipboardItem === "undefined") {
          await copyText(new URL(u, window.location.origin).href, "Image clipboard unavailable; link copied");
          return;
        }
        await navigator.clipboard.write([new window.ClipboardItem({ [blob.type || "image/png"]: blob })]);
        toast("Image copied");
      } catch (err) {
        toast(`Copy failed: ${err.message || err}`);
      }
    };
    const copyText = async (text, label = "Copied") => {
      let ta = null;
      try {
        const value = String(text || "");
        if (navigator.clipboard && navigator.clipboard.writeText) {
          await navigator.clipboard.writeText(value);
        } else {
          ta = document.createElement("textarea");
          ta.value = value;
          ta.style.position = "fixed";
          ta.style.left = "-9999px";
          document.body.appendChild(ta);
          ta.select();
          if (!document.execCommand("copy")) throw new Error("Clipboard not available");
        }
        toast(label);
      } catch (err) {
        toast(`Copy failed: ${err.message || err}`);
      } finally {
        if (ta && ta.parentNode) ta.parentNode.removeChild(ta);
      }
    };
    const copyAssetLink = (m) => {
      const u = assetUrl(m);
      if (!u) return;
      copyText(new URL(u, window.location.origin).href, "Link copied");
    };
    const recordCount = items.length;
    const lastSynced = recordCount > 0 ? String(items[0]?.t || "-") : "none";
    const typeCount = useMemo(() => {
      let text = 0;
      let image = 0;
      let file = 0;
      for (const it of items) {
        if (it.type === "image") image += 1; else
        if (it.type === "file") file += 1; else text += 1;
      }
      return { text, image, file };
    }, [items]);
    const filteredItems = useMemo(() => {
      const q = String(query || "").trim().toLowerCase();
      const now = Date.now();
      const minMs = timeRange === "today" ? now - 24 * 3600 * 1000 :
        timeRange === "week" ? now - 7 * 24 * 3600 * 1000 :
        timeRange === "month" ? now - 30 * 24 * 3600 * 1000 : 0;
      const rows = items.filter((it) => {
        if (filterType !== "all" && it.type !== filterType) return false;
        if (minMs && new Date(it.updatedAt).getTime() < minMs) return false;
        if (!q) return true;
        return `${it.text} ${it.attach} ${it.id} ${it.type}`.toLowerCase().includes(q);
      });
      rows.sort((a, b) => {
        if (sortBy === "oldest") return String(a.updatedAt).localeCompare(String(b.updatedAt));
        if (sortBy === "name") return String(a.attach || a.text).localeCompare(String(b.attach || b.text));
        if (sortBy === "type") return String(a.type).localeCompare(String(b.type)) || String(b.updatedAt).localeCompare(String(a.updatedAt));
        return String(b.updatedAt).localeCompare(String(a.updatedAt));
      });
      return rows;
    }, [items, filterType, query, timeRange, sortBy]);
    const selectedSet = useMemo(() => new Set(selectedIds), [selectedIds]);
    const selectedCount = selectedIds.length;
    useEffect(() => {
      const all = new Set(items.map((it) => String(it.id || "")));
      setSelectedIds((prev) => prev.filter((id) => all.has(String(id))));
    }, [items]);
    const toggleSelect = (id) => {
      const key = String(id || "");
      if (!key) return;
      setSelectedIds((prev) => prev.includes(key) ? prev.filter((x) => x !== key) : [...prev, key]);
    };
    const selectAllFiltered = () => {
      const keys = filteredItems.map((it) => String(it.id || "")).filter(Boolean);
      setSelectedIds(Array.from(new Set(keys)));
    };
    const clearSelected = () => setSelectedIds([]);
    const deleteSelected = async () => {
      if (!selectedIds.length) return;
      if (!confirm(`Delete ${selectedIds.length} selected record(s)?`)) return;
      try {
        const d = await apiJson("/api/history/bulk-delete", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ id: "pub", record_ids: selectedIds }),
        });
        toast(`Deleted ${Array.isArray(d.deleted_ids) ? d.deleted_ids.length : selectedIds.length} record(s)`);
        setSelectedIds([]);
        await loadHistory();
      } catch (err) {
        toast(`Bulk delete failed: ${err.message || err}`);
      }
    };
    useEffect(() => {
      let dead = false;
      const run = async () => {
        try {
          await loadHistory();
        } catch (e) {
          if (!dead) toast(`ShareClip load failed: ${e.message || e}`);
        }
      };
      run();
      const tk = setInterval(run, 3000);
      return () => {
        dead = true;
        clearInterval(tk);
      };
    }, []);
    const send = (e) => {
      e.preventDefault();
      const tx = String(v || "").trim();
      if (!tx || sending) return;
      setSending(true);
      const fd = new FormData();
      fd.append("id", "pub");
      fd.append("text", tx);
      fetch("/api/clip", { method: "POST", body: fd }).then(async (r) => {
        const d = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(d.error || "Share failed");
        setV("");
        toast("Shared");
        await loadHistory();
      }).catch((err) => {
        toast(`Share failed: ${err.message || err}`);
      }).finally(() => setSending(false));
    };
    const onPickFile = (e) => {
      const f = e.target && e.target.files && e.target.files[0];
      if (f) sendFile(f, "image");
    };
    const onPickAttachment = (e) => {
      const f = e.target && e.target.files && e.target.files[0];
      if (f) sendFile(f, "file");
    };
    const onDropFile = (e) => {
      e.preventDefault();
      const f = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
      if (f) sendFile(f, String(f.type || "").startsWith("image/") ? "image" : "file");
    };
    return (
      <div className="col">
      <div>
        <h1 className="h1">ShareClip</h1>
        <p className="sub">Searchable LAN clipboard for text, images and shared files.</p>
      </div>
      <div className="shareclip-layout">
        <aside className="card" style={{ padding: "10px 10px 12px" }}>
          <div style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--ink-2)", marginBottom: 8 }}>ShareClip Filters</div>
          <input className="input" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search text, filename or ID" />
          <div className="shareclip-selectors">
            <select className="input" value={timeRange} onChange={(e) => setTimeRange(e.target.value)}>
              <option value="all">Any time</option>
              <option value="today">Last 24 hours</option>
              <option value="week">Last 7 days</option>
              <option value="month">Last 30 days</option>
            </select>
            <select className="input" value={sortBy} onChange={(e) => setSortBy(e.target.value)}>
              <option value="newest">Newest first</option>
              <option value="oldest">Oldest first</option>
              <option value="name">Name / content</option>
              <option value="type">Type</option>
            </select>
          </div>
          <div className="col" style={{ gap: 8 }}>
            <button className={cx("btn sm", filterType === "all" && "primary")} onClick={() => setFilterType("all")}>All · {recordCount}</button>
            <button className={cx("btn sm", filterType === "text" && "primary")} onClick={() => setFilterType("text")}>Text · {typeCount.text}</button>
            <button className={cx("btn sm", filterType === "image" && "primary")} onClick={() => setFilterType("image")}>Image · {typeCount.image}</button>
            <button className={cx("btn sm", filterType === "file" && "primary")} onClick={() => setFilterType("file")}>File · {typeCount.file}</button>
          </div>
          <div style={{ marginTop: 12, paddingTop: 10, borderTop: "1px solid var(--rule)" }}>
            <div className="meta" style={{ marginBottom: 8 }}>Selection: {selectedCount}</div>
            <div className="row" style={{ gap: 6, flexWrap: "wrap" }}>
              <button className="btn sm" onClick={selectAllFiltered}>Select all</button>
              <button className="btn sm" onClick={clearSelected}>Clear</button>
              <button className="btn sm danger" disabled={!selectedCount} onClick={deleteSelected}>Delete selected</button>
            </div>
          </div>
        </aside>
        <div
          className="card"
          onDragOver={(e) => e.preventDefault()}
          onDrop={onDropFile}
          style={{ display: "flex", flexDirection: "column", maxHeight: 760 }}>
          <div className="card-h">
            <h3>Public ShareClip (pub)</h3>
            <span className="meta">{recordCount} records · filtered {filteredItems.length} · last update {lastSynced}</span>
            <div className="spacer" />
            <button className="btn sm" onClick={() => toast("Profile ID: pub")}>Profile info</button>
          </div>
          <div style={{ padding: "16px 16px 8px", overflowY: "auto", flex: 1, display: "flex", flexDirection: "column", gap: 12, minHeight: 360 }}>
          {!filteredItems.length && <div style={{ color: "var(--ink-3)", fontSize: 12 }}>No records for this filter.</div>}
          {filteredItems.map((m, i) =>
            <div key={m.id || i} style={{ display: "flex", flexDirection: "column", alignItems: m.mine ? "flex-end" : "flex-start", gap: 4 }}>
              <div className="row" style={{ gap: 6, fontSize: 11.5, color: "var(--ink-3)", fontFamily: "var(--font-mono)" }}>
                <input type="checkbox" checked={selectedSet.has(String(m.id || ""))} onChange={() => toggleSelect(m.id)} />
                <span style={{ color: "var(--ink-2)", fontWeight: 600 }}>{m.who}</span>
                <span>· {m.t}</span>
                <span className="chip">{m.type}</span>
              </div>
              <div style={{
                background: m.mine ? "var(--accent-soft)" : "var(--paper-2)",
                padding: "8px 12px", borderRadius: 12,
                borderTopRightRadius: m.mine ? 4 : 12,
                borderTopLeftRadius: m.mine ? 12 : 4,
                maxWidth: 480,
                border: "1px solid var(--rule)"
              }}>
                {m.type === "text" &&
                <div>
                    <div style={{ fontSize: 12.5, color: "var(--ink)", whiteSpace: "pre-wrap" }}>{m.text}</div>
                    <button className="btn sm" style={{ marginTop: 6 }} onClick={() => copyText(m.text, "Text copied")}>copy text</button>
                  </div>
                }
                {m.code &&
                <div style={{ marginTop: 6, fontFamily: "var(--font-mono)", fontSize: 11.5, color: "var(--ink)", background: "var(--card)", padding: "5px 8px", borderRadius: 6, border: "1px solid var(--rule)", display: "flex", alignItems: "center", gap: 8 }}>
                    <span style={{ flex: 1 }}>{m.code}</span>
                    <button className="btn sm icon" onClick={() => toast("Copied")}>{Ic.copy}</button>
                  </div>
                }
                {m.attach &&
                <div className="row" style={{ marginTop: 6, padding: "6px 8px", border: "1px solid var(--rule)", borderRadius: 6, background: "var(--card)" }}>
                    <span className="ficon" />
                    <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--ink-2)", flex: 1 }}>{m.attach}</span>
                    <button className="btn sm" onClick={() => copyAssetLink(m)}>copy link</button>
                    <button className="btn sm" onClick={() => downloadAsset(m)}>download</button>
                  </div>
                }
                {!!m.imageUrl &&
                <div style={{ marginTop: 8 }}>
                    <img
                    src={`${m.imageUrl}?t=${Date.now()}`}
                    alt={m.attach || "shareclip image"}
                    onClick={() => setPreviewImage({ url: m.imageUrl, name: m.attach || "image" })}
                    style={{
                      display: "block",
                      maxWidth: 280,
                      maxHeight: 180,
                      borderRadius: 8,
                      border: "1px solid var(--rule)",
                      cursor: "zoom-in",
                      objectFit: "cover",
                      background: "var(--paper-2)"
                    }}
                    />
                    <div className="row" style={{ marginTop: 6, gap: 6 }}>
                      <button className="btn sm" onClick={() => setPreviewImage({ url: m.imageUrl, name: m.attach || "image" })}>preview</button>
                      <button className="btn sm" onClick={() => downloadAsset(m)}>download</button>
                      <button className="btn sm" onClick={() => copyImageToClipboard(m)}>copy image</button>
                    </div>
                  </div>
                }
              </div>
            </div>
            )}
          </div>
          <form onSubmit={send} style={{ display: "flex", gap: 8, padding: 12, borderTop: "1px solid var(--rule)" }}>
            <input ref={fileRef} type="file" accept="image/*" style={{ display: "none" }} onChange={onPickFile} />
            <input ref={attachmentRef} type="file" style={{ display: "none" }} onChange={onPickAttachment} />
            <button type="button" className="btn" onClick={() => fileRef.current && fileRef.current.click()}>{Ic.upload}<span>Image</span></button>
            <button type="button" className="btn" onClick={() => attachmentRef.current && attachmentRef.current.click()}>{Ic.plus}<span>File</span></button>
            <input className="input" placeholder="Paste a clip, snippet, or drop a file…" value={v} onChange={(e) => setV(e.target.value)} />
            <button type="submit" className="btn primary" disabled={sending}>{sending ? "Sharing..." : "Share"}</button>
          </form>
        </div>
      </div>
      {previewImage &&
      <div className="modal-back" onClick={() => setPreviewImage(null)}>
          <div className="modal" style={{ width: "min(96vw, 1100px)", padding: 12 }} onClick={(e) => e.stopPropagation()}>
            <div className="card-h" style={{ padding: "8px 10px" }}>
              <h3 style={{ margin: 0 }}>{previewImage.name}</h3>
              <div className="spacer" />
              <button className="btn sm" onClick={() => copyImageToClipboard(previewImage)}>copy image</button>
              <button className="btn sm" onClick={() => downloadAsset(previewImage)}>download</button>
              <button className="btn sm" onClick={() => setPreviewImage(null)}>close</button>
            </div>
            <div style={{ maxHeight: "80vh", overflow: "auto", padding: 10 }}>
              <img
                src={`${previewImage.url}?t=${Date.now()}`}
                alt={previewImage.name || "preview"}
                style={{ display: "block", maxWidth: "100%", height: "auto", margin: "0 auto", borderRadius: 8, border: "1px solid var(--rule)" }}
              />
            </div>
          </div>
        </div>
      }
    </div>);

  }

  /* ═════════ Settings (real config-backed) ═════════ */
  const CORE_MODULES = [
  { id: "qbt", name: "qBittorrent", desc: "BitTorrent integration and service control." },
  { id: "ddns", name: "DDNS", desc: "Domain update module and controls." },
  { id: "docker", name: "Docker", desc: "Container inventory, logs, and safe controls." },
  { id: "shareclip", name: "ShareClip", desc: "Clipboard and file-drop module." },
  { id: "http", name: "HTTP file access", desc: "Public/LAN file routes and directory service." }];
  const OPT_MODULES = [
  { id: "remote", name: "Remote access", desc: "Expose panel beyond LAN (not wired in current backend).", beta: false },
  { id: "cluster", name: "Cluster (multi-node)", desc: "Multi-node control surface (not wired in current backend).", beta: true }];
  function SRow({ label, hint, children }) {
    return (
      <div className="row" style={{ padding: "10px 0", borderTop: "1px solid var(--rule)", alignItems: "flex-start" }}>
      <div style={{ width: 220, display: "grid", gap: 2 }}>
        <span style={{ fontSize: 12.5, color: "var(--ink-2)" }}>{label}</span>
        {hint && <span style={{ fontSize: 10.5, color: "var(--ink-3)", fontFamily: "var(--font-mono)" }}>{hint}</span>}
      </div>
      <div style={{ flex: 1 }}>{children}</div>
    </div>);
  }
  function ModRow({ m, i, enabled, onToggle }) {
    return (
      <div className="row" style={{ padding: "12px 16px", gap: 14, borderTop: i ? "1px solid var(--rule)" : 0, alignItems: "center" }}>
      <div style={{ flex: 1 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontWeight: 500, color: "var(--ink)" }}>{m.name}</span>
          {m.beta && <span className="chip" style={{ color: "var(--warn)", borderColor: "var(--warn-soft)" }}>beta</span>}
        </div>
        <div style={{ fontSize: 12, color: "var(--ink-3)", marginTop: 2 }}>{m.desc}</div>
      </div>
      <div className={cx("tog", enabled && "on")} onClick={onToggle} />
    </div>);
  }
  function Settings({ toast, onConfigSaved }) {
    const TABS = ["Modules", "Services", "Terminal", "Server"];
    const [tab, setTab] = useState("Modules");
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [cfg, setCfg] = useState(null);
    const [status, setStatus] = useState(null);
    const [err, setErr] = useState("");

    const modules = (cfg && cfg.modules) || {};
    const terminal = (cfg && cfg.terminal) || {};
    const httpService = (cfg && cfg.http_service) || {};
    const qbt = (cfg && cfg.qbt) || {};
    const [qbtDiscover, setQbtDiscover] = useState(null);
    const [qbtBusy, setQbtBusy] = useState(false);
    const [remoteDurationSec, setRemoteDurationSec] = useState(8 * 3600);

    const loadAll = async () => {
      setLoading(true);
      setErr("");
      try {
        const [cfgResp, statusResp] = await Promise.all([
        fetch("/api/app-config", { cache: "no-store" }),
        fetch("/api/control/status", { cache: "no-store" })]);
        const cfgData = await cfgResp.json().catch(() => ({}));
        const statusData = await statusResp.json().catch(() => ({}));
        if (!cfgResp.ok) throw new Error(cfgData.error || `HTTP ${cfgResp.status}`);
        if (!statusResp.ok) throw new Error(statusData.error || `HTTP ${statusResp.status}`);
        setCfg(cfgData.config || {});
        setStatus(statusData || {});
      } catch (e) {
        setErr(String(e && e.message || e || "load failed"));
      } finally {
        setLoading(false);
      }
    };

    useEffect(() => {loadAll();}, []);
    useEffect(() => {
      let dead = false;
      (async () => {
        try {
          const client = String(((cfg || {}).qbt || {}).client || "qbittorrent");
          const d = await apiJson(`/api/qbt/discover?client=${encodeURIComponent(client)}`, { cache: "no-store" });
          if (!dead) setQbtDiscover(d || {});
        } catch (e) {}
      })();
      return () => {dead = true;};
    }, [((cfg || {}).qbt || {}).client]);

    const patchCfg = (patch) => {
      setCfg((prev) => ({ ...(prev || {}), ...patch }));
    };
    const patchNested = (key, patch) => {
      setCfg((prev) => ({ ...(prev || {}), [key]: { ...((prev || {})[key] || {}), ...patch } }));
    };
    const saveConfig = async (payload, msg) => {
      setSaving(true);
      try {
        const r = await fetch("/api/app-config", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        const d = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(d.error || `HTTP ${r.status}`);
        setCfg(d.config || cfg);
        if (onConfigSaved) onConfigSaved(d.config || cfg);
        toast(msg || "Saved");
      } catch (e) {
        toast(`Save failed: ${String(e && e.message || e)}`);
      } finally {
        setSaving(false);
      }
    };
    const runQbtAction = async (label, fn) => {
      setQbtBusy(true);
      try {
        await fn();
        await loadAll();
        toast(label);
      } catch (e) {
        toast(`${label} failed: ${String(e && e.message || e)}`);
      } finally {
        setQbtBusy(false);
      }
    };

    if (loading) return <div className="card-b" style={{ color: "var(--ink-3)" }}>Loading settings...</div>;
    if (err) return <div className="card-b" style={{ color: "var(--danger)" }}>Failed to load settings: {err}</div>;

    return (
      <div className="col">
      <div>
        <h1 className="h1">Settings</h1>
        <p className="sub">Configure modules, services, terminal access and server options from real backend config.</p>
      </div>
      <div className="card">
        <div className="card-h"><h3>System</h3><div className="spacer" /><span className="meta">port · display name · logo</span></div>
        <div className="card-b">
          <SRow label="Panel port" hint="web_port">
            <input className="input" style={{ maxWidth: 180 }} value={String(cfg.web_port || 1288)} onChange={(e) => patchCfg({ web_port: Number(e.target.value || 1288) })} />
          </SRow>
          <SRow label="System name" hint="ui.system_name">
            <input className="input" placeholder="eg: ubuntu-server" value={String((((cfg || {}).ui) || {}).system_name || "")} onChange={(e) => patchNested("ui", { system_name: e.target.value })} />
          </SRow>
          <SRow label="Top logo URL" hint="ui.brand_logo_url">
            <input className="input" placeholder="https://.../logo.png (empty = auto by system)" value={String((((cfg || {}).ui) || {}).brand_logo_url || "")} onChange={(e) => patchNested("ui", { brand_logo_url: e.target.value })} />
          </SRow>
          <div className="row" style={{ marginTop: 10, gap: 8 }}>
            <button className="btn sm primary" disabled={saving} onClick={() => saveConfig({ web_port: cfg.web_port, ui: cfg.ui || {} }, "System saved")}>Save system</button>
            <button className="btn sm" onClick={async () => {
              try {
                const r = await fetch("/api/control/restart", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
                const d = await r.json().catch(() => ({}));
                if (!r.ok) throw new Error(d.error || `HTTP ${r.status}`);
                toast("Restart queued");
              } catch (e) {
                toast(`Restart failed: ${String(e && e.message || e)}`);
              }
            }}>Restart service</button>
          </div>
        </div>
      </div>
      <div className="tablist" style={{ padding: "0 12px" }}>
        {TABS.map((t) => <div key={t} className={cx("tab", tab === t && "on")} onClick={() => setTab(t)}>{t}</div>)}
      </div>

      {tab === "Modules" &&
      <div className="col" style={{ gap: 12 }}>
          <div className="card">
            <div className="card-h"><h3>Core modules</h3><div className="spacer" /><span className="meta">app_config.json · modules</span></div>
            <div className="card-b" style={{ padding: 0 }}>
              {CORE_MODULES.map((m, i) => <ModRow key={m.id} m={m} i={i} enabled={modules[m.id] !== false} onToggle={() => patchNested("modules", { [m.id]: !(modules[m.id] !== false) })} />)}
            </div>
            <div className="card-b" style={{ borderTop: "1px solid var(--rule)", paddingTop: 10 }}>
              <button className="btn sm primary" disabled={saving} onClick={() => saveConfig({ modules: cfg.modules || {} }, "Modules saved")}>Save modules</button>
            </div>
          </div>
          <div className="card">
            <div className="card-h"><h3>Optional & experimental</h3><div className="spacer" /><span className="meta">display only</span></div>
            <div className="card-b" style={{ padding: 0 }}>
              {OPT_MODULES.map((m, i) => <ModRow key={m.id} m={m} i={i} enabled={false} onToggle={() => toast("This option is not wired in current backend")} />)}
            </div>
          </div>
        </div>
      }

      {tab === "Services" &&
      <div className="col" style={{ gap: 12 }}>
          <div className="card">
            <div className="card-h"><h3>Torrent service status</h3><div className="spacer" /><button className="btn sm" onClick={loadAll}>refresh</button></div>
            <div className="card-b">
              <SRow label="qBittorrent" hint="control.status.qbt">
                <span style={{ fontFamily: "var(--font-mono)" }}>{String(((status || {}).qbt || {}).detail || "-")}</span>
              </SRow>
              <SRow label="Unit" hint="control.status.qbt.unit">
                <span style={{ fontFamily: "var(--font-mono)" }}>{String(((status || {}).qbt || {}).unit || "-")}</span>
              </SRow>
              <SRow label="State" hint="control.status.qbt.active_state">
                <span style={{ fontFamily: "var(--font-mono)" }}>{String(((status || {}).qbt || {}).active_state || "-")}</span>
              </SRow>
            </div>
          </div>
          <div className="card">
            <div className="card-h"><h3>Torrent module</h3><div className="spacer" /><span className="meta">detect · optimize · fix permissions · service control</span></div>
            <div className="card-b">
              <SRow label="Client" hint="qbt.client">
                <select className="input" value={String(qbt.client || "qbittorrent")} onChange={(e) => patchNested("qbt", { client: e.target.value })}>
                  <option value="qbittorrent">qBittorrent</option>
                  <option value="deluge">Deluge</option>
                  <option value="transmission">Transmission</option>
                  <option value="rtorrent">rTorrent</option>
                </select>
              </SRow>
              <SRow label="Stats monitor" hint="qbt.monitor_enabled">
                <div className="tog-wrap"><div className={cx("tog", qbt.monitor_enabled !== false && "on")} onClick={() => patchNested("qbt", { monitor_enabled: !(qbt.monitor_enabled !== false) })} /></div>
              </SRow>
              <SRow label="Service unit" hint="qbt.service_unit">
                <select className="input" value={String(qbt.service_unit || "")} onChange={(e) => patchNested("qbt", { service_unit: e.target.value })}>
                  <option value="">Auto detect (recommended)</option>
                  {(((qbtDiscover || {}).service_units) || []).map((x) => <option key={x} value={String(x)}>{String(x)}</option>)}
                </select>
              </SRow>
              <SRow label="Docker container" hint="qbt.docker_container">
                <select className="input" value={String(qbt.docker_container || "")} onChange={(e) => patchNested("qbt", { docker_container: e.target.value })}>
                  <option value="">Auto detect (recommended)</option>
                  {(((qbtDiscover || {}).docker_containers) || []).map((x) => <option key={x} value={String(x)}>{String(x)}</option>)}
                </select>
              </SRow>
              <SRow label="API URL" hint="qbt.api_url">
                <select className="input" value={String(qbt.api_url || "")} onChange={(e) => patchNested("qbt", { api_url: e.target.value })}>
                  <option value="">Auto detect (recommended)</option>
                  {(((qbtDiscover || {}).api_urls) || []).map((x) => <option key={x} value={String(x)}>{String(x)}</option>)}
                </select>
              </SRow>
              <div className="row" style={{ marginTop: 10 }}>
                <button className="btn sm primary" disabled={saving} onClick={() => saveConfig({ qbt: cfg.qbt || {} }, "qB config saved")}>Save qB config</button>
              </div>
              <div className="row" style={{ marginTop: 10, gap: 8, flexWrap: "wrap" }}>
                <button className="btn sm" disabled={qbtBusy} onClick={() => runQbtAction("Detect completed", async () => {
                  const d = await apiJson(`/api/qbt/discover?client=${encodeURIComponent(String(qbt.client || "qbittorrent"))}`, { cache: "no-store" });
                  setQbtDiscover(d || {});
                })}>Detect</button>
                <button className="btn sm" disabled={qbtBusy} onClick={() => runQbtAction("Optimization completed", async () => {
                  await apiJson("/api/qbt/optimize-config", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ qbt: cfg.qbt || {} })
                  });
                })}>Optimize</button>
                <button className="btn sm" disabled={qbtBusy} onClick={() => runQbtAction("Fix completed", async () => {
                  await apiJson("/api/qbt/fix-monitor", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
                })}>Fix permissions</button>
              </div>
              <div className="row" style={{ marginTop: 10, gap: 8, flexWrap: "wrap" }}>
                {["start", "stop", "restart", "quit"].map((action) =>
                <button key={action} className="btn sm" disabled={qbtBusy} onClick={() => runQbtAction(`Service ${action} done`, async () => {
                  await apiJson("/api/control/service", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ service: "qbt", action, client: String(qbt.client || "qbittorrent") })
                  });
                })}>{action}</button>
                )}
              </div>
            </div>
          </div>
        </div>
      }

      {tab === "Terminal" &&
      <div className="card">
          <div className="card-h"><h3>Web terminal — SSH config</h3><div className="spacer" /><span className="meta">app_config.json · terminal</span></div>
          <div className="card-b">
            <SRow label="Enabled" hint="terminal.enabled">
              <div className="tog-wrap"><div className={cx("tog", terminal.enabled !== false && "on")} onClick={() => patchNested("terminal", { enabled: !(terminal.enabled !== false) })} /></div>
            </SRow>
            <SRow label="SSH host" hint="terminal.host">
              <input className="input" value={String(terminal.host || "")} onChange={(e) => patchNested("terminal", { host: e.target.value })} />
            </SRow>
            <SRow label="SSH port" hint="terminal.port">
              <input className="input" style={{ maxWidth: 120 }} value={String(terminal.port || 22)} onChange={(e) => patchNested("terminal", { port: Number(e.target.value || 22) })} />
            </SRow>
            <SRow label="Username" hint="terminal.user">
              <input className="input" value={String(terminal.user || "")} onChange={(e) => patchNested("terminal", { user: e.target.value })} />
            </SRow>
            <SRow label="Auth mode" hint="terminal.auth_mode">
              <select className="input" style={{ maxWidth: 160 }} value={String(terminal.auth_mode || "key")} onChange={(e) => patchNested("terminal", { auth_mode: e.target.value })}>
                <option value="key">SSH key</option>
                <option value="password">Password</option>
              </select>
            </SRow>
            <SRow label="Key path" hint="terminal.key_path">
              <input className="input" placeholder="eg: /home/randy/.ssh/id_ed25519" value={String(terminal.key_path || "")} onChange={(e) => patchNested("terminal", { key_path: e.target.value })} />
            </SRow>
            <SRow label="Key filename" hint="terminal.key_file">
              <input className="input" value={String(terminal.key_file || "")} onChange={(e) => patchNested("terminal", { key_file: e.target.value })} />
            </SRow>
            <div className="row" style={{ marginTop: 10 }}>
              <button className="btn sm primary" disabled={saving} onClick={() => saveConfig({ terminal: cfg.terminal || {} }, "Terminal saved")}>Save terminal</button>
            </div>
          </div>
        </div>
      }

      {tab === "Server" &&
      <div className="col" style={{ gap: 12 }}>
          <div className="card">
            <div className="card-h"><h3>Server options</h3><div className="spacer" /><span className="meta">http_service</span></div>
            <div className="card-b">
              <SRow label="Storage root" hint="http_service.root_dir">
                <input className="input" value={String(httpService.root_dir || "/srv/Storage")} onChange={(e) => patchNested("http_service", { root_dir: e.target.value })} />
              </SRow>
              <SRow label="Default dir" hint="http_service.default_dir">
                <input className="input" value={String(httpService.default_dir || ".")} onChange={(e) => patchNested("http_service", { default_dir: e.target.value })} />
              </SRow>
              <SRow label="Recent transfer TTL" hint="http_service.transfer_recent_ttl_sec">
                <input className="input" style={{ maxWidth: 160 }} value={String(httpService.transfer_recent_ttl_sec ?? 15)} onChange={(e) => patchNested("http_service", { transfer_recent_ttl_sec: Number(e.target.value || 15) })} />
              </SRow>
              <div className="row" style={{ marginTop: 10, gap: 8 }}>
                <button className="btn sm primary" disabled={saving} onClick={() => saveConfig({ http_service: cfg.http_service || {} }, "Server settings saved")}>Save server</button>
                <button className="btn sm" onClick={async () => {
                  try {
                    const r = await fetch("/api/control/restart", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
                    const d = await r.json().catch(() => ({}));
                    if (!r.ok) throw new Error(d.error || `HTTP ${r.status}`);
                    toast("Restart queued");
                  } catch (e) {
                    toast(`Restart failed: ${String(e && e.message || e)}`);
                  }
                }}>Restart service</button>
              </div>
            </div>
          </div>
          <div className="card">
            <div className="card-h"><h3>Remote access</h3><div className="spacer" /><span className="meta">http_access policy</span></div>
            <div className="card-b">
              {(() => {
                const access = ((status || {}).http_access) || {};
                const mode = String(access.effective_mode || "lan_only");
                const remain = Number(access.public_seconds_remaining || 0);
                const persistent = !!access.public_persistent;
                const base = String(access.public_base_url || "");
                const hint = mode === "public" ? (persistent ? "WAN open (persistent)" : `WAN open (${Math.max(0, Math.floor(remain / 60))} min left)`) : "LAN-only";
                return (
                  <>
                    <SRow label="Current mode" hint="http_access.effective_mode">
                      <span className={cx("pill", mode === "public" ? "warn" : "ok")}><span className="d" />{hint}</span>
                    </SRow>
                    <SRow label="Public base URL" hint="api/base.public_base_url">
                      <div className="row" style={{ gap: 8, width: "100%" }}>
                        <input className="input" readOnly value={base || "-"} />
                        <button className="btn sm" disabled={!base} onClick={async () => {
                          try { await navigator.clipboard.writeText(base); toast("Copied"); } catch (e) { toast("Copy failed"); }
                        }}>Copy</button>
                      </div>
                    </SRow>
                    <SRow label="Timed duration" hint="duration_sec">
                      <select className="input" style={{ maxWidth: 220 }} value={String(remoteDurationSec)} onChange={(e) => setRemoteDurationSec(Number(e.target.value || 28800))}>
                        <option value={1800}>30 minutes</option>
                        <option value={3600}>1 hour</option>
                        <option value={14400}>4 hours</option>
                        <option value={28800}>8 hours</option>
                        <option value={86400}>24 hours</option>
                      </select>
                    </SRow>
                    <div className="row" style={{ marginTop: 10, gap: 8, flexWrap: "wrap" }}>
                      <button className={cx("btn sm", mode !== "public" && "primary")} onClick={async () => {
                        try { await apiJson("/api/control/http-access", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action: "close" }) }); toast("Switched to LAN-only"); await loadAll(); } catch (e) { toast(`Switch failed: ${String(e && e.message || e)}`); }
                      }}>LAN-only</button>
                      <button className={cx("btn sm", mode === "public" && !persistent && "primary")} onClick={async () => {
                        try { await apiJson("/api/control/http-access", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action: "open_public", duration_sec: remoteDurationSec }) }); toast("Timed WAN opened"); await loadAll(); } catch (e) { toast(`Open failed: ${String(e && e.message || e)}`); }
                      }}>Open WAN (timed)</button>
                      <button className={cx("btn sm", mode === "public" && persistent && "primary")} onClick={async () => {
                        try { await apiJson("/api/control/http-access", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action: "open_public_persistent" }) }); toast("Persistent WAN opened"); await loadAll(); } catch (e) { toast(`Open failed: ${String(e && e.message || e)}`); }
                      }}>Open WAN (persistent)</button>
                    </div>
                    <div className="meta" style={{ marginTop: 8, color: "var(--warn)" }}>
                      Keep WAN open only when needed. Timed mode is recommended.
                    </div>
                  </>
                );
              })()}
            </div>
          </div>
        </div>
      }
    </div>);
  }

  /* ═════════ App shell ═════════ */
  const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
    "theme": "light",
    "language": "en"
  } /*EDITMODE-END*/;

  function App() {
    const [section, setSection] = useState("dash");
    const [toasts, setToasts] = useState([]);
    const [member, setMember] = useState(null);
    const [memberOpen, setMemberOpen] = useState(false);
    const [tweaksOpen, setTweaksOpen] = useState(false);
    const tweaksRef = useRef(null);
    const toast = (msg) => {
      const id = Date.now() + Math.random();
      setToasts((T) => [...T, { id, msg }]);
      setTimeout(() => setToasts((T) => T.filter((x) => x.id !== id)), 2400);
    };

    const initTheme = (() => {
      try {
        return localStorage.getItem("fc-theme") || TWEAK_DEFAULTS.theme;
      } catch (_) {
        return TWEAK_DEFAULTS.theme;
      }
    })();
    const initLang = (() => {
      try {
        return localStorage.getItem("fc-lang") || TWEAK_DEFAULTS.language;
      } catch (_) {
        return TWEAK_DEFAULTS.language;
      }
    })();
    const t = (window.useTweaks || (() => [{ ...TWEAK_DEFAULTS, theme: initTheme, language: initLang }, () => {}, () => {}]))({ ...TWEAK_DEFAULTS, theme: initTheme, language: initLang });
    const tweaks = t[0];
    const setTweak = t[1];
    const openTweaks = () => {
      setTweaksOpen(true);
      try {
        window.postMessage({ type: "__activate_edit_mode" }, "*");
        if (window.parent && window.parent !== window) window.parent.postMessage({ type: "__activate_edit_mode" }, "*");
      } catch (_) {}
    };

    /* live state */
    const [live, setLive] = useState({
      system: {},
      qbt: {},
      ddns: {},
      self: {},
      http_access: {},
      speed: {},
      transferMeta: { items: [], count: 0, recent_count: 0, overall_progress_pct: 0, source_stats: [] },
      clipHistory: []
    });
    const [appCfg, setAppCfg] = useState(null);
    const [metricHist, setMetricHist] = useState({
      cpu: Array(40).fill(0),
      mem: Array(40).fill(0),
      netDown: Array(40).fill(0),
      netUp: Array(40).fill(0),
      disk: Array(40).fill(0),
      diskIO: Array(40).fill(0)
    });
    const [primaryDiskPath, setPrimaryDiskPath] = useState((() => {
      try { return localStorage.getItem("ac-home-disk-primary") || localStorage.getItem("ac-home-disk") || ""; } catch (_) { return ""; }
    })());
    const [selectedDiskPaths, setSelectedDiskPaths] = useState((() => {
      try {
        const raw = localStorage.getItem("ac-home-disks-selected");
        const arr = raw ? JSON.parse(raw) : [];
        return Array.isArray(arr) ? arr.map((x) => String(x || "")).filter(Boolean) : [];
      } catch (_) { return []; }
    })());
    const [diskVisibleMap, setDiskVisibleMap] = useState((() => {
      try {
        const raw = localStorage.getItem("ac-home-disks-visible");
        const obj = raw ? JSON.parse(raw) : {};
        return obj && typeof obj === "object" ? obj : {};
      } catch (_) { return {}; }
    })());
    const [disksPanelOpen, setDisksPanelOpen] = useState((() => {
      try {
        const raw = localStorage.getItem("ac-home-disks-open");
        return raw == null ? true : raw === "1";
      } catch (_) { return true; }
    })());
    const pushHist = (arr, v, limit = 80) => {
      const next = [...(Array.isArray(arr) ? arr : []), Number.isFinite(Number(v)) ? Number(v) : 0];
      return next.length > limit ? next.slice(next.length - limit) : next;
    };
    const [services, setServices] = useState([]);
    const navCounts = useMemo(() => {
      const system = (live && live.system) || {};
      const nodes = system && Object.keys(system).length ? 1 : 0;
      const svcWarn = services.filter((s) => !!s.warn || !s.on).length;
      const shareCnt = Array.isArray(live.clipHistory) ? live.clipHistory.length : 0;
      const out = {};
      if (nodes > 0) out.nodes = { badge: nodes };
      if (Number(((live || {}).docker || {}).total || 0) > 0) out.docker = { badge: Number(((live || {}).docker || {}).total || 0) };
      if (svcWarn > 0) out.services = { alert: svcWarn };
      if (shareCnt > 0) out.share = { badge: shareCnt };
      return out;
    }, [live, services]);
    const toggleService = (id) => {
      const map = { qbt: "qbt", ddns: "ddns", http: "self" };
      const target = map[id];
      if (!target) return;
      const cur = services.find((s) => s.id === id);
      const action = cur && cur.on ? "stop" : "start";
      apiJson("/api/control/service", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ service: target, action }),
      }).then(() => {
        toast(`${cur ? cur.name : id} ${action} requested`);
      }).catch((e) => {
        toast(`${cur ? cur.name : id} ${action} failed: ${e.message || e}`);
      });
    };

    const transfers = Array.isArray(live.transferMeta.items) ? live.transferMeta.items.slice(0, 16).map((it) => ({
      name: String(it.filename || it.relative_path || "unknown"),
      kind: String(it.source || "http"),
      pct: Math.max(0, Math.min(100, Number(it.progress_pct || 0))),
      speed: Number(it.speed_mibps || 0).toFixed(2),
      eta: "—",
      done: Number(it.sent_bytes || 0),
      total: Number(it.total_bytes || 0),
      dir: false,
    })) : [];
    const pushTransfer = (t) => {
      toast(`Design-only upload simulation: ${t.name}`);
    };
    useEffect(() => {
      let dead = false;
      const restoreMember = async () => {
        const tok = memberSessionToken();
        if (!tok) return;
        try {
          const cached = JSON.parse(String(localStorage.getItem(MEMBER_PROFILE_KEY) || "null"));
          if (!dead && cached && typeof cached === "object") setMember(cached);
        } catch (_) {}
        try {
          const d = await apiJson(memberApiUrl("/api/member/profile"), { cache: "no-store" });
          const nextMember = (d && d.member) || null;
          if (nextMember && typeof nextMember === "object") {
            if (!dead) setMember(nextMember);
            try { localStorage.setItem(MEMBER_PROFILE_KEY, JSON.stringify(nextMember)); } catch (_) {}
          }
        } catch (e) {
          const msg = String((e && e.message) || e || "");
          const invalid = /Member session invalid|Request failed 401|401/.test(msg);
          if (invalid) {
            clearMemberSessionStore();
            if (!dead) setMember(null);
          }
        }
      };
      restoreMember();
      return () => { dead = true; };
    }, []);

    useEffect(() => {
      let dead = false;
      const pullMetricsHistory = async () => {
        try {
          const h = await apiJson("/api/metrics/history");
          if (dead) return;
          const pick = (k) => Array.isArray(h[k]) && h[k].length ? h[k].map((x) => Number(x || 0)) : Array(40).fill(0);
          setMetricHist({
            cpu: pick("cpu"),
            mem: pick("mem"),
            netDown: pick("netDown"),
            netUp: pick("netUp"),
            disk: pick("diskUsage"),
            diskIO: pick("diskIO")
          });
        } catch (e) {}
      };
      const pullCfg = async () => {
        try {
          const d = await apiJson("/api/app-config");
          if (!dead) setAppCfg((d && d.config) || d || null);
        } catch (e) {}
      };
      const pull = async () => {
        try {
          const [status, speed, transfer, clips] = await Promise.all([
            apiJson("/api/control/status"),
            apiJson("/api/speed"),
            apiJson("/api/transfers"),
            apiJson("/api/history?id=pub&limit=5").catch(() => ({ items: [] })),
          ]);
          if (dead) return;
          const nextLive = {
            system: status.system || {},
            qbt: status.qbt || {},
            ddns: status.ddns || {},
            self: status.self || {},
            http_access: status.http_access || {},
            speed: speed || {},
            transferMeta: transfer || {},
            clipHistory: Array.isArray(clips.items) ? clips.items.map((it) => ({
              id: it.id,
              who: "shareclip",
              t: String(it.updated_at || "").replace("T", " ").slice(5, 16),
              text: it.type === "text" ? String(it.text || "") : it.type === "file" ? `file: ${String(it.file_name || it.file_filename || "file")}` : `image: ${String(it.image_filename || "image")}`,
              attach: it.type === "image" ? String(it.image_filename || "image") : it.type === "file" ? String(it.file_name || it.file_filename || "file") : "",
            })) : [],
          };
          setLive(nextLive);
          const memTotalNow = Number((nextLive.system || {}).mem_total || 0);
          const memUsedNow = Number((nextLive.system || {}).mem_used || 0);
          const diskTotalNow = Number((nextLive.system || {}).disk_total || 0);
          const diskUsedNow = Number((nextLive.system || {}).disk_used || 0);
          const cpuNow = Math.max(0, Math.min(100, Number((nextLive.system || {}).load1 || 0) * 10));
          const memNow = memTotalNow > 0 ? Math.max(0, Math.min(100, memUsedNow * 100 / memTotalNow)) : 0;
          const diskNow = diskTotalNow > 0 ? Math.max(0, Math.min(100, diskUsedNow * 100 / diskTotalNow)) : 0;
          const rxNow = Math.max(0, Number((nextLive.speed || {}).rx_mibps || 0));
          const txNow = Math.max(0, Number((nextLive.speed || {}).tx_mibps || 0));
          const diskReadNow = Math.max(0, Number((nextLive.speed || {}).disk_read_mibps || 0));
          const diskWriteNow = Math.max(0, Number((nextLive.speed || {}).disk_write_mibps || 0));
          setMetricHist((prev) => ({
            cpu: pushHist(prev.cpu, cpuNow),
            mem: pushHist(prev.mem, memNow),
            netDown: pushHist(prev.netDown, rxNow),
            netUp: pushHist(prev.netUp, txNow),
            disk: pushHist(prev.disk, diskNow),
            diskIO: pushHist(prev.diskIO, diskReadNow + diskWriteNow)
          }));
          const httpMode = String(((nextLive.http_access || {}).effective_mode || "")).toLowerCase();
          const httpModeText = httpMode === "public" ? "public" : "lan-only";
          const httpDetailRaw = String(nextLive.self.detail || "").trim();
          const httpDetail = [httpDetailRaw, httpModeText].filter(Boolean).join(" · ");
          const dockerSummary = (nextLive && nextLive.docker) || {};
          const dockerTotal = Number(dockerSummary.total || 0);
          const dockerRunning = Number(dockerSummary.running || 0);
          setServices([
            {
              id: "qbt",
              name: "BitTorrent",
              on: String(nextLive.qbt.active_state || "") === "active",
              warn: false,
              detail: String((nextLive.qbt.stats && nextLive.qbt.stats.detail) || nextLive.qbt.detail || ""),
              kind: "torrent",
              exposed: false,
            },
            {
              id: "ddns",
              name: "DDNS",
              on: String(nextLive.ddns.active_state || "") === "active",
              warn: false,
              detail: String(nextLive.ddns.detail || ""),
              kind: "network",
              exposed: true,
            },
            {
              id: "http",
              name: "HTTPD",
              on: String(nextLive.self.active_state || "") === "active",
              warn: false,
              detail: httpDetail || "-",
              kind: "web",
              exposed: String((nextLive.http_access || {}).effective_mode || "") === "public",
            },
            {
              id: "docker",
              name: "Docker",
              on: dockerTotal > 0,
              warn: !!dockerSummary.error && !dockerSummary.disabled,
              detail: dockerSummary.disabled ? "Docker module disabled" : dockerSummary.error ? String(dockerSummary.error) : `${dockerRunning}/${dockerTotal} containers running · ${Number(dockerSummary.images || 0)} images`,
              kind: "containers",
              exposed: false,
              readOnly: true,
              target: "docker",
            }
          ]);
        } catch (e) {
          if (!dead) toast(`Live data refresh failed: ${e.message || e}`);
        }
      };
      pullMetricsHistory();
      pullCfg();
      pull();
      const cfgTk = setInterval(pullCfg, 10000);
      const tk = setInterval(pull, 2500);
      return () => { dead = true; clearInterval(tk); clearInterval(cfgTk); };
    }, []);
    useEffect(() => {
      try { localStorage.setItem("ac-home-disk-primary", String(primaryDiskPath || "")); } catch (_) {}
    }, [primaryDiskPath]);
    useEffect(() => {
      try { localStorage.setItem("ac-home-disks-selected", JSON.stringify(Array.isArray(selectedDiskPaths) ? selectedDiskPaths : [])); } catch (_) {}
    }, [selectedDiskPaths]);
    useEffect(() => {
      try { localStorage.setItem("ac-home-disks-visible", JSON.stringify(diskVisibleMap || {})); } catch (_) {}
    }, [diskVisibleMap]);
    useEffect(() => {
      try { localStorage.setItem("ac-home-disks-open", disksPanelOpen ? "1" : "0"); } catch (_) {}
    }, [disksPanelOpen]);

    /* tweak side-effects: theme + language */
    useEffect(() => {
      const themeNow = tweaks.theme || "light";
      document.documentElement.setAttribute("data-theme", themeNow);
      try {localStorage.setItem("fc-theme", themeNow);} catch (_) {}
      const langNow = tweaks.language || "en";
      try {localStorage.setItem("fc-lang", langNow);} catch (_) {}
      const langMap = { en: "en", zh: "zh-CN", ms: "ms", de: "de", fr: "fr", ja: "ja" };
      try {document.documentElement.setAttribute("lang", langMap[langNow] || "en");} catch (_) {}
    }, [tweaks.theme, tweaks.language]);
    useEffect(() => {
      if (!tweaksOpen) return;
      const onDown = (e) => {
        const el = tweaksRef.current;
        if (!el) return;
        if (!el.contains(e.target)) setTweaksOpen(false);
      };
      document.addEventListener("mousedown", onDown);
      return () => document.removeEventListener("mousedown", onDown);
    }, [tweaksOpen]);

    const primaryDisk = useMemo(() => {
      const disks = (((live || {}).system || {}).disks || []);
      if (!Array.isArray(disks) || !disks.length) return null;
      const byPath = disks.find((d) => String(d.path || "") === String(primaryDiskPath || ""));
      return byPath || disks[0];
    }, [live, primaryDiskPath]);
    const selectedDisks = useMemo(() => {
      const disks = (((live || {}).system || {}).disks || []);
      if (!Array.isArray(disks) || !disks.length) return [];
      const picked = new Set((Array.isArray(selectedDiskPaths) ? selectedDiskPaths : []).map((x) => String(x || "")));
      return disks.filter((d) => picked.has(String(d.path || "")));
    }, [live, selectedDiskPaths]);
    useEffect(() => {
      const disks = (((live || {}).system || {}).disks || []);
      if (!Array.isArray(disks) || !disks.length) return;
      const paths = disks.map((d) => String(d.path || ""));
      const primaryExists = paths.includes(String(primaryDiskPath || ""));
      if (!primaryExists) setPrimaryDiskPath(String(paths[0] || ""));
      setSelectedDiskPaths((prev) => {
        const arr = Array.isArray(prev) ? prev.map((x) => String(x || "")).filter((x) => paths.includes(x)) : [];
        if (!arr.length && paths[0]) return [paths[0]];
        return arr;
      });
    }, [live && live.system && live.system.disks, primaryDiskPath]);

    const renderSection = () => {
      switch (section) {
        case "dash":return <Dashboard services={services} toggleService={toggleService} transfers={transfers} goto={setSection} toast={toast} live={live} appCfg={appCfg} metricHist={metricHist} primaryDisk={primaryDisk} selectedDisks={selectedDisks} diskVisibleMap={diskVisibleMap} disksPanelOpen={disksPanelOpen} setDisksPanelOpen={setDisksPanelOpen} member={member} />;
        case "files":return <Files pushTransfer={pushTransfer} />;
        case "httpd":return <HTTPDBrowser toast={toast} />;
        case "monitor":return <Monitor live={live} appCfg={appCfg} metricHist={metricHist} primaryDiskPath={primaryDiskPath} setPrimaryDiskPath={setPrimaryDiskPath} selectedDiskPaths={selectedDiskPaths} setSelectedDiskPaths={setSelectedDiskPaths} diskVisibleMap={diskVisibleMap} setDiskVisibleMap={setDiskVisibleMap} />;
        case "nodes":return <Nodes live={live} appCfg={appCfg} homeDisk={primaryDisk} />;
        case "docker":return <Docker toast={toast} live={live} />;
        case "term":return <Terminal toast={toast} />;
        case "services":return <Services services={services} toggleService={toggleService} goto={setSection} />;
        case "share":return <ShareClip toast={toast} />;
        case "settings":return <Settings toast={toast} onConfigSaved={setAppCfg} />;
      }
    };

    return (
      <div className="app" data-screen-label={`AfterClaw — ${SECTIONS.find((s) => s.id === section)?.label}`}>
      <Topbar section={section} onTweaks={openTweaks} onAccount={() => setMemberOpen(true)} live={live} appCfg={appCfg} member={member} />
      <Sidebar active={section} onNav={setSection} navCounts={navCounts} />
      <main className="main">{renderSection()}</main>
      {toasts.length > 0 &&
        <div className="toast-stack">
          {toasts.map((t) =>
            <div key={t.id} className="toast">
              <span className="toast-dot" />
              <span>{t.msg}</span>
            </div>
          )}
        </div>
      }
      {tweaksOpen &&
        <div style={{ position: "fixed", top: 62, right: 84, zIndex: 40 }}>
          <div ref={tweaksRef} className="card" style={{ width: "min(92vw, 560px)", boxShadow: "var(--shadow-2)", borderRadius: 22 }}>
            <div className="card-h" style={{ padding: "16px 18px 10px" }}>
              <h3 style={{ fontSize: 38, lineHeight: 1, margin: 0, fontFamily: "var(--font-ui)", fontWeight: 700 }}>Tweaks</h3>
              <div className="spacer" />
              <button className="btn sm ghost" onClick={() => setTweaksOpen(false)}>✕</button>
            </div>
            <div className="card-b col" style={{ gap: 12, paddingTop: 6 }}>
              <div className="meta" style={{ letterSpacing: ".08em", fontWeight: 700 }}>APPEARANCE</div>
              <div className="meta" style={{ color: "var(--ink-2)", marginBottom: -4 }}>Theme</div>
              <div className="row" style={{ gap: 8, flexWrap: "nowrap", borderRadius: 14, background: "var(--paper-2)", padding: 6 }}>
                {["light", "dim", "dark"].map((x) =>
                <button key={x} className={cx("btn sm", tweaks.theme === x && "primary")} style={{ flex: 1, justifyContent: "center" }} onClick={() => setTweak("theme", x)}>{x[0].toUpperCase() + x.slice(1)}</button>
                )}
              </div>
              <div className="meta" style={{ color: "var(--ink-2)", marginBottom: -4 }}>Language</div>
              <div className="grid-3" style={{ gap: 8, borderRadius: 14, background: "var(--paper-2)", padding: 6 }}>
                {[
                { k: "en", n: "English" },
                { k: "zh", n: "中文" },
                { k: "ms", n: "Bahasa Melayu" },
                { k: "de", n: "Deutsch" },
                { k: "fr", n: "Français" },
                { k: "ja", n: "日本語" }].map((x) =>
                <button key={x.k} className={cx("btn sm", tweaks.language === x.k && "primary")} style={{ width: "100%", justifyContent: "center" }} onClick={() => setTweak("language", x.k)}>{x.n}</button>
                )}
              </div>
            </div>
          </div>
        </div>
      }
      <MemberModal open={memberOpen} onClose={() => setMemberOpen(false)} member={member} setMember={setMember} toast={toast} live={live} />
    </div>);

  }

  return { App };
}();

ReactDOM.createRoot(document.getElementById("root")).render(<window.AfterClaw.App />);
