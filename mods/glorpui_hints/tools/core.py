#!/usr/bin/env python3
"""Privileges, government reforms and policies that push a societal value.

These are the three kinds a country actually *takes*, and the bulk of every
list. Until 2026-10-03 they came from Glorp UI's generated files, copied or
forked; Glorp UI did not regenerate them for game 1.4, so the fifteen
privileges and fourteen reforms 1.4 added were in nobody's list. Since then
they are read here, from the game's own `common/`, every build.

Each line carries two gates, both country-scope triggers:

* **now** — the country can take it today. The same rules Glorp UI's generator
  used, which were in game since August: `is_implementable_in` and not already
  in force (the `svx_*_core` scripted triggers), `is_locked_for` where the
  object supports it, the reform's own `government` and `age`, the estate the
  privilege belongs to, and for a policy its law's and its own `potential` and
  every stronger policy of the same law already in force. Run against game 1.3,
  this picks exactly Glorp UI's 725 lines, no more and no fewer.
* **soon** — the country could get it, but not today: the object's own
  `potential`, and the advance that unlocks it either researched or open to this
  country. Listed under the game's own «not yet available» title.

A `potential` is copied verbatim, and only when it is written against the
country alone; one that reaches for `scope:`, `prev` or an organization's type
is left out, which makes the «soon» gate looser rather than wrong.
"""

from __future__ import annotations

import re
from pathlib import Path

import pdx

AXIS = re.compile(r"^monthly_towards_([a-z_]+)$")
FOREIGN_SCOPE = re.compile(r"\bscope:|\bprev\b|\bPREV\b|\bfrom\b|\bFROM\b|international_organization_type")

# Keys of a law block that are not policies.
LAW_FIELDS = {"potential", "allow", "locked", "custom_tags", "law_category", "type",
              "requires_vote", "unique", "law_country_group", "law_gov_group",
              "law_religion_group", "law_culture_group"}


def steps(game: Path) -> dict[str, float]:
    """`societal_value_*_move = 0.1` and the rest, as the game defines them."""
    found = {}
    for path in (game / "main_menu/common/script_values").glob("*.txt"):
        for match in re.finditer(r"^(societal_value_\w+)\s*=\s*(-?[\d.]+)",
                                 path.read_text(encoding="utf-8-sig"), re.M):
            found[match.group(1)] = float(match.group(2))
    return found


def amount(raw: str, known: dict[str, float]) -> float | None:
    if raw in known:
        return known[raw]
    try:
        return float(raw)
    except ValueError:
        return None


def pushes(block: list, known: dict[str, float]) -> dict[str, tuple[float, bool]]:
    """axis -> (value, up_to) for every `monthly_towards_*` under a block.

    An object that pushes one axis from several modifiers — a policy with one
    modifier for the organization's leader and another for its members — gets
    the largest, marked as a ceiling.
    """
    found: dict[str, list[float]] = {}
    for _, entry in pdx.walk(block):
        match = AXIS.match(entry.key)
        if not match:
            continue
        value = amount(entry.value, known)
        if value is not None and value > 0:
            found.setdefault(match.group(1), []).append(value)
    return {axis: (max(values), len(set(values)) > 1) for axis, values in found.items()}


def own_trigger(block) -> str | None:
    """A trigger block as one line, or None when it is empty or not the country's."""
    if not block or not isinstance(block, list):
        return None
    line = pdx.text(block)
    if not line.strip() or FOREIGN_SCOPE.search(line):
        return None
    return line


