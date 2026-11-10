"""Paper profiles, links and graph, gaps, and AI classification (LLM transport and OpenAlex mocked)."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import knowledge, llm, scholarly, storage
from app.main import app

LOCAL = {"provider": "ollama", "base_url": "http://127.0.0.1:11434", "model": "fake"}
EXTERNAL = {"provider": "openai_compatible", "base_url": "https://example.test/v1", "model": "m"}


class FakeTransport:
    def __init__(self, reply):
        self.reply = reply
        self.calls = []

    def __call__(self, config, messages, *, json_output=False, max_tokens=2000, **_):
        self.calls.append(messages)
        return self.reply(messages) if callable(self.reply) else self.reply


class KnowledgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"EASYRESEARCH_DATA_DIR": self.temp.name})
        self.env.start()
        os.environ.pop("OPENALEX_API_KEY", None)
        self.client = TestClient(app)
        self.client.__enter__()
        self.h = {"X-EasyResearch": "1"}
        self.original_transport = llm.transport
        self.fake = FakeTransport("{}")
        llm.transport = self.fake

    def tearDown(self):
        llm.transport = self.original_transport
        self.client.__exit__(None, None, None)
        self.env.stop()
        self.temp.cleanup()

    # helpers
    def paper(self, title, pages=None, abstract="", doi=None, source=None, source_id=None):
        response = self.client.post("/api/papers", json={"title": title, "authors": [], "doi": doi}, headers=self.h)
        self.assertEqual(response.status_code, 201, response.text)
        paper_id = response.json()["id"]
        with storage.transaction() as con:
            con.execute("UPDATE papers SET abstract=?, source=COALESCE(?,source), source_id=? WHERE id=?",
                        (abstract, source, source_id, paper_id))
            for index, text in (pages or {}).items():
                con.execute("INSERT INTO pages(paper_id,page_index,label,text,rotation,status) VALUES(?,?,?,?,0,'ok')",
                            (paper_id, index, None, text))
        return paper_id

    def set_config(self, config):
        llm.save_config(config)

    def profile_data(self, facets=None, summary=""):
        base = {"summary": summary, "keywords": [], "facets": {f: [] for f in knowledge.FACETS}}
        base["facets"].update(facets or {})
        return base

    def item(self, text, quote=None, page=1):
        return {"text": text, "origin": "author_stated", "evidence": [{"page": page, "quote": quote or text}]}

    def manual_profile(self, paper_id, data, origin="manual"):
        return self.client.post(f"/api/papers/{paper_id}/profile", json={"data": data, "origin": origin}, headers=self.h)

    def gaps_rules(self, ids):
        return self.client.post("/api/gaps/rules", json={"paper_ids": ids}, headers=self.h)


class ProfileTests(KnowledgeTests):
    def test_rules_profile_versions_and_exact_quotes(self):
        pid = self.paper("Pruning study", {0: "We propose a pruning method for networks. The method has a limitation: it does not handle long inputs.\nFuture work: extend to multilingual corpora."})
        response = self.client.post(f"/api/papers/{pid}/profile/rules", headers=self.h)
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["origin"], "rules")
        facets = response.json()["data"]["facets"]
        self.assertTrue(facets["method"])
        evidence = facets["method"][0]["evidence"][0]
        self.assertEqual((evidence["page"], evidence["match"]), (1, "exact"))
        self.assertIsNone(evidence["found_page"])
        self.assertTrue(facets["limitations"])
        self.assertTrue(facets["future_work"])
        self.client.post(f"/api/papers/{pid}/profile/rules", headers=self.h)
        history = self.client.get(f"/api/papers/{pid}/profile", headers=self.h).json()["history"]
        self.assertEqual(len(history), 2)

    def test_quote_verification_statuses(self):
        pid = self.paper("Verify", {0: "Alpha beta gamma delta.", 1: "Pruni-\nng works well. Other text here."})
        data = self.profile_data({"method": [{"text": "m", "origin": "inferred", "evidence": [
            {"page": 1, "quote": "Alpha beta gamma delta."},          # exact on claimed page
            {"page": 1, "quote": "PRUNING works"},                    # normalized (case + hyphen) on page 2 only
            {"page": 2, "quote": "Alpha beta gamma delta."},          # exact elsewhere -> found_page 1
            {"page": 1, "quote": "never appears anywhere"},           # not_found
        ]}]})
        with storage.transaction() as con:
            verified = knowledge.verify_quotes(con, pid, data)
        ev = verified["facets"]["method"][0]["evidence"]
        self.assertEqual((ev[0]["match"], ev[0]["found_page"]), ("exact", None))
        self.assertEqual((ev[1]["match"], ev[1]["found_page"]), ("normalized", 2))
        self.assertEqual((ev[2]["match"], ev[2]["found_page"]), ("exact", 1))
        self.assertEqual((ev[3]["match"], ev[3]["found_page"]), ("not_found", None))

    def test_manual_profile_validation_and_recomputed_match(self):
        pid = self.paper("Manual", {0: "We build a classifier for images."})
        bad_facet = self.manual_profile(pid, {"facets": {"problems": []}})
        self.assertEqual(bad_facet.status_code, 422)
        too_many = self.manual_profile(pid, {"facets": {"method": [self.item(f"m{i}") for i in range(13)]}})
        self.assertEqual(too_many.status_code, 422)
        long_text = self.manual_profile(pid, {"facets": {"method": [self.item("x" * 1001)]}})
        self.assertEqual(long_text.status_code, 422)
        long_quote = self.manual_profile(pid, {"facets": {"method": [self.item("m", quote="q" * 501)]}})
        self.assertEqual(long_quote.status_code, 422)
        unknown_item_key = self.manual_profile(pid, {"facets": {"method": [{"text": "m", "extra": 1}]}})
        self.assertEqual(unknown_item_key.status_code, 422)
        forged = {"facets": {"method": [{"text": "m", "origin": "author_stated", "evidence": [
            {"page": 1, "quote": "We build a classifier", "match": "exact", "found_page": 9}]}]}}
        ok = self.manual_profile(pid, forged)
        self.assertEqual(ok.status_code, 201, ok.text)
        ev = ok.json()["data"]["facets"]["method"][0]["evidence"][0]
        self.assertEqual((ev["match"], ev["found_page"]), ("exact", None))
        self.assertEqual(ok.json()["origin"], "manual")

    def test_latest_profile_and_status_patch(self):
        pid = self.paper("Versions", {0: "Text."})
        first = self.manual_profile(pid, {"summary": "one"}).json()
        second = self.manual_profile(pid, {"summary": "two"}, origin="agent").json()
        latest = self.client.get(f"/api/papers/{pid}/profile", headers=self.h).json()
        self.assertEqual(latest["profile"]["id"], second["id"])
        self.assertEqual(latest["profile"]["origin"], "agent")
        patched = self.client.patch(f"/api/profiles/{first['id']}", json={"status": "confirmed"}, headers=self.h)
        self.assertEqual(patched.json()["status"], "confirmed")
        self.assertEqual(self.client.patch(f"/api/profiles/{first['id']}", json={"status": "bogus"}, headers=self.h).status_code, 422)

    def test_ai_profile_local_needs_no_hash_and_verifies_quotes(self):
        pid = self.paper("AI paper", {0: "We propose a graph model. Limitation: it cannot scale.",
                                      1: "Results are strong."}, abstract="An abstract.")
        self.set_config(LOCAL)
        reply = json.dumps({"summary": "요약", "keywords": ["graph"], "facets": {
            "method": [{"text": "그래프 모델", "origin": "author_stated",
                        "evidence": [{"page": 1, "quote": "We propose a graph model."},
                                     {"page": 1, "quote": "results ARE strong."},
                                     {"page": 1, "quote": "invented sentence"}]}],
            "bogus": [{"text": "x"}],
        }})
        self.fake.reply = reply
        response = self.client.post(f"/api/papers/{pid}/profile/ai", json={}, headers=self.h)
        self.assertEqual(response.status_code, 201, response.text)
        body = response.json()
        self.assertEqual(body["origin"], "llm")
        self.assertEqual(body["model"], "fake")
        evidence = body["data"]["facets"]["method"][0]["evidence"]
        self.assertEqual([e["match"] for e in evidence], ["exact", "normalized", "not_found"])
        self.assertEqual(evidence[1]["found_page"], 2)
        self.assertNotIn("bogus", body["data"]["facets"])
        messages = self.fake.calls[-1]
        self.assertIn(llm.UNTRUSTED_RULE, messages[0]["content"])
        self.assertIn('<document label="page 1">', messages[1]["content"])
        self.assertIn("We propose a graph model.", messages[1]["content"])

    def test_ai_profile_external_requires_matching_hash(self):
        pid = self.paper("External", {0: "We propose a method for things."})
        self.set_config(EXTERNAL)
        self.fake.reply = json.dumps({"summary": "s", "facets": {"method": [
            {"text": "m", "evidence": [{"page": 1, "quote": "We propose a method for things."}]}]}})
        preview = self.client.post(f"/api/papers/{pid}/profile/ai/preview", headers=self.h)
        self.assertEqual(preview.status_code, 200, preview.text)
        self.assertTrue(preview.json()["external"])
        self.assertEqual(self.client.post(f"/api/papers/{pid}/profile/ai", json={}, headers=self.h).status_code, 409)
        self.assertEqual(self.client.post(f"/api/papers/{pid}/profile/ai", json={"preview_hash": "0" * 64},
                                          headers=self.h).status_code, 409)
        self.assertEqual(len(self.fake.calls), 0)
        ok = self.client.post(f"/api/papers/{pid}/profile/ai", json={"preview_hash": preview.json()["preview_hash"]},
                              headers=self.h)
        self.assertEqual(ok.status_code, 201, ok.text)
        with storage.transaction() as con:
            stored = con.execute("SELECT input_hash FROM paper_profiles WHERE id=?", (ok.json()["id"],)).fetchone()
        self.assertEqual(stored["input_hash"], preview.json()["preview_hash"])

    def test_provider_none_gives_400_but_rules_work(self):
        pid = self.paper("No AI", {0: "We propose something."})
        self.assertEqual(self.client.post(f"/api/papers/{pid}/profile/ai/preview", headers=self.h).status_code, 400)
        self.assertEqual(self.client.post(f"/api/papers/{pid}/profile/ai", json={}, headers=self.h).status_code, 400)
        self.assertEqual(self.client.post(f"/api/papers/{pid}/profile/rules", headers=self.h).status_code, 201)

    def test_ai_profile_with_nothing_valid_returns_502(self):
        pid = self.paper("Garbage", {0: "Text."})
        self.set_config(LOCAL)
        self.fake.reply = json.dumps({"facets": {"method": [{"text": "", "evidence": []}]}})
        response = self.client.post(f"/api/papers/{pid}/profile/ai", json={}, headers=self.h)
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["detail"]["code"], "invalid_response")


class LinkTests(KnowledgeTests):
    def test_link_crud_duplicates_and_self_link(self):
        a = self.paper("A")
        b = self.paper("B")
        created = self.client.post("/api/paper-links", json={"source_paper_id": a, "target_paper_id": b,
                                                            "relation": "extends"}, headers=self.h)
        self.assertEqual(created.status_code, 201, created.text)
        self.assertEqual(created.json()["status"], "accepted")
        self.assertEqual(self.client.post("/api/paper-links", json={"source_paper_id": a, "target_paper_id": b,
                                                                   "relation": "extends"}, headers=self.h).status_code, 409)
        self.assertEqual(self.client.post("/api/paper-links", json={"source_paper_id": a, "target_paper_id": a,
                                                                   "relation": "related"}, headers=self.h).status_code, 422)
        self.assertEqual(self.client.post("/api/paper-links", json={"source_paper_id": a, "target_paper_id": b,
                                                                   "relation": "nonsense"}, headers=self.h).status_code, 422)
        symmetric = self.client.post("/api/paper-links", json={"source_paper_id": b, "target_paper_id": a,
                                                              "relation": "same_method", "origin": "agent"}, headers=self.h)
        self.assertEqual(symmetric.json()["status"], "suggested")
        self.assertEqual(self.client.post("/api/paper-links", json={"source_paper_id": a, "target_paper_id": b,
                                                                   "relation": "same_method"}, headers=self.h).status_code, 409)
        from_a = self.client.get(f"/api/papers/{a}/links", headers=self.h).json()
        self.assertEqual(len(from_a), 2)
        self.assertTrue({item["direction"] for item in from_a} <= {"outgoing", "incoming"})
        self.assertIn("B", {item["other_title"] for item in from_a})
        link_id = created.json()["id"]
        patched = self.client.patch(f"/api/paper-links/{link_id}", json={"status": "rejected", "note": "n"}, headers=self.h)
        self.assertEqual((patched.json()["status"], patched.json()["note"]), ("rejected", "n"))
        self.assertEqual(self.client.delete(f"/api/paper-links/{link_id}", headers=self.h).status_code, 204)
        self.assertEqual(self.client.delete(f"/api/paper-links/{link_id}", headers=self.h).status_code, 404)

    def test_discover_creates_rule_links_and_never_recreates_rejected(self):
        a = self.paper("Pruning A")
        b = self.paper("Pruning B")
        method = {"method": [self.item("We propose structured pruning of convolution filters for compact networks.")]}
        self.assertEqual(self.manual_profile(a, self.profile_data(method)).status_code, 201)
        self.assertEqual(self.manual_profile(b, self.profile_data(method)).status_code, 201)
        first = self.client.post("/api/library/links/discover", json={"use_openalex": False}, headers=self.h).json()
        self.assertEqual(first["created"], 1)
        self.assertEqual(first["errors"], [])
        links = self.client.get(f"/api/papers/{a}/links", headers=self.h).json()
        self.assertEqual(links[0]["relation"], "same_method")
        self.assertEqual(links[0]["status"], "suggested")
        self.client.patch(f"/api/paper-links/{links[0]['id']}", json={"status": "rejected"}, headers=self.h)
        again = self.client.post("/api/library/links/discover", json={}, headers=self.h).json()
        self.assertEqual(again["created"], 0)
        self.assertEqual(again["skipped"], 1)
        with storage.transaction() as con:
            count = con.execute("SELECT COUNT(*) FROM paper_links").fetchone()[0]
        self.assertEqual(count, 1)

    def test_openalex_cites_with_mocked_lookup_and_errors_collected(self):
        a = self.paper("Citing", doi="10.1000/a")
        b = self.paper("Cited", doi="10.1000/b")
        c = self.paper("Broken", doi="10.1000/c")

        def fake_get(source, url, headers=None):
            if "doi:10.1000/a" in url:
                return json.dumps({"id": "https://openalex.org/W1", "doi": "https://doi.org/10.1000/a",
                                   "referenced_works": ["https://openalex.org/W2", "https://openalex.org/W999"]}).encode()
            if "doi:10.1000/b" in url:
                return json.dumps({"id": "https://openalex.org/W2", "doi": "https://doi.org/10.1000/b",
                                   "referenced_works": []}).encode()
            raise scholarly.ScholarlyError("openalex", "network_error", "down")

        with patch.object(scholarly, "_get", side_effect=fake_get):
            result = self.client.post("/api/library/links/discover", json={"use_openalex": True}, headers=self.h).json()
        self.assertEqual(result["created"], 1)
        self.assertEqual(len(result["errors"]), 1)
        links = self.client.get(f"/api/papers/{a}/links", headers=self.h).json()
        self.assertEqual(links[0]["relation"], "cites")
        self.assertEqual(links[0]["origin"], "openalex")
        self.assertEqual(links[0]["status"], "accepted")
        self.assertEqual(links[0]["target_paper_id"], b)
        self.assertNotIn(c, [links[0]["target_paper_id"]])

    def test_graph_excludes_rejected_links_and_deleted_papers(self):
        a = self.paper("G1")
        b = self.paper("G2")
        d = self.paper("G3")
        keep = self.client.post("/api/paper-links", json={"source_paper_id": a, "target_paper_id": b,
                                                         "relation": "supports"}, headers=self.h).json()
        drop = self.client.post("/api/paper-links", json={"source_paper_id": a, "target_paper_id": d,
                                                         "relation": "supports"}, headers=self.h).json()
        self.client.patch(f"/api/paper-links/{drop['id']}", json={"status": "rejected"}, headers=self.h)
        graph = self.client.get("/api/library/graph", headers=self.h).json()
        self.assertEqual([e["id"] for e in graph["edges"]], [keep["id"]])
        self.assertEqual({n["id"] for n in graph["nodes"]}, {a, b, d})
        with storage.transaction() as con:
            con.execute("UPDATE papers SET deleted_at=CURRENT_TIMESTAMP WHERE id=?", (b,))
        graph = self.client.get("/api/library/graph", headers=self.h).json()
        self.assertEqual(graph["edges"], [])
        self.assertNotIn(b, {n["id"] for n in graph["nodes"]})


class GapTests(KnowledgeTests):
    def test_rule_gaps_single_paper_has_evidence(self):
        pid = self.paper("Solo", {0: "We propose a fast decoder. The model has a limitation: it does not handle long documents.",
                                  1: "Future work: extend to multilingual corpora in the future."})
        created = self.gaps_rules([pid])
        self.assertEqual(created.status_code, 201, created.text)
        gaps = created.json()
        types = [g["gap_type"] for g in gaps]
        self.assertIn("unaddressed_limitation", types)
        self.assertNotIn("common_limitation", types)
        limitation = next(g for g in gaps if g["gap_type"] == "unaddressed_limitation")
        self.assertEqual(limitation["paper_ids"], [pid])
        self.assertEqual(limitation["evidence"][0]["paper_id"], pid)
        self.assertEqual(limitation["evidence"][0]["facet"], "limitations")
        self.assertIn("does not handle long documents", limitation["evidence"][0]["quote"])
        self.assertIn(limitation["evidence"][0]["match"], {"exact", "normalized"})
        self.assertEqual(self.gaps_rules([pid]).json(), [])  # duplicates are not recreated

    def test_rule_gaps_two_papers_common_limitation_dataset_and_method(self):
        a = self.paper("Alpha", {0: "We propose a graph attention network. The model cannot handle long sequences efficiently. "
                                     "We evaluate on the ImageNet dataset and CIFAR-10 benchmark. Accuracy improves."})
        b = self.paper("Beta", {0: "We introduce an approach for scheduling. The approach cannot handle long sequences well. "
                                    "We evaluate on the ImageNet dataset. The problem of scheduling is hard."})
        gaps = self.gaps_rules([a, b]).json()
        types = {g["gap_type"] for g in gaps}
        self.assertIn("common_limitation", types)
        self.assertIn("missing_dataset_or_metric", types)
        self.assertIn("method_not_applied_to_problem", types)
        dataset = next(g for g in gaps if g["gap_type"] == "missing_dataset_or_metric")
        self.assertIn("cifar-10", dataset["title"])
        methods = [g for g in gaps if g["gap_type"] == "method_not_applied_to_problem"]
        self.assertLessEqual(len(methods), knowledge.METHOD_PAIR_CAP)
        for gap in gaps:
            for ev in gap["evidence"]:
                self.assertIn(ev["paper_id"], {a, b})
        self.assertEqual(self.gaps_rules([a, b]).json(), [])

    def test_ai_gaps_discard_unknown_paper_keys(self):
        a = self.paper("Gap A", {0: "Body text about pruning in networks."}, abstract="We study pruning. Limitation: slow.")
        b = self.paper("Gap B", {0: "Other text."}, abstract="We study quantization.")
        self.set_config(LOCAL)
        self.fake.reply = json.dumps({"gaps": [
            {"title": "Slow pruning", "description": "d", "gap_type": "unaddressed_limitation", "papers": ["P1"],
             "evidence": [{"paper": "P1", "quote": "Limitation: slow."}]},
            {"title": "Ghost", "description": "d", "gap_type": "other", "papers": ["P1", "P9"],
             "evidence": [{"paper": "P1", "quote": "We study pruning."}]},
            {"title": "Bad evidence key", "description": "d", "gap_type": "other", "papers": ["P2"],
             "evidence": [{"paper": "P7", "quote": "x"}]},
            {"title": "Weird type", "description": "d", "gap_type": "made_up", "papers": ["P2"],
             "evidence": [{"paper": "P2", "quote": "We study quantization."}]},
        ]})
        preview = self.client.post("/api/gaps/ai/preview", json={"paper_ids": [a, b]}, headers=self.h)
        self.assertEqual(preview.status_code, 200, preview.text)
        response = self.client.post("/api/gaps/ai", json={"paper_ids": [a, b]}, headers=self.h)
        self.assertEqual(response.status_code, 201, response.text)
        titles = [g["title"] for g in response.json()]
        self.assertEqual(titles, ["Slow pruning", "Weird type"])
        slow = response.json()[0]
        self.assertEqual(slow["origin"], "llm")
        self.assertEqual(slow["evidence"][0]["match"], "exact")
        self.assertEqual(response.json()[1]["gap_type"], "other")
        self.assertIn("P1", self.fake.calls[-1][1]["content"])

    def test_manual_gap_quotes_and_validation(self):
        pid = self.paper("Manual gap", {0: "The approach fails on rare classes.", 1: "Other words."})
        created = self.client.post("/api/gaps", json={
            "paper_ids": [pid], "title": "Rare classes", "description": "d", "gap_type": "unaddressed_limitation",
            "origin": "manual", "evidence": [
                {"paper_id": pid, "quote": "fails on rare classes."},
                {"paper_id": pid, "quote": "not in text at all", "page": 2},
                {"paper_id": pid, "quote": "Other WORDS.", "page": 1}]}, headers=self.h)
        self.assertEqual(created.status_code, 201, created.text)
        gap = created.json()
        self.assertEqual(gap["status"], "candidate")
        self.assertEqual([e["match"] for e in gap["evidence"]], ["exact", "not_found", "normalized"])
        self.assertEqual(gap["evidence"][1]["match"], "not_found")
        other = self.paper("Other")
        bad = self.client.post("/api/gaps", json={"paper_ids": [pid], "title": "t", "gap_type": "other",
                                                  "origin": "manual",
                                                  "evidence": [{"paper_id": other, "quote": "x"}]}, headers=self.h)
        self.assertEqual(bad.status_code, 422)
        self.assertEqual(self.client.post("/api/gaps", json={"paper_ids": [pid], "title": "t", "gap_type": "bogus",
                                                             "origin": "manual"}, headers=self.h).status_code, 422)
        self.assertEqual(self.client.post("/api/gaps", json={"paper_ids": [pid], "title": "t", "gap_type": "other",
                                                             "origin": "llm"}, headers=self.h).status_code, 422)

    def test_patch_status_and_to_idea(self):
        pid = self.paper("Idea source", {0: "The model has a limitation: it does not scale."})
        gap = self.gaps_rules([pid]).json()[0]
        patched = self.client.patch(f"/api/gaps/{gap['id']}", json={"status": "accepted", "title": "New title"},
                                    headers=self.h).json()
        self.assertEqual((patched["status"], patched["title"]), ("accepted", "New title"))
        self.assertEqual(self.client.patch(f"/api/gaps/{gap['id']}", json={"status": "nope"}, headers=self.h).status_code, 422)
        project = self.client.post("/api/projects", json={"name": "P"}, headers=self.h).json()
        idea = self.client.post(f"/api/gaps/{gap['id']}/to-idea", json={"project_id": project["id"]}, headers=self.h)
        self.assertEqual(idea.status_code, 201, idea.text)
        self.assertEqual(idea.json()["status"], "draft")
        self.assertEqual(idea.json()["title"], "New title")
        with storage.transaction() as con:
            con.execute("INSERT INTO project_trash(project_id) VALUES(?)", (project["id"],))
        self.assertEqual(self.client.post(f"/api/gaps/{gap['id']}/to-idea", json={"project_id": project["id"]},
                                          headers=self.h).status_code, 404)
        self.assertEqual(self.client.post(f"/api/gaps/{gap['id']}/to-idea", json={"project_id": "missing"},
                                          headers=self.h).status_code, 404)
        self.assertEqual(len(self.client.get("/api/gaps", headers=self.h).json()), 1)
        self.assertEqual(self.client.get("/api/gaps", params={"project_id": project["id"]}, headers=self.h).json(), [])


class ClassifyTests(KnowledgeTests):
    def test_ai_classification_respects_user_decisions(self):
        pid = self.paper("Vision transformer", {0: "We study image segmentation with transformers."}, abstract="Vision.")
        vision = next(c["id"] for c in self.client.get("/api/categories", headers=self.h).json() if c["name"] == "컴퓨터 비전")
        rl = next(c["id"] for c in self.client.get("/api/categories", headers=self.h).json() if c["name"] == "강화학습")
        self.client.put(f"/api/papers/{pid}/categories/{rl}", json={"status": "rejected"}, headers=self.h)
        self.set_config(LOCAL)
        self.fake.reply = json.dumps({"categories": ["컴퓨터 비전", "강화학습", "Totally New Field"], "new_categories": ["Other"]})
        response = self.client.post(f"/api/papers/{pid}/classify/ai", json={}, headers=self.h)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["applied"], ["컴퓨터 비전"])
        self.assertEqual(response.json()["proposed_new"], ["Totally New Field", "Other"])
        cats = {c["name"]: c for c in self.client.get(f"/api/papers/{pid}/categories", headers=self.h).json()}
        self.assertEqual(cats["컴퓨터 비전"]["source"], "llm")
        self.assertEqual(cats["컴퓨터 비전"]["status"], "suggested")
        self.assertEqual(cats["강화학습"]["status"], "rejected")
        self.client.put(f"/api/papers/{pid}/categories/{vision}", json={"status": "confirmed"}, headers=self.h)
        self.client.post(f"/api/papers/{pid}/classify/ai", json={}, headers=self.h)
        cats = {c["name"]: c for c in self.client.get(f"/api/papers/{pid}/categories", headers=self.h).json()}
        self.assertEqual(cats["컴퓨터 비전"]["status"], "confirmed")

    def test_ai_classification_external_hash_and_preview(self):
        pid = self.paper("Ext classify", {0: "Text about graphs."})
        self.set_config(EXTERNAL)
        self.fake.reply = json.dumps({"categories": ["자연어 처리"], "new_categories": []})
        preview = self.client.post(f"/api/papers/{pid}/classify/ai/preview", headers=self.h)
        self.assertEqual(preview.status_code, 200, preview.text)
        self.assertEqual(self.client.post(f"/api/papers/{pid}/classify/ai", json={"preview_hash": "x" * 64},
                                          headers=self.h).status_code, 409)
        ok = self.client.post(f"/api/papers/{pid}/classify/ai", json={"preview_hash": preview.json()["preview_hash"]},
                              headers=self.h)
        self.assertEqual(ok.status_code, 200, ok.text)
        self.assertEqual(ok.json()["applied"], ["자연어 처리"])

    def test_classify_none_provider_is_400(self):
        pid = self.paper("No provider")
        self.assertEqual(self.client.post(f"/api/papers/{pid}/classify/ai", json={}, headers=self.h).status_code, 400)


if __name__ == "__main__":
    unittest.main()
