"""Bounded offline interpreter for generated GUI guards and callbacks.

Checks Promote/Function dispatch against the local 1.3.11 API dump and executes
the rendered datamodel and callbacks using injected native data. It does not
emulate EU5's widget scheduler or claim engine/visual acceptance.
"""
from copy import deepcopy
from numbers import Number
import json
from pathlib import Path
import re

from src.eu5autobuild.script_syntax import parse

API = json.loads(Path(__file__).with_name('production_gui_api.json').read_text())['entries']


def expression(text):
    tokens = re.findall(r"'[^']*'|[A-Za-z_][A-Za-z_0-9]*|[().,]", text.strip('[]'))
    pos = 0

    def read():
        nonlocal pos
        if tokens[pos].startswith("'"):
            value = tokens[pos][1:-1]
            pos += 1
            return value
        chain = []
        while True:
            name = tokens[pos]
            pos += 1
            args = []
            if pos < len(tokens) and tokens[pos] == '(':
                pos += 1
                while tokens[pos] != ')':
                    args.append(read())
                    if tokens[pos] == ',':
                        pos += 1
                    elif tokens[pos] != ')':
                        raise AssertionError(tokens[pos:])
                pos += 1
            chain.append((name, args))
            if pos == len(tokens) or tokens[pos] != '.':
                return chain
            pos += 1

    result = read()
    assert pos == len(tokens), tokens[pos:]
    return result


def check(node, *, promote=False):
    if isinstance(node, str):
        return node.split(')', 1)[0][1:] if node.startswith('(') else 'string'
    owner, fresh = None, False
    for index, (name, args) in enumerate(node):
        types = [check(arg) for arg in args]
        if index == 0 and name in {'TopScope', 'Scope', 'Building', 'BuildingType', 'Location', 'ProductionMethod',
                                   'ActiveProductionMethod', 'GoodsDemandEntry'}:
            owner = name
            continue
        key = f'{owner}.{name}' if owner else name
        declarations = API[key]
        needs_promote = index < len(node) - 1 or promote
        allowed = [ret for kind, ret in declarations
                   if not needs_promote or kind in ('Promote', 'Global promote')]
        assert allowed, f'{key} is Function, not Promote'
        if key in ('TopScope.SetRoot', 'TopScope.AddScope'):
            assert fresh, f'{key} mutates a borrowed const TopScope'
        if key == 'MakeScopeValue':
            assert types == ['CFixedPoint'], types
        if key == 'TopScope.SetRoot':
            assert types == ['Scope'], types
        if key == 'TopScope.AddScope':
            # Native Scope.Self returns an unregistered object and AddScope
            # rejects it; a numeric ticket must be copied with MakeScopeValue.
            assert types[0] == 'string' and types[1] == 'Scope', types
        if key == 'TopScope.GetValue':
            assert types == ['string'], types
        if key in ('ScriptedGui.IsShown', 'ScriptedGui.Execute'):
            assert types == ['TopScope'], types
        owner = allowed[0]
        if name == 'GuiScope':
            fresh = True
    return owner


def check_widget(text):
    def visit(entries):
        for key, _, value in entries:
            if isinstance(value, list):
                visit(value)
            elif isinstance(value, str) and value.strip('"').startswith('['):
                # The clause parser preserves the GUI string's double quotes.
                # Check the actual quoted expressions rather than skipping them.
                kind = check(expression(value.strip('"')), promote=key == 'datacontext')
                if key == 'datacontext':
                    assert kind != 'TopScope', 'Native GUI does not register TopScope datacontext'
    visit(parse(text))


