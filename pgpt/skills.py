from __future__ import annotations

import re
from pathlib import Path

from pgpt.config import CONFIG, ROOT, expand


_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
BUILTIN_SKILLS_DIR = ROOT / "skills"


def user_skills_dir() -> Path:
    configured = CONFIG.get("paths", {}).get(
        "skills_dir",
        "~/.config/pgpt/skills",
    )
    return expand(str(configured))


def _validate_name(name: str) -> str:
    value = name.strip().casefold()
    if not _NAME.fullmatch(value):
        raise ValueError(
            "Skill names may contain lowercase letters, numbers, "
            "and hyphens only"
        )
    return value


def _files(root: Path) -> dict[str, Path]:
    if not root.exists():
        return {}
    result: dict[str, Path] = {}
    for path in sorted(root.glob("*.md")):
        if path.name.casefold() == "readme.md":
            continue
        result[path.stem.casefold()] = path
    return result


def available_skills() -> dict[str, Path]:
    skills = _files(BUILTIN_SKILLS_DIR)
    skills.update(_files(user_skills_dir()))
    return skills


def list_skills() -> list[str]:
    return sorted(available_skills())


def load_skill(name: str) -> str:
    normalized = _validate_name(name)
    path = available_skills().get(normalized)
    if path is None:
        raise RuntimeError(f"Unknown skill: {normalized}")
    return path.read_text(encoding="utf-8").strip()


def create_skill(name: str) -> Path:
    normalized = _validate_name(name)
    root = user_skills_dir()
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{normalized}.md"
    if path.exists():
        raise RuntimeError(f"Skill already exists: {normalized}")
    path.write_text(f"# {normalized}\n\n", encoding="utf-8")
    return path


def skill_history(
    history: list[dict[str, str]] | None,
    skill: str | None,
) -> list[dict[str, str]]:
    base = list(history or [])
    if not skill:
        return base
    return [
        {
            "role": "system",
            "content": load_skill(skill),
        },
        *base,
    ]
