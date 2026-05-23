/* global React, WFTop, WFSide, Box, Pill, Sticky, Note, Spark, AreaChart, Donut, Meter, Prog, Btn, Scrawl */

// System monitor — 3 variants
//   A · Stacked timeline   — area charts vertically stacked + scrubber
//   B · Gauge cluster       — donuts + sparklines + history grid
//   C · Heatmap floor       — surprising: every metric × time as a colored grid

const cpuPts  = [22,24,28,30,29,32,34,36,33,30,28,30,32,35,38,42,44,40,36,33,32];
const memPts  = [38,38,40,41,42,44,45,46,46,47,48,48,49,50,51,52,52,52,52,52,53];
const diskPts = [70,70,70,70,71,71,71,71,71,71,71,71,71,71,71,71,71,71,71,71,71];
const tempPts = [42,42,43,43,44,44,45,46,46,46,47,47,48,48,49,49,49,48,48,48,48];
const netPts  = [3,4,4,6,8,7,9,12,11,10,12,14,13,12,11,13,15,14,12,10,11];

// ─── A · Stacked timeline ───────────────────────────────────────────
function Monitor_Timeline() {
  const blocks = [
    ['CPU',  cpuPts,  '%', '32%', 'avg 31 · peak 44'],
    ['MEM',  memPts,  '%', '52%', '8.3 GB / 16 GB'],
    ['DISK', diskPts, '%', '71%', '2.1 TB free'],
    ['TEMP', tempPts, '°C','48°C', 'pkg · cores 46-52'],
    ['NET',  netPts, ' MB/s','14.2', '↑ 14.2 ↓ 2.1'],
  ];
  return (
    <WFFrame>
      <WFTop active="Monitor" exposure="lan" />
      <div className="wf-body">
        <WFSide active="monitor" />
        <main className="wf-main" style={{padding:'var(--pad)', display:'flex', flexDirection:'column', gap: 6}}>
          <div style={{display:'flex', alignItems:'baseline', gap: 12, marginBottom: 4}}>
            <Scrawl style={{fontSize: 26}}>vitals</Scrawl>
            <span style={{fontFamily:'var(--font-mono)', fontSize:11, color:'var(--ink-3)'}}>mac-mini · last 60 min · sample 5s</span>
            <span style={{flex:1}}></span>
            {['1h','6h','24h','7d'].map((r,i) => (
              <Btn key={r} primary={i===0}>{r}</Btn>
            ))}
          </div>
          {blocks.map(([label, pts, unit, value, sub]) => (
            <div key={label} className="box" style={{padding: 10, display:'grid', gridTemplateColumns:'92px 1fr 130px', alignItems:'center', gap: 12}}>
              <div>
                <div style={{fontFamily:'var(--font-mono)', fontSize: 10, color:'var(--ink-3)', textTransform:'uppercase', letterSpacing:'.08em'}}>{label}</div>
                <div style={{fontFamily:'var(--font-hand)', fontSize: 26, fontWeight:700, lineHeight:1}}>{value}</div>
              </div>
              <AreaChart pts={pts} h={70} accent={label==='CPU' || label==='NET'} />
              <div style={{fontFamily:'var(--font-mono)', fontSize: 10.5, color:'var(--ink-2)', textAlign:'right'}}>{sub}</div>
            </div>
          ))}
          {/* timeline scrubber */}
          <div className="box ghost" style={{display:'flex', alignItems:'center', gap: 10, padding: '8px 12px'}}>
            <span style={{fontFamily:'var(--font-mono)', fontSize: 10, color:'var(--ink-3)'}}>13:04</span>
            <div style={{flex:1, height: 16, position:'relative', borderTop:'1.5px dashed var(--rule-soft)', borderBottom:'1.5px dashed var(--rule-soft)'}}>
              <div style={{position:'absolute', left:'72%', top:-3, bottom:-3, width: 2, background:'var(--accent)'}}></div>
              <div style={{position:'absolute', left:'72%', top:-12, transform:'translateX(-50%)', fontFamily:'var(--font-hand)', fontSize:13, color:'var(--accent)'}}>now</div>
            </div>
            <span style={{fontFamily:'var(--font-mono)', fontSize: 10, color:'var(--ink-3)'}}>14:04</span>
          </div>
        </main>
      </div>
      <Sticky style={{top: 70, right: 24}} rotate={2}>scrub anywhere — every chart redraws to that moment</Sticky>
    </WFFrame>
  );
}

