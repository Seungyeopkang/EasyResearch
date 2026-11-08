"""Exercise the built-in Translator wrapper (availability, chunking, errors) with a mocked Translator API."""
import shutil
import subprocess
import unittest
from pathlib import Path


class TranslateUITests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node.js is required for the browser logic test')
    def test_translator_wrapper_chunking_availability_and_errors(self):
        script = Path(__file__).resolve().parents[3] / 'scripts' / 'tests' / 'translate_module.cjs'
        subprocess.run(['node', str(script)], check=True, capture_output=True, text=True, timeout=60)


if __name__ == '__main__':
    unittest.main()
