from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from pgpt.retrieval import web_usage


class TestWebUsage(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def _now(self) -> datetime:
        return datetime(2026, 8, 17, tzinfo=timezone.utc)

    def test_parses_monthly_window(self) -> None:
        value = web_usage._api_quota({
            "X-RateLimit-Limit": "1, 500",
            "X-RateLimit-Remaining": "1, 435",
            "X-RateLimit-Reset": "1, 1209600",
            "X-RateLimit-Policy": "1;w=1, 500;w=2592000",
        })
        self.assertEqual(value["monthly_limit"], 500)
        self.assertEqual(value["monthly_remaining"], 435)
        self.assertEqual(value["monthly_window_seconds"], 2592000)

    def test_usage_uses_api_count_when_higher(self) -> None:
        state = {
            "period": "2026-08",
            "local_requests": 2,
            "updated_at": None,
            "api": {"monthly_limit": 500, "monthly_remaining": 435},
        }
        path = self.root / "brave_usage.json"
        path.write_text(json.dumps(state), encoding="utf-8")
        with patch.object(web_usage, "_state_path", return_value=path), patch.dict(
            web_usage.CONFIG["web"], {"monthly_request_budget": 500}, clear=False
        ):
            snapshot = web_usage.usage_snapshot(self._now())
        self.assertEqual(snapshot["api_monthly_used"], 65)
        self.assertEqual(snapshot["effective_requests"], 65)
        self.assertEqual(snapshot["remaining"], 435)

    def test_record_success_increments_local(self) -> None:
        path = self.root / "brave_usage.json"
        with patch.object(web_usage, "_state_path", return_value=path):
            snapshot = web_usage.record_search_success({}, self._now())
        self.assertEqual(snapshot["local_requests"], 1)

    def test_month_rollover_resets_local(self) -> None:
        path = self.root / "brave_usage.json"
        path.write_text(json.dumps({"period": "2026-07", "local_requests": 499, "api": {}}), encoding="utf-8")
        with patch.object(web_usage, "_state_path", return_value=path):
            snapshot = web_usage.usage_snapshot(self._now())
        self.assertEqual(snapshot["local_requests"], 0)

    def test_budget_blocks_search(self) -> None:
        path = self.root / "brave_usage.json"
        path.write_text(json.dumps({"period": "2026-08", "local_requests": 500, "api": {}}), encoding="utf-8")
        with patch.object(web_usage, "_state_path", return_value=path), patch.dict(
            web_usage.CONFIG["web"], {"monthly_request_budget": 500}, clear=False
        ):
            with self.assertRaises(RuntimeError):
                web_usage.ensure_search_budget()


if __name__ == "__main__":
    unittest.main()
