from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pgpt import config


class TestConfigPaths(unittest.TestCase):
    def test_relative_path_is_repo_relative(self) -> None:
        self.assertEqual(
            config.expand("tests/fixtures/historical_pgpt"),
            (config.ROOT / "tests/fixtures/historical_pgpt").resolve(),
        )

    def test_absolute_path_remains_absolute(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory).resolve()
            self.assertEqual(config.expand(str(path)), path)


if __name__ == "__main__":
    unittest.main()
