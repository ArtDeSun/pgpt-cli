from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from pgpt.routing import classifier


class TestWebNeedClassifier(unittest.TestCase):
    def test_schema_has_one_decision(self) -> None:
        self.assertEqual(
            classifier._WEB_NEED_SCHEMA["required"],
            ["needs_web"],
        )
        self.assertEqual(
            classifier._WEB_NEED_SCHEMA["properties"]["needs_web"]["enum"],
            ["yes", "no", "unknown"],
        )

    def test_valid_results_are_returned(self) -> None:
        for value in ("yes", "no", "unknown"):
            with self.subTest(value=value):
                response = {
                    "message": {
                        "content": json.dumps({"needs_web": value})
                    }
                }
                with patch.object(classifier, "json_request", return_value=response):
                    self.assertEqual(
                        classifier.classify_web_need("Question"),
                        value,
                    )

    def test_bad_model_output_is_unknown(self) -> None:
        with patch.object(
            classifier,
            "json_request",
            return_value={"message": {"content": "not json"}},
        ):
            self.assertEqual(
                classifier.classify_web_need("Question"),
                "unknown",
            )


if __name__ == "__main__":
    unittest.main()
