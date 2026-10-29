"""Launcher tests do not touch the user's library or use external services."""
import importlib.util
import io
import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("easyresearch_launcher", ROOT / "scripts" / "launch.py")
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


class Handler(BaseHTTPRequestHandler):
    payload = {"status": "ok", "pdf_parser": "pypdf"}

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(json.dumps(self.payload).encode())

    def log_message(self, *args):
        pass


class LauncherTests(unittest.TestCase):
    def test_probe_identifies_local_app_and_other_listener(self):
        server = HTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            port = server.server_address[1]
            self.assertEqual(launcher.probe_server(port=port), "easyresearch")
            Handler.payload = {"status": "ok"}
            self.assertEqual(launcher.probe_server(port=port), "other")
        finally:
            Handler.payload = {"status": "ok", "pdf_parser": "pypdf"}
            server.shutdown()
            server.server_close()
            thread.join()
        self.assertEqual(launcher.probe_server(port=port), "free")

    def test_existing_server_opens_without_starting_another(self):
        with patch.object(launcher, "probe_server", return_value="easyresearch"), \
             patch.object(launcher, "open_browser") as browser, \
             patch.object(launcher.subprocess, "Popen") as start, \
             patch("sys.stdout", new_callable=io.StringIO) as output:
            self.assertEqual(launcher.main(), 0)
            browser.assert_called_once()
            start.assert_not_called()
            self.assertIn("자료 폴더", output.getvalue())

    def test_other_listener_never_opens_browser_or_starts_server(self):
        with patch.object(launcher, "probe_server", return_value="other"), \
             patch.object(launcher, "open_browser") as browser, \
             patch.object(launcher.subprocess, "Popen") as start:
            self.assertEqual(launcher.main(), 1)
            browser.assert_not_called()
            start.assert_not_called()

    def test_missing_dependency_is_explained_without_installing(self):
        with patch.object(launcher, "probe_server", return_value="free"), \
             patch.object(launcher, "missing_packages", return_value=["pypdf"]), \
             patch.object(launcher.subprocess, "Popen") as start, \
             patch("sys.stdout", new_callable=io.StringIO) as output:
            self.assertEqual(launcher.main(), 1)
            self.assertIn("pypdf", output.getvalue())
            self.assertIn("requirements.txt", output.getvalue())
            start.assert_not_called()

    def test_start_failure_does_not_open_browser(self):
        process = Mock()
        process.stderr = iter(["ERROR: address already in use\n"])
        process.poll.return_value = 1
        with patch.object(launcher, "probe_server", return_value="free"), \
             patch.object(launcher, "missing_packages", return_value=[]), \
             patch.object(launcher.subprocess, "Popen", return_value=process), \
             patch.object(launcher, "open_browser") as browser:
            self.assertEqual(launcher.main(), 1)
            browser.assert_not_called()

    def test_opens_only_after_own_server_reports_listening(self):
        process = Mock()
        process.stderr = iter(["INFO: Uvicorn running on http://127.0.0.1:8000\n"])
        process.poll.return_value = None

        def finished():
            process.poll.return_value = 0
            return 0

        process.wait.side_effect = finished
        with patch.object(launcher, "probe_server", side_effect=["free", "easyresearch"]), \
             patch.object(launcher, "missing_packages", return_value=[]), \
             patch.object(launcher.subprocess, "Popen", return_value=process) as start, \
             patch.object(launcher, "open_browser") as browser:
            self.assertEqual(launcher.main(), 0)
            browser.assert_called_once()
            self.assertIn("--no-use-colors", start.call_args.args[0])

    def test_browser_failure_displays_local_address(self):
        with patch.object(launcher.webbrowser, "open", return_value=False), \
             patch("sys.stdout", new_callable=io.StringIO) as output:
            launcher.open_browser()
            self.assertIn(launcher.URL, output.getvalue())

    def test_ctrl_c_waits_for_child_and_terminates_if_it_stalls(self):
        process = Mock()
        process.stderr = iter(['INFO: Uvicorn running on http://127.0.0.1:8000\n'])
        process.poll.return_value = None
        process.wait.side_effect = [KeyboardInterrupt(), subprocess.TimeoutExpired('uvicorn', 10), 0]
        process.terminate.side_effect = lambda: setattr(process.poll, 'return_value', 0)
        with patch.object(launcher, 'probe_server', side_effect=['free', 'easyresearch']), \
             patch.object(launcher, 'missing_packages', return_value=[]), \
             patch.object(launcher.subprocess, 'Popen', return_value=process), \
             patch.object(launcher, 'open_browser'), patch('sys.stdout', new_callable=io.StringIO):
            self.assertEqual(launcher.main(), 0)
        process.terminate.assert_called_once()
        self.assertEqual(process.wait.call_count, 3)

    @unittest.skipUnless(os.name == 'nt', 'Windows command entry points')
    def test_windows_command_entry_points_refuse_a_busy_port(self):
        try:
            server = HTTPServer(('127.0.0.1', 8000), Handler)
        except OSError:
            self.skipTest('port 8000 is already occupied; will not touch that process')
        Handler.payload = {'status': 'not-easyresearch'}
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory(prefix='easyresearch-cmd-test-') as data:
                env = os.environ.copy()
                env['EASYRESEARCH_DATA_DIR'] = data
                for name in ('EasyResearch 시작.cmd', '복원 보관함 열기.cmd'):
                    with self.subTest(entry=name):
                        result = subprocess.run(['cmd.exe', '/d', '/c', str(ROOT / name)], cwd=str(ROOT), env=env,
                                                input='\n', text=True, encoding='utf-8', errors='replace',
                                                capture_output=True, timeout=15)
                        self.assertIn('8000', result.stdout, result.stdout + result.stderr)
                        self.assertEqual(os.listdir(data), [], 'busy port must not open or create a library')
        finally:
            Handler.payload = {'status': 'ok', 'pdf_parser': 'pypdf'}
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == "__main__":
    unittest.main()
