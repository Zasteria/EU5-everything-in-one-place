"""Execute generated demand/price predicates with injected native facts."""
from dataclasses import asdict, replace
from itertools import product, zip_longest
from decimal import Decimal, ROUND_DOWN
from functools import cache
import re
import unittest

from src.eu5autobuild.engine import (
    AutomationContext, BuildingCandidate, GoodsMarketState, LocationState,
    MarketState, PauseReason, first_blocking_reason, granary_demand_present,
    windmill_demand_present, score_candidate_components,
    food_building_profit, granary_decay_return_present,
)
from src.eu5autobuild.food_infrastructure import (
    FOOD_BUILDING_FINAL_GATES, GRANARY_BUILDINGS, render_food_building_triggers, render_food_building_values,
    granary_monthly_savings, windmill_incremental_revenue,
)
from src.eu5autobuild.generator import (
    CATALOG_FILE, RULES_FILE, _food_support_trigger_lines, _support_trigger_lines,
)
from src.eu5autobuild.policy import load_building_catalog
from src.eu5autobuild.rules import AutomationThresholds, load_automation_rules
from tests._governor_script_vm import parse
from tests.test_irrigation_demand_runtime import IrrigationVM
from tests.test_engine import policy
from tests import _generated as automation
from tests.test_queue_recovery_runtime import QueueVM


@cache
def selected_output_definitions():
    fixture = automation.generated_fixture()
    return ({k: v for k, _, v in parse(fixture.triggers)},
            {k: v for k, _, v in parse(fixture.values)})


