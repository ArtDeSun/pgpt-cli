from __future__ import annotations
import tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import pgpt.runtime.pipeline as pipeline
from pgpt.routing.types import RoutingDecision
from pgpt.runtime.route import Route
class TestPipelineControls(unittest.TestCase):
    def test_answer_length_override(self):
        route=type('R',(),{'template':'general','deep':False})()
        with patch.dict(pipeline.CONFIG,{'performance':{'answer_lengths':{'long':2000},'max_tokens_by_template':{'general':1000},'num_ctx_by_role':{'general':4096}},'models':{'coder_templates':[]}},clear=False): self.assertEqual(pipeline._generation_settings(route,'long'),(2000,4096))
    def test_continuation_instruction_is_hidden(self):
        instruction=pipeline._load_runtime_prompt('continue'); self.assertEqual(pipeline._clean_continuation(instruction+'\nFinished answer.'),'Finished answer.')
    def test_forced_web_does_not_fallback(self):
        decision=RoutingDecision(source='web',web_mode='lookup',task='general',freshness='current',project_evidence=False,reason='explicit --web lookup'); route=Route(decision=decision,execution='web_lookup',template='web-lookup',model='test',deep=False,project=None,reason='test')
        with tempfile.TemporaryDirectory() as d,patch.object(pipeline,'has_symbol_hit',return_value=False),patch.object(pipeline,'resolve_route',return_value=decision),patch.object(pipeline.Route,'from_decision',return_value=route),patch.object(pipeline,'connectivity_ok',return_value=False),patch.object(pipeline,'response_path',return_value=Path(d)/'x.md'):
            with self.assertRaisesRegex(RuntimeError,'Forced web search is unavailable'): pipeline.run('current fact',project_name='pgpt-cli',web_override='lookup',echo_route=False)
if __name__=='__main__': unittest.main()
