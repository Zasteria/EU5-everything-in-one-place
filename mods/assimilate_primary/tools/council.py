"""The mod's own council automation: CMF page, lists and the monthly pass.

His ask 12.10: a checkbox turns on our automation; every so often idle seats get
an action, picked down a priority list he orders in CMF. Common actions only,
nothing country-specific and nothing as pointed as settling the frontier. Two
lists: «Доступные» (every pool action this country can see, a checkbox puts it
in use) and «Приоритет» (the actions in use, in the order they are tried).

What is copied from the game rather than written here: each target's validity
is the action's own `visible` and `enabled` from its `select_trigger`, pasted
into the search, so a target the game would grey out is never picked. The order
in which targets are tried, and the gates of standing actions, are this file's
guesses at vanilla (the game scores 62 of 74 actions inside the engine).

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
    ("integrate_province", "province", "population", ""),
    ("integrate_area", "area", "population", ""),
    ("reduce_war_exhaustion", "country", None, ""),
    ("stabilize_country", "country", None, "stability < 50"),
    ("increase_control_province", "province", "province_tax_base", ""),
    ("increase_control_area", "area", "province_tax_base", ""),
    ("send_secret_royal_inspectors", "province", "province_tax_base", ""),
    ("promote_culture", "culture", "population", ""),
    ("promote_religion", "religion", "population", ""),
    ("pacify_population", "province", "population", ""),
    ("recovery_effort", "province", "population", ""),
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
    # Unset in the file counts as one seat at a time: otherwise an action with no
    # condition on its target (pop_promote_action) takes every seat left.
    multiple = value(action, "allow_multiple") == "yes"
    religion = value(action, "require_matching_character_religion") == "yes"
    cond = [
        "scope:actor = { NOT = { has_variable = bag_asp_filled } }",
        f"cabinet_action:{key} = {{ is_available_for = scope:actor }}",
    ]
    if gate:
        cond.append(f"scope:actor = {{ {gate} }}")
    if not multiple:
        cond.append(f"scope:actor = {{ NOT = {{ any_cabinet = {{ has_cabinet_action = yes cabinet_action = cabinet_action:{key} }} }} }}")
    if religion:
        cond.append("cabinet_member = { religion = scope:actor.religion }")
    limit = "\n".join("\t\t\t" + c for c in cond)
    done = (f"\t\t\t\tscope:actor = {{ set_variable = {{ name = bag_asp_filled value = yes }} }}\n"
            f"\t\t\t\tdebug_log = \"bag_asp: seat set to {key}\"")

    def assign(params: str, flag: str = "") -> str:
        mark = ""
        if flag:
            BUSY.add((key, flag))
            mark = f"\t\t\t\tscope:bag_asp_pick = {{ set_variable = {{ name = bag_asp_busy_{key} value = yes }} }}\n"
        return (f"\t\t\t\tscope:bag_asp_seat = {{ set_cabinet_action = {{ type = cabinet_action:{key}{params} }} }}\n"
                + mark + done)

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
    return (f"# Scope: cabinet (a seat), saved as scope:bag_asp_seat; scope:actor = country.\n"
            f"bag_asp_try_{key} = {{\n\tif = {{\n\t\tlimit = {{\n{limit}\n\t\t}}\n{inner}\n\t}}\n}}\n")


def standing(action: str) -> bool:
    """An action with no is_finished holds its seat until something stops it."""
    return child(action, "is_finished") is None


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
"""]
    for i, (k, *_) in enumerate(POOL, 1):
        ability = value(actions[k], "ability") or "adm"
        reg.append(f"\tcmm_set_list_item_value = {{ mod_id = {MOD_ID} setting_id = available item = {i} value = flag:bag_asp_{k} }}\n"
                   f"\tcmm_set_list_item_value = {{ mod_id = {MOD_ID} setting_id = priority item = {i} value = flag:bag_asp_{k} }}\n"
                   f"\tcmm_set_list_text_value = {{ mod_id = {MOD_ID} setting_id = priority field_id = ability item = {i} value = flag:bag_asp_ability_{ability} }}\n")
    reg.append(f"""
\tcmm_register_bool_setting = {{
\t\tmod_id = {MOD_ID}
\t\tsetting_id = cabinetactions
\t\ttab_id = main
\t\tgroup_id = debug
\t\tdefault_value = 0
\t}}

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
\t\t}}
\t\telse = {{
\t\t\tcmm_hide_list_item = {{ mod_id = {MOD_ID} setting_id = available item = {i} }}
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
\t\t\t\tbag_asp_run = yes
\t\t\t}}
\t\t\telse = {{
\t\t\t\tdebug_log = "bag_asp: own council automation off"
\t\t\t}}
\t\t}}
\t\tflag:{MOD_ID}__period = {{ bag_asp_sync = yes }}
\t\tflag:{MOD_ID}__review = {{ bag_asp_sync = yes }}
\t\tflag:{MOD_ID}__cabinetactions = {{
\t\t\tif = {{
\t\t\t\tlimit = {{ is_system_automated = cabinetactions }}
\t\t\t\tdebug_log = "bag_asp: cabinetactions was on before the click"
\t\t\t}}
\t\t\telse = {{
\t\t\t\tdebug_log = "bag_asp: cabinetactions was off before the click"
\t\t\t}}
\t\t\tcmm_sync_bool_alias = {{
\t\t\t\tsetting = {MOD_ID}__cabinetactions
\t\t\t\talias = bag_asp_cabinetactions_on
\t\t\t}}
\t\t\tif = {{
\t\t\t\tlimit = {{ has_variable = bag_asp_cabinetactions_on }}
\t\t\t\tset_automated_system = {{ system = cabinetactions activate = yes }}
\t\t\t}}
\t\t\telse = {{
\t\t\t\tset_automated_system = {{ system = cabinetactions activate = no }}
\t\t\t}}
\t\t\tif = {{
\t\t\t\tlimit = {{ is_system_automated = cabinetactions }}
\t\t\t\tdebug_log = "bag_asp: cabinetactions is on after the click"
\t\t\t}}
\t\t\telse = {{
\t\t\t\tdebug_log = "bag_asp: cabinetactions is off after the click"
\t\t\t}}
\t\t}}
\t}}
}}
""")
    effects = "".join(reg)

    stand = [k for k, *_ in POOL if standing(actions[k])]
    stand_or = "\n".join(f"\t\t\t\tcabinet_action = cabinet_action:{k}" for k in stand)
    switch = "\n".join(f"\t\t\t\t\t\t\tflag:bag_asp_{k} = {{ bag_asp_try_{k} = yes }}" for k, *_ in POOL)
    run = f"""# assimilate_primary: the mod's own council automation, the monthly pass.
# Rebuilt by tools/generate.py (tools/council.py).

# Scope: country. Every month for a player with the checkbox on; the work runs
# every `period` months, and every `review` months (0 = never) the standing
# actions, which never finish on their own, are stopped and re-chosen.
bag_asp_tick = {{
\tif = {{
\t\tlimit = {{ NOT = {{ has_variable = bag_asp_period }} }}
\t\tbag_asp_sync = yes
\t}}
\tchange_variable = {{ name = bag_asp_months add = 1 }}
\tchange_variable = {{ name = bag_asp_review_months add = 1 }}
\tif = {{
\t\tlimit = {{
\t\t\tvar:bag_asp_review > 0
\t\t\tvar:bag_asp_review_months >= var:bag_asp_review
\t\t}}
\t\tset_variable = {{ name = bag_asp_review_months value = 0 }}
\t\tbag_asp_review_seats = yes
\t\tset_variable = {{ name = bag_asp_months value = var:bag_asp_period }}
\t}}
\tif = {{
\t\tlimit = {{ var:bag_asp_months >= var:bag_asp_period }}
\t\tset_variable = {{ name = bag_asp_months value = 0 }}
\t\tbag_asp_run = yes
\t}}
}}

# Scope: country. Stop the standing actions of the pool so the next pass
# re-chooses those seats down the priority list.
bag_asp_review_seats = {{
\tevery_cabinet = {{
\t\tlimit = {{
\t\t\thas_cabinet_action = yes
\t\t\tOR = {{
{stand_or}
\t\t\t}}
\t\t}}
\t\tstop_cabinet_action = {{}}
\t\tdebug_log = "bag_asp: review, a standing action stopped to be re-chosen"
\t}}
}}

# Scope: country. Every seat with a member and no action gets the first action
# down «Приоритет» that is in use, allowed now and has a target.
bag_asp_run = {{
\tsave_scope_as = actor
\tif = {{
\t\tlimit = {{ NOT = {{ has_variable_list = bag_asp_order }} }}
\t\tbag_asp_rebuild = yes
\t}}
\tbag_asp_mark_busy = yes
\tevery_cabinet = {{
\t\tlimit = {{
\t\t\thas_cabinet_action = no
\t\t\texists = cabinet_member
\t\t}}
\t\tsave_scope_as = bag_asp_seat
\t\tscope:actor = {{
\t\t\tevery_in_list = {{
\t\t\t\tvariable = bag_asp_order
\t\t\t\tsave_temporary_scope_as = bag_asp_item
\t\t\t\tif = {{
\t\t\t\t\tlimit = {{
\t\t\t\t\t\tscope:actor = {{
\t\t\t\t\t\t\tNOT = {{ has_variable = bag_asp_filled }}
\t\t\t\t\t\t\tis_target_in_variable_list = {{ name = bag_asp_used target = scope:bag_asp_item }}
\t\t\t\t\t\t}}
\t\t\t\t\t}}
\t\t\t\t\tscope:bag_asp_seat = {{
\t\t\t\t\t\tswitch = {{
\t\t\t\t\t\t\ttrigger = scope:bag_asp_item
{switch}
\t\t\t\t\t\t}}
\t\t\t\t\t}}
\t\t\t\t}}
\t\t\t}}
\t\t\tif = {{
\t\t\t\tlimit = {{ has_variable = bag_asp_filled }}
\t\t\t\tremove_variable = bag_asp_filled
\t\t\t}}
\t\t\telse = {{
\t\t\t\tdebug_log = "bag_asp: a seat stays empty, nothing in use fits"
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

    on_actions = f"""# assimilate_primary: the CMF page and the monthly pass. The engine merges
