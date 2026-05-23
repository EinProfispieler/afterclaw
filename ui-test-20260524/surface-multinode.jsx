/* global React, WFTop, WFSide, Box, Pill, Sticky, Note, Spark, Meter, Prog, Btn, Tog, Scrawl */

// Multi-node panel — 3 variants
//   A · Node cards          — master + workers as a card grid
//   B · Topology map        — circles connected by lines (surprising)
//   C · Aggregator table    — every node a row, dense spreadsheet

const NODES = [
  { name: 'mac-mini',   role: 'master',   ip: '10.0.1.10',  uptime: '12d 04h', cpu: 32, mem: 52, disk: 71, temp: 48, status: 'ok',   svc: 5, alerts: 0 },
  { name: 'thinkpad-x230', role: 'worker', ip: '10.0.1.21', uptime: '4d 11h',  cpu: 12, mem: 28, disk: 44, temp: 41, status: 'ok',   svc: 3, alerts: 0 },
  { name: 'nas-02',     role: 'worker',   ip: '10.0.1.30',  uptime: '37d 02h', cpu: 8,  mem: 18, disk: 88, temp: 39, status: 'warn', svc: 4, alerts: 1 },
  { name: 'pi4-shed',   role: 'worker',   ip: '10.0.1.42',  uptime: '02h 18m', cpu: 22, mem: 38, disk: 24, temp: 56, status: 'err',  svc: 2, alerts: 2 },
];

// ─── A · Node cards ─────────────────────────────────────────────────
function Nodes_Cards() {
  return (
    <WFFrame>
      <WFTop active="Nodes" exposure="lan" />
      <div className="wf-body">
        <WFSide active="nodes" />
        <main className="wf-main" style={{padding:'var(--pad)', display:'flex', flexDirection:'column', gap:'var(--gap)'}}>
          <div style={{display:'flex', alignItems:'baseline', gap: 14}}>
            <Scrawl style={{fontSize: 26}}>cluster</Scrawl>
            <span style={{fontFamily:'var(--font-mono)', fontSize:11, color:'var(--ink-3)'}}>4 nodes · 1 anomaly · last sync 3s ago</span>
            <span style={{flex:1}}></span>
            <Btn>＋ add node</Btn>
            <Btn primary>broadcast cmd</Btn>
          </div>
          <div style={{display:'grid', gridTemplateColumns:'repeat(4, 1fr)', gap:'var(--gap)', flex: 1, minHeight: 0}}>
            {NODES.map((n, i) => (
              <Box key={i} className={n.role === 'master' ? '' : ''} style={{display:'flex', flexDirection:'column', gap: 8, borderWidth: n.role==='master' ? 2 : 1.5}}>
                <div style={{display:'flex', alignItems:'baseline', gap: 6}}>
                  <span style={{fontFamily:'var(--font-hand)', fontSize: 22, fontWeight:700}}>{n.name}</span>
                  {n.role === 'master' && <Pill tone="ok">master</Pill>}
                </div>
                <div style={{fontFamily:'var(--font-mono)', fontSize: 10.5, color:'var(--ink-3)'}}>{n.ip} · up {n.uptime}</div>
                <Pill tone={n.status}>{n.status === 'err' ? `${n.alerts} alerts` : n.status === 'warn' ? '1 alert' : 'healthy'}</Pill>
                <div className="div-cap">vitals</div>
                <Meter name="cpu"  pct={n.cpu}  accent />
                <Meter name="mem"  pct={n.mem} />
                <Meter name="disk" pct={n.disk} />
                <Meter name="°C"   pct={n.temp} value={`${n.temp}°`} accent={n.temp > 50} />
                <div className="div-cap">services · {n.svc}</div>
                <div style={{display:'flex', flexWrap:'wrap', gap: 4}}>
                  {['qbit','ddns','http','clip','term'].slice(0, n.svc).map(s => (
                    <span key={s} className="pill idle" style={{padding:'1px 6px', fontSize:10, color:'var(--ink-2)'}}>{s}</span>
                  ))}
                </div>
                <div style={{display:'flex', gap: 4, marginTop: 'auto'}}>
                  <Btn ghost style={{flex:1}}>open</Btn>
                  <Btn ghost>⌘</Btn>
                </div>
              </Box>
            ))}
          </div>
        </main>
      </div>
      <Sticky style={{top: 70, right: 24}} rotate={2}>master gets a thicker border + tinted ring</Sticky>
    </WFFrame>
  );
}

