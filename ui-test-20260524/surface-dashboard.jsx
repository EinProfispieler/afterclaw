/* global React, WFTop, WFSide, Box, Stat, Pill, Sticky, Note, Spark, AreaChart, Donut, Meter, Prog, Btn, Tog, Scrawl */

// Three dashboard variants exploring layout density and metaphor:
//   A · Card grid       — conventional admin: stat tiles + panels (sparse, friendly)
//   B · Status board    — airport/NOC vibe: every node·service in one big strip
//   C · Terminal log    — power-user: streaming log + ascii-y vitals (surprising)

// ─── A · Card grid ──────────────────────────────────────────────────
function Dashboard_Cards() {
  return (
    <WFFrame>
      <WFTop active="Dashboard" exposure="lan" />
      <div className="wf-body">
        <WFSide active="overview" />
        <main className="wf-main" style={{display:'flex', flexDirection:'column', gap: 'var(--gap)'}}>
          {/* row of stat tiles */}
          <div style={{display:'grid', gridTemplateColumns:'repeat(4, 1fr)', gap:'var(--gap)'}}>
            <Box>
              <Stat label="CPU" v="32" u="%" sub="4·core · 1.8 GHz" />
              <div style={{marginTop:8}}><Spark accent /></div>
            </Box>
            <Box>
              <Stat label="MEMORY" v="6.1" u="GB" sub="of 16 GB · 38%" />
              <div style={{marginTop:8}}><Spark pts={[5,5,4,5,6,6,7,6,7,8,7,7,6,6,7,7,8,8,7,8]} /></div>
            </Box>
            <Box>
              <Stat label="DISK" v="71" u="%" sub="2.1 TB free / 7.3 TB" />
              <div style={{marginTop:8}}><Meter name="srv" pct={71} value="71%" /></div>
            </Box>
            <Box>
              <Stat label="TEMP" v="48" u="°C" sub="cpu pkg · normal" />
              <div style={{marginTop:8}}><Spark pts={[42,43,45,46,45,47,46,48,49,48,47,49,48,50,49,48,49,48,48,49]} accent /></div>
            </Box>
          </div>

          {/* two-column block */}
          <div style={{display:'grid', gridTemplateColumns:'1.4fr 1fr', gap:'var(--gap)', flex:1, minHeight:0}}>
            <Box title="Active transfers" meta="3 streams · 14.2 MB/s ▲">
              <table className="tbl">
                <thead><tr><th>file</th><th>peer</th><th>progress</th><th style={{textAlign:'right'}}>rate</th></tr></thead>
                <tbody>
                  <tr><td className="k">04-master-mix.wav</td><td>10.0.1.4</td><td><Prog pct={62} striped /></td><td style={{textAlign:'right'}}>8.4 MB/s</td></tr>
                  <tr><td className="k">backup-2026-05.tar</td><td>nas-02</td><td><Prog pct={38} /></td><td style={{textAlign:'right'}}>3.1 MB/s</td></tr>
                  <tr><td className="k">photos-iphone.zip</td><td>10.0.1.7</td><td><Prog pct={91} /></td><td style={{textAlign:'right'}}>2.7 MB/s</td></tr>
                </tbody>
              </table>
              <div className="div-cap">queue · 4 waiting</div>
              <div style={{display:'flex', gap:8}}>
                <Btn primary>↑ upload</Btn>
                <Btn ghost>pause new</Btn>
              </div>
            </Box>

            <div style={{display:'flex', flexDirection:'column', gap:'var(--gap)', minHeight:0}}>
              <Box title="Services">
                <div style={{display:'flex', flexDirection:'column', gap:8}}>
                  {[['qBittorrent', 'ok', 'on', '142 peers'],
                    ['DDNS · cloudflare', 'ok', 'on', '12m ago'],
                    ['HTTP /http-files/', 'warn', 'on', 'public'],
                    ['ShareClip', 'idle', 'off', '—']].map(([n,t,s,sub]) => (
                    <div key={n} style={{display:'flex', alignItems:'center', gap: 10}}>
                      <Tog on={s==='on'} />
                      <div style={{flex:1, minWidth:0}}>
                        <div style={{fontFamily:'var(--font-mono)', fontSize:11.5, color:'var(--ink)'}}>{n}</div>
                        <div style={{fontFamily:'var(--font-mono)', fontSize:10, color:'var(--ink-3)'}}>{sub}</div>
                      </div>
                      <Pill tone={t}>{t === 'idle' ? 'off' : t}</Pill>
                    </div>
                  ))}
                </div>
              </Box>
              <Box title="Recent activity" meta="last 30m" style={{flex:1, minHeight:0, overflow:'hidden'}}>
                <div className="term" style={{border:0, padding:0, fontSize:10.5, lineHeight:1.7}}>
                  <span className="dim">14:02</span>  <span className="ok">✓</span> ShareClip · note saved (mac-mini){'\n'}
                  <span className="dim">13:58</span>  <span className="acc">↑</span> 04-master-mix.wav started → 10.0.1.4{'\n'}
                  <span className="dim">13:51</span>  <span className="warn">!</span> DDNS rotated public IP{'\n'}
                  <span className="dim">13:47</span>  <span className="ok">✓</span> qBittorrent · 2 torrents resumed{'\n'}
                  <span className="dim">13:30</span>  <span className="dim">·</span> nightly snapshot complete
                </div>
              </Box>
            </div>
          </div>
        </main>
      </div>

      <Sticky style={{top: 18, right: 220}} rotate={-3}>warm card grid — safest default. easy to scan.</Sticky>
    </WFFrame>
  );
}

