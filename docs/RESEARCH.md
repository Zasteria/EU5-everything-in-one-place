# EU5 modding notes

How EU5 modding actually works, learnt mostly by getting it wrong first. The
game ships no modding documentation, so everything here came from the game's own
files, from mods that already work, and from `error.log` after each attempt.

Split by subject, because a session rarely needs more than one of them: a
translation does not care how a CMM list is registered, and an interface mod
does not care what a `$vanilla_key$` passthrough is.

| | |
| --- | --- |
| **[`research/engine.md`](research/engine.md)** | What the engine gives a mod: how to ask it what exists, mod layout, why localization is code and the ways it fails to compile, what gates a production method, geography from script, and where the RGO bonus and the goods data live |
| **[`research/interface.md`](research/interface.md)** | The interface half of the same: which panel is which, list filters and what a filter trigger receives, view object scoping, what a scripted widget costs, and the game's own map selection — what it is made of and which parts of it a mod may have |
| **[`research/cmf.md`](research/cmf.md)** | Community Mod Framework: its hooks, Mod Menu settings, the list machinery that fails silently, and how Construction Manager's automation is put together for an addon to reach |
| **[`research/translation.md`](research/translation.md)** | Translating somebody else's mod: what the job is, what it costs, and how a localization breaks without a word |

Two things are worth knowing before opening any of them.

**The game prints its own API.** `-debug_mode`, then `script_docs` and
`dump_data_types` in the console; the dumps are in `reference/game/docs/`. Ask
them rather than inferring from what mods happen to use:

```
python3 tools/api.py set_subsidized       exact name, across every dump
python3 tools/api.py --find subsid        substring, anywhere
python3 tools/api.py --scope building     everything taking that scope
python3 tools/api.py --gui IsAvailable    GUI data functions only
```

That distinction cost real work once: subsidies were written off as
interface-only because nothing in `common/` used `set_subsidized`, and the
engine had it all along. What the dumps do *not* say is how something behaves,
or whether it does anything useful in a given scope. That still comes from
vanilla, from the reference mods, and in the end from a run.

**Versions are not written down here.** The owner refreshes `reference/`
whenever a mod updates; `python3 tools/refs.py` says what is in the tree. What
these notes describe was true of CMF 2.3.x and re-checked against 2.4.1, and
says so where a version matters.

The companion documents are [`PITFALLS.md`](PITFALLS.md) — the same knowledge
from the other end, as mistakes and the symptom each one showed — and
[`TESTLOG.md`](TESTLOG.md), which is what has actually been in the game.

## Почему `Building` нельзя подсунуть: скрипт не создаёт объекты движка

`Building` -- это объект в сохранении: локация, тип, уровень, ход
обживания, владелец и среди полей флаг авторасширения (93 функции на типе,
`Building.GetLevel`, `GetMaxLevel`, `GetIsFullyEstablished`, ...). **Ни скрипт,
ни интерфейс объектов не создают** -- у них нет конструктора вообще: они умеют
только сослаться на то, что движок уже держит.

* «Выдать `Building` всему в локации» -- `every_buildings_in_location` идёт по
  списку движка. Его можно прочитать, в него нельзя дописать. У CM он ровно для
  чтения: считает занятость стоящих зданий.
* «Подсунуть фейковую стройку» -- `Construction` такой же объект движка;
  `Location.GetCivilConstructions` читает очередь, а дописывает в неё только
  `construct_building`, то есть заказ.
* **Событийный таргет `building` существует** (`Input Scopes: location`,
  `Output Scopes: building`, `Requires Data: yes`) -- но это переход к
  существующей записи, а не её создание.

**Почему это не та стена, которую ломают мододелы.** Меняют две вещи: **данные**
(файлы, которые движок читает на загрузке) и **скрипт** (триггеры, эффекты,
значения, которые движок сам зовёт). Флаг авторасширения -- ни то, ни другое:
поле рантайм-объекта, о котором движок скрипт не спрашивает **никогда**.
Перехватывать нечего -- в этой точке наружу не выходит ничего.

**Как заказывает ИИ.** `ConstructScoreRanking` (`BuildModeGetConstructScoreRanking`,
`ExpandModeGetConstructScoreRanking`) -- движок строит список кандидатов,
`ConstructScoreItem` несёт `GetCostValue` и `GetEmployability`, посчитанные в
C++, и дальше зовётся та же внутренняя процедура, что и у кнопки игрока.
**Скрипта в этом пути нет ни в одной точке.** Единственное, что движок
спрашивает у скрипта, -- ворота самого здания (`allow`, `location_potential`,
`country_potential`); поэтому только они и нашлись рычагом, и поэтому же они
запрещают заодно игроку.

## «Объявить, что здание есть» нечем: здание -- это его уровень

**У игры нет состояния «здание есть, но его нет».** Существование здания -- это
его уровень: 0 значит «нет записи». Единственный объект, который существует при
нуле уровней, -- **стройка**, и создаётся она только заказом
(`construct_building`) либо прямой выдачей уровня
(`change_building_level_in_location`, то есть постройкой).

**Ванильная автоматизация тоже не творит здания из ничего.** Её стройки -- те же
`Construction`, что и у игрока: карта рисует их одним и тем же маркером и
различает только владельца (`Construction.GetCountry.IsPlayer`, `.IsEnemy`,
`.IsAllied` -- `map_markers_construction.gui`). То есть «как ванила строит с
нуля» = «заказывает обычную стройку и платит за неё». Особого пути 0 -> 1 нет
ни у кого.

