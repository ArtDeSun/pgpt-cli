from __future__ import annotations

import json
import tempfile
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
        self.assertEqual([item["role"] for item in history], ["user", "assistant", "system"])

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

    def test_completion_maps_request_and_exposes_timing(self) -> None:
        route = SimpleNamespace(
            execution="project",
            template="explain-code",
            model="qwen2.5-coder:3b",
            project="pgpt-cli",
            deep=False,
            reason="test",
            decision=None,
        )
        timing = SimpleNamespace(
            total=2.5,
            phases={"Routing": 0.2, "Generation": 2.0},
            metrics={},
        )
        result = SimpleNamespace(
            answer="hello",
            route=route,
            timing=timing,
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
        self.assertEqual(completion["pgpt"]["timing"]["total_seconds"], 2.5)
        json.dumps(completion)
        kwargs = run_mock.call_args.kwargs
        self.assertEqual(kwargs["project_name"], "pgpt-cli")
        self.assertEqual(kwargs["web_override"], "off")
        self.assertTrue(kwargs["project_override"])
        self.assertFalse(kwargs["echo_route"])

    def test_response_listing_and_safe_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            older = root / "older.md"
            newer = root / "newer.md"
            older.write_text("old", encoding="utf-8")
            newer.write_text("new", encoding="utf-8")
            with patch.object(server, "_response_root", return_value=root):
                rows = server._list_responses()
                self.assertEqual({row["name"] for row in rows}, {"older.md", "newer.md"})
                self.assertEqual(server._safe_response_path("newer.md"), newer)
                with self.assertRaises(ValueError):
                    server._safe_response_path("../newer.md")
                with self.assertRaises(ValueError):
                    server._safe_response_path("newer.txt")

    def test_loopback_origin_filter(self) -> None:
        self.assertEqual(server._loopback_origin("http://127.0.0.1:8765"), "http://127.0.0.1:8765")
        self.assertEqual(server._loopback_origin("http://localhost:8765"), "http://localhost:8765")
        self.assertIsNone(server._loopback_origin("https://example.com"))

    def test_stream_body_is_valid_sse_shape(self) -> None:
        completion = {
            "id": "chatcmpl-test",
            "created": 1,
            "model": "pgpt-cli",
            "choices": [{"message": {"content": "hello"}}],
        }
        text = server._stream_body(completion).decode("utf-8")
        self.assertIn("data: [DONE]", text)
        first = text.split("\n\n", 1)[0].removeprefix("data: ")
        parsed = json.loads(first)
        self.assertEqual(parsed["choices"][0]["delta"]["content"], "hello")


if __name__ == "__main__":
    unittest.main()
