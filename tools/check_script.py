#!/usr/bin/env python3
"""Three ways a mod file fails at load, all findable from here.

Every other checker in this tree answers a question about one mod's meaning.
This one answers a question about the file: the game read it and gave up, and
said so in `error.log` once per line while the session that wrote it saw nothing
at all. Both rules below cost a run on 2026-08-31, in one build, together.

**A trigger's conditional is `trigger_if`.** `if` is an *effect* — the engine's
own dump says so — and `else_if` is not in the dump at all. Written in a file
under `common/scripted_triggers/` they produce `Unknown trigger type: else_if`
once per line and a scripted trigger that comes back true no matter what, which
is the worst possible failure for a filter: it filters nothing and looks fine.
`where_to_produce`'s "only where it can be built today" was that, from the day
it was written.

**A file carries one byte order mark, at byte zero.** A second one is a
character in the text, and the interface parser answers
`'﻿' is not a valid widget/type/property` and then abandons the whole
file — every type in it missing, the window never found. Writing a string that
already begins with `﻿` through `encoding='utf-8-sig'` is how it happens,
and nothing about the file looks wrong afterwards.

**A name that nothing defines is not an error the game reports usefully.**
`bag_wtp_store_right_row_if_worth_it` called `bag_wtp_right_row_is_worth_it` and
the patch that was to have written that trigger died half way; the call stayed,
the definition never existed, and the `limit` it sat in passed for every
province. The symptom was a filter that filtered nothing — which is the same
symptom as the `trigger_if` rule above, and cost a run of its own. Every
`<name> = yes` in a mod's own `common/` has to resolve: to something the mod
defines, to something a mod in `reference/` defines (CMF's macros), or to an
effect or trigger in the engine's own dumps.

    python3 tools/check_script.py                 every mod in mods/
    python3 tools/check_script.py mods/<mod>      one of them
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# `if`, `else` and `else_if` as a block key. Anything under `scripted_triggers/`
# is a trigger all the way down, so depth does not enter into it.
EFFECT_CONDITIONAL = re.compile(r'(?<![\w.])(if|else|else_if)\s*=\s*\{')

# Files the game parses. `.yml` is localization and carries a BOM too, but a
# doubled one there is a broken first key rather than a broken file, and
# `check_cmm.py` already reads those.
PARSED = ("*.txt", "*.gui")

# And only under a mount the game reads. A generator's fingerprint table and a
# translator's rewrite list are `.txt` in the same repository and are nobody's
# game files; asking them for a byte order mark is noise.
MOUNTS = ("in_game", "main_menu", "loading_screen")

# `<name> = { ... }` at the top of a line is a definition; `<name> = yes` is a
# call. `yes` is also how a hundred ordinary keys are written -- `always = yes`,
# `is_ownable = yes` -- so a call only counts as unresolved when nothing in the
# game, in `reference/`, or in the mod itself defines it.
# A variable this mod writes, reads, or hands to CMF to write. **The game logs
# the fault this catches** -- «Variable 'X' is used but is never set» -- but only
# once the mod is loaded, and what it costs is a run: on 2026-09-01 a rename in
# `where_to_produce`'s generator caught `set_variable` for the plan window's own
# open flag along with the three it meant, and both plan buttons stopped opening
# anything. Nothing else in the mod said a word.
WRITTEN = (
    # **`remove_variable` is not a write.** A variable only ever removed and read
    # is precisely the fault: the rename that broke both plan buttons left the
    # window's flag with a reader, a remover, and nobody to set it.
    # **A local is a write too.** `local_var:x` matches the `var:` arm of
    # BEING_READ below -- nothing stands in front of `var:` there -- so unless
    # `set_local_variable` counts, every staged local reads as never set. The
    # town-rights map copy staged nineteen of them and all nineteen were
    # reported as faults.
    re.compile(r'(?:set|change)(?:_global|_local)?_variable(?:_list)?\s*=\s*'
               r'\{\s*name\s*=\s*(\w+)'),
    re.compile(r'add_to(?:_global|_local)?_variable_list\s*=\s*\{\s*name\s*=\s*(\w+)'),
    # CMF owns these: a setting alias and a list it builds are written by the
    # framework, and the mod only ever reads them back.
    re.compile(r'(?:alias|list_name)\s*=\s*(\w+)'),
)
BEING_READ = re.compile(
    r'(?:global_var|var):(\w+)'
    r'|has(?:_global)?_variable\s*=\s*(\w+)'
    r"|GetVariable\('(\w+)'\)"
    r'|is_target_in(?:_global)?_variable_list\s*=\s*\{\s*name\s*=\s*(\w+)'
    r'|(?<![\w])variable\s*=\s*(\w+)')

# A read the mod knows can never be written, with the reason beside it. Put on
# the line, the way `check_docs.py` takes `check-docs: ignore`.
IGNORE_READ = "check-script: never set"


DEFINITION = re.compile(r'^(\w+)\s*=\s*\{', re.M)
CALL = re.compile(r'(?<![\w.:])(\w+)\s*=\s*yes\b')


def known_names() -> set[str]:
    """Everything a call may legitimately name, gathered once.

    The engine's own dumps carry `## <name>` per effect and trigger, which is
    where `always`, `is_ownable` and the rest come from; `reference/mods/` is
    where CMF's macros and every other mod's scripted effects live.
    """
    names: set[str] = set()
    for log in ("effects.log", "triggers.log"):
        path = REPO / "reference/game/docs" / log
        if path.is_file():
            names.update(line[3:].strip()
                         for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
                         if line.startswith("## "))
    for base in ((REPO / "reference/game/in_game/common"),
                 *(p / "in_game/common" for p in (REPO / "reference/mods").glob("*"))):
        if not base.is_dir():
            continue
        for path in base.rglob("*.txt"):
            names.update(DEFINITION.findall(path.read_text(encoding="utf-8-sig",
                                                           errors="replace")))
    return names


def unresolved(root: Path, known: set[str]) -> list[str]:
    """Calls in this mod's own `common/` that name nothing that exists."""
    defined: set[str] = set()
    sources: list[tuple[Path, str]] = []
    for path in sorted((root / "in_game/common").rglob("*.txt")):
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        defined.update(DEFINITION.findall(text))
        sources.append((path, text))
    if not defined:
        return []
    # Only names in this mod's own namespace: `always = yes` is the engine's and
    # a call into another mod is that mod's business.
    prefixes = tuple(sorted({n.split("_")[0] + "_" for n in defined}))
    found = []
    for path, text in sources:
        for match in CALL.finditer(text):
            name = match.group(1)
            if name in defined or name in known or not name.startswith(prefixes):
                continue
            line = text[:match.start()].count("\n") + 1
            found.append(f"{path.relative_to(REPO)}:{line}: `{name}` is called and "
                         f"nothing defines it — the block it sits in passes or "
                         f"does nothing, and the game says so nowhere useful")
    return found


