from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


_RULES_PATH = (
    Path(__file__).resolve().parents[2]
    / "prompts"
    / "retrieval"
    / "project-symbols.json"
)


@lru_cache(maxsize=1)
def project_symbol_rules() -> dict[str, Any]:
    with _RULES_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:
        data = json.load(file)

    if not isinstance(
        data,
        dict,
    ):
        raise RuntimeError(
            "project-symbols.json must contain an object"
        )

    return data


def max_candidates() -> int:
    return int(
        project_symbol_rules().get(
            "max_candidates",
            12,
        )
    )


def minimum_project_definition_score() -> int:
    return int(
        project_symbol_rules().get(
            "minimum_project_definition_score",
            90,
        )
    )


def looks_like_project_symbol(
    value: str,
) -> bool:
    rules = (
        project_symbol_rules()
        .get(
            "identifier_shapes",
            {},
        )
    )

    if not value:
        return False

    has_lower = any(
        char.islower()
        for char in value
    )

    has_upper = any(
        char.isupper()
        for char in value
    )

    has_internal_upper = any(
        char.isupper()
        for char in value[1:]
    )

    is_all_upper = (
        value.isupper()
        and any(
            char.isalpha()
            for char in value
        )
    )

    if (
        is_all_upper
        and not rules.get(
            "allow_all_uppercase",
            False,
        )
    ):
        return False

    if (
        rules.get(
            "allow_snake_case",
            True,
        )
        and "_" in value
    ):
        return True

    if (
        rules.get(
            "allow_dollar_identifiers",
            True,
        )
        and "$" in value
    ):
        return True

    if (
        rules.get(
            "allow_mixed_case",
            True,
        )
        and has_lower
        and has_upper
        and has_internal_upper
    ):
        return True

    return False