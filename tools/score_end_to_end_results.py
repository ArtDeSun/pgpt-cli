from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from pgpt.config import CONFIG
from pgpt.generation.ollama import ollama_url
from pgpt.runtime.http import json_request


ROOT = Path(__file__).resolve().parents[1]

CASES_PATH = (
    ROOT
    / "evals"
    / "end_to_end_cases.json"
)

RESULTS_PATH = (
    ROOT
    / "evals"
    / "end_to_end_results.json"
)

OUTPUT_PATH = (
    ROOT
    / "evals"
    / "end_to_end_scored.json"
)

REQUIRED_CRITERION_PROMPT_PATH = (
    ROOT
    / "prompts"
    / "quality"
    / "required-criterion.md"
)

FORBIDDEN_CRITERION_PROMPT_PATH = (
    ROOT
    / "prompts"
    / "quality"
    / "forbidden-criterion.md"
)

_SOURCE_ID = re.compile(
    r"\[S(\d+)\]",
    re.IGNORECASE,
)


def _load_json(
    path: Path,
) -> Any:
    with path.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def _save_json(
    path: Path,
    value: Any,
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            value,
            file,
            indent=2,
            ensure_ascii=False,
        )
        file.write("\n")


def _criterion_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "matched": {
                "type": "boolean",
            },
            "reason": {
                "type": "string",
            },
        },
        "required": [
            "matched",
            "reason",
        ],
        "additionalProperties": False,
    }


def _run_deterministic_check(
    *,
    answer: str,
    check: dict[str, Any],
) -> dict[str, Any]:
    check_type = check.get(
        "type"
    )

    if check_type == "inline_source_ids":
        before = check.get(
            "before"
        )

        content = answer

        if isinstance(
            before,
            str,
        ):
            position = content.find(
                before
            )

            if position >= 0:
                content = content[
                    :position
                ]

        source_ids = {
            int(value)
            for value in (
                _SOURCE_ID.findall(
                    content
                )
            )
        }

        minimum_distinct = int(
            check.get(
                "minimum_distinct",
                1,
            )
        )

        passed = (
            len(source_ids)
            >= minimum_distinct
        )

        return {
            "type": check_type,
            "passed": passed,
            "details": {
                "distinct_source_ids": (
                    sorted(
                        source_ids
                    )
                ),
                "count": len(
                    source_ids
                ),
                "minimum_distinct": (
                    minimum_distinct
                ),
            },
        }

    if check_type == "forbidden_regex":
        patterns = check.get(
            "patterns",
            [],
        )

        if not isinstance(
            patterns,
            list,
        ):
            raise ValueError(
                "forbidden_regex patterns "
                "must be a list"
            )

        matches: list[str] = []

        for pattern in patterns:
            if not isinstance(
                pattern,
                str,
            ):
                raise ValueError(
                    "forbidden_regex patterns "
                    "must contain strings"
                )

            if re.search(
                pattern,
                answer,
                re.IGNORECASE,
            ):
                matches.append(
                    pattern
                )

        return {
            "type": check_type,
            "passed": not matches,
            "details": {
                "matched_patterns": (
                    matches
                ),
            },
        }

    raise ValueError(
        "Unknown deterministic check "
        f"type: {check_type!r}"
    )


def _run_deterministic_checks(
    *,
    answer: str,
    checks: list[
        dict[str, Any]
    ],
) -> list[dict[str, Any]]:
    return [
        _run_deterministic_check(
            answer=answer,
            check=check,
        )
        for check in checks
    ]


def _load_criterion_prompt(
    criterion_type: str,
) -> str:
    paths = {
        "required": (
            REQUIRED_CRITERION_PROMPT_PATH
        ),
        "forbidden": (
            FORBIDDEN_CRITERION_PROMPT_PATH
        ),
    }

    try:
        path = paths[
            criterion_type
        ]
    except KeyError as exc:
        raise ValueError(
            criterion_type
        ) from exc

    return path.read_text(
        encoding="utf-8"
    ).strip()


