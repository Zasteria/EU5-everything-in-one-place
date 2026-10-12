"""Opt-in counters for quote delivery, GUI bursts and candidate-pool reuse.

Worker hooks write only to their own location. Country totals are read on demand,
or written by serial GUI/reducer paths. The GUI pulse is an observation window,
not a frame clock. Nothing here changes an automation guard or dispatch budget.
"""
from .quote_cache import FIELDS
from .queue_bridge import _block

PREFIX = 'eu5ab_sp_'
LOCAL_COUNTERS = (
    'worker_runs', 'ordinary_calls', 'input_calls', 'input_reuse', 'input_native',
    'ordinary_visits', 'input_visits', 'ordinary_repeat', 'input_repeat',
    'input_overlap', 'workforce_calls', 'workforce_off', 'workforce_hit', 'workforce_live',
)
REASONS = ('owner', 'context', 'ticket', 'fields', 'ready', 'unrequested', 'pass')
WINDOW_FIELDS = ('callbacks', 'accepted', 'screened', 'capacity_callbacks', 'merged')
QUOTE_COUNTERS = ('screen_early_rejected', 'screen_passed', 'screen_score_calls',
                  'quote_reference_calls', 'quote_production_calls', 'quote_output_calls',
                  'quote_input_calls', 'quote_economy_calls')
COUNTRY_COUNTERS = (
    'callbacks', 'accepted', 'screened', 'capacity_callbacks', 'merged',
    *QUOTE_COUNTERS,
    *(f'reject_{reason}' for reason in REASONS[:-1]), 'guard_pass',
    'merge_batches', 'merge_current', 'merge_max', 'windows', 'busy_windows',
    'windows_ge_16', 'windows_ge_64',
    *(f'window_{field}' for field in WINDOW_FIELDS),
    *(f'max_{field}' for field in WINDOW_FIELDS),
)
LOCAL_GATE = f'''has_variable = {PREFIX}country
    owner = var:{PREFIX}country
    var:{PREFIX}country = {{ has_variable = {PREFIX}enabled }}'''
COUNTRY_GATE = f'has_variable = {PREFIX}enabled'
GUI_GATE = f'''exists = scope:eu5ab_engine_country
    scope:eu5ab_engine_country = {{ {COUNTRY_GATE} }}'''


def inc(name: str) -> str:
    """Lazy initialization keeps unused location counters absent."""
    key = PREFIX + name
    return (f'if = {{ limit = {{ has_variable = {key} }} change_variable = {{ name = {key} add = 1 }} }}\n'
            f'else = {{ set_variable = {{ name = {key} value = 1 }} }}')


def gated(body: str, gate: str = LOCAL_GATE) -> str:
    return f'if = {{ limit = {{ {gate} }}\n{body}\n}}'


def gui_count(field: str) -> str:
    return gated(f'scope:eu5ab_engine_country = {{ {inc(field)} {inc("window_" + field)} }}', GUI_GATE)


def log_value(label: str, expression: str) -> str:
    return f'''debug_log = EU5AB_SCAN_{label.upper()}
    set_local_variable = {{ name = {PREFIX}read value = {expression} }}
    local_var:{PREFIX}read = {{ debug_log_scopes = no }}'''


def render_quote_observer() -> str:
    # Classify before the original callback modifies its request/ready lists.
    # Ready precedes unrequested because accepting a row removes its request.
    missing = ' '.join(f'NOT = {{ exists = scope:eu5ab_engine_{f} }}' for f in FIELDS)
    guards = (
        'NOT = { owner = scope:eu5ab_engine_country }',
        'NOT = { eu5ab_quote_context_current = yes }',
        f'OR = {{ NOT = {{ exists = scope:eu5ab_quote_ticket }} NOT = {{ scope:eu5ab_quote_ticket = var:eu5ab_quote_ticket }} }}',
        f'OR = {{ NOT = {{ exists = scope:eu5ab_candidate_building }} {missing} }}',
        'is_target_in_variable_list = { name = eu5ab_quote_ready_types target = scope:eu5ab_candidate_building }',
        'NOT = { is_target_in_variable_list = { name = eu5ab_quote_requests target = scope:eu5ab_candidate_building } }',
    )
    lines = [gui_count('callbacks')]
    for i, (reason, guard) in enumerate(zip(REASONS, guards, strict=False)):
        lines.append(f'''{'if' if i == 0 else 'else_if'} = {{ limit = {{ {guard} }}
            scope:eu5ab_engine_country = {{ {inc('reject_' + reason)} }} }}''')
    lines.append(f'else = {{ scope:eu5ab_engine_country = {{ {inc("guard_pass")} }} }}')
    return 'eu5ab_probe_scan_quote = {\n' + '\n'.join(lines) + '\n}\n'


