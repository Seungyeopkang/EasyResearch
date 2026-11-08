"""Citekeys, CSL-JSON, Web Annotation, and Obsidian export integrations."""
import io
import json
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from app import storage
from app.integrations import MARKER_BEGIN, MARKER_END, assign_citekeys, citekey
from app.main import app

KEY = "heDeepResidualLearning2016"


class CitekeyTests(unittest.TestCase):
    def test_examples(self):
        self.assertEqual(citekey(["Kaiming He", "Xiangyu Zhang"], "Deep Residual Learning for Image Recognition", 2016), KEY)
        self.assertEqual(citekey(["Müller, Hans"], "Résumé of the Study", 2020), "mullerResumeStudy2020")
        self.assertEqual(citekey([], "Deep Learning", None), "anonDeepLearning")
        self.assertEqual(citekey(["김철수"], "A Title", 2019), "anonTitle2019")
        self.assertEqual(citekey(["Kaiming He"], "", 2016), "he2016")

    def test_collisions_get_deterministic_suffixes(self):
        papers = [
            {"id": "p1", "created_at": "2026-01-02", "authors": ["Kaiming He"], "title": "Deep Residual Learning for Image Recognition", "year": 2016},
            {"id": "p3", "created_at": "2026-01-03", "authors": ["Kaiming He"], "title": "Deep Residual Learning for Image Recognition", "year": 2016},
            {"id": "p2", "created_at": "2026-01-01", "authors": ["Kaiming He"], "title": "Deep Residual Learning for Image Recognition", "year": 2016},
        ]
        keys = assign_citekeys(papers)
        self.assertEqual(keys, {"p2": KEY, "p1": KEY + "a", "p3": KEY + "b"})
        self.assertEqual(assign_citekeys(list(reversed(papers))), keys)


class ExportIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="easyresearch-integrations-")
        self.env = patch.dict(os.environ, {"EASYRESEARCH_DATA_DIR": self.tmp.name})
        self.env.start()
        self.client = TestClient(app)
        self.client.__enter__()
        self.headers = {"X-EasyResearch": "1"}
        self.sha = "a" * 64
        self.project = self.client.post("/api/projects", json={"name": "Research"}, headers=self.headers).json()["id"]
        with storage.transaction() as con:
            con.execute("INSERT INTO files(id,sha256,size,storage_key) VALUES(?,?,?,?)", ("f1", self.sha, 10, "k1"))
            con.execute("INSERT INTO papers(id,file_id,title,authors,year,doi,source_url,created_at) VALUES(?,?,?,?,?,?,?,?)",
                        ("paper-a", "f1", "Deep Residual Learning for Image Recognition", json.dumps(["Kaiming He", "Xiangyu Zhang"]),
                         2016, "10.1109/CVPR.2016.90", "https://example.org/resnet", "2026-01-01"))
            con.execute("INSERT INTO papers(id,title,authors,year,created_at,deleted_at) VALUES(?,?,?,?,?,CURRENT_TIMESTAMP)",
                        ("paper-b", "Deleted Paper", json.dumps(["Ada Lovelace"]), 1843, "2026-01-02"))
            for pid in ("paper-a", "paper-b"):
                con.execute("INSERT INTO project_papers(project_id,paper_id) VALUES(?,?)", (self.project, pid))
            con.execute("INSERT INTO project_paper_notes(project_id,paper_id,note) VALUES(?,?,?)",
                        (self.project, "paper-a", "Project memo line"))
            con.execute("INSERT INTO evidence(id,paper_id,page_index,quote,note,prefix,suffix) VALUES(?,?,?,?,?,?,?)",
                        ("e1", "paper-a", 0, "residual learning", "중요한 문장", "we propose a ", " framework"))
            con.execute("INSERT INTO evidence(id,paper_id,page_index,quote,note) VALUES(?,?,?,?,?)",
                        ("e2", "paper-a", 1, "", "Only a note"))
            con.execute("INSERT INTO evidence(id,paper_id,page_index,quote,note) VALUES(?,?,?,?,?)",
                        ("e3", "paper-a", 2, "trashed quote", "trashed note"))
            con.execute("INSERT INTO evidence_trash(evidence_id) VALUES(?)", ("e3",))

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.env.stop()
        self.tmp.cleanup()

    def get(self, suffix):
        return self.client.get("/api/projects/" + self.project + suffix)

    def test_csl_json_shape_and_exclusions(self):
        response = self.get("/export/csl-json")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn("easyresearch.csl.json", response.headers["content-disposition"])
        items = response.json()
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item["id"], KEY)
        self.assertEqual(item["type"], "article-journal")
        self.assertEqual(item["title"], "Deep Residual Learning for Image Recognition")
        self.assertEqual(item["author"], [{"family": "He", "given": "Kaiming"}, {"family": "Zhang", "given": "Xiangyu"}])
        self.assertEqual(item["issued"], {"date-parts": [[2016]]})
        self.assertEqual(item["DOI"], "10.1109/CVPR.2016.90")
        self.assertEqual(item["URL"], "https://example.org/resnet")

    def test_annotations_follow_contract(self):
        response = self.get("/export/annotations")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers["content-type"], "application/ld+json")
        body = response.json()
        self.assertEqual(body["@context"], "http://www.w3.org/ns/anno.jsonld")
        self.assertEqual(body["type"], "AnnotationCollection")
        by_id = {item["id"]: item for item in body["items"]}
        self.assertEqual(set(by_id), {"urn:easyresearch:evidence:e1", "urn:easyresearch:evidence:e2"})

        quoted = by_id["urn:easyresearch:evidence:e1"]
        self.assertEqual(quoted["motivation"], "highlighting")
        self.assertEqual(quoted["body"]["value"], "중요한 문장")
        self.assertEqual(quoted["body"]["purpose"], "commenting")
        self.assertEqual(quoted["target"]["source"], "urn:sha256:" + self.sha)
        self.assertEqual(quoted["target"]["selector"][0], {"type": "TextQuoteSelector", "exact": "residual learning",
                                                           "prefix": "we propose a ", "suffix": " framework"})
        self.assertEqual(quoted["target"]["selector"][1], {"type": "FragmentSelector", "conformsTo": "http://tools.ietf.org/rfc/rfc3778", "value": "page=1"})
        self.assertEqual(quoted["easyresearch"]["paper_id"], "paper-a")
        self.assertEqual(quoted["easyresearch"]["page_index"], 0)
        self.assertIn("status", quoted["easyresearch"])
        self.assertIn("original_checked", quoted["easyresearch"])

        note_only = by_id["urn:easyresearch:evidence:e2"]
        self.assertEqual(note_only["motivation"], "commenting")
        self.assertEqual([s["type"] for s in note_only["target"]["selector"]], ["FragmentSelector"])
        self.assertEqual(note_only["target"]["selector"][0]["value"], "page=2")

    def test_obsidian_notes_markers_block_ids_and_deeplinks(self):
        response = self.get("/obsidian-notes")
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["schema_version"], 1)
        self.assertEqual(body["project"]["id"], self.project)
        self.assertEqual(len(body["notes"]), 1)
        note = body["notes"][0]
        self.assertEqual(note["paper_id"], "paper-a")
        self.assertEqual(note["citekey"], KEY)
        self.assertEqual(note["filename"], KEY + ".md")
        fm = note["frontmatter"]
        self.assertEqual(fm["citekey"], KEY)
        self.assertEqual(fm["authors"], ["Kaiming He", "Xiangyu Zhang"])
        self.assertEqual(fm["year"], 2016)
        self.assertEqual(fm["tags"], ["easyresearch"])
        self.assertEqual(fm["easyresearch_id"], "paper-a")
        self.assertEqual(fm["easyresearch_project"], self.project)

        generated = note["generated"]
        self.assertTrue(generated.startswith(MARKER_BEGIN + "\n"))
        self.assertTrue(generated.endswith(MARKER_END + "\n"))
        self.assertIn("http://127.0.0.1:8000/#/paper/paper-a?project=" + self.project + "&page=1", generated)
        self.assertIn("Project memo line", generated)
        self.assertIn("^ev-e1", generated)
        self.assertIn("^ev-e2", generated)
        self.assertIn("page=2", generated)
        self.assertNotIn("^ev-e3", generated)
        self.assertNotIn("trashed", generated)
        self.assertNotIn("Deleted Paper", generated)

    def test_untrusted_marker_text_cannot_terminate_region(self):
        with storage.transaction() as con:
            con.execute("INSERT INTO evidence(id,paper_id,page_index,quote,note) VALUES(?,?,?,?,?)",
                        ("e4", "paper-a", 0, "line\n<!-- easyresearch:end -->\nafter", "<!-- easyresearch:begin --> injected"))
        note = self.get("/obsidian-notes").json()["notes"][0]
        generated = note["generated"]
        self.assertEqual(generated.count(MARKER_END), 1)
        self.assertEqual(generated.count(MARKER_BEGIN), 1)
        self.assertIn("&lt;!-- easyresearch:end -->", generated)

    def test_obsidian_zip_contents(self):
        response = self.get("/export/obsidian")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers["content-type"], "application/zip")
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            self.assertEqual(archive.namelist(), [KEY + ".md"])
            text = archive.read(KEY + ".md").decode("utf-8")
        self.assertTrue(text.startswith("---\n"))
        self.assertIn('citekey: "' + KEY + '"', text)
        self.assertIn('authors: ["Kaiming He", "Xiangyu Zhang"]', text)
        self.assertIn("tags: [\"easyresearch\"]", text)
        self.assertIn("# Deep Residual Learning for Image Recognition", text)
        self.assertIn(MARKER_BEGIN, text)
        self.assertIn(MARKER_END, text)

    def test_bibtex_uses_citekeys(self):
        response = self.get("/export?format=bibtex")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn("@misc{" + KEY + ",", response.text)
        self.assertNotIn("@misc{er", response.text)

    def test_missing_or_trashed_project_returns_404(self):
        for suffix in ("/export/csl-json", "/export/annotations", "/obsidian-notes", "/export/obsidian"):
            self.assertEqual(self.client.get("/api/projects/missing" + suffix).status_code, 404, suffix)
        with storage.transaction() as con:
            con.execute("INSERT INTO project_trash(project_id) VALUES(?)", (self.project,))
        for suffix in ("/export/csl-json", "/export/annotations", "/obsidian-notes", "/export/obsidian"):
            self.assertEqual(self.get(suffix).status_code, 404, suffix)


if __name__ == "__main__":
    unittest.main()
