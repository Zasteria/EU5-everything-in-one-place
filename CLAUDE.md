# Working in this repository

Mods for Europa Universalis V. Six of them, in [`mods/`](mods/), plus the game's
own files to grep and the tooling that rebuilds everything.

## Do not read this repository. Ask it.

The documents here are worth about ninety thousand tokens. Reading them is how a
session spends its whole budget before writing a line — and pays for them again
on every turn afterwards, because the context is resent each time. So:

    python3 tools/kb.py <words>            which section answers this, and what it costs
    python3 tools/kb.py --show FILE:LINE   read exactly that section

**The code is larger than the documents — ask it the same way**, and that
includes **the hand-written windows**: `code.py` indexes the comments in
`in_game/gui/*.gui`, where the interface keeps what its runs cost.

    python3 tools/code.py <words>          which effect, window or rule, and its cost
    python3 tools/code.py --show FILE:LINE read exactly that block

**Open a whole document or function only when the index says the answer fills
it.** `--map` is **not cheap — 4 000 tokens for `kb.py`, 13 000 for `code.py`**:
a last resort. `grep -rn` over `reference/` beats reading a game file.

## Start of a task

1. **The task names a mod** → read `mods/<mod>/CLAUDE.md`, that one only. It
   holds the state, the commands, and what fails silently in that mod.
   [`docs/STATUS.md`](docs/STATUS.md) is the one-line-each index if you need to
   pick.
2. **The task names no mod** → [`docs/NEXT_SESSION.md`](docs/NEXT_SESSION.md) is
   the job in progress.
3. **Before designing any test** → [`docs/SETTLED.md`](docs/SETTLED.md). It is
   short, every row cost the owner an evening, and asking for one of those
   measurements again is the one thing this repository cannot afford.

Everything else is on demand: [`docs/PITFALLS.md`](docs/PITFALLS.md) when
something silently does nothing, [`docs/RESEARCH.md`](docs/RESEARCH.md) for how
the engine and CMF actually work, [`docs/CONVENTIONS.md`](docs/CONVENTIONS.md)
for the reference tree and the rebuild loop,
[`docs/WORKSHOP.md`](docs/WORKSHOP.md) when putting a mod out.

## Rules that exist because breaking them is silent

- **Only the player can run the game.** Nothing here can be tested from a
  session. Say plainly what is verified and what is not. Build the smallest
  thing that would show a signal and ask for one run — a whole feature finished
  before its first load is how `where_to_produce` ended up with six suspects and
  no way to choose between them.
- **A run the player reports goes into [`docs/TESTLOG.md`](docs/TESTLOG.md) in
  the same session.** He reports it once, in passing; a session that does not
  write it down leaves the next one calling the thing untested.
- **End anything that changed the tree with two short lists: what changed, and
  what he has to check in the game.** His own words, 2026-09-02, after a summary
  that left him unable to tell whether a run was owed. **Where nothing needs
  one, say so outright** — «проверять нечего» is an answer he can act on. Where
  one is owed, name the ground, the presses and what a right answer looks like;
  «протестируй» is not a check.
- **Before touching any `.gui`, read
  [`docs/pitfalls/windows.md`](docs/pitfalls/windows.md)** — every rule in it is
  paid for. Windows cost more of his sessions than anything else: «меня заебало
  решать проблему окон чуть ли не через одну сессию», 2026-09-06.
- **A CMM macro called with an argument CMF does not declare fails silently**
  and takes the rest of its effect with it. `python3 tools/check_cmm.py
  mods/<mod>/in_game/common` after touching any CMM call.
- **A cause you cannot name is not a cause — measure it by diffing against
  something here that works.** Written once and broken again: one empty window,
  five builds, four of them guesses «по правилу» (09-14; «гадать НИКОГДА не
  нужно… Зонды, счётчики, проверки», 09-01). **First move is a diff, not a
  rule**; then a probe, so one run says where it breaks.
  [`docs/pitfalls/how_to_fix.md`](docs/pitfalls/how_to_fix.md) — the order of
  moves, and what each mistake cost here.
- **Effects that merely do nothing log nothing.** `error.log` names the file and
  line for GUI and script failures; one that never runs is invisible.
- **A `building_type` filter receives `root`**, whatever vanilla's comment says.
- **Localization has its own checklist**,
  [`docs/pitfalls/localization.md`](docs/pitfalls/localization.md): a
  `customizable_localization` cannot be overridden, square brackets in a value
  are data function syntax, a CMF action bar draws its `_icon` and `_color` from
  localization. Script and localization files carry a UTF-8 BOM and keys take one
  leading space; he plays in Russian, and a key missing there shows raw.

## Ask the game whether something exists

    python3 tools/api.py set_subsidized      an effect, trigger, target or GUI function
    python3 tools/api.py --find subsid       substring, across every dump
    python3 tools/api.py --says «Пересчитать» which key holds this text, and what draws it
    python3 tools/api.py --where checkbox    every file naming it

**Never state what the player sees, or what the game lacks, from memory** —
both cost a round trip on 2026-09-05. Every `api.py` answer ends with what it
did **not** search: `reference/` is partial. **An empty result is a fact about
the tree, never about the game.** Say plainly when something is unproven.

Do not hardcode a reference folder's name or trust a version written in prose:
`python3 tools/refs.py`.

## Rebuilding

    python3 tools/refresh.py           rebuild every generated file, report what moved

Run it at the start of a session; it is cheaper than believing a document. The
owner does this and the rest of his mod loop from `mods.bat`, a menu rather than
a command to remember. **Do not tell him to run the pieces by hand when the menu
covers it**, and do not build a step only a session can perform.

## Keeping this current

Write it down in the same session it was learnt, in the smallest place that
holds it — and keep that place small:

| what | where |
| --- | --- |
| a rule about the engine or an API | `docs/RESEARCH.md` and the file it indexes |
| a mistake and the symptom that revealed it | `docs/PITFALLS.md` |
| a mod's state, or what is untested | `mods/<mod>/CLAUDE.md`, one line in `docs/STATUS.md` |
| a measurement a run settled | `docs/TESTLOG.md`, and `docs/SETTLED.md` if it closes a question |
| a rule a checker could enforce instead | the checker |

**Everything under `docs/` has a size budget and `tools/check_docs.py` enforces
it.** A document over budget is not trimmed by deleting what it knows — it is
split, and the finished half moves to `docs/archive/`, which `kb.py` still
searches.
