from __future__ import annotations

import unittest
from unittest.mock import patch

from tools import run_end_to_end_evals as e2e
from tools import run_reliability_evals as reliability


CASE_PROJECT = {
    "id": "p",
    "prompt": "Explain select_model.",
    "expect": {"project": "pgpt-cli-history"},
}
CASE_LOCAL = {
    "id": "l",
    "prompt": "Explain dependency injection.",
    "expect": {"project": None},
}


class TestEvalProjectSelection(unittest.TestCase):
    def test_project_case_uses_expected_project(self) -> None:
        self.assertEqual(e2e._case_project(CASE_PROJECT), "pgpt-cli-history")
        self.assertEqual(reliability._case_project(CASE_PROJECT), "pgpt-cli-history")

    def test_override_wins(self) -> None:
        self.assertEqual(e2e._case_project(CASE_PROJECT, "custom"), "custom")
        self.assertEqual(reliability._case_project(CASE_PROJECT, "custom"), "custom")

    def test_local_case_uses_config_default(self) -> None:
        self.assertEqual(e2e._case_project(CASE_LOCAL), "pgpt-cli")
        self.assertEqual(reliability._case_project(CASE_LOCAL), "pgpt-cli")

    def test_project_evidence_is_built_from_expected_project(self) -> None:
        with patch.object(e2e, "build_project_context", return_value=("ctx", ["a.py"])) as build:
            evidence = e2e._evaluation_evidence(CASE_PROJECT)
        build.assert_called_once_with("Explain select_model.", "pgpt-cli-history")
        self.assertEqual(evidence, {"project": "pgpt-cli-history", "files": ["a.py"], "context": "ctx"})

    def test_no_evidence_for_non_project_case(self) -> None:
        self.assertIsNone(e2e._evaluation_evidence(CASE_LOCAL))
        self.assertIsNone(reliability._evaluation_evidence(CASE_LOCAL))


if __name__ == "__main__":
    unittest.main()