// ─── B · Gauge cluster ──────────────────────────────────────────────
function Monitor_Gauges() {
  return (
    <WFFrame>
      <WFTop active="Monitor" exposure="lan" />
      <div className="wf-body">
        <WFSide active="monitor" />
        <main className="wf-main" style={{padding:'var(--pad)', display:'flex', flexDirection:'column', gap:'var(--gap)'}}>
          {/* gauge row */}
          <div style={{display:'grid', gridTemplateColumns:'repeat(4, 1fr)', gap:'var(--gap)'}}>
            {[['CPU', 32, true],['MEM', 52, false],['DISK', 71, false],['TEMP', 48, true]].map(([l,p,a], i) => (
              <Box key={i}>
                <div style={{display:'flex', alignItems:'center', gap: 10}}>
                  <Donut pct={p} accent={a} size={70} />
                  <div style={{flex:1, minWidth:0}}>
                    <div style={{fontFamily:'var(--font-mono)', fontSize: 10, color:'var(--ink-3)', textTransform:'uppercase'}}>{l}</div>
                    <Spark pts={l==='TEMP'?tempPts:l==='MEM'?memPts:l==='DISK'?diskPts:cpuPts} accent={a} h={32} w={120} />
                    <div style={{fontFamily:'var(--font-mono)', fontSize: 10, color:'var(--ink-3)', marginTop: 2}}>1h sparkline</div>
                  </div>
                </div>
              </Box>
            ))}
          </div>
          {/* per-core + per-disk + per-iface */}
          <div style={{display:'grid', gridTemplateColumns:'1fr 1fr 1fr', gap:'var(--gap)', flex: 1, minHeight: 0}}>
            <Box title="cores · 4" meta="GHz">
              {[1,2,3,4].map(c => <Meter key={c} name={`core ${c}`} pct={[28,42,18,55][c-1]} value={`${[1.6,2.1,1.4,2.4][c-1]} GHz`} accent={c===2 || c===4} />)}
              <div className="div-cap">load avg</div>
              <div style={{fontFamily:'var(--font-mono)', fontSize: 11.5, color:'var(--ink-2)'}}>0.42  ·  0.51  ·  0.48</div>
            </Box>
            <Box title="disks" meta="3 mounts">
              {[['/srv', 71, '5.2 / 7.3 TB'],
                ['/', 28, '24 / 86 GB'],
                ['/var/log', 12, '1.2 / 10 GB']].map(([n,p,sub]) => (
                <div key={n} style={{marginBottom: 10}}>
                  <Meter name={n} pct={p} accent />
                  <div style={{fontFamily:'var(--font-mono)', fontSize: 10, color:'var(--ink-3)', marginLeft: 64, marginTop: 2}}>{sub}</div>
                </div>
              ))}
              <div className="div-cap">io</div>
              <div style={{fontFamily:'var(--font-mono)', fontSize: 11.5, color:'var(--ink-2)'}}>read 24 MB/s · write 8 MB/s</div>
            </Box>
            <Box title="network" meta="2 ifaces">
              {[['en0', 14.2, '↑ 14.2 ↓ 2.1 MB/s'],
                ['utun0', 0.4, 'wireguard · idle']].map(([n,p,sub]) => (
                <div key={n} style={{marginBottom: 10}}>
                  <Meter name={n} pct={Math.min(100, p*5)} value={`${p} MB/s`} />
                  <div style={{fontFamily:'var(--font-mono)', fontSize: 10, color:'var(--ink-3)', marginLeft: 64, marginTop: 2}}>{sub}</div>
                </div>
              ))}
              <AreaChart pts={netPts} h={56} />
            </Box>
          </div>
        </main>
      </div>
      <Note style={{bottom: 18, right: 22, width: 130}}>
        donuts to glance, sparklines for context, breakdown below
      </Note>
    </WFFrame>
  );
}

