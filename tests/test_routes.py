from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from pgpt.routing.router import resolve_route
from pgpt.runtime.route import Route


def route(prompt: str, **overrides):
    return resolve_route(
        prompt,
        project_name="pgpt-cli",
        web_override=overrides.get("web_override"),
        project_override=overrides.get("project_override"),
        template_override=overrides.get("template_override"),
        model_override=None,
        deep_override=None,
        symbol_hit=overrides.get("symbol_hit", False),
    )


class TestRoutingPolicy(unittest.TestCase):
    def test_high_confidence_routes_skip_classifier(self) -> None:
        cases = [
            ("What's the weather in Toronto?", "web", "general"),
            ("What is the latest Node.js version?", "web", "general"),
            ("Diagnose this traceback.", "none", "debug"),
            ("Design a migration strategy.", "none", "architecture"),
            ("Write a Python function for this.", "none", "implement"),
            ("Summarize these recent notes.", "none", "general"),
        ]

        with patch("pgpt.routing.router.classify_web_need") as classifier:
            for prompt, source, task in cases:
                with self.subTest(prompt=prompt):
                    result = route(prompt)
                    self.assertEqual(result.source, source)
                    self.assertEqual(result.task, task)
            classifier.assert_not_called()

    def test_ambiguous_general_question_uses_one_web_decision(self) -> None:
        cases = [
            ("Who runs this organization?", "yes", "web", "current"),
            ("Who founded this organization?", "no", "none", "stable"),
        ]

        for prompt, web_need, source, freshness in cases:
            with self.subTest(prompt=prompt):
                with patch(
                    "pgpt.routing.router.classify_web_need",
                    return_value=web_need,
                ) as classifier:
                    result = route(prompt)
                classifier.assert_called_once_with(prompt)
                self.assertEqual(result.source, source)
                self.assertEqual(result.freshness, freshness)

    def test_project_context_wins_over_web_inference(self) -> None:
        with patch("pgpt.routing.router.classify_web_need") as classifier:
            result = route(
                "Review the current caching strategy in my project."
            )
        classifier.assert_not_called()
        self.assertEqual(result.source, "project")
        self.assertEqual(result.task, "architecture")
        self.assertEqual(result.freshness, "stable")

    def test_symbol_hit_uses_project_code(self) -> None:
        with patch("pgpt.routing.router.classify_web_need") as classifier:
            result = route("Explain select_model.", symbol_hit=True)
        classifier.assert_not_called()
        self.assertEqual(result.source, "project")
        self.assertEqual(result.task, "explain-code")

    def test_explicit_overrides_are_authoritative(self) -> None:
        self.assertEqual(
            route("Question", web_override="lookup").web_mode,
            "lookup",
        )
        self.assertEqual(
            route("Question", web_override="research").web_mode,
            "research",
        )
        self.assertEqual(
            route("Question", project_override=True).source,
            "project",
        )
        self.assertEqual(
            route("What's the weather?", web_override="off").source,
            "none",
        )


class TestRuntimeRoute(unittest.TestCase):
    def test_decision_maps_to_runtime(self) -> None:
        decision = route("What's the weather in Toronto?")
        selection = SimpleNamespace(model="model-a", reason="test")

        with patch("pgpt.runtime.route.select_model", return_value=selection):
            runtime = Route.from_decision(
                decision,
                project_name="pgpt-cli",
                template_override=None,
                model_override=None,
                deep_override=False,
            )

        self.assertEqual(runtime.execution, "web_lookup")
        self.assertEqual(runtime.template, "web-lookup")
        self.assertEqual(runtime.model, "model-a")


if __name__ == "__main__":
    unittest.main()
