"""Project-independent reading library: list, filters, and linking to projects."""
import json
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from . import library_management, storage

router = APIRouter()

READING_STATUSES = {"to_read", "reading", "read", "on_hold"}
SORTS = {
    "recent": "(rs.last_opened_at IS NULL), rs.last_opened_at DESC, p.id",
    "added": "p.created_at DESC, p.id",
    "title": "p.title COLLATE NOCASE, p.id",
    "year": "(p.year IS NULL), p.year DESC, p.id",
}


def on_paper_read(con, paper_id: str) -> None:
    """Hook run when a paper's global reading status becomes 'read': rule classification."""
    from . import categories  # local import avoids a circular import at module load
    categories.classify_paper(con, paper_id)


def reading_state(con, paper_id: str) -> dict:
    """Global reading state; a paper without a stored row is treated as to_read / page 0."""
    row = con.execute("SELECT reading_status,last_page,last_opened_at FROM paper_reading_state WHERE paper_id=?",
                      (paper_id,)).fetchone()
    if row is None:
        return {"reading_status": "to_read", "last_page": 0, "last_opened_at": None}
    return {"reading_status": row["reading_status"], "last_page": row["last_page"], "last_opened_at": row["last_opened_at"]}


def _like_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _library_item(con, row) -> dict:
    item = dict(row)
    item["authors"] = json.loads(item.get("authors") or "[]")
    item["metadata"] = json.loads(item.pop("metadata_json", "{}") or "{}")
    paper_id = item["id"]
    item["projects"] = [dict(r) for r in con.execute(
        """SELECT pr.id,pr.name FROM project_papers pp JOIN projects pr ON pr.id=pp.project_id
           WHERE pp.paper_id=? AND pr.id NOT IN (SELECT project_id FROM project_trash) ORDER BY pr.name,pr.id""", (paper_id,))]
    categories = []
    for r in con.execute("""SELECT c.id,c.name,pc.status,pc.source,pc.matched_json FROM paper_categories pc
            JOIN categories c ON c.id=pc.category_id WHERE pc.paper_id=? AND pc.status IN ('suggested','confirmed')
            ORDER BY c.name,c.id""", (paper_id,)):
        categories.append({"id": r["id"], "name": r["name"], "status": r["status"], "source": r["source"],
                           "matched": json.loads(r["matched_json"] or "[]")})
    item["categories"] = categories
    return item


@router.get("/api/library/papers")
def list_library_papers(status: Optional[str] = None, category_id: Optional[str] = None,
                        q: Optional[str] = Query(default=None, max_length=200),
                        sort: str = "recent"):
    if status is not None and status not in READING_STATUSES:
        raise HTTPException(422, "읽기 상태가 올바르지 않습니다.")
    if sort not in SORTS:
        raise HTTPException(422, "정렬 기준이 올바르지 않습니다.")
    clauses = ["p.deleted_at IS NULL"]
    params = []
    if status is not None:
        clauses.append("COALESCE(rs.reading_status,'to_read')=?")
        params.append(status)
    if category_id:
        clauses.append("EXISTS (SELECT 1 FROM paper_categories pc WHERE pc.paper_id=p.id AND pc.category_id=? AND pc.status IN ('suggested','confirmed'))")
        params.append(category_id)
    needle = (q or "").strip().lower()
    if needle:
        pattern = "%" + _like_escape(needle) + "%"
        clauses.append("(lower(p.title) LIKE ? ESCAPE '\\' OR lower(p.authors) LIKE ? ESCAPE '\\' OR lower(COALESCE(p.doi,'')) LIKE ? ESCAPE '\\')")
        params.extend([pattern, pattern, pattern])
    sql = f"""SELECT p.*, COALESCE(rs.reading_status,'to_read') AS reading_status, COALESCE(rs.last_page,0) AS last_page,
            rs.last_opened_at AS last_opened_at
        FROM papers p LEFT JOIN paper_reading_state rs ON rs.paper_id=p.id
        WHERE {' AND '.join(clauses)} ORDER BY {SORTS[sort]}"""
    with storage.transaction() as con:
        rows = con.execute(sql, params).fetchall()
        return [_library_item(con, row) for row in rows]


@router.post("/api/projects/{project_id}/papers/{paper_id}/link", status_code=201)
def link_paper(project_id: str, paper_id: str):
    with storage.transaction() as con:
        con.execute("BEGIN IMMEDIATE")
        if not con.execute("SELECT 1 FROM projects WHERE id=? AND id NOT IN (SELECT project_id FROM project_trash)", (project_id,)).fetchone():
            raise HTTPException(404, "프로젝트를 찾을 수 없습니다.")
        if not con.execute("SELECT 1 FROM papers WHERE id=? AND deleted_at IS NULL", (paper_id,)).fetchone():
            raise HTTPException(404, "논문을 찾을 수 없습니다.")
        library_management.attach_paper(con, project_id, paper_id)
        return {"project_id": project_id, "paper_id": paper_id, "status": "linked"}