class GuiBridge:
    def __init__(self, vm):
        self.vm = vm
        self.guis = {}
        self.building_reads = []
        self.country_reads = []

    def eval(self, node, context):
        if isinstance(node, str):
            return float(node.split(')', 1)[1]) if node.startswith('(') else node
        value = None
        vm = self.vm
        for index, (name, arguments) in enumerate(node):
            args = [self.eval(arg, context) for arg in arguments]
            if index == 0:
                if name in context:
                    value = context[name]
                    if name == 'Building':
                        self.building_reads.append(value)
                        assert value in vm.building_locations, 'dereferenced vanished building'
                    continue
                if name == 'GuiScope':
                    value = {'root': vm.ROOT, 'scopes': {}}
                elif name == 'GetPlayer':
                    value = context.get('player', vm.ROOT)
                elif name in ('MakeScopeValue', 'MakeScopeBool'):
                    value = args[0]
                elif name == 'GetScriptedGui':
                    value = args[0]
                elif name == 'GetDataModelSize':
                    value = len(args[0])
                elif name == 'DataModelFirst':
                    value = args[0][:int(args[1])]
                elif name == 'DataModelRepeatedItem':
                    value = [None] * int(args[0])
                elif name == 'Select_int32':
                    value = args[1] if args[0] else args[2]
                elif name == 'EqualTo_int32':
                    value = args[0] == args[1]
                elif name == 'GreaterThan_int32':
                    value = args[0] > args[1]
                elif name == 'Multiply_CFixedPoint':
                    value = args[0] * args[1]
                else:
                    raise AssertionError(name)
            elif name == 'Exists':
                value = value in vm.vars
            elif name in ('Self', 'MakeScope', 'End'):
                pass
            elif name == 'SetRoot':
                value['root'] = args[0]
            elif name == 'AddScope':
                value['scopes'][args[0]] = args[1]
            elif name == 'GetValue':
                if isinstance(value, Number):
                    assert not args
                else:
                    value = value['scopes'][args[0]] if 'scopes' in value else value['value']
            elif name == 'GetList':
                self.country_reads.append(value)
                assert value in vm.vars, 'read list from invalid country'
                value = list(vm.lists[value].get(args[0], []))
            elif name == 'GetVariableFromVariableMap':
                value = vm.variable_maps.get(value, {}).get(args[0], {}).get(args[1])
            elif name == 'GetVariable':
                value = vm.vars[value].get(args[0], 0)
            elif name == 'GetBuilding':
                assert value in vm.building_locations, 'promoted invalid Building'
            elif name in ('GetLocation', 'GetBuildingType'):
                pass
            elif name == 'GetProductionMethods':
                value = context['methods']
            elif name == 'GetMethod':
                value = value['method']
            elif name == 'GetGoodsDemand':
                value = context['inputs']
            elif name == 'GetEntries':
                pass
            elif name == 'GetOutput':
                value = context['output']
            elif name == 'GetEffectiveOutput':
                value = context['actual']
            elif name == 'GetInputGoodsAccess':
                value = value['access']
            elif name == 'GetGoods':
                value = value['good']
            elif name == 'GetInputScale':
                value = context['scale']
            elif name == 'IsShown':
                self.country_reads.append(args[0]['root'])
                assert args[0]['root'] in vm.vars, 'queried script on invalid country'
                saved = deepcopy(vm.scopes)
                vm.scopes.update(args[0]['scopes'])
                value = vm.condition(self.guis[value]['is_shown'], [args[0]['root']])
                vm.scopes = saved
            else:
                raise AssertionError(name)
        return value

    def callbacks(self, widget, token, *, animation='eu5ab_pl_background_sample', **native):
        """Collect commands for an explicitly activated named reader state.

        Native probes showed that dynamic _show readers never fired. Do not
        turn every on_finish into an implicit callback in this offline model.
        The activation is injected; this is not an engine timer simulation.
        """
        result = []

        def visit(entries, context, shown=True):
            # Widgets establish contexts/models before evaluating children.
            fields = {k: v for k, _, v in entries}
            if 'datacontext' in fields:
                context = dict(context)
                expr = expression(fields['datacontext'])
                kind = check(expr, promote=True)
                assert kind != 'TopScope', 'Native GUI does not register TopScope datacontext'
                context[kind] = self.eval(expr, context)
            if 'visible' in fields and not self.eval(expression(fields['visible']), context):
                # Still evaluate other fields/children; visibility is not a guard.
                shown = False
            if 'datamodel' in fields:
                for item in self.eval(expression(fields['datamodel']), context):
                    child = dict(context)
                    kind = (None if item is None else
                            'ActiveProductionMethod' if isinstance(item, dict) and 'method' in item
                            else 'GoodsDemandEntry' if isinstance(item, dict) else 'Scope')
                    if kind is not None:
                        child[kind] = item
                    if kind == 'ActiveProductionMethod':
                        child.update({k: v for k, v in item.items() if k not in ('method', 'access')})
                    visit(fields['item'], child, shown)
                return
            if 'name' in fields and 'on_finish' in fields:
                if fields['name'].strip('"') != animation:
                    return
            for key, _, value in entries:
                if key == 'on_finish' and shown:
                    expr = expression(value)
                    assert expr[-1][0] == 'Execute'
                    gui = self.eval(expr[:1], context)
                    args = self.eval(expr[-1][1][0], context)
                    result.append((gui, deepcopy(args)))
                elif isinstance(value, list):
                    visit(value, context, shown)

        visit(parse(widget), {'Scope': token, **native})
        return result

    def deliver(self, command):
        gui, args = command
        saved = deepcopy(self.vm.scopes)
        # Each delayed callback is a separate script invocation, not one giant
        # pulse of 168 requests plus recovery and aggregate refreshes.
        self.vm.operations = 0
        self.vm.scopes.update(args['scopes'])
        self.vm.execute(self.guis[gui]['effect'], [args['root']])
        self.vm.scopes = saved
