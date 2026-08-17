from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "web" / "index.html"


class TestWebUI(unittest.TestCase):
    def test_ui_is_self_contained_and_uses_local_api(self) -> None:
        text = INDEX.read_text(encoding="utf-8")
        self.assertIn("/v1/chat/completions", text)
        self.assertIn("/api/meta", text)
        self.assertIn('id="project"', text)
        self.assertIn('id="skill"', text)
        self.assertNotIn("<script src=", text)
        self.assertNotIn("<link rel=", text)


if __name__ == "__main__":
    unittest.main()
