"""Run the project-independent library and reader browser-logic checks with Node.js."""
import shutil
import subprocess
import unittest
from pathlib import Path


class LibraryReaderUITests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node.js is required for the browser logic test')
    def test_library_reader_progress_translation_categories_and_links(self):
        script = Path(__file__).resolve().parents[3] / 'scripts' / 'tests' / 'library_reader_ui.cjs'
        subprocess.run(['node', str(script)], check=True, capture_output=True, text=True, timeout=60)


if __name__ == '__main__':
    unittest.main()
