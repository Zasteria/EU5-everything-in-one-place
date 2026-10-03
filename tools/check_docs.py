#!/usr/bin/env python3
"""Check that the documents still describe the repository that exists.

Everything here is written down so a session with no memory can trust it. That
only works while it is true, and the ways it stops being true are dull and
repeatable: a mod is deleted and four documents still link to it, a folder in
`reference/` is renamed and the path in a code block is now wrong, a mod updates
and a version typed into prose quietly becomes a lie.

    python3 tools/check_docs.py

Each rule below exists because the mistake was actually made in this repository.
Two of them are hard failures — a path that does not exist, and a reference
folder named literally. Versions written in prose are only listed, because a
version is a lie when it claims what is in the tree and a fact when it records
what something was checked against, and no regular expression can tell those
apart.

A line carrying `check-docs: ignore` is skipped, for the case where a document
deliberately talks about something that is gone.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import kb  # noqa: E402
import refs  # noqa: E402

SKIP_DIRS = {".git", "reference", "__pycache__"}

# What a document may cost to put in a context window, by the estimate in
# `tools/kb.py`. The first pattern that matches a document owns it; anything
# unmatched — `docs/archive/`, a mod's README — is unbudgeted, because nothing
# routes a session into it and `kb.py` hands out its sections one at a time.
#
# This rule exists because the documents grew, quietly and each time for a good
# reason, until reading the ones a session was told to read cost about forty
# thousand tokens — a third of an hour's budget spent before any work, and paid
# again on every turn after, because the context is resent each time.
#
# A document over budget is **not** fixed by deleting what it knows. It is
# split, and the finished half moves to `docs/archive/`, which `kb.py` still
# searches and no document routes anybody into.
BUDGETS = (
    ("CLAUDE.md", 1800),            # loaded automatically, every session, every turn
    ("mods/*/CLAUDE.md", 1100),     # one is read whenever a task names that mod
    ("docs/STATUS.md", 1000),
    ("docs/SETTLED.md", 1600),      # the one document worth reading in full
    ("docs/NEXT_SESSION.md", 1900),
    ("docs/investigations/*.md", 4000),
    ("docs/pitfalls/*.md", 6000),
    ("docs/TESTLOG.md", 5000),      # grows with every run; archive when it trips
    ("docs/research/*.md", 8000),
    ("docs/*.md", 4000),
)

# A repository path written in a document: a link target, or a bare path in
# backticks or a code block. No spaces — what follows a path is an argument or a
# description of it, and neither is part of the path.
PATHS = re.compile(r"(?:\]\(|`|^|\s)((?:mods|docs|tools|reference)/[\w./-]*[\w/])")
IGNORE = "check-docs: ignore"
# Mods and tools retired on 2026-10-03, whose files live on only in git history
# (`docs/archive/retired_mods.md` says where). A document naming one of them is
# talking about what was, not about the tree, so the path is not checked — and
# nothing under `docs/archive/` is, for the same reason.
RETIRED = ("mods/goods_target", "mods/marker_throttle", "mods/widget_probe",
           "mods/where_to_produce", "mods/qol_beta", "mods/auto_build_ru",
           "tools/diag.py", "tools/eu5data.py", "tools/sync_workshop.ps1",
           "tools/extract_game_files.ps1",
           # glorpui_hints went back to its Steam build (8e028184), tools and all.
           "mods/glorpui_hints/tools")
# A version number sitting next to a mod's name, which `tools/refs.py` owns.
VERSIONS = re.compile(
    r"(?:CMF|Community Mod Framework|Construction Manager|Glorp UI|"
    r"National Destinies|Advanced Auto Build|community_mod_framework|glorp\.ui)"
    r"[^\n.]{0,30}?\b(\d+\.\d+\.\d+[\w.]*)"
)
# A folder inside reference/mods/ named literally. The name depends on how the
# owner's upload happened and has changed before; ask refs.py instead.
REFERENCE_FOLDER = re.compile(r"reference/mods/(?!\*)[\w.'-]+")


def documents() -> list[Path]:
    found = []
    for path in refs.REPO.rglob("*.md"):
        if not any(part in SKIP_DIRS for part in path.relative_to(refs.REPO).parts):
            found.append(path)
    return sorted(found)


def scripts() -> list[Path]:
    found = []
    for path in refs.REPO.rglob("*.py"):
        if not any(part in SKIP_DIRS for part in path.relative_to(refs.REPO).parts):
            found.append(path)
    return sorted(found)


def check_path(text: str, document: Path) -> bool:
    """Does this path exist — from the repository root, or from the document?

    A mod's own README writes `tools/generate_ru.py` meaning its own tools
    folder, which is right there on the page and wrong from the root.
    """
    if "*" in text or "<" in text:
        # `mods/*/tools/` and friends describe a shape rather than name a file.
        return True
    target = text.rstrip("/")
    if target.startswith(RETIRED) or "docs/archive" in document.as_posix():
        return True
    return (refs.REPO / target).exists() or (document.parent / target).exists()


def budget(path: Path) -> int | None:
    where = path.relative_to(refs.REPO)
    for pattern, allowance in BUDGETS:
        if where.match(pattern) and where.as_posix().count("/") == pattern.count("/"):
            return allowance
    return None


def check_budgets() -> list[str]:
    over: list[str] = []
    for path in documents():
        allowance = budget(path)
        if allowance is None:
            continue
        cost = kb.estimate(path.read_text(encoding="utf-8-sig"))
        if cost > allowance:
            over.append(
                "%s: ~%d tokens, budget %d — split it, and move the finished half"
                " to docs/archive/ (it stays searchable with tools/kb.py)"
                % (path.relative_to(refs.REPO), cost, allowance))
    return over


def main(argv: list[str]) -> int:
    problems: list[str] = check_budgets()
    notes: list[str] = []

    for path in documents():
        where = path.relative_to(refs.REPO)
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if IGNORE in line:
                continue
            for match in PATHS.finditer(line):
                target = match.group(1)
                if not check_path(target, path):
                    problems.append(f"{where}:{number}: no such path: {target}")
            for match in VERSIONS.finditer(line):
                notes.append(
                    "%s:%d: a version in prose (%s) — fine as a record of what was"
                    " checked, wrong as a claim about the tree"
                    % (where, number, match.group(1)))
            for match in REFERENCE_FOLDER.finditer(line):
                problems.append(
                    "%s:%d: names a folder inside reference/mods/ (%s) — the name"
                    " depends on the upload; ask refs.known()"
                    % (where, number, match.group(0)))

    # The same rule for the tools, where a hardcoded reference folder is worse:
    # it breaks silently rather than reading wrong.
    for path in scripts():
        if path.name == "check_docs.py":
            continue
        where = path.relative_to(refs.REPO)
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith("#") or IGNORE in line:
                continue
            for match in REFERENCE_FOLDER.finditer(line):
                problems.append(
                    "%s:%d: hardcodes %s — use refs.known(); a renamed folder"
                    " fails silently" % (where, number, match.group(0)))

    for problem in problems:
        print(problem, file=sys.stderr)
    if notes and "--quiet" not in argv:
        print("worth a look:")
        for note in notes:
            print("  %s" % note)
    print("%d documents, %d scripts: %s"
          % (len(documents()), len(scripts()),
             "%d problems" % len(problems) if problems else "clean"))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
