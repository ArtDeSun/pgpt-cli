from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path


RULES_PATH = Path(__file__).resolve().parents[2] / "prompts" / "routing" / "rules.txt"


@lru_cache(maxsize=1)
def _load_rules() -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current: str | None = None

    for raw in RULES_PATH.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue

        if line.startswith("[") and line.endswith("]"):
            current = line[1:-1].strip()
            if not current:
                raise ValueError("Empty routing rule section")
            sections.setdefault(current, [])
            continue

        if current is None:
            raise ValueError("Routing rule found before a section")
        sections[current].append(line)

    return sections


@lru_cache(maxsize=None)
def load_rule(name: str) -> re.Pattern[str]:
    patterns = _load_rules().get(name)
    if not patterns:
        raise KeyError(f"Unknown or empty routing rule: {name}")

    combined = "|".join(f"(?:{pattern})" for pattern in patterns)
    return re.compile(combined, re.IGNORECASE)
