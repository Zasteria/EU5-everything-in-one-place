# Next session: the job in progress

This file is the part that is live; history is in `docs/archive/`, and the
mods retired on 2026-10-03 are in [`archive/retired_mods.md`](archive/retired_mods.md). What has already been settled is in
[`SETTLED.md`](SETTLED.md); where each mod stands is [`STATUS.md`](STATUS.md).

## Патч 2026-10-01: моды подогнаны, в игре почти ничего

Что патч сломал и что сделано — [`investigations/patch_2026_10_01.md`](investigations/patch_2026_10_01.md).
Копии под бету (`cmf_dev_beta`, `cm_dev_perf`) ставятся **вместо** оригиналов;
что из них не было в игре — [`STATUS.md`](STATUS.md).

## The job: `mods.bat`, rebuilt 10-03 and never run

Four items ([`CONVENTIONS.md`](CONVENTIONS.md)), **no rebuild in it** — after a
reference update he pushes, `tools/refresh.py` is ours. Tried only on a mock
Steam folder. **Ask for** `mods.bat → 1`, `→ 2` and `mods.bat check`.

## Also waiting on the owner, all of it cheap

- **`mods.bat → 3 → 1` on his machine** — the 2026-08-28 files of Advanced Auto
  Build and Glorp UI are still missing here; it does **not** re-extract the game.
- **The panel-open bisect and the hover run** —
  [`investigations/panel_hitch.md`](investigations/panel_hitch.md),
  [`investigations/widget_leak.md`](investigations/widget_leak.md). **Do not
  design a different test until they have run.**

## Задача на будущее: подсказки по действию

**Его просьба 2026-09-22:** подсказки при наведении открываются по таймеру и
лезут отовсюду; закрепление он перевёл на колёсико, хочет и **появление** по
действию.

**Разобрано 09-22 в**
[`research/engine_reach.md`](research/engine_reach.md): режима «по действию» нет,
ванильную настройку мод не двигает, но своя клавиша ему доступна, а
`tooltip_enabled` принимает выражение — гасить по виджетам, форкая ваниль.

**Первый шаг:** клавиша плюс **одна** ванильная панель; прогон скажет, гаснет ли
подсказка совсем или остаётся пустая рамка. **Панель выбирает он.**

## Before asking him for anything

Read [`SETTLED.md`](SETTLED.md). And walk the protocol as the person who has to
do it: *"sit on the map and open nothing"* is impossible while events fire, which
is why everything is paused now. He cannot be asked to run a thing twice.
