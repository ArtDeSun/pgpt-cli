from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pgpt.config import CONFIG, cfg_path


def _state_path() -> Path:
    return cfg_path("state_dir") / "brave_usage.json"


def _period(now: datetime | None = None) -> str:
    value = now if now is not None else datetime.now(timezone.utc)
    return value.strftime("%Y-%m")


def _fresh_state(period: str) -> dict[str, Any]:
    return {"period": period, "local_requests": 0, "updated_at": None, "api": {}}


def _load_state(now: datetime | None = None) -> dict[str, Any]:
    period = _period(now)
    path = _state_path()
    if not path.exists():
        return _fresh_state(period)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _fresh_state(period)
    if not isinstance(value, dict) or value.get("period") != period:
        return _fresh_state(period)
    value.setdefault("local_requests", 0)
    value.setdefault("api", {})
    value.setdefault("updated_at", None)
    return value


def _save_state(state: dict[str, Any]) -> None:
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def _header(headers: dict[str, str], name: str) -> str | None:
    wanted = name.casefold()
    for key, value in headers.items():
        if key.casefold() == wanted:
            return str(value)
    return None


def _integer_list(value: str | None) -> list[int]:
    if not value:
        return []
    out: list[int] = []
    for part in value.split(","):
        try:
            out.append(int(part.strip()))
        except ValueError:
            continue
    return out


def _policy_windows(value: str | None) -> list[int]:
    if not value:
        return []
    windows: list[int] = []
    for item in value.split(","):
        window = 0
        for token in item.split(";"):
            token = token.strip()
            if token.startswith("w="):
                try:
                    window = int(token[2:])
                except ValueError:
                    window = 0
        windows.append(window)
    return windows


def _api_quota(headers: dict[str, str]) -> dict[str, Any]:
    limits = _integer_list(_header(headers, "X-RateLimit-Limit"))
    remaining = _integer_list(_header(headers, "X-RateLimit-Remaining"))
    resets = _integer_list(_header(headers, "X-RateLimit-Reset"))
    windows = _policy_windows(_header(headers, "X-RateLimit-Policy"))
    size = max(len(limits), len(remaining), len(resets), len(windows), 0)
    if size == 0:
        return {}

    def item(values: list[int], index: int) -> int | None:
        return values[index] if index < len(values) else None

    candidates = [
        {
            "limit": item(limits, index),
            "remaining": item(remaining, index),
            "reset_seconds": item(resets, index),
            "window_seconds": item(windows, index),
        }
        for index in range(size)
    ]
    monthly = max(
        candidates,
        key=lambda value: (
            int(value.get("window_seconds") or 0),
            int(value.get("limit") or 0),
        ),
    )
    output: dict[str, Any] = {"windows": candidates}
    for key in ("limit", "remaining", "reset_seconds", "window_seconds"):
        value = monthly.get(key)
        if value is not None:
            output[f"monthly_{key}"] = int(value)
    return output


def _budget() -> int:
    return max(0, int(CONFIG.get("web", {}).get("monthly_request_budget", 500)))


def usage_snapshot(now: datetime | None = None) -> dict[str, Any]:
    state = _load_state(now)
    budget = _budget()
    local_requests = max(0, int(state.get("local_requests", 0) or 0))
    api = state.get("api", {})
    if not isinstance(api, dict):
        api = {}

    api_limit = api.get("monthly_limit")
    api_remaining = api.get("monthly_remaining")
    api_unlimited = isinstance(api_limit, int) and api_limit == 0
    api_used: int | None = None
    if (
        isinstance(api_limit, int)
        and api_limit > 0
        and isinstance(api_remaining, int)
    ):
        api_used = max(0, api_limit - api_remaining)

    effective_requests = max(local_requests, api_used if api_used is not None else 0)
    remaining = max(0, budget - effective_requests) if budget > 0 else None
    warning_ratio = float(CONFIG.get("web", {}).get("budget_warning_ratio", 0.8))
    warning = bool(budget > 0 and effective_requests >= budget * warning_ratio)
    return {
        "period": state["period"],
        "budget": budget,
        "local_requests": local_requests,
        "api_monthly_used": api_used,
        "api_monthly_unlimited": api_unlimited,
        "effective_requests": effective_requests,
        "remaining": remaining,
        "warning": warning,
        "api_monthly_limit": api_limit,
        "api_monthly_remaining": api_remaining,
        "api_monthly_reset_seconds": api.get("monthly_reset_seconds"),
        "api_monthly_window_seconds": api.get("monthly_window_seconds"),
        "updated_at": state.get("updated_at"),
    }


def ensure_search_budget() -> None:
    snapshot = usage_snapshot()
    remaining = snapshot.get("remaining")
    if isinstance(remaining, int) and remaining <= 0:
        raise RuntimeError("Brave monthly request budget has been reached")

    api_limit = snapshot.get("api_monthly_limit")
    api_remaining = snapshot.get("api_monthly_remaining")
    if (
        isinstance(api_limit, int)
        and api_limit > 0
        and isinstance(api_remaining, int)
        and api_remaining <= 0
    ):
        raise RuntimeError("Brave API reports no monthly requests remaining")


def record_search_success(headers: dict[str, str], now: datetime | None = None) -> dict[str, Any]:
    state = _load_state(now)
    state["local_requests"] = max(0, int(state.get("local_requests", 0) or 0)) + 1
    api = _api_quota(headers)
    if api:
        state["api"] = api
    value = now if now is not None else datetime.now(timezone.utc)
    state["updated_at"] = value.isoformat()
    _save_state(state)
    return usage_snapshot(now)
