"""OpenAlex key storage and precedence (AC10), budget headers and cache (AC11).

Network is faked at scholarly.urlopen. The key is a fake value and is checked for leaks in every response,
the SQLite database, every file under the temporary data folder, and the backup archive.
"""
import datetime
import json
import os
import sqlite3
import sys
import tempfile
import unittest
import zipfile
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import categories, scholarly
from app.main import app

FILE_KEY = "file-openalex-KEY-0123456789"
ENV_KEY = "env-openalex-KEY-abcdefghij"
BUDGET_HEADERS = {"X-RateLimit-Remaining-USD": "0.42", "X-RateLimit-Limit-USD": "1.00",
                  "X-RateLimit-Reset": "3600", "X-RateLimit-Credits-Used": "58", "X-RateLimit-Cost-USD": "0.0001"}
WORKS = json.dumps({"results": [{"id": "https://openalex.org/W9", "display_name": "Cached study",
                                 "publication_year": 2024, "doi": None, "authorships": [],
                                 "abstract_inverted_index": None, "best_oa_location": None}]}).encode("utf-8")


class FakeResponse:
    def __init__(self, body, headers):
        self.body = body
        self.headers = headers

    def read(self, _size=-1):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class OpenAlexSettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"EASYRESEARCH_DATA_DIR": self.temp.name})
        self.env.start()
        os.environ.pop("OPENALEX_API_KEY", None)
        self.client = TestClient(app)
        self.client.__enter__()
        self.h = {"X-EasyResearch": "1"}
        self.requests = []
        self.responses = []  # queue of exceptions to raise, popped per call; empty means a normal response
        self.clock = [1000.0]
        scholarly.clear_openalex_cache()
        scholarly._budget = None
        self.urlopen_patch = patch.object(scholarly, "urlopen", side_effect=self.fake_urlopen)
        self.urlopen_patch.start()
        self.now_patch = patch.object(scholarly, "_now", side_effect=lambda: self.clock[0])
        self.now_patch.start()

    def tearDown(self):
        self.now_patch.stop()
        self.urlopen_patch.stop()
        scholarly.clear_openalex_cache()
        scholarly._budget = None
        self.client.__exit__(None, None, None)
        self.env.stop()
        self.temp.cleanup()

    def fake_urlopen(self, request, timeout=None):
        self.requests.append(request)
        if self.responses:
            raise self.responses.pop(0)
        return FakeResponse(WORKS, dict(BUDGET_HEADERS))

    @property
    def secret_file(self):
        return Path(self.temp.name) / "secrets" / "openalex_api_key"

    def put(self, **body):
        return self.client.put("/api/settings/openalex", json=body, headers=self.h)

    def search(self, query="neural nets"):
        params = {"q": query}
        return self.client.get("/api/search", params=params)

    # ---- AC10: storage and precedence

    def test_put_stores_key_in_secrets_file_and_get_reports_file_source(self):  # AC10
        response = self.put(api_key=FILE_KEY)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertNotIn(FILE_KEY, response.text)
        self.assertEqual(response.json()["has_key"], True)
        self.assertEqual(response.json()["source"], "file")
        self.assertEqual(self.secret_file.read_text(encoding="utf-8"), FILE_KEY)
        got = self.client.get("/api/settings/openalex")
        self.assertEqual(got.status_code, 200)
        self.assertTrue(got.json()["has_key"])
        self.assertEqual(got.json()["source"], "file")
        self.assertNotIn(FILE_KEY, got.text)
        self.assertIn("free_key_url", got.json())
        self.assertIn("keyless_note", got.json())

    def test_key_never_appears_in_responses_database_files_or_backup(self):  # AC10
        self.assertEqual(self.put(api_key=FILE_KEY).status_code, 200)
        self.assertNotIn(FILE_KEY, self.client.get("/api/settings/openalex").text)
        backup = self.client.post("/api/backups", headers=self.h)
        self.assertEqual(backup.status_code, 201, backup.text)
        self.assertNotIn(FILE_KEY, backup.text)
        archive = Path(self.temp.name) / "backups" / (backup.json()["id"] + ".zip")
        self.assertTrue(archive.is_file())
        with zipfile.ZipFile(archive) as zf:
            names = zf.namelist()
            self.assertFalse(any("openalex" in name or "secrets" in name for name in names), names)
            for name in names:
                self.assertNotIn(FILE_KEY.encode("utf-8"), zf.read(name), name)
        self.assertNotIn(FILE_KEY.encode("utf-8"), archive.read_bytes())
        with closing(sqlite3.connect(str(Path(self.temp.name) / "library.sqlite3"))) as con:
            dump = "\n".join(con.iterdump())
        self.assertNotIn(FILE_KEY, dump)
        # Every other file in the data folder (database, logs, backups) must be free of the key.
        for path in Path(self.temp.name).rglob("*"):
            if path.is_file() and path != self.secret_file and path.suffix != ".lock":
                self.assertNotIn(FILE_KEY.encode("utf-8"), path.read_bytes(), str(path))

    def test_environment_key_wins_over_file(self):  # AC10
        self.assertEqual(self.put(api_key=FILE_KEY).status_code, 200)
        with patch.dict(os.environ, {"OPENALEX_API_KEY": "  " + ENV_KEY + "  "}):
            got = self.client.get("/api/settings/openalex")
            self.assertEqual(got.json()["source"], "env")
            self.assertTrue(got.json()["has_key"])
            self.assertNotIn(ENV_KEY, got.text)
            self.assertNotIn(FILE_KEY, got.text)
            self.assertEqual(self.search("env wins").status_code, 200)
        self.assertEqual(self.requests[-1].get_header("Authorization"), "Bearer " + ENV_KEY)

    def test_search_sends_file_key_as_bearer_header(self):  # AC10
        self.put(api_key=FILE_KEY)
        scholarly.search_openalex("file key search", 5)
        self.assertEqual(self.requests[-1].get_header("Authorization"), "Bearer " + FILE_KEY)
        self.assertNotIn(FILE_KEY, self.requests[-1].full_url)

    def test_category_lookup_uses_the_same_key_source(self):  # AC10
        self.assertIsNone(categories._openalex_headers())
        self.put(api_key=FILE_KEY)
        self.assertEqual(categories._openalex_headers(), {"Authorization": "Bearer " + FILE_KEY})

    def test_invalid_keys_are_rejected_with_422(self):  # AC10
        for bad in ("short", "has space 12345678", "비밀키한글키입니다12345", "x" * 201, "tab\tkey12345"):
            with self.subTest(bad=bad[:20]):
                response = self.put(api_key=bad)
                self.assertEqual(response.status_code, 422, response.text)
        self.assertFalse(self.secret_file.exists())

    def test_clear_key_removes_the_file(self):  # AC10
        self.put(api_key=FILE_KEY)
        cleared = self.put(clear_key=True)
        self.assertEqual(cleared.status_code, 200, cleared.text)
        self.assertFalse(cleared.json()["has_key"])
        self.assertIsNone(cleared.json()["source"])
        self.assertFalse(self.secret_file.exists())

    # ---- AC11: budget, cache, 429

    def test_budget_headers_are_exposed_with_keyed_flag(self):  # AC11
        self.put(api_key=FILE_KEY)
        self.assertEqual(self.search("budget probe").status_code, 200)
        budget = self.client.get("/api/settings/openalex").json()["budget"]
        self.assertEqual(budget["remaining_usd"], 0.42)
        self.assertEqual(budget["limit_usd"], 1.0)
        self.assertEqual(budget["reset_seconds"], 3600)
        self.assertEqual(budget["credits_used"], 58)
        self.assertEqual(budget["cost_usd"], 0.0001)
        self.assertIs(budget["keyed"], True)
        observed = datetime.datetime.strptime(budget["observed_at"], "%Y-%m-%dT%H:%M:%SZ")
        self.assertLess(abs((datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) - observed).total_seconds()), 600)

    def test_keyless_request_is_recorded_as_not_keyed(self):  # AC11
        self.assertEqual(self.search("keyless probe").status_code, 200)
        self.assertIs(self.client.get("/api/settings/openalex").json()["budget"]["keyed"], False)

    def test_identical_query_is_cached_until_ttl(self):  # AC11
        scholarly.search_openalex("Neural  Nets", 5)
        scholarly.search_openalex("neural nets", 5)
        self.assertEqual(len(self.requests), 1, "same normalized query must not refetch")
        scholarly.search_openalex("neural nets", 6)
        self.assertEqual(len(self.requests), 2, "a different limit is a different query")
        scholarly.search_openalex("neural nets beyond", 5)
        self.assertEqual(len(self.requests), 3, "a different query must fetch")
        self.assertEqual(scholarly.search_openalex("neural nets", 5)[0]["title"], "Cached study")
        self.assertEqual(len(self.requests), 3)

    def test_cache_returns_copies_and_expires_after_ttl(self):  # AC11
        first = scholarly.search_openalex("ttl query", 5)
        first[0]["title"] = "mutated by caller"
        self.assertEqual(scholarly.search_openalex("ttl query", 5)[0]["title"], "Cached study")
        self.assertEqual(len(self.requests), 1)
        self.clock[0] += scholarly.OPENALEX_CACHE_TTL_SECONDS - 1
        scholarly.search_openalex("ttl query", 5)
        self.assertEqual(len(self.requests), 1, "still inside the TTL")
        self.clock[0] += 2
        scholarly.search_openalex("ttl query", 5)
        self.assertEqual(len(self.requests), 2, "expired entry must be fetched again")

    def test_failed_responses_are_not_cached(self):  # AC11
        self.responses.append(HTTPError("https://api.openalex.org", 500, "boom", {}, None))
        with self.assertRaises(scholarly.ScholarlyError):
            scholarly.search_openalex("flaky query", 5)
        self.assertEqual(scholarly.search_openalex("flaky query", 5)[0]["title"], "Cached study")
        self.assertEqual(len(self.requests), 2)

    def test_429_becomes_rate_limited_with_free_key_message(self):  # AC11
        budget_empty = {"X-RateLimit-Remaining-USD": "0", "X-RateLimit-Limit-USD": "0.10", "X-RateLimit-Reset": "900"}
        self.responses.append(HTTPError("https://api.openalex.org", 429, "Too Many Requests", budget_empty, None))
        with self.assertRaises(scholarly.ScholarlyError) as error:
            scholarly.search_openalex("limited query", 5)
        self.assertEqual(error.exception.code, "rate_limited")
        self.assertEqual(error.exception.status, 429)
        self.assertIn("무료 OpenAlex 키", error.exception.message)
        self.assertNotIn("Too Many", error.exception.message)

    def test_search_route_returns_429_with_free_key_message(self):  # AC11
        self.responses.append(HTTPError("https://api.openalex.org", 429, "Too Many Requests",
                                        {"X-RateLimit-Remaining-USD": "0"}, None))
        response = self.search("route limited")
        self.assertEqual(response.status_code, 429, response.text)
        detail = response.json()["detail"]
        self.assertEqual(detail["code"], "rate_limited")
        self.assertIn("무료 OpenAlex 키", detail["message"])
        self.assertEqual(self.client.get("/api/settings/openalex").json()["budget"]["remaining_usd"], 0.0)

    def test_mutating_settings_require_custom_header(self):
        response = self.client.put("/api/settings/openalex", json={"api_key": FILE_KEY})
        self.assertEqual(response.status_code, 403)
        self.assertFalse(self.secret_file.exists())


if __name__ == "__main__":
    unittest.main()
