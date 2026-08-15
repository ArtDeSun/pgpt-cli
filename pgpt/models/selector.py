from __future__ import annotations

from dataclasses import dataclass

from pgpt.generation.ollama import list_models

from pgpt.config import CONFIG


_TASK_MODELS: dict[str, tuple[str, ...]] = {
    "general": (
        "qwen3:1.7b",
        "qwen2.5-coder:3b",
        "llama3.2:3b",
    ),
    "research": (
        "qwen3:1.7b",
        "qwen2.5-coder:3b",
        "llama3.2:3b",
    ),
    "explain-code": (
        "qwen2.5-coder:3b",
        "llama3.2:3b",
        "qwen3:1.7b",
    ),
    "debug": (
        "llama3.2:3b",
        "qwen2.5-coder:3b",
        "qwen3:1.7b",
    ),
    "implement": (
        "qwen2.5-coder:3b",
        "llama3.2:3b",
        "qwen3:1.7b",
    ),
    "architecture": (
        "qwen2.5-coder:3b",
        "qwen3:1.7b",
        "llama3.2:3b",
    ),
}


@dataclass(frozen=True)
class ModelSelection:
    model: str
    reason: str

def _task_preferences(
    task: str,
) -> tuple[str, ...]:
    configured = (
        CONFIG.get(
            "models",
            {}
        )
        .get(
            "task_preferences",
            {}
        )
    )

    values = configured.get(
        task
    )

    if values is None:
        values = configured.get(
            "general",
            []
        )

    return tuple(
        str(value)
        for value in values
    )


def _resolve_available_name(
    requested: str,
    available: set[str],
) -> str | None:
    if requested in available:
        return requested

    # Ollama often reports an untagged request as
    # "<name>:latest".
    if ":" not in requested:
        latest = (
            f"{requested}:latest"
        )

        if latest in available:
            return latest

    return None


def select_model(
    task: str,
    *,
    model_override: str | None = None,
    available_models: set[str] | None = None,
) -> ModelSelection:
    available = (
        set(list_models())
        if available_models is None
        else set(available_models)
    )

    if model_override is not None:
        resolved = _resolve_available_name(
            model_override,
            available,
        )

        if resolved is None:
            raise RuntimeError(
                "Requested model is not available in Ollama: "
                f"{model_override}"
            )

        return ModelSelection(
            model=resolved,
            reason="explicit model override",
        )

    candidates = _task_preferences(
        task
    )

    if not candidates:
        raise RuntimeError(
            "No answer-model preferences are configured "
            f"for task={task!r}."
        )

    for candidate in candidates:
        resolved = _resolve_available_name(
            candidate,
            available,
        )

        if resolved is not None:
            return ModelSelection(
                model=resolved,
                reason=(
                    f"benchmark-preferred model for task={task}"
                ),
            )

    raise RuntimeError(
        "None of the configured answer models "
        f"for task={task!r} are available in Ollama."
    )