def unresolved_script_values(root: Path) -> list[str]:
    """Every `ScriptValue('x')` this mod prints, against the values it defines.

    **A `ScriptValue` that names nothing prints a blank and says so nowhere.**
    Not in `error.log`, not on screen -- the line simply comes out with a hole
    where the number was, and a diagnosis full of them still looks like a
    diagnosis. On 2026-09-06 a `WTP G<n>` line was one build from shipping with
    `bag_wtp_dg17` on it against sixteen generated scratch values.

    Reads every place a value can be printed from: the localization, the
    windows, and `debug_log` strings in `common/`. Only this mod's own names --
    another mod's value is that mod's business, and the engine's own are not
    script values at all.
    """
    defined: set[str] = set()
    for path in sorted((root / "in_game/common/script_values").rglob("*.txt")):
        defined.update(DEFINITION.findall(
            path.read_text(encoding="utf-8-sig", errors="replace")))
    if not defined:
        return []
    prefixes = tuple(sorted({n.split("_")[0] + "_" for n in defined}))
    found = []
    for pattern in ("in_game/**/*.txt", "in_game/**/*.gui",
                    "main_menu/**/*.yml"):
        for path in sorted(root.glob(pattern)):
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8-sig", errors="replace")
            for match in re.finditer(r"ScriptValue\('([\w.]+)'\)", text):
                name = match.group(1)
                if name in defined or not name.startswith(prefixes):
                    continue
                line = text[:match.start()].count("\n") + 1
                found.append(
                    f"{path.relative_to(REPO)}:{line}: `ScriptValue('{name}')` "
                    f"and no script value of that name — it prints a blank, in "
                    f"`error.log` and everywhere else")
    return found


def duplicate_definitions(root: Path) -> list[str]:
    """Two script values of the same name, which the engine resolves silently.

    **The first definition wins and the second is dropped**, the same rule
    `customizable_localization` obeys (`CLAUDE.md`) -- so a value edited in the
    wrong copy simply has no effect, and nothing on screen or in `error.log`
    says which copy the game is reading. Two of these were shipped in one day on
    2026-09-06, both from a generator adding a reader that already existed
    forty lines further down.
    """
    seen: dict[str, str] = {}
    found = []
    for path in sorted((root / "in_game/common/script_values").rglob("*.txt")):
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        for match in re.finditer(r"^([a-z0-9_]+) = \{", text, re.M):
            name = match.group(1)
            line = text[:match.start()].count("\n") + 1
            where = f"{path.relative_to(REPO)}:{line}"
            if name in seen:
                found.append(
                    f"{where}: `{name}` is defined twice — first at {seen[name]}, "
                    f"and the engine keeps the first and drops this one without "
                    f"saying so")
            else:
                seen[name] = where
    return found


def unwritten(root: Path) -> list[str]:
    """Variables this mod reads that nothing in it, and not CMF, ever writes.

    The game says this itself once loaded, so the only thing bought here is the
    run it would have cost. Scoped to the mod's own prefix: a variable belonging
    to the base game or to another mod is that mod's to set.
    """
    written: set[str] = set()
    ignored: set[str] = set()
    read: dict[str, tuple[Path, int]] = {}
    raw_lines: dict[Path, list[str]] = {}
    # `PARSED` holds globs, not suffixes -- matching a suffix against them reads
    # nothing at all and calls every mod clean, which is how this check first
    # shipped and passed.
    for path in sorted(root.rglob("*")):
        if not any(path.match(g) for g in PARSED) or not set(path.parts) & set(MOUNTS):
            continue
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        raw_lines[path] = text.splitlines()
        text = "\n".join(l.split("#", 1)[0] for l in text.splitlines())
        for pattern in WRITTEN:
            written.update(pattern.findall(text))
        for match in BEING_READ.finditer(text):
            name = next(g for g in match.groups() if g)
            line = text[:match.start()].count("\n") + 1
            if IGNORE_READ in raw_lines[path][line - 1]:
                ignored.add(name)
                continue
            read.setdefault(name, (path, line))
    # A mod's own namespace is the prefix its files are named for -- `bag_wtp`
    # from `bag_wtp_compute.txt`. Taken off the writes, so a mod that has not
    # settled on one is simply not checked rather than checked wrongly.
    prefixes = {n.rsplit("_", 1)[0] + "_" for n in written if n.count("_") >= 2}
    if not prefixes:
        return []
    found = []
    for name, (path, line) in sorted(read.items()):
        if name in written or name in ignored or not name.startswith(tuple(prefixes)):
            continue
        found.append(f"{path.relative_to(REPO)}:{line}: `{name}` is read and "
                     f"nothing sets it — the game logs this only once loaded, "
                     f"and finding out that way costs a run")
    return found


def problems(root: Path) -> list[str]:
    found: list[str] = []
    for pattern in PARSED:
        for path in sorted(root.rglob(pattern)):
            if not path.is_file() or not set(path.parts) & set(MOUNTS):
                continue
            raw = path.read_bytes()
            where = path.relative_to(REPO)

            if not raw.startswith(b"\xef\xbb\xbf"):
                found.append(f"{where}: no byte order mark — "
                             f"the game reads the first key as part of it")
                text = raw.decode("utf-8", "replace")
            else:
                text = raw.decode("utf-8-sig")

            if "﻿" in text:
                line = text[:text.index("﻿")].count("\n") + 1
                found.append(f"{where}:{line}: a second byte order mark, in the "
                             f"text — the interface parser abandons the file "
                             f"and every type in it goes missing")

            # **Braces, counted over the whole file, comments included.** Two
            # faults on 2026-09-01 that nothing here caught: a generator's
            # f-string nested one level too deep and shipped a literal `{{` into
            # every line of an effect, and a comment quoting `divide = {` left
            # the file one brace open. The engine ignores a brace in a comment
            # and chokes on the other, and neither says which file in
            # `error.log`, so both are cheaper to catch here.
            body = "\n".join(l.split("#", 1)[0] for l in text.splitlines())
            if "{{" in body or "}}" in body:
                token = "{{" if "{{" in body else "}}"
                line = body[:body.index(token)].count("\n") + 1
                found.append(f"{where}:{line}: `{token}` in script — a "
                             f"generator's f-string escaped one level too many, "
                             f"and the engine reads the whole block as one key")
            opened, closed = text.count("{"), text.count("}")
            if opened != closed:
                found.append(f"{where}: {opened} `{{` against {closed} `}}` — "
                             f"count them in the comments too; a stray brace in "
                             f"one is invisible to the engine and to a reader")

            if "scripted_triggers" not in path.parts:
                continue
            for match in EFFECT_CONDITIONAL.finditer(text):
                # A comment saying so is not a use of it.
                start = text.rfind("\n", 0, match.start()) + 1
                if "#" in text[start:match.start()]:
                    continue
                line = text[:match.start()].count("\n") + 1
                found.append(f"{where}:{line}: `{match.group(1)}` in a trigger — "
                             f"`if` is an effect and `else_if` is nothing; a "
                             f"trigger wants `trigger_{match.group(1)}`")
    return found


TRIGGER_ONLY = re.compile(
    r"^\s*(has_variable|has_global_variable|always|OR|AND|NOT|NOR|NAND|"
    r"is_target_in_variable_list|is_target_in_global_variable_list|"
    r"var:|global_var:|location_rank|raw_material|vegetation|topography|climate|"
    r"can_build_building|has_building|exists|owner|region|continent|market|"
    r"province_definition|scope:|#|\{|\}|$)")


