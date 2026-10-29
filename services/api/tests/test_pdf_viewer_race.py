"""Regression checks for switching or closing PDFs while rendering."""
from pathlib import Path
import shutil
import subprocess
import unittest


class PDFViewerRaceTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Node.js is needed for the browser module test")
    def test_pending_loads_do_not_restore_stale_documents(self):
        root = Path(__file__).resolve().parents[3]
        result = subprocess.run([shutil.which("node"), str(root / "scripts" / "tests" / "pdf_viewer_race.cjs")],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
