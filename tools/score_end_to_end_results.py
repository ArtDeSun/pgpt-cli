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
CASES_PATH = ROOT / "evals" / "end_to_end_cases.json"
RESULTS_PATH = ROOT / "evals" / "end_to_end_results.json"
OUTPUT_PATH = ROOT / "evals" / "end_to_end_scored.json"
REQUIRED_CRITERION_PROMPT_PATH = ROOT / "prompts" / "quality" / "required-criterion.md"
FORBIDDEN_CRITERION_PROMPT_PATH = ROOT / "prompts" / "quality" / "forbidden-criterion.md"
_SOURCE_ID = re.compile(r"\[S(\d+)\]", re.IGNORECASE)


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _save_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(value, file, indent=2, ensure_ascii=False)
        file.write("\n")


def _criterion_schema(criterion_type: str) -> dict[str, Any]:
    field = {"required": "satisfied", "forbidden": "violated"}[criterion_type]
    return {
        "type": "object",
        "properties": {field: {"type": "boolean"}},
        "required": [field],
        "additionalProperties": False,
    }


def _criterion_value(value: Any, *, criterion_type: str) -> bool:
    if not isinstance(value, dict):
        raise ValueError("Criterion result is not an object")
    field = {"required": "satisfied", "forbidden": "violated"}[criterion_type]
    if set(value) != {field}:
        raise ValueError("Criterion result fields do not match the schema")
    result = value[field]
    if not isinstance(result, bool):
        raise ValueError("Criterion result is not boolean")
    return result


def _run_deterministic_check(*, answer: str, check: dict[str, Any]) -> dict[str, Any]:
    check_type = check.get("type")
    if check_type == "inline_source_ids":
        before = check.get("before")
        content = answer
        if isinstance(before, str):
            position = content.find(before)
            if position >= 0:
                content = content[:position]
        source_ids = {int(value) for value in _SOURCE_ID.findall(content)}
        minimum_distinct = int(check.get("minimum_distinct", 1))
        return {
            "type": check_type,
            "passed": len(source_ids) >= minimum_distinct,
            "details": {
                "distinct_source_ids": sorted(source_ids),
                "count": len(source_ids),
                "minimum_distinct": minimum_distinct,
            },
        }
    if check_type == "forbidden_regex":
        patterns = check.get("patterns", [])
        if not isinstance(patterns, list):
            raise ValueError("forbidden_regex patterns must be a list")
        matches: list[str] = []
        for pattern in patterns:
            if not isinstance(pattern, str):
                raise ValueError("forbidden_regex patterns must contain strings")
            if re.search(pattern, answer, re.IGNORECASE):
                matches.append(pattern)
        return {
            "type": check_type,
            "passed": not matches,
            "details": {"matched_patterns": matches},
        }
    raise ValueError(f"Unknown deterministic check type: {check_type!r}")


