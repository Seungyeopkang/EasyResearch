// PDF.js 6.2.108. Two viewers share this module:
// - renderPdfPage: one physical page at a time (used by the current app flow).
// - renderPdfDocument: continuous vertical scroll; only pages near the viewport
//   keep a canvas and text layer, and at most MAX_RENDERED_PAGES are kept.
// Selection is tied to one physical PDF page; text is never reflowed here.
let pdfjs;
let current = {id: null, task: null, document: null, generation: 0};
let continuous = null;

const NEAR_MARGIN = '1500px 0px';
const MAX_RENDERED_PAGES = 8;
const PAGE_GAP = 12;
const PAGE_PADDING = 16;
const MAX_MEASURED_PAGES = 500;
const PAGE_CHANGE_DELAY_MS = 300;

async function ensurePdfJs() {
  if (!pdfjs) {
    const module = await import('/assets/vendor/pdfjs/pdf.min.mjs?v=6.2.108');
    module.GlobalWorkerOptions.workerSrc = '/assets/vendor/pdfjs/pdf.worker.min.mjs?v=6.2.108';
    pdfjs = module;
  }
  return pdfjs;
}

function documentOptions(paperId) {
  return {
    url: `/api/papers/${encodeURIComponent(paperId)}/file`,
    // The app displays pages and text only; do not activate XFA forms or
    // generated evaluation code for document content.
    enableXfa: false, isEvalSupported: false,
    cMapUrl: '/assets/vendor/pdfjs/cmaps/', cMapPacked: true,
    standardFontDataUrl: '/assets/vendor/pdfjs/standard_fonts/',
    wasmUrl: '/assets/vendor/pdfjs/wasm/', iccUrl: '/assets/vendor/pdfjs/iccs/'
  };
}

export async function renderPdfPage(container, paperId, pageNumber, onSelection, zoom = 1) {
  const generation = ++current.generation;
  disposeContinuous();
  try {
    await ensurePdfJs();
    if (generation !== current.generation || !container.isConnected) return;
    if (current.id !== paperId) {
      const previousTask = current.task;
      current.id = paperId;
      current.document = null;
      current.task = pdfjs.getDocument(documentOptions(paperId));
      if (previousTask) await previousTask.destroy();
      if (generation !== current.generation || !container.isConnected) return;
    }
    const task = current.task;
    const document = current.document || await task.promise;
    if (generation !== current.generation || current.task !== task || !container.isConnected) return;
    current.document = document;
    if (pageNumber < 1 || pageNumber > document.numPages) throw new Error(`파일에는 ${document.numPages}쪽이 있습니다.`);
    const page = await document.getPage(pageNumber);
    if (generation !== current.generation || !container.isConnected) return;
    // A single page is rendered at a time to bound memory on long documents.
    const base = page.getViewport({scale: 1});
    const scale = Math.min(1.15 * zoom, 4000 / Math.max(base.width, base.height), Math.sqrt(12000000 / (base.width * base.height)));
    const viewport = page.getViewport({scale});
    const surface = documentNode('div', 'pdf-page');
    surface.style.width = `${viewport.width}px`;
    surface.style.height = `${viewport.height}px`;
    surface.style.setProperty('--total-scale-factor', String(scale));
    surface.style.setProperty('--scale-round-x', '1px');
    surface.style.setProperty('--scale-round-y', '1px');
    const canvas = documentNode('canvas', 'pdf-canvas');
    const ratio = Math.min(window.devicePixelRatio || 1, 2, Math.sqrt(16000000 / (viewport.width * viewport.height)));
    canvas.width = Math.ceil(viewport.width * ratio);
    canvas.height = Math.ceil(viewport.height * ratio);
    canvas.style.width = `${viewport.width}px`;
    canvas.style.height = `${viewport.height}px`;
    surface.append(canvas);
    const textLayer = documentNode('div', 'textLayer');
    surface.append(textLayer);
    container.replaceChildren(surface);
    await page.render({canvasContext: canvas.getContext('2d'), viewport, transform: ratio === 1 ? null : [ratio, 0, 0, ratio, 0, 0]}).promise;
    if (generation !== current.generation || !container.isConnected) return;
    const layer = new pdfjs.TextLayer({textContentSource: page.streamTextContent(), container: textLayer, viewport});
    await layer.render();
    if (generation !== current.generation || !container.isConnected) return;
    textLayer.addEventListener('mouseup', () => {
      const selection = window.getSelection();
      if (!selection || !selection.anchorNode || !selection.focusNode ||
          !textLayer.contains(selection.anchorNode) || !textLayer.contains(selection.focusNode)) return;
      const text = selection.toString().trim();
      if (text) onSelection(text, pageNumber, selectionContext(selection, textLayer));
    });
    return {pageCount: document.numPages};
  } catch (error) {
    if (generation === current.generation && container.isConnected) {
      container.textContent = `PDF를 표시하지 못했습니다: ${error?.message || '파일을 확인해 주세요.'}`;
    }
    return null;
  }
}

