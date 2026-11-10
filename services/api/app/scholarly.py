"""Small, dependency-free adapters for scholarly metadata services.

Results retain a source-specific record. They are metadata, not verified claims
or proof that a PDF is accessible. No request or response contains API keys.
"""

import collections
import copy
import datetime
import json
import math
import os
import re
import socket
import threading
import time
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urlencode
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

from . import storage

TIMEOUT_SECONDS = 15
MAX_RESPONSE_BYTES = 5 * 1024 * 1024
USER_AGENT = "EasyResearch/0.1 (local research application)"
_arxiv_lock = threading.Lock()
_arxiv_last_request = 0.0

OPENALEX_ENV_VAR = "OPENALEX_API_KEY"
OPENALEX_RATE_LIMITED_MESSAGE = (
    "OpenAlex 하루 사용 예산을 모두 사용했습니다. 무료 OpenAlex 키를 AI 설정에서 넣으면 "
    "하루 약 1,000회까지 검색할 수 있습니다."
)
OPENALEX_CACHE_MAX = 256
OPENALEX_CACHE_TTL_SECONDS = 24 * 60 * 60
_KEY_PATTERN = re.compile(r"[!-~]{8,200}")
_budget_lock = threading.Lock()
_budget = None
_cache_lock = threading.Lock()
_openalex_cache = collections.OrderedDict()  # key -> (expires_at, results)


class ScholarlyError(Exception):
    def __init__(self, source, code, message, status=None):
        super().__init__(message)
        self.source = source
        self.code = code
        self.message = message
        self.status = status


def _openalex_secret_path():
    return storage.data_dir() / "secrets" / "openalex_api_key"


def _env_key():
    return (os.environ.get(OPENALEX_ENV_VAR) or "").strip() or None


def _file_key():
    path = _openalex_secret_path()
    try:
        if not path.is_file():
            return None
        return path.read_text(encoding="utf-8").strip() or None
    except (OSError, UnicodeDecodeError):
        return None


def openalex_key() -> Optional[str]:
    """Environment variable first, then the saved local file. Never log the value."""
    return _env_key() or _file_key()


def openalex_key_source() -> Optional[str]:
    if _env_key():
        return "env"
    if _file_key():
        return "file"
    return None


def save_openalex_key(api_key: Optional[str], clear: bool = False):
    if api_key is not None and not _KEY_PATTERN.fullmatch(api_key):
        raise ValueError("OpenAlex API 키 형식이 올바르지 않습니다.")
    path = _openalex_secret_path()
    if clear and path.exists():
        path.unlink()
    if api_key is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(api_key, encoding="utf-8")


def _parse_number(value, kind):
    if value is None:
        return None
    try:
        number = kind(str(value).strip())
    except (TypeError, ValueError):
        return None
    if isinstance(number, float) and not math.isfinite(number):
        return None
    return number


