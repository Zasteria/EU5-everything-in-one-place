"""Lower map membership to a total predicate without creating map entries.

EU5 logs an error when is_key_in_variable_map sees an absent map. Sparse
ledgers and caches intentionally have no map until their first nonzero entry.
Keep their existing missing-key branches, including NOT and live fallbacks.
"""
import re

from .script_syntax import parse


_READS = re.compile(
    r'"(?:\\.|[^"\\])*"|#[^\n]*|'
    r'(?P<check>(?<![\w:.])is_key_in_variable_map\s*=\s*\{[^{}]*\})'
)


def guard_map_membership(text):
    """Final, once-only lowering; preserve surrounding text and scope depth.

    AND's existence test supplies false for absent maps. The conditional
    separately protects the native lookup even when all AND children are
    evaluated (for example while generating a trigger description). Logical
    blocks do not push a scope, so target=prev retains its original meaning.
    Do not initialize maps or change the consumers' readiness/zero semantics.
    """
    def guard(match):
        query = match.group('check')
        if query is None:
            return match[0]
        fields = parse(query)[0][2]
        names = [value for key, op, value in fields if key == 'name' and op == '=']
        if len(names) != 1 or not isinstance(names[0], str):
            raise ValueError(f'Expected a scalar map name: {query}')
        name = names[0]
        return (f'AND = {{ has_variable_map = {name} '
                f'trigger_if = {{ limit = {{ has_variable_map = {name} }} '
                f'{query} }} }}')

    return _READS.sub(guard, text)
