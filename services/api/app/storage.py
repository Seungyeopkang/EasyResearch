"""SQLite storage and content-addressed files for the local workspace."""
from __future__ import annotations

import hashlib
import os
import shutil
import sqlite3
import tempfile
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional


ROOT = Path(__file__).resolve().parents[3]
SCHEMA_VERSION = 7
_server_lock = None


def data_dir() -> Path:
    return Path(os.environ.get("EASYRESEARCH_DATA_DIR", str(ROOT / "data"))).resolve()


def lock_server() -> None:
    """Hold an OS lock for the life of the single local server."""
    global _server_lock
    if _server_lock is not None:
        raise RuntimeError("서버 잠금이 이미 사용 중입니다.")
    root = data_dir()
    root.mkdir(parents=True, exist_ok=True)
    handle = open(root / "server.lock", "a+b")
    try:
        if os.name == "nt":
            import msvcrt
            handle.seek(0)
            if not handle.read(1):
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        handle.close()
        raise RuntimeError("이 라이브러리는 다른 EasyResearch 서버에서 사용 중입니다.") from exc
    _server_lock = handle


def unlock_server() -> None:
    global _server_lock
    if _server_lock is not None:
        _server_lock.close()
        _server_lock = None


def new_id() -> str:
    return str(uuid.uuid4())


def wal_fixed(version: tuple) -> bool:
    """SQLite's 2026 WAL-reset fix also has 3.44 and 3.50 backports."""
    return version >= (3, 51, 3) or (3, 50, 7) <= version < (3, 51, 0) or (3, 44, 6) <= version < (3, 45, 0)


def connect() -> sqlite3.Connection:
    root = data_dir()
    root.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(root / "library.sqlite3"), timeout=15)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA busy_timeout=15000")
    con.execute("PRAGMA synchronous=FULL")
    return con


@contextmanager
def transaction() -> Iterator[sqlite3.Connection]:
    con = connect()
    try:
        yield con
        con.commit()
    except BaseException:
        con.rollback()
        raise
    finally:
        con.close()


