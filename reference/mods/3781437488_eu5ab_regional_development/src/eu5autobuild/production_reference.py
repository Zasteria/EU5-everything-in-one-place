"""Current script recipes and native type efficiency, without output allocation.

Only a selected reference building is inspected. Location goods_output is not
an individual project's output. The native building_efficiency reader supplies
the reference scale; its native semantics require in-game validation.
"""
import math


def capacity(recipe, quantity, efficiency):
    if not all(isinstance(v, (int, float)) and math.isfinite(v) and v >= 0
               for v in (recipe, quantity, efficiency)):
        raise ValueError('Invalid production reference')
    return recipe * quantity * efficiency


def render(models, goods):
    triggers, values, cases = [], [], []
    for building, model in sorted(models.items()):
        checks = []
        identities = sorted({m.production_method_id for slot in model.slots for m in slot})
        recognized = ' '.join(f'this = production_method:{m}' for m in identities)
        checks.append('NOT = { any_production_method_of_building = { NOT = { OR = { ' +
                      (recognized or 'always = no') + ' } } } }')
        for slot in model.slots:
            methods = [f'any_production_method_of_building = {{ this = production_method:{m.production_method_id} }}'
                       for m in slot]
            checks.append('OR = { ' + ' '.join(methods or ['always = no']) + ' }')
            for i, left in enumerate(methods):
                for right in methods[i + 1:]:
                    checks.append(f'NOT = {{ AND = {{ {left} {right} }} }}')
        cases.append(f'building_type:{building} = {{ {" ".join(checks)} }}')
    triggers.append('eu5ab_pr_recipe_known = { switch = { trigger = building_type '
                    'fallback = { always = no } ' + ' '.join(cases) + ' } }')
    checks, branches = [], []
    for building in sorted(models):
        checks.append(f'building_type:{building} = {{ location = {{ building_efficiency = {{ building_type = building_type:{building} value >= 0 }} }} }}')
        branches.append(f'{"else_if" if branches else "if"} = {{ limit = {{ building_type = building_type:{building} }} value = "location.building_efficiency(building_type:{building})" }}')
    triggers.append('eu5ab_pr_efficiency_known = { building_level > 0 switch = { trigger = building_type fallback = { always = no } ' + ' '.join(checks) + ' } }')
    values.append('eu5ab_pr_efficiency = { value = 0 ' + ' '.join(branches) + ' }')
    values.append('eu5ab_pr_jobs_per_level = { value = 0 if = { limit = { building_level > 0 building_employment_size_amount >= 0 } value = building_employment_size_amount divide = building_level } }')
    for good in goods:
        for kind, prop in (('output', 'outputs'), ('input', 'inputs')):
            branches = []
            for building, model in sorted(models.items()):
                terms = []
                for slot in model.slots:
                    for method in slot:
                        amount = getattr(method, prop).get(good, 0)
                        if amount > 0:
                            terms.append(f'if = {{ limit = {{ any_production_method_of_building = {{ this = production_method:{method.production_method_id} }} }} add = {amount:g} }}')
                if terms:
                    branches.append(f'{"else_if" if branches else "if"} = {{ limit = {{ building_type = building_type:{building} }} {" ".join(terms)} }}')
            values.append(f'eu5ab_pr_nominal_{kind}_{good} = {{ value = 0 if = {{ limit = {{ eu5ab_pr_recipe_known = yes }} value = eu5ab_pr_nominal_{kind}_{good}_validated }} }}')
            # Only the invocation-local quote path can skip identity validation.
            values.append(f'eu5ab_pr_nominal_{kind}_{good}_validated = {{ value = 0 {" ".join(branches)} }}')
            values.append(f'eu5ab_pr_reference_{kind}_{good} = {{ value = eu5ab_pr_nominal_{kind}_{good} multiply = eu5ab_pr_efficiency }}')
    from .script_syntax import parse, render as script
    return tuple(script(parse(text)) + '\n' for text in ('\n'.join(triggers), '\n'.join(values)))


def render_candidate_effects(models):
    branches = ' '.join(f'''building_type:{b} = {{ ordered_location_in_market = {{
        limit = {{ owner ?= scope:eu5ab_pf_reference_country
            NOT = {{ this = scope:eu5ab_pf_reference_destination }}
            has_building_with_at_least_one_level = {b} }}
        order_by = 1 max = 1 check_range_bounds = no
        eu5ab_find_local_production_reference = yes
    }} }}''' for b in sorted(models))
    return '''# One target-type donor. Fallback visits only this market, filters
# for other owned locations by type, and inspects at most one matching location.
eu5ab_prepare_production_reference = {
    remove_variable = eu5ab_pf_reference_building
    remove_variable = eu5ab_quote_production_search_type
    remove_variable = eu5ab_quote_production_search_reference
    save_scope_as = eu5ab_pf_reference_destination
    # Resolve the destination owner once, before dereferencing it. Donor
    # locations/buildings may be unowned; their comparisons use safe links.
    if = { limit = { exists = owner }
        owner = { save_scope_as = eu5ab_pf_reference_country }
        eu5ab_find_local_production_reference = yes
        if = { limit = { NOT = { exists = var:eu5ab_pf_reference_building } exists = market }
            market = { switch = { trigger = scope:eu5ab_candidate_building
''' + branches + '''
            } }
        }
    }
    # Only synchronous quote processing carries this proof to its next step.
    if = { limit = { has_variable = eu5ab_quote_production_active }
        set_variable = { name = eu5ab_quote_production_search_type value = scope:eu5ab_candidate_building }
    }
}
eu5ab_find_local_production_reference = {
    every_buildings_in_location = {
        limit = { building_type = { this = scope:eu5ab_candidate_building }
            owner ?= scope:eu5ab_pf_reference_country NOT = { exists = estate_type }
            building_level > 0 eu5ab_pr_recipe_known = yes eu5ab_pr_efficiency_known = yes
            scope:eu5ab_pf_reference_destination = { NOT = { exists = var:eu5ab_pf_reference_building } } }
        save_scope_as = eu5ab_pf_reference_donor
        scope:eu5ab_pf_reference_destination = {
            set_variable = { name = eu5ab_pf_reference_building value = scope:eu5ab_pf_reference_donor }
            if = { limit = { has_variable = eu5ab_quote_production_active }
                set_variable = { name = eu5ab_quote_production_search_reference value = scope:eu5ab_pf_reference_donor }
            }
        }
    }
}
'''
