# Why `where_to_produce` failed

**Picked up again in August 2026**, as a different mod with the same name:
[`../../mods/where_to_produce/CLAUDE.md`](../../../mods/where_to_produce/CLAUDE.md).
It answers the opposite question — borders first, then one building and one
method, then the locations ranked — and it is deliberately shipped before it is
finished, which is the lesson below applied rather than repeated. Everything
under this line is about the removed mod.

The mod was removed in August 2026: a Mod Menu tab that ranked what was worth
building in a province. It never worked in game, the owner stopped wanting it,
and the reason was never established because it was never tested. Kept because
the *shape* of the failure is the lesson, and it is quoted in
[`../PITFALLS.md`](../../PITFALLS.md).


It was removed in August 2026, unfinished, at the owner's word: "нерабочая
помойка, я ей не пользуюсь". Written down because the next attempt at the same
question should not repeat the shape of it.

**What it was.** A tab in CMF's Mod Menu. Four CMM list settings — region, area,
province, then the answer — where picking a row in one filled the next, and the
last ranked every building by what that province's raw materials were worth to
its best production method, in percent and in volume.

**What was verified, and what was not.** The data layer was checked against the
game and was right: the bonus formula matches three tooltips to the digit, and
an earlier build of the same data answered the *opposite* question ("for this
good, which province") correctly on screen — `Рудные горы / Оружейные заводы /
1.88% / 4.075` read true. Then the front end was rebuilt around province-first
picking, and **that rebuild was never run in game even once**. Nothing about the
new front is known to be broken; nothing about it is known to work either.

**Why the cause was never found.** The failure mode this repository hits most:
an effect that never runs logs nothing at all. Six things were suspect at once —
`region = { }` and `area = { }` as scope blocks, comparing `region =
global_var:x`, reading a variable map inside a script value, re-registering a
list at a new height, `GetRegion` / `GetArea` on a global variable, and whether
`can_build_building` was stricter than it looked. Diagnosing that needs one
`cmf_log` per suspect and one game run each, and the mod was not wanted enough
to pay for them.

**The lesson worth carrying.** The mod was built to completion before anything
of it was loaded once. A `cmf_log` on the first picker, run in game, would have
cost one round trip and told us which half of six unknowns was even in play. In
a repository where only the player can run the game, the size of the untested
increment *is* the risk — and the interface half, not the data half, is where
everything here has gone wrong.

**Where its parts went.** The formula and the CMM list mechanics are in
[`RESEARCH.md`](../../RESEARCH.md); the game-data reader is `tools/eu5data.py`,
untouched and still correct; the CMM macro check is `tools/check_cmm.py`, which
now runs against any mod. The mod itself is in git history — `git log --
mods/where_to_produce` — if a future approach wants to read how something was  <!-- check-docs: ignore -->
done.

**If the question gets picked up again**, two things are known to be possible and
were never done: a button injected into the location panel through
`scripted_widgets`, so the province on screen is the one answered for instead of
walking three pickers; and building straight from a row, since
`construct_building = { building_type owner payer }` in a location scope queues a
real construction and Construction Manager uses exactly that. The open question
there was never the effect — it was *which* location of the province to build in.

One thing the game files in `reference/` could not answer when this was written:
a *method* locked behind an advance. **Answered since** — `common/advances/` is
in the tree now, and `docs/research/engine.md` records how. The rest of this file
still stands.
