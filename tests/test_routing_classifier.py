from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from pgpt.routing import classifier


class TestRoutingClassifier(unittest.TestCase):
    def test_schema_uses_only_task_and_generic_time_scope(self) -> None:
        properties = classifier._ROUTE_SCHEMA["properties"]
        self.assertIn("task", properties)
        self.assertIn("time_scope", properties)
        self.assertNotIn("freshness", properties)
        self.assertNotIn("complexity", properties)
        self.assertEqual(
            properties["time_scope"]["enum"],
            ["moving", "fixed", "unknown"],
        )
        self.assertEqual(
            classifier._ROUTE_SCHEMA["required"],
            ["task", "time_scope"],
        )

    def test_router_model_can_be_overridden_for_local_acceptance(self) -> None:
        with patch.dict(
            os.environ,
            {"PGPT_ROUTER_MODEL": "candidate-router"},
        ):
            self.assertEqual(
                classifier.router_model(),
                "candidate-router",
            )

    def test_chat_classifier_uses_router_runtime_settings(self) -> None:
        with patch.object(
            classifier,
            "router_model",
            return_value="router-test",
        ), patch.object(
            classifier,
            "_router_num_ctx",
            return_value=4096,
        ), patch.object(
            classifier,
            "json_request",
            return_value={
                "message": {
                    "content": '{"task":"general","time_scope":"fixed"}'
                }
            },
        ) as request:
            result = classifier._chat_classifier(
                prompt="Question",
                classifier_name="route",
                schema=classifier._ROUTE_SCHEMA,
            )

        self.assertIsNotNone(result)
        payload = request.call_args.kwargs["payload"]
        self.assertEqual(payload["model"], "router-test")
        self.assertEqual(payload["options"]["num_ctx"], 4096)
        self.assertEqual(
            payload["keep_alive"],
            classifier.CONFIG["performance"]["router_keep_alive"],
        )

    def test_moving_scope_maps_to_current(self) -> None:
        with patch.object(
            classifier,
            "_chat_classifier",
            return_value={
                "task": "general",
                "time_scope": "moving",
            },
        ):
            result = classifier.classify_route_semantics(
                "Question"
            )
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.freshness, "current")
        self.assertEqual(result.complexity, "simple")

    def test_fixed_scope_maps_to_stable(self) -> None:
        with patch.object(
            classifier,
            "_chat_classifier",
            return_value={
                "task": "general",
                "time_scope": "fixed",
            },
        ):
            result = classifier.classify_route_semantics(
                "Question"
            )
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.freshness, "stable")

    def test_unknown_scope_maps_to_unknown(self) -> None:
        with patch.object(
            classifier,
            "_chat_classifier",
            return_value={
                "task": "general",
                "time_scope": "unknown",
            },
        ):
            result = classifier.classify_route_semantics(
                "Question"
            )
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.freshness, "unknown")

    def test_complexity_is_derived_from_task_not_model_output(self) -> None:
        cases = {
            "general": "simple",
            "explain-code": "standard",
            "debug": "standard",
            "implement": "standard",
            "architecture": "complex",
            "research": "complex",
        }

        for task, expected in cases.items():
            with self.subTest(task=task):
                with patch.object(
                    classifier,
                    "_chat_classifier",
                    return_value={
                        "task": task,
                        "time_scope": "fixed",
                    },
                ):
                    result = classifier.classify_route_semantics(
                        "Question"
                    )
                self.assertIsNotNone(result)
                assert result is not None
                self.assertEqual(result.complexity, expected)

    def test_invalid_scope_is_rejected(self) -> None:
        with patch.object(
            classifier,
            "_chat_classifier",
            return_value={
                "task": "general",
                "time_scope": "recentish",
            },
        ):
            result = classifier.classify_route_semantics("Question")
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
