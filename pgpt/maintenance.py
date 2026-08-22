from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import urllib.request
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterator

from pgpt.config import (
    CONFIG,
    cfg_path,
    expand,
    get_project,
    load_secrets,
    save_user_project,
    validate_user_project_name,
)
from pgpt.generation.ollama import list_models


_SENSITIVE_NAMES = {".ssh", ".gnupg", ".aws"}
_SECRET_SUFFIXES = {".pem", ".key"}
_SYSTEM_ROOTS = tuple(Path(value) for value in ("/etc", "/proc", "/sys", "/dev", "/boot"))
_INGEST_HELPER = Path(__file__).resolve().parents[1] / "tools" / "privategpt_ingest_folder.py"


def _reachable(url: str, timeout: float = 1.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout):
            return True
    except Exception:
        return False


def status() -> None:
    ollama = CONFIG["endpoints"]["ollama"].rstrip("/") + "/api/tags"
    private_gpt = CONFIG["endpoints"]["private_gpt"].rstrip("/") + "/v1/models"
    server = CONFIG.get("server", {})
    host = str(server.get("host", "127.0.0.1"))
    port = int(server.get("port", 8765))
    local_api = f"http://{host}:{port}/health"
    print(f"Ollama:     {'reachable' if _reachable(ollama) else 'NOT reachable'}")
    print(f"pgpt API:   {'reachable' if _reachable(local_api) else 'NOT reachable'}")
    print(f"PrivateGPT: {'reachable' if _reachable(private_gpt) else 'NOT reachable'}")


def models() -> None:
    try:
        for name in list_models():
            print(name)
    except Exception as exc:
        raise SystemExit(str(exc)) from exc


def sync(project_name: str | None = None) -> None:
    project_name, project = get_project(project_name)
    source = expand(project["source_dir"])
    destination = expand(project["knowledge_dir"])
    if source == destination or project.get("sync_required") is False:
        print(f"[sync] {project_name}: source is already the knowledge directory; nothing to copy")
        return
    destination.mkdir(parents=True, exist_ok=True)
    cmd = ["rsync", "-a", "--delete"]
    for pattern in project.get("sync_excludes", []):
        cmd.append(f"--exclude={pattern}")
    cmd += [f"{source}/", f"{destination}/"]
    print(f"[sync] {project_name}: {source} -> {destination}")
    subprocess.run(cmd, check=True)


def _automatic_ingest_ignores(root: Path) -> list[str]:
    """Return basenames that should never be sent to a knowledge index."""
    ignored = set(_SENSITIVE_NAMES)
    for path in root.rglob("*"):
        name = path.name
        folded = name.casefold()
        if folded == ".env" or folded.startswith(".env."):
            ignored.add(name)
        if path.is_file() and path.suffix.casefold() in _SECRET_SUFFIXES:
            ignored.add(name)
    return sorted(ignored)


def _zero_byte_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        try:
            if path.stat().st_size == 0:
                files.append(path)
        except OSError:
            continue
    return sorted(files)


def _zero_byte_name_collisions(
    root: Path,
    zero_files: list[Path],
    configured: list[str],
) -> list[str]:
    configured_names = set(configured)
    zero_names = {path.name for path in zero_files if path.name not in configured_names}
    if not zero_names:
        return []

    nonempty_names: set[str] = set()
    for path in root.rglob("*"):
        if not path.is_file() or path.name not in zero_names:
            continue
        try:
            if path.stat().st_size > 0:
                nonempty_names.add(path.name)
        except OSError:
            continue
    return sorted(zero_names & nonempty_names)


def privategpt_env() -> dict[str, str]:
    load_secrets()
    env = os.environ.copy()
    api_base = CONFIG["endpoints"]["openai_api_base"]
    env["OPENAI_API_BASE"] = api_base
    if not env.get("OPENAI_EMBEDDING_API_BASE"):
        env["OPENAI_EMBEDDING_API_BASE"] = api_base
    env["PGPT_HOME"] = str(cfg_path("pgpt_home"))
    return env


def _ingest_command(
    root: Path,
    ignored: list[str],
    watch: bool,
    collection: str,
) -> list[str]:
    cmd = [
        "uv",
        "run",
        "python",
        str(_INGEST_HELPER),
        str(root),
        "--collection",
        collection,
    ]
    if ignored:
        cmd += ["--ignored", *ignored]
    if watch:
        cmd.append("--watch")
    return cmd


@contextmanager
def _prepared_ingest(
    root: Path,
    configured: list[str],
    *,
    watch: bool = False,
) -> Iterator[tuple[Path, list[str], list[str]]]:
    """Prepare a safe ingestion root without modifying the user's source tree.

    PrivateGPT ignores local-ingestion entries by basename. If a zero-byte file
    and a valid file in another directory share the same basename, a basename
    ignore would hide both. For one-shot ingestion, create a temporary filtered
    tree only for that collision case. Normal ingestion keeps using the original
    directory and has no copy overhead.

    Watched ingestion cannot use a temporary snapshot because later source
    changes would not be mirrored into it. In that rare collision case we retain
    basename filtering and report the collision to the caller.
    """

    configured = list(dict.fromkeys([*configured, *_automatic_ingest_ignores(root)]))
    zero_files = _zero_byte_files(root)
    zero_names = sorted({path.name for path in zero_files})
    collisions = _zero_byte_name_collisions(root, zero_files, configured)

    if not collisions or watch:
        ignored = list(dict.fromkeys([*configured, *zero_names]))
        yield root, ignored, collisions
        return

    zero_relative = {path.relative_to(root) for path in zero_files}
    with tempfile.TemporaryDirectory(prefix="pgpt-ingest-") as temp:
        staging_root = Path(temp) / "source"

        def ignore_zero_byte(directory: str, names: list[str]) -> list[str]:
            base = Path(directory)
            skipped: list[str] = []
            for name in names:
                candidate = base / name
                try:
                    relative = candidate.relative_to(root)
                except ValueError:
                    continue
                if relative in zero_relative:
                    skipped.append(name)
            return skipped

        shutil.copytree(
            root,
            staging_root,
            ignore=ignore_zero_byte,
            symlinks=True,
        )
        yield staging_root, configured, collisions


