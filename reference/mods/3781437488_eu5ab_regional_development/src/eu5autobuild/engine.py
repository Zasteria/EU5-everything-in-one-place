"""Pure Python decision engine for the bounded EU5AB regional economy loop."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from enum import StrEnum
import math
from typing import Callable

from .policy import BuildingCatalog, Policy
from . import building_capacity, output_prices, construction_slots, production_ledger
from .rgo_automation import high_price_factor, price_factor
from .food_infrastructure import (
    GRANARY_BUILDINGS, NON_RECIPE_FOOD_BUILDINGS, RGO_BOOST_GOODS, granary_monthly_savings,
    windmill_incremental_revenue,
)
from .rules import AutomationRules, WORKFORCE_FORECAST_MAX_MONTHS


class PauseReason(StrEnum):
    NONE = "none"
    BANNED_BUILDING = "banned_building"
    NOT_ALLOWED = "not_allowed"
    NOT_UNLOCKED = "not_unlocked"
    SUPERSEDED_BUILDING = "superseded_building"
    PRIORITY_DISABLED = "priority_disabled"
    LABOR_SHORTAGE = "labor_shortage"
    INPUT_SHORTAGE = "input_shortage"
    POPULATION_SHORTAGE = "population_shortage"
    SPECIAL_BUILDING_DISABLED = "special_building_disabled"
    CASH_RESERVE = "cash_reserve"
    PRICE_OUT_OF_RANGE = "price_out_of_range"
    BUDGET_EXHAUSTED = "budget_exhausted"
    CONSTRUCTION_QUEUE = "construction_queue"
    COOLDOWN = "cooldown"
    FAILURE_COOLDOWN = "failure_cooldown"
    RGO_DISABLED = "rgo_disabled"
    RGO_UTILIZATION = "rgo_utilization"
    RGO_QUOTA = "rgo_quota"
    RGO_NEGATIVE_SCORE = "rgo_negative_score"
    VANILLA_REJECTED = "vanilla_rejected"
    NO_CANDIDATE = "no_candidate"
    NO_IRRIGATION_NEED = "no_irrigation_need"
    NO_GRANARY_NEED = "no_granary_need"
    STORAGE_PROJECT_PENDING = "storage_project_pending"
    NO_WINDMILL_NEED = "no_windmill_need"
    PENDING_OUTPUT = "pending_output"
    BUILDING_CAPACITY = "building_capacity"
    BUILDING_CAPACITY_UNAVAILABLE = "building_capacity_unavailable"


class WorkforceState(StrEnum):
    CURRENT_SUFFICIENT = "current_sufficient"
    WITHIN_DEADLINE = "within_deadline"
    BEYOND_DEADLINE = "beyond_deadline"
    NO_PROMOTION_PATH = "no_promotion_path"
    ZERO_PROMOTION_RATE = "zero_promotion_rate"
    TARGET_CAP = "target_cap"
    PREDICTION_UNAVAILABLE = "prediction_unavailable"


@dataclass(frozen=True)
class WorkforceRequirement:
    pop_type: str
    current_unfilled_jobs: float = 0.0
    new_jobs: float = 0.0
    queued_reserved_jobs: float = 0.0
    immediately_employable: float = 0.0
    promotion_capacity: float | None = None

    @property
    def demand(self) -> float:
        return max(
            0.0,
            self.current_unfilled_jobs + self.new_jobs + self.queued_reserved_jobs,
        )

    @property
    def gap(self) -> float:
        return max(0.0, self.demand - self.immediately_employable)


@dataclass(frozen=True)
class PromotionSource:
    id: str
    pop_type: str
    population: float
    monthly_amount: float
    promote_to: tuple[str, ...]


@dataclass(frozen=True)
class WorkforceAssessment:
    state: WorkforceState
    deadline_months: int
    months_to_fill: int | None
    total_demand: float
    total_gap: float
    slowest_pop_type: str | None
    source_population: float
    monthly_promotion: float
    reliable: bool

    @property
    def within_deadline(self) -> bool:
        return self.state in {
            WorkforceState.CURRENT_SUFFICIENT,
            WorkforceState.WITHIN_DEADLINE,
        }


class NativeInputMethod(StrEnum):
    NONE = "none"
    PROXY = "proxy"
    EXACT = "exact"


@dataclass(frozen=True)
class NativeInputAssessment:
    method: NativeInputMethod
    score: int
    coverage: float
    matched_inputs: tuple[str, ...]
    total_raw_input: float
    shortage_factor: float
    output_factor: float
    utilization_factor: float
    access_factor: float
    control_factor: float


def _promotion_flow(
    requirements: tuple[WorkforceRequirement, ...],
    sources: tuple[PromotionSource, ...],
    months: int,
) -> float:
    """Return a bounded bipartite max-flow without double-counting sources."""

    gaps: dict[str, float] = {}
    for requirement in requirements:
        gaps[requirement.pop_type] = gaps.get(requirement.pop_type, 0.0) + requirement.gap
    active_targets = tuple(sorted(pop_type for pop_type, gap in gaps.items() if gap > 0))
    active_sources = tuple(
        source
        for source in sources
        if source.population > 0
        and source.monthly_amount > 0
        and set(source.promote_to) & set(active_targets)
    )
    source_nodes = tuple(f"source:{index}" for index in range(len(active_sources)))
    graph: dict[str, dict[str, float]] = {}

    def add_edge(start: str, end: str, capacity: float) -> None:
        graph.setdefault(start, {})[end] = max(0.0, capacity)
        graph.setdefault(end, {}).setdefault(start, 0.0)

    for index, source in enumerate(active_sources):
        source_node = source_nodes[index]
        capacity = min(source.population, source.monthly_amount * months)
        add_edge("start", source_node, capacity)
        for target in active_targets:
            if target in source.promote_to:
                add_edge(source_node, f"target:{target}", capacity)
    for target in active_targets:
        add_edge(f"target:{target}", "end", gaps[target])

    total = 0.0
    epsilon = 1e-9
    while True:
        parents: dict[str, str | None] = {"start": None}
        queue: deque[str] = deque(["start"])
        while queue and "end" not in parents:
            current = queue.popleft()
            for neighbor, capacity in graph.get(current, {}).items():
                if capacity > epsilon and neighbor not in parents:
                    parents[neighbor] = current
                    queue.append(neighbor)
        if "end" not in parents:
            break
        amount = float("inf")
        current = "end"
        while parents[current] is not None:
            previous = parents[current]
            amount = min(amount, graph[previous][current])
            current = previous
        current = "end"
        while parents[current] is not None:
            previous = parents[current]
            graph[previous][current] -= amount
            graph[current][previous] += amount
            current = previous
        total += amount
    return total


def assess_workforce(
    requirements: tuple[WorkforceRequirement, ...],
    sources: tuple[PromotionSource, ...],
    deadline_months: int,
    *,
    prediction_reliable: bool = True,
    diagnostic_horizon_months: int | None = None,
    is_rgo: bool = False,
) -> WorkforceAssessment:
    """Classify current, forecast-fillable, and unsafe workforce states.

    Only direct vanilla promote_to edges supplied by callers are considered.
    Source capacity is shared through max-flow, so one source population cannot
    be counted once for every requested target class.
    """

    if not isinstance(deadline_months, int) or isinstance(deadline_months, bool):
        raise ValueError("Workforce fill deadline must be an integer")
    maximum = 1200 if is_rgo else WORKFORCE_FORECAST_MAX_MONTHS
    if not 0 <= deadline_months <= maximum:
        raise ValueError(
            "Workforce fill deadline must be between 0 and "
            f"{maximum} months"
        )
    if diagnostic_horizon_months is None:
        diagnostic_horizon_months = max(120, deadline_months)
    if not isinstance(diagnostic_horizon_months, int) or isinstance(
        diagnostic_horizon_months, bool
    ):
        raise ValueError("Diagnostic workforce horizon must be an integer")
    if diagnostic_horizon_months < deadline_months:
        raise ValueError("Diagnostic workforce horizon cannot be below the deadline")
    if any(
        not math.isfinite(value)
        for requirement in requirements
        for value in (
            requirement.current_unfilled_jobs,
            requirement.new_jobs,
            requirement.queued_reserved_jobs,
            requirement.immediately_employable,
        )
    ):
        raise ValueError("Workforce requirements must contain finite populations")
    if any(
        value < 0
        for requirement in requirements
        for value in (
            requirement.current_unfilled_jobs,
            requirement.new_jobs,
            requirement.queued_reserved_jobs,
            requirement.immediately_employable,
        )
    ):
        raise ValueError("Workforce requirements cannot contain negative populations")
    if any(
        requirement.promotion_capacity is not None
        and not math.isfinite(requirement.promotion_capacity)
        for requirement in requirements
    ):
        raise ValueError("Workforce promotion capacity must be finite")
    if any(
        requirement.promotion_capacity is not None
        and requirement.promotion_capacity < 0
        for requirement in requirements
    ):
        raise ValueError("Workforce promotion capacity cannot be negative")
    if any(
        not math.isfinite(source.population) or not math.isfinite(source.monthly_amount)
        for source in sources
    ):
        raise ValueError("Promotion sources must contain finite populations and rates")
    if any(source.population < 0 or source.monthly_amount < 0 for source in sources):
        raise ValueError("Promotion sources cannot contain negative populations or rates")

    total_demand = sum(requirement.demand for requirement in requirements)
    total_gap = sum(requirement.gap for requirement in requirements)
    eligible_sources = tuple(
        source
        for source in sources
        if any(
            requirement.gap > 0 and requirement.pop_type in source.promote_to
            for requirement in requirements
        )
    )
    source_population = sum(source.population for source in eligible_sources)
    monthly_promotion = sum(source.monthly_amount for source in eligible_sources)
    slowest_pop_type = None
    positive_requirements = tuple(
        requirement for requirement in requirements if requirement.gap > 0
    )
    if positive_requirements:
        def target_month_ratio(requirement: WorkforceRequirement) -> float:
            rate = sum(
                source.monthly_amount
                for source in eligible_sources
                if requirement.pop_type in source.promote_to
            )
            return float("inf") if rate <= 0 else requirement.gap / rate

        slowest_pop_type = max(
            positive_requirements,
            key=lambda requirement: (
                target_month_ratio(requirement),
                requirement.pop_type,
            ),
        ).pop_type

    def result(
        state: WorkforceState,
        months_to_fill: int | None,
        reliable: bool,
    ) -> WorkforceAssessment:
        return WorkforceAssessment(
            state=state,
            deadline_months=deadline_months,
            months_to_fill=months_to_fill,
            total_demand=total_demand,
            total_gap=total_gap,
            slowest_pop_type=slowest_pop_type,
            source_population=source_population,
            monthly_promotion=monthly_promotion,
            reliable=reliable,
        )

    if total_gap <= 1e-9:
        return result(WorkforceState.CURRENT_SUFFICIENT, 0, True)
    if not prediction_reliable:
        return result(WorkforceState.PREDICTION_UNAVAILABLE, None, False)
    if any(
        requirement.promotion_capacity is not None
        and requirement.promotion_capacity + 1e-9 < requirement.gap
        for requirement in positive_requirements
    ):
        return result(WorkforceState.TARGET_CAP, None, True)
    if any(
        not any(
            source.population > 0 and requirement.pop_type in source.promote_to
            for source in sources
        )
        for requirement in positive_requirements
    ):
        return result(WorkforceState.NO_PROMOTION_PATH, None, True)
    if any(
        not any(
            source.population > 0
            and source.monthly_amount > 0
            and requirement.pop_type in source.promote_to
            for source in sources
        )
        for requirement in positive_requirements
    ):
        return result(WorkforceState.ZERO_PROMOTION_RATE, None, True)

    earliest = next(
        (
            months
            for months in range(1, diagnostic_horizon_months + 1)
            if _promotion_flow(requirements, sources, months) + 1e-9 >= total_gap
        ),
        None,
    )
    if earliest is not None and earliest <= deadline_months:
        return result(WorkforceState.WITHIN_DEADLINE, earliest, True)
    return result(WorkforceState.BEYOND_DEADLINE, earliest, True)


def workforce_risk_penalty(
    assessment: WorkforceAssessment,
    *,
    max_penalty: int,
    strategic_relief: float = 1.0,
) -> int:
    if max_penalty < 0:
        raise ValueError("Maximum workforce penalty cannot be negative")
    if not 0 < strategic_relief <= 1:
        raise ValueError("Strategic workforce relief must be in (0, 1]")
    if assessment.state is WorkforceState.CURRENT_SUFFICIENT:
        return 0
    if assessment.state is not WorkforceState.WITHIN_DEADLINE:
        return -max_penalty
    demand_fraction = min(
        1.0,
        assessment.total_gap / max(assessment.total_demand, 1.0),
    )
    time_fraction = min(
        1.0,
        (assessment.months_to_fill or assessment.deadline_months)
        / max(assessment.deadline_months, 1),
    )
    return -round(max_penalty * demand_fraction * time_fraction * strategic_relief)


def assess_native_input_fit(
    input_quantities: dict[str, float],
    raw_input_goods: frozenset[str],
    province_raw_goods: frozenset[str],
    *,
    priority: int,
    max_bonus: int,
    shortage_goods: frozenset[str] = frozenset(),
    output_ratio: float = 1.0,
    raw_input_utilization: float = 0.0,
    market_access: float = 1.0,
    control: float = 1.0,
    exact_vanilla_coverage: float | None = None,
    is_rgo: bool = False,
    shortage_discount: float = 0.5,
    high_utilization_discount: float = 0.5,
    low_output_floor: float = 0.25,
    access_control_floor: float = 0.5,
) -> NativeInputAssessment:
    """Return one bounded PM-dependent native-input score.

    exact_vanilla_coverage, when available, replaces the proxy rather than being
    added to it. This prevents double-counting the same vanilla efficiency.
    """

    if not isinstance(priority, int) or isinstance(priority, bool):
        raise ValueError("Native-input priority must be an integer")
    if not 0 <= priority <= 10:
        raise ValueError("Native-input priority must be between 0 and 10")
    if not isinstance(max_bonus, int) or isinstance(max_bonus, bool):
        raise ValueError("Native-input maximum bonus must be an integer")
    if max_bonus < 0:
        raise ValueError("Native-input maximum bonus cannot be negative")
    if any(
        not isinstance(quantity, (int, float))
        or isinstance(quantity, bool)
        or not math.isfinite(quantity)
        for quantity in input_quantities.values()
    ):
        raise ValueError("Production-method input quantities must be finite numbers")
    if any(quantity < 0 for quantity in input_quantities.values()):
        raise ValueError("Production-method input quantities cannot be negative")
    numeric_factors = (
        (output_ratio, "output ratio"),
        (raw_input_utilization, "raw-input utilization"),
        (market_access, "market access"),
        (control, "control"),
        (shortage_discount, "shortage discount"),
        (high_utilization_discount, "utilization discount"),
        (low_output_floor, "output floor"),
        (access_control_floor, "access/control floor"),
    )
    for value, name in numeric_factors:
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
            raise ValueError(f"Native-input {name} must be a finite number")
    if exact_vanilla_coverage is not None and (
        not isinstance(exact_vanilla_coverage, (int, float))
        or isinstance(exact_vanilla_coverage, bool)
        or not math.isfinite(exact_vanilla_coverage)
    ):
        raise ValueError("Native-input exact coverage must be a finite number")
    for value, name in (
        (shortage_discount, "shortage discount"),
        (high_utilization_discount, "utilization discount"),
        (low_output_floor, "output floor"),
        (access_control_floor, "access/control floor"),
    ):
        if not 0 <= value <= 1:
            raise ValueError(f"Native-input {name} must be between 0 and 1")

    raw_inputs = {
        good: quantity
        for good, quantity in input_quantities.items()
        if good in raw_input_goods and quantity > 0
    }
    total_raw_input = sum(raw_inputs.values())
    matched_inputs = tuple(sorted(set(raw_inputs) & province_raw_goods))
    empty = NativeInputAssessment(
        method=NativeInputMethod.NONE,
        score=0,
        coverage=0.0,
        matched_inputs=(),
        total_raw_input=total_raw_input,
        shortage_factor=1.0,
        output_factor=1.0,
        utilization_factor=1.0,
        access_factor=1.0,
        control_factor=1.0,
    )
    if is_rgo or priority == 0 or total_raw_input <= 0:
        return empty

    if exact_vanilla_coverage is not None:
        method = NativeInputMethod.EXACT
        coverage = max(0.0, min(1.0, exact_vanilla_coverage))
    else:
        method = NativeInputMethod.PROXY
        coverage = sum(raw_inputs[good] for good in matched_inputs) / total_raw_input

    shortage_weight = sum(
        quantity for good, quantity in raw_inputs.items() if good in shortage_goods
    )
    shortage_factor = 1.0 - (
        (1.0 - shortage_discount) * shortage_weight / total_raw_input
    )
    output_factor = max(low_output_floor, min(1.0, output_ratio))
    utilization = max(0.0, min(1.0, raw_input_utilization))
    utilization_factor = 1.0 - utilization * (1.0 - high_utilization_discount)
    access_factor = access_control_floor + (
        1.0 - access_control_floor
    ) * max(0.0, min(1.0, market_access))
    control_factor = access_control_floor + (
        1.0 - access_control_floor
    ) * max(0.0, min(1.0, control))
    score = round(
        max_bonus
        * (priority / 10)
        * coverage
        * shortage_factor
        * output_factor
        * utilization_factor
        * access_factor
        * control_factor
    )
    return NativeInputAssessment(
        method=method,
        score=max(0, min(max_bonus, score)),
        coverage=coverage,
        matched_inputs=matched_inputs,
        total_raw_input=total_raw_input,
        shortage_factor=shortage_factor,
        output_factor=output_factor,
        utilization_factor=utilization_factor,
        access_factor=access_factor,
        control_factor=control_factor,
    )


@dataclass(frozen=True)
class BuildingCandidate:
    id: str
    output_goods: tuple[str, ...]
    cost: int
    price_ratio: float | None
    labor_available: bool = True
    inputs_available: bool = True
    input_shortages: tuple[str, ...] = ()
    local_pop_available: bool = True
    is_special: bool = False
    base_score: int = 0
    input_goods: tuple[str, ...] = ()
    potential_profit: float = 0.0
    available_workers: float | None = None
    existing_levels: int = 0
    strategic_tags: tuple[str, ...] = ()
    is_rgo: bool = False
    rgo_utilization: float = 1.0
    rgo_expansion_space: int = 0
    consecutive_expansions: int = 0  # Legacy input, ignored.
    recent_same_rgo: bool = False
    expected_output_value: float | None = None
    expected_input_cost: float | None = None
    construction_cost: float | None = None
    unlocked: bool = True
    newer_replacement_unlocked: bool = False
    upgradeable_predecessor_levels: int = 0
    counts_towards_building_capacity: bool = True
    predecessor_counts_towards_building_capacity: bool = True
    workforce_assessment: WorkforceAssessment | None = None
    native_input_assessment: NativeInputAssessment | None = None
    output_prices: tuple[output_prices.OutputPrice, ...] | None = None
    # Explicit monthly net outputs activate the production-ledger contract.
    # None keeps older economic-only callers usable; runtime always supplies it.
    net_monthly_outputs: dict[str, float] | None = None
    output_base_prices: dict[str, float] = field(default_factory=dict)
    production_identity_known: bool = True


@dataclass(frozen=True)
class GoodsMarketState:
    supply: float
    demand: float
    price_ratio: float = 1.0
    stockpile: float = 0.0
    pending_output: float = 0.0
    future_input: float = 0.0
    pending_known: bool = True

    @property
    def supply_ratio(self) -> float:
        if self.demand <= 0:
            return float("inf")
        return self.supply / self.demand


@dataclass(frozen=True)
class MarketState:
    goods: dict[str, GoodsMarketState] = field(default_factory=dict)
    food_stockpile_ratio: float = 1.0
    monthly_food_balance: float = 0.0
    projected_food_exhaustion: bool = False
    available: bool = True


@dataclass(frozen=True)
class CountryState:
    at_war: bool = False
    manpower_ratio: float = 1.0
    sailors_ratio: float = 1.0
    monthly_balance: float = 0.0
    active_mod_constructions: int = 0
    economic_metric: int = 1
    emergency_food_exhaustion_override: bool = True
    emergency_food_stockpile_override: bool = True


@dataclass(frozen=True)
class LocationState:
    id: str = ""
    covered: bool = True
    civil_constructions: int = 0
    parallel_construction_limit: int | None = 1
    reserved_construction_slots: int = 0
    cooldown_months: int = 0
    failure_cooldown_months: int = 0
    market_access: float = 1.0
    control: float = 1.0
    population: float = 0.0
    development: float = 0.0
    unemployed_workers: float = 0.0
    total_building_levels: int = 0
    fully_staffed_building_levels: float | None = None
    supported_building_levels: float | None = None
    recently_built: bool = False
    waiting_months: int = 0
    template_role_match: bool = False
    critical_shortage: bool = False
    emergency: bool = False
    population_capacity: float | None = None
    raw_material: str = ""
    raw_material_output: float = 0.0
    province_food_capacity: float = 0.0
    province_food_ratio: float = 0.0
    province_monthly_food_production: float = 0.0
    province_food_balance: float | None = None
    province_natural_food_balance: float | None = None
    province_granary_pending: bool = False
    province_monthly_food_consumption: float | None = None
    province_food_stock: float | None = None
    province_food_price: float | None = None
    is_province_capital: bool = False
    province_food_decay_base: float | None = None  # Capital local + owner global.
    province_food_preservation: float | None = None  # Actual sum across locations.
    rgo_monthly_revenue: float | None = None
    rgo_output_factor: float | None = None


@dataclass(frozen=True)
class AutomationContext:
    market: MarketState = field(default_factory=MarketState)
    country: CountryState = field(default_factory=CountryState)
    location: LocationState = field(default_factory=LocationState)


@dataclass(frozen=True)
class BuildDecision:
    building_id: str | None
    reason: PauseReason
    score: int = 0

    @property
    def should_build(self) -> bool:
        return self.building_id is not None and self.reason is PauseReason.NONE


@dataclass(frozen=True)
class LocationScore:
    location_id: str
    score: int
    components: dict[str, int]
    emergency: bool = False


@dataclass(frozen=True)
class RankedCandidate:
    candidate: BuildingCandidate
    score: int
    components: dict[str, int]


@dataclass(frozen=True)
class BuildExecution:
    building_id: str | None
    reason: PauseReason
    attempted_buildings: tuple[str, ...] = ()
    rejected_buildings: tuple[str, ...] = ()
    score: int = 0
    budget_spent: int = 0
    cooldown_months: int = 0
    quota_used: int = 0
    rgo_quota_used: int = 0

    @property
    def succeeded(self) -> bool:
        return self.building_id is not None and self.reason is PauseReason.NONE


def calculate_monthly_quota(
    covered_locations: int,
    *,
    user_hard_cap: int,
    budget_remaining: int,
    cash_available: int,
    min_cash_reserve: int,
    active_mod_constructions: int,
    rules: AutomationRules,
) -> int:
    """Return free slots using only this Mod's projects, budget, and cash rules."""
    if covered_locations <= 0:
        return 0
    concurrent_target = min(
        max(0, user_hard_cap) + 1,
        rules.cadence.max_country_concurrent_projects,
    )
    quota = max(0, concurrent_target - max(0, active_mod_constructions))
    if budget_remaining <= 0 or cash_available <= min_cash_reserve:
        return 0
    return quota