# on_actions lists, so these add to CMF's own and the game's.
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

monthly_country_pulse = {{
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
\t\tis_ai = no
\t\thas_variable = bag_asp_auto_on
\t}}
\teffect = {{
\t\tbag_asp_tick = yes
\t}}
}}
"""

    guis = ""
    for s in ("available", "priority"):
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
    guis = "# assimilate_primary: the two lists' callbacks. Rebuilt by tools/generate.py.\n\n" + guis

    return {
        "in_game/common/scripted_effects/bag_asp_cmm_effects.txt": effects,
        "in_game/common/scripted_effects/bag_asp_council_effects.txt": run,
        "in_game/common/on_action/bag_asp_cmf_on_actions.txt": on_actions,
        "in_game/common/scripted_guis/bag_asp_scripted_gui.txt": guis,
    }


# Names the game builds from references, written out (a label that is only a
# reference can render blank, docs/pitfalls/localization.md).
NAMES = {
    "english": {"reduce_war_exhaustion": "Reduce War Exhaustion"},
    "russian": {},
}


def loc_rows(game: Path, language: str) -> dict[str, str]:
    """List row labels copied from the game's own action names."""
    src = (game / f"main_menu/localization/{language}/government_l_{language}.yml").read_text(encoding="utf-8-sig")
    names = dict(re.findall(r'^ (\w+):\d* "(.*)"\s*$', src, re.M))
    rows = {}
    for i, (k, *_) in enumerate(POOL, 1):
        name = NAMES[language].get(k) or names.get(k)
        if not name or "$" in name or "[" in name:
            raise SystemExit(f"council: no plain {language} name for {k}; write one by hand")
        rows[f"{MOD_ID}__available_i{i}_name"] = name
        rows[f"{MOD_ID}__priority_i{i}_name"] = name
    for ab, text in ABILITY[language].items():
        rows[f"bag_asp_ability_{ab}"] = text
    return rows
