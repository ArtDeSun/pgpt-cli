from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
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

    def test_automatic_ingest_ignores_secrets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".env").write_text("TOKEN=secret", encoding="utf-8")
            (root / ".env.production").write_text("TOKEN=secret", encoding="utf-8")
            (root / "client.key").write_text("secret", encoding="utf-8")
            (root / "certificate.pem").write_text("secret", encoding="utf-8")
            ignored = maintenance._automatic_ingest_ignores(root)
            for name in (
                ".ssh",
                ".gnupg",
                ".aws",
                ".env",
                ".env.production",
                "client.key",
                "certificate.pem",
            ):
                with self.subTest(name=name):
                    self.assertIn(name, ignored)

    def test_zero_byte_name_without_collision_uses_direct_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "empty.md").write_bytes(b"")
            with maintenance._prepared_ingest(root, []) as (
                ingest_root,
                ignored,
                collisions,
            ):
                self.assertEqual(ingest_root, root)
                self.assertIn("empty.md", ignored)
                self.assertEqual(collisions, [])

    def test_duplicate_zero_byte_basename_uses_filtered_staging_tree(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "a").mkdir()
            (root / "b").mkdir()
            (root / "a" / "same.md").write_bytes(b"")
            (root / "b" / "same.md").write_text("keep me", encoding="utf-8")

            with maintenance._prepared_ingest(root, []) as (
                ingest_root,
                ignored,
                collisions,
            ):
                self.assertNotEqual(ingest_root, root)
                self.assertEqual(collisions, ["same.md"])
                self.assertNotIn("same.md", ignored)
                self.assertFalse((ingest_root / "a" / "same.md").exists())
                self.assertEqual(
                    (ingest_root / "b" / "same.md").read_text(encoding="utf-8"),
                    "keep me",
                )

    def test_configured_basename_ignore_does_not_require_staging(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "a").mkdir()
            (root / "b").mkdir()
            (root / "a" / "same.md").write_bytes(b"")
            (root / "b" / "same.md").write_text("intentionally ignored", encoding="utf-8")

            with maintenance._prepared_ingest(root, ["same.md"]) as (
                ingest_root,
                ignored,
                collisions,
            ):
                self.assertEqual(ingest_root, root)
                self.assertEqual(collisions, [])
                self.assertIn("same.md", ignored)

    def test_privategpt_runtime_data_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = Path(directory) / "private-gpt-data"
            child = runtime / "local_data"
            child.mkdir(parents=True)
            with patch.object(
                maintenance,
                "cfg_path",
                side_effect=lambda name: runtime
                if name == "pgpt_home"
                else Path(directory),
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "PrivateGPT runtime data",
                ):
                    maintenance.resolve_knowledge_directory(str(child))


if __name__ == "__main__":
    unittest.main()
