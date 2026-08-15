from __future__ import annotations

import json
from pathlib import Path
from unittest import TestCase

from pgpt.routing.router import resolve_route


ROOT = Path(__file__).resolve().parents[1]

DATASET_PATH = (
    ROOT
    / "evals"
    / "routing_regressions.json"
)

FIELDS = (
    "source",
    "web_mode",
    "task",
    "freshness",
    "complexity",
)


class TestRouterRegressions(
    TestCase
):
    def test_routing_regressions(
        self,
    ) -> None:
        with DATASET_PATH.open(
            "r",
            encoding="utf-8",
        ) as file:
            cases = json.load(file)

        failures: list[str] = []

        for case in cases:
            decision = resolve_route(
                case["prompt"],
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

            expected = case["expect"]

            for field in FIELDS:
                if field not in expected:
                    continue

                if actual[field] != expected[field]:
                    failures.append(
                        (
                            f"{case['id']}: "
                            f"{field} expected "
                            f"{expected[field]!r}, "
                            f"got {actual[field]!r} "
                            f"| prompt="
                            f"{case['prompt']!r}"
                        )
                    )

        if failures:
            self.fail(
                "\n"
                + "\n".join(failures)
            )