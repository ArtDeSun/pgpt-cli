from __future__ import annotations

import json
from http import HTTPStatus
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from pgpt import server as base
from pgpt.config import CONFIG
from pgpt.storage import chats


ROOT = Path(__file__).resolve().parents[1]
PERSISTENCE_SCRIPT = ROOT / "web" / "persistence.js"


def _browser_state_payload() -> dict[str, Any]:
    return {"state": chats.load_browser_state()}


def _web_index_bytes() -> bytes:
    if not base.WEB_INDEX_PATH.exists():
        raise FileNotFoundError(base.WEB_INDEX_PATH)
    html = base.WEB_INDEX_PATH.read_text(encoding="utf-8")
    tag = '<script src="/persistence.js"></script>'
    if tag not in html:
        html = html.replace("</body>", f"{tag}</body>")
    return html.encode("utf-8")


class BrowserHandler(base.PgptHandler):
    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path == "/api/chats":
            self._json(HTTPStatus.OK, _browser_state_payload())
            return
        if path == "/persistence.js":
            if not PERSISTENCE_SCRIPT.exists():
                self._json(HTTPStatus.NOT_FOUND, {"error": "Persistence script not found"})
                return
            self._bytes(
                HTTPStatus.OK,
                PERSISTENCE_SCRIPT.read_bytes(),
                "text/javascript; charset=utf-8",
                headers={"Cache-Control": "no-store"},
            )
            return
        if path == "/":
            try:
                body = _web_index_bytes()
            except FileNotFoundError:
                self._json(HTTPStatus.NOT_FOUND, {"error": "Web UI is not installed"})
                return
            self._bytes(
                HTTPStatus.OK,
                body,
                "text/html; charset=utf-8",
                headers={"Cache-Control": "no-store"},
            )
            return
        super().do_GET()

    def do_POST(self) -> None:
        path = urlsplit(self.path).path
        if path != "/api/chats":
            super().do_POST()
            return
        try:
            state = chats.save_browser_state(self._payload())
            self._json(HTTPStatus.OK, {"ok": True, "state": state})
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
        raise RuntimeError("Refusing a non-loopback bind without --allow-remote")
    server = ThreadingHTTPServer((host, port), BrowserHandler)
    print(f"pgpt-cli UI:  http://{host}:{port}/")
    print(f"OpenAI API:   http://{host}:{port}/v1")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
