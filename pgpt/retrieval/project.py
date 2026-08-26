from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from pgpt.config import CONFIG, expand, get_project, user_project_names
from pgpt.retrieval.project_symbol_rules import (
    lexical_max_terms,
    lexical_minimum_term_length,
    lexical_stop_words,
    looks_like_project_symbol,
    max_candidates,
    minimum_project_definition_score,
)


CODE_EXTS = {".ts", ".tsx", ".js", ".jsx", ".py", ".json", ".md", ".mjs", ".cjs"}
TEXT_EXTS = CODE_EXTS | {
    ".adoc",
    ".bash",
    ".cfg",
    ".conf",
    ".csv",
    ".css",
    ".fish",
    ".gql",
    ".graphql",
    ".htm",
    ".html",
    ".ini",
    ".less",
    ".ps1",
    ".rst",
    ".scss",
    ".sh",
    ".sql",
    ".toml",
    ".tsv",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
    ".zsh",
}
IGNORE_DIRS = {
    ".git",
    ".next",
    ".venv",
    ".ssh",
    ".gnupg",
    ".aws",
    "__pycache__",
    "node_modules",
    "venv",
    "dist",
    "build",
    "coverage",
}
IDENTIFIER = re.compile(r"\b[A-Za-z_$][A-Za-z0-9_$]{2,}\b")
_GENERIC_PROJECT_INTENT = re.compile(
    r"\b(?:my|this)\s+(?:project|repo|repository|codebase|application|app)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SymbolHit:
    path: Path
    identifier: str
    line_number: int
    line_text: str
    definition_score: int


def _source_root(project_name: str) -> Path:
    _, project = get_project(project_name)
    return expand(project["source_dir"])


def candidate_identifiers(prompt: str) -> list[str]:
    """Return distinctive code-like identifiers from the request."""
    values = []
    for value in IDENTIFIER.findall(prompt):
        if looks_like_project_symbol(value) and value not in values:
            values.append(value)

    values.sort(key=lambda value: (-sum(c.isupper() for c in value), -len(value)))
    return values[: max_candidates()]


def _definition_score(line: str, identifier: str) -> int:
    name = re.escape(identifier)
    patterns = (
        rf"\b(?:export\s+)?(?:default\s+)?async\s+function\s+{name}\b",
        rf"\b(?:export\s+)?function\s+{name}\b",
        rf"\b(?:export\s+)?(?:const|let|var)\s+{name}\b",
        rf"\b(?:export\s+)?class\s+{name}\b",
        rf"\b(?:export\s+)?interface\s+{name}\b",
        rf"\b(?:export\s+)?type\s+{name}\b",
        rf"\bdef\s+{name}\b",
        rf"\bclass\s+{name}\b",
    )
    for index, pattern in enumerate(patterns):
        if re.search(pattern, line, flags=re.IGNORECASE):
            return 100 - index
    return 5 if line.strip().startswith(("import ", "export {")) else 20


def _symbol_hits(prompt: str, project_name: str) -> list[SymbolHit]:
    root = _source_root(project_name)
    if not root.exists():
        return []

    hits: list[SymbolHit] = []
    for identifier in candidate_identifiers(prompt):
        try:
            result = subprocess.run(
                ["rg", "-n", "-i", "-F", identifier, str(root)],
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            break

        for raw in result.stdout.splitlines():
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
            if any(part in IGNORE_DIRS for part in path.parts):
                continue

            hits.append(
                SymbolHit(
                    path=path,
                    identifier=identifier,
                    line_number=line_number,
                    line_text=line_text,
                    definition_score=_definition_score(line_text, identifier),
                )
            )

    return sorted(
        hits,
        key=lambda hit: (-hit.definition_score, len(str(hit.path)), hit.line_number),
    )


def exact_symbol_files(prompt: str, project_name: str) -> list[Path]:
    files: list[Path] = []
    for hit in _symbol_hits(prompt, project_name):
        if hit.path not in files:
            files.append(hit.path)
        if len(files) == 6:
            break
    return files


def has_symbol_hit(prompt: str, project_name: str) -> bool:
    minimum = minimum_project_definition_score()
    return any(hit.definition_score >= minimum for hit in _symbol_hits(prompt, project_name))


def select_user_project(prompt: str) -> str | None:
    """Choose a user-registered context only when the evidence is unambiguous.

    Automatic selection never scans PrivateGPT runtime folders and never chooses
    built-in/internal projects. It first honors an explicitly named registered
    context, then a unique code-symbol match, then a generic "my project" request
    only when exactly one user context exists.
    """

    names = user_project_names()
    if not names:
        return None

    folded = prompt.casefold()
    named = [
        name
        for name in names
        if re.search(
            rf"(?<![a-z0-9]){re.escape(name.casefold())}(?![a-z0-9])",
            folded,
        )
    ]
    if len(named) == 1:
        return named[0]
    if len(named) > 1:
        return None

    if candidate_identifiers(prompt):
        matched = [name for name in names if has_symbol_hit(prompt, name)]
        if len(matched) == 1:
            return matched[0]
        if len(matched) > 1:
            return None

    if len(names) == 1 and _GENERIC_PROJECT_INTENT.search(prompt):
        return names[0]
    return None


def _iter_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if path.is_symlink() or not path.is_file() or path.suffix.lower() not in TEXT_EXTS:
            continue
        if any(part in IGNORE_DIRS for part in path.parts):
            continue
        yield path


def _read_prefix(path: Path, limit: int) -> str:
    with path.open("r", encoding="utf-8", errors="replace") as file:
        return file.read(max(0, limit))


def _query_terms(prompt: str) -> list[str]:
    minimum = lexical_minimum_term_length()
    stop = lexical_stop_words()
    terms = [
        value.casefold()
        for value in IDENTIFIER.findall(prompt)
        if len(value) >= minimum and value.casefold() not in stop
    ]
    return terms[: lexical_max_terms()]


def lexical_files(prompt: str, project_name: str, limit: int = 8) -> list[Path]:
    root = _source_root(project_name)
    terms = _query_terms(prompt)
    preferred = {"package.json", "README.md", "next.config.js", "next.config.mjs", "vercel.json"}
    scored: list[tuple[int, Path]] = []

    for path in _iter_files(root):
        score = 2 if path.name in preferred else 0
        relative = str(path.relative_to(root)).casefold()
        score += sum(4 for term in terms if term in relative)

        if score == 0:
            try:
                text = _read_prefix(path, 50000).casefold()
            except OSError:
                continue
            score += sum(1 for term in terms if term in text)

        if score:
            scored.append((score, path))

    scored.sort(key=lambda item: (-item[0], len(str(item[1]))))
    return [path for _, path in scored[:limit]]


def _source_window(path: Path, line_number: int, before: int = 35, after: int = 100) -> str:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    start = max(0, line_number - before - 1)
    end = min(len(lines), line_number + after)
    return "\n".join(f"{index + 1:>5} | {lines[index]}" for index in range(start, end))


def _exact_context(prompt: str, project_name: str, budget: int) -> tuple[str, list[str]]:
    root = _source_root(project_name)
    minimum = minimum_project_definition_score()
    hits = [hit for hit in _symbol_hits(prompt, project_name) if hit.definition_score >= minimum]
    if not hits:
        return "", []

    chunks: list[str] = []
    files: list[str] = []
    seen: set[Path] = set()
    remaining = budget

    for hit in hits:
        if hit.path in seen:
            continue
        seen.add(hit.path)
        try:
            relative = str(hit.path.relative_to(root))
            source = _source_window(hit.path, hit.line_number)
        except OSError:
            continue

        block = (
            f"### SOURCE FILE: {relative}\n"
            f"Matched symbol: {hit.identifier}\n"
            f"Matched line: {hit.line_number}\n"
            f"Definition score: {hit.definition_score}\n"
            f"```text\n{source}\n```"
        )
        if len(block) > remaining:
            if chunks:
                break
            block = block[:remaining]

        chunks.append(block)
        files.append(relative)
        remaining -= len(block)
        if len(chunks) == 3:
            break

    return "\n\n".join(chunks), files


def _lexical_context(prompt: str, project_name: str, budget: int) -> tuple[str, list[str]]:
    root = _source_root(project_name)
    chunks: list[str] = []
    files: list[str] = []
    remaining = budget

    for path in lexical_files(prompt, project_name):
        try:
            relative = str(path.relative_to(root))
            content = _read_prefix(path, remaining)
        except OSError:
            continue

        header = f"### SOURCE FILE: {relative}\n"
        available = remaining - len(header) - 20
        if available <= 0:
            break

        block = f"{header}```\n{content[:available]}\n```"
        chunks.append(block)
        files.append(relative)
        remaining -= len(block)
        if remaining <= 0:
            break

    return "\n\n".join(chunks), files


def _representative_context(root: Path, budget: int) -> tuple[str, list[str]]:
    paths = sorted(
        _iter_files(root),
        key=lambda path: (
            0
            if path.name.casefold()
            in {"readme.md", "readme.txt", "package.json", "pyproject.toml"}
            else 1,
            len(path.relative_to(root).parts),
            str(path.relative_to(root)).casefold(),
        ),
    )
    if not paths:
        return "### PROJECT FILE MANIFEST\nNo supported text files found.", []

    manifest = "### PROJECT FILE MANIFEST\n" + "\n".join(
        str(path.relative_to(root)) for path in paths[:120]
    )
    manifest_limit = min(budget, 1600, max(200, budget // 5))
    chunks = [manifest[:manifest_limit]]
    remaining = budget - len(chunks[0])
    files: list[str] = []

    for path in paths:
        relative = str(path.relative_to(root))
        header = f"### SOURCE FILE: {relative}\n"
        available = remaining - len(header) - 20
        if available <= 0:
            break
        try:
            content = _read_prefix(path, available)
        except OSError:
            continue
        if not content.strip():
            continue

        block = f"{header}```\n{content}\n```"
        chunks.append(block)
        files.append(relative)
        remaining -= len(block)
        if len(files) == 8:
            break

    return "\n\n".join(chunks)[:budget], files


def build_context(
    prompt: str,
    project_name: str,
    max_chars: int | None = None,
) -> tuple[str, list[str]]:
    """Build bounded project context, preferring exact symbols over lexical matches."""
    root = _source_root(project_name)
    budget = int(max_chars or CONFIG["retrieval"]["project_max_chars"])

    context, files = _exact_context(prompt, project_name, budget)
    if context:
        return context, files

    context, files = _lexical_context(prompt, project_name, budget)
    if context:
        return context, files

    if not root.exists():
        return "PROJECT SOURCE DIRECTORY DOES NOT EXIST.", []

    return _representative_context(root, budget)
