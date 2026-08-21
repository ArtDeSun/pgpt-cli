from __future__ import annotations
import unittest
from unittest.mock import patch
from pgpt import server
class TestServerControls(unittest.TestCase):
    def test_manual_controls_are_parsed(self):
        payload={'messages':[{'role':'user','content':'question'}],'pgpt':{'project':'pgpt-cli','web':'lookup','context':False,'template':'debug','model':'m','deep':True,'history_mode':'off','answer_length':'long'}}
        with patch.object(server,'skill_history',side_effect=lambda h,s:h): value=server._prepare_request(payload)
        self.assertEqual((value.web,value.context,value.template,value.model,value.deep,value.history_mode,value.answer_length),('lookup',False,'debug','m',True,'off','long'))
    def test_bad_control_is_rejected(self):
        with self.assertRaises(ValueError): server._prepare_request({'messages':[{'role':'user','content':'x'}],'pgpt':{'answer_length':'huge'}})
    def test_meta_exposes_models_and_projects(self):
        with patch.object(server,'_available_models',return_value=['a:1']),patch.object(server,'project_names',return_value=['one']),patch.object(server,'list_skills',return_value=[]): meta=server._meta()
        self.assertEqual(meta['models'],['a:1']); self.assertEqual(meta['projects'],['one'])
if __name__=='__main__': unittest.main()
