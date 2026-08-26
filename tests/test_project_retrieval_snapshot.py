from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pgpt.retrieval import project
from pgpt.retrieval.project import build_context


class TestHistoricalProjectRetrieval(unittest.TestCase):
    def test_historical_project_retrieves_select_model_source(self) -> None:
        context, files = build_context(
            "Explain how select_model works in the historical pgpt-cli project.",
            "pgpt-cli-history",
        )
        self.assertIn("pgpt/models/selector.py", files)
        self.assertIn("def select_model(", context)
        self.assertIn("model_override", context)

    def test_plain_text_notes_are_retrieved_for_generic_project_summary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            note = root / "test_note.txt"
            note.write_text(
                "Project codename: AURORA-731.\nOwner: local acceptance test.\n",
                encoding="utf-8",
            )

            with patch.object(project, "_source_root", return_value=root):
                context, files = build_context(
                    "Summarize the most distinctive facts in this project and cite "
                    "the source filenames.",
                    "test-notes",
                )

        self.assertEqual(files, ["test_note.txt"])
        self.assertIn("### SOURCE FILE: test_note.txt", context)
        self.assertIn("Project codename: AURORA-731.", context)


if __name__ == "__main__":
    unittest.main()