def low_cost_location_reason(location: LocationState, rules: AutomationRules) -> PauseReason:
    """Perform only checks that do not enumerate building types or market recipes."""
    if not location.covered:
        return PauseReason.NOT_ALLOWED
    if construction_slots.remaining(location.parallel_construction_limit, location.civil_constructions, location.reserved_construction_slots) <= 0:
        return PauseReason.CONSTRUCTION_QUEUE
    if location.cooldown_months > 0:
        return PauseReason.COOLDOWN
    if location.failure_cooldown_months > 0:
        return PauseReason.FAILURE_COOLDOWN
    return PauseReason.NONE


def score_location(location: LocationState, rules: AutomationRules) -> LocationScore:
    weights = rules.location_scores
    components = {
        "emergency": weights.emergency if location.emergency else 0,
        "critical_shortage": weights.critical_shortage if location.critical_shortage else 0,
        "template_role": weights.template_role if location.template_role_match else 0,
        "workforce": (
            weights.workforce
            if location.unemployed_workers >= rules.thresholds.minimum_unemployed_workers
            else 0
        ),
        "population": round(weights.population * min(1.0, location.population / 100_000)),
        "development": round(weights.development * min(1.0, location.development / 50)),
        "control": round(weights.control * max(0.0, min(1.0, location.control))),
        "market_access": round(
            weights.market_access * max(0.0, min(1.0, location.market_access))
        ),
        "recent_build": weights.recent_build_penalty if location.recently_built else 0,
        "waiting": location.waiting_months * weights.waiting_per_month,
    }
    return LocationScore(
        location_id=location.id,
        score=sum(components.values()),
        components=components,
        emergency=location.emergency,
    )


