"""Offline checks for provider configuration and Chat Completions requests.

All configuration imports suppress the real dotenv files. HTTP calls, image
reads, and dotenv fixtures are mocked; no provider credentials or network are
required.
"""

from __future__ import annotations

import base64
import importlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, mock_open, patch


CORE_DIR = Path(__file__).resolve().parents[1] / "core"


def load_config(environment: dict[str, str] | None = None):
    """Evaluate only the supplied environment, never backend/.env or ../.env."""
    spec = importlib.util.spec_from_file_location(
        "isolated_model_config", CORE_DIR / "aliyun_config.py"
    )
    assert spec is not None and spec.loader is not None
    config = importlib.util.module_from_spec(spec)
    with patch.dict(os.environ, environment or {}, clear=True), patch.object(
        Path, "is_file", return_value=False
    ):
        spec.loader.exec_module(config)
    return config


def load_client(config):
    """Provide an isolated acfg before loading the client module."""
    core = importlib.import_module("core")
    spec = importlib.util.spec_from_file_location(
        "isolated_model_client", CORE_DIR / "aliyun_vl.py"
    )
    assert spec is not None and spec.loader is not None
    client = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {"core.aliyun_config": config}), patch.object(
        core, "aliyun_config", config, create=True
    ):
        spec.loader.exec_module(client)
    return client


def model_response(content="{}", *, finish_reason="stop"):
    response = MagicMock()
    response.__enter__.return_value = response
    response.read.return_value = json.dumps(
        {"choices": [{"message": {"content": content}, "finish_reason": finish_reason}]},
        ensure_ascii=False,
    ).encode("utf-8")
    return response


