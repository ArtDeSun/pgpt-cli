from __future__ import annotations

import unittest

import pgpt.runtime.pipeline as pipeline


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
    }


class TestPipeline(unittest.TestCase):

    def test_streamed_markdown_and_timing(self):
        original = pipeline.stream_chat
        pipeline.stream_chat = fake_stream_chat

        result = None

        try:
            result = pipeline.run(
                "What is dependency injection?",
                echo_route=False,
            )

            text = result.response_path.read_text(encoding="utf-8")

            self.assertIn("Hello world", text)
            self.assertIn("## Timing", text)
            self.assertIn("✓ Routing", text)
            self.assertIn("✓ Retrieval", text)
            self.assertIn("✓ Generation", text)
            self.assertIn("Model load", text)

        finally:
            pipeline.stream_chat = original

            if result is not None:
                result.response_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()