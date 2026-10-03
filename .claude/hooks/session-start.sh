#!/bin/bash
# Hand a fresh session the state of the tree — in about a hundred tokens.
#
# What a session needs at minute zero is the facts the documents cannot keep
# current on their own, because the owner refreshes `reference/` by hand and
# without notice: what is in the tree, whether the generated files still match
# it, and whether the documents still describe files that exist.
#
# It used to hand back every generator's full report — six paragraphs of counts
# that are correct, uninteresting while they are unchanged, and paid for on
# every turn of the session afterwards. So it now says only what is *wrong* or
# *moved*, and one line when nothing is. The full report is one command away:
# `python3 tools/refresh.py --check`.
set -uo pipefail

cd "${CLAUDE_PROJECT_DIR:-$(dirname "$0")/../..}" || exit 0

refresh=$(python3 tools/refresh.py --check 2>&1)
docs=$(python3 tools/check_docs.py --quiet 2>&1)
# Needs the network, so it gets a short leash and is allowed to say nothing.
steam=$(timeout 20 python3 tools/workshop.py status --quiet 2>/dev/null)

briefing=$(
    echo "State of the tree, read just now — trust this over any version written in a document."
    echo

    # reference/, one line: mod id and version, in the order refresh.py lists them.
    printf 'reference: '
    # refresh.py prints the block as "  %-40s %-34s %s" between `reference/`
    # and the first blank line; read it by column so a mod with no metadata.json
    # does not shift the fields.
    echo "$refresh" | awk '
        /^reference\/$/ { inside = 1; next }
        inside && /^$/   { exit }
        inside {
            id = substr($0, 44, 34); version = substr($0, 79)
            gsub(/^ +| +$/, "", id); gsub(/^ +| +$/, "", version)
            printf "%s %s · ", id, version
        }' | sed 's/ · $//'
    echo
    python3 tools/refs.py --game

    # Generators and checks: one line each, and only what is wrong. The full
    # report — a translation's every stale key, every check's every line — was
    # three thousand tokens on 2026-10-03, paid on every turn of every session
    # that never touched the mod. `python3 tools/refresh.py --check` has it all.
    echo "$refresh" | python3 -c '
import re, sys
from collections import Counter
lines = sys.stdin.read().splitlines()
gen, checks, moved, take = [], Counter(), [], False
for i, line in enumerate(lines):
    if re.match(r"(FAIL|note) [\w-]+$", line):
        block = []
        for l in lines[i + 1:]:
            if not l.startswith("     "):
                break
            block.append(l.strip())
        # The last line is the verdict: a traceback ends on the error, a
        # translation report on what to do about it.
        gen.append("%s %s (%d lines): %s" % (line.split()[0], line.split()[1],
                                             len(block), (block or [""])[-1][:110]))
    elif line.startswith("FAIL mods"):
        checks[re.sub(r"^FAIL mods[\\/]([^\\/]+).*", r"\1", line)] += 1
    elif line.startswith("changed by this run"):
        take = True
    elif take and line.startswith("  "):
        moved.append(line.strip())
if not gen and not checks and not moved:
    print("generators: all clean, nothing to rebuild")
for g in gen:
    print(g)
if checks:
    print("check_script: " + ", ".join("%s %d" % kv for kv in checks.most_common())
          + " — python3 tools/check_script.py for the lines")
if moved:
    print("a refresh would rewrite %d file(s), e.g. %s" % (len(moved), moved[0]))
'

    echo "documents: $docs"
    [ -n "$steam" ] && echo "$steam"

    echo
    echo "Read CLAUDE.md's routing, not the documents. Ask them: python3 tools/kb.py <words>"
)

python3 - "$briefing" <<'PY'
import json
import sys

print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": sys.argv[1],
    }
}))
PY
