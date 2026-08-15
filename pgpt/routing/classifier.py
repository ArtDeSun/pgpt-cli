from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from pgpt.config import CONFIG
from pgpt.generation.ollama import ollama_url
from pgpt.runtime.http import json_request
from pgpt.routing.types import (
    Complexity,
    Freshness,
    Task,
    WebMode,
)


@dataclass(frozen=True)
class ClassifierDecision:
    task: Task
    freshness: Freshness
    complexity: Complexity
    web_mode: WebMode | None = None


_TASK_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "value": {
            "type": "string",
            "enum": [
                "general",
                "explain-code",
                "debug",
                "implement",
                "architecture",
                "research",
            ],
        }
    },
    "required": [
        "value",
    ],
    "additionalProperties": False,
}


_FRESHNESS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "value": {
            "type": "string",
            "enum": [
                "stable",
                "current",
                "unknown",
            ],
        }
    },
    "required": [
        "value",
    ],
    "additionalProperties": False,
}


_COMPLEXITY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "value": {
            "type": "string",
            "enum": [
                "simple",
                "standard",
                "complex",
            ],
        }
    },
    "required": [
        "value",
    ],
    "additionalProperties": False,
}


_WEB_MODE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "value": {
            "type": "string",
            "enum": [
                "lookup",
                "research",
            ],
        }
    },
    "required": [
        "value",
    ],
    "additionalProperties": False,
}


def _prompt_root() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "prompts"
        / "routing"
        / "classifiers"
    )


@lru_cache(maxsize=None)
def _load_prompt(
    name: str,
) -> str:
    path = (
        _prompt_root()
        / f"{name}.md"
    )

    return path.read_text(
        encoding="utf-8"
    ).strip()


@lru_cache(maxsize=1)
def _load_request_prompt() -> str:
    path = (
        Path(__file__).resolve().parents[2]
        / "prompts"
        / "routing"
        / "classifier-request.md"
    )

    return path.read_text(
        encoding="utf-8"
    ).strip()


def _classifier_request(
    prompt: str,
) -> str:
    return _load_request_prompt().format(
        prompt=prompt
    )


def _classify_one(
    *,
    prompt: str,
    classifier_name: str,
    schema: dict[str, Any],
    allowed: set[str],
) -> str | None:
    payload = {
        "model": CONFIG[
            "models"
        ][
            "roles"
        ][
            "router"
        ],
        "messages": [
            {
                "role": "system",
                "content": _load_prompt(
                    classifier_name
                ),
            },
            {
                "role": "user",
                "content": _classifier_request(
                    prompt
                ),
            },
        ],
        "stream": False,
        "think": False,
        "format": schema,
        "keep_alive": CONFIG[
            "performance"
        ].get(
            "final_keep_alive",
            "10m",
        ),
        "options": {
            "temperature": 0.0,
            "num_ctx": 1024,
            "num_predict": 30,
        },
    }

    response = json_request(
        "POST",
        ollama_url(
            "/api/chat"
        ),
        payload=payload,
        timeout=float(
            CONFIG[
                "performance"
            ].get(
                "request_timeout_seconds",
                180,
            )
        ),
    )

    if not isinstance(
        response,
        dict,
    ):
        return None

    message = response.get(
        "message"
    )

    if not isinstance(
        message,
        dict,
    ):
        return None

    content = str(
        message.get(
            "content"
        )
        or ""
    ).strip()

    if not content:
        return None

    try:
        data = json.loads(
            content
        )
    except json.JSONDecodeError:
        return None

    if not isinstance(
        data,
        dict,
    ):
        return None

    value = data.get(
        "value"
    )

    if value not in allowed:
        return None

    return str(
        value
    )


def classify_route_semantics(
    prompt: str,
) -> ClassifierDecision | None:
    """
    Classify semantic routing dimensions independently.

    Source selection is intentionally NOT performed here.
    The router derives source deterministically from explicit
    capabilities, project evidence, and freshness.
    """

    try:
        task = _classify_one(
            prompt=prompt,
            classifier_name="task",
            schema=_TASK_SCHEMA,
            allowed={
                "general",
                "explain-code",
                "debug",
                "implement",
                "architecture",
                "research",
            },
        )

        freshness = _classify_one(
            prompt=prompt,
            classifier_name="freshness",
            schema=_FRESHNESS_SCHEMA,
            allowed={
                "stable",
                "current",
                "unknown",
            },
        )

        complexity = _classify_one(
            prompt=prompt,
            classifier_name="complexity",
            schema=_COMPLEXITY_SCHEMA,
            allowed={
                "simple",
                "standard",
                "complex",
            },
        )

        if (
            task is None
            or freshness is None
            or complexity is None
        ):
            return None

        return ClassifierDecision(
            task=task,  # type: ignore[arg-type]
            freshness=freshness,  # type: ignore[arg-type]
            complexity=complexity,  # type: ignore[arg-type]
        )

    except Exception:
        return None


def classify_web_mode(
    prompt: str,
) -> WebMode | None:
    """
    Classify lookup vs research only after the router has
    already decided that web retrieval is required.
    """

    try:
        value = _classify_one(
            prompt=prompt,
            classifier_name="web-mode",
            schema=_WEB_MODE_SCHEMA,
            allowed={
                "lookup",
                "research",
            },
        )

    except Exception:
        return None

    if value in {
        "lookup",
        "research",
    }:
        return value  # type: ignore[return-value]

    return None


# Temporary compatibility alias while other code migrates.
def classify_ambiguous_route(
    prompt: str,
) -> ClassifierDecision | None:
    return classify_route_semantics(
        prompt
    )