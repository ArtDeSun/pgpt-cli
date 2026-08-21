from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "web" / "index.html"


class TestWebUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = INDEX.read_text(encoding="utf-8")

    def test_self_contained(self) -> None:
        self.assertIn("/v1/chat/completions", self.text)
        self.assertIn("/api/meta", self.text)
        self.assertNotIn("<script src=", self.text)

    def test_chat_features(self) -> None:
        for value in (
            "Pinned",
            "Recents",
            "Search chats",
            "Export chat",
            "/api/responses",
            "Download Markdown",
        ):
            with self.subTest(value=value):
                self.assertIn(value, self.text)

    def test_settings_and_manual_controls(self) -> None:
        self.assertIn('id="controls" class="drawer"', self.text)
        self.assertNotIn('id="controls" class="drawer open"', self.text)
        for value in (
            "Routing & context",
            "Capabilities",
            'id="projectMode"',
            "Force project",
            "Force lookup",
            "Force research",
            'id="model"',
            'id="task"',
            'id="historyMode"',
            "Smart",
            'id="answerLength"',
            'id="reasoning"',
            "Add knowledge folder",
        ):
            with self.subTest(value=value):
                self.assertIn(value, self.text)

    def test_rendering_streaming_feedback_and_trace(self) -> None:
        for value in (
            "renderMarkdown",
            "copy-code",
            "stream:true",
            ".body.getReader()",
            "e==='status'",
            "e==='replace'",
            "e==='done'",
            "Run details",
            "trace-events",
            ":hover",
            ":active",
            ":focus-visible",
            "data-suggestion",
        ):
            with self.subTest(value=value):
                self.assertIn(value, self.text)

    def test_capability_status_and_brave_usage(self) -> None:
        for value in (
            "Ollama models",
            "Brave Search",
            "Project context",
            "Skills",
            "api_monthly_unlimited",
            "/api/knowledge/ingest",
            "/api/web-usage",
            "Off · local-only",
        ):
            with self.subTest(value=value):
                self.assertIn(value, self.text)

    def test_activity_feedback_and_submit_contrast(self) -> None:
        for value in (
            "stageLabel",
            "Thinking",
            "Retrieving",
            "Analyzing",
            "Working",
            "Reviewing",
            "activity-indicator",
            "@keyframes activityPulse",
            'aria-live="polite"',
            ".send{",
            "background:var(--accent)",
            "prefers-reduced-motion",
        ):
            with self.subTest(value=value):
                self.assertIn(value, self.text)


if __name__ == "__main__":
    unittest.main()
