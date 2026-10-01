"""CLI behavior tests for the development structure health check."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CHECK_SCRIPT = REPOSITORY_ROOT / "scripts" / "check_development_structure.py"
REQUIRED_PATHS = (
    (Path("AGENTS.md"), "file"),
    (Path(".agent/PLANS.md"), "file"),
    (Path("docs/development/orchestration.md"), "file"),
    (Path("docs/exec-plans/active"), "directory"),
    (Path("docs/exec-plans/completed"), "directory"),
)


def create_valid_structure(root: Path) -> None:
    for relative_path, expected_type in REQUIRED_PATHS:
        path = root / relative_path
        if expected_type == "file":
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("fixture\n", encoding="utf-8")
        else:
            path.mkdir(parents=True, exist_ok=True)


def run_check(*arguments: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CHECK_SCRIPT), *arguments],
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def output_of(result: subprocess.CompletedProcess[str]) -> str:
    return f"{result.stdout}\n{result.stderr}"


class DevelopmentStructureCliTests(unittest.TestCase):
    def assert_success(self, result: subprocess.CompletedProcess[str]) -> None:
        self.assertEqual(result.returncode, 0, output_of(result))
        message = output_of(result).strip()
        self.assertTrue(message, "successful check should print a concise result")
        self.assertLessEqual(len(message), 200, "success result should be concise")
        self.assertTrue(
            any(
                marker in message.casefold()
                for marker in ("passed", "success", "valid", "healthy", "ok")
            ),
            "success result should clearly communicate success",
        )

    def assert_invalid_path(
        self,
        result: subprocess.CompletedProcess[str],
        relative_path: Path,
        expected_type: str,
    ) -> None:
        self.assertNotEqual(result.returncode, 0, output_of(result))
        output = output_of(result).casefold().replace("\\", "/")
        self.assertIn(relative_path.as_posix().casefold(), output)
        self.assertIn(expected_type, output)

    def test_valid_structure_accepts_required_paths_and_ignores_extras(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            create_valid_structure(root)
            (root / "unrelated.txt").write_text("extra\n", encoding="utf-8")
            (root / "unrelated-directory").mkdir()

            result = run_check("--root", str(root), cwd=REPOSITORY_ROOT)

        self.assert_success(result)

    def test_default_root_is_script_repository_from_a_different_cwd(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            different_cwd = Path(temporary_directory)
            result = run_check(cwd=different_cwd)

        self.assert_success(result)

    def test_each_missing_required_path_fails_with_its_expected_type(self) -> None:
        for relative_path, expected_type in REQUIRED_PATHS:
            with self.subTest(path=relative_path.as_posix()):
                with tempfile.TemporaryDirectory() as temporary_directory:
                    root = Path(temporary_directory)
                    create_valid_structure(root)
                    path = root / relative_path
                    if expected_type == "file":
                        path.unlink()
                    else:
                        path.rmdir()

                    result = run_check("--root", str(root), cwd=REPOSITORY_ROOT)

                self.assert_invalid_path(result, relative_path, expected_type)

    def test_each_wrong_type_required_path_fails_with_its_expected_type(self) -> None:
        for relative_path, expected_type in REQUIRED_PATHS:
            with self.subTest(path=relative_path.as_posix()):
                with tempfile.TemporaryDirectory() as temporary_directory:
                    root = Path(temporary_directory)
                    create_valid_structure(root)
                    path = root / relative_path
                    if expected_type == "file":
                        path.unlink()
                        path.mkdir()
                    else:
                        path.rmdir()
                        path.write_text("not a directory\n", encoding="utf-8")

                    result = run_check("--root", str(root), cwd=REPOSITORY_ROOT)

                self.assert_invalid_path(result, relative_path, expected_type)

    def test_all_missing_paths_are_reported_for_an_alternate_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "alternate-root"
            root.mkdir()
            result = run_check("--root", str(root), cwd=REPOSITORY_ROOT)

        for relative_path, expected_type in REQUIRED_PATHS:
            with self.subTest(path=relative_path.as_posix()):
                self.assert_invalid_path(result, relative_path, expected_type)

    def test_invalid_root_check_does_not_create_or_modify_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "read-only-root"
            root.mkdir()
            (root / "AGENTS.md").write_text("existing fixture\n", encoding="utf-8")
            (root / "docs").mkdir()

            before = self.snapshot(root)
            result = run_check("--root", str(root), cwd=REPOSITORY_ROOT)
            after = self.snapshot(root)

        self.assertNotEqual(result.returncode, 0, output_of(result))
        self.assertEqual(after, before, "health check changed its input tree")

    @staticmethod
    def snapshot(root: Path) -> tuple[tuple[str, str, bytes | None], ...]:
        entries = []
        for path in sorted(root.rglob("*")):
            relative_path = path.relative_to(root).as_posix()
            if path.is_file():
                entries.append((relative_path, "file", path.read_bytes()))
            elif path.is_dir():
                entries.append((relative_path, "directory", None))
            else:
                entries.append((relative_path, "other", None))
        return tuple(entries)


if __name__ == "__main__":
    unittest.main()
