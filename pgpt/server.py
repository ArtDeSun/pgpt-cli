from __future__ import annotations

import contextlib
import io
import json
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import unquote, urlsplit

from pgpt.config import CONFIG, cfg_path, project_names
from pgpt.generation.ollama import list_models
from pgpt.maintenance import ingest_directory
from pgpt.retrieval.web import connectivity_ok
from pgpt.retrieval.web_usage import usage_snapshot
from pgpt.runtime.pipeline import PipelineResult, run
from pgpt.skills import list_skills, skill_history

ROOT = Path(__file__).resolve().parents[1]
WEB_INDEX_PATH = ROOT / "web" / "index.html"
_PIPELINE_LOCK = threading.Lock()

class _ClientDisconnected(Exception):
    pass

@dataclass(frozen=True)
class PreparedRequest:
    prompt: str
    history: list[dict[str, str]]
    project: str | None
    web: str | None
    context: bool | None
    template: str | None
    model: str | None
    deep: bool | None
    history_mode: str | None
    answer_length: str | None

def _web_override(value: Any) -> str | None:
    if value in {None, "auto"}: return None
    mapping = {"on": "lookup", "lookup": "lookup", "research": "research", "off": "off"}
    try: return mapping[str(value)]
    except KeyError as exc: raise ValueError(f"Invalid web mode: {value!r}") from exc

def _text_content(value: Any) -> str:
    if isinstance(value, str): return value
    if isinstance(value, list):
        parts = [item["text"] for item in value if isinstance(item, dict) and item.get("type") == "text" and isinstance(item.get("text"), str)]
        if parts: return "\n".join(parts)
    raise ValueError("Only text chat messages are supported")

def _extract_messages(payload: dict[str, Any]) -> tuple[str, list[dict[str, str]]]:
    messages = payload.get("messages")
    if not isinstance(messages, list) or not messages: raise ValueError("messages must be a non-empty list")
    normalized: list[dict[str, str]] = []
    for message in messages:
        if not isinstance(message, dict): raise ValueError("Each message must be an object")
        role = message.get("role")
        if role in {"system", "user", "assistant"}: normalized.append({"role": str(role), "content": _text_content(message.get("content"))})
    user_indexes = [i for i, message in enumerate(normalized) if message["role"] == "user"]
    if not user_indexes: raise ValueError("At least one user message is required")
    last_user = user_indexes[-1]; history = normalized[:last_user]
    conversation = [message for message in history if message["role"] != "system"]
    system_messages = [message for message in history if message["role"] == "system"]
    return normalized[last_user]["content"], [*conversation, *system_messages]

def _optional_string(options: dict[str, Any], name: str) -> str | None:
    value = options.get(name)
    if value in {None, ""}: return None
    if not isinstance(value, str): raise ValueError(f"pgpt.{name} must be a string")
    return value

def _optional_bool(options: dict[str, Any], name: str) -> bool | None:
    value = options.get(name)
    if value is None: return None
    if not isinstance(value, bool): raise ValueError(f"pgpt.{name} must be a boolean")
    return value

def _choice(options: dict[str, Any], name: str, allowed: set[str]) -> str | None:
    value = _optional_string(options, name)
    if value in {None, "auto"}: return None
    if value not in allowed: raise ValueError(f"Invalid pgpt.{name}: {value!r}")
    return value

def _prepare_request(payload: dict[str, Any]) -> PreparedRequest:
    prompt, history = _extract_messages(payload); options = payload.get("pgpt", {}) or {}
    if not isinstance(options, dict): raise ValueError("pgpt options must be an object")
    skill = _optional_string(options, "skill")
    return PreparedRequest(prompt=prompt, history=skill_history(history, skill), project=_optional_string(options, "project"), web=_web_override(options.get("web")), context=_optional_bool(options, "context"), template=_choice(options, "template", {"general", "research", "explain-code", "debug", "implement", "architecture"}), model=_optional_string(options, "model"), deep=_optional_bool(options, "deep"), history_mode=_choice(options, "history_mode", {"auto", "full", "off"}), answer_length=_choice(options, "answer_length", {"auto", "short", "standard", "long"}))

