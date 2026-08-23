from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from pgpt import server


class TestServerControls(unittest.TestCase):
    def test_manual_controls_are_parsed(self) -> None:
        payload = {
            "messages": [{"role": "user", "content": "question"}],
            "pgpt": {
                "project": "pgpt-cli",
                "web": "lookup",
                "context": False,
                "template": "debug",
                "model": "m",
                "deep": True,
                "history_mode": "off",
                "answer_length": "long",
            },
        }
        with patch.object(server, "skill_history", side_effect=lambda h, s: h):
            value = server._prepare_request(payload)

        self.assertIsNone(value.project)
        self.assertEqual(
            (
                value.web,
                value.context,
                value.template,
                value.model,
                value.deep,
                value.history_mode,
                value.answer_length,
            ),
            ("lookup", False, "debug", "m", True, "off", "long"),
        )

    def test_bad_control_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            server._prepare_request(
                {
                    "messages": [{"role": "user", "content": "x"}],
                    "pgpt": {"answer_length": "huge"},
                }
            )

    def test_meta_exposes_only_user_contexts(self) -> None:
        with (
            patch.object(server, "_available_models", return_value=["a:1"]),
            patch.object(server, "user_project_names", return_value=["one"]),
            patch.object(
                server,
                "_project_details",
                return_value=[
                    {
                        "name": "one",
                        "source_dir": "/tmp/one",
                        "exists": True,
                        "collection": "one",
                    }
                ],
            ),
            patch.object(server, "list_skills", return_value=[]),
            patch.object(server, "cfg_path", return_value=Path("/tmp/runtime")),
        ):
            meta = server._meta()

        self.assertEqual(meta["models"], ["a:1"])
        self.assertEqual(meta["projects"], ["one"])
        self.assertEqual(meta["project_details"][0]["source_dir"], "/tmp/one")
        self.assertIsNone(meta["default_project"])


if __name__ == "__main__":
    unittest.main()