// ─── C · Heatmap floor (surprising) ─────────────────────────────────
function Monitor_Heatmap() {
  // each row = a metric, each cell = a 5-min slice of the last 6h
  const rows = [
    ['mac-mini · cpu',  [12,18,22,28,34,30,28,22,32,38,42,44,38,32,28,30,32,34,36,38,42,44,46,32]],
    ['mac-mini · mem',  [38,38,40,42,44,46,48,49,50,52,52,52,52,52,52,52,52,52,52,52,52,52,52,52]],
    ['mac-mini · temp', [42,42,43,44,44,45,46,47,48,49,49,49,48,48,48,48,49,50,52,54,56,58,52,48]],
    ['nas-02 · cpu',    [4,4,5,5,6,6,8,8,12,18,16,12,8,6,5,6,8,8,12,18,12,8,5,4]],
    ['nas-02 · disk-io',[5,5,8,12,16,12,8,5,4,5,6,8,10,12,18,22,28,32,28,18,12,8,5,4]],
    ['nas-02 · temp',   [38,38,38,39,39,39,40,40,40,40,40,40,39,39,39,39,40,40,41,42,42,41,40,39]],
    ['pi4-shed · cpu',  [22,22,24,28,32,38,42,38,32,28,24,22,22,24,28,32,42,48,52,48,42,38,32,28]],
    ['pi4-shed · temp', [56,56,58,60,62,64,66,64,62,60,58,56,56,58,60,62,66,68,70,68,66,64,62,60]],
  ];

  function color(v, max = 100) {
    const t = Math.min(1, v / max);
    const lightness = 0.92 - t * 0.45;
    return `oklch(${lightness} ${0.05 + t * 0.13} 30)`;
  }

  return (
    <WFFrame>
      <WFTop active="Monitor" exposure="lan" />
      <div className="wf-body">
        <WFSide active="monitor" />
        <main className="wf-main" style={{padding:'var(--pad)', display:'flex', flexDirection:'column', gap: 'var(--gap)', minHeight: 0}}>
          <div style={{display:'flex', alignItems:'baseline', gap: 14}}>
            <Scrawl style={{fontSize: 26}}>fleet floor · 6h</Scrawl>
            <span style={{fontFamily:'var(--font-mono)', fontSize:11, color:'var(--ink-3)'}}>3 nodes · 8 series · 15-min cells</span>
            <span style={{flex: 1}}></span>
            <Btn>cpu/mem/temp</Btn>
            <Btn ghost>add metric +</Btn>
          </div>

          <Box style={{flex: 1, padding: 0, overflow:'hidden'}}>
            <div style={{display:'grid', gridTemplateColumns:'140px 1fr', gap: 0}}>
              {rows.map(([label, vals], r) => (
                <React.Fragment key={r}>
                  <div style={{padding:'8px 12px', borderBottom:'1px dashed var(--rule-soft)', fontFamily:'var(--font-mono)', fontSize: 10.5, color:'var(--ink-2)', display:'flex', alignItems:'center'}}>
                    {label}
                  </div>
                  <div style={{display:'grid', gridTemplateColumns:`repeat(${vals.length}, 1fr)`, borderBottom:'1px dashed var(--rule-soft)'}}>
                    {vals.map((v, c) => (
                      <div key={c}
                        style={{
                          height: 28,
                          background: color(v, label.includes('temp') ? 80 : 100),
                          borderRight: c < vals.length - 1 ? '1px solid rgba(0,0,0,0.04)' : 0,
                          position:'relative',
                        }}>
                        {label === 'pi4-shed · temp' && c === 18 && (
                          <span style={{position:'absolute', inset: 0, border:'1.5px solid var(--bad)', borderRadius: 2}}></span>
                        )}
                      </div>
                    ))}
                  </div>
                </React.Fragment>
              ))}
              {/* time axis */}
              <div></div>
              <div style={{display:'flex', justifyContent:'space-between', padding:'4px 6px', fontFamily:'var(--font-mono)', fontSize: 9, color:'var(--ink-3)'}}>
                <span>-6h</span><span>-4h</span><span>-2h</span><span>now</span>
              </div>
            </div>
          </Box>

          {/* legend + anomaly callout */}
          <div style={{display:'flex', gap: 'var(--gap)'}}>
            <Box style={{flex: 1, display:'flex', alignItems:'center', gap: 12}}>
              <span style={{fontFamily:'var(--font-mono)', fontSize: 10, color:'var(--ink-3)', textTransform:'uppercase', letterSpacing:'.08em'}}>scale</span>
              <div style={{display:'flex', height: 14, flex: 1, borderRadius: 4, overflow:'hidden', border:'1px solid var(--rule-soft)'}}>
                {[0,15,30,45,60,75,90].map(v => (
                  <span key={v} style={{flex:1, background: color(v)}}></span>
                ))}
              </div>
              <span style={{fontFamily:'var(--font-mono)', fontSize: 10, color:'var(--ink-3)'}}>0 → 100</span>
            </Box>
            <Box tinted style={{flex: 1, display:'flex', alignItems:'center', gap: 10}}>
              <Pill tone="err">hot cell</Pill>
              <span style={{fontFamily:'var(--font-mono)', fontSize: 11, color:'var(--ink-2)'}}>pi4-shed temp 70°C @ -45m — fan?</span>
              <span style={{flex:1}}></span>
              <Btn primary>open →</Btn>
            </Box>
          </div>
        </main>
      </div>
      <Sticky style={{top: 70, right: 24}} rotate={-3}>
        ★ unusual: glance scans for hot streaks across nodes & metrics at once
      </Sticky>
    </WFFrame>
  );
}

window.MonitorVariants = [
  { id: 'timeline', label: 'A · Stacked timeline', comp: Monitor_Timeline },
  { id: 'gauges',   label: 'B · Gauge cluster',     comp: Monitor_Gauges },
  { id: 'heatmap',  label: 'C · Fleet heatmap',     comp: Monitor_Heatmap },
];