// ─── B · Topology map (surprising) ──────────────────────────────────
function Nodes_Topology() {
  // pre-positioned nodes; lines drawn underneath
  const positions = [
    { ...NODES[0], x: 280, y: 150 }, // master center
    { ...NODES[1], x:  90, y:  60 },
    { ...NODES[2], x: 470, y:  70 },
    { ...NODES[3], x: 430, y: 240 },
  ];
  return (
    <WFFrame>
      <WFTop active="Nodes" exposure="lan" />
      <div className="wf-body">
        <WFSide active="nodes" />
        <main className="wf-main" style={{padding: 'var(--pad)', display:'flex', gap: 'var(--gap)', minHeight: 0}}>
          {/* canvas */}
          <Box style={{flex: 1, padding: 0, position:'relative', minHeight: 320, overflow:'hidden', background:`
            radial-gradient(circle at 50% 50%, var(--paper) 0%, var(--paper-2) 100%)
          `}}>
            {/* connection lines from master */}
            <svg style={{position:'absolute', inset: 0, width:'100%', height:'100%'}}>
              {positions.slice(1).map((n, i) => (
                <g key={i}>
                  <line x1={positions[0].x + 32} y1={positions[0].y + 32} x2={n.x + 32} y2={n.y + 32}
                    stroke={n.status === 'err' ? 'var(--bad)' : 'var(--rule-soft)'}
                    strokeWidth={n.status === 'err' ? 2 : 1.5}
                    strokeDasharray={n.status === 'err' ? '0' : '4 4'} />
                  <text x={(positions[0].x + n.x)/2 + 32} y={(positions[0].y + n.y)/2 + 30}
                    fill="var(--ink-3)" fontSize="9" fontFamily="var(--font-mono)" textAnchor="middle">
                    {n.status === 'err' ? '✗ ddns 401' : `${(Math.random()*5+0.2).toFixed(1)} MB/s`}
                  </text>
                </g>
              ))}
            </svg>

            {positions.map((n, i) => (
              <div key={i} className={`node-circle ${n.role === 'master' ? 'master' : ''}`}
                style={{left: n.x, top: n.y,
                  borderColor: n.status === 'err' ? 'var(--bad)' : n.status === 'warn' ? 'var(--warn)' : 'var(--rule)',
                }}>
                <span className="nm">{n.name.split('-')[0]}</span>
                <span style={{color:'var(--ink-3)'}}>{n.cpu}% · {n.temp}°</span>
              </div>
            ))}

            {/* legend */}
            <div style={{position:'absolute', left: 12, bottom: 12, display:'flex', gap: 10, fontFamily:'var(--font-mono)', fontSize: 10, color:'var(--ink-3)'}}>
              <span><span style={{display:'inline-block', width: 10, height: 10, borderRadius:'50%', border:'2px solid var(--ink)', verticalAlign:'-2px', background:'var(--accent-soft)'}}></span> master</span>
              <span><span style={{display:'inline-block', width: 18, height: 0, borderTop:'1.5px dashed var(--rule-soft)', verticalAlign:'middle'}}></span> healthy link</span>
              <span><span style={{display:'inline-block', width: 18, height: 0, borderTop:'2px solid var(--bad)', verticalAlign:'middle'}}></span> error</span>
            </div>

            <Note style={{position:'absolute', left: 130, top: 110, color: 'var(--accent)'}}>
              live edges show transfer rate · click a node to drill in
            </Note>
          </Box>

          {/* selected node detail */}
          <aside style={{width: 220, display:'flex', flexDirection:'column', gap:'var(--gap)'}}>
            <Box>
              <div style={{display:'flex', alignItems:'baseline', gap: 6, marginBottom: 6}}>
                <span style={{fontFamily:'var(--font-hand)', fontSize: 22, fontWeight: 700}}>pi4-shed</span>
                <Pill tone="err">2 alerts</Pill>
              </div>
              <div style={{fontFamily:'var(--font-mono)', fontSize: 10.5, color:'var(--ink-3)'}}>10.0.1.42 · up 02h 18m</div>
              <div className="div-cap">vitals</div>
              <Meter name="cpu" pct={22} accent />
              <Meter name="mem" pct={38} />
              <Meter name="°C"  pct={56} value="56°" accent />
              <div className="div-cap">alerts</div>
              <div style={{fontFamily:'var(--font-mono)', fontSize: 11, color:'var(--ink-2)'}}>
                <div><span style={{color:'var(--bad)'}}>✗</span> ddns · 401</div>
                <div><span style={{color:'var(--warn)'}}>!</span> temp 56°C ↑</div>
              </div>
              <div style={{display:'flex', gap: 6, marginTop: 10}}>
                <Btn primary>fix →</Btn>
                <Btn ghost>⌘ ssh</Btn>
              </div>
            </Box>
            <Box ghost>
              <div style={{fontFamily:'var(--font-mono)', fontSize: 10, color:'var(--ink-3)', textTransform:'uppercase', letterSpacing:'.08em', marginBottom: 6}}>fleet ops</div>
              <Btn ghost style={{width:'100%', marginBottom: 4}}>broadcast restart</Btn>
              <Btn ghost style={{width:'100%', marginBottom: 4}}>sync configs</Btn>
              <Btn ghost style={{width:'100%'}}>rotate keys</Btn>
            </Box>
          </aside>
        </main>
      </div>
    </WFFrame>
  );
}

