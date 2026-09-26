#!/usr/bin/env python3
"""What is wrong with the game's own Russian localization, asked of the files.

The player runs EU5 in Russian. The Russian localization Paradox ships is not a
translation of the English strings so much as a rewrite of them, and the rewrite
damaged the markup in places: brackets that were never closed, a scope name that
does not exist in that context, a data function that lost an argument. The
engine does not render those keys at all — it writes a line to `error.log` or to
`gui.log` and leaves the text blank or half printed.

This module is the list of ways that damage shows up, written as rules that can
be asked of every key in the tree at once. Each rule was put here because a real
key tripped it and the game complained; the comment on each names the evidence.

The rules split in two:

**Hard** rules cannot fire on a healthy key. An unbalanced bracket is broken in
any language, in any context, with no exception — so a hard rule firing is a bug
and nothing else, and `generate.py` will let a fix ship on the strength of one.

**Advisory** rules compare the Russian key against the English key of the same
name and report a difference that is *usually* damage. Russian legitimately
rearranges a sentence, and a rewritten string may reference a scope the English
one had no use for, so these need a person to look. `generate.py` will not
accept an advisory rule alone as the reason for a fix; say what the game logged.

Run it to see the current state of the tree:

    python3 mods/ru_loc_fix/tools/locscan.py              every rule, summarised
    python3 mods/ru_loc_fix/tools/locscan.py --rule brackets
    python3 mods/ru_loc_fix/tools/locscan.py --key HONOR_TT_CURRENT_TEXT
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

MOD = Path(__file__).resolve().parent.parent
REPO = MOD.parent.parent
sys.path.insert(0, str(REPO / "tools"))
import refs  # noqa: E402  the reference tree, resolved by mod id

# ` KEY:0 "value"` — the version number after the colon is optional and ignored,
# and so is a comment after the closing quote. Missing that trailing comment cost
# this module 18 012 keys, 3.4% of the tree, every one of them silently: a line
# it cannot match is not a key as far as every rule here is concerned, so
# `hre_tt: "0" #True` read as undefined and every reference to it looked broken.
# The value itself is matched greedily to the last quote on the line, so a `#`
# inside the text — `#Y ... #!` — is safe.
KEY_LINE = re.compile(r'^\s*([A-Za-z0-9_.\-]+):\d*\s+"(.*)"\s*(?:#.*)?$')
# `[ ... ]`, one level, which is what a data function looks like from outside.
DATA_BLOCK = re.compile(r"\[([^\[\]]*)\]")
# The identifier a data function starts from: `Country.GetName` -> `Country`.
DATA_ROOT = re.compile(r"(?:^|[\s(,])([A-Za-z_][A-Za-z0-9_]*)\.")
# `$OTHER_KEY$` — one localization key quoting another.
KEY_REF = re.compile(r"\$([A-Za-z0-9_.\-]+)(?:\|[^$]*)?\$")
# `Name(` anywhere in a data block, for counting the arguments it was given.
CALL = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)\(")
# Accessors that hand back text. Nothing can be promoted off the end of one.
TEXT_ACCESSOR = re.compile(
    r"\.(GetName|GetNameWithNoTooltip|GetLongName|GetLongNameWithNoTooltip"
    r"|GetAdjective|GetAdjectiveWithNoTooltip|GetShortName"
    r"|GetShortNameWithNoTooltip)\.Custom\("
)
# A name at the start of a line in the engine's own data type dump, which is
# either a type (`UnitTypeLateralView`) or one of its members
# (`UnitTypeLateralView.GetPlayer`). The first component is the root.
DUMPED_ROOT = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)(?:[.(]|\s*$)", re.M)
# Every name in the dump, root and member alike: `Location.GetTotalFoodConsumption`
# contributes both halves.
DUMPED_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*", re.M)
# `.Something` in a data function — one step along a promote chain.
MEMBER = re.compile(r"\.([A-Za-z_][A-Za-z0-9_]*)")
# A saved event scope, which is written in snake case and defined by the event
# script rather than by anything in this tree.
SAVED_SCOPE = re.compile(r"^[a-z][a-z0-9_]*$")


@dataclass
class Entry:
    key: str
    value: str
    path: Path
    line: int


@dataclass
class Finding:
    rule: str
    key: str
    detail: str
    entry: Entry = field(repr=False, default=None)


def read_language(directory: Path) -> dict[str, Entry]:
    """Every key a localization tree defines, last definition winning.

    Last wins because that is what the engine does with a key defined twice, and
    a rule that scanned a shadowed value would report a string nobody can see.
    """
    found: dict[str, Entry] = {}
    for path in sorted(directory.rglob("*.yml")):
        try:
            text = path.read_text(encoding="utf-8-sig")
        except (UnicodeDecodeError, OSError):
            continue
        for number, line in enumerate(text.splitlines(), 1):
            match = KEY_LINE.match(line)
            if match:
                key, value = match.groups()
                found[key] = Entry(key, value, path, number)
    return found


def load(root: Path = None) -> tuple[dict[str, Entry], dict[str, Entry]]:
    """The game's Russian and English localization, as key -> entry."""
    base = root or refs.GAME_LOCALIZATION
    return read_language(base / "russian"), read_language(base / "english")


