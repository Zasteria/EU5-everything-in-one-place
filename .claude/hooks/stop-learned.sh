#!/bin/bash
# At the end of a turn: did this branch change a mod or record a run, and keep
# what it learnt out of the knowledge base? tools/check_learned.py says why this
# exists; it asks once per commit and never traps a turn.
cd "${CLAUDE_PROJECT_DIR:-$(dirname "$0")/../..}" || exit 0
python3 tools/check_learned.py --hook
