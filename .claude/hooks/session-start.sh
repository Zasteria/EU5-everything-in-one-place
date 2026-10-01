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

    # Generators: silent while every one is `ok` and nothing was rewritten.
    if echo "$refresh" | grep -qE '^(FAIL|note)'; then
        echo
        echo "generators — not all clean:"
        echo "$refresh" | grep -A4 -E '^(FAIL|note)'
    elif echo "$refresh" | grep -q '^changed by this run'; then
        echo
        echo "generated files moved under a refresh that has not been committed:"
        echo "$refresh" | sed -n '/^changed by this run/,$p'
    else
        echo "generators: all clean, nothing to rebuild"
    fi

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
