#!/usr/bin/env python3
"""Availability gates for the extra societal value hints.

Reads the game files a second time to learn, per object, what a country needs in
order for that object to be reachable at all - so hints for other religions,
other estates or other subject types stop showing up.

Only triggers whose exact syntax is confirmed by usage in the shipped game files
are emitted. Anything unconfirmed is left ungated rather than guessed at: a
mistyped trigger is a load error, an ungated hint is only noise.
"""

import os
import re

import pdx

CONFIRMED_NOTE = "# gates use only trigger forms found verbatim in the game files"


def find_blocks(text):
    """Yield (object_key, body_text) for each top-level `key = { ... }`."""
    depth = 0
    key = None
    start = None
    i = 0
    line_start = True
    while i < len(text):
        ch = text[i]
        if ch == "#":
            j = text.find("\n", i)
            i = len(text) if j < 0 else j
            continue
        if ch == "{":
            if depth == 0 and key:
                start = i + 1
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and key and start is not None:
                yield key, text[start:i]
                key = None
                start = None
        elif depth == 0:
            match = re.match(r'([a-zA-Z_][a-zA-Z_0-9]*)\s*=\s*\{', text[i:])
            if match:
                key = match.group(1)
                i += match.end() - 1
                continue
        i += 1


def sub_block(body, name):
    """Return the raw text of `name = { ... }` inside body, or None."""
    match = re.search(r'\b%s\s*=\s*\{' % re.escape(name), body)
    if not match:
        return None
    depth = 0
    for i in range(match.end() - 1, len(body)):
        if body[i] == "{":
            depth += 1
        elif body[i] == "}":
            depth -= 1
            if depth == 0:
                return body[match.end():i].strip()
    return None


def scan_objects(root, relative_dir):
    """object key -> body text, for every .txt under root/relative_dir."""
    objects = {}
    directory = os.path.join(root, relative_dir)
    if not os.path.isdir(directory):
        return objects
    for name in sorted(os.listdir(directory)):
        if not name.endswith(".txt"):
            continue
        with open(os.path.join(directory, name),
                  encoding="utf-8-sig", errors="replace") as handle:
            # Comments out first: a block is copied as one line, and a `#` left
            # in it swallowed the rest — `merge_culture_group`'s commented-out
            # rank, four unit checks of `support_noble_sponsored_armies` (10-04).
            for key, body in find_blocks(pdx.strip_comments(handle.read())):
                objects[key] = body
    return objects


def status_owners(root):
    """special status -> the international organization that grants it.

    Read out of `special_statuses_implemented` rather than written down: the
    status's own `can_bestow_trigger` names the granting organization as
    `scope:recipient`, which a country scoped customizable localization does not
    have, so the organization has to be found from the other side.
    """
    owners = {}
    for key, body in scan_objects(root, "in_game/common/international_organizations").items():
        listed = sub_block(body, "special_statuses_implemented")
        if not listed:
            continue
        for status in listed.split():
            owners[status] = key
    return owners


def _needs_a_scope(block):
    """True when a trigger block reaches for something a country scope lacks.

    `scope:recipient`, `scope:source` and `scope:actor` are handed in by the
    system that evaluates the block in the game — an organization inviting a
    country, an interaction being set up. A customizable localization of
    `type = country` has none of them, so a block naming one cannot be copied
    and the entry is left ungated instead. `international_organization_type`
    is the same problem by another name: it is asked of an organization.
    """
    block = pdx.without_blocks(block, "any_international_organizations_member_of")
    return any(token in block for token in
               ("scope:recipient", "scope:source", "scope:actor", "scope:target",
                "international_organization_type"))


