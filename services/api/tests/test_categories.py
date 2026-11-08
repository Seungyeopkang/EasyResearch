"""Categories: CRUD, rule classification, user decisions, and OpenAlex topics (network mocked)."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import categories, scholarly, storage
from app.main import app


def openalex_work(title="Some study", doi="https://doi.org/10.1000/x", topics=None, keywords=None):
    return {"id": "https://openalex.org/W1", "display_name": title, "doi": doi,
            "topics": topics if topics is not None else [
                {"id": "https://openalex.org/T1", "display_name": "Image Segmentation", "score": 0.91,
                 "subfield": {"display_name": "Computer Vision"}, "field": {"display_name": "Computer Science"}},
                {"id": "https://openalex.org/T2", "display_name": "Protein Folding", "score": 0.2,
                 "subfield": {"display_name": "Biophysics"}, "field": {"display_name": "Biology"}},
            ],
            "keywords": keywords if keywords is not None else [
                {"id": "https://openalex.org/keywords/k1", "display_name": "Quantum Annealing", "score": 0.5}]}


class CategoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"EASYRESEARCH_DATA_DIR": self.temp.name})
        self.env.start()
        os.environ.pop("OPENALEX_API_KEY", None)  # keep the developer's real key out of the tests
        self.client = TestClient(app)
        self.client.__enter__()
        self.h = {"X-EasyResearch": "1"}

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.env.stop()
        self.temp.cleanup()

    # helpers
    def manual(self, title, abstract_pages=None, doi=None):
        response = self.client.post("/api/papers", json={"title": title, "authors": [], "doi": doi}, headers=self.h)
        self.assertEqual(response.status_code, 201, response.text)
        paper_id = response.json()["id"]
        if abstract_pages:
            with storage.transaction() as con:
                for index, text in abstract_pages.items():
                    con.execute("INSERT INTO pages(paper_id,page_index,label,text,rotation,status) VALUES(?,?,?,?,0,'ok')",
                                (paper_id, index, None, text))
        return paper_id

    def category_id(self, name):
        with storage.transaction() as con:
            return con.execute("SELECT id FROM categories WHERE name=?", (name,)).fetchone()[0]

    def create(self, name, keywords=()):
        return self.client.post("/api/categories", json={"name": name, "keywords": list(keywords)}, headers=self.h)

    def paper_rows(self, paper_id):
        with storage.transaction() as con:
            return [dict(r) for r in con.execute("SELECT * FROM paper_categories WHERE paper_id=?", (paper_id,))]

    def set_status(self, paper_id, category_id, status):
        return self.client.put(f"/api/papers/{paper_id}/categories/{category_id}", json={"status": status}, headers=self.h)

    def openalex_fetch(self, paper_id, work=None, records=None):
        """Patch scholarly._get so the lookup returns a DOI record or a title search result."""
        if work is not None:
            body = json.dumps(work).encode()
        else:
            body = json.dumps({"results": records or []}).encode()
        return patch.object(scholarly, "_get", return_value=body)

    # CRUD

    def test_crud_duplicate_names_and_validation(self):
        created = self.create("연구 주제", ["alpha", "Beta", "beta", "  gamma   delta "])
        self.assertEqual(created.status_code, 201, created.text)
        body = created.json()
        self.assertEqual(body["keywords"], ["alpha", "Beta", "gamma delta"])
        self.assertEqual((body["suggested_count"], body["confirmed_count"]), (0, 0))
        self.assertEqual(self.create("연구 주제").status_code, 409)
        self.assertEqual(self.create("  연구 주제  ").status_code, 409)
        self.assertEqual(self.create("").status_code, 422)
        self.assertEqual(self.create("x" * 61).status_code, 422)
        self.assertEqual(self.create("ok", ["x" * 81]).status_code, 422)
        self.assertEqual(self.create("ok", [""]).status_code, 422)
        self.assertEqual(self.create("ok", [str(i) for i in range(51)]).status_code, 422)
        other = self.create("Other").json()
        renamed = self.client.patch(f"/api/categories/{other['id']}", json={"name": "연구 주제"}, headers=self.h)
        self.assertEqual(renamed.status_code, 409)
        renamed = self.client.patch(f"/api/categories/{other['id']}", json={"name": "Renamed", "keywords": ["k"]}, headers=self.h)
        self.assertEqual(renamed.status_code, 200, renamed.text)
        self.assertEqual((renamed.json()["name"], renamed.json()["keywords"]), ("Renamed", ["k"]))
        self.assertEqual(self.client.patch(f"/api/categories/{other['id']}", json={"name": None}, headers=self.h).status_code, 422)
        self.assertEqual(self.client.patch("/api/categories/missing", json={"name": "z"}, headers=self.h).status_code, 404)
        names = [c["name"] for c in self.client.get("/api/categories").json()]
        self.assertIn("최적화", names)
        self.assertEqual(names, sorted(names, key=str.casefold))

    def test_defaults_are_listed_and_counts_only_include_suggested_and_confirmed(self):
        paper = self.manual("Efficient pruning of networks")
        self.client.post(f"/api/papers/{paper}/classify", headers=self.h)
        lightweight = self.category_id("경량화")
        listing = {c["id"]: c for c in self.client.get("/api/categories").json()}
        self.assertEqual(listing[lightweight]["suggested_count"], 1)
        self.set_status(paper, lightweight, "rejected")
        listing = {c["id"]: c for c in self.client.get("/api/categories").json()}
        self.assertEqual((listing[lightweight]["suggested_count"], listing[lightweight]["confirmed_count"]), (0, 0))
        self.set_status(paper, lightweight, "confirmed")
        listing = {c["id"]: c for c in self.client.get("/api/categories").json()}
        self.assertEqual(listing[lightweight]["confirmed_count"], 1)
        self.client.delete(f"/api/papers/{paper}", headers=self.h)
        listing = {c["id"]: c for c in self.client.get("/api/categories").json()}
        self.assertEqual(listing[lightweight]["confirmed_count"], 0)

    def test_delete_category_removes_its_paper_rows(self):
        paper = self.manual("Pruning study")
        cid = self.create("Temp", ["pruning"]).json()["id"]
        self.client.post(f"/api/papers/{paper}/classify", headers=self.h)
        self.assertEqual(self.set_status(paper, cid, "confirmed").status_code, 200)
        self.assertEqual(self.client.delete(f"/api/categories/{cid}", headers=self.h).status_code, 204)
        self.assertEqual(self.client.delete(f"/api/categories/{cid}", headers=self.h).status_code, 404)
        self.assertEqual([r for r in self.paper_rows(paper) if r["category_id"] == cid], [])
        with storage.transaction() as con:
            self.assertEqual(con.execute("SELECT count(*) FROM paper_categories WHERE category_id=?", (cid,)).fetchone()[0], 0)

    # rule matching

    def test_whole_word_matching_and_hangul_substring(self):
        cid = self.create("Words", ["pruning", "gan", "양자화", "low-rank"]).json()["id"]
        paper = self.manual("Organ images and imagine")
        self.client.post(f"/api/papers/{paper}/classify", headers=self.h)
        self.assertEqual([r for r in self.paper_rows(paper) if r["category_id"] == cid], [])
        paper2 = self.manual("Pruning and a GAN, low-rank factors")
        result = self.client.post(f"/api/papers/{paper2}/classify", headers=self.h).json()
        row = next(r for r in result if r["id"] == cid)
        self.assertEqual((row["status"], row["source"]), ("suggested", "rule"))
        self.assertEqual(row["matched"], ["gan", "low-rank", "pruning"])
        paper3 = self.manual("양자화를 적용한 모델")
        result = self.client.post(f"/api/papers/{paper3}/classify", headers=self.h).json()
        self.assertEqual(next(r for r in result if r["id"] == cid)["matched"], ["양자화"])

    def test_inflection_variants_match_and_report_the_keyword(self):
        positives = [
            ("pruning", "we prune the network"), ("pruning", "pruned weights"), ("pruning", "the pruning step"),
            ("quantization", "quantized models"), ("quantization", "quantize the weights"),
            ("distillation", "distilled student"), ("distillation", "to distill knowledge"),
            ("optimizer", "several optimizers"), ("optimizer", "an optimizer step"),
            ("detection", "object detections"), ("detection", "detected objects"),
            ("image", "many images"), ("text", "texts and texts"), ("compression", "compressed networks"),
            ("knowledge distillation", "knowledge distillations were studied"),
            ("language model", "language models"), ("low-rank", "low-ranks"),
        ]
        negatives = [
            ("text", "a texture map"), ("image", "we imagine a world"), ("gan", "the organ grows"),
            ("vision", "visual cues"), ("pruning", "pruneless design"),
            ("optimizer", "optimal solution"),
            ("quantization", "quantum computing"), ("knowledge distillation", "distillation alone"),
            ("detection", "detector module"), ("adam", "adamant claims"),
        ]
        for keyword, text in positives:
            self.assertTrue(categories._keyword_matches(keyword, text), (keyword, text))
        for keyword, text in negatives:
            self.assertFalse(categories._keyword_matches(keyword, text), (keyword, text))
        cid = self.create("Variants", ["pruning", "text"]).json()["id"]
        paper = self.manual("We prune and prune again, but no texture work")
        row = next(r for r in self.client.post(f"/api/papers/{paper}/classify", headers=self.h).json() if r["id"] == cid)
        self.assertEqual(row["matched"], ["pruning"])
        self.assertNotIn("text", row["matched"])

    def test_matched_list_is_sorted_and_capped_at_ten(self):
        keywords = ["kw{:02d}".format(i) for i in range(12)]
        cid = self.create("Many", keywords).json()["id"]
        paper = self.manual(" ".join(keywords))
        row = next(r for r in self.client.post(f"/api/papers/{paper}/classify", headers=self.h).json() if r["id"] == cid)
        self.assertEqual(row["matched"], sorted(keywords)[:10])

    def test_only_title_abstract_topics_and_first_three_pages_are_used(self):
        cid = self.create("Only early", ["zebra"]).json()["id"]
        paper = self.manual("Plain title", abstract_pages={0: "intro", 2: "zebra appears here", 3: "zebra on page four"})
        self.client.post(f"/api/papers/{paper}/classify", headers=self.h)
        self.assertEqual([r["category_id"] for r in self.paper_rows(paper) if r["category_id"] == cid], [cid])
        paper_late = self.manual("Plain", abstract_pages={3: "zebra only late"})
        self.client.post(f"/api/papers/{paper_late}/classify", headers=self.h)
        self.assertEqual([r for r in self.paper_rows(paper_late) if r["category_id"] == cid], [])

    def test_reclassify_keeps_user_decisions_and_removes_stale_suggestions(self):
        confirmed_cat = self.create("Confirm me", ["lighthouse"]).json()["id"]
        rejected_cat = self.create("Reject me", ["lantern"]).json()["id"]
        stale_cat = self.create("Stale", ["compass"]).json()["id"]
        paper = self.manual("lighthouse lantern compass")
        self.client.post(f"/api/papers/{paper}/classify", headers=self.h)
        self.assertEqual(self.set_status(paper, confirmed_cat, "confirmed").status_code, 200)
        self.assertEqual(self.set_status(paper, rejected_cat, "rejected").status_code, 200)
        # Rewrite the title so only the confirmed/rejected keywords and a fresh one remain.
        with storage.transaction() as con:
            con.execute("UPDATE papers SET title='lighthouse lantern ship' WHERE id=?", (paper,))
        self.client.post(f"/api/papers/{paper}/classify", headers=self.h)
        rows = {r["category_id"]: r for r in self.paper_rows(paper)}
        self.assertEqual(rows[confirmed_cat]["status"], "confirmed")
        self.assertEqual(rows[rejected_cat]["status"], "rejected")
        self.assertNotIn(stale_cat, rows)
        # A rejected category never comes back through reclassification.
        self.client.post("/api/library/classify", headers=self.h)
        self.assertEqual({r["category_id"]: r["status"] for r in self.paper_rows(paper)}[rejected_cat], "rejected")
        listing = self.client.get(f"/api/papers/{paper}/categories").json()
        self.assertIn(("rejected", rejected_cat), [(r["status"], r["id"]) for r in listing])

    def test_manual_decision_keeps_existing_source_and_delete_resets(self):
        paper = self.manual("Gradient descent with Adam")
        cid = self.category_id("최적화")
        self.client.post(f"/api/papers/{paper}/classify", headers=self.h)
        row = self.set_status(paper, cid, "confirmed").json()
        self.assertEqual((row["status"], row["source"]), ("confirmed", "rule"))
        other = self.manual("Nothing to see here")
        row = self.set_status(other, cid, "rejected").json()
        self.assertEqual((row["status"], row["source"]), ("rejected", "manual"))
        self.assertEqual(self.set_status(other, cid, "maybe").status_code, 422)
        self.assertEqual(self.set_status("missing", cid, "confirmed").status_code, 404)
        self.assertEqual(self.set_status(other, "missing", "confirmed").status_code, 404)
        self.assertEqual(self.client.delete(f"/api/papers/{other}/categories/{cid}", headers=self.h).status_code, 204)
        self.assertEqual(self.paper_rows(other), [])
        self.assertEqual(self.client.get(f"/api/papers/{other}/categories").json(), [])
        self.assertEqual(self.client.get("/api/papers/missing/categories").status_code, 404)

    def test_reading_status_read_triggers_classification(self):
        paper = self.manual("Quantization and pruning for mobile devices")
        cid = self.category_id("경량화")
        self.assertEqual(self.paper_rows(paper), [])
        response = self.client.patch(f"/api/papers/{paper}", json={"reading_status": "read"}, headers=self.h)
        self.assertEqual(response.status_code, 200, response.text)
        rows = {r["category_id"]: r for r in self.paper_rows(paper)}
        self.assertEqual(rows[cid]["status"], "suggested")
        self.assertEqual(json.loads(rows[cid]["matched_json"]), ["mobile", "pruning", "quantization"])
        library = self.client.get("/api/library/papers", params={"category_id": cid}).json()
        self.assertEqual([item["id"] for item in library], [paper])

    def test_classify_all_counts_only_live_papers(self):
        live = self.manual("Knowledge distillation")
        trashed = self.manual("Knowledge distillation twin")
        self.assertEqual(self.client.delete(f"/api/papers/{trashed}", headers=self.h).status_code, 204)
        result = self.client.post("/api/library/classify", headers=self.h)
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json(), {"classified": 1})
        self.assertTrue(any(r["status"] == "suggested" for r in self.paper_rows(live)))
        self.assertEqual(self.client.post(f"/api/papers/{trashed}/classify", headers=self.h).status_code, 404)

    # OpenAlex topics

    def test_topics_fetch_by_doi_stores_topics_and_feeds_classification(self):
        paper = self.manual("Unrelated heading", doi="10.1000/X-9")
        with self.openalex_fetch(paper, work=openalex_work()) as fetch:
            response = self.client.post(f"/api/papers/{paper}/topics/fetch", headers=self.h)
        self.assertEqual(response.status_code, 200, response.text)
        url = fetch.call_args.args[1]
        self.assertTrue(url.startswith("https://api.openalex.org/works/doi:10.1000/x-9?"), url)
        self.assertIn("select=", url)
        self.assertIsNone(fetch.call_args.args[2])
        body = response.json()
        self.assertEqual({(t["source"], t["name"]) for t in body["topics"]},
                         {("openalex", "Image Segmentation"), ("openalex", "Protein Folding"),
                          ("openalex_keyword", "Quantum Annealing")})
        cv = self.category_id("컴퓨터 비전")
        self.assertIn(cv, {c["id"] for c in body["categories"]})
        cat = next(c for c in body["categories"] if c["id"] == cv)
        self.assertEqual((cat["status"], cat["source"]), ("suggested", "rule"))
        # "Image Segmentation" (topic) matches "image" and "segmentation"; "Computer Vision" (subfield) matches "vision".
        self.assertEqual(cat["matched"], ["image", "segmentation", "vision"])

    def test_topics_fetch_by_title_requires_exact_normalized_match(self):
        paper = self.manual("A Study: On  Pruning!")
        match = openalex_work(title="a study on pruning")
        with self.openalex_fetch(paper, records=[match]) as fetch:
            response = self.client.post(f"/api/papers/{paper}/topics/fetch", headers=self.h)
        self.assertEqual(response.status_code, 200, response.text)
        url = fetch.call_args.args[1]
        self.assertIn("api.openalex.org/works?", url)
        self.assertIn("per-page=1", url)
        self.assertNotIn("doi", url)
        self.assertEqual(len(response.json()["topics"]), 3)

        other = self.manual("A Study on Pruning Methods")
        with self.openalex_fetch(other, records=[match]):
            response = self.client.post(f"/api/papers/{other}/topics/fetch", headers=self.h)
        self.assertEqual(response.status_code, 404, response.text)
        self.assertEqual(response.json()["detail"], "OpenAlex에서 같은 제목의 논문을 찾지 못했습니다.")
        with self.openalex_fetch(other, records=[]):
            self.assertEqual(self.client.post(f"/api/papers/{other}/topics/fetch", headers=self.h).status_code, 404)

    def test_topics_refetch_replaces_previous_openalex_rows_only(self):
        paper = self.manual("Title", doi="10.1000/abc")
        with self.openalex_fetch(paper, work=openalex_work()):
            self.client.post(f"/api/papers/{paper}/topics/fetch", headers=self.h)
        with storage.transaction() as con:
            con.execute("INSERT INTO paper_topics(paper_id,source,topic_id,name) VALUES(?,'manual','M1','Manual')", (paper,))
        with self.openalex_fetch(paper, work=openalex_work(topics=[], keywords=[])):
            body = self.client.post(f"/api/papers/{paper}/topics/fetch", headers=self.h).json()
        self.assertEqual(body["topics"], [])
        with storage.transaction() as con:
            names = [r[0] for r in con.execute("SELECT name FROM paper_topics WHERE paper_id=?", (paper,))]
        self.assertEqual(names, ["Manual"])

    def test_openalex_errors_are_mapped_to_korean_http_errors(self):
        paper = self.manual("Mapped", doi="10.1000/err")
        cases = [("not_found", 404), ("rate_limited", 429), ("timeout", 502), ("network_error", 502), ("invalid_response", 502)]
        for code, status in cases:
            error = scholarly.ScholarlyError("openalex", code, "raw")
            with patch.object(scholarly, "_get", side_effect=error):
                response = self.client.post(f"/api/papers/{paper}/topics/fetch", headers=self.h)
            self.assertEqual(response.status_code, status, (code, response.text))
            self.assertIsInstance(response.json()["detail"], str)
        titled = self.manual("No DOI title")
        with patch.object(scholarly, "_get", side_effect=scholarly.ScholarlyError("openalex", "rate_limited", "raw")):
            self.assertEqual(self.client.post(f"/api/papers/{titled}/topics/fetch", headers=self.h).status_code, 429)

    def test_topics_fetch_sends_api_key_only_when_configured(self):
        paper = self.manual("Keyed", doi="10.1000/key")
        with patch.dict(os.environ, {"OPENALEX_API_KEY": "secret-key"}):
            with self.openalex_fetch(paper, work=openalex_work()) as fetch:
                self.client.post(f"/api/papers/{paper}/topics/fetch", headers=self.h)
        self.assertEqual(fetch.call_args.args[2], {"Authorization": "Bearer secret-key"})
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("OPENALEX_API_KEY", None)
            with self.openalex_fetch(paper, work=openalex_work()) as fetch:
                self.client.post(f"/api/papers/{paper}/topics/fetch", headers=self.h)
        self.assertIsNone(fetch.call_args.args[2])

    def test_topics_fetch_rejects_missing_or_trashed_paper_without_network(self):
        with patch.object(scholarly, "_get") as fetch:
            self.assertEqual(self.client.post("/api/papers/missing/topics/fetch", headers=self.h).status_code, 404)
            paper = self.manual("Trash me", doi="10.1000/t")
            self.client.delete(f"/api/papers/{paper}", headers=self.h)
            self.assertEqual(self.client.post(f"/api/papers/{paper}/topics/fetch", headers=self.h).status_code, 404)
            fetch.assert_not_called()

    def test_writes_require_local_header(self):
        self.assertEqual(self.client.post("/api/categories", json={"name": "No header"}).status_code, 403)


if __name__ == "__main__":
    unittest.main()
