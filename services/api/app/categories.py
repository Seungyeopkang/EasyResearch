"""Editable research categories, rule-based suggestions, and OpenAlex topics.

Rules: a keyword matches when it appears as a whole word (ASCII keywords are
bounded by non-word characters, so "pruning" does not match "pruned"). Keywords
containing Hangul are matched as plain substrings, because Korean particles
attach directly to nouns. Suggestions are stored as status 'suggested'; a
user's 'confirmed' or 'rejected' decision is never changed by classification.
"""
import json
import os
import re
import sqlite3
from typing import List, Optional
from urllib.parse import quote, urlencode

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from . import scholarly, storage

router = APIRouter()

CLASSIFY_PAGE_LIMIT = 3
MAX_MATCHED = 10
MAX_KEYWORDS = 50
MAX_TOPICS = 5
MAX_KEYWORD_TAGS = 20
HANGUL = re.compile(r"[ᄀ-ᇿ㄰-㆏가-힯]")


class CategoryCreate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=500)
    keywords: List[str] = Field(default_factory=list, max_length=MAX_KEYWORDS)


class CategoryUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=500)
    keywords: Optional[List[str]] = Field(default=None, max_length=MAX_KEYWORDS)


class CategoryDecision(BaseModel):
    status: str = Field(pattern="^(confirmed|rejected)$")


def _clean_name(value) -> str:
    name = (value or "").strip() if isinstance(value, str) else ""
    if not 1 <= len(name) <= 60:
        raise HTTPException(422, "분야 이름은 1~60자로 입력해 주세요.")
    return name


def _clean_keywords(values) -> List[str]:
    cleaned: List[str] = []
    seen = set()
    for raw in values:
        if not isinstance(raw, str):
            raise HTTPException(422, "키워드는 문자열이어야 합니다.")
        keyword = " ".join(raw.split())
        if not 1 <= len(keyword) <= 80:
            raise HTTPException(422, "키워드는 1~80자로 입력해 주세요.")
        if keyword.lower() in seen:
            continue
        seen.add(keyword.lower())
        cleaned.append(keyword)
    return cleaned


