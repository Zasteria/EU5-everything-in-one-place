# CM Maps

Three of Construction Manager's map modes, lifted out and made to stand on their
own. No Construction Manager — three entries in the map-mode flyout under
**Economy**:

- **Потенциал продовольствия локации** — every land location coloured by how much
  food a level of raw-material village could take out of it, green through black.
- **Рекомендуемые городские права** — every location coloured by the town-rights
  specialization whose boosted buildings could draw the largest share of their
  input goods from the province's own RGOs. Hover for the full ranking of all the
  specializations, with the reason under each. Nine per-right maps sit behind it.
- **Рекомендуемое размещение губернатора** — every owned location coloured by how
  much proximity a new Local or Naval Governor built there would add, given what
  the capital and the existing governors already provide.

**These are copies, not reimplementations.** Every colour, threshold, gradient
and formula is Construction Manager's, down to its comments. That is the point:
they are worth having as a reference you can trust to agree with the mod they
came from.

## The nine per-right maps

`Рекомендуемые городские права` answers "which charter suits this land best".
The nine behind it answer the other direction — "where in the realm does *this*
charter suit the land" — one per royal right: tooling, jewelry, naval, textile,
weaponry, book, artisan, brewing, masonry.

They are `category = hidden`, exactly as in Construction Manager, so they are not
in the flyout. **A strip of icons appears over the map-mode banner at the bottom
of the screen whenever any map of this family is up**, and that is how you move
between them. Hovering an icon previews its map; clicking sets it; the × goes
back. Pick `Рекомендуемые городские права` from the flyout to get into the family
in the first place.

## What it costs

Two of the three maps are precomputed once per save and then only read.

- **Urban rights** walks every province definition once, on the first load of a
  save, and writes what it finds onto each of the province's locations. The stamp
  `bcm_trmm_stamp` means a reload never pays for it twice.
- **Food potential** writes one number per land location on the same pass, behind
  `bcm_fpot_stamp`.
- **Governor placement** is not precomputable the same way — it is a cheapest-path
  search out of every proximity source, and it depends on what the country owns.
  It runs **when you open the map**, in batches of eight locations per tick, so
  the map fills in over a few seconds rather than freezing anything. The result
  is cached for four years of game time; opening the map again inside that is
  free.

There is also a one-off **river-adjacency harvest** on a save's first load: the
placement search needs to know which neighbours a river genuinely connects, and
that list is readable only from the interface, so a hidden window records it in
batches over the first few seconds of play. It saves with the game and never runs
again.

## Why there is no on_action

Construction Manager starts its passes from `on_game_start_after_lobby` and
`on_game_load_after_lobby`. **Those are not the engine's.** The game's own dump
marks both `From Code: No` (`reference/game/docs/on_actions.log`) — the Community
Mod Framework declares them and fires them. The engine's own `on_game_start`
fires before the country selection screen and has no load-time counterpart.

Wiring to CMF's hooks would have made this mod need CMF, so it drives its own
setup from the window it already has: one hidden widget that fires the first time
any of the three passes is out of date, which is a new game, a save made before
this mod, or a version bump. It is the same shape as the river harvest driver
beside it, and it is Construction Manager's own idiom.

The one thing lost with the on_action is CM's load-time precompute of the
governor scores. `bcm_pf_recompute_now` is still there, marked NOT WIRED UP; a
CMF-aware version of this mod would call it and have the map already filled the
first time it opens.

## The settings page

**Community Mod Framework is a dependency**, and the one thing it carries is the
mod's settings page. Everything else drives itself; without CMF the page is all
that would be missing, since every setting below is read through an `exists`
check that falls through to the value the mod used before the page existed.

Under **Recommended Governor**:

- **Search Accuracy**, 1 (Exhaustive) to 5 (Fastest) — how hard the search looks.
  **It defaults to 1 here, where Construction Manager defaults to 3.** Tiers 2-5
  leave locations unevaluated and paint them black; that is fine in CM, where the
  tooltip over a black location tells you to raise the setting, and it was not
  fine here for as long as there was no setting to raise (2026-09-19). 1 is the
  only tier that skips nothing. It is also the slowest, so raising it is the
  first thing to try if the map is slow to fill.
