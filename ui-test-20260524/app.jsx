/* global React, ReactDOM, DesignCanvas, DCSection, DCArtboard,
   TweaksPanel, useTweaks, TweakSection, TweakRadio, TweakSelect,
   DashboardVariants, FilesVariants, MonitorVariants, NodesVariants, MinorVariants */

const { useEffect } = React;

// One artboard per variant, sized to feel like a real app viewport.
const FRAME_W = 960;
const FRAME_H = 600;

// DCSection inspects child types directly, so we can't wrap the boards in a
// component — return raw DCArtboard elements via a plain helper instead.
function variantBoards(variants, theme, density) {
  return variants.map(v => {
    const Comp = v.comp;
    return (
      <DCArtboard key={v.id} id={v.id} label={v.label} width={FRAME_W} height={FRAME_H}>
        <div data-theme={theme} data-density={density} style={{width:'100%', height:'100%'}}>
          <Comp />
        </div>
      </DCArtboard>
    );
  });
}

function App() {
  const t = useTweaks(/*EDITMODE-BEGIN*/{
    "theme": "cream",
    "density": "cozy"
  }/*EDITMODE-END*/);

  // mirror tweak state onto the document root so the canvas chrome (cream pad)
  // stays light while the wireframe frames re-tone via their own data-theme.
  useEffect(() => {
    document.documentElement.setAttribute('data-density', t.density);
  }, [t.density]);

  return (
    <>
      <DesignCanvas>
        <DCSection id="intro" title="AfterClaw · wireframe explorations" subtitle="9 surfaces · 22 variants · warm low-fi">
          <DCArtboard id="brief" label="brief" width={520} height={FRAME_H}>
            <div style={{
              padding: 36, height: '100%', boxSizing:'border-box',
              background: 'var(--paper)', color: 'var(--ink)',
              fontFamily: 'var(--font-ui)', overflow:'auto',
            }}>
              <div style={{fontFamily:'var(--font-hand)', fontSize: 44, fontWeight: 700, lineHeight: 1, marginBottom: 8}}>
                afterclaw <span style={{color:'var(--accent)'}}>/</span> wireframes
              </div>
              <div style={{fontFamily:'var(--font-mono)', fontSize: 11, color:'var(--ink-3)', marginBottom: 18, letterSpacing:'.04em'}}>
                v0 · low-fi · cream · may 9, 2026
              </div>
              <p style={{fontSize: 13.5, color:'var(--ink-2)', lineHeight: 1.55, marginTop: 0}}>
                Nine surfaces from <code style={{fontFamily:'var(--font-mono)', fontSize: 12}}>fcc/modules/*</code> sketched
                three-ish ways each. Three big variations on the
                primary screens (Dashboard, Files, Monitor, Nodes), two on the
                supporting ones. Tone is friendly home-server — warm cream,
                hand-lettered headlines, mono for data, a single coral accent.
              </p>
              <div className="div-cap">how to read</div>
              <ul style={{paddingLeft: 18, fontSize: 12.5, color:'var(--ink-2)', lineHeight: 1.7}}>
                <li>scroll/pan the canvas; ⌘-scroll to zoom</li>
                <li>click <em>⛶</em> on any artboard for fullscreen focus</li>
                <li>drag artboards to reorder — focus your shortlist on one row</li>
                <li>open <strong>Tweaks</strong> from the toolbar to retone all sketches at once</li>
              </ul>
              <div className="div-cap">surfaces · top to bottom</div>
              <ol style={{paddingLeft: 18, fontFamily:'var(--font-mono)', fontSize: 11.5, color:'var(--ink-2)', lineHeight: 1.85}}>
                <li>Dashboard · 3</li>
                <li>Files + transfers · 3</li>
                <li>System monitor · 3</li>
                <li>Multi-node · 3</li>
                <li>Docker · 2</li>
                <li>Web terminal · 2</li>
                <li>Services / DDNS · 2</li>
                <li>Settings · 2</li>
                <li>ShareClip · 2</li>
              </ol>
              <div className="div-cap">picked direction?</div>
              <p style={{fontSize: 12.5, color:'var(--ink-2)', lineHeight: 1.5}}>
                Tell me which artboard from each row to keep and I'll fork those into a single hi-fi prototype with real flows.
              </p>
            </div>
          </DCArtboard>
        </DCSection>

        <DCSection id="dashboard" title="01 · Dashboard" subtitle="primary surface — cards vs. status board vs. terminal log">
          {variantBoards(DashboardVariants, t.theme, t.density)}
        </DCSection>

        <DCSection id="files" title="02 · Files & HTTP transfers" subtitle="browsing + uploading + sharing">
          {variantBoards(FilesVariants, t.theme, t.density)}
        </DCSection>

        <DCSection id="monitor" title="03 · System monitor" subtitle="cpu / mem / disk / temp · history">
          {variantBoards(MonitorVariants, t.theme, t.density)}
        </DCSection>

        <DCSection id="nodes" title="04 · Multi-node" subtitle="cluster overview · drill-in">
          {variantBoards(NodesVariants, t.theme, t.density)}
        </DCSection>

        <DCSection id="docker" title="05 · Docker" subtitle="containers + compose stacks">
          {variantBoards(MinorVariants.docker, t.theme, t.density)}
        </DCSection>

        <DCSection id="terminal" title="06 · Web terminal" subtitle="single shell vs. multi-pane">
          {variantBoards(MinorVariants.terminal, t.theme, t.density)}
        </DCSection>

        <DCSection id="services" title="07 · Services / DDNS" subtitle="cards vs. switchboard">
          {variantBoards(MinorVariants.services, t.theme, t.density)}
        </DCSection>

        <DCSection id="settings" title="08 · Settings" subtitle="modules + exposure + env">
          {variantBoards(MinorVariants.settings, t.theme, t.density)}
        </DCSection>

        <DCSection id="shareclip" title="09 · ShareClip" subtitle="clipboard-style sharing across the fleet">
          {variantBoards(MinorVariants.shareclip, t.theme, t.density)}
        </DCSection>
      </DesignCanvas>

      <TweaksPanel title="Tweaks">
        <TweakSection label="Sketch tone">
          <TweakRadio
            label="Theme"
            value={t.theme}
            options={[{value:'cream',label:'Cream'},{value:'dim',label:'Dim'},{value:'dark',label:'Dark'}]}
            onChange={v => t.setTweak('theme', v)} />
          <TweakRadio
            label="Density"
            value={t.density}
            options={[{value:'compact',label:'Compact'},{value:'cozy',label:'Cozy'},{value:'roomy',label:'Roomy'}]}
            onChange={v => t.setTweak('density', v)} />
        </TweakSection>
      </TweaksPanel>
    </>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
