from __future__ import annotations

import unittest
from unittest.mock import patch

from pgpt import config, server
from pgpt.retrieval import project
from pgpt.routing.router import resolve_route
from pgpt.runtime import pipeline


class TestProjectRegistryRouting(unittest.TestCase):
    def test_user_registry_is_separate_from_internal_projects(self) -> None:
        with patch.object(
            config,
            "_load_user_projects",
            return_value={"notes": {"source_dir": "/tmp/notes"}},
        ):
            self.assertEqual(config.user_project_names(), ["notes"])
            self.assertIn("pgpt-cli", config.project_names(include_hidden=True))
            self.assertNotIn("pgpt-cli", config.user_project_names())

    def test_explicit_registered_name_wins_without_symbol_scan(self) -> None:
        with (
            patch.object(project, "user_project_names", return_value=["alpha", "beta"]),
            patch.object(project, "has_symbol_hit") as symbol,
        ):
            self.assertEqual(project.select_user_project("Explain beta please"), "beta")
        symbol.assert_not_called()

    def test_unique_symbol_match_selects_one_registered_context(self) -> None:
        with (
            patch.object(project, "user_project_names", return_value=["alpha", "beta"]),
            patch.object(project, "candidate_identifiers", return_value=["renderCard"]),
            patch.object(
                project,
                "has_symbol_hit",
                side_effect=lambda _prompt, name: name == "beta",
            ),
        ):
            self.assertEqual(project.select_user_project("Explain renderCard"), "beta")

    def test_ambiguous_symbol_match_selects_nothing(self) -> None:
        with (
            patch.object(project, "user_project_names", return_value=["alpha", "beta"]),
            patch.object(project, "candidate_identifiers", return_value=["renderCard"]),
            patch.object(project, "has_symbol_hit", return_value=True),
        ):
            self.assertIsNone(project.select_user_project("Explain renderCard"))

    def test_generic_my_project_uses_only_context_when_unique(self) -> None:
        with (
            patch.object(project, "user_project_names", return_value=["notes"]),
            patch.object(project, "candidate_identifiers", return_value=[]),
        ):
            self.assertEqual(project.select_user_project("Explain my project"), "notes")

    def test_generic_my_project_is_not_assigned_when_multiple_contexts_exist(self) -> None:
        with (
            patch.object(project, "user_project_names", return_value=["alpha", "beta"]),
            patch.object(project, "candidate_identifiers", return_value=[]),
        ):
            self.assertIsNone(project.select_user_project("Explain my project"))

    def test_router_cannot_create_project_route_without_selected_source(self) -> None:
        decision = resolve_route(
            "Explain my project",
            project_name="",
            web_override="off",
            project_override=None,
            template_override=None,
            model_override=None,
            deep_override=None,
            symbol_hit=False,
        )
        self.assertEqual(decision.source, "none")
        self.assertFalse(decision.project_evidence)

    def test_browser_auto_ignores_visible_dropdown_project(self) -> None:
        request = server._prepare_request(
            {
                "messages": [{"role": "user", "content": "Hello"}],
                "pgpt": {"project": "notes", "context": None},
            }
        )
        self.assertIsNone(request.project)
        self.assertIsNone(request.context)

    def test_browser_force_project_keeps_selected_project(self) -> None:
        request = server._prepare_request(
            {
                "messages": [{"role": "user", "content": "Hello"}],
                "pgpt": {"project": "notes", "context": True},
            }
        )
        self.assertEqual(request.project, "notes")
        self.assertTrue(request.context)

    def test_browser_force_project_requires_selection(self) -> None:
        with self.assertRaisesRegex(ValueError, "requires a selected project"):
            server._prepare_request(
                {
                    "messages": [{"role": "user", "content": "Hello"}],
                    "pgpt": {"context": True},
                }
            )

    def test_pipeline_auto_uses_selector_not_internal_default(self) -> None:
        with patch.object(pipeline, "select_user_project", return_value="notes") as select:
            self.assertEqual(
                pipeline._resolve_project("Explain renderCard", None, None), "notes"
            )
        select.assert_called_once_with("Explain renderCard")

    def test_pipeline_context_off_skips_auto_selection(self) -> None:
        with patch.object(pipeline, "select_user_project") as select:
            self.assertIsNone(
                pipeline._resolve_project("Explain renderCard", None, False)
            )
        select.assert_not_called()


if __name__ == "__main__":
    unittest.main()
