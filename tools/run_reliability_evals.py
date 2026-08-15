from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path
from typing import Any

from pgpt.runtime.pipeline import run
from tools.score_end_to_end_results import (
    _judge,
    _run_deterministic_checks,
)


ROOT = Path(__file__).resolve().parents[1]

CASES_PATH = (
    ROOT
    / "evals"
    / "end_to_end_cases.json"
)

OUTPUT_PATH = (
    ROOT
    / "evals"
    / "reliability_results.json"
)


def _load_json(
    path: Path,
    *,
    default: Any,
) -> Any:
    if not path.exists():
        return default

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


def _route_value(
    route,
    name: str,
):
    if name == "project":
        return route.project

    return getattr(
        route,
        name,
    )


def _route_checks(
    *,
    route,
    expected: dict[str, Any],
) -> dict[str, Any]:
    checks = {}

    for field, expected_value in (
        expected.items()
    ):
        actual = _route_value(
            route,
            field,
        )

        checks[field] = {
            "expected": expected_value,
            "actual": actual,
            "passed": (
                actual
                == expected_value
            ),
        }

    return checks


def _successful_judge_runs(
    runs: list[
        dict[str, Any]
    ],
) -> list[dict[str, Any]]:
    return [
        run
        for run in runs
        if not run.get(
            "judge_error"
        )
    ]


def _case_summary(
    runs: list[
        dict[str, Any]
    ],
) -> dict[str, Any]:
    if not runs:
        return {
            "runs": 0,
        }

    judged_runs = (
        _successful_judge_runs(
            runs
        )
    )

    route_values = [
        run[
            "route_passed"
        ]
        for run in runs
    ]

    deterministic_values = [
        run[
            "deterministic_passed"
        ]
        for run in runs
    ]

    quality_values = [
        run[
            "quality_passed"
        ]
        for run in runs
    ]

    generation_elapsed = [
        run[
            "generation_elapsed_seconds"
        ]
        for run in runs
    ]

    judge_elapsed = [
        run[
            "judge_elapsed_seconds"
        ]
        for run in runs
    ]

    total_elapsed = [
        run[
            "total_elapsed_seconds"
        ]
        for run in runs
    ]

    semantic_values = [
        run[
            "semantic_passed"
        ]
        for run in judged_runs
    ]

    scores = [
        run[
            "score"
        ]
        for run in judged_runs
    ]

    judge_error_count = (
        len(runs)
        - len(judged_runs)
    )

    summary: dict[
        str,
        Any,
    ] = {
        "runs": len(runs),

        "judge_success_count": (
            len(judged_runs)
        ),
        "judge_error_count": (
            judge_error_count
        ),
        "judge_success_rate": (
            len(judged_runs)
            / len(runs)
        ),

        "route_pass_count": sum(
            route_values
        ),
        "route_pass_rate": (
            sum(route_values)
            / len(route_values)
        ),

        "deterministic_pass_count": (
            sum(
                deterministic_values
            )
        ),
        "deterministic_pass_rate": (
            sum(
                deterministic_values
            )
            / len(
                deterministic_values
            )
        ),

        "quality_pass_count": sum(
            quality_values
        ),
        "quality_pass_rate": (
            sum(quality_values)
            / len(quality_values)
        ),

        "generation_elapsed_mean_seconds": (
            statistics.mean(
                generation_elapsed
            )
        ),

        "judge_elapsed_mean_seconds": (
            statistics.mean(
                judge_elapsed
            )
        ),

        "total_elapsed_mean_seconds": (
            statistics.mean(
                total_elapsed
            )
        ),
    }

    if judged_runs:
        summary.update(
            {
                "semantic_pass_count": (
                    sum(
                        semantic_values
                    )
                ),
                "semantic_pass_rate": (
                    sum(
                        semantic_values
                    )
                    / len(
                        semantic_values
                    )
                ),
                "score_mean": (
                    statistics.mean(
                        scores
                    )
                ),
                "score_min": min(
                    scores
                ),
                "score_max": max(
                    scores
                ),
            }
        )

    else:
        summary.update(
            {
                "semantic_pass_count": 0,
                "semantic_pass_rate": None,
                "score_mean": None,
                "score_min": None,
                "score_max": None,
            }
        )

    return summary


