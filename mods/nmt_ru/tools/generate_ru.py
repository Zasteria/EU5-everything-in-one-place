#!/usr/bin/env python3
"""Build the Russian localization for EU5 National Mission Trees.

The base mod ships **English and Japanese only**, and the game loads the
selected language's folder and nothing else -- there is no fallback to English
(``docs/pitfalls/localization.md``).  So a Russian client that only got the
translated files would render every untranslated key blank.  This tool
therefore emits a Russian file for *every* base file: a key with a hand
translation in ``translations/`` gets it, a key without one keeps the English
value verbatim, which is what the player would have seen anyway.

Usage:

    python3 mods/nmt_ru/tools/generate_ru.py [<path to the base mod>]
    python3 mods/nmt_ru/tools/generate_ru.py --accept [<path to the base mod>]

One source file per base file: ``translations/<stem>.yml`` covers the base
mod's ``<stem>_l_english.yml``, wherever in the two trees that file lives.  The
base mod keeps near-identical copies under ``main_menu/`` and ``in_game/``; both
are emitted from the same source, so a translation is written once.

When the base mod updates, the English behind a translated key can be rewritten
without any visible sign -- the Russian silently goes on saying what the mod no
longer says.  Every translated English value is therefore fingerprinted in
``english_generated_fingerprints.txt``, and a run after a base-mod update names
the keys whose English moved.  Fix the translation, then record the new English
with ``--accept``.

It refuses to write a file that would show up wrong in game:

* a key the base mod does not define is invented and cannot render;
* the markup of a value -- ``[data functions]`` and ``[concept|e]`` links,
  ``$key$`` references, ``@texticons!``, ``#format`` codes, ``\\n`` -- is read by
  the engine rather than displayed and has to survive translation unchanged;
* a stray double quote truncates the line, and a square bracket added to plain
  text renders as ``ERROR:``;
* a character belonging to neither Russian nor the Latin the mod's proper names
  need has no business in the file -- the base mod is Japanese, and a stray
  ideograph would reach the player unnoticed;
* a Latin letter glued to a Cyrillic one inside a single word -- ``territoryов``
  -- is an English word left mid-sentence and declined as if it were Russian.
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from hashlib import sha1
from pathlib import Path

HERE = Path(__file__).resolve().parent
MOD = HERE.parent
REPO = MOD.parent.parent
sys.path.insert(0, str(REPO / "tools"))

import refs  # noqa: E402  the reference tree, resolved by mod id

DEFAULT_BASE = refs.known("national_mission_trees")
TREES = ("main_menu", "in_game")
SOURCES = MOD / "translations"
FINGERPRINTS = MOD / "english_generated_fingerprints.txt"
KEPT = MOD / "translations" / "kept_as_is.txt"

KEY_LINE = re.compile(r'^\s*([\w.\-]+):\s*\d*\s*"(.*)"\s*$')
OPEN_LINE = re.compile(r'^\s*([\w.\-]+):\s*\d*\s*"(.*)$')
MARKUP = re.compile(r"\[[^\]]*\]|\$[^$]*\$|§.|@\w+!|#[A-Za-z!]+|\\n")
CYRILLIC = re.compile(r"[Ѐ-ӿ]")
LATIN = re.compile(r"[A-Za-z]")
ALLOWED = re.compile(
    r"[Ѐ-ӿA-Za-z0-9\s"
    r"""!"#$%&'()*+,\-./:;<=>?@\[\]^_`{|}~"""
    r"«»—–…„“”‘’°№§±×÷]"
)
MIXED_WORD = re.compile(r"[Ѐ-ӿ][A-Za-z]|[A-Za-z][Ѐ-ӿ]")

# English function words: one of these standing in a Russian sentence that the
# English value does not itself contain is a line left half translated.
FUNCTION_WORDS = {
    "the", "and", "of", "to", "in", "for", "with", "from", "that", "this",
    "will", "have", "has", "been", "are", "was", "were", "their", "its",
    "into", "over", "under", "after", "before", "when", "while", "would",
    "could", "should", "than", "then", "but", "not", "all", "any", "which",
}


