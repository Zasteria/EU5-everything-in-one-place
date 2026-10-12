"""Execute generated backfill, ordinary rejection effects and phase routing.

Native candidate pools, scores and economic responses are injected. These tests
are control-flow regression evidence, not native ordering or game benchmarks.
"""
from copy import deepcopy
import re
import unittest

from src.eu5autobuild import candidate_backfill as backfill
from src.eu5autobuild import building_capacity, manual_decisions, quote_cache
from tests._governor_script_vm import GovernorScriptVM, parse
from tests._automation_runtime import country_counter_initializers
from tests import _generated as automation
from tests.test_queue_recovery_runtime import QueueVM


POLICY = "eu5ab_try_construct_current_policy"
ROUTER = "eu5ab_try_construct_policy_candidate"
WORKER = "eu5ab_run_location_worker"
MERGE = "eu5ab_merge_location_worker_results"


class BackfillVM(GovernorScriptVM):
    def __init__(self, definitions, *, mode=2, n=10, enabled=True):
        self.definitions = definitions.copy()
        self.definitions.update({k: v for k, _, v in parse(quote_cache.render_effects())})
        from src.eu5autobuild.worker_screening import render_effects
        self.definitions.update({k: v for k, _, v in parse(render_effects())})
        self.local, self.scopes = {}, {}
        self.operations = 0
        self.owners = {"location": self.ROOT}
        self.vars = {self.ROOT: {
            "eu5ab_scan_active": 1,
            "eu5ab_global_candidate_ranking_mode": mode,
            "eu5ab_global_candidates_per_location": n,
            "eu5ab_global_actual_profit_candidates_per_location": n,
            "eu5ab_candidate_priority_upgrade": 1,
            "eu5ab_candidate_priority_expand": 2,
            "eu5ab_candidate_priority_new": 4,
        }, "location": {"eu5ab_policy_id": 1}}
        self.lists = {self.ROOT: {"eu5ab_worker_pending_locations": ["location"]}, "location": {}}
        self.maps = {self.ROOT: {}, "location": {}}
        self.pools = {kind: [] for kind in backfill.CLASSES}
        self.upstream = {kind: [] for kind in backfill.CLASSES}
        self.native, self.checks, self.sorts, self.stage_calls = {}, [], [], []
        self.score_calls = []
        self.upstream_calls = 0
        self.stage_rejected = set()
        # These scenarios start at worker entry, after a known valid GUI read.
        self.capacity_factor = 1
        self.auto_inputs = True
        GovernorScriptVM.execute(self, self.definitions["test_country_counter_initializers"], [self.ROOT])
        if enabled:
            self.vars[self.ROOT]["eu5ab_scan_backfill_enabled"] = 1
            self.vars["location"]["eu5ab_backfill_dispatch_country"] = self.ROOT

    def add_pool(self, kind, count, *, inputs=False, output=True, score_ties=False):
        for i in range(count):
            name = f"{kind}_{i + 1}"
            self.pools[kind].append(name)
            self.native[name] = dict(kind=kind, inputs=inputs, output=output,
                                     score=1 if score_ties else count - i, food=False)
            self.vars[name], self.lists[name] = {}, {}
        return self.pools[kind]

    def target(self, word, stack):
        if word.endswith(".owner"):
            return self.owners.get(self.target(word[:-6], stack))
        return super().target(word, stack)

    def value(self, x, stack):
        if isinstance(x, str):
            if x.startswith('eu5ab_manual_') and x in self.definitions:
                return self.value(self.definitions[x], stack)
            if '.' in x and x.rsplit('.', 1)[1].startswith('eu5ab_manual_'):
                scope, name = x.rsplit('.', 1)
                return self.value(name, stack + [self.target(scope, stack)])
            if x.startswith("flag:"):
                return x
            if x == "eu5ab_current_candidate_score":
                self.score_calls.append((self.scopes["eu5ab_candidate_location"], stack[-1]))
                return self.native[stack[-1]]["score"]
            if x == backfill.CACHED_SCORE:
                return self.value(self.definitions[x], stack)
            for name in ("eu5ab_current_candidate_score", backfill.CACHED_SCORE):
                if x.endswith("." + name):
                    return self.value(name, stack + [self.target(x[:-(len(name) + 1)], stack)])
            if x in ("eu5ab_uncached_preset_origin", "num_civil_constructions"):
                return 0
            if x == "eu5ab_capacity_location_order":
                score = self.vars[stack[-1]].get("eu5ab_cached_location_need_score", 0)
                building = self.scopes["eu5ab_candidate_building"]
                factor = 1 if self.native[building]["kind"] == "upgrade" else self.capacity_factor
                return building_capacity.discount(score, factor) or 0
            if x.startswith("eu5ab_capacity_phase_") and x.endswith("_order_value"):
                return self.vars[stack[-1]].get(x.removesuffix("_value"), 0)
        return super().value(x, stack)

    def test(self, k, op, v, stack):
        data = dict((a, c) for a, _, c in v) if isinstance(v, list) else {}
        if k == 'eu5ab_manual_month_current':
            return self.condition(self.definitions[k], stack) == (v == 'yes')
        if k == 'eu5ab_scan_month_current':
            # Calendar transitions have a dedicated VM; these worker fixtures
            # enter a current month only after both scan stamps are supplied.
            return all(name in self.vars[stack[-1]] for name in
                       ('eu5ab_scan_month', 'eu5ab_scan_year')) == (v == 'yes')
        if k == 'eu5ab_quote_context_current':
            return self.condition(parse(quote_cache.render_triggers())[0][2], stack) == (v == 'yes')
        if k == "is_key_in_variable_map":
            return self.value(data["target"], stack) in self.maps[stack[-1]].get(data["name"], {})
        if k == "eu5ab_candidate_pending_preliminary_allowed":
            return v == "yes"  # Commodity limits run in the dedicated ledger VM.
        if k == "eu5ab_candidate_pending_data_ready":
            return self.native[stack[-1]].get('pending_ready', True) == (v == 'yes')
        if k == "market":
            return True  # Native market membership is injected.
        if k == "eu5ab_candidate_has_capacity":
            exempt = self.native[stack[-1]]["kind"] == "upgrade"
            return (exempt or self.capacity_factor > 0) == (v == "yes")
        if k == "eu5ab_rgo_capacity_available":
            return v == "no"  # Keep RGO outside the backfill scenarios.
        if k == "owner" and isinstance(v, list):
            owner = self.owners.get(stack[-1])
            return owner is not None and self.condition(v, stack + [owner])
        if k == "has_variable_list":
            return bool(self.lists[stack[-1]].get(v))
        if k == "is_target_in_variable_list":
            target = self.value(data["target"], stack)
            if target in self.stage_rejected and data["name"].startswith("eu5ab_worker_phase_"):
                return True  # Already staged elsewhere; backfill must continue.
            return target in self.lists[stack[-1]].get(data["name"], [])
        if k == "exists":
            return self.target(v, stack) is not None
        if k in ("eu5ab_inputs_available", "eu5ab_output_not_oversupplied"):
            building = self.scopes["eu5ab_candidate_building"]
            if stack[-1] != building:
                raise AssertionError((k, stack, building))
            field = "inputs" if k == "eu5ab_inputs_available" else "output"
            self.checks.append((building, field))
            return self.native[building][field] == (v == "yes")
        if k == "eu5ab_engine_candidate_is_food_emergency":
            if stack[-1] != self.scopes["eu5ab_candidate_location"]:
                raise AssertionError(stack)
            return self.native[self.scopes["eu5ab_candidate_building"]]["food"] == (v == "yes")
        if k in (
            "eu5ab_candidate_is_upgrade",
            "eu5ab_candidate_has_existing_building",
            "eu5ab_candidate_lacks_existing_building",
        ):
            kind = self.native[self.scopes["eu5ab_candidate_building"]]["kind"]
            expected = {
                "eu5ab_candidate_is_upgrade": "upgrade",
                "eu5ab_candidate_has_existing_building": "expansion",
                "eu5ab_candidate_lacks_existing_building": "new",
            }[k]
            return (kind == expected) == (v == "yes")
        if k.startswith("eu5ab_engine_candidate_feature_rank_"):
            building = self.scopes["eu5ab_candidate_building"]
            if building in self.stage_rejected:
                return False
            kind = self.native[building]["kind"]
            setting = "expand" if kind == "expansion" else kind
            return self.vars[self.ROOT]["eu5ab_candidate_priority_" + setting] == int(k[-1])
        if k == "eu5ab_current_policy_auto_builds_input_sources":
            return self.auto_inputs == (v == "yes")
        return super().test(k, op, v, stack)

    def execute(self, entries, stack):
        index = 0
        while index < len(entries):
            k, _, v = entries[index]
            end = index + 1
            if k == "if":
                while end < len(entries) and entries[end][0] in ("else_if", "else"):
                    end += 1
            data = dict((a, c) for a, _, c in v) if isinstance(v, list) else {}
            if k == "owner":
                self.execute(v, stack + [self.owners[stack[-1]]])
            elif k == "switch":
                selected = self.value(data["trigger"], stack)
                self.execute(data.get(selected, []), stack)
            elif k == "clamp_variable":
                variables = self.vars[stack[-1]]
                variables[data["name"]] = min(float(data["max"]), max(float(data["min"]), variables.get(data["name"], 0)))
            elif k in ("eu5ab_collect_current_candidate_pools", "eu5ab_collect_current_input_candidate_pools"):
                upstream = "_input_" in k
                for kind, candidates in (self.upstream if upstream else self.pools).items():
                    prefix = "input_" if upstream else ""
                    self.lists[stack[-1]][f"eu5ab_current_{prefix}{kind}_candidate_pool"] = candidates.copy()
            elif k.startswith('eu5ab_prepare_worker_screen_'):
                pass  # Native screening facts are injected; memoization has its own VM.
            elif k in ("eu5ab_clear_scan_promotion_cache", "eu5ab_cache_candidate_promotion",
                       "eu5ab_prepare_recipe_score_snapshot", "eu5ab_prepare_candidate_score_snapshot", "eu5ab_clear_recipe_score_snapshot"):
                # These tests inject complete scores/eligibility. Recipe snapshot
                # arithmetic and cleanup are executed in test_recipe_snapshot_runtime.
                pass
            else:
                if k == "ordered_in_list":
                    self.sorts.append((data["variable"], self.value(data["max"], stack)))
                if k == "eu5ab_try_construct_current_input_source":
                    self.upstream_calls += 1
                if k == "eu5ab_stage_engine_candidate":
                    if stack[-1] != self.scopes["eu5ab_candidate_location"]:
                        raise AssertionError("Candidate staged outside its location")
                    self.stage_calls.append(self.scopes["eu5ab_candidate_building"])
                super().execute(entries[index:end], stack)
            index = end

    def run(self, name=WORKER, root="location"):
        self.execute(self.definitions[name], [root])

    def staged(self):
        return [(phase, building) for phase in range(1, 17)
                for building in self.lists["location"].get(f"eu5ab_worker_phase_{phase}_types", [])]


