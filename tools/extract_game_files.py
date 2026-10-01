#!/usr/bin/env python3
"""Pull the game files this repository needs out of an EU5 install.

`reference/game/` deliberately holds only part of EU5 — the parts the mods here
reason about. When a task needs more, the fix is to copy the missing
directories in, and doing that by hand means hunting through a hundred folders
and getting one of them wrong. This does it in one command, preserving the
layout `reference/game/` already uses, so the result can be dropped straight on
top of it.

    python3 tools/extract_game_files.py
    python3 tools/extract_game_files.py --game "D:/Steam/steamapps/common/Europa Universalis V"
    python3 tools/extract_game_files.py --out /somewhere/else

There is a PowerShell twin, `tools/extract_game_files.ps1`, for the machine that
has the game on it. The two do the same thing; use whichever runs.

Without `--game` it looks in the usual Steam locations for this platform.
Without `--out` it writes straight into this repository's `reference/game/`,
which is where the files are wanted — so the next step is `git status`, not a
copy. Existing files are overwritten with the newer copy from the install, which
is the point of a refresh, and `git` is the undo.

**After a patch, `--prune`.** Without it nothing is deleted, so a file the game
dropped stays here looking alive. With it, `reference/game/` (and the Jomini and
Clausewitz layers next to it) becomes a mirror of what it holds from the
install: a file whose original is gone from the install goes too. `docs/` and
`version.json` are not from the install and are never touched. `mods.bat` → 9
runs it this way.

Two more things come along on every run, because a patch is when they matter:

- **every game file a mod replaces whole.** A mod that ships a file at the same
  path as the game's replaces all of it, so when the game changes that file the
  mod brings the old one back without a word — the commonest way a mod breaks
  on an update. Every such file, in any folder, is copied, and the ones that
  moved are listed with the mods that carry them. The mods looked at are
  `reference/mods/`, `reference/playset/`, `mods/` and any `--mods-from`.
- **the build it was taken from**, into `reference/game/version.json`: the
  Steam build and its date, and the game's own version where the install
  states one. `python3 tools/refs.py --game` reads it back.

What it takes, and why, is the manifest below. Every entry names the tool that
wants it, so an entry with no reason left can be dropped. On top of the
manifest it sweeps `in_game/common/` for any file mentioning
`monthly_towards_`, which is how a directory that Paradox renames still comes
along — the sweep does not care what the folder is called.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path

# The list of directories lives in a file both this and the PowerShell twin
# read, so adding one adds it to both.
MANIFEST_FILE = Path(__file__).resolve().parent / "game_files_manifest.txt"


def manifest() -> dict[str, str]:
    """Directory under the game root -> what needs it."""
    wanted: dict[str, str] = {}
    # **`utf-8-sig`, and a second guard after the split.** Read as plain
    # `utf-8` the first line keeps its BOM, so `lstrip().startswith("#")` is
    # false for the file's own header and it became an entry with an empty path
    # -- printed on 2026-09-03 at the top of "not in this install" as a blank
    # name and the header's own words as its reason. A path that is empty after
    # the split is a comment however it got here.
    for line in MANIFEST_FILE.read_text(encoding="utf-8-sig").splitlines():
        path, _, reason = line.partition("#")
        if not path.strip():
            continue
        wanted[path.strip()] = reason.strip()
    return wanted


# Any .txt under the whole install mentioning this comes along, whatever folder
# it is in. The sweep used to cover `in_game/common/` alone, which is where a
# mod's `common/` lives — but the game puts some of its own data elsewhere
# (`loading_screen/common/defines/` is the known case), and `static_modifiers`
# turned out to be one of those: 298 of the societal value pushes, absent from
# the first extraction and missed by a sweep that never left `in_game/`.
SWEEP_MARKER = "monthly_towards_"

# Where the game usually is, per platform. First one that exists wins.
CANDIDATES = {
    "win32": [
        r"C:\Program Files (x86)\Steam\steamapps\common\Europa Universalis V",
        r"C:\Program Files\Steam\steamapps\common\Europa Universalis V",
        r"D:\Steam\steamapps\common\Europa Universalis V",
        r"D:\SteamLibrary\steamapps\common\Europa Universalis V",
        r"E:\SteamLibrary\steamapps\common\Europa Universalis V",
    ],
    "darwin": [
        "~/Library/Application Support/Steam/steamapps/common/Europa Universalis V",
    ],
    "linux": [
        "~/.steam/steam/steamapps/common/Europa Universalis V",
        "~/.local/share/Steam/steamapps/common/Europa Universalis V",
    ],
}

# Where under an install the mounts may sit. Tried in order, first hit wins.
INSIDE = ("", "game", "game/game")

# **What proves a folder is the one.** `in_game/` alone does not: on 2026-09-03
# it matched `…/Europa Universalis V/game`, and not one manifest entry was under
# it -- 0 files copied, every entry reported missing, and nothing in the output
# said what the folder actually held. A mount root has script data in it, so the
# landmark is a directory the repository already carries a copy of.
LANDMARKS = ("in_game/common/goods", "in_game/common/production_methods",
             "in_game/common/building_types")


def looks_like_root(path: Path) -> bool:
    return any((path / mark).is_dir() for mark in LANDMARKS)


def show_tree(path: Path, depth: int = 2, indent: str = "    ") -> None:
    """What is actually there, so a failure can be read rather than guessed at."""
    if not path.is_dir():
        print("%s%s — not a directory" % (indent, path), file=sys.stderr)
        return
    try:
        entries = sorted(path.iterdir())
    except OSError as problem:
        print("%s%s — %s" % (indent, path, problem), file=sys.stderr)
        return
    for entry in entries[:40]:
        mark = "/" if entry.is_dir() else ""
        print("%s%s%s" % (indent, entry.name, mark), file=sys.stderr)
        if entry.is_dir() and depth > 1:
            show_tree(entry, depth - 1, indent + "    ")
    if len(entries) > 40:
        print("%s… and %d more" % (indent, len(entries) - 40), file=sys.stderr)


def find_game(given: str | None) -> Path:
    """The folder the mounts sit in, or a failure that says what was there instead."""
    tried: list[Path] = []
    roots = [Path(given).expanduser()] if given else [
        Path(p).expanduser() for p in CANDIDATES.get(sys.platform, CANDIDATES["linux"])]
    fallback: Path | None = None
    for root in roots:
        for inside in INSIDE:
            candidate = root / inside if inside else root
            tried.append(candidate)
            if looks_like_root(candidate):
                return candidate
            if fallback is None and (candidate / "in_game").is_dir():
                fallback = candidate
    print("no EU5 script data found. A folder counts as the root when one of",
          file=sys.stderr)
    for mark in LANDMARKS:
        print("  %s" % mark, file=sys.stderr)
    print("is a directory inside it. Looked in:", file=sys.stderr)
    for path in tried:
        print("  %-70s %s" % (path, "exists" if path.is_dir() else "no"),
              file=sys.stderr)
    if fallback is not None:
        print("\n`%s` has an `in_game/` but none of the landmarks. What is in it:"
              % fallback, file=sys.stderr)
        show_tree(fallback)
    else:
        for root in roots:
            if root.is_dir():
                print("\n`%s` exists. What is in it:" % root, file=sys.stderr)
                show_tree(root, depth=1)
                break
    print("\nPaste that back, or pass the folder explicitly:\n"
          "  python3 tools/extract_game_files.py --game \"<path>\"",
          file=sys.stderr)
    raise SystemExit(2)


def copy_tree(source: Path, target: Path,
              states: dict[Path, str] | None = None) -> tuple[int, int, int, int]:
    """Copy source over target, keeping layout. Returns (files, bytes, new, changed).

    `states`, when given, gets each destination's "new", "changed" or "same".

    **`changed` is the number that matters and it was not reported.** On
    2026-09-03 the extraction said «1098 files, 13.2 MB» and GitHub Desktop then
    said there was nothing to commit, which read like the commit failing. It had
    not: every one of those files was already in the repository, byte for byte.
    A copy is not a change, and a tool that counts copies cannot tell the two
    apart for him.
    """
    files = size = new = changed = 0
    for path in sorted(source.rglob("*")):
        if not path.is_file():
            continue
        destination = target / path.relative_to(source)
        state = copy_file(path, destination)
        if states is not None:
            states[destination] = state
        files += 1
        size += path.stat().st_size
        new += state == "new"
        changed += state == "changed"
    return files, size, new, changed


def copy_file(path: Path, destination: Path) -> str:
    """Copy one file; say whether it was "new", "changed" or "same"."""
    before = destination.read_bytes() if destination.is_file() else None
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, destination)
    if before is None:
        return "new"
    return "same" if before == path.read_bytes() else "changed"


def elsewhere(game: Path, relative: str) -> Path | None:
    """The directory `relative` names, wherever in the install it actually is.

    Paradox moves a folder between mounts — `static_modifiers` is not under
    `in_game/` at all — so a manifest entry that misses at its written path gets
    one search by name before it is called missing.
    """
    # The last two names, not one: `main_menu/gui` searched for as `gui` alone
    # would land on `in_game/gui`, a folder that is already copied.
    tail = relative.split("/")[-2:]
    for candidate in sorted(game.rglob(tail[-1])):
        if candidate.is_dir() and list(candidate.parts[-len(tail):]) == tail:
            return candidate
    return None


def sweep(game: Path, out: Path, already: set[Path]) -> list[tuple[str, int]]:
    """Every .txt in the install that mentions the marker, folder be damned."""
    root = game
    found: dict[str, int] = {}
    for path in sorted(root.rglob("*.txt")):
        if not path.is_file() or path in already:
            continue
        try:
            text = path.read_text(encoding="utf-8-sig", errors="replace")
        except OSError:
            continue
        if SWEEP_MARKER not in text:
            continue
        relative = path.relative_to(game)
        destination = out / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
        folder = str(relative.parent).replace(os.sep, "/")
        found[folder] = found.get(folder, 0) + 1
    return sorted(found.items())


def human(size: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return "%.1f %s" % (size, unit) if unit != "B" else "%d B" % size
        size /= 1024.0
    return "%d B" % size


# ------------------------------------------------- what a patch needs on top

REPO = Path(__file__).resolve().parent.parent
APP_ID = "3450310"                    # EU5 on Steam; tools/workshop.py has the same

# Not copies of anything in the install, so a prune leaves them alone: the
# engine's own API dumps come from the game's Documents folder, and the build
# record is written here.
NOT_FROM_INSTALL = {"docs", "version.json"}

# A prune that would take more than this share of a tree is refused: that is
# not a patch, that is the wrong folder passed as the game.
PRUNE_LIMIT = 0.3

# Text a mod can replace a game file with. Shaders and `.settings` are here on
# purpose: the performance mods replace exactly those.
TEXT_SUFFIXES = {".txt", ".gui", ".yml", ".settings", ".shader", ".fxh",
                 ".csv", ".asset", ".lua"}

# The engine layers under the game's own files. `reference/jomini/` held two
# defines files taken by hand; the base GUI types live here too, which is why
# `button_regular` read as declared nowhere. Text only, and only these folders.
LAYERS = ("jomini", "clausewitz")
LAYER_PARTS = {"gui", "common", "data_binding", "localization"}
LAYER_SUFFIXES = {".gui", ".txt", ".yml", ".settings"}
LANGUAGES = {"english", "russian"}


def layer_dir(game: Path, name: str) -> Path | None:
    """`jomini/` or `clausewitz/`, beside the game's mounts or one level up."""
    for base in (game, game.parent, game.parent.parent):
        candidate = base / name
        if candidate.is_dir():
            return candidate
    return None


