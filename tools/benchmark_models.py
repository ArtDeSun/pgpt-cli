from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from pgpt.generation.ollama import (
    list_models,
    stream_chat,
)


ROOT = Path(__file__).resolve().parents[1]

CASES_PATH = (
    ROOT
    / "evals"
    / "model_selection_cases.json"
)

RESULTS_PATH = (
    ROOT
    / "evals"
    / "model_benchmark_results.json"
)


MODELS = [
    "qwen3:1.7b",
    "llama3.2:3b",
    "qwen2.5-coder:3b",
    "phi4-mini",
]


SYSTEM_PROMPT = """
Answer the user's request accurately and directly.

Do not discuss routing, model selection, or evaluation.

For code tasks, prefer the smallest correct implementation.

For explanation tasks, explain the actual mechanism rather than
giving generic advice.

For research tasks, use only evidence supplied by the user when the
prompt explicitly limits the sources.

Be concise but complete.
""".strip()


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


def _existing_results() -> list[dict]:
    if not RESULTS_PATH.exists():
        return []

    try:
        value = _load_json(
            RESULTS_PATH
        )
    except (
        OSError,
        json.JSONDecodeError,
    ):
        return []

    if not isinstance(
        value,
        list,
    ):
        return []

    return value


def _run_case(
    *,
    model: str,
    case: dict,
) -> dict:
    parts: list[str] = []

    def on_text(
        chunk: str,
    ) -> None:
        parts.append(
            chunk
        )

    started = time.monotonic()

    final = stream_chat(
        model=model,
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": case[
                    "prompt"
                ],
            },
        ],
        on_text=on_text,
        max_tokens=int(
            case.get(
                "max_tokens",
                400,
            )
        ),
        num_ctx=4096,
        temperature=0.1,
    )

    wall_seconds = (
        time.monotonic()
        - started
    )

    eval_duration = int(
        final.get(
            "eval_duration",
            0,
        )
        or 0
    )

    eval_count = int(
        final.get(
            "eval_count",
            0,
        )
        or 0
    )

    tokens_per_second = (
        eval_count
        / (
            eval_duration
            / 1e9
        )
        if eval_duration
        else 0.0
    )

    return {
        "case_id": case["id"],
        "task": case["task"],
        "model": model,
        "prompt": case["prompt"],
        "rubric": case.get(
            "rubric",
            [],
        ),
        "answer": "".join(
            parts
        ).strip(),
        "done_reason": final.get(
            "done_reason"
        ),
        "wall_seconds": round(
            wall_seconds,
            3,
        ),
        "load_seconds": round(
            int(
                final.get(
                    "load_duration",
                    0,
                )
                or 0
            )
            / 1e9,
            3,
        ),
        "prompt_eval_seconds": round(
            int(
                final.get(
                    "prompt_eval_duration",
                    0,
                )
                or 0
            )
            / 1e9,
            3,
        ),
        "generation_seconds": round(
            eval_duration
            / 1e9,
            3,
        ),
        "output_tokens": eval_count,
        "tokens_per_second": round(
            tokens_per_second,
            2,
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--model",
        action="append",
        dest="models",
        help=(
            "Benchmark only this model. "
            "Repeat --model to select several."
        ),
    )

    parser.add_argument(
        "--task",
        action="append",
        dest="tasks",
        help=(
            "Benchmark only this task family. "
            "Repeat --task to select several."
        ),
    )

    parser.add_argument(
        "--fresh",
        action="store_true",
        help=(
            "Discard existing benchmark results "
            "before running."
        ),
    )

    args = parser.parse_args()

    cases = _load_json(
        CASES_PATH
    )

    requested_models = (
        args.models
        if args.models
        else MODELS
    )

    available = set(
        list_models()
    )

    models = [
        model
        for model in requested_models
        if model in available
    ]

    missing = [
        model
        for model in requested_models
        if model not in available
    ]

    if missing:
        print(
            "Unavailable models:"
        )

        for model in missing:
            print(
                f"  - {model}"
            )

    if not models:
        raise SystemExit(
            "No requested benchmark models "
            "are available in Ollama."
        )

    if args.tasks:
        selected_tasks = set(
            args.tasks
        )

        cases = [
            case
            for case in cases
            if case["task"]
            in selected_tasks
        ]

    results = (
        []
        if args.fresh
        else _existing_results()
    )

    completed = {
        (
            item.get(
                "case_id"
            ),
            item.get(
                "model"
            ),
        )
        for item in results
    }

    total_new = 0
    suite_started = time.monotonic()

    for model in models:
        print()
        print(
            "=" * 72
        )
        print(
            f"MODEL: {model}"
        )
        print(
            "=" * 72
        )

        for case in cases:
            key = (
                case["id"],
                model,
            )

            if key in completed:
                print(
                    f"[skip] "
                    f"{case['id']} "
                    f"already benchmarked"
                )

                continue

            print()
            print(
                f"[run] "
                f"{case['id']} "
                f"({case['task']})"
            )

            try:
                result = _run_case(
                    model=model,
                    case=case,
                )

            except Exception as exc:
                result = {
                    "case_id": case["id"],
                    "task": case["task"],
                    "model": model,
                    "prompt": case["prompt"],
                    "rubric": case.get(
                        "rubric",
                        [],
                    ),
                    "error": (
                        f"{type(exc).__name__}: "
                        f"{exc}"
                    ),
                }

            results.append(
                result
            )

            completed.add(
                key
            )

            total_new += 1

            # Save after every run so a long benchmark
            # can be interrupted safely.
            _save_json(
                RESULTS_PATH,
                results,
            )

            if "error" in result:
                print(
                    "  ERROR:",
                    result["error"],
                )

                continue

            print(
                "  wall:",
                f"{result['wall_seconds']:.1f}s",
            )

            print(
                "  tokens:",
                result[
                    "output_tokens"
                ],
            )

            print(
                "  speed:",
                f"{result['tokens_per_second']:.1f} tok/s",
            )

            print(
                "  done:",
                result[
                    "done_reason"
                ],
            )

    elapsed = (
        time.monotonic()
        - suite_started
    )

    print()
    print(
        "=" * 72
    )

    print(
        "New runs:",
        total_new,
    )

    print(
        "Elapsed:",
        f"{elapsed:.1f}s",
    )

    print(
        "Saved:",
        RESULTS_PATH,
    )


if __name__ == "__main__":
    main()