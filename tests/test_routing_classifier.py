from __future__ import annotations

import unittest
from unittest.mock import patch

from pgpt.routing import classifier


class TestRoutingClassifier(unittest.TestCase):
    def test_schema_uses_generic_time_scope(self) -> None:
        properties = classifier._ROUTE_SCHEMA["properties"]
        self.assertIn("time_scope", properties)
        self.assertNotIn("freshness", properties)
        self.assertEqual(
            properties["time_scope"]["enum"],
            ["moving", "fixed", "unknown"],
        )

    def test_moving_scope_maps_to_current(self) -> None:
        with patch.object(
            classifier,
            "_chat_classifier",
            return_value={
                "task": "general",
                "time_scope": "moving",
                "complexity": "simple",
            },
        ):
            result = classifier.classify_route_semantics(
                "Who runs this organization?"
            )
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.freshness, "current")

    def test_fixed_scope_maps_to_stable(self) -> None:
        with patch.object(
            classifier,
            "_chat_classifier",
            return_value={
                "task": "general",
                "time_scope": "fixed",
                "complexity": "simple",
            },
        ):
            result = classifier.classify_route_semantics(
                "Who ran this organization in 2010?"
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
                "complexity": "standard",
            },
        ):
            result = classifier.classify_route_semantics(
                "What about the other one?"
            )
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.freshness, "unknown")

    def test_invalid_scope_is_rejected(self) -> None:
        with patch.object(
            classifier,
            "_chat_classifier",
            return_value={
                "task": "general",
                "time_scope": "recentish",
                "complexity": "simple",
            },
        ):
            result = classifier.classify_route_semantics("Question")
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
