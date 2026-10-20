# Translating somebody else's mod

Three of the mods here are translations. What that job actually is, what it
costs, and the ways a localization breaks in silence.

## Translating a mod that ships without your language

A separate mod carrying one `.yml` is the whole job. It needs no dependency on
the mod it translates — the keys simply add, and nothing collides — and only a
CMF dependency if it redefines one of CMF's own shared keys. `auto_build_ru` is
the worked example; its `mods/auto_build_ru/tools/generate_ru.py` is written
against one mod but
the shape of it is reusable.

**A mod may ship a language that is only the English text.** National Destinies
ships eleven languages whose files are byte identical to the English ones apart
from the `l_<language>:` header, so it reads in English in a Russian game while
`localization/russian/` plainly exists. Diff against `english/` before believing
a language is present.

That changes the job from adding keys to **overriding** them, which is confirmed
working in game: a separate localization mod loaded after the base mod replaces
the base mod's values for the same keys. Load order decides, so the translation
declares a dependency on the mod it translates and has to sit below it in the
playset.

**Read the size before quoting one.** A mod's key count badly overstates the
work. Of Advanced Auto Build's 1201 keys, 372 were pure markup, 316 were
`$vanilla_key$` passthrough, and another 315 were families differing only by a
number — 883 strings of actual prose, and about 6000 words. Count what is left
after stripping `[...]`, `$...$`, `@icon!` and `#code`, not lines.

**Audit before translating.** Four checks, each cheap and each has caught
something:

1. Parse every language the mod ships and compare key sets. Equal sets mean the
   English is a complete translation and can be the source; a gap means the
   other language is the original and has to be consulted for those keys.
2. Collect every key its `.gui` files and scripts reference — `text`, `tooltip`,
   `raw_tooltip`, `custom_tooltip`, and `$...$` inside other values — and check
   each is defined. A dangling one renders raw in *every* language, and is the
   mod's bug rather than yours.