def _overall_summary(
    cases: list[
        dict[str, Any]
    ],
) -> dict[str, Any]:
    all_runs = [
        run
        for case in cases
        for run in case.get(
            "runs",
            [],
        )
    ]

    if not all_runs:
        return {
            "cases": len(cases),
            "runs": 0,
        }

    judged_runs = (
        _successful_judge_runs(
            all_runs
        )
    )

    completed_cases = [
        case
        for case in cases
        if case.get(
            "summary",
            {},
        ).get(
            "runs",
            0,
        )
        > 0
    ]

    fully_reliable = [
        (
            case[
                "summary"
            ].get(
                "quality_pass_rate",
                0.0,
            )
            == 1.0
            and case[
                "summary"
            ].get(
                "judge_error_count",
                0,
            )
            == 0
        )
        for case in (
            completed_cases
        )
    ]

    generation_elapsed = [
        run[
            "generation_elapsed_seconds"
        ]
        for run in all_runs
    ]

    judge_elapsed = [
        run[
            "judge_elapsed_seconds"
        ]
        for run in all_runs
    ]

    total_elapsed = [
        run[
            "total_elapsed_seconds"
        ]
        for run in all_runs
    ]

    result: dict[
        str,
        Any,
    ] = {
        "cases": len(cases),
        "runs": len(all_runs),

        "fully_reliable_case_count": (
            sum(
                fully_reliable
            )
        ),
        "fully_reliable_case_rate": (
            sum(
                fully_reliable
            )
            / len(
                completed_cases
            )
            if completed_cases
            else 0.0
        ),

        "judge_success_count": (
            len(judged_runs)
        ),
        "judge_error_count": (
            len(all_runs)
            - len(judged_runs)
        ),
        "judge_success_rate": (
            len(judged_runs)
            / len(all_runs)
        ),

        "route_pass_count": sum(
            run[
                "route_passed"
            ]
            for run in all_runs
        ),
        "route_pass_rate": (
            sum(
                run[
                    "route_passed"
                ]
                for run in all_runs
            )
            / len(all_runs)
        ),

        "deterministic_pass_count": (
            sum(
                run[
                    "deterministic_passed"
                ]
                for run in all_runs
            )
        ),
        "deterministic_pass_rate": (
            sum(
                run[
                    "deterministic_passed"
                ]
                for run in all_runs
            )
            / len(all_runs)
        ),

        "quality_pass_count": sum(
            run[
                "quality_passed"
            ]
            for run in all_runs
        ),
        "quality_pass_rate": (
            sum(
                run[
                    "quality_passed"
                ]
                for run in all_runs
            )
            / len(all_runs)
        ),

        "generation_elapsed_mean_seconds": (
            statistics.mean(
                generation_elapsed
            )
        ),

        "judge_elapsed_mean_seconds": (
            statistics.mean(
                judge_elapsed
            )
        ),

        "total_elapsed_mean_seconds": (
            statistics.mean(
                total_elapsed
            )
        ),
    }

    if judged_runs:
        result.update(
            {
                "semantic_pass_count": (
                    sum(
                        run[
                            "semantic_passed"
                        ]
                        for run in (
                            judged_runs
                        )
                    )
                ),
                "semantic_pass_rate": (
                    sum(
                        run[
                            "semantic_passed"
                        ]
                        for run in (
                            judged_runs
                        )
                    )
                    / len(
                        judged_runs
                    )
                ),
                "score_mean": (
                    statistics.mean(
                        run[
                            "score"
                        ]
                        for run in (
                            judged_runs
                        )
                    )
                ),
            }
        )

    else:
        result.update(
            {
                "semantic_pass_count": 0,
                "semantic_pass_rate": None,
                "score_mean": None,
            }
        )

    return result


def _ordered_case_results(
    *,
    selected_cases: list[
        dict[str, Any]
    ],
    records: dict[
        str,
        dict[str, Any],
    ],
) -> list[dict[str, Any]]:
    return [
        records[
            case["id"]
        ]
        for case in selected_cases
        if case["id"] in records
    ]