def layer_files(layer: Path) -> list[Path]:
    wanted = []
    for path in sorted(layer.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in LAYER_SUFFIXES:
            continue
        parts = [part.lower() for part in path.relative_to(layer).parts[:-1]]
        if not LAYER_PARTS.intersection(parts):
            continue
        if "localization" in parts:
            index = parts.index("localization")
            if index + 1 < len(parts) and parts[index + 1] not in LANGUAGES:
                continue
        wanted.append(path)
    return wanted


def mod_roots(extra: list[Path]) -> list[tuple[str, Path]]:
    """(name, folder) of every mod to look at, each mod once.

    A workshop folder is named by its number alone, the copies here by number
    and name, so the number is what says two are the same mod; the copies here
    come first and give the readable name.
    """
    seen: dict[str, tuple[str, Path]] = {}
    for base in [REPO / "reference/mods", REPO / "reference/playset", REPO / "mods", *extra]:
        if not base.is_dir():
            continue
        for folder in sorted(base.iterdir()):
            if not folder.is_dir():
                continue
            head = folder.name.split("_", 1)[0]
            key = head if head.isdigit() else folder.name
            seen.setdefault(key, (folder.name, folder))
    return list(seen.values())


def replaced_by_mods(game: Path, extra: list[Path]) -> dict[str, list[str]]:
    """Game file (relative path) -> the mods that ship a file at that path."""
    found: dict[str, list[str]] = {}
    for name, root in mod_roots(extra):
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            relative = path.relative_to(root)
            if relative.parts[0].startswith("."):
                continue
            if (game / relative).is_file():
                mods = found.setdefault(relative.as_posix(), [])
                if name not in mods:
                    mods.append(name)
    return found


def prune(out: Path, source: Path) -> tuple[list[str], bool]:
    """Delete what under `out` is gone from `source`. Returns (gone, done)."""
    total = 0
    gone: list[Path] = []
    for path in sorted(out.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(out)
        if relative.parts[0] in NOT_FROM_INSTALL:
            continue
        total += 1
        if not (source / relative).exists():
            gone.append(path)
    names = [str(p.relative_to(out)).replace(os.sep, "/") for p in gone]
    if len(gone) > max(50, total * PRUNE_LIMIT):
        return names, False
    for path in gone:
        path.unlink()
    for folder in sorted((p for p in out.rglob("*") if p.is_dir()), reverse=True):
        if not any(folder.iterdir()):
            folder.rmdir()
    return names, True


def build_of(game: Path) -> dict:
    """What Steam and the install say about the build: `version.json`'s content."""
    found: dict = {}
    install = None
    for parent in [game, *game.parents]:
        if (parent.parent.name.lower() == "common"
                and parent.parent.parent.name.lower() == "steamapps"):
            install = parent
            acf = parent.parent.parent / ("appmanifest_%s.acf" % APP_ID)
            if acf.is_file():
                text = acf.read_text(encoding="utf-8", errors="replace")
                for key, name in (("buildid", "steam_build"), ("LastUpdated", "steam_updated")):
                    match = re.search(r'"%s"\s+"([^"]*)"' % key, text)
                    if match:
                        found[name] = match.group(1)
            break
    if "steam_updated" in found and found["steam_updated"].isdigit():
        found["steam_updated"] = time.strftime(
            "%Y-%m-%d %H:%M", time.localtime(int(found["steam_updated"])))
    for root in [p for p in (install, game, game.parent) if p is not None]:
        for name in ("launcher/launcher-settings.json", "launcher-settings.json"):
            settings = root / name
            if settings.is_file():
                try:
                    data = json.loads(settings.read_text(encoding="utf-8-sig"))
                except (OSError, ValueError):
                    continue
                for key in ("version", "rawVersion"):
                    if data.get(key):
                        found["game_" + key.lower()] = str(data[key])
                break
        if any(k.startswith("game_") for k in found):
            break
    return found


def write_build(out: Path, build: dict) -> None:
    """Merge into `version.json`, keeping what other steps wrote there."""
    target = out / "version.json"
    data: dict = {}
    if target.is_file():
        try:
            data = json.loads(target.read_text(encoding="utf-8"))
        except ValueError:
            data = {}
    for key in ("steam_build", "steam_updated", "game_version", "game_rawversion"):
        data.pop(key, None)
    data.update(build)
    data["files_taken"] = time.strftime("%Y-%m-%d %H:%M")
    target.write_text(json.dumps(data, indent=1, ensure_ascii=False, sort_keys=True) + "\n",
                      encoding="utf-8")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Copy the game directories this repository needs into one "
                    "folder shaped like reference/game/.")
    parser.add_argument("--game", help="the Europa Universalis V install folder")
    parser.add_argument("--out", type=Path,
                        help="where to write it (default: this repository's "
                             "reference/game/)")
    parser.add_argument("--no-sweep", action="store_true",
                        help="skip the content sweep for renamed folders")
    parser.add_argument("--prune", action="store_true",
                        help="after a patch: delete what the install no longer has")
    parser.add_argument("--mods-from", action="append", type=Path, default=[],
                        metavar="DIR",
                        help="one more folder of mods to check for replaced game "
                             "files, such as the Steam workshop folder")
    args = parser.parse_args(argv[1:])

    game = find_game(args.game)
    out = (args.out.expanduser() if args.out else REPO / "reference/game").resolve()
    build = build_of(game)
    print("игра:   %s" % game)
    if build:
        print("сборка: %s" % ", ".join(
            "%s %s" % (label, build[key]) for key, label in (
                ("game_version", "версия"), ("game_rawversion", "полная"),
                ("steam_build", "Steam build"), ("steam_updated", "обновлена"))
            if key in build))
    print("куда:   %s" % out)
    print()

    total_files = total_size = total_new = total_changed = 0
    missing: list[str] = []
    copied: set[Path] = set()
    states: dict[Path, str] = {}
    for relative, reason in manifest().items():
        source = game / relative
        found_at = relative
        if not source.is_dir():
            moved = elsewhere(game, relative)
            if moved is None:
                missing.append("%-46s %s" % (relative, reason))
                continue
            source = moved
            found_at = str(moved.relative_to(game)).replace(os.sep, "/")
        files, size, new, changed = copy_tree(source, out / found_at, states)
        copied.update(p for p in source.rglob("*") if p.is_file())
        total_files += files
        total_size += size
        total_new += new
        total_changed += changed
        note = "" if found_at == relative else "   <- нашлось в %s" % found_at
        if new or changed:
            note = ("   новых %d, изменённых %d" % (new, changed)) + note
        print("  %-46s %5d файлов %9s%s" % (relative, files, human(size), note))

    if not args.no_sweep:
        extra = sweep(game, out, copied)
        if extra:
            print("\nещё, по содержимому — файлы с %r вне списка выше:" % SWEEP_MARKER)
            for folder, count in extra:
                print("  %-46s %5d" % (folder, count))
                total_files += count

    # Every game file a mod replaces whole, wherever it lives.
    replaced = replaced_by_mods(game, args.mods_from)
    moved: list[tuple[str, str]] = []
    extra_new = extra_changed = 0
    for relative in sorted(replaced):
        destination = out / relative
        state = states.get(destination)
        if state is None:
            # Outside the folders above: copied here and nowhere else.
            state = copy_file(game / relative, destination)
            extra_new += state == "new"
            extra_changed += state == "changed"
        if state in ("new", "changed"):
            moved.append((relative, state))
    print("\nфайлы игры, которые моды заменяют целиком: %d" % len(replaced))

    layers: list[tuple[str, Path]] = []
    for name in LAYERS:
        layer = layer_dir(game, name)
        if layer is None:
            print("  слой %-10s в установке не найден" % name)
            continue
        layers.append((name, layer))
        target = REPO / "reference" / name if not args.out else out.parent / name
        new = changed = 0
        files = layer_files(layer)
        for path in files:
            state = copy_file(path, target / path.relative_to(layer))
            new += state == "new"
            changed += state == "changed"
        total_new += new
        total_changed += changed
        print("  слой %-10s %5d файлов%s" % (name, len(files),
              "   новых %d, изменённых %d" % (new, changed) if new or changed else ""))

    removed: list[str] = []
    if args.prune:
        trees = [(out, game)] + [((REPO / "reference" / n) if not args.out
                                  else out.parent / n, layer) for n, layer in layers]
        for target, source in trees:
            if not target.is_dir():
                continue
            gone, done = prune(target, source)
            if not done:
                print("\n!! %s: в установке нет %d файлов отсюда — это больше трети."
                      % (target.name, len(gone)))
                print("   Похоже, указана не та папка игры. Ничего не удалено.")
                continue
            removed += ["%s/%s" % (target.name, g) for g in gone]
        if removed:
            print("\nудалено, потому что из игры их убрали: %d" % len(removed))
            for line in removed[:40]:
                print("  " + line)
            if len(removed) > 40:
                print("  … и ещё %d" % (len(removed) - 40))

    if missing:
        print("\nв этой установке нет, пропущено:")
        for line in missing:
            print("  %s" % line)
        print("\nПапка, которую Paradox переименовали, сама по себе не беда — поиск по "
              "содержимому выше ловит нужные файлы.")

    if moved:
        print("\nМоды заменяют эти файлы игры целиком, а файлы новые или изменились:")
        for relative, state in moved:
            print("  %-8s %s" % ("новый" if state == "new" else "изменён", relative))
            print("           %s" % ", ".join(replaced[relative]))

    total_new += extra_new
    total_changed += extra_changed
    write_build(out, build)
    print("\n%d файлов, %s: новых %d, изменённых %d, удалённых %d."
          % (total_files, human(total_size), total_new, total_changed, len(removed)))
    # **No git here.** He commits through GitHub Desktop and asked that nothing
    # in this repository's tooling write the working tree behind him.
    if total_new or total_changed or removed:
        print("\nЭто в reference/. Закоммить в GitHub Desktop — пока не закоммичено и "
              "не запушено, сессия ничего из этого не видит.")
    else:
        print("\nНичего не отличается от того, что уже в репозитории, коммитить нечего. "
              "Это ответ, а не сбой.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
