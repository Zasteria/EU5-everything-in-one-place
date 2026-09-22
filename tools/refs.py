#!/usr/bin/env python3
"""Where the reference tree is — resolved by mod id, not by folder name.

`reference/` is refreshed by hand, whenever the owner feels like it, and the
folder names come along for the ride: the same mod arrives as
`community_mod_framework` from a folder copy and as
`3692202776_community_mod_framework` from a workshop copy. A tool that hardcodes
either one breaks on the next upload — silently, because a missing folder reads
as "nothing to translate" rather than as an error.

So nothing hardcodes a folder name. A mod is asked for by the `id` in its
`.metadata/metadata.json`, which is the mod's real identity and does not change
when the folder is renamed:

    import refs
    cmf = refs.mod("community_mod_framework")

A mod whose `.metadata/` did not come along is matched on its folder name
instead, which is why `mod()` takes more than one hint.

Run it for what is currently in the tree:

    python3 tools/refs.py            # the inventory, as a table
    python3 tools/refs.py --write    # the same, into reference/INVENTORY.md
    python3 tools/refs.py --path community_mod_framework
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
REFERENCE = REPO / "reference"
MODS = REFERENCE / "mods"

# The rest of the owner's subscribed mods: copied text-only, for looking at and
# for measuring, not for building against. Nothing compiles from here, and
# `mods()` deliberately does not see it — a tool that asks for "the reference
# mods" means the five in `mods/`.
PLAYSET = REFERENCE / "playset"

GAME = REFERENCE / "game"
GAME_COMMON = GAME / "in_game/common"
GAME_GUI = GAME / "in_game/gui"
GAME_LOCALIZATION = GAME / "main_menu/localization"

INVENTORY = REFERENCE / "INVENTORY.md"

# The mods this repository's tools ask for, and the hints that find each one.
# First hint is the metadata id where there is one; the rest match the folder.
KNOWN = {
    "cmf": ("community_mod_framework",),
    "construction_manager": ("romaimperator.construction_manager", "construction manager"),
    "glorp_ui": ("glorp.ui", "glorp"),
    "national_destinies": ("trin.national_destinies", "national destinies"),
    "national_mission_trees": ("national_mission_trees", "mission trees"),
}


@dataclass(frozen=True)
class Mod:
    """One folder under `reference/mods/`, and whatever it says about itself."""

    path: Path
    id: str | None
    name: str | None
    version: str | None
    game_version: str | None

    @property
    def folder(self) -> str:
        return self.path.name

    def matches(self, hint: str) -> bool:
        want = _slug(hint)
        if self.id and want in _slug(self.id):
            return True
        return all(token in _slug(self.folder) for token in want.split())


def _slug(text: str) -> str:
    return "".join(c if c.isalnum() else " " for c in text.lower()).strip()


def _metadata(folder: Path) -> dict:
    """Read a mod's metadata, from `.metadata/` or wherever it ended up.

    A mod uploaded through the GitHub web form used to arrive with the leading
    dot eaten, so `metadata/` is accepted as well. Missing metadata is not an
    error: Advanced Auto Build has none in this tree.
    """
    for candidate in (folder / ".metadata/metadata.json", folder / "metadata/metadata.json"):
        if candidate.is_file():
            try:
                return json.loads(candidate.read_text(encoding="utf-8-sig"))
            except json.JSONDecodeError as exc:
                raise SystemExit(f"{candidate}: {exc}") from exc
    return {}


def mod_commons() -> list[Path]:
    """`in_game/common` каждого мода из `reference/mods`, в порядке имён папок.

    **Это и есть «сканирование других модов».** Перечислить типы зданий из
    скрипта игры нельзя ничем, поэтому сканирует генератор: он читает те же
    папки, что читает игра, и кладёт их поверх игровых. Порядок между модами --
    имя папки; настоящий порядок загрузки задаёт плейсет и знать его тут нечем,
    но два мода, объявляющих одно здание, -- случай, которого в этом дереве нет.
    """
    if not MODS.is_dir():
        return []
    return [folder / "in_game/common" for folder in sorted(MODS.iterdir())
            if (folder / "in_game/common").is_dir()]


def mod_sources() -> list[tuple[str, str, Path]]:
    """Папка, человеческое имя и `in_game/common` каждого мода дерева.

    Имя берётся из его же `.metadata/metadata.json`, чтобы в настройках стояло
    то, что игрок видит в лаунчере, а не имя папки Мастерской.
    """
    out: list[tuple[str, str, Path]] = []
    for folder in sorted(MODS.iterdir()) if MODS.is_dir() else []:
        common = folder / "in_game/common"
        if not common.is_dir():
            continue
        name = folder.name
        meta = folder / ".metadata/metadata.json"
        if meta.is_file():
            try:
                name = json.loads(meta.read_text(encoding="utf-8-sig")).get("name") or name
            except Exception:
                pass
        out.append((folder.name, name, common))
    return out


def mods() -> list[Mod]:
    """Every mod folder currently under `reference/mods/`, sorted by folder."""
    if not MODS.is_dir():
        raise SystemExit(f"no reference tree at {MODS}")
    found = []
    for folder in sorted(MODS.iterdir()):
        if not folder.is_dir():
            continue
        data = _metadata(folder)
        found.append(Mod(
            path=folder,
            id=data.get("id"),
            name=data.get("name"),
            version=str(data.get("version")) if data.get("version") else None,
            game_version=data.get("supported_game_version"),
        ))
    return found


def playset() -> list[Mod]:
    """Every mod folder under `reference/playset/`, sorted by folder.

    Empty when the tree has none, rather than an error: the playset copies are
    optional, and every tool that reads them has to work without them.
    """
    if not PLAYSET.is_dir():
        return []
    found = []
    for folder in sorted(PLAYSET.iterdir()):
        if not folder.is_dir():
            continue
        data = _metadata(folder)
        found.append(Mod(
            path=folder,
            id=data.get("id"),
            name=data.get("name"),
            version=str(data.get("version")) if data.get("version") else None,
            game_version=data.get("supported_game_version"),
        ))
    return found


def mod(*hints: str) -> Path:
    """The folder of the mod named by any of `hints`, matched id first.

    Fails naming what is actually in the tree, because the likely cause is a
    refresh that renamed the folder or dropped the mod, and the folder listing
    is the answer either way.
    """
    known = mods()
    for hint in hints:
        matched = [m for m in known if m.matches(hint)]
        if len(matched) == 1:
            return matched[0].path
        if len(matched) > 1:
            # An addon to a mod is named after it — `glorp_ui_small_fix` answers
            # to every hint `glorp_ui` does — so a folder name alone stopped
            # being enough the day one arrived. The mod's own `id` is the thing
            # that cannot be shared: if exactly one candidate declares the id
            # asked for, that is the mod, whatever the folders are called.
            exact = [m for m in matched if m.id and _slug(m.id) == _slug(hint)]
            if len(exact) == 1:
                return exact[0].path
            names = ", ".join(m.folder for m in matched)
            raise SystemExit(f"{hint!r} matches more than one mod: {names}")
    listing = "\n".join(f"  {m.folder}  ({m.id or 'no metadata'})" for m in known)
    raise SystemExit(
        "no mod in reference/mods/ matches %s. What is there:\n%s"
        % (" or ".join(repr(h) for h in hints), listing)
    )


def known(key: str) -> Path:
    """The folder of one of the mods this repository's tools depend on."""
    return mod(*KNOWN[key])


