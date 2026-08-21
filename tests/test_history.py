from __future__ import annotations
import unittest
from pgpt.runtime.history import select_history
H=[{'role':'user','content':'Explain pgpt routing code.'},{'role':'assistant','content':'The router chooses local, project, or web.'},{'role':'user','content':'How does model selection work in pgpt?'},{'role':'assistant','content':'It maps tasks to models.'}]
class TestHistory(unittest.TestCase):
    def test_unrelated_topic_is_dropped(self): self.assertEqual(select_history('Who won the NBA championship?',H,mode='auto'),[])
    def test_short_followup_keeps_topic(self): self.assertEqual(select_history('Use the web for that.',H,mode='auto'),H)
    def test_full_and_off(self):
        self.assertEqual(select_history('x',H,mode='full',limit=2),H[-2:]); self.assertEqual(select_history('x',[*H,{'role':'system','content':'skill'}],mode='off'),[{'role':'system','content':'skill'}])
if __name__=='__main__': unittest.main()
