# Pitfalls — the reference tree changes under you

Split out of [`../PITFALLS.md`](../PITFALLS.md), which routes here. `reference/`
is refreshed whenever a mod updates, by a person, without notice — so every
assumption a generator makes about somebody else's files is a thing that will
break on a day nobody chose.


**An addon answers to its base mod's name.** `3784988919_glorp_ui_small_fix`
matches every hint that finds `3601047146_glorp_ui` — both folders contain
`glorp` and `ui` — and the day it arrived, `refs.mod("glorp.ui")` stopped being
able to answer at all and `glorpui_hints` failed to build. Folder names were
never enough on their own; the fix is that a candidate declaring exactly the
`id` asked for wins over one that merely reads like it. Expect more of this: an
addon is usually named after what it is an addon to.

**A folder name in `reference/mods/` is not a fact.** The owner refreshes these
by hand, and the name arrives however the upload produced it: the same mod is
`community_mod_framework` one time and `3692202776_community_mod_framework` the
next. Anything hardcoding the name breaks silently — a missing base mod reads as
"nothing to translate", not as an error. Ask `tools/refs.py`, which matches on
the `id` inside `metadata.json` (`trin.national_destinies`); the number in the
Steam path is not that id.

**Another mod's localization file is not written the way ours are.** A strict
parser — key, colon, quoted value, end of line — is right for this repository's
own files and wrong for everybody else's. `nation_destinies_rus` ends every
line with a `#NT!` marker *after* the closing quote, and a parser that insisted
on the quote being last read **8 keys out of 37 949** and produced a confident,
completely wrong conclusion about how much that mod translates. Allow a trailing
comment before drawing any conclusion from somebody else's file, and sanity-check
the count against the file size before believing it.

**A translated key can go stale while every check still passes.** When a base mod
*rewrites* an English value, the Russian under it is still present, still
markup-clean and still counted as covered — and now says something else.
Advanced Auto Build 0.9.3 did that to two keys, and nothing reported it, because
that generator kept no fingerprint of the English it had translated from. Both
translation generators keep one now (`english_generated_fingerprints.txt`,
signed off with `--accept`). Coverage is not currency.

**A workshop sync that pushed is not a refresh that ran.** `sync_workshop.ps1`
rebuilds the generated files only if it finds Python on that machine; without
one, the reference copies are committed and pushed and nothing else happens,
which reads exactly like a clean run. The first sync did this — **on a machine
with Python installed**, because the search was `Get-Command python/python3/py`
and an install made without ticking "Add python.exe to PATH" answers none of the
three. It reads the registry first now
(`Software\Python\<company>\<tag>\InstallPath`, which every python.org and
Store install writes whether or not PATH knows), and
`.\tools\sync_workshop.ps1 -CheckPython` reports what it would use and every
candidate it rejected. `workshop.py status` works the currency out from git
regardless, but the generators still have to run somewhere — `python3
tools/refresh.py` after any sync, and read the report.

**PowerShell hands a native command's output through a pipe, not a console.**
Python then encodes stdout with the machine's ANSI code page instead of UTF-8,
and the first Cyrillic line — `nd_ru`'s generator prints its report in Russian —
raises `UnicodeEncodeError` and takes the rest of the run with it. The sync
script sets `PYTHONUTF8=1` and `PYTHONIOENCODING=utf-8` before calling Python
for exactly this.

**A base mod that *deletes* a key stopped the whole update loop.** Advanced Auto
Build's 2026-08-28 build dropped 28 keys, the ranking-mode block among them.
`generate_ru.py` treated "a key here the base mod does not define" as the same
class of fault as "a key the base mod defines and nobody translated" and refused
to write anything — and because the mod menu runs every generator in one pass,
one deleted feature in somebody else's mod stopped the owner's update. The
generated file is written from the base mod's own key list, so a translation of
a deleted key is never emitted and nothing renders wrong: it is dead weight, not
a fault. It is now reported by name, the run goes on, and `--prune` takes the
lines out of `ru.yml`. A *rename* still stops the run, because that half shows up
as a missing key — which is the case that actually needs a human.

