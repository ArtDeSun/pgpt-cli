from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from pgpt.config import CONFIG
from pgpt.retrieval.project import build_context as build_project_context
from pgpt.runtime.pipeline import run


ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = ROOT / "evals" / "end_to_end_cases.json"
RESULTS_PATH = ROOT / "evals" / "end_to_end_results.json"


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


def _ordered_results(
    *,
    cases: list[dict[str, Any]],
    records: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    ordered: list[dict[str, Any]] = []
    known_ids: set[str] = set()
    for case in cases:
        case_id = case["id"]
        known_ids.add(case_id)
        if case_id in records:
            ordered.append(records[case_id])
    for case_id, record in records.items():
        if case_id not in known_ids:
            ordered.append(record)
    return ordered


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", action="append", dest="case_ids")
    parser.add_argument("--project")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Rerun selected cases even when results already exist.",
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Discard existing end-to-end results before running.",
    )
    args = parser.parse_args()

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

    existing_rows = (
        [] if args.fresh else _load_json(RESULTS_PATH, default=[])
    )
    if not isinstance(existing_rows, list):
        raise RuntimeError("end_to_end_results.json must contain a list")

    records = {
        row["id"]: row
        for row in existing_rows
        if isinstance(row, dict) and "id" in row
    }

    new_runs = 0
    skipped = 0

    for case in selected_cases:
        case_id = case["id"]
        if case_id in records and not args.force:
            print()
            print("=" * 72)
            print(case_id)
            print("=" * 72)
            print("[skip] existing result")
            skipped += 1
            continue

        print()
        print("=" * 72)
        print(case_id)
        print("=" * 72)

        started = time.monotonic()
        result = run(
            case["prompt"],
            project_name=_case_project(case, args.project),
            echo_route=True,
        )
        elapsed = time.monotonic() - started

        route_checks: dict[str, dict[str, Any]] = {}
        for field, expected in case.get("expect", {}).items():
            actual = _route_value(result.route, field)
            route_checks[field] = {
                "expected": expected,
                "actual": actual,
                "passed": actual == expected,
            }

        record = {
            "id": case_id,
            "prompt": case["prompt"],
            "route_checks": route_checks,
            "route_passed": all(
                check["passed"] for check in route_checks.values()
            ),
            "quality_rubric": case.get("quality", {}),
            "answer": result.answer,
            "response_path": str(result.response_path),
            "elapsed_seconds": round(elapsed, 3),
            "evaluation_evidence": _evaluation_evidence(case),
        }
        records[case_id] = record
        new_runs += 1

        print()
        print("route:", "PASS" if record["route_passed"] else "FAIL")
        for field, check in route_checks.items():
            print(
                f"  {field}: {check['actual']!r} "
                f"(expected {check['expected']!r})"
            )

        _save_json(
            RESULTS_PATH,
            _ordered_results(cases=cases, records=records),
        )

    final_rows = _ordered_results(cases=cases, records=records)
    _save_json(RESULTS_PATH, final_rows)

    print()
    print("=" * 72)
    print("New runs:", new_runs)
    print("Skipped existing:", skipped)
    print("Total saved:", len(final_rows))
    print("Saved:", RESULTS_PATH)


if __name__ == "__main__":
    main()
