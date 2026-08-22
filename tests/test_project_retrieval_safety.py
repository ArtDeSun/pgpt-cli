from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pgpt.retrieval.project import _iter_files


class TestProjectRetrievalSafety(unittest.TestCase):
    def test_iter_files_skips_sensitive_and_generated_directories(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            keep = root / "src" / "app.py"
            keep.parent.mkdir()
            keep.write_text("print('ok')", encoding="utf-8")

            skipped = [
                root / ".aws" / "profile.json",
                root / ".ssh" / "notes.md",
                root / ".gnupg" / "export.json",
                root / ".venv" / "debug.py",
                root / "node_modules" / "pkg" / "index.js",
            ]
            for path in skipped:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("secret or generated", encoding="utf-8")

            self.assertEqual(list(_iter_files(root)), [keep])

    def test_iter_files_skips_symlink_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            outside = root.parent / f"{root.name}-outside.py"
            outside.write_text("outside", encoding="utf-8")
            try:
                link = root / "linked.py"
                link.symlink_to(outside)
                self.assertEqual(list(_iter_files(root)), [])
            finally:
                outside.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
