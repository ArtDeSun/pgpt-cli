from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from pgpt.config import cfg_path


_BROWSER_STATE_NAME = "browser-state.json"


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.casefold()).strip("-")[:60] or "chat"


def _chat_dir(slug: str) -> Path:
    return cfg_path("chats_dir") / slug


def current_file() -> Path:
    return cfg_path("state_dir") / "current_chat.txt"


def browser_state_file() -> Path:
    return cfg_path("chats_dir") / _BROWSER_STATE_NAME


def create(title: str, project: str | None = None) -> str:
    base = _slug(title)
    slug = base
    i = 2
    while _chat_dir(slug).exists():
        slug = f"{base}-{i}"
        i += 1
    d = _chat_dir(slug)
    d.mkdir(parents=True, exist_ok=True)
    data = {
        "title": title,
        "project": project,
        "created": datetime.now().isoformat(),
        "messages": [],
    }
    save(slug, data)
    set_current(slug)
    return slug


def set_current(slug: str) -> None:
    path = current_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(slug, encoding="utf-8")


def current() -> str | None:
    path = current_file()
    return path.read_text(encoding="utf-8").strip() if path.exists() else None


def load(slug: str) -> dict[str, Any]:
    path = _chat_dir(slug) / "conversation.json"
    if not path.exists():
        raise SystemExit(f"Chat not found: {slug}")
    return json.loads(path.read_text(encoding="utf-8"))


def save(slug: str, data: dict[str, Any]) -> None:
    directory = _chat_dir(slug)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "conversation.json"
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def list_chats() -> list[tuple[str, dict[str, Any]]]:
    root = cfg_path("chats_dir")
    if not root.exists():
        return []
    out = []
    for d in sorted(root.iterdir()):
        if d.is_dir() and (d / "conversation.json").exists():
            out.append((d.name, load(d.name)))
    return out


def _validate_browser_state(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("Browser chat state must be an object")
    chats = value.get("chats")
    active_id = value.get("activeId")
    if not isinstance(chats, list):
        raise ValueError("Browser chat state requires a chats list")
    if active_id is not None and not isinstance(active_id, str):
        raise ValueError("Browser chat activeId must be a string")

    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in chats:
        if not isinstance(item, dict):
            raise ValueError("Each browser chat must be an object")
        chat_id = item.get("id")
        title = item.get("title")
        messages = item.get("messages")
        if not isinstance(chat_id, str) or not chat_id.strip():
            raise ValueError("Each browser chat requires an id")
        if chat_id in seen:
            raise ValueError(f"Duplicate browser chat id: {chat_id}")
        if not isinstance(title, str):
            raise ValueError("Each browser chat requires a title")
        if not isinstance(messages, list):
            raise ValueError("Each browser chat requires a messages list")
        seen.add(chat_id)
        normalized.append(dict(item))

    if active_id is not None and normalized and active_id not in seen:
        raise ValueError("Browser chat activeId must reference an existing chat")
    return {"activeId": active_id, "chats": normalized}


def load_browser_state() -> dict[str, Any] | None:
    path = browser_state_file()
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return _validate_browser_state(value)
    except (OSError, json.JSONDecodeError, ValueError):
        return None


def save_browser_state(value: Any) -> dict[str, Any]:
    state = _validate_browser_state(value)
    path = browser_state_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)
    return state
