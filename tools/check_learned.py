#!/usr/bin/env python3
"""Did this branch learn something general and keep it only where nobody looks?

His question, 2026-10-04: «ПРАВИЛЬНЫЕ методы и успешные способы всегда
записываются в базу или всё как пойдёт?» The answer, checked that evening, was
"not always": the `cm_dev_perf` thread wrote every run into `docs/TESTLOG.md`
and the mod's state into its `CLAUDE.md`, and four findings that any mod could
use went into the mod's notes or nowhere. A mod's notes hold its *state*: they
are rewritten as the mod moves and trimmed to their budget (that same evening,
three times), and a finding filed there is filed under a mod nobody working on
another one would think to ask about.

"Write it down next time" is not a mechanism (`docs/pitfalls/diagnosis.md`), so
this runs as the session's Stop hook (`.claude/hooks/stop-learned.sh`). When the
branch changed a mod or recorded a run, and touched none of the documents the
knowledge lives in, the turn goes back once per commit with the question.

    python3 tools/check_learned.py          what this branch changed, and the verdict
    python3 tools/check_learned.py --hook   the Stop hook: exit 2 and a question, or 0

An honest "nothing general here" is a line `Learned: nothing general` in any
commit message on the branch.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

# The checkout the command runs in (the hook enters the project first), so a
# copy of this file can check any worktree.
REPO = Path(subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True,
                           text=True).stdout.strip() or Path(__file__).resolve().parent.parent)

# Work that can teach something: a mod, a run, an investigation.
WORK = ("mods/", "docs/TESTLOG.md", "docs/investigations/")
# Where what it taught is found again: the table in CLAUDE.md, «Keeping this current».
# A checker is not on it: adding a mod to a checker's list (as this very branch
# did with check_script.py's copies) records nothing, and a new rule in one
# comes with its pitfall written down anyway.
KNOWLEDGE = ("docs/research/", "docs/pitfalls/", "docs/RESEARCH.md", "docs/PITFALLS.md",
             "docs/SETTLED.md")
WAIVER = "Learned: nothing general"


def git(*args: str) -> str:
    done = subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True)
    return done.stdout.strip() if done.returncode == 0 else ""


def branch_state() -> tuple[str, list[str], bool] | None:
    """The head, every path changed since main (committed or not), and the waiver."""
    base = git("merge-base", "HEAD", "origin/main") or git("merge-base", "HEAD", "main")
    head = git("rev-parse", "HEAD")
    if not base or not head or base == head and not git("status", "--porcelain"):
        return None
    changed = set(git("diff", "--name-only", base).splitlines())
    changed |= set(git("ls-files", "--others", "--exclude-standard").splitlines())
    waived = WAIVER in git("log", "--format=%B", f"{base}..HEAD")
    return head, sorted(p for p in changed if p), waived


def verdict() -> tuple[str, str | None]:
    """(head, the question to put) — no question when nothing is owed."""
    state = branch_state()
    if state is None:
        return "", None
    head, changed, waived = state
    work = [p for p in changed if p.startswith(WORK)]
    known = [p for p in changed if p.startswith(KNOWLEDGE)]
    if not work or known or waived:
        return head, None
    mods = sorted({p.split("/")[1] for p in work if p.startswith("mods/") and p.count("/") > 1})
    where = ", ".join(mods) if mods else "the runs in docs/TESTLOG.md"
    return head, (
        f"This branch changed {where} and wrote nothing to the knowledge base "
        "(docs/research/, docs/pitfalls/, docs/SETTLED.md). Before ending: "
        "what worked, what failed and why, and how the engine or a mod really behaves "
        "here -- would any of it serve another mod? A mod's CLAUDE.md holds that mod's "
        "state and is trimmed to budget as the mod moves. Write each such finding where CLAUDE.md's "
        "«Keeping this current» table puts it. If nothing general was learned, say so "
        f"with a line `{WAIVER}` in the next commit message.")


def main() -> int:
    head, question = verdict()
    if "--hook" not in sys.argv:
        print(question or "nothing owed: no mod work on this branch, or its findings are in the base")
        return 0
    try:
        payload = json.load(sys.stdin)
    except (ValueError, OSError):
        payload = {}
    # Once per commit, and never twice in a row: the hook must not trap a turn.
    if not question or payload.get("stop_hook_active"):
        return 0
    stamp = REPO / (git("rev-parse", "--git-path", "check_learned_stamp") or ".git/check_learned_stamp")
    try:
        if stamp.read_text().strip() == head:
            return 0
    except OSError:
        pass
    try:
        stamp.write_text(head)
    except OSError:
        return 0
    print(question, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
