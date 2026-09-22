# Test log

What has actually been in the game, and what it showed.

Only the player can run EU5, so a run is the scarcest thing this repository
consumes. Everything else here — the reference tree, the generators, the
checkers — exists to spend fewer of them. This file is where a run's result
stops being a remark in a chat and becomes something a later session can rely
on.

**A session writes the entry, not the player.** The player says what happened,
in as few words as they like; the session turns it into a row and commits it. If
a run is not written down, `STATUS.md` will keep calling something "untested"
long after it was tested, which is the same cost as not having run it.

## How to fill this in

One entry per run. What matters is the last two columns: what was expected, and
what actually appeared.

- **Date and mod** — and the base mod's version if the run was about a
  translation, from `python3 tools/refs.py`.
- **What was loaded** — the playset order matters for a localization mod, since
  the mod loaded later wins the key.
- **Expected / observed** — the whole point. "Nothing happened" is a result and
  belongs here.
- **`error.log`** — quote the line if there was one. It names the file and the
  line for GUI failures and script errors. An effect that never runs logs
  nothing at all, so "log clean" is itself worth recording: it says the failure
  is the silent kind and the next step is a `cmf_log`, not another guess.

**Do not ask for logs by default.** The owner said so on 2026-08-31 — a zip is
his time and the session's tokens both — and three loads running the answer was
"clean". Ask when something *did nothing* and the reason has to be either a GUI
error or a silent effect, when a crash or a load failure is in play, or when a
`cmf_log` was added for this run. A layout question, a number that looks wrong,
a filter that filters: the screenshot already says it.

## Runs

**2026-09-20, `marker_throttle` — два прогона, подход закрыт.**

**0.1.1, семь типов под тормозом.** Его слова: «отряды стали не кликабельными. Я
не мог никого из них выбрать, хотя сами значки визуально были. Их можно выбрать
если выделить область на экране мышью, но не щелчком». Скорость оценить не
успел. Значит `max_update_rate` на типе портит **попадание мышью**, а не только
числа: рисование идёт, рамочное выделение (оно у движка) идёт, щелчок мимо.

**0.2.0, три типа** — без кнопок, без `alwaystransparent = no`, без раскладки.
«Ничего не изменилось». Значит ломает **любой потомок значка**, а не только тот,
что сам ловит мышь.

**Вывод в [`SETTLED.md`](SETTLED.md), третьего захода не просить.** Мод оставлен
в дереве ради генератора и разбора, но **ставить его нельзя**. `max_update_rate`
остаётся настоящим рычагом — только для того, по чему не кликают, а этим уже
занят FUM.

**И до этого 0.1.1 в лаунчер не попал**: в `metadata.json` не было
`game_custom_data`. Правило вынесено в `tools/check_script.py`.

**2026-09-20, debug mode — что там есть на самом деле, и три его поправки.**

Прогон по кнопкам: `gui_editor` — **Unknown command**, кнопки UI Editor в этой
сборке нет. `gui.debug` включается. `UI Bounds` работает: обводит виджеты и под
курсором пишет файл и строку (`gui/outliner.gui:1178`, `gui/console.gui:29`,
`glorpUI_hud_topbar.gui:397`), Alt+ПКМ открывает файл, Alt+ЛКМ перебирает
виджеты. `Inspect` открывает инспектор страны: там **Script Variables, 2049
записей** на игроке, от `cmf_`, `cmm_`, `atd_`, `cm_`, `fum_`, `bag_wsl_`.
Вкладка скриптов **надолго вешает игру**, потом отвисает.

**Его три поправки, и все по делу:**

1. **Подсказки от мыши — мимо.** Он их отверг по опыту. Файл
   `00_tooltips.txt` действительно пишет `OPEN_DELAYED_TIME = 0.0f`, но поверх
   лежит настройка игры, так что сам по себе дефайн про его игру не говорит
   ничего. Версия закрыта.
