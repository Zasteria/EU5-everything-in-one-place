"""Resolve the local Europa Universalis V installation directory."""

from __future__ import annotations

import os
from pathlib import Path


EU5_GAME_ROOT_ENV = "EU5_GAME_ROOT"
_EXPECTED_GAME_DATA = Path("game") / "in_game" / "common"


def configured_game_root(explicit: Path | str | None = None) -> Path | None:
    """Return an explicit root or the root configured through the environment."""
    value: Path | str | None = explicit
    if value is None:
        value = os.environ.get(EU5_GAME_ROOT_ENV)
    if value is None or not str(value).strip():
        return None
    return Path(value).expanduser()


def require_game_root(explicit: Path | str | None = None) -> Path:
    """Return a configured EU5 root and verify that it contains game data."""
    root = configured_game_root(explicit)
    if root is None:
        raise FileNotFoundError(
            "EU5 game data directory was not provided. "
            "Pass --game-root PATH or set EU5_GAME_ROOT."
        )

    expected = root / _EXPECTED_GAME_DATA
    if not expected.is_dir():
        raise FileNotFoundError(
            f"EU5 game data directory is invalid: {root}. "
            f"Expected to find: {expected}"
        )
    return root
