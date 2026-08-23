from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pgpt.storage import chats


class TestBrowserChatPersistence(unittest.TestCase):
    def test_browser_state_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(chats, "cfg_path", return_value=root):
                state = {
                    "activeId": "chat-1",
                    "chats": [
                        {
                            "id": "chat-1",
                            "title": "Persistent chat",
                            "pinned": True,
                            "updatedAt": "2026-08-23T12:00:00-04:00",
                            "messages": [
                                {
                                    "role": "user",
                                    "content": "hello",
                                    "at": "2026-08-23T12:00:00-04:00",
                                }
                            ],
                        }
                    ],
                }
                self.assertEqual(chats.save_browser_state(state), state)
                self.assertEqual(chats.load_browser_state(), state)
                self.assertTrue((root / "browser-state.json").is_file())

    def test_invalid_browser_state_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "chats list"):
            chats.save_browser_state({"activeId": None})
        with self.assertRaisesRegex(ValueError, "activeId"):
            chats.save_browser_state(
                {
                    "activeId": "missing",
                    "chats": [
                        {"id": "chat-1", "title": "Chat", "messages": []}
                    ],
                }
            )

    def test_corrupt_browser_state_does_not_break_startup(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "browser-state.json").write_text("{broken", encoding="utf-8")
            with patch.object(chats, "cfg_path", return_value=root):
                self.assertIsNone(chats.load_browser_state())


if __name__ == "__main__":
    unittest.main()
