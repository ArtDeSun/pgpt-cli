from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config.json"
_PROJECT_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


def expand(value: str) -> Path:
    path = Path(os.path.expanduser(value))
    if not path.is_absolute():
        path = ROOT / path
    return path.resolve()


def load_config() -> dict[str, Any]:
    with CONFIG_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


CONFIG = load_config()


def cfg_path(name: str) -> Path:
    return expand(CONFIG["paths"][name])


def _user_projects_path() -> Path:
    return cfg_path("projects_file")


def _load_user_projects() -> dict[str, dict[str, Any]]:
    path = _user_projects_path()
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {
        str(name): project
        for name, project in value.items()
        if isinstance(name, str) and isinstance(project, dict)
    } if isinstance(value, dict) else {}


def projects(*, include_hidden: bool = True) -> dict[str, dict[str, Any]]:
    merged = {str(name): dict(value) for name, value in CONFIG.get("projects", {}).items()}
    merged.update(_load_user_projects())
    if include_hidden:
        return merged
    return {name: value for name, value in merged.items() if not value.get("hidden")}


def project_names(*, include_hidden: bool = False) -> list[str]:
    return sorted(projects(include_hidden=include_hidden))


def get_project(name: str | None = None) -> tuple[str, dict[str, Any]]:
    project_name = name or CONFIG["defaults"]["project"]
    try:
        return project_name, projects()[project_name]
    except KeyError as exc:
        raise SystemExit(f"Unknown project: {project_name}") from exc


def save_user_project(name: str, source_dir: str, *, collection: str | None = None) -> dict[str, Any]:
    normalized = name.strip().casefold()
    if not _PROJECT_NAME.fullmatch(normalized):
        raise ValueError("Project names may contain lowercase letters, numbers, and hyphens only")
    if normalized in CONFIG.get("projects", {}):
        raise ValueError(f"Built-in project already exists: {normalized}")
    root = expand(source_dir)
    if not root.is_dir():
        raise ValueError(f"Project directory does not exist: {root}")
    entry = {
        "source_dir": str(root),
        "knowledge_dir": str(root),
        "collection": collection or normalized,
        "sync_excludes": [],
        "ingest_ignored": [],
        "sync_required": False,
        "user_managed": True,
    }
    path = _user_projects_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    current = _load_user_projects()
    current[normalized] = entry
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)
    return entry


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def load_secrets() -> None:
    path = CONFIG.get("paths", {}).get("secrets_file")
    if path:
        load_env_file(expand(path))
