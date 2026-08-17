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


def _validate_boolean_list(
    value: Any,
    *,
    expected_length: int,
    field: str,
) -> list[bool]:
    if not isinstance(
        value,
        list,
    ):
        raise ValueError(
            f"Judge {field!r} is not a list"
        )

    if len(value) != expected_length:
        raise ValueError(
            f"Judge {field!r} returned "
            f"{len(value)} entries; "
            f"expected {expected_length}"
        )

    if not all(
        isinstance(
            item,
            bool,
        )
        for item in value
    ):
        raise ValueError(
            f"Judge {field!r} contains "
            "non-boolean values"
        )

    return value


def _validate_string_list(
    value: Any,
    *,
    expected_length: int | None,
    field: str,
) -> list[str]:
    if not isinstance(
        value,
        list,
    ):
        raise ValueError(
            f"Judge {field!r} is not a list"
        )

    if (
        expected_length is not None
        and len(value)
        != expected_length
    ):
        raise ValueError(
            f"Judge {field!r} returned "
            f"{len(value)} entries; "
            f"expected {expected_length}"
        )

    if not all(
        isinstance(
            item,
            str,
        )
        for item in value
    ):
        raise ValueError(
            f"Judge {field!r} contains "
            "non-string values"
        )

    return value


def _criterion_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "passed": {
                "type": "boolean",
            },
            "reason": {
                "type": "string",
            },
        },
        "required": [
            "passed",
            "reason",
        ],
        "additionalProperties": False,
    }


def _validate_criterion_result(
    value: Any,
) -> dict[str, Any]:
    if not isinstance(
        value,
        dict,
    ):
        raise ValueError(
            "Criterion result is not an object"
        )

    if set(value) != {
        "passed",
        "reason",
    }:
        raise ValueError(
            "Criterion result fields do not "
            "match the required schema"
        )

    if not isinstance(
        value["passed"],
        bool,
    ):
        raise ValueError(
            "Criterion 'passed' is not boolean"
        )

    if not isinstance(
        value["reason"],
        str,
    ):
        raise ValueError(
            "Criterion 'reason' is not a string"
        )

    return value


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


