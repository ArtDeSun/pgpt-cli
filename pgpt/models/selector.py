from __future__ import annotations

from dataclasses import dataclass

from pgpt.config import CONFIG
from pgpt.generation.ollama import list_models


@dataclass(frozen=True)
class ModelSelection:
    model: str
    reason: str


def _task_preferences(task: str) -> tuple[str, ...]:
    configured = CONFIG.get("models", {}).get("task_preferences", {})
    values = configured.get(task, configured.get("general", []))
    return tuple(str(value) for value in values)


def _resolve_name(requested: str, available: set[str]) -> str | None:
    if requested in available:
        return requested
    latest = f"{requested}:latest"
    return latest if ":" not in requested and latest in available else None


def select_model(
    task: str,
    *,
    model_override: str | None = None,
    available_models: set[str] | None = None,
) -> ModelSelection:
    available = set(list_models()) if available_models is None else set(available_models)

    if model_override is not None:
        resolved = _resolve_name(model_override, available)
        if resolved is None:
            raise RuntimeError(f"Requested model is not available in Ollama: {model_override}")
        return ModelSelection(resolved, "explicit model override")

    candidates = _task_preferences(task)
    if not candidates:
        raise RuntimeError(f"No answer-model preferences are configured for task={task!r}.")

    for candidate in candidates:
        resolved = _resolve_name(candidate, available)
        if resolved is not None:
            return ModelSelection(resolved, f"benchmark-preferred model for task={task}")

    raise RuntimeError(
        f"None of the configured answer models for task={task!r} are available in Ollama."
    )
