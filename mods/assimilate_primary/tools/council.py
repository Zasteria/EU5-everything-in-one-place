"""The mod's own council automation: CMF page, lists and the monthly pass.

His ask 12.10: a checkbox turns on our automation; every so often the seats get
actions, picked down a priority list he orders in CMF. Common actions only,
nothing country-specific and nothing as pointed as settling the frontier. Two
lists: «Доступные» (every pool action this country can see, a checkbox puts it
in use) and «Приоритет» (the actions in use, in the order they are tried).

His run 12.10: seats he had given other actions kept them with integration on
top of the list. So the pass owns every seat: on the checkbox and every `review`
months each action down the list keeps the seats already on it and then takes
free ones, the advisor best in its skill first; a seat left over keeps what it
had. Between those, every `period` months only empty seats are filled.

What is copied from the game rather than written here: each target's validity
is the action's own `visible` and `enabled` from its `select_trigger`, pasted
into the search, so a target the game would grey out is never picked. The order
in which targets are tried, and the gates in POOL, are this file's guesses at
vanilla (the game scores 62 of 74 actions inside the engine).

Not measured: whether `set_cabinet_action` takes every target flag by its name
(vanilla calls it with `target` only, `on_action_effects.txt:290`), and whether a
finished action empties its seat by itself. The debug.log lines say both.
"""

from __future__ import annotations

import re

import alert_banner  # tools/, put on sys.path by generate.py
import value_window
from pathlib import Path

MOD_ID = "bag_asp"

# The pool, in the default priority. kind decides how a target is found:
#   country   no target
#   province  ordered_province over the country, order_by below
#   area      the area of an ordered province
#   capital   the capital's province (vanilla's own AI pick for develop_province)
#   culture   promote_culture: primary culture, province by population
#   religion  promote_religion: state religion, province by population
#   estate    an estate, least satisfied first
#   values    a societal value pair, by the list of «Тонкие настройки»
# gate: extra country-scope condition for picking it; the game's own allow is
# checked anyway through is_available_for.
POOL = [
    ("integrate_province", "province", "INTEGRATION", ""),
    ("integrate_area", "area", "INTEGRATION", ""),
    ("reduce_war_exhaustion", "country", None, ""),
    ("stabilize_country", "country", None, "stability < 50"),
    ("increase_control_province", "province", "province_tax_base", ""),
    ("increase_control_area", "area", "province_tax_base", ""),
    ("send_secret_royal_inspectors", "province", "province_tax_base", ""),
    ("promote_culture", "culture", "HALF", ""),
    ("promote_religion", "religion", "population", ""),
    ("pacify_population", "province", "population", ""),
    ("recovery_effort", "province", "RECOVERY", ""),
    ("appease_estate", "estate", None, ""),
    ("alleviate_concerns", "country", None, ""),
    ("reduce_inflation", "country", None, "inflation > 0"),
    ("develop_province", "capital", None, ""),
    ("study_institutions", "province", "population", ""),
    ("pop_promote_action", "province", "population", ""),
    ("strengthen_government", "country", None, ""),
    ("diplomatic_endeavors", "country", None, ""),
    ("counter_espionage_action", "country", None, ""),
    # Appended, not inserted: CMF keeps a list's rows by position, and a saved
    # game's order of the first twenty must not shift.
    ("noblesse_oblige_cabinet_action", "province", "province_tax_base", ""),
    # His ask 12.10: diplomatic endeavors serves two ends, so two rows he can
    # rank apart. The action has no target; this row only takes a seat while
    # someone is near a coalition against him.
    ("diplomatic_antagonism", "country", None,
     "OR = { has_countries_with_near_coalition_grade_antagonism = yes has_countries_with_coalition_grade_antagonism = yes }"),
    # His rule 13.10: assimilation serves two ends. The row above (kept at its
    # place) brings every location of a province to half a primary or accepted
    # culture, what integration and cores need; this one goes on to the whole.
    ("promote_culture_full", "culture", "population", ""),
    # His spec 12.10–13.10: the pairs ticked in «Общественные ценности», one
    # seat, through the game's window (value_effects, value_window.py).
    ("change_societal_values", "values", None, ""),
]

# A row that is not an action of its own: the action it places.
ROW_ACTION = {"diplomatic_antagonism": "diplomatic_endeavors", "promote_culture_full": "promote_culture"}

# A row's own condition on a target (in the province search) and on a seat
# already on its action (keeping it; the emergency's rank).
ROW_TARGET = {"promote_culture": "bag_asp_needs_half = yes bag_asp_control_reachable = yes"}
ROW_SEAT = {"promote_culture": "interaction_target:target_1 ?= { bag_asp_needs_half = yes }"}

# Rows of one action told apart in their label, and their tooltips.
ROW_NOTE = {
    "promote_culture": {
        "english": (" (to half)", "Until no location of the province is «integrated» or «conquered» short of half a primary or accepted culture: at half an integrated location becomes core. The province with the higher average control goes first, counted in bands of ten points (without control nothing assimilates; none at all, never); within a band, the one with more integrated locations, then more conquered ones. In a full hand-out a running one moves to a province that ranks higher. A seat whose province is done is freed, unless the full row is in use."),
        "russian": (" (до 50%)", "Пока в провинции есть районы «интегрирован» или «завоёван» без половины основной или признанной культуры: на половине интегрированный район становится национальным. Первой идёт провинция с более высоким средним контролем, по ступеням в 10 пунктов (без контроля ассимиляция не идёт; при нулевом провинция не берётся); внутри ступени — где больше интегрированных районов, потом завоёванных. При полной раздаче идущая ассимиляция переезжает в провинцию выше по этому порядку. Место, чья провинция готова, освобождается, если не используется строка полной ассимиляции."),
    },
    "promote_culture_full": {
        "english": (" (full)", "On to the whole province in the target culture, for the rare goal of changing culture outright."),
        "russian": (" (полная)", "Дальше, до всей провинции в нужной культуре: для редкой цели полностью сменить культуру."),
    },
    "diplomatic_endeavors": {
        "english": (" (opinion)", "For improving opinion with your targets. Taken whenever a seat is free for it."),
        "russian": (" (мнение)", "Для улучшения мнения у ваших целей. Берёт место всегда, когда оно свободно."),
    },
    "change_societal_values": {
        "english": ("", "Pushes the pairs ticked in «Societal values» (Fine tuning), in that list's order, toward the side chosen there: the advisor best in diplomacy among the free ones takes the first pair he would move at least one whole point. One seat. The pair is picked in the game's own window, which opens and closes by itself."),
        "russian": ("", "Двигает пары, отмеченные в «Общественных ценностях» («Тонкие настройки»), в порядке того списка, в выбранную там сторону: лучший по дипломатии свободный советник берёт первую пару, которую сдвинет хотя бы на одну целую единицу. Одно место. Пару выбирает окно игры, оно само открывается и закрывается."),
    },
    "diplomatic_antagonism": {
        "english": (" (antagonism)", "For lowering antagonism: diplomatic reputation reduces it. Taken only while a country is near a coalition against you."),
        "russian": (" (неприязнь)", "Для снижения неприязни: её уменьшает дипломатическая репутация. Берёт место, только пока кто-то близок к коалиции против вас."),
    },
}


def act(row: str) -> str:
    return ROW_ACTION.get(row, row)

LEAD = 0.3  # his rule 05.10, the same as the vanilla-automation patch

# Which province to recover first, his rule 12.10: the more of its locations
# are below zero prosperity, the sooner; then population.
RECOVERY = """{
\t\t\t\t\tvalue = 0
\t\t\t\t\tevery_location_in_province = {
\t\t\t\t\t\tlimit = { prosperity < 0 }
\t\t\t\t\t\tadd = 100
\t\t\t\t\t}
\t\t\t\t\tadd = {
\t\t\t\t\t\tvalue = population
\t\t\t\t\t\tmax = 99
\t\t\t\t\t}
\t\t\t\t}"""

# Which province to integrate first, his rule 12.10, not a setting: first by how
# many of its conquered locations are at least half the primary culture (they
# integrate about twice as fast), then by how many are at least half an accepted
# culture (no assimilating afterwards), then by population. A tier counts a
# location once; the weights keep the tiers apart (a province has far fewer
# than 100 locations, population is capped below the second weight) and stay
# small: the range of a fixed-point script value is not measured here.
INTEGRATION = """{
\t\t\t\t\tvalue = 0
\t\t\t\t\tevery_location_in_province = {
\t\t\t\t\t\tlimit = {
\t\t\t\t\t\t\tintegration_level = conquered
\t\t\t\t\t\t\tculture_percentage = { culture = scope:actor.culture value >= 0.5 }
\t\t\t\t\t\t}
\t\t\t\t\t\tadd = 10000
\t\t\t\t\t}
\t\t\t\t\tevery_location_in_province = {
\t\t\t\t\t\tlimit = {
\t\t\t\t\t\t\tintegration_level = conquered
\t\t\t\t\t\t\tNOT = { culture_percentage = { culture = scope:actor.culture value >= 0.5 } }
\t\t\t\t\t\t\tdominant_culture ?= { is_primary_or_accepted_in = scope:actor }
\t\t\t\t\t\t\tculture_percentage = { culture = dominant_culture value >= 0.5 }
\t\t\t\t\t\t}
\t\t\t\t\t\tadd = 100
\t\t\t\t\t}
\t\t\t\t\tadd = {
\t\t\t\t\t\tvalue = population
\t\t\t\t\t\tmax = 99
\t\t\t\t\t}
\t\t\t\t}"""

# Which province to assimilate to half first, his rule 13.10: by the status of
# its locations, not by percentages. «Integrated» is a location integrated and
# short of half a primary or accepted culture (at half it becomes core);
# «conquered» assimilates slower. Locations assimilate each on their own, so
# the more of them at once, the better. Then, his correction: average control
# first, by bands of ten points. Script values in VALUES.
HALF = "bag_asp_half_score"

VALUES = """# assimilate_primary: script values of the council pass. Rebuilt by tools/generate.py.

# Scope: province; scope:actor is the country. His rule 13.10: integrated
# locations first, conquered ones short of half after them.
bag_asp_half_need = {
\tvalue = 0
\tevery_location_in_province = {
\t\tlimit = {
\t\t\towner ?= scope:actor
\t\t\tintegration_level = integrated
\t\t}
\t\tadd = 100
\t}
\tevery_location_in_province = {
\t\tlimit = {
\t\t\towner ?= scope:actor
\t\t\tintegration_level = conquered
\t\t\tbag_asp_short_of_half = yes
\t\t}
\t\tadd = 1
\t}
}

# His rule 13.10, later: control first, since without it nothing assimilates.
# Average control of the province in bands of ten points, 0–10; a higher band
# wins outright, within a band the locations decide.
bag_asp_control_band = {
\tvalue = province_average_control
\tmultiply = 10
\tfloor = yes
}

bag_asp_half_rank = {
\tvalue = bag_asp_control_band
\tmultiply = 10000
\tadd = bag_asp_half_need
}

# Scope: cabinet (a seat). The rank of the province its assimilation works on,
# 0 without one: which of two assimilations keeps its seat for the other's
# control (bag_asp_keep_pairs).
bag_asp_seat_rank = {
\tvalue = 0
\tinteraction_target:target_1 ?= { add = bag_asp_half_rank }
}

# Probe, his run 13.10 07:12: a number parked in a global for the log line.
bag_asp_probe_value = {
\tvalue = global_var:bag_asp_probe
}

# The rank, then population to part equal ones. Kept near a million at most:
# the range of a fixed-point script value is not measured here.
bag_asp_half_score = {
\tvalue = bag_asp_half_rank
\tmultiply = 10
\tadd = {
\t\tvalue = population
\t\tmax = 9
\t}
}
"""

# The two lists over the pool. «Тонкие настройки» holds only the CMF groups of
# the actions that have settings (FINE): the list of every action that stood
# there in 0.9.0 told nothing, his word 13.10.
LISTS = ("available", "priority")

# The control actions «Ускорять контролем» puts on a province being assimilated,
# in the order tried: the game hides each where the other is (their visible).
SPEEDUP = ("noblesse_oblige_cabinet_action", "increase_control_province")
PAIRED_WITH = "promote_culture"

# The CMF settings of «Тонкие настройки», his ask 12.10. Each: (setting, group,
# kind, options). Groups are named after the action, by its game name.
FINE = [
    ("culture_target", "promote_culture", "dropdown", 2),
    ("culture_speedup", "promote_culture", "bool", 0),
    ("religion_target", "promote_religion", "dropdown", 2),
]
FINE_LOC = {
    "english": {
        "bag_asp__culture_target_name": "Assimilate into",
        "bag_asp__culture_target_desc": "Which culture the council assimilates provinces into.",
        "bag_asp__culture_target_option_1_name": "Primary culture",
        "bag_asp__culture_target_option_1_desc": "The country's primary culture. Where an accepted culture already leads it by 30 points, the province is left alone.",
        "bag_asp__culture_target_option_2_name": "Accepted culture",
        "bag_asp__culture_target_option_2_desc": "The accepted culture most widespread in the country. With none accepted, the primary.",
        "bag_asp__culture_speedup_name": "Speed it up with control",
        "bag_asp__culture_speedup_desc": "Assimilation runs faster where control is high. On: each assimilation brings its own seat with [ShowCabinetActionName('noblesse_oblige_cabinet_action')], or [ShowCabinetActionName('increase_control_province')] where that does not fit, in the same province, before the next assimilation is placed. That seat is bound to the assimilation, whatever the control action's own place in «Priority», and is freed with it. It never takes a seat from an action ranked above assimilation. The game forbids both control actions on one province.",
        "bag_asp__religion_target_name": "Convert into",
        "bag_asp__religion_target_desc": "Which religion the council converts provinces into.",
        "bag_asp__religion_target_option_1_name": "State religion",
        "bag_asp__religion_target_option_1_desc": "The country's own religion.",
        "bag_asp__religion_target_option_2_name": "Another of its group",
        "bag_asp__religion_target_option_2_desc": "The most widespread other religion of the state religion's group in the country; the game allows no other. With none present, the state religion.",
    },
    "russian": {
        "bag_asp__culture_target_name": "Ассимилировать в",
        "bag_asp__culture_target_desc": "В какую культуру совет ассимилирует провинции.",
        "bag_asp__culture_target_option_1_name": "Основную культуру",
        "bag_asp__culture_target_option_1_desc": "Основная культура страны. Где признанная уже опережает её на 30 пунктов, провинция не трогается.",
        "bag_asp__culture_target_option_2_name": "Признанную культуру",
        "bag_asp__culture_target_option_2_desc": "Самая распространённая в стране признанная культура. Если признанных нет, основная.",
        "bag_asp__culture_speedup_name": "Ускорять контролем",
        "bag_asp__culture_speedup_desc": "Ассимиляция идёт быстрее при высоком контроле. Включено: каждая ассимиляция сразу получает своё место с [ShowCabinetActionName('noblesse_oblige_cabinet_action')], а где он не подходит, с [ShowCabinetActionName('increase_control_province')], в той же провинции, и только потом ставится следующая ассимиляция. Это место привязано к ассимиляции, где бы ни стояло действие контроля в «Приоритете», и освобождается вместе с ней. Место у действия выше ассимиляции оно не забирает. Оба действия контроля в одну провинцию игра не даёт.",
        "bag_asp__religion_target_name": "Обращать в",
        "bag_asp__religion_target_desc": "В какую религию совет обращает провинции.",
        "bag_asp__religion_target_option_1_name": "Государственную",
        "bag_asp__religion_target_option_1_desc": "Религия страны.",
        "bag_asp__religion_target_option_2_name": "Другую из её группы",
        "bag_asp__religion_target_option_2_desc": "Самая распространённая в стране другая религия той же группы: другую игра не даёт. Если такой нет, государственная.",
    },
}