SCHEMA_V1 = """
CREATE TABLE IF NOT EXISTS projects (
 id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS files (
 id TEXT PRIMARY KEY, sha256 TEXT NOT NULL UNIQUE, size INTEGER NOT NULL,
 storage_key TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS papers (
 id TEXT PRIMARY KEY, file_id TEXT REFERENCES files(id), title TEXT NOT NULL,
 authors TEXT NOT NULL DEFAULT '[]', year INTEGER, doi TEXT, source TEXT,
 source_id TEXT, source_url TEXT, abstract TEXT NOT NULL DEFAULT '',
 metadata_json TEXT NOT NULL DEFAULT '{}', page_count INTEGER,
 deleted_at TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_papers_doi ON papers(doi);
CREATE TABLE IF NOT EXISTS project_papers (
 project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
 paper_id TEXT NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
 reading_status TEXT NOT NULL DEFAULT 'to_read', last_page INTEGER NOT NULL DEFAULT 0,
 PRIMARY KEY(project_id,paper_id)
);
CREATE TABLE IF NOT EXISTS pages (
 paper_id TEXT NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
 page_index INTEGER NOT NULL, label TEXT, text TEXT NOT NULL DEFAULT '',
 rotation INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL DEFAULT 'unknown',
 PRIMARY KEY(paper_id,page_index)
);
CREATE TABLE IF NOT EXISTS evidence (
 id TEXT PRIMARY KEY, paper_id TEXT NOT NULL REFERENCES papers(id),
 page_index INTEGER NOT NULL, quote TEXT NOT NULL DEFAULT '', note TEXT NOT NULL DEFAULT '',
 prefix TEXT NOT NULL DEFAULT '', suffix TEXT NOT NULL DEFAULT '',
 source TEXT NOT NULL DEFAULT 'manual', status TEXT NOT NULL DEFAULT 'unverified',
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS evidence_revisions (
 id INTEGER PRIMARY KEY AUTOINCREMENT, evidence_id TEXT NOT NULL REFERENCES evidence(id) ON DELETE CASCADE,
 page_index INTEGER NOT NULL, quote TEXT NOT NULL, note TEXT NOT NULL,
 prefix TEXT NOT NULL, suffix TEXT NOT NULL, status TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS ideas (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), title TEXT NOT NULL,
 description TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'draft',
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS idea_evidence (
 idea_id TEXT NOT NULL REFERENCES ideas(id) ON DELETE CASCADE,
 evidence_id TEXT NOT NULL REFERENCES evidence(id), PRIMARY KEY(idea_id,evidence_id)
);
CREATE TABLE IF NOT EXISTS jobs (
 id TEXT PRIMARY KEY, kind TEXT NOT NULL, target_id TEXT, status TEXT NOT NULL DEFAULT 'queued',
 detail TEXT NOT NULL DEFAULT '', error TEXT, attempts INTEGER NOT NULL DEFAULT 0,
 lease_token TEXT, cancel_requested INTEGER NOT NULL DEFAULT 0, pid INTEGER,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS job_events (
 id INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT NOT NULL REFERENCES jobs(id),
 status TEXT NOT NULL, detail TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS ocr_pages (
 job_id TEXT PRIMARY KEY REFERENCES jobs(id), paper_id TEXT NOT NULL REFERENCES papers(id),
 page_index INTEGER NOT NULL, text TEXT NOT NULL, language TEXT NOT NULL,
 source TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS analyses (
 id TEXT PRIMARY KEY, question TEXT NOT NULL, output TEXT NOT NULL,
 evidence_json TEXT NOT NULL, provider TEXT NOT NULL, model TEXT,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS experiments (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
 title TEXT NOT NULL, status TEXT NOT NULL, config_json TEXT NOT NULL,
 result_json TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS search_runs (
 id TEXT PRIMARY KEY, project_id TEXT REFERENCES projects(id), source TEXT NOT NULL,
 query TEXT NOT NULL, status TEXT NOT NULL, results_json TEXT NOT NULL DEFAULT '[]',
 error TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


# Frozen v1 definition. Version 2 adds only independent tables; existing shared
# evidence, file references, and project-specific reading state stay untouched.
SCHEMA_V2_ADDITIONS = """
CREATE TABLE IF NOT EXISTS evidence_provenance (
 evidence_id TEXT PRIMARY KEY REFERENCES evidence(id), capture_method TEXT NOT NULL DEFAULT 'legacy_unknown',
 original_checked INTEGER, file_sha256 TEXT
);
CREATE TABLE IF NOT EXISTS revision_provenance (
 revision_id INTEGER PRIMARY KEY REFERENCES evidence_revisions(id), capture_method TEXT NOT NULL DEFAULT 'legacy_unknown',
 original_checked INTEGER, file_sha256 TEXT
);
CREATE TABLE IF NOT EXISTS project_paper_notes (
 project_id TEXT NOT NULL REFERENCES projects(id), paper_id TEXT NOT NULL REFERENCES papers(id),
 note TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(project_id,paper_id)
);
CREATE TABLE IF NOT EXISTS project_trash (
 project_id TEXT PRIMARY KEY REFERENCES projects(id), deleted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS evidence_trash (
 evidence_id TEXT PRIMARY KEY REFERENCES evidence(id), deleted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS link_trash (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
 paper_id TEXT NOT NULL REFERENCES papers(id), reading_status TEXT NOT NULL,
 last_page INTEGER NOT NULL, deleted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(project_id,paper_id)
);
"""
SCHEMA_V2 = SCHEMA_V1 + SCHEMA_V2_ADDITIONS
SCHEMA_V3_ADDITIONS = """
CREATE TABLE IF NOT EXISTS paper_versions (
 id TEXT PRIMARY KEY, paper_id TEXT NOT NULL REFERENCES papers(id),
 file_id TEXT NOT NULL REFERENCES files(id), label TEXT NOT NULL DEFAULT '',
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, UNIQUE(paper_id,file_id)
);
CREATE TABLE IF NOT EXISTS page_extraction_details (
 paper_id TEXT NOT NULL, page_index INTEGER NOT NULL, parser_version TEXT,
 warning_json TEXT NOT NULL DEFAULT '[]', image_count INTEGER,
 extracted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(paper_id,page_index), FOREIGN KEY(paper_id,page_index) REFERENCES pages(paper_id,page_index) ON DELETE CASCADE
);
"""
SCHEMA_V3 = SCHEMA_V2 + SCHEMA_V3_ADDITIONS
SCHEMA_V4_ADDITIONS = """
CREATE TABLE IF NOT EXISTS evidence_ocr_source (
 evidence_id TEXT PRIMARY KEY REFERENCES evidence(id), job_id TEXT NOT NULL REFERENCES ocr_pages(job_id)
);
CREATE TABLE IF NOT EXISTS revision_ocr_source (
 revision_id INTEGER PRIMARY KEY REFERENCES evidence_revisions(id), job_id TEXT NOT NULL REFERENCES ocr_pages(job_id)
);
"""
SCHEMA_V4 = SCHEMA_V3 + SCHEMA_V4_ADDITIONS
SCHEMA_V5_ADDITIONS = """
CREATE TABLE IF NOT EXISTS paper_version_state (
 version_id TEXT PRIMARY KEY REFERENCES paper_versions(id), revision TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS paper_version_trash (
 version_id TEXT PRIMARY KEY REFERENCES paper_versions(id),
 deleted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""
SCHEMA_V5 = SCHEMA_V4 + SCHEMA_V5_ADDITIONS
SCHEMA_V6_ADDITIONS = """
CREATE TABLE IF NOT EXISTS paper_reading_state (
 paper_id TEXT PRIMARY KEY REFERENCES papers(id), reading_status TEXT NOT NULL DEFAULT 'to_read',
 last_page INTEGER NOT NULL DEFAULT 0, last_opened_at TEXT,
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS categories (
 id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, keywords_json TEXT NOT NULL DEFAULT '[]',
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS paper_categories (
 paper_id TEXT NOT NULL REFERENCES papers(id), category_id TEXT NOT NULL REFERENCES categories(id),
 source TEXT NOT NULL, status TEXT NOT NULL, matched_json TEXT NOT NULL DEFAULT '[]',
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(paper_id,category_id)
);
CREATE TABLE IF NOT EXISTS paper_topics (
 paper_id TEXT NOT NULL REFERENCES papers(id), source TEXT NOT NULL, topic_id TEXT NOT NULL,
 name TEXT NOT NULL, subfield TEXT, field TEXT, score REAL,
 fetched_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(paper_id,source,topic_id)
);
"""
SCHEMA_V6 = SCHEMA_V5 + SCHEMA_V6_ADDITIONS
# v7: research assistant records. AI output is always stored as a draft or
# candidate with its origin, model and input hash; it never replaces evidence.
SCHEMA_V7_ADDITIONS = """
CREATE TABLE IF NOT EXISTS paper_profiles (
 id TEXT PRIMARY KEY, paper_id TEXT NOT NULL REFERENCES papers(id), profile_json TEXT NOT NULL,
 origin TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'draft', model TEXT, input_hash TEXT,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_paper_profiles_paper ON paper_profiles(paper_id,created_at);
CREATE TABLE IF NOT EXISTS paper_links (
 id TEXT PRIMARY KEY, source_paper_id TEXT NOT NULL REFERENCES papers(id),
 target_paper_id TEXT NOT NULL REFERENCES papers(id), relation TEXT NOT NULL, origin TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'suggested', note TEXT NOT NULL DEFAULT '', detail_json TEXT NOT NULL DEFAULT '{}',
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(source_paper_id,target_paper_id,relation)
);
CREATE TABLE IF NOT EXISTS research_gaps (
 id TEXT PRIMARY KEY, project_id TEXT REFERENCES projects(id), title TEXT NOT NULL,
 description TEXT NOT NULL DEFAULT '', gap_type TEXT NOT NULL, paper_ids_json TEXT NOT NULL DEFAULT '[]',
 evidence_json TEXT NOT NULL DEFAULT '[]', origin TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'candidate',
 model TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS chat_threads (
 id TEXT PRIMARY KEY, project_id TEXT REFERENCES projects(id), title TEXT NOT NULL, mode TEXT NOT NULL,
 context_json TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS chat_messages (
 id INTEGER PRIMARY KEY AUTOINCREMENT, thread_id TEXT NOT NULL REFERENCES chat_threads(id) ON DELETE CASCADE,
 role TEXT NOT NULL, content TEXT NOT NULL, meta_json TEXT NOT NULL DEFAULT '{}',
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS research_runs (
 id TEXT PRIMARY KEY, project_id TEXT REFERENCES projects(id), topic TEXT NOT NULL, status TEXT NOT NULL,
 config_json TEXT NOT NULL DEFAULT '{}', state_json TEXT NOT NULL DEFAULT '{}',
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS research_steps (
 id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL REFERENCES research_runs(id) ON DELETE CASCADE,
 iteration INTEGER NOT NULL, stage TEXT NOT NULL, status TEXT NOT NULL, input_json TEXT NOT NULL DEFAULT '{}',
 output_json TEXT NOT NULL DEFAULT '{}', error TEXT, model TEXT, prompt_hash TEXT,
 started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, finished_at TEXT
);
"""
SCHEMA_V7 = SCHEMA_V6 + SCHEMA_V7_ADDITIONS
SCHEMA = SCHEMA_V7
SCHEMAS = {1: SCHEMA_V1, 2: SCHEMA_V2, 3: SCHEMA_V3, 4: SCHEMA_V4, 5: SCHEMA_V5, 6: SCHEMA_V6, 7: SCHEMA_V7}

# Editable default categories. Only the seeding helper below reads this list.
DEFAULT_CATEGORIES = [
    ("최적화", ["optimization", "optimizer", "convergence", "gradient descent", "stochastic gradient", "adam", "learning rate", "hyperparameter", "loss landscape"]),
    ("경량화", ["pruning", "quantization", "distillation", "knowledge distillation", "compression", "lightweight", "efficient inference", "low-rank", "sparsity", "mobile"]),
    ("컴퓨터 비전", ["image", "vision", "detection", "segmentation", "convolutional", "visual"]),
    ("자연어 처리", ["language model", "natural language", "transformer", "translation", "text", "token"]),
    ("생성 모델", ["generative", "diffusion", "gan", "adversarial", "variational autoencoder"]),
    ("강화학습", ["reinforcement learning", "policy", "reward", "agent", "q-learning"]),
]

def _seed_default_categories(con: sqlite3.Connection) -> None:
    """Insert the default categories once; the unique name keeps reruns harmless."""
    import json
    for name, keywords in DEFAULT_CATEGORIES:
        con.execute("INSERT OR IGNORE INTO categories(id,name,keywords_json) VALUES(?,?,?)",
                    (new_id(), name, json.dumps(keywords, ensure_ascii=False)))


def _check_schema_version(con: sqlite3.Connection) -> int:
    version = con.execute("PRAGMA user_version").fetchone()[0]
    if version > SCHEMA_VERSION:
        raise RuntimeError(
            f"이 보관함의 데이터 버전({version})은 이 프로그램이 지원하는 버전({SCHEMA_VERSION})보다 높습니다. "
            "보관함을 변경하지 않았습니다. 최신 EasyResearch로 열어 주세요."
        )
    return version


def _schema_objects(con: sqlite3.Connection) -> dict:
    query = "SELECT type,name,tbl_name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name"
    return {(row[0], row[1]): tuple(row) for row in con.execute(query)}


def _validate_integrity(con: sqlite3.Connection) -> None:
    if [row[0] for row in con.execute("PRAGMA integrity_check")] != ["ok"]:
        raise RuntimeError("데이터베이스 무결성 검사에 실패했습니다. 백업을 확인해 주세요.")
    if con.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise RuntimeError("데이터베이스 연결 관계가 손상되었습니다. 백업을 확인해 주세요.")


def validate_schema_connection(con: sqlite3.Connection, *, allow_unversioned: bool = False,
                               allow_extra: bool = False) -> dict:
    """Validate a v1 DB without changing it; optionally identify legacy v0.

    Additional objects are accepted only for local startup when explicitly
    requested; untrusted backup archives should use the strict default.
    """
    version = _check_schema_version(con)
    if version == 0 and not allow_unversioned:
        raise RuntimeError("버전이 기록되지 않은 보관함입니다. 이관이 필요합니다.")
    schema_version = 1 if version == 0 else version
    schema = SCHEMAS.get(schema_version)
    if schema is None:
        raise RuntimeError("지원하지 않는 보관함 데이터 버전입니다.")
    _validate_integrity(con)
    reference = sqlite3.connect(":memory:")
    try:
        reference.executescript(schema)
        expected = _schema_objects(reference)
    finally:
        reference.close()
    actual = _schema_objects(con)
    if any(actual.get(key) != value for key, value in expected.items()):
        raise RuntimeError("보관함 구조를 확인할 수 없어 변경하지 않았습니다.")
    if not allow_extra and actual != expected:
        raise RuntimeError("지원하지 않는 보관함 구조입니다.")
    return {"source_version": version, "target_version": SCHEMA_VERSION,
            "requires_migration": version != SCHEMA_VERSION}


def _execute_schema(con: sqlite3.Connection, schema: str = None) -> None:
    # executescript() implicitly commits first. Execute each complete statement
    # individually so creation, validation and user_version are one transaction.
    statement = ""
    for line in (SCHEMA if schema is None else schema).splitlines(keepends=True):
        statement += line
        if sqlite3.complete_statement(statement):
            con.execute(statement)
            statement = ""
    if statement.strip():
        raise RuntimeError("보관함 스키마가 완전하지 않습니다.")


def _migrate_unversioned_v1(con: sqlite3.Connection) -> None:
    # This is a version stamp for an already validated, exact v1 structure.
    # It does not infer missing columns or rewrite any existing records.
    validate_schema_connection(con, allow_unversioned=True, allow_extra=True)


def _migrate_v1_v2(con: sqlite3.Connection) -> None:
    _execute_schema(con, SCHEMA_V2_ADDITIONS)
    # v1 did not record how a quote was captured. Only the explicit old OCR
    # confirmation can be retained as a check; its capture origin is unknown.
    con.execute("""INSERT OR IGNORE INTO evidence_provenance(evidence_id,capture_method,original_checked,file_sha256)
        SELECT e.id,'legacy_unknown',CASE WHEN e.source='user_verified_ocr' THEN 1 ELSE NULL END,NULL FROM evidence e""")
    con.execute("""INSERT OR IGNORE INTO revision_provenance(revision_id,capture_method,original_checked,file_sha256)
        SELECT id,'legacy_unknown',NULL,NULL FROM evidence_revisions""")


def _migrate_v2_v3(con: sqlite3.Connection) -> None:
    _execute_schema(con, SCHEMA_V3_ADDITIONS)


def _migrate_v3_v4(con: sqlite3.Connection) -> None:
    # Previous OCR records never identified the result they used. Do not
    # guess a result from the most recent OCR job during migration.
    _execute_schema(con, SCHEMA_V4_ADDITIONS)


def _migrate_v4_v5(con: sqlite3.Connection) -> None:
    # Existing versions remain active; their links and PDF bytes are untouched.
    _execute_schema(con, SCHEMA_V5_ADDITIONS)


def _migrate_v5_v6(con: sqlite3.Connection) -> None:
    # Reading state moves from project links to papers. Existing project values
    # are copied, never deleted; the most advanced status across projects wins.
    _execute_schema(con, SCHEMA_V6_ADDITIONS)
    con.execute("""INSERT INTO paper_reading_state(paper_id,reading_status,last_page,last_opened_at,updated_at)
        SELECT p.id,
          COALESCE((SELECT pp.reading_status FROM project_papers pp WHERE pp.paper_id=p.id
              ORDER BY CASE pp.reading_status WHEN 'read' THEN 0 WHEN 'reading' THEN 1 WHEN 'on_hold' THEN 2 ELSE 3 END, pp.project_id LIMIT 1),'to_read'),
          COALESCE((SELECT max(pp.last_page) FROM project_papers pp WHERE pp.paper_id=p.id),0),
          NULL, CURRENT_TIMESTAMP
        FROM papers p""")
    _seed_default_categories(con)


def _migrate_v6_v7(con: sqlite3.Connection) -> None:
    # New tables only; no existing record is read or changed.
    _execute_schema(con, SCHEMA_V7_ADDITIONS)


MIGRATIONS = {0: _migrate_unversioned_v1, 1: _migrate_v1_v2, 2: _migrate_v2_v3, 3: _migrate_v3_v4, 4: _migrate_v4_v5, 5: _migrate_v5_v6, 6: _migrate_v6_v7}


def _migrate_connection(con: sqlite3.Connection, *, allow_extra: bool = False) -> dict:
    """Atomically migrate a validated connection without committing caller work."""
    initial = validate_schema_connection(con, allow_unversioned=True, allow_extra=allow_extra)
    version = initial["source_version"]
    con.execute("BEGIN IMMEDIATE")
    try:
        while version < SCHEMA_VERSION:
            migration = MIGRATIONS.get(version)
            if migration is None:
                raise RuntimeError(f"데이터 버전 {version}의 이관 경로가 없습니다.")
            migration(con)
            version += 1
            con.execute(f"PRAGMA user_version={version}")
            validate_schema_connection(con, allow_extra=allow_extra)
        validate_schema_connection(con, allow_extra=allow_extra)
        con.commit()
    except BaseException:
        con.rollback()
        raise
    return initial


def _copy_database(source: sqlite3.Connection, destination: Path) -> None:
    """Write a new SQLite backup; never replace an existing destination."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("xb"):
        pass
    try:
        target = sqlite3.connect(str(destination))
        try:
            source.backup(target)
        finally:
            target.close()
    except BaseException:
        destination.unlink(missing_ok=True)
        raise


def migrate_database_copy(source: Path, destination: Path) -> dict:
    """Copy and migrate a validated DB, leaving source and existing files intact.

    The destination must not exist and should be within a disposable restore
    staging directory. On any failure a newly created destination is removed.
    """
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if source == destination:
        raise ValueError("원본과 이관 대상 경로가 같습니다.")
    read = sqlite3.connect(source.as_uri() + "?mode=ro", uri=True, timeout=15)
    created = False
    try:
        result = validate_schema_connection(read, allow_unversioned=True)
        _copy_database(read, destination)
        created = True
        target = sqlite3.connect(str(destination), timeout=15)
        try:
            target.execute("PRAGMA foreign_keys=ON")
            _migrate_connection(target)
        finally:
            target.close()
        return result
    except BaseException:
        if created:
            destination.unlink(missing_ok=True)
        raise
    finally:
        read.close()


def init_db() -> None:
    # Read-only preflight must precede journal-mode changes and all DB writes.
    database = data_dir() / "library.sqlite3"
    needs_migration = False
    if database.exists():
        read = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True, timeout=15)
        try:
            version = _check_schema_version(read)
            objects = _schema_objects(read)
            if objects or version:
                state = validate_schema_connection(read, allow_unversioned=True, allow_extra=True)
                needs_migration = state["requires_migration"]
                if needs_migration:
                    # Preserve a validated, consistent snapshot before touching
                    # the live DB. PDF files are never changed by migration.
                    snapshot = data_dir() / "migration-backups" / (new_id() + ".sqlite3")
                    _copy_database(read, snapshot)
                    try:
                        check = sqlite3.connect(snapshot.as_uri() + "?mode=ro", uri=True)
                        try:
                            validate_schema_connection(check, allow_unversioned=True, allow_extra=True)
                        finally:
                            check.close()
                    except BaseException:
                        snapshot.unlink(missing_ok=True)
                        raise
            elif version == 0:
                # Empty SQLite file is a fresh installation.
                pass
        finally:
            read.close()
    con = connect()
    try:
        version = _check_schema_version(con)
        if not _schema_objects(con) and version == 0:
            con.execute("BEGIN IMMEDIATE")
            try:
                _execute_schema(con)
                _seed_default_categories(con)
                con.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
                validate_schema_connection(con)
                con.commit()
            except BaseException:
                con.rollback()
                raise
        else:
            _migrate_connection(con, allow_extra=True)
        # Switch journal only after validation and migration succeed.
        journal = "WAL" if wal_fixed(sqlite3.sqlite_version_info) else "DELETE"
        con.execute("PRAGMA journal_mode=" + journal)
    finally:
        con.close()


def store_stream(stream, max_bytes: int = 100 * 1024 * 1024) -> tuple:
    """Copy a stream into a content-addressed location without trusting its name."""
    root = data_dir()
    tmp_dir = root / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix="upload-", suffix=".tmp", dir=str(tmp_dir))
    digest = hashlib.sha256()
    size = 0
    header = b""
    try:
        with os.fdopen(fd, "wb") as out:
            while True:
                chunk = stream.read(1024 * 1024)
                if not chunk:
                    break
                if size == 0:
                    header = chunk[:1024]
                size += len(chunk)
                if size > max_bytes:
                    raise ValueError("PDF가 허용 크기를 초과했습니다.")
                digest.update(chunk)
                out.write(chunk)
            out.flush()
            os.fsync(out.fileno())
        if b"%PDF-" not in header:
            raise ValueError("PDF 파일 형식을 확인할 수 없습니다.")
        sha = digest.hexdigest()
        target = root / "files" / sha[:2] / (sha + ".pdf")
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            existing = hashlib.sha256()
            with target.open("rb") as old:
                for part in iter(lambda: old.read(1024 * 1024), b""):
                    existing.update(part)
            if existing.hexdigest() != sha:
                raise ValueError("기존 PDF가 손상되었습니다. 백업에서 복원해 주세요.")
            os.unlink(temporary)
        else:
            os.replace(temporary, target)
        return sha, size, target.relative_to(root).as_posix()
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def file_path(storage_key: str) -> Path:
    root = data_dir()
    path = (root / storage_key).resolve()
    if root not in path.parents:
        raise ValueError("잘못된 파일 경로입니다.")
    return path


def backup_database(destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    source = connect()
    dest = sqlite3.connect(str(destination))
    try:
        source.backup(dest)
    finally:
        dest.close()
        source.close()
