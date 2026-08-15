from __future__ import annotations

from typing import Any, Callable

from pgpt.config import CONFIG
from pgpt.runtime.http import json_request, ndjson_request


def ollama_url(path: str) -> str:
    return CONFIG["endpoints"]["ollama"].rstrip("/") + path


def list_models() -> list[str]:
    data = json_request("GET", ollama_url("/api/tags"), timeout=3)
    return [str(x.get("name")) for x in (data or {}).get("models", [])]


def embed(inputs: str | list[str]) -> list[list[float]]:
    routing = CONFIG["routing"]
    result = json_request(
        "POST",
        ollama_url("/api/embed"),
        payload={
            "model": routing["embedding_model"],
            "input": inputs,
            "keep_alive": routing.get("embedding_keep_alive", "30m"),
        },
        timeout=float(routing.get("embedding_timeout_seconds", 20)),
    )
    vectors = result.get("embeddings") if isinstance(result, dict) else None
    if not vectors:
        raise RuntimeError("Ollama embedding endpoint returned no vectors")
    return vectors


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
    return {
        "done_reason": final.get("done_reason"),
        "load_duration": final.get("load_duration", 0),
        "prompt_eval_duration": final.get("prompt_eval_duration", 0),
        "prompt_eval_count": final.get("prompt_eval_count", 0),
        "eval_duration": final.get("eval_duration", 0),
        "eval_count": final.get("eval_count", 0),
        "total_duration": final.get("total_duration", 0),
    }
