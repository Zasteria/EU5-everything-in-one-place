# Pitfalls: CMF and CMM

Split out of [`../PITFALLS.md`](../PITFALLS.md) 2026-09-09, when it outgrew
its budget. Everything here is about Community Mod Framework and its list and
settings macros: the ways a mod page, a setting or a list does nothing and says
nothing. How CMF works at all is [`../research/cmf.md`](../research/cmf.md);
`python3 tools/check_cmm.py mods/<mod>/in_game/common` enforces the first two.

**A CMM macro called *without* an argument CMF declares fails exactly like one
called with an argument it does not.** `cmm_register_settings_list` declares
`is_ordered`, the call omitted it, `$is_ordered$` stayed in the pasted text, and
every list registration died where it stood — taking everything after it in the
same effect, with no error anywhere. `check_cmm.py` now reports both directions.

**A CMM macro called with an argument CMF does not declare fails silently and
takes the rest of its effect with it.** `step` where CMF declares `step_value`
meant the setting never entered CMM's maps; syncing its alias then errored, and
everything after it in the same effect was skipped — including four other
settings. Symptom: an interface that renders perfectly and does nothing.
`python3 tools/check_cmm.py mods/<mod>/in_game/common` checks a whole mod against
whichever CMF is in `reference/`.

**And not only CMM macros: any scripted effect whose `$param$` sits only inside
quotes.** The game does not substitute a macro inside a quoted string, so such a
parameter is undeclared, and a call passing it drops the rest of the caller's
effect. `cmf_saved_settings` 0.1.0 printed `CMFSAVE begin` and nothing else;
0.1.1, the same code with `$kind$` gone from a `debug_log` string, printed 611
settings (10-14). `check_script.py` reports it (`quoted_only_parameters`).

**A formatted list field needs its format keys or it prints their names.**
`cmm_set_list_field_format` and `cmm_set_list_field_conditional_format` make the
widget read `<mod>__<setting>__<field>_prefix` and `_postfix`, and for the
conditional one also `_prefix_high` / `_postfix_high` / `_prefix_low` /
`_postfix_low`. CMF decides whether a key exists by comparing `Localize(key)`
against the key itself, so a missing one is not an error — it renders as its own
name, in the column, where a number should be. `cm__auto_build_list__min_discount_*`
shows the full set.

**A CMM list silently loses every row past the fiftieth.** CMF initialises list
items through an unrolled chain ending at item 50, so a list registered at 74
shows 50 rows and says nothing about the rest. Split into several lists — and
give each its own output, since `cmm_build_list_bool_list` clears the list it
builds into and a shared one would keep only the last.

**Asking a variable map for a key it does not hold is an error, not false.** A
CMM setting sitting at its registered default may never have been written to the
`cmm` map, so `"variable_map(cmm|flag:<mod>__<setting>)" >= 1` as a plain gate
can take the whole effect down on a new game. Guard it with
`is_key_in_variable_map` and decide what the absence means.

**`item = var:x` inside a CMM list macro dies at load** with "More than one
colon in event target link" — the macro pastes it verbatim. Ordinals into
`cmm_set_list_data_value` and friends have to be literals; generate a switch that
turns a counter into one.

**Dropdown options are numbered from one.** Registering with `default_index = 0`
put the stored value out of range, so nothing the player picked matched any
branch. Symptom: menu looks correctly filled in, nothing downstream reacts.

**`cmf_on_mod_registration` fires every time the mod page is opened.** Not on a
new game, a save load and a country transfer only, whatever it reads like:
`where_to_produce`'s registration ended with a `clear_rows`, and the result the
player had just computed was gone by the time he reached the button that reopens
it. Registration is for making things exist. Anything it destroys, it destroys on
a schedule nobody chose.

**A list row reading `ERROR_FLAG_INDEX`, with no checkbox, is an entry in the
list store that resolves to no row** — so `cmm_hide_list_item` cannot hide it
and it has no field. Seen twice in `rulers_toolkit` (0.6.0 on a new list, 0.6.3
on a list that grew from 27 to 31 rows); the cause is still unnamed. 0.6.4 checks
`cmm_list_items_<mod>__<setting>` against 1..N after registration and rebuilds it,
logging what it found. Rows are also stored by their position, so a list that
loses or reorders rows needs a new `setting_id`.
