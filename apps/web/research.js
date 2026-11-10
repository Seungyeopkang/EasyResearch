// 연구 도우미 화면 (연구 채팅, 갭 찾기, 자동 연구, 연결 그래프, AI 설정, 논문 정리, AI 분류).
// app.js가 ctx 객체를 넘긴다: {api, post, esc, $, $$, notify, error, modal, heading, empty, state,
// names, paperTitle, openPaper, gotoPage, currentPaperId, refreshLibrary, refreshCategories,
// refreshProjects, navigate}. 이 파일은 DOM을 ctx로만 다룬다.
// 순수 함수(esc, refChips, matchBadge, createForceLayout, forceLayout)는 DOM 없이 Node 테스트에서 불러온다.
// 모든 사용자 입력과 서버 값은 esc()를 거쳐 HTML에 넣는다.

const enc = encodeURIComponent;

export function esc(value) {
  return String(value ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
}

const arr = (data, key) => (Array.isArray(data) ? data : (Array.isArray(data?.[key]) ? data[key] : []));
const short = (value, max) => { const text = String(value ?? ''); return text.length > max ? `${text.slice(0, max - 1)}…` : text; };
const fmtDate = value => {
  if (!value) return '-';
  // SQLite CURRENT_TIMESTAMP is UTC without a zone marker.
  const raw = String(value);
  const date = new Date(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/.test(raw) ? raw.replace(' ', 'T') + 'Z' : raw);
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString('ko-KR', {dateStyle: 'short', timeStyle: 'short'});
};
const titleOf = paper => paper?.title || paper?.filename || '제목 없음';
const libraryPaper = (ctx, id) => (ctx.state.libraryPapers || []).find(p => String(p.id) === String(id)) || null;
const textOf = item => (typeof item === 'string' ? item : String(item?.text ?? item?.title ?? item?.statement ?? item?.name ?? item?.description ?? item?.summary ?? ''));
const clamp = (value, low, high) => Math.min(high, Math.max(low, value));

export const FACET_LABELS = {
  problem: '문제', method: '방법', contributions: '기여', strengths: '장점', limitations: '한계',
  datasets: '데이터셋', metrics: '지표', results: '결과', future_work: '향후 과제',
};
const MATCH_LABELS = {exact: '원문 일치', normalized: '정규화 일치', not_found: '원문 미확인'};
const GAP_TYPE_LABELS = {
  unaddressed_limitation: '다뤄지지 않은 한계', common_limitation: '공통 한계', missing_dataset_or_metric: '데이터셋·지표 공백',
  method_not_applied_to_problem: '방법을 문제에 적용하지 않음', conflicting_findings: '상충하는 결과', untested_setting: '검증되지 않은 설정', other: '기타',
};
const GAP_STATUS_LABELS = {candidate: '후보', accepted: '채택', rejected: '제외'};
const REL_LABELS = {
  cites: '인용', extends: '확장', compares_against: '비교', contradicts: '상반', supports: '지지',
  same_problem: '같은 문제', same_method: '같은 방법', uses_dataset: '같은 데이터셋', related: '관련',
};
const REL_DASH = {cites: '', extends: '', compares_against: '6 3', contradicts: '2 3', supports: '', same_problem: '8 4', same_method: '4 2 1 2', uses_dataset: '10 3 2 3', related: '1 4'};
const READ_LABELS = {to_read: '읽을 예정', reading: '읽는 중', read: '읽음', on_hold: '보류'};
const READ_COLORS = {to_read: '#9aa9a2', reading: '#3a5f86', read: '#3d6b45', on_hold: '#8a6322'};
const MODE_LABELS = {idea: '아이디어 구체화', gap: '갭·근거 검토', free: '자유 대화'};
const PROVIDER_LABELS = {none: '사용 안 함', ollama: 'Ollama (이 PC)', openai_compatible: 'OpenAI 호환 서버'};
const RUN_STATUS_LABELS = {ready: '준비됨', running: '진행 중', awaiting_review: '검토 대기', budget_exhausted: '예산 소진', cancelled: '중단됨', completed: '완료', failed: '실패', failed_step: '단계 실패 · 다시 실행 가능'};
const RUN_TERMINAL = ['budget_exhausted', 'cancelled', 'completed', 'failed'];
const STAGES = [
  ['plan_queries', '검색 질의 계획'], ['search', '문헌 검색'], ['screen', '근거 선별'], ['problems', '문제 찾기'],
  ['methods', '방법 개선'], ['contributions', '기여 초안'], ['critique', '비판 검토'],
];
const ORIGIN_LABELS = {rules: '규칙', llm: 'AI', agent: '에이전트', manual: '직접 입력', openalex: 'OpenAlex', author_stated: '저자 서술', inferred: '추론'};

// Set by gaps/graph views to open a specific thread when the chat view renders.
let pendingThreadId = null;
// Gap rows from the last load, keyed by id, so actions do not refetch the list.
let gapCache = new Map();

// ---------- Pure helpers (no DOM) ----------

export function matchBadge(match) {
  const key = Object.hasOwn(MATCH_LABELS, match) ? match : 'not_found';
  return `<span class="match match-${key}" title="인용 구절을 저장된 본문과 대조한 결과">${MATCH_LABELS[key]}</span>`;
}

// Turns [P1], [P2] ... into chips. papers[0] is P1. Text is escaped before chips are inserted.
export function refChips(text, papers = []) {
  const source = String(text ?? '');
  const pattern = /\[P(\d+)\]/g;
  let html = '';
  let last = 0;
  let match;
  while ((match = pattern.exec(source))) {
    html += esc(source.slice(last, match.index));
    const number = Number(match[1]);
    const paper = number >= 1 ? papers[number - 1] : null;
    if (paper) {
      html += `<button type="button" class="ref-chip" data-ref-paper="${esc(paper.id)}" title="${esc(paper.title || '')}">P${number} · ${esc(short(paper.title || '제목 없음', 40))}</button>`;
    } else {
      html += `<span class="ref-chip unknown" title="선택한 논문 목록 밖의 인용입니다">P${number} · 목록 밖</span>`;
    }
    last = pattern.lastIndex;
  }
  return html + esc(source.slice(last));
}

// Incremental Fruchterman-Reingold style layout. Naive O(n^2) repulsion; callers keep n <= 300.
export function createForceLayout(nodes = [], edges = [], opts = {}) {
  const width = opts.width || 1000;
  const height = opts.height || 700;
  const maxIterations = opts.maxIterations || 300;
  // Wider side margin leaves room for node labels.
  const margin = 24;
  const marginX = Math.min(120, width * 0.15);
  const n = nodes.length;
  let seed = (opts.seed ?? 20251110) >>> 0;
  const rand = () => { seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0; return seed / 4294967296; };
  const points = nodes.map(() => ({x: width * (0.3 + 0.4 * rand()), y: height * (0.3 + 0.4 * rand()), dx: 0, dy: 0}));
  const index = new Map(nodes.map((node, i) => [String(node.id), i]));
  const links = [];
  for (const edge of edges) {
    const a = index.get(String(edge.source));
    const b = index.get(String(edge.target));
    if (a !== undefined && b !== undefined && a !== b) links.push([a, b]);
  }
  // Ideal edge length; capped so a handful of nodes is not flung to the corners.
  const k = n ? Math.min(0.6 * Math.sqrt((width * height) / n), Math.min(width, height) / 4) : 1;
  let iter = 0;
  let settled = false;

  function tick() {
    const temperature = Math.max(0.5, (width / 10) * (1 - iter / maxIterations));
    for (const p of points) { p.dx = 0; p.dy = 0; }
    for (let i = 0; i < n; i++) {
      for (let j = i + 1; j < n; j++) {
        let dx = points[i].x - points[j].x;
        let dy = points[i].y - points[j].y;
        let d = Math.sqrt(dx * dx + dy * dy);
        if (d < 1e-3) { dx = rand() - 0.5; dy = rand() - 0.5; d = Math.sqrt(dx * dx + dy * dy) || 1; }
        // Repulsion only within 2k (grid variant of Fruchterman-Reingold) so
        // centering gravity keeps sparse graphs compact instead of in corners.
        if (d > 2 * k) continue;
        const force = (k * k) / d;
        const ux = dx / d;
        const uy = dy / d;
        points[i].dx += ux * force; points[i].dy += uy * force;
        points[j].dx -= ux * force; points[j].dy -= uy * force;
      }
    }
    for (const [a, b] of links) {
      const dx = points[a].x - points[b].x;
      const dy = points[a].y - points[b].y;
      const d = Math.sqrt(dx * dx + dy * dy) || 1e-3;
      const force = (d * d) / k;
      const ux = dx / d;
      const uy = dy / d;
      points[a].dx -= ux * force; points[a].dy -= uy * force;
      points[b].dx += ux * force; points[b].dy += uy * force;
    }
    let maxMove = 0;
    for (const p of points) {
      p.dx += (width / 2 - p.x) * 0.06;
      p.dy += (height / 2 - p.y) * 0.06;
      const length = Math.sqrt(p.dx * p.dx + p.dy * p.dy);
      if (length > 0) {
        const scale = Math.min(length, temperature) / length;
        const mx = p.dx * scale;
        const my = p.dy * scale;
        p.x = clamp(p.x + mx, marginX, width - marginX);
        p.y = clamp(p.y + my, margin, height - margin);
        maxMove = Math.max(maxMove, Math.abs(mx) + Math.abs(my));
      }
    }
    iter += 1;
    if (iter > 20 && maxMove < 0.05) settled = true;
  }

  const done = () => settled || iter >= maxIterations;
  return {
    step(count = 1) { for (let s = 0; s < count && !done(); s++) tick(); return iter; },
    done,
    iterations: () => iter,
    positions: () => nodes.map((node, i) => ({id: node.id, x: points[i].x, y: points[i].y})),
  };
}

export function forceLayout(nodes, edges, opts) {
  const layout = createForceLayout(nodes, edges, opts);
  while (!layout.done()) layout.step(50);
  return layout.positions();
}

// ---------- Shared request and preview helpers ----------

const asBody = (data) => ({method: 'PATCH', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data)});

