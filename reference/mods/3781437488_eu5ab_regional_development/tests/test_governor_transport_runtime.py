"""Execute the actual generated transport values and effects, not VM cost stubs.

This narrowly extends the shared script interpreter with value if/else blocks
and injected engine inputs. It remains an offline scope/logic test, not an
emulation of EU5 scheduling, fixed-point arithmetic, or game frame time.
"""

import math
import unittest

from src.eu5autobuild.governor_generator import (
    render_governor_effects,
    render_governor_script_values,
    render_governor_triggers,
)
from src.eu5autobuild.governor_model import LocationState
from tests._governor_script_vm import GovernorScriptVM, parse, substitute
from src.eu5autobuild.governor_connections import render_connection_effects, bundled_straits


class TransportScriptVM(GovernorScriptVM):
    def __init__(self, *, nodes=(1, 2, 3), edges=((1, 2), (2, 3)),
                 capital=1, roads=None, advances=(), sources=None, lakes=()):
        locations = {
            node: LocationState(node, str(node), "city", 0, 1, 1, 10, 10, 10)
            for node in nodes
        }
        neighbors = {node: set() for node in nodes}
        for a, b in edges:
            neighbors[a].add(b)
            neighbors[b].add(a)
        super().__init__(locations, neighbors, roads or {}, sources or {}, set(), set(nodes), capital)
        self.advance_set = set(advances)
        self.lakes = set(lakes)
        for node in lakes:
            self.owners[node] = None
        self.terrain = {node: "lakes" if node in lakes else "flatland" for node in nodes}
        self.vegetation = {node: "grasslands" for node in nodes}
        self.country_modifiers = {
            "num_local_governors": 4,
            "minimum_num_local_governors": 0,
            "num_naval_governors": 0,
            "global_distance_from_capital_speed_propagation": 0,
            "land_cost_on_distance_from_capital_speed_propagation": 0,
            "road_cost_on_distance_from_capital": 20,
            "land_cost_on_distance_from_capital": 40,
            "sea_cost_on_distance_from_capital_when_maritime": 4,
            "mountains_proximity_impact": 0,
            "hills_proximity_impact": 0,
            "plateau_proximity_impact": 0,
            "wetlands_proximity_impact": 0,
        }
        self.location_modifiers = {
            node: {
                "local_distance_from_capital_speed_propagation": 0,
                "local_proximity_source": (sources or {}).get(node, 100 if node == self.capital else 0),
            } for node in nodes
        }
        self.buildings = {}
        self.construction = {}
        # Native country totals are injected independently of record membership;
        # diagnostics must preserve a stale/different native count as observed.
        self.native_building_totals = {kind: 0 for kind in ("local_governor", "naval_governor", "lieutenancy", "itinerant_court_seat", "kings_manor")}
        self.has_pillars_dlc = False
        self.script_values = {k: v for k, _, v in parse(render_governor_script_values(
            registered_dlcs=frozenset({"d009_across_the_pillars"})))}
        self.script_triggers = {k: v for k, _, v in parse(render_governor_triggers())}
        self.definitions = {k: v for k, _, v in parse(render_governor_effects())}
        self.slot_available = True
        self.connected = set(nodes)
        self.vars[self.ROOT].update(
            eu5ab_global_governor_scoring_profile=1,
            eu5ab_global_governor_strategic_value=0,
        )
        # The shared VM has historical implementations of these two effect
        # names. Alias only their dispatch names so their real generated bodies
        # execute unchanged instead of entering those compatibility stubs.
        bypass = {
            "eu5ab_governor_snapshot_local_slot_state": "test_actual_local_slot_state",
            "eu5ab_naval_planner_snapshot_naval_slots": "test_actual_naval_slots",
            "eu5ab_governor_prepare_location_value": "test_actual_prepare_location_value",
            "eu5ab_governor_refresh_other_recommendations": "test_actual_refresh_other_recommendations",
            "eu5ab_naval_planner_prepare_location_value": "test_actual_naval_prepare_location_value",
            "eu5ab_naval_planner_refresh_other_recommendations": "test_actual_naval_refresh_other_recommendations",
            "eu5ab_governor_refresh_begin": "test_actual_refresh_begin",
            "eu5ab_naval_planner_refresh_begin": "test_actual_naval_refresh_begin",
        }
        self.bypass = bypass

        def actual(entries):
            return [(bypass.get(k, k), op, actual(v) if isinstance(v, list) else v)
                    for k, op, v in entries]

        for name, entries in list(self.definitions.items()):
            self.definitions[bypass.get(name, name)] = actual(entries)

    def call(self, name):
        super().call(self.bypass.get(name, name))

    def at(self, name, node):
        self.local, self.scopes = {}, {}
        self.operations = 0
        self.execute(self.definitions[self.bypass.get(name, name)], [self.ROOT, node])

    def arithmetic(self, entries, stack, current=0):
        matched = False
        for key, _, value in entries:
            if key in ("if", "else_if", "else"):
                if key == "if":
                    matched = False
                data = {k: v for k, _, v in value}
                if not matched and (key == "else" or self.condition(data["limit"], stack)):
                    current = self.arithmetic([item for item in value if item[0] != "limit"], stack, current)
                    matched = True
                continue
            if key == "value":
                current = self.value(value, stack)
            elif key == "add":
                current += self.value(value, stack)
            elif key == "subtract":
                current -= self.value(value, stack)
            elif key == "multiply":
                current *= self.value(value, stack)
            elif key == "divide":
                current /= self.value(value, stack)
            elif key == "min":
                current = max(current, self.value(value, stack))
            elif key == "max":
                current = min(current, self.value(value, stack))
            elif key == "floor":
                current = math.floor(current)
            elif key == "ceiling":
                current = math.ceil(current)
            elif key == "round":
                current = math.floor(current + 0.5)
            else:
                raise AssertionError(f"Unknown generated value operation {key}")
        return current

    def value(self, value, stack):
        if isinstance(value, list):
            return self.arithmetic(value, stack)
        if value == "effective_num_local_governors":
            return max(self.country_modifiers["num_local_governors"], self.country_modifiers["minimum_num_local_governors"])
        if value in self.script_values:
            return self.arithmetic(self.script_values[value], stack)
        if value.startswith("owner.modifier:"):
            self.assert_owned(stack[-1])
            return self.country_modifiers[value[len("owner.modifier:"):]]
        if value.startswith("prev.modifier:"):
            return self.value(value[len("prev."):], stack + [self.target("prev", stack)])
        if value.startswith("total_building_levels_including_construction:"):
            return self.native_building_totals[value.split(":", 1)[1]]
        if value.startswith("modifier:"):
            modifiers = self.country_modifiers if stack[-1] == self.ROOT else self.location_modifiers[stack[-1]]
            return modifiers[value[len("modifier:"):]]
        if value.startswith(("prev.eu5ab_", "root.eu5ab_", "owner.eu5ab_")):
            scope, script_value = value.split(".", 1)
            return self.value(script_value, stack + [self.target(scope, stack)])
        if value in ("population", "development", "proximity", "local_control", "max_control", "location_tax_base"):
            node = self.locations[stack[-1]]
            return {
                "population": node.population, "development": node.development,
                "proximity": node.proximity, "local_control": node.control,
                "max_control": node.max_control,
                "location_tax_base": node.potential_tax_base * node.control,
            }[value]
        return super().value(value, stack)

    def assert_owned(self, node):
        if self.owners.get(node) != self.ROOT:
            raise AssertionError(f"Country modifier requested from unowned node {node}")

    def test(self, key, op, value, stack):
        if key == "eu5ab_is_strait_connection_to":
            return self.condition(substitute(self.script_triggers[key], dict((k, v) for k, _, v in value)), stack)
        if key in ("eu5ab_gov_refresh_wave_budget_available", "eu5ab_naval_gov_refresh_wave_budget_available"):
            return self.condition(self.script_triggers[key], stack)
        if key in (
                   "eu5ab_fresh_naval_governor_slot_available",
                   "eu5ab_local_governor_slot_available",
                   "eu5ab_fresh_local_governor_slot_available"):
            return self.condition(self.script_triggers[key], stack) == (value == "yes")
        if key == "has_dlc":
            assert value == '"d009_across_the_pillars"' or value == "d009_across_the_pillars"
            return self.has_pillars_dlc
        if key == "always":
            return value == "yes"
        if key == "has_advance":
            return value in self.advance_set
        if key == "has_owner":
            return (self.owners.get(stack[-1]) is not None) == (value == "yes")
        if key == "location_rank":
            return self.locations[stack[-1]].rank == value.removeprefix("location_rank:")
        if key == "has_road_to_capital":
            return self.locations[stack[-1]].road_to_capital == (value == "yes")
        if key == "topography":
            return self.terrain[stack[-1]] == value
        if key == "vegetation":
            return self.vegetation[stack[-1]] == value
        if key == "is_ownable":
            return (stack[-1] not in self.lakes) == (value == "yes")
        if key == "is_land":
            return (stack[-1] not in self.lakes) == (value == "yes")
        if key == "is_connected_to_through_realm":
            return stack[-1] in self.connected
        if key in ("any_owned_location", "any_neighbor_location"):
            nodes = (
                [node for node, owner in self.owners.items() if owner == self.ROOT]
                if key == "any_owned_location" else self.neighbors.get(stack[-1], ())
            )
            return any(self.condition(value, stack + [node]) for node in nodes)
        if key == "has_road_to":
            return frozenset((stack[-1], self.value(value, stack))) in self.roads
        if key == "has_road_of_type_to":
            data = {k: v for k, _, v in value}
            return self.roads.get(frozenset((stack[-1], self.value(data["target"], stack)))) == data["type"].split(":")[1]
        if key == "has_building":
            return self.buildings.get((stack[-1], value.split(":")[1]), 0) > 0
        if key == "eu5ab_local_governor_candidate":
            node = stack[-1]
            return (node in self.candidates and node not in self.old
                    and not any(self.buildings.get((node, kind), 0)
                                or self.construction.get((node, kind), 0)
                                for kind in ("local_governor", "itinerant_court_seat", "kings_manor", "seljuk_mint")))
        if key == "eu5ab_naval_governor_candidate":
            node = stack[-1]
            return (node in self.naval_candidates and node not in self.connected
                    and not self.buildings.get((node, "naval_governor"), 0)
                    and not self.construction.get((node, "naval_governor"), 0))
        if key == "any_buildings_in_location":
            # Execute the predicate on injected structural building records.
            return any(self.condition(value, stack + [(stack[-1], kind)])
                       for kind in {k for n, k in self.buildings if n == stack[-1]}
                       | {k for n, k in self.construction if n == stack[-1]})
        if key == "building_type":
            return stack[-1][1] == value.split(":")[1]
        if key == "building_levels_under_construction":
            if op != ">":
                raise AssertionError(f"Unexpected construction comparison: {op}")
            return self.construction.get(stack[-1], 0) > float(value)
        if key == "location_building_level":
            kind = next(v for k, _, v in value if k == "building_type").split(":")[1]
            level = next((op, v) for k, op, v in value if k == "value")
            if level[0] != ">=":
                raise AssertionError("Unexpected building level comparison")
            return self.buildings.get((stack[-1], kind), 0) >= float(level[1])
        if key == "eu5ab_naval_governor_slot_available":
            return self.slot_available
        return super().test(key, op, value, stack)

    def prepare(self):
        connections = {}
        for pair in self.special_edges:
            a, b = pair
            connections.setdefault(self.location_keys[a], []).append(self.location_keys[b])
            connections.setdefault(self.location_keys[b], []).append(self.location_keys[a])
        self.definitions.update({k: v for k, _, v in parse(render_connection_effects(connections))})
        self.call("eu5ab_governor_clear_country_results")
        self.call("eu5ab_governor_snapshot_transport")
        for node, owner in self.owners.items():
            if owner == self.ROOT:
                self.at("eu5ab_governor_clear_location_cache", node)
                self.at("eu5ab_governor_prepare_location_value", node)

    def prediction(self, source, destination, *, known_land=False):
        self.scopes["eu5ab_gov_edge_from"] = source
        self.vars[source]["eu5ab_gov_predicted"] = 100
        value = ("eu5ab_governor_known_land_edge_prediction" if known_land else
                 "eu5ab_governor_land_edge_prediction")
        return self.value(value, [self.ROOT, destination])