def select_locations_for_deep_scoring(
    locations: list[LocationState],
    rules: AutomationRules,
    *,
    remaining_slots: int | None = None,
) -> tuple[list[LocationScore], dict[PauseReason, int]]:
    """Filter every covered location cheaply, then deeply inspect a bounded pool.

    Emergencies lead the shared pool. Linear waiting compensation is unbounded,
    so a persistently eligible location eventually outranks locations with
    bounded demographic and market scores.
    """
    passed: list[LocationScore] = []
    failures: dict[PauseReason, int] = {}
    for location in locations:
        reason = low_cost_location_reason(location, rules)
        if reason is not PauseReason.NONE:
            failures[reason] = failures.get(reason, 0) + 1
            continue
        passed.append(score_location(location, rules))

    ranked = sorted(passed, key=lambda item: (-item.score, item.location_id))
    emergencies = [item for item in ranked if item.emergency]
    normal = [item for item in ranked if not item.emergency]
    pool_limit = rules.cadence.deep_score_location_limit
    if remaining_slots is not None:
        pool_limit = min(
            pool_limit,
            max(0, remaining_slots) * rules.cadence.deep_score_quota_multiplier,
        )
    return (emergencies + normal)[:pool_limit], failures


def _shortage_level(state: GoodsMarketState | None, rules: AutomationRules) -> int:
    if state is None:
        return 0
    if state.supply_ratio <= rules.thresholds.goods_critical_supply_ratio:
        return 2
    if state.supply_ratio <= rules.thresholds.goods_shortage_supply_ratio:
        return 1
    return 0


