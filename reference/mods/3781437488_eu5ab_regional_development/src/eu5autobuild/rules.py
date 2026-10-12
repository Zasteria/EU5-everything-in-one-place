"""Data-driven automation rules derived from EU5's market and building data."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .validation import (
    load_json,
    require_finite_number,
    require_identifier,
    require_identifier_list,
    require_int,
    require_mapping,
)


REQUIRED_GOODS_GROUPS = {
    "food",
    "construction_core",
    "construction_secondary",
    "population_basic",
    "military",
    "industrial_inputs",
}

WORKFORCE_FORECAST_MAX_MONTHS = 240

_MISSING = object()


def _int_setting(
    raw: dict[str, Any],
    key: str,
    default: Any = _MISSING,
) -> int:
    if key not in raw:
        if default is _MISSING:
            raise ValueError(f"Missing required automation setting: {key}")
        value = default
    else:
        value = raw[key]
    return require_int(value, f"Automation setting {key}")


def _number_setting(
    raw: dict[str, Any],
    key: str,
    default: Any = _MISSING,
) -> float:
    if key not in raw:
        if default is _MISSING:
            raise ValueError(f"Missing required automation setting: {key}")
        value = default
    else:
        value = raw[key]
    return require_finite_number(value, f"Automation setting {key}")


def _section(raw: dict[str, Any], key: str) -> dict[str, Any]:
    value = raw.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"Automation rules missing mapping section: {key}")
    return value


def _tuple_mapping(raw: dict[str, Any], key: str) -> dict[str, tuple[str, ...]]:
    section = _section(raw, key)
    result: dict[str, tuple[str, ...]] = {}
    for group, values in section.items():
        group_id = require_identifier(group, f"Automation rules {key} group")
        result[group_id] = require_identifier_list(
            values,
            f"Automation rules {key}.{group_id}",
        )
    return result


@dataclass(frozen=True)
class AutomationCadence:
    max_country_concurrent_projects: int
    location_cooldown_months: int
    deep_score_location_limit: int
    deep_score_quota_multiplier: int
    candidates_per_location: int
    actual_profit_candidates_per_location: int

    @classmethod
    def from_mapping(cls, raw: dict[str, Any]) -> "AutomationCadence":
        result = cls(
            max_country_concurrent_projects=_int_setting(
                raw, "max_country_concurrent_projects", 600
            ),
            location_cooldown_months=_int_setting(raw, "location_cooldown_months"),
            deep_score_location_limit=_int_setting(raw, "deep_score_location_limit", 600),
            deep_score_quota_multiplier=_int_setting(
                raw, "deep_score_quota_multiplier", 8
            ),
            candidates_per_location=_int_setting(raw, "candidates_per_location", 3),
            actual_profit_candidates_per_location=_int_setting(
                raw, "actual_profit_candidates_per_location", 10
            ),
        )
        if min(
            result.max_country_concurrent_projects,
            result.deep_score_location_limit,
            result.deep_score_quota_multiplier,
            result.candidates_per_location,
            result.actual_profit_candidates_per_location,
        ) < 1:
            raise ValueError("Automation cadence build limits must be positive")
        if result.max_country_concurrent_projects > 600:
            raise ValueError("Country concurrent construction limit cannot exceed 600")
        if result.deep_score_location_limit > 600:
            raise ValueError("Deep-score location limit cannot exceed 600")
        if result.candidates_per_location != 3:
            raise ValueError("EU5AB requires exactly three retained candidates per location")
        if result.actual_profit_candidates_per_location < result.candidates_per_location:
            raise ValueError(
                "Actual-profit candidate limit cannot be below the diagnostic candidate limit"
            )
        if result.actual_profit_candidates_per_location > 30:
            raise ValueError("Actual-profit candidate limit cannot exceed 30")
        if result.location_cooldown_months < 0:
            raise ValueError("Automation location cooldown cannot be negative")
        return result


@dataclass(frozen=True)
class AutomationThresholds:
    food_emergency_ratio: float
    food_low_ratio: float
    goods_critical_supply_ratio: float
    goods_shortage_supply_ratio: float
    goods_high_price_ratio: float
    input_shortage_supply_ratio: float
    minimum_unemployed_workers: float
    rgo_budget_cost: int
    high_profit: float
    positive_profit: float
    expansion_bonus_per_level: int
    upgrade_replacement_bonus: int
    economic_score_scale: float
    engine_min_annual_return_ratio: float
    construction_price_ceiling_ratio: float
    construction_stall_headroom_ratio: float
    irrigation_population_capacity_ratio: float
    granary_full_ratio: float
    food_reserve_months: float

    @classmethod
    def from_mapping(cls, raw: dict[str, Any]) -> "AutomationThresholds":
        result = cls(
            food_emergency_ratio=_number_setting(raw, "food_emergency_ratio"),
            food_low_ratio=_number_setting(raw, "food_low_ratio"),
            goods_critical_supply_ratio=_number_setting(raw, "goods_critical_supply_ratio"),
            goods_shortage_supply_ratio=_number_setting(raw, "goods_shortage_supply_ratio"),
            goods_high_price_ratio=_number_setting(raw, "goods_high_price_ratio"),
            input_shortage_supply_ratio=_number_setting(raw, "input_shortage_supply_ratio"),
            minimum_unemployed_workers=_number_setting(raw, "minimum_unemployed_workers"),
            rgo_budget_cost=_int_setting(raw, "rgo_budget_cost"),
            high_profit=_number_setting(raw, "high_profit"),
            positive_profit=_number_setting(raw, "positive_profit"),
            # Old saturation penalties are retired, not reinterpreted as bonuses.
            expansion_bonus_per_level=_int_setting(raw, "expansion_bonus_per_level", 1),
            upgrade_replacement_bonus=_int_setting(raw, "upgrade_replacement_bonus", 5000),
            economic_score_scale=_number_setting(raw, "economic_score_scale", 10.0),
            engine_min_annual_return_ratio=_number_setting(
                raw, "engine_min_annual_return_ratio", 0.05
            ),
            construction_price_ceiling_ratio=_number_setting(
                raw, "construction_price_ceiling_ratio", 1.50
            ),
            construction_stall_headroom_ratio=_number_setting(
                raw, "construction_stall_headroom_ratio", 0.75
            ),
            irrigation_population_capacity_ratio=_number_setting(
                raw, "irrigation_population_capacity_ratio", 0.90
            ),
            granary_full_ratio=_number_setting(raw, "granary_full_ratio", 0.75),
            food_reserve_months=_number_setting(raw, "food_reserve_months", 6),
        )
        if not 0 <= result.food_emergency_ratio < result.food_low_ratio <= 1:
            raise ValueError("Food thresholds must satisfy 0 <= emergency < low <= 1")
        if not 0 < result.goods_critical_supply_ratio < result.goods_shortage_supply_ratio <= 1:
            raise ValueError("Goods thresholds must satisfy 0 < critical < shortage <= 1")
        if not 0 < result.input_shortage_supply_ratio <= 1:
            raise ValueError("Input shortage ratio must be in (0, 1]")
        if result.goods_high_price_ratio <= 1:
            raise ValueError("High-price ratio must be greater than the default price")
        if (
            result.minimum_unemployed_workers < 0
            or result.expansion_bonus_per_level < 0
            or result.upgrade_replacement_bonus < 0
        ):
            raise ValueError("Worker, expansion, and upgrade thresholds cannot be negative")
        if result.rgo_budget_cost <= 0:
            raise ValueError("RGO budget cost must be positive")
        if result.high_profit < result.positive_profit:
            raise ValueError("High-profit threshold cannot be below the positive-profit threshold")
        if result.economic_score_scale <= 0:
            raise ValueError("Economic score scale must be positive")
        if not 0 <= result.engine_min_annual_return_ratio <= 1:
            raise ValueError("Engine annual return ratio must be between 0 and 1")
        if result.construction_price_ceiling_ratio <= 1:
            raise ValueError("Construction price ceiling ratio must exceed the default price")
        if not 0 < result.construction_stall_headroom_ratio <= 1:
            raise ValueError("Construction stall headroom ratio must be in (0, 1]")
        if not 0 < result.irrigation_population_capacity_ratio <= 1:
            raise ValueError("Irrigation population capacity ratio must be in (0, 1]")
        if not 0 < result.granary_full_ratio <= 1:
            raise ValueError("Granary full ratio must be in (0, 1]")
        if not 0 < result.food_reserve_months <= 60:
            raise ValueError("Food reserve target must be in (0, 60] months")
        return result


@dataclass(frozen=True)
class AutomationLocationScores:
    emergency: int
    critical_shortage: int
    template_role: int
    workforce: int
    population: int
    development: int
    control: int
    market_access: int
    recent_build_penalty: int
    waiting_per_month: int

    @classmethod
    def from_mapping(cls, raw: dict[str, Any]) -> "AutomationLocationScores":
        values = {
            name: _int_setting(raw, name, default)
            for name, default in {
                "emergency": 1000,
                "critical_shortage": 300,
                "template_role": 120,
                "workforce": 80,
                "population": 60,
                "development": 40,
                "control": 40,
                "market_access": 40,
                "recent_build_penalty": -160,
                "waiting_per_month": 8,
            }.items()
        }
        result = cls(**values)
        if result.waiting_per_month <= 0:
            raise ValueError("Waiting compensation must be positive")
        if result.recent_build_penalty > 0:
            raise ValueError("Recent-build weight must be a penalty")
        return result


@dataclass(frozen=True)
class AutomationFailureCooldowns:
    workforce: int
    inputs: int
    oversupply: int
    budget: int
    cash_reserve: int
    vanilla_rejected: int
    no_legal_building: int

    @classmethod
    def from_mapping(cls, raw: dict[str, Any]) -> "AutomationFailureCooldowns":
        defaults = {
            "workforce": 2,
            "inputs": 2,
            "oversupply": 3,
            "budget": 1,
            "cash_reserve": 1,
            "vanilla_rejected": 2,
            "no_legal_building": 3,
        }
        result = cls(**{name: _int_setting(raw, name, default) for name, default in defaults.items()})
        if min(vars(result).values()) < 0:
            raise ValueError("Failure cooldowns cannot be negative")
        return result


@dataclass(frozen=True)
class AutomationRgoScores:
    shortage: int
    high_price: int
    utilization: int
    expansion_space: int
    strategic: int
    cost_penalty: int
    food_emergency: int

    @classmethod
    def from_mapping(cls, raw: dict[str, Any]) -> "AutomationRgoScores":
        defaults = {
            "shortage": 320,
            "high_price": 140,
            "utilization": 100,
            "expansion_space": 80,
            "strategic": 180,
            "cost_penalty": -1,
            "food_emergency": 2000,
        }
        result = cls(**{name: _int_setting(raw, name, default) for name, default in defaults.items()})
        if result.cost_penalty > 0:
            raise ValueError("RGO cost weight must be a penalty")
        return result


@dataclass(frozen=True)
class AutomationWorkforceModel:
    default_fill_deadline_months: int
    maximum_fill_deadline_months: int
    max_penalty: int
    strategic_relief: float

    @classmethod
    def from_mapping(cls, raw: dict[str, Any]) -> "AutomationWorkforceModel":
        result = cls(
            default_fill_deadline_months=_int_setting(
                raw, "default_fill_deadline_months", 12
            ),
            maximum_fill_deadline_months=_int_setting(
                raw, "maximum_fill_deadline_months", WORKFORCE_FORECAST_MAX_MONTHS
            ),
            max_penalty=_int_setting(raw, "max_penalty", 1200),
            strategic_relief=_number_setting(raw, "strategic_relief", 0.5),
        )
        if result.maximum_fill_deadline_months != WORKFORCE_FORECAST_MAX_MONTHS:
            raise ValueError(
                "Workforce fill-deadline maximum must remain "
                f"{WORKFORCE_FORECAST_MAX_MONTHS} months"
            )
        if not 0 <= result.default_fill_deadline_months <= WORKFORCE_FORECAST_MAX_MONTHS:
            raise ValueError(
                "Default workforce fill deadline must be between 0 and "
                f"{WORKFORCE_FORECAST_MAX_MONTHS}"
            )
        if result.max_penalty < 0:
            raise ValueError("Maximum workforce risk penalty cannot be negative")
        if not 0 < result.strategic_relief <= 1:
            raise ValueError("Strategic workforce relief must be in (0, 1]")
        return result


@dataclass(frozen=True)
class AutomationNativeInputFit:
    default_priority: int
    maximum_priority: int
    max_bonus: int
    shortage_discount: float
    high_utilization_discount: float
    low_output_floor: float
    access_control_floor: float

    @classmethod
    def from_mapping(cls, raw: dict[str, Any]) -> "AutomationNativeInputFit":
        result = cls(
            default_priority=_int_setting(raw, "default_priority", 5),
            maximum_priority=_int_setting(raw, "maximum_priority", 10),
            max_bonus=_int_setting(raw, "max_bonus", 500),
            shortage_discount=_number_setting(raw, "shortage_discount", 0.5),
            high_utilization_discount=_number_setting(
                raw, "high_utilization_discount", 0.5
            ),
            low_output_floor=_number_setting(raw, "low_output_floor", 0.25),
            access_control_floor=_number_setting(raw, "access_control_floor", 0.5),
        )
        if result.maximum_priority != 10:
            raise ValueError("Native-input priority maximum must remain 10")
        if not 0 <= result.default_priority <= 10:
            raise ValueError("Default native-input priority must be between 0 and 10")
        if result.max_bonus < 0:
            raise ValueError("Native-input maximum bonus cannot be negative")
        for name in (
            "shortage_discount",
            "high_utilization_discount",
            "low_output_floor",
            "access_control_floor",
        ):
            if not 0 <= getattr(result, name) <= 1:
                raise ValueError(f"Native-input {name} must be between 0 and 1")
        return result


@dataclass(frozen=True)
class AutomationScores:
    food_projected_exhaustion: int
    food_emergency: int
    food_low: int
    food_negative_balance: int
    critical_construction_good: int
    short_construction_good: int
    critical_population_good: int
    short_population_good: int
    critical_military_good: int
    short_military_good: int
    critical_generic_good: int
    short_generic_good: int
    wartime_military_bonus: int
    policy_priority_base: int
    policy_priority_step: int
    role_match: int
    input_shortage_penalty: int
    upstream_source_bonus: int
    high_profit: int
    positive_profit: int
    negative_profit: int

    @classmethod
    def from_mapping(cls, raw: dict[str, Any]) -> "AutomationScores":
        field_names = cls.__dataclass_fields__
        missing = set(field_names) - raw.keys()
        if missing:
            raise ValueError(f"Automation scores missing keys: {sorted(missing)}")
        result = cls(**{name: _int_setting(raw, name) for name in field_names})
        if result.input_shortage_penalty > 0 or result.negative_profit > 0:
            raise ValueError("Input-shortage and negative-profit scores must be penalties")
        for name in field_names:
            if name in {"input_shortage_penalty", "negative_profit"}:
                continue
            if getattr(result, name) < 0:
                raise ValueError(f"Automation score {name} cannot be negative")
        return result


@dataclass(frozen=True)
class AutomationBuildingPriorities:
    minimum: float
    maximum: float
    default: float
    score_per_point: int
    overrides: dict[str, float]

    @classmethod
    def from_mapping(cls, raw: dict[str, Any]) -> "AutomationBuildingPriorities":
        overrides_raw = raw.get("overrides")
        if not isinstance(overrides_raw, dict):
            raise ValueError("Automation building priorities overrides must be a mapping")
        overrides: dict[str, float] = {}
        for building_id, value in overrides_raw.items():
            building_id = require_identifier(
                building_id,
                "Automation building priority id",
            )
            overrides[building_id] = require_finite_number(
                value,
                f"Automation building priority {building_id}",
            )

        result = cls(
            minimum=_number_setting(raw, "minimum"),
            maximum=_number_setting(raw, "maximum"),
            default=_number_setting(raw, "default"),
            score_per_point=_int_setting(raw, "score_per_point"),
            overrides=overrides,
        )
        if result.minimum < 0 or result.maximum <= result.minimum:
            raise ValueError("Automation building priority range must satisfy 0 <= minimum < maximum")
        if not result.minimum <= result.default <= result.maximum:
            raise ValueError("Automation default building priority is outside the configured range")
        if result.score_per_point <= 0:
            raise ValueError("Automation building priority score multiplier must be positive")
        for building_id, value in result.overrides.items():
            if not result.minimum <= value <= result.maximum:
                raise ValueError(
                    f"Automation building priority {building_id}={value:g} is outside "
                    f"{result.minimum:g}-{result.maximum:g}"
                )
        return result

    def value_for(self, building_id: str) -> float:
        return self.overrides.get(building_id, self.default)


@dataclass(frozen=True)
class AutomationRules:
    schema_version: int
    cadence: AutomationCadence
    thresholds: AutomationThresholds
    scores: AutomationScores
    building_priorities: AutomationBuildingPriorities
    location_scores: AutomationLocationScores
    failure_cooldowns: AutomationFailureCooldowns
    rgo_scores: AutomationRgoScores
    workforce_model: AutomationWorkforceModel
    native_input_fit: AutomationNativeInputFit
    goods_groups: dict[str, tuple[str, ...]]
    building_groups: dict[str, tuple[str, ...]]

    @classmethod
    def from_mapping(cls, raw: dict[str, Any]) -> "AutomationRules":
        raw = require_mapping(raw, "Automation rules")
        version = _int_setting(raw, "schema_version", 0)
        if version not in {2, 3, 4, 5}:
            raise ValueError(f"Unsupported automation rules schema version: {version}")
        goods_groups = _tuple_mapping(raw, "goods_groups")
        missing_groups = REQUIRED_GOODS_GROUPS - goods_groups.keys()
        if missing_groups:
            raise ValueError(f"Automation rules missing goods groups: {sorted(missing_groups)}")
        return cls(
            schema_version=version,
            cadence=AutomationCadence.from_mapping(_section(raw, "cadence")),
            thresholds=AutomationThresholds.from_mapping(_section(raw, "thresholds")),
            scores=AutomationScores.from_mapping(_section(raw, "scores")),
            building_priorities=AutomationBuildingPriorities.from_mapping(
                _section(raw, "building_priorities")
            ),
            location_scores=AutomationLocationScores.from_mapping(
                require_mapping(raw.get("location_scores", {}), "Automation location scores")
            ),
            failure_cooldowns=AutomationFailureCooldowns.from_mapping(
                require_mapping(raw.get("failure_cooldowns", {}), "Automation failure cooldowns")
            ),
            rgo_scores=AutomationRgoScores.from_mapping(
                require_mapping(raw.get("rgo_scores", {}), "Automation RGO scores")
            ),
            workforce_model=AutomationWorkforceModel.from_mapping(
                require_mapping(raw.get("workforce_model", {}), "Automation workforce model")
            ),
            native_input_fit=AutomationNativeInputFit.from_mapping(
                require_mapping(raw.get("native_input_fit", {}), "Automation native input fit")
            ),
            goods_groups=goods_groups,
            building_groups=_tuple_mapping(raw, "building_groups"),
        )

    @property
    def food_goods(self) -> frozenset[str]:
        return frozenset(self.goods_groups["food"])

    @property
    def construction_goods(self) -> frozenset[str]:
        return frozenset(
            self.goods_groups["construction_core"]
            + self.goods_groups["construction_secondary"]
        )

    @property
    def essential_goods(self) -> frozenset[str]:
        return frozenset(
            self.goods_groups["food"]
            + self.goods_groups["construction_core"]
            + self.goods_groups["construction_secondary"]
            + self.goods_groups["population_basic"]
            + self.goods_groups["military"]
        )

    @property
    def input_goods(self) -> frozenset[str]:
        return frozenset(self.goods_groups["industrial_inputs"])

    def goods_groups_for(self, good: str) -> frozenset[str]:
        return frozenset(group for group, goods in self.goods_groups.items() if good in goods)

    def building_groups_for(self, building_id: str) -> frozenset[str]:
        return frozenset(group for group, ids in self.building_groups.items() if building_id in ids)

    def building_priority_for(self, building_id: str) -> float:
        return self.building_priorities.value_for(building_id)


def load_automation_rules(path: Path) -> AutomationRules:
    data = require_mapping(load_json(path), "Automation rules file")
    return AutomationRules.from_mapping(data)