# The list «Общественные ценности» of «Тонкие настройки», his spec 12.10.
VALUES_LOC = {
    "english": {
        "bag_asp__fine__values_name": "Societal values",
        "bag_asp__values_name": "Societal values",
        "bag_asp__values_desc": "For the «Priority» row [ShowCabinetActionName('change_societal_values')]: ticked pairs are pushed, tried from the top, toward the side chosen for each. Each month the advisor best in diplomacy among the free ones takes the first pair he would move at least one whole point: a pair stops where 100 × its monthly push toward the side says (the game's «no more than»), his push included. Hover a row for its two sides.",
        "bag_asp__values_item_column_name": "Pair",
        "bag_asp__values__use_name": "Push",
        "bag_asp__values__side_name": "Toward",
        "bag_asp__values__side_option_1_name": "Left, the first",
        "bag_asp__values__side_option_1_desc": "Toward the first side named in the pair.",
        "bag_asp__values__side_option_2_name": "Right, the second",
        "bag_asp__values__side_option_2_desc": "Toward the second side named in the pair.",
    },
    "russian": {
        "bag_asp__fine__values_name": "Общественные ценности",
        "bag_asp__values_name": "Общественные ценности",
        "bag_asp__values_desc": "Для строки «Приоритета» [ShowCabinetActionName('change_societal_values')]: отмеченные пары двигаются, пробуются сверху вниз, в сторону, выбранную у каждой. Каждый месяц лучший по дипломатии свободный советник берёт первую пару, которую сдвинет хотя бы на одну целую единицу: пара останавливается там, где 100 × её месячный сдвиг в эту сторону (игровое «не больше»), с его толчком. Наведите на строку — увидите обе стороны.",
        "bag_asp__values_item_column_name": "Пара",
        "bag_asp__values__use_name": "Двигать",
        "bag_asp__values__side_name": "Куда",
        "bag_asp__values__side_option_1_name": "Влево, к первой",
        "bag_asp__values__side_option_1_desc": "К первой стороне в названии пары.",
        "bag_asp__values__side_option_2_name": "Вправо, ко второй",
        "bag_asp__values__side_option_2_desc": "Ко второй стороне в названии пары.",
    },
}
SIDE_WORDS = {"english": ("Left", "right"), "russian": ("Влево", "вправо")}

ABILITY = {
    "english": {"adm": "ADM", "dip": "DIP", "mil": "MIL"},
    "russian": {"adm": "АДМ", "dip": "ДИП", "mil": "ВОЕ"},
}


def block_end(text: str, start: int) -> int:
    depth, i = 0, text.index("{", start)
    while True:
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1


def body(text: str, start: int) -> str:
    """The inside of the block whose `{` is the first after start."""
    return text[text.index("{", start) + 1:block_end(text, start)]


def child(block: str, key: str) -> str | None:
    """A direct child block `key = { ... }` of block, or None."""
    depth = 0
    for m in re.finditer(r"[{}]|(?<![\w:.])" + re.escape(key) + r"\s*=\s*\{", block):
        tok = m.group(0)
        if tok == "{":
            depth += 1
        elif tok == "}":
            depth -= 1
        else:
            if depth == 0:
                return body(block, m.start())
            depth += 1
    return None


def children(block: str, key: str) -> list[str]:
    out, depth = [], 0
    for m in re.finditer(r"[{}]|(?<![\w:.])" + re.escape(key) + r"\s*=\s*\{", block):
        tok = m.group(0)
        if tok == "{":
            depth += 1
        elif tok == "}":
            depth -= 1
        else:
            if depth == 0:
                out.append(body(block, m.start()))
            depth += 1
    return out


def value(block: str, key: str) -> str | None:
    depth = 0
    for m in re.finditer(r"[{}]|(?<![\w:.])" + re.escape(key) + r"\s*=\s*(\w+)", block):
        tok = m.group(0)
        if tok == "{":
            depth += 1
        elif tok == "}":
            depth -= 1
        elif depth == 0:
            return m.group(1)
    return None


def strip_comments(text: str) -> str:
    return re.sub(r"#[^\n]*", "", text)


def load_actions(game: Path) -> dict[str, str]:
    """Every cabinet action's body by key."""
    out = {}
    for f in sorted((game / "in_game/common/cabinet_actions").glob("*.txt")):
        text = strip_comments(f.read_text(encoding="utf-8-sig").replace("\r\n", "\n"))
        for m in re.finditer(r"^(\w+)\s*=\s*\{", text, re.M):
            out[m.group(1)] = body(text, m.start())
    return out


def select(action: str, looking_for: str) -> str:
    for s in children(action, "select_trigger"):
        if value(s, "looking_for_a") == looking_for:
            return s
    raise SystemExit(f"council: no select_trigger looking for a {looking_for}")


def indent(text: str, tabs: int) -> str:
    lines = [l.strip() for l in text.strip().split("\n")]
    out, depth = [], tabs
    for l in lines:
        if not l:
            continue
        if l.startswith("}"):
            depth -= l.count("}") - l.count("{") if l.count("}") > l.count("{") else 0
        out.append("\t" * max(depth, 0) + l)
        if not l.startswith("}"):
            depth += l.count("{") - l.count("}")
    return "\n".join(out)


# Seats whose target the copied triggers ask about: (action, its target flag).
# Filled by rewrite() while the try effects are built, read by the marking pass.
BUSY: set[tuple[str, str]] = set()


def rewrite(text: str, actions: dict[str, str]) -> str:
    """The game's triggers about other seats compare a seat's target with `root`,
    which in a select_trigger is the candidate and here is the country. Each
    becomes a variable the pass puts on every target a seat already has."""
    def busy(key: str, flag: str) -> str:
        BUSY.add((key, flag))
        return f"has_variable = bag_asp_busy_{key}"

    def flag_for(key: str, looking: str) -> str:
        return flag_of(select(actions[key], looking))

    text = re.sub(
        r"cabinet_already_performing_same_task_on_target\s*=\s*\{\s*cabinet_action\s*=\s*(\w+)\s+interaction_target\s*=\s*(\w+)\s*\}",
        lambda m: busy(m.group(1), m.group(2)), text)
    text = re.sub(
        r"cabinet_control_area_action_covers_province\s*=\s*yes",
        lambda m: "area ?= { " + busy("increase_control_area", flag_for("increase_control_area", "area")) + " }", text)
    text = re.sub(
        r"cabinet_control_province_action_in_area\s*=\s*\{\s*cabinet_action\s*=\s*(\w+)\s*\}",
        lambda m: "any_location_in_area = { province ?= { " + busy(m.group(1), flag_for(m.group(1), "province")) + " } }", text)
    # appease_estate asks the country whether it has the estate being listed;
    # every estate ordered_estate walks is the country's own.
    text = re.sub(r"scope:actor\s*=\s*\{\s*country_has_estate\s*=\s*root\.estate_type\s*\}", "always = yes", text)
    if re.search(r"(?<![\w:.])root\b", text):
        raise SystemExit("council: a copied trigger still reads `root`, which is the country here:\n" + text)
    return text


def target_test(sel: str, tabs: int, actions: dict[str, str], key: str) -> str:
    """The select_trigger's own visible and enabled, as one block of conditions,
    after a guard that no seat, this pass included, already has this target."""
    parts = [f"NOT = {{ has_variable = bag_asp_busy_{key} }}"]
    parts += [b for b in (child(sel, "visible"), child(sel, "enabled")) if b and b.strip()]
    return indent(rewrite("\n".join(parts), actions), tabs)


def flag_of(sel: str, default: str = "target") -> str:
    return value(sel, "target_flag") or default


def try_effect(row: str, kind: str, order: str | None, gate: str, actions: dict[str, str],
               at: str | None = None) -> str:
    """bag_asp_try_<row>: put this row's action on scope:bag_asp_seat if a
    target fits. With `at`, only on that one province (a scope), and the
    effect is bag_asp_try_at_<row>."""
    key = act(row)
    action = actions[key]
    if order == "INTEGRATION":
        order = INTEGRATION
    elif order == "RECOVERY":
        order = RECOVERY
    elif order == "HALF":
        order = HALF
    # Unset in the file counts as one seat at a time: otherwise an action with no
    # condition on its target (pop_promote_action) takes every seat left.
    multiple = value(action, "allow_multiple") == "yes"
    cond = [f"cabinet_action:{key} = {{ is_available_for = scope:actor }}"]
    if gate:
        cond.append(f"scope:actor = {{ {gate} }}")
    if not multiple:
        cond.append(f"scope:actor = {{ NOT = {{ any_cabinet = {{ has_cabinet_action = yes cabinet_action = cabinet_action:{key} }} }} }}")
    limit = "\n".join("\t\t\t" + c for c in cond)
    done = (f"\t\t\t\tscope:bag_asp_seat = {{ cabinet_member = {{ set_variable = {{ name = bag_asp_claimed value = yes }} }} }}\n"
            f"\t\t\t\tscope:actor = {{ set_variable = {{ name = bag_asp_placed value = yes }} }}\n"
            f"\t\t\t\tdebug_log = \"bag_asp: seat set to {row}\"")

    def assign(params: str, flag: str = "") -> str:
        mark = ""
        if flag:
            BUSY.add((key, flag))
            mark = f"\t\t\t\tscope:bag_asp_pick = {{ set_variable = {{ name = bag_asp_busy_{key} value = yes }} }}\n"
        # A seat taken from a lower action is stopped first; set_cabinet_action
        # is not known to replace a running action by itself.
        last = "\t\t\t\tscope:bag_asp_pick = { save_scope_as = bag_asp_last }\n" if key == PAIRED_WITH else ""
        return (last + f"\t\t\t\tscope:bag_asp_seat = {{\n"
                f"\t\t\t\t\tbag_asp_vacate = yes\n"
                f"\t\t\t\t\tset_cabinet_action = {{ type = cabinet_action:{key}{params} }}\n"
                f"\t\t\t\t}}\n" + mark + done)

    if kind == "country":
        inner = assign("").replace("\t\t\t\t", "\t\t", 1).replace("\n\t\t\t\t", "\n\t\t")
    elif kind in ("province", "capital"):
        sel = select(action, "province")
        flag = flag_of(sel)
        if at:
            inner = (f"\t\t{at} = {{\n\t\t\tif = {{\n\t\t\t\tlimit = {{\n"
                     f"{target_test(sel, 5, actions, key)}\n\t\t\t\t}}\n"
                     f"\t\t\t\tsave_temporary_scope_as = bag_asp_pick\n"
                     f"{assign(f' {flag} = scope:bag_asp_pick', flag)}\n\t\t\t}}\n\t\t}}")
        elif kind == "province":
            inner = (f"\t\tscope:actor = {{\n\t\t\tordered_province = {{\n\t\t\t\tlimit = {{\n"
                     f"{target_test(sel, 5, actions, key)}\n\t\t\t\t}}\n\t\t\t\torder_by = {order}\n"
                     f"\t\t\t\tsave_temporary_scope_as = bag_asp_pick\n"
                     f"{assign(f' {flag} = scope:bag_asp_pick', flag)}\n\t\t\t}}\n\t\t}}")
        else:
            inner = (f"\t\tscope:actor.capital.province = {{\n\t\t\tif = {{\n\t\t\t\tlimit = {{\n"
                     f"{target_test(sel, 5, actions, key)}\n\t\t\t\t}}\n"
                     f"\t\t\t\tsave_temporary_scope_as = bag_asp_pick\n"
                     f"{assign(f' {flag} = scope:bag_asp_pick', flag)}\n\t\t\t}}\n\t\t}}")
    elif kind == "area":
        sel = select(action, "area")
        flag = flag_of(sel)
        inner = (f"\t\tscope:actor = {{\n\t\t\tordered_province = {{\n\t\t\t\tlimit = {{\n"
                 f"\t\t\t\t\tarea ?= {{\n{target_test(sel, 6, actions, key)}\n\t\t\t\t\t}}\n\t\t\t\t}}\n"
                 f"\t\t\t\torder_by = {order}\n"
                 f"\t\t\t\tarea = {{ save_temporary_scope_as = bag_asp_pick }}\n"
                 f"{assign(f' {flag} = scope:bag_asp_pick', flag)}\n\t\t\t}}\n\t\t}}")
    elif kind == "culture":
        sel = select(action, "province")
        cflag = flag_of(select(action, "culture"))
        pflag = flag_of(sel)
        own = f"\t\t\t\t\t{ROW_TARGET[row]}\n" if row in ROW_TARGET else ""
        rule = lead_rule(cflag)
        inner = (culture_choice(cflag) +
                 f"\t\tscope:actor = {{\n\t\t\tordered_province = {{\n\t\t\t\tlimit = {{\n"
                 f"{target_test(sel, 5, actions, key)}\n{rule}\n{own}\t\t\t\t}}\n\t\t\t\torder_by = {order}\n"
                 f"\t\t\t\tsave_temporary_scope_as = bag_asp_pick\n"
                 f"{assign(f' {cflag} = scope:{cflag} {pflag} = scope:bag_asp_pick', pflag)}\n\t\t\t}}\n\t\t}}")
    elif kind == "religion":
        sel = select(action, "province")
        rflag = flag_of(select(action, "religion"))
        pflag = flag_of(sel)
        # His ask 12.10: into the state religion (option 1, the default) or the
        # most widespread other religion of its group in the country (option 2:
        # the game offers no other).
        other = ("NOT = { this = scope:actor.religion } group = scope:actor.religion.group "
                 "is_religion_enabled = yes")
        inner = (f"\t\tif = {{\n\t\t\tlimit = {{\n\t\t\t\tscope:actor = {{\n"
                 f"\t\t\t\t\tvar:bag_asp_religion_target = 2\n"
                 f"\t\t\t\t\tany_present_religion_in_country = {{ {other} }}\n"
                 f"\t\t\t\t}}\n\t\t\t}}\n"
                 f"\t\t\tscope:actor = {{\n\t\t\t\tordered_present_religion_in_country = {{\n"
                 f"\t\t\t\t\tlimit = {{ {other} }}\n"
                 f"\t\t\t\t\torder_by = \"scope:actor.religion_percentage_in_country(this)\"\n"
                 f"\t\t\t\t\tsave_scope_as = {rflag}\n\t\t\t\t}}\n\t\t\t}}\n\t\t}}\n"
                 f"\t\telse = {{\n\t\t\tscope:actor.religion = {{ save_scope_as = {rflag} }}\n\t\t}}\n"
                 f"\t\tscope:actor = {{\n\t\t\tordered_province = {{\n\t\t\t\tlimit = {{\n"
                 f"{target_test(sel, 5, actions, key)}\n\t\t\t\t}}\n\t\t\t\torder_by = {order}\n"
                 f"\t\t\t\tsave_temporary_scope_as = bag_asp_pick\n"
                 f"{assign(f' {rflag} = scope:{rflag} {pflag} = scope:bag_asp_pick', pflag)}\n\t\t\t}}\n\t\t}}")
    elif kind == "estate":
        sel = select(action, "estate")
        flag = flag_of(sel)
        inner = (f"\t\tscope:actor = {{\n\t\t\tordered_estate = {{\n\t\t\t\tlimit = {{\n"
                 f"{target_test(sel, 5, actions, key)}\n\t\t\t\t}}\n"
                 f"\t\t\t\torder_by = {{ value = 1 subtract = satisfaction }}\n"
                 f"\t\t\t\tsave_temporary_scope_as = bag_asp_pick\n"
                 f"{assign(f' {flag} = scope:bag_asp_pick', flag)}\n\t\t\t}}\n\t\t}}")
    else:
        raise SystemExit(f"council: unknown kind {kind}")
    name = f"bag_asp_try_at_{row}" if at else f"bag_asp_try_{row}"
    where = f"; the province is {at}" if at else ""
    return (f"# Scope: country (scope:actor); the seat is scope:bag_asp_seat{where}.\n"
            f"{name} = {{\n\tif = {{\n\t\tlimit = {{\n{limit}\n\t\t}}\n{inner}\n\t}}\n}}\n")


