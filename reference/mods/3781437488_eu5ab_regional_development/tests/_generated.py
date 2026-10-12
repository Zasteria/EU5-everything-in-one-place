"""Cached renderer fixture; treat its inputs and output as read-only.

Runtime harnesses parse the strings into their own mutable VM state.
"""
from functools import cache
import json
from pathlib import Path
from types import SimpleNamespace

from src.eu5autobuild.governor_connections import bundled_straits
from src.eu5autobuild.generator import generated_files
from src.eu5autobuild.governor_generator import GOVERNOR_RECOMMENDATION_BUILDINGS
from src.eu5autobuild.policy import load_building_catalog, load_policies
from src.eu5autobuild.rules import load_automation_rules
from tests._game_data_fixtures import cached_game_data

ROOT = Path(__file__).resolve().parents[1]


def _blocks_for_token(text: str, token: str) -> list[str]:
    blocks: list[str] = []
    offset = 0
    while True:
        start = text.find(token, offset)
        if start < 0:
            return blocks
        brace = text.find("{", start + len(token))
        if brace < 0:
            raise AssertionError(f"{token!r} is missing an opening brace")
        depth = 0
        in_quote = False
        escaped = False
        for index in range(brace, len(text)):
            char = text[index]
            if escaped:
                escaped = False
                continue
            if char == "\\":
                escaped = True
                continue
            if char == '"':
                in_quote = not in_quote
                continue
            if in_quote:
                continue
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    blocks.append(text[start:index + 1])
                    offset = index + 1
                    break
        else:
            raise AssertionError(f"{token!r} has an unbalanced block")


@cache
def generated_fixture():
    cls = SimpleNamespace()
    cls.policies = policies = load_policies(ROOT / "policies" / "templates.json")
    cls.catalog = load_building_catalog(ROOT / "policies" / "building_catalog.json")
    cls.building_count = sum(
        building_id not in GOVERNOR_RECOMMENDATION_BUILDINGS
        for building_id in cls.catalog.buildings
    )
    rules = load_automation_rules(ROOT / "policies" / "automation_rules.json")
    cls.input_source_policy_ids = tuple(
        policy.id for policy in policies
        if policy.auto_build_input_sources
    )
    recipes, construction_demands, upgrades, workforce = cached_game_data()
    cls.files = files = generated_files(
        policies,
        catalog=cls.catalog,
        rules=rules,
        recipes=recipes,
        construction_demands=construction_demands,
        upgrades=upgrades,
        workforce=workforce, straits=bundled_straits(),
    )
    cls.policy_ids = tuple(policy.id for policy in policies)
    cls.effects = files[
        ROOT / "in_game" / "common" / "scripted_effects" / "eu5ab_scripted_effects.txt"
    ]
    cls.triggers = files[
        ROOT / "in_game" / "common" / "scripted_triggers" / "eu5ab_scripted_triggers.txt"
    ]
    cls.values = files[
        ROOT / "in_game" / "common" / "script_values" / "eu5ab_script_values.txt"
    ]
    cls.scripted_guis = files[
        ROOT / "in_game" / "common" / "scripted_guis" / "eu5ab_scripted_guis.txt"
    ]
    cls.engine_queue_gui = files[
        ROOT / "in_game" / "gui" / "eu5ab_engine_queue_window.gui"
    ]
    cls.events = files[
        ROOT / "in_game" / "events" / "eu5ab_monthly_events.txt"
    ]
    cls.on_actions = files[
        ROOT / "in_game" / "common" / "on_action" / "eu5ab_on_actions.txt"
    ]
    cls.chinese_localization = files[
        ROOT / "in_game" / "localization" / "simp_chinese" / "eu5ab_l_simp_chinese.yml"
    ]
    cls.english_localization = files[
        ROOT / "in_game" / "localization" / "english" / "eu5ab_l_english.yml"
    ]
    cls.construction_demands = json.loads(files[
        ROOT / ".metadata" / "eu5ab_construction_demands.json"
    ])
    return cls