- **Placement Finder Scoring**, **Land Infrastructure** and **Naval
  Infrastructure** — Construction Manager's three, at Construction Manager's
  defaults, which are also what this mod did before the page.
- **Recompute Governor Placement** — a button. A finished search is cached for
  four years of game time, so roads, harbors and governors built since do not
  reach the map until it expires. The button computes now: in front of you if the
  map is open, on the next opening if not. Changing any of the four settings does
  the same thing on its own.

Under **Map Data**:

- **Rebuild Map Data** — drops the three load-time stamps and runs the passes
  again: the industry coverage behind Recommended Urban Rights, food potential,
  and the river crossings the governor search routes through. Those are computed
  once per save, so their colours age as the campaign goes on. This is
  Construction Manager's own `cm_dbg_rebuild_setup`, which CM keeps behind debug
  mode; in a mod that is three maps it is not a debug button.

Under **Diagnostics**: **Enable Debug Diagnostics**, Construction Manager's path
dump in the governor tooltip.

## What was left behind

The maps came with parts of Construction Manager that only make sense inside it,
and those are not here:

- **Granting a charter from the map.** CM's urban-rights map has a row in its
  location tooltip that grants the charter and then switches auto-build on for
  the buildings it unlocks. Granting is CM's feature, not a map, and it reaches
  into auto-build, foreign building and the charter-cost settings. This mod shows
  you where; you grant it yourself, the way the game means you to.
- **The "житницы" map and the auto-food stripe** on the food map. Both read CM's
  auto-food, which is not here.
- **The capital-placement map.** The engine that scores it is carried — it is the
  same code the governor map runs — but the mode itself is not published, so that
  half never runs. Publishing it is a two-line change in the porter if it is ever
  wanted.
- **The action-bar refresh button.** CM puts one on the CMF action bar while a
  finder map is open. This mod has the same thing as a button on its settings
  page instead, which is a click further away and does not need the bar.

## How it is built

Nothing in `in_game/` or `main_menu/` is written by hand:

```
python3 mods/cm_maps/tools/port_from_cm.py
```

It reads `reference/mods/<construction manager dev>/`, takes the blocks named in
its own manifest, renames every `cm_` to `bcm_`, applies the wiring changes it
lists and explains one by one, and then refuses to finish if it left behind a
name it calls and does not define, or a name it failed to rename. `tools/refresh.py`
runs it with the other generators, so a Construction Manager update is picked up
by a rebuild rather than by hand.

The rename is total — values, effects, triggers, scripted guis, map modes, the
variables parked on locations, and the localization keys. That is what lets this
mod and Construction Manager be loaded together without writing over each other.

## Layout

```
mods/cm_maps/
  .metadata/metadata.json
  in_game/
    common/
      scripted_effects/          the urban-rights pass, the placement search
      scripted_triggers/
      scripted_guis/             what the two windows fire
      script_values/             every number the maps read
      customizable_localization/ the tooltips
    gfx/map/map_modes/           the twenty-three modes
    gui/
      bcm_pf_map_mode_window.gui          setup, river harvest, finder ticks
      bcm_town_rights_search_panel.gui    the icon strip
      scripted_widgets/                   what makes those two exist at all
  main_menu/
    gfx/interface/icons/map_modes/  twelve map-mode icons
    localization/{russian,english}/
  tools/port_from_cm.py
  CLAUDE.md
  README.md
```

## Standing beside `where_to_produce`

`where_to_produce` already carries its own copies of two of these three maps,
under `bag_wtp_` names. Loading both mods gives you two urban-rights maps and two
food maps that look alike and are computed separately — which works, but pays for
the province pass twice. If you run `where_to_produce`, you want this mod for the
governor map, or instead of it, not alongside it.

## Рядом с `where_to_produce`

**Две из трёх карт у `where_to_produce` уже есть**, под `bag_wtp_*`, из того же
CM dev — [`wtp_town_right_map.md`](../../docs/investigations/wtp_town_right_map.md).
Имена не сталкиваются, но обход провинций идёт дважды: осознанная цена, а не
находка. Перенесено сюда из
[`CLAUDE.md`](CLAUDE.md) 2026-09-19, когда тот вышел за бюджет.
