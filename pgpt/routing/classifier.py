from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pgpt.config import CONFIG
from pgpt.generation.ollama import ollama_url
from pgpt.runtime.http import json_request


WebNeed = Literal["yes", "no", "unknown"]

_WEB_NEED_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "needs_web": {
            "type": "string",
            "enum": ["yes", "no", "unknown"],
        }
    },
    "required": ["needs_web"],
    "additionalProperties": False,
}


@lru_cache(maxsize=1)
def _system_prompt() -> str:
    path = Path(__file__).resolve().parents[2] / "prompts" / "routing" / "web-need.md"
    return path.read_text(encoding="utf-8").strip()


def _router_model() -> str:
    return os.environ.get("PGPT_ROUTER_MODEL", str(CONFIG["models"]["router"]))


def classify_web_need(prompt: str) -> WebNeed:
    """Return whether an ambiguous request needs current public data."""
    payload = {
        "model": _router_model(),
        "messages": [
            {"role": "system", "content": _system_prompt()},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "think": False,
        "format": _WEB_NEED_SCHEMA,
        "keep_alive": "5m",
        "options": {
            "temperature": 0.0,
            "num_ctx": 1024,
            "num_predict": 16,
        },
    }

    try:
        response = json_request(
            "POST",
            ollama_url("/api/chat"),
            payload=payload,
            timeout=float(CONFIG["performance"].get("request_timeout_seconds", 180)),
        )
        content = str(((response or {}).get("message") or {}).get("content") or "").strip()
        value = json.loads(content).get("needs_web")
    except Exception:
        return "unknown"

    return value if value in {"yes", "no", "unknown"} else "unknown"
