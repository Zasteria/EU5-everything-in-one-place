# Решение 2026-09-12: CM и Glorp UI убраны, и что мод у них брал

Вынесено из [`../investigations/wtp_backlog.md`](../investigations/wtp_backlog.md)
по размеру. Решение исполнено, автострой закрыт его же решением 09-14
([`wtp_vanilla_autoexpand_attempt.md`](wtp_vanilla_autoexpand_attempt.md)).

## Решение, из которого следует половина работы: CM и Glorp UI убраны

«Я решил полностью отказаться от CM и GlorpUI… Они оба снижают
производительность игры. Особенно сильно это делает CM. Поэтому переключатель
нашей автоматизации должен работать теперь не через CM, а через ванильную
систему автоматизации строительства.»

**CMF остаётся** — страница мода на нём, и он про него говорит отдельно
(«отдельную кнопку CMF»). Уходит `romaimperator.construction_manager`.

**Что мод берёт у CM сейчас** (измерено, `grep` по дереву мода): ровно две вещи.

| что | имя CM | где у нас |
| --- | --- | --- |
| галочки автостроя | `cm_auto_expand_registered_building_types`, `cm_auto_expand_excluded_building_types`, `cm_mass_auto_expand_building_types` | `bag_wtp_cm_apply` в `bag_wtp_generated_plan.txt` |
| пометка «житница» | `cm_auto_food_location_enabled` | `bag_wtp_is_granary` в `bag_wtp_generated_triggers.txt` |

**Ванильная замена автостроя — только из интерфейса, и это измерено.** В дампах
игры есть `IsAutoExpand( Arg0 )`, `ToggleAutoExpandBuilding( Arg0 )`,
`ToggleAutoExpandBuildings( Arg0 )`, `AreBuildingsAutoExpand( Arg0 )` и
`BuildInLocationLateralView.ToggleAutoExpandAllBuildings` — **всё это функции
GUI**. Ни эффекта, ни триггера с этим смыслом в дампах нет: `api.py --find
auto_expand` не находит ничего, кроме чужого `on_action` CM. Значит **отмашка
скриптом невозможна**, и наша кнопка обязана стать виджетом, который зовёт
`ToggleAutoExpandBuilding` на здании.

**И отсюда его единственная добавка**: «чтобы ещё не построенные здания всё так
же имели возможность включить для себя автоматизацию». Ванильная галочка висит
на `Building.Self` — на **существующем** здании; у непостроенного её нет.
Значит это наше: помнить намерение на локации и отдать его игре, когда здание
появится, либо строить первый уровень самим.

---

