from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from pgpt.runtime import http


class _Response:
    def __init__(self, body: bytes, headers: dict[str, str]) -> None:
        self._body = body
        self.headers = headers

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def read(self) -> bytes:
        return self._body


class TestHTTPUsageHooks(unittest.TestCase):
    def test_brave_request_checks_budget_and_records_headers(self) -> None:
        response = _Response(
            b'{"web":{"results":[]}}',
            {
                "X-RateLimit-Limit": "1, 500",
                "X-RateLimit-Remaining": "1, 499",
                "X-RateLimit-Policy": "1;w=1, 500;w=2592000",
            },
        )
        with patch("urllib.request.urlopen", return_value=response), patch(
            "pgpt.retrieval.web_usage.ensure_search_budget"
        ) as ensure, patch(
            "pgpt.retrieval.web_usage.record_search_success"
        ) as record:
            value, headers = http.json_request_with_headers(
                "GET",
                "https://api.search.brave.com/res/v1/web/search?q=test",
                headers={"X-Subscription-Token": "key"},
            )
        self.assertIn("web", value)
        ensure.assert_called_once_with()
        record.assert_called_once()
        self.assertEqual(headers["X-RateLimit-Remaining"], "1, 499")

    def test_non_brave_request_does_not_import_usage_policy(self) -> None:
        response = _Response(b'{"ok":true}', {})
        with patch("urllib.request.urlopen", return_value=response):
            value = http.json_request("GET", "http://127.0.0.1:11434/api/tags")
        self.assertEqual(value, {"ok": True})


if __name__ == "__main__":
    unittest.main()
