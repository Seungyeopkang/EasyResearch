import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import jobs, process_control, storage


@unittest.skipUnless(os.name == "nt", "Windows Job Object integration requires Windows")
class WindowsProcessControlTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="easyresearch-process-")
        self.root = Path(self.tmp.name)
        (self.root / "fixtureworker.py").write_text(
            "import pathlib, subprocess, sys, time\n"
            "marker = pathlib.Path(sys.argv[1])\n"
            "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'], "
            "stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)\n"
            "marker.write_text(str(child.pid), encoding='utf-8')\n"
            "time.sleep(60)\n", encoding="utf-8")
        self.marker = self.root / "started.txt"

    def tearDown(self):
        self.tmp.cleanup()

    def _wait_marker(self):
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if self.marker.exists():
                return int(self.marker.read_text(encoding="utf-8"))
            time.sleep(0.05)
        self.fail("worker did not start")

    def test_terminate_and_close_wait_for_worker_and_descendant(self):
        tree = process_control.start_windows_worker("fixtureworker", [str(self.marker)], self.root)
        try:
            child = self._wait_marker()
            self.assertGreater(child, 0)
            # Some Windows Python launchers introduce an extra process.
            self.assertGreaterEqual(process_control._active(tree._job), 2)
            tree.terminate()
            self.assertEqual(process_control._active(tree._job), 0)
            self.assertIsNotNone(tree.poll())
        finally:
            tree.close()

    def test_assignment_failure_never_releases_worker(self):
        with patch.object(process_control, "_assign", side_effect=process_control.ProcessControlError("synthetic assignment failure")):
            with self.assertRaises(process_control.ProcessControlError):
                process_control.start_windows_worker("fixtureworker", [str(self.marker)], self.root)
        self.assertFalse(self.marker.exists())

    def test_parent_crash_closes_job_and_stops_descendant(self):
        api_dir = Path(__file__).resolve().parents[1]
        supervisor = (
            "import sys,time\n"
            "from app.process_control import start_windows_worker\n"
            "tree=start_windows_worker('fixtureworker',[sys.argv[2]],sys.argv[1])\n"
            "time.sleep(60)\n"
        )
        process = subprocess.Popen([sys.executable, "-c", supervisor, str(self.root), str(self.marker)],
                                   cwd=str(api_dir), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        try:
            child = self._wait_marker()
            import ctypes
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
            kernel.OpenProcess.restype = ctypes.c_void_p
            kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
            kernel.WaitForSingleObject.restype = ctypes.c_uint32
            kernel.CloseHandle.argtypes = [ctypes.c_void_p]
            kernel.CloseHandle.restype = ctypes.c_int
            handle = kernel.OpenProcess(0x00100000, False, child)  # SYNCHRONIZE
            self.assertTrue(handle, "could not open descendant process")
            try:
                process.kill()
                process.wait(timeout=5)
                self.assertEqual(kernel.WaitForSingleObject(handle, 5000), 0, "descendant remained alive after parent exited")
            finally:
                kernel.CloseHandle(handle)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)

    def test_input_validation(self):
        with self.assertRaises(ValueError):
            process_control.start_windows_worker("../../bad", [], self.root)
        with self.assertRaises(ValueError):
            process_control.start_windows_worker("fixtureworker", [1], self.root)

    def test_job_cancellation_stops_descendants_and_removes_attempt_files(self):
        data = self.root / "data"
        original_start = process_control.start_windows_worker
        with patch.dict(os.environ, {"EASYRESEARCH_DATA_DIR": str(data)}):
            storage.init_db()
            with storage.transaction() as con:
                job_id = jobs.enqueue_pdf(con, "fixture")

            def start_fixture(module, args, root, env=None):
                return original_start("fixtureworker", [str(self.marker)], self.root, env=env)

            with patch.object(jobs, "start_windows_worker", side_effect=start_fixture):
                jobs.start()
                try:
                    child_pid = self._wait_marker()
                    import ctypes
                    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
                    kernel.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
                    kernel.OpenProcess.restype = ctypes.c_void_p
                    kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
                    kernel.WaitForSingleObject.restype = ctypes.c_uint32
                    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
                    handle = kernel.OpenProcess(0x00100000, False, child_pid)
                    self.assertTrue(handle)
                    try:
                        jobs.cancel(job_id)
                        deadline = time.monotonic() + 15
                        while time.monotonic() < deadline:
                            with storage.transaction() as con:
                                state = con.execute("SELECT status FROM jobs WHERE id=?", (job_id,)).fetchone()[0]
                            attempts = list((data / "tmp" / "jobs").glob("*"))
                            if state == "cancelled" and not attempts:
                                break
                            time.sleep(0.05)
                        self.assertEqual(state, "cancelled")
                        self.assertEqual(attempts, [])
                        self.assertEqual(kernel.WaitForSingleObject(handle, 1000), 0)
                    finally:
                        kernel.CloseHandle(handle)
                finally:
                    jobs.stop()


if __name__ == "__main__":
    unittest.main()
