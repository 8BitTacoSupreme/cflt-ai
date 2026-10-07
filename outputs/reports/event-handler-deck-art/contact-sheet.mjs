// Builds the reviewable contact sheet by inlining every SVG into one page.
import { readFileSync, writeFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const svg = n => readFileSync(join(here, 'svg', n + '.svg'), 'utf8')
  .replace(/<\?xml[^>]*\?>\s*/g, '')
  .replace(/<!DOCTYPE[^>]*>\s*/g, '');

const ASSETS = [
  { id: 'ART-1',  slide: 'S4',  file: 'art-01-pattern-taxonomy',      title: 'The catalog at a glance',
    kind: 'hand-authored', status: 'revised',
    note: 'Two chips added. Share-group worker sits bottom-left in teal — the one pattern that cannot move up or right, because it has no state, no EOS and no key ordering. Outbox / CDC ingress covers S18, which v1.0 left off the grid.' },
  { id: 'ART-2',  slide: 'S5',  file: 'art-02-handler-anatomy',       title: 'Handler reference anatomy',
    kind: 'mermaid', status: 'unchanged',
    note: 'The nine parts every handler has. Amber marks the two exits people forget to build.' },
  { id: 'ART-3',  slide: 'S7',  file: 'art-03-delivery-semantics',    title: 'Delivery semantics decision tree',
    kind: 'mermaid', status: 'bug fixed',
    note: 'v1.0 could route an external sink to Transactional EOS. EOS does not cross the cluster boundary, so that branch recommended something that cannot work. The “Is the effect inside Kafka?” node now gates both EOS terminals. Portrait — give it a full slide or a right-half column.' },
  { id: 'ART-4',  slide: 'S13', file: 'art-04-saga',                  title: 'Saga / process manager',
    kind: 'mermaid', status: 'unchanged',
    note: 'Portrait. Every non-terminal state carries a timeout and a compensating action.' },
  { id: 'ART-5',  slide: 'S14', file: 'art-05-request-reply',         title: 'Request–reply over Kafka',
    kind: 'mermaid', status: 'unchanged',
    note: 'Codified so it gets done once, well.' },
  { id: 'ART-6',  slide: 'S15', file: 'art-06-retry-ladder',          title: 'Error taxonomy & retry ladder',
    kind: 'mermaid', status: 'rewired',
    note: 'v1.0 implied delay consumers execute business logic. They wait and re-publish. The ladder is now a contained subgraph feeding one re-publish node, drawn as a return node rather than a back-edge so it reads left to right. Wide and short — full slide width, about a third of the height.' },
  { id: 'ART-7',  slide: 'S17', file: 'art-07-claim-check',           title: 'Claim check',
    kind: 'mermaid', status: 'unchanged',
    note: 'Open item: the slide wants the real max message size for your cluster type beside it. Not confirmed via confluent-docs — the Cloud quotas page does not carry it.' },
  { id: 'ART-8',  slide: 'S18', file: 'art-08-outbox-cdc',            title: 'Outbox & CDC ingress',
    kind: 'mermaid', status: 'unchanged',
    note: 'Both paths converge on the same downstream handler contract.' },
  { id: 'ART-9',  slide: 'S21', file: 'art-09-test-pyramid',          title: 'The streaming test pyramid',
    kind: 'hand-authored', status: 'revised',
    note: 'Five tiers with the contract gate second — the cheapest check in the stack, so it runs earliest. v1.0’s slide copy listed four tiers with contract fourth; the art was right, so the slide was corrected instead.' },
  { id: 'ART-10', slide: 'S24', file: 'art-10-environment-topology',  title: 'Environment topology',
    kind: 'hand-authored', status: 'unchanged',
    note: 'Lock glyph on prod only. The Terraform bar underneath is the load-bearing element.' },
  { id: 'ART-11', slide: 'S25', file: 'art-11-cicd-schema-gate',      title: 'CI/CD with the schema gate',
    kind: 'mermaid', status: 'revised',
    note: 'Two distinct gates now: compatibility is syntactic, Data Contract rules carry meaning. Drawing them separately is what makes S25’s caveat visible rather than a verbal footnote.' },
  { id: 'ART-12', slide: 'S26', file: 'art-12-blue-green',            title: 'Shadow / blue-green consumer deploy',
    kind: 'mermaid', status: 'revised',
    note: 'Green starts at blue’s committed offsets, not earliest. The double-read cost is annotated because “leave it shadowing for a while” is how this pattern gets banned.' },
  { id: 'ART-13', slide: 'S30', file: 'art-13-maturity-model',        title: 'Maturity model',
    kind: 'hand-authored', status: 'unchanged',
    note: 'Carries the five scorecard axes, so S30 needs no second graphic.' },
  { id: 'ART-14', slide: 'S7',  file: 'art-14-eos-boundary',          title: 'The exactly-once boundary',
    kind: 'hand-authored', status: 'new',
    note: 'Pairs with ART-3 on S7. The boundary is the strongest element on purpose; the single amber crossing arrow is the only amber in the image. This is S2’s failure #2 in one picture.' },
  { id: 'ART-15', slide: 'S12', file: 'art-15-cost-diagonal',         title: 'What the diagonal costs',
    kind: 'hand-authored', status: 'new',
    note: 'Reuses ART-1’s geometry so it reads as a callback. Four levers, no dollar figures — rates change, the levers do not.' },
  { id: 'ART-16', slide: 'S29', file: 'art-16-handler-dr',            title: 'Handler-side DR',
    kind: 'mermaid', status: 'new',
    note: 'The two amber elements are the two things teams do not plan: state restore time, and the human decision to route. The link itself is the easy part.' },
];

const STATUS_TONE = { 'new': 'new', 'revised': 'revised', 'bug fixed': 'fix', 'rewired': 'fix', 'unchanged': 'base' };

const cards = ASSETS.map(a => `
      <article class="asset" id="${a.id.toLowerCase()}">
        <header class="asset-head">
          <div class="asset-ident">
            <span class="slide">${a.slide}</span>
            <h2>${a.title}</h2>
          </div>
          <div class="asset-meta">
            <span class="tag tag--${STATUS_TONE[a.status]}">${a.status}</span>
            <span class="tag tag--kind">${a.kind}</span>
            <code>${a.id}</code>
          </div>
        </header>
        <div class="board">${svg(a.file)}</div>
        <footer class="asset-foot">
          <p>${a.note}</p>
          <code class="path">svg/${a.file}.svg</code>
        </footer>
      </article>`).join('\n');

const html = `<title>Event Handler Deck — Art Contact Sheet</title>
<style>
  :root {
    --ink:        #12233d;
    --ink-soft:   #4d5f79;
    --ink-faint:  #7d8ca3;
    --ground:     #f7f8fb;
    --surface:    #ffffff;
    --line:       #dfe4ed;
    --line-soft:  #ebeef4;
    --indigo:     #173a6c;
    --blue:       #0074e4;
    --teal:       #00a6a0;
    --amber:      #f2a900;
    --amber-ink:  #8a6100;
    --board:      #ffffff;
    --board-line: #e3e7ee;
    --shadow: 0 1px 2px rgba(18,35,61,.05), 0 8px 24px -12px rgba(18,35,61,.18);
    --sans: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
    --mono: ui-monospace, SFMono-Regular, "SF Mono", Menlo, monospace;
  }
  @media (prefers-color-scheme: dark) {
    :root:not([data-theme="light"]) {
      --ink:       #e6ecf5;
      --ink-soft:  #a3b1c6;
      --ink-faint: #74849c;
      --ground:    #0e1520;
      --surface:   #161f2e;
      --line:      #27344a;
      --line-soft: #1e2a3c;
      --indigo:    #8fb4e8;
      --blue:      #4ca0f0;
      --teal:      #35c4bd;
      --amber:     #f5bb3c;
      --amber-ink: #f5bb3c;
      --shadow: 0 1px 2px rgba(0,0,0,.4), 0 8px 24px -12px rgba(0,0,0,.7);
    }
  }
  :root[data-theme="dark"] {
    --ink:       #e6ecf5;
    --ink-soft:  #a3b1c6;
    --ink-faint: #74849c;
    --ground:    #0e1520;
    --surface:   #161f2e;
    --line:      #27344a;
    --line-soft: #1e2a3c;
    --indigo:    #8fb4e8;
    --blue:      #4ca0f0;
    --teal:      #35c4bd;
    --amber:     #f5bb3c;
    --amber-ink: #f5bb3c;
    --shadow: 0 1px 2px rgba(0,0,0,.4), 0 8px 24px -12px rgba(0,0,0,.7);
  }

  * { box-sizing: border-box; }
  body {
    margin: 0;
    background: var(--ground);
    color: var(--ink);
    font-family: var(--sans);
    font-size: 16px;
    line-height: 1.55;
    -webkit-font-smoothing: antialiased;
  }
  .wrap { max-width: 1180px; margin: 0 auto; padding: 0 24px 96px; }

  .masthead {
    display: flex; flex-direction: column; gap: 20px;
    padding: 64px 0 36px;
    border-bottom: 2px solid var(--ink);
  }
  .eyebrow {
    font-family: var(--mono); font-size: 12px; letter-spacing: .13em;
    text-transform: uppercase; color: var(--ink-faint);
  }
  h1 {
    margin: 0; font-size: clamp(30px, 4.4vw, 46px); line-height: 1.08;
    letter-spacing: -.022em; font-weight: 700; text-wrap: balance;
  }
  .standfirst { margin: 0; max-width: 62ch; color: var(--ink-soft); font-size: 17.5px; }

  .facts { display: flex; flex-wrap: wrap; gap: 8px 28px; margin-top: 4px; }
  .fact { display: flex; align-items: baseline; gap: 8px; }
  .fact dt { font-family: var(--mono); font-size: 11.5px; letter-spacing: .1em;
             text-transform: uppercase; color: var(--ink-faint); margin: 0; }
  .fact dd { margin: 0; font-size: 15px; font-variant-numeric: tabular-nums; }

  .brief {
    margin: 40px 0 0; padding: 26px 28px;
    background: var(--surface); border: 1px solid var(--line);
    border-left: 3px solid var(--amber); border-radius: 3px;
  }
  .brief h3 { margin: 0 0 14px; font-size: 13px; letter-spacing: .1em;
              text-transform: uppercase; color: var(--amber-ink); font-family: var(--mono); }
  .brief ol { margin: 0; padding-left: 20px; display: flex; flex-direction: column; gap: 11px; }
  .brief li { color: var(--ink-soft); max-width: 82ch; }
  .brief strong { color: var(--ink); font-weight: 600; }

  .swatches { display: flex; flex-wrap: wrap; gap: 18px; margin: 28px 0 0; }
  .swatch { display: flex; align-items: center; gap: 9px; }
  .chip { width: 15px; height: 15px; border-radius: 3px; border: 1px solid rgba(0,0,0,.16); }
  .swatch span { font-family: var(--mono); font-size: 12px; color: var(--ink-soft); }

  .sheet { display: flex; flex-direction: column; gap: 40px; margin-top: 48px; }

  .asset {
    background: var(--surface); border: 1px solid var(--line);
    border-radius: 4px; box-shadow: var(--shadow); overflow: hidden;
    scroll-margin-top: 24px;
  }
  .asset-head {
    display: flex; flex-wrap: wrap; gap: 12px 20px;
    align-items: baseline; justify-content: space-between;
    padding: 20px 24px 16px; border-bottom: 1px solid var(--line-soft);
  }
  .asset-ident { display: flex; align-items: baseline; gap: 14px; min-width: 0; }
  .slide {
    font-family: var(--mono); font-size: 13px; font-weight: 600;
    color: var(--surface); background: var(--indigo);
    padding: 3px 8px; border-radius: 3px; flex: none;
    font-variant-numeric: tabular-nums;
  }
  .asset h2 { margin: 0; font-size: 20px; letter-spacing: -.012em; font-weight: 650; }
  .asset-meta { display: flex; align-items: center; gap: 10px; }
  .asset-meta code { font-family: var(--mono); font-size: 12.5px; color: var(--ink-faint); }
  .tag {
    font-family: var(--mono); font-size: 11px; letter-spacing: .07em;
    text-transform: uppercase; padding: 3px 8px; border-radius: 3px;
    border: 1px solid currentColor;
  }
  .tag--new     { color: var(--teal); }
  .tag--revised { color: var(--blue); }
  .tag--fix     { color: var(--amber-ink); }
  .tag--base    { color: var(--ink-faint); }
  .tag--kind    { color: var(--ink-faint); border-style: dashed; }

  /* The artboard stays light in both themes — these are assets for light slides,
     and showing them on a dark ground would misrepresent how they will look. */
  .board {
    background: var(--board);
    border-bottom: 1px solid var(--board-line);
    padding: 22px;
    overflow-x: auto;
    display: flex; justify-content: center;
  }
  .board svg { max-width: 100%; height: auto; display: block; }

  .asset-foot {
    display: flex; flex-wrap: wrap; gap: 10px 24px;
    align-items: baseline; justify-content: space-between;
    padding: 16px 24px 20px;
  }
  .asset-foot p { margin: 0; max-width: 78ch; color: var(--ink-soft); font-size: 15px; }
  .path { font-family: var(--mono); font-size: 12px; color: var(--ink-faint); white-space: nowrap; }

  .closing { margin-top: 56px; padding-top: 28px; border-top: 1px solid var(--line); }
  .closing h3 { margin: 0 0 12px; font-size: 17px; }
  .closing ul { margin: 0; padding-left: 20px; display: flex; flex-direction: column; gap: 9px; }
  .closing li { color: var(--ink-soft); max-width: 82ch; }
  .closing code { font-family: var(--mono); font-size: 13px; color: var(--ink); }

  @media (max-width: 640px) {
    .wrap { padding: 0 16px 64px; }
    .masthead { padding-top: 44px; }
    .board { padding: 12px; }
  }
  @media (prefers-reduced-motion: reduce) {
    * { animation: none !important; transition: none !important; }
  }
</style>

<div class="wrap">
  <header class="masthead">
    <p class="eyebrow">Contact sheet · for review before slide build</p>
    <h1>Event Handler Design Patterns — art assets</h1>
    <p class="standfirst">Sixteen finished graphics for the Confluent Cloud event-handler playbook deck (v1.1).
      All output is vector SVG. Three of them carry corrections to the diagrams themselves, not just to the slide copy.</p>
    <dl class="facts">
      <div class="fact"><dt>Assets</dt><dd>16</dd></div>
      <div class="fact"><dt>Hand-authored</dt><dd>6</dd></div>
      <div class="fact"><dt>Mermaid</dt><dd>10</dd></div>
      <div class="fact"><dt>New</dt><dd>3</dd></div>
      <div class="fact"><dt>Corrected</dt><dd>3</dd></div>
      <div class="fact"><dt>Format</dt><dd>SVG</dd></div>
    </dl>
  </header>

  <section class="brief">
    <h3>Three corrections carried in the art</h3>
    <ol>
      <li><strong>ART-3</strong> — the old tree could route an <em>external</em> sink to Transactional EOS via
        <code>state? No → duplicate visible? Yes</code>. EOS does not cross the cluster boundary, so that branch
        recommended something that cannot work. An “Is the effect inside Kafka?” node now gates both EOS terminals.</li>
      <li><strong>ART-6</strong> — the old ladder flowed <code>retry topic → delay consumer → retry succeeded?</code>,
        implying delay consumers run business logic. They wait and re-publish. Teams copy these diagrams, so the wiring matters.</li>
      <li><strong>ART-11</strong> — compatibility checking and Data Contract rules are now two distinct gates. That is what
        makes the “syntactic, not semantic” caveat on S25 visible rather than a verbal footnote.</li>
    </ol>
    <div class="swatches">
      <div class="swatch"><span class="chip" style="background:#173A6C"></span><span>#173A6C primary</span></div>
      <div class="swatch"><span class="chip" style="background:#0074E4"></span><span>#0074E4 accent</span></div>
      <div class="swatch"><span class="chip" style="background:#00A6A0"></span><span>#00A6A0 secondary</span></div>
      <div class="swatch"><span class="chip" style="background:#F2A900"></span><span>#F2A900 error path only</span></div>
      <div class="swatch"><span class="chip" style="background:#5A6572"></span><span>#5A6572 neutral</span></div>
    </div>
  </section>

  <main class="sheet">
${cards}
  </main>

  <section class="closing">
    <h3>Before this goes into slides</h3>
    <ul>
      <li>Pin the real max message size for your cluster type and put it on <strong>S17</strong> beside ART-7. It was not
        confirmable via <code>confluent-docs</code> — the Cloud quotas page does not carry it.</li>
      <li><code>wiki/patterns/event-handler-testing-strategy.md</code> does not exist. Act 5 is the least wiki-backed part
        of the deck.</li>
      <li>Correct the topic-naming convention in the global <code>CLAUDE.md</code> canon block to match
        <code>wiki/patterns/topic-naming.md</code> — there are currently three different orderings across canon, wiki,
        and the v1.0 deck.</li>
      <li>ART-3 and ART-4 are portrait; ART-6 is wide and short. Everything else is 16:9 or close to it.</li>
    </ul>
  </section>
</div>`;

writeFileSync(join(here, 'contact-sheet.html'), html);
console.log('wrote contact-sheet.html —', (html.length / 1024).toFixed(0), 'KB');
