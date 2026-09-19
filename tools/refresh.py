#!/usr/bin/env python3
"""The one command to run after `reference/` is refreshed.

The owner updates the game files and the workshop mods by hand, at no fixed
time and under whatever folder names the upload produced. Nothing in this
repository needs to be told about it — but the generated files do have to be
rebuilt, because they are compiled out of exactly those files, and it is worth
seeing *what* the update moved underneath the mods.

    python3 tools/refresh.py

It re-reads the inventory, runs every generator, and then reports which
generated files changed. A clean report means the update touched nothing this
repository depends on. A changed file is not a problem by itself — it is the
patch's effect, made visible, and `git diff` says what it was.

Add `--check` to leave nothing changed on disk and only report, which is what a
session should run before trusting anything a doc says about the tree.

Add `--brief` to hear from a generator only when it has something to say — a
failure, a remark it made on stderr, or a file it actually changed. That is the
shape the mod menu wants:
the full report is reassuring the first time and noise the twentieth, and it
reads as though the generators were rewriting mods that nobody touched.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import refs  # noqa: E402

# Every generator, in the order that makes the output read sensibly. Each takes
# its reference paths from `refs`, so none of them is given an argument here.
#
# **`auto_build_ru` не в списке с 2026-09-12.** Владелец убрал Advanced Auto
# Build из дерева совсем -- «он говнище и больше не пригодится», -- а генератор
# перевода читает английские ключи из копии этого мода. Сам перевод (1269
# ключей) лежит в `mods/auto_build_ru` и работает; пересобрать его нельзя, пока
# копия AAB не вернётся в `reference/mods/`.
GENERATORS = (
    ("rgo_bonus_filter", "mods/rgo_bonus_filter/tools/generate_rgo_filter.py"),
    ("goods_target", "mods/goods_target/tools/generate.py"),
    ("where_to_produce", "mods/where_to_produce/tools/generate.py"),
    ("cm_maps", "mods/cm_maps/tools/port_from_cm.py"),
    ("cm_perf", "mods/cm_perf/tools/port_from_cm.py"),
    ("nd_ru", "mods/nd_ru/tools/generate_ru.py"),
    ("ru_loc_fix", "mods/ru_loc_fix/tools/generate.py"),
    ("glorpui_hints", "mods/glorpui_hints/tools/generate.py"),
    ("glorpui_hints window", "mods/glorpui_hints/tools/generate_values_window.py"),
)


def run(script: str) -> tuple[int, str, str]:
    """The generator's exit code, what it reported, and what it warned about.

    The two streams are kept apart because `--brief` is silent about a generator
    that succeeded, and a generator that succeeded *with something to say* — a
    base mod that deleted a key, an English original that moved — must not be
    silenced along with it. Everything routine goes to stdout; anything that
    wants a human goes to stderr.
    """
    done = subprocess.run(
        [sys.executable, str(refs.REPO / script)],
        capture_output=True, text=True, cwd=refs.REPO,
    )
    return done.returncode, done.stdout.strip(), done.stderr.strip()


def changed_files() -> list[str]:
    """What git sees as different, generated files and inventory alike."""
    done = subprocess.run(
        ["git", "status", "--porcelain", "--", "mods", "reference/INVENTORY.md"],
        capture_output=True, text=True, cwd=refs.REPO,
    )
    if done.returncode != 0:
        return []
    return [line[3:] for line in done.stdout.splitlines() if line.strip()]


def main(argv: list[str]) -> int:
    check_only = "--check" in argv
    brief = "--brief" in argv
    before = set(changed_files())

    if not brief:
        print("reference/")
        for mod in refs.mods():
            print("  %-40s %-34s %s" % (mod.folder, mod.id or "(no metadata)", mod.version or "—"))

    failed = []
    warned = []
    if not brief:
        print()
    for name, script in GENERATORS:
        code, output, warning = run(script)
        if code != 0:
            failed.append(name)
        elif warning:
            warned.append(name)
        if brief and code == 0 and not warning:
            continue
        print("%s %s" % ("FAIL" if code else ("note" if warning else "ok  "), name))
        for line in (output + "\n" + warning).strip().splitlines():
            print("     %s" % line)
    if brief and not failed:
        print("ok  %d генератор(ов) отработали%s"
              % (len(GENERATORS),
                 ", %d с замечанием" % len(warned) if warned else ""))

    refs.INVENTORY.write_text(refs.table(), encoding="utf-8")

    # Two ways a mod file fails at load and nothing here would notice: a
    # trigger written with an effect's `if`, and a doubled byte order mark. Both
    # cost a run on 2026-08-31 and both are one regex, so they are checked on
    # every refresh rather than remembered.
    code, output, warning = run("tools/check_script.py")
    line = (output + "\n" + warning).strip().splitlines()
    if code != 0:
        failed.append("check_script")
    if code != 0 or not brief:
        print()
        for text in line:
            print("%s %s" % ("FAIL" if code else "    ", text))

    after = [path for path in changed_files() if path not in before]
    print()
    if after:
        print("changed by this run (%d):" % len(after))
        for path in after:
            print("  %s" % path)
        print("`git diff` for what the update did; commit it with the reference refresh.")
    else:
        print("nothing changed: the refresh touched nothing this repository compiles from.")

    if check_only and after:
        subprocess.run(["git", "checkout", "--"] + after, cwd=refs.REPO)
        print("(--check: reverted)")

    if failed:
        print()
        print("FAILED: %s" % ", ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
