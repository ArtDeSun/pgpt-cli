from __future__ import annotations

import json
from pathlib import Path
from unittest import TestCase

from pgpt.routing.router import resolve_route


ROOT = Path(__file__).resolve().parents[1]

DATASET_PATH = (
    ROOT
    / "evals"
    / "routing_gold.json"
)


# These are the routing dimensions we now trust as the
# authoritative routing contract.
HARD_FIELDS = (
    "source",
    "web_mode",
    "task",
    "freshness",
)


# Complexity remains useful telemetry, but it is not allowed
# to fail the routing suite.
REPORT_ONLY_FIELDS = (
    "complexity",
)


class TestRouterDataset(
    TestCase
):
    def test_routing_dataset(
        self,
    ) -> None:
        with DATASET_PATH.open(
            "r",
            encoding="utf-8",
        ) as file:
            cases = json.load(file)

        totals = {
            field: 0
            for field in (
                *HARD_FIELDS,
                *REPORT_ONLY_FIELDS,
            )
        }

        correct = {
            field: 0
            for field in totals
        }

        hard_failures: list[str] = []
        complexity_mismatches: list[str] = []

        for case in cases:
            prompt = case["prompt"]
            expected = case["expect"]

            decision = resolve_route(
                prompt,
                project_name="vibemaster",
                web_override=None,
                project_override=None,
                template_override=None,
                model_override=None,
                deep_override=None,
                symbol_hit=case.get(
                    "symbol_hit",
                    False,
                ),
            )

            actual = {
                "source": decision.source,
                "web_mode": decision.web_mode,
                "task": decision.task,
                "freshness": decision.freshness,
                "complexity": decision.complexity,
            }

            for field in (
                *HARD_FIELDS,
                *REPORT_ONLY_FIELDS,
            ):
                if field not in expected:
                    continue

                totals[field] += 1

                if (
                    actual[field]
                    == expected[field]
                ):
                    correct[field] += 1
                    continue

                message = (
                    f"{case['id']}: "
                    f"{field} expected "
                    f"{expected[field]!r}, "
                    f"got {actual[field]!r} "
                    f"| prompt={prompt!r}"
                )

                if field in HARD_FIELDS:
                    hard_failures.append(
                        message
                    )
                else:
                    complexity_mismatches.append(
                        message
                    )

        print()
        print(
            "Routing dataset accuracy:"
        )

        for field in (
            *HARD_FIELDS,
            *REPORT_ONLY_FIELDS,
        ):
            total = totals[field]

            if total == 0:
                print(
                    f"  {field:10} "
                    f"{0:3}/{0:<3} "
                    f"{0.0:6.1f}%"
                )

                continue

            value = correct[field]

            percentage = (
                value
                / total
                * 100
            )

            suffix = (
                "  (report only)"
                if field
                in REPORT_ONLY_FIELDS
                else ""
            )

            print(
                f"  {field:10} "
                f"{value:3}/{total:<3} "
                f"{percentage:6.1f}%"
                f"{suffix}"
            )

        if complexity_mismatches:
            print()
            print(
                "Complexity mismatches "
                "(non-blocking):"
            )

            for failure in (
                complexity_mismatches
            ):
                print(
                    f"  - {failure}"
                )

        if hard_failures:
            self.fail(
                "\n"
                + "\n".join(
                    hard_failures
                )
            )