def _candidate_groups(candidate: BuildingCandidate, rules: AutomationRules) -> frozenset[str]:
    return frozenset(candidate.strategic_tags) | rules.building_groups_for(candidate.id)


def _effective_output_goods(candidate: BuildingCandidate, context: AutomationContext | None) -> tuple[str, ...]:
    if candidate.id in RGO_BOOST_GOODS:
        if context is not None and context.location.raw_material_output > 0:
            good = context.location.raw_material
            if good in RGO_BOOST_GOODS[candidate.id]:
                return (good,)
        return ()
    if candidate.id in NON_RECIPE_FOOD_BUILDINGS:
        return ()
    return candidate.output_goods


def _output_price_ratio(candidate: BuildingCandidate, context: AutomationContext | None) -> float | None:
    if candidate.id in RGO_BOOST_GOODS:
        for good in _effective_output_goods(candidate, context):
            state = context.market.goods.get(good)
            if context.market.available and state is not None:
                return state.price_ratio
        return None
    return None if candidate.id in NON_RECIPE_FOOD_BUILDINGS else candidate.price_ratio


def _supports_food(candidate: BuildingCandidate, context: AutomationContext, rules: AutomationRules) -> bool:
    return candidate.id == "irrigation_systems" or bool(set(_effective_output_goods(candidate, context)) & rules.food_goods)


