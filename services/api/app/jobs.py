"""Single local document worker with persisted state and fenced results."""
from __future__ import annotations

import os
import json
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

from . import storage
from .pdf_processing import PDFProcessingError, inspect_pdf, locate_quote, ocr_page_windows
from .process_control import ProcessControlError, start_windows_worker

_stop = threading.Event()
_thread = None


def _verify_source(path, expected_size, expected_hash):
    """Do not persist results derived from a modified or missing original."""
    import hashlib
    try:
        digest = hashlib.sha256()
        size = 0
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                size += len(chunk)
                digest.update(chunk)
        if size != expected_size or digest.hexdigest() != expected_hash:
            raise PDFProcessingError("source_changed", "Original PDF changed or is damaged")
    except OSError as exc:
        raise PDFProcessingError("source_changed", "Original PDF is missing or unreadable") from exc


def add_event(con, job_id, status, detail=""):
    con.execute("INSERT INTO job_events(job_id,status,detail) VALUES(?,?,?)", (job_id, status, detail))


def enqueue_pdf(con, paper_id):
    job_id = storage.new_id()
    con.execute("INSERT INTO jobs(id,kind,target_id) VALUES(?,?,?)", (job_id, "pdf_extract", paper_id))
    add_event(con, job_id, "queued")
    return job_id


def enqueue_ocr(con, paper_id, page_index, language):
    job_id = storage.new_id()
    detail = json.dumps({"page_index": page_index, "language": language})
    con.execute("INSERT INTO jobs(id,kind,target_id,detail) VALUES(?,?,?,?)", (job_id, "ocr_page", paper_id, detail))
    add_event(con, job_id, "queued")
    return job_id


