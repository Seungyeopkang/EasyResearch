#!/usr/bin/env python3
"""Sync EasyResearch Obsidian notes into a vault folder.

Only the region between the easyresearch begin/end markers is regenerated.
Frontmatter and user-written text outside the markers are kept byte-identical.
Files without exactly one valid marker pair are reported as conflicts and left
untouched.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
DATA_ROOT = (REPOSITORY_ROOT / "data").resolve()
BEGIN_MARKER = "<!-- easyresearch:begin -->"
END_MARKER = "<!-- easyresearch:end -->"
DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_SUBDIR = "EasyResearch"
USER_NOTE_HEADING = "## 내 메모"
EXIT_OK = 0
EXIT_ERROR = 1
EXIT_CONFLICT = 2

Fetcher = Callable[[str, str], dict[str, Any]]


class SyncError(Exception):
    """A fatal problem that stops the sync with exit code 1."""


def fetch_obsidian_notes(base_url: str, project_id: str) -> dict[str, Any]:
    """Fetch the note payload for one project from the local API (GET only)."""
    encoded_id = urllib.parse.quote(project_id, safe="")
    url = f"{base_url.rstrip('/')}/api/projects/{encoded_id}/obsidian-notes"
    request = urllib.request.Request(
        url, method="GET", headers={"Accept": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read()
    except urllib.error.HTTPError as error:
        raise SyncError(
            f"서버가 오류를 반환했습니다 (HTTP {error.code}). 프로젝트 ID를 확인하세요."
        ) from error
    except urllib.error.URLError as error:
        raise SyncError(
            f"EasyResearch 앱에 연결할 수 없습니다 ({base_url}). "
            "앱을 먼저 실행한 뒤 다시 시도하세요."
        ) from error
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SyncError("서버 응답을 JSON으로 읽을 수 없습니다.") from error
    if not isinstance(payload, dict) or not isinstance(payload.get("notes"), list):
        raise SyncError("서버 응답에 notes 목록이 없습니다.")
    return payload


def resolve_vault(vault_argument: str) -> Path:
    vault = Path(vault_argument).expanduser().resolve()
    if vault == DATA_ROOT or DATA_ROOT in vault.parents:
        raise SyncError(
            "data/ 폴더는 볼트로 사용할 수 없습니다 (개인 연구 데이터 보호)."
        )
    if not vault.is_dir():
        raise SyncError(f"볼트 폴더가 없습니다: {vault}")
    return vault


def validate_subdir(subdir: str) -> str:
    path = Path(subdir)
    if not subdir or path.is_absolute() or ".." in path.parts or subdir.startswith(("/", "\\")):
        raise SyncError(f"잘못된 하위 폴더 이름입니다: {subdir}")
    return subdir


def validate_filename(filename: Any) -> str | None:
    """Return a rejection reason, or None when the filename is acceptable."""
    if not isinstance(filename, str) or not filename:
        return "파일 이름이 비어 있습니다"
    if any(character in filename for character in ("/", "\\", ":", "\x00")):
        return "경로 구분자가 포함되어 있습니다"
    if ".." in filename:
        return "'..'가 포함되어 있습니다"
    if not filename.endswith(".md") or filename == ".md":
        return ".md 확장자가 필요합니다"
    return None


def render_frontmatter(frontmatter: dict[str, Any]) -> str:
    # JSON string and number literals are valid YAML scalars.
    return "\n".join(
        f"{key}: {json.dumps(value, ensure_ascii=False)}"
        for key, value in frontmatter.items()
    )


def generated_body(generated: str) -> str:
    """Generated block without trailing line breaks (the API output may end with one)."""
    return generated.rstrip("\r\n")


def build_new_document(note: dict[str, Any]) -> str:
    return (
        f"---\n{render_frontmatter(note['frontmatter'])}\n---\n\n"
        f"# {note['title']}\n\n"
        f"{generated_body(note['generated'])}\n\n"
        f"{USER_NOTE_HEADING}\n\n"
    )


def merge_existing(existing: str, generated: str) -> str | None:
    """Replace the marker region, including the end marker's line terminator.

    The line terminator that follows the end marker in the file is kept as-is, so
    text the user wrote on the next line survives and repeated runs are byte-identical.
    Returns None when markers are not exactly one ordered pair.
    """
    if existing.count(BEGIN_MARKER) != 1 or existing.count(END_MARKER) != 1:
        return None
    begin = existing.index(BEGIN_MARKER)
    end_start = existing.index(END_MARKER)
    if end_start < begin:
        return None
    end_stop = end_start + len(END_MARKER)
    if existing.startswith("\r\n", end_stop):
        terminator_stop = end_stop + 2
    elif existing.startswith("\n", end_stop):
        terminator_stop = end_stop + 1
    else:
        terminator_stop = end_stop
    terminator = existing[end_stop:terminator_stop]
    return existing[:begin] + generated_body(generated) + terminator + existing[terminator_stop:]


def write_atomic(target: Path, content: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temporary_name = tempfile.mkstemp(
        dir=target.parent, prefix=f".{target.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        os.replace(temporary_name, target)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except OSError:
            pass
        raise


def process_note(
    note: Any, vault: Path, subdir: str, dry_run: bool
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "paper_id": None,
        "filename": None,
        "path": None,
        "status": "error",
        "reason": None,
    }
    if not isinstance(note, dict):
        result["reason"] = "노트 형식이 올바르지 않습니다"
        return result
    result["paper_id"] = note.get("paper_id")
    filename = note.get("filename")
    result["filename"] = filename

    rejection = validate_filename(filename)
    if rejection:
        result["reason"] = f"파일 이름 거부: {rejection}"
        return result
    generated = note.get("generated")
    if not isinstance(generated, str) or not isinstance(note.get("frontmatter"), dict) \
            or not isinstance(note.get("title"), str):
        result["reason"] = "노트 필드(frontmatter, title, generated)가 올바르지 않습니다"
        return result
    if (
        generated.count(BEGIN_MARKER) != 1
        or generated.count(END_MARKER) != 1
        or generated.index(END_MARKER) < generated.index(BEGIN_MARKER)
    ):
        result["reason"] = "generated에 마커 쌍이 정확히 하나 있어야 합니다"
        return result

    base = (vault / subdir).resolve()
    target = (base / filename).resolve()
    if target.parent != base or not target.is_relative_to(vault):
        result["reason"] = "대상 경로가 볼트 밖을 가리킵니다"
        return result
    result["path"] = str(target)

    if not target.exists():
        if not dry_run:
            write_atomic(target, build_new_document(note))
        result["status"] = "created"
        return result
    if not target.is_file():
        result["status"] = "conflict"
        result["reason"] = "같은 이름의 폴더 또는 특수 파일이 있습니다"
        return result

    try:
        existing = target.read_bytes().decode("utf-8")
    except UnicodeDecodeError:
        result["status"] = "conflict"
        result["reason"] = "UTF-8이 아닌 파일입니다"
        return result

    merged = merge_existing(existing, generated)
    if merged is None:
        result["status"] = "conflict"
        result["reason"] = "생성 구간 마커가 정확히 한 쌍 있어야 합니다"
        return result
    if merged == existing:
        result["status"] = "unchanged"
        return result
    if not dry_run:
        write_atomic(target, merged)
    result["status"] = "updated"
    return result


def sync_notes(
    payload: dict[str, Any], vault: Path, subdir: str, dry_run: bool
) -> list[dict[str, Any]]:
    return [
        process_note(note, vault, subdir, dry_run) for note in payload["notes"]
    ]


def count_statuses(results: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"created": 0, "updated": 0, "unchanged": 0, "conflict": 0, "error": 0}
    for result in results:
        counts[result["status"]] += 1
    return counts


def exit_code_for(counts: dict[str, int]) -> int:
    if counts["error"]:
        return EXIT_ERROR
    if counts["conflict"]:
        return EXIT_CONFLICT
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="EasyResearch 노트를 Obsidian 볼트로 동기화합니다 (생성 구간만 갱신)."
    )
    parser.add_argument("--project", required=True, help="프로젝트 ID")
    parser.add_argument("--vault", required=True, help="Obsidian 볼트 폴더")
    parser.add_argument("--subdir", default=DEFAULT_SUBDIR, help="볼트 안의 하위 폴더")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="로컬 API 주소")
    parser.add_argument("--dry-run", action="store_true", help="파일을 쓰지 않고 결과만 표시")
    parser.add_argument("--json", action="store_true", help="결과를 JSON으로 출력")
    return parser


def main(argv: list[str] | None = None, fetcher: Fetcher = fetch_obsidian_notes) -> int:
    args = build_parser().parse_args(argv)
    try:
        vault = resolve_vault(args.vault)
        subdir = validate_subdir(args.subdir)
        payload = fetcher(args.base_url, args.project)
        results = sync_notes(payload, vault, subdir, args.dry_run)
    except SyncError as error:
        print(f"오류: {error}", file=sys.stderr)
        return EXIT_ERROR

    counts = count_statuses(results)
    if args.json:
        report = {
            "project": args.project,
            "vault": str(vault),
            "subdir": subdir,
            "dry_run": args.dry_run,
            "counts": counts,
            "results": results,
        }
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        mode = " (시험 실행, 파일 변경 없음)" if args.dry_run else ""
        print(
            f"동기화 완료{mode}: 생성 {counts['created']}, 갱신 {counts['updated']}, "
            f"변경 없음 {counts['unchanged']}, 충돌 {counts['conflict']}, 오류 {counts['error']}"
        )
        for result in results:
            if result["status"] in ("conflict", "error"):
                print(f"  - [{result['status']}] {result['filename']}: {result['reason']}")
    return exit_code_for(counts)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
