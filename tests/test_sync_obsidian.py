"""Behavior tests for the Obsidian vault sync script (no network, temp vaults only)."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from typing import Any
from unittest import mock


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPOSITORY_ROOT / "scripts" / "sync_obsidian.py"

_spec = importlib.util.spec_from_file_location("sync_obsidian_under_test", SCRIPT_PATH)
sync = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(sync)

BEGIN = "<!-- easyresearch:begin -->"
END = "<!-- easyresearch:end -->"


def generated_block(body: str) -> str:
    return f"{BEGIN}\n{body}\n{END}"


def make_payload(body: str = "생성 A", filename: str = "doe2020.md") -> dict[str, Any]:
    return {
        "schema_version": 1,
        "project": {"id": "project-1", "name": "테스트"},
        "notes": [
            {
                "paper_id": "paper-1",
                "citekey": "doe2020",
                "filename": filename,
                "frontmatter": {"citekey": "doe2020", "title": '제목 "quoted"'},
                "generated": generated_block(body),
                "title": "제목",
            }
        ],
    }


def fixed_fetcher(payload: dict[str, Any]):
    def fetch(base_url: str, project_id: str) -> dict[str, Any]:
        return payload

    return fetch


def run_sync(vault: Path, payload: dict[str, Any], *extra: str) -> tuple[int, str, str]:
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = sync.main(
            ["--project", "project-1", "--vault", str(vault), *extra],
            fetcher=fixed_fetcher(payload),
        )
    return code, stdout.getvalue(), stderr.getvalue()


class SyncObsidianTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.vault = Path(self._temporary.name) / "vault"
        self.vault.mkdir()
        self.target = self.vault / "EasyResearch" / "doe2020.md"

    def tearDown(self) -> None:
        self._temporary.cleanup()

    def test_creates_new_file_with_frontmatter_and_user_section(self) -> None:
        code, _, _ = run_sync(self.vault, make_payload())

        self.assertEqual(code, 0)
        expected = (
            '---\ncitekey: "doe2020"\ntitle: "제목 \\"quoted\\""\n---\n\n'
            "# 제목\n\n"
            f"{generated_block('생성 A')}\n\n"
            "## 내 메모\n\n"
        )
        self.assertEqual(self.target.read_bytes(), expected.encode("utf-8"))

    def test_second_run_is_idempotent_and_reports_unchanged(self) -> None:
        run_sync(self.vault, make_payload())
        first = self.target.read_bytes()

        code, stdout, _ = run_sync(self.vault, make_payload(), "--json")

        self.assertEqual(code, 0)
        report = json.loads(stdout)
        self.assertEqual(report["counts"]["unchanged"], 1)
        self.assertEqual(self.target.read_bytes(), first)

    def test_user_edits_outside_markers_are_preserved(self) -> None:
        run_sync(self.vault, make_payload("생성 A"))
        original = self.target.read_text(encoding="utf-8")
        edited = original.replace("## 내 메모\n\n", "## 내 메모\n\n나의 생각입니다.\n")
        edited = edited.replace('citekey: "doe2020"', 'citekey: "doe2020"\nstatus: "읽는 중"')
        with open(self.target, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(edited)

        code, stdout, _ = run_sync(self.vault, make_payload("생성 B"), "--json")

        self.assertEqual(code, 0)
        self.assertEqual(json.loads(stdout)["counts"]["updated"], 1)
        result = self.target.read_text(encoding="utf-8")
        self.assertIn("나의 생각입니다.", result)
        self.assertIn('status: "읽는 중"', result)
        self.assertIn("생성 B", result)
        self.assertNotIn("생성 A", result)
        self.assertEqual(result, edited.replace("생성 A", "생성 B"))

    def test_missing_markers_is_conflict_and_file_is_untouched(self) -> None:
        self.target.parent.mkdir(parents=True)
        original = "# 직접 쓴 노트\n\n그대로 둡니다.\n".encode("utf-8")
        self.target.write_bytes(original)

        code, stdout, _ = run_sync(self.vault, make_payload(), "--json")

        self.assertEqual(code, 2)
        self.assertEqual(json.loads(stdout)["counts"]["conflict"], 1)
        self.assertEqual(self.target.read_bytes(), original)

    def test_duplicated_markers_is_conflict_and_file_is_untouched(self) -> None:
        self.target.parent.mkdir(parents=True)
        original = f"{generated_block('x')}\n중간\n{generated_block('y')}\n".encode("utf-8")
        self.target.write_bytes(original)

        code, _, _ = run_sync(self.vault, make_payload())

        self.assertEqual(code, 2)
        self.assertEqual(self.target.read_bytes(), original)

    def test_end_marker_before_begin_marker_is_conflict(self) -> None:
        self.target.parent.mkdir(parents=True)
        original = f"{END}\n본문\n{BEGIN}\n".encode("utf-8")
        self.target.write_bytes(original)

        code, _, _ = run_sync(self.vault, make_payload())

        self.assertEqual(code, 2)
        self.assertEqual(self.target.read_bytes(), original)

    def test_path_traversal_filenames_are_rejected(self) -> None:
        for filename in ("../evil.md", "sub/evil.md", "..\\evil.md", "evil.txt", "a..b.md"):
            with self.subTest(filename=filename):
                with tempfile.TemporaryDirectory() as temporary:
                    vault = Path(temporary) / "vault"
                    vault.mkdir()
                    code, _, stderr = run_sync(vault, make_payload(filename=filename), "--json")

                    self.assertEqual(code, 1)
                    self.assertFalse((Path(temporary) / "evil.md").exists())
                    self.assertEqual(list(vault.rglob("*.md")), [])

    def test_dry_run_writes_nothing(self) -> None:
        self.target.parent.mkdir(parents=True)
        original = "사용자 파일\n".encode("utf-8")
        existing = self.target
        existing.write_bytes(original)
        other = self.vault / "EasyResearch" / "other.md"
        payload = make_payload()
        payload["notes"].append(dict(payload["notes"][0], paper_id="paper-2", filename="other.md"))

        code, stdout, _ = run_sync(self.vault, payload, "--dry-run", "--json")

        self.assertEqual(code, 2)
        report = json.loads(stdout)
        self.assertTrue(report["dry_run"])
        self.assertEqual(report["counts"]["created"], 1)
        self.assertEqual(report["counts"]["conflict"], 1)
        self.assertFalse(other.exists())
        self.assertEqual(existing.read_bytes(), original)

    def test_refuses_repository_data_folder_without_creating_anything(self) -> None:
        forbidden = sync.DATA_ROOT / "sync-test-should-not-exist"

        code, _, stderr = run_sync(forbidden, make_payload())

        self.assertEqual(code, 1)
        self.assertIn("data/", stderr)
        self.assertFalse(forbidden.exists())

    def test_connection_refused_gives_korean_start_hint(self) -> None:
        refused = urllib.error.URLError(ConnectionRefusedError(10061, "refused"))
        with mock.patch.object(sync.urllib.request, "urlopen", side_effect=refused):
            with self.assertRaises(sync.SyncError) as context:
                sync.fetch_obsidian_notes("http://127.0.0.1:8000", "project-1")

        self.assertIn("앱을 먼저 실행", str(context.exception))

    def test_fetch_uses_get_with_encoded_project_id(self) -> None:
        captured: list[Any] = []

        class FakeResponse(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *exc_info):
                return False

        def fake_urlopen(request, timeout=None):
            captured.append(request)
            return FakeResponse(json.dumps({"notes": []}).encode("utf-8"))

        with mock.patch.object(sync.urllib.request, "urlopen", side_effect=fake_urlopen):
            sync.fetch_obsidian_notes("http://127.0.0.1:8000", "a/b c")

        self.assertEqual(len(captured), 1)
        self.assertEqual(captured[0].get_method(), "GET")
        self.assertIsNone(captured[0].data)
        self.assertEqual(
            captured[0].full_url,
            "http://127.0.0.1:8000/api/projects/a%2Fb%20c/obsidian-notes",
        )

    def test_api_style_generated_with_trailing_newline_is_stable_over_three_runs(self) -> None:
        payload = make_payload("생성 A")
        payload["notes"][0]["generated"] = generated_block("생성 A") + "\n"

        statuses = []
        contents = []
        for _ in range(3):
            code, stdout, _ = run_sync(self.vault, payload, "--json")
            self.assertEqual(code, 0)
            statuses.append(json.loads(stdout)["results"][0]["status"])
            contents.append(self.target.read_bytes())

        self.assertEqual(statuses, ["created", "unchanged", "unchanged"])
        self.assertEqual(contents[0], contents[1])
        self.assertEqual(contents[1], contents[2])
        self.assertIn(f"{END}\n\n## 내 메모".encode("utf-8"), contents[0])

    def test_user_text_on_line_after_end_marker_is_preserved(self) -> None:
        payload_a = make_payload("생성 A")
        payload_a["notes"][0]["generated"] = generated_block("생성 A") + "\n"
        run_sync(self.vault, payload_a)
        original = self.target.read_text(encoding="utf-8")
        with open(self.target, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(original.replace(f"{END}\n", f"{END}\n사용자 줄\n", 1))
        before_run = self.target.read_text(encoding="utf-8")

        payload_b = make_payload("생성 B")
        payload_b["notes"][0]["generated"] = generated_block("생성 B") + "\n"
        code, stdout, _ = run_sync(self.vault, payload_b, "--json")

        self.assertEqual(code, 0)
        self.assertEqual(json.loads(stdout)["results"][0]["status"], "updated")
        after_run = self.target.read_text(encoding="utf-8")
        self.assertIn(f"{END}\n사용자 줄\n", after_run)
        self.assertIn("생성 B", after_run)
        self.assertEqual(after_run, before_run.replace("생성 A", "생성 B"))

        code, stdout, _ = run_sync(self.vault, payload_b, "--json")
        self.assertEqual(json.loads(stdout)["results"][0]["status"], "unchanged")
        self.assertEqual(self.target.read_text(encoding="utf-8"), after_run)

    def test_invalid_generated_block_is_reported_as_error(self) -> None:
        payload = make_payload()
        payload["notes"][0]["generated"] = "마커 없음"

        code, _, _ = run_sync(self.vault, payload)

        self.assertEqual(code, 1)
        self.assertFalse(self.target.exists())


if __name__ == "__main__":
    unittest.main()
