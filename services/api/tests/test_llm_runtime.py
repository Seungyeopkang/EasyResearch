"""LLM transport: cooperative stop during Ollama streaming (AC2), local runtime status (AC8), context buckets (AC9).

No test reaches a real server. urlopen and the runtime probe are replaced with fakes.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.error import URLError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import llm, storage

LOCAL = {"provider": "ollama", "base_url": "http://127.0.0.1:11434", "model": "fake"}
MESSAGES = [{"role": "user", "content": "hello"}]


class FakeStream:
    def __init__(self, lines):
        self.lines = list(lines)
        self.reads = 0
        self.closed = False

    def readline(self):
        self.reads += 1
        return self.lines.pop(0) if self.lines else b""

    def close(self):
        self.closed = True


def ollama_config(**extra):
    return {**LOCAL, "temperature": 0.2, "timeout": 5, "max_input_chars": 8000, **extra}


class StreamStopTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"EASYRESEARCH_DATA_DIR": self.temp.name})
        self.env.start()
        storage.init_db()
        llm.save_config(dict(LOCAL))

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_stop_after_first_line_ends_stream_without_reading_more(self):  # AC2
        stream = FakeStream([
            b'{"message": {"content": "first "}, "done": false}\n',
            b'{"message": {"content": "second"}, "done": false}\n',
            b'{"message": {"content": "third"}, "done": false}\n',
            b'{"done": true}\n',
        ])
        checks = []

        def should_stop():
            checks.append(True)
            # Continue for the first line, stop before reading the second.
            return None if len(checks) == 1 else "사용자가 중단했습니다"

        with patch.object(llm, "urlopen", return_value=stream):
            with self.assertRaises(llm.LLMError) as error:
                llm._http_transport(ollama_config(), MESSAGES, json_output=False, max_tokens=50, should_stop=should_stop)
        self.assertEqual(error.exception.code, "stopped")
        self.assertIn("중단", error.exception.message)
        self.assertEqual(stream.reads, 2, "the stream must not be read past the stop check")
        self.assertTrue(stream.closed)

    def test_stop_before_sending_never_opens_connection(self):  # AC2
        transport = Mock(return_value="never")
        with patch.object(llm, "transport", transport), patch.object(llm, "urlopen") as opened:
            with self.assertRaises(llm.LLMError) as error:
                llm.complete(MESSAGES, purpose="test", should_stop=lambda: "취소됨")
        self.assertEqual(error.exception.code, "stopped")
        transport.assert_not_called()
        opened.assert_not_called()

    def test_stop_check_without_reason_keeps_streaming(self):
        stream = FakeStream([b'{"message": {"content": "a"}, "done": false}\n',
                             b'{"message": {"content": "b"}, "done": true, "eval_count": 2}\n'])
        with patch.object(llm, "urlopen", return_value=stream):
            text = llm._http_transport(ollama_config(), MESSAGES, json_output=False, max_tokens=50,
                                       should_stop=lambda: None)
        self.assertEqual(text, "ab")
        self.assertTrue(stream.closed)

    def test_network_failure_on_open_maps_to_network_error(self):
        with patch.object(llm, "urlopen", side_effect=URLError("refused")):
            with self.assertRaises(llm.LLMError) as error:
                llm._http_transport(ollama_config(), MESSAGES, json_output=False, max_tokens=50)
        self.assertEqual(error.exception.code, "network_error")


class RuntimeStatusTests(unittest.TestCase):
    def status(self, size, size_vram, model="fake", name="fake:latest"):
        probe = Mock(return_value=[{"name": name, "size": size, "size_vram": size_vram}])
        with patch.object(llm, "runtime_probe", probe):
            return llm.runtime_status({**LOCAL, "model": model}), probe

    def test_model_fully_on_cpu_warns_with_all(self):  # AC8
        result, _ = self.status(size=1000, size_vram=0)
        self.assertTrue(result["applicable"] and result["reachable"])
        self.assertEqual(result["configured_gpu_percent"], 0)
        self.assertTrue(result["configured_loaded"])
        self.assertIn("CPU", result["warning"])
        self.assertIn("전부", result["warning"])
        self.assertIn("GPU 0%", result["warning"])

    def test_partial_gpu_warns_with_partly(self):  # AC8
        result, _ = self.status(size=1000, size_vram=500)
        self.assertEqual(result["configured_gpu_percent"], 50)
        self.assertIn("일부", result["warning"])
        self.assertIn("CPU", result["warning"])

    def test_at_or_above_ninety_percent_has_no_warning(self):  # AC8
        for vram in (900, 950, 1000):
            with self.subTest(vram=vram):
                result, _ = self.status(size=1000, size_vram=vram)
                self.assertIsNone(result["warning"])
                self.assertGreaterEqual(result["configured_gpu_percent"], 90)

    def test_just_below_ninety_warns(self):  # AC8 boundary
        result, _ = self.status(size=1000, size_vram=899)
        self.assertEqual(result["configured_gpu_percent"], 90)
        self.assertIsNone(result["warning"])
        result, _ = self.status(size=1000, size_vram=894)
        self.assertEqual(result["configured_gpu_percent"], 89)
        self.assertIn("일부", result["warning"])

    def test_tag_matching_and_unloaded_model(self):  # AC8 naming rule
        result, _ = self.status(size=1000, size_vram=0, model="fake", name="fake:latest")
        self.assertTrue(result["configured_loaded"])
        result, _ = self.status(size=1000, size_vram=0, model="fake:7b", name="fake:latest")
        self.assertFalse(result["configured_loaded"])
        self.assertIsNone(result["warning"])
        self.assertIsNone(result["configured_gpu_percent"])

    def test_zero_size_reports_zero_percent(self):
        result, _ = self.status(size=0, size_vram=0)
        self.assertEqual(result["models"][0]["gpu_percent"], 0)

    def test_probe_failure_is_unreachable_without_warning(self):  # AC8
        probe = Mock(side_effect=llm.LLMError("network_error", "down"))
        with patch.object(llm, "runtime_probe", probe):
            result = llm.runtime_status(dict(LOCAL))
        self.assertEqual(result, {"applicable": True, "reachable": False, "models": [], "warning": None})

    def test_remote_or_non_ollama_never_probes(self):  # AC8
        probe = Mock(side_effect=AssertionError("probe must not run"))
        cases = [
            {**LOCAL, "base_url": "https://ollama.example.test"},
            {"provider": "openai_compatible", "base_url": "http://127.0.0.1:1234/v1", "model": "m"},
            {"provider": "openai_compatible", "base_url": "https://example.test/v1", "model": "m"},
            {"provider": "none", "base_url": "", "model": ""},
        ]
        with patch.object(llm, "runtime_probe", probe):
            for config in cases:
                with self.subTest(config=config):
                    result = llm.runtime_status(config)
                    self.assertFalse(result["applicable"])
        probe.assert_not_called()


class NumCtxTests(unittest.TestCase):  # AC9
    def test_tiny_english_prompt_uses_smallest_bucket(self):
        self.assertEqual(llm.ollama_num_ctx([{"role": "user", "content": "hello"}], 200), 4096)

    def test_ten_thousand_hangul_characters_use_16k(self):
        self.assertEqual(llm.ollama_num_ctx([{"role": "user", "content": "가" * 10000}], 200), 16384)

    def test_two_hundred_thousand_characters_use_largest_bucket(self):
        self.assertEqual(llm.ollama_num_ctx([{"role": "user", "content": "a" * 200000}], 200), 32768)

    def test_hangul_boundary_between_4k_and_8k(self):
        # estimate = hangul + ceil(other/3) + max_tokens(200) + 512
        self.assertEqual(llm.ollama_num_ctx([{"role": "user", "content": "가" * 3384}], 200), 4096)
        self.assertEqual(llm.ollama_num_ctx([{"role": "user", "content": "가" * 3385}], 200), 8192)

    def test_other_text_is_counted_at_one_token_per_three_characters(self):
        self.assertEqual(llm.ollama_num_ctx([{"role": "user", "content": "a" * 10152}], 200), 4096)
        self.assertEqual(llm.ollama_num_ctx([{"role": "user", "content": "a" * 10153}], 200), 8192)

    def test_jamo_and_compatibility_jamo_count_as_hangul(self):
        self.assertEqual(llm.ollama_num_ctx([{"role": "user", "content": "ㄱ" * 3385}], 200), 8192)
        self.assertEqual(llm.ollama_num_ctx([{"role": "user", "content": "ᄀ" * 3385}], 200), 8192)

    def test_all_messages_and_max_tokens_are_included(self):
        messages = [{"role": "system", "content": "가" * 2000}, {"role": "user", "content": "가" * 2000}]
        self.assertEqual(llm.ollama_num_ctx(messages, 200), 8192)
        self.assertEqual(llm.ollama_num_ctx(messages[:1], 200), 4096)
        self.assertEqual(llm.ollama_num_ctx([{"role": "user", "content": "x"}], 6000), 8192)
        self.assertEqual(llm.ollama_num_ctx([{"role": "user", "content": "x"}], 100000), 32768)

    def test_result_is_always_a_known_bucket(self):
        for size in (0, 1, 3000, 3500, 7000, 20000, 90000):
            with self.subTest(size=size):
                self.assertIn(llm.ollama_num_ctx([{"role": "user", "content": "가" * size}], 512), llm.NUM_CTX_BUCKETS)


if __name__ == "__main__":
    unittest.main()