def candidate_price_assessment(policy: Policy, candidate: BuildingCandidate,
                               context: AutomationContext | None,
                               rules: AutomationRules | None) -> tuple[float, float]:
    goods = _effective_output_goods(candidate, context)
    if not goods:
        return 1.0, 0.0
    if context is not None and not context.market.available:
        return 0.0, 0.0
    readings = candidate.output_prices
    if readings is None:
        # The scalar is an explicitly supplied local-market reading for a single
        # output. Multi-output callers must provide quantities and base prices.
        if len(goods) != 1:
            return 0.0, 0.0
        state = context.market.goods.get(goods[0]) if context is not None else None
        ratio = state.price_ratio if state is not None else _output_price_ratio(candidate, context)
        readings = (output_prices.OutputPrice(1, 1, ratio),)
    return output_prices.assess(readings, policy.min_price_ratio * 100,
                                policy.max_price_ratio * 100,
                                emergency=_food_emergency(candidate, context, rules))


def food_demand_present(context: AutomationContext, rules: AutomationRules) -> bool:
    market, thresholds = context.market, rules.thresholds
    return market.available and (
        market.projected_food_exhaustion
        or market.food_stockpile_ratio <= thresholds.food_emergency_ratio
        or (market.food_stockpile_ratio <= thresholds.food_low_ratio and market.monthly_food_balance < 0)
    )


def granary_demand_present(context: AutomationContext, rules: AutomationRules) -> bool:
    location = context.location
    consumption = location.province_monthly_food_consumption
    return (location.province_food_capacity > 0
            and location.province_food_ratio >= rules.thresholds.granary_full_ratio
            and consumption is not None and math.isfinite(consumption)
            and location.province_food_capacity < abs(consumption) * rules.thresholds.food_reserve_months)


def food_building_profit(candidate: BuildingCandidate, context: AutomationContext) -> float | None:
    location = context.location
    if candidate.id == 'windmill':
        addition = windmill_incremental_revenue(location.rgo_monthly_revenue, location.rgo_output_factor)
    elif candidate.id in GRANARY_BUILDINGS:
        saved = granary_monthly_savings(location.province_food_stock, location.province_food_decay_base,
                                       location.province_food_preservation)
        price = location.province_food_price
        addition = saved * price if saved is not None and price is not None and math.isfinite(price) and price >= 0 else None
    else:
        return candidate.potential_profit
    return candidate.potential_profit + addition if addition is not None else None


def granary_decay_return_present(candidate: BuildingCandidate, context: AutomationContext,
                                 rules: AutomationRules) -> bool:
    location = context.location
    saved = granary_monthly_savings(location.province_food_stock, location.province_food_decay_base,
                                   location.province_food_preservation)
    profit = food_building_profit(candidate, context)
    return (saved is not None and saved > 0 and location.province_food_price is not None
            and location.province_food_price > 0 and profit is not None and profit > 0
            and profit >= candidate.cost * rules.thresholds.engine_min_annual_return_ratio / 12)


def windmill_demand_present(context: AutomationContext, rules: AutomationRules, high_price_ratio: float) -> bool:
    location = context.location
    if (not context.market.available or location.raw_material_output <= 0
            or location.raw_material not in RGO_BOOST_GOODS["windmill"]):
        return False
    state = context.market.goods.get(location.raw_material)
    return food_demand_present(context, rules) or (state is not None and (
        state.supply < state.demand or state.price_ratio > high_price_ratio
    ))


def irrigation_demand_present(context: AutomationContext, rules: AutomationRules) -> bool:
    """Same present-state gate as the generated native triggers; no growth forecast."""
    location, thresholds = context.location, rules.thresholds
    capacity = location.population_capacity
    population_need = (
        capacity is not None
        and capacity > 0
        and location.population / capacity >= thresholds.irrigation_population_capacity_ratio
    )
    return population_need or food_demand_present(context, rules)


def _addresses_critical_need(
    candidate: BuildingCandidate,
    context: AutomationContext | None,
    rules: AutomationRules | None,
) -> bool:
    if context is None or rules is None:
        return False
    outputs = set(_effective_output_goods(candidate, context))
    if _supports_food(candidate, context, rules) and context.market.available and (
        context.market.projected_food_exhaustion
        or context.market.food_stockpile_ratio <= rules.thresholds.food_emergency_ratio
        or context.market.monthly_food_balance < 0
    ):
        return True
    return any(
        good in rules.essential_goods
        and _shortage_level(context.market.goods.get(good), rules) == 2
        for good in outputs
    )


def _goods_need_score(
    candidate: BuildingCandidate,
    context: AutomationContext,
    rules: AutomationRules,
) -> int:
    scores = rules.scores
    output_goods = set(_effective_output_goods(candidate, context))
    components: list[int] = []

    if _supports_food(candidate, context, rules) and context.market.available:
        if context.market.projected_food_exhaustion:
            components.append(scores.food_projected_exhaustion)
        elif context.market.food_stockpile_ratio <= rules.thresholds.food_emergency_ratio:
            components.append(scores.food_emergency)
        elif context.market.food_stockpile_ratio <= rules.thresholds.food_low_ratio:
            components.append(scores.food_low)
        if context.market.monthly_food_balance < 0:
            components.append(scores.food_negative_balance)

    construction_goods = rules.construction_goods
    population_goods = set(rules.goods_groups["population_basic"])
    military_goods = set(rules.goods_groups["military"])
    for good in output_goods:
        shortage = _shortage_level(context.market.goods.get(good), rules)
        if shortage == 0:
            continue
        if good in construction_goods:
            components.append(
                scores.critical_construction_good if shortage == 2 else scores.short_construction_good
            )
        elif good in population_goods:
            components.append(
                scores.critical_population_good if shortage == 2 else scores.short_population_good
            )
        elif good in military_goods:
            components.append(
                scores.critical_military_good if shortage == 2 else scores.short_military_good
            )
        else:
            components.append(scores.critical_generic_good if shortage == 2 else scores.short_generic_good)

    # Only the two strongest market signals count. This prevents a broad output list
    # from winning merely because it enumerates more goods than a focused producer.
    need_score = sum(sorted(components, reverse=True)[:2])
    if context.country.at_war and output_goods & military_goods:
        need_score += scores.wartime_military_bonus
    return need_score