function externalLead(shown) {
  return `<div class="notice warning">이 내용은 <strong>${esc(shown.host || '외부 서버')}</strong>로 전송됩니다. 보내기 전에 아래 내용을 확인하세요. 무료 등급 서비스는 입력이 제품 개선에 쓰일 수 있습니다.</div>`;
}

function localLead(shown) {
  return `<div class="notice">이 PC의 모델(${esc(shown.model || shown.provider || '')})로 실행합니다. 외부로 전송되지 않습니다. 그래도 보낼 내용을 확인하세요.</div>`;
}

// Modal that shows what will be sent. Resolves true only when the user presses the confirm button.
export function confirmDialog(ctx, {title, lead = '', shown = {}, confirmText = '보내기'}) {
  return new Promise(resolve => {
    const dialog = ctx.$('#modal');
    const messages = Array.isArray(shown.messages) ? shown.messages : [];
    const roleLabel = {system: '시스템 지시', user: '사용자 입력', assistant: '이전 응답'};
    ctx.modal(`<div class="modal-head"><h2>${esc(title)}</h2><button class="close" aria-label="닫기">×</button></div>${lead}` +
      `<dl class="preview-meta"><dt>제공자</dt><dd>${esc(PROVIDER_LABELS[shown.provider] || shown.provider || '-')}</dd>` +
      `<dt>모델</dt><dd>${esc(shown.model || '지정 없음')}</dd>` +
      `<dt>호스트</dt><dd>${esc(shown.host || '-')}${shown.external ? '' : ' (이 PC)'}</dd>` +
      `<dt>글자 수</dt><dd>${esc(shown.chars ?? '-')}자</dd>` +
      `<dt>목적</dt><dd>${esc(shown.purpose || '-')}</dd></dl>` +
      `<details class="preview-details"><summary>보낼 메시지 전문 (${messages.length}개)</summary>` +
      messages.map(m => `<p class="help"><strong>${esc(roleLabel[m.role] || m.role)}</strong></p><pre class="text-output">${esc(m.content)}</pre>`).join('') +
      `</details><div class="actions"><button class="secondary" id="preview-cancel" type="button">취소</button>` +
      `<button class="primary" id="preview-send" type="button">${esc(confirmText)}</button></div>`);
    let settled = false;
    const finish = value => { if (!settled) { settled = true; resolve(value); } };
    ctx.$('#preview-send').onclick = () => { finish(true); dialog.close(); };
    ctx.$('#preview-cancel').onclick = () => { finish(false); dialog.close(); };
    dialog.addEventListener('close', () => finish(false), {once: true});
  });
}

// POSTs the preview, asks before any external transmission, then POSTs the send with the preview hash.
// Returns the send response, or null when the user cancels. Local providers run without a dialog.
export async function sendWithPreview(ctx, previewUrl, sendUrl, body = {}, opts = {}) {
  ctx.notify('미리보기를 만드는 중입니다.');
  const shown = await ctx.post(previewUrl, body);
  if (!shown || typeof shown.preview_hash !== 'string') throw new Error('미리보기 응답을 확인할 수 없습니다.');
  if (shown.external) {
    ctx.notify('');
    const ok = await confirmDialog(ctx, {title: '외부 서비스로 보내기 전 확인', lead: externalLead(shown), shown, confirmText: '보내기'});
    if (!ok) {
      ctx.notify('전송을 취소했습니다. 아무 내용도 보내지 않았습니다.');
      return null;
    }
  }
  const where = shown.external ? '외부 서비스' : `이 PC의 모델(${shown.model || shown.provider})`;
  ctx.notify(`${where}로 실행합니다. ${opts.busyText || '응답을 기다리는 중입니다. 로컬 모델은 1~2분 걸릴 수 있습니다.'}`);
  try {
    const result = await ctx.post(sendUrl, {...body, preview_hash: shown.preview_hash});
    ctx.notify('');
    return result;
  } catch (error) {
    ctx.notify('');
    throw error;
  }
}

function paperPicker(ctx, name, selected = []) {
  const papers = ctx.state.libraryPapers || [];
  if (!papers.length) return '<p class="help">서재에 논문이 없습니다. 먼저 서재에 논문을 추가하세요.</p>';
  return `<label class="sr-only" for="${name}-search">논문 검색</label>` +
    `<input type="search" id="${name}-search" class="picker-search" placeholder="제목으로 거르기" aria-label="논문 검색">` +
    `<div class="check-list picker">${papers.map(p => {
      const title = titleOf(p);
      return `<label class="check-item" data-title="${esc(title.toLowerCase())}"><input type="checkbox" name="${name}" value="${esc(p.id)}" ${selected.includes(p.id) ? 'checked' : ''}><span>${esc(title)}${p.year ? ` · ${esc(p.year)}` : ''}</span></label>`;
    }).join('')}</div>`;
}

// Filters a picker while typing. Bind once per freshly rendered form element.
function bindPickerSearch(root) {
  root.addEventListener('input', e => {
    const input = e.target.closest?.('.picker-search');
    if (!input) return;
    const query = input.value.trim().toLowerCase();
    input.parentElement.querySelectorAll('.picker [data-title]').forEach(el => { el.hidden = !!query && !el.dataset.title.includes(query); });
  });
}

const checkedValues = (root, name) => [...root.querySelectorAll(`input[name="${name}"]:checked`)].map(x => x.value);

// ---------- AI 설정 ----------

export async function showAISettings(ctx) {
  ctx.$('#content').innerHTML = ctx.heading('AI 설정', '연구 도우미가 사용할 언어 모델을 고릅니다. 기본값은 이 PC의 Ollama입니다. 무료이고, 인터넷 없이 동작하며, 논문 내용이 이 PC 밖으로 나가지 않습니다.') + '<div id="ai-body" class="stack">불러오는 중입니다.</div>';
  let cfg;
  try {
    cfg = await ctx.api('/api/ai/config');
  } catch (err) {
    ctx.$('#ai-body').innerHTML = ctx.empty('AI 설정을 불러오지 못했습니다', esc(err.message), '!');
    return;
  }
  const presets = cfg.presets || {};
  const body = ctx.$('#ai-body');
  body.innerHTML = `
  <section class="card card-pad"><h2 class="section-title">빠른 선택</h2><p class="help">버튼을 누르면 아래 입력란이 채워집니다. 저장 버튼을 눌러야 적용됩니다.</p>
    <div class="chip-row" style="margin-top:8px">${Object.entries(presets).map(([key, p]) => `<button type="button" class="secondary" data-preset="${esc(key)}">${esc(p.label || key)}</button>`).join('')}</div></section>
  <section class="card card-pad"><h2 class="section-title">현재 설정</h2>
    <p class="help">현재: ${esc(PROVIDER_LABELS[cfg.provider] || cfg.provider)} · ${cfg.external ? '외부 서버로 보냅니다. 보내기 전에 매번 확인합니다.' : '이 PC 안에서 실행합니다.'}</p>
    <form id="ai-form" class="stack" autocomplete="off">
      <div class="form-row">
        <div class="form-group"><label class="label" for="ai-provider">제공자 방식</label><select id="ai-provider">${Object.entries(PROVIDER_LABELS).map(([v, l]) => `<option value="${esc(v)}" ${cfg.provider === v ? 'selected' : ''}>${esc(l)}</option>`).join('')}</select></div>
        <div class="form-group"><label class="label" for="ai-model">모델 이름</label><input id="ai-model" value="${esc(cfg.model || '')}" maxlength="200"></div>
      </div>
      <div class="form-group"><label class="label" for="ai-base">서버 주소</label><input id="ai-base" value="${esc(cfg.base_url || '')}" maxlength="300"></div>
      <div class="form-row">
        <div class="form-group"><label class="label" for="ai-key-env">API 키 환경 변수 이름 <span class="muted">선택</span></label><input id="ai-key-env" value="${esc(cfg.api_key_env || '')}" maxlength="100" placeholder="예: GEMINI_API_KEY"></div>
        <div class="form-group"><label class="label" for="ai-key">API 키 <span class="muted">${cfg.has_api_key ? '· 저장된 키 있음' : '· 없음'}</span></label><input id="ai-key" type="password" maxlength="500" autocomplete="new-password" placeholder="${cfg.has_api_key ? '새 키를 넣을 때만 입력' : '필요한 서비스에서만 입력'}"></div>
      </div>
      <label class="check-item"><input type="checkbox" id="ai-clear-key"> 저장된 키 삭제</label>
      <div class="form-row">
        <div class="form-group"><label class="label" for="ai-max">한 번에 보낼 최대 글자 수</label><input id="ai-max" type="number" min="1000" max="200000" value="${Number(cfg.max_input_chars) || 8000}"></div>
        <div class="form-group"><label class="label" for="ai-timeout">응답 제한 시간(초)</label><input id="ai-timeout" type="number" min="5" max="900" value="${Number(cfg.timeout) || 120}"></div>
      </div>
      <div class="actions"><button class="primary" type="submit">설정 저장</button></div>
    </form></section>
  <section class="card card-pad"><h2 class="section-title">연결 확인</h2><p class="help">짧은 테스트 문장을 보냅니다. 외부 서버라면 보내기 전에 내용을 확인합니다.</p>
    <div class="actions start"><button class="secondary" id="ai-test" type="button" ${cfg.enabled ? '' : 'disabled'}>연결 확인</button></div>
    <div id="ai-test-result" class="text-output" aria-live="polite"></div></section>
  <section class="card card-pad"><h2 class="section-title">선택 안내</h2>
    <ul class="help">
      <li><strong>Ollama (이 PC)</strong>: 무료입니다. 인터넷이 필요 없고 논문 내용이 이 PC 밖으로 나가지 않습니다. 기본값입니다.</li>
      <li><strong>LM Studio (이 PC)</strong>: 무료입니다. 이 PC에서 실행하는 OpenAI 호환 서버를 씁니다.</li>
      <li><strong>Google Gemini 무료 등급</strong>: 무료로 쓸 수 있지만 인터넷으로 전송합니다. 무료 등급의 입력은 Google 제품 개선에 쓰일 수 있으므로 민감한 연구 자료에는 쓰지 마세요.</li>
      <li><strong>Groq 등 외부 무료 등급</strong>: 인터넷으로 전송됩니다. 각 서비스의 데이터 사용 정책을 확인하세요.</li>
      <li>API 키는 환경 변수나 이 PC의 비공개 파일에 두며, 이 화면·데이터베이스·백업·로그에 저장되지 않습니다.</li>
    </ul></section>`;
  body.addEventListener('click', e => {
    const button = e.target.closest('[data-preset]');
    if (!button) return;
    const p = presets[button.dataset.preset] || {};
    ctx.$('#ai-provider').value = p.provider || 'none';
    ctx.$('#ai-base').value = p.base_url || '';
    ctx.$('#ai-model').value = p.model || '';
    ctx.$('#ai-key-env').value = p.api_key_env || '';
    ctx.$('#ai-max').value = p.max_input_chars || 8000;
    ctx.notify('선택한 설정을 입력란에 채웠습니다. 저장해야 적용됩니다.');
  });
  ctx.$('#ai-form').onsubmit = async e => {
    e.preventDefault();
    const button = e.target.querySelector('button[type=submit]');
    button.disabled = true;
    const payload = {
      provider: ctx.$('#ai-provider').value,
      base_url: ctx.$('#ai-base').value.trim(),
      model: ctx.$('#ai-model').value.trim(),
      api_key_env: ctx.$('#ai-key-env').value.trim(),
      max_input_chars: Number(ctx.$('#ai-max').value),
      timeout: Number(ctx.$('#ai-timeout').value),
      api_key: ctx.$('#ai-key').value || null,
      clear_api_key: ctx.$('#ai-clear-key').checked,
    };
    try {
      await ctx.api('/api/ai/config', {method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)});
      await showAISettings(ctx);
      ctx.notify('AI 설정을 저장했습니다.');
    } catch (err) {
      ctx.error(err);
      button.disabled = false;
    }
  };
  const testButton = ctx.$('#ai-test');
  if (testButton) testButton.onclick = async () => {
    const output = ctx.$('#ai-test-result');
    testButton.disabled = true;
    output.textContent = '';
    try {
      const result = await sendWithPreview(ctx, '/api/ai/test/preview', '/api/ai/test', {}, {busyText: '연결을 확인하는 중입니다. 로컬 모델은 첫 응답에 시간이 걸릴 수 있습니다.'});
      output.textContent = result ? `연결 성공 · ${result.provider} · ${result.model}\n응답: ${result.reply}` : '연결 확인을 취소했습니다.';
    } catch (err) {
      ctx.error(err);
    } finally {
      testButton.disabled = false;
    }
  };
}