# --------------------------------------------------------------------------
# Hard rules. A healthy key cannot trip one of these.
# --------------------------------------------------------------------------

def bracket_fault(value: str) -> str | None:
    """`[` and `]` that do not pair up.

    The engine reads `[...]` as a data function and everything else as text, so
    a bracket that never closes swallows the rest of the line and a bracket that
    closes nothing leaves the opening text printed raw. Both are the same class
    of typo and both were found in the shipped Russian files: five economy
    tooltips lost the `]` after `|W`, and `WAR_UNIT_TYPE_STATS_TT_LOSSES` has a
    doubled `[[`. The game answers with
    `pdx_gui_localize.cpp:302 - Failed parsing localized text: <key>`.
    """
    depth = 0
    for character in value:
        if character == "[":
            depth += 1
        elif character == "]":
            depth -= 1
            if depth < 0:
                return "a ']' that closes nothing"
    return "a '[' that is never closed" if depth else None


def custom_on_text_fault(value: str) -> str | None:
    """`.Custom(...)` hung off an accessor that returns text.

    `Country.GetName` is already a string; there is no object left to ask for a
    custom localization. `VOTE_OF_COUNTRY` does exactly this and the game
    reports the whole key as unparseable. The fix is always to drop the text
    accessor: `Country.Custom('CL_GEN')`.
    """
    match = TEXT_ACCESSOR.search(value)
    return "'%s' — Custom() on a string" % match.group(0).strip(".") if match else None


def filter_nested_fault(key: str, value: str, russian: dict[str, Entry]) -> str | None:
    """A search-filter string quoting another key that contains data functions.

    Filter names and descriptions are built per object — one per good, one per
    pop type — and in that context a `$OTHER_KEY$` reference is expanded without
    the object's scope. Direct data functions work there; the same functions
    reached through a quoted key do not.

    This is not a guess. `lists_l_russian.yml` writes some of these keys both
    ways, and the split in the log is exact:
    `CUSTOM_SEARCH_FILTER_LOCATION_RAW_GOODS_NAME` uses
    `[GOODS.GetNameWithNoTooltip]` directly and never errors, while
    `..._RAW_GOODS_DESC` quotes `$GOODS_GetNameWithNoTooltip_RU_ACC_lower$` and
    fails every single time. Five such keys produced 34 225 of the 39 289 errors
    in the run of 2026-08-24 — over one second, which rotated `error.log` five
    times and took every other error of that session with it.

    Fixing those five did not end the class: the hour-long run that followed put
    `RGO_BUILD_GOODS_PRICE_IMPACT_ON_COST` (13 950 lines), `FILTER_BY_GOODS`
    (3 866) and `MARKET_SURPLYS_INFO` (1 650) in their place, none of which is a
    filter string. This rule stays narrow because it is the only shape that can
    be *proven* wrong from the files — the same key written both ways, four lines
    apart. `declension_ref` lists the rest of the pool for a person to watch.
    """
    if not key.startswith("CUSTOM_SEARCH_FILTER_"):
        return None
    for referenced in KEY_REF.findall(value):
        target = russian.get(referenced)
        if target and DATA_BLOCK.search(target.value):
            return "quotes $%s$, which contains data functions" % referenced
    return None


