"""Pure-Python reference model for Governor recommendation validation.

The generated EU5 scripts are the production implementation.  This module is
kept deliberately engine-agnostic so the ranking, bounded propagation,
component grouping, and migration hysteresis can be tested with synthetic
graphs and plaintext saves without launching the game.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import heapq
import math
from typing import Iterable, Mapping

from .governor_transport import TransportContext, TransportInputError, TransportMode


# These are propagation discounts applied to an actual road edge.  They are
# deliberately not scoring bonuses: a road matters only when it changes how
# far the hypothetical Proximity source can reach.
ROAD_PROPAGATION_DISCOUNT = {
    None: 0.0,
    "gravel_road": 0.0,
    "paved_road": 5.0,
    "modern_road": 10.0,
    "railroad": 15.0,
}


def _score_component(value: float) -> float:
    """Quantize a non-negative gain to the one decimal shown in the UI."""

    return math.floor(max(0.0, value) * 10.0 + 0.5) / 10.0


@dataclass(frozen=True, slots=True)
class LocationState:
    id: int
    name: str
    rank: str
    proximity: float
    # Kept for save diagnostics and callers that already provide the full
    # location state. Neither value is a scoring multiplier: Proximity is the
    # main input to Max Control, while other active game modifiers also apply.
    control: float
    max_control: float | None
    population: float
    potential_tax_base: float
    development: float
    road_to_capital: bool = False
    is_port: bool = False
    has_fort: bool = False
    is_border: bool = False
    # Historical runtime caches. These reproduce the previous Mod formula,
    # not the engine's source-scoped and separately factored transport rule.
    # Calibrated callers pass a TransportContext instead; these legacy fields
    # must never be reinterpreted as its separate source modifier inputs.
    edge_cost_factor: float | None = None
    road_edge_base_cost: float | None = None
    land_edge_base_cost: float | None = None
    # The authoritative location value calculated by the game for the active
    # profile and strategic toggle.  Save validation prefers it when present.
    runtime_value: float | None = None
    # Lakes can carry propagation without being owned economic targets or seats.
    is_transit_only: bool = False
    # Add the hypothetical seat to the current raw modifier before clamping.
    raw_proximity_source: float = 0.0


@dataclass(frozen=True, slots=True)
class NodeContribution:
    location_id: int
    old_proximity: float
    candidate_proximity: float
    effective_proximity: float
    proximity_gain: float
    old_control: float
    old_max_control: float | None
    # This offline proxy does not request an engine Max Control recomputation
    # for hypothetical Proximity, so these two diagnostics remain unavailable.
    new_max_control: float | None
    max_control_gain: float | None
    location_value: float
    site_or_surrounding: str
    final_contribution: float


@dataclass(frozen=True, slots=True)
class CandidateScore:
    location_id: int
    score: float
    marginal_gain: float
    site_gain: float
    surrounding_gain: float
    covered_locations: int
    covered_value: float
    contributions: tuple[NodeContribution, ...] = ()


@dataclass(frozen=True, slots=True)
class MigrationContribution:
    location_id: int
    current_proximity: float
    proximity_without_current: float
    replacement_proximity: float
    after_proximity: float
    current_source_contribution: float
    replacement_source_contribution: float
    net_contribution: float


@dataclass(frozen=True, slots=True)
class MigrationProposal:
    current_location_id: int
    recommended_location_id: int
    current_score: float
    recommended_score: float
    net_gain: float
    covered_locations: int
    contributions: tuple[MigrationContribution, ...] = ()


def location_value(
    location: LocationState,
    profile: str = "mixed",
    *,
    strategic_value: bool = False,
) -> float:
    """Return the compact economic/administrative value used by both scorers.

    EU5's population script value is expressed in thousands, matching the
    plaintext save's ``population_ratio`` totals.  The weights therefore use
    that unit directly rather than treating it as a raw person count.
    """

    # getattr also permits historical slotted pickles created before this field.
    if getattr(location, "is_transit_only", False):
        return 0.0
    if location.runtime_value is not None:
        return max(0.01, location.runtime_value)
    if profile == "economic":
        base = (
            location.potential_tax_base * 2.5
            + location.population * 0.15
            + location.development * 0.75
        )
    elif profile == "administrative_population":
        base = (
            location.potential_tax_base * 0.25
            + location.population * 1.2
            + location.development * 0.75
        )
    elif profile == "mixed":
        base = (
            location.potential_tax_base * 1.5
            + location.population * 0.5
            + location.development * 0.75
        )
    else:
        raise ValueError(f"Unknown Governor scoring profile: {profile}")
    if strategic_value:
        if location.is_port:
            base *= 1.15
        if location.has_fort:
            base *= 1.1
        if location.is_border:
            base *= 1.1
    return max(0.01, base)


def _edge_cost(
    destination: LocationState,
    road_type: str | None,
    *,
    base_road_cost: float,
    base_land_cost: float,
) -> float:
    """Legacy destination-cache calculation, retained for historical replay."""
    discount = ROAD_PROPAGATION_DISCOUNT.get(road_type, 0.0)
    base_cost = base_land_cost if road_type is None else base_road_cost - discount
    if (
        destination.edge_cost_factor is not None
        and destination.road_edge_base_cost is not None
        and destination.land_edge_base_cost is not None
    ):
        if road_type is None:
            return max(0.0, destination.land_edge_base_cost)
        return max(
            0.01 * destination.edge_cost_factor,
            destination.road_edge_base_cost
            - discount * destination.edge_cost_factor,
        )
    return max(0.01, base_cost)


class PropagationBudgetExceeded(RuntimeError):
    """The queue still contains work; partial coverage must not be ranked."""


def propagate_proximity(
    source_values: Mapping[int, float],
    locations: Mapping[int, LocationState],
    neighbors: Mapping[int, set[int]],
    roads: Mapping[frozenset[int], str],
    *,
    naval: bool = False,
    special_edges: set[frozenset[int]] | None = None,
    max_depth: int | None = 6,
    max_steps: int | None = None,
    base_road_cost: float = 20.0,
    base_land_cost: float = 40.0,
    require_complete: bool = False,
    transport_context: TransportContext | None = None,
) -> dict[int, float]:
    """Propagate one or more explicit Proximity sources over the bounded graph.

    This is also the counterfactual primitive used for relocation.  In
    particular, relocation never seeds from the live ``location.proximity``
    snapshot because that snapshot still contains the source being removed.
    Without ``transport_context`` this explicitly retains historical Mod
    semantics for old saves. A context supplies calibrated source-scoped costs
    and its actual/planned road snapshot; no old factor cache is reused.
    """

    special_edges = special_edges or set()
    max_steps = max(100, len(locations) * 4) if max_steps is None else max_steps
    if max_steps < 0:
        raise ValueError("max_steps must be non-negative")
    predicted: dict[int, float] = {}
    depths: dict[int, int] = {}
    queue: list[tuple[float, int]] = []
    for location_id, source_value in source_values.items():
        if location_id not in locations or source_value <= 0:
            continue
        # EU5 Proximity is capped at 100. Keep the raw source map unbounded so
        # relocation can subtract exactly one 80-point Governor source before
        # this propagation-time cap is applied.
        value = min(100.0, max(0.0, source_value))
        if value <= predicted.get(location_id, -1.0):
            continue
        predicted[location_id] = value
        depths[location_id] = 0
        heapq.heappush(queue, (-value, location_id))

    steps = 0
    while queue and steps < max_steps:
        negative_value, location_id = heapq.heappop(queue)
        value = -negative_value
        if value + 1e-9 < predicted[location_id]:
            continue
        steps += 1
        depth = depths[location_id]
        if (max_depth is not None and depth >= max_depth) or value <= 0:
            continue
        for neighbor_id in neighbors.get(location_id, set()):
            edge = frozenset((location_id, neighbor_id))
            if not naval and edge in special_edges:
                continue
            neighbor = locations.get(neighbor_id)
            if neighbor is None:
                continue
            relaxed = max(
                0.0,
                value
                - (transport_context.edge_cost(location_id, neighbor_id, roads.get(edge))
                   if transport_context is not None else _edge_cost(
                    neighbor,
                    roads.get(edge),
                    base_road_cost=base_road_cost,
                    base_land_cost=base_land_cost,
                )),
            )
            if relaxed > predicted.get(neighbor_id, -1.0) + 1e-9:
                predicted[neighbor_id] = relaxed
                depths[neighbor_id] = depth + 1
                heapq.heappush(queue, (-relaxed, neighbor_id))
    if require_complete and queue:
        raise PropagationBudgetExceeded("Proximity propagation has unfinished work")
    return predicted


def _candidate_locations(
    locations: Mapping[int, LocationState],
    transport_context: TransportContext | None,
    baseline_proximity: Mapping[int, float] | None,
) -> Mapping[int, LocationState]:
    """Prevent a planned-road candidate from being compared to a live baseline."""

    if baseline_proximity is None:
        if transport_context is not None and transport_context.mode is TransportMode.HIGHEST_UNLOCKED:
            raise TransportInputError("Highest-road candidate scoring requires a baseline propagated with the same context")
        return locations
    missing = locations.keys() - baseline_proximity.keys()
    if missing:
        raise TransportInputError(f"Candidate baseline omits locations: {sorted(missing)}")
    if any(not math.isfinite(value) or not 0 <= value <= 100 for value in baseline_proximity.values()):
        raise TransportInputError("Baseline Proximity must be finite and between 0 and 100")
    return {
        location_id: replace(
            location,
            proximity=baseline_proximity[location_id],
            is_transit_only=getattr(location, "is_transit_only", False),
        )
        for location_id, location in locations.items()
    }


def evaluate_candidate(
    candidate_id: int,
    locations: Mapping[int, LocationState],
    neighbors: Mapping[int, set[int]],
    roads: Mapping[frozenset[int], str],
    *,
    profile: str = "mixed",
    strategic_value: bool = False,
    naval: bool = False,
    special_edges: set[frozenset[int]] | None = None,
    max_depth: int = 6,
    max_steps: int | None = None,
    base_road_cost: float = 20.0,
    base_land_cost: float = 40.0,
    transport_context: TransportContext | None = None,
    baseline_proximity: Mapping[int, float] | None = None,
) -> CandidateScore:
    """Evaluate only the value of a hypothetical source's Proximity gain.

    Control is intentionally not forecast here. The game moves Control toward
    Max Control over time, and Max Control also includes modifiers that this
    offline model cannot reliably attribute to the candidate building.
    """

    if candidate_id not in locations:
        raise KeyError(candidate_id)
    if getattr(locations[candidate_id], "is_transit_only", False):
        raise ValueError("A transit-only node cannot host a Governor candidate")
    locations = _candidate_locations(locations, transport_context, baseline_proximity)
    predicted = propagate_proximity(
        {candidate_id: locations[candidate_id].raw_proximity_source + 80.0},
        locations,
        neighbors,
        roads,
        naval=naval,
        special_edges=special_edges,
        max_depth=None if naval else max_depth,
        max_steps=max_steps if max_steps is not None else (max(100, len(locations) * 4) if naval else None),
        require_complete=naval or transport_context is not None,
        base_road_cost=base_road_cost,
        base_land_cost=base_land_cost,
        transport_context=transport_context,
    )
    site_gain = 0.0
    surrounding_gain = 0.0
    contributions: list[NodeContribution] = []
    covered_value = 0.0
    covered = 0
    for location_id, value in predicted.items():
        location = locations[location_id]
        if getattr(location, "is_transit_only", False):
            continue
        node_value = location_value(
            location, profile, strategic_value=strategic_value
        )
        effective_proximity = max(location.proximity, value)
        improvement = max(0.0, effective_proximity - location.proximity)
        if improvement > 0:
            # Control is a downstream game value: Proximity changes the
            # location's Max Control, while other active modifiers can change
            # that ceiling too.  The reference model cannot predict those
            # unknown modifiers, so it values only the observable Proximity
            # improvement and leaves Control out of the score multiplier.
            node_gain = node_value * improvement / 100.0
            if location_id == candidate_id:
                site_gain += node_gain
                site_or_surrounding = "site"
            else:
                surrounding_gain += node_gain
                site_or_surrounding = "surrounding"
            contributions.append(
                NodeContribution(
                    location_id=location_id,
                    old_proximity=location.proximity,
                    candidate_proximity=value,
                    effective_proximity=effective_proximity,
                    proximity_gain=improvement,
                    old_control=location.control,
                    old_max_control=location.max_control,
                    new_max_control=None,
                    max_control_gain=None,
                    location_value=node_value,
                    site_or_surrounding=site_or_surrounding,
                    final_contribution=node_gain,
                )
            )
            covered_value += node_value
            covered += 1
    # Save both components at the precision shown by the recommendation card,
    # then derive the score from those saved values. This keeps the visible
    # arithmetic exact as well as the underlying CandidateScore invariant.
    site_gain = _score_component(site_gain)
    surrounding_gain = _score_component(surrounding_gain)
    gain = site_gain + surrounding_gain
    return CandidateScore(
        location_id=candidate_id,
        score=gain,
        marginal_gain=gain,
        site_gain=site_gain,
        surrounding_gain=surrounding_gain,
        covered_locations=covered,
        covered_value=covered_value,
        contributions=tuple(contributions),
    )


def cheap_score(
    location_id: int,
    locations: Mapping[int, LocationState],
    neighbors: Mapping[int, set[int]],
    roads: Mapping[frozenset[int], str],
    *,
    profile: str = "mixed",
    naval: bool = False,
    strategic_value: bool = False,
) -> float:
    """Estimate shortlist demand without rewarding road count.

    roads and naval remain in the signature for API compatibility and to keep
    local/naval shortlist call sites symmetrical. Actual road quality is
    applied by evaluate_candidate during bounded propagation.
    """
    location = locations[location_id]
    value = location_value(location, profile, strategic_value=strategic_value)
    demand = (
        value
        * max(0.0, min(100.0, location.raw_proximity_source + 80.0) - location.proximity)
        / 100.0
    )
    score = demand
    for neighbor_id in neighbors.get(location_id, set()):
        neighbor = locations.get(neighbor_id)
        if neighbor is None:
            continue
        neighbor_value = location_value(
            neighbor, profile, strategic_value=strategic_value
        )
        score += neighbor_value * max(0.0, min(100.0, neighbor.raw_proximity_source + 80.0) - neighbor.proximity) / 100.0 * 0.65
    return score


def rank_local_candidates(
    candidate_ids: Iterable[int],
    locations: Mapping[int, LocationState],
    neighbors: Mapping[int, set[int]],
    roads: Mapping[frozenset[int], str],
    *,
    profile: str = "mixed",
    strategic_value: bool = False,
    special_edges: set[frozenset[int]] | None = None,
    transport_context: TransportContext | None = None,
    baseline_proximity: Mapping[int, float] | None = None,
) -> list[CandidateScore]:
    locations = _candidate_locations(locations, transport_context, baseline_proximity)
    shortlist = sorted(
        set(candidate_ids),
        key=lambda location_id: cheap_score(
            location_id,
            locations,
            neighbors,
            roads,
            profile=profile,
            strategic_value=strategic_value,
        ),
        reverse=True,
    )[:8]
    return sorted(
        (
            evaluate_candidate(
                location_id,
                locations,
                neighbors,
                roads,
                profile=profile,
                strategic_value=strategic_value,
                special_edges=special_edges,
                transport_context=transport_context,
                baseline_proximity=baseline_proximity,
            )
            for location_id in shortlist
        ),
        key=lambda result: result.score,
        reverse=True,
    )


def connected_components(
    location_ids: Iterable[int], neighbors: Mapping[int, set[int]]
) -> list[set[int]]:
    remaining = set(location_ids)
    components: list[set[int]] = []
    while remaining:
        start = remaining.pop()
        component = {start}
        stack = [start]
        while stack:
            current = stack.pop()
            for neighbor in neighbors.get(current, set()):
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    component.add(neighbor)
                    stack.append(neighbor)
        components.append(component)
    return components


def rank_naval_components(
    components: Iterable[set[int]],
    candidate_ids: Iterable[int],
    existing_governor_ids: set[int],
    locations: Mapping[int, LocationState],
    neighbors: Mapping[int, set[int]],
    roads: Mapping[frozenset[int], str],
    *,
    profile: str = "mixed",
    strategic_value: bool = False,
    special_edges: set[frozenset[int]] | None = None,
    transport_context: TransportContext | None = None,
    baseline_proximity: Mapping[int, float] | None = None,
) -> list[CandidateScore]:
    # Components are descriptive, never a hard candidate shortlist. The caller
    # supplies structural eligibility; evaluate every legal port globally.
    return sorted(evaluate_naval_relocation_candidates(
        components, candidate_ids, locations, neighbors, roads, profile=profile,
        strategic_value=strategic_value, special_edges=special_edges,
        transport_context=transport_context, baseline_proximity=baseline_proximity),
        key=lambda result: (-result.score, result.location_id))


def evaluate_naval_relocation_candidates(
    components: Iterable[set[int]],
    candidate_ids: Iterable[int],
    locations: Mapping[int, LocationState],
    neighbors: Mapping[int, set[int]],
    roads: Mapping[frozenset[int], str],
    *,
    profile: str = "mixed",
    strategic_value: bool = False,
    special_edges: set[frozenset[int]] | None = None,
    transport_context: TransportContext | None = None,
    baseline_proximity: Mapping[int, float] | None = None,
) -> list[CandidateScore]:
    """Evaluate every supplied legal target, without regional hard exclusions."""
    locations = _candidate_locations(locations, transport_context, baseline_proximity)
    return [
        evaluate_candidate(
            node, locations, neighbors, roads, profile=profile,
            strategic_value=strategic_value, naval=True, special_edges=special_edges,
            transport_context=transport_context, baseline_proximity=baseline_proximity)
        for node in sorted(set(candidate_ids))
    ]


def evaluate_migration_pair(
    current_location_id: int,
    recommended_location_id: int,
    source_values: Mapping[int, float],
    locations: Mapping[int, LocationState],
    neighbors: Mapping[int, set[int]],
    roads: Mapping[frozenset[int], str],
    *,
    profile: str = "mixed",
    strategic_value: bool = False,
    naval: bool = False,
    special_edges: set[frozenset[int]] | None = None,
    moving_source_strength: float = 80.0,
    max_depth: int = 6,
    max_steps: int | None = None,
    base_road_cost: float = 20.0,
    base_land_cost: float = 40.0,
    transport_context: TransportContext | None = None,
) -> MigrationProposal:
    """Score the complete remove-then-add relocation counterfactual.

    ``source_values`` contains the complete raw source modifier in the current
    network, including the source being moved.  The old source is subtracted
    before the baseline is propagated; the destination is then evaluated on
    top of that same source-free baseline.  Consequently the returned net gain
    is the weighted nationwide Proximity change caused by the move, not the
    value of adding the destination while retaining the old source.
    """

    if current_location_id not in locations:
        raise KeyError(current_location_id)
    if recommended_location_id not in locations:
        raise KeyError(recommended_location_id)
    if any(getattr(locations[node], "is_transit_only", False) for node in (current_location_id, recommended_location_id)):
        raise ValueError("A transit-only node cannot host a Governor seat")
    if current_location_id not in source_values:
        raise ValueError("The current location has no raw source snapshot")

    if naval:
        max_depth = None
        if max_steps is None:
            max_steps = max(100, len(locations) * 4)
    without_sources = dict(source_values)
    # Negative fixed modifiers still matter when a seat is placed here again.
    without_sources[current_location_id] -= moving_source_strength
    without_current = propagate_proximity(
        without_sources,
        locations,
        neighbors,
        roads,
        naval=naval,
        special_edges=special_edges,
        max_depth=max_depth,
        max_steps=max_steps,
        require_complete=naval or transport_context is not None,
        base_road_cost=base_road_cost,
        base_land_cost=base_land_cost,
        transport_context=transport_context,
    )
    replacement_source = (
        without_sources.get(recommended_location_id, 0.0)
        + moving_source_strength
    )
    replacement = propagate_proximity(
        {recommended_location_id: replacement_source},
        locations,
        neighbors,
        roads,
        naval=naval,
        special_edges=special_edges,
        max_depth=max_depth,
        max_steps=max_steps,
        require_complete=naval or transport_context is not None,
        base_road_cost=base_road_cost,
        base_land_cost=base_land_cost,
        transport_context=transport_context,
    )

    # Calibrated relocation compares both source contributions in the same
    # context and depth budget. In particular, a planned old layout must not
    # use live Proximity from a less developed road network.
    current_model = propagate_proximity(
        {current_location_id: source_values[current_location_id]},
        locations, neighbors, roads, naval=naval, special_edges=special_edges,
        max_depth=max_depth if transport_context is not None else None,
        max_steps=max_steps if max_steps is not None else max(100, len(locations) * 4),
        require_complete=True, base_road_cost=base_road_cost, base_land_cost=base_land_cost,
        transport_context=transport_context,
    ) if naval or transport_context is not None else None

    current_score = 0.0
    recommended_score = 0.0
    covered = 0
    contributions: list[MigrationContribution] = []
    for location_id, location in locations.items():
        if getattr(location, "is_transit_only", False):
            continue
        baseline = without_current.get(location_id, 0.0)
        replacement_proximity = replacement.get(location_id, 0.0)
        after = max(baseline, replacement_proximity)
        node_value = location_value(
            location, profile, strategic_value=strategic_value
        )
        before = max(baseline, current_model.get(location_id, 0.0)) if current_model is not None else location.proximity
        current_contribution = node_value * max(0.0, before - baseline) / 100.0
        replacement_contribution = (
            node_value * max(0.0, after - baseline) / 100.0
        )
        current_score += current_contribution
        recommended_score += replacement_contribution
        net_contribution = replacement_contribution - current_contribution
        if replacement_contribution > 1e-9:
            covered += 1
        if abs(net_contribution) > 1e-9:
            contributions.append(
                MigrationContribution(
                    location_id=location_id,
                    current_proximity=before,
                    proximity_without_current=baseline,
                    replacement_proximity=replacement_proximity,
                    after_proximity=after,
                    current_source_contribution=current_contribution,
                    replacement_source_contribution=replacement_contribution,
                    net_contribution=net_contribution,
                )
            )

    current_score = _score_component(current_score)
    recommended_score = _score_component(recommended_score)
    return MigrationProposal(
        current_location_id=current_location_id,
        recommended_location_id=recommended_location_id,
        current_score=current_score,
        recommended_score=recommended_score,
        net_gain=recommended_score - current_score,
        covered_locations=covered,
        contributions=tuple(contributions),
    )


def rank_migration_pairs(
    current_location_ids: Iterable[int],
    alternative_location_ids: Iterable[int],
    source_values: Mapping[int, float],
    locations: Mapping[int, LocationState],
    neighbors: Mapping[int, set[int]],
    roads: Mapping[frozenset[int], str],
    **kwargs: object,
) -> list[MigrationProposal]:
    """Evaluate every current/destination pair and order by nationwide gain."""

    current_ids = set(current_location_ids)
    alternative_ids = set(alternative_location_ids)
    proposals = [
        evaluate_migration_pair(
            current_id,
            alternative_id,
            source_values,
            locations,
            neighbors,
            roads,
            **kwargs,
        )
        for current_id in current_ids
        for alternative_id in alternative_ids
        if current_id != alternative_id
    ]
    return sorted(
        proposals,
        key=lambda proposal: (
            proposal.net_gain,
            proposal.recommended_score,
            -proposal.current_score,
        ),
        reverse=True,
    )


def choose_migration(
    proposals: Iterable[MigrationProposal],
    *,
    nationwide_value: float,
    relative_threshold: float = 1.2,
) -> MigrationProposal | None:
    absolute_threshold = max(2.0, nationwide_value * 0.02)
    eligible = (
        proposal
        for proposal in proposals
        if proposal.recommended_score
        >= proposal.current_score * relative_threshold
        and proposal.net_gain >= absolute_threshold
    )
    return max(
        eligible,
        key=lambda proposal: (
            proposal.net_gain,
            proposal.recommended_score,
            -proposal.current_score,
        ),
        default=None,
    )


@dataclass(slots=True)
class MigrationHysteresis:
    """Two consecutive evaluations plus a 12-month accepted-pair cooldown."""

    pending_pair: tuple[int, int] | None = None
    pending_count: int = 0
    accepted_pair: tuple[int, int] | None = None
    cooldown_months: int = 0

    def advance_months(self, months: int = 1) -> None:
        self.cooldown_months = max(0, self.cooldown_months - months)

    def observe(
        self, proposal: MigrationProposal | None, *, confidence_sufficient: bool = True
    ) -> bool:
        if proposal is None or not confidence_sufficient:
            self.pending_pair = None
            self.pending_count = 0
            self.accepted_pair = None
            return False
        pair = (proposal.current_location_id, proposal.recommended_location_id)
        if pair == self.pending_pair:
            self.pending_count += 1
        else:
            self.pending_pair = pair
            self.pending_count = 1
            self.accepted_pair = None
        if self.pending_count < 2 or self.cooldown_months > 0:
            return False
        if self.accepted_pair == pair:
            return False
        self.accepted_pair = pair
        self.cooldown_months = 12
        return True
