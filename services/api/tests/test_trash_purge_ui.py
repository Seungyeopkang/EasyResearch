"""Trash permanent-delete confirmation in an isolated mock DOM."""
import shutil
import subprocess
import unittest
from pathlib import Path


class TrashPurgeUITests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node.js is required for the browser logic test')
    def test_trash_purge_confirmation(self):
        script = Path(__file__).resolve().parents[3] / 'scripts' / 'tests' / 'trash_purge_ui.cjs'
        subprocess.run(['node', str(script)], check=True, capture_output=True, text=True)