// Continuous vertical viewer. Page sizes are measured up front for documents of
// up to MAX_MEASURED_PAGES pages (one getPage per page, no rendering). Longer
// documents use the first page's size for every placeholder and correct a page's
// size when it is first rendered; browser scroll anchoring absorbs the shift.
// Resolves to a controller {scrollToPage, getCurrentPage, setZoom, getZoom}, or
// null when the viewer was replaced, closed, or failed (failure text is shown).
export async function renderPdfDocument(container, paperId, options = {}) {
  const session = createSession(container, options);
  const previous = resetViewer();
  continuous = session;
  await previous;
  if (isStale(session)) return null;
  try {
    await ensurePdfJs();
    if (isStale(session)) return null;
    const task = pdfjs.getDocument(documentOptions(paperId));
    session.task = task;
    if (isStale(session)) {
      await destroyTask(task);
      return null;
    }
    const pdf = await task.promise;
    if (isStale(session)) return null;
    if (!pdf.numPages || pdf.numPages < 1) throw new Error('페이지가 없는 파일입니다.');
    session.pdf = pdf;
    session.pageCount = pdf.numPages;
    await measurePages(session);
    if (isStale(session)) return null;
    buildPages(session);
    layout(session);
    session.io = new IntersectionObserver(entries => onNearChange(session, entries), {root: container, rootMargin: NEAR_MARGIN});
    for (const p of session.pages) session.io.observe(p.el);
    session.listeners = {
      scroll: () => onScroll(session),
      mouseup: event => onMouseUp(session, event)
    };
    container.addEventListener('scroll', session.listeners.scroll);
    container.addEventListener('mouseup', session.listeners.mouseup);
    session.current = clampPage(session, session.startPage);
    session.reported = session.current;
    scrollToPageNumber(session, session.current, 'auto');
    session.onReady?.({pageCount: session.pageCount});
    return controllerFor(session);
  } catch (error) {
    if (!isStale(session)) {
      container.textContent = `PDF를 표시하지 못했습니다: ${error?.message || '파일을 확인해 주세요.'}`;
    }
    await disposeSession(session);
    if (continuous === session) continuous = null;
    return null;
  }
}

function createSession(container, options) {
  return {
    container,
    startPage: Number(options.startPage) || 1,
    zoom: clampZoom(options.zoom),
    onSelection: options.onSelection,
    onPageChange: options.onPageChange,
    onReady: options.onReady,
    disposed: false,
    task: null, pdf: null, io: null, timer: null, listeners: null, stack: null,
    pageCount: 0, pages: [], byElement: new Map(), base: [], sizes: [], tops: [],
    near: new Set(), rendered: new Set(),
    current: 1, reported: 1
  };
}

function isStale(session) {
  return session.disposed || continuous !== session || !session.container.isConnected;
}

function controllerFor(session) {
  return {
    scrollToPage(page, {behavior = 'auto'} = {}) {
      if (isStale(session)) return session.current;
      return scrollToPageNumber(session, page, behavior);
    },
    getCurrentPage() {
      return session.current;
    },
    setZoom(zoom) {
      applyZoom(session, zoom);
    },
    getZoom() {
      return session.zoom;
    }
  };
}

