"""Shared validation helpers for trusted-but-editable JSON configuration."""

from __future__ import annotations

import json
import math
from pathlib import Path
import re
from typing import Any


_SCRIPT_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def require_mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be a mapping")
    return value


def require_identifier(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _SCRIPT_IDENTIFIER.fullmatch(value):
        raise ValueError(f"{field} must be a valid script identifier")
    return value


def require_identifier_list(
    value: Any,
    field: str,
    *,
    allow_empty: bool = True,
) -> tuple[str, ...]:
    if not isinstance(value, list) or (not allow_empty and not value):
        qualifier = "non-empty " if not allow_empty else ""
        raise ValueError(f"{field} must be a {qualifier}list of script identifiers")
    result = tuple(
        require_identifier(item, f"{field}[{index}]")
        for index, item in enumerate(value)
    )
    if len(result) != len(set(result)):
        raise ValueError(f"{field} contains duplicate ids")
    return result


def require_bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field} must be a boolean")
    return value


def require_int(value: Any, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{field} must be an integer")
    return value


def require_finite_number(value: Any, field: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{field} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{field} must be finite")
    return result


def load_json(path: Path) -> Any:
    try:
        return json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_raise_invalid_constant,
        )
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid JSON in {path}: {error.msg}") from error


def _raise_invalid_constant(value: str) -> None:
    raise ValueError(f"Invalid non-finite JSON number: {value}")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result
