"""Read-only save recipe identification against the configured slot graph.

Save block names have no required suffix. Declaration quantities are recipe
coefficients, not observed Building output, employment or realized profit.
"""
from collections import defaultdict
import re

from .production import BuildingProduction


def identify_saved_methods(block: bytes, model: BuildingProduction | None) -> dict:
    """Identify exact top-level method blocks; never infer an active alternative.

Unknown demand-bearing blocks and conflicting slot identities remain explicit
errors rather than being silently dropped or valued as zero.
"""
    blocks = {}
    for match in re.finditer(rb'^\t([\w]+)=\{\r?$', block, re.M):
        end = block.find(b'\n\t}', match.end())
        if end < 0:
            raise ValueError('Unclosed building child block')
        blocks[match[1].decode()] = block[match.end():end]
    configured = {method.production_method_id for slot in model.slots for method in slot} if model else set()
    names = [name for name in blocks if name in configured]
    unknown = [name for name, body in blocks.items() if name not in configured
               and re.search(rb'^\t\tdemand=|^\t\t\tdemand=', body, re.M)]
    slots = [[m.production_method_id for m in slot if m.production_method_id in names]
             for slot in model.slots] if model else []
    if model is None:
        status = 'unresolved_configuration'
    elif unknown:
        status = 'unrecognized_saved_method'
    elif not slots:
        status = 'no_configured_methods'
    elif any(len(slot) > 1 for slot in slots):
        status = 'conflicting_slot'
    elif any(not slot for slot in slots):
        status = 'missing_saved_slot'
    else:
        status = 'configured_saved_methods'
    return dict(methods=names, slots=slots, unrecognized=unknown, status=status)


def associate_recipe(identified: dict, model: BuildingProduction | None,
                     prices: dict[str, float], *, saved_profit=None) -> dict:
    """Link both output and input coefficients to the exact saved slot choices.

Gross margin excludes employment, throughput, wages and taxes. Missing prices
or identities are unknown, not zero. Keep realized save profit independent.
"""
    result = dict(saved_last_months_profit=saved_profit, declared_outputs=None,
                  declared_inputs=None, declared_output_value=None,
                  declared_input_cost=None, declared_gross_margin=None)
    if identified['status'] != 'configured_saved_methods':
        return result
    outputs, inputs = defaultdict(float), defaultdict(float)
    for slot, names in zip(model.slots, identified['slots'], strict=True):
        method = next(m for m in slot if m.production_method_id == names[0])
        for good, amount in method.outputs.items():
            outputs[good] += amount
        for good, amount in method.inputs.items():
            inputs[good] += amount
    result.update(declared_outputs=dict(outputs), declared_inputs=dict(inputs))
    if all(good in prices for good in outputs):
        result['declared_output_value'] = sum(amount * prices[good] for good, amount in outputs.items())
    if all(good in prices for good in inputs):
        result['declared_input_cost'] = sum(amount * prices[good] for good, amount in inputs.items())
    if result['declared_output_value'] is not None and result['declared_input_cost'] is not None:
        result['declared_gross_margin'] = result['declared_output_value'] - result['declared_input_cost']
    return result