async function measurePages(session) {
  const pdf = session.pdf;
  const count = pdf.numPages;
  for (let n = 1; n <= count; n++) {
    if (n > 1 && count > MAX_MEASURED_PAGES) {
      session.base[n - 1] = session.base[0];
      continue;
    }
    const page = await pdf.getPage(n);
    const viewport = page.getViewport({scale: 1});
    session.base[n - 1] = {width: viewport.width, height: viewport.height};
    safeCall(() => page.cleanup());
    if (isStale(session)) return;
  }
}

function buildPages(session) {
  const container = session.container;
  container.style.overflow = 'auto';
  container.classList?.add('pdf-continuous');
  const stack = documentNode('div', 'pdf-stack');
  session.stack = stack;
  container.replaceChildren(stack);
  for (let n = 1; n <= session.pageCount; n++) {
    const el = documentNode('div', 'pdf-page');
    el.dataset.pageNumber = String(n);
    const label = documentNode('span', 'pdf-page-label');
    label.textContent = `${n} / ${session.pageCount}`;
    el.append(label);
    const page = {number: n, el, canvas: null, textLayer: null, state: 'idle', token: 0, renderTask: null, textTask: null, proxy: null};
    session.pages.push(page);
    session.byElement.set(el, page);
    stack.append(el);
  }
}

// Computes each page's display size and top offset from the zoom and the
// container width, then writes the placeholder sizes.
function layout(session) {
  const tops = [];
  const sizes = [];
  let top = PAGE_PADDING;
  session.pages.forEach((p, i) => {
    const base = session.base[i];
    const scale = pageScale(session, base);
    const width = base.width * scale;
    const height = base.height * scale;
    sizes[i] = {width, height, scale};
    tops[i] = top;
    p.el.style.width = `${width}px`;
    p.el.style.height = `${height}px`;
    p.el.style.marginBottom = `${PAGE_GAP}px`;
    top += height + PAGE_GAP;
  });
  session.sizes = sizes;
  session.tops = tops;
  session.stack.style.padding = `${PAGE_PADDING}px 0`;
  session.stack.style.width = '100%';
}

function pageScale(session, base) {
  const cssWidth = Math.max(280, session.container.clientWidth - PAGE_PADDING * 2);
  return Math.max(0.3, Math.min(2, cssWidth / base.width)) * session.zoom;
}

function pageAt(session, y) {
  const tops = session.tops;
  let lo = 0;
  let hi = tops.length - 1;
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1;
    if (tops[mid] <= y) lo = mid;
    else hi = mid - 1;
  }
  return lo + 1;
}

function clampPage(session, page) {
  return Math.min(session.pageCount, Math.max(1, Math.trunc(Number(page)) || 1));
}

function scrollToPageNumber(session, page, behavior) {
  const target = clampPage(session, page);
  session.current = target;
  const top = session.tops[target - 1];
  const container = session.container;
  if (typeof container.scrollTo === 'function') container.scrollTo({top, behavior});
  else container.scrollTop = top;
  scheduleReport(session);
  return target;
}

function onScroll(session) {
  if (isStale(session)) return;
  const container = session.container;
  session.current = pageAt(session, container.scrollTop + container.clientHeight / 2);
  scheduleReport(session);
  renderNear(session);
}

// onPageChange fires only when the page differs from the last reported page,
// after the position has settled for PAGE_CHANGE_DELAY_MS.
function scheduleReport(session) {
  clearTimeout(session.timer);
  session.timer = setTimeout(() => {
    session.timer = null;
    if (isStale(session) || session.current === session.reported) return;
    session.reported = session.current;
    session.onPageChange?.(session.current);
  }, PAGE_CHANGE_DELAY_MS);
}

