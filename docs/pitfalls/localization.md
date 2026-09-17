# Pitfalls — localization

Split out of [`../PITFALLS.md`](../PITFALLS.md), which routes here. The player
plays in Russian, every mod here ships localization, and this is the subject
that has cost the most round trips.


**A `customizable_localization` cannot be overridden.** Localization keys do —
a mod loading later wins, and `glorpui_hints` rewrites 759 of Glorp UI's every
build. A `customizable_localization` does the opposite: **the first definition
read wins, and the later duplicate is dropped**, saying so in the log and
nowhere else.

```
gamedatabase.h:408  Duplicated key glorpui_svh_free_subjects_pv_peasants_yeomanry
                    will not be created from file: ...
```

So an addon cannot tighten a base mod's rule by redeclaring it, however late it
loads — the redeclaration is simply thrown away and the base mod's rule keeps
running. What it *can* do is take over the localization key that rule prints and
point it at a rule of its own. That is what
`in_game/common/customizable_localization/svx_unlock_gate.txt` does. The line
came out of `Glorp UI small fix`, whose author had already hit it and written the
log line down.

**A category noun probably does not need translating at all.** The game defines
`game_concept_<name>` in all eleven of its localization folders, so
`[religious_aspect|e]` renders "Religious Aspect", «Религиозная особенность»,
"Glaubensaspekt" — for free, in the player's language, with the encyclopedia link
attached. `python3 tools/api.py` does not list these; grep
`reference/game/main_menu/localization/*/game_concepts_l_*.yml` for
`game_concept_`.

Beyond the ten languages it saves, it is the only way to be *sure* the term
matches the game's own. Fourteen category nouns in `glorpui_hints` were hand
written Russian and **seven of them were synonyms** rather than the game's word:
an advance is «Улучшение», not «Достижение»; a subject type «Тип ленника», not
«Тип вассала». Nobody would have noticed either without comparing.

The cost is that a concept the game renames becomes a raw token on screen in
every language at once and nothing errors — so check the ids against the game's
own localization in the generator, the way
`mods/glorpui_hints/tools/generate.py` does.

**Square brackets are data function syntax.** A label reading `[debug] location
known` renders as `ERROR:`. Keep brackets out of plain text.

**A `$NAME$` that names a key which does exist can still come out blank.**
`glorpui_hints` replaced its hand written modifier labels with references to the
game's own — `$STATIC_MODIFIER_NAME_parliament_outside_capital$` instead of
"Парламент вне столицы" — so that a patch renaming a modifier would be followed
for free. On screen some of them rendered and some rendered as nothing:
`is_bankrupt` was fine, `parliament_outside_capital` and
`peasants_percentage_in_country` were bare values with no text. All three keys
exist in the game's Russian files. Nothing was logged.

What separates them is still unknown, and that is the point: **a label that is
nothing but a reference has no floor.** If the reference resolves the line reads
correctly, and if it does not the line loses everything, silently. The rule now
in `mods/glorpui_hints/tools/generate.py` is not "no references" — the catalogue
lines have referenced `$building_type$` since the beginning and always worked —
but "every label carries literal text of its own", so a reference can lose part
of a line and never all of it.

