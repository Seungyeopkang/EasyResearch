"""Exercise project note draft recovery and conflict state without user data."""
import shutil
import subprocess
import unittest
from pathlib import Path


class ProjectNoteUITests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node.js is required for the browser logic test')
    def test_drafts_and_conflicts(self):
        script = Path(__file__).resolve().parents[3] / 'scripts' / 'tests' / 'project_note_conflict.cjs'
        subprocess.run(['node', str(script)], check=True, capture_output=True, text=True)
