"""Complete-layout reference policy, independent of the experimental scorer.

Select maximum marginal gain, respecting transport-cost bands for Local seats.
Scores before and after share an explicitly reconstructed source baseline.
"""
from __future__ import annotations

from dataclasses import dataclass
import heapq
import math
from time import perf_counter

from .governor_model import (
    PropagationBudgetExceeded, _edge_cost, location_value, propagate_proximity,
)
from .governor_transport import TransportContext, TransportMode
from .governor_planner import LOCAL_PLANNER, PlannerType

TRANSPORT_BAND_WIDTH = 40.0
MIGRATION_RELATIVE_RATE = .80


def capital_transport_costs(capital, locations, neighbors, roads, *,
                            special_edges=None, max_steps=None,
                            transport_context: TransportContext | None = None):
    """Shortest directed costs; no context explicitly replays legacy costs."""
    if capital not in locations:
        return {}
    special_edges = special_edges or set()
    budget = len(locations) if max_steps is None else max_steps
    distances = {capital: 0.0}
    queue = [(0.0, capital)]
    visited = set()
    while queue:
        cost, node = heapq.heappop(queue)
        if node in visited:
            continue
        if len(visited) >= budget:
            raise PropagationBudgetExceeded("Capital-distance queue has unfinished work")
        visited.add(node)
        for target in sorted(neighbors.get(node, set())):
            edge = frozenset((node, target))
            if target not in locations or edge in special_edges:
                continue
            candidate = cost + (
                transport_context.edge_cost(node, target, roads.get(edge))
                if transport_context is not None else
                _edge_cost(locations[target], roads.get(edge),
                           base_road_cost=20, base_land_cost=40))
            if candidate < distances.get(target, float("inf")):
                distances[target] = candidate
                heapq.heappush(queue, (candidate, target))
    return distances