def dumped_roots() -> set[str]:
    """Every type and promote the engine printed in `dump_data_types`.

    A GUI type can be perfectly real and still never appear in the English
    localization — `UnitTypeLateralView` is used by twenty-five Russian unit
    tooltips and by no English string at all. Asking the engine's own dump is
    what keeps `unknown_root` from calling those a bug.
    """
    known: set[str] = set()
    for path in sorted((refs.GAME / "docs/data_types").glob("*.txt")):
        known.update(DUMPED_ROOT.findall(path.read_text(encoding="utf-8", errors="replace")))
    return known


def near_miss(root: str, neighbours: set[str]) -> str | None:
    """The name this one is a slip of, if it is one letter away from a real one."""
    for other in sorted(neighbours):
        if other == root:
            continue
        if abs(len(other) - len(root)) > 1:
            continue
        if len(other) == len(root):
            if sum(a != b for a, b in zip(other, root)) == 1:
                return other
            continue
        longer, shorter = (other, root) if len(other) > len(root) else (root, other)
        for cut in range(len(longer)):
            if longer[:cut] + longer[cut + 1:] == shorter:
                return other
    return None


def unknown_root_fault(value: str, known: set[str], neighbours: set[str]) -> str | None:
    """A data function starting from a name that is not a thing.

    `known` is every root the English localization uses plus every type the
    engine dumped, so a root outside it is either an invention —
    `LocationFoodWrap` where the English key says `Location`, `XXX` where a
    translator left a placeholder — or a slip of the finger.

    A snake case root can also be an event's saved scope, which no file in this
    tree declares, so those are only reported when they are one letter away from
    a name used elsewhere in the same file: `taget_character` next to
    `target_character`, `arget_heir` next to `target_heir`.
    """
    for root in sorted(roots(value)):
        if root in known:
            continue
        if SAVED_SCOPE.match(root):
            slip = near_miss(root, neighbours)
            if slip:
                return "'%s.' is one letter from '%s.'" % (root, slip)
            continue
        return "'%s.' is neither a dumped type nor a root the English tree uses" % root
    return None


def dumped_names() -> set[str]:
    """Every name the engine dumped, split at the dots.

    `Location.GetTotalFoodConsumption` contributes `Location` and
    `GetTotalFoodConsumption`, so a member can be checked for existence without
    knowing what type the chain in front of it produced.
    """
    known: set[str] = set()
    for path in sorted((refs.GAME / "docs/data_types").glob("*.txt")):
        for name in DUMPED_NAME.findall(path.read_text(encoding="utf-8", errors="replace")):
            known.update(name.split("."))
    return known


def unknown_member_fault(value: str, known: set[str]) -> str | None:
    """A step in a promote chain that the engine never printed.

    The engine's own `dump_data_types` lists every accessor it has, so a
    `.Something` outside that list cannot resolve. `EXPLORATION_CONSTRUCTION_
    FINISHED_WHEN` asks for `GetFinishedDate`, which does not exist — the real
    one is `GetFinishedDateIncludingQueue`, and the English key uses it.

    This does not check that the member belongs to *this* chain's type, only
    that it exists at all; the narrower check would need the type of every
    expression, which the dump does not give us.
    """
    for block in DATA_BLOCK.findall(value):
        # `Concept('x', 'text')` and `Link(...)` carry display text that may
        # contain dots and full stops; their arguments are not promote chains.
        stripped = re.sub(r"'[^']*'", "''", block)
        for member in MEMBER.findall(stripped):
            if member not in known:
                return "'.%s' is not in the engine's data type dump" % member
    return None


