"""Execute industry scope receipts and direct-output scoring from generated script."""
import re
import tempfile
from pathlib import Path
import unittest

from src.eu5autobuild import industry_promotion as industry
from src.eu5autobuild.production import BuildingProduction
from tests._governor_script_vm import GovernorScriptVM, parse
from tests.test_town_rights_runtime import RightsVM, method
from tests.test_engine import RULES


class IndustryScoreVM(RightsVM):
    def __init__(self, model, industries):
        super().__init__({'example': model}, RULES)
        self.building = 'example'
        self.industries = {'industry_type:textiles'}
        self.current = True
        self.definitions.update({k: v for k, _, v in parse(industry.render_values({'example': model}, industries))})

    def predicate(self, key, op, value):
        if key == 'eu5ab_industry_snapshot_current':
            return self.current
        if key == 'has_variable_list' and value == 'eu5ab_industry_types':
            return bool(self.industries)
        if key == 'is_target_in_variable_list':
            fields = {k: v for k, _, v in value}
            if fields['name'] == 'eu5ab_industry_types':
                return fields['target'] in self.industries
        return super().predicate(key, op, value)

    def score(self):
        return self.value('eu5ab_industry_candidate_score')


class SnapshotVM(GovernorScriptVM):
    def __init__(self):
        super().__init__({'location': None}, {}, {}, {}, (), (), None)
        effects, triggers, values, guis = industry.render()
        self.definitions = {k: v for k, _, v in parse(effects)}
        self.triggers = {k: v for k, _, v in parse(triggers)}
        self.values = {k: v for k, _, v in parse(values)}
        self.guis = {k: dict((a, c) for a, _, c in v)['effect']
                     for k, _, v in parse(re.sub(r'saved_scopes = \{[^}]*\}', '', guis))}
        self.vars[self.ROOT].update(eu5ab_scan_active=1, eu5ab_scan_month=1, eu5ab_scan_year=1497)
        self.vars['location'].update(eu5ab_capacity_request=7, eu5ab_capacity_requested=1,
                                    eu5ab_capacity_worker_country=self.ROOT, eu5ab_capacity_month=1, eu5ab_capacity_year=1497)
        self.lists[self.ROOT]['eu5ab_worker_pending_locations'] = ['location']
        self.scopes.update(eu5ab_industry_count=2, eu5ab_engine_country=self.ROOT, eu5ab_capacity_ticket=7)

    def value(self, word, stack):
        if isinstance(word, str) and word in self.values:
            return self.value(self.values[word], stack)
        if word == 'area':
            return 'area:prussia'
        return super().value(word, stack)

    def test(self, key, op, value, stack):
        if key in self.triggers:
            return self.condition(self.triggers[key], stack)
        if key == 'eu5ab_scan_month_current':
            return True
        if key == 'owner' and isinstance(value, list):
            return self.condition(value, stack + [self.owners[stack[-1]]])
        if key == 'exists':
            return self.value(value, stack) is not None
        return super().test(key, op, value, stack)

    def run(self, name):
        self.execute(self.definitions[name], ['location'])

    def begin(self, count=2):
        self.scopes['eu5ab_industry_count'] = count
        self.execute(self.guis['eu5ab_gui_begin_industry_snapshot'], [self.ROOT])

    def capture(self, promotion, area='area:prussia', owner=None, kind='textiles', ticket=7):
        self.scopes.update(eu5ab_industry_promotion=promotion, eu5ab_industry_area=area,
                           eu5ab_industry_country=owner or self.ROOT,
                           eu5ab_industry_type='industry_type:' + kind, eu5ab_capacity_ticket=ticket)
        self.execute(self.guis['eu5ab_gui_capture_industry_promotion'], ['location'])


