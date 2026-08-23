from __future__ import annotations

import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from pgpt import privategpt_ingest as helper


class _FakeIngestService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def bulk_ingest(self, **kwargs: object) -> None:
        self.calls.append(kwargs)


class TestPrivateGPTIngestHelper(unittest.TestCase):
    def test_artifact_ids_include_relative_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "one" / "same.md"
            second = root / "two" / "same.md"
            first.parent.mkdir()
            second.parent.mkdir()
            first.write_text("one", encoding="utf-8")
            second.write_text("two", encoding="utf-8")

            self.assertEqual(helper._artifact_id(root, first), "one__same.md")
            self.assertEqual(helper._artifact_id(root, second), "two__same.md")
            self.assertNotEqual(
                helper._artifact_id(root, first),
                helper._artifact_id(root, second),
            )

    def test_long_artifact_id_is_bounded_and_stable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            nested = root
            for index in range(12):
                nested = nested / (f"segment-{index}-" + "x" * 20)
            path = nested / "document.md"
            artifact = helper._artifact_id(root, path)
            self.assertLessEqual(len(artifact), 255)
            self.assertEqual(artifact, helper._artifact_id(root, path))

    def test_iter_files_skips_ignored_names_and_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            keep = root / "keep.md"
            ignored = root / ".env"
            nested = root / "nested"
            nested.mkdir()
            nested_keep = nested / "also.md"
            keep.write_text("keep", encoding="utf-8")
            ignored.write_text("secret", encoding="utf-8")
            nested_keep.write_text("nested", encoding="utf-8")
            symlink = root / "linked.md"
            symlink.symlink_to(keep)

            files = list(helper._iter_files(root, {".env"}))
            self.assertEqual(files, [keep, nested_keep])
            self.assertNotIn(ignored, files)
            self.assertNotIn(symlink, files)

    def test_ingest_file_preserves_collection_and_relative_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "notes" / "entry.md"
            path.parent.mkdir()
            path.write_text("hello", encoding="utf-8")
            service = _FakeIngestService()

            helper._ingest_file(
                service,
                root=root,
                path=path,
                collection="notes-v1",
            )

            self.assertEqual(len(service.calls), 1)
            call = service.calls[0]
            self.assertEqual(call["collection"], "notes-v1")
            files = call["files"]
            assert isinstance(files, list)
            data_path, artifact, metadata = files[0]
            self.assertEqual(data_path, path)
            self.assertEqual(artifact, "notes__entry.md")
            self.assertEqual(
                metadata,
                {"file_name": "entry.md", "relative_path": "notes/entry.md"},
            )

    def test_current_privategpt_injector_api_is_preferred(self) -> None:
        expected = object()
        package = types.ModuleType("private_gpt")
        di = types.ModuleType("private_gpt.di")
        di.get_injector = lambda: expected
        package.di = di
        with patch.dict(
            sys.modules,
            {"private_gpt": package, "private_gpt.di": di},
        ):
            self.assertIs(helper._application_injector(), expected)

    def test_legacy_privategpt_injector_api_is_supported(self) -> None:
        expected = object()
        package = types.ModuleType("private_gpt")
        di = types.ModuleType("private_gpt.di")
        di.get_global_injector = lambda: expected
        package.di = di
        with patch.dict(
            sys.modules,
            {"private_gpt": package, "private_gpt.di": di},
        ):
            self.assertIs(helper._application_injector(), expected)

    def test_privategpt_embedding_becomes_llamaindex_process_default(self) -> None:
        expected = object()

        class FakeSettings:
            embed_model = None

        llama_package = types.ModuleType("llama_index")
        llama_core = types.ModuleType("llama_index.core")
        llama_core.Settings = FakeSettings
        llama_package.core = llama_core
        service = types.SimpleNamespace(
            embedding_component=types.SimpleNamespace(get_embed=lambda: expected)
        )

        with patch.dict(
            sys.modules,
            {"llama_index": llama_package, "llama_index.core": llama_core},
        ):
            helper._configure_llama_index_embedding(service)

        self.assertIs(FakeSettings.embed_model, expected)

    def test_source_mime_equivalents_extend_upstream_without_replacing_it(self) -> None:
        package = types.ModuleType("private_gpt")
        components = types.ModuleType("private_gpt.components")
        ingest = types.ModuleType("private_gpt.components.ingest")
        utils = types.ModuleType("private_gpt.components.ingest.utils")
        ingest_helper = types.ModuleType("private_gpt.components.ingest.ingest_helper")

        def original(guest: str, actual: str) -> bool:
            return frozenset({guest, actual}) == frozenset({"text/markdown", "text/plain"})

        utils.should_ignore_mime_mismatch = original
        ingest_helper.should_ignore_mime_mismatch = original
        ingest.utils = utils
        ingest.ingest_helper = ingest_helper
        components.ingest = ingest
        package.components = components

        with patch.dict(
            sys.modules,
            {
                "private_gpt": package,
                "private_gpt.components": components,
                "private_gpt.components.ingest": ingest,
                "private_gpt.components.ingest.utils": utils,
                "private_gpt.components.ingest.ingest_helper": ingest_helper,
            },
        ):
            helper._configure_source_mime_compatibility()
            self.assertTrue(utils.should_ignore_mime_mismatch("text/css", "text/plain"))
            self.assertTrue(
                ingest_helper.should_ignore_mime_mismatch(
                    "text/javascript", "application/javascript"
                )
            )
            self.assertTrue(
                utils.should_ignore_mime_mismatch("text/markdown", "text/plain")
            )
            self.assertFalse(
                utils.should_ignore_mime_mismatch("image/png", "text/plain")
            )

    def test_file_backed_qdrant_is_forced_to_serial_ingest(self) -> None:
        package = types.ModuleType("private_gpt")
        components = types.ModuleType("private_gpt.components")
        vector_store = types.ModuleType("private_gpt.components.vector_store")
        patched = types.ModuleType(
            "private_gpt.components.vector_store.patched_qdrant_store"
        )

        class FakeStore:
            @classmethod
            def executor(cls, *args: object, **kwargs: object) -> object:
                return object()

        patched.PatchedQdrantVectorStore = FakeStore
        vector_store.patched_qdrant_store = patched
        components.vector_store = vector_store
        package.components = components
        service = types.SimpleNamespace(
            settings=types.SimpleNamespace(qdrant=types.SimpleNamespace(url=""))
        )

        with patch.dict(
            sys.modules,
            {
                "private_gpt": package,
                "private_gpt.components": components,
                "private_gpt.components.vector_store": vector_store,
                "private_gpt.components.vector_store.patched_qdrant_store": patched,
            },
        ):
            helper._configure_local_qdrant_safety(service)

        self.assertIsNone(FakeStore.executor(max_workers=8))


if __name__ == "__main__":
    unittest.main()
