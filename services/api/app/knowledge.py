"""Paper profiles, paper links and graph, research gaps, AI classification.

Contract: docs/exec-plans/active/004-research-assistant.md (Workstream W1).

All AI output is a draft: it stores origin, model and input hash, and quotes
are checked against the stored page text (match: exact / normalized /
not_found). Every outbound call goes through llm.preview first.
"""
import json
import re
import sqlite3
import unicodedata
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote, urlencode
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from . import categories, llm, scholarly, storage
from .ai_routes import run_llm

router = APIRouter()

FACETS = ["problem", "method", "contributions", "strengths", "limitations", "datasets", "metrics", "results", "future_work"]
MAX_ITEMS = 12
MAX_TEXT = 1000
MAX_QUOTE = 500
SUMMARY_MAX = 1000
MAX_KEYWORDS = 20
ITEM_ORIGINS = {"author_stated", "inferred"}
PROFILE_ORIGINS = {"rules", "llm", "agent", "manual"}
PROFILE_STATUSES = {"draft", "confirmed"}
RELATIONS = {"cites", "extends", "compares_against", "contradicts", "supports", "same_problem", "same_method",
             "uses_dataset", "related"}
# Relations whose direction carries no meaning are stored in canonical (sorted) order so the UNIQUE key catches reversed duplicates.
SYMMETRIC_RELATIONS = {"same_problem", "same_method", "related", "contradicts"}
LINK_ORIGINS = {"manual", "openalex", "rules", "llm", "agent"}
LINK_STATUSES = {"suggested", "accepted", "rejected"}
GAP_TYPES = {"unaddressed_limitation", "common_limitation", "missing_dataset_or_metric",
             "method_not_applied_to_problem", "conflicting_findings", "untested_setting", "other"}
GAP_STATUSES = {"candidate", "accepted", "rejected"}
GAP_ORIGINS = {"manual", "agent", "rules", "llm"}
JACCARD_LINK = 0.2
JACCARD_COMMON_LIMITATION = 0.25
RULE_LIMIT = 5
METHOD_PAIR_CAP = 10

PROFILE_PURPOSE = "논문 정리"
GAP_PURPOSE = "연구 갭 찾기"
CLASSIFY_PURPOSE = "AI 분야 분류"

RULE_CUES = {
    "problem": ["we address", "problem of", "challenge", "suffer"],
    "method": ["we propose", "we introduce", "our method", "our approach"],
    "contributions": ["our contributions", "we show", "we demonstrate"],
    "strengths": ["advantage", "benefit"],
    "limitations": ["limitation", "fail to", "does not", "cannot"],
    "datasets": ["dataset", "benchmark"],
    "metrics": ["accuracy", "f1", "bleu", "map", "top-1"],
    "results": ["outperform", "improves", "achieves"],
    "future_work": ["future work", "in the future"],
}
METRIC_WORDS = {"accuracy", "f1", "bleu", "map", "top-1", "rouge", "auc", "precision", "recall", "mse", "rmse",
                "psnr", "ssim", "iou", "fid", "perplexity"}
STOPWORDS = {"the", "and", "for", "with", "that", "this", "from", "are", "was", "were", "has", "have", "our",
             "their", "its", "into", "can", "not", "but", "use", "using", "based", "such", "also", "which", "than",
             "more", "over", "all", "any", "one", "two", "via", "our", "we", "they", "is", "be", "to", "of", "in", "on",
             "by", "as", "at", "an", "a", "it", "or", "if", "so", "do", "does"}

OUT_OF_LIST = "목록 밖 논문 키"


class AIHashBody(BaseModel):
    preview_hash: Optional[str] = Field(default=None, max_length=128)


class ProfileCreate(BaseModel):
    data: Dict[str, Any]
    origin: str = Field(pattern="^(manual|agent)$")
    model: Optional[str] = Field(default=None, max_length=200)


class ProfilePatch(BaseModel):
    status: str = Field(pattern="^(draft|confirmed)$")


class LinkCreate(BaseModel):
    source_paper_id: str = Field(min_length=1, max_length=64)
    target_paper_id: str = Field(min_length=1, max_length=64)
    relation: str = Field(pattern="^(cites|extends|compares_against|contradicts|supports|same_problem|same_method|uses_dataset|related)$")
    note: str = Field(default="", max_length=2000)
    origin: str = Field(default="manual", pattern="^(manual|agent)$")


class LinkPatch(BaseModel):
    status: Optional[str] = Field(default=None, pattern="^(suggested|accepted|rejected)$")
    note: Optional[str] = Field(default=None, max_length=2000)


class DiscoverRequest(BaseModel):
    use_openalex: bool = False


class GapRulesRequest(BaseModel):
    paper_ids: List[str] = Field(min_length=1, max_length=20)
    project_id: Optional[str] = Field(default=None, max_length=64)


class GapAIRequest(BaseModel):
    paper_ids: List[str] = Field(min_length=1, max_length=20)
    project_id: Optional[str] = Field(default=None, max_length=64)
    focus: Optional[str] = Field(default=None, max_length=500)
    preview_hash: Optional[str] = Field(default=None, max_length=128)


class GapEvidenceIn(BaseModel):
    paper_id: str = Field(min_length=1, max_length=64)
    quote: str = Field(min_length=1, max_length=MAX_QUOTE)
    page: Optional[int] = Field(default=None, ge=1)
    facet: Optional[str] = Field(default=None, max_length=40)


class GapCreate(BaseModel):
    paper_ids: List[str] = Field(min_length=1, max_length=20)
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(default="", max_length=4000)
    gap_type: str = Field(pattern="^(unaddressed_limitation|common_limitation|missing_dataset_or_metric|method_not_applied_to_problem|conflicting_findings|untested_setting|other)$")
    evidence: List[GapEvidenceIn] = Field(default_factory=list, max_length=50)
    project_id: Optional[str] = Field(default=None, max_length=64)
    origin: str = Field(pattern="^(manual|agent)$")


class GapPatch(BaseModel):
    status: Optional[str] = Field(default=None, pattern="^(candidate|accepted|rejected)$")
    title: Optional[str] = Field(default=None, max_length=300)
    description: Optional[str] = Field(default=None, max_length=4000)


class GapToIdea(BaseModel):
    project_id: str = Field(min_length=1, max_length=64)


# ---- shared helpers --------------------------------------------------------

