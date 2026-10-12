"""Client visibility gates for one command per pending queue item.

Repeating a broadcast while the script dispatcher is busy queues duplicate
commands before the client's done markers update. A visible item's _show
animation sends once; the existing phase reset clears its done marker to rearm
a real retry. No local tickets or saved state are needed.
"""


STAGE_SCOPE = 'eu5ab_engine_queue_check_stage'


def stage_argument(stage: int) -> str:
    return f".AddScope('{STAGE_SCOPE}', MakeScopeValue('(CFixedPoint){stage}'))"


def item_states(kind: str, stage: int, command: str) -> str:
    args = ("GuiScope.SetRoot(Location.MakeScope)"
            ".AddScope('eu5ab_engine_country', GetPlayer.MakeScope)"
            + stage_argument(stage))
    if kind != 'rgo':
        args += ".AddScope('eu5ab_candidate_building', BuildingType.MakeScope)"
    return f'''visible_at_creation = no
        visible = "[And(GetPlayer.Exists, GetScriptedGui('eu5ab_gui_queue_{kind}_pending').IsShown({args}.End))]"
        state = {{ name = _hide alpha = 0 }}
        # Keep the native parallel sample/refresh ahead of the item command.
        # The former first broadcast also followed the controller's 0.45s setup.
        state = {{ name = _show alpha = 1 duration = 0.45 on_finish = "[{command}]" }}'''


def render_guis(phase_count: int) -> str:
    scopes = f'eu5ab_engine_country {STAGE_SCOPE}'
    country = '''has_variable = eu5ab_q_active eu5ab_queue_calendar_open = yes
            NOT = { has_variable = eu5ab_scan_resume_after_load }
            has_variable = eu5ab_q_phase NOT = { has_variable = eu5ab_q_fire }'''
    ordinary = '\n'.join(
        f'''AND = {{ scope:eu5ab_engine_country.var:eu5ab_q_phase = {phase}
            is_target_in_variable_list = {{ name = eu5ab_q_phase_{phase}_types target = scope:eu5ab_candidate_building }} }}'''
        for phase in range(1, phase_count + 1))
    return f'''# Read-only client gates. The server's existing effect guards still
# reject duplicate/late commands; these gates avoid emitting repeated commands.
eu5ab_gui_queue_candidate_pending = {{
    saved_scopes = {{ {scopes} eu5ab_candidate_building }}
    is_shown = {{
        exists = scope:{STAGE_SCOPE} exists = scope:eu5ab_candidate_building
        owner = scope:eu5ab_engine_country
        scope:eu5ab_engine_country = {{ {country}
            NOT = {{ has_variable = eu5ab_q_profit_selecting }}
            var:eu5ab_q_phase = scope:{STAGE_SCOPE}
        }}
        OR = {{ {ordinary} }}
        NOT = {{ is_target_in_variable_list = {{ name = eu5ab_q_done_types target = scope:eu5ab_candidate_building }} }}
    }}
}}
eu5ab_gui_queue_profit_pending = {{
    saved_scopes = {{ {scopes} eu5ab_candidate_building }}
    is_shown = {{
        exists = scope:{STAGE_SCOPE} scope:{STAGE_SCOPE} = 0
        exists = scope:eu5ab_candidate_building owner = scope:eu5ab_engine_country
        scope:eu5ab_engine_country = {{ {country} has_variable = eu5ab_q_profit_selecting }}
        NOT = {{ has_variable = eu5ab_q_profit_done }}
        is_target_in_variable_list = {{ name = eu5ab_q_profit_best_types target = scope:eu5ab_candidate_building }}
    }}
}}
'''
