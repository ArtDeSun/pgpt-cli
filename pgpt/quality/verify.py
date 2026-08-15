from __future__ import annotations

import re
from dataclasses import dataclass

from pgpt.quality.citations import (
    find_weak_citations,
)
from pgpt.retrieval.web import WebResult
from pgpt.runtime.route import Route


_SOURCE_ID = re.compile(
    r"\[S(\d+)\]",
    re.IGNORECASE,
)


@dataclass
class QualityResult:
    passed: bool
    issues: list[str]


def _source_ids(
    answer: str,
) -> set[int]:
    return {
        int(value)
        for value
        in _SOURCE_ID.findall(
            answer
        )
    }


def verify_answer(
    *,
    answer: str,
    route: Route,
    web_results: list[WebResult],
    project_files: list[str],
    done_reason: str | None,
) -> QualityResult:
    issues: list[str] = []

    stripped = answer.strip()
    lowered = (
        stripped.casefold()
    )

    # ---------------------------------------------------------
    # Completion
    # ---------------------------------------------------------

    if not stripped:
        issues.append(
            "Answer is empty."
        )

    if (
        done_reason
        == "length"
    ):
        issues.append(
            "Answer still ended because of the token limit."
        )

    # ---------------------------------------------------------
    # Web grounding
    # ---------------------------------------------------------

    if route.execution.startswith(
        "web"
    ):
        used = _source_ids(
            answer
        )

        valid = set(
            range(
                1,
                len(
                    web_results
                ) + 1,
            )
        )

        invalid = (
            used
            - valid
        )

        if invalid:
            issues.append(
                "Invalid source IDs: "
                + ", ".join(
                    f"S{x}"
                    for x
                    in sorted(
                        invalid
                    )
                )
            )

        if (
            web_results
            and not used
        ):
            issues.append(
                "Web answer has no inline source citations."
            )

        # -----------------------------------------------------
        # Citation-to-evidence support
        # -----------------------------------------------------

        if (
            web_results
            and used
            and not invalid
        ):
            weak_citations = (
                find_weak_citations(
                    answer=answer,
                    web_results=web_results,
                )
            )

            # Avoid flooding repair with many near-identical
            # citation messages. Three concrete examples are
            # enough to diagnose the problem.
            for weak in (
                weak_citations[:3]
            ):
                claim = (
                    " ".join(
                        weak.claim.split()
                    )
                )

                if len(claim) > 160:
                    claim = (
                        claim[:157]
                        + "..."
                    )

                issues.append(
                    (
                        f"Citation [S{weak.source_id}] "
                        "is weakly supported by its retrieved "
                        f"source (similarity "
                        f"{weak.score:.2f}) near claim: "
                        f"{claim}"
                    )
                )

    # ---------------------------------------------------------
    # Research contract
    # ---------------------------------------------------------

    if (
        route.execution
        == "web_research"
    ):
        used = _source_ids(
            answer
        )

        if len(used) < 2:
            issues.append(
                "Research answer uses fewer than two sources."
            )

        research_method_signals = (
            "to research ",
            "you can follow these steps",
            "start by identifying",
            "use academic search engines",
        )

        if any(
            signal in lowered
            for signal
            in research_method_signals
        ):
            issues.append(
                "Research answer explains how to research "
                "instead of presenting findings."
            )

        comparison_signals = (
            "however",
            "whereas",
            "in contrast",
            "similarly",
            "unlike",
            "both ",
            "limitation",
            "tradeoff",
            "agreement",
            "disagree",
            "differ",
            "compared",
            "comparison",
        )

        if not any(
            signal in lowered
            for signal
            in comparison_signals
        ):
            issues.append(
                "Research answer does not meaningfully "
                "compare the evidence."
            )

    # ---------------------------------------------------------
    # Project grounding
    # ---------------------------------------------------------

    if (
        route.execution
        == "project"
    ):
        if not project_files:
            issues.append(
                "Project answer has no retrieved source files."
            )

        if (
            route.template
            == "explain-code"
            and (
                "## example usage"
                in lowered
                or "### example usage"
                in lowered
            )
        ):
            issues.append(
                "Explain-code answer generated an "
                "Example Usage section."
            )

    return QualityResult(
        passed=not issues,
        issues=issues,
    )