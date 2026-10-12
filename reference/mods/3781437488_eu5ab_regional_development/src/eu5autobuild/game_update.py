"""Versioned upstream observations, semantic diffs and bounded data synchronization.

No hashes, network access, game launch, or compatibility-version changes. Run
``python -B -m src.eu5autobuild.game_update --help`` from the repository root.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import tempfile

from . import catalog_builder as cb, game_data as gd, production, rgo_automation
from .game_root import require_game_root
from .governor_connections import extract_straits
from .industry_promotion import extract_industries
from .policy import BuildingCatalog

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = 1
EXTRACTOR = 1
CONFIG = ROOT / "policies/game_update_rules.json"
STATE = ROOT / ".upstream"
TOKEN = re.compile(r'"(?:\\.|[^"\\])*"|#[^\n]*|[{}=<>!?]+|[^\s{}=<>!?#]+')
DATA_TARGETS = {
    "catalog": "policies/building_catalog.json",
    "raw_goods": ".metadata/eu5ab_raw_goods.json",
    "production": ".metadata/eu5ab_production_recipes.json",
    "construction": ".metadata/eu5ab_construction_demands.json",
    "upgrades": ".metadata/eu5ab_building_upgrades.json",
    "workforce": ".metadata/eu5ab_workforce_model.json",
    "straits": ".metadata/eu5ab_governor_connections.json",
    "industries": ".metadata/eu5ab_industry_types.json",
}


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def json_text(value):
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def normalized_script(text):
    """Keep operators, order and repeated keys; ignore comments and whitespace."""
    return " ".join(m[0] for m in TOKEN.finditer(text) if not m[0].startswith("#"))


def atomic_write(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
            name = Path(stream.name)
            stream.write(content if isinstance(content, bytes) else content.encode("utf-8"))
        name.replace(path)
    finally:
        if name is not None and name.exists():
            name.unlink()


def definition_records(root, relative, *, unlocks_only=False):
    directory = root / relative
    if not directory.is_dir():
        raise ValueError(f"Missing upstream directory: {directory}")
    result = {}
    for path in sorted(directory.glob("*.txt")):
        if path.name.lower() == "readme.txt":
            continue
        for key, body in production.script_blocks(path.read_text(encoding="utf-8-sig")):
            if unlocks_only and not re.search(r"\bunlock_(building|production_method)\s*=", body):
                continue
            result[key] = {"source": path.relative_to(root).as_posix(),
                           "body": normalized_script(body)}
    if not result:
        raise ValueError(f"No definitions extracted: {directory}")
    return result


def watched_files(root, patterns):
    result = {}
    for pattern in patterns:
        if Path(pattern).is_absolute() or ".." in Path(pattern).parts:
            raise ValueError(f"Watch patterns must stay within the upstream root: {pattern}")
        for path in sorted(root.glob(pattern)):
            if path.is_file() and path.name.lower() != "readme.txt":
                result[path.relative_to(root).as_posix()] = normalized_script(
                    path.read_text(encoding="utf-8-sig"))
    return result


def upstream_identity(game_root, cmf_root, version):
    """Only retain public build identity, never Steam account/installation data."""
    manifest = game_root.parent.parent / "appmanifest_3450310.acf"
    steam = {}
    if manifest.is_file():
        text = manifest.read_text(encoding="utf-8-sig")
        install = re.search(r'"installdir"\s+"([^"]+)"', text)
        if install and install[1] == game_root.name:
            for field in ("buildid", "BetaKey"):
                match = re.search(r'"' + field + r'"\s+"([^"]+)"', text)
                if match:
                    steam[field] = match[1]
    metadata = read_json(cmf_root / ".metadata/metadata.json")
    if metadata.get("id") != "community_mod_framework":
        raise ValueError("--cmf-root is not Community Mod Framework")
    return {"game_version_label": version, "game_version_source": "explicit_label",
            "steam": steam, "cmf": {key: metadata.get(key) for key in
            ("id", "version", "supported_game_version", "cmf_last_updated_game_version")}}


def collect_snapshot(game_root, cmf_root, version, config):
    common = "game/in_game/common/"
    buildings = definition_records(game_root, common + "building_types")
    goods = definition_records(game_root, common + "goods")
    methods = definition_records(game_root, common + "production_methods")
    unlocks = definition_records(game_root, common + "advances", unlocks_only=True)
    catalog = cb.build_catalog_payload(game_root, {"buildings": []})
    typed_catalog = BuildingCatalog.from_mapping(catalog)
    recipes = production.extract_production_models(game_root, typed_catalog)
    demands = gd.extract_supported_construction_demands(game_root, typed_catalog)
    workforce = gd.extract_workforce_model(game_root, typed_catalog)
    diagnostics = []
    for row in catalog["buildings"]:
        key = row["id"]
        block = gd.parse_paradox_script(buildings[key]["body"])
        if gd._first_scalar(block, "employment_size") is not None and key not in workforce.buildings:
            diagnostics.append(f"Unresolved workforce: {key}")
        if gd._first_scalar(block, "construction_demand") is not None and key not in demands:
            diagnostics.append(f"Unresolved construction demand: {key}")
    mechanics = {}
    for name, spec in config["mechanic_sources"].items():
        files = watched_files(game_root, spec["patterns"])
        if not files:
            diagnostics.append(f"No files matched mechanic watch: {name}")
        mechanics[name] = files
    cmf_files = watched_files(cmf_root, config["cmf_patterns"])
    if not cmf_files:
        diagnostics.append("No CMF source files matched")
    cmf_text = "\n".join(cmf_files.values())
    for symbol in config["cmf_required_symbols"]:
        if not re.search(r"\b" + re.escape(symbol) + r"\s*=\s*\{", cmf_text):
            diagnostics.append(f"Missing CMF definition: {symbol}")
    data = {
        "catalog": catalog, "raw_goods": list(rgo_automation.extract_raw_goods(game_root)),
        "production": json.loads(production.production_models_as_json(recipes)),
        "construction": json.loads(gd.construction_demands_as_json(demands)),
        "upgrades": json.loads(gd.building_upgrades_as_json(gd.extract_building_upgrades(game_root, typed_catalog))),
        "workforce": json.loads(gd.workforce_model_as_json(workforce)),
        "rgo_costs": gd.extract_rgo_base_costs(game_root), "straits": extract_straits(game_root),
        "industries": extract_industries(game_root),
        "unlock_ages": cb.extract_building_unlock_ages(game_root),
        "building_definitions": buildings, "goods_definitions": goods,
        "method_definitions": methods, "unlock_definitions": unlocks,
        "mechanics": mechanics, "cmf_files": cmf_files,
    }
    return {"schema_version": SCHEMA, "extractor_version": EXTRACTOR,
            "identity": upstream_identity(game_root, cmf_root, version),
            "data": data, "diagnostics": diagnostics}


def load_baseline(path):
    if not path.exists():
        return None
    value = read_json(path)
    if value.get("schema_version") != SCHEMA or value.get("extractor_version") != EXTRACTOR:
        raise ValueError("Baseline schema/extractor differs; migrate or choose a separate baseline; do not silently replace it")
    if not isinstance(value.get("data"), dict) or not isinstance(value.get("identity"), dict):
        raise ValueError("Invalid baseline: missing data or identity")
    return value


def rows(data, category):
    # New monitored datasets have no predecessor in older observations.
    if category not in data:
        return {}
    value = data[category]
    if category == "catalog":
        return {row["id"]: row for row in value["buildings"]}
    if category in {"production", "construction", "workforce"}:
        result = {row["building_id"]: row for row in value["buildings"]}
        result["$model"] = {key: item for key, item in value.items() if key != "buildings"}
        return result
    if category == "upgrades":
        return value["buildings"]
    if category == "raw_goods":
        return {key: True for key in value}
    if category == "mechanics":
        return {f"{group}/{path}": body for group, files in value.items() for path, body in files.items()}
    return value


def value_changes(before, after, prefix=""):
    if isinstance(before, dict) and isinstance(after, dict):
        result = []
        for key in sorted(set(before) | set(after)):
            name = f"{prefix}.{key}" if prefix else key
            if key not in before or key not in after:
                result.append({"field": name, "before": before.get(key), "after": after.get(key)})
            else:
                result.extend(value_changes(before[key], after[key], name))
        return result
    return [] if before == after else [{"field": prefix or "$", "before": before, "after": after}]


def snapshot_diff(before, after):
    if before is None:
        return {}  # Absence of history is not evidence that everything is new.
    changes = {}
    for category in after["data"]:
        old, new = rows(before["data"], category), rows(after["data"], category)
        changed = {}
        for key in sorted(old.keys() & new.keys()):
            fields = value_changes(old[key], new[key])
            if fields:
                changed[key] = fields
        added = {key: new[key] for key in sorted(new.keys() - old.keys())}
        removed = {key: old[key] for key in sorted(old.keys() - new.keys())}
        if added or removed or changed:
            definition_kind = {"raw_goods": "goods_definitions", "unlock_ages": "building_definitions"}.get(category)
            if category in {"catalog", "production", "construction", "workforce", "upgrades"}:
                definition_kind = "building_definitions"
            if category.endswith("_definitions"):
                definition_kind = category
            sources = {}
            for key in sorted(set(added) | set(removed) | set(changed)):
                if definition_kind:
                    sources[key] = {
                        "before": before["data"][definition_kind].get(key, {}).get("source"),
                        "after": after["data"][definition_kind].get(key, {}).get("source")}
            changes[category] = {"added": added, "removed": removed, "changed": changed,
                                 "sources": sources,
                                 "handling": "manual_review" if category in {
                                     "building_definitions", "method_definitions", "goods_definitions",
                                     "unlock_definitions", "mechanics", "cmf_files", "rgo_costs"
                                 } else "data_sync_and_policy_review"}
    return changes


def policy_issues(snapshot, baseline, config, repo=ROOT):
    """Cross-check policy references and preserve unresolved work across baselines."""
    data = snapshot["data"]
    building_ids = set(rows(data, "catalog"))
    goods = set(data["goods_definitions"])
    rules = read_json(repo / "policies/automation_rules.json")
    priorities = read_json(repo / "policies/video_building_priorities.json")
    templates = read_json(repo / "policies/templates.json")["policies"]
    issues = []

    def issue(kind, subject, detail):
        issues.append({"kind": kind, "subject": subject, "detail": detail})

    for template in templates:
        for field in ("allowed_buildings", "banned_buildings"):
            for key in template[field]:
                if key not in building_ids:
                    issue("stale_reference", template["id"], f"{field}: {key}")
        for key in template["priority_goods"]:
            if key not in goods:
                issue("stale_reference", template["id"], f"priority_goods: {key}")
    for group, members in rules["goods_groups"].items():
        for key in members:
            if key not in goods:
                issue("stale_reference", f"goods_groups.{group}", key)
    for group, members in rules.get("building_groups", {}).items():
        for key in members:
            if key not in building_ids:
                issue("stale_reference", f"building_groups.{group}", key)
    # Historical predecessors can be outside the manageable set; explicit scores
    # are still meaningful while their native definition exists.
    for field, values in priorities.items():
        if isinstance(values, dict):
            for key in values:
                if key not in data["building_definitions"]:
                    issue("stale_reference", field, key)
    old_ids = set(rows(baseline["data"], "catalog")) if baseline else set()
    reviewed = config.get("building_decisions", {})
    for key in sorted(building_ids - old_ids):
        if key not in reviewed and baseline is not None:
            issue("decision_needed", key, "Set/review general priority, role and flavor membership; do not infer from the display name")
    old_goods = set(baseline["data"]["goods_definitions"]) if baseline else goods
    grouped = {key for members in rules["goods_groups"].values() for key in members}
    for key in sorted(goods - old_goods):
        if key not in grouped and key not in config.get("generic_goods", {}):
            issue("decision_needed", key, "Assign goods group or record deliberate generic treatment")
    for key, decision in reviewed.items():
        if decision["status"] == "pending":
            issue("decision_needed", key, decision["reason"])
        if decision["status"] == "excluded" and key in building_ids:
            issue("exclusion_changed", key, decision["reason"])
        if "same_priority_as" in decision and key in building_ids:
            scores = rules["building_priorities"]["overrides"]
            other = decision["same_priority_as"]
            if scores.get(key) != scores.get(other):
                issue("decision_drift", key, f"Priority should match {other}; {decision['reason']}")
        if baseline and key in data["building_definitions"]:
            old = baseline["data"]["building_definitions"].get(key, {}).get("body")
            if old is not None and old != data["building_definitions"][key]["body"]:
                issue("decision_review", key, decision["reason"])
    for task in config.get("open_adaptations", []):
        issue("functional_adaptation", task["id"], task["reason"])
    return issues


def data_drift(snapshot, game_root, repo=ROOT):
    catalog_text, rules_text, _ = cb.generated_catalog_and_rules(game_root)
    expected = dict(snapshot["data"])
    expected["catalog"] = json.loads(catalog_text)  # preserve reviewed aliases
    stale = []
    for category, target in DATA_TARGETS.items():
        path = repo / target
        if not path.is_file() or read_json(path) != expected[category]:
            stale.append(target)
    if read_json(repo / "policies/automation_rules.json") != json.loads(rules_text):
        stale.append("policies/automation_rules.json")
    costs = set(snapshot["data"]["rgo_costs"].values())
    mirror = read_json(repo / "policies/automation_rules.json")["thresholds"]["rgo_budget_cost"]
    if costs != {mirror}:
        stale.append("policies/automation_rules.json:thresholds.rgo_budget_cost (manual review)")
    return stale


@contextmanager
def candidate_raw_goods(goods):
    """Render new goods without writing the active snapshot before validation.

