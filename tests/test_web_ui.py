from __future__ import annotations
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; INDEX=ROOT/'web'/'index.html'
class TestWebUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.text=INDEX.read_text(encoding='utf-8')
    def test_self_contained(self): self.assertIn('/v1/chat/completions',self.text); self.assertIn('/api/meta',self.text); self.assertNotIn('<script src=',self.text)
    def test_chat_features(self):
        for value in ('Pinned','Recents','Search chats','Export chat','/api/responses','Download Markdown'): self.assertIn(value,self.text)
    def test_manual_controls(self):
        for value in ('id="projectMode"','Force project','Force lookup','Force research','id="model"','id="task"','id="historyMode"','Smart','id="answerLength"','id="reasoning"','Add knowledge folder'): self.assertIn(value,self.text)
    def test_rendering_streaming_and_feedback(self):
        for value in ('renderMarkdown','copy-code','stream:true','response.body.getReader()',"e==='status'","e==='replace'","e==='done'",':hover',':active',':focus-visible','data-suggestion'): self.assertIn(value,self.text)
    def test_knowledge_and_web_usage(self): self.assertIn('/api/knowledge/ingest',self.text); self.assertIn('/api/web-usage',self.text); self.assertIn('off · local-only',self.text)
if __name__=='__main__': unittest.main()
