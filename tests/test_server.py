from __future__ import annotations

import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from pgpt import server


class TestServerHelpers(unittest.TestCase):
    def test_extract_messages_uses_last_user_as_prompt(self) -> None:
        prompt, history = server._extract_messages(
            {
                "messages": [
                    {"role": "system", "content": "system"},
                    {"role": "user", "content": "first"},
                    {"role": "assistant", "content": "answer"},
                    {"role": "user", "content": "second"},
                ]
            }
        )
        self.assertEqual(prompt, "second")
        self.assertEqual(len(history), 3)
        self.assertEqual(history[-1]["role"], "assistant")

    def test_extract_messages_accepts_text_parts(self) -> None:
        prompt, _ = server._extract_messages(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "one"},
                            {"type": "text", "text": "two"},
                        ],
                    }
                ]
            }
        )
        self.assertEqual(prompt, "one\ntwo")

    def test_invalid_pgpt_option_types_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            server._completion(
                {
                    "messages": [{"role": "user", "content": "question"}],
                    "pgpt": {"context": "yes"},
                }
            )

    def test_web_override(self) -> None:
        self.assertIsNone(server._web_override("auto"))
        self.assertEqual(server._web_override("lookup"), "lookup")
        self.assertEqual(server._web_override("research"), "research")
        self.assertEqual(server._web_override("off"), "off")
        with self.assertRaises(ValueError):
            server._web_override("bad")

    def test_completion_maps_openai_request_to_pipeline(self) -> None:
        route = SimpleNamespace(
            execution="project",
            template="explain-code",
            model="qwen2.5-coder:3b",
            project="pgpt-cli",
        )
        result = SimpleNamespace(
            answer="hello",
            route=route,
            response_path=Path("/tmp/response.md"),
        )

        with patch.object(server, "run", return_value=result) as run_mock, patch.object(
            server,
            "skill_history",
            side_effect=lambda history, skill: history,
        ):
            completion = server._completion(
                {
                    "messages": [{"role": "user", "content": "question"}],
                    "pgpt": {
                        "project": "pgpt-cli",
                        "web": "off",
                        "context": True,
                        "deep": False,
                    },
                }
            )

        self.assertEqual(completion["choices"][0]["message"]["content"], "hello")
        self.assertEqual(completion["pgpt"]["route"]["execution"], "project")
        json.dumps(completion)
        kwargs = run_mock.call_args.kwargs
        self.assertEqual(kwargs["project_name"], "pgpt-cli")
        self.assertEqual(kwargs["web_override"], "off")
        self.assertTrue(kwargs["project_override"])
        self.assertFalse(kwargs["echo_route"])

    def test_loopback_origin_filter(self) -> None:
        self.assertEqual(
            server._loopback_origin("http://127.0.0.1:8765"),
            "http://127.0.0.1:8765",
        )
        self.assertEqual(
            server._loopback_origin("http://localhost:8765"),
            "http://localhost:8765",
        )
        self.assertIsNone(server._loopback_origin("https://example.com"))

    def test_stream_body_is_valid_sse_shape(self) -> None:
        completion = {
            "id": "chatcmpl-test",
            "created": 1,
            "model": "pgpt-cli",
            "choices": [
                {
                    "message": {"content": "hello"},
                }
            ],
        }
        text = server._stream_body(completion).decode("utf-8")
        self.assertIn("data: [DONE]", text)
        first = text.split("\n\n", 1)[0].removeprefix("data: ")
        parsed = json.loads(first)
        self.assertEqual(parsed["choices"][0]["delta"]["content"], "hello")


if __name__ == "__main__":
    unittest.main()
