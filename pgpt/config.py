from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config.json"


def expand(value: str) -> Path:
    return Path(os.path.expanduser(value)).resolve()


def load_config() -> dict[str, Any]:
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


CONFIG = load_config()


def cfg_path(name: str) -> Path:
    return expand(CONFIG["paths"][name])


def get_project(name: str | None = None) -> tuple[str, dict[str, Any]]:
    project_name = name or CONFIG["defaults"]["project"]
    try:
        return project_name, CONFIG["projects"][project_name]
    except KeyError as exc:
        raise SystemExit(f"Unknown project: {project_name}") from exc


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
