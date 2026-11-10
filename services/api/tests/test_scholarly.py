import json
import socket
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import scholarly


OPENALEX = {"results": [{"id": "https://openalex.org/W1", "display_name": "A Study",
    "publication_year": 2024, "doi": "https://doi.org/10.1234/ABC",
    "authorships": [{"author": {"display_name": "A. Author"}}],
    "abstract_inverted_index": {"world": [1], "Hello": [0, 2]},
    "best_oa_location": {"landing_page_url": "https://example.org/paper", "pdf_url": "https://example.org/paper.pdf"}}]}
ARXIV = b'''<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
<entry><id>https://arxiv.org/abs/1234.56789v2</id><title> A\n Study </title>
<published>2023-01-02T00:00:00Z</published><summary> First\n result. </summary>
<author><name>A. Author</name></author><arxiv:doi>10.1234/ABC</arxiv:doi>
<link title="pdf" href="https://arxiv.org/pdf/1234.56789v2"/></entry></feed>'''
CROSSREF = {"message": {"DOI": "10.1234/ABC", "title": ["A Study"],
    "author": [{"given": "A.", "family": "Author"}],
    "published": {"date-parts": [[2021, 2]]}, "URL": "https://doi.org/10.1234/ABC"}}


class ScholarlyTests(unittest.TestCase):
    def setUp(self):
        # search_openalex caches successful results in memory; each test starts empty.
        # The key lookup is pinned so the developer's real key or env var never affects a test.
        scholarly.clear_openalex_cache()
        self.key_patch = patch.object(scholarly, "openalex_key", return_value=None)
        self.key_patch.start()

    def tearDown(self):
        self.key_patch.stop()
        scholarly.clear_openalex_cache()

    def test_openalex_normalization_and_key_header(self):
        with patch.object(scholarly, "_get", return_value=json.dumps(OPENALEX).encode()) as fetch:
            result = scholarly.search_openalex("neural nets", 5, "secret")[0]
        self.assertEqual(result["authors"], ["A. Author"])
        self.assertEqual(result["abstract"], "Hello world Hello")
        self.assertEqual(result["doi"], "10.1234/abc")
        self.assertEqual(result["source_record"], OPENALEX["results"][0])
        self.assertEqual(fetch.call_args.args[2]["Authorization"], "Bearer secret")
        self.assertNotIn("secret", fetch.call_args.args[1])
        self.assertEqual(parse_qs(urlparse(fetch.call_args.args[1]).query)["search"], ["neural nets"])

    def test_arxiv_normalization_and_query_escaping(self):
        with patch.object(scholarly, "_get", return_value=ARXIV) as fetch, patch.object(scholarly.time, "sleep"):
            result = scholarly.search_arxiv('graph "learning"', 3)[0]
        self.assertEqual(result["source"], "arxiv")
        self.assertEqual(result["title"], "A Study")
        self.assertEqual(result["year"], 2023)
        self.assertEqual(result["authors"], ["A. Author"])
        self.assertEqual(result["doi"], "10.1234/abc")
        self.assertIn("1234.56789v2", result["pdf_url"])
        self.assertIn("1234.56789v2", result["source_record"])
        params = parse_qs(urlparse(fetch.call_args.args[1]).query)
        self.assertEqual(params["search_query"], ['all:"graph  learning "'])

    def test_crossref_encoded_doi_and_normalization(self):
        with patch.object(scholarly, "_get", return_value=json.dumps(CROSSREF).encode()) as fetch:
            result = scholarly.lookup_crossref("https://doi.org/10.1234/ABC")
        self.assertEqual(result["doi"], "10.1234/abc")
        self.assertEqual(result["year"], 2021)
        self.assertEqual(result["authors"], ["A. Author"])
        self.assertTrue(fetch.call_args.args[1].endswith("10.1234%2Fabc"))
        self.assertEqual(result["source_record"], CROSSREF["message"])

    def test_empty_results_and_invalid_responses_are_distinct(self):
        with patch.object(scholarly, "_get", return_value=b'{"results": []}'):
            self.assertEqual(scholarly.search_openalex("query"), [])
        for body in (b"not json", b"{}", b'{"results": [null]}'):
            scholarly.clear_openalex_cache()  # the empty result above is cached; each body needs a fresh fetch
            with self.subTest(body=body), patch.object(scholarly, "_get", return_value=body):
                with self.assertRaises(scholarly.ScholarlyError) as error:
                    scholarly.search_openalex("query")
                self.assertEqual(error.exception.code, "invalid_response")

    def test_arxiv_error_entry_and_dtd_are_rejected(self):
        error_feed = b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>http://arxiv.org/api/errors#bad</id><title>Error</title></entry></feed>'
        for body, code in ((error_feed, "upstream_error"), (b'<!DOCTYPE feed><feed/>', "invalid_response")):
            with self.subTest(code=code), patch.object(scholarly, "_get", return_value=body), patch.object(scholarly.time, "sleep"):
                with self.assertRaises(scholarly.ScholarlyError) as error:
                    scholarly.search_arxiv("query")
                self.assertEqual(error.exception.code, code)

    def test_validation(self):
        for query, limit in (("", 10), ("x", 0), ("x", 26), ("x", True)):
            with self.subTest(query=query, limit=limit), self.assertRaises(ValueError):
                scholarly.search_openalex(query, limit)
        for doi in ("", "not-a-doi", "10.1234/with space", "10.1234/\nabc"):
            with self.subTest(doi=doi), self.assertRaises(ValueError):
                scholarly.lookup_crossref(doi)

    def test_http_and_network_error_mapping(self):
        errors = [(HTTPError("https://example.org", 404, "no", {}, None), "not_found"),
                  (HTTPError("https://example.org", 429, "no", {}, None), "rate_limited"),
                  (URLError(socket.timeout()), "timeout"), (URLError("offline"), "network_error")]
        for failure, expected in errors:
            with self.subTest(expected=expected), patch.object(scholarly, "urlopen", side_effect=failure):
                with self.assertRaises(scholarly.ScholarlyError) as error:
                    scholarly.lookup_crossref("10.1234/abc")
                self.assertEqual(error.exception.code, expected)
                self.assertEqual(error.exception.source, "crossref")


if __name__ == "__main__":
    unittest.main()
