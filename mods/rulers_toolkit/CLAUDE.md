# `rulers_toolkit` — брифинг

**Сборник мелкой автоматики для страны игрока** (его решение 10-18: «не хочется
плодить микромоды»). «Помощник правителя» / «Ruler's Toolkit», id
`bag.rulers_toolkit`, префикс `bag_rtk_`, нужен CMF. Одна вкладка CMF, по
группе на функцию; месячный такт один — `bag_rtk_monthly`
(`cmf_monthly_human_country_pulse`, только игрок), новая функция дописывает туда
строку. Кандидаты на перенос сюда: `war_sliders`, автоматика совета из
`assimilate_primary`, своё из `auto_marry`.

## 0.1.0 — командиры из правителей (10-18, в игре не была)

- **Мир:** армии от большей (`num_subunits`) получают командира из сословия
  «Правители» (`crown_estate`; по-русски игра зовёт его так): сначала
  правитель, потом по `mil`. Кандидат — `bag_rtk_crown_commander_candidate`:
  взрослый, не в совете, ничем не командует, `is_eligible_military_leader`.
  Армию, где командир уже из «Правителей», не трогаем. Наёмники, изгнанные и в
  бою — мимо. Флоты — галочка, по умолчанию выкл.
- **Война:** ничего, кроме одного: при «Генерал-правитель»
  (`modifier:ruler_must_be_commander_during_war`) правитель без отряда идёт на
  самую большую армию. Штраф `ruler_is_not_a_commander_during_war`
  (`auto_modifiers/country.txt`) не берётся, когда правитель ведёт свой отряд.
- **Зонд:** `debug_log` «bag_rtk: crown commander set» на каждое назначение и
  «bag_rtk: war, ruler put on the largest army».

## Что не проверено

- Видит ли `any_character` в следующей итерации `ordered_army`, что прошлый
  кандидат уже `is_general` (иначе один человек встанет на все армии по
  очереди и останется на последней).
- Что `set_as_commander` снимает прежнего командира без побочек.

## Команды

    python3 tools/check_script.py mods/rulers_toolkit
    python3 tools/check_cmm.py mods/rulers_toolkit/in_game/common
