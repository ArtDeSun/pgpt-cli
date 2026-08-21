from __future__ import annotations

import re

_WORD = re.compile(r"[a-z0-9][a-z0-9_+-]{2,}", re.IGNORECASE)
_FOLLOWUP = re.compile(
    r"^\s*(?:yes|no|why|how|what about|and |also |then |continue|again|same|"
    r"use (?:the )?web|try again|wrong|that|this|it|they|those|these|previous|above)\b",
    re.IGNORECASE,
)
_STOP = {
    "the", "and", "that", "this", "with", "from", "into", "your", "you", "for",
    "are", "was", "were", "what", "who", "how", "why", "can", "could", "would",
    "use", "using", "please", "about", "answer", "question", "explain", "tell",
}


def _tokens(text: str) -> set[str]:
    return {word.casefold() for word in _WORD.findall(text) if word.casefold() not in _STOP}


def _related(left: set[str], right: set[str]) -> bool:
    if not left or not right:
        return False
    common = left & right
    return bool(common) and len(common) / max(1, min(len(left), len(right))) >= 0.2


def _looks_like_followup(prompt: str) -> bool:
    words = _WORD.findall(prompt)
    return bool(_FOLLOWUP.search(prompt)) or len(words) <= 5


def _topic_tail(conversation: list[dict[str, str]], limit: int) -> list[dict[str, str]]:
    user_indexes = [i for i, row in enumerate(conversation) if row.get("role") == "user"]
    if not user_indexes:
        return conversation[-limit:]
    last = user_indexes[-1]
    anchor = _tokens(conversation[last].get("content", ""))
    start = last
    for index in reversed(user_indexes[:-1]):
        candidate = _tokens(conversation[index].get("content", ""))
        if not _related(candidate, anchor):
            break
        start = index
        anchor |= candidate
    return conversation[start:][-limit:]


def select_history(
    prompt: str,
    history: list[dict[str, str]] | None,
    *,
    mode: str = "auto",
    limit: int = 12,
) -> list[dict[str, str]]:
    """Keep relevant conversational context while preserving explicit system/skill messages."""
    rows = list(history or [])
    system = [row for row in rows if row.get("role") == "system"]
    conversation = [row for row in rows if row.get("role") in {"user", "assistant"}]
    if mode == "off":
        return system
    if mode == "full":
        return [*conversation[-limit:], *system]
    if mode != "auto":
        raise ValueError(f"Unknown history mode: {mode}")
    if not conversation:
        return system

    previous_users = [row for row in conversation if row.get("role") == "user"]
    if not previous_users:
        return system
    previous = previous_users[-1].get("content", "")
    if _looks_like_followup(prompt) or _related(_tokens(prompt), _tokens(previous)):
        return [*_topic_tail(conversation, limit), *system]
    return system
