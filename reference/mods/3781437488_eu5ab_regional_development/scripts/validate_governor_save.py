"""Validate Governor recommendation ranking against a plaintext EU5 save.

This is an offline diagnostic, not part of the in-game runtime.  It prefers
authoritative values and propagation inputs cached by the generated scripts,
then falls back to reconstructing missing values from the plaintext save.

Control is reported as a diagnostic and, when the save omits possible_tax, is
used only to reconstruct the pre-Control tax base. Recommendation gains are
scored from observable Proximity improvement because other active modifiers
also affect the eventual Max Control and Control outcome.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass, field, replace
import math
from pathlib import Path
import re
import sys
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from src.eu5autobuild.governor_model import (  # noqa: E402
    CandidateScore,
    LocationState,
    MigrationProposal,
    cheap_score,
    choose_migration,
    connected_components,
    evaluate_candidate,
    evaluate_naval_relocation_candidates,
    location_value,
    rank_local_candidates,
    rank_migration_pairs,
    rank_naval_components,
    propagate_proximity,
)
from src.eu5autobuild.governor_transport import (  # noqa: E402
    CountryTransportInputs, LocationTransportInputs, TransportContext,
    TransportInputError, TransportMode, ROAD_UNLOCKS, lake_edge_cost,
)


# Historical 1.3 replay only; 1.4 uses the complete saved raw modifier.
LEGACY_VANILLA_PROXIMITY_SOURCE_VALUES = {
    "local_governor": 80,
    "italian_administration_center": 80,
    "naval_governor": 80,
    "bulgarian_administration_center": 15,
    "lieutenancy": 75,
    "kings_manor": 20,
    "seljuk_mint": 20,
}
SOURCE_BUILDING_TYPES = tuple(
    LEGACY_VANILLA_PROXIMITY_SOURCE_VALUES
) + ("itinerant_court_seat", "ostrog")


LOCATION_START = re.compile(r"^\t\t(\d+)=\{$")
BUILDING_START = re.compile(r"^(\d+)=\{$")
TEMPLATE_LINE = re.compile(r"^(\w+)\s*=\s*\{(.*)\}\s*$")
FIELD = re.compile(r"^\t\t\t([a-z_]+)=(.+)$")


@dataclass(slots=True)
class RawLocation:
    id: int
    owner: int | None = None
    rank: str = ""
    development: float = 0.0
    control: float = 0.0
    road_to_capital: bool = False
    proximity: float = 0.0
    # Opaque engine cache retained for diagnostics only. It is neither the
    # per-edge cost nor a speed multiplier and must not drive propagation.
    local_proximity_propagation: float | None = None
    tax: float = 0.0
    possible_tax: float = 0.0
    estate_possible_tax: dict[str, float] = field(default_factory=dict)
    population: float = 0.0
    province: int | None = None
    runtime_variables: dict[str, float] = field(default_factory=dict)
    runtime_scope_variables: dict[str, int] = field(default_factory=dict)


@dataclass(slots=True)
class SourceBuilding:
    id: int
    building_type: str
    location: int
    owner: int | None
    completed_level: int | None
    level_omitted: bool = False


@dataclass(slots=True)
class BuildingConstruction:
    id: int
    building: int | None
    location: int | None
    country: int | None
    demand: str
    progress: float | None
    total: float | None


@dataclass(frozen=True, slots=True)
class BuildingStateIssue:
    building_type: str
    location: int | None
    country: int | None
    detail: str


@dataclass(slots=True)
class SaveSnapshot:
    date: str = ""
    version: str = ""
    player_country_name: str = ""
    player_country_id: int | None = None
    capitals: dict[int, int] = field(default_factory=dict)
    tax_rates: dict[int, dict[str, float]] = field(default_factory=dict)
    country_runtime_variables: dict[int, dict[str, float]] = field(default_factory=dict)
    country_runtime_scope_variables: dict[int, dict[str, int]] = field(default_factory=dict)
    locations: dict[int, RawLocation] = field(default_factory=dict)
    roads: dict[frozenset[int], str] = field(default_factory=dict)
    # Completed locations only. Record existence and construction are separate.
    buildings: dict[str, set[int]] = field(default_factory=dict)
    building_levels: dict[str, dict[int, int]] = field(default_factory=dict)
    source_buildings: dict[int, SourceBuilding] = field(default_factory=dict)
    building_constructions: dict[int, BuildingConstruction] = field(default_factory=dict)
    conflicting_project_buildings: set[int] = field(default_factory=set)
    buildings_under_construction: dict[str, set[int]] = field(default_factory=dict)
    unknown_buildings: dict[str, set[int]] = field(default_factory=dict)
    building_state_issues: list[BuildingStateIssue] = field(default_factory=list)


def _optional_int(value: str | None) -> int | None:
    try:
        return int(value) if value is not None else None
    except ValueError:
        return None


def _optional_float(value: str | None) -> float | None:
    try:
        number = float(value) if value is not None else None
        return number if number is not None and math.isfinite(number) else None
    except ValueError:
        return None


def _record_building_state(snapshot: SaveSnapshot, section: str, record: dict[str, str]) -> None:
    """Read only direct fields of source buildings and CIVIL projects."""
    record_id = int(record["id"])
    building_type = record.get("type", "")
    location = _optional_int(record.get("location"))
    if section == "building_manager":
        if building_type not in SOURCE_BUILDING_TYPES:
            return
        owner = _optional_int(record.get("owner"))
        if location is None:
            snapshot.building_state_issues.append(BuildingStateIssue(
                building_type, None, owner, f"building {record_id}: missing/invalid location"))
            return
        building = SourceBuilding(record_id, building_type, location, owner,
                                  _optional_int(record.get("level")), "level" not in record)
        previous = snapshot.source_buildings.get(record_id)
        if previous is not None and previous != building:
            for item in (previous, building):
                snapshot.building_state_issues.append(BuildingStateIssue(
                    item.building_type, item.location, item.owner,
                    f"building {record_id}: conflicting duplicate record"))
        else:
            snapshot.source_buildings[record_id] = building
    elif building_type == "CIVIL":
        construction = BuildingConstruction(
            record_id, _optional_int(record.get("building")), location,
            _optional_int(record.get("country")), record.get("demand", ""),
            _optional_float(record.get("progress")), _optional_float(record.get("total")))
        previous = snapshot.building_constructions.get(record_id)
        if previous is not None and previous != construction:
            # Keep both associations uncertain; never resolve a duplicate by
            # accepting whichever record happened to occur last in the save.
            for item in (previous, construction):
                if item.building is not None:
                    snapshot.conflicting_project_buildings.add(item.building)
                kind = item.demand.removesuffix("_construction")
                if kind in SOURCE_BUILDING_TYPES:
                    snapshot.building_state_issues.append(BuildingStateIssue(
                        kind, item.location, item.country,
                        f"construction {record_id}: conflicting duplicate record"))
        else:
            snapshot.building_constructions[record_id] = construction


def _resolve_building_states(snapshot: SaveSnapshot) -> None:
    linked: dict[int | None, list[BuildingConstruction]] = {}
    for project in snapshot.building_constructions.values():
        linked.setdefault(project.building, []).append(project)
        kind = project.demand.removesuffix("_construction")
        if kind in SOURCE_BUILDING_TYPES and project.building not in snapshot.source_buildings:
            snapshot.building_state_issues.append(BuildingStateIssue(
                kind, project.location, project.country,
                f"construction {project.id}: missing source building {project.building}"))

    for building in snapshot.source_buildings.values():
        kind, location = building.building_type, building.location
        if building.id in snapshot.conflicting_project_buildings:
            snapshot.building_state_issues.append(BuildingStateIssue(
                kind, location, building.owner,
                f"building {building.id}: linked construction has conflicting duplicate records"))
        projects = linked.get(building.id, [])
        valid = []
        for project in projects:
            if (project.location == location
                    and building.owner is not None and project.country == building.owner
                    and project.demand == f"{kind}_construction"
                    and project.progress is not None and project.total is not None
                    and 0 <= project.progress < project.total):
                valid.append(project)
            else:
                snapshot.building_state_issues.append(BuildingStateIssue(
                    kind, location, building.owner,
                    f"construction {project.id}: inconsistent or unsettled link to building {building.id}"))
                if project.location is not None and project.location != location:
                    snapshot.building_state_issues.append(BuildingStateIssue(
                        kind, project.location, project.country,
                        f"construction {project.id}: conflicting location"))
        ambiguous = any(issue.location == location and issue.building_type == kind
                        for issue in snapshot.building_state_issues)
        # Only the single-level 1.3.11 Local Governor case has been proven from
        # the original building/CIVIL pair. Do not generalize omitted levels.
        level = building.completed_level
        if (level is None and building.level_omitted and snapshot.version == "1.3.11"
                and kind == "local_governor" and len(valid) == 1
                and len(projects) == 1 and not ambiguous):
            level = 0
        if level is None or level < 0:
            snapshot.unknown_buildings.setdefault(kind, set()).add(location)
            snapshot.building_state_issues.append(BuildingStateIssue(
                kind, location, building.owner,
                f"building {building.id}: completed level is unknown"))
        else:
            levels = snapshot.building_levels.setdefault(kind, {})
            levels[location] = levels.get(location, 0) + level
            if level > 0:
                snapshot.buildings.setdefault(kind, set()).add(location)
        if valid and not ambiguous:
            snapshot.buildings_under_construction.setdefault(kind, set()).add(location)


def completed_building_locations(snapshot: SaveSnapshot, building_type: str) -> set[int]:
    return {location for location, level in snapshot.building_levels.get(building_type, {}).items()
            if level > 0}


def excluded_building_locations(
    snapshot: SaveSnapshot, building_type: str, *, include_construction: bool = True,
) -> set[int]:
    excluded = completed_building_locations(snapshot, building_type)
    if include_construction:
        excluded |= snapshot.buildings_under_construction.get(building_type, set())
    excluded |= snapshot.unknown_buildings.get(building_type, set())
    excluded |= {issue.location for issue in snapshot.building_state_issues
                 if issue.building_type == building_type and issue.location is not None}
    return excluded


def source_building_summary(snapshot: SaveSnapshot, owned_ids: set[int]) -> dict[str, dict[str, int]]:
    """Known occupancy only, not a reconstruction of the country's capacity."""
    result = {}
    for kind in ("local_governor", "naval_governor", "lieutenancy"):
        completed = completed_building_locations(snapshot, kind) & owned_ids
        pending = snapshot.buildings_under_construction.get(kind, set()) & owned_ids
        unknown = (excluded_building_locations(snapshot, kind) & owned_ids) - (completed | pending)
        result[kind] = dict(completed=len(completed), construction_locations=len(pending),
                            known_occupied_locations=len(completed | pending), unknown_locations=len(unknown))
    return result