class ModelConfigTests(unittest.TestCase):
    def test_legacy_configuration_preserves_aliyun_behavior(self):
        config = load_config(
            {
                "DASHSCOPE_API_KEY": "fixture-asr-key",
                "ALIYUN_VL_MODEL": "fixture-old-omni",
                "ALIYUN_VL_BASE_URL": "https://old.example/v1/",
                "ALIYUN_TIMEOUT_SEC": "45",
            }
        )
        self.assertEqual(config.VL_PROVIDER, "aliyun")
        self.assertEqual(config.VL_MODEL, "fixture-old-omni")
        self.assertEqual(config.VL_API_KEY, "fixture-asr-key")
        self.assertEqual(config.VL_TEMPERATURE, 0.2)
        self.assertEqual(config.VL_MODALITIES, ["text"])
        self.assertEqual(config.VL_THINKING, "")
        self.assertEqual(config.VL_MAX_TOKENS, 800)
        self.assertEqual(config.VL_TIMEOUT_SEC, 45)
        self.assertEqual(
            config.vl_chat_completions_url(), "https://old.example/v1/chat/completions"
        )

    def test_new_variables_take_priority_and_keys_are_independent(self):
        config = load_config(
            {
                "VL_PROVIDER": " Moonshot ",
                "DASHSCOPE_API_KEY": "fixture-asr-key",
                "VL_API_KEY": "fixture-vl-key",
                "ALIYUN_VL_MODEL": "fixture-old-model",
                "ALIYUN_VL_BASE_URL": "https://old.example/v1",
                "VL_MODEL": "kimi-k2.6",
                "VL_BASE_URL": "https://new.example/v1",
                "ALIYUN_TIMEOUT_SEC": "30",
                "VL_TIMEOUT_SEC": "60",
            }
        )
        self.assertEqual(config.VL_PROVIDER, "moonshot")
        self.assertEqual(config.VL_MODEL, "kimi-k2.6")
        self.assertEqual(config.VL_BASE_URL, "https://new.example/v1")
        self.assertEqual(config.VL_API_KEY, "fixture-vl-key")
        self.assertEqual(config.DASHSCOPE_API_KEY, "fixture-asr-key")
        self.assertTrue(config.has_api_key())
        self.assertTrue(config.has_vl_api_key())
        self.assertEqual(config.VL_TIMEOUT_SEC, 60)

    def test_aliyun_explicit_vl_key_overrides_asr_key(self):
        config = load_config(
            {"DASHSCOPE_API_KEY": "fixture-asr-key", "VL_API_KEY": "fixture-vl-key"}
        )
        self.assertEqual(config.VL_API_KEY, "fixture-vl-key")
        self.assertEqual(config.DASHSCOPE_API_KEY, "fixture-asr-key")

    def test_moonshot_missing_key_does_not_reuse_asr_key(self):
        config = load_config(
            {"VL_PROVIDER": "moonshot", "DASHSCOPE_API_KEY": "fixture-asr-key"}
        )
        self.assertTrue(config.has_api_key())
        self.assertFalse(config.has_vl_api_key())
        self.assertEqual(config.VL_API_KEY, "")
        self.assertIsNone(config.VL_TEMPERATURE)
        self.assertEqual(config.VL_MODALITIES, [])

    def test_base_and_complete_urls_are_normalized_once(self):
        for base in (
            "https://gateway.example/v1",
            "https://gateway.example/v1/",
            "https://gateway.example/v1/chat/completions",
            "https://gateway.example/v1/chat/completions/",
        ):
            with self.subTest(base=base):
                config = load_config({"VL_BASE_URL": base})
                self.assertEqual(
                    config.vl_chat_completions_url(),
                    "https://gateway.example/v1/chat/completions",
                )

    def test_explicit_empty_optional_fields_disable_aliyun_defaults(self):
        config = load_config({"VL_TEMPERATURE": " ", "VL_MODALITIES": ""})
        self.assertIsNone(config.VL_TEMPERATURE)
        self.assertEqual(config.VL_MODALITIES, [])

    def test_dotenv_bom_quotes_comments_and_precedence(self):
        config = load_config()
        backend_path = Path("fixture-backend.env")
        repo_path = Path("fixture-repo.env")
        fixtures = {
            backend_path: (
                '\ufeffexport FIRST="quoted # value" # trailing comment\n'
                "SINGLE='single quoted value' # trailing comment\n"
                "UNQUOTED=plain # trailing comment\n"
                "VL_TEMPERATURE= # omit optional field\n"
                "VL_API_KEY=fixture#literal # trailing comment\n"
                "HASH=fixture#literal\n"
                "PRIORITY=from-backend\n"
                "FROM_ENV=from-backend\n"
            ).encode("utf-8"),
            repo_path: b"PRIORITY=from-repo\nFROM_REPO=repo-only\n",
        }

        def fixture_open(path, mode="r", encoding=None, errors=None, **kwargs):
            self.assertEqual(mode, "r")
            self.assertEqual(encoding, "utf-8-sig")
            return io.TextIOWrapper(io.BytesIO(fixtures[path]), encoding=encoding)

        with patch.dict(os.environ, {"FROM_ENV": "from-process"}, clear=True), patch.object(
            Path, "is_file", autospec=True, side_effect=lambda path: path in fixtures
        ), patch.object(Path, "open", autospec=True, side_effect=fixture_open):
            config._load_dotenv([backend_path, repo_path])
            self.assertEqual(os.environ["FIRST"], "quoted # value")
            self.assertEqual(os.environ["SINGLE"], "single quoted value")
            self.assertEqual(os.environ["UNQUOTED"], "plain")
            self.assertEqual(os.environ["VL_TEMPERATURE"], "")
            self.assertEqual(os.environ["VL_API_KEY"], "fixture#literal")
            self.assertEqual(os.environ["HASH"], "fixture#literal")
            self.assertEqual(os.environ["PRIORITY"], "from-backend")
            self.assertEqual(os.environ["FROM_ENV"], "from-process")
            self.assertEqual(os.environ["FROM_REPO"], "repo-only")

    def test_dotenv_unclosed_quote_is_rejected(self):
        config = load_config()
        with patch.dict(os.environ, {}, clear=True), patch.object(
            Path, "is_file", return_value=True
        ), patch.object(Path, "read_text", return_value='VL_MODEL="unfinished'):
            with self.assertRaisesRegex(ValueError, "引号未闭合"):
                config._load_dotenv([Path("fixture-invalid.env")])

    def test_invalid_temperatures_are_rejected(self):
        for value in ("not-a-number", "nan", "inf", "-inf"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "VL_TEMPERATURE"):
                    load_config({"VL_TEMPERATURE": value})

    def test_invalid_thinking_modes_are_rejected(self):
        for value in ("true", "false", "automatic", '{"type":"disabled"}'):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "VL_THINKING"):
                    load_config({"VL_THINKING": value})

    def test_nonpositive_token_limit_and_timeout_are_rejected(self):
        for name in ("VL_MAX_TOKENS", "VL_TIMEOUT_SEC"):
            for value in ("0", "-1"):
                with self.subTest(name=name, value=value):
                    with self.assertRaises(ValueError):
                        load_config({name: value})

    def test_describe_contains_no_fixture_keys(self):
        config = load_config(
            {"DASHSCOPE_API_KEY": "fixture-asr-key", "VL_API_KEY": "fixture-vl-key"}
        )
        description = config.describe()
        self.assertNotIn("fixture-asr-key", description)
        self.assertNotIn("fixture-vl-key", description)
        self.assertIn("asr_key=set", description)
        self.assertIn("vl_key=set", description)


