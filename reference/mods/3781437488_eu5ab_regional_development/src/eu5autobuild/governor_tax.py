"""Experimental offline tax forecast. Never used by the production generator.

Compare two steady states, with and without the new source, holding wealth,
estate tax rates and non-Proximity control modifiers fixed. This is not an
immediate next-month prediction or a live-engine counterfactual.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Mapping

from .governor_model import propagate_proximity


def estimate_monthly_tax_gain(
    old_max_control: float | None,
    proximity_gain: float,
    estate_possible_tax: Mapping[str, float],
    tax_rates: Mapping[str, float],
    *,
    control_per_full_proximity: float,
) -> dict:
    """Return a conditional steady-state estimate, or an explicit missing reason.

    A zero clamped ceiling hides negative modifiers, so do not extrapolate it.
    Missing rates are unknown rather than implicit tax exemptions.
    """
    def unknown(reason):
        return dict(monthly_tax_gain=None, reason=reason)
    if old_max_control is None or not math.isfinite(old_max_control):
        return unknown("missing_max_control")
    if not 0 <= old_max_control <= 1:
        return unknown("invalid_max_control")
    if not math.isfinite(proximity_gain) or not math.isfinite(control_per_full_proximity):
        return unknown("invalid_proximity_input")
    if not 0 <= proximity_gain <= 100 or control_per_full_proximity < 0:
        return unknown("invalid_proximity_input")
    if proximity_gain == 0 or old_max_control == 1 or control_per_full_proximity == 0:
        return dict(monthly_tax_gain=0.0, control_gain=0.0, reason=None)
    if old_max_control == 0:
        return unknown("clamped_zero_max_control")
    if not estate_possible_tax:
        return unknown("missing_estate_wealth")
    full_control_tax = 0.0
    unknown_rate_wealth = 0.0
    missing_rates = []
    for estate, wealth in estate_possible_tax.items():
        if not math.isfinite(wealth) or wealth < 0:
            return unknown("invalid_estate_wealth")
        if wealth == 0:
            continue
        rate = tax_rates.get(estate)
        if rate is None:
            missing_rates.append(estate)
            unknown_rate_wealth += wealth
            continue
        if not math.isfinite(rate) or not 0 <= rate <= 1:
            return unknown("invalid_tax_rate:" + estate)
        full_control_tax += wealth * rate
    gain = min(1 - old_max_control, proximity_gain / 100 * control_per_full_proximity)
    if missing_rates:
        return dict(monthly_tax_gain=None, control_gain=gain,
                    monthly_tax_gain_lower=full_control_tax * gain,
                    monthly_tax_gain_upper=(full_control_tax + unknown_rate_wealth) * gain,
                    reason="missing_tax_rate:" + ",".join(sorted(missing_rates)))
    return dict(monthly_tax_gain=full_control_tax * gain, control_gain=gain,
                old_max_control=old_max_control, new_max_control=old_max_control + gain,
                full_control_monthly_tax=full_control_tax, reason=None)


def read_proximity_control_coefficient(game_layer: Path) -> tuple[float, str]:
    source = game_layer / "main_menu/common/static_modifiers/location.txt"
    text = source.read_text(encoding="utf-8-sig")
    block = re.search(r"(?m)^proximity_to_capital\s*=\s*\{(.*?)^\}", text, re.S)
    value = re.search(r"(?m)^\s*local_max_control\s*=\s*([\d.]+)\s*$", block[1]) if block else None
    if value is None:
        raise ValueError(f"Cannot identify vanilla Proximity control coefficient in {source}")
    return float(value[1]), str(source)


def parse_tax_rate_override(value: str) -> tuple[str, float]:
    estate, separator, raw_rate = value.partition("=")
    if not separator or not re.fullmatch(r"[a-z_]+_estate", estate):
        raise ValueError("Use estate_id=rate, for example clergy_estate=0")
    rate = float(raw_rate)
    if not math.isfinite(rate) or not 0 <= rate <= 1:
        raise ValueError("Tax rates must be between 0 and 1")
    return estate, rate


def write_tax_report(path, snapshot, game_layer, owned_raw, locations,
                     candidates, graph, roads, special_edges, tax_rate_overrides=None):
    coefficient, coefficient_source = read_proximity_control_coefficient(game_layer)
    rates = dict(snapshot.tax_rates.get(snapshot.player_country_id, {}))
    overrides = dict(tax_rate_overrides or {})
    rates.update(overrides)
    results = []
    # Evaluate every structural candidate, not the current proxy-score shortlist.
    for candidate in sorted(candidates):
        try:
            predicted = propagate_proximity(
                {candidate: 80.0}, locations, graph, roads,
                special_edges=special_edges, max_depth=None,
                max_steps=max(100, len(locations) * 20), require_complete=True,
            )
        except RuntimeError as exc:
            results.append(dict(location_id=candidate, location=locations[candidate].name,
                                monthly_tax_gain=None, reason=str(exc), complete=False))
            continue
        nodes = []
        for location_id, proximity in sorted(predicted.items()):
            gain = max(0, proximity - locations[location_id].proximity)
            if gain <= 0:
                continue
            raw = owned_raw[location_id]
            estimate = estimate_monthly_tax_gain(
                raw.runtime_variables.get("eu5ab_gov_cached_old_max_control"), gain,
                raw.estate_possible_tax, rates, control_per_full_proximity=coefficient,
            )
            nodes.append(dict(location_id=location_id, location=locations[location_id].name,
                              current_control=raw.control, proximity_gain=gain, **estimate))
        missing = [n["location_id"] for n in nodes if n["monthly_tax_gain"] is None]
        lower = [n.get("monthly_tax_gain_lower", n["monthly_tax_gain"]) for n in nodes]
        upper = [n.get("monthly_tax_gain_upper", n["monthly_tax_gain"]) for n in nodes]
        subtotal = sum(n["monthly_tax_gain"] or 0 for n in nodes)
        results.append(dict(
            location_id=candidate, location=locations[candidate].name,
            monthly_tax_gain=None if missing else subtotal,
            known_monthly_tax_subtotal=subtotal, complete=not missing,
            monthly_tax_gain_lower=None if None in lower else sum(lower),
            monthly_tax_gain_upper=None if None in upper else sum(upper),
            missing_location_ids=missing, affected_locations=len(nodes), nodes=nodes,
        ))
    results.sort(key=lambda r: (r.get("monthly_tax_gain_lower") is None,
                               -(r.get("monthly_tax_gain_lower") or 0), r["location_id"]))
    report = dict(
        status="experimental_not_engine_validated", date=snapshot.date,
        player_country_id=snapshot.player_country_id,
        metric="additional_monthly_tax_after_control_settles",
        ordering="descending_conditional_lower_bound_not_verified_recommendations",
        coefficient=coefficient, coefficient_source=coefficient_source, tax_rates=rates,
        confirmed_tax_rate_overrides=overrides,
        assumptions=[
            "Other control modifiers, estate wealth and tax rates remain fixed.",
            "Proximity contributes linearly to Max Control with the vanilla coefficient.",
            "Compare future control ceilings in both scenarios, not current low control against a future ceiling.",
            "Control eventually reaches its ceiling; no claim about next-month receipts or recovery time.",
            "Cached Max Control may predate the save; mod overrides are not reconstructed.",
            "Only Proximity-mediated tax is estimated; construction effects on wealth are excluded.",
            "Structural candidates are offline approximations; capacity and final build legality need the engine.",
            "Missing estate rates span 0-100%; intervals are conditional on the model, not confidence intervals.",
        ],
        candidates=results,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