All existing raw_goods imports read the module's path at call time. This CLI
is single-threaded; restore the path on both success and failure.
"""
    original = rgo_automation.RAW_GOODS_FILE
    with tempfile.TemporaryDirectory(prefix="eu5ab-update-") as directory:
        path = Path(directory) / "raw_goods.json"
        path.write_text(json_text(goods), encoding="utf-8")
        rgo_automation.RAW_GOODS_FILE = path
        try:
            yield
        finally:
            rgo_automation.RAW_GOODS_FILE = original


def render_candidate(game_root, snapshot):
    from . import generator as gen
    from .rules import AutomationRules

    catalog_text, rules_text, _ = cb.generated_catalog_and_rules(game_root)
    with candidate_raw_goods(snapshot["data"]["raw_goods"]):
        files = gen.generated_files(
            gen.load_policies(gen.POLICY_FILE),
            BuildingCatalog.from_mapping(json.loads(catalog_text)),
            AutomationRules.from_mapping(json.loads(rules_text)), game_root=game_root)
    for path, content in files.items():
        if path.suffix in {".txt", ".gui"} and not gen._balanced_script(content):
            raise ValueError(f"Unbalanced generated script: {path}")
    files[cb.CATALOG_FILE] = catalog_text
    files[cb.RULES_FILE] = rules_text
    files[cb.RAW_GOODS_FILE] = json.dumps(snapshot["data"]["raw_goods"], indent=2) + "\n"
    return files


def stale_generated(files):
    return [str(path.relative_to(ROOT)).replace("\\", "/") for path, content in files.items()
            if not path.exists() or path.read_text(encoding="utf-8-sig") != content.lstrip("\ufeff").replace("\r\n", "\n")]


def apply_files(files):
    """Render every byte before mutation, write only differences, roll back errors."""
    from .generator import _write_generated_file

    prepared, originals, changed = {}, {}, []
    with tempfile.TemporaryDirectory(prefix="eu5ab-sync-") as directory:
        for path, text in files.items():
            relative = path.resolve().relative_to(ROOT.resolve())
            staged = Path(directory) / relative
            staged.parent.mkdir(parents=True, exist_ok=True)
            if path in {cb.CATALOG_FILE, cb.RULES_FILE, cb.RAW_GOODS_FILE}:
                staged.write_text(text, encoding="utf-8")
            else:
                _write_generated_file(staged, text)
            content = staged.read_bytes()
            previous = path.read_bytes() if path.exists() else None
            # Do not rewrite files merely for newline/BOM normalization.
            if previous is not None and previous.decode("utf-8-sig").replace("\r\n", "\n") == text.lstrip("\ufeff").replace("\r\n", "\n"):
                continue
            prepared[path], originals[path] = content, previous
        try:
            for path, content in prepared.items():
                atomic_write(path, content)
                changed.append(path)
        except OSError:
            for path in reversed(changed):
                if originals[path] is None:
                    path.unlink()
                else:
                    atomic_write(path, originals[path])
            raise
    return [path.relative_to(ROOT).as_posix() for path in changed]


def accept_baseline(snapshot, path):
    """Baseline is an observation, never a claim of runtime compatibility."""
    previous = load_baseline(path)
    if previous == snapshot:
        return False
    if previous is not None:
        archive = path.parent / "history" / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + ".json")
        atomic_write(archive, json_text(previous))
    atomic_write(path, json_text(snapshot))
    return True


def report_markdown(report):
    lines = ["# EU5 上游更新审计", "", f"当前来源：`{json.dumps(report['identity'], ensure_ascii=False)}`", "",
             "此报告区分数据同步与功能兼容；未覆盖的引擎行为仍须结合更新日志和游戏内验证。", ""]
    if report["baseline_identity"] is None:
        lines += ["**尚无历史基线：本次是首次采集，不能据此声称没有上游变化。**", ""]
    else:
        lines += [f"比较基线：`{json.dumps(report['baseline_identity'], ensure_ascii=False)}`", ""]
    lines += ["| 数据 | 新增 | 移出 | 修改 |", "|---|---:|---:|---:|"]
    for category, change in report["changes"].items():
        lines.append(f"| {category} | {len(change['added'])} | {len(change['removed'])} | {len(change['changed'])} |")
    lines += ["", "## 待办与覆盖范围", ""]
    for item in report["issues"]:
        lines.append(f"- **{item['kind']}** `{item['subject']}`：{item['detail']}")
    for item in report["diagnostics"]:
        lines.append(f"- **提取失败或覆盖缺口**：{item}")
    for path in report["stale_files"]:
        lines.append(f"- **数据或生成文件过期**：`{path}`")
    for name, spec in report["coverage"].items():
        lines.append(f"- 监测 `{name}` → {', '.join(spec['consumers'])}；{spec['note']}")
    lines += ["", "## 变化明细", "", "完整旧值与新值保存在同名 JSON 报告；候选原始定义见 candidate.json。", ""]
    for category, change in report["changes"].items():
        lines += [f"### {category}", "", f"处理类别：`{change['handling']}`", ""]
        for action in ("added", "removed"):
            if change[action]:
                lines.append(f"- {action}：" + ", ".join(f"`{key}`" for key in change[action]))
        for key, fields in change["changed"].items():
            lines.append(f"- `{key}`")
            source = change["sources"].get(key)
            if source:
                lines.append(f"  - 来源：`{source['before']}` → `{source['after']}`")
            for field in fields:
                def brief(value):
                    text = json.dumps(value, ensure_ascii=False)
                    return (text[:237] + "…") if len(text) > 240 else text
                lines.append(f"  - `{field['field']}`：`{brief(field['before'])}` → `{brief(field['after'])}`")
        lines.append("")
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("audit", "sync", "check", "baseline"))
    parser.add_argument("--game-root", type=Path)
    parser.add_argument("--cmf-root", type=Path, default=os.environ.get("EU5_CMF_ROOT"))
    parser.add_argument("--game-version", required=True, help="Explicit observed version label; Steam build/branch are detected separately")
    parser.add_argument("--baseline", type=Path, default=STATE / "baseline.json")
    parser.add_argument("--output", type=Path, default=STATE / "latest")
    parser.add_argument("--config", type=Path, default=CONFIG)
    args = parser.parse_args(argv)
    try:
        game_root = require_game_root(args.game_root)
        if args.cmf_root is None:
            raise ValueError("Pass --cmf-root or set EU5_CMF_ROOT; CMF checks cannot be silently skipped")
        config = read_json(args.config)
        if config.get("schema_version") != 1:
            raise ValueError("Unsupported game_update_rules schema")
        baseline = load_baseline(args.baseline)
        candidate = collect_snapshot(game_root, Path(args.cmf_root), args.game_version, config)
        changes = snapshot_diff(baseline, candidate)
        issues = policy_issues(candidate, baseline, config)
        stale = data_drift(candidate, game_root)
        report = {"identity": candidate["identity"],
                  "baseline_identity": baseline["identity"] if baseline else None,
                  "changes": changes, "issues": issues, "diagnostics": candidate["diagnostics"],
                  "stale_files": stale, "coverage": config["mechanic_sources"]}
        args.output.mkdir(parents=True, exist_ok=True)
        atomic_write(args.output / "candidate.json", json_text(candidate))
        # Always leave an audit before an attempted mutation or failed render.
        atomic_write(args.output / "report.json", json_text(report))
        atomic_write(args.output / "report.md", report_markdown(report))
        if args.command in {"sync", "check", "baseline"}:
            if candidate["diagnostics"]:
                raise ValueError("Extraction/coverage diagnostics need resolution; see report.md")
            files = render_candidate(game_root, candidate)
            report["stale_files"] = sorted(set(stale + stale_generated(files)))
            if args.command == "sync":
                if any(item["kind"] in {"stale_reference", "exclusion_changed"} for item in issues):
                    raise ValueError("Resolve stale policy references/exclusion changes before sync; see report.md")
                report["written_files"] = apply_files(files)
                print(f"Synchronized {len(report['written_files'])} files; baseline unchanged.")
            elif args.command == "baseline":
                if report["stale_files"]:
                    raise ValueError("Data/generated files are stale; sync before recording a baseline")
                # Unclassified additions must not disappear when the baseline moves.
                untracked = [item for item in issues if item["kind"] == "decision_needed"
                             and item["subject"] not in config.get("building_decisions", {})]
                if untracked:
                    raise ValueError("Record new decisions (pending is allowed) before advancing baseline")
                accept_baseline(candidate, args.baseline)
                print("Recorded observation baseline; open adaptations remain in the report.")
            atomic_write(args.output / "report.json", json_text(report))
            atomic_write(args.output / "report.md", report_markdown(report))
        print(f"Report: {args.output / 'report.md'}")
        print(f"Changed categories: {len(changes)}; policy/functional issues: {len(issues)}; extraction diagnostics: {len(candidate['diagnostics'])}")
        if args.command == "check":
            return int(baseline is None or bool(changes or issues or report["stale_files"])
                       or baseline["identity"] != candidate["identity"])
        return 0
    except (OSError, ValueError, KeyError) as error:
        print(f"Update tool error: {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