// ---------- 연구 채팅 ----------

export async function showChat(ctx) {
  await ctx.refreshLibrary().catch(() => {});
  ctx.$('#content').innerHTML = ctx.heading('연구 채팅', '아이디어를 구체화하거나 갭의 근거를 따져 봅니다. 답변의 [P1] 표시는 대화에 고른 논문 번호입니다. 답변은 초안이므로 원문과 대조하세요.',
    '<div class="toolbar"><button class="primary" id="chat-new" type="button">＋ 새 대화</button></div>') +
    '<div class="chat-layout"><aside class="card card-pad chat-list" aria-label="대화 목록"><div id="thread-list" class="stack-list">불러오는 중입니다.</div></aside>' +
    '<section id="chat-main" class="card card-pad chat-main"></section></div>';
  ctx.$('#chat-new').onclick = () => showNewThread(ctx);
  await loadThreadList(ctx);
  const requested = pendingThreadId;
  pendingThreadId = null;
  if (requested) await openThread(ctx, requested);
  else showNewThread(ctx);
}

async function loadThreadList(ctx) {
  const target = ctx.$('#thread-list');
  if (!target) return;
  const query = ctx.state.projectId ? `?project_id=${enc(ctx.state.projectId)}` : '';
  try {
    const threads = arr(await ctx.api(`/api/chat/threads${query}`), 'threads');
    target.innerHTML = threads.length
      ? threads.map(t => `<button type="button" class="thread-item" data-thread="${esc(t.id)}"><strong>${esc(t.title || '제목 없는 대화')}</strong><span class="section-caption">${esc(MODE_LABELS[t.mode] || t.mode || '')} · ${esc(fmtDate(t.updated_at || t.created_at))}</span></button>`).join('')
      : '<p class="help">아직 대화가 없습니다.</p>';
    target.onclick = e => {
      const button = e.target.closest('[data-thread]');
      if (button) openThread(ctx, button.dataset.thread).catch(err => ctx.error(err));
    };
  } catch (err) {
    target.innerHTML = `<p class="help">대화 목록을 불러오지 못했습니다: ${esc(err.message)}</p>`;
  }
}

async function showNewThread(ctx) {
  const main = ctx.$('#chat-main');
  if (!main) return;
  const hasProject = !!ctx.state.projectId;
  const projectName = (ctx.state.projects || []).find(p => p.id === ctx.state.projectId)?.name || '';
  main.innerHTML = `<h2 class="section-title">새 대화</h2>
    <form id="thread-form" class="stack">
      <div class="form-row">
        <div class="form-group"><label class="label" for="thread-title">제목 <span class="muted">선택</span></label><input id="thread-title" maxlength="200"></div>
        <div class="form-group"><label class="label" for="thread-mode">대화 방식</label><select id="thread-mode">${Object.entries(MODE_LABELS).map(([v, l]) => `<option value="${v}">${esc(l)}</option>`).join('')}</select></div>
      </div>
      <label class="check-item"><input type="checkbox" id="thread-project" ${hasProject ? 'checked' : 'disabled'}> ${hasProject ? `현재 프로젝트「${esc(projectName)}」에 묶기` : '프로젝트를 선택하면 묶을 수 있습니다'}</label>
      <div><p class="label">대화에 쓸 논문 <span class="muted">고른 순서대로 [P1], [P2]가 됩니다</span></p>${paperPicker(ctx, 'thread-paper')}</div>
      <div class="actions"><button class="primary" type="submit">대화 시작</button></div>
    </form>`;
  bindPickerSearch(main);
  ctx.$('#thread-form').onsubmit = async e => {
    e.preventDefault();
    const button = e.target.querySelector('button[type=submit]');
    button.disabled = true;
    try {
      const paperIds = checkedValues(e.target, 'thread-paper');
      const created = await ctx.post('/api/chat/threads', {
        title: ctx.$('#thread-title').value.trim() || null,
        mode: ctx.$('#thread-mode').value,
        project_id: ctx.$('#thread-project').checked && hasProject ? ctx.state.projectId : null,
        paper_ids: paperIds,
        gap_ids: [],
      });
      await loadThreadList(ctx);
      await openThread(ctx, created.id);
    } catch (err) {
      ctx.error(err);
      button.disabled = false;
    }
  };
}

async function openThread(ctx, id) {
  const main = ctx.$('#chat-main');
  if (!main) return;
  main.innerHTML = '<p class="help">대화를 불러오는 중입니다.</p>';
  let data;
  try {
    data = await ctx.api(`/api/chat/threads/${enc(id)}`);
    await ctx.refreshLibrary().catch(() => {});
  } catch (err) {
    main.innerHTML = ctx.empty('대화를 불러오지 못했습니다', esc(err.message), '!');
    return;
  }
  const thread = data.thread ?? data;
  const messages = arr(data.messages ?? thread.messages, 'messages');
  const papers = arr(thread.paper_ids).map(pid => {
    const paper = libraryPaper(ctx, pid);
    return {id: pid, title: paper ? titleOf(paper) : '삭제되었거나 찾을 수 없는 논문'};
  });
  const projectId = thread.project_id || ctx.state.projectId || '';
  const messageHtml = m => {
    const isUser = m.role === 'user';
    const unknown = arr(m.meta?.unknown_refs);
    const unknownNote = unknown.length ? `<p class="help">목록 밖 인용: ${esc(unknown.map(x => `P${String(x).replace(/^P/i, '')}`).join(', '))} · 대화에 고르지 않은 논문 번호입니다.</p>` : '';
    const ideaButton = !isUser ? `<div class="actions start"><button type="button" class="ghost" data-to-idea="${esc(m.id)}">아이디어로 저장</button></div>` : '';
    return `<div class="bubble ${isUser ? 'user' : 'assistant'}"><span class="bubble-role">${isUser ? '나' : '도우미 · 초안'}</span><div class="bubble-text">${refChips(m.content, papers)}</div>${unknownNote}${ideaButton}</div>`;
  };
  main.innerHTML = `<div class="thread-head"><div><h2 class="section-title">${esc(thread.title || '제목 없는 대화')}</h2>` +
    `<p class="help">${esc(MODE_LABELS[thread.mode] || thread.mode || '')} · 논문 ${papers.length}편${thread.project_id ? ' · 프로젝트에 묶임' : ''}</p></div>` +
    `<button type="button" class="ghost" id="thread-delete">대화 삭제</button></div>` +
    (papers.length ? `<details class="paper-ref-list"><summary class="help">대화에 쓰는 논문 [P1]..[P${papers.length}]</summary><ol class="help">${papers.map(p => `<li><button type="button" class="paper-title" data-open-paper="${esc(p.id)}">${esc(p.title)}</button></li>`).join('')}</ol></details>` : '') +
    `<div id="messages" class="messages" aria-live="polite">${messages.length ? messages.map(messageHtml).join('') : '<p class="help">아직 메시지가 없습니다. 아래에 질문을 입력하세요.</p>'}</div>` +
    `<form id="composer" class="composer"><label class="sr-only" for="composer-text">메시지</label><textarea id="composer-text" rows="3" maxlength="4000" placeholder="예: 이 논문들의 공통 한계를 바탕으로 연구 질문을 구체화해 줘"></textarea><div class="actions"><button class="primary" type="submit">질문 보내기</button></div></form>`;
  const messagesEl = ctx.$('#messages');
  if (messagesEl) messagesEl.scrollTop = messagesEl.scrollHeight;
  main.onclick = async e => {
    const refButton = e.target.closest('[data-ref-paper], [data-open-paper]');
    if (refButton) {
      ctx.openPaper(refButton.dataset.refPaper || refButton.dataset.openPaper).catch(err => ctx.error(err));
      return;
    }
    const ideaButton = e.target.closest('[data-to-idea]');
    if (ideaButton) {
      if (!projectId) { ctx.notify('아이디어로 저장하려면 프로젝트를 선택하세요.', 'error'); return; }
      const title = window.prompt('아이디어 제목을 입력하세요.', '');
      if (!title || !title.trim()) return;
      try {
        await ctx.post(`/api/chat/messages/${enc(ideaButton.dataset.toIdea)}/to-idea`, {project_id: projectId, title: title.trim()});
        ctx.notify('아이디어로 저장했습니다. 아이디어 화면에서 확인하세요.');
      } catch (err) { ctx.error(err); }
      return;
    }
    if (e.target.closest('#thread-delete')) {
      if (!window.confirm('이 대화를 삭제할까요? 대화 기록은 복구할 수 없습니다. 고른 논문과 프로젝트는 그대로 남습니다.')) return;
      try {
        await ctx.api(`/api/chat/threads/${enc(id)}`, {method: 'DELETE'});
        await loadThreadList(ctx);
        showNewThread(ctx);
        ctx.notify('대화를 삭제했습니다.');
      } catch (err) { ctx.error(err); }
    }
  };
  ctx.$('#composer').onsubmit = async e => {
    e.preventDefault();
    const text = ctx.$('#composer-text').value.trim();
    if (!text) return;
    const button = e.target.querySelector('button[type=submit]');
    button.disabled = true;
    try {
      const reply = await sendWithPreview(ctx, `/api/chat/threads/${enc(id)}/preview`, `/api/chat/threads/${enc(id)}/messages`, {content: text}, {busyText: '답변을 만드는 중입니다. 로컬 모델은 1~2분 걸릴 수 있습니다.'});
      if (reply) {
        await openThread(ctx, id);
        ctx.notify('답변을 저장했습니다. 초안이므로 원문과 대조하세요.');
      }
    } catch (err) {
      ctx.error(err);
    } finally {
      button.disabled = false;
    }
  };
}

