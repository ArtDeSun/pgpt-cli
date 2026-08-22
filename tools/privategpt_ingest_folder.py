from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from private_gpt.di import get_global_injector
from private_gpt.server.ingest.ingest_service import IngestService
from private_gpt.server.ingest.ingest_watcher import IngestWatcher


def _artifact_id(root: Path, path: Path) -> str:
    relative = path.relative_to(root).as_posix()
    candidate = relative.replace("/", "__")
    if len(candidate) <= 255:
        return candidate
    digest = hashlib.sha256(relative.encode("utf-8")).hexdigest()[:16]
    return f"{candidate[:238]}-{digest}"


def _iter_files(root: Path, ignored: set[str]):
    for path in sorted(root.iterdir(), key=lambda item: item.name.casefold()):
        if path.name in ignored or path.is_symlink():
            continue
        if path.is_file():
            yield path
        elif path.is_dir():
            yield from _iter_files(path, ignored)


def _ingest_file(
    service: IngestService,
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


def main() -> None:
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

    ignored = set(args.ignored)
    service = get_global_injector().get(IngestService)

    for path in _iter_files(root, ignored):
        _ingest_file(service, root=root, path=path, collection=args.collection)

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
                collection=args.collection,
            )
        except Exception as exc:
            print(f"[privategpt] watch ingest failed: {exc}", flush=True)

    watcher = IngestWatcher(root, on_change)
    watcher.start()


if __name__ == "__main__":
    main()