def culture_choice(cflag: str) -> str:
    """His ask 12.10: scope:<cflag> is the primary culture (option 1, the default)
    or the accepted one most widespread in the country (option 2)."""
    return (f"\t\tif = {{\n\t\t\tlimit = {{\n\t\t\t\tscope:actor = {{\n"
            f"\t\t\t\t\tvar:bag_asp_culture_target = 2\n\t\t\t\t\tany_accepted_culture = {{ always = yes }}\n"
            f"\t\t\t\t}}\n\t\t\t}}\n"
            f"\t\t\tscope:actor = {{\n\t\t\t\tordered_accepted_culture = {{\n"
            f"\t\t\t\t\torder_by = \"scope:actor.culture_percentage_in_country(this)\"\n"
            f"\t\t\t\t\tsave_scope_as = {cflag}\n\t\t\t\t}}\n\t\t\t}}\n\t\t}}\n"
            f"\t\telse = {{\n\t\t\tscope:actor.culture = {{ save_scope_as = {cflag} }}\n\t\t}}\n")


def lead_rule(cflag: str) -> str:
    """His rule 05.10 as conditions on a province, five tabs deep."""
    return (f"\t\t\t\t\t# His rule 05.10: where an accepted culture leads the primary by\n"
            f"\t\t\t\t\t# {round(LEAD * 100)} points, do not push the primary.\n"
            f"\t\t\t\t\ttrigger_if = {{\n\t\t\t\t\t\tlimit = {{ scope:{cflag} = scope:actor.culture }}\n"
            f"\t\t\t\t\t\tNAND = {{\n\t\t\t\t\t\t\texists = dominant_culture\n"
            f"\t\t\t\t\t\t\tNOT = {{ dominant_culture = scope:actor.culture }}\n"
            f"\t\t\t\t\t\t\tdominant_culture = {{ is_primary_or_accepted_in = scope:actor }}\n"
            f"\t\t\t\t\t\t\t\"culture_percentage(dominant_culture)\" >= {{\n"
            f"\t\t\t\t\t\t\t\tvalue = \"culture_percentage(scope:actor.culture)\"\n"
            f"\t\t\t\t\t\t\t\tadd = {LEAD}\n\t\t\t\t\t\t\t}}\n\t\t\t\t\t\t}}\n\t\t\t\t\t}}")


def seat_test(action: str, tabs: int) -> str:
    """A free seat this action can use."""
    seat = ["bag_asp_free_seat = yes"]
    if value(action, "require_matching_character_religion") == "yes":
        seat.append("cabinet_member = { religion = scope:actor.religion }")
    return "\n".join("\t" * tabs + s for s in seat)


def place_effect(row: str, gate: str, actions: dict[str, str]) -> str:
    """Seats already on this action are kept (while the row's gate holds);
    then free seats take it, the advisor best in its skill first, while it
    still finds a target."""
    key = act(row)
    action = actions[key]
    ability = value(action, "ability") or "adm"
    # His run 13.10 10:02: an assimilation moved onto the seat of its own
    # control, which was not yet kept at that step, and the control was lost.
    own_pair = "\t\t\t\t\tNOT = { bag_asp_paired_seat = yes }\n" if key == PAIRED_WITH else ""
    seat = seat_test(action, 4)
    keep_gate = f"\n\t\t\tscope:actor = {{ {gate} }}" if gate else ""
    if row in ROW_SEAT:
        keep_gate += f"\n\t\t\t{ROW_SEAT[row]}"
    keep_pairs = pair_after = retarget = ""
    if row in ROW_TARGET:
        sel = select(action, "province")
        retarget = f"""\t# His rule 13.10: locations assimilate each on their own, so a kept
\t# assimilation moves to a province with more locations to bring to half.
\tif = {{
\t\tlimit = {{ NOT = {{ has_variable = bag_asp_fill_only }} }}
\t\tevery_cabinet = {{
\t\t\tlimit = {{
\t\t\t\tcabinet_member ?= {{ has_variable = bag_asp_kept }}
\t\t\t\texists = interaction_target:target
\t\t\t\texists = interaction_target:target_1
\t\t\t}}
\t\t\tsave_scope_as = bag_asp_seat
\t\t\tinteraction_target:target = {{ save_scope_as = target }}
\t\t\tinteraction_target:target_1 = {{
\t\t\t\tsave_scope_as = bag_asp_cur
\t\t\t\tsave_scope_value_as = {{ name = bag_asp_cur_rank value = bag_asp_half_rank }}
\t\t\t}}
\t\t\tscope:actor = {{
\t\t\t\tordered_province = {{
\t\t\t\t\tlimit = {{
{target_test(sel, 6, actions, key)}
\t\t\t\t\t\t{ROW_TARGET[row]}
\t\t\t\t\t\tbag_asp_half_rank > scope:bag_asp_cur_rank
\t\t\t\t\t}}
\t\t\t\t\torder_by = {HALF}
\t\t\t\t\tsave_scope_as = bag_asp_new
\t\t\t\t\tscope:bag_asp_cur = {{ remove_variable = bag_asp_busy_{key} }}
\t\t\t\t\tscope:bag_asp_new = {{ set_variable = {{ name = bag_asp_busy_{key} value = yes }} }}
\t\t\t\t\tscope:bag_asp_seat = {{
\t\t\t\t\t\tstop_cabinet_action = {{}}
\t\t\t\t\t\tset_cabinet_action = {{ type = cabinet_action:{key} target = scope:target target_1 = scope:bag_asp_new }}
\t\t\t\t\t}}
\t\t\t\t\tdebug_log = "bag_asp: assimilation moved to a province with more locations to bring to half"
\t\t\t\t}}
\t\t\t}}
\t\t}}
\t\t# The control seat of a province left behind goes now.
\t\tbag_asp_unpair = yes
\t}}
"""
    if key == PAIRED_WITH:
        # His rule 13.10: with «Ускорять контролем» each assimilation brings its
        # control seat at once, before the next assimilation takes a seat.
        keep_pairs = "\tif = {\n\t\tlimit = { has_variable = bag_asp_speedup_on }\n\t\tbag_asp_keep_pairs = yes\n\t}\n"
        pair_after = ("\t\tif = {\n\t\t\tlimit = {\n\t\t\t\thas_variable = bag_asp_placed\n"
                      "\t\t\t\thas_variable = bag_asp_speedup_on\n\t\t\t}\n\t\t\tbag_asp_pair = yes\n\t\t}\n")
    return f"""# Scope: country (scope:actor).
bag_asp_place_{row} = {{
\tevery_cabinet = {{
\t\tlimit = {{
\t\t\tbag_asp_free_seat = yes
\t\t\thas_cabinet_action = yes
\t\t\tcabinet_action = cabinet_action:{key}{keep_gate}
\t\t}}
\t\tcabinet_member = {{
\t\t\tset_variable = {{ name = bag_asp_claimed value = yes }}
\t\t\tset_variable = {{ name = bag_asp_kept value = yes }}
\t\t}}
\t}}
{retarget}\t# His rule 13.10: in a full hand-out the row takes the best advisors for it,
\t# even from a lower row: while a free seat beats its weakest kept one in the
\t# skill, the action moves there with its targets.
\tif = {{
\t\tlimit = {{ NOT = {{ has_variable = bag_asp_fill_only }} }}
\t\tset_variable = {{ name = bag_asp_moving value = yes }}
\t\twhile = {{
\t\t\tlimit = {{
\t\t\t\thas_variable = bag_asp_moving
\t\t\t\tany_cabinet = {{ cabinet_member ?= {{ has_variable = bag_asp_kept }} }}
\t\t\t}}
\t\t\tremove_variable = bag_asp_moving
\t\t\tordered_cabinet = {{
\t\t\t\tlimit = {{ cabinet_member ?= {{ has_variable = bag_asp_kept }} }}
\t\t\t\torder_by = {{
\t\t\t\t\tvalue = 0
\t\t\t\t\tsubtract = cabinet_member.{ability}
\t\t\t\t}}
\t\t\t\tsave_scope_as = bag_asp_from
\t\t\t}}
\t\t\tset_variable = {{ name = bag_asp_low value = scope:bag_asp_from.cabinet_member.{ability} }}
\t\t\tordered_cabinet = {{
\t\t\t\tlimit = {{
{seat_test(action, 5)}
{own_pair}\t\t\t\t\tcabinet_member = {{ {ability} > scope:actor.var:bag_asp_low }}
\t\t\t\t}}
\t\t\t\torder_by = cabinet_member.{ability}
\t\t\t\tsave_scope_as = bag_asp_seat
\t\t\t\tscope:actor = {{
\t\t\t\t\tbag_asp_move_{row} = yes
\t\t\t\t\tset_variable = {{ name = bag_asp_moving value = yes }}
\t\t\t\t}}
\t\t\t}}
\t\t}}
\t\tif = {{
\t\t\tlimit = {{ has_variable = bag_asp_moving }}
\t\t\tremove_variable = bag_asp_moving
\t\t}}
\t}}
\tevery_cabinet = {{
\t\tlimit = {{ cabinet_member ?= {{ has_variable = bag_asp_kept }} }}
\t\tcabinet_member = {{ remove_variable = bag_asp_kept }}
\t}}
{keep_pairs}\tset_variable = {{ name = bag_asp_placed value = yes }}
\twhile = {{
\t\tlimit = {{
\t\t\thas_variable = bag_asp_placed
\t\t\tany_cabinet = {{ bag_asp_free_seat = yes }}
\t\t}}
\t\tremove_variable = bag_asp_placed
\t\tordered_cabinet = {{
\t\t\tlimit = {{
{seat}
\t\t\t}}
\t\t\torder_by = cabinet_member.{ability}
\t\t\tsave_scope_as = bag_asp_seat
\t\t\tbag_asp_try_{row} = yes
\t\t}}
{pair_after}\t}}
\tif = {{
\t\tlimit = {{ has_variable = bag_asp_placed }}
\t\tremove_variable = bag_asp_placed
\t}}
}}
"""


def move_effect(row: str, actions: dict[str, str]) -> str:
    """bag_asp_move_<row>: the action of scope:bag_asp_from, with every target
    it was given, onto scope:bag_asp_seat; the seat is claimed and kept, the
    one left behind is free again. Whether the game keeps the action's
    progress across the move is not known."""
    key = act(row)
    flags = sorted({flag_of(s) for s in children(actions[key], "select_trigger")})
    save = "".join(f"\t\tinteraction_target:{f} ?= {{ save_scope_as = bag_asp_t_{f} }}\n" for f in flags)
    params = "".join(f" {f} = scope:bag_asp_t_{f}" for f in flags)
    return f"""# Scope: country (scope:actor).
bag_asp_move_{row} = {{
\tscope:bag_asp_from = {{
{save}\t\tstop_cabinet_action = {{}}
\t\tcabinet_member = {{
\t\t\tremove_variable = bag_asp_claimed
\t\t\tremove_variable = bag_asp_kept
\t\t\tif = {{
\t\t\t\tlimit = {{ has_variable = bag_asp_paired }}
\t\t\t\tremove_variable = bag_asp_paired
\t\t\t\tscope:bag_asp_seat.cabinet_member = {{ set_variable = {{ name = bag_asp_paired value = yes }} }}
\t\t\t}}
\t\t}}
\t}}
\tscope:bag_asp_seat = {{
\t\tbag_asp_vacate = yes
\t\tset_cabinet_action = {{ type = cabinet_action:{key}{params} }}
\t\tcabinet_member = {{
\t\t\tset_variable = {{ name = bag_asp_claimed value = yes }}
\t\t\tset_variable = {{ name = bag_asp_kept value = yes }}
\t\t}}
\t}}
\tdebug_log = "bag_asp: {row} moved to an advisor better at it"
}}
"""


