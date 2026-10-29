"""Windows process-tree lifetime control for trusted worker modules.

The child starts Python without site initialization, blocks on a private stdin
gate, and only imports the worker after the supervisor has assigned it to a
kill-on-close Job Object. This contains ordinary CreateProcess descendants.
This is process lifecycle control, not a security sandbox for untrusted code.
"""
from __future__ import annotations

import ctypes
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Iterable, Optional, Union


class ProcessControlError(RuntimeError):
    pass


_GATE = """import sys
signal = sys.stdin.buffer.read(1)
if signal != b'1':
    sys.exit(125)
import site
site.main()
import runpy
root, module = sys.argv[1:3]
sys.path.insert(0, root)
sys.argv = [module] + sys.argv[3:]
runpy.run_module(module, run_name='__main__')
"""
_MODULE = re.compile(r"^[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*$")


if os.name == "nt":
    from ctypes import wintypes

    class _BasicLimits(ctypes.Structure):
        _fields_ = [("PerProcessUserTimeLimit", ctypes.c_longlong),
                    ("PerJobUserTimeLimit", ctypes.c_longlong),
                    ("LimitFlags", wintypes.DWORD),
                    ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t),
                    ("ActiveProcessLimit", wintypes.DWORD),
                    ("Affinity", ctypes.c_size_t),
                    ("PriorityClass", wintypes.DWORD),
                    ("SchedulingClass", wintypes.DWORD)]

    class _IOCounters(ctypes.Structure):
        _fields_ = [(name, ctypes.c_ulonglong) for name in (
            "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
            "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

    class _ExtendedLimits(ctypes.Structure):
        _fields_ = [("BasicLimitInformation", _BasicLimits), ("IoInfo", _IOCounters),
                    ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                    ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]

    class _BasicAccounting(ctypes.Structure):
        _fields_ = [("TotalUserTime", ctypes.c_longlong), ("TotalKernelTime", ctypes.c_longlong),
                    ("ThisPeriodTotalUserTime", ctypes.c_longlong), ("ThisPeriodTotalKernelTime", ctypes.c_longlong),
                    ("TotalPageFaultCount", wintypes.DWORD), ("TotalProcesses", wintypes.DWORD),
                    ("ActiveProcesses", wintypes.DWORD), ("TotalTerminatedProcesses", wintypes.DWORD)]

    _kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    _kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    _kernel.CreateJobObjectW.restype = wintypes.HANDLE
    _kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    _kernel.SetInformationJobObject.restype = wintypes.BOOL
    _kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    _kernel.AssignProcessToJobObject.restype = wintypes.BOOL
    _kernel.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
    _kernel.TerminateJobObject.restype = wintypes.BOOL
    _kernel.QueryInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p]
    _kernel.QueryInformationJobObject.restype = wintypes.BOOL
    _kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    _kernel.CloseHandle.restype = wintypes.BOOL


def _create_job():
    if os.name != "nt":
        raise ProcessControlError("Windows Job Objects are unavailable on this platform")
    job = _kernel.CreateJobObjectW(None, None)
    if not job:
        raise ProcessControlError("CreateJobObject failed: {}".format(ctypes.get_last_error()))
    limits = _ExtendedLimits()
    limits.BasicLimitInformation.LimitFlags = 0x00002000  # KILL_ON_JOB_CLOSE, no breakaway
    if not _kernel.SetInformationJobObject(job, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
        error = ctypes.get_last_error()
        _kernel.CloseHandle(job)
        raise ProcessControlError("SetInformationJobObject failed: {}".format(error))
    return job


def _assign(job, process):
    # Popen retains a real Win32 process handle for its own lifetime.
    if not _kernel.AssignProcessToJobObject(job, int(process._handle)):
        raise ProcessControlError("AssignProcessToJobObject failed: {}".format(ctypes.get_last_error()))


def _active(job) -> int:
    info = _BasicAccounting()
    if not _kernel.QueryInformationJobObject(job, 1, ctypes.byref(info), ctypes.sizeof(info), None):
        raise ProcessControlError("QueryInformationJobObject failed: {}".format(ctypes.get_last_error()))
    return int(info.ActiveProcesses)


class WindowsProcessTree:
    """Own a job handle until the worker and all descendants have exited.

    ``wait`` waits only for the worker. ``terminate`` / ``close`` explicitly
    stop descendants and wait for the job's active-process count to reach zero.
    A caller may clean its own attempt directory only after successful close.
    """

    def __init__(self, job, process):
        self._job = job
        self.process = process
        self._closed = False

    @property
    def pid(self):
        return self.process.pid

    def poll(self):
        return self.process.poll()

    def wait(self, timeout: Optional[float] = None):
        return self.process.wait(timeout=timeout)

    def terminate(self, timeout: float = 10):
        if self._closed:
            raise ProcessControlError("process tree is closed")
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        if _active(self._job) and not _kernel.TerminateJobObject(self._job, 1):
            raise ProcessControlError("TerminateJobObject failed: {}".format(ctypes.get_last_error()))
        deadline = time.monotonic() + timeout
        while _active(self._job):
            if time.monotonic() >= deadline:
                raise ProcessControlError("job processes did not terminate within the timeout")
            time.sleep(min(0.05, max(0, deadline - time.monotonic())))
        # Reap the worker if present; no child process is left in this job.
        self.process.wait(timeout=max(0.01, deadline - time.monotonic()))

    def close(self, timeout: float = 10):
        if self._closed:
            return
        try:
            self.terminate(timeout)
        finally:
            # Kill-on-close also acts if explicit termination failed. The caller
            # must treat an exception as unconfirmed cleanup, not success.
            _kernel.CloseHandle(self._job)
            self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()


def start_windows_worker(module: str, args: Iterable[str], root: Union[str, Path], env=None) -> WindowsProcessTree:
    """Start a trusted Python worker in a Windows job; fail closed on errors.

    ``root`` must be a trusted import root, and ``module`` a trusted module,
    not an untrusted user selection. Job-object assignment is mandatory.
    The blocked child's stdin belongs exclusively to the supervisor and closes
    after authorization; an EOF before authorization makes the child exit.
    """
    if os.name != "nt":
        raise ProcessControlError("Windows Job Objects are unavailable on this platform")
    if not isinstance(module, str) or not _MODULE.fullmatch(module):
        raise ValueError("invalid module name")
    root = Path(root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("worker root must be a directory")
    args = list(args)
    if any(not isinstance(arg, str) for arg in args):
        raise ValueError("worker arguments must be strings")
    job = _create_job()
    process = None
    try:
        process = subprocess.Popen([sys.executable, "-I", "-S", "-c", _GATE, str(root), module] + args,
                                   stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                   close_fds=True, env=env, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        _assign(job, process)
        process.stdin.write(b"1")
        process.stdin.close()
        return WindowsProcessTree(job, process)
    except BaseException:
        # Closing the gate prevents execution even if assignment failed.
        if process is not None:
            try:
                process.stdin.close()
            except (OSError, ValueError):
                pass
            try:
                process.terminate()
                process.wait(timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                try:
                    process.kill()
                    process.wait(timeout=5)
                except (OSError, subprocess.TimeoutExpired):
                    pass
        _kernel.CloseHandle(job)
        raise
