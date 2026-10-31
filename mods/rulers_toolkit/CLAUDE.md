# `rulers_toolkit` — брифинг

**Сборник мелкой автоматики для страны игрока** (его решение 10-18: «не хочется
плодить микромоды»). «Помощник правителя» / «Ruler's Toolkit», id
`bag.rulers_toolkit`, префикс `bag_rtk_`, нужен CMF. Месячный такт один —
`bag_rtk_monthly` (`cmf_monthly_human_country_pulse`, только игрок), новая
функция дописывает туда строку.

## Командиры из правителей (работает на армиях, 10-18)

Как устроено (очередь, котлы армий и флотов, кого не трогаем) —
[`README.md`](README.md#командиры-из-правителей). Зонды `bag_rtk: month, peace
pass`, `bag_rtk: crown commander set`.

## Пленники

- **Выкуп после мира** (`bag_rtk_prisoners.txt`, в игре не смотрен): 1-го числа, как
  ванильный `ransom_prisoners_effect`.
- **В тыл** (`bag_rtk_safety`, ≤ 2 раз на отряд) **работает в игре 10-18**.
- **Генерала с пленных не снимаем** (его выбор 10-18); **своей точки и слияния
  скриптом нет** — [`rulers_toolkit_history.md`](../../docs/archive/rulers_toolkit_history.md).

## Творения (вкладка `art`, по умолчанию выкл.)

[`README.md`](README.md#творения). **0.12.7 (10-27) работает в hands-off:** своё общее
действие (`generic_actions/bag_rtk_sell_art.txt`, `fire_generic_action`); за такт игра
выполняет одно — следующую продажу зовёт эффект (`bag_rtk_art_chain`). Теги-копии
`rulers_toolkit-0.12.7`, `-0.11.0`, `-0.9.22`.

## Откаты, женитьба, мир

- **Напоминалка** (`cooldowns`, `tools/gen_cooldowns.py`): **строки не переставлять и не
  убирать** — галочка по номеру строки (`tools/cd_lists.json`). Не мерены галочка
  «Привлечь чужеземного» и зонды 0.6.5.
- **Женитьба** (`family`, выкл.): `marry_character` женит (10-20; потомки — 0.13.2).
  Династического брака скрипт не создаёт.
- **Дипрепутация работает в игре 10-20.** Шаблон мира (`tools/gen_peace.py`) в 0.9.3
  ничего не нажал; 0.9.4–0.13.4 не проверены.

**После патча:** `refresh.py` не зовёт `gen_cooldowns.py` и `gen_peace.py` — руками;
копию `gui/peace_offer_view.gui` — `tools/rebase_overrides.py`. Слияние нерегулярных
(`gui/bag_rtk_merge_driver.gui`) выключено с 0.9.18. Версии 0.6–0.13:
[`rulers_toolkit_0_6_0_13.md`](../../docs/archive/rulers_toolkit_0_6_0_13.md).

## Журнал

Все `debug_log` мода — под галочкой «Писать в debug.log» (вкладка «Командиры»,
глобальный флаг `bag_rtk_log`, `tools/quiet_logs.py`; генераторы оборачивают сами).

## Ползунки после войны (бывший `war_sliders`)

Как перенесено и 0.2.1 (чеканка в ноль после двух промахов) — [`README.md`](README.md).
**С War Sliders вместе не ставить.**

## Что не проверено

- Видит ли следующий шаг, что прошлый кандидат уже `is_general` (иначе один
  человек пройдёт по всем отрядам: 20 строк «set» за месяц).
- Котлы: делятся ли поровну или по размеру отряда, и считаются ли отряды без
  командира.

## Команды

    python3 tools/check_script.py mods/rulers_toolkit
    python3 tools/check_cmm.py mods/rulers_toolkit/in_game/common
