from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROMPTS = ROOT / "prompts"
CLASSIFIER = ROOT / "pgpt" / "routing" / "classifier.py"
SCORER = ROOT / "tools" / "score_end_to_end_results.py"


class TestPromptOwnership(unittest.TestCase):
    def test_language_instructions_live_in_prompt_files(self) -> None:
        self.assertTrue((PROMPTS / "routing" / "web-need.md").is_file())
        self.assertTrue((PROMPTS / "quality" / "required-criterion.md").is_file())
        self.assertTrue((PROMPTS / "quality" / "forbidden-criterion.md").is_file())

        classifier = CLASSIFIER.read_text(encoding="utf-8")
        scorer = SCORER.read_text(encoding="utf-8")
        self.assertNotIn("current public information", classifier)
        self.assertNotIn("evaluate exactly one required criterion", scorer.casefold())

    def test_prompt_files_stay_short(self) -> None:
        for path in PROMPTS.rglob("*.md"):
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertLessEqual(
                    len(path.read_text(encoding="utf-8")),
                    1800,
                )


if __name__ == "__main__":
    unittest.main()
