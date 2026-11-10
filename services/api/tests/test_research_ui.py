"""Run the research assistant browser-logic checks (apps/web/research.js) with Node.js."""
import shutil
import subprocess
import unittest
from pathlib import Path


class ResearchUITests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node.js is required for the browser logic test')
    def test_research_helpers_layout_and_preview_gate(self):
        script = Path(__file__).resolve().parent / 'research_ui.test.cjs'
        result = subprocess.run(['node', str(script)], capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        self.assertIn('research_ui ok', result.stdout)


if __name__ == '__main__':
    unittest.main()