2. **Форма нагрузки не та, что в таблице переписи виджетов.** Его опыт: большая
   война с сотнями значков отрядов роняет игру **сразу**, хоть только запусти; а
   тихое развитие с тысячей кликов по картам и странам вреда не приносит.
   «Ощущение, что виджеты интерфейса чистятся сами, а иконки отрядов
   складируются».
3. **Faster Universalis что-то с этим делает**, и его значки строительства
   мигают чужой картинкой при появлении новых.

**Пункт 3 привёл к находке.** `max_update_rate` — свойство виджета, тормозящее
пересчёт выражений. Игра ставит его один раз (`map_markers.gui`,
`inactive_widgets_storage`, `-2`), FUM — двадцать раз, и **ни разу на значке
отряда**: у него throttled парламент, рынок, пошлина, порт, династия и прочие
редкие, а `unit_marker`, `combat_marker`, `fort_marker`, `supply_depot_marker` —
нет. Мигание значков стройки — это и есть цена его `9999`. Отсюда
[`../mods/marker_throttle/CLAUDE.md`](../mods/marker_throttle/CLAUDE.md).


**2026-09-20, `gui.clearwidgets` — кандидат выбыл, и это его наблюдение.**
Команда **сама печатается в консоль время от времени**, и игре это не помогает.
Сходится с файлами: в `ui_library.gui:18261` это **кнопка закрытия окна UI
Library**, а не метла по дереву. Прогона на неё не просить.


**2026-09-20, `cm_perf` с правкой 5 — «субъективно стало лучше».**

Три часа, куча войн, нагруженная СРИ, все моды. Его слова: **«просадки в тиках
сократились, возможно сама деградация приблизилась к ванильной»** — иногда в
начале месяца и в конце, в середине хорошо. Первый час супер, второй терпимо,
третий «задушил сильно».

**Новое наблюдение:** галочка «максимизировать количество тиков» снова начала
давать разницу — небольшой прирост ценой нестабильного FPS. Раньше разницы не
было (это и был признак потолка, снятого правками 1–2).

Зонд `widget_probe` в сборке **не стоял**, поэтому секунд на месяц за этот заход
нет, и «лучше» — на глаз.

**Логи, 41 секунда `error.log` и 8 минут `debug.log`:**

- `cm_ae_ok` не упоминается **ни разу**. Правка 5 не ругается; живёт ли
  переменная, это не доказывает.
- **21 443 строки `debug.log` — одна и та же:** «Trying to access non-const
  context pointer from a const context for type `EconomyView`», ~45 раз в
  секунду, весь заход. Это **наш** `war_sliders`: драйвер `bag_wsl_driver.gui`
  нарочно всегда живой и держит два `datacontext = "[GetEconomyView]"`, один с
  живой датамоделью. Мод работает (война 09-17), но промот резолвится каждый
  кадр всю сессию.
- `gui.log` — только переопределения типов на загрузке, ничего покадрового.



**2026-09-20, CM и карта — его три наблюдения, и они об одном.** Не замер, а
то, что видно само: карта рекомендованных городских прав открыта и игра снята с
паузы — тики «супер медленно и подгружаются», закрыл карту — ускорились. То же
при множестве значков отрядов и при множестве значков строительства. Играет на
плоской карте, без 3D.

**Форма одна: счёт на объект, повторяемый на такте** — не пиксели. Разбор и
связь с панелями CM —
[`investigations/cm_performance.md`](investigations/cm_performance.md).

**И его претензия по делу**: предыдущий заход ушёл в ошибки локализации, которые
его сейчас не волнуют.


**2026-09-20, зонд и логи — секундомер работает, и в логах нашлась поломка
игры, которую чинит наш же мод.**

**Секундомер жив**: «по началу было 4-5 сек на месяц, потом… дошло до 7-9 сек…
минут 10-15 посидел» — **деградация вдвое, в числах**. Счётчики детей он
подтвердил бесполезными: это структура, а не утечка.

