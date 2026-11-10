"""EasyResearch local HTTP API. Run with uvicorn app.main:app."""
from __future__ import annotations

import hashlib
import errno
import json
import mimetypes
import os
import shutil
import sqlite3
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import analysis_engine, experiment_runner, jobs, scholarly, storage, library_management, evidence_records, integrations, reading_library, categories, search_import, ai_routes, knowledge, research_agent, openalex_routes
from .pdf_processing import locate_quote

app = FastAPI(title="EasyResearch", version="0.1.0", description="로컬 연구 자료와 페이지 근거를 관리하는 API")
app.include_router(library_management.router)
app.include_router(integrations.router)
app.include_router(reading_library.router)
app.include_router(categories.router)
app.include_router(search_import.router)
app.include_router(ai_routes.router)
app.include_router(knowledge.router)
app.include_router(research_agent.router)
app.include_router(openalex_routes.router)
WEB = storage.ROOT / "apps" / "web"
# Windows may register .mjs as text/plain, which browsers refuse as a module.
mimetypes.add_type("text/javascript", ".mjs", strict=True)


@app.middleware("http")
async def local_boundary(request: Request, call_next):
    host = request.headers.get("host", "").split(":", 1)[0].lower()
    if host not in {"127.0.0.1", "localhost", "testserver"}:
        return JSONResponse(status_code=403, content={"detail": "로컬 주소로만 접근할 수 있습니다."})
    origin = request.headers.get("origin")
    if origin:
        parsed = urlparse(origin)
        # Scheme and full netloc must match the app origin; this also blocks
        # browsers from untrusted websites on a different localhost port.
        if parsed.scheme not in {"http", "https"} or parsed.netloc.lower() != request.headers.get("host", "").lower():
            return JSONResponse(status_code=403, content={"detail": "허용되지 않은 요청 출처입니다."})
    if request.method in {"POST", "PUT", "PATCH", "DELETE"} and request.headers.get("X-EasyResearch") != "1":
        return JSONResponse(status_code=403, content={"detail": "X-EasyResearch: 1 헤더가 필요합니다."})
    response = await call_next(request)
    # After an app update the browser must revalidate the page, scripts and
    # styles (cheap ETag check) instead of mixing cached old and new files.
    if request.url.path == "/" or (request.url.path.startswith("/assets/") and "/vendor/" not in request.url.path):
        response.headers["Cache-Control"] = "no-cache"
    return response


@app.on_event("startup")
def startup():
    storage.lock_server()
    try:
        storage.init_db()
        jobs.start()
    except BaseException:
        storage.unlock_server()
        raise


@app.on_event("shutdown")
def shutdown():
    if jobs.stop():
        storage.unlock_server()


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=20000)


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=20000)


class PaperFromSearch(BaseModel):
    project_id: Optional[str] = None
    paper: Dict[str, Any]


class ManualPaperCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    authors: List[str] = Field(default_factory=list, max_length=100)
    year: Optional[int] = Field(default=None, ge=1, le=9999, strict=True)
    doi: Optional[str] = Field(default=None, max_length=1000)


class PaperUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=500)
    authors: Optional[List[str]] = Field(default=None, max_length=100)
    year: Optional[int] = Field(default=None, ge=0, le=9999)
    doi: Optional[str] = Field(default=None, max_length=1000)
    reading_status: Optional[str] = None
    last_page: Optional[int] = Field(default=None, ge=0)
    project_id: Optional[str] = None


class EvidenceCreate(BaseModel):
    page_index: int = Field(ge=0)
    quote: str = Field(default="", max_length=20000)
    note: str = Field(default="", max_length=20000)
    prefix: str = Field(default="", max_length=1000)
    suffix: str = Field(default="", max_length=1000)
    verified_with_original: Optional[bool] = None
    capture_method: Optional[str] = None
    ocr_job_id: Optional[str] = Field(default=None, max_length=100)


class OCRRequest(BaseModel):
    language: str = Field(default="ko", max_length=35, pattern=r"^[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*$")


class IdeaCreate(BaseModel):
    project_id: str
    title: str = Field(min_length=1, max_length=500)
    description: str = Field(default="", max_length=20000)
    evidence_ids: List[str] = Field(default_factory=list, max_length=1000)


class IdeaUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=500)
    description: Optional[str] = Field(default=None, max_length=20000)
    status: Optional[str] = None
    evidence_ids: Optional[List[str]] = Field(default=None, max_length=1000)


class AnalysisRequest(BaseModel):
    paper_ids: List[str] = Field(min_length=1, max_length=20)
    question: str = Field(min_length=1, max_length=2000)
    provider: str = "extractive"
    model: Optional[str] = None
    allow_external: bool = False
    evidence_ids: Optional[List[str]] = Field(default=None, max_length=8)
    preview_hash: Optional[str] = None


class ComparisonRequest(BaseModel):
    paper_ids: List[str] = Field(min_length=2, max_length=20)
    question: str = ""


class ExperimentRequest(BaseModel):
    project_id: str
    title: str = Field(default="평균 예측 기준선", min_length=1, max_length=500)
    values: List[float] = Field(min_length=2, max_length=10000)
    seed: int = Field(default=42, ge=0, lt=2**32)


class CodexProposalRequest(BaseModel):
    project_id: str
    prompt: str = Field(min_length=1, max_length=4000)
    user_requested: bool = False


class IsolatedExperimentRequest(ExperimentRequest):
    code: str = Field(min_length=1, max_length=65536)
    image_digest: str


def rowdict(row):
    return dict(row) if row is not None else None


def paper_dict(row):
    item = dict(row)
    item["authors"] = json.loads(item.get("authors") or "[]")
    item["metadata"] = json.loads(item.pop("metadata_json", "{}") or "{}")
    return item


def require_project(con, project_id):
    if not con.execute("SELECT 1 FROM projects WHERE id=? AND id NOT IN (SELECT project_id FROM project_trash)", (project_id,)).fetchone():
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다.")


