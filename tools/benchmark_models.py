from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from pgpt.generation.ollama import list_models, stream_chat


ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = ROOT / "evals" / "model_selection_cases.json"
RESULTS_PATH = ROOT / "evals" / "model_benchmark_results.json"
PROMPT_PATH = ROOT / "prompts" / "benchmark.md"
DEFAULT_MODELS = [
    "qwen3:1.7b",
    "llama3.2:3b",
    "qwen2.5-coder:3b",
    "phi4-mini",
]


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _save(value: Any) -> None:
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _existing() -> list[dict]:
    try:
        value = _load(RESULTS_PATH)
        return value if isinstance(value, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def _run_case(model: str, case: dict) -> dict:
    parts: list[str] = []
    started = time.monotonic()
    final = stream_chat(
        model=model,
        messages=[
            {
                "role": "system",
                "content": PROMPT_PATH.read_text(encoding="utf-8").strip(),
            },
            {"role": "user", "content": case["prompt"]},
        ],
        on_text=parts.append,
        max_tokens=int(case.get("max_tokens", 400)),
        num_ctx=4096,
        temperature=0.1,
    )

    eval_ns = int(final.get("eval_duration", 0) or 0)
    tokens = int(final.get("eval_count", 0) or 0)
    speed = tokens / (eval_ns / 1e9) if eval_ns else 0.0

    return {
        "case_id": case["id"],
        "task": case["task"],
        "model": model,
        "prompt": case["prompt"],
        "rubric": case.get("rubric", []),
        "answer": "".join(parts).strip(),
        "done_reason": final.get("done_reason"),
        "wall_seconds": round(time.monotonic() - started, 3),
        "output_tokens": tokens,
        "tokens_per_second": round(speed, 2),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", action="append", dest="models")
    parser.add_argument("--task", action="append", dest="tasks")
    parser.add_argument("--fresh", action="store_true")
    args = parser.parse_args()

    cases = _load(CASES_PATH)
    if args.tasks:
        tasks = set(args.tasks)
        cases = [case for case in cases if case["task"] in tasks]

    requested = args.models or DEFAULT_MODELS
    available = set(list_models())
    models = [model for model in requested if model in available]
    for model in requested:
        if model not in available:
            print(f"[skip] unavailable: {model}")
    if not models:
        raise SystemExit("No requested benchmark models are available in Ollama.")

    results = [] if args.fresh else _existing()
    completed = {(row.get("case_id"), row.get("model")) for row in results}
    started = time.monotonic()
    added = 0

    for model in models:
        print(f"\nMODEL: {model}")
        for case in cases:
            key = (case["id"], model)
            if key in completed:
                print(f"[skip] {case['id']}")
                continue

            print(f"[run] {case['id']} ({case['task']})")
            try:
                row = _run_case(model, case)
            except Exception as exc:
                row = {
                    "case_id": case["id"],
                    "task": case["task"],
                    "model": model,
                    "prompt": case["prompt"],
                    "rubric": case.get("rubric", []),
                    "error": f"{type(exc).__name__}: {exc}",
                }

            results.append(row)
            completed.add(key)
            added += 1
            _save(results)

            if "error" in row:
                print(f"  ERROR: {row['error']}")
            else:
                print(
                    f"  {row['wall_seconds']:.1f}s | "
                    f"{row['output_tokens']} tokens | "
                    f"{row['tokens_per_second']:.1f} tok/s"
                )

    print(f"\nNew runs: {added}")
    print(f"Elapsed: {time.monotonic() - started:.1f}s")
    print(f"Saved: {RESULTS_PATH}")


if __name__ == "__main__":
    main()
