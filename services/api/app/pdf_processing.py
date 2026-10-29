"""Local PDF inspection and conservative text-quote matching.

Page indices are always zero based. Text returned here is a search aid, not a
faithful reconstruction of columns, tables, equations, or a PDF.js text layer.
No coordinates are inferred, and no network or OCR runs implicitly.
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import base64
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pypdf import PdfReader


class PDFProcessingError(Exception):
    """A PDF could not be inspected; ``code`` is suitable for UI handling."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _image_count(page: Any) -> Optional[int]:
    try:
        # pypdf's page.images covers ordinary images and forms, but not image
        # XObjects embedded in tiling-pattern resources. Historical scans can
        # use this form for the page image and have a separate OCR text layer.
        # Count such resources conservatively; this is not proof the page was
        # scanned and may include unused resources.
        count = len(page.images)
        resources = page.get("/Resources")
        resources = resources.get_object() if resources else {}
        patterns = resources.get("/Pattern")
        patterns = patterns.get_object() if patterns else {}
        seen = set()

        def pattern_images(resource: Any, depth: int = 0) -> int:
            if depth > 16 or len(seen) > 1024:
                raise ValueError("PDF image resource nesting limit exceeded")
            resource = resource.get_object() if resource else {}
            objects = resource.get("/XObject")
            objects = objects.get_object() if objects else {}
            found = 0
            for ref in objects.values():
                key = (getattr(ref, "idnum", None), getattr(ref, "generation", None))
                obj = ref.get_object()
                if key[0] is None:
                    key = id(obj)
                if key in seen:
                    continue
                seen.add(key)
                if obj.get("/Subtype") == "/Image":
                    found += 1
                elif obj.get("/Subtype") == "/Form":
                    found += pattern_images(obj.get("/Resources"), depth + 1)
            return found

        for ref in patterns.values():
            pattern = ref.get_object()
            count += pattern_images(pattern.get("/Resources"))
        return count
    except Exception:
        # Unsupported image encodings should not stop otherwise usable text.
        return None