def _judge_criterion(
    *,
    model: str,
    criterion_type: str,
    prompt: str,
    answer: str,
    criterion: str,
    evaluation_context: Any,
    evaluation_evidence: Any,
) -> dict[str, Any]:
    system_prompt = _load_criterion_prompt(
        criterion_type
    )

    request = {
        "user_request": prompt,
        "evaluation_context": (
            evaluation_context
        ),
        "evaluation_evidence": (
            evaluation_evidence
        ),
        "answer": answer,
        "criterion": criterion,
    }

    response = json_request(
        "POST",
        ollama_url(
            "/api/chat"
        ),
        payload={
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        system_prompt
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        request,
                        ensure_ascii=False,
                        indent=2,
                    ),
                },
            ],
            "stream": False,
            "think": False,
            "format": (
                _criterion_schema()
            ),
            "keep_alive": "10m",
            "options": {
                "temperature": 0.0,
                "num_ctx": int(
                    CONFIG.get(
                        "quality",
                        {},
                    ).get(
                        "judge_num_ctx",
                        4096,
                    )
                ),
                "num_predict": int(
                    CONFIG.get(
                        "quality",
                        {},
                    ).get(
                        "criterion_max_tokens",
                        180,
                    )
                ),
            },
        },
        timeout=float(
            CONFIG.get(
                "quality",
                {},
            ).get(
                "judge_timeout_seconds",
                120,
            )
        ),
    )

    if not isinstance(
        response,
        dict,
    ):
        raise ValueError(
            "Ollama returned no judge "
            "response object"
        )

    message = response.get(
        "message"
    )

    if not isinstance(
        message,
        dict,
    ):
        raise ValueError(
            "Ollama judge response "
            "has no message"
        )

    content = str(
        message.get(
            "content",
            "",
        )
    ).strip()

    if not content:
        raise ValueError(
            "Judge returned empty content"
        )

    result = json.loads(
        content
    )

    if not isinstance(
        result,
        dict,
    ):
        raise ValueError(
            "Criterion result is not "
            "an object"
        )

    if set(result) != {
        "matched",
        "reason",
    }:
        raise ValueError(
            "Criterion result fields do not "
            "match the required schema"
        )

    matched = result[
        "matched"
    ]

    reason = result[
        "reason"
    ]

    if not isinstance(
        matched,
        bool,
    ):
        raise ValueError(
            "Criterion matched result "
            "is not boolean"
        )

    if not isinstance(
        reason,
        str,
    ):
        raise ValueError(
            "Criterion reason is not "
            "a string"
        )

    return {
        "matched": matched,
        "reason": reason,
        "judge_metrics": {
            "done_reason": (
                response.get(
                    "done_reason"
                )
            ),
            "load_duration": (
                response.get(
                    "load_duration",
                    0,
                )
            ),
            "prompt_eval_duration": (
                response.get(
                    "prompt_eval_duration",
                    0,
                )
            ),
            "prompt_eval_count": (
                response.get(
                    "prompt_eval_count",
                    0,
                )
            ),
            "eval_duration": (
                response.get(
                    "eval_duration",
                    0,
                )
            ),
            "eval_count": (
                response.get(
                    "eval_count",
                    0,
                )
            ),
            "total_duration": (
                response.get(
                    "total_duration",
                    0,
                )
            ),
        },
    }


def _score_judgment(
    *,
    required_passed: list[bool],
    forbidden_violated: list[bool],
) -> int:
    if (
        all(required_passed)
        and not any(
            forbidden_violated
        )
    ):
        return 5

    if any(
        forbidden_violated
    ):
        return 2

    if not required_passed:
        return 3

    ratio = (
        sum(required_passed)
        / len(required_passed)
    )

    if ratio >= 0.5:
        return 3

    return 1


