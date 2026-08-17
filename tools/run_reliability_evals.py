from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path
from typing import Any

from pgpt.config import CONFIG
from pgpt.retrieval.project import build_context as build_project_context
from pgpt.runtime.pipeline import run
from tools.score_end_to_end_results import _judge, _run_deterministic_checks


ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = ROOT / "evals" / "end_to_end_cases.json"
OUTPUT_PATH = ROOT / "evals" / "reliability_results.json"


def _load_json(path: Path, *, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _save_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(value, file, indent=2, ensure_ascii=False)
        file.write("\n")


def _route_value(route: Any, name: str) -> Any:
    if name == "project":
        return route.project
    return getattr(route, name)


def _route_checks(
    *,
    route: Any,
    expected: dict[str, Any],
) -> dict[str, Any]:
    return {
        field: {
            "expected": expected_value,
            "actual": _route_value(route, field),
            "passed": _route_value(route, field) == expected_value,
        }
        for field, expected_value in expected.items()
    }


def _case_project(
    case: dict[str, Any],
    override: str | None = None,
) -> str:
    if override:
        return override
    expected = case.get("expect", {}).get("project")
    if isinstance(expected, str) and expected:
        return expected
    return str(CONFIG["defaults"]["project"])


def _evaluation_evidence(
    case: dict[str, Any],
) -> dict[str, Any] | None:
    expected = case.get("expect", {}).get("project")
    if not isinstance(expected, str) or not expected:
        return None
    context, files = build_project_context(case["prompt"], expected)
    return {
        "project": expected,
        "files": files,
        "context": context,
    }


def _successful_judge_runs(
    runs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [run_record for run_record in runs if not run_record.get("judge_error")]


def _mean(values: list[float]) -> float:
    return statistics.mean(values) if values else 0.0


def _case_summary(runs: list[dict[str, Any]]) -> dict[str, Any]:
    if not runs:
        return {"runs": 0}

    judged = _successful_judge_runs(runs)
    summary: dict[str, Any] = {
        "runs": len(runs),
        "judge_success_count": len(judged),
        "judge_error_count": len(runs) - len(judged),
        "judge_success_rate": len(judged) / len(runs),
        "route_pass_count": sum(bool(item["route_passed"]) for item in runs),
        "route_pass_rate": sum(bool(item["route_passed"]) for item in runs) / len(runs),
        "deterministic_pass_count": sum(bool(item["deterministic_passed"]) for item in runs),
        "deterministic_pass_rate": sum(bool(item["deterministic_passed"]) for item in runs) / len(runs),
        "quality_pass_count": sum(bool(item["quality_passed"]) for item in runs),
        "quality_pass_rate": sum(bool(item["quality_passed"]) for item in runs) / len(runs),
        "generation_elapsed_mean_seconds": _mean([float(item["generation_elapsed_seconds"]) for item in runs]),
        "judge_elapsed_mean_seconds": _mean([float(item["judge_elapsed_seconds"]) for item in runs]),
        "total_elapsed_mean_seconds": _mean([float(item["total_elapsed_seconds"]) for item in runs]),
    }

    if judged:
        scores = [int(item["score"]) for item in judged]
        summary.update(
            {
                "semantic_pass_count": sum(bool(item["semantic_passed"]) for item in judged),
                "semantic_pass_rate": sum(bool(item["semantic_passed"]) for item in judged) / len(judged),
                "score_mean": statistics.mean(scores),
                "score_min": min(scores),
                "score_max": max(scores),
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


def _overall_summary(cases: list[dict[str, Any]]) -> dict[str, Any]:
    runs = [
        item
        for case in cases
        for item in case.get("runs", [])
    ]
    if not runs:
        return {"cases": len(cases), "runs": 0}

    judged = _successful_judge_runs(runs)
    completed_cases = [
        case for case in cases if case.get("summary", {}).get("runs", 0) > 0
    ]
    fully_reliable = [
        case["summary"].get("quality_pass_rate") == 1.0
        and case["summary"].get("judge_error_count") == 0
        for case in completed_cases
    ]

    result: dict[str, Any] = {
        "cases": len(cases),
        "runs": len(runs),
        "fully_reliable_case_count": sum(fully_reliable),
        "fully_reliable_case_rate": (
            sum(fully_reliable) / len(completed_cases)
            if completed_cases
            else 0.0
        ),
        "judge_success_count": len(judged),
        "judge_error_count": len(runs) - len(judged),
        "judge_success_rate": len(judged) / len(runs),
        "route_pass_count": sum(bool(item["route_passed"]) for item in runs),
        "route_pass_rate": sum(bool(item["route_passed"]) for item in runs) / len(runs),
        "deterministic_pass_count": sum(bool(item["deterministic_passed"]) for item in runs),
        "deterministic_pass_rate": sum(bool(item["deterministic_passed"]) for item in runs) / len(runs),
        "quality_pass_count": sum(bool(item["quality_passed"]) for item in runs),
        "quality_pass_rate": sum(bool(item["quality_passed"]) for item in runs) / len(runs),
        "generation_elapsed_mean_seconds": _mean([float(item["generation_elapsed_seconds"]) for item in runs]),
        "judge_elapsed_mean_seconds": _mean([float(item["judge_elapsed_seconds"]) for item in runs]),
        "total_elapsed_mean_seconds": _mean([float(item["total_elapsed_seconds"]) for item in runs]),
    }
    if judged:
        scores = [int(item["score"]) for item in judged]
        result.update(
            {
                "semantic_pass_count": sum(bool(item["semantic_passed"]) for item in judged),
                "semantic_pass_rate": sum(bool(item["semantic_passed"]) for item in judged) / len(judged),
                "score_mean": statistics.mean(scores),
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


def _build_output(
    *,
    judge_model: str,
    generation_model: str | None,
    project_override: str | None,
    requested_runs: int,
    selected_cases: list[dict[str, Any]],
    records: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    case_results = [
        records[case["id"]]
        for case in selected_cases
        if case["id"] in records
    ]
    for case_result in case_results:
        case_result["summary"] = _case_summary(case_result.get("runs", []))
    return {
        "generation_model_override": generation_model,
        "judge_model": judge_model,
        "project_override": project_override,
        "requested_runs_per_case": requested_runs,
        "cases": case_results,
        "summary": _overall_summary(case_results),
    }


def _compatible_existing(
    existing: Any,
    *,
    judge_model: str,
    generation_model: str | None,
    project_override: str | None,
) -> bool:
    if not isinstance(existing, dict):
        return False
    return (
        existing.get("judge_model") == judge_model
        and existing.get("generation_model_override") == generation_model
        and existing.get("project_override") == project_override
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", action="append", dest="case_ids")
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--judge-model", required=True)
    parser.add_argument(
        "--generation-model",
        default=None,
        help="Override runtime generation without changing the case definition.",
    )
    parser.add_argument("--project", default=None)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--fresh", action="store_true")
    args = parser.parse_args()

    if args.runs <= 0:
        raise ValueError("--runs must be greater than zero")

    cases = _load_json(CASES_PATH, default=[])
    if not isinstance(cases, list):
        raise RuntimeError("end_to_end_cases.json must contain a list")

    selected_ids = set(args.case_ids) if args.case_ids else None
    selected_cases = [
        case
        for case in cases
        if selected_ids is None or case["id"] in selected_ids
    ]
    if selected_ids is not None:
        missing = selected_ids - {case["id"] for case in selected_cases}
        if missing:
            raise RuntimeError("Unknown case IDs: " + ", ".join(sorted(missing)))

    existing = {} if args.fresh else _load_json(OUTPUT_PATH, default={})
    if not _compatible_existing(
        existing,
        judge_model=args.judge_model,
        generation_model=args.generation_model,
        project_override=args.project,
    ):
        existing = {}

    existing_map = {
        item.get("case_id"): item
        for item in existing.get("cases", [])
        if isinstance(item, dict) and item.get("case_id")
    }

    records: dict[str, dict[str, Any]] = {}
    for case in selected_cases:
        case_id = case["id"]
        old = existing_map.get(case_id, {})
        old_runs = (
            old.get("runs", [])
            if isinstance(old, dict) and not args.force
            else []
        )
        if not isinstance(old_runs, list):
            old_runs = []
        records[case_id] = {
            "case_id": case_id,
            "prompt": case["prompt"],
            "expect": case.get("expect", {}),
            "quality_rubric": case.get("quality", {}),
            "runs": old_runs,
        }

    for case in selected_cases:
        case_id = case["id"]
        record = records[case_id]
        current_runs = record["runs"]
        remaining = max(0, args.runs - len(current_runs))

        print()
        print("=" * 72)
        print(case_id)
        print("=" * 72)
        print("existing runs:", len(current_runs))
        print("runs needed:", remaining)
        if remaining == 0:
            print("[skip] requested runs already completed")
            continue

        rubric = case.get("quality", {})
        expected_route = case.get("expect", {})
        evidence = _evaluation_evidence(case)
        project_name = _case_project(case, args.project)

        for _ in range(remaining):
            run_number = len(current_runs) + 1
            print()
            print("-" * 72)
            print(f"{case_id} run {run_number}/{args.runs}")
            print("-" * 72)

            generation_started = time.monotonic()
            result = run(
                case["prompt"],
                project_name=project_name,
                model_override=args.generation_model,
                echo_route=True,
            )
            generation_elapsed = time.monotonic() - generation_started

            route_checks = _route_checks(
                route=result.route,
                expected=expected_route,
            )
            if args.generation_model is not None and "model" in route_checks:
                route_checks["model"] = {
                    "expected": args.generation_model,
                    "actual": result.route.model,
                    "passed": result.route.model == args.generation_model,
                }
            route_passed = all(check["passed"] for check in route_checks.values())

            deterministic_checks = _run_deterministic_checks(
                answer=result.answer,
                checks=rubric.get("deterministic_checks", []),
            )
            deterministic_passed = all(
                check["passed"] for check in deterministic_checks
            )

            judge_started = time.monotonic()
            judge_result: dict[str, Any] | None = None
            judge_error: str | None = None
            try:
                judge_result = _judge(
                    model=args.judge_model,
                    prompt=case["prompt"],
                    answer=result.answer,
                    rubric=rubric,
                    evaluation_evidence=evidence,
                )
            except Exception as exc:
                judge_error = f"{type(exc).__name__}: {exc}"
            judge_elapsed = time.monotonic() - judge_started

            run_record: dict[str, Any] = {
                "run": run_number,
                "route_checks": route_checks,
                "route_passed": route_passed,
                "answer": result.answer,
                "response_path": str(result.response_path),
                "evaluation_evidence": evidence,
                "generation_elapsed_seconds": round(generation_elapsed, 3),
                "deterministic_checks": deterministic_checks,
                "deterministic_passed": deterministic_passed,
                "judge_elapsed_seconds": round(judge_elapsed, 3),
            }

            if judge_result is None:
                run_record.update(
                    {
                        "judge_error": judge_error,
                        "semantic_passed": False,
                        "score": 0,
                        "quality_passed": False,
                    }
                )
            else:
                judgment = judge_result["judgment"]
                semantic_passed = bool(judgment["passed"])
                run_record.update(
                    {
                        "judgment": judgment,
                        "semantic_passed": semantic_passed,
                        "score": int(judgment["score"]),
                        "judge_attempts": judge_result["judge_attempts"],
                        "judge_metrics": judge_result["judge_metrics"],
                        "quality_passed": (
                            route_passed
                            and deterministic_passed
                            and semantic_passed
                        ),
                    }
                )

            run_record["total_elapsed_seconds"] = round(
                generation_elapsed + judge_elapsed,
                3,
            )
            current_runs.append(run_record)

            print("route passed:", route_passed)
            print("deterministic passed:", deterministic_passed)
            if judge_error:
                print("judge error:", judge_error)
            else:
                print("semantic passed:", run_record["semantic_passed"])
                print("score:", run_record["score"])
            print("quality passed:", run_record["quality_passed"])

            output = _build_output(
                judge_model=args.judge_model,
                generation_model=args.generation_model,
                project_override=args.project,
                requested_runs=args.runs,
                selected_cases=selected_cases,
                records=records,
            )
            _save_json(OUTPUT_PATH, output)

    output = _build_output(
        judge_model=args.judge_model,
        generation_model=args.generation_model,
        project_override=args.project,
        requested_runs=args.runs,
        selected_cases=selected_cases,
        records=records,
    )
    _save_json(OUTPUT_PATH, output)

    print()
    print("=" * 72)
    print("RELIABILITY SUMMARY")
    print("=" * 72)
    for case_result in output["cases"]:
        summary = case_result["summary"]
        print()
        print(case_result["case_id"])
        print(
            f"  quality: {summary.get('quality_pass_count', 0)}/"
            f"{summary.get('runs', 0)}"
        )
        print("  score mean:", summary.get("score_mean"))
    print()
    print("OVERALL")
    print(json.dumps(output["summary"], indent=2))
    print()
    print("Saved:", OUTPUT_PATH)


if __name__ == "__main__":
    main()
