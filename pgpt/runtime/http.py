from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Iterator


def _request(
    method: str,
    url: str,
    *,
    payload: dict[str, Any] | None,
    headers: dict[str, str] | None,
) -> urllib.request.Request:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request_headers = {"Accept": "application/json", **(headers or {})}
    if data is not None:
        request_headers.setdefault("Content-Type", "application/json")
    return urllib.request.Request(url, data=data, headers=request_headers, method=method)


def json_request_with_headers(
    method: str,
    url: str,
    *,
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 30.0,
) -> tuple[Any, dict[str, str]]:
    brave_request = url.startswith("https://api.search.brave.com/")
    if brave_request:
        from pgpt.retrieval.web_usage import ensure_search_budget
        ensure_search_budget()

    req = _request(method, url, payload=payload, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            value = json.loads(raw) if raw else None
            response_headers = {str(key): str(value) for key, value in response.headers.items()}
            if brave_request:
                from pgpt.retrieval.web_usage import record_search_success
                record_search_success(response_headers)
            return value, response_headers
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} from {url}: {body[:1000]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Request failed for {url}: {exc.reason}") from exc


def json_request(
    method: str,
    url: str,
    *,
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 30.0,
) -> Any:
    value, _ = json_request_with_headers(
        method,
        url,
        payload=payload,
        headers=headers,
        timeout=timeout,
    )
    return value


def ndjson_request(
    url: str,
    *,
    payload: dict[str, Any],
    timeout: float = 300.0,
) -> Iterator[dict[str, Any]]:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/x-ndjson"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            for raw in response:
                line = raw.decode("utf-8").strip()
                if line:
                    yield json.loads(line)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} from {url}: {body[:1000]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Request failed for {url}: {exc.reason}") from exc
