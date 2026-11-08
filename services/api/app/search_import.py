"""Attach an open-access PDF to a search-result paper, on explicit user request only.

Candidates are tried in order: the URL given by the user, the search result's
pdf_url, an arXiv PDF derived from source_id, and finally OpenAlex's open-access
location for the DOI. Only https URLs are fetched. Every host must resolve to
public addresses, both before the request and after each redirect. Downloads
are capped at 100MB and must start with %PDF-. Logs and error responses carry
only host names and short reason codes, never full URLs.
"""
from __future__ import annotations

import http.client
import ipaddress
import json
import re
import socket
import urllib.request
from typing import Iterator, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse, urlunparse

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from . import jobs, scholarly, storage

router = APIRouter()

MAX_PDF_BYTES = 100 * 1024 * 1024
DOWNLOAD_TIMEOUT_SECONDS = 30
MAX_REDIRECTS = 5
MAX_LOOKUP_BYTES = 1024 * 1024
ARXIV_HOSTS = {"arxiv.org", "www.arxiv.org"}
OPENALEX_HOST = "api.openalex.org"
NOT_FOUND_MESSAGE = "공개 PDF를 찾지 못했습니다. 출판사 페이지에서 직접 받아 등록해 주세요."

_ARXIV_ABS = re.compile(r"arxiv\.org/abs/([A-Za-z0-9./_-]+?)(?:[?#].*)?$", re.IGNORECASE)
_ARXIV_BARE = re.compile(r"^(?:\d{4}\.\d{4,5}|[a-z-]+(?:\.[A-Za-z]{2})?/\d{7})(?:v\d+)?$", re.IGNORECASE)


class OpenPdfRequest(BaseModel):
    url: Optional[str] = None


