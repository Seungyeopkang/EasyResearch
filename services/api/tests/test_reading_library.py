"""Project-independent reading library: import, global state, filters, link and purge."""
import os
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import storage, reading_library
from app.main import app
from test_api_integration import pdf_bytes


class ReadingLibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"EASYRESEARCH_DATA_DIR": self.temp.name})
        self.env.start()
        self.client = TestClient(app)
        self.client.__enter__()
        self.h = {"X-EasyResearch": "1"}

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.env.stop()
        self.temp.cleanup()

    def manual(self, title, year=None, authors=None, doi=None):
        body = {"title": title, "year": year, "authors": authors or [], "doi": doi}
        response = self.client.post("/api/papers", json=body, headers=self.h)
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def library(self, **params):
        response = self.client.get("/api/library/papers", params=params)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def patch_paper(self, paper_id, **fields):
        return self.client.patch(f"/api/papers/{paper_id}", json=fields, headers=self.h)

    def new_project(self, name="P"):
        return self.client.post("/api/projects", json={"name": name}, headers=self.h).json()["id"]

    def test_import_and_manual_paper_work_without_a_project(self):
        upload = self.client.post("/api/papers/import", files={"file": ("paper.pdf", pdf_bytes(), "application/pdf")}, headers=self.h)
        self.assertEqual(upload.status_code, 201, upload.text)
        self.assertEqual(upload.json()["import_action"], "created_paper")
        manual = self.manual("Manual without project", year=2024, authors=["Kim"])
        items = self.library()
        self.assertEqual({item["id"] for item in items}, {upload.json()["id"], manual["id"]})
        for item in items:
            self.assertEqual(item["projects"], [])
            self.assertEqual((item["reading_status"], item["last_page"], item["last_opened_at"]), ("to_read", 0, None))
            self.assertEqual(item["categories"], [])

    def test_import_duplicate_without_project_returns_existing_paper(self):
        data = pdf_bytes()
        first = self.client.post("/api/papers/import", files={"file": ("a.pdf", data, "application/pdf")}, headers=self.h).json()
        second = self.client.post("/api/papers/import", files={"file": ("b.pdf", data, "application/pdf")}, headers=self.h)
        self.assertEqual(second.status_code, 201, second.text)
        self.assertEqual(second.json()["id"], first["id"])
        self.assertTrue(second.json()["duplicate"])
        self.assertEqual(len(self.library()), 1)

    def test_import_with_project_still_links_and_keeps_project_list(self):
        project = self.new_project()
        upload = self.client.post("/api/papers/import", data={"project_id": project},
                                  files={"file": ("p.pdf", pdf_bytes(), "application/pdf")}, headers=self.h)
        self.assertEqual(upload.status_code, 201, upload.text)
        self.assertEqual(upload.json()["import_action"], "created_paper")
        listed = self.client.get(f"/api/papers?project_id={project}").json()
        self.assertEqual([p["id"] for p in listed], [upload.json()["id"]])
        self.assertEqual(listed[0]["reading_status"], "to_read")
        self.assertEqual(listed[0]["global_reading_status"], "to_read")
        self.assertEqual(self.library()[0]["projects"], [{"id": project, "name": "P"}])

    def test_import_with_unknown_project_is_rejected(self):
        response = self.client.post("/api/papers/import", data={"project_id": "missing"},
                                    files={"file": ("p.pdf", pdf_bytes(), "application/pdf")}, headers=self.h)
        self.assertEqual(response.status_code, 404, response.text)

    def test_global_patch_updates_state_and_last_opened_without_project(self):
        paper = self.manual("Global state")
        response = self.patch_paper(paper["id"], reading_status="reading", last_page=2)
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual((body["reading_status"], body["last_page"]), ("reading", 2))
        self.assertIsNotNone(body["last_opened_at"])
        self.assertEqual([item["id"] for item in self.library(status="reading")], [paper["id"]])
        self.assertEqual(self.library(status="read"), [])
        # Saving the same page again does not count as opening it anew.
        with storage.transaction() as con:
            con.execute("UPDATE paper_reading_state SET last_opened_at='2000-01-01 00:00:00'")
        self.patch_paper(paper["id"], reading_status="read", last_page=2)
        item = self.library(status="read")[0]
        self.assertEqual(item["last_opened_at"], "2000-01-01 00:00:00")

    def test_invalid_reading_values_are_rejected(self):
        paper = self.manual("Validation")
        self.assertEqual(self.patch_paper(paper["id"], reading_status="finished").status_code, 422)
        self.assertEqual(self.patch_paper(paper["id"], last_page=-1).status_code, 422)
        self.assertEqual(self.client.get("/api/library/papers", params={"status": "finished"}).status_code, 422)
        self.assertEqual(self.client.get("/api/library/papers", params={"sort": "random"}).status_code, 422)

    def test_project_patch_updates_project_and_global_state(self):
        project = self.new_project()
        paper = self.manual("Both states")
        self.assertEqual(self.client.post(f"/api/projects/{project}/papers/{paper['id']}/link", headers=self.h).status_code, 201)
        response = self.patch_paper(paper["id"], project_id=project, reading_status="read", last_page=0)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["reading_status"], "read")
        listed = self.client.get(f"/api/papers?project_id={project}").json()[0]
        self.assertEqual(listed["reading_status"], "read")
        self.assertEqual(listed["global_reading_status"], "read")
        self.assertEqual([item["id"] for item in self.library(status="read")], [paper["id"]])

    def test_patch_with_unlinked_project_is_rejected(self):
        project = self.new_project()
        paper = self.manual("Not linked")
        response = self.patch_paper(paper["id"], project_id=project, reading_status="reading")
        self.assertEqual(response.status_code, 404, response.text)
        self.assertEqual(self.library()[0]["reading_status"], "to_read")

    def test_read_hook_runs_only_when_status_becomes_read(self):
        paper = self.manual("Hook")
        with patch.object(reading_library, "on_paper_read") as hook:
            self.patch_paper(paper["id"], reading_status="reading")
            hook.assert_not_called()
            self.patch_paper(paper["id"], reading_status="read")
            hook.assert_called_once()
            self.patch_paper(paper["id"], reading_status="read")
            hook.assert_called_once()

    def test_filters_search_and_sorting(self):
        alpha = self.manual("Alpha Pruning", year=2019, authors=["Lee"], doi="10.1000/alpha")
        beta = self.manual("beta quantization", year=2023, authors=["Park"])
        gamma = self.manual("Gamma diffusion", year=None, authors=["Choi"])
        self.assertEqual({i["id"] for i in self.library(q="PRUNING")}, {alpha["id"]})
        self.assertEqual({i["id"] for i in self.library(q="park")}, {beta["id"]})
        self.assertEqual({i["id"] for i in self.library(q="10.1000/ALPHA")}, {alpha["id"]})
        self.assertEqual(self.library(q="100%"), [])
        self.assertEqual([i["title"] for i in self.library(sort="title")], ["Alpha Pruning", "beta quantization", "Gamma diffusion"])
        self.assertEqual([i["year"] for i in self.library(sort="year")], [2023, 2019, None])
        self.patch_paper(gamma["id"], last_page=1)
        self.patch_paper(beta["id"], last_page=3)
        recent = [i["id"] for i in self.library(sort="recent")]
        self.assertEqual(set(recent[:2]), {gamma["id"], beta["id"]})
        self.assertEqual(recent[2], alpha["id"])
        self.assertEqual(len(self.library(sort="added")), 3)

    def test_category_filter_uses_only_suggested_or_confirmed_rows(self):
        first = self.manual("Category one")
        second = self.manual("Category two")
        with storage.transaction() as con:
            cid = con.execute("SELECT id FROM categories WHERE name='경량화'").fetchone()[0]
            con.execute("INSERT INTO paper_categories(paper_id,category_id,source,status,matched_json) VALUES(?,?,'rule','suggested','[\"pruning\"]')", (first["id"], cid))
            con.execute("INSERT INTO paper_categories(paper_id,category_id,source,status) VALUES(?,?,'rule','rejected')", (second["id"], cid))
        found = self.library(category_id=cid)
        self.assertEqual([i["id"] for i in found], [first["id"]])
        self.assertEqual(found[0]["categories"], [{"id": cid, "name": "경량화", "status": "suggested", "source": "rule", "matched": ["pruning"]}])
        by_id = {item["id"]: item for item in self.library()}
        self.assertEqual(by_id[second["id"]]["categories"], [])

    def test_link_and_guards(self):
        project = self.new_project()
        paper = self.manual("Linkable")
        url = f"/api/projects/{project}/papers/{paper['id']}/link"
        self.assertEqual(self.client.post(url, headers=self.h).status_code, 201)
        self.assertEqual(self.client.post(url, headers=self.h).status_code, 201)
        self.assertEqual([p["id"] for p in self.client.get(f"/api/papers?project_id={project}").json()], [paper["id"]])
        self.assertEqual(self.library()[0]["projects"], [{"id": project, "name": "P"}])
        self.assertEqual(self.client.post(f"/api/projects/missing/papers/{paper['id']}/link", headers=self.h).status_code, 404)
        self.assertEqual(self.client.post(f"/api/projects/{project}/papers/missing/link", headers=self.h).status_code, 404)
        self.assertEqual(self.client.delete(f"/api/papers/{paper['id']}", headers=self.h).status_code, 204)
        other = self.new_project("Other")
        self.assertEqual(self.client.post(f"/api/projects/{other}/papers/{paper['id']}/link", headers=self.h).status_code, 404)
        self.assertEqual(self.library(), [])

    def test_missing_state_row_is_treated_as_to_read(self):
        paper = self.manual("Lazy state")
        with storage.transaction() as con:
            con.execute("DELETE FROM paper_reading_state WHERE paper_id=?", (paper["id"],))
        item = self.library()[0]
        self.assertEqual((item["reading_status"], item["last_page"]), ("to_read", 0))
        self.assertEqual(self.patch_paper(paper["id"], last_page=4).status_code, 200)
        self.assertEqual(self.library()[0]["last_page"], 4)

    def test_purge_removes_new_tables_rows_and_keeps_integrity(self):
        paper = self.manual("Purge me")
        self.patch_paper(paper["id"], reading_status="read", last_page=0)
        with storage.transaction() as con:
            cid = con.execute("SELECT id FROM categories WHERE name='강화학습'").fetchone()[0]
            con.execute("INSERT INTO paper_categories(paper_id,category_id,source,status) VALUES(?,?,'rule','suggested')", (paper["id"], cid))
            con.execute("INSERT INTO paper_topics(paper_id,source,topic_id,name) VALUES(?,'openalex','T1','Topic')", (paper["id"],))
        self.assertEqual(self.client.delete(f"/api/papers/{paper['id']}", headers=self.h).status_code, 204)
        preview = self.client.get(f"/api/trash/papers/{paper['id']}/purge-preview").json()
        self.assertEqual(preview["counts"]["paper_categories"], 1)
        self.assertEqual(preview["counts"]["paper_topics"], 1)
        self.assertEqual(preview["counts"]["paper_reading_state"], 1)
        response = self.client.post(f"/api/trash/papers/{paper['id']}/purge", headers=self.h,
                                    json={"confirm_token": preview["confirm_token"], "delete_files": False})
        self.assertEqual(response.status_code, 200, response.text)
        with closing(sqlite3.connect(str(storage.data_dir() / "library.sqlite3"))) as con, con:
            for table in ("paper_categories", "paper_topics", "paper_reading_state", "papers"):
                self.assertEqual(con.execute(f"SELECT count(*) FROM {table} WHERE {'id' if table == 'papers' else 'paper_id'}=?", (paper["id"],)).fetchone()[0], 0, table)
            self.assertEqual(con.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertIsNone(con.execute("PRAGMA foreign_key_check").fetchone())
            self.assertGreater(con.execute("SELECT count(*) FROM categories").fetchone()[0], 0)

    def test_v6_backup_can_be_created_and_inspected(self):
        paper = self.manual("Backed up")
        self.patch_paper(paper["id"], reading_status="reading", last_page=1)
        created = self.client.post("/api/backups", headers=self.h)
        self.assertEqual(created.status_code, 201, created.text)
        archive = self.client.get(created.json()["download_url"]).content
        inspected = self.client.post("/api/backups/inspect", files={"file": ("b.zip", archive, "application/zip")}, headers=self.h)
        self.assertEqual(inspected.status_code, 200, inspected.text)
        self.assertEqual(inspected.json()["database_version"], storage.SCHEMA_VERSION)
        self.assertFalse(inspected.json()["requires_migration"])


if __name__ == "__main__":
    unittest.main()
