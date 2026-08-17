from __future__ import annotations

import contextlib
import io
import json
import threading
import time
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from pgpt.config import CONFIG
from pgpt.runtime.pipeline import run
from pgpt.skills import list_skills, skill_history


ROOT = Path(__file__).resolve().parents[1]
WEB_INDEX_PATH = ROOT / "web" / "index.html"
_PIPELINE_LOCK = threading.Lock()


def _web_override(value: Any) -> str | None:
    if value in {None, "auto"}:
        return None
    mapping = {
        "on": "lookup",
        "lookup": "lookup",
        "research": "research",
        "off": "off",
    }
    try:
        return mapping[str(value)]
    except KeyError as exc:
        raise ValueError(f"Invalid web mode: {value!r}") from exc


def _text_content(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "text" and isinstance(item.get("text"), str):
                parts.append(item["text"])
        if parts:
            return "\n".join(parts)
    raise ValueError("Only text chat messages are supported")


def _extract_messages(payload: dict[str, Any]) -> tuple[str, list[dict[str, str]]]:
    messages = payload.get("messages")
    if not isinstance(messages, list) or not messages:
        raise ValueError("messages must be a non-empty list")

    normalized: list[dict[str, str]] = []
    for message in messages:
        if not isinstance(message, dict):
            raise ValueError("Each message must be an object")
        role = message.get("role")
        if role not in {"system", "user", "assistant"}:
            continue
        normalized.append(
            {
                "role": str(role),
                "content": _text_content(message.get("content")),
            }
        )

    user_indexes = [
        index
        for index, message in enumerate(normalized)
        if message["role"] == "user"
    ]
    if not user_indexes:
        raise ValueError("At least one user message is required")

    last_user = user_indexes[-1]
    prompt = normalized[last_user]["content"]
    history = normalized[:last_user]
    return prompt, history


def _optional_string(options: dict[str, Any], name: str) -> str | None:
    value = options.get(name)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"pgpt.{name} must be a string")
    return value


def _optional_bool(options: dict[str, Any], name: str) -> bool | None:
    value = options.get(name)
    if value is None:
        return None
    if not isinstance(value, bool):
        raise ValueError(f"pgpt.{name} must be a boolean")
    return value


def _route_payload(route: Any) -> dict[str, Any]:
    value = {
        "execution": getattr(route, "execution", None),
        "template": getattr(route, "template", None),
        "model": getattr(route, "model", None),
        "deep": getattr(route, "deep", None),
        "project": getattr(route, "project", None),
        "reason": getattr(route, "reason", None),
    }
    decision = getattr(route, "decision", None)
    if decision is not None:
        value["decision"] = {
            "source": getattr(decision, "source", None),
            "web_mode": getattr(decision, "web_mode", None),
            "task": getattr(decision, "task", None),
            "freshness": getattr(decision, "freshness", None),
            "complexity": getattr(decision, "complexity", None),
            "project_evidence": getattr(decision, "project_evidence", None),
            "reason": getattr(decision, "reason", None),
        }
    return value


def _completion(payload: dict[str, Any]) -> dict[str, Any]:
    prompt, history = _extract_messages(payload)
    options = payload.get("pgpt", {})
    if options is None:
        options = {}
    if not isinstance(options, dict):
        raise ValueError("pgpt options must be an object")

    skill = _optional_string(options, "skill")
    project = _optional_string(options, "project")
    template = _optional_string(options, "template")
    model = _optional_string(options, "model")
    context_enabled = _optional_bool(options, "context")
    deep_enabled = _optional_bool(options, "deep")

    history = skill_history(history, skill)

    with _PIPELINE_LOCK:
        sink = io.StringIO()
        with contextlib.redirect_stdout(sink):
            result = run(
                prompt,
                project_name=project,
                web_override=_web_override(options.get("web")),
                project_override=context_enabled,
                template_override=template,
                model_override=model,
                deep_override=deep_enabled,
                history=history,
                echo_route=False,
            )

    created = int(time.time())
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex}",
        "object": "chat.completion",
        "created": created,
        "model": "pgpt-cli",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": result.answer,
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        },
        "pgpt": {
            "route": _route_payload(result.route),
            "response_path": str(result.response_path),
        },
    }


