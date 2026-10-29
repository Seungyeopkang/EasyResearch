"""Backup inspection and restore do not touch the existing library."""
import io
import errno
import hashlib
import json
import os
import sqlite3
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from fastapi import UploadFile

from test_api_integration import app, pdf_bytes
from app import storage


class BackupInspectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="easyresearch-backup-")
        self.env = patch.dict(os.environ, {"EASYRESEARCH_DATA_DIR": self.temp.name})
        self.env.start()
        self.client = TestClient(app)
        self.client.__enter__()
        self.headers = {"X-EasyResearch": "1"}

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.env.stop()
        self.temp.cleanup()

    def backup(self):
        project = self.client.post("/api/projects", json={"name": "sample"}, headers=self.headers).json()
        upload = self.client.post("/api/papers/import", data={"project_id": project["id"]},
                                  files={"file": ("paper.pdf", pdf_bytes(), "application/pdf")}, headers=self.headers)
        self.assertEqual(upload.status_code, 201, upload.text)
        result = self.client.post("/api/backups", headers=self.headers)
        self.assertEqual(result.status_code, 201, result.text)
        return self.client.get(result.json()["download_url"]).content

    def inspect(self, data):
        return self.client.post("/api/backups/inspect", files={"file": ("backup.zip", data, "application/zip")}, headers=self.headers)

    def test_inspect_returns_verified_summary_without_creating_a_restore(self):
        archive = self.backup()
        original_projects = self.client.get("/api/projects").json()
        result = self.inspect(archive)
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()["status"], "verified")
        self.assertEqual(result.json()["file_count"], 1)
        self.assertEqual(result.json()["project_count"], 1)
        self.assertEqual(result.json()["paper_count"], 1)
        self.assertGreater(result.json()["total_file_bytes"], 0)
        self.assertFalse((Path(self.temp.name) / "restores").exists())
        self.assertEqual(self.client.get("/api/projects").json(), original_projects)
        self.assertFalse(list((Path(self.temp.name) / "tmp").glob("restore-*")))

    def test_backup_does_not_claim_success_for_unsupported_schema(self):
        self.client.post("/api/projects", json={"name": "보존할 프로젝트"}, headers=self.headers)
        with storage.transaction() as con:
            con.execute("CREATE INDEX custom_local_index ON papers(title)")
        before = self.client.get("/api/projects").json()
        result = self.client.post("/api/backups", headers=self.headers)
        self.assertEqual(result.status_code, 409, result.text)
        self.assertIn("복원 형식", result.json()["detail"])
        self.assertEqual(self.client.get("/api/projects").json(), before)
        with storage.transaction() as con:
            self.assertIsNotNone(con.execute("SELECT name FROM sqlite_master WHERE name='custom_local_index'").fetchone())
        self.assertEqual(list((Path(self.temp.name) / "backups").glob("*.zip")), [])

    def test_inspect_distinguishes_missing_and_modified_pdf(self):
        archive = self.backup()
        with zipfile.ZipFile(io.BytesIO(archive)) as original:
            entries = {name: original.read(name) for name in original.namelist()}
        pdf = next(name for name in entries if name.endswith(".pdf"))
        for replacement, expected in [(None, "필요한 파일"), (b"changed", "PDF가 손상")]:
            out = io.BytesIO()
            with zipfile.ZipFile(out, "w") as z:
                for name, data in entries.items():
                    if name == pdf:
                        if replacement is None:
                            continue
                        data = replacement
                    z.writestr(name, data)
            result = self.inspect(out.getvalue())
            self.assertEqual(result.status_code, 400, result.text)
            self.assertIn(expected, result.json()["detail"])
            self.assertFalse((Path(self.temp.name) / "restores").exists())

    def test_restore_does_not_overwrite_a_preexisting_directory(self):
        archive = self.backup()
        restore_id = "b1a3fc7d-32d4-429c-861c-6f0fcc503d47"
        target = Path(self.temp.name) / "restores" / restore_id
        target.mkdir(parents=True)
        (target / "keep.txt").write_text("original", encoding="utf-8")
        with patch.object(storage, "new_id", return_value=restore_id):
            result = self.client.post("/api/backups/restore", files={"file": ("backup.zip", archive, "application/zip")}, headers=self.headers)
        self.assertEqual(result.status_code, 409, result.text)
        self.assertEqual((target / "keep.txt").read_text(encoding="utf-8"), "original")
        self.assertFalse((target / "library.sqlite3").exists())

    def test_storage_full_during_restore_keeps_existing_library(self):
        archive = self.backup()
        before = self.client.get("/api/projects").json()
        with patch("app.main.os.rename", side_effect=OSError(errno.ENOSPC, "no space")):
            response = self.client.post("/api/backups/restore", files={"file": ("backup.zip", archive, "application/zip")}, headers=self.headers)
        self.assertEqual(response.status_code, 507, response.text)
        self.assertIn("저장 공간", response.json()["detail"])
        self.assertEqual(self.client.get("/api/projects").json(), before)
        self.assertEqual(list((Path(self.temp.name) / "restores").iterdir()), [])

    def test_partial_restore_publication_is_cleaned_on_failure(self):
        archive = self.backup()
        before = self.client.get("/api/projects").json()
        rename = os.rename
        attempts = []
        def fail_second(source, target):
            attempts.append((source, target))
            if len(attempts) == 2:
                raise OSError(errno.ENOSPC, "no space")
            return rename(source, target)
        with patch("app.main.os.rename", side_effect=fail_second):
            response = self.client.post("/api/backups/restore", files={"file": ("backup.zip", archive, "application/zip")}, headers=self.headers)
        self.assertEqual(response.status_code, 507, response.text)
        self.assertEqual(len(attempts), 2)
        self.assertEqual(list((Path(self.temp.name) / "restores").iterdir()), [])
        self.assertEqual(self.client.get("/api/projects").json(), before)

    def test_interruption_during_publish_leaves_an_unopenable_marker(self):
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
        import open_restored
        from app.main import _inspect_or_restore_backup
        archive = self.backup()
        before = self.client.get("/api/projects").json()
        rename = os.rename
        attempts = []

        class Interruption(BaseException):
            pass

        def interrupted(source, target):
            attempts.append((source, target))
            if len(attempts) == 2:
                raise Interruption()
            return rename(source, target)

        upload = UploadFile(filename="backup.zip", file=io.BytesIO(archive))
        with patch("app.main.os.rename", side_effect=interrupted):
            with self.assertRaises(Interruption):
                _inspect_or_restore_backup(upload, True)
        restored = list((Path(self.temp.name) / "restores").iterdir())
        self.assertEqual(len(restored), 1)
        self.assertTrue((restored[0] / ".incomplete").is_file())
        self.assertEqual(open_restored.restored_libraries(Path(self.temp.name)), [])
        self.assertEqual(self.client.get("/api/projects").json(), before)

    def test_storage_full_creating_backup_is_reported(self):
        with patch("app.main._create_backup", side_effect=OSError(errno.ENOSPC, "no space")):
            response = self.client.post("/api/backups", headers=self.headers)
        self.assertEqual(response.status_code, 507, response.text)
        self.assertIn("저장 공간", response.json()["detail"])
        with patch("app.main._create_backup", side_effect=sqlite3.OperationalError("database or disk is full")):
            response = self.client.post("/api/backups", headers=self.headers)
        self.assertEqual(response.status_code, 507, response.text)
        self.assertIn("저장 공간", response.json()["detail"])

    def archive_with_database_version(self, archive, version):
        with zipfile.ZipFile(io.BytesIO(archive)) as original:
            entries = {name: original.read(name) for name in original.namelist()}
        db = Path(self.temp.name) / "test-db.sqlite3"
        db.write_bytes(entries["library.sqlite3"])
        connection = sqlite3.connect(str(db))
        try:
            if version <= 4:
                connection.execute("DROP TABLE IF EXISTS paper_version_trash")
                connection.execute("DROP TABLE IF EXISTS paper_version_state")
            if version <= 3:
                for table in ("revision_ocr_source", "evidence_ocr_source"):
                    connection.execute("DROP TABLE IF EXISTS " + table)
            # A v0 or v1 archive must have the original v1 structure; changing
            # only the version of the current database is not a valid fixture.
            if version in (0, 1):
                for table in ("project_paper_notes", "project_trash", "evidence_trash", "link_trash", "evidence_provenance", "revision_provenance", "paper_versions", "page_extraction_details"):
                    connection.execute("DROP TABLE IF EXISTS " + table)
            elif version == 2:
                for table in ("paper_versions", "page_extraction_details"):
                    connection.execute("DROP TABLE IF EXISTS " + table)
                connection.execute("INSERT INTO project_paper_notes(project_id,paper_id,note) SELECT project_id,paper_id,'v2 기록' FROM project_papers LIMIT 1")
            connection.execute(f"PRAGMA user_version={version}")
            connection.commit()
        finally:
            connection.close()
        entries["library.sqlite3"] = db.read_bytes()
        db.unlink()
        manifest = json.loads(entries["manifest.json"])
        manifest["database_sha256"] = hashlib.sha256(entries["library.sqlite3"]).hexdigest()
        entries["manifest.json"] = json.dumps(manifest).encode()
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w") as z:
            for name, content in entries.items():
                z.writestr(name, content)
        return out.getvalue()

    def test_old_version_is_migrated_only_in_restored_copy(self):
        archive = self.archive_with_database_version(self.backup(), 0)
        before = hashlib.sha256(archive).hexdigest()
        inspected = self.inspect(archive)
        self.assertEqual(inspected.status_code, 200, inspected.text)
        self.assertEqual(inspected.json()["database_version"], 0)
        self.assertEqual(inspected.json()["target_database_version"], storage.SCHEMA_VERSION)
        self.assertTrue(inspected.json()["requires_migration"])
        restored = self.client.post("/api/backups/restore", files={"file": ("backup.zip", archive, "application/zip")}, headers=self.headers)
        self.assertEqual(restored.status_code, 201, restored.text)
        connection = sqlite3.connect(str(Path(restored.json()["restore_path"]) / "library.sqlite3"))
        try:
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], storage.SCHEMA_VERSION)
            self.assertEqual(connection.execute("SELECT count(*) FROM projects").fetchone()[0], 1)
        finally:
            connection.close()
        self.assertEqual(hashlib.sha256(archive).hexdigest(), before)

    def test_v1_backup_is_migrated_to_current_version(self):
        archive = self.archive_with_database_version(self.backup(), 1)
        result = self.inspect(archive)
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()["database_version"], 1)
        self.assertTrue(result.json()["requires_migration"])
        restored = self.client.post("/api/backups/restore", files={"file": ("backup.zip", archive, "application/zip")}, headers=self.headers)
        self.assertEqual(restored.status_code, 201, restored.text)
        with sqlite3.connect(str(Path(restored.json()["restore_path"]) / "library.sqlite3")) as con:
            self.assertEqual(con.execute("PRAGMA user_version").fetchone()[0], storage.SCHEMA_VERSION)
            self.assertEqual(con.execute("SELECT count(*) FROM projects").fetchone()[0], 1)

    def test_v2_backup_preserves_project_notes_when_migrated(self):
        archive = self.archive_with_database_version(self.backup(), 2)
        result = self.inspect(archive)
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()["database_version"], 2)
        restored = self.client.post("/api/backups/restore", files={"file": ("backup.zip", archive, "application/zip")}, headers=self.headers)
        self.assertEqual(restored.status_code, 201, restored.text)
        with sqlite3.connect(str(Path(restored.json()["restore_path"]) / "library.sqlite3")) as con:
            self.assertEqual(con.execute("PRAGMA user_version").fetchone()[0], storage.SCHEMA_VERSION)
            self.assertEqual(con.execute("SELECT note FROM project_paper_notes").fetchone()[0], "v2 기록")

    def test_v4_backup_restores_extra_pdf_version_without_changing_archive(self):
        self.backup()
        with storage.transaction() as con:
            paper = con.execute('SELECT id FROM papers LIMIT 1').fetchone()['id']
        alternative = pdf_bytes() + b'\n% alternative version\n'
        upload = self.client.post(f'/api/papers/{paper}/versions', headers=self.headers,
                                  data={'label':'old version'}, files={'file':('other.pdf',alternative,'application/pdf')})
        self.assertEqual(upload.status_code,201,upload.text)
        created = self.client.post('/api/backups',headers=self.headers)
        self.assertEqual(created.status_code,201,created.text)
        current = self.client.get(created.json()['download_url']).content
        archive = self.archive_with_database_version(current,4)
        before = hashlib.sha256(archive).hexdigest()
        inspected = self.inspect(archive)
        self.assertEqual(inspected.status_code,200,inspected.text)
        self.assertEqual(inspected.json()['database_version'],4)
        self.assertTrue(inspected.json()['requires_migration'])
        restored = self.client.post('/api/backups/restore',headers=self.headers,
                                    files={'file':('backup.zip',archive,'application/zip')})
        self.assertEqual(restored.status_code,201,restored.text)
        root = Path(restored.json()['restore_path'])
        with sqlite3.connect(str(root/'library.sqlite3')) as con:
            self.assertEqual(con.execute('PRAGMA user_version').fetchone()[0],storage.SCHEMA_VERSION)
            label,key = con.execute('SELECT v.label,f.storage_key FROM paper_versions v JOIN files f ON f.id=v.file_id').fetchone()
            self.assertEqual(label,'old version')
            self.assertEqual(con.execute('SELECT count(*) FROM paper_version_trash').fetchone()[0],0)
        self.assertEqual((root/key).read_bytes(),alternative)
        self.assertEqual(hashlib.sha256(archive).hexdigest(),before)

    def test_v3_backup_migrates_to_current_without_changing_archive(self):
        archive = self.archive_with_database_version(self.backup(), 3)
        digest = hashlib.sha256(archive).hexdigest()
        inspected = self.inspect(archive)
        self.assertEqual(inspected.status_code, 200, inspected.text)
        self.assertEqual(inspected.json()['database_version'], 3)
        self.assertTrue(inspected.json()['requires_migration'])
        restored = self.client.post('/api/backups/restore', files={'file': ('backup.zip', archive, 'application/zip')}, headers=self.headers)
        self.assertEqual(restored.status_code, 201, restored.text)
        con = sqlite3.connect(str(Path(restored.json()['restore_path']) / 'library.sqlite3'))
        try:
            self.assertEqual(con.execute('PRAGMA user_version').fetchone()[0], storage.SCHEMA_VERSION)
            self.assertEqual(con.execute('SELECT count(*) FROM evidence_ocr_source').fetchone()[0], 0)
        finally:
            con.close()
        self.assertEqual(hashlib.sha256(archive).hexdigest(), digest)

    def test_newer_database_version_is_rejected_without_a_restore(self):
        archive = self.archive_with_database_version(self.backup(), storage.SCHEMA_VERSION + 1)
        result = self.inspect(archive)
        self.assertEqual(result.status_code, 400, result.text)
        self.assertIn("버전", result.json()["detail"])
        self.assertFalse((Path(self.temp.name) / "restores").exists())


if __name__ == "__main__":
    unittest.main()
