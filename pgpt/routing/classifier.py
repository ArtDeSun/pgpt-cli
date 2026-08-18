from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from pgpt.config import CONFIG
from pgpt.generation.ollama import ollama_url
from pgpt.routing.types import (
    Complexity,
    Freshness,
    Task,
    WebMode,
)
from pgpt.runtime.http import json_request


@dataclass(frozen=True)
class ClassifierDecision:
    task: Task
    freshness: Freshness
    complexity: Complexity
    web_mode: WebMode | None = None


_ROUTE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "task": {
            "type": "string",
            "enum": [
                "general",
                "explain-code",
                "debug",
                "implement",
                "architecture",
                "research",
            ],
        },
        "time_scope": {
            "type": "string",
            "enum": [
                "moving",
                "fixed",
                "unknown",
            ],
        },
        "complexity": {
            "type": "string",
            "enum": [
                "simple",
                "standard",
                "complex",
            ],
        },
    },
    "required": [
        "task",
        "time_scope",
        "complexity",
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


def _chat_classifier(
    *,
    prompt: str,
    classifier_name: str,
    schema: dict[str, Any],
) -> dict[str, Any] | None:
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
            "num_predict": 48,
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

    return data


def classify_route_semantics(
    prompt: str,
) -> ClassifierDecision | None:
    try:
        data = _chat_classifier(
            prompt=prompt,
            classifier_name="route",
            schema=_ROUTE_SCHEMA,
        )

    except Exception:
        return None

    if data is None:
        return None

    task = data.get(
        "task"
    )
    time_scope = data.get(
        "time_scope"
    )
    complexity = data.get(
        "complexity"
    )

    if task not in {
        "general",
        "explain-code",
        "debug",
        "implement",
        "architecture",
        "research",
    }:
        return None

    freshness_by_scope: dict[str, Freshness] = {
        "moving": "current",
        "fixed": "stable",
        "unknown": "unknown",
    }

    if time_scope not in freshness_by_scope:
        return None

    if complexity not in {
        "simple",
        "standard",
        "complex",
    }:
        return None

    return ClassifierDecision(
        task=task,  # type: ignore[arg-type]
        freshness=freshness_by_scope[
            str(time_scope)
        ],
        complexity=complexity,  # type: ignore[arg-type]
    )


def classify_web_mode(
    prompt: str,
) -> WebMode | None:
    try:
        data = _chat_classifier(
            prompt=prompt,
            classifier_name="web-mode",
            schema=_WEB_MODE_SCHEMA,
        )

    except Exception:
        return None

    if data is None:
        return None

    value = data.get(
        "value"
    )

    if value in {
        "lookup",
        "research",
    }:
        return value  # type: ignore[return-value]

    return None


def classify_ambiguous_route(
    prompt: str,
) -> ClassifierDecision | None:
    return classify_route_semantics(
        prompt
    )
