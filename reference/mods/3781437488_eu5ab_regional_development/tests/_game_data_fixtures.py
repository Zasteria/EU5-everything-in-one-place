"""Load checked-in vanilla-data snapshots for renderer unit tests."""

from __future__ import annotations

from functools import cache
import json
from pathlib import Path

from src.eu5autobuild.game_data import (
    BuildingUpgradeData,
    BuildingWorkforce,
    ConstructionDemand,
    PromotionPath,
    WorkforceModelData,
)
from src.eu5autobuild.production import BuildingProduction, production_models_from_json


ROOT = Path(__file__).resolve().parents[1]


def _load_json(relative_path: str) -> dict:
    return json.loads((ROOT / relative_path).read_text(encoding="utf-8-sig"))


@cache
def cached_game_data() -> tuple[
    dict[str, BuildingProduction],
    dict[str, ConstructionDemand],
    BuildingUpgradeData,
    WorkforceModelData,
]:
    """Return stable renderer inputs without requiring a local game install."""
    recipes_payload = _load_json(".metadata/eu5ab_production_recipes.json")
    recipes = production_models_from_json(recipes_payload)

    demands_payload = _load_json(".metadata/eu5ab_construction_demands.json")
    construction_demands = {
        row["building_id"]: ConstructionDemand(**row)
        for row in demands_payload["buildings"]
    }

    upgrades_payload = _load_json(".metadata/eu5ab_building_upgrades.json")
    upgrades = BuildingUpgradeData(
        native_successors={building_id: tuple(row.get("native_successors", ()))
                           for building_id, row in upgrades_payload["buildings"].items()},
        successors={
            building_id: tuple(row["successors"])
            for building_id, row in upgrades_payload["buildings"].items()
        },
        predecessors={
            building_id: tuple(row["predecessors"])
            for building_id, row in upgrades_payload["buildings"].items()
        },
    )

    workforce_payload = _load_json(".metadata/eu5ab_workforce_model.json")
    buildings = {
        row["building_id"]: BuildingWorkforce(
            building_id=row["building_id"],
            pop_types=tuple(row["pop_types"]),
            jobs_per_level=row["jobs_per_level"],
            employment_size_id=row["employment_size_id"],
        )
        for row in workforce_payload["buildings"]
    }
    promotion_paths = {
        row["source_pop_type"]: PromotionPath(
            source_pop_type=row["source_pop_type"],
            targets=tuple(row["targets"]),
            promotion_factor=row["promotion_factor"],
            has_cap=row["has_cap"],
        )
        for row in workforce_payload["promotion_paths"]
    }
    source = workforce_payload["source"]
    workforce = WorkforceModelData(
        buildings=buildings,
        # Checked-in metadata intentionally contains only supported buildings.
        # That is sufficient for renderer unit tests; installed-game integration
        # tests separately cover extraction of unsupported upgrade predecessors.
        all_buildings=buildings,
        promotion_paths=promotion_paths,
        base_promotion_speed=source["base_promotion_speed"],
        monthly_script_value_available=source[
            "monthly_script_value_available"
        ],
        rgo_jobs_per_level=source.get("rgo_jobs_per_level"),
    )
    return recipes, construction_demands, upgrades, workforce