**The left half of a `TooltipScrolledStringPairList` row is narrow, and it
truncates rather than wraps.** A hint line is `@hint! <label>: <value>`, and the
label has about as much room as a short noun phrase. Adding a parenthetical to
it — "(масштабируется: максимум при used_fort_limit_percentage = 200%)" — did
not make the row taller: it cut the *label* off at «Традиции армии ( …» and
«Во вр …» and spilled the rest across the value column. Nothing errors, and it
only shows on a screenshot. Whatever a hint line has to say has to fit in a few
words, or belong somewhere that is not that row.

**A mod-defined game concept with no texture renders as nothing.** The same
change made «(масштабируется)» a game concept so the explanation could be a
hover: `[Concept('svx_scale_army_tradition','(масштабируется)')|e]`, with the
concept declared in the mod's own `in_game/common/game_concepts/`. Glorp UI
proves a mod can define concepts — but every one of its own carries a `texture`,
and these carried only `shown_in_encyclopedia = no`. On screen the whole
`[Concept(...)]` produced empty output: the line kept its label and its value and
lost the word between them. No error, no log line. If a text-only concept is
wanted, prove it with one before generating forty.

**A `$NAME$` that names no key prints the name.** No error, no log line, no
blank: the engine puts `SOCIEALVALUE_RIGHTITEM_WNTT_GEN` in capitals in the
middle of the Russian sentence and carries on. The game's own Russian defines
seven societal value declension helpers as `SOCIETALVALUE_*` and references all
seven as `SOCIEALVALUE_*`, so twenty four keys print a name instead of a word —
and it took a screenshot to notice, because nothing else could. `missing_ref` in
`locscan.py` is the rule now. It is hard on the fault and careful about the
repair: the *nearest* defined key is not always the intended one, and four of
the thirteen references it finds are cultures whose neighbour is a different
people (Even and Evenk, Halkomelem and Halkomelemt, Lalagir and Lalagyr).

**A pattern in the data is not a fault until something fails.** All 1755
`*_culture_tt` keys in the game's Russian
`EU5_customizable_localization_ru_culrel_l_russian.yml` hold a bare number that
is exactly the key's own line number minus two — every one of them, plus 624
more in a sibling family. They are used as `#TOOLTIP:CULTURE,$X_tt$,`, where a
culture key looks like it belongs. That is a striking, verifiable pattern and it
reads exactly like a generator that wrote line numbers into tooltip targets, so
this document briefly said every culture tooltip in the Russian localization was
broken.

It is not. A hover settled it: the tooltips are complete and correct, and the
key on screen (`westphalian_cadj` → `#TOOLTIP:CULTURE,$westphalian_tt$,` →
`"1052"`, on line 1054) is one of the numeric ones. The number is what the engine
wants there, or the engine ignores it.

The cost of getting this wrong would have been 1755 keys rewritten to fix
nothing. **A pattern explains a fault; it does not establish one.** Before
repairing on the strength of a shape in the data, find the thing that visibly
fails — and if nothing visibly fails, that is the answer.

**A "broken" key can be a key nothing can call.** Three of the culture
references `missing_ref` found are declensions for `even_culture`,
`halkomelemt_culture` and `lalagyr_culture` — cultures the game does not have,
though `evenk_`, `halkomelem_` and `lalagir_` all exist. Unreachable, harmless,
and repairing them by pointing at the near neighbour would have put the Evenk
tooltip on the Even culture. Before repairing a dangling reference, check
whether the thing it belongs to exists at all: `reference/game/in_game/common/`
answers it, and a dead key is cheaper left alone than fixed wrong.

**A checker that silently reads less than it thinks is worse than no checker.**
`locscan.py`'s key regex required the line to end at the closing quote, so
`hre_tt: "0" #True` — a key with a comment after it — was not a key as far as
every rule was concerned. **18 012 keys, 3.4% of the tree**, invisible. The
symptom only appeared when a new rule started asking "is this reference
defined?" and answered no 1 418 times. Nothing was wrong with the rule. When a
checker's finding count looks too big to be true, suspect what the checker can
see before suspecting the game.

**The game loads the selected language's folder and nothing else — there is no
fallback to English.** Glorp UI generates 759 `GLORP_UI_SVH_*` keys into
`main_menu/localization/english/` and no other language, so on a Russian client
every one of them is missing, the societal value hint list renders empty, and
the tooltip says «Нет.» while `debug.log` takes 725 `Missing loc key` lines per
load. Nothing about that reads as a localization problem on screen: the widget
draws correctly and is simply blank. It hits all ten non-English languages, not
just Russian. When a mod's feature works in English and does nothing in Russian,
check which language folders it actually ships before looking anywhere else.

**A CMF action bar element is drawn entirely from localization**, keyed on the
element name: `_icon` takes a texticon such as `@good!`, `_name` and `_tooltip`
fill the tooltip, and **`_color` must name one of CMF's palette entries** or the
button is invisible in both bottom bars. The top position is a tab and skips
that gate, which makes a missing `_color` look like "only works in one position".

**A list setting is its own group**, so CMM keys its header through the tab:
`<mod>__<tab>__<setting>_name`. Getting this wrong prints the key on screen,
which at least tells you the right one.

**A model writing hundreds of Russian lines drops foreign characters into
them.** Three CJK ideographs landed mid-word in the first large batch
(`сохранив自 свою`), a fourth in a later one, and an English `though` survived in
a Russian sentence. None of it is visible while writing and none of it errors:
it simply renders on screen. On any batch past a few dozen lines, put the check
in the generator rather than trusting the eye — `mods/nd_ru/tools/generate_ru.py`
refuses a value carrying a character outside Cyrillic and the Latin proper names
need, or an English function word the source value does not itself contain.

**A Latin word given a Russian ending reads past every check that was in
place.** `territoryов` survived the CJK rule (Latin is allowed, for the mod's
proper names) and the English-function-word rule (`territory` is not a function
word), and would have reached the screen. The rule that catches it is narrower
and exact: a Latin letter glued to a Cyrillic one *inside one word* is never a
proper name and always a slip. It is in `generate_ru.py` now, and it fires on
nothing in the 4 000 keys already translated.

**A base-mod update can leave a translation stale in complete silence.** When
National Destinies went to 1.3.7 it rewrote `DNM_f_desc` and `nd_dnm.21.a_tt`.
Only the second was caught, and only because its *markup* changed; the first was
found by diffing the reference tree by hand. A rewritten sentence with the same
brackets looks identical to every check. `generate_ru.py` now fingerprints the
English behind every translated key in `english_generated_fingerprints.txt` and
names the ones that moved; `--accept` records the new English once the
translation has been brought up to date. Symptom without it: the Russian
confidently describes a mechanic the mod no longer has.

**Not everything with letters in it is prose.** `dip_..._CATEGORY:
"CATEGORY_HOSTILE_ACTIONS"` names one of the game's own interaction categories.
It has no markup to protect it, so it read as ordinary text and sat in
`scope.py`'s to-do list as two keys that would never go away. Translating it
would file the interaction under a category that does not exist. `scope.py`
excludes it now.

**Checking one file is not checking the country.** Westphalia looked finished at
88 keys; ten more sat in a shared modifier file, and the shared file for event
guards held one more. Grep every localization file for the tag before calling a
country done. Symptom: a panel that is Russian everywhere except one tooltip.

**A per-file completeness rule blocks a layered pass.** The generator first
demanded that a source file cover its base file entirely, which is right for a
small mod and wrong for a names-first pass over a large one. An untranslated key
simply stays with the base mod; count it and report it, do not refuse it.

**The mod's own `\"` is legal and the quote check must allow it.** A value like
`\"Let others wage war\"` parses fine; a naive "no double quotes" rule rejects
the whole file. Match an unescaped quote only.

**Generate localization for every language, not just English.** The player plays
in Russian; an English-only key shows as the raw key.

**The engine does not fall back to English.** A mod shipping only
`english` and `simp_chinese` renders every one of its keys as the raw key name
in a Russian game — the whole interface, not a stray label. That is what
Advanced Auto Build's Mod Menu tab looked like, and it is diagnosed by the
company it keeps: if other mods in the same list read correctly, the language
is fine and that mod's `.yml` for it is simply absent.

**A shipped language can be the English text under a different header.**
National Destinies ships eleven languages whose 220 files are byte identical to
the English ones apart from the `l_<language>:` line, so the mod reads in English
inside a Russian game while `localization/russian/` plainly exists. It is the
opposite symptom to a missing `.yml`, which shows raw keys — here everything
renders, just in the wrong language. Diff the files against `english/` before
concluding a language is present. It also changes the job: those keys are
defined, so a translation has to **override** them rather than add to them, and
the overriding mod has to load later.

**A `_format` key does nothing for a CMM setting.** Only list *fields* take a
format, and only through `cmm_set_list_field_format`. A row's text comes from
`_name`, `_desc` and `_text`. `search_filter_<key>_format` is the unrelated
filter convention that makes this look plausible.

**The base game's own Russian localization is broken, and it is the largest
single source of errors in a Russian game.** For a long time the answer to "the
log is full of localization errors" here was "some mod's". It is not: 88% of the
39 289 errors in the run of 2026-08-24 came out of
`reference/game/main_menu/localization/russian/`. Six shapes, all found by
`mods/ru_loc_fix/tools/locscan.py`: unclosed brackets (55 keys), accessors that
`dump_data_types` does not list (36 — `GetAdjectvive`, `GetGovernnment`,
`GerHerHis`), `Custom()` applied to the result of `GetName` (27), roots that are
nothing at all (10 — including `XXX` left in by a translator), a filter string
quoting another key (6), and wrong scopes the game named itself (14). Before
blaming a mod for a localization error, run that scanner.

**A `$OTHER_KEY$` reference inside a search-filter string loses the object.** A
filter's name and description are built once per object the filter selects, and
in that context a data function written inline resolves and the same data
function reached through a quoted key does not.
`CUSTOM_SEARCH_FILTER_LOCATION_RAW_GOODS_NAME` and `..._RAW_GOODS_DESC` sit four
lines apart, do the same thing two ways, and only the second one fails — every
time, 75 failed lookups per evaluation.

**Thirty thousand errors in one second destroys the log.** `error.log` rotates
at 1 MB and keeps five. Five filter strings produced 31 350 lines inside the
second the game started, which rotated it five times over: everything the game
had said before that second was gone before the player quit. When a log looks
suspiciously empty of everything except one repeated error, check the
timestamps at the head of each rotation — if they are all the same second, the
log is not telling you what happened, it is telling you what happened last.

**`Custom()` cannot be asked of a name.** `Country.GetName.Custom('CL_GEN')` is
27 keys' worth of the same mistake in the shipped Russian files: `GetName` has
already produced text and text cannot be promoted. The whole key fails to parse,
so the player sees nothing at all rather than an undeclined name.

**A GUI type can be real and appear nowhere in the English localization.** The
first version of the unknown-root rule compared against English strings alone
and accused twenty-five healthy keys, all using `UnitTypeLateralView`, which is
a perfectly ordinary type that no English string happens to mention. Check the
engine's `dump_data_types` before calling a name invented — the same rule that
applies to effects and triggers.

**`performance_degradation.log` has columns that identify a playset.** `GUI
widgets` at the first in-game sample, `Total number of Gfx units` and
`Total number of Trade wagons` are deterministic for a given bookmark and data
set — 37 768 / 449 / 843 for this playset at 1337_04_01, every single run. When a
run arrived that was supposed to be vanilla, those three columns said so without
anyone having to be asked: 36 977 / 448 / 713. Use them to confirm a run was
configured the way the report says it was.

**`performance_degradation.log` records the in-game date, which turns it into a
controlled experiment for free.** A row whose date equals the row before it was
taken while the game was paused. Splitting an hour that way said more than any
guess: paused and idle adds zero widgets, growth does not scale with game days
(103 days added 138 widgets, 125 days added 10 936), and it does not scale with
the unit count on the map. That ruled out map icons, unit markers and the tick
itself without asking the player to run anything.

**Three samples of a performance log cannot tell a leak from a warm-up.** The
first reading of `performance_degradation.log` had memory climbing 280 MB a
minute and concluded the game was heading for swap. An hour of the same log says
otherwise: the working set peaks at 14.7 GB and then falls under 7 GB. What
actually grows without limit is the GUI widget count and the frame time. Read the
whole run before naming a cause; the file is a few kilobytes and there is no
excuse.

**`Failed parsing localized text` in `gui.log` at frontend load says nothing
about the game.** Seventeen of them, all at one timestamp, sixteen seconds before
the mod's localization is merged — the frontend parses vanilla's value on the way
past. Check the timestamp against the `pdx_localize.cpp:257` lines that mark the
merge before believing that list.

**Fixing the loudest error is how you find the second loudest.** Five keys were
34 225 of 39 289 lines and hid everything else, including three keys with exactly
the same fault that had never once appeared in a log. There is no way to reach
those by reading files: nothing separates the ninety keys that reference a
declension helper from the ten that fail. Expect a fix of this kind to take more
than one round, and treat the second log as the point of the first fix.

**Closing a bracket turns a parse error into a scope error.** `lieutenancy_tt`
never rendered because of an unbalanced bracket; with the bracket closed it
renders, and now the two `Custom()` calls inside it can be seen failing on a
scope that is not a country. The fix was still right — but a key that starts
working starts reporting, and a rise in a different error is not automatically a
regression.

**A test the player physically cannot perform is a wasted round trip.** "Sit on
the map for five minutes without opening anything" is impossible in a running
game — events fire and demand a click. The owner said so, and he was right. Pause
removes events, the tick and map churn in one move, and every block after that is
attributable. Before asking for a protocol, walk through it as the person who has
to do it.

**"Report it to the developers" is not a deliverable.** This session established
that the widget leak is vanilla's, wrote the numbers up as a bug report, and
handed it over as the answer. The owner's reply was that he had known it was
vanilla the whole time and was asking for a fix, not a diagnosis. He was right
about that too: the diagnosis had ruled things out, but nothing had yet been
asked of the engine dumps about what a mod *could* do. Establishing whose fault
something is is the beginning of the work here, not the end of it.

**When a measurement is finished, say which questions it closed.** Five rounds of
tests produced ten settled facts, and the risk at the end of every session is
that the next one re-derives them and spends the owner's evenings doing it. The
table in [`SETTLED.md`](../SETTLED.md)
exists for that; add to it rather than writing a new narrative each time.

## Разметка и значки: `#`, а не `§`, и галочка — это текстура

**Файл локализации несёт UTF-8 BOM, и каждый ключ — один ведущий пробел.**
Без них файл не читается вовсе или теряет первый ключ, и молча.

**Цвет в этом движке — `#Y текст#!`.** `§Y…§!` — разметка прошлого поколения и
печатается буквально: в русской локализации игры **660 `#Y` и ни одного `§`**. В
`where_to_produce` их было **100**, включая жёлтое число закреплённого товара.
Ни строки в логах.

**`✔` вернулся с экрана пустым квадратом — но вывод «игра их не рисует» был
неверным.** Владелец показал сторонний мод с нормальными значками и сказал
«думай». Игра рисует их **текстурой**: своим контекстным меню через
`flats/accept.dds`, чекбоксом через `checkbox_round.dds` с `frame_grid = { 2 1 }`,
а любой мод может объявить `texticon` поверх текстуры и вставлять его как
`@имя!` — так работают `@clay!` и товарные значки этого мода.

**Правило.** Символ, который есть в локализации игры, рисуется — `×` и `−` там
есть, поэтому кнопки пикера живы. Символа, которого нет, может не быть в шрифте:
**не подбирайте следующий, берите текстуру или виджет.** Оба случая ловит
`check_script.py` → `localization_markup`, и замеры под правилом — в его
docstring.

**И самое дорогое здесь — не движок, а мы.** Про `§` **уже знала предыдущая
сессия**: в `bag_wtp_plan_window.gui` стоял комментарий «coloured the word with
`§Y...§!`, which this widget prints literally». Верно — и записано **только в
комментарии внутри `.gui`**, где его не находит ни `kb.py`, ни `code.py`, и где
оно читалось как особенность виджета, а не правило движка. Через несколько
сессий ошибка вернулась сотней ключей. **Правило, живущее в комментарии рядом с
местом ошибки, будет нарушено снова.**

**И вывод об отсутствии — самый дорогой из всех.** `reference/` неполно: в нём
нет ни текстиконов игры, ни половины её типов виджетов (`button_regular` работает
и используется 114 раз, а объявления нет). «Не нашёл здесь» и «не существует» —
разные утверждения.