function onNearChange(session, entries) {
  if (isStale(session)) return;
  for (const entry of entries) {
    const p = session.byElement.get(entry.target);
    if (!p) continue;
    if (entry.isIntersecting) {
      session.near.add(p.number);
    } else {
      session.near.delete(p.number);
      releasePage(session, p);
    }
  }
  renderNear(session);
}

function renderNear(session) {
  const ordered = [...session.near].sort((a, b) => distance(session, a) - distance(session, b));
  for (const n of ordered) renderPage(session, session.pages[n - 1]);
}

function distance(session, pageNumber) {
  return Math.abs(pageNumber - session.current);
}

// Admits a page into the rendered set. When the set is full, the farthest page
// from the current page is released, but only if it is farther than this one.
function admit(session, p) {
  if (session.rendered.size < MAX_RENDERED_PAGES) return true;
  let worst = null;
  let worstDistance = -1;
  for (const q of session.rendered) {
    const d = distance(session, q.number);
    if (d > worstDistance) {
      worst = q;
      worstDistance = d;
    }
  }
  if (worst && worstDistance > distance(session, p.number)) {
    releasePage(session, worst);
    return true;
  }
  return false;
}

async function renderPage(session, p) {
  if (p.state !== 'idle' || !admit(session, p)) return;
  p.state = 'rendering';
  session.rendered.add(p);
  const token = ++p.token;
  const live = () => !isStale(session) && p.token === token && p.state === 'rendering';
  try {
    const page = await session.pdf.getPage(p.number);
    if (!live()) {
      safeCall(() => page.cleanup());
      return;
    }
    p.proxy = page;
    const base = page.getViewport({scale: 1});
    const known = session.base[p.number - 1];
    if (Math.abs(base.width - known.width) > 0.5 || Math.abs(base.height - known.height) > 0.5) {
      session.base[p.number - 1] = {width: base.width, height: base.height};
      layout(session);
      scrollToPageNumber(session, session.current, 'auto');
    }
    const {scale} = session.sizes[p.number - 1];
    const viewport = page.getViewport({scale});
    const ratio = Math.min(window.devicePixelRatio || 1, 2, Math.sqrt(16000000 / (viewport.width * viewport.height)));
    const canvas = documentNode('canvas', 'pdf-canvas');
    canvas.width = Math.ceil(viewport.width * ratio);
    canvas.height = Math.ceil(viewport.height * ratio);
    canvas.style.width = `${viewport.width}px`;
    canvas.style.height = `${viewport.height}px`;
    const textLayer = documentNode('div', 'textLayer');
    p.canvas = canvas;
    p.textLayer = textLayer;
    p.el.append(canvas);
    p.el.append(textLayer);
    p.renderTask = page.render({canvasContext: canvas.getContext('2d'), viewport, transform: ratio === 1 ? null : [ratio, 0, 0, ratio, 0, 0]});
    await p.renderTask.promise;
    if (!live()) return;
    const layer = new pdfjs.TextLayer({textContentSource: page.streamTextContent(), container: textLayer, viewport});
    p.textTask = layer;
    await layer.render();
    if (!live()) return;
    p.renderTask = null;
    p.textTask = null;
    p.state = 'done';
  } catch (error) {
    // Cancelled renders from releasePage are expected and silent.
    if (live()) {
      releasePage(session, p);
      const note = documentNode('div', 'pdf-page-error');
      note.textContent = `이 페이지를 표시하지 못했습니다: ${error?.message || '알 수 없는 오류'}`;
      p.el.append(note);
    }
  }
}

// Releases a page's canvas and text layer. Any in-flight render for the page is
// cancelled, and its token is bumped so late results are ignored.
function releasePage(session, p) {
  p.token++;
  p.state = 'idle';
  session.rendered.delete(p);
  safeCall(() => p.renderTask?.cancel());
  safeCall(() => p.textTask?.cancel?.());
  safeCall(() => p.proxy?.cleanup());
  p.renderTask = null;
  p.textTask = null;
  p.proxy = null;
  if (p.canvas) {
    p.canvas.width = 0;
    p.canvas.height = 0;
    p.canvas.remove();
    p.canvas = null;
  }
  if (p.textLayer) {
    p.textLayer.replaceChildren();
    p.textLayer.remove();
    p.textLayer = null;
  }
  p.el.querySelectorAll?.('.pdf-page-error').forEach(node => node.remove());
}