// ─── B · Status board ───────────────────────────────────────────────
function Dashboard_Statusboard() {
  const services = [
    { node: 'mac-mini · master', uptime: '12d 04h', svc: { qbit:'ok', ddns:'ok', http:'warn', clip:'ok', term:'idle' }, cpu: 32, temp: 48 },
    { node: 'thinkpad-x230',    uptime: '4d 11h',  svc: { qbit:'idle', ddns:'ok', http:'ok', clip:'ok', term:'idle' }, cpu: 12, temp: 41 },
    { node: 'nas-02',           uptime: '37d 02h', svc: { qbit:'ok', ddns:'idle', http:'ok', clip:'idle', term:'idle' }, cpu: 8,  temp: 39 },
    { node: 'pi4-shed',         uptime: '02h 18m', svc: { qbit:'idle', ddns:'err', http:'idle', clip:'idle', term:'idle' }, cpu: 22, temp: 56 },
  ];
  const cols = ['qbit','ddns','http','clip','term'];
  const colLabels = { qbit:'qbittor.', ddns:'ddns', http:'http', clip:'shareclip', term:'terminal' };

  return (
    <WFFrame>
      <WFTop active="Dashboard" exposure="public" />
      <main className="wf-main" style={{padding: 'var(--pad)'}}>
        <div style={{display:'flex', alignItems:'baseline', gap:14, marginBottom: 12}}>
          <Scrawl style={{fontSize: 30, fontWeight: 700}}>fleet status</Scrawl>
          <span style={{fontFamily:'var(--font-mono)', fontSize:11, color:'var(--ink-3)'}}>4 nodes · 1 anomaly · refreshed 3s ago</span>
        </div>

        <div className="box" style={{padding: 0, overflow:'hidden'}}>
          <table className="tbl" style={{tableLayout:'fixed'}}>
            <thead>
              <tr>
                <th style={{width: '22%'}}>node</th>
                <th style={{width: '10%'}}>uptime</th>
                {cols.map(c => <th key={c} style={{textAlign:'center'}}>{colLabels[c]}</th>)}
                <th style={{width:'14%'}}>cpu</th>
                <th style={{width:'10%', textAlign:'right'}}>°c</th>
              </tr>
            </thead>
            <tbody>
              {services.map((r, i) => (
                <tr key={i}>
                  <td className="k" style={{fontFamily:'var(--font-mono)'}}>
                    <span style={{display:'inline-block', width:6, height:6, borderRadius:'50%', background: r.svc.qbit==='err'||Object.values(r.svc).includes('err')?'var(--bad)':'var(--good)', marginRight:8}}></span>
                    {r.node}
                  </td>
                  <td>{r.uptime}</td>
                  {cols.map(c => (
                    <td key={c} style={{textAlign:'center'}}>
                      <span className={`pill ${r.svc[c]}`} style={{padding:'1px 6px', fontSize:10}}>
                        <span className="d"></span>{r.svc[c]==='idle'?'—':r.svc[c]}
                      </span>
                    </td>
                  ))}
                  <td><Prog pct={r.cpu} /></td>
                  <td style={{textAlign:'right', fontFamily:'var(--font-mono)'}}>{r.temp}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div style={{display:'grid', gridTemplateColumns:'2fr 1fr', gap:'var(--gap)', marginTop:'var(--gap)'}}>
          <Box title="Aggregate transfer pipeline" meta="last 60 min">
            <AreaChart pts={[3,4,4,6,8,7,9,12,11,10,12,14,13,12,11,13,15,14,12,10]} h={90}
              gridLabels={['-60m','-45m','-30m','-15m','now']} />
            <div style={{display:'flex', gap:14, fontFamily:'var(--font-mono)', fontSize:11, color:'var(--ink-2)', marginTop:8}}>
              <span><span style={{color:'var(--accent)'}}>▲</span> 14.2 MB/s out</span>
              <span><span style={{color:'var(--ink)'}}>▼</span> 2.1 MB/s in</span>
              <span style={{marginLeft:'auto'}}>peak: 18.4 MB/s</span>
            </div>
          </Box>
          <Box title="Anomaly" tinted>
            <div style={{display:'flex', alignItems:'center', gap:8, marginBottom: 8}}>
              <Pill tone="err">DDNS down</Pill>
              <span style={{fontFamily:'var(--font-mono)', fontSize:10, color:'var(--ink-3)'}}>pi4-shed</span>
            </div>
            <div style={{fontSize: 12, color: 'var(--ink-2)', marginBottom: 10}}>
              cloudflare token rejected (401) at 13:51. last good push 14h ago.
            </div>
            <div style={{display:'flex', gap:6}}>
              <Btn primary>retry</Btn>
              <Btn ghost>logs →</Btn>
            </div>
          </Box>
        </div>
      </main>

      <Note style={{top: 70, right: 16, width: 130}}>
        big public-exposure pill turns red the moment something's reachable
      </Note>
    </WFFrame>
  );
}

// ─── C · Terminal log + vitals (surprising) ─────────────────────────
function Dashboard_TerminalLog() {
  return (
    <WFFrame>
      <WFTop active="Dashboard" exposure="lan" />
      <main className="wf-main" style={{padding:'var(--pad)', display:'flex', gap:'var(--gap)', minHeight:0, height:'100%'}}>
        {/* main: live log */}
        <div style={{flex: 1.5, display:'flex', flexDirection:'column', gap:'var(--gap)', minHeight:0}}>
          <div style={{display:'flex', alignItems:'center', gap:10}}>
            <span className="pill ok"><span className="d"></span>tail -f</span>
            <span style={{fontFamily:'var(--font-mono)', fontSize:11, color:'var(--ink-2)'}}>everything · all nodes · 12 lines/s</span>
            <span style={{marginLeft:'auto', display:'flex', gap:6}}>
              <Btn ghost>filter…</Btn>
              <Btn ghost>pause</Btn>
            </span>
          </div>
          <Box style={{flex:1, padding:0, minHeight:0}}>
            <div className="term" style={{border:0, height:'100%', overflow:'hidden'}}>
{`14:03:21  mac-mini  files     `}<span className="acc">▲</span>{` 04-master-mix.wav  62%  8.4MB/s
14:03:18  nas-02    qbittorrent `}<span className="ok">✓</span>{` torrent_added 1080p.mkv
14:03:14  mac-mini  shareclip  `}<span className="ok">✓</span>{` note "wifi pwd" saved (3 lines)
14:03:09  pi4-shed  ddns       `}<span className="err">✗</span>{` cloudflare 401 — token rejected
14:03:02  nas-02    files      `}<span className="acc">▲</span>{` backup-2026-05.tar  38%  3.1MB/s
14:02:55  thinkpad  monitor    `}<span className="dim">·</span>{` cpu  12% mem 22% temp 41°C
14:02:48  mac-mini  http       `}<span className="warn">!</span>{` /http-files/ exposed publicly
14:02:31  mac-mini  files      `}<span className="acc">▲</span>{` photos-iphone.zip  91%  2.7MB/s
14:02:20  pi4-shed  service    `}<span className="warn">!</span>{` retry 4/5 — backoff 30s
14:02:01  nas-02    nightly    `}<span className="ok">✓</span>{` snapshot complete (218 GB, 14m)
14:01:42  mac-mini  terminal   `}<span className="dim">·</span>{` session opened from 10.0.1.4
14:01:30  thinkpad  shareclip  `}<span className="ok">✓</span>{` clip received: image (412 KB)
14:01:14  mac-mini  files      `}<span className="dim">·</span>{` queued: documents-q2.zip
              ▌`}
            </div>
          </Box>
        </div>

        {/* right: vitals strip + quick actions */}
        <aside style={{flex:'0 0 220px', display:'flex', flexDirection:'column', gap:'var(--gap)'}}>
          <Box>
            <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap: 10}}>
              <Donut pct={32} label="CPU" />
              <Donut pct={38} label="MEM" accent={false} />
              <Donut pct={71} label="DISK" />
              <Donut pct={48} label="TEMP" accent={false} />
            </div>
          </Box>
          <Box title="now">
            <div style={{display:'flex', flexDirection:'column', gap:6, fontFamily:'var(--font-mono)', fontSize:11}}>
              <div style={{display:'flex', justifyContent:'space-between'}}><span style={{color:'var(--ink-3)'}}>↑ out</span><span>14.2 MB/s</span></div>
              <div style={{display:'flex', justifyContent:'space-between'}}><span style={{color:'var(--ink-3)'}}>↓ in</span><span>2.1 MB/s</span></div>
              <div style={{display:'flex', justifyContent:'space-between'}}><span style={{color:'var(--ink-3)'}}>peers</span><span>142</span></div>
              <div style={{display:'flex', justifyContent:'space-between'}}><span style={{color:'var(--ink-3)'}}>queue</span><span>4 + 3</span></div>
            </div>
          </Box>
          <Box ghost style={{flex:1}}>
            <div style={{fontFamily:'var(--font-mono)', fontSize: 10, letterSpacing:'.06em', textTransform:'uppercase', color:'var(--ink-3)', marginBottom: 8}}>quick</div>
            <div style={{display:'flex', flexDirection:'column', gap: 6}}>
              <Btn>↑ upload</Btn>
              <Btn>+ shareclip</Btn>
              <Btn>⌘ open terminal</Btn>
              <Btn ghost>pause downloads</Btn>
            </div>
          </Box>
        </aside>
      </main>

      <Sticky style={{bottom: 16, left: 200}} rotate={2}>
        for the tinkerer who already lives in tmux. dense + cathartic.
      </Sticky>
    </WFFrame>
  );
}

window.DashboardVariants = [
  { id: 'cards',  label: 'A · Card grid',     comp: Dashboard_Cards },
  { id: 'board',  label: 'B · Status board',  comp: Dashboard_Statusboard },
  { id: 'log',    label: 'C · Terminal log',  comp: Dashboard_TerminalLog },
];
