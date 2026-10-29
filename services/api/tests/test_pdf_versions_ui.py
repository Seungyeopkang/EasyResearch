"""PDF version actions in an isolated mock browser DOM."""
import shutil
import subprocess
import unittest
from pathlib import Path


class PDFVersionsUITests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node.js is required for the browser logic test')
    def test_version_actions(self):
        script = Path(__file__).resolve().parents[3] / 'scripts' / 'tests' / 'pdf_versions_ui.cjs'
        subprocess.run(['node', str(script)], check=True, capture_output=True, text=True)