# --------------------------------------------------------------------------
# Advisory rules. These compare against English and need a person to read them.
# --------------------------------------------------------------------------

def roots(value: str) -> set[str]:
    """The identifiers data functions in this value start from."""
    found: set[str] = set()
    for block in DATA_BLOCK.findall(value):
        found.update(DATA_ROOT.findall(block))
    return found


# `A.B.C` — a promote chain, for pairing each step with the one in front of it.
CHAIN = re.compile(r"(?:^|[\s(,])([A-Za-z_][A-Za-z0-9_]*)((?:\.[A-Za-z_][A-Za-z0-9_]*)+)")
# Two accessors the Russian files reach for constantly and the English ones never
# need: a declension and a gender agreement. They are available on any scope, so
# their absence from the English corpus says nothing.
RUSSIAN_ONLY = {"Custom", "IsFemale"}
# The declension helpers: a key holding seventy five `AddTextIf` tests that turn
# a goods or estate name into one Russian case. Referencing one loses the scope
# in some panels and not others.
DECLENSION_HELPER = re.compile(r"^(GOODS|Goods|TARGET_GOODS|ESTATE|Estate)_.*_RU_")
# How often English has to use a root before its silence about a member counts
# as evidence.
ENOUGH = 20


def chain_pairs(value: str) -> set[tuple[str, str]]:
    """Each `<thing>.<member>` step in the value's promote chains."""
    found: set[tuple[str, str]] = set()
    for block in DATA_BLOCK.findall(value):
        block = re.sub(r"'[^']*'", "''", block)
        for match in CHAIN.finditer(block):
            previous = match.group(1)
            for member in match.group(2).split(".")[1:]:
                found.add((previous, member))
                previous = member
    return found


def member_on_root_fault(value: str, en_pairs: dict, en_roots: dict) -> str | None:
    """A member asked of something the English files never ask it of.

    Weaker than `unknown_member`, which only says the accessor exists somewhere;
    this says it exists on the wrong thing. English calls `TARGET_CULTURE.GetName`
    210 times and never `.GetAdjective`, and sure enough the engine's dump gives
    `GetAdjective` to Country, Government, Location, Religion and ReligionGroup
    and not to Culture — so the five Russian keys that ask a culture for its
    adjective print nothing.

    Advisory, because English's silence is not proof: it needs `GetAdjective` on
    a country and Russian needs it on everything, and a rewritten sentence may
    legitimately reach one step further. Read the hits against the dump —
    `python3 tools/api.py <member>` says which types have it.
    """
    for root, member in sorted(chain_pairs(value)):
        if member in RUSSIAN_ONLY:
            continue
        if en_roots.get(root, 0) >= ENOUGH and (root, member) not in en_pairs:
            return "%s.%s — English uses %s. %d times and never with .%s" % (
                root, member, root, en_roots[root], member)
    return None


def declension_ref_fault(key: str, value: str, russian: dict[str, Entry]) -> str | None:
    """A key that reaches a Russian case through one of the declension helpers.

    `filter_nested` proves the fault for the shape where the same key exists both
    ways; this reports the whole pool it belongs to. Ninety-odd keys reference
    `$GOODS_..._RU_GEN_lower$` or a sibling, and the game has complained about
    ten of them so far — always when a panel that had never been opened before
    was opened. There is nothing in the files that separates the ten from the
    rest, so this stays advisory and the list is what to read the next log
    against.

    Where one does fail, the repair is `fixes/expand.txt`: write the helper out
    inside the key. The promote resolves inline in the very same string where it
    fails through the reference, so inlining keeps the declension and loses the
    error.
    """
    if DECLENSION_HELPER.match(key):
        return None  # the helpers themselves, quoting each other
    for referenced in KEY_REF.findall(value):
        if DECLENSION_HELPER.match(referenced) and referenced in russian:
            return "reaches a Russian case through $%s$" % referenced
    return None


