"""Strict test interpreter for the planner's actual generated effects.

Not an EU5 emulator: engine topology/values are injected, but branching,
scopes, lists, queue state, and arithmetic execute from generated text. Unknown
operations fail. Temporary scopes are discarded at every external GUI pulse.
"""

import math
from numbers import Number
import re

from src.eu5autobuild.governor_generator import render_governor_effects
from src.eu5autobuild.governor_model import _edge_cost, location_value


def parse(text):
    text = re.sub(r"#[^\n]*", "", text)
    tokens = re.findall(r'"[^"\n]*"|>=|<=|!=|\?=|[{}=<>]|[^\s{}=<>!?]+', text)
    cursor = 0

    def block(nested=False):
        nonlocal cursor
        entries = []
        while cursor < len(tokens):
            if tokens[cursor] == "}":
                if not (nested):
                    raise AssertionError("Unsupported script input: nested")
                cursor += 1
                return entries
            key, operator = tokens[cursor : cursor + 2]
            key = key.strip('"')
            if operator not in ("=", ">", "<", ">=", "<=", "!=", "?="):
                raise AssertionError((key, operator))
            cursor += 2
            if tokens[cursor] == "{":
                cursor += 1
                value = block(True)
            else:
                value = tokens[cursor].strip('"')
                cursor += 1
            entries.append((key, operator, value))
        if not (not nested):
            raise AssertionError("Unsupported script input: not nested")
        return entries

    return block()


def substitute(entries, parameters):
    def word(value):
        for key, argument in parameters.items():
            value = value.replace(f"${key}$", argument)
        return value
    return [(word(k), op, substitute(v, parameters) if isinstance(v, list) else word(v))
            for k, op, v in entries]


