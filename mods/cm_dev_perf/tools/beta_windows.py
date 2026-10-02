"""CM Dev's vanilla windows rebuilt on the 2026-10-01 beta: the beta's file plus
CM's own hooks, re-applied by anchor.

CM Dev replaces five vanilla windows whole (`location_window`,
`production_lateralview`, `town_rights`, `building_view`,
`expand_raw_goods_lateralview`), and its copies are Glorp UI's 1.3 layout: a
three-way merge onto the beta leaves 12 000 conflicting lines in
`location_window` alone. What CM itself adds is small — a dozen hook lines per
window — so the beta's window is taken whole and those hooks are put back.

Each `beta/<window>.json` is a list of edits, applied in order to the beta's
text. An edit names an `anchor`: a substring that occurs **exactly once** in
the text at that moment (an edit fails the build otherwise, rather than land in
the wrong block — windows.md, «правка пяти файлов»).

    {"op": "replace_block", "anchor": "...", "up": 0, "text": "..."}
        the block holding the anchor (`up` more levels out) becomes `text`
    {"op": "insert_after_block" | "insert_before_block", "anchor": ..., "up": 0, "text": ...}
    {"op": "insert_after_line" | "insert_before_line", "anchor": ..., "text": ...}
        `text` on its own line(s) next to the line holding the anchor
    {"op": "replace", "anchor": ..., "text": ...}
        the anchor itself becomes `text`
    {"op": "beta_type", "name": "X"}
        the `type X = …` / `template X` block becomes the beta's own definition
        of X (from any vanilla `.gui`); CM's edits to it then go on as edits
    {"why": "..."}  on any edit — what CM wanted there; kept for the next port

A spec named after a vanilla window starts from the beta's window; a spec named
after one of CM's own files (`cm_*.gui`) starts from CM's file.

Indentation in `text` is written as it should stand; nothing is re-indented.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

TYPE_HEAD = r"^[ \t]*(?:type\s+{0}\s*=\s*[A-Za-z_0-9]+|template\s+{0})\s*\{{"


class EditFailed(SystemExit):
    pass


def _once(text: str, anchor: str, where: str) -> int:
    count = text.count(anchor)
    if count != 1:
        raise EditFailed(f"{where}: anchor occurs {count} times: {anchor[:80]!r}")
    return text.index(anchor)


def _block(text: str, at: int, up: int) -> tuple[int, int]:
    """(start of the line opening the block around `at`, end past its `}`)."""
    open_at = at
    for _ in range(up + 1):
        depth = 0
        i = open_at - 1
        while i >= 0:
            c = text[i]
            if c == "}":
                depth += 1
            elif c == "{":
                if depth == 0:
                    break
                depth -= 1
            i -= 1
        if i < 0:
            raise EditFailed("no enclosing block")
        open_at = i
    start = text.rfind("\n", 0, open_at) + 1
    depth, j = 0, open_at
    while j < len(text):
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
            if depth == 0:
                return start, j + 1
        j += 1
    raise EditFailed("block never closes")


def type_block(text: str, name: str) -> tuple[int, int] | None:
    found = list(re.finditer(TYPE_HEAD.format(re.escape(name)), text, re.M))
    if len(found) != 1:
        return None
    brace = found[0].end() - 1
    return _block(text, brace + 1, 0)


def beta_type(game_gui: Path, name: str) -> str:
    hits = []
    for path in sorted(game_gui.rglob("*.gui")):
        text = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
        span = type_block(text, name)
        if span:
            hits.append(text[span[0]:span[1]])
    if len(hits) != 1:
        raise EditFailed(f"type {name}: defined {len(hits)} times in the beta")
    return hits[0]


def apply(text: str, edits: list[dict], where: str, game_gui: Path | None = None) -> str:
    for number, edit in enumerate(edits, 1):
        if edit["op"] == "beta_type":
            span = type_block(text, edit["name"])
            if not span:
                raise EditFailed(f"{where}: no single type {edit['name']}")
            text = text[:span[0]] + beta_type(game_gui, edit["name"]) + text[span[1]:]
            continue
        op, anchor = edit["op"], edit["anchor"]
        payload = edit.get("text", "")
        label = f"{where} edit {number} ({op})"
        at = _once(text, anchor, label)
        if op == "replace":
            text = text[:at] + payload + text[at + len(anchor):]
        elif op in ("insert_after_line", "insert_before_line"):
            if op == "insert_after_line":
                cut = text.find("\n", at)
                cut = len(text) if cut < 0 else cut + 1
            else:
                cut = text.rfind("\n", 0, at) + 1
            text = text[:cut] + payload.rstrip("\n") + "\n" + text[cut:]
        else:
            start, end = _block(text, at, edit.get("up", 0))
            if op == "replace_block":
                text = text[:start] + payload.rstrip("\n") + text[end:]
            elif op == "insert_after_block":
                text = text[:end] + "\n" + payload.rstrip("\n") + text[end:]
            elif op == "insert_before_block":
                text = text[:start] + payload.rstrip("\n") + "\n" + text[start:]
            else:
                raise EditFailed(f"{label}: unknown op")
    return text


def rebuild(game_gui: Path, specs: Path, out_gui: Path) -> list[str]:
    """Every file with a spec: the beta's window (or CM's own file), CM's edits on top."""
    done = []
    for spec in sorted(specs.glob("*.json")):
        window = spec.stem + ".gui"
        base = game_gui / window if (game_gui / window).exists() else out_gui / window
        text = base.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
        edits = json.loads(spec.read_text(encoding="utf-8"))
        text = apply(text, edits, window, game_gui)
        (out_gui / window).write_text("﻿" + text, encoding="utf-8")
        done.append(window)
    return done


if __name__ == "__main__":
    # Try one spec without a rebuild: `beta_windows.py <window> [out.gui]`.
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tools"))
    import refs
    name = sys.argv[1].removesuffix(".gui")
    game_gui = refs.GAME_GUI
    mod_gui = refs.REPO / "mods/cm_dev_perf/in_game/gui"
    base = game_gui / f"{name}.gui"
    base = base if base.exists() else mod_gui / f"{name}.gui"
    spec = Path(__file__).resolve().parent / "beta" / f"{name}.json"
    text = base.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    result = apply(text, json.loads(spec.read_text(encoding="utf-8")), name, game_gui)
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    if out:
        out.write_text(result, encoding="utf-8")
    print(f"{name}: {len(json.loads(spec.read_text(encoding='utf-8')))} edits applied to {base.relative_to(refs.REPO)}")
