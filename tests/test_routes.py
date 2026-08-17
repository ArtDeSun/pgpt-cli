from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from pgpt.routing.classifier import ClassifierDecision
from pgpt.routing.router import resolve_route
from pgpt.runtime.route import Route


def decision(
    prompt: str,
    *,
    symbol_hit: bool = False,
    web_override: str | None = None,
    project_override: bool | None = None,
    template_override: str | None = None,
) -> object:
    return resolve_route(
        prompt,
        project_name="pgpt-cli",
        web_override=web_override,
        project_override=project_override,
        template_override=template_override,
        model_override=None,
        deep_override=None,
        symbol_hit=symbol_hit,
    )


class TestRoutingDecision(unittest.TestCase):
    def test_high_confidence_current_surface_uses_fast_web_path(self) -> None:
        prompts = [
            "What's the weather in Toronto?",
            "What time is it in Tokyo?",
            "Is the CN Tower open now?",
            "What is the current score of the game?",
            "What is the current exchange rate?",
            "What is the latest stable version of Node.js?",
            "Who is currently the CEO of Microsoft?",
            "Who won the most recent NBA championship?",
            "What is the current price of Bitcoin?",
            "What happened in the markets today?",
            "Is this service still operating?",
            "Has Python 3.14 been released?",
            "What's the latest on the EU AI regulation?",
            "What is the flight status of AC123?",
            "Is example.com down right now?",
            "Who heads Microsoft?",
            "Who is the CEO of Microsoft?",
            "Who runs OpenAI?",
            "Who is the prime minister of Canada?",
            "Who coaches the Toronto Raptors?",
        ]
        with patch("pgpt.routing.router.classify_route_semantics") as classifier:
            for prompt in prompts:
                with self.subTest(prompt=prompt):
                    result = decision(prompt)
                    self.assertEqual(result.source, "web")
                    self.assertEqual(result.web_mode, "lookup")
                    self.assertEqual(result.freshness, "current")
        classifier.assert_not_called()

    def test_semantic_current_fallback_routes_web(self) -> None:
        semantic = ClassifierDecision(
            task="general",
            freshness="current",
            complexity="simple",
        )
        with patch(
            "pgpt.routing.router.classify_route_semantics",
            return_value=semantic,
        ) as classifier:
            result = decision("Who leads ExampleCorp?")
        classifier.assert_called_once()
        self.assertEqual(result.source, "web")
        self.assertEqual(result.web_mode, "lookup")
        self.assertEqual(result.freshness, "current")
        self.assertIn("semantic classifier marked freshness as current", result.reason)

    def test_temporal_words_do_not_automatically_force_web(self) -> None:
        prompts = [
            "Explain electrical current in a wire.",
            "Rewrite this paragraph to sound more current.",
            "Write a poem about tonight.",
            "I exercised yesterday; explain delayed-onset muscle soreness.",
            "Summarize these recent notes.",
            "Explain the current design pattern.",
        ]
        semantic = ClassifierDecision(
            task="general",
            freshness="stable",
            complexity="simple",
        )
        with patch(
            "pgpt.routing.router.classify_route_semantics",
            return_value=semantic,
        ):
            for prompt in prompts:
                with self.subTest(prompt=prompt):
                    result = decision(prompt)
                    self.assertEqual(result.source, "none")
                    self.assertIsNone(result.web_mode)
                    self.assertEqual(result.freshness, "stable")

    def test_historical_or_conceptual_role_questions_do_not_force_web(self) -> None:
        prompts = [
            "Who was the CEO of Microsoft in 2010?",
            "Who founded Microsoft?",
            "Explain what a CEO does.",
            "Who leads the request lifecycle in this framework?",
        ]
        semantic = ClassifierDecision(
            task="general",
            freshness="stable",
            complexity="simple",
        )
        with patch(
            "pgpt.routing.router.classify_route_semantics",
            return_value=semantic,
        ) as classifier:
            for prompt in prompts:
                with self.subTest(prompt=prompt):
                    result = decision(prompt)
                    self.assertEqual(result.source, "none")
                    self.assertIsNone(result.web_mode)
                    self.assertEqual(result.freshness, "stable")
        self.assertEqual(classifier.call_count, len(prompts))

    def test_multi_source_research(self) -> None:
        result = decision(
            "Research current AI privacy approaches using multiple independent sources."
        )
        self.assertEqual(result.source, "web")
        self.assertEqual(result.web_mode, "research")
        self.assertEqual(result.task, "research")

    def test_debug_fast_path(self) -> None:
        result = decision(
            "Why does this traceback fail and what is the smallest fix?"
        )
        self.assertEqual(result.task, "debug")
        self.assertEqual(result.source, "none")

    def test_architecture_fast_path(self) -> None:
        result = decision(
            "Design a staged migration from a monolith to workers."
        )
        self.assertEqual(result.task, "architecture")

    def test_project_symbol_routes_project(self) -> None:
        semantic = ClassifierDecision(
            task="general",
            freshness="stable",
            complexity="standard",
        )
        with patch(
            "pgpt.routing.router.classify_route_semantics",
            return_value=semantic,
        ):
            result = decision(
                "Explain select_model in my project.",
                symbol_hit=True,
            )
        self.assertEqual(result.source, "project")
        self.assertEqual(result.task, "explain-code")
        self.assertTrue(result.project_evidence)

    def test_web_off_suppresses_fast_current_web(self) -> None:
        result = decision(
            "Who heads Microsoft?",
            web_override="off",
        )
        self.assertEqual(result.source, "none")
        self.assertIsNone(result.web_mode)
        self.assertEqual(result.freshness, "current")

    def test_web_off_suppresses_semantic_current_web(self) -> None:
        semantic = ClassifierDecision(
            task="general",
            freshness="current",
            complexity="simple",
        )
        with patch(
            "pgpt.routing.router.classify_route_semantics",
            return_value=semantic,
        ):
            result = decision(
                "Who leads ExampleCorp?",
                web_override="off",
            )
        self.assertEqual(result.source, "none")
        self.assertIsNone(result.web_mode)
        self.assertEqual(result.freshness, "current")

    def test_project_off_suppresses_project(self) -> None:
        semantic = ClassifierDecision(
            task="general",
            freshness="stable",
            complexity="standard",
        )
        with patch(
            "pgpt.routing.router.classify_route_semantics",
            return_value=semantic,
        ):
            result = decision(
                "Explain this project.",
                project_override=False,
            )
        self.assertEqual(result.source, "none")

    def test_classifier_fallback_for_general(self) -> None:
        semantic = ClassifierDecision(
            task="general",
            freshness="stable",
            complexity="simple",
        )
        with patch(
            "pgpt.routing.router.classify_route_semantics",
            return_value=semantic,
        ) as classifier:
            result = decision("What is dependency injection?")
        classifier.assert_called_once()
        self.assertEqual(result.source, "none")
        self.assertEqual(result.task, "general")
        self.assertEqual(result.freshness, "stable")

    def test_explicit_overrides(self) -> None:
        semantic = ClassifierDecision(
            task="general",
            freshness="stable",
            complexity="simple",
        )
        with patch(
            "pgpt.routing.router.classify_route_semantics",
            return_value=semantic,
        ):
            project = decision(
                "Explain this.",
                project_override=True,
            )
            lookup = decision(
                "Explain this.",
                web_override="lookup",
            )
            research = decision(
                "Explain this.",
                web_override="research",
            )
            template = decision(
                "Explain this.",
                template_override="debug",
            )
        self.assertEqual(project.source, "project")
        self.assertEqual(lookup.web_mode, "lookup")
        self.assertEqual(research.web_mode, "research")
        self.assertEqual(template.task, "debug")


