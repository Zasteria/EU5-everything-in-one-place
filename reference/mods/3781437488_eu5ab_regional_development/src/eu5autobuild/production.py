"""Read-only recipes: script method identities first, economic estimates otherwise.

Fallbacks compare complete feasible recipes per slot, with declaration order
breaking ties. A hypothetical choice never proves an upstream output: each
target good must also be guaranteed across available alternatives or confirmed
by the native method iterator. The Mod never switches production methods.
"""

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re

from .game_data import ProductionRecipe, _recipe_from_method, parse_paradox_script
from .policy import BuildingCatalog
from . import recipe_snapshot
from .rgo_automation import raw_goods


@dataclass(frozen=True)
class ProductionMethod(ProductionRecipe):
    potential: str = ""
    allow: str = ""
    unlock_advances: tuple[str, ...] = ()


@dataclass(frozen=True)
class BuildingProduction:
    building_id: str
    slots: tuple[tuple[ProductionMethod, ...], ...]


# Keep condition bodies verbatim: the small numeric-data parser intentionally
# does not represent comparison operators or quoted trigger expressions.
_TOKENS = re.compile(r'#[^\n]*|"(?:\\.|[^"\\])*"|>=|<=|!=|\?=|[{}=<>]|[^\s{}=<>!?#]+')


def script_blocks(text: str):
    """Yield top-level named block bodies, preserving repeats and source syntax."""
    tokens = [m for m in _TOKENS.finditer(text) if not m[0].startswith("#")]
    i = 0
    while i < len(tokens):
        if i + 2 < len(tokens) and tokens[i + 1][0] == "=" and tokens[i + 2][0] == "{":
            key, start = tokens[i][0], tokens[i + 2].end()
            i += 3
            depth = 1
            while i < len(tokens) and depth:
                depth += (tokens[i][0] == "{") - (tokens[i][0] == "}")
                i += 1
            if depth:
                raise ValueError(f"Unclosed source block: {key}")
            yield key, text[start:tokens[i - 1].start()].strip()
        else:
            i += 1


def _definitions(directory: Path):
    return {key: body for path in sorted(directory.glob("*.txt"))
            for key, body in script_blocks(path.read_text(encoding="utf-8-sig"))}


def extract_production_models(game_root: Path, catalog: BuildingCatalog) -> dict[str, BuildingProduction]:
    common = game_root / "game" / "in_game" / "common"
    buildings = _definitions(common / "building_types")
    methods = _definitions(common / "production_methods")
    # Inline methods are global database objects too; another building may
    # reference one through possible_production_methods (e.g. grain_house).
    for source in buildings.values():
        for key, body in script_blocks(source):
            if key == "unique_production_methods":
                methods.update(script_blocks(body))
    goods = _definitions(common / "goods")
    raw = {good for good, body in goods.items()
           if not any(k == "category" and str(v).removeprefix("goods_category:") == "produced"
                      for k, v in parse_paradox_script(body))}
    unlocks: dict[str, list[str]] = {}
    for advance, body in _definitions(common / "advances").items():
        for key, value in parse_paradox_script(body):
            if key == "unlock_production_method" and isinstance(value, str):
                unlocks.setdefault(value.removeprefix("production_method:"), []).append(advance)
    result = {}
    for building_id in sorted(catalog.buildings):
        if building_id not in buildings:
            raise ValueError(f"Missing production definition: {building_id}")
        slots = []
        for key, body in script_blocks(buildings[building_id]):
            if key == "unique_production_methods":
                candidates = list(script_blocks(body))
            elif key == "possible_production_methods":
                candidates = []
                for _, method_id in parse_paradox_script(body):
                    method_id = str(method_id).removeprefix("production_method:")
                    if method_id not in methods:
                        raise ValueError(f"Unresolved production method: {building_id}/{method_id}")
                    candidates.append((method_id, methods[method_id]))
            else:
                continue
            slot = []
            for method_id, source in candidates:
                recipe = _recipe_from_method(building_id, method_id, parse_paradox_script(source), set(goods), raw)
                conditions = dict(script_blocks(source))
                slot.append(ProductionMethod(
                    **asdict(recipe), potential=conditions.get("potential", ""),
                    allow=conditions.get("allow", ""),
                    unlock_advances=tuple(sorted(unlocks.get(method_id, ()))),
                ))
            if slot:
                slots.append(tuple(slot))
        result[building_id] = BuildingProduction(building_id, tuple(slots))
    return result


