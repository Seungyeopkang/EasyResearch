"""Small, dependency-free adapters for scholarly metadata services.

Results retain a source-specific record. They are metadata, not verified claims
or proof that a PDF is accessible. No request or response contains API keys.
"""

import json
import re
import socket
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urlencode
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

TIMEOUT_SECONDS = 15
MAX_RESPONSE_BYTES = 5 * 1024 * 1024
USER_AGENT = "EasyResearch/0.1 (local research application)"
_arxiv_lock = threading.Lock()
_arxiv_last_request = 0.0


class ScholarlyError(Exception):
    def __init__(self, source, code, message, status=None):
        super().__init__(message)
        self.source = source
        self.code = code
        self.message = message
        self.status = status


def _get(source, url, headers=None):
    request_headers = {"User-Agent": USER_AGENT, "Accept": "application/json, application/atom+xml"}
    request_headers.update(headers or {})
    request = Request(url, headers=request_headers)
    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            body = response.read(MAX_RESPONSE_BYTES + 1)
        if len(body) > MAX_RESPONSE_BYTES:
            raise ScholarlyError(source, "response_too_large", "The service returned too much data.")
        return body
    except HTTPError as exc:
        code = "not_found" if exc.code == 404 else "rate_limited" if exc.code == 429 else "http_error"
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


def search_openalex(query, limit=10, api_key=None):
    query = _query_and_limit(query, limit)
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
