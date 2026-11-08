'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '..', '..', 'apps', 'web', 'pdf-viewer.js'), 'utf8')
  .replace("import('/assets/vendor/pdfjs/pdf.min.mjs?v=6.2.108')", '__loadPdfJs()')
  .replace(/^export /gm, '');

const PAGE_W = 612;
const PAGE_H = 792;
const GAP = 12;
const PADDING = 16;
const flush = () => new Promise(resolve => setImmediate(resolve));
const plain = value => JSON.parse(JSON.stringify(value));
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

function deferred() {
  let resolve;
  const promise = new Promise(done => { resolve = done; });
  return {promise, resolve};
}

class FakeNode {
  constructor(tag) {
    this.tagName = String(tag).toUpperCase();
    this.nodeType = 1;
    this.parentNode = null;
    this.children = [];
    this.className = '';
    this.style = {};
    this.dataset = {};
    this.listeners = {};
    this.isConnected = true;
    this.textContent = '';
    this.scrollTop = 0;
    this.clientHeight = 600;
    this.clientWidth = 800;
    this.classList = {add() {}};
  }
  get parentElement() { return this.parentNode; }
  append(...nodes) {
    for (const node of nodes) {
      if (node.parentNode) node.remove();
      node.parentNode = this;
      this.children.push(node);
    }
  }
  replaceChildren(...nodes) {
    for (const child of this.children) child.parentNode = null;
    this.children = [];
    this.append(...nodes);
  }
  remove() {
    if (!this.parentNode) return;
    this.parentNode.children = this.parentNode.children.filter(child => child !== this);
    this.parentNode = null;
  }
  contains(node) {
    for (let n = node; n; n = n.parentNode) if (n === this) return true;
    return false;
  }
  closest(selector) {
    const name = selector.slice(1);
    for (let n = this; n; n = n.parentNode) {
      if (n.className && n.className.split(' ').includes(name)) return n;
    }
    return null;
  }
  querySelectorAll(selector) {
    const name = selector.slice(1);
    const found = [];
    const walk = node => {
      for (const child of node.children) {
        if (child.className.split(' ').includes(name)) found.push(child);
        walk(child);
      }
    };
    walk(this);
    return found;
  }
  addEventListener(type, fn) { (this.listeners[type] ??= []).push(fn); }
  removeEventListener(type, fn) { this.listeners[type] = (this.listeners[type] || []).filter(f => f !== fn); }
  dispatch(type) {
    for (let n = this; n; n = n.parentNode) {
      for (const fn of n.listeners[type] || []) fn({target: this});
    }
  }
  getContext() { return {}; }
  scrollTo(options) { this.scrollTop = options.top; this.lastScroll = options; }
}

class FakeIntersectionObserver {
  constructor(callback, options) {
    this.callback = callback;
    this.options = options;
    this.targets = [];
    this.disconnected = false;
    FakeIntersectionObserver.instances.push(this);
  }
  observe(node) { this.targets.push(node); }
  disconnect() { this.disconnected = true; }
}
FakeIntersectionObserver.instances = [];

function fire(io, nodes, isIntersecting) {
  io.callback(nodes.map(target => ({target, isIntersecting})));
}

function pagesOf(container) {
  return container.children[0].children.filter(child => child.className === 'pdf-page');
}

function renderedCount(container) {
  return pagesOf(container).filter(page => page.children.some(child => child.tagName === 'CANVAS')).length;
}

function topOf(container, pageNumber) {
  let top = PADDING;
  const pages = pagesOf(container);
  for (let i = 0; i < pageNumber - 1; i++) top += parseFloat(pages[i].style.height) + GAP;
  return top;
}

