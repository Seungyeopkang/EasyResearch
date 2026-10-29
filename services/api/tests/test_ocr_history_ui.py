"""OCR history and out-of-order reader responses in a mock browser DOM."""
import shutil
import subprocess
import unittest
from pathlib import Path


class OCRHistoryUITests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node.js is required for the browser logic test')
    def test_ocr_history_and_reader_races(self):
        script = Path(__file__).resolve().parents[3] / 'scripts' / 'tests' / 'ocr_history_ui.cjs'
        subprocess.run(['node', str(script)], check=True, capture_output=True, text=True)
