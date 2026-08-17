from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from pgpt import maintenance


class TestMaintenance(unittest.TestCase):
    def test_status_reports_local_api(self) -> None:
        output = io.StringIO()
        with patch.object(
            maintenance,
            "_reachable",
            side_effect=[True, False, False],
        ), redirect_stdout(output):
            maintenance.status()
        text = output.getvalue()
        self.assertIn("Ollama:", text)
        self.assertIn("pgpt API:", text)
        self.assertIn("PrivateGPT:", text)

    def test_redaction(self) -> None:
        self.assertNotIn(
            "actual-key",
            maintenance._redact("PGPT_BRAVE_API_KEY=actual-key"),
        )


if __name__ == "__main__":
    unittest.main()
