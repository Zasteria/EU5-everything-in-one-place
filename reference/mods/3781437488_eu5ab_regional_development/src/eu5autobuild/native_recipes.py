"""Synchronous script production-method identities for a candidate location.

Read the engine's production_method_of_building iterator and associate its
identities with the static recipe slots. Ambiguous identities are unknown.
Identity needs no GUI reader, method change or country scan.
"""

def render_active_filter_trigger(models, upgrades=None) -> str:
    """Limit a scan-time capture to active types and their predecessors."""
    relevant: dict[str, set[str]] = {
        building: {building} for building in models
    }
    if upgrades is not None:
        for destination in models:
            for predecessor in upgrades.predecessors.get(destination, ()):
                relevant.setdefault(predecessor, set()).add(destination)

    lines = [
        "# Building-type scope. The location view contains the current country's",
        "# active normal/input destinations; existing upgrade sources map back to it.",
        "eu5ab_native_recipe_relevant_to_active_catalog = {",
        "\tswitch = {",
        "\t\ttrigger = this",
    ]
    for building, destinations in sorted(relevant.items()):
        lines += [
            f"\t\tbuilding_type:{building} = {{",
            f"\t\t\tscope:eu5ab_native_recipe_location = {{",
            "\t\t\t\tOR = {",
            *(
                "\t\t\t\t\tis_target_in_variable_list = { "
                f"name = eu5ab_active_recipe_catalog_view target = building_type:{destination} }}"
                for destination in sorted(destinations)
            ),
            "\t\t\t\t}",
            "\t\t\t}",
            "\t\t}",
        ]
    lines += ["\t\tfallback = { always = no }", "\t}", "}", ""]
    return "\n".join(lines)


def render(models, upgrades=None) -> tuple[str, str, str]:
    count = max((len(m.slots) for m in models.values()), default=0)
    clear = "\n".join(f"    clear_variable_map = eu5ab_native_recipe_slot_{i}" for i in range(count))
    from .production_reference import render as render_reference
    recipe_known, _ = render_reference(models, ())
    effects = ['''eu5ab_clear_native_recipes = {
    remove_variable = eu5ab_native_recipe_owner
    remove_variable = eu5ab_native_recipe_capturing
    clear_variable_list = eu5ab_native_recipe_types
    clear_variable_list = eu5ab_native_recipe_conflicts
''' + clear + '''
}
eu5ab_begin_native_recipe_capture = {
    eu5ab_clear_native_recipes = yes
    eu5ab_clear_recipe_score_snapshot = yes
    set_variable = eu5ab_native_recipe_capturing
    save_scope_as = eu5ab_native_recipe_location
    every_buildings_in_location = {
        limit = {
            owner = scope:eu5ab_native_recipe_location.owner
            NOT = { exists = estate_type }
            OR = {
                scope:eu5ab_native_recipe_location = { NOT = { eu5ab_active_recipe_catalog_current = yes } }
                building_type = { eu5ab_native_recipe_relevant_to_active_catalog = yes }
            }
        }
        save_scope_as = eu5ab_native_recipe_building
        if = { limit = { eu5ab_pr_recipe_known = yes }
            every_production_method_of_building = {
                save_scope_as = eu5ab_native_recipe_method
                scope:eu5ab_native_recipe_location = { eu5ab_capture_native_recipe_method = yes }
            }
        }
        else = {
            building_type = { save_scope_as = eu5ab_native_recipe_unknown_type }
            scope:eu5ab_native_recipe_location = {
                add_to_variable_list = { name = eu5ab_native_recipe_conflicts target = scope:eu5ab_native_recipe_unknown_type }
            }
        }
    }
}
eu5ab_capture_native_recipe_method = {
    switch = {
        trigger = scope:eu5ab_native_recipe_building.building_type
''']
    for building, model in sorted(models.items()):
        effects += [f"        building_type:{building} = {{"]
        for slot_index, slot in enumerate(model.slots):
            name = f"eu5ab_native_recipe_slot_{slot_index}"
            for index, method in enumerate(slot, 1):
                effects += [f'''            if = {{
                limit = {{ scope:eu5ab_native_recipe_method = production_method:{method.production_method_id} }}
                if = {{
                    limit = {{ has_variable_map = {name} is_key_in_variable_map = {{ name = {name} target = building_type:{building} }}
                        NOT = {{ "variable_map({name}|building_type:{building})" = {index} }} }}
                    add_to_variable_list = {{ name = eu5ab_native_recipe_conflicts target = building_type:{building} }}
                }}
                add_to_variable_map = {{ name = {name} key = building_type:{building} value = {index} }}
            }}''']
        checks = " ".join(f"has_variable_map = eu5ab_native_recipe_slot_{i} is_key_in_variable_map = {{ name = eu5ab_native_recipe_slot_{i} target = building_type:{building} }}"
                          for i in range(len(model.slots)))
        effects += [f'''            if = {{
                limit = {{ {checks}
                    NOT = {{ is_target_in_variable_list = {{ name = eu5ab_native_recipe_types target = building_type:{building} }} }} }}
                add_to_variable_list = {{ name = eu5ab_native_recipe_types target = building_type:{building} }}
            }}
        }}''']
    effects += ['''    }
}
eu5ab_finish_native_recipe_capture = {
    if = {
        limit = { has_variable = eu5ab_native_recipe_capturing }
        every_in_list = {
            variable = eu5ab_native_recipe_conflicts
            save_scope_as = eu5ab_conflicted_recipe_type
            prev = { remove_list_variable = { name = eu5ab_native_recipe_types target = scope:eu5ab_conflicted_recipe_type } }
        }
        set_variable = { name = eu5ab_native_recipe_owner value = owner }
        remove_variable = eu5ab_native_recipe_capturing
    }
}
eu5ab_refresh_native_recipes = {
    eu5ab_begin_native_recipe_capture = yes
    eu5ab_finish_native_recipe_capture = yes
}
''']
    triggers = '''eu5ab_native_recipes_current = {
    exists = var:eu5ab_native_recipe_owner
    owner = var:eu5ab_native_recipe_owner
    NOT = { has_variable = eu5ab_native_recipe_capturing }
}
'''
    return "\n".join(effects), triggers + render_active_filter_trigger(models, upgrades) + recipe_known, ""