def _owned_building_issues(snapshot: SaveSnapshot, owned_ids: set[int]) -> list[BuildingStateIssue]:
    return [issue for issue in snapshot.building_state_issues
            if issue.location in owned_ids
            or (issue.location is None and issue.country == snapshot.player_country_id)]


def _number(value: str, default: float = 0.0) -> float:
    try:
        return float(value.strip().strip('"'))
    except ValueError:
        return default


def _runtime_fixed_point(identity: str) -> float | None:
    """Decode EU5's signed 64-bit, five-decimal value without float rounding."""
    try:
        integer = int(identity)
    except ValueError:
        return None
    if not -(1 << 63) <= integer < (1 << 64):
        return None
    if integer >= (1 << 63):
        integer -= 1 << 64
    return integer / 100000.0


class _RuntimeVariableReader:
    """Read only direct entries in one country's/location's variables block.

    The save wraps each variable as ``flag=... data={type=...}``. Entry and
    payload indentation prevent a typed flag, location reference, nested list,
    or unrelated identity field from being consumed as the previous value.
    Unsupported or missing types are omitted, never assumed numeric.
    """

    def __init__(self, indent: int, numbers: dict[str, float], scopes: dict[str, int]):
        self.prefix = "\t" * indent
        self.entry_prefix = self.prefix + "\t\t\t"
        self.field_prefix = self.entry_prefix + "\t"
        self.numbers, self.scopes = numbers, scopes
        self.active = False
        self.name: str | None = None
        self.fields: dict[str, str] = {}
        self.in_data = False
        self.complete_data = False

    def _finish_entry(self) -> None:
        name = self.name
        if name is not None:
            self.numbers.pop(name, None)
            self.scopes.pop(name, None)
            kind = self.fields.get("type") if self.complete_data else None
            if kind == "value":
                # A typed zero value omits identity in actual EU5 saves.
                value = _runtime_fixed_point(self.fields.get("identity", "0"))
                if value is not None:
                    self.numbers[name] = value
            elif kind == "boolean" and self.fields.get("identity") in {"0", "1"}:
                self.numbers[name] = float(self.fields["identity"])
            elif kind == "loc":
                value = _optional_int(self.fields.get("location"))
                if value is not None and value >= 0:
                    self.scopes[name] = value
        self.name = None
        self.fields = {}
        self.in_data = self.complete_data = False

    def feed(self, line: str) -> bool:
        if not self.active:
            if line != self.prefix + "variables={":
                return False
            self.active = True
            return True
        if line == self.prefix + "}":
            self._finish_entry()
            self.active = False
            return True
        if line.startswith(self.prefix + "\t\t}"):
            self._finish_entry()
        elif line.startswith(self.entry_prefix + "flag="):
            self._finish_entry()
            name = line[len(self.entry_prefix + "flag="):].strip('"')
            if re.fullmatch(r"eu5ab_[A-Za-z0-9_.]+", name):
                self.name = name
        elif self.name is not None and line == self.entry_prefix + "data={":
            self.in_data = True
        elif self.in_data and line == self.entry_prefix + "}":
            self.in_data = False
            self.complete_data = True
        elif self.in_data and line.startswith(self.field_prefix) and not line.startswith(self.field_prefix + "\t"):
            field = line[len(self.field_prefix):]
            if "=" in field:
                key, value = field.split("=", 1)
                if key in {"type", "identity", "location"}:
                    self.fields[key] = value.strip('"')
        return True


