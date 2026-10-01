#!/usr/bin/env python3
"""Russian for the keys the game ships without it.

    python3 mods/ru_loc_fix/tools/translate.py            what is left to translate
    python3 mods/ru_loc_fix/tools/translate.py --todo DIR  the same, as one JSON per game file
    python3 mods/ru_loc_fix/tools/translate.py --check FILE...  check translation files quickly

The 2026-10-01 beta rewrote a good part of the English and left the Russian
behind. The game loads the selected language and nothing else, so on a Russian
client that shows three ways:

* **missing** — English defines the key, Russian does not: the key itself is
  printed on screen (793 keys on 10-01);
* **english** — the Russian file holds the English text (1 339 new on 10-01);
* **stale** — English moved to other markup (a removed event's title, a
  function the engine no longer has) and the Russian still prints the old one.

`translations/<stem>.yml` holds the Russian, one file per game file
(`religious_orders.yml` for `religious_orders_l_english.yml`).
`generate.py` ships them; a key goes out only while one of the three reasons
above still holds — once Paradox translates it, ours is reported and dropped
rather than left shadowing theirs.

Everything a translation has to survive before it is written:

* the key is the game's — English defines it;
* the markup — `[data functions]`, `$references$`, `@icons!`, `#formats#!`,
  `\\n` — comes through as English has it. The one liberty is the game's own
  Russian habit of declining a concept: `[markets|e]` may become
  `[Concept('markets', 'рынками')|e]`;
* no stray double quote, no square bracket in plain text, no character that is
  neither Russian nor the Latin a name needs, no English function word the
  English value does not itself contain, no Latin letter glued to a Cyrillic
  one inside a word (`territoryов`) — each of these reached a screen once in
  `nd_ru` before a rule stopped it;
* the hard rules of `locscan`;
* and the English it was made from has not moved since:
  `translations/english_fingerprints.txt` names a key whose English Paradox
  rewrote after it was translated. Bring the Russian up to date, then
  `generate.py --accept`.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from hashlib import sha1
from pathlib import Path

MOD = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(MOD / "tools"))
import locscan  # noqa: E402

SOURCE = MOD / "translations"
FINGERPRINTS = SOURCE / "english_fingerprints.txt"
OUT = MOD / "main_menu/localization/russian/bag_ruloc_translated_l_russian.yml"
OUT_LOADING = MOD / "loading_screen/localization/russian/bag_ruloc_translated_loading_l_russian.yml"

MARKUP = re.compile(r"\[(?:[^\[\]]|\[[^\[\]]*\])*\]|\$[^$\s]*\$|@\w+!|#[A-Za-z_]+|#!|\\n")
CONCEPT = re.compile(r"\[Concept\('([A-Za-z0-9_]+)',\s*'[^']*'\)(\|[A-Za-z]+)?\]")
CYRILLIC = re.compile(r"[Ѐ-ӿ]")
MIXED_SCRIPT = re.compile(r"[Ѐ-ӿ][A-Za-z]|[A-Za-z][Ѐ-ӿ]")
ENGLISH_WORDS = {
    "the", "and", "of", "though", "with", "that", "which", "from", "into",
    "their", "its", "was", "were", "have", "has", "been", "this", "there",
    "when", "while", "would", "could", "should", "than", "then", "but",
}
ALLOWED = "«»—–…‘’“„ʿʽ́·•"


# The game's own way to agree a Russian verb with a character's sex. English
# has no need of it, so a translation may add one — on a scope the English
# value already names.
SELECT = re.compile(r"\[Select_CString\(\s*([A-Za-z_]+)[A-Za-z_.()']*\.IsFemale\s*,"
                    r"\s*'[^'\[\]]*'\s*,\s*'[^'\[\]]*'\s*\)\]")


def markup(value: str) -> Counter:
    """What the engine reads in a value, with a declined concept counted as the plain one."""
    value = CONCEPT.sub(lambda m: "[%s%s]" % (m.group(1), m.group(2) or ""), value)
    return Counter(MARKUP.findall(value))


def prose(value: str) -> str:
    return MARKUP.sub(" ", value)


def has_prose(value: str) -> bool:
    """Words a player reads, not an identifier: two words with a lowercase letter."""
    return len(re.findall(r"\b[A-Za-z\u0400-\u04FF]*[a-z\u0430-\u044f][A-Za-z\u0400-\u04FF]+\b",
                          prose(value))) >= 2


# Files whose Latin is a proper name rather than English left untranslated: a
# Maghrebi town or a Castilian king read the same in a Russian game, and the QA
# and mod-upload strings are not the player's.
NAMES = re.compile(r"^(location_names|character_names|dynasty_names|qa_debug|caesar_tools)")


def hard_flagged(russian: dict, english: dict) -> set[str]:
    """Keys whose Russian markup a hard rule of locscan says is broken."""
    return {f.key for f in locscan.scan(russian, english, locscan.HARD)}


def reason(key: str, russian: dict, english: dict, flagged: set[str]) -> str | None:
    """Why the game's Russian for `key` needs ours, or None once it does not."""
    if key not in russian:
        return "missing"
    theirs = russian[key].value
    stem = english[key].path.name
    if (has_prose(english[key].value) and not CYRILLIC.search(theirs)
            and not NAMES.match(stem)):
        return "english"
    if key in flagged:
        return "stale"
    return None