3. Derive the CMM keys from its registration effects (see
   [Mod Menu settings](#mod-menu-settings-cmm)) and check those too. This is
   where a real mod is likeliest to be missing one.
4. Look for keys that are not the mod's own. A mod may redefine a vanilla or CMF
   key, and translating it changes what every other mod says.

**Ask the game what it calls its own concepts.** A mod's prose names game
concepts in plain text — advances, levies, bureaucracy — and inventing a word for
them produces exactly the disease the translation is meant to cure: a private
term sitting in the middle of the game's own interface. The game's localization
answers it: match the English value against `localization/english`, read the
Russian value of the same key. In EU5 1.3.10 advances are «Улучшения», not
«достижения», which is what a session guessed before the game's files were in the
repository. `nd_ru/tools/term.py` (мод убран 10-20, история git) is that lookup.

Inside `[advances|e]` and other concept links the game substitutes the name
itself, so the word only has to be chosen where the mod writes it as prose.

**What must not be translated.** Each of these looks like text and is not:

| Looks like | Is | If translated |
| --- | --- | --- |
| `gold` under `<element>_color` | a CMF palette name | the action bar button vanishes |
| `@production_panel!` | a texticon | renders as literal text |
| `$farming_village$` | a reference to the game's own key | breaks; it was already in the player's language |
| `[GetPlayer.MakeScope...]` | a data function | `ERROR:` on screen |
| `#G ... #!` | a colour code | the colour is lost, or the text is |

Passthrough is the happy case: a mod that names its buildings
`$vanilla_key$` needs none of them translated.

**A mod of a hundred thousand words is a different job.** `auto_build_ru` was
6000 words and fitted in one sitting. National Destinies is some 690 000 words
of prose across 220 files, which no subscription pays for in full. Take the
current figure from `generate_ru.py` rather than from here. What that changes:

- **Measure before promising.** Count prose words after stripping markup, not
  keys and not lines. Then convert to sessions: one session of steady work moved
  about 25 000 words, tooling and mistakes included. That number is the only
  honest basis for "how long will this take".
- **The order of work is a deliverable.** A file like `priority.txt` naming the
  stems in the order they matter — for a player, the region they actually play —
  lets any later session pick up without re-deciding anything.
- **Translate in layers, not files.** Names first (short, low judgement, most
  visible), then the events a player reads, then descriptions. A layer finished
  across the whole mod is worth more than a few files finished completely.
- **Look for the cheap thousands.** `nd_bureaucracy_impact_modifier_types` holds
  1770 keys built from three sentences; `nd_event_guards` holds 144 keys built
  from one. Both were generated from templates in minutes and fixed their line
  for every country at once. Before translating by hand, group the file's values
  by shape and see how many distinct sentences there really are.

**A key of a country need not live in that country's file.** Westphalia had 88
keys in `nd_wes` and 10 more in a shared modifier file. Checking one file and
declaring the country done is how a gap survives. Search every file for the tag.

**`_entry` keys are usually passthrough.** `nd_wes.1.entry: "$nd_wes.1.t$"` is a
reference to the event title, so translating the title makes the log entry
Russian by itself. Translating the entry as well is wasted work.

**Overriding another mod's localization works, and stacks with a third.** A
separate mod loaded later replaces the base mod's values for the same keys —
confirmed in game. That also means a hand translation can sit on top of somebody
else's machine translation of the same mod: theirs below, yours above, and the
player gets your keys where you have them and theirs everywhere else. Two
conditions: the overriding mod must load later, and **its file names must differ**,
because a file of the same name replaces the whole file rather than merging keys.
Naming the generated output `<stem>_ru_generated_l_russian.yml` keeps it clear of
both the base mod and any other translation.

**A base-mod update rewrites keys you have already translated, and most of
those rewrites are invisible.** National Destinies 1.3.7 touched exactly four
localization files: 67 new keys and one rewritten value in `nd_dnm`, one
rewritten value in `nd_dnm_country`, one in `nd_ymp`, four passthrough `.entry`
keys. The generator's markup check caught one of the three rewrites — the one
whose brackets changed. The other two were found only by diffing the reference
tree between the two versions:

```
git log --oneline -- reference/mods                # when the owner refreshed
git show <commit> --stat | grep localization/english | grep -v '|   0$'
```

That works only while the old version is still in git history, so do not rely on
it. Fingerprint instead: record a digest of the English value behind every
translated key, and have the generator name the ones that moved. Then a base-mod
update really is *one run that names the keys*, which is what this section used
to promise and could not deliver. `nd_ru/english_generated_fingerprints.txt` (мод убран 10-20, история git)
is that record, and `generate_ru.py --accept` is how a reviewed key is signed off.
**A partial translation layered over a machine one is a deliberate design, not a
shortfall.** `nd_ru` covers a tenth of National Destinies and is meant to: the
owner also runs `nation_destinies_rus`, Google's machine translation of 93% of
the mod, and mounts `nd_ru` *after* it. Every key we translate is upgraded from
machine to human; every key we have not reached still reads as Russian rather
than as English. So "only 10%" is never a problem to solve by rushing coverage,
and the completeness figure `scope.py` prints is a measure of work done, not of
work owed. The one thing that must hold is the load order — ours later. The
numbers are in
[`../archive/nd_ru_and_the_machine_translation.md`](../archive/nd_ru_and_the_machine_translation.md),
and the decision is in that document's settled table: **it is not a question to
put to the owner again.**

`auto_build_ru` keeps one too now — it did not, and the update to 0.9.3 rewrote
two of its English values under a Russian translation that went on reporting
itself complete. A generator that checks only *coverage* cannot see that: the key
is still there, still translated, and no longer true.

**Generate rather than hand-write the final file.** Keep the prose in a source
file and emit the game's `.yml` from it, with the source checked against the
base mod's English: every key covered, no key invented, and the markup of each
value identical in both. That last check is the one that earns its keep — it
catches a bracket eaten while rewording, which is otherwise found by the player.
It also turns a base-mod update into one run that names the keys whose *markup*
moved — which is not the same as every key that moved, see above.

**Families collapse.** Keys differing only by a number — twenty template slots,
step buttons, per-ordinal rows — are worth writing once with a placeholder and
expanding over the numbers the base mod actually uses. Collapse only when the
*values* match too: `eu5ab_building_age_1..6` share a key shape and are six
different ages.


## Shipping in all eleven languages

The game has eleven: `braz_por`, `english`, `french`, `german`, `japanese`,
`korean`, `polish`, `russian`, `simp_chinese`, `spanish`, `turkish`. That is not
read off a wiki — it is the folder list every mod in `reference/mods/` carries,
Community Mod Framework, Glorp UI and Construction Manager alike, and
`reference/game/main_menu/localization/` is a subset of it because
`tools/game_files_manifest.txt` only extracts two.

`glorpui_hints` went from one language to eleven for about **fifty short strings
each**, and the three things that made that possible generalise:

**Translate the opener, not the line.** A generated hint is an opening phrase, a
`$key$` reference the game resolves in the player's language, and a number. Only
the first is language specific, so a language is a phrase table and the
generator does the rest — which also means an update to the mod being extended
is picked up in every language at once rather than in one.

**The reference in the middle has more than one shape, and the engine's own is
one of them.** Glorp UI wrote `#TOOLTIP:ESTATE_PRIVILEGE,petty_bureaucracy #L
$petty_bureaucracy$#!#!` and now writes
`[ShowEstatePrivilegeName('petty_bureaucracy')]`. Both render the object's name
in the player's language with its tooltip attached; the second is a GUI function
the engine declares, and there is one per object type —
`python3 tools/api.py --find ShowEstatePrivilegeName` for the family, including
the `...WithNoTooltip` variants. Either way it is copied through a translation
byte for byte, so a parser wants to accept both and carry whichever it found
into the output unchanged. Which opener a reference asks for is derived from the
function name rather than tabulated: `ShowEstatePrivilegeName` is the registry
the markup form spells `ESTATE_PRIVILEGE`, so an object type nobody has seen yet
fails with "no opener for registry X" — a one-line fix in `languages.py` — rather
than going untranslated.

**Write the opener with a placeholder, not as a prefix.** `"Grant {ref}"` and
`"{ref} gewähren"` are the same table entry; `"Grant "` and `"gewähren"` are not.
German, Turkish, Japanese and Korean all want the verb after the object, and a
prefix-substitution design cannot express that without being rewritten. The
observation is `Glorp UI small fix`'s, which puts the verb last in exactly those
four.

**Ask the game for its own nouns.** See the concept-token entry in
[`../PITFALLS.md`](../pitfalls/localization.md): fourteen category nouns cost
nothing in eleven languages and came out more accurate than the hand written
Russian they replaced.

**Keep every word in one file.** `mods/glorpui_hints/tools/languages.py` holds
every string the mod puts on screen and the generators hold none, so a
correction from somebody who actually speaks the language has exactly one place
to go, and a generated `.yml` is never the thing edited.

**A language folder is compared against the others, not against a list.**
`tools/check_cmm.py` reports a key one language defines and another does not,
because that is what shows on screen as a raw key. The one legitimate exception
is overriding *another mod's* key in one language only — repairing broken
grammar where it is broken and leaving the other ten alone — and the checker now
allows it where the game or a reference mod already defines the key in the
languages that are short of it.
