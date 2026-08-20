from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable

from pgpt.config import CONFIG
from pgpt.generation.ollama import stream_chat

_EXAMPLE_USAGE_ISSUE = "Explain-code answer generated an Example Usage section."
_ROOT = Path(__file__).resolve().parents[2] / "prompts"


def _prompt(path: str) -> str:
    return (_ROOT / path).read_text(encoding="utf-8").strip()


def _remove_markdown_section(answer: str, heading_text: str) -> str:
    heading = re.compile(
        rf"(?im)^(#{{1,6}})[ \t]+{re.escape(heading_text)}[ \t]*#*[ \t]*$"
    )
    match = heading.search(answer)
    if match is None:
        return answer

    level = len(match.group(1))
    end = len(answer)
    next_heading = re.compile(r"(?m)^(#{1,6})[ \t]+.+$")
    for candidate in next_heading.finditer(answer, match.end()):
        if len(candidate.group(1)) <= level:
            end = candidate.start()
            break

    before = answer[: match.start()].rstrip()
    after = answer[end:].lstrip("\n")
    if before and after:
        return before + "\n\n" + after
    return before or after


def apply_deterministic_repairs(
    *, answer: str, issues: list[str]
) -> tuple[str, list[str]]:
    if _EXAMPLE_USAGE_ISSUE not in issues:
        return answer, []

    repaired = _remove_markdown_section(answer, "Example Usage")
    if repaired == answer:
        return answer, []
    return repaired, [_EXAMPLE_USAGE_ISSUE]


def stream_repair(
    *,
    model: str,
    base_system: str,
    original_prompt: str,
    draft_answer: str,
    issues: list[str],
    on_text: Callable[[str], None],
    max_tokens: int,
    num_ctx: int,
) -> dict[str, Any]:
    issue_text = "\n".join(f"- {issue}" for issue in issues)
    request = _prompt("quality/repair-request.md").format(
        original_prompt=original_prompt,
        issue_text=issue_text,
        draft_answer=draft_answer,
    )
    return stream_chat(
        model=model,
        messages=[
            {"role": "system", "content": base_system + "\n\n" + _prompt("repair.md")},
            {"role": "user", "content": request},
        ],
        on_text=on_text,
        max_tokens=max_tokens,
        num_ctx=num_ctx,
        temperature=float(CONFIG["defaults"].get("temperature", 0.1)),
    )
