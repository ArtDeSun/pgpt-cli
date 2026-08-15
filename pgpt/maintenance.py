from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

from pgpt.config import CONFIG, cfg_path, expand, get_project, load_secrets
from pgpt.generation.ollama import list_models


def _reachable(url: str, timeout: float = 1.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout):
            return True
    except Exception:
        return False


def status() -> None:
    ollama = CONFIG["endpoints"]["ollama"].rstrip("/") + "/api/tags"
    pgpt = CONFIG["endpoints"]["private_gpt"].rstrip("/") + "/v1/models"
    print(f"Ollama:     {'reachable' if _reachable(ollama) else 'NOT reachable'}")
    print(f"PrivateGPT: {'reachable' if _reachable(pgpt) else 'NOT reachable'}")


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
    destination.mkdir(parents=True, exist_ok=True)

    cmd = ["rsync", "-a", "--delete"]
    for pattern in project.get("sync_excludes", []):
        cmd.append(f"--exclude={pattern}")
    cmd += [f"{source}/", f"{destination}/"]
    print(f"[sync] {project_name}: {source} -> {destination}")
    subprocess.run(cmd, check=True)


def _zero_byte_names(root: Path) -> list[str]:
    return sorted({p.name for p in root.rglob("*") if p.is_file() and p.stat().st_size == 0})


def privategpt_env() -> dict[str, str]:
    load_secrets()
    env = os.environ.copy()
    env["OPENAI_API_BASE"] = CONFIG["endpoints"]["openai_api_base"]
    env["PGPT_HOME"] = str(cfg_path("pgpt_home"))
    env["PGPT_PROFILES"] = ",".join(CONFIG.get("server", {}).get("profiles", ["model"]))
    return env


def ingest(project_name: str | None = None, watch: bool = False) -> None:
    project_name, project = get_project(project_name)
    root = expand(project["knowledge_dir"])
    zero = _zero_byte_names(root)
    if zero:
        print(f"[ingest] skipping {len(zero)} zero-byte basename(s):")
        for name in zero:
            print(f"  - {name}")

    ignored = list(dict.fromkeys([*project.get("ingest_ignored", []), *zero]))
    cmd = ["uv", "run", "python", "scripts/ingest_folder.py", str(root)]
    if ignored:
        cmd += ["--ignored", *ignored]
    if watch:
        cmd.append("--watch")
    print(f"[ingest] project={project_name}")
    subprocess.run(cmd, cwd=cfg_path("private_gpt_dir"), env=privategpt_env(), check=False)


def _redact(line: str) -> str:
    patterns = [
        (r"(PGPT_BRAVE_API_KEY\s*=\s*)\S+", r"\1***REDACTED***"),
        (r"(X-Subscription-Token['\":=\s]+)\S+", r"\1***REDACTED***"),
        (r"(Authorization['\":=\s]+(?:Bearer\s+)?)\S+", r"\1***REDACTED***"),
        (r"(api_key\s*=\s*['\"])[^'\"]*(['\"])", r"\1***REDACTED***\2"),
    ]
    for pattern, repl in patterns:
        line = re.sub(pattern, repl, line, flags=re.I)
    return line


def serve() -> None:
    cmd = ["uv", "run", "python", "-m", "private_gpt", "serve", "--host", "127.0.0.1"]
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