class TestRuntimeRoute(unittest.TestCase):
    def test_runtime_route_maps_decision(self) -> None:
        selection = SimpleNamespace(
            model="model-a",
            reason="test selection",
        )
        routing = resolve_route(
            "Who heads Microsoft?",
            project_name="pgpt-cli",
            web_override=None,
            project_override=None,
            template_override=None,
            model_override=None,
            deep_override=None,
            symbol_hit=False,
        )
        with patch(
            "pgpt.runtime.route.select_model",
            return_value=selection,
        ):
            route = Route.from_decision(
                routing,
                project_name="pgpt-cli",
                template_override=None,
                model_override=None,
                deep_override=True,
            )
        self.assertEqual(route.execution, "web_lookup")
        self.assertEqual(route.template, "web-lookup")
        self.assertEqual(route.model, "model-a")
        self.assertTrue(route.deep)

    def test_project_runtime_route(self) -> None:
        selection = SimpleNamespace(
            model="coder",
            reason="test selection",
        )
        routing = resolve_route(
            "Explain this project architecture.",
            project_name="pgpt-cli",
            web_override=None,
            project_override=True,
            template_override=None,
            model_override=None,
            deep_override=None,
            symbol_hit=False,
        )
        with patch(
            "pgpt.runtime.route.select_model",
            return_value=selection,
        ):
            route = Route.from_decision(
                routing,
                project_name="pgpt-cli",
                template_override=None,
                model_override=None,
                deep_override=None,
            )
        self.assertEqual(route.execution, "project")
        self.assertEqual(route.project, "pgpt-cli")


if __name__ == "__main__":
    unittest.main()