function createHarness() {
  const env = {
    numPages: 30,
    holdPages: false,
    heldPages: [],
    selection: null,
    destroyed: 0,
    documentQueue: [],
    layers: [],
    renders: 0
  };
  const makePage = number => ({
    number,
    getViewport({scale}) { return {width: PAGE_W * scale, height: PAGE_H * scale}; },
    render() {
      env.renders++;
      return {promise: Promise.resolve(), cancel() {}};
    },
    streamTextContent() { return {}; },
    cleanup() {}
  });
  const makeDocument = count => ({
    numPages: count,
    getPage(number) {
      const page = makePage(number);
      if (!env.holdPages) return Promise.resolve(page);
      const held = deferred();
      env.heldPages.push({resolve: () => held.resolve(page)});
      return held.promise;
    }
  });
  class FakeTextLayer {
    constructor(options) {
      this.container = options.container;
      env.layers.push(this);
    }
    render() {
      this.span = new FakeNode('span');
      this.container.append(this.span);
      return Promise.resolve();
    }
    cancel() {}
  }
  const pdfjs = {
    GlobalWorkerOptions: {},
    TextLayer: FakeTextLayer,
    getDocument() {
      const next = env.documentQueue.shift();
      const promise = next ? next.promise : Promise.resolve(makeDocument(env.numPages));
      return {promise, destroy() { env.destroyed++; return Promise.resolve(); }};
    }
  };
  const context = vm.createContext({
    console, setTimeout, clearTimeout, setImmediate,
    IntersectionObserver: FakeIntersectionObserver,
    __loadPdfJs: () => Promise.resolve(pdfjs)
  });
  context.document = {createElement: tag => new FakeNode(tag)};
  context.window = {devicePixelRatio: 1, getSelection: () => env.selection};
  vm.runInContext(source + '\nthis.renderPdfDocument = renderPdfDocument; this.renderPdfPage = renderPdfPage; this.closePdfViewer = closePdfViewer;', context);
  return {env, viewer: context};
}

