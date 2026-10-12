"""Execute the generated native-count boundary and its pending consumers.

Only engine inputs are injected: civil count, native RGO count, level and time.
Queue identity and scheduling remain engine acceptance work.
"""

from decimal import Decimal as D
import re
import unittest

from tests import _generated
from tests._governor_script_vm import parse
from tests.test_rgo_cost_runtime import RgoVM
from tests.test_rgo_decision_runtime import RgoDecisionVM
from src.eu5autobuild.gui_integer import nonnegative_int32


class NativeQueueVM(RgoDecisionVM):
    def value(self, x, stack):
        if x == 'eu5ab_rgos_under_construction':
            return RgoVM.value(self, x, stack)
        if x == 'num_civil_constructions':
            row = self.locations[stack[-1]]
            return row['queue'] + row.get('other_projects', D(0))
        return super().value(x, stack)

    def capture(self, count, location='a'):
        self.scopes['eu5ab_engine_rgo_count'] = D(count)
        self.execute(self.definitions['eu5ab_capture_rgo_queue'], [location])


class RgoQueueTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture = _generated.generated_fixture()
        cls.effects = {k: v for k, _, v in parse(fixture.effects)}
        cls.triggers = {k: v for k, _, v in parse(fixture.triggers)}
        cls.values = {k: v for k, _, v in parse(fixture.values)}
        source = '\n'.join(_generated._blocks_for_token(fixture.scripted_guis, '\n' + name + ' = ')[0]
            for name in ('eu5ab_gui_capture_pending_rgo_queue', 'eu5ab_gui_capture_rgo_timing'))
        source = re.sub(r'saved_scopes = \{[^}]*\}', '', source)
        cls.guis = {k: dict((a, c) for a, _, c in v) for k, _, v in parse(source)}

    def setUp(self):
        self.vm = NativeQueueVM(self.effects, self.triggers, self.values)

    def test_native_time_waits_for_completion_then_staffing_and_ignores_duplicate(self):
        vm = self.vm
        vm.attempt()
        vm.scopes.update(eu5ab_engine_country='country', eu5ab_engine_rgo_count=D(1), eu5ab_engine_rgo_days=D(180))
        callback = self.guis['eu5ab_gui_capture_rgo_timing']['effect']
        vm.execute(callback, ['a'])
        self.assertEqual(vm.vars['a']['eu5ab_rgo_pending_build_days'], 180)
        # Native days parsing requires a named script value. Resolve it in the
        # callback's location scope; the VM itself does not implement timers.
        from tests.test_script_engine_contracts import walk
        timer = next(dict((k, v) for k, _, v in value)
                     for key, _, value in walk(callback)
                     if key == 'set_variable' and isinstance(value, list)
                     and dict((k, v) for k, _, v in value).get('name') == 'eu5ab_rgo_pending_wait_construction')
        self.assertIn(timer['days'], self.values)
        self.assertEqual(vm.value(timer['days'], ['a']), 180)
        self.assertIn('eu5ab_rgo_pending_wait_construction', vm.vars['a'])
        self.assertEqual(vm.lists['country']['eu5ab_rgo_timing_requests'], [])
        vm.scopes['eu5ab_engine_rgo_days'] = D(999)
        vm.execute(callback, ['a'])
        self.assertEqual(vm.vars['a']['eu5ab_rgo_pending_build_days'], 180)
        # Simulate the engine expiring its days-based variable. Expiry alone
        # cannot release queued work, even if pre-existing workers are full.
        vm.vars['a'].pop('eu5ab_rgo_pending_wait_construction')
        vm.refresh()
        self.assertEqual(vm.vars['a']['eu5ab_rgo_pending_levels'], 1)
        vm.locations['a'].update(queue=D(0), levels=D(5), workers=D('4.9'))
        vm.refresh()
        self.assertEqual(vm.vars['a']['eu5ab_rgo_pending_levels'], 1)
        vm.locations['a']['workers'] = D(5)
        vm.refresh()
        self.assertNotIn('eu5ab_rgo_pending_levels', vm.vars['a'])

    def test_duplicate_callback_and_empty_report_never_compare_missing_variables(self):
        vm = self.vm
        vm.attempt()
        vm.day += 1
        vm.refresh()
        vm.scopes.update(eu5ab_engine_country='country', eu5ab_engine_rgo_count=D(1),
                         eu5ab_rgo_queue_ticket=vm.vars['a']['eu5ab_rgo_queue_sequence'])
        test = vm.test

        def strict_test(k, op, v, stack):
            for operand in (k, v):
                if k != 'exists' and isinstance(operand, str) and operand.startswith('var:'):
                    self.assertIn(operand[4:], vm.vars[stack[-1]], 'Undefined comparison: ' + operand)
            return test(k, op, v, stack)

        vm.test = strict_test
        callback = self.guis['eu5ab_gui_capture_pending_rgo_queue']['effect']
        vm.execute(callback, ['a'])
        vm.execute(callback, ['a'])
        vm.execute(vm.definitions['eu5ab_report_rgo_confirmed'], ['a'])
        self.assertEqual(vm.number('eu5ab_rgos_under_construction'), 1)

    def test_roads_upgrades_and_estates_use_exact_count_and_worker_reservation(self):
        vm = self.vm
        # road; building + road; road + estate RGO; estate RGO; upgrade.
        for civil, rgos in ((1, 0), (2, 0), (2, 1), (1, 1), (1, 0)):
            with self.subTest(civil=civil, rgos=rgos):
                vm.locations['a'].update(queue=D(rgos), other_projects=D(civil - rgos))
                vm.capture(rgos)
                if rgos == 0:
                    vm.vars['a'].pop('eu5ab_rgo_queue_count', None)
                self.assertEqual(vm.number('eu5ab_rgos_under_construction'), rgos)
                self.assertEqual(vm.number('eu5ab_rgo_queued_jobs'),
                                 rgos * vm.number('eu5ab_rgo_jobs_per_expansion'))

    def test_missing_stale_and_invalid_readings_do_not_become_zero(self):
        vm = self.vm
        vm.locations['a'].update(queue=D(1), other_projects=D(1))
        self.assertEqual(vm.number('eu5ab_rgos_under_construction'), -1)
        vm.capture(1)
        vm.day += 1
        self.assertEqual(vm.number('eu5ab_rgos_under_construction'), -1)
        vm.capture(1)
        vm.locations['a']['other_projects'] += 1
        self.assertEqual(vm.number('eu5ab_rgos_under_construction'), -1)
        vm.capture(1)
        vm.owners['a'] = 'foreign'
        self.assertEqual(vm.number('eu5ab_rgos_under_construction'), -1)
        vm.capture(-1)
        self.assertEqual(vm.number('eu5ab_rgos_under_construction'), -1)
        self.assertEqual(vm.number('eu5ab_rgo_queued_jobs'), 3 * vm.number('eu5ab_rgo_jobs_per_expansion'))
        vm.capture(4)  # More RGO projects than all civil projects is invalid.
        self.assertEqual(vm.number('eu5ab_rgos_under_construction'), -1)
        vm.locations['a'].update(queue=D(0), other_projects=D(0))
        self.assertEqual(vm.number('eu5ab_rgos_under_construction'), 0)

    def test_cancelled_rgo_releases_pending_even_when_a_road_remains(self):
        vm = self.vm
        vm.attempt()
        self.assertEqual(vm.number('eu5ab_rgos_under_construction'), 1)
        self.assertEqual(vm.vars['a']['eu5ab_rgo_pending_levels'], 1)
        vm.day += 1
        vm.locations['a'].update(queue=D(0), other_projects=D(1))
        vm.refresh()
        self.assertEqual(vm.vars['a']['eu5ab_rgo_pending_levels'], 1)
        self.assertEqual(vm.vars['a']['eu5ab_rgo_pending_unknown'], 1)
        self.assertEqual(vm.lists['country']['eu5ab_rgo_queue_requests'], ['a'])
        ticket = vm.vars['a']['eu5ab_rgo_queue_sequence']
        vm.scopes.update(eu5ab_engine_country='country', eu5ab_engine_rgo_count=D(0), eu5ab_rgo_queue_ticket=ticket - 1)
        callback = self.guis['eu5ab_gui_capture_pending_rgo_queue']['effect']
        vm.execute(callback, ['a'])
        self.assertEqual(vm.vars['a']['eu5ab_rgo_pending_levels'], 1)
        vm.scopes['eu5ab_rgo_queue_ticket'] = ticket
        vm.execute(callback, ['a'])
        self.assertNotIn('eu5ab_rgo_pending_levels', vm.vars['a'])
        self.assertEqual(vm.number('eu5ab_rgos_under_construction'), 0)
        self.assertEqual(vm.lists['country']['eu5ab_rgo_queue_requests'], [])
        self.assertEqual(vm.number('eu5ab_rgo_market_pending_unknown', 'b'), 0)

    def test_failed_receipt_preserves_pending_without_unbounded_retry(self):
        vm = self.vm
        vm.attempt()
        vm.day += 1
        vm.refresh()
        vm.scopes.update(eu5ab_engine_country='country', eu5ab_engine_rgo_count=D(-1),
                         eu5ab_rgo_queue_ticket=vm.vars['a']['eu5ab_rgo_queue_sequence'])
        vm.execute(self.guis['eu5ab_gui_capture_pending_rgo_queue']['effect'], ['a'])
        self.assertEqual(vm.vars['a']['eu5ab_rgo_pending_levels'], 1)
        self.assertEqual(vm.lists['country']['eu5ab_rgo_queue_requests'], [])
        vm.refresh()
        self.assertEqual(vm.lists['country']['eu5ab_rgo_queue_requests'], [])
        vm.day += 1
        vm.refresh()
        self.assertEqual(vm.lists['country']['eu5ab_rgo_queue_requests'], ['a'])

    def test_integer_transport_preserves_boundaries_and_rejects_negative(self):
        # Evaluate generated GUI arithmetic using the documented integer and
        # fixed arithmetic operators, independently of the script count cache.
        operators = dict(Select_CFixedPoint=lambda c, a, b: a if c else b,
                         EqualTo_int32=lambda a, b: a == b,
                         LessThan_int32=lambda a, b: a < b,
                         Modulo_int32=lambda a, b: a % b,
                         Divide_int32=lambda a, b: int(a / b),
                         Add_CFixedPoint=lambda a, b: a + b)
        for n in (-1, 0, 1, 17, 65535, 2147483647):
            expression = nonnegative_int32(str(n))
            expression = re.sub(r"'\((?:int32|CFixedPoint)\)(-?\d+)'", r'\1', expression)
            self.assertEqual(eval(expression, {'__builtins__': {}}, operators), max(-1, n))
