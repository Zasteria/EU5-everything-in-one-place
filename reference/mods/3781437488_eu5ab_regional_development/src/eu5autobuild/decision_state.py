"""Explicit, generated save-state copies for the two manual decisions.

No native construction commands and no CMM-wide reset belong in this module.
Transport serials survive reset: a queued GUI receipt must never match a new job.
"""
import re


def inventory(text):
    """Collect owned storage, including fields removed only for save recovery."""
    scalars = set(re.findall(r'(?:set_variable|remove_variable|has_variable)\s*=\s*(eu5ab_\w+)', text))
    scalars.update(re.findall(r'(?:set_variable|change_variable|clamp_variable)\s*=\s*\{\s*name\s*=\s*(eu5ab_\w+)', text))
    lists = set(re.findall(r'(?:clear_variable_list|has_variable_list)\s*=\s*(eu5ab_\w+)', text))
    lists.update(re.findall(r'(?:add_to_variable_list|remove_list_variable)\s*=\s*\{\s*name\s*=\s*(eu5ab_\w+)', text))
    maps = set(re.findall(r'(?:clear_variable_map|has_variable_map)\s*=\s*(eu5ab_\w+)', text))
    maps.update(re.findall(r'(?:add_to_variable_map|remove_from_variable_map)\s*=\s*\{\s*name\s*=\s*(eu5ab_\w+)', text))
    return tuple(sorted(x) for x in (scalars, lists, maps))


def copy_state(fields, source, destination, rename=lambda n: n):
    """Copy storage between saved scopes; absence clears the destination.

    Map keys and list elements can be scope values, not just game objects.
    Keep the source scope explicitly throughout the iterators.
    """
    lines = []
    for kind, names in zip(('scalar', 'list', 'map'), fields):
        for name in names:
            target = rename(name)
            if kind == 'scalar':
                lines.append(f'''{destination} = {{ remove_variable = {target} }}
{source} = {{ if = {{ limit = {{ has_variable = {name} }}
    {destination} = {{ set_variable = {{ name = {target} value = {source}.var:{name} }} }} }} }}''')
            elif kind == 'list':
                lines.append(f'''{destination} = {{ clear_variable_list = {target} }}
{source} = {{ every_in_list = {{ variable = {name} save_scope_as = eu5ab_state_item
    {destination} = {{ add_to_variable_list = {{ name = {target} target = scope:eu5ab_state_item }} }} }} }}''')
            else:
                lines.append(f'''{destination} = {{ clear_variable_map = {target} }}
{source} = {{ every_key_in_variable_map = {{ variable = {name} save_scope_as = eu5ab_state_key
    {destination} = {{ add_to_variable_map = {{ name = {target} key = scope:eu5ab_state_key
        value = "{source}.variable_map({name}|scope:eu5ab_state_key)" }} }} }} }}''')
    return '\n'.join(lines)


def clear_state(fields):
    return '\n'.join(f'{operation} = {name}' for operation, names in zip(
        ('remove_variable', 'clear_variable_list', 'clear_variable_map'), fields) for name in names)


def rename_state(fields, rename):
    return tuple(tuple(rename(n) for n in names) for names in fields)


def profile_fields(settings, presets):
    scalars = [f'eu5ab_tpl_{slot}_{field}' for slot in range(1, 21) for field in
               ('exists', 'saved', 'name_id', 'name_selected', 'custom_name', 'preset_origin', 'paused', 'building_priorities_initialized')]
    scalars += [f'eu5ab_preset_{p}_paused' for p in presets]
    scalars += ['eu5ab_monthly_build_hard_cap' if s == 'monthly_build_hard_cap' else 'eu5ab_global_' + s
                for s in settings if s != 'performance_preset']
    scalars += ['eu5ab_candidate_priority_' + s for s in ('upgrade', 'expand', 'rgo', 'new')]
    return (tuple(scalars), ('eu5ab_candidate_priority_features',
            'cmm_list_items_eu5ab_regional_development__candidate_priority'),
            tuple(f'eu5ab_tpl_{s}_building_priorities' for s in range(1, 21)))


