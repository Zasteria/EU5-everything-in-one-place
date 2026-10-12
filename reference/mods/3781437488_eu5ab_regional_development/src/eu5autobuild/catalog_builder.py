"""Build the EU5AB catalog from player-manageable vanilla buildings."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from typing import Any

from .game_data import (
    Block,
    _first_block,
    _first_scalar,
    extract_workforce_model,
    parse_paradox_script,
)
from .game_root import require_game_root
from .policy import BuildingCatalog
from .production import extract_production_models
from .rgo_automation import RAW_GOODS_FILE, extract_raw_goods
from .validation import (
    load_json,
    require_finite_number,
    require_identifier,
    require_mapping,
)


ROOT = Path(__file__).resolve().parents[2]
CATALOG_FILE = ROOT / "policies" / "building_catalog.json"
RULES_FILE = ROOT / "policies" / "automation_rules.json"
VIDEO_PRIORITIES_FILE = ROOT / "policies" / "video_building_priorities.json"

# Reviewed indirect RGO support, not manufactured output. Keep these explicit
# rather than preserving every generated field from the previous game version.
INDIRECT_OUTPUT_GOODS = {
    "local_smelters": ("copper",),
    "mercury_patio": ("goods_gold",),
}

# These files contain definitions that are deliberately unavailable in the
# normal player construction interface. Estate-owned buildings are filtered by
# their ``estate`` field below even if a future patch moves them to another file.
NON_PLAYER_BUILDING_FILES = frozenset(
    {
        "00_unique_buildings_to_make_obsolete.txt",
        "event_only_buildings.txt",
        "readme.txt",
    }
)

# Some lifecycle buildings appear in the normal definitions but are not safe
# standalone construction candidates. Querying settlement_building through the
# GUI construction API evaluates its remove_if block without an existing
# building location and floods the runtime log with unset `location` errors.
NON_AUTOMATION_BUILDINGS = frozenset({"settlement_building"})

_AGE_ID = re.compile(r"^age_([1-6])_")


def _definition_sources(path: Path) -> dict[str, tuple[Block, str]]:
    definitions: dict[str, tuple[Block, str]] = {}
    for source in sorted(path.glob("*.txt")):
        for key, value in parse_paradox_script(source.read_text(encoding="utf-8-sig")):
            if key is not None and isinstance(value, list):
                definitions[key] = (value, source.name)
    return definitions


def _direct_always_no(block: Block, key: str) -> bool:
    condition = _first_block(block, key)
    if condition is None:
        return False
    return any(
        entry_key == "always"
        and not isinstance(value, list)
        and str(value).lower() == "no"
        for entry_key, value in condition
    )


def is_player_manageable_building(block: Block, source_name: str) -> bool:
    """Return whether a country player can normally build/manage this type."""
    if source_name in NON_PLAYER_BUILDING_FILES:
        return False
    if _first_scalar(block, "estate") is not None:
        return False
    if _direct_always_no(block, "country_potential"):
        return False
    return True


def extract_player_manageable_buildings(
    game_root: Path,
) -> dict[str, tuple[Block, str]]:
    definitions = _definition_sources(
        game_root / "game" / "in_game" / "common" / "building_types"
    )
    return {
        building_id: definition
        for building_id, definition in definitions.items()
        if building_id not in NON_AUTOMATION_BUILDINGS
        and is_player_manageable_building(*definition)
    }


def extract_building_unlock_ages(game_root: Path) -> dict[str, int]:
    ages: dict[str, int] = {}
    advances = game_root / "game" / "in_game" / "common" / "advances"
    for source in sorted(advances.glob("*.txt")):
        for _, value in parse_paradox_script(source.read_text(encoding="utf-8-sig")):
            if not isinstance(value, list):
                continue
            raw_age = _first_scalar(value, "age")
            match = _AGE_ID.match(str(raw_age)) if raw_age is not None else None
            if match is None:
                continue
            age = int(match.group(1))
            for building_id in (
                str(item).removeprefix("building_type:")
                for key, item in value
                if key == "unlock_building" and not isinstance(item, list)
            ):
                ages[building_id] = min(age, ages.get(building_id, age))
    return ages


def _vanilla_is_special(block: Block) -> bool:
    value = _first_scalar(block, "is_special")
    return value is not None and str(value).lower() == "yes"


def build_catalog_payload(
    game_root: Path,
    existing_payload: dict[str, Any],
) -> dict[str, Any]:
    definitions = extract_player_manageable_buildings(game_root)
    building_ids = tuple(sorted(definitions))
    minimal_catalog = BuildingCatalog.from_mapping(
        {"buildings": [{"id": building_id} for building_id in building_ids]}
    )
    recipes = extract_production_models(game_root, minimal_catalog)
    workforce = extract_workforce_model(game_root, minimal_catalog)
    unlock_ages = extract_building_unlock_ages(game_root)

    existing_entries = {
        item["id"]: item for item in existing_payload.get("buildings", [])
    }
    buildings: list[dict[str, Any]] = []
    input_goods_by_building: dict[str, list[str]] = {}

    for building_id in building_ids:
        block, _ = definitions[building_id]
        existing = existing_entries.get(building_id, {})
        model = recipes[building_id]
        workforce_entry = workforce.buildings.get(building_id)
        # This is a discovery index across all alternative methods and slots.
        # Runtime recipe guards still decide what is actually produced/needed.
        output_goods = sorted(
            {good for slot in model.slots for method in slot
             for good, amount in method.outputs.items() if amount > 0}
            | set(INDIRECT_OUTPUT_GOODS.get(building_id, ()))
        )
        pop_types = list(workforce_entry.pop_types if workforce_entry else ())
        entry: dict[str, Any] = {
            "id": building_id,
            "age": unlock_ages.get(building_id, int(existing.get("age", 1))),
            "output_goods": output_goods,
            "workforce_pop_types": pop_types,
        }
        if _vanilla_is_special(block):
            entry["is_special"] = True
        localization_key = existing.get("localization_key")
        if localization_key and localization_key != building_id:
            entry["localization_key"] = str(localization_key)
        buildings.append(entry)

        inputs = sorted({good for slot in model.slots for method in slot
                         for good, amount in method.inputs.items() if amount > 0})
        if inputs:
            input_goods_by_building[building_id] = inputs

    sources: dict[str, list[str]] = {}
    for building in buildings:
        for good in building["output_goods"]:
            sources.setdefault(good, []).append(building["id"])
    return {
        "schema_version": 2,
        "source": {
            "kind": "vanilla_player_manageable_buildings",
            "goods_mapping": "all_production_method_slots_with_reviewed_indirect_support",
            "indirect_output_goods": {
                building: list(goods) for building, goods in INDIRECT_OUTPUT_GOODS.items()
                if building in definitions
            },
            "excluded_files": sorted(NON_PLAYER_BUILDING_FILES),
            "excluded_definition_rules": [
                "estate_owned",
                "country_potential_always_no",
                "unsafe_lifecycle_building",
            ],
        },
        "buildings": buildings,
        "source_buildings_by_good": dict(sorted(sources.items())),
        "input_goods_by_building": input_goods_by_building,
    }


def _direct_predecessors(game_root: Path) -> dict[str, tuple[str, ...]]:
    definitions = _definition_sources(
        game_root / "game" / "in_game" / "common" / "building_types"
    )
    return {
        building_id: tuple(
            str(value).removeprefix("building_type:")
            for key, value in block
            if key == "obsolete" and not isinstance(value, list)
        )
        for building_id, (block, _) in definitions.items()
    }


def build_priority_overrides(
    game_root: Path,
    building_ids: set[str],
    priority_payload: dict[str, Any],
) -> tuple[dict[str, float], dict[str, str]]:
    def validated_priorities(field: str, *, required: bool) -> dict[str, float]:
        raw = priority_payload.get(field)
        if raw is None and not required:
            raw = {}
        entries = require_mapping(raw, field)
        result: dict[str, float] = {}
        for building_id, value in entries.items():
            identifier = require_identifier(building_id, f"{field} key")
            priority = require_finite_number(value, f"{field}.{identifier}")
            if not 0 <= priority <= 10:
                raise ValueError(f"{field}.{identifier} must be between 0 and 10")
            result[identifier] = priority
        return result

    video = validated_priorities("direct_video_priorities", required=True)
    manual = validated_priorities("manual_overrides", required=False)
    predecessors = _direct_predecessors(game_root)
    resolved: dict[str, float] = {}
    provenance: dict[str, str] = {}

    def priority_for(building_id: str, stack: tuple[str, ...] = ()) -> float:
        if building_id in resolved:
            return resolved[building_id]
        if building_id in stack:
            raise ValueError(f"Building upgrade cycle: {' -> '.join((*stack, building_id))}")
        if building_id in manual:
            value = manual[building_id]
            source = "manual_override"
        elif building_id in video:
            value = video[building_id]
            source = "video_calibrated"
        else:
            inherited = predecessors.get(building_id, ())
            if inherited:
                values = {
                    priority_for(predecessor, (*stack, building_id))
                    for predecessor in inherited
                }
                # A few vanilla destinations replace both a rural and an urban
                # predecessor. Preserve the strongest calibrated chain instead
                # of silently disabling that upgrade because another branch is 0.
                value = max(values)
                source = "inherited_upgrade"
            else:
                value = 0.0
                source = "independent_default"
        resolved[building_id] = value
        provenance[building_id] = source
        return value

    overrides = {
        building_id: priority_for(building_id)
        for building_id in sorted(building_ids)
    }
    return overrides, {building_id: provenance[building_id] for building_id in overrides}


def _json_number(value: float) -> int | float:
    return int(value) if value.is_integer() else value


def _replace_rules_priority_section(text: str, section: dict[str, Any]) -> str:
    marker = '"building_priorities": '
    marker_start = text.index(marker)
    start = text.index("{", marker_start + len(marker))
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                rendered_lines = json.dumps(section, indent=2).splitlines()
                rendered = "\n".join(
                    [rendered_lines[0], *("  " + line for line in rendered_lines[1:])]
                )
                return text[:start] + rendered + text[index + 1 :]
    raise ValueError("Unbalanced building_priorities JSON object")


def generated_catalog_and_rules(game_root: Path) -> tuple[str, str, dict[str, str]]:
    existing_catalog = require_mapping(load_json(CATALOG_FILE), "Building catalog file")
    BuildingCatalog.from_mapping(existing_catalog)
    catalog_payload = build_catalog_payload(game_root, existing_catalog)
    priority_payload = require_mapping(
        load_json(VIDEO_PRIORITIES_FILE),
        "Video priorities file",
    )
    priorities, provenance = build_priority_overrides(
        game_root,
        {item["id"] for item in catalog_payload["buildings"]},
        priority_payload,
    )
    priority_section = {
        "minimum": 0,
        "maximum": 10,
        "default": 0,
        "score_per_point": 50,
        "overrides": {
            building_id: _json_number(value)
            for building_id, value in priorities.items()
        },
    }
    catalog_text = json.dumps(catalog_payload, ensure_ascii=False, indent=2) + "\n"
    rules_text = _replace_rules_priority_section(
        RULES_FILE.read_text(encoding="utf-8"),
        priority_section,
    )
    return catalog_text, rules_text, provenance


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--game-root",
        type=Path,
        help="EU5 installation root; defaults to the EU5_GAME_ROOT environment variable.",
    )
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        game_root = require_game_root(args.game_root)
    except FileNotFoundError as error:
        parser.error(str(error))
    catalog_text, rules_text, _ = generated_catalog_and_rules(game_root)
    raw_goods_text = json.dumps(extract_raw_goods(game_root), indent=2) + "\n"
    if args.check:
        mismatches = []
        if CATALOG_FILE.read_text(encoding="utf-8") != catalog_text:
            mismatches.append(str(CATALOG_FILE))
        if RULES_FILE.read_text(encoding="utf-8") != rules_text:
            mismatches.append(str(RULES_FILE))
        if RAW_GOODS_FILE.read_text(encoding="utf-8") != raw_goods_text:
            mismatches.append(str(RAW_GOODS_FILE))
        if mismatches:
            raise SystemExit("Generated catalog is stale: " + ", ".join(mismatches))
        return
    CATALOG_FILE.write_text(catalog_text, encoding="utf-8")
    RULES_FILE.write_text(rules_text, encoding="utf-8")
    RAW_GOODS_FILE.write_text(raw_goods_text, encoding="utf-8")
    print(f"Generated {len(json.loads(catalog_text)['buildings'])} player-manageable buildings.")


if __name__ == "__main__":
    main()
