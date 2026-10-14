#!/usr/bin/env python3
"""Find every value National Destinies cut between two of its versions.

    python3 mods/nd_unnerf/tools/baseline.py [OLD_COMMIT NEW_COMMIT]

Reads both versions out of git history (the tree keeps only the current one)
and writes `mods/nd_unnerf/baseline.tsv`: one row per value that moved the
wrong way for the player, with the old and the new number. `generate.py`
builds the mod from that table and the current reference, so this runs only
when a new ND version brings a new round of cuts. The default commits are
`update ref mods` (ND 1.3.9, 2026-09-26) and `update ref` (ND 1.4.0,
2026-10-03).

What counts as a cut — the owner's ruling, 2026-10-14: soften the author's
nerfs, keep every buff, keep cheaper upkeep.

- A modifier is better higher, except the keys in `WORSE_HIGHER`.
- `monthly_towards_*` pushes a slider; it is cut when it pushes less.
- A building's upkeep goods (a production method without `produced`) are a
  cost: more goods is the cut. Production methods that make goods are left to
  the author, whose input and output are tuned against each other.
- Triggers (`allow`, `potential`, …) are conditions, not bonuses, and are left.
- `formable_countries` is the author's patch work on the game's own formables;
  left.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MOD = HERE.parent
REPO = MOD.parent.parent
sys.path.insert(0, str(HERE))

import script  # noqa: E402

OLD, NEW = "0f50c8b9", "613205d7"
ND = "reference/mods/3668193813_trin_national_destinies"
OUT = MOD / "baseline.tsv"

CATEGORIES = {
    "advances", "static_modifiers", "auto_modifiers", "bureaucracies",
    "building_types", "unit_types", "cabinet_actions",
}
TRIGGERS = {
    "allow", "potential", "trigger", "limit", "visible", "country_potential",
    "country_allow", "location_potential", "province_potential", "is_shown",
    "can_build", "potential_trigger", "ai_will_do", "scale", "build_trigger",
}
# Ambiguous for the player either way: left as the author wrote them.
NEUTRAL = {"combat_speed", "hull_size", "level", "value", "multiply", "add"}
WORSE_HIGHER = re.compile(
    r"cost|decay|separatism|unrest|inflation|war_exhaustion|damage_taken"
    r"|antagonism|_time$|supply_weight|crew_size|complacency|corruption"
    r"|unit_attrition|attrition_loss"
)
BETTER_ANYWAY = re.compile(r"efficiency|recovery|threshold")


def git_files(commit: str) -> list[str]:
    out = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", commit,
         f"{ND}/in_game/common", f"{ND}/main_menu/common"],
        capture_output=True, text=True, cwd=REPO, check=True,
    ).stdout.split()
    return [f for f in out if f.endswith(".txt")]


def git_text(commit: str, path: str) -> str:
    raw = subprocess.run(["git", "show", f"{commit}:{path}"],
                         capture_output=True, cwd=REPO, check=True).stdout
    return raw.decode("utf-8-sig")


def category(path: str) -> str:
    return path.split("/common/", 1)[1].split("/", 1)[0]


def objects(commit: str) -> dict:
    """{(category, name): (text, open, close)}."""
    found = {}
    for path in git_files(commit):
        cat = category(path)
        if cat not in CATEGORIES:
            continue
        text = git_text(commit, path)
        for key, _, start, end in script.objects(text):
            found[(cat, key.split(":")[-1])] = (text, start, end)
    return found


def upkeep_method(text: str, start: int, end: int, path: tuple) -> bool | None:
    """True for an upkeep method, False for one that makes goods, None if
    `path` is not inside a production method."""
    if not path or path[0][0] != "unique_production_methods" or len(path) < 3:
        return None
    method = path[1][0]
    body = text[start:end]
    m = re.search(r"\b%s\s*=\s*\{" % re.escape(method), body)
    if not m:
        return None
    depth, i = 0, m.end() - 1
    for i in range(m.end() - 1, len(body)):
        depth += {"{": 1, "}": -1}.get(body[i], 0)
        if depth == 0:
            break
    return not re.search(r"\bproduced\s*=", body[m.end():i])


def is_cut(key: str, old: float, new: float, upkeep: bool | None) -> bool:
    if upkeep is False:
        return False
    if upkeep is True:
        return key != "output" and new > old
    if key in NEUTRAL:
        return False
    if key.startswith("monthly_towards_"):
        return (old > 0 and new < old) or (old < 0 and new > old)
    if WORSE_HIGHER.search(key) and not BETTER_ANYWAY.search(key):
        return new > old
    return new < old


def main(argv: list[str]) -> int:
    old_commit, new_commit = (argv[1], argv[2]) if len(argv) > 2 else (OLD, NEW)
    old, new = objects(old_commit), objects(new_commit)
    rows = []
    for (cat, name), (text, start, end) in sorted(new.items()):
        if (cat, name) not in old:
            continue
        before = script.leaves(*old[(cat, name)])
        for path, (value, _, _, _) in script.leaves(text, start, end).items():
            if path not in before or before[path][0] == value:
                continue
            if any(step[0] in TRIGGERS or step[0].startswith("ai_") for step in path):
                continue
            key = path[-1][0]
            if is_cut(key, before[path][0], value, upkeep_method(text, start, end, path)):
                rows.append((cat, name, script.path_text(path), before[path][0], value))
    with OUT.open("w", encoding="utf-8", newline="\n") as f:
        f.write(f"# ND cuts, {old_commit} -> {new_commit}. Written by tools/baseline.py.\n")
        f.write("# category\tobject\tpath\tbefore\tafter\n")
        for cat, name, path, a, b in rows:
            f.write(f"{cat}\t{name}\t{path}\t{script.number(a)}\t{script.number(b)}\n")
    print(f"{len(rows)} cuts written to {OUT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