**Логи: 5310 строк `error.log` за 87 секунд**, самый частый источник — один
тултип игры:

| ключ | строк | что не так |
| --- | --- | --- |
| `BUILDING_TYPE_PROFIT_TT` | **362** | `LOCATION.GetRank.Custom('LR_PREP')`. `LR_PREP` объявлен `type = location` (`ru_EU5_custom_loc.txt:46422`), а ключ зовёт его с ранга. Чинится переписыванием на `LOCATION.Custom('LR_PREP')` — **сделано в `ru_loc_fix`**, 209 ключей вместо 207 |
| `longname_ru_GEN` на стране | **668** | суффикс с `parent = country_ru_flavor` (`ru_EU5_custom_suffix.txt:3926`), а зовут его прямо со страны — и сама игра тоже. Правильной формы не знаем |
| `MARKET_SURPLYS_INFO`, `GOODS_PRODUCED_IN_LOCATION_MARKET_TRIGGER` | по 15 | **наша починка второго круга не сработала**: `GOODS` там не резолвится и развёрнутым |

**Что это стоит в скорости, не измерено**, и утечку не объясняет.


**2026-09-19, `widget_probe` — перепись корня закрыта, кнопка уничтожения
работает, профайлер мёртв.** Вынесено:
[`archive/testlog_widget_probe_0919.md`](archive/testlog_widget_probe_0919.md).

**2026-09-19, CM и скорость — он описал форму, и она не та, под которую я
правил.** Его слова: «Я тебе хоть раз жаловался, что ежемесячный пересчёт —
долгий? Нет… Основной паттерн: идёт пересчёт месячный, потом первые пару игровых
дней очень замедленны (будто бы игра что-то ещё досчитывает), потом идёт разгон
постепенный до нормальной скорости… к 8-10 дню скорость полностью
восстанавливается. И всё бы ничего, но с течением игры срок медленного
начального тика дней становится длиннее, разгон тоже», пока медленное не
занимает весь месяц. **Лечится перезагрузкой.** Без CM то же жирное сохранение
4 эпохи — «просто молния скорость».

| что это исключает | почему |
| --- | --- |
| месячный пересчёт как причина | он «не особо отличается от базовой игры» — его прямые слова |
| правка 4 (пульс раз в три месяца) | целилась в пересчёт, а не в то, что болит. **Выключена по его слову в тот же день: «верни ежемесячную».** Месячный пульс не трогать |
| что растёт в сохранении | перезагрузка лечит, а сохранение то же — значит растёт **в процессе** |

**Названный механизм** — слив очереди зовёт `PdxGuiTriggerAllAnimations`,
глобальную функцию, обходящую всё дерево виджетов, кругами; цена = длина очереди
× число виджетов в процессе. С файлами и строками:
[`investigations/cm_performance.md`](investigations/cm_performance.md). **В игре
не проверен**, и проверку через режимы карты он делать отказался — мерить должен
зонд, поэтому в нём теперь секундомер месяца.


**2026-09-19, `widget_probe` — первый прогон зонда** (дерево над окном мелкое,
профайлер мёртв). Вынесено:
[`archive/testlog_widget_probe_first.md`](archive/testlog_widget_probe_first.md).

**2026-09-19, `cm_maps`, два прогона — карты рисуются; губернатор починен, права
чинились дважды.** Первый заход: «Две карты — подбор городских прав и размещение
губернатора глючат. Некоторые области для гор. прав просто ничего не показывают,
хотя дают цвет и окно, но описание пустое… Некоторые области чёрные, мод говорит
про какую-то настройку поиска, он не может отсканировать всю державу иногда.»
Второй, после правок: «Карта губернатора пока работает как надо. А вот с
городскими правами ты чёт херню сморозил… Есть провинция, в ней ТОЧНО есть разные
ресурсы… Причём возникает это спустя время игры или сохранений. В начале он может
показать все провинции правильно, а потом какие-то провинции сломались.»