# The characters a localization key is made of, for generating the one-edit
# neighbours of a name that is not a key.
KEY_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_."


def one_edit_away(name: str, keys: set[str]) -> str | None:
    """A defined key one insertion, deletion or substitution from `name`.

    Generated from the name rather than compared against every key: the tree has
    286 000 of them and this is asked for a thousand names.
    """
    for cut in range(len(name)):
        candidate = name[:cut] + name[cut + 1:]
        if candidate in keys:
            return candidate
    for cut in range(len(name)):
        for character in KEY_ALPHABET:
            if character == name[cut]:
                continue
            candidate = name[:cut] + character + name[cut + 1:]
            if candidate in keys:
                return candidate
    for cut in range(len(name) + 1):
        for character in KEY_ALPHABET:
            candidate = name[:cut] + character + name[cut:]
            if candidate in keys:
                return candidate
    return None


def misspelled_refs(russian: dict[str, Entry],
                    english: dict[str, Entry]) -> dict[str, str]:
    """`$NAME$` references that name no key, mapped to the key they meant.

    A `$NAME$` in a value is one of two things and the file cannot tell them
    apart by looking: a reference to another localization key, or a parameter
    the caller substitutes at runtime. `$NUM$` is a parameter and names no key;
    reporting it would drown the rule.

    Two filters together do separate them, and both are needed. **The English
    key set** answers the parameter question: a parameter the engine
    substitutes is substituted in every language, so a `$NAME$` that appears
    nowhere in the English tree is not one. **One edit** answers the rest: a
    reference that is a single keystroke from a key that does exist is a slip,
    and a name invented from nothing is not reported at all.

    Loosening either filter breaks it. Edit distance alone offers `$NUM$` ->
    `$AUM$` and a hundred more like it, because a three letter parameter is
    always one letter from something in a tree this size.

    What comes back is the *nearest* defined key, which is not always the
    intended one. Four of the thirteen references this finds are cultures — Even
    and Evenk, Halkomelem and Halkomelemt, Lalagir and Lalagyr are each two real
    peoples, and the nearest key belongs to the other one. The fault is hard
    either way: the reference resolves to nothing and the raw name reaches the
    screen. The repair is a person's, and `fixes/` is where they write it.
    """
    defined = set(russian)
    parameters: set[str] = set()
    for entry in english.values():
        parameters.update(KEY_REF.findall(entry.value))

    wanted: set[str] = set()
    for entry in russian.values():
        for referenced in KEY_REF.findall(entry.value):
            if referenced not in defined and referenced not in parameters:
                wanted.add(referenced)

    repairs: dict[str, str] = {}
    for name in sorted(wanted):
        near = one_edit_away(name, defined)
        if near:
            repairs[name] = near
    return repairs


def missing_ref_fault(key: str, value: str, repairs: dict[str, str],
                      russian: dict[str, Entry],
                      english: dict[str, Entry]) -> str | None:
    """A `$NAME$` reference to a key that does not exist.

    The engine does not fail on it and does not log it: it prints the name, in
    capitals, in the middle of the sentence. `TO_MOVE_FURTHER_TO_RIGHT` reads
    "Дальше продвинуться в сторону $SOCIEALVALUE_RIGHTITEM_WNTT_GEN$:" — one
    missing T in a name defined seven lines away — and that is what the societal
    value tooltip shows on screen. Seen in a 2026-08-25 screenshot; TESTLOG has
    it.

    `repairs` decides which references count, and is built once by
    `misspelled_refs` — a reference outside it is a runtime parameter or an
    invention, and neither is this rule's business.
    """
    for referenced in KEY_REF.findall(value):
        if referenced not in repairs:
            continue
        their = english.get(key)
        if their:
            # The English key of the same name is evidence rather than
            # inference — but only where it references something a keystroke
            # from the broken name. Its `$VAL$` and `$NAME$` are parameters the
            # caller fills in, and one of those happens to be a defined key too,
            # so "the English key references something" is not on its own a
            # reason to believe it is what the Russian meant.
            for name in KEY_REF.findall(their.value):
                if name != referenced and one_edit_away(referenced, {name}):
                    return ("$%s$ names no key; the English key of the same "
                            "name references $%s$" % (referenced, name))
        return "$%s$ names no key (nearest defined: $%s$)" % (
            referenced, repairs[referenced])
    return None


