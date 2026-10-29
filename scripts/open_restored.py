"""Choose and open a previously restored library as a separate workspace."""
from __future__ import annotations

import hashlib
import os
import re
import sqlite3
import stat
import sys
import uuid
from pathlib import Path

import launch

sys.path.insert(0, str(launch.API_DIR))
from app import storage  # noqa: E402


def _plain_directory(path: Path) -> bool:
    """Reject symlinks and Windows junctions/reparse points."""
    try:
        info = path.lstat()
        return (stat.S_ISDIR(info.st_mode) and not stat.S_ISLNK(info.st_mode)
                and not (getattr(info, "st_file_attributes", 0) & 0x400))
    except OSError:
        return False


def restored_libraries(root: Path) -> list:
    parent = root / "restores"
    if not _plain_directory(parent):
        return []
    entries = []
    for entry in parent.iterdir():
        try:
            if str(uuid.UUID(entry.name)) != entry.name or not _plain_directory(entry) or (entry / ".incomplete").exists():
                continue
        except ValueError:
            continue
        entries.append(entry)
    return sorted(entries, key=lambda item: item.stat().st_mtime, reverse=True)


def validate_library(path: Path, root: Path) -> dict:
    """Recheck a restore before opening it. Never write to it during checking."""
    parent = root / "restores"
    if not _plain_directory(parent) or not _plain_directory(path):
        raise ValueError("복원 폴더를 찾을 수 없거나 연결 경로입니다.")
    if (path / ".incomplete").exists():
        raise ValueError("복원이 완료되지 않아 이 보관함을 열 수 없습니다.")
    try:
        if str(uuid.UUID(path.name)) != path.name or path.parent.resolve() != parent.resolve():
            raise ValueError("복원 경로가 올바르지 않습니다.")
    except ValueError as exc:
        raise ValueError("복원 경로가 올바르지 않습니다.") from exc
    db = path / "library.sqlite3"
    info = db.lstat()
    if not stat.S_ISREG(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
        raise ValueError("복원 데이터베이스가 일반 파일이 아닙니다.")
    con = sqlite3.connect(db.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        storage.validate_schema_connection(con)
        files = con.execute("SELECT storage_key,sha256,size FROM files").fetchall()
        counts = {name: con.execute("SELECT count(*) FROM " + name).fetchone()[0]
                  for name in ("projects", "papers", "evidence")}
    finally:
        con.close()
    for key, expected, size in files:
        match = re.fullmatch(r"files/([0-9a-f]{2})/([0-9a-f]{64})\.pdf", key)
        if not match or match.group(2) != expected or match.group(1) != expected[:2]:
            raise ValueError("PDF 참조가 올바르지 않습니다.")
        file_path = path / "files" / match.group(1) / (expected + ".pdf")
        if not _plain_directory(path / "files") or not _plain_directory(file_path.parent):
            raise ValueError("PDF 폴더가 없거나 연결 경로입니다.")
        info = file_path.lstat()
        if not stat.S_ISREG(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400 or info.st_size != size:
            raise ValueError("PDF 파일이 없거나 크기가 다릅니다.")
        digest = hashlib.sha256()
        with file_path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        if digest.hexdigest() != expected:
            raise ValueError("PDF 파일이 백업 기록과 다릅니다.")
    return {**counts, "files": len(files)}


def main() -> int:
    root = storage.data_dir()
    if launch.probe_server() != "free":
        print("8000번 포트가 사용 중입니다. 현재 앱을 종료한 뒤 다시 실행하세요.")
        return 1
    try:
        entries = restored_libraries(root)
        if not entries:
            print("이 보관함에 복원된 자료가 없습니다. 앱에서 먼저 백업을 복원하세요.")
            return 1
        print("복원된 보관함을 선택하세요. 기존 보관함은 변경하지 않습니다.")
        for number, entry in enumerate(entries, 1):
            print(f"{number}. {entry.name}")
        choice = input("번호 입력 (취소하려면 Enter): ").strip()
        if not choice:
            return 0
        if not choice.isdecimal() or not 1 <= int(choice) <= len(entries):
            print("목록의 번호를 입력하세요.")
            return 1
        selected = entries[int(choice) - 1]
        print("복원 자료와 PDF를 검증하고 있습니다...")
        summary = validate_library(selected, root)
        print(f"검증 완료: 프로젝트 {summary['projects']}개, 논문 {summary['papers']}편, "
              f"근거 {summary['evidence']}개, PDF {summary['files']}개")
        print("복원된 별도 보관함을 엽니다. 여기서 변경한 기록은 이 복원본에 저장됩니다.")
        os.environ["EASYRESEARCH_DATA_DIR"] = str(selected)
        return launch.main(require_free=True)
    except (OSError, sqlite3.Error, ValueError, RuntimeError) as exc:
        print("복원된 보관함을 열지 못했습니다:", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
