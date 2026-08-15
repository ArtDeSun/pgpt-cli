from __future__ import annotations

import math
import re
from dataclasses import dataclass

from pgpt.generation.ollama import embed
from pgpt.retrieval.web import WebResult


_SOURCE_ID = re.compile(
    r"\[S(\d+)\]",
    re.IGNORECASE,
)

_CITATION = re.compile(
    r"\[S\d+\]",
    re.IGNORECASE,
)

_SENTENCE_SPLIT = re.compile(
    r"(?<=[.!?])\s+|\n+"
)


@dataclass(frozen=True)
class CitationSupportIssue:
    source_id: int
    claim: str
    score: float


def _cosine(
    left: list[float],
    right: list[float],
) -> float:
    dot = sum(
        a * b
        for a, b in zip(
            left,
            right,
        )
    )

    left_norm = math.sqrt(
        sum(
            value * value
            for value in left
        )
    )

    right_norm = math.sqrt(
        sum(
            value * value
            for value in right
        )
    )

    if (
        not left_norm
        or not right_norm
    ):
        return 0.0

    return (
        dot
        / (
            left_norm
            * right_norm
        )
    )


def _claim_segments(
    answer: str,
) -> list[
    tuple[
        str,
        set[int],
    ]
]:
    """
    Extract answer segments containing one or more [S#]
    citations.

    The returned claim text has citation markers removed so
    semantic similarity measures the actual factual statement.
    """

    segments: list[
        tuple[
            str,
            set[int],
        ]
    ] = []

    for raw in _SENTENCE_SPLIT.split(
        answer
    ):
        raw = raw.strip()

        if not raw:
            continue

        source_ids = {
            int(value)
            for value
            in _SOURCE_ID.findall(
                raw
            )
        }

        if not source_ids:
            continue

        claim = _CITATION.sub(
            "",
            raw,
        ).strip()

        # Very short labels/headings are not meaningful claims.
        if len(claim) < 20:
            continue

        segments.append(
            (
                claim,
                source_ids,
            )
        )

    return segments


def _source_chunks(
    result: WebResult,
) -> list[str]:
    """
    Build small evidence chunks for one retrieved source.

    Small chunks are preferable to embedding an entire fetched
    webpage because one relevant paragraph should be able to
    strongly support a claim even when the rest of the page is
    unrelated.
    """

    chunks: list[str] = []

    if result.title:
        chunks.append(
            result.title.strip()
        )

    if result.description:
        chunks.append(
            result.description.strip()
        )

    for snippet in (
        result.extra_snippets[:4]
    ):
        snippet = snippet.strip()

        if snippet:
            chunks.append(
                snippet
            )

    if result.page_text:
        paragraphs = [
            value.strip()
            for value
            in re.split(
                r"\n{1,}",
                result.page_text,
            )
            if value.strip()
        ]

        current = ""

        for paragraph in paragraphs:
            if len(paragraph) > 900:
                paragraph = (
                    paragraph[:900]
                )

            if not current:
                current = paragraph

            elif (
                len(current)
                + len(paragraph)
                + 1
                <= 900
            ):
                current += (
                    " "
                    + paragraph
                )

            else:
                chunks.append(
                    current
                )

                current = paragraph

            # Keep citation checking bounded.
            if len(chunks) >= 12:
                break

        if (
            current
            and len(chunks) < 12
        ):
            chunks.append(
                current
            )

    # Remove duplicates while preserving order.
    unique: list[str] = []
    seen: set[str] = set()

    for chunk in chunks:
        normalized = (
            " ".join(
                chunk.split()
            )
            .casefold()
        )

        if (
            not normalized
            or normalized in seen
        ):
            continue

        seen.add(
            normalized
        )

        unique.append(
            chunk
        )

    return unique[:12]


def find_weak_citations(
    *,
    answer: str,
    web_results: list[WebResult],
    minimum_similarity: float = 0.34,
) -> list[CitationSupportIssue]:
    """
    Find inline citations whose nearby claim has weak semantic
    similarity to every evidence chunk from that cited source.

    This is deliberately conservative. It is an additional
    verifier signal, not a proof that a citation is false.

    If embedding fails, verification fails open so a temporary
    embedding problem does not reject an otherwise usable
    response.
    """

    claims = _claim_segments(
        answer
    )

    if (
        not claims
        or not web_results
    ):
        return []

    chunks_by_source: dict[
        int,
        list[str],
    ] = {}

    for source_id, result in enumerate(
        web_results,
        1,
    ):
        chunks_by_source[
            source_id
        ] = _source_chunks(
            result
        )

    relevant_source_ids = {
        source_id
        for _, source_ids
        in claims
        for source_id
        in source_ids
        if source_id
        in chunks_by_source
    }

    texts: list[str] = []
    text_index: dict[str, int] = {}

    def add_text(
        text: str,
    ) -> None:
        if text not in text_index:
            text_index[text] = len(
                texts
            )

            texts.append(
                text
            )

    for claim, _ in claims:
        add_text(
            claim
        )

    for source_id in relevant_source_ids:
        for chunk in chunks_by_source.get(
            source_id,
            [],
        ):
            add_text(
                chunk
            )

    if not texts:
        return []

    try:
        vectors = embed(
            texts
        )

    except Exception:
        return []

    vector_by_text = {
        text: vectors[index]
        for text, index
        in text_index.items()
    }

    issues: list[
        CitationSupportIssue
    ] = []

    for claim, source_ids in claims:
        claim_vector = (
            vector_by_text[
                claim
            ]
        )

        for source_id in source_ids:
            chunks = (
                chunks_by_source.get(
                    source_id,
                    [],
                )
            )

            if not chunks:
                continue

            best_score = max(
                _cosine(
                    claim_vector,
                    vector_by_text[
                        chunk
                    ],
                )
                for chunk in chunks
            )

            if (
                best_score
                < minimum_similarity
            ):
                issues.append(
                    CitationSupportIssue(
                        source_id=source_id,
                        claim=claim,
                        score=best_score,
                    )
                )

    return issues