def _judge(
    *,
    model: str,
    prompt: str,
    answer: str,
    rubric: dict[str, Any],
    evaluation_evidence: Any = None,
) -> dict[str, Any]:
    required_points = rubric.get(
        "required_points",
        [],
    )

    forbidden_points = rubric.get(
        "forbidden_points",
        [],
    )

    evaluation_context = rubric.get(
        "evaluation_context",
        [],
    )

    if not isinstance(
        required_points,
        list,
    ):
        raise ValueError(
            "required_points must be "
            "a list"
        )

    if not isinstance(
        forbidden_points,
        list,
    ):
        raise ValueError(
            "forbidden_points must be "
            "a list"
        )

    required_results = [
        _judge_criterion(
            model=model,
            criterion_type="required",
            prompt=prompt,
            answer=answer,
            criterion=criterion,
            evaluation_context=(
                evaluation_context
            ),
            evaluation_evidence=(
                evaluation_evidence
            ),
        )
        for criterion in required_points
    ]

    forbidden_results = [
        _judge_criterion(
            model=model,
            criterion_type="forbidden",
            prompt=prompt,
            answer=answer,
            criterion=criterion,
            evaluation_context=(
                evaluation_context
            ),
            evaluation_evidence=(
                evaluation_evidence
            ),
        )
        for criterion in forbidden_points
    ]

    required_passed = [
        result["matched"]
        for result in required_results
    ]

    required_reasons = [
        result["reason"]
        for result in required_results
    ]

    forbidden_violated = [
        result["matched"]
        for result in forbidden_results
    ]

    forbidden_reasons = [
        result["reason"]
        for result in forbidden_results
    ]

    score = _score_judgment(
        required_passed=(
            required_passed
        ),
        forbidden_violated=(
            forbidden_violated
        ),
    )

    passed = (
        score >= 4
        and all(
            required_passed
        )
        and not any(
            forbidden_violated
        )
    )

    issues: list[str] = []

    for result in required_results:
        if not result[
            "matched"
        ]:
            issues.append(
                result["reason"]
            )

    for result in forbidden_results:
        if result[
            "matched"
        ]:
            issues.append(
                result["reason"]
            )

    total_metrics = {
        "load_duration": 0,
        "prompt_eval_duration": 0,
        "prompt_eval_count": 0,
        "eval_duration": 0,
        "eval_count": 0,
        "total_duration": 0,
    }

    all_results = (
        required_results
        + forbidden_results
    )

    for result in all_results:
        metrics = result[
            "judge_metrics"
        ]

        for key in total_metrics:
            total_metrics[key] += int(
                metrics.get(
                    key,
                    0,
                )
                or 0
            )

    return {
        "judgment": {
            "passed": passed,
            "score": score,
            "required_passed": (
                required_passed
            ),
            "required_reasons": (
                required_reasons
            ),
            "forbidden_violated": (
                forbidden_violated
            ),
            "forbidden_reasons": (
                forbidden_reasons
            ),
            "issues": issues,
        },
        "judge_metrics": {
            **total_metrics,
            "criterion_count": len(
                all_results
            ),
        },
    }


def _case_map() -> dict[
    str,
    dict[str, Any],
]:
    cases = _load_json(
        CASES_PATH
    )

    return {
        case["id"]: case
        for case in cases
    }


def _selected_rows(
    rows: list[dict[str, Any]],
    case_ids: list[str],
) -> list[dict[str, Any]]:
    if not case_ids:
        return rows

    wanted = set(
        case_ids
    )

    missing = (
        wanted
        - {
            row["id"]
            for row in rows
        }
    )

    if missing:
        raise ValueError(
            "Unknown or missing result cases: "
            + ", ".join(
                sorted(
                    missing
                )
            )
        )

    return [
        row
        for row in rows
        if row["id"] in wanted
    ]


