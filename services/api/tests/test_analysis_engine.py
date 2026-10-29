import io
import json
import socket
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import analysis_engine as engine


EVIDENCE = [
    {"id": "e1", "paper_id": "p1", "page_index": 0, "quote": "The model used a 10 sample dataset.", "note": "PRIVATE NOTE"},
    {"id": "e2", "paper_id": "p2", "page_index": 2, "quote": "A model used a 50 sample dataset."},
    {"id": "e3", "paper_id": "p1", "page_index": 1, "quote": "Irrelevant passage."},
]


def response(result):
    return json.dumps({"status": "completed", "output": [{"type": "message", "content": [
        {"type": "output_text", "text": json.dumps(result)}]}]}).encode()


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class AnalysisTests(unittest.TestCase):
    def test_extractive_mode_is_not_a_generated_answer(self):
        result = engine.analyze("sample dataset", EVIDENCE)
        self.assertEqual(result["status"], "excerpts_only")
        self.assertEqual(result["claims"], [])
        self.assertEqual([e["id"] for e in result["excerpts"]], ["e1", "e2"])
        self.assertEqual(result["semantic_support"], "not_checked")
        self.assertNotIn("note", result["excerpts"][0])

    def test_missing_or_irrelevant_evidence_abstains(self):
        for evidence in ([], EVIDENCE):
            result = engine.analyze("quantum teleportation", evidence)
            self.assertEqual(result["status"], "insufficient_evidence")
            self.assertEqual(result["claims"], [])

    def test_external_preview_and_consent(self):
        evidence = [{"id": "x", "paper_id": "p", "page_index": 0, "quote": "model " + "a" * 2000, "note": "secret"}]
        preview = engine.prepare_external_input("model", evidence)
        self.assertEqual(len(preview["excerpts"][0]["quote"]), 1200)
        self.assertTrue(preview["excerpts"][0]["truncated"])
        self.assertNotIn("secret", json.dumps(preview))
        with patch.object(engine, "urlopen") as call:
            with self.assertRaises(engine.AnalysisError) as error:
                engine.analyze("model", evidence, provider="openai", api_key="key", model="model")
            self.assertEqual(error.exception.code, "external_not_allowed")
            call.assert_not_called()

    def test_explicit_cross_language_evidence_selection(self):
        question = "사용한 데이터의 크기는 얼마인가요?"
        evidence = [{"id": "e{}".format(i), "paper_id": "p1", "page_index": i,
                     "quote": "A sample contains {} observations.".format(i)} for i in range(10)]
        self.assertEqual(engine.analyze(question, evidence)["status"], "insufficient_evidence")
        preview = engine.prepare_external_input(question, evidence, include_selected=True)
        self.assertEqual(len(preview["excerpts"]), 8)
        self.assertEqual([item["id"] for item in preview["excerpts"]], ["e{}".format(i) for i in range(8)])
        local = engine.analyze(question, evidence, include_selected=True)
        self.assertEqual(local["status"], "excerpts_only")
        self.assertEqual(local["excerpts"], preview["excerpts"])
        self.assertIn("직접 선택", local["message"])
        raw = response({"claims": [{"text": "표본이 0개입니다.", "evidence_ids": ["e0"]}], "insufficient_evidence": False})
        with patch.object(engine, "urlopen", return_value=Response(raw)) as call:
            engine.analyze(question, evidence, provider="openai", api_key="key", model="model",
                           allow_external=True, include_selected=True)
        payload = json.loads(call.call_args.args[0].data)
        self.assertEqual(json.loads(payload["input"][1]["content"]), preview)

    def test_selected_evidence_still_abstains_when_empty(self):
        self.assertEqual(engine.analyze("질문", [], include_selected=True)["status"], "insufficient_evidence")
        with self.assertRaises(ValueError):
            engine.prepare_external_input("질문", EVIDENCE, include_selected="true")

    def test_openai_payload_and_evidence_ids(self):
        raw = response({"claims": [{"text": "The sample had 10 items.", "evidence_ids": ["e1"]}], "insufficient_evidence": False})
        with patch.object(engine, "urlopen", return_value=Response(raw)) as call:
            result = engine.analyze("sample", [EVIDENCE[0], EVIDENCE[2]], provider="openai", api_key="secret", model="example-model", allow_external=True)
        request = call.call_args.args[0]
        payload = json.loads(request.data)
        self.assertFalse(payload["store"])
        self.assertEqual(payload["text"]["format"]["type"], "json_schema")
        self.assertNotIn("secret", request.data.decode())
        transmitted = json.loads(payload["input"][1]["content"])
        self.assertEqual(transmitted, engine.prepare_external_input("sample", [EVIDENCE[0], EVIDENCE[2]]))
        self.assertEqual(result["status"], "needs_review")
        self.assertEqual(result["claims"][0]["evidence_ids"], ["e1"])
        self.assertEqual(result["semantic_support"], "not_checked")

    def test_invented_or_missing_citations_rejected(self):
        for ids in (["fake"], []):
            raw = response({"claims": [{"text": "claim", "evidence_ids": ids}], "insufficient_evidence": False})
            with self.subTest(ids=ids), patch.object(engine, "urlopen", return_value=Response(raw)):
                with self.assertRaises(engine.AnalysisError) as error:
                    engine.analyze("sample", [EVIDENCE[0]], provider="openai", api_key="key", model="model", allow_external=True)
                self.assertEqual(error.exception.code, "invalid_response")

    def test_model_uncertainty_and_incomplete_response(self):
        raw = response({"claims": [], "insufficient_evidence": True})
        with patch.object(engine, "urlopen", return_value=Response(raw)):
            result = engine.analyze("sample", [EVIDENCE[0]], provider="openai", api_key="key", model="model", allow_external=True)
        self.assertEqual(result["status"], "insufficient_evidence")
        with patch.object(engine, "urlopen", return_value=Response(b'{"status":"incomplete"}')):
            with self.assertRaises(engine.AnalysisError) as error:
                engine.analyze("sample", [EVIDENCE[0]], provider="openai", api_key="key", model="model", allow_external=True)
            self.assertEqual(error.exception.code, "invalid_response")

    def test_provider_errors_and_multi_paper_guard(self):
        for error, code in [(HTTPError("https://example.org", 429, "", {}, None), "rate_limited"),
                            (URLError(socket.timeout()), "timeout"), (URLError("offline"), "network_error")]:
            with self.subTest(code=code), patch.object(engine, "urlopen", side_effect=error):
                with self.assertRaises(engine.AnalysisError) as failure:
                    engine.analyze("sample", [EVIDENCE[0]], provider="openai", api_key="key", model="model", allow_external=True)
                self.assertEqual(failure.exception.code, code)
        with self.assertRaises(engine.AnalysisError) as failure:
            engine.analyze("sample", EVIDENCE, provider="openai", api_key="key", model="model", allow_external=True)
        self.assertEqual(failure.exception.code, "multi_paper_not_supported")

    def test_comparison_remains_extractive_and_displays_missing_papers(self):
        papers = [{"id": "p1", "title": "A"}, {"id": "p2", "title": "B"}, {"id": "p3", "title": "C"}]
        result = engine.compare_papers(papers, EVIDENCE, "sample")
        self.assertEqual([r["status"] for r in result["rows"]], ["excerpts_only", "excerpts_only", "insufficient_evidence"])
        self.assertEqual(result["rows"][0]["excerpts"][0]["id"], "e1")
        self.assertEqual(result["rows"][1]["excerpts"][0]["id"], "e2")
        self.assertNotIn("ranking", result)

    def test_input_validation(self):
        duplicate = EVIDENCE + [EVIDENCE[0]]
        with self.assertRaises(ValueError):
            engine.analyze("sample", duplicate)
        with self.assertRaises(ValueError):
            engine.analyze("", [])
        with self.assertRaises(engine.AnalysisError) as error:
            engine.analyze("sample", [EVIDENCE[0]], provider="openai", allow_external=True)
        self.assertEqual(error.exception.code, "missing_config")


if __name__ == "__main__":
    unittest.main()
