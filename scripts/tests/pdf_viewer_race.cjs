'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '..', '..', 'apps', 'web', 'pdf-viewer.js'), 'utf8')
  .replace("import('/assets/vendor/pdfjs/pdf.min.mjs?v=6.2.108')", '__loadPdfJs()')
  .replaceAll('export async function', 'async function');

function deferred() {
  let resolve;
  const promise = new Promise(done => { resolve = done; });
  return {promise, resolve};
}

function setup(loader) {
  const context = vm.createContext({__loadPdfJs: loader, console});
  vm.runInContext(source + '\nthis.render = renderPdfPage; this.close = closePdfViewer; this.selectionContext = selectionContext;', context);
  return context;
}

async function main() {
  const selectionTest = setup(() => Promise.resolve({}));
  const start = {}, end = {};
  const layer = {contains(node) { return node === start || node === end; }};
  const range = {startContainer: start, endContainer: end, startOffset: 3, endOffset: 4,
    cloneRange() { return {selectNodeContents() {}, setEnd(node, offset) { assert.equal(node, start); assert.equal(offset, 3); this.value = 'a'.repeat(150); },
      setStart(node, offset) { assert.equal(node, end); assert.equal(offset, 4); this.value = 'b'.repeat(150); }, toString() { return this.value; }}; }};
  const context = selectionTest.selectionContext({rangeCount: 1, getRangeAt() { return range; }}, layer);
  assert.equal(context.prefix, 'a'.repeat(120));
  assert.equal(context.suffix, 'b'.repeat(120));
  assert.equal(selectionTest.selectionContext({rangeCount: 0}, layer).prefix, '');
  assert.equal(selectionTest.selectionContext({rangeCount: 1, getRangeAt() { throw Error('bad range'); }}, layer).suffix, '');
  assert.equal(selectionTest.selectionContext({rangeCount: 1, getRangeAt() { return range; }}, {contains() { return false; }}).prefix, '');

  const loading = deferred();
  let created = 0;
  const first = setup(() => loading.promise);
  const pending = first.render({isConnected: true}, 'paper-a', 1, () => {});
  await first.close();
  loading.resolve({GlobalWorkerOptions: {}, getDocument() { created++; }});
  await pending;
  assert.equal(created, 0, 'closing during module import must not create a new document task');

  const previousDestroyed = deferred();
  const firstDocument = deferred();
  let pageAccesses = 0;
  const tasks = [];
  const pdfjs = {GlobalWorkerOptions: {}, getDocument() {
    const n = tasks.length;
    const task = {promise: n === 0 ? firstDocument.promise : Promise.resolve({}), destroyed: false,
      destroy() { this.destroyed = true; return n === 0 ? previousDestroyed.promise : Promise.resolve(); }};
    tasks.push(task);
    return task;
  }};
  const second = setup(() => Promise.resolve(pdfjs));
  const oldContainer = {isConnected: true};
  const newContainer = {isConnected: true};
  const older = second.render(oldContainer, 'paper-a', 1, () => {});
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(tasks.length, 1, oldContainer.textContent || 'first document should start');
  const newer = second.render(newContainer, 'paper-b', 1, () => {});
  await new Promise(resolve => setImmediate(resolve));
  await second.close();
  previousDestroyed.resolve();
  firstDocument.resolve({numPages: 1, getPage() { pageAccesses++; }});
  await Promise.all([older, newer]);
  assert.equal(tasks.length, 2);
  assert.ok(tasks.every(task => task.destroyed), 'both document tasks should be closed');
  assert.equal(pageAccesses, 0, 'stale documents must not render into a newer view');
}

main().catch(error => { console.error(error); process.exitCode = 1; });