def listless_callbacks(root: Path) -> list[str]:
    """A registered list setting with no `<setting>_on_changed` scripted GUI.

    CMM draws a list row only while `CMMGuiIsShown('<setting>_on_changed')`, and
    registering a list is what marks the setting as having one. Without the GUI
    the whole widget is hidden -- but a list is filed under a group named after
    itself, so the **group header still renders**. On screen it reads as a list
    that came back empty, which is the one thing it is not.

    Two builds were spent on it: the mod-source list registered one row, the
    dump counted that row, and the page showed a header with nothing under it.
    """
    registered: dict[str, str] = {}
    declared: set[str] = set()
    for path in sorted(root.rglob("*.txt")):
        if not set(path.parts) & set(MOUNTS):
            continue
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        text = "\n".join(l.split("#", 1)[0] for l in text.splitlines())
        for match in re.finditer(
                r"cmm_register(?:_global)?_settings_list\s*=\s*\{([^}]*)\}", text):
            body = match.group(1)
            mod = re.search(r"mod_id\s*=\s*(\w+)", body)
            setting = re.search(r"setting_id\s*=\s*(\w+)", body)
            if not (mod and setting):
                continue
            line = text[:match.start()].count("\n") + 1
            registered.setdefault(f"{mod.group(1)}__{setting.group(1)}",
                                  f"{path.relative_to(REPO)}:{line}")
        declared.update(re.findall(r"(?m)^(\w+)_on_changed\s*=\s*\{", text))
    return [f"{where}: list setting `{name}` has no `{name}_on_changed` scripted "
            f"GUI -- CMM hides the list and draws its group header anyway, so "
            f"the page shows an empty list rather than a missing one"
            for name, where in sorted(registered.items()) if name not in declared]


