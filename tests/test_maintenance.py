from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from pgpt import maintenance


class TestMaintenance(unittest.TestCase):
    def test_status_reports_local_api_and_storage_boundaries(self) -> None:
        output = io.StringIO()
        with (
            patch.object(
                maintenance,
                "_reachable",
                side_effect=[True, False, False],
            ),
            patch.object(
                maintenance,
                "privategpt_source_info",
                return_value={
                    "path": "/tmp/private-gpt",
                    "exists": True,
                    "compatible": True,
                    "reason": "ready",
                    "commit": "abc123",
                },
            ),
            redirect_stdout(output),
        ):
            maintenance.status()
        text = output.getvalue()
        self.assertIn("Ollama:", text)
        self.assertIn("pgpt API:", text)
        self.assertIn("PrivateGPT API:", text)
        self.assertIn("PrivateGPT source:", text)
        self.assertIn("PrivateGPT data:", text)
        self.assertIn("PrivateGPT embed:", text)
        self.assertIn("Context registry:", text)

    def test_redaction(self) -> None:
        self.assertNotIn(
            "actual-key",
            maintenance._redact("PGPT_BRAVE_API_KEY=actual-key"),
        )

    def test_collection_name_validation(self) -> None:
        self.assertEqual(maintenance._collection_name(None, "notes"), "notes")
        self.assertEqual(maintenance._collection_name(" notes-v1 ", "notes"), "notes-v1")
        with self.assertRaises(ValueError):
            maintenance._collection_name("   ", "notes")
        with self.assertRaises(ValueError):
            maintenance._collection_name("x" * 256, "notes")
        with self.assertRaises(ValueError):
            maintenance._collection_name(42, "notes")

    def test_privategpt_source_info_requires_expected_checkout_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "private-gpt"
            root.mkdir()
            with patch.object(
                maintenance,
                "cfg_path",
                side_effect=lambda name: root
                if name == "private_gpt_dir"
                else Path(directory),
            ):
                missing = maintenance.privategpt_source_info()
                self.assertFalse(missing["compatible"])

                (root / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
                di = root / "private_gpt" / "di.py"
                ingest_service = (
                    root
                    / "private_gpt"
                    / "server"
                    / "ingest"
                    / "ingest_service.py"
                )
                di.parent.mkdir(parents=True)
                ingest_service.parent.mkdir(parents=True)
                di.write_text("def get_injector():\n    return None\n", encoding="utf-8")
                ingest_service.write_text("class IngestService: pass\n", encoding="utf-8")

                ready = maintenance.privategpt_source_info()
                self.assertTrue(ready["compatible"])
                self.assertEqual(ready["reason"], "ready")

    def test_privategpt_env_matches_current_upstream_settings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = Path(directory) / "private-gpt-data"
            with (
                patch.dict(maintenance.os.environ, {}, clear=True),
                patch.object(maintenance, "load_secrets"),
                patch.object(
                    maintenance,
                    "cfg_path",
                    return_value=runtime,
                ),
                patch.object(
                    maintenance,
                    "list_models",
                    return_value=["mxbai-embed-large:latest"],
                ),
            ):
                env = maintenance.privategpt_env()

            self.assertEqual(
                env["OPENAI_API_BASE"],
                maintenance.CONFIG["endpoints"]["openai_api_base"],
            )
            self.assertEqual(
                env["OPENAI_EMBEDDING_API_BASE"],
                maintenance.CONFIG["endpoints"]["openai_api_base"],
            )
            self.assertEqual(
                env["PGPT_EMBEDDING_DEFAULT"],
                "mxbai-embed-large:latest",
            )
            self.assertEqual(
                env["PGPT_EMBED_DIM"],
                str(maintenance.CONFIG["private_gpt"]["embed_dim"]),
            )
            self.assertEqual(env["UV_PROJECT_ENVIRONMENT"], str(runtime / "venv"))
            self.assertEqual(env["PGPT_LOCAL_DATA_FOLDER"], str(runtime / "private_gpt"))
            self.assertEqual(env["PGPT_QDRANT_PATH"], str(runtime / "qdrant"))
            self.assertEqual(
                env["PGPT_CODE_EXECUTION_VOLUME_ROOT"],
                str(runtime / "volumes"),
            )
            self.assertTrue(runtime.is_dir())
            self.assertTrue((runtime / "private_gpt").is_dir())
            self.assertTrue((runtime / "qdrant").is_dir())
            self.assertTrue((runtime / "volumes").is_dir())
            self.assertNotIn("PGPT_HOME", env)
            self.assertNotIn("PGPT_PROFILES", env)

    def test_privategpt_embedding_environment_override_wins(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = Path(directory) / "runtime"
            with (
                patch.dict(
                    maintenance.os.environ,
                    {
                        "PGPT_EMBEDDING_DEFAULT": "custom-embed",
                        "PGPT_EMBED_DIM": "768",
                    },
                    clear=True,
                ),
                patch.object(maintenance, "load_secrets"),
                patch.object(maintenance, "cfg_path", return_value=runtime),
                patch.object(
                    maintenance,
                    "list_models",
                    return_value=["custom-embed:latest"],
                ),
            ):
                env = maintenance.privategpt_env()
            self.assertEqual(env["PGPT_EMBEDDING_DEFAULT"], "custom-embed:latest")
            self.assertEqual(env["PGPT_EMBED_DIM"], "768")

    def test_privategpt_embedding_model_must_be_installed(self) -> None:
        with patch.object(
            maintenance,
            "list_models",
            return_value=["qwen3-embedding:0.6b"],
        ):
            with self.assertRaisesRegex(RuntimeError, "not installed in Ollama"):
                maintenance._resolve_privategpt_embedding_model(
                    "mxbai-embed-large"
                )

    def test_privategpt_commands_pin_python_311_core_and_frozen_lock(self) -> None:
        self.assertEqual(
            maintenance._uv_privategpt_prefix(),
            ["uv", "run", "--frozen", "--python", "3.11", "--extra", "core"],
        )

    def test_ingest_command_uses_collection_aware_helper(self) -> None:
        command = maintenance._ingest_command(
            Path("/tmp/notes"),
            [".env"],
            True,
            "notes-v1",
        )
        self.assertEqual(
            command[:8],
            [
                "uv",
                "run",
                "--frozen",
                "--python",
                "3.11",
                "--extra",
                "core",
                "python",
            ],
        )
        self.assertEqual(command[8], str(maintenance._INGEST_HELPER))
        self.assertIn("--collection", command)
        self.assertIn("notes-v1", command)
        self.assertIn("--ignored", command)
        self.assertIn(".env", command)
        self.assertEqual(command[-1], "--watch")

    def test_project_ingest_propagates_privategpt_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = {
                "knowledge_dir": directory,
                "ingest_ignored": [],
                "collection": "notes-v1",
            }
            with (
                patch.object(maintenance, "get_project", return_value=("notes", project)),
                patch.object(
                    maintenance,
                    "_require_privategpt_checkout",
                    return_value=Path(directory),
                ),
                patch.object(maintenance, "_reachable", return_value=False),
                patch.object(
                    maintenance.subprocess,
                    "run",
                    return_value=SimpleNamespace(returncode=7),
                ),
                patch.object(maintenance, "privategpt_env", return_value={}),
            ):
                with self.assertRaisesRegex(RuntimeError, "exit code 7"):
                    maintenance.ingest("notes")

    def test_automatic_ingest_ignores_secrets_and_generated_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = root / "private-gpt-data"
            runtime.mkdir()
            (root / ".env").write_text("TOKEN=secret", encoding="utf-8")
            (root / ".env.production").write_text("TOKEN=secret", encoding="utf-8")
            (root / "client.key").write_text("secret", encoding="utf-8")
            (root / "certificate.pem").write_text("secret", encoding="utf-8")
            (root / "module.pyc").write_bytes(b"generated")
            (root / "__pycache__").mkdir()
            (root / "node_modules").mkdir()
            with patch.object(
                maintenance,
                "cfg_path",
                side_effect=lambda name: runtime
                if name == "pgpt_home"
                else Path(directory),
            ):
                ignored = maintenance._automatic_ingest_ignores(root)
            for name in (
                ".ssh",
                ".gnupg",
                ".aws",
                ".git",
                ".venv",
                "__pycache__",
                "node_modules",
                "private-gpt-data",
                ".env",
                ".env.production",
                "client.key",
                "certificate.pem",
                "module.pyc",
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