function applyZoom(session, zoom) {
  const next = clampZoom(zoom);
  if (isStale(session) || next === session.zoom) return;
  session.zoom = next;
  for (const p of session.pages) releasePage(session, p);
  layout(session);
  scrollToPageNumber(session, session.current, 'auto');
  renderNear(session);
}

function onMouseUp(session, event) {
  if (isStale(session) || !session.onSelection) return;
  const selection = window.getSelection?.();
  if (!selection || !selection.anchorNode || !selection.focusNode) return;
  const start = pageOf(session, selection.anchorNode);
  const end = pageOf(session, selection.focusNode);
  // Selections that span two pages are ignored; the viewer does not guess a page.
  if (!start || start !== end || !start.textLayer) return;
  if (!start.textLayer.contains(selection.anchorNode) || !start.textLayer.contains(selection.focusNode)) return;
  const text = selection.toString().trim();
  if (text) session.onSelection(text, start.number, selectionContext(selection, start.textLayer));
}

function pageOf(session, node) {
  const element = node.nodeType === 3 ? node.parentElement : node;
  const pageElement = element?.closest?.('.pdf-page');
  return pageElement ? session.byElement.get(pageElement) || null : null;
}

function disposeSession(session) {
  if (!session || session.disposed) return Promise.resolve();
  session.disposed = true;
  session.io?.disconnect();
  clearTimeout(session.timer);
  session.timer = null;
  if (session.listeners) {
    session.container.removeEventListener('scroll', session.listeners.scroll);
    session.container.removeEventListener('mouseup', session.listeners.mouseup);
  }
  for (const p of session.pages) releasePage(session, p);
  return destroyTask(session.task);
}

function disposeContinuous() {
  const session = continuous;
  continuous = null;
  return disposeSession(session);
}

function destroyTask(task) {
  if (!task) return Promise.resolve();
  try {
    return Promise.resolve(task.destroy()).catch(() => {});
  } catch {
    return Promise.resolve();
  }
}

function clampZoom(zoom) {
  return Number.isFinite(zoom) ? Math.min(3, Math.max(0.5, zoom)) : 1;
}

function safeCall(fn) {
  try {
    fn();
  } catch {
    // Cleanup of an already finished or cancelled PDF.js object may throw.
  }
}

// Text from PDF.js and the extraction backend can differ. The context is only
// a hint for locating repeated text; a mismatch must never confirm a match.
function selectionContext(selection, textLayer) {
  try {
    if (selection.rangeCount !== 1) return {prefix: '', suffix: ''};
    const selected = selection.getRangeAt(0);
    if (!textLayer.contains(selected.startContainer) || !textLayer.contains(selected.endContainer)) {
      return {prefix: '', suffix: ''};
    }
    const before = selected.cloneRange();
    before.selectNodeContents(textLayer);
    before.setEnd(selected.startContainer, selected.startOffset);
    const after = selected.cloneRange();
    after.selectNodeContents(textLayer);
    after.setStart(selected.endContainer, selected.endOffset);
    return {prefix: before.toString().slice(-120), suffix: after.toString().slice(0, 120)};
  } catch {
    return {prefix: '', suffix: ''};
  }
}

function documentNode(tag, className) {
  const node = document.createElement(tag);
  node.className = className;
  return node;
}

// Resets the shared state: any pending renderPdfPage or renderPdfDocument call
// becomes stale, and the open documents are destroyed.
function resetViewer() {
  current.generation++;
  const task = current.task;
  current = {id: null, task: null, document: null, generation: current.generation};
  const session = continuous;
  continuous = null;
  return Promise.all([disposeSession(session), task ? destroyTask(task) : null]);
}

export async function closePdfViewer() {
  await resetViewer();
}