def scope_difference(value: str, english: str) -> str | None:
    """A scope the Russian key reaches for and the English key does not.

    Sometimes a rewrite, sometimes a wrong scope: `UNLOCKS_TOWN_RIGHTS` asks for
    `TOWN_RIGHTS` where English asks `TOWN_RIGHTS_TYPE`, and the game answers
    `Promote 'TOWN_RIGHTS' returned nullptr`.
    """
    extra = roots(value) - roots(english)
    return "uses %s, absent from the English key" % ", ".join(sorted(extra)) if extra else None


def argument_counts(value: str) -> dict[str, set[int]]:
    """How many arguments each named call was given, per name."""
    counts: dict[str, set[int]] = {}
    for block in DATA_BLOCK.findall(value):
        for match in CALL.finditer(block):
            name = match.group(1)
            depth, args, seen = 1, 1, False
            for character in block[match.end():]:
                if character == "(":
                    depth += 1
                elif character == ")":
                    depth -= 1
                    if depth == 0:
                        break
                elif character == "," and depth == 1:
                    args += 1
                if depth == 1 and not character.isspace():
                    seen = True
            counts.setdefault(name, set()).add(args if seen else 0)
    return counts


def argument_difference(value: str, english: str) -> str | None:
    """The same call, given a different number of arguments than in English.

    `TT_AVERAGE_DISCIPLINE_COMBAT_TEXT` calls `GetCombatModifierNoFormat` with
    two arguments where English passes three, and the key fails to parse.
    """
    mine, theirs = argument_counts(value), argument_counts(english)
    for name, counts in mine.items():
        if name in theirs and not (counts & theirs[name]):
            return "%s() takes %s here and %s in English" % (
                name,
                "/".join(str(n) for n in sorted(counts)),
                "/".join(str(n) for n in sorted(theirs[name])),
            )
    return None


# A window's own context (`CountryCultureLateralView`, `LocationView`) or the
# player, where English asks the thing the tooltip is about.
FOREIGN_CONTEXT = re.compile(r"(View|^Player)$")


def foreign_context_fault(value: str, english: str) -> str | None:
    """A window context or `Player` the English key does not use.

    The key then works only inside that one window, and only for the player:
    Glorp UI's left panel shows `CULTURAL_TRADITION_TT_TEXT` outside the
    culture window and got "No context supplied … 'CountryCultureLateralView'"
    318 times in a minute; `TT_AVERAGE_DISCIPLINE_TEXT` printed the player's
    discipline on every other country. Hard only when English has roots of its
    own — a key with none has nothing to say which scope was meant.
    """
    theirs = roots(english)
    if not theirs:
        return None
    extra = sorted(r for r in roots(value) - theirs if FOREIGN_CONTEXT.search(r))
    return "asks %s, English asks %s" % (", ".join(extra), ", ".join(sorted(theirs))) if extra else None


HARD = ("brackets", "custom_on_text", "filter_nested", "unknown_root",
        "unknown_member", "missing_ref", "foreign_context")
ADVISORY = ("scope", "arguments", "member_on_root", "declension_ref")
RULES = HARD + ADVISORY


