'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '..', '..', 'apps', 'web', 'translate.js'), 'utf8')
  .replace(/^export /gm, '');
const UNSUPPORTED = '이 브라우저는 내장 번역을 지원하지 않습니다. 최신 Chrome 또는 Edge에서 열어 주세요.';

function load(translatorValue) {
  const context = vm.createContext({console, Error, Promise, String, Number});
  context.self = context;
  if (translatorValue !== undefined) context.Translator = translatorValue;
  vm.runInContext(source + '\nthis.translatorAvailability = translatorAvailability; this.translateText = translateText; this.normalizePdfText = normalizePdfText;', context);
  return context;
}

// Fake Translator that records each translate() input and emits download progress.
function fakeTranslator(options = {}) {
  const inputs = [];
  let created = 0;
  const api = {
    inputs,
    get created() { return created; },
    availability: async () => options.availability ?? 'available',
    create(config) {
      created++;
      if (options.createError) return Promise.reject(options.createError);
      const listeners = [];
      config.monitor?.({addEventListener(type, fn) { if (type === 'downloadprogress') listeners.push(fn); }});
      listeners.forEach(fn => fn({loaded: 0.25}));
      listeners.forEach(fn => fn({loaded: 1}));
      return Promise.resolve({
        translate(text) {
          inputs.push(text);
          if (options.translateError) return Promise.reject(options.translateError);
          return Promise.resolve(`KO(${text})`);
        }
      });
    }
  };
  return api;
}

async function main() {
  // Unsupported browser.
  {
    const context = load(undefined);
    assert.equal(await context.translatorAvailability('en', 'ko'), 'unsupported');
    await assert.rejects(() => context.translateText('Hello world.'), {message: UNSUPPORTED});
  }

  // Availability mapping.
  for (const state of ['available', 'downloadable', 'downloading', 'unavailable']) {
    const context = load(fakeTranslator({availability: state}));
    assert.equal(await context.translatorAvailability(), state);
  }
  {
    const context = load(fakeTranslator({availability: 'strange-state'}));
    assert.equal(await context.translatorAvailability('en', 'ko'), 'unavailable');
    const throwing = {availability: async () => { throw new Error('boom'); }};
    assert.equal(await load(throwing).translatorAvailability(), 'unavailable');
    assert.equal(await load({create() {}}).translatorAvailability(), 'unsupported', 'missing availability() is unsupported');
  }

  // Chunking: each request is at most 900 characters, order is kept, paragraphs stay separate.
  {
    const api = fakeTranslator();
    const context = load(api);
    const sentences = [];
    for (let i = 0; i < 120; i++) sentences.push(`Sentence number ${i} explains the method in plain words.`);
    const long = sentences.join(' ');
    const progress = [];
    const output = await context.translateText(`${long}\n\nShort second paragraph.`, {onProgress: value => progress.push(value)});
    assert.ok(api.inputs.length > 3, 'long text is split');
    for (const input of api.inputs) assert.ok(input.length <= 900, `chunk length ${input.length} exceeds 900`);
    assert.equal(api.inputs.join(' '), `${long} Short second paragraph.`, 'chunks keep the original text in order');
    assert.equal(api.inputs.at(-1), 'Short second paragraph.');
    const paragraphs = output.split('\n\n');
    assert.equal(paragraphs.length, 2, 'paragraph breaks are kept');
    assert.ok(paragraphs[0].startsWith('KO(Sentence number 0 '), 'translation order matches input order');
    assert.equal(paragraphs[1], 'KO(Short second paragraph.)');
    assert.deepEqual(progress, [0.25, 1], 'download progress is reported as loaded fraction');
  }

  // Oversized sentence without spaces is still cut to the limit.
  {
    const api = fakeTranslator();
    const context = load(api);
    await context.translateText('x'.repeat(2500));
    assert.deepEqual(api.inputs.map(input => input.length), [900, 900, 700]);
  }

  // The translator is created once per language pair.
  {
    const api = fakeTranslator();
    const context = load(api);
    await context.translateText('One.');
    await context.translateText('Two.');
    assert.equal(api.created, 1);
  }

  // Error messages.
  {
    const notSupported = Object.assign(new Error('nope'), {name: 'NotSupportedError'});
    await assert.rejects(() => load(fakeTranslator({createError: notSupported})).translateText('Hi.'),
      error => error.message.includes('이 기기에서 번역할 수 없습니다'));
    const activation = Object.assign(new Error('gesture'), {name: 'NotAllowedError'});
    await assert.rejects(() => load(fakeTranslator({createError: activation})).translateText('Hi.'),
      error => error.message.includes('다시 눌러'));
    await assert.rejects(() => load(fakeTranslator({translateError: new Error('bad')})).translateText('Hi.'),
      error => error.message.startsWith('번역 중 오류가 났습니다'));
    await assert.rejects(() => load(fakeTranslator()).translateText('   \n\n  '),
      error => error.message === '번역할 텍스트가 없습니다.');
  }

  // normalizePdfText: display and translation input only.
  {
    const context = load(fakeTranslator());
    assert.equal(context.normalizePdfText('We propose an optimi-\nzation method\nthat is fast.\n\nNext para.'),
      'We propose an optimization method that is fast.\n\nNext para.');
    assert.equal(context.normalizePdfText('Table 1 lists\r\nTHE-\r\nRESULTS here'), 'Table 1 lists THE- RESULTS here',
      'a hyphen before an uppercase line start is kept');
    assert.equal(context.normalizePdfText('  spaced   out \t text  '), 'spaced out text');
    assert.equal(context.normalizePdfText(''), '');
    assert.equal(context.normalizePdfText('\n\n\n'), '');
  }

  console.log('translate_module: all checks passed');
}

main().catch(error => { console.error(error); process.exitCode = 1; });
