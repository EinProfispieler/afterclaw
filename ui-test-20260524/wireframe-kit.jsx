/* global React */
// Tiny shared kit of wireframe atoms used by every surface. All sizing is
// done with CSS custom-properties (--pad, --gap) so density tweaks cascade.

const { useState } = React;

// ── Frame: simulated viewport for one wireframe ──────────────────────
function WFFrame({ children, theme, density, style }) {
  // theme/density are inherited from the page-level data-attrs in app.jsx,
  // but each frame can override (we don't, today).
  return (
    <div className="wf" style={style}>{children}</div>
  );
}

// ── Topbar with brand + nav + LAN/public exposure pill ──────────────
function WFTop({ active = 'Dashboard', exposure = 'lan', tabs = ['Dashboard','Files','Monitor','Services','Nodes','Terminal','Settings'] }) {
  return (
    <div className="wf-top">
      <div className="brand"><span className="glyph"></span>afterclaw</div>
      <nav>
        {tabs.map(t => <a key={t} className={t === active ? 'active' : ''}>{t}</a>)}
      </nav>
      <div className="right">
        {exposure === 'lan'
          ? <span className="pill lan"><span className="d"></span>LAN ONLY</span>
          : <span className="pill public"><span className="d"></span>PUBLIC EXPOSED</span>}
        <span className="pill idle" style={{fontFamily:'var(--font-mono)'}}>v0.9.7</span>
      </div>
    </div>
  );
}

// ── Sidebar nav ──────────────────────────────────────────────────────
function WFSide({ active = 'overview', items }) {
  const groups = items || [
    { group: 'CONTROL', items: [
      ['overview', 'Overview'], ['transfers', 'Transfers'], ['files', 'Files'], ['shareclip', 'ShareClip'],
    ]},
    { group: 'SYSTEM', items: [
      ['monitor', 'Monitor'], ['docker', 'Docker'], ['terminal', 'Terminal'],
    ]},
    { group: 'NETWORK', items: [
      ['ddns', 'DDNS'], ['nodes', 'Nodes'], ['settings', 'Settings'],
    ]},
  ];
  return (
    <aside className="wf-side">
      {groups.map(g => (
        <React.Fragment key={g.group}>
          <div className="group">{g.group}</div>
          {g.items.map(([k, label]) =>
            <a key={k} className={k === active ? 'active' : ''}><span className="dot"></span>{label}</a>)}
        </React.Fragment>
      ))}
    </aside>
  );
}

// ── Box / card ───────────────────────────────────────────────────────
function Box({ title, meta, children, ghost, tinted, style, className = '' }) {
  return (
    <div className={`box ${ghost ? 'ghost' : ''} ${tinted ? 'tinted' : ''} ${className}`} style={style}>
      {(title || meta) && (
        <div className="box-h">
          {title && <span className="t">{title}</span>}
          {meta && <span className="meta">{meta}</span>}
        </div>
      )}
      {children}
    </div>
  );
}

// ── Stat tile ────────────────────────────────────────────────────────
function Stat({ label, v, u, sub }) {
  return (
    <div className="stat">
      <div className="label">{label}</div>
      <div className="v">{v}{u && <span className="u">{u}</span>}</div>
      {sub && <div className="sub">{sub}</div>}
    </div>
  );
}

// ── Pill ─────────────────────────────────────────────────────────────
function Pill({ tone = 'ok', children }) {
  return <span className={`pill ${tone}`}><span className="d"></span>{children}</span>;
}

// ── Sticky note ──────────────────────────────────────────────────────
function Sticky({ children, style, rotate = -2 }) {
  return (
    <div className="sticky" style={{ ...style, transform: `rotate(${rotate}deg)` }}>{children}</div>
  );
}

// ── Annotation arrow + label (hand-drawn) ────────────────────────────
function Note({ children, style, arrow }) {
  // arrow: { d: 'M0,0 C20,10 40,5 60,18', flip?: bool }
  return (
    <div className="note" style={style}>
      {arrow && (
        <svg width={arrow.w || 60} height={arrow.h || 30} style={{position:'absolute', left: arrow.x ?? -50, top: arrow.y ?? 8}}>
          <path d={arrow.d} fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
          <path d={arrow.head || ''} fill="currentColor" />
        </svg>
      )}
      {children}
    </div>
  );
}

