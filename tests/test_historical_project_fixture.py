from __future__ import annotations

import unittest

from pgpt.config import CONFIG, expand


class TestHistoricalProjectFixture(unittest.TestCase):
    def test_historical_project_profile_is_self_contained(self) -> None:
        project = CONFIG["projects"]["pgpt-cli-history"]
        root = expand(project["source_dir"])
        selector = root / "pgpt" / "models" / "selector.py"
        snapshot = root / "SNAPSHOT.md"

        self.assertTrue(root.is_dir())
        self.assertTrue(selector.is_file())
        self.assertTrue(snapshot.is_file())
        self.assertIn("def select_model(", selector.read_text(encoding="utf-8"))
        self.assertIn(
            "bc2343a14db511b4103afdf45e3fa8c81067e12c",
            snapshot.read_text(encoding="utf-8"),
        )


if __name__ == "__main__":
    unittest.main()
