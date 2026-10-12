"""1.4 capacity and source regressions using generated script bodies."""
from dataclasses import replace
import unittest

from scripts.validate_governor_save import SaveSnapshot, RawLocation, build_attributed_source_values
from src.eu5autobuild.governor_model import evaluate_candidate
from src.eu5autobuild.governor_generator import render_governor_script_values
from tests._governor_script_vm import parse
from tests.test_governor_transport_runtime import TransportScriptVM


class Governor14Tests(unittest.TestCase):
    def test_refresh_distinguishes_zero_capacity_free_and_full_slots(self):
        for naval in (False, True):
            vm = TransportScriptVM(edges=())
            vm.connected = {1}
            vm.candidates = vm.naval_candidates = {3}
            kind = "naval" if naval else "local"
            effect = "eu5ab_naval_planner_" if naval else "eu5ab_governor_"
            prefix = "eu5ab_naval_gov_" if naval else "eu5ab_gov_"
            root = vm.vars[vm.ROOT]
            # Reuse one country so stale status/cards must be replaced each time.
            for capacity, occupied, status in ((0, False, 6), (1, False, 5),
                                                (1, True, 1), (0, True, 6)):
                with self.subTest(naval=naval, capacity=capacity, occupied=occupied):
                    vm.country_modifiers[f"num_{kind}_governors"] = capacity
                    vm.buildings = {(2, kind + "_governor"): 1} if occupied else {}
                    vm.location_modifiers[2]["local_proximity_source"] = 80 if occupied else 0
                    vm.call(effect + "refresh_other_recommendations")
                    self.assertEqual(root[prefix + "sync_status"], status)
                    self.assertEqual(root[prefix + f"fresh_{kind}_occupied"], int(occupied))
                    if status == 5:
                        self.assertEqual(root[f"eu5ab_{kind}_top_1"], 3)
                    else:
                        self.assertNotIn(f"eu5ab_{kind}_top_1", root)

    def test_capacity_uses_minimum_dlc_and_construction(self):
        vm = TransportScriptVM(nodes=range(1, 7), edges=())
        vm.country_modifiers.update(num_local_governors=1, minimum_num_local_governors=4)
        vm.buildings = {(2, "local_governor"): 1, (3, "lieutenancy"): 1, (4, "kings_manor"): 1}
        vm.construction = {(5, "itinerant_court_seat"): 1}
        vm.native_building_totals.update(local_governor=1, lieutenancy=1, kings_manor=1, itinerant_court_seat=1)
        for dlc, available, other in ((False, False, 3), (True, True, 2)):
            with self.subTest(dlc=dlc):
                vm.has_pillars_dlc = dlc
                vm.call("eu5ab_governor_snapshot_local_slot_state")
                for trigger in ("eu5ab_local_governor_slot_available", "eu5ab_fresh_local_governor_slot_available"):
                    self.assertEqual(vm.test(trigger, "=", "yes", [vm.ROOT]), available)
                self.assertEqual(vm.value("eu5ab_governor_local_other_slots", [vm.ROOT]), other)
                self.assertEqual(vm.value("eu5ab_governor_fresh_local_other_slots", [vm.ROOT]), other)
                self.assertEqual(vm.vars[vm.ROOT]["eu5ab_gov_fresh_local_capacity"], 4)

        # Beta installs may ship the building rules before registering the DLC.
        # Do not emit an invalid has_dlc reference, but still count Lieutenancies.
        unregistered = render_governor_script_values()
        self.assertNotIn('has_dlc =', unregistered)
        vm.script_values = {k: v for k, _, v in parse(unregistered)}
        vm.call("eu5ab_governor_snapshot_local_slot_state")
        self.assertEqual(vm.value("eu5ab_governor_local_other_slots", [vm.ROOT]), 3)
        self.assertEqual(vm.value("eu5ab_governor_fresh_local_other_slots", [vm.ROOT]), 3)
        self.assertFalse(vm.test("eu5ab_fresh_local_governor_slot_available", "=", "yes", [vm.ROOT]))

    def test_candidate_blocks_court_manor_but_allows_lieutenancy(self):
        vm = TransportScriptVM()
        vm.locations[2] = replace(vm.locations[2], road_to_capital=True)
        body = vm.script_triggers["eu5ab_local_governor_candidate"]
        for kind in ("lieutenancy", "itinerant_court_seat", "kings_manor", "local_governor", "seljuk_mint"):
            for construction in (False, True):
                if construction and kind == "seljuk_mint":
                    continue
                with self.subTest(kind=kind, construction=construction):
                    vm.buildings, vm.construction = {}, {}
                    (vm.construction if construction else vm.buildings)[(2, kind)] = 1
                    self.assertEqual(vm.condition(body, [vm.ROOT, 2]), kind == "lieutenancy")

    def source_fixture(self, naval=False):
        vm = TransportScriptVM(nodes=range(1, 6), edges=(), sources={1: 80, 2: 175, 3: -25, 4: 130, 5: 60})
        kind, other = ("naval", "local") if naval else ("local", "naval")
        vm.buildings = {(2, kind + "_governor"): 1, (5, kind + "_governor"): 1, (2, other + "_governor"): 1}
        vm.native_building_totals[kind + "_governor"] = 2
        vm.country_modifiers["num_naval_governors"] = 4
        vm.connected = {1}
        vm.candidates = vm.naval_candidates = {3, 4}
        return vm

    def finish(self, vm, naval=False):
        prefix = "eu5ab_naval_layout_" if naval else "eu5ab_layout_"
        active = "eu5ab_naval_planner_scan_active" if naval else "eu5ab_governor_scan_active"
        for _ in range(1000):
            if active not in vm.vars[vm.ROOT]:
                return
            vm.call(prefix + "tick")
        self.fail("Planner did not finish")

    def test_raw_sources_subtract_only_moving_type_before_clamp(self):
        for naval in (False, True):
            with self.subTest(naval=naval):
                vm = self.source_fixture(naval)
                # Stale native totals must not replace structural seat counts.
                vm.native_building_totals["naval_governor" if naval else "local_governor"] = 99
                effect = "eu5ab_naval_planner_" if naval else "eu5ab_governor_"
                layout = "eu5ab_naval_layout_" if naval else "eu5ab_layout_"
                vm.call(effect + "snapshot_transport")
                vm.call(layout + "begin")
                self.finish(vm, naval)
                self.assertIn(layout + "has_results", vm.vars[vm.ROOT])
                for node, expected in {1: 80, 2: 95, 3: 0, 4: 100, 5: 0}.items():
                    self.assertEqual(vm.vars[node][layout + "base"], expected)
                self.assertEqual(vm.vars[5][layout + "current"], 60)

    def test_publication_rejects_changed_source_capacity_or_occupancy(self):
        for naval in (False, True):
            for mutation in ("source", "capacity", "construction"):
                with self.subTest(naval=naval, mutation=mutation):
                    vm = self.source_fixture(naval)
                    effect = "eu5ab_naval_planner_" if naval else "eu5ab_governor_"
                    layout = "eu5ab_naval_layout_" if naval else "eu5ab_layout_"
                    vm.call(effect + "snapshot_transport")
                    vm.call(layout + "begin")
                    for _ in range(1000):
                        if vm.vars[vm.ROOT][layout + "phase"] == 5:
                            break
                        vm.call(layout + "tick")
                    else:
                        self.fail("No publication boundary")
                    if mutation == "source":
                        vm.location_modifiers[2]["local_proximity_source"] -= 15
                    elif mutation == "capacity":
                        vm.country_modifiers["num_naval_governors" if naval else "num_local_governors"] -= 1
                    else:
                        vm.construction[(4, "naval_governor" if naval else "local_governor")] = 1
                    vm.call(layout + "publish")
                    self.assertNotIn(layout + "has_results", vm.vars[vm.ROOT])
                    self.assertIn(layout + "failed", vm.vars[vm.ROOT])

    def test_over_capacity_does_not_publish_relocation(self):
        for naval in (False, True):
            with self.subTest(naval=naval):
                vm = self.source_fixture(naval)
                vm.country_modifiers["num_naval_governors" if naval else "num_local_governors"] = 1
                effect = "eu5ab_naval_planner_" if naval else "eu5ab_governor_"
                layout = "eu5ab_naval_layout_" if naval else "eu5ab_layout_"
                vm.call(effect + "snapshot_transport")
                vm.call(layout + "begin")
                self.finish(vm, naval)
                self.assertNotIn(layout + "has_results", vm.vars[vm.ROOT])

    def test_offline_14_sources_require_complete_raw_snapshot(self):
        snapshot = SaveSnapshot(version="1.4.0", player_country_id=1,
                                locations={n: RawLocation(n, runtime_variables={"eu5ab_gov_snapshot_native_source": v})
                                           for n, v in {1: 80, 2: 175, 3: -25, 4: 0}.items()})
        self.assertEqual(build_attributed_source_values(snapshot, {1, 2, 3, 4}, 1), {1: 80, 2: 175, 3: -25, 4: 0})
        snapshot.locations[4].runtime_variables.clear()
        with self.assertRaisesRegex(ValueError, "Missing complete raw"):
            build_attributed_source_values(snapshot, {1, 2, 3, 4}, 1)

    def test_new_candidate_adds_to_current_fixed_source(self):
        vm = TransportScriptVM(edges=(), sources={2: 30})
        vm.prepare()
        vm.call("eu5ab_governor_prepare_planned_baseline")
        vm.vars[vm.ROOT]["eu5ab_gov_eval_kind"] = 1
        vm.at("eu5ab_governor_evaluate_candidate", 2)
        reference = {2: replace(vm.locations[2], raw_proximity_source=30, proximity=30)}
        score = evaluate_candidate(2, reference, {}, {})
        self.assertEqual(vm.vars[2]["eu5ab_gov_eval_result_gain"], score.score)


if __name__ == "__main__":
    unittest.main()
