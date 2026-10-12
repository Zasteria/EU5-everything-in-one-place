"""Cross-reference EU5 static warnings with current Mod sources.

Matches literal variable names in supplied logs to source references. Check
runtime initialization and framework-generated names in the running game.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import re


WARNING = re.compile(
    r"(?:Variable|Event target|Flag) '([^']+)' is (used but is never set|set but is never used)"
)
IDENTIFIER = re.compile(r"\b(?:eu5ab\w*|cmm_\w*eu5ab\w*)\b")
OWN_NAME = r"(?:eu5ab\w*|cmm_\w*eu5ab\w*)"
READER = re.compile(
    r"(?:\b(?:var:|local_var:|has_(?:local_)?variable(?:_list|_map)?\s*=\s*|variable\s*=\s*|variable_map\()|(?:GetVariable|HasVariable)\(')(" + OWN_NAME + r")"
)
WRITES = {"set_variable", "set_local_variable", "set_global_variable",
          "add_to_variable_list", "add_to_local_variable_list", "add_to_variable_map"}
READS = {"is_key_in_variable_map", "is_target_in_variable_list",
         "change_variable", "change_local_variable", "change_global_variable"}
CLEANUPS = {"remove_variable", "remove_local_variable", "clear_variable_list",
            "clear_variable_map", "remove_from_variable_map", "remove_list_variable"}
TOKENS = re.compile(r'"(?:\\.|[^"\\])*"|#[^\n]*|[{}=]|[^\s{}=]+')


def script_accesses(text: str):
    """Classify name fields by their actual enclosing operation, across lines.

    A map/list existence check is a read, not an initializer. Mutations of
    numeric variables require existing state and do not prove initialization.
    """
    stack, previous = [], []
    line, offset = 1, 0
    for match in TOKENS.finditer(text):
        line += text.count('\n', offset, match.start())
        offset = match.start()
        token = match[0]
        if token.startswith('#'):
            continue
        if token == '{':
            stack.append(previous[-2] if len(previous) == 2 and previous[-1] == '=' else '')
        elif token == '}':
            if stack:
                stack.pop()
        elif re.fullmatch(OWN_NAME, token) and len(previous) == 2 and previous[-1] == '=':
            key = previous[-2]
            operation = stack[-1] if key == 'name' and stack else key
            if operation in WRITES:
                yield token, 'writers', line
            elif operation in READS:
                yield token, 'readers', line
            elif operation in CLEANUPS:
                yield token, 'cleanup', line
        previous = (previous + [token])[-2:]


def index_sources(root: Path) -> dict[str, dict[str, list[str]]]:
    index = defaultdict(lambda: defaultdict(list))
    for folder in ("in_game", "main_menu"):
        for path in sorted((root / folder).rglob("*")):
            if path.suffix not in (".txt", ".gui", ".yml"):
                continue
            text = path.read_text(encoding="utf-8-sig")
            relative = path.relative_to(root).as_posix()
            if path.suffix == '.txt':
                for name, kind, number in script_accesses(text):
                    reference = f"{relative}:{number}"
                    index[name][kind].append(reference)
                    if kind == 'readers':
                        index[name]['script_readers'].append(reference)
            for number, line in enumerate(text.splitlines(), 1):
                if line.lstrip().startswith("#"):
                    continue
                reference = f"{relative}:{number}"
                for name in set(IDENTIFIER.findall(line)):
                    index[name]["references"].append(reference)
                for name in READER.findall(line):
                    index[name]["readers"].append(reference)
                    if path.suffix == ".txt":
                        index[name]["script_readers"].append(reference)
    return dict(index)


def classify(name: str, warning: str, evidence: dict) -> str:
    if not re.fullmatch(OWN_NAME, name):
        return "framework_or_other_mod"
    # CMM expands and consumes these through list-setting macros.
    if re.fullmatch(r"eu5ab_regional_development__candidate_priority_i\d+_f\d+", name):
        return "framework_generated_list_field"
    if not evidence.get("references"):
        return "absent_from_current_source"
    if warning == "used but is never set":
        if evidence.get("writers"):
            return "writer_present_runtime_not_verified"
        if evidence.get("readers"):
            return "unresolved_read_without_literal_writer"
        if evidence.get("cleanup"):
            return "legacy_cleanup_without_reader"
    else:
        if evidence.get("script_readers"):
            return "script_consumer_present_runtime_not_verified"
        if evidence.get("readers"):
            return "consumer_present_runtime_not_verified"
        if not evidence.get("writers"):
            return "write_removed_from_current_source"
    return "requires_manual_review"


def audit(root: Path, logs: list[Path]) -> dict:
    index = index_sources(root)
    counts = Counter()
    locations = defaultdict(list)
    for path in sorted(logs):
        for number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
            match = WARNING.search(line)
            if not match:
                continue
            name, warning = match.groups()
            if "eu5ab" not in name and "Event target" not in line:
                continue
            key = (name, warning)
            counts[key] += 1
            locations[key].append(f"{path.name}:{number}")
    rows = []
    for (name, warning), count in sorted(counts.items()):
        evidence = index.get(name, {})
        rows.append(dict(
            name=name, warning=warning, occurrences=count,
            classification=classify(name, warning, evidence),
            log_references=locations[name, warning],
            source_evidence={key: value[:4] for key, value in evidence.items()},
        ))
    return {
        "limitation": "Matches supplied logs to literal source names. Check runtime initialization against logs from the same mod revision.",
        "logs": [str(p) for p in sorted(logs)],
        "unique_warning_count": len(rows),
        "classifications": dict(Counter(row["classification"] for row in rows)),
        "warnings": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log_directory", type=Path)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    logs = list(args.log_directory.glob("error*.log"))
    if not logs:
        parser.error("No error*.log files found")
    report = audit(args.root, logs)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["classifications"], ensure_ascii=False, indent=2))
    if any(row["classification"] in ("unresolved_read_without_literal_writer", "requires_manual_review")
           for row in report["warnings"]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
