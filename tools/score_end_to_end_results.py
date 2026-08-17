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

JUDGE_PROMPT_PATH = (
    ROOT
    / "prompts"
    / "quality"
    / "judge.md"
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


def _judge_schema(
    *,
    required_count: int,
    forbidden_count: int,
) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "passed": {
                "type": "boolean",
            },
            "score": {
                "type": "integer",
                "minimum": 0,
                "maximum": 5,
            },
            "required_passed": {
                "type": "array",
                "items": {
                    "type": "boolean",
                },
                "minItems": required_count,
                "maxItems": required_count,
            },
            "required_reasons": {
                "type": "array",
                "items": {
                    "type": "string",
                },
                "minItems": required_count,
                "maxItems": required_count,
            },
            "forbidden_violated": {
                "type": "array",
                "items": {
                    "type": "boolean",
                },
                "minItems": forbidden_count,
                "maxItems": forbidden_count,
            },
            "forbidden_reasons": {
                "type": "array",
                "items": {
                    "type": "string",
                },
                "minItems": forbidden_count,
                "maxItems": forbidden_count,
            },
            "issues": {
                "type": "array",
                "items": {
                    "type": "string",
                },
            },
        },
        "required": [
            "passed",
            "score",
            "required_passed",
            "required_reasons",
            "forbidden_violated",
            "forbidden_reasons",
            "issues",
        ],
        "additionalProperties": False,
    }


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


def _validate_judgment(
    value: Any,
    *,
    required_count: int,
    forbidden_count: int,
) -> dict[str, Any]:
    if not isinstance(
        value,
        dict,
    ):
        raise ValueError(
            "Judge result is not an object"
        )

    expected_fields = {
        "passed",
        "score",
        "required_passed",
        "required_reasons",
        "forbidden_violated",
        "forbidden_reasons",
        "issues",
    }

    if set(value) != expected_fields:
        raise ValueError(
            "Judge result fields do not "
            "match the required schema"
        )

    passed = value[
        "passed"
    ]

    score = value[
        "score"
    ]

    if not isinstance(
        passed,
        bool,
    ):
        raise ValueError(
            "Judge 'passed' is not boolean"
        )

    if (
        not isinstance(
            score,
            int,
        )
        or isinstance(
            score,
            bool,
        )
        or not 0 <= score <= 5
    ):
        raise ValueError(
            "Judge score must be an integer "
            "from 0 through 5"
        )

    required_passed = (
        _validate_boolean_list(
            value[
                "required_passed"
            ],
            expected_length=(
                required_count
            ),
            field=(
                "required_passed"
            ),
        )
    )

    _validate_string_list(
        value[
            "required_reasons"
        ],
        expected_length=(
            required_count
        ),
        field=(
            "required_reasons"
        ),
    )

    forbidden_violated = (
        _validate_boolean_list(
            value[
                "forbidden_violated"
            ],
            expected_length=(
                forbidden_count
            ),
            field=(
                "forbidden_violated"
            ),
        )
    )

    _validate_string_list(
        value[
            "forbidden_reasons"
        ],
        expected_length=(
            forbidden_count
        ),
        field=(
            "forbidden_reasons"
        ),
    )

    _validate_string_list(
        value[
            "issues"
        ],
        expected_length=None,
        field="issues",
    )

    expected_pass = (
        score >= 4
        and all(
            required_passed
        )
        and not any(
            forbidden_violated
        )
    )

    if passed != expected_pass:
        raise ValueError(
            "Judge 'passed' is inconsistent "
            "with score and rubric results"
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
            position = (
                content.find(
                    before
                )
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


def _judge_once(
    *,
    model: str,
    system_prompt: str,
    request: dict[str, Any],
    required_count: int,
    forbidden_count: int,
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
            "format": _judge_schema(
                required_count=(
                    required_count
                ),
                forbidden_count=(
                    forbidden_count
                ),
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

    judgment = (
        _validate_judgment(
            parsed,
            required_count=(
                required_count
            ),
            forbidden_count=(
                forbidden_count
            ),
        )
    )

    return {
        "judgment": judgment,
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

    required_count = len(
        required_points
    )

    forbidden_count = len(
        forbidden_points
    )

    system_prompt = (
        JUDGE_PROMPT_PATH
        .read_text(
            encoding="utf-8"
        )
        .strip()
    )

    request = {
        "user_request": prompt,
        "evaluation_context": (
            rubric.get(
                "evaluation_context",
                [],
            )
        ),
        "required_points": (
            required_points
        ),
        "forbidden_points": (
            forbidden_points
        ),
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
            result = _judge_once(
                model=model,
                system_prompt=(
                    system_prompt
                ),
                request=request,
                required_count=(
                    required_count
                ),
                forbidden_count=(
                    forbidden_count
                ),
            )

            result[
                "judge_attempts"
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

            deterministic_passed = (
                all(
                    check["passed"]
                    for check in (
                        deterministic_checks
                    )
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