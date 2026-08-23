from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pgpt import browser_server


class TestBrowserServer(unittest.TestCase):
    def test_browser_state_payload_reads_disk_state(self) -> None:
        state = {"activeId": "chat-1", "chats": []}
        with patch.object(browser_server.chats, "load_browser_state", return_value=state):
            self.assertEqual(browser_server._browser_state_payload(), {"state": state})

    def test_web_index_injects_persistence_script_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            index = Path(directory) / "index.html"
            index.write_text("<html><body><script>app()</script></body></html>", encoding="utf-8")
            with patch.object(browser_server.base, "WEB_INDEX_PATH", index):
                body = browser_server._web_index_bytes().decode("utf-8")
            self.assertEqual(body.count('src="/persistence.js"'), 1)
            self.assertIn("<script>app()</script>", body)

    def test_persistence_script_is_present(self) -> None:
        text = browser_server.PERSISTENCE_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("/api/chats", text)
        self.assertIn("sendBeacon", text)
        self.assertIn("Chats are saved locally on disk", text)


if __name__ == "__main__":
    unittest.main()
