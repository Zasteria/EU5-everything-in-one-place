# Ошибки в скрипте: пара ценностей на месте советника

Вынесено из [`../pitfalls/script.md`](../pitfalls/script.md) 2026-10-31, когда
тот ушёл за бюджет. Ничего не отменено; короткое правило осталось там, здесь —
случаи, числа и всё, что не сработало. `kb.py` ищет здесь так же.

## Место советника помнит пару ценностей и после смены действия

**Скрипт её не снимает, и окно потом не может посчитать прогресс.** Место,
которому окно `select_societal_value` выбрало пару, хранит `societal_values=…`
и после `stop_cabinet_action` + `set_cabinet_action` другого действия; в
`debug.log` тогда «Promote 'SCOPE' returned nullptr» на `*_action_progress`
этого места, десятки строк в секунду, пока виден аутлайнер (130 тыс. за его
вечер 10-24, по одному действию за раз). Не снимают (hands-off 10-25): `actor`
в параметрах, `remove_from_cabinet` и обратно того же советника, месяц без
действия. Из 8 178 мест мира такое одно — ваниль при смене действия через своё
окно пару сбрасывает. `actor` игра хранит у всех мест (`params={ actor=… }`).
Своим окном тоже не вышло (10-25): `SelectCabinetAction(место, no)` из скрытого окна открывает
ванильный список, виджет в строке (`attribute_columns/cabinet_action.gui`) её находит
(`ObjectsEqual(InteractionTarget.GetCabinetAction.Self, …GetVariable(…).GetCabinetAction.Self)`),
но `SelectInteractionTargetGlue.OnLeftClick`, `…AndConfirm`, `OnMouseDown/Up`,
`SelectInteractionTargetView.Confirm` из `state` действие не меняют — им нужны параметры клика
(`on_action_with_params`). Работает своё окончание игры: снятое игрой действие пару стирает;
0.10.14 даёт игре снять его через свой `is_finished` в копии `change_societal_values.txt`.
Прогоны от лица игрока 10-25 (ниже): `is_finished` у ценностей игра не читает; `allow` по флагу
снимает действие, но пару **оставляет** (ошибки пошли); игровая автоматика «Совет» на месяц
ценности не трогает. Стирают пару только команда выбора действия — игрока в окне или ИИ страны.
**Клик с параметрами — как у Playmaker Cabinet Queue** (мастерская 3804621893, 10-26; у автора работало с 0.3.55, у нас не мерено): в строке списка скрытая кнопка 1×1 с двумя `action_tooltip` (`on_action_with_params = "[SelectInteractionTargetGlue.OnLeftClick]"` и `…AndConfirm`), строку отбирает `dynamicgridbox` с `datamodel = DataModelRepeatedItem(Select_int32(условие, 1, 0))`; `state` кнопки с `trigger_on_create` зовёт `OnMouseEnter(PdxGuiWidget.AccessSelf, SelectInteractionTargetGlue.GetObject)`, затем `[UIAction.OnLeftClick]` — щелчок по своему `action_tooltip`, параметры при нём.
**Действие из `country_interactions` без боковой панели не достать** (`rulers_toolkit` 0.10.3, 10-26): `Country.GetQuickDiplomaticActions` — только шесть быстрых (`WAR`, `CREATE_CASUS_BELLI`, `BUILD_SPYNETWORK`, `CURRY_FAVORS`, `PROFESS_TRUST`, `IMPROVE_RELATION`), `GetSpecificAction('sell_work_of_art')` нет; полный список — у `ForeignCountryView` и `DiplomacyMacrobuilderLateralView`, глобально из видов доступен лишь `GetEconomyView`. Ярлыки Playmaker тоже стоят внутри `ForeignCountryView`.
**`perform_diplomatic_action` не запускает действие державы мода** (`rulers_toolkit` 0.11.0–0.11.3, 10-26/27): `accept`, `accept` + `hidden`, `propose`, пустое действие без цены и условий от игрока и от ИИ — эффект ни разу, ошибок нет. Своё общее действие (`generic_actions`, `type = diplomacy` бывает) зовут `fire_generic_action` — CM и Playmaker так и делают (0.12.0 — проверка). Кнопку любого действия без панели даёт `scripted_action_tooltip` (`action_name`, `actor`, `parameter`), `generic_actions/readme.txt` — ход для брака, не мерен.
**Решение (0.11.0): своё задание без `societal_values`, с `country_modifier = { monthly_towards_<сторона> }`** —
пару движок хранит только у заданий с полем `societal_values`; модификатор задания он умножает на навык так же.
