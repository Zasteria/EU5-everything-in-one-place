# Pitfalls

Mistakes already made here, each with the symptom that gave it away. Every one
cost at least one round trip through the game: none of them raises an error you
would notice.

**«Возьми этот инструмент» — это `cp` и замена префикса, а не новый код**, и
«соберём заново по подобию» оплачивается его прогонами:
[`archive/wtp2_failed.md`](archive/wtp2_failed.md), 2026-09-12.

**Запасное значение настройки — не запасное, если настройку некому выставить.**
2026-09-19 `cm_maps` вернул с прогона чёрные области на карте губернатора и
подсказку над ними, велящую выставить «Исчерпывающую» точность поиска — настройку,
которой в моде нет. Порт сознательно переписал авторскую единицу на тройку,
«потому что тройку видит игрок CM»: игрок CM её видит потому, что **может
подвинуть ползунок**, а здесь страницы настроек нет и тройка — единственное
значение. **Перенося значение по умолчанию из мода, у которого есть настройки, в
мод, у которого их нет, проверяй не «что видит их игрок», а «что делает это
значение, когда изменить его нельзя».**

**Гейт на группу — не разрешение метить каждого в ней.** Там же и в тот же день:
проход городских прав берёт определение провинции, если хоть у одной локации в
нём есть сырьё **или** бонус к выпуску, и метит **все** локации определения.
Покрытие считается на всё определение, так что сырьевая половина гейта никого не
метит зря; бонусная — метит. У такой локации все девять прав нулевые, кодировка
`round(score*1000)*10 + index` разрешает ничью нулей в пользу старшего индекса —
и локация красится осмысленным цветом под подсказкой с тремя пустыми списками.
Ошибка CM, унаследованная копией. **Нулевой результат надо не метить, а отдавать
ветке «нет данных»:** её текст уже написан и для этого случая верен.

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
