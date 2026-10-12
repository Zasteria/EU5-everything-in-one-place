import unittest
from io import StringIO
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest.mock import patch

from scripts.validate_governor_save import (
    SaveSnapshot,
    build_attributed_source_values,
    completed_building_locations,
    excluded_building_locations,
    parse_save,
    source_building_summary,
    validate,
)


def parse_text(text):
    # Exercise the complete streaming parser without relying on the host's
    # temporary-directory ACLs or writing a synthetic save beside real saves.
    with patch.object(Path, "open", return_value=StringIO(text)):
        return parse_save(Path("synthetic-fixture.eu5"))


def runtime_block(entries, *, indent=3):
    """Serialize the actual typed variables/data entry nesting used by EU5."""
    prefix = "\t" * indent
    rows = [prefix + "variables={", prefix + "\tdata={ {"]
    for index, (name, kind, fields) in enumerate(entries):
        if index:
            rows.append(prefix + "\t\t} {")
        rows.extend((prefix + "\t\t\tflag=" + name, prefix + "\t\t\tdata={"))
        if kind is not None:
            rows.append(prefix + "\t\t\t\ttype=" + kind)
        rows.extend(prefix + "\t\t\t\t" + line for line in fields.splitlines())
        rows.append(prefix + "\t\t\t}")
    rows.extend((prefix + "\t\t} }", prefix + "}"))
    return "\n".join(rows) + "\n"


def parse_fixture(buildings="", constructions="", *, version="1.3.11"):
    text = (
        f'date=1429.3.1\nversion="{version}"\nprevious_played={{ {{\n\tidtype=764\n'
        f'construction_manager={{\n{constructions}\n}}\nbuilding_manager={{\n{buildings}\n}}\n'
        'locations={\n\t\t1={\n\t\t\towner=764\n\t\t}\n'
        '\t\t2={\n\t\t\towner=764\n\t\t}\ndisease_outbreak_manager={\n'
    )
    return parse_text(text)


def building_record(*, id=10, kind="local_governor", location=1, level=None, owner=764):
    level_text = "" if level is None else f"\tlevel={level}\n"
    return f"{id}={{\n\ttype={kind}\n\tlocation={location}\n\towner={owner}\n{level_text}}}\n"


def construction_record(*, id=20, building=10, kind="local_governor", location=1,
                        country=764, progress="146.54395", total="365"):
    return (f"{id}={{\n\ttype=CIVIL\n\tbuilding={building}\n\tlocation={location}\n"
            f"\tcountry={country}\n\tdemand={kind}_construction\n"
            f"\tprogress={progress}\n\ttotal={total}\n}}\n")


