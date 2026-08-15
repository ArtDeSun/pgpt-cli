import unittest

from pgpt.routing.router import resolve_route


def route(
    prompt: str,
    *,
    symbol_hit: bool = False,
    web_override: str | None = None,
    project_override: bool | None = None,
    template_override: str | None = None,
    model_override: str | None = None,
    deep_override: bool | None = None,
):
    return resolve_route(
        prompt,
        project_name="vibemaster",
        web_override=web_override,
        project_override=project_override,
        template_override=template_override,
        model_override=model_override,
        deep_override=deep_override,
        symbol_hit=symbol_hit,
    )


class TestRouting(unittest.TestCase):

    def test_general_stable_concept_routes_local(self):
        result = route(
            "Explain dependency injection."
        )

        self.assertEqual(
            result.execution,
            "local",
        )

        self.assertEqual(
            result.template,
            "general",
        )

    def test_code_explanation_routes_explain_code(self):
        result = route(
            "Explain how this TypeScript interface works."
        )

        self.assertEqual(
            result.execution,
            "local",
        )

        self.assertEqual(
            result.template,
            "explain-code",
        )

    def test_exact_project_symbol_routes_project(self):
        result = route(
            "Explain this function in my project.",
            symbol_hit=True,
        )

        self.assertEqual(
            result.execution,
            "project",
        )

        self.assertEqual(
            result.template,
            "explain-code",
        )

    def test_current_public_fact_routes_web_lookup(self):
        result = route(
            "What is the current stable release of this public software?"
        )

        self.assertEqual(
            result.execution,
            "web_lookup",
        )

        self.assertEqual(
            result.template,
            "web-lookup",
        )

    def test_explicit_web_lookup_override_wins(self):
        result = route(
            "Explain this public technology.",
            web_override="lookup",
        )

        self.assertEqual(
            result.execution,
            "web_lookup",
        )

        self.assertEqual(
            result.template,
            "web-lookup",
        )

    def test_explicit_web_research_override_wins(self):
        result = route(
            "Compare the available evidence.",
            web_override="research",
        )

        self.assertEqual(
            result.execution,
            "web_research",
        )

        self.assertEqual(
            result.template,
            "research-web",
        )

    def test_multi_source_current_research_routes_web_research(self):
        result = route(
            "Research the current approaches to this topic "
            "using multiple independent sources and compare "
            "their findings."
        )

        self.assertEqual(
            result.execution,
            "web_research",
        )

        self.assertEqual(
            result.template,
            "research-web",
        )

    def test_debug_task_routes_debug(self):
        result = route(
            "Diagnose why this traceback occurs and identify "
            "the smallest fix."
        )

        self.assertEqual(
            result.template,
            "debug",
        )

    def test_implementation_task_routes_implement(self):
        result = route(
            "Modify this function to add validation while "
            "preserving the existing behavior."
        )

        self.assertEqual(
            result.template,
            "implement",
        )

    def test_architecture_task_routes_architecture(self):
        result = route(
            "Design a staged migration across several "
            "repositories, databases, and cloud services while "
            "preserving APIs and minimizing downtime.",
            project_override=True,
        )

        self.assertEqual(
            result.execution,
            "project",
        )

        self.assertEqual(
            result.template,
            "architecture",
        )

    def test_project_override_wins(self):
        result = route(
            "Explain the architecture.",
            project_override=True,
        )

        self.assertEqual(
            result.execution,
            "project",
        )

    def test_project_off_prevents_project_route(self):
        result = route(
            "Explain this project architecture.",
            project_override=False,
        )

        self.assertNotEqual(
            result.execution,
            "project",
        )

    def test_web_off_prevents_web_route(self):
        result = route(
            "Look up the current public status.",
            web_override="off",
        )

        self.assertEqual(
            result.execution,
            "local",
        )

    def test_template_override_wins(self):
        result = route(
            "Explain this.",
            template_override="debug",
        )

        self.assertEqual(
            result.template,
            "debug",
        )

    def test_model_override_wins(self):
        result = route(
            "Explain this concept.",
            model_override="qwen2.5-coder:3b",
        )

        self.assertEqual(
            result.model,
            "qwen2.5-coder:3b",
        )

    def test_deep_override_wins(self):
        result = route(
            "Explain this concept.",
            deep_override=True,
        )

        self.assertTrue(
            result.deep
        )
    def test_explicit_online_lookup_routes_web(self):
        result = route(
            "Find someone's personal website online."
        )

        self.assertEqual(
            result.execution,
            "web_lookup",
        )

        self.assertEqual(
            result.template,
            "web-lookup",
        )


if __name__ == "__main__":
    unittest.main()