def read_yml(path: Path) -> list[tuple[str, str]]:
    """Parse a Clausewitz localization file into key/value pairs, in file order.

    Pairs rather than a dict: the base mod defines 145 keys twice per tree,
    usually an event's old wording and its rewrite, and which of the two the
    game shows is the game's business.  Keeping both, in order, means the
    Russian file answers that question exactly as the English one does.

    A value can run over several lines with real newlines inside the quotes --
    the mod writes its event bodies that way -- so a value ends at the line
    whose last character is the closing quote, not at the first line break.
    """
    pairs: list[tuple[str, str]] = []
    key: str | None = None
    parts: list[str] = []
    for number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if key is not None:
            if line.rstrip().endswith('"'):
                parts.append(line.rstrip()[:-1])
                pairs.append((key, "\n".join(parts)))
                key, parts = None, []
            else:
                parts.append(line)
            continue
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or re.match(r"^l_\w+:$", stripped):
            continue
        match = KEY_LINE.match(line)
        if match:
            pairs.append((match.group(1), match.group(2)))
            continue
        opening = OPEN_LINE.match(line)
        if not opening:
            raise SystemExit(f"{path}:{number}: cannot parse: {line!r}")
        key, parts = opening.group(1), [opening.group(2)]
    if key is not None:
        raise SystemExit(f"{path}: the value of {key} is never closed")
    return pairs


def by_key(pairs: list[tuple[str, str]]) -> dict[str, list[str]]:
    """The values of each key, in the order the file gives them."""
    grouped: dict[str, list[str]] = {}
    for key, value in pairs:
        grouped.setdefault(key, []).append(value)
    return grouped


def write_yml(path: Path, pairs: list[tuple[str, str]]) -> None:
    """Write a localization file the way the game wants it: BOM, one space."""
    body = ["l_russian:"]
    body += [f' {key}: "{value}"' for key, value in pairs]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(body) + "\n", encoding="utf-8-sig")


def prose(value: str) -> str:
    """The part of a value a player actually reads."""
    return MARKUP.sub("", value).strip()


def markup(value: str) -> Counter:
    """Everything in a value the engine reads rather than draws."""
    return Counter(MARKUP.findall(value) + ["<newline>"] * value.count("\n"))


def read_kept() -> set[str]:
    """Keys deliberately left in the base mod's own words, and why -- one per line.

    A Latin name the mod chose on purpose (``Renovatio Imperii``) is not an
    untranslated line, but it looks exactly like one, so it is named here
    rather than silently allowed.
    """
    if not KEPT.is_file():
        return set()
    kept = set()
    for line in KEPT.read_text(encoding="utf-8").splitlines():
        line = line.split("#")[0].strip()
        if line:
            kept.add(line)
    return kept


def check(stem: str, english: dict[str, list[str]], russian: dict[str, list[str]],
          kept: set[str]) -> list[str]:
    """Everything wrong with one file's translation, as printable lines."""
    problems: list[str] = []

    for key in sorted(k for k in russian if k not in english):
        problems.append(f"{stem}: {key} is not a key of the base mod")

    for key, values in sorted(russian.items()):
        if key not in english:
            continue
        if len(values) > len(english[key]):
            problems.append(
                f"{stem}: {key}: translated {len(values)} times, the base mod defines it "
                f"{len(english[key])}"
            )
        for value, source in zip(values, english[key]):
            where = f"{stem}: {key}"
            if value.count('"') != source.count('"'):
                problems.append(
                    f"{where}: a double quote truncates the line -- the English has "
                    f"{source.count(chr(34))} of them, this has {value.count(chr(34))}"
                )
            if markup(value) != markup(source):
                problems.append(
                    f"{where}: markup changed -- "
                    f"{sorted(markup(source))} became {sorted(markup(value))}"
                )
            stray = sorted({c for c in ALLOWED.sub("", MARKUP.sub("", value))})
            if stray:
                problems.append(f"{where}: characters that belong to no language here: {stray}")
            text = prose(value)
            if MIXED_WORD.search(text):
                problems.append(f"{where}: Latin and Cyrillic glued inside one word")
            if CYRILLIC.search(text):
                left = {w.lower() for w in re.findall(r"[A-Za-z]+", text)}
                came_with = {w.lower() for w in re.findall(r"[A-Za-z]+", prose(source))}
                leftover = sorted((left & FUNCTION_WORDS) - came_with)
                if leftover:
                    problems.append(f"{where}: English left standing: {leftover}")
            elif text and text == prose(source) and key not in kept:
                problems.append(
                    f"{where}: still the English value -- translate it, or name the key "
                    f"in translations/kept_as_is.txt"
                )
    return problems


