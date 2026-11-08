"""Corrupted backups are rejected with 4xx and leave the live library untouched."""
import hashlib
import io
import json
import os
import re
import sys
import tempfile
import unittest
import uuid
import warnings
import zipfile
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from test_api_integration import app, pdf_bytes

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
import open_restored  # noqa: E402

HANGUL = re.compile(r"[가-힣]")


class BackupFailureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="easyresearch-backup-failures-")
        self.root = Path(self.temp.name)
        self.env = patch.dict(os.environ, {"EASYRESEARCH_DATA_DIR": self.temp.name})
        self.env.start()
        self.client = TestClient(app)
        self.client.__enter__()
        self.headers = {"X-EasyResearch": "1"}
        self.archive = self.make_backup()
        self.entries = self.read_entries(self.archive)
        self.pdf_name = next(name for name, _ in self.entries if name.startswith("files/") and name.endswith(".pdf"))

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.env.stop()
        self.temp.cleanup()

    # helpers

    def make_backup(self):
        project = self.client.post("/api/projects", json={"name": "failure sample"}, headers=self.headers).json()
        upload = self.client.post("/api/papers/import", data={"project_id": project["id"]},
                                  files={"file": ("paper.pdf", pdf_bytes(), "application/pdf")}, headers=self.headers)
        self.assertEqual(upload.status_code, 201, upload.text)
        created = self.client.post("/api/backups", headers=self.headers)
        self.assertEqual(created.status_code, 201, created.text)
        return self.client.get(created.json()["download_url"]).content

    @staticmethod
    def read_entries(archive):
        with zipfile.ZipFile(io.BytesIO(archive)) as source:
            return [(info.filename, source.read(info.filename)) for info in source.infolist()]

    @staticmethod
    def build(entries):
        out = io.BytesIO()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)  # duplicate-name warning is expected for case 7
            with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
                for name, data in entries:
                    z.writestr(name, data)
        return out.getvalue()

    def replace_entry(self, name, data):
        return [(n, data if n == name else d) for n, d in self.entries]

    def manifest(self):
        return json.loads(dict(self.entries)["manifest.json"])

    def with_manifest(self, manifest):
        return self.replace_entry("manifest.json", json.dumps(manifest).encode("utf-8"))

    def snapshot(self):
        """Hash the live library and everything else except staging, restore and the OS-locked server.lock."""
        digest = {}
        for path in sorted(self.root.rglob("*")):
            rel = path.relative_to(self.root)
            if rel.parts and rel.parts[0] in ("tmp", "restores") or rel.as_posix() == "server.lock":
                continue
            if path.is_file():
                digest[rel.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
        return digest

    def restore_names(self):
        folder = self.root / "restores"
        return sorted(p.name for p in folder.iterdir()) if folder.exists() else []

    def assert_rejected(self, data):
        before_snapshot = self.snapshot()
        before_restores = self.restore_names()
        for endpoint in ("/api/backups/inspect", "/api/backups/restore"):
            with self.subTest(endpoint=endpoint):
                response = self.client.post(endpoint, files={"file": ("backup.zip", data, "application/zip")},
                                            headers=self.headers)
                self.assertTrue(400 <= response.status_code < 500, response.text)
                self.assertRegex(response.json().get("detail", ""), HANGUL)
        self.assertEqual(self.restore_names(), before_restores)
        self.assertEqual(self.snapshot(), before_snapshot)
        self.assertEqual(list((self.root / "tmp").glob("restore-*")), [])

    # corrupted variants

    def test_truncated_zip_is_rejected(self):
        self.assert_rejected(self.archive[: int(len(self.archive) * 0.7)])

    def test_pdf_bytes_changed_with_manifest_hash_unchanged_is_rejected(self):
        original = dict(self.entries)[self.pdf_name]
        mutated = original[:-1] + bytes([original[-1] ^ 0x01])
        self.assertEqual(len(mutated), len(original))
        self.assert_rejected(self.build(self.replace_entry(self.pdf_name, mutated)))

    def test_manifest_lists_pdf_missing_from_zip_is_rejected(self):
        entries = [(n, d) for n, d in self.entries if n != self.pdf_name]
        self.assert_rejected(self.build(entries))

    def test_unlisted_extra_entry_is_rejected(self):
        self.assert_rejected(self.build(self.entries + [("notes/extra.txt", b"not in manifest")]))

    def test_database_sha256_mismatch_is_rejected(self):
        manifest = self.manifest()
        manifest["database_sha256"] = "0" * 64
        self.assert_rejected(self.build(self.with_manifest(manifest)))

    def test_path_traversal_entry_name_is_rejected(self):
        evil = "files/../../evil.pdf"
        entries = [(evil if n == self.pdf_name else n, d) for n, d in self.entries]
        manifest = self.manifest()
        for item in manifest["files"]:
            if item["path"] == self.pdf_name:
                item["path"] = evil
        entries = [(n, json.dumps(manifest).encode("utf-8") if n == "manifest.json" else d) for n, d in entries]
        self.assert_rejected(self.build(entries))

    def test_duplicate_entry_names_are_rejected(self):
        self.assert_rejected(self.build(self.entries + [(self.pdf_name, dict(self.entries)[self.pdf_name])]))

    def test_non_zip_upload_is_rejected(self):
        self.assert_rejected(b"this is plainly not a zip archive\n" * 20)

    # interruption and restored-library discovery

    def test_interrupted_publish_returns_server_error_and_is_not_listed(self):
        before = self.snapshot()
        rename = os.rename
        attempts = []

        def fail_after_first(source, target):
            attempts.append((source, target))
            if len(attempts) == 2:
                raise OSError("simulated interruption during restore publishing")
            return rename(source, target)

        with patch("app.main.os.rename", side_effect=fail_after_first):
            response = self.client.post("/api/backups/restore", headers=self.headers,
                                        files={"file": ("backup.zip", self.archive, "application/zip")})
        self.assertEqual(len(attempts), 2, "the simulated interruption was not reached")
        self.assertTrue(response.status_code >= 500, response.text)
        self.assertEqual(open_restored.restored_libraries(self.root), [])
        self.assertEqual(self.restore_names(), [])
        self.assertEqual(self.snapshot(), before)

    def test_restore_folder_with_incomplete_marker_is_excluded(self):
        complete = self.root / "restores" / str(uuid.uuid4())
        complete.mkdir(parents=True)
        (complete / "library.sqlite3").write_bytes(b"placeholder")
        self.assertEqual(open_restored.restored_libraries(self.root), [complete])

        marked = self.root / "restores" / str(uuid.uuid4())
        marked.mkdir(parents=True)
        (marked / "library.sqlite3").write_bytes(b"placeholder")
        (marked / ".incomplete").write_bytes(b"incomplete restore\n")
        listed = open_restored.restored_libraries(self.root)
        self.assertNotIn(marked, listed)
        self.assertEqual(listed, [complete])


if __name__ == "__main__":
    unittest.main()
