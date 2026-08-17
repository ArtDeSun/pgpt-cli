from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pgpt.output.stream import ResponseWriter
from pgpt.runtime.timing import Timing


class TestResponseWriter(unittest.TestCase):
    def test_finished_markdown_has_metadata_and_view_link(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "answer.md"
            writer = ResponseWriter(path, prompt="Question")
            writer.set_metadata(project="pgpt-cli", model="model", template="general")
            with patch("sys.stdout.write"), patch("sys.stdout.flush"):
                writer.write("Answer")
                writer.finish(Timing())
            text = path.read_text(encoding="utf-8")
        self.assertIn("**Created:**", text)
        self.assertIn("**Rendered view:**", text)
        self.assertIn("?response=answer.md", text)
        self.assertIn("## Prompt", text)
        self.assertIn("## Assistant", text)
        self.assertIn("## Timing", text)


if __name__ == "__main__":
    unittest.main()