def fingerprint(value: str) -> str:
    return sha1(value.encode("utf-8")).hexdigest()[:12]


def read_fingerprints() -> dict[str, str]:
    if not FINGERPRINTS.is_file():
        return {}
    recorded: dict[str, str] = {}
    for line in FINGERPRINTS.read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#"):
            key, _, digest = line.partition(" ")
            recorded[key] = digest
    return recorded


def write_fingerprints(recorded: dict[str, str]) -> None:
    body = ["# Written by mods/nmt_ru/tools/generate_ru.py. The English behind",
            "# every translated key, so a base-mod update cannot move it silently."]
    body += [f"{key} {digest}" for key, digest in sorted(recorded.items())]
    FINGERPRINTS.write_text("\n".join(body) + "\n", encoding="utf-8")


def base_files(base: Path) -> dict[str, list[Path]]:
    """Every English file of the base mod, by stem, across both trees."""
    found: dict[str, list[Path]] = {}
    for tree in TREES:
        root = base / tree / "localization" / "english"
        if not root.is_dir():
            raise SystemExit(f"no English localization under {root}")
        for path in sorted(root.rglob("*_l_english.yml")):
            found.setdefault(path.name[: -len("_l_english.yml")], []).append(path)
    return found


def main(argv: list[str]) -> int:
    argv = list(argv)
    accept = "--accept" in argv
    if accept:
        argv.remove("--accept")
    base = Path(argv[1]) if len(argv) > 1 else DEFAULT_BASE

    files = base_files(base)
    sources = {p.stem: p for p in sorted(SOURCES.glob("*.yml"))}
    unknown = sorted(set(sources) - set(files))
    if unknown:
        raise SystemExit(
            "translations/ names files the base mod does not have: " + ", ".join(unknown)
        )

    kept = read_kept()
    recorded = read_fingerprints()
    problems: list[str] = []
    moved: list[str] = []
    fresh: dict[str, str] = {}
    written = translated = total = 0

    for stem, paths in sorted(files.items()):
        russian = by_key(read_yml(sources[stem])) if stem in sources else {}
        english_of_stem: dict[str, list[str]] = {}
        for path in paths:
            pairs = read_yml(path)
            grouped = by_key(pairs)
            for key, values in grouped.items():
                if len(values) > len(english_of_stem.get(key, [])):
                    english_of_stem[key] = values
            seen: Counter = Counter()
            merged: list[tuple[str, str]] = []
            for key, value in pairs:
                spoken = russian.get(key, [])
                index = seen[key]
                seen[key] += 1
                merged.append((key, spoken[index] if index < len(spoken) else value))
                total += 1
                translated += 1 if index < len(spoken) else 0
            target = (
                MOD
                / path.relative_to(base).parent.as_posix().replace("/english", "/russian")
                / path.name.replace("_l_english.yml", "_ru_generated_l_russian.yml")
            )
            write_yml(target, merged)
            written += 1
        if russian:
            problems += check(stem, english_of_stem, russian, kept)
            for key, values in russian.items():
                for index, _ in enumerate(values):
                    if key not in english_of_stem or index >= len(english_of_stem[key]):
                        continue
                    name = key if index == 0 else f"{key}#{index + 1}"
                    digest = fingerprint(english_of_stem[key][index])
                    fresh[name] = digest
                    if name in recorded and recorded[name] != digest:
                        moved.append(name)

    if problems:
        print("\n".join(problems[:40]))
        if len(problems) > 40:
            print(f"... and {len(problems) - 40} more")
        raise SystemExit(f"nothing written: {len(problems)} problems")

    if moved and not accept:
        print("the English behind these keys moved since they were translated:")
        for key in sorted(moved)[:20]:
            print(f"  {key}")
        raise SystemExit(
            "read each one, bring the translation up to date, then rerun with --accept"
        )
    write_fingerprints(fresh)

    covered = translated * 100 / total if total else 0
    print(f"     {written} Russian files written from {len(files)} base files")
    print(f"     {translated} of {total} key slots translated by hand ({covered:.1f}%),"
          " the rest carry the base mod's English")
    print(f"     translated: {', '.join(sorted(sources)) or 'nothing yet'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
