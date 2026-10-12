"""Scan-time native predecessor reservations; never a construction-time wait."""


def job_credit_cases(workforce, upgrades, pop):
    """Credit only compatible queued successors, including unsupported tiers.

    The native source reservation does not identify its target. If multiple
    targets are queued, use the smallest possible transfer; an incompatible
    or unmodeled queued successor prevents any transfer from that source.
    """
    cases = []
    for source, targets in sorted(upgrades.native_successors.items()):
        old = workforce.all_buildings.get(source)
        if not old or pop not in old.pop_types:
            continue
        compatible, incompatible = [], []
        for target in targets:
            row = workforce.all_buildings.get(target)
            if row and row.pop_types == old.pop_types:
                compatible.append((min(old.jobs_per_level, row.jobs_per_level) / 1000, target))
            else:
                incompatible.append(target)
        if not compatible:
            continue
        guard = ''
        if incompatible:
            guard = 'NOT = { location = { any_buildings_in_location = { building_levels_under_construction > 0 OR = { ' + ' '.join('building_type = building_type:' + target for target in incompatible) + ' } } } }'
        amount = ['value = 0']
        for index, (jobs, target) in enumerate(sorted(compatible)):
            amount.append(f'''{'if' if index == 0 else 'else_if'} = {{ limit = {{
                location = {{ any_buildings_in_location = {{ building_type = building_type:{target}
                    building_levels_under_construction > 0 }} }} }} value = {jobs:g} }}''')
        cases.append(f'''if = {{ limit = {{ building_type = building_type:{source} {guard} }}
            subtract = {{ {' '.join(amount)} multiply = eu5ab_upgrade_reserved_count }} }}''')
    return cases


