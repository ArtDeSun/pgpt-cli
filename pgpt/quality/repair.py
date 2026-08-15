from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable

from pgpt.config import CONFIG
from pgpt.generation.ollama import stream_chat


_EXAMPLE_USAGE_ISSUE = (
    "Explain-code answer generated an Example Usage section."
)


def _repair_prompt() -> str:
    path = (
        Path(__file__).resolve().parents[2]
        / "prompts"
        / "repair.md"
    )

    return path.read_text(
        encoding="utf-8"
    ).strip()


def _remove_markdown_section(
    answer: str,
    heading_text: str,
) -> str:
    """
    Remove one Markdown section by heading name.

    The section ends at the next heading of the same or a
    higher level. If there is no following heading, it ends
    at the end of the answer.
    """

    heading = re.compile(
        rf"(?im)^"
        rf"(#{{1,6}})"
        rf"[ \t]+"
        rf"{re.escape(heading_text)}"
        rf"[ \t]*#*"
        rf"[ \t]*$"
    )

    match = heading.search(
        answer
    )

    if match is None:
        return answer

    level = len(
        match.group(1)
    )

    next_heading = re.compile(
        r"(?m)^(#{1,6})[ \t]+.+$"
    )

    end = len(answer)

    for candidate in next_heading.finditer(
        answer,
        match.end(),
    ):
        candidate_level = len(
            candidate.group(1)
        )

        if candidate_level <= level:
            end = candidate.start()
            break

    before = answer[
        :match.start()
    ].rstrip()

    after = answer[
        end:
    ].lstrip("\n")

    if before and after:
        return (
            before
            + "\n\n"
            + after
        )

    if before:
        return before

    return after


def apply_deterministic_repairs(
    *,
    answer: str,
    issues: list[str],
) -> tuple[str, list[str]]:
    """
    Apply only repairs that are mechanically safe.

    Returns:
        repaired answer,
        verifier issues that were actually handled
    """

    repaired = answer
    applied: list[str] = []

    if _EXAMPLE_USAGE_ISSUE in issues:
        candidate = _remove_markdown_section(
            repaired,
            "Example Usage",
        )

        if candidate != repaired:
            repaired = candidate

            applied.append(
                _EXAMPLE_USAGE_ISSUE
            )

    return (
        repaired,
        applied,
    )


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
    """
    Perform one semantic LLM repair.

    This is used only after deterministic repair has been
    attempted and verifier problems still remain.
    """

    issue_text = "\n".join(
        f"- {issue}"
        for issue in issues
    )

    system = (
        base_system
        + "\n\n"
        + _repair_prompt()
    )

    request = (
        "ORIGINAL REQUEST\n"
        f"{original_prompt}\n\n"
        "VERIFICATION ISSUES\n"
        f"{issue_text}\n\n"
        "DRAFT ANSWER\n"
        f"{draft_answer}"
    )

    return stream_chat(
        model=model,
        messages=[
            {
                "role": "system",
                "content": system,
            },
            {
                "role": "user",
                "content": request,
            },
        ],
        on_text=on_text,
        max_tokens=max_tokens,
        num_ctx=num_ctx,
        temperature=float(
            CONFIG["defaults"].get(
                "temperature",
                0.1,
            )
        ),
    )