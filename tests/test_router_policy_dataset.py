from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from pgpt.routing.router import resolve_route

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "evals" / "routing_policy_cases.json"
FIELDS = ("source", "web_mode", "task", "freshness")


class TestRouterPolicyDataset(unittest.TestCase):
    def test_policy_dataset(self) -> None:
        cases = json.loads(CASES.read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(cases), 100)
        failures: list[str] = []

        for case in cases:
            semantic = case.get("classifier", "unused")
            value = "unknown" if semantic == "unused" else semantic
            with self.subTest(case=case["id"]), patch(
                "pgpt.routing.router.classify_web_need", return_value=value
            ) as classifier:
                result = resolve_route(
                    case["prompt"],
                    project_name="pgpt-cli",
                    web_override=case.get("web_override"),
                    project_override=case.get("project_override"),
                    template_override=case.get("template_override"),
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
                if semantic == "unused":
                    classifier.assert_not_called()
                else:
                    classifier.assert_called_once_with(case["prompt"])

        if failures:
            self.fail("\n" + "\n".join(failures))


if __name__ == "__main__":
    unittest.main()
