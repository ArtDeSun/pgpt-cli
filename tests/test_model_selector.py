from __future__ import annotations

import unittest

from pgpt.models.selector import select_model


AVAILABLE = {
    "qwen3:1.7b",
    "qwen2.5-coder:3b",
    "llama3.2:3b",
    "phi4-mini:latest",
}


class TestModelSelector(
    unittest.TestCase
):
    def test_general(
        self,
    ) -> None:
        result = select_model(
            "general",
            available_models=AVAILABLE,
        )

        self.assertEqual(
            result.model,
            "qwen3:1.7b",
        )

    def test_research(
        self,
    ) -> None:
        result = select_model(
            "research",
            available_models=AVAILABLE,
        )

        self.assertEqual(
            result.model,
            "qwen3:1.7b",
        )

    def test_explain_code(
        self,
    ) -> None:
        result = select_model(
            "explain-code",
            available_models=AVAILABLE,
        )

        self.assertEqual(
            result.model,
            "qwen2.5-coder:3b",
        )

    def test_debug(
        self,
    ) -> None:
        result = select_model(
            "debug",
            available_models=AVAILABLE,
        )

        self.assertEqual(
            result.model,
            "llama3.2:3b",
        )

    def test_implement(
        self,
    ) -> None:
        result = select_model(
            "implement",
            available_models=AVAILABLE,
        )

        self.assertEqual(
            result.model,
            "qwen2.5-coder:3b",
        )

    def test_architecture(
        self,
    ) -> None:
        result = select_model(
            "architecture",
            available_models=AVAILABLE,
        )

        self.assertEqual(
            result.model,
            "qwen2.5-coder:3b",
        )

    def test_fallback(
        self,
    ) -> None:
        result = select_model(
            "general",
            available_models={
                "llama3.2:3b",
            },
        )

        self.assertEqual(
            result.model,
            "llama3.2:3b",
        )

    def test_explicit_override(
        self,
    ) -> None:
        result = select_model(
            "general",
            model_override="phi4-mini",
            available_models={
                "phi4-mini:latest",
            },
        )

        self.assertEqual(
            result.model,
            "phi4-mini:latest",
        )

    def test_missing_override_fails(
        self,
    ) -> None:
        with self.assertRaises(
            RuntimeError
        ):
            select_model(
                "general",
                model_override="missing-model",
                available_models=AVAILABLE,
            )

    def test_unknown_task_uses_general_preferences(
        self,
    ) -> None:
        result = select_model(
            "unknown-task",
            available_models=AVAILABLE,
        )

        self.assertEqual(
            result.model,
            "qwen3:1.7b",
        )


if __name__ == "__main__":
    unittest.main()
