"""Commodity dimensions shared by building and extraction reservations."""


def goods_in(models, rules):
    from .rgo_automation import raw_goods
    return sorted(set(raw_goods()) | set(rules.input_goods) |
                  {g for model in models.values() for slot in model.slots
                   for method in slot for g in (*method.outputs, *method.inputs)})


def map_value(name, key):
    # The generator's final map_access lowering protects the membership test
    # itself; missing maps/keys retain this consumer's zero contribution.
    return f'{{ value = 0 if = {{ limit = {{ is_key_in_variable_map = {{ name = {name} target = {key} }} }} add = "variable_map({name}|{key})" }} }}'
