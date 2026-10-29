"""Exercise library search pagination with an isolated mock browser DOM."""
import shutil
import subprocess
import unittest
from pathlib import Path


class LocalSearchUITests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node.js is required for the browser logic test')
    def test_pagination_navigation_and_stale_responses(self):
        script = Path(__file__).resolve().parents[3] / 'scripts' / 'tests' / 'local_search_ui.cjs'
        subprocess.run(['node', str(script)], check=True, capture_output=True, text=True)
