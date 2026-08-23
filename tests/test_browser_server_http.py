from __future__ import annotations

import json
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from unittest.mock import patch

from pgpt import browser_server


class TestBrowserServerHTTP(unittest.TestCase):
    def setUp(self) -> None:
        self.httpd = ThreadingHTTPServer(
            ("127.0.0.1", 0),
            browser_server.BrowserHandler,
        )
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.httpd.server_port}"

    def tearDown(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=2)

    def test_browser_chat_state_round_trip_endpoint(self) -> None:
        state = {
            "activeId": "chat-1",
            "chats": [
                {
                    "id": "chat-1",
                    "title": "Persistent",
                    "updatedAt": "2026-08-23T12:00:00-04:00",
                    "messages": [],
                }
            ],
        }
        with patch.object(
            browser_server.chats,
            "load_browser_state",
            return_value=state,
        ):
            with urllib.request.urlopen(self.base + "/api/chats", timeout=2) as response:
                payload = json.load(response)
        self.assertEqual(payload["state"], state)

        request = urllib.request.Request(
            self.base + "/api/chats",
            data=json.dumps(state).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with patch.object(
            browser_server.chats,
            "save_browser_state",
            return_value=state,
        ) as save:
            with urllib.request.urlopen(request, timeout=2) as response:
                payload = json.load(response)
        save.assert_called_once_with(state)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["state"], state)

    def test_root_includes_disk_persistence_script(self) -> None:
        with urllib.request.urlopen(self.base + "/", timeout=2) as response:
            text = response.read().decode("utf-8")
        self.assertIn('<script src="/persistence.js"></script>', text)
        with urllib.request.urlopen(self.base + "/persistence.js", timeout=2) as response:
            script = response.read().decode("utf-8")
        self.assertIn("/api/chats", script)


if __name__ == "__main__":
    unittest.main()
