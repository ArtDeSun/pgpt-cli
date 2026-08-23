from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from typing import Any, Iterator

_SAFE_MIME_EQUIVALENTS = {
    frozenset({"text/javascript", "application/javascript"}),
    frozenset({"text/vnd.trolltech.linguist", "application/javascript"}),
    frozenset({"text/vnd.trolltech.linguist", "text/plain"}),
    frozenset({"text/vnd.trolltech.linguist", "text/x-c"}),
    frozenset({"text/css", "text/plain"}),
}


def _artifact_id(root: Path, path: Path) -> str:
    relative = path.relative_to(root).as_posix()
    candidate = relative.replace("/", "__")
    if len(candidate) <= 255:
        return candidate
    digest = hashlib.sha256(relative.encode("utf-8")).hexdigest()[:16]
    return f"{candidate[:238]}-{digest}"


def _iter_files(root: Path, ignored: set[str]) -> Iterator[Path]:
    for path in sorted(root.iterdir(), key=lambda item: item.name.casefold()):
        if path.name in ignored or path.is_symlink():
            continue
        if path.is_file():
            yield path
        elif path.is_dir():
            yield from _iter_files(path, ignored)


def _ingest_file(
    service: Any,
    *,
    root: Path,
    path: Path,
    collection: str,
) -> None:
    relative = path.relative_to(root).as_posix()
    print(f"[privategpt] ingest {relative}", flush=True)
    service.bulk_ingest(
        collection=collection,
        files=[
            (
                path,
                _artifact_id(root, path),
                {
                    "file_name": path.name,
                    "relative_path": relative,
                },
            )
        ],
    )


def _application_injector() -> Any:
    """Return PrivateGPT's application injector across supported API revisions."""
    from private_gpt import di

    getter = getattr(di, "get_injector", None)
    if getter is None:
        getter = getattr(di, "get_global_injector", None)
    if getter is None:
        raise RuntimeError(
            "Unsupported PrivateGPT checkout: no get_injector-compatible API found"
        )
    return getter()


def _configure_llama_index_embedding(service: Any) -> None:
    """Make pristine upstream VectorStoreIndex initialization use PrivateGPT's embedding."""
    component = getattr(service, "embedding_component", None)
    getter = getattr(component, "get_embed", None)
    if getter is None:
        return

    from llama_index.core import Settings as LlamaIndexSettings

    LlamaIndexSettings.embed_model = getter()


def _configure_source_mime_compatibility() -> None:
    """Accept known-equivalent source MIME pairs without patching PrivateGPT source."""
    from private_gpt.components.ingest import ingest_helper, utils

    original = utils.should_ignore_mime_mismatch

    def compatible(guest_mime: str, actual_mime: str) -> bool:
        return (
            frozenset({guest_mime, actual_mime}) in _SAFE_MIME_EQUIVALENTS
            or original(guest_mime, actual_mime)
        )

    utils.should_ignore_mime_mismatch = compatible
    # IngestionHelper imports the function directly, so update that module alias too.
    ingest_helper.should_ignore_mime_mismatch = compatible


def _configure_local_qdrant_safety(service: Any) -> None:
    """Keep file-backed Qdrant writes serial inside the ingestion subprocess."""
    settings = getattr(service, "settings", None)
    qdrant = getattr(settings, "qdrant", None)
    if qdrant is None or getattr(qdrant, "url", None):
        return

    from private_gpt.components.vector_store.patched_qdrant_store import (
        PatchedQdrantVectorStore,
    )

    def serial_executor(cls: type[Any], *args: Any, **kwargs: Any) -> None:
        return None

    PatchedQdrantVectorStore.executor = classmethod(serial_executor)


def _configure_privategpt_ingestion(service: Any) -> None:
    """Apply process-local compatibility needed by pgpt's clean upstream workflow."""
    _configure_llama_index_embedding(service)
    _configure_source_mime_compatibility()
    _configure_local_qdrant_safety(service)


def main() -> None:
    # Delayed imports keep this helper importable by pgpt's normal CI without
    # installing PrivateGPT into pgpt's own environment. The script itself is
    # executed through `uv run` inside the PrivateGPT checkout.
    from private_gpt.server.ingest.ingest_service import IngestService
    from private_gpt.server.ingest.ingest_watcher import IngestWatcher

    parser = argparse.ArgumentParser(
        description="Ingest a folder into a named PrivateGPT collection."
    )
    parser.add_argument("folder")
    parser.add_argument("--collection", required=True)
    parser.add_argument("--ignored", nargs="*", default=[])
    parser.add_argument("--watch", action="store_true")
    args = parser.parse_args()

    root = Path(args.folder).expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"Path is not a directory: {root}")

    collection = args.collection.strip()
    if not collection or len(collection) > 255:
        raise ValueError("Collection must contain 1 to 255 characters")

    ignored = set(args.ignored)
    service = _application_injector().get(IngestService)
    _configure_privategpt_ingestion(service)

    for path in _iter_files(root, ignored):
        _ingest_file(service, root=root, path=path, collection=collection)

    if not args.watch:
        return

    print(f"[privategpt] watching {root}", flush=True)

    def on_change(path: Path) -> None:
        try:
            if path.is_symlink():
                return
            resolved = path.expanduser().resolve()
            if not resolved.exists() or not resolved.is_file():
                return
            relative = resolved.relative_to(root)
            if any(part in ignored for part in relative.parts):
                return
            _ingest_file(
                service,
                root=root,
                path=resolved,
                collection=collection,
            )
        except Exception as exc:
            print(f"[privategpt] watch ingest failed: {exc}", flush=True)

    watcher = IngestWatcher(root, on_change)
    watcher.start()


if __name__ == "__main__":
    main()