class GovernorTransportRuntimeTests(unittest.TestCase):
    def test_layout_road_batches_recompute_requeued_sources_and_keep_water_costs(self):
        edges = [(1, 2), (1, 3), (2, 4), (3, 5), (4, 5), (4, 6),
                 (1, 7), (1, 8), (8, 9), (1, 10)] + [(1, n) for n in range(11, 86)]
        roads = {frozenset(edge): "railroad" for edge in edges if edge not in ((1, 3), (1, 7))}
        for naval in (False, True):
            for advances in ((), ("railroad_advance",)):
                with self.subTest(naval=naval, advances=advances):
                    vm = TransportScriptVM(nodes=range(1, 86), edges=edges, roads=roads,
                                           advances=advances, lakes={8})
                    vm.special_edges = {frozenset((1, 7))}
                    vm.owners[10] = "foreign"
                    # The slow route reaches node 4 first. A later improvement
                    # must propagate through 4 again and update node 6.
                    vm.location_modifiers[2]["local_distance_from_capital_speed_propagation"] = -0.9
                    vm.prepare()
                    effect = "eu5ab_naval_planner_" if naval else "eu5ab_governor_"
                    layout = "eu5ab_naval_layout_" if naval else "eu5ab_layout_"
                    gov = "eu5ab_naval_gov_" if naval else "eu5ab_gov_"
                    root = vm.vars[vm.ROOT]
                    if naval:
                        root[effect + "total_value"] = 0
                        vm.call(effect + "snapshot_transport")
                        for node, owner in vm.owners.items():
                            if owner == vm.ROOT:
                                vm.at(effect + "prepare_location_value", node)
                    root.update({effect + "scan_active": 1, gov + "eval_generation": 0,
                                 gov + "refresh_phase": 0, layout + "mode": 2,
                                 layout + "total_work": 0, layout + "ticks": 0,
                                 layout + "wave_budget": 1000,
                                 layout + "snapshot_capital": vm.capital,
                                 layout + "snapshot_count": sum(o == vm.ROOT for o in vm.owners.values())})
                    for node in vm.locations:
                        vm.vars[node][gov + "visit_generation"] = -1
                        vm.vars[node][layout + "base"] = 0
                    lake_state = dict(vm.vars[8])
                    vm.call(layout + "reset_wave")
                    vm.local[layout + "seed_value"] = 100
                    vm.execute(vm.definitions[layout + "seed"], [vm.ROOT, 1])
                    vm.call(layout + "tick")
                    self.assertEqual(root[layout + "phase"], 1)
                    self.assertEqual(root[layout + "wave_work"], 64)
                    self.assertEqual(root[layout + "pending_nodes"], 0)
                    vm.call(layout + "snapshot_progress")
                    vm.call(layout + "tick")
                    vm.call(layout + "check_liveness")
                    self.assertNotIn(layout + "failed", root)
                    self.assertEqual(root[layout + "phase"], 2)
                    self.assertEqual(root[layout + "pending_nodes"], root[layout + "footprint_nodes"])
                    self.assertGreater(root[layout + "wave_work"], root[layout + "footprint_nodes"])
                    for _ in range(2):
                        vm.call(layout + "tick")
                    self.assertEqual(root[layout + "pending_nodes"], 0)
                    self.assertNotEqual(root[layout + "phase"], 2)
                    expected = {1: 100, 2: 95, 3: 95 if advances else 60,
                                4: 85 if advances else 50, 5: 90 if advances else 55,
                                6: 80 if advances else 45, 7: 60 if naval else 0, 9: 92}
                    for node, value in expected.items():
                        self.assertAlmostEqual(vm.vars[node][layout + "base"], value)
                    self.assertEqual(vm.vars[8], lake_state)
                    self.assertNotIn(gov + "predicted", vm.vars[10])

    def test_generated_map_cache_covers_straits_in_both_directions_and_empty_results(self):
        connections = bundled_straits()
        nodes = tuple(connections) + ("ordinary_land",)
        vm = TransportScriptVM(nodes=nodes, edges=(), capital=nodes[0])
        original_value = vm.value

        def checked_value(value, stack):
            # EU5 logs an error on an unset variable comparison; the general
            # VM's None comparison previously hid this first-load error.
            if value == "var:eu5ab_strait_schema":
                self.assertIn("eu5ab_strait_schema", vm.vars[stack[-1]])
            return original_value(value, stack)

        vm.value = checked_value
        for node in nodes:
            vm.at("eu5ab_prepare_strait_connections", node)
            self.assertEqual(set(vm.lists[node]["eu5ab_strait_neighbors"]), set(connections.get(node, ())))
            for target in connections.get(node, ()):
                self.assertTrue(vm.test("eu5ab_is_strait_connection_to", "=", [("target", "=", "location:" + target)], [vm.ROOT, node]))
        self.assertIn("bardodalen", vm.lists["senja"]["eu5ab_strait_neighbors"])
        self.assertIn("senja", vm.lists["bardodalen"]["eu5ab_strait_neighbors"])
        self.assertFalse(vm.test("eu5ab_is_strait_connection_to", "=", [("target", "=", "location:senja")], [vm.ROOT, "ordinary_land"]))
        version = vm.vars["ordinary_land"]["eu5ab_strait_schema"]
        vm.owners["ordinary_land"] = "other_country"
        vm.at("eu5ab_prepare_strait_connections", "ordinary_land")
        self.assertEqual(vm.vars["ordinary_land"]["eu5ab_strait_schema"], version)
        # A map revision rebuilds both positive and negative cached entries.
        vm.definitions.update({k: v for k, _, v in parse(render_connection_effects({}, revision='test_v2'))})
        vm.at("eu5ab_prepare_strait_connections", "senja")
        self.assertEqual(vm.lists["senja"]["eu5ab_strait_neighbors"], [])

    def test_interleaved_batched_refresh_matches_manual_and_keeps_published_cards(self):
        def fixture():
            vm = TransportScriptVM(nodes=range(1, 41), edges=[(n, n + 1) for n in range(1, 40)], advances={"railroad_advance"})
            vm.candidates.discard(1)
            vm.connected = set(range(1, 21))
            vm.naval_candidates = set(range(21, 41))
            vm.country_modifiers["num_naval_governors"] = 2
            vm.vars[vm.ROOT]["eu5ab_global_governor_migration_enabled"] = 0
            return vm
        manual, automatic = fixture(), fixture()
        manual.call("eu5ab_governor_manual_recalculation")
        root = automatic.vars[automatic.ROOT]
        root.update(eu5ab_local_top_1=999, eu5ab_naval_top_1=998)
        automatic.call("eu5ab_governor_run_recalculation_now")
        automatic.call("eu5ab_naval_planner_run_recalculation_now")
        self.assertEqual(root["eu5ab_local_top_1"], 999)
        self.assertEqual(root["eu5ab_naval_top_1"], 998)
        automatic.call("eu5ab_layout_tick")
        self.assertEqual(root["eu5ab_gov_refresh_phase"], 1)
        self.assertEqual(root["eu5ab_gov_refresh_cursor"], 33)
        for _ in range(1000):
            active = False
            for prefix, tick in (("eu5ab_governor_", "eu5ab_layout_tick"), ("eu5ab_naval_planner_", "eu5ab_naval_layout_tick")):
                if prefix + "scan_active" in root:
                    automatic.call(tick)
                    active = True
            if not active:
                break
        self.assertNotIn("eu5ab_governor_scan_active", root)
        self.assertNotIn("eu5ab_naval_planner_scan_active", root)
        for kind in ("local", "naval"):
            published = {k: v for k, v in manual.vars[manual.ROOT].items() if k.startswith(f"eu5ab_{kind}_top_")}
            self.assertTrue(published)
            self.assertEqual(published, {k: v for k, v in root.items() if k.startswith(f"eu5ab_{kind}_top_")})

    def test_refresh_reuses_raw_inputs_for_layout_and_skips_unneeded_baseline(self):
        vm = self.recommendation_fixture()
        vm.buildings[(2, "local_governor")] = 1
        vm.location_modifiers[2]["local_proximity_source"] = 80
        root = vm.vars[vm.ROOT]
        root["test_prepare_count"] = 0
        vm.definitions[vm.bypass["eu5ab_governor_prepare_location_value"]][:0] = parse("root = { change_variable = { name = test_prepare_count add = 1 } }")
        vm.call("eu5ab_governor_manual_recalculation")
        self.assertEqual(root["test_prepare_count"], len(vm.locations))
        self.assertIn("eu5ab_layout_ready", root)
        # A full country without relocation enabled needs neither input values
        # nor a baseline; structural slot counts still include construction.
        vm.country_modifiers["num_local_governors"] = 1
        root["eu5ab_global_governor_migration_enabled"] = 0
        root["test_prepare_count"] = 0
        root.pop("eu5ab_gov_refresh_wave_work", None)
        vm.call("eu5ab_governor_run_recalculation_now")
        vm.finish()
        self.assertEqual(root["test_prepare_count"], 0)
        self.assertNotIn("eu5ab_gov_refresh_wave_work", root)
        self.assertNotIn("eu5ab_local_top_1", root)

    def test_manual_feature_off_still_publishes_new_sites_without_layout_work(self):
        vm = self.recommendation_fixture()
        vm.cmm_settings.update(eu5ab_global_governor_relocation_enabled=0,
                               eu5ab_global_governor_migration_enabled=1)
        vm.call("eu5ab_governor_manual_recalculation")
        root = vm.vars[vm.ROOT]
        self.assertIn("eu5ab_local_top_1", root)
        self.assertIn("eu5ab_local_governor_available_alert", vm.alerts)
        self.assertEqual(root.get("eu5ab_layout_phase", 0), 0)
        self.assertNotIn("eu5ab_layout_has_results", root)
        self.assertNotIn("eu5ab_layout_failed", root)
        self.assertNotIn("eu5ab_governor_scan_active", root)
        self.assertNotIn("eu5ab_governor_manual_run", root)
        self.assertEqual(root["eu5ab_global_governor_relocation_enabled"], 0)
        self.assertEqual(root["eu5ab_global_governor_migration_enabled"], 1)

    def test_periodic_new_site_scan_preserves_naval_card_when_auto_off(self):
        vm = self.recommendation_fixture()
        root = vm.vars[vm.ROOT]
        vm.slot_available = False
        root.update(eu5ab_global_governor_migration_enabled=0,
                    eu5ab_naval_top_1=5)
        vm.lists[vm.ROOT]["eu5ab_naval_top_1_list"] = [5]
        before = {key: value for key, value in root.items() if key.startswith("eu5ab_naval_")}
        vm.call("eu5ab_governor_run_recalculation_now")
        vm.finish()
        for key, value in before.items():
            self.assertEqual(root[key], value, key)
        self.assertEqual(vm.lists[vm.ROOT]["eu5ab_naval_top_1_list"], [5])
        self.assertIn("eu5ab_local_top_1", root)
        self.assertNotIn("eu5ab_governor_scan_active", root)
        self.assertNotIn("eu5ab_governor_preserve_naval_results", root)
        # Only the naval consumer may replace naval cards when its slots change.
        vm.country_modifiers["num_naval_governors"] = 1
        vm.call("eu5ab_naval_planner_run_recalculation_now")
        while "eu5ab_naval_planner_scan_active" in root:
            vm.call("eu5ab_naval_layout_tick")
        self.assertNotIn("eu5ab_naval_top_1", root)

    def recommendation_fixture(self):
        vm = TransportScriptVM(nodes=range(1, 15),
                               edges=[(n, n+1) for n in range(1, 14)],
                               advances={"railroad_advance"})
        vm.candidates.discard(1)
        return vm

    def test_stale_native_full_count_does_not_block_fresh_free_slot(self):
        vm = self.recommendation_fixture()
        vm.buildings.update({(n, "local_governor"): 1 for n in (2, 3, 4)})
        vm.native_building_totals["local_governor"] = 4
        vm.call("eu5ab_governor_refresh_other_recommendations")
        root = vm.vars[vm.ROOT]
        self.assertEqual(root["eu5ab_gov_sync_occupied"], 4)
        self.assertEqual(root["eu5ab_gov_sync_fresh_occupied"], 3)
        self.assertEqual(root["eu5ab_gov_sync_slot_available"], 0)
        self.assertEqual(root["eu5ab_gov_sync_fresh_slot_available"], 1)
        self.assertEqual(root["eu5ab_gov_sync_slot_cache_mismatch"], 1)
        self.assertGreater(root["eu5ab_local_top_1_score"], root["eu5ab_gov_sync_threshold"])
        self.assertEqual(root["eu5ab_gov_sync_status"], 5)
        self.assertIn("eu5ab_local_governor_available_alert", vm.alerts)

    def test_shared_and_under_construction_slots_override_stale_low_native_count(self):
        for last_kind in ("local_governor", "lieutenancy"):
            with self.subTest(last_kind=last_kind):
                vm = self.recommendation_fixture()
                vm.buildings.update({(n, "local_governor"): 1 for n in (2, 3, 4)})
                vm.construction[(5, last_kind)] = 1
                # A completed site with a construction record counts only once.
                vm.construction[(2, "local_governor")] = 1
                vm.call("eu5ab_governor_refresh_other_recommendations")
                root = vm.vars[vm.ROOT]
                self.assertEqual(root["eu5ab_gov_sync_slot_available"], 1)
                self.assertEqual(root["eu5ab_gov_sync_fresh_slot_available"], 0)
                self.assertEqual(root["eu5ab_gov_sync_status"], 1)
                self.assertNotIn("eu5ab_local_top_1", root)
                self.assertNotIn("eu5ab_local_governor_available_alert", vm.alerts)
                del vm.construction[(5, last_kind)]
                vm.call("eu5ab_governor_refresh_other_recommendations")
                self.assertEqual(root["eu5ab_gov_sync_fresh_slot_available"], 1)
                self.assertIn("eu5ab_local_governor_available_alert", vm.alerts)

    def test_manual_reads_settings_runs_both_consumers_with_auto_toggles_off(self):
        vm = self.recommendation_fixture()
        root = vm.vars[vm.ROOT]
        vm.cmm_settings.update(eu5ab_global_governor_recommendations_enabled=0,
                               eu5ab_global_governor_migration_enabled=0,
                               eu5ab_global_governor_scoring_profile=2)
        root.update(eu5ab_governor_scan_active=True,
                    eu5ab_layout_has_results=True,
                    eu5ab_layout_result_net=999999,
                    eu5ab_local_migration_cooldown=9,
                    eu5ab_governor_recalculation_scheduled=True)
        vm.call("eu5ab_governor_manual_recalculation")
        self.assertEqual(root["eu5ab_global_governor_scoring_profile"], 2)
        self.assertEqual(root["eu5ab_global_governor_recommendations_enabled"], 0)
        self.assertEqual(root["eu5ab_global_governor_migration_enabled"], 0)
        self.assertIn("eu5ab_local_top_1", root)
        self.assertEqual(root["eu5ab_layout_result_net"], 0)
        self.assertNotIn("eu5ab_layout_has_results", root)  # No existing seats to move.
        self.assertEqual(root["eu5ab_gov_result_road_tier"], 4)
        self.assertNotIn("eu5ab_governor_manual_run", root)
        self.assertNotIn("eu5ab_governor_scan_active", root)
        self.assertIn("eu5ab_governor_skip_next_scheduled_event", root)
        self.assertIn("eu5ab_governor_window_requested", root)
        self.assertNotIn("eu5ab_governor_manual_realert", root)
        self.assertNotIn("eu5ab_governor_manual_run", root)
        self.assertNotIn("eu5ab_layout_failed", root)
        self.assertEqual(root["eu5ab_local_migration_cooldown"], 9)
        runs = root["eu5ab_gov_sync_runs"]
        vm.call("eu5ab_governor_run_recalculation_now")
        self.assertEqual(root["eu5ab_gov_sync_runs"], runs)

    def test_same_target_manual_realerts_but_periodic_refresh_deduplicates(self):
        vm = self.recommendation_fixture()
        vm.vars[vm.ROOT]["eu5ab_global_governor_migration_enabled"] = 0
        alert = "eu5ab_local_governor_available_alert"
        vm.call("eu5ab_governor_manual_recalculation")
        target = vm.vars[vm.ROOT]["eu5ab_local_top_1"]
        vm.alert_actions.clear()
        # Repeated click after the first synchronous result.
        vm.call("eu5ab_governor_manual_recalculation")
        self.assertEqual(vm.vars[vm.ROOT]["eu5ab_local_top_1"], target)
        self.assertIn(("cmf_remove_alert", alert), vm.alert_actions)
        self.assertIn(("cmf_show_alert", alert), vm.alert_actions)
        vm.finish()
        vm.alert_actions.clear()
        vm.call("eu5ab_governor_refresh_other_recommendations")
        self.assertNotIn(("cmf_show_alert", alert), vm.alert_actions)

    def test_current_temporary_source_is_kept_without_suppressing_layout(self):
        vm = TransportScriptVM(sources={2: 80}, advances={"railroad_advance"})
        vm.buildings[(2, "local_governor")] = 1
        vm.location_modifiers[3]["local_proximity_source"] = 80
        vm.call("eu5ab_governor_refresh_other_recommendations")
        root = vm.vars[vm.ROOT]
        self.assertEqual(vm.vars[3]["eu5ab_gov_snapshot_source"], 80)
        self.assertIn("eu5ab_gov_refresh_need_layout", root)
        self.assertEqual(root["eu5ab_local_top_1"], 3)
        self.assertGreater(root["eu5ab_local_top_1_score"], 0)

    def test_sync_diagnostics_preserve_native_block_and_reset_on_next_refresh(self):
        vm = TransportScriptVM(nodes=range(1, 12), edges=[(n, n+1) for n in range(1, 11)],
                               advances={"railroad_advance"})
        vm.candidates.discard(1)
        vm.native_building_totals["local_governor"] = 4
        vm.buildings.update({(n, "local_governor"): 1 for n in (1, 2, 3, 4)})
        vm.slot_available = False
        vm.vars[vm.ROOT]["eu5ab_global_governor_migration_enabled"] = 0
        vm.call("eu5ab_governor_refresh_other_recommendations")
        root = vm.vars[vm.ROOT]
        self.assertEqual(root["eu5ab_gov_sync_stage"], 4)
        self.assertEqual(root["eu5ab_gov_sync_capacity"], 4)
        self.assertEqual(root["eu5ab_gov_sync_occupied"], 4)
        self.assertEqual(root["eu5ab_gov_sync_slot_available"], 0)
        self.assertEqual(root["eu5ab_gov_sync_candidates"], 7)
        self.assertEqual(root["eu5ab_gov_sync_shortlisted"], 0)
        self.assertNotIn("eu5ab_local_top_1", root)

        vm.native_building_totals["local_governor"] = 3
        del vm.buildings[(4, "local_governor")]
        vm.slot_available = True
        root["eu5ab_global_governor_migration_enabled"] = 1
        vm.call("eu5ab_recalculate_governor_recommendations")
        while root["eu5ab_gov_refresh_phase"] > 0:
            vm.call("eu5ab_layout_tick")
        self.assertEqual(root["eu5ab_gov_sync_runs"], 2)
        self.assertEqual(root["eu5ab_gov_sync_occupied"], 3)
        self.assertEqual(root["eu5ab_gov_sync_shortlisted"], 8)
        self.assertGreater(root["eu5ab_local_top_1_score"], 0)
        self.assertTrue(root["eu5ab_local_has_new_recommendation"])
        self.assertIn("eu5ab_local_governor_available_alert", vm.alerts)
        self.assertTrue(root["eu5ab_governor_scan_active"])
        self.assertIn("eu5ab_local_score", vm.vars[root["eu5ab_local_top_1"]])

    def test_full_sync_pipeline_publishes_its_road_tier_snapshot(self):
        vm = TransportScriptVM(advances={"railroad_advance"})
        vm.call("eu5ab_governor_refresh_other_recommendations")
        self.assertEqual(vm.vars[vm.ROOT]["eu5ab_gov_result_road_tier"], 4)
        self.assertEqual(vm.vars[3]["eu5ab_gov_planned_proximity"], 90)
        self.assertNotIn("eu5ab_local_top_1", vm.vars[vm.ROOT])
        vm.advance_set = {"road_building"}
        vm.call("eu5ab_governor_check_transport_rules")
        self.assertTrue(vm.vars[vm.ROOT]["eu5ab_governor_dirty"])
        self.assertEqual(vm.vars[vm.ROOT]["eu5ab_gov_result_road_tier"], 4)

    def test_schema_invalidation_clears_old_cards_without_consuming_event_markers(self):
        vm = TransportScriptVM()
        root = vm.vars[vm.ROOT]
        root.update(
            eu5ab_gov_transport_schema=1, eu5ab_gov_result_road_tier=4,
            eu5ab_governor_recalculation_scheduled=True,
            eu5ab_governor_skip_next_scheduled_event=True,
            eu5ab_governor_months_since_refresh=2,
            eu5ab_local_top_1=2, eu5ab_local_top_1_score=999,
            eu5ab_local_has_new_recommendation=True,
        )
        vm.lists[vm.ROOT]["eu5ab_local_top_1_list"] = [2]
        vm.alerts.add("eu5ab_local_governor_available_alert")
        vm.call("eu5ab_governor_check_transport_rules")
        self.assertNotIn("eu5ab_local_top_1", root)
        self.assertNotIn("eu5ab_local_top_1_score", root)
        self.assertNotIn("eu5ab_gov_result_road_tier", root)
        self.assertNotIn("eu5ab_local_has_new_recommendation", root)
        self.assertFalse(vm.lists[vm.ROOT]["eu5ab_local_top_1_list"])
        self.assertNotIn("eu5ab_local_governor_available_alert", vm.alerts)
        self.assertTrue(root["eu5ab_governor_recalculation_scheduled"])
        self.assertTrue(root["eu5ab_governor_skip_next_scheduled_event"])
        self.assertEqual(root["eu5ab_governor_months_since_refresh"], 2)

    def test_generated_highest_unlock_applies_to_roadless_links(self):
        vm = TransportScriptVM(advances={"road_building", "railroad_advance"})
        vm.prepare()
        self.assertEqual(vm.vars[vm.ROOT]["eu5ab_gov_transport_schema"], 2)
        self.assertEqual(vm.vars[vm.ROOT]["eu5ab_gov_transport_road_tier"], 4)
        self.assertEqual(vm.prediction(1, 2), 95)
        vm.advance_set = {"road_building"}
        vm.prepare()
        self.assertEqual(vm.prediction(1, 2), 80)

    def test_generated_cost_uses_source_and_separate_terrain_divisor(self):
        vm = TransportScriptVM(advances={"railroad_advance"})
        vm.terrain[1] = "hills"
        vm.vegetation[1] = "jungle"
        vm.location_modifiers[1]["local_distance_from_capital_speed_propagation"] = 0.8296
        vm.prepare()
        self.assertAlmostEqual(vm.prediction(1, 2), 100 - 5 / 1.8296 / 0.75)
        self.assertEqual(vm.prediction(2, 1), 95)
        vm.country_modifiers["hills_proximity_impact"] = 0.2
        vm.prepare()
        self.assertAlmostEqual(vm.prediction(1, 2), 100 - 5 / 1.8296 / 0.7)

    def test_no_unlock_uses_actual_road_and_roadless_vegetation(self):
        vm = TransportScriptVM(roads={frozenset((2, 3)): "railroad"})
        vm.vegetation[1] = "jungle"
        vm.prepare()
        self.assertEqual(vm.vars[vm.ROOT]["eu5ab_gov_transport_road_tier"], 0)
        self.assertEqual(vm.prediction(1, 2), 20)
        self.assertEqual(vm.prediction(2, 3), 95)

    def test_known_land_value_matches_general_value_across_transport_inputs(self):
        unlocks = ((), ("road_building",), ("paved_road_advance",),
                   ("modern_road_advance",), ("railroad_advance",))
        for advances in unlocks:
            for road in (None, "dirt_road", "paved_road", "modern_road", "railroad"):
                for terrain, vegetation, local_speed in (
                    ("flatland", "grasslands", 0),
                    ("hills", "forest", 0.37),
                    ("mountains", "jungle", -0.2),
                ):
                    with self.subTest(advances=advances, road=road, terrain=terrain,
                                      vegetation=vegetation, local_speed=local_speed):
                        roads = {frozenset((1, 2)): road} if road else {}
                        vm = TransportScriptVM(roads=roads, advances=advances)
                        vm.terrain[1] = terrain
                        vm.vegetation[1] = vegetation
                        vm.location_modifiers[1]["local_distance_from_capital_speed_propagation"] = local_speed
                        vm.country_modifiers["global_distance_from_capital_speed_propagation"] = 0.14
                        vm.country_modifiers["land_cost_on_distance_from_capital_speed_propagation"] = 0.11
                        vm.prepare()
                        self.assertAlmostEqual(vm.prediction(1, 2, known_land=True),
                                               vm.prediction(1, 2))
                        self.assertAlmostEqual(vm.prediction(2, 1, known_land=True),
                                               vm.prediction(2, 1))

    def test_straits_receive_no_hypothetical_railroad_and_naval_baseline_matches(self):
        vm = TransportScriptVM(advances={"railroad_advance"})
        vm.special_edges = {frozenset((1, 2))}
        vm.prepare()
        self.assertEqual(vm.prediction(1, 2), 60)
        vm.call("eu5ab_governor_prepare_planned_baseline")
        self.assertEqual(vm.vars[2]["eu5ab_gov_planned_proximity"], 0)
        vm.call("eu5ab_governor_prepare_planned_naval_baseline")
        self.assertEqual(vm.vars[2]["eu5ab_gov_planned_proximity"], 60)
        self.assertEqual(vm.vars[3]["eu5ab_gov_planned_proximity"], 55)

    def test_source_ownership_and_raw_completed_source_use_native_modifier(self):
        vm = TransportScriptVM(nodes=(1, 2, 3, 4), edges=((1, 2), (2, 3)), capital=4,
                               sources={1: 80}, advances={"railroad_advance"})
        vm.owners[2] = "foreign"
        vm.prepare()
        vm.call("eu5ab_governor_prepare_planned_baseline")
        self.assertEqual(vm.vars[1]["eu5ab_gov_planned_proximity"], 80)
        self.assertEqual(vm.vars[3]["eu5ab_gov_planned_proximity"], 0)
        self.assertNotIn("eu5ab_gov_predicted", vm.vars[2])

    def test_lake_transit_uses_two_directed_costs_without_shared_water_state(self):
        vm = TransportScriptVM(nodes=(1, 2, 3, 4), edges=((1, 2), (2, 3), (2, 4)),
                               lakes={2}, advances={"railroad_advance"})
        vm.owners[4] = "foreign"
        vm.country_modifiers["global_distance_from_capital_speed_propagation"] = 0.536
        vm.country_modifiers["land_cost_on_distance_from_capital_speed_propagation"] = 0.1224
        vm.location_modifiers[1]["local_distance_from_capital_speed_propagation"] = 0.2765
        vm.prepare()
        untouched = dict(vm.vars[2])
        vm.call("eu5ab_governor_prepare_planned_baseline")
        self.assertAlmostEqual(vm.vars[3]["eu5ab_gov_planned_proximity"], 100 - 4 / 1.8125 - 4 / 1.536)
        self.assertEqual(vm.vars[2], untouched)
        self.assertNotIn("eu5ab_gov_predicted", vm.vars[4])

    def test_planned_baseline_removes_road_upgrade_gain_from_new_candidate(self):
        vm = TransportScriptVM(advances={"railroad_advance"})
        vm.prepare()
        vm.call("eu5ab_governor_prepare_planned_baseline")
        self.assertEqual(vm.vars[3]["eu5ab_gov_planned_proximity"], 90)
        vm.at("eu5ab_governor_evaluate_local_candidate", 3)
        self.assertEqual(vm.vars[3]["eu5ab_local_score"], 0)
        self.assertEqual(vm.vars[3]["eu5ab_local_coverage"], 0)

    def test_baseline_budget_exhaustion_suppresses_partial_ranking_and_cleans_queue(self):
        vm = TransportScriptVM(advances={"railroad_advance"})
        vm.prepare()
        # This fixture changes only the bounded work allowance to zero. The
        # actual generated seeding, failure gate and cleanup still execute.
        body = vm.definitions["eu5ab_governor_prepare_planned_baseline_core"]
        body = [(k, op, [(a, b, "0" if a == "count" else c) for a, b, c in v] if k == "while" else v)
                for k, op, v in body]
        vm.definitions["eu5ab_governor_prepare_planned_baseline_core"] = body
        vm.call("eu5ab_governor_prepare_planned_baseline")
        self.assertTrue(vm.vars[vm.ROOT]["eu5ab_governor_baseline_failed"])
        self.assertTrue(vm.vars[vm.ROOT]["eu5ab_governor_queue_exhausted"])
        vm.vars[3]["eu5ab_local_score"] = 100
        vm.call("eu5ab_governor_rank_local_results")
        self.assertNotIn("eu5ab_local_top_1", vm.vars[vm.ROOT])
        self.assertNotIn("eu5ab_gov_queue_head", vm.vars[vm.ROOT])
        self.assertTrue(all("eu5ab_gov_in_queue" not in variables for variables in vm.vars.values()))

    def test_exhausted_candidate_cannot_publish_its_partial_positive_score(self):
        vm = TransportScriptVM(nodes=(1, 2, 3, 4), capital=4, advances={"railroad_advance"})
        vm.prepare()
        vm.call("eu5ab_governor_prepare_planned_baseline")
        # Preserve the generated queue and arithmetic; reduce only the test's
        # candidate work budget so a positive but incomplete footprint remains.
        def zero_budget(entries):
            return [(k, op, [(a, b, "0" if a == "count" else zero_budget(c) if isinstance(c, list) else c)
                             for a, b, c in v] if k == "while"
                            else zero_budget(v) if isinstance(v, list) else v)
                    for k, op, v in entries]
        vm.definitions["eu5ab_governor_evaluate_candidate"] = zero_budget(vm.definitions["eu5ab_governor_evaluate_candidate"])
        vm.at("eu5ab_governor_evaluate_local_candidate", 1)
        self.assertGreater(vm.vars[1]["eu5ab_local_score"], 0)
        self.assertTrue(vm.vars[vm.ROOT]["eu5ab_governor_queue_exhausted"])
        vm.call("eu5ab_governor_rank_local_results")
        self.assertNotIn("eu5ab_local_top_1", vm.vars[vm.ROOT])


if __name__ == "__main__":
    unittest.main()
