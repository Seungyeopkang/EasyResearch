"""Synthetic, locally generated PDF regression fixtures; no third-party PDFs."""
import io
import tempfile
import unittest
import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image, ImageDraw, ImageFont
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

from app.pdf_processing import PDFProcessingError, _image_count, inspect_pdf, locate_quote, ocr_page_windows


def make_fixture(path):
    """Four pages: two columns, table, equation and image-only scan."""
    pdf = canvas.Canvas(str(path), pagesize=(612, 792))
    pdf.setTitle("Synthetic research fixture")
    pdf.drawString(45, 745, "LEFT COLUMN first finding")
    pdf.drawString(45, 725, "LEFT COLUMN second finding")
    pdf.drawString(325, 745, "RIGHT COLUMN first finding")
    pdf.drawString(325, 725, "RIGHT COLUMN second finding")
    pdf.showPage()
    for row, values in enumerate((("Method", "Score"), ("Baseline", "0.75"), ("Proposed", "0.90"))):
        for column, value in enumerate(values):
            pdf.drawString(70 + column * 140, 720 - row * 30, value)
    pdf.showPage()
    pdf.drawString(70, 700, "Equation: E = m c^2")
    pdf.showPage()
    image = Image.new("RGB", (600, 200), "white")
    ImageDraw.Draw(image).text((30, 80), "SCANNED FINDING", fill="black")
    image_data = io.BytesIO()
    image.save(image_data, format="PNG")
    image_data.seek(0)
    pdf.drawImage(ImageReader(image_data), 40, 450, width=500, height=180)
    pdf.showPage()
    pdf.save()


class PDFProcessingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "fixture.pdf"
        make_fixture(self.path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_content_and_exact_physical_pages(self):
        result = inspect_pdf(self.path)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["page_count"], 4)
        self.assertEqual(result["title"], "Synthetic research fixture")
        self.assertEqual([p["page_index"] for p in result["pages"]], [0, 1, 2, 3])
        self.assertIsNone(result["pages"][0]["page_label"])
        self.assertIn("LEFT COLUMN first finding", result["pages"][0]["text"])
        self.assertIn("RIGHT COLUMN second finding", result["pages"][0]["text"])
        self.assertIn("0.90", result["pages"][1]["text"])
        self.assertIn("E = m c^2", result["pages"][2]["text"])
        self.assertEqual(result["pages"][3]["status"], "image_only")
        self.assertEqual(result["pages"][3]["text"], "")
        self.assertTrue(result["pages"][3]["image_count"])
        self.assertEqual(len(result["sha256"]), 64)

    def test_quotes_and_context_are_candidates_not_verified_coordinates(self):
        page = "first duplicate text end. second duplicate\n text final."
        ambiguous = locate_quote(page, "duplicate text")
        self.assertEqual(ambiguous["status"], "ambiguous")
        self.assertEqual(len(ambiguous["candidates"]), 2)
        match = locate_quote(page, "duplicate text", prefix="second", suffix="final.")
        self.assertEqual(match["status"], "candidate")
        candidate = match["candidates"][0]
        self.assertEqual(page[candidate["start"]:candidate["end"]], "duplicate\n text")
        self.assertFalse(match["verified"])
        stale = locate_quote(page, "duplicate text", prefix="missing")
        self.assertEqual(stale["status"], "context_mismatch")
        self.assertFalse(any(item["context_match"] for item in stale["candidates"]))
        single_stale = locate_quote("the unique finding ends", "unique finding", prefix="not here")
        self.assertEqual(single_stale["status"], "context_mismatch")
        self.assertEqual(len(single_stale["candidates"]), 1)
        self.assertEqual(locate_quote(page, "unknown")["status"], "not_found")
        with self.assertRaises(ValueError):
            locate_quote(page, "  ")

    def test_partial_and_bad_files(self):
        partial = inspect_pdf(self.path, max_pages=2)
        self.assertEqual(partial["status"], "partial")
        self.assertEqual(partial["page_count"], 4)
        self.assertEqual(len(partial["pages"]), 2)
        bad = Path(self.tmp.name) / "bad.pdf"
        bad.write_bytes(b"not a PDF")
        with self.assertRaises(PDFProcessingError) as invalid:
            inspect_pdf(bad)
        self.assertEqual(invalid.exception.code, "invalid_pdf")
        with self.assertRaises(PDFProcessingError) as missing:
            inspect_pdf(Path(self.tmp.name) / "missing.pdf")
        self.assertEqual(missing.exception.code, "missing_file")

    def test_warns_when_extraction_has_private_font_glyphs_or_controls(self):
        from pypdf._page import PageObject
        with patch.object(PageObject, "extract_text", return_value="Formula \uf8ee 1\x01 + 2"):
            result = inspect_pdf(self.path, max_pages=1)
        page = result["pages"][0]
        self.assertEqual(page["text"], "Formula \uf8ee 1\x01 + 2")
        self.assertTrue(any("private font" in warning for warning in page["warnings"]))
        self.assertTrue(any("control" in warning for warning in page["warnings"]))

    def test_detects_image_inside_tiling_pattern_resources(self):
        from pypdf.generic import DictionaryObject, NameObject
        image = DictionaryObject({NameObject("/Subtype"): NameObject("/Image")})
        objects = DictionaryObject({NameObject("/Img"): image})
        resources = DictionaryObject({NameObject("/XObject"): objects})
        pattern = DictionaryObject({NameObject("/Resources"): resources})
        page_resources = DictionaryObject({NameObject("/Pattern"): DictionaryObject({NameObject("/P0"): pattern})})
        page = SimpleNamespace(images=[], get=lambda name: page_resources if name == "/Resources" else None)
        self.assertEqual(_image_count(page), 1)

    def test_typographic_ligature_expansion_preserves_original_offsets(self):
        page = "office o\ufb03ce \ufb01nding coe\ufb03cient E=mc\u00b2"
        ambiguous = locate_quote(page, "office")
        self.assertEqual(ambiguous["status"], "ambiguous")
        match = locate_quote(page, "office finding coefficient", prefix="office")
        self.assertEqual(match["status"], "candidate")
        candidate = match["candidates"][0]
        self.assertEqual(page[candidate["start"]:candidate["end"]], "o\ufb03ce \ufb01nding coe\ufb03cient")
        self.assertEqual(locate_quote(page, "E=mc2")["status"], "not_found")
        self.assertEqual(locate_quote(page, "E=mc\u00b2")["status"], "candidate")

    def test_quote_never_matches_only_part_of_a_ligature(self):
        # Each result must span full original glyphs, even though the
        # normalized comparison expands a single ligature to multiple letters.
        page = "\ufb01 f \ufb03 ffi"
        result = locate_quote(page, "f")
        self.assertEqual(result["status"], "ambiguous")
        self.assertEqual([page[c["start"]:c["end"]] for c in result["candidates"]], ["f", "f", "f"])
        self.assertEqual(locate_quote("\ufb01", "f")["status"], "not_found")
        self.assertEqual(locate_quote("\ufb01", "i")["status"], "not_found")
        self.assertEqual(locate_quote("\ufb03", "ff")["status"], "not_found")
        self.assertEqual(locate_quote("\ufb03", "ffi")["status"], "candidate")

    def test_line_break_hyphen_is_only_a_possible_unverified_match(self):
        page = "Prefix a deep represen-\r\n  tation finding ends."
        result = locate_quote(page, "representation finding", prefix="deep", suffix="ends.")
        self.assertEqual(result["status"], "possible_line_hyphenation")
        self.assertFalse(result["verified"])
        candidate = result["candidates"][0]
        self.assertEqual(candidate["match_kind"], "possible_line_hyphenation")
        self.assertTrue(candidate["context_match"])
        self.assertEqual(page[candidate["start"]:candidate["end"]], "represen-\r\n  tation finding")
        self.assertEqual(locate_quote(page, "representation finding", prefix="wrong")["status"], "context_mismatch")

    def test_line_break_hyphen_does_not_silently_confirm_a_compound_word(self):
        # The dash might actually belong to a compound word. The only safe
        # way to resolve this is to inspect the original PDF.
        page = "This is a well-\nknown method."
        possible = locate_quote(page, "wellknown")
        self.assertEqual(possible["status"], "possible_line_hyphenation")
        self.assertFalse(possible["verified"])
        self.assertEqual(locate_quote("This is a well-known method.", "wellknown")["status"], "not_found")
        self.assertEqual(locate_quote("well- known", "wellknown")["status"], "not_found")
        self.assertEqual(locate_quote("well-\n\nknown", "wellknown")["status"], "not_found")
        self.assertEqual(locate_quote(page, "well- known")["status"], "candidate")

    def test_possible_and_exact_occurrences_are_both_retained(self):
        page = "first representation. second represen-\ntation."
        result = locate_quote(page, "representation")
        self.assertEqual(result["status"], "possible_line_hyphenation")
        self.assertEqual([page[c["start"]:c["end"]] for c in result["candidates"]],
                         ["representation", "represen-\ntation"])
        selected = locate_quote(page, "representation", prefix="first")
        self.assertEqual(selected["status"], "candidate")
        self.assertEqual(len(selected["candidates"]), 1)
        selected_possible = locate_quote(page, "representation", prefix="second")
        self.assertEqual(selected_possible["status"], "possible_line_hyphenation")
        self.assertEqual(len(selected_possible["candidates"]), 1)

    def test_line_break_hyphen_and_ligature_offsets_never_split_a_glyph(self):
        page = "co-\n\ufb03cient"
        match = locate_quote(page, "cofficient")
        self.assertEqual(match["status"], "possible_line_hyphenation")
        item = match["candidates"][0]
        self.assertEqual(page[item["start"]:item["end"]], page)
        self.assertEqual(locate_quote(page, "cof")["status"], "not_found")

    def test_encryption_rejected_without_storing_password(self):
        writer = PdfWriter()
        writer.append(PdfReader(str(self.path)))
        writer.encrypt("secret")
        encrypted = Path(self.tmp.name) / "encrypted.pdf"
        with encrypted.open("wb") as stream:
            writer.write(stream)
        with self.assertRaises(PDFProcessingError) as error:
            inspect_pdf(encrypted)
        self.assertEqual(error.exception.code, "encrypted")

    def test_explicit_labels_and_rotation_are_separate_from_page_index(self):
        from pypdf.constants import PageLabelStyle
        writer = PdfWriter()
        writer.append(PdfReader(str(self.path)))
        writer.pages[1].rotate(90)
        writer.set_page_label(0, 0, PageLabelStyle.LOWERCASE_ROMAN, start=1)
        writer.set_page_label(1, 3, PageLabelStyle.DECIMAL, start=1)
        labeled = Path(self.tmp.name) / "labeled.pdf"
        with labeled.open("wb") as stream:
            writer.write(stream)
        result = inspect_pdf(labeled)
        self.assertEqual(result["pages"][0]["page_label"], "i")
        self.assertEqual(result["pages"][1]["page_label"], "1")
        self.assertEqual(result["pages"][1]["page_index"], 1)
        self.assertEqual(result["pages"][1]["rotation"], 90)

    def test_windows_ocr_input_validation_and_page_boundaries(self):
        for index in (-1, True):
            with self.assertRaises(ValueError):
                ocr_page_windows(self.path, index)
        with self.assertRaises(ValueError):
            ocr_page_windows(self.path, 0, language="ko;not-a-language")
        with self.assertRaises(ValueError):
            ocr_page_windows(self.path, 0, max_dimension=10000)
        if os.name == "nt" and shutil.which("pdftoppm") and shutil.which("powershell.exe"):
            with self.assertRaises(PDFProcessingError) as error:
                ocr_page_windows(self.path, 4)
            self.assertEqual(error.exception.code, "page_out_of_range")

    @unittest.skipUnless(os.name == "nt" and shutil.which("pdftoppm") and shutil.which("powershell.exe"), "Windows OCR or Poppler is unavailable")
    def test_windows_ocr_timeout_cleans_temporary_image(self):
        images = []

        def fake_run(args, **kwargs):
            if "-singlefile" in args:
                image = Path(args[-1] + ".png")
                image.write_bytes(b"synthetic")
                images.append(image)
                return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")
            self.assertTrue(images[0].exists())
            raise subprocess.TimeoutExpired(args, kwargs["timeout"])

        with patch("app.pdf_processing.subprocess.run", side_effect=fake_run):
            with self.assertRaises(PDFProcessingError) as error:
                ocr_page_windows(self.path, 0, timeout=2)
        self.assertEqual(error.exception.code, "adapter_timeout")
        self.assertEqual(len(images), 1)
        self.assertFalse(images[0].exists())

    @unittest.skipUnless(os.name == "nt" and shutil.which("pdftoppm") and shutil.which("powershell.exe"), "Windows OCR or Poppler is unavailable")
    def test_windows_ocr_language_unavailable_is_reported(self):
        def fake_run(args, **kwargs):
            if "-singlefile" in args:
                Path(args[-1] + ".png").write_bytes(b"synthetic")
                return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")
            return SimpleNamespace(returncode=30, stdout=b"", stderr=b"")

        with patch("app.pdf_processing.subprocess.run", side_effect=fake_run):
            with self.assertRaises(PDFProcessingError) as error:
                ocr_page_windows(self.path, 0, language="fr")
        self.assertEqual(error.exception.code, "language_unavailable")

    @unittest.skipUnless(os.name == "nt" and shutil.which("pdftoppm") and shutil.which("powershell.exe"), "Windows OCR or Poppler is unavailable")
    def test_windows_ocr_on_synthetic_korean_scanned_pdf(self):
        font_path = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "malgun.ttf"
        if not font_path.exists():
            self.skipTest("Korean font unavailable")
        image = Image.new("RGB", (1500, 240), "white")
        ImageDraw.Draw(image).text((40, 50), "연구 논문 정확도 향상", font=ImageFont.truetype(str(font_path), 72), fill="black")
        data = io.BytesIO()
        image.save(data, format="PNG")
        data.seek(0)
        scan = Path(self.tmp.name) / "korean-scan.pdf"
        pdf = canvas.Canvas(str(scan), pagesize=(750, 120))
        pdf.drawImage(ImageReader(data), 0, 0, width=750, height=120)
        pdf.save()
        self.assertEqual(inspect_pdf(scan)["pages"][0]["status"], "image_only")
        try:
            result = ocr_page_windows(scan, 0, language="ko")
        except PDFProcessingError as exc:
            if exc.code == "language_unavailable":
                self.skipTest("Korean Windows OCR language not installed")
            raise
        self.assertEqual(result["page_index"], 0)
        self.assertEqual(result["status"], "ocr_unverified")
        self.assertEqual(result["text_source"], "ocr_windows")
        self.assertEqual(result["engine"], "windows_media_ocr")
        self.assertIn("연구", result["text"])
        self.assertIn("정확도", result["text"])


if __name__ == "__main__":
    unittest.main()