// ---------- 갭 찾기 ----------

export async function showGaps(ctx) {
  await ctx.refreshLibrary().catch(() => {});
  ctx.$('#content').innerHTML = ctx.heading('갭 찾기', '선택한 논문에서 연구 공백 후보를 찾습니다. 규칙 방식은 한계 문장과 데이터셋·지표 공백을 찾고, AI 방식은 근거 구절을 붙여 제안합니다. 결과는 후보이며 채택하거나 제외해야 합니다.') +
    `<section class="card card-pad"><form id="gap-form" class="stack">
      <div><h2 class="section-title">논문 고르기 <span class="muted">1~20편</span></h2>${paperPicker(ctx, 'gap-paper')}</div>
      <div class="form-group"><label class="label" for="gap-focus">AI에 줄 관심 주제 <span class="muted">선택</span></label><input id="gap-focus" maxlength="300" placeholder="예: 소량 데이터 환경의 일반화"></div>
      <div class="toolbar"><button type="button" class="secondary" id="gap-rules">규칙으로 찾기</button><button type="button" class="primary" id="gap-ai">AI로 찾기</button></div>
    </form></section>
    <section class="card card-pad" style="margin-top:16px"><div class="toolbar"><h2 class="section-title" style="margin:0">찾은 갭</h2></div><div id="gap-list">불러오는 중입니다.</div></section>
    <details class="card card-pad" style="margin-top:16px"><summary class="section-title">갭 직접 추가</summary>
      <form id="gap-manual" class="stack" style="margin-top:12px">
        <div class="form-group"><label class="label" for="gap-m-title">제목</label><input id="gap-m-title" required maxlength="300"></div>
        <div class="form-group"><label class="label" for="gap-m-desc">설명</label><textarea id="gap-m-desc" maxlength="2000"></textarea></div>
        <div class="form-group"><label class="label" for="gap-m-type">유형</label><select id="gap-m-type">${Object.entries(GAP_TYPE_LABELS).map(([v, l]) => `<option value="${v}">${esc(l)}</option>`).join('')}</select></div>
        <p class="help">위에서 고른 논문이 함께 연결됩니다. 직접 추가한 갭은 후보로 저장됩니다.</p>
        <div class="actions"><button class="secondary" type="submit">갭 추가</button></div>
      </form></details>`;
  const form = ctx.$('#gap-form');
  bindPickerSearch(form);
  const selectedPapers = () => checkedValues(form, 'gap-paper');
  const selectionValid = () => {
    const ids = selectedPapers();
    if (ids.length < 1 || ids.length > 20) { ctx.notify('논문을 1편 이상 20편 이하로 고르세요.', 'error'); return null; }
    return ids;
  };
  const projectId = ctx.state.projectId || null;
  ctx.$('#gap-rules').onclick = async () => {
    const ids = selectionValid();
    if (!ids) return;
    try {
      const result = await ctx.post('/api/gaps/rules', {paper_ids: ids, project_id: projectId});
      ctx.notify(`규칙으로 갭 후보 ${arr(result, 'gaps').length || 0}개를 만들었습니다. 근거 구절을 확인하세요.`);
      await loadGaps(ctx);
    } catch (err) { ctx.error(err); }
  };
  ctx.$('#gap-ai').onclick = async () => {
    const ids = selectionValid();
    if (!ids) return;
    try {
      const result = await sendWithPreview(ctx, '/api/gaps/ai/preview', '/api/gaps/ai',
        {paper_ids: ids, project_id: projectId, focus: ctx.$('#gap-focus').value.trim() || null},
        {busyText: 'AI가 갭을 찾는 중입니다. 로컬 모델은 1~2분 걸릴 수 있습니다.'});
      if (result) {
        ctx.notify(`AI가 갭 후보 ${arr(result, 'gaps').length || 0}개를 만들었습니다. 근거를 확인하고 채택하세요.`);
        await loadGaps(ctx);
      }
    } catch (err) { ctx.error(err); }
  };
  ctx.$('#gap-manual').onsubmit = async e => {
    e.preventDefault();
    const button = e.target.querySelector('button[type=submit]');
    button.disabled = true;
    try {
      await ctx.post('/api/gaps', {
        paper_ids: selectedPapers(),
        title: ctx.$('#gap-m-title').value.trim(),
        description: ctx.$('#gap-m-desc').value.trim(),
        gap_type: ctx.$('#gap-m-type').value,
        project_id: projectId,
        origin: 'manual',
      });
      ctx.notify('갭을 추가했습니다.');
      await loadGaps(ctx);
      e.target.reset();
    } catch (err) { ctx.error(err); } finally { button.disabled = false; }
  };
  ctx.$('#gap-list').onclick = e => gapAction(ctx, e);
  await loadGaps(ctx);
}

async function loadGaps(ctx) {
  const target = ctx.$('#gap-list');
  if (!target) return;
  const query = ctx.state.projectId ? `?project_id=${enc(ctx.state.projectId)}` : '';
  let gaps;
  try {
    gaps = arr(await ctx.api(`/api/gaps${query}`), 'gaps');
  } catch (err) {
    target.innerHTML = ctx.empty('갭을 불러오지 못했습니다', esc(err.message), '!');
    return;
  }
  gapCache = new Map(gaps.map(g => [String(g.id), g]));
  if (!gaps.length) {
    target.innerHTML = ctx.empty('찾은 갭이 없습니다', '위에서 논문을 고르고 규칙 또는 AI로 찾아 보세요.', '◇');
    return;
  }
  target.innerHTML = Object.entries(GAP_STATUS_LABELS).map(([status, label]) => {
    const items = gaps.filter(g => g.status === status);
    return items.length ? `<h3 class="group-title">${esc(label)} · ${items.length}</h3>${items.map(g => gapCard(ctx, g)).join('')}` : '';
  }).join('');
}

function gapCard(ctx, g) {
  const evidence = arr(g.evidence);
  const evidenceHtml = evidence.length ? evidence.map(ev => {
    const page = Number.isInteger(ev.page) && ev.page >= 1 ? ev.page : null;
    return `<div class="evidence"><button type="button" data-open-paper="${esc(ev.paper_id)}"${page ? ` data-page="${page}"` : ''}>${esc(titleOf(libraryPaper(ctx, ev.paper_id)))}${page ? ` · ${page}쪽` : ''} ↗</button> ${matchBadge(ev.match)}${ev.facet ? ` <span class="section-caption">· ${esc(FACET_LABELS[ev.facet] || ev.facet)}</span>` : ''}${ev.quote ? `<blockquote>${esc(ev.quote)}</blockquote>` : ''}</div>`;
  }).join('') : '<p class="help">근거 구절이 없습니다.</p>';
  const buttons = [
    g.status !== 'accepted' ? `<button type="button" class="secondary" data-gap-status="accepted" data-gap-id="${esc(g.id)}">채택</button>` : '',
    g.status !== 'rejected' ? `<button type="button" class="ghost" data-gap-status="rejected" data-gap-id="${esc(g.id)}">제외</button>` : '',
    g.status !== 'rejected' ? `<button type="button" class="secondary" data-gap-idea="${esc(g.id)}">아이디어로</button>` : '',
    g.status !== 'rejected' ? `<button type="button" class="secondary" data-gap-chat="${esc(g.id)}">채팅으로 논의</button>` : '',
  ].join('');
  return `<article class="result gap-card"><div class="result-top"><div><span class="pill">${esc(GAP_TYPE_LABELS[g.gap_type] || '기타')}</span> <span class="pill">${esc(GAP_STATUS_LABELS[g.status] || g.status || '')}</span><h3>${esc(g.title)}</h3><p>${esc(g.description || '')}</p></div><div class="result-actions">${buttons}</div></div>${evidenceHtml}</article>`;
}

