from __future__ import annotations

import unittest

from pgpt.models.selector import select_model


AVAILABLE = {
    "qwen3:1.7b",
    "qwen2.5-coder:3b",
    "llama3.2:3b",
    "phi4-mini:latest",
}


class TestModelSelector(unittest.TestCase):
    """The first available preference wins; explicit overrides win over preferences."""

    def test_task_preferences(self) -> None:
        cases = {
            "general": "qwen3:1.7b",
            "research": "qwen3:1.7b",
            "explain-code": "qwen2.5-coder:3b",
            "debug": "qwen2.5-coder:3b",
            "implement": "qwen2.5-coder:3b",
            "architecture": "qwen2.5-coder:3b",
            "unknown-task": "qwen3:1.7b",
        }
        for task, expected in cases.items():
            with self.subTest(task=task):
                self.assertEqual(
                    select_model(task, available_models=AVAILABLE).model,
                    expected,
                )

    def test_fallback(self) -> None:
        self.assertEqual(
            select_model("general", available_models={"llama3.2:3b"}).model,
            "llama3.2:3b",
        )

    def test_explicit_override_resolves_latest_tag(self) -> None:
        self.assertEqual(
            select_model(
                "general",
                model_override="phi4-mini",
                available_models={"phi4-mini:latest"},
            ).model,
            "phi4-mini:latest",
        )

    def test_missing_override_fails(self) -> None:
        with self.assertRaises(RuntimeError):
            select_model(
                "general",
                model_override="missing-model",
                available_models=AVAILABLE,
            )


if __name__ == "__main__":
    unittest.main()
