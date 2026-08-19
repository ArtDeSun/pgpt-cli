from __future__ import annotations

import json
import unittest
from pathlib import Path

from pgpt.routing.router import resolve_route


ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "evals" / "routing_gold.json"
FIELDS = ("source", "web_mode", "task", "freshness")


class TestRouterDataset(unittest.TestCase):
    """Local Ollama acceptance test for the human-curated routing cases."""

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
            actual = result.__dict__

            for field in FIELDS:
                if field in case["expect"] and actual[field] != case["expect"][field]:
                    failures.append(
                        f"{case['id']}: {field} expected "
                        f"{case['expect'][field]!r}, got {actual[field]!r}"
                    )

        if failures:
            self.fail("\n" + "\n".join(failures))


if __name__ == "__main__":
    unittest.main()
