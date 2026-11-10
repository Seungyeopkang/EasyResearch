"""Research agent: chat threads, preview hash rules, and the staged research loop.

The LLM transport and OpenAlex are faked. Data lives in a temporary EASYRESEARCH_DATA_DIR.
"""
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import llm, research_agent, scholarly, storage
from app.main import app

ABSTRACT = ("Image segmentation models are accurate on benchmarks. Boundary accuracy remains limited on small objects. "
            "The dataset covers urban scenes only.")
STAGES = ["plan_queries", "search", "screen", "problems", "methods", "contributions", "critique"]
LOCAL = {"provider": "ollama", "base_url": "http://127.0.0.1:11434", "model": "fake"}
EXTERNAL = {"provider": "openai_compatible", "base_url": "https://example.test/v1", "model": "m"}


class FakeLLM:
    """Replaces llm.transport. The stage is detected from the JSON shape named in each system prompt."""

    def __init__(self):
        self.calls = []
        self.plan_responses = [["image segmentation transformer", "efficient segmentation survey"]]
        self.fail_once = {}
        self.network_error = False
        self.chat_reply = "답변입니다. [P1]에 따르면 경계 정확도가 낮습니다. [P9]도 있습니다. [G1] 참고."
        self.search_calls = []
        self._counter = 0

    @staticmethod
    def stage_of(system):
        if '"weaknesses"' in system:  # the critique prompt names this key; it has no "scores" any more
            return "critique"
        if '"contributions"' in system:
            return "contributions"
        if '"methods"' in system:
            return "methods"
        if '"problems"' in system:
            return "problems"
        if '"queries"' in system:
            return "plan"
        return "chat"

    def __call__(self, config, messages, *, json_output, max_tokens, **_):
        stage = self.stage_of(messages[0]["content"])
        self.calls.append((stage, messages))
        if self.network_error and stage == "chat":
            raise llm.LLMError("network_error", "AI 서버에 연결할 수 없습니다.")
        if self.fail_once.get(stage, 0) > 0:
            self.fail_once[stage] -= 1
            return "이것은 JSON이 아닙니다"
        if stage == "chat":
            return self.chat_reply
        if stage == "plan":
            batch = self.plan_responses.pop(0) if len(self.plan_responses) > 1 else self.plan_responses[0]
            return json.dumps({"queries": batch})
        if stage == "problems":
            return json.dumps({"problems": [
                {"title": "Boundary accuracy", "statement": "작은 객체의 경계 정확도", "type": "unaddressed_limitation",
                 "why_open": "근거가 제한적", "evidence": ["E1", "E99"]},
                {"title": "Ghost problem", "statement": "근거 없음", "type": "bogus", "why_open": "",
                 "evidence": ["E404"]},
                {"title": "Dataset gap", "statement": "도시 장면만 다룸", "type": "missing_dataset_or_metric",
                 "why_open": "", "evidence": ["E2"]},
            ]})
        if stage == "methods":
            return json.dumps({"methods": [
                {"problem_index": 0, "title": "경계 손실 보정", "idea": "경계 가중 손실을 시험한다",
                 "expected_gain": "경계 정확도 개선 가능", "risks": "데이터 편향", "evidence": ["E1", "E77"]},
                {"problem_index": 2, "title": "범위 밖", "idea": "x", "expected_gain": "", "risks": "",
                 "evidence": ["E1"]},
            ]})
        if stage == "contributions":
            return json.dumps({"contributions": [
                {"statement": "작은 객체 경계 정확도 평가", "search_query": "small object boundary accuracy evaluation"},
                {"statement": "도시 외 장면으로 일반화 검증", "search_query": "generalization beyond urban scenes segmentation"}]})
        if stage == "critique":
            return json.dumps({"weaknesses": [{"text": "표본이 작음", "refs": ["P1", "E1"]},
                                              {"text": "uncited", "refs": []}],
                               "next_queries": ["lightweight segmentation distillation",
                                                "boundary refinement small objects"]})
        raise AssertionError("unexpected stage " + stage)

    def search(self, query, limit=10, api_key=None):
        self.search_calls.append(query)
        records = []
        for _ in range(2):
            self._counter += 1
            n = self._counter
            records.append({"source": "openalex", "source_id": "https://openalex.org/W%d" % n,
                            "title": "Paper %d" % n, "authors": [], "year": 2021, "doi": "10.1000/p%d" % n,
                            "abstract": ABSTRACT, "url": "https://openalex.org/W%d" % n, "pdf_url": None})
        return records[:limit]

    def stage_messages(self, stage):
        return [messages for name, messages in self.calls if name == stage]


class ResearchAgentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"EASYRESEARCH_DATA_DIR": self.temp.name})
        self.env.start()
        os.environ.pop("OPENALEX_API_KEY", None)
        self.client = TestClient(app)
        self.client.__enter__()
        self.h = {"X-EasyResearch": "1"}
        self.original_transport = llm.transport
        self.fake = FakeLLM()
        llm.transport = self.fake
        self.search_patch = patch.object(scholarly, "search_openalex", side_effect=self.fake.search)
        self.search_patch.start()
        # Retry backoff is zero in tests. The runtime probe reports a fully GPU-loaded model (no warning).
        self.backoff_patch = patch.object(research_agent, "_backoff_seconds", return_value=0)
        self.backoff_patch.start()
        self.probe_patch = patch.object(llm, "runtime_probe",
                                        return_value=[{"name": "fake:latest", "size": 1000, "size_vram": 1000}])
        self.probe_patch.start()
        llm.save_config(dict(LOCAL))
        self.seed_id = self.make_paper("Seed study", ABSTRACT, "10.1000/seed")
        self.add_profile(self.seed_id)
        self.project_id = self.client.post("/api/projects", json={"name": "연구"}, headers=self.h).json()["id"]

    def tearDown(self):
        # Background workers must finish before the temporary data folder is removed.
        research_agent._join_workers(10)
        self.probe_patch.stop()
        self.backoff_patch.stop()
        self.search_patch.stop()
        llm.transport = self.original_transport
        self.client.__exit__(None, None, None)
        self.env.stop()
        self.temp.cleanup()

    # helpers
    def post(self, path, body):
        return self.client.post(path, json=body, headers=self.h)

    def make_paper(self, title, abstract, doi):
        response = self.client.post("/api/papers", json={"title": title, "authors": [], "doi": doi}, headers=self.h)
        self.assertEqual(response.status_code, 201, response.text)
        paper_id = response.json()["id"]
        with storage.transaction() as con:
            con.execute("UPDATE papers SET abstract=?, year=? WHERE id=?", (abstract, 2022, paper_id))
        return paper_id

    def add_profile(self, paper_id):
        profile = {"summary": "경계 정확도를 다룬 연구",
                   "facets": {"problem": [{"text": "작은 객체 분할", "origin": "inferred", "evidence": []}],
                              "method": [], "limitations": [{"text": "단일 데이터셋", "origin": "author_stated",
                                                             "evidence": []}]},
                   "keywords": []}
        with storage.transaction() as con:
            con.execute("INSERT INTO paper_profiles(id,paper_id,profile_json,origin,status,model) VALUES(?,?,?,?,?,?)",
                        (storage.new_id(), paper_id, json.dumps(profile, ensure_ascii=False), "manual", "draft", None))

    def add_note(self, paper_id):
        with storage.transaction() as con:
            con.execute("INSERT INTO project_paper_notes(project_id,paper_id,note) VALUES(?,?,?)",
                        (self.project_id, paper_id, "PRIVATE NOTE 비밀 메모"))

    def add_gap(self, title="Gap A"):
        gap_id = storage.new_id()
        with storage.transaction() as con:
            con.execute("INSERT INTO research_gaps(id,title,description,gap_type,origin) VALUES(?,?,?,?,?)",
                        (gap_id, title, "작은 객체 경계", "unaddressed_limitation", "manual"))
        return gap_id

    def new_thread(self, mode="idea", paper_ids=None, gap_ids=None, project_id=None):
        body = {"mode": mode, "paper_ids": paper_ids or [], "gap_ids": gap_ids or []}
        if project_id:
            body["project_id"] = project_id
        response = self.post("/api/chat/threads", body)
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()["id"]

    def thread_messages(self, thread_id):
        return self.client.get(f"/api/chat/threads/{thread_id}").json()["messages"]

    def run_body(self, **extra):
        body = {"topic": "image segmentation", "project_id": self.project_id, "seed_paper_ids": [self.seed_id],
                "max_iterations": 2, "papers_per_iteration": 3}
        body.update(extra)
        return body

    def start_run(self, **extra):
        body = self.run_body(**extra)
        preview = self.post("/api/research-runs/preview", body)
        self.assertEqual(preview.status_code, 200, preview.text)
        create = self.post("/api/research-runs", {**body, "preview_hash": preview.json()["preview_hash"]})
        self.assertEqual(create.status_code, 201, create.text)
        return create.json()["run"]["id"]

    def wait_idle(self, run_id, timeout=20.0):
        """Poll the run until its worker is no longer busy and return the detail."""
        deadline = time.monotonic() + timeout
        while True:
            detail = self.client.get(f"/api/research-runs/{run_id}").json()
            if not detail["run"]["busy"]:
                return detail
            if time.monotonic() > deadline:
                self.fail("research run stayed busy")
            time.sleep(0.02)

    def advance(self, run_id):
        response = self.client.post(f"/api/research-runs/{run_id}/advance", headers=self.h)
        self.assertEqual(response.status_code, 202, response.text)
        return self.wait_idle(run_id)

    def step(self, run_id):
        response = self.client.post(f"/api/research-runs/{run_id}/step", headers=self.h)
        self.assertEqual(response.status_code, 202, response.text)
        return self.wait_idle(run_id)

    # ---- chat

    def test_thread_crud_and_validation(self):
        created = self.post("/api/chat/threads", {"mode": "idea", "project_id": self.project_id,
                                                  "paper_ids": [self.seed_id]})
        self.assertEqual(created.status_code, 201, created.text)
        thread_id = created.json()["id"]
        self.assertEqual(created.json()["title"], "아이디어 대화")
        self.assertEqual(created.json()["paper_ids"], [self.seed_id])
        self.assertEqual(self.post("/api/chat/threads", {"mode": "bogus"}).status_code, 422)
        listed = self.client.get(f"/api/chat/threads?project_id={self.project_id}").json()
        self.assertEqual([t["id"] for t in listed], [thread_id])
        renamed = self.client.patch(f"/api/chat/threads/{thread_id}", json={"title": "새 제목"}, headers=self.h)
        self.assertEqual(renamed.json()["title"], "새 제목")
        self.assertEqual(self.thread_messages(thread_id), [])
        self.assertEqual(self.client.delete(f"/api/chat/threads/{thread_id}", headers=self.h).status_code, 204)
        self.assertEqual(self.client.get(f"/api/chat/threads/{thread_id}").status_code, 404)

    def test_chat_context_has_paper_card_but_no_private_note(self):
        self.add_note(self.seed_id)
        thread_id = self.new_thread(paper_ids=[self.seed_id])
        response = self.post(f"/api/chat/threads/{thread_id}/preview", {"content": "경계 정확도를 어떻게 재나요?"})
        self.assertEqual(response.status_code, 200, response.text)
        contents = "\n".join(m["content"] for m in response.json()["messages"])
        self.assertIn('<document label="P1">', contents)
        self.assertIn("Seed study", contents)
        self.assertIn("Boundary accuracy remains", contents)
        self.assertIn("경계 정확도를 다룬 연구", contents)
        self.assertIn("작은 객체 분할", contents)
        self.assertNotIn("PRIVATE NOTE", contents)
        self.assertEqual(response.json()["messages"][-1]["role"], "user")

    def test_chat_local_hash_rules_and_unknown_refs(self):
        gap_id = self.add_gap()
        thread_id = self.new_thread(paper_ids=[self.seed_id], gap_ids=[gap_id])
        content = "다음 실험은 무엇인가요?"
        preview = self.post(f"/api/chat/threads/{thread_id}/preview", {"content": content}).json()
        wrong = self.post(f"/api/chat/threads/{thread_id}/messages", {"content": content, "preview_hash": "0" * 64})
        self.assertEqual(wrong.status_code, 409, wrong.text)
        self.assertEqual(self.thread_messages(thread_id), [])
        ok = self.post(f"/api/chat/threads/{thread_id}/messages",
                       {"content": content, "preview_hash": preview["preview_hash"]})
        self.assertEqual(ok.status_code, 201, ok.text)
        self.assertEqual(ok.json()["role"], "assistant")
        self.assertEqual(ok.json()["meta"]["refs"], ["P1", "G1"])
        self.assertEqual(ok.json()["meta"]["unknown_refs"], ["P9"])
        roles = [m["role"] for m in self.thread_messages(thread_id)]
        self.assertEqual(roles, ["user", "assistant"])

    def test_chat_external_provider_requires_matching_hash(self):
        llm.save_config(dict(EXTERNAL))
        thread_id = self.new_thread(paper_ids=[self.seed_id])
        content = "외부 모델로 질문합니다."
        preview = self.post(f"/api/chat/threads/{thread_id}/preview", {"content": content})
        self.assertEqual(preview.status_code, 200, preview.text)
        self.assertTrue(preview.json()["external"])
        no_hash = self.post(f"/api/chat/threads/{thread_id}/messages", {"content": content})
        self.assertEqual(no_hash.status_code, 409, no_hash.text)
        self.assertEqual(self.thread_messages(thread_id), [])
        ok = self.post(f"/api/chat/threads/{thread_id}/messages",
                       {"content": content, "preview_hash": preview.json()["preview_hash"]})
        self.assertEqual(ok.status_code, 201, ok.text)
        self.assertEqual(len(self.thread_messages(thread_id)), 2)

    def test_failed_model_call_stores_nothing(self):
        thread_id = self.new_thread(paper_ids=[self.seed_id])
        self.fake.network_error = True
        response = self.post(f"/api/chat/threads/{thread_id}/messages", {"content": "질문"})
        self.assertEqual(response.status_code, 502, response.text)
        self.assertEqual(self.thread_messages(thread_id), [])

    def test_message_to_idea_rules(self):
        thread_id = self.new_thread()
        reply = self.post(f"/api/chat/threads/{thread_id}/messages", {"content": "아이디어를 정리해 주세요"})
        self.assertEqual(reply.status_code, 201, reply.text)
        assistant_id = reply.json()["id"]
        user_id = [m["id"] for m in self.thread_messages(thread_id) if m["role"] == "user"][0]
        converted = self.post(f"/api/chat/messages/{assistant_id}/to-idea",
                              {"project_id": self.project_id, "title": "경계 중심 아이디어"})
        self.assertEqual(converted.status_code, 201, converted.text)
        ideas = self.client.get(f"/api/ideas?project_id={self.project_id}").json()
        self.assertEqual([i["title"] for i in ideas], ["경계 중심 아이디어"])
        self.assertIn("경계 정확도", ideas[0]["description"])
        self.assertEqual(self.post(f"/api/chat/messages/{user_id}/to-idea",
                                   {"project_id": self.project_id, "title": "x"}).status_code, 422)
        trashed = self.client.post("/api/projects", json={"name": "휴지통"}, headers=self.h).json()["id"]
        with storage.transaction() as con:
            con.execute("INSERT INTO project_trash(project_id) VALUES(?)", (trashed,))
        self.assertEqual(self.post(f"/api/chat/messages/{assistant_id}/to-idea",
                                   {"project_id": trashed, "title": "x"}).status_code, 404)

    # ---- research loop

    def test_full_loop_two_iterations(self):
        self.fake.plan_responses = [["image segmentation transformer", "efficient segmentation survey"],
                                    ["image segmentation transformer", "lightweight segmentation distillation"]]
        run_id = self.start_run()
        detail = self.advance(run_id)
        self.assertEqual(detail["run"]["status"], "awaiting_review")
        self.assertEqual([s["stage"] for s in detail["steps"]], STAGES)
        self.assertTrue(all(s["status"] == "done" for s in detail["steps"]))
        self.assertEqual(len(detail["steps"][0]["prompt_hash"]), 64)
        self.assertIsNone(detail["steps"][1]["prompt_hash"])
        state = detail["state"]
        self.assertEqual(state["queries"], ["image segmentation transformer", "efficient segmentation survey"])
        self.assertTrue(all(c["key"].startswith("S") for c in state["candidates"]))
        self.assertTrue(all(e["quote"] in ABSTRACT for e in state["evidence"]))
        keys = {e["key"] for e in state["evidence"]}
        self.assertEqual([p["title"] for p in state["problems"]], ["Boundary accuracy", "Dataset gap"])
        self.assertEqual(state["problems"][0]["evidence"], ["E1"])
        self.assertTrue(all(set(p["evidence"]) <= keys for p in state["problems"]))
        self.assertEqual([m["problem_index"] for m in state["methods"]], [0])
        self.assertEqual(state["methods"][0]["evidence"], ["E1"])
        self.assertEqual([c["statement"] for c in state["contributions"]],
                         ["작은 객체 경계 정확도 평가", "도시 외 장면으로 일반화 검증"])
        # The closest-prior search uses the contribution's search_query, not the Korean statement (AC7).
        self.assertIn("small object boundary accuracy evaluation", self.fake.search_calls)
        self.assertNotIn("작은 객체 경계 정확도 평가", self.fake.search_calls)
        critique = state["critique"]
        self.assertNotIn("scores", critique)
        self.assertEqual(set(critique), {"weaknesses", "next_queries", "checks", "dropped_uncited", "note"})
        self.assertEqual([w["text"] for w in critique["weaknesses"]], ["표본이 작음"])
        self.assertEqual(critique["weaknesses"][0]["refs"], ["P1", "E1"])
        self.assertGreaterEqual(critique["dropped_uncited"], 1)
        self.assertEqual(state["critique"]["next_queries"],
                         ["lightweight segmentation distillation", "boundary refinement small objects"])

        feedback = self.post(f"/api/research-runs/{run_id}/feedback", {"note": "작은 객체에 집중", "focus_problem": 0})
        self.assertEqual(feedback.status_code, 200, feedback.text)
        self.assertEqual(feedback.json()["run"]["iteration"], 2)
        done = self.advance(run_id)
        self.assertEqual(done["run"]["status"], "completed")
        self.assertEqual(len(done["steps"]), 14)
        second = done["state"]
        self.assertEqual(second["queries"], ["lightweight segmentation distillation"])
        self.assertEqual(len(second["history"]), 1)
        self.assertEqual(second["history"][0]["note"], "작은 객체에 집중")
        plan_text = self.fake.stage_messages("plan")[-1][1]["content"]
        self.assertIn("작은 객체에 집중", plan_text)

    def test_feedback_rules(self):
        run_id = self.start_run()
        self.assertEqual(self.post(f"/api/research-runs/{run_id}/feedback", {"note": "x"}).status_code, 409)
        self.advance(run_id)
        self.assertEqual(self.post(f"/api/research-runs/{run_id}/feedback", {"focus_problem": 9}).status_code, 422)

    def test_repeated_queries_fall_back_to_topic_and_weakness(self):
        self.fake.plan_responses = [["image segmentation transformer"], ["image segmentation transformer"]]
        run_id = self.start_run()
        self.advance(run_id)
        self.post(f"/api/research-runs/{run_id}/feedback", {"note": ""})
        second = self.advance(run_id)["state"]
        self.assertEqual(second["queries"], ["image segmentation 표본이 작음"])

    def test_budget_exhausted(self):
        run_id = self.start_run(max_llm_calls=2)
        detail = self.advance(run_id)
        self.assertEqual(detail["run"]["status"], "budget_exhausted")
        self.assertEqual([s["stage"] for s in detail["steps"]], ["plan_queries", "search", "screen", "problems"])
        self.assertEqual(detail["run"]["llm_calls"], 2)
        self.assertEqual(detail["run"]["stop_reason"], "calls")
        self.assertEqual(self.client.post(f"/api/research-runs/{run_id}/step", headers=self.h).status_code, 409)

    def test_failed_stage_is_recorded_and_retry_succeeds(self):
        # One invalid answer is retried once (AC4); the stage fails only when both attempts are invalid.
        self.fake.fail_once = {"problems": 2}
        run_id = self.start_run()
        detail = self.advance(run_id)
        self.assertEqual(detail["run"]["status"], "failed_step")
        self.assertEqual(detail["run"]["stage"], "problems")
        self.assertEqual(detail["steps"][-1]["status"], "failed")
        self.assertTrue(detail["steps"][-1]["error"])
        retry = self.step(run_id)
        self.assertEqual(retry["steps"][-1]["status"], "done")
        self.assertEqual(retry["steps"][-1]["stage"], "problems")
        self.assertEqual(retry["run"]["stage"], "methods")
        self.assertEqual(retry["run"]["status"], "ready")

    def test_external_run_requires_matching_hash(self):
        llm.save_config(dict(EXTERNAL))
        body = self.run_body()
        preview = self.post("/api/research-runs/preview", body)
        self.assertEqual(preview.status_code, 200, preview.text)
        self.assertTrue(preview.json()["external"])
        self.assertIn("외부 서버", preview.json()["policy"])
        self.assertEqual(self.post("/api/research-runs", body).status_code, 409)
        self.assertEqual(self.post("/api/research-runs", {**body, "preview_hash": "0" * 64}).status_code, 409)
        created = self.post("/api/research-runs", {**body, "preview_hash": preview.json()["preview_hash"]})
        self.assertEqual(created.status_code, 201, created.text)
        self.assertEqual(created.json()["run"]["status"], "ready")

    def test_local_run_hash_is_optional(self):
        created = self.post("/api/research-runs", self.run_body())
        self.assertEqual(created.status_code, 201, created.text)

    def test_cancel_blocks_further_steps(self):
        run_id = self.start_run()
        cancelled = self.client.post(f"/api/research-runs/{run_id}/cancel", headers=self.h)
        self.assertEqual(cancelled.status_code, 200, cancelled.text)
        self.assertEqual(cancelled.json()["run"]["status"], "cancelled")
        self.assertEqual(self.client.post(f"/api/research-runs/{run_id}/step", headers=self.h).status_code, 409)
        self.assertEqual(self.client.post(f"/api/research-runs/{run_id}/cancel", headers=self.h).status_code, 409)

    def test_save_creates_ideas_and_gaps(self):
        run_id = self.start_run()
        self.advance(run_id)
        empty = self.post(f"/api/research-runs/{run_id}/save", {"project_id": self.project_id})
        self.assertEqual(empty.status_code, 422)
        saved = self.post(f"/api/research-runs/{run_id}/save",
                          {"project_id": self.project_id, "problems": [0], "contributions": [0]})
        self.assertEqual(saved.status_code, 201, saved.text)
        titles = sorted(i["title"] for i in self.client.get(f"/api/ideas?project_id={self.project_id}").json())
        self.assertEqual(titles, ["Boundary accuracy", "작은 객체 경계 정확도 평가"])
        with storage.transaction() as con:
            gaps = [dict(r) for r in con.execute("SELECT * FROM research_gaps WHERE project_id=?", (self.project_id,))]
        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0]["origin"], "research_loop")
        self.assertEqual(gaps[0]["gap_type"], "unaddressed_limitation")
        self.assertEqual(gaps[0]["status"], "candidate")
        evidence = json.loads(gaps[0]["evidence_json"])
        self.assertEqual(evidence[0]["quote"], ABSTRACT.split(". ")[0] + ".")
        self.assertIn(evidence[0]["quote"], ABSTRACT)

    def test_list_and_get_runs(self):
        run_id = self.start_run()
        listed = self.client.get("/api/research-runs").json()
        self.assertEqual([r["id"] for r in listed], [run_id])
        detail = self.client.get(f"/api/research-runs/{run_id}").json()
        self.assertEqual(detail["run"]["status"], "ready")
        self.assertEqual(detail["steps"], [])


if __name__ == "__main__":
    unittest.main()