class IndustryTests(unittest.TestCase):
    def test_direct_outputs_weighted_union_cap_and_independent_rights(self):
        vm = IndustryScoreVM(BuildingProduction('example', ((method({'cloth': 1, 'tools': 9}),),)),
                             {'textiles': ['cloth'], 'overlap': ['cloth'], 'crafts': ['tools']})
        vm.base_prices = {'cloth': 9, 'tools': 1}
        vm.industries.add('industry_type:overlap')
        self.assertEqual(vm.score(), 250)
        vm.town_rights.add('royal_tooling_rights')
        self.assertEqual(vm.score(), 250)
        self.assertEqual(vm.value('eu5ab_town_rights_candidate_score'), 250)
        vm.industries.add('industry_type:crafts')
        self.assertEqual(vm.score(), 500)
        vm.town_rights.add('royal_textile_rights')
        self.assertEqual(vm.value('eu5ab_town_rights_candidate_score'), 500)
        vm.current = False
        self.assertEqual(vm.score(), 0)

    def test_inputs_upstream_goods_and_unselected_methods_do_not_match(self):
        for outputs in ({'wool': 1}, {'dyes': 1}, {}, {'cloth': 0}):
            vm = IndustryScoreVM(BuildingProduction('example', ((method(outputs, {'cloth': 1}),),)), {'textiles': ['cloth']})
            self.assertEqual(vm.score(), 0)
        model = BuildingProduction('example', ((method({'cloth': 1}, unlock_advances=('locked',)), method({'tools': 1})),))
        vm = IndustryScoreVM(model, {'textiles': ['cloth']})
        self.assertEqual(vm.score(), 0)
        vm.advances.add('locked')
        self.assertEqual(vm.score(), 500)
        vm.base_prices['cloth'] = 0
        self.assertEqual(vm.score(), 0)

    def test_receipts_filter_area_owner_deduplicate_and_reset(self):
        vm = SnapshotVM()
        vm.begin()
        vm.capture('first', area='area:pomerania')
        vm.capture('second')
        vm.capture('second')
        vm.run('eu5ab_finish_industry_snapshot')
        self.assertEqual(vm.lists['location']['eu5ab_industry_types'], ['industry_type:textiles'])
        self.assertEqual(vm.vars['location']['eu5ab_industry_sampled'], 2)
        self.assertTrue(vm.condition(vm.triggers['eu5ab_industry_snapshot_current'], ['location']))
        vm.begin(1)
        vm.capture('foreign', owner='other')
        vm.run('eu5ab_finish_industry_snapshot')
        self.assertEqual(vm.lists['location']['eu5ab_industry_types'], [])
        vm.begin(0)
        vm.vars['location'].pop('eu5ab_industry_expected', None)  # engine drops zero
        vm.run('eu5ab_finish_industry_snapshot')
        self.assertIn('eu5ab_industry_ready', vm.vars['location'])

    def test_missing_rows_stale_ticket_and_changed_count_never_publish_old_support(self):
        vm = SnapshotVM()
        vm.begin()
        vm.capture('one', ticket=6)
        self.assertEqual(vm.lists['location']['eu5ab_industry_seen'], [])
        vm.capture('one')
        vm.run('eu5ab_finish_industry_snapshot')
        self.assertNotIn('eu5ab_industry_ready', vm.vars['location'])
        self.assertEqual(vm.lists['location']['eu5ab_industry_types'], [])
        vm.begin(1)
        vm.capture('one')
        vm.scopes['eu5ab_industry_count'] = 0  # native revocation before publication
        vm.run('eu5ab_finish_industry_snapshot')
        self.assertNotIn('eu5ab_industry_ready', vm.vars['location'])
        vm.begin(1)
        vm.capture('one')
        vm.run('eu5ab_finish_industry_snapshot')
        vm.owners['location'] = 'other'
        self.assertFalse(vm.condition(vm.triggers['eu5ab_industry_snapshot_current'], ['location']))

    def test_extract_repeated_goods_and_reject_unsupported_structure(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / 'game/in_game/common/industry_types/types.txt'
            path.parent.mkdir(parents=True)
            path.write_text('textiles = { goods = { cloth fine_cloth cloth } }', encoding='utf-8')
            self.assertEqual(industry.extract_industries(root), {'textiles': ['cloth', 'fine_cloth']})
            path.write_text('textiles = { goods = { cloth = 2 } }', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'Unsupported'):
                industry.extract_industries(root)
