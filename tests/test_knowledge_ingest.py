from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from pgpt import maintenance


class TestKnowledgeIngest(unittest.TestCase):
    def test_safe_and_blocked_directories(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(
                maintenance.resolve_knowledge_directory(directory),
                Path(directory).resolve(),
            )
            sensitive = Path(directory) / ".ssh"
            sensitive.mkdir()
            with self.assertRaises(ValueError):
                maintenance.resolve_knowledge_directory(str(sensitive))
        with self.assertRaises(ValueError):
            maintenance.resolve_knowledge_directory("/")

    def test_invalid_or_builtin_name_fails_before_privategpt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(maintenance.subprocess, "Popen") as popen:
                with self.assertRaisesRegex(ValueError, "Built-in project already exists"):
                    maintenance.ingest_directory(
                        directory,
                        project_name="pgpt-cli",
                    )
            popen.assert_not_called()

    def test_registers_only_after_success(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            proc = SimpleNamespace(stdout=iter(["done\n"]), wait=lambda: 0)
            with (
                patch.object(maintenance.subprocess, "Popen", return_value=proc),
                patch.object(maintenance, "privategpt_env", return_value={}),
                patch.object(maintenance, "cfg_path", return_value=Path(directory)),
                patch.object(maintenance, "save_user_project") as save,
            ):
                self.assertEqual(
                    maintenance.ingest_directory(directory, project_name="notes"),
                    0,
                )
            save.assert_called_once()

    def test_failed_ingest_is_not_registered(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            proc = SimpleNamespace(stdout=iter(["failed\n"]), wait=lambda: 3)
            with (
                patch.object(maintenance.subprocess, "Popen", return_value=proc),
                patch.object(maintenance, "privategpt_env", return_value={}),
                patch.object(maintenance, "cfg_path", return_value=Path(directory)),
                patch.object(maintenance, "save_user_project") as save,
            ):
                self.assertEqual(
                    maintenance.ingest_directory(directory, project_name="notes"),
                    3,
                )
            save.assert_not_called()


if __name__ == "__main__":
    unittest.main()
