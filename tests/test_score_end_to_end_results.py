from __future__ import annotations

import unittest
from unittest.mock import patch

from tools import score_end_to_end_results as scorer


class TestScoreEndToEndResults(unittest.TestCase):
    def test_deterministic_source_ids(self) -> None:
        result = scorer._run_deterministic_check(
            answer="A [S1] and B [S2].\n### Sources\n[S3]",
            check={
                "type": "inline_source_ids",
                "before": "### Sources",
                "minimum_distinct": 2,
            },
        )
        self.assertTrue(result["passed"])
        self.assertEqual(result["details"]["distinct_source_ids"], [1, 2])

    def test_forbidden_regex(self) -> None:
        result = scorer._run_deterministic_check(
            answer="safe text",
            check={"type": "forbidden_regex", "patterns": ["secret"]},
        )
        self.assertTrue(result["passed"])

    def test_judge_aggregates_independent_criteria(self) -> None:
        values = {
            ("required", "r1"): (True, "r1 yes"),
            ("required", "r2"): (False, "r2 no"),
            ("forbidden", "f1"): (True, "f1 violated"),
        }

        def fake_judge(**kwargs):
            passed, reason = values[(kwargs["criterion_type"], kwargs["criterion"])]
            return {
                "result": {"passed": passed, "reason": reason},
                "attempts": 1,
                "metrics": {},
            }

        with patch.object(scorer, "_judge_criterion", side_effect=fake_judge):
            result = scorer._judge(
                model="judge",
                prompt="question",
                answer="answer",
                rubric={
                    "required_points": ["r1", "r2"],
                    "forbidden_points": ["f1"],
                },
            )

        judgment = result["judgment"]
        self.assertEqual(judgment["required_passed"], [True, False])
        self.assertEqual(judgment["forbidden_violated"], [True])
        self.assertFalse(judgment["passed"])
        self.assertEqual(judgment["score"], 1)
        self.assertEqual(judgment["issues"], ["r2 no", "f1 violated"])

    def test_criterion_request_uses_single_criterion_schema(self) -> None:
        response = {
            "message": {
                "content": '{"passed": true, "reason": "supported"}',
            },
            "done_reason": "stop",
        }
        with patch.object(scorer, "json_request", return_value=response) as request_mock:
            result = scorer._judge_criterion_once(
                model="judge",
                system_prompt="required prompt",
                request={"criterion": "criterion", "assistant_answer": "answer"},
            )

        self.assertTrue(result["result"]["passed"])
        payload = request_mock.call_args.kwargs["payload"]
        self.assertEqual(payload["format"], scorer._criterion_schema())
        request_text = payload["messages"][1]["content"]
        self.assertIn('"criterion": "criterion"', request_text)


if __name__ == "__main__":
    unittest.main()
