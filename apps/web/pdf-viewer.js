// PDF.js 6.2.108; selection is tied to the one visible physical PDF page.
let pdfjs;
let current = {id: null, task: null, document: null, generation: 0};

export async function renderPdfPage(container, paperId, pageNumber, onSelection, zoom = 1) {
  const generation = ++current.generation;
  try {
    if (!pdfjs) {
      const module = await import('/assets/vendor/pdfjs/pdf.min.mjs?v=6.2.108');
      if (generation !== current.generation || !container.isConnected) return;
      pdfjs = module;
      pdfjs.GlobalWorkerOptions.workerSrc = '/assets/vendor/pdfjs/pdf.worker.min.mjs?v=6.2.108';
    }
    if (current.id !== paperId) {
      const previousTask = current.task;
      current.id = paperId;
      current.document = null;
      current.task = pdfjs.getDocument({
        url: `/api/papers/${encodeURIComponent(paperId)}/file`,
        // The app displays pages and text only; do not activate XFA forms or
        // generated evaluation code for document content.
        enableXfa: false, isEvalSupported: false,
        cMapUrl: '/assets/vendor/pdfjs/cmaps/', cMapPacked: true,
        standardFontDataUrl: '/assets/vendor/pdfjs/standard_fonts/',
        wasmUrl: '/assets/vendor/pdfjs/wasm/', iccUrl: '/assets/vendor/pdfjs/iccs/'
      });
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

export async function closePdfViewer() {
  current.generation++;
  const task = current.task;
  current = {id: null, task: null, document: null, generation: current.generation};
  if (task) await task.destroy();
}