def fingerprint(value: str) -> str:
    return sha1(value.encode("utf-8")).hexdigest()[:12]


def read_fingerprints() -> dict[str, str]:
    recorded: dict[str, str] = {}
    if FINGERPRINTS.exists():
        for line in FINGERPRINTS.read_text(encoding="utf-8").splitlines():
            if line and not line.startswith("#"):
                digest, _, key = line.partition("\t")
                recorded[key] = digest
    return recorded


def write_fingerprints(recorded: dict[str, str]) -> None:
    body = ["# Written by mods/ru_loc_fix/tools/translate.py — do not edit by hand.",
            "# <digest of the English value>\t<key>, for every translated key."]
    body += ["%s\t%s" % (recorded[key], key) for key in sorted(recorded)]
    FINGERPRINTS.write_text("\n".join(body) + "\n", encoding="utf-8")


def read_sources() -> dict[str, tuple[str, Path, int]]:
    values: dict[str, tuple[str, Path, int]] = {}
    for path in sorted(SOURCE.glob("*.yml")):
        for number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or re.match(r"^l_\w+:$", stripped):
                continue
            match = locscan.KEY_LINE.match(line)
            if not match:
                raise SystemExit("%s:%d: cannot parse: %r" % (path.name, number, line))
            key, value = match.groups()
            if key in values:
                raise SystemExit("%s:%d: %s is already translated in %s"
                                 % (path.name, number, key, values[key][1].name))
            values[key] = (value, path, number)
    return values


def check(key: str, value: str, english: str) -> list[str]:
    problems: list[str] = []
    roots = set(re.findall(r"\[([A-Za-z_]+)[.(]", english))
    value_bare = SELECT.sub(lambda m: "" if m.group(1) in roots else m.group(0), value)
    want, got = markup(english), markup(value_bare)
    for token in sorted((want - got).keys()):
        problems.append("markup %r lost" % token)
    for token in sorted((got - want).keys()):
        problems.append("markup %r invented" % token)
    if re.search(r'(?<!\\)"', value):
        problems.append("a double quote would truncate the line")
    text = prose(value_bare)
    if "[" in text or "]" in text:
        problems.append("a square bracket in plain text renders as ERROR:")
    if not value.strip() and english.strip():
        problems.append("empty value")
    mixed = MIXED_SCRIPT.search(text)
    if mixed:
        problems.append("Latin and Cyrillic inside one word (%r)" % mixed.group(0))
    ours = {w.lower() for w in re.findall(r"[A-Za-z]+", text)}
    theirs = {w.lower() for w in re.findall(r"[A-Za-z]+", english)}
    for word in sorted(ours & ENGLISH_WORDS - theirs):
        problems.append("English word %r left in" % word)
    if has_prose(english) and not CYRILLIC.search(text) and text.strip() == prose(english).strip():
        problems.append("still the English text")
    for char in set(value):
        point = ord(char)
        if not (0x0400 <= point <= 0x04FF or 0x20 <= point <= 0x7E
                or 0x00C0 <= point <= 0x024F or char in ALLOWED):
            problems.append("stray character %r (U+%04X)" % (char, point))
    return ["%s: %s" % (key, p) for p in problems]


