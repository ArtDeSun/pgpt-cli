from __future__ import annotations

import unittest
from types import SimpleNamespace

from pgpt.quality.repair import apply_deterministic_repairs
from pgpt.quality.verify import verify_answer
from pgpt.retrieval.web import WebResult


def route(execution: str, template: str = "general"):
    return SimpleNamespace(execution=execution, template=template)


def web_results(count: int) -> list[WebResult]:
    return [
        WebResult(title=f"Source {i}", url=f"https://example.com/{i}", description="evidence", extra_snippets=[])
        for i in range(1, count + 1)
    ]


class TestQualityVerifier(unittest.TestCase):
    def test_completion_contract(self) -> None:
        result = verify_answer(
            answer="", route=route("local"), web_results=[], project_files=[], done_reason="length"
        )
        self.assertIn("Answer is empty.", result.issues)
        self.assertIn("Answer still ended because of the token limit.", result.issues)

    def test_web_citations_are_required_and_validated(self) -> None:
        missing = verify_answer(
            answer="Current value is 5.", route=route("web_lookup"), web_results=web_results(1), project_files=[], done_reason="stop"
        )
        self.assertIn("Web answer has no inline source citations.", missing.issues)
        invalid = verify_answer(
            answer="Current value is 5. [S2]", route=route("web_lookup"), web_results=web_results(1), project_files=[], done_reason="stop"
        )
        self.assertIn("Invalid source IDs: S2", invalid.issues)
        valid = verify_answer(
            answer="Current value is 5. [S1]", route=route("web_lookup"), web_results=web_results(1), project_files=[], done_reason="stop"
        )
        self.assertTrue(valid.passed)

    def test_research_requires_multiple_sources_and_comparison(self) -> None:
        weak = verify_answer(
            answer="One source says X. [S1]", route=route("web_research"), web_results=web_results(2), project_files=[], done_reason="stop"
        )
        self.assertIn("Research answer uses fewer than two sources.", weak.issues)
        self.assertIn("Research answer does not meaningfully compare the evidence.", weak.issues)
        strong = verify_answer(
            answer="Both sources agree on X [S1], whereas they differ on Y [S2].",
            route=route("web_research"), web_results=web_results(2), project_files=[], done_reason="stop"
        )
        self.assertTrue(strong.passed)

    def test_project_explain_requires_files_and_blocks_example_usage(self) -> None:
        result = verify_answer(
            answer="Explanation.\n\n## Example Usage\n\nDo this.",
            route=route("project", "explain-code"), web_results=[], project_files=[], done_reason="stop"
        )
        self.assertIn("Project answer has no retrieved source files.", result.issues)
        self.assertIn("Explain-code answer generated an Example Usage section.", result.issues)


class TestDeterministicRepair(unittest.TestCase):
    def test_example_usage_section_is_removed_without_touching_following_section(self) -> None:
        issue = "Explain-code answer generated an Example Usage section."
        answer = "# Explanation\n\nKeep this.\n\n## Example Usage\n\nRemove this.\n\n## Details\n\nKeep details."
        repaired, applied = apply_deterministic_repairs(answer=answer, issues=[issue])
        self.assertEqual(applied, [issue])
        self.assertNotIn("Remove this", repaired)
        self.assertIn("Keep this", repaired)
        self.assertIn("Keep details", repaired)

    def test_unrelated_issue_does_not_change_answer(self) -> None:
        answer = "Keep me"
        self.assertEqual(apply_deterministic_repairs(answer=answer, issues=["other"]), (answer, []))


if __name__ == "__main__":
    unittest.main()