**A regex that reads somebody else's file in one shape goes quiet when they
change shape.** Glorp UI wrote its hint references as
`#TOOLTIP:ESTATE_PRIVILEGE,petty_bureaucracy #L $petty_bureaucracy$#!#!` and now
writes `[ShowEstatePrivilegeName('petty_bureaucracy')]` — the engine's own data
function, which does the same job. Two things in `glorpui_hints` read that shape,
and they failed differently: the hint parser raised, loudly, naming the line;
`PRIVILEGE_HINT_RE`, which finds the privileges an advance locks, would simply
have matched nothing, written an empty `svx_unlock_gate.txt`, and shipped a mod
recommending privileges the country cannot take, with nothing in any log. **A
loud failure is the lucky one.** Both shapes are accepted now, and
`check_gates_found_something` compares the two readings against each other, so a
third shape stops the run instead of emptying a file.

**Re-emitting somebody else's block drops whatever your parse cannot see.**
`glorpui_hints` replaces Glorp UI's `blockoverride` on the societal value
tooltip wholesale, and it used to rebuild their half from the entries its regex
recognised — a `ScriptValue(...)` gate, a title, a `Localize(...)` body. Glorp
UI's 2026-08-28 build added one entry per side with **none of the three**:
vanilla's own C++ hint blob, `[SocietalValue.GetLeftHint(Player.Self)]`, behind
their new `showUnavailableSocietalValueSuggestions` setting. The parse could not
see it, the check that compares the two lists compared parsed entries and passed,
and the entry was silently dropped — so their new switch did nothing for anyone
running both mods, and because the same setting also switches *their* per-axis
lists off (`NOT = { has_variable = ... }` in every `glorpui_svh_visible_*`),
turning it on made half the tooltip vanish. Nothing in `error.log`.

The fix is not a better regex. **Copy the bytes**: the block is spliced in
verbatim and the check compares text, so a shape nobody has thought of survives
by default. This is the second time in two days that a parse of somebody else's
file went quiet when they changed shape — the entry above it is the first. When
this repository holds a copy of another mod's *structure* rather than its data,
copy it, do not re-derive it.

**A copy synced and not yet committed reads as `behind`.** `record` dated a
reference copy by `git log` — which still knows only the old commit — so the
sync stamped two mods it had just brought in as out of date, and the run ended
by telling the owner to run the sync he had just run. Nothing under `reference/`
is ever hand-edited, so an uncommitted change there means exactly one thing: it
was just copied in. That is now its own verdict (`uncommitted`), and it says
"commit it" rather than "you are behind".

**A version written in prose goes stale the moment the owner updates a mod.**
That is not the owner's mistake to fix by annotating uploads; it is the
document's mistake. Versions come from `python3 tools/refs.py`, and a mod
arriving newer than a document remembers is the normal state of this repository
rather than something to report as a problem.


**Never put the old game back with `git checkout <old> -- reference/game`.** It
writes the old files over the new and re-adds what the patch deleted — into the
index too — and `git checkout HEAD -- reference/game` afterwards restores the
changed files but leaves the deleted ones behind, staged (10-13: two canal files
1.4.1 had removed rode into a commit's index). To read the previous game, use
`git show <old>:<path>` or `git archive <old> reference/game/... | tar -x -C <scratch>`.

**After a patch, a copy of the game's own text that a mod carries goes stale
silently — find the plain ones by comparing with the previous game.** A mod's
copy of a type, a template or a whole window shadows the game's, so the patch
never shows. Three-way: equal to the new game — fine; equal to the old game —
a plain copy, take the game's; equal to neither — the mod's own edit, port by
hand. On 1.4.1 that sorted CMF's 201 copies into 190 / 11 / 0 in a minute
(`cmf_dev_beta` +beta12 now takes the game's for any copy without `cmf`/`cmm`).