def render_effects() -> str:
    clear_local = '\n'.join(f'remove_variable = {PREFIX}{name}' for name in LOCAL_COUNTERS)
    clear_country = '\n'.join(f'remove_variable = {PREFIX}{name}' for name in COUNTRY_COUNTERS)
    init_country = '\n'.join(f'set_variable = {{ name = {PREFIX}{name} value = 0 }}' for name in COUNTRY_COUNTERS)
    update_max = '\n'.join(f'''set_variable = {{ name = {PREFIX}max_{field} value = {{
        value = var:{PREFIX}max_{field} min = var:{PREFIX}window_{field} }} }}''' for field in WINDOW_FIELDS)
    window_dump = '\n'.join(log_value('window_' + field, 'var:' + PREFIX + 'window_' + field) for field in WINDOW_FIELDS)
    window_clear = '\n'.join(f'set_variable = {{ name = {PREFIX}window_{field} value = 0 }}' for field in WINDOW_FIELDS)
    total_dump = '\n'.join(log_value(name,
        f'{{ value = 0 if = {{ limit = {{ has_variable = {PREFIX}{name} }} add = var:{PREFIX}{name} }} }}'
        if name in QUOTE_COUNTERS else 'var:' + PREFIX + name)
        for name in COUNTRY_COUNTERS if not name.startswith('window_'))
    local_sums = '\n'.join(f'''set_local_variable = {{ name = {PREFIX}sum_{name} value = 0 }}
    every_in_list = {{ variable = {PREFIX}locations
        limit = {{ has_variable = {PREFIX}{name} }}
        change_local_variable = {{ name = {PREFIX}sum_{name} add = var:{PREFIX}{name} }} }}
    {log_value(name, 'local_var:' + PREFIX + 'sum_' + name)}''' for name in LOCAL_COUNTERS)
    return f'''# Manual console: effect eu5ab_probe_scan_start/snapshot/stop = yes
eu5ab_probe_scan_stop = {{
    remove_variable = {PREFIX}enabled
    every_in_list = {{ variable = {PREFIX}locations
        {clear_local}
        remove_variable = {PREFIX}country
        clear_variable_list = {PREFIX}ordinary_seen
        clear_variable_list = {PREFIX}input_seen
    }}
    clear_variable_list = {PREFIX}locations
    {clear_country}
    remove_variable = {PREFIX}trace_left
}}
eu5ab_probe_scan_start = {{
    eu5ab_probe_scan_stop = yes
    save_scope_as = {PREFIX}start_country
    {init_country}
    set_variable = {PREFIX}enabled
    every_owned_location = {{
        set_variable = {{ name = {PREFIX}country value = scope:{PREFIX}start_country }}
        scope:{PREFIX}start_country = {{ add_to_variable_list = {{ name = {PREFIX}locations target = prev }} }}
    }}
    debug_log = EU5AB_SCAN_STARTED_V1
    debug_log_date = yes
}}
eu5ab_probe_scan_trace = {{
    if = {{ limit = {{ {COUNTRY_GATE} }}
        set_variable = {{ name = {PREFIX}trace_left value = 32 }}
        debug_log = EU5AB_SCAN_TRACE_NEXT_32_BUSY_GUI_WINDOWS
    }}
}}
eu5ab_probe_scan_flush_window = {{
    {update_max}
    if = {{ limit = {{ var:{PREFIX}window_callbacks >= 16 }} {inc('windows_ge_16')} }}
    if = {{ limit = {{ var:{PREFIX}window_callbacks >= 64 }} {inc('windows_ge_64')} }}
    if = {{ limit = {{ OR = {{ {' '.join(f'var:{PREFIX}window_{f} > 0' for f in WINDOW_FIELDS)} }} }}
        {inc('busy_windows')}
        if = {{ limit = {{ has_variable = {PREFIX}trace_left var:{PREFIX}trace_left > 0 }}
            debug_log = EU5AB_SCAN_GUI_WINDOW_BEGIN
            debug_log_date = yes
            {log_value('window_number', 'var:' + PREFIX + 'windows')}
            {window_dump}
            debug_log = EU5AB_SCAN_GUI_WINDOW_END
            change_variable = {{ name = {PREFIX}trace_left subtract = 1 }}
        }}
    }}
    {window_clear}
}}
eu5ab_probe_scan_pulse = {{
    if = {{ limit = {{ {COUNTRY_GATE} }}
        {inc('windows')}
        eu5ab_probe_scan_flush_window = yes
    }}
}}
eu5ab_probe_scan_snapshot = {{
    if = {{ limit = {{ {COUNTRY_GATE} }}
        debug_log = EU5AB_SCAN_SNAPSHOT_BEGIN_V1
        debug_log_date = yes
        # Close a partial window too, so pausing before the next pulse loses no peak.
        eu5ab_probe_scan_pulse = yes
        {total_dump}
        {local_sums}
        debug_log = EU5AB_SCAN_SNAPSHOT_END
    }}
}}
''' + render_quote_observer()


