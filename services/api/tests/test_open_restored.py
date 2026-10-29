"""Restore picker tests use disposable libraries and never open a browser."""
import hashlib
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
import uuid
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "services" / "api"))
import launch
import open_restored
from app import storage


class RestoredLibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.id = str(uuid.uuid4())
        self.restored = self.root / "restores" / self.id
        self.restored.mkdir(parents=True)
        with patch.dict(os.environ, {"EASYRESEARCH_DATA_DIR": str(self.restored)}):
            storage.init_db()
            pdf = b"%PDF-1.4\nsynthetic"
            sha = hashlib.sha256(pdf).hexdigest()
            pdf_path = self.restored / "files" / sha[:2] / (sha + ".pdf")
            pdf_path.parent.mkdir(parents=True)
            pdf_path.write_bytes(pdf)
            with storage.transaction() as con:
                con.execute("INSERT INTO projects(id,name) VALUES('p','test')")
                con.execute("INSERT INTO files(id,sha256,size,storage_key) VALUES(?,?,?,?)",
                            ("f", sha, len(pdf), pdf_path.relative_to(self.restored).as_posix()))
        self.pdf = pdf_path

    def test_valid_restored_library_is_checked_read_only(self):
        before = (self.restored / "library.sqlite3").read_bytes()
        self.assertEqual(open_restored.validate_library(self.restored, self.root),
                         {"projects": 1, "papers": 0, "evidence": 0, "files": 1})
        self.assertEqual((self.restored / "library.sqlite3").read_bytes(), before)

    def test_changed_or_missing_pdf_is_rejected(self):
        self.pdf.write_bytes(b"%PDF-1.4\ncorrupted")
        with self.assertRaises(ValueError):
            open_restored.validate_library(self.restored, self.root)
        self.pdf.unlink()
        with self.assertRaises(OSError):
            open_restored.validate_library(self.restored, self.root)

    def test_only_uuid_directories_are_offered(self):
        (self.root / "restores" / "not-a-restore").mkdir()
        self.assertEqual(open_restored.restored_libraries(self.root), [self.restored])
        with self.assertRaises(ValueError):
            open_restored.validate_library(self.root / "restores" / "not-a-restore", self.root)

    def test_interrupted_restore_is_not_offered_or_opened(self):
        (self.restored / ".incomplete").write_text("interrupted", encoding="utf-8")
        self.assertEqual(open_restored.restored_libraries(self.root), [])
        with self.assertRaisesRegex(ValueError, "완료되지"):
            open_restored.validate_library(self.restored, self.root)
        self.assertTrue((self.restored / "library.sqlite3").exists())
        self.assertTrue(self.pdf.exists())

    def test_active_server_is_never_reused_for_restore(self):
        with patch.object(launch, "probe_server", return_value="easyresearch"), \
             patch.object(launch, "open_browser") as browser:
            self.assertEqual(launch.main(require_free=True), 1)
            browser.assert_not_called()
        with patch.object(open_restored.storage, "data_dir", return_value=self.root), \
             patch.object(launch, "probe_server", return_value="easyresearch"), \
             patch.object(launch, "main") as run:
            self.assertEqual(open_restored.main(), 1)
            run.assert_not_called()

    def test_selected_library_passes_path_only_to_child_launch(self):
        with patch.object(open_restored.storage, "data_dir", return_value=self.root), \
             patch.object(launch, "probe_server", return_value="free"), \
             patch.object(launch, "main", return_value=0) as run, \
             patch("builtins.input", return_value="1"), \
             patch.dict(os.environ, {}, clear=False):
            self.assertEqual(open_restored.main(), 0)
            self.assertEqual(os.environ["EASYRESEARCH_DATA_DIR"], str(self.restored))
            run.assert_called_once_with(require_free=True)

    def test_corrupt_library_never_launches(self):
        self.pdf.write_bytes(b"corrupt")
        with patch.object(open_restored.storage, "data_dir", return_value=self.root), \
             patch.object(launch, "probe_server", return_value="free"), \
             patch.object(launch, "main") as run, patch("builtins.input", return_value="1"), \
             patch("sys.stdout", new_callable=io.StringIO):
            self.assertEqual(open_restored.main(), 1)
            run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
