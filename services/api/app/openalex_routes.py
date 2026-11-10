"""OpenAlex key settings and budget status. The key value is never returned."""
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from . import scholarly

router = APIRouter()

FREE_KEY_URL = "https://openalex.org/settings/api"
KEYLESS_NOTE = (
    "OpenAlex 키 없이 쓰면 이 네트워크를 쓰는 모든 사용자가 하루 $0.10 예산(검색 약 100회)을 함께 씁니다. "
    "무료 OpenAlex 키를 넣으면 하루 $1 예산을 쓸 수 있습니다(검색 약 1,000회)."
)


class OpenAlexKeyUpdate(BaseModel):
    api_key: Optional[str] = Field(default=None, max_length=300)
    clear_key: bool = False


def _settings_payload():
    source = scholarly.openalex_key_source()
    return {
        "has_key": source is not None,
        "source": source,
        "budget": scholarly.openalex_budget(),
        "free_key_url": FREE_KEY_URL,
        "keyless_note": KEYLESS_NOTE,
    }


@router.get("/api/settings/openalex")
def get_openalex_settings():
    return _settings_payload()


@router.put("/api/settings/openalex")
def put_openalex_settings(payload: OpenAlexKeyUpdate):
    try:
        scholarly.save_openalex_key(payload.api_key, clear=payload.clear_key)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return _settings_payload()