def plan_complete_layout(existing, candidates, sources, locations, neighbors, roads,
                         *, capital, profile="mixed", special_edges=None,
                         max_steps=None, band_width=TRANSPORT_BAND_WIDTH,
                         relative_rate=MIGRATION_RELATIVE_RATE,
                         transport_context: TransportContext | None = None,
                         scored_location_ids=None, planner: PlannerType = LOCAL_PLANNER):
    """Compare a full layout and every legal single-seat replacement.

    The caller supplies eligible new sites. Old sites can always be retained.
    Coverage is cached once per source across all rounds. Unfinished queues
    raise rather than returning a partial recommendation. Planning gain is
    relative to earlier planned seats, NOT a single real relocation's gain.
    Each proposal must improve by its own changed seats' contribution times
    ``relative_rate``, without an absolute floor. Only qualifying plans
    compete with retaining the current layout. All comparisons share the same
    caller-supplied road graph, including any future-road assumptions.
    ``scored_location_ids`` excludes transit-only lake nodes from economics.
    """
    started = perf_counter()
    if band_width <= 0:
        raise ValueError("Band width must be positive")
    if not math.isfinite(relative_rate) or relative_rate < 0:
        raise ValueError("Relative rate must be finite and non-negative")
    existing = set(existing)
    candidates = set(candidates) | existing
    if not candidates <= locations.keys():
        raise ValueError("A candidate is outside the location snapshot")
    if any(getattr(locations[n], "is_transit_only", False) for n in candidates):
        raise ValueError("A transit-only node cannot be a governor seat")
    scored_ids = set(locations) if scored_location_ids is None else set(scored_location_ids)
    if not scored_ids <= locations.keys() or not candidates <= scored_ids:
        raise ValueError("Scored locations must include every candidate and exist in the snapshot")
    base_sources = dict(sources)
    for node in existing:
        if node not in base_sources or not math.isfinite(base_sources[node]):
            raise ValueError("An existing seat has no raw source snapshot")
        # Raw modifiers may be negative or exceed 100. Clamp only in propagation.
        base_sources[node] -= 80
    distances = capital_transport_costs(capital, locations, neighbors, roads,
                                        special_edges=special_edges,
                                        transport_context=transport_context) if planner.capital_bands else {}

    def band(node):
        if not planner.capital_bands:
            return 0
        return int(distances[node] // band_width) if node in distances else 1000000

    propagation = dict(special_edges=special_edges, max_depth=None, naval=planner.allow_straits,
                       max_steps=max(100, len(locations) * 20) if max_steps is None else max_steps,
                       require_complete=True, transport_context=transport_context)
    base = propagate_proximity(base_sources, locations, neighbors, roads, **propagation)
    current = propagate_proximity(sources, locations, neighbors, roads, **propagation)
    weights = {n: location_value(locations[n], profile) / 100 for n in sorted(scored_ids)}
    minimum_site_gain = max(1.0, sum(weights.values())) if planner.capital_bands else 0.00001
    footprints = {node: propagate_proximity(
        {node: min(100, base_sources.get(node, 0) + 80)},
        locations, neighbors, roads, **propagation) for node in sorted(candidates)}
    baseline = dict(base)
    selected = []
    evaluations = 0
    for _ in existing:
        available = candidates - set(selected)
        scored = {node: sum(max(0, p-baseline.get(n, 0)) * weights.get(n, 0)
                             for n, p in footprints[node].items()) for node in available}
        evaluations += len(scored)
        useful = [n for n in available if scored[n] >= minimum_site_gain]
        if useful:
            inner = min(band(n) for n in useful)
            winner = max((n for n in useful if band(n) == inner),
                         key=lambda n: (scored[n], n in existing, -n))
        else:
            winner = min(available, key=lambda n: (n not in existing, band(n), n))
        selected.append(winner)
        for n, p in footprints[winner].items():
            baseline[n] = max(baseline.get(n, 0), p)

    def score(coverage):
        return sum((coverage.get(n, 0)-base.get(n, 0))*w for n, w in weights.items())

    def coverage_for(seats):
        result = dict(base)
        for seat in sorted(seats):
            for n, p in footprints[seat].items():
                result[n] = max(result.get(n, 0), p)
        return result

    before = score(current)
    comparable_to_live = (transport_context is None
                          or transport_context.mode is TransportMode.ACTUAL)
    residual = (sum(abs(current.get(n, 0)-locations[n].proximity)*w
                    for n, w in weights.items()) if comparable_to_live else None)

    def proposal(seats, after, retained_score, kind):
        changed = max(0.0, before-retained_score)
        threshold = changed*relative_rate
        net = after-before
        return dict(seats=list(seats), modeled_after=after, modeled_net=net,
                    changed_contribution=changed, migration_threshold=threshold,
                    qualifies=net > 0 and net >= threshold and set(seats) != existing,
                    proposal_kind=kind)

    full = proposal(selected, score(baseline),
                    score(coverage_for(existing & set(selected))), "full_layout")
    chosen = proposal(sorted(existing), before, before, "retain")
    if full["qualifies"]:
        chosen = full
    single_swap_comparisons = 0
    best_by_destination = {}
    # Removing a seat retains the capital, other source buildings, and every
    # other completed seat. Footprints are reused; no new propagation runs are
    # introduced by the single-seat comparisons.
    for origin in sorted(existing):
        retained = coverage_for(existing - {origin})
        retained_score = score(retained)
        for destination in sorted(candidates - existing):
            gain = sum(max(0, p-retained.get(n, 0))*weights.get(n, 0)
                       for n, p in footprints[destination].items())
            single = proposal(sorted(existing - {origin} | {destination}),
                              retained_score+gain, retained_score, "single_swap")
            single_swap_comparisons += 1
            preview = dict(origin_id=origin, origin=locations[origin].name,
                           destination_id=destination, destination=locations[destination].name,
                           before=single["changed_contribution"], after=gain,
                           net=single["modeled_net"], qualifies=single["qualifies"],
                           gain_percent=(single["modeled_net"] / single["changed_contribution"] * 100
                                         if single["changed_contribution"] > 0 else None))
            previous = best_by_destination.get(destination)
            if previous is None or preview["net"] > previous["net"]:
                best_by_destination[destination] = preview
            # Stable ties retain the full proposal, or the earliest single
            # proposal in origin/destination order.
            if single["qualifies"] and single["modeled_net"] > chosen["modeled_net"]:
                chosen = single

    # Retained destinations are matched first. All other destinations are
    # currently vacant, preventing old-site assignment conflicts and cycles.
    def make_steps(seats):
        remaining_origins = existing - set(seats)
        ordered = sorted(seats, key=lambda n: (band(n), seats.index(n)))
        running = dict(base)
        result = []
        for node in ordered:
            origin = node if node in existing else min(
                remaining_origins,
                key=lambda n: (abs(distances.get(n, 1e9)-distances.get(node, 1e9)), n))
            remaining_origins.discard(origin)
            gain = sum(max(0, p-running.get(n, 0))*weights.get(n, 0)
                       for n, p in footprints[node].items())
            result.append(dict(step=len(result)+1, origin_id=origin, origin=locations[origin].name,
                               destination_id=node, destination=locations[node].name,
                               transport_band=band(node), planning_gain=round(gain, 3),
                               retained=node == origin))
            for n, p in footprints[node].items():
                running[n] = max(running.get(n, 0), p)
        return result

    def diagnostics(item):
        return {key: round(value, 3) if isinstance(value, float) else value
                for key, value in item.items() if key != "seats"}

    steps = make_steps(chosen["seats"])
    return dict(existing=[dict(id=n, name=locations[n].name) for n in sorted(existing)],
                steps=steps, display_steps=steps,
                modeled_before=round(before, 3), **diagnostics(chosen),
                relative_rate=relative_rate,
                top_candidates=[diagnostics(item) for item in sorted(
                    best_by_destination.values(), key=lambda item: (-item["net"], item["destination_id"]))[:3]],
                full_layout=dict(steps=make_steps(full["seats"]), **diagnostics(full)),
                single_swap_comparisons=single_swap_comparisons,
                minimum_site_gain=round(minimum_site_gain, 3),
                live_model_absolute_weighted_error=round(residual, 3) if residual is not None else None,
                transport_mode=transport_context.mode.value if transport_context else "legacy",
                live_error_comparable=comparable_to_live,
                candidate_count=len(candidates), rounds=len(steps),
                scored_candidates=evaluations, footprint_propagations=len(footprints),
                band_width=band_width, seconds=round(perf_counter()-started, 4))


@dataclass
class LayoutConfirmation:
    """Confirm source and target SETS, so a display reorder isn't a new plan."""
    signature: tuple | None = None
    streak: int = 0
    cooldown_months: int = 0
    notified_signature: tuple | None = None

    def observe(self, plan: dict, *, valid: bool = True) -> bool:
        if not valid or not plan["qualifies"]:
            self.signature, self.streak = None, 0
            self.notified_signature = None
            return False
        signature = (tuple(sorted(n["id"] for n in plan["existing"])),
                     tuple(sorted(s["destination_id"] for s in plan["steps"])))
        self.streak = self.streak+1 if signature == self.signature else 1
        self.signature = signature
        if self.streak < 2 or self.cooldown_months or signature == self.notified_signature:
            return False
        self.notified_signature = signature
        self.cooldown_months = 12
        return True

    def month_elapsed(self):
        self.cooldown_months = max(0, self.cooldown_months-1)
