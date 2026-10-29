"""Page OCR API and persisted job regressions using a synthetic scanned PDF."""
import io
import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import HTTPException, UploadFile
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from app import jobs, main, storage
from app.pdf_processing import PDFProcessingError


def make_scan():
    font_path = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "malgun.ttf"
    font = ImageFont.truetype(str(font_path), 70) if font_path.exists() else ImageFont.load_default()
    image = Image.new("RGB", (1500, 240), "white")
    text = "연구 논문 정확도 향상" if font_path.exists() else "SCANNED RESEARCH"
    ImageDraw.Draw(image).text((40, 50), text, font=font, fill="black")
    image_bytes = io.BytesIO()
    image.save(image_bytes, format="PNG")
    image_bytes.seek(0)
    stream = io.BytesIO()
    pdf = canvas.Canvas(stream, pagesize=(750, 120))
    pdf.drawImage(ImageReader(image_bytes), 0, 0, width=750, height=120)
    pdf.showPage()
    pdf.save()
    return stream.getvalue()


class OCRIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"EASYRESEARCH_DATA_DIR": self.folder.name})
        self.env.start()
        storage.init_db()
        self.project = main.create_project(main.ProjectCreate(name="OCR"))["id"]
        uploaded = UploadFile(file=io.BytesIO(make_scan()), filename="scan.pdf")
        self.paper = main.import_pdf(project_id=self.project, file=uploaded, paper_id=None)["id"]
        extraction = jobs._claim()
        self.assertIsNotNone(extraction)
        self.assertEqual(extraction[1], "pdf_extract")
        jobs.execute_pdf(extraction[0], extraction[2])
        self.assertEqual(main.get_page(self.paper, 0)["status"], "image_only")

    def tearDown(self):
        jobs.stop()
        self.env.stop()
        self.folder.cleanup()

    def queue(self):
        # The endpoint is platform-specific; mock only capability discovery.
        with patch.object(main.shutil, "which", return_value="available"):
            return main.request_ocr(self.paper, 0, main.OCRRequest(language="ko"))["job_id"]

    @unittest.skipUnless(os.name == "nt", "Windows OCR endpoint requires Windows")
    def test_ocr_job_completion_persists_separate_unverified_source(self):
        job_id = self.queue()
        self.assertEqual(self.queue(), job_id)
        job = jobs._claim()
        self.assertEqual(job[:2], (job_id, "ocr_page"))
        result = {"page_index": 0, "text": "연구 논문", "language": "ko",
                  "text_source": "ocr_windows", "status": "ocr_unverified"}
        with patch.object(jobs, "ocr_page_windows", return_value=result) as ocr:
            jobs.execute_ocr(job_id, job[2])
        self.assertEqual(ocr.call_args.args[1:], (0, "ko"))
        page = main.get_page(self.paper, 0)
        self.assertEqual(page["text"], "")
        self.assertEqual(page["ocr"]["text"], "연구 논문")
        self.assertEqual(page["ocr"]["source"], "ocr_windows")
        self.assertEqual(page["ocr"]["status"], "ocr_unverified")
        self.assertEqual(main.get_job(job_id)["status"], "completed")

    @unittest.skipUnless(os.name == "nt", "Windows OCR endpoint requires Windows")
    def test_cancel_queued_and_fence_cancelled_running_result(self):
        queued = self.queue()
        self.assertTrue(jobs.cancel(queued))
        self.assertEqual(main.get_job(queued)["status"], "cancelled")
        self.assertIsNone(jobs._claim())
        running = self.queue()
        claim = jobs._claim()

        def cancel_while_processing(*args):
            jobs.cancel(running)
            return {"page_index": 0, "text": "should not be saved", "language": "ko",
                    "text_source": "ocr_windows", "status": "ocr_unverified"}

        with patch.object(jobs, "ocr_page_windows", side_effect=cancel_while_processing):
            jobs.execute_ocr(running, claim[2])
        self.assertIsNone(main.get_page(self.paper, 0)["ocr"])
        jobs._finish_aborted(running, claim[2], "cancelled")
        self.assertEqual(main.get_job(running)["status"], "cancelled")

    @unittest.skipUnless(os.name == "nt", "Windows OCR endpoint requires Windows")
    def test_failure_and_page_bounds(self):
        with patch.object(main.shutil, "which", return_value="available"):
            for index in (-1, 1):
                with self.subTest(index=index), self.assertRaises(HTTPException) as error:
                    main.request_ocr(self.paper, index, main.OCRRequest())
                self.assertEqual(error.exception.status_code, 422)
        job_id = self.queue()
        claim = jobs._claim()
        with patch.object(jobs, "ocr_page_windows", side_effect=PDFProcessingError("language_unavailable", "missing")):
            jobs.execute_ocr(job_id, claim[2])
        job = main.get_job(job_id)
        self.assertEqual(job["status"], "failed")
        self.assertEqual(job["error"], "language_unavailable")
        self.assertIsNone(main.get_page(self.paper, 0)["ocr"])

    @unittest.skipUnless(os.name == "nt", "Windows OCR endpoint requires Windows")
    def test_only_user_confirmed_ocr_quote_can_be_used_for_analysis(self):
        job_id = self.queue()
        claim = jobs._claim()
        result = {"page_index": 0, "text": "연구 논문 정확도 향상", "language": "ko",
                  "text_source": "ocr_windows", "status": "ocr_unverified"}
        with patch.object(jobs, "ocr_page_windows", return_value=result):
            jobs.execute_ocr(job_id, claim[2])
        unconfirmed = main.add_evidence(self.paper, main.EvidenceCreate(page_index=0, quote="연구 논문", note=""))
        unconfirmed_result = main.analyze(main.AnalysisRequest(paper_ids=[self.paper], question="연구"))
        self.assertEqual(unconfirmed_result["status"], "insufficient_evidence")
        confirmed = main.add_evidence(self.paper, main.EvidenceCreate(page_index=0, quote="연구 논문", note="직접 확인", verified_with_original=True, capture_method="ocr"))
        analyzed = main.analyze(main.AnalysisRequest(paper_ids=[self.paper], question="의미를 설명해줘", evidence_ids=[confirmed["id"]]))
        self.assertEqual(analyzed["status"], "excerpts_only")
        self.assertEqual(analyzed["excerpts"][0]["verification"], "user_verified_ocr")
        self.assertEqual(analyzed["semantic_support"], "not_checked")
        revised = main.update_evidence(confirmed["id"], main.EvidenceCreate(page_index=0, quote="다른 구절", note=""))
        self.assertEqual(revised["source"], "manual")
        with self.assertRaises(HTTPException):
            main.analyze(main.AnalysisRequest(paper_ids=[self.paper], question="질문", evidence_ids=[confirmed["id"]]))

    @unittest.skipUnless(os.name == "nt" and shutil.which("pdftoppm") and shutil.which("powershell.exe"),
                         "Windows OCR or Poppler is unavailable")
    def test_real_korean_ocr_through_background_worker(self):
        font_path = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "malgun.ttf"
        if not font_path.exists():
            self.skipTest("Korean font unavailable")
        jobs.start()
        job_id = self.queue()
        deadline = time.monotonic() + 55
        while time.monotonic() < deadline:
            job = main.get_job(job_id)
            if job["status"] in ("completed", "failed", "cancelled"):
                break
            time.sleep(0.2)
        if job["status"] == "failed" and job["error"] == "language_unavailable":
            self.skipTest("Korean Windows OCR language is not installed")
        self.assertEqual(job["status"], "completed", job)
        result = main.get_page(self.paper, 0)["ocr"]
        self.assertEqual(result["source"], "ocr_windows")
        self.assertEqual(result["status"], "ocr_unverified")
        self.assertIn("연구", result["text"])
        self.assertIn("정확도", result["text"])

    @unittest.skipUnless(os.name == "nt" and shutil.which("pdftoppm") and shutil.which("powershell.exe"),
                         "Windows OCR or Poppler is unavailable")
    def test_real_english_ocr_through_background_worker(self):
        font_path = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "arial.ttf"
        if not font_path.exists():
            self.skipTest("English font unavailable")
        image = Image.new("RGB", (1500, 240), "white")
        ImageDraw.Draw(image).text((40, 50), "SCANNED RESEARCH FINDINGS",
                                   font=ImageFont.truetype(str(font_path), 70), fill="black")
        image_bytes = io.BytesIO()
        image.save(image_bytes, format="PNG")
        image_bytes.seek(0)
        stream = io.BytesIO()
        pdf = canvas.Canvas(stream, pagesize=(750, 120))
        pdf.drawImage(ImageReader(image_bytes), 0, 0, width=750, height=120)
        pdf.showPage()
        pdf.save()
        paper = main.import_pdf(project_id=self.project, file=UploadFile(file=io.BytesIO(stream.getvalue()), filename="english.pdf"), paper_id=None)["id"]
        jobs.start()
        job_id = main.request_ocr(paper, 0, main.OCRRequest(language="en"))["job_id"]
        deadline = time.monotonic() + 55
        while time.monotonic() < deadline:
            job = main.get_job(job_id)
            if job["status"] in ("completed", "failed", "cancelled"):
                break
            time.sleep(0.2)
        if job["status"] == "failed" and job["error"] == "language_unavailable":
            self.skipTest("English Windows OCR language is not installed")
        self.assertEqual(job["status"], "completed", job)
        result = main.get_ocr_result(job_id)
        self.assertTrue(result["language"].lower().startswith("en"))
        self.assertEqual(result["status"], "ocr_unverified")
        self.assertIn("RESEARCH", result["text"].upper())


if __name__ == "__main__":
    unittest.main()
