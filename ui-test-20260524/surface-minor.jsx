/* global React, WFTop, WFSide, Box, Pill, Sticky, Note, Spark, Meter, Prog, Btn, Tog, Scrawl, Bars */

// Minor surfaces (2 variants each):
//   Docker · Terminal · DDNS/Services · Settings · ShareClip

// ─── DOCKER ─────────────────────────────────────────────────────────
function Docker_List() {
  const containers = [
    ['qbittorrent-nox', 'running', 1.2, 'linuxserver/qbittorrent', '4d 11h', '8080→8080'],
    ['nginx-proxy',     'running', 0.4, 'jc21/nginx-proxy:latest','12d 04h', '80,443'],
    ['shareclip-redis', 'running', 0.2, 'redis:7-alpine',         '12d 04h', '6379'],
    ['photoprism',      'running', 8.6, 'photoprism/photoprism', '2d 04h',  '2342→80'],
    ['cleanup-cron',    'exited',  0.0, 'busybox',                '— · code 0', '—'],
    ['paperless-ngx',   'restart', 1.8, 'paperlessngx/paperless', '12s ago', '8000'],
  ];
  return (
    <WFFrame>
      <WFTop active="Docker" exposure="lan" />
      <div className="wf-body">
        <WFSide active="docker" />
        <main className="wf-main" style={{padding:'var(--pad)', display:'flex', flexDirection:'column', gap:'var(--gap)'}}>
          <div style={{display:'flex', alignItems:'baseline', gap: 12}}>
            <Scrawl style={{fontSize: 26}}>containers</Scrawl>
            <span style={{fontFamily:'var(--font-mono)', fontSize:11, color:'var(--ink-3)'}}>6 total · 4 running · 1 restarting</span>
            <span style={{flex:1}}></span>
            <Btn ghost>compose</Btn>
            <Btn>pull all</Btn>
          </div>
          <Box style={{padding:0, overflow:'hidden', flex:1, minHeight:0}}>
            <table className="tbl" style={{tableLayout:'fixed'}}>
              <thead><tr>
                <th style={{paddingLeft: 14, width:'24%'}}>name</th>
                <th style={{width:'12%'}}>status</th>
                <th>image</th>
                <th style={{width:'14%'}}>cpu/mem</th>
                <th style={{width:'14%'}}>uptime</th>
                <th style={{width:'14%'}}>actions</th>
              </tr></thead>
              <tbody>
                {containers.map((c,i) => (
                  <tr key={i}>
                    <td className="k" style={{paddingLeft: 14}}>{c[0]}</td>
                    <td><Pill tone={c[1]==='running'?'ok':c[1]==='exited'?'idle':'warn'}>{c[1]}</Pill></td>
                    <td>{c[3]}<div style={{fontFamily:'var(--font-mono)', fontSize: 9.5, color:'var(--ink-3)'}}>{c[5]}</div></td>
                    <td><Prog pct={c[2]*8} /></td>
                    <td>{c[4]}</td>
                    <td style={{display:'flex', gap: 4}}>
                      <Btn ghost>logs</Btn>
                      <Btn ghost>{c[1]==='running'?'■':'▶'}</Btn>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Box>
          <Box title="logs · paperless-ngx" meta="tail -f · last 8 lines" tinted>
            <div className="term" style={{border:0, padding:0, fontSize: 10.5, lineHeight: 1.5}}>
{`[2026-05-09 14:03:01] `}<span className="warn">! </span>{`waiting for postgres at db:5432
[2026-05-09 14:03:04] `}<span className="warn">! </span>{`retry 1/5
[2026-05-09 14:03:09] `}<span className="ok">✓ </span>{`postgres ready
[2026-05-09 14:03:10] `}<span className="dim">· </span>{`migrating … 0042_async_indexing
[2026-05-09 14:03:14] `}<span className="ok">✓ </span>{`migrations applied (3)
[2026-05-09 14:03:15] `}<span className="dim">· </span>{`gunicorn workers=4 spawned
[2026-05-09 14:03:16] `}<span className="ok">✓ </span>{`listening on :8000`}
            </div>
          </Box>
        </main>
      </div>
    </WFFrame>
  );
}

function Docker_Compose() {
  const stacks = [
    { name: 'media',        services: [['photoprism','run'],['mariadb','run'],['nginx','run']],   path:'/srv/compose/media' },
    { name: 'downloads',    services: [['qbittorrent','run'],['gluetun','run']],                  path:'/srv/compose/dl' },
    { name: 'paperless',    services: [['paperless-ngx','restart'],['postgres','run'],['redis','run'],['gotenberg','exit']], path:'/srv/compose/paper' },
  ];
  return (
    <WFFrame>
      <WFTop active="Docker" exposure="lan" />
      <div className="wf-body">
        <WFSide active="docker" />
        <main className="wf-main" style={{padding:'var(--pad)', display:'flex', flexDirection:'column', gap:'var(--gap)'}}>
          <div style={{display:'flex', alignItems:'baseline', gap: 12}}>
            <Scrawl style={{fontSize: 26}}>compose stacks</Scrawl>
            <span style={{fontFamily:'var(--font-mono)', fontSize:11, color:'var(--ink-3)'}}>3 projects · 11 services</span>
            <span style={{flex: 1}}></span>
            <Btn ghost>＋ import</Btn>
            <Btn primary>up all</Btn>
          </div>
          <div style={{display:'grid', gridTemplateColumns:'repeat(3, 1fr)', gap:'var(--gap)', flex:1, minHeight: 0}}>
            {stacks.map((s,i) => {
              const bad = s.services.some(([,t]) => t==='restart' || t==='exit');
              return (
                <Box key={i} style={{display:'flex', flexDirection:'column'}}>
                  <div style={{display:'flex', alignItems:'baseline', gap:6, marginBottom: 4}}>
                    <span style={{fontFamily:'var(--font-hand)', fontSize: 22, fontWeight: 700}}>{s.name}</span>
                    <Pill tone={bad?'warn':'ok'}>{bad?'attention':'healthy'}</Pill>
                  </div>
                  <div style={{fontFamily:'var(--font-mono)', fontSize: 10, color:'var(--ink-3)', marginBottom: 8}}>{s.path}</div>
                  <div style={{display:'flex', flexDirection:'column', gap: 4}}>
                    {s.services.map(([n,t]) => (
                      <div key={n} style={{display:'flex', alignItems:'center', gap: 8, padding: '4px 6px', borderRadius: 4, background: t==='restart' ? 'var(--warn-soft)' : 'transparent'}}>
                        <span style={{width: 6, height: 6, borderRadius:'50%', background: t==='run'?'var(--good)':t==='exit'?'var(--ink-3)':'var(--warn)'}}></span>
                        <span style={{fontFamily:'var(--font-mono)', fontSize: 11.5, flex:1}}>{n}</span>
                        <span style={{fontFamily:'var(--font-mono)', fontSize: 10, color:'var(--ink-3)'}}>{t}</span>
                      </div>
                    ))}
                  </div>
                  <div style={{display:'flex', gap: 6, marginTop: 'auto', paddingTop: 10}}>
                    <Btn ghost>logs</Btn>
                    <Btn ghost>edit yml</Btn>
                    <span style={{flex:1}}></span>
                    <Btn>{bad ? 'restart' : 'down'}</Btn>
                  </div>
                </Box>
              );
            })}
          </div>
        </main>
      </div>
      <Note style={{top: 88, right: 18, width: 120}}>group services by stack — easier mental model than 11 flat rows</Note>
    </WFFrame>
  );
}

// ─── TERMINAL ───────────────────────────────────────────────────────
function Terminal_Full() {
  return (
    <WFFrame>
      <WFTop active="Terminal" exposure="lan" />
      <div className="wf-body">
        <WFSide active="terminal" />
        <main className="wf-main" style={{padding:'var(--pad)', display:'flex', gap:'var(--gap)', minHeight: 0}}>
          {/* keys + sessions */}
          <aside style={{width: 200, display:'flex', flexDirection:'column', gap:'var(--gap)'}}>
            <Box title="keys" meta="3">
              {[['id_ed25519', 'default · used 2m ago'],
                ['mac-mini.pub', 'master node'],
                ['cloud-2024.pub', 'archived']].map(([n,sub], i) => (
                <div key={i} style={{display:'flex', alignItems:'center', gap:8, padding:'5px 0', borderBottom: i<2?'1px dashed var(--rule-soft)':0}}>
                  <span style={{width: 6, height: 6, borderRadius:'50%', background: i===2?'var(--ink-3)':'var(--good)'}}></span>
                  <div style={{flex:1, minWidth:0}}>
                    <div style={{fontFamily:'var(--font-mono)', fontSize: 11}}>{n}</div>
                    <div style={{fontFamily:'var(--font-mono)', fontSize: 9.5, color:'var(--ink-3)'}}>{sub}</div>
                  </div>
                </div>
              ))}
              <div style={{display:'flex', gap: 4, marginTop: 8}}>
                <Btn ghost style={{flex:1}}>＋ add</Btn>
                <Btn ghost>import</Btn>
              </div>
            </Box>
            <Box title="sessions">
              {[['mac-mini', 'active'],['nas-02','15m idle'],['pi4-shed','disconnected']].map(([n,t], i) => (
                <div key={i} style={{display:'flex', alignItems:'center', gap: 6, padding: '4px 0'}}>
                  <span className="dot" style={{width:6, height:6, borderRadius:'50%', background: t==='active'?'var(--accent)':'var(--ink-3)'}}></span>
                  <span style={{fontFamily:'var(--font-mono)', fontSize: 11.5, flex:1}}>{n}</span>
                  <span style={{fontFamily:'var(--font-mono)', fontSize: 9.5, color:'var(--ink-3)'}}>{t}</span>
                </div>
              ))}
            </Box>
          </aside>
          {/* main term */}
          <div style={{flex:1, display:'flex', flexDirection:'column', minWidth: 0}}>
            <div style={{display:'flex', gap: 0, marginBottom: 6}}>
              {[['mac-mini', true],['nas-02', false],['＋', false]].map(([t,a], i) => (
                <span key={i} style={{
                  padding:'5px 12px', fontFamily:'var(--font-mono)', fontSize: 11,
                  border:'1.5px solid var(--rule)',
                  borderBottom: a ? '1.5px solid var(--paper)' : '1.5px solid var(--rule)',
                  background: a ? 'var(--paper)' : 'var(--paper-2)',
                  color: a ? 'var(--ink)' : 'var(--ink-3)',
                  borderRadius: '6px 6px 0 0',
                  marginRight: 4, marginBottom: -1.5,
                }}>{t}</span>
              ))}
            </div>
            <Box style={{flex: 1, padding: 0, minHeight: 0}}>
              <div className="term" style={{border:0, height:'100%'}}>
{`mac-mini ~ % `}<span className="acc">df -h /srv</span>{`
Filesystem      Size   Used   Avail   Use%  Mounted on
/dev/disk2s1    7.3T   5.2T   2.1T    71%   /srv

mac-mini ~ % `}<span className="acc">systemctl status afterclaw</span>{`
`}<span className="ok">● afterclaw.service — AfterClaw control surface</span>{`
   Loaded: loaded (/etc/systemd/system/afterclaw.service; enabled)
   Active: `}<span className="ok">active (running)</span>{` since Sun 2026-04-27 09:12
   Memory: 142.4M
   CGroup: /system.slice/afterclaw.service
           └─2138 /usr/bin/python3 -m fcc

mac-mini ~ % `}<span className="acc">tail -f /var/log/afterclaw/access.log</span>{`
2026-05-09 14:03:21  ▲ 10.0.1.4   /http-files/04-master-mix.wav  206  62%
2026-05-09 14:03:18  ▲ nas-02     /http-files/backup-2026-05.tar 206  38%
2026-05-09 14:03:14  · 10.0.1.7   /api/shareclip/save            200  3ms
`}<span className="acc">_</span>
              </div>
            </Box>
          </div>
        </main>
      </div>
      <Sticky style={{top: 70, right: 24}} rotate={3}>keys + tabs left, terminal fills the rest. familiar.</Sticky>
    </WFFrame>
  );
}

function Terminal_Tabs() {
  return (
    <WFFrame>
      <WFTop active="Terminal" exposure="lan" />
      <main className="wf-main" style={{padding:'var(--pad)', display:'flex', flexDirection:'column', gap:'var(--gap)', minHeight: 0, height:'100%'}}>
        <div style={{display:'flex', alignItems:'baseline', gap: 12}}>
          <Scrawl style={{fontSize: 26}}>multi-shell</Scrawl>
          <span style={{fontFamily:'var(--font-mono)', fontSize:11, color:'var(--ink-3)'}}>tile mode · 4 nodes side-by-side</span>
          <span style={{flex:1}}></span>
          <Btn ghost>broadcast input ⌥</Btn>
          <Btn>＋ pane</Btn>
        </div>
        <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gridTemplateRows:'1fr 1fr', gap:'var(--gap)', flex: 1, minHeight: 0}}>
          {[['mac-mini', 'master', `top - 14:03:21
Tasks: 248 total
%CPU(s):  32 us, 4 sy
KiB Mem :  16384 total
PID  USER     %CPU %MEM
2138 root      8.4  0.9  python3 -m fcc
1042 qbit      4.2  3.1  qbittorrent-no`],
            ['thinkpad-x230', 'worker', `$ uname -a
Linux thinkpad 6.5.0
$ uptime
 14:03  up 4 days 11h
 load average: 0.12 0.18 0.22`],
            ['nas-02', 'worker', `$ zpool status srv
  pool: srv
 state: ONLINE
  scan: scrub repaired 0B
config:  raidz2-0  ONLINE
errors: No known data errors`],
            ['pi4-shed', 'worker · ⚠ ddns', `$ journalctl -u afterclaw --tail=4
13:51:02 cloudflare push 401
13:51:32 cloudflare push 401
13:52:02 cloudflare push 401
13:52:30 backoff 30s · retry 4/5`]
          ].map(([h, sub, body], i) => (
            <div key={i} className="box" style={{padding: 0, overflow:'hidden', display:'flex', flexDirection:'column'}}>
              <div style={{display:'flex', alignItems:'center', gap: 6, padding: '4px 10px', borderBottom: '1.5px solid var(--rule)', background: 'var(--paper-2)'}}>
                <span style={{width: 6, height: 6, borderRadius:'50%', background: i===3?'var(--bad)':'var(--good)'}}></span>
                <span style={{fontFamily:'var(--font-mono)', fontSize: 11}}>{h}</span>
                <span style={{fontFamily:'var(--font-mono)', fontSize: 9.5, color:'var(--ink-3)'}}>{sub}</span>
                <span style={{flex:1}}></span>
                <span style={{fontFamily:'var(--font-mono)', fontSize: 9.5, color:'var(--ink-3)'}}>⌘ {i+1}</span>
              </div>
              <div className="term" style={{border:0, borderRadius: 0, flex: 1, fontSize: 10.5}}>{body}</div>
            </div>
          ))}
        </div>
      </main>
      <Note style={{bottom: 18, right: 22, width: 130}}>
        ★ broadcast input → type once, send to all 4 panes. ops dream
      </Note>
    </WFFrame>
  );
}

// ─── DDNS / SERVICES ────────────────────────────────────────────────
function Services_Cards() {
  const services = [
    { n: 'qBittorrent', sub: 'torrent client · :8080', on: true, status: 'ok', meta: '142 peers · ↑ 2.1 ↓ 4.4 MB/s' },
    { n: 'DDNS · cloudflare', sub: 'rotates A record', on: true, status: 'ok', meta: 'last push 12m ago · IP 81.42.13.7' },
    { n: 'HTTP /http-files/', sub: 'public link sharing', on: true, status: 'warn', meta: 'EXPOSED · 4.2 GB / 24h' },
    { n: 'ShareClip', sub: 'clipboard sync', on: false, status: 'idle', meta: '—' },
    { n: 'qBittorrent (pi4-shed)', sub: 'remote node', on: false, status: 'idle', meta: 'paused · 02h 18m' },
    { n: 'self · afterclaw', sub: 'control surface', on: true, status: 'ok', meta: 'pid 2138 · 142 MB' },
  ];
  return (
    <WFFrame>
      <WFTop active="Services" exposure="public" />
      <div className="wf-body">
        <WFSide active="ddns" />
        <main className="wf-main" style={{padding:'var(--pad)'}}>
          <div style={{display:'grid', gridTemplateColumns:'repeat(3, 1fr)', gap:'var(--gap)'}}>
            {services.map((s, i) => (
              <Box key={i}>
                <div style={{display:'flex', alignItems:'center', gap: 8}}>
                  <Tog on={s.on} />
                  <div style={{flex: 1, minWidth: 0}}>
                    <div style={{fontFamily:'var(--font-hand)', fontSize: 18, fontWeight: 700}}>{s.n}</div>
                    <div style={{fontFamily:'var(--font-mono)', fontSize: 10.5, color:'var(--ink-3)'}}>{s.sub}</div>
                  </div>
                  <Pill tone={s.status}>{s.status === 'idle' ? 'off' : s.status}</Pill>
                </div>
                <div className="div-cap">live</div>
                <div style={{fontFamily:'var(--font-mono)', fontSize: 11, color:'var(--ink-2)', minHeight: 14}}>{s.meta}</div>
                <div style={{display:'flex', gap: 6, marginTop: 8}}>
                  <Btn ghost>config</Btn>
                  <Btn ghost>logs</Btn>
                  <span style={{flex: 1}}></span>
                  <Btn>restart</Btn>
                </div>
              </Box>
            ))}
          </div>
        </main>
      </div>
      <Sticky style={{top: 64, right: 24}} rotate={-2}>
        public/exposed pill turns the topbar pill red — you can see it from any tab
      </Sticky>
    </WFFrame>
  );
}

function Services_Switchboard() {
  // big lever-style toggles arranged like a mixer/switchboard
  const groups = [
    ['transfer',   [['HTTP files', 'public', 'ok'], ['qBittorrent', 'on', 'ok'], ['ShareClip', 'off', 'idle']]],
    ['network',    [['DDNS', 'on', 'ok'], ['Tailscale', 'on', 'ok'], ['UPnP', 'off', 'idle']]],
    ['housekeeping', [['Nightly snap', 'on', 'ok'], ['Naming sweep', 'on', 'ok'], ['Log rotate', 'on', 'ok']]],
  ];
  return (
    <WFFrame>
      <WFTop active="Services" exposure="public" />
      <main className="wf-main" style={{padding:'var(--pad)', display:'flex', flexDirection:'column', gap:'var(--gap)'}}>
        <div style={{display:'flex', alignItems:'baseline', gap: 12}}>
          <Scrawl style={{fontSize: 28}}>switchboard</Scrawl>
          <span style={{fontFamily:'var(--font-mono)', fontSize:11, color:'var(--ink-3)'}}>master switch · all transfer can be killed at once</span>
          <span style={{flex: 1}}></span>
          <Btn primary style={{padding: '8px 16px'}}>STOP ALL TRANSFER</Btn>
        </div>
        <div style={{display:'grid', gridTemplateColumns:'repeat(3, 1fr)', gap:'var(--gap)', flex: 1, minHeight: 0}}>
          {groups.map(([g, items]) => (
            <Box key={g} title={g} meta={`${items.length}`}>
              <div style={{display:'flex', flexDirection:'column', gap: 14, marginTop: 4}}>
                {items.map(([n, state, st]) => {
                  const on = state === 'on' || state === 'public';
                  return (
                    <div key={n} style={{display:'flex', alignItems:'center', gap: 12}}>
                      {/* big lever */}
                      <div style={{
                        width: 36, height: 56, borderRadius: 8,
                        border: '1.5px solid var(--rule)',
                        background: 'var(--paper-2)',
                        position:'relative',
                      }}>
                        <span style={{
                          position:'absolute', left: 4, right: 4,
                          height: 22, borderRadius: 5,
                          background: on ? 'var(--accent)' : 'var(--ink-3)',
                          top: on ? 4 : 'auto', bottom: on ? 'auto' : 4,
                          boxShadow: '0 1px 0 rgba(0,0,0,0.18)',
                        }}></span>
                        <span style={{position:'absolute', top: -10, left: '50%', transform:'translateX(-50%)', fontFamily:'var(--font-mono)', fontSize: 8, color:'var(--ink-3)'}}>ON</span>
                        <span style={{position:'absolute', bottom: -10, left: '50%', transform:'translateX(-50%)', fontFamily:'var(--font-mono)', fontSize: 8, color:'var(--ink-3)'}}>OFF</span>
                      </div>
                      <div style={{flex: 1, minWidth: 0}}>
                        <div style={{fontFamily:'var(--font-hand)', fontSize: 17, fontWeight: 700, lineHeight: 1.1}}>{n}</div>
                        <div style={{fontFamily:'var(--font-mono)', fontSize: 10, color:'var(--ink-3)'}}>{state}</div>
                      </div>
                      <Pill tone={st}>{st === 'idle' ? 'off' : st}</Pill>
                    </div>
                  );
                })}
              </div>
            </Box>
          ))}
        </div>
      </main>
      <Note style={{bottom: 18, right: 22, width: 124}}>
        ★ tactile metaphor — feels like flipping a real switch on a rack
      </Note>
    </WFFrame>
  );
}

// ─── SETTINGS ───────────────────────────────────────────────────────
function Settings_Modules() {
  const modules = [
    ['files',     'HTTP file server + browser',  true,  'all'],
    ['downloads', 'qBittorrent integration',     true,  'mac-mini, nas-02'],
    ['monitor',   'system metrics',              true,  'all'],
    ['docker',    'container management',        true,  'mac-mini, nas-02'],
    ['terminal',  'web SSH + key manager',       true,  'all'],
    ['ddns',      'cloudflare/dynu DNS',         true,  'mac-mini'],
    ['shareclip', 'clipboard-style sharing',     false, 'all'],
    ['naming',    'directory cleanup sweeps',    false, 'mac-mini'],
    ['nodes',     'multi-node cluster',          true,  'master only'],
  ];
  return (
    <WFFrame>
      <WFTop active="Settings" exposure="lan" />
      <div className="wf-body">
        <WFSide active="settings" />
        <main className="wf-main" style={{padding:'var(--pad)', display:'flex', gap:'var(--gap)'}}>
          <Box title="modules" meta={`${modules.filter(m=>m[2]).length}/${modules.length} on`} style={{flex: 1.5}}>
            <div style={{display:'flex', flexDirection:'column'}}>
              {modules.map(([k, sub, on, scope], i) => (
                <div key={k} style={{display:'flex', alignItems:'center', gap: 12, padding: '10px 0', borderBottom: i<modules.length-1?'1px dashed var(--rule-soft)':0}}>
                  <Tog on={on} />
                  <div style={{flex:1, minWidth:0}}>
                    <div style={{fontFamily:'var(--font-mono)', fontSize: 12}}>{k}</div>
                    <div style={{fontFamily:'var(--font-mono)', fontSize: 10, color:'var(--ink-3)'}}>{sub}</div>
                  </div>
                  <span style={{fontFamily:'var(--font-mono)', fontSize: 10, color:'var(--ink-3)'}}>{scope}</span>
                  <Btn ghost>configure</Btn>
                </div>
              ))}
            </div>
          </Box>
          <div style={{flex: 1, display:'flex', flexDirection:'column', gap:'var(--gap)'}}>
            <Box title="exposure" meta="security">
              <div style={{display:'flex', flexDirection:'column', gap: 10}}>
                <div style={{display:'flex', alignItems:'center', gap: 8}}><Tog on={true} /><div style={{flex:1, fontSize: 12}}>LAN-only by default</div></div>
                <div style={{display:'flex', alignItems:'center', gap: 8}}><Tog on={true} /><div style={{flex:1, fontSize: 12}}>Allow public HTTP transfer</div><Pill tone="warn">on</Pill></div>
                <div style={{display:'flex', alignItems:'center', gap: 8}}><Tog on={false} /><div style={{flex:1, fontSize: 12}}>Allow public terminal</div></div>
              </div>
              <div className="div-cap">cap</div>
              <div style={{fontFamily:'var(--font-mono)', fontSize: 11, color:'var(--ink-2)'}}>50 GB / 24h · resets at 00:00</div>
            </Box>
            <Box title="storage">
              <div style={{display:'flex', flexDirection:'column', gap: 6, fontFamily:'var(--font-mono)', fontSize: 11}}>
                <div style={{display:'flex', justifyContent:'space-between'}}><span style={{color:'var(--ink-3)'}}>STORAGE_ROOT</span><span>/srv/Storage</span></div>
                <div style={{display:'flex', justifyContent:'space-between'}}><span style={{color:'var(--ink-3)'}}>WEB_PORT</span><span>1288</span></div>
                <div style={{display:'flex', justifyContent:'space-between'}}><span style={{color:'var(--ink-3)'}}>PUBLIC_HOST</span><span>example.com:1288</span></div>
              </div>
              <Btn ghost style={{marginTop: 10}}>edit .env</Btn>
            </Box>
          </div>
        </main>
      </div>
      <Sticky style={{top: 70, right: 24}} rotate={-3}>
        per-node scope on each module — small studios stay sane
      </Sticky>
    </WFFrame>
  );
}

function Settings_Form() {
  return (
    <WFFrame>
      <WFTop active="Settings" exposure="lan" />
      <div className="wf-body">
        <WFSide active="settings" />
        <main className="wf-main" style={{padding:'var(--pad)', display:'flex', gap:'var(--gap)'}}>
          {/* sub-nav */}
          <aside style={{width: 150, display:'flex', flexDirection:'column', gap: 2}}>
            {['general','exposure','modules','nodes','tokens','danger zone'].map((s,i) => (
              <a key={s} style={{
                padding: '6px 10px', borderRadius: 6,
                fontFamily:'var(--font-mono)', fontSize: 11.5,
                color: i===1?'var(--ink)':'var(--ink-2)',
                background: i===1?'var(--paper-2)':'transparent',
                outline: i===1?'1.5px solid var(--rule)':'none',
                outlineOffset: -1.5,
              }}>{s}</a>
            ))}
          </aside>
          <div style={{flex:1, display:'flex', flexDirection:'column', gap:'var(--gap)'}}>
            <Box title="public exposure" meta="security · LAN-first">
              <div style={{display:'flex', flexDirection:'column', gap: 14, marginTop: 4}}>
                {[
                  ['Public HTTP /http-files/', true,  'Anyone with the link can download. Subject to 24h cap.'],
                  ['Accept new downloads',     true,  'Off only stops new connections; ongoing transfers continue.'],
                  ['Public terminal access',   false, 'Strongly discouraged — keep on LAN-only.'],
                  ['Public ShareClip',         false, 'Read-only public share if enabled.'],
                ].map(([n, on, hint], i) => (
                  <div key={i} style={{display:'flex', gap: 12}}>
                    <Tog on={on} />
                    <div style={{flex: 1}}>
                      <div style={{fontSize: 13, color:'var(--ink)', fontWeight: 500}}>{n}</div>
                      <div style={{fontSize: 11.5, color:'var(--ink-2)', marginTop: 2}}>{hint}</div>
                    </div>
                  </div>
                ))}
              </div>
              <div className="div-cap">24h transfer cap</div>
              <div style={{display:'flex', alignItems:'center', gap: 12}}>
                <Prog pct={42} />
                <span style={{fontFamily:'var(--font-mono)', fontSize: 11, color:'var(--ink-2)'}}>21 GB · cap 50 GB</span>
                <Btn ghost>change</Btn>
              </div>
            </Box>
            <Box title="public host" meta="DDNS-fed">
              <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap: 10}}>
                <div>
                  <div style={{fontFamily:'var(--font-mono)', fontSize: 10, color:'var(--ink-3)', textTransform:'uppercase', letterSpacing:'.08em'}}>scheme</div>
                  <div className="placeholder" style={{height: 28, marginTop: 4}}>http  ·  https</div>
                </div>
                <div>
                  <div style={{fontFamily:'var(--font-mono)', fontSize: 10, color:'var(--ink-3)', textTransform:'uppercase', letterSpacing:'.08em'}}>host:port</div>
                  <div className="placeholder" style={{height: 28, marginTop: 4}}>example.com:1288</div>
                </div>
              </div>
            </Box>
          </div>
        </main>
      </div>
    </WFFrame>
  );
}

