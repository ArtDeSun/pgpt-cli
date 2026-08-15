from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path


def _rules_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "prompts"
        / "routing"
        / "rules.txt"
    )


@lru_cache(maxsize=1)
def _load_rules() -> dict[
    str,
    list[str],
]:
    sections: dict[
        str,
        list[str],
    ] = {}

    current: str | None = None

    for raw_line in _rules_path().read_text(
        encoding="utf-8"
    ).splitlines():
        line = raw_line.strip()

        if not line:
            continue

        if line.startswith("#"):
            continue

        if (
            line.startswith("[")
            and line.endswith("]")
        ):
            current = line[1:-1].strip()

            if not current:
                raise ValueError(
                    "Empty routing rule section name"
                )

            sections.setdefault(
                current,
                [],
            )

            continue

        if current is None:
            raise ValueError(
                "Routing rule found before any section"
            )

        sections[current].append(
            line
        )

    return sections


@lru_cache(maxsize=None)
def load_rule(
    name: str,
) -> re.Pattern[str]:
    sections = _load_rules()

    patterns = sections.get(
        name
    )

    if not patterns:
        raise KeyError(
            f"Unknown or empty routing rule: {name}"
        )

    combined = "|".join(
        f"(?:{pattern})"
        for pattern in patterns
    )

    return re.compile(
        combined,
        re.IGNORECASE,
    )