async function main() {
  // Placeholders, near-only rendering, and far release.
  {
    const {env, viewer} = createHarness();
    const container = new FakeNode('div');
    const ready = [];
    const controller = await viewer.renderPdfDocument(container, 'paper-a', {onReady: info => ready.push(info)});
    assert.ok(controller, 'controller should be returned');
    assert.deepEqual(plain(ready), [{pageCount: 30}]);
    assert.equal(container.style.overflow, 'auto');
    const pages = pagesOf(container);
    assert.equal(pages.length, 30, 'one placeholder per page');
    assert.equal(pages[4].dataset.pageNumber, '5');
    assert.ok(parseFloat(pages[0].style.height) > 0, 'placeholder has a size');
    assert.equal(renderedCount(container), 0, 'nothing renders before the observer reports proximity');
    const io = FakeIntersectionObserver.instances.at(-1);
    assert.equal(io.options.root, container);
    assert.match(io.options.rootMargin, /1500px/);
    assert.equal(io.targets.length, 30);

    fire(io, pages.slice(0, 3), true);
    await flush();
    assert.equal(renderedCount(container), 3, 'near pages render');
    fire(io, [pages[19]], false);
    await flush();
    assert.equal(renderedCount(container), 3, 'far unrendered page stays unrendered');

    fire(io, pages.slice(0, 12), true);
    await flush();
    assert.ok(renderedCount(container) <= 8, 'at most 8 pages keep canvases');
    assert.equal(renderedCount(container), 8);
    assert.equal(pages[8].children.some(child => child.tagName === 'CANVAS'), false, 'the farthest page is not admitted');

    fire(io, pages.slice(0, 3), false);
    await flush();
    assert.equal(pages[0].children.some(child => child.tagName === 'CANVAS'), false, 'far page canvas released');
    assert.equal(pages[0].children.length, 1, 'only the page label remains on a released page');
    assert.ok(renderedCount(container) <= 8);
    await viewer.closePdfViewer();
    assert.ok(io.disconnected, 'closing disconnects the observer');
    assert.equal(renderedCount(container), 0, 'closing releases every canvas');
    assert.ok(env.destroyed >= 1);
  }

  // Scroll-driven current page, debounced onPageChange, and scrollToPage.
  {
    const {viewer} = createHarness();
    const container = new FakeNode('div');
    const changes = [];
    const controller = await viewer.renderPdfDocument(container, 'paper-a', {onPageChange: page => changes.push(page)});
    assert.equal(controller.getCurrentPage(), 1);
    assert.equal(controller.scrollToPage(999, {behavior: 'smooth'}), 30, 'page is clamped to the last page');
    assert.deepEqual(plain(container.lastScroll), {top: topOf(container, 30), behavior: 'smooth'});
    assert.equal(controller.getCurrentPage(), 30);
    await sleep(350);
    assert.deepEqual(changes, [30], 'scrollToPage reports the new page after the debounce');

    controller.scrollToPage(1);
    container.scrollTop = topOf(container, 20);
    container.dispatch('scroll');
    container.scrollTop = topOf(container, 21);
    container.dispatch('scroll');
    container.scrollTop = topOf(container, 20);
    container.dispatch('scroll');
    await sleep(350);
    assert.deepEqual(changes, [30, 20], 'bounces within the debounce window report only the settled page');

    container.dispatch('scroll');
    await sleep(350);
    assert.deepEqual(changes, [30, 20], 'an unchanged page is not reported again');
    assert.equal(controller.getCurrentPage(), 20);
  }

  // Start page and deep link.
  {
    const {viewer} = createHarness();
    const container = new FakeNode('div');
    const controller = await viewer.renderPdfDocument(container, 'paper-a', {startPage: 7});
    assert.equal(controller.getCurrentPage(), 7);
    assert.equal(container.scrollTop, topOf(container, 7));
  }

  // Selection page number comes from the page that holds the selection.
  {
    const {env, viewer} = createHarness();
    const container = new FakeNode('div');
    const selections = [];
    await viewer.renderPdfDocument(container, 'paper-a', {onSelection: (text, page, context) => selections.push({text, page, context})});
    const pages = pagesOf(container);
    const io = FakeIntersectionObserver.instances.at(-1);
    fire(io, pages.slice(1, 3), true);
    await flush();
    const layerFor = number => env.layers.find(layer => layer.container.parentNode === pages[number - 1]);
    const span2 = layerFor(2).span;
    const span3 = layerFor(3).span;
    env.selection = {anchorNode: span2, focusNode: span2, rangeCount: 0, toString: () => '  Some text  '};
    span2.dispatch('mouseup');
    assert.deepEqual(plain(selections), [{text: 'Some text', page: 2, context: {prefix: '', suffix: ''}}]);

    env.selection = {anchorNode: span2, focusNode: span3, rangeCount: 0, toString: () => 'across pages'};
    span2.dispatch('mouseup');
    assert.equal(selections.length, 1, 'selections spanning two pages are ignored');

    env.selection = {anchorNode: span3, focusNode: span3, rangeCount: 0, toString: () => '   '};
    span3.dispatch('mouseup');
    assert.equal(selections.length, 1, 'blank selections are ignored');
  }

  // A document that finishes after a newer viewer started must not render.
  {
    const {env, viewer} = createHarness();
    const oldContainer = new FakeNode('div');
    const newContainer = new FakeNode('div');
    const oldLoad = deferred();
    env.documentQueue.push({promise: oldLoad.promise});
    const older = viewer.renderPdfDocument(oldContainer, 'paper-a', {});
    await flush();
    const newer = viewer.renderPdfDocument(newContainer, 'paper-b', {});
    const newController = await newer;
    assert.ok(newController, 'newer viewer renders');
    oldLoad.resolve({numPages: 5, getPage() { throw new Error('stale document must not load pages'); }});
    assert.equal(await older, null, 'stale viewer resolves to null');
    assert.equal(oldContainer.children.length, 0, 'stale viewer does not write into its container');
    assert.equal(pagesOf(newContainer).length, 30);
  }

  // A page render that finishes after closePdfViewer must not draw.
  {
    const {env, viewer} = createHarness();
    const container = new FakeNode('div');
    await viewer.renderPdfDocument(container, 'paper-a', {});
    const io = FakeIntersectionObserver.instances.at(-1);
    env.holdPages = true;
    fire(io, [pagesOf(container)[0]], true);
    await flush();
    await viewer.closePdfViewer();
    env.heldPages.forEach(held => held.resolve());
    await flush();
    assert.equal(renderedCount(container), 0, 'late page result is discarded after close');
    assert.equal(env.layers.length, 0, 'no text layer is built after close');
  }

  console.log('pdf_viewer_continuous: all checks passed');
}

main().catch(error => { console.error(error); process.exitCode = 1; });
