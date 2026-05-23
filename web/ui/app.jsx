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
const apiJson = async (url, opts = {}) => {
  const r = await fetch(url, opts);
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error((d && d.error) || `Request failed ${r.status}`);
  return d;
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
  { id: "nodes", label: "Nodes", icon: Ic.nodes, group: "OVERVIEW", badge: "3" },
  { id: "files", label: "Files", icon: Ic.files, group: "WORKLOADS" },
  { id: "docker", label: "Docker", icon: Ic.docker, group: "WORKLOADS", badge: "12" },
  { id: "services", label: "Services", icon: Ic.svc, group: "WORKLOADS", badgeAlert: "1" },
  { id: "term", label: "Web terminal", icon: Ic.term, group: "TOOLS" },
  { id: "share", label: "ShareClip", icon: Ic.share, group: "TOOLS" },
  { id: "settings", label: "Settings", icon: Ic.set, group: "SYSTEM" }];


  function Sidebar({ active, onNav }) {
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
              {s.badge && <span className="badge">{s.badge}</span>}
              {s.badgeAlert && <span className="badge alert">{s.badgeAlert}</span>}
            </div>
          )}
        </div>
        )}
    </aside>);

  }

  /* ═════════ Topbar ═════════ */
  function Topbar({ section, onTweaks, theme, setTheme, live }) {
    const label = SECTIONS.find((s) => s.id === section)?.label || "";
    const time = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    const host = String((((live || {}).system) || {}).hostname || "ubuntu-server");
    const themes = [
    { id: "light", icon: "☀", title: "Light" },
    { id: "dim", icon: "◐", title: "Dim" },
    { id: "dark", icon: "●", title: "Dark" }];

    return (
      <header className="topbar">
      <div className="brand">
        <span className="mascot" />
        <span>after<b>Claw</b></span>
      </div>
      <div className="crumbs">
        <span>{host}</span>
        <span>›</span>
        <span className="here">{label}</span>
      </div>
      <div className="spacer" />
      <div className="theme-switch" role="radiogroup" aria-label="Color theme">
        {themes.map((t) =>
          <button key={t.id} className={cx("th-btn", theme === t.id && "on")}
          onClick={() => setTheme && setTheme(t.id)}
          title={t.title} aria-pressed={theme === t.id}>
            <span>{t.icon}</span>
          </button>
          )}
      </div>
      <span className="pill lan"><span className="d" />LAN-only</span>
      <span className="pill ok" title="uptime · clock"><span className="d" />up 5d 13h · {time}</span>
      <button className="btn icon" title="Notifications">{Ic.bell}</button>
      <button className="btn" onClick={onTweaks}>Tweaks</button>
      <button className="btn icon" title="Account">{Ic.user}</button>
    </header>);

  }

  /* ═════════ Dashboard (variant A — card grid) ═════════ */
  const cpuHist = wave(40, 38, 12, 0, 0.5);
  const memHist = wave(40, 62, 6, 1, 0.3);
  const netHist = wave(40, 50, 30, 2, 0.6);
  const diskHist = wave(40, 22, 6, 3, 0.5);

  function Dashboard({ services, toggleService, transfers, goto, toast, live }) {
    const system = (live && live.system) || {};
    const speed = (live && live.speed) || {};
    const transferMeta = (live && live.transferMeta) || {};
    const cpuValue = Number(system.load1 || 0);
    const memTotal = Number(system.mem_total || 0);
    const memUsed = Number(system.mem_used || 0);
    const memPct = memTotal > 0 ? memUsed * 100 / memTotal : 0;
    const diskTotal = Number(system.disk_total || 0);
    const diskUsed = Number(system.disk_used || 0);
    const diskPct = diskTotal > 0 ? diskUsed * 100 / diskTotal : 0;
    const netDown = Number(speed.rx_mibps || 0);
    const netUp = Number(speed.tx_mibps || 0);
    const activeTransfers = Number(transferMeta.count || 0);
    const serviceWarnCount = services.filter((s) => !!s.warn).length;
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
          <div className="hero-eyebrow">AFTERCLAW · NAS-01</div>
          <h1 className="hero-title">Good <span className="accent">afternoon.</span></h1>
          <p className="hero-sub">
            Everything's quiet on the box.<br />
            <b className="hero-num">{activeTransfers}</b> transfers running, <b className="hero-num warn">{serviceWarnCount}</b> service needs your attention.
          </p>
        </div>
      </section>

      <div className="grid-4">
        <StatCard label="CPU" value={cpuValue.toFixed(2)} unit="" sub={`load1 · uptime ${system.uptime_human || "-"}`} hist={cpuHist} unit2="" />
        <StatCard label="Memory" value={system.mem_used_human || "0B"} unit={` / ${system.mem_total_human || "0B"}`} sub={`${memPct.toFixed(1)}% used`} hist={memHist} unit2="%" />
        <StatCard label="Network" value={netDown.toFixed(2)} unit=" MiB/s" sub={`↓ ${netDown.toFixed(2)} · ↑ ${netUp.toFixed(2)} MiB/s`} hist={netHist} color="var(--good)" paper unit2=" MiB/s" />
        <StatCard label="Storage" value={system.disk_used_human || "0B"} unit={` / ${system.disk_total_human || "0B"}`} sub={`${diskPct.toFixed(1)}% used`} hist={diskHist} color="var(--warn)" unit2="%" />
      </div>

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
          <div className="card-b" style={{ padding: 0 }}>
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
          <div className="card-b" style={{ padding: 0 }}>
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
          <div className="card-b" style={{ padding: "6px 16px 12px" }}>
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
          <div className="card-b" style={{ padding: 0 }}>
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
    const qbt = (live && live.qbt) || {};
    const stats = qbt.stats || {};
    const running = String(qbt.active_state || "") === "active";
    const label = String(qbt.unit || "qBittorrent");
    const down = fmtRate(stats.dl_bps || 0);
    const up = fmtRate(stats.up_bps || 0);
    const runAction = async (action) => {
      try {
        await apiJson("/api/control/service", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ service: "qbt", action }),
        });
        toast(`BitTorrent ${action} requested`);
      } catch (e) {
        toast(`BitTorrent ${action} failed: ${e.message || e}`);
      }
    };
    return (
      <section className="card ctrl">
      <div className="card-h">
        <h3>BitTorrent Service</h3>
      </div>
      <div className="card-b ctrl-b">
        <div className="row" style={{ gap: 8, alignItems: "center" }}>
          <span className={cx("pill", running ? "ok" : "idle")}><span className="d" />{running ? "Running" : "Stopped"}</span>
          <span style={{ fontFamily: "var(--font-mono)", fontSize: 11.5, color: "var(--ink-2)" }}>{label}</span>
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
      <section className="card ctrl">
      <div className="card-h"><h3>DDNS Service</h3></div>
      <div className="card-b ctrl-b">
        <div className="row" style={{ gap: 8 }}>
          <span className={cx("pill", running ? "ok" : "idle")}><span className="d" />{running ? "Running" : "Stopped"}</span>
          <span style={{ fontFamily: "var(--font-mono)", fontSize: 11.5, color: "var(--ink-2)" }}>{String(ddns.unit || "ddns")}</span>
        </div>
        <div className="ctrl-meta">{detail}</div>
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
    return (
      <section className="card ctrl">
      <div className="card-h"><h3>HTTPD Service</h3></div>
      <div className="card-b ctrl-b">
        <div className="row" style={{ gap: 8 }}>
          <span className={cx("pill", running ? "ok" : "idle")}><span className="d" />{running ? "Running" : "Stopped"}</span>
          <span style={{ fontFamily: "var(--font-mono)", fontSize: 11.5, color: "var(--ink-2)" }}>{String(http.unit || "storage-http-link-web")}</span>
        </div>
        <div className="ctrl-meta">
          File Access: <b style={{ color: "var(--ink)" }}>{modeText}</b>
          {mode === "public" &&
            <span style={{ marginLeft: 8, color: "var(--ink-2)" }}>
              {isTimed ? `Timer ${remainText}` : "Persistent"}
            </span>
            }
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
            onChange={(e) => setDurationSec(Number(e.target.value) || 3600)}>
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


  function NetdiskGauge({ d, unit, max = 100 }) {
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
          <div className="g-unit">{unit || "Mbps"}</div>
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
    const [unit, setUnit] = useState("Mbps");
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
    const dialRows = dialRowsRaw.map((d) => d);
    const gaugeMax = 1000;
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
        {dialRows.map((d) => <NetdiskGauge key={d.id} d={d} unit={unit} max={gaugeMax} />)}
      </div>
      <div className="card-h" style={{ borderTop: "1px solid var(--rule)", borderBottom: 0 }}>
        <h3 style={{ fontSize: 12.5 }}>Aggregate HTTP Session Activity</h3>
        <div className="spacer" />
        <button className="btn sm" onClick={() => setUnit((u) => u === "Mbps" ? "Mbit/s" : "Mbps")}>{unit}</button>
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
      <div className="col">
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
  function Monitor() {
    const ranges = ["5m", "1h", "6h", "24h", "7d"];
    const [r, setR] = useState("1h");
    const cpu = wave(80, 38, 18, 0, 0.6);
    const mem = wave(80, 62, 5, 1, 0.4);
    const netDown = wave(80, 30, 22, 2, 0.7);
    const netUp = wave(80, 14, 12, 1.5, 0.7);
    const disk = wave(80, 22, 16, 3, 1.2);
    const temp = wave(80, 56, 4, 4, 0.3);
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
        <ChartCard title="CPU" right="38% · 1.4 GHz" series={[{ data: cpu, color: "var(--accent)" }]} max={100} />
        <ChartCard title="Memory" right="9.8 / 16 GB" series={[{ data: mem, color: "oklch(0.6 0.13 280)" }]} max={100} />
        <ChartCard title="Network" right="↓ 31 · ↑ 17 MB/s" series={[
          { data: netDown, color: "var(--good)" }, { data: netUp, color: "var(--accent)" }]
          } max={80} />
        <ChartCard title="Disk I/O" right="22 MB/s read" series={[{ data: disk, color: "var(--warn)" }]} max={100} />
      </div>
      <div className="card">
        <div className="card-h">
          <h3>Per-disk health</h3>
          <div className="spacer" />
          <span className="meta">2 disks · btrfs raid1 · last scrub 3d ago</span>
        </div>
        <div className="card-b">
          <DiskRow name="WD Red 4TB" path="/dev/sda" used={1.8} total={4} temp={42} health="ok" />
          <DiskRow name="WD Red 4TB" path="/dev/sdb" used={1.8} total={4} temp={44} health="ok" />
          <DiskRow name="Samsung 970 1TB" path="/dev/nvme0" used={0.6} total={1} temp={51} health="warn" note="51 °C — fan may need cleaning" />
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
  function DiskRow({ name, path, used, total, temp, health, note }) {
    const pct = used / total * 100;
    return (
      <div style={{ padding: "10px 0", borderBottom: "1px solid var(--rule)" }}>
      <div className="row" style={{ justifyContent: "space-between", marginBottom: 6 }}>
        <div className="row">
          <span style={{ fontWeight: 500 }}>{name}</span>
          <span className="chip">{path}</span>
          <span className={cx("pill", health === "ok" ? "ok" : "warn")}><span className="d" />{health === "ok" ? "healthy" : "warm"}</span>
          {note && <span style={{ fontSize: 11.5, color: "var(--ink-3)" }}>{note}</span>}
        </div>
        <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--ink-2)" }}>
          {used} / {total} TB · {temp} °C
        </span>
      </div>
      <div className="prog"><i style={{ width: pct + "%" }} /></div>
    </div>);

  }

  /* ═════════ Nodes (live host card) ═════════ */
  function Nodes({ live }) {
    const system = (live && live.system) || {};
    const speed = (live && live.speed) || {};
    const qbt = (live && live.qbt) || {};
    const ddns = (live && live.ddns) || {};
    const self = (live && live.self) || {};
    const memTotal = Number(system.mem_total || 0);
    const memUsed = Number(system.mem_used || 0);
    const node = {
      id: String(system.hostname || "ubuntu-server"),
      role: "primary",
      os: "Ubuntu server",
      uptime: String(system.uptime_human || "-"),
      cpu: Math.max(0, Math.min(100, Number(system.load1 || 0) * 10)),
      mem: memTotal > 0 ? Math.max(0, Math.min(100, memUsed * 100 / memTotal)) : 0,
      net: Number(speed.rx_mibps || 0) + Number(speed.tx_mibps || 0),
      services: [qbt, ddns, self].filter((x) => String(x.active_state || "") === "active").length,
      disk: `${system.disk_used_human || "0B"} / ${system.disk_total_human || "0B"}`,
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
          <NodeActivityRow t={new Date().toTimeString().slice(0, 5)} who={node.id} what={`HTTPD: ${String(self.detail || "-")}`} />
        </div>
      </div>
    </div>);

  }
  function NodeCard({ n }) {
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
        <div className="meter"><span className="name">CPU</span><div className="prog"><i style={{ width: n.cpu + "%", background: n.cpu > 70 ? "var(--bad)" : "var(--accent)" }} /></div><span className="v">{n.cpu}%</span></div>
        <div className="meter" style={{ marginTop: 6 }}><span className="name">Memory</span><div className="prog"><i style={{ width: n.mem + "%", background: n.mem > 85 ? "var(--bad)" : "var(--accent)" }} /></div><span className="v">{n.mem}%</span></div>
        <div className="meter" style={{ marginTop: 6 }}><span className="name">Net</span><div className="prog"><i style={{ width: Math.min(100, n.net * 2) + "%", background: "var(--good)" }} /></div><span className="v">{n.net} MB/s</span></div>
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

  /* ═════════ Docker (variant A — container list) ═════════ */
  const CONTAINERS = [
  { name: "plex", image: "plex/plex:1.40", status: "running", uptime: "12d", cpu: 14, mem: 1.4, ports: "32400/tcp" },
  { name: "qbittorrent", image: "lsio/qbittorrent", status: "running", uptime: "12d", cpu: 3, mem: 0.4, ports: "8080,6881" },
  { name: "homepage", image: "ghcr.io/gethomepage", status: "running", uptime: "30d", cpu: 1, mem: 0.1, ports: "3000/tcp" },
  { name: "duckdns", image: "lsio/duckdns", status: "running", uptime: "30d", cpu: 0, mem: 0.0, ports: "—" },
  { name: "vaultwarden", image: "vaultwarden/server", status: "running", uptime: "12d", cpu: 1, mem: 0.2, ports: "80,3012" },
  { name: "actualbudget", image: "actualbudget/actual", status: "stopped", uptime: "—", cpu: 0, mem: 0.0, ports: "5006" },
  { name: "minecraft", image: "itzg/minecraft-server", status: "warn", uptime: "2d", cpu: 71, mem: 5.2, ports: "25565" },
  { name: "syncthing", image: "syncthing/syncthing", status: "running", uptime: "30d", cpu: 2, mem: 0.3, ports: "8384,22000" }];

  function Docker() {
    const [tab, setTab] = useState("Containers");
    return (
      <div className="col">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div>
          <h1 className="h1">Docker</h1>
          <p className="sub">{CONTAINERS.filter((c) => c.status !== "stopped").length} running · {CONTAINERS.length} total · 6.4 GB images.</p>
        </div>
        <div className="row">
          <button className="btn">Pull image</button>
          <button className="btn primary">{Ic.plus}<span style={{ marginLeft: 4 }}>New container</span></button>
        </div>
      </div>
      <div className="card">
        <div className="tablist" style={{ padding: "0 12px" }}>
          {["Containers", "Images", "Volumes", "Compose", "Logs"].map((t) =>
            <div key={t} className={cx("tab", tab === t && "on")} onClick={() => setTab(t)}>{t}</div>
            )}
        </div>
        {tab === "Containers" &&
          <table className="tbl">
            <thead><tr>
              <th></th><th>Name</th><th>Image</th><th>Status</th>
              <th style={{ textAlign: "right" }}>CPU</th>
              <th style={{ textAlign: "right" }}>Memory</th>
              <th>Ports</th><th>Uptime</th><th></th>
            </tr></thead>
            <tbody>
              {CONTAINERS.map((c) =>
              <tr key={c.name}>
                  <td><input type="checkbox" /></td>
                  <td className="k">{c.name}</td>
                  <td style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--ink-3)" }}>{c.image}</td>
                  <td>
                    {c.status === "running" && <span className="pill ok"><span className="d" />up</span>}
                    {c.status === "stopped" && <span className="pill idle"><span className="d" />stopped</span>}
                    {c.status === "warn" && <span className="pill warn"><span className="d" />oom risk</span>}
                  </td>
                  <td style={{ textAlign: "right", fontFamily: "var(--font-mono)", fontSize: 11 }}>{c.cpu}%</td>
                  <td style={{ textAlign: "right", fontFamily: "var(--font-mono)", fontSize: 11 }}>{c.mem.toFixed(1)} GB</td>
                  <td style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--ink-3)" }}>{c.ports}</td>
                  <td style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--ink-3)" }}>{c.uptime}</td>
                  <td>
                    <div className="row" style={{ gap: 4, justifyContent: "flex-end" }}>
                      <button className="btn sm icon" title="Restart">{Ic.restart}</button>
                      <button className="btn sm icon" title={c.status === "running" ? "Stop" : "Start"}>{c.status === "running" ? Ic.stop : Ic.play}</button>
                      <button className="btn sm icon" title="Logs">{Ic.term}</button>
                    </div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
          }
        {tab !== "Containers" &&
          <div className="card-b" style={{ padding: 32, textAlign: "center", color: "var(--ink-3)", fontFamily: "var(--font-mono)" }}>
            {tab} view — switch back to Containers to see the list.
          </div>
          }
      </div>
    </div>);

  }

  /* ═════════ Web terminal (variant A — single shell + keys) ═════════ */
  function Terminal({ toast }) {
    const [tab, setTab] = useState("term");
    return (
      <div className="col">
      <div>
        <h1 className="h1">Web terminal</h1>
        <p className="sub">Shell access to nas-01 with managed SSH keys.</p>
      </div>
      <div className="card">
        <div className="tablist" style={{ padding: "0 12px" }}>
          <div className={cx("tab", tab === "term" && "on")} onClick={() => setTab("term")}>Shell</div>
          <div className={cx("tab", tab === "keys" && "on")} onClick={() => setTab("keys")}>SSH keys (4)</div>
          <div className={cx("tab", tab === "history" && "on")} onClick={() => setTab("history")}>History</div>
        </div>
        {tab === "term" && <ShellPanel toast={toast} />}
        {tab === "keys" && <KeysPanel toast={toast} />}
        {tab === "history" && <HistoryPanel />}
      </div>
    </div>);

  }
  function ShellPanel({ toast }) {
    const [lines, setLines] = useState([
    { t: "out", v: <><span className="acc">will@nas-01</span><span className="dim">:~$ </span><span>uptime</span></> },
    { t: "out", v: <span className="dim"> 14:33:01 up 23 days, 11:42, 2 users, load average: 0.42, 0.38, 0.31</span> },
    { t: "out", v: <><span className="acc">will@nas-01</span><span className="dim">:~$ </span><span>docker ps --format "&#123;&#123;.Names&#125;&#125; &#123;&#123;.Status&#125;&#125;"</span></> },
    { t: "out", v: <span>plex          Up 12 days{"\n"}qbittorrent   Up 12 days{"\n"}minecraft     <span className="warn">Up 2 days (high mem)</span>{"\n"}vaultwarden   Up 12 days</span> },
    { t: "out", v: <><span className="acc">will@nas-01</span><span className="dim">:~$ </span><span>df -h /mnt/data</span></> },
    { t: "out", v: <span>Filesystem  Size  Used  Avail  Use%  Mounted on{"\n"}/dev/md0   8.0T  2.4T  5.4T   <span className="ok">31%</span>  /mnt/data</span> }]
    );
    const [val, setVal] = useState("");
    const inputRef = useRef();
    const submit = (e) => {
      e?.preventDefault?.();
      if (!val.trim()) return;
      const v = val.trim();
      const out = [{ t: "out", v: <><span className="acc">will@nas-01</span><span className="dim">:~$ </span><span>{v}</span></> }];
      let resp = null;
      if (v === "ls" || v === "ls -la") resp = "src  assets  build  package.json  README.md  preview.mp4  design-spec.pdf";else
      if (v.startsWith("docker")) resp = <span><span className="dim">8 containers running.</span></span>;else
      if (v === "whoami") resp = "will";else
      if (v === "clear") {setLines([]);setVal("");return;} else
      resp = <span className="err">{v.split(" ")[0]}: command not found (demo shell)</span>;
      if (resp) out.push({ t: "out", v: resp });
      setLines((L) => [...L, ...out]);
      setVal("");
    };
    useEffect(() => {inputRef.current?.focus();}, []);
    return (
      <div className="card-b">
      <div className="row" style={{ justifyContent: "space-between", marginBottom: 8 }}>
        <span className="meta" style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--ink-3)" }}>
          will@nas-01 · /home/will · bash 5.2
        </span>
        <div className="row">
          <button className="btn sm" onClick={() => toast("Session locked")}>Lock session</button>
          <button className="btn sm" onClick={() => setLines([])}>Clear</button>
        </div>
      </div>
      <div className="term" style={{ minHeight: 320, maxHeight: 380 }}>
        {lines.map((l, i) => <div key={i} style={{ whiteSpace: "pre-wrap" }}>{l.v}</div>)}
        <form onSubmit={submit} style={{ display: "flex", alignItems: "center" }}>
          <span><span className="acc">will@nas-01</span><span className="dim">:~$ </span></span>
          <input ref={inputRef} value={val} onChange={(e) => setVal(e.target.value)}
            style={{ flex: 1, background: "transparent", border: 0, outline: 0, font: "inherit", color: "var(--ink)" }} />
          <span className="cursor" />
        </form>
      </div>
      <div style={{ marginTop: 8, fontFamily: "var(--font-mono)", fontSize: 10.5, color: "var(--ink-3)" }}>
        try: <span style={{ color: "var(--accent)" }}>ls</span>, <span style={{ color: "var(--accent)" }}>whoami</span>, <span style={{ color: "var(--accent)" }}>docker</span>, <span style={{ color: "var(--accent)" }}>clear</span>
      </div>
    </div>);

  }
  const KEYS = [
  { name: "studio-mbp", type: "ed25519", added: "2025-09-04", lastUsed: "2m ago" },
  { name: "iphone (termius)", type: "ed25519", added: "2025-08-12", lastUsed: "yesterday" },
  { name: "edge-pi", type: "rsa-4096", added: "2024-12-01", lastUsed: "3h ago" },
  { name: "old-laptop", type: "rsa-2048", added: "2023-06-19", lastUsed: "never", warn: true }];

  function KeysPanel({ toast }) {
    return (
      <table className="tbl">
      <thead><tr><th>Name</th><th>Type</th><th>Added</th><th>Last used</th><th></th></tr></thead>
      <tbody>
        {KEYS.map((k) =>
          <tr key={k.name}>
            <td className="k">{k.name} {k.warn && <span className="pill warn" style={{ marginLeft: 6 }}><span className="d" />weak</span>}</td>
            <td style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--ink-3)" }}>{k.type}</td>
            <td style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--ink-3)" }}>{k.added}</td>
            <td style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--ink-3)" }}>{k.lastUsed}</td>
            <td><div className="row" style={{ justifyContent: "flex-end", gap: 4 }}>
              <button className="btn sm" onClick={() => toast("Public key copied")}>{Ic.copy}<span style={{ marginLeft: 4 }}>copy</span></button>
              <button className="btn sm danger">revoke</button>
            </div></td>
          </tr>
          )}
      </tbody>
    </table>);

  }
  function HistoryPanel() {
    const items = [
    { t: "14:33", cmd: "df -h /mnt/data" },
    { t: "14:32", cmd: 'docker ps --format "{{.Names}} {{.Status}}"' },
    { t: "14:31", cmd: "uptime" },
    { t: "11:08", cmd: "tail -f /var/log/nginx/access.log" },
    { t: "yesterday", cmd: "rsync -av ~/projects/ /mnt/cold/projects/" }];

    return (
      <table className="tbl">
      <thead><tr><th style={{ width: 90 }}>When</th><th>Command</th><th></th></tr></thead>
      <tbody>{items.map((it, i) =>
          <tr key={i}>
          <td style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--ink-3)" }}>{it.t}</td>
          <td className="k">{it.cmd}</td>
          <td style={{ textAlign: "right" }}><button className="btn sm">re-run</button></td>
        </tr>
          )}</tbody>
    </table>);

  }

  /* ═════════ Services (variant A — service cards) ═════════ */
  function Services({ services, toggleService }) {
    return (
      <div className="col">
      <div>
        <h1 className="h1">Services</h1>
        <p className="sub">Background services running on nas-01.</p>
      </div>
      <div className="grid-3">
        {services.map((s) => <ServiceCard key={s.id} s={s} toggle={() => toggleService(s.id)} />)}
      </div>
    </div>);

  }
  function ServiceCard({ s, toggle }) {
    return (
      <div className="card">
      <div className="card-h">
        <h3>{s.name}</h3>
        <span className={cx("pill", s.on ? s.warn ? "warn" : "ok" : "idle")}><span className="d" />{s.on ? s.warn ? "warn" : "running" : "stopped"}</span>
        <div className="spacer" />
        <div className={cx("tog", s.on && "on")} onClick={toggle} />
      </div>
      <div className="card-b">
        <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--ink-3)", marginBottom: 8 }}>{s.detail}</div>
        <div className="row" style={{ justifyContent: "space-between" }}>
          <span className="chip">{s.kind}</span>
          {s.exposed && <span className="pill public" title="Reachable from the internet"><span className="d" />public</span>}
          {!s.exposed && <span className="pill lan"><span className="d" />LAN</span>}
        </div>
        <div className="row" style={{ marginTop: 12, gap: 4 }}>
          <button className="btn sm">{Ic.restart}<span style={{ marginLeft: 4 }}>restart</span></button>
          <button className="btn sm">{Ic.term}<span style={{ marginLeft: 4 }}>logs</span></button>
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
    const loadHistory = async () => {
      const d = await apiJson("/api/history?id=pub&limit=100");
      const rows = Array.isArray(d.items) ? d.items : [];
      setItems(rows.map((it) => ({
        id: it.id,
        who: "shareclip",
        t: String(it.updated_at || "").replace("T", " ").slice(5, 16),
        text: it.type === "text" ? String(it.text || "") : "",
        attach: it.type === "image" ? String(it.image_filename || "image") : "",
        mine: false,
      })));
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
    return (
      <div className="col">
      <div>
        <h1 className="h1">ShareClip</h1>
        <p className="sub">A shared clipboard for everyone on the box. End-to-end encrypted between nodes.</p>
      </div>
      <div className="card" style={{ display: "flex", flexDirection: "column", maxHeight: 600 }}>
        <div className="card-h">
          <h3>shared-with-studio</h3>
          <span className="meta">3 members · synced just now</span>
          <div className="spacer" />
          <button className="btn sm">copy invite link</button>
        </div>
        <div style={{ padding: "16px 16px 8px", overflowY: "auto", flex: 1, display: "flex", flexDirection: "column", gap: 12, minHeight: 360 }}>
          {!items.length && <div style={{ color: "var(--ink-3)", fontSize: 12 }}>No ShareClip records yet.</div>}
          {items.map((m, i) =>
            <div key={i} style={{ display: "flex", flexDirection: "column", alignItems: m.mine ? "flex-end" : "flex-start", gap: 4 }}>
              <div className="row" style={{ gap: 6, fontSize: 11.5, color: "var(--ink-3)", fontFamily: "var(--font-mono)" }}>
                <span style={{ color: "var(--ink-2)", fontWeight: 600 }}>{m.who}</span>
                <span>· {m.t}</span>
              </div>
              <div style={{
                background: m.mine ? "var(--accent-soft)" : "var(--paper-2)",
                padding: "8px 12px", borderRadius: 12,
                borderTopRightRadius: m.mine ? 4 : 12,
                borderTopLeftRadius: m.mine ? 12 : 4,
                maxWidth: 480,
                border: "1px solid var(--rule)"
              }}>
                <div style={{ fontSize: 12.5, color: "var(--ink)" }}>{m.text}</div>
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
                    <button className="btn sm">download</button>
                  </div>
                }
              </div>
            </div>
            )}
        </div>
        <form onSubmit={send} style={{ display: "flex", gap: 8, padding: 12, borderTop: "1px solid var(--rule)" }}>
          <button type="button" className="btn icon" onClick={() => toast("Drop a file anywhere on this page to share")}>{Ic.upload}</button>
          <input className="input" placeholder="Paste a clip, snippet, or drop a file…" value={v} onChange={(e) => setV(e.target.value)} />
          <button type="submit" className="btn primary" disabled={sending}>{sending ? "Sharing..." : "Share"}</button>
        </form>
      </div>
    </div>);

  }

  /* ═════════ Settings (variant A — module toggles) ═════════ */
  const MODULES = [
  { id: "files", name: "File browser", on: true, desc: "Browse, share, and upload files via the web." },
  { id: "trans", name: "Transfer pipeline", on: true, desc: "qBittorrent + http upload + remote pull." },
  { id: "monitor", name: "System monitor", on: true, desc: "CPU, memory, disk, network and temperatures." },
  { id: "docker", name: "Docker control", on: true, desc: "Start, stop, and configure containers." },
  { id: "term", name: "Web terminal", on: true, desc: "Browser-based shell access to this host." },
  { id: "share", name: "ShareClip", on: true, desc: "Shared clipboard between nodes." },
  { id: "ddns", name: "DDNS", on: true, desc: "Keep your domain pointed at this box." },
  { id: "remote", name: "Remote access", on: false, desc: "Expose AfterClaw beyond your LAN." },
  { id: "experimental", name: "Cluster (multi-node)", on: false, beta: true, desc: "Manage multiple AfterClaw nodes from one panel." }];

  function Settings() {
    const [mods, setMods] = useState(MODULES);
    const tog = (id) => setMods((M) => M.map((m) => m.id === id ? { ...m, on: !m.on } : m));
    return (
      <div className="col">
      <div>
        <h1 className="h1">Settings</h1>
        <p className="sub">Turn modules on or off. Anything below the line is opt-in.</p>
      </div>
      <div className="card">
        <div className="card-h"><h3>Core modules</h3><div className="spacer" /><span className="meta">always available</span></div>
        <div className="card-b" style={{ padding: 0 }}>
          {mods.filter((m) => !m.beta && m.id !== "remote").map((m, i) => <ModRow key={m.id} m={m} i={i} tog={tog} />)}
        </div>
      </div>
      <div className="card">
        <div className="card-h"><h3>Optional / experimental</h3><div className="spacer" /><span className="meta">opt-in</span></div>
        <div className="card-b" style={{ padding: 0 }}>
          {mods.filter((m) => m.beta || m.id === "remote").map((m, i) => <ModRow key={m.id} m={m} i={i} tog={tog} />)}
        </div>
      </div>
      <div className="card">
        <div className="card-h"><h3>Identity</h3><div className="spacer" /></div>
        <div className="card-b">
          <SettingRow label="Hostname" v="nas-01" mono />
          <SettingRow label="Domain" v="afterclaw.duckdns.org" mono />
          <SettingRow label="Time zone" v="Europe/Berlin" />
          <SettingRow label="Theme" v="dim — controlled via Tweaks panel" />
        </div>
      </div>
    </div>);

  }
  function ModRow({ m, i, tog }) {
    return (
      <div className="row" style={{ padding: "12px 16px", gap: 14, borderTop: i ? "1px solid var(--rule)" : "0" }}>
      <div style={{ flex: 1 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontWeight: 500, color: "var(--ink)" }}>{m.name}</span>
          {m.beta && <span className="chip" style={{ color: "var(--warn)" }}>beta</span>}
        </div>
        <div style={{ fontSize: 12, color: "var(--ink-3)", marginTop: 2 }}>{m.desc}</div>
      </div>
      <div className={cx("tog", m.on && "on")} onClick={() => tog(m.id)} />
    </div>);

  }
  function SettingRow({ label, v, mono }) {
    return (
      <div className="row" style={{ padding: "8px 0", borderTop: "1px solid var(--rule)" }}>
      <span style={{ width: 140, fontSize: 12.5, color: "var(--ink-3)" }}>{label}</span>
      <span style={{ flex: 1, fontSize: 12.5, color: "var(--ink)", fontFamily: mono ? "var(--font-mono)" : "inherit" }}>{v}</span>
      <button className="btn sm ghost">edit</button>
    </div>);

  }

  /* ═════════ App shell ═════════ */
  const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
    "theme": "light",
    "density": "cozy"
  } /*EDITMODE-END*/;

  function App() {
    const [section, setSection] = useState("dash");
    const [toasts, setToasts] = useState([]);
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
    const t = (window.useTweaks || (() => [{ ...TWEAK_DEFAULTS, theme: initTheme }, () => {}, () => {}]))({ ...TWEAK_DEFAULTS, theme: initTheme });
    const tweaks = t[0];
    const setTweak = t[1];

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
    const [services, setServices] = useState([]);
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
              text: it.type === "text" ? String(it.text || "") : (it.image_filename ? `image: ${it.image_filename}` : "image"),
              attach: it.type === "image" ? String(it.image_filename || "image") : "",
            })) : [],
          };
          setLive(nextLive);
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
              detail: String(nextLive.self.detail || ""),
              kind: "web",
              exposed: String((nextLive.http_access || {}).effective_mode || "") === "public",
            }
          ]);
        } catch (e) {
          if (!dead) toast(`Live data refresh failed: ${e.message || e}`);
        }
      };
      pull();
      const tk = setInterval(pull, 2500);
      return () => { dead = true; clearInterval(tk); };
    }, []);

    /* tweak side-effects: theme + density */
    useEffect(() => {
      const themeNow = tweaks.theme || "light";
      document.documentElement.setAttribute("data-theme", themeNow);
      try {localStorage.setItem("fc-theme", themeNow);} catch (_) {}
      const d = tweaks.density || "cozy";
      const main = document.querySelector(".main");
      if (main) main.style.padding = d === "compact" ? "12px 16px 24px" : d === "roomy" ? "26px 30px 50px" : "18px 22px 36px";
    }, [tweaks.theme, tweaks.density]);

    const renderSection = () => {
      switch (section) {
        case "dash":return <Dashboard services={services} toggleService={toggleService} transfers={transfers} goto={setSection} toast={toast} live={live} />;
        case "files":return <Files pushTransfer={pushTransfer} />;
        case "monitor":return <Monitor />;
        case "nodes":return <Nodes live={live} />;
        case "docker":return <Docker />;
        case "term":return <Terminal toast={toast} />;
        case "services":return <Services services={services} toggleService={toggleService} />;
        case "share":return <ShareClip toast={toast} />;
        case "settings":return <Settings />;
      }
    };

    return (
      <div className="app" data-screen-label={`AfterClaw — ${SECTIONS.find((s) => s.id === section)?.label}`}>
      <Topbar section={section} theme={tweaks.theme} setTheme={(t) => setTweak("theme", t)} live={live} />
      <Sidebar active={section} onNav={setSection} />
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
      {window.TweaksPanel &&
        <window.TweaksPanel title="Tweaks">
          <window.TweakSection label="Appearance">
            <window.TweakRadio label="Theme" value={tweaks.theme}
            options={[
            { value: "light", label: "Light" },
            { value: "dim", label: "Dim" },
            { value: "dark", label: "Dark" }]
            }
            onChange={(v) => setTweak("theme", v)} />
            <window.TweakRadio label="Density" value={tweaks.density}
            options={[
            { value: "compact", label: "Compact" },
            { value: "cozy", label: "Cozy" },
            { value: "roomy", label: "Roomy" }]
            }
            onChange={(v) => setTweak("density", v)} />
          </window.TweakSection>
        </window.TweaksPanel>
        }
    </div>);

  }

  return { App };
}();

ReactDOM.createRoot(document.getElementById("root")).render(<window.AfterClaw.App />);
