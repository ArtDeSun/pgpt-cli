from __future__ import annotations

import os
import unittest

from pgpt.routing.classifier import classify_web_need


@unittest.skipUnless(
    os.environ.get("PGPT_RUN_LOCAL_MODEL_TESTS") == "1",
    "requires local Ollama router model",
)
class TestRouterAcceptanceLocal(unittest.TestCase):
    def test_current_public_role_needs_web(self) -> None:
        self.assertEqual(
            classify_web_need("Who is the current CEO of OpenAI?"),
            "yes",
        )

    def test_fixed_historical_fact_does_not_need_web(self) -> None:
        self.assertEqual(
            classify_web_need("Who created the Python programming language?"),
            "no",
        )


if __name__ == "__main__":
    unittest.main()
