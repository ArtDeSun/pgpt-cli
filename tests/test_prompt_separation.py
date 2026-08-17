from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCORER = ROOT / "tools" / "score_end_to_end_results.py"
CLASSIFIER = ROOT / "pgpt" / "routing" / "classifier.py"


class TestPromptSeparation(unittest.TestCase):
    def test_quality_instructions_live_in_prompt_files(self) -> None:
        scorer = SCORER.read_text(encoding="utf-8")
        self.assertNotIn("You evaluate exactly one required criterion", scorer)
        self.assertNotIn("You evaluate exactly one forbidden criterion", scorer)
        self.assertTrue((ROOT / "prompts" / "quality" / "required-criterion.md").is_file())
        self.assertTrue((ROOT / "prompts" / "quality" / "forbidden-criterion.md").is_file())

    def test_combined_route_instructions_live_in_prompt_file(self) -> None:
        classifier = CLASSIFIER.read_text(encoding="utf-8")
        prompt_path = ROOT / "prompts" / "routing" / "classifiers" / "route.md"
        self.assertTrue(prompt_path.is_file())
        prompt = prompt_path.read_text(encoding="utf-8")
        self.assertIn("Route Semantics Classifier", prompt)
        self.assertNotIn("Classify only the meaning of the user's request", classifier)
        self.assertIn('classifier_name="route"', classifier)


if __name__ == "__main__":
    unittest.main()