class FoodVM(IrrigationVM):
    def __init__(self, rules, context, building='granary', profit=-1, cost=40):
        super().__init__(rules, context)
        output_triggers, output_values = selected_output_definitions()
        self.triggers.update(output_triggers)
        self.definitions.update({k: v for k, v in output_values.items()
                                 if k.startswith(('eu5ab_recipe_', 'eu5ab_output_', 'eu5ab_market_price_'))})
        self.triggers.update({k: v for k, _, v in parse(render_food_building_triggers(rules))})
        self.definitions.update({k: v for k, _, v in parse(render_food_building_values(rules))})
        self.building = building
        self.raw_material = context.location.raw_material
        self.variables['eu5ab_global_price_max'] = 125
        self.variables['eu5ab_global_price_min'] = 75
        self.variables['eu5ab_global_economic_metric'] = context.country.economic_metric
        self.consumptions = [context.location.province_monthly_food_consumption or 0]
        self.preservations = [context.location.province_food_preservation or 0]
        self.province_locations = []
        self.visiting = {}
        self.native_values.update({
            'raw_material_output': context.location.raw_material_output,
            'province_max_food': context.location.province_food_capacity,
            'province_food_percentage': context.location.province_food_ratio,
            'province_monthly_food_production': context.location.province_monthly_food_production,
            'province.province_food': context.location.province_food_stock or 0,
            'modifier:local_food_decay': 0,
            'province.capital.modifier:local_food_decay': context.location.province_food_decay_base or 0,
            'modifier:global_food_decay': 0,
            'modifier:local_food_preservation_efficiency_modifier': 0,
            'modifier:local_raw_material_output': (context.location.rgo_output_factor
                if context.location.rgo_output_factor is not None else 1) - 1,
            'modifier:global_raw_material_output': 0,
        })
        if context.location.province_food_price is not None:
            self.native_values['province.capital.market.food_price'] = context.location.province_food_price
        for crop in ('wheat', 'rice', 'millet'):
            for scope in ('local', 'global'):
                self.native_values[f'modifier:{scope}_{crop}_output_modifier'] = 0
        for name, value in (('profit', profit), ('cost', cost),
                            ('rgo_revenue', context.location.rgo_monthly_revenue),
                            ('food_price', context.location.province_food_price)):
            if value is not None:
                self.native_values['scope:eu5ab_engine_' + name] = value
        if context.location.province_food_balance is not None:
            self.native_values['scope:eu5ab_engine_province_food_balance'] = context.location.province_food_balance
        if context.location.province_natural_food_balance is not None:
            self.native_values['scope:eu5ab_engine_province_food_natural'] = context.location.province_natural_food_balance

    def value(self, value):
        if isinstance(value, str):
            if value == 'scope:eu5ab_candidate_building':
                return 'building_type:' + self.building
            if value.startswith('var:'):
                return self.variables.get(value[4:], 0)
            if value.startswith('scope:eu5ab_candidate_location.eu5ab_'):
                return super().value(value.split('.', 1)[1])
            value = value.strip('"')
            value = value.removeprefix('scope:eu5ab_candidate_location.market.')
            query = re.fullmatch(r'(market_price|default_price|goods_supply_in_market|goods_demand_in_market)\(goods:([a-z_]+)\)', value)
            if query:
                kind, good = query.groups()
                state = self.context.market.goods.get(good, GoodsMarketState(0, 0))
                return {'market_price': state.price_ratio, 'default_price': 1,
                        'goods_supply_in_market': state.supply, 'goods_demand_in_market': state.demand}[kind]
        return super().value(value)

    def predicate(self, key, op, value):
        if key == 'exists' and value == 'province.capital.market':
            return 'province.capital.market.food_price' in self.native_values
        if key == 'exists' and value.startswith('scope:eu5ab_engine_'):
            return value in self.native_values
        if key == 'exists' and value == 'owner':
            return True
        if key == 'is_province_capital':
            return self.context.location.is_province_capital == (value == 'yes')
        if key == 'scope:eu5ab_candidate_building':
            return self.condition(value)
        if key == 'exists' and value in ('province', 'province.capital', 'province.capital.owner'):
            return self.context.location.province_food_capacity > 0
        if key in ('province', 'scope:eu5ab_candidate_location', 'scope:eu5ab_candidate_location.owner'):
            return self.condition(value)
        if key == 'scope:eu5ab_candidate_location.market':
            return self.context.market.available and self.condition(value)
        if key == 'any_location_in_province':
            for location in self.province_locations:
                self.visiting = location
                if self.condition(value):
                    return True
            return False
        if key == 'any_buildings_in_location':
            return self.visiting.get('construction', 0) > 0 and self.condition(value)
        if key == 'building_type':
            return value == self.visiting.get('building', 'building_type:granary')
        if key == 'building_levels_under_construction':
            return self.visiting.get('construction', 0) > float(value)
        if key == 'owner':
            return self.condition(value)
        if key == 'has_variable' and value == 'eu5ab_q_active':
            return self.visiting.get('queue_active', False)
        if key == 'is_target_in_variable_list':
            data = {k: v for k, _, v in value}
            return data['target'] in self.visiting.get(data['name'], [])
        return super().predicate(key, op, value)

    def gate(self, name):
        return self.condition(self.triggers[name])

    def run(self, entries, result=0):
        # Preserve the parent VM's full if/else-chain handling.
        index = 0
        while index < len(entries):
            key, _, body = entries[index]
            end = index + 1
            if key == 'if':
                while end < len(entries) and entries[end][0] in ('else_if', 'else'):
                    end += 1
            if key in ('province', 'owner'):
                result = self.run(body, result)
            elif key == 'province.capital':
                original = self.native_values['modifier:local_food_decay']
                self.native_values['modifier:local_food_decay'] = self.native_values['province.capital.modifier:local_food_decay']
                try:
                    result = self.run(body, result)
                finally:
                    self.native_values['modifier:local_food_decay'] = original
            elif key == 'every_location_in_province':
                modifier = 'modifier:local_food_preservation_efficiency_modifier'
                original = self.native_values[modifier]
                for consumption, preservation in zip_longest(self.consumptions, self.preservations, fillvalue=0):
                    self.native_values['food_consumption'] = consumption
                    self.native_values[modifier] = preservation
                    result = self.run(body, result)
                self.native_values[modifier] = original
            elif key in ('value', 'add', 'subtract', 'multiply', 'divide', 'min', 'max'):
                # Model native five-decimal fixed arithmetic, avoiding binary
                # floating-point errors at exact rate/return boundaries.
                left, right = Decimal(str(result)), Decimal(str(self.value(body)))
                if key == 'value': result = right
                elif key == 'add': result = left + right
                elif key == 'subtract': result = left - right
                elif key == 'multiply': result = left * right
                elif key == 'divide': result = left / right
                elif key == 'min': result = max(left, right)
                else: result = min(left, right)
                result = float(result.quantize(Decimal('.00001'), rounding=ROUND_DOWN))
            else:
                result = super().run(entries[index:end], result)
            index = end
        return result


class FoodInfrastructureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules = load_automation_rules(RULES_FILE)
        cls.catalog = load_building_catalog(CATALOG_FILE)
        cls.generated = automation.generated_fixture()

    def block(self, text, name):
        return parse(automation._blocks_for_token(text, '\n' + name + ' = ')[0])[0][2]

    def context(self, **location):
        return AutomationContext(location=LocationState(**({
            'province_monthly_food_consumption': 300,
            'fully_staffed_building_levels': 0,
            'supported_building_levels': 100,
        } | location)))

    def test_granary_uses_province_not_market_and_requires_storage_pressure(self):
        for building, ratio, capacity, production, market_food in product(
            sorted(GRANARY_BUILDINGS), (0, .74999, .75, 1), (0, 1000), (-10, 0, 10), (0, 1),
        ):
            ctx = replace(self.context(province_food_ratio=ratio, province_food_capacity=capacity,
                                       province_monthly_food_production=production),
                          market=MarketState(food_stockpile_ratio=market_food))
            expected = capacity > 0 and ratio >= .75
            vm = FoodVM(self.rules, ctx, building)
            self.assertEqual(vm.gate('eu5ab_candidate_has_granary_demand'), expected)
            self.assertEqual(granary_demand_present(ctx, self.rules), expected)

    def test_storage_threshold_configuration_and_unavailable_market(self):
        rules = replace(self.rules, thresholds=replace(self.rules.thresholds, granary_full_ratio=.95))
        ctx = self.context(province_food_capacity=1000, province_food_ratio=.94,
                           province_monthly_food_production=10)
        self.assertFalse(FoodVM(rules, ctx).gate('eu5ab_candidate_has_granary_demand'))
        for ratio in (0, -1, 1.01, float('nan')):
            with self.subTest(ratio=ratio), self.assertRaises(ValueError):
                AutomationThresholds.from_mapping(asdict(rules.thresholds) | {'granary_full_ratio': ratio})
        ctx = replace(self.context(raw_material='millet', raw_material_output=100),
                      market=MarketState(available=False, food_stockpile_ratio=0, projected_food_exhaustion=True))
        self.assertFalse(FoodVM(rules, ctx, 'windmill').gate('eu5ab_candidate_has_windmill_demand'))

    def test_pending_native_and_unconfirmed_approvals_block_other_locations(self):
        cases = [({}, True), ({'construction': 1}, False),
                 ({'construction': 1, 'building': 'building_type:village_granary'}, False),
                 ({'construction': 1, 'building': 'building_type:windmill'}, True),
                 ({'queue_active': True, 'eu5ab_q_approved_types': ['building_type:granary']}, False),
                 ({'queue_active': True, 'eu5ab_q_approved_types': ['building_type:village_granary']}, False),
                 ({'queue_active': False, 'eu5ab_q_approved_types': ['building_type:granary']}, True),
                 ({'queue_active': True, 'eu5ab_q_approved_types': ['building_type:granary'],
                   'eu5ab_q_confirmed_types': ['building_type:granary']}, True),
                 ({'queue_active': True, 'eu5ab_q_approved_types': ['building_type:village_granary'],
                   'eu5ab_q_confirmed_types': ['building_type:village_granary']}, True),
                 ({'queue_active': True, 'eu5ab_q_approved_types': ['building_type:granary', 'building_type:village_granary'],
                   'eu5ab_q_confirmed_types': ['building_type:granary']}, False),
                 ({'queue_active': True, 'eu5ab_q_approved_types': ['building_type:granary'],
                   'eu5ab_q_confirmed_types': ['building_type:village_granary']}, False)]
        for building, (other, expected) in product(sorted(GRANARY_BUILDINGS), cases):
            with self.subTest(building=building, other=other):
                vm = FoodVM(self.rules, self.context(province_food_capacity=1000), building)
                vm.province_locations = [{}, other]  # Another location in the same province.
                self.assertEqual(vm.gate('eu5ab_candidate_storage_project_available'), expected)

    def test_granary_final_net_balance_fails_closed_including_missing_bridge_value(self):
        for building, balance in product(sorted(GRANARY_BUILDINGS), (None, -10, 0, 0.001, 10)):
            ctx = self.context(province_food_capacity=1000, province_food_ratio=.95,
                               province_monthly_food_production=10, province_food_balance=balance)
            vm = FoodVM(self.rules, ctx, building)
            allowed = balance is not None and balance > 0
            self.assertEqual(vm.gate('eu5ab_candidate_has_granary_food_balance'), allowed)
            candidate = BuildingCandidate(building, (), 40, 1)
            reason = first_blocking_reason(policy(allowed_buildings=[building]), candidate, 1000, 2000,
                                           context=ctx, rules=self.rules)
            self.assertEqual(reason, PauseReason.NONE if allowed else PauseReason.NO_GRANARY_NEED)
        # Both normal and profit callbacks carry the verified native sum.
        expression = 'MakeScopeValue(Add_CFixedPoint(Location.GetProvince.GetMonthlyFood, Location.GetProvince.GetFoodFromMarket))'
        capture = next(line for line in self.generated.engine_queue_gui.splitlines()
                       if "eu5ab_gui_capture_candidate_quote').Execute" in line)
        self.assertIn(expression, capture)

    def test_real_approval_reserves_province_before_construction_is_visible(self):
        queue = QueueVM(self.generated.effects, self.generated.scripted_guis)
        queue.scopes.update(eu5ab_candidate_building='building_type:granary',
                            eu5ab_engine_cost=40, eu5ab_engine_income=0, eu5ab_engine_profit=-1)
        queue.vars[queue.ROOT]['eu5ab_q_active'] = 1
        queue.stubs.update(eu5ab_reserve_engine_candidate=lambda: None,
                           eu5ab_commit_candidate_construction_demand=lambda: None)
        before = FoodVM(self.rules, self.context(province_food_capacity=1000))
        self.assertTrue(before.gate('eu5ab_candidate_storage_project_available'))
        queue.run('eu5ab_approve_engine_candidate')
        before.province_locations = [{}, {
            'queue_active': True, **queue.lists['location'],
        }]
        self.assertFalse(before.gate('eu5ab_candidate_storage_project_available'))
        # After a failed start is confirmed, stale approval lists must not lock storage.
        before.province_locations[1]['eu5ab_q_confirmed_types'] = ['building_type:granary']
        self.assertTrue(before.gate('eu5ab_candidate_storage_project_available'))

    def test_generated_prices_follow_only_actual_crop_for_presets_and_custom_slots(self):
        scores = ['eu5ab_score_granary', 'eu5ab_score_template_slot_1', 'eu5ab_score_template_slot_20']
        floor = self.block(self.generated.triggers, 'eu5ab_output_not_oversupplied')
        for crop, expensive in product(('wheat', 'rice', 'millet'), repeat=2):
            ctx = replace(self.context(raw_material=crop, raw_material_output=10), market=MarketState(
                goods={g: GoodsMarketState(100, 100, 2 if g == expensive else .1)
                       for g in ('wheat', 'rice', 'millet')}))
            vm = FoodVM(self.rules, ctx, 'windmill')
            vm.native_values.update(eu5ab_global_price_max_ratio=1.25, eu5ab_global_price_min_ratio=.75)
            for name in scores:
                price_branches = [entry for entry in self.block(self.generated.values, name)
                                  if entry == ('add', '=', 'eu5ab_output_high_price_bonus')]
                self.assertEqual(vm.run(price_branches), self.rules.rgo_scores.high_price if crop == expensive else 0)
            self.assertEqual(vm.condition(floor), crop == expensive)
            vm.building = 'granary'
            self.assertTrue(vm.condition(floor))
            self.assertEqual(vm.run(price_branches), 0)

    def test_windmill_needs_actual_crop_output_and_matching_demand(self):
        for crop, output, food, price, supply in product(
            ('wheat', 'rice', 'millet', 'iron'), (0, 10), (0.2, 1), (1, 1.25, 1.251), (90, 100, 110),
        ):
            ctx = replace(self.context(raw_material=crop, raw_material_output=output),
                          market=MarketState(food_stockpile_ratio=food,
                                             goods={crop: GoodsMarketState(supply, 100, price)}))
            expected = crop != 'iron' and output > 0 and (food <= .25 or price > 1.25 or supply < 100)
            self.assertEqual(FoodVM(self.rules, ctx, 'windmill').gate('eu5ab_candidate_has_windmill_demand'), expected)
            self.assertEqual(windmill_demand_present(ctx, self.rules, 1.25), expected)

    def test_wrong_crop_prices_cannot_create_windmill_demand_or_bonus(self):
        candidate = BuildingCandidate('windmill', (), 40, 1)
        configured = policy(allowed_buildings=['windmill'])
        for actual in ('wheat', 'rice', 'millet'):
            for expensive in ('wheat', 'rice', 'millet'):
                ctx = replace(self.context(raw_material=actual, raw_material_output=10),
                              market=MarketState(goods={g: GoodsMarketState(100, 100, 2 if g == expensive else 1)
                                                        for g in ('wheat', 'rice', 'millet')}))
                vm = FoodVM(self.rules, ctx, 'windmill')
                self.assertEqual(vm.gate('eu5ab_candidate_has_windmill_demand'), actual == expensive)
                condition = parse('\n'.join(_support_trigger_lines((expensive,), self.catalog, '')))
                self.assertEqual(vm.condition(condition), actual == expensive)
                score = score_candidate_components(configured, candidate, ctx, self.rules)
                self.assertEqual('price_above_max' in score, actual == expensive)

    def test_storage_is_not_a_food_producer_or_goods_source(self):
        ctx = replace(self.context(), market=MarketState(food_stockpile_ratio=0, projected_food_exhaustion=True))
        for building in sorted(GRANARY_BUILDINGS):
            candidate = BuildingCandidate(building, (), 40, 10)
            vm = FoodVM(self.rules, ctx, building)
            self.assertFalse(vm.condition(parse('\n'.join(_food_support_trigger_lines(self.catalog, self.rules, '')))))
            self.assertEqual(score_candidate_components(policy(), candidate, ctx, self.rules)['market_need'], 0)
        for building in (*sorted(GRANARY_BUILDINGS), 'windmill', 'irrigation_systems'):
            self.assertEqual(self.catalog.get(building).output_goods, ())
            self.assertFalse(any(building in sources for sources in self.catalog.source_buildings_by_good.values()))

    def test_missing_data_and_existing_gates_are_not_bypassed(self):
        for building, reason in [('granary', PauseReason.NO_GRANARY_NEED),
                                 ('village_granary', PauseReason.NO_GRANARY_NEED),
                                 ('windmill', PauseReason.NO_WINDMILL_NEED)]:
            candidate = BuildingCandidate(building, (), 40, 1000)
            configured = policy(allowed_buildings=[building])
            self.assertEqual(first_blocking_reason(configured, candidate, 1000, 2000,
                                                  context=self.context(), rules=self.rules), reason)
        ctx = self.context(province_food_capacity=1000, province_food_ratio=.95,
                           province_monthly_food_production=10, province_food_balance=10)
        candidate = BuildingCandidate('granary', (), 40, .01)
        configured = policy(allowed_buildings=['granary'])
        self.assertEqual(first_blocking_reason(configured, candidate, 1000, 2000, context=ctx, rules=self.rules), PauseReason.NONE)
        for changes, expected in [({'inputs_available': False}, PauseReason.INPUT_SHORTAGE),
                                  ({'labor_available': False}, PauseReason.LABOR_SHORTAGE),
                                  ({'cost': 1001}, PauseReason.CASH_RESERVE)]:
            self.assertEqual(first_blocking_reason(configured, replace(candidate, **changes), 1000, 2000,
                                                  context=ctx, rules=self.rules), expected)
        for gate, _ in FOOD_BUILDING_FINAL_GATES:
            self.assertTrue(FoodVM(self.rules, self.context(), 'fruit_orchard').gate(gate))

    def test_reserve_target_sums_actual_consumption_and_stops_at_six_months(self):
        vm = FoodVM(self.rules, self.context(province_food_capacity=6000, province_food_ratio=1))
        vm.consumptions = [-100, -200, -700, 0]  # Native GUI consumption is a debit.
        self.assertEqual(vm.value('eu5ab_province_food_reserve_target'), 6000)
        self.assertFalse(vm.gate('eu5ab_candidate_has_granary_demand'))
        vm.native_values['province_max_food'] = 5999
        self.assertTrue(vm.gate('eu5ab_candidate_has_granary_demand'))
        vm.consumptions = [0, 0]
        self.assertFalse(vm.gate('eu5ab_candidate_has_granary_demand'))
        for invalid in (0, -1, 61, float('nan')):
            with self.assertRaises(ValueError):
                AutomationThresholds.from_mapping(asdict(self.rules.thresholds) | {'food_reserve_months': invalid})

    def test_import_or_local_surplus_can_refill_storage_even_when_exporting(self):
        for balance, natural in product((None, -20, 0, 20), (None, -100, 0, 20)):
            ctx = self.context(province_food_capacity=1000, province_food_ratio=.95,
                               province_food_balance=balance, province_natural_food_balance=natural)
            vm = FoodVM(self.rules, ctx)
            self.assertTrue(vm.gate('eu5ab_candidate_has_granary_demand'))
            expected = any(value is not None and value > 0 for value in (balance, natural))
            self.assertEqual(vm.gate('eu5ab_candidate_has_granary_food_balance'), expected)
            candidate = BuildingCandidate('granary', (), 40, 1, potential_profit=-1)
            reason = first_blocking_reason(policy(allowed_buildings=['granary']), candidate, 1000, 2000,
                                           context=ctx, rules=self.rules)
            self.assertEqual(reason, PauseReason.NONE if expected else PauseReason.NO_GRANARY_NEED)

    def test_preservation_uses_province_sum_and_capital_base_for_both_locations(self):
        # Native observations, including exactly 100% and more than 100%.
        samples = (
            (6990.60963, .005, [.55, .03557, .08204, .03810, .10], 19.29408),
            (10450, .005, [.60, .05, .05, .05, .05, .20], 26.125),
            (16050.1, .006, [.05, .70, .00002, .70], 39.16224),
        )
        for building, capital, (stock, base, contributions, loss) in product(
            sorted(GRANARY_BUILDINGS), (False, True), samples,
        ):
            preservation = float(sum(map(lambda x: Decimal(str(x)), contributions)))
            ctx = self.context(province_food_capacity=30000, province_food_stock=stock,
                               is_province_capital=capital, province_food_decay_base=base,
                               province_food_preservation=preservation)
            vm = FoodVM(self.rules, ctx, building)
            vm.preservations = contributions
            # Candidate climate and local preservation must not replace the
            # province-capital base or the sum, even for a non-capital candidate.
            vm.native_values['modifier:local_food_decay'] = .99
            vm.native_values['modifier:local_food_preservation_efficiency_modifier'] = .99
            vm.native_values['province.capital.modifier:local_food_decay'] = base - .005
            vm.native_values['modifier:global_food_decay'] = .005
            self.assertEqual(vm.value('eu5ab_province_food_preservation'), preservation)
            self.assertEqual(vm.value('eu5ab_province_monthly_food_decay'), loss)
            self.assertEqual(vm.value('eu5ab_granary_monthly_food_saved'),
                             granary_monthly_savings(stock, base, preservation))
        for preservation, saved in ((0, 2.4), (1, .7), (2, .3)):
            self.assertEqual(granary_monthly_savings(10000, .005, preservation), saved)
        self.assertEqual(granary_monthly_savings(0, .005, 0), 0)
        # Native precision can make a very small marginal improvement zero.
        self.assertEqual(granary_monthly_savings(10000, .00001, 1), 0)
        for invalid in (None, float('nan'), float('inf'), -1):
            self.assertIsNone(granary_monthly_savings(10000, .005, invalid))

    def test_nonpositive_base_disables_only_preservation_not_storage(self):
        for building, base, ratio in product(sorted(GRANARY_BUILDINGS), (0, -.015), (.74999, .75)):
            ctx = self.context(province_food_capacity=1000, province_food_stock=750,
                               province_food_ratio=ratio, province_food_balance=10,
                               province_food_decay_base=base, province_food_preservation=1,
                               province_food_price=1)
            vm = FoodVM(self.rules, ctx, building, profit=-1)
            self.assertEqual(vm.value('eu5ab_granary_monthly_food_saved'), 0)
            self.assertEqual(granary_monthly_savings(750, base, 1), 0)
            candidate = BuildingCandidate(building, (), 40, 1, potential_profit=-1)
            self.assertEqual(food_building_profit(candidate, ctx), -1)
            self.assertFalse(granary_decay_return_present(candidate, ctx, self.rules))
            self.assertEqual(vm.gate('eu5ab_candidate_has_granary_food_balance'), ratio >= .75)
            self.assertEqual(first_blocking_reason(policy(allowed_buildings=[building]), candidate,
                1000, 2000, context=ctx, rules=self.rules),
                PauseReason.NONE if ratio >= .75 else PauseReason.NO_GRANARY_NEED)

    def test_decay_only_project_must_cover_operation_and_capital_cost(self):
        candidate = BuildingCandidate('granary', (), 40, 1, potential_profit=-1)
        for granary, price, capital, preservation, profit, cost in product(
            sorted(GRANARY_BUILDINGS), (None, 0, .1, 1), (False, True), (0, 1.45), (-1, 0, 1), (40, 10000),
        ):
            ctx = self.context(province_food_capacity=10000, province_food_ratio=.5,
                               province_food_stock=5000, province_monthly_food_consumption=100,
                               province_food_balance=-10, province_food_price=price,
                               is_province_capital=capital, province_food_decay_base=.01,
                               province_food_preservation=preservation)
            building = replace(candidate, id=granary, cost=cost, potential_profit=profit)
            vm = FoodVM(self.rules, ctx, granary, profit=profit, cost=cost)
            expected = granary_decay_return_present(building, ctx, self.rules)
            self.assertEqual(vm.gate('eu5ab_candidate_has_granary_food_balance'), expected)
            reason = first_blocking_reason(policy(allowed_buildings=[granary]), building, 20000, 30000,
                                           context=ctx, rules=self.rules)
            self.assertEqual(reason, PauseReason.NONE if expected else PauseReason.NO_GRANARY_NEED)
        vm = FoodVM(self.rules, ctx, profit=None)
        self.assertFalse(vm.gate('eu5ab_candidate_has_granary_food_balance'))

    def test_windmill_uses_all_four_modifiers_and_native_total_sale_revenue(self):
        for crop in ('wheat', 'rice', 'millet'):
            ctx = self.context(raw_material=crop, raw_material_output=24,
                               rgo_monthly_revenue=240, rgo_output_factor=2.4)
            vm = FoodVM(self.rules, ctx, 'windmill', profit=-3)
            vm.native_values.update({
                'modifier:local_raw_material_output': .2,
                'modifier:global_raw_material_output': .3,
                f'modifier:local_{crop}_output_modifier': .4,
                f'modifier:global_{crop}_output_modifier': .5,
            })
            self.assertAlmostEqual(vm.value('eu5ab_windmill_output_factor'), 2.4)
            self.assertAlmostEqual(vm.value('eu5ab_windmill_added_revenue'), 10)
            self.assertAlmostEqual(vm.value('eu5ab_engine_adjusted_profit'), 7)
            self.assertAlmostEqual(food_building_profit(BuildingCandidate('windmill', (), 40, 1, potential_profit=-3), ctx), 7)
        for value in (None, 0, -1, float('nan')):
            self.assertIsNone(windmill_incremental_revenue(100, value))
        for factor in (0, -1):
            ctx = self.context(raw_material='wheat', rgo_monthly_revenue=100, rgo_output_factor=factor)
            vm = FoodVM(self.rules, ctx, 'windmill')
            self.assertEqual(vm.value('eu5ab_windmill_added_revenue'), 0)
            self.assertFalse(vm.gate('eu5ab_candidate_has_windmill_return'))

    def test_windmill_losses_missing_values_and_roi_modes(self):
        for revenue, cost, mode, direct in product((None, 0, 10, 11, 100), (40, 10000), (1, 2, 3, 4), (-1, 1)):
            ctx = self.context(raw_material='wheat', raw_material_output=10,
                               rgo_monthly_revenue=revenue, rgo_output_factor=1)
            ctx = replace(ctx, market=MarketState(food_stockpile_ratio=.1, goods={'wheat': GoodsMarketState(100, 100, 1)}),
                          country=replace(ctx.country, economic_metric=mode))
            vm = FoodVM(self.rules, ctx, 'windmill', profit=direct, cost=cost)
            expected = (revenue is not None and revenue > 0 and revenue * .1 + direct > 0
                        and (mode < 3 or revenue * .1 + direct >= cost * .05 / 12))
            self.assertEqual(vm.gate('eu5ab_candidate_has_windmill_return'), expected)
            candidate = BuildingCandidate('windmill', (), cost, 1, potential_profit=direct)
            reason = first_blocking_reason(policy(allowed_buildings=['windmill']), candidate, 20000, 30000,
                                          context=ctx, rules=self.rules)
            self.assertEqual(reason, PauseReason.NONE if expected else PauseReason.NO_WINDMILL_NEED)

    def test_native_food_price_preserves_capital_market_precision_and_valid_zero(self):
        for price in (None, 0, .00001, .12345, 1.23456):
            with self.subTest(price=price):
                vm = FoodVM(self.rules, self.context(province_food_price=price))
                self.assertEqual(vm.gate('eu5ab_location_food_price_known'), price is not None)
                self.assertEqual(vm.value('eu5ab_location_food_price'), price or 0)
                # The old GUI scope is deliberately different: it is no longer
                # a consumer input for the normal granary valuation path.
                vm.native_values['scope:eu5ab_engine_food_price'] = 999
                self.assertEqual(vm.value('eu5ab_location_food_price'), price or 0)

    def test_both_bridges_and_actual_profit_selection_use_adjusted_value_once(self):
        capture = next(line for line in self.generated.engine_queue_gui.splitlines()
                       if "eu5ab_gui_capture_candidate_quote').Execute" in line)
        for expr in ('MakeScopeValue(Location.GetRawMaterialsPrice)',
                     'MakeScopeValue(Location.GetProvince.GetMonthlyFood)'):
            self.assertIn(expr, capture)
        # Current batching captures native cost in this same initial quote;
        # the retired second cost callback must not issue another read.
        self.assertIn("AddScope('eu5ab_engine_cost'", capture)
        self.assertNotIn("eu5ab_gui_batch_capture_cost').Execute", self.generated.engine_queue_gui)
        self.assertEqual(self.generated.engine_queue_gui.count(
            'MakeScopeValue(Location.GetProvince.GetCapital.GetMarket.GetFoodPrice)'), 1)
        quote_gui = automation._blocks_for_token(self.generated.scripted_guis,
                        '\neu5ab_gui_capture_candidate_quote = ')[0]
        for name in ('eu5ab_engine_rgo_revenue', 'eu5ab_engine_province_food_natural',
                     'eu5ab_engine_province_food_balance'):
            self.assertIn(name, quote_gui)
            self.assertIn(name, capture)
        queue = QueueVM(self.generated.effects, self.generated.scripted_guis)
        # This test exercises profit selection, with an already captured open
        # capacity snapshot; recipe-catalog capture has its own runtime tests.
        queue.vars['location'].update(eu5ab_capacity_ready=1, eu5ab_capacity_open=1,
                                      eu5ab_capacity_factor=1)
        queue.native['scope:eu5ab_candidate_building.eu5ab_current_candidate_configured_priority'] = 1
        ctx = self.context(raw_material='wheat', rgo_monthly_revenue=240, rgo_output_factor=2.4)
        vm = FoodVM(self.rules, ctx, 'windmill', profit=-3)
        for building, direct, total in [('building_type:granary', 6, 6),
                                        ('building_type:village_granary', 6, 6),
                                        ('building_type:windmill', -3, vm.value('eu5ab_engine_adjusted_profit'))]:
            queue.scopes.update(eu5ab_engine_profit=direct, eu5ab_candidate_building=building)
            queue.native['scope:eu5ab_candidate_location.eu5ab_engine_adjusted_profit'] = total
            queue.run('eu5ab_record_actual_profit_candidate')
        self.assertEqual(queue.lists['location']['eu5ab_q_profit_best_types'], ['building_type:windmill'])
        self.assertAlmostEqual(queue.vars['location']['eu5ab_q_profit_best_actual'], 7)


if __name__ == '__main__':
    unittest.main()
