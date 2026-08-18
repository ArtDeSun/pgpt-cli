from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

from pgpt.config import CONFIG
from pgpt.generation.ollama import list_models
from pgpt.routing.router import resolve_route


ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = ROOT / "evals" / "routing_temporal_pairs.json"


def _load_cases() -> list[dict]:
    with CASES_PATH.open("r", encoding="utf-8") as file:
        value = json.load(file)

    if not isinstance(value, list):
        raise RuntimeError("routing_temporal_pairs.json must contain a list")

    return value


def _default_models() -> list[str]:
    configured = str(CONFIG["models"]["roles"]["router"])
    return list(dict.fromkeys([configured, "gemma4:e4b"]))


def _run_model(model: str, cases: list[dict]) -> tuple[int, list[str], float]:
    previous = os.environ.get("PGPT_ROUTER_MODEL")
    os.environ["PGPT_ROUTER_MODEL"] = model
    started = time.monotonic()
    failures: list[str] = []

    try:
        for case in cases:
            decision = resolve_route(
                case["prompt"],
                project_name="pgpt-cli",
                web_override=None,
                project_override=None,
                template_override=None,
                model_override=None,
                deep_override=None,
                symbol_hit=False,
            )

            actual = {
                "source": decision.source,
                "freshness": decision.freshness,
            }

            for field, expected in case["expect"].items():
                if actual[field] != expected:
                    failures.append(
                        f"{case['id']}: {field} expected {expected!r}, "
                        f"got {actual[field]!r}"
                    )
    finally:
        if previous is None:
            os.environ.pop("PGPT_ROUTER_MODEL", None)
        else:
            os.environ["PGPT_ROUTER_MODEL"] = previous

    elapsed = time.monotonic() - started
    passed = len(cases) - len({item.split(":", 1)[0] for item in failures})
    return passed, failures, elapsed


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare local Ollama router models on temporal routing acceptance cases."
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

    cases = _load_cases()
    best_passed = -1
    best_model = ""

    for model in models:
        passed, failures, elapsed = _run_model(model, cases)
        print()
        print(f"{model}: {passed}/{len(cases)} cases passed in {elapsed:.1f}s")

        for failure in failures:
            print(f"  - {failure}")

        if passed > best_passed:
            best_passed = passed
            best_model = model

    print()
    print(f"Best router: {best_model} ({best_passed}/{len(cases)})")

    if best_passed != len(cases):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