def inspect_pdf(path: Union[str, Path], max_pages: Optional[int] = None) -> Dict[str, Any]:
    """Inspect a local PDF, returning JSON-serializable metadata and pages.

    Password-protected files are deliberately rejected without attempting to
    store passwords. ``max_pages`` limits extraction, not the reported page
    count; a truncated result is marked partial.
    """
    path = Path(path)
    if max_pages is not None and (not isinstance(max_pages, int) or max_pages < 1):
        raise ValueError("max_pages must be a positive integer")
    try:
        with path.open("rb") as stream:
            header = stream.read(1024)
        if b"%PDF-" not in header:
            raise PDFProcessingError("invalid_pdf", "PDF header was not found")
        digest = _sha256(path)
        reader = PdfReader(str(path), strict=False)
        if reader.is_encrypted:
            # Even an empty-password encrypted document must be explicitly
            # handled, rather than silently claiming encryption is supported.
            raise PDFProcessingError("encrypted", "Encrypted PDFs are not supported")
        page_count = len(reader.pages)
        if page_count == 0:
            raise PDFProcessingError("invalid_pdf", "PDF contains no pages")
    except PDFProcessingError:
        raise
    except FileNotFoundError as exc:
        raise PDFProcessingError("missing_file", "PDF file is missing") from exc
    except PermissionError as exc:
        raise PDFProcessingError("unreadable_file", "PDF file cannot be read") from exc
    except Exception as exc:
        raise PDFProcessingError("invalid_pdf", "PDF could not be opened") from exc

    try:
        # pypdf generates "1", "2", ... even when the PDF defines no page
        # labels. Preserve only explicit PDF labels and never infer print pages.
        labels = reader.page_labels if reader.trailer["/Root"].get("/PageLabels") else []
    except Exception:
        labels = []
    try:
        meta = reader.metadata
        title = str(meta.title) if meta and meta.title else None
        author = str(meta.author) if meta and meta.author else None
    except Exception:
        title = author = None

    pages: List[Dict[str, Any]] = []
    for index in range(min(page_count, max_pages or page_count)):
        page_result: Dict[str, Any] = {
            "page_index": index, "page_label": labels[index] if index < len(labels) else None,
            "text": "", "text_source": "pypdf", "status": "failed",
            "image_count": None, "width": None, "height": None,
            "rotation": None, "crop_box": None, "warnings": [],
        }
        try:
            page = reader.pages[index]
            page_result["width"] = float(page.mediabox.width)
            page_result["height"] = float(page.mediabox.height)
            page_result["crop_box"] = [float(v) for v in page.cropbox]
            page_result["rotation"] = int(page.rotation or 0)
            page_result["image_count"] = _image_count(page)
            page_result["text"] = page.extract_text() or ""
            text = page_result["text"]
            if not text.strip():
                if page_result["image_count"]:
                    page_result["status"] = "image_only"
                    page_result["warnings"].append("Text extraction found no text on a page containing images; OCR may help.")
                else:
                    page_result["status"] = "no_text"
                    page_result["warnings"].append("No extractable text was found; this page may be blank or need OCR.")
            else:
                page_result["status"] = "extracted"
                if page_result["image_count"]:
                    page_result["warnings"].append("This page has image resources; text may include an unverified OCR layer. Compare it with the original.")
                if "\ufffd" in text or "\x00" in text:
                    page_result["warnings"].append("Some characters may be corrupted; check the original page.")
                # Embedded equation/diagram fonts can map glyphs to private
                # Unicode points or non-printing controls. Their meaning is
                # font-specific, so displaying them as ordinary text or
                # silently discarding them would misrepresent the source.
                if any(unicodedata.category(char) == "Co" for char in text):
                    page_result["warnings"].append("Some characters use private font mappings; check symbols against the original page.")
                if any(unicodedata.category(char) == "Cc" and char not in "\t\r\n" for char in text):
                    page_result["warnings"].append("Non-printing control characters were found; check the original page.")
                page_result["warnings"].append("Reading order, tables and equations have not been verified.")
        except Exception:
            # Do not log document text, parser exception messages or paths.
            page_result["warnings"].append("Text extraction failed for this page; the original may still be readable.")
        pages.append(page_result)

    truncated = len(pages) < page_count
    failed = any(p["status"] == "failed" for p in pages)
    return {
        "sha256": digest, "size_bytes": path.stat().st_size, "page_count": page_count,
        "title": title, "author": author, "parser": "pypdf",
        "parser_version": importlib.metadata.version("pypdf"),
        "status": "partial" if failed or truncated else "completed", "truncated": truncated,
        "pages": pages,
    }


_LIGATURES = {"\ufb00": "ff", "\ufb01": "fi", "\ufb02": "fl", "\ufb03": "ffi",
              "\ufb04": "ffl", "\ufb05": "st", "\ufb06": "st"}
_LINE_HYPHEN = re.compile(r"(?<=[A-Za-z\ufb00-\ufb06])-[ \t]*(?:\r\n|\r|\n)[ \t]*(?=[A-Za-z\ufb00-\ufb06])")


def _normalize_with_offsets(text: str, join_line_hyphens: bool = False) -> tuple:
    """Collapse whitespace and expand common typographic Latin ligatures.

    Every expanded character maps to its original Python code-point offset.
    When requested, omit line-break hyphens only for uncertain suggestions;
    whether the hyphen belongs to the word cannot be inferred from text.
    Do not apply broad Unicode compatibility normalization: it can collapse
    meaningful distinctions such as mathematical superscripts.
    """
    chars: List[str] = []
    offsets: List[int] = []
    in_space = False
    # This alternative is only used to find *possible* line-break matches.
    # An ASCII hyphen can also be part of a genuine compound word, so a
    # match obtained by dropping it must never become an ordinary candidate.
    skipped = set()
    if join_line_hyphens:
        for match in _LINE_HYPHEN.finditer(text):
            skipped.update(range(match.start(), match.end()))
    for index, char in enumerate(text):
        if index in skipped:
            continue
        if char.isspace():
            if chars and not in_space:
                chars.append(" ")
                offsets.append(index)
            in_space = True
        else:
            expanded = _LIGATURES.get(char, char)
            chars.extend(expanded)
            offsets.extend([index] * len(expanded))
            in_space = False
    if chars and chars[-1] == " ":
        chars.pop()
        offsets.pop()
    return "".join(chars), offsets


