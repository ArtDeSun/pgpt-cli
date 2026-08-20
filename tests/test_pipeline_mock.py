from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pgpt.runtime.pipeline as pipeline
from pgpt.routing.types import RoutingDecision
from pgpt.runtime.route import Route


def fake_stream_chat(*, on_text, **kwargs):
    on_text("Hello")
    on_text(" world")
    return {
        "load_duration": 100_000_000,
        "prompt_eval_duration": 200_000_000,
        "prompt_eval_count": 10,
        "eval_duration": 300_000_000,
        "eval_count": 6,
        "total_duration": 600_000_000,
        "done_reason": "stop",
    }


class TestPipeline(unittest.TestCase):
    def test_streamed_markdown_timing_and_callbacks_without_live_models(self) -> None:
        decision = RoutingDecision(
            source="none",
            web_mode=None,
            task="general",
            freshness="stable",
            project_evidence=False,
            reason="test route",
        )
        route = Route(
            decision=decision,
            execution="local",
            template="general",
            model="test-model",
            deep=False,
            project=None,
            reason="test route",
        )
        chunks: list[str] = []
        statuses: list[str] = []

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "response.md"
            with patch.object(pipeline, "has_symbol_hit", return_value=False), patch.object(
                pipeline, "resolve_route", return_value=decision
            ), patch.object(
                pipeline.Route, "from_decision", return_value=route
            ), patch.object(
                pipeline, "stream_chat", side_effect=fake_stream_chat
            ), patch.object(
                pipeline,
                "verify_answer",
                return_value=SimpleNamespace(passed=True, issues=[]),
            ), patch.object(
                pipeline, "response_path", return_value=output
            ):
                result = pipeline.run(
                    "What is dependency injection?",
                    project_name="pgpt-cli",
                    echo_route=False,
                    on_chunk=chunks.append,
                    on_status=lambda _frame, label, _elapsed, _completed: statuses.append(label),
                )

            text = result.response_path.read_text(encoding="utf-8")
            self.assertEqual(result.answer, "Hello world")
            self.assertEqual(chunks, ["Hello", " world"])
            self.assertIn("Routing request", statuses)
            self.assertIn("Waiting for first token", statuses)
            self.assertIn("Hello world", text)
            self.assertIn("## Timing", text)
            self.assertIn("✓ Routing", text)
            self.assertIn("✓ Retrieval", text)
            self.assertIn("✓ Generation", text)
            self.assertIn("Model load", text)


if __name__ == "__main__":
    unittest.main()
