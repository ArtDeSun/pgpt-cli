from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pgpt import skills


class TestSkills(unittest.TestCase):
    def test_user_skill_overrides_builtin(self) -> None:
        with tempfile.TemporaryDirectory() as builtin_dir, tempfile.TemporaryDirectory() as user_dir:
            builtin = Path(builtin_dir)
            user = Path(user_dir)
            (builtin / "review.md").write_text("builtin", encoding="utf-8")
            (user / "review.md").write_text("user", encoding="utf-8")
            (user / "custom.md").write_text("custom", encoding="utf-8")

            with patch.object(skills, "BUILTIN_SKILLS_DIR", builtin), patch.object(
                skills,
                "user_skills_dir",
                return_value=user,
            ):
                self.assertEqual(skills.list_skills(), ["custom", "review"])
                self.assertEqual(skills.load_skill("review"), "user")

    def test_skill_history_keeps_skill_at_end(self) -> None:
        with patch.object(skills, "load_skill", return_value="skill text"):
            history = [{"role": "user", "content": "old"}]
            value = skills.skill_history(history, "review")

        self.assertEqual(value[:-1], history)
        self.assertEqual(value[-1], {"role": "system", "content": "skill text"})
        self.assertEqual(history, [{"role": "user", "content": "old"}])

    def test_create_skill_writes_user_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as user_dir:
            root = Path(user_dir)
            with patch.object(skills, "user_skills_dir", return_value=root):
                path = skills.create_skill("my-review")
                self.assertEqual(path, root / "my-review.md")
                self.assertEqual(path.read_text(encoding="utf-8"), "# my-review\n\n")
                with self.assertRaises(RuntimeError):
                    skills.create_skill("my-review")

    def test_invalid_skill_name_rejected(self) -> None:
        with self.assertRaises(ValueError):
            skills.load_skill("../secret")


if __name__ == "__main__":
    unittest.main()
