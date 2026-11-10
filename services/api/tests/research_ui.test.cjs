'use strict';
// Node checks for apps/web/research.js: pure helpers, force layout bounds, and the preview gate.
// No browser and no network. Run with: node services/api/tests/research_ui.test.cjs
const assert = require('node:assert/strict');
const path = require('node:path');
const {pathToFileURL} = require('node:url');

const file = path.join(__dirname, '..', '..', '..', 'apps', 'web', 'research.js');

function mulberry32(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function stubContext(overrides = {}) {
  const els = {};
  const dialog = {
    listeners: {},
    addEventListener(type, fn) { this.listeners[type] = fn; },
    close() { if (this.listeners.close) this.listeners.close(); },
  };
  els['#modal'] = dialog;
  const notices = [];
  const posts = [];
  const ctx = {
    $: sel => els[sel] ?? null,
    $$: () => [],
    notify: msg => { notices.push(msg); },
    error: err => { notices.push(`ERR:${err.message}`); },
    modal: () => { els['#preview-send'] = {}; els['#preview-cancel'] = {}; },
    post: async (url, body) => {
      posts.push({url, body});
      if (url.endsWith('/preview')) return overrides.preview;
      return {ok: true, url, body};
    },
    state: {libraryPapers: []},
    ...overrides.ctx,
  };
  return {ctx, els, posts, notices};
}

const tick = () => new Promise(resolve => setImmediate(resolve));

(async () => {
  const r = await import(pathToFileURL(file).href);

  // esc escapes all five characters.
  assert.equal(r.esc(`<a href="x">&'</a>`), '&lt;a href=&quot;x&quot;&gt;&amp;&#39;&lt;/a&gt;');
  assert.equal(r.esc(null), '');

  // matchBadge labels, and unknown values fall back to not_found.
  assert.match(r.matchBadge('exact'), /원문 일치/);
  assert.match(r.matchBadge('normalized'), /정규화 일치/);
  assert.match(r.matchBadge('not_found'), /원문 미확인/);
  assert.match(r.matchBadge('<b>weird</b>'), /원문 미확인/);
  assert.doesNotMatch(r.matchBadge('<b>weird</b>'), /<b>/);

  // refChips: [P1] becomes a chip for papers[0]; unknown numbers become a warning chip; text is escaped.
  const papers = [{id: 'p1', title: '<img src=x onerror=alert(1)>'}, {id: 'p2', title: 'Second paper'}];
  const html = r.refChips('Claim [P1], [P2] and [P9] <script>x</script>', papers);
  assert.match(html, /data-ref-paper="p1"/);
  assert.match(html, /data-ref-paper="p2"/);
  assert.match(html, /P9 · 목록 밖/);
  assert.doesNotMatch(html, /<script>/);
  assert.doesNotMatch(html, /<img/);
  assert.match(html, /&lt;script&gt;x&lt;\/script&gt;/);
  assert.equal(r.refChips(null, []), '');

  // forceLayout: 50 random nodes, random edges (including self-loops and unknown ids), all finite and inside bounds.
  const rng = mulberry32(7);
  const nodes = Array.from({length: 50}, (_, i) => ({id: `n${i}`}));
  const edges = [];
  for (let i = 0; i < 80; i++) {
    edges.push({source: `n${Math.floor(rng() * 50)}`, target: `n${Math.floor(rng() * 50)}`});
  }
  edges.push({source: 'n1', target: 'missing'}, {source: 'n2', target: 'n2'});
  const width = 1000;
  const height = 700;
  const positions = r.forceLayout(nodes, edges, {width, height});
  assert.equal(positions.length, 50);
  for (const p of positions) {
    assert.ok(Number.isFinite(p.x) && Number.isFinite(p.y), `non-finite position for ${p.id}`);
    assert.ok(p.x >= 24 && p.x <= width - 24, `x out of bounds: ${p.x}`);
    assert.ok(p.y >= 24 && p.y <= height - 24, `y out of bounds: ${p.y}`);
  }
  assert.deepEqual(r.forceLayout([], []), []);
  const single = r.forceLayout([{id: 'only'}], []);
  assert.ok(Number.isFinite(single[0].x) && Number.isFinite(single[0].y));
  // Identical seeds in identical graphs give identical results (deterministic layout).
  const again = r.forceLayout(nodes, edges, {width, height});
  assert.deepEqual(again, positions);

  // Incremental stepping settles within the iteration budget.
  const layout = r.createForceLayout(nodes, edges, {width, height});
  let guard = 0;
  while (!layout.done() && guard < 1000) { layout.step(25); guard += 1; }
  assert.ok(layout.done(), 'layout did not finish');
  assert.ok(layout.iterations() <= 300, `too many iterations: ${layout.iterations()}`);

  // sendWithPreview, local provider: no dialog, sends with the preview hash.
  {
    const {ctx, posts} = stubContext({preview: {external: false, provider: 'ollama', model: 'llama3-ko', preview_hash: 'h-local', messages: []}});
    const result = await r.sendWithPreview(ctx, '/api/x/preview', '/api/x', {content: 'hi'});
    assert.equal(result.ok, true);
    assert.deepEqual(posts.map(p => p.url), ['/api/x/preview', '/api/x']);
    assert.deepEqual(posts[1].body, {content: 'hi', preview_hash: 'h-local'});
  }

  // sendWithPreview, external provider: cancel sends nothing and returns null.
  {
    const {ctx, els, posts} = stubContext({preview: {external: true, provider: 'openai_compatible', host: 'api.example.test', preview_hash: 'h-ext', messages: [{role: 'user', content: '<b>secret text</b>'}]}});
    const pending = r.sendWithPreview(ctx, '/api/x/preview', '/api/x', {content: 'hi'});
    await tick();
    els['#preview-cancel'].onclick();
    assert.equal(await pending, null);
    assert.deepEqual(posts.map(p => p.url), ['/api/x/preview']);
  }

  // sendWithPreview, external provider: confirm sends with the hash.
  {
    const {ctx, els, posts} = stubContext({preview: {external: true, provider: 'openai_compatible', host: 'api.example.test', preview_hash: 'h-ext', messages: []}});
    const pending = r.sendWithPreview(ctx, '/api/x/preview', '/api/x', {content: 'hi'});
    await tick();
    els['#preview-send'].onclick();
    const result = await pending;
    assert.equal(result.ok, true);
    assert.deepEqual(posts[1].body, {content: 'hi', preview_hash: 'h-ext'});
  }

  // The preview dialog escapes message text (the modal HTML is captured).
  {
    let captured = '';
    const {ctx, els} = stubContext({preview: {external: true, host: 'h.example.test', preview_hash: 'x', messages: [{role: 'user', content: '<img src=x>'}]}});
    ctx.modal = html => { captured = html; els['#preview-cancel'] = {}; els['#preview-send'] = {}; };
    const pending = r.sendWithPreview(ctx, '/api/x/preview', '/api/x', {});
    await tick();
    els['#preview-cancel'].onclick();
    await pending;
    assert.match(captured, /&lt;img src=x&gt;/);
    assert.doesNotMatch(captured, /<img src=x>/);
  }

  // runProgressText (AC12): a busy run names the stage, elapsed time against the budget, and the AI call count.
  {
    const busy = r.runProgressText({busy: true, status: 'running', stage: 'search', elapsed_seconds: 83,
      max_run_seconds: 2700, llm_calls: 3, max_llm_calls: 40, config: {}});
    assert.match(busy, /진행 중/);
    assert.match(busy, /문헌 검색/);
    assert.match(busy, /1:23/);
    assert.match(busy, /예산 45분/);
    assert.match(busy, /AI 호출 3\/40/);
    // The budget may come from config when the view omits max_run_seconds (runs saved before this change).
    const fromConfig = r.runProgressText({busy: true, status: 'running', stage: 'search', elapsed_seconds: 5,
      llm_calls: 0, config: {max_run_seconds: 2700}});
    assert.match(fromConfig, /예산 45분/);
    // A run that is not busy is not shown as in progress.
    const idle = r.runProgressText({busy: false, status: 'awaiting_review', stage: null, elapsed_seconds: 83,
      max_run_seconds: 2700, llm_calls: 3, max_llm_calls: 40});
    assert.doesNotMatch(idle, /진행 중/);
    assert.match(idle, /AI 호출 3\/40/);
  }

  // CHECK_FLAG_LABELS has exactly the five documented self-check flags (AC7).
  assert.deepEqual(Object.keys(r.CHECK_FLAG_LABELS).sort(),
    ['high_prior_overlap', 'inherited_evidence', 'no_prior_found', 'prior_search_failed', 'single_source']);
  for (const label of Object.values(r.CHECK_FLAG_LABELS)) assert.equal(typeof label, 'string');

  console.log('research_ui ok');
})().catch(error => {
  console.error(error);
  process.exit(1);
});