def sized_above_datamodel(root: Path) -> list[str]:
    """A `datamodel` with a fixed-size box somewhere above it in the window.

    Every list this repository actually draws hangs under nothing but layout
    policies: `window > vbox > vbox > scrollbox > blockoverride > vbox`. Put a
    box with a real `size = { N M }` anywhere in that chain and the policies
    under it resolve to zero width -- the rows render into nothing while
    everything beside them, headers and counters included, is still correct.
    That reads as an empty list and logs nothing.

    Five builds of the swap window were spent on it, four of them guesses. The
    rule is the measurement: compare the chain, not the look.
    """
    found: list[str] = []
    for path in sorted(root.rglob("*.gui")):
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        text = "\n".join(l.split("#", 1)[0] for l in text.splitlines())
        if "\nwindow = {" not in text:
            continue
        stack: list[tuple[str, bool]] = []
        for number, line in enumerate(text[text.index("\nwindow = {"):].splitlines(), 1):
            stripped = line.strip()
            if "datamodel =" in stripped:
                # The window frame itself is sized, always and rightly; the
                # rule is about the boxes between it and the list.
                sized = [n for n, s in stack[1:] if s]
                if sized:
                    where = f"{path.relative_to(REPO)}"
                    found.append(
                        f"{where}: a datamodel hangs under `{sized[-1]}`, which "
                        f"carries a fixed size -- every list this repo draws has "
                        f"nothing but layout policies above it, and a policy "
                        f"under a sized box resolves to zero width: the rows "
                        f"render into nothing while the headers beside them stay "
                        f"correct")
            opens = stripped.count("{") - stripped.count("}")
            if opens > 0:
                match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*\{", stripped)
                stack.append((match.group(1) if match else "?", False))
            for _ in range(max(0, -opens)):
                if stack:
                    stack.pop()
            # A real size on the box just opened, not on a leaf that closes here.
            if stack and re.match(r"^size\s*=\s*\{\s*\d+\s+\d+\s*\}$", stripped):
                stack[-1] = (stack[-1][0], True)
    return found


def misplaced_values(root: Path) -> list[str]:
    """A script value defined outside `common/script_values`.

    The same silent class as a trigger outside `scripted_triggers`: the engine
    registers a value only from that folder, so one written next to the effects
    that use it reads as zero for ever and logs nothing. It happened twice --
    the swap window's per-building gain, and it would have happened again with
    the coverage pass.

    A value is told from an effect by its body: `value =`, or an arithmetic key
    at the top level of the block, and no effect-only key anywhere in it.
    """
    found: list[str] = []
    for path in sorted(root.rglob("*.txt")):
        parts = set(path.parts)
        if "common" not in parts or "script_values" in parts:
            continue
        if not {"scripted_effects", "scripted_triggers"} & parts:
            continue
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        text = "\n".join(l.split("#", 1)[0] for l in text.splitlines())
        for match in re.finditer(r"(?m)^([a-z_0-9]+) = \{$", text):
            body = text[match.end():_brace_end(text, match.end())]
            if not re.search(r"(?m)^\tvalue = ", body):
                continue
            if re.search(r"(?m)^\t(?:set|change|add_to|remove|clear)_", body):
                continue
            line = text[:match.start()].count("\n") + 1
            found.append(
                f"{path.relative_to(REPO)}:{line}: `{match.group(1)}` looks like "
                f"a script value and does not live in common/script_values -- the "
                f"engine registers one only from there, so this reads as zero "
                f"for ever and says so nowhere")
    return found


def orphan_localization_lists(root: Path) -> list[str]:
    """A localization data function reading a global list nothing fills.

    `GetGlobalList('x')` in a .yml is as much a reader as one in a .gui, and it
    fails the same way -- a count that prints 0 over a list that is plainly not
    empty, because the code moved to another list and the string stayed behind.
    That is exactly what "Можно поставить (0)" was.
    """
    written: set[str] = set()
    for path in sorted(root.rglob("*.txt")):
        if "common" not in set(path.parts):
            continue
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        written.update(re.findall(
            r"(?:add_to|clear)_global_variable_list = \{?\s*(?:name = )?(\w+)", text))
    found: list[str] = []
    for path in sorted(root.rglob("*.yml")):
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        for number, line in enumerate(text.splitlines(), 1):
            for name in re.findall(r"GetGlobalList\('(\w+)'\)", line):
                if name not in written:
                    found.append(
                        f"{path.relative_to(REPO)}:{number}: localization reads "
                        f"`{name}`, and nothing in common/ ever fills it -- the "
                        f"number prints 0 beside a list that is not empty")
    return found


def misplaced_triggers(root: Path) -> list[str]:
    """A block in `scripted_effects/` whose body is nothing but conditions.

    **Это стоило трёх недель тихой поломки.** `bag_wtp_is_food_loc` -- обычный
    триггер из одной строки -- лежал в файле эффектов, потому что генератор
    писал его рядом с эффектом, который им пользуется. Игра в
    `common/scripted_effects` триггеров не заводит: кнопка житницы показывалась
    на каждой локации подряд, `error.log` молчал, а условие переписывали дважды,
    потому что виновным считали его. Владелец, 2026-09-13, во второй раз:
    «кнопка житниц всё так же на всех локациях отображается».

    **Ложные срабатывания невозможны по построению**: эффект, который только
    зовёт другие эффекты, пишет `foo = yes`, и `TRIGGER_ONLY` такую строку не
    пропускает. Флагуется только блок, в котором нет ни одной строки, кроме
    условий.
    """
    found: list[str] = []
    folder = root / "in_game/common/scripted_effects"
    if not folder.is_dir():
        return found
    for path in sorted(folder.glob("*.txt")):
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        for match in re.finditer(r"(?m)^([a-z0-9_]+)\s*=\s*\{", text):
            end = _brace_end(text, match.end() - 1)
            body = text[match.end():end - 1]
            lines = [line for line in body.splitlines() if line.strip()]
            if lines and all(TRIGGER_ONLY.match(line) for line in lines):
                line_no = text[:match.start()].count("\n") + 1
                found.append(
                    f"{path.relative_to(REPO)}:{line_no}: `{match.group(1)}` is a "
                    f"trigger and lives in `scripted_effects/` — the game reads "
                    f"triggers only from `scripted_triggers/`, so every caller "
                    f"of it silently answers something else")
    return found


def unresolved_interface(root: Path) -> list[str]:
    """Every name a window says, checked against the thing that has to define it.

    Five kinds of name, and each one fails the same silent way -- the window
    draws, the cell is empty or the button does nothing, and no log says which:

    - a `text` or `tooltip` key with no localization behind it;
    - a `Custom('x')` with no `customizable_localization` of that name;
    - a `GetScriptedGui('x')` with no scripted GUI of that name;
    - a `GetList` / `GetGlobalList` nothing in `scripted_effects/` ever writes;
    - a key in one language and not the other -- the owner plays in Russian, so
      a key missing there shows on screen as the raw key.

    **This was done by hand three times in one day and caught something every
    time**, the last of them a `\\n` that stayed a backslash and glued two
    localization keys onto one line.
    """
    gui_dir = root / "in_game/gui"
    if not gui_dir.is_dir():
        return []

    def slurp(pattern: str) -> str:
        return "".join(path.read_text(encoding="utf-8-sig")
                       for path in sorted(root.glob(pattern)))

    languages: dict[str, set[str]] = {}
    for folder in sorted((root / "main_menu/localization").glob("*")):
        if not folder.is_dir():
            continue
        keys = set()
        for path in sorted(folder.glob("*.yml")):
            for line in path.read_text(encoding="utf-8-sig").split("\n"):
                match = re.match(r"\s+([A-Za-z0-9_]+):", line)
                if match:
                    keys.add(match.group(1))
        languages[folder.name] = keys
    if not languages:
        return []
    known = set().union(*languages.values())

    # **Only the keys this mod invents.** A mod reuses vanilla keys freely --
    # `rgo_bonus_filter` prints `game_concept_province`, `ru_loc_fix` is nothing
    # but vanilla keys -- and vanilla's own localization is not all in
    # `reference/`, so a name this file cannot find is usually the game's and
    # not a fault. The mod's own prefix is what its keys agree on: `bag_wtp_` for
    # `where_to_produce`. A mod whose keys agree on nothing is a mod that invents
    # none, and there is nothing here to check in it.
    # **The prefix most of the keys share, not the one all of them do.** The
    # common prefix of every key is empty the moment a mod defines one key that
    # does not fit -- `where_to_produce` has `mapmode_bag_wtp_*` beside its 345
    # `bag_wtp_*` -- and this returned nothing at all for it, which is the exact
    # failure this file exists to catch. So: the leading segment a majority of
    # the keys agree on, and no check at all when they agree on nothing.
    heads: dict[str, int] = {}
    for key in known:
        head = key.split("_")[0]
        heads[head] = heads.get(head, 0) + 1
    head, count = max(heads.items(), key=lambda pair: pair[1]) if heads else ("", 0)
    if len(head) < 2 or count * 2 < len(known):
        return []
    prefix = head + "_"
    mine = {key for key in known if key.startswith(prefix)}

    custom = set(re.findall(r"^(\w+) = \{",
                            slurp("in_game/common/customizable_localization/*.txt"), re.M))
    guis = set(re.findall(r"^(\w+) = \{",
                          slurp("in_game/common/scripted_guis/*.txt"), re.M))
    effects = slurp("in_game/common/scripted_effects/*.txt")

    found = []
    for path in sorted(gui_dir.glob("*.gui")):
        text = path.read_text(encoding="utf-8-sig")
        where = path.relative_to(REPO)
        for name in sorted(set(re.findall(
                r'(?:text|tooltip)\s*=\s*"([a-z][A-Za-z0-9_]*)"', text))):
            if name.startswith(prefix) and name not in mine:
                found.append(f"{where}: `{name}` on a widget, and no localization "
                             f"defines it — the key itself draws on screen")
        for name in sorted(set(re.findall(r"Custom\('(\w+)'\)", text))):
            if name not in custom:
                found.append(f"{where}: `Custom('{name}')`, and no "
                             f"customizable_localization of that name — the cell "
                             f"comes out empty")
        for name in sorted(set(re.findall(r"GetScriptedGui\('(\w+)'\)", text))):
            if name not in guis:
                found.append(f"{where}: `GetScriptedGui('{name}')`, and no "
                             f"scripted GUI of that name — the button does nothing")
        for name in sorted(set(re.findall(r"Get(?:Global)?List\('(\w+)'\)", text))):
            if name not in effects:
                found.append(f"{where}: the datamodel reads `{name}`, and nothing "
                             f"in scripted_effects/ ever writes it — the list is "
                             f"always empty")
    # **A global variable map nothing writes.** The interface reads one through
    # `GetVariableFromGlobalVariableMap('name', ...)`, in a `.gui` or inside a
    # localization value, and a name nothing ever writes returns an unset scope:
    # the number comes out blank and the `visible` that reads it is false for
    # ever. `bag_wtp_held` is read only from localization, so looking in the
    # `.gui` alone would have missed it.
    written_maps = set(re.findall(r"name = (\w+) key = ", effects))
    for where, text in ([(path.relative_to(REPO), path.read_text(encoding="utf-8-sig"))
                         for path in sorted(gui_dir.glob("*.gui"))]
                        + [(path.relative_to(REPO), path.read_text(encoding="utf-8-sig"))
                           for path in sorted((root / "main_menu/localization").glob("*/*.yml"))]):
        for name in sorted(set(re.findall(
                r"GetVariableFromGlobalVariableMap\('(\w+)'", text))):
            if name.startswith(prefix) and name not in written_maps:
                found.append(f"{where}: reads the variable map `{name}`, and "
                             f"nothing in scripted_effects/ ever writes it — the "
                             f"value comes back unset every time")

    # Custom localizations point at keys of their own.
    for name in sorted(set(re.findall(r"localization_key = (\S+)",
                                      slurp("in_game/common/customizable_localization/*.txt")))):
        if name.startswith(prefix) and name not in mine:
            found.append(f"{root.name}: a customizable_localization points at "
                         f"`{name}`, and no localization defines it")
    # **English against Russian, and no other pair.** He plays in Russian, and
    # `CLAUDE.md` says what that costs: a key missing there shows on screen as
    # the raw key. Every other language a mod ships is somebody else's promise --
    # `glorpui_hints` carries seven and translates into some of them partly, and
    # comparing all pairs turned that into 7 560 findings that are not faults.
    english, russian = languages.get("english"), languages.get("russian")
    if english and russian:
        for name in sorted((english - russian) & mine):
            found.append(f"{root.name}: `{name}` is in english and not in "
                         f"russian — a missing key draws as itself on screen, "
                         f"and he plays in Russian")
    return found


def unregistered_windows(root: Path) -> list[str]:
    """A `window` in a .gui that no `scripted_widgets` file names.

    **The game does not create a window because it is there.** It creates the
    ones a `gui/scripted_widgets/*.txt` line points at, `gui/<file>.gui = <name>`,
    and it says nothing at all about the rest: no parse error, no missing type,
    no line in `error.log` — the file simply is not asked for. That cost a whole
    round trip on 2026-09-03. Two new windows were written, checked, localized,
    wired to their buttons and shipped; the button's effect logged that it ran,
    the .gui had no error of any kind, and nothing appeared. The registry was in
    the same folder the whole time.

    The name in the registry has to match the window's own `name`, because that
    is what the engine looks the widget up by.
    """
    gui = root / "in_game/gui"
    if not gui.is_dir():
        return []
    registered: dict[str, str] = {}
    for path in sorted((gui / "scripted_widgets").glob("*.txt")):
        for line in path.read_text(encoding="utf-8-sig").split("\n"):
            line = line.split("#")[0].strip()
            if "=" not in line:
                continue
            where, name = (part.strip() for part in line.split("=", 1))
            registered[where] = name
    found = []
    for path in sorted(gui.glob("*.gui")):
        text = path.read_text(encoding="utf-8-sig")
        # A top-level `window = {` and its `name`. Only the first is asked for:
        # every window in this repository is one file, and a second in the same
        # file could not be registered separately anyway.
        if not re.search(r"^window = \{", text, re.M):
            continue
        match = re.search(r'^window = \{[^}]*?name = "([^"]+)"', text, re.M | re.S)
        name = match.group(1) if match else None
        key = f"gui/{path.name}"
        where = f"{path.relative_to(REPO)}"
        if key not in registered:
            found.append(f"{where}: a window nothing registers — add "
                         f"`{key} = {name or path.stem}` to "
                         f"in_game/gui/scripted_widgets/, or the game never "
                         f"creates it and says so nowhere")
        elif name and registered[key] != name:
            found.append(f"{where}: registered as `{registered[key]}` but the "
                         f"window is named `{name}` — the engine looks it up by "
                         f"the name and finds nothing")
    return found


def flowcontainer_datamodels(root: Path) -> list[str]:
    """A `flowcontainer` that carries a `datamodel` of its own.

    **This is the widget that cost four crashes and five of the owner's runs.**
    The editor's picker wrapped on a `flowcontainer` with `wrap_count` and
    `datamodel = "[GetGlobalList('bag_wtp_edit_pool')]"`. Every build that had
    one died — two on opening the window, one on opening it with a CMM switch
    that was supposed to save it, one on loading the game at all — and every
    build without one opened. Nothing was ever written to `error.log`, `gui.log`
    or `debug.log`: a native layout failure logs nothing, so four sessions went
    to four different theories about the *contents* of the window instead.

    **The game's own files say it plainly.** Search vanilla for a `flowcontainer`
    with a real datamodel on it and there is none. The two `wrap_count` pickers
    (`agenda_view.gui`, `multiplayer_lobby.gui`) hold literal children, and where
    a flowcontainer does get a `datamodel` it is `DataModelRepeatedItem(N)` — a
    counter, not a list. A wrapping grid **of a list** is a `fixedgridbox`, all
    138 times the game draws one: `addcolumn`, `addrow`, `datamodel_wrap`,
    `flipdirection = yes`.

    So this refuses the pairing rather than the widget. A `flowcontainer` of
    literal children is fine and stays fine.
    """
    gui = root / "in_game/gui"
    if not gui.is_dir():
        return []
    found = []
    for path in sorted(gui.rglob("*.gui")):
        text = path.read_text(encoding="utf-8-sig")
        # Walk to the matching brace so a datamodel in a *child* widget does not
        # count: only the flowcontainer's own block is asked about.
        for match in re.finditer(r"\bflowcontainer\s*=\s*\{", text):
            depth, i = 0, match.end() - 1
            while i < len(text):
                if text[i] == "{":
                    depth += 1
                elif text[i] == "}":
                    depth -= 1
                    if depth == 0:
                        break
                i += 1
            block = text[match.end():i]
            own = re.sub(r"\{[^{}]*\}", "", block)
            for _ in range(8):
                own = re.sub(r"\{[^{}]*\}", "", own)
            model = re.search(r'datamodel\s*=\s*"([^"]*)"', own)
            if not model or "DataModelRepeatedItem" in model.group(1):
                continue
            line = text[:match.start()].count("\n") + 1
            found.append(
                f"{path.relative_to(REPO)}:{line}: a `flowcontainer` with a "
                f"datamodel of its own — the game has none and four builds of "
                f"this repository crashed on one, silently. A wrapping grid of "
                f"a list is a `fixedgridbox` (addcolumn/addrow/datamodel_wrap/"
                f"flipdirection); docs/pitfalls/interface.md")
    return found


def scope_mixed_variables(root: Path) -> list[str]:
    """A name written as a global and read as a location's own, or the reverse.

    **This is what three builds of the plan editor died on.** `_edit_good` was
    written with `set_variable` in a country-scoped effect and read with `var:`
    twice: once at country scope, where it worked, and once inside
    `ordered_in_global_list`, where the scope is the location the walk stands on
    and the variable simply is not there. Every «+1» evicted a building, failed
    to place, and put the victim back -- and nothing said why until the numbers
    went into the report: `evicted=1 room=1 | placed_before=191 placed_after=192`
    with `done=0 fail=1`.

    Reading a variable that is not on the scope is not an error the game raises.
    It is a condition that is quietly false, forever, which is the failure this
    repository names first.

    So: a name only ever written globally must never be read as `var:`, and a
    name only ever written on a scope must never be read as `global_var:`. A name
    written both ways is deliberate (the plan keeps a few) and is left alone.
    """
    written_global: dict[str, str] = {}
    written_local: dict[str, str] = {}
    read_global: dict[str, str] = {}
    read_local: dict[str, str] = {}
    for path in sorted((root / "in_game/common").rglob("*.txt")):
        where = f"{path.relative_to(REPO)}"
        for n, line in enumerate(path.read_text(encoding="utf-8-sig").split("\n"), 1):
            code = line.split("#")[0]
            for m in re.finditer(r"(set|change)_global_variable\s*=\s*\{\s*name\s*=\s*(\w+)", code):
                written_global.setdefault(m.group(2), f"{where}:{n}")
            for m in re.finditer(r"(?<!global_)(?:set|change)_variable\s*=\s*\{\s*name\s*=\s*(\w+)", code):
                written_local.setdefault(m.group(1), f"{where}:{n}")
            for m in re.finditer(r"global_var:(\w+)", code):
                read_global.setdefault(m.group(1), f"{where}:{n}")
            for m in re.finditer(r"(?<![_a-z])var:(\w+)", code):
                read_local.setdefault(m.group(1), f"{where}:{n}")
    found = []
    for name, at in sorted(read_local.items()):
        if name in written_global and name not in written_local:
            found.append(f"{at}: `var:{name}` reads as the scope's own, but "
                         f"{name} is only ever written with set_global_variable "
                         f"({written_global[name]}) — the read is silently false")
    for name, at in sorted(read_global.items()):
        if name in written_local and name not in written_global:
            found.append(f"{at}: `global_var:{name}` reads a global, but {name} "
                         f"is only ever written on a scope "
                         f"({written_local[name]}) — the read is silently false")
    return found


def localization_markup(root: Path) -> list[str]:
    """Markup and glyphs in a localization value that this game cannot draw.

    **Two of these have already reached his screen.** A `✔` came back an empty
    box, and every `§Y…§!` in the mod was the previous engine's colour markup —
    100 of them, including the yellow that marks a pinned good. Neither is an
    error: the game draws the box, or prints the marker literally, and the run
    that finds it is his.

    The rule is measured, not guessed. **This game's own Russian localization
    uses `#Y …#!` 660 times and `#!` 37 259 times, and contains no `§` at all**;
    it also contains `×` and `−`, which is exactly why those two render in the
    picker's buttons. So: `§` is always wrong, and a character the game never
    uses anywhere is a gamble that costs a round trip.

    **A checkmark is not unavailable — it is a texture.** The game's own context
    menus draw one with `gfx/interface/buttons/flats/accept.dds`, its checkboxes
    with `gfx/interface/buttons/checkbox_round.dds` and `frame_grid = { 2 1 }`,
    and any mod may declare a `texticon` over a texture the way Glorp UI and
    Construction Manager both do. Reach for one of those rather than a third
    character.
    """
    GLYPHS = "✔✓√☑✗✘☒●■▪◆★☆♦♣♠♥•‣▶◀"
    found = []
    for path in sorted(root.rglob("main_menu/localization/*/*.yml")):
        for number, line in enumerate(
                path.read_text(encoding="utf-8-sig").split("\n"), start=1):
            if "§" in line:
                found.append(
                    f"{path.relative_to(REPO)}:{number}: `§` is the previous "
                    f"engine's markup — this game uses `#Y …#!` (660 times in "
                    f"its own Russian localization, and not one `§`), so this "
                    f"prints literally; docs/pitfalls/localization.md")
            bad = [c for c in GLYPHS if c in line]
            if bad:
                found.append(
                    f"{path.relative_to(REPO)}:{number}: {''.join(bad)} — the "
                    f"game's own localization never uses these and `✔` came "
                    f"back an empty box in game. A check or a cross is a "
                    f"texture (`buttons/flats/accept.dds`) or a widget, not a "
                    f"character; docs/pitfalls/localization.md")
    return found


def overflowing_windows(root: Path) -> list[str]:
    """A window whose widest row is wider than the box the window declares.

    **This is the fault the owner reported as «шапка не растягивается».** She
    does not lag: the header, the background and the close button are the only
    things still drawn at the declared size, and everything else has grown past
    it. `allow_outside = yes` on the window's background is what lets the rest
    spill -- and it cannot simply be removed, because the close button is placed
    at `parentanchor = right` with `position = { -5 5 }` and hangs 35px outside
    the frame *on purpose*, exactly as the game's own `lateralview_topbuttons`
    does. So the box has to grow to the content instead.

    It had drifted five times before anyone measured it. `bag_wtp_plan_window`
    declared 1180 and its button row summed to 1524 -- four 128px buttons, a
    190px readout, three 150px buttons, a 300px save block and eight 8px gaps --
    which is the third the screenshot showed. Nothing logs any of this: a child
    drawn outside its parent is not an error, it is a layout.

    So the number is checked rather than remembered. **The measurement is a
    lower bound**: a child whose width comes from a type defined elsewhere
    counts as zero, so a row can be wider than this says and never narrower. A
    box that clears the bound can still be too small; a box that does not is
    certainly too small, and that is the half worth failing on.

    **`SLACK` is subtracted from the box, not added to it**, and getting that
    backwards is what let the fault through a sixth time. The window's own margin
    and its scrollbar take width *away* from what a row may use, so a row is
    allowed `width - SLACK` and not `width + SLACK`. Under the old direction
    `bag_wtp_edit_window` sat at 1500 with a 1544 row and passed: the frame ended
    44px before the sheet, and the owner reported it as the header again --
    «рамка всего окна вместе с шапкой не увеличивается, а содержимое выходит за
    пределы рамки в правую сторону», 2026-09-06, which is the first description
    of it that named the right thing.

    `window_margin_alt` is a game template this repository has no copy of, so the
    figure is an allowance and not a measurement -- deliberately small, because
    the margin it stands for is small and the check is now the strict side.
    """
    SLACK = 40
    gui = root / "in_game/gui"
    if not gui.is_dir():
        return []
    types = _gui_types(gui)
    found = []
    for path in sorted(gui.rglob("*.gui")):
        text = _gui_text(path)
        for match in re.finditer(r"^window\s*=\s*\{", text, re.M):
            body = text[match.end():_brace_end(text, match.end() - 1)]
            name = re.search(r'name\s*=\s*"([^"]+)"', body)
            box = re.search(r"size\s*=\s*\{\s*(\d+)\s+(\d+)", body)
            if not box:
                continue
            width = int(box.group(1))
            # **The same number is typed twice in every one of these windows**:
            # once on the window and once on the background widget that carries
            # `bg_window_default_alt`. They are the frame and the thing drawn in
            # it, and when they disagree the window is one size and its
            # background another -- which reads on screen as the header being
            # the wrong width, the very complaint this check was written for.
            sizes = [int(m.group(1)) for m in
                     re.finditer(r"size\s*=\s*\{\s*(\d+)\s+\d+\s*\}", body)]
            inner = re.search(r"widget\s*=\s*\{[^{}]*size\s*=\s*\{\s*(\d+)\s+\d+\s*\}"
                              r"[^{}]*using\s*=\s*bg_window_", body)
            if inner and int(inner.group(1)) != width:
                line = text[:match.end()].count("\n") + 1
                found.append(
                    f"{path.relative_to(REPO)}:{line}: "
                    f"{name.group(1) if name else 'window'} is "
                    f"size = {{ {width} ... }} but its background widget is "
                    f"{{ {inner.group(1)} ... }} — the frame and what is drawn "
                    f"in it must be one number; docs/pitfalls/interface.md")
            rows = _widest_rows(body, known=types)
            if not rows:
                continue
            worst, line_off = max(rows)
            if worst <= width - SLACK:
                continue
            line = text[:match.end() + line_off].count("\n") + 1
            found.append(
                f"{path.relative_to(REPO)}:{line}: "
                f"{name.group(1) if name else 'window'} declares "
                f"size = {{ {width} ... }} and holds a row at least {worst} wide "
                f"— with {SLACK} for the margin and the scrollbar a row may use "
                f"{width - SLACK}. The content spills past the frame through "
                f"`allow_outside`, and the frame is what stays at the declared "
                f"size. Widen the box or narrow the row; "
                f"docs/pitfalls/interface.md")
    return found


def frameless_windows(root: Path) -> list[str]:
    """A window that draws no frame, and a frame drawn on something that is not one.

    **The frame is one line and its absence is silent.** `using =
    bg_window_default_alt` on the `window` is what paints the border, the header
    ground and the sheet; without it the window still opens, still works, and has
    no edges at all. On 2026-09-06 a script meant to move that line onto the
    window put it on the first `size = {` line in the file instead — which in four
    of the five files belongs to a *type* declared above the window — and three
    windows lost their frame while a goods cell gained one. He found all four.

    So both halves are checked: every `window` carries the line, and nothing that
    is not a `window` does.
    """
    gui = root / "in_game/gui"
    if not gui.is_dir():
        return []
    found = []
    for path in sorted(gui.rglob("*.gui")):
        text = _gui_text(path)
        for match in re.finditer(r"^window\s*=\s*\{", text, re.M):
            body = text[match.end():_brace_end(text, match.end() - 1)]
            name = re.search(r'name\s*=\s*"([^"]+)"', body)
            # **The window's own line, at its own indentation.** Splitting the
            # body at "the first child" does not work: `size = { 1320 900 }` is a
            # property and looks exactly like a block opening.
            if re.search(r"^\tusing = bg_window_default_alt\s*$", body, re.M):
                continue
            line = text[:match.end()].count("\n") + 1
            found.append(
                f"{path.relative_to(REPO)}:{line}: "
                f"{name.group(1) if name else 'window'} carries no "
                f"`using = bg_window_default_alt` — it opens with no frame at all, "
                f"and nothing logs that; docs/pitfalls/interface.md")
        for match in re.finditer(r"^\ttype (\w+) = ", text, re.M):
            body = text[match.end():_brace_end(text, text.index("{", match.end()))]
            if "bg_window_default_alt" not in body:
                continue
            line = text[:match.start()].count("\n") + 1
            found.append(
                f"{path.relative_to(REPO)}:{line}: type `{match.group(1)}` carries "
                f"`using = bg_window_default_alt` — that is a window's frame, and "
                f"a type wearing it is a line that landed in the wrong place")
    return found


def _gui_text(path: Path) -> str:
    """The file with its comments removed, so a `#` note never reads as script."""
    out = []
    for line in path.read_text(encoding="utf-8-sig").split("\n"):
        quoted = False
        for i, ch in enumerate(line):
            if ch == '"':
                quoted = not quoted
            elif ch == "#" and not quoted:
                line = line[:i]
                break
        out.append(line)
    return "\n".join(out)


def _brace_end(text: str, start: int) -> int:
    depth, i = 0, start
    while i < len(text):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return len(text)


def _gui_children(block: str) -> list[tuple[str, str, int]]:
    """Every `keyword = { ... }` one level down, with its offset in `block`."""
    out, i = [], 0
    while i < len(block):
        match = re.compile(r"(\w+)\s*=\s*\{").search(block, i)
        if not match:
            break
        end = _brace_end(block, match.end() - 1)
        out.append((match.group(1), block[match.end():end], match.start()))
        i = end + 1
    return out


def _gui_types(gui: Path) -> dict[str, int]:
    """Every `type <name> = ...` a mod declares, and how wide it draws.

    **A window's row can be a type from another file, and then the window's own
    text says nothing about its width.** `bag_wtp_edit_window` draws five
    `bag_wtp_edit_row<n>`, each declared in `bag_wtp_edit_cells.gui`; adding one
    control to a cell widened those rows by 270 and the window's `.gui` did not
    change by a character. Without this the overflow check reads such a row as
    zero and passes a window a fifth too small -- the same silent overflow it
    exists to catch, arriving through the one door left open.

    A type built on an `hbox` measures as a row; any other measures by the size
    it declares. Types that draw types settle over a few passes, capped, so a
    cycle cannot hang the check.
    """
    declared: dict[str, tuple[str, str]] = {}
    for path in sorted(gui.rglob("*.gui")):
        text = _gui_text(path)
        for match in re.finditer(r"\btype\s+(\w+)\s*=\s*(\w+)\s*\{", text):
            declared[match.group(1)] = (
                match.group(2), text[match.end():_brace_end(text, match.end() - 1)])
    known: dict[str, int] = {}
    for _ in range(4):
        for name, (kind, body) in declared.items():
            if kind == "hbox":
                # Wrapped as an `hbox` so the type's own body is summed as a
                # row: wrapping it under any other keyword measures only the
                # rows *inside* it, which read the picker's 1328-wide row as one
                # 128-wide cell and let a window 160 too small pass.
                rows = _widest_rows("hbox = {%s}" % body, known=known)
                known[name] = max((w for w, _ in rows), default=0)
            else:
                known[name] = _declared_width(body)
    return known


def _declared_width(body: str) -> int:
    """What a child says it is wide, reading nothing from its own children.

    Only a `size` or `minimumsize` at the child's own brace depth counts;
    the same words inside a descendant are that descendant's business. Depth is
    counted rather than cut at the first `{`, because `size = { 128 34 }` opens
    a brace itself -- reading up to it measured every widget in the mod as zero
    the first time this was written, and the check passed a window whose row was
    a third too wide.

    A width of `-1` is «take whatever is left», which in a row that is already
    overfull is nothing, so it counts as zero.
    """
    depth, i, best = 0, 0, 0
    while i < len(body):
        ch = body[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        elif depth == 0:
            match = re.compile(r"(size|minimumsize)\s*=\s*\{\s*(-?\d+)").match(body, i)
            if match:
                best = max(best, int(match.group(2)))
                i = match.end()
                continue
        i += 1
    return max(best, 0)


def _widest_rows(block: str, base: int = 0,
                 known: dict[str, int] | None = None) -> list[tuple[int, int]]:
    """Every `hbox`'s summed width, with the offset it sits at.

    A child that sizes itself is taken at its word; one that does not, but names
    a type the mod declares, is taken at that type's width.
    """
    known = known or {}
    rows = []
    for keyword, body, offset in _gui_children(block):
        # **A type is a row wherever it is drawn, not only inside an `hbox`.**
        # The picker's five rows are `bag_wtp_edit_row<n> = {}` in a `vbox`, so
        # nothing sums them and their width is the type's own. Missing this let
        # a window 160 too narrow pass the check that exists for exactly that.
        if keyword in known and not _declared_width(body):
            rows.append((known[keyword], offset))
        if keyword == "hbox":
            kids = _gui_children(body)
            total = sum(_declared_width(b) or known.get(k, 0) for k, b, _ in kids)
            gap = re.search(r"spacing\s*=\s*(\d+)", body[:body.find("{")]
                            if "{" in body else body)
            if gap and len(kids) > 1:
                total += int(gap.group(1)) * (len(kids) - 1)
            rows.append((total, base + offset))
        rows.extend(_widest_rows(body, base + offset, known))
    return rows


# **Файлы, которые два мода возят побайтово одинаковыми, и почему.**
#
# `rgo_bonus_filter` и `where_to_produce` оба перекрывают панель производства
# локации: обоим нужен один и тот же факт -- какую локацию она показывает, --
# а донести его до фильтра можно только глобалкой, которую пишет виджет внутри
# самой панели. Два разных перекрытия одного окна -- это молчаливая пропажа:
# кто загрузился последним, тот и унёс пробу другого.
#
# Поэтому проба одна, под именами, не принадлежащими ни одному из модов, и оба
# мода возят её копию. Разойдутся копии -- вернётся ровно та же пропажа, только
# теперь её никто не заметит, потому что «у меня же есть этот файл».
SHARED_COPIES = (
    ("in_game/gui/location_production_lateralview.gui",
     ("rgo_bonus_filter", "where_to_produce")),
    ("in_game/common/scripted_guis/bag_shared_view_location.txt",
     ("rgo_bonus_filter", "where_to_produce")),
)


# Перенесённые из чужого мода разборы: их можно рисовать в перенесённом окне и
# нельзя в своём. Ключ -> файл, в котором он законен.
FOREIGN_BREAKDOWNS = (
    ("bag_wtp_trmm_ur_rank_", "bag_wtp_trmm_l_"),
    ("bag_wtp_trmm_bd_slot_", "bag_wtp_trmm_l_"),
    ("bag_wtp_trmm_slot_", "bag_wtp_trmm_l_"),
)


def unresolved_localization_refs(root: Path) -> list[str]:
    """`$ключ$` без ключа и `Custom('имя')` без `customizable_localization`.

    **Две формы, которые легко перепутать, и обе молчат.** `$x$` подставляет
    другой ключ локализации, `[Scope.Custom('x')]` зовёт
    `customizable_localization` -- и если взять не ту, на экране окажется имя
    ключа или пустота. Дважды за один день: строка товара переезжала между
    двумя формами, и оба раза это было видно только в игре.

    Ключи ищутся и в моде, и в игровом дереве (`$ключ$` часто указывает на
    ванильный), а `Custom()` -- только среди своих: чужие определения лежат в
    модах, которых в `reference/` может не быть.
    """
    keys: set[str] = set()
    for folder in (root / "main_menu/localization",
                   REPO / "reference/game/main_menu/localization",
                   REPO / "reference/mods"):
        if not folder.is_dir():
            continue
        for path in folder.rglob("*.yml"):
            for line in path.read_text(encoding="utf-8-sig",
                                       errors="ignore").splitlines():
                match = re.match(r"\s*([A-Za-z0-9_.]+):\s*", line)
                if match:
                    keys.add(match.group(1))
    custom: set[str] = set()
    folder = root / "in_game/common/customizable_localization"
    if folder.is_dir():
        for path in folder.glob("*.txt"):
            custom |= set(re.findall(r"^(\w+)\s*=\s*\{",
                                     path.read_text(encoding="utf-8-sig"), re.M))
    found: list[str] = []
    seen: set[tuple[str, str]] = set()
    prefix = root.name and "bag_"
    for path in sorted(list((root / "main_menu/localization").rglob("*.yml"))
                       + list((root / "in_game/gui").rglob("*.gui"))):
        text = path.read_text(encoding="utf-8-sig", errors="ignore")
        for name in re.findall(r"\$([A-Za-z0-9_.]+)\$", text):
            # `$ВЕРХНИМ_РЕГИСТРОМ$` -- это параметр, который подставляет
            # позвавший, а не ссылка на ключ. Ключи здесь и у игры пишутся
            # строчными.
            if name.upper() == name:
                continue
            if name not in keys and (path.name, name) not in seen:
                seen.add((path.name, name))
                found.append(f"{path.relative_to(REPO)}: `${name}$` — такого "
                             f"ключа локализации нет ни у мода, ни у игры")
        for name in re.findall(r"Custom\('([A-Za-z0-9_]+)'\)", text):
            if name.startswith(prefix) and name not in custom \
                    and (path.name, name) not in seen:
                seen.add((path.name, name))
                found.append(f"{path.relative_to(REPO)}: `Custom('{name}')` — "
                             f"нет такого `customizable_localization`; ключ "
                             f"локализации подставляется через `${name}$`")
    return found


def foreign_breakdown_in_own_text(root: Path) -> list[str]:
    """Наш текст, рисующий разбор чужого расчёта.

    **Столбец считает одно, подсказка под ним рисует другое.** «Пригодность»
    считалась нашим `_rq<k>` -- по способам, доступным державе, -- а подсказка
    под ней звала `_trmm_ur_rank_bd_slot_*`, разбор перенесённой карты, который
    про эпоху не знает вовсе. На экране владельца 2026-09-14 стояли 76.1 % и
    236.1 % разом; в окне плана то же самое назвало лучшей грамотой не ту,
    которую раздача выдала. Сойтись эти два числа не могли ни при каких данных.

    Правило: перенесённый разбор рисует перенесённое окно. В своём тексте
    (`bag_wtp_l_<язык>.yml`) его быть не должно -- у своего расчёта свой разбор.
    """
    found: list[str] = []
    for path in sorted(root.rglob("*.yml")):
        name = path.name
        for key, allowed_prefix in FOREIGN_BREAKDOWNS:
            if allowed_prefix in name or key not in path.read_text(
                    encoding="utf-8-sig", errors="ignore"):
                continue
            found.append(
                f"{path.relative_to(REPO)}: рисует `{key}*` — разбор чужого "
                f"расчёта в своём тексте; у столбца и его подсказки обязан быть "
                f"один счёт")
    return found


def stale_overrides(root: Path) -> list[str]:
    """A full-file copy of a vanilla `.gui` that no longer carries all of it.

    **Идея взята у Community Mod Toolkit** (`tools/gui_update.py` в их ветке
    `dev`, 2026-08-31): мод, который кладёт свой файл на место игрового,
    заменяет его целиком, и когда игра патчит этот файл, добавленное патчем
    просто исчезает из игры -- молча, без строчки в логе. У них это целая
    машинерия на двух гит-ветках с трёхсторонним слиянием; нам столько не надо,
    потому что игровое дерево у нас и так лежит в `reference/` -- достаточно
    сверить состав.

    Сверяется состав верхнего уровня: блоки `имя = {{` и `types Имя {{`. Имя,
    которое есть у игры и которого нет у нас, -- это окно или набор типов,
    которого в игре больше не будет. Сверять построчно смысла нет: мод затем и
    правит файл, чтобы он отличался.
    """
    found: list[str] = []
    for path in sorted(root.rglob("*.gui")):
        rel = path.relative_to(root)
        original = REPO / "reference" / "game" / rel
        if not original.is_file():
            continue
        theirs = _top_level_names(original)
        ours = _top_level_names(path)
        for name in sorted(theirs - ours):
            found.append(f"{path.relative_to(REPO)}: пропал `{name}` — файл "
                         f"кладётся поверх игрового целиком, значит этого блока "
                         f"в игре не будет вовсе; он есть в "
                         f"{original.relative_to(REPO)}")
    return found


def _top_level_names(path: Path) -> set[str]:
    """Имена блоков нулевого уровня в `.gui`: `имя = {{` и `types Имя {{`."""
    names: set[str] = set()
    depth = 0
    pending: str | None = None
    for line in _gui_text(path).splitlines():
        if depth == 0:
            match = (re.match(r"\s*(\w[\w.]*)\s*=\s*\{", line)
                     or re.match(r"\s*types\s+(\w+)\s*\{", line))
            if match:
                pending = match.group(1)
        opened = line.count("{") - line.count("}")
        if depth == 0 and opened > 0 and pending:
            names.add(pending)
            pending = None
        depth += opened
    return names


def shared_copies() -> list[str]:
    """Одинаковые файлы двух модов -- одинаковы ли они на самом деле."""
    found: list[str] = []
    for name, mods in SHARED_COPIES:
        paths = [REPO / "mods" / mod / name for mod in mods]
        missing = [p for p in paths if not p.is_file()]
        if missing:
            for p in missing:
                found.append(f"{p.relative_to(REPO)}: общая копия пропала — "
                             f"её возят оба мода, {' и '.join(mods)}")
            continue
        first = paths[0].read_bytes()
        for other in paths[1:]:
            if other.read_bytes() != first:
                found.append(f"{other.relative_to(REPO)}: разошлась с "
                             f"{paths[0].relative_to(REPO)} — общая проба должна "
                             f"быть побайтово одинаковой в обоих модах, иначе "
                             f"порядок загрузки решает, чья останется")
    return found


def main(argv: list[str]) -> int:
    roots = [Path(a) for a in argv[1:]] or sorted((REPO / "mods").iterdir())
    known = known_names()
    total = 0
    if not argv[1:]:
        shared = shared_copies()
        total += len(shared)
        for line in shared:
            print(line)
    for root in roots:
        if not root.is_dir():
            continue
        root = root if root.is_absolute() else REPO / root
        found = (problems(root) + unresolved(root, known) + unwritten(root)
                 + misplaced_triggers(root)
                 + listless_callbacks(root)
                 + sized_above_datamodel(root)
                 + misplaced_values(root)
                 + orphan_localization_lists(root)
                 + unresolved_script_values(root)
                 + duplicate_definitions(root)
                 + frameless_windows(root)
                 + unregistered_windows(root) + unresolved_interface(root)
                 + flowcontainer_datamodels(root)
                 + scope_mixed_variables(root)
                 + overflowing_windows(root)
                 + localization_markup(root)
                 + stale_overrides(root)
                 + foreign_breakdown_in_own_text(root)
                 + unresolved_localization_refs(root))
        total += len(found)
        for line in found:
            print(line)
    checked = ", ".join(r.name for r in roots if r.is_dir())
    print(f"{checked}: {'clean' if not total else f'{total} problem(s)'}")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
