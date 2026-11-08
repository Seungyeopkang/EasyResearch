"""Deep-link hash parsing and reader keyboard shortcuts in an isolated mock DOM."""
import shutil
import subprocess
import unittest
from pathlib import Path


class DeepLinkUITests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node.js is required for the browser logic test')
    def test_deep_link_and_reader_keys(self):
        script = Path(__file__).resolve().parents[3] / 'scripts' / 'tests' / 'deep_link_ui.cjs'
        subprocess.run(['node', str(script)], check=True, capture_output=True, text=True)
