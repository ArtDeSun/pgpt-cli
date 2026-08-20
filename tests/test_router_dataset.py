from __future__ import annotations

import json
import os
import unittest
from pathlib import Path

from pgpt.routing.router import resolve_route


ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "evals" / "routing_gold.json"
FIELDS = ("source", "web_mode", "task")
RUN_LOCAL = os.getenv("PGPT_RUN_LOCAL_MODEL_TESTS") == "1"


@unittest.skipUnless(RUN_LOCAL, "set PGPT_RUN_LOCAL_MODEL_TESTS=1; requires Ollama")
class TestRouterDataset(unittest.TestCase):
    """Human-run acceptance test for the real router model."""

    def test_routing_gold(self) -> None:
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
                symbol_hit=case.get("symbol_hit", False),
            )
            for field in FIELDS:
                expected = case["expect"][field]
                actual = getattr(result, field)
                if actual != expected:
                    failures.append(
                        f"{case['id']}: {field} expected {expected!r}, got {actual!r}"
                    )

        if failures:
            self.fail("\n" + "\n".join(failures))


if __name__ == "__main__":
    unittest.main()