def _score_row(
    *,
    row: dict[str, Any],
    case: dict[str, Any],
    model: str,
) -> dict[str, Any]:
    scored = dict(
        row
    )

    rubric = case.get(
        "quality_rubric",
        {},
    )

    deterministic_checks = (
        rubric.get(
            "deterministic_checks",
            [],
        )
    )

    if not isinstance(
        deterministic_checks,
        list,
    ):
        raise ValueError(
            "deterministic_checks must "
            "be a list"
        )

    deterministic_results = (
        _run_deterministic_checks(
            answer=str(
                row.get(
                    "answer",
                    "",
                )
            ),
            checks=(
                deterministic_checks
            ),
        )
    )

    deterministic_passed = all(
        result["passed"]
        for result
        in deterministic_results
    )

    scored[
        "deterministic_checks"
    ] = deterministic_results

    scored[
        "deterministic_passed"
    ] = deterministic_passed

    judge_result = _judge(
        model=model,
        prompt=str(
            row.get(
                "prompt",
                case.get(
                    "prompt",
                    "",
                ),
            )
        ),
        answer=str(
            row.get(
                "answer",
                "",
            )
        ),
        rubric=rubric,
        evaluation_evidence=(
            row.get(
                "evaluation_evidence"
            )
        ),
    )

    judgment = judge_result[
        "judgment"
    ]

    semantic_passed = bool(
        judgment[
            "passed"
        ]
    )

    quality_passed = (
        bool(
            row.get(
                "route_passed",
                False,
            )
        )
        and deterministic_passed
        and semantic_passed
    )

    scored[
        "judge_model"
    ] = model

    scored[
        "judgment"
    ] = judgment

    scored[
        "semantic_passed"
    ] = semantic_passed

    scored[
        "quality_passed"
    ] = quality_passed

    scored[
        "judge_attempts"
    ] = 1

    scored[
        "judge_metrics"
    ] = judge_result[
        "judge_metrics"
    ]

    scored.pop(
        "judge_error",
        None,
    )

    return scored


def _print_scored_row(
    row: dict[str, Any],
) -> None:
    judgment = row.get(
        "judgment",
        {},
    )

    print(
        "semantic passed:",
        row.get(
            "semantic_passed"
        ),
    )

    print(
        "score:",
        judgment.get(
            "score"
        ),
    )

    print(
        "deterministic passed:",
        row.get(
            "deterministic_passed"
        ),
    )

    for result in row.get(
        "deterministic_checks",
        [],
    ):
        status = (
            "PASS"
            if result.get(
                "passed"
            )
            else "FAIL"
        )

        print(
            "  check:",
            result.get(
                "type"
            ),
            status,
        )

    print(
        "judge attempts:",
        row.get(
            "judge_attempts"
        ),
    )

    print(
        "quality passed:",
        row.get(
            "quality_passed"
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--model",
        required=True,
    )

    parser.add_argument(
        "--case",
        dest="case_ids",
        action="append",
        default=[],
    )

    args = parser.parse_args()

    rows = _load_json(
        RESULTS_PATH
    )

    if not isinstance(
        rows,
        list,
    ):
        raise ValueError(
            "End-to-end results must "
            "be a list"
        )

    cases = _case_map()

    selected = _selected_rows(
        rows,
        args.case_ids,
    )

    scored_rows: list[
        dict[str, Any]
    ] = []

    for row in selected:
        case_id = row[
            "id"
        ]

        case = cases.get(
            case_id
        )

        if case is None:
            raise ValueError(
                "Missing end-to-end case: "
                f"{case_id}"
            )

        print()
        print(
            "=" * 72
        )
        print(
            case_id
        )
        print(
            "=" * 72
        )

        try:
            scored = _score_row(
                row=row,
                case=case,
                model=args.model,
            )

            _print_scored_row(
                scored
            )

        except Exception as exc:
            scored = dict(
                row
            )

            scored[
                "judge_model"
            ] = args.model

            scored[
                "judge_error"
            ] = (
                f"{type(exc).__name__}: "
                f"{exc}"
            )

            print(
                "ERROR:",
                scored[
                    "judge_error"
                ],
            )

        scored_rows.append(
            scored
        )

    _save_json(
        OUTPUT_PATH,
        scored_rows,
    )

    print()
    print(
        "Saved:",
        OUTPUT_PATH,
    )


if __name__ == "__main__":
    main()