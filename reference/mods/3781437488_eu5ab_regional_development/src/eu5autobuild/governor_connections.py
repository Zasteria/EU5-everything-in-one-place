"""Own the map's strait classification; never depend on another mod's triggers."""
from __future__ import annotations

import csv
import json
from pathlib import Path
import re


SNAPSHOT = Path(__file__).resolve().parents[2] / ".metadata/eu5ab_governor_connections.json"
# Explicit data revision: bump when the bundled topology changes. Ordinary
# rendering must not compute hashes (including cache/version fingerprints).
STRAIT_SCHEMA = 'v1'


def extract_straits(game_root: Path) -> dict[str, list[str]]:
    connections: dict[str, set[str]] = {}
    path = game_root / "game/in_game/map_data/adjacencies.csv"
    with path.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream, delimiter=";"):
            if row["Type"] != "sea":
                continue
            source, target = row["From"], row["To"]
            if not all(re.fullmatch(r"[a-z0-9_]+", name) for name in (source, target)):
                raise ValueError(f"Invalid strait endpoints in {path}: {source}, {target}")
            connections.setdefault(source, set()).add(target)
            connections.setdefault(target, set()).add(source)
    return {name: sorted(targets) for name, targets in sorted(connections.items())}


def bundled_straits() -> dict[str, list[str]]:
    return json.loads(SNAPSHOT.read_text(encoding="utf-8-sig"))


def straits_json(connections: dict[str, list[str]]) -> str:
    return json.dumps(connections, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def render_connection_effects(connections: dict[str, list[str]], *, revision: str = STRAIT_SCHEMA) -> str:
    if not re.fullmatch(r"[a-zA-Z0-9_]+", revision):
        raise ValueError("Topology revision must be a script-safe explicit identifier")
    version = revision
    branches = []
    for source, targets in sorted(connections.items()):
        body = "\n".join(
            f"                add_to_variable_list = {{ name = eu5ab_strait_neighbors target = location:{target} }}"
            for target in sorted(targets)
        )
        branches.append(f"            {source} = {{\n{body}\n            }}")
    return f'''# Static, owner-independent topology. Empty results are cached too.
eu5ab_prepare_strait_connections = {{
    # A version comparison on an unset variable logs an EU5 script error.
    if = {{
        limit = {{ has_variable = eu5ab_strait_schema }}
        if = {{
            limit = {{ NOT = {{ var:eu5ab_strait_schema = flag:eu5ab_map_{version} }} }}
            remove_variable = eu5ab_strait_schema
        }}
    }}
    if = {{
        limit = {{ NOT = {{ has_variable = eu5ab_strait_schema }} }}
        clear_variable_list = eu5ab_strait_neighbors
        switch = {{
            trigger = location_key
{chr(10).join(branches)}
        }}
        set_variable = {{ name = eu5ab_strait_schema value = flag:eu5ab_map_{version} }}
    }}
}}
'''


def render_connection_trigger() -> str:
    return '''eu5ab_is_strait_connection_to = {
    is_target_in_variable_list = { name = eu5ab_strait_neighbors target = $target$ }
}
'''
