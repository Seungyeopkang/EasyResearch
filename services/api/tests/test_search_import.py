"""Open-access PDF attachment for search-result papers. The network is always mocked."""
import hashlib
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import closing
from email.message import Message
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import HTTPSHandler
from urllib.response import addinfourl

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import search_import, storage
from app.main import app

HEADERS = {"X-EasyResearch": "1"}
PUBLIC_IP = "93.184.216.34"
PRIVATE_HOSTS = {"intranet.example.org": "10.0.0.5"}
OPENALEX_DOI_URL = "https://api.openalex.org/works/doi:10.1000/xyz123?select=best_oa_location,open_access"


def fake_resolve(host, port):
    return [PRIVATE_HOSTS.get(host, PUBLIC_IP)]


def make_pdf(tag):
    return b"%PDF-1.4\n% " + tag.encode("ascii") + b"\n1 0 obj << >> endobj\n%%EOF\n"


def ok(body, headers=None):
    return (200, headers or {"Content-Type": "application/pdf"}, body)


class FakeResponse:
    def __init__(self, body, headers):
        self._buffer = io.BytesIO(body)
        self.headers = headers
        self.closed = False

    def read(self, size=-1):
        return self._buffer.read(size)

    def close(self):
        self.closed = True


class FakeOpener:
    """Serves exact URLs. Unknown URLs answer 404, and every request is recorded."""

    def __init__(self, routes):
        self.routes = routes
        self.requested = []

    def open(self, request, timeout=None):
        url = request.full_url
        self.requested.append(url)
        status, headers, body = self.routes.get(url, (404, {}, b""))
        if status >= 400:
            raise HTTPError(url, status, "error", Message(), io.BytesIO(b""))
        return FakeResponse(body, headers)


def http_response(url, code, headers, body=b""):
    message = Message()
    for key, value in headers.items():
        message[key] = value
    response = addinfourl(io.BytesIO(body), message, url, code)
    response.msg = "test"
    return response


class SearchImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"EASYRESEARCH_DATA_DIR": self.temp.name})
        self.env.start()
        self.client = TestClient(app)
        self.client.__enter__()
        self.resolver = patch.object(search_import, "_resolve", side_effect=fake_resolve)
        self.resolver.start()

    def tearDown(self):
        self.resolver.stop()
        self.client.__exit__(None, None, None)
        self.env.stop()
        self.temp.cleanup()

    def use_routes(self, routes):
        opener = FakeOpener(routes)
        patcher = patch.object(search_import, "_build_opener", return_value=opener)
        patcher.start()
        self.addCleanup(patcher.stop)
        return opener

    def add_search_paper(self, **fields):
        paper = {"title": "Pruning study", "source": "crossref", "source_id": "crossref-1", "year": 2024}
        paper.update(fields)
        response = self.client.post("/api/papers/from-search", headers=HEADERS, json={"paper": paper})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()["id"]

    def fetch(self, paper_id, body=None):
        return self.client.post("/api/papers/{}/fetch-open-pdf".format(paper_id), headers=HEADERS, json=body or {})

    def db_row(self, sql, args=()):
        with closing(storage.connect()) as con:
            return con.execute(sql, args).fetchone()

    def paper_file_id(self, paper_id):
        return self.db_row("SELECT file_id FROM papers WHERE id=?", (paper_id,))["file_id"]

    def assert_attached(self, response, body, source_url):
        self.assertEqual(response.status_code, 201, response.text)
        payload = response.json()
        self.assertEqual(payload["status"], "attached")
        self.assertEqual(payload["sha256"], hashlib.sha256(body).hexdigest())
        self.assertEqual(payload["size"], len(body))
        self.assertEqual(payload["source_url"], source_url)
        job = self.db_row("SELECT kind, target_id FROM jobs WHERE id=?", (payload["job_id"],))
        self.assertIsNotNone(job)
        self.assertEqual(job["kind"], "pdf_extract")
        return payload

    def test_success_from_metadata_pdf_url_enqueues_job(self):
        body = make_pdf("metadata")
        opener = self.use_routes({"https://repo.example.org/paper.pdf": ok(body)})
        paper_id = self.add_search_paper(pdf_url="https://repo.example.org/paper.pdf")
        response = self.fetch(paper_id)
        payload = self.assert_attached(response, body, "https://repo.example.org/paper.pdf")
        self.assertEqual(opener.requested, ["https://repo.example.org/paper.pdf"])
        file_id = self.paper_file_id(paper_id)
        self.assertIsNotNone(file_id)
        self.assertEqual(self.db_row("SELECT sha256 FROM files WHERE id=?", (file_id,))["sha256"], payload["sha256"])
        self.assertEqual(self.db_row("SELECT target_id FROM jobs WHERE id=?", (payload["job_id"],))["target_id"], paper_id)

    def test_arxiv_pdf_url_is_derived_from_source_id(self):
        body = make_pdf("arxiv")
        opener = self.use_routes({"https://arxiv.org/pdf/2301.00001v2": ok(body)})
        paper_id = self.add_search_paper(source="arxiv", source_id="http://arxiv.org/abs/2301.00001v2")
        self.assert_attached(self.fetch(paper_id), body, "https://arxiv.org/pdf/2301.00001v2")
        self.assertEqual(opener.requested, ["https://arxiv.org/pdf/2301.00001v2"])

    def test_openalex_doi_fallback_after_direct_candidates_fail(self):
        body = make_pdf("openalex")
        openalex_body = json.dumps({"best_oa_location": {"pdf_url": "https://oa.example.org/open.pdf"},
                                    "open_access": {"oa_url": None}}).encode("utf-8")
        opener = self.use_routes({
            OPENALEX_DOI_URL: ok(openalex_body, {"Content-Type": "application/json"}),
            "https://oa.example.org/open.pdf": ok(body),
        })
        paper_id = self.add_search_paper(doi="10.1000/xyz123")
        self.assert_attached(self.fetch(paper_id), body, "https://oa.example.org/open.pdf")
        self.assertEqual(opener.requested, [OPENALEX_DOI_URL, "https://oa.example.org/open.pdf"])

    def test_html_landing_page_is_skipped_for_next_candidate(self):
        body = make_pdf("after-html")
        opener = self.use_routes({
            "https://publisher.example.org/article": ok(b"<!doctype html><html>login</html>", {"Content-Type": "text/html"}),
            "https://arxiv.org/pdf/2301.00002": ok(body),
        })
        paper_id = self.add_search_paper(source="arxiv", source_id="https://arxiv.org/abs/2301.00002",
                                         pdf_url="https://publisher.example.org/article")
        self.assert_attached(self.fetch(paper_id), body, "https://arxiv.org/pdf/2301.00002")
        self.assertEqual(opener.requested, ["https://publisher.example.org/article", "https://arxiv.org/pdf/2301.00002"])

    def test_content_length_over_100mb_is_rejected_without_download(self):
        too_big = str(search_import.MAX_PDF_BYTES + 1)
        self.use_routes({"https://big.example.org/a.pdf": ok(make_pdf("big"), {"Content-Length": too_big})})
        paper_id = self.add_search_paper(pdf_url="https://big.example.org/a.pdf")
        response = self.fetch(paper_id)
        self.assertEqual(response.status_code, 404, response.text)
        self.assertEqual(response.json()["tried"], [{"url_host": "big.example.org", "reason": "too_large"}])
        self.assertIsNone(self.paper_file_id(paper_id))
        self.assertIsNone(self.db_row("SELECT id FROM files LIMIT 1"))

    def test_stream_over_limit_is_rejected_and_nothing_is_stored(self):
        body = make_pdf("stream") + b"x" * 4096
        self.use_routes({"https://stream.example.org/a.pdf": ok(body)})
        paper_id = self.add_search_paper(pdf_url="https://stream.example.org/a.pdf")
        with patch.object(search_import, "MAX_PDF_BYTES", 2048):
            response = self.fetch(paper_id)
        self.assertEqual(response.status_code, 404, response.text)
        self.assertEqual(response.json()["tried"][0]["reason"], "too_large")
        self.assertIsNone(self.paper_file_id(paper_id))
        self.assertIsNone(self.db_row("SELECT id FROM files LIMIT 1"))

    def test_http_private_ip_localhost_and_private_dns_are_rejected_before_any_request(self):
        opener = self.use_routes({})
        paper_id = self.add_search_paper()
        urls = [
            "http://files.example.org/a.pdf",
            "https://127.0.0.1/a.pdf",
            "https://[::1]/a.pdf",
            "https://localhost/a.pdf",
            "https://intranet.example.org/a.pdf",
        ]
        reasons = []
        for url in urls:
            response = self.fetch(paper_id, {"url": url})
            self.assertEqual(response.status_code, 404, response.text)
            reasons.append(response.json()["tried"][0])
        self.assertEqual(reasons, [
            {"url_host": "files.example.org", "reason": "not_https"},
            {"url_host": "127.0.0.1", "reason": "ip_literal"},
            {"url_host": "::1", "reason": "ip_literal"},
            {"url_host": "localhost", "reason": "local_host"},
            {"url_host": "intranet.example.org", "reason": "private_address"},
        ])
        self.assertEqual(opener.requested, [])

    def test_redirect_to_private_address_is_blocked(self):
        def https_open(handler, req):
            if req.full_url == "https://files.example.org/a.pdf":
                return http_response(req.full_url, 302, {"Location": "https://intranet.example.org/secret.pdf"})
            if req.full_url == "https://intranet.example.org/secret.pdf":
                return http_response(req.full_url, 200, {"Content-Type": "application/pdf"}, make_pdf("private"))
            raise AssertionError("unexpected request")

        paper_id = self.add_search_paper(pdf_url="https://files.example.org/a.pdf")
        with patch.object(HTTPSHandler, "https_open", https_open):
            response = self.fetch(paper_id)
        self.assertEqual(response.status_code, 404, response.text)
        self.assertEqual(response.json()["tried"], [{"url_host": "files.example.org", "reason": "private_address"}])
        self.assertIsNone(self.paper_file_id(paper_id))

    def test_redirect_to_public_host_is_followed(self):
        body = make_pdf("redirected")

        def https_open(handler, req):
            if req.full_url == "https://files.example.org/a.pdf":
                return http_response(req.full_url, 302, {"Location": "https://cdn.example.org/final.pdf"})
            if req.full_url == "https://cdn.example.org/final.pdf":
                return http_response(req.full_url, 200, {"Content-Type": "application/pdf"}, body)
            raise AssertionError("unexpected request")

        paper_id = self.add_search_paper(pdf_url="https://files.example.org/a.pdf")
        with patch.object(HTTPSHandler, "https_open", https_open):
            response = self.fetch(paper_id)
        self.assert_attached(response, body, "https://files.example.org/a.pdf")

    def test_too_many_redirects_are_rejected(self):
        def https_open(handler, req):
            count = int(req.full_url.rsplit("/", 1)[-1].split(".")[0] or 0)
            return http_response(req.full_url, 302, {"Location": "https://hop.example.org/{}.pdf".format(count + 1)})

        paper_id = self.add_search_paper(pdf_url="https://hop.example.org/0.pdf")
        with patch.object(HTTPSHandler, "https_open", https_open):
            response = self.fetch(paper_id)
        self.assertEqual(response.status_code, 404, response.text)
        self.assertEqual(response.json()["tried"], [{"url_host": "hop.example.org", "reason": "too_many_redirects"}])

    def test_already_has_pdf_returns_409_without_network(self):
        opener = self.use_routes({})
        imported = self.client.post("/api/papers/import", headers=HEADERS,
                                    files={"file": ("mine.pdf", make_pdf("own"), "application/pdf")})
        self.assertEqual(imported.status_code, 201, imported.text)
        response = self.fetch(imported.json()["id"], {"url": "https://repo.example.org/other.pdf"})
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(response.json()["detail"], "이미 PDF가 연결되어 있습니다.")
        self.assertEqual(opener.requested, [])

    def test_same_pdf_owned_by_another_paper_returns_409_without_merging(self):
        body = make_pdf("shared")
        self.use_routes({"https://repo.example.org/shared.pdf": ok(body)})
        owner = self.client.post("/api/papers/import", headers=HEADERS,
                                 files={"file": ("owner.pdf", body, "application/pdf")})
        self.assertEqual(owner.status_code, 201, owner.text)
        owner_id = owner.json()["id"]
        paper_id = self.add_search_paper(pdf_url="https://repo.example.org/shared.pdf")
        response = self.fetch(paper_id)
        self.assertEqual(response.status_code, 409, response.text)
        self.assertIn("다른 논문", response.json()["detail"])
        self.assertIsNone(self.paper_file_id(paper_id))
        self.assertIsNotNone(self.paper_file_id(owner_id))
        self.assertEqual(self.db_row("SELECT COUNT(*) AS n FROM papers WHERE file_id IS NOT NULL")["n"], 1)
        self.assertEqual(self.db_row("SELECT COUNT(*) AS n FROM files")["n"], 1)

    def test_trashed_paper_returns_404(self):
        self.use_routes({"https://repo.example.org/a.pdf": ok(make_pdf("trash"))})
        paper_id = self.add_search_paper(pdf_url="https://repo.example.org/a.pdf")
        with closing(storage.connect()) as con:
            con.execute("UPDATE papers SET deleted_at=CURRENT_TIMESTAMP WHERE id=?", (paper_id,))
            con.commit()
        response = self.fetch(paper_id)
        self.assertEqual(response.status_code, 404, response.text)

    def test_unknown_paper_returns_404(self):
        response = self.fetch("does-not-exist")
        self.assertEqual(response.status_code, 404, response.text)

    def test_all_candidates_failing_returns_korean_404_without_query_strings(self):
        self.use_routes({})
        paper_id = self.add_search_paper(pdf_url="https://repo.example.org/a.pdf?token=abc123",
                                         source="arxiv", source_id="http://arxiv.org/abs/2301.00003")
        response = self.fetch(paper_id)
        self.assertEqual(response.status_code, 404, response.text)
        payload = response.json()
        self.assertEqual(payload["detail"], "공개 PDF를 찾지 못했습니다. 출판사 페이지에서 직접 받아 등록해 주세요.")
        self.assertEqual(payload["tried"], [
            {"url_host": "repo.example.org", "reason": "http_404"},
            {"url_host": "arxiv.org", "reason": "http_404"},
        ])
        self.assertNotIn("abc123", response.text)
        self.assertIsNone(self.paper_file_id(paper_id))


if __name__ == "__main__":
    unittest.main()
