"""Reproducible local baseline and opt-in isolated code execution.

The built-in baseline is trusted static code. Arbitrary or model-generated code
must only go through the Docker path. Containers share a host kernel and are
not a complete boundary against hostile code; use a dedicated VM for that.
"""
from __future__ import annotations

import hashlib
import json
import math
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional, Sequence


BASELINE_CODE = '''import json, random, math, sys
payload = json.load(sys.stdin)
values = payload["values"]
rng = random.Random(payload["seed"])
indices = list(range(len(values)))
rng.shuffle(indices)
cut = max(1, min(len(indices) - 1, int(len(indices) * 0.8)))
train = [values[i] for i in indices[:cut]]
test = [values[i] for i in indices[cut:]]
prediction = sum(train) / len(train)
rmse = math.sqrt(sum((v - prediction) ** 2 for v in test) / len(test))
print(json.dumps({"baseline": "train_mean", "prediction": prediction, "test_rmse": rmse, "train_count": len(train), "test_count": len(test)}, sort_keys=True))
'''
OUTPUT_LIMIT = 128 * 1024
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")


class CodexProviderError(Exception):
    """Provider-reported availability or authentication failure."""

    def __init__(self, code: str):
        if code not in {"codex_unavailable", "codex_auth_required", "codex_unsafe_configuration", "codex_timeout", "codex_failed"}:
            raise ValueError("unsupported provider error")
        super().__init__(code)
        self.code = code


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _payload(values: Sequence[float], seed: int) -> bytes:
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed < 2**32:
        raise ValueError("seed must be an integer from 0 to 2**32 - 1")
    if not 2 <= len(values) <= 10000:
        raise ValueError("values must contain 2 to 10000 finite numbers")
    numbers = []
    for value in values:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or abs(value) > 1e100:
            raise ValueError("values must contain finite numbers with magnitude at most 1e100")
        numbers.append(float(value))
    return json.dumps({"seed": seed, "values": numbers}, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _run(command: list, data: bytes, timeout: int, cleanup: Optional[Callable[[], bool]] = None) -> Dict[str, Any]:
    started = _now()
    tick = time.monotonic()
    output: Dict[str, bytearray] = {"stdout": bytearray(), "stderr": bytearray()}
    truncated = {"stdout": False, "stderr": False}
    timed_out = False
    try:
        proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError as exc:
        return {"status": "unavailable", "error": type(exc).__name__, "exit_code": None,
                "started_at": started, "finished_at": _now(), "duration_seconds": time.monotonic() - tick,
                "stdout": "", "stderr": "", "output_truncated": truncated}

    def read_stream(name: str, stream: Any) -> None:
        while True:
            chunk = stream.read(8192)
            if not chunk:
                break
            remaining = OUTPUT_LIMIT - len(output[name])
            if len(chunk) > remaining:
                truncated[name] = True
            if remaining > 0:
                output[name].extend(chunk[:remaining])
        stream.close()

    threads = [threading.Thread(target=read_stream, args=(name, stream), daemon=True)
               for name, stream in (("stdout", proc.stdout), ("stderr", proc.stderr))]
    for thread in threads:
        thread.start()

    def write_input() -> None:
        try:
            proc.stdin.write(data)
            proc.stdin.close()
        except (BrokenPipeError, OSError, ValueError):
            pass

    writer = threading.Thread(target=write_input, daemon=True)
    writer.start()
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        proc.kill()
        proc.wait()
    cleanup_ok = True
    if timed_out and cleanup is not None:
        cleanup_ok = cleanup()
    writer.join(timeout=1)
    for thread in threads:
        thread.join(timeout=2)
    return {"status": "timeout" if timed_out else "completed" if proc.returncode == 0 else "failed",
            "exit_code": proc.returncode, "started_at": started, "finished_at": _now(),
            "duration_seconds": time.monotonic() - tick,
            "stdout": bytes(output["stdout"]).decode("utf-8", errors="replace"),
            "stderr": bytes(output["stderr"]).decode("utf-8", errors="replace"),
            "output_truncated": truncated, "cleanup_ok": cleanup_ok}


def run_baseline(values: Sequence[float], seed: int = 42, timeout: int = 10) -> Dict[str, Any]:
    """Run the built-in mean predictor; callers must save the returned record."""
    if not 1 <= timeout <= 60:
        raise ValueError("timeout must be between 1 and 60 seconds")
    data = _payload(values, seed)
    command = [sys.executable, "-I", "-c", BASELINE_CODE]
    record = _run(command, data, timeout)
    record.update({"kind": "fixed_baseline", "seed": seed, "command": command,
                   "code_sha256": _hash(BASELINE_CODE.encode("utf-8")), "data_sha256": _hash(data),
                   "input_data": json.loads(data.decode("utf-8")),
                   "environment": {"python": sys.version, "platform": platform.platform(), "processor": platform.processor()},
                   "timeout_seconds": timeout})
    return record


def run_container(code: str, values: Sequence[float], image_digest: str, seed: int = 42,
                  timeout: int = 30) -> Dict[str, Any]:
    """Run explicit code with no host mounts or network in a local Docker image.

    Image must be a locally present immutable ``sha256:...`` image ID containing
    Python. Pulling is disabled. Never fall back to running code on the host.
    """
    if not isinstance(code, str) or not code or len(code.encode("utf-8")) > 64 * 1024:
        raise ValueError("code must be nonempty and at most 64 KiB")
    if not _DIGEST.fullmatch(image_digest):
        raise ValueError("image_digest must be an immutable local sha256 image ID")
    if not 1 <= timeout <= 120:
        raise ValueError("timeout must be between 1 and 120 seconds")
    data = _payload(values, seed)
    docker = shutil.which("docker")
    common = {"kind": "isolated_code", "seed": seed, "image_digest": image_digest,
              "code_sha256": _hash(code.encode("utf-8")), "data_sha256": _hash(data),
              "input_data": json.loads(data.decode("utf-8")),
              "timeout_seconds": timeout, "environment": {"host_platform": platform.platform(), "image_id": image_digest}}
    if docker is None:
        return dict(common, status="unavailable", error="docker_not_installed", exit_code=None,
                    command=None, stdout="", stderr="")
    name = "easyresearch-" + uuid.uuid4().hex
    command = [docker, "run", "--rm", "--name", name, "--pull", "never", "--network", "none",
               "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
               "--pids-limit", "64", "--memory", "256m", "--cpus", "1", "--user", "65534:65534",
               "--tmpfs", "/tmp:rw,noexec,nosuid,size=16m", "--env", "PYTHONHASHSEED=" + str(seed),
               "--entrypoint", "python", "-i", image_digest, "-I", "-c", code]

    def cleanup() -> bool:
        try:
            result = subprocess.run([docker, "rm", "-f", name], capture_output=True, timeout=10)
            return result.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            return False

    result = _run(command, data, timeout, cleanup)
    result.update(common)
    result["command"] = command
    if result["status"] == "failed":
        error_text = result["stderr"].lower()
        if "cannot connect to the docker daemon" in error_text or "failed to connect to the docker api" in error_text:
            result["status"] = "unavailable"
            result["error"] = "docker_daemon_unavailable"
    return result


def request_codex_proposal(prompt: str, *, user_requested: bool,
                           provider: Optional[Callable[[str], str]] = None) -> Dict[str, Any]:
    """Ask an explicitly configured provider for a proposal; never execute it.

    Provider integration, authentication, model configuration, and disclosure
    of data sent externally belong to the caller. This function does not imply
    that an installed CLI or an authenticated account is available.
    """
    if not user_requested:
        return {"status": "not_requested", "proposal": None}
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("prompt must not be empty")
    if provider is None:
        return {"status": "unavailable", "error": "codex_provider_not_configured", "proposal": None}
    try:
        proposal = provider(prompt)
        if not isinstance(proposal, str) or not proposal.strip():
            return {"status": "failed", "error": "empty_proposal", "proposal": None}
        return {"status": "proposed", "proposal": proposal, "executed": False}
    except CodexProviderError as exc:
        return {"status": "unavailable", "error": exc.code, "proposal": None}
    except Exception:
        return {"status": "failed", "error": "codex_provider_failed", "proposal": None}


def codex_cli_proposal(prompt: str, timeout: int = 120) -> str:
    """Codex provider for explicit proposal requests, with a fail-closed check.

    Only the caller-supplied prompt and the fixed instruction are sent; callers
    must present that scope to the user. No files are attached. CLI tool flags
    must be verifiably disabled before making any model request. This relies on
    the installed CLI honestly reporting its effective features.
    """
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt.encode("utf-8")) > 8192:
        raise ValueError("prompt must be nonempty and at most 8 KiB")
    if not 1 <= timeout <= 300:
        raise ValueError("timeout must be between 1 and 300 seconds")
    # On Windows, invoke a native executable directly, never a .cmd or .ps1
    # wrapper which the OS could interpret through a command shell.
    executable = shutil.which("codex.exe" if sys.platform == "win32" else "codex")
    if not executable:
        raise CodexProviderError("codex_unavailable")
    features = ("shell_tool", "unified_exec", "code_mode_host", "plugins", "apps", "browser_use", "computer_use", "hooks", "multi_agent")
    flags = []
    for feature in features:
        flags.extend(["--disable", feature])
    check = _run([executable] + flags + ["features", "list"], b"", 10)
    if check["status"] != "completed" or check.get("output_truncated", {}).get("stdout"):
        raise CodexProviderError("codex_unsafe_configuration")
    states = {}
    for line in check["stdout"].splitlines():
        parts = line.split()
        if len(parts) >= 3:
            states[parts[0]] = parts[-1]
    if any(states.get(feature) != "false" for feature in features):
        raise CodexProviderError("codex_unsafe_configuration")
    instruction = ("Propose a small CPU research experiment as text only. "
                   "Do not run commands, open files, use tools, or execute code. "
                   "State assumptions and provide code for later independent review.\n\n"
                   "User request:\n" + prompt)
    with tempfile.TemporaryDirectory(prefix="easyresearch-codex-") as directory:
        command = ([executable, "--ask-for-approval", "never"] + flags +
                   ["exec", "--ignore-user-config", "--sandbox", "read-only", "--skip-git-repo-check", "--ephemeral", "--cd", directory, "-"])
        result = _run(command, instruction.encode("utf-8"), timeout)
    if result["status"] == "timeout":
        raise CodexProviderError("codex_timeout")
    if result["status"] != "completed":
        message = result.get("stderr", "").lower()
        if any(value in message for value in ("not logged in", "not authenticated", "authentication required", "unauthorized", "401")):
            raise CodexProviderError("codex_auth_required")
        raise CodexProviderError("codex_failed")
    if result.get("output_truncated", {}).get("stdout") or not result["stdout"].strip():
        raise CodexProviderError("codex_failed")
    return result["stdout"].strip()
