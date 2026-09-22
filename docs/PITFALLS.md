# Pitfalls

Mistakes already made here, each with the symptom that gave it away. Every one
cost at least one round trip through the game: none of them raises an error you
would notice.

**«Возьми этот инструмент» — это `cp` и замена префикса, а не новый код**, и
«соберём заново по подобию» оплачивается его прогонами:
[`archive/wtp2_failed.md`](archive/wtp2_failed.md), 2026-09-12.

**Мод с неполным `metadata.json` лаунчер не показывает вовсе**, и не говорит
почему. Дважды: 09-20 у `marker_throttle` не было `game_custom_data`, 09-22 у
`nmt_ru` — `relationships` (у части модов он пустой, `[]`, но он есть).
Оба раза мод собрался, прошёл все проверки и просто отсутствовал в списке.
**Поэтому требуется не «то, без чего точно не работает», а весь набор ключей,
который везут работающие моды** — лаунчер про причину молчит, и дешевле
повторить чужой файл целиком. Сверяет `tools/check_script.py`.
**Запасное значение настройки — не запасное, если настройку некому выставить.**
2026-09-19 `cm_maps` вернул с прогона чёрные области на карте губернатора и
подсказку над ними, велящую выставить «Исчерпывающую» точность поиска — настройку,
которой в моде нет. Порт сознательно переписал авторскую единицу на тройку,
«потому что тройку видит игрок CM»: игрок CM её видит потому, что **может
подвинуть ползунок**, а здесь страницы настроек нет и тройка — единственное
значение. **Перенося значение по умолчанию из мода, у которого есть настройки, в
мод, у которого их нет, проверяй не «что видит их игрок», а «что делает это
значение, когда изменить его нельзя».**

**Переменная на провинции не переживает смену владельца.** Провинция в EU5 —
срез определения провинции **по владельцу** ([`research/map_modes.md`](research/map_modes.md)):
земля переходит — игра делает новые срезы, и новый срез не несёт ни одной
переменной, записанной на старый. Локация — объект на всю партию, и её
переменные живут. 2026-09-19 карта городских прав `cm_maps` именно поэтому
красила дальше (цвет читается с локации) и показывала пустую подсказку
(покрытие читалось с провинции), причём **не сразу, а спустя часы игры**. Проход
стоял за клеймом и второй раз сам не шёл. **Долгоживущее держать на локации; если
объём гонит на провинцию — класть туда метку и пересчитывать срез без метки.**

**И к этому — как эту причину нашли, а до того не нашли.** Первая догадка была
названа из кода за один вечер и оказалась не той. Отличала их **форма жалобы**:
«ломается спустя время» не объясняется ничем, что решается один раз на загрузке.
«Сразу» и «потом» — разные болезни, и спрашивать об этом надо прежде, чем читать
код. А починка, которая спрашивает «лежат ли тут данные» вместо «почему они
пропали», верна и тогда, когда причина названа неправильно.

**Молча не работает — сперва
[`pitfalls/how_to_fix.md`](pitfalls/how_to_fix.md)**, порядок действий, и только
потом этот список: правило, применённое не к тому случаю, стоило пяти сборок.

**«Игра этого не умеет» — почти всегда значит «я искал не в том дампе».**
2026-09-14 стоящее здание было объявлено недостижимым для мода после обыска
`Location.*` и `Country.*` в поисках **интерфейсной** двери; дверь оказалась в
скрипте (`Scope.GetBuilding`, `data_types_script.txt`) и в собственном окне
этого мода, где та же форма работает для `BuildingType`. Владелец не поверил и
был прав. **Прежде чем называть что-то невозможным: (1) все пять дампов, не
один; (2) чем скрипт отдаёт объекты интерфейсу; (3) что уже умеет своё же окно.**

**А дальше — что три сборки по этому следу всё равно ничего не поставили**, и
попытка снята целиком:
[`archive/wtp_vanilla_autoexpand_attempt.md`](archive/wtp_vanilla_autoexpand_attempt.md).
Найденная дверь и работающая функция — разные вещи.

These subjects outgrew this file and have their own, which `tools/kb.py`
searches like everything else:

- [`pitfalls/localization.md`](pitfalls/localization.md) — declensions,
  `customizable_localization`, `$NAME$` references, markup that renders as
  `ERROR:`, and the theory about culture tooltips that did not survive a run.
- [`pitfalls/reference_tree.md`](pitfalls/reference_tree.md) — what breaks when
  somebody else's mod updates under a generator.
- [`pitfalls/interface.md`](pitfalls/interface.md) — windows that draw outside
  themselves, skins that do nothing, view objects that resolve nowhere.
- [`pitfalls/diagnosis.md`](pitfalls/diagnosis.md) — how to find a fault that
  logs nothing, and how to spend a run on it rather than a guess. **Read it
  before proposing a cause for anything**: the four-theories episode is there.
- [`pitfalls/shipping.md`](pitfalls/shipping.md) — putting a mod out and getting
  it loaded: workshop tags, the app id, load order, `metadata.json`, and
  overriding somebody else's override.
- [`pitfalls/script.md`](pitfalls/script.md) — effects, triggers, values and
  variables: a trigger in the wrong scope, an operation a command does not have,
  a format a getter does not take, a predicate computed twice. **The longest of
  these lists, and the one this repository paid for most.**
- [`pitfalls/cmm.md`](pitfalls/cmm.md) — CMF and its macros: a call that fails
  silently, a list that loses its fifty-first row, a setting numbered from the
  wrong end.

## Never invent a name for something the game already names

**2026-09-01.** A session called `royal_masonry_rights` «масонская хартия» — a
name that exists in no game of his. Nothing had been invented but the name; his
game says «Права на каменные и стекольные работы», one grep away.

**Name a rule, building, good or right by its key or by the string the game
shows** — never by a translation, never by a smoother phrase. He cannot check
the code, so a name he cannot find costs him the whole report.

## Deciding what exists

**"No mod here uses it" is not "the engine lacks it".** Subsidies were declared
GUI-only after grepping vanilla's `common/`, CMF, Construction Manager and Glorp
UI and finding only `ToggleSubsidizeBuildings` in a `.gui`. The engine has
`set_subsidized` and `is_subsidized`, both in the building scope, and a feature
had already been redesigned around their absence. The game prints its whole API
— `python3 tools/api.py <name>` answers in a second, and
`reference/game/docs/` is where those dumps live. Ask it before concluding
anything is impossible.