def pair_effects(actions: dict[str, str]) -> str:
    ability = value(actions[SPEEDUP[0]], "ability") or "adm"
    if any((value(actions[k], "ability") or "adm") != ability for k in SPEEDUP):
        raise SystemExit("council: the speedup's control actions no longer share a skill")
    pflag = flag_of(select(actions[PAIRED_WITH], "province"))
    if pflag != "target_1":
        raise SystemExit("council: assimilation's province is no longer target_1, which bag_asp_seat_rank reads")
    flags = {flag_of(select(actions[k], "province")) for k in SPEEDUP}
    if len(flags) != 1:
        raise SystemExit("council: the speedup's control actions no longer share a target flag")
    cflag = flags.pop()
    is_control = "OR = { " + " ".join(f"cabinet_action = cabinet_action:{k}" for k in SPEEDUP) + " }"
    tries = f"\t\tbag_asp_try_at_{SPEEDUP[0]} = yes\n"
    for k in SPEEDUP[1:]:
        tries += (f"\t\tif = {{\n\t\t\tlimit = {{ scope:actor = {{ NOT = {{ has_variable = bag_asp_placed }} }} }}\n"
                  f"\t\t\tbag_asp_try_at_{k} = yes\n\t\t}}\n")
    return f"""
# «Ускорять контролем», his rule 13.10: a control action ({", ".join(SPEEDUP)},
# the first that fits; the game forbids both on one province) is bound to an
# assimilation. It comes with it, whatever its own row's place, from a free
# seat (in a full hand-out a seat a lower row would have taken; in a fill, an
# empty one), and is released with it. The seat's advisor carries
# bag_asp_paired while it lasts.

# Scope: country (scope:actor); scope:bag_asp_last is the province just given
# to an assimilation. Leaves bag_asp_placed set, as the assimilation left it.
bag_asp_pair = {{
\tscope:bag_asp_last = {{ save_scope_as = bag_asp_at }}
\tremove_variable = bag_asp_placed
\tordered_cabinet = {{
\t\tlimit = {{
{seat_test(actions[SPEEDUP[0]], 3)}
\t\t}}
\t\torder_by = cabinet_member.{ability}
\t\tsave_scope_as = bag_asp_seat
{tries}\t\tif = {{
\t\t\tlimit = {{ scope:actor = {{ has_variable = bag_asp_placed }} }}
\t\t\tcabinet_member = {{ set_variable = {{ name = bag_asp_paired value = yes }} }}
\t\t\tdebug_log = "bag_asp: assimilation sped up with a control action"
\t\t}}
\t}}
\tset_variable = {{ name = bag_asp_placed value = yes }}
}}

# Scope: country (scope:actor). For the assimilations this pass keeps, the
# best province first: a control seat already with one is kept with it; one
# without gets one now. His rule 13.10 is assimilation, control, assimilation,
# control: where no seat is free (his run 13.10 07:12: two integrations above,
# two assimilations, no control for a month), the weakest assimilation still
# waiting gives its seat to the control of a better one, in a full hand-out
# and only where a control action fits that province.
bag_asp_keep_pairs = {{
\tevery_cabinet = {{
\t\tlimit = {{
\t\t\thas_cabinet_action = yes
\t\t\tcabinet_action = cabinet_action:{PAIRED_WITH}
\t\t\texists = interaction_target:{pflag}
\t\t\tcabinet_member ?= {{ has_variable = bag_asp_claimed }}
\t\t}}
\t\tcabinet_member = {{ set_variable = {{ name = bag_asp_pending value = yes }} }}
\t}}
\twhile = {{
\t\tlimit = {{ any_cabinet = {{ cabinet_member ?= {{ has_variable = bag_asp_pending }} }} }}
\t\tordered_cabinet = {{
\t\t\tlimit = {{ cabinet_member ?= {{ has_variable = bag_asp_pending }} }}
\t\t\torder_by = bag_asp_seat_rank
\t\t\tcabinet_member = {{ remove_variable = bag_asp_pending }}
\t\t\tinteraction_target:{pflag} = {{ save_scope_as = bag_asp_last }}
\t\t}}
\t\tif = {{
\t\t\tlimit = {{
\t\t\t\tany_cabinet = {{
\t\t\t\t\tbag_asp_paired_seat = yes
\t\t\t\t\tinteraction_target:{cflag} ?= {{ this = scope:bag_asp_last }}
\t\t\t\t}}
\t\t\t}}
\t\t\tevery_cabinet = {{
\t\t\t\tlimit = {{
\t\t\t\t\tbag_asp_paired_seat = yes
\t\t\t\t\tinteraction_target:{cflag} ?= {{ this = scope:bag_asp_last }}
\t\t\t\t}}
\t\t\t\tcabinet_member = {{ set_variable = {{ name = bag_asp_claimed value = yes }} }}
\t\t\t}}
\t\t}}
\t\telse = {{
\t\t\tif = {{
\t\t\t\tlimit = {{
\t\t\t\t\tNOT = {{ has_variable = bag_asp_fill_only }}
\t\t\t\t\tNOT = {{ any_cabinet = {{ bag_asp_free_seat = yes }} }}
\t\t\t\t\tany_cabinet = {{ cabinet_member ?= {{ has_variable = bag_asp_pending }} }}
\t\t\t\t\tscope:bag_asp_last = {{ bag_asp_control_fits = yes }}
\t\t\t\t}}
\t\t\t\tordered_cabinet = {{
\t\t\t\t\tlimit = {{ cabinet_member ?= {{ has_variable = bag_asp_pending }} }}
\t\t\t\t\torder_by = {{
\t\t\t\t\t\tvalue = 0
\t\t\t\t\t\tsubtract = bag_asp_seat_rank
\t\t\t\t\t}}
\t\t\t\t\tbag_asp_vacate = yes
\t\t\t\t\tcabinet_member = {{
\t\t\t\t\t\tremove_variable = bag_asp_pending
\t\t\t\t\t\tremove_variable = bag_asp_claimed
\t\t\t\t\t}}
\t\t\t\t\tdebug_log = "bag_asp: an assimilation gave its seat to the control of a better one"
\t\t\t\t}}
\t\t\t}}
\t\t\tbag_asp_pair = yes
\t\t\tremove_variable = bag_asp_placed
\t\t}}
\t}}
}}

# Scope: country (scope:actor), after bag_asp_mark_busy. A control seat whose
# assimilation is gone is stopped, so this pass can fill it; with the setting
# off, or the seat given something else, it is only no longer bound.
bag_asp_unpair = {{
\tevery_cabinet = {{
\t\tlimit = {{ cabinet_member ?= {{ has_variable = bag_asp_paired }} }}
\t\tif = {{
\t\t\tlimit = {{
\t\t\t\tscope:actor = {{ has_variable = bag_asp_speedup_on }}
\t\t\t\tbag_asp_paired_seat = yes
\t\t\t\tinteraction_target:{cflag} ?= {{ NOT = {{ has_variable = bag_asp_busy_{PAIRED_WITH} }} }}
\t\t\t}}
\t\t\tbag_asp_vacate = yes
\t\t\tdebug_log = "bag_asp: a control seat released with its assimilation"
\t\t}}
\t\telse_if = {{
\t\t\tlimit = {{
\t\t\t\tOR = {{
\t\t\t\t\tscope:actor = {{ NOT = {{ has_variable = bag_asp_speedup_on }} }}
\t\t\t\t\tNOT = {{ bag_asp_paired_seat = yes }}
\t\t\t\t}}
\t\t\t}}
\t\t\tcabinet_member = {{ remove_variable = bag_asp_paired }}
\t\t}}
\t}}
}}
"""


PRINT = "[GuiScope.SetRoot(GetPlayer.MakeScope).ScriptValue('bag_asp_probe_value')|0]"

# His ask 13.10: every setting's value, logged after he changes one. A number
# prints through a script value reading the variable outright: the form with
# `value = 0` and an `if` read zero in silence (docs/pitfalls/diagnosis.md).
NUMBERS = (("period", "bag_asp_period"), ("review", "bag_asp_review"),
           ("culture_target", "bag_asp_culture_target"), ("religion_target", "bag_asp_religion_target"))
SWITCHES = (("auto", "bag_asp_auto_on"), ("culture_speedup", "bag_asp_speedup_on"), ("log", "bag_asp_log_on"))


def shown_values() -> str:
    return "\n# Scope: country. A setting as a number, for the log.\n" + "\n".join(
        f"bag_asp_show_{name} = {{\n\tvalue = global_var:bag_asp_show_{name}\n}}\n" for name, var in NUMBERS)


def log_settings() -> str:
    numbers = ", ".join(
        f"{name} [GuiScope.SetRoot(GetPlayer.MakeScope).ScriptValue('bag_asp_show_{name}')|0]" for name, _ in NUMBERS)
    switches = "\n".join(
        f"\tif = {{\n\t\tlimit = {{ has_variable = {var} }}\n\t\tdebug_log = \"bag_asp: setting {name} on\"\n\t}}\n"
        f"\telse = {{\n\t\tdebug_log = \"bag_asp: setting {name} off\"\n\t}}" for name, var in SWITCHES)
    # A country variable printed through GetPlayer reads «none/any» in a
    # debug_log (his run 13.10 11:14); a global prints (docs/pitfalls/diagnosis.md).
    park = "\n".join(
        f"\tif = {{\n\t\tlimit = {{ has_variable = {var} }}\n"
        f"\t\tset_global_variable = {{ name = bag_asp_show_{name} value = var:{var} }}\n\t}}\n"
        f"\telse = {{\n\t\tset_global_variable = {{ name = bag_asp_show_{name} value = 0 }}\n\t}}"
        for name, var in NUMBERS)
    return f"""
# Scope: country. His ask 13.10: the settings as they stand, after he changed one.
bag_asp_log_settings = {{
{park}
\tdebug_log = "bag_asp: settings: {numbers}"
{switches}
}}
"""


def probe_effects(actions: dict[str, str]) -> str:
    """Probes, his run 13.10 07:12: integration that would not come back on top,
    a province at 52 % control passed over for ones at 30–43 %, and seats the
    log never named. What each pass reads, and what it leaves."""
    key = PAIRED_WITH
    sel = select(actions[key], "province")
    cflag = flag_of(select(actions[key], "culture"))
    order = "\n".join(
        f"\t\t\t\t\tflag:bag_asp_{k} = {{ debug_log = \"bag_asp: probe: in use, next down the order: {k}\" }}"
        for k, *_ in POOL)
    seats = []
    for k in sorted({act(r) for r, *_ in POOL}):
        ability = value(actions[k], "ability") or "adm"
        where = ""
        if k == key:
            where = (f"\t\t\tinteraction_target:target_1 ?= {{\n"
                     f"\t\t\t\tset_global_variable = {{ name = bag_asp_probe value = bag_asp_half_rank }}\n"
                     f"\t\t\t\tdebug_log = \"bag_asp: probe: its province, rank {PRINT}:\"\n"
                     f"\t\t\t\tdebug_log_scopes = no\n\t\t\t}}\n")
        seats.append(f"\t\telse_if = {{\n\t\t\tlimit = {{ cabinet_action = cabinet_action:{k} }}\n"
                     f"\t\t\tset_global_variable = {{ name = bag_asp_probe value = cabinet_member.{ability} }}\n"
                     f"\t\t\tdebug_log = \"bag_asp: probe: a seat on {k}, its advisor's {ability} {PRINT}\"\n"
                     f"{where}\t\t}}")
    seats_text = "\n".join(seats)
    return f"""
# Probe, his run 13.10 07:12: the order a full hand-out reads.
bag_asp_probe_order = {{
\tevery_in_list = {{
\t\tvariable = bag_asp_order
\t\tsave_temporary_scope_as = bag_asp_item
\t\tif = {{
\t\t\tlimit = {{ scope:actor = {{ is_target_in_variable_list = {{ name = bag_asp_used target = scope:bag_asp_item }} }} }}
\t\t\tscope:actor = {{
\t\t\t\tswitch = {{
\t\t\t\t\ttrigger = scope:bag_asp_item
{order}
\t\t\t\t}}
\t\t\t}}
\t\t}}
\t}}
}}

# Probe, his run 13.10 07:12: every seat as a pass leaves it.
bag_asp_probe_seats = {{
\tevery_cabinet = {{
\t\tif = {{
\t\t\tlimit = {{ NOT = {{ exists = cabinet_member }} }}
\t\t\tdebug_log = "bag_asp: probe: a seat has no advisor"
\t\t}}
\t\telse_if = {{
\t\t\tlimit = {{ has_cabinet_action = no }}
\t\t\tdebug_log = "bag_asp: probe: a seat is empty"
\t\t}}
{seats_text}
\t\telse = {{
\t\t\tdebug_log = "bag_asp: probe: a seat on an action outside the pool"
\t\t}}
\t\tif = {{
\t\t\tlimit = {{ cabinet_member ?= {{ has_variable = bag_asp_paired }} }}
\t\t\tdebug_log = "bag_asp: probe: (that seat is the control of an assimilation)"
\t\t}}
\t}}
\tremove_global_variable = bag_asp_probe
}}

# Probe, his run 13.10 07:12: every province at 40 % average control or more
# with a location integrated or conquered and no assimilation on it, and
# which test keeps «(до 50%)» from it. Scope: country (scope:actor).
bag_asp_probe_half = {{
\tif = {{
\t\tlimit = {{ has_variable = bag_asp_auto_on }}
{culture_choice(cflag)}\t\tscope:actor = {{
\t\t\tevery_province = {{
\t\t\t\tlimit = {{
\t\t\t\t\tprovince_average_control >= 0.4
\t\t\t\t\tNOT = {{ has_variable = bag_asp_busy_{key} }}
\t\t\t\t\tany_location_in_province = {{
\t\t\t\t\t\towner ?= scope:actor
\t\t\t\t\t\tOR = {{
\t\t\t\t\t\t\tintegration_level = integrated
\t\t\t\t\t\t\tintegration_level = conquered
\t\t\t\t\t\t}}
\t\t\t\t\t}}
\t\t\t\t}}
\t\t\t\tset_global_variable = {{ name = bag_asp_probe value = bag_asp_half_rank }}
\t\t\t\tif = {{
\t\t\t\t\tlimit = {{ NOT = {{ bag_asp_needs_half = yes }} }}
\t\t\t\t\tdebug_log = "bag_asp: probe: not taken, no location integrated or conquered short of half; rank {PRINT}:"
\t\t\t\t}}
\t\t\t\telse_if = {{
\t\t\t\t\tlimit = {{
\t\t\t\t\t\tNOT = {{
{target_test(sel, 7, actions, key)}
\t\t\t\t\t\t}}
\t\t\t\t\t}}
\t\t\t\t\tdebug_log = "bag_asp: probe: not taken, the game's own province test fails; rank {PRINT}:"
\t\t\t\t}}
\t\t\t\telse_if = {{
\t\t\t\t\tlimit = {{
\t\t\t\t\t\tNOT = {{
{indent(lead_rule(cflag), 7)}
\t\t\t\t\t\t}}
\t\t\t\t\t}}
\t\t\t\t\tdebug_log = "bag_asp: probe: not taken, an accepted culture leads the primary by {round(LEAD * 100)} points; rank {PRINT}:"
\t\t\t\t}}
\t\t\t\telse = {{
\t\t\t\t\tdebug_log = "bag_asp: probe: passes every test; rank {PRINT}:"
\t\t\t\t}}
\t\t\t\tdebug_log_scopes = no
\t\t\t}}
\t\t}}
\t}}
\tremove_global_variable = bag_asp_probe
}}
"""


