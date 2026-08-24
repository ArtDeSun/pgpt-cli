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
_GENERATED_NAMES = {
    ".git",
    ".next",
    ".venv",
    "__pycache__",
    "build",
    "coverage",
    "dist",
    "node_modules",
    "venv",
}
_GENERATED_SUFFIXES = {".pyc", ".pyo"}
_SYSTEM_ROOTS = tuple(Path(value) for value in ("/etc", "/proc", "/sys", "/dev", "/boot"))
_INGEST_HELPER = Path(__file__).resolve().with_name("privategpt_ingest.py")


def _reachable(url: str, timeout: float = 1.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout):
            return True
    except Exception:
        return False


def _privategpt_models_url() -> str:
    return CONFIG["endpoints"]["private_gpt"].rstrip("/") + "/v1/models"


def privategpt_source_info() -> dict[str, object]:
    """Describe the PrivateGPT source checkout without treating it as context."""
    root = cfg_path("private_gpt_dir")
    required = (
        root / "pyproject.toml",
        root / "private_gpt" / "di.py",
        root / "private_gpt" / "server" / "ingest" / "ingest_service.py",
    )
    missing = [str(path.relative_to(root)) for path in required if not path.is_file()]
    compatible = not missing
    reason = "ready" if compatible else "missing: " + ", ".join(missing)

    if compatible:
        try:
            di_text = required[1].read_text(encoding="utf-8")
        except OSError as exc:
            compatible = False
            reason = f"cannot read private_gpt/di.py: {exc}"
        else:
            if "def get_injector(" not in di_text and "def get_global_injector(" not in di_text:
                compatible = False
                reason = "unsupported injector API"

    commit: str | None = None
    if compatible and (root / ".git").exists():
        try:
            completed = subprocess.run(
                ["git", "-C", str(root), "rev-parse", "--short=12", "HEAD"],
                check=False,
                capture_output=True,
                text=True,
                timeout=1,
            )
            if completed.returncode == 0:
                commit = completed.stdout.strip() or None
        except (OSError, subprocess.TimeoutExpired):
            pass

    return {
        "path": str(root),
        "exists": root.is_dir(),
        "compatible": compatible,
        "reason": reason,
        "commit": commit,
    }


def _require_privategpt_checkout() -> Path:
    info = privategpt_source_info()
    if not info["compatible"]:
        raise RuntimeError(
            "PrivateGPT source checkout is not ready at "
            f"{info['path']}: {info['reason']}. Use a clean current checkout before "
            "running PrivateGPT indexing or `pgpt serve`."
        )
    return Path(str(info["path"]))


def _ensure_privategpt_stopped_for_local_ingest() -> None:
    if _reachable(_privategpt_models_url(), timeout=0.25):
        raise RuntimeError(
            "PrivateGPT is already running. Stop `pgpt serve` before local folder "
            "ingestion so the ingestion helper and server do not open the same "
            "file-backed Qdrant state concurrently."
        )


def status() -> None:
    ollama = CONFIG["endpoints"]["ollama"].rstrip("/") + "/api/tags"
    private_gpt = _privategpt_models_url()
    server = CONFIG.get("server", {})
    host = str(server.get("host", "127.0.0.1"))
    port = int(server.get("port", 8765))
    local_api = f"http://{host}:{port}/health"
    source = privategpt_source_info()
    revision = f" @ {source['commit']}" if source.get("commit") else ""
    source_state = "ready" if source["compatible"] else f"NOT ready ({source['reason']})"
    private_cfg = CONFIG.get("private_gpt", {})
    embedding = private_cfg.get("embedding_model", "auto")

    print(f"Ollama:             {'reachable' if _reachable(ollama) else 'NOT reachable'}")
    print(f"pgpt API:           {'reachable' if _reachable(local_api) else 'NOT reachable'}")
    print(f"PrivateGPT API:     {'reachable' if _reachable(private_gpt) else 'NOT reachable'}")
    print(f"PrivateGPT source:  {source_state} · {source['path']}{revision}")
    print(f"PrivateGPT data:    {cfg_path('pgpt_home')} (generated runtime only)")
    print(f"PrivateGPT embed:   {embedding}")
    print(f"Context registry:   {cfg_path('projects_file')}")


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
    """Return sensitive or generated basenames that must not enter an index."""
    ignored = {*_SENSITIVE_NAMES, *_GENERATED_NAMES}
    runtime_root = cfg_path("pgpt_home")
    if runtime_root == root or root in runtime_root.parents:
        ignored.add(runtime_root.name)

    for directory, directory_names, file_names in os.walk(root, followlinks=False):
        directory_names[:] = [
            name
            for name in directory_names
            if name not in ignored and not (Path(directory) / name).is_symlink()
        ]
        for name in file_names:
            path = Path(directory) / name
            if path.is_symlink():
                continue
            folded = name.casefold()
            if folded == ".env" or folded.startswith(".env."):
                ignored.add(name)
            if path.suffix.casefold() in _SECRET_SUFFIXES | _GENERATED_SUFFIXES:
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