def _build_output(
    *,
    judge_model: str,
    requested_runs: int,
    selected_cases: list[
        dict[str, Any]
    ],
    records: dict[
        str,
        dict[str, Any],
    ],
    generation_model: str | None,
) -> dict[str, Any]:
    case_results = (
        _ordered_case_results(
            selected_cases=(
                selected_cases
            ),
            records=records,
        )
    )

    for case_result in (
        case_results
    ):
        case_result[
            "summary"
        ] = _case_summary(
            case_result.get(
                "runs",
                [],
            )
        )

    return {
        "generation_model_override": (
            generation_model
        ),
        "judge_model": (
            judge_model
        ),
        "requested_runs_per_case": (
            requested_runs
        ),
        "cases": case_results,
        "summary": (
            _overall_summary(
                case_results
            )
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--case",
        action="append",
        dest="case_ids",
    )

    parser.add_argument(
        "--runs",
        type=int,
        default=5,
    )

    parser.add_argument(
        "--judge-model",
        required=True,
    )

    parser.add_argument(
        "--generation-model",
        default=None,
        help=(
            "Override the runtime generation model "
            "without changing the expected route."
        ),
    )

    parser.add_argument(
        "--project",
        default="vibemaster",
    )

    parser.add_argument(
        "--force",
        action="store_true",
    )

    parser.add_argument(
        "--fresh",
        action="store_true",
    )

    args = parser.parse_args()

    if args.runs <= 0:
        raise ValueError(
            "--runs must be greater "
            "than zero"
        )

    cases = _load_json(
        CASES_PATH,
        default=[],
    )

    if not isinstance(
        cases,
        list,
    ):
        raise RuntimeError(
            "end_to_end_cases.json "
            "must contain a list"
        )

    selected_ids = (
        set(
            args.case_ids
        )
        if args.case_ids
        else None
    )

    selected_cases = [
        case
        for case in cases
        if (
            selected_ids is None
            or case["id"]
            in selected_ids
        )
    ]

    if selected_ids is not None:
        found_ids = {
            case["id"]
            for case in (
                selected_cases
            )
        }

        missing_ids = (
            selected_ids
            - found_ids
        )

        if missing_ids:
            raise RuntimeError(
                "Unknown case IDs: "
                + ", ".join(
                    sorted(
                        missing_ids
                    )
                )
            )

    existing = (
        {}
        if args.fresh
        else _load_json(
            OUTPUT_PATH,
            default={},
        )
    )

    existing_cases = (
        existing.get(
            "cases",
            [],
        )
        if isinstance(
            existing,
            dict,
        )
        else []
    )

    existing_map = {
        item.get(
            "case_id"
        ): item
        for item in existing_cases
        if (
            isinstance(
                item,
                dict,
            )
            and item.get(
                "case_id"
            )
        )
    }

    records: dict[
        str,
        dict[str, Any],
    ] = {}

    for case in selected_cases:
        case_id = case[
            "id"
        ]

        old = existing_map.get(
            case_id,
            {},
        )

        old_runs = (
            old.get(
                "runs",
                [],
            )
            if (
                isinstance(
                    old,
                    dict,
                )
                and not args.fresh
                and not args.force
            )
            else []
        )

        if not isinstance(
            old_runs,
            list,
        ):
            old_runs = []

        records[
            case_id
        ] = {
            "case_id": case_id,
            "prompt": case[
                "prompt"
            ],
            "expect": (
                case.get(
                    "expect",
                    {},
                )
            ),
            "quality_rubric": (
                case.get(
                    "quality",
                    {},
                )
            ),
            "runs": old_runs,
        }

    started_all = (
        time.monotonic()
    )

    for case in selected_cases:
        case_id = case[
            "id"
        ]

        record = records[
            case_id
        ]

        current_runs = record[
            "runs"
        ]

        completed = len(
            current_runs
        )

        remaining = max(
            0,
            args.runs
            - completed,
        )

        print()
        print("=" * 72)
        print(case_id)
        print("=" * 72)
        print(
            "existing runs:",
            completed,
        )
        print(
            "runs needed:",
            remaining,
        )

        if remaining == 0:
            print(
                "[skip] requested runs "
                "already completed"
            )
            continue

        rubric = case.get(
            "quality",
            {},
        )

        expected_route = (
            case.get(
                "expect",
                {},
            )
        )

        for _ in range(
            remaining
        ):
            run_number = (
                len(
                    current_runs
                )
                + 1
            )

            print()
            print(
                "-" * 72
            )
            print(
                f"{case_id} "
                f"run {run_number}/"
                f"{args.runs}"
            )
            print(
                "-" * 72
            )

            generation_started = (
                time.monotonic()
            )

            result = run(
                case["prompt"],
                project_name=(
                    args.project
                ),
                model_override=(
                    args.generation_model
                ),
                echo_route=True,
            )

            generation_elapsed = (
                time.monotonic()
                - generation_started
            )

            route_checks = (
                _route_checks(
                    route=(
                        result.route
                    ),
                    expected=(
                        expected_route
                    ),
                )
            )

            if (
                args.generation_model
                is not None
                and "model"
                in route_checks
            ):
                route_checks[
                    "model"
                ] = {
                    "expected": (
                        args.generation_model
                    ),
                    "actual": (
                        result.route.model
                    ),
                    "passed": (
                        result.route.model
                        == args.generation_model
                    ),
                }

            route_passed = all(
                check[
                    "passed"
                ]
                for check in (
                    route_checks.values()
                )
            )

            deterministic_checks = (
                _run_deterministic_checks(
                    answer=(
                        result.answer
                    ),
                    checks=rubric.get(
                        "deterministic_checks",
                        [],
                    ),
                )
            )

            deterministic_passed = (
                all(
                    check[
                        "passed"
                    ]
                    for check in (
                        deterministic_checks
                    )
                )
            )

            judge_started = (
                time.monotonic()
            )

            judge_result = None
            judge_error = None

            try:
                judge_result = _judge(
                    model=(
                        args.judge_model
                    ),
                    prompt=(
                        case["prompt"]
                    ),
                    answer=(
                        result.answer
                    ),
                    rubric=rubric,
                )

            except Exception as exc:
                judge_error = (
                    f"{type(exc).__name__}: "
                    f"{exc}"
                )

            judge_elapsed = (
                time.monotonic()
                - judge_started
            )

            if (
                judge_result
                is not None
            ):
                judgment = (
                    judge_result[
                        "judgment"
                    ]
                )

                semantic_passed = (
                    judgment[
                        "passed"
                    ]
                )

                score = (
                    judgment[
                        "score"
                    ]
                )

                judge_metrics = (
                    judge_result[
                        "judge_metrics"
                    ]
                )

                judge_attempts = (
                    judge_result[
                        "judge_attempts"
                    ]
                )

            else:
                judgment = None
                semantic_passed = False
                score = 0
                judge_metrics = {}
                judge_attempts = 2

            quality_passed = (
                route_passed
                and deterministic_passed
                and semantic_passed
                and judge_error is None
            )

            total_elapsed = (
                generation_elapsed
                + judge_elapsed
            )

            run_record = {
                "run": (
                    run_number
                ),

                "route_checks": (
                    route_checks
                ),
                "route_passed": (
                    route_passed
                ),

                "answer": (
                    result.answer
                ),
                "response_path": str(
                    result.response_path
                ),

                "generation_elapsed_seconds": (
                    round(
                        generation_elapsed,
                        3,
                    )
                ),

                "deterministic_checks": (
                    deterministic_checks
                ),
                "deterministic_passed": (
                    deterministic_passed
                ),

                "semantic_judgment": (
                    judgment
                ),
                "semantic_passed": (
                    semantic_passed
                ),

                "score": score,

                "judge_attempts": (
                    judge_attempts
                ),
                "judge_error": (
                    judge_error
                ),
                "judge_metrics": (
                    judge_metrics
                ),

                "judge_elapsed_seconds": (
                    round(
                        judge_elapsed,
                        3,
                    )
                ),

                "total_elapsed_seconds": (
                    round(
                        total_elapsed,
                        3,
                    )
                ),

                "quality_passed": (
                    quality_passed
                ),
            }

            current_runs.append(
                run_record
            )

            print()
            print(
                "route passed:",
                route_passed,
            )

            print(
                "semantic passed:",
                semantic_passed,
            )

            print(
                "score:",
                score,
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
                    check[
                        "type"
                    ],
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
                judge_attempts,
            )

            if judge_error:
                print(
                    "judge error:",
                    judge_error,
                )

            print(
                "quality passed:",
                quality_passed,
            )

            output = (
                _build_output(
                    generation_model=(
                        args.generation_model
                    ),
                    judge_model=(
                        args.judge_model
                    ),
                    requested_runs=(
                        args.runs
                    ),
                    selected_cases=(
                        selected_cases
                    ),
                    records=records,
                )
            )

            _save_json(
                OUTPUT_PATH,
                output,
            )

    final = _build_output(
        generation_model=(
            args.generation_model
        ),
        judge_model=(
            args.judge_model
        ),
        requested_runs=(
            args.runs
        ),
        selected_cases=(
            selected_cases
        ),
        records=records,
    )

    final[
        "wall_elapsed_seconds"
    ] = round(
        time.monotonic()
        - started_all,
        3,
    )

    _save_json(
        OUTPUT_PATH,
        final,
    )

    print()
    print("=" * 72)
    print(
        "RELIABILITY SUMMARY"
    )
    print("=" * 72)

    for case_result in (
        final[
            "cases"
        ]
    ):
        summary = (
            case_result[
                "summary"
            ]
        )

        runs = summary[
            "runs"
        ]

        print()
        print(
            case_result[
                "case_id"
            ]
        )

        if runs == 0:
            print(
                "  no completed runs"
            )
            continue

        print(
            "  route:",
            (
                f"{summary['route_pass_count']}"
                f"/{runs} "
                f"({summary['route_pass_rate'] * 100:.1f}%)"
            ),
        )

        semantic_rate = (
            summary.get(
                "semantic_pass_rate"
            )
        )

        if (
            semantic_rate
            is not None
        ):
            print(
                "  semantic:",
                (
                    f"{summary['semantic_pass_count']}"
                    f"/{summary['judge_success_count']} "
                    f"({semantic_rate * 100:.1f}%)"
                ),
            )

        print(
            "  deterministic:",
            (
                f"{summary['deterministic_pass_count']}"
                f"/{runs} "
                f"({summary['deterministic_pass_rate'] * 100:.1f}%)"
            ),
        )

        print(
            "  judge:",
            (
                f"{summary['judge_success_count']}"
                f"/{runs} "
                f"({summary['judge_success_rate'] * 100:.1f}%)"
            ),
        )

        print(
            "  quality:",
            (
                f"{summary['quality_pass_count']}"
                f"/{runs} "
                f"({summary['quality_pass_rate'] * 100:.1f}%)"
            ),
        )

        if (
            summary.get(
                "score_mean"
            )
            is not None
        ):
            print(
                "  score mean:",
                round(
                    summary[
                        "score_mean"
                    ],
                    2,
                ),
            )

    overall = final[
        "summary"
    ]

    print()
    print(
        "OVERALL"
    )

    print(
        "  cases:",
        overall[
            "cases"
        ],
    )

    print(
        "  runs:",
        overall[
            "runs"
        ],
    )

    if overall[
        "runs"
    ]:
        print(
            "  fully reliable cases:",
            (
                f"{overall['fully_reliable_case_count']}"
                f"/{overall['cases']} "
                f"({overall['fully_reliable_case_rate'] * 100:.1f}%)"
            ),
        )

        print(
            "  route:",
            (
                f"{overall['route_pass_count']}"
                f"/{overall['runs']} "
                f"({overall['route_pass_rate'] * 100:.1f}%)"
            ),
        )

        print(
            "  deterministic:",
            (
                f"{overall['deterministic_pass_count']}"
                f"/{overall['runs']} "
                f"({overall['deterministic_pass_rate'] * 100:.1f}%)"
            ),
        )

        print(
            "  judge:",
            (
                f"{overall['judge_success_count']}"
                f"/{overall['runs']} "
                f"({overall['judge_success_rate'] * 100:.1f}%)"
            ),
        )

        semantic_rate = (
            overall.get(
                "semantic_pass_rate"
            )
        )

        if semantic_rate is not None:
            print(
                "  semantic:",
                (
                    f"{overall['semantic_pass_count']}"
                    f"/{overall['judge_success_count']} "
                    f"({semantic_rate * 100:.1f}%)"
                ),
            )

        print(
            "  quality:",
            (
                f"{overall['quality_pass_count']}"
                f"/{overall['runs']} "
                f"({overall['quality_pass_rate'] * 100:.1f}%)"
            ),
        )

        if (
            overall.get(
                "score_mean"
            )
            is not None
        ):
            print(
                "  score mean:",
                round(
                    overall[
                        "score_mean"
                    ],
                    2,
                ),
            )

    print()
    print(
        "Saved:",
        OUTPUT_PATH,
    )


if __name__ == "__main__":
    main()