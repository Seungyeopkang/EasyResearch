"""End-to-end local API tests. No external services or real papers are used."""
import io
import hashlib
import json
import os
import sqlite3
import sys
import tempfile
import time
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas

from app.main import app
from app import analysis_engine, scholarly, storage


def pdf_bytes():
    data = io.BytesIO()
    pdf = canvas.Canvas(data)
    pdf.drawString(70, 700, "alpha method improves accuracy")
    pdf.showPage()
    pdf.drawString(70, 700, "second page limitation")
    pdf.save()
    return data.getvalue()


class APIIntegrationTests(unittest.TestCase):
    def setUp(self):
        # A # in the storage path verifies SQLite URI percent escaping.
        self.temp = tempfile.TemporaryDirectory(prefix="easyresearch-#-")
        self.env = patch.dict(os.environ, {"EASYRESEARCH_DATA_DIR": self.temp.name})
        self.env.start()
        self.client = TestClient(app)
        self.client.__enter__()
        self.headers = {"X-EasyResearch": "1"}

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.env.stop()
        self.temp.cleanup()

    def project(self):
        response = self.client.post("/api/projects", json={"name": "연구"}, headers=self.headers)
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()["id"]

    def test_pdfjs_modules_are_served_with_browser_javascript_mime(self):
        for asset in ("pdf.min.mjs", "pdf.worker.min.mjs"):
            response = self.client.get("/assets/vendor/pdfjs/" + asset)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.headers["content-type"].startswith("text/javascript"))
            self.assertGreater(len(response.content), 1000)

    def upload(self, project, data=None, name="paper.pdf"):
        return self.client.post("/api/papers/import", data={"project_id": project},
                                files={"file": (name, data if data is not None else pdf_bytes(), "application/pdf")},
                                headers=self.headers)

    def wait_job(self, job_id):
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            result = self.client.get("/api/jobs/" + job_id)
            self.assertEqual(result.status_code, 200, result.text)
            if result.json()["status"] in {"completed", "partial", "failed", "cancelled"}:
                return result.json()
            time.sleep(0.1)
        self.fail("PDF extraction timed out")

    def backup_and_restore(self, expected_count):
        response = self.client.post("/api/backups", headers=self.headers)
        self.assertEqual(response.status_code, 201, response.text)
        backup = response.json()
        self.assertEqual(backup["file_count"], expected_count)
        archive = self.client.get(backup["download_url"])
        self.assertEqual(archive.status_code, 200)
        with zipfile.ZipFile(io.BytesIO(archive.content)) as z:
            self.assertIsNone(z.testzip())
            self.assertEqual(len(json.loads(z.read("manifest.json"))["files"]), expected_count)
        restored = self.client.post("/api/backups/restore", files={"file": ("backup.zip", archive.content, "application/zip")}, headers=self.headers)
        self.assertEqual(restored.status_code, 201, restored.text)
        self.assertEqual(restored.json()["file_count"], expected_count)
        self.assertEqual(restored.json()["status"], "verified")
        return Path(restored.json()["restore_path"])

    def test_empty_backup_with_hash_in_path(self):
        restored = self.backup_and_restore(0)
        self.assertIn("#", str(restored))
        connection = sqlite3.connect(str(restored / "library.sqlite3"))
        try:
            self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        finally:
            connection.close()

    def test_complete_local_workflow_and_restore(self):
        project = self.project()
        raw = pdf_bytes()
        upload = self.upload(project, raw)
        self.assertEqual(upload.status_code, 201, upload.text)
        paper = upload.json()
        self.assertFalse(paper["duplicate"])
        self.assertEqual(self.wait_job(paper["job_id"])["status"], "completed")
        duplicate = self.upload(project, raw)
        self.assertEqual(duplicate.status_code, 201, duplicate.text)
        self.assertTrue(duplicate.json()["duplicate"])
        self.assertEqual(duplicate.json()["id"], paper["id"])
        self.assertEqual(self.client.get("/api/papers/" + paper["id"] + "/file").content, raw)
        first_page = self.client.get("/api/papers/" + paper["id"] + "/pages/0")
        self.assertIn("alpha method", first_page.json()["text"])
        evidence = self.client.post("/api/papers/" + paper["id"] + "/evidence",
                                    json={"page_index": 0, "quote": "alpha method improves accuracy", "note": "check"}, headers=self.headers)
        self.assertEqual(evidence.status_code, 201, evidence.text)
        self.assertEqual(evidence.json()["status"], "candidate")
        evidence_id = evidence.json()["id"]
        idea = self.client.post("/api/ideas", json={"project_id": project, "title": "Idea", "evidence_ids": [evidence_id]}, headers=self.headers)
        self.assertEqual(idea.status_code, 201, idea.text)
        self.assertEqual(self.client.get("/api/ideas", params={"project_id": project}).json()[0]["evidence_ids"], [evidence_id])
        self.assertEqual(self.client.delete("/api/evidence/" + evidence_id, headers=self.headers).status_code, 409)

        record = {"title": "Reference", "source": "arxiv", "source_id": "arxiv:example", "authors": [], "doi": None}
        with patch.object(scholarly, "search_arxiv", return_value=[record]) as search:
            found = self.client.get("/api/search", params={"source": "arxiv", "q": "accuracy"})
        self.assertEqual(found.status_code, 200, found.text)
        search.assert_called_once()
        second = self.client.post("/api/papers/from-search", json={"project_id": project, "paper": found.json()[0]}, headers=self.headers)
        self.assertEqual(second.status_code, 201, second.text)
        self.assertFalse(second.json()["duplicate"])
        analysis = self.client.post("/api/analyses", json={"paper_ids": [paper["id"]], "question": "accuracy"}, headers=self.headers)
        self.assertEqual(analysis.status_code, 200, analysis.text)
        self.assertEqual(analysis.json()["status"], "excerpts_only")
        self.assertEqual(analysis.json()["excerpts"][0]["id"], evidence_id)
        insufficient = self.client.post("/api/analyses", json={"paper_ids": [paper["id"]], "question": "irrelevantword"}, headers=self.headers)
        self.assertEqual(insufficient.json()["status"], "insufficient_evidence")
        compare = self.client.post("/api/comparisons", json={"paper_ids": [paper["id"], second.json()["id"]]}, headers=self.headers)
        self.assertEqual(compare.status_code, 200, compare.text)
        self.assertEqual([row["status"] for row in compare.json()["rows"]], ["excerpts_only", "insufficient_evidence"])
        experiment = self.client.post("/api/experiments", json={"project_id": project, "values": [1, 2, 3, 4], "seed": 42}, headers=self.headers)
        self.assertEqual(experiment.status_code, 201, experiment.text)
        self.assertEqual(experiment.json()["status"], "completed")
        self.assertEqual(len(experiment.json()["result"]["data_sha256"]), 64)
        restored = self.backup_and_restore(1)
        connection = sqlite3.connect(str(restored / "library.sqlite3"))
        try:
            self.assertEqual(connection.execute("SELECT count(*) FROM evidence").fetchone()[0], 1)
            key = connection.execute("SELECT storage_key FROM files").fetchone()[0]
            self.assertEqual((restored / key).read_bytes(), raw)
        finally:
            connection.close()

    def test_request_rejections_page_ranges_and_corruption(self):
        self.assertEqual(self.client.post("/api/projects", json={"name": "X"}).status_code, 403)
        self.assertEqual(self.client.post("/api/projects", json={"name": "X"}, headers={**self.headers, "Origin": "https://evil.example"}).status_code, 403)
        project = self.project()
        raw = pdf_bytes()
        self.assertEqual(self.upload(project, b"not a PDF").status_code, 400)
        upload = self.upload(project, raw).json()
        self.assertEqual(self.wait_job(upload["job_id"])["status"], "completed")
        paper_id = upload["id"]
        self.assertEqual(self.client.get("/api/papers/" + paper_id + "/pages/2").status_code, 404)
        self.assertEqual(self.client.post("/api/papers/" + paper_id + "/evidence", json={"page_index": 2, "note": "bad"}, headers=self.headers).status_code, 422)
        self.assertEqual(self.client.get("/api/search", params={"source": "other", "q": "a"}).status_code, 422)
        with storage.transaction() as con:
            key = con.execute("SELECT storage_key FROM files WHERE sha256=?", (upload["sha256"],)).fetchone()[0]
        path = storage.file_path(key)
        path.write_bytes(b"corrupted")
        self.assertEqual(self.client.get("/api/papers/" + paper_id + "/file").status_code, 409)
        self.assertEqual(self.client.post("/api/backups", headers=self.headers).status_code, 409)
        self.assertEqual(self.upload(project, raw).status_code, 400)
        path.write_bytes(raw)
        replacement = self.upload(project, raw)
        self.assertEqual(replacement.status_code, 201, replacement.text)
        self.assertTrue(replacement.json()["duplicate"])
        self.assertEqual(self.client.post("/api/backups/restore", files={"file": ("bad.zip", b"garbage", "application/zip")}, headers=self.headers).status_code, 400)

    def test_search_adapters_are_invoked_and_failures_preserved(self):
        record = {"title": "Synthetic result", "source": "test", "source_id": "one"}
        with patch.object(scholarly, "search_openalex", return_value=[record]) as openalex:
            response = self.client.get("/api/search", params={"source": "openalex", "q": "test"})
        self.assertEqual(response.json(), [record])
        openalex.assert_called_once()
        with patch.object(scholarly, "lookup_crossref", return_value=record) as crossref:
            response = self.client.get("/api/search", params={"source": "crossref", "q": "10.1/example"})
        self.assertEqual(response.json(), [record])
        crossref.assert_called_once_with("10.1/example")
        error = scholarly.ScholarlyError("arxiv", "rate_limited", "retry later", status=429)
        with patch.object(scholarly, "search_arxiv", side_effect=error):
            response = self.client.get("/api/search", params={"source": "arxiv", "q": "test"})
        self.assertEqual(response.status_code, 429, response.text)
        self.assertEqual(response.json()["detail"]["code"], "rate_limited")

    def test_bad_pdf_header_can_be_opened_neither_by_worker_nor_analysis(self):
        project = self.project()
        response = self.upload(project, b"%PDF-1.7\ninvalid body")
        self.assertEqual(response.status_code, 201, response.text)
        paper = response.json()
        result = self.wait_job(paper["job_id"])
        self.assertEqual(result["status"], "failed", str(result))
        self.assertEqual(result["error"], "invalid_pdf")
        analysis = self.client.post("/api/analyses", json={"paper_ids": [paper["id"]], "question": "test"}, headers=self.headers)
        self.assertEqual(analysis.json()["status"], "insufficient_evidence")

    def test_selected_english_evidence_and_preview_changes(self):
        project = self.project()
        uploaded = self.upload(project).json()
        self.assertEqual(self.wait_job(uploaded["job_id"])["status"], "completed")
        evidence_ids = []
        for index, quote in [(0, "alpha method improves accuracy"), (1, "second page limitation")]:
            result = self.client.post("/api/papers/" + uploaded["id"] + "/evidence",
                                      json={"page_index": index, "quote": quote}, headers=self.headers)
            self.assertEqual(result.status_code, 201, result.text)
            evidence_ids.append(result.json()["id"])
        selected = {"paper_ids": [uploaded["id"]], "question": "이 논문의 방법은 무엇인가요?", "evidence_ids": evidence_ids[:1]}
        result = self.client.post("/api/analyses", json=selected, headers=self.headers)
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()["status"], "excerpts_only")
        self.assertEqual([x["id"] for x in result.json()["excerpts"]], evidence_ids[:1])
        self.assertEqual(result.json()["semantic_support"], "not_checked")

        request = dict(selected, provider="openai", model="example-model", allow_external=True)
        preview = self.client.post("/api/analyses/preview", json=request, headers=self.headers)
        self.assertEqual(preview.status_code, 200, preview.text)
        digest = preview.json()["preview_hash"]
        changed = [dict(request, question="다른 질문"), dict(request, evidence_ids=evidence_ids[1:]), dict(request, model="other-model")]
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}), patch.object(analysis_engine, "_openai", return_value={"provider": "openai", "status": "insufficient_evidence", "claims": [], "excerpts": [], "semantic_support": "not_checked"}) as provider:
            for payload in changed:
                response = self.client.post("/api/analyses", json=dict(payload, preview_hash=digest), headers=self.headers)
                self.assertEqual(response.status_code, 409, response.text)
            provider.assert_not_called()
            same = self.client.post("/api/analyses", json=dict(request, preview_hash=digest), headers=self.headers)
            self.assertEqual(same.status_code, 200, same.text)
            provider.assert_called_once()

    def test_backup_rejects_valid_database_with_modified_schema(self):
        response = self.client.post("/api/backups", headers=self.headers)
        self.assertEqual(response.status_code, 201, response.text)
        archive = self.client.get(response.json()["download_url"]).content
        with zipfile.ZipFile(io.BytesIO(archive)) as original:
            entries = {name: original.read(name) for name in original.namelist()}
        db = Path(self.temp.name) / "schema-variant.sqlite3"
        db.write_bytes(entries["library.sqlite3"])
        connection = sqlite3.connect(str(db))
        try:
            connection.execute("ALTER TABLE projects ADD COLUMN injected TEXT")
            connection.commit()
        finally:
            connection.close()
        entries["library.sqlite3"] = db.read_bytes()
        manifest = json.loads(entries["manifest.json"])
        manifest["database_sha256"] = hashlib.sha256(entries["library.sqlite3"]).hexdigest()
        entries["manifest.json"] = json.dumps(manifest).encode("utf-8")
        changed = io.BytesIO()
        with zipfile.ZipFile(changed, "w") as zipped:
            for name, data in entries.items():
                zipped.writestr(name, data)
        result = self.client.post("/api/backups/restore", files={"file": ("modified.zip", changed.getvalue(), "application/zip")}, headers=self.headers)
        self.assertEqual(result.status_code, 400, result.text)

    def test_backup_detects_pdf_changed_between_check_and_archive(self):
        project = self.project()
        raw = pdf_bytes()
        uploaded = self.upload(project, raw).json()
        self.assertEqual(self.wait_job(uploaded["job_id"])["status"], "completed")
        original_write = zipfile.ZipFile.write
        changed = []

        def mutate_then_write(archive, filename, arcname=None, *args, **kwargs):
            if arcname and str(arcname).startswith("files/"):
                Path(filename).write_bytes(b"changed after the precheck")
                changed.append(True)
            return original_write(archive, filename, arcname, *args, **kwargs)

        with patch.object(zipfile.ZipFile, "write", new=mutate_then_write):
            result = self.client.post("/api/backups", headers=self.headers)
        self.assertTrue(changed)
        self.assertEqual(result.status_code, 409, result.text)
        self.assertEqual(list((Path(self.temp.name) / "backups").glob("*.zip")), [])


if __name__ == "__main__":
    unittest.main()
