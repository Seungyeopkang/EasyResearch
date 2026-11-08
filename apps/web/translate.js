// Translation through the browser's built-in Translator API (Chrome 138+).
// This module has no network code of its own. The browser runs and, on first
// use, downloads its translation model. Translated text is never stored here.

const MAX_CHUNK_CHARS = 900;
const UNSUPPORTED_MESSAGE = '이 브라우저는 내장 번역을 지원하지 않습니다. 최신 Chrome 또는 Edge에서 열어 주세요.';
const AVAILABILITY_STATES = new Set(['available', 'downloadable', 'downloading', 'unavailable']);
const pairs = new Map();

function translatorApi() {
  return typeof self !== 'undefined' ? self.Translator : undefined;
}

// Returns 'available' | 'downloadable' | 'downloading' | 'unavailable' | 'unsupported'.
export async function translatorAvailability(source = 'en', target = 'ko') {
  const api = translatorApi();
  if (!api || typeof api.availability !== 'function') return 'unsupported';
  try {
    // Some embedded Chromium builds expose the API but never settle (no
    // on-device model service). Report that instead of waiting forever.
    const request = api.availability({sourceLanguage: source, targetLanguage: target});
    let timer;
    const timeout = typeof setTimeout === 'function'
      ? new Promise(resolve => { timer = setTimeout(() => resolve('timeout'), 6000); })
      : null;
    const state = await (timeout ? Promise.race([request, timeout]) : request);
    if (timer !== undefined && typeof clearTimeout === 'function') clearTimeout(timer);
    if (state === 'timeout') return 'timeout';
    return AVAILABILITY_STATES.has(state) ? state : 'unavailable';
  } catch {
    return 'unavailable';
  }
}

// Translates text paragraph by paragraph. Long paragraphs are split on sentence
// boundaries into chunks of at most MAX_CHUNK_CHARS. Chunks are translated one
// at a time, in order, and rejoined with the original paragraph breaks.
export async function translateText(text, {source = 'en', target = 'ko', onProgress} = {}) {
  const api = translatorApi();
  if (!api || typeof api.create !== 'function') throw new Error(UNSUPPORTED_MESSAGE);
  const input = normalizePdfText(String(text ?? ''));
  if (!input) throw new Error('번역할 텍스트가 없습니다.');
  const paragraphs = input.split('\n\n').map(paragraph => chunksOf(paragraph));
  // The create call is made synchronously so that a click handler's user
  // activation is still available when the browser needs to download a model.
  let translator;
  try {
    translator = await getTranslator(source, target, onProgress);
  } catch (error) {
    throw new Error(creationMessage(error, source, target));
  }
  const paragraphOutputs = [];
  for (const chunks of paragraphs) {
    const translated = [];
    for (const chunk of chunks) {
      try {
        translated.push(await translator.translate(chunk));
      } catch (error) {
        throw new Error(`번역 중 오류가 났습니다: ${error?.message || '다시 시도해 주세요.'}`);
      }
    }
    paragraphOutputs.push(translated.join(' '));
  }
  return paragraphOutputs.join('\n\n');
}

function getTranslator(source, target, onProgress) {
  const key = `${source}>${target}`;
  if (!pairs.has(key)) {
    const promise = translatorApi().create({
      sourceLanguage: source,
      targetLanguage: target,
      monitor(monitor) {
        monitor.addEventListener('downloadprogress', event => onProgress?.(event.loaded));
      }
    });
    pairs.set(key, promise);
    promise.catch(() => pairs.delete(key));
  }
  return pairs.get(key);
}

function creationMessage(error, source, target) {
  if (error?.name === 'NotAllowedError') return '번역 모델을 내려받으려면 번역 버튼을 다시 눌러 주세요.';
  if (error?.name === 'NotSupportedError') return `이 언어 쌍(${source}→${target})은 이 기기에서 번역할 수 없습니다.`;
  return `번역기를 준비하지 못했습니다: ${error?.message || '잠시 후 다시 시도해 주세요.'}`;
}

// Splits one paragraph into chunks of at most MAX_CHUNK_CHARS, keeping order.
function chunksOf(paragraph) {
  const chunks = [];
  let current = '';
  const flush = () => {
    if (current) chunks.push(current);
    current = '';
  };
  // A lookbehind keeps the punctuation; nothing else in the text is dropped.
  for (const raw of paragraph.split(/(?<=[.!?。])\s+/)) {
    let sentence = raw.trim();
    while (sentence.length > MAX_CHUNK_CHARS) {
      let cut = sentence.lastIndexOf(' ', MAX_CHUNK_CHARS);
      if (cut < MAX_CHUNK_CHARS / 2) cut = MAX_CHUNK_CHARS;
      flush();
      chunks.push(sentence.slice(0, cut).trim());
      sentence = sentence.slice(cut).trim();
    }
    if (!sentence) continue;
    if (current && current.length + 1 + sentence.length > MAX_CHUNK_CHARS) flush();
    current = current ? `${current} ${sentence}` : sentence;
  }
  flush();
  return chunks;
}

// Cleans PDF text for display or translation only. Hard line breaks inside a
// paragraph are joined, and a word split by a line-end hyphen is rejoined when
// the next line starts with a lowercase letter. Paragraph breaks are kept as
// blank lines. Stored evidence must keep the extracted text unchanged.
export function normalizePdfText(text) {
  return String(text ?? '')
    .replace(/\r\n?/g, '\n')
    .replace(/ /g, ' ')
    .split(/\n\s*\n+/)
    .map(joinParagraphLines)
    .filter(Boolean)
    .join('\n\n');
}

function joinParagraphLines(paragraph) {
  const lines = paragraph.split('\n').map(line => line.replace(/\s+/g, ' ').trim()).filter(Boolean);
  let out = '';
  for (const line of lines) {
    if (!out) {
      out = line;
    } else if (/\p{L}-$/u.test(out) && /^\p{Ll}/u.test(line)) {
      out = out.slice(0, -1) + line;
    } else {
      out = `${out} ${line}`;
    }
  }
  return out;
}
