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

    def test_skill_new_command(self) -> None:
        args = build_parser().parse_args(["skill-new", "my-review"])
        self.assertEqual(args.command, "skill-new")
        self.assertEqual(args.name, "my-review")

    def test_ask_skill_argument(self) -> None:
        args = build_parser().parse_args(
            ["ask", "review this", "--skill", "code-review"]
        )
        self.assertEqual(args.skill, "code-review")
        self.assertEqual(args.prompt, "review this")


if __name__ == "__main__":
    unittest.main()
