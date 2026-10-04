# `cm_rio_patch` — brief

**Окна Glorp UI Río с крючками CM, которых в Río нет.** Как в 1.3: окна Glorp
несли все галочки CM, CM стоял перед Glorp. Río (Glorp под 1.4) потерял часть
крючков, этот мод их возвращает. Собирается генератором `cm_dev_perf`, руками не
писать:

    python3 mods/cm_dev_perf/tools/port_from_cm_dev.py

**Порядок в плейсете: CM Perf → Río → cm_rio_patch → glorpui_hints →
ru_loc_fix.** Без Río и без CM Perf не ставить.

Два файла — файл Río из `reference/` целиком плюс правки из
`mods/cm_dev_perf/tools/rio_patch/` и `_gate_vanilla_toggles`:

- `location_window.gui` — галочки CM автоеды и авторасширения RGO на кнопке
  RGO; при CM скрыты значок ванильного авторасширения RGO и все Alt+клик
  «Включить авторасширение» (RGO, здания, карточки районов).
- `production_lateralview.gui` — кнопка CM у построенного здания, ванильная
  галочка и её Alt+клик скрыты при CM.

**Río обновился → собрать заново** (после того как новый Río лёг в
`reference/`): иначе этот мод держит окна прежнего Río. Якорь не нашёлся —
сборка падает и называет файл. Находки `check_script` по этим файлам — сам Río.

С Río в плейсете в игре не был (10-04).