def _run_deterministic_checks(*, answer: str, checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [_run_deterministic_check(answer=answer, check=check) for check in checks]


def _load_criterion_prompt(criterion_type: str) -> str:
    paths = {
        "required": REQUIRED_CRITERION_PROMPT_PATH,
        "forbidden": FORBIDDEN_CRITERION_PROMPT_PATH,
    }
    return paths[criterion_type].read_text(encoding="utf-8").strip()


def _judge_criterion_once(
    *,
    model: str,
    criterion_type: str,
    prompt: str,
    answer: str,
    criterion: str,
    evaluation_context: Any,
    evaluation_evidence: Any,
) -> dict[str, Any]:
    request = {
        "user_request": prompt,
        "evaluation_context": evaluation_context,
        "criterion": criterion,
        "assistant_answer": answer,
        "evaluation_evidence": evaluation_evidence,
    }
    response = json_request(
        "POST",
        ollama_url("/api/chat"),
        payload={
            "model": model,
            "messages": [
                {"role": "system", "content": _load_criterion_prompt(criterion_type)},
                {"role": "user", "content": json.dumps(request, ensure_ascii=False)},
            ],
            "stream": False,
            "think": False,
            "format": _criterion_schema(criterion_type),
            "keep_alive": "10m",
            "options": {
                "temperature": 0.0,
                "num_ctx": int(CONFIG.get("quality", {}).get("judge_num_ctx", 4096)),
                "num_predict": int(CONFIG.get("quality", {}).get("criterion_max_tokens", 32)),
            },
        },
        timeout=float(CONFIG.get("quality", {}).get("judge_timeout_seconds", 120)),
    )
    if not isinstance(response, dict):
        raise ValueError("Ollama returned no judge response object")
    message = response.get("message")
    if not isinstance(message, dict):
        raise ValueError("Ollama judge response has no message")
    content = str(message.get("content", "")).strip()
    if not content:
        raise ValueError("Judge returned empty content")
    value = _criterion_value(json.loads(content), criterion_type=criterion_type)
    return {
        "value": value,
        "metrics": {
            "done_reason": response.get("done_reason"),
            "load_duration": response.get("load_duration", 0),
            "prompt_eval_duration": response.get("prompt_eval_duration", 0),
            "prompt_eval_count": response.get("prompt_eval_count", 0),
            "eval_duration": response.get("eval_duration", 0),
            "eval_count": response.get("eval_count", 0),
            "total_duration": response.get("total_duration", 0),
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
    attempts = 2
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            result = _judge_criterion_once(
                model=model,
                criterion_type=criterion_type,
                prompt=prompt,
                answer=answer,
                criterion=criterion,
                evaluation_context=evaluation_context,
                evaluation_evidence=evaluation_evidence,
            )
            result["attempts"] = attempt
            return result
        except (ValueError, json.JSONDecodeError, TimeoutError) as exc:
            last_error = exc
            if attempt >= attempts:
                raise
    assert last_error is not None
    raise last_error


def _aggregate_metrics(results: list[dict[str, Any]]) -> dict[str, Any]:
    numeric = (
        "load_duration",
        "prompt_eval_duration",
        "prompt_eval_count",
        "eval_duration",
        "eval_count",
        "total_duration",
    )
    output: dict[str, Any] = {"criterion_count": len(results)}
    for field in numeric:
        output[field] = sum(int(result.get("metrics", {}).get(field, 0) or 0) for result in results)
    return output


def _score_judgment(*, required_passed: list[bool], forbidden_violated: list[bool]) -> int:
    missing = sum(not value for value in required_passed)
    forbidden = sum(forbidden_violated)
    if missing == 0 and forbidden == 0:
        return 5
    if forbidden == 0 and missing == 1:
        return 3
    if forbidden == 0 and missing == 2:
        return 2
    return 1


def _judge(
    *,
    model: str,
    prompt: str,
    answer: str,
    rubric: dict[str, Any],
    evaluation_evidence: Any = None,
) -> dict[str, Any]:
    required_points = rubric.get("required_points", [])
    forbidden_points = rubric.get("forbidden_points", [])
    evaluation_context = rubric.get("evaluation_context", [])
    if not isinstance(required_points, list):
        raise ValueError("required_points must be a list")
    if not isinstance(forbidden_points, list):
        raise ValueError("forbidden_points must be a list")

    required_results = [
        _judge_criterion(
            model=model,
            criterion_type="required",
            prompt=prompt,
            answer=answer,
            criterion=str(criterion),
            evaluation_context=evaluation_context,
            evaluation_evidence=evaluation_evidence,
        )
        for criterion in required_points
    ]
    forbidden_results = [
        _judge_criterion(
            model=model,
            criterion_type="forbidden",
            prompt=prompt,
            answer=answer,
            criterion=str(criterion),
            evaluation_context=evaluation_context,
            evaluation_evidence=evaluation_evidence,
        )
        for criterion in forbidden_points
    ]
    required_passed = [bool(result["value"]) for result in required_results]
    forbidden_violated = [bool(result["value"]) for result in forbidden_results]
    required_reasons = [
        ("Satisfied required point: " if passed else "Missing required point: ") + str(criterion)
        for criterion, passed in zip(required_points, required_passed)
    ]
    forbidden_reasons = [
        ("Forbidden point violated: " if violated else "Forbidden point not present: ") + str(criterion)
        for criterion, violated in zip(forbidden_points, forbidden_violated)
    ]
    passed = all(required_passed) and not any(forbidden_violated)
    issues = [reason for reason, value in zip(required_reasons, required_passed) if not value]
    issues.extend(reason for reason, value in zip(forbidden_reasons, forbidden_violated) if value)
    all_results = required_results + forbidden_results
    return {
        "judgment": {
            "passed": passed,
            "score": _score_judgment(required_passed=required_passed, forbidden_violated=forbidden_violated),
            "required_passed": required_passed,
            "required_reasons": required_reasons,
            "forbidden_violated": forbidden_violated,
            "forbidden_reasons": forbidden_reasons,
            "issues": issues,
        },
        "judge_attempts": max((int(result.get("attempts", 1)) for result in all_results), default=1),
        "judge_metrics": _aggregate_metrics(all_results),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--case", action="append", dest="case_ids")
    args = parser.parse_args()
    rows = _load_json(RESULTS_PATH)
    cases = _load_json(CASES_PATH)
    if not isinstance(rows, list):
        raise RuntimeError("end_to_end_results.json must contain a list")
    if not isinstance(cases, list):
        raise RuntimeError("end_to_end_cases.json must contain a list")
    case_map = {case["id"]: case for case in cases if isinstance(case, dict) and "id" in case}
    selected = set(args.case_ids) if args.case_ids else None
    scored: list[dict[str, Any]] = []
    for row in rows:
        if selected is not None and row["id"] not in selected:
            continue
        print()
        print("=" * 72)
        print(row["id"])
        print("=" * 72)
        try:
            case = case_map.get(row["id"])
            if case is None:
                raise ValueError(f"No current eval case exists for {row['id']!r}")
            rubric = case.get("quality", {})
            deterministic_checks = _run_deterministic_checks(
                answer=row["answer"],
                checks=rubric.get("deterministic_checks", []),
            )
            deterministic_passed = all(check["passed"] for check in deterministic_checks)
            semantic_result = _judge(
                model=args.model,
                prompt=row["prompt"],
                answer=row["answer"],
                rubric=rubric,
                evaluation_evidence=row.get("evaluation_evidence"),
            )
            judgment = semantic_result["judgment"]
            semantic_passed = bool(judgment["passed"])
            quality_passed = row.get("route_passed", True) and deterministic_passed and semantic_passed
            record = {
                **row,
                "quality_rubric": rubric,
                "judge_model": args.model,
                "deterministic_checks": deterministic_checks,
                "deterministic_passed": deterministic_passed,
                "judgment": judgment,
                "semantic_passed": semantic_passed,
                "quality_passed": quality_passed,
                "judge_attempts": semantic_result["judge_attempts"],
                "judge_metrics": semantic_result["judge_metrics"],
            }
            print("semantic passed:", semantic_passed)
            print("score:", judgment["score"])
            print("deterministic passed:", deterministic_passed)
            print("judge attempts:", semantic_result["judge_attempts"])
            print("quality passed:", quality_passed)
        except Exception as exc:
            record = {
                **row,
                "judge_model": args.model,
                "judge_error": f"{type(exc).__name__}: {exc}",
            }
            print("ERROR:", record["judge_error"])
        scored.append(record)
    _save_json(OUTPUT_PATH, scored)
    print()
    print("Saved:", OUTPUT_PATH)


if __name__ == "__main__":
    main()
