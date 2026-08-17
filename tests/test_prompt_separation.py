from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCORER = ROOT / "tools" / "score_end_to_end_results.py"


class TestPromptSeparation(unittest.TestCase):
    def test_quality_instructions_live_in_prompt_files(self) -> None:
        scorer = SCORER.read_text(encoding="utf-8")
        self.assertNotIn("You evaluate exactly one required criterion", scorer)
        self.assertNotIn("You evaluate exactly one forbidden criterion", scorer)
        self.assertTrue(
            (ROOT / "prompts" / "quality" / "required-criterion.md").is_file()
        )
        self.assertTrue(
            (ROOT / "prompts" / "quality" / "forbidden-criterion.md").is_file()
        )


if __name__ == "__main__":
    unittest.main()