# The value shift (his spec 12.10–13.10). Script sets the action, but the pair
# stays empty (his runs 12.10); the game's window picks it (value_window.py):
# opened, rows listed and the asked side pressed since 0.9.11. The flags live
# only between the mod's request and the press, or the wait running out.
SV_FLAGS = ("bag_asp_sv_open", "bag_asp_sv_left", "bag_asp_sv_right", "bag_asp_sv_pair")
SV_FILE = "in_game/common/societal_values/00_default.txt"
SV_ACTION = "change_societal_values"
SV_DEFINES = "loading_screen/common/defines/00_defines.txt"


def clear_sv(tabs: int) -> str:
    pad = "\t" * tabs
    return "\n".join(f"{pad}if = {{ limit = {{ has_variable = {v} }} remove_variable = {v} }}"
                     for v in SV_FLAGS)


def value_pairs(game: Path) -> list[str]:
    """Every pair the game defines, in its file's order: the rows of the CMF
    list «Общественные ценности», item n = the n-th pair. A pair the game adds
    in the middle shifts the saved ticks below it."""
    text = (game / SV_FILE).read_text(encoding="utf-8-sig")
    pairs = re.findall(r"^(\w+_vs_\w+) = \{", text, re.M)
    if "traditionalist_vs_innovative" not in pairs:
        raise SystemExit("societal values: the game's file no longer has traditionalist_vs_innovative")
    if len(pairs) > 50:
        raise SystemExit("societal values: more pairs than a CMM list holds")
    return pairs


def sv_formula(game: Path, actions: dict[str, str]) -> tuple[str, str, str]:
    """The advisor's monthly push, his screenshots 13.10 12:14: base × (1 +
    effective skill); effective skill = the country's cabinet efficiency +
    (ruler's + advisor's ability) × CABINET_ACTION_SKILL_MODIFIER + the
    advisor's own cabinet efficiency. 0.1 × (1 + 0.530 + 0.045 + 0.38) = 0.1956;
    with the seat on decentralization its push rose 0.25 → 0.4455."""
    action = actions[SV_ACTION]
    # value() reads words; the base is a decimal.
    b = re.search(r"^\s*societal_values\s*=\s*([\d.]+)", action, re.M)
    base = b.group(1) if b and float(b.group(1)) > 0 else None
    ability = value(action, "ability") or "adm"
    m = re.search(r"CABINET_ACTION_SKILL_MODIFIER\s*=\s*([\d.]+)",
                  (game / SV_DEFINES).read_text(encoding="utf-8-sig"))
    if not base or not m:
        raise SystemExit("societal values: the action's base push or the skill define moved")
    return base, ability, m.group(1)


def sv_push_value(game: Path, actions: dict[str, str]) -> str:
    base, ability, skill = sv_formula(game, actions)
    return f"""
# Scope: country; scope:bag_asp_seat is a seat. What its advisor would add to
# a pair each month on «{SV_ACTION}» (council.py, sv_formula).
bag_asp_sv_push = {{
\tvalue = modifier:country_cabinet_efficiency
\tif = {{
\t\tlimit = {{ exists = ruler }}
\t\tadd = {{
\t\t\tvalue = ruler.{ability}
\t\t\tmultiply = {skill}
\t\t}}
\t}}
\tadd = {{
\t\tvalue = scope:bag_asp_seat.cabinet_member.{ability}
\t\tmultiply = {skill}
\t}}
\tadd = scope:bag_asp_seat.cabinet_member.modifier:character_cabinet_efficiency
\tadd = 1
\tmultiply = {base}
}}
"""


SV_LOG = "[GuiScope.SetRoot(GetPlayer.MakeScope).ScriptValue('bag_asp_sv_n{n}_value')|{d}]"


def value_effects(game: Path, actions: dict[str, str]) -> str:
    """His spec 12.10–13.10: one seat, the best diplomat among the free ones,
    pushes the first ticked pair of «Общественные ценности» (in its order,
    toward its chosen side) that it can move at least one whole point.

    Where a pair stops, his screenshot 13.10 12:14 («не больше 51.92» at +0.51
    a month): at 100 × the monthly net push toward the side, 100 at most. So a
    pair qualifies when floor(that) > floor(where it stands now, toward the
    side) — his rule, hundredths do not count. The net push is
    monthly_towards_<side> − monthly_towards_<other side>, and the advisor's
    push on top unless the seat already pushes this pair: then it is in the
    modifier already (his run 13.10: 0.25 → 0.4455)."""
    _, ability, _ = sv_formula(game, actions)
    tests = []
    for i, pair in enumerate(value_pairs(game), 1):
        left, right = pair.split("_vs_")
        tests.append(f"""\t\t\t\tflag:bag_asp_sv_{pair} = {{
\t\t\t\t\tif = {{
\t\t\t\t\t\tlimit = {{ has_societal_value = societal_value_type:{pair} }}
\t\t\t\t\t\tset_local_variable = {{ name = bag_asp_sv_key value = flag:bag_asp_sv_{pair} }}
\t\t\t\t\t\tset_local_variable = {{ name = bag_asp_sv_i value = {i} }}
\t\t\t\t\t\tif = {{
\t\t\t\t\t\t\tlimit = {{ "variable_map(bag_asp_sv_side|local_var:bag_asp_sv_key)" >= 2 }}
\t\t\t\t\t\t\tset_local_variable = {{ name = bag_asp_sv_s value = 2 }}
\t\t\t\t\t\t\tset_local_variable = {{ name = bag_asp_sv_pos value = societal_value:{pair} }}
\t\t\t\t\t\t\tset_local_variable = {{
\t\t\t\t\t\t\t\tname = bag_asp_sv_net
\t\t\t\t\t\t\t\tvalue = {{
\t\t\t\t\t\t\t\t\tvalue = modifier:monthly_towards_{right}
\t\t\t\t\t\t\t\t\tsubtract = modifier:monthly_towards_{left}
\t\t\t\t\t\t\t\t}}
\t\t\t\t\t\t\t}}
\t\t\t\t\t\t\tbag_asp_sv_test = yes
\t\t\t\t\t\t\tif = {{
\t\t\t\t\t\t\t\tlimit = {{ has_variable = bag_asp_log_on }}
\t\t\t\t\t\t\t\tdebug_log = "bag_asp: values, {pair} toward {right}: stands at {SV_LOG.format(n=1, d=2)}, would stop at {SV_LOG.format(n=2, d=2)}"
\t\t\t\t\t\t\t}}
\t\t\t\t\t\t}}
\t\t\t\t\t\telse = {{
\t\t\t\t\t\t\tset_local_variable = {{ name = bag_asp_sv_s value = 1 }}
\t\t\t\t\t\t\tset_local_variable = {{
\t\t\t\t\t\t\t\tname = bag_asp_sv_pos
\t\t\t\t\t\t\t\tvalue = {{
\t\t\t\t\t\t\t\t\tvalue = societal_value:{pair}
\t\t\t\t\t\t\t\t\tmultiply = -1
\t\t\t\t\t\t\t\t}}
\t\t\t\t\t\t\t}}
\t\t\t\t\t\t\tset_local_variable = {{
\t\t\t\t\t\t\t\tname = bag_asp_sv_net
\t\t\t\t\t\t\t\tvalue = {{
\t\t\t\t\t\t\t\t\tvalue = modifier:monthly_towards_{left}
\t\t\t\t\t\t\t\t\tsubtract = modifier:monthly_towards_{right}
\t\t\t\t\t\t\t\t}}
\t\t\t\t\t\t\t}}
\t\t\t\t\t\t\tbag_asp_sv_test = yes
\t\t\t\t\t\t\tif = {{
\t\t\t\t\t\t\t\tlimit = {{ has_variable = bag_asp_log_on }}
\t\t\t\t\t\t\t\tdebug_log = "bag_asp: values, {pair} toward {left}: stands at {SV_LOG.format(n=1, d=2)}, would stop at {SV_LOG.format(n=2, d=2)}"
\t\t\t\t\t\t\t}}
\t\t\t\t\t\t}}
\t\t\t\t\t}}
\t\t\t\t}}""")
    asks = "\n".join(
        f"\t\t{i} = {{\n\t\t\tset_variable = {{ name = bag_asp_sv_pair value = societal_value_type:{pair} }}\n"
        f"\t\t\tdebug_log = \"bag_asp: values, the seat goes on {pair}\"\n\t\t}}"
        for i, pair in enumerate(value_pairs(game), 1))
    # The switch sits five tabs deep in bag_asp_sv_choose.
    switch = "\n".join("\t" + line for line in "\n".join(tests).split("\n"))
    on_values = f"has_cabinet_action = yes cabinet_action = cabinet_action:{SV_ACTION}"
    return f"""
# Scope: country (scope:actor). The «Приоритет» row of {SV_ACTION}.
bag_asp_place_{SV_ACTION} = {{
\t# A pass that only fills empty seats leaves a seat already on values alone.
\tif = {{
\t\tlimit = {{
\t\t\tany_cabinet = {{
\t\t\t\t{on_values}
\t\t\t\tNOT = {{ bag_asp_free_seat = yes }}
\t\t\t}}
\t\t}}
\t\tdebug_log = "bag_asp: values, the seat on values stays: this pass fills empty seats only"
\t}}
\telse = {{
\t\t# What the mod asked for last holds only while a seat is still on values.
\t\tif = {{
\t\t\tlimit = {{
\t\t\t\thas_variable = bag_asp_sv_cur
\t\t\t\tNOT = {{ any_cabinet = {{ {on_values} }} }}
\t\t\t}}
\t\t\tremove_variable = bag_asp_sv_cur
\t\t\tremove_variable = bag_asp_sv_cur_side
\t\t}}
\t\tordered_cabinet = {{
\t\t\tlimit = {{ bag_asp_free_seat = yes }}
\t\t\torder_by = cabinet_member.{ability}
\t\t\tsave_scope_as = bag_asp_seat
\t\t}}
\t\tif = {{
\t\t\tlimit = {{
\t\t\t\texists = scope:bag_asp_seat
\t\t\t\tcabinet_action:{SV_ACTION} = {{ is_available_for = scope:actor }}
\t\t\t}}
\t\t\tset_local_variable = {{ name = bag_asp_sv_p value = bag_asp_sv_push }}
\t\t\tif = {{
\t\t\t\tlimit = {{ has_variable = bag_asp_log_on }}
\t\t\t\tset_global_variable = {{ name = bag_asp_sv_n3 value = local_var:bag_asp_sv_p }}
\t\t\t\tdebug_log = "bag_asp: values, the best free diplomat would push {SV_LOG.format(n=3, d=4)} a month"
\t\t\t}}
\t\t\tbag_asp_sv_choose = yes
\t\t\tif = {{
\t\t\t\tlimit = {{
\t\t\t\t\thas_variable = bag_asp_sv_want
\t\t\t\t\thas_variable = bag_asp_sv_cur
\t\t\t\t\tvar:bag_asp_sv_want = var:bag_asp_sv_cur
\t\t\t\t\tvar:bag_asp_sv_want_side = var:bag_asp_sv_cur_side
\t\t\t\t}}
\t\t\t\tevery_cabinet = {{
\t\t\t\t\tlimit = {{ {on_values} }}
\t\t\t\t\tcabinet_member ?= {{ set_variable = {{ name = bag_asp_claimed value = yes }} }}
\t\t\t\t}}
\t\t\t\tdebug_log = "bag_asp: values, the seat keeps its pair"
\t\t\t}}
\t\t\telse_if = {{
\t\t\t\tlimit = {{ has_variable = bag_asp_sv_want }}
\t\t\t\t# One seat on values: another one still on it gives it up.
\t\t\t\tevery_cabinet = {{
\t\t\t\t\tlimit = {{
\t\t\t\t\t\t{on_values}
\t\t\t\t\t\tNOT = {{ this = scope:bag_asp_seat }}
\t\t\t\t\t}}
\t\t\t\t\tbag_asp_vacate = yes
\t\t\t\t}}
\t\t\t\tscope:bag_asp_seat = {{
\t\t\t\t\tbag_asp_vacate = yes
\t\t\t\t\tset_cabinet_action = {{
\t\t\t\t\t\ttype = cabinet_action:{SV_ACTION}
\t\t\t\t\t\t# Any pair: the target sets none (his run 12.10); the window picks it.
\t\t\t\t\t\ttarget = societal_value_type:traditionalist_vs_innovative
\t\t\t\t\t}}
\t\t\t\t\tcabinet_member = {{ set_variable = {{ name = bag_asp_claimed value = yes }} }}
\t\t\t\t}}
{clear_sv(4)}
\t\t\t\tset_variable = {{ name = bag_asp_sv_cur value = var:bag_asp_sv_want }}
\t\t\t\tset_variable = {{ name = bag_asp_sv_cur_side value = var:bag_asp_sv_want_side }}
\t\t\t\tset_variable = {{ name = bag_asp_sv_cab value = scope:bag_asp_seat }}
\t\t\t\tbag_asp_sv_ask = yes
\t\t\t}}
\t\t\telse = {{
\t\t\t\tdebug_log = "bag_asp: values, no ticked pair would move a whole point"
\t\t\t}}
\t\t\tif = {{ limit = {{ has_variable = bag_asp_sv_want }} remove_variable = bag_asp_sv_want }}
\t\t\tif = {{ limit = {{ has_variable = bag_asp_sv_want_side }} remove_variable = bag_asp_sv_want_side }}
\t\t}}
\t}}
}}

# Scope: country (scope:actor). var:bag_asp_sv_want (the pair's row) and
# var:bag_asp_sv_want_side (1 left, 2 right): the first ticked pair, in the
# list's order, that the seat would move at least one whole point.
bag_asp_sv_choose = {{
\tevery_in_list = {{
\t\tvariable = bag_asp_sv_used
\t\tsave_temporary_scope_as = bag_asp_sv_item
\t\tif = {{
\t\t\tlimit = {{ scope:actor = {{ NOT = {{ has_variable = bag_asp_sv_want }} }} }}
\t\t\tscope:actor = {{
\t\t\t\tswitch = {{
\t\t\t\t\ttrigger = scope:bag_asp_sv_item
{switch}
\t\t\t\t}}
\t\t\t}}
\t\t}}
\t}}
}}

# Scope: country. One pair, set up by bag_asp_sv_choose: local
# bag_asp_sv_i (its row), _s (side), _pos (where it stands toward the side),
# _net (the monthly net push toward it without this seat), _p (the seat's push).
bag_asp_sv_test = {{
\tif = {{
\t\tlimit = {{
\t\t\thas_variable = bag_asp_sv_cur
\t\t\tvar:bag_asp_sv_cur = local_var:bag_asp_sv_i
\t\t}}
\t\t# The seat pushes this pair: its push is in the modifier already. Pushed
\t\t# the other way, the pair is passed over: the window would not list it.
\t\tif = {{
\t\t\tlimit = {{ NOT = {{ var:bag_asp_sv_cur_side = local_var:bag_asp_sv_s }} }}
\t\t\tset_local_variable = {{ name = bag_asp_sv_net value = -10 }}
\t\t}}
\t}}
\telse = {{
\t\tchange_local_variable = {{ name = bag_asp_sv_net add = local_var:bag_asp_sv_p }}
\t}}
\tset_local_variable = {{
\t\tname = bag_asp_sv_stop
\t\tvalue = {{
\t\t\tvalue = local_var:bag_asp_sv_net
\t\t\tmultiply = 100
\t\t\tmax = 100
\t\t}}
\t}}
\tif = {{
\t\tlimit = {{ has_variable = bag_asp_log_on }}
\t\tset_global_variable = {{ name = bag_asp_sv_n1 value = local_var:bag_asp_sv_pos }}
\t\tset_global_variable = {{ name = bag_asp_sv_n2 value = local_var:bag_asp_sv_stop }}
\t}}
\tset_local_variable = {{
\t\tname = bag_asp_sv_stop
\t\tvalue = {{
\t\t\tvalue = local_var:bag_asp_sv_stop
\t\t\tfloor = yes
\t\t}}
\t}}
\tset_local_variable = {{
\t\tname = bag_asp_sv_at
\t\tvalue = {{
\t\t\tvalue = local_var:bag_asp_sv_pos
\t\t\tfloor = yes
\t\t}}
\t}}
\tif = {{
\t\tlimit = {{ local_var:bag_asp_sv_stop > local_var:bag_asp_sv_at }}
\t\tset_variable = {{ name = bag_asp_sv_want value = local_var:bag_asp_sv_i }}
\t\tset_variable = {{ name = bag_asp_sv_want_side value = local_var:bag_asp_sv_s }}
\t}}
}}

# Scope: country. The request for the hidden window: the pair, the side, open.
bag_asp_sv_ask = {{
\tswitch = {{
\t\ttrigger = var:bag_asp_sv_want
{asks}
\t}}
\tif = {{
\t\tlimit = {{ var:bag_asp_sv_want_side = 2 }}
\t\tset_variable = {{ name = bag_asp_sv_right value = yes }}
\t}}
\telse = {{
\t\tset_variable = {{ name = bag_asp_sv_left value = yes }}
\t}}
\tset_variable = {{ name = bag_asp_sv_open value = yes }}
\tdebug_log = "bag_asp: values, the window is asked to open and press"
}}
"""


