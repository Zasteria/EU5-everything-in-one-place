"""Area-local industrial intent, sampled with the existing capacity request."""
import json
from pathlib import Path

from .game_data import _atoms, _blocks_from_directory, _first_block
from .production import LOCATION, selected_method_branches

SNAPSHOT = Path(__file__).resolve().parents[2] / '.metadata/eu5ab_industry_types.json'
MAX_BONUS = 500


def extract_industries(game_root):
    definitions = _blocks_from_directory(Path(game_root) / 'game/in_game/common/industry_types')
    result = {}
    for name, body in sorted(definitions.items()):
        goods = _first_block(body, 'goods')
        if not goods or any(key is not None or isinstance(value, list) for key, value in goods):
            raise ValueError(f'Unsupported industry goods definition: {name}')
        result[name] = sorted(set(_atoms(goods)))
    if not result:
        raise ValueError('No industry definitions found')
    return result


def load_industries():
    return json.loads(SNAPSHOT.read_text(encoding='utf-8-sig'))


def render_values(models, industries):
    by_good = {}
    for industry, goods in industries.items():
        for good in goods:
            by_good.setdefault(good, []).append(industry)
    values, cases = [], []
    for building, model in sorted(models.items()):
        if not any(q > 0 and g in by_good for slot in model.slots for m in slot for g, q in m.outputs.items()):
            continue
        total, matched = [], []
        for index, slot in enumerate(model.slots):
            def amounts(method, matching=False):
                lines = []
                for good, quantity in method.outputs.items():
                    if quantity <= 0:
                        continue
                    amount = f'add = {{ value = "default_price(goods:{good})" min = 0 multiply = {quantity:g} }}'
                    if not matching:
                        lines.append(amount)
                    elif good in by_good:
                        supported = ' '.join(f'is_target_in_variable_list = {{ name = eu5ab_industry_types target = industry_type:{i} }}' for i in by_good[good])
                        lines.append(f'if = {{ limit = {{ {LOCATION} = {{ OR = {{ {supported} }} }} }} {amount} }}')
                return lines
            total += selected_method_branches(building, index, slot, amounts)
            matched += selected_method_branches(building, index, slot, lambda m: amounts(m, True))
        stem = f'eu5ab_industry_{building}'
        values += [f'{stem}_total = {{ value = 0 {" ".join(total)} }}',
                   f'{stem}_matched = {{ value = 0 {" ".join(matched)} }}']
        cases.append(f'''{'if' if not cases else 'else_if'} = {{ limit = {{ this = building_type:{building} }}
            if = {{ limit = {{ {stem}_total > 0 }} value = {stem}_matched divide = {stem}_total multiply = {MAX_BONUS} }} }}''')
    values.append('''eu5ab_industry_candidate_score = { value = 0
        if = { limit = { scope:eu5ab_candidate_location = {
            eu5ab_industry_snapshot_current = yes has_variable_list = eu5ab_industry_types } }
            $CASES$
        }
        min = 0 max = 500
    }'''.replace('$CASES$', '\n'.join(cases)))
    return '\n'.join(values) + '\n'


def count_argument():
    from .gui_integer import nonnegative_int32
    return ".AddScope('eu5ab_industry_count', MakeScopeValue(" + nonnegative_int32('GetDataModelSize(GetPlayer.GetIndustryPromotions)') + '))'


