"""Small Paradox-script extractors for bounded EU5AB runtime data."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
import re
from typing import TypeAlias

from .policy import BuildingCatalog


def registered_dlc_names(game_root: Path) -> frozenset[str]:
    """Read registered identities, not ownership or folder-name guesses."""
    return frozenset(
        json.loads(path.read_text(encoding="utf-8-sig"))["name"]
        for path in (game_root / "game" / "dlc").rglob("*.dlc.json")
    )


Scalar: TypeAlias = str | float
Entry: TypeAlias = tuple[str | None, Scalar | list["Entry"]]
Block: TypeAlias = list[Entry]

RGO_EXPANSION_PRICE_IDS = (
    "expand_rgo_mining",
    "expand_rgo_farming",
    "expand_rgo_hunting",
    "expand_rgo_gathering",
    "expand_rgo_forestry",
)

_TOKEN = re.compile(
    r'"(?:\\.|[^"\\])*"|\{|\}|=|-?(?:\d+(?:\.\d*)?|\.\d+)|[A-Za-z_][\w:.-]*'
)


def _without_comments(text: str) -> str:
    lines: list[str] = []
    for line in text.splitlines():
        quoted = False
        escaped = False
        kept: list[str] = []
        for character in line:
            if character == '"' and not escaped:
                quoted = not quoted
            if character == "#" and not quoted:
                break
            kept.append(character)
            escaped = character == "\\" and not escaped
            if character != "\\":
                escaped = False
        lines.append("".join(kept))
    return "\n".join(lines)


def _atom(token: str) -> Scalar:
    if token.startswith('"') and token.endswith('"'):
        return token[1:-1]
    try:
        return float(token)
    except ValueError:
        return token


def parse_paradox_script(text: str) -> Block:
    """Parse the subset needed for definitions while preserving repeated keys."""
    tokens = _TOKEN.findall(_without_comments(text))
    index = 0

    def parse_entries(stop_at_brace: bool = False) -> Block:
        nonlocal index
        entries: Block = []
        while index < len(tokens):
            current = tokens[index]
            if current == "}":
                if not stop_at_brace:
                    raise ValueError("Unexpected closing brace")
                index += 1
                return entries
            if current == "{":
                index += 1
                entries.append((None, parse_entries(True)))
                continue
            index += 1
            key = str(_atom(current))
            if index < len(tokens) and tokens[index] == "=":
                index += 1
                if index >= len(tokens):
                    raise ValueError(f"Missing value for {key}")
                if tokens[index] == "{":
                    index += 1
                    value: Scalar | Block = parse_entries(True)
                else:
                    value = _atom(tokens[index])
                    index += 1
                entries.append((key, value))
            else:
                entries.append((None, key))
        if stop_at_brace:
            raise ValueError("Unclosed block")
        return entries

    return parse_entries()


def _blocks_from_directory(path: Path) -> dict[str, Block]:
    definitions: dict[str, Block] = {}
    for source in sorted(path.glob("*.txt")):
        for key, value in parse_paradox_script(source.read_text(encoding="utf-8-sig")):
            if key is not None and isinstance(value, list):
                definitions[key] = value
    return definitions


def _first_block(block: Block, key: str) -> Block | None:
    for entry_key, value in block:
        if entry_key == key and isinstance(value, list):
            return value
    return None


def _atoms(block: Block) -> tuple[str, ...]:
    return tuple(str(value) for key, value in block if key is None and not isinstance(value, list))


def extract_rgo_base_costs(game_root: Path) -> dict[str, float]:
    """Read the five vanilla RGO expansion base-gold prices."""
    prices = _blocks_from_directory(
        game_root / "game" / "in_game" / "common" / "prices"
    )
    result: dict[str, float] = {}
    for price_id in RGO_EXPANSION_PRICE_IDS:
        block = prices.get(price_id)
        if block is None:
            raise ValueError(f"Missing vanilla RGO price: {price_id}")
        gold = next(
            (
                float(value)
                for key, value in block
                if key == "gold" and isinstance(value, float)
            ),
            None,
        )
        if gold is None or gold <= 0:
            raise ValueError(f"Invalid vanilla RGO gold price: {price_id}")
        result[price_id] = gold
    return result


@dataclass(frozen=True)
class ProductionRecipe:
    building_id: str
    production_method_id: str
    outputs: dict[str, float]
    inputs: dict[str, float]
    raw_inputs: dict[str, float]
    has_potential: bool
    has_allow: bool

    @property
    def is_economic(self) -> bool:
        return bool(self.outputs)


@dataclass(frozen=True)
class ConstructionDemand:
    """Vanilla construction-goods demand for one supported building type."""

    building_id: str
    demand_id: str
    goods: dict[str, float]


@dataclass(frozen=True)
class BuildingUpgradeData:
    """Vanilla replacement chains rooted at EU5AB-supported candidates.

    Successors are the newer EU5AB-supported destinations reachable through
    the vanilla chain. Predecessors include unsupported vanilla intermediates
    so a supported destination can still recognise every upgradeable source.
    """

    successors: dict[str, tuple[str, ...]]
    predecessors: dict[str, tuple[str, ...]]
    # Full native graph for queued manual upgrades, including unsupported tiers.
    native_successors: dict[str, tuple[str, ...]] = field(default_factory=dict)


@dataclass(frozen=True)
class BuildingWorkforce:
    """Vanilla jobs created by one building level.

    EU5 1.3.11 defines one ``pop_type`` and one ``employment_size`` on a
    building type. The vanilla readme defines one employment-size unit as
    1,000 people. ``pop_types`` remains a tuple so the decision model can
    represent future vanilla schemas without changing saved EU5AB data.
    """

    building_id: str
    pop_types: tuple[str, ...]
    jobs_per_level: float
    employment_size_id: str | None


@dataclass(frozen=True)
class PromotionPath:
    """Static, direct vanilla ``promote_to`` paths for one source pop type."""

    source_pop_type: str
    targets: tuple[str, ...]
    promotion_factor: float
    has_cap: bool


@dataclass(frozen=True)
class WorkforceModelData:
    buildings: dict[str, BuildingWorkforce]
    all_buildings: dict[str, BuildingWorkforce]
    promotion_paths: dict[str, PromotionPath]
    base_promotion_speed: float | None
    monthly_script_value_available: bool = False
    rgo_jobs_per_level: float | None = None


def _recipe_from_method(
    building_id: str,
    method_id: str,
    method: Block,
    goods_ids: set[str],
    raw_goods: set[str],
) -> ProductionRecipe:
    produced_goods = [
        str(value)
        for key, value in method
        if key == "produced" and not isinstance(value, list)
    ]
    output_values = [
        float(value)
        for key, value in method
        if key == "output" and isinstance(value, float)
    ]
    outputs: dict[str, float] = {}
    for index, good in enumerate(produced_goods):
        if output_values:
            outputs[good.removeprefix("goods:")] = output_values[min(index, len(output_values) - 1)]

    inputs = {
        key.removeprefix("goods:"): float(value)
        for key, value in method
        if key is not None
        and key.removeprefix("goods:") in goods_ids
        and isinstance(value, float)
    }
    return ProductionRecipe(
        building_id=building_id,
        production_method_id=method_id,
        outputs=dict(sorted(outputs.items())),
        inputs=dict(sorted(inputs.items())),
        raw_inputs=dict(
            sorted((good, value) for good, value in inputs.items() if good in raw_goods)
        ),
        has_potential=any(key == "potential" for key, _ in method),
        has_allow=any(key == "allow" for key, _ in method),
    )


def extract_supported_recipes(
    game_root: Path,
    catalog: BuildingCatalog,
    preferred_methods: dict[str, str] | None = None,
) -> dict[str, ProductionRecipe]:
    """Extract one bounded default/preferred recipe per supported building."""
    common = game_root / "game" / "in_game" / "common"
    building_definitions = _blocks_from_directory(common / "building_types")
    method_definitions = _blocks_from_directory(common / "production_methods")
    goods_definitions = _blocks_from_directory(common / "goods")
    goods_ids = set(goods_definitions)
    raw_goods = {
        good_id
        for good_id, block in goods_definitions.items()
        if not any(
            key == "category"
            and str(value).removeprefix("goods_category:") == "produced"
            for key, value in block
            if not isinstance(value, list)
        )
    }
    preferred_methods = preferred_methods or {}
    recipes: dict[str, ProductionRecipe] = {}

    for building_id in sorted(catalog.buildings):
        building = building_definitions.get(building_id)
        if building is None:
            continue
        candidates: list[tuple[str, Block]] = []
        unique = _first_block(building, "unique_production_methods")
        if unique is not None:
            candidates.extend(
                (method_id, value)
                for method_id, value in unique
                if method_id is not None and isinstance(value, list)
            )
        possible = _first_block(building, "possible_production_methods")
        if possible is not None:
            candidates.extend(
                (method_id, method_definitions[method_id])
                for method_id in _atoms(possible)
                if method_id in method_definitions
            )
        if not candidates:
            continue

        preferred = preferred_methods.get(building_id)
        selected = next(
            (candidate for candidate in candidates if candidate[0] == preferred),
            candidates[0],
        )
        recipe = _recipe_from_method(
            building_id,
            selected[0],
            selected[1],
            goods_ids,
            raw_goods,
        )
        if recipe.is_economic:
            recipes[building_id] = recipe
    return recipes


def recipes_as_json(recipes: dict[str, ProductionRecipe]) -> str:
    payload = {
        "schema_version": 1,
        "recipes": [asdict(recipes[key]) for key in sorted(recipes)],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def extract_supported_construction_demands(
    game_root: Path,
    catalog: BuildingCatalog,
) -> dict[str, ConstructionDemand]:
    """Resolve each supported building's vanilla construction-demand bundle.

    EU5 stores a demand id on the building type and the actual goods quantities
    in ``common/goods_demand``. Keeping the resolved table in generated metadata
    lets runtime script enforce the same material mix without hard-coding one
    assumed recipe for every building tier.
    """

    common = game_root / "game" / "in_game" / "common"
    building_definitions = _blocks_from_directory(common / "building_types")
    demand_definitions = _blocks_from_directory(common / "goods_demand")
    demands: dict[str, ConstructionDemand] = {}

    for building_id in sorted(catalog.buildings):
        building = building_definitions.get(building_id)
        if building is None:
            continue
        raw_demand_id = _first_scalar(building, "construction_demand")
        if raw_demand_id is None:
            continue
        demand_id = str(raw_demand_id).removeprefix("goods_demand:")
        demand = demand_definitions.get(demand_id)
        if demand is None:
            continue
        goods = {
            str(key).removeprefix("goods:"): float(value)
            for key, value in demand
            if key not in {None, "category"} and isinstance(value, float)
        }
        demands[building_id] = ConstructionDemand(
            building_id=building_id,
            demand_id=demand_id,
            goods=dict(sorted(goods.items())),
        )
    return demands


def construction_demands_as_json(
    demands: dict[str, ConstructionDemand],
) -> str:
    payload = {
        "schema_version": 1,
        "source": "vanilla common/building_types + common/goods_demand",
        "buildings": [asdict(demands[key]) for key in sorted(demands)],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _first_scalar(block: Block, key: str) -> Scalar | None:
    for entry_key, value in block:
        if entry_key == key and not isinstance(value, list):
            return value
    return None


def _top_level_scalars(path: Path) -> dict[str, Scalar]:
    if not path.exists():
        return {}
    return {
        key: value
        for key, value in parse_paradox_script(path.read_text(encoding="utf-8-sig"))
        if key is not None and not isinstance(value, list)
    }


def _resolve_float(
    value: Scalar | None,
    constants: dict[str, Scalar],
) -> tuple[float | None, str | None]:
    if isinstance(value, float):
        return value, None
    if value is None:
        return None, None
    constant_id = str(value)
    resolved = constants.get(constant_id)
    if isinstance(resolved, float):
        return resolved, constant_id
    return None, constant_id


def extract_workforce_model(
    game_root: Path,
    catalog: BuildingCatalog,
) -> WorkforceModelData:
    """Extract reproducible workforce structure without inventing promotion rates.

    Vanilla exposes the exact monthly promotion amount only to GUI data bindings
    (Location.GetPromoteValue in 1.3.11), not to script values. The returned
    model therefore records the static promotion graph and base modifier while
    deliberately marking the runtime monthly amount unavailable.
    """

    common = game_root / "game" / "in_game" / "common"
    building_definitions = _blocks_from_directory(common / "building_types")
    employment_constants = _top_level_scalars(
        game_root
        / "game"
        / "main_menu"
        / "common"
        / "script_values"
        / "default_values.txt"
    )

    all_buildings: dict[str, BuildingWorkforce] = {}
    for building_id, block in sorted(building_definitions.items()):
        pop_value = _first_scalar(block, "pop_type")
        employment_value = _first_scalar(block, "employment_size")
        employment_size, employment_size_id = _resolve_float(
            employment_value,
            employment_constants,
        )
        if pop_value is None or employment_size is None:
            continue
        pop_type = str(pop_value).removeprefix("pop_type:")
        all_buildings[building_id] = BuildingWorkforce(
            building_id=building_id,
            pop_types=(pop_type,),
            jobs_per_level=employment_size * 1000.0,
            employment_size_id=employment_size_id,
        )

    promotion_paths: dict[str, PromotionPath] = {}
    for source_pop_type, block in sorted(
        _blocks_from_directory(common / "pop_types").items()
    ):
        targets = tuple(
            sorted(
                str(value).removeprefix("pop_type:")
                for key, value in block
                if key == "promote_to" and not isinstance(value, list)
            )
        )
        factor_value = _first_scalar(block, "promotion_factor")
        factor = float(factor_value) if isinstance(factor_value, float) else 1.0
        promotion_paths[source_pop_type] = PromotionPath(
            source_pop_type=source_pop_type,
            targets=targets,
            promotion_factor=factor,
            has_cap=str(_first_scalar(block, "has_cap")).lower() == "yes",
        )

    location_modifiers = _blocks_from_directory(
        game_root / "game" / "main_menu" / "common" / "static_modifiers"
    )
    location_block = location_modifiers.get("location_base_values", [])
    base_value = _first_scalar(location_block, "local_pop_promotion_speed")
    base_promotion_speed = float(base_value) if isinstance(base_value, float) else None
    rgo_level_block = location_modifiers.get("rgo_level", [])
    rgo_jobs_value = _first_scalar(
        rgo_level_block,
        "local_laborers_desired_pop",
    )
    rgo_jobs_per_level = (
        float(rgo_jobs_value) * 1000.0
        if isinstance(rgo_jobs_value, float)
        else None
    )

    return WorkforceModelData(
        buildings={
            building_id: all_buildings[building_id]
            for building_id in sorted(catalog.buildings)
            if building_id in all_buildings
        },
        all_buildings=all_buildings,
        promotion_paths=promotion_paths,
        base_promotion_speed=base_promotion_speed,
        monthly_script_value_available=False,
        rgo_jobs_per_level=rgo_jobs_per_level,
    )


def workforce_model_as_json(model: WorkforceModelData) -> str:
    payload = {
        "schema_version": 2,
        "source": {
            "employment_size_unit_people": 1000,
            "base_promotion_speed": model.base_promotion_speed,
            "monthly_script_value_available": model.monthly_script_value_available,
            "fallback": "current_available_population",
            "rgo_jobs_per_level": model.rgo_jobs_per_level,
            "rgo_primary_pop_type": "laborers",
            "rgo_optional_pop_type": "slaves",
            "rgo_optional_pop_type_country_modifier": "allow_rgo_slave_demand",
        },
        "buildings": [
            asdict(model.buildings[key]) for key in sorted(model.buildings)
        ],
        "promotion_paths": [
            asdict(model.promotion_paths[key]) for key in sorted(model.promotion_paths)
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _transitive_nodes(graph: dict[str, set[str]], start: str) -> set[str]:
    visited: set[str] = set()
    pending = list(graph.get(start, ()))
    while pending:
        current = pending.pop()
        if current == start or current in visited:
            continue
        visited.add(current)
        pending.extend(graph.get(current, ()))
    return visited


def extract_building_upgrades(
    game_root: Path,
    catalog: BuildingCatalog,
) -> BuildingUpgradeData:
    """Extract transitive vanilla obsolete relationships for EU5AB types."""
    definitions = _blocks_from_directory(
        game_root / "game" / "in_game" / "common" / "building_types"
    )
    successors: dict[str, set[str]] = {}
    predecessors: dict[str, set[str]] = {}
    for newer_id, block in definitions.items():
        for key, value in block:
            if key != "obsolete" or isinstance(value, list):
                continue
            older_id = str(value).removeprefix("building_type:")
            successors.setdefault(older_id, set()).add(newer_id)
            predecessors.setdefault(newer_id, set()).add(older_id)

    supported = set(catalog.buildings)
    return BuildingUpgradeData(
        successors={
            building_id: tuple(
                sorted(_transitive_nodes(successors, building_id) & supported)
            )
            for building_id in sorted(catalog.buildings)
        },
        predecessors={
            building_id: tuple(sorted(_transitive_nodes(predecessors, building_id)))
            for building_id in sorted(catalog.buildings)
        },
        native_successors={
            building_id: tuple(sorted(_transitive_nodes(successors, building_id)))
            for building_id in sorted(successors)
        },
    )


def building_upgrades_as_json(upgrades: BuildingUpgradeData) -> str:
    payload = {
        "schema_version": 1,
        "buildings": {
            building_id: {
                "successors": list(upgrades.successors.get(building_id, ())),
                "predecessors": list(upgrades.predecessors.get(building_id, ())),
                "native_successors": list(upgrades.native_successors.get(building_id, ())),
            }
            for building_id in sorted(
                set(upgrades.successors) | set(upgrades.predecessors) | set(upgrades.native_successors)
            )
        },
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
