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
    ("promote_culture", "culture", "population", ""),
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
]

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

# The three lists over the pool; «Тонкие настройки» is a skeleton for now (his
# ask 12.10: the tab first, each action's own settings later).
LISTS = ("available", "priority", "tuning")
TUNING_NONE = {"english": "none yet", "russian": "пока нет"}

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


def try_effect(key: str, kind: str, order: str | None, gate: str, actions: dict[str, str]) -> str:
    action = actions[key]
    if order == "INTEGRATION":
        order = INTEGRATION
    elif order == "RECOVERY":
        order = RECOVERY
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
            f"\t\t\t\tdebug_log = \"bag_asp: seat set to {key}\"")

    def assign(params: str, flag: str = "") -> str:
        mark = ""
        if flag:
            BUSY.add((key, flag))
            mark = f"\t\t\t\tscope:bag_asp_pick = {{ set_variable = {{ name = bag_asp_busy_{key} value = yes }} }}\n"
        # A seat taken from a lower action is stopped first; set_cabinet_action
        # is not known to replace a running action by itself.
        return (f"\t\t\t\tscope:bag_asp_seat = {{\n"
                f"\t\t\t\t\tif = {{\n\t\t\t\t\t\tlimit = {{ has_cabinet_action = yes }}\n"
                f"\t\t\t\t\t\tstop_cabinet_action = {{}}\n\t\t\t\t\t}}\n"
                f"\t\t\t\t\tset_cabinet_action = {{ type = cabinet_action:{key}{params} }}\n"
                f"\t\t\t\t}}\n" + mark + done)

    if kind == "country":
        inner = assign("").replace("\t\t\t\t", "\t\t", 1).replace("\n\t\t\t\t", "\n\t\t")
    elif kind in ("province", "capital"):
        sel = select(action, "province")
        flag = flag_of(sel)
        if kind == "province":
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
        rule = (f"\t\t\t\t\t# His rule 05.10: where an accepted culture leads the primary by\n"
                f"\t\t\t\t\t# {round(LEAD * 100)} points, do not push the primary.\n"
                f"\t\t\t\t\tNAND = {{\n\t\t\t\t\t\texists = dominant_culture\n"
                f"\t\t\t\t\t\tNOT = {{ dominant_culture = scope:actor.culture }}\n"
                f"\t\t\t\t\t\tdominant_culture = {{ is_primary_or_accepted_in = scope:actor }}\n"
                f"\t\t\t\t\t\t\"culture_percentage(dominant_culture)\" >= {{\n"
                f"\t\t\t\t\t\t\tvalue = \"culture_percentage(scope:actor.culture)\"\n"
                f"\t\t\t\t\t\t\tadd = {LEAD}\n\t\t\t\t\t\t}}\n\t\t\t\t\t}}")
        inner = (f"\t\tscope:actor.culture = {{ save_scope_as = {cflag} }}\n"
                 f"\t\tscope:actor = {{\n\t\t\tordered_province = {{\n\t\t\t\tlimit = {{\n"
                 f"{target_test(sel, 5, actions, key)}\n{rule}\n\t\t\t\t}}\n\t\t\t\torder_by = {order}\n"
                 f"\t\t\t\tsave_temporary_scope_as = bag_asp_pick\n"
                 f"{assign(f' {cflag} = scope:{cflag} {pflag} = scope:bag_asp_pick', pflag)}\n\t\t\t}}\n\t\t}}")
    elif kind == "religion":
        sel = select(action, "province")
        rflag = flag_of(select(action, "religion"))
        pflag = flag_of(sel)
        inner = (f"\t\tscope:actor.religion = {{ save_scope_as = {rflag} }}\n"
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
    return (f"# Scope: country (scope:actor); the seat is scope:bag_asp_seat.\n"
            f"bag_asp_try_{key} = {{\n\tif = {{\n\t\tlimit = {{\n{limit}\n\t\t}}\n{inner}\n\t}}\n}}\n")


def place_effect(key: str, actions: dict[str, str]) -> str:
    """Seats already on this action are kept; then free seats take it, the
    advisor best in its skill first, while it still finds a target."""
    action = actions[key]
    ability = value(action, "ability") or "adm"
    seat = ["bag_asp_free_seat = yes"]
    if value(action, "require_matching_character_religion") == "yes":
        seat.append("cabinet_member = { religion = scope:actor.religion }")
    seat = "\n".join("\t\t\t\t" + s for s in seat)
    return f"""# Scope: country (scope:actor).
bag_asp_place_{key} = {{
\tevery_cabinet = {{
\t\tlimit = {{
\t\t\tbag_asp_free_seat = yes
\t\t\thas_cabinet_action = yes
\t\t\tcabinet_action = cabinet_action:{key}
\t\t}}
\t\tcabinet_member = {{ set_variable = {{ name = bag_asp_claimed value = yes }} }}
\t}}
\tset_variable = {{ name = bag_asp_placed value = yes }}
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
\t\t\tbag_asp_try_{key} = yes
\t\t}}
\t}}
\tif = {{
\t\tlimit = {{ has_variable = bag_asp_placed }}
\t\tremove_variable = bag_asp_placed
\t}}
}}
"""


def build(game: Path) -> dict[str, str]:
    """Generated files, by path under the mod, and localization rows."""
    actions = load_actions(game)
    missing = [k for k, *_ in POOL if k not in actions]
    if missing:
        raise SystemExit(f"council: the game has no cabinet action {', '.join(missing)}")
    for k, *_ in POOL:
        if value(actions[k], "forbid_for_automation") == "yes":
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
\t\tdefault_value = 12
\t\tmin_value = 0
\t\tmax_value = 60
\t\tstep_value = 1
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
\tcmm_register_settings_list = {{
\t\tmod_id = {MOD_ID}
\t\tsetting_id = tuning
\t\ttab_id = fine
\t\titem_count = {n}
\t\tis_ordered = 0
\t}}
\tcmm_register_list_text_field = {{
\t\tmod_id = {MOD_ID}
\t\tsetting_id = tuning
\t\tfield_id = settings
\t}}
"""]
    for i, (k, *_) in enumerate(POOL, 1):
        ability = value(actions[k], "ability") or "adm"
        reg.append(f"\tcmm_set_list_item_value = {{ mod_id = {MOD_ID} setting_id = available item = {i} value = flag:bag_asp_{k} }}\n"
                   f"\tcmm_set_list_item_value = {{ mod_id = {MOD_ID} setting_id = priority item = {i} value = flag:bag_asp_{k} }}\n"
                   f"\tcmm_set_list_text_value = {{ mod_id = {MOD_ID} setting_id = priority field_id = ability item = {i} value = flag:bag_asp_ability_{ability} }}\n"
                   f"\tcmm_set_list_item_value = {{ mod_id = {MOD_ID} setting_id = tuning item = {i} value = flag:bag_asp_{k} }}\n"
                   f"\tcmm_set_list_text_value = {{ mod_id = {MOD_ID} setting_id = tuning field_id = settings item = {i} value = flag:bag_asp_tuning_none }}\n")
    reg.append(f"""
\tbag_asp_sync = yes
\tbag_asp_rebuild = yes
}}