def render():
    from .building_capacity import RECEIPT_CURRENT, REQUEST_PENDING_CONDITIONS
    effects = '''eu5ab_clear_industry_snapshot = {
        clear_variable_list = eu5ab_industry_types
        clear_variable_list = eu5ab_industry_seen
        remove_variable = eu5ab_industry_sampled
        remove_variable = eu5ab_industry_expected
        remove_variable = eu5ab_industry_owner
        remove_variable = eu5ab_industry_ticket
        remove_variable = eu5ab_industry_ready
    }
    eu5ab_begin_industry_snapshot = {
        eu5ab_clear_industry_snapshot = yes
        set_variable = { name = eu5ab_industry_owner value = owner }
        set_variable = { name = eu5ab_industry_ticket value = var:eu5ab_capacity_request }
        set_variable = { name = eu5ab_industry_expected value = scope:eu5ab_industry_count }
    }
    eu5ab_capture_industry_promotion = {
        if = { limit = { NOT = { is_target_in_variable_list = { name = eu5ab_industry_seen target = scope:eu5ab_industry_promotion } } }
            add_to_variable_list = { name = eu5ab_industry_seen target = scope:eu5ab_industry_promotion }
            set_variable = { name = eu5ab_industry_sampled value = { value = eu5ab_industry_sampled_count add = 1 } }
            if = { limit = { owner = scope:eu5ab_industry_country area = scope:eu5ab_industry_area
                NOT = { is_target_in_variable_list = { name = eu5ab_industry_types target = scope:eu5ab_industry_type } } }
                add_to_variable_list = { name = eu5ab_industry_types target = scope:eu5ab_industry_type }
            }
        }
    }
    eu5ab_finish_industry_snapshot = {
        remove_variable = eu5ab_industry_ready
        if = { limit = { exists = var:eu5ab_industry_owner owner = var:eu5ab_industry_owner
            has_variable = eu5ab_industry_ticket var:eu5ab_industry_ticket = var:eu5ab_capacity_request
            exists = scope:eu5ab_industry_count
            eu5ab_industry_expected_count = scope:eu5ab_industry_count
            eu5ab_industry_sampled_count = scope:eu5ab_industry_count }
            set_variable = eu5ab_industry_ready
        }
        # Incomplete sampling removes only the preference; never stalls a worker.
        else = { clear_variable_list = eu5ab_industry_types }
        clear_variable_list = eu5ab_industry_seen
    }
    '''
    triggers = '''eu5ab_industry_snapshot_current = {
        has_variable = eu5ab_industry_ready
        exists = var:eu5ab_industry_owner
        owner = var:eu5ab_industry_owner
        has_variable = eu5ab_industry_ticket
        has_variable = eu5ab_capacity_request
        var:eu5ab_industry_ticket = var:eu5ab_capacity_request
        var:eu5ab_capacity_month = owner.var:eu5ab_scan_month
        var:eu5ab_capacity_year = owner.var:eu5ab_scan_year
        owner = { has_variable = eu5ab_scan_active eu5ab_scan_month_current = yes }
    }
    '''
    values = '\n'.join(f'eu5ab_industry_{key}_count = {{ value = 0 if = {{ limit = {{ has_variable = eu5ab_industry_{key} }} add = var:eu5ab_industry_{key} }} }}' for key in ('sampled', 'expected'))
    guis = '''eu5ab_gui_begin_industry_snapshot = {
        saved_scopes = { eu5ab_industry_count }
        is_valid = { always = yes }
        effect = {
            if = { limit = { exists = scope:eu5ab_industry_count scope:eu5ab_industry_count >= 0 }
                every_in_list = { variable = eu5ab_worker_pending_locations
                    limit = { $PENDING$ }
                    eu5ab_begin_industry_snapshot = yes
                }
            }
        }
    }
    eu5ab_gui_capture_industry_promotion = {
        saved_scopes = { eu5ab_engine_country eu5ab_capacity_ticket eu5ab_industry_promotion eu5ab_industry_area eu5ab_industry_country eu5ab_industry_type }
        is_valid = { always = yes }
        effect = { if = { limit = {
            $RECEIPT$
            owner = scope:eu5ab_engine_country
            exists = var:eu5ab_industry_owner owner = var:eu5ab_industry_owner
            has_variable = eu5ab_industry_ticket var:eu5ab_industry_ticket = scope:eu5ab_capacity_ticket
            exists = scope:eu5ab_industry_promotion exists = scope:eu5ab_industry_area
            exists = scope:eu5ab_industry_country exists = scope:eu5ab_industry_type
        } eu5ab_capture_industry_promotion = yes } }
    }
    '''.replace('$PENDING$', REQUEST_PENDING_CONDITIONS).replace('$RECEIPT$', RECEIPT_CURRENT)
    return effects, triggers, values, guis


def capture_widget():
    # Keep the numeric ticket Scope innermost; the other native data contexts
    # survive the nested model. Match owner and area in the script callback.
    return '''widget = {
        datamodel = "[GetPlayer.GetIndustryPromotions]"
        item = { widget = {
            datamodel = "[Location.MakeScope.GetList('eu5ab_capacity_tickets')]"
            item = { widget = {
                state = { name = eu5ab_worker_parallel_sample
                    on_finish = "[GetScriptedGui('eu5ab_gui_capture_industry_promotion').Execute(GuiScope.SetRoot(Location.MakeScope).AddScope('eu5ab_engine_country', GetPlayer.MakeScope).AddScope('eu5ab_capacity_ticket', MakeScopeValue(Scope.GetValue)).AddScope('eu5ab_industry_promotion', IndustryPromotion.MakeScope).AddScope('eu5ab_industry_area', IndustryPromotion.GetArea.MakeScope).AddScope('eu5ab_industry_country', IndustryPromotion.GetOwner.MakeScope).AddScope('eu5ab_industry_type', IndustryPromotion.GetType.MakeScope).End)]"
                }
            } }
        } }
    }'''
