'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '..', '..', 'apps', 'web', 'app.js'), 'utf8');
const start = source.indexOf('const evidenceDraftSession =');
const end = source.indexOf('function extractionWarning(', start);
assert.ok(start > 0 && end > start);
const importStart = source.indexOf('function importActionLabel(');
const importEnd = source.indexOf('\nfunction uploadDialog(', importStart);
assert.ok(importStart > 0 && importEnd > importStart);
const importContext = vm.createContext({});
vm.runInContext(source.slice(importStart, importEnd) + '\nthis.label=importActionLabel;', importContext);
assert.match(importContext.label({import_action: 'created_paper', duplicate: true}), /새 논문/);
assert.match(importContext.label({import_action: 'linked_existing', duplicate: true}), /프로젝트에 연결/);
assert.match(importContext.label({import_action: 'already_linked', duplicate: true}), /이미 연결/);
assert.match(importContext.label({import_action: 'attached_pdf', duplicate: false}), /PDF를 연결/);
assert.match(importContext.label({import_action: 'already_attached', duplicate: true}), /이미 연결/);

const store = new Map();
const localStorage = {
  get length() { return store.size; },
  key(i) { return [...store.keys()][i] ?? null; },
  getItem(k) { return store.has(k) ? store.get(k) : null; },
  setItem(k, v) { store.set(k, String(v)); },
  removeItem(k) { store.delete(k); }
};
function tab(id) {
  const nodes = {};
  for (const name of ['evidence-form','evidence-page','quote','note','verify-original','capture-method','draft-info','evidence-draft-recovery','evidence-draft-list','evidence-draft-recover','evidence-draft-delete']) {
    nodes[name] = {value: '', checked: false, dataset: {}, options: [], hidden: true, append(option) { this.options.push(option); option.remove = () => { this.options.splice(this.options.indexOf(option), 1); }; if (!this.value) this.value = option.value; }};
  }
  const context = vm.createContext({crypto: {randomUUID: () => id}, localStorage, document: {createElement: () => ({})},
    $: selector => nodes[selector.slice(1)], state: {projectId: 'project', workspaceScope: 'scope', drafts: {}},
    notify() {}, confirm() { return true; }, error(err) { throw err; }});
  vm.runInContext(source.slice(start, end) + '\nthis.save=saveEvidenceDraft;this.restore=restoreEvidenceDraft;this.clear=clearEvidenceDraft;this.key=draftKey;this.base=draftBaseKey;this.canSaveOcr=canSaveOcrDraft;', context);
  return {context, nodes};
}
const a = tab('a'), b = tab('b');
a.nodes.quote.value = 'first'; a.nodes['evidence-page'].value = '1'; a.nodes['evidence-form'].dataset.prefix = 'before';
a.nodes['evidence-form'].dataset.ocrSourceJobId = 'old-ocr';
a.context.save('paper');
b.nodes.quote.value = 'second'; b.nodes['evidence-page'].value = '2'; b.context.save('paper');
assert.notEqual(a.context.key('paper'), b.context.key('paper'));
assert.equal(store.size, 2);
assert.equal(JSON.parse(store.get(a.context.key('paper'))).prefix, 'before');

const c = tab('new-load');
c.context.restore('paper');
assert.equal(c.nodes['evidence-draft-recovery'].hidden, false);
assert.equal(c.nodes['evidence-draft-list'].options.length, 2);
c.nodes['evidence-draft-list'].value = a.context.key('paper');
c.nodes['evidence-draft-recover'].onclick();
assert.equal(c.nodes.quote.value, 'first');
assert.equal(c.nodes['evidence-form'].dataset.prefix, 'before');
assert.equal(c.nodes['evidence-form'].dataset.ocrSourceJobId, 'old-ocr');
c.nodes['evidence-form'].dataset.ocrJobId = 'new-ocr';
assert.equal(c.context.canSaveOcr(c.nodes['evidence-form'], 1, 1), false, 'new OCR must not silently replace a draft source');
c.nodes['evidence-form'].dataset.ocrJobId = 'old-ocr';
assert.equal(c.context.canSaveOcr(c.nodes['evidence-form'], 1, 1), true);
assert.equal(c.context.canSaveOcr(c.nodes['evidence-form'], 2, 1), false);
assert.equal(store.size, 3, 'recovery copies instead of deleting another window draft');
c.context.clear('paper');
assert.equal(store.size, 2, 'saving or clearing one window must not erase other drafts');

store.set(a.context.base('legacy-paper'), JSON.stringify({page: '3', quote: 'legacy'}));
const legacy = tab('legacy-reader'); legacy.context.restore('legacy-paper');
assert.equal(legacy.nodes['evidence-draft-list'].options.length, 1);
legacy.nodes['evidence-draft-recover'].onclick();
assert.equal(legacy.nodes.quote.value, 'legacy');
assert.ok(store.has(a.context.base('legacy-paper')));
legacy.nodes['evidence-draft-delete'].onclick();
assert.equal(store.has(a.context.base('legacy-paper')), false);
assert.ok(store.has(legacy.context.key('legacy-paper')), 'explicitly deleting an old draft must preserve the recovered copy');
