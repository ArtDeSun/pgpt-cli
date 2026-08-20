from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from pgpt.routing.router import resolve_route
from pgpt.runtime.route import Route


def route(prompt: str, **overrides):
    return resolve_route(
        prompt,
        project_name=overrides.get("project_name", "pgpt-cli"),
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
            ("Has Python 3.14 been released?", "web", "general"),
            ("Compare the current AWS services for containers.", "web", "architecture"),
            ("Look up this npm error on the web and explain the likely cause.", "web", "debug"),
            ("Diagnose this traceback.", "none", "debug"),
            ("Design a staged migration to worker services.", "none", "architecture"),
            ("Write a Python function for this.", "none", "implement"),
            ("Summarize these recent notes.", "none", "general"),
        ]

        with patch("pgpt.routing.router.classify_web_need") as classifier:
            for prompt, source, task in cases:
                with self.subTest(prompt=prompt):
                    result = route(prompt)
                    self.assertEqual((result.source, result.task), (source, task))
            classifier.assert_not_called()

    def test_ambiguous_general_questions_use_one_web_decision(self) -> None:
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
                self.assertEqual((result.source, result.freshness), (source, freshness))

    def test_keywords_alone_do_not_define_task(self) -> None:
        cases = [
            "What does research mean?",
            "Explain how to add two numbers.",
            "What is a TypeError?",
            "Explain error handling in Python.",
            "What is software architecture?",
        ]
        with patch("pgpt.routing.router.classify_web_need", return_value="no"):
            for prompt in cases:
                with self.subTest(prompt=prompt):
                    self.assertEqual(route(prompt).task, "general")

    def test_project_context_wins_over_web_inference(self) -> None:
        with patch("pgpt.routing.router.classify_web_need") as classifier:
            result = route("Review the current caching strategy in my project.")
        classifier.assert_not_called()
        self.assertEqual(
            (result.source, result.task, result.freshness),
            ("project", "architecture", "stable"),
        )

    def test_named_project_counts_as_project_evidence(self) -> None:
        with patch("pgpt.routing.router.classify_web_need") as classifier:
            explain = route("Explain routing in pgpt-cli.")
            architecture = route("Review the pgpt-cli architecture.")
        classifier.assert_not_called()
        self.assertEqual((explain.source, explain.task), ("project", "explain-code"))
        self.assertEqual((architecture.source, architecture.task), ("project", "architecture"))

    def test_explicit_current_web_writing_keeps_current_freshness(self) -> None:
        with patch("pgpt.routing.router.classify_web_need") as classifier:
            result = route("Search the web for the latest release notes and summarize them.")
        classifier.assert_not_called()
        self.assertEqual(
            (result.source, result.web_mode, result.task, result.freshness),
            ("web", "lookup", "general", "current"),
        )

    def test_symbol_intent_distinguishes_read_from_change(self) -> None:
        with patch("pgpt.routing.router.classify_web_need") as classifier:
            explain = route("Explain select_model.", symbol_hit=True)
            change = route(
                "Modify prepareLandscapeVideo so it rejects empty titles.",
                symbol_hit=True,
            )
        classifier.assert_not_called()
        self.assertEqual((explain.source, explain.task), ("project", "explain-code"))
        self.assertEqual((change.source, change.task), ("project", "implement"))

    def test_explicit_overrides_are_authoritative(self) -> None:
        self.assertEqual(route("Question", web_override="lookup").web_mode, "lookup")
        self.assertEqual(route("Question", web_override="research").web_mode, "research")
        self.assertEqual(route("Question", project_override=True).source, "project")
        self.assertEqual(route("What's the weather?", web_override="off").source, "none")


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

        self.assertEqual(
            (runtime.execution, runtime.template, runtime.model),
            ("web_lookup", "web-lookup", "model-a"),
        )


if __name__ == "__main__":
    unittest.main()
