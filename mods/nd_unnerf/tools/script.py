"""Reads National Destinies' script files and keeps where every value sits.

`objects(text)` gives each top-level object of a file with its span, and
`leaves(text, start, end)` every numeric assignment inside one, addressed by
its path from the object: `(key, n)` steps, where `n` counts earlier siblings
with the same key, so a repeated `positive_modifier` keeps its place. The span
of each value is kept so a build can change one number and leave the author's
text, comments and layout as they are.
"""

from __future__ import annotations

import re

TOKEN = re.compile(r'"(?:[^"\\]|\\.)*"|#[^\n]*|[<>!?]?=|[<>]|[{}]|[^\s{}=<>!?"#]+')
NUMBER = re.compile(r"-?(?:\d+\.?\d*|\.\d+)$")


def tokens(text: str, start: int = 0, end: int | None = None):
    """(token, start, end) with comments dropped."""
    for m in TOKEN.finditer(text, start, len(text) if end is None else end):
        if not m.group().startswith("#"):
            yield m.group(), m.start(), m.end()


def objects(text: str):
    """[(key, key_start, open_brace, close_brace_end)] of top-level `key = { }`."""
    out, toks = [], list(tokens(text))
    i, depth = 0, 0
    while i < len(toks):
        tok = toks[i][0]
        if depth == 0 and i + 2 < len(toks) and toks[i + 1][0] == "=" and toks[i + 2][0] == "{":
            d, j = 0, i + 2
            while j < len(toks):
                if toks[j][0] == "{":
                    d += 1
                elif toks[j][0] == "}":
                    d -= 1
                    if d == 0:
                        break
                j += 1
            out.append((tok, toks[i][1], toks[i + 2][1], toks[j][2]))
            i = j + 1
            continue
        if tok == "{":
            depth += 1
        elif tok == "}":
            depth -= 1
        i += 1
    return out


def leaves(text: str, start: int, end: int):
    """{path: (value, op, value_start, value_end)} of numeric assignments.

    `start`..`end` is the object's own `{ ... }`. A path is a tuple of
    `(key, n)`; a bare list value (`{ a b }`) is skipped.
    """
    toks = list(tokens(text, start, end))[1:-1]
    out: dict = {}
    stack: list[tuple[tuple, dict]] = [((), {})]
    i = 0
    while i < len(toks):
        tok = toks[i][0]
        if tok == "}":
            stack.pop()
            i += 1
            continue
        if i + 2 < len(toks) + 1 and i + 1 < len(toks) and toks[i + 1][0] in ("=", "<", ">", "<=", ">=", "!=", "?="):
            path, seen = stack[-1]
            n = seen.get(tok, 0)
            seen[tok] = n + 1
            step = path + ((tok, n),)
            value, vs, ve = toks[i + 2] if i + 2 < len(toks) else ("", 0, 0)
            if value == "{":
                stack.append((step, {}))
                i += 3
                continue
            if NUMBER.match(value):
                out[step] = (float(value), toks[i + 1][0], vs, ve)
            i += 3
            continue
        if tok == "{":
            stack.append((stack[-1][0] + (("{}", 0),), {}))
        i += 1
    return out


def path_text(path: tuple) -> str:
    """`positive_modifier/global_population_growth`; `key#1` for a repeat."""
    return "/".join(f"{key}#{n}" if n else key for key, n in path)


def path_parse(text: str) -> tuple:
    out = []
    for step in text.split("/"):
        key, _, n = step.partition("#")
        out.append((key, int(n) if n else 0))
    return tuple(out)


def number(value: float) -> str:
    """As short as it is exact to six places: 0.0325, 2, -0.085."""
    text = f"{value:.6f}".rstrip("0").rstrip(".")
    return "0" if text in ("-0", "") else text
