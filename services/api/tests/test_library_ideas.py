"""Idea editing, association validation, and backup preservation."""
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from app import storage
from app.main import app


class IdeaEditingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="easyresearch-ideas-")
        self.env = patch.dict(os.environ, {"EASYRESEARCH_DATA_DIR": self.tmp.name})
        self.env.start()
        self.client = TestClient(app)
        self.client.__enter__()
        self.headers = {"X-EasyResearch": "1"}

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.env.stop()
        self.tmp.cleanup()

    def create_fixture(self):
        projects = [self.client.post("/api/projects", json={"name": name}, headers=self.headers).json()["id"]
                    for name in ("A", "B")]
        with storage.transaction() as con:
            for i, project in enumerate(projects):
                con.execute("INSERT INTO papers(id,title) VALUES(?,?)", ("p" + str(i), "Paper"))
                con.execute("INSERT INTO project_papers(project_id,paper_id) VALUES(?,?)", (project, "p" + str(i)))
                con.execute("INSERT INTO evidence(id,paper_id,page_index,note) VALUES(?,?,0,?)", ("e" + str(i), "p" + str(i), "original note"))
        return projects

    def test_idea_edit_is_atomic_validates_scope_and_preserves_evidence(self):
        project, other = self.create_fixture()
        bad_title = self.client.post("/api/ideas", json={"project_id": project, "title": "  "}, headers=self.headers)
        self.assertEqual(bad_title.status_code, 422)
        created = self.client.post("/api/ideas", json={"project_id": project, "title": " Initial ", "evidence_ids": ["e0", "e0"]}, headers=self.headers)
        self.assertEqual(created.status_code, 201, created.text)
        self.assertEqual(created.json()["evidence_ids"], ["e0"])
        idea_id = created.json()["id"]
        url = "/api/ideas/" + idea_id
        self.assertEqual(self.client.patch(url, json={"title": "changed", "evidence_ids": ["e1"]}, headers=self.headers).status_code, 422)
        self.assertEqual(self.client.patch(url, json={"title": "  "}, headers=self.headers).status_code, 422)
        self.assertEqual(self.client.patch(url, json={"title": None}, headers=self.headers).status_code, 422)
        self.assertEqual(self.client.patch(url, json={"status": "unknown"}, headers=self.headers).status_code, 422)
        current = self.client.get("/api/ideas", params={"project_id": project}).json()[0]
        self.assertEqual(current["title"], "Initial")
        self.assertEqual(current["evidence_ids"], ["e0"])
        update = self.client.patch(url, json={"title": " Revised ", "description": "new", "status": "exploring", "evidence_ids": []}, headers=self.headers)
        self.assertEqual(update.status_code, 200, update.text)
        self.assertEqual((update.json()["title"], update.json()["description"], update.json()["status"], update.json()["evidence_ids"]), ("Revised", "new", "exploring", []))
        self.assertEqual(self.client.patch(url, json={"evidence_ids": ["e0"]}, headers=self.headers).json()["evidence_ids"], ["e0"])
        self.assertEqual(self.client.delete(url, headers=self.headers).status_code, 204)
        self.assertEqual(self.client.delete(url, headers=self.headers).status_code, 404)
        with storage.transaction() as con:
            self.assertEqual(con.execute("SELECT note FROM evidence WHERE id='e0'").fetchone()[0], "original note")
            self.assertEqual(con.execute("SELECT count(*) FROM idea_evidence").fetchone()[0], 0)
            self.assertEqual(con.execute("SELECT count(*) FROM papers").fetchone()[0], 2)

    def test_edited_idea_and_links_survive_backup_and_restore(self):
        project, _ = self.create_fixture()
        changed = self.client.patch("/api/projects/" + project, json={"name": "  Changed  ", "description": "project description"}, headers=self.headers)
        self.assertEqual(changed.status_code, 200, changed.text)
        self.assertEqual((changed.json()["name"], changed.json()["description"]), ("Changed", "project description"))
        self.assertEqual(self.client.patch("/api/projects/" + project, json={"name": "  ", "description": "not saved"}, headers=self.headers).status_code, 422)
        self.assertEqual(self.client.patch("/api/projects/missing", json={"name": "X"}, headers=self.headers).status_code, 404)
        idea_id = self.client.post("/api/ideas", json={"project_id": project, "title": "Before"}, headers=self.headers).json()["id"]
        response = self.client.patch("/api/ideas/" + idea_id, json={"title": "After", "status": "paused", "evidence_ids": ["e0"]}, headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        backup = self.client.post("/api/backups", headers=self.headers)
        self.assertEqual(backup.status_code, 201, backup.text)
        archive = self.client.get(backup.json()["download_url"])
        restored = self.client.post("/api/backups/restore", files={"file": ("backup.zip", archive.content, "application/zip")}, headers=self.headers)
        self.assertEqual(restored.status_code, 201, restored.text)
        connection = sqlite3.connect(str(Path(restored.json()["restore_path"]) / "library.sqlite3"))
        try:
            self.assertEqual(connection.execute("SELECT name,description FROM projects WHERE id=?", (project,)).fetchone(), ("Changed", "project description"))
            self.assertEqual(connection.execute("SELECT title,status FROM ideas WHERE id=?", (idea_id,)).fetchone(), ("After", "paused"))
            self.assertEqual(connection.execute("SELECT evidence_id FROM idea_evidence WHERE idea_id=?", (idea_id,)).fetchone()[0], "e0")
            self.assertEqual(connection.execute("SELECT note FROM evidence WHERE id='e0'").fetchone()[0], "original note")
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