// ─── C · Aggregator table ───────────────────────────────────────────
function Nodes_Table() {
  return (
    <WFFrame>
      <WFTop active="Nodes" exposure="lan" />
      <div className="wf-body">
        <WFSide active="nodes" />
        <main className="wf-main" style={{padding:'var(--pad)', display:'flex', flexDirection:'column', gap:'var(--gap)'}}>
          <div style={{display:'flex', alignItems:'baseline', gap: 12}}>
            <Scrawl style={{fontSize: 26}}>nodes</Scrawl>
            <span style={{fontFamily:'var(--font-mono)', fontSize:11, color:'var(--ink-3)'}}>spreadsheet view · sortable · multi-select</span>
            <span style={{flex:1}}></span>
            <Btn ghost>columns</Btn>
            <Btn ghost>filter</Btn>
            <Btn>＋ add</Btn>
          </div>
          <Box style={{padding: 0, overflow:'hidden'}}>
            <table className="tbl" style={{tableLayout:'fixed'}}>
              <thead>
                <tr>
                  <th style={{width: 28, paddingLeft: 12}}><span style={{display:'inline-block', width: 12, height: 12, border:'1.5px solid var(--rule)', borderRadius: 2}}></span></th>
                  <th style={{width: 140}}>node</th>
                  <th style={{width: 80}}>role</th>
                  <th style={{width: 100}}>address</th>
                  <th style={{width: 80}}>uptime</th>
                  <th>cpu</th>
                  <th>mem</th>
                  <th>disk</th>
                  <th style={{width: 50}}>°C</th>
                  <th style={{width: 110}}>services</th>
                  <th style={{width: 80}}>status</th>
                </tr>
              </thead>
              <tbody>
                {NODES.map((n, i) => (
                  <tr key={i}>
                    <td style={{paddingLeft: 12}}><span style={{display:'inline-block', width: 12, height: 12, border:'1.5px solid var(--rule)', borderRadius: 2, background: i===3 ? 'var(--accent)' : 'transparent'}}></span></td>
                    <td className="k">{n.name}</td>
                    <td>{n.role === 'master' ? <Pill tone="ok">master</Pill> : <span style={{color:'var(--ink-3)'}}>worker</span>}</td>
                    <td>{n.ip}</td>
                    <td>{n.uptime}</td>
                    <td><Prog pct={n.cpu} /></td>
                    <td><Prog pct={n.mem} /></td>
                    <td><Prog pct={n.disk} /></td>
                    <td style={{fontFamily:'var(--font-mono)', color: n.temp > 50 ? 'var(--bad)' : 'var(--ink-2)'}}>{n.temp}</td>
                    <td>
                      <div style={{display:'flex', gap: 3}}>
                        {Array.from({length: 5}).map((_, j) => (
                          <span key={j} style={{
                            width: 10, height: 10, borderRadius: 2,
                            background: j < n.svc ? (n.status==='err' && j === n.svc - 1 ? 'var(--bad)' : 'var(--good)') : 'var(--rule-ghost)',
                            border: '1px solid var(--rule-soft)',
                          }}></span>
                        ))}
                      </div>
                    </td>
                    <td><Pill tone={n.status}>{n.status === 'err' ? `${n.alerts}` : n.status}</Pill></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Box>
          <div style={{display:'flex', gap: 'var(--gap)'}}>
            <Box style={{flex: 1, display:'flex', alignItems:'center', gap: 10}}>
              <span style={{fontFamily:'var(--font-mono)', fontSize: 10, color:'var(--ink-3)', textTransform:'uppercase', letterSpacing:'.08em'}}>1 selected</span>
              <span style={{flex:1}}></span>
              <Btn ghost>restart svcs</Btn>
              <Btn ghost>sync config</Btn>
              <Btn>open ssh</Btn>
            </Box>
            <Box ghost style={{flex: 1, display:'flex', alignItems:'center', gap: 8, fontFamily:'var(--font-mono)', fontSize: 11, color:'var(--ink-2)'}}>
              <Pill tone="warn">tip</Pill>
              shift-click ranges, ⌘-click to add — ops apply to all selected
            </Box>
          </div>
        </main>
      </div>
      <Note style={{bottom: 18, right: 22, width: 130}}>power-user mode · keyboard-first · sortable</Note>
    </WFFrame>
  );
}

window.NodesVariants = [
  { id: 'cards',     label: 'A · Node cards',     comp: Nodes_Cards },
  { id: 'topology',  label: 'B · Topology map',   comp: Nodes_Topology },
  { id: 'table',     label: 'C · Aggregator',     comp: Nodes_Table },
];