# Scope: country. Settings into plain variables the pulse reads.
bag_asp_sync = {{
\tcmm_sync_bool_alias = {{ setting = {MOD_ID}__auto alias = bag_asp_auto_on }}
\tcmm_sync_setting_alias = {{ setting = {MOD_ID}__period alias = bag_asp_period }}
\tcmm_sync_setting_alias = {{ setting = {MOD_ID}__review alias = bag_asp_review }}
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
\t\t\tlimit = {{ cabinet_action:{k} = {{ is_visible_for = root }} }}
\t\t\tcmm_show_list_item = {{ mod_id = {MOD_ID} setting_id = available item = {i} }}
\t\t\tcmm_show_list_item = {{ mod_id = {MOD_ID} setting_id = tuning item = {i} }}
\t\t}}
\t\telse = {{
\t\t\tcmm_hide_list_item = {{ mod_id = {MOD_ID} setting_id = available item = {i} }}
\t\t\tcmm_hide_list_item = {{ mod_id = {MOD_ID} setting_id = tuning item = {i} }}
\t\t}}
\t\tif = {{
\t\t\tlimit = {{
\t\t\t\tcabinet_action:{k} = {{ is_visible_for = root }}
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
""".replace("{{", "{").replace("}}", "}"))
    reg.append("\t}\n}\n")

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
\t}}
}}
""")
    effects = "".join(reg)

    switch = "\n".join(f"\t\t\t\t\tflag:bag_asp_{k} = {{ bag_asp_place_{k} = yes }}" for k, *_ in POOL)
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
\tif = {{
\t\tlimit = {{ NOT = {{ any_in_list = {{ variable = bag_asp_used }} }} }}
\t\tdebug_log = "bag_asp: no action is ticked in use"
\t}}
\tbag_asp_mark_busy = yes
\t# A seat the emergency put on recovery keeps it until the action ends.
\tif = {{
\t\tlimit = {{ is_target_in_variable_list = {{ name = bag_asp_used target = flag:bag_asp_recovery_effort }} }}
\t\tevery_cabinet = {{
\t\t\tlimit = {{
\t\t\t\texists = cabinet_member
\t\t\t\thas_cabinet_action = yes
\t\t\t\tcabinet_action = cabinet_action:recovery_effort
\t\t\t}}
\t\t\tcabinet_member = {{ set_variable = {{ name = bag_asp_claimed value = yes }} }}
\t\t}}
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
    tries = "\n".join(try_effect(k, kind, order, gate, actions) for k, kind, order, gate in POOL)
    def pass_(effect: str) -> str:
        return "\n".join(
            f"\t\tif = {{\n\t\t\tlimit = {{ cabinet_action = cabinet_action:{k} }}\n"
            f"\t\t\tinteraction_target:{f} ?= {{ {effect.format(k=k)} }}\n\t\t}}"
            for k, f in sorted(BUSY))
    run += f"""# Scope: country. Mark every target a seat already works on, for the copied
# «already performing the same task» triggers; unmark after the pass.
bag_asp_mark_busy = {{
\tevery_cabinet = {{
\t\tlimit = {{ has_cabinet_action = yes }}
{pass_("set_variable = {{ name = bag_asp_busy_{k} value = yes }}")}
\t}}
}}

bag_asp_clear_busy = {{
\tevery_cabinet = {{
\t\tlimit = {{ has_cabinet_action = yes }}
{pass_("remove_variable = bag_asp_busy_{k}")}
\t}}
}}

"""
    run += tries
    seat_rank = "\n".join(
        f"\t\t\telse_if = {{ limit = {{ cabinet_action = cabinet_action:{k} }} add = scope:actor.var:bag_asp_rank_{k} }}"
        for k, *_ in POOL)
    run += f"""
# Scope: country. While the game's «devastated locations» alert shows, every
# couple of seconds (bag_asp_devastation_watch.gui): one province below zero
# prosperity without recovery gets it now, from the seat whose action ranks
# lowest in «Приоритет» (an empty one first, then one outside the pool).
bag_asp_emergency = {{
\tif = {{
\t\tlimit = {{ has_variable = bag_asp_auto_on }}
\t\tsave_scope_as = actor
\t\tbag_asp_rebuild = yes
\t\tif = {{
\t\t\tlimit = {{ is_target_in_variable_list = {{ name = bag_asp_used target = flag:bag_asp_recovery_effort }} }}
\t\t\tbag_asp_mark_busy = yes
\t\t\tordered_cabinet = {{
\t\t\t\tlimit = {{
\t\t\t\t\texists = cabinet_member
\t\t\t\t\tNOT = {{
\t\t\t\t\t\thas_cabinet_action = yes
\t\t\t\t\t\tcabinet_action = cabinet_action:recovery_effort
\t\t\t\t\t}}
\t\t\t\t}}
\t\t\t\torder_by = {{
\t\t\t\t\tvalue = 0
\t\t\t\t\tif = {{ limit = {{ has_cabinet_action = no }} add = 1000 }}
{seat_rank.replace(chr(9) * 3, chr(9) * 5)}
\t\t\t\t\telse = {{ add = 500 }}
\t\t\t\t\tadd = {{
\t\t\t\t\t\tvalue = cabinet_member.dip
\t\t\t\t\t\tdivide = 100
\t\t\t\t\t}}
\t\t\t\t}}
\t\t\t\tsave_scope_as = bag_asp_seat
\t\t\t\tbag_asp_try_recovery_effort = yes
\t\t\t\tif = {{
\t\t\t\t\tlimit = {{ exists = cabinet_member }}
\t\t\t\t\tcabinet_member = {{
\t\t\t\t\t\tif = {{
\t\t\t\t\t\t\tlimit = {{ has_variable = bag_asp_claimed }}
\t\t\t\t\t\t\tremove_variable = bag_asp_claimed
\t\t\t\t\t\t}}
\t\t\t\t\t}}
\t\t\t\t}}
\t\t\t}}
\t\t\tif = {{
\t\t\t\tlimit = {{ has_variable = bag_asp_placed }}
\t\t\t\tdebug_log = "bag_asp: emergency, a seat moved to recovery"
\t\t\t\tremove_variable = bag_asp_placed
\t\t\t}}
\t\t\tbag_asp_clear_busy = yes
\t\t}}
\t}}
}}
"""
    run += "\n" + "\n".join(place_effect(k, actions) for k, *_ in POOL)

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
\t}}
}}

"""
    guis = "# assimilate_primary: the lists' callbacks. Rebuilt by tools/generate.py.\n\n" + guis
    guis += f"""# Called by bag_asp_devastation_watch.gui while the game's «devastated
# locations» alert shows: once as it appears, then every two seconds.
bag_asp_devastated = {{
\tscope = country
\tis_shown = {{ always = yes }}
\teffect = {{
\t\tbag_asp_emergency = yes
\t}}
}}

# Called once as the alert appears: the probe that says the window sees it.
bag_asp_devastated_seen = {{
\tscope = country
\tis_shown = {{ always = yes }}
\teffect = {{
\t\tdebug_log = "bag_asp: the devastated locations alert is showing"
\t}}
}}
"""
    watch = """# assimilate_primary: watches the game's yellow «devastated locations» alert
# (has_devastated_locations, in_game/gui/alertmanager.gui). Nothing lives here
# but one number the engine already has; while the alert shows, the council's
# emergency runs every two seconds. Rebuilt by tools/generate.py.
widget = {
	name = "bag_asp_devastation_watch"
	size = { 0 0 }
	visible = "[And(GetPlayer.Exists, GreaterThan_uint32(GetAlertOfTypeShowingCount('has_devastated_locations'), IntToUnsigned('(int32)0')))]"

	state = {
		name = _show
		duration = 0.1
		on_finish = "[GetScriptedGui('bag_asp_devastated_seen').Execute(GuiScope.SetRoot(GetPlayer.MakeScope).End)]"
		on_finish = "[GetScriptedGui('bag_asp_devastated').Execute(GuiScope.SetRoot(GetPlayer.MakeScope).End)]"
		next = bag_asp_devastation_again
	}

	state = {
		name = bag_asp_devastation_again
		duration = 2
		on_finish = "[GetScriptedGui('bag_asp_devastated').Execute(GuiScope.SetRoot(GetPlayer.MakeScope).End)]"
		next = bag_asp_devastation_again
	}
}
"""

    triggers = """# assimilate_primary: triggers of the council pass. Rebuilt by tools/generate.py.

# Scope: cabinet (a seat). It has an advisor whom this pass has not chosen yet.
bag_asp_free_seat = {
\texists = cabinet_member
\tcabinet_member = { NOT = { has_variable = bag_asp_claimed } }
}
"""

    return {
        "in_game/common/scripted_triggers/bag_asp_council_triggers.txt": triggers,
        "in_game/common/scripted_effects/bag_asp_cmm_effects.txt": effects,
        "in_game/common/scripted_effects/bag_asp_council_effects.txt": run,
        "in_game/common/on_action/bag_asp_cmf_on_actions.txt": on_actions,
        "in_game/common/scripted_guis/bag_asp_scripted_gui.txt": guis,
        "in_game/gui/bag_asp_devastation_watch.gui": watch,
        "in_game/gui/scripted_widgets/bag_asp_widgets.txt":
            "gui/bag_asp_devastation_watch.gui = bag_asp_devastation_watch\n",
    }


def loc_rows(game: Path, language: str) -> dict[str, str]:
    """List row labels: the game's own linked action names."""
    src = (game / f"main_menu/localization/{language}/government_l_{language}.yml").read_text(encoding="utf-8-sig")
    names = dict(re.findall(r'^ (\w+):\d* "(.*)"\s*$', src, re.M))
    rows = {}
    for i, (k, *_) in enumerate(POOL, 1):
        if k not in names:
            raise SystemExit(f"council: the game has no {language} name for {k}")
        # The game's own linked name, as CM writes its building rows
        # ([ShowBuildingTypeName]): it hovers the game's tooltip of the action.
        name = f"[ShowCabinetActionName('{k}')]"
        for s in LISTS:
            rows[f"{MOD_ID}__{s}_i{i}_name"] = name
    for ab, text in ABILITY[language].items():
        rows[f"bag_asp_ability_{ab}"] = text
    rows["bag_asp_tuning_none"] = TUNING_NONE[language]
    return rows