def _stream_body(completion: dict[str, Any]) -> bytes:
    choice = completion["choices"][0]
    chunk = {
        "id": completion["id"],
        "object": "chat.completion.chunk",
        "created": completion["created"],
        "model": completion["model"],
        "choices": [
            {
                "index": 0,
                "delta": {
                    "role": "assistant",
                    "content": choice["message"]["content"],
                },
                "finish_reason": None,
            }
        ],
    }
    finish = {
        "id": completion["id"],
        "object": "chat.completion.chunk",
        "created": completion["created"],
        "model": completion["model"],
        "choices": [
            {
                "index": 0,
                "delta": {},
                "finish_reason": "stop",
            }
        ],
    }
    text = (
        "data: " + json.dumps(chunk, ensure_ascii=False) + "\n\n"
        + "data: " + json.dumps(finish, ensure_ascii=False) + "\n\n"
        + "data: [DONE]\n\n"
    )
    return text.encode("utf-8")


def _meta() -> dict[str, Any]:
    return {
        "name": "pgpt-cli",
        "projects": sorted(CONFIG.get("projects", {})),
        "default_project": CONFIG.get("defaults", {}).get("project"),
        "skills": list_skills(),
    }


def _loopback_origin(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parsed = urlsplit(value)
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"}:
        return None
    if parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        return None
    return value


class PgptHandler(BaseHTTPRequestHandler):
    server_version = "pgpt-cli"

    def _cors(self) -> None:
        origin = _loopback_origin(self.headers.get("Origin"))
        if origin is not None:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

    def _json(self, status: int, value: Any) -> None:
        body = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _bytes(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _payload(self) -> dict[str, Any]:
        raw_length = self.headers.get("Content-Length", "0")
        try:
            length = int(raw_length)
        except ValueError as exc:
            raise ValueError("Invalid Content-Length") from exc
        if length <= 0:
            return {}
        maximum = int(
            CONFIG.get("server", {}).get(
                "max_request_bytes",
                2_000_000,
            )
        )
        if length > maximum:
            raise ValueError("Request body is too large")
        raw = self.rfile.read(length)
        value = json.loads(raw.decode("utf-8"))
        if not isinstance(value, dict):
            raise ValueError("Request body must be a JSON object")
        return value

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(HTTPStatus.NO_CONTENT)
        self._cors()
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path in {"/health", "/api/health"}:
            self._json(HTTPStatus.OK, {"status": "ok", **_meta()})
            return
        if path == "/api/meta":
            self._json(HTTPStatus.OK, _meta())
            return
        if path == "/v1/models":
            self._json(
                HTTPStatus.OK,
                {
                    "object": "list",
                    "data": [
                        {
                            "id": "pgpt-cli",
                            "object": "model",
                            "created": 0,
                            "owned_by": "local",
                        }
                    ],
                },
            )
            return
        if path == "/":
            if not WEB_INDEX_PATH.exists():
                self._json(
                    HTTPStatus.NOT_FOUND,
                    {"error": "Web UI is not installed"},
                )
                return
            self._bytes(
                HTTPStatus.OK,
                WEB_INDEX_PATH.read_bytes(),
                "text/html; charset=utf-8",
            )
            return
        self._json(HTTPStatus.NOT_FOUND, {"error": "Not found"})

    def do_POST(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path != "/v1/chat/completions":
            self._json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
            return
        try:
            payload = self._payload()
            completion = _completion(payload)
            if payload.get("stream") is True:
                body = _stream_body(completion)
                self._bytes(
                    HTTPStatus.OK,
                    body,
                    "text/event-stream; charset=utf-8",
                )
            else:
                self._json(HTTPStatus.OK, completion)
        except (ValueError, json.JSONDecodeError) as exc:
            self._json(
                HTTPStatus.BAD_REQUEST,
                {"error": {"message": str(exc), "type": "invalid_request_error"}},
            )
        except Exception as exc:
            self._json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"error": {"message": str(exc), "type": type(exc).__name__}},
            )

    def log_message(self, format: str, *args: Any) -> None:
        return


def serve(
    *,
    host: str | None = None,
    port: int | None = None,
    allow_remote: bool = False,
) -> None:
    configured = CONFIG.get("server", {})
    host = host or str(configured.get("host", "127.0.0.1"))
    port = int(port or configured.get("port", 8765))

    if host not in {"127.0.0.1", "localhost", "::1"} and not allow_remote:
        raise RuntimeError(
            "Refusing a non-loopback bind without --allow-remote"
        )

    server = ThreadingHTTPServer((host, port), PgptHandler)
    print(f"pgpt-cli UI:  http://{host}:{port}/")
    print(f"OpenAI API:   http://{host}:{port}/v1")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