def build(russian: dict, english: dict, accept: bool = False, flagged: set[str] | None = None
          ) -> tuple[dict[str, str], set[str], list[str]]:
    """(key -> Russian to ship, the keys among them from the loading screen, complaints)."""
    complaints: list[str] = []
    shipped: dict[str, str] = {}
    sources = read_sources()
    if flagged is None:
        flagged = hard_flagged(russian, english)
    recorded = read_fingerprints()
    current = dict(recorded)
    for key, (value, path, number) in sources.items():
        where = "%s:%d" % (path.name, number)
        if key not in english:
            complaints.append("%s: the game's English no longer defines %s" % (where, key))
            continue
        why = reason(key, russian, english, flagged)
        if why is None:
            complaints.append("%s: the game's own Russian for %s is fine now — drop ours"
                              % (where, key))
            continue
        problems = check(key, value, english[key].value)
        complaints += ["%s: %s" % (where, p) for p in problems]
        if problems:
            continue
        digest = fingerprint(english[key].value)
        was = recorded.get(key)
        if was is not None and was != digest and not accept:
            complaints.append("%s: English for %s changed since it was translated — "
                              "update the Russian, then generate.py --accept" % (where, key))
            continue
        current[key] = digest
        shipped[key] = value
    entries = {k: locscan.Entry(k, v, OUT, 0) for k, v in shipped.items()}
    for finding in locscan.scan(entries, english, locscan.HARD):
        complaints.append("translation of %s trips %s: %s"
                          % (finding.key, finding.rule, finding.detail))
    for key in list(current):
        if key not in sources:
            del current[key]
    if not complaints:
        write_fingerprints(current)
    loading = {k for k in shipped if "loading_screen" in english[k].path.parts}
    return shipped, loading, complaints


def todo(russian: dict, english: dict, repaired: set[str] = frozenset(),
         flagged: set[str] | None = None) -> dict[str, dict[str, dict]]:
    """Every key that needs Russian and has none in `translations/`, by game file stem.

    `repaired` are the keys `generate.py` already mends by rewrite: a broken
    key it fixes needs no translation.
    """
    done = read_sources()
    flagged = (hard_flagged(russian, english) if flagged is None else flagged) - set(repaired)
    out: dict[str, dict[str, dict]] = {}
    for key, entry in english.items():
        if key in done:
            continue
        why = reason(key, russian, english, flagged)
        if why is None:
            continue
        stem = entry.path.name[: -len("_l_english.yml")]
        item = {"why": why, "en": entry.value}
        if key in russian:
            item["ru_now"] = russian[key].value
        out.setdefault(stem, {})[key] = item
    return out


def check_files(paths: list[str]) -> int:
    """The per-key checks on translation files, without the slow whole-tree scan."""
    russian, english = locscan.load()
    bad = 0
    for name in paths:
        path = Path(name)
        for number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or re.match(r"^l_\w+:$", stripped):
                continue
            match = locscan.KEY_LINE.match(line)
            if not match:
                print("%s:%d: cannot parse: %r" % (path.name, number, line))
                bad += 1
                continue
            key, value = match.groups()
            if key not in english:
                print("%s:%d: the game's English does not define %s" % (path.name, number, key))
                bad += 1
                continue
            for problem in check(key, value, english[key].value):
                print("%s:%d: %s" % (path.name, number, problem))
                bad += 1
    print("problems: %d" % bad)
    return 1 if bad else 0


def main(argv: list[str]) -> int:
    if "--check" in argv:
        return check_files(argv[argv.index("--check") + 1:])
    import generate  # here, not above: generate imports this module
    russian, english = locscan.load()
    fixed, _, _, _, findings = generate.repairs(russian, english)
    hard = {key for key, f in findings.items() if f.rule in locscan.HARD}
    pending = todo(russian, english, set(fixed), hard)
    count = Counter(item["why"] for items in pending.values() for item in items.values())
    print("left to translate: %d missing, %d english, %d stale"
          % (count["missing"], count["english"], count["stale"]))
    if "--todo" in argv:
        target = Path(argv[argv.index("--todo") + 1])
        target.mkdir(parents=True, exist_ok=True)
        for stem, items in pending.items():
            (target / ("%s.json" % stem)).write_text(
                json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
        print("wrote %d files to %s" % (len(pending), target))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
