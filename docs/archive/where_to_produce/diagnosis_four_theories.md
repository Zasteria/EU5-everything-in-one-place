# The four theories that built the diagnostic

Split out of [`../pitfalls/diagnosis.md`](../../pitfalls/diagnosis.md) on
2026-09-03, at its budget. **This is the episode the whole instrument came out
of** — four of the owner's runs spent on four theories about one symptom, none of
them a measurement — and the rule it produced («a cause you cannot name is not a
cause») is quoted in the root `CLAUDE.md` and stays live there. What moved is the
narrative; `tools/kb.py` still searches it.

---

## Four theories, three fixes, and the cause still unknown

**2026-09-01, and it is why `CLAUDE.md` now forbids guessing.** One symptom —
`where_to_produce`'s plan would not put glass in a town — drew four explanations
out of a session in a row, each stated with more confidence than it had earned:

1. *the ground has no sand* → wrong; the owner's screenshots showed the game
   offering him a glass guild;
2. *`can_build_building` refuses it, so glass is impossible in Westphalia* →
   wrong, and it went into `SETTLED.md` before he disproved it;
3. *the charter is granted where the bundle cannot be finished* → real, but not
   the cause; fixing it changed nothing;
4. *sand is in the market but not **produced** there* → unfalsifiable from here,
   and the same run refuted it: **`glass_guild` and `rural_glassmaker` carry the
   identical gate, and glass appears in the villages while never appearing in the
   towns.** One condition cannot be true and false in one market.

Each theory cost a fix and a run. **The run is the scarce thing** — only the
owner can make one — and none of the four spent one on finding out.

**And the shape of the mistake is the same every time: a condition was read out
of `reference/` and then treated as a fact about the ground.** The tree says what
a condition *is*, never whether it *holds* — market contents, RGOs and buildings
are save state, and nothing here can see them. A `location_potential` explains why
a good *might* be missing; only a run says whether it is. Say which of the two
you have.

What should have been built after the first miss is a probe: a counter per stage
of the funnel, for one good, reported on the window. Availability, then
buildability, then a method won, then the placement gate, then placed. One run
reads it and the cause has nowhere left to hide.