def parse_save(path: Path) -> SaveSnapshot:
    snapshot = SaveSnapshot()
    in_roads = False
    road_from: int | None = None
    road_to: int | None = None
    building_section: str | None = None
    current_building: dict[str, str] | None = None
    in_countries = False
    current_country: int | None = None
    country_variables_reader: _RuntimeVariableReader | None = None
    country_depth = 0
    in_tax_rates = False
    in_estate_possible_tax = False
    in_locations = False
    current_location: RawLocation | None = None
    current_pop_type: str | None = None
    current_pop_ratio: float | None = None
    current_pop_fallback = 0.0
    location_variables_reader: _RuntimeVariableReader | None = None
    previous_played = False

    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        for raw_line in handle:
            line = raw_line.rstrip("\r\n")
            stripped = line.strip()
            if not snapshot.date and stripped.startswith("date="):
                snapshot.date = stripped.split("=", 1)[1]
            elif not snapshot.version and stripped.startswith("version="):
                snapshot.version = stripped.split("=", 1)[1].strip('"')
            elif not snapshot.player_country_name and stripped.startswith("player_country_name="):
                snapshot.player_country_name = stripped.split("=", 1)[1].strip('"')

            if line == "road_network={":
                in_roads = True
                continue
            if in_roads:
                if line == "}":
                    in_roads = False
                    continue
                if stripped.startswith("from="):
                    road_from = int(stripped.split("=", 1)[1])
                elif stripped.startswith("to="):
                    road_to = int(stripped.split("=", 1)[1])
                elif stripped.startswith("type=") and road_from is not None and road_to is not None:
                    snapshot.roads[frozenset((road_from, road_to))] = stripped.split("=", 1)[1]
                    road_from = None
                    road_to = None
                continue

            if line in {"building_manager={", "construction_manager={"}:
                building_section = line.split("=", 1)[0]
                current_building = None
                continue
            if building_section:
                if re.match(r"^[a-z_]+=\{", line):
                    building_section = None
                    current_building = None
                else:
                    match = BUILDING_START.match(line)
                    if match:
                        current_building = {"id": match.group(1)}
                    elif current_building is not None:
                        if line == "}":
                            _record_building_state(snapshot, building_section, current_building)
                            current_building = None
                        elif line.startswith("\t") and not line.startswith("\t\t") and "=" in stripped:
                            key, value = stripped.split("=", 1)
                            if key in {"type", "location", "owner", "level", "country",
                                       "building", "progress", "total", "demand"}:
                                current_building[key] = value
                    continue

            if line == "countries={":
                in_countries = True
                continue
            if in_countries:
                if line == "market_manager={":
                    in_countries = False
                elif current_country is None:
                    match = BUILDING_START.match(line)
                    if match:
                        current_country = int(match.group(1))
                        country_depth = 1
                        snapshot.country_runtime_variables[current_country] = {}
                        snapshot.country_runtime_scope_variables[current_country] = {}
                        country_variables_reader = _RuntimeVariableReader(
                            1, snapshot.country_runtime_variables[current_country],
                            snapshot.country_runtime_scope_variables[current_country])
                else:
                    country_depth += line.count("{") - line.count("}")
                    if country_variables_reader is not None:
                        country_variables_reader.feed(line)
                    if line.startswith("\tcapital="):
                        snapshot.capitals[current_country] = int(stripped.split("=", 1)[1])
                    if line == "\t\ttax_rates={":
                        in_tax_rates = True
                        snapshot.tax_rates[current_country] = {}
                    elif in_tax_rates:
                        if line == "\t\t}":
                            in_tax_rates = False
                        elif line.startswith("\t\t\t") and "=" in stripped:
                            estate, rate = stripped.split("=", 1)
                            snapshot.tax_rates[current_country][estate] = _number(rate, float("nan"))
                    if country_depth == 0:
                        country_variables_reader = None
                        current_country = None
                        in_tax_rates = False
                if in_countries:
                    continue

            if line == "locations={" and not in_locations:
                in_locations = True
                continue
            if in_locations:
                if line == "disease_outbreak_manager={":
                    in_locations = False
                else:
                    match = LOCATION_START.match(line)
                    if match:
                        current_location = RawLocation(int(match.group(1)))
                        in_estate_possible_tax = False
                        current_pop_type = None
                        current_pop_ratio = None
                        current_pop_fallback = 0.0
                        location_variables_reader = _RuntimeVariableReader(
                            3, current_location.runtime_variables, current_location.runtime_scope_variables)
                        continue
                    if current_location is not None:
                        if location_variables_reader is not None and location_variables_reader.feed(line):
                            continue
                        if line == "\t\t\testate_possible_tax={":
                            in_estate_possible_tax = True
                            continue
                        if in_estate_possible_tax:
                            if line == "\t\t\t}":
                                in_estate_possible_tax = False
                            elif line.startswith("\t\t\t\t") and "=" in stripped:
                                estate, amount = stripped.split("=", 1)
                                current_location.estate_possible_tax[estate] = _number(amount, float("nan"))
                            continue
                        pop_type_match = re.match(r"^\t{5}([a-z_]+)=\{$", line)
                        if pop_type_match:
                            current_pop_type = pop_type_match.group(1)
                            current_pop_ratio = None
                            current_pop_fallback = 0.0
                            continue
                        if current_pop_type is not None:
                            if line == "\t\t\t\t\t}":
                                current_location.population += (
                                    current_pop_ratio
                                    if current_pop_ratio is not None
                                    else current_pop_fallback
                                )
                                current_pop_type = None
                                current_pop_ratio = None
                                current_pop_fallback = 0.0
                                continue
                            if line.startswith("\t\t\t\t\t\t") and "=" in stripped:
                                pop_key, pop_value = stripped.split("=", 1)
                                if pop_key == "population_ratio":
                                    current_pop_ratio = _number(pop_value)
                                elif pop_key in {"unemployed", "employed_in_rgo"}:
                                    # Peasants commonly omit population_ratio.
                                    # Their explicit employment totals are the
                                    # only saved population quantity available.
                                    current_pop_fallback += _number(pop_value)
                        if line == "\t\t}":
                            snapshot.locations[current_location.id] = current_location
                            current_location = None
                            location_variables_reader = None
                            continue
                        field_match = FIELD.match(line)
                        if field_match:
                            key, value = field_match.groups()
                            if key == "owner":
                                current_location.owner = int(value)
                            elif key == "rank":
                                current_location.rank = value
                            elif key == "development":
                                current_location.development = _number(value)
                            elif key == "control":
                                current_location.control = _number(value)
                            elif key == "road_to_capital":
                                current_location.road_to_capital = value == "yes"
                            elif key == "proximity":
                                current_location.proximity = _number(value)
                            elif key == "local_proximity_propagation":
                                current_location.local_proximity_propagation = _number(
                                    value
                                )
                            elif key == "province":
                                current_location.province = int(value)
                            elif key == "tax":
                                current_location.tax = _number(value)
                            elif key == "possible_tax":
                                current_location.possible_tax = _number(value)
                    continue

            if line == "previous_played={ {":
                previous_played = True
            elif previous_played and stripped.startswith("idtype="):
                snapshot.player_country_id = int(stripped.split("=", 1)[1])
                previous_played = False

    if snapshot.player_country_id is None:
        raise ValueError("Could not identify the player country from previous_played")
    _resolve_building_states(snapshot)
    return snapshot


