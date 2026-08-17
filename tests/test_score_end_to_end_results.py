from __future__ import annotations

import unittest
from unittest.mock import patch

from tools import score_end_to_end_results as scorer


class TestScoreEndToEndResults(unittest.TestCase):
    def test_deterministic_source_ids(self) -> None:
        result = scorer._run_deterministic_check(
            answer="A [S1] and B [S2].\n### Sources\n[S3]",
            check={"type": "inline_source_ids", "before": "### Sources", "minimum_distinct": 2},
        )
        self.assertTrue(result["passed"])
        self.assertEqual(result["details"]["distinct_source_ids"], [1, 2])

    def test_forbidden_regex(self) -> None:
        result = scorer._run_deterministic_check(
            answer="safe text",
            check={"type": "forbidden_regex", "patterns": ["secret"]},
        )
        self.assertTrue(result["passed"])

    def test_type_specific_schemas(self) -> None:
        self.assertEqual(set(scorer._criterion_schema("required")["properties"]), {"satisfied"})
        self.assertEqual(set(scorer._criterion_schema("forbidden")["properties"]), {"violated"})

    def test_forbidden_false_stays_false(self) -> None:
        response = {"message": {"content": '{"violated": false}'}, "done_reason": "stop"}
        with patch.object(scorer, "json_request", return_value=response):
            result = scorer._judge_criterion_once(
                model="judge",
                criterion_type="forbidden",
                prompt="question",
                answer="safe answer",
                criterion="forbidden thing",
                evaluation_context=[],
                evaluation_evidence=None,
            )
        self.assertFalse(result["value"])

    def test_required_true_stays_true(self) -> None:
        response = {"message": {"content": '{"satisfied": true}'}, "done_reason": "stop"}
        with patch.object(scorer, "json_request", return_value=response):
            result = scorer._judge_criterion_once(
                model="judge",
                criterion_type="required",
                prompt="question",
                answer="good answer",
                criterion="required thing",
                evaluation_context=[],
                evaluation_evidence=None,
            )
        self.assertTrue(result["value"])

    def test_retry_after_bad_json(self) -> None:
        responses = [
            {"message": {"content": "{bad"}},
            {"message": {"content": '{"satisfied": true}'}},
        ]
        with patch.object(scorer, "json_request", side_effect=responses):
            result = scorer._judge_criterion(
                model="judge",
                criterion_type="required",
                prompt="question",
                answer="answer",
                criterion="criterion",
                evaluation_context=[],
                evaluation_evidence=None,
            )
        self.assertTrue(result["value"])
        self.assertEqual(result["attempts"], 2)

    def test_judge_aggregates_criteria(self) -> None:
        values = {("required", "r1"): True, ("required", "r2"): False, ("forbidden", "f1"): True}

        def fake_judge(**kwargs):
            return {
                "value": values[(kwargs["criterion_type"], kwargs["criterion"])],
                "attempts": 1,
                "metrics": {},
            }

        with patch.object(scorer, "_judge_criterion", side_effect=fake_judge):
            result = scorer._judge(
                model="judge",
                prompt="question",
                answer="answer",
                rubric={"required_points": ["r1", "r2"], "forbidden_points": ["f1"]},
            )
        judgment = result["judgment"]
        self.assertEqual(judgment["required_passed"], [True, False])
        self.assertEqual(judgment["forbidden_violated"], [True])
        self.assertFalse(judgment["passed"])
        self.assertEqual(judgment["score"], 1)
        self.assertEqual(len(judgment["issues"]), 2)


if __name__ == "__main__":
    unittest.main()
