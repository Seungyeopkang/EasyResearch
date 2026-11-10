"""Idea/gap chat threads and the staged research loop.

Contract: docs/exec-plans/active/004-research-assistant.md (Workstream W2) and
docs/exec-plans/active/005-research-runtime-hardening.md (W-C).

Every model call goes through llm.preview() and then llm.complete().
A research run advances in a daemon worker thread (one at a time per run).
Each run has its own short lock around database read-modify-write sections.
That lock, and every database transaction, is never held during a model call.
State saves are conditional on the run not being cancelled.
"""
import hashlib
import json
import os
import random
import re
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

from . import llm, scholarly, storage
from .ai_routes import run_llm

router = APIRouter()

MODES = ("idea", "gap", "free")
DEFAULT_TITLES = {"idea": "아이디어 대화", "gap": "갭 대화", "free": "자유 대화"}
MODE_INSTRUCTIONS = {
    "idea": ("연구 아이디어를 구체화하도록 돕습니다. Heilmeier 질문을 한 번에 두 개 이내로 던집니다: "
             "어떤 문제를 푸는가, 현재 방법과 한계는 무엇인가, 무엇이 새로운가, 누가 관심을 갖는가, "
             "어떤 위험이 있는가, 어떻게 측정하는가."),
    "gap": ("연구 갭 후보를 검토합니다. 각 갭에 대해 뒷받침하는 근거와 반례를 묻습니다. "
            "논문이 직접 밝힌 한계와 추론한 한계를 구분해서 말합니다."),
    "free": "연구 도우미로서 연구자의 질문에 답합니다.",
}
CITATION_RULE = ("논문은 [P1]처럼, 갭은 [G1]처럼 주어진 키만 인용합니다. 주어진 목록에 없는 논문, 저자, 결과를 "
                 "만들지 않습니다. 근거가 목록에 없으면 모른다고 답합니다. 답변은 한국어로 씁니다.")
CHAT_PURPOSE = "연구 채팅"
HISTORY_LIMIT = 12
CONTENT_MAX = 8000
ABSTRACT_LIMITS = (1500, 800, 300, 0)
PROFILE_CARD_CHARS = 400

GAP_TYPES = ("unaddressed_limitation", "common_limitation", "missing_dataset_or_metric",
             "method_not_applied_to_problem", "conflicting_findings", "untested_setting", "other")
STAGES = ("plan_queries", "search", "screen", "problems", "methods", "contributions", "critique")
LLM_STAGES = frozenset(("plan_queries", "problems", "methods", "contributions", "critique"))
STEPPABLE = frozenset(("ready", "running", "failed_step"))
TERMINAL = frozenset(("awaiting_review", "completed", "cancelled", "budget_exhausted"))
NOVELTY_NOTE = "가장 가까운 선행 연구는 검색 결과일 뿐이며 참신성 판정이 아닙니다."
CHECK_NOTE = ("자기 점검은 같은 모델이 쓴 약점과 코드가 계산한 구조 점검입니다. 참신성 판정이 아니며, "
              "선행 연구 겹침은 검색어와 검색 결과의 단어 겹침일 뿐입니다.")
STOPWORDS = frozenset(("the", "and", "for", "with", "from", "that", "this", "are", "was", "were",
                       "using", "based", "study", "paper", "results", "our", "their", "into"))

DEFAULT_MAX_RUN_SECONDS = 2700
MAX_RAW_CHARS = 20000
INTERRUPTED_ERROR = "중단된 단계입니다. 다시 실행하세요."
CANCELLED_ERROR = "실행이 취소되었습니다."
BUDGET_MESSAGES = {"time": "실행 시간 예산을 넘었습니다.", "calls": "AI 호출 예산을 다 썼습니다."}
TRANSIENT_CODES = frozenset(("timeout", "network_error", "rate_limited"))

PLAN_PURPOSE = "연구 루프: 검색어 설계"
PROBLEM_PURPOSE = "연구 루프: 문제 찾기"
METHOD_PURPOSE = "연구 루프: 방법 설계"
CONTRIBUTION_PURPOSE = "연구 루프: 기여 초안"
CRITIQUE_PURPOSE = "연구 루프: 자기 점검"

# The JSON shape each system prompt names is part of the contract (see AGENTS.md: JSON prompts).
PLAN_SYSTEM = ("당신은 학술 문헌 검색 질의를 설계하는 도우미입니다.\n"
               "출력은 아래 형식의 JSON 객체 하나뿐이어야 합니다: {\"queries\": [\"...\"]}\n"
               "검색어는 3~5개이며 영어로 씁니다. 방법, 문제, 데이터셋, 한계처럼 서로 다른 각도에서 찾도록 만듭니다.\n"
               "근거를 인용할 때는 주어진 E 키만 씁니다. 설명은 한국어로 씁니다.")
PROBLEM_SYSTEM = ("당신은 근거에서 아직 열려 있는 연구 문제를 찾는 분석가입니다.\n"
                  "출력은 아래 형식의 JSON 객체 하나뿐이어야 합니다: "
                  "{\"problems\": [{\"title\": \"...\", \"statement\": \"...\", \"type\": \"...\", "
                  "\"why_open\": \"...\", \"evidence\": [\"E1\"]}]}\n"
                  "type은 " + ", ".join(GAP_TYPES) + " 중 하나입니다.\n"
                  "evidence에는 주어진 E 키만 씁니다. 근거가 없는 문제는 만들지 않습니다.\n"
                  "'후보'로 표현하고 확정된 사실처럼 쓰지 않습니다. 한국어로 씁니다.")
METHOD_SYSTEM = ("당신은 연구 문제마다 방법 개선안을 설계하는 연구자입니다.\n"
                 "출력은 아래 형식의 JSON 객체 하나뿐이어야 합니다: "
                 "{\"methods\": [{\"problem_index\": 0, \"title\": \"...\", \"idea\": \"...\", "
                 "\"expected_gain\": \"...\", \"risks\": \"...\", \"evidence\": [\"E1\"]}]}\n"
                 "problem_index는 대상 목록에 있는 번호만 씁니다. 개선안은 검증할 가설로 쓰고 결과를 단정하지 않습니다.\n"
                 "evidence에는 주어진 E 키만 씁니다. 한국어로 씁니다.")
CONTRIBUTION_SYSTEM = ("당신은 연구 기여 문장의 초안을 쓰는 도우미입니다.\n"
                       "출력은 아래 형식의 JSON 객체 하나뿐이어야 합니다: "
                       "{\"contributions\": [{\"statement\": \"...\", \"search_query\": \"...\"}]}\n"
                       "최대 3개입니다. statement는 한국어로, 가능한 기여의 형태만 씁니다. "
                       "참신하거나 우수하다고 주장하지 않습니다.\n"
                       "search_query는 가장 가까운 선행 연구를 찾기 위한 영어 키워드이며 12단어 이내입니다.")
CRITIQUE_SYSTEM = ("당신은 독립 점검자입니다. 작성자의 초안에서 근거로 확인할 수 있는 약점을 찾습니다. "
                   "작성자가 같은 모델일 수 있으므로 칭찬하지 않습니다. 참신성이나 우수성을 판정하지 않으며 점수를 매기지 않습니다.\n"
                   "출력은 아래 형식의 JSON 객체 하나뿐이어야 합니다: "
                   "{\"weaknesses\": [{\"text\": \"...\", \"refs\": [\"P1\", \"E2\"]}], \"next_queries\": [\"...\"]}\n"
                   "refs에는 주어진 키(P, M, C, E 번호)를 하나 이상 씁니다. 연결할 키를 댈 수 없는 약점은 쓰지 않습니다.\n"
                   "next_queries는 영어 검색어 0~5개입니다. 약점 문장은 한국어로 씁니다.")


# ---- request models -------------------------------------------------------

class ThreadCreate(BaseModel):
    title: str = Field(default="", max_length=200)
    mode: str = Field(max_length=20)
    project_id: Optional[str] = Field(default=None, max_length=100)
    paper_ids: List[str] = Field(default_factory=list, max_length=50)
    gap_ids: List[str] = Field(default_factory=list, max_length=50)


class ThreadUpdate(BaseModel):
    title: Optional[str] = Field(default=None, max_length=200)
    paper_ids: Optional[List[str]] = Field(default=None, max_length=50)
    gap_ids: Optional[List[str]] = Field(default=None, max_length=50)


class ChatPreviewIn(BaseModel):
    content: str = Field(min_length=1, max_length=CONTENT_MAX)


class ChatSendIn(ChatPreviewIn):
    preview_hash: Optional[str] = None


class ToIdeaIn(BaseModel):
    project_id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=500)


class RunConfigIn(BaseModel):
    topic: str = Field(min_length=1, max_length=300)
    project_id: Optional[str] = Field(default=None, max_length=100)
    seed_paper_ids: List[str] = Field(default_factory=list, max_length=10)
    max_iterations: int = Field(default=2, ge=1, le=3)
    papers_per_iteration: int = Field(default=6, ge=3, le=10)
    max_llm_calls: int = Field(default=40, ge=1, le=200)
    max_run_minutes: int = Field(default=45, ge=5, le=240)


class RunCreateIn(RunConfigIn):
    preview_hash: Optional[str] = None


class FeedbackIn(BaseModel):
    note: str = Field(default="", max_length=2000)
    focus_problem: Optional[int] = Field(default=None, ge=0, le=1000)


class SaveIn(BaseModel):
    project_id: str = Field(min_length=1, max_length=100)
    problems: List[int] = Field(default_factory=list, max_length=50)
    contributions: List[int] = Field(default_factory=list, max_length=50)


# ---- shared helpers -------------------------------------------------------

def _dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _canon_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _unique(values) -> List[str]:
    out: List[str] = []
    for value in values:
        if value and value not in out:
            out.append(value)
    return out


def _line(value: Any, limit: int) -> str:
    """Normalize one model-produced line. Non-strings become empty."""
    if not isinstance(value, str):
        return ""
    return " ".join(value.split())[:limit]


