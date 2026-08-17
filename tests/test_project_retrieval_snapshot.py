from __future__ import annotations

import unittest

from pgpt.retrieval.project import build_context


class TestHistoricalProjectRetrieval(unittest.TestCase):
    def test_historical_project_retrieves_select_model_source(self) -> None:
        context, files = build_context(
            "Explain how select_model works in the historical pgpt-cli project.",
            "pgpt-cli-history",
        )
        self.assertIn("pgpt/models/selector.py", files)
        self.assertIn("def select_model(", context)
        self.assertIn("model_override", context)


if __name__ == "__main__":
    unittest.main()