def _run_request(request: PreparedRequest, *, on_chunk: Callable[[str], None] | None = None, on_replace: Callable[[str], None] | None = None, on_status: Callable[[str, str, float, bool], None] | None = None) -> PipelineResult:
    with _PIPELINE_LOCK:
        sink = io.StringIO()
        with contextlib.redirect_stdout(sink):
            return run(request.prompt, project_name=request.project, web_override=request.web, project_override=request.context, template_override=request.template, model_override=request.model, deep_override=request.deep, history=request.history, history_mode=request.history_mode, answer_length=request.answer_length, echo_route=False, on_chunk=on_chunk, on_replace=on_replace, on_status=on_status)

def _route_payload(route: Any) -> dict[str, Any]:
    value = {"execution": getattr(route, "execution", None), "template": getattr(route, "template", None), "model": getattr(route, "model", None), "deep": getattr(route, "deep", None), "project": getattr(route, "project", None), "reason": getattr(route, "reason", None)}
    decision = getattr(route, "decision", None)
    if decision is not None:
        value["decision"] = {"source": getattr(decision, "source", None), "web_mode": getattr(decision, "web_mode", None), "task": getattr(decision, "task", None), "freshness": getattr(decision, "freshness", None), "project_evidence": getattr(decision, "project_evidence", None), "reason": getattr(decision, "reason", None)}
    return value

def _timing_payload(timing: Any) -> dict[str, Any]:
    return {"total_seconds": round(float(getattr(timing, "total", 0.0)), 3), "phases": {str(k): round(float(v), 3) for k, v in dict(getattr(timing, "phases", {})).items()}, "metrics": dict(getattr(timing, "metrics", {}))}

def _result_metadata(result: PipelineResult) -> dict[str, Any]:
    return {"route": _route_payload(result.route), "timing": _timing_payload(result.timing), "response_path": str(result.response_path)}

def _completion(payload: dict[str, Any]) -> dict[str, Any]:
    result = _run_request(_prepare_request(payload))
    return {"id": f"chatcmpl-{uuid.uuid4().hex}", "object": "chat.completion", "created": int(time.time()), "model": "pgpt-cli", "choices": [{"index": 0, "message": {"role": "assistant", "content": result.answer}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}, "pgpt": _result_metadata(result)}

def _stream_chunk(completion_id: str, created: int, *, content: str | None = None, finish_reason: str | None = None, pgpt: dict[str, Any] | None = None) -> dict[str, Any]:
    chunk: dict[str, Any] = {"id": completion_id, "object": "chat.completion.chunk", "created": created, "model": "pgpt-cli", "choices": [{"index": 0, "delta": {"content": content} if content is not None else {}, "finish_reason": finish_reason}]}
    if pgpt is not None: chunk["pgpt"] = pgpt
    return chunk

def _sse(value: Any) -> bytes:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return f"data: {text}\n\n".encode("utf-8")

def _response_root() -> Path: return cfg_path("responses_dir")
def _response_metadata(path: Path) -> dict[str, Any]:
    stat = path.stat(); return {"name": path.name, "size": stat.st_size, "modified": datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(timespec="seconds")}
def _list_responses() -> list[dict[str, Any]]:
    root = _response_root()
    if not root.exists(): return []
    limit = int(CONFIG.get("server", {}).get("response_list_limit", 100)); paths = sorted((p for p in root.glob("*.md") if p.is_file()), key=lambda p: p.stat().st_mtime, reverse=True)
    return [_response_metadata(path) for path in paths[:limit]]
def _safe_response_path(name: str) -> Path:
    decoded = unquote(name)
    if not decoded or decoded != Path(decoded).name or not decoded.endswith(".md"): raise ValueError("Invalid response filename")
    path = _response_root() / decoded
    if not path.exists(): raise FileNotFoundError(decoded)
    return path

def _web_usage_payload() -> dict[str, Any]:
    snapshot = usage_snapshot(); snapshot["online"] = connectivity_ok(); return snapshot

def _available_models() -> list[str]:
    try: return list_models()
    except Exception: return []

def _meta() -> dict[str, Any]:
    return {"name": "pgpt-cli", "projects": project_names(), "default_project": CONFIG.get("defaults", {}).get("project"), "skills": list_skills(), "models": _available_models(), "server_time": datetime.now().astimezone().isoformat(timespec="seconds")}

def _loopback_origin(value: str | None) -> str | None:
    if not value: return None
    try: parsed = urlsplit(value)
    except ValueError: return None
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}: return None
    return value