**Поэтому и отметить нечего:** `IsAutoExpand` читает флаг **на записи**, а записи
до стройки не существует. Это не ограничение мода и не ограничение CM -- это
устройство: отмечать можно то, что уже заказано, и с этого мига -- да, ещё при
0/N.

## Ванильную автоматизацию стройки гейтит `allow` здания

**Автоматизация «Сооружения» строит с нуля**, и что ей можно строить, решает
скриптовый блок `allow` в самом `building_type`: он считается в скоупе локации и
закрывает **и ручную стройку, и автоматическую**. Проверено на живом примере:
`calidad_de_vida_eu5` переопределяет `forts.txt`, дописывая условие в `allow`,
и так запрещает автоматизации ставить форты в выбранных локациях.

**Чего нет:** весов в `building_types` (`ai_will_do` там не бывает -- только
`ai_forbid_shutdown`, `ai_ignore_maintenance`, `ai_unique_location_list`,
`ai_foreign_ignore_naval_range`), и модификатора-запрета стройки. Сам выбор
считает движок (`ConstructScoreItem.GetCostValue`, `GetEmployability`).

**Значит единственный способ направить ванильную автоматизацию -- сузить ей
выбор**, переопределив `allow` тех зданий, которыми она распоряжается.

## Автострой зданий: запись есть уже у стройки

**Галочку авторасширения ставит только интерфейс** --
`ToggleAutoExpandBuilding(Building.Self)`, `IsAutoExpand(Building.Self)`. Ни
эффекта, ни триггера для неё нет: проверено по полным `effects.log` и
`triggers.log`, а не по ключевому слову. Среди систем `set_automated_system`
постройки зданий тоже нет.

**Но `Building` достаётся не только из панели игры.** Здание **в стройке** уже
имеет запись, и до неё дотягивается любое окно, у которого есть локация:
`Location.GetCivilConstructions` -> `Construction.GetBuilding`. Обе формы --
ванильные (`build_location_lateralview.gui:1460`,
`map_markers_construction.gui:116`).

**Заказать стройку скрипт умеет**: `construct_building` в скоупе локации,
с `cost_multiplier`, `payer` и `instant = yes/no`. `change_building_level_in_location`
ставит уровень напрямую, `every_buildings_in_location` заводит в скоуп здания
(`building_level`, `building_max_level`, `building_levels_under_construction`,
`is_at_max_level`).

**Здание с потолком в один уровень галочки не получает** -- гейт по потолку,
а не по существованию записи.

**Но `construct_building` -- не та стройка, которой строит игрок.** Эффект
скрипта **не берёт особые валюты цены**; это написано у самого CM
(`cm_feature_effects.txt:194`), и поэтому CM заказывает стройку кнопкой движка
`BuildOrExpandBuildingDefault(BuildingType, Location)`. Точную цену называет
`GetBuildOrExpandBuildingCost(BuildingType, Location)` -- **CFixedPoint**, а
`...CostValue` -- строка.

**Дверь от локации к `Building` -- в скрипте, а не в интерфейсе.** Искать её
среди функций `Location` бесполезно: их там нет, а все четыре списка зданий в
игре (`LocationView.GetLocationBuildings`,
`LocationProductionView`/`ProductionView.GetBuildingItems`,
`LocationUpkeepWrap.GetBuildings`) висят на панелях, которые движок строит сам.
**Дверь -- `Scope.GetBuilding`** (`data_types_script.txt`): здание, положенное
скриптом в список переменной, читается датамоделью и достаётся из строки
`Building`-ом, ровно как `Scope.GetBuildingType` достаёт тип из `_row_builds`.

Скриптовая половина: `every_buildings_in_location` заводит здание в скоуп,
`save_temporary_scope_as` его сохраняет (так делает и CM,
`cm_misc_script_values.txt:102`), а тип здания спрашивается событийным таргетом
`building_type` (`Input Scopes: building`) -- форма ваниллы,
`scripted_triggers/building_triggers.txt:26`. **Так достижимо любое стоящее
здание**, не только то, что в стройке.

`Location.GetCivilConstructions` -> `Construction.GetBuilding` (с воротами
`Construction.IsBuilding`) остаётся вторым путём и нужен для здания, которое
ещё строится: про здание с нулём уровней `every_buildings_in_location` ничего не
обещает.

**Цена ошибки здесь уже заплачена**: 2026-09-14 сессия объявила стоящее здание
недостижимым, обыскав список функций `Location` и ни разу не спросив, чем скрипт
отдаёт объекты интерфейсу. Владелец не поверил -- и был прав.

**Как заставить интерфейс что-то сделать по списку, не платя кадрами.** Форма
CM, и она работает: скрипт пишет список, виджет с `datamodel` по нему рождает
строки, а `state = { name = X on_finish = ... }` срабатывает только когда кто-то
позвал `PdxGuiTriggerAllAnimations('X')`. Зовёт его состояние `_show` виджета,
чей `visible` читает флаг: флаг поставлен -- переход в видимость -- один проход.
**`_show` ловит переход, а не рождение**: виджет, родившийся уже видимым, молчит,
и на этот случай у игры есть `trigger_on_create = yes`
(`economy_lateralview.gui:333`). А **`visible` у самой строки -- это условие
действия**: строка, которой нечего делать, невидима и не срабатывает.

