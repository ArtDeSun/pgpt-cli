from __future__ import annotations

import json
import unittest
from pathlib import Path

from pgpt.config import CONFIG, expand


ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "evals" / "end_to_end_cases.json"


class TestEvalDatasetSelfContained(unittest.TestCase):
    def test_project_cases_use_repository_available_sources(self) -> None:
        cases = json.loads(CASES.read_text(encoding="utf-8"))
        for case in cases:
            project_name = case.get("expect", {}).get("project")
            if not project_name:
                continue
            with self.subTest(case=case["id"]):
                self.assertIn(project_name, CONFIG["projects"])
                source = expand(CONFIG["projects"][project_name]["source_dir"])
                self.assertTrue(source.exists(), source)


if __name__ == "__main__":
    unittest.main()