async function gapAction(ctx, e) {
  const openButton = e.target.closest('[data-open-paper]');
  if (openButton) {
    const page = openButton.dataset.page ? Number(openButton.dataset.page) : null;
    ctx.openPaper(openButton.dataset.openPaper, page).catch(err => ctx.error(err));
    return;
  }
  const statusButton = e.target.closest('[data-gap-status]');
  if (statusButton) {
    try {
      await ctx.api(`/api/gaps/${enc(statusButton.dataset.gapId)}`, asBody({status: statusButton.dataset.gapStatus}));
      await loadGaps(ctx);
    } catch (err) { ctx.error(err); }
    return;
  }
  const ideaButton = e.target.closest('[data-gap-idea]');
  if (ideaButton) {
    if (!ctx.state.projectId) { ctx.notify('아이디어로 저장하려면 프로젝트를 선택하세요.', 'error'); return; }
    try {
      await ctx.post(`/api/gaps/${enc(ideaButton.dataset.gapIdea)}/to-idea`, {project_id: ctx.state.projectId});
      ctx.notify('아이디어로 저장했습니다. 아이디어 화면에서 확인하세요.');
    } catch (err) { ctx.error(err); }
    return;
  }
  const chatButton = e.target.closest('[data-gap-chat]');
  if (chatButton) {
    const id = chatButton.dataset.gapChat;
    const gap = gapCache.get(String(id));
    const papers = new Set([...arr(gap?.paper_ids), ...arr(gap?.evidence).map(x => x.paper_id)].filter(Boolean));
    try {
      const thread = await ctx.post('/api/chat/threads', {
        title: short(`갭: ${gap?.title || id}`, 190),
        mode: 'gap',
        project_id: gap?.project_id || ctx.state.projectId || null,
        paper_ids: [...papers],
        gap_ids: [id],
      });
      pendingThreadId = thread.id;
      ctx.navigate('research-chat');
    } catch (err) { ctx.error(err); }
  }
}

// ---------- 자동 연구 ----------

export async function showResearchLoop(ctx) {
  await ctx.refreshLibrary().catch(() => {});
  ctx.$('#content').innerHTML = ctx.heading('자동 연구', '주제를 주면 문헌을 검색하고, 근거 카드를 만들고, 문제·방법·기여 초안을 단계별로 만듭니다. 각 반복이 끝나면 멈추고 사람이 검토합니다. 참신성은 판정하지 않습니다.') +
    '<div class="notice warning">자동 연구는 모델을 여러 번 호출하고 OpenAlex에서 제목·초록을 검색합니다. 시작 전에 보낼 내용을 확인합니다.</div>' +
    `<section class="card card-pad" style="margin-top:16px"><h2 class="section-title">새 연구 실행</h2>
      <form id="run-form" class="stack">
        <div class="form-group"><label class="label" for="run-topic">연구 주제</label><textarea id="run-topic" maxlength="500" required placeholder="예: 소량 데이터에서 시계열 이상 탐지"></textarea></div>
        <details><summary class="help">시드 논문 고르기 <span class="muted">선택</span></summary><div style="margin-top:8px">${paperPicker(ctx, 'run-seed')}</div></details>
        <div class="form-row">
          <div class="form-group"><label class="label" for="run-iter">반복 횟수</label><select id="run-iter"><option value="1">1회</option><option value="2">2회</option><option value="3">3회</option></select></div>
          <div class="form-group"><label class="label" for="run-per">반복당 논문 수 (3~10)</label><input id="run-per" type="number" min="3" max="10" value="5"></div>
        </div>
        <div class="actions"><button class="primary" type="submit">보낼 내용 확인 후 시작</button></div>
      </form></section>
    <section class="card card-pad" style="margin-top:16px"><h2 class="section-title">실행 목록</h2><div id="run-list">불러오는 중입니다.</div></section>
    <section id="run-detail" style="margin-top:16px"></section>`;
  bindPickerSearch(ctx.$('#run-form'));
  ctx.$('#run-form').onsubmit = e => {
    e.preventDefault();
    const button = e.target.querySelector('button[type=submit]');
    button.disabled = true;
    startRun(ctx, e.target).catch(err => ctx.error(err)).finally(() => { button.disabled = false; });
  };
  ctx.$('#run-list').onclick = e => {
    const button = e.target.closest('[data-run-open]');
    if (button) showRunDetail(ctx, button.dataset.runOpen).catch(err => ctx.error(err));
  };
  ctx.$('#run-detail').onclick = e => runAction(ctx, e).catch(err => ctx.error(err));
  await loadRuns(ctx);
}

async function startRun(ctx, form) {
  const topic = form.querySelector('#run-topic').value.trim();
  const perIteration = Number(form.querySelector('#run-per').value);
  const iterations = Number(form.querySelector('#run-iter').value);
  if (!topic) { ctx.notify('연구 주제를 입력하세요.', 'error'); return; }
  if (!Number.isInteger(perIteration) || perIteration < 3 || perIteration > 10) { ctx.notify('반복당 논문 수는 3~10 사이여야 합니다.', 'error'); return; }
  const body = {
    topic,
    project_id: ctx.state.projectId || null,
    seed_paper_ids: checkedValues(form, 'run-seed'),
    max_iterations: iterations,
    papers_per_iteration: perIteration,
  };
  ctx.notify('미리보기를 만드는 중입니다.');
  const preview = await ctx.post('/api/research-runs/preview', body);
  ctx.notify('');
  const shown = preview.first_prompt || preview;
  const ok = await confirmDialog(ctx, {
    title: '자동 연구 시작 확인',
    lead: (shown.external ? externalLead(shown) : localLead(shown)) + `<p class="help">데이터 정책</p><p class="text-output">${esc(preview.policy || '')}</p>`,
    shown,
    confirmText: '시작',
  });
  if (!ok) {
    ctx.notify('시작을 취소했습니다. 아무 내용도 보내지 않았습니다.');
    return;
  }
  const run = await ctx.post('/api/research-runs', {...body, preview_hash: preview.preview_hash});
  ctx.notify('연구 실행을 만들었습니다. 단계를 실행하세요.');
  await loadRuns(ctx);
  await showRunDetail(ctx, run.id);
}

async function loadRuns(ctx) {
  const target = ctx.$('#run-list');
  if (!target) return;
  try {
    const runs = arr(await ctx.api('/api/research-runs'), 'runs');
    target.innerHTML = runs.length
      ? runs.map(r => `<div class="evidence run-row"><span class="pill">${esc(RUN_STATUS_LABELS[r.status] || r.status || '')}</span> <strong>${esc(short(r.topic, 120))}</strong> <span class="section-caption">${esc(fmtDate(r.created_at))}</span> <button type="button" class="ghost" data-run-open="${esc(r.id)}">열기</button></div>`).join('')
      : '<p class="help">아직 실행이 없습니다.</p>';
  } catch (err) {
    target.innerHTML = `<p class="help">실행 목록을 불러오지 못했습니다: ${esc(err.message)}</p>`;
  }
}

async function showRunDetail(ctx, id) {
  const target = ctx.$('#run-detail');
  if (!target) return;
  target.innerHTML = '<p class="help">실행 정보를 불러오는 중입니다.</p>';
  const data = await ctx.api(`/api/research-runs/${enc(id)}`);
  target.dataset.runId = id;
  target.innerHTML = runDetailHtml(ctx, data);
}

const textList = list => arr(list).map(item => `<li>${esc(textOf(item))}</li>`).join('');

