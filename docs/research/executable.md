# Что знает сам `eu5.exe`: консоль, параметры запуска, профилировщики

**2026-10-20, впервые с доступом к его компьютеру.** Строки из
`binaries/eu5.exe` (сборка Steam 25905365 от 10-13, та же, что в `reference/`):
`strings -n 5 eu5.exe`, полмиллиона строк. Имя команды стоит в exe рядом со своим
описанием. **Всё ниже названо самим exe, но в игре не пробовано**: работает ли
команда в обычной сборке, скажет первый же ввод в консоль.

Повторить: скопировать exe с его машины и `strings -n 5 eu5.exe | grep -n -x <имя>`,
описание лежит в соседних строках.

## Профилировщики, которых в репозитории не было

| что | как зовётся | что даёт |
| --- | --- | --- |
| профиль скриптов | консоль `Script.Profiling.Start`, `…Stop`, `…Dump`, `…DumpAll`, `…Restart` | `logs/profiling.csv` и `logs/profiling_roots.csv`; «Captured {} samples over {} s ({} frames, {} ticks)» |
| окно профиля скриптов | консоль `Script.Profiling.Gui` | `gui/script_profiler/script_profiler.gui`, построчно по файлам |
| профиль данных интерфейса | консоль `Tools.GuiDataProfiler` | окно: «Only Script», «Frame %», «Longest Duration», «Calls List», «Widget Tree» |
| время задач тика | параметр запуска `-profile_ticktasks` | «Stream per-tick task timings to profiling.log and dump an aggregated summary to docs/ticktask_profiling.tsv on shutdown» (путь в его папке игры) <!-- check-docs: ignore --> |
| подсветка тяжёлых данных | консоль `GUI.Debug.HeavyData` | рядом с `pdx_gui_data_context.cpp` |
| частота обновления данных окон | `GUI.DataUpdateDelay`, `GUI.MaxSpeedDataUpdateDelay` | второе лежит среди строк верхней панели; что принимает — не проверено |

Старая строка в [`engine.md`](engine.md) «`ScriptProfilerGui` не достать» верна
только про кнопки тулбокса: консольная команда для него есть.

Ещё консоль: `GUI.ClearWidgets <окно>` (он ею пользуется), `GUI.CreateWidget`,
`GUI.Debug.DrawUnderMouse`, `Ecs.Stats`, `Tools.LogViewer`, `Log.ClearAll`,
`Benchmark.EnableWidgetChurn` — **у Paradox в этой сборке свой стенд утечки
виджетов** (`widget_churn_benchmark.cpp`); см.
[`../investigations/widget_leak.md`](../investigations/widget_leak.md).

## Параметры запуска (`game_commandline.cpp`)

- `-force_text_save` — «Force the savegames to be in text mode». Обычный сейв —
  zip из `gamestate` (двоичные токены) и `string_lookup`; без таблицы токенов его
  не прочесть, текстовый читается как скрипт. Так проверяется, что сделал мод
  (браки, переменные), без его глаз.
- `continuelastsave`, `loadsave`, `loadsavehandsoff` (`frontend_idler.cpp`,
  описаний рядом нет, что это параметры запуска — вывод по соседству) —
  сразу в сохранение, без меню.
- `-handsoff`, `-timed_handsoff` («for a set amount of months»),
  `-handsoff_save_at_dates "1350|1437.03.31"`, `-observe` — игра идёт сама.
- `-skip_flatmap_generation`, `-skip_checksum`, `-benchmark`, `-validate_gs`.
- `-force_serial_tick_tasks` — задачи тика последовательно, не параллельно.
- `-debug_mode` — то же, что команда консоли.

## Прогон от лица игрока (10-25)

`-loadsavehandsoff` отдаёт страну ИИ: тот снимает задания, запрещённые ему
(`forbid_for_automation` — ценности), и меряет не то. Обычный `-loadsave=<сейв>`
даёт страну игроку, но встаёт в лобби и на паузу. Скрытые виджеты (в окне,
которое есть всегда, например `bag_asp_hidden.gui`) это снимают:
`[StartLobbyGame]` по `IsGamePausedByGame`, `[OnPause]` + `[OnIncreaseGameSpeed]`×4
по `IsGameUserPaused`; события — виджет в кнопке варианта `eventwindow.gui`
(`[EventOption.Select]` по `EventWindow.GetLockableInfo.IsUnlocked`), но не все
(событие `dynastic.14` вешает прогон). **Обычная загрузка пишет автосейвы под
именем партии** — грузить копию сейва под другим именем и помнить, что его
автосейвы перезапишутся. Выключать — `timeout N eu5.exe …`. Его время: строка
в тред до и после каждого прогона.

**10-26, CM:** для проверки автоматики CM прогон от лица игрока не нужен — **в `-loadsavehandsoff` CM работает** (циклы, одобрения, зонды пишут) и ничего не стопорит. `-timed_handsoff=36` дал около 1.5 года игры за 2 минуты. Временный автопилот для `-loadsave` (скрытое окно со `StartLobbyGame`) в выборе державы не сработал, окна сообщений его виджет не закрывает.

## Что ещё есть на его машине и чего нет в `reference/`

- `clausewitz/` и `jomini/` из папки игры — движковые окна инструментов
  (`profiler.gui`, профили ввода), в `game_files_manifest.txt` не входят.
- Его живые логи: `performance_degradation.log` (виджеты, память, время кадра
  за сессию), `error.log`, `debug.log`, и сейвы.
- Копии наших модов в `Documents/.../mod/` — **10-20 там `rulers_toolkit` 0.7.4**,
  когда в main уже 0.7.5: что в игре, видно прямо, без вопроса ему.
