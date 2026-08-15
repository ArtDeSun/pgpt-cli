from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from pgpt.config import CONFIG, expand, get_project

from pgpt.retrieval.project_symbol_rules import (
    looks_like_project_symbol,
    max_candidates,
    minimum_project_definition_score,
)


CODE_EXTS = {
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".py",
    ".json",
    ".md",
    ".mjs",
    ".cjs",
}

IGNORE_DIRS = {
    ".git",
    "node_modules",
    ".next",
    "dist",
    "build",
    "coverage",
}

_IDENTIFIER = re.compile(
    r"\b[A-Za-z_$][A-Za-z0-9_$]{2,}\b"
)


@dataclass
class SymbolHit:
    path: Path
    identifier: str
    line_number: int
    line_text: str
    definition_score: int


def _source_root(project_name: str) -> Path:
    _, project = get_project(project_name)
    return expand(project["source_dir"])


def candidate_identifiers(
    prompt: str,
) -> list[str]:
    """
    Extract structurally distinctive code identifiers.

    Semantic vocabulary is intentionally not encoded here.
    Identifier-shape policy is loaded from prompts/retrieval/
    project-symbols.json.
    """

    values: list[str] = []

    for value in _IDENTIFIER.findall(
        prompt
    ):
        if not looks_like_project_symbol(
            value
        ):
            continue

        if value not in values:
            values.append(
                value
            )

    values.sort(
        key=lambda value: (
            -sum(
                char.isupper()
                for char in value
            ),
            -len(value),
        )
    )

    return values[
        :max_candidates()
    ]


def _definition_score(
    line: str,
    identifier: str,
) -> int:
    """
    Rank actual symbol definitions above imports/usages.
    """
    escaped = re.escape(identifier)

    patterns = (
        rf"\b(?:export\s+)?(?:default\s+)?async\s+function\s+{escaped}\b",
        rf"\b(?:export\s+)?function\s+{escaped}\b",
        rf"\b(?:export\s+)?(?:const|let|var)\s+{escaped}\b",
        rf"\b(?:export\s+)?class\s+{escaped}\b",
        rf"\b(?:export\s+)?interface\s+{escaped}\b",
        rf"\b(?:export\s+)?type\s+{escaped}\b",
        rf"\bdef\s+{escaped}\b",
        rf"\bclass\s+{escaped}\b",
    )

    for index, pattern in enumerate(patterns):
        if re.search(
            pattern,
            line,
            flags=re.IGNORECASE,
        ):
            return 100 - index

    stripped = line.strip()

    if stripped.startswith(("import ", "export {")):
        return 5

    return 20