def locate_quote(page_text: str, quote: str, prefix: str = "", suffix: str = "") -> Dict[str, Any]:
    """Find quote candidates on one page, never automatically confirm them.

    Candidate offsets refer only to the supplied Python text, not PDF.js or
    screen coordinates. Context is used only when it matches exactly after
    whitespace and common Latin ligature normalization; otherwise all quote
    matches remain candidates. A possible match requiring a line-break hyphen
    to be removed is kept separately and never becomes an ordinary candidate.
    """
    normalized, offsets = _normalize_with_offsets(page_text)
    needle, _ = _normalize_with_offsets(quote)
    if not needle:
        raise ValueError("quote must contain non-whitespace text")
    before, _ = _normalize_with_offsets(prefix)
    after, _ = _normalize_with_offsets(suffix)
    def find_candidates(haystack: str, mapping: list, possible: bool) -> list:
        candidates = []
        start = 0
        while True:
            found = haystack.find(needle, start)
            if found < 0:
                break
            end = found + len(needle)
            # A ligature expands to several normalized characters that all map
            # to one original code point. Consume the whole original glyph.
            if ((found > 0 and mapping[found] == mapping[found - 1]) or
                    (end < len(mapping) and mapping[end - 1] == mapping[end])):
                start = found + 1
                continue
            original_start, original_end = mapping[found], mapping[end - 1] + 1
            # Do not turn unrelated exact matches into uncertain ones merely
            # because a different part of the page has a line-break hyphen.
            if possible and not _LINE_HYPHEN.search(page_text[original_start:original_end]):
                start = found + 1
                continue
            context_match = ((not before or haystack[:found].rstrip().endswith(before)) and
                             (not after or haystack[end:].lstrip().startswith(after)))
            result = {"start": original_start, "end": original_end, "context_match": context_match}
            if possible:
                result["match_kind"] = "possible_line_hyphenation"
            candidates.append(result)
            start = found + 1
        return candidates

    candidates = find_candidates(normalized, offsets, False)
    if _LINE_HYPHEN.search(page_text):
        joined, joined_offsets = _normalize_with_offsets(page_text, join_line_hyphens=True)
        candidates.extend(find_candidates(joined, joined_offsets, True))
    candidates.sort(key=lambda candidate: (candidate["start"], candidate["end"]))
    context_matches = [candidate for candidate in candidates if candidate["context_match"]]
    context_mismatch = bool(candidates and (before or after) and not context_matches)
    if (before or after) and context_matches:
        candidates = context_matches
    # A unique quote with stale context is not a usable candidate. Keep all
    # positions available for inspection but make the mismatch visible in the
    # persisted status as well as in each candidate's context_match field.
    status = ("not_found" if not candidates else "context_mismatch" if context_mismatch
              else "possible_line_hyphenation" if any(c.get("match_kind") for c in candidates)
              else "candidate" if len(candidates) == 1 else "ambiguous")
    return {"status": status,
            "candidates": candidates, "offset_unit": "python_unicode_codepoint",
            "normalization": "whitespace-latin-ligatures-line-hyphen-suggestions-v4", "verified": False}


def extract_with_docling(path: Union[str, Path]) -> Dict[str, Any]:
    """Opt-in Docling conversion preserving its native document/provenance.

    Run this heavyweight adapter in a separate job with resource/time limits.
    Model availability, OCR behavior and remote services depend on installed
    Docling configuration. This adapter does not translate its coordinates or
    claim page-level completeness.
    """
    try:
        from docling.document_converter import DocumentConverter
    except ImportError as exc:
        raise PDFProcessingError("adapter_unavailable", "Docling is not installed") from exc
    try:
        result = DocumentConverter().convert(str(path))
        status = str(result.status)
        return {"parser": "docling", "parser_version": importlib.metadata.version("docling"),
                "status": status, "document": result.document.export_to_dict()}
    except Exception as exc:
        raise PDFProcessingError("adapter_failed", "Docling conversion failed") from exc


