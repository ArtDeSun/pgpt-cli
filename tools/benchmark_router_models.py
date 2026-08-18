from __future__ import annotations

import argparse
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

from pgpt.config import CONFIG
from pgpt.generation.ollama import list_models
from pgpt.routing.router import resolve_route


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Suite:
    name: str
    path: Path
    fields: tuple[str, ...]


TEMPORAL = Suite(
    name="temporal",
    path=ROOT / "evals" / "routing_temporal_pairs.json",
    fields=("source", "freshness"),
)

GOLD = Suite(
    name="routing-gold",
    path=ROOT / "evals" / "routing_gold.json",
    fields=("source", "web_mode", "task", "freshness"),
)


def _load_cases(suite: Suite) -> list[dict]:
    with suite.path.open("r", encoding="utf-8") as file:
        value = json.load(file)

    if not isinstance(value, list):
        raise RuntimeError(f"{suite.path.name} must contain a list")

    return value


def _default_models() -> list[str]:
    configured = str(CONFIG["models"]["roles"]["router"])
    return list(dict.fromkeys([configured, "gemma4:e4b"]))


def _decision(case: dict) -> dict[str, object]:
    decision = resolve_route(
        case["prompt"],
        project_name="pgpt-cli",
        web_override=None,
        project_override=None,
        template_override=None,
        model_override=None,
        deep_override=None,
        symbol_hit=bool(case.get("symbol_hit", False)),
    )

    return {
        "source": decision.source,
        "web_mode": decision.web_mode,
        "task": decision.task,
        "freshness": decision.freshness,
    }


def _run_suite(
    *,
    model: str,
    suite: Suite,
    cases: list[dict],
) -> tuple[int, list[str], float]:
    previous = os.environ.get("PGPT_ROUTER_MODEL")
    os.environ["PGPT_ROUTER_MODEL"] = model
    started = time.monotonic()
    failed_cases: set[str] = set()
    failures: list[str] = []

    try:
        for case in cases:
            actual = _decision(case)
            expected = case["expect"]

            for field in suite.fields:
                if field not in expected:
                    continue

                expected_value = expected[field]
                if actual[field] != expected_value:
                    failed_cases.add(case["id"])
                    failures.append(
                        f"{case['id']}: {field} expected {expected_value!r}, "
                        f"got {actual[field]!r}"
                    )
    finally:
        if previous is None:
            os.environ.pop("PGPT_ROUTER_MODEL", None)
        else:
            os.environ["PGPT_ROUTER_MODEL"] = previous

    elapsed = time.monotonic() - started
    passed = len(cases) - len(failed_cases)
    return passed, failures, elapsed


def _print_result(
    *,
    model: str,
    suite: Suite,
    passed: int,
    total: int,
    elapsed: float,
    failures: list[str],
) -> None:
    print()
    print(f"{model} [{suite.name}]: {passed}/{total} cases passed in {elapsed:.1f}s")

    for failure in failures:
        print(f"  - {failure}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Compare local Ollama router models. Candidates must first pass the "
            "small temporal gate; only passing candidates run the broader gold suite."
        )
    )
    parser.add_argument(
        "--model",
        action="append",
        dest="models",
        help="Router model to test. Repeat to compare several models.",
    )
    args = parser.parse_args()

    requested = args.models or _default_models()
    available = set(list_models())
    models = [model for model in requested if model in available]

    missing = [model for model in requested if model not in available]
    for model in missing:
        print(f"[skip] unavailable: {model}")

    if not models:
        raise SystemExit("No requested router models are available in Ollama.")

    temporal_cases = _load_cases(TEMPORAL)
    gold_cases = _load_cases(GOLD)
    temporal_passers: list[str] = []

    print("Temporal gate: every case must pass before the broad suite runs.")

    for model in models:
        passed, failures, elapsed = _run_suite(
            model=model,
            suite=TEMPORAL,
            cases=temporal_cases,
        )
        _print_result(
            model=model,
            suite=TEMPORAL,
            passed=passed,
            total=len(temporal_cases),
            elapsed=elapsed,
            failures=failures,
        )

        if passed == len(temporal_cases):
            temporal_passers.append(model)

    if not temporal_passers:
        print()
        print("No router passed the temporal gate; no default should be changed yet.")
        raise SystemExit(1)

    print()
    print("Broad gate: source, web mode, task, and freshness must all match routing_gold.json.")

    broad_passers: list[tuple[str, float]] = []

    for model in temporal_passers:
        passed, failures, elapsed = _run_suite(
            model=model,
            suite=GOLD,
            cases=gold_cases,
        )
        _print_result(
            model=model,
            suite=GOLD,
            passed=passed,
            total=len(gold_cases),
            elapsed=elapsed,
            failures=failures,
        )

        if passed == len(gold_cases):
            broad_passers.append((model, elapsed))

    if not broad_passers:
        print()
        print("No router passed both gates; no default should be changed yet.")
        raise SystemExit(1)

    broad_passers.sort(key=lambda item: item[1])
    winner = broad_passers[0][0]

    print()
    print(f"Qualified router: {winner}")

    if len(broad_passers) > 1:
        print("Multiple routers passed both gates; the fastest broad-suite run won the tie.")


if __name__ == "__main__":
    main()