def _paper_or_404(con, paper_id: str):
    row = con.execute("SELECT * FROM papers WHERE id=? AND deleted_at IS NULL", (paper_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "논문을 찾을 수 없습니다.")
    return row


def _active_project_or_404(con, project_id: Optional[str]) -> None:
    if project_id is None:
        return
    row = con.execute("SELECT id FROM projects WHERE id=? AND id NOT IN (SELECT project_id FROM project_trash)",
                      (project_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "프로젝트를 찾을 수 없습니다.")


def _bad(message: str) -> HTTPException:
    return HTTPException(422, message)


def _invalid_response(message: str = "AI 응답에서 유효한 항목을 찾지 못했습니다.") -> HTTPException:
    return HTTPException(502, {"code": "invalid_response", "message": message})


def _norm(text: str) -> str:
    """Comparison form: NFKC, soft hyphens and line-break hyphens removed, case and whitespace folded."""
    value = unicodedata.normalize("NFKC", text or "").replace("­", "")
    value = re.sub(r"(?<=\w)-\s+(?=\w)", "", value)
    return " ".join(value.lower().split())


def _locate(pages: List[Tuple[int, str]], quote: str, claimed: Optional[int] = None) -> Tuple[str, Optional[int]]:
    """Return (match, found_page).

    found_page is None when the quote is confirmed on the claimed page; otherwise
    it is the physical page where the quote was found. not_found has no page.
    """
    needle = (quote or "").strip()
    if not needle:
        return "not_found", None
    folded = _norm(needle)
    if claimed is not None:
        text = next((t for n, t in pages if n == claimed), None)
        if text is not None:
            if needle in text:
                return "exact", None
            if folded and folded in _norm(text):
                return "normalized", None
    for number, text in pages:
        if needle in text:
            return "exact", (None if number == claimed else number)
    for number, text in pages:
        if folded and folded in _norm(text):
            return "normalized", (None if number == claimed else number)
    return "not_found", None


def _pages(con, paper_id: str) -> List[Tuple[int, str]]:
    return [(r["page_index"] + 1, r["text"] or "")
            for r in con.execute("SELECT page_index,text FROM pages WHERE paper_id=? ORDER BY page_index", (paper_id,))]


def verify_quotes(con, paper_id: str, data: dict) -> dict:
    """Return a copy of profile data with each evidence entry's match and found_page set."""
    pages = _pages(con, paper_id)
    result = json.loads(json.dumps(data))
    for facet in FACETS:
        for item in (result.get("facets") or {}).get(facet, []):
            for evidence in item.get("evidence", []):
                match, found = _locate(pages, evidence.get("quote", ""), evidence.get("page"))
                evidence["match"] = match
                evidence["found_page"] = found
    return result


def _sentences(text: str) -> List[str]:
    out = []
    for m in re.finditer(r"[^.!?]+(?:[.!?]+|$)", text or "", flags=re.S):
        sentence = m.group(0).strip()
        if len(sentence) >= 25:
            out.append(sentence[:MAX_QUOTE])
    return out


def _tokens(text: str) -> set:
    return {t for t in re.findall(r"[0-9a-z가-힣]+", (text or "").lower())
            if len(t) >= 2 and t not in STOPWORDS}


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _name_terms(text: str) -> set:
    """Dataset-like terms: tokens with a digit or an uppercase letter after the first character, plus metric words."""
    terms = set()
    for token in re.findall(r"[A-Za-z][A-Za-z0-9-]*[A-Za-z0-9]", text or ""):
        if len(token) >= 2 and (re.search(r"\d", token) or re.search(r"[A-Z]", token[1:])):
            terms.add(token.lower())
    for word in re.findall(r"[a-z0-9-]+", (text or "").lower()):
        if word in METRIC_WORDS:
            terms.add(word)
    return terms


def _profile_row_out(row) -> dict:
    return {"id": row["id"], "paper_id": row["paper_id"], "origin": row["origin"], "status": row["status"],
            "model": row["model"], "created_at": row["created_at"], "data": json.loads(row["profile_json"])}


def _latest_profile(con, paper_id: str):
    return con.execute("SELECT * FROM paper_profiles WHERE paper_id=? ORDER BY created_at DESC, rowid DESC LIMIT 1",
                       (paper_id,)).fetchone()


def _insert_profile(con, paper_id: str, origin: str, data: dict, model: Optional[str], input_hash: Optional[str]):
    profile_id = storage.new_id()
    con.execute("""INSERT INTO paper_profiles(id,paper_id,profile_json,origin,status,model,input_hash)
        VALUES(?,?,?,?,'draft',?,?)""",
                (profile_id, paper_id, json.dumps(data, ensure_ascii=False), origin, model, input_hash))
    return _profile_row_out(con.execute("SELECT * FROM paper_profiles WHERE id=?", (profile_id,)).fetchone())


def _rules_profile_data(con, paper_id: str) -> dict:
    paper = con.execute("SELECT * FROM papers WHERE id=?", (paper_id,)).fetchone()
    pages = _pages(con, paper_id)
    sentences = []
    for number, text in pages:
        for sentence in _sentences(text):
            sentences.append((number, sentence))
    facets = {facet: [] for facet in FACETS}
    for facet, cues in RULE_CUES.items():
        seen = set()
        items = []
        for number, sentence in sentences:
            low = sentence.lower()
            if sentence in seen or not any(re.search(r"(?<!\w)" + re.escape(cue) + r"(?!\w)", low) for cue in cues):
                continue
            seen.add(sentence)
            items.append({"text": sentence, "origin": "author_stated",
                          "evidence": [{"page": number, "quote": sentence}]})
            if len(items) >= RULE_LIMIT:
                break
        facets[facet] = items
    summary_source = (paper["abstract"] or "").strip() if paper else ""
    source_sentences = _sentences(summary_source) or [s for _, s in sentences[:2]]
    summary = " ".join(source_sentences[:2])[:SUMMARY_MAX]
    keywords = [r["name"] for r in con.execute(
        "SELECT name FROM paper_topics WHERE paper_id=? ORDER BY score DESC, name LIMIT 10", (paper_id,))]
    return {"summary": summary, "facets": facets, "keywords": keywords}


def _strict_item(raw, facet: str) -> dict:
    if not isinstance(raw, dict):
        raise _bad(f"{facet} 항목은 객체여야 합니다.")
    unknown = set(raw) - {"text", "origin", "evidence"}
    if unknown:
        raise _bad(f"알 수 없는 항목 키: {', '.join(sorted(unknown))}")
    text = raw.get("text")
    if not isinstance(text, str) or not text.strip() or len(text) > MAX_TEXT:
        raise _bad(f"{facet} 항목 텍스트는 1~{MAX_TEXT}자여야 합니다.")
    origin = raw.get("origin", "inferred")
    if origin not in ITEM_ORIGINS:
        raise _bad("항목 origin은 author_stated 또는 inferred여야 합니다.")
    evidence_raw = raw.get("evidence", [])
    if not isinstance(evidence_raw, list) or len(evidence_raw) > 10:
        raise _bad("evidence는 최대 10개의 목록이어야 합니다.")
    evidence = []
    for ev in evidence_raw:
        if not isinstance(ev, dict):
            raise _bad("evidence 항목은 객체여야 합니다.")
        if set(ev) - {"page", "quote", "match", "found_page"}:
            raise _bad("알 수 없는 evidence 키가 있습니다.")
        page = ev.get("page")
        if isinstance(page, bool) or not isinstance(page, int) or page < 1:
            raise _bad("evidence page는 1 이상의 정수여야 합니다.")
        quote = ev.get("quote")
        if not isinstance(quote, str) or not quote.strip() or len(quote) > MAX_QUOTE:
            raise _bad(f"quote는 1~{MAX_QUOTE}자여야 합니다.")
        evidence.append({"page": page, "quote": quote, "match": "not_found", "found_page": None})
    return {"text": text.strip(), "origin": origin, "evidence": evidence}


def _strict_profile(raw) -> dict:
    if not isinstance(raw, dict):
        raise _bad("프로필 데이터는 객체여야 합니다.")
    if set(raw) - {"summary", "facets", "keywords"}:
        raise _bad("알 수 없는 프로필 키가 있습니다.")
    summary = raw.get("summary", "")
    if not isinstance(summary, str) or len(summary) > SUMMARY_MAX:
        raise _bad(f"summary는 {SUMMARY_MAX}자 이하의 문자열이어야 합니다.")
    keywords = raw.get("keywords", [])
    if not isinstance(keywords, list) or len(keywords) > MAX_KEYWORDS or \
            any(not isinstance(k, str) or not 1 <= len(k.strip()) <= 80 for k in keywords):
        raise _bad("keywords는 최대 20개의 1~80자 문자열 목록이어야 합니다.")
    facets_raw = raw.get("facets", {})
    if not isinstance(facets_raw, dict):
        raise _bad("facets는 객체여야 합니다.")
    unknown = set(facets_raw) - set(FACETS)
    if unknown:
        raise _bad(f"알 수 없는 facet: {', '.join(sorted(unknown))}")
    facets = {}
    for facet in FACETS:
        items = facets_raw.get(facet, [])
        if not isinstance(items, list) or len(items) > MAX_ITEMS:
            raise _bad(f"{facet}는 최대 {MAX_ITEMS}개 항목의 목록이어야 합니다.")
        facets[facet] = [_strict_item(item, facet) for item in items]
    return {"summary": summary, "facets": facets, "keywords": [k.strip() for k in keywords]}


def _clean_ai_profile(raw) -> dict:
    """Keep only well-formed items; drop the rest. Raises 502 when nothing usable remains."""
    if not isinstance(raw, dict):
        raise _invalid_response()
    summary = raw.get("summary") if isinstance(raw.get("summary"), str) else ""
    summary = summary.strip()[:SUMMARY_MAX]
    keywords_raw = raw.get("keywords") if isinstance(raw.get("keywords"), list) else []
    keywords = [k.strip()[:80] for k in keywords_raw if isinstance(k, str) and k.strip()][:MAX_KEYWORDS]
    # Small models sometimes put facets at the top level or return plain strings.
    facets_raw = raw.get("facets") if isinstance(raw.get("facets"), dict) else raw
    facets = {}
    total = 0
    for facet in FACETS:
        items = []
        values = facets_raw.get(facet)
        if isinstance(values, (str, dict)):
            values = [values]
        for item in (values if isinstance(values, list) else []):
            if isinstance(item, str):
                item = {"text": item}
            if not isinstance(item, dict) or not isinstance(item.get("text"), str) or not item["text"].strip():
                continue
            evidence = []
            for ev in (item.get("evidence") if isinstance(item.get("evidence"), list) else []):
                if not isinstance(ev, dict):
                    continue
                page, quote = ev.get("page"), ev.get("quote")
                if isinstance(page, str) and page.strip().isdigit():
                    page = int(page.strip())
                if isinstance(page, bool) or not isinstance(page, int) or page < 1:
                    continue
                if not isinstance(quote, str) or not quote.strip():
                    continue
                evidence.append({"page": page, "quote": quote[:MAX_QUOTE], "match": "not_found", "found_page": None})
            origin = item.get("origin") if item.get("origin") in ITEM_ORIGINS else "inferred"
            items.append({"text": item["text"].strip()[:MAX_TEXT], "origin": origin, "evidence": evidence[:10]})
            if len(items) >= MAX_ITEMS:
                break
        facets[facet] = items
        total += len(items)
    if total == 0 and not summary:
        raise _invalid_response()
    return {"summary": summary, "facets": facets, "keywords": keywords}


def _profile_out_list(con, paper_id: str) -> dict:
    latest = _latest_profile(con, paper_id)
    history = [dict(r) for r in con.execute(
        "SELECT id,origin,status,model,created_at FROM paper_profiles WHERE paper_id=? ORDER BY created_at DESC, rowid DESC",
        (paper_id,))]
    return {"profile": _profile_row_out(latest) if latest else None, "history": history}


def _ensure_profile_data(con, paper_id: str) -> dict:
    latest = _latest_profile(con, paper_id)
    if latest is not None:
        return json.loads(latest["profile_json"])
    data = verify_quotes(con, paper_id, _rules_profile_data(con, paper_id))
    _insert_profile(con, paper_id, "rules", data, None, None)
    return data


# ---- profiles --------------------------------------------------------------

@router.get("/api/papers/{paper_id}/profile")
def get_profile(paper_id: str):
    with storage.transaction() as con:
        _paper_or_404(con, paper_id)
        return _profile_out_list(con, paper_id)


@router.post("/api/papers/{paper_id}/profile/rules", status_code=201)
def create_rules_profile(paper_id: str):
    with storage.transaction() as con:
        _paper_or_404(con, paper_id)
        data = verify_quotes(con, paper_id, _rules_profile_data(con, paper_id))
        return _insert_profile(con, paper_id, "rules", data, None, None)


_ITEM_SCHEMA = {"type": "object", "properties": {
    "text": {"type": "string"}, "origin": {"type": "string", "enum": ["author_stated", "inferred"]},
    "evidence": {"type": "array", "items": {"type": "object", "properties": {
        "page": {"type": "integer"}, "quote": {"type": "string"}}, "required": ["page", "quote"]}}},
    "required": ["text", "origin", "evidence"]}
# Constrains the output shape on providers that support JSON Schema (Ollama).
PROFILE_SCHEMA = {"type": "object", "properties": {
    "summary": {"type": "string"}, "keywords": {"type": "array", "items": {"type": "string"}},
    "facets": {"type": "object", "properties": {f: {"type": "array", "items": _ITEM_SCHEMA} for f in FACETS},
               "required": list(FACETS)}},
    "required": ["summary", "keywords", "facets"]}


def _profile_messages(con, paper_id: str, max_chars: int) -> list:
    paper = _paper_or_404(con, paper_id)
    title = (paper["title"] or "")[:300]
    abstract = (paper["abstract"] or "")[:3000]
    system = (
        "You summarize one academic paper into a structured JSON profile for a researcher. "
        "Write summary and text fields in Korean. Copy every evidence quote verbatim from the document "
        "in its original language. Page numbers are 1-based physical page numbers from the page labels. "
        "Use only facets from the schema. Keep at most 12 items per facet. "
        + llm.UNTRUSTED_RULE + " "
        "Return only a JSON object with this shape: "
        '{"summary": "string", "keywords": ["string"], "facets": {"problem": [ITEM], "method": [ITEM], '
        '"contributions": [ITEM], "strengths": [ITEM], "limitations": [ITEM], "datasets": [ITEM], '
        '"metrics": [ITEM], "results": [ITEM], "future_work": [ITEM]}} '
        'where ITEM is {"text": "string", "origin": "author_stated" or "inferred", '
        '"evidence": [{"page": 1, "quote": "string"}]}.'
    )
    pages = [(r["page_index"] + 1, r["text"] or "") for r in con.execute(
        "SELECT page_index,text FROM pages WHERE paper_id=? ORDER BY page_index", (paper_id,)) if (r["text"] or "").strip()]
    parts = [f"Title:\n{llm.untrusted_block('title', title)}", f"Abstract:\n{llm.untrusted_block('abstract', abstract)}"]
    remaining = max_chars - len(system) - sum(len(p) for p in parts) - 200

    def priority(entry):
        number, text = entry
        if number <= 3:
            return (0, number)
        if re.search(r"limitation|conclusion|future work|discussion", text.lower()):
            return (1, number)
        return (2, number)

    chosen = []
    for number, text in sorted(pages, key=priority):
        overhead = len(f'<document label="page {number}">\n\n</document>') + 2
        room = remaining - overhead
        if room < 300:
            break
        snippet = text[:room]
        chosen.append((number, snippet))
        remaining -= len(snippet) + overhead
    for number, snippet in sorted(chosen):
        parts.append(llm.untrusted_block(f"page {number}", snippet))
    return [{"role": "system", "content": system}, {"role": "user", "content": "\n\n".join(parts)}]


@router.post("/api/papers/{paper_id}/profile/ai/preview")
def preview_profile_ai(paper_id: str):
    config = llm.get_config()
    with storage.transaction() as con:
        messages = _profile_messages(con, paper_id, config["max_input_chars"])
    return run_llm(lambda: llm.preview(messages, purpose=PROFILE_PURPOSE, json_output=True))


@router.post("/api/papers/{paper_id}/profile/ai", status_code=201)
def create_profile_ai(paper_id: str, payload: AIHashBody):
    config = llm.get_config()
    with storage.transaction() as con:
        messages = _profile_messages(con, paper_id, config["max_input_chars"])
    result = run_llm(lambda: llm.complete_json(messages, purpose=PROFILE_PURPOSE,
                                               preview_hash=payload.preview_hash, max_tokens=3000,
                                               schema=PROFILE_SCHEMA))
    with storage.transaction() as con:
        _paper_or_404(con, paper_id)
        data = verify_quotes(con, paper_id, _clean_ai_profile(result["data"]))
        return _insert_profile(con, paper_id, "llm", data, result["model"], result["preview_hash"])


@router.post("/api/papers/{paper_id}/profile", status_code=201)
def create_profile_manual(paper_id: str, payload: ProfileCreate):
    data = _strict_profile(payload.data)
    with storage.transaction() as con:
        _paper_or_404(con, paper_id)
        verified = verify_quotes(con, paper_id, data)
        return _insert_profile(con, paper_id, payload.origin, verified, payload.model, None)


@router.patch("/api/profiles/{profile_id}")
def patch_profile(profile_id: str, payload: ProfilePatch):
    with storage.transaction() as con:
        row = con.execute("SELECT * FROM paper_profiles WHERE id=?", (profile_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "프로필을 찾을 수 없습니다.")
        con.execute("UPDATE paper_profiles SET status=? WHERE id=?", (payload.status, profile_id))
        return _profile_row_out(con.execute("SELECT * FROM paper_profiles WHERE id=?", (profile_id,)).fetchone())


# ---- links and graph ------------------------------------------------------

def _canonical(relation: str, a: str, b: str) -> Tuple[str, str]:
    if relation in SYMMETRIC_RELATIONS and a > b:
        return b, a
    return a, b


def _link_out(row) -> dict:
    return {"id": row["id"], "source_paper_id": row["source_paper_id"], "target_paper_id": row["target_paper_id"],
            "source_title": row["source_title"], "target_title": row["target_title"], "relation": row["relation"],
            "origin": row["origin"], "status": row["status"], "note": row["note"],
            "detail": json.loads(row["detail_json"] or "{}"), "created_at": row["created_at"],
            "updated_at": row["updated_at"]}


LINK_SELECT = """SELECT l.*, sp.title AS source_title, tp.title AS target_title FROM paper_links l
    JOIN papers sp ON sp.id=l.source_paper_id JOIN papers tp ON tp.id=l.target_paper_id"""


def _link_or_404(con, link_id: str):
    row = con.execute(LINK_SELECT + " WHERE l.id=?", (link_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "연결을 찾을 수 없습니다.")
    return row


@router.get("/api/papers/{paper_id}/links")
def list_paper_links(paper_id: str):
    with storage.transaction() as con:
        _paper_or_404(con, paper_id)
        rows = con.execute(LINK_SELECT + """ WHERE (l.source_paper_id=? OR l.target_paper_id=?)
            AND sp.deleted_at IS NULL AND tp.deleted_at IS NULL ORDER BY l.created_at DESC, l.rowid DESC""",
                           (paper_id, paper_id)).fetchall()
        out = []
        for row in rows:
            item = _link_out(row)
            outgoing = row["source_paper_id"] == paper_id
            item["direction"] = "outgoing" if outgoing else "incoming"
            item["other_paper_id"] = row["target_paper_id"] if outgoing else row["source_paper_id"]
            item["other_title"] = row["target_title"] if outgoing else row["source_title"]
            out.append(item)
        return out


@router.post("/api/paper-links", status_code=201)
def create_paper_link(payload: LinkCreate):
    if payload.source_paper_id == payload.target_paper_id:
        raise _bad("같은 논문끼리는 연결할 수 없습니다.")
    source, target = _canonical(payload.relation, payload.source_paper_id, payload.target_paper_id)
    status = "accepted" if payload.origin == "manual" else "suggested"
    with storage.transaction() as con:
        _paper_or_404(con, payload.source_paper_id)
        _paper_or_404(con, payload.target_paper_id)
        if con.execute("SELECT 1 FROM paper_links WHERE source_paper_id=? AND target_paper_id=? AND relation=?",
                       (source, target, payload.relation)).fetchone():
            raise HTTPException(409, "같은 연결이 이미 있습니다.")
        link_id = storage.new_id()
        try:
            con.execute("""INSERT INTO paper_links(id,source_paper_id,target_paper_id,relation,origin,status,note)
                VALUES(?,?,?,?,?,?,?)""", (link_id, source, target, payload.relation, payload.origin, status, payload.note))
        except sqlite3.IntegrityError as exc:
            raise HTTPException(409, "같은 연결이 이미 있습니다.") from exc
        return _link_out(_link_or_404(con, link_id))


@router.patch("/api/paper-links/{link_id}")
def patch_paper_link(link_id: str, payload: LinkPatch):
    with storage.transaction() as con:
        _link_or_404(con, link_id)
        if payload.status is not None:
            con.execute("UPDATE paper_links SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (payload.status, link_id))
        if payload.note is not None:
            con.execute("UPDATE paper_links SET note=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (payload.note, link_id))
        return _link_out(_link_or_404(con, link_id))


@router.delete("/api/paper-links/{link_id}", status_code=204)
def delete_paper_link(link_id: str):
    with storage.transaction() as con:
        _link_or_404(con, link_id)
        con.execute("DELETE FROM paper_links WHERE id=?", (link_id,))
    return Response(status_code=204)


def _pair_exists(con, source: str, target: str, relation: str) -> bool:
    """Any status counts, so a rejected link is never recreated."""
    return con.execute("SELECT 1 FROM paper_links WHERE source_paper_id=? AND target_paper_id=? AND relation=?",
                       (source, target, relation)).fetchone() is not None


def _discover_local(con) -> Tuple[int, int]:
    papers = [r["id"] for r in con.execute("SELECT id FROM papers WHERE deleted_at IS NULL ORDER BY id")]
    categories_of: Dict[str, set] = {pid: set() for pid in papers}
    for r in con.execute("SELECT paper_id,category_id FROM paper_categories WHERE status IN ('confirmed','suggested')"):
        if r["paper_id"] in categories_of:
            categories_of[r["paper_id"]].add(r["category_id"])
    kw, method, problem = {}, {}, {}
    for pid in papers:
        latest = _latest_profile(con, pid)
        data = json.loads(latest["profile_json"]) if latest else {}
        facets = data.get("facets") or {}
        kw[pid] = _tokens(" ".join(data.get("keywords") or []))
        method[pid] = _tokens(" ".join(i.get("text", "") for i in facets.get("method", [])))
        problem[pid] = _tokens(" ".join(i.get("text", "") for i in facets.get("problem", [])))
    created = skipped = 0
    for i, a in enumerate(papers):
        for b in papers[i + 1:]:
            shared = categories_of[a] & categories_of[b]
            sim = _jaccard(kw[a] | method[a], kw[b] | method[b])
            if not shared and sim < JACCARD_LINK:
                continue
            if _jaccard(method[a], method[b]) >= JACCARD_LINK:
                relation = "same_method"
            elif _jaccard(problem[a], problem[b]) >= JACCARD_LINK:
                relation = "same_problem"
            else:
                relation = "related"
            source, target = _canonical(relation, a, b)
            if _pair_exists(con, source, target, relation):
                skipped += 1
                continue
            reason = "token_overlap" if sim >= JACCARD_LINK else "same_category"
            con.execute("""INSERT INTO paper_links(id,source_paper_id,target_paper_id,relation,origin,status,note,detail_json)
                VALUES(?,?,?,?,'rules','suggested','',?)""",
                        (storage.new_id(), source, target, relation,
                         json.dumps({"reason": reason, "score": round(sim, 3)})))
            created += 1
    return created, skipped


_OPENALEX_W = re.compile(r"(W\d+)\s*$")


def _openalex_id(value) -> Optional[str]:
    if not isinstance(value, str):
        return None
    match = _OPENALEX_W.search(value.strip())
    return match.group(1) if match else None


def _openalex_fetch(papers_meta: list, errors: list) -> List[Tuple[str, list]]:
    headers = categories._openalex_headers()
    fetched = []
    for paper_id, doi in papers_meta:
        url = ("https://api.openalex.org/works/doi:" + quote(doi, safe="/") + "?"
               + urlencode({"select": "id,doi,referenced_works"}))
        try:
            record = scholarly._json("openalex", scholarly._get("openalex", url, headers))
        except scholarly.ScholarlyError as exc:
            errors.append({"paper_id": paper_id, "code": exc.code, "message": "OpenAlex 조회에 실패했습니다."})
            if exc.code == "rate_limited":
                break
            continue
        refs = [w for w in (_openalex_id(x) for x in (record.get("referenced_works") or [])) if w]
        own = _openalex_id(record.get("id"))
        fetched.append((paper_id, own, refs))
    return fetched


def _discover_openalex_write(con, fetched: list, extra_map: Dict[str, str]) -> Tuple[int, int]:
    created = skipped = 0
    oa_map = dict(extra_map)
    for paper_id, own, _refs in fetched:
        if own:
            oa_map.setdefault(own, paper_id)
    for paper_id, _own, refs in fetched:
        for ref in refs:
            target = oa_map.get(ref)
            if not target or target == paper_id:
                continue
            if _pair_exists(con, paper_id, target, "cites"):
                skipped += 1
                continue
            con.execute("""INSERT INTO paper_links(id,source_paper_id,target_paper_id,relation,origin,status,note,detail_json)
                VALUES(?,?,?,?,'openalex','accepted','',?)""",
                        (storage.new_id(), paper_id, target, "cites", json.dumps({"openalex_id": ref})))
            created += 1
    return created, skipped


@router.post("/api/library/links/discover")
def discover_links(payload: DiscoverRequest):
    errors: List[dict] = []
    with storage.transaction() as con:
        created, skipped = _discover_local(con)
    if payload.use_openalex:
        with storage.transaction() as con:
            rows = con.execute("SELECT id,doi,source,source_id FROM papers WHERE deleted_at IS NULL").fetchall()
            oa_map: Dict[str, str] = {}
            doi_jobs = []
            for r in rows:
                if r["source"] == "openalex" and _openalex_id(r["source_id"]):
                    oa_map[_openalex_id(r["source_id"])] = r["id"]
                if r["doi"]:
                    try:
                        doi_jobs.append((r["id"], scholarly.normalize_doi(r["doi"])))
                    except ValueError:
                        continue
        fetched = _openalex_fetch(doi_jobs, errors)
        with storage.transaction() as con:
            c2, s2 = _discover_openalex_write(con, fetched, oa_map)
        created += c2
        skipped += s2
    return {"created": created, "skipped": skipped, "errors": errors}


@router.get("/api/library/graph")
def library_graph():
    with storage.transaction() as con:
        nodes_rows = con.execute("SELECT id,title,year FROM papers WHERE deleted_at IS NULL ORDER BY id").fetchall()
        reading = {r["paper_id"]: r["reading_status"] for r in con.execute("SELECT paper_id,reading_status FROM paper_reading_state")}
        cats: Dict[str, List[str]] = {}
        for r in con.execute("""SELECT pc.paper_id, c.name FROM paper_categories pc JOIN categories c ON c.id=pc.category_id
                WHERE pc.status != 'rejected' ORDER BY c.name"""):
            cats.setdefault(r["paper_id"], []).append(r["name"])
        nodes = [{"id": r["id"], "title": r["title"], "year": r["year"],
                  "reading_status": reading.get(r["id"], "to_read"), "categories": cats.get(r["id"], [])}
                 for r in nodes_rows]
        edges = [{"id": r["id"], "source": r["source_paper_id"], "target": r["target_paper_id"], "relation": r["relation"],
                  "origin": r["origin"], "status": r["status"]}
                 for r in con.execute("""SELECT l.* FROM paper_links l
                    JOIN papers s ON s.id=l.source_paper_id AND s.deleted_at IS NULL
                    JOIN papers t ON t.id=l.target_paper_id AND t.deleted_at IS NULL
                    WHERE l.status != 'rejected' ORDER BY l.created_at, l.rowid""")]
        return {"nodes": nodes, "edges": edges}


# ---- gaps ----------------------------------------------------------------

def _gap_out(row) -> dict:
    return {"id": row["id"], "project_id": row["project_id"], "title": row["title"], "description": row["description"],
            "gap_type": row["gap_type"], "paper_ids": json.loads(row["paper_ids_json"] or "[]"),
            "evidence": json.loads(row["evidence_json"] or "[]"), "origin": row["origin"], "status": row["status"],
            "model": row["model"], "created_at": row["created_at"], "updated_at": row["updated_at"]}


def _gap_or_404(con, gap_id: str):
    row = con.execute("SELECT * FROM research_gaps WHERE id=?", (gap_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "갭을 찾을 수 없습니다.")
    return row


def _gap_key(title: str, paper_ids: List[str]) -> Tuple[str, Tuple[str, ...]]:
    return title, tuple(sorted(set(paper_ids)))


def _existing_gap_keys(con) -> set:
    keys = set()
    for r in con.execute("SELECT title, paper_ids_json FROM research_gaps"):
        keys.add(_gap_key(r["title"], json.loads(r["paper_ids_json"] or "[]")))
    return keys


def _insert_gap(con, project_id, cand: dict, origin: str, model: Optional[str]) -> dict:
    gap_id = storage.new_id()
    con.execute("""INSERT INTO research_gaps(id,project_id,title,description,gap_type,paper_ids_json,evidence_json,origin,status,model)
        VALUES(?,?,?,?,?,?,?,?,'candidate',?)""",
                (gap_id, project_id, cand["title"][:300], cand.get("description", "")[:4000], cand["gap_type"],
                 json.dumps(cand["paper_ids"]), json.dumps(cand.get("evidence", []), ensure_ascii=False), origin, model))
    return _gap_out(_gap_or_404(con, gap_id))


def _verified_evidence(pid: str, facet: str, item: dict) -> List[dict]:
    out = []
    for ev in item.get("evidence", []):
        if ev.get("match") == "not_found":
            continue
        out.append({"paper_id": pid, "facet": facet, "quote": ev["quote"],
                    "page": ev.get("found_page") or ev.get("page"), "match": ev["match"]})
    return out


def _rule_candidates(papers: List[dict]) -> List[dict]:
    """papers: [{id, title, data}] in request order."""
    cands: List[dict] = []
    for p in papers:
        for facet in ("limitations", "future_work"):
            for item in p["data"]["facets"].get(facet, []):
                cands.append({"title": f"{p['title'][:60]}: {item['text'][:120]}", "description": item["text"],
                              "gap_type": "unaddressed_limitation", "paper_ids": [p["id"]],
                              "evidence": _verified_evidence(p["id"], facet, item)})
    for i, a in enumerate(papers):
        for b in papers[i + 1:]:
            best = (0.0, None, None)
            for la in a["data"]["facets"].get("limitations", []):
                for lb in b["data"]["facets"].get("limitations", []):
                    score = _jaccard(_tokens(la["text"]), _tokens(lb["text"]))
                    if score > best[0]:
                        best = (score, la, lb)
            if best[0] >= JACCARD_COMMON_LIMITATION:
                _, la, lb = best
                cands.append({"title": f"공통 한계: {a['title'][:50]} · {b['title'][:50]}",
                              "description": f"{la['text']}\n↔ {lb['text']}", "gap_type": "common_limitation",
                              "paper_ids": [a["id"], b["id"]],
                              "evidence": _verified_evidence(a["id"], "limitations", la) +
                              _verified_evidence(b["id"], "limitations", lb)})
    if len(papers) >= 2:
        for facet in ("datasets", "metrics"):
            terms: Dict[str, List[Tuple[str, dict]]] = {}
            for p in papers:
                for item in p["data"]["facets"].get(facet, []):
                    for term in _name_terms(item["text"]):
                        terms.setdefault(term, []).append((p["id"], item))
            for term in sorted(terms):
                present = {pid for pid, _ in terms[term]}
                if not 0 < len(present) < len(papers):
                    continue
                evidence = []
                for pid, item in terms[term]:
                    evidence.extend(_verified_evidence(pid, facet, item))
                label = "데이터셋" if facet == "datasets" else "지표"
                cands.append({"title": f"{label} 공백: {term}",
                              "description": f"{term}은(는) {len(present)}편에서 쓰였고 "
                                             f"{len(papers) - len(present)}편에서는 확인되지 않았습니다.",
                              "gap_type": "missing_dataset_or_metric", "paper_ids": [p["id"] for p in papers],
                              "evidence": evidence})
    count = 0
    for a in papers:
        for b in papers:
            if a is b:
                continue
            for m in a["data"]["facets"].get("method", [])[:3]:
                for pr in b["data"]["facets"].get("problem", [])[:3]:
                    if count >= METHOD_PAIR_CAP:
                        break
                    cands.append({"title": f"{a['title'][:40]}의 방법을 {b['title'][:40]}의 문제에 적용",
                                  "description": f"방법: {m['text']}\n문제: {pr['text']}",
                                  "gap_type": "method_not_applied_to_problem", "paper_ids": [a["id"], b["id"]],
                                  "evidence": _verified_evidence(a["id"], "method", m) +
                                  _verified_evidence(b["id"], "problem", pr)})
                    count += 1
    return cands


def _resolve_papers(con, paper_ids: List[str]) -> List[str]:
    ids = list(dict.fromkeys(paper_ids))
    for pid in ids:
        _paper_or_404(con, pid)
    return ids


@router.post("/api/gaps/rules", status_code=201)
def create_rule_gaps(payload: GapRulesRequest):
    with storage.transaction() as con:
        ids = _resolve_papers(con, payload.paper_ids)
        _active_project_or_404(con, payload.project_id)
        papers = []
        for pid in ids:
            paper = _paper_or_404(con, pid)
            papers.append({"id": pid, "title": paper["title"] or "", "data": _ensure_profile_data(con, pid)})
        existing = _existing_gap_keys(con)
        out = []
        for cand in _rule_candidates(papers):
            key = _gap_key(cand["title"], cand["paper_ids"])
            if key in existing:
                continue
            existing.add(key)
            out.append(_insert_gap(con, payload.project_id, cand, "rules", None))
        return out


def _gap_cards(con, ids: List[str], max_chars: int) -> Tuple[str, Dict[str, str]]:
    key_map = {}
    per_card = max(300, (max_chars - 1500) // max(1, len(ids)))
    cards = []
    for index, pid in enumerate(ids, start=1):
        paper = _paper_or_404(con, pid)
        key = f"P{index}"
        key_map[key] = pid
        latest = _latest_profile(con, pid)
        profile = json.loads(latest["profile_json"]) if latest else {}
        facets = profile.get("facets") or {}

        def joined(facet):
            return " / ".join(i.get("text", "") for i in facets.get(facet, []))

        lines = [f"{key} | {paper['title'] or ''} ({paper['year'] or 'year unknown'})",
                 f"abstract: {(paper['abstract'] or '')[:per_card // 2]}",
                 f"summary: {(profile.get('summary') or '')[:200]}",
                 f"problem: {joined('problem')[:150]}",
                 f"method: {joined('method')[:150]}",
                 f"limitations: {joined('limitations')[:200]}"]
        cards.append("\n".join(lines)[:per_card])
    return llm.untrusted_block("library papers", "\n\n".join(cards)), key_map


GAP_SYSTEM = (
    "You find research gaps across the given papers. Write title and description in Korean. "
    "Quotes must be copied verbatim from the paper text shown. Reference papers only by the keys P1..Pn shown. "
    + llm.UNTRUSTED_RULE + " Return only JSON: "
    '{"gaps": [{"title": "string", "description": "string", "gap_type": "unaddressed_limitation | '
    'common_limitation | missing_dataset_or_metric | method_not_applied_to_problem | conflicting_findings | '
    'untested_setting | other", "papers": ["P1"], "evidence": [{"paper": "P1", "quote": "string"}]}]}'
)


def _gap_messages(con, ids: List[str], focus: Optional[str], max_chars: int):
    cards, key_map = _gap_cards(con, ids, max_chars)
    user = "Papers:\n" + cards
    if focus:
        user += "\n\nUser focus: " + focus
    return [{"role": "system", "content": GAP_SYSTEM}, {"role": "user", "content": user}], key_map


@router.post("/api/gaps/ai/preview")
def preview_gaps_ai(payload: GapAIRequest):
    config = llm.get_config()
    with storage.transaction() as con:
        ids = _resolve_papers(con, payload.paper_ids)
        messages, _ = _gap_messages(con, ids, payload.focus, config["max_input_chars"])
    return run_llm(lambda: llm.preview(messages, purpose=GAP_PURPOSE, json_output=True))


def _locate_in_paper(pages: List[Tuple[int, str]], abstract: str, quote: str) -> Tuple[str, Optional[int]]:
    match, found = _locate(pages, quote)
    if match != "not_found":
        return match, found
    abstract_match, _ = _locate([(0, abstract or "")], quote)
    if abstract_match != "not_found":
        return abstract_match, None
    return "not_found", None


@router.post("/api/gaps/ai", status_code=201)
def create_gaps_ai(payload: GapAIRequest):
    config = llm.get_config()
    with storage.transaction() as con:
        ids = _resolve_papers(con, payload.paper_ids)
        _active_project_or_404(con, payload.project_id)
        messages, key_map = _gap_messages(con, ids, payload.focus, config["max_input_chars"])
    result = run_llm(lambda: llm.complete_json(messages, purpose=GAP_PURPOSE, preview_hash=payload.preview_hash,
                                               max_tokens=3000))
    raw = result["data"]
    if not isinstance(raw, dict) or not isinstance(raw.get("gaps"), list):
        raise _invalid_response()
    with storage.transaction() as con:
        _active_project_or_404(con, payload.project_id)
        existing = _existing_gap_keys(con)
        out = []
        for item in raw["gaps"]:
            if not isinstance(item, dict):
                continue
            title = item.get("title").strip() if isinstance(item.get("title"), str) else ""
            if not title:
                continue
            paper_keys = item.get("papers")
            if not isinstance(paper_keys, list) or not paper_keys or \
                    any(not isinstance(k, str) or k not in key_map for k in paper_keys):
                continue
            evidence_raw = item.get("evidence") if isinstance(item.get("evidence"), list) else []
            if any(not isinstance(ev, dict) or ev.get("paper") not in key_map for ev in evidence_raw):
                continue
            paper_ids = list(dict.fromkeys(key_map[k] for k in paper_keys))
            evidence = []
            for ev in evidence_raw:
                quote = ev.get("quote")
                if not isinstance(quote, str) or not quote.strip():
                    continue
                pid = key_map[ev["paper"]]
                pages = _pages(con, pid)
                abstract = _paper_or_404(con, pid)["abstract"] or ""
                match, page = _locate_in_paper(pages, abstract, quote[:MAX_QUOTE])
                if match == "not_found":
                    continue
                evidence.append({"paper_id": pid, "page": page, "quote": quote.strip()[:MAX_QUOTE], "match": match})
            gap_type = item.get("gap_type") if item.get("gap_type") in GAP_TYPES else "other"
            description = item.get("description") if isinstance(item.get("description"), str) else ""
            cand = {"title": title[:300], "description": description.strip()[:4000], "gap_type": gap_type,
                    "paper_ids": paper_ids, "evidence": evidence}
            key = _gap_key(cand["title"], paper_ids)
            if key in existing:
                continue
            existing.add(key)
            out.append(_insert_gap(con, payload.project_id, cand, "llm", result["model"]))
        return out


@router.post("/api/gaps", status_code=201)
def create_gap_manual(payload: GapCreate):
    """Manual or agent gap. Evidence quotes are verified against stored pages; not_found is kept visible as match."""
    with storage.transaction() as con:
        ids = _resolve_papers(con, payload.paper_ids)
        _active_project_or_404(con, payload.project_id)
        evidence = []
        for ev in payload.evidence:
            if ev.paper_id not in ids:
                raise _bad("근거의 논문은 갭의 논문 목록에 있어야 합니다.")
            pages = _pages(con, ev.paper_id)
            match, found = _locate(pages, ev.quote, ev.page)
            evidence.append({"paper_id": ev.paper_id, "page": found or ev.page, "quote": ev.quote,
                             "match": match, **({"facet": ev.facet} if ev.facet else {})})
        cand = {"title": payload.title.strip(), "description": payload.description, "gap_type": payload.gap_type,
                "paper_ids": ids, "evidence": evidence}
        return _insert_gap(con, payload.project_id, cand, payload.origin, None)


@router.get("/api/gaps")
def list_gaps(project_id: Optional[str] = None, paper_id: Optional[str] = None):
    with storage.transaction() as con:
        sql = """SELECT * FROM research_gaps WHERE (project_id IS NULL OR project_id NOT IN
            (SELECT project_id FROM project_trash))"""
        args: List[Any] = []
        if project_id:
            sql += " AND project_id=?"
            args.append(project_id)
        sql += " ORDER BY created_at DESC, rowid DESC"
        out = [_gap_out(r) for r in con.execute(sql, args)]
        if paper_id:
            out = [g for g in out if paper_id in g["paper_ids"]]
        return out


@router.patch("/api/gaps/{gap_id}")
def patch_gap(gap_id: str, payload: GapPatch):
    with storage.transaction() as con:
        _gap_or_404(con, gap_id)
        if payload.status is not None:
            con.execute("UPDATE research_gaps SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (payload.status, gap_id))
        if payload.title is not None:
            title = payload.title.strip()
            if not title:
                raise _bad("갭 제목을 입력해 주세요.")
            con.execute("UPDATE research_gaps SET title=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (title, gap_id))
        if payload.description is not None:
            con.execute("UPDATE research_gaps SET description=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                        (payload.description, gap_id))
        return _gap_out(_gap_or_404(con, gap_id))


@router.post("/api/gaps/{gap_id}/to-idea", status_code=201)
def gap_to_idea(gap_id: str, payload: GapToIdea):
    with storage.transaction() as con:
        gap = _gap_or_404(con, gap_id)
        _active_project_or_404(con, payload.project_id)
        idea_id = storage.new_id()
        con.execute("INSERT INTO ideas(id,project_id,title,description,status) VALUES(?,?,?,?,'draft')",
                    (idea_id, payload.project_id, gap["title"], gap["description"]))
        row = con.execute("SELECT * FROM ideas WHERE id=?", (idea_id,)).fetchone()
        return {"id": row["id"], "project_id": row["project_id"], "title": row["title"],
                "description": row["description"], "status": row["status"], "created_at": row["created_at"]}


# ---- AI classification ----------------------------------------------------

def _classify_messages(con, paper_id: str, max_chars: int):
    names = [r["name"] for r in con.execute("SELECT name FROM categories ORDER BY name")]
    if not names:
        raise _bad("먼저 분야를 만들어 주세요.")
    paper = _paper_or_404(con, paper_id)
    system = (
        "You classify one academic paper into research categories. Choose only from the category list given. "
        "If nothing fits, return an empty list and put up to 3 new category names in new_categories. "
        + llm.UNTRUSTED_RULE + " Return only JSON: "
        '{"categories": ["name from the list"], "new_categories": ["string"]}'
    )
    pages = [(r["page_index"] + 1, r["text"] or "") for r in con.execute(
        "SELECT page_index,text FROM pages WHERE paper_id=? AND page_index<3 ORDER BY page_index", (paper_id,))]
    parts = ["Category list:\n" + "\n".join(names),
             "Title:\n" + llm.untrusted_block("title", (paper["title"] or "")[:300]),
             "Abstract:\n" + llm.untrusted_block("abstract", (paper["abstract"] or "")[:2000])]
    budget = max_chars - len(system) - sum(len(p) for p in parts) - 200
    for number, text in pages:
        if budget < 300:
            break
        snippet = text[:budget - 60]
        parts.append(llm.untrusted_block(f"page {number}", snippet))
        budget -= len(snippet) + 60
    return [{"role": "system", "content": system}, {"role": "user", "content": "\n\n".join(parts)}], names


@router.post("/api/papers/{paper_id}/classify/ai/preview")
def preview_classify_ai(paper_id: str):
    config = llm.get_config()
    with storage.transaction() as con:
        messages, _ = _classify_messages(con, paper_id, config["max_input_chars"])
    return run_llm(lambda: llm.preview(messages, purpose=CLASSIFY_PURPOSE, json_output=True))


@router.post("/api/papers/{paper_id}/classify/ai")
def classify_ai(paper_id: str, payload: AIHashBody):
    config = llm.get_config()
    with storage.transaction() as con:
        messages, names = _classify_messages(con, paper_id, config["max_input_chars"])
    result = run_llm(lambda: llm.complete_json(messages, purpose=CLASSIFY_PURPOSE,
                                               preview_hash=payload.preview_hash, max_tokens=500))
    raw = result["data"]
    if not isinstance(raw, dict):
        raise _invalid_response()
    listed = raw.get("categories") if isinstance(raw.get("categories"), list) else []
    fresh = raw.get("new_categories") if isinstance(raw.get("new_categories"), list) else []
    by_fold = {n.casefold(): n for n in names}
    chosen: List[str] = []
    proposed: List[str] = []
    for value in listed:
        if not isinstance(value, str) or not value.strip():
            continue
        canonical = by_fold.get(value.strip().casefold())
        if canonical:
            if canonical not in chosen:
                chosen.append(canonical)
        elif value.strip()[:60] not in proposed:
            proposed.append(value.strip()[:60])
    for value in fresh:
        if isinstance(value, str) and value.strip() and value.strip()[:60] not in proposed \
                and value.strip().casefold() not in by_fold:
            proposed.append(value.strip()[:60])
    applied = []
    with storage.transaction() as con:
        _paper_or_404(con, paper_id)
        for name in chosen:
            category_id = con.execute("SELECT id FROM categories WHERE name=?", (name,)).fetchone()["id"]
            cursor = con.execute("""INSERT INTO paper_categories(paper_id,category_id,source,status,matched_json,updated_at)
                    VALUES(?,?,'llm','suggested','[]',CURRENT_TIMESTAMP)
                ON CONFLICT(paper_id,category_id) DO UPDATE SET source='llm', status='suggested', matched_json='[]',
                    updated_at=CURRENT_TIMESTAMP
                WHERE paper_categories.status NOT IN ('confirmed','rejected')""", (paper_id, category_id))
            if cursor.rowcount:
                applied.append(name)
    return {"applied": applied, "proposed_new": proposed[:10]}
