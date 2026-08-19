from __future__ import annotations

import json
import unittest
from pathlib import Path

from pgpt.routing.router import resolve_route


ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "evals" / "routing_temporal_pairs.json"


class TestRouterTemporalPairs(unittest.TestCase):
    """Local-model check for moving facts versus fixed facts/context."""

    def test_temporal_pairs(self) -> None:
        cases = json.loads(CASES.read_text(encoding="utf-8"))
        failures: list[str] = []

        for case in cases:
            result = resolve_route(
                case["prompt"],
                project_name="pgpt-cli",
                web_override=None,
                project_override=None,
                template_override=None,
                model_override=None,
                deep_override=None,
                symbol_hit=False,
            )

            for field, expected in case["expect"].items():
                actual = getattr(result, field)
                if actual != expected:
                    failures.append(
                        f"{case['id']}: {field} expected {expected!r}, got {actual!r}"
                    )

        if failures:
            self.fail("\n" + "\n".join(failures))


if __name__ == "__main__":
    unittest.main()