| что | что вышло |
| --- | --- |
| карты вообще загрузились и рисуют | **да** — первое подтверждение, что порт живой |
| `error.log`, `gui.log` | **от мода чисто**: ни одного `bcm_`. Всё чужое |
| «Рекомендуемый губернатор», чёрные области | причина — наша правка; **после возврата точности на 1 работает как надо** |
| «Рекомендуемые городские права», пустые описания | **ломается не сразу**: сначала всё верно, потом часть провинций перестаёт показывать что-либо, и сырьё у них есть |

**Чёрные области — наша правка, а не игра.** Порт переписал авторскую
`bcm_pf_accuracy_value` с 1 на 3, «потому что тройку видит игрок CM». Видит,
потому что **может подвинуть ползунок**; здесь страницы настроек нет, и тройка —
единственное значение, а уровни 2-5 часть локаций не оценивают, красят чёрным и
шлют игрока в несуществующую настройку. Вернули единицу. **Подтверждено прогоном.**

~~**Первая догадка про пустые описания** — гейт прохода метит локации в
определении, прошедшем только из-за чужого бонуса к выпуску, ничья нулей уходит
старшему индексу.~~ **Снято в тот же вечер:** она была названа из кода, не
измерена, и не объясняет ни «сырьё точно есть», ни «ломается спустя время».
Правка откатана — цена одной догадки вместо зонда.

**Настоящая причина — в форме ответа.** Покрытие хранится на **провинции**, а
провинция в EU5 — срез определения **по владельцу**
([`research/map_modes.md`](research/map_modes.md)). Земля меняет хозяина — игра
делает новые срезы, и новый срез не несёт ничего из записанного проходом.
`bcm_trmm_best_idx` лежит на **локации** и это переживает, поэтому карта красит
дальше, а подсказка пустеет; проход стоит за клеймом и сам второй раз не пойдёт.
Ошибка есть и у самого CM.

**Починка не зависит от того, права ли догадка.** Каждый записанный срез несёт
метку `bcm_trmm_cov_v`; `bcm_trmm_repair` пересчитывает определения, у которых
есть срез без метки — вопрос «лежат ли тут данные», а не «почему пропали». Гонит
его драйвер в `bcm_pf_map_mode_window.gui` при входе в семейство режимов прав,
ровно тогда, когда данные собираются читать; ворота драйвера побайтно те же,
которыми решает показаться панель поиска. К правкам — одноразовая миграция за
`bcm_pf_epoch` в `bcm_run_lobby_setup`: она снимает `bcm_trmm_stamp` и
`bcm_pf_fresh_g`, иначе начатая партия осталась бы со старыми данными.
**Сама починка прав в игре не проверена.**

**Прогоны `cm_perf` 2026-09-18** (деградация за 20 минут; месячный ритм и
первые два захода) — вынесены:
[`archive/testlog_0918_cm_perf.md`](archive/testlog_0918_cm_perf.md); две
просадки скорости, накопительная и месячная, обе закрыты —
[`archive/testlog_cm_perf_0918_slowdowns.md`](archive/testlog_cm_perf_0918_slowdowns.md).

**Прогоны 2026-09-09 — 2026-09-14** (`where_to_produce`, `glorpui_hints`,
ванильный костыль автостроя) — вынесены:
[`archive/testlog_0909_0914.md`](archive/testlog_0909_0914.md).

## Waiting on a run

The next session should start here rather than designing anything new. All of
these are prepared, all are cheap, and the owner has agreed to the hover one.

**`where_to_produce`, twenty-eighth load.** Four small things and one question,
all of it one glance with the results window open. Not worth a run of its own.

1. **Any market can be taken now**, the neighbour's included — the list is every
   market in the world, framed by the ticked continents. Hover a market you hold
   nothing in and it should outline and click like the rest.
2. **The four picker buttons look like «Очистить выбор»** — solid, not
   transparent. Same in the rights window.