class CandidateBackfillRuntimeTests(unittest.TestCase):
    def test_reducer_requests_scan_quotes_after_worker_staging(self):
        vm = BackfillVM(self.definitions)
        vm.vars[vm.ROOT].update(eu5ab_scan_month=7, eu5ab_scan_year=1436)
        vm.add_pool('new', 2, inputs=True)
        vm.run()
        self.assertFalse(vm.lists[vm.ROOT].get('eu5ab_quote_pending_locations'))
        vm.run(MERGE, vm.ROOT)
        self.assertEqual(vm.lists[vm.ROOT]['eu5ab_quote_pending_locations'], ['location'])
        self.assertEqual(vm.lists['location']['eu5ab_quote_requests'], ['new_1', 'new_2'])
        ticket = vm.vars['location']['eu5ab_quote_ticket']
        vm.run(MERGE, vm.ROOT)
        self.assertEqual(vm.vars['location']['eu5ab_quote_ticket'], ticket)

    @classmethod
    def setUpClass(cls):
        cls.effects = automation.generated_fixture().effects
        names = [POLICY, ROUTER, "eu5ab_try_construct_current_input_source", WORKER, MERGE,
                 "eu5ab_clear_candidate_collection_cache",
                 "eu5ab_record_scan_candidate_location",
                 "eu5ab_hydrate_final_building_diagnostics",
                 "eu5ab_clear_location_worker_state", "eu5ab_try_construct_saved_building_type",
                 "eu5ab_stage_engine_candidate"]
        names += [f"eu5ab_try_construct_{policy_id}" for policy_id in automation.generated_fixture().policy_ids]
        names += [f"eu5ab_try_construct_template_slot_{slot}" for slot in range(1, 21)]
        names += [f"eu5ab_stage_current_{prefix}{kind}_candidates"
                  for prefix in ("", "input_") for kind in backfill.CLASSES]
        names += re.findall(r"^(eu5ab_\w*backfill\w*) = \{", cls.effects, re.M)
        cls.definitions = {}
        for name in dict.fromkeys(names):
            body = automation._blocks_for_token(cls.effects, "\n" + name + " = ")[0]
            cls.definitions[name] = parse(body)[0][2]
        cls.definitions[backfill.CACHED_SCORE] = parse(automation._blocks_for_token(
            automation.generated_fixture().values, "\n" + backfill.CACHED_SCORE + " = "
        )[0])[0][2]
        cls.definitions["test_country_counter_initializers"] = country_counter_initializers(cls.effects)
        cls.definitions.update({k: v for k, _, v in parse(manual_decisions.render_triggers())})
        cls.definitions.update({k: v for k, _, v in parse(automation.generated_fixture().values)
                                if k.startswith('eu5ab_manual_')})

    def vm(self, **kwargs):
        return BackfillVM(self.definitions, **kwargs)

    def test_unknown_candidates_are_retained_without_inflating_usable_reserve(self):
        vm = self.vm()
        candidates = vm.add_pool('new', 2, inputs=True)
        for name in candidates:
            vm.native[name]['pending_ready'] = False
        vm.run()
        self.assertEqual({building for _, building in vm.staged()}, set(candidates))
        self.assertTrue(vm.vars['location']['eu5ab_worker_data_wait'])
        vm.run(MERGE, vm.ROOT)
        self.assertEqual(vm.vars[vm.ROOT].get('eu5ab_scan_candidate_reserve', 0), 0)
        self.assertEqual(vm.lists['location']['eu5ab_q_phase_8_types'], candidates)
        self.assertEqual(len(vm.score_calls), 2)

    def test_resumed_worker_diagnostics_publish_missing_totals_and_add_once(self):
        from src.eu5autobuild.generator import WORKER_DIAGNOSTIC_COUNTERS
        # Native probe I: change_variable on an absent target raises Type: empty;
        # zero and nonzero targets are valid. A resumed worker needs no reset.
        for inherited in (None, 0, 1024):
            with self.subTest(inherited=inherited):
                vm = self.vm()
                vm.vars["location"]["eu5ab_worker_complete"] = True
                vm.vars[vm.ROOT]["eu5ab_global_budget_spent"] = 22610.733
                vm.vars[vm.ROOT]["eu5ab_scan_next_month_pending"] = True
                for index, counter in enumerate(WORKER_DIAGNOSTIC_COUNTERS):
                    vm.vars[vm.ROOT].pop(counter, None)
                    if inherited is not None:
                        vm.vars[vm.ROOT][counter] = inherited
                    vm.vars["location"]["eu5ab_worker_" + counter] = index
                vm.run(MERGE, vm.ROOT)
                expected = {counter: (inherited or 0) + index
                            for index, counter in enumerate(WORKER_DIAGNOSTIC_COUNTERS)}
                self.assertEqual({k: vm.vars[vm.ROOT][k] for k in expected}, expected)
                vm.run(MERGE, vm.ROOT)
                self.assertEqual({k: vm.vars[vm.ROOT][k] for k in expected}, expected)
                self.assertEqual(vm.vars[vm.ROOT]["eu5ab_global_budget_spent"], 22610.733)
                self.assertTrue(vm.vars[vm.ROOT]["eu5ab_scan_next_month_pending"])

    def test_missing_worker_counter_does_not_publish_a_fabricated_total(self):
        vm = self.vm()
        counter = "eu5ab_diag_legal_candidates"
        vm.vars[vm.ROOT].pop(counter, None)
        vm.vars["location"]["eu5ab_worker_complete"] = True
        vm.run(MERGE, vm.ROOT)
        self.assertNotIn(counter, vm.vars[vm.ROOT])

    def test_rgo_worker_diagnostics_replace_previous_building_identity(self):
        vm = self.vm()
        vm.vars[vm.ROOT].update(eu5ab_diag_top_1_kind=1,
                               eu5ab_diag_top_1_priority=100,
                               eu5ab_diag_top_1_building='previous_building')
        vm.vars['location'].update(eu5ab_worker_complete=1,
                                   eu5ab_worker_top_1_kind=2,
                                   eu5ab_worker_top_1_priority=1,
                                   eu5ab_worker_top_1_score=180)
        vm.run(MERGE, vm.ROOT)
        self.assertEqual(vm.vars[vm.ROOT]['eu5ab_diag_top_1_kind'], 2)
        self.assertEqual(vm.vars[vm.ROOT]['eu5ab_diag_top_1_score'], 180)
        self.assertNotIn('eu5ab_diag_top_1_building', vm.vars[vm.ROOT])

    def assert_scratch_clean(self, vm):
        self.assertFalse(any(k.startswith("eu5ab_backfill_") for k in vm.vars["location"]))
        self.assertNotIn("eu5ab_stage_candidate_priority", vm.vars["location"])
        self.assertNotIn("eu5ab_stage_priority_computed", vm.vars["location"])
        self.assertNotIn(backfill.SCORE_CACHE, vm.maps["location"])
        for pool in (*backfill.POOLS, "eu5ab_backfill_upstream_checked"):
            self.assertFalse(vm.lists["location"].get(pool))

    def uncached_definitions(self):
        """Restore only the old score path, keeping the same generated gates."""
        def rewrite(entries):
            result = []
            for key, op, value in entries:
                if key == "clear_variable_map" and value == backfill.SCORE_CACHE:
                    continue
                if key == "every_in_list" and backfill.SCORE_CACHE in str(value):
                    continue
                if isinstance(value, list):
                    value = rewrite(value)
                elif isinstance(value, str):
                    value = value.replace(backfill.CACHED_SCORE, "eu5ab_current_candidate_score")
                result.append((key, op, value))
            return result
        return {name: rewrite(body) for name, body in self.definitions.items()}

    def test_cached_scores_preserve_order_limits_food_diagnostics_and_backfill(self):
        for mode, n in ((1, 3), (2, 5)):
            for enabled in (False, True):
                for upstream in (False, True):
                    with self.subTest(mode=mode, enabled=enabled, upstream=upstream):
                        before = BackfillVM(self.uncached_definitions(), mode=mode, n=n, enabled=enabled)
                        after = self.vm(mode=mode, n=n, enabled=enabled)
                        for vm in (before, after):
                            # Equal, fractional, zero and negative scores must retain
                            # their exact order and food-layer diagnostic precedence.
                            for kind in backfill.CLASSES:
                                names = vm.add_pool(kind, 7, inputs=not upstream)
                                for index, score in enumerate((0, -0.25, 100.125, 100.125, -10, 33.2, 0)):
                                    vm.native[names[index]]["score"] = score
                                    vm.native[names[index]]["food"] = index in (1, 4, 5)
                                if upstream:
                                    vm.upstream[kind] = names.copy()
                            vm.run()
                        self.assertEqual((after.vars, after.lists), (before.vars, before.lists))
                        self.assertEqual((after.checks, after.stage_calls, after.sorts),
                                         (before.checks, before.stage_calls, before.sorts))
                        self.assertEqual(len(after.score_calls), 42 if upstream else 21)
                        self.assertGreater(len(before.score_calls), len(after.score_calls))
                        for building in after.native:
                            self.assertEqual(after.score_calls.count(("location", building)),
                                             2 if upstream else 1)
                        # Building scopes and the country never hold the snapshot.
                        self.assertTrue(all(not after.vars[name] for name in after.native))
                        self.assertFalse(any(backfill.SCORE_CACHE in maps for maps in after.maps.values()))
                        self.assert_scratch_clean(after)

    def test_score_cache_discards_stale_values_and_recomputes_on_next_run(self):
        vm = self.vm(enabled=False)
        names = vm.add_pool("new", 2, inputs=True)
        vm.maps["location"][backfill.SCORE_CACHE] = dict.fromkeys(names, 9999)
        vm.native[names[0]]["score"], vm.native[names[1]]["score"] = -2.5, 0
        vm.scopes['eu5ab_candidate_location'] = 'location'
        vm.run('eu5ab_clear_location_worker_state')
        self.assertNotIn(backfill.SCORE_CACHE, vm.maps['location'])
        self.assertEqual([vm.value(backfill.CACHED_SCORE, ['location', name])
                          for name in names], [-2.5, 0])
        vm.native[names[0]]["score"] = 1.125
        vm.run('eu5ab_clear_location_worker_state')
        self.assertEqual([vm.value(backfill.CACHED_SCORE, ['location', name])
                          for name in names], [1.125, 0])
        self.assertEqual(len(vm.score_calls), 4)
        self.assert_scratch_clean(vm)

    def test_empty_pool_and_worker_cleanup_remove_stale_score_map(self):
        vm = self.vm()
        vm.maps["location"][backfill.SCORE_CACHE] = {"old_building": 123}
        vm.run("eu5ab_stage_current_new_candidates")
        self.assertFalse(vm.score_calls)
        self.assertNotIn(backfill.SCORE_CACHE, vm.maps["location"])
        vm.maps["location"][backfill.SCORE_CACHE] = {"old_building": 123}
        vm.run("eu5ab_clear_location_worker_state")
        self.assertNotIn(backfill.SCORE_CACHE, vm.maps["location"])

    def test_interleaved_locations_keep_independent_score_snapshots(self):
        vm = self.vm(enabled=False)
        names = vm.add_pool("upgrade", 3, inputs=True)
        vm.vars["second"], vm.lists["second"] = {"eu5ab_policy_id": 1}, {}
        vm.owners["second"] = vm.ROOT
        vm.maps['location'][backfill.SCORE_CACHE] = dict(zip(names, (3, 2, 1)))
        vm.maps['second'] = {backfill.SCORE_CACHE: dict(zip(names, (-3, -2, -1)))}
        # Read shared building types alternately in each location's scope.
        for name, expected in zip(names, (3, 2, 1)):
            for location, score in (('location', expected), ('second', -expected)):
                vm.scopes['eu5ab_candidate_location'] = location
                self.assertEqual(vm.value(backfill.CACHED_SCORE, [location, name]), score)
        self.assertFalse(vm.score_calls)
        vm.run('eu5ab_clear_location_worker_state', root='second')
        self.assertEqual(vm.maps['location'][backfill.SCORE_CACHE], dict(zip(names, (3, 2, 1))))
        vm.run('eu5ab_clear_location_worker_state')
        self.assertFalse(any(backfill.SCORE_CACHE in maps for maps in vm.maps.values()))

    def test_stage_checks_food_once_and_stops_at_matching_rank(self):
        class CountingVM(BackfillVM):
            def __init__(self, definitions):
                super().__init__(definitions)
                self.stage_checks = []

            def test(self, k, op, v, stack):
                if k == "eu5ab_engine_candidate_is_food_emergency" or k.startswith(
                    "eu5ab_engine_candidate_feature_rank_"
                ):
                    self.stage_checks.append(k)
                return super().test(k, op, v, stack)

        for worker in (False, True):
            for kind, rank in (("upgrade", 1), ("expansion", 2), ("new", 4)):
                for food in (False, True):
                    with self.subTest(worker=worker, kind=kind, food=food):
                        vm = CountingVM(self.definitions)
                        building = vm.add_pool(kind, 1)[0]
                        vm.native[building]["food"] = food
                        vm.scopes["eu5ab_candidate_location"] = "location"
                        vm.scopes["eu5ab_candidate_building"] = building
                        priority_key = "expand" if kind == "expansion" else kind
                        vm.vars["location"]["eu5ab_stage_candidate_priority"] = (
                            vm.vars[vm.ROOT]["eu5ab_candidate_priority_" + priority_key]
                        )
                        if worker:
                            vm.vars["location"]["eu5ab_worker_active"] = 1
                            vm.vars["location"]["eu5ab_worker_staged"] = 0
                        vm.run("eu5ab_stage_engine_candidate")
                        phase = rank if food else rank + 4
                        list_name = (
                            f"eu5ab_worker_phase_{phase}_types" if worker
                            else f"eu5ab_q_phase_{phase}_types"
                        )
                        self.assertEqual(vm.lists["location"].get(list_name), [building])
                        self.assertEqual(
                            vm.stage_checks,
                            ["eu5ab_engine_candidate_is_food_emergency"],
                        )

    def test_standalone_stage_classifies_once_and_cleans_scratch(self):
        for kind, phase in (("upgrade", 5), ("expansion", 6), ("new", 8)):
            with self.subTest(kind=kind):
                vm = self.vm()
                building = vm.add_pool(kind, 1)[0]
                vm.scopes["eu5ab_candidate_location"] = "location"
                vm.scopes["eu5ab_candidate_building"] = building
                vm.run("eu5ab_stage_engine_candidate")
                self.assertEqual(
                    vm.lists["location"].get(f"eu5ab_q_phase_{phase}_types"),
                    [building],
                )
                self.assertNotIn("eu5ab_stage_candidate_priority", vm.vars["location"])
                self.assertNotIn("eu5ab_stage_priority_computed", vm.vars["location"])

    def test_workforce_diagnostic_queries_stop_after_first_match(self):
        collector = parse(automation._blocks_for_token(
            self.effects, "\neu5ab_collect_current_candidate_pools = "
        )[0])[0][2]

        def diagnostic_limit(entries):
            for key, _, value in entries:
                if not isinstance(value, list):
                    continue
                if key == "else_if":
                    limit = dict((name, child) for name, _, child in value)["limit"]
                    if "eu5ab_had_workforce_blocked_candidate" in str(limit):
                        return value
                nested = diagnostic_limit(value)
                if nested is not None:
                    return nested
            return None

        branch = diagnostic_limit(collector)
        self.assertIsNotNone(branch)
        limit = next(value for key, _, value in branch if key == 'limit')
        vm = self.vm()
        building = vm.add_pool("new", 1, inputs=True)[0]
        vm.scopes["eu5ab_candidate_location"] = "location"
        vm.scopes["eu5ab_candidate_building"] = building
        vm.vars[vm.ROOT]["eu5ab_global_pause_low_workforce"] = 1
        self.assertTrue(vm.condition(limit, [vm.ROOT, building]))
        vm.execute([entry for entry in branch if entry[0] != 'limit'], [vm.ROOT, building])
        self.assertEqual(vm.checks, [(building, "inputs"), (building, "output")])
        vm.vars["location"]["eu5ab_had_workforce_blocked_candidate"] = 1
        self.assertFalse(vm.condition(limit, [vm.ROOT, building]))
        self.assertEqual(vm.checks, [(building, "inputs"), (building, "output")])

    def test_disabled_backfill_and_normal_success_stay_within_shortlist(self):
        for enabled, success in ((False, False), (False, True), (True, True)):
            for mode, n in ((1, 3), (2, 10), (2, 30)):
                with self.subTest(enabled=enabled, success=success, mode=mode, n=n):
                    vm = self.vm(mode=mode, n=n, enabled=enabled)
                    vm.add_pool('new', n + 7)
                    winner = f'new_{n if success else n + 1}'
                    vm.native[winner]['inputs'] = True
                    vm.run()
                    self.assertEqual(vm.stage_calls, [winner] if success else [])
                    self.assertEqual([b for b, gate in vm.checks if gate == 'inputs'],
                                     [f'new_{rank}' for rank in range(1, n + 1)])
                    self.assertNotIn('eu5ab_worker_backfill_triggered', vm.vars['location'])
                    self.assert_scratch_clean(vm)

    def test_half_default_budget_rounded_up_independent_of_configured_n(self):
        for mode, budget in ((1, 2), (2, 5)):
            for n in (3, 10, 15, 30):
                with self.subTest(mode=mode, n=n):
                    vm = self.vm(mode=mode, n=n)
                    vm.add_pool("new", n + 20)
                    vm.run()
                    self.assertEqual(vm.vars["location"]["eu5ab_worker_backfill_checked"], budget)
                    self.assertEqual(vm.vars["location"]["eu5ab_worker_backfill_budget_exhausted"], 1)
                    self.assertEqual([cap for pool, cap in vm.sorts if "_input_" not in pool], [n + budget] * 3)
                    self.assert_scratch_clean(vm)

    def test_all_normal_candidates_are_compared_before_any_backfill(self):
        for mode, n in ((1, 3), (2, 10)):
            with self.subTest(mode=mode):
                vm = self.vm(mode=mode, n=n)
                expected = []
                for kind in backfill.CLASSES:
                    expected.extend(vm.add_pool(kind, n + 5, inputs=True)[:n])
                vm.run()
                self.assertEqual(vm.stage_calls, expected)
                self.assertEqual(len(vm.staged()), 3 * n)
                self.assertEqual([b for b, gate in vm.checks if gate == "inputs"], expected)
                self.assertEqual(vm.vars["location"]["eu5ab_worker_eu5ab_diag_legal_candidates"], 3 * n)
                self.assertEqual(vm.vars["location"]["eu5ab_worker_eu5ab_diag_fail_no_legal"], 0)
                self.assertNotIn("eu5ab_worker_backfill_triggered", vm.vars["location"])
                self.assert_scratch_clean(vm)

    def test_sixth_or_tenth_normal_candidate_prevents_earlier_pool_backfill(self):
        for rank in (6, 10):
            with self.subTest(rank=rank):
                vm = self.vm()
                vm.add_pool("upgrade", 15)
                vm.add_pool("new", 15)
                vm.native["upgrade_11"]["inputs"] = True
                vm.native[f"new_{rank}"]["inputs"] = True
                vm.native["new_11"]["inputs"] = True
                vm.run()
                self.assertEqual(vm.stage_calls, [f"new_{rank}"])
                self.assertIn(("new_10", "inputs"), vm.checks)
                self.assertNotIn(("upgrade_11", "inputs"), vm.checks)
                self.assertNotIn(("new_11", "inputs"), vm.checks)
                self.assertNotIn("eu5ab_worker_backfill_checked", vm.vars["location"])

    def test_missing_backfill_rank_is_not_zero(self):
        vm = self.vm()
        self.assertIsNone(vm.value("var:eu5ab_backfill_rank", ["location"]))
        self.assertFalse(vm.test("var:eu5ab_backfill_rank", "<=", "10", ["location"]))
        with self.assertRaisesRegex(AssertionError, "unset eu5ab_backfill_rank"):
            vm.execute(parse("change_variable = { name = eu5ab_backfill_rank add = 1 }"), ["location"])

    def test_empty_diagnostic_slots_do_not_read_unset_kinds(self):
        class DiagnosticVM(BackfillVM):
            def value(self, x, stack):
                result = super().value(x, stack)
                if isinstance(x, str) and re.fullmatch(r"var:eu5ab_diag_top_\d+_kind", x):
                    self.assert_kind_exists(result, x)
                return result

            @staticmethod
            def assert_kind_exists(result, name):
                if result is None:
                    raise AssertionError(f"Diagnostic read of unset {name}")

        vm = DiagnosticVM(self.definitions)
        vm.run("eu5ab_hydrate_final_building_diagnostics", vm.ROOT)
        vm.vars[vm.ROOT]["eu5ab_diag_top_1_kind"] = 2  # RGO; other slots empty.
        vm.run("eu5ab_hydrate_final_building_diagnostics", vm.ROOT)

    def test_first_tail_success_preserves_failure_state_and_stops(self):
        vm = self.vm()
        vm.add_pool("new", 20)
        vm.native["new_11"]["inputs"] = True
        vm.run()
        self.assertEqual(vm.staged(), [(8, "new_11")])
        self.assertEqual(vm.vars["location"]["eu5ab_worker_backfill_checked"], 1)
        self.assertEqual(vm.vars["location"]["eu5ab_worker_backfill_staged"], 1)
        self.assertEqual(vm.vars["location"]["eu5ab_worker_eu5ab_diag_fail_inputs"], 10)
        self.assertEqual([b for b, gate in vm.checks if gate == "inputs"],
                         [f"new_{rank}" for rank in range(1, 12)])
        self.assertIn("eu5ab_failure_cooldown", vm.vars["location"])
        self.assertNotIn("eu5ab_build_cooldown", vm.vars["location"])
        self.assertNotIn(("new_12", "inputs"), vm.checks)
        self.assert_scratch_clean(vm)

    def test_small_pools_and_candidate_beyond_window_do_not_expand_search(self):
        for size in (0, 9, 10, 16):
            vm = self.vm()
            vm.add_pool("new", size)
            if size == 16:
                vm.native["new_16"]["inputs"] = True
            vm.run()
            self.assertEqual(vm.staged(), [])
            self.assertEqual(vm.vars["location"].get("eu5ab_worker_backfill_checked", 0), 5 if size == 16 else 0)

    def test_food_layer_precedes_type_order_and_budget_is_shared(self):
        vm = self.vm(mode=1, n=3)
        for kind in backfill.CLASSES:
            vm.add_pool(kind, 5)
        vm.native["upgrade_4"]["inputs"] = True
        vm.native["new_4"].update(inputs=True, food=True)
        vm.run()
        self.assertEqual(vm.staged(), [(4, "new_4")])
        self.assertEqual(vm.vars["location"]["eu5ab_worker_backfill_checked"], 1)
        vm = self.vm(mode=1, n=3)
        for kind in backfill.CLASSES:
            vm.add_pool(kind, 5)
        vm.run()
        self.assertEqual(vm.vars["location"]["eu5ab_worker_backfill_checked"], 2)
        self.assertNotIn(("expansion_4", "inputs"), vm.checks)

    def test_custom_feature_order_is_used(self):
        vm = self.vm(mode=1, n=3)
        for kind in backfill.CLASSES:
            vm.add_pool(kind, 5)
            vm.native[f"{kind}_4"]["inputs"] = True
        vm.lists[vm.ROOT]["eu5ab_candidate_priority_features"] = [
            "flag:eu5ab_feature_new_building", "flag:eu5ab_feature_expand_rgo",
            "flag:eu5ab_feature_expand_building", "flag:eu5ab_feature_upgrade_building",
        ]
        vm.vars[vm.ROOT].update(eu5ab_candidate_priority_new=1, eu5ab_candidate_priority_upgrade=4,
                                 eu5ab_candidate_priority_expand=3)
        vm.run()
        self.assertEqual(vm.staged(), [(5, "new_4")])

    def test_supplement_does_not_suppress_ordinary_backfill_and_both_check_price(self):
        for succeeds in (False, True):
            vm = self.vm()
            vm.add_pool("new", 16)
            vm.upstream["new"] = ["new_11"]
            vm.native["new_11"].update(inputs=succeeds, output=False)
            vm.run()
            self.assertEqual(vm.upstream_calls, 1)
            if succeeds:
                self.assertEqual(vm.staged(), [])
                self.assertEqual(vm.vars["location"]["eu5ab_worker_backfill_output_rejected"], 1)
            else:
                self.assertEqual(vm.vars["location"]["eu5ab_worker_backfill_upstream_rechecks"], 1)

    def test_input_rejection_short_circuits_output_and_stage_failure_can_continue(self):
        vm = self.vm()
        vm.add_pool("new", 16, output=False)
        vm.native["new_12"]["inputs"] = True
        vm.native["new_13"].update(inputs=True, output=True)
        vm.native["new_14"].update(inputs=True, output=True)
        vm.stage_rejected.add("new_13")
        vm.run()
        self.assertNotIn(("new_11", "output"), vm.checks)
        self.assertEqual(vm.vars["location"]["eu5ab_worker_backfill_output_rejected"], 1)
        self.assertEqual(vm.vars["location"]["eu5ab_worker_backfill_stage_failed"], 1)
        self.assertEqual(vm.vars["location"]["eu5ab_worker_backfill_checked"], 4)
        self.assertEqual(vm.staged(), [(8, "new_14")])

    def test_dispatch_owner_change_cancelled_scan_and_stale_state(self):
        for invalid in ("owner", "scan", "pending", "disabled"):
            vm = self.vm()
            vm.add_pool("new", 16, inputs=False)
            vm.native["new_11"]["inputs"] = True
            vm.vars["location"]["eu5ab_backfill_done"] = 1
            vm.lists["location"][backfill.POOLS[0]] = ["new_11"]
            if invalid == "owner":
                vm.vars["other"] = deepcopy(vm.vars[vm.ROOT])
                vm.lists["other"] = {}
                vm.vars["location"]["eu5ab_backfill_dispatch_country"] = "other"
            elif invalid == "scan":
                vm.vars[vm.ROOT].pop("eu5ab_scan_active")
            elif invalid == "pending":
                vm.lists[vm.ROOT]["eu5ab_worker_pending_locations"] = []
            else:
                vm.vars[vm.ROOT].pop("eu5ab_scan_backfill_enabled")
            vm.run()
            self.assertEqual(vm.staged(), [])
            self.assertNotIn("eu5ab_worker_backfill_checked", vm.vars["location"])
            self.assert_scratch_clean(vm)

    def test_one_attempt_even_if_called_again(self):
        vm = self.vm(mode=1, n=3)
        vm.add_pool("new", 6)
        vm.vars["location"].update(eu5ab_worker_active=1, eu5ab_backfill_country=vm.ROOT,
                                    eu5ab_backfill_budget=2)
        vm.lists["location"][backfill.POOLS[2]] = ["new_4", "new_5", "new_6"]
        vm.run("eu5ab_try_candidate_backfill")
        vm.run("eu5ab_try_candidate_backfill")
        self.assertEqual(vm.vars["location"]["eu5ab_worker_backfill_checked"], 2)

    def test_snapshot_enable_disable_and_cleanup(self):
        vm = self.vm(enabled=False)
        vm.definitions["snapshot"] = parse("snapshot = {\n" + "\n".join(backfill.snapshot_lines()) + "\n}")[0][2]
        vm.run("snapshot", vm.ROOT)
        self.assertNotIn("eu5ab_scan_backfill_enabled", vm.vars[vm.ROOT])
        vm.vars[vm.ROOT]["eu5ab_global_candidate_backfill_enabled"] = 1
        vm.run("snapshot", vm.ROOT)
        vm.vars[vm.ROOT]["eu5ab_global_candidate_backfill_enabled"] = 0
        self.assertIn("eu5ab_scan_backfill_enabled", vm.vars[vm.ROOT])
        vm.run("snapshot", vm.ROOT)
        self.assertNotIn("eu5ab_scan_backfill_enabled", vm.vars[vm.ROOT])
        vm.vars["location"].update(eu5ab_backfill_dispatch_country=vm.ROOT,
                                    eu5ab_worker_backfill_checked=2, eu5ab_backfill_rank=1)
        vm.run("eu5ab_clear_location_worker_state")
        self.assert_scratch_clean(vm)
        self.assertNotIn("eu5ab_worker_backfill_checked", vm.vars["location"])

    def test_generated_backfill_initializes_every_mutated_counter(self):
        self.assertIn(
            "set_variable = { name = eu5ab_backfill_rank value = 1 }",
            self.effects,
        )
        for name in backfill.COUNTERS:
            with self.subTest(counter=name):
                self.assertIn(
                    f"limit = {{ has_variable = eu5ab_worker_backfill_{name} }}",
                    self.effects,
                )
                self.assertIn(
                    f"limit = {{ has_variable = eu5ab_diag_backfill_{name} }}",
                    self.effects,
                )

    def test_reducer_merges_candidates_and_backfill_counters_exactly_once(self):
        vm = self.vm()
        vm.add_pool("new", 16)
        vm.native["new_11"]["inputs"] = True
        vm.run()
        vm.run(MERGE, vm.ROOT)
        self.assertEqual(vm.vars[vm.ROOT]["eu5ab_scan_candidate_reserve"], 1)
        self.assertEqual(vm.vars[vm.ROOT]["eu5ab_diag_backfill_checked"], 1)
        self.assertEqual(vm.vars[vm.ROOT]["eu5ab_diag_backfill_staged"], 1)
        self.assertEqual(vm.lists["location"]["eu5ab_q_phase_8_types"], ["new_11"])
        self.assertFalse(any(k.startswith("eu5ab_worker_backfill_") for k in vm.vars["location"]))
        state = deepcopy((vm.vars, vm.lists))
        vm.run(MERGE, vm.ROOT)
        self.assertEqual((vm.vars, vm.lists), state)

    def test_serial_and_deferred_worker_merge_have_independent_budgets(self):
        results = []
        for parallel in (False, True):
            vm = self.vm(mode=1, n=3)
            vm.add_pool("new", 7)
            vm.native["new_5"]["inputs"] = True  # Uses both of the two checks.
            vm.vars["second"] = {"eu5ab_policy_id": 1, "eu5ab_backfill_dispatch_country": vm.ROOT}
            vm.lists["second"] = {}
            vm.owners["second"] = vm.ROOT
            vm.lists[vm.ROOT]["eu5ab_worker_pending_locations"] = []
            for location in ("location", "second"):
                vm.lists[vm.ROOT]["eu5ab_worker_pending_locations"].append(location)
                vm.run(root=location)
                self.assertEqual(vm.vars[location]["eu5ab_worker_backfill_checked"], 2)
                if not parallel:
                    vm.run(MERGE, vm.ROOT)
            if parallel:
                vm.run(MERGE, vm.ROOT)
            self.assertEqual(vm.vars[vm.ROOT]["eu5ab_diag_backfill_checked"], 4)
            self.assertEqual(vm.vars[vm.ROOT]["eu5ab_scan_candidate_reserve"], 2)
            self.assertTrue(all(not vm.vars[name] for name in vm.native))
            results.append((vm.vars, vm.lists))
        self.assertEqual(results[0], results[1])

    def test_staged_backfill_with_old_cooldown_still_uses_final_gui_gates(self):
        worker = self.vm()
        worker.add_pool("new", 16)
        worker.native["new_11"]["inputs"] = True
        worker.run()
        worker.run(MERGE, worker.ROOT)
        for rejected_gate in (None, "passes_selected_metric", "has_actual_budget", "keeps_actual_cash_reserve"):
            q = QueueVM(self.effects, automation.generated_fixture().scripted_guis)
            q.vars["location"] = deepcopy(worker.vars["location"])
            q.lists["location"] = deepcopy(worker.lists["location"])
            q.scopes["eu5ab_candidate_building"] = "new_11"
            q.scopes["eu5ab_engine_can_build"] = True
            q.vars[q.ROOT].update(eu5ab_q_active=1, eu5ab_q_phase=8, eu5ab_q_approved=0,
                                   eu5ab_monthly_build_quota=1, eu5ab_constructions_started_this_tick=0)
            q.scopes['eu5ab_engine_cost'] = 100
            q.native['scope:eu5ab_candidate_building.eu5ab_recipe_expected_output_value'] = 1
            for gate in ("in_current_priority_phase", "passes_selected_metric", "has_actual_budget", "keeps_actual_cash_reserve"):
                q.native["eu5ab_engine_candidate_" + gate] = gate != rejected_gate
            q.native["eu5ab_engine_construction_materials_available"] = True
            q.native["eu5ab_engine_candidate_has_emergency_demand"] = False
            q.stubs["eu5ab_approve_engine_candidate"] = lambda q=q: q.calls.append("approve")
            cold = q.vars["location"]["eu5ab_failure_cooldown"]
            q.run("eu5ab_gui_queue_try_candidate")
            self.assertEqual(q.calls, ["approve"] if rejected_gate is None else [])
            self.assertEqual(q.vars["location"]["eu5ab_failure_cooldown"], cold)

    def test_dispatch_uses_scanning_country_not_a_foreign_owner(self):
        vm = self.vm(enabled=False)
        vm.vars[vm.ROOT]["eu5ab_scan_backfill_enabled"] = 1
        vm.scopes["eu5ab_scan_country"] = vm.ROOT
        vm.run("eu5ab_prepare_backfill_dispatch")
        self.assertEqual(vm.vars["location"]["eu5ab_backfill_dispatch_country"], vm.ROOT)
        vm.scopes["eu5ab_scan_country"] = "foreign"
        vm.run("eu5ab_prepare_backfill_dispatch")
        self.assertNotIn("eu5ab_backfill_dispatch_country", vm.vars["location"])


if __name__ == "__main__":
    unittest.main()