def gate_for(source_type, key, objects, extra=None):
    """Return {"reach": [...], "now": [...]} trigger lines for one hint.

    "reach" is what the country can never change on a whim - its tag, religion,
    which estates it has. Failing it means the hint is impossible and is dropped
    entirely. "now" adds what has to be true to act on it today. An entry that
    passes "reach" but not "now" is listed as merely attainable.

    Empty lists mean unconditional.
    """
    body = objects.get(key, "")
    extra = extra or {}

    if source_type == "international_organizations":
        # `can_join_international_organization` is the engine's own answer, in
        # the country scope and taking the organization as a target — both
        # confirmed in `docs/triggers.log`. The organization's own
        # `can_join_trigger` cannot be copied instead: it is written against
        # `scope:recipient`, which is the organization, and a country scoped
        # customizable localization has no such scope.
        #
        # `exists` first because most of these are situational — the Italian
        # leagues only exist while the Italian Wars run — and it is the same
        # guard the game puts in front of its own organization checks.
        lines = ["exists = international_organization:%s" % key,
                 "can_join_international_organization = international_organization:%s" % key]
        return {"reach": lines, "now": lines}

    if source_type == "international_organization_special_statuses":
        owner = extra.get("status_owners", {}).get(key)
        if not owner:
            return {"reach": [], "now": []}
        lines = ["exists = international_organization:%s" % owner,
                 "OR = { is_member_of_international_organization = international_organization:%s"
                 " can_join_international_organization = international_organization:%s }"
                 % (owner, owner)]
        return {"reach": lines, "now": lines}

    if source_type == "missions":
        # Every mission's `visible` opens with `game_has_missions_enabled = yes`,
        # the game's own scripted trigger for the Missions game rule
        # (`NOT = { has_game_rule = mission_packs_disabled }`). Copying the whole
        # block takes that and the mission's own conditions together.
        #
        # `enabled` is deliberately not copied: it answers "can this be finished
        # now", which changes month to month, where the hint only needs "is this
        # a thing this country can be offered".
        visible = sub_block(body, "visible")
        lines = ["game_has_missions_enabled = yes"]
        if visible and not _needs_a_scope(visible):
            lines = [" ".join(visible.split())]
        return {"reach": lines, "now": lines}

    if source_type == "parliament_types":
        # The same shape as building types: the object's own blocks, verbatim.
        # Parliament types belonging to an international organization gate on
        # `international_organization_type`, which is not a country trigger, so
        # those are left ungated rather than copied into the wrong scope.
        lines = []
        for name in ("potential", "allow"):
            block = sub_block(body, name)
            if block and not _needs_a_scope(block):
                lines.append(" ".join(block.split()))
        return {"reach": lines, "now": lines}

    if source_type == "religious_aspects":
        religions = re.findall(r'^\s*religion\s*=\s*([a-z_0-9]+)\s*$', body, re.M)
        reach = []
        if religions:
            # `religion = religion:X` in a country scope — 598 uses in the game's
            # own common/, and the form CMF and Construction Manager use too.
            #
            # This said `country_religion = religion:X` until 2026-08-25, on a
            # comment claiming it was confirmed in common/religious_aspects. It
            # was not: `country_religion` appears nowhere in the game's script
            # and is not in the engine's trigger dump. What the aspect files
            # carry is `religion = calvinist`, the aspect declaring its own
            # religion, which is a different thing in a different scope. 492
            # gates called a trigger that does not exist.
            reach.append("OR = { %s }" % " ".join(
                "religion = religion:%s" % r for r in sorted(set(religions))))
        # `has_religious_aspect = religious_aspect:X` - confirmed in the same files
        now = reach + ["NOT = { has_religious_aspect = religious_aspect:%s }" % key]
        enabled = sub_block(body, "enabled")
        if enabled:
            now.append(" ".join(enabled.split()))
        return {"reach": reach, "now": now}

    if source_type == "building_types":
        # `country_potential` is asked of a country and copies straight across.
        #
        # **`allow` is not.** The game evaluates it on the location being built
        # in, so it is written in location scope: `is_core_of = owner`,
        # `owner = { ... }`, `region`, `market`, `has_building`,
        # `dominant_culture`. Copied into a `type = country` customizable
        # localization it made the engine say so, in the player's error.log and
        # nowhere else:
        #
        #     jomini_trigger.cpp:803: is_core_of: Inconsistent trigger scopes
        #     (country vs. location) at svx_extra_hint_loc.txt:3073
        #
        # Every building push here is a `capital_country_modifier`, so the
        # location the block has to hold in is the capital — which makes
        # `capital = { ... }` not a workaround but the exact question. `capital`
        # is a country → location event target (`tools/api.py capital`), and the
        # game writes `exists = capital` in front of it, 76 times in its own
        # `common/`.
        potential = sub_block(body, "country_potential")
        reach = ([" ".join(potential.split())]
                 if potential and not _needs_a_scope(potential) else [])
        allow = sub_block(body, "allow")
        now = reach + (["exists = capital capital = { %s }" % " ".join(allow.split())]
                       if allow and not _needs_a_scope(allow) else [])
        return {"reach": reach, "now": now}

    if source_type == "religious_schools":
        enabled = sub_block(body, "enabled_for_country")
        lines = [" ".join(enabled.split())] if enabled else []
        return {"reach": lines, "now": lines}

    if source_type == "estates":
        # `country_has_estate = estate_type:X` - confirmed in Glorp UI and game files
        lines = ["country_has_estate = estate_type:%s" % key]
        return {"reach": lines, "now": lines}

    if source_type == "parliament_issues":
        # A parliament to raise it in, the estate that raises it, and the
        # issue's own blocks. `has_parliament = yes` alone left four "support
        # building X forts" issues on screen at once when only one can ever be
        # valid: each names its advance and forbids the better ones, in `allow`.
        #
        # Two issues carry `potential = { always = no }` with a comment saying
        # they are driven by events. Copying `potential` verbatim drops them,
        # which is right — they are not something a country can be offered.
        lines = ["has_parliament = yes"]
        estate = re.search(r"^\testate\s*=\s*(\w+)", body, re.M)
        if estate:
            lines.append("country_has_estate = estate_type:%s" % estate.group(1))
        for name in ("potential", "allow"):
            block = sub_block(body, name)
            if block and not _needs_a_scope(block):
                lines.append(" ".join(block.split()))
        return {"reach": lines, "now": lines}

    if source_type == "cabinet_actions":
        # The same shape again: the action's own `potential` and `allow`.
        # `potential` is where the national ones live — `office_of_new_converts`
        # wants a modifier on Kazan, `stroganov_influences` wants the Stroganov
        # variable — and both were on screen for a Catholic German county until
        # this was written.
        lines = []
        for name in ("potential", "allow"):
            block = sub_block(body, name)
            if block and not _needs_a_scope(block):
                lines.append(" ".join(block.split()))
        return {"reach": lines, "now": lines}

    if source_type == "subject_types":
        # A `subject_modifier` pushes the subject itself; an `overlord_modifier`
        # pushes whoever holds such a subject, which no gate on this country's
        # own type can say — those stay ungated.
        #
        # What the overlord's side can say comes from the type's `visible` and
        # `visible_through_diplomacy`, which run in the overlord's scope with
        # the would-be subject as `scope:target`: each top-level condition
        # that does not reach for the subject is copied. Pronoia then wants
        # Byzantium, the familial governor the Tunisian reform (10-04).
        if extra.get("block") == "overlord_modifier":
            lines = []
            for name in ("visible", "visible_through_diplomacy"):
                block = sub_block(body, name)
                for entry in pdx.parse(block or ""):
                    line = pdx.text([entry])
                    if line.split() == ["always", "=", "no"] or _needs_a_scope(line):
                        continue
                    lines.append(line)
            return {"reach": lines, "now": lines}
        lines = ["is_subject_type = %s" % key]
        return {"reach": lines, "now": lines}

    if source_type == "advances":
        # Its own `potential` — the two that push a value are a Persian and an
        # Anatolian one — and not yet researched.
        potential = sub_block(body, "potential")
        reach = ([" ".join(potential.split())]
                 if potential and not _needs_a_scope(potential) else [])
        return {"reach": reach, "now": reach + ["NOT = { has_advance = %s }" % key]}

    if source_type == "bureaucracies":
        # The game's own pair of questions, both country triggers taking the
        # type (`docs/triggers.log`): can this country see it, can it set it up.
        reach = ["bureaucracy_type_is_visible = bureaucracy_type:%s" % key,
                 "NOT = { has_bureaucracy_of_type = bureaucracy_type:%s }" % key]
        return {"reach": reach,
                "now": reach + ["bureaucracy_type_is_enabled = bureaucracy_type:%s" % key]}

    if source_type == "chivalric_orders":
        # And the order's own `potential`: the Golden Fleece is Burgundy's,
        # each German society its own state's, and every one of them was on
        # screen for any country with an order until 10-04.
        lines = ["has_chivalric_order = yes"]
        potential = sub_block(body, "potential")
        if potential and not _needs_a_scope(potential):
            lines.append(" ".join(potential.split()))
        return {"reach": lines, "now": lines}

    return {"reach": [], "now": []}
