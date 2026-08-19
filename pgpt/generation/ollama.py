from __future__ import annotations

from typing import Any, Callable

from pgpt.config import CONFIG
from pgpt.runtime.http import json_request, ndjson_request


def ollama_url(path: str) -> str:
    return CONFIG["endpoints"]["ollama"].rstrip("/") + path


def list_models() -> list[str]:
    data = json_request("GET", ollama_url("/api/tags"), timeout=3)
    return [str(row.get("name")) for row in (data or {}).get("models", [])]


def stream_chat(
    *,
    model: str,
    messages: list[dict[str, str]],
    on_text: Callable[[str], None],
    max_tokens: int,
    num_ctx: int,
    temperature: float,
) -> dict[str, Any]:
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "think": False,
        "keep_alive": CONFIG["performance"].get("final_keep_alive", "10m"),
        "options": {
            "temperature": temperature,
            "num_ctx": num_ctx,
            "num_predict": max_tokens,
        },
    }

    final: dict[str, Any] = {}
    for chunk in ndjson_request(
        ollama_url("/api/chat"),
        payload=payload,
        timeout=float(CONFIG["performance"].get("request_timeout_seconds", 300)),
    ):
        content = str((chunk.get("message") or {}).get("content") or "")
        if content:
            on_text(content)
        if chunk.get("done"):
            final = chunk

    keys = (
        "done_reason",
        "load_duration",
        "prompt_eval_duration",
        "prompt_eval_count",
        "eval_duration",
        "eval_count",
        "total_duration",
    )
    return {key: final.get(key, 0) for key in keys}
