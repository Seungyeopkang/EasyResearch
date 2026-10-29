"""OCR language selection and request state in an isolated mock DOM."""
import shutil
import subprocess
import unittest
from pathlib import Path


class OCRLanguageUITests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node.js is required for the browser logic test')
    def test_ocr_language_selection_and_state(self):
        script = Path(__file__).resolve().parents[3] / 'scripts' / 'tests' / 'ocr_language_ui.cjs'
        subprocess.run(['node', str(script)], check=True, capture_output=True, text=True)