class PgptHandler(BaseHTTPRequestHandler):
    server_version = "pgpt-cli"; protocol_version = "HTTP/1.1"
    def _cors(self) -> None:
        origin = _loopback_origin(self.headers.get("Origin"))
        if origin is not None: self.send_header("Access-Control-Allow-Origin", origin); self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization"); self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    def _json(self, status: int, value: Any) -> None:
        body = json.dumps(value, ensure_ascii=False).encode("utf-8"); self.send_response(status); self.send_header("Content-Type", "application/json; charset=utf-8"); self.send_header("Content-Length", str(len(body))); self._cors(); self.end_headers(); self.wfile.write(body)
    def _bytes(self, status: int, body: bytes, content_type: str, *, headers: dict[str, str] | None = None) -> None:
        self.send_response(status); self.send_header("Content-Type", content_type); self.send_header("Content-Length", str(len(body)))
        for key, value in (headers or {}).items(): self.send_header(key, value)
        self._cors(); self.end_headers(); self.wfile.write(body)
    def _payload(self) -> dict[str, Any]:
        try: length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc: raise ValueError("Invalid Content-Length") from exc
        if length <= 0: return {}
        if length > int(CONFIG.get("server", {}).get("max_request_bytes", 2_000_000)): raise ValueError("Request body is too large")
        value = json.loads(self.rfile.read(length).decode("utf-8"))
        if not isinstance(value, dict): raise ValueError("Request body must be a JSON object")
        return value
    def _write_sse(self, value: Any) -> bool:
        try: self.wfile.write(_sse(value)); self.wfile.flush(); return True
        except (BrokenPipeError, ConnectionResetError, OSError): return False
    def _stream(self, payload: dict[str, Any]) -> None:
        request = _prepare_request(payload); completion_id = f"chatcmpl-{uuid.uuid4().hex}"; created = int(time.time()); connected = True
        self.send_response(HTTPStatus.OK); self.send_header("Content-Type", "text/event-stream; charset=utf-8"); self.send_header("Cache-Control", "no-cache"); self.send_header("Connection", "close"); self._cors(); self.end_headers(); self.close_connection = True
        def send(value: Any) -> bool:
            nonlocal connected
            if connected: connected = self._write_sse(value)
            return connected
        send(_stream_chunk(completion_id, created, pgpt={"event": "start"}))
        def on_chunk(text: str) -> None:
            if not send(_stream_chunk(completion_id, created, content=text)): raise _ClientDisconnected()
        def on_replace(answer: str) -> None:
            if not send(_stream_chunk(completion_id, created, pgpt={"event": "replace", "content": answer})): raise _ClientDisconnected()
        def on_status(_frame: str, label: str, elapsed: float, completed: bool) -> None:
            send(_stream_chunk(completion_id, created, pgpt={"event": "status", "label": label, "elapsed": round(elapsed, 3), "completed": completed}))
        try:
            result = _run_request(request, on_chunk=on_chunk, on_replace=on_replace, on_status=on_status); send(_stream_chunk(completion_id, created, finish_reason="stop", pgpt={"event": "done", **_result_metadata(result)}))
        except _ClientDisconnected: return
        except Exception as exc: send(_stream_chunk(completion_id, created, finish_reason="stop", pgpt={"event": "error", "error": {"message": str(exc), "type": type(exc).__name__}}))
        send("[DONE]")
    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT); self._cors(); self.end_headers()
    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path in {"/health", "/api/health"}: self._json(HTTPStatus.OK, {"status": "ok", **_meta()})
        elif path == "/api/meta": self._json(HTTPStatus.OK, _meta())
        elif path == "/api/web-usage": self._json(HTTPStatus.OK, _web_usage_payload())
        elif path == "/api/responses": self._json(HTTPStatus.OK, {"responses": _list_responses()})
        elif path.startswith("/api/responses/"): self._get_response(path)
        elif path == "/v1/models": self._json(HTTPStatus.OK, {"object": "list", "data": [{"id": "pgpt-cli", "object": "model", "created": 0, "owned_by": "local"}]})
        elif path == "/":
            if WEB_INDEX_PATH.exists(): self._bytes(HTTPStatus.OK, WEB_INDEX_PATH.read_bytes(), "text/html; charset=utf-8")
            else: self._json(HTTPStatus.NOT_FOUND, {"error": "Web UI is not installed"})
        else: self._json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
    def _get_response(self, path: str) -> None:
        suffix = path[len("/api/responses/"):]; download = suffix.endswith("/download")
        if download: suffix = suffix[:-len("/download")]
        try: response_path = _safe_response_path(suffix)
        except ValueError as exc: self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)}); return
        except FileNotFoundError: self._json(HTTPStatus.NOT_FOUND, {"error": "Response not found"}); return
        if download: self._bytes(HTTPStatus.OK, response_path.read_bytes(), "text/markdown; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{response_path.name}"'}); return
        self._json(HTTPStatus.OK, {**_response_metadata(response_path), "content": response_path.read_text(encoding="utf-8")})
    def _ingest(self, payload: dict[str, Any]) -> None:
        path = payload.get("path"); name = payload.get("name"); collection = payload.get("collection") or None; ignored = payload.get("ignored", [])
        if not isinstance(path, str) or not isinstance(name, str): raise ValueError("name and path are required strings")
        if collection is not None and not isinstance(collection, str): raise ValueError("collection must be a string")
        if not isinstance(ignored, list) or any(not isinstance(value, str) for value in ignored): raise ValueError("ignored must be a list of strings")
        lines: list[str] = []; code = ingest_directory(path, project_name=name, collection=collection, ignored=ignored, on_line=lambda line: lines.append(line))
        if code != 0: raise RuntimeError(f"PrivateGPT ingestion failed with exit code {code}: " + " | ".join(lines[-5:]))
        self._json(HTTPStatus.OK, {"ok": True, "project": name.strip().casefold(), "lines": lines[-20:]})
    def do_POST(self) -> None:
        path = urlsplit(self.path).path
        try:
            payload = self._payload()
            if path == "/api/knowledge/ingest": self._ingest(payload); return
            if path != "/v1/chat/completions": self._json(HTTPStatus.NOT_FOUND, {"error": "Not found"}); return
            if payload.get("stream") is True: self._stream(payload)
            else: self._json(HTTPStatus.OK, _completion(payload))
        except (ValueError, json.JSONDecodeError) as exc: self._json(HTTPStatus.BAD_REQUEST, {"error": {"message": str(exc), "type": "invalid_request_error"}})
        except Exception as exc: self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": {"message": str(exc), "type": type(exc).__name__}})
    def log_message(self, format: str, *args: Any) -> None: return

def serve(*, host: str | None = None, port: int | None = None, allow_remote: bool = False) -> None:
    configured = CONFIG.get("server", {}); host = host or str(configured.get("host", "127.0.0.1")); port = int(port or configured.get("port", 8765))
    if host not in {"127.0.0.1", "localhost", "::1"} and not allow_remote: raise RuntimeError("Refusing a non-loopback bind without --allow-remote")
    server = ThreadingHTTPServer((host, port), PgptHandler); print(f"pgpt-cli UI:  http://{host}:{port}/"); print(f"OpenAI API:   http://{host}:{port}/v1"); print("Press Ctrl+C to stop.")
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()