class Advances:
    """Which advance unlocks what, and what it takes to have that advance."""

    def __init__(self, game: Path):
        self.unlocks: dict[tuple[str, str], list[str]] = {}
        self.potential: dict[str, str | None] = {}
        self.age: dict[str, str] = {}
        for name, (block, _) in pdx.objects(game / "in_game/common/advances").items():
            self.potential[name] = own_trigger(pdx.get(block, "potential"))
            age = pdx.get(block, "age")
            if isinstance(age, str):
                self.age[name] = age
            for entry in block:
                if entry.key.startswith("unlock_") and isinstance(entry.value, str):
                    self.unlocks.setdefault((entry.key[len("unlock_"):], entry.value),
                                            []).append(name)

    def of(self, kind: str, key: str) -> list[str]:
        return sorted(set(self.unlocks.get((kind, key), [])))

    def earliest(self, names: list[str]) -> str | None:
        """The one of these that comes in the earliest age: what a «not yet»
        line names as the advance to get (his ask 10-04)."""
        dated = [n for n in names if n in self.age]
        return min(dated, key=lambda n: (age_number(self.age[n]), n)) if dated else None

    def have(self, names: list[str]) -> str:
        if len(names) == 1:
            return "has_advance = %s" % names[0]
        return "OR = { %s }" % " ".join("has_advance = %s" % n for n in names)

    def open_to(self, names: list[str]) -> str | None:
        """Has one of these, or could research one: its `potential` holds.

        None when one of them is open to everybody, which leaves nothing to
        check.
        """
        options = []
        for name in names:
            potential = self.potential.get(name)
            if potential is None:
                return None
            options.append("has_advance = %s AND = { %s }" % (name, potential))
        return "OR = { %s }" % " ".join(options)


def age_number(age: str) -> int:
    """`age_4_reformation` -> 4."""
    match = re.match(r"age_(\d+)_", age)
    return int(match.group(1)) if match else 0


def _why(advances: Advances, unlocking: list[str], age: str | None) -> dict:
    """What a «not yet» line says it waits on: the advance that unlocks it, or
    the age it belongs to. Neither: «requirements not met», as the game says."""
    why = {"age": age if isinstance(age, str) else None, "advance": None, "advance_have": None}
    first = advances.earliest(unlocking) if unlocking else None
    if first:
        why.update(advance=first, advance_age=advances.age[first],
                   advance_have=advances.have(unlocking))
    return why


def _needs(*parts) -> list[str]:
    """What the «?» beside a «not yet» line lists (his ask 10-04): every gate
    the game itself puts on the object, for the game to word in its own
    tooltip, with a tick or a cross beside each."""
    return [p for p in parts if p]


def _soon(reach: list[str], now: list[str]) -> list[str]:
    return reach + ["NOT = { AND = { %s } }" % " ".join(now)]


