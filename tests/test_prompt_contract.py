from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROMPTS = ROOT / "prompts"


class TestPromptContract(unittest.TestCase):
    def read(self, name: str) -> str:
        return (PROMPTS / name).read_text(encoding="utf-8").casefold()

    def test_system_prompt_is_direct_grounded_and_chat_like(self) -> None:
        text = self.read("system.md")
        self.assertIn("answer directly", text)
        self.assertIn("do not invent", text)
        self.assertIn("evidence", text)
        self.assertIn("next ideas", text)

    def test_debug_and_implementation_prompts_prefer_targeted_changes(self) -> None:
        debug = self.read("debug.md")
        implement = self.read("implement.md")
        self.assertIn("root cause", debug)
        self.assertIn("smallest targeted fix", debug)
        self.assertIn("smallest coherent change", implement)
        self.assertIn("verification", implement)

    def test_web_prompts_require_grounding_and_inline_sources(self) -> None:
        for name in ("web-lookup.md", "research-web.md"):
            with self.subTest(name=name):
                text = self.read(name)
                self.assertIn("[s1]", text)
                self.assertIn("evidence", text)
                self.assertIn("invent", text)

    def test_code_explanation_stays_on_retrieved_code(self) -> None:
        text = self.read("explain-code.md")
        self.assertIn("supplied or retrieved code", text)
        self.assertIn("do not redesign", text)


if __name__ == "__main__": unittest.main()