def _collection_name(value: object | None, fallback: str) -> str:
    candidate = fallback if value is None else value
    if not isinstance(candidate, str):
        raise ValueError("Collection must be a string")
    candidate = candidate.strip()
    if not candidate or len(candidate) > 255:
        raise ValueError("Collection must contain 1 to 255 characters")
    return candidate


def _privategpt_runtime_paths() -> dict[str, Path]:
    root = cfg_path("pgpt_home")
    return {
        "root": root,
        "venv": root / "venv",
        "data": root / "private_gpt",
        "qdrant": root / "qdrant",
        "volumes": root / "volumes",
    }


def _prepare_privategpt_runtime() -> dict[str, Path]:
    paths = _privategpt_runtime_paths()
    paths["root"].mkdir(parents=True, exist_ok=True)
    for name in ("data", "qdrant", "volumes"):
        paths[name].mkdir(parents=True, exist_ok=True)
    return paths


def privategpt_env() -> dict[str, str]:
    load_secrets()
    env = os.environ.copy()
    api_base = CONFIG["endpoints"]["openai_api_base"]
    runtime = _prepare_privategpt_runtime()
    private_cfg = CONFIG.get("private_gpt", {})
    embedding_model = str(private_cfg.get("embedding_model", "")).strip()
    embed_dim = private_cfg.get("embed_dim")

    env["OPENAI_API_BASE"] = api_base
    if not env.get("OPENAI_EMBEDDING_API_BASE"):
        env["OPENAI_EMBEDDING_API_BASE"] = api_base
    if embedding_model:
        env.setdefault("PGPT_EMBEDDING_DEFAULT", embedding_model)
    if embed_dim:
        env.setdefault("PGPT_EMBED_DIM", str(embed_dim))
    env["UV_PROJECT_ENVIRONMENT"] = str(runtime["venv"])
    env["PGPT_LOCAL_DATA_FOLDER"] = str(runtime["data"])
    env["PGPT_QDRANT_PATH"] = str(runtime["qdrant"])
    env["PGPT_CODE_EXECUTION_VOLUME_ROOT"] = str(runtime["volumes"])
    return env


def _uv_privategpt_prefix() -> list[str]:
    # --frozen guarantees pgpt never rewrites the PrivateGPT source lockfile.
    return ["uv", "run", "--frozen", "--python", "3.11", "--extra", "core"]


def _ingest_command(
    root: Path,
    ignored: list[str],
    watch: bool,
    collection: str,
) -> list[str]:
    cmd = [
        *_uv_privategpt_prefix(),
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
    collection = _collection_name(project.get("collection"), project_name)
    private_gpt_dir = _require_privategpt_checkout()
    _ensure_privategpt_stopped_for_local_ingest()
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
        completed = subprocess.run(
            _ingest_command(ingest_root, ignored, watch, collection),
            cwd=private_gpt_dir,
            env=privategpt_env(),
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                f"PrivateGPT ingestion failed with exit code {completed.returncode}"
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
    target_collection = _collection_name(collection, normalized)
    private_gpt_dir = _require_privategpt_checkout()
    _ensure_privategpt_stopped_for_local_ingest()
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
            cwd=private_gpt_dir,
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
    private_gpt_dir = _require_privategpt_checkout()
    cmd = [
        *_uv_privategpt_prefix(),
        "private-gpt",
        "serve",
        "--host",
        "127.0.0.1",
    ]
    proc = subprocess.Popen(
        cmd,
        cwd=private_gpt_dir,
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