# Scope: any. The value rule's numbers, parked in globals for the log.
SV_VALUES = "".join(f"\n{sv}_value = {{\n\tvalue = global_var:{sv}\n}}\n"
                    for sv in ("bag_asp_sv_n1", "bag_asp_sv_n2", "bag_asp_sv_n3"))


def value_guis() -> str:
    return f"""
# The list «Общественные ценности» draws only while this exists, and a change
# of it is committed here.
{MOD_ID}__values_on_changed = {{
\tscope = country
\tis_shown = {{ always = yes }}
\teffect = {{
\t\tcmm_apply_list_change = {{ setting = {MOD_ID}__values }}
\t\tbag_asp_rebuild = yes
\t\tif = {{
\t\t\tlimit = {{ has_variable = bag_asp_log_on }}
\t\t\tdebug_log = "bag_asp: you changed the list values"
\t\t}}
\t\tif = {{
\t\t\tlimit = {{ has_variable = bag_asp_auto_on }}
\t\t\tbag_asp_plan_all = yes
\t\t}}
\t}}
}}

# Called by the hidden window right after it asked the game's value window to
# open for the seat in var:bag_asp_sv_cab.
bag_asp_sv_opening = {{
\tscope = country
\tis_shown = {{ always = yes }}
\teffect = {{
\t\tdebug_log = "bag_asp: values, the hidden window asked the game's value window to open"
\t\tif = {{ limit = {{ has_variable = bag_asp_sv_open }} remove_variable = bag_asp_sv_open }}
\t}}
}}

# Called by a row of the value window right after it pressed a side.
bag_asp_sv_pressed = {{
\tscope = country
\tis_shown = {{ always = yes }}
\teffect = {{
\t\tdebug_log = "bag_asp: values, the value window pressed the asked side"
{clear_sv(2)}
\t}}
}}

# Called by the hidden window as it closes the panels after a press.
bag_asp_sv_closed = {{
\tscope = country
\tis_shown = {{ always = yes }}
\teffect = {{
\t\tdebug_log = "bag_asp: values, the panels close after the press"
\t}}
}}

# Called by the hidden window two seconds after it opened the value window.
# A side still asked means no row pressed: the window leaves out the pair the
# seat already pushes. The next pass then takes another pair, and comes back
# to this one when the seat is off it.
bag_asp_sv_timeout = {{
\tscope = country
\tis_shown = {{ always = yes }}
\teffect = {{
\t\tif = {{
\t\t\tlimit = {{
\t\t\t\tOR = {{
\t\t\t\t\thas_variable = bag_asp_sv_left
\t\t\t\t\thas_variable = bag_asp_sv_right
\t\t\t\t}}
\t\t\t}}
\t\t\tdebug_log = "bag_asp: values, no row pressed in two seconds; the panels close, the next pass takes another pair"
{clear_sv(3)}
\t\t\tif = {{
\t\t\t\tlimit = {{ has_variable = bag_asp_sv_cur }}
\t\t\t\tset_variable = {{ name = bag_asp_sv_cur_side value = 0 }}
\t\t\t}}
\t\t}}
\t}}
}}

# Called once by each row of the value window while a press is awaited: names
# the row's pair, so a run without a press still says what the window showed.
bag_asp_sv_row = {{
\tscope = country
\tis_shown = {{ always = yes }}
\teffect = {{
\t\tdebug_log = "bag_asp: values, the value window shows a row"
\t\tscope:sv ?= {{ debug_log_scopes = no }}
\t}}
}}
"""