def replace_once(text: str, old: str, new: str, count: int = 1) -> str:
    if text.count(old) != count:
        raise ValueError(f'Scan probe hook expected {count} occurrences: {old!r}')
    return text.replace(old, new)


def instrument_effects(text: str, replace) -> str:
    def edit(name, fn):
        nonlocal text
        text = replace(text, name, fn(_block(text, name)))

    def prepend(name, body):
        edit(name, lambda s: replace_once(s, name + ' = {', name + ' = {\n' + body))

    prepend('eu5ab_run_location_worker', gated(inc('worker_runs')))
    prepend('eu5ab_clear_candidate_collection_cache', gated(
        f'clear_variable_list = {PREFIX}ordinary_seen\nclear_variable_list = {PREFIX}input_seen'))
    for kind, name in (('ordinary', 'eu5ab_collect_current_candidate_pools'),
                       ('input', 'eu5ab_collect_current_input_candidate_pools')):
        def pool(s, kind=kind):
            s = replace_once(s, 'save_scope_as = eu5ab_candidate_location',
                'save_scope_as = eu5ab_candidate_location\n' + gated(inc(kind + '_calls')))
            body = inc(kind + '_visits') + f'''
                if = {{ limit = {{ is_target_in_variable_list = {{ name = {PREFIX}{kind}_seen target = scope:eu5ab_candidate_building }} }}
                    {inc(kind + '_repeat')} }}
                else = {{ add_to_variable_list = {{ name = {PREFIX}{kind}_seen target = scope:eu5ab_candidate_building }} }}'''
            if kind == 'input':
                body += f'''if = {{ limit = {{ is_target_in_variable_list = {{ name = {PREFIX}ordinary_seen target = scope:eu5ab_candidate_building }} }}
                    {inc('input_overlap')} }}'''
                reuse_hook = '# eu5ab_candidate_catalog_reuse_probe_hook'
                native_hook = '# eu5ab_candidate_catalog_native_probe_hook'
                s = replace_once(s, reuse_hook, reuse_hook + '\n' + gated(inc('input_reuse')))
                s = replace_once(s, native_hook, native_hook + '\n' + gated(inc('input_native')))
            # Count the original admitted pool visit, after upstream readiness
            # and shortage filtering, rather than its preliminary cache lookup.
            return replace_once(s, 'eu5ab_prepare_candidate_collection_gate = yes',
                'scope:eu5ab_candidate_location = {\n' + gated(body) + '\n}\neu5ab_prepare_candidate_collection_gate = yes',
                2 if kind == 'input' else 1)
        edit(name, pool)
    def workforce(s):
        s = replace_once(s, 'remove_variable = eu5ab_candidate_workforce_passed',
                        gated(inc('workforce_calls')) + '\nremove_variable = eu5ab_candidate_workforce_passed')
        s = replace_once(s, 'limit = { owner.var:eu5ab_global_pause_low_workforce <= 0 }',
                        'limit = { owner.var:eu5ab_global_pause_low_workforce <= 0 }\n' + gated(inc('workforce_off')))
        marker = 'is_target_in_variable_list = { name = eu5ab_candidate_workforce_checked target = scope:eu5ab_candidate_building }\n\t\t\t}'
        s = replace_once(s, marker, marker + '\n' + gated(inc('workforce_hit')))
        marker = 'scope:eu5ab_candidate_building = { eu5ab_evaluate_candidate_workforce = yes }'
        return replace_once(s, marker, gated(inc('workforce_live')) + '\n' + marker)
    edit('eu5ab_prepare_candidate_workforce', workforce)
    # The merge is serial; worker counters above never write to the country.
    def merge(s):
        s = replace_once(s, 'save_scope_as = eu5ab_worker_merge_country',
            'save_scope_as = eu5ab_worker_merge_country\n' + gated(
                f'set_variable = {{ name = {PREFIX}merge_current value = 0 }}', COUNTRY_GATE))
        s = replace_once(s, 'remove_variable = eu5ab_worker_complete',
            f'scope:eu5ab_worker_merge_country = {{\n' + gated(
                inc('merged') + inc('window_merged') + inc('merge_current'), COUNTRY_GATE) + '\n}\nremove_variable = eu5ab_worker_complete')
        return s[:-1] + gated(f'''if = {{ limit = {{ var:{PREFIX}merge_current > 0 }} {inc('merge_batches')} }}
            set_variable = {{ name = {PREFIX}merge_max value = {{ value = var:{PREFIX}merge_max min = var:{PREFIX}merge_current }} }}''', COUNTRY_GATE) + '\n}'
    edit('eu5ab_merge_location_worker_results', merge)
    prepend('eu5ab_batch_screen_quote', gated(
        f'owner = {{ {inc("screened")} {inc("window_screened")} }}', f'owner = {{ {COUNTRY_GATE} }}'))
    prepend('eu5ab_batch_screen_quote', gated(f'''if = {{ limit = {{ exists = market NOT = {{
        exists = scope:eu5ab_engine_can_build scope:eu5ab_engine_can_build = yes
        scope:eu5ab_engine_cost > 0 eu5ab_cached_quote_capacity_factor > 0 }} }}
        owner = {{ {inc('screen_early_rejected')} }}
    }}''', f'owner = {{ {COUNTRY_GATE} }}'))
    edit('eu5ab_batch_screen_quote', lambda s: s[:-1] + gated(f'''if = {{ limit = {{
        is_target_in_variable_list = {{ name = eu5ab_batch_passed_types target = scope:eu5ab_candidate_building }} }}
        owner = {{ {inc('screen_passed')} }}
    }}''', f'owner = {{ {COUNTRY_GATE} }}') + '\n}')
    prepend('eu5ab_batch_compute_quote_score', gated(
        f'owner = {{ {inc("screen_score_calls")} }}', f'owner = {{ {COUNTRY_GATE} }}'))
    for effect, counter in (
        ('eu5ab_prepare_production_reference', 'quote_reference_calls'),
        ('eu5ab_prepare_quote_production_snapshot', 'quote_production_calls'),
        ('eu5ab_prepare_quote_production_output_quantities', 'quote_output_calls'),
        ('eu5ab_prepare_quote_production_input_quantities', 'quote_input_calls'),
        ('eu5ab_prepare_quote_economy_snapshot', 'quote_economy_calls'),
    ):
        prepend(effect, gated(f'owner = {{ {inc(counter)} }}',
            f'has_variable = eu5ab_quote_production_active owner = {{ {COUNTRY_GATE} }}'))
    return text + '\n' + render_effects()


