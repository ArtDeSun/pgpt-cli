from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "web" / "index.html"


class TestWebUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = INDEX.read_text(encoding="utf-8")

    def test_ui_is_self_contained_and_uses_local_api(self) -> None:
        self.assertIn("/v1/chat/completions", self.text)
        self.assertIn("/api/meta", self.text)
        self.assertIn('id="project"', self.text)
        self.assertIn('id="skill"', self.text)
        self.assertNotIn("<script src=", self.text)
        self.assertNotIn("<link rel=", self.text)

    def test_multi_chat_surface_has_recents_pinning_and_search(self) -> None:
        for value in ("Pinned", "Recents", "Search chats", "data-pin-chat", "data-delete-chat", "Export chat"):
            with self.subTest(value=value): self.assertIn(value, self.text)

    def test_file_and_response_workflows_are_present(self) -> None:
        for value in ('id="fileInput"', "/api/responses", "Download Markdown", "downloadBlob", "data-download-attachment"):
            with self.subTest(value=value): self.assertIn(value, self.text)

    def test_markdown_rendering_links_and_code_controls(self) -> None:
        for value in ("renderMarkdown", "copy-code", 'target=\"_blank\"', "code-block", "code.inline"):
            with self.subTest(value=value): self.assertIn(value, self.text)

    def test_loading_timestamps_and_followups_are_visible_features(self) -> None:
        for value in ("loadingTimer", "spinner", "formatFullTime", "suggestions", "data-suggestion"):
            with self.subTest(value=value): self.assertIn(value, self.text)

    def test_browser_uses_real_streaming_and_server_status(self) -> None:
        for value in ("stream:true", "response.body.getReader()", "consumeSseBlock", 'event === \'status\'', 'event === \'replace\'', 'event === \'done\''):
            with self.subTest(value=value): self.assertIn(value, self.text)

    def test_web_mode_and_usage_controls_are_clear(self) -> None:
        self.assertIn("/api/web-usage", self.text)
        self.assertIn("off · local-only", self.text)
        self.assertIn("Brave", self.text)


if __name__ == "__main__": unittest.main()