def _food_emergency(candidate, context, rules) -> bool:
    return bool(context and rules and context.market.available
                and _supports_food(candidate, context, rules) and (
                    context.country.emergency_food_exhaustion_override
                    and context.market.projected_food_exhaustion
                    or context.country.emergency_food_stockpile_override
                    and context.market.food_stockpile_ratio <= rules.thresholds.food_emergency_ratio))


def _current_workers_sufficient(candidate: BuildingCandidate) -> bool:
    if candidate.workforce_assessment is not None:
        return candidate.workforce_assessment.state is WorkforceState.CURRENT_SUFFICIENT
    return candidate.labor_available


def candidate_capacity_factor(candidate: BuildingCandidate, context: AutomationContext | None) -> float:
    if (candidate.is_rgo or not candidate.counts_towards_building_capacity
            or (candidate.upgradeable_predecessor_levels > 0
                and candidate.predecessor_counts_towards_building_capacity)):
        return 1.0
    if context is None:
        return 0.0
    return building_capacity.coefficient(context.location.fully_staffed_building_levels,
                                         context.location.supported_building_levels)


def candidate_pending_factor(candidate: BuildingCandidate, context: AutomationContext | None,
                             rules: AutomationRules | None) -> float:
    """Use the same country/market commodity ledger for every commodity project."""
    if candidate.id == "windmill" or candidate.net_monthly_outputs is None:
        return 1.0
    if not candidate.net_monthly_outputs:
        return 1.0
    if not candidate.production_identity_known:
        return 1.0
    if context is None or not context.market.available:
        return 0.0
    states = context.market.goods
    if any(q > 0 and (g not in states or (
            not states[g].pending_known and not _food_emergency(candidate, context, rules)))
           for g, q in candidate.net_monthly_outputs.items()):
        return 0.0
    return production_ledger.assess(
        candidate.net_monthly_outputs,
        {g: v.demand for g, v in states.items()},
        {g: v.supply for g, v in states.items()},
        {g: v.pending_output for g, v in states.items()},
        candidate.output_base_prices,
        {g: v.future_input for g, v in states.items()},
        emergency=_food_emergency(candidate, context, rules),
    )


def score_candidate_components(
    policy: Policy,
    candidate: BuildingCandidate,
    context: AutomationContext | None = None,
    rules: AutomationRules | None = None,
) -> dict[str, int]:
    components: dict[str, int] = {"base": candidate.base_score}
    output_goods = _effective_output_goods(candidate, context)
    price_ratio = _output_price_ratio(candidate, context)
    if rules is not None:
        effective_building_priority = rules.building_priority_for(candidate.id)
        if (
            effective_building_priority <= rules.building_priorities.minimum
            and candidate.id in policy.allowed_buildings
        ):
            effective_building_priority = 1
        components["building_priority"] = round(
            effective_building_priority * rules.building_priorities.score_per_point
        )
        if not candidate.is_rgo:
            _, bonus = candidate_price_assessment(policy, candidate, context, rules)
            if bonus > 0:
                components["price_above_max"] = round(rules.rgo_scores.high_price * bonus)
        if candidate.upgradeable_predecessor_levels > 0:
            components["upgrade_replacement"] = rules.thresholds.upgrade_replacement_bonus
    if (not candidate.is_rgo and candidate.upgradeable_predecessor_levels <= 0
            and candidate.existing_levels > 0):
        bonus_per_level = rules.thresholds.expansion_bonus_per_level if rules is not None else 1
        components["expansion_scale"] = candidate.existing_levels * bonus_per_level
    if context is None or rules is None:
        policy_priority = 0
        for index, good in enumerate(policy.priority_goods):
            if good in output_goods:
                policy_priority = max(policy_priority, 100 - index)
        components["policy_priority"] = policy_priority
        if policy.role in output_goods:
            components["role"] = 25
        if not candidate.is_rgo:
            total = sum(components.values())
            factor, _ = candidate_price_assessment(policy, candidate, context, rules)
            adjusted = building_capacity.discount(total, factor)
            components["output_price"] = (round(adjusted) if adjusted is not None else 0) - total
        total = sum(components.values())
        adjusted = building_capacity.discount(total, candidate_pending_factor(candidate, context, rules))
        components["pending_output"] = (round(adjusted) if adjusted is not None else 0) - total
        total = sum(components.values())
        adjusted = building_capacity.discount(total, candidate_capacity_factor(candidate, context))
        components["building_capacity"] = (round(adjusted) if adjusted is not None else 0) - total
        return components

    components["market_need"] = _goods_need_score(candidate, context, rules)
    priority_scores = [
        max(0, rules.scores.policy_priority_base - index * rules.scores.policy_priority_step)
        for index, good in enumerate(policy.priority_goods)
        if good in output_goods
    ]
    if priority_scores:
        components["policy_priority"] = max(priority_scores)
    if policy.role in _candidate_groups(candidate, rules):
        components["role"] = rules.scores.role_match

    input_shortage = any(
        state is not None and state.supply_ratio <= rules.thresholds.input_shortage_supply_ratio
        for good in candidate.input_goods
        for state in (context.market.goods.get(good),)
    )
    if input_shortage or not candidate.inputs_available:
        components["input_shortage"] = rules.scores.input_shortage_penalty

    if candidate.native_input_assessment is not None:
        components["native_input_fit"] = candidate.native_input_assessment.score

    expected_profit = candidate.potential_profit
    adjusted = None
    if candidate.expected_output_value is not None and candidate.expected_input_cost is not None:
        expected_profit = candidate.expected_output_value - candidate.expected_input_cost
    if context is not None and (candidate.id == 'windmill' or candidate.id in GRANARY_BUILDINGS):
        adjusted = food_building_profit(candidate, context)
        if adjusted is not None:
            expected_profit = adjusted
    if not candidate.is_rgo:
        construction_cost = candidate.construction_cost or float(candidate.cost)
        if construction_cost > 0:
            components["economic_efficiency"] = round(
                (adjusted if adjusted is not None else candidate.potential_profit)
                / construction_cost * rules.thresholds.economic_score_scale
            )
    if expected_profit >= rules.thresholds.high_profit:
        components["profit_signal"] = rules.scores.high_profit
    elif expected_profit >= rules.thresholds.positive_profit:
        components["profit_signal"] = rules.scores.positive_profit
    else:
        components["profit_signal"] = rules.scores.negative_profit

    if candidate.is_rgo:
        # RGO utility is independent of ordinary-building profit/priority inputs.
        components = {"base": candidate.base_score,
                      "location": score_location(context.location, rules).score}
        if context.location.recently_built:
            components["location"] -= rules.location_scores.recent_build_penalty
        rgo = rules.rgo_scores
        output_states = [
            context.market.goods[good]
            for good in candidate.output_goods
            if good in context.market.goods
        ]
        if any(_shortage_level(state, rules) > 0 for state in output_states):
            components["rgo_shortage"] = rgo.shortage
        high_price = max(
            (high_price_factor(state.price_ratio * 100, policy.max_price_ratio * 100)
             for state in output_states),
            default=0.0,
        )
        if high_price > 0:
            components["rgo_price"] = round(rgo.high_price * high_price)
        components["rgo_utilization"] = round(
            rgo.utilization * max(0.0, min(1.0, candidate.rgo_utilization))
        )
        if candidate.rgo_expansion_space > 0:
            components["rgo_expansion_space"] = rgo.expansion_space
        if (
            set(candidate.output_goods) & rules.essential_goods
            or set(candidate.strategic_tags) & {"food", "construction", "military", "strategic"}
        ):
            components["rgo_strategic"] = rgo.strategic
        components["rgo_cost"] = candidate.cost * rgo.cost_penalty
        if _food_emergency(candidate, context, rules):
            components["rgo_food_emergency"] = rgo.food_emergency
        total = sum(components.values())
        # Negative utility remains negative so the admission gate can reject it.
        if total >= 0:
            factor = price_factor((price_ratio or 0) * 100, policy.min_price_ratio * 100,
                                  _food_emergency(candidate, context, rules))
            if candidate.recent_same_rgo and not _food_emergency(candidate, context, rules):
                factor *= 0.4
            components["rgo_market_factors"] = round(total * factor) - total
    if not policy.pause_on_labor_shortage and not _current_workers_sufficient(candidate):
        total = sum(components.values())
        adjusted = total * 0.4 if total >= 0 else total / 0.4
        components["labor_risk"] = round(adjusted) - total
    if not candidate.is_rgo:
        total = sum(components.values())
        factor, _ = candidate_price_assessment(policy, candidate, context, rules)
        adjusted = building_capacity.discount(total, factor)
        components["output_price"] = (round(adjusted) if adjusted is not None else 0) - total
    total = sum(components.values())
    adjusted = building_capacity.discount(total, candidate_pending_factor(candidate, context, rules))
    components["pending_output"] = (round(adjusted) if adjusted is not None else 0) - total
    total = sum(components.values())
    adjusted = building_capacity.discount(total, candidate_capacity_factor(candidate, context))
    # Ineligible projects are removed by the admission gate, never ranked at zero.
    components["building_capacity"] = (round(adjusted) if adjusted is not None else 0) - total
    return components


