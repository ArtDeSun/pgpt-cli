from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from pgpt.config import cfg_path


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.casefold()).strip("-")[:60] or "chat"


def _chat_dir(slug: str) -> Path:
    return cfg_path("chats_dir") / slug


def current_file() -> Path:
    return cfg_path("state_dir") / "current_chat.txt"


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
    (d / "conversation.json").write_text(
        json.dumps(data, indent=2), encoding="utf-8"
    )
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
    (_chat_dir(slug) / "conversation.json").write_text(
        json.dumps(data, indent=2), encoding="utf-8"
    )


def list_chats() -> list[tuple[str, dict[str, Any]]]:
    root = cfg_path("chats_dir")
    if not root.exists():
        return []
    out = []
    for d in sorted(root.iterdir()):
        if d.is_dir() and (d / "conversation.json").exists():
            out.append((d.name, load(d.name)))
    return out
