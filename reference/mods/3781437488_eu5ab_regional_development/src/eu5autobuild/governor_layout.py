"""Offline whole-layout experiment; not the production game algorithm.

Reuse each source footprint across greedy rounds. All existing local governors
are removed from the explicit source map, never from live buildings. Retaining
an old site remains a valid choice. Scores compare modeled layouts symmetrically.
"""
from __future__ import annotations

from dataclasses import replace
from time import perf_counter

from .governor_model import cheap_score, location_value, propagate_proximity


def plan_layout(existing, candidates, sources, locations, neighbors, roads, *,
                capital, profile="mixed", special_edges=None, shortlist=8,
                max_depth=6):
    started = perf_counter()
    existing = set(existing)
    candidates = set(candidates) | existing
    base_sources = dict(sources)
    for node in existing:
        base_sources[node] = max(0.0, base_sources.get(node, 0.0) - 80.0)
    propagation = dict(special_edges=special_edges, max_depth=max_depth,
                       max_steps=max(100, len(locations) * 20))
    base = propagate_proximity(base_sources, locations, neighbors, roads, **propagation)
    current = propagate_proximity(sources, locations, neighbors, roads, **propagation)
    weights = {n: location_value(v, profile) / 100 for n, v in locations.items()}
    footprints = {}
    baseline = dict(base)
    steps = []
    evaluations = 0
    for index in range(len(existing)):
        virtual = {n: replace(v, proximity=baseline.get(n, 0.0)) for n, v in locations.items()}
        available = candidates - {step["destination_id"] for step in steps}
        pool = sorted(available, key=lambda n: (-cheap_score(n, virtual, neighbors, roads,
                                                           profile=profile), n))
        if shortlist:
            # Always compare retained sites, so shortlist pruning cannot force a move.
            pool = sorted(set(pool[:shortlist]) | (existing & available))
        scored = []
        for node in pool:
            if node not in footprints:
                footprints[node] = propagate_proximity(
                    {node: min(100, base_sources.get(node, 0) + 80)},
                    locations, neighbors, roads, **propagation)
            gain = sum(max(0, p - baseline.get(n, 0)) * weights[n]
                       for n, p in footprints[node].items())
            scored.append((gain, -node, node))
            evaluations += 1
        if not scored:
            break
        gain, _, winner = max(scored)
        steps.append(dict(step=index + 1, destination_id=winner,
                          destination=locations[winner].name, marginal_gain=round(gain, 3),
                          retained=winner in existing))
        for n, p in footprints[winner].items():
            baseline[n] = max(baseline.get(n, 0), p)
    before = sum((current.get(n, 0) - base.get(n, 0)) * w for n, w in weights.items())
    after = sum((baseline.get(n, 0) - base.get(n, 0)) * w for n, w in weights.items())
    residual = sum(abs(current.get(n, 0) - locations[n].proximity) * w
                   for n, w in weights.items())
    chosen = {s["destination_id"] for s in steps}
    return dict(existing=[dict(id=n, name=locations[n].name) for n in sorted(existing)],
                steps=steps, removed=[locations[n].name for n in sorted(existing-chosen)],
                retained=[locations[n].name for n in sorted(existing & chosen)],
                modeled_before=round(before, 3), modeled_after=round(after, 3),
                modeled_net=round(after-before, 3),
                live_model_absolute_weighted_error=round(residual, 3),
                candidate_count=len(candidates), rounds=len(steps),
                scored_candidates=evaluations, footprint_propagations=len(footprints),
                max_depth=max_depth, shortlist=shortlist,
                seconds=round(perf_counter()-started, 4))
