from __future__ import annotations

import json
from pathlib import Path
from unittest import TestCase

from pgpt.routing.router import resolve_route


ROOT = Path(__file__).resolve().parents[1]
DATASET_PATH = ROOT / "evals" / "routing_temporal_pairs.json"


class TestRouterTemporalPairs(TestCase):
    def test_temporal_minimal_pairs(self) -> None:
        with DATASET_PATH.open("r", encoding="utf-8") as file:
            cases = json.load(file)

        failures: list[str] = []

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
            expected = case["expect"]
            actual = {
                "source": decision.source,
                "freshness": decision.freshness,
            }

            for field, expected_value in expected.items():
                if actual[field] != expected_value:
                    failures.append(
                        f"{case['id']}: {field} expected "
                        f"{expected_value!r}, got {actual[field]!r} "
                        f"| prompt={case['prompt']!r}"
                    )

        if failures:
            self.fail("\n" + "\n".join(failures))


if __name__ == "__main__":
    import unittest

    unittest.main()
