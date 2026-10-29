"""Manual paper form and PDF-free reader in an isolated mock DOM."""
import shutil
import subprocess
import unittest
from pathlib import Path


class ManualPaperUITests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node.js is required for the browser logic test')
    def test_manual_paper_form_and_reader(self):
        script = Path(__file__).resolve().parents[3] / 'scripts' / 'tests' / 'manual_paper_ui.cjs'
        subprocess.run(['node', str(script)], check=True, capture_output=True, text=True)