def _record_budget(headers, keyed):
    global _budget
    try:
        def get(name):
            return headers.get(name) if headers is not None else None
        record = {
            "remaining_usd": _parse_number(get("X-RateLimit-Remaining-USD"), float),
            "limit_usd": _parse_number(get("X-RateLimit-Limit-USD"), float),
            "reset_seconds": _parse_number(get("X-RateLimit-Reset"), lambda v: int(float(v))),
            "credits_used": _parse_number(get("X-RateLimit-Credits-Used"), lambda v: int(float(v))),
            "cost_usd": _parse_number(get("X-RateLimit-Cost-USD"), float),
        }
    except Exception:
        return
    if all(value is None for value in record.values()):
        return
    record["keyed"] = bool(keyed)
    record["observed_at"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with _budget_lock:
        _budget = record


def openalex_budget() -> Optional[dict]:
    with _budget_lock:
        return dict(_budget) if _budget is not None else None


def _get(source, url, headers=None):
    request_headers = {"User-Agent": USER_AGENT, "Accept": "application/json, application/atom+xml"}
    request_headers.update(headers or {})
    request = Request(url, headers=request_headers)
    keyed = "Authorization" in request_headers
    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            body = response.read(MAX_RESPONSE_BYTES + 1)
            if source == "openalex":
                _record_budget(response.headers, keyed)
        if len(body) > MAX_RESPONSE_BYTES:
            raise ScholarlyError(source, "response_too_large", "The service returned too much data.")
        return body
    except HTTPError as exc:
        if source == "openalex":
            _record_budget(exc.headers, keyed)
        code = "not_found" if exc.code == 404 else "rate_limited" if exc.code == 429 else "http_error"
        if code == "rate_limited" and source == "openalex":
            raise ScholarlyError(source, code, OPENALEX_RATE_LIMITED_MESSAGE, exc.code) from exc
        raise ScholarlyError(source, code, "The service returned HTTP {}.".format(exc.code), exc.code) from exc
    except (TimeoutError, socket.timeout) as exc:
        raise ScholarlyError(source, "timeout", "The service timed out.") from exc
    except URLError as exc:
        code = "timeout" if isinstance(exc.reason, (TimeoutError, socket.timeout)) else "network_error"
        raise ScholarlyError(source, code, "The service could not be reached.") from exc
    except OSError as exc:
        raise ScholarlyError(source, "network_error", "The service could not be reached.") from exc


def _json(source, body):
    try:
        value = json.loads(body)
        if not isinstance(value, dict):
            raise ValueError("expected an object")
        return value
    except (ValueError, UnicodeDecodeError) as exc:
        raise ScholarlyError(source, "invalid_response", "The service returned invalid JSON.") from exc


def _query_and_limit(query, limit):
    if not isinstance(query, str) or not query.strip() or len(query) > 300:
        raise ValueError("query must contain 1 to 300 characters")
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 25:
        raise ValueError("limit must be an integer from 1 to 25")
    return " ".join(query.split())


def normalize_doi(value):
    if not isinstance(value, str):
        raise ValueError("invalid DOI")
    value = unquote(value.strip())
    value = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", value, flags=re.I)
    if len(value) > 1000 or not re.fullmatch(r"10\.\d{4,9}/[^\s\x00-\x1f\x7f]+", value, re.I):
        raise ValueError("invalid DOI")
    return value.lower()


def _maybe_doi(value):
    try:
        return normalize_doi(value)
    except ValueError:
        return None


def _openalex_abstract(inverted):
    if not isinstance(inverted, dict):
        return None
    words = []
    for word, positions in inverted.items():
        if isinstance(word, str) and isinstance(positions, list):
            words.extend((p, word) for p in positions if isinstance(p, int) and not isinstance(p, bool) and 0 <= p < 100000)
    return " ".join(word for _, word in sorted(words)) or None


def _now():
    return time.monotonic()


def _cache_key(query, limit):
    return (" ".join(query.lower().split()), limit)


def _cache_get(key):
    with _cache_lock:
        item = _openalex_cache.get(key)
        if item is None:
            return None
        expires_at, results = item
        if _now() >= expires_at:
            del _openalex_cache[key]
            return None
        _openalex_cache.move_to_end(key)
        return copy.deepcopy(results)


def _cache_put(key, results):
    with _cache_lock:
        _openalex_cache[key] = (_now() + OPENALEX_CACHE_TTL_SECONDS, copy.deepcopy(results))
        _openalex_cache.move_to_end(key)
        while len(_openalex_cache) > OPENALEX_CACHE_MAX:
            _openalex_cache.popitem(last=False)


def clear_openalex_cache():
    with _cache_lock:
        _openalex_cache.clear()


def search_openalex(query, limit=10, api_key=None):
    query = _query_and_limit(query, limit)
    if api_key is None:
        api_key = openalex_key()
    key = _cache_key(query, limit)
    cached = _cache_get(key)
    if cached is not None:
        return cached
    headers = {"Authorization": "Bearer " + api_key} if api_key else None
    url = "https://api.openalex.org/works?" + urlencode({"search": query, "per-page": limit})
    payload = _json("openalex", _get("openalex", url, headers))
    records = payload.get("results")
    if not isinstance(records, list):
        raise ScholarlyError("openalex", "invalid_response", "The service returned an invalid results list.")
    results = []
    for record in records:
        if not isinstance(record, dict):
            raise ScholarlyError("openalex", "invalid_response", "The service returned an invalid record.")
        location = record.get("best_oa_location") or {}
        if not isinstance(location, dict):
            location = {}
        authors = []
        for authorship in record.get("authorships") or []:
            author = authorship.get("author") or {} if isinstance(authorship, dict) else {}
            if isinstance(author, dict) and author.get("display_name"):
                authors.append(author["display_name"])
        results.append({"source": "openalex", "source_id": record.get("id"),
                        "title": record.get("display_name") or record.get("title"),
                        "authors": authors, "year": record.get("publication_year"),
                        "doi": _maybe_doi(record.get("doi")),
                        "url": location.get("landing_page_url") or record.get("id"),
                        "abstract": _openalex_abstract(record.get("abstract_inverted_index")),
                        "pdf_url": location.get("pdf_url"), "source_record": record})
    _cache_put(key, results)
    return results


def search_arxiv(query, limit=10):
    global _arxiv_last_request
    query = _query_and_limit(query, limit)
    # Interpret the user's input as a phrase, not as an arXiv query language.
    phrase = query.replace('"', ' ').replace('\\', ' ')
    url = "https://export.arxiv.org/api/query?" + urlencode({"search_query": 'all:"' + phrase + '"', "start": 0, "max_results": limit})
    # arXiv requests a 3 second interval between consecutive requests.
    with _arxiv_lock:
        delay = 3.0 - (time.monotonic() - _arxiv_last_request)
        if delay > 0:
            time.sleep(delay)
        _arxiv_last_request = time.monotonic()
        body = _get("arxiv", url)
    try:
        if b"<!DOCTYPE" in body.upper() or b"<!ENTITY" in body.upper():
            raise ValueError("DTD is not allowed")
        root = ET.fromstring(body)
        atom = "{http://www.w3.org/2005/Atom}"
        arxiv = "{http://arxiv.org/schemas/atom}"
        if root.tag != atom + "feed":
            raise ValueError("expected Atom feed")
        results = []
        for entry in root.findall(atom + "entry"):
            source_id = entry.findtext(atom + "id")
            if source_id and "/api/errors#" in source_id:
                raise ScholarlyError("arxiv", "upstream_error", "arXiv rejected the search query.")
            pdf_url = None
            for link in entry.findall(atom + "link"):
                if link.get("title") == "pdf" or link.get("type") == "application/pdf":
                    pdf_url = link.get("href")
                    break
            date = entry.findtext(atom + "published") or ""
            results.append({"source": "arxiv", "source_id": source_id,
                            "title": " ".join((entry.findtext(atom + "title") or "").split()),
                            "authors": [" ".join((name.text or "").split()) for name in entry.findall(atom + "author/" + atom + "name") if name.text],
                            "year": int(date[:4]) if re.match(r"^\d{4}", date) else None,
                            "doi": _maybe_doi(entry.findtext(arxiv + "doi")), "url": source_id,
                            "abstract": " ".join((entry.findtext(atom + "summary") or "").split()) or None,
                            "pdf_url": pdf_url, "source_record": ET.tostring(entry, encoding="unicode")})
        return results
    except (ET.ParseError, ValueError) as exc:
        raise ScholarlyError("arxiv", "invalid_response", "The service returned invalid Atom data.") from exc


def lookup_crossref(doi):
    doi = normalize_doi(doi)
    url = "https://api.crossref.org/works/" + quote(doi, safe="")
    payload = _json("crossref", _get("crossref", url))
    record = payload.get("message")
    if not isinstance(record, dict):
        raise ScholarlyError("crossref", "invalid_response", "The service returned an invalid record.")
    dates = record.get("published") or record.get("issued") or {}
    parts = dates.get("date-parts", []) if isinstance(dates, dict) else []
    year = parts[0][0] if parts and isinstance(parts[0], list) and parts[0] and isinstance(parts[0][0], int) else None
    authors = []
    for author in record.get("author") or []:
        if isinstance(author, dict):
            name = author.get("name") or " ".join(filter(None, [author.get("given"), author.get("family")]))
            if name:
                authors.append(name)
    titles = record.get("title") or []
    return {"source": "crossref", "source_id": record.get("DOI") or doi,
            "title": titles[0] if isinstance(titles, list) and titles else None,
            "authors": authors, "year": year, "doi": _maybe_doi(record.get("DOI")) or doi,
            "url": record.get("URL") or "https://doi.org/" + doi,
            "abstract": record.get("abstract"), "pdf_url": None, "source_record": record}
