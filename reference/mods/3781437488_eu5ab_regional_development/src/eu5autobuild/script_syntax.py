"""Small clause-language tree used by generator lowering and validation.

Quoted tokens stay quoted, including macro arguments and scope expressions.
This parser checks structure; it does not claim to validate engine semantics.
"""
import re


def parse(text):
    tokens = re.findall(r'"(?:\\.|[^"\\])*"|#[^\n]*|>=|<=|!=|\?=|[{}=<>]|[^\s{}=<>!?]+', text)
    tokens = [t for t in tokens if not t.startswith('#')]
    position = 0

    def block(nested=False):
        nonlocal position
        result = []
        while position < len(tokens):
            key = tokens[position]
            position += 1
            if key == '}':
                if not nested:
                    raise ValueError('Unexpected closing brace')
                return result
            if position >= len(tokens) or tokens[position] not in ('=', '>', '<', '>=', '<=', '!=', '?='):
                result.append((key, '', ''))
                continue
            operator = tokens[position]
            value = tokens[position + 1]
            position += 2
            if value == '{':
                value = block(True)
            result.append((key, operator, value))
        if nested:
            raise ValueError('Unclosed block')
        return result

    return block()


def render(entries, indent=0):
    lines = []
    for key, operator, value in entries:
        prefix = '    ' * indent + key
        if not operator:
            lines.append(prefix)
        elif isinstance(value, list):
            lines.extend((prefix + f' {operator} {{', render(value, indent + 1), '    ' * indent + '}'))
        else:
            lines.append(prefix + f' {operator} {value}')
    return '\n'.join(lines)


def substitute(entries, arguments):
    def word(value):
        for key, replacement in arguments.items():
            value = value.replace('$' + key + '$', replacement)
        return value
    return [(word(k), op, substitute(v, arguments) if isinstance(v, list) else word(v)) for k, op, v in entries]


def specialize(entries, names):
    """Expand only the selected helpers in Python, before Jomini sees strings."""
    definitions = {k: v for k, _, v in entries if k in names}

    def expand(body):
        result = []
        for k, op, v in body:
            if k in definitions:
                arguments = {a: b for a, _, b in v}
                result.extend(expand(substitute(definitions[k], arguments)))
            else:
                result.append((k, op, expand(v) if isinstance(v, list) else v))
        return result

    return [(k, op, expand(v)) for k, op, v in entries if k not in names]


def lower_map_formulas(text):
    """Map values are scope values, not inline script-value formula blocks."""
    def visit(entries):
        out = []
        for k, op, v in entries:
            if k == 'add_to_variable_map' and isinstance(v, list):
                formula = next((x for a, _, x in v if a == 'value'), None)
                if isinstance(formula, list):
                    out.append(('set_local_variable', '=', [('name', '=', 'eu5ab_map_write_value'), ('value', '=', formula)]))
                    v = [(a, b, 'local_var:eu5ab_map_write_value' if a == 'value' else c) for a, b, c in v]
            out.append((k, op, visit(v) if isinstance(v, list) else v))
        return out
    return render(visit(parse(text))) + '\n'