def ingest(project_name: str | None = None, watch: bool = False) -> None:
    project_name, project = get_project(project_name)
    root = expand(project["knowledge_dir"])
    configured = list(project.get("ingest_ignored", []))
    collection = str(project.get("collection") or project_name)
    print(f"[ingest] project={project_name} collection={collection} root={root}")
    with _prepared_ingest(root, configured, watch=watch) as (
        ingest_root,
        ignored,
        collisions,
    ):
        if collisions and watch:
            print(
                "[ingest] warning: watched ingestion uses basename ignores for "
                "zero-byte collision(s): "
                + ", ".join(collisions)
            )
        elif collisions:
            print(
                "[ingest] using a temporary filtered staging tree for zero-byte "
                "basename collision(s): "
                + ", ".join(collisions)
            )
        subprocess.run(
            _ingest_command(ingest_root, ignored, watch, collection),
            cwd=cfg_path("private_gpt_dir"),
            env=privategpt_env(),
            check=False,
        )


def resolve_knowledge_directory(value: str) -> Path:
    if not value or not value.strip():
        raise ValueError("A folder path is required")
    root = expand(value.strip())
    if not root.exists():
        raise ValueError(f"Folder does not exist: {root}")
    if not root.is_dir():
        raise ValueError(f"Path is not a directory: {root}")
    if root == Path(root.anchor):
        raise ValueError("Refusing to ingest a filesystem root")
    home = Path.home().resolve()
    if root in {home, home.parent}:
        raise ValueError("Refusing to ingest a home-directory root")
    pgpt_home = cfg_path("pgpt_home")
    if root == pgpt_home or pgpt_home in root.parents:
        raise ValueError("Refusing to ingest PrivateGPT runtime data")
    if any(root == base or base in root.parents for base in _SYSTEM_ROOTS):
        raise ValueError("Refusing to ingest a system directory")
    if any(part.casefold() in _SENSITIVE_NAMES for part in root.parts):
        raise ValueError("Refusing to ingest a sensitive credentials directory")
    if not os.access(root, os.R_OK | os.X_OK):
        raise ValueError(f"Folder is not readable: {root}")
    return root


def ingest_directory(
    path: str,
    *,
    project_name: str,
    collection: str | None = None,
    ignored: list[str] | None = None,
    on_line: Callable[[str], None] | None = None,
) -> int:
    """Register and ingest a user-selected folder without changing PrivateGPT source."""
    normalized = validate_user_project_name(project_name)
    root = resolve_knowledge_directory(path)
    configured = list(ignored or [])
    target_collection = collection or normalized
    with _prepared_ingest(root, configured) as (
        ingest_root,
        ignore_names,
        collisions,
    ):
        if collisions and on_line is not None:
            on_line(
                "[pgpt] using a temporary filtered staging tree for zero-byte "
                "basename collision(s): "
                + ", ".join(collisions)
            )
        proc = subprocess.Popen(
            _ingest_command(ingest_root, ignore_names, False, target_collection),
            cwd=cfg_path("private_gpt_dir"),
            env=privategpt_env(),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert proc.stdout is not None
        for raw in proc.stdout:
            line = _redact(raw.rstrip("\n"))
            if on_line is not None:
                on_line(line)
        code = proc.wait()

    if code == 0:
        save_user_project(normalized, str(root), collection=target_collection)
    return code


def _redact(line: str) -> str:
    patterns = [
        (r"(PGPT_BRAVE_API_KEY\s*=\s*)\S+", r"\1***REDACTED***"),
        (r"(X-Subscription-Token['\":=\s]+)\S+", r"\1***REDACTED***"),
        (r"(Authorization['\":=\s]+(?:Bearer\s+)?)\S+", r"\1***REDACTED***"),
        (r"(api_key\s*=\s*['\"])[^'\"]*(['\"])", r"\1***REDACTED***\2"),
    ]
    for pattern, replacement in patterns:
        line = re.sub(pattern, replacement, line, flags=re.I)
    return line


def serve() -> None:
    cmd = ["uv", "run", "private-gpt", "serve", "--host", "127.0.0.1"]
    proc = subprocess.Popen(
        cmd,
        cwd=cfg_path("private_gpt_dir"),
        env=privategpt_env(),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    try:
        assert proc.stdout is not None
        for line in proc.stdout:
            print(_redact(line), end="")
    except KeyboardInterrupt:
        proc.terminate()
    finally:
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
