"""Source integrity and conservative page-result retention regressions."""
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException, UploadFile
from reportlab.pdfgen import canvas

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import jobs, main, storage
from app.pdf_processing import inspect_pdf


def make_pdf():
    data = io.BytesIO()
    pdf = canvas.Canvas(data)
    pdf.drawString(40, 700, "First page unique research result")
    pdf.showPage()
    pdf.drawString(40, 700, "Second page distinct conclusion")
    pdf.save()
    return data.getvalue()


class PDFIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"EASYRESEARCH_DATA_DIR": self.folder.name})
        self.env.start()
        storage.init_db()
        project = main.create_project(main.ProjectCreate(name="Integrity"))["id"]
        self.paper = main.import_pdf(project_id=project, file=UploadFile(file=io.BytesIO(make_pdf()), filename="original.pdf"), paper_id=None)["id"]
        job = jobs._claim()
        jobs.execute_pdf(job[0], job[2])
        self.assertEqual(main.get_job(job[0])["status"], "completed")
        with storage.transaction() as con:
            row = con.execute("SELECT f.storage_key FROM papers p JOIN files f ON f.id=p.file_id WHERE p.id=?", (self.paper,)).fetchone()
        self.path = storage.file_path(row["storage_key"])

    def tearDown(self):
        jobs.stop()
        self.env.stop()
        self.folder.cleanup()

    def queue_pdf(self):
        with storage.transaction() as con:
            job_id = jobs.enqueue_pdf(con, self.paper)
        claim = jobs._claim()
        self.assertEqual(claim[0], job_id)
        return job_id, claim[2]

    def queue_ocr(self):
        with storage.transaction() as con:
            job_id = jobs.enqueue_ocr(con, self.paper, 0, "ko")
        claim = jobs._claim()
        self.assertEqual(claim[0], job_id)
        return job_id, claim[2]

    def test_changed_source_before_reprocessing_keeps_original_extraction(self):
        original_text = main.get_page(self.paper, 0)["text"]
        job_id, token = self.queue_pdf()
        original = self.path.read_bytes()
        self.path.write_bytes(original[:-1] + bytes([original[-1] ^ 1]))
        jobs.execute_pdf(job_id, token)
        job = main.get_job(job_id)
        self.assertEqual((job["status"], job["error"]), ("failed", "source_changed"))
        self.assertEqual(main.get_page(self.paper, 0)["text"], original_text)

    def test_changed_source_during_extraction_prevents_persisting_new_text(self):
        original_text = main.get_page(self.paper, 0)["text"]
        job_id, token = self.queue_pdf()
        def changed(path):
            result = inspect_pdf(path)
            result["pages"][0]["text"] = "not the original"
            path.write_bytes(b"%PDF- changed during processing")
            return result
        with patch.object(jobs, "inspect_pdf", side_effect=changed):
            jobs.execute_pdf(job_id, token)
        self.assertEqual(main.get_job(job_id)["error"], "source_changed")
        self.assertEqual(main.get_page(self.paper, 0)["text"], original_text)

    def test_partial_reprocessing_preserves_failed_page_and_evidence(self):
        old = main.get_page(self.paper, 0)
        evidence = main.add_evidence(self.paper, main.EvidenceCreate(page_index=0, quote="First page unique research result"))
        job_id, token = self.queue_pdf()
        result = inspect_pdf(self.path)
        result["status"] = "partial"
        result["pages"][0].update(status="failed", text="")
        result["pages"][1]["text"] = "Updated second page text"
        with patch.object(jobs, "inspect_pdf", return_value=result):
            jobs.execute_pdf(job_id, token)
        self.assertEqual(main.get_job(job_id)["status"], "partial")
        self.assertEqual(main.get_page(self.paper, 0)["text"], old["text"])
        self.assertEqual(main.get_page(self.paper, 0)["extraction_details"], old["extraction_details"])
        self.assertEqual(main.get_page(self.paper, 1)["text"], "Updated second page text")
        self.assertEqual(main.list_evidence(self.paper)[0]["status"], "candidate")
        self.assertEqual(main.list_evidence(self.paper)[0]["id"], evidence["id"])

    def test_page_quality_warnings_and_parser_version_are_saved(self):
        job_id, token = self.queue_pdf()
        result = inspect_pdf(self.path)
        result["parser_version"] = "test-parser-version"
        result["pages"][0]["warnings"] = ["Verify unusual font against original."]
        result["pages"][0]["image_count"] = 2
        with patch.object(jobs, "inspect_pdf", return_value=result):
            jobs.execute_pdf(job_id, token)
        self.assertEqual(main.get_job(job_id)["status"], "completed")
        details = main.get_page(self.paper, 0)["extraction_details"]
        self.assertEqual(details["parser_version"], "test-parser-version")
        self.assertEqual(details["warnings"], ["Verify unusual font against original."])
        self.assertEqual(details["image_count"], 2)

    def test_new_empty_result_does_not_erase_previous_text(self):
        previous_text = main.get_page(self.paper, 0)["text"]
        job_id, token = self.queue_pdf()
        result = inspect_pdf(self.path)
        result["pages"][0].update(status="no_text", text="")
        with patch.object(jobs, "inspect_pdf", return_value=result):
            jobs.execute_pdf(job_id, token)
        self.assertEqual(main.get_job(job_id)["status"], "partial")
        self.assertEqual(main.get_page(self.paper, 0)["text"], previous_text)

    def test_ocr_source_change_or_wrong_page_is_not_saved(self):
        original = self.path.read_bytes()
        for mode in ("changed", "wrong_page"):
            with self.subTest(mode=mode):
                self.path.write_bytes(original)
                job_id, token = self.queue_ocr()
                def fake_ocr(path, page, language):
                    if mode == "changed":
                        path.write_bytes(b"%PDF- changed during OCR")
                    return {"page_index": 1 if mode == "wrong_page" else 0,
                            "text": "untrusted", "language": "ko", "text_source": "ocr_windows", "status": "ocr_unverified"}
                with patch.object(jobs, "ocr_page_windows", side_effect=fake_ocr):
                    jobs.execute_ocr(job_id, token)
                job = main.get_job(job_id)
                self.assertEqual(job["status"], "failed")
                self.assertEqual(job["error"], "source_changed" if mode == "changed" else "page_mismatch")
                self.assertIsNone(main.get_page(self.paper, 0)["ocr"])

    def test_stale_context_is_visible_and_not_used_as_evidence(self):
        record = main.add_evidence(self.paper, main.EvidenceCreate(page_index=0, quote="unique research result", prefix="incorrect"))
        self.assertEqual(record["status"], "context_mismatch")
        with self.assertRaises(HTTPException):
            main.analyze(main.AnalysisRequest(paper_ids=[self.paper], question="research", evidence_ids=[record["id"]]))

    def test_line_break_hyphen_remains_uncertain_after_extraction_and_reload(self):
        stream = io.BytesIO()
        pdf = canvas.Canvas(stream)
        pdf.drawString(40, 700, "The represen-")
        pdf.drawString(40, 680, "tation is useful.")
        pdf.save()
        original = stream.getvalue()
        project = main.create_project(main.ProjectCreate(name="Line break"))["id"]
        paper = main.import_pdf(project_id=project, file=UploadFile(file=io.BytesIO(original), filename="line-break.pdf"), paper_id=None)["id"]
        job_id, _, token = jobs._claim()
        jobs.execute_pdf(job_id, token)
        self.assertEqual(main.get_job(job_id)["status"], "completed")
        self.assertIn("represen-\ntation", main.get_page(paper, 0)["text"])
        record = main.add_evidence(paper, main.EvidenceCreate(page_index=0, quote="representation"))
        self.assertEqual(record["status"], "possible_line_hyphenation")
        self.assertFalse(record["match"]["verified"])
        reloaded = main.list_evidence(paper)[0]
        self.assertEqual(reloaded["quote"], "representation")
        self.assertEqual(reloaded["status"], "possible_line_hyphenation")
        with self.assertRaises(HTTPException):
            main.analyze(main.AnalysisRequest(paper_ids=[paper], question="research", evidence_ids=[record["id"]]))
        with storage.transaction() as con:
            row = con.execute("SELECT f.storage_key FROM papers p JOIN files f ON f.id=p.file_id WHERE p.id=?", (paper,)).fetchone()
            queued = jobs.enqueue_pdf(con, paper)
        self.assertEqual(storage.file_path(row["storage_key"]).read_bytes(), original)
        job_id, _, token = jobs._claim()
        self.assertEqual(job_id, queued)
        jobs.execute_pdf(job_id, token)
        self.assertEqual(main.list_evidence(paper)[0]["status"], "possible_line_hyphenation")
        self.assertEqual(storage.file_path(row["storage_key"]).read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
