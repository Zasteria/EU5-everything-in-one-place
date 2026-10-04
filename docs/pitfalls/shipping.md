# Pitfalls — publishing and loading

Split out of [`../PITFALLS.md`](../PITFALLS.md) when it outgrew its budget: what
goes wrong between a mod being written and a player actually running it. Same
rule as the rest of that file — every entry cost at least one round trip, and
none of them raises an error you would notice.

Ask for one rather than reading the file: `python3 tools/kb.py <words>`.

## Publishing

**The workshop's tag list is fixed, and a tag outside it is dropped rather than
refused.** Four mods here were filed under `Localization`, which EU5 does not
have; the tag it does have is `Translation`, and `Economy` is really
`Trade and Economics`. The upload says nothing, the mod simply ends up in no
category on a hub where people browse by category. The list read off the hub's
own filter sidebar is `WORKSHOP_TAGS` in
[`../tools/publish.py`](../tools/publish.py), and `python3 tools/publish.py`
checks every mod against it along with the version format, the thumbnail and the
BOM.

**The Steam app id for EU5 is `3450310`.** The wiki's PDX Workshop Manager page
says `529340`, which is Imperator: Rome. `3450310` is the one `steamcmd` in
`tools/workshop.py` actually downloads with.

## Loading

**Later file wins for a duplicate database key, and files sort by name.** A mod
redeclaring `sheep_farms` in `00_sheep_farm_food_buildings.txt` loses to
vanilla's `rural_buildings.txt`, because `00_` sorts first. The `00_` prefix is
for files that must load *early*; to override, sort late. Symptom: mod loads,
changes nothing, logs nothing.

**`metadata.json` needs `"game_id": "eu5"`.** Every working mod has it. Without
it the launcher does not treat the folder as an EU5 mod.

**Overriding another mod's *generated* override goes stale in complete
silence.** `mods/glorpui_hints/` overrides Glorp UI's override of the societal
value tooltip templates, and until 2026-10 it carried Glorp UI's hint lists as a
copy. When Glorp UI regenerates those — or, as with game 1.4, does not — nothing
errors: the templates still parse, the mod still loads, and the player quietly
gets a stale list. `error.log` says nothing, because nothing failed. Since
2026-10-03 the mod builds its lists from the game's own files
(`mods/glorpui_hints/tools/generate.py`) and takes from Glorp UI only the wording,
read at build time and refused if its shape changes. Any mod that copies another
mod's generated file needs a check like that written the same day the copy is
made.