def parse_location_templates(path: Path) -> tuple[dict[int, str], dict[str, dict[str, str]]]:
    names: dict[int, str] = {}
    attributes: dict[str, dict[str, str]] = {}
    with path.open("r", encoding="utf-8-sig", errors="replace") as handle:
        for line in handle:
            match = TEMPLATE_LINE.match(line.strip())
            if not match:
                continue
            name, body = match.groups()
            location_id = len(names) + 1
            names[location_id] = name
            attributes[name] = dict(re.findall(r"([a-z_]+)\s*=\s*([\w.-]+)", body))
    return names, attributes


def parse_ports(path: Path) -> set[str]:
    ports: set[str] = set()
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        for row in csv.DictReader(handle, delimiter=";"):
            name = (row.get("LandProvince") or "").strip()
            if name:
                ports.add(name)
    return ports


def parse_colors(path: Path, name_to_id: dict[str, int], owned: set[int]) -> dict[int, int]:
    colors: dict[int, int] = {}
    pattern = re.compile(r"^(\w+)\s*=\s*([0-9a-fA-F]+)(?:\s*#.*)?$")
    with path.open("r", encoding="utf-8-sig", errors="replace") as handle:
        for line in handle:
            match = pattern.match(line.strip())
            if not match:
                continue
            name, hexadecimal = match.groups()
            location_id = name_to_id.get(name)
            if location_id in owned:
                colors[int(hexadecimal.zfill(6), 16)] = location_id
    return colors


def _add_numpy_pairs(graph: dict[int, set[int]], left, right, numpy) -> None:
    mask = (left != right) & (left > 0) & (right > 0)
    if not bool(mask.any()):
        return
    pairs = numpy.stack((left[mask], right[mask]), axis=1)
    pairs.sort(axis=1)
    for first, second in numpy.unique(pairs, axis=0):
        a, b = int(first), int(second)
        graph[a].add(b)
        graph[b].add(a)


def build_owned_adjacency(
    map_data: Path,
    names: dict[int, str],
    owned: set[int],
) -> tuple[dict[int, set[int]], set[frozenset[int]]]:
    try:
        import numpy
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError(
            "Map adjacency validation needs Pillow and NumPy; use the Codex bundled Python runtime."
        ) from exc

    name_to_id = {name: location_id for location_id, name in names.items()}
    colors = parse_colors(map_data / "named_locations" / "00_default.txt", name_to_id, owned)
    lookup = numpy.zeros(1 << 24, dtype=numpy.int32)
    for color, location_id in colors.items():
        lookup[color] = location_id
    graph = {location_id: set() for location_id in owned}
    Image.MAX_IMAGE_PIXELS = None
    image = Image.open(map_data / "locations.png").convert("RGB")
    width, height = image.size
    previous_row = None
    for top in range(0, height, 256):
        bottom = min(height, top + 256)
        rgb = numpy.asarray(image.crop((0, top, width, bottom)), dtype=numpy.uint32)
        encoded = (rgb[:, :, 0] << 16) | (rgb[:, :, 1] << 8) | rgb[:, :, 2]
        location_ids = lookup[encoded]
        _add_numpy_pairs(graph, location_ids[:, :-1], location_ids[:, 1:], numpy)
        _add_numpy_pairs(graph, location_ids[:, -1], location_ids[:, 0], numpy)
        if previous_row is not None:
            _add_numpy_pairs(graph, previous_row, location_ids[0], numpy)
        _add_numpy_pairs(graph, location_ids[:-1], location_ids[1:], numpy)
        previous_row = location_ids[-1].copy()

    special_edges: set[frozenset[int]] = set()
    with (map_data / "adjacencies.csv").open(
        "r", encoding="utf-8-sig", errors="replace", newline=""
    ) as handle:
        for row in csv.DictReader(handle, delimiter=";"):
            first = name_to_id.get((row.get("From") or "").strip())
            second = name_to_id.get((row.get("To") or "").strip())
            if first in owned and second in owned:
                graph[first].add(second)
                graph[second].add(first)
                special_edges.add(frozenset((first, second)))
    return graph, special_edges


def load_chinese_names(root: Path, wanted: Iterable[str]) -> dict[str, str]:
    wanted_set = set(wanted)
    translated: dict[str, str] = {}
    pattern = re.compile(r'^\s*([A-Za-z0-9_]+):\s*"([^"#]*)"')
    localization_root = root / "main_menu" / "localization" / "simp_chinese" / "location_names"
    for path in localization_root.glob("*.yml"):
        with path.open("r", encoding="utf-8-sig", errors="replace") as handle:
            for line in handle:
                match = pattern.match(line)
                if match and match.group(1) in wanted_set:
                    translated[match.group(1)] = match.group(2)
    return translated


def _format_candidate(
    rank: int,
    result: CandidateScore,
    locations: dict[int, LocationState],
    chinese: dict[str, str],
) -> str:
    location = locations[result.location_id]
    display = chinese.get(location.name, location.name)
    return (
        f"  {rank}. {display} ({location.name}, ID {location.id}) — "
        f"综合评分 {result.score:.2f} = 候选地点自身临近度代理收益 {result.site_gain:.2f} "
        f"+ 周边地点临近度代理收益 {result.surrounding_gain:.2f}；"
        f"覆盖 {result.covered_locations} 个地点（包括候选地点），"
        f"当前邻近度 {location.proximity:.2f}，当前控制力 {location.control:.1%}"
    )


def _optional_percent(value: float | None) -> str:
    return "不可从该存档复现" if value is None else f"{value:.2%}"


def _format_migration(
    proposal: MigrationProposal,
    locations: dict[int, LocationState],
    chinese: dict[str, str],
) -> str:
    current = locations[proposal.current_location_id]
    recommended = locations[proposal.recommended_location_id]
    current_name = chinese.get(current.name, current.name)
    recommended_name = chinese.get(recommended.name, recommended.name)
    return (
        f"{current_name} ({current.name}, ID {current.id}) → "
        f"{recommended_name} ({recommended.name}, ID {recommended.id})；"
        f"迁移前分 {proposal.current_score:.2f}，迁移后分 "
        f"{proposal.recommended_score:.2f}，全国加权邻近度净提升 "
        f"{proposal.net_gain:.2f}"
    )


