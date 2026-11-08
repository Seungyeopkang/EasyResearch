"""Exercise the continuous PDF viewer (virtual pages, near rendering, selection, races) in a mock DOM."""
import shutil
import subprocess
import unittest
from pathlib import Path


class PDFViewerContinuousUITests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node.js is required for the browser logic test')
    def test_continuous_viewer_rendering_selection_and_races(self):
        script = Path(__file__).resolve().parents[3] / 'scripts' / 'tests' / 'pdf_viewer_continuous.cjs'
        subprocess.run(['node', str(script)], check=True, capture_output=True, text=True, timeout=60)


if __name__ == '__main__':
    unittest.main()