def ocr_page(path: Union[str, Path], page_index: int, language: str = "eng") -> Dict[str, Any]:
    """Opt-in local OCR for one page; needs pypdfium2, pytesseract and Tesseract.

    OCR text is explicitly labeled and cannot supply verified coordinates.
    """
    if page_index < 0:
        raise ValueError("page_index must be nonnegative")
    try:
        import pypdfium2 as pdfium
        import pytesseract
    except ImportError as exc:
        raise PDFProcessingError("adapter_unavailable", "Local OCR dependencies are not installed") from exc
    document = None
    page = None
    bitmap = None
    try:
        document = pdfium.PdfDocument(str(path))
        if page_index >= len(document):
            raise PDFProcessingError("page_out_of_range", "Page index is outside the document")
        page = document[page_index]
        bitmap = page.render(scale=2)
        text = pytesseract.image_to_string(bitmap.to_pil(), lang=language)
        return {"page_index": page_index, "text": text, "text_source": "ocr_tesseract",
                "status": "ocr_unverified", "language": language}
    except PDFProcessingError:
        raise
    except Exception as exc:
        raise PDFProcessingError("adapter_failed", "Local OCR failed; check the engine and language data") from exc
    finally:
        for item in (bitmap, page, document):
            if item is not None:
                try:
                    item.close()
                except Exception:
                    pass


# Windows PowerShell 5 exposes WinRT without additional Python dependencies.
# The image and language are passed as environment variables, not interpolated
# into code. Its only model output is the recognized text, returned as JSON.
_WINDOWS_OCR_SCRIPT = r'''
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Storage.StorageFile, Windows.Storage, ContentType=WindowsRuntime]
$null = [Windows.Storage.FileAccessMode, Windows.Storage, ContentType=WindowsRuntime]
$null = [Windows.Storage.Streams.IRandomAccessStream, Windows.Storage.Streams, ContentType=WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics.Imaging, ContentType=WindowsRuntime]
$null = [Windows.Graphics.Imaging.SoftwareBitmap, Windows.Graphics.Imaging, ContentType=WindowsRuntime]
$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType=WindowsRuntime]
$null = [Windows.Media.Ocr.OcrResult, Windows.Foundation, ContentType=WindowsRuntime]
$null = [Windows.Globalization.Language, Windows.Globalization, ContentType=WindowsRuntime]
function Await-Result($operation, $resultType) {
  $method = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and $_.IsGenericMethod -and $_.GetParameters().Count -eq 1 -and
    $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
  } | Select-Object -First 1
  $task = $method.MakeGenericMethod($resultType).Invoke($null, @($operation))
  $task.Wait()
  return $task.Result
}
$stream = $null
$pixels = $null
try {
  $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage((New-Object Windows.Globalization.Language($env:EASYRESEARCH_OCR_LANGUAGE)))
  if ($null -eq $engine) { exit 30 }
  $file = Await-Result ([Windows.Storage.StorageFile]::GetFileFromPathAsync($env:EASYRESEARCH_OCR_IMAGE)) ([Windows.Storage.StorageFile])
  $stream = Await-Result ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
  $decoder = Await-Result ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
  $pixels = Await-Result ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
  $result = Await-Result ($engine.RecognizeAsync($pixels)) ([Windows.Media.Ocr.OcrResult])
  @{ text = $result.Text; language = $engine.RecognizerLanguage.LanguageTag } | ConvertTo-Json -Compress
} catch { exit 31 }
finally {
  if ($null -ne $pixels) { $pixels.Dispose() }
  if ($null -ne $stream) { $stream.Dispose() }
}
'''