def _paper_or_404(con, paper_id: str):
    row = con.execute("SELECT * FROM papers WHERE id=? AND deleted_at IS NULL", (paper_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "논문을 찾을 수 없습니다.")
    return row


def _category_or_404(con, category_id: str):
    row = con.execute("SELECT * FROM categories WHERE id=?", (category_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "분야를 찾을 수 없습니다.")
    return row


def _name_taken(con, name: str, exclude_id: Optional[str] = None) -> bool:
    for row in con.execute("SELECT id,name FROM categories"):
        if row["id"] != exclude_id and row["name"].casefold() == name.casefold():
            return True
    return False


def _category_out(con, row) -> dict:
    counts = con.execute("""SELECT
            COALESCE(SUM(CASE WHEN pc.status='suggested' THEN 1 ELSE 0 END),0) AS suggested_count,
            COALESCE(SUM(CASE WHEN pc.status='confirmed' THEN 1 ELSE 0 END),0) AS confirmed_count
        FROM paper_categories pc JOIN papers p ON p.id=pc.paper_id AND p.deleted_at IS NULL
        WHERE pc.category_id=?""", (row["id"],)).fetchone()
    return {"id": row["id"], "name": row["name"], "keywords": json.loads(row["keywords_json"] or "[]"),
            "suggested_count": counts["suggested_count"], "confirmed_count": counts["confirmed_count"]}


def paper_categories(con, paper_id: str) -> list:
    """All stored category rows for a paper, including rejected ones."""
    return [{"id": r["id"], "name": r["name"], "status": r["status"], "source": r["source"],
             "matched": json.loads(r["matched_json"] or "[]")}
            for r in con.execute("""SELECT c.id,c.name,pc.status,pc.source,pc.matched_json FROM paper_categories pc
                JOIN categories c ON c.id=pc.category_id WHERE pc.paper_id=? ORDER BY c.name,c.id""", (paper_id,))]


SUFFIXES = ("ization", "isation", "ation", "ing", "ion", "ed", "er", "s")
STEM_FORMS = ("e", "es", "ed", "ing", "ion", "ions", "ation", "ations", "ization", "ize", "ized", "izes", "er", "ers", "s")


def _keyword_pattern(keyword: str) -> str:
    """Regex body for one lowercase keyword; boundaries are added by the caller.

    Single ASCII words also match conservative inflections: a stem of at least
    4 letters is combined with STEM_FORMS (e.g. pruning -> prune, pruned).
    Words without a long-enough suffix match only plural forms (image -> images).
    Phrases match only a plural on the final word (knowledge distillation -> ...s).
    Bare prefixes never match, so "text" does not match "texture".
    """
    if re.fullmatch(r"[a-z0-9]+", keyword):
        for suffix in SUFFIXES:
            if keyword.endswith(suffix) and len(keyword) - len(suffix) >= 4:
                stem = keyword[:-len(suffix)]
                forms = set(STEM_FORMS) | {suffix}
                alternatives = "|".join(sorted(forms, key=len, reverse=True))
                return re.escape(stem) + "(?:" + alternatives + ")?"
        return re.escape(keyword) + "(?:s|es)?"
    return re.escape(keyword) + "(?:s|es)?"


def _keyword_matches(keyword: str, text: str) -> bool:
    """keyword is lowercase; text is lowercase and whitespace-normalized."""
    if HANGUL.search(keyword):
        return keyword in text
    return re.search(r"(?<!\w)" + _keyword_pattern(keyword) + r"(?!\w)", text) is not None


def _classification_text(con, paper, paper_id: str) -> str:
    parts = [paper["title"] or "", paper["abstract"] or ""]
    # Topic names, subfields and fields; stored OpenAlex keywords are included too.
    for r in con.execute("SELECT name,subfield,field FROM paper_topics WHERE paper_id=?", (paper_id,)):
        parts.extend(value for value in (r["name"], r["subfield"], r["field"]) if value)
    for r in con.execute("SELECT text FROM pages WHERE paper_id=? AND page_index<? ORDER BY page_index",
                         (paper_id, CLASSIFY_PAGE_LIMIT)):
        parts.append(r["text"] or "")
    return " ".join(" ".join(parts).lower().split())


def classify_paper(con, paper_id: str) -> list:
    """Rule-classify one paper and return its stored category rows.

    Called by reading_library.on_paper_read with the caller's connection, so it
    must not commit. Rows decided by the user are never modified.
    """
    paper = con.execute("SELECT * FROM papers WHERE id=?", (paper_id,)).fetchone()
    if paper is None:
        return []
    text = _classification_text(con, paper, paper_id)
    matches = {}
    for category in con.execute("SELECT id,keywords_json FROM categories"):
        keywords = json.loads(category["keywords_json"] or "[]")
        hit = sorted({kw for kw in keywords if isinstance(kw, str) and kw.strip()
                      and _keyword_matches(kw.strip().lower(), text)})
        if hit:
            matches[category["id"]] = hit[:MAX_MATCHED]
    stale = [r["category_id"] for r in con.execute(
        "SELECT category_id FROM paper_categories WHERE paper_id=? AND source='rule' AND status='suggested'", (paper_id,))]
    for category_id in stale:
        if category_id not in matches:
            con.execute("DELETE FROM paper_categories WHERE paper_id=? AND category_id=? AND source='rule' AND status='suggested'",
                        (paper_id, category_id))
    for category_id, hit in matches.items():
        con.execute("""INSERT INTO paper_categories(paper_id,category_id,source,status,matched_json,updated_at)
                VALUES(?,?,'rule','suggested',?,CURRENT_TIMESTAMP)
            ON CONFLICT(paper_id,category_id) DO UPDATE SET source='rule', status='suggested',
                matched_json=excluded.matched_json, updated_at=CURRENT_TIMESTAMP
            WHERE paper_categories.status NOT IN ('confirmed','rejected')""",
                    (paper_id, category_id, json.dumps(hit, ensure_ascii=False)))
    return paper_categories(con, paper_id)


@router.get("/api/categories")
def list_categories():
    with storage.transaction() as con:
        return [_category_out(con, row) for row in con.execute("SELECT * FROM categories ORDER BY name COLLATE NOCASE, id")]


@router.post("/api/categories", status_code=201)
def create_category(payload: CategoryCreate):
    name = _clean_name(payload.name)
    keywords = _clean_keywords(payload.keywords)
    with storage.transaction() as con:
        if _name_taken(con, name):
            raise HTTPException(409, "같은 이름의 분야가 이미 있습니다.")
        category_id = storage.new_id()
        try:
            con.execute("INSERT INTO categories(id,name,keywords_json) VALUES(?,?,?)",
                        (category_id, name, json.dumps(keywords, ensure_ascii=False)))
        except sqlite3.IntegrityError as exc:
            raise HTTPException(409, "같은 이름의 분야가 이미 있습니다.") from exc
        return _category_out(con, _category_or_404(con, category_id))


@router.patch("/api/categories/{category_id}")
def update_category(category_id: str, payload: CategoryUpdate):
    fields = payload.model_fields_set
    with storage.transaction() as con:
        _category_or_404(con, category_id)
        if "name" in fields:
            name = _clean_name(payload.name)
            if _name_taken(con, name, exclude_id=category_id):
                raise HTTPException(409, "같은 이름의 분야가 이미 있습니다.")
            try:
                con.execute("UPDATE categories SET name=? WHERE id=?", (name, category_id))
            except sqlite3.IntegrityError as exc:
                raise HTTPException(409, "같은 이름의 분야가 이미 있습니다.") from exc
        if "keywords" in fields:
            if payload.keywords is None:
                raise HTTPException(422, "키워드 목록을 확인해 주세요.")
            keywords = _clean_keywords(payload.keywords)
            con.execute("UPDATE categories SET keywords_json=? WHERE id=?", (json.dumps(keywords, ensure_ascii=False), category_id))
        return _category_out(con, _category_or_404(con, category_id))


@router.delete("/api/categories/{category_id}", status_code=204)
def delete_category(category_id: str):
    with storage.transaction() as con:
        _category_or_404(con, category_id)
        con.execute("DELETE FROM paper_categories WHERE category_id=?", (category_id,))
        con.execute("DELETE FROM categories WHERE id=?", (category_id,))
    return Response(status_code=204)


@router.post("/api/papers/{paper_id}/classify")
def classify_one(paper_id: str):
    with storage.transaction() as con:
        _paper_or_404(con, paper_id)
        return classify_paper(con, paper_id)


@router.post("/api/library/classify")
def classify_all():
    with storage.transaction() as con:
        ids = [r["id"] for r in con.execute("SELECT id FROM papers WHERE deleted_at IS NULL ORDER BY id")]
        for paper_id in ids:
            classify_paper(con, paper_id)
        return {"classified": len(ids)}


@router.get("/api/papers/{paper_id}/categories")
def get_paper_categories(paper_id: str):
    with storage.transaction() as con:
        _paper_or_404(con, paper_id)
        return paper_categories(con, paper_id)


@router.put("/api/papers/{paper_id}/categories/{category_id}")
def set_category_decision(paper_id: str, category_id: str, payload: CategoryDecision):
    with storage.transaction() as con:
        _paper_or_404(con, paper_id)
        _category_or_404(con, category_id)
        # An existing row keeps its source and matched keywords; only the decision changes.
        con.execute("""INSERT INTO paper_categories(paper_id,category_id,source,status,matched_json,updated_at)
                VALUES(?,?,'manual',?,'[]',CURRENT_TIMESTAMP)
            ON CONFLICT(paper_id,category_id) DO UPDATE SET status=excluded.status, updated_at=CURRENT_TIMESTAMP""",
                    (paper_id, category_id, payload.status))
        return next(row for row in paper_categories(con, paper_id) if row["id"] == category_id)


@router.delete("/api/papers/{paper_id}/categories/{category_id}", status_code=204)
def clear_category_decision(paper_id: str, category_id: str):
    """Remove the stored row. A later classification may suggest the category again."""
    with storage.transaction() as con:
        _paper_or_404(con, paper_id)
        _category_or_404(con, category_id)
        con.execute("DELETE FROM paper_categories WHERE paper_id=? AND category_id=?", (paper_id, category_id))
    return Response(status_code=204)


# ---- OpenAlex topics -------------------------------------------------------

def _title_key(value) -> str:
    return " ".join(re.sub(r"[\W_]+", " ", (value or "").casefold()).split())


def _openalex_headers():
    key = os.environ.get("OPENALEX_API_KEY")
    return {"Authorization": "Bearer " + key} if key else None


def _openalex_error(exc: scholarly.ScholarlyError):
    if exc.code == "not_found":
        raise HTTPException(404, "OpenAlex에서 이 DOI의 논문을 찾지 못했습니다.") from exc
    if exc.code == "rate_limited":
        raise HTTPException(429, "OpenAlex 요청 한도에 도달했습니다. 잠시 후 다시 시도해 주세요.") from exc
    raise HTTPException(502, "OpenAlex에 연결하지 못했거나 응답을 확인할 수 없습니다.") from exc


def _fetch_openalex_work(doi, title) -> dict:
    """Network lookup only; the caller must not hold a database transaction."""
    headers = _openalex_headers()
    try:
        if doi:
            url = ("https://api.openalex.org/works/doi:" + quote(doi, safe="/") + "?"
                   + urlencode({"select": "id,topics,keywords,primary_topic"}))
            return scholarly._json("openalex", scholarly._get("openalex", url, headers))
        key = _title_key(title)
        not_found = HTTPException(404, "OpenAlex에서 같은 제목의 논문을 찾지 못했습니다.")
        if not key:
            raise not_found
        url = "https://api.openalex.org/works?" + urlencode({"search": title[:300], "per-page": 1,
                                                             "select": "id,display_name,topics,keywords"})
        payload = scholarly._json("openalex", scholarly._get("openalex", url, headers))
        results = payload.get("results")
        if not isinstance(results, list):
            raise scholarly.ScholarlyError("openalex", "invalid_response", "The service returned an invalid results list.")
        for record in results:
            if isinstance(record, dict) and _title_key(record.get("display_name") or record.get("title")) == key:
                return record
        raise not_found
    except scholarly.ScholarlyError as exc:
        _openalex_error(exc)


def _named(value):
    return value.get("display_name") if isinstance(value, dict) and isinstance(value.get("display_name"), str) else None


def _score(value):
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _extract_openalex(record: dict):
    topics = []
    raw_topics = record.get("topics")
    if isinstance(raw_topics, list):
        for item in raw_topics:
            if len(topics) >= MAX_TOPICS:
                break
            if isinstance(item, dict) and isinstance(item.get("id"), str) and _named(item):
                topics.append((item["id"][:300], _named(item)[:300], (_named(item.get("subfield")) or "")[:300] or None,
                               (_named(item.get("field")) or "")[:300] or None, _score(item.get("score"))))
    tags = []
    raw_keywords = record.get("keywords")
    if isinstance(raw_keywords, list):
        for item in raw_keywords:
            if len(tags) >= MAX_KEYWORD_TAGS:
                break
            if isinstance(item, dict) and isinstance(item.get("id"), str) and _named(item):
                tags.append((item["id"][:300], _named(item)[:300], None, None, _score(item.get("score"))))
    return topics, tags


@router.post("/api/papers/{paper_id}/topics/fetch")
def fetch_topics(paper_id: str):
    with storage.transaction() as con:
        paper = _paper_or_404(con, paper_id)
        doi, title = paper["doi"], paper["title"] or ""
    try:
        doi = scholarly.normalize_doi(doi) if doi else None
    except ValueError:
        doi = None
    record = _fetch_openalex_work(doi, title)
    topics, tags = _extract_openalex(record)
    with storage.transaction() as con:
        _paper_or_404(con, paper_id)
        con.execute("DELETE FROM paper_topics WHERE paper_id=? AND source IN ('openalex','openalex_keyword')", (paper_id,))
        for source, rows in (("openalex", topics), ("openalex_keyword", tags)):
            for topic_id, name, subfield, field, score in rows:
                con.execute("""INSERT OR IGNORE INTO paper_topics(paper_id,source,topic_id,name,subfield,field,score)
                    VALUES(?,?,?,?,?,?,?)""", (paper_id, source, topic_id, name, subfield, field, score))
        stored = [dict(r) for r in con.execute("""SELECT source,topic_id,name,subfield,field,score FROM paper_topics
            WHERE paper_id=? AND source IN ('openalex','openalex_keyword') ORDER BY source,score DESC,name""", (paper_id,))]
        return {"topics": stored, "categories": classify_paper(con, paper_id)}