def collect(game: Path) -> list[dict]:
    known = steps(game)
    advances = Advances(game)
    common = game / "in_game/common"
    lines: list[dict] = []

    # --- estate privileges -------------------------------------------------
    for key, (block, _) in pdx.objects(common / "estate_privileges").items():
        estate = pdx.get(block, "estate")
        if not isinstance(estate, str):
            continue
        base = ["country_has_estate = estate_type:%s" % estate]
        now = base + ["svx_privilege_takeable = { KEY = %s }" % key]
        reach = base + ["NOT = { has_estate_privilege = estate_privilege:%s }" % key]
        potential = own_trigger(pdx.get(block, "potential"))
        if potential:
            reach.append(potential)
        unlocking = advances.of("estate_privilege", key)
        needs = _needs(*base, advances.have(unlocking) if unlocking else None, potential,
                       own_trigger(pdx.get(block, "allow")))
        if unlocking:
            # `is_implementable_in` lets these through before the advance:
            # five of them were recommended to countries that could not take
            # them until 2026-09 (`svx_unlock_gate.txt` then).
            now.append(advances.have(unlocking))
            opened = advances.open_to(unlocking)
            if opened:
                reach.append(opened)
        for axis, (value, up_to) in pushes(block, known).items():
            lines.append({"direction": axis, "kind": "privilege", "object": key,
                          "value": value, "up_to": up_to, "now": now,
                          "soon": _soon(reach, now) if unlocking or potential else None,
                          "why": _why(advances, unlocking, None), "needs": needs})

    # --- government reforms ------------------------------------------------
    for key, (block, _) in pdx.objects(common / "government_reforms").items():
        base = []
        government = pdx.get(block, "government")
        if isinstance(government, str):
            base.append("government_type = government_type:%s" % government)
        now = list(base)
        age = pdx.get(block, "age")
        if isinstance(age, str):
            now.append("current_age_or_later = { age = %s }" % age)
        now += ["svx_reform_core = { KEY = %s }" % key,
                "government_reform:%s = { NOT = { is_locked_for = PREV } }" % key]
        reach = base + ["NOT = { has_reform = government_reform:%s }" % key]
        potential = own_trigger(pdx.get(block, "potential"))
        if potential:
            reach.append(potential)
        unlocking = advances.of("government_reform", key)
        needs = _needs(*base, "current_age_or_later = { age = %s }" % age if isinstance(age, str) else None,
                       advances.have(unlocking) if unlocking else None, potential,
                       own_trigger(pdx.get(block, "allow")))
        if unlocking:
            opened = advances.open_to(unlocking)
            if opened:
                reach.append(opened)
        gated_later = isinstance(age, str) or unlocking or potential
        for axis, (value, up_to) in pushes(block, known).items():
            lines.append({"direction": axis, "kind": "reform", "object": key,
                          "value": value, "up_to": up_to, "now": now,
                          "soon": _soon(reach, now) if gated_later else None,
                          "why": _why(advances, unlocking, age), "needs": needs})

    # --- laws and their policies -------------------------------------------
    for law, (block, _) in pdx.objects(common / "laws").items():
        policies = [(e.key, e.value) for e in block
                    if isinstance(e.value, list) and e.key and e.key not in LAW_FIELDS]
        pushed = {name: pushes(body, known) for name, body in policies}
        organization = pdx.get(block, "type") == "international_organization"
        if organization:
            kind = re.search(r"international_organization_type\s*=\s*international_organization_type:(\w+)",
                             pdx.text(pdx.get(block, "potential") or []))
            if not kind:
                continue
            for name, axes in pushed.items():
                gate = ["any_international_organizations_member_of = { "
                        "international_organization_type = international_organization_type:%s "
                        "NOT = { international_organization_has_policy = policy:%s } }"
                        % (kind.group(1), name)]
                for axis, (value, up_to) in axes.items():
                    lines.append({"direction": axis, "kind": "io_policy", "object": name,
                                  "law": law, "value": value, "up_to": up_to,
                                  "now": gate, "soon": None})
            continue

        law_potential = own_trigger(pdx.get(block, "potential"))
        law_unlocking = advances.of("law", law)
        law_allow = own_trigger(pdx.get(block, "allow"))
        for name, body in policies:
            policy_potential = own_trigger(pdx.get(body, "potential"))
            unlocking = sorted(set(law_unlocking + advances.of("policy", name)))
            needs = _needs(law_potential, law_allow, advances.have(unlocking) if unlocking else None,
                           policy_potential, own_trigger(pdx.get(body, "allow")))
            for axis, (value, up_to) in pushed[name].items():
                # Only one policy of a law is in force: one that already pushes
                # this way at least as hard makes this one pointless.
                stronger = [other for other, axes in pushed.items()
                            if other != name and axis in axes and axes[axis][0] >= value]
                peers = ["NOT = { has_policy = %s }" % other for other in stronger]
                # The law's and the policy's own `potential` too, as Glorp UI
                # did: `svx_policy_core` lets a law through once it is in force,
                # whatever its `potential` says of the policy.
                now = peers + [p for p in (law_potential, policy_potential) if p] + [
                    "svx_policy_core = { KEY = %s LAW = %s }" % (name, law),
                    "law:%s = { NOT = { is_locked_for = PREV } }" % law,
                    "policy:%s = { NOT = { is_locked_for = PREV } }" % name,
                ]
                reach = peers + ["NOT = { has_policy = %s }" % name]
                reach += [p for p in (law_potential, policy_potential) if p]
                if unlocking:
                    opened = advances.open_to(unlocking)
                    if opened:
                        reach.append(opened)
                gated_later = unlocking or law_potential or policy_potential
                lines.append({"direction": axis, "kind": "policy", "object": name,
                              "law": law, "value": value, "up_to": up_to, "now": now,
                              "soon": _soon(reach, now) if gated_later else None,
                              "why": _why(advances, unlocking, None), "needs": needs})
    return lines


ORDER = {"privilege": 0, "reform": 1, "policy": 2, "io_policy": 3}


def by_direction(lines: list[dict]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for line in sorted(lines, key=lambda l: (ORDER[l["kind"]], -l["value"], l["object"])):
        out.setdefault(line["direction"], []).append(line)
    return out


if __name__ == "__main__":
    import sys
    game = Path(sys.argv[1] if len(sys.argv) > 1 else "reference/game")
    found = collect(game)
    from collections import Counter
    print(Counter(l["kind"] for l in found))
    print(sum(1 for l in found if l["soon"]), "with a «not yet available» gate")
