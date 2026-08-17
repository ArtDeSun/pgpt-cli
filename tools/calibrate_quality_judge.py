from __future__ import annotations

import argparse
import json
from pathlib import Path

from tools.score_end_to_end_results import _judge


ROOT = Path(__file__).resolve().parents[1]

CASES_PATH = (
    ROOT
    / "evals"
    / "judge_calibration.json"
)


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--model",
        required=True,
    )

    args = parser.parse_args()

    with CASES_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:
        cases = json.load(file)

    passed_cases = 0

    for case in cases:
        result = _judge(
            model=args.model,
            prompt=case["prompt"],
            answer=case["answer"],
            rubric=case["rubric"],
            evaluation_evidence=case.get(
                "evaluation_evidence"
            ),
        )

        judgment = result["judgment"]
        expected = case["expect"]

        correct = (
            judgment["passed"]
            == expected["passed"]
        )

        if (
            correct
            and "min_score" in expected
        ):
            correct = (
                judgment["score"]
                >= expected["min_score"]
            )

        if (
            correct
            and "max_score" in expected
        ):
            correct = (
                judgment["score"]
                <= expected["max_score"]
            )

        if (
            correct
            and "required_passed"
            in expected
        ):
            correct = (
                judgment["required_passed"]
                == expected[
                    "required_passed"
                ]
            )

        if (
            correct
            and "forbidden_violated"
            in expected
        ):
            correct = (
                judgment[
                    "forbidden_violated"
                ]
                == expected[
                    "forbidden_violated"
                ]
            )

        if correct:
            passed_cases += 1

        print()
        print(case["id"])
        print(
            "expected passed:",
            expected["passed"],
        )
        print(
            "actual passed:",
            judgment["passed"],
        )
        print(
            "score:",
            judgment["score"],
        )
        print(
            "calibration:",
            (
                "PASS"
                if correct
                else "FAIL"
            ),
        )

        if "required_passed" in expected:
            print(
                "expected required:",
                expected[
                    "required_passed"
                ],
            )
            print(
                "actual required:",
                judgment[
                    "required_passed"
                ],
            )

        if "forbidden_violated" in expected:
            print(
                "expected forbidden:",
                expected[
                    "forbidden_violated"
                ],
            )
            print(
                "actual forbidden:",
                judgment[
                    "forbidden_violated"
                ],
            )

    total = len(cases)

    print()
    print(
        f"Calibration: "
        f"{passed_cases}/{total} "
        f"({passed_cases / total * 100:.1f}%)"
    )


if __name__ == "__main__":
    main()