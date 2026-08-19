from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROMPTS = ROOT / "prompts"
SKILLS = ROOT / "skills"
CLASSIFIER = ROOT / "pgpt" / "routing" / "classifier.py"
SCORER = ROOT / "tools" / "score_end_to_end_results.py"
BENCHMARK = ROOT / "tools" / "benchmark_models.py"


class TestPromptOwnership(unittest.TestCase):
    def test_model_instructions_live_in_markdown(self) -> None:
        required = [
            PROMPTS / "routing" / "web-need.md",
            PROMPTS / "quality" / "required-criterion.md",
            PROMPTS / "quality" / "forbidden-criterion.md",
            PROMPTS / "benchmark.md",
        ]
        for path in required:
            self.assertTrue(path.is_file(), path)

        self.assertNotIn(
            "current public information",
            CLASSIFIER.read_text(encoding="utf-8"),
        )
        self.assertNotIn(
            "evaluate exactly one required criterion",
            SCORER.read_text(encoding="utf-8").casefold(),
        )
        self.assertNotIn(
            "answer the user's request accurately and directly",
            BENCHMARK.read_text(encoding="utf-8").casefold(),
        )

    def test_instruction_files_stay_short(self) -> None:
        files = [*PROMPTS.rglob("*.md"), *SKILLS.glob("*.md")]
        for path in files:
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertLessEqual(
                    len(path.read_text(encoding="utf-8")),
                    1800,
                )


if __name__ == "__main__":
    unittest.main()