def production_models_as_json(models: dict[str, BuildingProduction]) -> str:
    return json.dumps({
        "schema_version": 2,
        "selection_mode": "native_active_else_best_feasible_margin_estimate",
        "active_method_readable": True,
        "new_build_method_readable": False,
        "buildings": [asdict(models[key]) for key in sorted(models)],
    }, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def production_models_from_json(payload: dict) -> dict[str, BuildingProduction]:
    if payload["schema_version"] != 2:
        raise ValueError("Regenerate production metadata: slot-aware schema 2 required")
    return {row["building_id"]: BuildingProduction(row["building_id"], tuple(
        tuple(ProductionMethod(**{**method, "unlock_advances": tuple(method["unlock_advances"])})
              for method in slot) for slot in row["slots"])) for row in payload["buildings"]}


LOCATION = "scope:eu5ab_candidate_location"


def _name(building, slot, method=None):
    return f"eu5ab_recipe_{building}_{slot}" + (f"_{method}" if method is not None else "")


def _shortage(good, ratio):
    return (f'{LOCATION}.market ?= {{ "goods_supply_in_market(goods:{good})" < '
            f'{{ value = "goods_demand_in_market(goods:{good})" multiply = {ratio} }} }}')


def _branch(condition, body, keyword="if"):
    return [f"\t{keyword} = {{", f"\t\tlimit = {{ {condition} }}", *[f"\t\t{line}" for line in body], "\t}"]


def _value(name, body):
    return [f"{name} = {{", "\tvalue = 0", *body, "}", ""]


def selected_method_branches(building, slot_index, slot, body):
    """All consumers dispatch through the same selection value, never a union."""
    lines = []
    for method_index, method in enumerate(slot, 1):
        lines += _branch(f"{_name(building, slot_index)}_selected = {method_index}",
                         body(method), "if" if method_index == 1 else "else_if")
    return lines


def native_slot_condition(building, slot_index):
    return (f'{LOCATION} = {{ eu5ab_native_recipes_current = yes '
            f'is_target_in_variable_list = {{ name = eu5ab_native_recipe_types target = building_type:{building} }} '
            f'has_variable_map = eu5ab_native_recipe_slot_{slot_index} '
            f'is_key_in_variable_map = {{ name = eu5ab_native_recipe_slot_{slot_index} target = building_type:{building} }} }}')


def guaranteed_output_condition(building, model, good):
    """Building identity is already established by the caller's dispatch."""
    cases = []
    for slot_index, slot in enumerate(model.slots):
        producers = [i for i, method in enumerate(slot, 1) if good in method.outputs]
        if not producers:
            continue
        other_outputs = ' '.join(f'{_name(building, slot_index, i)}_available = yes'
                                 for i, method in enumerate(slot, 1) if good not in method.outputs)
        selected = ' '.join(f'{_name(building, slot_index)}_selected = {i}' for i in producers)
        cases.append(f'AND = {{ OR = {{ {selected} }} OR = {{ '
                     f'AND = {{ {native_slot_condition(building, slot_index)} }} '
                     f'NOT = {{ OR = {{ {other_outputs or "always = no"} }} }} }} }}')
    return f'OR = {{ {" ".join(cases) or "always = no"} }}'


def _output_dispatch(name, cases):
    lines = [f'{name} = {{', '\tswitch = {', '\t\ttrigger = this', '\t\tfallback = { always = no }']
    for building, conditions in sorted(cases.items()):
        lines.append(f'\t\tbuilding_type:{building} = {{ OR = {{ {" ".join(conditions)} }} }}')
    return [*lines, '\t}', '}', '']


def render_production(models, rules, *, score_buildings=()):
    """Return shared recipe triggers, values and score snapshot effects."""
    triggers = ["eu5ab_native_recipes_current = { exists = var:eu5ab_native_recipe_owner owner = var:eu5ab_native_recipe_owner NOT = { has_variable = eu5ab_native_recipe_capturing } }"]
    from .production_reference import render as render_reference
    triggers.append(render_reference(models, ())[0])
    values, effects = [], []
    ratio = rules.thresholds.input_shortage_supply_ratio
    for good in sorted(rules.input_goods):
        triggers += [f"eu5ab_recipe_short_{good} = {{ {_shortage(good, ratio)} }}", ""]
    shortage_cases, available_cases, input_cases = [], [], []
    output_cases = {good: {} for good in set(raw_goods()) | rules.input_goods | rules.essential_goods}
    guaranteed_cases = {good: {} for good in set(rules.input_goods) | {g for m in models.values() for s in m.slots for p in s for g in p.outputs}}
    property_cases = {key: [] for key in ("output_value", "input_cost", "raw_total", "raw_matched")}
    for building, model in sorted(models.items()):
        slot_failures, slot_unavailable = [], []
        properties = {key: [] for key in property_cases}
        for slot_index, slot in enumerate(model.slots):
            stem = _name(building, slot_index)
            selection = []
            native = native_slot_condition(building, slot_index)
            for index, method in enumerate(slot, 1):
                name = _name(building, slot_index, index)
                for good in method.outputs:
                    output_cases.setdefault(good, {}).setdefault(building, []).append(
                        f"{stem}_selected = {index}")
                # Vanilla method conditions use country scope; scope:target is
                # the proposed location. Do not let an absent optional scope
                # silently bypass a granary's local-market restriction.
                conditions = [re.sub(r"scope:target\b", LOCATION, body)
                              for body in (method.potential, method.allow)]
                conditions = [body for body in conditions if body]
                if method.unlock_advances:
                    conditions.append("OR = { " + " ".join(f"has_advance = {advance}" for advance in method.unlock_advances) + " }")
                triggers += [f"{name}_available = {{",
                             f"\t{LOCATION}.owner = {{", *[f"\t\t{body}" for body in conditions], "\t}", "}", ""] if conditions else [f"{name}_available = {{ always = yes }}", ""]
                shortages = [f"eu5ab_recipe_short_{good} = yes" for good, amount in method.inputs.items() if amount > 0 and good in rules.input_goods]
                triggers += [f"{name}_inputs = {{", "\tNOT = { OR = {", *[f"\t\t{line}" for line in shortages], "\t} }", "}", ""] if shortages else [f"{name}_inputs = {{ always = yes }}", ""]
                margin = [f'{operation} = {{ value = "{LOCATION}.market.market_price(goods:{g})" multiply = {q:g} }}'
                          for operation, quantities in (("add", method.outputs), ("subtract", method.inputs))
                          for g, q in quantities.items()]
                if len(slot) > 1:
                    values += _value(name + "_margin", margin)
            for feasible in ((True, False) if len(slot) > 1 else (False,)):
                for index, _ in enumerate(slot, 1):
                    name = _name(building, slot_index, index)
                    condition = f"{name}_available = yes" + (f" {name}_inputs = yes" if feasible else "")
                    better = []
                    for other in range(1, len(slot) + 1):
                        if other == index:
                            continue
                        rival = _name(building, slot_index, other)
                        better.append(f"AND = {{ {rival}_available = yes " +
                                      (f"{rival}_inputs = yes " if feasible else "") +
                                      f"{rival}_margin {'>=' if other < index else '>'} {{ value = {name}_margin }} }}")
                    if better:
                        condition += " NOT = { OR = { " + " ".join(better) + " } }"
                    selection += _branch(condition, [f"value = {index}"], "if" if not selection else "else_if")
            # A native read is authoritative, including a locked but input-starved
            # method. Replacing it with a more profitable estimate would lie.
            live = _branch(native, [f'value = "{LOCATION}.variable_map(eu5ab_native_recipe_slot_{slot_index}|building_type:{building})"'])
            live += ["\telse = {", *["\t" + line for line in selection], "\t}"]
            values += _value(stem + "_live_selected", live)
            cached = f"{LOCATION} = {{ has_variable = {recipe_snapshot.BUILDING} var:{recipe_snapshot.BUILDING} = building_type:{building} }}"
            values += _value(stem + "_selected", _branch(cached, [f"if = {{ limit = {{ {LOCATION} = {{ has_variable = eu5ab_recipe_snapshot_slot_{slot_index} }} }} value = {LOCATION}.var:eu5ab_recipe_snapshot_slot_{slot_index} }}"]) +
                             [f"\telse = {{ value = {stem}_live_selected }}"])
            slot_unavailable.append(f"{stem}_selected = 0")
            slot_failures.extend(f"AND = {{ {stem}_selected = {i} NOT = {{ {_name(building, slot_index, i)}_inputs = yes }} }}"
                                 for i in range(1, len(slot) + 1))
            for prop, field in (("output_value", "outputs"), ("input_cost", "inputs")):
                properties[prop] += selected_method_branches(building, slot_index, slot, lambda method, field=field: [
                    f'add = {{ value = "{LOCATION}.market.market_price(goods:{good})" multiply = {quantity:g} }}'
                    for good, quantity in getattr(method, field).items()])
            properties["raw_total"] += selected_method_branches(building, slot_index, slot, lambda method: [f"add = {sum(method.raw_inputs.values()):g}"])
            properties["raw_matched"] += selected_method_branches(building, slot_index, slot, lambda method: [
                f"if = {{ limit = {{ {LOCATION}.province = {{ any_location_in_province = {{ raw_material = goods:{good} }} }} }} add = {quantity:g} }}"
                for good, quantity in method.raw_inputs.items()])
        shortage_cases += [f"\t\tbuilding_type:{building} = {{ OR = {{ {' '.join(slot_failures) or 'always = no'} }} }}"]
        available_cases += [f"\t\tbuilding_type:{building} = {{ NOT = {{ OR = {{ {' '.join(slot_unavailable) or 'always = no'} }} }} }}"]
        # Both gates know the same building identity. Preserve availability
        # first and the optional shortage check, but dispatch only once.
        input_cases.append(f'''\t\tbuilding_type:{building} = {{
            NOT = {{ OR = {{ {' '.join(slot_unavailable) or 'always = no'} }} }}
            OR = {{ {LOCATION}.owner.var:eu5ab_global_stop_input_shortage <= 0
                NOT = {{ OR = {{ {' '.join(slot_failures) or 'always = no'} }} }} }}
        }}''')
        for prop in properties:
            property_cases[prop] += _branch(f"this = building_type:{building}", properties[prop], "if" if not property_cases[prop] else "else_if")
        for good in {g for slot in model.slots for method in slot for g in method.outputs}:
            guaranteed_cases[good][building] = [guaranteed_output_condition(building, model, good)]
    for name, cases, fallback in (("eu5ab_candidate_scoring_input_shortage", shortage_cases, "no"), ("eu5ab_recipe_available", available_cases, "no")):
        triggers += [f"{name} = {{", "\tswitch = {", "\t\ttrigger = this", f"\t\tfallback = {{ always = {fallback} }}", *cases, "\t}", "}", ""]
    triggers += ["eu5ab_inputs_available = {", "\tswitch = {", "\t\ttrigger = this",
                 "\t\tfallback = { always = no }", *input_cases, "\t}", "}", ""]
    for prop, body in property_cases.items():
        values += recipe_snapshot.cached_value("eu5ab_recipe_expected_" + prop, prop, body)
    for good, cases in sorted(output_cases.items()):
        triggers += _output_dispatch(f"eu5ab_recipe_produces_{good}", cases)
    for good, cases in sorted(guaranteed_cases.items()):
        triggers += _output_dispatch(f"eu5ab_recipe_guarantees_{good}", cases)
    # Delayed import avoids the module-level production/town-rights cycle.
    from .town_rights import render_town_rights_effects
    return ("\n".join(triggers), "\n".join(values),
            "\n".join(effects) + recipe_snapshot.render_effects(
                models, score_buildings=score_buildings
            ) + render_town_rights_effects(models, rules))
