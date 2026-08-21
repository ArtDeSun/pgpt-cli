from __future__ import annotations
import unittest
from datetime import datetime
from unittest.mock import patch
from pgpt.routing.router import resolve_route
def route(prompt,**kw): return resolve_route(prompt,project_name='pgpt-cli',web_override=kw.get('web_override'),project_override=kw.get('project_override'),template_override=None,model_override=None,deep_override=None,symbol_hit=kw.get('symbol_hit',False))
class TestReleaseRouting(unittest.TestCase):
    def test_current_year_nba_uses_web(self):
        with patch('pgpt.routing.router.classify_web_need') as c: value=route(f'Who won the {datetime.now().year} NBA championship?')
        c.assert_not_called(); self.assertEqual((value.source,value.web_mode,value.task),('web','lookup','general'))
    def test_symbol_hit_cannot_hijack_public_question(self):
        with patch('pgpt.routing.router.classify_web_need') as c: value=route(f'Who won the {datetime.now().year} NBA championship?',symbol_hit=True)
        c.assert_not_called(); self.assertEqual(value.source,'web'); self.assertFalse(value.project_evidence)
    def test_own_source_code_is_project(self):
        with patch('pgpt.routing.router.classify_web_need') as c: value=route('Explain your own source code and routing.')
        c.assert_not_called(); self.assertEqual((value.source,value.task),('project','explain-code'))
if __name__=='__main__': unittest.main()
