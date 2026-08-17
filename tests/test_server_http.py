from __future__ import annotations

import json
import tempfile
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from pgpt import server


class TestServerHTTP(unittest.TestCase):
    def setUp(self) -> None:
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.PgptHandler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.httpd.server_port}"

    def tearDown(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=2)

    def test_health_and_models(self) -> None:
        with urllib.request.urlopen(self.base + "/health", timeout=2) as response:
            payload = json.load(response)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["name"], "pgpt-cli")
        self.assertIn("server_time", payload)
        with urllib.request.urlopen(self.base + "/v1/models", timeout=2) as response:
            payload = json.load(response)
        self.assertEqual(payload["data"][0]["id"], "pgpt-cli")

    def test_chat_completion_endpoint(self) -> None:
        completion = {
            "id": "chatcmpl-test",
            "object": "chat.completion",
            "created": 1,
            "model": "pgpt-cli",
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": "ok"},
                "finish_reason": "stop",
            }],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            "pgpt": {"route": {}, "timing": {"total_seconds": 1.0}, "response_path": "/tmp/x.md"},
        }
        request = urllib.request.Request(
            self.base + "/v1/chat/completions",
            data=json.dumps({"messages": [{"role": "user", "content": "hi"}]}).encode(),
            headers={"Content-Type": "application/json", "Origin": self.base},
            method="POST",
        )
        with patch.object(server, "_completion", return_value=completion):
            with urllib.request.urlopen(request, timeout=2) as response:
                payload = json.load(response)
                cors = response.headers.get("Access-Control-Allow-Origin")
        self.assertEqual(payload["choices"][0]["message"]["content"], "ok")
        self.assertEqual(payload["pgpt"]["timing"]["total_seconds"], 1.0)
        self.assertEqual(cors, self.base)

    def test_web_usage_endpoint(self) -> None:
        sample = {"budget": 500, "effective_requests": 65, "remaining": 435, "warning": False, "online": True}
        with patch.object(server, "_web_usage_payload", return_value=sample):
            with urllib.request.urlopen(self.base + "/api/web-usage", timeout=2) as response:
                payload = json.load(response)
        self.assertEqual(payload["effective_requests"], 65)
        self.assertEqual(payload["remaining"], 435)

    def test_response_list_read_and_download(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "saved.md"
            path.write_text("# Response\n\nHello", encoding="utf-8")
            with patch.object(server, "_response_root", return_value=root):
                with urllib.request.urlopen(self.base + "/api/responses", timeout=2) as response:
                    payload = json.load(response)
                self.assertEqual(payload["responses"][0]["name"], "saved.md")
                with urllib.request.urlopen(self.base + "/api/responses/saved.md", timeout=2) as response:
                    payload = json.load(response)
                self.assertIn("Hello", payload["content"])
                with urllib.request.urlopen(self.base + "/api/responses/saved.md/download", timeout=2) as response:
                    body = response.read().decode("utf-8")
                    disposition = response.headers.get("Content-Disposition")
                self.assertIn("Hello", body)
                self.assertIn("attachment", disposition or "")


if __name__ == "__main__":
    unittest.main()
