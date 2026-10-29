import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import experiment_runner as runner


class ExperimentTests(unittest.TestCase):
    def test_fixed_baseline_is_reproducible_and_records_inputs(self):
        first = runner.run_baseline([1, 2, 3, 4, 5], seed=9)
        second = runner.run_baseline([1, 2, 3, 4, 5], seed=9)
        self.assertEqual(first["status"], "completed")
        self.assertEqual(first["exit_code"], 0)
        self.assertEqual(json.loads(first["stdout"]), json.loads(second["stdout"]))
        self.assertEqual(first["data_sha256"], second["data_sha256"])
        self.assertEqual(first["input_data"]["values"], [1, 2, 3, 4, 5])
        self.assertEqual(first["code_sha256"], second["code_sha256"])
        self.assertNotEqual(first["data_sha256"], runner.run_baseline([1, 2, 3, 4, 5], seed=10)["data_sha256"])
        self.assertTrue(first["environment"]["python"])
        self.assertTrue(first["command"])
        self.assertTrue(first["started_at"])

    def test_rejects_bad_input(self):
        for values, seed in (([1], 1), ([1, float("nan")], 1), ([1, 2], -1), ([True, 2], 1)):
            with self.assertRaises(ValueError):
                runner.run_baseline(values, seed)
        with self.assertRaises(ValueError):
            runner.run_container("print(1)", [1, 2], "python:latest")

    def test_missing_docker_never_runs_code_on_host(self):
        with patch.object(runner.shutil, "which", return_value=None), patch.object(runner, "_run") as run:
            result = runner.run_container("raise Exception()", [1, 2], "sha256:" + "a" * 64)
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["error"], "docker_not_installed")
        run.assert_not_called()

    def test_docker_command_has_isolation_and_no_mounts_or_pull(self):
        result = {"status": "failed", "exit_code": 125, "stdout": "", "stderr": "daemon unavailable"}
        with patch.object(runner.shutil, "which", return_value="docker"), patch.object(runner, "_run", return_value=result):
            actual = runner.run_container("print(1)", [1, 2], "sha256:" + "a" * 64)
        cmd = actual["command"]
        for pair in (("--network", "none"), ("--pull", "never"), ("--cap-drop", "ALL"), ("--cpus", "1")):
            self.assertIn(pair, list(zip(cmd, cmd[1:])))
        self.assertIn("--read-only", cmd)
        self.assertNotIn("--mount", cmd)
        self.assertNotIn("-v", cmd)
        self.assertEqual(actual["status"], "failed")

    def test_codex_is_explicit_and_never_auto_executes_proposal(self):
        provider = unittest.mock.Mock(return_value="print('proposed code')")
        self.assertEqual(runner.request_codex_proposal("plan", user_requested=False, provider=provider)["status"], "not_requested")
        provider.assert_not_called()
        self.assertEqual(runner.request_codex_proposal("plan", user_requested=True)["error"], "codex_provider_not_configured")
        proposed = runner.request_codex_proposal("plan", user_requested=True, provider=provider)
        self.assertFalse(proposed["executed"])
        self.assertEqual(proposed["status"], "proposed")
        missing_auth = unittest.mock.Mock(side_effect=runner.CodexProviderError("codex_auth_required"))
        self.assertEqual(runner.request_codex_proposal("plan", user_requested=True, provider=missing_auth)["error"], "codex_auth_required")

    def test_output_is_bounded_and_timeout_recorded(self):
        command = [sys.executable, "-c", "print('x' * 200000)"]
        output = runner._run(command, b"", 5)
        self.assertEqual(output["status"], "completed")
        self.assertTrue(output["output_truncated"]["stdout"])
        self.assertEqual(len(output["stdout"]), runner.OUTPUT_LIMIT)
        timeout = runner._run([sys.executable, "-c", "import time; time.sleep(10)"], b"", 1)
        self.assertEqual(timeout["status"], "timeout")

    def test_cli_provider_fails_closed_without_verified_disabled_tools(self):
        check = {"status": "completed", "stdout": "shell_tool stable false\nunified_exec stable true\n", "output_truncated": {"stdout": False}}
        with patch.object(runner.shutil, "which", return_value="codex"), patch.object(runner, "_run", return_value=check) as run:
            result = runner.request_codex_proposal("idea", user_requested=True, provider=runner.codex_cli_proposal)
        self.assertEqual(result["error"], "codex_unsafe_configuration")
        self.assertEqual(run.call_count, 1)

    def test_cli_provider_is_explicit_restricted_and_prompt_only(self):
        names = ("shell_tool", "unified_exec", "code_mode_host", "plugins", "apps", "browser_use", "computer_use", "hooks", "multi_agent")
        check = {"status": "completed", "stdout": "".join(name + " stable false\n" for name in names), "output_truncated": {"stdout": False}}
        answer = {"status": "completed", "stdout": "Proposed code", "stderr": "", "output_truncated": {"stdout": False}}
        with patch.object(runner.shutil, "which", return_value="codex"), patch.object(runner, "_run", side_effect=[check, answer]) as run:
            result = runner.request_codex_proposal("Only this request", user_requested=True, provider=runner.codex_cli_proposal)
        self.assertEqual(result["proposal"], "Proposed code")
        command, sent, _ = run.call_args.args
        self.assertIn("--ignore-user-config", command)
        self.assertIn("read-only", command)
        self.assertIn("--ephemeral", command)
        self.assertIn("--skip-git-repo-check", command)
        self.assertIn(b"Only this request", sent)
        self.assertEqual(command[-1], "-")

    def test_cli_provider_auth_failure_is_reported(self):
        names = ("shell_tool", "unified_exec", "code_mode_host", "plugins", "apps", "browser_use", "computer_use", "hooks", "multi_agent")
        check = {"status": "completed", "stdout": "".join(name + " stable false\n" for name in names), "output_truncated": {"stdout": False}}
        failure = {"status": "failed", "stdout": "", "stderr": "Not logged in", "output_truncated": {"stdout": False}}
        with patch.object(runner.shutil, "which", return_value="codex"), patch.object(runner, "_run", side_effect=[check, failure]):
            result = runner.request_codex_proposal("idea", user_requested=True, provider=runner.codex_cli_proposal)
        self.assertEqual(result["error"], "codex_auth_required")


if __name__ == "__main__":
    unittest.main()