class _Rejected(Exception):
    """A candidate was refused or failed for a reason that is safe to show."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _is_ip_literal(host: str) -> bool:
    try:
        ipaddress.ip_address(host.strip("[]"))
        return True
    except ValueError:
        return False


def _is_public(address: str) -> bool:
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return False
    return ip.is_global and not (ip.is_private or ip.is_loopback or ip.is_link_local
                                 or ip.is_multicast or ip.is_reserved or ip.is_unspecified)


def _resolve(host: str, port: int) -> list:
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise _Rejected("dns_failed") from exc
    addresses = [info[4][0] for info in infos]
    if not addresses:
        raise _Rejected("dns_failed")
    return addresses


def check_url(raw) -> str:
    """Return a normalized https URL or raise _Rejected. Reasons are short codes."""
    if not isinstance(raw, str) or not raw.strip() or len(raw) > 2048:
        raise _Rejected("invalid_url")
    try:
        parsed = urlparse(raw.strip())
        host = (parsed.hostname or "").lower()
        port = parsed.port
    except ValueError as exc:
        raise _Rejected("invalid_url") from exc
    if not host:
        raise _Rejected("invalid_url")
    if parsed.scheme == "https" or (parsed.scheme == "http" and host in ARXIV_HOSTS):
        scheme = "https"
    else:
        raise _Rejected("not_https")
    if parsed.username or parsed.password:
        raise _Rejected("credentials_in_url")
    if port not in (None, 443):
        raise _Rejected("port_not_allowed")
    if _is_ip_literal(host):
        raise _Rejected("ip_literal")
    if host == "localhost" or host.endswith(".localhost") or "." not in host:
        raise _Rejected("local_host")
    for address in _resolve(host, 443):
        if not _is_public(address):
            raise _Rejected("private_address")
    return urlunparse((scheme, host, parsed.path, parsed.params, parsed.query, ""))


class _GuardedRedirects(urllib.request.HTTPRedirectHandler):
    """Re-checks every redirect target and caps the number of hops per fetch."""

    def __init__(self):
        self.hops = 0

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        self.hops += 1
        if self.hops > MAX_REDIRECTS:
            raise _Rejected("too_many_redirects")
        return super().redirect_request(req, fp, code, msg, headers, check_url(newurl))


def _build_opener():
    return urllib.request.build_opener(_GuardedRedirects())


class _CappedBody:
    """Serves the already-read PDF header first, then the rest, and caps the total size."""

    def __init__(self, head: bytes, response, limit: int):
        self._pending = head
        self._response = response
        self._limit = limit
        self._total = 0

    def read(self, size: int = -1) -> bytes:
        if self._pending:
            take = self._pending if size is None or size < 0 else self._pending[:size]
            self._pending = self._pending[len(take):]
            chunk = take
        else:
            chunk = self._response.read(size if size and size > 0 else 1024 * 1024)
        self._total += len(chunk)
        if self._total > self._limit:
            raise _Rejected("too_large")
        return chunk


def _download(url: str):
    """Fetch url into content-addressed storage. Returns (sha256, size, storage_key)."""
    request = urllib.request.Request(url, headers={"User-Agent": scholarly.USER_AGENT,
                                                   "Accept": "application/pdf,*/*;q=0.1"})
    response = _build_opener().open(request, timeout=DOWNLOAD_TIMEOUT_SECONDS)
    try:
        length = response.headers.get("Content-Length") if response.headers else None
        if length and length.isdigit() and int(length) > MAX_PDF_BYTES:
            raise _Rejected("too_large")
        head = response.read(1024)
        if b"%PDF-" not in head:
            raise _Rejected("not_pdf")
        body = _CappedBody(head, response, MAX_PDF_BYTES)
        return storage.store_stream(body, max_bytes=MAX_PDF_BYTES)
    finally:
        response.close()


def _openalex_pdf_urls(doi: str) -> list:
    url = "https://{}/works/doi:{}?select=best_oa_location,open_access".format(OPENALEX_HOST, quote(doi, safe="/"))
    check_url(url)
    request = urllib.request.Request(url, headers={"User-Agent": scholarly.USER_AGENT, "Accept": "application/json"})
    response = _build_opener().open(request, timeout=scholarly.TIMEOUT_SECONDS)
    try:
        body = response.read(MAX_LOOKUP_BYTES + 1)
    finally:
        response.close()
    if len(body) > MAX_LOOKUP_BYTES:
        raise _Rejected("response_too_large")
    try:
        data = json.loads(body)
    except ValueError as exc:
        raise _Rejected("invalid_response") from exc
    if not isinstance(data, dict):
        raise _Rejected("invalid_response")
    found = []
    best = data.get("best_oa_location")
    if isinstance(best, dict) and isinstance(best.get("pdf_url"), str):
        found.append(best["pdf_url"])
    oa = data.get("open_access")
    if isinstance(oa, dict) and isinstance(oa.get("oa_url"), str):
        found.append(oa["oa_url"])
    return found


def _arxiv_pdf_url(source, source_id) -> Optional[str]:
    if not isinstance(source_id, str):
        return None
    value = source_id.strip()
    match = _ARXIV_ABS.search(value)
    if match:
        identifier = match.group(1)
    elif str(source or "").lower() == "arxiv" and _ARXIV_BARE.match(value):
        identifier = value
    else:
        return None
    return "https://arxiv.org/pdf/" + identifier


def _reason(exc: BaseException) -> str:
    if isinstance(exc, _Rejected):
        return exc.reason
    if isinstance(exc, HTTPError):
        return "http_{}".format(exc.code)
    if isinstance(exc, (TimeoutError, socket.timeout)):
        return "timeout"
    if isinstance(exc, URLError) and isinstance(exc.reason, (TimeoutError, socket.timeout)):
        return "timeout"
    if isinstance(exc, ValueError):
        return "storage_error"
    return "network_error"


def _host_of(raw) -> Optional[str]:
    try:
        return urlparse(str(raw)).hostname
    except ValueError:
        return None


def _metadata(paper) -> dict:
    try:
        value = json.loads(paper["metadata_json"] or "{}")
    except ValueError:
        return {}
    return value if isinstance(value, dict) else {}


def _candidates(paper, body_url, tried: list) -> Iterator[str]:
    if body_url:
        yield body_url
    meta = _metadata(paper)
    if isinstance(meta.get("pdf_url"), str) and meta["pdf_url"].strip():
        yield meta["pdf_url"]
    arxiv = _arxiv_pdf_url(paper["source"] or meta.get("source"), paper["source_id"] or meta.get("source_id"))
    if arxiv:
        yield arxiv
    doi = paper["doi"]
    if doi:
        # OpenAlex is consulted only after the direct candidates have failed.
        try:
            found = _openalex_pdf_urls(doi)
        except (_Rejected, HTTPError, URLError, OSError, http.client.HTTPException, ValueError) as exc:
            tried.append({"url_host": OPENALEX_HOST, "reason": _reason(exc)})
            return
        yield from found


def _active_paper(con, paper_id: str):
    paper = con.execute("SELECT * FROM papers WHERE id=? AND deleted_at IS NULL", (paper_id,)).fetchone()
    if paper is None:
        raise HTTPException(404, "논문을 찾을 수 없습니다.")
    return paper


def _attach(paper_id: str, source_url: str, sha: str, size: int, key: str) -> dict:
    with storage.transaction() as con:
        con.execute("BEGIN IMMEDIATE")
        paper = _active_paper(con, paper_id)
        if paper["file_id"]:
            raise HTTPException(409, "이미 PDF가 연결되어 있습니다.")
        row = con.execute("SELECT id FROM files WHERE sha256=?", (sha,)).fetchone()
        if row:
            file_id = row["id"]
        else:
            file_id = storage.new_id()
            con.execute("INSERT INTO files(id,sha256,size,storage_key) VALUES(?,?,?,?)", (file_id, sha, size, key))
        # Same guard as import_pdf: a concurrent purge may have removed the file.
        if not storage.file_path(key).is_file():
            raise HTTPException(409, "PDF를 저장하는 중 파일이 정리되었습니다. 다시 시도해 주세요.")
        owner = con.execute("SELECT title FROM papers WHERE file_id=? AND deleted_at IS NULL AND id<>? LIMIT 1",
                            (file_id, paper_id)).fetchone()
        if owner:
            raise HTTPException(409, "같은 PDF가 이미 다른 논문('{}')에 연결되어 있습니다. 두 논문을 합치지 않습니다.".format(owner["title"]))
        if con.execute("SELECT 1 FROM papers WHERE file_id=? AND deleted_at IS NOT NULL AND id<>?", (file_id, paper_id)).fetchone():
            raise HTTPException(409, "같은 PDF가 휴지통에 있는 논문에 연결되어 있습니다. 기존 논문을 복구해 주세요.")
        con.execute("UPDATE papers SET file_id=? WHERE id=?", (file_id, paper_id))
        job_id = jobs.enqueue_pdf(con, paper_id)
        return {"status": "attached", "sha256": sha, "size": size, "source_url": source_url, "job_id": job_id}


@router.post("/api/papers/{paper_id}/fetch-open-pdf", status_code=201)
def fetch_open_pdf(paper_id: str, payload: OpenPdfRequest):
    with storage.transaction() as con:
        paper = _active_paper(con, paper_id)
        if paper["file_id"]:
            raise HTTPException(409, "이미 PDF가 연결되어 있습니다.")
        snapshot = dict(paper)

    tried: list = []
    seen_raw: set = set()
    seen_urls: set = set()
    for raw in _candidates(snapshot, payload.url, tried):
        key_raw = raw.strip() if isinstance(raw, str) else raw
        if key_raw in seen_raw:
            continue
        seen_raw.add(key_raw)
        try:
            url = check_url(raw)
        except _Rejected as exc:
            tried.append({"url_host": _host_of(raw), "reason": exc.reason})
            continue
        if url in seen_urls:
            continue
        seen_urls.add(url)
        try:
            sha, size, key = _download(url)
        except (_Rejected, HTTPError, URLError, OSError, http.client.HTTPException, ValueError) as exc:
            tried.append({"url_host": urlparse(url).hostname, "reason": _reason(exc)})
            continue
        return _attach(paper_id, url, sha, size, key)

    return JSONResponse(status_code=404, content={"detail": NOT_FOUND_MESSAGE, "tried": tried})
