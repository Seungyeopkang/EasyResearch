"""AI provider settings, local runtime status, and shared helpers for AI endpoints."""
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from . import llm

router = APIRouter()


class AIConfigUpdate(BaseModel):
    provider: str
    base_url: str = ""
    model: str = ""
    api_key_env: str = ""
    timeout: int = 120
    max_input_chars: int = 8000
    temperature: float = 0.2
    api_key: Optional[str] = Field(default=None, max_length=500)
    clear_api_key: bool = False


class AITestRequest(BaseModel):
    preview_hash: Optional[str] = None


def llm_http_error(exc: "llm.LLMError") -> HTTPException:
    if exc.code == "stopped":
        return HTTPException(409, {"code": exc.code, "message": exc.message})
    status = exc.status if exc.status in (409, 429) else 400 if exc.code == "not_configured" else 502
    return HTTPException(status, {"code": exc.code, "message": exc.message})


def run_llm(call):
    """Run an llm call and translate errors to HTTP errors."""
    try:
        return call()
    except llm.LLMError as exc:
        raise llm_http_error(exc) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/api/ai/config")
def get_ai_config():
    return {**llm.public_config(), "presets": llm.PRESETS}


@router.get("/api/ai/status")
def get_ai_status():
    cfg = llm.get_config()
    return {"provider": cfg["provider"], "model": cfg["model"], "runtime": llm.runtime_status(cfg)}


@router.put("/api/ai/config")
def put_ai_config(payload: AIConfigUpdate):
    data = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
    api_key, clear = data.pop("api_key"), data.pop("clear_api_key")
    try:
        return llm.save_config(data, api_key=api_key, clear_key=clear)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


TEST_MESSAGES = [{"role": "user", "content": "Reply with the single word: OK"}]


@router.post("/api/ai/test/preview")
def preview_ai_test():
    return run_llm(lambda: llm.preview(TEST_MESSAGES, purpose="연결 확인"))


@router.post("/api/ai/test")
def ai_test(payload: AITestRequest):
    result = run_llm(lambda: llm.complete(TEST_MESSAGES, purpose="연결 확인", preview_hash=payload.preview_hash, max_tokens=20))
    return {"ok": True, "reply": result["text"][:200], "model": result["model"], "provider": result["provider"],
            "runtime": llm.runtime_status()}