def build(game: Path) -> dict[str, str]:
    """Generated files, by path under the mod, and localization rows."""
    actions = load_actions(game)
    missing = [act(k) for k, *_ in POOL if act(k) not in actions]
    if missing:
        raise SystemExit(f"council: the game has no cabinet action {', '.join(missing)}")
    for k, kind, *_ in POOL:
        # The game keeps its own automation off values; ours presses its window.
        if kind != "values" and value(actions[act(k)], "forbid_for_automation") == "yes":
            raise SystemExit(f"council: {k} is forbidden for automation in the game now")
    n = len(POOL)
    if n > 50:
        raise SystemExit("council: a CMM list holds at most 50 rows")

    reg = [f"""# assimilate_primary: the mod's CMF page. After any change here:
# python3 tools/check_cmm.py mods/assimilate_primary/in_game/common
# Rebuilt by tools/generate.py (tools/council.py).

# Scope: country
bag_asp_register = {{
\tcmm_register_bool_setting = {{
\t\tmod_id = {MOD_ID}
\t\tsetting_id = auto
\t\ttab_id = main
\t\tgroup_id = council
\t\tdefault_value = 0
\t}}
\tcmm_register_numeric_setting = {{
\t\tmod_id = {MOD_ID}
\t\tsetting_id = period
\t\ttab_id = main
\t\tgroup_id = council
\t\tdefault_value = 1
\t\tmin_value = 1
\t\tmax_value = 12
\t\tstep_value = 1
\t}}
\tcmm_register_numeric_setting = {{
\t\tmod_id = {MOD_ID}
\t\tsetting_id = review
\t\ttab_id = main
\t\tgroup_id = council
\t\tdefault_value = 1
\t\tmin_value = 0
\t\tmax_value = 60
\t\tstep_value = 1
\t}}
\t# His ask 13.10: everything he does and everything the mod does, in the log.
\tcmm_register_bool_setting = {{
\t\tmod_id = {MOD_ID}
\t\tsetting_id = log
\t\ttab_id = main
\t\tgroup_id = council
\t\tdefault_value = 0
\t}}
\tcmm_register_settings_list = {{
\t\tmod_id = {MOD_ID}
\t\tsetting_id = available
\t\ttab_id = actions
\t\titem_count = {n}
\t\tis_ordered = 0
\t}}
\tcmm_register_list_bool_field = {{
\t\tmod_id = {MOD_ID}
\t\tsetting_id = available
\t\tfield_id = use
\t\tdefault_value = 1
\t}}
\tcmm_register_settings_list = {{
\t\tmod_id = {MOD_ID}
\t\tsetting_id = priority
\t\ttab_id = actions
\t\titem_count = {n}
\t\tis_ordered = 1
\t}}
\tcmm_register_list_text_field = {{
\t\tmod_id = {MOD_ID}
\t\tsetting_id = priority
\t\tfield_id = ability
\t}}
"""]
    for setting, group, kind, opt in FINE:
        if kind == "dropdown":
            reg.append(f"\tcmm_register_dropdown_setting = {{\n\t\tmod_id = {MOD_ID}\n\t\tsetting_id = {setting}\n"
                       f"\t\ttab_id = fine\n\t\tgroup_id = {group}\n\t\tdefault_index = 1\n\t\toption_count = {opt}\n\t}}\n")
        else:
            reg.append(f"\tcmm_register_bool_setting = {{\n\t\tmod_id = {MOD_ID}\n\t\tsetting_id = {setting}\n"
                       f"\t\ttab_id = fine\n\t\tgroup_id = {group}\n\t\tdefault_value = {opt}\n\t}}\n")
    # His spec 12.10: in «Тонкие настройки», every pair the game has, in an
    # order he sets, each with a tick and the side to push it toward.
    pairs = value_pairs(game)
    reg.append(f"""\tcmm_register_settings_list = {{
\t\tmod_id = {MOD_ID}
\t\tsetting_id = values
\t\ttab_id = fine
\t\titem_count = {len(pairs)}
\t\tis_ordered = 1
\t}}
\tcmm_register_list_bool_field = {{
\t\tmod_id = {MOD_ID}
\t\tsetting_id = values
\t\tfield_id = use
\t\tdefault_value = 0
\t}}
\tcmm_register_list_dropdown_field = {{
\t\tmod_id = {MOD_ID}
\t\tsetting_id = values
\t\tfield_id = side
\t\tdefault_index = 1
\t\toption_count = 2
\t}}
""")
    for i, pair in enumerate(pairs, 1):
        reg.append(f"\tcmm_set_list_item_value = {{ mod_id = {MOD_ID} setting_id = values item = {i} value = flag:bag_asp_sv_{pair} }}\n")
    for i, (k, *_) in enumerate(POOL, 1):
        ability = value(actions[act(k)], "ability") or "adm"
        reg.append(f"\tcmm_set_list_item_value = {{ mod_id = {MOD_ID} setting_id = available item = {i} value = flag:bag_asp_{k} }}\n"
                   f"\tcmm_set_list_item_value = {{ mod_id = {MOD_ID} setting_id = priority item = {i} value = flag:bag_asp_{k} }}\n"
                   f"\tcmm_set_list_text_value = {{ mod_id = {MOD_ID} setting_id = priority field_id = ability item = {i} value = flag:bag_asp_ability_{ability} }}\n")
    reg.append(f"""
\tbag_asp_sync = yes
\tbag_asp_rebuild = yes
}}

# Scope: country. Settings into plain variables the pulse reads.
bag_asp_sync = {{
\tcmm_sync_bool_alias = {{ setting = {MOD_ID}__auto alias = bag_asp_auto_on }}
\tcmm_sync_setting_alias = {{ setting = {MOD_ID}__period alias = bag_asp_period }}
\tcmm_sync_setting_alias = {{ setting = {MOD_ID}__review alias = bag_asp_review }}
\tcmm_sync_setting_alias = {{ setting = {MOD_ID}__culture_target alias = bag_asp_culture_target }}
\tcmm_sync_bool_alias = {{ setting = {MOD_ID}__culture_speedup alias = bag_asp_speedup_on }}
\tcmm_sync_setting_alias = {{ setting = {MOD_ID}__religion_target alias = bag_asp_religion_target }}
\tcmm_sync_bool_alias = {{ setting = {MOD_ID}__log alias = bag_asp_log_on }}
}}

# Scope: country. The two lists into the order the pulse walks, and which rows
# show: «Доступные» only what this country can see, «Приоритет» only what is
# also in use.
bag_asp_rebuild = {{
\tif = {{
\t\tlimit = {{
\t\t\thas_variable_list = cmm_list_items_{MOD_ID}__available
\t\t\thas_variable_list = cmm_list_items_{MOD_ID}__priority
\t\t}}
\t\tcmm_build_list_bool_list = {{ setting = {MOD_ID}__available field_slot = 1 list_name = bag_asp_used }}
\t\tcmm_build_list_ordered_values = {{ setting = {MOD_ID}__priority list_name = bag_asp_order }}
""")
    for i, (k, *_) in enumerate(POOL, 1):
        reg.append(f"""\t\tif = {{
\t\t\tlimit = {{ cabinet_action:{act(k)} = {{ is_visible_for = root }} }}
\t\t\tcmm_show_list_item = {{ mod_id = {MOD_ID} setting_id = available item = {i} }}
\t\t}}
\t\telse = {{
\t\t\tcmm_hide_list_item = {{ mod_id = {MOD_ID} setting_id = available item = {i} }}
\t\t}}
\t\tif = {{
\t\t\tlimit = {{
\t\t\t\tcabinet_action:{act(k)} = {{ is_visible_for = root }}
\t\t\t\tis_target_in_variable_list = {{ name = bag_asp_used target = flag:bag_asp_{k} }}
\t\t\t}}
\t\t\tcmm_show_list_item = {{ mod_id = {MOD_ID} setting_id = priority item = {i} }}
\t\t}}
\t\telse = {{
\t\t\tcmm_hide_list_item = {{ mod_id = {MOD_ID} setting_id = priority item = {i} }}
\t\t}}
""")
    rank_switch = "\n".join(
        f"\t\t\t\t\tflag:bag_asp_{k} = {{ set_variable = {{ name = bag_asp_rank_{k} value = var:bag_asp_rank_counter }} }}"
        for k, *_ in POOL)
    rank_unused = "\n".join(
        f"\t\tif = {{\n\t\t\tlimit = {{ NOT = {{ is_target_in_variable_list = {{ name = bag_asp_used target = flag:bag_asp_{k} }} }} }}\n"
        f"\t\t\tchange_variable = {{ name = bag_asp_rank_{k} add = 100 }}\n\t\t}}"
        for k, *_ in POOL)
    reg.append(f"""\t\t# Each action's place in «Приоритет» (1 = top), +100 when not ticked:
\t\t# the emergency gives up the seat whose action ranks lowest.
\t\tset_variable = {{{{ name = bag_asp_rank_counter value = 0 }}}}
\t\tevery_in_list = {{{{
\t\t\tvariable = bag_asp_order
\t\t\tsave_temporary_scope_as = bag_asp_item
\t\t\troot = {{{{
\t\t\t\tchange_variable = {{{{ name = bag_asp_rank_counter add = 1 }}}}
\t\t\t\tswitch = {{{{
\t\t\t\t\ttrigger = scope:bag_asp_item
{rank_switch}
\t\t\t\t}}}}
\t\t\t}}}}
\t\t}}}}
{rank_unused}
\t\t# The «№» box of each row shows its place among the shown rows (cmf_dev_beta).
\t\tcmf_beta_list_renumber = {{{{ setting = bag_asp__priority }}}}
""".replace("{{", "{").replace("}}", "}"))
    # The pairs: ticked ones in the list's order, each one's side (1 left,
    # 2 right), and rows only for the pairs this country has.
    shown = "".join(
        f"\t\tif = {{\n\t\t\tlimit = {{ has_societal_value = societal_value_type:{pair} }}\n"
        f"\t\t\tcmm_show_list_item = {{ mod_id = {MOD_ID} setting_id = values item = {i} }}\n\t\t}}\n"
        f"\t\telse = {{\n\t\t\tcmm_hide_list_item = {{ mod_id = {MOD_ID} setting_id = values item = {i} }}\n\t\t}}\n"
        for i, pair in enumerate(pairs, 1))
    reg.append(f"""\t}}
\tif = {{
\t\tlimit = {{ has_variable_list = cmm_list_items_{MOD_ID}__values }}
\t\tcmm_build_list_bool_list = {{ setting = {MOD_ID}__values field_slot = 1 list_name = bag_asp_sv_used }}
\t\tcmm_build_list_field_map = {{ setting = {MOD_ID}__values field_slot = 2 map_name = bag_asp_sv_side multiply = 1 }}
{shown}\t\tcmf_beta_list_renumber = {{ setting = {MOD_ID}__values }}
\t}}
}}
""")

    reg.append(f"""
# Scope: country. var:cmf_callback names what was clicked; switch as in
# war_sliders.
bag_asp_handle_callback = {{
\tswitch = {{
\t\ttrigger = var:cmf_callback
\t\tflag:{MOD_ID}__auto = {{
\t\t\tbag_asp_sync = yes
\t\t\tif = {{
\t\t\t\tlimit = {{ has_variable = bag_asp_auto_on }}
\t\t\t\t# Ours and the game's «Совет» would fight over the same seats.
\t\t\t\tset_automated_system = {{ system = cabinet activate = no }}
\t\t\t\tdebug_log = "bag_asp: own council automation on, the game's «Совет» switched off"
\t\t\t\tset_variable = {{ name = bag_asp_months value = 0 }}
\t\t\t\tset_variable = {{ name = bag_asp_review_months value = 0 }}
\t\t\t\tbag_asp_plan_all = yes
\t\t\t}}
\t\t\telse = {{
\t\t\t\tdebug_log = "bag_asp: own council automation off"
\t\t\t}}
\t\t}}
\t\tflag:{MOD_ID}__period = {{ bag_asp_sync = yes }}
\t\tflag:{MOD_ID}__review = {{ bag_asp_sync = yes }}
\t\tflag:{MOD_ID}__culture_target = {{ bag_asp_sync = yes }}
\t\tflag:{MOD_ID}__culture_speedup = {{ bag_asp_sync = yes }}
\t\tflag:{MOD_ID}__religion_target = {{ bag_asp_sync = yes }}
\t\tflag:{MOD_ID}__log = {{ bag_asp_sync = yes }}
\t}}
\t# His ask 13.10: what he changes goes into the log, with every setting after it.
\tif = {{
\t\tlimit = {{ has_variable = bag_asp_log_on }}
\t\tdebug_log = "bag_asp: you changed a setting"
\t\tbag_asp_log_settings = yes
\t}}
}}
""")
    effects = "".join(reg)

    switch = "\n".join(
        f"\t\t\t\t\tflag:bag_asp_{k} = {{ bag_asp_place_{k} = yes"  + " }"
        for k, *_ in POOL)
    run = f"""# assimilate_primary: the mod's own council automation, the monthly pass.
# Rebuilt by tools/generate.py (tools/council.py).

# Scope: country. Every month for a player with the checkbox on, from CMF's
# monthly pulse (the one CM's auto-build runs on). Every `review` months
# (0 = never) all seats are handed out again; otherwise every `period` months
# only seats without an action are filled.
bag_asp_tick = {{
\tif = {{
\t\tlimit = {{ NOT = {{ has_variable = bag_asp_period }} }}
\t\tbag_asp_sync = yes
\t}}
\tif = {{
\t\tlimit = {{ NOT = {{ has_variable = bag_asp_months }} }}
\t\tset_variable = {{ name = bag_asp_months value = 0 }}
\t}}
\tif = {{
\t\tlimit = {{ NOT = {{ has_variable = bag_asp_review_months }} }}
\t\tset_variable = {{ name = bag_asp_review_months value = 0 }}
\t}}
\tchange_variable = {{ name = bag_asp_months add = 1 }}
\tchange_variable = {{ name = bag_asp_review_months add = 1 }}
\tdebug_log = "bag_asp: month"
\tif = {{
\t\tlimit = {{
\t\t\tvar:bag_asp_review > 0
\t\t\tvar:bag_asp_review_months >= var:bag_asp_review
\t\t}}
\t\tset_variable = {{ name = bag_asp_review_months value = 0 }}
\t\tset_variable = {{ name = bag_asp_months value = 0 }}
\t\tbag_asp_plan_all = yes
\t}}
\telse_if = {{
\t\tlimit = {{ var:bag_asp_months >= var:bag_asp_period }}
\t\tset_variable = {{ name = bag_asp_months value = 0 }}
\t\tbag_asp_plan_fill = yes
\t}}
}}

# Scope: country. Every seat handed out down «Приоритет».
bag_asp_plan_all = {{
\tdebug_log = "bag_asp: handing out every seat"
\tbag_asp_plan = yes
}}

# Scope: country. Only seats without an action: the others are taken as chosen.
bag_asp_plan_fill = {{
\tdebug_log = "bag_asp: filling empty seats"
\tset_variable = {{ name = bag_asp_fill_only value = yes }}
\tbag_asp_plan = yes
\tremove_variable = bag_asp_fill_only
}}

# Scope: country. Down «Приоритет», each action in use first keeps the seats
# already on it, then takes free seats, the advisor best in its skill first,
# while it has a target and a free seat is left. A seat is free until this pass
# chose it; at the end, seats nothing could take keep what they had.
bag_asp_plan = {{
\tsave_scope_as = actor
\t# The lists may have moved without their callback (a typed place goes
\t# through the console), so the order is read afresh every pass.
\tbag_asp_rebuild = yes
\t# His ask 13.10: the seats as the pass finds them, so what he changed by
\t# hand between two passes shows against the last pass's «after».
\tif = {{
\t\tlimit = {{ has_variable = bag_asp_log_on }}
\t\tdebug_log = "bag_asp: the seats before the pass:"
\t\tbag_asp_probe_seats = yes
\t}}
\tif = {{
\t\tlimit = {{ NOT = {{ any_in_list = {{ variable = bag_asp_used }} }} }}
\t\tdebug_log = "bag_asp: no action is ticked in use"
\t}}
\t# His rule 13.10: an assimilation whose province has every location at
\t# half is freed, unless the full row is in use; before the marking, so its
\t# control seat goes with it.
\tif = {{
\t\tlimit = {{ NOT = {{ is_target_in_variable_list = {{ name = bag_asp_used target = flag:bag_asp_promote_culture_full }} }} }}
\t\tevery_cabinet = {{
\t\t\tlimit = {{
\t\t\t\thas_cabinet_action = yes
\t\t\t\tcabinet_action = cabinet_action:promote_culture
\t\t\t\tinteraction_target:target_1 ?= {{ NOT = {{ bag_asp_needs_half = yes }} }}
\t\t\t}}
\t\t\tstop_cabinet_action = {{}}
\t\t\tdebug_log = "bag_asp: an assimilation freed, every location of its province is at half"
\t\t}}
\t}}
\tbag_asp_mark_busy = yes
\tbag_asp_unpair = yes
\tif = {{
\t\tlimit = {{
\t\t\thas_variable = bag_asp_log_on
\t\t\tNOT = {{ has_variable = bag_asp_fill_only }}
\t\t}}
\t\tbag_asp_probe_order = yes
\t\tbag_asp_probe_half = yes
\t}}
\tif = {{
\t\tlimit = {{ has_variable = bag_asp_fill_only }}
\t\tevery_cabinet = {{
\t\t\tlimit = {{
\t\t\t\thas_cabinet_action = yes
\t\t\t\texists = cabinet_member
\t\t\t}}
\t\t\tcabinet_member = {{ set_variable = {{ name = bag_asp_claimed value = yes }} }}
\t\t}}
\t}}
\tevery_in_list = {{
\t\tvariable = bag_asp_order
\t\tsave_temporary_scope_as = bag_asp_item
\t\tif = {{
\t\t\tlimit = {{
\t\t\t\tscope:actor = {{
\t\t\t\t\tis_target_in_variable_list = {{ name = bag_asp_used target = scope:bag_asp_item }}
\t\t\t\t\tany_cabinet = {{ bag_asp_free_seat = yes }}
\t\t\t\t}}
\t\t\t}}
\t\t\tscope:actor = {{
\t\t\t\tswitch = {{
\t\t\t\t\ttrigger = scope:bag_asp_item
{switch}
\t\t\t\t}}
\t\t\t}}
\t\t}}
\t}}
\tif = {{
\t\tlimit = {{ any_cabinet = {{ bag_asp_free_seat = yes }} }}
\t\tdebug_log = "bag_asp: a seat is left as it was, nothing in use fits it"
\t}}
\tif = {{
\t\tlimit = {{ has_variable = bag_asp_log_on }}
\t\tdebug_log = "bag_asp: the seats after the pass:"
\t\tbag_asp_probe_seats = yes
\t}}
\tevery_cabinet = {{
\t\tlimit = {{ exists = cabinet_member }}
\t\tcabinet_member = {{
\t\t\tif = {{
\t\t\t\tlimit = {{ has_variable = bag_asp_claimed }}
\t\t\t\tremove_variable = bag_asp_claimed
\t\t\t}}
\t\t}}
\t}}
\tbag_asp_clear_busy = yes
}}

"""
    BUSY.clear()
    tries = "\n".join(try_effect(k, kind, order, gate, actions) for k, kind, order, gate in POOL if kind != "values")
    tries += "\n" + "\n".join(try_effect(k, "province", None, "", actions, at="scope:bag_asp_at") for k in SPEEDUP)
    def pass_(effect: str) -> str:
        return "\n".join(
            f"\t\tif = {{\n\t\t\tlimit = {{ cabinet_action = cabinet_action:{k} }}\n"
            f"\t\t\tinteraction_target:{f} ?= {{ {effect.format(k=k)} }}\n\t\t}}"
            for k, f in sorted(BUSY))
    keys = sorted({k for k, _ in BUSY})
    sweep = "\n".join(f"\t\tremove_variable = bag_asp_busy_{k}" for k in keys)
    busy_any = " ".join(f"has_variable = bag_asp_busy_{k}" for k in keys)
    stopped = "\n".join(
        f"\t\tif = {{ limit = {{ cabinet_action = cabinet_action:{k} }} debug_log = \"bag_asp: {k} stopped on a seat\" }}"
        for k in sorted({act(r) for r, *_ in POOL}))
    run += f"""# Scope: country. Mark every target a seat already works on, for the copied
# «already performing the same task» triggers; unmark after the pass.
bag_asp_mark_busy = {{
\tevery_cabinet = {{
\t\tlimit = {{ has_cabinet_action = yes }}
{pass_("set_variable = {{ name = bag_asp_busy_{k} value = yes }}")}
\t}}
}}

# Marks a stopped seat left behind stayed for good until 0.9.8 (his run 13.10
# 10:02: a control action was refused on a province whose own had been
# stopped a month before), so every mark is swept, not only the seats' own.
bag_asp_clear_busy = {{
\tevery_cabinet = {{
\t\tlimit = {{ has_cabinet_action = yes }}
{pass_("remove_variable = bag_asp_busy_{k}")}
\t}}
\tevery_province = {{
\t\tlimit = {{ bag_asp_busy_any = yes }}
{sweep}
\t}}
\tevery_province = {{
\t\tarea ?= {{
\t\t\tif = {{
\t\t\t\tlimit = {{ bag_asp_busy_any = yes }}
{sweep.replace(chr(9) * 2, chr(9) * 4)}
\t\t\t}}
\t\t}}
\t}}
\tevery_estate = {{
\t\tlimit = {{ bag_asp_busy_any = yes }}
{sweep}
\t}}
}}

# Scope: cabinet (a seat). Stops its action and takes back what the pass gave
# it: the busy mark on its target and the bond of a control seat. Every seat
# the pass takes from another action goes through here.
bag_asp_vacate = {{
\tif = {{
\t\tlimit = {{ has_cabinet_action = yes }}
{pass_("remove_variable = bag_asp_busy_{k}")}
{stopped}
\t\tstop_cabinet_action = {{}}
\t}}
\tcabinet_member ?= {{
\t\tif = {{
\t\t\tlimit = {{ has_variable = bag_asp_paired }}
\t\t\tremove_variable = bag_asp_paired
\t\t}}
\t}}
}}

"""
    run += tries
    run += value_effects(game, actions)
    # A seat's rank is its action's row; where two rows share an action, the
    # row whose gate holds now, gated rows tried first.
    shared = {act(k) for k, *_ in POOL if act(k) != k}
    rows = sorted((r for r in POOL if r[0] != "recovery_effort"),
                  key=lambda r: not (act(r[0]) in shared and (r[3] or r[0] in ROW_SEAT)))

    def seat_is(k: str, gate: str) -> str:
        if k == "paired":
            return "bag_asp_paired_seat = yes"
        own = f"cabinet_action = cabinet_action:{act(k)}"
        if act(k) in SPEEDUP:
            own += " NOT = { bag_asp_paired_seat = yes }"
        if act(k) in shared and k in ROW_SEAT:
            own += f" {ROW_SEAT[k]}"
        return own + (f" scope:actor = {{ {gate} }}" if act(k) in shared and gate else "")
    # A control seat bound to an assimilation ranks as the assimilation.
    ranked = [("paired", PAIRED_WITH, "")] + [(k, k, g) for k, _, _, g in rows]
    seat_rank = "\n".join(
        f"\t\t\telse_if = {{ limit = {{ {seat_is(k, g)} }} add = scope:actor.var:bag_asp_rank_{r} }}"
        for k, r, g in ranked)
    seat_below = "\n".join(
        f"\t\t\t\t\t\t\tAND = {{ {seat_is(k, g)} scope:actor.var:bag_asp_rank_{r} > scope:actor.var:bag_asp_rank_recovery_effort }}"
        for k, r, g in ranked)
    run += f"""
# Scope: country. While the «devastated locations» alert shows (its banner,
# bag_alert_banner.gui): as it appears, then every second. Costs a look
# over the provinces unless one has a location below zero and no recovery;
# then each such province, most devastated first, gets recovery: an empty seat
# first, else the seat whose action ranks lowest in «Приоритет» — only among
# actions ranked below recovery (unticked ones count as below). Actions
# outside the pool stay.
bag_asp_emergency = {{
\tif = {{
\t\tlimit = {{
\t\t\thas_variable = bag_asp_auto_on
\t\t\tis_target_in_variable_list = {{ name = bag_asp_used target = flag:bag_asp_recovery_effort }}
\t\t\tany_province = {{ any_location_in_province = {{ prosperity < 0 }} }}
\t\t}}
\t\tsave_scope_as = actor
\t\tbag_asp_mark_busy = yes
\t\tif = {{
\t\t\tlimit = {{
\t\t\t\tany_province = {{
\t\t\t\t\tNOT = {{ has_variable = bag_asp_busy_recovery_effort }}
\t\t\t\t\tany_location_in_province = {{ prosperity < 0 }}
\t\t\t\t}}
\t\t\t}}
\t\t\tbag_asp_rebuild = yes
\t\t\t# One province per seat, until none is left without recovery or no
\t\t\t# seat below recovery is free to give.
\t\t\tset_variable = {{ name = bag_asp_em_go value = yes }}
\t\t\twhile = {{
\t\t\t\tlimit = {{
\t\t\t\t\thas_variable = bag_asp_em_go
\t\t\t\t\tany_province = {{
\t\t\t\t\t\tNOT = {{ has_variable = bag_asp_busy_recovery_effort }}
\t\t\t\t\t\tany_location_in_province = {{ prosperity < 0 }}
\t\t\t\t\t}}
\t\t\t\t}}
\t\t\t\tremove_variable = bag_asp_em_go
\t\t\t\tordered_cabinet = {{
\t\t\t\t\tlimit = {{
\t\t\t\t\t\texists = cabinet_member
\t\t\t\t\t\tOR = {{
\t\t\t\t\t\t\thas_cabinet_action = no
{seat_below}
\t\t\t\t\t\t}}
\t\t\t\t\t}}
\t\t\t\t\torder_by = {{
\t\t\t\t\t\tvalue = 0
\t\t\t\t\t\tif = {{ limit = {{ has_cabinet_action = no }} add = 1000 }}
{seat_rank.replace(chr(9) * 3, chr(9) * 6)}
\t\t\t\t\t\tadd = {{
\t\t\t\t\t\t\tvalue = cabinet_member.dip
\t\t\t\t\t\t\tdivide = 100
\t\t\t\t\t\t}}
\t\t\t\t\t}}
\t\t\t\t\tsave_scope_as = bag_asp_seat
\t\t\t\t\tbag_asp_try_recovery_effort = yes
\t\t\t\t\tif = {{
\t\t\t\t\t\tlimit = {{ exists = cabinet_member }}
\t\t\t\t\t\tcabinet_member = {{
\t\t\t\t\t\t\tif = {{
\t\t\t\t\t\t\t\tlimit = {{ has_variable = bag_asp_claimed }}
\t\t\t\t\t\t\t\tremove_variable = bag_asp_claimed
\t\t\t\t\t\t\t}}
\t\t\t\t\t\t}}
\t\t\t\t\t}}
\t\t\t\t}}
\t\t\t\tif = {{
\t\t\t\t\tlimit = {{ has_variable = bag_asp_placed }}
\t\t\t\t\tdebug_log = "bag_asp: emergency, a seat moved to recovery"
\t\t\t\t\tremove_variable = bag_asp_placed
\t\t\t\t\tset_variable = {{ name = bag_asp_em_go value = yes }}
\t\t\t\t}}
\t\t\t}}
\t\t\tif = {{
\t\t\t\tlimit = {{ has_variable = bag_asp_em_go }}
\t\t\t\tremove_variable = bag_asp_em_go
\t\t\t}}
\t\t}}
\t\tbag_asp_clear_busy = yes
\t}}
}}
"""
    run += "\n" + "\n".join(place_effect(k, gate, actions) for k, kind, _, gate in POOL if kind != "values")
    run += "\n" + "\n".join(move_effect(k, actions) for k, kind, *_ in POOL if kind != "values")
    run += pair_effects(actions)
    run += probe_effects(actions)
    run += log_settings()

    on_actions = f"""# assimilate_primary: the CMF page and the monthly pass. The engine merges
# on_actions lists, so these add to CMF's own.
# Rebuilt by tools/generate.py (tools/council.py).
cmf_on_mod_registration = {{
\ton_actions = {{
\t\tbag_asp_on_register
\t}}
}}

cmf_on_callback = {{
\ton_actions = {{
\t\tbag_asp_on_callback
\t}}
}}

# CMF's own monthly pulse for players, the one CM's auto-build runs on in his
# games. 0.5.0 joined the game's monthly_country_pulse, and in his run of 12.10
# nothing the pass writes came in a dozen months; whether that leaf ran at all is
# not known, so the pulse moved to the proven one and the tick logs each month.
cmf_monthly_human_country_pulse = {{
\ton_actions = {{
\t\tbag_asp_on_month
\t}}
}}

# His rule 13.10: a new advisor hands every seat out at once. The game's own
# effect on it stays: these lists merge. root = country, scope:target = the
# advisor. A death is not on it; the monthly hand-out covers that.
on_cabinet_assigned = {{
\ton_actions = {{
\t\tbag_asp_on_cabinet_change
\t}}
}}

# His ask 13.10: an advisor leaving is logged too (named, with the log on).
# root = country, scope:target = the advisor; fired before on_cabinet_assigned
# when one replaces another, not on a death.
on_cabinet_removed = {{
\ton_actions = {{
\t\tbag_asp_on_cabinet_removed
\t}}
}}

# Scope: country
bag_asp_on_cabinet_change = {{
\ttrigger = {{
\t\thas_variable = bag_asp_auto_on
\t}}
\teffect = {{
\t\tdebug_log = "bag_asp: an advisor was assigned"
\t\tif = {{
\t\t\tlimit = {{ has_variable = bag_asp_log_on }}
\t\t\tscope:target ?= {{ debug_log_scopes = no }}
\t\t}}
\t\tbag_asp_plan_all = yes
\t}}
}}

# Scope: country
bag_asp_on_cabinet_removed = {{
\ttrigger = {{
\t\thas_variable = bag_asp_auto_on
\t}}
\teffect = {{
\t\tdebug_log = "bag_asp: an advisor left the cabinet"
\t\tif = {{
\t\t\tlimit = {{ has_variable = bag_asp_log_on }}
\t\t\tscope:target ?= {{ debug_log_scopes = no }}
\t\t}}
\t}}
}}

# Scope: country
bag_asp_on_register = {{
\teffect = {{
\t\tbag_asp_register = yes
\t}}
}}

# Scope: country
bag_asp_on_callback = {{
\teffect = {{
\t\tbag_asp_handle_callback = yes
\t}}
}}

# Scope: country
bag_asp_on_month = {{
\ttrigger = {{
\t\thas_variable = bag_asp_auto_on
\t}}
\teffect = {{
\t\tbag_asp_tick = yes
\t}}
}}
"""

    guis = ""
    for s in LISTS:
        guis += f"""# The list draws only while this exists, and a list change is committed here.
{MOD_ID}__{s}_on_changed = {{
\tscope = country
\tis_shown = {{ always = yes }}
\teffect = {{
\t\tcmm_apply_list_change = {{ setting = {MOD_ID}__{s} }}
\t\tbag_asp_rebuild = yes
\t\tif = {{
\t\t\tlimit = {{ has_variable = bag_asp_log_on }}
\t\t\tdebug_log = "bag_asp: you changed the list {s}"
\t\t\tsave_scope_as = actor
\t\t\tbag_asp_probe_order = yes
\t\t}}
\t\t# His rule 13.10: a change of the lists hands every seat out at once.
\t\tif = {{
\t\t\tlimit = {{ has_variable = bag_asp_auto_on }}
\t\t\tbag_asp_plan_all = yes
\t\t}}
\t}}
}}

"""
    guis = "# assimilate_primary: the lists' callbacks. Rebuilt by tools/generate.py.\n\n" + guis
    guis += f"""# Called by the «devastated locations» banner (bag_alert_banner.gui) while
# the automation is on: once as it appears, then every second.
bag_asp_devastated = {{
\tscope = country
\tis_shown = {{ always = yes }}
\teffect = {{
\t\tbag_asp_emergency = yes
\t}}
}}

# Called once as the banner appears: the probe that says the watch sees it.
bag_asp_devastated_seen = {{
\tscope = country
\tis_shown = {{ always = yes }}
\teffect = {{
\t\tdebug_log = "bag_asp: the devastated locations alert is showing"
\t}}
}}
""" + value_guis()
    # His rule 13.10: a province without control assimilates nothing, so it is
    # taken only while a control action can come with it.
    fits = []
    for k in SPEEDUP:
        fits.append(f"\t\tAND = {{\n\t\t\tcabinet_action:{k} = {{ is_available_for = scope:actor }}\n"
                    f"\t\t\tscope:actor = {{ NOT = {{ any_cabinet = {{ has_cabinet_action = yes cabinet_action = cabinet_action:{k} }} }} }}\n"
                    f"{target_test(select(actions[k], 'province'), 3, actions, k)}\n\t\t}}")
    reachable = f"""
# Scope: province; scope:actor is the country. A control action of the
# speedup can be put on it now: available, not on a seat yet (one seat each),
# and its target test holds here.
bag_asp_control_fits = {{
\tOR = {{
{chr(10).join(fits)}
\t}}
}}

# Scope: province; scope:actor is the country, scope:bag_asp_seat the seat
# about to assimilate. His rule 13.10: control above zero, or «Ускорять
# контролем» on, another free seat, and a control action that fits here.
bag_asp_control_reachable = {{
\tOR = {{
\t\tprovince_average_control > 0
\t\tAND = {{
\t\t\tscope:actor = {{
\t\t\t\thas_variable = bag_asp_speedup_on
\t\t\t\tany_cabinet = {{
\t\t\t\t\tbag_asp_free_seat = yes
\t\t\t\t\tNOT = {{ this = scope:bag_asp_seat }}
\t\t\t\t}}
\t\t\t}}
\t\t\tbag_asp_control_fits = yes
\t\t}}
\t}}
}}
"""
    triggers = """# assimilate_primary: triggers of the council pass. Rebuilt by tools/generate.py.

# Scope: cabinet (a seat). It has an advisor whom this pass has not chosen yet.
bag_asp_free_seat = {
\texists = cabinet_member
\tcabinet_member = { NOT = { has_variable = bag_asp_claimed } }
}
""" + f"""
# Scope: location. No primary or accepted culture holds half of it.
bag_asp_short_of_half = {{
\tNAND = {{
\t\texists = dominant_culture
\t\tdominant_culture = {{ is_primary_or_accepted_in = scope:actor }}
\t\t"culture_percentage(dominant_culture)" >= 0.5
\t}}
}}

# Scope: province; scope:actor is the country. His rule 13.10, by status: a
# location of it is integrated but not core yet, or conquered and short of half
# (conquered at half needs integration, not assimilation).
bag_asp_needs_half = {{
\tany_location_in_province = {{
\t\towner ?= scope:actor
\t\tOR = {{
\t\t\tintegration_level = integrated
\t\t\tAND = {{
\t\t\t\tintegration_level = conquered
\t\t\t\tbag_asp_short_of_half = yes
\t\t\t}}
\t\t}}
\t}}
}}

# Scope: any target. A busy mark of the pass is on it.
bag_asp_busy_any = {{
\tOR = {{ {busy_any} }}
}}

# Scope: cabinet. A control action bound to an assimilation («Ускорять контролем»).
bag_asp_paired_seat = {{
\thas_cabinet_action = yes
\tOR = {{
{chr(10).join(f"{chr(9)*2}cabinet_action = cabinet_action:{k}" for k in SPEEDUP)}
\t}}
\tcabinet_member ?= {{ has_variable = bag_asp_paired }}
}}
""" + reachable

    return {
        "in_game/common/scripted_triggers/bag_asp_council_triggers.txt": triggers,
        "in_game/common/script_values/bag_asp_values.txt": VALUES + shown_values() + SV_VALUES + sv_push_value(game, actions),
        "in_game/common/scripted_effects/bag_asp_cmm_effects.txt": effects,
        "in_game/common/scripted_effects/bag_asp_council_effects.txt": run,
        "in_game/common/on_action/bag_asp_cmf_on_actions.txt": on_actions,
        "in_game/common/scripted_guis/bag_asp_scripted_gui.txt": guis,
        # The watch is a child of the game's alert banner: tools/alert_banner.py.
        alert_banner.PATH: alert_banner.build(game),
        # The value shift presses the game's own window: tools/value_window.py.
        **value_window.build(game),
    }


