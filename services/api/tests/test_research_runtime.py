"""Research loop runtime contract: background workers, cancel, retries, raw replay, time budget, critique checks.

The LLM transport, OpenAlex and the Ollama runtime probe are faked. Each test uses a temporary
EASYRESEARCH_DATA_DIR. Workers are joined in tearDown before the folder is removed.
Acceptance criteria (AC) numbers refer to docs/exec-plans/active/005-research-runtime-hardening.md.
"""
import json
import os
import re
import sys
import tempfile
import threading
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
LOCAL = {"provider": "ollama", "base_url": "http://127.0.0.1:11434", "model": "fake"}
FILE_KEY = "file-openalex-KEY-research-0123"
CHECK_FLAGS = {"single_source", "inherited_evidence", "no_prior_found", "prior_search_failed", "high_prior_overlap"}
STAGE_OF_SYSTEM = (("\"weaknesses\"", "critique"), ("\"contributions\"", "contributions"),
                   ("\"methods\"", "methods"), ("\"problems\"", "problems"), ("\"queries\"", "plan"))


def stage_of(system):
    for marker, stage in STAGE_OF_SYSTEM:
        if marker in system:
            return stage
    return "other"


class Fake:
    """Replaces llm.transport. Each call is classified by stage; behaviour can be scripted per stage.

    queue[stage]: items consumed one per call; an Exception is raised, a str is returned as raw text.
    delay[stage]: seconds the call takes (cooperative: honours should_stop).
    hold[stage]: threading.Event the call waits for (cooperative; capped at 30 s).
    hold_topic[marker]: like hold, for plan calls whose prompt contains the marker.
    """

    def __init__(self):
        self.lock = threading.Lock()
        self.calls = []
        self.queue = {}
        self.delay = {}
        self.hold = {}
        self.hold_topic = {}
        self.started = threading.Event()
        self.plan_queries = ["image segmentation transformer", "efficient segmentation survey"]
        self.search_calls = []
        self.search_keys = []
        self.empty_queries = set()
        self._counter = 0

    def __call__(self, config, messages, *, json_output, max_tokens, should_stop=None, schema=None, **_):
        stage = stage_of(messages[0]["content"])
        with self.lock:
            self.calls.append((stage, messages))
            queued = self.queue[stage].pop(0) if self.queue.get(stage) else None
        self._wait(stage, messages, should_stop)
        if isinstance(queued, BaseException):
            raise queued
        if queued is not None:
            return queued
        return self.respond(stage)

    def _wait(self, stage, messages, should_stop):
        event = self.hold.get(stage)
        seconds = self.delay.get(stage, 0)
        user_text = messages[-1]["content"]
        if stage == "plan":
            for marker, marked in self.hold_topic.items():
                if marker in user_text:
                    event = marked
        if event is None and not seconds:
            return
        self.started.set()
        deadline = time.monotonic() + (30.0 if event is not None else seconds)
        while time.monotonic() < deadline:
            if event is not None and event.is_set():
                return
            if should_stop is not None:
                reason = should_stop()
                if reason:
                    raise llm.LLMError("stopped", str(reason))
            time.sleep(0.02)

    def respond(self, stage):
        if stage == "plan":
            return json.dumps({"queries": list(self.plan_queries)})
        if stage == "problems":
            return json.dumps({"problems": [
                {"title": "Boundary accuracy", "statement": "작은 객체의 경계 정확도", "type": "unaddressed_limitation",
                 "why_open": "근거가 제한적", "evidence": ["E1", "E99"]},
                {"title": "Dataset gap", "statement": "도시 장면만 다룸", "type": "missing_dataset_or_metric",
                 "why_open": "", "evidence": ["E2"]},
            ]})
        if stage == "methods":
            # E404 is not a shown key, so the method must inherit the evidence of problem 0 (E1).
            return json.dumps({"methods": [
                {"problem_index": 0, "title": "경계 손실 보정", "idea": "경계 가중 손실을 시험한다",
                 "expected_gain": "경계 정확도 개선 가능", "risks": "데이터 편향", "evidence": ["E404"]},
            ]})
        if stage == "contributions":
            return json.dumps({"contributions": [
                {"statement": "작은 객체 경계 정확도 평가", "search_query": "small object boundary accuracy evaluation"},
                {"statement": "도시 외 장면으로 일반화 검증", "search_query": "generalization beyond urban scenes segmentation"}]})
        if stage == "critique":
            return json.dumps({"weaknesses": [
                {"text": "표본이 작음", "refs": ["P1", "E1"]},
                {"text": "근거 인용 없음", "refs": []},
                {"text": "존재하지 않는 키", "refs": ["Z9"]}],
                "next_queries": ["lightweight segmentation distillation"]})
        raise AssertionError("unexpected stage " + stage)

    def search(self, query, limit=10, api_key=None):
        with self.lock:
            self.search_calls.append(query)
            # The engine passes no key; search_openalex resolves openalex_key() itself. Record what it would send.
            self.search_keys.append(api_key if api_key is not None else scholarly.openalex_key())
            if query in self.empty_queries:
                return []
            records = []
            for _ in range(2):
                self._counter += 1
                n = self._counter
                records.append({"source": "openalex", "source_id": "https://openalex.org/W%d" % n,
                                "title": "Paper %d" % n, "authors": [], "year": 2021, "doi": "10.1000/p%d" % n,
                                "abstract": ABSTRACT, "url": "https://openalex.org/W%d" % n, "pdf_url": None})
            return records[:limit]

    def messages_for(self, stage):
        with self.lock:
            return [messages for name, messages in self.calls if name == stage]

    def count(self, stage):
        return len(self.messages_for(stage))


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"EASYRESEARCH_DATA_DIR": self.temp.name})
        self.env.start()
        os.environ.pop("OPENALEX_API_KEY", None)
        self.client = TestClient(app)
        self.client.__enter__()
        self.h = {"X-EasyResearch": "1"}
        self.original_transport = llm.transport
        self.fake = Fake()
        llm.transport = self.fake
        self.search_patch = patch.object(scholarly, "search_openalex", side_effect=self.fake.search)
        self.search_patch.start()
        self.backoff_patch = patch.object(research_agent, "_backoff_seconds", return_value=0)
        self.backoff_patch.start()
        self.probe_patch = patch.object(llm, "runtime_probe",
                                        return_value=[{"name": "fake:latest", "size": 1000, "size_vram": 1000}])
        self.probe_patch.start()
        llm.save_config(dict(LOCAL))
        self.seed_id = self.make_paper("Seed study", ABSTRACT, "10.1000/seed")
        self.project_id = self.client.post("/api/projects", json={"name": "연구"}, headers=self.h).json()["id"]

    def tearDown(self):
        research_agent._join_workers(10)  # workers must not outlive the temporary folder
        self.probe_patch.stop()
        self.backoff_patch.stop()
        self.search_patch.stop()
        llm.transport = self.original_transport
        self.client.__exit__(None, None, None)
        self.env.stop()
        self.temp.cleanup()

    # ---- helpers

    def make_paper(self, title, abstract, doi):
        response = self.client.post("/api/papers", json={"title": title, "authors": [], "doi": doi}, headers=self.h)
        self.assertEqual(response.status_code, 201, response.text)
        paper_id = response.json()["id"]
        with storage.transaction() as con:
            con.execute("UPDATE papers SET abstract=?, year=? WHERE id=?", (abstract, 2022, paper_id))
        return paper_id

    def run_body(self, **extra):
        body = {"topic": "image segmentation", "project_id": self.project_id, "seed_paper_ids": [self.seed_id],
                "max_iterations": 2, "papers_per_iteration": 3}
        body.update(extra)
        return body

    def start_run(self, **extra):
        response = self.client.post("/api/research-runs", json=self.run_body(**extra), headers=self.h)
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()["run"]["id"]

    def get_detail(self, run_id):
        return self.client.get(f"/api/research-runs/{run_id}").json()

    def wait_idle(self, run_id, timeout=20.0):
        deadline = time.monotonic() + timeout
        while True:
            detail = self.get_detail(run_id)
            if not detail["run"]["busy"]:
                return detail
            if time.monotonic() > deadline:
                self.fail("research run stayed busy")
            time.sleep(0.02)

    def post_action(self, run_id, action, body=None):
        if body is None:
            return self.client.post(f"/api/research-runs/{run_id}/{action}", headers=self.h)
        return self.client.post(f"/api/research-runs/{run_id}/{action}", json=body, headers=self.h)

    def advance(self, run_id):
        response = self.post_action(run_id, "advance")
        self.assertEqual(response.status_code, 202, response.text)
        return self.wait_idle(run_id)

    def step(self, run_id):
        response = self.post_action(run_id, "step")
        self.assertEqual(response.status_code, 202, response.text)
        return self.wait_idle(run_id)

    def edit_run_row(self, run_id, mutate_config=None, mutate_state=None):
        with storage.transaction() as con:
            row = con.execute("SELECT config_json, state_json FROM research_runs WHERE id=?", (run_id,)).fetchone()
            config = json.loads(row["config_json"])
            state = json.loads(row["state_json"])
            if mutate_config:
                mutate_config(config)
            if mutate_state:
                mutate_state(state)
            con.execute("UPDATE research_runs SET config_json=?, state_json=? WHERE id=?",
                        (json.dumps(config, ensure_ascii=False), json.dumps(state, ensure_ascii=False), run_id))

    # ---- AC1: background worker, 202, busy flag, per-run busy conflicts

    def test_ac1_advance_returns_202_quickly_and_reports_busy(self):  # AC1
        self.fake.delay["plan"] = 3.0
        run_id = self.start_run()
        began = time.monotonic()
        response = self.post_action(run_id, "advance")
        self.assertLess(time.monotonic() - began, 1.0)
        self.assertEqual(response.status_code, 202, response.text)
        self.assertEqual(response.json()["run"]["id"], run_id)
        view = self.get_detail(run_id)["run"]
        self.assertIs(view["busy"], True)
        self.assertEqual(view["status"], "running")
        self.assertIsNotNone(view["elapsed_seconds"])
        self.assertEqual(view["max_run_seconds"], 2700)

        again = self.post_action(run_id, "advance")
        self.assertEqual(again.status_code, 409, again.text)
        self.assertEqual(again.json()["detail"]["code"], "run_busy")
        self.assertEqual(self.post_action(run_id, "step").status_code, 409)
        feedback = self.post_action(run_id, "feedback", {"note": "중간 피드백"})
        self.assertEqual(feedback.status_code, 409)
        self.assertEqual(feedback.json()["detail"]["code"], "run_busy")

        done = self.wait_idle(run_id)
        self.assertEqual(done["run"]["status"], "awaiting_review")
        self.assertIs(done["run"]["busy"], False)
        self.assertEqual(self.fake.count("plan"), 1)

    def test_ac1_list_endpoint_reports_busy_too(self):  # AC1
        self.fake.delay["plan"] = 2.0
        run_id = self.start_run()
        self.post_action(run_id, "advance")
        listed = self.client.get("/api/research-runs").json()
        row = [r for r in listed if r["id"] == run_id][0]
        self.assertIs(row["busy"], True)
        self.wait_idle(run_id)

    # ---- AC2: immediate cancel of an in-flight call

    def test_ac2_cancel_stops_in_flight_call_within_a_second(self):  # AC2
        self.fake.hold["plan"] = threading.Event()  # never set: the call runs until should_stop fires
        run_id = self.start_run()
        self.assertEqual(self.post_action(run_id, "advance").status_code, 202)
        self.assertTrue(self.fake.started.wait(5), "the plan call never started")
        began = time.monotonic()
        cancelled = self.post_action(run_id, "cancel")
        self.assertLess(time.monotonic() - began, 1.0)
        self.assertEqual(cancelled.status_code, 200, cancelled.text)
        self.assertEqual(cancelled.json()["run"]["status"], "cancelled")

        detail = self.wait_idle(run_id)
        self.assertEqual(detail["run"]["status"], "cancelled")
        self.assertEqual(detail["steps"][-1]["stage"], "plan_queries")
        self.assertEqual(detail["steps"][-1]["status"], "cancelled")
        time.sleep(0.5)  # a late worker must not overwrite the cancelled state
        self.assertEqual(self.get_detail(run_id)["run"]["status"], "cancelled")
        self.assertEqual(self.post_action(run_id, "step").status_code, 409)
        self.assertEqual(self.post_action(run_id, "cancel").status_code, 409)

    # ---- AC3: runs are isolated

    def test_ac3_a_slow_run_does_not_block_another_run(self):  # AC3
        release = threading.Event()
        self.fake.hold_topic["SLOWTOPIC"] = release
        slow = self.start_run(topic="SLOWTOPIC 느린 주제")
        fast = self.start_run(topic="빠른 주제")
        self.assertEqual(self.post_action(slow, "advance").status_code, 202)
        self.assertTrue(self.fake.started.wait(5))
        self.assertEqual(self.post_action(fast, "advance").status_code, 202)
        fast_detail = self.wait_idle(fast)
        self.assertEqual(fast_detail["run"]["status"], "awaiting_review")
        slow_view = self.get_detail(slow)["run"]
        self.assertIs(slow_view["busy"], True, "the slow run must still be in flight")
        self.assertEqual(self.post_action(slow, "advance").status_code, 409)
        release.set()
        self.assertEqual(self.wait_idle(slow)["run"]["status"], "awaiting_review")

    # ---- AC4: retries, validation, budget

    def test_ac4_transient_errors_are_retried_exactly_once(self):  # AC4
        cases = [("timeout", None), ("network_error", None), ("http_error", 503), ("rate_limited", 429)]
        for code, status in cases:
            with self.subTest(code=code, status=status):
                self.fake.calls.clear()
                self.fake.queue = {"problems": [llm.LLMError(code, "일시 오류", status),
                                                llm.LLMError(code, "일시 오류", status)]}
                run_id = self.start_run()
                detail = self.advance(run_id)
                self.assertEqual(detail["run"]["status"], "failed_step")
                self.assertEqual(detail["run"]["stage"], "problems")
                self.assertEqual(self.fake.count("problems"), 2)
                self.assertEqual(detail["steps"][-1]["status"], "failed")
                self.assertEqual(detail["run"]["llm_calls"], 3)  # plan + two problems attempts

    def test_ac4_auth_and_client_errors_are_not_retried(self):  # AC4
        for code, status in (("auth_error", 401), ("auth_error", 403), ("http_error", 400)):
            with self.subTest(code=code, status=status):
                self.fake.calls.clear()
                self.fake.queue = {"problems": [llm.LLMError(code, "인증 또는 요청 오류", status)]}
                run_id = self.start_run()
                detail = self.advance(run_id)
                self.assertEqual(detail["run"]["status"], "failed_step")
                self.assertEqual(self.fake.count("problems"), 1)

    def test_ac4_invalid_output_is_asked_again_once_with_the_reason(self):  # AC4
        self.fake.queue = {"problems": ["이것은 JSON이 아닙니다"]}
        run_id = self.start_run()
        detail = self.advance(run_id)
        self.assertEqual(detail["run"]["status"], "awaiting_review")
        calls = self.fake.messages_for("problems")
        self.assertEqual(len(calls), 2)
        retry = calls[1]
        self.assertEqual(retry[-2]["role"], "assistant")
        self.assertEqual(retry[-2]["content"], "이것은 JSON이 아닙니다")
        self.assertEqual(retry[-1]["role"], "user")
        # The reason is the parse failure; it names the JSON format problem.
        self.assertIn("JSON", retry[-1]["content"])
        problems_step = [s for s in detail["steps"] if s["stage"] == "problems"][0]
        self.assertEqual(problems_step["status"], "done")
        self.assertEqual(len(problems_step["output"]["attempts"]), 2)
        # Every attempt is counted: plan 1 + problems 2 + methods 1 + contributions 1 + critique 1.
        self.assertEqual(detail["run"]["llm_calls"], 6)

    def test_ac4_call_budget_refuses_the_retry_mid_stage(self):  # AC4
        self.fake.queue = {"problems": ["이것은 JSON이 아닙니다"]}
        run_id = self.start_run(max_llm_calls=2)  # plan (1) + first problems attempt (2); a retry would be a 3rd
        detail = self.advance(run_id)
        self.assertEqual(detail["run"]["status"], "budget_exhausted")
        self.assertEqual(detail["run"]["stop_reason"], "calls")
        self.assertEqual(self.fake.count("problems"), 1)
        self.assertEqual(detail["run"]["llm_calls"], 2)
        self.assertEqual(detail["steps"][-1]["status"], "failed")

    # ---- AC5: raw responses and replay

    def test_ac5_failed_validation_keeps_raw_response_and_attempts(self):  # AC5
        self.fake.queue = {"problems": ["이것은 JSON이 아닙니다", "두 번째 응답도 JSON이 아닙니다"]}
        run_id = self.start_run()
        detail = self.advance(run_id)
        self.assertEqual(detail["run"]["status"], "failed_step")
        step = detail["steps"][-1]
        self.assertEqual(step["stage"], "problems")
        self.assertEqual(step["status"], "failed")
        self.assertIn("JSON이 아닙니다", step["output"]["raw_response"])
        self.assertIs(step["output"]["raw_truncated"], False)
        self.assertEqual(len(step["output"]["attempts"]), 2)

    def plan_prompt_hash(self, run_id):
        # Computed exactly as the engine does: the plan messages built from the run's stored seed snapshot.
        state = json.loads(self.get_raw_state(run_id))
        messages = research_agent._plan_messages("image segmentation", state["seed_snapshot"], 1, None,
                                                 research_agent._budget())
        return llm.preview(messages, purpose=research_agent.PLAN_PURPOSE, json_output=True)["preview_hash"]

    def get_raw_state(self, run_id):
        with storage.transaction() as con:
            return con.execute("SELECT state_json FROM research_runs WHERE id=?", (run_id,)).fetchone()["state_json"]

    def insert_interrupted_plan(self, run_id, prompt_hash, raw_response, raw_truncated=False):
        output = {"raw_response": raw_response, "raw_truncated": raw_truncated, "attempt": 1}
        with storage.transaction() as con:
            cursor = con.execute(
                "INSERT INTO research_steps(run_id,iteration,stage,status,input_json,output_json,prompt_hash) "
                "VALUES(?,?,?,?,?,?,?)",
                (run_id, 1, "plan_queries", "running", "{}", json.dumps(output, ensure_ascii=False), prompt_hash))
            return cursor.lastrowid

    def test_ac5_interrupted_step_with_same_prompt_is_replayed_without_llm(self):  # AC5
        run_id = self.start_run()
        prompt_hash = self.plan_prompt_hash(run_id)
        raw = json.dumps({"queries": ["image segmentation transformer", "efficient segmentation survey"]})
        interrupted_id = self.insert_interrupted_plan(run_id, prompt_hash, raw)
        detail = self.step(run_id)
        self.assertEqual(self.fake.count("plan"), 0, "the saved response must be reused, not requested again")
        plan_steps = [s for s in detail["steps"] if s["stage"] == "plan_queries"]
        self.assertEqual(plan_steps[-1]["status"], "done")
        self.assertEqual(plan_steps[-1]["output"]["replayed_from_step"], interrupted_id)
        self.assertEqual(detail["run"]["llm_calls"], 0)
        self.assertEqual(detail["run"]["stage"], "search")
        self.assertEqual(detail["state"]["queries"], ["image segmentation transformer", "efficient segmentation survey"])

    def test_ac5_replay_requires_same_prompt_and_untruncated_raw(self):  # AC5
        run_id = self.start_run()
        self.insert_interrupted_plan(run_id, "0" * 64, json.dumps({"queries": ["stale query"]}))
        detail = self.step(run_id)
        self.assertEqual(self.fake.count("plan"), 1, "a different prompt hash must not be replayed")
        self.assertNotIn("replayed_from_step", [s for s in detail["steps"] if s["stage"] == "plan_queries"][-1]["output"])

        other = self.start_run()
        prompt_hash = self.plan_prompt_hash(other)
        self.insert_interrupted_plan(other, prompt_hash, json.dumps({"queries": ["cut off"]}), raw_truncated=True)
        self.step(other)
        self.assertEqual(self.fake.count("plan"), 2, "a truncated raw response must not be replayed")

    # ---- AC6: run time budget

    def test_ac6_time_budget_stops_an_in_flight_call(self):  # AC6
        self.fake.delay["plan"] = 30
        run_id = self.start_run()
        self.edit_run_row(run_id, mutate_config=lambda c: c.update(max_run_seconds=1))
        began = time.monotonic()
        detail = self.advance(run_id)
        self.assertLess(time.monotonic() - began, 10)
        self.assertEqual(detail["run"]["status"], "budget_exhausted")
        self.assertEqual(detail["run"]["stop_reason"], "time")
        self.assertEqual(detail["steps"][-1]["status"], "failed")
        self.assertEqual(detail["run"]["max_run_seconds"], 1)

    def test_ac6_time_waiting_for_review_is_not_counted(self):  # AC6
        run_id = self.start_run()
        detail = self.advance(run_id)
        self.assertEqual(detail["run"]["status"], "awaiting_review")
        first = detail["run"]["elapsed_seconds"]
        time.sleep(1.1)
        second = self.get_detail(run_id)["run"]["elapsed_seconds"]
        self.assertEqual(second, first)

    def test_ac6_run_without_budget_field_uses_2700_seconds(self):  # AC6
        run_id = self.start_run()
        self.edit_run_row(run_id, mutate_config=lambda c: c.pop("max_run_seconds", None))
        view = self.get_detail(run_id)["run"]
        self.assertEqual(view["max_run_seconds"], 2700)
        detail = self.advance(run_id)
        self.assertEqual(detail["run"]["status"], "awaiting_review")

    # ---- AC7: critique checks, search_query, legacy runs

    def test_ac7_critique_has_cited_weaknesses_and_code_checks(self):  # AC7
        run_id = self.start_run()
        self.fake.empty_queries = {"generalization beyond urban scenes segmentation"}
        detail = self.advance(run_id)
        self.assertEqual(detail["run"]["status"], "awaiting_review")
        critique = detail["state"]["critique"]
        self.assertNotIn("scores", critique)
        self.assertEqual(set(critique), {"weaknesses", "next_queries", "checks", "dropped_uncited", "note"})
        self.assertEqual([w["text"] for w in critique["weaknesses"]], ["표본이 작음"])
        self.assertEqual(critique["weaknesses"][0]["refs"], ["P1", "E1"])
        for weakness in critique["weaknesses"]:
            self.assertTrue(weakness["refs"])
            for ref in weakness["refs"]:
                self.assertRegex(ref, r"^[PMCE]\d+$")
        self.assertGreaterEqual(critique["dropped_uncited"], 2)  # the uncited item and the unknown key Z9
        self.assertIsInstance(critique["note"], str)

        checks = critique["checks"]
        self.assertTrue({"problems", "methods", "contributions", "summary"} <= set(checks))
        self.assertGreaterEqual(len(checks["problems"]), 1)
        for problem in checks["problems"]:
            for field in ("key", "title", "evidence_count", "source_papers", "seed_evidence", "flags"):
                self.assertIn(field, problem)
            self.assertLessEqual(set(problem["flags"]), CHECK_FLAGS)
            self.assertEqual("single_source" in problem["flags"], problem["source_papers"] < 2)

        method = checks["methods"][0]
        for field in ("key", "problem", "evidence_inherited", "flags"):
            self.assertIn(field, method)
        self.assertIs(method["evidence_inherited"], True)
        self.assertIn("inherited_evidence", method["flags"])
        self.assertEqual(detail["state"]["methods"][0]["evidence"], ["E1"])

        contribution = checks["contributions"][0]
        for field in ("key", "search_query", "closest_prior_count", "prior_overlap", "prior_overlap_label", "flags"):
            self.assertIn(field, contribution)
        self.assertEqual(contribution["search_query"], "small object boundary accuracy evaluation")
        self.assertIn("small object boundary accuracy evaluation", self.fake.search_calls)
        self.assertNotIn("작은 객체 경계 정확도 평가", self.fake.search_calls)
        self.assertIn(contribution["prior_overlap_label"], {"높음", "보통", "낮음"})
        self.assertTrue(0 <= contribution["prior_overlap"] <= 1)

        empty = checks["contributions"][1]
        self.assertEqual(empty["closest_prior_count"], 0)
        self.assertIn("no_prior_found", empty["flags"])
        self.assertIsInstance(checks["summary"], dict)
        for flag_list in [p["flags"] for p in checks["problems"]] + [m["flags"] for m in checks["methods"]] + \
                [c["flags"] for c in checks["contributions"]]:
            self.assertLessEqual(set(flag_list), CHECK_FLAGS)

    def test_ac7_legacy_critique_run_accepts_feedback_and_carries_weakness(self):  # AC7
        run_id = self.start_run()
        self.assertEqual(self.advance(run_id)["run"]["status"], "awaiting_review")
        legacy = {"scores": {"novelty": 4, "feasibility": 3, "evidence": 5, "clarity": 4},
                  "weaknesses": ["레거시 약점 문장"], "next_queries": ["legacy query one"]}
        self.edit_run_row(run_id, mutate_state=lambda s: s.update(critique=legacy))
        response = self.post_action(run_id, "feedback", {"note": ""})
        self.assertEqual(response.status_code, 200, response.text)
        self.wait_idle(run_id)
        done = self.advance(run_id)
        self.assertEqual(done["run"]["status"], "completed")
        plan_text = self.fake.messages_for("plan")[-1][-1]["content"]
        self.assertIn("레거시 약점 문장", plan_text)

    # ---- AC8: runtime status recorded per step

    def test_ac8_cpu_only_model_is_recorded_on_step_and_shown_on_run(self):  # AC8
        with patch.object(llm, "runtime_probe", return_value=[{"name": "fake:latest", "size": 1000, "size_vram": 0}]):
            run_id = self.start_run()
            detail = self.advance(run_id)
        runtime = detail["steps"][0]["output"]["runtime"]
        self.assertEqual(runtime["gpu_percent"], 0)
        self.assertIn("CPU", runtime["warning"])
        self.assertIn("CPU", detail["run"]["runtime_warning"])

    def test_ac8_gpu_resident_model_has_no_runtime_warning(self):  # AC8
        run_id = self.start_run()
        detail = self.advance(run_id)
        self.assertEqual(detail["steps"][0]["output"]["runtime"]["gpu_percent"], 100)
        self.assertFalse(detail["run"].get("runtime_warning"))

    # ---- AC10: research loop uses the saved OpenAlex key

    def test_ac10_research_search_uses_saved_openalex_key(self):  # AC10
        scholarly.save_openalex_key(FILE_KEY)
        try:
            run_id = self.start_run()
            detail = self.advance(run_id)
        finally:
            scholarly.save_openalex_key(None, clear=True)
        self.assertEqual(detail["run"]["status"], "awaiting_review")
        self.assertTrue(self.fake.search_keys)
        self.assertTrue(all(key == FILE_KEY for key in self.fake.search_keys), self.fake.search_keys)


if __name__ == "__main__":
    unittest.main()