def _print_contribution_diagnostics(
    result: CandidateScore,
    locations: dict[int, LocationState],
    chinese: dict[str, str],
) -> None:
    print("逐地点代理收益诊断：")
    print(
        "  location | old_proximity | candidate_proximity | effective_proximity | "
        "proximity_gain | old_control | old_max_control | new_max_control | "
        "max_control_gain | location_value | site_or_surrounding | final_contribution"
    )
    ordered = sorted(
        result.contributions,
        key=lambda item: (
            item.site_or_surrounding != "site",
            -item.final_contribution,
            item.location_id,
        ),
    )
    for item in ordered:
        location = locations[item.location_id]
        display = chinese.get(location.name, location.name)
        role = "候选地点自身" if item.site_or_surrounding == "site" else "周边地点"
        print(
            f"  {display}({item.location_id}) | {item.old_proximity:.4f} | "
            f"{item.candidate_proximity:.4f} | {item.effective_proximity:.4f} | "
            f"{item.proximity_gain:.4f} | {item.old_control:.2%} | "
            f"{_optional_percent(item.old_max_control)} | "
            f"{_optional_percent(item.new_max_control)} | "
            f"{_optional_percent(item.max_control_gain)} | "
            f"{item.location_value:.5f} | {role} | {item.final_contribution:.5f}"
        )
    print(
        "  说明：引擎没有提供以反事实临近度查询最大控制力的接口，"
        "因此 new_max_control 与 max_control_gain 不编造数值；"
        "final_contribution 是地点价值 × 新增临近度比例的代理收益。"
    )


def resolve_game_layer(game_root: Path) -> Path:
    """Accept either the EU5 install directory or its ``game`` layer."""

    for candidate in (game_root, game_root / "game"):
        if (candidate / "in_game" / "map_data" / "location_templates.txt").is_file():
            return candidate
    raise FileNotFoundError(
        "找不到 EU5 地图数据；--game-root 应指向 Europa Universalis V 安装目录或其 game 子目录"
    )


def build_attributed_source_values(
    snapshot: SaveSnapshot,
    owned_ids: set[int],
    capital: int | None,
) -> dict[int, float]:
    """Read the 1.4 raw runtime snapshot; preserve historical 1.3 replay only."""

    schema = snapshot.country_runtime_variables.get(snapshot.player_country_id, {}).get("eu5ab_planner_schema", 0)
    if schema >= 4 or re.match(r"1\.[4-9](?:\D|$)", snapshot.version):
        source_values = {}
        for node in sorted(owned_ids):
            raw = snapshot.locations.get(node)
            value = raw.runtime_variables.get("eu5ab_gov_snapshot_native_source") if raw else None
            if value is None or not math.isfinite(value):
                raise ValueError(f"Missing complete raw proximity source snapshot at {node}; refresh with the 1.4 Mod and save again")
            source_values[node] = value
        return source_values

    issues = _owned_building_issues(snapshot, owned_ids)
    if issues:
        raise ValueError("Source building state is uncertain: " + "; ".join(issue.detail for issue in issues))
    source_values: dict[int, float] = {}
    if capital in owned_ids:
        source_values[capital] = 100.0
    for building_id, source_strength in LEGACY_VANILLA_PROXIMITY_SOURCE_VALUES.items():
        for location_id in completed_building_locations(snapshot, building_id) & owned_ids:
            levels = (
                min(4, snapshot.building_levels[building_id][location_id])
                if building_id == "seljuk_mint"
                else 1
            )
            source_values[location_id] = (
                source_values.get(location_id, 0.0) + source_strength * levels
            )
    return source_values


LAKE_TOPOGRAPHIES = frozenset({"lakes", "high_lakes", "salt_pans"})


def build_transport_context(
    snapshot: SaveSnapshot,
    owned_ids: set[int],
    graph: dict[int, set[int]],
    special_edges: set[frozenset[int]],
    *,
    mode: str,
    lake_ids: set[int] | None = None,
) -> TransportContext | None:
    """Use explicit schema-2 engine-input caches, never invert old factors.

    All graph land nodes must be owned. Lakes are identified independently from
    the map templates and only form owned-land/lake/owned-land paths. Country
    and per-location inputs form the cached planning snapshot, not a promise
    that every live modifier has remained unchanged since its last refresh.
    """
    if mode not in {"legacy", "actual", "highest-unlocked"}:
        raise TransportInputError(f"Unknown transport mode: {mode}")
    variables = snapshot.country_runtime_variables.get(snapshot.player_country_id, {})
    schema = variables.get("eu5ab_gov_transport_schema")
    if mode == "legacy":
        if schema == 2:
            raise TransportInputError("Schema-2 factors cannot replay legacy semantics; select actual or highest-unlocked")
        return None
    if schema != 2:
        raise TransportInputError("New transport modes require eu5ab_gov_transport_schema=2; refresh with the repaired Mod and save again")

    def require(values, key, scope):
        value = values.get(key)
        if value is None or not math.isfinite(value):
            raise TransportInputError(f"Missing/invalid {scope} transport input: {key}")
        return value

    global_speed = require(variables, "eu5ab_gov_cached_global_speed", "country")
    land_speed = require(variables, "eu5ab_gov_cached_land_speed", "country")
    tier = require(variables, "eu5ab_gov_transport_road_tier", "country")
    if tier not in range(5):
        raise TransportInputError("Road tier must be an integer from 0 to 4")
    country = CountryTransportInputs(global_speed, land_speed, 0.0)
    inputs = {}
    for node in sorted(owned_ids):
        raw = snapshot.locations.get(node)
        if raw is None:
            raise TransportInputError(f"Missing location record: {node}")
        values = raw.runtime_variables
        inputs[node] = LocationTransportInputs(
            local_speed=require(values, "eu5ab_gov_cached_local_speed", f"location {node}"),
            topography=require(values, "eu5ab_gov_cached_topography", f"location {node}"),
            vegetation=require(values, "eu5ab_gov_cached_vegetation", f"location {node}"),
            topography_modifier=require(values, "eu5ab_gov_cached_topography_impact", f"location {node}"),
        )
    lake_ids = lake_ids or set()
    land_edges, non_land = set(), {}
    lake_base = require(variables, "eu5ab_gov_cached_lake_base", "country")
    for source, neighbors in graph.items():
        for target in neighbors:
            edge = frozenset((source, target))
            if edge in special_edges:
                continue
            if source in owned_ids and target in owned_ids:
                land_edges.add(edge)
            elif source in lake_ids and target in owned_ids:
                non_land[source, target] = lake_edge_cost(0.0, country, base_cost=lake_base)
            elif source in owned_ids and target in lake_ids:
                non_land[source, target] = lake_edge_cost(inputs[source].local_speed, country, base_cost=lake_base)
            else:
                raise TransportInputError(f"Unclassified or unsupported water edge: {source}->{target}")
    return TransportContext(
        country=country, locations=inputs, land_edges=frozenset(land_edges),
        mode=TransportMode(mode.replace("-", "_")),
        unlocked_advances=frozenset(advance for advance, _ in ROAD_UNLOCKS[:int(tier)]),
        buildable_land_edges=frozenset(land_edges), non_land_edge_costs=non_land,
        base_road_cost=require(variables, "eu5ab_gov_cached_road_base", "country"),
        base_land_cost=require(variables, "eu5ab_gov_cached_land_base", "country"),
    )