class GovernorSaveValidatorTests(unittest.TestCase):
    def test_typed_runtime_values_scopes_and_nested_payloads_are_isolated(self):
        entries = [
            ("eu5ab_positive", "value", "identity=34097914"),
            ("eu5ab_unsigned_negative", "value", "identity=18446744073709501616"),
            ("eu5ab_signed_negative", "value", "identity=-25000"),
            ("eu5ab_negative_smallest_unit", "value", "identity=18446744073709551615"),
            ("eu5ab_zero", "value", ""),
            ("eu5ab_true", "boolean", "identity=1"),
            ("eu5ab_false", "boolean", "identity=0"),
            ("eu5ab_scope", "loc", "location=8763"),
            ("eu5ab_ui_description", "flag", 'flag="eu5ab_quoted_ui_payload"'),
            ("eu5ab_list", "list", 'values={ {\n\tidentity=999990000\n\tflag=eu5ab_nested_list_entry\n\tdata={\n\t\ttype=value\n\t\tidentity=888880000\n\t}\n} }'),
            ("eu5ab_missing_type", None, "identity=100000"),
            ("eu5ab_missing_type_and_identity", None, ""),
            ("eu5ab_unknown_type", "unknown", "identity=100000"),
            ("eu5ab_invalid_number", "value", "identity=nan"),
            ("eu5ab_out_of_range", "value", "identity=18446744073709551616"),
            ("eu5ab_invalid_boolean", "boolean", "identity=-1"),
            ("eu5ab_unknown_boolean", "boolean", ""),
            ("eu5ab_after_list", "value", "identity=123456"),
        ]
        text = ('date=1435.5.20\nversion="1.3.11"\nprevious_played={ {\n\tidtype=764\n'
                'countries={\n764={\n\tcapital=1\n' + runtime_block(entries, indent=1)
                + '\tui={\n\t\t\t\tflag=eu5ab_outside_variables\n'
                  '\t\t\t\tdata={\n\t\t\t\t\ttype=value\n\t\t\t\t\tidentity=555550000\n\t\t\t\t}\n\t}\n'
                  '}\nmarket_manager={\n}\nlocations={\n\t\t1={\n\t\t\towner=764\n'
                + runtime_block(entries, indent=3)
                + '\t\t\tidentity=666660000\n\t\t}\ndisease_outbreak_manager={\n')
        snapshot = parse_text(text)
        expected = {
            "eu5ab_positive": 340.97914,
            "eu5ab_unsigned_negative": -.5,
            "eu5ab_signed_negative": -.25,
            "eu5ab_negative_smallest_unit": -.00001,
            "eu5ab_zero": 0,
            "eu5ab_true": 1,
            "eu5ab_false": 0,
            "eu5ab_after_list": 1.23456,
        }
        self.assertEqual(snapshot.country_runtime_variables[764], expected)
        self.assertEqual(snapshot.locations[1].runtime_variables, expected)
        self.assertEqual(snapshot.country_runtime_scope_variables[764], {"eu5ab_scope": 8763})
        self.assertEqual(snapshot.locations[1].runtime_scope_variables, {"eu5ab_scope": 8763})

    def test_untyped_flat_variable_lookalikes_are_not_guessed(self):
        text = ('previous_played={ {\n\tidtype=764\nlocations={\n\t\t1={\n'
                '\t\t\towner=764\n\t\t\tflag=eu5ab_untyped\n\t\t\tidentity=100000\n'
                '\t\t}\ndisease_outbreak_manager={\n')
        self.assertEqual(parse_text(text).locations[1].runtime_variables, {})

    def test_plaintext_file_entrypoint(self):
        text = ('date=1429.3.1\nversion="1.3.11"\nprevious_played={ {\n\tidtype=764\n'
                'locations={\n\t\t1={\n\t\t\towner=764\n\t\t}\ndisease_outbreak_manager={\n')
        with TemporaryDirectory(prefix="eu5ab-save-file-test-") as directory:
            path = Path(directory) / "fixture.eu5"
            path.write_text(text, encoding="utf-8-sig")
            snapshot = parse_save(path)
        self.assertEqual(snapshot.player_country_id, 764)
        self.assertEqual(snapshot.locations[1].owner, 764)

    def test_attributed_source_map_preserves_overlapping_raw_sources(self):
        snapshot = SaveSnapshot(
            capitals={764: 1},
            buildings={
                "local_governor": {1, 2, 99},
                "naval_governor": {2},
                "lieutenancy": {3},
                "seljuk_mint": {3},
            },
            building_levels={
                "local_governor": {1: 1, 2: 1, 99: 1},
                "naval_governor": {2: 1}, "lieutenancy": {3: 1},
                "seljuk_mint": {3: 3},
            },
        )

        self.assertEqual(
            build_attributed_source_values(snapshot, {1, 2, 3}, 1),
            {1: 180.0, 2: 160.0, 3: 135.0},
        )

    def test_population_fallback_and_runtime_fixed_point_variables(self):
        save_text = """date=1374.7.1
version=\"1.0\"
player_country_name=\"China\"
previous_played={ {
\tidtype=764
locations={
\t\t1={
\t\t\towner=764
\t\t\trank=city
\t\t\tdevelopment=23
\t\t\tcontrol=0.42
\t\t\troad_to_capital=yes
\t\t\tproximity=2.76888
\t\t\t\t\tnobles={
\t\t\t\t\t\tpopulation_ratio=1.34568
\t\t\t\t\t}
\t\t\t\t\tpeasants={
\t\t\t\t\t\tunemployed=112.2054
\t\t\t\t\t\temployed_in_rgo=4.25
\t\t\t\t\t}
__VARIABLES__
\t\t}
disease_outbreak_manager={
"""
        save_text = save_text.replace("__VARIABLES__\n", runtime_block([
            ("eu5ab_gov_node_value", "value", "identity=34097914"),
            ("eu5ab_gov_cached_population", "value", "identity=11780108"),
            ("eu5ab_gov_cached_potential_tax_base", "value", "identity=1900000"),
            ("eu5ab_gov_edge_cost_factor", "value", "identity=125000"),
        ]))
        snapshot = parse_text(save_text)

        location = snapshot.locations[1]
        self.assertEqual(snapshot.player_country_id, 764)
        self.assertAlmostEqual(location.population, 117.80108)
        self.assertAlmostEqual(
            location.runtime_variables["eu5ab_gov_node_value"], 340.97914
        )
        self.assertAlmostEqual(
            location.runtime_variables["eu5ab_gov_cached_population"], 117.80108
        )
        self.assertAlmostEqual(
            location.runtime_variables["eu5ab_gov_cached_potential_tax_base"], 19
        )
        self.assertAlmostEqual(
            location.runtime_variables["eu5ab_gov_edge_cost_factor"], 1.25
        )

    def test_first_level_construction_occupies_but_does_not_source(self):
        snapshot = parse_fixture(
            building_record() + building_record(id=11, location=2, level=1),
            construction_record(),
        )
        self.assertEqual(snapshot.building_state_issues, [])
        self.assertEqual(completed_building_locations(snapshot, "local_governor"), {2})
        self.assertEqual(snapshot.buildings_under_construction["local_governor"], {1})
        self.assertEqual(excluded_building_locations(snapshot, "local_governor"), {1, 2})
        self.assertEqual(build_attributed_source_values(snapshot, {1, 2}, None), {2: 80})
        self.assertEqual(source_building_summary(snapshot, {1, 2})["local_governor"], {
            "completed": 1, "construction_locations": 1,
            "known_occupied_locations": 2, "unknown_locations": 0,
        })

    def test_explicit_zero_is_not_a_completed_source_or_seat(self):
        for pending in (False, True):
            with self.subTest(pending=pending):
                snapshot = parse_fixture(building_record(level=0), construction_record(progress="0") if pending else "")
                self.assertEqual(snapshot.building_state_issues, [])
                self.assertEqual(build_attributed_source_values(snapshot, {1}, None), {})
                self.assertEqual(completed_building_locations(snapshot, "local_governor"), set())
                self.assertEqual(excluded_building_locations(snapshot, "local_governor"), {1} if pending else set())

    def test_completed_mint_levels_remain_during_upgrade(self):
        for level, expected in ((0, 0), (3, 60), (4, 80)):
            with self.subTest(level=level):
                snapshot = parse_fixture(building_record(kind="seljuk_mint", level=level),
                                         construction_record(kind="seljuk_mint") if level < 4 else "")
                self.assertEqual(snapshot.building_state_issues, [])
                self.assertEqual(build_attributed_source_values(snapshot, {1}, None), {1: expected} if expected else {})

    def test_upgrade_and_duplicate_project_do_not_double_occupancy(self):
        # Synthetic parsing case; does not assert that Local Governor upgrades
        # are legal in vanilla (its max_levels is 1).
        project = construction_record()
        snapshot = parse_fixture(building_record(level=1), project + project)
        self.assertEqual(build_attributed_source_values(snapshot, {1}, None), {1: 80})
        state = source_building_summary(snapshot, {1})["local_governor"]
        self.assertEqual(state["completed"], 1)
        self.assertEqual(state["construction_locations"], 1)
        self.assertEqual(state["known_occupied_locations"], 1)

    def test_missing_levels_require_the_verified_format_and_link(self):
        cases = (
            (building_record(), "", "1.3.11"),
            (building_record(), construction_record(), "1.0"),
            (building_record(kind="seljuk_mint"), construction_record(kind="seljuk_mint"), "1.3.11"),
            (building_record(level="invalid"), construction_record(), "1.3.11"),
            (building_record(level=-1), construction_record(), "1.3.11"),
        )
        for buildings, projects, version in cases:
            with self.subTest(buildings=buildings, version=version):
                snapshot = parse_fixture(buildings, projects, version=version)
                self.assertTrue(snapshot.building_state_issues)
                with self.assertRaisesRegex(ValueError, "uncertain"):
                    build_attributed_source_values(snapshot, {1}, None)

    def test_unreliable_construction_links_are_unknown_not_phantom_occupancy(self):
        for kwargs in ({"building": 999}, {"location": 2}, {"country": 99},
                       {"kind": "mason"}, {"progress": "365"}, {"progress": "nan"},
                       {"progress": "-1"}, {"total": "0"}):
            with self.subTest(kwargs=kwargs):
                snapshot = parse_fixture(building_record(), construction_record(**kwargs))
                self.assertTrue(snapshot.building_state_issues)
                self.assertEqual(source_building_summary(snapshot, {1, 2})["local_governor"]["known_occupied_locations"], 0)
                self.assertIn(1, excluded_building_locations(snapshot, "local_governor"))
                with self.assertRaises(ValueError):
                    build_attributed_source_values(snapshot, {1, 2}, None)

    def test_orphan_construction_is_reported_without_fabricating_a_building(self):
        snapshot = parse_fixture(constructions=construction_record())
        self.assertEqual(snapshot.buildings_under_construction, {})
        self.assertEqual(excluded_building_locations(snapshot, "local_governor"), {1})
        with self.assertRaises(ValueError):
            build_attributed_source_values(snapshot, {1}, None)

    def test_conflicting_duplicate_links_fail_closed_even_with_wrong_demand(self):
        snapshot = parse_fixture(
            building_record() + building_record(id=11, location=2, level=1),
            construction_record() + construction_record(building=11, location=2, kind="mason"),
        )
        self.assertTrue(any(issue.location == 2 for issue in snapshot.building_state_issues))
        with self.assertRaises(ValueError):
            build_attributed_source_values(snapshot, {2}, None)

    def test_duplicate_building_record_cannot_double_the_source(self):
        record = building_record(level=1)
        snapshot = parse_fixture(record + record)
        self.assertEqual(build_attributed_source_values(snapshot, {1}, None), {1: 80})
        snapshot = parse_fixture(record + building_record(level=0))
        with self.assertRaises(ValueError):
            build_attributed_source_values(snapshot, {1}, None)

    def test_nested_fields_and_demand_activity_do_not_override_root_fields(self):
        record = building_record(level=1).replace("\tlevel=1\n", "\tlevel=1\n\tmaintenance={\n\t\tlevel=0\n\t\tlocation=99\n\t}\n")
        project = construction_record().replace("\tprogress=", "\thas_active_demand=no\n\tprogress=")
        snapshot = parse_fixture(record, project)
        self.assertEqual(build_attributed_source_values(snapshot, {1}, None), {1: 80})
        self.assertEqual(snapshot.buildings_under_construction["local_governor"], {1})

    def test_source_ownership_keeps_existing_owned_location_rule(self):
        snapshot = parse_fixture(building_record(level=1, owner=99))
        self.assertEqual(build_attributed_source_values(snapshot, {1}, None), {1: 80})
        self.assertEqual(build_attributed_source_values(snapshot, {2}, None), {})

    def test_unknown_owned_source_stops_model_and_report_writes(self):
        snapshot = parse_fixture(building_record())
        with patch("scripts.validate_governor_save.parse_save", return_value=snapshot), \
             patch("scripts.validate_governor_save.resolve_game_layer", return_value=Path("unused")), \
             patch("scripts.validate_governor_save.parse_location_templates", return_value=({}, {})), \
             patch("scripts.validate_governor_save.parse_ports", return_value=set()), \
             patch("scripts.validate_governor_save.build_owned_adjacency") as graph, \
             patch.object(Path, "write_text") as write, patch("builtins.print"):
            self.assertEqual(validate(Path("unused.eu5"), Path("unused"), "mixed", layout_report=Path("unused.json")), 2)
            graph.assert_not_called()
            write.assert_not_called()


if __name__ == "__main__":
    unittest.main()