def loc_rows(game: Path, language: str) -> dict[str, str]:
    """List row labels: the game's own linked action names."""
    src = (game / f"main_menu/localization/{language}/government_l_{language}.yml").read_text(encoding="utf-8-sig")
    names = dict(re.findall(r'^ (\w+):\d* "(.*)"\s*$', src, re.M))
    rows = {}
    for i, (k, *_) in enumerate(POOL, 1):
        if act(k) not in names:
            raise SystemExit(f"council: the game has no {language} name for {act(k)}")
        # The game's own linked name, as CM writes its building rows
        # ([ShowBuildingTypeName]): it hovers the game's tooltip of the action.
        suffix, desc = ROW_NOTE.get(k, {}).get(language, ("", ""))
        name = f"[ShowCabinetActionName('{act(k)}')]{suffix}"
        for s in LISTS:
            rows[f"{MOD_ID}__{s}_i{i}_name"] = name
            if desc:
                rows[f"{MOD_ID}__{s}_i{i}_desc"] = desc
    rows.update(FINE_LOC[language])
    for group in sorted({g for _, g, *_ in FINE}):
        # The plain name: the run of 13.10 flooded the logs with assimilation's
        # progress text read without a province, cause not placed; a linked name
        # here was new in 0.9.0, so it goes.
        rows[f"{MOD_ID}__fine__{group}_name"] = f"${group}$"
    rows.update(VALUES_LOC[language])
    # A pair's row: the game's own name of the pair; its tooltip, the two sides.
    lw, rw = SIDE_WORDS[language]
    for i, pair in enumerate(value_pairs(game), 1):
        if pair not in names:
            raise SystemExit(f"council: the game has no {language} name for {pair}")
        left, right = pair.split("_vs_")
        rows[f"{MOD_ID}__values_i{i}_name"] = f"${pair}$"
        rows[f"{MOD_ID}__values_i{i}_desc"] = (f"{lw}: [ShowSocietyDirectionName('{left}')], "
                                               f"{rw}: [ShowSocietyDirectionName('{right}')].")
    for ab, text in ABILITY[language].items():
        rows[f"bag_asp_ability_{ab}"] = text
    return rows