def require_paper(con, paper_id):
    row = con.execute("SELECT * FROM papers WHERE id=? AND deleted_at IS NULL", (paper_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="논문을 찾을 수 없습니다.")
    return row


@app.get("/api/health")
def health():
    with storage.transaction() as con:
        journal = con.execute("PRAGMA journal_mode").fetchone()[0]
    workspace_scope = hashlib.sha256(os.path.normcase(str(storage.data_dir())).encode("utf-8")).hexdigest()
    return {"status": "ok", "workspace_scope": workspace_scope, "sqlite_version": sqlite3.sqlite_version, "journal_mode": journal,
            "pdf_parser": "pypdf", "docling_available": _available("docling"),
            "ocr_available": os.name == "nt" and bool(shutil.which("pdftoppm")) and bool(shutil.which("powershell.exe")),
            "ocr_engine": "windows_media_ocr" if os.name == "nt" and shutil.which("pdftoppm") and shutil.which("powershell.exe") else None,
            "api_version": "0.1.0"}


def _available(name):
    import importlib.util
    return importlib.util.find_spec(name) is not None


@app.get("/api/projects")
def list_projects():
    with storage.transaction() as con:
        return [dict(row) for row in con.execute("SELECT * FROM projects WHERE id NOT IN (SELECT project_id FROM project_trash) ORDER BY created_at DESC,id")]


@app.post("/api/projects", status_code=201)
def create_project(payload: ProjectCreate):
    name = payload.name.strip()
    if not name:
        raise HTTPException(422, "프로젝트 이름을 입력해 주세요.")
    project_id = storage.new_id()
    with storage.transaction() as con:
        con.execute("INSERT INTO projects(id,name,description) VALUES(?,?,?)", (project_id, name, payload.description))
        return rowdict(con.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone())


@app.patch("/api/projects/{project_id}")
def update_project(project_id: str, payload: ProjectUpdate):
    fields = payload.model_fields_set
    if not fields or any(getattr(payload, field) is None for field in fields):
        raise HTTPException(422, "수정할 값을 입력해 주세요.")
    if "name" in fields and not payload.name.strip():
        raise HTTPException(422, "프로젝트 이름을 입력해 주세요.")
    with storage.transaction() as con:
        require_project(con, project_id)
        if "name" in fields:
            con.execute("UPDATE projects SET name=? WHERE id=?", (payload.name.strip(), project_id))
        if "description" in fields:
            con.execute("UPDATE projects SET description=? WHERE id=?", (payload.description, project_id))
        return rowdict(con.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone())


def paper_with_state(con, paper_id):
    """A paper with its global reading state; a missing state row means to_read / page 0."""
    item = paper_dict(con.execute("SELECT * FROM papers WHERE id=?", (paper_id,)).fetchone())
    item.update(reading_library.reading_state(con, paper_id))
    return item


@app.get("/api/papers")
def list_papers(project_id: Optional[str] = None):
    with storage.transaction() as con:
        if project_id:
            require_project(con, project_id)
            # Project-scoped rows keep the project's own values under reading_status/last_page
            # for existing clients; the global state is exposed as global_* alongside them.
            rows = con.execute("""SELECT p.*,pp.reading_status,pp.last_page,
                    COALESCE(rs.reading_status,'to_read') AS global_reading_status,COALESCE(rs.last_page,0) AS global_last_page,
                    rs.last_opened_at
                FROM papers p JOIN project_papers pp ON pp.paper_id=p.id LEFT JOIN paper_reading_state rs ON rs.paper_id=p.id
                WHERE pp.project_id=? AND p.deleted_at IS NULL ORDER BY p.created_at DESC,p.id""", (project_id,))
        else:
            rows = con.execute("""SELECT p.*,COALESCE(rs.reading_status,'to_read') AS reading_status,COALESCE(rs.last_page,0) AS last_page,
                    rs.last_opened_at FROM papers p LEFT JOIN paper_reading_state rs ON rs.paper_id=p.id
                WHERE p.deleted_at IS NULL ORDER BY p.created_at DESC,p.id""")
        return [paper_dict(row) for row in rows]


def _manual_paper_fields(payload: ManualPaperCreate):
    title = payload.title.strip()
    if not title:
        raise HTTPException(422, "제목을 입력해 주세요.")
    if any(not author.strip() or len(author) > 500 for author in payload.authors):
        raise HTTPException(422, "저자 이름을 확인해 주세요.")
    try:
        doi = scholarly.normalize_doi(payload.doi) if payload.doi and payload.doi.strip() else None
    except ValueError as exc:
        raise HTTPException(422, "DOI 형식을 확인해 주세요.") from exc
    return title, json.dumps([author.strip() for author in payload.authors], ensure_ascii=False), payload.year, doi


@app.post("/api/papers", status_code=201)
def create_library_paper(payload: ManualPaperCreate):
    title, authors, year, doi = _manual_paper_fields(payload)
    paper_id = storage.new_id()
    with storage.transaction() as con:
        # Always create a distinct record; similarity is only a suggestion.
        con.execute("INSERT INTO papers(id,title,authors,year,doi,source) VALUES(?,?,?,?,?,'manual')",
                    (paper_id, title, authors, year, doi))
        return paper_with_state(con, paper_id)


@app.post("/api/projects/{project_id}/papers", status_code=201)
def create_manual_paper(project_id: str, payload: ManualPaperCreate):
    title, authors, year, doi = _manual_paper_fields(payload)
    paper_id = storage.new_id()
    with storage.transaction() as con:
        con.execute("BEGIN IMMEDIATE")
        require_project(con, project_id)
        # Always create a distinct record. Similarity is a suggestion for the
        # user to inspect, never an implicit merge or metadata overwrite.
        con.execute("INSERT INTO papers(id,title,authors,year,doi,source) VALUES(?,?,?,?,?,'manual')",
                    (paper_id, title, authors, year, doi))
        library_management.attach_paper(con, project_id, paper_id)
        return paper_dict(con.execute("""SELECT p.*,pp.reading_status,pp.last_page FROM papers p
            JOIN project_papers pp ON pp.paper_id=p.id WHERE p.id=? AND pp.project_id=?""", (paper_id, project_id)).fetchone())


@app.post("/api/papers/import", status_code=201)
def import_pdf(project_id: Optional[str] = Form(default=None), file: UploadFile = File(...), paper_id: Optional[str] = Form(default=None)):
    with storage.transaction() as con:
        if project_id:
            require_project(con, project_id)
        if paper_id:
            require_paper(con, paper_id)
            if project_id and not con.execute("SELECT 1 FROM project_papers WHERE project_id=? AND paper_id=?", (project_id, paper_id)).fetchone():
                raise HTTPException(404, "프로젝트에 없는 논문입니다.")
    try:
        sha, size, key = storage.store_stream(file.file)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    finally:
        file.file.close()
    with storage.transaction() as con:
        con.execute("BEGIN IMMEDIATE")
        if project_id:
            require_project(con, project_id)
        if paper_id:
            require_paper(con, paper_id)
            if project_id and not con.execute("SELECT 1 FROM project_papers WHERE project_id=? AND paper_id=?", (project_id, paper_id)).fetchone():
                raise HTTPException(409, "업로드 중 프로젝트 연결이 바뀌었습니다. 논문 연결을 확인한 뒤 다시 시도해 주세요.")
        f = con.execute("SELECT * FROM files WHERE sha256=?", (sha,)).fetchone()
        duplicate = f is not None
        if not f:
            file_id = storage.new_id()
            con.execute("INSERT INTO files(id,sha256,size,storage_key) VALUES(?,?,?,?)", (file_id, sha, size, key))
        else:
            file_id = f["id"]
        # A concurrent permanent delete removes an unreferenced PDF only while
        # holding the write lock and only when no files row exists. Re-check
        # under this lock so a record never points to a removed file.
        if not storage.file_path(key).is_file():
            raise HTTPException(409, "PDF를 저장하는 중 파일이 정리되었습니다. 다시 등록해 주세요.")
        p = con.execute("SELECT * FROM papers WHERE file_id=? AND deleted_at IS NULL ORDER BY created_at LIMIT 1", (file_id,)).fetchone()
        if not p and con.execute("SELECT 1 FROM papers WHERE file_id=? AND deleted_at IS NOT NULL", (file_id,)).fetchone():
            raise HTTPException(409, "이 PDF는 휴지통에 있습니다. 기존 논문을 복구해 주세요.")
        if paper_id:
            selected = require_paper(con, paper_id)
            import_action = 'already_attached' if selected['file_id'] == file_id else 'attached_pdf'
            if selected["file_id"] and selected["file_id"] != file_id:
                raise HTTPException(409, "이미 PDF가 연결되어 있습니다. 다른 버전은 별도 논문으로 등록하세요.")
            if p and p["id"] != paper_id:
                raise HTTPException(409, "이 PDF는 이미 다른 논문에 연결되어 있습니다.")
            con.execute("UPDATE papers SET file_id=? WHERE id=?", (file_id, paper_id))
            existing_job = con.execute("SELECT id FROM jobs WHERE kind='pdf_extract' AND target_id=? AND status IN ('queued','running')", (paper_id,)).fetchone()
            job_id = existing_job["id"] if existing_job else jobs.enqueue_pdf(con, paper_id)
        elif p:
            paper_id = p["id"]
            linked = project_id and con.execute("SELECT 1 FROM project_papers WHERE project_id=? AND paper_id=?", (project_id, paper_id)).fetchone()
            import_action = ('already_linked' if linked else 'linked_existing') if project_id else 'already_exists'
            job_id = None
        else:
            paper_id = storage.new_id()
            import_action = 'created_paper'
            title = Path(file.filename or "논문.pdf").stem[:500] or "제목 없는 논문"
            con.execute("INSERT INTO papers(id,file_id,title) VALUES(?,?,?)", (paper_id, file_id, title))
            job_id = jobs.enqueue_pdf(con, paper_id)
        if project_id:
            library_management.attach_paper(con, project_id, paper_id)
        result = paper_with_state(con, paper_id)
        result.update({"duplicate": duplicate, "import_action": import_action, "job_id": job_id, "sha256": sha})
        return result


@app.post("/api/papers/from-search", status_code=201)
def add_search_paper(payload: PaperFromSearch):
    p = payload.paper
    title = str(p.get("title") or "").strip()
    if not title:
        raise HTTPException(422, "논문 제목이 필요합니다.")
    doi = str(p.get("doi") or "").lower().strip() or None
    with storage.transaction() as con:
        if payload.project_id:
            require_project(con, payload.project_id)
        existing = con.execute("SELECT * FROM papers WHERE doi=? AND deleted_at IS NULL", (doi,)).fetchone() if doi else None
        if existing is None and p.get("source") and p.get("source_id"):
            existing = con.execute("SELECT * FROM papers WHERE source=? AND source_id=? AND deleted_at IS NULL", (p["source"], p["source_id"])).fetchone()
        if existing:
            paper_id = existing["id"]
        else:
            paper_id = storage.new_id()
            con.execute("INSERT INTO papers(id,title,authors,year,doi,source,source_id,source_url,abstract,metadata_json) VALUES(?,?,?,?,?,?,?,?,?,?)", (paper_id, title[:500], json.dumps(p.get("authors") or [], ensure_ascii=False), p.get("year"), doi, p.get("source"), p.get("source_id"), p.get("url"), p.get("abstract") or "", json.dumps(p, ensure_ascii=False)))
        if payload.project_id:
            library_management.attach_paper(con, payload.project_id, paper_id)
        item = paper_with_state(con, paper_id)
        item["duplicate"] = existing is not None
        return item


@app.patch("/api/papers/{paper_id}")
def update_paper(paper_id: str, payload: PaperUpdate):
    with storage.transaction() as con:
        paper = require_paper(con, paper_id)
        if payload.title is not None:
            if not payload.title.strip():
                raise HTTPException(422, "제목을 입력해 주세요.")
            con.execute("UPDATE papers SET title=? WHERE id=?", (payload.title.strip(), paper_id))
        fields = payload.model_fields_set
        if "authors" in fields:
            if payload.authors is None or any(not isinstance(a, str) or not a.strip() or len(a) > 500 for a in payload.authors):
                raise HTTPException(422, "저자 이름을 확인해 주세요.")
            con.execute("UPDATE papers SET authors=? WHERE id=?", (json.dumps([a.strip() for a in payload.authors], ensure_ascii=False), paper_id))
        if "year" in fields:
            con.execute("UPDATE papers SET year=? WHERE id=?", (payload.year, paper_id))
        if "doi" in fields:
            try:
                doi = scholarly.normalize_doi(payload.doi) if payload.doi and payload.doi.strip() else None
            except ValueError:
                raise HTTPException(422, "DOI 형식을 확인해 주세요.")
            con.execute("UPDATE papers SET doi=? WHERE id=?", (doi, paper_id))
        if payload.reading_status is not None or payload.last_page is not None:
            if payload.reading_status is not None and payload.reading_status not in reading_library.READING_STATUSES:
                raise HTTPException(422, "읽기 상태가 올바르지 않습니다.")
            if payload.last_page is not None and paper["page_count"] and payload.last_page >= paper["page_count"]:
                raise HTTPException(422, "페이지가 범위를 벗어났습니다.")
            if payload.project_id:
                require_project(con, payload.project_id)
                if not con.execute("SELECT 1 FROM project_papers WHERE paper_id=? AND project_id=?", (paper_id, payload.project_id)).fetchone():
                    raise HTTPException(404, "프로젝트에 없는 논문입니다.")
                if payload.reading_status is not None:
                    con.execute("UPDATE project_papers SET reading_status=? WHERE project_id=? AND paper_id=?", (payload.reading_status, payload.project_id, paper_id))
                if payload.last_page is not None:
                    con.execute("UPDATE project_papers SET last_page=? WHERE project_id=? AND paper_id=?", (payload.last_page, payload.project_id, paper_id))
            # The global state is always updated; a project id additionally keeps the project link values in step.
            previous = reading_library.reading_state(con, paper_id)
            status = payload.reading_status if payload.reading_status is not None else previous["reading_status"]
            last_page = payload.last_page if payload.last_page is not None else previous["last_page"]
            opened = payload.last_page is not None and payload.last_page != previous["last_page"]
            con.execute("""INSERT INTO paper_reading_state(paper_id,reading_status,last_page,last_opened_at,updated_at)
                VALUES(?,?,?,CASE WHEN ? THEN CURRENT_TIMESTAMP ELSE NULL END,CURRENT_TIMESTAMP)
                ON CONFLICT(paper_id) DO UPDATE SET reading_status=excluded.reading_status,last_page=excluded.last_page,
                    last_opened_at=CASE WHEN ? THEN CURRENT_TIMESTAMP ELSE paper_reading_state.last_opened_at END,
                    updated_at=CURRENT_TIMESTAMP""", (paper_id, status, last_page, opened, opened))
            if status == "read" and previous["reading_status"] != "read":
                reading_library.on_paper_read(con, paper_id)
        return paper_with_state(con, paper_id)


@app.get("/api/papers/{paper_id}/file")
def get_pdf(paper_id: str):
    with storage.transaction() as con:
        p = require_paper(con, paper_id)
        if not p["file_id"]:
            raise HTTPException(404, "등록된 PDF가 없습니다.")
        file_row = con.execute("SELECT * FROM files WHERE id=?", (p["file_id"],)).fetchone()
        path = storage.file_path(file_row["storage_key"])
        if not path.is_file():
            raise HTTPException(404, "저장된 PDF 파일을 찾을 수 없습니다.")
        if path.stat().st_size != file_row["size"] or sha256_file(path) != file_row["sha256"]:
            raise HTTPException(409, "저장된 PDF가 손상되었습니다. 백업에서 복원해 주세요.")
        return FileResponse(path, media_type="application/pdf", filename="paper.pdf", content_disposition_type="inline")


@app.get("/api/papers/{paper_id}/pages/{page_index}")
def get_page(paper_id: str, page_index: int):
    if page_index < 0:
        raise HTTPException(422, "페이지 번호가 올바르지 않습니다.")
    with storage.transaction() as con:
        p = require_paper(con, paper_id)
        if p["page_count"] is not None and page_index >= p["page_count"]:
            raise HTTPException(404, "페이지를 찾을 수 없습니다.")
        row = con.execute("SELECT * FROM pages WHERE paper_id=? AND page_index=?", (paper_id, page_index)).fetchone()
        result = rowdict(row) if row else {"paper_id": paper_id, "page_index": page_index, "label": None, "text": "", "status": "pending"}
        ocr = con.execute("SELECT job_id,text,language,source,status,created_at FROM ocr_pages WHERE paper_id=? AND page_index=? ORDER BY rowid DESC LIMIT 1", (paper_id, page_index)).fetchone()
        result["ocr"] = rowdict(ocr)
        detail = con.execute("SELECT parser_version,warning_json,image_count,extracted_at FROM page_extraction_details WHERE paper_id=? AND page_index=?", (paper_id, page_index)).fetchone()
        result["extraction_details"] = ({"parser_version": detail["parser_version"], "warnings": json.loads(detail["warning_json"]), "image_count": detail["image_count"], "extracted_at": detail["extracted_at"]} if detail else None)
        return result


@app.post("/api/papers/{paper_id}/pages/{page_index}/ocr", status_code=202)
def request_ocr(paper_id: str, page_index: int, payload: OCRRequest):
    if page_index < 0:
        raise HTTPException(422, "페이지 번호가 올바르지 않습니다.")
    if not (os.name == "nt" and shutil.which("pdftoppm") and shutil.which("powershell.exe")):
        raise HTTPException(503, "Windows OCR 또는 PDF 렌더러를 사용할 수 없습니다.")
    with storage.transaction() as con:
        con.execute("BEGIN IMMEDIATE")
        paper = require_paper(con, paper_id)
        if not paper["file_id"]:
            raise HTTPException(422, "원문 PDF를 먼저 연결해 주세요.")
        if paper["page_count"] is not None and page_index >= paper["page_count"]:
            raise HTTPException(422, "페이지가 범위를 벗어났습니다.")
        language = payload.language.lower()
        for pending in con.execute("SELECT id,detail FROM jobs WHERE kind='ocr_page' AND target_id=? AND status IN ('queued','running')", (paper_id,)):
            try:
                detail = json.loads(pending['detail'])
                if isinstance(detail,dict) and detail.get('page_index') == page_index and isinstance(detail.get('language'),str) and detail['language'].lower() == language:
                    return {"job_id": pending['id'], "language": language, "reused": True}
            except (ValueError,TypeError):
                continue
        return {"job_id": jobs.enqueue_ocr(con, paper_id, page_index, language), "language": language, "reused": False}


@app.get("/api/papers/{paper_id}/pages/{page_index}/ocr-results")
def list_page_ocr_results(paper_id: str, page_index: int):
    if page_index < 0:
        raise HTTPException(422, "페이지 번호가 올바르지 않습니다.")
    with storage.transaction() as con:
        paper = require_paper(con, paper_id)
        if paper['page_count'] is not None and page_index >= paper['page_count']:
            raise HTTPException(404, "페이지를 찾을 수 없습니다.")
        rows = con.execute("""SELECT job_id,language,source,status,created_at FROM ocr_pages
            WHERE paper_id=? AND page_index=? ORDER BY rowid DESC LIMIT 201""", (paper_id, page_index)).fetchall()
        return {"results": [dict(row) for row in rows[:200]], "truncated": len(rows)>200}


@app.get("/api/papers/{paper_id}/evidence")
def list_evidence(paper_id: str):
    with storage.transaction() as con:
        require_paper(con, paper_id)
        return [evidence_records.evidence_item(con, row) for row in con.execute("SELECT * FROM evidence WHERE paper_id=? AND id NOT IN (SELECT evidence_id FROM evidence_trash) ORDER BY page_index,created_at,id", (paper_id,))]


@app.post("/api/papers/{paper_id}/evidence", status_code=201)
def add_evidence(paper_id: str, payload: EvidenceCreate):
    if not payload.quote.strip() and not payload.note.strip():
        raise HTTPException(422, "구절 또는 메모를 입력해 주세요.")
    evidence_id = storage.new_id()
    with storage.transaction() as con:
        p = require_paper(con, paper_id)
        if not p["file_id"]:
            raise HTTPException(422, "원문 PDF를 먼저 연결해 주세요.")
        if p["page_count"] is not None and payload.page_index >= p["page_count"]:
            raise HTTPException(422, "페이지가 범위를 벗어났습니다.")
        page = con.execute("SELECT text FROM pages WHERE paper_id=? AND page_index=?", (paper_id, payload.page_index)).fetchone()
        match = locate_quote(page["text"], payload.quote, payload.prefix, payload.suffix) if page and payload.quote.strip() else None
        status = match["status"] if match else "page_unverified" if p["page_count"] is None else "unverified"
        method, checked, file_sha, ocr_job_id = evidence_records.capture_details(con, p, payload)
        if method == 'ocr':
            ocr = con.execute("SELECT text FROM ocr_pages WHERE job_id=?", (ocr_job_id,)).fetchone() if ocr_job_id else None
            status = locate_quote(ocr['text'], payload.quote, payload.prefix, payload.suffix)['status'] if ocr and ocr['text'].strip() else 'ocr_unavailable'
        source = "user_verified_ocr" if method == "ocr" and checked else "manual"
        con.execute("INSERT INTO evidence(id,paper_id,page_index,quote,note,prefix,suffix,status,source) VALUES(?,?,?,?,?,?,?,?,?)", (evidence_id, paper_id, payload.page_index, payload.quote, payload.note, payload.prefix, payload.suffix, status, source))
        con.execute("INSERT INTO evidence_provenance(evidence_id,capture_method,original_checked,file_sha256) VALUES(?,?,?,?)", (evidence_id,method,checked,file_sha))
        if ocr_job_id:
            con.execute("INSERT INTO evidence_ocr_source(evidence_id,job_id) VALUES(?,?)", (evidence_id,ocr_job_id))
        return evidence_records.evidence_item(con, con.execute("SELECT * FROM evidence WHERE id=?", (evidence_id,)).fetchone())


@app.put("/api/evidence/{evidence_id}")
def update_evidence(evidence_id: str, payload: EvidenceCreate):
    if not payload.quote.strip() and not payload.note.strip():
        raise HTTPException(422, "구절 또는 메모를 입력해 주세요.")
    with storage.transaction() as con:
        old = con.execute("SELECT * FROM evidence WHERE id=? AND id NOT IN (SELECT evidence_id FROM evidence_trash)", (evidence_id,)).fetchone()
        if not old:
            raise HTTPException(404, "근거를 찾을 수 없습니다.")
        paper = require_paper(con, old["paper_id"])
        if paper["page_count"] is not None and payload.page_index >= paper["page_count"]:
            raise HTTPException(422, "페이지가 범위를 벗어났습니다.")
        page = con.execute("SELECT text FROM pages WHERE paper_id=? AND page_index=?", (old["paper_id"], payload.page_index)).fetchone()
        match = locate_quote(page["text"], payload.quote, payload.prefix, payload.suffix) if page and payload.quote.strip() else None
        status = match["status"] if match else "page_unverified" if paper["page_count"] is None else "unverified"
        method, checked, file_sha, ocr_job_id = evidence_records.capture_details(con, paper, payload, old)
        if method == 'ocr':
            ocr = con.execute("SELECT text FROM ocr_pages WHERE job_id=?", (ocr_job_id,)).fetchone() if ocr_job_id else None
            status = locate_quote(ocr['text'], payload.quote, payload.prefix, payload.suffix)['status'] if ocr and ocr['text'].strip() else 'ocr_unavailable'
        source = "user_verified_ocr" if method == "ocr" and checked else "manual"
        prior = con.execute("SELECT * FROM evidence_provenance WHERE evidence_id=?", (evidence_id,)).fetchone()
        revision = con.execute("INSERT INTO evidence_revisions(evidence_id,page_index,quote,note,prefix,suffix,status) VALUES(?,?,?,?,?,?,?)", (evidence_id, old["page_index"], old["quote"], old["note"], old["prefix"], old["suffix"], old["status"]))
        con.execute("INSERT INTO revision_provenance(revision_id,capture_method,original_checked,file_sha256) VALUES(?,?,?,?)", (revision.lastrowid, prior["capture_method"] if prior else "legacy_unknown", prior["original_checked"] if prior else None, prior["file_sha256"] if prior else None))
        old_ocr = con.execute("SELECT job_id FROM evidence_ocr_source WHERE evidence_id=?", (evidence_id,)).fetchone()
        if old_ocr:
            con.execute("INSERT INTO revision_ocr_source(revision_id,job_id) VALUES(?,?)", (revision.lastrowid, old_ocr["job_id"]))
        con.execute("UPDATE evidence SET page_index=?,quote=?,note=?,prefix=?,suffix=?,status=?,source=?,updated_at=CURRENT_TIMESTAMP WHERE id=?", (payload.page_index, payload.quote, payload.note, payload.prefix, payload.suffix, status, source, evidence_id))
        con.execute("INSERT INTO evidence_provenance(evidence_id,capture_method,original_checked,file_sha256) VALUES(?,?,?,?) ON CONFLICT(evidence_id) DO UPDATE SET capture_method=excluded.capture_method,original_checked=excluded.original_checked,file_sha256=excluded.file_sha256", (evidence_id, method, checked, file_sha))
        con.execute("DELETE FROM evidence_ocr_source WHERE evidence_id=?", (evidence_id,))
        if ocr_job_id:
            con.execute("INSERT INTO evidence_ocr_source(evidence_id,job_id) VALUES(?,?)", (evidence_id,ocr_job_id))
        return evidence_records.evidence_item(con, con.execute("SELECT * FROM evidence WHERE id=?", (evidence_id,)).fetchone())


@app.get("/api/evidence/{evidence_id}/revisions")
def evidence_revisions(evidence_id: str):
    with storage.transaction() as con:
        if not con.execute("SELECT 1 FROM evidence WHERE id=?", (evidence_id,)).fetchone():
            raise HTTPException(404, "근거를 찾을 수 없습니다.")
        return [dict(row) for row in con.execute("""SELECT r.*, COALESCE(p.capture_method,'legacy_unknown') AS capture_method,
            p.original_checked,p.file_sha256,s.job_id AS ocr_job_id FROM evidence_revisions r LEFT JOIN revision_provenance p ON p.revision_id=r.id
            LEFT JOIN revision_ocr_source s ON s.revision_id=r.id
            WHERE r.evidence_id=? ORDER BY r.id DESC""", (evidence_id,))]


@app.get("/api/ocr-results/{job_id}")
def get_ocr_result(job_id: str):
    """A previous OCR result can be inspected independently of later runs."""
    with storage.transaction() as con:
        row = con.execute("""SELECT o.job_id,o.paper_id,o.page_index,o.text,o.language,o.source,o.status,o.created_at
            FROM ocr_pages o JOIN papers p ON p.id=o.paper_id
            WHERE o.job_id=? AND p.deleted_at IS NULL""", (job_id,)).fetchone()
        if not row:
            raise HTTPException(404, "OCR 결과를 찾을 수 없습니다.")
        return dict(row)


@app.get("/api/jobs")
def list_jobs():
    with storage.transaction() as con:
        return [dict(r) for r in con.execute("SELECT id,kind,target_id,status,detail,error,attempts,created_at,updated_at FROM jobs ORDER BY created_at DESC,id LIMIT 100")]


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    with storage.transaction() as con:
        row = con.execute("SELECT id,kind,target_id,status,detail,error,attempts,created_at,updated_at FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not row:
            raise HTTPException(404, "작업을 찾을 수 없습니다.")
        item = dict(row)
        item["events"] = [dict(e) for e in con.execute("SELECT status,detail,created_at FROM job_events WHERE job_id=? ORDER BY id", (job_id,))]
        return item


@app.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: str):
    if not jobs.cancel(job_id):
        raise HTTPException(404, "작업을 찾을 수 없습니다.")
    return get_job(job_id)


@app.post("/api/papers/{paper_id}/extractions", status_code=202)
def extract_again(paper_id: str):
    with storage.transaction() as con:
        p = require_paper(con, paper_id)
        if not p["file_id"]:
            raise HTTPException(422, "추출할 PDF가 없습니다.")
        running = con.execute("SELECT id FROM jobs WHERE kind='pdf_extract' AND target_id=? AND status IN ('queued','running')", (paper_id,)).fetchone()
        return {"job_id": running["id"] if running else jobs.enqueue_pdf(con, paper_id)}


@app.get("/api/search")
def search(q: str, source: str = "openalex", project_id: Optional[str] = None):
    if project_id:
        with storage.transaction() as con:
            require_project(con, project_id)
    if source not in {"openalex", "arxiv", "crossref"}:
        raise HTTPException(422, "검색 소스가 올바르지 않습니다.")
    try:
        if source == "openalex":
            results = scholarly.search_openalex(q, api_key=scholarly.openalex_key())
        elif source == "arxiv":
            results = scholarly.search_arxiv(q)
        else:
            results = [scholarly.lookup_crossref(q)]
        with storage.transaction() as con:
            con.execute("INSERT INTO search_runs(id,project_id,source,query,status,results_json) VALUES(?,?,?,?,?,?)", (storage.new_id(), project_id, source, q, "completed", json.dumps(results, ensure_ascii=False)))
        return results
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except scholarly.ScholarlyError as exc:
        with storage.transaction() as con:
            con.execute("INSERT INTO search_runs(id,project_id,source,query,status,error) VALUES(?,?,?,?,?,?)", (storage.new_id(), project_id, source, q, "failed", exc.code))
        raise HTTPException(502 if exc.status is None or exc.status >= 500 else exc.status, {"source": exc.source, "code": exc.code, "message": exc.message}) from exc


@app.get("/api/search/history")
def search_history(project_id: Optional[str] = None):
    with storage.transaction() as con:
        if project_id:
            require_project(con, project_id)
            rows = con.execute("SELECT * FROM search_runs WHERE project_id=? ORDER BY created_at DESC,id DESC LIMIT 100", (project_id,)).fetchall()
        else:
            rows = con.execute("SELECT * FROM search_runs ORDER BY created_at DESC,id DESC LIMIT 100").fetchall()
    return [{"id": r["id"], "source": r["source"], "query": r["query"], "status": r["status"], "results": json.loads(r["results_json"]), "error": r["error"], "created_at": r["created_at"]} for r in rows]


@app.get("/api/ideas")
def list_ideas(project_id: str):
    with storage.transaction() as con:
        require_project(con, project_id)
        items = [dict(r) for r in con.execute("SELECT * FROM ideas WHERE project_id=? ORDER BY created_at DESC,id", (project_id,))]
        for item in items:
            item["evidence_ids"] = [r[0] for r in con.execute("SELECT evidence_id FROM idea_evidence WHERE idea_id=?", (item["id"],))]
        return items


@app.post("/api/ideas", status_code=201)
def create_idea(payload: IdeaCreate):
    idea_id = storage.new_id()
    if not payload.title.strip():
        raise HTTPException(422, "제목을 입력해 주세요.")
    with storage.transaction() as con:
        require_project(con, payload.project_id)
        evidence_ids = list(dict.fromkeys(payload.evidence_ids))
        validate_idea_evidence(con, payload.project_id, evidence_ids)
        con.execute("INSERT INTO ideas(id,project_id,title,description) VALUES(?,?,?,?)", (idea_id, payload.project_id, payload.title.strip(), payload.description))
        for evidence_id in evidence_ids:
            con.execute("INSERT INTO idea_evidence(idea_id,evidence_id) VALUES(?,?)", (idea_id, evidence_id))
        item = rowdict(con.execute("SELECT * FROM ideas WHERE id=?", (idea_id,)).fetchone())
        item["evidence_ids"] = evidence_ids
        return item


def validate_idea_evidence(con, project_id, evidence_ids):
    for evidence_id in evidence_ids:
        if not con.execute("SELECT 1 FROM evidence e JOIN project_papers pp ON pp.paper_id=e.paper_id JOIN papers p ON p.id=e.paper_id WHERE e.id=? AND pp.project_id=? AND p.deleted_at IS NULL AND e.id NOT IN (SELECT evidence_id FROM evidence_trash)", (evidence_id, project_id)).fetchone():
            raise HTTPException(422, "프로젝트에 속하지 않은 근거입니다.")


@app.patch("/api/ideas/{idea_id}")
def update_idea(idea_id: str, payload: IdeaUpdate):
    fields = payload.model_fields_set
    if not fields or any(getattr(payload, field) is None for field in fields):
        raise HTTPException(422, "수정할 값을 입력해 주세요.")
    if "title" in fields and not payload.title.strip():
        raise HTTPException(422, "제목을 입력해 주세요.")
    if "status" in fields and payload.status not in {"draft", "exploring", "paused", "completed"}:
        raise HTTPException(422, "아이디어 상태가 올바르지 않습니다.")
    with storage.transaction() as con:
        old = con.execute("SELECT * FROM ideas WHERE id=?", (idea_id,)).fetchone()
        if not old:
            raise HTTPException(404, "아이디어를 찾을 수 없습니다.")
        evidence_ids = list(dict.fromkeys(payload.evidence_ids)) if "evidence_ids" in fields else None
        if evidence_ids is not None:
            validate_idea_evidence(con, old["project_id"], evidence_ids)
        for field in ("title", "description", "status"):
            if field in fields:
                value = payload.title.strip() if field == "title" else getattr(payload, field)
                con.execute("UPDATE ideas SET " + field + "=? WHERE id=?", (value, idea_id))
        if evidence_ids is not None:
            con.execute("DELETE FROM idea_evidence WHERE idea_id=?", (idea_id,))
            con.executemany("INSERT INTO idea_evidence(idea_id,evidence_id) VALUES(?,?)", [(idea_id, eid) for eid in evidence_ids])
        item = rowdict(con.execute("SELECT * FROM ideas WHERE id=?", (idea_id,)).fetchone())
        item["evidence_ids"] = [r[0] for r in con.execute("SELECT evidence_id FROM idea_evidence WHERE idea_id=? ORDER BY evidence_id", (idea_id,))]
        return item


@app.delete("/api/ideas/{idea_id}", status_code=204)
def delete_idea(idea_id: str):
    with storage.transaction() as con:
        if not con.execute("DELETE FROM ideas WHERE id=?", (idea_id,)).rowcount:
            raise HTTPException(404, "아이디어를 찾을 수 없습니다.")
    return Response(status_code=204)


def analysis_inputs(paper_ids):
    if len(set(paper_ids)) != len(paper_ids):
        raise HTTPException(422, "같은 논문이 중복 선택되었습니다.")
    with storage.transaction() as con:
        papers, evidence = [], []
        for paper_id in paper_ids:
            p = require_paper(con, paper_id)
            papers.append({"id": p["id"], "title": p["title"]})
            if p["file_id"]:
                file_row = con.execute("SELECT * FROM files WHERE id=?", (p["file_id"],)).fetchone()
                path = storage.file_path(file_row["storage_key"])
                if not path.is_file() or path.stat().st_size != file_row["size"] or sha256_file(path) != file_row["sha256"]:
                    raise HTTPException(409, "분석할 원문 PDF가 없거나 손상되었습니다. 백업을 확인해 주세요.")
            rows = con.execute("SELECT e.*,p.text AS page_text FROM evidence e LEFT JOIN pages p ON p.paper_id=e.paper_id AND p.page_index=e.page_index WHERE e.paper_id=? AND e.id NOT IN (SELECT evidence_id FROM evidence_trash) ORDER BY e.created_at,e.id", (paper_id,))
            for row in rows:
                # Only quotes found uniquely in the saved extraction are sent to
                # an analysis. This establishes presence, not semantic support.
                if row["quote"].strip() and row["page_text"]:
                    match = locate_quote(row["page_text"], row["quote"], row["prefix"], row["suffix"])
                    if match["status"] == "candidate" and all(c["context_match"] for c in match["candidates"]):
                        evidence.append({"id": row["id"], "paper_id": paper_id, "page_index": row["page_index"], "quote": row["quote"], "verification": "native_text_match"})
                        continue
                if row["quote"].strip() and row["source"] == "user_verified_ocr":
                    ocr = con.execute("""SELECT o.text FROM evidence_ocr_source s
                        JOIN ocr_pages o ON o.job_id=s.job_id
                        WHERE s.evidence_id=? AND o.paper_id=? AND o.page_index=?""",
                        (row["id"], paper_id, row["page_index"])).fetchone()
                    if ocr and ocr["text"]:
                        match = locate_quote(ocr["text"], row["quote"], row["prefix"], row["suffix"])
                        if match["status"] == "candidate" and all(c["context_match"] for c in match["candidates"]):
                            evidence.append({"id": row["id"], "paper_id": paper_id, "page_index": row["page_index"], "quote": row["quote"], "verification": "user_verified_ocr"})
        return papers, evidence


def prepare_analysis(payload):
    _, evidence = analysis_inputs(payload.paper_ids)
    explicit = payload.evidence_ids is not None
    if explicit:
        if len(set(payload.evidence_ids)) != len(payload.evidence_ids):
            raise HTTPException(422, "같은 근거가 중복 선택되었습니다.")
        by_id = {item["id"]: item for item in evidence}
        if any(item not in by_id for item in payload.evidence_ids):
            raise HTTPException(422, "선택한 근거가 없거나 원문에서 구절을 확인할 수 없습니다.")
        evidence = [by_id[item] for item in payload.evidence_ids]
    try:
        preview = analysis_engine.prepare_external_input(payload.question, evidence, include_selected=explicit)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    envelope = {"provider": payload.provider, "model": payload.model, **preview}
    digest = hashlib.sha256(json.dumps(envelope, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return evidence, preview, digest, explicit


@app.post("/api/analyses/preview")
def preview_analysis(payload: AnalysisRequest):
    _, preview, digest, _ = prepare_analysis(payload)
    return {"provider": payload.provider, "external_send": payload.provider == "openai", "preview_hash": digest, **preview}


@app.post("/api/analyses")
def analyze(payload: AnalysisRequest):
    evidence, _, digest, explicit = prepare_analysis(payload)
    if payload.provider == "openai" and (not payload.preview_hash or payload.preview_hash != digest):
        raise HTTPException(409, "전송할 내용이 미리보기와 다릅니다. 다시 확인해 주세요.")
    try:
        result = analysis_engine.analyze(payload.question, evidence, provider=payload.provider,
                    api_key=os.environ.get("OPENAI_API_KEY"), model=payload.model, allow_external=payload.allow_external, include_selected=explicit)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except analysis_engine.AnalysisError as exc:
        raise HTTPException(502 if exc.status is None or exc.status >= 500 else exc.status, {"code": exc.code, "message": exc.message}) from exc
    analysis_id = storage.new_id()
    with storage.transaction() as con:
        con.execute("INSERT INTO analyses(id,question,output,evidence_json,provider,model) VALUES(?,?,?,?,?,?)", (analysis_id, payload.question, json.dumps(result, ensure_ascii=False), json.dumps([e["id"] for e in result.get("excerpts", [])]), result["provider"], payload.model))
    result["id"] = analysis_id
    return result


@app.get("/api/analyses")
def list_analyses():
    with storage.transaction() as con:
        rows = con.execute("SELECT * FROM analyses ORDER BY created_at DESC,id LIMIT 100").fetchall()
    return [{"id": r["id"], "question": r["question"], "result": json.loads(r["output"]), "created_at": r["created_at"]} for r in rows]


@app.post("/api/comparisons")
def compare(payload: ComparisonRequest):
    papers, evidence = analysis_inputs(payload.paper_ids)
    try:
        return analysis_engine.compare_papers(papers, evidence, payload.question)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.get("/api/experiments")
def list_experiments(project_id: str):
    with storage.transaction() as con:
        require_project(con, project_id)
        rows = con.execute("SELECT * FROM experiments WHERE project_id=? ORDER BY created_at DESC,id", (project_id,)).fetchall()
    return [{"id": r["id"], "project_id": r["project_id"], "title": r["title"], "status": r["status"], "config": json.loads(r["config_json"]), "result": json.loads(r["result_json"]) if r["result_json"] else None, "created_at": r["created_at"]} for r in rows]


@app.post("/api/experiments", status_code=201)
def run_experiment(payload: ExperimentRequest):
    with storage.transaction() as con:
        require_project(con, payload.project_id)
    try:
        result = experiment_runner.run_baseline(payload.values, seed=payload.seed)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    experiment_id = storage.new_id()
    config = {"kind": "fixed_baseline", "values": payload.values, "seed": payload.seed}
    with storage.transaction() as con:
        con.execute("INSERT INTO experiments(id,project_id,title,status,config_json,result_json) VALUES(?,?,?,?,?,?)", (experiment_id, payload.project_id, payload.title.strip(), result["status"], json.dumps(config), json.dumps(result)))
    return {"id": experiment_id, "project_id": payload.project_id, "title": payload.title, "status": result["status"], "config": config, "result": result}


@app.post("/api/experiments/codex-proposal")
def codex_proposal(payload: CodexProposalRequest):
    with storage.transaction() as con:
        require_project(con, payload.project_id)
    result = experiment_runner.request_codex_proposal(payload.prompt, user_requested=payload.user_requested, provider=experiment_runner.codex_cli_proposal)
    if result["status"] == "proposed":
        proposal_id = storage.new_id()
        with storage.transaction() as con:
            con.execute("INSERT INTO experiments(id,project_id,title,status,config_json,result_json) VALUES(?,?,?,?,?,?)", (proposal_id, payload.project_id, "Codex 실험 제안", "proposed", json.dumps({"kind":"codex_proposal", "prompt":payload.prompt}, ensure_ascii=False), json.dumps(result, ensure_ascii=False)))
        result["id"] = proposal_id
    return result


@app.post("/api/experiments/isolated", status_code=201)
def isolated_experiment(payload: IsolatedExperimentRequest):
    with storage.transaction() as con:
        require_project(con, payload.project_id)
    try:
        result = experiment_runner.run_container(payload.code, payload.values, payload.image_digest, seed=payload.seed)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    experiment_id = storage.new_id()
    config = {"kind": "isolated_code", "values": payload.values, "seed": payload.seed, "image_digest": payload.image_digest, "code": payload.code}
    with storage.transaction() as con:
        con.execute("INSERT INTO experiments(id,project_id,title,status,config_json,result_json) VALUES(?,?,?,?,?,?)", (experiment_id, payload.project_id, payload.title.strip(), result["status"], json.dumps(config), json.dumps(result)))
    return {"id": experiment_id, "project_id": payload.project_id, "title": payload.title, "status": result["status"], "config": config, "result": result}


@app.get("/api/projects/{project_id}/export")
def export_project(project_id: str, format: str = "json"):
    if format not in {"json", "markdown", "bibtex"}:
        raise HTTPException(422, "지원하지 않는 내보내기 형식입니다.")
    with storage.transaction() as con:
        require_project(con, project_id)
        project = rowdict(con.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone())
        rows = con.execute("SELECT p.*,pp.reading_status,pp.last_page FROM papers p JOIN project_papers pp ON p.id=pp.paper_id WHERE pp.project_id=? AND p.deleted_at IS NULL ORDER BY p.title", (project_id,)).fetchall()
        papers = []
        for row in rows:
            item = paper_dict(row)
            item["evidence"] = [evidence_records.evidence_item(con, e) for e in con.execute("SELECT * FROM evidence WHERE paper_id=? AND id NOT IN (SELECT evidence_id FROM evidence_trash) ORDER BY page_index,id", (item["id"],))]
            note = con.execute("SELECT note FROM project_paper_notes WHERE project_id=? AND paper_id=?", (project_id, item["id"])).fetchone()
            item["project_note"] = note["note"] if note else ""
            papers.append(item)
        ideas = [dict(r) for r in con.execute("SELECT * FROM ideas WHERE project_id=? ORDER BY created_at,id", (project_id,))]
        for idea in ideas:
            idea["evidence_ids"] = [r[0] for r in con.execute("SELECT evidence_id FROM idea_evidence WHERE idea_id=?", (idea["id"],))]
    if format == "json":
        body = json.dumps({"schema_version": 1, "project": project, "papers": papers, "ideas": ideas}, ensure_ascii=False, indent=2)
        mime, filename = "application/json", "easyresearch.json"
    elif format == "markdown":
        lines = ["# " + project["name"], "", project["description"], "", "## 논문", ""]
        for p in papers:
            lines.extend(["### " + p["title"], "", "- 저자: " + ", ".join(p["authors"]), "- DOI: " + (p["doi"] or "미입력"), "- 읽기 상태: " + p["reading_status"], ""])
            if p["project_note"]:
                lines.extend(["프로젝트 메모: " + p["project_note"], ""])
            for e in p["evidence"]:
                lines.extend(["- 파일 {}쪽 · {}".format(e["page_index"] + 1, e["status"]), "  - 발췌: " + e["quote"].replace("\n", " "), "  - 메모: " + e["note"].replace("\n", " ")])
            lines.append("")
        lines.extend(["## 아이디어", ""])
        for idea in ideas:
            lines.extend(["### " + idea["title"], "", idea["description"], "", "근거 ID: " + ", ".join(idea["evidence_ids"]), ""])
        body, mime, filename = "\n".join(lines), "text/markdown", "easyresearch.md"
    else:
        def escape(value):
            value = " ".join(str(value or "").split())
            for char in ("\\", "{", "}", "%", "&", "#", "_"):
                value = value.replace(char, "\\" + char)
            return value
        entries = []
        keys = integrations.assign_citekeys(papers)
        for p in papers:
            fields = [("title", p["title"]), ("author", " and ".join(p["authors"])), ("year", p["year"]), ("doi", p["doi"]), ("url", p["source_url"])]
            entries.append("@misc{" + keys[p["id"]] + ",\n" + ",\n".join("  " + k + " = {" + escape(v) + "}" for k, v in fields if v) + "\n}")
        body, mime, filename = "\n\n".join(entries), "application/x-bibtex", "easyresearch.bib"
    return Response(content=body, media_type=mime, headers={"Content-Disposition": 'attachment; filename="' + filename + '"'})


@app.get("/api/projects/{project_id}/context")
def agent_context(project_id: str):
    """Structured local context for tools and agents, without PDF bytes or keys."""
    data = json.loads(export_project(project_id, "json").body.decode("utf-8"))
    return {"schema_version": 1, "project": data["project"],
            "papers": [{"id": p["id"], "title": p["title"], "doi": p["doi"], "reading_status": p["reading_status"], "evidence": p["evidence"]} for p in data["papers"]],
            "ideas": data["ideas"], "note": "발췌 일치와 의미 지지 여부는 별도 확인이 필요합니다."}


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _backup_io_failure(exc: OSError):
    if exc.errno in {errno.ENOSPC, getattr(errno, "EDQUOT", -1)} or getattr(exc, "winerror", None) == 112:
        return HTTPException(507, "저장 공간이 부족합니다. 공간을 확보한 뒤 다시 시도하세요. 기존 보관함은 유지됩니다.")
    return HTTPException(500, "백업 파일을 읽거나 저장하지 못했습니다. 저장 위치와 접근 권한을 확인하세요. 기존 보관함은 유지됩니다.")


def _sqlite_storage_full(exc: sqlite3.Error) -> bool:
    code = getattr(exc, "sqlite_errorcode", None)
    return (isinstance(code, int) and (code & 255) == sqlite3.SQLITE_FULL) or "database or disk is full" in str(exc).lower()


def _backup_sqlite_failure(exc: sqlite3.Error):
    if _sqlite_storage_full(exc):
        return HTTPException(507, "저장 공간이 부족합니다. 공간을 확보한 뒤 다시 시도하세요. 기존 보관함은 유지됩니다.")
    return HTTPException(500, "백업 데이터베이스를 읽거나 저장하지 못했습니다. 기존 보관함은 유지됩니다.")


def _create_backup():
    root = storage.data_dir()
    backup_id = storage.new_id()
    backup_dir = root / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    (root / "tmp").mkdir(parents=True, exist_ok=True)
    output = backup_dir / (backup_id + ".zip")
    with tempfile.TemporaryDirectory(prefix="backup-", dir=str(root / "tmp")) as temporary:
        snapshot = Path(temporary) / "library.sqlite3"
        storage.backup_database(snapshot)
        con = sqlite3.connect(str(snapshot))
        try:
            try:
                # A successful archive must be accepted by the same strict
                # schema validator used by inspection and restoration.
                storage.validate_schema_connection(con)
            except RuntimeError as exc:
                raise HTTPException(409, "현재 보관함의 데이터 구조를 백업 복원 형식으로 확인할 수 없습니다. 기존 자료는 변경되지 않았습니다.") from exc
            files = con.execute("SELECT storage_key,sha256,size FROM files").fetchall()
        finally:
            con.close()
        if len(files) > 10000 or snapshot.stat().st_size + sum(item[2] for item in files) > 2 * 1024 * 1024 * 1024 - 5 * 1024 * 1024:
            raise HTTPException(413, "라이브러리가 현재 백업·복원 한도를 초과했습니다.")
        manifest = {"format": 1, "database_sha256": sha256_file(snapshot), "files": []}
        tmp_zip = Path(temporary) / "archive.zip"
        with zipfile.ZipFile(str(tmp_zip), "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as z:
            z.write(snapshot, "library.sqlite3")
            for key, sha, size in files:
                path = storage.file_path(key)
                if not path.is_file() or sha256_file(path) != sha:
                    raise HTTPException(409, "백업할 PDF가 없거나 내용이 변경되었습니다.")
                z.write(path, key)
                manifest["files"].append({"path": key, "sha256": sha, "size": size})
            manifest_json = json.dumps(manifest, ensure_ascii=False, indent=2)
            if len(manifest_json.encode("utf-8")) > 5 * 1024 * 1024:
                raise HTTPException(413, "백업 목록이 복원 한도를 초과했습니다.")
            z.writestr("manifest.json", manifest_json)
        if tmp_zip.stat().st_size > 1024 * 1024 * 1024:
            raise HTTPException(413, "백업 파일이 현재 복원 한도를 초과했습니다.")
        # Test archive integrity before moving it into its final location.
        with zipfile.ZipFile(str(tmp_zip)) as z:
            if z.testzip() is not None:
                raise HTTPException(500, "백업 파일 검증에 실패했습니다.")
            for item in manifest["files"]:
                archive_hash = hashlib.sha256()
                archive_size = 0
                with z.open(item["path"]) as source:
                    for chunk in iter(lambda: source.read(1024 * 1024), b""):
                        archive_hash.update(chunk)
                        archive_size += len(chunk)
                if archive_hash.hexdigest() != item["sha256"] or archive_size != item["size"]:
                    raise HTTPException(409, "백업 중 PDF가 변경되어 백업을 중단했습니다.")
        os.replace(tmp_zip, output)
    return {"id": backup_id, "status": "completed", "file_count": len(manifest["files"]), "download_url": "/api/backups/" + backup_id + "/download"}


@app.post("/api/backups", status_code=201)
def create_backup():
    try:
        return _create_backup()
    except OSError as exc:
        raise _backup_io_failure(exc) from exc
    except sqlite3.Error as exc:
        raise _backup_sqlite_failure(exc) from exc


@app.get("/api/backups/{backup_id}/download")
def download_backup(backup_id: str):
    try:
        import uuid
        if str(uuid.UUID(backup_id)) != backup_id:
            raise ValueError()
    except ValueError:
        raise HTTPException(404, "백업을 찾을 수 없습니다.")
    path = storage.data_dir() / "backups" / (backup_id + ".zip")
    if not path.is_file():
        raise HTTPException(404, "백업을 찾을 수 없습니다.")
    return FileResponse(path, media_type="application/zip", filename="easyresearch-backup.zip")


def _inspect_or_restore_backup(file: UploadFile, restore: bool):
    """Fully validate a temporary copy; optionally publish a separate restored library."""
    import re
    root = storage.data_dir()
    tmp = root / "tmp"
    restores = root / "restores"
    tmp.mkdir(parents=True, exist_ok=True)
    restore_id = storage.new_id()
    destination = restores / restore_id
    pattern = re.compile(r"^files/([0-9a-f]{2})/([0-9a-f]{64})\.pdf$")
    try:
        with tempfile.TemporaryDirectory(prefix="restore-", dir=str(tmp)) as folder:
            stage = Path(folder)
            archive = stage / "upload.zip"
            total = 0
            with archive.open("wb") as out:
                while True:
                    chunk = file.file.read(1024 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > 1024 * 1024 * 1024:
                        raise HTTPException(413, "백업 파일이 너무 큽니다.")
                    out.write(chunk)
            restored = stage / "library"
            restored.mkdir()
            try:
                with zipfile.ZipFile(str(archive)) as z:
                    entries = z.namelist()
                    if len(entries) != len(set(entries)) or len(entries) > 10002:
                        raise ValueError("백업에 중복 항목이 있거나 파일 수가 제한을 초과했습니다.")
                    if sum(info.file_size for info in z.infolist()) > 2 * 1024 * 1024 * 1024:
                        raise ValueError("압축을 푼 백업의 크기가 제한을 초과했습니다.")
                    if z.getinfo("manifest.json").file_size > 5 * 1024 * 1024:
                        raise ValueError("백업 목록의 크기가 제한을 초과했습니다.")
                    manifest = json.loads(z.read("manifest.json"))
                    if not isinstance(manifest, dict) or manifest.get("format") != 1 or not isinstance(manifest.get("files"), list):
                        raise ValueError("지원하지 않는 백업 형식입니다.")
                    db = restored / "library.sqlite3"
                    with z.open("library.sqlite3") as source, db.open("wb") as output:
                        shutil.copyfileobj(source, output, 1024 * 1024)
                    if sha256_file(db) != manifest.get("database_sha256"):
                        raise ValueError("백업의 데이터베이스가 손상되었거나 변경되었습니다.")
                    seen = set()
                    for item in manifest["files"]:
                        key, expected = item["path"], item["sha256"]
                        match = pattern.fullmatch(key)
                        if not match or match.group(1) != match.group(2)[:2] or match.group(2) != expected or key in seen:
                            raise ValueError("백업에 올바르지 않거나 중복된 파일 경로가 있습니다.")
                        seen.add(key)
                        path = restored / key
                        path.parent.mkdir(parents=True, exist_ok=True)
                        with z.open(key) as source, path.open("wb") as output:
                            shutil.copyfileobj(source, output, 1024 * 1024)
                        if path.stat().st_size != item["size"] or sha256_file(path) != expected:
                            raise ValueError("백업에 포함된 PDF가 손상되었거나 변경되었습니다.")
                    if set(entries) != seen | {"manifest.json", "library.sqlite3"}:
                        raise ValueError("백업에 목록에 없는 파일이 포함되어 있습니다.")
                connection = sqlite3.connect(db.resolve().as_uri() + "?mode=ro", uri=True)
                try:
                    try:
                        version_info = storage.validate_schema_connection(connection, allow_unversioned=True)
                    except RuntimeError as exc:
                        raise ValueError("백업의 데이터베이스를 사용할 수 없습니다: " + str(exc)) from exc
                    refs = {(r[0], r[1], r[2]) for r in connection.execute("SELECT storage_key,sha256,size FROM files")}
                    listed = {(x["path"], x["sha256"], x["size"]) for x in manifest["files"]}
                    if refs != listed:
                        raise ValueError("백업 목록과 데이터베이스의 PDF 목록이 일치하지 않습니다.")
                    summary = {"status": "verified", "format": manifest["format"],
                               "database_version": version_info["source_version"],
                               "target_database_version": version_info["target_version"],
                               "requires_migration": version_info["requires_migration"],
                               "file_count": len(manifest["files"]),
                               "total_file_bytes": sum(item["size"] for item in manifest["files"]),
                               "project_count": connection.execute("SELECT count(*) FROM projects").fetchone()[0],
                               "paper_count": connection.execute("SELECT count(*) FROM papers").fetchone()[0],
                               "evidence_count": connection.execute("SELECT count(*) FROM evidence").fetchone()[0]}
                finally:
                    connection.close()
                if version_info["requires_migration"]:
                    # The upload and extracted original are immutable; test an
                    # isolated migrated copy even for a preview.
                    migrated = stage / "migrated.sqlite3"
                    try:
                        storage.migrate_database_copy(db, migrated)
                    except RuntimeError as exc:
                        raise ValueError("백업의 데이터베이스 이관에 실패했습니다.") from exc
                    os.replace(migrated, db)
            except KeyError as exc:
                raise HTTPException(400, "백업에 필요한 파일 또는 목록 정보가 없습니다.") from exc
            except ValueError as exc:
                message = str(exc) if str(exc).startswith(("백업", "압축", "지원")) else "백업 형식 또는 파일 무결성을 확인할 수 없습니다."
                raise HTTPException(400, message) from exc
            except sqlite3.Error as exc:
                if _sqlite_storage_full(exc):
                    raise _backup_sqlite_failure(exc) from exc
                raise HTTPException(400, "백업을 읽을 수 없거나 손상되었습니다.") from exc
            except (TypeError, zipfile.BadZipFile, RuntimeError, NotImplementedError) as exc:
                raise HTTPException(400, "백업을 읽을 수 없거나 손상되었습니다.") from exc
            if restore:
                restores.mkdir(parents=True, exist_ok=True)
                # UUID destinations must not replace any existing library.
                try:
                    destination.mkdir()
                except FileExistsError as exc:
                    raise HTTPException(409, "복원 대상이 이미 존재하여 기존 보관함을 보호했습니다.") from exc
                try:
                    # The directory is published incrementally on Windows.
                    # Keep an interruption marker until every verified file is
                    # in place, so an interrupted restore cannot be offered as
                    # an available library on the next launch.
                    marker = destination / ".incomplete"
                    with marker.open("xb") as pending:
                        pending.write(b"incomplete restore\n")
                        pending.flush()
                        os.fsync(pending.fileno())
                    for child in restored.iterdir():
                        os.rename(child, destination / child.name)
                    marker.unlink()
                except OSError:
                    if destination.resolve().parent == restores.resolve() and not destination.is_symlink():
                        shutil.rmtree(destination, ignore_errors=True)
                    raise
    except OSError as exc:
        raise _backup_io_failure(exc) from exc
    finally:
        file.file.close()
    if restore:
        summary.update({"id": restore_id, "restore_path": str(destination),
                        "message": "별도 폴더에 복원했습니다. 기존 라이브러리는 변경되지 않았습니다."})
    return summary


@app.post("/api/backups/inspect")
def inspect_backup(file: UploadFile = File(...)):
    """Validate the entire upload without creating a permanent restored library."""
    return _inspect_or_restore_backup(file, False)


@app.post("/api/backups/restore", status_code=201)
def restore_backup(file: UploadFile = File(...)):
    """Validate an uploaded archive and restore it into a separate library."""
    return _inspect_or_restore_backup(file, True)


if WEB.exists():
    app.mount("/assets", StaticFiles(directory=str(WEB)), name="assets")


@app.get("/", include_in_schema=False)
def index():
    page = WEB / "index.html"
    if not page.exists():
        raise HTTPException(503, "화면이 아직 준비되지 않았습니다.")
    return FileResponse(page)