def validate(
    save_path: Path,
    game_root: Path,
    profile: str,
    inspect_location: str | None = None,
    layout_report: Path | None = None,
    tax_report: Path | None = None,
    tax_rate_overrides: dict[str, float] | None = None,
    transport_mode: str = "legacy",
) -> int:
    snapshot = parse_save(save_path)
    player = snapshot.player_country_id
    if player is None:
        raise ValueError("Save does not identify a player country")
    game_layer = resolve_game_layer(game_root)
    map_data = game_layer / "in_game" / "map_data"
    names, template_attributes = parse_location_templates(map_data / "location_templates.txt")
    ports = parse_ports(map_data / "ports.csv")
    owned_raw = {
        location_id: location
        for location_id, location in snapshot.locations.items()
        if location.owner == player
    }
    owned_ids = set(owned_raw)
    state_summary = source_building_summary(snapshot, owned_ids)
    issues = _owned_building_issues(snapshot, owned_ids)
    if issues:
        print("建筑完成 / 施工状态不确定，停止输出推荐和布局报告；请核对建筑等级与施工记录。")
        for issue in issues:
            print(f"  {issue.building_type} location={issue.location}: {issue.detail}")
        print(f"已确认建筑状态（占位不等于国家容量）：{state_summary}")
        return 2
    # Fail closed before constructing the map if the save cannot supply the
    # explicit engine-input snapshot required by the requested transport mode.
    try:
        build_transport_context(snapshot, owned_ids, {}, set(), mode=transport_mode)
    except TransportInputError as exc:
        print(f"传播输入不可用：{exc}")
        return 2
    if transport_mode != "legacy" and tax_report is not None:
        print("税收实验仍使用历史传播接口；不能与新 transport mode 混合输出。")
        return 2
    lake_ids = ({node for node, name in names.items()
                 if template_attributes.get(name, {}).get("topography") in LAKE_TOPOGRAPHIES}
                if transport_mode != "legacy" else set())
    graph, special_edges = build_owned_adjacency(map_data, names, owned_ids | lake_ids)
    # Only direct owned shore -> lake -> owned shore transit is supported;
    # neither lake-to-lake chains nor foreign shores are fabricated.
    lake_ids = {node for node in lake_ids if graph.get(node, set()) & owned_ids}
    graph = {node: {other for other in neighbors if other in owned_ids or other in lake_ids}
             for node, neighbors in graph.items() if node in owned_ids or node in lake_ids}
    for node in lake_ids:
        graph[node] &= owned_ids
    roads = {
        edge: road_type
        for edge, road_type in snapshot.roads.items()
        if edge <= owned_ids
    }
    for edge in roads:
        first, second = tuple(edge)
        graph[first].add(second)
        graph[second].add(first)
    transport_context = build_transport_context(snapshot, owned_ids, graph, special_edges,
                                                mode=transport_mode, lake_ids=lake_ids)

    locations: dict[int, LocationState] = {}
    for location_id, raw in owned_raw.items():
        name = names.get(location_id, f"location_{location_id}")
        possible_tax = raw.runtime_variables.get(
            "eu5ab_gov_cached_potential_tax_base",
            raw.possible_tax or raw.tax / max(raw.control, 0.05),
        )
        locations[location_id] = LocationState(
            id=location_id,
            name=name,
            rank=raw.rank,
            proximity=raw.proximity,
            control=raw.control,
            max_control=raw.runtime_variables.get(
                "eu5ab_gov_cached_old_max_control"
            ),
            population=raw.runtime_variables.get(
                "eu5ab_gov_cached_population", raw.population
            ),
            potential_tax_base=possible_tax,
            development=raw.runtime_variables.get(
                "eu5ab_gov_cached_development", raw.development
            ),
            road_to_capital=raw.road_to_capital,
            is_port=name in ports,
            edge_cost_factor=raw.runtime_variables.get(
                "eu5ab_gov_edge_cost_factor"
            ),
            road_edge_base_cost=raw.runtime_variables.get(
                "eu5ab_gov_road_edge_base_cost"
            ),
            land_edge_base_cost=raw.runtime_variables.get(
                "eu5ab_gov_land_edge_base_cost"
            ),
            runtime_value=raw.runtime_variables.get("eu5ab_gov_node_value"),
        )
    for node in lake_ids:
        locations[node] = LocationState(node, names[node], "lake", 0, 0, None,
                                        0, 0, 0, is_transit_only=True)

    capital = snapshot.capitals.get(player)
    local_governors = completed_building_locations(snapshot, "local_governor") & owned_ids
    naval_governors = completed_building_locations(snapshot, "naval_governor") & owned_ids
    current_sources = snapshot.country_runtime_variables.get(player, {}).get("eu5ab_planner_schema", 0) >= 4 or bool(re.match(r"1\.[4-9](?:\D|$)", snapshot.version))
    special_excluded = (excluded_building_locations(snapshot, "itinerant_court_seat")
                        | excluded_building_locations(snapshot, "kings_manor")) if current_sources else excluded_building_locations(snapshot, "lieutenancy")
    local_excluded = (excluded_building_locations(snapshot, "local_governor")
                      | special_excluded
                      | excluded_building_locations(snapshot, "seljuk_mint", include_construction=False))
    naval_excluded = excluded_building_locations(snapshot, "naval_governor")
    local_candidates = {
        location_id
        for location_id, location in locations.items()
        if location.rank in {"city", "megalopolis"}
        and location.road_to_capital
        and location_id != capital
        and location_id not in local_excluded
    }
    source_values = build_attributed_source_values(snapshot, owned_ids, capital)
    if current_sources:
        locations = {node: replace(location, raw_proximity_source=source_values.get(node, 0.0))
                     for node, location in locations.items()}
    baseline = None
    if transport_context is not None:
        baseline = propagate_proximity(source_values, locations, graph, roads,
                                       special_edges=special_edges, max_depth=None,
                                       max_steps=max(100, len(locations)*20),
                                       require_complete=True, transport_context=transport_context)
        baseline = {node: baseline.get(node, 0.0) for node in locations}
    calibrated = (dict(transport_context=transport_context, baseline_proximity=baseline)
                  if transport_context is not None else {})
    local_ranked = rank_local_candidates(
        local_candidates,
        locations,
        graph,
        roads,
        profile=profile,
        special_edges=special_edges,
        **calibrated,
    )
    if tax_report is not None:
        from src.eu5autobuild.governor_tax import write_tax_report

        write_tax_report(
            tax_report, snapshot, game_layer, owned_raw, locations,
            local_candidates, graph, roads, special_edges, tax_rate_overrides,
        )
        print(f"新增月税收离线实验（尚未实机验证）：{tax_report}")

    owned_graph = {node: graph[node] & owned_ids for node in owned_ids}
    all_components = connected_components(owned_ids, owned_graph)
    capital_component = next((component for component in all_components if capital in component), set())
    disconnected = [component for component in all_components if component is not capital_component]
    disconnected_ids = set().union(*disconnected) if disconnected else set()
    naval_candidates = {
        location_id
        for location_id in disconnected_ids
        if locations[location_id].rank in {"city", "megalopolis"}
        and locations[location_id].is_port
        and location_id not in naval_excluded
    }
    # The calibrated Local Governor scope does not establish all naval
    # presence/overseas rules. Keep historical naval diagnostics explicit.
    naval_ranked = rank_naval_components(
        disconnected,
        naval_candidates,
        naval_governors,
        locations,
        graph,
        roads,
        profile=profile,
        special_edges=special_edges,
    ) if transport_mode == "legacy" else []
    naval_relocation_candidates = evaluate_naval_relocation_candidates(
        disconnected,
        naval_candidates,
        locations,
        graph,
        roads,
        profile=profile,
        special_edges=special_edges,
    ) if transport_mode == "legacy" else []

    from src.eu5autobuild.governor_layout_policy import plan_complete_layout
    complete_layout = plan_complete_layout(
        local_governors, local_candidates, source_values, locations,
        graph, roads, capital=capital, profile=profile, special_edges=special_edges,
        transport_context=transport_context, scored_location_ids=owned_ids,
        relative_rate=snapshot.country_runtime_variables.get(player, {}).get(
            "eu5ab_global_governor_migration_threshold_percent", 80) / 100,
    )

    if layout_report is not None:
        import json
        from src.eu5autobuild.governor_layout import plan_layout
        experiments = {}
        for depth in ((6, len(locations)) if transport_mode == "legacy" else ()):
            for shortlist in (8, None):
                key = f"depth_{depth}_shortlist_{shortlist}"
                experiments[key] = plan_layout(
                    local_governors, local_candidates, source_values, locations,
                    graph, roads, capital=capital, profile=profile,
                    special_edges=special_edges, shortlist=shortlist, max_depth=depth,
                )
        layout_report.parent.mkdir(parents=True, exist_ok=True)
        # Generated-script equivalence is tested separately with explicit
        # injected engine primitives. An old factor cache cannot impersonate
        # those inputs, and offline timings are not EU5 worker measurements.
        runtime_check = dict(
            status="not_run", matches_reference=None,
            reason="Save validation does not substitute cached factors for engine primitives; use targeted generated-script tests.",
        )
        layout_report.write_text(json.dumps(dict(
            save=str(save_path), date=snapshot.date, locations=len(locations),
            roads=len(roads), capital=capital, experiments=experiments,
            source_building_state=state_summary,
            saved_sync_diagnostics={
                key: value for key, value in snapshot.country_runtime_variables.get(player, {}).items()
                if key.startswith("eu5ab_gov_sync_")
            },
            saved_sync_scopes={
                key: value for key, value in snapshot.country_runtime_scope_variables.get(player, {}).items()
                if key.startswith("eu5ab_gov_sync_")
            },
            transport_mode=transport_mode, lake_transit_nodes=len(lake_ids),
            planned_road_type=transport_context.planned_road_type if transport_context else None,
            transport_input_source="schema-2 cached engine inputs" if transport_context else "historical Mod factors or 20/40 fallback",
            complete_layout=complete_layout,
            generated_runtime=runtime_check,
            limitation="Offline proxy only; timings are not EU5 frame timings. "
                       "Source attribution, cached modifiers, and engine propagation may differ.",
        ), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"完整布局离线实验：{layout_report}")

    local_pairs = rank_migration_pairs(
        local_governors,
        (result.location_id for result in local_ranked),
        source_values,
        locations,
        graph,
        roads,
        profile=profile,
        special_edges=special_edges,
        transport_context=transport_context,
    ) if transport_mode == "legacy" else []
    naval_pairs = rank_migration_pairs(
        naval_governors,
        (result.location_id for result in naval_relocation_candidates),
        source_values,
        locations,
        graph,
        roads,
        profile=profile,
        naval=True,
        special_edges=special_edges,
    )
    nationwide_value = sum(location_value(location, profile) for location in locations.values())
    naval_migration = choose_migration(
        naval_pairs,
        nationwide_value=nationwide_value,
    )

    interesting_ids = set(local_governors) | set(naval_governors)
    interesting_ids.update(result.location_id for result in local_ranked[:3])
    interesting_ids.update(result.location_id for result in naval_ranked[:3])
    if inspect_location:
        interesting_ids.update(
            location_id
            for location_id, location in locations.items()
            if location.name == inspect_location
        )
    chinese = load_chinese_names(game_layer, (locations[item].name for item in interesting_ids))
    threshold = min(1000.0, max(1.0, nationwide_value * 0.01))

    print(f"存档：{save_path.name}")
    print(
        f"日期 {snapshot.date}，版本 {snapshot.version}，玩家 {snapshot.player_country_name} "
        f"(country ID {player})，首都地点 ID {capital}"
    )
    print(
        f"读取 {len(owned_ids)} 个直属地点、{len(lake_ids)} 个湖泊中转节点、{len(roads)} 条实际道路、"
        f"{len(all_components)} 个相邻领地分量；评分偏好：{profile}"
    )
    if transport_context is None:
        print("传播模式 legacy：历史 Mod 传播近似；不是修复后的引擎公式验证。迁移政策使用当前完整布局与单席位比较。")
    else:
        print(f"传播模式 {transport_mode}；输入来自 schema-2 缓存快照，不反算旧版 factor。")
        if transport_context.mode is TransportMode.HIGHEST_UNLOCKED:
            print(f"所有已归类可修路陆地连接按已解锁最高道路 {transport_context.planned_road_type or '未解锁'} 计算；"
                  "原布局与候选共用此网络，不将它与实际道路邻近度相减作为预测误差。")
        else:
            print("actual 模式用于当前路网传播诊断；长期选址请另用 highest-unlocked。")
        print("湖泊只连接本国岸边；未纳入海洋、海峡及跨外国领土。候选仍须满足当前存档的道路连接与建筑结构资格。")
    value_cache_count = sum(
        locations[node].runtime_value is not None for node in owned_ids
    )
    edge_cache_count = sum(
        location.edge_cost_factor is not None
        and location.road_edge_base_cost is not None
        and location.land_edge_base_cost is not None
        for node in owned_ids for location in (locations[node],)
    )
    print(
        f"游戏运行时地点价值缓存：{value_cache_count}/{len(owned_ids)}；"
        f"Mod 传播模型缓存：{edge_cache_count}/{len(owned_ids)}（不是引擎逐边成本）"
    )
    if value_cache_count < len(owned_ids):
        print(
            "警告：部分地点缺少游戏运行时地点价值缓存；这些地点会使用存档字段近似，"
            "无法保证地点价值偏好和战略价值开关与游戏内完全一致。"
        )
    if transport_context is None and edge_cache_count < len(owned_ids):
        print(
            f"警告：{len(owned_ids) - edge_cache_count} 个地点缺少逐地点传播缓存；"
            "只有经过这些地点的边会回退到未修正的原版 20/40 基准成本。"
            "若关键候选经过这些地点，请用新版脚本重新计算后再保存。"
        )
    print(
        f"现有地方总督治所 {len(local_governors)} 个，现有海军总督治所 {len(naval_governors)} 个；"
        f"地方候选 {len(local_candidates)} 个，海军候选 {len(naval_candidates)} 个"
    )
    for kind, state in state_summary.items():
        print(f"  {kind}: 完成地点 {state['completed']}，施工地点 {state['construction_locations']}，"
              f"已确认占位地点 {state['known_occupied_locations']}，未知地点 {state['unknown_locations']}")
    print("占位按完成与有效施工去重；这里没有重建全部国家容量修正。")
    sync = {key.removeprefix("eu5ab_gov_sync_"): value
            for key, value in snapshot.country_runtime_variables.get(player, {}).items()
            if key.startswith("eu5ab_gov_sync_")}
    if sync:
        print(f"已保存的同步诊断（与本次离线复算分开）：{sync}")
        print("stage: 1=进入刷新，2=基线完成，3=地方排名已尝试并保存诊断，4=提醒阶段完成；"
              "stage 未到 3 时，其他诊断可能仍属上次刷新。")
    print(f"新槽位价值门槛：{threshold:.2f}")
    print("地方总督治所 Top 3：")
    if local_ranked:
        for rank, result in enumerate(local_ranked[:3], 1):
            print(_format_candidate(rank, result, locations, chinese))
    else:
        print("  无合法候选")
    if inspect_location:
        inspected_id = next(
            (
                location_id
                for location_id, location in locations.items()
                if location.name == inspect_location
            ),
            None,
        )
        if inspected_id is None:
            print(f"指定检查地点 {inspect_location} 不属于玩家")
        elif inspected_id not in local_candidates:
            inspected = locations[inspected_id]
            print(
                f"指定检查地点 {inspect_location} 不是合法的地方总督治所候选；"
                f"当前邻近度 {inspected.proximity:.2f}，当前控制力 {inspected.control:.1%}"
            )
        else:
            inspected_result = evaluate_candidate(
                inspected_id,
                locations,
                graph,
                roads,
                profile=profile,
                special_edges=special_edges,
                **calibrated,
            )
            scoring_locations = ({n: replace(item, proximity=baseline[n]) for n, item in locations.items()}
                                 if baseline is not None else locations)
            cheap_order = sorted(
                local_candidates,
                key=lambda location_id: cheap_score(
                    location_id,
                    scoring_locations,
                    graph,
                    roads,
                    profile=profile,
                ),
                reverse=True,
            )
            shortlist_rank = cheap_order.index(inspected_id) + 1
            final_rank = next(
                (
                    rank
                    for rank, result in enumerate(local_ranked, 1)
                    if result.location_id == inspected_id
                ),
                None,
            )
            final_label = (
                f"第 {final_rank} 名"
                if final_rank is not None
                else "未进入前 8 名初筛"
            )
            print(
                f"指定检查地点 {inspect_location}：初筛第 {shortlist_rank} 名，"
                f"最终{final_label}；"
                + _format_candidate(0, inspected_result, locations, chinese).split("— ", 1)[1]
            )
            _print_contribution_diagnostics(inspected_result, locations, chinese)
        if inspected_id is not None:
            inspected_pairs = [
                proposal
                for proposal in local_pairs
                if proposal.current_location_id == inspected_id
                or proposal.recommended_location_id == inspected_id
            ]
            if inspected_pairs:
                print("与指定地点有关的完整迁移反事实：")
                for proposal in inspected_pairs:
                    print("  " + _format_migration(proposal, locations, chinese))
    print("海军总督治所 Top 3（每个分离领地先选一个港口）：" if transport_mode == "legacy"
          else "海军总督诊断：actual 和 highest-unlocked 模式仅计算地方治所，跳过海军计算。")
    if naval_ranked:
        for rank, result in enumerate(naval_ranked[:3], 1):
            print(_format_candidate(rank, result, locations, chinese))
    else:
        print("  无符合离线结构过滤的候选")
    print(f"地方迁移：{complete_layout['proposal_kind']}，全国净收益 {complete_layout['modeled_net']:.3f}，"
          f"改变席位原贡献 {complete_layout['changed_contribution']:.3f}，"
          f"门槛 改变席位贡献×{complete_layout['relative_rate']:.0%}={complete_layout['migration_threshold']:.3f}，"
          f"合格={complete_layout['qualifies']}；单席位比较 {complete_layout['single_swap_comparisons']} 次。")
    for step in complete_layout["display_steps"]:
        print(f"  {step['origin']} → {step['destination']}" + ("（保留）" if step['retained'] else ""))
    if complete_layout["live_model_absolute_weighted_error"] is not None:
        print(f"当前路网模型与实际邻近度的加权绝对误差：{complete_layout['live_model_absolute_weighted_error']:.3f}"
              "（来源完整性及快照时效仍可能影响差值）")
    if local_pairs:
        print("  历史八候选逐对模型诊断（不参与当前方案选择）：" + _format_migration(local_pairs[0], locations, chinese))
    print(
        "海军迁移完整反事实比较（先移除旧来源，再加入新来源）："
        + (
            _format_migration(naval_migration, locations, chinese)
            if naval_migration
            else "无现有治所或未超过迁移双门槛"
        )
    )
    if naval_pairs:
        print("  最佳原始组合：" + _format_migration(naval_pairs[0], locations, chinese))
    recognized = set().union(
        *(completed_building_locations(snapshot, building) for building in SOURCE_BUILDING_TYPES)
    ) & owned_ids
    print(f"已识别的原版邻近度来源建筑地点：{len(recognized)} 个")
    print(
        "说明：1.4 使用保存的完整邻近度来源快照，包含当时的临时效果；"
        "快照可能已过时，请重算后保存。历史 1.3 回放仍使用旧建筑表。"
    )
    print(
        "海军离线候选未复刻 is_overseas_for_owner 的引擎判定；"
        "最终新槽位横幅仍由原版 location_and_owner_can_build 精确复核。"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--save", type=Path, required=True)
    parser.add_argument("--game-root", type=Path, required=True)
    parser.add_argument(
        "--profile",
        choices=("mixed", "economic", "administrative_population"),
        default="mixed",
    )
    parser.add_argument(
        "--inspect-location",
        help="额外输出一个 location template ID 的候选评分诊断，例如 nanchang",
    )
    parser.add_argument("--layout-report", type=Path,
                        help="写出完整布局/单席位比较 JSON；legacy 另含历史深度/候选实验")
    parser.add_argument("--transport-mode", choices=("legacy", "actual", "highest-unlocked"),
                        default="legacy", help="legacy 历史重放；actual 实际路网诊断；highest-unlocked 长期选址。后两者要求新 Mod 的 schema-2 完整缓存")
    parser.add_argument("--tax-report", type=Path,
                        help="写出实验性稳定后新增月税收排名，不替代游戏内评分")
    from src.eu5autobuild.governor_tax import parse_tax_rate_override
    parser.add_argument("--tax-rate", action="append", type=parse_tax_rate_override,
                        default=[], metavar="ESTATE=RATE",
                        help="明确指定已确认税率（0 到 1），例如 clergy_estate=0；可重复")
    args = parser.parse_args()
    if args.tax_rate and args.tax_report is None:
        parser.error("--tax-rate requires --tax-report")
    return validate(args.save, args.game_root, args.profile, args.inspect_location,
                    args.layout_report, args.tax_report, dict(args.tax_rate), args.transport_mode)


if __name__ == "__main__":
    raise SystemExit(main())
