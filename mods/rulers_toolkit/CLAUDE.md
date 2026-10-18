# `rulers_toolkit` — брифинг

**Сборник мелкой автоматики для страны игрока** (его решение 10-18: «не хочется
плодить микромоды»). «Помощник правителя» / «Ruler's Toolkit», id
`bag.rulers_toolkit`, префикс `bag_rtk_`, нужен CMF. Одна вкладка CMF, по
группе на функцию; месячный такт один — `bag_rtk_monthly`
(`cmf_monthly_human_country_pulse`, только игрок), новая функция дописывает туда
строку. Кандидаты на перенос сюда: `war_sliders`, автоматика совета из
`assimilate_primary`, своё из `auto_marry`.

## Командиры из правителей (работает на армиях, 10-18)

Как устроено (очередь, котлы армий и флотов, кого не трогаем) —
[`README.md`](README.md#командиры-из-правителей). Зонды `bag_rtk: month, peace
pass`, `bag_rtk: crown commander set`.

## Пленники

- **Выкуп после мира** (`bag_rtk_prisoners.txt`, в игре не смотрен): 1-го числа в мире, как
  ванильный `ransom_prisoners_effect`. Зонд `bag_rtk: prisoners offered for ransom`.
- **Генерала с пленных не снимаем**: «Замена генералов» ставит нового сразу,
  выключается только на всю страну; он выбрал оставить (10-18).
- **В тыл** (`move_prisoners_to_safety = {}` работает, 10-18): не больше двух
  раз на отряд, переменная отряда `bag_rtk_safety` — первый раз из
  `on_battle_won`/`on_overrun_imprisoned` или 1-го числа, второй — 1-го числа,
  когда `is_moving = no`. **В игре 10-18: работает** (после боя, затем 1-го числа).
- **Своей точки и слияния скриптом нет** — чем проверено:
  [`rulers_toolkit_history.md`](../../docs/archive/rulers_toolkit_history.md).

## Творения (0.4.1, в игре не было; вкладка `art`, по умолчанию выкл.)

`bag_rtk_art.txt`: 1-го числа, пока `num_of_diplomats` > «оставлять», до 5
продаж — самое дорогое творение отмеченной ступени (8 галочек, ступени из
`artists_l_russian.yml`) — державе с наибольшим `bag_rtk_art_accept` (ванильная
формула, сверена с его скрином) и `gold >= art_price`. **`fire_generic_action`
действие державы не берёт** (0.4.0, 10-18) — продажа повторена в скрипте:
`add_gold`, престиж −2 %, `add_diplomats = -1`, `move_art_and_owner`. Зонды
`work of art sold` / `not sold` / `no buyer for any work of art`.

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