function runDetailHtml(ctx, data) {
  const run = data.run ?? data;
  const steps = arr(data.steps ?? run.steps, 'steps');
  const state = data.state ?? run.state ?? {};
  const status = run.status || '';
  const terminal = RUN_TERMINAL.includes(status);
  const reviewing = status === 'awaiting_review';
  const problems = arr(state.problems);
  const methods = arr(state.methods);
  const contributions = arr(state.contributions);
  const evidence = arr(state.evidence);
  const candidates = arr(state.candidates);
  const critique = state.critique || {};
  const evidenceById = new Map(evidence.map(e => [String(e.key ?? e.id), e]));
  const scores = critique.scores && typeof critique.scores === 'object' ? Object.entries(critique.scores) : [];
  const lastByStage = new Map();
  const iteration = run.iteration ?? state.iteration;
  for (const s of steps) if (iteration === undefined || s.iteration === iteration) lastByStage.set(s.stage, s);
  const stepper = STAGES.map(([key, label]) => {
    const last = lastByStage.get(key);
    const cls = !last ? 'pending' : last.status === 'failed' ? 'failed' : last.status === 'running' ? 'running' : 'done';
    return `<li class="step ${cls}"><span class="step-dot" aria-hidden="true"></span>${esc(label)}</li>`;
  }).join('');
  const controls = `<div class="toolbar">
      <button type="button" class="secondary" data-run-step ${terminal || reviewing ? 'disabled' : ''}>다음 단계</button>
      <button type="button" class="secondary" data-run-advance ${terminal || reviewing ? 'disabled' : ''}>검토 지점까지 실행</button>
      <button type="button" class="danger" data-run-cancel ${terminal ? 'disabled' : ''}>중단</button></div>`;
  const review = reviewing ? `<div class="notice warning"><strong>검토 지점입니다.</strong> 점수와 약점을 보고 방향을 정하세요. 점수는 모델의 자체 평가이며 참신성을 판정하지 않습니다.</div>
      <div class="info-block"><h3>비판 점수</h3>${scores.length ? `<ul>${scores.map(([k, v]) => `<li>${esc(k)}: ${esc(v)}</li>`).join('')}</ul>` : '<p class="help">점수가 없습니다.</p>'}
      <h3>약점</h3>${arr(critique.weaknesses).length ? `<ul>${textList(critique.weaknesses)}</ul>` : '<p class="help">기록된 약점이 없습니다.</p>'}</div>
      <div class="form-group"><label class="label" for="run-feedback">검토 메모 <span class="muted">선택</span></label><textarea id="run-feedback" maxlength="2000"></textarea></div>
      <div class="form-group"><label class="label" for="run-focus">집중할 문제</label><select id="run-focus"><option value="">지정 안 함</option>${problems.map((p, i) => `<option value="${i}">#${i + 1} ${esc(short(textOf(p), 60))}</option>`).join('')}</select></div>
      <div class="actions"><button type="button" class="primary" data-run-feedback>다음 반복으로 진행</button></div>` : '';
  const evidenceHtml = evidence.length ? evidence.map(e => `<div class="evidence"><strong>${esc(e.key ?? e.id)}</strong> · ${esc(e.title || '제목 없음')}${e.year ? ` · ${esc(e.year)}` : ''}${e.quote ? `<blockquote>${esc(e.quote)}</blockquote>` : ''}</div>`).join('') : '<p class="help">근거 카드가 없습니다.</p>';
  const problemsHtml = problems.length ? problems.map((p, i) => {
    const chips = arr(p.evidence).map(id => {
      const ev = evidenceById.get(String(id));
      return `<span class="chip evidence-chip" tabindex="0" title="${esc(ev?.quote || '연결된 근거 구절이 없습니다')}">${esc(id)}</span>`;
    }).join(' ') || '<span class="section-caption">근거 없음</span>';
    return `<div class="result"><span class="pill">#${i + 1}</span> ${p.type ? `<span class="pill">${esc(p.type)}</span>` : ''}<p><strong>${esc(textOf(p))}</strong></p>${p.why_open ? `<p>${esc(p.why_open)}</p>` : ''}<div class="chip-row">${chips}</div></div>`;
  }).join('') : '<p class="help">문제 후보가 없습니다.</p>';
  const methodsHtml = methods.length ? `<ul>${methods.map(m => { const pi = m.problem_index ?? m.problem; return `<li>${pi !== undefined && pi !== null ? `<span class="pill">문제 #${esc(Number(pi) + 1)}</span> ` : ''}<strong>${esc(textOf(m))}</strong>${m.idea && m.idea !== textOf(m) ? `<p>${esc(m.idea)}</p>` : ''}${m.expected_gain ? `<p class="help">기대 효과: ${esc(m.expected_gain)}</p>` : ''}${m.risks ? `<p class="help">위험: ${esc(m.risks)}</p>` : ''}</li>`; }).join('')}</ul>` : '<p class="help">방법 제안이 없습니다.</p>';
  const contributionsHtml = contributions.length ? contributions.map((c, i) => {
    const nearest = arr(c.closest_prior ?? c.nearest ?? c.nearest_prior ?? c.prior_work);
    return `<div class="result"><p><span class="pill">#${i + 1}</span> <strong>${esc(textOf(c))}</strong></p>
      <p class="help">가장 가까운 선행 연구 (검색 결과일 뿐입니다. 참신성은 판정하지 않습니다.)</p>
      ${nearest.length ? `<ul>${nearest.map(n => `<li>${esc(n.title || '제목 없음')}${n.year ? ` · ${esc(n.year)}` : ''}${/^https?:\/\//.test(String(n.url || '')) ? ` · <a href="${esc(n.url)}" target="_blank" rel="noopener noreferrer">원문</a>` : ''}</li>`).join('')}</ul>` : '<p class="help">가까운 선행 연구를 찾지 못했습니다.</p>'}</div>`;
  }).join('') : '<p class="help">기여 초안이 없습니다.</p>';
  const saveCandidates = (problems.length || contributions.length) ? `<section class="card card-pad"><h2 class="section-title">프로젝트에 저장</h2>
      ${ctx.state.projectId ? '' : '<p class="notice warning">저장하려면 프로젝트를 선택하세요.</p>'}
      <div class="check-list">${problems.map((p, i) => `<label class="check-item"><input type="checkbox" name="run-save-problem" value="${i}"><span>문제 #${i + 1}: ${esc(short(textOf(p), 120))}</span></label>`).join('')}
      ${contributions.map((c, i) => `<label class="check-item"><input type="checkbox" name="run-save-contribution" value="${i}"><span>기여 #${i + 1}: ${esc(short(textOf(c), 120))}</span></label>`).join('')}</div>
      <div class="actions"><button type="button" class="primary" data-run-save ${ctx.state.projectId ? '' : 'disabled'}>선택 항목 저장</button></div>
      <p class="help">저장하면 아이디어와 갭 후보로 기록됩니다. 확정 전까지 초안입니다.</p></section>` : '';
  const stepRows = steps.length ? steps.map(s => `<tr><td>${esc((STAGES.find(([k]) => k === s.stage) || [s.stage, s.stage])[1])}</td><td>${esc(s.status || '')}</td><td>${esc(s.model || '-')}</td><td>${esc(s.error || '')}</td></tr>`).join('') : '<tr><td colspan="4">기록이 없습니다.</td></tr>';
  return `<section class="card card-pad" data-run-status="${esc(status)}">
      <div class="thread-head"><div><h2 class="section-title">${esc(short(run.topic, 200))}</h2>
      <p class="help"><span class="pill">${esc(RUN_STATUS_LABELS[status] || status)}</span> · 반복 ${esc(run.iteration ?? state.iteration ?? '-')}/${esc(run.max_iterations ?? run.config?.max_iterations ?? '-')} · ${esc(fmtDate(run.created_at))}</p></div></div>
      <ol class="stepper" aria-label="단계">${stepper}</ol>
      ${controls}${review}</section>
    <section class="card card-pad" style="margin-top:16px"><h2 class="section-title">근거 카드</h2>${evidenceHtml}</section>
    <section class="card card-pad" style="margin-top:16px"><h2 class="section-title">검색 후보</h2>${candidates.length ? `<ul>${candidates.map(c => `<li>${esc(c.title || '제목 없음')}${c.year ? ` · ${esc(c.year)}` : ''}${c.doi ? ` · DOI ${esc(c.doi)}` : ''}</li>`).join('')}</ul>` : '<p class="help">검색 후보가 없습니다.</p>'}</section>
    <section class="card card-pad" style="margin-top:16px"><h2 class="section-title">문제 후보</h2>${problemsHtml}</section>
    <section class="card card-pad" style="margin-top:16px"><h2 class="section-title">방법 개선안</h2>${methodsHtml}</section>
    <section class="card card-pad" style="margin-top:16px"><h2 class="section-title">기여 초안</h2>${contributionsHtml}</section>
    ${saveCandidates ? `<div style="margin-top:16px">${saveCandidates}</div>` : ''}
    <section class="card card-pad" style="margin-top:16px"><h2 class="section-title">단계 기록</h2>
      <div class="table-wrap"><table class="step-table"><thead><tr><th>단계</th><th>상태</th><th>모델</th><th>오류</th></tr></thead><tbody>${stepRows}</tbody></table></div></section>`;
}

async function runAction(ctx, e) {
  const detail = ctx.$('#run-detail');
  const runId = detail?.dataset.runId;
  const button = e.target.closest('button');
  if (!runId || !button || button.disabled) return;
  const base = `/api/research-runs/${enc(runId)}`;
  let path = null;
  let body = {};
  let busy = '';
  let done = '';
  let confirmText = '';
  if (button.hasAttribute('data-run-step')) { path = '/step'; busy = '다음 단계를 실행하는 중입니다. 로컬 모델은 단계마다 1~2분 걸릴 수 있습니다.'; }
  else if (button.hasAttribute('data-run-advance')) { path = '/advance'; busy = '검토 지점까지 실행하는 중입니다. 여러 단계가 이어지므로 시간이 걸릴 수 있습니다.'; }
  else if (button.hasAttribute('data-run-cancel')) { path = '/cancel'; confirmText = '실행을 중단할까요? 지금까지의 단계 기록은 남습니다.'; done = '실행을 중단했습니다.'; }
  else if (button.hasAttribute('data-run-feedback')) {
    const focus = detail.querySelector('#run-focus').value;
    path = '/feedback';
    body = {note: detail.querySelector('#run-feedback').value.trim() || null, focus_problem: focus === '' ? null : Number(focus)};
    busy = '다음 반복을 준비하는 중입니다.';
  } else if (button.hasAttribute('data-run-save')) {
    const run = await ctx.api(base);
    const projectId = (run.run ?? run).project_id || ctx.state.projectId;
    if (!projectId) { ctx.notify('저장하려면 프로젝트를 선택하세요.', 'error'); return; }
    const problems = checkedValues(detail, 'run-save-problem').map(Number);
    const contributions = checkedValues(detail, 'run-save-contribution').map(Number);
    if (!problems.length && !contributions.length) { ctx.notify('저장할 문제나 기여를 고르세요.', 'error'); return; }
    path = '/save';
    body = {project_id: projectId, problems, contributions};
    done = '선택한 항목을 프로젝트에 저장했습니다. 아이디어와 갭에서 확인하세요.';
  }
  if (!path) return;
  if (confirmText && !window.confirm(confirmText)) return;
  detail.querySelectorAll('button').forEach(b => { b.disabled = true; });
  if (busy) ctx.notify(busy);
  try {
    await ctx.post(base + path, body);
    if (done) ctx.notify(done);
  } finally {
    await showRunDetail(ctx, runId).catch(() => {});
    await loadRuns(ctx).catch(() => {});
  }
}

// ---------- 연결 그래프 ----------

export async function showGraph(ctx) {
  ctx.$('#content').innerHTML = ctx.heading('연결 그래프', '서재 논문들의 연결을 봅니다. 점선은 추천 연결이고 실선은 확정된 연결입니다. 노드를 누르면 논문을 엽니다.',
    '<div class="toolbar"><button class="secondary" id="links-discover" type="button">연결 찾기</button><button class="secondary" id="links-openalex" type="button">OpenAlex 인용으로 연결</button></div>') +
    '<p class="help">“연결 찾기”는 이 PC의 분야·키워드를 비교합니다. “OpenAlex 인용으로 연결”은 DOI를 OpenAlex 서비스로 보내 인용 관계를 찾습니다.</p>' +
    `<section class="card card-pad" style="margin-top:12px"><fieldset class="rel-filter" id="rel-filter"><legend class="section-caption">관계 필터</legend>${Object.entries(REL_LABELS).map(([k, v]) => `<label class="check-item"><input type="checkbox" data-rel="${esc(k)}" checked> ${esc(v)}</label>`).join('')}</fieldset>
      <div id="graph-status" class="help" aria-live="polite"></div><div id="graph-box" class="graph-box"><p class="help">그래프를 불러오는 중입니다.</p></div></section>`;
  ctx.$('#links-discover').onclick = () => discoverLinks(ctx, false);
  ctx.$('#links-openalex').onclick = () => {
    if (!window.confirm('서재 논문의 DOI가 OpenAlex 서비스로 전송되어 인용 관계를 찾습니다. 계속할까요?')) return;
    discoverLinks(ctx, true);
  };
  const box = ctx.$('#graph-box');
  let data;
  try {
    data = await ctx.api('/api/library/graph');
  } catch (err) {
    box.innerHTML = ctx.empty('그래프를 불러오지 못했습니다', esc(err.message), '!');
    return;
  }
  const nodes = arr(data.nodes);
  const edges = arr(data.edges);
  if (!nodes.length) { box.innerHTML = ctx.empty('서재가 비어 있습니다', '논문을 추가하면 연결을 보여 줍니다.', '◎'); return; }
  if (!edges.length) { box.innerHTML = ctx.empty('연결이 없습니다', '“연결 찾기”를 누르면 분야와 키워드가 겹치는 논문을 추천 연결로 만듭니다. 논문 화면의 정보 탭에서 직접 연결할 수도 있습니다.', '◎'); return; }
  const redraw = () => {
    const active = new Set(ctx.$$('[data-rel]').filter(c => c.checked).map(c => c.dataset.rel));
    drawGraph(ctx, box, nodes, edges, active);
  };
  ctx.$('#rel-filter').onchange = redraw;
  redraw();
}

async function discoverLinks(ctx, useOpenAlex) {
  ctx.notify(useOpenAlex ? 'OpenAlex에서 인용 관계를 찾는 중입니다.' : '서재에서 연결 후보를 찾는 중입니다.');
  try {
    const result = await ctx.post('/api/library/links/discover', {use_openalex: useOpenAlex});
    const errors = arr(result?.errors).length;
    ctx.notify(`연결 ${result?.created ?? 0}개를 만들었습니다. 건너뜀 ${result?.skipped ?? 0}개${errors ? `, 오류 ${errors}개` : ''}. 추천 연결은 논문 화면의 정보 탭에서 확정하거나 제외할 수 있습니다.`);
    await showGraph(ctx);
  } catch (err) {
    ctx.error(err);
  }
}

const GRAPH_LIMIT = 300;
const GRAPH_W = 1000;
const GRAPH_H = 700;

function drawGraph(ctx, box, allNodes, allEdges, active) {
  if (box._stop) box._stop();
  const nodes = allNodes.slice(0, GRAPH_LIMIT);
  const ids = new Set(nodes.map(n => String(n.id)));
  const edges = allEdges.filter(e => active.has(e.relation) && ids.has(String(e.source)) && ids.has(String(e.target)));
  const status = ctx.$('#graph-status');
  if (status) status.textContent = `논문 ${nodes.length}편${allNodes.length > GRAPH_LIMIT ? ` (전체 ${allNodes.length}편 중 ${GRAPH_LIMIT}편만 표시)` : ''} · 연결 ${edges.length}개`;
  const index = new Map(nodes.map((n, i) => [String(n.id), i]));
  box.innerHTML = `<svg class="graph-svg" viewBox="0 0 ${GRAPH_W} ${GRAPH_H}" role="img" aria-label="논문 연결 그래프. 노드를 누르면 논문을 엽니다.">` +
    `<g class="g-edges">${edges.map(e => `<line stroke="#7f968c" stroke-width="1.4" stroke-dasharray="${esc(REL_DASH[e.relation] || '')}" opacity="${e.status === 'suggested' ? 0.5 : 0.85}"><title>${esc(REL_LABELS[e.relation] || e.relation)} · ${e.status === 'suggested' ? '추천' : '확정'}</title></line>`).join('')}</g>` +
    `<g class="g-nodes">${nodes.map(n => `<g class="graph-node" data-id="${esc(n.id)}" tabindex="0" role="link" aria-label="${esc(titleOf(n))}"><circle r="9" fill="${READ_COLORS[n.reading_status] || '#9aa9a2'}"></circle><text x="13" y="5" style="font-size:16px">${esc(short(titleOf(n), 28))}</text><title>${esc(titleOf(n))}${n.year ? ` (${esc(n.year)})` : ''} · ${esc(READ_LABELS[n.reading_status] || '')}</title></g>`).join('')}</g></svg>`;
  const svg = box.querySelector('svg');
  const groups = [...svg.querySelectorAll('.graph-node')];
  const lines = [...svg.querySelectorAll('line')];
  const layout = createForceLayout(nodes, edges, {width: GRAPH_W, height: GRAPH_H});
  const view = {x: 0, y: 0, w: GRAPH_W, h: GRAPH_H};
  const applyView = () => svg.setAttribute('viewBox', `${view.x} ${view.y} ${view.w} ${view.h}`);
  const paint = () => {
    const pos = layout.positions();
    pos.forEach((p, i) => groups[i]?.setAttribute('transform', `translate(${p.x.toFixed(1)} ${p.y.toFixed(1)})`));
    edges.forEach((e, i) => {
      const a = pos[index.get(String(e.source))];
      const b = pos[index.get(String(e.target))];
      if (a && b && lines[i]) { lines[i].setAttribute('x1', a.x.toFixed(1)); lines[i].setAttribute('y1', a.y.toFixed(1)); lines[i].setAttribute('x2', b.x.toFixed(1)); lines[i].setAttribute('y2', b.y.toFixed(1)); }
    });
  };
  let raf = 0;
  let stopped = false;
  const frame = () => {
    if (stopped) return;
    layout.step(10);
    paint();
    if (!layout.done()) raf = requestAnimationFrame(frame);
  };
  paint();
  if (typeof requestAnimationFrame === 'function') raf = requestAnimationFrame(frame);
  else { layout.step(400); paint(); }
  box._stop = () => { stopped = true; if (typeof cancelAnimationFrame === 'function') cancelAnimationFrame(raf); };

  const toView = (clientX, clientY) => {
    const r = svg.getBoundingClientRect();
    return {x: view.x + ((clientX - r.left) / r.width) * view.w, y: view.y + ((clientY - r.top) / r.height) * view.h};
  };
  svg.addEventListener('wheel', e => {
    e.preventDefault();
    const point = toView(e.clientX, e.clientY);
    const factor = e.deltaY > 0 ? 1.12 : 1 / 1.12;
    const nextW = clamp(view.w * factor, GRAPH_W * 0.25, GRAPH_W * 4);
    const ratio = nextW / view.w;
    view.x = point.x - (point.x - view.x) * ratio;
    view.y = point.y - (point.y - view.y) * ratio;
    view.w = nextW;
    view.h = nextW * GRAPH_H / GRAPH_W;
    applyView();
  }, {passive: false});
  let drag = null;
  let suppressClick = false;
  svg.addEventListener('pointerdown', e => {
    if (e.button !== 0) return;
    drag = {x: e.clientX, y: e.clientY, vx: view.x, vy: view.y, moved: false};
  });
  svg.addEventListener('pointermove', e => {
    if (!drag) return;
    const dx0 = e.clientX - drag.x;
    const dy0 = e.clientY - drag.y;
    if (!drag.moved && Math.hypot(dx0, dy0) <= 4) return;
    if (!drag.moved) { drag.moved = true; svg.setPointerCapture?.(e.pointerId); }
    const r = svg.getBoundingClientRect();
    view.x = drag.vx - dx0 * view.w / r.width;
    view.y = drag.vy - dy0 * view.h / r.height;
    applyView();
  });
  const endDrag = () => { if (drag?.moved) suppressClick = true; drag = null; };
  svg.addEventListener('pointerup', endDrag);
  svg.addEventListener('pointercancel', endDrag);
  svg.addEventListener('click', e => {
    if (suppressClick) { suppressClick = false; return; }
    const node = e.target.closest?.('.graph-node');
    if (node) ctx.openPaper(node.dataset.id).catch(err => ctx.error(err));
  });
  svg.addEventListener('keydown', e => {
    if ((e.key === 'Enter' || e.key === ' ') && e.target.classList?.contains('graph-node')) {
      e.preventDefault();
      ctx.openPaper(e.target.dataset.id).catch(err => ctx.error(err));
    }
  });
}

// ---------- 논문 정리 (논문 화면 정보 탭) ----------

function facetHtml(key, label, items) {
  if (!items.length) return '';
  return `<div class="facet"><h4>${esc(label)}</h4>${items.map(item => `<div class="facet-item"><p>${esc(item.text)} <span class="origin-tag ${item.origin === 'author_stated' ? 'author' : 'inferred'}">${esc(ORIGIN_LABELS[item.origin] || item.origin || '')}</span></p>${arr(item.evidence).map(evidenceQuote).join('')}</div>`).join('')}</div>`;
}

function evidenceQuote(ev) {
  const page = Number.isInteger(ev.found_page) ? ev.found_page : (Number.isInteger(ev.page) ? ev.page : null);
  const clickable = ev.match !== 'not_found' && page;
  const quote = `<span class="evidence-quote">${esc(ev.quote || '')}</span>`;
  const body = clickable
    ? `<button type="button" class="quote-btn" data-evidence-page="${page}" title="${page}쪽으로 이동">${quote}<span class="section-caption"> · ${page}쪽</span></button>`
    : quote;
  return `<div class="quote-row">${body} ${matchBadge(ev.match)}</div>`;
}

function linkRow(link, paperId) {
  const otherId = link.source_paper_id === paperId ? link.target_paper_id : link.source_paper_id;
  const otherTitle = link.other_title || link.other_paper_title || link.title || '상대 논문';
  const relation = REL_LABELS[link.relation] || link.relation;
  const statusLabel = {suggested: '추천', accepted: '확정', rejected: '제외'}[link.status] || link.status;
  const actions = [
    link.status !== 'accepted' ? `<button type="button" class="ghost" data-link-status="accepted" data-link-id="${esc(link.id)}">수락</button>` : '',
    link.status !== 'rejected' ? `<button type="button" class="ghost" data-link-status="rejected" data-link-id="${esc(link.id)}">제외</button>` : '',
    `<button type="button" class="ghost" data-link-delete="${esc(link.id)}">삭제</button>`,
  ].join('');
  return `<div class="link-row"><span class="pill">${esc(relation)}</span><button type="button" class="paper-title small" data-open-paper="${esc(otherId)}">${esc(otherTitle)}</button><span class="section-caption">${esc(statusLabel)} · ${esc(ORIGIN_LABELS[link.origin] || link.origin || '')}</span><span class="link-actions">${actions}</span></div>`;
}

export async function renderPaperProfileSection(container, paper, ctx) {
  if (!container || !paper) return;
  const paperId = paper.id;
  container.innerHTML = '<h3>논문 정리</h3><p class="help">불러오는 중입니다.</p>';
  let profileData;
  let links;
  try {
    [profileData, links] = await Promise.all([
      ctx.api(`/api/papers/${enc(paperId)}/profile`),
      ctx.api(`/api/papers/${enc(paperId)}/links`),
    ]);
  } catch (err) {
    if (container.isConnected) container.innerHTML = `<h3>논문 정리</h3><p class="help">불러오지 못했습니다: ${esc(err.message)}</p>`;
    return;
  }
  if (!container.isConnected) return;
  const profile = profileData?.profile || null;
  const history = arr(profileData?.history);
  const data = profile?.data || {};
  const facets = data.facets || {};
  const linkList = arr(links, 'links');
  const others = (ctx.state.libraryPapers || []).filter(p => String(p.id) !== String(paperId));
  container.innerHTML = `<h3>논문 정리</h3>
    <div class="toolbar" style="margin:0"><button type="button" class="secondary" data-profile-rules>규칙으로 정리</button><button type="button" class="secondary" data-profile-ai>AI로 정리</button>${profile && profile.status !== 'confirmed' ? `<button type="button" class="primary" data-profile-confirm="${esc(profile.id)}">확정</button>` : ''}</div>
    ${profile
      ? `<p class="help">${esc(ORIGIN_LABELS[profile.origin] || profile.origin)} · 모델 ${esc(profile.model || '없음')} · ${esc(fmtDate(profile.created_at))} · ${profile.status === 'confirmed' ? '확정됨' : '초안'} · 이전 기록 ${Math.max(0, history.length - 1)}개</p>`
      : '<p class="help">아직 정리가 없습니다. 규칙 정리는 단서 문장을 찾고, AI 정리는 제목·초록·본문으로 초안을 만듭니다. 둘 다 초안이므로 확정해야 합니다.</p>'}
    ${data.summary ? `<p class="profile-summary">${esc(data.summary)}</p>` : ''}
    ${profile ? Object.entries(FACET_LABELS).map(([key, label]) => facetHtml(key, label, arr(facets[key]))).join('') : ''}
    <div class="info-block"><h3>연결된 논문</h3>${linkList.length ? linkList.map(l => linkRow(l, paperId)).join('') : '<p class="help">연결된 논문이 없습니다.</p>'}
      ${others.length ? `<form id="link-add-form" class="link-form"><label class="sr-only" for="link-target">연결할 논문</label><select id="link-target">${others.map(p => `<option value="${esc(p.id)}">${esc(titleOf(p))}</option>`).join('')}</select><label class="sr-only" for="link-relation">관계</label><select id="link-relation">${Object.entries(REL_LABELS).map(([v, l]) => `<option value="${esc(v)}">${esc(l)}</option>`).join('')}</select><button type="submit" class="secondary">연결 추가</button></form>` : '<p class="help">연결할 다른 논문이 서재에 없습니다.</p>'}
    </div>`;
  container.onclick = async e => {
    const target = e.target.closest('button');
    if (!target) return;
    try {
      if (target.hasAttribute('data-profile-rules')) {
        await ctx.post(`/api/papers/${enc(paperId)}/profile/rules`, {});
        ctx.notify('규칙으로 정리했습니다. 초안이므로 원문과 대조하세요.');
      } else if (target.hasAttribute('data-profile-ai')) {
        const result = await sendWithPreview(ctx, `/api/papers/${enc(paperId)}/profile/ai/preview`, `/api/papers/${enc(paperId)}/profile/ai`, {}, {busyText: 'AI가 논문을 정리하는 중입니다. 로컬 모델은 1~2분 걸릴 수 있습니다.'});
        if (result === null) return;
        ctx.notify('AI로 정리했습니다. 초안이므로 원문과 대조하세요.');
      } else if (target.hasAttribute('data-profile-confirm')) {
        await ctx.api(`/api/profiles/${enc(target.dataset.profileConfirm)}`, asBody({status: 'confirmed'}));
        ctx.notify('정리를 확정했습니다.');
      } else if (target.hasAttribute('data-evidence-page')) {
        const page = Number(target.dataset.evidencePage);
        if (ctx.currentPaperId?.() === paperId && ctx.gotoPage) ctx.gotoPage(page);
        else await ctx.openPaper(paperId, page);
        return;
      } else if (target.hasAttribute('data-link-status')) {
        await ctx.api(`/api/paper-links/${enc(target.dataset.linkId)}`, asBody({status: target.dataset.linkStatus}));
      } else if (target.hasAttribute('data-link-delete')) {
        if (!window.confirm('이 연결을 삭제할까요?')) return;
        await ctx.api(`/api/paper-links/${enc(target.dataset.linkDelete)}`, {method: 'DELETE'});
      } else if (target.hasAttribute('data-open-paper')) {
        await ctx.openPaper(target.dataset.openPaper);
        return;
      } else {
        return;
      }
      await renderPaperProfileSection(container, paper, ctx);
    } catch (err) {
      ctx.error(err);
    }
  };
  const linkForm = container.querySelector('#link-add-form');
  if (linkForm) linkForm.onsubmit = async e => {
    e.preventDefault();
    const button = linkForm.querySelector('button');
    button.disabled = true;
    try {
      await ctx.post('/api/paper-links', {
        source_paper_id: paperId,
        target_paper_id: linkForm.querySelector('#link-target').value,
        relation: linkForm.querySelector('#link-relation').value,
        origin: 'manual',
      });
      ctx.notify('연결을 추가했습니다.');
      await renderPaperProfileSection(container, paper, ctx);
    } catch (err) {
      ctx.error(err);
      button.disabled = false;
    }
  };
}

// ---------- 분야 AI 분류 ----------

export async function aiClassifyLibrary(ctx) {
  await ctx.refreshLibrary().catch(() => {});
  const papers = (ctx.state.libraryPapers || []).filter(p => p.reading_status === 'read');
  if (!papers.length) {
    ctx.notify('AI 분류는 읽음 상태의 논문에 실행합니다. 읽음으로 표시된 논문이 없습니다.', 'error');
    return null;
  }
  const summary = {done: 0, failed: 0, skipped: 0, proposed: new Set(), errors: []};
  for (let i = 0; i < papers.length; i++) {
    const paper = papers[i];
    ctx.notify(`AI 분류 ${i + 1}/${papers.length}: ${titleOf(paper)}`);
    try {
      const result = await sendWithPreview(ctx,
        `/api/papers/${enc(paper.id)}/classify/ai/preview`,
        `/api/papers/${enc(paper.id)}/classify/ai`, {},
        {busyText: `${i + 1}/${papers.length} 분류 중입니다.`});
      if (result === null) {
        summary.skipped += papers.length - i;
        break;
      }
      summary.done += 1;
      for (const name of arr(result?.proposed_new)) {
        const label = typeof name === 'string' ? name : String(name?.name || '');
        if (label) summary.proposed.add(label);
      }
    } catch (err) {
      summary.failed += 1;
      summary.errors.push(`${titleOf(paper)}: ${err.message}`);
    }
  }
  await ctx.refreshLibrary().catch(() => {});
  await ctx.refreshCategories?.().catch(() => {});
  const proposed = [...summary.proposed];
  ctx.modal(`<div class="modal-head"><h2>AI 분류 완료</h2><button class="close" aria-label="닫기">×</button></div>` +
    `<p>완료 ${summary.done}편 · 실패 ${summary.failed}편 · 건너뜀 ${summary.skipped}편</p>` +
    `<p class="help">AI 제안은 점선으로 표시됩니다. 확정하거나 제외할 수 있으며, 확정·제외한 기록은 바뀌지 않습니다.</p>` +
    (proposed.length ? `<h3 class="section-title">새 분야 제안 (목록에 없음)</h3><div class="chip-row">${proposed.map(n => `<span class="chip suggested">${esc(n)}</span>`).join('')}</div><p class="help">새 분야는 분야 화면에서 직접 추가한 뒤 다시 분류해야 적용됩니다.</p>` : '') +
    (summary.errors.length ? `<h3 class="section-title">실패 목록</h3><ul class="help">${summary.errors.map(x => `<li>${esc(x)}</li>`).join('')}</ul>` : ''));
  ctx.notify(`AI 분류를 마쳤습니다. 완료 ${summary.done}편, 실패 ${summary.failed}편.`);
  return {done: summary.done, failed: summary.failed, skipped: summary.skipped, proposed_new: proposed};
}

export const VIEW_NAMES = {
  'research-chat': '연구 채팅',
  gaps: '갭 찾기',
  'research-loop': '자동 연구',
  graph: '연결 그래프',
  'ai-settings': 'AI 설정',
};
