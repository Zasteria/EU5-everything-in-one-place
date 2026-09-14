# Карта городских прав: что именно перенесено из CM dev

Вынесено из [`../investigations/wtp_town_right_map.md`](../investigations/wtp_town_right_map.md)
2026-09-14, когда тот ушёл за бюджет. Это опись переноса — какие файлы, какие
режимы и что переименовано; перенос закончен, и живая часть (расчёт, запуск,
открытые вопросы) осталась в исходном документе.

## Что именно перенесено

| у него | у нас |
| --- | --- |
| `cm_best_town_right`, `_refresh` | `in_game/gfx/map/map_modes/bag_wtp_town_right.txt` |
| `cm_town_right_map_mode_script_values.txt` | `script_values/bag_wtp_trmm_values.txt` |
| `cm_town_right_map_mode_effects.txt` | `scripted_effects/bag_wtp_trmm_effects.txt` |
| `cm_town_right_map_mode_triggers.txt` + `cm_atr_ur_has_no_specialization` | `scripted_triggers/bag_wtp_trmm_triggers.txt` |
| `cm_town_right_map_mode_custom_loc.txt` | `customizable_localization/bag_wtp_trmm_custom_loc.txt` |
| `cm_town_right_map_mode*_l_*.yml` | `bag_wtp_trmm*_l_{russian,english}.yml` |
| девять `cm_trmm_search_*` + двойники | те же режимы в том же файле карты |
| девять `cm_trmm_search_*.dds` | `gfx/interface/icons/map_modes/bag_wtp_trmm_search_*.dds` |

Переименование механическое: `cm_trmm_` → `bag_wtp_trmm_`,
`cm_best_town_right` → `bag_wtp_best_town_right`,
`cm_atr_ur_has_no_specialization` → `bag_wtp_trmm_no_spec`.

**Зависимостей у этого куска почти нет** — это и делает перенос честным.
Проверено сканом по шести файлам: наружу они смотрят ровно пятью именами, и три
из них принадлежат тому, что здесь не нужно (`cm_enable_auto_expand_*`,
`cm_building_type` — включение автостроя после выдачи грамоты; `cm_country` —
её скоуп).

**Девять детских карт взяты тоже** — его слово, 2026-09-14: «мне нужны и те
карты которые были внутри этой карты. Они как дети этой карты и их удобно
использовать, тащи их тоже.» Они `category = hidden`: во флайауте их нет, у него
в них ходили из панели выдачи грамот. Панели без CM нет, поэтому **вход наш** —
значок карты в строке грамоты на второй странице сводки, ванильным
`mapmode_tooltip_button`. Иконки режимов перенесены под нашими именами: файл
значка зовётся так же, как режим.

**Не перенесено:** панель выдачи грамот `cm_trmm_grant_*` и включение автостроя
`cm_trmm_enable_expands_*` — части CM, снятого с плейсета. Ключи локализации,
которые на них ссылались, убраны; всё остальное, включая семейство `cm_uright_*`
(под именем `bag_wtp_trmm_ur_*`), взято как есть — **его копия подсказки,
привязанной к `Location`, а не к корню окна**, и это ровно то, что нужно строке
плана.