class ModelClientTests(unittest.TestCase):
    def setUp(self):
        # Fail closed if a test forgets to supply its own fake HTTP response.
        guard = patch("urllib.request.urlopen", side_effect=AssertionError("Network disabled"))
        guard.start()
        self.addCleanup(guard.stop)
        self.config = load_config(
            {
                "VL_PROVIDER": "moonshot",
                "VL_API_KEY": "fixture-vl-key",
                "DASHSCOPE_API_KEY": "fixture-asr-key",
                "VL_MODEL": "kimi-k2.6",
                "VL_BASE_URL": "https://gateway.example/v1",
                "VL_THINKING": "disabled",
                "VL_MAX_TOKENS": "4096",
            }
        )
        self.client = load_client(self.config)

    def test_kimi_request_sends_base64_images_and_provider_parameters(self):
        jpeg = b"\xff\xd8fixture-jpeg\xff\xd9"
        with patch.object(self.client.os.path, "isfile", return_value=True), patch(
            "builtins.open", mock_open(read_data=jpeg)
        ), patch.object(
            self.client.urllib.request, "urlopen", return_value=model_response("  编码文本  ")
        ) as urlopen:
            text = self.client.call_qwen_vl("课堂提示", image_paths=["fixture-image.jpg"])

        self.assertEqual(text, "编码文本")
        urlopen.assert_called_once()
        request = urlopen.call_args.args[0]
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(request.full_url, "https://gateway.example/v1/chat/completions")
        self.assertEqual(request.get_header("Authorization"), "Bearer fixture-vl-key")
        self.assertEqual(urlopen.call_args.kwargs["timeout"], 120)
        self.assertEqual(payload["model"], "kimi-k2.6")
        self.assertEqual(payload["thinking"], {"type": "disabled"})
        self.assertEqual(payload["max_tokens"], 4096)
        self.assertFalse(payload["stream"])
        self.assertNotIn("temperature", payload)
        self.assertNotIn("modalities", payload)
        content = payload["messages"][0]["content"]
        self.assertEqual(content[1], {"type": "text", "text": "课堂提示"})
        self.assertEqual(content[0]["type"], "image_url")
        image_url = content[0]["image_url"]["url"]
        self.assertTrue(image_url.startswith("data:image/jpeg;base64,"))
        self.assertEqual(base64.b64decode(image_url.split(",", 1)[1]), jpeg)

    def test_explicit_call_parameters_override_config_and_content_parts_are_joined(self):
        content = [{"type": "text", "text": "分段"}, {"type": "text", "text": "回复"}]
        with patch.object(
            self.client.urllib.request, "urlopen", return_value=model_response(content)
        ) as urlopen:
            result = self.client.call_qwen_vl("prompt", temperature=0.6, max_tokens=2048)
        self.assertEqual(result, "分段回复")
        payload = json.loads(urlopen.call_args.args[0].data)
        self.assertEqual(payload["temperature"], 0.6)
        self.assertEqual(payload["max_tokens"], 2048)

    def test_legacy_aliyun_payload_preserves_modalities_and_temperature(self):
        config = load_config({"DASHSCOPE_API_KEY": "fixture-legacy-key"})
        with patch.object(self.client, "acfg", config), patch.object(
            self.client.urllib.request, "urlopen", return_value=model_response()
        ) as urlopen:
            self.client.call_qwen_vl("prompt")
        payload = json.loads(urlopen.call_args.args[0].data)
        self.assertEqual(payload["temperature"], 0.2)
        self.assertEqual(payload["modalities"], ["text"])
        self.assertEqual(payload["max_tokens"], 800)
        self.assertNotIn("thinking", payload)

    def test_unset_optional_parameters_are_not_sent(self):
        with patch.object(self.config, "VL_THINKING", ""), patch.object(
            self.client.urllib.request, "urlopen", return_value=model_response()
        ) as urlopen:
            self.client.call_qwen_vl("prompt")
        payload = json.loads(urlopen.call_args.args[0].data)
        self.assertNotIn("thinking", payload)
        self.assertNotIn("temperature", payload)
        self.assertNotIn("modalities", payload)

    def test_missing_moonshot_key_fails_before_http(self):
        config = load_config(
            {"VL_PROVIDER": "moonshot", "DASHSCOPE_API_KEY": "fixture-asr-key"}
        )
        with patch.object(self.client, "acfg", config), patch.object(
            self.client.urllib.request, "urlopen"
        ) as urlopen:
            with self.assertRaisesRegex(self.client.AliyunVLError, "VL_API_KEY"):
                self.client.call_qwen_vl("prompt")
        urlopen.assert_not_called()

    def test_truncated_output_is_rejected(self):
        with patch.object(
            self.client.urllib.request,
            "urlopen",
            return_value=model_response('{"behavior_code":"B1"}', finish_reason="length"),
        ):
            with self.assertRaisesRegex(self.client.AliyunVLError, "token 上限"):
                self.client.call_qwen_vl("prompt")

    def test_empty_final_content_is_rejected(self):
        for content in (None, "", " \n ", [], [{"type": "text", "text": ""}]):
            with self.subTest(content=content), patch.object(
                self.client.urllib.request, "urlopen", return_value=model_response(content)
            ):
                with self.assertRaisesRegex(self.client.AliyunVLError, "最终文本 content"):
                    self.client.call_qwen_vl("prompt")

    def test_absent_choices_is_rejected(self):
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = b'{"choices": []}'
        with patch.object(self.client.urllib.request, "urlopen", return_value=response):
            with self.assertRaisesRegex(self.client.AliyunVLError, "模型返回为空"):
                self.client.call_qwen_vl("prompt")

    def test_truncation_and_empty_content_produce_review_fallback(self):
        for content, finish_reason in (("partial", "length"), ("", "stop")):
            with self.subTest(content=content), patch.object(
                self.client, "extract_keyframes", return_value=[]
            ), patch.object(
                self.client.urllib.request,
                "urlopen",
                return_value=model_response(content, finish_reason=finish_reason),
            ), self.assertLogs(self.client.logger, level="ERROR"):
                result = self.client.code_segment("fixture-video.mp4", 0.0, 2.0, "课堂文本")
            self.assertEqual(result["behavior_code"], "B1")
            self.assertEqual(result["emotion_code"], "X0")
            self.assertEqual(result["confidence"], 0.0)
            self.assertTrue(result["needs_review"])

    def test_invalid_json_produces_review_fallback(self):
        with patch.object(self.client, "extract_keyframes", return_value=[]), patch.object(
            self.client.urllib.request, "urlopen", return_value=model_response("no valid JSON")
        ), self.assertLogs(self.client.logger, level="WARNING"):
            result = self.client.code_segment("fixture-video.mp4", 0.0, 2.0, "课堂文本")
        self.assertEqual(result["emotion_code"], "X0")
        self.assertEqual(result["confidence"], 0.0)
        self.assertTrue(result["needs_review"])

    def test_non_numeric_confidence_is_normalized_for_review(self):
        raw = json.dumps(
            {"behavior_code": "B1", "emotion_code": "U1", "confidence": "unknown"}
        )
        with patch.object(self.client, "extract_keyframes", return_value=[]), patch.object(
            self.client.urllib.request, "urlopen", return_value=model_response(raw)
        ):
            result = self.client.code_segment("fixture-video.mp4", 0.0, 2.0, "课堂文本")
        self.assertEqual(result["behavior_code"], "B1")
        self.assertEqual(result["emotion_code"], "U1")
        self.assertEqual(result["confidence"], 0.0)
        self.assertTrue(result["needs_review"])


if __name__ == "__main__":
    unittest.main()
