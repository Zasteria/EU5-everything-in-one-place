"""Engine grammar and GUI argument contracts the script VM cannot validate."""
import unittest

from src.eu5autobuild.script_syntax import parse
from src.eu5autobuild.construction_slots import MAX_GUI_QUEUE_COUNT, capture_widget as queue_capture_widget
from tests._generated import _blocks_for_token, generated_fixture


def walk(entries):
    for key, op, value in entries:
        yield key, op, value
        if isinstance(value, list):
            yield from walk(value)


class ScriptEngineContracts(unittest.TestCase):
    def test_scripted_triggers_use_scope_blocks_instead_of_dotted_names(self):
        fixture = generated_fixture()
        triggers = {key for key, _, _ in parse(fixture.triggers)}
        for text in (fixture.effects, fixture.triggers, fixture.scripted_guis):
            for key, _, _ in walk(parse(text)):
                self.assertFalse(
                    '.' in key and key.rsplit('.', 1)[-1] in triggers,
                    f'{key}: a scripted trigger must be called inside a scope block',
                )

    def test_formula_and_map_arguments_match_engine_grammar(self):
        fixture = generated_fixture()
        for key, _, value in walk(parse(fixture.values)):
            self.assertNotEqual(key, 'switch', 'switch is not a script-value operator')
            self.assertNotIn('prev.prev', key)
            if isinstance(value, str):
                self.assertNotIn('prev.prev', value)
        for key, _, value in walk(parse(fixture.effects)):
            if key == 'add_to_variable_map':
                self.assertNotIsInstance(dict((k, v) for k, _, v in value).get('value'), list)
            if key == 'variable_list_size':
                self.assertNotIn('target', {k for k, _, _ in value})
            for word in (key, value):
                if isinstance(word, str) and 'variable_map(' in word:
                    self.assertNotIn('$', word, 'Expand map expressions in Python, not engine macros')
            if 'variable_map(' in key and isinstance(value, list):
                self.assertFalse({'value', 'add', 'subtract', 'multiply', 'divide'} &
                                 {k for k, _, _ in value},
                                 'A map-scope comparison block is triggers, not a formula')

    def test_engine_queue_never_promotes_model_size_to_fixed_point(self):
        self.assertNotIn(
            'MakeScopeValue(GetDataModelSize(',
            generated_fixture().engine_queue_gui,
        )

    def test_engine_queue_uses_native_room_predicate_and_literal_count(self):
        gui = queue_capture_widget('contract')
        for count in range(1, MAX_GUI_QUEUE_COUNT + 1):
            self.assertIn(
                f"visible = \"[EqualTo_int32(Construction.CountAllInLocation, '(int32){count}')]\"",
                gui,
            )
            self.assertIn(f"MakeScopeValue('(CFixedPoint){count}')", gui)
        self.assertIn(
            'MakeScopeBool(LessThan_int32(Construction.CountAllInLocation, Construction.GetMaxParallelInQueue))',
            gui,
        )
        self.assertIn("GetScriptedGui('eu5ab_gui_clear_parallel_queue')", gui)
        self.assertNotIn('MakeScopeValue(Construction.CountAllInLocation)', gui)
        self.assertNotIn('MakeScopeValue(Construction.GetMaxParallelInQueue)', gui)
