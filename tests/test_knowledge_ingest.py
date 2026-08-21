from __future__ import annotations
import tempfile, unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from pgpt import maintenance
class TestKnowledgeIngest(unittest.TestCase):
    def test_safe_and_blocked_directories(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(maintenance.resolve_knowledge_directory(d),Path(d).resolve()); p=Path(d)/'.ssh'; p.mkdir()
            with self.assertRaises(ValueError): maintenance.resolve_knowledge_directory(str(p))
        with self.assertRaises(ValueError): maintenance.resolve_knowledge_directory('/')
    def test_registers_only_after_success(self):
        with tempfile.TemporaryDirectory() as d:
            proc=SimpleNamespace(stdout=iter(['done\n']),wait=lambda:0)
            with patch.object(maintenance.subprocess,'Popen',return_value=proc),patch.object(maintenance,'privategpt_env',return_value={}),patch.object(maintenance,'cfg_path',return_value=Path(d)),patch.object(maintenance,'save_user_project') as save:
                self.assertEqual(maintenance.ingest_directory(d,project_name='notes'),0)
            save.assert_called_once()
if __name__=='__main__': unittest.main()
