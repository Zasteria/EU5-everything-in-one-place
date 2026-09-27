# Community wishlist - fix backlog for Responsive Universalis

Compiled 2026-07-22 from Paradox forum threads, Steam discussions, reviews, top mod
feature sets and Paradox's Grand Voyage roadmap acknowledgments. Excludes
everything already fixed by Paradox through 1.3.11 and everything the Responsive
Universalis family already covers. Items Paradox has announced but not shipped are
marked (planned).

## Scope rules (Matte, 2026-07-22)
- We fix problems, we do not write content. No story or flavor items, no event
  packs, no mission trees, no per-country or per-region content. If the fix IS
  new content, it is out of scope for this mod family.
- Mechanical fixes, balance, AI, UI and QoL are in scope.
- A fix needs a CLEAR USER CASE, not just an existing complaint (Matte,
  2026-07-23). Many list items turned out to already exist in game or to
  misread mechanics.

1. Filterable RGO map mode (Matte's idea) - SHELVED 2026-07-23 after extensive
   attempts: selection state, custom map mode and ledger integration all built
   and individually verified, but in-game behavior stayed wrong (stuck
   selection, grey map). Full implementation preserved at git tag
   shelved-rgo-finder for revival after future patches.
2. Sieges require the besieger to outnumber the garrison (Matte's idea) -
   UNBLOCKED 2026-08-19 (the July "engine-blocked" verdict was wrong): siege
   INITIATION gating truly does not exist (complete exe define registry
   enumerated, 2975 defines, zero besieger-ratio keys), but vanilla ships a
   `garrison_sortie` AI generic action (common/generic_actions/siege.txt)
   with LIVE strength numbers on both sides (garrison_strength,
   siege besieger_strength, strength_ratio_for_garrison_sortie script
   value). The bug is tuning: a garrison only sorties ALONE at ratio > 5.0
   and only checks every 35 days. Fix = lower the threshold (~1.5-2.0, a
   losing sortie instantly loses the fort, keep a win margin) and tighten
   the check cadence. Works both directions (player automation tick exists).
   Now item 1 of the top-10 build list below.
3. Navy Gather Food and Distribute Food on by default (Matte's idea) -
   ENGINE-BLOCKED 2026-07-22: hardcoded unit actions, no define, no effect, no
   setter exposed. Re-check after every patch.
4. Control spreading by geography and infrastructure, not just circles from the capital
5. Mountain penalties that respect actual local capitals (Esfahan case)
6. Expansion that yields something: taxes and manpower from new land, not only costs
7. Cheaper or faster ways to raise control in conquered land
8. Capital relocation meta - STRUCK 2026-07-23: no clean solve, and already milder via shipped control fixes
9. Roads and harbors raising proximity - BUILT v1.2.0: roads carry control (capital roads 3x), base port radiates proximity 20
10. Integration progress feedback - SOLVED per Matte: covered by the accelerated integration levels
11. Coring and integration costs scaled to country size - SOLVED by the
    accelerated integration levels (v1.2.0), cost scales with the economy
12. Less punishing overextension death spiral - DEPRIORITIZED, Matte has not
    encountered it, likely already covered by pillars 1-2 and autonomy
13. The suppress rebellions army order doing anything at all - NOTE: order is
    so obscure Matte did not know it existed; investigate its actual effect later
14. Proactive tools to prevent revolts, not just react - BUILT in v1.2.0:
    forts deter unrest tenfold, bailiffs keep local order (Matte's design)
15. A provoke-rebels style batch-clearing option
16. Rebel respawn loops - STRUCK: never observed (no user case)
17. Cabinet babysitting rebellions - explained, likely stale complaint; SKIP
18. Estate satisfaction micro - STRUCK: automation handles it, zero micro in practice
19. Estate demands - redirected per Matte: stabilize country cabinet action DOUBLED instead (was underpowered), faster stability = faster change
20. Peasant Enfranchisement cost - SKIP: unclear meaning, no user case
21. Unrest forecasting - STRUCK: exists as popup with percentages
22. Build queue - STRUCK: exists in the build menu
23. Auto-expand toggle - STRUCK: exists
24. Auto-upgrade obsolete buildings - INVESTIGATE: check if AI/auto-build erects upgraded tiers and whether retroactive upgrading is reachable
25. Priority auto-build - SKIP
26. Building filters - STRUCK: exists via map modes
27. Mass expand per building - STRUCK: exists
28. Building upkeep yearly creep - STRUCK: upkeep is goods-priced (maintenance production methods), moves with market prices, working as designed
29. Market access upkeep penalty - STRUCK: no such mechanism found in files; no user case
30. Production buildings as strategic choices, not passive money printers
31. Food glut fixed: food scarcity mattering to prices and growth
32. Pop growth pacing rework (the 1.2 10x cut controversy)
33. Ship costs down from the 1.3 hike
34. Price elasticity working across all goods
35. Inflation as a manageable mechanic with counterplay
36. Trade UI showing why a route is profitable or not
37. Merchant capacity readable at a glance
38. Better bankruptcy recovery path
39. AI personalities and attitudes you can read (EU4 layer, acknowledged missing)
40. Visible AI goals: know why a neighbor hates you
41. Major powers pushing their advantage late game
42. AI coalitions forming against runaway blobs - INVERTED 2026-08-19: the
    live complaint is now the opposite (coalition spam, suicidal coalitions
    vs the player: threads Jun 30, Feb 24, Nov 20). Do NOT build the July
    direction; if anything the community wants coalitions rarer.
43. AI colonizing competitively
44. AI navies used with purpose instead of idling
45. AI not chasing rebels across the continent while losing its capital
46. AI reinforcing its sieges under threat instead of starving
47. AI peace evaluation: accepting reasonable deals earlier
48. AI army composition keeping up through the ages
49. AI handling of multi-front wars
50. Smarter AI ally war contribution (show up to the actual front)
51. Sieges less tedious overall
52. Carpet sieging less dominant as a war strategy
53. Fort zone of control rules that are readable on the map
54. Battles mattering more relative to siege grinding
55. War exhaustion reflecting actual war performance
56. Better frontage and combat width feedback in battle UI
57. Combined arms mattering: no single-unit-type meta
58. Levies vs regulars balance across eras
59. Manpower recovery pacing late game
60. Clearer supply and attrition preview before moving armies
61. Naval pathfinding through straits fixed (Bosphorus, Oresund, Gibraltar)
62. Galleys viable for Mediterranean powers
63. Naval blockades with visible impact
64. Army maintenance slider or peacetime cost relief - STALE 2026-08-19:
    maintenance funding levels already exist in-game and players toggle
    them at peace freely (May 18 thread even calls the toggle too
    forgiving). Nothing to build.
65. Peace negotiation overhaul: bilateral demands (planned 1.5)
66. Peace deals transferring occupied land you actually hold
67. Subject relationship contracts: negotiate terms (planned 1.5)
68. Tributaries acting as truly independent nations
69. Alliances less predictable after 1600
70. Diplomatic actions beyond ally-rival binary (economic warfare, planned 1.4)
71. Great Power status from actual dominance, not a score formula
72. Truce-breaking consequences that make sense
73. Better coalition and aggressive expansion transparency
74. Exploration missions sortable and filterable
75. Exploration with less menu micromanagement
76. Colonization overhaul (acknowledged, details pending)
77. Colonial nations forming correctly across continents
78. Colonial charters clearer: what you get and when
79. Distance penalties for overseas holdings that feel fair
80. Culturally and religiously plausible character generation
81. Fewer nonsense character events for the wrong government type
82. Character skill actually mattering for outcomes
83. A working ledger with sortable comparisons
84. More and better map modes (food, building levels, unrest)
85. Better tooltips on other countries' relations
86. Building limit and efficiency visible while constructing
87. Map zoom range extension both directions
88. Macro alerts that are configurable per severity
89. Outliner customization: pin what you care about
90. Late-game performance past 1700 on mid-range PCs

## Top 10 build candidates (2026-08-19 refresh, Claude + Matte)

Selection rule: highest value x feasibility. Every lever verified to exist
(exe define registry, modifier registry, vanilla files) and every complaint
refreshed against current Steam discussions this day. Dropped by the
refresh: coalitions-against-blobs (complaint inverted, see item 42) and
peacetime maintenance relief (stale, see item 64).

1. **Garrisons punish undermanned sieges** (Matte's biggest item, was
   engine-blocked, now unblocked - see item 2 above for the full mechanism).
   Lever: generic_actions/siege.txt ai_will_do alone-sortie ratio 5.0 ->
   ~1.5-2.0 + ai_tick_frequency 35 -> ~10-15 (siege phase is 30 days).
   Complaint: Matte's own MP campaigns; "Are Sieges Broken?" Jul 10.
2. **AI accepts reasonable peace deals earlier.** Levers (all RTTI-real):
   PEACE_OFFER_WAR_ENTHUSIASM_THRESHOLD 0.6, IDEAL_WARSCORE_DIFFERENCE_
   THRESHOLD_TO_CONSIDER_PEACE 20, AI_PEACE_CHECK_DAYS 90, MINIMUM_WAR_
   SCORE_TO_CONSIDER_DEFEAT -50. Complaint: fresh (Aug 15, Jan 5 "peace
   deal system is broken", Feb 14 absurd-outcome thread).
3. **Bankruptcy stops being a century scar.** Levers: BANKRUPTCY_DURATION_
   IN_MONTHS 60, BANKRUPTCY_STAB_LOSS -50, CREDITWORTHINESS_BANKRUPTCY_
   YEARLY_RECOVERY 0.005 (Paradox's own comment: "~0.5 over 100 years").
   Complaint: fresh (Jul 11 "Bankruptcy spirals: They're back!!!", Jan 29,
   big Nov cluster). Fits the mod's anti-death-spiral identity exactly.
4. **Province peace costs down.** Levers: wargoals/00_default.txt
   conquer_cost/subjugate_cost multipliers + PEACE_COST_EFFICIENCY_*
   defines. Complaint: fresh (Aug 14 "war score prices for provinces are
   astronomical"). Pairs with item 2: wars end, and end reasonably.
5. **Parliament callable earlier.** Lever: PARLIAMENT_COOLDOWN_MONTHS 59
   (the real key; the 08-16 guess PARLIAMENT_MONTHS_NOT_CALLED_THRESHOLD
   was wrong). Complaint: direct Workshop request (Nate700, May 12) plus
   live parliament friction (Jul 6).
6. **War exhaustion reflects battle performance.** Levers: LAND/NAVAL_WAR_
   EXHAUSTION_FROM_LOSSES, MAX_WAR_EXHAUSTION_FROM_BATTLE, WAR_ENTHUSIASM_
   ONGOING_BATTLES. Complaint: WEAK in the fresh sweep - kept on the July
   compilation + review sources. Build LAST, or cut if still quiet.
7. **Manpower and mercenary pools recover.** Levers: MONTHLY_REINFORCE
   0.25, MAX_MANPOWER_YEARS 5, MERCENARY_MANPOWER_REPLENISH_TIME_DAYS 3600
   (Paradox already halved it once, their comment admits it was far too
   slow). Complaint: fresh (Aug 11 "almost no mercenaries left to hire
   mid-game", late-game manpower threads).
8. **Inflation counterplay.** Lever: reduce_inflation cabinet action at a
   token monthly_inflation -0.00025 - boost it (same pattern as the shipped
   stabilize pillar). Complaint: large Nov cluster (gold-mine inflation has
   no counter, "I don't see any cabinet action to reduce it" - it exists
   but is imperceptible, which IS the finding); mechanic unchanged since.
9. **Battles matter vs carpet sieging.** Levers: CARPET_SIEGE_MAX_ARMIES
   10, AI_CARPET_SIEGE_MAX_ARMIES_FACTOR, WAR_ENTHUSIASM_ONGOING_BATTLES.
   Complements shipped pillars 6/7. Complaint: fresh (Aug 14 "AI doesn't
   take chances on even battles... don't like helping allies").
10. **Missing map modes: devastation back, unrest added.** Lever: full-file
    map_modes override, STATIC modes only (no toggle panel - the shelved
    RGO repaint bug class stays untouched). Complaint: fresh (Jul 19
    "Devastation map mode - did they remove it?", Aug 15 map info asks).

## Recon 2026-08-16 (Workshop discussions sweep, Claude)
- REQUEST (clear user case, mechanical, in scope): building automation
  can destroy forts, user asks for a guard. Workshop Discussions, Nate700,
  12 May. Candidate CF pillar: automation must never demolish forts.
- REQUEST (defines-only, in scope): call Parliament earlier, after one
  year or when a war starts. Same user. The lever likely exists:
  PARLIAMENT_MONTHS_NOT_CALLED_THRESHOLD (seen in static_modifiers
  comments). Candidate CF pillar or tiny optional mod.
- SIGNAL: "Literacy Provide More Research Speed" by megalovania is
  trending this week, a standalone of an existing CF pillar. Demand for
  the pillar proven, discovery of CF remains the gap.
- SIGNAL: three governor mods trending in one week (Universal Governors,
  Local and Naval Governors Unlocked, Province Governors 20%) - governors
  are a hot demand cluster, mostly content-adjacent, watch not build.
- META: "Workshop AI slop problem" thread active since 8 Aug - community
  sensitive to low-effort mod spam; verified-quality positioning helps.
