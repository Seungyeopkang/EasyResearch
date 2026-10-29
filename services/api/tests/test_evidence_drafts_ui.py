import shutil
import subprocess
import unittest
from pathlib import Path


class EvidenceDraftTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node is required for browser logic tests')
    def test_drafts_are_isolated_and_recoverable(self):
        root = Path(__file__).resolve().parents[3]
        subprocess.run(['node', str(root / 'scripts/tests/evidence_drafts.cjs')],
                       cwd=root, check=True, timeout=30)