def instrument_guis(text: str, replace) -> str:
    name = 'eu5ab_gui_capture_candidate_quote'
    s = _block(text, name)
    s = replace_once(s, 'effect = {', 'effect = {\n' + gated('eu5ab_probe_scan_quote = yes', GUI_GATE))
    marker = 'add_to_variable_map = { name = eu5ab_quote_cost'
    s = replace_once(s, marker, gui_count('accepted') + '\n' + marker)
    text = replace(text, name, s)
    name = 'eu5ab_gui_capture_building_capacity'
    s = _block(text, name)
    s = replace_once(s, 'effect = {', 'effect = {\n' + gui_count('capacity_callbacks'))
    return replace(text, name, s) + f'''
eu5ab_gui_scan_probe_pulse = {{
    is_shown = {{ {COUNTRY_GATE} }}
    is_valid = {{ always = yes }}
    effect = {{ eu5ab_probe_scan_pulse = yes }}
}}
'''


def render_widget() -> str:
    return '''
# Optional diagnostic clock. A delayed animation pulse is NOT a rendered frame.
widget = {
    visible = "[And(GetPlayer.Exists, GetScriptedGui('eu5ab_gui_scan_probe_pulse').IsShown(GuiScope.SetRoot(GetPlayer.MakeScope).End))]"
    state = { name = _show next = eu5ab_scan_probe_loop }
    state = { name = eu5ab_scan_probe_loop duration = 0.1
        on_finish = "[GetScriptedGui('eu5ab_gui_scan_probe_pulse').Execute(GuiScope.SetRoot(GetPlayer.MakeScope).End)]"
        next = eu5ab_scan_probe_loop }
}
'''


def apply(files, root, replace) -> None:
    effects = root / 'in_game/common/scripted_effects/eu5ab_scripted_effects.txt'
    guis = root / 'in_game/common/scripted_guis/eu5ab_scripted_guis.txt'
    widget = root / 'in_game/gui/eu5ab_engine_queue_window.gui'
    files[effects] = instrument_effects(files[effects], replace)
    files[guis] = instrument_guis(files[guis], replace)
    # Keep the probe within the existing registered scripted window.
    files[widget] = files[widget].rstrip()[:-1] + render_widget() + '\n}\n'