class GovernorScriptVM:
    ROOT = "country"

    def __init__(self, locations, neighbors, roads, sources, old, candidates, capital):
        self.locations, self.neighbors, self.roads = locations, neighbors, roads
        self.sources, self.old, self.candidates, self.capital = (
            sources,
            set(old),
            set(candidates),
            capital,
        )
        self.vars = {entity: {} for entity in [self.ROOT, *locations]}
        self.lists = {entity: {} for entity in self.vars}
        self.maps = {entity: {} for entity in self.vars}
        self.vars[self.ROOT]["eu5ab_global_governor_recommendations_enabled"] = 1
        self.vars[self.ROOT]["eu5ab_global_governor_migration_enabled"] = 1
        self.vars[self.ROOT]["eu5ab_global_governor_relocation_enabled"] = 1
        self.vars[self.ROOT]["eu5ab_gov_transport_schema"] = 2
        self.vars[self.ROOT]["eu5ab_planner_schema"] = 4
        self.vars[self.ROOT]["eu5ab_gov_transport_road_tier"] = 0
        self.highest_road_tier = 0
        self.topographies = {}
        self.naval_old, self.naval_candidates = set(), set()
        self.owners = {n: self.ROOT for n in locations}
        self.definitions = {k: v for k, _, v in parse(render_governor_effects())}
        self.alerts = set()
        self.alert_actions = []
        self.cmm_settings = {}
        self.calls = []
        self.naval_calls = []
        self.special_edges = set()
        self.local = {}
        self.scopes = {}
        self.operations = 0
        self.location_keys = {node: str(node) for node in locations}

    def target(self, word, stack):
        if word == "root":
            return self.ROOT
        if word == "prev":
            return stack[-2] if len(stack) > 1 else self.ROOT
        if word == "this":
            return stack[-1]
        if word in ("capital", "owner.capital"):
            return self.capital
        if word == "owner":
            return self.owners.get(stack[-1])
        if word.startswith("scope:"):
            return self.scopes.get(word[6:])
        if word.startswith("var:"):
            return self.vars[stack[-1]].get(word[4:])
        if word.startswith("location:"):
            return next(node for node, key in self.location_keys.items() if key == word[9:])
        raise AssertionError(f"Unknown scope {word}")

    def value(self, x, stack):
        if isinstance(x, list):
            value = 0
            matched = False
            for k, _, v in x:
                if k in ("if", "else_if", "else"):
                    if k == "if":
                        matched = False
                    condition = next((body for name, _, body in v if name == "limit"), [])
                    if not matched and (k == "else" or self.condition(condition, stack)):
                        body = [entry for entry in v if entry[0] != "limit"]
                        value = self.value([("value", "=", str(value)), *body], stack)
                        matched = True
                elif k == "value":
                    value = self.value(v, stack)
                elif k == "add":
                    value += self.value(v, stack)
                elif k == "subtract":
                    value -= self.value(v, stack)
                elif k == "multiply":
                    value *= self.value(v, stack)
                elif k == "divide":
                    value /= self.value(v, stack)
                elif k == "min":
                    value = max(value, self.value(v, stack))
                elif k == "max":
                    value = min(value, self.value(v, stack))
                elif k == "floor":
                    value = math.floor(value)
                elif k == "ceiling":
                    value = math.ceil(value)
                elif k == "round":
                    value = math.floor(value + 0.5)
                elif k.startswith("scope:"):
                    target = self.target(k, stack)
                    if target is None:
                        raise AssertionError(f"Missing arithmetic scope {k}")
                    value = self.value([("value", "=", str(value)), *v], stack + [target])
                else:
                    raise AssertionError(f"Unknown arithmetic {k}")
            return value
        if x == "yes":
            return True
        if x.startswith("flag:"):
            return x
        if x == "no":
            return False
        try:
            return float(x)
        except (ValueError, TypeError):
            pass
        if x.startswith("local_var:"):
            return self.local[x[10:]]
        if x.startswith("variable_map("):
            name, key = x[len("variable_map("):-1].split("|", 1)
            return self.maps[stack[-1]].get(name, {}).get(self.value(key, stack))
        if ".var:" in x:
            scope, variable = x.split(".var:", 1)
            return self.vars[self.target(scope, stack)].get(variable)
        if x.startswith("var:"):
            return self.vars[stack[-1]].get(x[4:])
        if x == "num_locations":
            return sum(o == self.ROOT for o in self.owners.values())
        if x == "current_year":
            return getattr(self, 'year', 1410)
        if x == "current_month":
            return getattr(self, 'month_number', 5)
        if x == "current_day":
            return getattr(self, 'day', 2)
        if x == "modifier:local_proximity_source":
            return self.sources.get(stack[-1], 0)
        if x == "eu5ab_governor_highest_road_tier":
            return self.highest_road_tier
        if x in (
            "root",
            "prev",
            "this",
            "capital",
            "owner",
            "owner.capital",
        ) or x.startswith(("scope:", "location:")):
            return self.target(x, stack)
        if x in ("eu5ab_naval_planner_land_edge_prediction", "eu5ab_naval_planner_actual_land_edge_prediction"):
            origin = self.scopes["eu5ab_naval_gov_edge_from"]
            cost = _edge_cost(self.locations[stack[-1]], self.roads.get(frozenset((origin, stack[-1]))),
                              base_road_cost=20, base_land_cost=40)
            return max(0, self.vars[origin]["eu5ab_naval_gov_predicted"] - cost)
        if x == "eu5ab_naval_planner_highest_road_tier":
            return self.highest_road_tier
        if x in ("eu5ab_governor_current_proximity_source", "eu5ab_naval_planner_current_proximity_source"):
            return self.sources.get(stack[-1], 0)
        if x in (
            "eu5ab_governor_new_recommendation_threshold",
            "eu5ab_governor_layout_candidate_threshold",
            "eu5ab_governor_migration_absolute_threshold",
        ):
            factor = 2 if "migration_absolute" in x else 1
            threshold = max(
                factor,
                self.vars[self.ROOT]["eu5ab_governor_total_value"] * factor / 100,
            )
            return min(1000, threshold) if "new_recommendation" in x else threshold
        if x in ("eu5ab_governor_land_edge_prediction", "eu5ab_governor_known_land_edge_prediction",
                 "eu5ab_governor_actual_land_edge_prediction"):
            origin = self.scopes["eu5ab_gov_edge_from"]
            cost = _edge_cost(
                self.locations[stack[-1]],
                self.roads.get(frozenset((origin, stack[-1]))),
                base_road_cost=20,
                base_land_cost=40,
            )
            return max(0, self.vars[origin]["eu5ab_gov_predicted"] - cost)
        if x in ("eu5ab_governor_relocation_capacity", "eu5ab_naval_planner_relocation_capacity"):
            return getattr(self, "seat_capacity", len(self.old) + len(self.naval_old) + 4)
        if x in ("eu5ab_governor_relocation_occupied", "eu5ab_naval_planner_relocation_occupied"):
            return len(self.naval_old if "naval" in x else self.old)
        raise AssertionError(f"Unknown value {x}")

    def condition(self, entries, stack):
        return all(self.test(k, op, v, stack) for k, op, v in entries)

    def test(self, k, op, v, stack):
        if op == "=" and isinstance(v, list) and k.startswith(("var:", "local_var:")):
            if not (not any(a in ("value", "multiply", "add") for a, _, _ in v)):
                raise AssertionError(
                    "Variable equality blocks are scope triggers, not arithmetic expressions"
                )
        if k in ("OR", "AND", "NOT"):
            truths = [self.test(a, b, c, stack) for a, b, c in v]
            return (
                any(truths)
                if k == "OR"
                else (not all(truths) if k == "NOT" else all(truths))
            )
        if k == "has_variable":
            return v in self.vars[stack[-1]]
        if k == "has_variable_map":
            return bool(self.maps.get(stack[-1], {}).get(v))
        if k == "trigger_if":
            limit = next(body for name, _, body in v if name == "limit")
            return not self.condition(limit, stack) or self.condition(
                [entry for entry in v if entry[0] != "limit"], stack)
        if k == "is_key_in_variable_map":
            data = dict((a, c) for a, _, c in v)
            return data["target"] in self.maps[stack[-1]].get(data["name"], {})
        if k in ("is_human", "is_ownable"):
            return v == "yes"
        if k == "topography":
            return self.topographies.get(stack[-1]) == v
        if k == "is_capital":
            return (stack[-1] == self.capital) == (v == "yes")
        if k == "has_building":
            if v == "building_type:naval_governor":
                return stack[-1] in self.naval_old
            if not (v == "building_type:local_governor"):
                raise AssertionError(
                    'Unsupported script input: v == "building_type:local_governor"'
                )
            return stack[-1] in self.old
        if k == "eu5ab_local_governor_candidate":
            return stack[-1] in self.candidates and stack[-1] not in self.old
        if k == "eu5ab_naval_governor_candidate":
            return stack[-1] in self.naval_candidates and stack[-1] not in self.naval_old
        if k == "eu5ab_is_strait_connection_to":
            destination = self.value(dict((a, c) for a, _, c in v)["target"], stack)
            return frozenset((stack[-1], destination)) in self.special_edges
        if k == "is_target_in_variable_list":
            data = {a: c for a, _, c in v}
            return self.value(data["target"], stack) in self.lists[stack[-1]].get(data["name"], [])
        if (
            isinstance(v, list)
            and (not v or v[0][0] != "value")
            and (k in ("root", "prev", "capital") or k.startswith(("var:", "scope:")))
        ):
            target = self.target(k, stack)
            return target is not None and self.condition(v, stack + [target])
        left, right = self.value(k, stack), self.value(v, stack)
        if op == "?=":
            return left is not None and right is not None and left == right
        # An unset scope is never a valid numeric comparison operand, including
        # equality/inequality. Do not let None == None or None != 0 pass a gate.
        if left is None or right is None:
            return False
        if op == "=":
            return left == right
        if op == "!=":
            return left != right
        return {
            ">": lambda: left > right,
            "<": lambda: left < right,
            ">=": lambda: left >= right,
            "<=": lambda: left <= right,
        }[op]()

    def call(self, name):
        self.local, self.scopes = {}, {}
        self.operations = 0
        self.execute(self.definitions[name], [self.ROOT])

    def execute(self, entries, stack):
        matched = False
        for k, _, v in entries:
            self.operations += 1
            if not (self.operations < 500000):
                raise AssertionError("Runaway single-pulse work")
            data = dict((a, c) for a, _, c in v) if isinstance(v, list) else {}
            if k in ("if", "else_if", "else"):
                if k == "if":
                    matched = False
                if not matched and (
                    k == "else" or self.condition(data["limit"], stack)
                ):
                    self.execute([e for e in v if e[0] != "limit"], stack)
                    matched = True
                continue
            if k.startswith(
                (
                    "set_variable",
                    "change_variable",
                    "set_local_variable",
                    "change_local_variable",
                )
            ):
                local = "local" in k
                variables = self.local if local else self.vars[stack[-1]]
                name = data["name"] if data else v
                if k.startswith("set"):
                    variables[name] = self.value(data["value"], stack) if data else True
                else:
                    # EU5 cannot change an unset variable. Fail loudly instead
                    # of creating a zero and masking missing initialization.
                    if name not in variables:
                        raise AssertionError(f"{k} used on unset {name} in {stack[-1]}")
                    if not isinstance(variables[name], Number):
                        raise AssertionError(f"{k} used on nonnumeric {name} in {stack[-1]}")
                    expression = [("value", "=", str(variables[name]))] + [
                        e for e in v if e[0] != "name"
                    ]
                    variables[name] = self.value(expression, stack)
            elif k in ("remove_variable", "remove_local_variable"):
                (self.local if "local" in k else self.vars[stack[-1]]).pop(v, None)
            elif k == "clear_variable_list":
                self.lists[stack[-1]][v] = []
            elif k == "clear_variable_map":
                getattr(self, "maps", {}).get(stack[-1], {}).pop(v, None)
            elif k == "add_to_variable_map":
                self.maps.setdefault(stack[-1], {}).setdefault(data["name"], {})[self.value(data["key"], stack)] = self.value(data["value"], stack)
            elif k == "cmm_set_setting_value":
                # CMF 2.5 public write boundary. EU5AB registers country settings;
                # the setter stores a scalar and does not dispatch callbacks.
                assert set(data) == {"setting", "value"}
                assert isinstance(data["value"], str)
                self.maps.setdefault(stack[-1], {}).setdefault("cmm", {})[
                    "flag:" + data["setting"]] = self.value(data["value"], stack)
            elif k == "add_to_variable_list":
                self.lists[stack[-1]].setdefault(data["name"], []).append(
                    self.value(data["target"], stack)
                )
            elif k == "remove_list_variable":
                target = self.value(data["target"], stack)
                self.lists[stack[-1]][data["name"]] = [
                    item for item in self.lists[stack[-1]].get(data["name"], [])
                    if item != target
                ]
            elif k in ("save_temporary_scope_as", "save_scope_as"):
                self.scopes[v] = stack[-1]
            elif k == "save_scope_value_as":
                self.scopes[data['name']] = self.value(data['value'], stack)
            elif k in (
                "every_owned_location",
                "ordered_owned_location",
                "every_neighbor_location",
                "every_in_list",
                "ordered_in_list",
            ):
                if "owned" in k:
                    pool = sorted(n for n, o in self.owners.items() if o == self.ROOT)
                elif "neighbor" in k:
                    pool = sorted(self.neighbors.get(stack[-1], set()))
                else:
                    pool = list(self.lists[stack[-1]].get(data["variable"], []))
                pool = [
                    n
                    for n in pool
                    if self.condition(data.get("limit", []), stack + [n])
                ]
                if "ordered" in k:
                    pool.sort(
                        key=lambda n: self.value(data["order_by"], stack + [n]),
                        reverse=True,
                    )
                    pool = pool[
                        # Native ordered effects select one item unless max is explicit.
                        : int(self.value(data.get("max", "1"), stack))
                    ]
                body = [
                    e
                    for e in v
                    if e[0]
                    not in (
                        "limit",
                        "max",
                        "order_by",
                        "variable",
                        "check_range_bounds",
                    )
                ]
                for n in pool:
                    self.execute(body, stack + [n])
            elif k == "while":
                for _ in range(int(self.value(data["count"], stack))):
                    if not self.condition(data["limit"], stack):
                        break
                    self.execute(
                        [e for e in v if e[0] not in ("limit", "count")], stack
                    )
            elif k == "switch":
                selected = self.location_keys[stack[-1]] if data['trigger'] == 'location_key' else self.value(data['trigger'], stack)
                if isinstance(selected, (int, float)) and float(selected).is_integer():
                    selected = str(int(selected))
                self.execute(data.get(selected, data.get('fallback', [])), stack)
            elif k in ("cmf_show_alert", "cmf_remove_alert"):
                self.alert_actions.append((k, data["alert"]))
                if k == "cmf_show_alert":
                    self.alerts.add(data["alert"])
                else:
                    self.alerts.discard(data["alert"])
            elif k == "trigger_event_silently":
                if not (data["id"] in ("eu5ab_governor.2", "eu5ab_governor.3") and data["days"] == "1"):
                    raise AssertionError(data)
                events = "scheduled_naval_events" if data["id"] == "eu5ab_governor.3" else "scheduled_events"
                setattr(self, events, getattr(self, events, []) + [data.copy()])
            elif k in ("eu5ab_governor_refresh_other_recommendations", "eu5ab_naval_planner_refresh_other_recommendations"):
                (self.naval_calls if "naval_planner" in k else self.calls).append(k)
                # Only country transport bookkeeping is modeled here. Actual
                # scoring and native transport inputs have separate tests.
                p = "eu5ab_naval_gov_" if "naval_planner" in k else "eu5ab_gov_"
                self.vars[self.ROOT][p + "transport_schema"] = 2
                self.vars[self.ROOT][p + "transport_road_tier"] = self.highest_road_tier
            elif k in ("eu5ab_governor_refresh_begin", "eu5ab_naval_planner_refresh_begin"):
                # Layout-only fixtures inject recommendation inputs at this
                # boundary; TransportScriptVM executes the actual refresh job.
                naval = "naval_planner" in k
                prefix = "eu5ab_naval_planner_" if naval else "eu5ab_governor_"
                self.execute([(prefix + "refresh_other_recommendations", "=", "yes")], stack)
                root = self.vars[self.ROOT]
                if root.get("eu5ab_global_governor_relocation_enabled", 0) > 0 and (root.get("eu5ab_global_governor_migration_enabled", 0) > 0 or prefix + "manual_run" in root):
                    self.execute(self.definitions["eu5ab_naval_layout_begin" if naval else "eu5ab_layout_begin"], stack)
                else:
                    root.pop(prefix + "scan_active", None)
                    root.pop(prefix + "manual_run", None)
            elif k == "eu5ab_sync_cmm_settings":
                # External CMM boundary: saved settings are injected separately
                # from the governor's current mirrored variables.
                self.vars[self.ROOT].update(self.cmm_settings)
                # Execute the real post-sync policy too: omitting it hid bugs
                # where the callback erased a just-completed manual result.
                self.execute(self.definitions["eu5ab_governor_apply_migration_settings"], stack)
            elif k in ("eu5ab_governor_snapshot_local_slot_state", "eu5ab_naval_planner_snapshot_naval_slots"):
                # Layout-only VM injects capacity; TransportScriptVM runs real counts.
                pass
            elif k in ("eu5ab_governor_prepare_location_value", "eu5ab_naval_planner_prepare_location_value"):
                node = self.locations[stack[-1]]
                p = "eu5ab_naval_gov_" if "naval_planner" in k else "eu5ab_gov_"
                self.vars[stack[-1]].update({p + "node_value": location_value(node), p + "cached_old_proximity": node.proximity})
                road = (None, "dirt_road", "paved_road", "modern_road", "railroad")[self.highest_road_tier]
                self.vars[stack[-1]][p + "planned_road_cost"] = _edge_cost(
                    node, road, base_road_cost=20, base_land_cost=40)
                total = "eu5ab_naval_planner_total_value" if "naval_planner" in k else "eu5ab_governor_total_value"
                self.vars[self.ROOT][total] += location_value(
                    node
                )
            elif k in self.definitions:
                self.execute(substitute(self.definitions[k], data) if data else self.definitions[k], stack)
            elif k in ("root", "prev", "capital") or k.startswith(("var:", "scope:")):
                target = self.target(k, stack)
                if not (target is not None):
                    raise AssertionError(k)
                self.execute(v, stack + [target])
            else:
                raise AssertionError(f"Unknown effect {k}")

    def finish(self, max_pulses=2000):
        pulses = 0
        while "eu5ab_governor_scan_active" in self.vars[self.ROOT]:
            if not (pulses < max_pulses):
                raise AssertionError(self.vars[self.ROOT])
            self.call("eu5ab_layout_tick")
            pulses += 1
        return pulses

    def rows(self):
        return [
            (n, v["eu5ab_layout_row_to"])
            for n, v in sorted(
                self.vars.items(),
                key=lambda item: item[1].get("eu5ab_layout_row_order", 1e9),
            )
            if "eu5ab_layout_row_to" in v
        ]
