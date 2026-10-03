#!/usr/bin/env python3
"""Rebuilds `qol_beta`: Quality of Life by Buddy, fitted to the 2026-10-01 beta.

A copy of `reference/mods/<QoL>/` with three changes, and nothing else:

1. **No map borders.** QoL replaces the game's `pdxborder.shader` and eight
   border textures with its 1.3 copies; on the beta's renderer they draw the
   country borders wrong (his run, 2026-10-01). Dropped whole — the game's own
   borders come back.
2. **Forts from the beta's files.** QoL replaces `forts.txt` and
   `coastal_forts.txt` whole to add one `allow` line per fort; its copies are
   1.3's and lose the icons the beta gave every fort. Here the beta's files are
   taken and the same line is put back in.
3. **The town rights card from the beta's file.** QoL replaces
   `town_rights_type.gui` whole for one marker row; the beta's card added a row
   of icons after the name. Here the beta's card is taken, QoL's templates go
   above it and its marker row goes after the name, as its own header asks.

Everything else — child education, the parliament pause, papal votes,
cooldown alerts, cabinet actions — is QoL's own script; every trigger, effect
and on_action it names is in the beta's dumps (checked 2026-10-01).

Names are left alone (`qol_*`, CMF `mod_id`): load it **instead of** QoL, never
alongside it.

    python3 mods/qol_beta/tools/port_from_qol.py
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tools"))

import refs  # noqa: E402

MOD = refs.REPO / "mods/qol_beta"
SRC = refs.mod("calidad_de_vida_eu5")

REVISION = 1

DROPPED = (
    "main_menu/gfx/FX/pdxborder.shader",
    "in_game/gfx/map/borders",
)

FORTS = ("in_game/common/building_types/forts.txt",
         "in_game/common/building_types/coastal_forts.txt")
CARD = "in_game/gui/attribute_columns/town_rights_type.gui"
ALLOW_LINE = "qol_fort_build_allowed = yes"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")


def blocks(text: str):
    """(name, start, end) of every top-level `name = { ... }`."""
    depth, start, name = 0, None, None
    for match in re.finditer(r"([A-Za-z_0-9]+)\s*=\s*\{|\{|\}", text):
        token = match.group(0)
        if token.endswith("{"):
            if depth == 0:
                start, name = match.start(), match.group(1)
            depth += 1
        else:
            depth -= 1
            if depth == 0 and start is not None:
                yield name, start, match.end()


def fort(text: str) -> str:
    """The beta's fort file with QoL's line in every fort's `allow`."""
    out, last, count = [], 0, 0
    for name, start, end in blocks(text):
        body = text[start:end]
        allow = re.search(r"\n(\t)allow\s*=\s*\{", body)
        if allow:
            cut = allow.end()
            body = body[:cut] + "\n\t\t" + ALLOW_LINE + body[cut:]
        else:
            anchor = re.search(r"\n\tunique_production_methods\s*=\s*\{", body)
            if not anchor:
                raise SystemExit(f"{name}: no allow and no unique_production_methods to anchor on")
            body = (body[:anchor.start()] + "\n\n\tallow = {\n\t\t" + ALLOW_LINE
                    + "\n\t}\n" + body[anchor.start():])
        out.append(text[last:start] + body)
        last, count = end, count + 1
    if not count:
        raise SystemExit("no fort found")
    return "".join(out) + text[last:]


NAME_TEXT = 'text = "[InteractionTarget.GetTownRightsType.GetNameWithNoTooltip]"'


def after_name(text: str) -> int:
    """Offset just past the `text_single` holding the right's name."""
    at = text.index(NAME_TEXT)
    depth = 1
    for match in re.finditer(r"[{}]", text[at:]):
        depth += 1 if match.group(0) == "{" else -1
        if depth == 0:
            return at + match.end()
    raise SystemExit("the name's text_single never closes")


def card(beta: str, qol: str) -> str:
    """The beta's card with QoL's templates on top and its marker row after the name."""
    head = re.search(r"^types TownRightsTypes", qol, re.M).start()
    templates = qol[:head]
    row_start = after_name(qol)
    # QoL's row runs to the `}` that closes the hbox the name sits in.
    depth, row_end = 0, None
    for match in re.finditer(r"[{}]", qol[row_start:]):
        depth += 1 if match.group(0) == "{" else -1
        if depth < 0:
            row_end = row_start + match.start()
            break
    row = qol[row_start:row_end].rstrip() + "\n"
    if "urqol" not in row:
        raise SystemExit("QoL's marker row is not where its header says")
    templates = templates.replace(
        "BASED ON GAME VERSION 1.3.11.",
        "qol_beta: REBUILT on the 2026-10-01 beta's card by tools/port_from_qol.py.")
    at = after_name(beta)
    return templates + beta[:at] + row + beta[at:]


def metadata() -> str:
    base = json.loads(read(SRC / ".metadata/metadata.json"))
    version = base.get("version", "unknown")
    base["name"] = "Quality of Life by Buddy (beta)"
    base["id"] = "bag.qol_beta"
    base["version"] = f"{version}+beta{REVISION}"
    base["supported_game_version"] = "1.*"
    base["short_description"] = (
        f"Quality of Life by Buddy {version} fitted to the 2026-10-01 beta: no border "
        "textures or shader, forts and the town rights card taken from the beta. "
        "Load this INSTEAD of Quality of Life by Buddy, never alongside it.")
    return json.dumps(base, indent=4, ensure_ascii=False) + "\n"


def main() -> int:
    for name in ("in_game", "main_menu", "loading_screen", ".metadata"):
        if (MOD / name).exists():
            shutil.rmtree(MOD / name)
    copied = 0
    for name in ("in_game", "main_menu", "loading_screen"):
        if (SRC / name).exists():
            shutil.copytree(SRC / name, MOD / name)
    for path in DROPPED:
        target = MOD / path
        if not target.exists():
            raise SystemExit(f"{path}: QoL no longer ships it — re-read what it replaces")
        shutil.rmtree(target) if target.is_dir() else target.unlink()
    for path in FORTS:
        (MOD / path).write_text("﻿" + fort(read(refs.GAME / path)), encoding="utf-8")
    (MOD / CARD).write_text(
        "﻿" + card(read(refs.GAME / CARD), read(SRC / CARD)), encoding="utf-8")
    copied = sum(1 for p in MOD.rglob("*") if p.is_file() and "tools" not in p.parts)
    (MOD / ".metadata").mkdir(parents=True, exist_ok=True)
    (MOD / ".metadata/metadata.json").write_text("﻿" + metadata(), encoding="utf-8")
    shutil.copy2(SRC / ".metadata/thumbnail.png", MOD / ".metadata/thumbnail.png")
    print("qol_beta: %d files from %s, borders dropped, forts and card rebuilt on the beta"
          % (copied, SRC.name))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