def score_candidate(
    policy: Policy,
    candidate: BuildingCandidate,
    context: AutomationContext | None = None,
    rules: AutomationRules | None = None,
) -> int:
    return sum(score_candidate_components(policy, candidate, context, rules).values())


def first_blocking_reason(
    policy: Policy,
    candidate: BuildingCandidate,
    budget_remaining: int,
    cash_available: int,
    *,
    ignore_allowlist: bool = False,
    ignore_input_shortage: bool = False,
    context: AutomationContext | None = None,
    rules: AutomationRules | None = None,
) -> PauseReason:
    if not candidate.unlocked:
        return PauseReason.NOT_UNLOCKED
    if candidate.newer_replacement_unlocked:
        return PauseReason.SUPERSEDED_BUILDING
    if candidate.id in policy.banned_buildings:
        return PauseReason.BANNED_BUILDING
    if (
        not candidate.is_rgo and rules is not None
        and rules.building_priority_for(candidate.id) <= rules.building_priorities.minimum
        and candidate.id not in policy.allowed_buildings
    ):
        return PauseReason.PRIORITY_DISABLED
    if not candidate.is_rgo and not ignore_allowlist and policy.allowed_buildings and candidate.id not in policy.allowed_buildings:
        return PauseReason.NOT_ALLOWED
    if candidate.is_special and not policy.allow_special_buildings:
        return PauseReason.SPECIAL_BUILDING_DISABLED
    if candidate.is_rgo and not policy.rgo.allowed:
        return PauseReason.RGO_DISABLED
    if candidate_capacity_factor(candidate, context) <= 0:
        if context is None or not building_capacity.readings_valid(
            context.location.fully_staffed_building_levels, context.location.supported_building_levels
        ):
            return PauseReason.BUILDING_CAPACITY_UNAVAILABLE
        return PauseReason.BUILDING_CAPACITY
    if candidate.is_rgo and candidate.rgo_utilization < 1:
        return PauseReason.RGO_UTILIZATION
    if not candidate.local_pop_available:
        return PauseReason.POPULATION_SHORTAGE
    if context is not None and rules is not None:
        if construction_slots.remaining(context.location.parallel_construction_limit, context.location.civil_constructions, context.location.reserved_construction_slots) <= 0:
            return PauseReason.CONSTRUCTION_QUEUE
        if context.location.cooldown_months > 0:
            return PauseReason.COOLDOWN
    if candidate.id == "irrigation_systems" and (
        context is None or rules is None or not irrigation_demand_present(context, rules)
    ):
        return PauseReason.NO_IRRIGATION_NEED
    if candidate.id in GRANARY_BUILDINGS:
        if context is not None and context.location.province_granary_pending:
            return PauseReason.STORAGE_PROJECT_PENDING
        if (context is None or rules is None or not (
            (granary_demand_present(context, rules) and any(
                balance is not None and math.isfinite(balance) and balance > 0
                for balance in (context.location.province_food_balance,
                                context.location.province_natural_food_balance)))
            or granary_decay_return_present(candidate, context, rules)
        )):
            return PauseReason.NO_GRANARY_NEED
    if candidate.id == "windmill" and (
        context is None or rules is None
        or not windmill_demand_present(context, rules, policy.max_price_ratio)
    ):
        return PauseReason.NO_WINDMILL_NEED
    if candidate.id == 'windmill':
        profit = food_building_profit(candidate, context)
        if (context.location.rgo_monthly_revenue is None or context.location.rgo_monthly_revenue <= 0
                or profit is None or profit <= 0 or (
                context.country.economic_metric >= 3
                and profit < candidate.cost * rules.thresholds.engine_min_annual_return_ratio / 12)):
            return PauseReason.NO_WINDMILL_NEED
    if policy.pause_on_labor_shortage and (not candidate.is_rgo or policy.rgo.workforce_mode == "population"):
        if (
            candidate.workforce_assessment is not None
            and not candidate.workforce_assessment.within_deadline
        ):
            return PauseReason.LABOR_SHORTAGE
        if candidate.workforce_assessment is None:
            if not candidate.labor_available:
                return PauseReason.LABOR_SHORTAGE
            if (
                candidate.available_workers is not None
                and rules is not None
                and candidate.available_workers
                < rules.thresholds.minimum_unemployed_workers
            ):
                return PauseReason.LABOR_SHORTAGE
    if not ignore_input_shortage and policy.pause_on_input_shortage and not candidate.inputs_available:
        return PauseReason.INPUT_SHORTAGE
    # A low output price signals oversupply and may block expansion. A high output
    # price signals scarcity, so the configured upper bound is a priority threshold.
    price_ratio = _output_price_ratio(candidate, context)
    if candidate.is_rgo:
        if (price_ratio is None or price_ratio <= policy.min_price_ratio) and not _food_emergency(candidate, context, rules):
            return PauseReason.PRICE_OUT_OF_RANGE
        if score_candidate(policy, candidate, context, rules) < 0:
            return PauseReason.RGO_NEGATIVE_SCORE
    elif candidate_price_assessment(policy, candidate, context, rules)[0] <= 0:
        return PauseReason.PRICE_OUT_OF_RANGE
    if candidate_pending_factor(candidate, context, rules) <= 0:
        return PauseReason.PENDING_OUTPUT
    # Both ordinary buildings and RGOs may spend the last positive annual
    # balance on one final project. Cash reserves still cover the whole cost.
    if budget_remaining <= 0:
        return PauseReason.BUDGET_EXHAUSTED
    if cash_available - candidate.cost < policy.min_cash_reserve:
        return PauseReason.CASH_RESERVE
    return PauseReason.NONE


