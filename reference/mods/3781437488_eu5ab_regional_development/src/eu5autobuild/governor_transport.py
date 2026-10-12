"""Explicit transport inputs for calibrated and long-term Governor models.

These inputs are not interchangeable with the historical destination-scoped
``LocationState.edge_cost_factor`` cache. Callers must reconstruct the separate
engine modifiers and classify edges before using this model. Actual-network
calibration and highest-unlocked-road planning are intentionally separate modes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import math
from types import MappingProxyType
from typing import Iterable, Mapping


ROAD_PROPAGATION_DISCOUNT = {
    "gravel_road": 0.0,
    "paved_road": 5.0,
    "modern_road": 10.0,
    "railroad": 15.0,
}
ROAD_UNLOCKS = (
    ("road_building", "gravel_road"),
    ("paved_road_advance", "paved_road"),
    ("modern_road_advance", "modern_road"),
    ("railroad_advance", "railroad"),
)


class TransportInputError(ValueError):
    """A calibrated prediction lacks explicit or internally consistent inputs."""


class TransportMode(str, Enum):
    ACTUAL = "actual"
    HIGHEST_UNLOCKED = "highest_unlocked"


def highest_unlocked_road(unlocked_advances: Iterable[str]) -> str | None:
    """Resolve road capability from country unlocks, never from roads or date."""

    advances = set(unlocked_advances)
    return next(
        (road for advance, road in reversed(ROAD_UNLOCKS) if advance in advances),
        None,
    )


def _require_finite(**values: float) -> None:
    for name, value in values.items():
        if not math.isfinite(value):
            raise TransportInputError(f"{name} must be finite")


@dataclass(frozen=True, slots=True)
class CountryTransportInputs:
    # Fractions: +19% is 0.19, not 19. Modifiers are a country snapshot.
    global_speed: float
    land_speed: float
    terrain_modifier: float

    def __post_init__(self) -> None:
        _require_finite(
            global_speed=self.global_speed,
            land_speed=self.land_speed,
            terrain_modifier=self.terrain_modifier,
        )


@dataclass(frozen=True, slots=True)
class LocationTransportInputs:
    # All three inputs belong to the source endpoint of a directed edge.
    local_speed: float
    topography: float
    vegetation: float
    # Country impact for this source's topography type, e.g.
    # hills_proximity_impact. None retains the explicit country fallback for
    # small fixtures; real mixed-terrain snapshots should supply this field.
    topography_modifier: float | None = None

    def __post_init__(self) -> None:
        _require_finite(
            local_speed=self.local_speed,
            topography=self.topography,
            vegetation=self.vegetation,
        )
        if self.topography_modifier is not None:
            _require_finite(topography_modifier=self.topography_modifier)


def land_edge_cost(
    source: LocationTransportInputs,
    country: CountryTransportInputs,
    road_type: str | None,
    *,
    base_road_cost: float = 20.0,
    base_land_cost: float = 40.0,
) -> float:
    """Evaluate one directed land edge using separated engine inputs.

    The terrain and speed divisors are separate. A road removes the vegetation
    term, but does not remove topography. Positive topography bonuses are capped
    at zero before the terrain divisor's 0.5 floor is applied.
    """

    _require_finite(base_road_cost=base_road_cost, base_land_cost=base_land_cost)
    if base_road_cost < 0 or base_land_cost < 0:
        raise TransportInputError("Base transport costs must be non-negative")
    if road_type is not None and road_type not in ROAD_PROPAGATION_DISCOUNT:
        raise TransportInputError(f"Unknown road type: {road_type}")
    terrain = max(
        0.5,
        1.0 + min(0.0, source.topography * (1.0 + (
            country.terrain_modifier if source.topography_modifier is None else source.topography_modifier
        )))
        + (source.vegetation if road_type is None else 0.0),
    )
    speed = max(0.05, 1.0 + country.global_speed + country.land_speed + source.local_speed)
    base = (
        base_land_cost if road_type is None
        else base_road_cost - ROAD_PROPAGATION_DISCOUNT[road_type]
    )
    if base < 0:
        raise TransportInputError("Road discount exceeds the supplied base cost")
    return base / terrain / speed


def lake_edge_cost(
    source_local_speed: float,
    country: CountryTransportInputs,
    *,
    base_cost: float = 4.0,
) -> float:
    """Cost of an already identified lake edge with maximum maritime presence.

    The caller must resolve edge eligibility and country ownership first. Lake
    nodes supply zero local speed; land endpoints supply their own local speed.
    Land speed, topography, vegetation, and planned roads do not enter this cost.
    No unverified ``sea_speed`` modifier is invented.
    """

    _require_finite(source_local_speed=source_local_speed, base_cost=base_cost)
    if base_cost < 0:
        raise TransportInputError("Lake base cost must be non-negative")
    return base_cost / max(0.05, 1.0 + country.global_speed + source_local_speed)


@dataclass(frozen=True, slots=True)
class TransportContext:
    """An immutable transport snapshot shared by old and proposed layouts.

    Every traversed edge needs an explicit classification. ``land_edges`` may
    include land links that cannot be upgraded. ``buildable_land_edges`` is the
    subset where planning substitutes the highest country-unlocked road, even
    when no road currently exists. No unlock means existing roads remain usable
    and currently roadless edges remain roadless.

    Non-land costs are directed, independently verified inputs. This interface
    accommodates lakes without pretending that a land formula proves maritime
    ownership, presence, scope, or cross-water eligibility rules. Missing reverse
    costs are errors rather than an assumption that both directions cost alike.
    """

    country: CountryTransportInputs
    locations: Mapping[int, LocationTransportInputs]
    land_edges: frozenset[frozenset[int]]
    mode: TransportMode = TransportMode.ACTUAL
    unlocked_advances: frozenset[str] = frozenset()
    buildable_land_edges: frozenset[frozenset[int]] = frozenset()
    non_land_edge_costs: Mapping[tuple[int, int], float] = field(default_factory=dict)
    base_road_cost: float = 20.0
    base_land_cost: float = 40.0
    _planned_road_type: str | None = field(init=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "mode", TransportMode(self.mode))
        object.__setattr__(self, "locations", MappingProxyType(dict(self.locations)))
        object.__setattr__(self, "land_edges", frozenset(frozenset(edge) for edge in self.land_edges))
        object.__setattr__(self, "buildable_land_edges", frozenset(frozenset(edge) for edge in self.buildable_land_edges))
        object.__setattr__(self, "unlocked_advances", frozenset(self.unlocked_advances))
        object.__setattr__(self, "_planned_road_type", highest_unlocked_road(self.unlocked_advances))
        object.__setattr__(self, "non_land_edge_costs", MappingProxyType(dict(self.non_land_edge_costs)))
        if not self.buildable_land_edges <= self.land_edges:
            raise TransportInputError("Only explicitly classified land edges can be road-buildable")
        for edge in self.land_edges:
            if len(edge) != 2:
                raise TransportInputError("Land edges must contain two distinct locations")
        for (source, destination), cost in self.non_land_edge_costs.items():
            if source == destination or frozenset((source, destination)) in self.land_edges:
                raise TransportInputError("Non-land edge classification conflicts with land edges")
            _require_finite(non_land_edge_cost=cost)
            if cost < 0:
                raise TransportInputError("Non-land edge costs must be non-negative")
        _require_finite(base_road_cost=self.base_road_cost, base_land_cost=self.base_land_cost)
        if self.base_road_cost < 0 or self.base_land_cost < 0:
            raise TransportInputError("Base transport costs must be non-negative")

    @property
    def planned_road_type(self) -> str | None:
        return self._planned_road_type

    def road_type_for_edge(self, source: int, destination: int, actual_road: str | None) -> str | None:
        edge = frozenset((source, destination))
        if edge not in self.land_edges:
            raise TransportInputError(f"Edge {source}->{destination} is not a classified land edge")
        if (
            self.mode is TransportMode.HIGHEST_UNLOCKED
            and edge in self.buildable_land_edges
            and self.planned_road_type is not None
        ):
            return self.planned_road_type
        return actual_road

    def edge_cost(self, source: int, destination: int, actual_road: str | None) -> float:
        edge = frozenset((source, destination))
        if edge not in self.land_edges:
            try:
                return self.non_land_edge_costs[(source, destination)]
            except KeyError:
                raise TransportInputError(f"No verified transport inputs for edge {source}->{destination}") from None
        try:
            source_inputs = self.locations[source]
        except KeyError:
            raise TransportInputError(f"Missing source transport inputs for location {source}") from None
        return land_edge_cost(
            source_inputs,
            self.country,
            self.road_type_for_edge(source, destination, actual_road),
            base_road_cost=self.base_road_cost,
            base_land_cost=self.base_land_cost,
        )