def table() -> str:
    """The inventory, as the Markdown table `reference/INVENTORY.md` holds."""
    lines = [
        "<!-- Written by tools/refs.py --write. Do not edit by hand. -->",
        "# What is in `reference/` right now",
        "",
        "Versions live here rather than in prose, so refreshing a mod needs no",
        "edit anywhere else. Re-run after any refresh:",
        "",
        "```",
        "python3 tools/refresh.py",
        "```",
        "",
        "| Folder | Mod id | Version | Game |",
        "| --- | --- | --- | --- |",
    ]
    for m in mods():
        lines.append("| `%s` | %s | %s | %s |" % (
            m.folder,
            "`%s`" % m.id if m.id else "no metadata",
            m.version or "—",
            m.game_version or "—",
        ))
    rest = playset()
    if rest:
        lines += [
            "",
            "## The rest of the playset",
            "",
            "Text only — no `gfx`, no sound, and only English and Russian",
            "localization. These are here to be read and measured, not built",
            "against: `refs.mods()` does not see them, and nothing generated",
            "compiles from them.",
            "",
            "| Folder | Mod id | Version | Mounts |",
            "| --- | --- | --- | --- |",
        ]
        for m in rest:
            mounts = sorted(p.name for p in m.path.iterdir()
                            if p.is_dir() and not p.name.startswith("."))
            lines.append("| `%s` | %s | %s | %s |" % (
                m.folder,
                "`%s`" % m.id if m.id else "no metadata",
                m.version or "—",
                ", ".join(mounts) or "—",
            ))

    game_files = sum(1 for _ in GAME.rglob("*")) if GAME.is_dir() else 0
    lines += [
        "",
        "`reference/game/` holds %d files of EU5 itself — `in_game/gui/`, the parts"
        % game_files,
        "of `in_game/common/` the mods here reason about, and the game's own",
        "localization, which is how `mods/nd_ru/tools/term.py` answers what the game",
        "calls a concept.",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    if "--path" in argv:
        index = argv.index("--path")
        if index + 1 >= len(argv):
            print(__doc__)
            return 2
        print(mod(argv[index + 1]))
        return 0

    if "--write" in argv:
        INVENTORY.write_text(table(), encoding="utf-8")
        print("wrote %s" % INVENTORY.relative_to(REPO))
        return 0

    for m in mods():
        print("%-40s %-34s %-9s %s" % (
            m.folder, m.id or "(no metadata)", m.version or "—", m.game_version or "—"))
    rest = playset()
    if rest:
        print("\nplayset/ (text only, for reading and measuring): %d mods" % len(rest))
        for m in rest:
            print("  %-40s %-34s %s" % (
                m.folder, m.id or "(no metadata)", m.version or "—"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
