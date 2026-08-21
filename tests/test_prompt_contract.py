from __future__ import annotations
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; PROMPTS=ROOT/'prompts'
class TestPromptContract(unittest.TestCase):
    def read(self,name): return (PROMPTS/name).read_text(encoding='utf-8').casefold()
    def test_system_identity_and_grounding(self):
        text=self.read('system.md'); self.assertIn('pgpt-cli',text); self.assertIn('ollama',text); self.assertIn('evidence',text); self.assertIn('never claim',text); self.assertNotIn('next ideas',text)
    def test_debug_and_implementation_are_targeted(self):
        self.assertIn('root cause',self.read('debug.md')); self.assertIn('smallest targeted fix',self.read('debug.md')); self.assertIn('smallest coherent change',self.read('implement.md'))
    def test_web_prompts_require_sources(self):
        for name in ('web-lookup.md','research-web.md'):
            text=self.read(name); self.assertIn('[s1]',text); self.assertIn('evidence',text); self.assertIn('invent',text)
    def test_code_explanation_stays_grounded(self): self.assertIn('supplied or retrieved code',self.read('explain-code.md'))
if __name__=='__main__': unittest.main()