def render(upgrades):
    source_types = {source for sources in upgrades.predecessors.values() for source in sources}
    source_types.update(source for source, targets in upgrades.native_successors.items() if targets)
    sources = ' '.join('building_type = building_type:' + source for source in sorted(source_types))
    effects = '''eu5ab_request_upgrade_snapshot = {
    clear_variable_list = eu5ab_upgrade_sources
    clear_variable_list = eu5ab_upgrade_sampled_sources
    clear_variable_map = eu5ab_upgrade_reserved_levels
    clear_variable_map = eu5ab_upgrade_source_levels
    clear_variable_map = eu5ab_upgrade_source_civil
    remove_variable = eu5ab_upgrade_snapshot_owner
    save_scope_as = eu5ab_upgrade_location
    every_buildings_in_location = {
        limit = { OR = { $SOURCES$ } }
        scope:eu5ab_upgrade_location = {
            add_to_variable_list = { name = eu5ab_upgrade_sources target = prev }
        }
    }
}
eu5ab_capture_upgrade_source = {
    save_scope_as = eu5ab_upgrade_source
    location = {
        remove_list_variable = { name = eu5ab_upgrade_sampled_sources target = scope:eu5ab_upgrade_source }
        remove_from_variable_map = { name = eu5ab_upgrade_reserved_levels key = scope:eu5ab_upgrade_source }
        remove_from_variable_map = { name = eu5ab_upgrade_source_levels key = scope:eu5ab_upgrade_source }
        remove_from_variable_map = { name = eu5ab_upgrade_source_civil key = scope:eu5ab_upgrade_source }
    }
    if = { limit = { exists = scope:eu5ab_engine_upgrade_reserved
        scope:eu5ab_engine_upgrade_reserved >= 0
        scope:eu5ab_engine_upgrade_reserved <= building_level }
        location = {
            add_to_variable_list = { name = eu5ab_upgrade_sampled_sources target = scope:eu5ab_upgrade_source }
            add_to_variable_map = { name = eu5ab_upgrade_reserved_levels key = scope:eu5ab_upgrade_source value = scope:eu5ab_engine_upgrade_reserved }
            add_to_variable_map = { name = eu5ab_upgrade_source_levels key = scope:eu5ab_upgrade_source value = scope:eu5ab_upgrade_source.building_level }
            add_to_variable_map = { name = eu5ab_upgrade_source_civil key = scope:eu5ab_upgrade_source value = num_civil_constructions }
            set_variable = { name = eu5ab_upgrade_snapshot_owner value = owner }
        }
    }
}
'''.replace('$SOURCES$', sources or 'always = no')
    triggers = '''# Building scope. Snapshot lifetime is the location scan request.
eu5ab_upgrade_source_sampled = {
    location = {
        exists = var:eu5ab_upgrade_snapshot_owner
        is_target_in_variable_list = { name = eu5ab_upgrade_sampled_sources target = prev }
        has_variable_map = eu5ab_upgrade_source_civil
        has_variable_map = eu5ab_upgrade_source_levels
        # A missing/zero entry is not a readable event target. Empty queues
        # already prove availability and need no sampled job credit.
        trigger_if = { limit = {
            exists = var:eu5ab_upgrade_snapshot_owner
            has_variable_map = eu5ab_upgrade_source_civil
            has_variable_map = eu5ab_upgrade_source_levels
        }
            is_key_in_variable_map = { name = eu5ab_upgrade_source_civil target = prev }
            is_key_in_variable_map = { name = eu5ab_upgrade_source_levels target = prev }
            trigger_if = { limit = {
                is_key_in_variable_map = { name = eu5ab_upgrade_source_civil target = prev }
                is_key_in_variable_map = { name = eu5ab_upgrade_source_levels target = prev }
            }
                owner = var:eu5ab_upgrade_snapshot_owner
                "variable_map(eu5ab_upgrade_source_civil|prev)" = num_civil_constructions
                "variable_map(eu5ab_upgrade_source_levels|prev)" = prev.building_level
            }
        }
    }
}
eu5ab_upgrade_source_available = {
    building_level >= 1
    OR = {
        location = { num_civil_constructions = 0 }
        AND = { eu5ab_upgrade_source_sampled = yes building_level > eu5ab_upgrade_reserved_count }
    }
}
'''
    values = '''# Zero map values can disappear; sampled membership proves zero.
eu5ab_upgrade_reserved_count = { value = 0
    if = { limit = { eu5ab_upgrade_source_sampled = yes }
        location = { if = { limit = { has_variable_map = eu5ab_upgrade_reserved_levels is_key_in_variable_map = { name = eu5ab_upgrade_reserved_levels target = prev } }
            add = "variable_map(eu5ab_upgrade_reserved_levels|prev)" } }
    }
}
'''
    from .building_capacity import RECEIPT_CURRENT
    guis = '''eu5ab_gui_capture_upgrade_source = {
    saved_scopes = { eu5ab_engine_country eu5ab_capacity_ticket eu5ab_engine_upgrade_reserved }
    is_valid = { always = yes }
    effect = {
        if = { limit = { location = {
            $RECEIPT$
            owner = scope:eu5ab_engine_country
            is_target_in_variable_list = { name = eu5ab_upgrade_sources target = prev }
        } }
            eu5ab_capture_upgrade_source = yes
        }
    }
}
'''.replace('$RECEIPT$', RECEIPT_CURRENT)
    return effects, triggers, values, guis


def capture_widget():
    # Runs alongside the existing parallel sample, before capacity publication.
    # Missing rows stay conservative and never delay the location worker.
    return '''widget = {
        datamodel = "[Location.MakeScope.GetList('eu5ab_upgrade_sources')]"
        item = { widget = {
            datacontext = "[Scope.GetBuilding]"
            datamodel = "[Location.MakeScope.GetList('eu5ab_capacity_tickets')]"
            item = { widget = {
                state = { name = eu5ab_worker_parallel_sample
                    on_finish = "[GetScriptedGui('eu5ab_gui_capture_upgrade_source').Execute(GuiScope.SetRoot(Building.MakeScope).AddScope('eu5ab_engine_country', GetPlayer.MakeScope).AddScope('eu5ab_capacity_ticket', MakeScopeValue(Scope.GetValue)).AddScope('eu5ab_engine_upgrade_reserved', MakeScopeValue(Building.GetLevelsUnderUpgrade)).End)]"
                }
            } }
        } }
    }'''