// ─── SHARECLIP ──────────────────────────────────────────────────────
function ShareClip_Timeline() {
  const items = [
    { kind: 'text',  who: 'mac-mini',  when: 'just now', body: 'wifi-guest · greenmoss-1842', tags: ['📌 pinned'] },
    { kind: 'image', who: 'iphone',    when: '14m',     body: '[ screenshot · 412 KB · 1170×2532 ]' },
    { kind: 'text',  who: 'thinkpad',  when: '32m',     body: 'curl -fsSL https://raw.githubusercontent.com/.../install.sh | bash' },
    { kind: 'file',  who: 'mac-mini',  when: '2h',      body: 'set-list-may.txt · 4 KB' },
    { kind: 'text',  who: 'nas-02',    when: 'yest.',   body: 'remember to renew domain · 14 days' },
  ];
  return (
    <WFFrame>
      <WFTop active="ShareClip" exposure="lan" />
      <div className="wf-body">
        <WFSide active="shareclip" />
        <main className="wf-main" style={{padding:'var(--pad)', display:'flex', gap:'var(--gap)'}}>
          {/* compose */}
          <Box style={{flex: 1.4, display:'flex', flexDirection:'column'}}>
            <div style={{display:'flex', alignItems:'baseline', gap: 10, marginBottom: 8}}>
              <Scrawl style={{fontSize: 22}}>paste anything</Scrawl>
              <span style={{fontFamily:'var(--font-mono)', fontSize: 10, color:'var(--ink-3)'}}>text · image · file · ⌘V</span>
            </div>
            <div className="placeholder" style={{minHeight: 100, marginBottom: 10}}>↓ drop here · or paste</div>
            <div style={{display:'flex', gap: 6, marginBottom: 14}}>
              <Btn ghost>📌 pin</Btn>
              <Btn ghost>⏱ expires in 24h</Btn>
              <span style={{flex:1}}></span>
              <Btn primary>send to fleet</Btn>
            </div>

            <div className="div-cap">timeline · 5 items</div>
            <div style={{display:'flex', flexDirection:'column', gap: 8, overflow:'hidden'}}>
              {items.map((it, i) => (
                <div key={i} style={{display:'flex', alignItems:'flex-start', gap: 10, padding: 10, border: '1.5px solid var(--rule-soft)', borderRadius: 8, background: 'var(--paper-2)'}}>
                  <span style={{
                    width: 22, height: 22, borderRadius: 4, flex: '0 0 auto',
                    background: it.kind==='image'?'var(--accent-soft)':it.kind==='file'?'var(--good-soft)':'transparent',
                    border: '1.5px solid var(--rule-soft)',
                    display:'flex', alignItems:'center', justifyContent:'center',
                    fontFamily:'var(--font-mono)', fontSize: 9, color:'var(--ink-2)',
                  }}>{it.kind[0].toUpperCase()}</span>
                  <div style={{flex: 1, minWidth: 0}}>
                    <div style={{fontFamily:'var(--font-mono)', fontSize: 10.5, color:'var(--ink-3)'}}>
                      {it.who} · {it.when} {it.tags && <span style={{color:'var(--accent)'}}>· {it.tags.join(' ')}</span>}
                    </div>
                    <div style={{fontFamily:'var(--font-mono)', fontSize: 11.5, color:'var(--ink)', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap'}}>{it.body}</div>
                  </div>
                  <Btn ghost>copy</Btn>
                </div>
              ))}
            </div>
          </Box>
          <aside style={{width: 180, display:'flex', flexDirection:'column', gap:'var(--gap)'}}>
            <Box title="devices" meta="3">
              {['mac-mini','thinkpad','nas-02'].map((d,i) => (
                <div key={d} style={{display:'flex', alignItems:'center', gap: 6, padding: '4px 0'}}>
                  <span className="dot" style={{width:6, height:6, borderRadius:'50%', background:'var(--good)'}}></span>
                  <span style={{fontFamily:'var(--font-mono)', fontSize: 11, flex:1}}>{d}</span>
                  <span style={{fontFamily:'var(--font-mono)', fontSize: 9.5, color:'var(--ink-3)'}}>active</span>
                </div>
              ))}
            </Box>
            <Box title="quota">
              <div style={{display:'flex', justifyContent:'space-between', fontFamily:'var(--font-mono)', fontSize:10.5, marginBottom: 4, color:'var(--ink-2)'}}>
                <span>this week</span><span>2.1 / 5 MB</span>
              </div>
              <Prog pct={42} />
              <div style={{fontFamily:'var(--font-mono)', fontSize: 10, color:'var(--ink-3)', marginTop: 6}}>auto-prune older than 7d</div>
            </Box>
          </aside>
        </main>
      </div>
      <Sticky style={{top: 70, right: 24}} rotate={2}>chat-like timeline · feels familiar to anyone using messages</Sticky>
    </WFFrame>
  );
}

function ShareClip_Wall() {
  const items = [
    { who: 'mac-mini', when: 'just now', text: 'wifi-guest · greenmoss-1842', pinned: true },
    { who: 'iphone',   when: '14m',      text: '[image · 412 KB]', img: true },
    { who: 'thinkpad', when: '32m',      text: 'curl -fsSL …/install.sh | bash' },
    { who: 'mac-mini', when: '2h',       text: 'set-list-may.txt' },
    { who: 'nas-02',   when: 'yest.',    text: 'renew domain · 14 days' },
    { who: 'thinkpad', when: '2 days',   text: '⌘ docker compose -f /srv/media/up.yml restart' },
    { who: 'mac-mini', when: '3 days',   text: '[image · 2.1 MB · session whiteboard]', img: true },
    { who: 'nas-02',   when: '5 days',   text: 'NAS spare drive in drawer 3' },
  ];
  return (
    <WFFrame>
      <WFTop active="ShareClip" exposure="lan" />
      <main className="wf-main" style={{padding:'var(--pad)', display:'flex', flexDirection:'column', gap:'var(--gap)'}}>
        <div style={{display:'flex', alignItems:'flex-end', gap: 14}}>
          <div style={{flex: 1.3}}>
            <Scrawl style={{fontSize: 30}}>shared wall</Scrawl>
            <div style={{fontFamily:'var(--font-mono)', fontSize: 11, color:'var(--ink-3)', marginTop: 4}}>everything pinned to your fleet · 8 items</div>
          </div>
          <div style={{flex: 1}}>
            <div className="placeholder" style={{height: 60, fontSize: 11}}>↓ drop · paste · type</div>
          </div>
          <Btn primary>send</Btn>
        </div>

        <div style={{display:'grid', gridTemplateColumns:'repeat(4, 1fr)', gridAutoRows: '120px', gap: 'var(--gap)', flex: 1, minHeight: 0}}>
          {items.map((it, i) => (
            <div key={i} style={{
              border: '1.5px solid var(--rule)', borderRadius: 6,
              padding: 10, position:'relative',
              background: it.pinned ? 'var(--postit)' : 'var(--paper)',
              color: it.pinned ? 'var(--postit-ink)' : 'var(--ink)',
              transform: `rotate(${[(-1.5),0.8,-0.6,1.4,-1.0,0.6,-1.2,0.4][i]}deg)`,
              boxShadow: '1px 2px 0 rgba(0,0,0,0.06)',
              display:'flex', flexDirection:'column', gap: 4,
            }}>
              <div style={{fontFamily:'var(--font-mono)', fontSize: 9.5, color: it.pinned?'var(--postit-ink)':'var(--ink-3)', display:'flex', justifyContent:'space-between'}}>
                <span>{it.who}</span><span>{it.when}</span>
              </div>
              {it.img
                ? <div className="placeholder" style={{flex: 1, fontSize: 10}}>image</div>
                : <div style={{fontFamily: it.pinned ? 'var(--font-hand)' : 'var(--font-mono)', fontSize: it.pinned ? 16 : 11, lineHeight: 1.25, flex:1, overflow:'hidden'}}>
                    {it.text}
                  </div>}
              {it.pinned && <span style={{position:'absolute', top: -6, right: 8, fontFamily:'var(--font-hand)', fontSize: 14}}>📌</span>}
            </div>
          ))}
        </div>
      </main>
      <Note style={{bottom: 18, right: 22, width: 124}}>★ pin-board metaphor — pinned notes get the post-it tint</Note>
    </WFFrame>
  );
}

window.MinorVariants = {
  docker:    [{id:'list', label:'A · Container list', comp: Docker_List},
              {id:'compose', label:'B · Compose stacks', comp: Docker_Compose}],
  terminal:  [{id:'full', label:'A · Single shell + keys', comp: Terminal_Full},
              {id:'tabs', label:'B · Multi-pane tile',     comp: Terminal_Tabs}],
  services:  [{id:'cards', label:'A · Service cards',      comp: Services_Cards},
              {id:'switch', label:'B · Switchboard',        comp: Services_Switchboard}],
  settings:  [{id:'modules', label:'A · Module toggles',   comp: Settings_Modules},
              {id:'form',    label:'B · Sectioned form',   comp: Settings_Form}],
  shareclip: [{id:'timeline', label:'A · Chat timeline',   comp: ShareClip_Timeline},
              {id:'wall',     label:'B · Pinboard wall',   comp: ShareClip_Wall}],
};
