from __future__ import annotations

import unittest

from pgpt.cli import build_parser


class TestCliParser(unittest.TestCase):
    def test_local_server_command(self) -> None:
        args = build_parser().parse_args(["server", "--port", "9999"])
        self.assertEqual(args.command, "server")
        self.assertEqual(args.port, 9999)

    def test_legacy_privategpt_serve_command_is_preserved(self) -> None:
        args = build_parser().parse_args(["serve"])
        self.assertEqual(args.command, "serve")

    def test_web_usage_command(self) -> None:
        args = build_parser().parse_args(["web-usage"])
        self.assertEqual(args.command, "web-usage")

    def test_skill_new_command(self) -> None:
        args = build_parser().parse_args(["skill-new", "my-review"])
        self.assertEqual(args.command, "skill-new")
        self.assertEqual(args.name, "my-review")

    def test_knowledge_add_command(self) -> None:
        args = build_parser().parse_args(
            [
                "knowledge-add",
                "/tmp/notes",
                "--name",
                "notes",
                "--collection",
                "notes-v1",
                "--ignore",
                "draft.txt",
            ]
        )
        self.assertEqual(args.command, "knowledge-add")
        self.assertEqual(args.path, "/tmp/notes")
        self.assertEqual(args.name, "notes")
        self.assertEqual(args.collection, "notes-v1")
        self.assertEqual(args.ignore, ["draft.txt"])

    def test_ask_skill_argument(self) -> None:
        args = build_parser().parse_args(["ask", "review this", "--skill", "code-review"])
        self.assertEqual(args.skill, "code-review")
        self.assertEqual(args.prompt, "review this")

    def test_lookup_web_mode_is_explicitly_available(self) -> None:
        ask = build_parser().parse_args(["ask", "weather", "--web", "lookup"])
        chat = build_parser().parse_args(["chat", "--web", "lookup"])
        self.assertEqual(ask.web, "lookup")
        self.assertEqual(chat.web, "lookup")

    def test_off_web_mode_is_local_only_override(self) -> None:
        args = build_parser().parse_args(["ask", "weather", "--web", "off"])
        self.assertEqual(args.web, "off")


if __name__ == "__main__":
    unittest.main()
