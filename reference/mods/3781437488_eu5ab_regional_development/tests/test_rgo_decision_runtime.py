"""Run generated RGO decisions against injected native values."""
from copy import deepcopy
from decimal import Decimal as D
import re
import unittest

from tests import _generated as automation
from tests._governor_script_vm import GovernorScriptVM, parse
from tests.test_rgo_cost_runtime import RgoVM
from src.eu5autobuild.rgo_automation import raw_goods, price_factor


class RgoDecisionVM(RgoVM):
    def __init__(self, effects, triggers, values):
        super().__init__(effects, triggers, values)
        self.month = 0
        self.expiries = {}
        self.promotion_reads = 0
        self.queue_calendar_open = True
        self.markets = {
            'm1': dict(stock=D(1), exhaustion=False, supply=D(200), demand=D(100)),
            'm2': dict(stock=D(1), exhaustion=False, supply=D(200), demand=D(100)),
        }
        self.owners.update(c=self.ROOT, d='foreign')
        self.vars.update(c={}, d={}, foreign=deepcopy(self.vars[self.ROOT]), m1={}, m2={})
        for country in (self.ROOT, 'foreign'):
            self.vars[country].update({
                'eu5ab_build_pending_ready': True,  # The ordinary-building ledger has an independent VM.
                'eu5ab_global_price_min': D(80), 'eu5ab_global_price_max': D(125),
                'eu5ab_global_pause_low_workforce': D(1),
                'eu5ab_global_rgo_workforce_mode': D(1),
                'eu5ab_global_rgo_job_fill_deadline_months': D(180),
                'eu5ab_global_job_fill_deadline_months': D(12),
                'eu5ab_global_emergency_food_exhaustion_override': D(1),
                'eu5ab_global_emergency_food_stockpile_override': D(1),
                'eu5ab_candidate_priority_rgo': D(3), 'eu5ab_q_phase': D(7),
            })
        self.locations = {
            n: dict(method='mining', output_price=D(1), market='m1', good='iron',
                    price=D(100), queue=D(0), lumber=D(1), masonry=D(1),
                    workers=D(4), levels=D(4), idle=D(1), sources=D(10),
                    speed=D('.01'), need=D(100), output=D(6))
            for n in self.owners
        }
        self.lists = {n: {} for n in self.vars}
        self.maps = {n: {} for n in self.vars}
        self.scopes['eu5ab_engine_country'] = self.ROOT
        self.refresh()

    def refresh(self, country=None):
        self.execute(self.definitions['eu5ab_refresh_rgo_pending'], [country or self.ROOT])

    def target(self, word, stack):
        if word.endswith('.market'):
            return self.target('market', [self.target(word[:-7], stack)])
        if word == 'market':
            return self.locations[stack[-1]]['market']
        return super().target(word, stack)

    def value(self, x, stack):
        if not isinstance(x, str):
            return super().value(x, stack)
        if x in ('prev.market', 'market'):
            return self.target(x, stack)
        if '.variable_map(' in x:
            country, expression = x.split('.variable_map(', 1)
            return self.value('variable_map(' + expression, stack + [self.target(country, stack)])
        if x == 'modifier:max_constructions_at_same_time':
            return self.locations[stack[-1]].get('parallel_capacity', D(1))
        if x.startswith('goods:'):
            return x
        if x.startswith('default_price(goods:'):
            return D(1)
        if x in ('rgo_workers', 'rgo_level', 'raw_material_output'):
            return self.locations[stack[-1]][{'rgo_workers':'workers', 'rgo_level':'levels', 'raw_material_output':'output'}[x]]
        if x == 'raw_material':
            return 'goods:' + self.locations[stack[-1]]['good']
        if x == 'eu5ab_rgos_under_construction':
            return self.locations[stack[-1]]['queue']
        if x.startswith('eu5ab_queued_jobs_'):
            # Native building-job aggregation is executed in queue_ranking tests.
            row = self.locations[stack[-1]]
            return row.get('queued_building_jobs', D(0)) + row['queue'] * self.value('eu5ab_rgo_jobs_per_expansion', stack)
        if x.startswith(('market.goods_supply_in_market(', 'market.goods_demand_in_market(')):
            return self.value(x.removeprefix('market.'), stack + [self.locations[stack[-1]]['market']])
        if x == 'eu5ab_location_need_score':
            row = self.locations[stack[-1]]
            return row['need'] - (D(160) if 'eu5ab_recent_build_penalty' in self.vars[stack[-1]] else 0)
        if x == 'eu5ab_town_rights_rgo_score':
            return D(0)
        if x == 'eu5ab_location_combined_pop_promotion_speed':
            self.promotion_reads += 1
            return self.locations[stack[-1]]['speed']
        if x.startswith('unemployed_pops_of_pop_type_in_location('):
            row = self.locations[stack[-1]]
            return row['idle'] if 'laborers' in x else row['sources']
        if x.startswith('market.market_price(goods:'):
            good=x.split(':')[1].removesuffix(')')
            row=self.locations[stack[-1]]
            return row[good] if good in ('lumber', 'masonry') and good != row['good'] else row['price']/100
        if x.startswith(('goods_supply_in_market(', 'goods_demand_in_market(')):
            return self.markets[stack[-1]]['supply' if 'supply' in x else 'demand']
        if x == 'market_food_percentage':
            return self.markets[stack[-1]]['stock']
        return super().value(x, stack)

    def test(self, k, op, v, stack):
        if k == 'eu5ab_queue_calendar_open':
            return self.queue_calendar_open == (v == 'yes')
        if k == 'eu5ab_location_template_not_paused':
            return (not self.locations[stack[-1]].get('paused', False)) == (v == 'yes')
        if k == 'owner' and isinstance(v, list):
            return self.condition(v, stack + [self.owners[stack[-1]]])
        if k == 'owner':
            return self.owners[stack[-1]] == self.value(v, stack)
        if k == 'market':
            m=self.locations[stack[-1]]['market']
            return bool(m) and self.condition(v, stack+[m])
        if k == 'exists':
            if v.startswith('scope:'):
                return self.scopes.get(v[6:]) is not None
            if v.startswith('var:'):
                return self.value(v, stack) is not None
            return bool(self.locations[stack[-1]]['market']) if v == 'market' else True
        if k == 'raw_material' and isinstance(v, str):
            return self.value(v,stack) == 'goods:' + self.locations[stack[-1]]['good']
        if k == 'is_full_expanded_rgo':
            return v == 'no'
        if k == 'is_projected_to_run_out_of_food_stockpile':
            return self.markets[stack[-1]]['exhaustion'] == (v == 'yes')
        if k == 'modifier:allow_rgo_slave_demand':
            return v == 'no'
        if k == 'is_key_in_variable_map':
            data=dict((a,c) for a,_,c in v)
            return self.value(data['target'],stack) in self.maps[stack[-1]].get(data['name'],{})
        if k in self.triggers and k not in ('eu5ab_rgo_capacity_available', 'eu5ab_rgo_finance_available'):
            return self.condition(self.triggers[k],stack) == (v == 'yes')
        return super().test(k,op,v,stack)

    def execute(self, entries, stack):
        i=0
        while i<len(entries):
            k,_,v=entries[i]
            end=i+1
            if k == 'if':
                while end<len(entries) and entries[end][0] in ('else_if','else'):
                    end+=1
            if k in ('eu5ab_record_rgo_start', 'eu5ab_capture_rgo_start_output'):
                self.execute(self.definitions[k],stack)
            elif k.startswith('variable_map('):
                self.execute(v, stack + [self.value(k, stack)])
            elif k == 'every_owned_location':
                data=dict((a,c) for a,_,c in v)
                for location, owner in self.owners.items():
                    if owner == stack[-1] and self.condition(data.get('limit',[]),stack+[location]):
                        self.execute([e for e in v if e[0]!='limit'],stack+[location])
            elif k == 'switch':
                data=dict((a,c) for a,_,c in v)
                selected=self.value(data['trigger'],stack)
                if isinstance(selected, (D, int, float)) and selected == int(selected):
                    selected=str(int(selected))
                self.execute(data.get(selected,data.get('fallback',[])),stack)
            elif k in ('remove_from_variable_map','add_to_variable_map'):
                data=dict((a,c) for a,_,c in v)
                name,key=data['name'],self.value(data['key'],stack)
                mapping=self.maps[stack[-1]].setdefault(name,{})
                identity=stack[-1],name,key
                if k == 'remove_from_variable_map':
                    mapping.pop(key,None)
                    self.expiries.pop(identity,None)
                else:
                    mapping[key]=self.value(data['value'],stack)
                    if 'months' in data:
                        self.expiries[identity]=self.month+int(data['months'])
            else:
                super().execute(entries[i:end],stack)
            i=end

    def advance(self, months):
        self.month += months
        for identity, expiry in list(self.expiries.items()):
            if expiry <= self.month:
                country,name,key=identity
                self.maps[country][name].pop(key,None)
                del self.expiries[identity]

    def allowed(self, trigger, location='a'):
        return self.condition(self.triggers[trigger], [location])

    def number(self, value, location='a'):
        return self.value(value,[location])


class RgoDecisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        f=automation.generated_fixture()
        cls.effects={k:v for k,_,v in parse(f.effects)}
        cls.triggers={k:v for k,_,v in parse(f.triggers)}
        cls.values={k:v for k,_,v in parse(f.values)}
        cls.guis = f.scripted_guis

    def setUp(self):
        self.vm=RgoDecisionVM(self.effects,self.triggers,self.values)

    def test_full_existing_jobs_are_always_required(self):
        for switch in (0,1):
            for mode in (1,2):
                self.vm.vars['country']['eu5ab_global_pause_low_workforce']=D(switch)
                self.vm.vars['country']['eu5ab_global_rgo_workforce_mode']=D(mode)
                self.vm.locations['a']['workers']=D('3.999')
                self.assertFalse(self.vm.allowed('eu5ab_rgo_expansion_allowed'))
                self.vm.locations['a']['workers']=D(4)
                self.assertTrue(self.vm.allowed('eu5ab_rgo_expansion_allowed'))

    def test_three_workforce_modes_and_separate_horizon(self):
        row=self.vm.locations['a']
        row.update(idle=D(0),speed=D('.004'))
        self.assertTrue(self.vm.allowed('eu5ab_rgo_workforce_allowed'))
        self.assertEqual(self.vm.number('eu5ab_rgo_current_labor_factor'),1)
        self.assertEqual(self.vm.promotion_reads,0)
        settings=self.vm.vars['country']
        settings['eu5ab_global_rgo_workforce_mode']=D(2)
        self.assertTrue(self.vm.allowed('eu5ab_rgo_workforce_allowed')) # .004 * 1.5 * 180 = 1.08
        settings['eu5ab_global_rgo_job_fill_deadline_months']=D(12)
        self.assertFalse(self.vm.allowed('eu5ab_rgo_workforce_allowed'))
        settings['eu5ab_global_pause_low_workforce']=D(0)
        self.vm.promotion_reads=0
        self.assertTrue(self.vm.allowed('eu5ab_rgo_workforce_allowed'))
        self.assertEqual(self.vm.number('eu5ab_rgo_projected_promotion'),0)
        self.assertEqual(self.vm.promotion_reads,0)
        self.assertEqual(self.vm.number('eu5ab_rgo_current_labor_factor'),D('.4'))

    def test_price_curve_boundaries_and_all_raw_goods(self):
        self.assertIn('silver',raw_goods())
        for floor in (0,80,99,100,125):
            self.vm.vars['country']['eu5ab_global_price_min']=D(floor)
            for price in (0,79,80,81,90,95,99,100,101,125,126):
                self.vm.locations['a']['price']=D(price)
                self.assertEqual(self.vm.allowed('eu5ab_rgo_price_allowed'),price>floor)
                self.assertAlmostEqual(float(self.vm.number('eu5ab_rgo_price_factor')),price_factor(price,floor),places=4)
        self.vm.vars['country']['eu5ab_global_price_min']=D(80)
        for good in raw_goods():
            self.vm.locations['a'].update(good=good,price=D(95))
            self.assertEqual(self.vm.number('eu5ab_rgo_price_percent'),D(95))
            self.assertTrue(self.vm.allowed('eu5ab_rgo_price_allowed'))
        self.vm.locations['a']['market']=None
        self.assertFalse(self.vm.allowed('eu5ab_rgo_price_allowed'))

    def test_high_reference_and_old_penalties(self):
        self.vm.locations['a']['price']=D(100)
        before=self.vm.number('eu5ab_rgo_base_score')
        self.vm.locations['a']['price']=D(126)
        self.assertEqual(self.vm.number('eu5ab_rgo_base_score')-before,140)
        self.vm.vars['country']['eu5ab_global_price_max']=D(150)
        self.vm.locations['a']['price']=D(125)
        self.assertEqual(self.vm.number('eu5ab_rgo_base_score'),before+70)
        self.vm.vars['a'].update(eu5ab_recent_build_penalty=12,eu5ab_consecutive_rgo_expansions=10)
        self.assertEqual(self.vm.number('eu5ab_rgo_base_score'),before+70)
        self.vm.locations['a']['need']=D(-1000)
        self.assertFalse(self.vm.allowed('eu5ab_rgo_score_allowed'))

    def test_pending_scope_completion_cancel_and_failure(self):
        self.vm.reject=True
        self.vm.attempt()
        self.assertEqual(self.vm.number('eu5ab_rgo_pending_factor','b'),1)
        self.vm.reject=False
        self.vm.attempt()
        self.assertEqual(self.vm.number('eu5ab_rgo_pending_factor','b'),D('.9775'))
        self.vm.refresh('foreign')
        self.assertEqual(self.vm.number('eu5ab_rgo_pending_factor','d'),1)
        self.vm.locations['c']['market']='m2'
        self.assertEqual(self.vm.number('eu5ab_rgo_pending_factor','c'),1)
        self.vm.locations['c'].update(market='m1',good='silver')
        self.assertEqual(self.vm.number('eu5ab_rgo_pending_factor','c'),1)
        self.vm.attempt('b')
        self.assertEqual(self.vm.number('eu5ab_rgo_market_pending_quantity'),D(3))
        self.vm.locations['a']['queue']=D(0)
        self.vm.refresh()
        self.assertEqual(self.vm.number('eu5ab_rgo_market_pending_quantity'),D('1.5'))
        self.vm.locations['b'].update(queue=D(0),levels=D(5))
        self.vm.refresh()
        self.assertEqual(self.vm.number('eu5ab_rgo_market_pending_quantity'),D('1.5'))
        self.vm.locations['b']['workers']=D(5)
        self.vm.refresh()
        self.assertEqual(self.vm.number('eu5ab_rgo_market_pending_quantity'),0)

    def test_stacked_factors_and_both_emergency_switches(self):
        vm=self.vm
        vm.attempt()
        vm.vars['country']['eu5ab_global_pause_low_workforce']=D(0)
        vm.locations['b']['idle']=D(0)
        base=vm.number('eu5ab_rgo_base_score','b')
        self.assertEqual(vm.number('eu5ab_rgo_queue_order_score','b'),base*D('.9775')*D('.4'))
        vm.locations['b']['price']=D(90)
        self.assertEqual(vm.number('eu5ab_rgo_queue_order_score','b'),base*D('.9775')*D('.2'))
        vm.locations['b'].update(good='wheat',price=D(50),method='farming')
        vm.locations['c'].update(good='wheat',queue=D(20))
        vm.refresh()
        for field in ('stock','exhaustion'):
            vm.markets['m1'].update(stock=D('.25') if field=='stock' else D(1), exhaustion=field=='exhaustion')
            self.assertTrue(vm.allowed('eu5ab_rgo_price_allowed','b'))
            self.assertEqual(vm.number('eu5ab_rgo_price_factor','b'),1)
            self.assertEqual(vm.number('eu5ab_rgo_pending_factor','b'),1)
            self.assertEqual(vm.number('eu5ab_rgo_current_labor_factor','b'),D('.4'))
            setting='eu5ab_global_emergency_food_'+('stockpile' if field=='stock' else 'exhaustion')+'_override'
            vm.vars['country'][setting]=D(0)
            self.assertFalse(vm.allowed('eu5ab_rgo_price_allowed','b'))
            vm.vars['country'][setting]=D(1)
        vm.locations['b']['workers']=D(3)
        self.assertFalse(vm.allowed('eu5ab_rgo_expansion_allowed','b'))

    def test_queue_reselects_after_start_without_repeated_multiplication(self):
        vm=self.vm
        vm.locations['a']['output']=D(32)
        vm.locations['a']['need']=D(200)
        vm.locations['b']['need']=D(190)
        vm.locations['c'].update(need=D(150),good='silver')
        vm.lists['country']['eu5ab_q_phase_7_rgo_locations']=['a','b','c']
        for _ in range(3):
            vm.execute(vm.definitions['eu5ab_try_best_remaining_rgo'],['country'])
        self.assertEqual(vm.calls,['a','c','b'])
        vm.execute(vm.definitions['eu5ab_try_best_remaining_rgo'],['country'])
        self.assertEqual(vm.calls,['a','c','b'])

    def test_old_save_defaults_preserve_user_settings(self):
        vm=self.vm
        vm.maps['country']['cmm']={'flag:unrelated': D(7)}
        vm.execute(vm.definitions['eu5ab_initialize_rgo_settings'],['country'])
        self.assertEqual(vm.maps['country']['cmm']['flag:eu5ab_regional_development__rgo_job_fill_deadline_months'],180)
        vm.maps['country']['cmm']['flag:eu5ab_regional_development__rgo_workforce_mode']=D(2)
        vm.execute(vm.definitions['eu5ab_initialize_rgo_settings'],['country'])
        self.assertEqual(vm.maps['country']['cmm']['flag:unrelated'],7)
        self.assertEqual(vm.maps['country']['cmm']['flag:eu5ab_regional_development__rgo_workforce_mode'],2)

    def test_horizon_callback_steps_bounds_and_reset(self):
        vm = self.vm
        key = 'flag:eu5ab_regional_development__rgo_job_fill_deadline_months'
        for old, incoming, expected in (
            (180, 181, 181), (180, 179, 179),  # ordinary clicks
            (180, 185, 192), (180, 175, 168),  # Ctrl +/-12 months
            (180, 1200, 300), (180, 0, 60),   # Shift +/-120 months
            (1190, 1195, 1200), (10, 5, 0),  # Ctrl clamps
            (1198, 1200, 1200), (2, 0, 0),  # bound-clamped CMM writes
            (1200, 1200, 1200), (0, 0, 0),  # already at bound
        ):
            with self.subTest(old=old, incoming=incoming):
                vm.vars['country']['eu5ab_global_rgo_job_fill_deadline_months'] = D(old)
                vm.maps['country']['cmm'] = {key: D(incoming)}
                vm.scopes['setting'] = key
                vm.execute(vm.definitions['eu5ab_rgo_adjust_horizon_step'], ['country'])
                self.assertEqual(vm.maps['country']['cmm'][key], expected)
        vm.vars['country']['eu5ab_global_rgo_job_fill_deadline_months'] = D(175)
        vm.maps['country']['cmm'][key] = D(180)
        vm.scopes['cmm_reset_key'] = key
        vm.execute(vm.definitions['eu5ab_rgo_adjust_horizon_step'], ['country'])
        self.assertEqual(vm.maps['country']['cmm'][key], 180)

    def test_script_checks_consume_live_candidates_exactly_once(self):
        vm=self.vm
        vm.locations['a']['output']=D(32)
        effect=vm.definitions['eu5ab_process_script_rgo_queue']
        vm.vars['country'].update(eu5ab_q_active=1,eu5ab_q_processed=0)
        vm.locations['a']['need']=D(200)
        vm.locations['b']['need']=D(190)
        vm.locations['c'].update(need=D(150),good='silver')
        vm.lists['country']['eu5ab_q_phase_7_rgo_locations']=['a','b','c']
        for expected_count in (1,2,3,3,3):
            vm.scopes={'eu5ab_engine_country':'country'}
            vm.execute(effect,['country'])
            self.assertEqual(vm.vars['country']['eu5ab_q_processed'], expected_count)
        self.assertEqual(vm.calls,['a','c','b'])
        self.assertEqual(vm.vars['country']['eu5ab_q_processed'],3)

    def test_script_dispatch_respects_calendar_load_and_stage_barriers(self):
        vm = self.vm
        effect = vm.definitions['eu5ab_process_script_rgo_queue']
        vm.vars['country'].update(eu5ab_q_active=1,eu5ab_q_processed=0)
        vm.lists['country']['eu5ab_q_phase_7_rgo_locations']=['a']
        for flag in ('eu5ab_q_fire','eu5ab_q_profit_selecting','eu5ab_scan_resume_after_load'):
            vm.vars['country'][flag]=True
            vm.execute(effect,['country'])
            vm.vars['country'].pop(flag)
        vm.queue_calendar_open=False
        vm.execute(effect,['country'])
        self.assertEqual(vm.vars['country']['eu5ab_q_processed'],0)
        self.assertNotIn('eu5ab_q_done_rgo',vm.vars['a'])
        self.assertEqual(vm.calls,[])

    def test_cmf_controls_follow_master_and_selected_mode(self):
        prefix='eu5ab_regional_development__'
        for switch in (0,1):
            for mode in (1,2):
                vm=self.vm
                vm.maps['country']['cmm']={'flag:'+prefix+'pause_low_workforce':D(switch),
                                           'flag:'+prefix+'rgo_workforce_mode':D(mode)}
                for setting, expected in (
                    ('job_fill_deadline_months',bool(switch)),
                    ('rgo_workforce_mode',bool(switch)),
                    ('rgo_job_fill_deadline_months',bool(switch and mode==2)),
                    ('rgo_forced_relaxed',not switch),
                ):
                    block=automation._blocks_for_token(self.guis,'\n'+prefix+setting+'_on_changed = ')[0]
                    body=parse(block)[0][2]
                    shown=next(v for k,_,v in body if k=='is_shown')
                    self.assertEqual(vm.condition(shown,['country']),expected,(switch,mode,setting))

    def test_forecast_is_capped_and_cannot_be_negative(self):
        vm=self.vm
        vm.vars['country']['eu5ab_global_rgo_workforce_mode']=D(2)
        vm.locations['a'].update(idle=D(0),sources=D('.001'),speed=D(10))
        self.assertLess(vm.number('eu5ab_rgo_projected_promotion'),D('.1'))
        self.assertFalse(vm.allowed('eu5ab_rgo_workforce_allowed'))
        vm.locations['a']['speed']=D(-1)
        self.assertEqual(vm.number('eu5ab_rgo_projected_promotion'),0)