def ocr_page_windows(path: Union[str, Path], page_index: int, language: str = "ko",
                     timeout: int = 45, max_dimension: int = 2000) -> Dict[str, Any]:
    """Opt-in Windows OCR of one rasterized PDF page, without network access.

    Requires Windows PowerShell 5, an installed Windows OCR language and a
    locally available Poppler pdftoppm. Return text is explicitly unverified.
    The renderer scales the longest image dimension down to ``max_dimension``;
    the total timeout covers both rendering and OCR. Run as a background job.
    """
    if isinstance(page_index, bool) or not isinstance(page_index, int) or page_index < 0:
        raise ValueError("page_index must be a nonnegative integer")
    if not isinstance(language, str) or not re.fullmatch(r"[A-Za-z0-9-]{2,35}", language):
        raise ValueError("language must be a language tag")
    if isinstance(timeout, bool) or not isinstance(timeout, int) or not 1 <= timeout <= 120:
        raise ValueError("timeout must be between 1 and 120 seconds")
    if isinstance(max_dimension, bool) or not isinstance(max_dimension, int) or not 256 <= max_dimension <= 3000:
        raise ValueError("max_dimension must be between 256 and 3000")
    if os.name != "nt":
        raise PDFProcessingError("adapter_unavailable", "Windows OCR is only available on Windows")
    renderer = shutil.which("pdftoppm")
    powershell = shutil.which("powershell.exe")
    if not renderer or not powershell:
        raise PDFProcessingError("adapter_unavailable", "Windows PowerShell or Poppler pdftoppm is not available")
    started = time.monotonic()
    try:
        reader = PdfReader(str(path), strict=False)
        if reader.is_encrypted:
            raise PDFProcessingError("encrypted", "Encrypted PDFs are not supported")
        if page_index >= len(reader.pages):
            raise PDFProcessingError("page_out_of_range", "Page index is outside the document")
    except PDFProcessingError:
        raise
    except FileNotFoundError as exc:
        raise PDFProcessingError("missing_file", "PDF file is missing") from exc
    except Exception as exc:
        raise PDFProcessingError("invalid_pdf", "PDF could not be opened") from exc
    try:
        with tempfile.TemporaryDirectory(prefix="easyresearch-ocr-") as directory:
            prefix = str(Path(directory) / "page")
            create_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            remaining = timeout - (time.monotonic() - started)
            if remaining <= 0:
                raise PDFProcessingError("adapter_timeout", "Windows OCR exceeded the time limit")
            render = subprocess.run([renderer, "-f", str(page_index + 1), "-l", str(page_index + 1),
                                     "-singlefile", "-scale-to", str(max_dimension), "-png", str(path), prefix],
                                    capture_output=True, timeout=remaining, creationflags=create_flags)
            image = prefix + ".png"
            if render.returncode != 0 or not Path(image).is_file():
                raise PDFProcessingError("adapter_failed", "PDF page rendering failed")
            remaining = timeout - (time.monotonic() - started)
            if remaining <= 0:
                raise PDFProcessingError("adapter_timeout", "Windows OCR exceeded the time limit")
            env = os.environ.copy()
            env["EASYRESEARCH_OCR_IMAGE"] = image
            env["EASYRESEARCH_OCR_LANGUAGE"] = language
            encoded = base64.b64encode(_WINDOWS_OCR_SCRIPT.encode("utf-16le")).decode("ascii")
            result = subprocess.run([powershell, "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
                                    capture_output=True, timeout=remaining, env=env, creationflags=create_flags)
            if result.returncode == 30:
                raise PDFProcessingError("language_unavailable", "Requested Windows OCR language is not installed")
            if result.returncode != 0:
                raise PDFProcessingError("adapter_failed", "Windows OCR failed")
            if len(result.stdout) > 1024 * 1024:
                raise PDFProcessingError("adapter_failed", "Windows OCR result is too large")
            output = json.loads(result.stdout.decode("utf-8-sig"))
            if not isinstance(output, dict) or not isinstance(output.get("text"), str) or not isinstance(output.get("language"), str):
                raise PDFProcessingError("adapter_failed", "Windows OCR returned an invalid result")
            return {"page_index": page_index, "text": output["text"], "text_source": "ocr_windows",
                    "status": "ocr_unverified", "language": output["language"],
                    "engine": "windows_media_ocr", "renderer": "poppler_pdftoppm", "max_dimension": max_dimension}
    except PDFProcessingError:
        raise
    except subprocess.TimeoutExpired as exc:
        raise PDFProcessingError("adapter_timeout", "Windows OCR exceeded the time limit") from exc
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise PDFProcessingError("adapter_failed", "Windows OCR failed") from exc
