/* global React, WFTop, WFSide, Box, Pill, Sticky, Note, Spark, Prog, Btn, Tog, Scrawl, Bars */

// File browser & HTTP transfer page.
//   A · Two-pane classic    — sidebar tree + file list (most boring, most familiar)
//   B · Drawer + grid       — card grid of recent shares with a transfer drawer
//   C · Pipeline kanban     — queued · uploading · done columns (transfer-as-pipeline)

const SAMPLE_FILES = [
  ['dir',  'Music',                  '—',      '4d ago'],
  ['dir',  'Photos',                 '—',      '12h ago'],
  ['dir',  'Backups',                '—',      '2h ago'],
  ['dir',  'studio-projects',        '—',      '38m ago'],
  ['file', '04-master-mix.wav',      '218 MB', 'just now'],
  ['file', 'backup-2026-05.tar',     '4.2 GB', '2h ago'],
  ['file', 'photos-iphone.zip',      '1.1 GB', '14m ago'],
  ['file', 'set-list-may.txt',       '4 KB',   '3d ago'],
  ['file', 'documents-q2.zip',       '88 MB',  'yesterday'],
];

function FileIcon({ kind }) {
  return <span className={`ficon ${kind === 'dir' ? 'dir' : ''}`}></span>;
}

// ─── A · Two-pane classic ───────────────────────────────────────────
function Files_TwoPane() {
  return (
    <WFFrame>
      <WFTop active="Files" exposure="lan" />
      <div className="wf-body">
        <WFSide active="files" />
        <main className="wf-main" style={{display:'flex', gap:'var(--gap)', padding:'var(--pad)'}}>
          {/* tree */}
          <aside className="box" style={{width: 180, padding: 10, fontFamily:'var(--font-mono)', fontSize: 11.5}}>
            <div style={{fontFamily:'var(--font-mono)', fontSize: 10, color:'var(--ink-3)', textTransform:'uppercase', letterSpacing:'.08em', marginBottom: 8}}>STORAGE_ROOT</div>
            <div style={{display:'flex', flexDirection:'column', gap: 3, color:'var(--ink-2)'}}>
              <span>▾ /srv/Storage</span>
              <span style={{paddingLeft: 12}}>▸ Music</span>
              <span style={{paddingLeft: 12}}>▸ Photos</span>
              <span style={{paddingLeft: 12, color:'var(--ink)'}}>▾ Backups</span>
              <span style={{paddingLeft: 24}}>▸ daily</span>
              <span style={{paddingLeft: 24, background:'var(--accent-soft)', borderRadius: 4, padding:'1px 4px 1px 24px', color:'var(--ink)'}}>nightly</span>
              <span style={{paddingLeft: 12}}>▸ studio-projects</span>
              <span style={{paddingLeft: 12}}>▸ shared</span>
            </div>
            <div className="div-cap">free · 2.1 TB</div>
            <Prog pct={71} />
          </aside>

          {/* list */}
          <div style={{flex: 1, display:'flex', flexDirection:'column', gap: 'var(--gap)', minWidth: 0}}>
            <div style={{display:'flex', alignItems:'center', gap: 8}}>
              <span style={{fontFamily:'var(--font-mono)', fontSize: 11.5, color:'var(--ink-2)'}}>
                /srv/Storage <span style={{color:'var(--ink-3)'}}>/</span> Backups <span style={{color:'var(--ink-3)'}}>/</span> <span style={{color:'var(--ink)'}}>nightly</span>
              </span>
              <span style={{flex:1}}></span>
              <Btn ghost>⌖ search</Btn>
              <Btn>↑ upload</Btn>
              <Btn primary>＋ link</Btn>
            </div>
            <Box style={{flex:1, padding: 0, overflow:'hidden'}}>
              <table className="tbl" style={{tableLayout:'fixed'}}>
                <thead>
                  <tr>
                    <th style={{paddingLeft: 14, width: '52%'}}>name</th>
                    <th style={{width: '12%'}}>size</th>
                    <th style={{width: '18%'}}>modified</th>
                    <th style={{width: '18%'}}>actions</th>
                  </tr>
                </thead>
                <tbody>
                  {SAMPLE_FILES.map((r, i) => (
                    <tr key={i}>
                      <td className="k" style={{paddingLeft: 14}}>
                        <span style={{display:'inline-flex', alignItems:'center', gap: 8}}>
                          <FileIcon kind={r[0]} /> {r[1]}
                        </span>
                      </td>
                      <td>{r[2]}</td>
                      <td>{r[3]}</td>
                      <td style={{display:'flex', gap: 4}}>
                        <Btn ghost>copy link</Btn>
                        {r[0] === 'file' && <Btn ghost>↓</Btn>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Box>
          </div>
        </main>
      </div>
      <Sticky style={{top: 78, right: 24}} rotate={3}>tree on left, list on right. classic. boring is fine.</Sticky>
    </WFFrame>
  );
}

// ─── B · Card grid + transfer drawer ────────────────────────────────
function Files_Drawer() {
  return (
    <WFFrame>
      <WFTop active="Files" exposure="lan" />
      <main className="wf-main" style={{padding:'var(--pad)', display:'flex', flexDirection:'column', gap:'var(--gap)'}}>
        <div style={{display:'flex', alignItems:'baseline', gap: 14}}>
          <Scrawl style={{fontSize: 28}}>shared with the world</Scrawl>
          <span style={{fontFamily:'var(--font-mono)', fontSize: 11, color:'var(--ink-3)'}}>/srv/Storage · 9 items · drag in to upload</span>
          <span style={{flex:1}}></span>
          <Btn>view: list</Btn>
          <Btn primary>＋ new share link</Btn>
        </div>

        <div style={{display:'grid', gridTemplateColumns:'repeat(4, 1fr)', gap:'var(--gap)', flex: 1, minHeight: 0}}>
          {SAMPLE_FILES.slice(0, 8).map((r, i) => (
            <Box key={i} style={{display:'flex', flexDirection:'column', gap: 8}}>
              <div className="placeholder" style={{aspectRatio:'4/3'}}>
                {r[0] === 'dir' ? '▢ folder' : r[1].split('.').pop()?.toUpperCase()}
              </div>
              <div style={{fontFamily:'var(--font-mono)', fontSize: 11.5, color:'var(--ink)', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap'}}>{r[1]}</div>
              <div style={{display:'flex', justifyContent:'space-between', fontFamily:'var(--font-mono)', fontSize: 10, color:'var(--ink-3)'}}>
                <span>{r[2]}</span>
                <span>{r[3]}</span>
              </div>
              <div style={{display:'flex', gap:4}}>
                <Btn ghost style={{flex:1}}>copy link</Btn>
              </div>
            </Box>
          ))}
        </div>

        {/* persistent transfer drawer */}
        <Box title="transfer drawer · 3 active" meta="drag here to queue" tinted>
          <div style={{display:'grid', gridTemplateColumns:'repeat(3, 1fr)', gap: 12}}>
            {[['04-master-mix.wav', 62, '8.4 MB/s', 'up'],
              ['backup-2026-05.tar', 38, '3.1 MB/s', 'up'],
              ['photos-iphone.zip', 91, '2.7 MB/s', 'up']].map(([n,p,r,d], i) => (
              <div key={i} style={{display:'flex', flexDirection:'column', gap: 4}}>
                <div style={{display:'flex', justifyContent:'space-between', fontFamily:'var(--font-mono)', fontSize: 11}}>
                  <span style={{overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap', maxWidth:'70%'}}>↑ {n}</span>
                  <span style={{color:'var(--ink-3)'}}>{p}%</span>
                </div>
                <Prog pct={p} striped />
                <div style={{fontFamily:'var(--font-mono)', fontSize: 10, color:'var(--ink-3)'}}>{r}</div>
              </div>
            ))}
          </div>
        </Box>
      </main>
      <Note style={{top: 88, right: 14, width: 124}}>previews + drawer = friendlier for non-CLI users</Note>
    </WFFrame>
  );
}

// ─── C · Pipeline kanban ────────────────────────────────────────────
function Files_Pipeline() {
  return (
    <WFFrame>
      <WFTop active="Files" exposure="public" />
      <main className="wf-main" style={{padding:'var(--pad)', display:'flex', flexDirection:'column', gap:'var(--gap)'}}>
        {/* command-bar style search */}
        <div className="box" style={{display:'flex', alignItems:'center', gap: 10, padding: '8px 12px'}}>
          <span style={{fontFamily:'var(--font-mono)', color:'var(--accent)'}}>⌘</span>
          <span style={{fontFamily:'var(--font-mono)', fontSize: 12, color:'var(--ink-3)'}}>search files · paste link · type a path…</span>
          <span style={{flex:1}}></span>
          <span style={{fontFamily:'var(--font-mono)', fontSize: 10, color:'var(--ink-3)'}}>4.2 GB / 24h · cap: 50 GB</span>
          <Prog pct={42} />
        </div>

        <div style={{display:'grid', gridTemplateColumns:'repeat(3, 1fr)', gap:'var(--gap)', flex: 1, minHeight: 0}}>
          {/* queued */}
          <Box title="queued" meta="4">
            {['documents-q2.zip','set-list-may.txt','live-set.flac','session-2.wav'].map((n,i) => (
              <div key={n} className="box ghost" style={{padding: 8, marginBottom: 6, display:'flex', alignItems:'center', gap: 8}}>
                <FileIcon kind="file" />
                <div style={{flex:1, minWidth:0, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap', fontFamily:'var(--font-mono)', fontSize: 11.5}}>{n}</div>
                <span style={{fontFamily:'var(--font-mono)', fontSize: 10, color:'var(--ink-3)'}}>·{i+1}</span>
              </div>
            ))}
          </Box>

          {/* uploading */}
          <Box title="uploading" meta="3 active">
            {[['04-master-mix.wav', 62, '8.4 MB/s'],
              ['backup-2026-05.tar', 38, '3.1 MB/s'],
              ['photos-iphone.zip', 91, '2.7 MB/s']].map(([n,p,r], i) => (
              <div key={i} className="box" style={{padding: 10, marginBottom: 8, background:'var(--paper-2)'}}>
                <div style={{display:'flex', justifyContent:'space-between', fontFamily:'var(--font-mono)', fontSize: 11.5, marginBottom: 6}}>
                  <span style={{overflow:'hidden', textOverflow:'ellipsis', maxWidth:'70%', whiteSpace:'nowrap'}}>{n}</span>
                  <span style={{color: 'var(--accent)'}}>↑ {p}%</span>
                </div>
                <Prog pct={p} striped />
                <div style={{display:'flex', justifyContent:'space-between', fontFamily:'var(--font-mono)', fontSize: 10, color:'var(--ink-3)', marginTop: 6}}>
                  <span>{r}</span>
                  <span>eta {Math.round((100-p)/8)}m</span>
                </div>
              </div>
            ))}
          </Box>

          {/* done */}
          <Box title="done · today" meta="11">
            {[['nightly-snap.tar', '4h ago'],
              ['hello-world.mp4', '6h ago'],
              ['album-art.png', '7h ago'],
              ['weekly-mix.flac', '8h ago'],
              ['receipts-q2.zip', 'yesterday']].map(([n, t], i) => (
              <div key={i} style={{display:'flex', alignItems:'center', gap: 8, padding: '5px 0', borderBottom: '1px dashed var(--rule-soft)'}}>
                <span style={{color:'var(--good)'}}>✓</span>
                <div style={{flex:1, fontFamily:'var(--font-mono)', fontSize: 11.5, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap'}}>{n}</div>
                <span style={{fontFamily:'var(--font-mono)', fontSize: 10, color:'var(--ink-3)'}}>{t}</span>
                <Btn ghost>link</Btn>
              </div>
            ))}
          </Box>
        </div>
      </main>
      <Sticky style={{top: 70, right: 24}} rotate={-2}>
        ★ surprising one — files as a pipeline. great when uploads dominate.
      </Sticky>
    </WFFrame>
  );
}

window.FilesVariants = [
  { id: 'twopane',  label: 'A · Two-pane classic', comp: Files_TwoPane },
  { id: 'drawer',   label: 'B · Grid + drawer',     comp: Files_Drawer },
  { id: 'pipeline', label: 'C · Transfer pipeline', comp: Files_Pipeline },
];