def scan(russian: dict[str, Entry], english: dict[str, Entry],
         rules: tuple[str, ...] = RULES) -> list[Finding]:
    """Every rule in `rules`, against every Russian key."""
    known: set[str] = set()
    members: set[str] = set()
    en_pairs: set[tuple[str, str]] = set()
    en_roots: dict[str, int] = {}
    if "member_on_root" in rules:
        for entry in english.values():
            for pair in chain_pairs(entry.value):
                en_pairs.add(pair)
                en_roots[pair[0]] = en_roots.get(pair[0], 0) + 1
    repairs: dict[str, str] = {}
    if "missing_ref" in rules:
        repairs = misspelled_refs(russian, english)
    per_file: dict[Path, set[str]] = {}
    if "unknown_member" in rules:
        members = dumped_names()
        for entry in english.values():
            for block in DATA_BLOCK.findall(entry.value):
                members.update(MEMBER.findall(re.sub(r"'[^']*'", "''", block)))
    if "unknown_root" in rules:
        for entry in english.values():
            known |= roots(entry.value)
        known |= dumped_roots()
        for entry in russian.values():
            per_file.setdefault(entry.path, set()).update(roots(entry.value))

    findings: list[Finding] = []
    for key, entry in russian.items():
        pair = english.get(key)
        checks = (
            ("brackets", lambda: bracket_fault(entry.value)),
            ("custom_on_text", lambda: custom_on_text_fault(entry.value)),
            ("filter_nested", lambda: filter_nested_fault(key, entry.value, russian)),
            ("unknown_root", lambda: unknown_root_fault(
                entry.value, known, per_file.get(entry.path, set()))),
            ("unknown_member", lambda: unknown_member_fault(entry.value, members)),
            ("missing_ref", lambda: missing_ref_fault(
                key, entry.value, repairs, russian, english)),
            ("foreign_context", lambda: foreign_context_fault(entry.value, pair.value) if pair else None),
            ("scope", lambda: scope_difference(entry.value, pair.value) if pair else None),
            ("arguments", lambda: argument_difference(entry.value, pair.value) if pair else None),
            ("member_on_root", lambda: member_on_root_fault(entry.value, en_pairs, en_roots)),
            ("declension_ref", lambda: declension_ref_fault(key, entry.value, russian)),
        )
        for name, check in checks:
            if name not in rules:
                continue
            detail = check()
            if detail:
                findings.append(Finding(name, key, detail, entry))
    findings.sort(key=lambda f: (RULES.index(f.rule), f.entry.path.name, f.entry.line))
    return findings


def main(argv: list[str]) -> int:
    wanted = RULES
    if "--rule" in argv:
        name = argv[argv.index("--rule") + 1]
        if name not in RULES:
            print("no rule named %r; have %s" % (name, ", ".join(RULES)))
            return 2
        wanted = (name,)

    russian, english = load()
    print("game localization: %d Russian keys, %d English" % (len(russian), len(english)))

    if "--key" in argv:
        key = argv[argv.index("--key") + 1]
        entry = russian.get(key)
        if not entry:
            print("no Russian key named %r" % key)
            return 2
        print("\n%s  (%s:%d)" % (key, entry.path.name, entry.line))
        print("  RU %s" % entry.value)
        print("  EN %s" % (english[key].value if key in english else "(no English key)"))
        hits = [f for f in scan({key: entry}, english, wanted) if f.key == key]
        for finding in hits:
            print("  !  %-14s %s" % (finding.rule, finding.detail))
        if not hits:
            print("  .  no rule fires on this key")
        return 0

    findings = scan(russian, english, wanted)
    counts = {rule: 0 for rule in wanted}
    for finding in findings:
        counts[finding.rule] += 1

    print()
    for rule in wanted:
        kind = "hard    " if rule in HARD else "advisory"
        print("  %s %-15s %4d" % (kind, rule, counts[rule]))

    detailed = [f for f in findings if f.rule in HARD]
    if detailed:
        print("\nhard rules, in full — each of these is broken in game:\n")
        for finding in detailed:
            print("  %s:%d  %s" % (finding.entry.path.name, finding.entry.line, finding.key))
            print("      %s: %s" % (finding.rule, finding.detail))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
