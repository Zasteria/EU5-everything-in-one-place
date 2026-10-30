#!/usr/bin/env python3
"""A small reader for the game's script files: blocks, keys, operators, values.

`parse(text)` gives a list of `Entry(key, op, value)` where `value` is either a
string or another such list, so a block keeps both its order and its repeated
keys (`country_modifier` appears twice in some policies). `text(entries)` writes
a block back out on one line, which is how a game trigger is copied into a gate
verbatim.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

TOKEN = re.compile(r'"(?:[^"\\]|\\.)*"|[<>!?]?=|[<>]|[{}]|[^\s{}=<>!?"]+(?:\?(?!=)[^\s{}=<>!?"]*)*')


@dataclass
class Entry:
    key: str
    op: str
    value: "str | list[Entry]"


def strip_comments(text: str) -> str:
    out = []
    for line in text.split("\n"):
        quoted = False
        for i, ch in enumerate(line):
            if ch == '"':
                quoted = not quoted
            elif ch == "#" and not quoted:
                line = line[:i]
                break
        out.append(line)
    return "\n".join(out)


def without_blocks(text: str, key: str) -> str:
    """`text` with every `key = { ... }` cut out, braces balanced."""
    while True:
        match = re.search(r"\b%s\s*=\s*\{" % re.escape(key), text)
        if not match:
            return text
        depth = 0
        for i in range(match.end() - 1, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    break
        text = text[:match.start()] + text[i + 1:]


def parse(text: str) -> list[Entry]:
    tokens = TOKEN.findall(strip_comments(text.lstrip("﻿")))
    pos = 0

    def block() -> list[Entry]:
        nonlocal pos
        out: list[Entry] = []
        while pos < len(tokens):
            token = tokens[pos]
            if token == "}":
                pos += 1
                return out
            if token == "{":
                # An anonymous block, as in `custom_tags = { a b }`'s cousins.
                pos += 1
                out.append(Entry("", "", block()))
                continue
            if pos + 1 < len(tokens) and tokens[pos + 1] in ("=", "?=", "<", ">", "<=", ">=", "!="):
                op = tokens[pos + 1]
                pos += 2
                if pos < len(tokens) and tokens[pos] == "{":
                    pos += 1
                    out.append(Entry(token, op, block()))
                elif pos < len(tokens):
                    out.append(Entry(token, op, tokens[pos]))
                    pos += 1
                continue
            # A bare list element.
            out.append(Entry(token, "", ""))
            pos += 1
        return out

    return block()


def parse_file(path: Path) -> list[Entry]:
    return parse(path.read_text(encoding="utf-8-sig", errors="replace"))


def with_dlc(directory: Path) -> list[Path]:
    """The folder and the same folder in every DLC of the game it belongs to.

    1.4.5's Across the Pillars keeps its laws, privileges, reforms and the rest
    in `dlc/D009_across_the_pillars/in_game/common/`, where a base-only read
    never looks. The DLC's come after the base game's, as the engine reads them.
    """
    directory = Path(directory)
    for root in directory.parents:
        if (root / "dlc").is_dir() and (root / "in_game").is_dir():
            rel = directory.relative_to(root)
            return [directory] + [dlc / rel for dlc in sorted((root / "dlc").iterdir())
                                  if (dlc / rel).is_dir()]
    return [directory]


def txt_files(directory: Path) -> list[Path]:
    return [p for d in with_dlc(directory) for p in sorted(d.glob("*.txt"))]


def objects(directory: Path) -> dict[str, tuple[list[Entry], str]]:
    """Top-level `name = { ... }` objects of every .txt in a folder, by name.

    The second item is the file's name, which is what orders objects the way the
    game lists them. The DLC's copies of the folder are read too (`with_dlc`).
    """
    found: dict[str, tuple[list[Entry], str]] = {}
    if not directory.is_dir():
        return found
    for path in txt_files(directory):
        for entry in parse_file(path):
            # `INJECT:legal_code_law = { … }` (Across the Pillars, 1.4.5) adds to the
            # base object, `REPLACE:` swaps it; as the engine reads them, not as new
            # objects — his run 10-30: «Unknown trigger type: law:INJECT:legal_code_law».
            op, _, name = (entry.key or "").rpartition(":")
            if op and isinstance(entry.value, list):
                if op in ("INJECT", "TRY_INJECT", "INJECT_OR_CREATE"):
                    if name in found:
                        found[name] = (found[name][0] + entry.value, found[name][1])
                    elif op == "INJECT_OR_CREATE":
                        found[name] = (entry.value, path.name)
                elif op in ("REPLACE", "TRY_REPLACE", "REPLACE_OR_CREATE"):
                    if name in found or op == "REPLACE_OR_CREATE":
                        found[name] = (entry.value, path.name)
                continue
            if isinstance(entry.value, list) and entry.key and not entry.key.startswith("@"):
                found[entry.key] = (entry.value, path.name)
    return found


def get(block: list[Entry], key: str) -> "str | list[Entry] | None":
    for entry in block:
        if entry.key == key:
            return entry.value
    return None


def get_all(block: list[Entry], key: str) -> list["str | list[Entry]"]:
    return [entry.value for entry in block if entry.key == key]


def text(block: "str | list[Entry]") -> str:
    """One line of script that reads back as the same block."""
    if isinstance(block, str):
        return block
    parts = []
    for entry in block:
        if not entry.op:
            parts.append("{ %s }" % text(entry.value) if isinstance(entry.value, list) else entry.key)
        elif isinstance(entry.value, list):
            parts.append("%s %s { %s }" % (entry.key, entry.op, text(entry.value)) if entry.value
                         else "%s %s { }" % (entry.key, entry.op))
        else:
            parts.append("%s %s %s" % (entry.key, entry.op, entry.value))
    return " ".join(parts)


def walk(block: list[Entry], path: tuple[str, ...] = ()):
    """Every scalar `key op value` under a block, with the keys above it."""
    for entry in block:
        if isinstance(entry.value, list):
            yield from walk(entry.value, path + (entry.key,))
        else:
            yield path, entry
