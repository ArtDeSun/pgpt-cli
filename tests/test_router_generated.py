from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from unittest import TestCase

from pgpt.routing.router import resolve_route


ROOT = Path(__file__).resolve().parents[1]

DATASET_PATH = (
    ROOT
    / "evals"
    / "routing_generated.json"
)

FIELDS = (
    "source",
    "web_mode",
    "task",
    "freshness",
    "complexity",
)


class TestGeneratedRoutingDataset(
    TestCase
):
    def test_generated_dataset_report(
        self,
    ) -> None:
        with DATASET_PATH.open(
            "r",
            encoding="utf-8",
        ) as file:
            cases = json.load(file)

        totals = defaultdict(int)
        correct = defaultdict(int)

        domain_totals = defaultdict(int)
        domain_exact = defaultdict(int)

        disagreements: list[str] = []

        for case in cases:
            prompt = case[
                "prompt"
            ]

            expected = case[
                "expect"
            ]

            domain = case.get(
                "domain",
                "unknown",
            )

            decision = resolve_route(
                prompt,
                project_name="vibemaster",
                web_override=None,
                project_override=None,
                template_override=None,
                model_override=None,
                deep_override=None,
                symbol_hit=False,
            )

            actual = {
                "source": (
                    decision.source
                ),
                "web_mode": (
                    decision.web_mode
                ),
                "task": (
                    decision.task
                ),
                "freshness": (
                    decision.freshness
                ),
                "complexity": (
                    decision.complexity
                ),
            }

            exact = True

            differences = []

            for field in FIELDS:
                if field not in expected:
                    continue

                totals[field] += 1

                if (
                    actual[field]
                    == expected[field]
                ):
                    correct[field] += 1

                else:
                    exact = False

                    differences.append(
                        f"{field}: "
                        f"expected="
                        f"{expected[field]!r}, "
                        f"actual="
                        f"{actual[field]!r}"
                    )

            domain_totals[
                domain
            ] += 1

            if exact:
                domain_exact[
                    domain
                ] += 1

            else:
                disagreements.append(
                    (
                        f"{case['id']} "
                        f"[{domain}]\n"
                        f"  prompt: {prompt!r}\n"
                        f"  "
                        + "\n  ".join(
                            differences
                        )
                    )
                )

        print()
        print(
            "Generated routing report:"
        )

        for field in FIELDS:
            total = totals[
                field
            ]

            if not total:
                continue

            value = correct[
                field
            ]

            percent = (
                value
                / total
                * 100
            )

            print(
                f"  {field:10} "
                f"{value:3}/{total:<3} "
                f"{percent:6.1f}%"
            )

        print()
        print(
            "Exact match by domain:"
        )

        for domain in sorted(
            domain_totals
        ):
            total = domain_totals[
                domain
            ]

            value = domain_exact[
                domain
            ]

            percent = (
                value
                / total
                * 100
            )

            print(
                f"  {domain:20} "
                f"{value:2}/{total:<2} "
                f"{percent:6.1f}%"
            )

        print()
        print(
            "Disagreements:",
            len(disagreements),
        )

        for disagreement in (
            disagreements
        ):
            print()
            print(
                disagreement
            )

        # IMPORTANT:
        #
        # Generated labels are not trusted
        # ground truth. This test deliberately
        # reports disagreements without failing.
        #
        # routing_gold.json remains the
        # authoritative regression suite.
        self.assertTrue(
            isinstance(
                cases,
                list,
            )
        )