def _source_building_ids(policy: Policy, catalog: BuildingCatalog | None, shortages: tuple[str, ...]) -> set[str]:
    if catalog is None or not policy.auto_build_input_sources:
        return set()
    source_ids: set[str] = set()
    for good in shortages:
        source_ids.update(catalog.source_buildings_by_good.get(good, ()))
    return source_ids


def rank_building_candidates(
    policy: Policy,
    candidates: list[BuildingCandidate],
    budget_remaining: int,
    cash_available: int,
    *,
    context: AutomationContext | None = None,
    rules: AutomationRules | None = None,
    limit: int | None = None,
) -> tuple[list[RankedCandidate], dict[PauseReason, int]]:
    """Return a bounded, score-ordered candidate list plus rejection counts."""
    ranked: list[RankedCandidate] = []
    rejected: dict[PauseReason, int] = {}
    for candidate in candidates:
        reason = first_blocking_reason(
            policy,
            candidate,
            budget_remaining,
            cash_available,
            context=context,
            rules=rules,
        )
        if reason is not PauseReason.NONE:
            rejected[reason] = rejected.get(reason, 0) + 1
            continue
        components = score_candidate_components(policy, candidate, context, rules)
        ranked.append(
            RankedCandidate(
                candidate=candidate,
                score=sum(components.values()),
                components=components,
            )
        )

    ranked.sort(key=lambda item: (not _food_emergency(item.candidate, context, rules), -item.score, item.candidate.id))
    if limit is None:
        limit = rules.cadence.candidates_per_location if rules is not None else 3
    return ranked[:limit], rejected


def execute_ranked_candidates(
    policy: Policy,
    candidates: list[BuildingCandidate],
    budget_remaining: int,
    cash_available: int,
    queue_count_before: int,
    attempt: Callable[[BuildingCandidate], int],
    *,
    rgo_quota_used: int = 0,
    context: AutomationContext | None = None,
    rules: AutomationRules,
) -> BuildExecution:
    """Try up to three candidates and commit state only after queue growth.

    The callback returns the observed queue size after the vanilla construction
    effect. A hidden vanilla rejection therefore falls through to the next
    candidate without spending budget, consuming quota, or applying cooldown.
    """
    ranked, rejections = rank_building_candidates(
        policy,
        candidates,
        budget_remaining,
        cash_available,
        context=context,
        rules=rules,
    )
    attempted: list[str] = []
    vanilla_rejected: list[str] = []

    for item in ranked:
        candidate = item.candidate
        attempted.append(candidate.id)
        queue_count_after = attempt(candidate)
        if queue_count_after > queue_count_before:
            return BuildExecution(
                building_id=candidate.id,
                reason=PauseReason.NONE,
                attempted_buildings=tuple(attempted),
                rejected_buildings=tuple(vanilla_rejected),
                score=item.score,
                budget_spent=candidate.cost,
                cooldown_months=rules.cadence.location_cooldown_months,
                quota_used=1,
                rgo_quota_used=1 if candidate.is_rgo else 0,
            )
        vanilla_rejected.append(candidate.id)

    if vanilla_rejected:
        reason = PauseReason.VANILLA_REJECTED
    elif rejections:
        reason = next(iter(rejections))
    else:
        reason = PauseReason.NO_CANDIDATE
    return BuildExecution(
        building_id=None,
        reason=reason,
        attempted_buildings=tuple(attempted),
        rejected_buildings=tuple(vanilla_rejected),
    )


def choose_building(
    policy: Policy,
    candidates: list[BuildingCandidate],
    budget_remaining: int,
    cash_available: int,
    catalog: BuildingCatalog | None = None,
    context: AutomationContext | None = None,
    rules: AutomationRules | None = None,
) -> BuildDecision:
    best: tuple[int, BuildingCandidate] | None = None
    fallback_reason = PauseReason.NO_CANDIDATE

    for candidate in candidates:
        reason = first_blocking_reason(
            policy,
            candidate,
            budget_remaining,
            cash_available,
            context=context,
            rules=rules,
        )
        if reason is PauseReason.INPUT_SHORTAGE and policy.auto_build_input_sources:
            source_ids = _source_building_ids(policy, catalog, candidate.input_shortages)
            source_candidates = [item for item in candidates if item.id in source_ids]
            source_decision = choose_input_source_building(
                policy,
                source_candidates,
                budget_remaining,
                cash_available,
                context=context,
                rules=rules,
            )
            if source_decision.should_build:
                return source_decision

        if reason is not PauseReason.NONE:
            if fallback_reason is PauseReason.NO_CANDIDATE:
                fallback_reason = reason
            continue
        score = score_candidate(policy, candidate, context, rules)
        if best is None or score > best[0]:
            best = (score, candidate)

    if best is None:
        return BuildDecision(None, fallback_reason)
    return BuildDecision(best[1].id, PauseReason.NONE, best[0])


def choose_input_source_building(
    policy: Policy,
    candidates: list[BuildingCandidate],
    budget_remaining: int,
    cash_available: int,
    context: AutomationContext | None = None,
    rules: AutomationRules | None = None,
) -> BuildDecision:
    best: tuple[int, BuildingCandidate] | None = None
    fallback_reason = PauseReason.NO_CANDIDATE
    for candidate in candidates:
        reason = first_blocking_reason(
            policy,
            candidate,
            budget_remaining,
            cash_available,
            ignore_allowlist=True,
            ignore_input_shortage=True,
            context=context,
            rules=rules,
        )
        if reason is not PauseReason.NONE:
            if fallback_reason is PauseReason.NO_CANDIDATE:
                fallback_reason = reason
            continue
        source_bonus = rules.scores.upstream_source_bonus if rules is not None else 50
        score = score_candidate(policy, candidate, context, rules) + source_bonus
        if best is None or score > best[0]:
            best = (score, candidate)

    if best is None:
        return BuildDecision(None, fallback_reason)
    return BuildDecision(best[1].id, PauseReason.NONE, best[0])


def apply_province_template(
    location_policy_ids: dict[str, str | None],
    province_locations: list[str],
    policy_id: str,
    decoupled_locations: set[str],
) -> dict[str, str | None]:
    updated = dict(location_policy_ids)
    for location_id in province_locations:
        if location_id not in decoupled_locations:
            updated[location_id] = policy_id
    return updated