3. **The corner above the +/- buttons has a «+» in it** and «№» has not moved.
4. **«Восточная Мунтения» does not touch «Валахия»**, «Трансильвания» does not
   touch its percentage, and the row is four pixels narrower than it was.
5. **The one question: «Из чего».** The header and the row are identical column
   for column in the file, so if the icons still sit right of the heading, the
   cause is a constant inset the rows carry and the header does not. **What
   settles it in one look:** does «Сейчас» sit exactly over its percentages? If
   yes, the drift starts somewhere in the middle and I have the wrong model of
   it; if «Сейчас» is *also* slightly left of its numbers, every heading is, and
   `margin_left` is the one number to move.

**The panel-open bisect — five minutes, no log to read.** Reported 2026-08-25:
any tab opens instantly in vanilla and with a hitch, sometimes a freeze, under
the playset — *on a save loaded a minute ago*, so it is not the widget leak.
Counted from the files already; the candidates and the numbers are in
[`investigations/panel_hitch.md`](investigations/panel_hitch.md).
The playset is 22 workshop mods, 17 of them touching `in_game`
(`python3 tools/playset.py <logs>` reads it out of `debug.log`), so this is a
bisect: same save, same three panels (country, diplomacy, a location's build
panel), halving the `in_game` mods until the hitch is cornered — four or five
loads of a minute each. Worth trying **Construction Manager** and
`rgo_bonus_filter` first, in case they save the bisect. No log, no timing — the
owner's own sense of the hitch is the measurement, because the difference he
describes is one anybody can feel.

Advanced Auto Build was the first version's headline and it was wrong: the owner
does not run it. Its `3781437488` is mounted in the 2026-08-24 log, so if it
turns out to be enabled and merely unused, that still costs — a scripted widget
is instantiated whether it is opened or not.

**The hover test, and the tooltip settings with it.** One session, one save,
paused throughout. Two minutes sweeping the mouse over the map and top bar with
**no clicks**; then Settings → Tooltip Settings with `Map Tooltips` set to
Disabled and both delays at maximum; then the same two minutes again. Send
`performance_degradation.log`. What each outcome means is in
[`investigations/widget_leak.md`](investigations/widget_leak.md) — read it
before asking for anything else, because the losing branch has its own next test
already written and it is not this one repeated.

~~**`ru_loc_fix` round two — eleven keys and four expansions, never in game.**~~
**Confirmed 2026-08-27** from the logs drop above: none of the six keys appears
in `error.log` any more.

**And one thing only eyes can check.** Whether the repaired Russian *reads*
correctly. The log says those keys no longer fail; it does not say the sentences
are right. Quickest look: a religion tooltip (harmony, purity, honor), the goods
filter chips in a location's buildings panel, and the price line in the build
panel.

## Never run

Kept here so it is one list rather than scattered through prose:

- whether anything in `goods_target` runs on a monthly pulse. Its lists,
  readings and ticks are confirmed on screen; nothing periodic is.
- `rgo_bonus_filter`'s build-panel chip. Его же **панельная пара чинилась**
  2026-09-09 по чужой причине: она читала `root`, и это была та же
  ошибка, что у `where_to_produce`.
- ~~**`where_to_produce`'s «В конце» plan.**~~ **Run 2026-09-03**, three times.
  What is still never run is **the whole plan on a large ground since the
  ladders were rebuilt**: Westphalia is 48 locations and its answer came back
  identical to the old build's, so nothing there tests the change. The press
  that would is the one of the earlier report — northern Germany, 233 locations,
  where the open pass used to place 271 buildings of 770.
- Everything `nd_ru` has translated apart from Westphalia — 3 600 keys that have
  never been on screen.
- ~~**All of `cm_maps`**, built 2026-09-15~~ — **loaded 2026-09-19**, and both
  the urban-rights and the governor mode drew. What is still never run is the
  **food-potential map**, the icon strip, and the two 2026-09-19 fixes
  themselves.
