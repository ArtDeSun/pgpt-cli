from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools import privategpt_ingest_folder as helper


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


if __name__ == "__main__":
    unittest.main()