def cmm_copy(settings, source, destination, saving):
    lines = []
    for setting in settings:
        key = 'flag:eu5ab_regional_development__' + setting
        src, dst = ('cmm', 'eu5ab_profile_cmm') if saving else ('eu5ab_profile_cmm', 'cmm')
        lines.append(f'''{destination} = {{ remove_from_variable_map = {{ name = {dst} key = {key} }} }}
{source} = {{ if = {{ limit = {{ is_key_in_variable_map = {{ name = {src} target = {key} }} }}
    {destination} = {{ add_to_variable_map = {{ name = {dst} key = {key} value = "{source}.variable_map({src}|{key})" }} }} }} }}''')
    return '\n'.join(lines)


def render_profile(storage, settings, presets):
    fields = profile_fields(settings, presets)
    snapshot = lambda n: 'eu5ab_profile_saved_' + n
    saved = rename_state(fields, snapshot)
    # Runtime counters have no gameplay meaning after reset, but their identity
    # cannot be recycled while old GUI callbacks are in flight.
    protected = lambda n: n.startswith('eu5ab_profile_') or n.endswith(('_sequence', '_serial'))
    clear = clear_state(tuple(tuple(n for n in ns if not protected(n)) for ns in storage))
    clear_own_settings = '\n'.join(f'remove_from_variable_map = {{ name = cmm key = flag:eu5ab_regional_development__{s} }}' for s in settings)
    return f'''
eu5ab_profile_ensure_identity = {{
    if = {{ limit = {{ NOT = {{ has_variable = eu5ab_profile_token }} }}
        if = {{ limit = {{ has_global_variable = eu5ab_profile_next_token }}
            change_global_variable = {{ name = eu5ab_profile_next_token add = 1 }} }}
        else = {{ set_global_variable = {{ name = eu5ab_profile_next_token value = 1 }} }}
        set_variable = {{ name = eu5ab_profile_token value = global_var:eu5ab_profile_next_token }}
    }}
}}
eu5ab_profile_capture = {{
    {copy_state(fields, 'scope:eu5ab_profile_source', 'scope:eu5ab_profile_target', snapshot)}
    {cmm_copy(settings, 'scope:eu5ab_profile_source', 'scope:eu5ab_profile_target', True)}
    scope:eu5ab_profile_target = {{ set_variable = eu5ab_profile_pending }}
}}
eu5ab_profile_transfer = {{
    if = {{ limit = {{ exists = scope:old_country NOT = {{ this = scope:old_country }} }}
        save_scope_as = eu5ab_profile_target
        scope:old_country = {{
            save_scope_as = eu5ab_profile_source eu5ab_profile_ensure_identity = yes
            # Enrol existing bindings when upgrading a save to this feature.
            every_owned_location = {{ limit = {{ has_variable = eu5ab_policy_id }} eu5ab_profile_remember_location = yes }}
        }}
        set_variable = {{ name = eu5ab_profile_token value = scope:old_country.var:eu5ab_profile_token }}
        clear_variable_list = eu5ab_profile_locations
        scope:old_country = {{ every_in_list = {{ variable = eu5ab_profile_locations save_scope_as = eu5ab_profile_location
            scope:eu5ab_profile_target = {{ add_to_variable_list = {{ name = eu5ab_profile_locations target = scope:eu5ab_profile_location }} }} }} }}
        if = {{ limit = {{ scope:old_country = {{ has_variable = eu5ab_profile_pending }} }}
            {copy_state((*saved[:2], (*saved[2], 'eu5ab_profile_cmm')), 'scope:eu5ab_profile_source', 'scope:eu5ab_profile_target')}
            set_variable = eu5ab_profile_pending
        }}
        else = {{ eu5ab_profile_capture = yes }}
        clear_variable_list = eu5ab_profile_countries
        scope:old_country = {{ every_in_list = {{ variable = eu5ab_profile_countries save_scope_as = eu5ab_profile_country
            scope:eu5ab_profile_target = {{ add_to_variable_list = {{ name = eu5ab_profile_countries target = scope:eu5ab_profile_country }} }} }} }}
        add_to_variable_list = {{ name = eu5ab_profile_countries target = scope:old_country }}
    }}
}}
eu5ab_profile_remember_location = {{
    # Called only when this location is registered to its current owner.
    owner = {{ eu5ab_profile_ensure_identity = yes }}
    set_variable = {{ name = eu5ab_profile_data_token value = owner.var:eu5ab_profile_token }}
    save_scope_as = eu5ab_profile_location
    owner = {{ if = {{ limit = {{ NOT = {{ is_target_in_variable_list = {{
        name = eu5ab_profile_locations target = scope:eu5ab_profile_location }} }} }}
        add_to_variable_list = {{ name = eu5ab_profile_locations target = scope:eu5ab_profile_location }} }} }}
}}
eu5ab_profile_clear_owned_state = {{
    # Caller has verified that this country belongs to the requesting player.
    # Lost locations require both an explicit registration and its profile stamp.
    # A new human owner, or a newer registration to another Tag, excludes them.
    every_in_list = {{ variable = eu5ab_profile_locations
        limit = {{ has_variable = eu5ab_profile_data_token
            var:eu5ab_profile_data_token = scope:eu5ab_profile_target.var:eu5ab_profile_token
            OR = {{ owner = scope:eu5ab_profile_target owner = {{ is_human = no }} }} }}
        eu5ab_profile_clear_scope = yes remove_variable = eu5ab_profile_data_token
    }}
    every_owned_location = {{ eu5ab_profile_clear_scope = yes remove_variable = eu5ab_profile_data_token }}
    clear_variable_list = eu5ab_profile_locations
    eu5ab_profile_clear_scope = yes
}}
eu5ab_profile_clear_scope = {{
{clear}
}}
eu5ab_profile_reset = {{
    if = {{ limit = {{ is_human = yes }}
        save_scope_as = eu5ab_profile_target
        eu5ab_profile_ensure_identity = yes
        if = {{ limit = {{ NOT = {{ has_variable = eu5ab_profile_pending }} }}
            eu5ab_sync_cmm_settings = yes
            save_scope_as = eu5ab_profile_source eu5ab_profile_capture = yes
        }}
        # Do not clear a former Tag now controlled by a different human.
        every_in_list = {{ variable = eu5ab_profile_countries
            limit = {{ is_human = no NOT = {{ this = scope:eu5ab_profile_target }}
                var:eu5ab_profile_token = scope:eu5ab_profile_target.var:eu5ab_profile_token }}
            eu5ab_profile_clear_owned_state = yes
            {clear_own_settings}
            clear_variable_list = cmm_list_items_eu5ab_regional_development__candidate_priority
            remove_variable = cmm_list_initialized_eu5ab_regional_development__candidate_priority
            {clear_state(saved)} clear_variable_map = eu5ab_profile_cmm
            clear_variable_list = eu5ab_profile_countries remove_variable = eu5ab_profile_pending
        }}
        eu5ab_profile_clear_owned_state = yes
        save_scope_as = eu5ab_profile_source
        {copy_state(saved, 'scope:eu5ab_profile_source', 'scope:eu5ab_profile_target', lambda n: n.removeprefix('eu5ab_profile_saved_'))}
        {cmm_copy(settings, 'scope:eu5ab_profile_source', 'scope:eu5ab_profile_target', False)}
        {clear_state(saved)} clear_variable_map = eu5ab_profile_cmm
        remove_variable = eu5ab_profile_pending clear_variable_list = eu5ab_profile_countries
        eu5ab_sync_cmm_settings = yes eu5ab_ensure_annual_budget = yes
        eu5ab_select_first_player_template = yes
    }}
}}
'''