def _judge_criterion_once(
    *,
    model: str,
    system_prompt: str,
    request: dict[str, Any],
) -> dict[str, Any]:
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
                        "judge_max_tokens",
                        550,
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

    parsed = json.loads(
        content
    )

    result = (
        _validate_criterion_result(
            parsed
        )
    )

    return {
        "result": result,
        "metrics": {
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
    system_prompt = (
        _load_criterion_prompt(
            criterion_type
        )
    )

    request = {
        "user_request": prompt,
        "evaluation_context": (
            evaluation_context
        ),
        "criterion": criterion,
        "assistant_answer": answer,
        "evaluation_evidence": (
            evaluation_evidence
        ),
    }

    attempts = 2
    last_error: Exception | None = None

    for attempt in range(
        1,
        attempts + 1,
    ):
        try:
            result = (
                _judge_criterion_once(
                    model=model,
                    system_prompt=(
                        system_prompt
                    ),
                    request=request,
                )
            )

            result[
                "attempts"
            ] = attempt

            return result

        except (
            ValueError,
            json.JSONDecodeError,
        ) as exc:
            last_error = exc

            if attempt >= attempts:
                raise

    assert last_error is not None
    raise last_error


def _sum_metrics(
    metrics: list[
        dict[str, Any]
    ],
) -> dict[str, Any]:
    if not metrics:
        return {
            "done_reason": None,
            "load_duration": 0,
            "prompt_eval_duration": 0,
            "prompt_eval_count": 0,
            "eval_duration": 0,
            "eval_count": 0,
            "total_duration": 0,
        }

    numeric_fields = (
        "load_duration",
        "prompt_eval_duration",
        "prompt_eval_count",
        "eval_duration",
        "eval_count",
        "total_duration",
    )

    result: dict[str, Any] = {
        "done_reason": (
            metrics[-1].get(
                "done_reason"
            )
        ),
    }

    for field in numeric_fields:
        result[field] = sum(
            int(
                metric.get(
                    field,
                    0,
                )
                or 0
            )
            for metric in metrics
        )

    return result


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

    if not isinstance(
        required_points,
        list,
    ):
        raise ValueError(
            "required_points must be a list"
        )

    if not isinstance(
        forbidden_points,
        list,
    ):
        raise ValueError(
            "forbidden_points must be a list"
        )

    if not all(
        isinstance(
            point,
            str,
        )
        for point in required_points
    ):
        raise ValueError(
            "required_points must contain "
            "strings"
        )

    if not all(
        isinstance(
            point,
            str,
        )
        for point in forbidden_points
    ):
        raise ValueError(
            "forbidden_points must contain "
            "strings"
        )

    evaluation_context = rubric.get(
        "evaluation_context",
        [],
    )

    required_passed: list[bool] = []
    required_reasons: list[str] = []

    forbidden_violated: list[bool] = []
    forbidden_reasons: list[str] = []

    metrics: list[
        dict[str, Any]
    ] = []

    total_attempts = 0

    for criterion in required_points:
        result = _judge_criterion(
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

        criterion_result = result[
            "result"
        ]

        required_passed.append(
            criterion_result[
                "passed"
            ]
        )

        required_reasons.append(
            criterion_result[
                "reason"
            ]
        )

        metrics.append(
            result[
                "metrics"
            ]
        )

        total_attempts += int(
            result[
                "attempts"
            ]
        )

    for criterion in forbidden_points:
        result = _judge_criterion(
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

        criterion_result = result[
            "result"
        ]

        forbidden_violated.append(
            criterion_result[
                "passed"
            ]
        )

        forbidden_reasons.append(
            criterion_result[
                "reason"
            ]
        )

        metrics.append(
            result[
                "metrics"
            ]
        )

        total_attempts += int(
            result[
                "attempts"
            ]
        )

    missing_required = sum(
        not passed
        for passed in required_passed
    )

    violated_forbidden = sum(
        forbidden_violated
    )

    if (
        missing_required == 0
        and violated_forbidden == 0
    ):
        score = 5
    elif (
        violated_forbidden == 0
        and missing_required == 1
    ):
        score = 3
    elif (
        violated_forbidden == 0
        and missing_required == 2
    ):
        score = 2
    else:
        score = 1

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

    for index, criterion_passed in enumerate(
        required_passed
    ):
        if not criterion_passed:
            issues.append(
                required_reasons[
                    index
                ]
            )

    for index, violated in enumerate(
        forbidden_violated
    ):
        if violated:
            issues.append(
                forbidden_reasons[
                    index
                ]
            )

    judgment = {
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
    }

    _validate_boolean_list(
        judgment[
            "required_passed"
        ],
        expected_length=len(
            required_points
        ),
        field="required_passed",
    )

    _validate_string_list(
        judgment[
            "required_reasons"
        ],
        expected_length=len(
            required_points
        ),
        field="required_reasons",
    )

    _validate_boolean_list(
        judgment[
            "forbidden_violated"
        ],
        expected_length=len(
            forbidden_points
        ),
        field="forbidden_violated",
    )

    _validate_string_list(
        judgment[
            "forbidden_reasons"
        ],
        expected_length=len(
            forbidden_points
        ),
        field="forbidden_reasons",
    )

    return {
        "judgment": judgment,
        "judge_attempts": (
            total_attempts
        ),
        "judge_metrics": (
            _sum_metrics(
                metrics
            )
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--model",
        required=True,
    )

    parser.add_argument(
        "--case",
        action="append",
        dest="case_ids",
    )

    args = parser.parse_args()

    rows = _load_json(
        RESULTS_PATH
    )

    cases = _load_json(
        CASES_PATH
    )

    if not isinstance(
        rows,
        list,
    ):
        raise RuntimeError(
            "end_to_end_results.json "
            "must contain a list"
        )

    if not isinstance(
        cases,
        list,
    ):
        raise RuntimeError(
            "end_to_end_cases.json "
            "must contain a list"
        )

    case_map = {
        case["id"]: case
        for case in cases
        if (
            isinstance(
                case,
                dict,
            )
            and "id" in case
        )
    }

    selected = (
        set(
            args.case_ids
        )
        if args.case_ids
        else None
    )

    scored: list[
        dict[str, Any]
    ] = []

    for row in rows:
        if (
            selected is not None
            and row["id"]
            not in selected
        ):
            continue

        print()
        print("=" * 72)
        print(
            row["id"]
        )
        print("=" * 72)

        try:
            case = case_map.get(
                row["id"]
            )

            if case is None:
                raise ValueError(
                    "No current eval case "
                    "exists for "
                    f"{row['id']!r}"
                )

            rubric = case.get(
                "quality",
                {},
            )

            deterministic_checks = (
                _run_deterministic_checks(
                    answer=(
                        row["answer"]
                    ),
                    checks=rubric.get(
                        "deterministic_checks",
                        [],
                    ),
                )
            )

            deterministic_passed = all(
                check["passed"]
                for check in (
                    deterministic_checks
                )
            )

            semantic_result = _judge(
                model=args.model,
                prompt=row["prompt"],
                answer=row["answer"],
                rubric=rubric,
                evaluation_evidence=(
                    row.get(
                        "evaluation_evidence"
                    )
                ),
            )

            judgment = (
                semantic_result[
                    "judgment"
                ]
            )

            semantic_passed = (
                judgment[
                    "passed"
                ]
            )

            quality_passed = (
                row.get(
                    "route_passed",
                    True,
                )
                and deterministic_passed
                and semantic_passed
            )

            record = {
                **row,
                "quality_rubric": (
                    rubric
                ),
                "judge_model": (
                    args.model
                ),
                "deterministic_checks": (
                    deterministic_checks
                ),
                "deterministic_passed": (
                    deterministic_passed
                ),
                "judgment": judgment,
                "semantic_passed": (
                    semantic_passed
                ),
                "quality_passed": (
                    quality_passed
                ),
                "judge_attempts": (
                    semantic_result[
                        "judge_attempts"
                    ]
                ),
                "judge_metrics": (
                    semantic_result[
                        "judge_metrics"
                    ]
                ),
            }

            print(
                "semantic passed:",
                semantic_passed,
            )

            print(
                "score:",
                judgment[
                    "score"
                ],
            )

            print(
                "deterministic passed:",
                deterministic_passed,
            )

            for check in (
                deterministic_checks
            ):
                print(
                    "  check:",
                    check["type"],
                    (
                        "PASS"
                        if check[
                            "passed"
                        ]
                        else "FAIL"
                    ),
                )

            print(
                "judge attempts:",
                semantic_result[
                    "judge_attempts"
                ],
            )

            print(
                "quality passed:",
                quality_passed,
            )

        except Exception as exc:
            record = {
                **row,
                "judge_model": (
                    args.model
                ),
                "judge_error": (
                    f"{type(exc).__name__}: "
                    f"{exc}"
                ),
            }

            print(
                "ERROR:",
                record[
                    "judge_error"
                ],
            )

        scored.append(
            record
        )

    _save_json(
        OUTPUT_PATH,
        scored,
    )

    print()
    print(
        "Saved:",
        OUTPUT_PATH,
    )


if __name__ == "__main__":
    main()