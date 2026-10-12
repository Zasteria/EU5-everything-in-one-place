from pathlib import Path
import os
import tempfile
import unittest
from unittest.mock import patch

from src.eu5autobuild.game_root import (
    EU5_GAME_ROOT_ENV,
    configured_game_root,
    require_game_root,
)


class GameRootTests(unittest.TestCase):
    def test_explicit_root_takes_precedence_over_environment(self):
        with patch.dict(os.environ, {EU5_GAME_ROOT_ENV: "environment-root"}):
            self.assertEqual(configured_game_root(Path("explicit-root")), Path("explicit-root"))

    def test_environment_root_is_used_when_explicit_root_is_absent(self):
        with patch.dict(os.environ, {EU5_GAME_ROOT_ENV: "configured-root"}):
            self.assertEqual(configured_game_root(), Path("configured-root"))

    def test_empty_environment_value_is_treated_as_missing(self):
        with patch.dict(os.environ, {EU5_GAME_ROOT_ENV: "  "}):
            self.assertIsNone(configured_game_root())

    def test_missing_configuration_has_actionable_error(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(
                FileNotFoundError,
                "Pass --game-root PATH or set EU5_GAME_ROOT",
            ):
                require_game_root()

    def test_configured_root_must_contain_common_game_data(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with self.assertRaisesRegex(FileNotFoundError, "Expected to find"):
                require_game_root(root)
            (root / "game" / "in_game" / "common").mkdir(parents=True)
            self.assertEqual(require_game_root(root), root)


if __name__ == "__main__":
    unittest.main()