def _symbol_hits(
    prompt: str,
    project_name: str,
) -> list[SymbolHit]:
    root = _source_root(project_name)

    if not root.exists():
        return []

    hits: list[SymbolHit] = []

    for identifier in candidate_identifiers(prompt):
        try:
            proc = subprocess.run(
                [
                    "rg",
                    "-n",
                    "-i",
                    "-F",
                    identifier,
                    str(root),
                ],
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
        except (
            FileNotFoundError,
            subprocess.TimeoutExpired,
        ):
            break

        for raw in proc.stdout.splitlines():
            # rg output:
            # /path/file.ts:123:matching source text
            parts = raw.split(":", 2)

            if len(parts) != 3:
                continue

            raw_path, raw_line, line_text = parts

            try:
                line_number = int(raw_line)
            except ValueError:
                continue

            path = Path(raw_path)

            if path.suffix.lower() not in CODE_EXTS:
                continue

            if any(
                part in IGNORE_DIRS
                for part in path.parts
            ):
                continue

            hits.append(
                SymbolHit(
                    path=path,
                    identifier=identifier,
                    line_number=line_number,
                    line_text=line_text,
                    definition_score=_definition_score(
                        line_text,
                        identifier,
                    ),
                )
            )

    hits.sort(
        key=lambda hit: (
            -hit.definition_score,
            len(str(hit.path)),
            hit.line_number,
        )
    )

    return hits


def exact_symbol_files(
    prompt: str,
    project_name: str,
) -> list[Path]:
    hits = _symbol_hits(
        prompt,
        project_name,
    )

    files: list[Path] = []

    for hit in hits:
        if hit.path not in files:
            files.append(hit.path)

        if len(files) >= 6:
            break

    return files


def has_symbol_hit(
    prompt: str,
    project_name: str,
) -> bool:
    minimum_score = (
        minimum_project_definition_score()
    )

    return any(
        hit.definition_score
        >= minimum_score
        for hit in _symbol_hits(
            prompt,
            project_name,
        )
    )


def _iter_files(
    root: Path,
) -> Iterable[Path]:
    for path in root.rglob("*"):
        if not path.is_file():
            continue

        if path.suffix.lower() not in CODE_EXTS:
            continue

        if any(
            part in IGNORE_DIRS
            for part in path.parts
        ):
            continue

        yield path


def _query_terms(
    prompt: str,
) -> list[str]:
    terms = [
        value.casefold()
        for value in _IDENTIFIER.findall(prompt)
        if len(value) >= 4
    ]

    stop = {
        "this",
        "that",
        "with",
        "from",
        "into",
        "while",
        "project",
        "application",
        "explain",
        "design",
    }

    return [
        value
        for value in terms
        if value not in stop
    ][:20]


def lexical_files(
    prompt: str,
    project_name: str,
    limit: int = 8,
) -> list[Path]:
    root = _source_root(project_name)
    terms = _query_terms(prompt)

    scored: list[tuple[int, Path]] = []

    preferred_names = {
        "package.json",
        "README.md",
        "next.config.js",
        "next.config.mjs",
        "vercel.json",
    }

    for path in _iter_files(root):
        score = (
            2
            if path.name in preferred_names
            else 0
        )

        relative = str(
            path.relative_to(root)
        ).casefold()

        score += sum(
            4
            for term in terms
            if term in relative
        )

        if score == 0:
            try:
                text = path.read_text(
                    encoding="utf-8",
                    errors="ignore",
                )[:50000].casefold()
            except OSError:
                continue

            score += sum(
                1
                for term in terms
                if term in text
            )

        if score:
            scored.append(
                (score, path)
            )

    scored.sort(
        key=lambda item: (
            -item[0],
            len(str(item[1])),
        )
    )

    return [
        path
        for _, path in scored[:limit]
    ]


def _source_window(
    path: Path,
    line_number: int,
    *,
    before: int = 35,
    after: int = 100,
) -> str:
    """
    Return source surrounding the actual symbol occurrence rather
    than blindly truncating the file from line 1.
    """
    text = path.read_text(
        encoding="utf-8",
        errors="replace",
    )

    lines = text.splitlines()

    if not lines:
        return ""

    start = max(
        0,
        line_number - before - 1,
    )

    end = min(
        len(lines),
        line_number + after,
    )

    selected: list[str] = []

    for index in range(start, end):
        selected.append(
            f"{index + 1:>5} | {lines[index]}"
        )

    return "\n".join(selected)


def _exact_context(
    prompt: str,
    project_name: str,
    budget: int,
) -> tuple[str, list[str]]:
    root = _source_root(project_name)

    hits = _symbol_hits(
        prompt,
        project_name,
    )

    if not hits:
        return "", []

    chunks: list[str] = []
    files: list[str] = []
    remaining = budget

    # Prefer one best match per file.
    seen: set[Path] = set()

    for hit in hits:
        if hit.path in seen:
            continue

        seen.add(hit.path)

        try:
            relative = str(
                hit.path.relative_to(root)
            )

            source = _source_window(
                hit.path,
                hit.line_number,
            )
        except OSError:
            continue

        header = (
            f"### SOURCE FILE: {relative}\n"
            f"Matched symbol: {hit.identifier}\n"
            f"Matched line: {hit.line_number}\n"
            f"Definition score: {hit.definition_score}\n"
        )

        block = (
            header
            + "```text\n"
            + source
            + "\n```"
        )

        if len(block) > remaining:
            if not chunks:
                block = block[:remaining]
            else:
                break

        chunks.append(block)
        files.append(relative)
        remaining -= len(block)

        # Usually the definition plus one usage/import file is enough.
        if len(chunks) >= 3:
            break

    return "\n\n".join(chunks), files


def _lexical_context(
    prompt: str,
    project_name: str,
    budget: int,
) -> tuple[str, list[str]]:
    root = _source_root(project_name)

    selected = lexical_files(
        prompt,
        project_name,
    )

    chunks: list[str] = []
    files: list[str] = []
    remaining = budget

    for path in selected:
        try:
            relative = str(
                path.relative_to(root)
            )

            content = path.read_text(
                encoding="utf-8",
                errors="replace",
            )
        except OSError:
            continue

        header = (
            f"### SOURCE FILE: {relative}\n"
        )

        available = (
            remaining
            - len(header)
            - 20
        )

        if available <= 0:
            break

        content = content[:available]

        block = (
            header
            + "```\n"
            + content
            + "\n```"
        )

        chunks.append(block)
        files.append(relative)
        remaining -= len(block)

        if remaining <= 0:
            break

    return "\n\n".join(chunks), files


def build_context(
    prompt: str,
    project_name: str,
    max_chars: int | None = None,
) -> tuple[str, list[str]]:
    root = _source_root(project_name)

    budget = int(
        max_chars
        or CONFIG["retrieval"]["project_max_chars"]
    )

    # ---------------------------------------------------------
    # Exact symbol retrieval has priority.
    # ---------------------------------------------------------

    exact_context, exact_files = _exact_context(
        prompt,
        project_name,
        budget,
    )

    if exact_context:
        return exact_context, exact_files

    # ---------------------------------------------------------
    # Broader lexical fallback.
    # ---------------------------------------------------------

    lexical_context, lexical_found = _lexical_context(
        prompt,
        project_name,
        budget,
    )

    if lexical_context:
        return lexical_context, lexical_found

    # ---------------------------------------------------------
    # Truthful fallback: manifest only.
    # ---------------------------------------------------------

    if not root.exists():
        return (
            "PROJECT SOURCE DIRECTORY DOES NOT EXIST.",
            [],
        )

    manifest = sorted(
        str(path.relative_to(root))
        for path in _iter_files(root)
    )

    context = (
        "### PROJECT FILE MANIFEST\n"
        + "\n".join(manifest[:120])
    )

    return context[:budget], []