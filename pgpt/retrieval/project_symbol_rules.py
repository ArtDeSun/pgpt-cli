from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


RULES_PATH = Path(__file__).resolve().parents[2] / "prompts" / "retrieval" / "project-symbols.json"


@lru_cache(maxsize=1)
def project_symbol_rules() -> dict[str, Any]:
    data = json.loads(RULES_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError("project-symbols.json must contain an object")
    return data


def max_candidates() -> int:
    return int(project_symbol_rules().get("max_candidates", 12))


def minimum_project_definition_score() -> int:
    return int(project_symbol_rules().get("minimum_project_definition_score", 90))


def looks_like_project_symbol(value: str) -> bool:
    if not value:
        return False

    rules = project_symbol_rules().get("identifier_shapes", {})
    if value.isupper() and any(c.isalpha() for c in value):
        return bool(rules.get("allow_all_uppercase", False))
    if "_" in value and rules.get("allow_snake_case", True):
        return True
    if "$" in value and rules.get("allow_dollar_identifiers", True):
        return True

    mixed = any(c.islower() for c in value) and any(c.isupper() for c in value[1:])
    return bool(rules.get("allow_mixed_case", True) and mixed)


def _lexical() -> dict[str, Any]:
    return project_symbol_rules().get("lexical", {})


def lexical_minimum_term_length() -> int:
    return int(_lexical().get("minimum_term_length", 4))


def lexical_max_terms() -> int:
    return int(_lexical().get("max_terms", 20))


def lexical_stop_words() -> set[str]:
    return {str(value).casefold() for value in _lexical().get("stop_words", [])}
