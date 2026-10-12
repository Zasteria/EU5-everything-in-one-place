"""Commodity assessment for explicit Mod additions and current market data."""
import math
from .rgo_pending import pending_factor

QUANTUM = .00001


def valid(*values):
    return all(v is not None and math.isfinite(v) and v >= 0 for v in values)


def net_output(proposed, predecessor):
    """A proposal reserves only positive commodity-specific net additions."""
    if any(not valid(q) for q in (*proposed.values(), *predecessor.values())):
        return None
    return {good: max(0, q - predecessor.get(good, 0)) for good, q in proposed.items()}


def assess(outputs, demand, supply, pending, prices, future=None, *, emergency=False):
    """Any positive output at its limit vetoes; otherwise use base-value weights.

    No-output facilities are neutral. Emergency waives the curve, never invalid
    output identity or measurements. P=0 retains the RGO first-level rule;
    market supplementation separately requires positive effective demand.
    """
    future = future or {}
    weighted = weight = 0.0
    for good, quantity in outputs.items():
        if not valid(quantity):
            return 0.0
        if quantity == 0:
            continue
        d, s, p, b, f = (demand.get(good), supply.get(good), pending.get(good, 0),
                         prices.get(good), future.get(good, 0))
        if not valid(d, s, p, b, f) or b <= 0:
            return 0.0
        factor = 1 if emergency else pending_factor(p, d + f, s)
        if factor <= 0:
            return 0.0
        w = quantity * b
        weighted += w * factor
        weight += w
    if not valid(weighted, weight):
        return 0.0
    return max(QUANTUM, weighted / weight) if weight > 0 else 1.0
