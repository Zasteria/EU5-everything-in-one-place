"""Policy loading and validation for regional development templates."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .validation import (
    load_json,
    require_bool,
    require_finite_number,
    require_identifier,
    require_identifier_list,
    require_int,
    require_mapping,
)


REQUIRED_POLICY_KEYS = {
    "id",
    "name_key",
    "description_key",
    "role",
    "priority_goods",
    "allowed_buildings",
    "banned_buildings",
    "prediction",
}


@dataclass(frozen=True)
class RgoPolicy:
    allowed: bool = True
    # Read old policy data for compatibility; decisions always require full staffing.
    minimum_utilization: float = 1.0
    workforce_mode: str = "relaxed"
    job_fill_deadline_months: int = 180

    @classmethod
    def from_mapping(cls, raw: dict[str, Any] | None) -> "RgoPolicy":
        if raw is None:
            raw = {}
        raw = require_mapping(raw, "RGO policy")
        result = cls(
            allowed=require_bool(raw.get("allowed", True), "RGO allowed"),
            workforce_mode=raw.get("workforce_mode", "relaxed"),
            job_fill_deadline_months=require_int(raw.get("job_fill_deadline_months", 180), "RGO forecast months"),
            minimum_utilization=require_finite_number(
                raw.get("minimum_utilization", 1.0),
                "RGO minimum utilization",
            ),
        )
        if not 0 <= result.minimum_utilization <= 1:
            raise ValueError("RGO minimum utilization must be between 0 and 1")
        if result.workforce_mode not in ("relaxed", "population"):
            raise ValueError("RGO workforce mode must be relaxed or population")
        if not 0 <= result.job_fill_deadline_months <= 1200:
            raise ValueError("RGO forecast horizon must be between 0 and 1200 months")
        return result


@dataclass(frozen=True)
class Policy:
    id: str
    name_key: str
    description_key: str
    role: str
    priority_goods: tuple[str, ...]
    allowed_buildings: tuple[str, ...]
    banned_buildings: tuple[str, ...]
    prediction: dict[str, Any]
    # The pure-Python planner keeps the same shared defaults as CMM for tests and
    # offline analysis. These values are no longer template schema fields.
    annual_budget: int = 500
    min_cash_reserve: int = 1000
    min_price_ratio: float = 0.8
    max_price_ratio: float = 1.25
    allow_special_buildings: bool = False
    pause_on_labor_shortage: bool = True
    pause_on_input_shortage: bool = True
    auto_build_input_sources: bool = True
    job_fill_deadline_months: int = 12
    native_input_priority: int = 5
    rgo: RgoPolicy = field(default_factory=RgoPolicy)

    @classmethod
    def from_mapping(cls, raw: dict[str, Any]) -> "Policy":
        raw = require_mapping(raw, "Policy")
        missing = REQUIRED_POLICY_KEYS - raw.keys()
        if missing:
            raise ValueError(f"Policy {raw.get('id', '<unknown>')} missing keys: {sorted(missing)}")

        policy_id = require_identifier(raw["id"], "Policy id")
        priority_goods = require_identifier_list(
            raw["priority_goods"],
            f"Policy {policy_id} priority goods",
        )
        allowed_buildings = require_identifier_list(
            raw["allowed_buildings"],
            f"Policy {policy_id} allowed buildings",
        )
        banned_buildings = require_identifier_list(
            raw["banned_buildings"],
            f"Policy {policy_id} banned buildings",
        )
        prediction = require_mapping(raw["prediction"], f"Policy {policy_id} prediction")
        for key in ("display_name", "summary"):
            if not isinstance(prediction.get(key), str) or not prediction[key].strip():
                raise ValueError(f"Policy {policy_id} prediction {key} must be non-empty text")

        result = cls(
            id=policy_id,
            name_key=require_identifier(raw["name_key"], f"Policy {policy_id} name key"),
            description_key=require_identifier(
                raw["description_key"], f"Policy {policy_id} description key"
            ),
            role=require_identifier(raw["role"], f"Policy {policy_id} role"),
            priority_goods=priority_goods,
            allowed_buildings=allowed_buildings,
            banned_buildings=banned_buildings,
            prediction=dict(prediction),
        )
        return result


@dataclass(frozen=True)
class BuildingDefinition:
    id: str
    output_goods: tuple[str, ...]
    input_goods: tuple[str, ...]
    workforce_pop_types: tuple[str, ...]
    is_special: bool = False
    localization_key: str = ""
    age: int = 1


@dataclass(frozen=True)
class BuildingCatalog:
    buildings: dict[str, BuildingDefinition]
    source_buildings_by_good: dict[str, tuple[str, ...]]
    consumer_buildings_by_good: dict[str, tuple[str, ...]]

    @classmethod
    def from_mapping(cls, raw: dict[str, Any]) -> "BuildingCatalog":
        raw = require_mapping(raw, "Building catalog")
        input_goods_by_building = require_mapping(
            raw.get("input_goods_by_building", {}),
            "Building catalog input_goods_by_building",
        )
        raw_buildings = raw.get("buildings", [])
        if not isinstance(raw_buildings, list):
            raise ValueError("Building catalog buildings must be a list")
        buildings: dict[str, BuildingDefinition] = {}
        for index, item in enumerate(raw_buildings):
            item = require_mapping(item, f"Building catalog buildings[{index}]")
            building_id = require_identifier(item.get("id"), f"Building catalog buildings[{index}].id")
            if building_id in buildings:
                raise ValueError(f"Building catalog contains duplicate id: {building_id}")
            fallback_inputs = input_goods_by_building.get(building_id, [])
            buildings[building_id] = BuildingDefinition(
                id=building_id,
                output_goods=require_identifier_list(
                    item.get("output_goods", []),
                    f"Building {building_id} output goods",
                ),
                input_goods=require_identifier_list(
                    item.get("input_goods", fallback_inputs),
                    f"Building {building_id} input goods",
                ),
                workforce_pop_types=require_identifier_list(
                    item.get("workforce_pop_types", []),
                    f"Building {building_id} workforce pop types",
                ),
                is_special=require_bool(
                    item.get("is_special", False),
                    f"Building {building_id} is_special",
                ),
                localization_key=require_identifier(
                    item.get("localization_key", building_id),
                    f"Building {building_id} localization key",
                ),
                age=require_int(item.get("age", 1), f"Building {building_id} age"),
            )
        if not buildings:
            raise ValueError("Building catalog must contain at least one building")
        invalid_ages = sorted(
            building.id for building in buildings.values() if building.age not in range(1, 7)
        )
        if invalid_ages:
            raise ValueError(f"Building catalog has invalid ages: {invalid_ages}")


        source_buildings_by_good: dict[str, list[str]] = {}
        consumer_buildings_by_good: dict[str, list[str]] = {}
        for building in buildings.values():
            for good in building.output_goods:
                source_buildings_by_good.setdefault(good, []).append(building.id)
            for good in building.input_goods:
                consumer_buildings_by_good.setdefault(good, []).append(building.id)

        explicit_sources = require_mapping(
            raw.get("source_buildings_by_good", {}),
            "Building catalog source_buildings_by_good",
        )
        for good, building_ids in explicit_sources.items():
            good_id = require_identifier(good, "Building catalog source good")
            sources = require_identifier_list(
                building_ids,
                f"Building catalog source buildings for {good_id}",
            )
            unknown = sorted(set(sources) - buildings.keys())
            if unknown:
                raise ValueError(
                    f"Building catalog source buildings for {good_id} are unknown: {unknown}"
                )
            source_buildings_by_good[good_id] = list(sources)

        return cls(
            buildings=buildings,
            source_buildings_by_good={
                good: tuple(building_ids)
                for good, building_ids in sorted(source_buildings_by_good.items())
            },
            consumer_buildings_by_good={
                good: tuple(building_ids)
                for good, building_ids in sorted(
                    consumer_buildings_by_good.items()
                )
            },
        )

    def get(self, building_id: str) -> BuildingDefinition | None:
        return self.buildings.get(building_id)


def load_policies(path: Path) -> list[Policy]:
    data = require_mapping(load_json(path), "Policy file")
    raw_policies = data.get("policies")
    if not isinstance(raw_policies, list):
        raise ValueError("Policy file must contain a policies list")
    policies = [Policy.from_mapping(item) for item in raw_policies]
    ids = [policy.id for policy in policies]
    duplicates = sorted({policy_id for policy_id in ids if ids.count(policy_id) > 1})
    if duplicates:
        raise ValueError(f"Duplicate policy ids: {duplicates}")
    return policies


def load_building_catalog(path: Path) -> BuildingCatalog:
    data = require_mapping(load_json(path), "Building catalog file")
    return BuildingCatalog.from_mapping(data)


def policy_by_id(policies: list[Policy], policy_id: str) -> Policy:
    for policy in policies:
        if policy.id == policy_id:
            return policy
    raise KeyError(policy_id)