def _norm(text: str) -> str:
    return " ".join(str(text).lower().split())


def _clean_list(values, limit: int, max_len: int) -> List[str]:
    out: List[str] = []
    seen = set()
    for value in values:
        text = _line(value, max_len)
        key = _norm(text)
        if not text or key in seen:
            continue
        seen.add(key)
        out.append(text)
        if len(out) >= limit:
            break
    return out


def _str_items(value: Any) -> List[str]:
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def _as_index(value: Any) -> Optional[int]:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _terms(text: str) -> set:
    return {t for t in re.findall(r"[0-9a-z가-힣]{2,}", str(text).lower()) if t not in STOPWORDS}


def _sentences(text: str) -> List[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def _dedupe_key(doi: Any, title: Any) -> str:
    value = str(doi or "").lower().strip()
    value = re.sub(r"^https?://(dx\.)?doi\.org/", "", value)
    if value:
        return "doi:" + value
    compact = re.sub(r"[^0-9a-z가-힣]", "", str(title or "").lower())
    return "title:" + compact if compact else ""


def _error_text(exc: BaseException) -> str:
    if isinstance(exc, llm.LLMError):
        return exc.message
    text = str(exc).strip()
    return text[:300] or type(exc).__name__


def _conflict(message: str) -> HTTPException:
    return HTTPException(409, {"code": "preview_mismatch", "message": message})


def _system(text: str) -> str:
    return text + "\n" + llm.UNTRUSTED_RULE


def _budget() -> int:
    return int(llm.get_config()["max_input_chars"])


def _fit(items: list, render: Callable[[Any], str], budget: int) -> list:
    """Keep items in order while their rendered size fits; the first item is always kept."""
    out: list = []
    used = 0
    for item in items:
        size = len(render(item))
        if out and used + size > budget:
            break
        out.append(item)
        used += size
    return out


def _require_project(con, project_id: str) -> None:
    if not con.execute("SELECT 1 FROM projects WHERE id=? AND id NOT IN (SELECT project_id FROM project_trash)",
                       (project_id,)).fetchone():
        raise HTTPException(404, "프로젝트를 찾을 수 없습니다.")


def _paper_row(con, paper_id: str):
    return con.execute("SELECT * FROM papers WHERE id=? AND deleted_at IS NULL", (paper_id,)).fetchone()


def _latest_profile(con, paper_id: str) -> Dict[str, Any]:
    row = con.execute("SELECT profile_json FROM paper_profiles WHERE paper_id=? "
                      "ORDER BY created_at DESC, rowid DESC LIMIT 1", (paper_id,)).fetchone()
    if row is None:
        return {}
    try:
        data = json.loads(row["profile_json"])
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def _profile_digest(profile: Dict[str, Any]) -> Dict[str, str]:
    """Summary plus the first facet texts only. Quotes are never included."""
    facets = profile.get("facets") if isinstance(profile.get("facets"), dict) else {}

    def joined(name: str) -> str:
        items = facets.get(name) if isinstance(facets.get(name), list) else []
        texts = [item["text"].strip() for item in items
                 if isinstance(item, dict) and isinstance(item.get("text"), str) and item["text"].strip()]
        return "; ".join(texts[:3])[:PROFILE_CARD_CHARS]

    summary = profile.get("summary") if isinstance(profile.get("summary"), str) else ""
    return {"summary": summary[:600], "problem": joined("problem"), "method": joined("method"),
            "limitations": joined("limitations")}


# ---- chat -----------------------------------------------------------------

def _thread_view(row, messages: Optional[list] = None) -> Dict[str, Any]:
    context = json.loads(row["context_json"] or "{}")
    item = {"id": row["id"], "project_id": row["project_id"], "title": row["title"], "mode": row["mode"],
            "paper_ids": context.get("paper_ids", []), "gap_ids": context.get("gap_ids", []),
            "created_at": row["created_at"], "updated_at": row["updated_at"]}
    if messages is not None:
        item["messages"] = messages
    return item


def _message_view(row) -> Dict[str, Any]:
    return {"id": row["id"], "role": row["role"], "content": row["content"],
            "meta": json.loads(row["meta_json"] or "{}"), "created_at": row["created_at"]}


def _load_thread(con, thread_id: str):
    row = con.execute("SELECT * FROM chat_threads WHERE id=? AND (project_id IS NULL OR project_id NOT IN "
                      "(SELECT project_id FROM project_trash))", (thread_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "대화를 찾을 수 없습니다.")
    return row


def _check_refs(con, paper_ids: List[str], gap_ids: List[str], project_id: Optional[str]) -> None:
    for paper_id in paper_ids:
        if _paper_row(con, paper_id) is None:
            raise HTTPException(422, "참고 논문을 찾을 수 없습니다.")
    for gap_id in gap_ids:
        row = con.execute("SELECT project_id FROM research_gaps WHERE id=?", (gap_id,)).fetchone()
        if row is None or (row["project_id"] is not None and row["project_id"] != project_id):
            raise HTTPException(422, "갭을 찾을 수 없거나 이 프로젝트의 갭이 아닙니다.")


def _clean_content(text: str) -> str:
    content = (text or "").strip()
    if not content:
        raise HTTPException(422, "메시지를 입력해 주세요.")
    return content


def _chat_cards(con, context: Dict[str, Any]):
    papers: List[Dict[str, Any]] = []
    for paper_id in context.get("paper_ids", []):
        row = _paper_row(con, paper_id)
        if row is None:
            continue
        papers.append({"key": "P%d" % (len(papers) + 1), "title": row["title"], "year": row["year"],
                       "abstract": row["abstract"] or "", **_profile_digest(_latest_profile(con, paper_id))})
    gaps: List[Dict[str, Any]] = []
    for gap_id in context.get("gap_ids", []):
        row = con.execute("SELECT title, description, gap_type FROM research_gaps WHERE id=?", (gap_id,)).fetchone()
        if row is None:
            continue
        gaps.append({"key": "G%d" % (len(gaps) + 1), "title": row["title"],
                     "description": row["description"] or "", "gap_type": row["gap_type"]})
    return papers, gaps


def _paper_body(card: Dict[str, Any], limit: int, with_profile: bool) -> str:
    lines = ["제목: " + card["title"], "연도: " + (str(card["year"]) if card["year"] else "미상")]
    if limit and card["abstract"]:
        lines.append("초록: " + card["abstract"][:limit])
    if with_profile:
        if card["summary"]:
            lines.append("정리 요약: " + card["summary"])
        for label, field in (("문제", "problem"), ("방법", "method"), ("한계", "limitations")):
            if card[field]:
                lines.append(label + ": " + card[field])
    return "\n".join(lines)


def _gap_body(card: Dict[str, Any]) -> str:
    return "\n".join(["제목: " + card["title"], "유형: " + card["gap_type"],
                      "설명: " + card["description"][:1000]])


def _chat_user_text(papers, gaps, limit: int, with_profile: bool, content: str) -> str:
    parts = []
    if papers:
        parts.append("[논문 카드]\n" + "\n\n".join(
            llm.untrusted_block(p["key"], _paper_body(p, limit, with_profile)) for p in papers))
    if gaps:
        parts.append("[갭 카드]\n" + "\n\n".join(llm.untrusted_block(g["key"], _gap_body(g)) for g in gaps))
    parts.append("[연구자 질문]\n" + content)
    return "\n\n".join(parts)


def _compose_chat(mode: str, papers, gaps, history: List[Dict[str, str]], content: str,
                  budget: int) -> List[Dict[str, str]]:
    system = "\n".join([MODE_INSTRUCTIONS[mode], llm.UNTRUSTED_RULE, CITATION_RULE])
    user = None
    # Trim abstracts first, then profile lines. History is dropped last, oldest first.
    for with_profile in (True, False):
        for limit in ABSTRACT_LIMITS:
            text = _chat_user_text(papers, gaps, limit, with_profile, content)
            if len(system) + len(text) <= budget:
                user = text
                break
        if user is not None:
            break
    if user is None:
        raise ValueError("입력이 AI 최대 입력 길이를 넘습니다. 질문이나 참고 논문을 줄여 주세요.")
    used = len(system) + len(user)
    kept: List[Dict[str, str]] = []
    for message in reversed(history):
        if used + len(message["content"]) > budget:
            break
        kept.append(message)
        used += len(message["content"])
    return ([{"role": "system", "content": system}] + list(reversed(kept))
            + [{"role": "user", "content": user}])


def _prepare_chat(thread_id: str, content: str, budget: int) -> Dict[str, Any]:
    with storage.transaction() as con:
        row = _load_thread(con, thread_id)
        papers, gaps = _chat_cards(con, json.loads(row["context_json"] or "{}"))
        rows = con.execute("SELECT role, content FROM chat_messages WHERE thread_id=? ORDER BY id DESC LIMIT ?",
                           (thread_id, HISTORY_LIMIT)).fetchall()
        history = [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]
        mode = row["mode"]
    messages = _compose_chat(mode, papers, gaps, history, content, budget)
    return {"messages": messages, "keys": [p["key"] for p in papers] + [g["key"] for g in gaps]}


@router.get("/api/chat/threads")
def list_chat_threads(project_id: Optional[str] = None):
    with storage.transaction() as con:
        if project_id:
            _require_project(con, project_id)
            rows = con.execute("SELECT * FROM chat_threads WHERE project_id=? ORDER BY updated_at DESC, rowid DESC",
                               (project_id,)).fetchall()
        else:
            rows = con.execute("SELECT * FROM chat_threads WHERE project_id IS NULL "
                               "ORDER BY updated_at DESC, rowid DESC").fetchall()
        return [_thread_view(r) for r in rows]


@router.post("/api/chat/threads", status_code=201)
def create_chat_thread(payload: ThreadCreate):
    if payload.mode not in MODES:
        raise HTTPException(422, "대화 모드가 올바르지 않습니다.")
    title = payload.title.strip() or DEFAULT_TITLES[payload.mode]
    project_id = payload.project_id or None
    paper_ids = _unique(payload.paper_ids)
    gap_ids = _unique(payload.gap_ids)
    with storage.transaction() as con:
        if project_id:
            _require_project(con, project_id)
        _check_refs(con, paper_ids, gap_ids, project_id)
        thread_id = storage.new_id()
        con.execute("INSERT INTO chat_threads(id,project_id,title,mode,context_json) VALUES(?,?,?,?,?)",
                    (thread_id, project_id, title, payload.mode,
                     _dumps({"paper_ids": paper_ids, "gap_ids": gap_ids})))
        return _thread_view(_load_thread(con, thread_id))


@router.get("/api/chat/threads/{thread_id}")
def get_chat_thread(thread_id: str):
    with storage.transaction() as con:
        row = _load_thread(con, thread_id)
        messages = [_message_view(m) for m in con.execute(
            "SELECT id, role, content, meta_json, created_at FROM chat_messages WHERE thread_id=? ORDER BY id",
            (thread_id,))]
        return _thread_view(row, messages)


@router.patch("/api/chat/threads/{thread_id}")
def update_chat_thread(thread_id: str, payload: ThreadUpdate):
    with storage.transaction() as con:
        row = _load_thread(con, thread_id)
        context = json.loads(row["context_json"] or "{}")
        title = row["title"]
        if payload.title is not None:
            title = payload.title.strip()
            if not title:
                raise HTTPException(422, "제목을 입력해 주세요.")
        paper_ids = _unique(payload.paper_ids) if payload.paper_ids is not None else context.get("paper_ids", [])
        gap_ids = _unique(payload.gap_ids) if payload.gap_ids is not None else context.get("gap_ids", [])
        if payload.paper_ids is not None or payload.gap_ids is not None:
            _check_refs(con, paper_ids, gap_ids, row["project_id"])
        con.execute("UPDATE chat_threads SET title=?, context_json=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    (title, _dumps({"paper_ids": paper_ids, "gap_ids": gap_ids}), thread_id))
        return _thread_view(_load_thread(con, thread_id))


@router.delete("/api/chat/threads/{thread_id}", status_code=204)
def delete_chat_thread(thread_id: str):
    with storage.transaction() as con:
        if not con.execute("DELETE FROM chat_threads WHERE id=?", (thread_id,)).rowcount:
            raise HTTPException(404, "대화를 찾을 수 없습니다.")
    return Response(status_code=204)


@router.post("/api/chat/threads/{thread_id}/preview")
def preview_chat_message(thread_id: str, payload: ChatPreviewIn):
    content = _clean_content(payload.content)
    prepared = run_llm(lambda: _prepare_chat(thread_id, content, _budget()))
    return run_llm(lambda: llm.preview(prepared["messages"], purpose=CHAT_PURPOSE))


@router.post("/api/chat/threads/{thread_id}/messages", status_code=201)
def send_chat_message(thread_id: str, payload: ChatSendIn):
    content = _clean_content(payload.content)
    prepared = run_llm(lambda: _prepare_chat(thread_id, content, _budget()))
    messages = prepared["messages"]
    shown = run_llm(lambda: llm.preview(messages, purpose=CHAT_PURPOSE))
    # A supplied hash must match what is sent now. Remote providers also require one (llm.complete enforces it).
    if payload.preview_hash is not None and payload.preview_hash != shown["preview_hash"]:
        raise _conflict("보낼 내용이 미리보기와 다릅니다. 다시 미리보기를 확인해 주세요.")
    result = run_llm(lambda: llm.complete(messages, purpose=CHAT_PURPOSE, preview_hash=payload.preview_hash))
    text = result["text"]
    valid = set(prepared["keys"])
    cited = _unique(re.findall(r"\[([PG]\d+)\]", text))
    meta = {"model": result["model"], "provider": result["provider"],
            "refs": [k for k in cited if k in valid], "unknown_refs": [k for k in cited if k not in valid]}
    with storage.transaction() as con:
        _load_thread(con, thread_id)
        con.execute("INSERT INTO chat_messages(thread_id,role,content,meta_json) VALUES(?,?,?,?)",
                    (thread_id, "user", content, "{}"))
        cursor = con.execute("INSERT INTO chat_messages(thread_id,role,content,meta_json) VALUES(?,?,?,?)",
                             (thread_id, "assistant", text, _dumps(meta)))
        con.execute("UPDATE chat_threads SET updated_at=CURRENT_TIMESTAMP WHERE id=?", (thread_id,))
        row = con.execute("SELECT id, role, content, meta_json, created_at FROM chat_messages WHERE id=?",
                          (cursor.lastrowid,)).fetchone()
        return _message_view(row)


@router.post("/api/chat/messages/{message_id}/to-idea", status_code=201)
def chat_message_to_idea(message_id: int, payload: ToIdeaIn):
    title = payload.title.strip()
    if not title:
        raise HTTPException(422, "제목을 입력해 주세요.")
    with storage.transaction() as con:
        message = con.execute("SELECT * FROM chat_messages WHERE id=?", (message_id,)).fetchone()
        if message is None:
            raise HTTPException(404, "메시지를 찾을 수 없습니다.")
        _load_thread(con, message["thread_id"])
        if message["role"] != "assistant":
            raise HTTPException(422, "AI 답변만 아이디어로 바꿀 수 있습니다.")
        _require_project(con, payload.project_id)
        idea_id = storage.new_id()
        con.execute("INSERT INTO ideas(id,project_id,title,description) VALUES(?,?,?,?)",
                    (idea_id, payload.project_id, title, message["content"]))
        row = con.execute("SELECT * FROM ideas WHERE id=?", (idea_id,)).fetchone()
        item = dict(row)
        item["evidence_ids"] = []
        return item


# ---- research loop: configuration and prompts -----------------------------

def _run_config(payload: RunConfigIn) -> Dict[str, Any]:
    topic = payload.topic.strip()
    if not topic:
        raise HTTPException(422, "주제를 입력해 주세요.")
    return {"topic": topic, "project_id": payload.project_id or None,
            "seed_paper_ids": _unique(payload.seed_paper_ids),
            "max_iterations": payload.max_iterations, "papers_per_iteration": payload.papers_per_iteration,
            "max_llm_calls": payload.max_llm_calls, "max_run_seconds": payload.max_run_minutes * 60}


def _max_seconds(cfg: Dict[str, Any]) -> int:
    return int(cfg.get("max_run_seconds") or DEFAULT_MAX_RUN_SECONDS)


def _seed_snapshot(con, seed_ids: List[str]) -> List[Dict[str, Any]]:
    snapshot: List[Dict[str, Any]] = []
    for paper_id in seed_ids:
        row = _paper_row(con, paper_id)
        if row is None:
            raise HTTPException(422, "시드 논문을 찾을 수 없습니다.")
        digest = _profile_digest(_latest_profile(con, paper_id))
        snapshot.append({"key": "Seed%d" % (len(snapshot) + 1), "paper_id": paper_id, "title": row["title"],
                         "year": row["year"], "doi": row["doi"], "url": row["source_url"],
                         "abstract": (row["abstract"] or "")[:1500], "summary": digest["summary"]})
    return snapshot


def _seed_block(seed: Dict[str, Any]) -> str:
    body = "\n".join(["제목: " + str(seed["title"]), "연도: " + (str(seed["year"]) if seed["year"] else "미상"),
                      "초록: " + seed["abstract"][:800], "정리 요약: " + seed["summary"]])
    return llm.untrusted_block(seed["key"], body)


def _evidence_block(evidence: Dict[str, Any]) -> str:
    body = "출처: %s (%s) %s\n발췌: %s" % (evidence["title"], evidence["year"] or "미상",
                                       evidence["doi"] or "", evidence["quote"])
    return llm.untrusted_block(evidence["key"], body)


def _plan_messages(topic: str, seeds, iteration: int, carry: Optional[Dict[str, Any]],
                   budget: int) -> List[Dict[str, str]]:
    shown = _fit(seeds, _seed_block, max(1, budget // 2))
    parts = ["연구 주제: " + topic]
    if shown:
        parts.append("[선택한 시드 논문]\n" + "\n\n".join(_seed_block(s) for s in shown))
    if carry:
        if carry.get("weaknesses"):
            parts.append("이전 반복의 약점: " + "; ".join(carry["weaknesses"]))
        if carry.get("next_queries"):
            parts.append("우선 검토할 검색어 후보: " + "; ".join(carry["next_queries"]))
        if carry.get("note"):
            parts.append("연구자 피드백: " + carry["note"])
    parts.append("반복 번호: %d" % iteration)
    return [{"role": "system", "content": _system(PLAN_SYSTEM)},
            {"role": "user", "content": "\n\n".join(parts)}]


def _carry_lines(carry: Optional[Dict[str, Any]]) -> List[str]:
    lines = []
    if carry:
        if carry.get("weaknesses"):
            lines.append("이전 반복의 약점: " + "; ".join(carry["weaknesses"]))
        if carry.get("focus_title"):
            lines.append("연구자가 중점을 둔 문제: " + carry["focus_title"])
        if carry.get("note"):
            lines.append("연구자 피드백: " + carry["note"])
    return lines


def _problem_messages(topic: str, carry, cards) -> List[Dict[str, str]]:
    parts = ["연구 주제: " + topic] + _carry_lines(carry)
    parts.append("[근거 카드]\n" + "\n\n".join(_evidence_block(c) for c in cards))
    return [{"role": "system", "content": _system(PROBLEM_SYSTEM)}, {"role": "user", "content": "\n\n".join(parts)}]


def _problem_lines(problems) -> str:
    return "\n".join("(%d) %s\n문제: %s\n왜 열려 있는가: %s\n근거: %s" % (
        p["index"], p["title"], p["statement"], p["why_open"], ", ".join(p["evidence"])) for p in problems)


def _method_messages(topic: str, problems, cards) -> List[Dict[str, str]]:
    parts = ["연구 주제: " + topic, "[대상 문제]\n" + _problem_lines(problems),
             "[근거 카드]\n" + "\n\n".join(_evidence_block(c) for c in cards)]
    return [{"role": "system", "content": _system(METHOD_SYSTEM)}, {"role": "user", "content": "\n\n".join(parts)}]


def _method_lines(methods) -> str:
    return "\n".join("- (문제 %d) %s: %s" % (m["problem_index"], m["title"], m["idea"]) for m in methods)


def _contribution_messages(topic: str, problems, methods) -> List[Dict[str, str]]:
    parts = ["연구 주제: " + topic, "[대상 문제]\n" + _problem_lines(problems)]
    if methods:
        parts.append("[방법 초안]\n" + _method_lines(methods))
    return [{"role": "system", "content": _system(CONTRIBUTION_SYSTEM)}, {"role": "user", "content": "\n\n".join(parts)}]


def _critique_problem_lines(problems) -> str:
    return "\n".join("P%d. %s\n문제: %s\n왜 열려 있는가: %s\n근거: %s" % (
        i + 1, p["title"], p["statement"], p["why_open"], ", ".join(p["evidence"]))
        for i, p in enumerate(problems))


def _critique_contribution(number: int, contribution: Dict[str, Any]) -> str:
    listing = "\n".join("- %s (%s)" % (p["title"], p["year"] or "미상")
                        for p in contribution.get("closest_prior") or []) or "(없음)"
    block = llm.untrusted_block("C%d 선행 연구" % number,
                                "검색어: %s\n%s" % (contribution.get("search_query") or "", listing))
    return "C%d. %s\n%s" % (number, contribution["statement"], block)


def _critique_messages(topic: str, problems, methods, contributions, cards) -> List[Dict[str, str]]:
    parts = ["연구 주제: " + topic, "[문제 후보]\n" + _critique_problem_lines(problems)]
    if methods:
        parts.append("[방법 초안]\n" + "\n".join(
            "M%d (P%d 대상). %s: %s" % (j + 1, m["problem_index"] + 1, m["title"], m["idea"])
            for j, m in enumerate(methods)))
    if contributions:
        parts.append("[기여 초안]\n" + "\n\n".join(
            _critique_contribution(n + 1, c) for n, c in enumerate(contributions)))
    parts.append("[근거 카드]\n" + "\n\n".join(_evidence_block(c) for c in cards))
    return [{"role": "system", "content": _system(CRITIQUE_SYSTEM)}, {"role": "user", "content": "\n\n".join(parts)}]


def _policy_text(first: Dict[str, Any], seed_count: int) -> str:
    where = ("외부 서버(%s)로 전송됩니다" % first["host"]) if first["external"] \
        else ("이 PC의 로컬 서버(%s)로만 전송됩니다" % first["host"])
    return ("보내는 내용: 연구 주제, 검색어, 공개 학술 검색(OpenAlex)에서 받은 논문의 제목·연도·초록, "
            "선택한 시드 논문(%d편)의 제목·연도·초록·정리 요약, 연구자가 입력한 피드백, "
            "앞 단계에서 만든 문제·방법·기여 초안과 근거 발췌(공개 초록 문장). "
            "보내지 않는 내용: 개인 메모, 발췌 메모, 다른 채팅과 다른 연구 실행의 내용, 원본 PDF 전문. "
            "%s. 승인하면 이 실행의 모든 AI 단계가 이 범위 안에서 전송되며, 단계마다 실제로 보낸 프롬프트의 해시를 "
            "단계 기록에 남깁니다." % (seed_count, where))


def _prepare_run(payload: RunConfigIn) -> Dict[str, Any]:
    cfg = _run_config(payload)
    with storage.transaction() as con:
        if cfg["project_id"]:
            _require_project(con, cfg["project_id"])
        snapshot = _seed_snapshot(con, cfg["seed_paper_ids"])
    messages = _plan_messages(cfg["topic"], snapshot, 1, None, _budget())
    first = llm.preview(messages, purpose=PLAN_PURPOSE, json_output=True)
    preview_hash = _canon_hash({"config": cfg, "first_prompt": first["preview_hash"]})
    return {"config": cfg, "snapshot": snapshot, "first": first, "preview_hash": preview_hash,
            "policy": _policy_text(first, len(snapshot))}


def _initial_state(snapshot, approved_hash: str) -> Dict[str, Any]:
    return {"iteration": 1, "stage_index": 0, "queries": [], "used_queries": [], "candidates": [],
            "evidence": [], "problems": [], "methods": [], "contributions": [], "critique": None,
            "carry": None, "history": [], "llm_calls": 0, "elapsed_seconds": 0, "seed_snapshot": snapshot,
            "approved_hash": approved_hash}


# ---- research loop: stage functions ---------------------------------------

def _obj(props: Dict[str, Any]) -> Dict[str, Any]:
    return {"type": "object", "properties": props, "required": list(props)}


_STR = {"type": "string"}
_STRS = {"type": "array", "items": _STR}
# JSON Schemas that constrain output shape where supported (Ollama structured
# outputs). The app still validates every field after the call.
STAGE_SCHEMAS = {
    PLAN_PURPOSE: _obj({"queries": _STRS}),
    PROBLEM_PURPOSE: _obj({"problems": {"type": "array", "items": _obj({
        "title": _STR, "statement": _STR, "type": {"type": "string", "enum": list(GAP_TYPES)},
        "why_open": _STR, "evidence": _STRS})}}),
    METHOD_PURPOSE: _obj({"methods": {"type": "array", "items": _obj({
        "problem_index": {"type": "integer"}, "title": _STR, "idea": _STR, "expected_gain": _STR,
        "risks": _STR, "evidence": _STRS})}}),
    CONTRIBUTION_PURPOSE: _obj({"contributions": {"type": "array", "items": _obj({
        "statement": _STR, "search_query": _STR})}}),
    CRITIQUE_PURPOSE: _obj({"weaknesses": {"type": "array", "items": _obj({"text": _STR, "refs": _STRS})},
                            "next_queries": _STRS}),
}


def _require_list(key: str, message: str) -> Callable[[Dict[str, Any]], None]:
    def check(data: Dict[str, Any]) -> None:
        if not isinstance(data.get(key), list):
            raise ValueError(message)
    return check


def _transient(exc: llm.LLMError) -> bool:
    if exc.code in TRANSIENT_CODES:
        return True
    return exc.code == "http_error" and (exc.status or 0) >= 500


def _backoff_seconds() -> float:
    return random.uniform(2.0, 5.0)


def _replay_lookup(run_id: str, iteration: int, stage: str, current_step_id: int,
                   prompt_hash: str) -> Optional[Tuple[str, int]]:
    """Reuse the raw response of an interrupted step for the same iteration and stage, if it is safe."""
    with storage.transaction() as con:
        row = con.execute("SELECT id, status, error, prompt_hash, output_json FROM research_steps "
                          "WHERE run_id=? AND iteration=? AND stage=? AND id<>? ORDER BY id DESC LIMIT 1",
                          (run_id, iteration, stage, current_step_id)).fetchone()
    if row is None:
        return None
    if row["status"] != "failed" or row["error"] != INTERRUPTED_ERROR or row["prompt_hash"] != prompt_hash:
        return None
    output = json.loads(row["output_json"] or "{}")
    raw = output.get("raw_response")
    if not isinstance(raw, str) or not raw.strip() or output.get("raw_truncated"):
        return None
    return raw, row["id"]


class _StopRun(Exception):
    """Stops the current step. reason is "cancelled", "time" or "calls"."""

    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason, self.message = reason, message


class _StepContext:
    """One stage attempt. Counts every LLM call in state and records the hash of the exact prompt."""

    def __init__(self, run_id: str, step_id: int, stage: str, state: Dict[str, Any], cfg: Dict[str, Any],
                 cancel: threading.Event, started: float):
        self.run_id, self.step_id, self.stage = run_id, step_id, stage
        self.state, self.cfg, self.cancel, self.started = state, cfg, cancel, started
        self.max_seconds = _max_seconds(cfg)
        self.max_calls = int(cfg["max_llm_calls"])
        self.model: Optional[str] = None
        self.prompt_hash: Optional[str] = None
        self.attempts: List[Dict[str, Any]] = []
        self.raw: Optional[str] = None
        self.raw_truncated = False
        self.stats: Optional[Dict[str, Any]] = None
        self.runtime: Optional[Dict[str, Any]] = None
        self.runtime_probed = False
        self.replayed_from: Optional[int] = None
        self.stop_kind: Optional[str] = None
        self.calls = 0

    def should_stop(self) -> Optional[str]:
        if self.cancel.is_set():
            self.stop_kind = "cancelled"
            return CANCELLED_ERROR
        elapsed = float(self.state.get("elapsed_seconds", 0)) + (time.monotonic() - self.started)
        if elapsed >= self.max_seconds:
            self.stop_kind = "time"
            return BUDGET_MESSAGES["time"]
        return None

    def check_stop(self) -> None:
        reason = self.should_stop()
        if reason:
            raise _StopRun(self.stop_kind or "cancelled", reason)

    def ask(self, messages: List[Dict[str, str]], purpose: str, max_tokens: int = 2000,
            validate: Optional[Callable[[Dict[str, Any]], None]] = None) -> Dict[str, Any]:
        current = list(messages)
        retried = reasked = False
        replay_checked = False
        while True:
            self.check_stop()
            shown = llm.preview(current, purpose=purpose, json_output=True)
            if self.prompt_hash is None:
                self.prompt_hash = shown["preview_hash"]
            text: Optional[str] = None
            replayed = False
            if not replay_checked:
                replay_checked = True
                found = _replay_lookup(self.run_id, self.state["iteration"], self.stage, self.step_id,
                                       self.prompt_hash)
                if found is not None:
                    text, self.replayed_from = found
                    replayed = True
            if text is None:
                if int(self.state.get("llm_calls", 0)) >= self.max_calls:
                    raise _StopRun("calls", BUDGET_MESSAGES["calls"])
                self.state["llm_calls"] = int(self.state.get("llm_calls", 0)) + 1
                self.calls += 1
                try:
                    result = llm.complete(current, purpose=purpose, preview_hash=shown["preview_hash"],
                                          json_output=True, max_tokens=max_tokens,
                                          schema=STAGE_SCHEMAS.get(purpose), should_stop=self.should_stop)
                except llm.LLMError as exc:
                    self.attempts.append({"error": exc.code, "status": exc.status})
                    if exc.code == "stopped":
                        raise _StopRun(self.stop_kind or "cancelled", exc.message)
                    if _transient(exc) and not retried:
                        retried = True
                        if self.cancel.wait(_backoff_seconds()):
                            raise _StopRun("cancelled", CANCELLED_ERROR)
                        continue
                    raise
                text = result["text"]
                self.model = result.get("model") or self.model
                self.stats = result.get("stats")
            self._record_raw(text)
            if not replayed and not self.runtime_probed:
                self._probe_runtime()
            try:
                data = llm.parse_json(text)
                if not isinstance(data, dict):
                    raise ValueError("AI 응답이 JSON 객체가 아닙니다.")
                if validate is not None:
                    validate(data)
            except (llm.LLMError, ValueError) as exc:
                reason = exc.message if isinstance(exc, llm.LLMError) else str(exc)
                self.attempts.append({"error": "invalid_output", "reason": reason[:200]})
                if reasked:
                    raise ValueError(reason)
                reasked = True
                current = list(messages) + [
                    {"role": "assistant", "content": text[:4000]},
                    {"role": "user", "content": "이전 응답은 다음 이유로 사용할 수 없습니다: " + reason
                     + "\n시스템 지시의 JSON 형식을 지켜 JSON 객체 하나만 다시 출력하세요."},
                ]
                continue
            self.attempts.append({"ok": True, "replayed": True} if replayed else {"ok": True})
            return data

    def _record_raw(self, text: str) -> None:
        """Save the raw response before it is parsed, so a failure or restart keeps it."""
        self.raw = text[:MAX_RAW_CHARS]
        self.raw_truncated = len(text) > MAX_RAW_CHARS
        output = {"raw_response": self.raw, "raw_truncated": self.raw_truncated, "attempt": self.calls}
        with storage.transaction() as con:
            con.execute("UPDATE research_steps SET output_json=?, prompt_hash=?, model=? WHERE id=?",
                        (_dumps(output), self.prompt_hash, self.model, self.step_id))

    def _probe_runtime(self) -> None:
        self.runtime_probed = True
        try:
            status = llm.runtime_status()
        except Exception:  # a probe problem must not fail the stage
            status = {"applicable": False}
        warning = None
        if status.get("applicable") and status.get("reachable"):
            self.runtime = {"gpu_percent": status.get("configured_gpu_percent"), "warning": status.get("warning")}
            warning = status.get("warning")
        else:
            self.runtime = None
        if warning:
            self.state["last_runtime_warning"] = warning
        else:
            self.state.pop("last_runtime_warning", None)

    def failure_output(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {"raw_truncated": self.raw_truncated, "attempts": list(self.attempts)}
        if self.raw is not None:
            out["raw_response"] = self.raw
        return out

    def success_meta(self) -> Dict[str, Any]:
        meta = {"attempts": list(self.attempts), "stats": self.stats, "runtime": self.runtime,
                "replayed_from_step": self.replayed_from}
        return {key: value for key, value in meta.items() if value is not None}


def _targets(state: Dict[str, Any]) -> List[int]:
    problems = state["problems"]
    if not problems:
        return []
    focus = _norm((state.get("carry") or {}).get("focus_title") or "")
    order = list(range(len(problems)))
    if focus:
        matched = [i for i in order if _norm(problems[i]["title"]) == focus]
        order = matched + [i for i in order if i not in matched]
    return order[:3]


def _stage_plan(ctx: _StepContext, cfg: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
    carry = state.get("carry")
    messages = _plan_messages(cfg["topic"], state["seed_snapshot"], state["iteration"], carry, _budget())
    data = ctx.ask(messages, PLAN_PURPOSE)
    raw = data.get("queries")
    proposed = _clean_list(_str_items(raw), 5, 200) if isinstance(raw, list) else []
    model_fallback = False
    if not proposed:
        # Small local models sometimes return no queries. Search with the topic
        # itself (and seed titles) instead of stopping the run; this is recorded.
        model_fallback = True
        proposed = _clean_list([cfg["topic"]] + [s.get("title", "") for s in state["seed_snapshot"]], 5, 200)
    used = {_norm(q) for q in state["used_queries"]}
    fresh = [q for q in proposed if _norm(q) not in used]
    dropped = len(proposed) - len(fresh)
    fallback = False
    if not fresh:
        # Repetition guard: every proposed query was already used, so fall back to topic plus a weakness.
        fallback = True
        weak = [_line(w, 60) for w in (carry or {}).get("weaknesses", []) if _line(w, 60)] or ["limitations"]
        options = ["%s %s" % (cfg["topic"], w) for w in weak] + ["%s limitations" % cfg["topic"]]
        chosen = next((o for o in options if _norm(o) not in used), options[0])
        fresh = [_line(chosen, 200)]
    state["queries"] = fresh
    state["used_queries"] = state["used_queries"] + [q for q in fresh if _norm(q) not in used]
    return {"queries": fresh, "dropped_repeats": dropped, "fallback": fallback, "model_fallback": model_fallback}


def _stage_search(ctx: _StepContext, cfg: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
    per = cfg["papers_per_iteration"]
    seen = set()
    seed_items = []
    for seed in state["seed_snapshot"]:
        dedupe = _dedupe_key(seed["doi"], seed["title"])
        if dedupe:
            seen.add(dedupe)
        seed_items.append({"title": seed["title"], "year": seed["year"], "doi": seed["doi"],
                           "abstract": seed["abstract"], "url": seed["url"], "source": "library",
                           "source_id": seed["paper_id"]})
    pools: List[list] = []
    errors: List[Dict[str, str]] = []
    for query in state["queries"]:
        ctx.check_stop()
        try:
            pools.append(scholarly.search_openalex(query, limit=per))
        except Exception as exc:  # recorded in the step output; the stage continues with other queries
            errors.append({"query": query, "error": _error_text(exc)})
            pools.append([])
    picked: List[Dict[str, Any]] = []
    depth = max([len(pool) for pool in pools] or [0])
    for rank in range(depth):
        for pool in pools:
            if rank >= len(pool) or len(picked) >= per:
                continue
            record = pool[rank]
            dedupe = _dedupe_key(record.get("doi"), record.get("title"))
            if not dedupe or dedupe in seen:
                continue
            seen.add(dedupe)
            picked.append(record)
    if not seed_items and not picked and errors:
        raise RuntimeError("OpenAlex 검색에 실패했습니다. 잠시 후 다시 시도하세요.")
    items = seed_items + [{"title": r.get("title") or "", "year": r.get("year"), "doi": r.get("doi"),
                           "abstract": r.get("abstract") or "", "url": r.get("url"), "source": "openalex",
                           "source_id": r.get("source_id")} for r in picked]
    state["candidates"] = [dict(item, key="S%d" % (i + 1)) for i, item in enumerate(items)]
    return {"queries": len(state["queries"]), "candidates": len(state["candidates"]), "errors": errors}


def _stage_screen(ctx: _StepContext, cfg: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
    terms = _terms(cfg["topic"])
    for query in state["queries"]:
        terms |= _terms(query)
    evidence: List[Dict[str, Any]] = []
    for cand in state["candidates"]:
        abstract = cand.get("abstract") or ""
        if not abstract.strip():
            continue
        scored = []
        for position, sentence in enumerate(_sentences(abstract)):
            if not 20 <= len(sentence) <= 500 or sentence not in abstract:
                continue
            overlap = len(_terms(sentence) & terms)
            if overlap:
                scored.append((-overlap, position, sentence))
        for _, _, sentence in sorted(scored)[:3]:
            evidence.append({"key": "E%d" % (len(evidence) + 1), "source_key": cand["key"], "quote": sentence,
                             "title": cand["title"], "year": cand.get("year"), "doi": cand.get("doi"),
                             "url": cand.get("url")})
    state["evidence"] = evidence
    return {"evidence": len(evidence), "papers_with_evidence": len({e["source_key"] for e in evidence})}


PROBLEM_VALIDATE = _require_list("problems", "문제 목록(problems 배열)이 없습니다.")
METHOD_VALIDATE = _require_list("methods", "방법 목록(methods 배열)이 없습니다.")
CONTRIBUTION_VALIDATE = _require_list("contributions", "기여 목록(contributions 배열)이 없습니다.")
CRITIQUE_VALIDATE = _require_list("weaknesses", "약점 목록(weaknesses 배열)이 없습니다.")


def _stage_problems(ctx: _StepContext, cfg: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
    evidence = state["evidence"]
    if not evidence:
        state["problems"] = []
        return {"problems": 0, "skipped": "no_evidence"}
    shown = _fit(evidence, _evidence_block, int(_budget() * 0.8))
    keys = {e["key"] for e in shown}
    data = ctx.ask(_problem_messages(cfg["topic"], state.get("carry"), shown), PROBLEM_PURPOSE,
                   validate=PROBLEM_VALIDATE)
    raw = data.get("problems")
    if not isinstance(raw, list):
        raise ValueError("문제 목록을 받지 못했습니다.")
    problems: List[Dict[str, Any]] = []
    unknown = 0
    dropped = 0
    for item in raw[:8]:
        if not isinstance(item, dict):
            dropped += 1
            continue
        valid: List[str] = []
        listed = item.get("evidence") if isinstance(item.get("evidence"), list) else []
        for key in listed:
            if isinstance(key, str) and key in keys:
                if key not in valid:
                    valid.append(key)
            else:
                unknown += 1
        title = _line(item.get("title"), 200)
        if not title or not valid:
            dropped += 1
            continue
        ptype = item.get("type") if item.get("type") in GAP_TYPES else "other"
        problems.append({"index": len(problems), "title": title,
                         "statement": _line(item.get("statement"), 1000) or title, "type": ptype,
                         "why_open": _line(item.get("why_open"), 500), "evidence": valid})
    state["problems"] = problems
    return {"problems": len(problems), "dropped_unknown_evidence": unknown, "dropped_problems": dropped,
            "evidence_in_prompt": len(shown)}


def _stage_methods(ctx: _StepContext, cfg: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
    targets = _targets(state)
    if not targets:
        state["methods"] = []
        return {"methods": 0, "skipped": "no_problems"}
    problems = state["problems"]
    by_key = {e["key"]: e for e in state["evidence"]}
    needed = _unique([k for i in targets for k in problems[i]["evidence"]])
    cards = _fit([by_key[k] for k in needed if k in by_key], _evidence_block, int(_budget() * 0.8))
    shown_keys = {c["key"] for c in cards}
    data = ctx.ask(_method_messages(cfg["topic"], [problems[i] for i in targets], cards), METHOD_PURPOSE,
                   max_tokens=2500, validate=METHOD_VALIDATE)
    raw = data.get("methods")
    if not isinstance(raw, list):
        raise ValueError("방법 목록을 받지 못했습니다.")
    methods: List[Dict[str, Any]] = []
    for item in raw[:9]:
        if not isinstance(item, dict):
            continue
        index = _as_index(item.get("problem_index"))
        if index not in targets:
            continue
        listed = item.get("evidence") if isinstance(item.get("evidence"), list) else []
        valid = _unique([k for k in listed if isinstance(k, str) and k in shown_keys])
        methods.append({"problem_index": index, "title": _line(item.get("title"), 200),
                        "idea": _line(item.get("idea"), 1000), "expected_gain": _line(item.get("expected_gain"), 500),
                        "risks": _line(item.get("risks"), 500),
                        "evidence": valid or list(problems[index]["evidence"]),
                        "evidence_inherited": not valid})
    state["methods"] = methods
    return {"methods": len(methods), "targets": targets}


def _overlap_label(value: Optional[float]) -> Optional[str]:
    if value is None:
        return None
    if value >= 0.6:
        return "높음"
    if value >= 0.3:
        return "보통"
    return "낮음"


def _prior_overlap(query: str, records: List[Dict[str, Any]]) -> Optional[float]:
    """Largest share of query terms that appear in one search result's title and abstract start."""
    terms = _terms(query)
    if not records or not terms:
        return None
    best = 0.0
    for record in records:
        text = "%s %s" % (record.get("title") or "", (record.get("abstract") or "")[:600])
        best = max(best, len(terms & _terms(text)) / len(terms))
    return round(best, 2)


def _stage_contributions(ctx: _StepContext, cfg: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
    if not state["problems"]:
        state["contributions"] = []
        return {"contributions": 0, "skipped": "no_problems"}
    targets = _targets(state)
    problems = [state["problems"][i] for i in targets]
    data = ctx.ask(_contribution_messages(cfg["topic"], problems, state["methods"]), CONTRIBUTION_PURPOSE,
                   validate=CONTRIBUTION_VALIDATE)
    raw = data.get("contributions")
    if not isinstance(raw, list):
        raise ValueError("기여 목록을 받지 못했습니다.")
    drafts: List[Tuple[str, Any]] = []
    for item in raw[:3]:
        statement = _line(item.get("statement") if isinstance(item, dict) else item, 500)
        if statement and statement not in [s for s, _ in drafts]:
            drafts.append((statement, item.get("search_query") if isinstance(item, dict) else None))
    contributions: List[Dict[str, Any]] = []
    for statement, query in drafts:
        if isinstance(query, str) and 3 <= len(query.strip()) <= 200:
            search = _line(query, 200)
        else:
            search = statement[:300]
        ctx.check_stop()
        # The closest prior work is a plain search result, not a novelty verdict.
        prior: List[Dict[str, Any]] = []
        error = None
        overlap: Optional[float] = None
        try:
            records = scholarly.search_openalex(search, limit=3)[:3]
            prior = [{"title": r.get("title") or "", "year": r.get("year"), "doi": r.get("doi"), "url": r.get("url")}
                     for r in records]
            overlap = _prior_overlap(search, records)
        except Exception as exc:
            error = _error_text(exc)
            prior = []
            overlap = None
        contributions.append({"statement": statement, "search_query": search, "closest_prior": prior,
                              "prior_error": error, "prior_overlap": overlap,
                              "prior_overlap_label": _overlap_label(overlap), "note": NOVELTY_NOTE})
    state["contributions"] = contributions
    return {"contributions": len(contributions),
            "prior_search_errors": [c["prior_error"] for c in contributions if c["prior_error"]]}


def _loop_checks(state: Dict[str, Any]) -> Dict[str, Any]:
    """Structural checks computed by code. They count evidence and overlap; they do not judge the idea."""
    evidence = {e["key"]: e for e in state["evidence"]}
    seeds = {c["key"] for c in state["candidates"] if c.get("source") == "library"}
    summary = {"single_source": 0, "inherited_evidence": 0, "no_prior_found": 0,
               "prior_search_failed": 0, "high_prior_overlap": 0}
    problems_out = []
    for i, problem in enumerate(state["problems"]):
        keys = [k for k in problem["evidence"] if k in evidence]
        sources = {evidence[k]["source_key"] for k in keys}
        seed_count = sum(1 for k in keys if evidence[k]["source_key"] in seeds)
        flags = ["single_source"] if len(sources) < 2 else []
        summary["single_source"] += len(flags)
        problems_out.append({"key": "P%d" % (i + 1), "title": problem["title"],
                             "evidence_count": len(problem["evidence"]), "source_papers": len(sources),
                             "seed_evidence": seed_count, "flags": flags})
    methods_out = []
    for j, method in enumerate(state["methods"]):
        inherited = bool(method.get("evidence_inherited"))
        summary["inherited_evidence"] += int(inherited)
        methods_out.append({"key": "M%d" % (j + 1), "problem": "P%d" % (method["problem_index"] + 1),
                            "evidence_inherited": inherited, "flags": ["inherited_evidence"] if inherited else []})
    contributions_out = []
    for n, contribution in enumerate(state["contributions"]):
        prior = contribution.get("closest_prior") or []
        flags: List[str] = []
        if contribution.get("prior_error"):
            flags.append("prior_search_failed")
            summary["prior_search_failed"] += 1
        elif not prior:
            flags.append("no_prior_found")
            summary["no_prior_found"] += 1
        overlap = contribution.get("prior_overlap")
        if overlap is not None and overlap >= 0.6:
            flags.append("high_prior_overlap")
            summary["high_prior_overlap"] += 1
        contributions_out.append({"key": "C%d" % (n + 1), "search_query": contribution.get("search_query"),
                                  "closest_prior_count": len(prior), "prior_overlap": overlap,
                                  "prior_overlap_label": contribution.get("prior_overlap_label"), "flags": flags})
    return {"problems": problems_out, "methods": methods_out, "contributions": contributions_out,
            "summary": summary}


def _critique_keys(state: Dict[str, Any], shown_keys: set) -> set:
    keys = set(shown_keys)
    keys.update("P%d" % (i + 1) for i in range(len(state["problems"])))
    keys.update("M%d" % (j + 1) for j in range(len(state["methods"])))
    keys.update("C%d" % (n + 1) for n in range(len(state["contributions"])))
    return keys


def _parse_weaknesses(raw: Any, valid: set) -> Tuple[List[Dict[str, Any]], int]:
    """Keep weaknesses that cite at least one valid key. Returns (kept, dropped_uncited)."""
    kept: List[Dict[str, Any]] = []
    dropped = 0
    items = raw if isinstance(raw, list) else []
    for item in items[:16]:
        if isinstance(item, dict):
            text = _line(item.get("text"), 300)
            raw_refs = item.get("refs")
        else:
            text = _line(item, 300)
            raw_refs = None
        refs = [r for r in _unique(r.strip() for r in (raw_refs or []) if isinstance(r, str)) if r in valid]
        if not text or not refs:
            dropped += 1
            continue
        kept.append({"text": text, "refs": refs})
        if len(kept) >= 8:
            break
    return kept, dropped


def _stage_critique(ctx: _StepContext, cfg: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
    checks = _loop_checks(state)
    if not state["problems"]:
        state["critique"] = {"weaknesses": [], "next_queries": [], "checks": checks, "dropped_uncited": 0,
                             "note": "근거 기반 문제 후보가 없어 점검하지 않았습니다. " + CHECK_NOTE,
                             "skipped": "no_problems"}
        return {"skipped": "no_problems", "weaknesses": 0, "dropped_uncited": 0, "next_queries": [],
                "check_summary": checks["summary"]}
    by_key = {e["key"]: e for e in state["evidence"]}
    needed = _unique([k for p in state["problems"] for k in p["evidence"]])
    cards = _fit([by_key[k] for k in needed if k in by_key], _evidence_block, int(_budget() * 0.8))
    data = ctx.ask(_critique_messages(cfg["topic"], state["problems"], state["methods"],
                                      state["contributions"], cards), CRITIQUE_PURPOSE, max_tokens=1500,
                   validate=CRITIQUE_VALIDATE)
    valid = _critique_keys(state, {c["key"] for c in cards})
    weaknesses, dropped = _parse_weaknesses(data.get("weaknesses"), valid)
    next_queries = _clean_list(_str_items(data.get("next_queries")), 5, 200)
    state["critique"] = {"weaknesses": weaknesses, "next_queries": next_queries, "checks": checks,
                         "dropped_uncited": dropped, "note": CHECK_NOTE}
    return {"weaknesses": len(weaknesses), "dropped_uncited": dropped, "next_queries": next_queries,
            "check_summary": checks["summary"]}


STAGE_FUNCS = {"plan_queries": _stage_plan, "search": _stage_search, "screen": _stage_screen,
               "problems": _stage_problems, "methods": _stage_methods,
               "contributions": _stage_contributions, "critique": _stage_critique}


def _needs_llm(stage: str, state: Dict[str, Any]) -> bool:
    if stage == "plan_queries":
        return True
    if stage == "problems":
        return bool(state["evidence"])
    if stage in ("methods", "contributions", "critique"):
        return bool(state["problems"])
    return False


# ---- research loop: persistence and engine --------------------------------
#
# Lock order: a run lock first, then _REGISTRY_LOCK. Never the reverse.
# Run locks cover short database sections only. Nothing holds a lock during a model call.

_REGISTRY_LOCK = threading.Lock()
_WORKERS: Dict[str, "_RunWorker"] = {}
_RUN_LOCKS: Dict[str, threading.Lock] = {}


def _run_lock(run_id: str) -> threading.Lock:
    with _REGISTRY_LOCK:
        lock = _RUN_LOCKS.get(run_id)
        if lock is None:
            lock = _RUN_LOCKS[run_id] = threading.Lock()
        return lock


def _active_worker_locked(run_id: str) -> Optional["_RunWorker"]:
    worker = _WORKERS.get(run_id)
    if worker is None:
        return None
    # ident is None until start(): a registered worker that has not started yet still counts as busy.
    if worker.thread.is_alive() or worker.thread.ident is None:
        return worker
    return None


def _active_worker(run_id: str) -> Optional["_RunWorker"]:
    with _REGISTRY_LOCK:
        return _active_worker_locked(run_id)


class _RunWorker:
    def __init__(self, run_id: str, mode: str):  # mode: "step" or "advance"
        self.run_id, self.mode = run_id, mode
        self.cancel = threading.Event()
        self.thread = threading.Thread(target=self._main, name="research-run-" + run_id[:8], daemon=True)

    def _main(self) -> None:
        try:
            for _ in range(200):
                if self.cancel.is_set():
                    break
                status = _execute_step(self.run_id, self.cancel)
                if self.mode == "step" or status != "ready":
                    break
        except Exception as exc:  # engine bug: never leave the run stuck
            _mark_engine_error(self.run_id, exc)
        finally:
            with _REGISTRY_LOCK:
                if _WORKERS.get(self.run_id) is self:
                    del _WORKERS[self.run_id]


def _join_workers(timeout: float = 10.0) -> bool:
    """For tests: wait up to timeout seconds for live worker threads. True when none remain alive."""
    deadline = time.monotonic() + timeout
    with _REGISTRY_LOCK:
        workers = list(_WORKERS.values())
    for worker in workers:
        if worker.thread.ident is None:
            continue
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        worker.thread.join(remaining)
    return not any(w.thread.is_alive() for w in workers)


def _mark_engine_error(run_id: str, exc: BaseException) -> None:
    text = _error_text(exc)
    try:
        with _run_lock(run_id):
            with storage.transaction() as con:
                con.execute("UPDATE research_steps SET status='failed', error=?, finished_at=CURRENT_TIMESTAMP "
                            "WHERE run_id=? AND status='running'", (text, run_id))
                con.execute("UPDATE research_runs SET status='failed_step', updated_at=CURRENT_TIMESTAMP "
                            "WHERE id=? AND status <> 'cancelled'", (run_id,))
    except Exception:  # the database itself is unavailable; nothing more can be recorded
        return


def _write_run(con, run_id: str, status: str, state: Dict[str, Any]) -> None:
    con.execute("UPDATE research_runs SET status=?, state_json=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (status, _dumps(state), run_id))


def _save_guarded(run_id: str, status: str, state: Dict[str, Any]) -> bool:
    """Save unless the user cancelled the run meanwhile. False means it was cancelled: never overwrite."""
    with storage.transaction() as con:
        cursor = con.execute("UPDATE research_runs SET status=?, state_json=?, updated_at=CURRENT_TIMESTAMP "
                             "WHERE id=? AND status <> 'cancelled'", (status, _dumps(state), run_id))
        return cursor.rowcount == 1


def _load_run(con, run_id: str):
    row = con.execute("SELECT * FROM research_runs WHERE id=?", (run_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "연구 실행을 찾을 수 없습니다.")
    return row


def _run_view(row, busy: Optional[bool] = None) -> Dict[str, Any]:
    # Callers pass ``busy`` read BEFORE the row: a worker that finishes in between then shows
    # busy=True with its final status (one extra poll), never a stale "running" with busy=False.
    if busy is None:
        busy = _active_worker(row["id"]) is not None
    state = json.loads(row["state_json"])
    cfg = json.loads(row["config_json"])
    index = state["stage_index"]
    stage = STAGES[index] if index < len(STAGES) and row["status"] not in ("completed", "cancelled") else None
    return {"id": row["id"], "project_id": row["project_id"], "topic": row["topic"], "status": row["status"],
            "config": cfg, "iteration": state["iteration"], "stage": stage,
            "llm_calls": state["llm_calls"], "created_at": row["created_at"], "updated_at": row["updated_at"],
            "busy": busy,
            "elapsed_seconds": round(float(state.get("elapsed_seconds", 0)), 1),
            "max_run_seconds": _max_seconds(cfg), "max_llm_calls": int(cfg["max_llm_calls"]),
            "stop_reason": state.get("stop_reason"), "runtime_warning": state.get("last_runtime_warning")}


def _step_view(row) -> Dict[str, Any]:
    return {"id": row["id"], "iteration": row["iteration"], "stage": row["stage"], "status": row["status"],
            "input": json.loads(row["input_json"] or "{}"), "output": json.loads(row["output_json"] or "{}"),
            "error": row["error"], "model": row["model"], "prompt_hash": row["prompt_hash"],
            "started_at": row["started_at"], "finished_at": row["finished_at"]}


def _run_detail(con, run_id: str) -> Dict[str, Any]:
    busy = _active_worker(run_id) is not None
    row = _load_run(con, run_id)
    steps = [_step_view(s) for s in con.execute("SELECT * FROM research_steps WHERE run_id=? ORDER BY id", (run_id,))]
    return {"run": _run_view(row, busy), "steps": steps, "state": json.loads(row["state_json"])}


def _step_input(stage: str, state: Dict[str, Any]) -> Dict[str, Any]:
    return {"iteration": state["iteration"], "stage": stage,
            "counts": {"queries": len(state["queries"]), "candidates": len(state["candidates"]),
                       "evidence": len(state["evidence"]), "problems": len(state["problems"]),
                       "methods": len(state["methods"])},
            "llm_calls_before": state["llm_calls"]}


def _elapsed(state: Dict[str, Any], started: float) -> None:
    state["elapsed_seconds"] = round(float(state.get("elapsed_seconds", 0)) + (time.monotonic() - started), 1)


def _budget_stop(run_id: str, state: Dict[str, Any], reason: str) -> str:
    state["stop_reason"] = reason
    if _save_guarded(run_id, "budget_exhausted", state):
        return "budget_exhausted"
    return "cancelled"


def _execute_step(run_id: str, cancel: Optional[threading.Event] = None) -> str:
    """Run the next stage once. Returns the resulting run status."""
    cancel = cancel or threading.Event()
    with _run_lock(run_id):
        with storage.transaction() as con:
            row = _load_run(con, run_id)
            if row["status"] == "cancelled":
                return "cancelled"
            if row["status"] not in STEPPABLE:
                return row["status"]
            cfg = json.loads(row["config_json"])
            state = json.loads(row["state_json"])
            con.execute("UPDATE research_steps SET status='failed', error=?, finished_at=CURRENT_TIMESTAMP "
                        "WHERE run_id=? AND status='running'", (INTERRUPTED_ERROR, run_id))
        stage = STAGES[state["stage_index"]]
        iteration = state["iteration"]
        if float(state.get("elapsed_seconds", 0)) >= _max_seconds(cfg):
            return _budget_stop(run_id, state, "time")
        if stage in LLM_STAGES and _needs_llm(stage, state) and int(state["llm_calls"]) >= int(cfg["max_llm_calls"]):
            return _budget_stop(run_id, state, "calls")
        with storage.transaction() as con:
            cursor = con.execute("INSERT INTO research_steps(run_id,iteration,stage,status,input_json) VALUES(?,?,?,?,?)",
                                 (run_id, iteration, stage, "running", _dumps(_step_input(stage, state))))
            step_id = cursor.lastrowid
        if not _save_guarded(run_id, "running", state):
            _finish_step(step_id, "cancelled", {}, CANCELLED_ERROR, None, None)
            return "cancelled"
    ctx = _StepContext(run_id, step_id, stage, state, cfg, cancel, time.monotonic())
    try:
        output = STAGE_FUNCS[stage](ctx, cfg, state)
    except _StopRun as stop:
        _elapsed(state, ctx.started)
        if stop.reason == "cancelled":
            _finish_step(step_id, "cancelled", ctx.failure_output(), CANCELLED_ERROR, ctx.model, ctx.prompt_hash)
            return "cancelled"
        state["stop_reason"] = stop.reason
        _finish_step(step_id, "failed", ctx.failure_output(), stop.message, ctx.model, ctx.prompt_hash)
        if _save_guarded(run_id, "budget_exhausted", state):
            return "budget_exhausted"
        return "cancelled"
    except Exception as exc:  # recorded on the step row; the same stage can be retried
        _elapsed(state, ctx.started)
        _finish_step(step_id, "failed", ctx.failure_output(), _error_text(exc), ctx.model, ctx.prompt_hash)
        if _save_guarded(run_id, "failed_step", state):
            return "failed_step"
        return "cancelled"
    _elapsed(state, ctx.started)
    state["stage_index"] = state["stage_index"] + 1
    if stage == "critique":
        status = "awaiting_review" if iteration < int(cfg["max_iterations"]) else "completed"
    else:
        status = "ready"
    if ctx.model:
        state["last_model"] = ctx.model
    if not _save_guarded(run_id, status, state):
        _finish_step(step_id, "cancelled", ctx.failure_output(), CANCELLED_ERROR, ctx.model, ctx.prompt_hash)
        return "cancelled"
    _finish_step(step_id, "done", {**output, **ctx.success_meta()}, None, ctx.model, ctx.prompt_hash)
    return status


def _finish_step(step_id: int, status: str, output: Dict[str, Any], error: Optional[str],
                 model: Optional[str], prompt_hash: Optional[str]) -> None:
    with storage.transaction() as con:
        con.execute("UPDATE research_steps SET status=?, output_json=?, error=?, model=?, prompt_hash=?, "
                    "finished_at=CURRENT_TIMESTAMP WHERE id=?",
                    (status, _dumps(output), error, model, prompt_hash, step_id))


def _start_worker(run_id: str, mode: str) -> Dict[str, Any]:
    with _run_lock(run_id):
        with storage.transaction() as con:
            row = _load_run(con, run_id)
            if row["status"] not in STEPPABLE:
                raise HTTPException(409, {"code": "run_not_steppable", "message": "이 실행은 더 진행할 수 없습니다."})
        with _REGISTRY_LOCK:
            if _active_worker_locked(run_id) is not None:
                raise HTTPException(409, {"code": "run_busy", "message": "이 실행은 이미 진행 중입니다."})
            worker = _RunWorker(run_id, mode)
            _WORKERS[run_id] = worker
        try:
            with storage.transaction() as con:
                con.execute("UPDATE research_runs SET status='running', updated_at=CURRENT_TIMESTAMP WHERE id=?",
                            (run_id,))
            worker.thread.start()
        except Exception:
            with _REGISTRY_LOCK:
                if _WORKERS.get(run_id) is worker:
                    del _WORKERS[run_id]
            raise
    with storage.transaction() as con:
        return _run_detail(con, run_id)


def _iteration_summary(state: Dict[str, Any], note: str) -> Dict[str, Any]:
    critique = state.get("critique") or {}
    return {"iteration": state["iteration"], "queries": list(state["queries"]),
            "candidate_count": len(state["candidates"]), "evidence_count": len(state["evidence"]),
            "problem_titles": [p["title"] for p in state["problems"]],
            "check_summary": (critique.get("checks") or {}).get("summary"), "note": note}


# ---- research loop: routes ------------------------------------------------

@router.post("/api/research-runs/preview")
def preview_research_run(payload: RunConfigIn):
    bundle = run_llm(lambda: _prepare_run(payload))
    return {"policy": bundle["policy"], "external": bundle["first"]["external"],
            "first_prompt": bundle["first"], "preview_hash": bundle["preview_hash"]}


@router.get("/api/research-runs")
def list_research_runs():
    with _REGISTRY_LOCK:
        busy_ids = {run_id for run_id in _WORKERS if _active_worker_locked(run_id) is not None}
    with storage.transaction() as con:
        rows = con.execute("SELECT * FROM research_runs ORDER BY created_at DESC, rowid DESC").fetchall()
        return [_run_view(r, r["id"] in busy_ids) for r in rows]


@router.post("/api/research-runs", status_code=201)
def create_research_run(payload: RunCreateIn):
    bundle = run_llm(lambda: _prepare_run(payload))
    if bundle["first"]["external"] or payload.preview_hash is not None:
        if payload.preview_hash != bundle["preview_hash"]:
            raise _conflict("보낼 내용이 미리보기와 다릅니다. 다시 미리보기를 확인해 주세요.")
    cfg = bundle["config"]
    run_id = storage.new_id()
    state = _initial_state(bundle["snapshot"], bundle["preview_hash"])
    with storage.transaction() as con:
        if cfg["project_id"]:
            _require_project(con, cfg["project_id"])
        con.execute("INSERT INTO research_runs(id,project_id,topic,status,config_json,state_json) VALUES(?,?,?,?,?,?)",
                    (run_id, cfg["project_id"], cfg["topic"], "ready", _dumps(cfg), _dumps(state)))
        return _run_detail(con, run_id)


@router.get("/api/research-runs/{run_id}")
def get_research_run(run_id: str):
    with storage.transaction() as con:
        return _run_detail(con, run_id)


@router.post("/api/research-runs/{run_id}/step", status_code=202)
def step_research_run(run_id: str):
    return _start_worker(run_id, "step")


@router.post("/api/research-runs/{run_id}/advance", status_code=202)
def advance_research_run(run_id: str):
    return _start_worker(run_id, "advance")


@router.post("/api/research-runs/{run_id}/feedback")
def feedback_research_run(run_id: str, payload: FeedbackIn):
    note = payload.note.strip()
    with _run_lock(run_id):
        if _active_worker(run_id) is not None:
            raise HTTPException(409, {"code": "run_busy", "message": "이 실행은 이미 진행 중입니다."})
        with storage.transaction() as con:
            row = _load_run(con, run_id)
            if row["status"] != "awaiting_review":
                raise HTTPException(409, {"code": "not_awaiting_review", "message": "검토 단계에서만 피드백을 보낼 수 있습니다."})
            state = json.loads(row["state_json"])
            focus = payload.focus_problem
            if focus is not None and focus >= len(state["problems"]):
                raise HTTPException(422, "선택한 문제 번호가 없습니다.")
            critique = state.get("critique") or {}
            state["history"].append(_iteration_summary(state, note))
            state["carry"] = {"weaknesses": [w.get("text") if isinstance(w, dict) else str(w)
                                             for w in critique.get("weaknesses", [])],
                              "next_queries": list(critique.get("next_queries", [])),
                              "note": note,
                              "focus_title": state["problems"][focus]["title"] if focus is not None else None}
            state["iteration"] += 1
            state["stage_index"] = 0
            state.pop("stop_reason", None)
            for field in ("queries", "candidates", "evidence", "problems", "methods", "contributions"):
                state[field] = []
            state["critique"] = None
            _write_run(con, run_id, "ready", state)
            return _run_detail(con, run_id)


@router.post("/api/research-runs/{run_id}/cancel")
def cancel_research_run(run_id: str):
    with _run_lock(run_id):
        with storage.transaction() as con:
            _load_run(con, run_id)
            changed = con.execute("UPDATE research_runs SET status='cancelled', updated_at=CURRENT_TIMESTAMP "
                                  "WHERE id=? AND status NOT IN ('completed','cancelled')", (run_id,)).rowcount
            if not changed:
                raise HTTPException(409, {"code": "run_finished", "message": "이미 끝난 실행입니다."})
            worker = _active_worker(run_id)
            if worker is not None:
                worker.cancel.set()  # the worker marks its own running step as cancelled
            else:
                con.execute("UPDATE research_steps SET status='cancelled', error=?, finished_at=CURRENT_TIMESTAMP "
                            "WHERE run_id=? AND status='running'", (CANCELLED_ERROR, run_id))
    with storage.transaction() as con:
        return _run_detail(con, run_id)


def _pick(indices: List[int], items: list, label: str) -> List[int]:
    picked: List[int] = []
    for index in indices:
        if not 0 <= index < len(items):
            raise HTTPException(422, "%s 번호가 올바르지 않습니다." % label)
        if index not in picked:
            picked.append(index)
    return picked


@router.post("/api/research-runs/{run_id}/save", status_code=201)
def save_research_run(run_id: str, payload: SaveIn):
    if not payload.problems and not payload.contributions:
        raise HTTPException(422, "저장할 문제나 기여 문장을 고르세요.")
    with storage.transaction() as con:
        row = _load_run(con, run_id)
        _require_project(con, payload.project_id)
        state = json.loads(row["state_json"])
        problem_ids = _pick(payload.problems, state["problems"], "문제")
        contribution_ids = _pick(payload.contributions, state["contributions"], "기여 문장")
        evidence = {e["key"]: e for e in state["evidence"]}
        ideas: List[Dict[str, str]] = []
        gaps: List[Dict[str, str]] = []
        for index in problem_ids:
            problem = state["problems"][index]
            quotes = [evidence[k] for k in problem["evidence"] if k in evidence]
            lines = ["문제 설명: " + problem["statement"], "왜 열려 있는가: " + problem["why_open"], "근거:"]
            for quote in quotes:
                source = quote["title"] + (", doi:" + quote["doi"] if quote.get("doi") else "")
                lines.append("- \"%s\" (%s)" % (quote["quote"], source))
            lines.append("AI 연구 루프가 만든 초안입니다. 확정하기 전에 근거를 직접 확인하세요.")
            idea_id = storage.new_id()
            con.execute("INSERT INTO ideas(id,project_id,title,description) VALUES(?,?,?,?)",
                        (idea_id, payload.project_id, problem["title"], "\n".join(lines)))
            ideas.append({"id": idea_id, "title": problem["title"]})
            gap_id = storage.new_id()
            description = problem["statement"] + ("\n" + problem["why_open"] if problem["why_open"] else "")
            evidence_json = [{"source_title": q["title"], "doi": q.get("doi"), "url": q.get("url"),
                              "quote": q["quote"], "origin": "openalex_abstract"} for q in quotes]
            con.execute("INSERT INTO research_gaps(id,project_id,title,description,gap_type,paper_ids_json,"
                        "evidence_json,origin,status,model) VALUES(?,?,?,?,?,?,?,?,?,?)",
                        (gap_id, payload.project_id, problem["title"], description, problem["type"], "[]",
                         _dumps(evidence_json), "research_loop", "candidate", state.get("last_model")))
            gaps.append({"id": gap_id, "title": problem["title"]})
        for index in contribution_ids:
            contribution = state["contributions"][index]
            lines = [contribution["statement"], "", "가장 가까운 선행 연구 (검색 결과이며 참신성 판정이 아님):"]
            for prior in contribution["closest_prior"]:
                lines.append("- %s (%s) %s" % (prior["title"], prior["year"] or "미상", prior["doi"] or prior["url"] or ""))
            lines.append("AI 연구 루프가 만든 초안입니다. 확정하기 전에 근거를 직접 확인하세요.")
            idea_id = storage.new_id()
            con.execute("INSERT INTO ideas(id,project_id,title,description) VALUES(?,?,?,?)",
                        (idea_id, payload.project_id, contribution["statement"][:500], "\n".join(lines)))
            ideas.append({"id": idea_id, "title": contribution["statement"][:500]})
        return {"ideas": ideas, "gaps": gaps}