def cancel(job_id):
    with storage.transaction() as con:
        row = con.execute("SELECT status FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not row:
            return False
        if row["status"] == "queued":
            con.execute("UPDATE jobs SET status='cancelled',cancel_requested=1,updated_at=CURRENT_TIMESTAMP WHERE id=?", (job_id,))
            add_event(con, job_id, "cancelled")
        elif row["status"] == "running":
            con.execute("UPDATE jobs SET cancel_requested=1,updated_at=CURRENT_TIMESTAMP WHERE id=?", (job_id,))
            add_event(con, job_id, "cancel_requested")
    return True


def execute_pdf(job_id, token):
    """Run in a child process; result commit must still own its lease."""
    try:
        with storage.transaction() as con:
            row = con.execute("SELECT j.target_id,f.storage_key,f.size,f.sha256 FROM jobs j JOIN papers p ON p.id=j.target_id JOIN files f ON f.id=p.file_id WHERE j.id=? AND j.lease_token=?", (job_id, token)).fetchone()
        if not row:
            return
        path = storage.file_path(row["storage_key"])
        _verify_source(path, row["size"], row["sha256"])
        result = inspect_pdf(path)
        if result["sha256"] != row["sha256"] or result["size_bytes"] != row["size"]:
            raise PDFProcessingError("source_changed", "Original PDF changed during extraction")
        _verify_source(path, row["size"], row["sha256"])
        with storage.transaction() as con:
            con.execute("BEGIN IMMEDIATE")
            owner = con.execute("SELECT id FROM jobs WHERE id=? AND status='running' AND lease_token=? AND cancel_requested=0", (job_id, token)).fetchone()
            if not owner:
                return
            preserved = 0
            for page in result["pages"]:
                existing = con.execute("SELECT text FROM pages WHERE paper_id=? AND page_index=?", (row["target_id"], page["page_index"])).fetchone()
                # A transient page failure must not erase a previous usable
                # extraction. Nor should a new empty extraction replace text
                # previously obtained from the same hash-checked PDF.
                if existing and (page["status"] == "failed" or (existing["text"].strip() and not page["text"].strip())):
                    preserved += 1
                    continue
                con.execute("INSERT INTO pages(paper_id,page_index,label,text,rotation,status) VALUES(?,?,?,?,?,?) ON CONFLICT(paper_id,page_index) DO UPDATE SET label=excluded.label,text=excluded.text,rotation=excluded.rotation,status=excluded.status", (row["target_id"], page["page_index"], page["page_label"], page["text"], page["rotation"] or 0, page["status"]))
                con.execute("""INSERT INTO page_extraction_details(paper_id,page_index,parser_version,warning_json,image_count)
                    VALUES(?,?,?,?,?) ON CONFLICT(paper_id,page_index) DO UPDATE SET
                    parser_version=excluded.parser_version,warning_json=excluded.warning_json,
                    image_count=excluded.image_count,extracted_at=CURRENT_TIMESTAMP""",
                    (row["target_id"], page["page_index"], result.get("parser_version"),
                     json.dumps(page.get("warnings", []), ensure_ascii=False), page.get("image_count")))
            con.execute("UPDATE papers SET page_count=? WHERE id=?", (result["page_count"], row["target_id"]))
            for evidence in con.execute("""SELECT e.id,e.page_index,e.quote,e.prefix,e.suffix,
                    p.capture_method,s.job_id AS ocr_job_id FROM evidence e
                    LEFT JOIN evidence_provenance p ON p.evidence_id=e.id
                    LEFT JOIN evidence_ocr_source s ON s.evidence_id=e.id WHERE e.paper_id=?""", (row["target_id"],)).fetchall():
                if evidence["page_index"] >= result["page_count"]:
                    evidence_status = "invalid_page"
                elif evidence["quote"].strip():
                    if evidence["capture_method"] == "ocr":
                        page = con.execute("SELECT text FROM ocr_pages WHERE job_id=? AND paper_id=? AND page_index=?", (evidence["ocr_job_id"], row["target_id"], evidence["page_index"])).fetchone()
                        absent_status = "ocr_unavailable"
                    else:
                        page = con.execute("SELECT text FROM pages WHERE paper_id=? AND page_index=?", (row["target_id"], evidence["page_index"])).fetchone()
                        absent_status = "unverified"
                    evidence_status = locate_quote(page["text"], evidence["quote"], evidence["prefix"], evidence["suffix"])["status"] if page and page["text"] else absent_status
                else:
                    evidence_status = "unverified"
                con.execute("UPDATE evidence SET status=? WHERE id=?", (evidence_status, evidence["id"]))
            status = "partial" if result["status"] == "partial" or preserved else "completed"
            detail = "일부 페이지 추출이 불완전합니다. 기존 결과가 있으면 보존했습니다." if status == "partial" else "PDF 텍스트 추출 완료. 페이지 원문 확인이 필요합니다."
            con.execute("UPDATE jobs SET status=?,detail=?,pid=NULL,updated_at=CURRENT_TIMESTAMP WHERE id=?", (status, detail, job_id))
            add_event(con, job_id, status)
    except Exception as exc:
        # Parser errors are classified, but document contents and paths are not logged.
        code = exc.code if isinstance(exc, PDFProcessingError) else "processing_error"
        with storage.transaction() as con:
            changed = con.execute("UPDATE jobs SET status='failed',error=?,pid=NULL,updated_at=CURRENT_TIMESTAMP WHERE id=? AND status='running' AND lease_token=? AND cancel_requested=0", (code, job_id, token)).rowcount
            if changed:
                add_event(con, job_id, "failed", code)


def execute_ocr(job_id, token):
    try:
        with storage.transaction() as con:
            row = con.execute("SELECT j.target_id,j.detail,f.storage_key,f.size,f.sha256 FROM jobs j JOIN papers p ON p.id=j.target_id JOIN files f ON f.id=p.file_id WHERE j.id=? AND j.lease_token=?", (job_id, token)).fetchone()
        if not row:
            return
        settings = json.loads(row["detail"])
        path = storage.file_path(row["storage_key"])
        _verify_source(path, row["size"], row["sha256"])
        result = ocr_page_windows(path, settings["page_index"], settings["language"])
        if (isinstance(result.get("page_index"), bool) or
                result.get("page_index") != settings["page_index"]):
            raise PDFProcessingError("page_mismatch", "OCR returned a different page")
        actual_language = result.get("language")
        requested_language = settings.get("language")
        if (not isinstance(actual_language, str) or not isinstance(requested_language, str) or
                actual_language.split('-')[0].lower() != requested_language.split('-')[0].lower() or
                ('-' in requested_language and actual_language.lower() != requested_language.lower())):
            raise PDFProcessingError("language_mismatch", "OCR returned a different language")
        _verify_source(path, row["size"], row["sha256"])
        with storage.transaction() as con:
            con.execute("BEGIN IMMEDIATE")
            owner = con.execute("SELECT id FROM jobs WHERE id=? AND status='running' AND lease_token=? AND cancel_requested=0", (job_id, token)).fetchone()
            if not owner:
                return
            con.execute("INSERT INTO ocr_pages(job_id,paper_id,page_index,text,language,source,status) VALUES(?,?,?,?,?,?,?)", (job_id, row["target_id"], result["page_index"], result["text"], result["language"], result["text_source"], result["status"]))
            # Keep requested language and page in detail after completion;
            # ocr_pages records the actual recognizer language separately.
            con.execute("UPDATE jobs SET status='completed',pid=NULL,updated_at=CURRENT_TIMESTAMP WHERE id=?", (job_id,))
            add_event(con, job_id, "completed", "OCR 결과는 원문과 대조해야 합니다.")
    except Exception as exc:
        code = exc.code if isinstance(exc, PDFProcessingError) else "processing_error"
        with storage.transaction() as con:
            changed = con.execute("UPDATE jobs SET status='failed',error=?,pid=NULL,updated_at=CURRENT_TIMESTAMP WHERE id=? AND status='running' AND lease_token=? AND cancel_requested=0", (code, job_id, token)).rowcount
            if changed:
                add_event(con, job_id, "failed", code)


def _claim():
    with storage.transaction() as con:
        con.execute("BEGIN IMMEDIATE")
        row = con.execute("SELECT id,kind FROM jobs WHERE status='queued' ORDER BY created_at,id LIMIT 1").fetchone()
        if not row:
            return None
        token = storage.new_id()
        changed = con.execute("UPDATE jobs SET status='running',attempts=attempts+1,lease_token=?,updated_at=CURRENT_TIMESTAMP WHERE id=? AND status='queued'", (token, row["id"])).rowcount
        if not changed:
            return None
        add_event(con, row["id"], "running")
        return row["id"], row["kind"], token


def _finish_aborted(job_id, token, status, error=None):
    with storage.transaction() as con:
        changed = con.execute("UPDATE jobs SET status=?,error=?,pid=NULL,lease_token=NULL,updated_at=CURRENT_TIMESTAMP WHERE id=? AND status='running' AND lease_token=?", (status, error, job_id, token)).rowcount
        if changed:
            add_event(con, job_id, status, error or "")


def _remove_attempt(path):
    base = (storage.data_dir() / "tmp" / "jobs").resolve()
    resolved = path.resolve()
    if base not in resolved.parents:
        raise ValueError("invalid job temporary directory")
    if resolved.exists():
        shutil.rmtree(str(resolved))


def _loop():
    while not _stop.is_set():
        claimed = _claim()
        if claimed is None:
            _stop.wait(0.5)
            continue
        job_id, kind, token = claimed
        if kind not in {"pdf_extract", "ocr_page"}:
            _finish_aborted(job_id, token, "failed", "unsupported_job")
            continue
        attempt = storage.data_dir() / "tmp" / "jobs" / (job_id + "-" + token)
        tree = None
        proc = None
        cleanup_confirmed = False
        try:
            attempt.mkdir(parents=True, exist_ok=False)
            # PDF/OCR workers do not need model or scholarly API credentials.
            # Keep only OS/runtime paths and the library location.
            allowed = {"path", "pathext", "systemroot", "windir", "systemdrive", "comspec",
                       "programfiles", "programfiles(x86)", "programdata", "commonprogramfiles",
                       "userprofile", "appdata", "localappdata", "home", "lang", "lc_all"}
            env = {key: value for key, value in os.environ.items() if key.lower() in allowed}
            env["EASYRESEARCH_DATA_DIR"] = str(storage.data_dir())
            env["TEMP"] = str(attempt)
            env["TMP"] = str(attempt)
            if os.name == "nt":
                tree = start_windows_worker("app.jobs", ["execute", job_id, token], Path(__file__).resolve().parents[1], env=env)
                proc = tree.process
            else:
                proc = subprocess.Popen([sys.executable, "-m", "app.jobs", "execute", job_id, token],
                                        cwd=str(Path(__file__).resolve().parents[1]), env=env,
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                        start_new_session=True)
            with storage.transaction() as con:
                con.execute("UPDATE jobs SET pid=? WHERE id=? AND lease_token=?", (proc.pid, job_id, token))
            started = time.monotonic()
            while proc.poll() is None:
                with storage.transaction() as con:
                    row = con.execute("SELECT cancel_requested FROM jobs WHERE id=? AND lease_token=?", (job_id, token)).fetchone()
                if _stop.is_set() or not row or row["cancel_requested"] or time.monotonic() - started > 600:
                    if tree:
                        tree.terminate(timeout=10)
                    else:
                        import signal
                        os.killpg(proc.pid, signal.SIGKILL)
                        proc.wait(timeout=5)
                    _finish_aborted(job_id, token, "cancelled" if row and row["cancel_requested"] else "failed", "interrupted_or_timeout")
                    break
                _stop.wait(0.3)
            else:
                # A child killed or crashed before writing a terminal status.
                _finish_aborted(job_id, token, "failed", "worker_exited")
        except (OSError, ProcessControlError, subprocess.TimeoutExpired):
            _finish_aborted(job_id, token, "failed", "worker_cleanup_or_start_failed")
        finally:
            if tree:
                try:
                    tree.close(timeout=10)
                    cleanup_confirmed = True
                except (OSError, ProcessControlError, subprocess.TimeoutExpired):
                    # Keep the temporary folder if termination cannot be verified.
                    cleanup_confirmed = False
            elif proc is None or proc.poll() is not None:
                cleanup_confirmed = True
            if cleanup_confirmed:
                try:
                    _remove_attempt(attempt)
                except (OSError, ValueError):
                    pass


def start():
    global _thread
    if _thread and _thread.is_alive():
        return
    _stop.clear()
    # The server's OS lock is held before startup. After a crash the Windows
    # Job Object closes with the supervisor, so old attempt files are orphaned.
    base = storage.data_dir() / "tmp" / "jobs"
    if os.name == "nt" and base.is_dir():
        for candidate in base.iterdir():
            if candidate.is_dir() and not candidate.is_symlink() and re.fullmatch(r"[0-9a-f-]{36}-[0-9a-f-]{36}", candidate.name):
                try:
                    _remove_attempt(candidate)
                except (OSError, ValueError):
                    pass
    # This app is a single local server. Invalidating leases fences any child
    # left after a previous server crash before a new attempt can start.
    with storage.transaction() as con:
        rows = con.execute("SELECT id,cancel_requested FROM jobs WHERE status='running'").fetchall()
        for row in rows:
            status = "cancelled" if row["cancel_requested"] else "queued"
            con.execute("UPDATE jobs SET status=?,lease_token=NULL,pid=NULL,updated_at=CURRENT_TIMESTAMP WHERE id=?", (status, row["id"]))
            add_event(con, row["id"], status, "recovered after restart")
    _thread = threading.Thread(target=_loop, name="easyresearch-worker", daemon=True)
    _thread.start()


def stop():
    _stop.set()
    if _thread:
        _thread.join(timeout=25)
        return not _thread.is_alive()
    return True


if __name__ == "__main__" and len(sys.argv) == 4 and sys.argv[1] == "execute":
    with storage.transaction() as con:
        record = con.execute("SELECT kind FROM jobs WHERE id=? AND lease_token=?", (sys.argv[2], sys.argv[3])).fetchone()
    if record and record["kind"] == "pdf_extract":
        execute_pdf(sys.argv[2], sys.argv[3])
    elif record and record["kind"] == "ocr_page":
        execute_ocr(sys.argv[2], sys.argv[3])