// ── Sparkline (simple polyline) ──────────────────────────────────────
function Spark({ pts = [3,5,4,7,6,8,7,9,8,11,9,12,10,13,12,11,14,13,16,15], w = 120, h = 28, accent = false }) {
  const max = Math.max(...pts), min = Math.min(...pts);
  const span = max - min || 1;
  const step = w / (pts.length - 1);
  const d = pts.map((p, i) => `${i ? 'L' : 'M'}${(i*step).toFixed(1)},${(h - ((p-min)/span)*h).toFixed(1)}`).join(' ');
  return (
    <svg width={w} height={h} style={{display:'block'}}>
      <path d={d} fill="none" stroke={accent ? 'var(--accent)' : 'var(--ink-2)'} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

// ── Area chart ───────────────────────────────────────────────────────
function AreaChart({ pts, w = 360, h = 110, accent = true, label, gridLabels }) {
  const max = Math.max(...pts), min = Math.min(...pts);
  const span = max - min || 1;
  const step = w / (pts.length - 1);
  const line = pts.map((p, i) => `${i ? 'L' : 'M'}${(i*step).toFixed(1)},${(h - ((p-min)/span)*h*0.85 - 4).toFixed(1)}`).join(' ');
  const area = `${line} L${w},${h} L0,${h} Z`;
  return (
    <svg width="100%" viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" style={{display:'block'}}>
      {/* gridlines */}
      {[0.25, 0.5, 0.75].map(g => (
        <line key={g} x1="0" x2={w} y1={h*g} y2={h*g}
          stroke="var(--rule-ghost)" strokeWidth="1" strokeDasharray="3 4" />
      ))}
      <path d={area} fill={accent ? 'var(--accent-soft)' : 'var(--rule-ghost)'} />
      <path d={line} fill="none" stroke={accent ? 'var(--accent)' : 'var(--ink-2)'} strokeWidth="1.5" />
      {gridLabels && gridLabels.map((g, i) => (
        <text key={i} x={(i / (gridLabels.length - 1)) * w} y={h - 2}
          fill="var(--ink-3)" fontSize="9" fontFamily="var(--font-mono)"
          textAnchor={i === 0 ? 'start' : i === gridLabels.length - 1 ? 'end' : 'middle'}>
          {g}
        </text>
      ))}
    </svg>
  );
}

// ── Donut gauge ──────────────────────────────────────────────────────
function Donut({ pct = 42, label, size = 76, accent = true }) {
  const r = size / 2 - 8, c = size / 2;
  const C = 2 * Math.PI * r;
  return (
    <div style={{display:'flex', flexDirection:'column', alignItems:'center', gap: 4}}>
      <svg width={size} height={size}>
        <circle cx={c} cy={c} r={r} fill="none" stroke="var(--rule-ghost)" strokeWidth="6" />
        <circle cx={c} cy={c} r={r} fill="none"
          stroke={accent ? 'var(--accent)' : 'var(--ink)'}
          strokeWidth="6" strokeLinecap="round"
          strokeDasharray={`${(C * pct/100).toFixed(1)} ${C}`}
          transform={`rotate(-90 ${c} ${c})`} />
        <text x={c} y={c+5} textAnchor="middle"
          fill="var(--ink)" fontSize="18" fontFamily="var(--font-hand)" fontWeight="700">
          {pct}%
        </text>
      </svg>
      {label && <div style={{fontFamily:'var(--font-mono)', fontSize: 10, color:'var(--ink-2)', letterSpacing:'.06em', textTransform:'uppercase'}}>{label}</div>}
    </div>
  );
}

// ── Meter (named horizontal bar) ─────────────────────────────────────
function Meter({ name, pct = 50, value, accent }) {
  return (
    <div className="meter">
      <span className="name">{name}</span>
      <span className="prog"><i style={{width: pct + '%', background: accent ? 'var(--accent)' : 'var(--ink-2)'}}></i></span>
      <span className="v">{value || pct + '%'}</span>
    </div>
  );
}

// ── Progress bar (transfer) ──────────────────────────────────────────
function Prog({ pct = 50, striped }) {
  return <span className={`prog ${striped ? 'striped' : ''}`}><i style={{width: pct + '%'}}></i></span>;
}

// ── Button ───────────────────────────────────────────────────────────
function Btn({ children, primary, ghost, style }) {
  return <button className={`btn ${primary ? 'primary' : ''} ${ghost ? 'ghost' : ''}`} style={style}>{children}</button>;
}

// ── Toggle ───────────────────────────────────────────────────────────
function Tog({ on }) { return <span className={`tog ${on ? 'on' : ''}`}></span>; }

// ── Bars (lorem placeholder) ─────────────────────────────────────────
function Bars({ widths = [80,60,90,40] }) {
  return <div className="bars">{widths.map((w,i) => <span key={i} className="bar" style={{width: w + '%'}}></span>)}</div>;
}

// ── Scrawl headline (handwritten with squiggle underline) ────────────
function Scrawl({ children, style }) {
  return <span className="scrawl" style={style}>{children}</span>;
}

// Expose to other Babel scripts
Object.assign(window, {
  WFFrame, WFTop, WFSide, Box, Stat, Pill, Sticky, Note, Spark, AreaChart,
  Donut, Meter, Prog, Btn, Tog, Bars, Scrawl,
});
