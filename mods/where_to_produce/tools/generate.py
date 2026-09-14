#!/usr/bin/env python3
"""Generate everything `where_to_produce` cannot write by hand.

The mod answers one question: **for this good, where is the best place to make
it, and with what.** The player names a good; the mod finds, per location, the
best production method available for that good there, and ranks the locations by
what that method would earn from the raw materials the province supplies.

Choosing the method was the player's job for one round and it should not have
been: knowing which recipe suits which ground *is* the question the mod exists to
answer, so asking it back was asking the player to do the work first.

Four things come out of the game's own files rather than out of a list somebody
typed, so a patch that adds a method or renames a region is picked up by a
rebuild:

  - **The good picker.** Two lists, split the way the goods themselves are: the
    25 raw materials an RGO can also make, and the 22 things only a workshop
    makes. Lists rather than dropdowns -- CMF handles a dropdown option click
    through `CMM_MarkDropdownSelection_<index>` and defines twenty of them, so a
    dropdown is silently unclickable past its twentieth option. A list is handled
    to fifty.
  - **The zone.** The five land continents, ticked. Not a walk: a location's
    continent is one plain trigger, so nothing has to be marked in advance.
  - **The scoring.** One script value per method giving what it would earn here,
    and one effect per good that runs its methods over the candidates and keeps
    the best. That is where "the mod finds the method" actually happens.
  - **The result rows.** Fifty of them, each reading back a location, a number
    and the building that won it.

The formula is `eu5data.Method.bonus`, verified to the digit against three
in-game tooltips at 1.3.10. See `docs/research/engine.md`.

    python3 mods/where_to_produce/tools/generate.py
"""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

MOD = Path(__file__).resolve().parent.parent
REPO = MOD.parent.parent
sys.path.insert(0, str(REPO / "tools"))

import eu5data  # noqa: E402
import refs  # noqa: E402

MOD_ID = "bag_wtp"

# How many rows any list has at most. CMF initialises list items through an
# unrolled chain of `if`s that ends at fifty, and handles a row click through
# `CMM_MarkListPosition_*`, which is unrolled to the same fifty. Raising this
# means leaving CMM, not editing this number.
LIST_CAP = 50
RESULT_ROWS = 50

# What `bag_wtp_m<n>` is multiplied by before anything ranks on it. A method's
# output is a fraction of a unit and the differences between two provinces are
# in its third decimal; nothing in the game or in `reference/` sorts on numbers
# that small. At 1000 the largest method in the game comes to about 4950, which
# is small enough to be nowhere near any fixed-point ceiling, and the smallest
# difference the bonus can make is still worth about half a unit.
RANK_SCALE = 1000

# What counts as rural. `village_category` is the game's own: forest, market,
# farming and fishing villages, thirteen methods between them, each producing a
# fifth to a half of what a workshop of the same good does. They are scored on
# their own side so a village never displaces a guild in the ranking, and shown
# beside it because rural ground is built on too.
RURAL_CATEGORIES = ("village_category",)

# How many goods one urban right can favour. Three is the widest in the game --
# paper, books and dyes; cloth, fine cloth and dyes; three weapons; three
# drinks -- and a row holds a fixed number of answers rather than a variable
# one, because script has no list of tuples and the answers are flat variables
# on the location.
RIGHT_SLOTS = 3

# A bundle's total is a sum of `RANK_SCALE`d outputs times market prices, and it
# runs an order of magnitude higher than a single good's: textile rights with
# every input present come to 64 680, against a single method's 4 950. Whether
# the engine's fixed point is 32-bit is not knowable from here and 21 474 is
# where a 32-bit one ends, so the weights carry a tenth of `RANK_SCALE` -- worst
# case 6 468, and the smallest difference the bonus can make is still about 4.6.
RIGHT_SCALE = RANK_SCALE // 10

# Товары, у которых `cov_file` считает покрытие: те, что стоят в связках грамот
# и у чьих способов есть сырьевой вход. Двадцать; `silk` среди них нет -- его
# рецепты сырья провинции не потребляют, -- и это единственный товар связок, на
# который счёта грамоты не хватает.
# **Два товара, у которых своё РГО усредняется в покрытие, и только два.**
# `_trmm_cov_dyes` и `_trmm_cov_wine` -- единственные, где он пишет `add = 1`
# и `divide = 2`, с объяснением: модификатор вывода грамоты поднимает и
# собственное РГО этого сырья, так что на его локации оно входит ещё одним
# полностью покрытым поставщиком. Остальные восемнадцать этого не делают.
TRMM_RGO_AVERAGED = frozenset(("dyes", "wine"))

COV_GOODS = frozenset("""
beer books cannons cloth dyes fine_cloth firearms furniture glass jewelry
leather liquor masonry naval_supplies paper pottery tar tools weaponry wine
""".split())

# The whole-map plan. How many rounds of allocation the player may ask for at
# most, and how many rows the plan window draws. The first is a ceiling on a
# setting rather than the setting itself: CMM clamps the number he chooses, and
# a `while` in an effect that cannot leave its condition is a hung game rather
# than an error in a log.
#
# **On a big ground the guard is what decides whether the plan finishes.** A
# sweep places at most one building per good per side, so 970 buildings over 32
# goods needs thirty sweeps at the very least; at 12 the thirty-eighth run was
# cut off with 342 of 1312 rooms still empty -- «мод не справился досчитать всё
# как надо». It costs nothing where a lap has no work, because the `while` leaves
# the moment two laps running add nothing.
#
# **A lap, not a sweep, since 2026-09-07.** The allocator used to be twenty
# passes with a `while` inside each; it is one `while` now, and a turn of it
# raises the level by one. So this is the highest count any good can reach, plus
# the dry laps that open the quota after the share is spent. Northern Germany --
# 416 locations, some 1300 rooms, 38 goods -- gives a share near 34, and the
# leftovers are dealt a layer a lap after that, so 150 leaves room. `laps=150` in
# the dump is the guard cutting the draft off with work still to do, which is the
# one fault in here that leaves no other trace.
PLAN_LAPS = 150
# **One page of the plan window, and not the size of the answer.** Only the
# datamodel decides what a scripted widget costs, so this is the number of rows
# drawn at once; `PLAN_RANKED` below is how many the plan keeps, and the page
# buttons walk them one page at a time. More than `RESULT_ROWS` because a
# plan's row is a location where a ranking's is a province -- the same ground is
# four to eight times the rows.
PLAN_ROWS = 150
# How many locations one plan ranks into pages. The ranked list is a global
# variable list and two variables on each location, which is cheap beside the
# pass that filled them -- the window's datamodel is the thing that costs, and it
# never holds more than one page. Northern Germany, the largest ground he has
# run, is 416 locations; this leaves room for several times that before anything
# is dropped, and the header says how many were kept against how many the plan
# used.
PLAN_RANKED = 1500
# And how many provinces are put in order for those rows. A location's row sorts
# on its province's place, so a province past this cap keeps the 9999 the reset
# gave it and its locations land at the end together rather than in the wrong
# place among the others.
PLAN_PROVS = 600

# The sweeps run in tiers, and a tier admits only goods that at most this many
# candidate locations could hold. **The scarce go first**: a good with one place
# in the whole ground takes it before a good with forty gets its second, which is
# the owner's «жёстко зарезервировать слоты».
#
# **These are the scarce rungs only, and 0 -- "everything" -- is no longer one of
# them.** It was, and the run of 2026-09-03 measured what that cost: with the
# ladder written `for band: for tier:` the tier rungs of every band together
# placed **three buildings out of sixty-nine**, and all the rest went to the
# `tierall` rung of band 800 -- because a scarce good's gain is usually low
# (`iron` best 0 of 1000 over the whole ground, `stone` 372) and a rung is only
# entered when the gain clears the band. So iron never reached a rung above band
# 0, and by the time band 0 came round the four locations in Westphalia that can
# hold a bog iron smelter had been common goods' for twenty-five passes.
# `docs/investigations/plan_gaps.md`, fault B.
# **Ступень — доля земли, а не число локаций.** Владелец, 2026-09-06: «а что
# если земля настолько большая, что ему будет места 40+, но по отношению к 1000
# локациям — это совсем мало. Но мод скажет, что 40 это много, железо первым не
# пойдёт и останется без своих локаций». Он прав: 16 из 48 — треть земли, 16 из
# 1000 — полтора процента, и одно число значит в этих случаях противоположное.
#
# **Поэтому ступень считается от числа кандидатов**, а абсолютные числа остались
# полом: на маленькой земле проценты дают меньше единицы, и там ступени обязаны
# работать ровно как работали. Проценты подобраны так, чтобы на его земле в 48
# локаций выйти в те же 1/2/4/8/15 — не сломать то, что уже проверено прогонами.
#
# 2 % / 4 % / 8 % / 16 % / 32 % — делители 50, 25, 12.5, 6.25, 3.125.
# Предел, до которого ищется доля стороны. Больше него не бывает: доля не
# превосходит числа комнат самой большой стороны.
SHARE_CAP = 2000

PLAN_TIERS = (1, 2, 4, 8, 16)
TIER_DIVISORS = (50, 25, 12.5, 6.25, 3.125)

# The gain a placement has to reach to be made in this pass, out of `RANK_SCALE`.
# Descending, and the last is 0 because a good the ground feeds nothing is still
# a good that has to be produced. Five rather than ten: a band costs a sweep over
# every tier, and the plan is already the expensive button.
PLAN_BANDS = (800, 600, 400, 200, 0)

# How many towns a charter may be dealt one at a time before the rest are dealt
# at once. The charter ladder raises its ceiling by one and runs every band at
# each height, which is what makes the counts come out level; the guard is there
# because the ceiling it climbs to is towns divided by charters, and a country
# with many towns and two charters would otherwise walk its ground a hundred
# times over. Westphalia -- 48 towns, 9 charters -- climbs to 6.
RIGHT_LEVELS = 12

# **The rungs inside one lap of the draft, and the whole of the ordering.**
#
# **A lap is a level**: `_plan_lvl` rises by one and every good may add at most
# one building before the next lap starts. So this list no longer decides *how
# many* buildings anything gets -- only who picks first inside the lap, and out
# of which locations.
#
# 1. **The scarce first**, tier by tier, five bands inside each -- a good only a
#    handful of locations can hold picks before a good with forty. «Дайте
#    сначала сложным домикам их 2 провинции по возможности, найдите минимум 20
#    локаций с болотами и зарезервируйте их под железо», 2026-09-03.
# 2. **Then everything**, five bands, where gain alone decides.
#
# **Coverage is not a rung any more and does not need to be.** It was five
# passes of its own, testing `_pn<n> = 0`; at `_plan_lvl = 1` the level gate
# *is* that test, and lap one runs every band down to 0 -- so a good the ground
# feeds nothing still takes a place before anything takes a second. One rule
# fewer for the same guarantee.
#
# **The open ladder is not a rung either.** It was five more passes raising every
# quota a round; a dry lap does that now, so the leftovers spread in level layers
# like everything else.
PLAN_RUNGS = ([(band, tier) for band in PLAN_BANDS for tier in PLAN_TIERS]
              + [(band, 0) for band in PLAN_BANDS])


def rung_name(band: int, tier: object) -> str:
    """How a rung is written in the dump: the band it admits and the tier it is."""
    return f"band{band}/tier{tier if tier else 'all'}"

# The diagnostic dump: what one press writes into the log, and the caps on it.
# **A cap must never be silently the answer**, so every capped block prints how
# many it left out. `docs/pitfalls/diagnosis.md` has the whole instrument and the
# four things about `debug_log` that were measured rather than assumed.
DIAG_VERSION = 5
DIAG_LOCS = 200
DIAG_ROWS = 25
# How many laps of the draft the dump prints one line each for. A lap line is
# «how many buildings level L placed», which is the shape of the whole
# allocation in one column: a plan that is even reads as a long flat run, and a
# plan that is not falls off a cliff. Forty covers his ground several times
# over and a realm-sized one once; past it the count is still in `laps=`.
DIAG_LAPS = 40
# The scratch globals a printed line reads through. **A `debug_log` string cannot
# reach the item a walk is standing on** -- measured 2026-09-02, `THIS.MakeScope`
# fails and the bracket is echoed literally -- so every number is parked in one of
# these first and printed from there. **Twenty because the widest line, a
# good's, has twenty numbers on it** -- and a line that parks past this number
# prints a blank, because the script value it reads through is not generated.
# Nothing catches that: `read(17)` against sixteen slots came within one build of
# shipping on 2026-09-06, and `read(18)` against seventeen slots came within one
# build again the same day, when the good's line gained `out=`. **Raise this
# whenever a line gains a number, in the same edit.**
DIAG_SCRATCH = 27

# The land continents, in the order the game's own localization lists them. The
# ocean continent is not offered: nothing is built there.
CONTINENTS = ("europe", "asia", "africa", "america", "oceania")

# One tab per job. A CMM tab is just a `tab_id` on the settings under it, so this
# costs nothing but the localization keys -- and the first build had five groups
# stacked on one tab, which meant scrolling past the goods to reach the answer.
#
# **«Товар» is gone, 2026-09-06.** Its four lists were the only way to choose a
# good or a right, and both are chosen in the ranking window now; what is left
# on the mod page is «Земля», three «open» buttons under «Расчёты» and the
# technical tab. `docs/investigations/wtp_menu_rebuild.md`.
TAB_ZONE = "zone"
TAB_PLAN = "plan"

ZONE_OUT = MOD / "in_game/common/scripted_effects/bag_wtp_generated_zone.txt"
SOURCES_OUT = MOD / "in_game/common/scripted_effects/bag_wtp_generated_sources.txt"
FOODPOT_OUT = MOD / "in_game/common/script_values/bag_wtp_generated_foodpot.txt"
REGION_OUT = MOD / "in_game/common/scripted_effects/bag_wtp_generated_regions.txt"
PICKER_OUT = MOD / "in_game/common/scripted_effects/bag_wtp_generated_picker.txt"
SCORE_OUT = MOD / "in_game/common/scripted_effects/bag_wtp_generated_score.txt"
ROWS_OUT = MOD / "in_game/common/scripted_effects/bag_wtp_generated_rows.txt"
VALUES_OUT = MOD / "in_game/common/script_values/bag_wtp_generated_values.txt"
TRIGGERS_OUT = MOD / "in_game/common/scripted_triggers/bag_wtp_generated_triggers.txt"
GUIS_OUT = MOD / "in_game/common/scripted_guis/bag_wtp_generated_scripted_gui.txt"
LAYOUT_OUT = MOD / "in_game/common/scripted_effects/bag_wtp_generated_layout.txt"
RIGHTS_OUT = MOD / "in_game/common/scripted_effects/bag_wtp_generated_rights.txt"
PLAN_OUT = MOD / "in_game/common/scripted_effects/bag_wtp_generated_plan.txt"
PLAN_TRIGGERS_OUT = MOD / "in_game/common/scripted_triggers/bag_wtp_generated_plan_triggers.txt"
PLAN_LOC_OUT = MOD / "in_game/common/customizable_localization/bag_wtp_generated_plan_loc.txt"
DIAG_OUT = MOD / "in_game/common/scripted_effects/bag_wtp_generated_diag.txt"
EDITOR_OUT = MOD / "in_game/common/scripted_effects/bag_wtp_generated_editor.txt"
EDITOR_TRIGGERS_OUT = MOD / "in_game/common/scripted_triggers/bag_wtp_generated_editor_triggers.txt"
LOC_OUT = MOD / "main_menu/localization/%s/bag_wtp_generated_l_%s.yml"
LOC_LANGUAGES = ("english", "russian")

BOM = "﻿"
def goods_order(split: dict[str, list[str]]) -> list[str]:
    """The plan's own numbering: raw goods first, then made, each alphabetical.

    Every numbered thing in this mod -- `_pn<n>`, `_p<n>`, `_pool<n>`, the
    picker's cells -- is indexed by position in this list, so it has one
    definition rather than eight copies of the same comprehension.
    """
    return [good for kind in ("raw", "made") for good in split[kind]]


HEADER = "# Generated by mods/where_to_produce/tools/generate.py. Do not edit by hand.\n"


def advance_files() -> list[Path]:
    """Файлы продвижений -- игры и каждого мода из `reference/mods`.

    **Национальный домик виден только отсюда.** `trin_national_destinies` гейтит
    каждое своё здание через `country_potential = { has_advance = X }`, а X --
    его собственное продвижение с `potential = { has_or_had_tag = GER }`. Пока
    эти файлы не читались, ни `unlocks`, ни `locked_advances` о них не знали, и
    план «на конец» предлагал Вестфалии японскую кузню.
    """
    out: list[Path] = [*(refs.GAME / "in_game/common/advances").glob("*.txt")]
    for common in refs.mod_commons():
        out += sorted((common / "advances").glob("*.txt"))
    return out


def unlocks() -> dict[str, str]:
    """Production method -> the advance that unlocks it.

    Only ten methods are gated this way; the rest ride on their building's own
    unlock, of which there are 119 with an age attached. Both are asked through
    `can_build_building` in country scope and `has_advance`.
    """
    out: dict[str, str] = {}
    for path in advance_files():
        text = path.read_text(encoding="utf-8-sig")
        for block in re.finditer(r"^([a-z0-9_]+)\s*=\s*\{(.*?)^\}", text, re.S | re.M):
            for method in re.findall(r"unlock_production_method\s*=\s*([a-z0-9_]+)",
                                     block.group(2)):
                out[method] = block.group(1)
    return out


UNLOCKS = unlocks()


def country_potentials() -> dict[str, str]:
    """Building -> its own `country_potential`, as text, game and mods alike.

    **Не всякий национальный домик назван своим продвижением.** `unlock_building`
    ставит связь «продвижение -> здание», но `nd_arc_cilician_workshop` её не
    имеет: он гейтится только `country_potential = { has_advance =
    nd_arc_kingship_of_levon }`, а само продвижение заперто на тег. Четыре здания
    из 297 держались ровно на этом, и «на конец» предлагал их всем.
    """
    out: dict[str, str] = {}
    folders = [refs.GAME_COMMON / "building_types"]
    folders += [common / "building_types" for common in refs.mod_commons()]
    for folder in folders:
        for path in sorted(folder.glob("*.txt")):
            text = path.read_text(encoding="utf-8-sig")
            for block in re.finditer(r"^([a-z0-9_]+)\s*=\s*\{(.*?)^\}", text, re.S | re.M):
                # **Однострочная форма пробуется ПЕРВОЙ, и это не стиль.** Форма
                # `^\tX = {{(.*?)^\t}}` нежадная, но закрывающую скобку ищет в
                # начале строки -- а у блока, где `potential` написан одной строкой,
                # первая такая скобка принадлежит **следующему** блоку с телом
                # (`ai_weight = {{ ... }}`). Так `nd_drr_jezail_tradition` отдал в
                # ворота всё своё содержимое целиком, и игра писала «Unknown trigger
                # type: ai_weight» шестнадцать раз за загрузку (его `debug.log`,
                # 2026-09-14). Однострочная форма требует, чтобы скобки сошлись в
                # той же строке, поэтому подменить её нечем.
                gate = (re.search(r"^\tcountry_potential\s*=\s*\{([^{}\n]*)\}[ \t]*$",
                                  block.group(2), re.M)
                        or re.search(r"^\tcountry_potential\s*=\s*\{[ \t]*$(.*?)^\t\}",
                                     block.group(2), re.S | re.M))
                if not gate:
                    continue
                body = " ".join(" ".join(line.split("#", 1)[0].split())
                                for line in gate.group(1).splitlines()).strip()
                if body:
                    out[block.group(1)] = " ".join(body.split())
    return out


def locked_advances() -> dict[str, str]:
    """Advance -> the country condition it carries, for the ones that have one.

    **An advance with a `potential` is not one you will have by the end -- it is
    one you will never have.** 45 of the 181 advances that unlock a building or a
    method are locked to a tag, a culture group or a region: `copperworking` wants
    `is_capital_mesoamerica`, the porcelain kiln wants an east-Asian capital,
    Scottish whisky wants Scotland. The plan's «на конец» side assumed every
    advance is eventually in, so it offered all of them to everybody -- which is
    how five porcelain guilds landed in northern Germany.
    """
    out: dict[str, str] = {}
    for path in advance_files():
        text = path.read_text(encoding="utf-8-sig")
        for block in re.finditer(r"^([a-z0-9_]+)\s*=\s*\{(.*?)^\}", text, re.S | re.M):
            # **И однострочный `potential`.** `trin_national_destinies` пишет
            # `potential = { has_or_had_tag = GER }` в одну строку, а форма,
            # искавшая только закрывающую скобку в начале строки, такие
            # пропускала -- то есть считала национальный домик доступным всем.
            # Так Вестфалия получила в план чужие домики, 2026-09-09.
            # **Однострочная форма пробуется ПЕРВОЙ, и это не стиль.** Форма
            # `^\tX = {{(.*?)^\t}}` нежадная, но закрывающую скобку ищет в
            # начале строки -- а у блока, где `potential` написан одной строкой,
            # первая такая скобка принадлежит **следующему** блоку с телом
            # (`ai_weight = {{ ... }}`). Так `nd_drr_jezail_tradition` отдал в
            # ворота всё своё содержимое целиком, и игра писала «Unknown trigger
            # type: ai_weight» шестнадцать раз за загрузку (его `debug.log`,
            # 2026-09-14). Однострочная форма требует, чтобы скобки сошлись в
            # той же строке, поэтому подменить её нечем.
            gate = (re.search(r"^\tpotential\s*=\s*\{([^{}\n]*)\}[ \t]*$",
                              block.group(2), re.M)
                    or re.search(r"^\tpotential\s*=\s*\{[ \t]*$(.*?)^\t\}",
                                 block.group(2), re.S | re.M))
            if not gate:
                continue
            # **Strip the game's own comments before collapsing to one line.**
            # `copperworking` carries a commented-out religion clause, and folded
            # flat the `#` swallowed the rest of the line -- closing braces
            # included. The file parsed as unbalanced and nothing would have said
            # so but `error.log`.
            body = " ".join(" ".join(line.split("#", 1)[0].split())
                            for line in gate.group(1).splitlines()).strip()
            body = " ".join(body.split())
            if body:
                out[block.group(1)] = body
    return out


LOCKED = locked_advances()
COUNTRY_POTENTIALS = country_potentials()


def building_sources() -> dict[str, int]:
    """Здание -> номер мода, который его объявил; ванильные сюда не попадают.

    **Читается тем же способом, каким склеивается игра**: чей `common` объявил
    ключ последним, того здание и есть. Номер нужен, чтобы у каждого мода-
    источника была своя галочка в настройках.
    """
    out: dict[str, int] = {}
    for number, (_folder, _name, common) in enumerate(refs.mod_sources(), start=1):
        folder = common / "building_types"
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.txt")):
            if "readme" in path.name.lower():
                continue
            text = path.read_text(encoding="utf-8-sig", errors="replace")
            for match in re.finditer(r"^([a-z0-9_]+)\s*=\s*\{", text, re.M):
                out[match.group(1)] = number
    return out


BUILDING_SOURCE = building_sources()
VANILLA_BUILDINGS = {
    match.group(1)
    for path in sorted((refs.GAME_COMMON / "building_types").glob("*.txt"))
    if "readme" not in path.name.lower()
    for match in re.finditer(r"^([a-z0-9_]+)\s*=\s*\{",
                             path.read_text(encoding="utf-8-sig", errors="replace"), re.M)}


def source_of(building: str) -> int:
    """Номер мода-источника, или 0 -- если здание есть и у самой игры.

    **Перекрытие ванильного здания источником не делает.** `construction_manager`
    объявляет свой `cm_location_upgrade_buildings`, но и правит чужие; галочка
    «не читать этот мод» не должна выключать здание, которое было в игре и без
    него.
    """
    return 0 if building in VANILLA_BUILDINGS else BUILDING_SOURCE.get(building, 0)


def method_gates(method: eu5data.Method) -> list[str]:
    """Условия «может ли эта страна вообще получить этот метод», все до одного.

    **Один источник правды, потому что их было два, и они разошлись.**
    `triggers_file` писал `_reach_<n>` по продвижениям **и** по
    `country_potential` здания, а `score_file` решал, спрашивать ли `_reach_<n>`
    вообще, только по продвижениям. У тибетского ателье продвижения нет -- оно
    заперто `country_potential`, -- поэтому ворота были написаны и ни разу не
    спрошены, и Вестфалия получила его в план «на конец». Владелец, 2026-09-09,
    со скриншотом Дортмунда: «так и что ты мне рассказываешь что в план не попал
    ни один лишний домик?»
    """
    gates = [LOCKED[a] for a in method_advances(method) if a in LOCKED]
    own = building_reach(method.building)
    gates += [own] if own else []
    # **И галочка мода-источника.** Она же делает список ворот непустым у любого
    # чужого здания, а значит `score_file` спросит их всегда -- ровно та дыра,
    # через которую тибетское ателье попало к Вестфалии.
    source = source_of(method.building)
    if source:
        gates.append(f"global_var:{MOD_ID}_src{source} = 1")
    # **И собственный `allow` метода.** Кастильское сукно не запирает ни одно
    # продвижение и ни один `country_potential` здания -- запирает переменная
    # державы внутри самого метода, и без этой строки «Мериносовая шерсть»
    # стояла кандидатом у любой страны на свете (`method_allows`).
    own_allow, _ = method_allow_gates(method)
    if own_allow:
        gates.append(own_allow)
    # **Один и тот же запор, названный дважды, -- одна строка.** Продвижение
    # мода и `country_potential` его же здания часто написаны одним условием;
    # в `_reach_<n>` это выходило двумя одинаковыми `AND`.
    return list(dict.fromkeys(gates))


def method_allows() -> dict[str, str]:
    """Метод -> его собственный `allow`, одной строкой. Их семь на всю сборку.

    **Ворота бывают на методе, а не только на здании, и этого никто не читал.**
    Владелец, поиграв, 2026-09-12: «тонкое сукно показывает, что расчитывает на
    метод "Мериносовая шерсть", которая очевидно доступна хер пойми кому, но
    точно не мне». «Мериносовая шерсть» -- `spanish_cloth_workshop_maintenance`,
    и он заперт не продвижением и не `country_potential` здания, а собственным

        allow = { custom_tooltip = { text = has_unlocked_spanish_cloth_industry
                                     has_variable = spanish_cloth_industry } }

    `method_gates()` смотрел только на продвижения метода и на
    `country_potential` **здания**, поэтому метод стоял в таблице без единых
    ворот у любой державы на свете.

    **Класс маленький и посчитан**: собственный `allow` несут семь блоков на всю
    сборку, но пять из них -- крепостные житницы, которые не производят ничего
    и методами не являются вовсе. Остаются два кастильских суконных. Читается
    тем же способом, каким склеивается игра: `common/building_types` каждого
    мода поверх игровой.
    """
    out: dict[str, str] = {}
    folders = [refs.GAME_COMMON / "building_types"] + [
        common / "building_types" for _folder, _name, common in refs.mod_sources()]
    for folder in folders:
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.txt")):
            if "readme" in path.name.lower():
                continue
            text = path.read_text(encoding="utf-8-sig", errors="replace")
            for match in re.finditer(r"(?m)^\t\t([a-z0-9_]+)\s*=\s*\{", text):
                body = eu5data._braced(text, match.end() - 1)
                # `produced` ключом, а не словом: пять крепостных житниц несут
                # `allow` и не производят ничего -- `is_produced_in_market`
                # внутри их условия ловился поиском по подстроке, и они попадали
                # сюда, не будучи методами вовсе.
                if not re.search(r"(?m)^\t\t\tproduced\s*=", body):
                    continue
                if not re.search(r"(?m)^\t\t\tallow\s*=\s*\{", body):
                    continue
                allow = eu5data._braced(body, body.index("{", body.index("allow")))
                out[match.group(1)] = " ".join(allow[1:-1].split())
    return out


METHOD_ALLOWS = method_allows()
# Что из `allow` метода переведено и куда. Ворота страны идут в `_avail_`/
# `_reach_`, ворота локации -- рядом с `_stands_<здание>`; непереведённое не
# гадается, а печатается в конце сборки, чтобы следующий чужой `allow` был
# виден, а не тих.
UNREAD_ALLOWS: dict[str, str] = {}


def method_country_gate(key: str) -> str | None:
    """Страновая половина `allow` метода, или `None`.

    **Переводится только то, что переводится без догадок** -- то же правило, что
    у `building_reach`. `has_variable = X`, в обёртке `custom_tooltip` или без
    неё, это переменная державы: кастильская промышленность приходит событием
    (`flavor_cas`), а не продвижением, поэтому «когда-нибудь» для неё значит
    ровно то же, что «сейчас», и ворота одни на обе стороны.

    **Скоуп выбран, а не измерен.** Сам `allow` спрашивает `scope:target`, когда
    хочет локацию, -- значит по умолчанию он не в локации; переменная,
    выдаваемая национальным событием, живёт на державе. Если окажется иначе,
    метод исчезнет у всех, включая Кастилию, -- и это единственное, что в этой
    правке может ошибиться.
    """
    body = METHOD_ALLOWS.get(key)
    if not body:
        return None
    one = re.fullmatch(r"custom_tooltip = \{ text = [a-z0-9_]+ (has_variable = [a-z0-9_]+) \}", body)
    if one:
        return one.group(1)
    if re.fullmatch(r"has_variable = [a-z0-9_]+", body):
        return body
    return None


def method_location_gate(key: str) -> str | None:
    """Локационная половина `allow` метода, или `None`.

    Пять крепостных житниц спрашивают `scope:target ?= { market ?= {
    is_produced_in_market = goods:X } }`. `scope:target` у метода -- локация, в
    которой его собираются запустить, и внутренность этого блока сама игра
    пишет как условие локации: `nd_msa_plantation_estate` несёт ровно
    `market ?= { is_produced_in_market = goods:pepper }` в своём
    `location_potential`. Поэтому перевод -- содержимое блока, слово в слово.
    """
    body = METHOD_ALLOWS.get(key)
    if not body:
        return None
    inner = re.fullmatch(r"scope:target \?= \{(.*)\}", body)
    if inner:
        return " ".join(inner.group(1).split())
    return None


def method_allow_gates(method: eu5data.Method) -> tuple[str | None, str | None]:
    """Обе половины `allow` всех частей метода -- страновая и локационная.

    У пары `base+improvement` частей две, и `allow` может нести любая: ключ
    метода это склейка, а `allow` объявлен на имени части.
    """
    country, location = [], []
    for part in method.parts:
        if part.key not in METHOD_ALLOWS:
            continue
        one = method_country_gate(part.key)
        two = method_location_gate(part.key)
        if one:
            country.append(one)
        elif two:
            location.append(two)
        else:
            UNREAD_ALLOWS[part.key] = METHOD_ALLOWS[part.key]
    join = lambda parts: (parts[0] if len(parts) == 1 else
                          " ".join(f"AND = {{ {p} }}" for p in parts)) if parts else None
    return join(country), join(location)


# **Что такое «еда» для житницы, и почему фруктов тут нет.** Владелец,
# 2026-09-13: «Локации отмеченные как житницы должны ставить в план то, что даёт
# бонус еды. В основном это земледельческая деревня. Фрукты туда ставить не
# нужно, они мусор даже для этой цели.» Список сырья -- тот же, что у
# продовольственного потенциала, минус фрукты.
GRANARY_FOOD = ("wheat", "rice", "millet", "maize", "legumes", "potato",
                "livestock", "olives", "fish", "wild_game", "fur", "beeswax")


def granary_buildings() -> list[str]:
    """Здания, которые житница ставит: те, что растят еду или сам РГО.

    **Правило измерено, а не выписано по памяти.** Его слово 2026-09-13: «он
    теперь должен добавлять в план на этой локации земледельческую деревню и
    другие здания, которые увеличивают добываемую пищу или в целом добычу РГО.
    Таких зданий немного… Но такие здания есть в других модах, поэтому мод
    должен учитывать подобное.»

    Значит признак -- **модификатор здания**, и три его вида:

    - `local_raw_material_output` -- «в целом добыча РГО» (земледельческая
      деревня, и она же единственная такая в самой игре);
    - `local_monthly_food_modifier` -- еда напрямую (`irrigation_systems`,
      акведук, польдеры, террасы);
    - `local_<сырьё>_output_modifier` по любому продовольственному сырью, кроме
      фруктов (`windmill` -- пшеница, рис, просо).

    **И только те, что сами ничего не производят, плюс деревни.** Иначе сюда
    попадают кожевня, поднимающая скот, и мастерская, поднимающая своё сырьё:
    это производственные домики, они борются за места в обычном плане и в
    житнице им делать нечего. Земледельческая деревня производит скот и всё
    равно здесь -- она и есть то, ради чего он это просил.

    На сборке с чужими модами набор -- 77 зданий, 15 из них игры.
    """
    found: list[tuple[int, str]] = []
    folders = [(0, refs.GAME_COMMON / "building_types")] + [
        (n, common / "building_types")
        for n, (_folder, _name, common) in enumerate(refs.mod_sources(), start=1)]
    for source, folder in folders:
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.txt")):
            if "readme" in path.name.lower():
                continue
            text = path.read_text(encoding="utf-8-sig", errors="replace")
            for match in re.finditer(r"(?m)^([a-z0-9_]+)\s*=\s*\{", text):
                block = eu5data._braced(text, match.end() - 1)
                mods = " ".join(
                    eu5data._braced(block, hit.end() - 1) for hit in
                    re.finditer(r"(?m)^\t(modifier|raw_modifier)\s*=\s*\{", block))
                raises = ("local_raw_material_output" in mods
                          or "local_monthly_food_modifier" in mods
                          or any(f"local_{good}_output_modifier" in mods
                                 for good in GRANARY_FOOD))
                if not raises:
                    continue
                produces = re.search(r"(?m)^\t\t\tproduced\s*=", block)
                village = re.search(r"(?m)^\tis_village\s*=\s*yes", block)
                if produces and not village:
                    continue
                found.append((source, match.group(1)))
    # **Земледельческая деревня первой, и это не косметика.** Круг ставит
    # домики по порядку, пока в локации есть место, а его «в основном это
    # земледельческая деревня» -- это и есть порядок.
    order = {name: i for i, (_s, name) in enumerate(found)}
    seen = {name: source for source, name in found}
    return sorted(seen, key=lambda b: (b != "farming_village", seen[b], order[b]))


def building_reach(building: str) -> str | None:
    """«Может ли эта страна вообще получить это здание», из его `country_potential`.

    **Переводится только то, что переводится без догадок.** `has_advance = X` --
    это `LOCKED[X]`, условие самого продвижения; чистый тег -- он сам. Всё
    прочее (`has_law`, `is_at_war`) -- условие сегодняшнего дня, а не «когда-
    нибудь», и в ворота «на конец» не идёт вовсе: лучше не запереть, чем
    запереть не тем.
    """
    body = COUNTRY_POTENTIALS.get(building)
    if not body:
        return None
    one = re.fullmatch(r"has_advance = ([a-z0-9_]+)", body)
    if one:
        return LOCKED.get(one.group(1))
    # **И «или одно из трёх продвижений».** Три здания держатся на `OR` из
    # нескольких своих продвижений; ворота -- `OR` из их условий, и только если
    # условие есть у каждого: одно незапертое делает здание общедоступным.
    many = re.fullmatch(r"OR = \{ ((?:has_advance = [a-z0-9_]+ ?)+)\}", body)
    if many:
        gates = [LOCKED.get(a) for a in
                 re.findall(r"has_advance = ([a-z0-9_]+)", many.group(1))]
        if gates and all(gates):
            uniq = sorted(set(gates))
            return uniq[0] if len(uniq) == 1 else "OR = { %s }" % " ".join(
                f"AND = {{ {g} }}" for g in uniq)
    if re.fullmatch(r"(?:(?:has_or_had_tag|is_tag) = [A-Za-z0-9_]+\s*)+", body):
        return body if body.count("=") == 1 else f"OR = {{ {body} }}"
    return None


def building_unlocks() -> dict[str, str]:
    """Building -> the advance that unlocks it, the mirror of `unlocks()`."""
    out: dict[str, str] = {}
    for path in advance_files():
        text = path.read_text(encoding="utf-8-sig")
        for block in re.finditer(r"^([a-z0-9_]+)\s*=\s*\{(.*?)^\}", text, re.S | re.M):
            for building in re.findall(r"unlock_building\s*=\s*([a-z0-9_]+)", block.group(2)):
                out[building] = block.group(1)
    return out


BUILDING_UNLOCKS = building_unlocks()


def method_advances(method: eu5data.Method) -> list[str]:
    """Every advance that gates this method: its own, its halves', its building's.

    **A pair's key is `base+improvement` and names no advance.** `copperworking`
    says `unlock_production_method = copper_base`, and the mod's four jewelry
    pairs are keyed `copper_base+amber_enhancement` and the like -- so the lookup
    missed them and Münster was offered a recipe only Mesoamerica can unlock, in
    the «сейчас» plan as much as at the end. Found 2026-09-03, by the owner:
    «этого метода не должно было быть как кандидата в принципе».
    """
    found = []
    for name in (method.key, *method.key.split("+")):
        advance = UNLOCKS.get(name)
        if advance and advance not in found:
            found.append(advance)
    advance = BUILDING_UNLOCKS.get(method.building)
    if advance and advance not in found:
        found.append(advance)
    return found

# **Two buildings the plan treats as always unlocked, at the owner's word.**
# The urban rights arrive with `town_rights_enable` in age 3; the first firearms
# building is age 1 and the first cannon building age 2, so by the time a
# weaponry charter can exist at all both have been buildable for an age or more.
# The plan already ignores that the rights themselves are not researched -- «мы
# же игнорируем тот факт, что гор права ещё не изучены… точно так же должны
# игнорировать» -- and ignoring it on one side while enforcing it on the other is
# what put cannons at zero under a granted weaponry charter.
#
# **Safe because neither building asks anything else of the country.** Both carry
# only rank gates -- `town`, `city`, `megalopolis` -- and no `potential` and no
# `allow`, checked in `production_cannons.txt` and `production_firearms.txt`, so
# the location side still decides where they may stand. Both advances are age 2
# and carry no `potential` either, so waiving them takes nothing from anyone.
#
# **`gun_smith` and not `hand_cannon_guild`, corrected 2026-09-03.** The hand
# cannon guild is age 1 and looked like the earlier firearms building, but its
# advance wants `original_capital ?= { sub_continent = east_asia }` -- putting it
# here handed a Chinese building to every country on the map. `gun_smith` is the
# first firearms building anyone else can have, and it is age 2 exactly as the
# owner said it was.
#
# Deliberately two names and not a rule: the owner asked for these as exceptions,
# and a rule would quietly take in whatever the next patch adds.
ALWAYS_AVAILABLE = ("gun_smith", "cannon_maker")

# **С какого числа провинций грамота становится свойством провинции, а не города.**
# Владелец, 2026-09-12, поиграв: «Меня вообще не устраивает то, когда в одной
# провинции у меня 2-4 вида городского права. Теперь делаем так. Если на
# выбранной земле 9 или больше провинций — расчёт идёт строго 1 гор. право на
# провинцию.» Порог считается по **провинциям выбранной земли**
# (`_plan_provn`), а не по локациям, и это его число, а не выведенное.
RIGHT_PROV_MIN = 9


def dedupe_comments(body: str) -> str:
    """Drop a comment block this file has already carried once.

    The game has no loop over building types, so every branch here is written
    out -- and a block of prose sitting above one branch used to be written out
    with it. One ten-line block appeared **1174 times** in the plan file alone:
    1.62 MB of the mod's 20 MB was the same paragraph, repeated.

    The explanation is not lost -- it lives in this generator, which is where a
    session reads it, and the first occurrence still stands in the output. The
    owner asked what the twenty megabytes were, 2026-09-14, and this was a sixth
    of the answer.
    """
    out: list[str] = []
    seen: set[str] = set()
    block: list[str] = []

    def flush() -> None:
        if not block:
            return
        key = "\n".join(l.strip() for l in block)
        # A block of one bare `#` or a rule of dashes is punctuation, not prose.
        if len(key) > 40 and key in seen:
            block.clear()
            return
        seen.add(key)
        out.extend(block)
        block.clear()

    for line in body.split("\n"):
        if line.lstrip().startswith("#"):
            block.append(line)
        else:
            flush()
            out.append(line)
    flush()
    return "\n".join(out)


def write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(BOM + dedupe_comments(body), encoding="utf-8")


# --------------------------------------------------------------------------
# What the game offers


def methods(game: eu5data.Game) -> list[eu5data.Method]:
    """Every method the game has, and the filter that used to be here is gone.

    **Это оно съело лесопилку.** Здесь стояло

        rows = [m for m in game.methods if m.raw_inputs(game.raw_goods)]

    -- «метод без сырьевого входа бонус взять не может, значит считать в нём
    нечего», -- и `lumber_mill` из `tools = 0.417` и вегетации ни одного
    сырьевого входа не имеет. Метод выбрасывался, здание не попадало в файлы
    мода ни разу, и владелец, поиграв, увидел ровно то, что из этого следует:
    «выбрав древесину в окне редактора и попытаться увеличить его кол-во -- мод
    напишет, что "товар стоит везде где может". Однако... его стоит в целом 0.»
    (2026-09-12). **И он сам же назвал класс**: «раз он не понял это с таким
    простым зданием, значит вполне может быть такое и с какими-то другими».

    **Класс измерен: 15 методов из 705** на сборке с чужими модами --
    `lumber_mill` (лесоматериалы), `forest_village` (дичь, и это одна из
    четырёх деревень), два перегонных (спиртное), `slave_market`, `shoen`,
    `iron_mill/steel_tools` и шесть зданий ND. Ни одного товара целиком это не
    лишало -- лишало лучшего способа его делать.

    **Считать в них есть что, и ветка для этого уже написана.** У такого метода
    `shares()` пуст, поэтому `_g<n>` выходит нулём везде -- `values_file` эту
    ветку знает и подписывает её «a recipe no RGO can feed», -- а `fed_floor`
    равен базе, то есть земля кормит его всегда и нигде не лучше. Это и есть
    честный ответ про лесопилку: ей ничего не нужно, кроме леса, и её
    `location_potential` уже спрашивается через `_stands_<здание>`.

    **Порядок внутри товара это не ломает**: `_m` -- выпуск, и лесопилка (1.0)
    бьёт `shoen` (0.6) и `nd_liv_dampfsagewerk` (0.48) без всякого бонуса.
    Ровно та же логика, по которой `fed_floor` не считает против метода вход,
    который РГО достать не могут: сделанное сырьём не бывает.
    """
    return sorted(game.methods, key=lambda m: (m.produced, m.building, m.key))


def fed_floor(method: eu5data.Method, game: eu5data.Game) -> float:
    """The `_m` a method has to beat before this ground counts as feeding it.

    **Half the bonus the recipe could ever earn, and that is the whole rule.**
    Before it the floor was the unbonused output, so one input out of three was
    enough: the twenty-fifth run's fine cloth put silk weavers at the top of a
    province that has dyes and no silk -- the silk half of the recipe unfed, the
    dyeing half fed, 1.78% of a possible 10 -- and the player's answer was that
    a silk weaver where there is no silk is not an answer at all. It is not a
    number the market can be asked about; the ground is what this mod can see,
    and a recipe whose bulk has to be shipped in is one the ground did not earn.

    Two things fall out of it that are worth keeping straight:

    - **an input the RGOs cannot supply does not count against a method.** The
      ceiling is already only what raw materials could ever add, so fine cloth
      from cloth -- cloth is made, not dug -- asks only for its dyes and passes
      on them. That is the answer the same province gets instead of the silk.
    - **a method with one raw input is unchanged**, because half of its ceiling
      is cleared by that one input or by nothing at all. The rule bites exactly
      where the eighteenth run's did not: recipes with a main ingredient and a
      garnish.

    The floor is put midway between the two nearest sums the goods can actually
    make, rather than at half the ceiling itself, so no combination of inputs can
    land on the boundary and be decided by the fixed point. The narrowest that
    gap gets is 0.12 of a scaled point, on the cannon maker's four inputs, against
    0.00025 of rounding in the `.4f` the script values are written with.
    """
    shares = sorted(v for good, v in method.shares().items()
                    if good in game.raw_goods)
    # **Рецепт, которому сырьё не нужно вовсе, проходит всегда -- и сказать это
    # надо числом, а не нулём.** Потолок у него нуль, половина нуля нуль, и
    # формула ниже возвращает ровно базу -- а `keep()` сравнивает **строго**
    # (`var:_try > floor`), так что метод не проходил бы собственный пол ни в
    # одном ответе с полом. Это второй замок на той же двери, за которой сидела
    # лесопилка: снять фильтр в `methods()` и оставить это -- значит починить
    # наполовину. Земля кормит такой рецепт настолько, насколько его вообще
    # можно кормить, поэтому пол ниже любого мыслимого `_m`.
    if not shares:
        return -1.0
    sums = {0.0}
    for share in shares:
        sums |= {s + share for s in sums}
    target = sum(shares) / 2
    below = max((s for s in sums if s < target), default=0.0)
    above = min((s for s in sums if s >= target), default=target)
    return method.output * RANK_SCALE * (1 + (below + above) / 2 / 100)


def endgame(rows: list[eu5data.Method], game: eu5data.Game) -> set[int]:
    """Which of `rows` are still buildable once every advance is in, by index.

    The game's own ladder, read off `obsolete`: guild -> workshop -> manufactory
    -> mill, thirty chains of it, and a building somebody obsoletes is one nobody
    builds at the end. Ninety-four of the two hundred and eighteen methods
    survive it, and no method that does not survive can beat one that does --
    checked at full bonus over every good and both sides -- so "the best of the
    survivors" is the answer the last age gives.

    **This is a second answer, not a better one.** Along the ladder the inputs
    move: bronze cannons want copper and tin, the cannon factory that replaces
    them wants lead and saltpetre; paper starts on cloth and ends on pure lumber;
    silk fine cloth tops out at 10% and the fine cloth mill at 0.63%. Fourteen of
    the forty-two goods shift their mix, five change it outright -- and for those
    the province that suits the guild is not the province that suits the mill,
    which is the whole reason a row carries both numbers.
    """
    return {index for index, method in enumerate(rows, start=1)
            if method.building not in game.obsoleted}


def goods_split(rows: list[eu5data.Method], game: eu5data.Game) -> dict[str, list[str]]:
    """The goods worth asking about, split into the two piles the player thinks in.

    A raw material is something an RGO also produces -- so a mason's yard and a
    quarry both make masonry, and the question "where should I make it" is a
    different one from "where should I make cannons".
    """
    goods = sorted({m.produced for m in rows})
    split = {
        "raw": [g for g in goods if g in game.raw_goods],
        "made": [g for g in goods if g not in game.raw_goods],
    }
    over = {k: len(v) for k, v in split.items() if len(v) > LIST_CAP}
    if over:
        raise SystemExit(f"a goods list is taller than CMM holds: {over}")
    return split


# --------------------------------------------------------------------------
# Output


def regions() -> dict[str, list[str]]:
    """Continent -> region keys, read off the game's own region localization.

    The file carries the hierarchy in its comments and it is the only place in
    `reference/` that knows it, because `map_data` is not in the tree. Two
    cautions, both paid for: five real regions sit under "Subcontinents" and
    `poland` is a region without the `_region` suffix, so the suffix is honoured
    wherever it appears and the Regions section counts on its own; and filtering
    water by name throws out `north_atlantic_islands_region`, which is dry land,
    so the file's own "Ocean Subcontinent" grouping does that job instead.
    """
    path = refs.GAME_LOCALIZATION / "english/region_names_l_english.yml"
    out: dict[str, list[str]] = {}
    seen: set[str] = set()
    section = continent = group = None
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("l_english"):
            continue
        indent = len(line) - len(line.lstrip())
        if stripped.startswith("#"):
            name = stripped.lstrip("#").strip()
            if indent <= 1:
                section, continent, group = name, None, None
            elif indent <= 2:
                continent, group = name, None
            else:
                group = name
            continue
        match = re.match(r"^([a-z0-9_]+):", stripped)
        if not match or continent is None:
            continue
        key = match.group(1)
        if not (key.endswith("_region") or section == "Regions"):
            continue
        if group == "Ocean Subcontinent" or key in seen:
            continue
        seen.add(key)
        out.setdefault(continent.lower(), []).append(key)
    over = {c: len(r) for c, r in out.items() if len(r) > LIST_CAP}
    if over:
        raise SystemExit(f"a continent has more regions than a CMM list holds: {over}")
    return {c: r for c, r in out.items() if c in CONTINENTS}


def region_file(by_continent: dict[str, list[str]]) -> str:
    """The regions, one list per continent, all on the zone tab.

    Ticking a whole continent paints the screen red and is a blunt frame; the
    good case is one region ticked, its ground offered and everything else left
    alone, with a neighbour addable beside it. Both are here: a continent row and
    a region row do the same thing to the same list.
    """
    out = [HEADER, "#\n# Scope: country\n"]
    for continent, keys in by_continent.items():
        out.append(f"""
{MOD_ID}_register_region_{continent}_list = {{
\tcmm_register_settings_list = {{
\t\tmod_id = {MOD_ID}
\t\tsetting_id = region_{continent}
\t\ttab_id = {TAB_ZONE}
\t\titem_count = {len(keys)}
\t\tis_ordered = 0
\t}}

""")
        for index, key in enumerate(keys, start=1):
            out.append(f"\tcmm_set_list_item_value = {{ mod_id = {MOD_ID} "
                       f"setting_id = region_{continent} item = {index} value = region:{key} }}\n")
        out.append("\n")
        for index, key in enumerate(keys, start=1):
            out.append(f"\tset_variable = {{ name = {MOD_ID}__region_{continent}_i{index}_name "
                       f"value = flag:{key} }}\n")
        out.append(f"""
\tcmm_register_list_bool_field = {{
\t\tmod_id = {MOD_ID}
\t\tsetting_id = region_{continent}
\t\tfield_id = pick
\t\tdefault_value = 0
\t}}
}}
""")

    out.append(f"\n# Scope: country\n{MOD_ID}_register_region_lists = {{\n")
    for continent in by_continent:
        out.append(f"\t{MOD_ID}_register_region_{continent}_list = yes\n")
    out.append("}\n")

    out.append(f"""
# The ticked regions, gathered beside the ticked continents. Both narrow the same
# search; a region is simply the finer of the two.
# Scope: country
{MOD_ID}_rebuild_regions = {{
\tclear_global_variable_list = {MOD_ID}_regions
\tset_global_variable = {{ name = {MOD_ID}_region_count value = 0 }}
""")
    for continent in by_continent:
        out.append(f"""\tif = {{
\t\tlimit = {{ has_variable_list = cmm_list_items_{MOD_ID}__region_{continent} }}
\t\tcmm_build_list_bool_list = {{ setting = {MOD_ID}__region_{continent} field_slot = 1 list_name = {MOD_ID}_region_{continent}_ticks }}
\t\tevery_in_list = {{
\t\t\tvariable = {MOD_ID}_region_{continent}_ticks
\t\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_regions target = this }}
\t\t\tchange_global_variable = {{ name = {MOD_ID}_region_count add = 1 }}
\t\t}}
\t}}
""")
    out.append("}\n")

    out.append(f"""
# Every land location of the ticked regions, for the ranking's fallback.
# Scope: country
{MOD_ID}_collect_regions = {{
\tevery_in_global_list = {{
\t\tvariable = {MOD_ID}_regions
\t\tevery_location_in_region = {{
\t\t\tlimit = {{ {MOD_ID}_is_candidate = yes }}
\t\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_candidates target = this }}
\t\t\tchange_global_variable = {{ name = {MOD_ID}_candidate_count add = 1 }}
\t\t}}
\t}}
}}
""")
    return "".join(out)


def clear_ticks_effect() -> str:
    """«Сбросить пометки город/село» -- по всему миру, разом.

    **Он существует, потому что различить их было нечем.** 2026-09-02: тумблеры
    стояли на четырнадцати локациях Трансильвании, он сбросил те, что видел в
    окне -- валашские, -- расширил область и пересчитал; трансильванские вошли в
    план впервые, встали наверх списка городами, и это неотличимо от «тумблеры
    вернулись сами». Отчёт это развёл (`docs/TESTLOG.md`), но развести должно
    было окно, а не отчёт.

    По всем пяти континентам, а не по отмеченным: пометка живёт на локации и
    переживает сохранение, поэтому «сбросить» обязано значить «везде», иначе
    остаётся ровно та же ловушка. Один обход по нажатию кнопки, без единого
    скриптового значения в `limit`, -- цена, которую платят раз.
    """
    walks = "".join(f"""\tcontinent:{name} = {{
\t\tevery_location_in_continent = {{
\t\t\tlimit = {{ OR = {{
\t\t\t\thas_variable = {MOD_ID}_force_town
\t\t\t\thas_variable = {MOD_ID}_force_rural
\t\t\t}} }}
\t\t\tremove_variable = {MOD_ID}_force_town
\t\t\tremove_variable = {MOD_ID}_force_rural
\t\t\tchange_global_variable = {{ name = {MOD_ID}_tick_count add = 1 }}
\t\t}}
\t}}
""" for name in CONTINENTS)
    return f"""#
# «Сбросить пометки город/село», по всему миру.
#
# The tick is a location variable and it outlives a save, so a reset that
# covered only what is on screen would leave the same trap it exists to remove:
# 2026-09-02 he cleared the fourteen he could see, widened the ground, and the
# fourteen he could not came into the plan looking exactly like a revert.
#
# Scope: country
{MOD_ID}_clear_ticks = {{
\tset_global_variable = {{ name = {MOD_ID}_tick_count value = 0 }}
{walks}}}
"""


def food_potential_file() -> str:
    """Продовольственный потенциал локации -- формула CM, переписанная под себя.

    Его слово, 2026-09-09: «у CM есть режим карты, который считает
    продовольственный потенциал... хочу, чтобы в плане в строке каждой локации,
    которая производит пищу, был указан этот продовольственный потенциал».

    **Копируется, а не зовётся, и вот почему это здесь честно.** Три значения CM
    (`cm_location_food_potential` и два его множителя) -- чистая функция локации:
    `raw_material.food_value`, `modifier:local_*`, `development`,
    `location_building_level`, `has_river`. Ни одной его переменной, ни одного
    его состояния. Значит копия даёт то же число, а мод остаётся рабочим без CM
    -- имя, которого нет, ломается не там, где его ищут.

    **И копируется генератором, а не руками**: текст берётся из его файла на
    сборке и переименовывается. Обновит CM формулу -- пересборка возьмёт новую;
    уйдёт CM из дерева -- значение станет нулём, и столбец просто не появится.
    """
    src = None
    for _folder, _name, common in refs.mod_sources():
        path = common / "script_values/cm_filter_script_values.txt"
        if path.is_file():
            src = path.read_text(encoding="utf-8-sig")
            break
    out = [HEADER, "#\n"]
    if src is None or "cm_location_food_potential = {" not in (src or ""):
        out.append("# Construction Manager не в дереве -- считать нечего.\n"
                   f"# Scope: location\n{MOD_ID}_food_potential = {{\n\tvalue = 0\n}}\n")
        return "".join(out)
    names = ("cm_location_food_potential_food_multiplier",
             "cm_location_food_potential_raw_output_multiplier",
             "cm_location_food_potential")
    for name in names:
        start = src.index(f"\n{name} = {{")
        depth, i = 0, src.index("{", start)
        while i < len(src):
            depth += (src[i] == "{") - (src[i] == "}")
            if depth == 0:
                break
            i += 1
        body = src[start:i + 1]
        for cm_name in names:
            body = body.replace(cm_name, f"{MOD_ID}_fp_{cm_name[len('cm_location_food_potential'):].strip('_') or 'value'}")
        out.append(f"\n# Scope: location\n# Списано с `{name}` (Construction Manager) на сборке.\n")
        out.append(body.strip() + "\n")
    out.append(f"""
# То же число, но округлённое до сотых и в целых: строка плана печатает целое.
# Scope: location
{MOD_ID}_food_potential = {{
\tvalue = {MOD_ID}_fp_value
\tmultiply = 100
}}
""")
    return "".join(out)


def sources_file(rows: list[eu5data.Method]) -> str:
    """Список модов, из которых мод взял здания, галочкой на каждый.

    Его слово, 2026-09-09: «в настройках мода должна быть секция, в которой будет
    отображаться список модов из которых наш мод подхватил какие-либо сооружения.
    В этом списке мы можем нажать галочку включить или выключить использование
    этих зданий в наших планах».

    **Список -- только те моды, чьё здание правда попало в пул.** Мод, который
    ничего производственного не даёт, строкой не будет: пустая галочка -- это
    вопрос без ответа.

    **Снятая галочка не убирает здание из файлов, а закрывает ему ворота.**
    Скрипт написан на сборке и другим уже не станет; `_src<k>` стоит в `_avail_`
    и в `_reach_` каждого метода этого мода, то есть и «на сейчас», и «на конец».
    По умолчанию включено: он их для того и просил.

    **Порядок и номера -- от `refs.mod_sources`**, папка за папкой. Мод, ушедший
    из дерева, сдвинул бы номера; поэтому пересборка после смены плейсета
    обязательна, как и для всего остального здесь.
    """
    used = sorted({source_of(m.building) for m in rows} - {0})
    named = {n: (folder, name) for n, (folder, name, _c)
             in enumerate(refs.mod_sources(), start=1)}
    out = [HEADER, f"""#
# Scope: country
{MOD_ID}_register_source_list = {{
"""]
    if not used:
        out.append("\t# Ни один мод дерева не дал плану здания -- списка нет.\n}\n")
        out.append(f"\n# Scope: country\n{MOD_ID}_rebuild_sources = {{\n}}\n")
        return "".join(out)
    out.append(f"""\tcmm_register_settings_list = {{
\t\tmod_id = {MOD_ID}
\t\tsetting_id = source
\t\ttab_id = tech
\t\titem_count = {len(used)}
\t\tis_ordered = 0
\t}}

""")
    for index, number in enumerate(used, start=1):
        folder, _name = named[number]
        out.append(f"\tcmm_set_list_item_value = {{ mod_id = {MOD_ID} "
                   f"setting_id = source item = {index} value = flag:{MOD_ID}_src_{folder} }}\n")
    out.append("\n")
    for index, number in enumerate(used, start=1):
        folder, _name = named[number]
        out.append(f"\tset_variable = {{ name = {MOD_ID}__source_i{index}_name "
                   f"value = flag:{MOD_ID}_src_{folder} }}\n")
    out.append(f"""
\tcmm_register_list_bool_field = {{
\t\tmod_id = {MOD_ID}
\t\tsetting_id = source
\t\tfield_id = pick
\t\tdefault_value = 1
\t}}
}}

# Галочки в числа, которые читают ворота методов.
#
# **До первой регистрации все включены.** Глобалки, которой нет, ворота читают
# как ложь, и здания чужих модов исчезли бы из плана молча -- то есть ровно так,
# как выглядит поломка.
# Scope: country
{MOD_ID}_rebuild_sources = {{
""")
    for number in used:
        out.append(f"\tset_global_variable = {{ name = {MOD_ID}_src{number} value = 1 }}\n")
    out.append(f"""\tif = {{
\t\tlimit = {{ has_variable_list = cmm_list_items_{MOD_ID}__source }}
\t\tclear_global_variable_list = {MOD_ID}_source_ticks
\t\tcmm_build_list_bool_list = {{ setting = {MOD_ID}__source field_slot = 1 list_name = {MOD_ID}_source_ticked }}
\t\tevery_in_list = {{
\t\t\tvariable = {MOD_ID}_source_ticked
\t\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_source_ticks target = this }}
\t\t}}
""")
    for number in used:
        folder, _name = named[number]
        out.append(f"""\t\tset_global_variable = {{ name = {MOD_ID}_src{number} value = 0 }}
\t\tif = {{
\t\t\tlimit = {{ is_target_in_global_variable_list = {{ name = {MOD_ID}_source_ticks target = flag:{MOD_ID}_src_{folder} }} }}
\t\t\tset_global_variable = {{ name = {MOD_ID}_src{number} value = 1 }}
\t\t}}
""")
    out.append("\t}\n}\n")
    return "".join(out)


def zone_file() -> str:
    """The zone: the continents to look inside, ticked.

    There is nothing to walk here. A location's continent is a plain trigger --
    `continent = continent:europe`, which vanilla uses seventy times -- so
    membership is asked at the moment it matters instead of being marked onto
    every location of a continent in advance. An earlier version did the walk,
    and ticking Europe would have meant setting a variable on some thousands of
    locations for nothing.
    """
    out = [HEADER, f"""#
# Scope: country
{MOD_ID}_register_zone_list = {{
\tcmm_register_settings_list = {{
\t\tmod_id = {MOD_ID}
\t\tsetting_id = continent
\t\ttab_id = {TAB_ZONE}
\t\titem_count = {len(CONTINENTS)}
\t\tis_ordered = 0
\t}}

"""]
    for index, key in enumerate(CONTINENTS, start=1):
        out.append(f"\tcmm_set_list_item_value = {{ mod_id = {MOD_ID} "
                   f"setting_id = continent item = {index} value = continent:{key} }}\n")
    out.append("\n")
    for index, key in enumerate(CONTINENTS, start=1):
        # The game's own key, so the row arrives named in the player's language
        # and nothing here carries a copy of it.
        out.append(f"\tset_variable = {{ name = {MOD_ID}__continent_i{index}_name "
                   f"value = flag:{key} }}\n")
    out.append(f"""
\tcmm_register_list_bool_field = {{
\t\tmod_id = {MOD_ID}
\t\tsetting_id = continent
\t\tfield_id = pick
\t\tdefault_value = 0
\t}}
}}

# Scope: country
{MOD_ID}_rebuild_zone = {{
\tclear_global_variable_list = {MOD_ID}_continents
\tset_global_variable = {{ name = {MOD_ID}_zone_count value = 0 }}

\tif = {{
\t\t# Registration may not have completed yet on the first pass.
\t\tlimit = {{ has_variable_list = cmm_list_items_{MOD_ID}__continent }}
\t\tcmm_build_list_bool_list = {{ setting = {MOD_ID}__continent field_slot = 1 list_name = {MOD_ID}_zone_ticks }}
\t\tevery_in_list = {{
\t\t\tvariable = {MOD_ID}_zone_ticks
\t\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_continents target = this }}
\t\t\tchange_global_variable = {{ name = {MOD_ID}_zone_count add = 1 }}
\t\t}}
\t}}
}}

# Every land location of the ticked continents, for when the player ranks a whole
# continent without narrowing it first.
# Scope: country
{MOD_ID}_collect_zone = {{
\tevery_in_global_list = {{
\t\tvariable = {MOD_ID}_continents
\t\tevery_location_in_continent = {{
\t\t\tlimit = {{ {MOD_ID}_is_candidate = yes }}
\t\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_candidates target = this }}
\t\t\tchange_global_variable = {{ name = {MOD_ID}_candidate_count add = 1 }}
\t\t}}
\t}}
}}
""")
    return "".join(out)


def triggers_file(rows, split, game) -> str:
    out = [HEADER, f"""#
# Whether the map picker and the ranking offer this location at all.
#
# The ticked continents narrow it; with nothing ticked the whole world is on
# offer, because a picker that shows nothing until a checkbox somewhere else is
# set looks broken rather than empty. Ownership is deliberately never asked --
# the whole use is planning for ground that is not yours yet.
#
# Scope: location
{MOD_ID}_in_zone = {{
\tOR = {{
\t\tAND = {{
\t\t\tglobal_var:{MOD_ID}_zone_count = 0
\t\t\tglobal_var:{MOD_ID}_region_count = 0
\t\t}}
\t\tregion = {{ is_target_in_global_variable_list = {{ name = {MOD_ID}_regions target = this }} }}
"""]
    for key in CONTINENTS:
        out.append(f"""\t\tAND = {{
\t\t\tcontinent = continent:{key}
\t\t\tis_target_in_global_variable_list = {{ name = {MOD_ID}_continents target = continent:{key} }}
\t\t}}
""")
    out.append("\t}\n}\n")

    # **«Только там, где здание может стоять» is gone, 2026-09-06, and its
    # triggers with it.** It was a tick on the mod page, then a circle in the
    # ranking window, and he threw it out with three reasons at once: «её
    # название не даёт смысл того, что она действительно делает», it did not
    # work, and «она вообще не нужна». What he wanted in its place is «Выбрать
    # мою землю», which is a button and needs none of this. `_stands_<building>`
    # stays -- the scorer asks it per method, which is the honest place for it.
    order = [good for kind in ("raw", "made") for good in split[kind]]

    # Which methods this country may actually run.
    #
    # 119 buildings in the game are unlocked by an advance with an age on it, and
    # ten production methods are unlocked separately, so `can_build_building` in
    # *country* scope -- "country checks the country scope requirements" -- is
    # what answers "is this available to me now". Without it the table happily
    # recommends a method three ages away, which is what the owner saw on beer.
    # **What no advance can ever bring, and the «на конец» side has to ask it.**
    # An advance carrying a `potential` is not one you will hold eventually -- it
    # is one you will never hold. Without this the end-game plan offered every
    # country everything: five porcelain guilds in northern Germany, whose kiln
    # wants an east-Asian capital.
    # **Only the gated ones are written**, and `score_file` only asks where one
    # exists. `_reach_<n>` answers "could this country ever take the advance
    # behind this method"; for all but thirteen of the 241 the answer is yes by
    # construction, and writing those out was 228 scripted triggers saying
    # `always = yes` that the engine parses on every load and nothing ever calls.
    reach = {index: method_gates(method)
             for index, method in enumerate(rows, start=1)}
    reach = {index: gates for index, gates in reach.items() if gates}
    out.append(f"\n# The {len(reach)} methods of {len(rows)} behind an advance somebody can never "
               f"take.\n# The rest are reachable by construction and are not written out.\n"
               f"# Scope: country\n")
    for index, gates in reach.items():
        method = rows[index - 1]
        body = "".join(f"\tAND = {{ {gate} }}\n" for gate in gates)
        out.append(f"# {method.building} / {method.key}: "
                   f"{', '.join(a for a in method_advances(method) if a in LOCKED)}\n"
                   f"{MOD_ID}_reach_{index} = {{\n{body}}}\n")

    out.append("\n# Scope: country\n")
    for index, method in enumerate(rows, start=1):
        if method.building in ALWAYS_AVAILABLE:
            out.append(f"# {method.building}: taken as given, `generate.ALWAYS_AVAILABLE`.\n"
                       f"{MOD_ID}_avail_{index} = {{\n\talways = yes\n}}\n")
            continue
        # `can_build_building` in country scope already answers the building's
        # own advance; this adds the *method's*, and `method_advances` is what
        # finds it through a pair's `base+improvement` key.
        extra = "".join(f"\n\thas_advance = {gate}" for gate in method_advances(method)
                        if gate in UNLOCKS.values())
        source = source_of(method.building)
        if source:
            extra += f"\n\tglobal_var:{MOD_ID}_src{source} = 1"
        # Страновая половина `allow` самого метода -- та же, что в `_reach_`:
        # она не про возраст, а про то, случилось ли с этой державой событие.
        own_allow, _ = method_allow_gates(method)
        if own_allow:
            extra += f"\n\t{own_allow}"
        out.append(f"{MOD_ID}_avail_{index} = {{\n"
                   f"\tcan_build_building = building_type:{method.building}{extra}\n}}\n")

    # **The plan simulates ranks, and this is where.** The owner, 2026-09-02:
    # «Расчёт должен симулировать ранги. Если я поставил там город в моде — он
    # должен воспринимать это как город, значит должен дать права, должен
    # поставить нужные дома. И не важно что там стоит на самом деле.»
    #
    # `can_build_building` in a location's scope answers two things at once: the
    # rank flags a building declares (`town = yes`), and its `location_potential`
    # -- the terrain, the market and the one-RGO-per-location rule. **The tick is
    # meant to override the first and nothing else**, so where a location carries
    # one, this asks the potential directly and lets the tick answer the rank.
    #
    # That is the whole of the 2026-09-02 diagnosis: a ticked village was scored
    # as a town, granted a mandatory urban right, and then refused every guild --
    # `w=3` of 17 towns for twenty different goods, and the charter came out
    # half-made every time.
    #
    # Where the potential names a scope this one has not got -- `scope:actor`,
    # two buildings of a hundred and ten -- the game is asked as before. A
    # condition evaluated wrong is worse than a condition not overridden.
    # **Житница Construction Manager -- локация, которую план не трогает вовсе.**
    #
    # Владелец, 2026-09-09: «в CM есть функция, которая переключает выбранную
    # локацию в режим "житницы"... Задача мода прочитать эти локации и выключить
    # их из плана в плане строительства, но при этом считать РГО которые они
    # дают и бонус земли тоже случайно не убрать».
    #
    # **Признак -- переменная CM, а не его имя.** `cm_auto_food_location_enabled`
    # ставит `cm_set_auto_food_for_location`, ручное включение по одной локации;
    # нет CM -- переменной нет, и трогать план нечему. Массовое покрытие по виду
    # сырья сюда намеренно не входит: у него свой речной фильтр, повторять
    # который значило бы гадать за CM.
    #
    # **Из плана она выпадает только как место.** В `_candidates` она остаётся,
    # поэтому её РГО считается в `_nrgo<n>` как раньше, а выгода провинции
    # спрашивает `any_location_in_province_definition` и наших списков не знает
    # вовсе -- земля платит соседям столько же, сколько платила.
    out.append(f"""
# Scope: location
{MOD_ID}_is_granary = {{
\thas_variable = cm_auto_food_location_enabled
}}
""")

    out.append(f"""
# **Там, где локация правда добывает еду, и нигде больше.**
#
# **Этот триггер три недели лежал в файле эффектов и потому не работал ни разу.**
# Кнопка житницы показывалась на каждой локации подряд, и владелец сказал об
# этом дважды -- сначала «убери её оттуда, где не добывается еда при помощи
# РГО», потом «кнопка житниц всё так же на всех локациях отображается», уже
# после того, как условие было переписано. Условие было ни при чём: `.txt` в
# `common/scripted_effects` триггером не становится, как бы он ни выглядел.
# **Теперь это ловит `check_script.py`.**
#
# Само условие -- тот же факт, которым рисуется число продовольственного
# потенциала: `_food_pot` стоит на локации ровно тогда, когда `_food_potential`
# больше нуля. Один факт -- одно место, где он считается; два списка разошлись
# бы, и один из них уже расходился (дичи в списке CM нет, а в потенциале она
# есть).
# Scope: location
{MOD_ID}_is_food_loc = {{
\thas_variable = {MOD_ID}_food_pot
}}
""")
    out.append("\n# Scope: location\n")
    seen: dict[str, eu5data.Method] = {}
    for method in rows:
        seen.setdefault(method.building, method)
    for building, method in sorted(seen.items()):
        potential = " ".join(method.potential.split())
        # Two reasons to leave a building alone and ask the game as before: it
        # is gated by something besides the rank and the potential, or its
        # potential names a scope this one has not got. Twelve buildings of a
        # hundred and ten, all of them exotic -- a Japanese reform, an English
        # tag, the Spanish cloth industry.
        if method.extra_gates or "scope:" in potential:
            why = ("an `allow` or a `country_potential` gates it besides the rank"
                   if method.extra_gates else
                   "its potential names a scope this one has not got")
            out.append(f"# {why}, so the tick does not override it.\n"
                       f"{MOD_ID}_stands_{building} = {{\n"
                       f"\tcan_build_building = building_type:{building}\n}}\n")
        elif not potential:
            # The rank is the whole of what the game checks here, and the tick is
            # the answer to the rank. This is the manufacturing ladder.
            out.append(f"{MOD_ID}_stands_{building} = {{\n"
                       f"\tOR = {{\n"
                       f"\t\t{MOD_ID}_rank_is_ticked = yes\n"
                       f"\t\tcan_build_building = building_type:{building}\n"
                       f"\t}}\n}}\n")
        else:
            out.append(f"""{MOD_ID}_stands_{building} = {{
\tOR = {{
\t\tAND = {{
\t\t\t{MOD_ID}_rank_is_ticked = no
\t\t\tcan_build_building = building_type:{building}
\t\t}}
\t\tAND = {{
\t\t\t{MOD_ID}_rank_is_ticked = yes
\t\t\t# the building's own `location_potential`, copied from the game
\t\t\t{potential}
\t\t}}
\t}}
}}
""")

    # **Ворота локации, которые метод несёт сам.** Пять крепостных житниц
    # спрашивают рынок локации: пшеничная стоит только там, где рынок даёт
    # пшеницу. `_stands_<здание>` -- про здание и общий на все его методы,
    # поэтому этим пяти нужен свой: `_mstands_<n>`, и `score_file` спрашивает
    # его вместо `_stands_` ровно там, где он написан (`method_allows`).
    own = {index: method_allow_gates(method)[1]
           for index, method in enumerate(rows, start=1)}
    own = {index: gate for index, gate in own.items() if gate}
    if own:
        out.append(f"\n# The {len(own)} method(s) whose own `allow` asks something "
                   f"of the location.\n# Scope: location\n")
    for index, gate in own.items():
        method = rows[index - 1]
        out.append(f"# {method.building} / {method.key}\n"
                   f"{MOD_ID}_mstands_{index} = {{\n"
                   f"\t{MOD_ID}_stands_{method.building} = yes\n"
                   f"\t{gate}\n}}\n")

    return "".join(out)


def picker_file(split: dict[str, list[str]], rows: list[eu5data.Method]) -> str:
    """The good the search answers for, set straight from the window's own cell.

    **This was 47 branches of tick-parsing and it is four lines a good now.**
    Until 2026-09-06 the good was chosen on the mod's settings page, in two CMM
    lists, and everything here existed to turn a tick into one number:
    `cmm_build_list_bool_list` handed back the ticked goods as scopes,
    `if = { limit = { this = goods:clay } }` turned a scope into an index, and
    a second pass forced every other row off. His words, 2026-09-06: «просто
    добавишь в окно расчёта иконки товаров и прав как ты это сделал в редакторе
    и поставишь каждому кружочек для активации нужного, далее кнопку искать
    локации, всё» -- and he was right, because the whole machine only ever
    produced `bag_wtp_good_index`, which a window can write itself.

    So a cell in `bag_wtp_pick_cells.gui` calls the effect for its own number.
    **The selection is also a flag per good**, `_sel<n>`, because that is what
    the cell's circle reads: a checkbutton's `down` takes a boolean, and
    `.IsSet` on a variable is the one this mod has already proved on screen.
    """
    order = goods_order(split)
    out = [HEADER, f"""#
# One good at a time, and a right is the other answer to the same question --
# so setting either clears the other. `{MOD_ID}_good_index` is what the ranking
# pass reads; `_sel<n>` is what the circle in the window draws itself from.
#
# The `root`s that used to be here are gone with the CMM callbacks that made
# them safe: every effect below is called from a scripted GUI in the country's
# own scope.

# Every good's circle off. One press writes one on again.
# Scope: country
{MOD_ID}_clear_good_sel = {{
"""]
    for i in range(1, len(order) + 1):
        out.append(f"\tremove_global_variable = {MOD_ID}_sel{i}\n")
    out.append("}\n")

    # **The circle and the stored answer, made to agree.** `_good_index` outlives
    # a save and `_sel<n>` was only invented on 2026-09-06, so the first load
    # after this build would otherwise show a chosen good with no circle on it --
    # and state the player can neither see nor clear is this mod's own fault
    # twice over (`docs/pitfalls/diagnosis.md`). Run from the registration hook,
    # which fires on load; a press writes both anyway.
    out.append(f"""
# Scope: country
{MOD_ID}_sync_sel = {{
\t{MOD_ID}_clear_good_sel = yes
\t{MOD_ID}_clear_right_sel = yes
""")
    for i in range(1, len(order) + 1):
        keyword = "if" if i == 1 else "else_if"
        out.append(f"\t{keyword} = {{ limit = {{ var:{MOD_ID}_good_index = {i} }} "
                   f"set_global_variable = {{ name = {MOD_ID}_sel{i} value = 1 }} }}\n")
    out.append(f"\t{MOD_ID}_sync_right_sel = yes\n}}\n")

    for i, good in enumerate(order, start=1):
        out.append(f"""
# {good}
# Scope: country
{MOD_ID}_set_good_{i} = {{
\t{MOD_ID}_clear_good_sel = yes
\t{MOD_ID}_clear_right_sel = yes
\tset_variable = {{ name = {MOD_ID}_good_index value = {i} }}
\tset_global_variable = {{ name = {MOD_ID}_good_index value = {i} }}
\tset_global_variable = {{ name = {MOD_ID}_good value = goods:{good} }}
\tset_global_variable = {{ name = {MOD_ID}_sel{i} value = 1 }}

\t# A right and a good are two answers to one question.
\tset_variable = {{ name = {MOD_ID}_right_index value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_right_index value = 0 }}

\t# The table on screen answered for the good before this one. Clearing it is
\t# the honest state: «Искать локации» is what fills it again.
\t{MOD_ID}_clear_rows = yes
}}
""")
    return "".join(out)


def values_file(rows: list[eu5data.Method], split: dict[str, list[str]],
                game: eu5data.Game) -> str:
    """Two script values per method: what it would be worth here, and the bonus.

    **What it is worth is what it produces, not what percentage it gains.** The
    eighth run put a forest village at the top of a weaponry search: one raw
    input, a full 10%, and 0.2 goods a level against a weapon guild's 1.0. The
    bonus is production efficiency, so it multiplies output rather than standing
    in for it:

        effective output = output * (1 + bonus / 100)
        RGO bonus %      = {max:g} * (input amounts the province supplies) / (all inputs)

    Both divisions are done here, at generation time, so a location costs one
    addition per raw material the method wants.

    The province, not the location: the game credits a raw material worked
    anywhere in it -- and the whole province definition, both sides of any border
    that currently cuts it, because that is the ground once it is yours. Every
    input counts towards the denominator, produced goods included: an RGO can
    never supply tools, but tools still carry their weight, which is why a method
    can top out well below {max:g}%.
    """
    # **What a good's gain is measured against: the best any recipe of that good
    # could ever earn, and not the recipe's own ceiling.** Dividing by its own was
    # the fault of 2026-09-03: a `fine_cloth_guild` running the plain base with a
    # fur trim has one raw input, fur, and a ceiling of 2.86% -- so a province
    # with fur and nothing else fed it whole and it scored **1000**, the same as a
    # perfect wool province, for 2.86% on an output of 0.7. «Туда встало тонкое
    # сукно... но там ничего для него нет, только мех для улучшения.»
    #
    # Against the good's best (10% for fine cloth) the same recipe reads 286 and a
    # wool province reads 833, which is the order he expects. **The reason to
    # normalize at all is untouched**: it is so a good whose *best* recipe tops
    # out at 5% still competes with one that reaches 10%, and that divisor is the
    # good's, not the method's.
    best_ceiling: dict[str, float] = {}
    for method in rows:
        best_ceiling[method.produced] = max(best_ceiling.get(method.produced, 0.0),
                                            method.ceiling(game.raw_goods))
    out = [HEADER, f"""#
# `{MOD_ID}_m<n>` ranks -- effective output. `{MOD_ID}_b<n>` is the bonus the row
# prints. Nothing reads `_b` until a method has won a row, so it costs nothing
# per candidate.
#
# **`_m` is the output times {RANK_SCALE}, and that is what makes it sortable.** In its own
# units a scriptorium runs from 0.3000 to 0.3129 across the whole of Europe, and
# ranking on that came back in map order: every `order_by` in the game and in
# every mod in `reference/` sorts on numbers in the thousands -- vanilla on
# `military_strength` and `country_tax_base`, Advanced Auto Build on a score
# built out of `add = 12000` -- and none on a fraction. Scaled, the same
# scriptorium runs 300.00 to 312.88 and the provinces separate. Nothing prints
# `_m`: the row's `×` is the method's own output, written out unscaled by
# `{MOD_ID}_store_winner`.
""".format(max=eu5data.RGO_MAX_BONUS)]
    for index, method in enumerate(rows, start=1):
        ceiling = method.ceiling(game.raw_goods)
        # What one raw material is worth here, in bonus points. For a building
        # that runs two methods at once this is already blended across the two
        # -- see `eu5data.Method.shares`.
        shares = {good: share for good, share in method.shares().items()
                  if good in game.raw_goods}
        out.append(f"\n# {method.building} / {method.key} -> {method.produced}, "
                   f"output {method.output:g}, ceiling {ceiling:.2f}% of the "
                   f"good's {best_ceiling.get(method.produced, 0.0):.2f}% "
                   f"-> at best {method.output * (1 + ceiling / 100):.4f}\n")
        out.append(f"# Scope: location\n{MOD_ID}_m{index} = {{\n"
                   f"\tvalue = {method.output * RANK_SCALE:.4f}\n")
        for good, share in sorted(shares.items()):
            out.append(f"""\tif = {{
\t\tlimit = {{ province_definition = {{ any_location_in_province_definition = {{ raw_material = goods:{good} }} }} }}
\t\tadd = {method.output * RANK_SCALE * share / 100:.4f}
\t}}
""")
        out.append("}\n")
        out.append(f"# Scope: location\n{MOD_ID}_b{index} = {{\n\tvalue = 0\n")
        for good, share in sorted(shares.items()):
            out.append(f"""\tif = {{
\t\tlimit = {{ province_definition = {{ any_location_in_province_definition = {{ raw_material = goods:{good} }} }} }}
\t\tadd = {share:.4f}
\t}}
""")
        out.append("}\n")
        # **What the plan deals the ground by**: how much of the bonus this
        # *good* could ever earn, this recipe earns here. A raw bonus does not
        # compare across goods -- the ceilings run from 2% to 10% and five goods
        # are capped under five -- and a `worth` normalized to the good's own best
        # on this ground compares even worse, squeezing everything into
        # 0.909-1.000. The divisor is the good's best ceiling in the game, for the
        # reason written where `best_ceiling` is built.
        divisor = best_ceiling.get(method.produced, 0.0)
        if divisor > 0:
            out.append(f"# Scope: location\n{MOD_ID}_g{index} = {{\n\tvalue = 0\n")
            for good, share in sorted(shares.items()):
                out.append(f"""\tif = {{
\t\tlimit = {{ province_definition = {{ any_location_in_province_definition = {{ raw_material = goods:{good} }} }} }}
\t\tadd = {share * RANK_SCALE / divisor:.4f}
\t}}
""")
            out.append("}\n")
        else:
            out.append(f"# A recipe no RGO can feed: its gain is nought everywhere.\n"
                       f"# Scope: location\n{MOD_ID}_g{index} = {{ value = 0 }}\n")

    # The plan's orderings. `order_by` takes a script value and never a variable,
    # so "what is this ground worth to this good" needs a name of its own -- one
    # per good per side, plus a third that is the better of the two, which is
    # what the good is normalized by. `bag_wtp_generated_plan.txt` fills the
    # variables behind them.
    order = [g for kind in ("raw", "made") for g in split[kind]]
    plan_values = []
    for index, good in enumerate(order, start=1):
        plan_values.append(f"""
# {good}: what this ground pays this good here, one side each -- the fraction of
# this recipe's own ceiling the province feeds, out of {RANK_SCALE}, **plus the weight the
# player put on this good**. `order_by` takes a script value and never a variable,
# which is the only reason these exist at all; the harvest puts the number on the
# location and this hands it to the walk.
#
# **`_pw<n>` is the hand regulator and it is in the same units as the gain**, so
# one step of {RANK_SCALE // 5} is exactly one band: a good moved up by one step is dealt with
# the band above its own. Nought by default and nothing else in the plan reads
# it, so the plan with every weight at nought is the plan the formula alone
# makes. **It cannot take a good's last building** -- the covering ladder runs
# before any band and gives every good one, whatever its weight.
#
# **Nothing divides it any more.** It used to be divided by `_pp<n>`, how many of
# that good already stood in the province, and that multiplier was the whole of
# the smear the owner reported on 2026-09-03: the second building of a good in a
# province scored half and the third a third, so a province that suited a good
# perfectly took two of it and handed its other fifteen rooms to whatever had not
# been there yet. Removed with the counter behind it,
# `docs/investigations/plan_formula.md`.
# Scope: location
{MOD_ID}_ord{index} = {{
\tvalue = var:{MOD_ID}_p{index}
}}
# Scope: location
{MOD_ID}_ordr{index} = {{
\tvalue = var:{MOD_ID}_pr{index}
}}
""")
    # Порядок обхода для деревни — лучшая выгода среди её собственных рецептов
    # на этой локации; её считает `{MOD_ID}_plan_village_scores`.
    for k, building in enumerate(village_entities(rows, split, game), start=1):
        out.append(f"""# {building}
# Scope: location
{MOD_ID}_ordv{k} = {{
\tvalue = var:{MOD_ID}_vb{k}
}}
""")

    # What a whole urban right is worth on this ground: its bundle's own
    # normalized scores added up. It costs no pass of its own -- every good in
    # the bundle was scored anyway -- and the right's own percentage is left out
    # on purpose, because it is the same everywhere and reorders nothing.
    for k, right in enumerate(output_rights(rows, game), start=1):
        bundle = sorted(right.output)
        def _reach(good: str) -> str:
            """Can this bundle good put something in a town — itself, or the
            input that would let it? The substitution below fills the slot
            either way, so the right must be scored as if it counts."""
            i = order.index(good) + 1
            feeder = market_inputs(game).get(good)
            j = order.index(feeder) + 1 if feeder in order else 0
            if j and plan_groups(rows, split, game).get((feeder, "t")):
                return (f"OR = {{ {MOD_ID}_plan_can_town_{i} = yes "
                        f"{MOD_ID}_plan_can_town_{j} = yes }}")
            return f"{MOD_ID}_plan_can_town_{i} = yes"

        # **The same question asked of the score and not of the gate.**
        # `_plan_can_town_<i>` is a *placement* gate: it also asks whether the
        # town still has room and whether this good is already standing there.
        # At grant time the town is empty, so the gate reduces to exactly this --
        # but the dump runs after the plan, when every town is full, and the
        # first `WTP RQ` line came back as thirteen zeroes because of it
        # (2026-09-03). The twin has to read what was true when the grant was
        # made, which is «a town method for this good won here».
        def _won(good: str) -> str:
            i = order.index(good) + 1
            feeder = market_inputs(game).get(good)
            j = order.index(feeder) + 1 if feeder in order else 0
            if j and plan_groups(rows, split, game).get((feeder, "t")):
                return (f"OR = {{ var:{MOD_ID}_pm{i} > 0 "
                        f"var:{MOD_ID}_pm{j} > 0 }}")
            return f"var:{MOD_ID}_pm{i} > 0"

        # **One score for a right, and it is a gain like any good's.** Each
        # bundle good the town can make contributes its own gain; each it cannot
        # contributes nothing; the sum is divided by the *whole* bundle, so a
        # charter that delivers one good of three is worth a third of one that
        # delivers all three. A flat bonus for each good the town can actually
        # make used to sit on top of this and it is gone: dividing by the full
        # bundle already prices the gaps, and without it the number is on the same
        # 0..RANK_SCALE scale as a good's gain -- which is what lets the bands
        # admit a right and a good by the same threshold. **A constant the plan
        # no longer reads must not stay in the dump's BUILD line either**: that
        # line exists so a number is never checked against the wrong constant,
        # and `right_fit=2000` on it said the plan still used one.
        # **The weight reaches a charter through its bundle**, so that raising a
        # good raises the charters that favour it. Without this the regulator
        # could not touch Sauerland, where the charter round decides all 28
        # buildings and the allocator none of them.
        def _won_here(g: str) -> str:
            mis = right_methods(right, g, rows)
            if not mis:
                return _won(g)
            # Право на лимит конкретного здания: считается только там, где
            # именно это здание и выиграло.
            return "AND = { %s OR = { %s } }" % (
                _won(g), " ".join(f"var:{MOD_ID}_pm{order.index(g) + 1} = {mi}"
                                  for mi in mis))

        # **Счёт грамоты -- его, из карты.** Его слово, 2026-09-14: «Я хочу,
        # чтобы выгода от земли по городскому праву считалась тем же методом,
        # что считается в этой карте.» Метод -- среднее арифметическое покрытий
        # товаров связки (`cm_trmm_right_textile = (cov_cloth + cov_dyes +
        # cov_fine_cloth) / 3`), а покрытие товара -- доля входа его лучшего
        # способа, которую провинция даёт своим РГО, плюс своё РГО локации и её
        # модификатор вывода. Разбор целиком --
        # `docs/investigations/wtp_town_right_map.md`.
        #
        # **Считаем через `_cov_<товар>`, а не через его же `_right_<право>`**:
        # у него девять грамот, у сборки тринадцать. Покрытий хватает на все,
        # кроме `silk`, а на девяти общих формула даёт ровно его число -- в этом
        # и смысл эталона.
        #
        # **`silk` покрытия в переносе не имеет** и в среднее не входит:
        # константинопольская грамота считается по двум товарам из трёх. Написано
        # здесь затем, чтобы разницу с картой не искали как ошибку.
        #
        # **Умножаем на RANK_SCALE**: покрытие -- доля около единицы, а всё, что
        # читает `_rq<k>` дальше -- квота, «Лучшая» в сводке, полосы -- меряет в
        # той же тысяче, что и выгода товара.
        #
        # **Старый счёт был денежный**: сумма `_p<n>` по тем товарам связки,
        # которые город и правда делает, делённая на всю связку. Он отвечал на
        # «сколько это принесёт», а спрошено «насколько земля под это подходит».
        covered = [g for g in bundle if g in COV_GOODS]
        if covered:
            adds = "".join(f"\tadd = var:{MOD_ID}_cov_{g}\n" for g in covered)
            adds += f"\tdivide = {len(covered)}\n\tmultiply = {RANK_SCALE}\n"
        else:
            # Ни одного покрытого товара -- считать нечем. В сборке такого нет;
            # ветка стоит, чтобы молчаливый ноль не выглядел как расчёт.
            adds = "\t# ни один товар связки не имеет покрытия в переносе\n"
        plan_values.append(f"""
# {right.key}: {", ".join(bundle)}.
#
# **Насколько эта земля подходит под эту грамоту**, из {RANK_SCALE}. Счёт --
# его, из карты «Лучшее городское право»: среднее покрытий товаров связки, где
# покрытие товара -- доля входа его лучшего способа, которую провинция даёт
# своим РГО. Считается по определению провинции, а не по локации, потому что
# грамота даёт доступ к сырью всей провинции, а сырьё лежит по разным её
# локациям.
#
# **Делителя по всей связке больше нет**: делим на те товары, у которых
# покрытие есть, как делит он. Из связок сборки не покрыт один `silk`.
#
# **Ни карты, ни провинции в делителе.** Оба были ошибками: счёт по карте делал
# диапазоны непересекающимися -- раз выданная грамота уже не могла выиграть по
# заслугам, -- а счёт по провинции выхолащивал провинцию, созданную ровно под
# одну грамоту. «Где драг металы — ювелиркой всё затыкано.»
#
# **Читается после плана**, когда ворота постановки уже врут, поэтому в нём нет
# ни одного `_plan_can_*`: только покрытия, которые пересчёт положил на
# провинцию, и модификаторы самой локации.
# Scope: location
{MOD_ID}_rq{k} = {{
\tvalue = 0
{adds}
}}
""")
    plan_values = "".join(plan_values)

    out.append(f"""
# The better of the two sides -- built-up and village -- in each of the three
# ages a row carries. A province with nothing but a village to offer still
# deserves its row.
# Scope: location
{MOD_ID}_near_score = {{
\tvalue = 0
\tif = {{
\t\tlimit = {{ var:{MOD_ID}_best >= var:{MOD_ID}_best_rural }}
\t\tvalue = var:{MOD_ID}_best
\t}}
\tif = {{
\t\tlimit = {{ var:{MOD_ID}_best < var:{MOD_ID}_best_rural }}
\t\tvalue = var:{MOD_ID}_best_rural
\t}}
}}

# Scope: location
{MOD_ID}_mid_score = {{
\tvalue = 0
\tif = {{
\t\tlimit = {{ var:{MOD_ID}_mid_best >= var:{MOD_ID}_mid_best_rural }}
\t\tvalue = var:{MOD_ID}_mid_best
\t}}
\tif = {{
\t\tlimit = {{ var:{MOD_ID}_mid_best < var:{MOD_ID}_mid_best_rural }}
\t\tvalue = var:{MOD_ID}_mid_best_rural
\t}}
}}

# Scope: location
{MOD_ID}_end_score = {{
\tvalue = 0
\tif = {{
\t\tlimit = {{ var:{MOD_ID}_end_best >= var:{MOD_ID}_end_best_rural }}
\t\tvalue = var:{MOD_ID}_end_best
\t}}
\tif = {{
\t\tlimit = {{ var:{MOD_ID}_end_best < var:{MOD_ID}_end_best_rural }}
\t\tvalue = var:{MOD_ID}_end_best_rural
\t}}
}}

# **A column shrunk until it can only break a tie in the column above it.**
# Ranking by the last age puts every province that reaches the same endgame
# percentage on one number -- and where fine cloth ends in silk, that number is
# 0.00% for the whole table. What separates them then is the road there: ten
# percent until the fifth age beats nothing at all, and that is the choice the
# twentieth run asked to be able to make.
#
# A ten-thousandth of a score is at most 0.495 and the smallest step any raw
# material makes in the endgame set is 1.9, so this orders ties and can never
# reorder anything that is not tied.
# Scope: location
{MOD_ID}_mid_tiebreak = {{
\tvalue = {MOD_ID}_mid_score
\tmultiply = 0.0001
}}

# What the ranking sorts on. Two orders, one per «Считать» button: what you
# could build today, or what the ground gives at the end -- and where the end
# cannot tell two provinces apart, which it cannot whenever a ladder runs out
# (0.00% in every wool province for fine cloth), the road there decides.
#
# One operation per branch, because a script value that quietly does nothing
# logs nothing.
# Scope: location
{MOD_ID}_score = {{
\tvalue = 0
\tif = {{
\t\tlimit = {{ NOT = {{ has_global_variable = {MOD_ID}_rank_by_end }} }}
\t\tvalue = {MOD_ID}_near_score
\t}}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_rank_by_end }}
\t\tvalue = {MOD_ID}_end_score
\t}}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_rank_by_end }}
\t\tadd = {MOD_ID}_mid_tiebreak
\t}}
}}

# The place the ranking gave this location, turned upside down, because
# `ordered_in_global_list` sorts **highest first** and rank 1 has to come out
# first. Ranking a list and then copying it with `every_in_global_list` is what
# lost the order once already: an unordered iterator promises nothing about the
# order it hands things back in, and the window draws its rows in the order the
# list holds them.
# Scope: location
{MOD_ID}_rank_order = {{
\tvalue = 0
\tsubtract = var:{MOD_ID}_rank
}}

# What the rights pass ranks on: every good of the bundle, each at its best
# method here, added through its price. Already scaled -- `_best` is.
#
# «На конец» adds the road there, shrunk until it can only break a tie -- and
# the tie it breaks is the whole table at once, because where no surviving
# recipe can be fed every province is worth exactly zero. A hundred-thousandth
# of a bundle's total is at most 0.065 and the smallest step a bundle's own
# total takes is about 0.6.
# Scope: location
{MOD_ID}_r_mid_tiebreak = {{
\tvalue = var:{MOD_ID}_r_mid_total
\tmultiply = 0.00001
}}

# **Порядок поиска по грамоте -- пригодность земли, а не деньги.** `_r_fit` --
# это `_rq<k>`, среднее покрытий связки, тот счёт, которым красит карта
# «Лучшее городское право»; кладёт его на кандидата `_score_right_<k>`. Деньги
# (`_r_total`) остались тем, что строка печатает, и решают ничью.
# Пригодность земли под отмеченную грамоту, как её показывает карта: `_r_fit`
# лежит в тысячных (`_rq<k>` = покрытие x RANK_SCALE), а на экран идёт долей,
# которую формат `|%1` печатает процентом.
# Scope: location
{MOD_ID}_r_fit_pct = {{
\t# **`has_variable` перед чтением, потому что рисуется оно и там, где прохода
\t# не было.** Строка окна читает значение каждый кадр, а `_r_fit` кладёт
\t# только поиск и только на кандидатов: в его `debug.log` 2026-09-14 это 240
\t# строк «Value of wrong type in 'bag_wtp_r_fit_pct'. Got value of type
\t# 'none'». Ни на экране, ни в `error.log` это не видно вовсе.
\tvalue = 0
\tif = {{
\t\tlimit = {{ has_variable = {MOD_ID}_r_fit }}
\t\tadd = var:{MOD_ID}_r_fit
\t}}
\tdivide = {RANK_SCALE}
}}

# Scope: location
{MOD_ID}_r_score = {{
\t# **Порядок ведёт пригодность земли, в обоих режимах.** `_r_fit` -- это
\t# `_rq<k>`, среднее наших покрытий по связке, и наше покрытие берёт лучший
\t# способ **из доступных** по тумблеру эпохи. Деньги остались тем, что строка
\t# печатает, и решают ничью.
\tvalue = var:{MOD_ID}_r_fit
\tmultiply = 1000
\tadd = var:{MOD_ID}_r_total
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_rank_by_end }}
\t\tadd = {MOD_ID}_r_mid_tiebreak
\t}}
}}

{plan_values}
# The same, for the quota: how many goods this ground can make at all. Divided by
# only under a `limit` that it is above zero, so the guard is the caller's.
{MOD_ID}_plan_scored_value = {{ value = global_var:{MOD_ID}_plan_scored }}
# Сколько городов провинции посчитали грамоту: делитель средней в
# `{MOD_ID}_plan_spec_rights`. `divide` берёт script value, не переменную.
# Scope: country
{MOD_ID}_sprn_value = {{ value = global_var:{MOD_ID}_sprn }}
# And the editor's own divisor: how many goods are still free of a lock and of
# the «не нужен» flag. Same shape and the same caller-side guard.
{MOD_ID}_edit_free_value = {{ value = global_var:{MOD_ID}_edit_free }}
# What the editor's ordered walks sort on: what this location charges for the
# building being added, or `RANK_SCALE` minus the gain of the one being taken
# out. `order_by` reads a script value and never a variable, which is the whole
# reason this exists.
# Scope: location
{MOD_ID}_edit_order = {{ value = var:{MOD_ID}_esv }}
# How many rights this country could grant at all, which the rights' own
# quota divides by. Counted once a plan, in country scope.
{MOD_ID}_rgrant_value = {{ value = global_var:{MOD_ID}_rgrant }}

# How the plan's provinces are ordered: by how much of it landed in each, read
# off the one location that stands in for the province. Under the province model
# every province fills to its capacity, so this is size and contention together
# -- the «магнит» the feature is named for.
# Scope: location
{MOD_ID}_plan_prov_order = {{ value = var:{MOD_ID}_plan_prov_load }}
# И как встают области: по сумме домиков во всех своих провинциях. Провинции
# упорядочены внутри области, а не поперёк неё — «я не хочу, чтобы провинции
# разных областей были в перемешку», 2026-09-06.
# Scope: location
{MOD_ID}_plan_area_order = {{ value = var:{MOD_ID}_plan_area_load }}
# И тот же порядок наоборот, чтобы свёрнутый список строился по возрастанию:
# `ordered_in_global_list` читает от большего к меньшему.
{MOD_ID}_plan_pseq_order = {{ value = 9999 subtract = var:{MOD_ID}_plan_prank }}

# And how a location's row is ordered: by its province's place, so a province's
# locations stay together, with its towns ahead of its villages. Negated because
# `ordered_in_global_list` sorts highest first and place 1 has to come out first.
#
# **Small numbers on purpose.** Packing the province's load and its place into
# one figure would run to five digits, and where the engine's fixed point ends is
# not knowable from here -- `RIGHT_SCALE` is in the generator for the same
# reason.
#
# **`_ord<n>` is the gain and nothing else now.** It used to be divided by
# `_pp<n>`, how many of that good already stood in the province, and that one
# multiplier was the whole of the smear the owner reported on 2026-09-03: a
# good's second building in a province scored half, its third a third, so a
# province that suited a good perfectly took two of it and gave the other
# fifteen rooms to whatever had not been there yet.
#
# **The quota and the concentration answer different questions, and confusing
# them was mine.** «Равномерно» is *how many* -- `_plan_quota`, 34 rooms a good
# on his ground -- and it is untouched. *Where* those 34 land is this value, and
# a province is 17.7 rooms, so a good can own two provinces outright without
# costing any other good a single room. His arithmetic, 2026-09-03, and it is
# right: «на всей общей земле от этого не пострадает ни один другой товар».
#
# **`_pp<n>` is gone with it.** It was still being written -- once per good per
# candidate to zero it, and a walk over every location of the province on every
# placement to raise it -- for a report that never read it. Nothing has read it
# since the divisor went, so nothing writes it either.
# Scope: location
{MOD_ID}_plan_order = {{
\tvalue = 0
\tsubtract = var:{MOD_ID}_plan_prank
\t# **A hundred a province, so the charter can order the towns inside one.**
\t# The owner, 2026-09-03: «мне отвратительно и неприятно видеть бесконечно
\t# чередующиеся права в одной провинции. Пиво-шкаф-пиво-шкаф... Надо как-то
\t# сортировать это, чтобы провинция так же показывала все свои локации вместе,
\t# но сами локации не стояли в таком порядке.»
\t#
\t# **And it is only the order of the rows.** Every location of a province is
\t# worth exactly the same to a charter -- `_rq<k>` reads the province's bonus --
\t# so which town of a province holds which charter is free, and sorting them
\t# changes no number in the plan. That is why this is a script value and not a
\t# change to the grant.
\tmultiply = 100
\tif = {{
\t\tlimit = {{ {MOD_ID}_plan_is_town = yes }}
\t\tadd = 50
\t}}
\t# Ascending by the charter's own number, so identical charters stand together.
\t# `has_variable` first: a village carries none, and a script value reading a
\t# variable that is not there is the failure that logs nothing.
\tif = {{
\t\tlimit = {{ has_variable = {MOD_ID}_plan_right }}
\t\tsubtract = var:{MOD_ID}_plan_right
\t}}
}}

# And the copy into the window's datamodel keeps that order the way the
# ranking's does: highest first, so the rank is negated.
# Scope: location
{MOD_ID}_plan_rank_order = {{
\tvalue = 0
\tsubtract = var:{MOD_ID}_plan_rank
}}

{MOD_ID}_show_regions = {{ value = global_var:{MOD_ID}_zone_count }}
{MOD_ID}_show_candidates = {{ value = global_var:{MOD_ID}_candidate_count }}
{MOD_ID}_show_found = {{ value = global_var:{MOD_ID}_found }}
{MOD_ID}_show_picked = {{ value = global_var:{MOD_ID}_picked_count }}
{MOD_ID}_show_browse = {{ value = global_var:{MOD_ID}_browse_count }}
{MOD_ID}_show_live = {{ value = global_var:{MOD_ID}_live_runs }}

# Что показать на самой кнопке «Диагностика». Она пишет в лог, а лог не на
# экране: без этих пяти чисел нажатие ничем не отличается от кнопки, которая
# не работает.
{MOD_ID}_show_ticks = {{ value = global_var:{MOD_ID}_tick_count }}
# The editor's own numbers, for its window to print. **A plain script value over
# a global and no guard inside it**: the self-guarding form returned zero for
# every reader on a plan that had just placed 417 buildings and said so nowhere,
# which is the note below this block.
#
# `_edit_moved` is how many locations the last «показать изменения» found, and
# it is the number that condemned the weight regulator -- 42 of 48 on one press.
# `_edit_done` is whether the last «+1» or «−1» actually did anything: an effect
# that merely does nothing logs nothing at all, and a good whose last building
# may not be taken out is exactly such a case.
# Scope: country
{MOD_ID}_show_edit_moved = {{ value = global_var:{MOD_ID}_edit_moved }}
# **Нажатие, которое ничего не сделало, тоже нажатие.** Его слова,
# 2026-09-06: «отсутствие изменений -- тоже изменение… журнал должен
# регистрировать такие клики». В списке изменений их видно только дырой в
# нумерации -- она начинается с 3, если первые два нажатия никуда не встали,
# -- и дыра без подписи читается как потерянная строка. Счётчик самих нажатий
# уже есть ниже, `_show_edit_presses`.
{MOD_ID}_show_edit_idle = {{ value = global_var:{MOD_ID}_edit_idle }}
# **The reshuffle's own two numbers**, and they are on screen because the pass
# is invisible otherwise: it moves buildings the player did not ask about, and
# «traded nothing», «traded and it was worth nothing» and «never ran» are three
# different answers that look identical on the map.
# Scope: country
{MOD_ID}_show_rs_swaps = {{ value = global_var:{MOD_ID}_rs_swaps }}
# Scope: country
{MOD_ID}_show_rs_gain = {{ value = global_var:{MOD_ID}_rs_gain }}
# Scope: country
{MOD_ID}_show_edit_saved = {{ value = global_var:{MOD_ID}_save_n }}
# Scope: country
{MOD_ID}_show_edit_done = {{ value = global_var:{MOD_ID}_edit_done }}
# Scope: country
{MOD_ID}_show_edit_reached = {{ value = global_var:{MOD_ID}_edit_reached }}
# **How many goods the picker was filled with.** On screen beside the list, and
# it is there to separate two failures that look identical: a list that was
# never filled, and a list that was filled and does not draw. The editor's goods
# vanished once already, and telling those apart cost a round trip.
# Scope: country
{MOD_ID}_show_edit_pooln = {{ value = global_var:{MOD_ID}_edit_pooln }}
# **How many presses the editor has taken since the window opened.** The probe
# that separates «кнопка не сработала» from «правило отказало»: if it does not
# move, the press never reached the effect at all.
# Scope: country
{MOD_ID}_show_edit_presses = {{ value = global_var:{MOD_ID}_edit_presses }}
# **The editor's own share, on the editor's own header.** The plan window says
# «норма 5» and means `_plan_quota`, the whole ground over every good it can
# make; the editor has been using a different number since the lock arrived, and
# on 2026-09-05 his ground read 5 on screen while the fill was working to 3.
# «Как увеличить общий лимит» is answerable the moment the three numbers it is
# made of are visible: rooms still in the pool, goods still free, and the
# quotient.
# Scope: country
{MOD_ID}_show_edit_quota = {{ value = global_var:{MOD_ID}_edit_quota }}
# Scope: country
{MOD_ID}_show_edit_free = {{ value = global_var:{MOD_ID}_edit_free }}
# Scope: country
{MOD_ID}_show_edit_pool_rooms = {{ value = global_var:{MOD_ID}_edit_pool_rooms }}
# Scope: country
{MOD_ID}_show_edit_slot1 = {{ value = global_var:{MOD_ID}_sl1_n }}
# Scope: country
{MOD_ID}_show_edit_slot1_locs = {{ value = global_var:{MOD_ID}_sl1_locn }}
# Scope: country
{MOD_ID}_show_edit_slot2 = {{ value = global_var:{MOD_ID}_sl2_n }}
# Scope: country
{MOD_ID}_show_edit_slot2_locs = {{ value = global_var:{MOD_ID}_sl2_locn }}
# Scope: country
{MOD_ID}_show_edit_slot3 = {{ value = global_var:{MOD_ID}_sl3_n }}
# Scope: country
{MOD_ID}_show_edit_slot3_locs = {{ value = global_var:{MOD_ID}_sl3_locn }}

{MOD_ID}_show_diag_runs = {{ value = global_var:{MOD_ID}_diag_runs }}
{MOD_ID}_show_diag_locs = {{ value = global_var:{MOD_ID}_diag_locs }}
{MOD_ID}_show_diag_towns = {{ value = global_var:{MOD_ID}_diag_towns }}
{MOD_ID}_show_diag_freet = {{ value = global_var:{MOD_ID}_diag_freet }}
{MOD_ID}_show_diag_freer = {{ value = global_var:{MOD_ID}_diag_freer }}

# The diagnosis reads through these sixteen and nothing else. **`value =
# global_var:x` and no guard inside the value**: the self-guarding form, `value =
# 0` with an `if` adding the global, returned zero for every reader on a plan
# that had just placed 417 buildings, and said nothing in any log. The guard is
# an `if` in the effect that fills the scratch global instead.
""" + "".join(f"{MOD_ID}_dg{i} = {{ value = global_var:{MOD_ID}_dv{i} }}\n"
               for i in range(1, DIAG_SCRATCH + 1)) + f"""

# What the plan pass counted, each of them printed on the button that ran it.
# The first zero among them is the diagnosis, which is the only debugging a
# player can be asked for: an effect that merely does nothing logs nothing.
# **Ключ, по которому «Показать изменения» раскладывает локации** -- номер
# нажатия, вывернутый наизнанку (`order_by` читает от большего к меньшему).
{MOD_ID}_chg_order = {{ value = var:{MOD_ID}_chg_rank }}

# **Что сделала «Расширить», шестью числами.** Строка под кнопкой -- это проба,
# а не украшение: «доливка не сработала», «новой земли не оказалось» и «доливка
# полезла на старую землю» на карте выглядят одинаково, а здесь это три разных
# числа. `moved` обязан быть нулём.
{MOD_ID}_show_ext_new = {{ value = global_var:{MOD_ID}_ext_new }}
{MOD_ID}_show_ext_was = {{ value = global_var:{MOD_ID}_ext_was }}
{MOD_ID}_show_ext_rooms = {{ value = global_var:{MOD_ID}_ext_rooms }}
{MOD_ID}_show_ext_added = {{ value = global_var:{MOD_ID}_ext_added }}
{MOD_ID}_show_ext_moved = {{ value = global_var:{MOD_ID}_ext_moved }}
{MOD_ID}_show_ext_lifted = {{ value = global_var:{MOD_ID}_ext_lifted }}
# **Делители трёхклассовой доли.** Скрипт делит только на script value, а не
# на глобалку напрямую — отсюда эти четыре.
{MOD_ID}_qgt_value = {{ value = global_var:{MOD_ID}_qgt }}
{MOD_ID}_qgr_value = {{ value = global_var:{MOD_ID}_qgr }}
{MOD_ID}_show_prooms_t = {{ value = global_var:{MOD_ID}_prooms_t }}
{MOD_ID}_show_prooms_r = {{ value = global_var:{MOD_ID}_prooms_r }}
# Постоянные делители ступеней: 2 %, 4 %, 8 %, 16 %, 32 % земли.
{MOD_ID}_tdiv1 = {{ value = 50 }}
{MOD_ID}_tdiv2 = {{ value = 25 }}
{MOD_ID}_tdiv3 = {{ value = 12.5 }}
{MOD_ID}_tdiv4 = {{ value = 6.25 }}
{MOD_ID}_tdiv5 = {{ value = 3.125 }}
{MOD_ID}_show_plan_scored = {{ value = global_var:{MOD_ID}_plan_scored }}
{MOD_ID}_show_plan_placed = {{ value = global_var:{MOD_ID}_plan_placed }}
{MOD_ID}_show_plan_found = {{ value = global_var:{MOD_ID}_plan_found }}
{MOD_ID}_show_plan_shown = {{ value = global_var:{MOD_ID}_plan_shown }}
{MOD_ID}_show_plan_rooms = {{ value = global_var:{MOD_ID}_plan_rooms }}
{MOD_ID}_show_plan_cap_rural = {{ value = global_var:{MOD_ID}_plan_cap_rural }}
{MOD_ID}_show_plan_cap_urban = {{ value = global_var:{MOD_ID}_plan_cap_urban }}
# Which page of the answer is on screen, out of how many, and the rows it covers.
# The window draws one page of {PLAN_ROWS} at a time; these four are what the page
# bar above the table prints, so «показано 150» is never read as the size of the
# plan again.
# Сколько провинций план застроил (а `_plan_provn` — сколько их на выбранной
# земле вообще) и сколько из них поместилось в свёрнутый список.
{MOD_ID}_show_plan_provfill = {{ value = global_var:{MOD_ID}_plan_provfill }}
{MOD_ID}_show_plan_provshown = {{ value = global_var:{MOD_ID}_plan_provshown }}
# Scope: location
{MOD_ID}_show_prov_locn = {{ value = var:{MOD_ID}_plan_prov_locn }}
{MOD_ID}_show_prov_load = {{ value = var:{MOD_ID}_plan_prov_load }}
{MOD_ID}_show_prov_rank = {{ value = var:{MOD_ID}_plan_prank }}
{MOD_ID}_show_plan_page = {{ value = global_var:{MOD_ID}_plan_page }}
{MOD_ID}_show_plan_pages = {{ value = global_var:{MOD_ID}_plan_pages }}
{MOD_ID}_show_plan_from = {{ value = global_var:{MOD_ID}_plan_from }}
{MOD_ID}_show_plan_to = {{ value = global_var:{MOD_ID}_plan_to }}
# The fair share the quota came out at, on the header line: with the room count
# and the goods count beside it, it is the whole of `plan_quota` readable at a
# glance, and a quota of 1 says the ground is the binding constraint.
{MOD_ID}_show_plan_quota = {{ value = global_var:{MOD_ID}_plan_quota }}
{MOD_ID}_show_qcapt = {{ value = global_var:{MOD_ID}_qcapt }}
{MOD_ID}_show_qcapr = {{ value = global_var:{MOD_ID}_qcapr }}
{MOD_ID}_show_plan_sweeps = {{ value = global_var:{MOD_ID}_plan_sweeps }}
{MOD_ID}_show_plan_towns = {{ value = global_var:{MOD_ID}_plan_towns }}
{MOD_ID}_show_plan_provn = {{ value = global_var:{MOD_ID}_plan_provn }}
{MOD_ID}_show_plan_rightn = {{ value = global_var:{MOD_ID}_plan_rightn }}
""")
    return "".join(out)


def score_file(rows: list[eu5data.Method], split: dict[str, list[str]],
               game: eu5data.Game) -> str:
    """Finding the method, which is the thing the player should not have to do.

    **Two axes, and a row carries both.** Across one: the best village and the
    best of everything else, scored apart because a village produces a fifth of
    what a guild does and buried the guilds when they shared a list. Across the
    other, three ages of the same question:

    | prefix | column | the best method that is |
    | --- | --- | --- |
    | none | «Сейчас» | unlocked for this country today |
    | `mid_` | «По пути» | unlocked in *any* age -- and until which age it lasts |
    | `end_` | «В конце» | still buildable once every advance is in |

    The third column is what makes this a planning tool rather than a table.
    Fine cloth from wool has no rung above the workshop, so «В конце» is 0.00%
    in every wool province and choosing between them needs the other number:
    ten percent, until the fifth age. **Rank by the end, break the ties by the
    road there** -- which is what the twentieth run asked for in as many words.

    **A method the ground cannot feed is not an answer**, so every one of the
    three keeps only methods this province supplies the bulk of the raw materials
    for -- asked as `_try > <a literal>`, the literal being `fed_floor`. Each
    also keeps an `_any_` twin without that floor, which nothing ranks on: a
    column has to print something, and "the mill you cannot feed, at 0.00%" is an
    answer where a blank cell is not.

    All of it in one walk: a method's `_m<n>` is computed once and offered to
    every answer it qualifies for.
    """
    order = [good for kind in ("raw", "made") for good in split[kind]]
    by_good: dict[str, list[int]] = {}
    for index, method in enumerate(rows, start=1):
        by_good.setdefault(method.produced, []).append(index)
    rural = {index for index, method in enumerate(rows, start=1)
             if method.building_category in RURAL_CATEGORIES}
    last = endgame(rows, game)

    # Every answer a candidate carries, and what it is allowed to keep.
    ANSWERS = ("", "any_", "mid_", "end_", "end_any_")

    # And the plan's own four, which are a different question from all of them.
    #
    # **The plan splits by where a building may stand, not by what category it
    # is in.** The ranking's «village» side is `village_category` -- four
    # buildings -- and the owner's twenty-ninth screenshot is what that costs: a
    # rural province offered tools, jewelry and beer, all three of them
    # `market_village`, where a stone quarry, a clay pit and a lumber mill would
    # have been the honest answer. Thirty production buildings declare
    # `rural_settlement = yes` and only four are villages, so the plan asks the
    # building type itself (`eu5data.Method.rural` / `.urban`).
    PLAN_SIDES = (("_t", "urban"), ("_r", "rural"))

    def keep(indent: str, prefix: str, suffix: str, method_index: int,
             floor: float | None, extra: str = "", plan: bool = False) -> str:
        """Is this the best of its side so far, and can this ground feed it?

        `floor` is `fed_floor`: the `_m<n>` of a method the province supplies
        exactly half the possible bonus of. Anything above it is a recipe this
        ground supplies the bulk of.

        Without any floor the eighteenth run's fine cloth answered with silk
        weavers at 0.00% in provinces full of wool: 0.70 a level unfed beats 0.50
        a level at the full ten percent, so the ranking preferred a recipe the
        ground cannot supply and buried every province that could have run the
        other one. With a floor at the unbonused output it did the same thing
        again on one input out of three -- the twenty-fifth run, and why the
        floor is where it is now.
        """
        fed = f"var:{MOD_ID}_try > {floor:.4f} " if floor is not None else ""
        # **The method is chosen by worth and the placement is dealt by gain**,
        # and the two are different questions. Within one good a mill at 5% beats
        # a guild at 10%, so `_try` decides which recipe wins here. Across goods
        # what compares is the fraction of its own ceiling that recipe earns, so
        # the winner's `_g<n>` is kept beside it for the plan to deal by.
        gain = ("" if not plan else
                f"{indent}\tset_variable = {{ name = {MOD_ID}_{prefix}gain{suffix} "
                f"value = {MOD_ID}_g{method_index} }}\n")
        return (f"""{indent}if = {{
{indent}\tlimit = {{ {fed}var:{MOD_ID}_try > var:{MOD_ID}_{prefix}best{suffix}{extra} }}
{indent}\tset_variable = {{ name = {MOD_ID}_{prefix}best{suffix} value = var:{MOD_ID}_try }}
{indent}\tset_variable = {{ name = {MOD_ID}_{prefix}best_method{suffix} value = {method_index} }}
{gain}{indent}}}
""")

    out = [HEADER, f"""#
# **The country is saved, not reached for.** Every method's availability is a
# country trigger asked from inside a walk over locations, and it used to get
# there with `root`. From a Mod Menu button `root` is the country; from a map
# picker's generic action it is not, so the eleventh run's pass walked its
# 44 locations, found no method available in any of them -- «нашёл 0» -- and the
# window emptied itself the moment a border was drawn.
#
# Scope: country
{MOD_ID}_score_candidates = {{
\tsave_scope_as = {MOD_ID}_country
"""]
    for index, good in enumerate(order, start=1):
        keyword = "if" if index == 1 else "else_if"
        out.append(f"\t{keyword} = {{ limit = {{ var:{MOD_ID}_good_index = {index} }} "
                   f"{MOD_ID}_score_{index} = yes }}\n")
    out.append("}\n")

    for index, good in enumerate(order, start=1):
        methods_for = by_good.get(good, [])
        village = [i for i in methods_for if i in rural]
        out.append(f"\n# {good}, made {len(methods_for)} way(s), "
                   f"{len(village)} of them in a village.\n"
                   f"# Scope: country\n{MOD_ID}_score_{index} = {{\n")
        out.append(f"\tevery_in_global_list = {{\n\t\tvariable = {MOD_ID}_candidates\n")
        for prefix in ANSWERS:
            for suffix in ("", "_rural"):
                out.append(f"\t\tset_variable = {{ name = {MOD_ID}_{prefix}best{suffix} value = 0 }}\n")
                out.append(f"\t\tset_variable = {{ name = {MOD_ID}_{prefix}best_method{suffix} value = 0 }}\n")
        for prefix in ("pnow", "pend", "pnowany", "pendany"):
            for side, _ in PLAN_SIDES:
                out.append(f"\t\tset_variable = {{ name = {MOD_ID}_{prefix}best{side} value = 0 }}\n")
                out.append(f"\t\tset_variable = {{ name = {MOD_ID}_{prefix}best_method{side} value = 0 }}\n")
                out.append(f"\t\tset_variable = {{ name = {MOD_ID}_{prefix}gain{side} value = 0 }}\n")

        for method_index in methods_for:
            suffix = "_rural" if method_index in rural else ""
            floor = fed_floor(rows[method_index - 1], game)
            out.append(f"\t\tset_variable = {{ name = {MOD_ID}_try value = {MOD_ID}_m{method_index} }}\n")
            # **Can this building stand here at all.** The ranking asked this of
            # nothing until the thirty-second load, and the owner caught it in as
            # many words: a stone quarry offered on ground that is flat all
            # through, because the province works wood. `can_build_building` in
            # the location's own scope is the terrain, the rank and the
            # building's `location_potential`, and never an advance -- so it is
            # as safe on «В конце» as on «Сейчас», and on ground nobody owns.
            # **Not `can_build_building` directly**: that answers the rank and
            # the `location_potential` in one breath, and the tick is meant to
            # override the rank alone. `{MOD_ID}_stands_<building>` splits them
            # where it can and asks the game as before where it cannot
            # (`triggers_file`, and `docs/SETTLED.md` for what it cost to find).
            # **И `_mstands_<n>` там, где метод несёт собственный `allow` про
            # локацию**: пшеничная житница крепости стоит не везде, где стоит
            # крепость, а там, где её рынок даёт пшеницу (`method_allows`).
            stands = (f" {MOD_ID}_mstands_{method_index} = yes"
                      if method_allow_gates(rows[method_index - 1])[1] else
                      f" {MOD_ID}_stands_{rows[method_index - 1].building} = yes")
            # **Every answer below is an end-game one, and the one thing even the
            # end cannot bring is an advance this country may never take.**
            # `_reach_<n>` is `always = yes` for all but thirteen methods, so the
            # `if` costs nothing where nothing is locked.
            # **Тот же вопрос и то же место, откуда он берётся.** Раньше здесь
            # стоял свой список -- только по продвижениям, -- и метод, запертый
            # `country_potential`, ворот не получал: они писались и не
            # спрашивались.
            reachable = method_gates(rows[method_index - 1])
            deep, shut = ("\t\t", "") if not reachable else ("\t\t\t", f"""\t\tif = {{
\t\t\tlimit = {{ scope:{MOD_ID}_country = {{ {MOD_ID}_reach_{method_index} = yes }} }}
""")
            out.append(shut)
            # «По пути»: every age, so no gate on availability -- but the ground
            # still has to be able to hold it.
            out.append(keep(deep, "mid_", suffix, method_index, floor, stands))
            if method_index in last:
                out.append(keep(deep, "end_", suffix, method_index, floor, stands))
                out.append(keep(deep, "end_any_", suffix, method_index, None, stands))
            # The plan's endgame side needs no availability: it is what stands
            # once every advance is in.
            # **The plan keeps an unfloored twin of each side and the ranking
            # does not.** `fed_floor` is right for an answer to «where should I
            # make wine» and wrong for «fill this ground»: the owner settled it
            # on 2026-09-01 -- «бонус от рго это приоритет, а не железное
            # правило, без которого в локации домика существовать не может».
            # A location no RGO helps still has to be filled, and a right's
            # bundle goes up whether the ground feeds it or not.
            #
            # The floored answer is still what wins wherever there is one, so
            # the twenty-fifth run's silk weaver in a wool province stays
            # buried: the twin is a fallback, never a rival.
            for side, where in PLAN_SIDES:
                if getattr(rows[method_index - 1], where) and method_index in last:
                    out.append(keep(deep, "pend", side, method_index, floor, stands, plan=True))
                    out.append(keep(deep, "pendany", side, method_index, None, stands, plan=True))
            if reachable:
                out.append("\t\t}\n")
            out.append(f"""\t\tif = {{
\t\t\tlimit = {{ scope:{MOD_ID}_country = {{ {MOD_ID}_avail_{method_index} = yes }} }}
""")
            out.append(keep("\t\t\t", "", suffix, method_index, floor, stands))
            out.append(keep("\t\t\t", "any_", suffix, method_index, None, stands))
            for side, where in PLAN_SIDES:
                if getattr(rows[method_index - 1], where):
                    out.append(keep("\t\t\t", "pnow", side, method_index, floor, stands, plan=True))
                    out.append(keep("\t\t\t", "pnowany", side, method_index, None, stands, plan=True))
            out.append("\t\t}\n")
        out.append("\t}\n}\n")

    def park(prefix: str, index: int, method: eu5data.Method, suffix: str) -> str:
        """One winner, written onto the location the window reads its row off.

        Each column keys on its own `_show`, which is the fed answer where the
        ground feeds one and the unfed one otherwise. `«По пути»` carries an age
        instead of a goods list: it is a number and a deadline, and the icons
        beside it would be the same icons twice.
        """
        raw = sorted(method.raw_inputs(game.raw_goods))
        # `_pm2` is the improvement half, and only eight buildings have one. The
        # key of a pair is "base+improvement" and names no production method the
        # game knows, so each half is written on its own.
        improvement = (f"\t\tset_variable = {{ name = {MOD_ID}_{prefix}pm2{suffix} "
                       f"value = production_method:{method.parts[1].key} }}\n"
                       if len(method.parts) > 1 else "")
        body = [f"\tif = {{\n"
                f"\t\tlimit = {{ var:{MOD_ID}_{prefix}show{suffix} = {index} }}\n"
                f"\t\tset_variable = {{ name = {MOD_ID}_{prefix}bt{suffix} value = building_type:{method.building} }}\n"
                f"\t\tset_variable = {{ name = {MOD_ID}_{prefix}pm{suffix} value = production_method:{method.parts[0].key} }}\n"
                + improvement
                + f"\t\tset_variable = {{ name = {MOD_ID}_{prefix}bonus{suffix} value = {MOD_ID}_b{index} }}\n"
                f"\t\tset_variable = {{ name = {MOD_ID}_{prefix}out{suffix} value = {method.output:.4f} }}\n"]
        if prefix == "mid_":
            body.append(f"\t\tset_variable = {{ name = {MOD_ID}_mid_age{suffix} value = {game.last_age(method)} }}\n")
        else:
            body.append(f"\t\tset_variable = {{ name = {MOD_ID}_{prefix}goods_all{suffix} value = {len(raw)} }}\n")
            for good in raw:
                body.append(f"""\t\tif = {{
\t\t\tlimit = {{ province_definition = {{ any_location_in_province_definition = {{ raw_material = goods:{good} }} }} }}
\t\t\tadd_to_variable_list = {{ name = {MOD_ID}_{prefix}goods{suffix} target = goods:{good} }}
\t\t}}
""")
        body.append("\t}\n")
        return "".join(body)

    # column prefix -> (what it is, the fed answer, the unfed fallback, which
    # methods can appear in it)
    COLUMNS = (
        ("", "what you could build today", "best_method", "any_best_method", None),
        ("mid_", "the best this ground ever feeds, and until when", "mid_best_method", None, None),
        ("end_", "what stands once every advance is in", "end_best_method", "end_any_best_method", last),
    )
    for prefix, what, fed, unfed, only in COLUMNS:
        for suffix in ("", "_rural"):
            age = (f"\tset_variable = {{ name = {MOD_ID}_mid_age{suffix} value = 0 }}\n"
                   if prefix == "mid_" else "")
            fallback = (f"""\tif = {{
\t\tlimit = {{ var:{MOD_ID}_{prefix}show{suffix} = 0 }}
\t\tset_variable = {{ name = {MOD_ID}_{prefix}show{suffix} value = var:{MOD_ID}_{unfed}{suffix} }}
\t}}
""" if unfed else "")
            out.append(f"""
# {what.capitalize()}, on the {"village" if suffix else "built-up"} side.
# Scope: location
{MOD_ID}_store_winner_{prefix or "now_"}{suffix.lstrip("_") or "town"} = {{
\tset_variable = {{ name = {MOD_ID}_{prefix}show{suffix} value = var:{MOD_ID}_{fed}{suffix} }}
{fallback}\tclear_variable_list = {MOD_ID}_{prefix}goods{suffix}
\tremove_variable = {MOD_ID}_{prefix}bt{suffix}
\tremove_variable = {MOD_ID}_{prefix}pm{suffix}
\tremove_variable = {MOD_ID}_{prefix}pm2{suffix}
\t# Zeroed rather than left: nothing sets these where no method won at all, the
\t# window guards only on `_bt`, and a number left over from the last run is
\t# invisible there and wrong to everything that reads it.
\tset_variable = {{ name = {MOD_ID}_{prefix}bonus{suffix} value = 0 }}
\tset_variable = {{ name = {MOD_ID}_{prefix}out{suffix} value = 0 }}
\tset_variable = {{ name = {MOD_ID}_{prefix}goods_all{suffix} value = 0 }}
{age}""")
            for index, method in enumerate(rows, start=1):
                if (index in rural) != bool(suffix):
                    continue
                if only is not None and index not in only:
                    continue
                out.append(park(prefix, index, method, suffix))
            out.append("}\n")
    return "".join(out)


def market_inputs(game: eu5data.Game) -> dict[str, str]:
    """Good -> the good its buildings need *in the market* before they may stand.

    Read off `location_potential`, where four buildings in the game carry an
    `is_produced_in_(location_)market = goods:X`. Only a good whose buildings all
    carry one is listed, and never one that asks for itself: `horse_breeders`
    wants horses in the market to make horses, which nothing can bootstrap.

    **This exists because a right's bundle is mandatory and the ground can still
    refuse it.** Glass is the case, and the owner's rule, 2026-09-01: «стекло
    делать в любом случае НАДО и отказаться от него нельзя из-за отсутствия
    песка, ведь у него нет альтернативного варианта как у тонкого сукна». Sand is
    dug by a `sand_pit`, which stands at any rank and asks only that the location
    is not already a sand RGO — so where a granted right cannot have its glass,
    the plan puts the pit that makes glass possible instead.
    """
    directory = refs.GAME_COMMON / "building_types"
    text = "".join(path.read_text(encoding="utf-8-sig", errors="replace")
                   for path in sorted(directory.glob("*.txt")))
    gated: dict[str, set[str]] = {}
    for block in re.split(r"\n(?=[a-z_0-9]+ = \{)", text):
        match = re.match(r"([a-z_0-9]+) = \{", block)
        if not match or "location_potential" not in block:
            continue
        needs = set(re.findall(
            r"is_produced_in(?:_location)?_market = goods:(\w+)",
            block.split("location_potential", 1)[1][:250]))
        if needs:
            gated[match.group(1)] = needs
    out: dict[str, str] = {}
    for good in game.goods_produced:
        makers = {m.building for m in game.methods
                  if m.produced == good and m.raw_inputs(game.raw_goods)} & set(gated)
        if not makers:
            continue
        # **Any of its buildings, not all of them.** Whether the ungated ones are
        # reachable is an availability question and the runtime already answers
        # it: `_plan_can_town_<n>` is asked with the age's own methods, so the
        # substitution below only ever fires where the good really cannot stand.
        needs = set().union(*(gated[b] for b in makers)) - {good}
        if len(needs) == 1:
            out[good] = needs.pop()
    return out


# Четыре деревни игры, `is_village = yes` в `rural_buildings.txt`. Три из них
# делят несколько товаров и становятся сущностями сами по себе; фермерская
# однотоварна (`unique_production_methods`, всегда скот) и остаётся товаром.
VILLAGES = ("fishing_village", "forest_village", "farming_village",
            "market_village")


def village_entities(rows, split, game) -> list[str]:
    """Деревни, которые считаются сущностью, а не товаром.

    **Его правило, повторённое полсотни раз:** «убрать все деревенские доли
    товаров и заменить их просто на торговая деревня = 1 уникальный товар».
    Деревня, за которую спорят несколько товаров, — один слот на всех них, и в
    равном круге она участвует сама, а не через пиво с гончаркой. Что она
    производит, решает лучший из её рецептов на этой локации.
    """
    return [b for b in shared_buildings(rows, split, game) if b in VILLAGES]


def own_sides(rows, split, game) -> dict[str, tuple[bool, bool]]:
    """Есть ли у товара **своё** здание в городе и в селе, по товару.

    **Село считается только по своим зданиям, деревни не в счёт.** «Деревня =
    товар»: бумага в селе не встанет никогда, пиво в селе не встанет тоже --
    его там делает торговая деревня, и это её домик, а не пива. Сводка ставит
    в такой клетке прочерк, а не ноль: «куча нулей меня напрягает»,
    2026-09-08.

    Это статический факт мода, а не выбранной земли: `pounamou_carver` --
    настоящее сельское здание украшений, даже если в Вестфалии его нет.
    """
    groups = plan_groups(rows, split, game)
    villages = village_entities(rows, split, game)
    order = [g for kind in ("raw", "made") for g in split[kind]]
    return {good: (bool(groups.get((good, "t"))),
                   any(b not in villages for b in (groups.get((good, "r")) or {})))
            for good in order}


def shared_buildings(rows, split, game) -> list[str]:
    """Здания, за которые спорят несколько товаров, в устойчивом порядке.

    **Это и есть «универсальные деревни» владельца, названные общим правилом.**
    Локация держит одно здание каждого вида, поэтому здание, которое умеет
    несколько товаров, -- один слот на всех них: торговая деревня делает пиво,
    украшения, гончарку, инструменты и оружие, и без своего потолка она встаёт
    впятеро чаще любого однотоварного домика. Его слова, 2026-09-07: «не хочу,
    чтобы лесная деревня заняла 80 лесных локаций, когда все остальные домики
    упёрлись в 60».

    **Однотоварные здания сюда не попадают, и это намеренно.** Их и так держит
    квота их товара, а второй потолок поверх неё мог бы связать раньше неё --
    у товара с грамотами квота выше общей доли, а у здания нет. Фермерская
    деревня однотоварна (`unique_production_methods`, всегда скот), поэтому её
    держит квота скота: «так и считай их как товар скот».
    """
    groups = plan_groups(rows, split, game)
    order = [g for kind in ("raw", "made") for g in split[kind]]
    goods_of: dict[str, set[str]] = {}
    for good in order:
        for side in ("t", "r"):
            for building in (groups.get((good, side)) or {}):
                goods_of.setdefault(building, set()).add(good)
    return sorted(b for b, gs in goods_of.items() if len(gs) > 1)


def plan_groups(rows, split, game):
    """Per good and side, the buildings that could win it and by which methods.

    **The plan's unit is a building in a location.** One location holds one
    building of a type and a building runs one method, so two goods off the same
    building cannot both be built there. But **two locations of one province
    can each hold that building running a different method** -- a market village
    makes tools, jewelry, beer and pottery, and four villages of a province may
    take one each. That is why the rule is per location and not per province.

    Returns `{(good, side): {building: [method index, ...]}}`, side being "t" for
    what may stand in a town and "r" for a rural settlement. A method appears on
    both sides where its building declares both.
    """
    order = [good for kind in ("raw", "made") for good in split[kind]]
    groups: dict[tuple[str, str], dict[str, list[int]]] = {}
    for index, method in enumerate(rows, start=1):
        if method.produced not in order:
            continue
        for side, allowed in (("t", method.urban), ("r", method.rural)):
            if allowed:
                groups.setdefault((method.produced, side), {}) \
                      .setdefault(method.building, []).append(index)
    return groups


def plan_right_gates(rows: list[eu5data.Method],
                     game: eu5data.Game) -> list[str]:
    """Per urban right, the country condition the plan grants it under.

    **The right's own `potential`, and never its unlocking advance.** Which is
    the same rule the rights *window* uses, and it was arrived at the hard way.

    On 2026-09-03 this asked `has_advance` on «Сейчас», on the argument that a
    plan is an answer about a moment and that refusing a cannon maker for want of
    an advance while handing out Discovery-age charters dated one answer two
    ways. **The run of the same day settled it, against that argument.** Münster
    holds `flemish_cloth_making` and not `town_rights_enable`, so the gate left
    it **one** grantable charter of thirteen -- and the rule every town gets one
    then gave the same charter to all forty-eight. Cloth stood in 48 locations of
    192, a quarter of the ground in one good, and the number of goods the plan
    produced fell from 35 to 30. Ungated, the same ground takes nine charters and
    spreads them.

    **The two are gated differently because they are different kinds of thing.**
    A building you cannot build today is not an answer to «what do I build»; a
    charter is not something you build. It is a property of a town that says
    which buildings belong in it, every country receives the nine general ones at
    one fixed age, and a plan is a target to build towards. That is exactly the
    reason already settled for the window -- «hiding them until age three would
    leave an empty list where the answer belongs» -- and it holds here for the
    same reason.

    **The advance is not lost, it is reported.** `WTP RIGHT` prints `unlocked=`
    beside `grantable=`, so the report says «the plan wants naval charters in
    Sauerland and you cannot grant one until Discovery» without the plan
    degrading into a monoculture to say it.
    """
    by_key = {r.key: r for r in game.town_rights}
    bodies = []
    for right in output_rights(rows, game):
        parts = [p for p in (by_key[right.key].potential,) if p]
        winner = by_key.get(PREFERRED_RIGHT.get(right.key, ""))
        if winner is not None:
            # A preferred right with no gate at all would be preferred always,
            # and the one it displaces would never be granted by anybody. Today
            # Flemish cloth carries a culture group; a silent `always = no` is
            # the worst way to learn that it had lost it.
            assert winner.potential, f"{winner.key} would displace {right.key} everywhere"
            parts.append("NOT = { %s }" % winner.potential)
        bodies.append("\n".join(f"\t{part}" for part in parts) or "\talways = yes")
    return bodies


def ladder_above(building: str, game: eu5data.Game) -> list[str]:
    """Ступени **над** этим зданием, снизу вверх.

    Игра называет их сама: `obsolete = <нижняя>` в `building_types`, откуда
    `eu5data` строит `successor` -- «кто делает это здание устаревшим». Гончарная
    гильдия → мастерская → мануфактура → мельница, одна цепочка на четыре
    ступени, и длиннее в игре не бывает.
    """
    chain, seen = [], {building}
    upper = game.successor.get(building)
    while upper and upper not in seen:
        chain.append(upper)
        seen.add(upper)
        upper = game.successor.get(upper)
    return chain


def ladder_below(building: str, game: eu5data.Game) -> list[str]:
    """Ступени **под** этим зданием, сверху вниз -- обратная сторона `successor`."""
    lower = {up: low for low, up in game.successor.items()}
    chain, seen = [], {building}
    down = lower.get(building)
    while down and down not in seen:
        chain.append(down)
        seen.add(down)
        down = lower.get(down)
    return chain


def ladder_set(groups: dict, game: eu5data.Game) -> list[str]:
    """Здания плана и все ступени над ними -- то, про что фильтр спрашивает."""
    planned = {b for key in groups for b in groups[key]}
    return sorted(planned | {a for b in planned for a in ladder_above(b, game)})


def plan_triggers_file(rows: list[eu5data.Method], split: dict[str, list[str]],
                       game: eu5data.Game) -> str:
    """Whether this location may still take this good on this side.

    One trigger per good per side, asked twice: as the `limit` of the ordered
    walk that picks the location, and again inside the effect that adds it, so
    that the urban-rights round can call the effect without repeating a word.

    Every condition is a plain read off the location in hand. The last of them is
    the building rule: a good whose winning building is already standing here is
    not an answer -- it would be a second one of that building, which the game
    does not offer. Which building would win is `_pm<n>` / `_prm<n>`, the method
    the harvest kept.
    """
    order = [good for kind in ("raw", "made") for good in split[kind]]
    groups = plan_groups(rows, split, game)
    shared = shared_buildings(rows, split, game)
    villages = village_entities(rows, split, game)
    out = [HEADER, f"""#
# **Written with OR and AND and never an `if`.** A scripted trigger takes an
# effect's `if` without complaining and answers true everywhere afterwards, which
# is what the buildable tick did for seventeen loads (`docs/PITFALLS.md`).
"""]
    for side, cap, listname, score, method_var, rank in (
            ("t", "urban", "town", "p", "pm", "yes"),
            ("r", "rural", "rural", "pr", "prm", "no")):
        for index, good in enumerate(order, start=1):
            by_building = groups.get((good, side), {})
            # **Деревня-сущность сюда не входит.** Её ставит собственный
            # круг `_plan_pick_v<k>`, и товару её домик не засчитывается —
            # «убрать все деревенские доли товаров и заменить их просто на
            # торговая деревня = 1 уникальный товар». Товар, у которого в
            # селе только такая деревня, становится здесь `always = no`.
            # Ворота редактора строятся отдельно и деревни сохраняют.
            if side == "r":
                by_building = {b: m for b, m in by_building.items()
                               if b not in villages}
            if not by_building:
                out.append(f"""
# {good}: no building that makes it may stand {"in a town" if side == "t" else "in a rural settlement"}.
# Scope: location
{MOD_ID}_plan_can_{listname}_{index} = {{ always = no }}
""")
                continue
            branches = ""
            for building, mis in sorted(by_building.items()):
                tests = "".join(
                    "\t\t\t\tvar:%s_%s%d = %d\n" % (MOD_ID, method_var, index, mi)
                    for mi in sorted(mis))
                # **Двое ворот, ровно те же, что у товара, — и они есть
                # только у зданий, которые умеет несколько товаров.**
                # Уровень: одно такое здание за круг, как один домик за
                # круг у товара. Потолок: та же кривая, что у квоты
                # товара, — доля земли, и сухой круг поднимает обе на
                # единицу. Вместе это и есть «пусть идёт по кругу так,
                # как если бы была однотоварной», его слова 2026-09-07.
                #
                # **Одной квоты не хватало, и это была настоящая
                # половинчатость.** Уровень у товара, а не у здания:
                # пять товаров торговой деревни ставили её пять раз за
                # круг и разбирали лучшую землю впятеро быстрее, а
                # потолок лишь обрезал итог.
                #
                # **Однотоварное здание ворот не получает**: его держат
                # ворота его товара, и второй потолок поверх них связал
                # бы раньше времени — у товара с грамотами квота выше
                # общей доли, а у здания нет.
                k = shared.index(building) + 1 if building in shared else 0
                one = ("\t\t\tglobal_var:%s_bn%d < global_var:%s_plan_lvl\n"
                       "\t\t\tglobal_var:%s_bn%d < global_var:%s_bq%d\n"
                       % (MOD_ID, k, MOD_ID, MOD_ID, k, MOD_ID, k)
                       if k else "")
                branches += f"""\t\tAND = {{
\t\t\tOR = {{
{tests}\t\t\t}}
\t\t\tNOT = {{ is_target_in_variable_list = {{ name = {MOD_ID}_plan_builds target = building_type:{building} }} }}
{one}\t\t}}
"""
            out.append(f"""
# {good}, {"town" if side == "t" else "village"} side: {len(by_building)} building(s) could win it.
# Scope: location
{MOD_ID}_plan_can_{listname}_{index} = {{
\t# **A method won here, not "the ground pays for it".** A good the RGOs feed
\t# nothing still has a gain of zero and must still be placed: «не важно есть
\t# для них сырьё на этой земле или нет».
\tvar:{MOD_ID}_{method_var}{index} > 0
\t{MOD_ID}_is_granary = no
\t{MOD_ID}_plan_is_town = {rank}
\tvar:{MOD_ID}_load < global_var:{MOD_ID}_plan_cap_{cap}
\tNOT = {{ is_target_in_variable_list = {{ name = {MOD_ID}_plan_goods target = goods:{good} }} }}
\tOR = {{
{branches}\t}}
}}
""")

    # Ворота деревни-сущности: пускает ли эта локация ещё одну такую деревню.
    #
    # **Товар выбран заранее** -- `_vw<k>` его номер, `_vb<k>` его выгода, оба
    # посчитаны `{MOD_ID}_plan_village_scores`. Здесь остаётся спросить то же,
    # что спрашивают ворота товара: своя сторона, свободная комната, этой
    # деревни тут ещё нет и её товара тут ещё нет.
    for k, building in enumerate(village_entities(rows, split, game), start=1):
        makes = [i for i, g in enumerate(order, start=1)
                 if building in (groups.get((g, "r")) or {})]
        goods_free = "".join(
            f"\t\tAND = {{\n"
            f"\t\t\tvar:{MOD_ID}_vw{k} = {i}\n"
            f"\t\t\tNOT = {{ is_target_in_variable_list = {{ name = {MOD_ID}_plan_goods "
            f"target = goods:{order[i - 1]} }} }}\n"
            f"\t\t}}\n" for i in makes)
        out.append(f"""
# {building}: {len(makes)} товар(ов) могут в ней встать.
# Scope: location
{MOD_ID}_plan_can_village_{k} = {{
\tvar:{MOD_ID}_vw{k} > 0
\t{MOD_ID}_is_granary = no
\t{MOD_ID}_plan_is_town = no
\tvar:{MOD_ID}_load < global_var:{MOD_ID}_plan_cap_rural
\tNOT = {{ is_target_in_variable_list = {{ name = {MOD_ID}_plan_builds target = building_type:{building} }} }}
\tOR = {{
{goods_free}\t}}
}}
""")

    # And one per urban right: is there anything here for it to grant?
    #
    # **A right is no longer all or nothing.** It was, until the owner settled it
    # on 2026-09-01: «каждому городу будет выдано наиболее подходящее ему право.
    # Оно БУДЕТ выдано ОБЯЗАТЕЛЬНО.» Under the old rule a bundle of three against
    # an urban cap of three had to fit exactly, and the thirty-fourth run granted
    # **one** right across six towns. The arithmetic agrees with him: a right
    # grants +20% to +50% output where the whole RGO bonus is a ten per cent
    # band, so it is the largest thing in a town by a factor of two to five
    # (`docs/investigations/plan_formula.md`).
    #
    # So this asks only whether *any* good of the bundle can be made here. Which
    # right a town gets is still decided by `{MOD_ID}_rq<k>`, the bundle's own
    # scores added up, and a bundle whose goods mostly cannot stand here loses
    # that comparison on its own without needing a gate.
    for k, right in enumerate(output_rights(rows, game), start=1):
        bundle = sorted(right.output)
        wanted = [g for g in bundle if g in order and groups.get((g, "t"))]
        if not wanted:
            out.append(f"""
# {right.key}: no good of its bundle can stand in a town at all.
# Scope: location
{MOD_ID}_plan_right_fits_{k} = {{ always = no }}
""")
            continue
        def _fit(g: str) -> str:
            i = order.index(g) + 1
            mis = right_methods(right, g, rows)
            if not mis:
                return "\t\t%s_plan_can_town_%d = yes\n" % (MOD_ID, i)
            return ("\t\tAND = {\n"
                    "\t\t\t%s_plan_can_town_%d = yes\n"
                    "\t\t\tOR = { %s }\n"
                    "\t\t}\n" % (MOD_ID, i,
                                   " ".join(f"var:{MOD_ID}_pm{i} = {mi}"
                                            for mi in mis)))

        tests = "".join(_fit(g) for g in wanted)
        out.append(f"""
# {right.key}: {", ".join(wanted)}. Granted if any one of them can be made here.
# Scope: location
{MOD_ID}_plan_right_fits_{k} = {{
\t{MOD_ID}_is_granary = no
\tOR = {{
{tests}\t}}
}}
""")

        # **И тот же вопрос, заданный факту, а не воротам.**
        #
        # `_plan_right_fits_<k>` -- ворота **постановки**: внутри `_plan_can_town_<i>`
        # сидит «в городе ещё есть комната» и «этого товара тут ещё нет». На
        # раздаче город пуст и оба верны; **после** плана каждый город полон, и
        # ворота отвечают «нет» везде. Ровно этим `WTP RQ` вышел тринадцатью
        # нулями 2026-09-03, и ровно этим вторая страница сводки вышла нулями в
        # столбцах «Подходит» и «Лучшая» 2026-09-13: «столбы полностью нули,
        # хотя очевидно там есть те, что подходят по кормлению земли».
        #
        # Здесь спрашивается то, что было правдой в момент раздачи и остаётся ею
        # навсегда: **городской метод этого товара выиграл здесь** (`_pm<i> > 0`),
        # с той же оговоркой про конкретное здание, что и у `_rq<k>`.
        won = "".join(
            "\t\t%s\n" % (
                f"var:{MOD_ID}_pm{order.index(g) + 1} > 0"
                if not right_methods(right, g, rows) else
                "AND = { var:%s_pm%d > 0 OR = { %s } }" % (
                    MOD_ID, order.index(g) + 1,
                    " ".join(f"var:{MOD_ID}_pm{order.index(g) + 1} = {mi}"
                             for mi in right_methods(right, g, rows))))
            for g in wanted)
        out.append(f"""
# {right.key}: подходил ли этот город хоть одним товаром связки -- факт, а не
# ворота. Читается сводкой после плана, когда ворота уже врут.
# Scope: location
{MOD_ID}_plan_right_won_{k} = {{
\t{MOD_ID}_is_granary = no
\tOR = {{
{won}\t}}
}}
""")

    # And whether this country may grant it at all, at the age the plan is being
    # drawn for. `plan_right_gates` is why this is not the window's question.
    out.append(f"""
# **Who may grant which charter, and when.** One trigger a right, asked by the
# grant pass, by the quota that divides the towns between them and by the dump --
# three places that used to carry three copies of the same condition, one of
# which (the dump's) was not asked at all and printed charters nobody could have.
""")
    for k, (right, body) in enumerate(
            zip(output_rights(rows, game), plan_right_gates(rows, game)), start=1):
        out.append(f"""
# {right.key}{": " + right.advance if right.advance else ""}
# Scope: country
{MOD_ID}_plan_right_gate_{k} = {{
{body}
}}
""")

    # ---- шаг 7: две фишки в списке зданий локации ---------------------------
    #
    # **Фишка -- это `gui/filters/*.txt`, а не окно.** Панель зовёт свои фильтры
    # через `WithFilterTags('building')`, и любой мод, положивший туда файл со
    # `scope = building_type`, получает свою галочку в том же ряду -- и в
    # ванильной панели, и в чужой, которая её перекрыла. Никакого `.gui` Glorp UI
    # для этого трогать не надо; решение «перекрывать их файл целиком или класть
    # своё окно рядом» отпало вместе с вопросом.
    #
    # **`root` -- это сам тип здания**, так пишет `gui/filters/readme.txt` игры и
    # так работает `bag_rgo_location_feeds_root` в соседнем моде. А вот
    # `scope:target` в фильтре типа зданий не приходит, что бы ни говорил
    # ванильный комментарий: чтение его пишет ошибку каждый проход.
    #
    # **Локацию приносит общая проба** -- `bag_view_location`, см.
    # `common/scripted_guis/bag_shared_view_location.txt`.
    #
    # Две фишки, потому что они отвечают на разное и ломаются по-разному. Первая
    # ничего не знает про локацию и не может не сработать -- она список типов,
    # известный на сборке. Если в игре видно её и не видно вторую, причина
    # названа без второго прогона: проба не записала локацию.
    # **Деревни здесь ровня всем прочим.** Владелец, 2026-09-09: «деревни не
    # предлагаются в фильтре, а должны». В обмене их выделяют потому, что одна
    # деревня стоит за несколько товаров; для списка зданий локации она такое же
    # здание, как любое другое, и план кладёт её в `_plan_builds` наравне.
    plan_builds = sorted({b for key in groups for b in groups[key]})
    listed = "".join(f"\t\tthis = building_type:{b}\n" for b in plan_builds)

    def in_list(building: str, tab: str) -> str:
        return (f"{tab}is_target_in_variable_list = {{ name = {MOD_ID}_plan_builds "
                f"target = building_type:{building} }}\n")

    # **Ступень, которая по зубам, когда план поставил ту, что не по зубам.**
    #
    # План «на конец» ставит мельницу, а строить можно мастерскую -- и панель
    # мельницу даже не покажет, так что строка товара пропадает целиком. Поэтому
    # здание проходит фильтр ещё и тогда, когда план поставил сюда ступень
    # **над** ним, и ни одна ступень между ними стране сейчас не доступна:
    # показывается ровно одна -- самая высокая из доступных.
    #
    # `_ba_<здание>` считает `{MOD_ID}_set_bavail` в скоупе страны; у фильтра
    # страны нет вовсе, поэтому ответ и лежит готовым числом.
    here = ""
    for b in plan_builds:
        branches = in_list(b, "\t" * 4)
        blocked = []
        for upper in ladder_above(b, game):
            # Каждая ступень между нами и поставленной обязана быть недоступной,
            # иначе показывать надо её, а не нас.
            branches += (f"\t\t\t\tAND = {{\n"
                         + in_list(upper, "\t" * 5)
                         + "".join(f"\t\t\t\t\tNOT = {{ global_var:{MOD_ID}_ba_{a} = 1 }}\n"
                                   for a in blocked + [upper])
                         + f"\t\t\t\t}}\n")
            blocked.append(upper)
        here += (f"\t\tAND = {{\n"
                 f"\t\t\tthis = building_type:{b}\n"
                 f"\t\t\tglobal_var:bag_view_location = {{\n"
                 f"\t\t\t\tOR = {{\n{branches}\t\t\t\t}}\n"
                 f"\t\t\t}}\n"
                 f"\t\t}}\n")
    out.append(f"""
# **Здания, которыми план вообще умеет строить** -- {len(plan_builds)} из тех, что
# есть в игре. Список известен на сборке, так что фишка стоит одно сравнение и
# ничего не читает: она сужает список локации до производственных зданий этого
# мода, и она же -- признак того, что фишки мода вообще доходят до панели.
# Scope: building_type
{MOD_ID}_type_is_planned = {{
\tOR = {{
{listed}\t}}
}}

# **Здания, которые план ставит именно здесь.** `_plan_builds` -- список типов на
# самой локации, его ведут и раздача, и редактор, так что фишка показывает то,
# что на карте сейчас: загрузили слот -- показывает слот.
#
# **`root` в фильтре -- не отфильтровываемый объект, что бы ни говорил
# `58_building_type.txt`.** Прогон 2026-09-09: фишка на `target = root` не
# оставила ни одного здания при `view_location=1` и `_plan_builds`, заполненном
# на 454 локациях; единственная другая фишка в репозитории, читавшая `root`
# (`bag_rgo_has_local_bonus`), -- ровно та, что никогда не работала, а все
# работающие спрашивают неявный `this`. Комментарий игры врёт про `root` так же,
# как он уже соврал про `scope:target`; в `06_country.txt` она сама пишет «root
# is player».
#
# Отсюда форма: **`this = building_type:X` до смены скоупа**, а внутрь идёт
# литерал. Ни одного `root`.
# Scope: building_type
{MOD_ID}_type_in_plan_here = {{
\thas_global_variable = bag_view_location
\tOR = {{
{here}\t}}
}}
""")
    return "".join(out)


def plan_loc_file(rows: list[eu5data.Method], split: dict[str, list[str]],
                  game: eu5data.Game) -> str:
    """Which urban right a town was given, as text a row can print.

    A number on the location is all script can park there, and a row has to name
    the right. A `customizable_localization` of this mod's own is the way across
    -- defining one is fine; it is only overriding somebody else's that cannot be
    done (`CLAUDE.md`). The keys it points at are the ones the rights list on the
    mod page uses, icon and all.
    """
    rights = output_rights(rows, game)
    out = [HEADER, f"""#
# Every branch asks `has_variable` first. A row is drawn once a frame, and a
# comparison against a variable that is not there is an error per row per frame.
#
# Scope: location
{MOD_ID}_plan_right_label = {{
\ttype = location
"""]
    for k, right in enumerate(rights, start=1):
        out.append(f"""\ttext = {{
\t\ttrigger = {{ has_variable = {MOD_ID}_plan_right var:{MOD_ID}_plan_right = {k} }}
\t\tlocalization_key = {MOD_ID}_right_{right.key}
\t}}
""")
    out.append(f"""\ttext = {{
\t\tfallback = yes
\t\tlocalization_key = {MOD_ID}_plan_no_right
\t}}
}}

# **Какая грамота сидит на месте p, словами и числом.**
#
# Ячейка редактора написана под *место*, а не под грамоту: места заполняются
# подряд, так что дыр в ряду не бывает вовсе. Номер в число и в имя переводит вот
# этот диспетчер -- по одному на каждое место, тринадцать веток в каждом. Дорого
# на вид и даром на деле: обе строки рисуются раз в кадр и читают одну глобалку.
""")
    for p_slot in range(1, len(rights) + 1):
        for kind, key in (("name", f"{MOD_ID}_right_%s"),
                          ("count", f"{MOD_ID}_edit_rcount_%s")):
            out.append(f"""
# Scope: country
{MOD_ID}_rslot_{kind}_{p_slot} = {{
\ttype = country
""")
            for k, right in enumerate(rights, start=1):
                target = key % (right.key if kind == "name" else k)
                out.append(f"""\ttext = {{
\t\ttrigger = {{ global_var:{MOD_ID}_rslot{p_slot} = {k} }}
\t\tlocalization_key = {target}
\t}}
""")
            out.append(f"""\ttext = {{
\t\tfallback = yes
\t\tlocalization_key = {MOD_ID}_rslot_empty
\t}}
}}
""")
    # ---- наш собственный разбор покрытия ----------------------------------
    #
    # **Число без разбора он читать отказался.** 2026-09-14, глядя на столбец
    # «Пригодность»: «я вижу текст "текстиль 100%" а с чего бы он 100%? Я этого
    # не вижу. Должно быть указано что он там например использует предполагаемо
    # шерсть 1/1». И следом: «нет общей простой лесенки по правам и их
    # проценту».
    #
    # **Подсказка показывала не то, что считает столбец.** В ней стояли
    # `_trmm_ur_rank_bd_slot_*` -- разбор КАРТЫ, по числам CM, -- а в столбце
    # наше `_rq<k>`, которое считает по доступным способам. Два разных счёта в
    # одном месте: у него в подсказке «Права на книгопечатание 76.1%», а в
    # столбце 236.1%, и сойтись они не могли никогда. Теперь подсказка целиком
    # наша: лесенка по нашим `_rqv<k>` и разбор отмеченной грамоты по нашим
    # `_cov_<товар>`.
    cov_goods = sorted({m.produced for m in rows
                        if m.produced in COV_GOODS and m.inputs
                        and any(r in game.raw_goods for r in m.inputs)})
    out.append(f"""
# **Чем именно взято покрытие товара**: способ, который здесь победил, и его
# сырьё поимённо. Номер способа лежит на локации (`_covm_<товар>`), потому что
# выбрал его тот же проход, который посчитал число.
""")
    for good in cov_goods:
        out.append(f"""# Scope: location
{MOD_ID}_cov_why_{good} = {{
	type = location
""")
        for mi, method in enumerate(rows, start=1):
            if method.produced != good or not method.inputs:
                continue
            if not any(r in game.raw_goods for r in method.inputs):
                continue
            out.append(f"""	text = {{
		trigger = {{ var:{MOD_ID}_covm_{good} = {mi} }}
		localization_key = {MOD_ID}_covm_{mi}
	}}
""")
        out.append(f"""	text = {{
		fallback = yes
		localization_key = {MOD_ID}_cov_no_method
	}}
}}
""")
    out.append(f"""
# **Лесенка прав по нашему счёту.** Место `n` рисует ту грамоту, у которой
# `_rqr<k>` равен `n-1`; ранги считает `_score_right_*`, строго упорядоченно,
# поэтому равные счётом не делят одно место и ни одна строка не пропадает.
""")
    for n in range(1, len(rights) + 1):
        out.append(f"""# Scope: location
{MOD_ID}_rq_slot_{n} = {{
	type = location
""")
        for k in range(1, len(rights) + 1):
            out.append(f"""	text = {{
		trigger = {{ has_variable = {MOD_ID}_rqr{k} var:{MOD_ID}_rqr{k} = {n - 1} }}
		localization_key = {MOD_ID}_rq_line_{k}
	}}
""")
        out.append(f"""	text = {{
		fallback = yes
		localization_key = {MOD_ID}_trmm_blank
	}}
}}
""")
    # **Строка товара в двух видах, и пустое слагаемое не печатается.** Его
    # слово 2026-09-14: «вообще там в целом не должно быть этой мусорной строки
    # +0%». Там, где местный модификатор ноль -- а после вычитания выданной
    # грамоты он ноль чаще всего, -- строка короткая: товар и его процент.
    # **Эпоха называется в каждой подсказке, которая от неё зависит.** Его слово
    # 2026-09-14: «чтобы всё и везде чётко разграничивалось что советует и
    # рассчитывает и на какую эпоху -- текущую или последнюю. Я уже раз 50 на
    # этой теме правки вношу за тобой». У каждого окна свой тумблер, поэтому и
    # подписи две -- одна на всех врала бы про то окно, чей тумблер не её.
    #
    # **Две области видимости у одной подписи, потому что зовут её из обеих.**
    # Подсказка строки читает локацию, подсказка столбца сводки -- державу;
    # `customizable_localization` принадлежит той области, из которой позван, и
    # чужой там не работает. Триггер у обеих один -- глобалка.
    for name, switch in (("plan", "plan_by_end"), ("rank", "rank_by_end")):
        for suffix, scope in (("", "location"), ("_c", "country")):
            out.append(f"""# Scope: {scope}
{MOD_ID}_age_{name}{suffix} = {{
\ttype = {scope}
\ttext = {{
\t\ttrigger = {{ has_global_variable = {MOD_ID}_{switch} }}
\t\tlocalization_key = {MOD_ID}_age_end
\t}}
\ttext = {{
\t\tfallback = yes
\t\tlocalization_key = {MOD_ID}_age_now
\t}}
}}
""")
    # **Подробности -- три лучших права локации, а не одно.** Его слово
    # 2026-09-14: «ниже в подробностях должны показываться как минимум 3
    # варианта топовых прав для локации, а не только текущее топовое право». И
    # это одни и те же три места в обоих окнах: лесенка считается одинаково,
    # значит и разбор под ней -- один.
    for place in (1, 2, 3):
        out.append(f"""
# Разбор права, стоящего на {place}-м месте лесенки: имя и товары связки.
# Scope: location
{MOD_ID}_rq_bd_slot_{place} = {{
\ttype = location
""")
        for k in range(1, len(rights) + 1):
            out.append(f"""\ttext = {{
\t\ttrigger = {{ has_variable = {MOD_ID}_rqr{k} var:{MOD_ID}_rqr{k} = {place - 1} }}
\t\tlocalization_key = {MOD_ID}_rq_bd_{k}
\t}}
""")
        out.append(f"""\ttext = {{
\t\tfallback = yes
\t\tlocalization_key = {MOD_ID}_trmm_blank
\t}}
}}
""")

    out.append(f"""
# **The charter this town held in the *saved* plan.** «Показать изменения» lists
# what left and what arrived, and until 2026-09-06 a charter moving between towns
# showed only as its buildings: «тогда уж там должна показываться вся связка —
# право, товары ушли — право, товары встали». `_save_right` is written by the
# same effect that writes `_save_goods`, so the two halves of a row are read the
# same way.
#
# Scope: location
{MOD_ID}_save_right_label = {{
\ttype = location
""")
    for k, right in enumerate(rights, start=1):
        out.append(f"""\ttext = {{
\t\ttrigger = {{ has_variable = {MOD_ID}_save_right var:{MOD_ID}_save_right = {k} }}
\t\tlocalization_key = {MOD_ID}_right_{right.key}
\t}}
""")
    out.append(f"""\ttext = {{
\t\tfallback = yes
\t\tlocalization_key = {MOD_ID}_plan_no_right
\t}}
}}
""")
    # **The editor's own two branching labels.** A plain localization key reads a
    # number through a script value -- `{MOD_ID}_plan_pass_summary` is nothing but
    # those -- but it cannot choose between two sentences, and both of these have
    # to: an empty slot must not read «0 buildings in 0 locations», and a «+1»
    # that a rule refused must not look like one that worked.
    for n in range(1, EDIT_SLOTS + 1):
        out.append(f"""
# Slot {n}: what it holds, or that it holds nothing.
# Scope: country
{MOD_ID}_edit_slot{n}_label = {{
\ttype = country
\ttext = {{
\t\ttrigger = {{ global_var:{MOD_ID}_sl{n}_n > 0 }}
\t\tlocalization_key = {MOD_ID}_edit_slot{n}_full
\t}}
\ttext = {{
\t\tfallback = yes
\t\tlocalization_key = {MOD_ID}_edit_slot{n}_empty
\t}}
}}
""")
    rfrom_branches = "".join(
        f"\ttext = {{\n"
        f"\t\ttrigger = {{ global_var:{MOD_ID}_edit_rfrom = {k} }}\n"
        f"\t\tlocalization_key = {MOD_ID}_right_{right.key}\n"
        f"\t}}\n"
        for k, right in enumerate(rights, start=1))
    rto_branches = "".join(
        f"\ttext = {{\n"
        f"\t\ttrigger = {{ global_var:{MOD_ID}_edit_rto = {k} }}\n"
        f"\t\tlocalization_key = {MOD_ID}_right_{right.key}\n"
        f"\t}}\n"
        for k, right in enumerate(rights, start=1))
    out.append(f"""
# Whether the last «+1» or «−1» did anything. **An effect that merely does
# nothing logs nothing at all**, and both of them have rules that refuse: a good
# fitting nowhere on this ground, a good down to its last building, a building
# belonging to a charter's bundle. `_edit_done` is set to 0 before the walk and
# to 1 by the walk. **The branches name the cause, and they exist because a
# single «не дало правило» was read as the mod being stubborn when it was the
# ground.** He pressed «+1» on iron: four locations of Westphalia can make iron
# and iron stood in all four, so there was nowhere for a fifth. The editor has
# only the two rules he agreed to -- never a good's last building, never a
# charter bundle's -- and it reads no quota of the plan's at all.
#
# **`_edit_fail` is the branch that had to exist and did not.** The walk used to
# say «сделано» whenever it found a location, whether or not a building actually
# went in, so a press that evicted something and then failed to place read as a
# success. It cannot happen now -- the victim goes back -- but the window must
# still say that the press did nothing, and why.
# Scope: country
# The charter `_edit_rfrom` names, in the game's own wording. A number
# reaches no name in localization, so this is the dispatch that does it.
# Scope: country
{MOD_ID}_edit_rfrom_name = {{
	type = country
{rfrom_branches}	text = {{
		fallback = yes
		localization_key = {MOD_ID}_edit_right_unnamed
	}}
}}

# The charter `_edit_rto` names, in the game's own wording. A number
# reaches no name in localization, so this is the dispatch that does it.
# Scope: country
{MOD_ID}_edit_rto_name = {{
	type = country
{rto_branches}	text = {{
		fallback = yes
		localization_key = {MOD_ID}_edit_right_unnamed
	}}
}}

# Что сделала последняя доливка, тремя ветками.
#
# **«Не нажимали» и «нажали, а новой земли не было» -- разные ответы, и оба
# нужны.** Кнопка, которая ничего не сделала, потому что доливать нечего, и
# кнопка, которая не дошла до эффекта, на экране выглядят одинаково; строка,
# молчащая в обоих случаях, -- ровно та немота, из-за которой в этом моде уже
# терялись прогоны.
{MOD_ID}_edit_ext_label = {{
\ttype = country
\ttext = {{
\t\ttrigger = {{ global_var:{MOD_ID}_ext_ran = 0 }}
\t\tlocalization_key = {MOD_ID}_edit_ext_none
\t}}
\ttext = {{
\t\ttrigger = {{ global_var:{MOD_ID}_ext_new = 0 }}
\t\tlocalization_key = {MOD_ID}_edit_ext_empty
\t}}
\ttext = {{
\t\tfallback = yes
\t\tlocalization_key = {MOD_ID}_edit_ext_done
\t}}
}}

{MOD_ID}_edit_last_label = {{
\ttype = country
\ttext = {{
\t\ttrigger = {{ global_var:{MOD_ID}_edit_op = 0 }}
\t\tlocalization_key = {MOD_ID}_edit_last_none
\t}}
\ttext = {{
\t\ttrigger = {{ global_var:{MOD_ID}_edit_done = 1 global_var:{MOD_ID}_edit_norefill = 1 }}
\t\tlocalization_key = {MOD_ID}_edit_last_empty
\t}}
\t# **What the press actually did, and this is the instrument.** «Сделано» is
\t# true and useless: it cannot tell a «+1» that landed in a free room from one
\t# that took a building off another good, and every rule from here on is a rule
\t# about which of those happened. The four branches below name the good, the
\t# location and the good that moved, off the scopes the walk parked.
\t#
\t# `_edit_last_done` stays as the last of them. Nothing should reach it -- a
\t# finished press is op 1 or op 2 -- and if the window ever prints it, the
\t# press did something these branches do not describe.
\t# **Деревня называется домиком, а не товаром**, и поэтому у неё свои два
\t# кода операции: одного товара, за который её ставят, у неё нет -- есть
\t# здание, которое встало или ушло.
\ttext = {{
\t\ttrigger = {{
\t\t\tglobal_var:{MOD_ID}_edit_done = 1
\t\t\tglobal_var:{MOD_ID}_edit_op = 5
\t\t\tglobal_var:{MOD_ID}_edit_evicted = 1
\t\t}}
\t\tlocalization_key = {MOD_ID}_edit_last_vill_over
\t}}
\ttext = {{
\t\ttrigger = {{ global_var:{MOD_ID}_edit_done = 1 global_var:{MOD_ID}_edit_op = 5 }}
\t\tlocalization_key = {MOD_ID}_edit_last_vill_add
\t}}
\ttext = {{
\t\ttrigger = {{ global_var:{MOD_ID}_edit_done = 1 global_var:{MOD_ID}_edit_op = 6 }}
\t\tlocalization_key = {MOD_ID}_edit_last_vill_drop
\t}}
\ttext = {{
\t\ttrigger = {{
\t\t\tglobal_var:{MOD_ID}_edit_done = 1
\t\t\tglobal_var:{MOD_ID}_edit_op = 1
\t\t\tglobal_var:{MOD_ID}_edit_evicted = 1
\t\t}}
\t\tlocalization_key = {MOD_ID}_edit_last_add_over
\t}}
\ttext = {{
\t\ttrigger = {{ global_var:{MOD_ID}_edit_done = 1 global_var:{MOD_ID}_edit_op = 1 }}
\t\tlocalization_key = {MOD_ID}_edit_last_add_free
\t}}
\ttext = {{
\t\ttrigger = {{ global_var:{MOD_ID}_edit_done = 1 global_var:{MOD_ID}_edit_op = 2 }}
\t\tlocalization_key = {MOD_ID}_edit_last_drop_refill
\t}}
\t# **A charter press is a move and its line has to say both ends.**
\t# Which charter left the town and which arrived are numbers, and a
\t# number has no name -- `_edit_rfrom_name` and `_edit_rto_name` are
\t# the thirteen-branch dispatches that turn them into the game's own
\t# wording.
\t# **Before both «сделано» branches**: the charter did move, and the
\t# town could not give up enough rooms for its bundle. Half a bundle is
\t# a state the player has to be told about, not one to read off a map.
\ttext = {{
\t\ttrigger = {{ global_var:{MOD_ID}_edit_done = 1 global_var:{MOD_ID}_edit_rshort > 0 }}
\t\tlocalization_key = {MOD_ID}_edit_last_right_short
\t}}
\ttext = {{
\t\ttrigger = {{ global_var:{MOD_ID}_edit_done = 1 global_var:{MOD_ID}_edit_op = 3 }}
\t\tlocalization_key = {MOD_ID}_edit_last_right_add
\t}}
\ttext = {{
\t\ttrigger = {{ global_var:{MOD_ID}_edit_done = 1 global_var:{MOD_ID}_edit_op = 4 }}
\t\tlocalization_key = {MOD_ID}_edit_last_right_drop
\t}}
\ttext = {{
\t\ttrigger = {{ global_var:{MOD_ID}_edit_done = 1 }}
\t\tlocalization_key = {MOD_ID}_edit_last_done
\t}}
\ttext = {{
\t\ttrigger = {{ global_var:{MOD_ID}_edit_reached = 0 }}
\t\tlocalization_key = {MOD_ID}_edit_last_lost
\t}}
\t# **Before the goods' own refusal, because op 4 fails for its own
\t# reason**: the town's charter could go, and no other charter this
\t# country may grant can stand there.
\ttext = {{
\t\ttrigger = {{ global_var:{MOD_ID}_edit_op = 4 global_var:{MOD_ID}_edit_fail = 1 }}
\t\tlocalization_key = {MOD_ID}_edit_last_right_noheir
\t}}
\ttext = {{
\t\ttrigger = {{ global_var:{MOD_ID}_edit_op = 3 }}
\t\tlocalization_key = {MOD_ID}_edit_last_right_notown
\t}}
\ttext = {{
\t\ttrigger = {{ global_var:{MOD_ID}_edit_op = 4 }}
\t\tlocalization_key = {MOD_ID}_edit_last_right_none
\t}}
\ttext = {{
\t\ttrigger = {{ global_var:{MOD_ID}_edit_fail = 1 }}
\t\tlocalization_key = {MOD_ID}_edit_last_refill
\t}}
\ttext = {{
\t\ttrigger = {{ global_var:{MOD_ID}_edit_op = 1 global_var:{MOD_ID}_edit_fitn = 0 }}
\t\tlocalization_key = {MOD_ID}_edit_last_nowhere
\t}}
\ttext = {{
\t\ttrigger = {{ global_var:{MOD_ID}_edit_op = 1 global_var:{MOD_ID}_edit_cands = 0 }}
\t\tlocalization_key = {MOD_ID}_edit_last_novictim
\t}}
\ttext = {{
\t\ttrigger = {{ global_var:{MOD_ID}_edit_op = 2 global_var:{MOD_ID}_edit_fitn < 2 }}
\t\tlocalization_key = {MOD_ID}_edit_last_lastone
\t}}
\ttext = {{
\t\ttrigger = {{ global_var:{MOD_ID}_edit_op = 2 global_var:{MOD_ID}_edit_cands = 0 }}
\t\tlocalization_key = {MOD_ID}_edit_last_allcharter
\t}}
\ttext = {{
\t\tfallback = yes
\t\tlocalization_key = {MOD_ID}_edit_last_refused
\t}}
}}
""")

    # **Почему товар остановился именно на этом числе, словами.** Диспетчер на
    # товар, восемь веток, читает одну глобалку `_wr<n>`, которую пишет
    # `bag_wtp_plan_summary`. Восемь флагов на товар вместо неё стоили бы семью
    # глобалками больше на каждый, а `visible` в `.gui` всё равно умеет только
    # `.IsSet` -- диспетчер дешевле и читается.
    for i in range(1, len(goods_order(split)) + 1):
        out.append(f"""
# Scope: country
{MOD_ID}_why_{i} = {{
\ttype = country
""")
        for code, key in ((1, "none"), (2, "room"), (3, "quota"), (4, "capt"),
                          (5, "capr"), (6, "lock"), (7, "skip"), (9, "lost"),
                          (10, "taken")):
            out.append(f"""\ttext = {{
\t\ttrigger = {{ global_var:{MOD_ID}_wr{i} = {code} }}
\t\tlocalization_key = {MOD_ID}_why_{key}
\t}}
""")
        out.append(f"""\ttext = {{
\t\tfallback = yes
\t\tlocalization_key = {MOD_ID}_why_open
\t}}
}}
""")

    # **И то же самое на грамоту, для второй страницы сводки.** Пять веток,
    # одна глобалка `_rwhy<k>`, и ни одна ветка не повторяет товарную: у
    # грамоты нет ни потолков сторон, ни «не нужен», ни замка.
    for k in range(1, len(output_rights(rows, game)) + 1):
        out.append(f"""
# Scope: country
{MOD_ID}_rwhy_{k} = {{
\ttype = country
""")
        for code, key in ((1, "gate"), (2, "noland"), (3, "off"), (4, "quota")):
            out.append(f"""\ttext = {{
\t\ttrigger = {{ global_var:{MOD_ID}_rwhy{k} = {code} }}
\t\tlocalization_key = {MOD_ID}_rwhy_{key}
\t}}
""")
        out.append(f"""\ttext = {{
\t\tfallback = yes
\t\tlocalization_key = {MOD_ID}_rwhy_beaten
\t}}
}}
""")

    # **Клетка «доля −РГО» -- тоже диспетчер, и по той же причине.** Приписку
    # «−N» пробовали через `SelectLocalization` с вложенным `GreaterThan_int32`
    # -- форма из игры, но в клетке сводки она сломала столбец целиком
    # (2026-09-09). Здесь два готовых ключа и выбор между ними: ровно то, что в
    # этом же окне работает у «почему остановился».
    for i in range(1, len(goods_order(split)) + 1):
        out.append(f"""
# Scope: country
{MOD_ID}_quota_{i} = {{
\ttype = country
\ttext = {{
\t\ttrigger = {{ global_var:{MOD_ID}_short{i} > 0 }}
\t\tlocalization_key = {MOD_ID}_sum_quotaA_{i}
\t}}
\ttext = {{
\t\tfallback = yes
\t\tlocalization_key = {MOD_ID}_sum_quotaB_{i}
\t}}
}}
""")
    return "".join(out)


def grant_bundle_blocks(rights, order, groups, substitute, tab: str,
                        level_counter: bool = True) -> str:
    """The charter's own buildings, put down on a town that has just taken it.

    **Written once and emitted three times.** The even plan's grant pass, its
    province-wide twin and the specialisation's place the identical bundle,
    keyed on the identical `_rbest_k` -- three copies would be three places for
    the substitute rule and the three counters to drift apart.

    **`level_counter` -- единственное, чем отличается провинциальный проход.**
    `_rn<k>` это лестница уровней и делитель доли, и в нём считаются те
    единицы, между которыми грамоты делят поровну: города в обычном проходе и
    **провинции** в провинциальном. Поэтому там он прибавляется один раз на
    провинцию, снаружи обхода её городов, а здесь его нет вовсе.
    """
    out = []
    for k, right in enumerate(rights, start=1):
        bundle = sorted(right.output)
        lines = []
        for g in bundle:
            if not groups.get((g, "t")):
                continue
            i = order.index(g) + 1
            feeder = substitute.get(g)
            j = order.index(feeder) + 1 if feeder in order else 0
            if j and groups.get((feeder, "t")):
                lines.append(
                    f"{tab}\tif = {{\n"
                    f"{tab}\t\tlimit = {{ {MOD_ID}_plan_can_town_{i} = yes }}\n"
                    f"{tab}\t\t{MOD_ID}_plan_try_town_{i} = yes\n"
                    f"{tab}\t}}\n"
                    f"{tab}\telse = {{\n"
                    f"{tab}\t\t# {g} cannot stand here; plant the {feeder} that would let it.\n"
                    f"{tab}\t\t{MOD_ID}_plan_try_town_{j} = yes\n"
                    f"{tab}\t}}\n")
            else:
                lines.append(f"{tab}\t{MOD_ID}_plan_try_town_{i} = yes\n")
        adds = "".join(lines)
        level = (f"{tab}\tchange_global_variable = {{ name = {MOD_ID}_rn{k} add = 1 }}\n"
                 if level_counter else "")
        out.append(f"""{tab}if = {{
{tab}\tlimit = {{ var:{MOD_ID}_rbest_k = {k} }}
{adds}{tab}\tset_variable = {{ name = {MOD_ID}_plan_right value = {k} }}
{tab}\t# **One counter, over the whole ground.** `_rn<k>` is what the quota reads;
{tab}\t# `_rgiven<k>` is the same number for the dump, kept apart so that changing
{tab}\t# what the plan counts never quietly changes what the report prints.
{level}{tab}\tchange_global_variable = {{ name = {MOD_ID}_rgiven{k} add = 1 }}
{tab}\tchange_global_variable = {{ name = {MOD_ID}_plan_rightn add = 1 }}
{tab}}}
""")
    return "".join(out)


def plan_file(rows: list[eu5data.Method], split: dict[str, list[str]],
              game: eu5data.Game) -> str:
    """The whole-map plan: every good placed at once over the chosen ground.

    The owner's answers and the design are in
    `docs/investigations/whole_map_plan.md`. Five things belong in front of the
    code.

    **It is decided per location.** The plan spent one build deciding per
    province and giving every location of it the same list, and the thirty-second
    load is why it does not: a market village makes tools, jewelry, beer and
    pottery, so four villages of one province can take one each rather than all
    taking pottery. Provinces still read as coherent wherever they deserve to --
    every location of a province scores the same, so the ordered walk keeps
    coming back to it -- but that is now something that happens rather than
    something imposed.

    **An entry is a building, and a location holds one of each.** Two goods off
    the same building are one answer here; the same two goods in two locations
    are two.

    **Every building is one the game says may stand there.** `can_build_building`
    in a location's scope is the rank, the terrain and `location_potential`, and
    never an advance, so it is as true for ground nobody owns and for the plan
    aimed at the last age.

    **The score is normalized per good.** `out * (1 + bonus/100)` is in units of
    the good -- 1.0 of lumber against 0.2 of wine -- so each good is divided by
    its own best in this ground, one divisor for both sides, and only then do the
    numbers compare.

    **The scarce go first.** A good with one place in the whole ground that can
    hold it takes that place before a good with forty gets its second: the sweeps
    run in tiers, and a tier only admits goods that few locations can host. That
    is the owner's «жёстко зарезервировать слоты» and it costs one comparison.
    """
    order = [good for kind in ("raw", "made") for good in split[kind]]
    # ---- житницы: свой круг, свои домики, ничьи места ----------------------
    #
    # **Житница выпадает из плана как место и заполняется отдельно.** Его слово
    # 2026-09-13: «он теперь должен добавлять в план на этой локации
    # земледельческую деревню и другие здания, которые увеличивают добываемую
    # пищу или в целом добычу РГО… В общую сводку они не идут и за места ни с
    # кем в плане не борются.»
    #
    # Поэтому круг стоит **после** раздачи товаров и грамот, ходит только по
    # помеченным локациям и ни одного счётчика товара не трогает: `_pn<n>`,
    # `_plan_gain` и `_plan_fed` остаются такими, будто житницы нет вовсе --
    # ровно как её комнаты не считаются в `_plan_rooms` с 2026-09-08.
    #
    # **Товар в строке -- собственное сырьё локации.** `_plan_goods` и
    # `_plan_builds` обязаны идти индекс в индекс (`ROWPAIR`), а житница по
    # определению стоит на продовольственном РГО: строка читается «пшеница --
    # Земледельческая деревня», и это правда о том, что там будет.
    #
    # **Ворота -- сама игра, оба раза.** `can_build_building` в скоупе локации
    # отвечает за ранг и `location_potential`, в скоупе страны -- за
    # продвижения. Тумблер ранга к житнице не применяется вовсе: она то, что
    # она есть.
    gran = granary_buildings()

    def gran_put(tab: str) -> str:
        out_ = ""
        for building in gran:
            source = source_of(building)
            # Галочка мода-источника, та же, что у `_avail_<n>`: снятая
            # закрывает его зданиям ворота, а не убирает их из файлов.
            src = (f"{tab}\t\tglobal_var:{MOD_ID}_src{source} = 1\n" if source else "")
            out_ += f"""{tab}if = {{
{tab}\tlimit = {{
{tab}\t\tOR = {{
{tab}\t\t\tAND = {{ {MOD_ID}_plan_is_town = yes
{tab}\t\t\t\tvar:{MOD_ID}_load < global_var:{MOD_ID}_plan_cap_urban }}
{tab}\t\t\tAND = {{ {MOD_ID}_plan_is_town = no
{tab}\t\t\t\tvar:{MOD_ID}_load < global_var:{MOD_ID}_plan_cap_rural }}
{tab}\t\t}}
{tab}\t\tNOT = {{ is_target_in_variable_list = {{ name = {MOD_ID}_plan_builds target = building_type:{building} }} }}
{tab}\t\tcan_build_building = building_type:{building}
{src}{tab}\t\tscope:{MOD_ID}_country = {{ can_build_building = building_type:{building} }}
{tab}\t}}
{tab}\tadd_to_variable_list = {{ name = {MOD_ID}_plan_builds target = building_type:{building} }}
{tab}\tchange_variable = {{ name = {MOD_ID}_load add = 1 }}
{tab}\tchange_global_variable = {{ name = {MOD_ID}_plan_placed add = 1 }}
{tab}\tchange_global_variable = {{ name = {MOD_ID}_gran_put add = 1 }}
{tab}}}
"""
        return out_

    rights = output_rights(rows, game)
    groups = plan_groups(rows, split, game)
    shared = shared_buildings(rows, split, game)
    # **Счётчики зданий обнуляет только свежий план.** Доливка их
    # продолжает: она достраивает тот же план на новой земле, и
    # универсальная деревня не должна получить второй потолок просто
    # потому, что земля расширилась.
    bzero = "".join(
        f"\tset_global_variable = {{ name = {MOD_ID}_bn{k} value = 0 }}\n"
        for k in range(1, len(shared) + 1))
    # Здания, про которые фильтру нужно знать «могу ли я это сейчас»: всё, чем
    # план строит, и каждая ступень над ними -- план «на конец» ставит верхнюю,
    # а показать надо ту, что по зубам.
    # **Ступень та же, что показывает фишка фильтра.** Иначе кнопка ставила бы
    # галочку не на том домике, который он там видит.
    #
    # **И только то, что тут правда может стоять**: `can_build_building` в самой
    # локации, а `_stands_<здание>` -- нет, он нарочно слушается тумблера ранга.
    # Уже стоящее здание тоже годится: галочка автостроя у него своя и значит
    # «расширяй дальше».
    def cm_ok(building: str) -> str:
        return (f"global_var:{MOD_ID}_ba_{building} = 1\n"
                f"\t\t\t\tOR = {{\n"
                f"\t\t\t\t\thas_building = building_type:{building}\n"
                f"\t\t\t\t\tcan_build_building = building_type:{building}\n"
                f"\t\t\t\t}}\n")

    def cm_mark(building: str, tab: str) -> str:
        """Галочка автостроя CM для этого типа здесь -- поставить или снять."""
        reg = f"cm_auto_expand_registered_building_types"
        exc = f"cm_auto_expand_excluded_building_types"
        t = tab
        return (
            f"{t}change_global_variable = {{ name = {MOD_ID}_cm_did add = 1 }}\n"
            f"{t}if = {{\n"
            f"{t}\tlimit = {{ owner = {{ is_target_in_variable_list = "
            f"{{ name = cm_mass_auto_expand_building_types "
            f"target = building_type:{building} }} }} }}\n"
            f"{t}\t# Массовый режим страны: «выключено» -- это исключение локации.\n"
            f"{t}\tif = {{\n"
            f"{t}\t\tlimit = {{ global_var:{MOD_ID}_cm_off = 1 }}\n"
            f"{t}\t\tif = {{\n"
            f"{t}\t\t\tlimit = {{ NOT = {{ is_target_in_variable_list = "
            f"{{ name = {exc} target = building_type:{building} }} }} }}\n"
            f"{t}\t\t\tadd_to_variable_list = {{ name = {exc} "
            f"target = building_type:{building} }}\n"
            f"{t}\t\t}}\n"
            f"{t}\t}}\n"
            f"{t}\telse = {{ remove_list_variable = {{ name = {exc} "
            f"target = building_type:{building} }} }}\n"
            f"{t}}}\n"
            f"{t}else = {{\n"
            f"{t}\tif = {{\n"
            f"{t}\t\tlimit = {{ global_var:{MOD_ID}_cm_off = 1 }}\n"
            f"{t}\t\tremove_list_variable = {{ name = {reg} "
            f"target = building_type:{building} }}\n"
            f"{t}\t}}\n"
            f"{t}\telse = {{\n"
            f"{t}\t\tif = {{\n"
            f"{t}\t\t\tlimit = {{ NOT = {{ is_target_in_variable_list = "
            f"{{ name = {reg} target = building_type:{building} }} }} }}\n"
            f"{t}\t\t\tadd_to_variable_list = {{ name = {reg} "
            f"target = building_type:{building} }}\n"
            f"{t}\t\t}}\n"
            f"{t}\t}}\n"
            f"{t}}}\n")

    def cm_seen(building: str, tab: str) -> str:
        """Та же галочка, прочитанная: стоит она сейчас или нет."""
        t = tab
        return (
            f"{t}change_global_variable = {{ name = {MOD_ID}_cm_all add = 1 }}\n"
            f"{t}if = {{\n"
            f"{t}\tlimit = {{\n"
            f"{t}\t\tOR = {{\n"
            f"{t}\t\t\tis_target_in_variable_list = "
            f"{{ name = cm_auto_expand_registered_building_types "
            f"target = building_type:{building} }}\n"
            f"{t}\t\t\tAND = {{\n"
            f"{t}\t\t\t\towner = {{ is_target_in_variable_list = "
            f"{{ name = cm_mass_auto_expand_building_types "
            f"target = building_type:{building} }} }}\n"
            f"{t}\t\t\t\tNOT = {{ is_target_in_variable_list = "
            f"{{ name = cm_auto_expand_excluded_building_types "
            f"target = building_type:{building} }} }}\n"
            f"{t}\t\t\t}}\n"
            f"{t}\t\t}}\n"
            f"{t}\t}}\n"
            f"{t}\tchange_global_variable = {{ name = {MOD_ID}_cm_on add = 1 }}\n"
            f"{t}}}\n")

    def cm_walk(body) -> str:
        """По каждому зданию плана -- та ступень, что по зубам, и с ней `body`."""
        out_ = ""
        for b in sorted({b for key in groups for b in groups[key]}):
            rungs = [b] + ladder_below(b, game)
            arms = "".join(
                f"\t\t{'if' if i == 0 else 'else_if'} = {{\n"
                f"\t\t\tlimit = {{\n\t\t\t\t{cm_ok(r)}\t\t\t}}\n"
                f"{body(r, chr(9) * 3)}"
                f"\t\t}}\n" for i, r in enumerate(rungs))
            out_ += (f"\tif = {{\n"
                     f"\t\tlimit = {{ is_target_in_variable_list = "
                     f"{{ name = {MOD_ID}_plan_builds target = building_type:{b} }} }}\n"
                     + arms + f"\t}}\n")
        return out_

    def cm_light(building: str, tab: str) -> str:
        """То же чтение, но в переменные локации -- для того, горит ли иконка."""
        t = tab
        return (
            f"{t}change_variable = {{ name = {MOD_ID}_cm_lfound add = 1 }}\n"
            f"{t}change_variable = {{ name = {MOD_ID}_cm_lall add = 1 }}\n"
            f"{t}if = {{\n"
            f"{t}\tlimit = {{\n"
            f"{t}\t\tOR = {{\n"
            f"{t}\t\t\tis_target_in_variable_list = "
            f"{{ name = cm_auto_expand_registered_building_types "
            f"target = building_type:{building} }}\n"
            f"{t}\t\t\tAND = {{\n"
            f"{t}\t\t\t\towner = {{ is_target_in_variable_list = "
            f"{{ name = cm_mass_auto_expand_building_types "
            f"target = building_type:{building} }} }}\n"
            f"{t}\t\t\t\tNOT = {{ is_target_in_variable_list = "
            f"{{ name = cm_auto_expand_excluded_building_types "
            f"target = building_type:{building} }} }}\n"
            f"{t}\t\t\t}}\n"
            f"{t}\t\t}}\n"
            f"{t}\t}}\n"
            f"{t}\tchange_variable = {{ name = {MOD_ID}_cm_lall subtract = 1 }}\n"
            f"{t}}}\n")

    # **Что план тут держит**, тем же правилом, что у фишки и у отмашки: само
    # здание или высшая доступная ступень того, что стоит в плане.
    def keeps(b: str, tab: str) -> str:
        arms = (f"{tab}\tis_target_in_variable_list = {{ name = {MOD_ID}_plan_builds "
                f"target = building_type:{b} }}\n")
        blocked: list[str] = []
        for upper in ladder_above(b, game):
            arms += (f"{tab}\tAND = {{\n"
                     f"{tab}\t\tis_target_in_variable_list = {{ name = {MOD_ID}_plan_builds "
                     f"target = building_type:{upper} }}\n"
                     + "".join(f"{tab}\t\tNOT = {{ global_var:{MOD_ID}_ba_{a} = 1 }}\n"
                               for a in blocked + [upper])
                     + f"{tab}\t}}\n")
            blocked.append(upper)
        return f"{tab}OR = {{\n{arms}{tab}}}\n"

    raze = "".join(
        f"\tif = {{\n"
        f"\t\tlimit = {{\n"
        f"\t\t\thas_building = building_type:{b}\n"
        f"\t\t\tNOT = {{\n{keeps(b, chr(9) * 4)}\t\t\t}}\n"
        f"\t\t}}\n"
        f"\t\tdestroy_all_buildings_of_type = building_type:{b}\n"
        f"\t\tchange_global_variable = {{ name = {MOD_ID}_raze_n add = 1 }}\n"
        f"\t\tset_variable = {{ name = {MOD_ID}_chg_seq value = global_var:{MOD_ID}_edit_presses }}\n"
        f"\t}}\n" for b in sorted({b for key in groups for b in groups[key]}))
    food_or = "".join(f"\t\traw_material = goods:{g}\n" for g in FOOD_GOODS)

    # **Ванильный костыль: что тут надо построить, чтобы было что отмечать.**
    # Ступень берётся та же, что у галочки CM и у фишки фильтра (`cm_walk`) --
    # иначе кнопка строила бы не тот домик, который он видит в строке. А внутри
    # неё вопрос уже другой: здания тут нет, страна и локация его пускают, и мод
    # его сюда ещё не заказывал.
    def b1_mark(building: str, tab: str) -> str:
        t = tab
        return (
            f"{t}if = {{\n"
            f"{t}\tlimit = {{\n"
            f"{t}\t\tNOT = {{ has_building = building_type:{building} }}\n"
            f"{t}\t\tcan_build_building = building_type:{building}\n"
            f"{t}\t\tNOT = {{ is_target_in_variable_list = {{ name = {MOD_ID}_b1_fired "
            f"target = building_type:{building} }} }}\n"
            f"{t}\t\tNOT = {{ is_target_in_variable_list = {{ name = {MOD_ID}_b1_todo "
            f"target = building_type:{building} }} }}\n"
            f"{t}\t}}\n"
            f"{t}\tadd_to_variable_list = {{ name = {MOD_ID}_b1_todo "
            f"target = building_type:{building} }}\n"
            f"{t}\tchange_variable = {{ name = {MOD_ID}_b1_n add = 1 }}\n"
            f"{t}}}\n")

    cm_apply = cm_walk(cm_mark)
    cm_scan = cm_walk(cm_seen)
    cm_lit = cm_walk(cm_light)
    b1_scan = cm_walk(b1_mark)
    # **Память о заказанном забывается, когда здание встало.** Пока стройка
    # идёт, `has_building` может ещё отвечать «нет», и без памяти второе нажатие
    # заказало бы второй уровень -- то самое расширение, которое он запретил.
    b1_forget = "".join(
        f"\tif = {{\n"
        f"\t\tlimit = {{ has_building = building_type:{b} }}\n"
        f"\t\tremove_list_variable = {{ name = {MOD_ID}_b1_fired "
        f"target = building_type:{b} }}\n"
        f"\t}}\n" for b in ladder_set(groups, game))

    bavail = "".join(
        f"\tset_global_variable = {{ name = {MOD_ID}_ba_{b} value = 0 }}\n"
        f"\tif = {{\n"
        f"\t\tlimit = {{ can_build_building = building_type:{b} }}\n"
        f"\t\tset_global_variable = {{ name = {MOD_ID}_ba_{b} value = 1 }}\n"
        f"\t}}\n" for b in ladder_set(groups, game))

    out = [HEADER, f"""#
# Scope: country
{MOD_ID}_plan_run = {{
\tsave_scope_as = {MOD_ID}_country
\t# **Nothing is re-read from CMM here any more.** The caps, the rights tick and
\t# «на конец» were settings on the mod page and had to be copied into globals
\t# at the top of every run; they are controls in the plan\'s own window now and
\t# write their globals themselves.
\t{MOD_ID}_collect_candidates = yes
\t{MOD_ID}_rebuild_browse = yes
\t{MOD_ID}_plan_prepare = yes
\t{MOD_ID}_plan_score = yes
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_plan_rights }}
\t\t{MOD_ID}_plan_place_rights = yes
\t}}
\t{MOD_ID}_plan_set_quota = yes
\t{MOD_ID}_plan_place_scarce = yes
\t{MOD_ID}_plan_allocate = yes
\t# **И житницы, последними.** Их комнаты в раздаче не участвуют вовсе, и
\t# домики, которые сюда встанут, ни с кем за места не спорили: круг ходит
\t# только по помеченным локациям и ставит то, что растит еду или сам РГО.
\t{MOD_ID}_plan_fill_granaries = yes
\t{MOD_ID}_plan_rank = yes
\t# **A fresh plan is its own baseline.** «Показать изменения» right after one is
\t# empty, which is the true answer: nothing has been edited yet, and everything
\t# after this is measured against what the formula produced.
\t{MOD_ID}_edit_save = yes
\t# **Свежий план -- свежий счёт костыля.** Что тут не построено и во что это
\t# обойдётся, спрашивается заново: без CM подсказка кнопки стройки читает
\t# именно эти числа.
\t{MOD_ID}_b1_scan = yes
\tcmf_log = {{ action = {MOD_ID}_log_plan }}
}}

# **Какие здания эта страна может строить сейчас** -- по одному числу на здание.
#
# Владелец, 2026-09-09: «я обычно использую метод плана „на конец"... если в
# плане стоит домик, который не доступен мне по уровню -- мне не показывается. Но
# я хочу, чтобы мне показывался его аналог более низкого уровня». Ступени лестницы
# игра называет сама (`obsolete` в `building_types`), а «доступна ли ступень»
# спрашивается `can_build_building` **в скоупе страны** -- именно она отвечает за
# продвижения, как и у `_avail_<n>`.
#
# **Почему числом в глобалке, а не вопросом на месте.** Фильтру списка достаётся
# только сам объект и глобальные переменные; страны у него нет вовсе. Значит
# ответ надо посчитать заранее там, где страна есть, -- здесь.
#
# Считается при каждой «Пересчитать» и при регистрации мода (то есть на загрузке
# сохранения и при открытии страницы мода). Взял продвижение и не пересчитал план
# -- фильтр покажет ступень ниже, чем мог бы; это единственная цена.
# Scope: country
{MOD_ID}_set_bavail = {{
{bavail}}}

# Переключить режим житницы для этой локации.
#
# **Переменная CM пишется по-прежнему, и это не рудимент.** Мод её и читает
# (`_is_granary`), и CM, если он у кого-то стоит, увидит ту же пометку; имя,
# которого нет, ломается не там, где его ищут, а переменную можно писать в
# пустоту. Модификатор `cm_auto_food_locked_location` намеренно не ставится.
#
# **В окне плана нажатие только помечает, в редакторе -- меняет сразу.** Его
# слово 2026-09-13: «если я жму её в окне "общего плана", то чтобы получить
# изменения -- нужно нажать пересчитать… если я нажму на эту кнопку в режиме
# редактора -- изменения должны произойти сразу же, т.е. исчезнуть из локации
# домики плана и встать домики житницы». Кнопка одна на оба окна -- ряд плана
# общий, -- поэтому решает то, открыт ли редактор.
# Scope: country, ждёт scope:wtp_location
{MOD_ID}_food_press_loc_do = {{
\tsave_scope_as = {MOD_ID}_country
\tscope:wtp_location = {{
\t\tif = {{
\t\t\tlimit = {{ has_variable = cm_auto_food_location_enabled }}
\t\t\tremove_variable = cm_auto_food_location_enabled
\t\t}}
\t\telse = {{ set_variable = {{ name = cm_auto_food_location_enabled value = yes }} }}
\t}}
\tif = {{
\t\tlimit = {{ has_variable = {MOD_ID}_edit_open }}
\t\tscope:wtp_location = {{
\t\t\tif = {{
\t\t\t\tlimit = {{ {MOD_ID}_is_granary = yes }}
\t\t\t\t# Стала житницей: всё плановое с локации долой, житничное на неё.
\t\t\t\t{MOD_ID}_edit_wipe_here = yes
{gran_put(chr(9) * 3)}\t\t\t}}
\t\t\telse = {{ {MOD_ID}_clear_granary_here = yes }}
\t\t}}
\t\t# Строка локации перерисовывается из `_plan_builds`, поэтому её надо
\t\t# собрать заново -- и по всей земле, потому что пара строк общая.
\t\t{MOD_ID}_plan_rows = yes
\t}}
}}

# **Снос всего производственного, чего план тут не хочет.**
#
# Его слово, 2026-09-09: «в локации 2 здания подходят и стоит там ещё штук 10
# производственных зданий, которые не подходят. При нажатии той кнопки все эти 10
# снесёт, а остальные 2 останутся. Только смотри, чтобы эта кнопка не сносила
# какие-либо другие здания.»
#
# **Трогается ровно тот список, которым план строит** -- здания
# производственных котлов и деревни, выписанные на сборке. Гарнизон, порт,
# университет и всё прочее в этот список не входят вовсе, поэтому «случайно
# снесла не то» тут невозможно по построению, а не по проверке.
#
# **Ступень лестницы считается подходящей.** План «на конец» ставит мельницу, а
# стоит мастерская: сносить её -- значит сносить то, что фильтр и автострой
# только что назвали правильным. Правило то же самое: здание остаётся, если оно
# в плане или это высшая доступная ступень того, что в плане.
# Scope: location
{MOD_ID}_raze_loc = {{
{raze}}}

# Scope: country, ждёт scope:wtp_location
{MOD_ID}_raze_press_loc_do = {{
\tset_global_variable = {{ name = {MOD_ID}_raze_n value = 0 }}
\t{MOD_ID}_set_bavail = yes
\tscope:wtp_location = {{ {MOD_ID}_raze_loc = yes }}
}}

# Scope: country, ждёт scope:wtp_location -- любую локацию нужной провинции
{MOD_ID}_raze_press_prov_do = {{
\tset_global_variable = {{ name = {MOD_ID}_raze_n value = 0 }}
\t{MOD_ID}_set_bavail = yes
\tscope:wtp_location = {{ province_definition = {{ save_scope_as = {MOD_ID}_cm_prov }} }}
\tevery_in_global_list = {{
\t\tvariable = {MOD_ID}_plan_touched
\t\tlimit = {{ province_definition = {{ this = scope:{MOD_ID}_cm_prov }} }}
\t\t{MOD_ID}_raze_loc = yes
\t}}
}}

# Scope: country
{MOD_ID}_raze_press_all_do = {{
\tset_global_variable = {{ name = {MOD_ID}_raze_n value = 0 }}
\t{MOD_ID}_set_bavail = yes
\tevery_in_global_list = {{
\t\tvariable = {MOD_ID}_plan_touched
\t\t{MOD_ID}_raze_loc = yes
\t}}
}}

# **Одна отмашка на галочки автостроя Construction Manager, и больше ничего.**
#
# Владелец, 2026-09-09, после первой версии: «я не хочу, чтобы мод делал
# что-либо каждый месяц… Всё, что это делает — включает 4 кнопки у каждого из
# этих зданий в их локации. 1 раз она это делает. Просто включает их галочки 1
# раз… А дальше уже CM сам решает когда строить, что строить. Только ссылка на
# другие ссылки.» Месячный лист и очередь `cm_q_ungated_*` из первой версии
# убраны целиком.
#
# **Галочка -- это две переменные CM на локации**, и обе пишутся напрямую, без
# единого его имени: имя, которого нет, ломается не там, где его ищут, а
# переменную можно писать в пустоту. Форма списана с `cm_apply_auto_expand_toggle`
# (CM 2.2.12): в обычном режиме тип лежит в `cm_auto_expand_registered_building_types`
# локации; если страна включила его массово (`cm_mass_auto_expand_building_types`),
# логика переворачивается и «выключено» значит «тип в
# `cm_auto_expand_excluded_building_types` этой локации».
#
# `_cm_off` -- направление отмашки: 1 снять, 0 поставить.
# Scope: location
{MOD_ID}_cm_apply = {{
{cm_apply}}}

# **Сколько галочек группы уже стоит.** Кнопка одна, а нажатий два смысла: не всё
# включено -- включить всё, включено всё -- снять. Считается на нажатие, а не на
# кадр: строк в окне сорок, и ответ на кадр стоил бы того же, что и панель,
# которую этот репозиторий до сих пор чинит.
# Scope: location
{MOD_ID}_cm_scan = {{
{cm_scan}}}

# **Горит ли иконка -- переменная, а не вопрос на каждом кадре.**
#
# Владелец, 2026-09-09: «иконки всегда горят так, как выглядит положение "вкл"…
# Она должна загораться и потухать». Ответ считается на нажатии и на открытии
# окна и лежит на локации: `visible` умеет читать переменную и не умеет звать
# триггер, а сорок строк, каждая со своим обходом плана на кадр, -- это ровно та
# цена, которую этот репозиторий до сих пор ищет в `panel_hitch.md`.
#
# **Считается вычитанием, а не сравнением двух переменных.** `var:x = var:y` тут
# нигде не доказан: `_cm_lall` растёт на каждую найденную галочку и убывает на
# каждую стоящую, так что «горит» -- это `_cm_lfound > 0` и `_cm_lall = 0`,
# оба против чисел.
# Scope: location
{MOD_ID}_cm_light_loc = {{
\tset_variable = {{ name = {MOD_ID}_cm_lfound value = 0 }}
\tset_variable = {{ name = {MOD_ID}_cm_lall value = 0 }}
{cm_lit}\tremove_variable = {MOD_ID}_cm_lit
\tif = {{
\t\tlimit = {{
\t\t\tvar:{MOD_ID}_cm_lfound > 0
\t\t\tNOT = {{ var:{MOD_ID}_cm_lall > 0 }}
\t\t}}
\t\tset_variable = {{ name = {MOD_ID}_cm_lit value = 1 }}
\t}}
}}

# Тот же ответ для ряда провинции и для шапки. Провинция горит, когда горят все
# её локации плана; шапка -- когда горит весь план. Провинция читается со своей
# представительной локации, той же, на которой стоит её ряд.
# Scope: country
{MOD_ID}_cm_light = {{
\t{MOD_ID}_set_bavail = yes
\tevery_in_global_list = {{
\t\tvariable = {MOD_ID}_plan_touched
\t\t{MOD_ID}_cm_light_loc = yes
\t}}
\tevery_in_global_list = {{
\t\tvariable = {MOD_ID}_plan_provs
\t\tprovince_definition = {{ save_scope_as = {MOD_ID}_cm_prov }}
\t\tremove_variable = {MOD_ID}_cm_lit_prov
\t\tif = {{
\t\t\tlimit = {{
\t\t\t\tany_in_global_list = {{
\t\t\t\t\tvariable = {MOD_ID}_plan_touched
\t\t\t\t\tprovince_definition = {{ this = scope:{MOD_ID}_cm_prov }}
\t\t\t\t\tvar:{MOD_ID}_cm_lit = 1
\t\t\t\t}}
\t\t\t\tNOT = {{
\t\t\t\t\tany_in_global_list = {{
\t\t\t\t\t\tvariable = {MOD_ID}_plan_touched
\t\t\t\t\t\tprovince_definition = {{ this = scope:{MOD_ID}_cm_prov }}
\t\t\t\t\t\tvar:{MOD_ID}_cm_lfound > 0
\t\t\t\t\t\tNOT = {{ var:{MOD_ID}_cm_lit = 1 }}
\t\t\t\t\t}}
\t\t\t\t}}
\t\t\t}}
\t\t\tset_variable = {{ name = {MOD_ID}_cm_lit_prov value = 1 }}
\t\t}}
\t}}
\tremove_global_variable = {MOD_ID}_cm_lit_all
\tif = {{
\t\tlimit = {{
\t\t\tany_in_global_list = {{
\t\t\t\tvariable = {MOD_ID}_plan_touched
\t\t\t\tvar:{MOD_ID}_cm_lit = 1
\t\t\t}}
\t\t\tNOT = {{
\t\t\t\tany_in_global_list = {{
\t\t\t\t\tvariable = {MOD_ID}_plan_touched
\t\t\t\t\tvar:{MOD_ID}_cm_lfound > 0
\t\t\t\t\tNOT = {{ var:{MOD_ID}_cm_lit = 1 }}
\t\t\t\t}}
\t\t\t}}
\t\t}}
\t\tset_global_variable = {{ name = {MOD_ID}_cm_lit_all value = 1 }}
\t}}
}}

# Пройти помеченную группу дважды: сначала посчитать, потом решить и применить.
# Scope: country, ждёт заполненный global list scope
{MOD_ID}_cm_press_prov_do = {{
\tscope:wtp_location = {{ province_definition = {{ save_scope_as = {MOD_ID}_cm_prov }} }}
\t{MOD_ID}_cm_zero = yes
\tevery_in_global_list = {{
\t\tvariable = {MOD_ID}_plan_touched
\t\tlimit = {{ province_definition = {{ this = scope:{MOD_ID}_cm_prov }} }}
\t\t{MOD_ID}_cm_scan = yes
\t}}
\t{MOD_ID}_cm_decide = yes
\tevery_in_global_list = {{
\t\tvariable = {MOD_ID}_plan_touched
\t\tlimit = {{ province_definition = {{ this = scope:{MOD_ID}_cm_prov }} }}
\t\t{MOD_ID}_cm_apply = yes
\t}}
\t{MOD_ID}_cm_light = yes
}}

# Scope: country
{MOD_ID}_cm_press_loc_do = {{
\t{MOD_ID}_cm_zero = yes
\tscope:wtp_location = {{ {MOD_ID}_cm_scan = yes }}
\t{MOD_ID}_cm_decide = yes
\tscope:wtp_location = {{ {MOD_ID}_cm_apply = yes }}
\t{MOD_ID}_cm_light = yes
}}

# Scope: country
{MOD_ID}_cm_press_all_do = {{
\t{MOD_ID}_cm_zero = yes
\tevery_in_global_list = {{
\t\tvariable = {MOD_ID}_plan_touched
\t\t{MOD_ID}_cm_scan = yes
\t}}
\t{MOD_ID}_cm_decide = yes
\tevery_in_global_list = {{
\t\tvariable = {MOD_ID}_plan_touched
\t\t{MOD_ID}_cm_apply = yes
\t}}
\t{MOD_ID}_cm_light = yes
}}

# Scope: country
{MOD_ID}_cm_zero = {{
\tset_global_variable = {{ name = {MOD_ID}_cm_all value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_cm_on value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_cm_did value = 0 }}
\t# Что стране по зубам -- на сегодня: ступень берётся та же, что показывает
\t# фишка «Из плана — сюда», иначе кнопка и список говорили бы разное.
\t{MOD_ID}_set_bavail = yes
}}

# Всё уже включено -- значит нажатие снимает. Иначе включает.
# Scope: country
{MOD_ID}_cm_decide = {{
\tset_global_variable = {{ name = {MOD_ID}_cm_off value = 0 }}
\tif = {{
\t\tlimit = {{
\t\t\tglobal_var:{MOD_ID}_cm_all > 0
\t\t\tNOT = {{ global_var:{MOD_ID}_cm_all > global_var:{MOD_ID}_cm_on }}
\t\t}}
\t\tset_global_variable = {{ name = {MOD_ID}_cm_off value = 1 }}
\t}}
}}

# ---- ванильный костыль: первый ярус и галочка движка ----------------------
#
# **CM снят, и с ним ушла единственная переменная, в которую галочку автостроя
# можно было написать скриптом.** Ванильная лежит полем на записи `Building`,
# ставит её только интерфейс (`ToggleAutoExpandBuilding`), а у непостроенного
# здания записи нет вовсе: «Авторасширение ванилы не может быть включено пока
# не начата стройка хотя бы первого уровня здания» -- его слова, 2026-09-14.
# Отсюда вторая кнопка рядом с первой, и обе -- виджеты, а не эффекты.
#
# **Скрипт здесь только считает, кому что положено.** Он пишет два списка:
# глобальный `_b1_locs` -- локации, где плану чего-то не хватает, и на каждой из
# них `_b1_todo` -- типы, которых там нет. Стройку и галочку заказывает по этим
# спискам скрытый привод окна плана.
#
# **Почему стройку заказывает интерфейс, а не `construct_building`.** Эффект
# скрипта **не берёт с игрока особые валюты цены** -- это написано у самого CM
# (`cm_feature_effects.txt:194`), и поэтому он тоже строит кнопкой движка.
# Строит `BuildOrExpandBuildingDefault`, ровно то же, что нажатие игрока.
#
# **`_b1_todo` -- это ровно «первый ярус и ничего больше».** Тип попадает в
# список только когда `has_building` про него говорит «нет»; стоящее здание в
# список не попадает, и кнопке движка нечего расширять.
# Scope: location
{MOD_ID}_b1_scan_loc = {{
\tclear_variable_list = {MOD_ID}_b1_todo
\tset_variable = {{ name = {MOD_ID}_b1_n value = 0 }}
\tset_variable = {{ name = {MOD_ID}_b1_cost value = 0 }}
{b1_forget}{b1_scan}}}

# **Обход считается один раз на открытие окна и после каждой стройки**, а не на
# кадр: это та самая цена, из-за которой CM снят.
#
# **При включённом CM не считается вовсе.** Ветка ванилы нужна только тогда,
# когда CM в игре нет.
# Scope: country
{MOD_ID}_b1_scan = {{
\t# **Очередь стройки не переживает ни загрузку, ни закрытие окна.** Она
\t# заполняется нажатием и опустошается приводом; всё, что осталось от прошлого
\t# раза, -- это стройка, за которую никто не собирался платить сейчас.
\tremove_global_variable = {MOD_ID}_b1_fire
\tclear_global_variable_list = {MOD_ID}_b1_fire_locs
\tif = {{
\t\tlimit = {{ NOT = {{ has_variable_list = cm_priority_features_list }} }}
\t\t{MOD_ID}_set_bavail = yes
\t\tclear_global_variable_list = {MOD_ID}_b1_locs
\t\tset_global_variable = {{ name = {MOD_ID}_b1_pairs value = 0 }}
\t\tset_global_variable = {{ name = {MOD_ID}_b1_cost_all value = 0 }}
\t\tset_global_variable = {{ name = {MOD_ID}_b1_cadd value = 0 }}
\t\tevery_in_global_list = {{
\t\t\tvariable = {MOD_ID}_plan_touched
\t\t\t{MOD_ID}_b1_scan_loc = yes
\t\t\tif = {{
\t\t\t\tlimit = {{ has_variable = {MOD_ID}_b1_n var:{MOD_ID}_b1_n > 0 }}
\t\t\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_b1_locs target = this }}
\t\t\t\tchange_global_variable = {{ name = {MOD_ID}_b1_pairs add = var:{MOD_ID}_b1_n }}
\t\t\t}}
\t\t}}
\t\tset_global_variable = {{ name = {MOD_ID}_b1_cost_go value = 1 }}
\t}}
}}

# **Цену называет движок, а не формула.** `GetBuildOrExpandBuildingCost` -- то
# самое число, которое он видит в панели стройки; скрипт его только
# складывает. Его выбор, 2026-09-14: «Точное число движка».
# Scope: location, ждёт scope:wtp_cost
{MOD_ID}_b1_cost_add_do = {{
\tchange_variable = {{ name = {MOD_ID}_b1_cost add = scope:wtp_cost }}
\tchange_global_variable = {{ name = {MOD_ID}_b1_cost_all add = scope:wtp_cost }}
\tchange_global_variable = {{ name = {MOD_ID}_b1_cadd add = 1 }}
}}

# Сумма провинции -- сумма её локаций, и лежит она на той же представительной
# локации, на которой стоит её ряд.
# Scope: country
{MOD_ID}_b1_cost_done_do = {{
\tremove_global_variable = {MOD_ID}_b1_cost_go
\tevery_in_global_list = {{
\t\tvariable = {MOD_ID}_plan_provs
\t\tprovince_definition = {{ save_scope_as = {MOD_ID}_b1_prov }}
\t\tset_global_variable = {{ name = {MOD_ID}_b1_tmp value = 0 }}
\t\tevery_in_global_list = {{
\t\t\tvariable = {MOD_ID}_plan_touched
\t\t\tlimit = {{
\t\t\t\tprovince_definition = {{ this = scope:{MOD_ID}_b1_prov }}
\t\t\t\thas_variable = {MOD_ID}_b1_cost
\t\t\t}}
\t\t\tchange_global_variable = {{ name = {MOD_ID}_b1_tmp add = var:{MOD_ID}_b1_cost }}
\t\t}}
\t\tset_variable = {{ name = {MOD_ID}_b1_cost_prov value = global_var:{MOD_ID}_b1_tmp }}
\t}}
}}

# Нажатие: чем платить, решает движок, а тут только собирается земля.
# Scope: country, ждёт scope:wtp_location
{MOD_ID}_b1_press_loc_do = {{
\tclear_global_variable_list = {MOD_ID}_b1_fire_locs
\tscope:wtp_location = {{
\t\tif = {{
\t\t\tlimit = {{ has_variable = {MOD_ID}_b1_n var:{MOD_ID}_b1_n > 0 }}
\t\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_b1_fire_locs target = this }}
\t\t}}
\t}}
\t{MOD_ID}_b1_arm = yes
}}

# Scope: country, ждёт scope:wtp_location -- любую локацию нужной провинции
{MOD_ID}_b1_press_prov_do = {{
\tscope:wtp_location = {{ province_definition = {{ save_scope_as = {MOD_ID}_b1_prov }} }}
\tclear_global_variable_list = {MOD_ID}_b1_fire_locs
\tevery_in_global_list = {{
\t\tvariable = {MOD_ID}_b1_locs
\t\tlimit = {{ province_definition = {{ this = scope:{MOD_ID}_b1_prov }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_b1_fire_locs target = this }}
\t}}
\t{MOD_ID}_b1_arm = yes
}}

# Scope: country
{MOD_ID}_b1_press_all_do = {{
\tclear_global_variable_list = {MOD_ID}_b1_fire_locs
\tevery_in_global_list = {{
\t\tvariable = {MOD_ID}_b1_locs
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_b1_fire_locs target = this }}
\t}}
\t{MOD_ID}_b1_arm = yes
}}

# Scope: country
{MOD_ID}_b1_arm = {{
\tset_global_variable = {{ name = {MOD_ID}_b1_fire_n value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_b1_fire value = 1 }}
}}

# Одна заказанная стройка: запомнить тип, чтобы второе нажатие не заказало
# второй уровень.
# Scope: location, ждёт scope:wtp_building
{MOD_ID}_b1_fire_one_do = {{
\tif = {{
\t\tlimit = {{
\t\t\tNOT = {{ is_target_in_variable_list = {{ name = {MOD_ID}_b1_fired
\t\t\t\ttarget = scope:wtp_building }} }}
\t\t}}
\t\tadd_to_variable_list = {{ name = {MOD_ID}_b1_fired target = scope:wtp_building }}
\t}}
\tchange_global_variable = {{ name = {MOD_ID}_b1_fire_n add = 1 }}
}}

# **Стройка кончилась -- начинается галочка.** Заказанное на этой земле уже
# имеет запись `Building`, и именно с этого мига её флаг доступен интерфейсу.
# Scope: country
{MOD_ID}_b1_fire_done_do = {{
\tremove_global_variable = {MOD_ID}_b1_fire
\tclear_global_variable_list = {MOD_ID}_ax_locs
\tevery_in_global_list = {{
\t\tvariable = {MOD_ID}_b1_fire_locs
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_ax_locs target = this }}
\t}}
\tclear_global_variable_list = {MOD_ID}_b1_fire_locs
\t{MOD_ID}_ax_arm = yes
\t{MOD_ID}_b1_scan = yes
}}

# **Отмашка ванильного автостроя -- в одну сторону.** Прочитать чужую галочку
# скрипт не может, а подсветка, которая врёт, хуже, чем её отсутствие: кнопка
# включает, а снимается галочка там же, где ставилась руками -- в панели
# локации. `_ax_locs` -- земля нажатия, и привод гасит её сам.
# Scope: country, ждёт scope:wtp_location
{MOD_ID}_ax_press_loc_do = {{
\tclear_global_variable_list = {MOD_ID}_ax_locs
\tscope:wtp_location = {{
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_ax_locs target = this }}
\t}}
\t{MOD_ID}_ax_arm = yes
}}

# Scope: country, ждёт scope:wtp_location -- любую локацию нужной провинции
{MOD_ID}_ax_press_prov_do = {{
\tscope:wtp_location = {{ province_definition = {{ save_scope_as = {MOD_ID}_ax_prov }} }}
\tclear_global_variable_list = {MOD_ID}_ax_locs
\tevery_in_global_list = {{
\t\tvariable = {MOD_ID}_plan_touched
\t\tlimit = {{ province_definition = {{ this = scope:{MOD_ID}_ax_prov }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_ax_locs target = this }}
\t}}
\t{MOD_ID}_ax_arm = yes
}}

# Scope: country
{MOD_ID}_ax_press_all_do = {{
\tclear_global_variable_list = {MOD_ID}_ax_locs
\tevery_in_global_list = {{
\t\tvariable = {MOD_ID}_plan_touched
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_ax_locs target = this }}
\t}}
\t{MOD_ID}_ax_arm = yes
}}

# Scope: country
{MOD_ID}_ax_arm = {{
\tset_global_variable = {{ name = {MOD_ID}_ax_n value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_ax_go value = 1 }}
}}

# **Список гаснет сразу после прохода.** Оставшись висеть, он отметил бы и ту
# стройку, которую игрок начал руками через минуту после нажатия.
# Scope: country
{MOD_ID}_ax_done_do = {{
\tremove_global_variable = {MOD_ID}_ax_go
\tclear_global_variable_list = {MOD_ID}_ax_locs
}}

# Scope: location
{MOD_ID}_ax_seen_do = {{
\tchange_global_variable = {{ name = {MOD_ID}_ax_n add = 1 }}
}}

# The ground this run works over, and everything the last one left on the map.
#
# `_plan_touched` is the previous run's locations, which a new choice on the map
# may no longer contain -- a location dropped out of the candidates would else
# keep its buildings, in the map mode as much as in the window.
#
# **`{MOD_ID}_force_town` and `_force_rural` are not among the things removed**:
# they are the player's answer to «what is this location», not the plan's.
# Scope: country
{MOD_ID}_plan_prepare = {{
\t{MOD_ID}_set_bavail = yes
\tevery_in_global_list = {{
\t\tvariable = {MOD_ID}_plan_touched
\t\tremove_variable = {MOD_ID}_load
\t\tremove_variable = {MOD_ID}_plan_rank
\t\tremove_variable = {MOD_ID}_plan_pg
\t\tremove_variable = {MOD_ID}_plan_prank
\t\tremove_variable = {MOD_ID}_plan_right
\t\tremove_variable = {MOD_ID}_plan_town_row
\t\tremove_variable = {MOD_ID}_plan_prov_load
\t\tremove_variable = {MOD_ID}_plan_prov_locn
\t\tremove_variable = {MOD_ID}_plan_area_load
\t\tremove_variable = {MOD_ID}_plan_pexp
\t\tremove_variable = {MOD_ID}_plan_seen
\t\t# **Снимок загрузки, который «Расширить» кладёт перед доливкой.** Он
\t\t# существует ровно затем, чтобы после доливки посчитать, сколько
\t\t# домиков на старой земле сдвинулось (ответ обязан быть нулём).
\t\t# Оставленный от прошлой доливки, он сравнивал бы новую с чужой.
\t\tremove_variable = {MOD_ID}_ext_load0
\t\tremove_variable = {MOD_ID}_ext_dl
\t\tclear_variable_list = {MOD_ID}_plan_goods
\t\tclear_variable_list = {MOD_ID}_plan_builds
\t}}
\tclear_global_variable_list = {MOD_ID}_plan_touched
\t# **Режим доливки не переживает свежий план.** `_ext` заставляет обход
\t# наращивать `_ng`/`_nrgo`/`_pbest` вместо того, чтобы обнулять их; свежий
\t# план считает всё с нуля, и оставленный флаг сложил бы новый счёт со старым.
\tremove_global_variable = {MOD_ID}_ext
\tclear_global_variable_list = {MOD_ID}_ext_locs
\tset_global_variable = {{ name = {MOD_ID}_ext_new value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_ext_rooms value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_ext_added value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_ext_moved value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_ext_lifted value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_ext_was value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_ext_ran value = 0 }}
\tclear_global_variable_list = {MOD_ID}_plan_prov_locs
\tclear_global_variable_list = {MOD_ID}_plan_area_locs
\tclear_global_variable_list = {MOD_ID}_plan_ranked
\tclear_global_variable_list = {MOD_ID}_plan_provs
\tclear_global_variable_list = {MOD_ID}_plan_results
{bzero}\tset_global_variable = {{ name = {MOD_ID}_plan_placed value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_plan_pt value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_plan_pr value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_plan_fed value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_plan_gain value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_plan_scored value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_plan_found value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_plan_shown value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_plan_page value = 1 }}
\tset_global_variable = {{ name = {MOD_ID}_plan_pages value = 1 }}
\tset_global_variable = {{ name = {MOD_ID}_plan_pagec value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_plan_from value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_plan_to value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_plan_rooms value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_prooms_t value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_prooms_r value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_plan_towns value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_plan_provn value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_plan_rightn value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_plan_sweeps value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_plan_opensw value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_plan_band value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_plan_lvl value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_plan_laps value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_plan_dry value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_plan_top value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_plan_quota value = 1 }}
\t# **Пометка режима снимается здесь, а ставится в конце `_spec_run`.** Так
\t# любой обычный «Пересчитать» гасит её сам, и ни одно окно не может назвать
\t# специализацией то, что ею не является.
\tremove_global_variable = {MOD_ID}_spec_ran
\t# **И то же самое числом, для отчёта.** `.IsSet` в окне не отличает
\t# отсутствующую глобалку от нулевой, поэтому пометка режима -- флаг; а
\t# `debug_log` печатает только числа, поэтому рядом с ней живёт `_plan_mode`.
\tset_global_variable = {{ name = {MOD_ID}_plan_mode value = 0 }}
"""]
    for index, good in enumerate(order, start=1):
        # `_pw<n>` is the player's own weight on this good and is **not** zeroed
        # here: it is a setting, not a counter, and outlives every plan. It is
        # created if it is missing, because a `limit` reading a global that is
        # not there is the failure that logs nothing.
        # **`_lock<n>` is zeroed here and `_skip<n>` is not**, and the difference
        # is the whole of what the two mean. A lock says «I moved this good to
        # here», which a fresh plan has not been told and must not assume; the
        # «не нужен» flag says «never fill this good past its minimum, on any
        # ground», which is a standing instruction and survives replanning --
        # otherwise it would have to be re-clicked on every new land, which is
        # the clicking it exists to save. **`_skip<n>` is an existence flag and
        # not a number**, so «off» is the variable being absent and no `limit`
        # ever reads a global that might not be there: `has_global_variable` is
        # true or false, where `global_var:x = 0` on a missing name is silently
        # false and reads as «off» whichever way it was meant.
        out.append(f"\tset_global_variable = {{ name = {MOD_ID}_pn{index} value = 0 }}\n"
                   f"\tset_global_variable = {{ name = {MOD_ID}_pnt{index} value = 0 }}\n"
                   f"\tset_global_variable = {{ name = {MOD_ID}_pnr{index} value = 0 }}\n"
                   f"\tset_global_variable = {{ name = {MOD_ID}_pqt{index} value = 1 }}\n"
                   f"\tset_global_variable = {{ name = {MOD_ID}_pqr{index} value = 1 }}\n"
                   f"\tset_global_variable = {{ name = {MOD_ID}_pout{index} value = 0 }}\n"
                   f"\tset_global_variable = {{ name = {MOD_ID}_pq{index} value = 1 }}\n"
                   f"\tset_global_variable = {{ name = {MOD_ID}_pqraw{index} value = 0 }}\n"
                   f"\tset_global_variable = {{ name = {MOD_ID}_nrgo{index} value = 0 }}\n"
                   f"\tset_global_variable = {{ name = {MOD_ID}_pbest{index} value = 0 }}\n"
                   f"\tremove_global_variable = {MOD_ID}_lock{index}\n"
                   # **И заморозка на время доливки, которая не должна пережить
                   # ничего.** `_frz<n>` держит товар вне раздачи ровно на один
                   # проход `_plan_allocate`, запущенный «Расширить»;
                   # `{MOD_ID}_ext_thaw` снимает её сам, а это -- вторая
                   # страховка на случай, если проход прервали. Свежий план не
                   # читает состояние редактора вообще, и это единственное
                   # место, где такое правило можно нарушить молча.
                   f"\tremove_global_variable = {MOD_ID}_frz{index}\n"
                   f"\tset_global_variable = {{ name = {MOD_ID}_esh{index} value = 0 }}\n"
                   )
    # How many towns each right has been given. **The global is the dump's now
    # and no longer the score's** -- `_rq<k>` divides by `_rp<k>`, the count in
    # this province. A script value reading a global that is not there is the
    # silent failure, so it still has to be zeroed.
    for k in range(1, len(rights) + 1):
        out.append(f"\tset_global_variable = {{ name = {MOD_ID}_rgiven{k} value = 0 }}\n"
                   f"\tset_global_variable = {{ name = {MOD_ID}_rn{k} value = 0 }}\n")
    # The rights' band and quota, zeroed here for the same reason every other
    # counter is: a `limit` that reads a global which is not there fails silently.
    out.append(f"\tset_global_variable = {{ name = {MOD_ID}_rband value = 0 }}\n"
               f"\tset_global_variable = {{ name = {MOD_ID}_ropen value = 0 }}\n"
               f"\tset_global_variable = {{ name = {MOD_ID}_rlevel value = 0 }}\n"
               f"\tset_global_variable = {{ name = {MOD_ID}_rquota value = 1 }}\n"
               f"\tset_global_variable = {{ name = {MOD_ID}_rgrant value = 0 }}\n")
    # **What each lap of the draft placed, kept so the dump can print it.** One
    # write a lap and none per good or per location, so it costs nothing a player
    # can feel -- and it is the only part of the diagnosis that cannot be read
    # back afterwards: the shape of the allocation leaves no other trace.
    for i in range(1, DIAG_LAPS + 1):
        out.append(f"\tset_global_variable = {{ name = {MOD_ID}_lapn{i} value = 0 }}\n")
    out.append(f"""
\t# Every candidate made ready. **Every counter a `limit` reads has to exist
\t# before the first round**: a comparison against a variable that is not there
\t# is the failure that logs nothing.
\t#
\t# `_plan_seen` marks the province through its first candidate, so
\t# `_plan_prov_locs` is one location per province -- what the row ordering
\t# walks, and the only thing the plan still asks a province.
\tevery_in_global_list = {{
\t\tvariable = {MOD_ID}_candidates
\t\tset_variable = {{ name = {MOD_ID}_load value = 0 }}
\t\tset_variable = {{ name = {MOD_ID}_plan_prank value = 9999 }}
\t\t# **Продовольственный потенциал -- в переменную, а не в строку.** Он не
\t\t# зависит от плана вовсе, только от локации, поэтому считается один раз
\t\t# на обходе: `visible` в ряду умеет читать переменную и не умеет звать
\t\t# значение, а сорок строк со своим счётом на кадр -- это `panel_hitch`.
\t\tset_variable = {{ name = {MOD_ID}_food_pot value = {MOD_ID}_food_potential }}
\t\tif = {{
\t\t\tlimit = {{ NOT = {{ var:{MOD_ID}_food_pot > 0 }} }}
\t\t\tremove_variable = {MOD_ID}_food_pot
\t\t}}
\t\tremove_variable = {MOD_ID}_plan_right
\t\tclear_variable_list = {MOD_ID}_plan_goods
\t\tclear_variable_list = {MOD_ID}_plan_builds
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_plan_touched target = this }}
\t\tif = {{
\t\t\tlimit = {{ {MOD_ID}_plan_is_town = yes }}
\t\t\tset_variable = {{ name = {MOD_ID}_plan_town_row value = 1 }}
\t\t}}
\t\telse = {{ remove_variable = {MOD_ID}_plan_town_row }}
\t\t# **Места житницы -- не места плана.** Комнаты, которые нельзя заполнить,
\t\t# делят доли на всех и оставляют товары ниже потолка: ровно тот случай,
\t\t# из-за которого 259 комнат стояли пустыми 2026-09-08. Ряд у неё остаётся,
\t\t# РГО считается, город городом быть не перестаёт -- в счёт не идут только
\t\t# места.
\t\tif = {{
\t\t\tlimit = {{ {MOD_ID}_is_granary = no }}
\t\t\tif = {{
\t\t\t\tlimit = {{ {MOD_ID}_plan_is_town = yes }}
\t\t\t\tchange_global_variable = {{ name = {MOD_ID}_plan_rooms add = {MOD_ID}_show_plan_cap_urban }}
\t\t\t\tchange_global_variable = {{ name = {MOD_ID}_prooms_t add = {MOD_ID}_show_plan_cap_urban }}
\t\t\t\tchange_global_variable = {{ name = {MOD_ID}_plan_towns add = 1 }}
\t\t\t}}
\t\t\telse = {{
\t\t\t\tchange_global_variable = {{ name = {MOD_ID}_plan_rooms add = {MOD_ID}_show_plan_cap_rural }}
\t\t\t\tchange_global_variable = {{ name = {MOD_ID}_prooms_r add = {MOD_ID}_show_plan_cap_rural }}
\t\t\t}}
\t\t}}
\t\tif = {{
\t\t\tlimit = {{ NOT = {{ has_variable = {MOD_ID}_plan_seen }} }}
\t\t\tprovince_definition = {{
\t\t\t\tevery_location_in_province_definition = {{
\t\t\t\t\tset_variable = {{ name = {MOD_ID}_plan_seen value = 1 }}
\t\t\t\t}}
\t\t\t}}
\t\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_plan_prov_locs target = this }}
\t\t\tchange_global_variable = {{ name = {MOD_ID}_plan_provn add = 1 }}
\t\t}}
\t}}
}}

# One scoring pass per good, the harvest that makes the answers comparable, and
# the count of how few places can hold it.
#
# **This is the expensive half of the mod and the reason the plan is a button of
# its own.** A single-good run reads about five methods on each candidate; this
# reads all {len(rows)} of them, {len(order)} passes over the same ground.
# Scope: country
{MOD_ID}_plan_score = {{
\t# **Покрытие -- до всего остального.** `_rq<k>`, которым раздача выбирает
\t# грамоты, читает `_cov_<товар>`, а посчитать его может только эффект: доля
\t# входа спрашивает `any_location_in_province_definition`.
\t#
\t# **Эпоха ставится тумблером этого окна, и это не мелочь.** Проход умеет
\t# считать «на сейчас» и «на конец», а из какого тумблера брать -- решает тот,
\t# кто зовёт: у плана свой, у поиска по грамоте свой.
\t{MOD_ID}_cov_age_plan = yes
\tsave_scope_as = {MOD_ID}_country
\tevery_in_global_list = {{
\t\tvariable = {MOD_ID}_candidates
\t\t{MOD_ID}_cov_pass = yes
\t\t# Лесенка грамот этой локации -- её читает подсказка строки плана.
\t\t{MOD_ID}_rq_park = yes
\t\t{MOD_ID}_rq_rank = yes
\t}}
""")
    for index, good in enumerate(order, start=1):
        out.append(f"\t{MOD_ID}_score_{index} = yes\n"
                   f"\t{MOD_ID}_plan_harvest_{index} = yes\n")
    out.append(f"\t{MOD_ID}_plan_village_scores = yes\n"
               "}\n")

    # ---- деревня как сущность --------------------------------------------
    #
    # **Его правило: «торговая деревня = 1 уникальный товар».** В равном круге
    # участвует сама деревня, а не пиво с гончаркой через неё. Что она
    # производит — лучший из её собственных рецептов на этой локации, и это
    # **не** засчитывается товару: у пива в сёлах теперь ноль, а вместо доли
    # деревенского производства стоит счёт деревень.
    #
    # `_vb<k>` — эта лучшая выгода, `_vw<k>` — номер товара, который её дал,
    # `_ngv<k>` — на скольких локациях выбранной земли деревня вообще может
    # стоять (её ступень в круге).
    villages = village_entities(rows, split, game)
    out.append(f"""
# Что каждая деревня стоит на каждой локации и сколько локаций её пускают.
# Scope: country
{MOD_ID}_plan_village_scores = {{
""")
    for k in range(1, len(villages) + 1):
        out.append(f"\tset_global_variable = {{ name = {MOD_ID}_ngv{k} value = 0 }}\n")
    out.append(f"""\tevery_in_global_list = {{
\t\tvariable = {MOD_ID}_candidates
\t\tlimit = {{ {MOD_ID}_plan_is_town = no }}
""")
    for k, building in enumerate(villages, start=1):
        makes = [i for i, g in enumerate(order, start=1)
                 if building in (groups.get((g, "r")) or {})]
        picks = "".join(f"""\t\t\tif = {{
\t\t\t\tlimit = {{
\t\t\t\t\tvar:{MOD_ID}_prm{i} > 0
\t\t\t\t\tvar:{MOD_ID}_pr{i} > var:{MOD_ID}_vb{k}
\t\t\t\t}}
\t\t\t\tset_variable = {{ name = {MOD_ID}_vb{k} value = var:{MOD_ID}_pr{i} }}
\t\t\t\tset_variable = {{ name = {MOD_ID}_vw{k} value = {i} }}
\t\t\t}}
""" for i in makes)
        out.append(f"""\t\t# {building}: {", ".join(order[i - 1] for i in makes)}
\t\tset_variable = {{ name = {MOD_ID}_vb{k} value = -1 }}
\t\tset_variable = {{ name = {MOD_ID}_vw{k} value = 0 }}
\t\tif = {{
\t\t\tlimit = {{ {MOD_ID}_stands_{building} = yes }}
{picks}\t\t}}
\t\tif = {{
\t\t\tlimit = {{ var:{MOD_ID}_vw{k} > 0 }}
\t\t\tchange_global_variable = {{ name = {MOD_ID}_ngv{k} add = 1 }}
\t\t}}
""")
    out.append("\t}\n}\n")

    for index, good in enumerate(order, start=1):
        # **One RGO already standing counts as one building of that good**, the
        # owner on 2026-09-01: «1 рго ты можешь рассматривать как один домик
        # локации… хочешь добывать глину 5 домиками на области, там уже есть 2
        # рго глины — тебе нужно всего 3 домика». So it is a count against the
        # quota and never a discount on the score. Only a raw good has an RGO to
        # count, and the engine already refuses to duplicate one: `clay_pit`,
        # `stone_quarry`, `sand_pit` and `bog_iron_smelter` all carry
        # `NOT = { raw_material = goods:<their own> }`.
        rgo_count = "" if good not in game.raw_goods else f"""\tevery_in_global_list = {{
\t\tvariable = {MOD_ID}_candidates
\t\tlimit = {{ raw_material = goods:{good} }}
\t\tchange_global_variable = {{ name = {MOD_ID}_nrgo{index} add = 1 }}
\t\t# **РГО тоже по сторонам.** Скидка «одно РГО — один домик» вычитается из
\t\t# квоты, а квоты теперь две: РГО в селе не должен уменьшать городскую
\t\t# квоту товара, и наоборот.
\t\tif = {{
\t\t\tlimit = {{ {MOD_ID}_plan_is_town = yes }}
\t\t\tchange_global_variable = {{ name = {MOD_ID}_nrgot{index} add = 1 }}
\t\t}}
\t\telse = {{
\t\t\tchange_global_variable = {{ name = {MOD_ID}_nrgor{index} add = 1 }}
\t\t}}
\t}}"""
        # **Сельское место считается только под своё здание, а не под деревню.**
        # Его правило, повторённое полсотни раз: «деревня = товар». Товар, у
        # которого в селе только деревня, своей сельской доли не имеет вовсе, и
        # места деревни ему не принадлежат — иначе он входит третьим лишним в
        # сельский делитель и уменьшает долю тем, у кого своё здание есть.
        # Украшения, 2026-09-08: 284 места торговой деревни давали им долю 54
        # при вечном нуле в столбце «село».
        #
        # **Проверка — та же, что в воротах `_plan_can_rural_<n>`:** какой
        # рецепт выиграл здесь. Победил рецепт деревни — ворота всё равно не
        # откроются, и место товару не принадлежит.
        own_r = sorted({m for building, ms
                        in (groups.get((good, "r")) or {}).items()
                        if building not in villages for m in ms})
        side_count = f"""\t\tif = {{
\t\t\tlimit = {{ {MOD_ID}_plan_is_town = yes }}
\t\t\tchange_global_variable = {{ name = {MOD_ID}_ngt{index} add = 1 }}
\t\t\tchange_global_variable = {{ name = {MOD_ID}_ng{index} add = 1 }}
\t\t}}"""
        if own_r:
            tests = " ".join(f"var:{MOD_ID}_prm{index} = {m}" for m in own_r)
            side_count += f"""
\t\telse = {{
\t\t\tif = {{
\t\t\t\tlimit = {{ OR = {{ {tests} }} }}
\t\t\t\tchange_global_variable = {{ name = {MOD_ID}_ngr{index} add = 1 }}
\t\t\t\tchange_global_variable = {{ name = {MOD_ID}_ng{index} add = 1 }}
\t\t\t}}
\t\t}}"""
        out.append(f"""
# {good}: keep both sides and the method that won each, then divide the ground by
# the better of them, so that {RANK_SCALE} means "the location this good wants most" for
# every good alike. A good nothing here can make stays at zero and never picks.
#
# `_ng{index}` is how many candidates could hold it at all, which is what the
# tiers in `{MOD_ID}_plan_allocate` order the goods by.
# Scope: country
{MOD_ID}_plan_harvest_{index} = {{
\tevery_in_global_list = {{
\t\tvariable = {MOD_ID}_candidates
\t\t# **The two sides are "where may this building stand", not "is it a
\t\t# village".** Thirty production buildings declare `rural_settlement` and
\t\t# only four are villages, so the ranking's category split would leave a
\t\t# rural location with nothing but villages to be offered.
\t\tif = {{
\t\t\tlimit = {{ has_global_variable = {MOD_ID}_plan_by_end }}
\t\t\tset_variable = {{ name = {MOD_ID}_p{index} value = var:{MOD_ID}_pendgain_t }}
\t\t\tset_variable = {{ name = {MOD_ID}_pm{index} value = var:{MOD_ID}_pendbest_method_t }}
\t\t\tset_variable = {{ name = {MOD_ID}_pr{index} value = var:{MOD_ID}_pendgain_r }}
\t\t\tset_variable = {{ name = {MOD_ID}_prm{index} value = var:{MOD_ID}_pendbest_method_r }}
\t\t\t# **Nothing clears the floor: take the best recipe anyway.** A location
\t\t\t# no RGO helps still has to be filled, and a granted right's bundle goes
\t\t\t# up whether the bonus is there or not -- the owner, 2026-09-01.
\t\t\t#
\t\t\t# **And it keeps its own gain, undivided.** The score already *is* how
\t\t\t# much of its ceiling the ground pays: a recipe earning 4% of a possible
\t\t\t# 10 comes in at 400 and is behind everything better by that alone.
\t\t\t# Halving it on top counted the same fact twice and moved the building in
\t\t\t# the queue for want of raw materials, which is the one thing the owner
\t\t\t# forbade outright («не должно... смещён в очереди из-за этого»,
\t\t\t# 2026-09-01, confirmed 2026-09-02). The floor still chooses the method --
\t\t\t# that is the half of his rule that stands: «может влиять только на ВЫБОР
\t\t\t# метода производства в конкретном домике».
\t\t\tif = {{
\t\t\t\tlimit = {{ var:{MOD_ID}_pm{index} = 0 }}
\t\t\t\tset_variable = {{ name = {MOD_ID}_p{index} value = var:{MOD_ID}_pendanygain_t }}
\t\t\t\tset_variable = {{ name = {MOD_ID}_pm{index} value = var:{MOD_ID}_pendanybest_method_t }}
\t\t\t}}
\t\t\tif = {{
\t\t\t\tlimit = {{ var:{MOD_ID}_prm{index} = 0 }}
\t\t\t\tset_variable = {{ name = {MOD_ID}_pr{index} value = var:{MOD_ID}_pendanygain_r }}
\t\t\t\tset_variable = {{ name = {MOD_ID}_prm{index} value = var:{MOD_ID}_pendanybest_method_r }}
\t\t\t}}
\t\t}}
\t\telse = {{
\t\t\tset_variable = {{ name = {MOD_ID}_p{index} value = var:{MOD_ID}_pnowgain_t }}
\t\t\tset_variable = {{ name = {MOD_ID}_pm{index} value = var:{MOD_ID}_pnowbest_method_t }}
\t\t\tset_variable = {{ name = {MOD_ID}_pr{index} value = var:{MOD_ID}_pnowgain_r }}
\t\t\tset_variable = {{ name = {MOD_ID}_prm{index} value = var:{MOD_ID}_pnowbest_method_r }}
\t\t\tif = {{
\t\t\t\tlimit = {{ var:{MOD_ID}_pm{index} = 0 }}
\t\t\t\tset_variable = {{ name = {MOD_ID}_p{index} value = var:{MOD_ID}_pnowanygain_t }}
\t\t\t\tset_variable = {{ name = {MOD_ID}_pm{index} value = var:{MOD_ID}_pnowanybest_method_t }}
\t\t\t}}
\t\t\tif = {{
\t\t\t\tlimit = {{ var:{MOD_ID}_prm{index} = 0 }}
\t\t\t\tset_variable = {{ name = {MOD_ID}_pr{index} value = var:{MOD_ID}_pnowanygain_r }}
\t\t\t\tset_variable = {{ name = {MOD_ID}_prm{index} value = var:{MOD_ID}_pnowanybest_method_r }}
\t\t\t}}
\t\t}}
\t}}
\t# **Три числа обо всей земле, и «Расширить» наращивает их, а не считает
\t# заново.** Обходы ниже идут по `_candidates`, а доливка подставляет туда
\t# только новые локации: обнуление здесь стёрло бы вклад старой земли, и
\t# доля вышла бы посчитанной по одной земле Y. `_ng` и `_nrgo` -- счётчики,
\t# так что «не обнулять» и есть «продолжить счёт»; `_pbest` -- максимум, и
\t# сравнение ниже само оставляет больший.
\tif = {{
\t\tlimit = {{ NOT = {{ has_global_variable = {MOD_ID}_ext }} }}
\t\tset_global_variable = {{ name = {MOD_ID}_ng{index} value = 0 }}
\t\tset_global_variable = {{ name = {MOD_ID}_ngt{index} value = 0 }}
\t\tset_global_variable = {{ name = {MOD_ID}_ngr{index} value = 0 }}
\t\tset_global_variable = {{ name = {MOD_ID}_nrgo{index} value = 0 }}
\t\tset_global_variable = {{ name = {MOD_ID}_nrgot{index} value = 0 }}
\t\tset_global_variable = {{ name = {MOD_ID}_nrgor{index} value = 0 }}
\t\tset_global_variable = {{ name = {MOD_ID}_pbest{index} value = 0 }}
\t}}
\t# **Counted on the side the location actually is**, and not on the better of
\t# the two: a good whose only buildings are rural would otherwise count as
\t# makeable on ground that is all towns. The
\t# thirty-sixth run is what that costs -- five towns of Münsterland reported
\t# «товаров 13» where at most eight could ever stand there, and the quota is
\t# divided by that number, so every good's share came out too small.
\tevery_in_global_list = {{
\t\tvariable = {MOD_ID}_candidates
\t\tlimit = {{
\t\t\tOR = {{
\t\t\t\tAND = {{
\t\t\t\t\t{MOD_ID}_plan_is_town = yes
\t\t\t\t\tvar:{MOD_ID}_pm{index} > 0
\t\t\t\t}}
\t\t\t\tAND = {{
\t\t\t\t\t{MOD_ID}_plan_is_town = no
\t\t\t\t\tvar:{MOD_ID}_prm{index} > 0
\t\t\t\t}}
\t\t\t}}
\t\t}}
\t\t# **И на какой стороне — раздельно.** Комнаты города и села не
\t\t# смешиваются: товар, который умеет только в городе, не может взять
\t\t# сельскую комнату, сколько бы их ни было. Доля, посчитанная одним
\t\t# котлом, обещает ему то, чего земля не имеет.
\t\t#
\t\t# **`_ng` -- сумма этих двух, а не «где товар может появиться».** Товар,
\t\t# у которого своих зданий нет ни на одной стороне, из корзины выпадает
\t\t# целиком, как шёлк: земля его не делает. Рыба, 2026-09-08: «она должна
\t\t# уйти вообще из этой корзины ровно как там нет шёлка. Мы смотрим на
\t\t# домики, которые можно сделать, а рыба нынче такой не является».
{side_count}
\t\t# **And the best this ground ever pays this good**, which is what the open
\t\t# ladder deals the leftovers by. Taken on the side the location actually is,
\t\t# inside the walk that was happening anyway: one comparison a candidate and
\t\t# no walk of its own. The dump has printed this number as `o` all along --
\t\t# read back off the map afterwards -- and afterwards is too late to
\t\t# allocate with.
\t\tif = {{
\t\t\tlimit = {{
\t\t\t\t{MOD_ID}_plan_is_town = yes
\t\t\t\tvar:{MOD_ID}_p{index} > global_var:{MOD_ID}_pbest{index}
\t\t\t}}
\t\t\tset_global_variable = {{ name = {MOD_ID}_pbest{index} value = var:{MOD_ID}_p{index} }}
\t\t}}
\t\tif = {{
\t\t\tlimit = {{
\t\t\t\t{MOD_ID}_plan_is_town = no
\t\t\t\tvar:{MOD_ID}_pr{index} > global_var:{MOD_ID}_pbest{index}
\t\t\t}}
\t\t\tset_global_variable = {{ name = {MOD_ID}_pbest{index} value = var:{MOD_ID}_pr{index} }}
\t\t}}
\t}}
{rgo_count}
\t# **Nothing is normalized any more, and the pass that did it is gone.** The
\t# gain is already the same question for every good -- what fraction of this
\t# recipe's own ceiling this ground pays -- so the ordered walk that used to
\t# find each good's best on the ground, once per good, is 47 walks saved.
\tif = {{
\t\tlimit = {{ global_var:{MOD_ID}_ng{index} > 0 }}
\t\tchange_global_variable = {{ name = {MOD_ID}_plan_scored add = 1 }}
\t}}
}}
""")

    # ---- adding a good to a location ---------------------------------------
    out.append(f"""
# One good, into the location in hand.
#
# **Guarded, and asked the same question the ordered walk used as its `limit`**,
# so the urban-rights round can call this on its own without repeating a word --
# and so a right whose second good wants a building the first took is simply not
# given it.
#
# The building goes into a list beside the good, because that is what a location
# can only hold one of. Which building it is comes off the method the harvest
# kept.
""")
    # Номер метода -> сам метод, чтобы ветка знала его выхлоп. Нумерация та же,
    # что пишут `_pm<n>`/`_prm<n>`: место в `rows`, считая с единицы.
    by_method = {i: m for i, m in enumerate(rows, start=1)}
    for side, listname, method_var, gain_var, cap in (("t", "town", "pm", "p", "urban"),
                                                     ("r", "rural", "prm", "pr", "rural")):
        for index, good in enumerate(order, start=1):
            by_building = groups.get((good, side), {})
            if not by_building:
                continue
            branches = ""
            for building, mis in sorted(by_building.items()):
                tests = "".join(
                    "\t\t\t\tvar:%s_%s%d = %d\n" % (MOD_ID, method_var, index, mi)
                    for mi in sorted(mis))
                # **Счётчик здания, если за него спорят несколько товаров.**
                # Он делится с `_edit_place_*`, и это верно: домик,
                # поставленный руками, тоже существует. Свежий план его не
                # читает -- `_plan_prepare` обнуляет счётчик, -- а доливка
                # читает, и должна.
                bcount = ("\t\t\tchange_global_variable = { name = %s_bn%d add = 1 }\n"
                          % (MOD_ID, shared.index(building) + 1)
                          if building in shared else "")
                # **Сколько товара этот домик на самом деле даёт, в сотых.**
                # Зонд, а не правило: план по-прежнему считает домики. Но домик
                # домику не равен — городская пивоварня-мельница даёт 4.0 пива,
                # сельская `rural_millet_brewery` 0.5, — и пока выхлоп нигде не
                # посчитан, «равномерно» и «неравномерно» проверить нечем.
                # Владелец, 2026-09-06: «усреднять нужно не кол-во домиков, а
                # количество выхлопа».
                #
                # **Ветка на метод, а не на домик**: у одного домика методов
                # несколько и выхлоп у них разный.
                outs = "".join(
                    f"\t\t\tif = {{ limit = {{ var:{MOD_ID}_{method_var}{index} = {mi} }} "
                    f"change_global_variable = {{ name = {MOD_ID}_pout{index} "
                    f"add = {int(round(by_method[mi].output * 100))} }} }}\n"
                    for mi in sorted(mis))
                branches += f"""\t\tif = {{
\t\t\tlimit = {{ OR = {{
{tests}\t\t\t}} }}
{outs}\t\t\tadd_to_variable_list = {{ name = {MOD_ID}_plan_goods target = goods:{good} }}
\t\t\tadd_to_variable_list = {{ name = {MOD_ID}_plan_builds target = building_type:{building} }}
\t\t\tchange_variable = {{ name = {MOD_ID}_load add = 1 }}
\t\t\tchange_global_variable = {{ name = {MOD_ID}_plan_placed add = 1 }}
\t\t\tchange_global_variable = {{ name = {MOD_ID}_plan_added add = 1 }}
\t\t\tchange_global_variable = {{ name = {MOD_ID}_pn{index} add = 1 }}
\t\t\tchange_global_variable = {{ name = {MOD_ID}_pn{side}{index} add = 1 }}
\t\t\t# **И сколько комнат занято на этой стороне.** Сухой круг поднимает
\t\t\t# долю только той стороны, где ещё есть куда ставить: сторон две, и
\t\t\t# растить их вместе значило растить городскую долю ради сельских
\t\t\t# комнат — на северной Германии это давало потолок 20 там, где товар
\t\t\t# доходил до 18.
\t\t\tchange_global_variable = {{ name = {MOD_ID}_plan_p{side} add = 1 }}
{bcount}
\t\t\t# **What this building gets out of standing here**, which is the question
\t\t\t# the owner asked of the whole plan on 2026-09-02: «какой процент из них
\t\t\t# получит выгоду от своего положения на карте». `_{gain_var}{index}` is the
\t\t\t# gain -- the fraction of this recipe's own ceiling the ground pays, out
\t\t\t# of {RANK_SCALE} -- so the two counters are «how many earn anything» and
\t\t\t# «what they earn on average». Two adds a placement and nothing per
\t\t\t# candidate: the plan does not get slower for being answerable.
\t\t\tchange_global_variable = {{ name = {MOD_ID}_plan_gain add = var:{MOD_ID}_{gain_var}{index} }}
\t\t\tif = {{
\t\t\t\tlimit = {{ var:{MOD_ID}_{gain_var}{index} > 0 }}
\t\t\t\tchange_global_variable = {{ name = {MOD_ID}_plan_fed add = 1 }}
\t\t\t}}
\t\t}}
"""
            out.append(f"""# {good}, {"town" if side == "t" else "village"} side.
# Scope: location
{MOD_ID}_plan_try_{listname}_{index} = {{
\tif = {{
\t\tlimit = {{ {MOD_ID}_plan_can_{listname}_{index} = yes }}
{branches}\t}}
}}

# {good}, {"town" if side == "t" else "village"} side, **for the editor**.
#
# **The same placement, asked a different question.** `_plan_can_*` is the plan's
# gate and it asks for a free room; the editor frees the room itself, an eviction
# at a time, so it asks `_edit_fits_*` -- the identical test with the room clause
# taken out. **The scan and the placement are then one predicate**, and cannot
# disagree: the walk chose this location *because* `_edit_fits_*` said yes, so a
# placement that then refuses is impossible by construction.
#
# The owner, 2026-09-04, after «поставить не удалось, и всё осталось как было»:
# «Там не должно быть вообще никаких ограничений и правил, кроме как что 1 домика
# не может быть меньше 1 и собственно самих правил наивыгоднейшей
# установки/удаления.» This is that, and the room is the walk's business.
# Scope: location
{MOD_ID}_edit_place_{listname}_{index} = {{
\tif = {{
\t\tlimit = {{
\t\t\t{MOD_ID}_edit_fits_{listname}_{index} = yes
\t\t\t# **The one invariant, asked again at the last moment.** A location holds
\t\t\t# `cap` buildings and no more. The walk frees the room before it places,
\t\t\t# so this passes by the time it is read -- and on 2026-09-04 it did not:
\t\t\t# 27 buildings went in over the cap, one location reaching 18 of 4, with
\t\t\t# nothing evicted at all. Whatever the walk got wrong, **a placement that
\t\t\t# cannot say no is a plan that can be corrupted**, and the diagnostics'
\t\t\t# `EDIT walk` line says which of the two failed.
\t\t\tvar:{MOD_ID}_load < global_var:{MOD_ID}_plan_cap_{cap}
\t\t}}
{branches}\t}}
}}
""")

    # ---- the row, in an order that does not move -----------------------------
    #
    # **`_plan_goods` is in placement order and that order is not reproducible.**
    # A plan appends a good the round it places it, so a location reads «пиво,
    # вино, спирт»; a slot restored appends in the goods' own numbering and the
    # same location reads «спирт, вино, пиво». Nothing about the plan differs —
    # the owner, 2026-09-03: «Одно и то же, но визуально сбивает с толку.»
    #
    # So the rows read a pair of their own, rebuilt in the goods' own order after
    # every plan, load and edit. `_plan_goods` stays the plan's working list,
    # where order means nothing; `_row_goods` and `_row_builds` are what a window
    # repeats over, and they line up because they are written in one step.
    #
    # **The building is re-derived from `_pm<n>` rather than copied.** That is the
    # same read the placement makes, and the scoring pass is the only thing that
    # writes it — no edit touches it — so the answer is the one that was placed.
    def row_entry(index: int, good: str, tab: str) -> str:
        """One good's cell: the good, then the building the method chose.

        **The side is asked, and it has to be.** The scoring pass writes both
        `_pm<n>` and `_prm<n>` on every candidate -- a location is scored as a
        town and as a village whatever it is now -- so a good whose town and
        village buildings run the same method number would be added twice
        without this. `_plan_try_*` asks the same question through
        `_plan_can_*`; here it is asked directly, because the room is not.
        """
        branches = ""
        for side, method_var, rank in (("t", "pm", "yes"), ("r", "prm", "no")):
            for building, mis in sorted(groups.get((good, side), {}).items()):
                tests = "".join(
                    "%s\t\t\tvar:%s_%s%d = %d\n" % (tab, MOD_ID, method_var, index, mi)
                    for mi in sorted(mis))
                branches += (f"{tab}\tif = {{\n{tab}\t\tlimit = {{\n"
                             f"{tab}\t\t\t{MOD_ID}_plan_is_town = {rank}\n"
                             f"{tab}\t\t\tOR = {{\n{tests}{tab}\t\t\t}}\n"
                             f"{tab}\t\t}}\n"
                             f"{tab}\t\tadd_to_variable_list = {{ name = {MOD_ID}_row_builds "
                             f"target = building_type:{building} }}\n{tab}\t}}\n")
        if not branches:
            return ""
        return (f"{tab}if = {{\n"
                f"{tab}\tlimit = {{\n"
                f"{tab}\t\tis_target_in_variable_list = "
                f"{{ name = {MOD_ID}_plan_goods target = goods:{good} }}\n"
                f"{tab}\t\tNOT = {{ is_target_in_variable_list = "
                f"{{ name = {MOD_ID}_row_goods target = goods:{good} }} }}\n"
                f"{tab}\t}}\n"
                f"{tab}\tadd_to_variable_list = {{ name = {MOD_ID}_row_goods "
                f"target = goods:{good} }}\n"
                f"{branches}{tab}}}\n")

    # **The charter's own goods go first, and that is the whole of the order he
    # asked for.** 2026-09-03, after the rows were made reproducible: «я привык
    # видеть например городские права на локации стекло и кладка -- дальше домики
    # в списке у локации обязательно сначала шли стекольный дом, каменный дом, а
    # потом товар x, товар y… Короче, красота опять попортилась, но уже в другом
    # месте.» The bundle is why the town has the charter, so it reads first; the
    # rest follow in the goods' own numbering, which is what makes the order the
    # same however the plan got there.
    #
    # **The second pass skips what the first already took**, through the `NOT` on
    # `_row_goods` -- a bundle good would otherwise be listed twice.
    bundles = ""
    for k, right in enumerate(output_rights(rows, game), start=1):
        inside = "".join(
            row_entry(order.index(good) + 1, good, "\t\t\t")
            for good in sorted(right.output) if good in order)
        if not inside:
            continue
        bundles += (f"\t\tif = {{\n\t\t\tlimit = {{ has_variable = {MOD_ID}_plan_right "
                    f"var:{MOD_ID}_plan_right = {k} }}\n{inside}\t\t}}\n")
    rest = "".join(row_entry(index, good, "\t\t")
                   for index, good in enumerate(order, start=1))
    # **Домики житницы -- свой список, и пару строк они не трогают.**
    #
    # Сначала они шли в `_row_goods`/`_row_builds` парой «сырьё локации --
    # домик», и это сломало инвариант: `add_to_variable_list` кладёт один и тот
    # же товар один раз, а домиков житница ставит несколько, так что списки
    # разъезжались по длине. Прогон 2026-09-13 это и намерил:
    # `WTP ROWPAIR rows=37 mismatched=7`, при семи ожидаемых нулях.
    #
    # Своего товара у этих домиков нет вовсе -- они ничего не производят, --
    # поэтому им и не место в паре. `_row_gran` рисуется в строке отдельным
    # датамоделем, как деревни в списке изменений.
    gran_rows = "".join(f"""\t\tif = {{
\t\t\tlimit = {{ is_target_in_variable_list = {{ name = {MOD_ID}_plan_builds target = building_type:{b} }} }}
\t\t\tadd_to_variable_list = {{ name = {MOD_ID}_row_gran target = building_type:{b} }}
\t\t}}
""" for b in granary_buildings())
    out.append(f"""
# What a row draws, in an order that is the same however the plan got there.
# Scope: country
{MOD_ID}_plan_rows = {{
\tevery_in_global_list = {{
\t\tvariable = {MOD_ID}_plan_touched
\t\tclear_variable_list = {MOD_ID}_row_goods
\t\tclear_variable_list = {MOD_ID}_row_builds
\t\tclear_variable_list = {MOD_ID}_row_gran
{bundles}{rest}{gran_rows}\t}}
}}

""")

    # ---- the rights round --------------------------------------------------
    #
    # A right the country cannot grant must not shrink the others' quota, so the
    # count asks each one's own gate -- **the very same trigger the grant asks**,
    # and not a second copy of the condition. On «Сейчас» that includes the
    # unlocking advance, so a country before the Discovery age divides its towns
    # between the charters it actually has rather than between all thirteen.
    grant_counts = "".join(
        f"\tif = {{\n\t\tlimit = {{ {MOD_ID}_plan_right_gate_{k} = yes }}\n"
        f"\t\tchange_global_variable = {{ name = {MOD_ID}_rgrant add = 1 }}\n\t}}\n"
        for k in range(1, len(rights) + 1))
    # **И счёт выданных грамот доливка тоже продолжает.** Лестница уровней
    # («ни одна грамота не берёт N-й город, пока каждая не имела шанса на свой
    # N-й») читает `_rn<k>`; обнулённый на доливке, он раздал бы новым городам
    # вторые грамоты тем, у кого их и так больше всех.
    grant_zeroes = (f"\tif = {{\n\t\tlimit = {{ NOT = {{ has_global_variable = {MOD_ID}_ext }} }}\n"
                    + "".join(
                        f"\t\tset_global_variable = {{ name = {MOD_ID}_rn{k} value = 0 }}\n"
                        for k in range(1, len(rights) + 1))
                    + "\t}\n")
    # **Every charter the country could grant is granted somewhere, and they
    # come out level.** The goods have had the covering rule since 2026-09-01 --
    # «все товары которые можно произвести на выбранной земле должны
    # производиться, все» -- and the owner asked the rights to obey the same one,
    # 2026-09-03: «какое-то количество оружейных прав должно было выделиться
    # каким-то городам обязательно».
    #
    # **The ladder is levels, not a cap.** A quota that is only a ceiling does
    # nothing for a charter nobody wants: the pass walks towns, each town takes
    # the best charter with room left, and one the ground pays 62 for is never
    # any town's best while a rival at 441 still has quota. On 48 towns and 9
    # charters that came out 6 6 6 6 6 6 6 3 3 -- the owner, 2026-09-03: «у пушек
    # ювелирки по 3 ... но вот с пушками я на такое не согласен, им есть чё взять».
    #
    # So the ceiling is raised one town at a time and the whole ladder of bands
    # runs at each height: **no charter takes an Nth town until every charter has
    # had the chance of its Nth.** Level 1 is exactly the covering ladder that
    # used to be a special case of its own -- `_rn<k> < 1` is `_rn<k> = 0` -- so
    # that case is gone and the flag with it.
    #
    # Inside a level the bands still decide *which* town, so a charter takes the
    # ground that pays it most before it takes ground that merely tolerates it.
    # That is what put the weaponry charter in Essen rather than in Elsfleth,
    # where it scores nothing: «КАК СУКА ТАК ПОЛУЧАЕТСЯ, ЧТО ЕДИНСТВЕННАЯ ХОРОШАЯ
    # ПРОВИНЦИЯ ДЛЯ ОРУЖЕЙНЫХ ПРАВ -- НЕ ПОЛУЧАЕТ ОРУЖЕЙНЫХ ПРАВ!?»
    #
    # **The price is a town that would rather have had another charter**, and the
    # owner set the price: «я не буду удовлетворён пока не увижу в вестфалии
    # относительно одинаковое количество каждого городского права… и мне похуй
    # что там в формулах».
    level_bands = "".join(
        f"\t\tset_global_variable = {{ name = {MOD_ID}_rband value = {band} }}\n"
        f"\t\tset_global_variable = {{ name = {MOD_ID}_ropen value = 0 }}\n"
        f"\t\t{MOD_ID}_plan_grant_step = yes\n"
        for band in PLAN_BANDS)
    # The same ladder once more, off the loop, for a ground where the guard below
    # cut the levels short. `_rlevel` jumps to the quota so the count is the one
    # the quota always meant.
    final_bands = level_bands.replace("\t\t", "\t\t\t")
    # **The guard is the loop's, and it has to be there.** `_rquota` is towns
    # divided by charters, so a country with many towns and two charters would
    # otherwise walk its whole ground a hundred times over. {RIGHT_LEVELS} levels
    # is past any ground this has been run on -- 48 towns and 9 charters is 6.
    grant_passes = f"""\tset_global_variable = {{ name = {MOD_ID}_rlevel value = 0 }}
\twhile = {{
\t\tlimit = {{
\t\t\tglobal_var:{MOD_ID}_rlevel < global_var:{MOD_ID}_rquota
\t\t\tglobal_var:{MOD_ID}_rlevel < {RIGHT_LEVELS}
\t\t}}
\t\tchange_global_variable = {{ name = {MOD_ID}_rlevel add = 1 }}
{level_bands}\t}}
\tif = {{
\t\tlimit = {{ global_var:{MOD_ID}_rlevel < global_var:{MOD_ID}_rquota }}
\t\tset_global_variable = {{ name = {MOD_ID}_rlevel value = global_var:{MOD_ID}_rquota }}
{final_bands}\t}}
"""
    # And the open pass: the quota and the band lifted together, so a town no
    # charter fits on merit still ends with one.
    grant_passes += (f"\tset_global_variable = {{ name = {MOD_ID}_rband value = 0 }}\n"
                     f"\tset_global_variable = {{ name = {MOD_ID}_ropen value = 1 }}\n"
                     f"\t{MOD_ID}_plan_grant_step = yes\n")
    gran_clear = "".join(f"""\tif = {{
\t\tlimit = {{ is_target_in_variable_list = {{ name = {MOD_ID}_plan_builds target = building_type:{b} }} }}
\t\tremove_list_variable = {{ name = {MOD_ID}_plan_builds target = building_type:{b} }}
\t\tchange_variable = {{ name = {MOD_ID}_load subtract = 1 }}
\t\tchange_global_variable = {{ name = {MOD_ID}_plan_placed subtract = 1 }}
\t}}
""" for b in gran)

    out.append(f"""
# Житницы: что план ставит на локацию, помеченную кормилицей.
#
# **По одному домику, по порядку, пока есть место.** Земледельческая деревня
# первой -- «в основном это земледельческая деревня», -- дальше то, что игра и
# чужие моды дают этой локации: `granary_buildings` собрал их по модификатору,
# а не по имени, поэтому здание чужого мода попадает сюда само.
# Scope: country
{MOD_ID}_plan_fill_granaries = {{
\tset_global_variable = {{ name = {MOD_ID}_gran_put value = 0 }}
\tevery_in_global_list = {{
\t\tvariable = {MOD_ID}_candidates
\t\tlimit = {{ {MOD_ID}_is_granary = yes }}
{gran_put(chr(9) * 2)}\t}}
}}

# И обратное: снять с локации всё, что поставила житница.
#
# **Нужно затем же, зачем и первое**: пометка снимается в редакторе и обязана
# убрать домики немедленно, не дожидаясь «Пересчитать».
# Scope: location
{MOD_ID}_clear_granary_here = {{
{gran_clear}}}
""")
    out.append(f"""
# Urban rights, before any good is placed and only in towns.
#
# **A right is a bundle of goods bound to a town, and obeys the rules a good
# obeys.** The owner, 2026-09-03: «права это просто связка товара, которая
# заложена в город. В остальном она подчиняется абсолютно тем же вещам что и
# простой товар.» So it is dealt exactly as a good is: **a quota over the whole
# ground says how many towns a right may take, and descending bands of gain say
# which towns those are.**
#
# **The quota is the "равномерно" half and it is the only limit.** Neither
# divisor this ever carried survives: the map-wide one made the ranges disjoint,
# so a right granted once could never again win on merit and they went round
# robin; the province-wide one emptied a province of the charter its ground was
# made for. The quota limits the count and leaves the placement to the ground,
# which is the whole distinction the owner drew.
#
# **The bands are what put a scarce charter where it belongs.** A town takes a
# right only where the ground pays at least the band, so the two towns on the map
# with silver under them are reached by the jewelry charter in band 800, before
# any town is handed a charter it merely tolerates. The last pass lifts the quota
# and the band together, so no town is left without one.
#
# **And a right is granted whether or not the whole bundle fits**, since
# 2026-09-01: «Оно БУДЕТ выдано ОБЯЗАТЕЛЬНО. И каждый такой город обязательно
# получит все здания из его бонуса.» The bundle's buildings go in before any
# ordinary good touches the town, and where the urban cap is smaller than the
# bundle the town simply runs out of room.
# Scope: country
{MOD_ID}_plan_place_rights = {{
\t# How many rights this country could grant at all. The quota is towns divided
\t# by that, so a country with three rights available spreads over three and not
\t# over the {len(rights)} the game defines.
\tset_global_variable = {{ name = {MOD_ID}_rgrant value = 0 }}
{grant_counts}\t# **Квота делит то, между чем грамоты и делятся.** Города -- в обычном
\t# режиме, провинции -- когда их {RIGHT_PROV_MIN} и больше и грамота стала
\t# свойством провинции: делить провинциальные грамоты на число городов
\t# значило бы выдать каждой грамоте в несколько раз больше провинций, чем
\t# земля держит, и лестница уровней выродилась бы в первый же круг.
\tset_global_variable = {{ name = {MOD_ID}_rquota value = global_var:{MOD_ID}_plan_towns }}
\tif = {{
\t\tlimit = {{ global_var:{MOD_ID}_plan_provn >= {RIGHT_PROV_MIN} }}
\t\tset_global_variable = {{ name = {MOD_ID}_rquota value = global_var:{MOD_ID}_plan_provn }}
\t}}
\tif = {{
\t\tlimit = {{ global_var:{MOD_ID}_rgrant > 0 }}
\t\tchange_global_variable = {{ name = {MOD_ID}_rquota divide = {MOD_ID}_rgrant_value }}
\t}}
\t# `max` is the floor on a variable operation -- `_plan_quota` above depends on
\t# the same and says so. A ground with fewer towns than rights still gives every
\t# charter one town to want.
\tchange_global_variable = {{ name = {MOD_ID}_rquota max = 1 }}
{grant_zeroes}{grant_passes}}}

# One pass of the rights round: every town still empty takes the best right the
# ground pays `_rband` for and whose quota is not spent.
# Scope: country
{MOD_ID}_plan_grant_pass = {{
\tevery_in_global_list = {{
\t\tvariable = {MOD_ID}_candidates
\t\tlimit = {{
\t\t\t{MOD_ID}_plan_is_town = yes
\t\t\tvar:{MOD_ID}_load = 0
\t\t}}
\t\t# **Minus one and not nought.** The winner is taken with `rtry > rbest`, so
\t\t# a charter this ground pays exactly nothing for could never win even when it
\t\t# was the only one left: 2026-09-03, Westphalia has no precious metal at all,
\t\t# the jewelry charter scored 0 in all 48 towns, and even the covering ladder
\t\t# could not place it. `_rbest_k` still starts at 0, so a town where no charter
\t\t# fits gets none.
\t\tset_variable = {{ name = {MOD_ID}_rbest value = -1 }}
\t\tset_variable = {{ name = {MOD_ID}_rbest_k value = 0 }}
""")
    for k, right in enumerate(rights, start=1):
        bundle = sorted(right.output)
        gate = (f"\t\t\t\tscope:{MOD_ID}_country = "
                f"{{ {MOD_ID}_plan_right_gate_{k} = yes }}\n")
        out.append(f"""\t\t# {right.key}: {", ".join(bundle)}
\t\tset_variable = {{ name = {MOD_ID}_rtry value = {MOD_ID}_rq{k} }}
\t\tif = {{
\t\t\tlimit = {{
\t\t\t\tvar:{MOD_ID}_rtry > var:{MOD_ID}_rbest
\t\t\t\t{MOD_ID}_plan_right_fits_{k} = yes
\t\t\t\t# The band: what this ground has to pay before the charter is taken
\t\t\t\t# here at all. The open pass sets it to 0.
\t\t\t\tvar:{MOD_ID}_rtry >= global_var:{MOD_ID}_rband
\t\t\t\t# The level: how many towns any one charter may hold so far. It
\t\t\t\t# climbs by one at a time, so no charter takes an Nth town while
\t\t\t\t# another is still short of its Nth -- that, and not the quota it
\t\t\t\t# ends at, is what makes the counts come out level. The open pass
\t\t\t\t# lifts it: a town with no charter at all is worse than an uneven count.
\t\t\t\tOR = {{
\t\t\t\t\tglobal_var:{MOD_ID}_ropen = 1
\t\t\t\t\tglobal_var:{MOD_ID}_rn{k} < global_var:{MOD_ID}_rlevel
\t\t\t\t}}
{gate}\t\t\t}}
\t\t\tset_variable = {{ name = {MOD_ID}_rbest value = var:{MOD_ID}_rtry }}
\t\t\tset_variable = {{ name = {MOD_ID}_rbest_k value = {k} }}
\t\t}}
""")
    # **A bundle good the ground refuses gets its input planted instead.** The
    # right's building is mandatory and the slot is the right's, so where glass
    # cannot stand the slot goes to the sand pit that would make it possible
    # rather than back to the ordinary goods -- the owner, 2026-09-01. Derived
    # rather than named: `market_inputs` finds one pair in the whole game.
    substitute = market_inputs(game)
    out.append(grant_bundle_blocks(rights, order, groups, substitute, "\t\t"))
    out.append("\t}\n}\n")

    # ---- одна грамота на провинцию ----------------------------------------
    #
    # Провинциальный близнец прохода выше. Всё, что делает лестницу лестницей --
    # полосы, уровни, квота, открывающий проход, -- то же самое и читается из тех
    # же глобалок; меняются ровно две вещи: **кого обходим** (представителей
    # провинций вместо городов) и **чем платит земля** (средняя `_rq<k>` по тем
    # городам провинции, которым грамота вообще подходит, вместо числа одного
    # города).
    #
    # Средняя, а не сумма, по той же причине, по какой она средняя в
    # «Специализации»: сумма выбирала бы грамоту числом городов, а не тем, что
    # под ними лежит.
    #
    # **Второй раз провинция не берёт, и сторожа для этого не нужно.** Выдача
    # ставит связку каждому городу провинции, значит `_load` у них уже не ноль,
    # значит на следующем круге `_sprn` у этой провинции выйдет нулём при любой
    # грамоте и `_sprk` останется нулём. Тот же сторож, что у обычного прохода,
    # и ровно та же строка.
    prov_picks = ""
    for k, right in enumerate(rights, start=1):
        prov_picks += f"""\t\t# {right.key}
\t\tset_global_variable = {{ name = {MOD_ID}_sprt value = 0 }}
\t\tset_global_variable = {{ name = {MOD_ID}_sprn value = 0 }}
\t\tprovince_definition = {{
\t\t\tevery_location_in_province_definition = {{
\t\t\t\tlimit = {{
\t\t\t\t\tis_target_in_global_variable_list = {{ name = {MOD_ID}_candidates target = this }}
\t\t\t\t\t{MOD_ID}_plan_is_town = yes
\t\t\t\t\tvar:{MOD_ID}_load = 0
\t\t\t\t\t{MOD_ID}_plan_right_fits_{k} = yes
\t\t\t\t}}
\t\t\t\tchange_global_variable = {{ name = {MOD_ID}_sprt add = {MOD_ID}_rq{k} }}
\t\t\t\tchange_global_variable = {{ name = {MOD_ID}_sprn add = 1 }}
\t\t\t}}
\t\t}}
\t\tif = {{
\t\t\tlimit = {{
\t\t\t\tglobal_var:{MOD_ID}_sprn > 0
\t\t\t\tscope:{MOD_ID}_country = {{ {MOD_ID}_plan_right_gate_{k} = yes }}
\t\t\t}}
\t\t\tchange_global_variable = {{ name = {MOD_ID}_sprt divide = {MOD_ID}_sprn_value }}
\t\t\tif = {{
\t\t\t\tlimit = {{
\t\t\t\t\tglobal_var:{MOD_ID}_sprt > global_var:{MOD_ID}_sprv
\t\t\t\t\tglobal_var:{MOD_ID}_sprt >= global_var:{MOD_ID}_rband
\t\t\t\t\tOR = {{
\t\t\t\t\t\tglobal_var:{MOD_ID}_ropen = 1
\t\t\t\t\t\tglobal_var:{MOD_ID}_rn{k} < global_var:{MOD_ID}_rlevel
\t\t\t\t\t}}
\t\t\t\t}}
\t\t\t\tset_global_variable = {{ name = {MOD_ID}_sprv value = global_var:{MOD_ID}_sprt }}
\t\t\t\tset_global_variable = {{ name = {MOD_ID}_sprk value = {k} }}
\t\t\t}}
\t\t}}
"""
    prov_level = "".join(
        f"\t\t\tif = {{\n\t\t\t\tlimit = {{ global_var:{MOD_ID}_sprk = {k} }}\n"
        f"\t\t\t\tchange_global_variable = {{ name = {MOD_ID}_rn{k} add = 1 }}\n\t\t\t}}\n"
        for k in range(1, len(rights) + 1))
    out.append(f"""
# Один круг провинциальной раздачи: каждая ещё пустая провинция берёт ту
# грамоту, за которую её города платят в среднем больше всего, и отдаёт её всем
# своим городам разом.
#
# **`-1`, а не ноль, как начальное лучшее** -- по той же причине, что и в
# обычном проходе: земля, за которую ни одна грамота не платит ничего, всё
# равно должна получить ту, что ей хоть как-то подходит.
#
# **`_rn<k>` здесь считает провинции**, поэтому он прибавляется один раз
# снаружи обхода городов, а связка выкладывается без него.
# Scope: country
{MOD_ID}_plan_grant_pass_prov = {{
\tevery_in_global_list = {{
\t\tvariable = {MOD_ID}_plan_prov_locs
\t\tset_global_variable = {{ name = {MOD_ID}_sprv value = -1 }}
\t\tset_global_variable = {{ name = {MOD_ID}_sprk value = 0 }}
{prov_picks}\t\tif = {{
\t\t\tlimit = {{ global_var:{MOD_ID}_sprk > 0 }}
{prov_level}\t\t\tprovince_definition = {{
\t\t\t\tevery_location_in_province_definition = {{
\t\t\t\t\tlimit = {{
\t\t\t\t\t\tis_target_in_global_variable_list = {{ name = {MOD_ID}_candidates target = this }}
\t\t\t\t\t\t{MOD_ID}_plan_is_town = yes
\t\t\t\t\t\tvar:{MOD_ID}_load = 0
\t\t\t\t\t}}
\t\t\t\t\tset_variable = {{ name = {MOD_ID}_rbest_k value = global_var:{MOD_ID}_sprk }}
{grant_bundle_blocks(rights, order, groups, substitute, chr(9) * 5, level_counter=False)}\t\t\t\t\tremove_variable = {MOD_ID}_rbest_k
\t\t\t\t}}
\t\t\t}}
\t\t}}
\t}}
}}

# **Чем раздаются грамоты -- городами или провинциями.** Его слово, 2026-09-12:
# «Если на выбранной земле {RIGHT_PROV_MIN} или больше провинций -- расчёт идёт строго 1 гор.
# право на провинцию». Порог по провинциям выбранной земли; ниже него ничего не
# меняется, и маленькая земля планируется ровно как планировалась.
#
# **Одна развилка на всю лестницу, а не на каждый её шаг.** Полосы и уровни
# зовут этот шаг, поэтому переключать гранулярность посреди раздачи нечем -- и
# незачем.
# Scope: country
{MOD_ID}_plan_grant_step = {{
\tif = {{
\t\tlimit = {{ global_var:{MOD_ID}_plan_provn >= {RIGHT_PROV_MIN} }}
\t\t{MOD_ID}_plan_grant_pass_prov = yes
\t}}
\telse = {{ {MOD_ID}_plan_grant_pass = yes }}
}}
""")

    # ---- the quota ---------------------------------------------------------
    #
    # What «равномерно» means, and it is the same rule at both scales the owner
    # described. Three provinces and forty goods gives a quota under one, so
    # every good takes exactly one place and the small realm comes out mixed
    # rather than specialised; a large realm gives a quota of twenty-odd, so each
    # good takes its best twenty-odd places -- which are the ones its raw
    # materials lie under -- and then stops, and the rooms left over are what the
    # goods with no bonus anywhere fill. His answer 4, in one number.
    #
    # **The share is over the whole ground, and a charter's buildings are spent
    # out of the good's own share rather than added to it.** Both halves changed
    # on 2026-09-03 and the owner's arithmetic is the reason: «как будто бы 1
    # домик + 2 РГО не равняются 9, а равняются 3. Так почему? Почему РГО
    # внезапно стал весить 4 вместо 1?»
    #
    # He was reading a real fault. The share used to be *what the charters left*
    # divided by the goods -- on Westphalia 84 rooms over 35 goods, **2** -- and
    # then each good got its own charters added back. So wine, whose charter is
    # brewing, walked in at 2 + 6 = **8**, and iron, with two RGOs under it,
    # walked in at 2 - 2 = 0, floored to **1**. Nine wine and one iron is that
    # subtraction, not the ground: two RGOs did not cost iron two buildings, they
    # cost it seven, because the base they came off was 2.
    #
    # Now the share is 192 rooms over 35 goods, **5**, and what a charter put down
    # counts against it: wine walks in holding 6 of a share of 5 and takes no
    # more, iron gets 5 - 2 = **3**. That is his own rule -- one RGO is one
    # building -- doing what it says.
    #
    # **What this overturns, and why that is right.** The addition was put in
    # after the thirty-eighth run, where `tools` held six charter buildings
    # against a quota of 2 and so could not take a free room in Sauerland at a
    # gain of 799. That was a real fault of a share of **2**; against a share of
    # 5 a good already holding 6 is above its share, and stopping there is the
    # evenness rather than a bug. The old fault cannot recur and the new rule is
    # the one he asked for.
    #
    # `_pn<n>` is the rights' count and nothing else at this moment: `_plan_run`
    # calls this between `_plan_place_rights` and `_plan_allocate`, and nothing
    # else in the plan writes it -- so the allocator's own `_pn<n> < _pq<n>` is
    # what charges the charters to the share, with no second subtraction here.
    # **Две стороны — две независимые дележки, и это проще трёх классов.**
    # Городские комнаты делятся между товарами, умеющими в город; сельские —
    # между умеющими в село. Товар, умеющий обе, просто участвует в обеих. Класс
    # «где угодно» перестаёт быть особым случаем: он не нужен.
    #
    # **Владелец, 2026-09-07:** «я хочу видеть приблизительно одинаковое кол-во
    # городских домиков по отношению к друг другу, примерно как городские права
    # 7/7/7/7/6/6». Это ровно оно и есть — и без единого весового коэффициента.
    # **Деревня живёт в том же сельском котле, что и товары**: её потолок —
    # сельская доля, и стеснённой деревне его так же снимают. Рыбацкая, 2026-09-08:
    # 42 прибрежных места при доле 56 — делить нечего, а она взяла 35.
    bquotas = "".join(
        f"\tset_global_variable = {{ name = {MOD_ID}_bq{k} "
        f"value = global_var:{MOD_ID}_qcapr }}\n"
        for k in range(1, len(shared) + 1))
    bquotas += "".join(
        f"""\tif = {{
\t\tlimit = {{ NOT = {{ global_var:{MOD_ID}_ngv{k} > global_var:{MOD_ID}_qcapr }} }}
\t\t# **«Потолка нет» пишется её собственной землёй, а не {SHARE_CAP}.**
\t\t# Столько она всё равно взять не может, а в сводке это читаемое число
\t\t# вместо 2000.
\t\tset_global_variable = {{ name = {MOD_ID}_bq{shared.index(b) + 1} value = global_var:{MOD_ID}_ngv{k} }}
\t}}
""" for k, b in enumerate(village_entities(rows, split, game), start=1))

    # **Доля стороны считается точно и сразу, а не растёт сухими кругами.**
    # Это наименьшее X, при котором `Σ min(своя земля, X − свои РГО)` по всем
    # участникам стороны накрывает её комнаты. Раньше доля стартовала с
    # «комнаты ÷ товары» и доползала до правды сухими кругами, и всё, что
    # считалось от неё **до** этого, считалось от вранья — проход стеснённых
    # пропускал железо, потому что его 43 локации были больше стартовых 36 и
    # меньше настоящих 71.
    #
    # **Скидка за РГО стоит внутри `min`, и это не украшение.** Без неё X
    # накрывал комнаты, а товар ставил `X − РГО`, и земля недобирала ровно
    # столько комнат, сколько на ней РГО: 1121 из 1380 при 284 РГО,
    # прогон 2026-09-08. Со скидкой внутри каждый кончает на X **считая РГО**
    # — это и есть его мерка равномерности.
    def share_loop(cap, rooms, terms):
        body = ""
        for land, adjust in terms:
            if adjust is None:
                eff = (f"\t\t\tset_global_variable = {{ name = {MOD_ID}_qeff "
                       f"value = global_var:{MOD_ID}_{cap} }}\n")
            else:
                op, var = adjust
                eff = (f"\t\t\tset_global_variable = {{ name = {MOD_ID}_qeff "
                       f"value = global_var:{MOD_ID}_{cap} }}\n"
                       f"\t\t\tchange_global_variable = {{ name = {MOD_ID}_qeff "
                       f"{op} = global_var:{MOD_ID}_{var} }}\n"
                       f"\t\t\tchange_global_variable = {{ name = {MOD_ID}_qeff max = 0 }}\n")
            body += f"""\t\tif = {{
\t\t\tlimit = {{ global_var:{MOD_ID}_{land} > 0 }}
{eff}\t\t\tif = {{
\t\t\t\tlimit = {{ global_var:{MOD_ID}_{land} < global_var:{MOD_ID}_qeff }}
\t\t\t\tchange_global_variable = {{ name = {MOD_ID}_qsum add = global_var:{MOD_ID}_{land} }}
\t\t\t}}
\t\t\telse = {{
\t\t\t\tchange_global_variable = {{ name = {MOD_ID}_qsum add = global_var:{MOD_ID}_qeff }}
\t\t\t}}
\t\t}}
"""
        return f"""\tset_global_variable = {{ name = {MOD_ID}_{cap} value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_qgo value = 1 }}
\twhile = {{
\t\tlimit = {{
\t\t\tglobal_var:{MOD_ID}_qgo = 1
\t\t\tglobal_var:{MOD_ID}_{cap} < {SHARE_CAP}
\t\t\t# Доля больше, чем комнат на стороне, смысла не имеет: это страховка
\t\t\t# от земли, которую никакая доля не накроет -- иначе цикл крутится до
\t\t\t# {SHARE_CAP} впустую.
\t\t\tglobal_var:{MOD_ID}_{rooms} > global_var:{MOD_ID}_{cap}
\t\t}}
\t\tchange_global_variable = {{ name = {MOD_ID}_{cap} add = 1 }}
\t\tset_global_variable = {{ name = {MOD_ID}_qsum value = 0 }}
{body}\t\tif = {{
\t\t\tlimit = {{ NOT = {{ global_var:{MOD_ID}_qsum < global_var:{MOD_ID}_{rooms} }} }}
\t\t\tset_global_variable = {{ name = {MOD_ID}_qgo value = 0 }}
\t\t}}
\t}}
\t# **И на единицу ниже найденного.** Цикл возвращает наименьшее X, при котором
\t# ёмкость накрывает комнаты, — а накрывает она с запасом: 35 товаров на 528
\t# городских комнат нацело не делятся, и при X=20 потолков выходит на 577
\t# домиков. Тогда потолок в таблице стоит на 2-3 выше того, до чего товар
\t# доходит. Начинать надо снизу и дать сухому кругу дойти ровно до той доли,
\t# на которой земля заполнилась: он поднимает по единице, а последнюю,
\t# никому не доставшуюся, раздача в конце отменяет. Тогда «доля» и есть то,
\t# что товар получает.
\tchange_global_variable = {{ name = {MOD_ID}_{cap} subtract = 1 }}
\tchange_global_variable = {{ name = {MOD_ID}_{cap} max = 1 }}
"""
    villages_ = village_entities(rows, split, game)
    own_rural = [i for i, g in enumerate(order, start=1)
                 if any(b not in villages_ for b in (groups.get((g, "r")) or {}))]
    # **Скидка за РГО считается внутри дележки, иначе земля не заполняется.**
    # Доля решала `Σ min(своя земля, X) >= комнаты`, а строил товар `X - свои
    # РГО` — и на северной Германии 284 РГО оставляли 259 комнат пустыми
    # (1121 из 1380, прогон 2026-09-08). Теперь X ищется по тому, что товар
    # действительно поставит: `Σ min(земля, X - РГО) >= комнаты`. Тогда каждый
    # кончает ровно на X **считая РГО** — это и есть его мерка равномерности,
    # — и земля заполняется.
    #
    # **Комнаты берутся все, включая занятые грамотами.** Грамота ставит домик
    # того же товара, и потолок товара его накрывает: вычитать грамоты из
    # комнат значило вычитать их дважды. С вычетом городская ёмкость выходила
    # 424 на 528 комнат.
    shares = share_loop("qcapt", "prooms_t",
                        [(f"ngt{i}", ("subtract", f"nrgo{i}"))
                         for i in range(1, len(order) + 1)])
    # **Остаток скидки, не поместившийся в город, уходит в село** — его
    # правило 2026-09-08. Считается один раз, когда городская доля уже
    # известна, и сельская дележка считает по нему.
    shares += "".join(
        f"""\tset_global_variable = {{ name = {MOD_ID}_qeff value = 0 }}
\tif = {{
\t\tlimit = {{ global_var:{MOD_ID}_ngt{i} > 0 }}
\t\tset_global_variable = {{ name = {MOD_ID}_qeff value = global_var:{MOD_ID}_qcapt }}
\t}}
\tchange_global_variable = {{ name = {MOD_ID}_qeff subtract = global_var:{MOD_ID}_nrgo{i} }}
\tset_global_variable = {{ name = {MOD_ID}_rgl{i} value = 0 }}
\tif = {{
\t\tlimit = {{ global_var:{MOD_ID}_qeff < 0 }}
\t\tset_global_variable = {{ name = {MOD_ID}_rgl{i} value = global_var:{MOD_ID}_qeff }}
\t}}
""" for i in own_rural)
    shares += share_loop("qcapr", "prooms_r",
                         [(f"ngr{i}", ("add", f"rgl{i}")) for i in own_rural]
                         + [(f"ngv{k}", None)
                            for k in range(1, len(villages_) + 1)])
    # **Сельскую долю делят сущности, а не товары.** Своё сельское здание есть
    # у четырнадцати товаров; три деревни считаются сами. Товар, у которого в
    # селе только деревня, из делителя выпадает — он получает то, что случится
    # в деревне, а своей доли в селе у него нет. На северной Германии это 18
    # сущностей вместо 23, то есть 852 ÷ 18 = 47 вместо 37.
    villages_ = village_entities(rows, split, game)
    own_rural = [i for i, g in enumerate(order, start=1)
                 if any(b not in villages_ for b in (groups.get((g, "r")) or {}))]
    counts = "".join(
        f"""\tif = {{ limit = {{ global_var:{MOD_ID}_ngt{index} > 0 }} """
        f"""change_global_variable = {{ name = {MOD_ID}_qgt add = 1 }} }}\n"""
        for index in range(1, len(order) + 1))
    counts += "".join(
        f"""\tif = {{ limit = {{ global_var:{MOD_ID}_ngr{index} > 0 }} """
        f"""change_global_variable = {{ name = {MOD_ID}_qgr add = 1 }} }}\n"""
        for index in own_rural)
    counts += "".join(
        f"""\tif = {{ limit = {{ global_var:{MOD_ID}_ngv{k} > 0 }} """
        f"""change_global_variable = {{ name = {MOD_ID}_qgr add = 1 }} }}\n"""
        for k in range(1, len(villages_) + 1))
    # **Скидка за РГО срезает сначала городской потолок, и только остаток —
    # сельский.** Его правило, 2026-09-08: «РГО в первую очередь вычитают из
    # городских лимитов… значит в городах мне не будет тыкаться глина, пока РГО
    # хватает для этого перевеса». Городская комната дороже сельской, а РГО их
    # не различает: глина с 16 своими РГО занимала 11 городов из 70, притом что
    # в селе ей 150 мест.
    #
    # **И это же чинит потерю скидки.** Делили её раньше по тому, ГДЕ РГО стоит:
    # у `medicaments` из семи РГО в городе стоит **одно** (`rgot=1 rgor=6`), а
    # строить она умеет только в городе — шесть скидок срезали сельский потолок,
    # которым она не пользуется никогда, и она кончила на 17+7=24 против 17+0=17
    # у `incense`. Теперь все семь уходят в город: потолок 15-7=8, и она встаёт
    # вровень.
    # **Стеснённый товар потолков сторон не имеет вовсе.** Его земля меньше его
    # же доли — значит делить ему нечего, и любой потолок только отнимает.
    # Железо, 2026-09-08: 43 локации на всю землю при доле 60, а городской
    # потолок после скидки за РГО стал 9 из 20 — оно взяло 8 городов из 15 и
    # кончило на 34+11=45 вместо 43+11=54. Скидка за РГО съела ровно те места,
    # которых у него и так мало, а добрать негде: в селе всего 28 локаций.
    #
    # **Признак — своя земля против доли ДО скидки**, `_ngt + _ngr <=
    # _plan_quota`, а не против `_pq`. Его поправка, 2026-09-08, и она закрывает
    # щель: при доле 70, десяти своих РГО и земле в 61 локацию признак по `_pq`
    # (60) сказал бы «обычный», скидка срезала бы город, и товар ушёл бы ниже
    # своих же шестидесяти — при том, что земли ему и так впритык. Скидка имеет
    # смысл только там, где земли хватает на **полную** долю: тогда она решает,
    # где долю набрать, а не сколько её отнять.
    #
    # Соль этим и чинится: земли 68 при доле 70 — стеснена, потолков сторон нет,
    # 26+42 = 52 домика при `_pq` 52, всего 71 вровень со всеми. По старому
    # признаку (68 > 52) она считалась обычной, городской потолок после скидки
    # равнялся единице, и она кончала на 62.
    #
    # Для `medicaments` признак ложен (132 городских локации против доли 71), и
    # скидка там работает как задумано.
    # **Доля товара — сумма долей тех сторон, где он умеет, минус свои РГО.**
    # Двусторонний держит обе, односторонний одну. Это его решение 2026-09-08:
    # два котла, полная доля в каждом.
    #
    # **Скидка за РГО срезает сначала городской потолок**, остаток — сельский:
    # городская комната дороже, а РГО их не различает.
    #
    # **У стеснённой стороны потолка нет вовсе.** Если земли товара на этой
    # стороне не больше её доли, делить ему нечего и любой потолок только
    # отнимает — железо с 15 городами и 28 сёлами при долях 23 и 48 берёт всё.
    # **Три равенства, которые эта дюжина строк держит.** Владелец, 2026-09-08:
    # «арифметика любит красоту».
    #
    #     доля           = доля города + доля села        (три числа на таблицу)
    #     доля − РГО     = доля город + доля село         (везде, где земля даёт)
    #     домиков + РГО  = доля                           (везде, где земля даёт)
    #
    # **Перелив.** Доля стороны, которую своя земля не может принять, уходит на
    # другую: у соли 42 сельских локации при сельской доле 55, и тринадцать её
    # доли годятся только в городе. Без перелива соль кончала на 42 при доле 56.
    #
    # **Скидка за РГО срезает город первым** — его правило: «в городах мне не
    # будет тыкаться глина, пока РГО хватает для этого перевеса». **Но не
    # глубже, чем село способно добрать**: если селу не хватает земли на всю
    # `_pq`, недостача возвращается городу. Иначе скидка отнимает домики,
    # которых товару и так не досталось.
    #
    # **Стеснённой стороны как особого случая больше нет.** Она делала
    # `_pqt = _pqr = _pq` у товара, стеснённого с обеих сторон, и он ставил
    # `_pq` **на каждой**: камень 73 домика при квоте 62 и 88 «с РГО» против 75
    # у всех (прогон 2026-09-08). Перелив делает ту же работу без этой дыры.
    quota_lines = "".join(
        f"""\tset_global_variable = {{ name = {MOD_ID}_qsct value = 0 }}
\tif = {{
\t\tlimit = {{ global_var:{MOD_ID}_ngt{index} > 0 }}
\t\tset_global_variable = {{ name = {MOD_ID}_qsct value = global_var:{MOD_ID}_qcapt }}
\t}}
\tset_global_variable = {{ name = {MOD_ID}_qscr value = 0 }}
""" + (f"""\tif = {{
\t\tlimit = {{ global_var:{MOD_ID}_ngr{index} > 0 }}
\t\tset_global_variable = {{ name = {MOD_ID}_qscr value = global_var:{MOD_ID}_qcapr }}
\t}}
""" if index in own_rural else "") + f"""\t# Доля до скидки: сумма долей тех сторон, где товар умеет. Перелив её не
\t# меняет — это по-прежнему одно из трёх чисел таблицы.
\tset_global_variable = {{ name = {MOD_ID}_pqraw{index} value = global_var:{MOD_ID}_qsct }}
\tchange_global_variable = {{ name = {MOD_ID}_pqraw{index} add = global_var:{MOD_ID}_qscr }}
\t# Перелив в обе стороны, город после села — землю проверяем ещё раз.
\tif = {{
\t\tlimit = {{ global_var:{MOD_ID}_qsct > global_var:{MOD_ID}_ngt{index} }}
\t\tset_global_variable = {{ name = {MOD_ID}_qeff value = global_var:{MOD_ID}_qsct }}
\t\tchange_global_variable = {{ name = {MOD_ID}_qeff subtract = global_var:{MOD_ID}_ngt{index} }}
\t\tchange_global_variable = {{ name = {MOD_ID}_qscr add = global_var:{MOD_ID}_qeff }}
\t\tset_global_variable = {{ name = {MOD_ID}_qsct value = global_var:{MOD_ID}_ngt{index} }}
\t}}
\tif = {{
\t\tlimit = {{ global_var:{MOD_ID}_qscr > global_var:{MOD_ID}_ngr{index} }}
\t\tset_global_variable = {{ name = {MOD_ID}_qeff value = global_var:{MOD_ID}_qscr }}
\t\tchange_global_variable = {{ name = {MOD_ID}_qeff subtract = global_var:{MOD_ID}_ngr{index} }}
\t\tchange_global_variable = {{ name = {MOD_ID}_qsct add = global_var:{MOD_ID}_qeff }}
\t\tset_global_variable = {{ name = {MOD_ID}_qscr value = global_var:{MOD_ID}_ngr{index} }}
\t}}
\tif = {{
\t\tlimit = {{ global_var:{MOD_ID}_qsct > global_var:{MOD_ID}_ngt{index} }}
\t\tset_global_variable = {{ name = {MOD_ID}_qsct value = global_var:{MOD_ID}_ngt{index} }}
\t}}
\t# Общая квота: доля минус свои РГО, но не ниже одного.
\tset_global_variable = {{ name = {MOD_ID}_pq{index} value = global_var:{MOD_ID}_pqraw{index} }}
\tchange_global_variable = {{ name = {MOD_ID}_pq{index} subtract = global_var:{MOD_ID}_nrgo{index} }}
\tchange_global_variable = {{ name = {MOD_ID}_pq{index} max = 1 }}
\t# Городской потолок: своя доля минус РГО, но не ниже того, что село не добирает.
\tset_global_variable = {{ name = {MOD_ID}_pqt{index} value = global_var:{MOD_ID}_qsct }}
\tchange_global_variable = {{ name = {MOD_ID}_pqt{index} subtract = global_var:{MOD_ID}_nrgo{index} }}
\tset_global_variable = {{ name = {MOD_ID}_qeff value = global_var:{MOD_ID}_pq{index} }}
\tchange_global_variable = {{ name = {MOD_ID}_qeff subtract = global_var:{MOD_ID}_qscr }}
\tif = {{
\t\tlimit = {{ global_var:{MOD_ID}_pqt{index} < global_var:{MOD_ID}_qeff }}
\t\tset_global_variable = {{ name = {MOD_ID}_pqt{index} value = global_var:{MOD_ID}_qeff }}
\t}}
\tif = {{
\t\tlimit = {{ global_var:{MOD_ID}_pqt{index} > global_var:{MOD_ID}_qsct }}
\t\tset_global_variable = {{ name = {MOD_ID}_pqt{index} value = global_var:{MOD_ID}_qsct }}
\t}}
\tchange_global_variable = {{ name = {MOD_ID}_pqt{index} max = 0 }}
\t# Сельский потолок: всё, что осталось от общей квоты, но не больше своей земли.
\tset_global_variable = {{ name = {MOD_ID}_pqr{index} value = global_var:{MOD_ID}_pq{index} }}
\tchange_global_variable = {{ name = {MOD_ID}_pqr{index} subtract = global_var:{MOD_ID}_pqt{index} }}
\tif = {{
\t\tlimit = {{ global_var:{MOD_ID}_pqr{index} > global_var:{MOD_ID}_qscr }}
\t\tset_global_variable = {{ name = {MOD_ID}_pqr{index} value = global_var:{MOD_ID}_qscr }}
\t}}
\tchange_global_variable = {{ name = {MOD_ID}_pqr{index} max = 0 }}
"""
        for index in range(1, len(order) + 1))
    out.append(f"""
# How many buildings each good may claim before the ground is opened to all.
#
# **Две дележки, по одной на сторону.** Городские комнаты делятся между
# товарами, которые умеют встать в городе; сельские — между умеющими в селе.
# Товар, умеющий обе стороны, держит обе квоты и тратит их порознь.
#
# **Это заменило трёхклассовую долю, и та была костылём.** Классы «только
# город» / «только село» / «где угодно» понадобились ровно потому, что квота
# была одна на обе стороны; с двумя квотами класс товара перестаёт что-либо
# значить — он просто участвует в тех дележках, где может.
#
# **`max = 1` — пол, и он намеренный.** Земля, которой мало на всех, всё равно
# даёт каждому по домику; уступает лимит, а не разброс. Скидка за РГО
# вычитается из квоты той стороны, где эти РГО лежат.
# **И потолок каждого здания, за которое спорят несколько товаров.** Он равен
# общей доле и растёт вместе с ней: сухой круг поднимает и квоты товаров, и эти.
# Без него торговая деревня -- один слот на пять товаров -- встаёт впятеро чаще
# любого однотоварного домика, и на северной Германии встала 225 раз против 61 у
# всех остальных. Его слова, 2026-09-07: «я хочу, чтобы лесных деревень тоже было
# 60, как и каких-нибудь сельских суконщиков».
# Scope: country
{MOD_ID}_plan_set_quota = {{
	set_global_variable = {{ name = {MOD_ID}_qgt value = 0 }}
	set_global_variable = {{ name = {MOD_ID}_qgr value = 0 }}
{counts}
	# **Общая квота: сколько домиков товару положено всего.** Это и есть
	# равномерность, и она вернулась к простому делению всей земли на все
	# товары — к той самой, что была до 2026-09-06. Владелец, 2026-09-07:
	# «товары с дублем будут иметь повышенные лимиты относительно остальных».
	set_global_variable = {{ name = {MOD_ID}_plan_quota value = global_var:{MOD_ID}_plan_rooms }}
	if = {{
		limit = {{ global_var:{MOD_ID}_plan_scored > 0 }}
		change_global_variable = {{ name = {MOD_ID}_plan_quota divide = {MOD_ID}_plan_scored_value }}
	}}
	change_global_variable = {{ name = {MOD_ID}_plan_quota max = 1 }}
 — **выведенные заново из трёх растущих чисел**, а не
# подправленные на единицу.
#
# **Сухой круг раньше прибавлял единицу каждому потолку, и это размывало скидку
# за РГО.** Северная Германия, 2026-09-08: у прядильных 21 своё РГО, городской
# потолок на старте 15-21 = 0 — а к концу, после 35 сухих кругов, 35. Ноль
# держал их ровно до первого сухого круга, и в города они всё-таки влезли,
# втроём. Его вопрос: «с какого перепуга прядильные должны остаться в городах не
# на 0, а на 3». Ни с какого.
#
# Теперь сухой круг поднимает **три числа** — общую долю и две доли сторон, — и
# зовёт этот эффект; скидка за РГО вычитается из уже поднятого, то есть держит
# всю раздачу, а не первый круг.
# Scope: country

	# **Два потолка: сколько из общей квоты можно взять на каждой стороне.**
	# Они не добавляют товару домиков — они мешают одному выгрести дефицитную
	# сторону, из-за чего «15 стекла» и «15 текстиля» оказывались разными
	# планами под одним числом.
{shares}	{MOD_ID}_plan_set_caps = yes
}}

# Потолки каждого товара и каждого общего здания — **выведенные заново из трёх
# растущих чисел**, а не подправленные на единицу.
#
# **Сами три числа считает `{MOD_ID}_plan_set_quota` и растит сухой круг; здесь
# они только читаются.** Считать их тут было ошибкой на полдня: `_qcapt` и
# `_qcapr` пересчитывались из «комнаты ÷ товары» на каждом сухом круге и стирали
# его же прибавку, потолки сторон замерли на 15 и 37 при квоте 55, и раздача
# встала, заполнив землю на 79 % вместо 100 % (1087 домиков из 1380,
# 2026-09-08). **Пересчёт, который сбрасывает то, ради чего его зовут, — это
# всегда одна и та же ошибка.**
#
# **Сухой круг раньше прибавлял единицу каждому потолку, и это размывало скидку
# за РГО.** У прядильных 21 своё РГО, городской потолок на старте 15-21 = 0 — а
# к концу, после 35 сухих кругов, 35: ноль держал их ровно до первого сухого
# круга. Теперь скидка вычитается из уже поднятого и держит всю раздачу.
# Scope: country
{MOD_ID}_plan_set_caps = {{
{bquotas}{quota_lines}}}
""")

    # ---- the draft ---------------------------------------------------------
    #
    # **The band decides where, never how many, and that is the change of
    # 2026-09-07.** The ladder was five bands on the outside with the sweeps
    # running to exhaustion inside each pass, so a good whose best location paid
    # 800 took its whole share -- and then, in the open ladder, layer after layer
    # -- before a good whose best paid 300 was admitted at all. Measured on his
    # own ground, 48 locations: `dyes`, `incense`, `wine`, `books`, `cannons`,
    # `saltpeter`, `medicaments` and `fine_cloth` had **six places each and
    # finished with one**, while `cloth` finished with **fifteen**. Eight goods
    # of thirty-eight, and it was not the ground that stopped them.
    #
    # So the level moved outside everything: one lap raises `_plan_lvl` by one,
    # and `_pn<n> < _plan_lvl` lets a good add at most one building in that lap.
    # Inside the lap the ladder is what it always was -- the scarce tiers first,
    # five bands inside each, then everything -- so gain still says **which**
    # location and scarcity still says **who picks first**. Neither says how many.
    #
    # **This is what the owner meant by «план — это в первую очередь план»**,
    # 2026-09-07: a reservation map, where every good the ground can make has a
    # profitable place held for it, and demand decides only *when* it is built.
    # `docs/investigations/plan_as_reservation.md`.
    out.append(f"""
# The draft: a level a lap, and no good takes its second before every good that
# can has taken its first.
#
# **Coverage is lap one.** At `_plan_lvl = 1` the level gate is `_pn<n> = 0`,
# which is exactly what the covering pass used to test, and lap one runs every
# band down to 0 -- so a good the ground feeds nothing still takes a place.
#
# **The open ladder is a dry lap.** When a whole lap places nothing, every quota
# rises by one and the next lap tries again: the rooms left over after the share
# is spent are dealt in level layers like everything else. Two dry laps running
# mean the ground is full rather than the quota, and the draft stops.
#
# **`_plan_top` is why a dry lap does not stop the extension dead.** «Расширить»
# runs this over a plan that already stands, where every good holds several
# buildings, so the first laps cannot place anything at all -- the level has to
# climb past what is already there first. A lap only counts as dry once the level
# is above every count the draft started with.
# Scope: country
{MOD_ID}_plan_allocate = {{
\tset_global_variable = {{ name = {MOD_ID}_plan_lvl value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_plan_laps value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_plan_dry value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_plan_top value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_plan_go value = 1 }}
""")
    # **Каждый товар снова считается небезнадёжным, и оба флага снимаются
    # здесь.** `_px<side><n>` — «этому товару на этой стороне места кончились»;
    # он ставится, когда обход на полосе 0 не нашёл ничего, и его снятие обязано
    # жить в том же эффекте, что и раздача: `_plan_allocate` зовут оба пути --
    # план и доливка, -- а `_plan_prepare` зовёт только первый.
    for index, good in enumerate(order, start=1):
        for sfx in ("t", "r"):
            if not groups.get((good, sfx)):
                continue
            out.append(f"\tremove_global_variable = {MOD_ID}_px{sfx}{index}\n")
    for k in range(1, len(village_entities(rows, split, game)) + 1):
        out.append(f"\tremove_global_variable = {MOD_ID}_pxv{k}\n")
    # Самый крупный счёт, с которым раздача начинает. Свежий план приходит сюда
    # с тем, что раздали хартии; доливка -- со всем прошлым планом.
    for index in range(1, len(order) + 1):
        out.append(f"""\tif = {{
\t\tlimit = {{ global_var:{MOD_ID}_pn{index} > global_var:{MOD_ID}_plan_top }}
\t\tset_global_variable = {{ name = {MOD_ID}_plan_top value = global_var:{MOD_ID}_pn{index} }}
\t}}
""")
    out.append(f"""\twhile = {{
\t\tlimit = {{
\t\t\tglobal_var:{MOD_ID}_plan_go = 1
\t\t\tglobal_var:{MOD_ID}_plan_laps < {PLAN_LAPS}
\t\t}}
\t\tchange_global_variable = {{ name = {MOD_ID}_plan_laps add = 1 }}
\t\tchange_global_variable = {{ name = {MOD_ID}_plan_lvl add = 1 }}
\t\tchange_global_variable = {{ name = {MOD_ID}_plan_sweeps add = 1 }}
\t\tset_global_variable = {{ name = {MOD_ID}_plan_added value = 0 }}
""")
    for band, tier in PLAN_RUNGS:
        out.append(f"\t\t# {rung_name(band, tier)}\n"
                   f"\t\tset_global_variable = {{ name = {MOD_ID}_plan_band value = {band} }}\n")
        if tier:
            # Ступень как доля выбранной земли, с абсолютным полом.
            k = PLAN_TIERS.index(tier) + 1
            out.append(f"\t\tset_global_variable = {{ name = {MOD_ID}_plan_tier "
                       f"value = global_var:{MOD_ID}_candidate_count }}\n"
                       f"\t\tchange_global_variable = {{ name = {MOD_ID}_plan_tier "
                       f"divide = {MOD_ID}_tdiv{k} }}\n"
                       f"\t\tchange_global_variable = {{ name = {MOD_ID}_plan_tier "
                       f"max = {tier} }}\n")
        else:
            out.append(f"\t\tset_global_variable = {{ name = {MOD_ID}_plan_tier value = 0 }}\n")
        for index in range(1, len(order) + 1):
            out.append(f"\t\t{MOD_ID}_plan_pick_{index} = yes\n")
        for k in range(1, len(village_entities(rows, split, game)) + 1):
            out.append(f"\t\t{MOD_ID}_plan_pick_v{k} = yes\n")
    # Сколько положил каждый круг -- вся форма раздачи одним столбцом.
    lap_marks = "".join(
        f"\t\tif = {{ limit = {{ global_var:{MOD_ID}_plan_laps = {lap} }} "
        f"set_global_variable = {{ name = {MOD_ID}_lapn{lap} "
        f"value = global_var:{MOD_ID}_plan_added }} }}\n"
        for lap in range(1, DIAG_LAPS + 1))
    # **Сухой круг поднимает три числа и пересчитывает потолки.** Общая доля и
    # две доли сторон растут на единицу, а `_plan_set_caps` выводит из них всё
    # остальное заново — потолки товаров и потолки общих зданий. Прибавлять
    # единицу каждому потолку по отдельности было ошибкой: скидка за РГО
    # вычиталась один раз на старте и растворялась в тридцати пяти прибавках.
    # **И сухой круг снова поднимает долю — но уже только как страховка.**
    # Доля посчитана точно, но «ёмкость >= комнаты» не то же самое, что
    # «комнаты заполнятся»: локация держит по одному зданию каждого вида, и
    # спор за общее здание оставляет комнаты пустыми при любой доле. Сухой
    # круг поднимает обе доли на единицу и выводит потолки заново; если
    # прибавка ничего не дала, следующий круг тоже сухой и раздача кончается.
    # Прибавлять единицу каждому потолку по отдельности было ошибкой: скидка
    # за РГО вычиталась один раз на старте и растворялась в прибавках.
    raise_all = (
        f"\t\t\t\tremove_global_variable = {MOD_ID}_qrt\n"
        f"\t\t\t\tremove_global_variable = {MOD_ID}_qrr\n"
        f"\t\t\t\tif = {{\n"
        f"\t\t\t\t\tlimit = {{ global_var:{MOD_ID}_plan_pt < global_var:{MOD_ID}_prooms_t }}\n"
        f"\t\t\t\t\tchange_global_variable = {{ name = {MOD_ID}_qcapt add = 1 }}\n"
        f"\t\t\t\t\tset_global_variable = {{ name = {MOD_ID}_qrt value = 1 }}\n"
        f"\t\t\t\t}}\n"
        f"\t\t\t\tif = {{\n"
        f"\t\t\t\t\tlimit = {{ global_var:{MOD_ID}_plan_pr < global_var:{MOD_ID}_prooms_r }}\n"
        f"\t\t\t\t\tchange_global_variable = {{ name = {MOD_ID}_qcapr add = 1 }}\n"
        f"\t\t\t\t\tset_global_variable = {{ name = {MOD_ID}_qrr value = 1 }}\n"
        f"\t\t\t\t}}\n"
        f"\t\t\t\tchange_global_variable = {{ name = {MOD_ID}_plan_quota add = 1 }}\n"
        f"\t\t\t\t{MOD_ID}_plan_set_caps = yes\n")
    out.append(f"""{lap_marks}\t\tif = {{
\t\t\tlimit = {{
\t\t\t\tglobal_var:{MOD_ID}_plan_added = 0
\t\t\t\tglobal_var:{MOD_ID}_plan_lvl > global_var:{MOD_ID}_plan_top
\t\t\t}}
\t\t\t# **Сухой круг открывает квоту, и это вся бывшая открытая лестница.**
\t\t\t# Поднимается доля **той стороны, где ещё остались комнаты**, и только
\t\t\t# она: сторон две, и растить их вместе значит растить городскую долю
\t\t\t# ради сельских комнат. На северной Германии это давало городской
\t\t\t# потолок 20 там, где товар доходил до 18. `_plan_opensw` -- сколько
\t\t\t# раз поднимали.
\t\t\tchange_global_variable = {{ name = {MOD_ID}_plan_dry add = 1 }}
\t\t\tchange_global_variable = {{ name = {MOD_ID}_plan_opensw add = 1 }}
\t\t\t# **Второй сухой круг подряд не поднимает ничего** -- он тот, на
\t\t\t# котором раздача кончается. Прибавку первого, если она никому не
\t\t\t# досталась, отменяет блок ниже.
\t\t\tif = {{
\t\t\t\tlimit = {{ global_var:{MOD_ID}_plan_dry < 2 }}
{raise_all}\t\t\t}}
\t\t}}
\t\telse = {{ set_global_variable = {{ name = {MOD_ID}_plan_dry value = 0 }} }}
\t\tif = {{
\t\t\tlimit = {{ global_var:{MOD_ID}_plan_dry > 1 }}
\t\t\t# **Последняя прибавка отменяется, потому что она никому не досталась.**
\t\t\t# Раздача кончается двумя пустыми кругами подряд, а прибавку сделал
\t\t\t# первый из них — значит она заведомо не дала ни одного домика, и доля
\t\t\t# на экране оказывалась на единицу выше достижимой. Его слова,
\t\t\t# 2026-09-08: «недочёты или переборы по +1 −1 в каждой строке
\t\t\t# достаточно сильно мне не нравятся». Отменяем ровно её: всё, что
\t\t\t# поставлено, поставлено на предыдущем уровне доли.
\t\t\tchange_global_variable = {{ name = {MOD_ID}_plan_quota subtract = 1 }}
\t\t\tif = {{
\t\t\t\tlimit = {{ has_global_variable = {MOD_ID}_qrt }}
\t\t\t\tchange_global_variable = {{ name = {MOD_ID}_qcapt subtract = 1 }}
\t\t\t}}
\t\t\tif = {{
\t\t\t\tlimit = {{ has_global_variable = {MOD_ID}_qrr }}
\t\t\t\tchange_global_variable = {{ name = {MOD_ID}_qcapr subtract = 1 }}
\t\t\t}}
\t\t\tchange_global_variable = {{ name = {MOD_ID}_plan_opensw subtract = 1 }}
\t\t\t{MOD_ID}_plan_set_caps = yes
\t\t\tset_global_variable = {{ name = {MOD_ID}_plan_go value = 0 }}
\t\t}}
\t}}
}}
""")

    for index, good in enumerate(order, start=1):
        town_side = "town" if groups.get((good, "t")) else ""
        rural_side = "rural" if groups.get((good, "r")) else ""
        out.append(f"""
# {good} takes the one location each side of it suits best, or neither.
#
# `max = 1` on an ordered walk is the engine doing the choosing, which is the
# only reason a lap over {len(order)} goods twice is affordable. The tier gate above the
# walk holds a common good back while a scarce one is still picking; the level
# gate holds every good to one building a lap.
# Scope: country
{MOD_ID}_plan_pick_{index} = {{
""")
        for side, order_value, sfx in ((town_side, f"{MOD_ID}_ord{index}", "t"),
                                       (rural_side, f"{MOD_ID}_ordr{index}", "r")):
            if not side:
                continue
            out.append(f"""\tif = {{
\t\tlimit = {{
\t\t\t# **Ступень считает места этой стороны, а не обе разом.** Всё
\t\t\t# остальное в раздаче стороны различает -- два счётчика, две квоты,
\t\t\t# два потолка, -- и одни только ворота ступени складывали их в одно
\t\t\t# число. Северная Германия, 2026-09-07, показала, чего это стоит:
\t\t\t# `naval_supplies` умеет 178 локаций всего, но в сёлах только 42 --
\t\t\t# ровно столько же, сколько рыба, -- и по общему числу проходил как
\t\t\t# массовый товар, то есть выбирал побережье последним, наравне с
\t\t\t# теми, кому подходят все 416.
\t\t\tOR = {{
\t\t\t\tglobal_var:{MOD_ID}_plan_tier = 0
\t\t\t\tAND = {{
\t\t\t\t\tglobal_var:{MOD_ID}_ng{sfx}{index} > 0
\t\t\t\t\tglobal_var:{MOD_ID}_ng{sfx}{index} <= global_var:{MOD_ID}_plan_tier
\t\t\t\t}}
\t\t\t}}
\t\t\t# **Уровень: один домик за круг, и это вся равномерность.**
\t\t\t# Никакой товар не берёт второй, пока каждый, кто может, не взял
\t\t\t# первый. Полоса выгоды решает, в какую локацию и кто раньше внутри
\t\t\t# круга, -- но «сколько» она больше не решает, и восемь товаров с
\t\t\t# шестью местами каждый, кончивших план с одним домиком, -- это она.
\t\t\t#
\t\t\t# **Уровень считается по своей стороне, а не по обеим сразу.** Котла
\t\t\t# два, и ровность меряется в каждом отдельно; общий счётчик выбивал из
\t\t\t# городского круга того, кто уже набрал в селе. Соль, 2026-09-08: 42
\t\t\t# сельских домика разом (проход стеснённых) подняли её общий счёт выше
\t\t\t# уровня, и к тому кругу, когда уровень её догнал, городов не осталось
\t\t\t# ни одного — 0 при городском потолке 14.
\t\t\tglobal_var:{MOD_ID}_pn{sfx}{index} < global_var:{MOD_ID}_plan_lvl
\t\t\t# **Квота своей стороны, и она про сторону, а не про равномерность.**
\t\t\t# Городская комната и сельская не взаимозаменяемы, поэтому у товара
\t\t\t# два счётчика: городские домики сравниваются с городскими остальных,
\t\t\t# сельские — с сельскими. Один общий счётчик прятал ровно то, что
\t\t\t# владелец увидел: «15 стекла» из 13 сельских и 2 городских выглядели
\t\t\t# равными «15 текстиля» из 15 городских, а это разные планы.
\t\t\tglobal_var:{MOD_ID}_pn{index} < global_var:{MOD_ID}_pq{index}
\t\t\tglobal_var:{MOD_ID}_pn{sfx}{index} < global_var:{MOD_ID}_pq{sfx}{index}
\t\t\t# **Замороженный товар не берёт ничего, и квота его не спасёт.**
\t\t\t# «Расширить» ставит `_frz<n>` на закреплённые и на «не нужен»: их
\t\t\t# квота приравнена к тому, что у них есть, но сухой круг поднимает
\t\t\t# всякую квоту на единицу, и одного равенства хватило бы ровно на
\t\t\t# один круг. **Свежий план сюда не попадает**: `_frz<n>` ставит
\t\t\t# только доливка и снимает сама, а `_plan_prepare` снимает ещё раз --
\t\t\t# функция 3 не читает состояние редактора.
\t\t\tNOT = {{ has_global_variable = {MOD_ID}_frz{index} }}
\t\t\t# **Товар, которому места кончились, больше не ходит по земле.**
\t\t\t# Обход по кандидатам -- единственное, что в раздаче стоит дорого, и
\t\t\t# круг за кругом его повторял товар, у которого свободной подходящей
\t\t\t# локации нет вовсе. Флаг ставится ниже, перед обходом на полосе 0,
\t\t\t# и снимается самим обходом, если тот что-то нашёл: на полосе 0 порог
\t\t\t# не отсекает ничего, поэтому «не нашёл» там значит именно «мест
\t\t\t# нет», а комнаты по ходу плана только убывают.
\t\t\tNOT = {{ has_global_variable = {MOD_ID}_px{sfx}{index} }}
\t\t}}
\t\tif = {{
\t\t\tlimit = {{ global_var:{MOD_ID}_plan_band = 0 }}
\t\t\tset_global_variable = {{ name = {MOD_ID}_px{sfx}{index} value = 1 }}
\t\t}}
\t\tordered_in_global_list = {{
\t\t\tvariable = {MOD_ID}_candidates
\t\t\t# **The threshold, and it is the whole of the optimum.** The ground
\t\t\t# is dealt in descending order of gain across every good at once, so
\t\t\t# by the time a good that would gain a tenth reaches a location, the
\t\t\t# good that would have gained nine tenths has already taken it. That is
\t\t\t# the opportunity cost, paid for by one comparison rather than by
\t\t\t# asking every other good what it would have made of the place.
\t\t\t#
\t\t\t# **`_plan_band` itself, and no longer a threshold per good.** There
\t\t\t# were two: the band for the fair share and each good's own best for
\t\t\t# the open ladder, because on a realm-sized ground the quota never
\t\t\t# bound and the band became the whole allocator. The level binds
\t\t\t# instead now, on every ground and from the first lap, so the second
\t\t\t# threshold has nothing left to fix -- and a good whose best pays 300
\t\t\t# simply places at band 200 of the same lap.
\t\t\tlimit = {{
\t\t\t\t{MOD_ID}_plan_can_{side}_{index} = yes
\t\t\t\t{order_value} >= global_var:{MOD_ID}_plan_band
\t\t\t}}
\t\t\torder_by = {order_value}
\t\t\tmax = 1
\t\t\tcheck_range_bounds = no
\t\t\tremove_global_variable = {MOD_ID}_px{sfx}{index}
\t\t\t{MOD_ID}_plan_try_{side}_{index} = yes
\t\t}}
\t}}
""")
        out.append("}\n")

    # **Итог на товар: домики плюс уже стоящие РГО.** Ровно то число, по
    # которому владелец судит о равномерности, и оно должно быть готовым, а не
    # складываться в голове.
    # **И сколько товар не добрал до своего потолка.** Комнат на стороне ровно
    # столько, сколько есть, и на все потолки их не хватает: 544 городских
    # потолка на 528 комнат. Товар, оставшийся на единицу ниже, не должен
    # выглядеть как товар, который свой потолок выбрал. Его слова, 2026-09-09:
    # «нельзя чтобы это терялось информационо. Пусть в таблице это отмечается
    # прямо так в общем лимите "15-1"».
    totals = "".join(
        f"\tset_global_variable = {{ name = {MOD_ID}_tot{i} "
        f"value = global_var:{MOD_ID}_pn{i} }}\n"
        f"\tchange_global_variable = {{ name = {MOD_ID}_tot{i} "
        f"add = global_var:{MOD_ID}_nrgo{i} }}\n"
        f"\tset_global_variable = {{ name = {MOD_ID}_short{i} "
        f"value = global_var:{MOD_ID}_pq{i} }}\n"
        f"\tchange_global_variable = {{ name = {MOD_ID}_short{i} "
        f"subtract = global_var:{MOD_ID}_pn{i} }}\n"
        f"\tchange_global_variable = {{ name = {MOD_ID}_short{i} max = 0 }}\n"
        for i in range(1, len(order) + 1))
    # ---- деревня ходит в круге сама ---------------------------------------
    shared_all = shared_buildings(rows, split, game)
    for k, building in enumerate(village_entities(rows, split, game), start=1):
        b = shared_all.index(building) + 1
        makes = [i for i, g in enumerate(order, start=1)
                 if building in (groups.get((g, "r")) or {})]
        places = "".join(f"""\t\t\tif = {{
\t\t\t\tlimit = {{ var:{MOD_ID}_vw{k} = {i} }}
\t\t\t\t# **Товар кладётся только ради строки локации.** `_plan_goods` и
\t\t\t\t# `_plan_builds` обязаны идти в ногу (`ROWPAIR`), и на карте видно,
\t\t\t\t# что деревня делает. В счёт он не идёт нигде: ни `_pn`, ни `_pnr`,
\t\t\t\t# ни `_pout`. «Оно ничего не производит кроме самого себя.»
\t\t\t\tadd_to_variable_list = {{ name = {MOD_ID}_plan_goods target = goods:{order[i - 1]} }}
\t\t\t}}
""" for i in makes)
        out.append(f"""
# {building} как сущность круга: одна за круг, своя доля, своя ступень.
#
# **Товару её домик не засчитывается.** `_pn`/`_pnr` не растут -- деревня стоит
# в счёте сама, `_bn{b}`, и это то, о чём он просил полсотни раз: «убрать все
# деревенские доли товаров и заменить их просто на торговая деревня = 1
# уникальный товар».
# Scope: location
{MOD_ID}_plan_try_village_{k} = {{
\tif = {{
\t\tlimit = {{ {MOD_ID}_plan_can_village_{k} = yes }}
\t\tadd_to_variable_list = {{ name = {MOD_ID}_plan_builds target = building_type:{building} }}
\t\tchange_variable = {{ name = {MOD_ID}_load add = 1 }}
\t\tchange_global_variable = {{ name = {MOD_ID}_plan_placed add = 1 }}
\t\tchange_global_variable = {{ name = {MOD_ID}_plan_added add = 1 }}
\t\tchange_global_variable = {{ name = {MOD_ID}_plan_pr add = 1 }}
\t\tchange_global_variable = {{ name = {MOD_ID}_bn{b} add = 1 }}
\t\tchange_global_variable = {{ name = {MOD_ID}_plan_gain add = var:{MOD_ID}_vb{k} }}
\t\tif = {{
\t\t\tlimit = {{ var:{MOD_ID}_vb{k} > 0 }}
\t\t\tchange_global_variable = {{ name = {MOD_ID}_plan_fed add = 1 }}
\t\t}}
{places}\t}}
}}

# Scope: country
{MOD_ID}_plan_pick_v{k} = {{
\tif = {{
\t\tlimit = {{
\t\t\tOR = {{
\t\t\t\tglobal_var:{MOD_ID}_plan_tier = 0
\t\t\t\tAND = {{
\t\t\t\t\tglobal_var:{MOD_ID}_ngv{k} > 0
\t\t\t\t\tglobal_var:{MOD_ID}_ngv{k} <= global_var:{MOD_ID}_plan_tier
\t\t\t\t}}
\t\t\t}}
\t\t\tglobal_var:{MOD_ID}_bn{b} < global_var:{MOD_ID}_plan_lvl
\t\t\tglobal_var:{MOD_ID}_bn{b} < global_var:{MOD_ID}_bq{b}
\t\t\tNOT = {{ has_global_variable = {MOD_ID}_pxv{k} }}
\t\t}}
\t\tif = {{
\t\t\tlimit = {{
\t\t\t\tglobal_var:{MOD_ID}_plan_band = 0
\t\t\t\tglobal_var:{MOD_ID}_plan_tier = 0
\t\t\t}}
\t\t\tset_global_variable = {{ name = {MOD_ID}_pxv{k} value = 1 }}
\t\t}}
\t\tordered_in_global_list = {{
\t\t\tvariable = {MOD_ID}_candidates
\t\t\tlimit = {{
\t\t\t\t{MOD_ID}_plan_can_village_{k} = yes
\t\t\t\t{MOD_ID}_ordv{k} >= global_var:{MOD_ID}_plan_band
\t\t\t}}
\t\t\torder_by = {MOD_ID}_ordv{k}
\t\t\tmax = 1
\t\t\tcheck_range_bounds = no
\t\t\tremove_global_variable = {MOD_ID}_pxv{k}
\t\t\t{MOD_ID}_plan_try_village_{k} = yes
\t\t}}
\t}}
}}
""")

    # ---- стеснённые берут своё до круга ------------------------------------
    #
    # **Его правило, 2026-09-08:** «я не вижу причин, почему железо не может
    # забрать первым все свои 43 ячейки, потом следующий чуть менее дефицитный
    # товар, а потом уже все остальные как угодно».
    #
    # **Стеснённый — тот, чьей земли меньше его же доли до скидки за РГО.**
    # Делить ему нечего: круг может только отнять у него места, которые некому
    # заменить. Железо, 2026-09-08: 43 локации, доля 60, а по кругу оно брало
    # 34 — восемь городов и две деревни успевали забиться, пока подходила его
    # очередь.
    #
    # **Порядок — по ступеням, от самых стеснённых.** Тот же `_plan_tier`, что
    # в круге: сперва товары, которым годится 2 % земли, потом 4 % и так далее.
    # Внутри ступени обход ставит домик **в каждую** подходящую локацию разом —
    # локация держит один домик товара, так что один проход и есть «забрать всё
    # своё».
    #
    # **Ни уровня, ни доли здесь нет.** Стеснённый по определению не дотянет до
    # своей доли, а уровень нужен, чтобы товары не обгоняли друг друга — тут
    # обгонять некого.
    out.append(f"""
# Стеснённые товары забирают свою землю целиком, до равного круга.
# Scope: country
{MOD_ID}_plan_place_scarce = {{
""")
    for tier in PLAN_TIERS:
        t = PLAN_TIERS.index(tier) + 1
        out.append(f"\tset_global_variable = {{ name = {MOD_ID}_plan_tier "
                   f"value = global_var:{MOD_ID}_candidate_count }}\n"
                   f"\tchange_global_variable = {{ name = {MOD_ID}_plan_tier "
                   f"divide = {MOD_ID}_tdiv{t} }}\n"
                   f"\tchange_global_variable = {{ name = {MOD_ID}_plan_tier "
                   f"max = {tier} }}\n")
        for index, good in enumerate(order, start=1):
            for side, listname, sfx in (("t", "town", "t"), ("r", "rural", "r")):
                if not groups.get((good, side)):
                    continue
                out.append(f"""\tif = {{
\t\tlimit = {{
\t\t\tglobal_var:{MOD_ID}_ng{sfx}{index} > 0
\t\t\tNOT = {{ global_var:{MOD_ID}_ng{sfx}{index} > global_var:{MOD_ID}_pq{sfx}{index} }}
\t\t\tglobal_var:{MOD_ID}_ng{sfx}{index} <= global_var:{MOD_ID}_plan_tier
\t\t}}
\t\t# **Проход стеснённых тоже держит квоту.** Он ставил домик в **каждую**
\t\t# подходящую локацию и не спрашивал ничего: камень, стеснённый с обеих
\t\t# сторон, взял 20 городов и 53 села — 73 домика при квоте 62 и 88 «с РГО»
\t\t# против 75 у всех (2026-09-08). `limit` пересчитывается на каждой
\t\t# локации, так что счётчик, растущий по ходу обхода, его и останавливает.
\t\tevery_in_global_list = {{
\t\t\tvariable = {MOD_ID}_candidates
\t\t\tlimit = {{
\t\t\t\t{MOD_ID}_plan_can_{listname}_{index} = yes
\t\t\t\tglobal_var:{MOD_ID}_pn{index} < global_var:{MOD_ID}_pq{index}
\t\t\t\tglobal_var:{MOD_ID}_pn{sfx}{index} < global_var:{MOD_ID}_pq{sfx}{index}
\t\t\t}}
\t\t\t{MOD_ID}_plan_try_{listname}_{index} = yes
\t\t}}
\t}}
""")
    for k, building in enumerate(village_entities(rows, split, game), start=1):
        b = shared_buildings(rows, split, game).index(building) + 1
        out.append(f"""\tif = {{
\t\tlimit = {{
\t\t\tglobal_var:{MOD_ID}_ngv{k} > 0
\t\t\tNOT = {{ global_var:{MOD_ID}_ngv{k} > global_var:{MOD_ID}_qcapr }}
\t\t}}
\t\tevery_in_global_list = {{
\t\t\tvariable = {MOD_ID}_candidates
\t\t\tlimit = {{
\t\t\t\t{MOD_ID}_plan_can_village_{k} = yes
\t\t\t\tglobal_var:{MOD_ID}_bn{b} < global_var:{MOD_ID}_bq{b}
\t\t\t}}
\t\t\t{MOD_ID}_plan_try_village_{k} = yes
\t\t}}
\t}}
""")
    out.append("}\n")

    out.append(f"""
# The rows: one per location that got anything, its province's locations together.
#
# **Provinces are ranked first and their locations follow.** A sort on the
# location's own load ties nearly all of them and `ordered_in_global_list`
# promises nothing about ties, so two provinces would interleave. The provinces
# are put in order by how much the plan put in each, every location is told its
# province's place, and the rows sort on that with a province's towns ahead of
# its villages.
#
# A province's load is added up through a global, because a walk over its
# locations cannot write back to the scope that started it.
# Scope: country
{MOD_ID}_plan_rank = {{
	# **The rows first, and from here rather than from each caller.** Everything
	# that changes the plan ranks it afterwards -- the plan itself, a slot load,
	# «+1», «−1» -- so one call here is the whole of it, and no path can forget.
	{MOD_ID}_plan_rows = yes
	# **И итог «домиков плюс РГО» на каждый товар, потому что смотреть на него
	# приходится в каждом разборе.** Владелец, 2026-09-07: «почему я должен
	# смотреть на цифры аля 13 и думать, а сколько там РГО к этому. Показывай
	# сразу со счётчиком РГО, чтобы оно складывалось в адекватные цифры».
	# Считается здесь по той же причине, что и строки: сюда приходит всё, что
	# меняет план, и забыть этот путь нельзя.
	#
	# **Отдельным глобалом, а не суммой в `script_value`.** Многочленный
	# `script_value` в этом моде нигде не доказан, а `change_global_variable`
	# доказан везде; число, которое молча читается нулём, хуже отсутствующего.
{totals}
\tevery_in_global_list = {{
\t\tvariable = {MOD_ID}_plan_prov_locs
\t\tset_global_variable = {{ name = {MOD_ID}_plan_count value = 0 }}
\t\tprovince_definition = {{
\t\t\tevery_location_in_province_definition = {{
\t\t\t\tlimit = {{ has_variable = {MOD_ID}_load }}
\t\t\t\tchange_global_variable = {{ name = {MOD_ID}_plan_count add = var:{MOD_ID}_load }}
\t\t\t}}
\t\t}}
\t\tset_variable = {{ name = {MOD_ID}_plan_prov_load value = global_var:{MOD_ID}_plan_count }}
\t\t# **And how many of its locations the plan uses**, for the province row
\t\t# of the folded list. Counted in the walk that is already standing in
\t\t# the province rather than in a second one.
\t\tset_global_variable = {{ name = {MOD_ID}_plan_count value = 0 }}
\t\tprovince_definition = {{
\t\t\tevery_location_in_province_definition = {{
\t\t\t\tlimit = {{ has_variable = {MOD_ID}_load var:{MOD_ID}_load > 0 }}
\t\t\t\tchange_global_variable = {{ name = {MOD_ID}_plan_count add = 1 }}
\t\t\t}}
\t\t}}
\t\tset_variable = {{ name = {MOD_ID}_plan_prov_locn value = global_var:{MOD_ID}_plan_count }}
\t}}
	# **Области сперва, провинции внутри области — и это одно место, а не два.**
	# Его слова 2026-09-06: «провинции должны идти по списку внутри своих
	# областей… я не хочу, чтобы провинции разных областей были в перемешку».
	# Порядок один на оба вида списка: `_plan_prank` несёт его целиком, и плоский
	# список читает то же число, что свёрнутый.
	#
	# **Без упаковки двух ключей в одно число.** Область и загрузка провинции
	# влезли бы в одно `order_by`, но предел фиксированной точки движка отсюда
	# неизвестен — предупреждение об этом уже стоит при `_plan_order`. Вместо
	# этого обход внутри обхода: области по своей загрузке, внутри каждой
	# провинции по своей, и номер выдаётся по ходу.
	set_global_variable = {{ name = {MOD_ID}_plan_area_load value = 0 }}
	clear_global_variable_list = {MOD_ID}_plan_area_locs
	every_in_global_list = {{
		variable = {MOD_ID}_plan_prov_locs
		save_scope_as = {MOD_ID}_plan_prov_at
		# **«Эту область уже видели?» -- через глобалку, потому что внутренний обход
		# не может писать в скоуп, из которого его позвали.** Список областей короток
		# (у него шестнадцать провинций на пять областей), так что квадрат здесь
		# дешевле любого хитрого способа.
		set_global_variable = {{ name = {MOD_ID}_plan_aseen value = 0 }}
		every_in_global_list = {{
			variable = {MOD_ID}_plan_area_locs
			limit = {{ area = scope:{MOD_ID}_plan_prov_at.area }}
			set_global_variable = {{ name = {MOD_ID}_plan_aseen value = 1 }}
		}}
		if = {{
			limit = {{ global_var:{MOD_ID}_plan_aseen = 0 }}
			add_to_global_variable_list = {{ name = {MOD_ID}_plan_area_locs target = this }}
		}}
	}}
	# Сколько домиков во всей области -- по этому числу области и встанут.
	every_in_global_list = {{
		variable = {MOD_ID}_plan_area_locs
		save_scope_as = {MOD_ID}_plan_area_at
		set_global_variable = {{ name = {MOD_ID}_plan_count value = 0 }}
		every_in_global_list = {{
			variable = {MOD_ID}_plan_prov_locs
			limit = {{ area = scope:{MOD_ID}_plan_area_at.area }}
			change_global_variable = {{ name = {MOD_ID}_plan_count add = var:{MOD_ID}_plan_prov_load }}
		}}
		set_variable = {{ name = {MOD_ID}_plan_area_load value = global_var:{MOD_ID}_plan_count }}
	}}
	set_global_variable = {{ name = {MOD_ID}_plan_prov_n value = 0 }}
	ordered_in_global_list = {{
		variable = {MOD_ID}_plan_area_locs
		order_by = {MOD_ID}_plan_area_order
		max = {PLAN_PROVS}
		check_range_bounds = no
		save_scope_as = {MOD_ID}_plan_area_at
		ordered_in_global_list = {{
			variable = {MOD_ID}_plan_prov_locs
			limit = {{ area = scope:{MOD_ID}_plan_area_at.area }}
			order_by = {MOD_ID}_plan_prov_order
			max = {PLAN_PROVS}
			check_range_bounds = no
			change_global_variable = {{ name = {MOD_ID}_plan_prov_n add = 1 }}
			province_definition = {{
				every_location_in_province_definition = {{
					limit = {{ has_variable = {MOD_ID}_plan_prank }}
					set_variable = {{ name = {MOD_ID}_plan_prank value = global_var:{MOD_ID}_plan_prov_n }}
				}}
			}}
		}}
	}}
\t# Counted before the rows are taken and separately from them: the walk below
\t# stops at {PLAN_RANKED}, and a count that stopped with it would say the plan
\t# used exactly as many locations as the window can keep, whatever it really
\t# used.
\t#
\t# **And it walks `_plan_touched`, not `_candidates`.** The two are the same
\t# list for a plan just run -- the reset puts every candidate in it -- but a slot
\t# loaded from the editor puts a plan back on ground the picker may no longer
\t# hold, and walking the picker would then rank nothing while the map mode
\t# painted the plan. A plan is ranked over the ground it stands on.
\tset_global_variable = {{ name = {MOD_ID}_plan_found value = 0 }}
\tevery_in_global_list = {{
\t\tvariable = {MOD_ID}_plan_touched
\t\tlimit = {{ var:{MOD_ID}_load > 0 }}
\t\tchange_global_variable = {{ name = {MOD_ID}_plan_found add = 1 }}
\t}}
\t# **The rows are ranked whole and drawn a page at a time.** The datamodel is
\t# what costs, so the window still holds {PLAN_ROWS} rows at once -- but the plan
\t# has always used more ground than that, and cutting the list at the window's
\t# capacity is what made «показано всего 150 локаций» look like the answer
\t# stopping short. Every location keeps its place in the whole order and the page
\t# it falls on; the page buttons choose which of them the datamodel gets.
\t#
\t# The page is counted here rather than divided out afterwards: the counter is
\t# reset and the page stepped whenever a page fills, so the comparison is against
\t# a literal and there is no rounding to be wrong about.
\tset_global_variable = {{ name = {MOD_ID}_plan_shown value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_plan_pages value = 1 }}
\tset_global_variable = {{ name = {MOD_ID}_plan_pagec value = 0 }}
\tordered_in_global_list = {{
\t\tvariable = {MOD_ID}_plan_touched
\t\t# **Житница остаётся в списке.** Его слово, 2026-09-09: «не удаляй из
\t\t# списка в плане локацию которая помечена как житница, я ожидаю, что в
\t\t# плане она будет просто помечена значком житницы и просто не будет
\t\t# указано никаких своих зданий». Домиков у неё ноль, и без этой оговорки
\t\t# ряд бы не выпал -- он бы просто не появился.
\t\tlimit = {{
\t\t\tOR = {{
\t\t\t\tvar:{MOD_ID}_load > 0
\t\t\t\t{MOD_ID}_is_granary = yes
\t\t\t}}
\t\t}}
\t\torder_by = {MOD_ID}_plan_order
\t\tmax = {PLAN_RANKED}
\t\tcheck_range_bounds = no
\t\tchange_global_variable = {{ name = {MOD_ID}_plan_shown add = 1 }}
\t\tchange_global_variable = {{ name = {MOD_ID}_plan_pagec add = 1 }}
\t\tif = {{
\t\t\tlimit = {{ global_var:{MOD_ID}_plan_pagec > {PLAN_ROWS} }}
\t\t\tset_global_variable = {{ name = {MOD_ID}_plan_pagec value = 1 }}
\t\t\tchange_global_variable = {{ name = {MOD_ID}_plan_pages add = 1 }}
\t\t}}
\t\tset_variable = {{ name = {MOD_ID}_plan_rank value = global_var:{MOD_ID}_plan_shown }}
\t\tset_variable = {{ name = {MOD_ID}_plan_pg value = global_var:{MOD_ID}_plan_pages }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_plan_ranked target = this }}
\t}}
\t# A new plan always opens on its first page; the old one's page may not exist.
\tset_global_variable = {{ name = {MOD_ID}_plan_page value = 1 }}
}}

# The window's own list, filled on opening and emptied on closing -- the same
# contract as the other two windows and for the same reason: a scripted widget
# never comes down, so emptying the datamodel is the only thing that frees a row.
#
# **One page of it, and the page bar says which.** `_plan_pg` was written on the
# location by the walk above, so choosing a page is one comparison per ranked
# location and no arithmetic at all -- the same shape as `var:{MOD_ID}_load <
# global_var:{MOD_ID}_plan_cap_urban`, which is the plan's own gate.
# Scope: country
{MOD_ID}_plan_show = {{
\tif = {{
\t\tlimit = {{ NOT = {{ has_global_variable = {MOD_ID}_plan_page }} }}
\t\tset_global_variable = {{ name = {MOD_ID}_plan_page value = 1 }}
\t}}
\tif = {{
\t\tlimit = {{ NOT = {{ has_global_variable = {MOD_ID}_plan_pages }} }}
\t\tset_global_variable = {{ name = {MOD_ID}_plan_pages value = 1 }}
\t}}
\t# **Clamped with an `if` and not with `min`/`max`.** `change_variable`'s
\t# `max = 1` is a floor -- `_plan_quota` above depends on it and says so -- but
\t# which way `min` runs is an inference and not a measurement, and getting it
\t# backwards here would jump the window to the last page on every open with
\t# nothing in any log to say why. A comparison between two globals is the form
\t# this file already lives on.
\tif = {{
\t\tlimit = {{ global_var:{MOD_ID}_plan_page < 1 }}
\t\tset_global_variable = {{ name = {MOD_ID}_plan_page value = 1 }}
\t}}
\tif = {{
\t\tlimit = {{ global_var:{MOD_ID}_plan_page > global_var:{MOD_ID}_plan_pages }}
\t\tset_global_variable = {{ name = {MOD_ID}_plan_page value = global_var:{MOD_ID}_plan_pages }}
\t}}
\t# The rows this page covers, for the bar above the table: it is the answer to
\t# «показано 150 из скольких» and it has to be readable without a log.
\tset_global_variable = {{ name = {MOD_ID}_plan_from value = global_var:{MOD_ID}_plan_page }}
\tchange_global_variable = {{ name = {MOD_ID}_plan_from subtract = 1 }}
\tchange_global_variable = {{ name = {MOD_ID}_plan_from multiply = {PLAN_ROWS} }}
\tset_global_variable = {{ name = {MOD_ID}_plan_to value = global_var:{MOD_ID}_plan_from }}
\tchange_global_variable = {{ name = {MOD_ID}_plan_to add = {PLAN_ROWS} }}
\tif = {{
\t\tlimit = {{ global_var:{MOD_ID}_plan_to > global_var:{MOD_ID}_plan_shown }}
\t\tset_global_variable = {{ name = {MOD_ID}_plan_to value = global_var:{MOD_ID}_plan_shown }}
\t}}
\tchange_global_variable = {{ name = {MOD_ID}_plan_from add = 1 }}
\t# The bar itself is only drawn where there is more than one page, and a country
\t# variable is the one thing a `visible` can ask about without a data function.
\tif = {{
\t\tlimit = {{ global_var:{MOD_ID}_plan_pages > 1 }}
\t\tset_variable = {{ name = {MOD_ID}_plan_paged value = 1 }}
\t}}
\telse = {{
\t\tremove_variable = {MOD_ID}_plan_paged
\t}}
	# **The folded list, and it is a second list rather than a second shape for
	# the first.** A datamodel item sees one scope, so a province row and a
	# location row cannot be the same row -- and the flat list is what he has
	# been reading since the plan existed, so it stays untouched and the fold is
	# a switch beside it.
	#
	# One representative location a province (`_plan_prov_locs` already holds
	# exactly that), ordered by the province's own place, and the province's
	# locations are drawn under it from `GetProvinceDefinition.GetLocations` --
	# the same nesting the search window has used since it was built.
	set_global_variable = {{ name = {MOD_ID}_plan_provfill value = 0 }}
	set_global_variable = {{ name = {MOD_ID}_plan_provshown value = 0 }}
	clear_global_variable_list = {MOD_ID}_plan_provs
	every_in_global_list = {{
		variable = {MOD_ID}_plan_prov_locs
		limit = {{ has_variable = {MOD_ID}_plan_prov_locn var:{MOD_ID}_plan_prov_locn > 0 }}
		change_global_variable = {{ name = {MOD_ID}_plan_provfill add = 1 }}
	}}
	ordered_in_global_list = {{
		variable = {MOD_ID}_plan_prov_locs
		limit = {{ has_variable = {MOD_ID}_plan_prov_locn var:{MOD_ID}_plan_prov_locn > 0 }}
		order_by = {MOD_ID}_plan_pseq_order
		max = {PLAN_ROWS}
		check_range_bounds = no
		change_global_variable = {{ name = {MOD_ID}_plan_provshown add = 1 }}
		add_to_global_variable_list = {{ name = {MOD_ID}_plan_provs target = this }}
	}}
\tclear_global_variable_list = {MOD_ID}_plan_results
\tordered_in_global_list = {{
\t\tvariable = {MOD_ID}_plan_ranked
\t\tlimit = {{ var:{MOD_ID}_plan_pg = global_var:{MOD_ID}_plan_page }}
\t\torder_by = {MOD_ID}_plan_rank_order
\t\tmax = {PLAN_ROWS}
\t\tcheck_range_bounds = no
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_plan_results target = this }}
\t}}
}}

# One page forward and one back, from the two buttons beside the page number.
# **Neither re-plans anything**: the answer is already ranked and every location
# knows its page, so a page turn is one walk over the ranked list.
# Scope: country
{MOD_ID}_plan_page_next_effect = {{
\tif = {{
\t\tlimit = {{ global_var:{MOD_ID}_plan_page < global_var:{MOD_ID}_plan_pages }}
\t\tchange_global_variable = {{ name = {MOD_ID}_plan_page add = 1 }}
\t\t{MOD_ID}_plan_show = yes
\t}}
}}

# Scope: country
{MOD_ID}_plan_page_prev_effect = {{
\tif = {{
\t\tlimit = {{ global_var:{MOD_ID}_plan_page > 1 }}
\t\tchange_global_variable = {{ name = {MOD_ID}_plan_page subtract = 1 }}
\t\t{MOD_ID}_plan_show = yes
\t}}
}}

# Scope: country
{MOD_ID}_plan_hide = {{
\tclear_global_variable_list = {MOD_ID}_plan_results
\tclear_global_variable_list = {MOD_ID}_plan_provs
\t# **Сводка уходит вместе с планом, который её породил.** Она открывается
\t# иконкой из окна плана и отвечает про этот план; оставшись висеть после
\t# того, как окно закрыли, она отвечала бы про него же, но выглядела бы как
\t# ответ про то, что на экране сейчас.
\tremove_variable = {MOD_ID}_sum_open
}}

# The same thing the window's own scripted GUI does, reachable from an effect,
# because a Mod Menu button is script and script cannot reach the interface's
# variable system.
# Scope: country
{MOD_ID}_open_plan_window_effect = {{
\t{MOD_ID}_sel_restore_plan = yes
\t{MOD_ID}_plan_show = yes
\t# **Галочки CM он мог трогать и сам**, по одной в панели локации, поэтому
\t# подсветка кнопок отмашки пересчитывается на каждом открытии окна, а не
\t# только после своего же нажатия.
\t{MOD_ID}_cm_light = yes
\t# **А без CM на том же месте считается другое**: чего плану на этой земле не
\t# хватает и во что обойдётся построить это первым ярусом. Считается здесь, на
\t# открытии, потому что подсказка обязана знать число до нажатия.
\t{MOD_ID}_b1_scan = yes
\tremove_variable = {MOD_ID}_result_open
\tremove_variable = {MOD_ID}_right_open
\t{MOD_ID}_hide_results = yes
\tset_variable = {{ name = {MOD_ID}_plan_open value = 1 }}
}}
""")
    return "".join(out)


# **How many plans the mod keeps.** Three at the least, and the reason is his:
# «Т.е. ты говоришь, что я проебу свой сохранённый план, если захочу посмотреть
# какой-то план на другой земле - спасибо. … Слотов для планов должно быть
# минимум 3.» A slot is a global list of locations plus one list of goods on each
# of them, so the cost is per slot and per location the plan touched, and nothing
# at all for a slot never written.
# **Продовольственное сырьё -- список Construction Manager, прочитанный у него.**
# Он решает, каким локациям CM вообще предлагает режим житницы; наша кнопка
# должна стоять ровно там же.
FOOD_GOODS = ['beeswax', 'fish', 'fruit', 'fur', 'legumes', 'livestock', 'maize', 'millet', 'olives', 'potato', 'rice', 'wheat', 'wild_game']

EDIT_SLOTS = 3

# **The picker is rows, and the rows are cut here.** Ten cells of 104 plus their
# spacing is 1060 of the 1130 the window has; five rows hold the 47 goods this
# game has, and a ground that makes fewer simply leaves the last rows empty.
# Both wrapping widgets that would have made this one list are gone:
# `flowcontainer` crashed the game and `fixedgridbox` drew the cells on top of
# one another. `docs/pitfalls/interface.md`.
EDIT_ROW = 10
# **Сколько рядов -- считается, а не написано.** Было пять под 47 товаров; с
# 2026-09-13 в той же сетке стоят и три универсальные деревни, а мод чужих
# модов может принести ещё: «таких домиков может быть очень много в модах,
# поэтому нужно учитывать это». Ряд добавляется сам.
def edit_rows(n: int) -> int:
    return max(1, -(-n // EDIT_ROW))
# The picker's cell, in one place: «−1», the count, «+1», «не нужен», and the
# gap between two goods. `CELL_GAP` is what keeps one good's buttons off the
# next good's; the window is sized from these, and `check_script.py` measures
# the result against it on every build.
CELL_W, CELL_H, CELL_GAP = 127, 28, 14


# The picker's cells, generated into a `.gui` of types only.
#
# **A datamodel row cannot reach a numbered counter.** `_pn<n>` is how many
# buildings of a good the plan holds, and a row of a goods datamodel carries a
# scope: `Goods.Custom` does not exist, no global returns a good by key, and a
# variable map crashes the game. So the cell that has to print a number cannot
# be a datamodel row -- it has to be written out, one a good, which is what this
# does. `docs/pitfalls/interface.md`.
#
# **And writing them out removes the scope bridge as well.** A datamodel cell
# reached its effect through `AddScope('bag_wtp_good', Goods.MakeScope)`; a
# written cell calls `bag_wtp_pick_plus_<n>`, which knows its own number. One
# fewer thing between the press and the plan.
#
# Types live in their own file because `.gui` types are global once parsed --
# vanilla keeps its own in `gui/shared/` the same way -- and a file with no
# `window` in it needs no line in `scripted_widgets`.
EDIT_CELLS_OUT = MOD / "in_game/gui/bag_wtp_edit_cells.gui"


# **The charter cell is bigger than a good's**, and he asked for it after seeing
# it on screen: «текст городских прав можно попытаться увеличить… было бы неплохо
# увеличить шрифт и иконки слегка». The icon is a texticon inside the name's own
# key, so it grows with the font and nothing else has to change.
# **Пять колонок по три, а не три по пять**, и высота блока — ровно три строки.
# Его слова 2026-09-06: «инструментарий занимает половину окна… вместо 4 строк они
# вполне могли бы уместиться в 2 строки по всей ширине». Держава выдаёт девять или
# десять грамот из тринадцати, невидимая ячейка в колонке места не занимает — так
# что на его земле пять колонок дают две строки, а на полных тринадцати три.
EDIT_RIGHT_W = 264
EDIT_RIGHT_H = 32
EDIT_RIGHT_ROW = 5


def edit_cells_file(order: list[str],
                    rights: list[eu5data.TownRight],
                    villages_pick: list[str] = ()) -> str:
    """Five rows of ten cells: «−1», the good's icon with its count, «+1».

    **All 47, not the ground's 38.** Every cell is a static child of a plain `hbox`. Both widgets that would
    have wrapped one list -- `flowcontainer`, `fixedgridbox` -- failed on their
    first load, one by crashing the game four builds running and one by drawing
    the cells on top of each other. `ignoreinvisible` keeps the goods this ground
    cannot make from leaving holes.

    **Every cell keeps its column, whether or not this ground can make the good.**
    The row used to carry `ignoreinvisible = yes` and the cell its own `visible`,
    so 35 goods of 47 drew as five ragged centred rows of different lengths --
    «на каждой строке их разное количество… они должны быть ровненькими по
    столбикам», his words on 2026-09-05. Now the cell is always there and its
    four controls answer for themselves, so an unmakeable good leaves an aligned
    gap and the columns line up down the block. It costs no height: five rows
    either way.

    **The cell is 127 wide** -- 28 + 42 + 28 + 26 and three gaps of one -- so a
    row of ten is 1324 with the row's spacing of six, and `bag_wtp_edit_window`
    is 1400 to hold it. **That sum is checked:**
    `check_script.py` → `overflowing_windows` resolves a type drawn inside a
    window to the width the type declares, so adding a control here and leaving
    the window alone is a failure and not a surprise. It did not resolve types
    until this cell grew, which is the door it was added to close.
    """
    # **Деревни стоят в той же сетке, что и товары, и это его правка.**
    # 2026-09-13: «я не хочу, чтобы они забирали себе отдельную строку… нужна
    # только иконка, аналогично как с простыми товарами». Своя строка была под
    # именами зданий; имена ушли, значки пришли, и ячейка стала такой же, как у
    # товара, -- минус «не нужен» и замок, которых у деревни нет.
    picker = list(order) + list(villages_pick)
    rows = []
    for r in range(edit_rows(len(picker))):
        cells = ""
        for i in range(r * EDIT_ROW + 1, min((r + 1) * EDIT_ROW, len(picker)) + 1):
            village = i > len(order)
            # **Три отличия ячейки деревни, и все три -- «у неё этого нет».**
            # Замка нет (доливка ходит по товарам и деревню назад не вернёт),
            # значка-близнеца под замок нет, «не нужен» нет. Пустышка вместо
            # галочки обязана остаться: ряд держит столбцы шириной ячейки, и
            # «просто не рисовать» сдвинуло бы всю строку.
            pin_plain = "" if village else (
                '\t\t\t\t\tvisible = "[Not(GetGlobalVariable(\'%s_lock%d\').IsSet)]"\n'
                % (MOD_ID, i))
            pin_twin = "" if village else (
                '\t\t\t\ttext_single = {\n'
                '\t\t\t\t\tparentanchor = center\n'
                '\t\t\t\t\twidgetanchor = center\n'
                '\t\t\t\t\tautoresize = yes\n'
                '\t\t\t\t\tfontsize = 16\n'
                '\t\t\t\t\tvisible = "[GetGlobalVariable(\'%s_lock%d\').IsSet]"\n'
                '\t\t\t\t\ttext = "%s_cell_pin_%d"\n'
                '\t\t\t\t}\n' % (MOD_ID, i, MOD_ID, i))
            cell_tip = f"{MOD_ID}_vcell_tt" if village else f"{MOD_ID}_cell_tt"
            skip_cell = ('\t\t\twidget = { size = { 26 28 } }\n' if village else
                '\t\t\twidget = {\n'
                '\t\t\t\tsize = { 26 28 }\n'
                '\t\t\t\tcheckbutton_round_alt = {\n'
                '\t\t\t\t\tsize = { 24 24 }\n'
                '\t\t\t\t\tparentanchor = center\n'
                '\t\t\t\t\twidgetanchor = center\n'
                '\t\t\t\t\tdown = "[GetGlobalVariable(\'%s_skip%d\').IsSet]"\n'
                '\t\t\t\t\ttooltip = "%s_edit_skip_tt"\n'
                '\t\t\t\t\tonclick = "[GetScriptedGui(\'%s_pick_skip_%d\')'
                '.Execute(GuiScope.SetRoot(GetPlayer.MakeScope).End)]"\n'
                '\t\t\t\t}\n'
                '\t\t\t}\n' % (MOD_ID, i, MOD_ID, MOD_ID, i))
            cells += f"""
		# **A plain `widget` holds the column; the `hbox` inside only lays the
		# controls out.** This file already carried the rule and it was not
		# applied: «an hbox sizes itself to its children, so anything after a
		# datamodel moves with it — fixed positions inside a plain `widget` are
		# what hold a column still» (`docs/pitfalls/interface.md`). The cell was
		# an `hbox` with a size written on it, and a declared size
		# does not hold an hbox: on a ground that cannot make the good all four
		# controls go invisible, the hbox collapses to nothing, and the row is
		# ragged again exactly as it was before the fix. He reported it
		# unchanged twice, 2026-09-05, and he was right both times.
		widget = {{
			size = {{ {CELL_W} {CELL_H} }}
			hbox = {{
			spacing = 1

			widget = {{
				size = {{ 28 28 }}
				button_regular = {{
					size = {{ 26 26 }}
					parentanchor = center
					widgetanchor = center
					tooltip = "{MOD_ID}_edit_minus_tt"
					onclick = "[GetScriptedGui('{MOD_ID}_pick_minus_{i}').Execute(GuiScope.SetRoot(GetPlayer.MakeScope).End)]"
					text_single = {{
						parentanchor = center
						widgetanchor = center
						autoresize = yes
						fontsize = 14
						text = "{MOD_ID}_edit_minus"
					}}
				}}
			}}

			# **The pin has to be visible, and it was not.** «+1» and «−1» pin
			# the good they are pressed on -- that is what keeps the fill from
			# undoing his own presses -- and until 2026-09-05 nothing on screen
			# said so. His words when asked about it: «я вообще не ебу что за
			# замки, как они работают, могу ли я ими управлять». A mechanism the
			# player cannot see or steer is the mod's fault, not his.
			#
			# Two labels in one slot, the same trick the flag used before it
			# became a checkbox: identical text, one of them coloured, each
			# visible under the opposite reading of `_lock<n>`. No new glyph --
			# `#Y …#!` is the game's markup -- `§Y…§!` is the previous engine's
			# and prints literally, which cost this mod 100 keys on 2026-09-05.
			widget = {{
				size = {{ 42 28 }}
				alwaystransparent = no
				tooltip = "{cell_tip}"
				text_single = {{
					parentanchor = center
					widgetanchor = center
					autoresize = yes
					fontsize = 16
{pin_plain}					text = "{MOD_ID}_cell_{i}"
				}}
{pin_twin}
			}}

			widget = {{
				size = {{ 28 28 }}
				button_regular = {{
					size = {{ 26 26 }}
					parentanchor = center
					widgetanchor = center
					tooltip = "{MOD_ID}_edit_plus_tt"
					onclick = "[GetScriptedGui('{MOD_ID}_pick_plus_{i}').Execute(GuiScope.SetRoot(GetPlayer.MakeScope).End)]"
					text_single = {{
						parentanchor = center
						widgetanchor = center
						autoresize = yes
						fontsize = 14
						text = "{MOD_ID}_edit_plus"
					}}
				}}
			}}

			# **«не нужен» is the game's own checkbox, and that is not a
			# decoration.** It was two buttons carrying «×» and «✔», and the
			# second rendered as an empty box: the game's fonts have no
			# checkmark, and its own localization uses no such character
			# anywhere -- so picking a different glyph would have been another
			# guess. `checkbutton_round_alt` draws both states from a texture
			# (`upframe` / `downframe`) and takes the state from `down`, which
			# is how the outliner's own category toggles work. One control, no
			# glyph, and the state is legible.
{skip_cell}
			}}
		}}
"""
        # **The last row is padded to full width or it drifts.** 47 goods over
        # five rows leaves the fifth with seven cells; a shorter `hbox` inside a
        # centred parent sits in a different place, and he reported exactly that
        # — «в столбики встали только первые три строчки, четвёртая съехала».
        # The pad is empty widgets of a cell's width, so every row measures the
        # same and every column lands under the one above.
        pad = "".join(f"""
		widget = {{ size = {{ {CELL_W} {CELL_H} }} }}
"""
            for _ in range(EDIT_ROW - (min((r + 1) * EDIT_ROW, len(picker))
                                       - r * EDIT_ROW)))
        rows.append(f"""
	# Cells {r * EDIT_ROW + 1}..{min((r + 1) * EDIT_ROW, len(picker))}: товары, затем универсальные деревни.
	type {MOD_ID}_edit_row{r + 1} = hbox {{
		# His words, 2026-09-05: «я не хочу, чтобы инструмент 1 товара был
		# буквально через миллиметр от другого инструмента другого товара».
		spacing = {CELL_GAP}
		# **Every good is here and every cell is identical**, which is the whole
		# of what he asked for twice: «точно такое же удобное расположение
		# товаров как это было реализовано в поиске по 1 товару/праву». Two
		# builds tried to draw only the goods this ground can make — first
		# aligned, which left holes scattered through the block, then packed,
		# which left rows of three beside rows of nine. Both were «страшный набор
		# столбиков». A full grid has neither, and a good this ground cannot make
		# is not a lie on screen: «+1» on it walks the ground, finds nowhere, and
		# says so in the press line (`_edit_last_nowhere`).
		#
		# **`ignoreinvisible = no` is what keeps the columns still**: the pads at
		# the end of the last row are empty widgets, and they have to hold their
		# width or the short row centres itself somewhere else.
		ignoreinvisible = no
{cells}{pad}	}}
""")
    # **Места, а не грамоты, и это разница, которую он назвал сам.** 2026-09-06:
    # «мод должен сначала узнать какие грамоты доступны, а потом загружать
    # доступные в окна». Ячейка, написанная под номер грамоты, держит своё место в
    # ряду даже невидимой -- девять грамот из тринадцати вставали рваными
    # столбцами, и «ювелирное производство» оставалось одно на третьей строке.
    #
    # Здесь ячейка написана под **место**: `_rslot<p>` говорит, какая грамота на
    # нём сидит, а имя, счётчик и обе кнопки попадают в свою грамоту через
    # диспетчер. Места заполняются подряд, так что дыр не бывает вовсе, и ряд из
    # пяти заполнен ровно настолько, сколько грамот держава может выдать.
    for r in range((len(rights) + EDIT_RIGHT_ROW - 1) // EDIT_RIGHT_ROW):
        first = r * EDIT_RIGHT_ROW + 1
        last = min((r + 1) * EDIT_RIGHT_ROW, len(rights))
        cells = ""
        for p in range(first, last + 1):
            cells += f"""
		widget = {{
			size = {{ {EDIT_RIGHT_W} {EDIT_RIGHT_H} }}
			visible = "[GetPlayer.MakeScope.GetVariable('{MOD_ID}_rslotok{p}').IsSet]"
			hbox = {{
				spacing = 1

				widget = {{
					size = {{ 28 {EDIT_RIGHT_H} }}
					button_regular = {{
						size = {{ 26 26 }}
						parentanchor = center
						widgetanchor = center
						tooltip = "{MOD_ID}_edit_right_minus_tt"
						onclick = "[GetScriptedGui('{MOD_ID}_right_minus_slot_{p}').Execute(GuiScope.SetRoot(GetPlayer.MakeScope).End)]"
						text_single = {{
							parentanchor = center
							widgetanchor = center
							autoresize = yes
							fontsize = 16
							text = "{MOD_ID}_edit_minus"
						}}
					}}
				}}

				widget = {{
					size = {{ 32 {EDIT_RIGHT_H} }}
					alwaystransparent = no
					tooltip = "{MOD_ID}_edit_right_count_tt"
					text_single = {{
						parentanchor = center
						widgetanchor = center
						autoresize = yes
						fontsize = 18
						text = "[GetPlayer.Custom('{MOD_ID}_rslot_count_{p}')]"
					}}
				}}

				widget = {{
					size = {{ 28 {EDIT_RIGHT_H} }}
					button_regular = {{
						size = {{ 26 26 }}
						parentanchor = center
						widgetanchor = center
						tooltip = "{MOD_ID}_edit_right_plus_tt"
						onclick = "[GetScriptedGui('{MOD_ID}_right_plus_slot_{p}').Execute(GuiScope.SetRoot(GetPlayer.MakeScope).End)]"
						text_single = {{
							parentanchor = center
							widgetanchor = center
							autoresize = yes
							fontsize = 16
							text = "{MOD_ID}_edit_plus"
						}}
					}}
				}}

				widget = {{
					size = {{ {EDIT_RIGHT_W - 91} {EDIT_RIGHT_H} }}
					alwaystransparent = no
					tooltip = "[GetPlayer.Custom('{MOD_ID}_rslot_name_{p}')]"
					text_single = {{
						size = {{ {EDIT_RIGHT_W - 95} {EDIT_RIGHT_H - 2} }}
						parentanchor = left|vcenter
						widgetanchor = left|vcenter
						autoresize = no
						maximumsize = {{ {EDIT_RIGHT_W - 95} {EDIT_RIGHT_H - 2} }}
						fontsize = 16
						fontsize_min = 12
						align = left|vcenter
						elide = right
						text = "[GetPlayer.Custom('{MOD_ID}_rslot_name_{p}')]"
					}}
				}}
			}}
		}}
"""
        # **`ignoreinvisible = no` и добивка до полного ряда.** Места заполняются
        # подряд, так что пустыми бывают только последние; короткий `hbox` в
        # центрирующем родителе уезжает, а пустышка держит его на месте.
        pad = "".join(f"		widget = {{ size = {{ {EDIT_RIGHT_W} {EDIT_RIGHT_H} }} }}\n"
                      for _ in range(EDIT_RIGHT_ROW - (last - first + 1)))
        rows.append(f"""
	# Места {first}..{last}: какая грамота на каком, решает `_rslot<p>`.
	#
	# **Ряд гаснет целиком по своему первому месту.** Места заполняются подряд, так
	# что ряд пуст тогда и только тогда, когда пусто его первое место -- а `hbox`,
	# у которого невидимы все дети, сам остаётся видимым и держит свои 32 пикселя.
	type {MOD_ID}_edit_right_row{r + 1} = hbox {{
		spacing = 14
		ignoreinvisible = no
		visible = "[GetPlayer.MakeScope.GetVariable('{MOD_ID}_rslotok{first}').IsSet]"
{cells}{pad}	}}
""")
    return (HEADER + f"""#
# The plan editor's picker, a cell a good and a cell a charter.
# `{MOD_ID}_edit_window.gui` draws the rows and the columns; this file only
# declares them, so it has no `window` and needs no line in
# `gui/scripted_widgets/`.

types BagWtpEditCells {{
{"".join(rows)}}}
""")


# The search picker's cells, in the same shape and for the same reason as the
# editor's: a cell knows its own number, so nothing has to carry a scope from
# the press to the effect.
#
# **A good is a circle and an icon; a right is a circle and its name.** Thirteen
# rights share their icons with the goods they favour, so an icon alone would
# not tell two of them apart -- and 47 goods with their names beside them would
# be four times the window wide. The tooltip carries the good's name.
# **The gap between cells is bigger than the gap inside one, and that is the
# whole point of it.** A circle two pixels from its own icon and four from the
# next good's reads as one row of loose parts: «они все в куче и не всегда
# понимаешь сразу на какую галочку нужно нажать — правую или левую от товара»,
# 2026-09-06. The editor learnt the same thing on 2026-09-05 and its gap is 14.
PICK_ROW = 10
PICK_ROWS = 5
PICK_W, PICK_H, PICK_GAP = 62, 28, 14
RIGHT_PICK_COL = 7
RIGHT_PICK_COLS = 2
RIGHT_PICK_W = 250
PICK_CELLS_OUT = MOD / "in_game/gui/bag_wtp_pick_cells.gui"


def pick_cells_file(order: list[str], rights: list[eu5data.TownRight]) -> str:
    """Which good, or which right, the ranking answers for -- picked in the window.

    **The mod page had four lists for this and now has none.** His words,
    2026-09-06: «мод внутри стал довольно громоздким и неудобным» and «просто
    добавишь в окно расчёта иконки товаров и прав как ты это сделал в редакторе
    и поставишь каждому кружочек для активации нужного, далее кнопку искать
    локации, всё». So the cells are the editor's cells with the counters taken
    off: a `checkbutton_round_alt` whose `down` reads `_sel<n>` and whose
    `onclick` calls the effect for that number.

    **Every cell is a static child of a plain `hbox` and keeps its column**,
    both rules paid for in `docs/pitfalls/interface.md`: `flowcontainer` crashed
    the game, `fixedgridbox` drew cells on top of each other, and a declared
    size does not hold an `hbox` whose children go invisible -- which is why a
    cell is a `widget` with a size and the `hbox` is inside it.

    A row of goods is 10 cells of 62 -- 656 with its spacing -- and the rights
    are two columns of 250 beside it; both windows that draw them are wide enough
    for the pair, and `check_script.py` measures that rather than trusting it.
    """
    out = [HEADER, f"""#
# The ranking windows' picker, a cell a good and a cell a right. Neither window
# declares these: `{MOD_ID}_result_window.gui` and `{MOD_ID}_right_window.gui`
# both draw the same rows, so the two can never offer different goods.
#
# This file has no `window` and needs no line in `gui/scripted_widgets/`.

types BagWtpPickCells {{
"""]

    for r in range(PICK_ROWS):
        first, last = r * PICK_ROW + 1, min((r + 1) * PICK_ROW, len(order))
        cells = ""
        for i in range(first, last + 1):
            good = order[i - 1]
            cells += f"""
		widget = {{
			size = {{ {PICK_W} {PICK_H} }}
			hbox = {{
				spacing = 2

				widget = {{
					size = {{ 26 {PICK_H} }}
					checkbutton_round_alt = {{
						size = {{ 24 24 }}
						parentanchor = center
						widgetanchor = center
						down = "[GetGlobalVariable('{MOD_ID}_sel{i}').IsSet]"
						tooltip = "{MOD_ID}_good_{good}"
						onclick = "[GetScriptedGui('{MOD_ID}_pick_good_{i}').Execute(GuiScope.SetRoot(GetPlayer.MakeScope).End)]"
					}}
				}}

				widget = {{
					size = {{ 34 {PICK_H} }}
					alwaystransparent = no
					tooltip = "{MOD_ID}_good_{good}"
					text_single = {{
						parentanchor = center
						widgetanchor = center
						autoresize = yes
						fontsize = 16
						text = "{MOD_ID}_pick_{i}"
					}}
				}}
			}}
		}}
"""
        pad = "".join(f"		widget = {{ size = {{ {PICK_W} {PICK_H} }} }}\n"
                      for _ in range(PICK_ROW - (last - first + 1)))
        out.append(f"""
	# Goods {first}..{last} of the plan's own order.
	type {MOD_ID}_pick_row{r + 1} = hbox {{
		spacing = {PICK_GAP}
		ignoreinvisible = no
{cells}{pad}	}}
""")

    # **The rights are two columns that pack upward, not rows that leave holes.**
    # A country is offered nine or ten of the thirteen, and on 2026-09-06 the
    # missing ones left gaps scattered through the block: «нужно сделать, чтобы
    # городские права справа вставали примерно по такому же принципу, аккуратно
    # и без пробелов». Two rows of two cannot pack -- half a row is a hole
    # wherever it falls -- but a column can, so each column is a `vbox` with
    # `ignoreinvisible = yes` and the cell itself carries the `visible`. What is
    # left over is a short second column, which is a gap at the end and the shape
    # he approved on the goods.
    for c in range(RIGHT_PICK_COLS):
        first = c * RIGHT_PICK_COL + 1
        last = min((c + 1) * RIGHT_PICK_COL, len(rights))
        cells = ""
        for i in range(first, last + 1):
            right = rights[i - 1]
            cells += f"""
		widget = {{
			size = {{ {RIGHT_PICK_W} {PICK_H} }}
			visible = "[GetPlayer.MakeScope.GetVariable('{MOD_ID}_right_ok{i}').IsSet]"
			hbox = {{
				spacing = 2

				widget = {{
					size = {{ 26 {PICK_H} }}
					checkbutton_round_alt = {{
						size = {{ 24 24 }}
						parentanchor = center
						widgetanchor = center
						down = "[GetGlobalVariable('{MOD_ID}_rsel{i}').IsSet]"
						tooltip = "{MOD_ID}_right_{right.key}"
						onclick = "[GetScriptedGui('{MOD_ID}_pick_right_{i}').Execute(GuiScope.SetRoot(GetPlayer.MakeScope).End)]"
					}}
				}}

				widget = {{
					size = {{ {RIGHT_PICK_W - 28} {PICK_H} }}
					alwaystransparent = no
					tooltip = "{MOD_ID}_right_{right.key}"
					text_single = {{
						size = {{ {RIGHT_PICK_W - 32} 26 }}
						parentanchor = left|vcenter
						widgetanchor = left|vcenter
						autoresize = no
						maximumsize = {{ {RIGHT_PICK_W - 32} 26 }}
						fontsize = 14
						fontsize_min = 10
						align = left|vcenter
						elide = right
						text = "{MOD_ID}_right_{right.key}"
					}}
				}}
			}}
		}}
"""
        out.append(f"""
	# Urban rights {first}..{last}, packed upward: a right this country cannot
	# hold takes no space at all.
	type {MOD_ID}_pick_right_col{c + 1} = vbox {{
		spacing = 2
		ignoreinvisible = yes
{cells}
		# **The slack goes here and not between the rights.** Drawn in a box
		# taller than the rights it has, this `vbox` shared the difference out
		# between them — «список городских прав во втором столбце вообще решил
		# поделить территорию на равные части, а не встать списком», 2026-09-06.
		# An expanding child takes it all, and the list stays a list.
		widget = {{ layoutpolicy_vertical = expanding size = {{ {RIGHT_PICK_W} -1 }} }}
	}}
""")
    out.append("}\n")
    return "".join(out)


def editor_file(rows: list[eu5data.Method], split: dict[str, list[str]],
                game: eu5data.Game) -> tuple[str, str]:
    """Editing a plan that already exists, one building at a time.

    **The plan is state on the map, and this changes it in place.** The owner
    asked for this twice and the second time in nine numbered steps, 2026-09-03:
    «Мод не пересобирает весь план с 0, он просто точечно выбирает какой товар X
    менее болезненно удалить для наилучшей установки туда товара Y, без
    полномасштабного смещения всех товаров и прав.» What was built instead was a
    weight fed back into a full re-plan, and the run measured what that is worth:
    **42 locations of 48 changed** on a knob meant to move one.

    So «+1 домик» is exactly one building:

    1. every candidate is asked what it would cost to put this good there --
       nothing if the location has a free room, otherwise the gain of the
       cheapest building that may be taken out;
    2. the location where that costs least takes it;
    3. the victim comes out, the good goes in, and nothing else on the map moves.

    **What may not be taken out**, and neither rule is optional:

    - **a good's last building.** «Нельзя увеличивать число локаций чего-либо
      больше, если у какого-то товара будет угроза потерять последний домик» --
      so a good standing in exactly one place is never the victim, and the plan
      keeps its covering constraint through any amount of editing.
    - **a building the town's charter put there.** A charter is granted for its
      bundle; taking a bundle good out leaves the town holding a charter for
      something it does not make, which is worse than the edit is worth.

    **The picker is this window's own** and not the goods list the ranking uses --
    also his, and also from the second telling: «выбор товара для регуляции не
    должны быть в том же выборе товара для поиска лучшей локации».

    **And it is a window of its own, not a page of the mod's settings.** The
    first build put the picker and the buttons in the Mod Menu and he refused to
    open it, 2026-09-03: «Сейчас окно настроек мода - стало засраным и неудобным.
    Более того это именно что окно настроек и основных функций, я не хочу делать
    подобные вещи там.» So the goods are icons in `bag_wtp_edit_window.gui`, each
    chosen one gets a row with `-1`, its icon and `+1`, and the effects here are
    reached from those buttons through `{MOD_ID}_edit_set_good`, which takes the
    good as a scope instead of reading a dropdown.
    """
    order = [good for kind in ("raw", "made") for good in split[kind]]
    groups = plan_groups(rows, split, game)
    villages_ = village_entities(rows, split, game)
    # **Деревня-сущность -- не здание товара, и редактор обязан знать это тоже.**
    #
    # Ворота плана выбрасывали её из товара с самого начала
    # (`plan_triggers_file`), а здесь стояло «ворота редактора строятся отдельно
    # и деревни сохраняют» -- ровно та дыра, которую нашёл прогон 2026-09-12,
    # когда `hunting_lodges` вернулся в игру: «+1» на дичь стал втыкать лесную
    # деревню. Его слово: «деревня -- универсальное здание, универсальные здания
    # считаются как отдельная сущность… такие товары как дичь или рыба выбывают
    # из счёта, так как они обобщены и включены в сущность какой-либо деревни».
    #
    # `groups` ниже читается там, где речь о самой деревне (обмен,
    # `_plan_pick_worst`); `own_groups` -- там, где речь о товаре.
    own_groups = {key: ({b: m for b, m in by.items() if b not in villages_}
                        if key[1] == "r" else by)
                  for key, by in groups.items()}
    rights = output_rights(rows, game)

    # **И три универсальные деревни стоят в том же списке «+1/−1».** Его слово
    # 2026-09-12, тем же сообщением, что выбросило деревню из товара: «в списке
    # товаров на +1 −1 нужно убрать те, которые производятся ТОЛЬКО деревнями
    # (кроме земледельческой) и добавить в список +1 −1 все три вида
    # универсальных деревень». Иначе деревню стало нечем ни поднять, ни опустить
    # вовсе: из товара она вышла, а своей строки не имела.
    #
    # **Номер деревни -- это `len(order) + k`**, и дальше она едет по тем же
    # рельсам: `_edit_good` её номер, `_edit_scan_<i>`, `_edit_fits_rural_<i>`,
    # `_edit_place_rural_<i>` и `_edit_remove_rural_<i>` у неё свои и зовут
    # готовые `_plan_try_village_<k>` / `_plan_drop_village_<k>`.
    #
    # **Жертвой деревня не бывает.** `_plan_pick_worst` выбирает только свои
    # домики товара, и `_esg` поэтому всегда товар -- значит `remove_dispatch`
    # и `restore_dispatch` остаются на товарах, а доливка после «−1» деревню не
    # вернёт: она ходит по товарам.
    vshared = shared_buildings(rows, split, game)
    vmakes_pick = {k: [i for i, g in enumerate(order, start=1)
                       if b in (groups.get((g, "r")) or {})]
                   for k, b in enumerate(villages_, start=1)}
    PICK_N = len(order) + len(villages_)

    def vill_of(index: int) -> int:
        """Номер деревни по номеру в списке редактора, или 0 для товара."""
        return index - len(order) if index > len(order) else 0

    def call(prefix: str, index: int, tab: str) -> str:
        """The two sides' effects, and only the ones that were generated.

        A good with no village building has no `_plan_try_rural_<n>`, and calling
        an effect that does not exist is the failure this repository names first:
        the block it sits in does nothing and the game says so nowhere useful.
        """
        if vill_of(index):
            # Деревня стоит только в селе, и городской половины у неё нет вовсе.
            return f"{tab}{MOD_ID}_{prefix}_rural_{index} = yes\n"
        good = order[index - 1]
        return "".join(
            f"{tab}{MOD_ID}_{prefix}_{listname}_{index} = yes\n"
            for side, listname in (("t", "town"), ("r", "rural"))
            if own_groups.get((good, side)))
    out = [HEADER, f"""#
# The plan editor. Everything here changes a plan that already exists and
# **nothing here re-runs the plan**: `{MOD_ID}_plan_run` is the only thing that
# does, and pressing it throws every edit away, which is why the save slot exists.
"""]
    gate = [HEADER, f"""#
# The editor's own questions. **Written with OR and AND and never an `if`**, the
# same rule every other scripted trigger here obeys.
"""]

    # ---- which good the editor is pointed at -------------------------------
    #
    # **It is a global, and the day it was a country variable cost three builds.**
    # `_edit_add` reads it in two scopes: at the top, where the scope is the
    # country, and again inside `ordered_in_global_list`, where the scope is the
    # **location** the walk stands on. A `var:` read there asks the location for
    # a variable only the country has, so `add_dispatch` matched nothing, ever --
    # the walk evicted a building, failed to place, and put the victim back. His
    # own report, 2026-09-04: `evicted=1 room=1 | placed_before=191
    # placed_after=192` with `done=0 fail=1`. Every «+1» and «−1» he pressed for
    # three builds died there.
    #
    # **A number the editor carries across scopes is a global. No exceptions.**
    #
    # **It is a number, and the buttons write it themselves.** An effect stood
    # here that took the good as a saved scope and walked 47 comparisons to turn
    # it into the plan's index, because every counter the plan keeps is numbered
    # -- `_pn<n>`, `_p<n>`, `_pm<n>` -- and a scope indexes none of them. The
    # picker stopped carrying scopes when its cells were written out, so
    # `_edit_plus_<n>` sets `_edit_good` to its own `n` and the bridge is gone.
    # `_edit_reached` stays: it is what tells «кнопка не донесла товар» apart
    # from a rule refusing, and the numbered effects set it.

    # ---- may this good stand here, room aside ------------------------------
    #
    # `_plan_can_*` is the placement gate and asks the room as well; an eviction
    # is precisely the case where there is no room, so the editor needs the same
    # question without that clause.
    for side, listname, method_var, rank in (("t", "town", "pm", "yes"),
                                             ("r", "rural", "prm", "no")):
        for index, good in enumerate(order, start=1):
            by_building = own_groups.get((good, side), {})
            if not by_building:
                gate.append(f"\n# Scope: location\n"
                            f"{MOD_ID}_edit_fits_{listname}_{index} = {{ always = no }}\n")
                continue
            branches = ""
            for building, mis in sorted(by_building.items()):
                tests = "".join("\t\t\t\tvar:%s_%s%d = %d\n" % (MOD_ID, method_var, index, mi)
                                for mi in sorted(mis))
                one = ""
                branches += (f"\t\tAND = {{\n\t\t\tOR = {{\n{tests}\t\t\t}}\n"
                             f"\t\t\tNOT = {{ is_target_in_variable_list = "
                             f"{{ name = {MOD_ID}_plan_builds target = building_type:{building} }} }}\n"
                             f"{one}\t\t}}\n")
            gate.append(f"""
# {good}, {"town" if side == "t" else "village"} side, room not asked.
# Scope: location
{MOD_ID}_edit_fits_{listname}_{index} = {{
\tvar:{MOD_ID}_{method_var}{index} > 0
\t{MOD_ID}_is_granary = no
\t{MOD_ID}_plan_is_town = {rank}
\tNOT = {{ is_target_in_variable_list = {{ name = {MOD_ID}_plan_goods target = goods:{good} }} }}
\tOR = {{
{branches}\t}}
}}
""")

    # ---- a bundle good of the charter granted here --------------------------
    #
    # **A charter's buildings are taken whole or not at all**, and this is the
    # second thing he said about them. On 2026-09-04 he struck the lock out --
    # «городские права и их домики не должны быть жёстко зарезервированы» -- and
    # then, having seen what that does, drew the line properly:
    #
    #   «Не должно происходить ситуации, когда в городе у которого допустим
    #    ремесленные права — он теряет все свои бонусные дома… Я бы предпочёл не
    #    забирать домики по частям у городских прав. Я бы скорее предпочёл
    #    забирать у города целиком всю связку право+его домики.»
    #
    # So piecemeal eviction is off again, and **taking the whole bundle is the
    # thing to build** -- «+1»/«−1» for the charters themselves, which he asked
    # for in the same breath. Until that exists this lock is the honest state:
    # a town keeps the buildings its charter is for.
    for index, good in enumerate(order, start=1):
        holders = [k for k, right in enumerate(rights, start=1) if good in right.output]
        if not holders:
            gate.append(f"\n# Scope: location\n"
                        f"{MOD_ID}_edit_locked_{index} = {{ always = no }}\n")
            continue
        tests = "".join(f"\t\tvar:{MOD_ID}_plan_right = {k}\n" for k in holders)
        gate.append(f"""
# {good} is in the bundle of the charter granted here, so the editor takes it out
# only with the charter itself -- never on its own.
# Scope: location
{MOD_ID}_edit_locked_{index} = {{
\thas_variable = {MOD_ID}_plan_right
\tOR = {{
{tests}\t}}
}}
"""  )


    # ---- the cheapest building this location could give up -----------------
    #
    # Good-independent, so it is worked out once a location and read by whichever
    # good is being added. Written as its own effect for that reason: inlined per
    # good it would be 47 x 94 blocks and the file would be unreadable.
    worst = {}
    for side, gain_var in (("t", "p"), ("r", "pr")):
        worst[side] = "".join(f"""\t\tif = {{
\t\t\tlimit = {{
\t\t\t\tis_target_in_variable_list = {{ name = {MOD_ID}_plan_goods target = goods:{good} }}
\t\t\t\tglobal_var:{MOD_ID}_pn{index} > 1
\t\t\t\tNOT = {{ {MOD_ID}_edit_locked_{index} = yes }}
\t\t\t\t# **Two different locks meet on this line and they are not the same
\t\t\t\t# thing.** `_edit_locked_<n>` above is the charter's: this building
\t\t\t\t# belongs to a town right's bundle and the bundle goes whole or not at
\t\t\t\t# all. `_lock<n>` here is the player's: he pressed this good and it
\t\t\t\t# stays where he put it.
\t\t\t\t#
\t\t\t\t# **A good the player pinned is never the one that gives way.** The
\t\t\t\t# second of the lock's three consequences: pressing «+1» on iron must
\t\t\t\t# not quietly undo the «−1» he spent on cloth a moment ago. Note this
\t\t\t\t# is `_lock<n>` and not `_skip<n>`: «не нужен» says «never fill this
\t\t\t\t# past its minimum», which makes its buildings *better* candidates to
\t\t\t\t# give up, not protected ones.
\t\t\t\tNOT = {{ has_global_variable = {MOD_ID}_lock{index} }}
\t\t\t\t# **The good that gave way is the one furthest above its share, and
\t\t\t\t# its cheapest building is the one that goes.** Step 3, and it is
\t\t\t\t# the eviction side of the rule the fill already obeys: «−1» hands
\t\t\t\t# a freed room to the good furthest *below* its share.
\t\t\t\t#
\t\t\t\t# **Two keys and one pass, exactly as the fill does it** -- `_esx`
\t\t\t\t# carries the best excess so far and `_esw` the gain that goes with
\t\t\t\t# it, so «more bloated» and «as bloated but cheaper to lose» are two
\t\t\t\t# arms of one `OR`. Not a packed `превышение × K + выгода`: the
\t\t\t\t# engine's fixed-point limit is not known from here, and the same
\t\t\t\t# warning already stands over `_plan_order`.
\t\t\t\t#
\t\t\t\t# On the strict pass a good at or below its share is not a victim
\t\t\t\t# at all. `{MOD_ID}_edit_add` runs the scan strict first and repeats
\t\t\t\t# it open only if nothing qualified, so this narrows and never blocks.
\t\t\t\tOR = {{
\t\t\t\t\tglobal_var:{MOD_ID}_edit_strict = 0
\t\t\t\t\tglobal_var:{MOD_ID}_exs{index} > 0
\t\t\t\t}}
\t\t\t\tOR = {{
\t\t\t\t\tvar:{MOD_ID}_esx < global_var:{MOD_ID}_exs{index}
\t\t\t\t\tAND = {{
\t\t\t\t\t\tvar:{MOD_ID}_esx = global_var:{MOD_ID}_exs{index}
\t\t\t\t\t\tOR = {{
\t\t\t\t\t\t\tvar:{MOD_ID}_esw = -1
\t\t\t\t\t\t\tvar:{MOD_ID}_{gain_var}{index} < var:{MOD_ID}_esw
\t\t\t\t\t\t}}
\t\t\t\t\t}}
\t\t\t\t}}
\t\t\t}}
\t\t\tset_variable = {{ name = {MOD_ID}_esx value = global_var:{MOD_ID}_exs{index} }}
\t\t\tset_variable = {{ name = {MOD_ID}_esw value = var:{MOD_ID}_{gain_var}{index} }}
\t\t\tset_variable = {{ name = {MOD_ID}_esg value = {index} }}
\t\t}}
"""
        for index, good in enumerate(order, start=1))
    out.append(f"""
# The building this location would give up most cheaply, and which good it is.
#
# `-1` in `_esw` means "nothing here may be taken out at all" -- every building
# is either its good's last on the ground or part of the town's charter bundle.
# **A gain of nought is a real answer and `-1` is not**, which is why the empty
# marker cannot be nought: a good the ground feeds nothing is exactly the one an
# edit should be taking out first.
# Scope: location
{MOD_ID}_edit_worst = {{
\tset_variable = {{ name = {MOD_ID}_esw value = -1 }}
\tset_variable = {{ name = {MOD_ID}_esg value = 0 }}
\t# Below every excess, which is floored at zero, so the first good that
\t# may go wins outright and the rest is a comparison between goods.
\tset_variable = {{ name = {MOD_ID}_esx value = -1 }}
\tif = {{
\t\tlimit = {{ {MOD_ID}_plan_is_town = yes }}
{worst["t"]}\t}}
\telse = {{
{worst["r"]}\t}}
}}
""")

    # **Ворота деревни для редактора -- `_plan_can_village_<k>` без комнаты.**
    # Та же пара, что у товара: план спрашивает свободную комнату, редактор
    # освобождает её сам, поэтому здесь её нет, и `_edit_place_rural_<i>`
    # спрашивает полные ворота в последний момент через `_plan_try_village_<k>`.
    for k, building in enumerate(villages_, start=1):
        index = len(order) + k
        goods_free = "".join(
            f"\t\tAND = {{\n"
            f"\t\t\tvar:{MOD_ID}_vw{k} = {i}\n"
            f"\t\t\tNOT = {{ is_target_in_variable_list = {{ name = {MOD_ID}_plan_goods "
            f"target = goods:{order[i - 1]} }} }}\n"
            f"\t\t}}\n" for i in vmakes_pick[k])
        gate.append(f"""
# {building}: ворота редактора, «комната» снята.
# Scope: location
{MOD_ID}_edit_fits_rural_{index} = {{
\tvar:{MOD_ID}_vw{k} > 0
\t{MOD_ID}_is_granary = no
\t{MOD_ID}_plan_is_town = no
\tNOT = {{ is_target_in_variable_list = {{ name = {MOD_ID}_plan_builds target = building_type:{building} }} }}
\tOR = {{
{goods_free}\t}}
}}

# {building} в городе не стоит вовсе.
# Scope: location
{MOD_ID}_edit_fits_town_{index} = {{ always = no }}
""")

    # ---- what it would cost to put this good here --------------------------
    for index, good in enumerate(order, start=1):
        arms = []
        for side, listname, cap, gain_var in (("t", "town", "urban", "p"),
                                              ("r", "rural", "rural", "pr")):
            arms.append(f"""\t\tif = {{
\t\t\tlimit = {{ {MOD_ID}_edit_fits_{listname}_{index} = yes }}
\t\t\tif = {{
\t\t\t\tlimit = {{ var:{MOD_ID}_load < global_var:{MOD_ID}_plan_cap_{cap} }}
\t\t\t\t# A free room costs nothing, so it always outbids an eviction.
\t\t\t\tset_variable = {{ name = {MOD_ID}_esc value = 1 }}
\t\t\t\tset_variable = {{ name = {MOD_ID}_esv value = var:{MOD_ID}_{gain_var}{index} }}
\t\t\t\tchange_variable = {{ name = {MOD_ID}_esv add = {RANK_SCALE} }}
\t\t\t}}
\t\t\telse_if = {{
\t\t\t\tlimit = {{ var:{MOD_ID}_esw >= 0 var:{MOD_ID}_esg > 0 }}
\t\t\t\tset_variable = {{ name = {MOD_ID}_esc value = 1 }}
\t\t\t\tset_variable = {{ name = {MOD_ID}_esv value = var:{MOD_ID}_{gain_var}{index} }}
\t\t\t\tchange_variable = {{ name = {MOD_ID}_esv subtract = var:{MOD_ID}_esw }}
\t\t\t}}
\t\t}}
""")
        out.append(f"""
# {good}: what every candidate would charge for one more of it.
# Scope: country
{MOD_ID}_edit_scan_{index} = {{
\tevery_in_global_list = {{
\t\tvariable = {MOD_ID}_candidates
{"".join(arms)}\t}}
}}
""")

    # То же для деревни: её выгода на локации -- `_vb<k>`, посчитанная тем же
    # проходом `_plan_village_scores`, что и `_p<n>` у товара.
    for k, building in enumerate(villages_, start=1):
        index = len(order) + k
        out.append(f"""
# {building}: что каждая локация запросит за ещё одну такую деревню.
# Scope: country
{MOD_ID}_edit_scan_{index} = {{
\tevery_in_global_list = {{
\t\tvariable = {MOD_ID}_candidates
\t\tif = {{
\t\t\tlimit = {{ {MOD_ID}_edit_fits_rural_{index} = yes }}
\t\t\tif = {{
\t\t\t\tlimit = {{ var:{MOD_ID}_load < global_var:{MOD_ID}_plan_cap_rural }}
\t\t\t\tset_variable = {{ name = {MOD_ID}_esc value = 1 }}
\t\t\t\tset_variable = {{ name = {MOD_ID}_esv value = var:{MOD_ID}_vb{k} }}
\t\t\t\tchange_variable = {{ name = {MOD_ID}_esv add = {RANK_SCALE} }}
\t\t\t}}
\t\t\telse_if = {{
\t\t\t\tlimit = {{ var:{MOD_ID}_esw >= 0 var:{MOD_ID}_esg > 0 }}
\t\t\t\tset_variable = {{ name = {MOD_ID}_esc value = 1 }}
\t\t\t\tset_variable = {{ name = {MOD_ID}_esv value = var:{MOD_ID}_vb{k} }}
\t\t\t\tchange_variable = {{ name = {MOD_ID}_esv subtract = var:{MOD_ID}_esw }}
\t\t\t}}
\t\t}}
\t}}
}}

# {building} сюда, и обратно. **Обёртки, а не вторая копия правил**: ставит и
# снимает деревню то же, что делает это в плане, — иначе счётчики разъехались бы.
# Scope: location
{MOD_ID}_edit_place_rural_{index} = {{ {MOD_ID}_plan_try_village_{k} = yes }}
# Scope: location
{MOD_ID}_edit_remove_rural_{index} = {{ {MOD_ID}_plan_drop_village_{k} = yes }}
""")

    # ---- taking one building out -------------------------------------------
    for side, listname, method_var, gain_var in (("t", "town", "pm", "p"),
                                                 ("r", "rural", "prm", "pr")):
        for index, good in enumerate(order, start=1):
            by_building = own_groups.get((good, side), {})
            if not by_building:
                continue
            branches = ""
            for building, mis in sorted(by_building.items()):
                tests = "".join("\t\t\t\tvar:%s_%s%d = %d\n" % (MOD_ID, method_var, index, mi)
                                for mi in sorted(mis))
                # **Выхлоп отдаётся обратно, и это ветка на метод**, как у
                # постановки: `_edit_place_*` растит `_pout<n>` числом того
                # способа, который стоит, и снятие обязано вычесть то же число.
                # Без этого «убрал всё и поставил заново» поднимало `_pout<n>`
                # на каждом круге, а его читает и сводка, и диагностика.
                outs = "".join(
                    f"\t\t\tif = {{ limit = {{ var:{MOD_ID}_{method_var}{index} = {mi} }} "
                    f"change_global_variable = {{ name = {MOD_ID}_pout{index} "
                    f"subtract = {int(round(rows[mi - 1].output * 100))} }} }}\n"
                    for mi in sorted(mis))
                branches += f"""\t\tif = {{
\t\t\tlimit = {{ OR = {{
{tests}\t\t\t}} }}
{outs}\t\t\tremove_list_variable = {{ name = {MOD_ID}_plan_builds target = building_type:{building} }}
\t\t}}
"""
            out.append(f"""
# {good} out of this location, {"town" if side == "t" else "village"} side.
#
# **Every counter the plan keeps is walked back**, because the report and the
# next edit both read them: the load, the total placed, this good's own count,
# and the two gain counters the header prints.
# Scope: location
{MOD_ID}_edit_remove_{listname}_{index} = {{
\tif = {{
\t\tlimit = {{
\t\t\tis_target_in_variable_list = {{ name = {MOD_ID}_plan_goods target = goods:{good} }}
\t\t\t# **The side is asked here too, and it was not.** `call()` emits both
\t\t\t# variants and the town one came first, so a village location had its
\t\t\t# *town* gain subtracted from `_plan_gain` and its building matched
\t\t\t# against `_pm<n>` instead of `_prm<n>`. Placement has always asked --
\t\t\t# `_edit_fits_*` carries `{MOD_ID}_plan_is_town` -- and the two halves
\t\t\t# of one edit have to agree about what kind of place this is.
\t\t\t{MOD_ID}_plan_is_town = {"yes" if side == "t" else "no"}
\t\t}}
\t\tremove_list_variable = {{ name = {MOD_ID}_plan_goods target = goods:{good} }}
{branches}\t\tchange_variable = {{ name = {MOD_ID}_load subtract = 1 }}
\t\tchange_global_variable = {{ name = {MOD_ID}_plan_placed subtract = 1 }}
\t\t# **И счётчик комнат своей стороны.** Постановка его растит, снятие обязано
\t\t# уменьшать: без этого обмен считался как две постановки, и «по сторонам»
\t\t# вышло 578 из 528 (прогон 2026-09-09).
\t\tchange_global_variable = {{ name = {MOD_ID}_plan_p{side} subtract = 1 }}
\t\tchange_global_variable = {{ name = {MOD_ID}_pn{index} subtract = 1 }}
\t\t# **И счёт своей стороны по этому товару.** Постановка растит
\t\t# `_pn{side}<n>`, снятие его не возвращало: `_pnt<n>` и `_pnr<n>`
\t\t# росли от каждого круга «убрал -- поставил», а на них стоят ряды
\t\t# и сводка.
\t\tchange_global_variable = {{ name = {MOD_ID}_pn{side}{index} subtract = 1 }}
\t\tchange_global_variable = {{ name = {MOD_ID}_plan_gain subtract = var:{MOD_ID}_{gain_var}{index} }}
\t\tif = {{
\t\t\tlimit = {{ var:{MOD_ID}_{gain_var}{index} > 0 }}
\t\t\tchange_global_variable = {{ name = {MOD_ID}_plan_fed subtract = 1 }}
\t\t}}
\t}}
}}
""")

    # ---- the two operations -------------------------------------------------
    scan_dispatch = "".join(
        f"\t\tif = {{ limit = {{ global_var:{MOD_ID}_edit_good = {i} }} {MOD_ID}_edit_scan_{i} = yes }}\n"
        for i in range(1, PICK_N + 1))
    # How many locations could hold this good at all, room and victims aside.
    fit_dispatch = "".join(
        f"\t\tif = {{\n\t\t\tlimit = {{ global_var:{MOD_ID}_edit_good = {i} }}\n"
        f"\t\t\tevery_in_global_list = {{\n"
        f"\t\t\t\tvariable = {MOD_ID}_candidates\n"
        f"\t\t\t\tlimit = {{ OR = {{ {MOD_ID}_edit_fits_town_{i} = yes "
        f"{MOD_ID}_edit_fits_rural_{i} = yes }} }}\n"
        f"\t\t\t\tchange_global_variable = {{ name = {MOD_ID}_edit_fitn add = 1 }}\n"
        f"\t\t\t}}\n\t\t}}\n"
        for i in range(1, PICK_N + 1))
    remove_dispatch = "".join(
        f"\t\t\tif = {{ limit = {{ var:{MOD_ID}_esg = {i} }}\n"
        f"{call('edit_remove', i, chr(9) * 4)}\t\t\t}}\n"
        for i in range(1, len(order) + 1))
    add_dispatch = "".join(
        f"\t\t\t\tif = {{ limit = {{ global_var:{MOD_ID}_edit_good = {i} }}\n"
        f"{call('edit_place', i, chr(9) * 5)}\t\t\t\t}}\n"
        for i in range(1, PICK_N + 1))
    # The victim put back where it stood, keyed by `_esg` rather than by the
    # good the press asked for. Same effects: a building that stood here a
    # moment ago passes `_plan_can_*` again by construction.
    restore_dispatch = "".join(
        f"\t\t\t\t\tif = {{ limit = {{ var:{MOD_ID}_esg = {i} }}\n"
        f"{call('edit_place', i, chr(9) * 6)}\t\t\t\t\t}}\n"
        for i in range(1, len(order) + 1))
    held = "".join(
        f"\tif = {{ limit = {{ global_var:{MOD_ID}_edit_good = {i} }} "
        f"set_global_variable = {{ name = {MOD_ID}_edit_fitn "
        f"value = global_var:{MOD_ID}_pn{i} }} }}\n"
        for i in range(1, len(order) + 1)) + "".join(
        # У деревни свой счётчик поставленных -- `_bn<k>` по списку общих
        # зданий, тот самый, которым её держит потолок в плане.
        f"\tif = {{ limit = {{ global_var:{MOD_ID}_edit_good = {len(order) + k} }} "
        f"set_global_variable = {{ name = {MOD_ID}_edit_fitn "
        f"value = global_var:{MOD_ID}_bn{vshared.index(b) + 1} }} }}\n"
        for k, b in enumerate(villages_, start=1))
    out.append(f"""
# How many buildings of the chosen good stand on the ground right now.
#
# `_edit_fitn` means «where could it go» for «+1» and «how many are there» for
# «−1», because the two answers are what the window has to say when a press does
# nothing and the two questions never both apply.
# Scope: country
{MOD_ID}_edit_count_held = {{
\tset_global_variable = {{ name = {MOD_ID}_edit_fitn value = 0 }}
{held}}}

""")

    # ---- the editor's own fair share, and it is not the plan's ---------------
    #
    # **`_plan_quota` divides the whole ground by every good it can make.** The
    # editor cannot use that number once anything has been pinned: a good the
    # player locked at fifteen is eating fifteen rooms that the rest can never
    # have, and a share computed as though those rooms were still on the table
    # is a share nobody can reach. His own question, and the answer is yes --
    # «общее число ВСЕХ домиков должно измениться с лимита 5 на более низкое или
    # высокое?»
    #
    #     share = (rooms − what the pinned goods hold) ÷ (goods still free)
    #
    # A pinned good is one the player pressed («+1» or «−1» writes `_lock<n>`)
    # or flagged «не нужен» (`_skip<n>`). **The rooms are counted from `_pn<n>`
    # and not from `_lock<n>`**, though the two agree by construction: `_pn<n>`
    # is what the good actually holds, and if the two ever part company the
    # share must follow the ground rather than the intention.
    #
    # **Only goods this land can make are counted**, `_ng<n> > 0`, for the same
    # reason `_plan_set_quota` uses `_plan_scored`: a good nothing here can
    # produce must not take a share and shrink everyone else's.
    #
    # `_esh<n>` is the shortfall that falls out of it -- how far below the share
    # each free good sits -- computed here so the fill can read one global and
    # compare, rather than doing arithmetic inside a `limit`, which script
    # cannot do.
    unpin = "".join(
        f"\tremove_global_variable = {MOD_ID}_lock{i}\n"
        for i in range(1, len(order) + 1))
    quota_scan = "".join(
        f"""\tif = {{
\t\tlimit = {{ global_var:{MOD_ID}_ng{i} > 0 }}
\t\tif = {{
\t\t\tlimit = {{ OR = {{ has_global_variable = {MOD_ID}_lock{i} has_global_variable = {MOD_ID}_skip{i} }} }}
\t\t\tchange_global_variable = {{ name = {MOD_ID}_edit_pool_rooms subtract = global_var:{MOD_ID}_pn{i} }}
\t\t}}
\t\telse = {{
\t\t\tchange_global_variable = {{ name = {MOD_ID}_edit_free add = 1 }}
\t\t}}
\t}}
"""
        for i in range(1, len(order) + 1))
    # **The share is per good, because an RGO already counts against it.** The
    # plan has always done this -- `_pq<n>` is `quota - _nrgo<n>`, floored at 1
    # -- and the editor did not: it compared every good against the same flat
    # number, so a good the ground already yields three times as an RGO was
    # filled to the same six buildings as one it yields never. He caught it,
    # 2026-09-06: «не учитывая что их аналогичных РГО уже есть там по 3 штуки, и
    # того счёт для них по сути уже 9, а всего остального 6». Same arithmetic as
    # the plan now, and the same floor.
    #
    # **`has_global_variable` before the subtraction**: `_nrgo<n>` is written by
    # `_plan_prepare`, so it does not exist until a plan has been run once, and
    # the editor can be opened before that.
    shares = "".join(
        f"""\tset_global_variable = {{ name = {MOD_ID}_eq{i} value = global_var:{MOD_ID}_edit_quota }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_nrgo{i} }}
\t\tchange_global_variable = {{ name = {MOD_ID}_eq{i} subtract = global_var:{MOD_ID}_nrgo{i} }}
\t}}
\tchange_global_variable = {{ name = {MOD_ID}_eq{i} max = 1 }}
"""
        for i in range(1, len(order) + 1))
    # **The other side of the same number.** `_esh<n>` is how far a good is below
    # its share and the fill reads it; `_exs<n>` is how far it is above, and the
    # eviction reads it. Both floored at zero, both computed once a press.
    excesses = "".join(
        f"""\tset_global_variable = {{ name = {MOD_ID}_exs{i} value = 0 }}
\tif = {{
\t\tlimit = {{ global_var:{MOD_ID}_pn{i} > global_var:{MOD_ID}_eq{i} }}
\t\tset_global_variable = {{ name = {MOD_ID}_exs{i} value = global_var:{MOD_ID}_pn{i} }}
\t\tchange_global_variable = {{ name = {MOD_ID}_exs{i} subtract = global_var:{MOD_ID}_eq{i} }}
\t}}
"""
        for i in range(1, len(order) + 1))
    shortfalls = "".join(
        f"""\tset_global_variable = {{ name = {MOD_ID}_esh{i} value = 0 }}
\tif = {{
\t\tlimit = {{
\t\t\tglobal_var:{MOD_ID}_ng{i} > 0
\t\t\tNOT = {{ has_global_variable = {MOD_ID}_lock{i} }}
\t\t\tNOT = {{ has_global_variable = {MOD_ID}_skip{i} }}
\t\t\tglobal_var:{MOD_ID}_pn{i} < global_var:{MOD_ID}_eq{i}
\t\t}}
\t\tset_global_variable = {{ name = {MOD_ID}_esh{i} value = global_var:{MOD_ID}_eq{i} }}
\t\tchange_global_variable = {{ name = {MOD_ID}_esh{i} subtract = global_var:{MOD_ID}_pn{i} }}
\t}}
"""
        for i in range(1, len(order) + 1))
    out.append(f"""
# Every pin released, and nothing else touched.
#
# **The pin needed a way out.** It is written by every «+1» and «−1», so a few
# minutes of editing pins most of the ground -- his 192 presses left 16 goods
# pinned holding 126 of 192 rooms -- and until this button the only way back was
# «Пересчитать» on the mod's page, which throws the edited plan away as well.
# This releases the pins and leaves the plan exactly where it stands: the shares
# are recomputed over all the goods again, and the next «−1» fills by them.
#
# The «не нужен» flags are not touched. They are a different statement and have
# their own control.
# Scope: country
{MOD_ID}_edit_unpin_all = {{
{unpin}	{MOD_ID}_edit_set_quota = yes
}}

# **Where the editor ends.** `_lock<n>`, `_skip<n>`, the share below, the star in
# a cell -- **all of it belongs to the editor window and to nothing else.**
# Pressing «План» on the mod's page gives a fresh plan, full stop: it does not
# read a pin, a flag, or anything the editor did. That was crossed on
# 2026-09-05, when `_pq<n>` was held at 1 for a flagged good and the open ladder
# was taught to skip it -- so a click in the editor quietly steered the next
# global plan. His words, 2026-09-06: «слава богу я получаю просто новый план, а
# не план в котором какой-то домик закреплён на лимите 1».
#
# The flag's real scope is «never top this good up **while editing**», on this
# ground and the next. It survives a replan because it is the player's standing
# preference for the editor -- not because the plan owes it anything.

# The share a good still free is entitled to, and how far each one is below it.
#
# Recomputed at the top of every press, because a press can pin a good and the
# next press must see it. Cheap: two passes over the goods and no walk of the
# ground at all.
# Scope: country
{MOD_ID}_edit_set_quota = {{
\tset_global_variable = {{ name = {MOD_ID}_edit_pool_rooms value = global_var:{MOD_ID}_plan_rooms }}
\tset_global_variable = {{ name = {MOD_ID}_edit_free value = 0 }}
{quota_scan}\tset_global_variable = {{ name = {MOD_ID}_edit_quota value = global_var:{MOD_ID}_edit_pool_rooms }}
\tchange_global_variable = {{ name = {MOD_ID}_edit_quota max = 0 }}
\tif = {{
\t\tlimit = {{ global_var:{MOD_ID}_edit_free > 0 }}
\t\tchange_global_variable = {{ name = {MOD_ID}_edit_quota divide = {MOD_ID}_edit_free_value }}
\t}}
\t# The same floor `_plan_set_quota` carries and for the same reason: a ground
\t# too small to give every free good one building still owes each of them one.
\tchange_global_variable = {{ name = {MOD_ID}_edit_quota max = 1 }}
{shares}{shortfalls}{excesses}}}

""")

    # ---- what the walk stood on, in words ------------------------------------
    #
    # The trace above is numbers, which the diagnostics read and the window
    # cannot. **The press line names three things** -- the good pressed, the
    # location, and the good that gave way -- and two of them are indices at the
    # moment the walk knows them. A number cannot be turned into a name in
    # localization, so the scope itself is parked in a global and the label
    # reads `GetGlobalVariable(...).GetGoods.GetName` off it: the same trick the
    # location panel's `_r_good_<n>` rows already use, one scope up.
    #
    # `_esg` is the victim on «+1» and the good that took the room on «−1» --
    # the same variable, both walks -- so one dispatch serves both.
    name_esg = "".join(
        f"\tif = {{ limit = {{ var:{MOD_ID}_esg = {i} }}\n"
        f"\t\tset_global_variable = {{ name = {MOD_ID}_ev_esg_s value = goods:{good} }} }}\n"
        for i, good in enumerate(order, start=1))
    out.append(f"""
# The good `_esg` names, parked as a scope so the press line can print it.
#
# Called from inside both ordered walks, standing on the location: `_esg` is a
# location variable and there is nowhere else to read it. It is only meaningful
# where the walk set it -- `> 0` -- and the global is removed rather than zeroed
# before every press, so «ничего не вытеснено» leaves nothing behind to print.
# Scope: location
{MOD_ID}_edit_name_esg = {{
{name_esg}}}

""")

    # **The press journal reads through the report's own scratch globals.**
    # `_dv<n>` is filled by an effect and `_dg<n>` is the script value that reads
    # it back, because the guard has to live in an effect: a script value that
    # guards itself with `value = 0` plus `if = { ... add = ... }` reads zero in
    # silence, and that is what emptied the first report of 2026-09-02.
    press_fields = (f"{MOD_ID}_edit_presses", f"{MOD_ID}_edit_op",
                    f"{MOD_ID}_edit_good", f"{MOD_ID}_ev_hit",
                    f"{MOD_ID}_edit_done", f"{MOD_ID}_edit_fail",
                    f"{MOD_ID}_edit_norefill", f"{MOD_ID}_ev_esg",
                    f"{MOD_ID}_edit_evicted", f"{MOD_ID}_edit_rfrom",
                    f"{MOD_ID}_edit_rto", f"{MOD_ID}_edit_right",
                    f"{MOD_ID}_edit_rshort")
    assert len(press_fields) <= DIAG_SCRATCH, (
        f"the press line parks {len(press_fields)} numbers and there are only "
        f"{DIAG_SCRATCH} scratch globals: raise `DIAG_SCRATCH`")
    park = "".join(
        f"\tset_global_variable = {{ name = {MOD_ID}_dv{slot} value = 0 }}\n"
        f"\tif = {{ limit = {{ has_global_variable = {source} }} "
        f"set_global_variable = {{ name = {MOD_ID}_dv{slot} "
        f"value = global_var:{source} }} }}\n"
        for slot, source in enumerate(press_fields, start=1))
    r1, r2, r3, r4, r5, r6, r7, r8, r9, r10, r11, r12, r13 = (
        f"[GuiScope.SetRoot(GetPlayer.MakeScope).ScriptValue('{MOD_ID}_dg{slot}')|0]"
        for slot in range(1, len(press_fields) + 1))

    out.append(f"""
# The walk's trace, cleared before every press.
#
# **Zero and «no walk happened» must not look alike.** `_ev_hit` is 0 when the
# ordered walk found no candidate at all, and 1 when it stood somewhere -- and
# then the rest of these say what it saw there. The diagnostics print them; that
# is the whole reason they exist. The owner, 2026-09-04: «Добавляй скан
# информации для себя в диагностике на функцию редактора, чтобы ты видел чё там
# происходит.»
# Scope: country
{MOD_ID}_edit_clear_trace = {{
\tset_global_variable = {{ name = {MOD_ID}_ev_hit value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_ev_town value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_ev_load value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_ev_load2 value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_ev_esg value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_ev_esw value = 0 }}
\t# **The three the press line is written from, and they are scopes, not
\t# numbers.** A scope variable has no zero to be set to, so it is removed
\t# instead -- and it must be, because the line names what it finds: a stale
\t# location left over from the previous press would be read as this one's.
\tremove_global_variable = {MOD_ID}_ev_loc
\tremove_global_variable = {MOD_ID}_ev_esg_s
\tset_global_variable = {{ name = {MOD_ID}_edit_evicted value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_edit_room value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_edit_mark value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_edit_rshort value = 0 }}
}}


# **The press journal, one line a press, straight into `debug.log`.**
#
# The changes window is a diff against the saved plan and not a log: two presses
# on the same location merge into one row and the order of them is gone. The
# owner, 2026-09-05: «В окне изменений -- всё смешивается. Там нет хронологии
# изменений… Так что сам проверяй всё в диагностике.» A diff cannot hold
# chronology, and the log already is chronology -- it is written in press order
# by construction and nothing has to remember anything.
#
# **The location is named by `debug_log_scopes`, from inside its own scope.** A
# `debug_log` string cannot reach a scope, and `_ev_loc` is a global holding one,
# so the effect steps into it and lets the engine write the name on the line
# above. That is the same trick every `L` block of the report uses.
#
# Numbers go through the report's own scratch globals, because
# `[GuiScope.SetRoot(GetPlayer.MakeScope).ScriptValue(...)]` is the one form that
# reads from a `debug_log` anywhere -- measured 2026-09-02. Goods are numbers
# here and names in the report's `G<n>` lines: `tools/diag.py` puts the two
# together, and baking 47 branches into every press to save it the trouble would
# cost a dispatch on the hot path for nothing.
# Scope: country
{MOD_ID}_edit_journal = {{
{park}\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_ev_loc }}
\t\tglobal_var:{MOD_ID}_ev_loc = {{
\t\t\tdebug_log_scopes = no
\t\t\t# **Метка, потому что «строка выше» -- не адрес.** В первом прогоне
\t\t\t# 2026-09-06 между именем локации и строкой нажатия влезла
\t\t\t# `Important assertion failed: … (Getting player in synchronous
\t\t\t# state)` -- движок ругается на `GetPlayer` внутри `debug_log`, один
\t\t\t# раз за сессию, -- и читалка подписала нажатие ею. Метка не читает
\t\t\t# ничего: между ней и именем встать нечему.
\t\t\tdebug_log = "WTP PRESSAT"
\t\t}}
\t}}
\tdebug_log = "WTP PRESS n={r1} op={r2} good={r3} right={r12} hit={r4} | done={r5} fail={r6} norefill={r7} | esg={r8} evicted={r9} | rfrom={r10} rto={r11} short={r13}"
}}

# One scan of every candidate: who could hold this good, what it would cost
# there, and how many qualified. Called twice by `{MOD_ID}_edit_add` — once
# strict, once open — so the two passes cannot drift apart.
# Scope: country
{MOD_ID}_edit_scan_pass = {{
\tset_global_variable = {{ name = {MOD_ID}_edit_fitn value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_edit_cands value = 0 }}
\tevery_in_global_list = {{
\t\tvariable = {MOD_ID}_candidates
\t\tset_variable = {{ name = {MOD_ID}_esc value = 0 }}
\t\tset_variable = {{ name = {MOD_ID}_esv value = 0 }}
\t\t{MOD_ID}_edit_worst = yes
\t}}
{fit_dispatch}{scan_dispatch}\t# **Two counts, because two different things read as «не дало правило».**
\t# `_edit_fitn` is how many locations could hold this good at all -- the
\t# ground's own answer, and 0 means it already stands everywhere this land
\t# can make it. `_edit_cands` is how many of those had a free room or a
\t# building that may be taken out. The owner pressed «+1» on iron and was
\t# told a rule refused it; iron can be made in four locations of Westphalia
\t# and stood in all four. That is the ground, not a rule, and saying so
\t# needs the number.
\tevery_in_global_list = {{
\t\tvariable = {MOD_ID}_candidates
\t\tlimit = {{ var:{MOD_ID}_esc = 1 }}
\t\tchange_global_variable = {{ name = {MOD_ID}_edit_cands add = 1 }}
\t}}
}}
""")

    out.append(f"""
# **One more building of the chosen good, and exactly one.**
#
# The ordered walk is the whole of the choice: `_esv` is what each candidate
# charges -- a free room charges nothing and outbids everything, an eviction
# charges the victim's gain -- so the highest is the least painful place, and
# `max = 1` takes it and stops. Both sides' effects are called and the one whose
# side the location is not simply does nothing, which is cheaper than asking.
# Scope: country
{MOD_ID}_edit_add = {{
\t# **The press counter, and it is a probe rather than a nicety.** A press that
\t# never reaches its effect and a press that reaches it and is refused look the
\t# same on screen -- «ничего не изменилось» -- and telling them apart has cost
\t# two runs. The window prints this number, so one look answers it: click five
\t# times, the number does not move, the button is not wired.
\tchange_global_variable = {{ name = {MOD_ID}_edit_presses add = 1 }}
\t{MOD_ID}_edit_clear_trace = yes
\tset_global_variable = {{ name = {MOD_ID}_edit_done value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_edit_fail value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_edit_norefill value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_edit_op value = 1 }}
\t{MOD_ID}_edit_set_quota = yes
\tset_global_variable = {{ name = {MOD_ID}_edit_fitn value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_edit_cands value = 0 }}
\tif = {{
\t\tlimit = {{ global_var:{MOD_ID}_edit_good > 0 }}
\t\t# **Two passes, and the second only when the first found nobody.**
\t\t# Strict: the building given up must belong to a good that is over
\t\t# its share. Open: any building that may be taken out at all. A
\t\t# location with a free room qualifies on both — it has no victim to
\t\t# ask about, and a free room outbids every eviction anyway.
\t\t#
\t\t# **Not one packed `order_by` number.** `превышение × K + выгода`
\t\t# was the other way and it is rejected: the engine's fixed-point
\t\t# limit is not known from here, and the same warning already
\t\t# stands over `_plan_order`.
\t\tset_global_variable = {{ name = {MOD_ID}_edit_strict value = 1 }}
\t\t{MOD_ID}_edit_scan_pass = yes
\t\tif = {{
\t\t\tlimit = {{ global_var:{MOD_ID}_edit_cands = 0 }}
\t\t\tset_global_variable = {{ name = {MOD_ID}_edit_strict value = 0 }}
\t\t\t{MOD_ID}_edit_scan_pass = yes
\t\t}}
\t\tordered_in_global_list = {{
\t\t\tvariable = {MOD_ID}_candidates
\t\t\tlimit = {{ var:{MOD_ID}_esc = 1 }}
\t\t\torder_by = {MOD_ID}_edit_order
\t\t\tmax = 1
\t\t\tcheck_range_bounds = no
\t\t\t# **One rule, and the walk owns the room.**
\t\t\t#
\t\t\t# The editor no longer asks the plan whether a building may stand here.
\t\t\t# `_plan_can_*` wants a free room; the editor makes the room itself, so it
\t\t\t# asks `_edit_fits_*` -- the same test with that clause removed -- and
\t\t\t# **the scan and the placement are then the same predicate**. They used to
\t\t\t# be two, and the day they disagreed the window said «поставить не
\t\t\t# удалось, и всё осталось как было» with nothing able to say why.
\t\t\t#
\t\t\t# So: evict when the location is full and has a victim, then place if the
\t\t\t# room is actually free. `_edit_worst` names a victim on every candidate
\t\t\t# -- the picker's markers need that -- so «full» and «has a victim» are
\t\t\t# asked here rather than assumed.
\t\t\t# **What the walk stood on, parked for the report.** A `debug_log` string
\t\t\t# cannot reach the item a walk is standing on, so the numbers that decide
\t\t\t# everything here -- the location's load, its victim, whether it counts as
\t\t\t# a town -- have to be copied into globals as they are read. Without this
\t\t\t# the editor is the one part of the mod the diagnostics cannot see, and
\t\t\t# 2026-09-04 is what that costs: 27 buildings over the cap and four
\t\t\t# theories about why.
\t\t\tset_global_variable = {{ name = {MOD_ID}_ev_hit value = 1 }}
\t\t\tset_global_variable = {{ name = {MOD_ID}_ev_town value = 0 }}
\t\t\tif = {{ limit = {{ {MOD_ID}_plan_is_town = yes }}
\t\t\t\tset_global_variable = {{ name = {MOD_ID}_ev_town value = 1 }} }}
\t\t\tset_global_variable = {{ name = {MOD_ID}_ev_load value = var:{MOD_ID}_load }}
\t\t\tset_global_variable = {{ name = {MOD_ID}_ev_esg value = var:{MOD_ID}_esg }}
\t\t\tset_global_variable = {{ name = {MOD_ID}_ev_esw value = var:{MOD_ID}_esw }}
\t\t\t# **And the same two in words, for the window.** The report reads the
\t\t\t# numbers above; the press line cannot, so the location the walk chose and
\t\t\t# the good it would evict are parked as scopes here as well. This is the
\t\t\t# only point in the press where both are in hand.
\t\t\t{MOD_ID}_edit_name_esg = yes
\t\t\tsave_scope_as = {MOD_ID}_ev_where
\t\t\tset_global_variable = {{ name = {MOD_ID}_ev_loc value = scope:{MOD_ID}_ev_where }}
\t\t\t# **And which press this was, on the location itself.** The changes
\t\t\t# window is a diff and cannot hold chronology, but it can be *ordered*
\t\t\t# by it: `_chg_seq` is what `{MOD_ID}_chg_order` sorts the list on, so
\t\t\t# ten «+1» on one good come out as ten rows in a row instead of
\t\t\t# scattered through the land by location id. The owner, 2026-09-06:
\t\t\t# «я ожидаю увидеть несколько строк подряд, где участвует кожа».
\t\t\tset_variable = {{ name = {MOD_ID}_chg_seq value = global_var:{MOD_ID}_edit_presses }}
\t\t\tset_global_variable = {{ name = {MOD_ID}_edit_evicted value = 0 }}
\t\t\tset_global_variable = {{ name = {MOD_ID}_edit_room value = 0 }}
\t\t\tif = {{
\t\t\t\tlimit = {{
\t\t\t\t\tvar:{MOD_ID}_esg > 0
\t\t\t\t\tOR = {{
\t\t\t\t\t\tAND = {{ {MOD_ID}_plan_is_town = yes
\t\t\t\t\t\t\tvar:{MOD_ID}_load >= global_var:{MOD_ID}_plan_cap_urban }}
\t\t\t\t\t\tAND = {{ {MOD_ID}_plan_is_town = no
\t\t\t\t\t\t\tvar:{MOD_ID}_load >= global_var:{MOD_ID}_plan_cap_rural }}
\t\t\t\t\t}}
\t\t\t\t}}
{remove_dispatch}\t\t\t\tset_global_variable = {{ name = {MOD_ID}_edit_evicted value = 1 }}
\t\t\t}}
\t\t\tif = {{
\t\t\t\tlimit = {{ OR = {{
\t\t\t\t\tAND = {{ {MOD_ID}_plan_is_town = yes
\t\t\t\t\t\tvar:{MOD_ID}_load < global_var:{MOD_ID}_plan_cap_urban }}
\t\t\t\t\tAND = {{ {MOD_ID}_plan_is_town = no
\t\t\t\t\t\tvar:{MOD_ID}_load < global_var:{MOD_ID}_plan_cap_rural }}
\t\t\t\t}} }}
\t\t\t\tset_global_variable = {{ name = {MOD_ID}_edit_room value = 1 }}
\t\t\t}}
\t\t\t# **And nothing is ever lost.** The count is taken after the eviction, so
\t\t\t# one comparison answers both cases: the plan grew, or it did not and the
\t\t\t# victim goes straight back. A press that cannot do what it says must cost
\t\t\t# nothing, and `_edit_fail` is what makes the window say so.
\t\t\tset_global_variable = {{ name = {MOD_ID}_edit_mark value = global_var:{MOD_ID}_plan_placed }}
\t\t\tif = {{
\t\t\t\tlimit = {{ global_var:{MOD_ID}_edit_room = 1 }}
{add_dispatch}\t\t\t}}
\t\t\tif = {{
\t\t\t\tlimit = {{ global_var:{MOD_ID}_plan_placed > global_var:{MOD_ID}_edit_mark }}
\t\t\t\tset_global_variable = {{ name = {MOD_ID}_edit_done value = 1 }}
\t\t\t}}
\t\t\telse = {{
\t\t\t\tset_global_variable = {{ name = {MOD_ID}_edit_fail value = 1 }}
\t\t\t\tif = {{
\t\t\t\t\tlimit = {{ global_var:{MOD_ID}_edit_evicted = 1 }}
{restore_dispatch}\t\t\t\t}}
\t\t\t}}
\t\t\tset_global_variable = {{ name = {MOD_ID}_ev_load2 value = var:{MOD_ID}_load }}
\t\t}}
\t}}
\tif = {{
\t\tlimit = {{ global_var:{MOD_ID}_edit_done = 0 }}
\t\tchange_global_variable = {{ name = {MOD_ID}_edit_idle add = 1 }}
\t}}
\t{MOD_ID}_edit_journal = yes
\t{MOD_ID}_plan_rank = yes
\t# **And the window's rows again.** A location the edit gave its first building
\t# is not in `_plan_results` and would not appear until something else refilled
\t# it; the goods already in a row read live off the location, so without this
\t# an edit is half-visible, which is the worst of the three states.
\t{MOD_ID}_plan_show = yes
}}

# **One building of the chosen good taken out, and the room given to whatever
# suits it best afterwards.** «Он уступает место тому у чего забрал слоты.»
#
# The walk takes the good's *worst* placement, which is why the scan stores
# `{RANK_SCALE} - gain`: `order_by` reads highest-first and there is no other way
# to ask it for a minimum.
# Scope: country
{MOD_ID}_edit_drop = {{
\tchange_global_variable = {{ name = {MOD_ID}_edit_presses add = 1 }}
\t{MOD_ID}_edit_clear_trace = yes
\tset_global_variable = {{ name = {MOD_ID}_edit_done value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_edit_fail value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_edit_norefill value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_edit_op value = 2 }}
\tset_global_variable = {{ name = {MOD_ID}_edit_nofill value = global_var:{MOD_ID}_edit_good }}
\t{MOD_ID}_edit_set_quota = yes
\t{MOD_ID}_edit_count_held = yes
\tset_global_variable = {{ name = {MOD_ID}_edit_cands value = 0 }}
\tif = {{
\t\tlimit = {{ global_var:{MOD_ID}_edit_good > 0 }}
\t\tevery_in_global_list = {{
\t\t\tvariable = {MOD_ID}_candidates
\t\t\tset_variable = {{ name = {MOD_ID}_esc value = 0 }}
\t\t\tset_variable = {{ name = {MOD_ID}_esv value = 0 }}
\t\t}}
""")
    for index, good in enumerate(order, start=1):
        out.append(f"""\t\tif = {{
\t\t\tlimit = {{ global_var:{MOD_ID}_edit_good = {index} global_var:{MOD_ID}_pn{index} > 1 }}
\t\t\tevery_in_global_list = {{
\t\t\t\tvariable = {MOD_ID}_candidates
\t\t\t\tlimit = {{ is_target_in_variable_list = {{ name = {MOD_ID}_plan_goods target = goods:{good} }} }}
\t\t\t\tset_variable = {{ name = {MOD_ID}_esc value = 1 }}
\t\t\t\tset_variable = {{ name = {MOD_ID}_esv value = {RANK_SCALE} }}
\t\t\t\tif = {{
\t\t\t\t\tlimit = {{ {MOD_ID}_plan_is_town = yes }}
\t\t\t\t\tchange_variable = {{ name = {MOD_ID}_esv subtract = var:{MOD_ID}_p{index} }}
\t\t\t\t}}
\t\t\t\telse = {{
\t\t\t\t\tchange_variable = {{ name = {MOD_ID}_esv subtract = var:{MOD_ID}_pr{index} }}
\t\t\t\t}}
\t\t\t}}
\t\t}}
""")
    for k, building in enumerate(villages_, start=1):
        index = len(order) + k
        vb = vshared.index(building) + 1
        # Деревня опознаётся на локации своим домиком, а не товаром: товар в
        # `_plan_goods` она кладёт только ради строки.
        out.append(f"""\t\tif = {{
\t\t\tlimit = {{ global_var:{MOD_ID}_edit_good = {index} global_var:{MOD_ID}_bn{vb} > 0 }}
\t\t\tevery_in_global_list = {{
\t\t\t\tvariable = {MOD_ID}_candidates
\t\t\t\tlimit = {{ is_target_in_variable_list = {{ name = {MOD_ID}_plan_builds target = building_type:{building} }} }}
\t\t\t\tset_variable = {{ name = {MOD_ID}_esc value = 1 }}
\t\t\t\tset_variable = {{ name = {MOD_ID}_esv value = {RANK_SCALE} }}
\t\t\t\tchange_variable = {{ name = {MOD_ID}_esv subtract = var:{MOD_ID}_vb{k} }}
\t\t\t}}
\t\t}}
""")

    drop_dispatch = "".join(
        f"\t\t\tif = {{ limit = {{ global_var:{MOD_ID}_edit_good = {i} }}\n"
        f"{call('edit_remove', i, chr(9) * 4)}\t\t\t}}\n"
        for i in range(1, PICK_N + 1))
    # **The freed room goes to the good furthest below its share, not to the
    # richest.** His words, 2026-09-04: «остальные, у которых не хватало до 7
    # равномерных, начнут по 1 заполнять места, чтобы добрать свою
    # равнозначность по количеству. А если у всех уже и так равность… туда будут
    # вставать по своей выгоде от земли.» Gain decides only a tie -- and «no
    # shortfall at all» is a tie at zero, which is that second sentence.
    #
    # **This is also why the lock had to be built in the same step.** Under
    # hunger alone, a good the player has just pressed down to one building is
    # the hungriest thing on the ground and climbs straight back into the next
    # good's rooms -- he found that himself, walking court materials from 7 to 1
    # and then herbs from 8 to 1. `_lock<n>` is what keeps a pressed good out of
    # this scan entirely, and on 2026-09-05 he confirmed the behaviour this must
    # preserve: goods he drops by hand stay dropped.
    #
    # Two keys and one pass, not a packed number: `_esd` carries the best
    # shortfall so far and `_esw` the gain that goes with it, so «strictly
    # hungrier» and «equally hungry but worth more» are two arms of one `OR`.
    fill = "".join(
        f"\tif = {{\n"
        f"\t\tlimit = {{\n"
        # **Never the good that just left.** It fits by construction -- it stood
        # here a moment ago -- and it is almost always the best fit as well, so
        # without this «−1» removes a building and hands the room straight back
        # to the same good. The press then reports «сделано» and nothing on the
        # map has changed, which is what he saw on 2026-09-04.
        f"\t\t\tNOT = {{ global_var:{MOD_ID}_edit_nofill = {i} }}\n"
        # Pinned by a press, or flagged «не нужен»: stands where it was put.
        f"\t\t\tNOT = {{ has_global_variable = {MOD_ID}_lock{i} }}\n"
        f"\t\t\tNOT = {{ has_global_variable = {MOD_ID}_skip{i} }}\n"
        f"\t\t\tOR = {{ {MOD_ID}_edit_fits_town_{i} = yes {MOD_ID}_edit_fits_rural_{i} = yes }}\n"
        f"\t\t\tOR = {{\n"
        f"\t\t\t\tvar:{MOD_ID}_esd < global_var:{MOD_ID}_esh{i}\n"
        f"\t\t\t\tAND = {{\n"
        f"\t\t\t\t\tvar:{MOD_ID}_esd = global_var:{MOD_ID}_esh{i}\n"
        f"\t\t\t\t\tOR = {{\n"
        f"\t\t\t\t\t\tAND = {{ {MOD_ID}_plan_is_town = yes var:{MOD_ID}_p{i} > var:{MOD_ID}_esw }}\n"
        f"\t\t\t\t\t\tAND = {{ {MOD_ID}_plan_is_town = no var:{MOD_ID}_pr{i} > var:{MOD_ID}_esw }}\n"
        f"\t\t\t\t\t}}\n"
        f"\t\t\t\t}}\n"
        f"\t\t\t}}\n"
        f"\t\t}}\n"
        f"\t\tset_variable = {{ name = {MOD_ID}_esd value = global_var:{MOD_ID}_esh{i} }}\n"
        f"\t\tif = {{ limit = {{ {MOD_ID}_plan_is_town = yes }}\n"
        f"\t\t\tset_variable = {{ name = {MOD_ID}_esw value = var:{MOD_ID}_p{i} }} }}\n"
        f"\t\telse = {{ set_variable = {{ name = {MOD_ID}_esw value = var:{MOD_ID}_pr{i} }} }}\n"
        f"\t\tset_variable = {{ name = {MOD_ID}_esg value = {i} }}\n"
        f"\t}}\n"
        for i in range(1, len(order) + 1))
    fill_dispatch = "".join(
        f"\tif = {{ limit = {{ var:{MOD_ID}_esg = {i} }}\n"
        f"{call('edit_place', i, chr(9) * 2)}\t}}\n"
        for i in range(1, len(order) + 1))
    out.append(f"""\t\tevery_in_global_list = {{
\t\t\tvariable = {MOD_ID}_candidates
\t\t\tlimit = {{ var:{MOD_ID}_esc = 1 }}
\t\t\tchange_global_variable = {{ name = {MOD_ID}_edit_cands add = 1 }}
\t\t}}
\t\tordered_in_global_list = {{
\t\t\tvariable = {MOD_ID}_candidates
\t\t\tlimit = {{ var:{MOD_ID}_esc = 1 }}
\t\t\torder_by = {MOD_ID}_edit_order
\t\t\tmax = 1
\t\t\tcheck_range_bounds = no
\t\t\t# **The same trace «+1» keeps, and «−1» kept none of it.** The report
\t\t\t# printed zeros for every «−1» press and read as «the walk found nothing»,
\t\t\t# which is the one thing it must never say by accident.
\t\t\tset_global_variable = {{ name = {MOD_ID}_ev_hit value = 1 }}
\t\t\tset_global_variable = {{ name = {MOD_ID}_ev_town value = 0 }}
\t\t\tif = {{ limit = {{ {MOD_ID}_plan_is_town = yes }}
\t\t\t\tset_global_variable = {{ name = {MOD_ID}_ev_town value = 1 }} }}
\t\t\tset_global_variable = {{ name = {MOD_ID}_ev_load value = var:{MOD_ID}_load }}
\t\t\tsave_scope_as = {MOD_ID}_ev_where
\t\t\tset_global_variable = {{ name = {MOD_ID}_ev_loc value = scope:{MOD_ID}_ev_where }}
\t\t\t# **And which press this was, on the location itself.** The changes
\t\t\t# window is a diff and cannot hold chronology, but it can be *ordered*
\t\t\t# by it: `_chg_seq` is what `{MOD_ID}_chg_order` sorts the list on, so
\t\t\t# ten «+1» on one good come out as ten rows in a row instead of
\t\t\t# scattered through the land by location id. The owner, 2026-09-06:
\t\t\t# «я ожидаю увидеть несколько строк подряд, где участвует кожа».
\t\t\tset_variable = {{ name = {MOD_ID}_chg_seq value = global_var:{MOD_ID}_edit_presses }}
{drop_dispatch}\t\t\t# The room is free now; the good furthest below its share takes it.
\t\t\t{MOD_ID}_edit_fill_room = yes
\t\t\t# **What the fill just put here, remembered for the reshuffle.** Which
\t\t\t# good takes the room is settled by shortfall, and that is right; *where*
\t\t\t# it lands is settled by which press freed which room, and that is
\t\t\t# nobody's decision at all. `{MOD_ID}_edit_reshuffle` trades these
\t\t\t# buildings between their own locations afterwards.
\t\t\tif = {{
\t\t\t\tlimit = {{ var:{MOD_ID}_esg > 0 }}
\t\t\t\tset_variable = {{ name = {MOD_ID}_fillg value = var:{MOD_ID}_esg }}
\t\t\t\tif = {{
\t\t\t\t\tlimit = {{ NOT = {{ is_target_in_global_variable_list = {{ name = {MOD_ID}_edit_fillset target = this }} }} }}
\t\t\t\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_edit_fillset target = this }}
\t\t\t\t}}
\t\t\t}}
\t\t\t# **Who took it, for the report and for the press line.** On «−1» `_esg` is
\t\t\t# the good that moved in rather than a victim, and both readings are the
\t\t\t# walk's answer to «what changed here», so they share the globals.
\t\t\tset_global_variable = {{ name = {MOD_ID}_ev_esg value = var:{MOD_ID}_esg }}
\t\t\tset_global_variable = {{ name = {MOD_ID}_ev_esw value = var:{MOD_ID}_esw }}
\t\t\t{MOD_ID}_edit_name_esg = yes
\t\t\tset_global_variable = {{ name = {MOD_ID}_ev_load2 value = var:{MOD_ID}_load }}
\t\t\t# **Whether anything took the room.** «−1» has done its job either way --
\t\t\t# the building is out, which is what was asked -- but «освободилось и
\t\t\t# занять нечем» and «освободилось, встал такой-то» are different answers
\t\t\t# and the window has to give the right one.
\t\t\tif = {{
\t\t\t\tlimit = {{ var:{MOD_ID}_esg = 0 }}
\t\t\t\tset_global_variable = {{ name = {MOD_ID}_edit_norefill value = 1 }}
\t\t\t}}
\t\t\tset_global_variable = {{ name = {MOD_ID}_edit_done value = 1 }}
\t\t}}
\t}}
\t{MOD_ID}_edit_reshuffle = yes
\tif = {{
\t\tlimit = {{ global_var:{MOD_ID}_edit_done = 0 }}
\t\tchange_global_variable = {{ name = {MOD_ID}_edit_idle add = 1 }}
\t}}
\t{MOD_ID}_edit_journal = yes
\t{MOD_ID}_plan_rank = yes
\t# **And the window's rows again.** A location the edit gave its first building
\t# is not in `_plan_results` and would not appear until something else refilled
\t# it; the goods already in a row read live off the location, so without this
\t# an edit is half-visible, which is the worst of the three states.
\t{MOD_ID}_plan_show = yes
}}
""")

    # ---- step 2а: the fill's buildings, traded between their own locations ---
    #
    # **His words, 2026-09-05:** «когда я нажимаю "−1" допустим освобождая 9
    # ячеек — их заполняют по степени лимита и недобора… им не особо важно встают
    # они в бонус или нет. После такого заполнения все новопоставленные домики
    # должны переменяться местами в поисках наибольшей выгоды от земли.»
    #
    # **He named a real flaw of the order.** The fill puts one building in the
    # room this press freed: *which* good is decided by shortfall, which is
    # right, and *where* by the accident of press order, which nothing decides.
    # Good X can take a room that suits good Y, placed a press later, far better.
    #
    # **The scope is strictly the fill's own buildings and their own locations.**
    # No count changes, so the share, the locks and the covering constraint are
    # all untouched, and charters and everything placed earlier are not looked
    # at. That makes it a pure improvement of the gain and nothing else.
    #
    # **A round is one pass over pairs, and rounds repeat while one swaps.** The
    # round is one effect called three times behind a guard rather than a `while`
    # — the same body, no unrolling, and a bound that cannot run away. A swap is
    # taken only on a strict improvement, so a pair cannot oscillate.
    town_of = "\n".join(
        f"\t\t\t\tset_global_variable = {{ name = {MOD_ID}_rsA{i} value = var:{MOD_ID}_p{i} }}"
        for i in range(1, len(order) + 1))
    rural_of = "\n".join(
        f"\t\t\t\tset_global_variable = {{ name = {MOD_ID}_rsA{i} value = var:{MOD_ID}_pr{i} }}"
        for i in range(1, len(order) + 1))
    fits_of = "".join(
        f"\t\t\tset_global_variable = {{ name = {MOD_ID}_rsF{i} value = 0 }}\n"
        f"\t\t\tif = {{\n"
        f"\t\t\t\tlimit = {{ OR = {{ {MOD_ID}_edit_fits_town_{i} = yes "
        f"{MOD_ID}_edit_fits_rural_{i} = yes }} }}\n"
        f"\t\t\t\tset_global_variable = {{ name = {MOD_ID}_rsF{i} value = 1 }}\n"
        f"\t\t\t}}\n"
        for i in range(1, len(order) + 1))
    # Is the good the fill left here still standing? A later «−1» may have taken
    # it out, and a stale marker would trade a building that is not there.
    still_here = "".join(
        f"\t\t\tif = {{ limit = {{ var:{MOD_ID}_fillg = {i} is_target_in_variable_list = "
        f"{{ name = {MOD_ID}_plan_goods target = goods:{order[i - 1]} }} }} "
        f"set_global_variable = {{ name = {MOD_ID}_rs_ok value = 1 }} }}\n"
        for i in range(1, len(order) + 1))
    # B's side of the comparison: what B pays for its own good, what A would pay
    # for it, and whether A may hold it at all.
    read_b = "".join(
        f"\t\t\t\tif = {{\n"
        f"\t\t\t\t\tlimit = {{ var:{MOD_ID}_fillg = {i} }}\n"
        f"\t\t\t\t\tset_global_variable = {{ name = {MOD_ID}_rs_bg value = {i} }}\n"
        f"\t\t\t\t\tif = {{ limit = {{ {MOD_ID}_plan_is_town = yes }}\n"
        f"\t\t\t\t\t\tset_global_variable = {{ name = {MOD_ID}_rs_bb value = var:{MOD_ID}_p{i} }} }}\n"
        f"\t\t\t\t\telse = {{ set_global_variable = {{ name = {MOD_ID}_rs_bb "
        f"value = var:{MOD_ID}_pr{i} }} }}\n"
        f"\t\t\t\t\tset_global_variable = {{ name = {MOD_ID}_rs_ab "
        f"value = global_var:{MOD_ID}_rsA{i} }}\n"
        f"\t\t\t\t\tset_global_variable = {{ name = {MOD_ID}_rs_afit "
        f"value = global_var:{MOD_ID}_rsF{i} }}\n"
        f"\t\t\t\t}}\n"
        for i in range(1, len(order) + 1))
    # A's good, asked of B: what B would pay for it, what A pays now, and whether
    # B may hold it.
    read_a = "".join(
        f"\t\t\t\tif = {{\n"
        f"\t\t\t\t\tlimit = {{ global_var:{MOD_ID}_rs_ag = {i} }}\n"
        f"\t\t\t\t\tif = {{ limit = {{ {MOD_ID}_plan_is_town = yes }}\n"
        f"\t\t\t\t\t\tset_global_variable = {{ name = {MOD_ID}_rs_ba value = var:{MOD_ID}_p{i} }} }}\n"
        f"\t\t\t\t\telse = {{ set_global_variable = {{ name = {MOD_ID}_rs_ba "
        f"value = var:{MOD_ID}_pr{i} }} }}\n"
        f"\t\t\t\t\tset_global_variable = {{ name = {MOD_ID}_rs_aa "
        f"value = global_var:{MOD_ID}_rsA{i} }}\n"
        f"\t\t\t\t\tset_global_variable = {{ name = {MOD_ID}_rs_bfit value = 0 }}\n"
        f"\t\t\t\t\tif = {{\n"
        f"\t\t\t\t\t\tlimit = {{ OR = {{ {MOD_ID}_edit_fits_town_{i} = yes "
        f"{MOD_ID}_edit_fits_rural_{i} = yes }} }}\n"
        f"\t\t\t\t\t\tset_global_variable = {{ name = {MOD_ID}_rs_bfit value = 1 }}\n"
        f"\t\t\t\t\t}}\n"
        f"\t\t\t\t}}\n"
        for i in range(1, len(order) + 1))

    def dispatch(prefix: str, key: str, tab: str) -> str:
        return "".join(
            f"{tab}if = {{ limit = {{ {key} = {i} }}\n"
            f"{call(prefix, i, tab + chr(9))}{tab}}}\n"
            for i in range(1, len(order) + 1))

    swap_b = (dispatch("edit_remove", f"var:{MOD_ID}_fillg", "\t" * 5)
              + dispatch("edit_place", f"global_var:{MOD_ID}_rs_ag", "\t" * 5))
    swap_a = (dispatch("edit_remove", f"global_var:{MOD_ID}_rs_ag", "\t" * 6)
              + dispatch("edit_place", f"global_var:{MOD_ID}_rs_bg", "\t" * 6))

    out.append(f"""
# **One free room, given to the good furthest below its share.**
#
# Called by «−1», which frees a room by taking a building out, and by the
# charter machine, which frees rooms by taking a whole bundle out. **The
# exclusion is `_edit_nofill` and not `_edit_good`**: «−1» must not hand the room
# straight back to the good it just took out -- it fits by construction and is
# almost always the best fit, so the press would report «сделано» with nothing
# changed on the map -- but a charter press has no such good and excluding
# whatever the goods picker happens to point at would be an accident.
#
# **The freed room goes to the good furthest below its share, not to the
# richest.** His words, 2026-09-04: «остальные, у которых не хватало до 7
# равномерных, начнут по 1 заполнять места, чтобы добрать свою
# равнозначность по количеству. А если у всех уже и так равность… туда будут
# вставать по своей выгоде от земли.» Gain decides only a tie -- and «no
# shortfall at all» is a tie at zero, which is that second sentence.
#
# **This is also why the lock had to be built in the same step.** Under
# hunger alone, a good the player has just pressed down to one building is
# the hungriest thing on the ground and climbs straight back into the next
# good's rooms -- he found that himself, walking court materials from 7 to 1
# and then herbs from 8 to 1. `_lock<n>` is what keeps a pressed good out of
# this scan entirely, and on 2026-09-05 he confirmed the behaviour this must
# preserve: goods he drops by hand stay dropped.
#
# Two keys and one pass, not a packed number: `_esd` carries the best
# shortfall so far and `_esw` the gain that goes with it, so «strictly
# hungrier» and «equally hungry but worth more» are two arms of one `OR`.
# Scope: location
{MOD_ID}_edit_fill_room = {{
\tset_variable = {{ name = {MOD_ID}_esw value = -1 }}
\tset_variable = {{ name = {MOD_ID}_esg value = 0 }}
\t# Below every shortfall, which is floored at zero, so the first good
\t# that fits wins outright and the rest is a comparison between goods.
\tset_variable = {{ name = {MOD_ID}_esd value = -1 }}
{fill}{fill_dispatch}}}
""")

    out.append(f"""
# Everything the reshuffle remembers, forgotten. A fresh plan or a loaded slot
# is a different set of buildings, and a marker left on a location would trade
# something the fill never put there.
# Scope: country
{MOD_ID}_edit_clear_fillset = {{
\tevery_in_global_list = {{
\t\tvariable = {MOD_ID}_edit_fillset
\t\tremove_variable = {MOD_ID}_fillg
\t}}
\t# **И номера нажатий тоже.** Они упорядочивают «Показать изменения», а
\t# счётчик нажатий обнуляется вместе с окном: оставленный номер разложил
\t# бы новую правку по порядку старой.
\tevery_in_global_list = {{
\t\tvariable = {MOD_ID}_plan_touched
\t\tremove_variable = {MOD_ID}_chg_seq
\t}}
\tclear_global_variable_list = {MOD_ID}_edit_fillset
\tclear_global_variable_list = {MOD_ID}_edit_fillset2
\tset_global_variable = {{ name = {MOD_ID}_rs_swaps value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_rs_rounds value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_rs_pairs value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_rs_same value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_rs_nofit value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_rs_worse value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_rs_gain value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_rs_did value = 0 }}
}}

# Three rounds at most, and it stops the moment one of them trades nothing.
# Scope: country
{MOD_ID}_edit_reshuffle = {{
\t# **What the trading is worth, kept as one number.** The gain is the
\t# whole reason this pass exists and nothing on screen showed it, so a
\t# run could not tell «traded nothing» from «traded and it was worth
\t# nothing» from «never ran». The changes window prints it.
\tset_global_variable = {{ name = {MOD_ID}_rs_gain0 value = global_var:{MOD_ID}_plan_gain }}
\t{MOD_ID}_edit_reshuffle_round = yes
\tif = {{
\t\tlimit = {{ global_var:{MOD_ID}_rs_did = 1 }}
\t\t{MOD_ID}_edit_reshuffle_round = yes
\t}}
\tif = {{
\t\tlimit = {{ global_var:{MOD_ID}_rs_did = 1 }}
\t\t{MOD_ID}_edit_reshuffle_round = yes
\t}}
\tchange_global_variable = {{ name = {MOD_ID}_rs_gain add = global_var:{MOD_ID}_plan_gain }}
\tchange_global_variable = {{ name = {MOD_ID}_rs_gain subtract = global_var:{MOD_ID}_rs_gain0 }}
}}

# One pass over the pairs. **`_rounds` and `_swaps` are the probe**: a reshuffle
# that never ran and one that found nothing to trade are the same picture on the
# map, and the diagnosis prints both.
# Scope: country
{MOD_ID}_edit_reshuffle_round = {{
\tchange_global_variable = {{ name = {MOD_ID}_rs_rounds add = 1 }}
\tset_global_variable = {{ name = {MOD_ID}_rs_did value = 0 }}
\t# **The inner walk reads a copy.** Iterating one list inside itself is a
\t# shape this mod has never proved, and copying it costs one pass over a
\t# handful of locations.
\tclear_global_variable_list = {MOD_ID}_edit_fillset2
\tevery_in_global_list = {{
\t\tvariable = {MOD_ID}_edit_fillset
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_edit_fillset2 target = this }}
\t}}
\tevery_in_global_list = {{
\t\tvariable = {MOD_ID}_edit_fillset
\t\tlimit = {{ has_variable = {MOD_ID}_fillg }}
\t\tsave_scope_as = {MOD_ID}_rs_a
\t\tset_global_variable = {{ name = {MOD_ID}_rs_ag value = var:{MOD_ID}_fillg }}
\t\tset_global_variable = {{ name = {MOD_ID}_rs_stop value = 0 }}
\t\tset_global_variable = {{ name = {MOD_ID}_rs_ok value = 0 }}
{still_here}\t\tif = {{
\t\t\tlimit = {{ global_var:{MOD_ID}_rs_ok = 0 }}
\t\t\tremove_variable = {MOD_ID}_fillg
\t\t}}
\t\t# **A's whole row, parked before the inner walk.** Two scopes cannot be
\t\t# read at once, so what A pays for every good and what A may hold go into
\t\t# globals here, and B compares against them in its own scope.
\t\tif = {{
\t\t\tlimit = {{ global_var:{MOD_ID}_rs_ok = 1 }}
\t\t\tif = {{
\t\t\t\tlimit = {{ {MOD_ID}_plan_is_town = yes }}
{town_of}
\t\t\t}}
\t\t\telse = {{
{rural_of}
\t\t\t}}
{fits_of}\t\t\tevery_in_global_list = {{
\t\t\t\tvariable = {MOD_ID}_edit_fillset2
\t\t\t\tlimit = {{
\t\t\t\t\tglobal_var:{MOD_ID}_rs_stop = 0
\t\t\t\t\thas_variable = {MOD_ID}_fillg
\t\t\t\t\tNOT = {{ this = scope:{MOD_ID}_rs_a }}
\t\t\t\t}}
\t\t\t\tchange_global_variable = {{ name = {MOD_ID}_rs_pairs add = 1 }}
\t\t\t\tset_global_variable = {{ name = {MOD_ID}_rs_bg value = 0 }}
\t\t\t\tset_global_variable = {{ name = {MOD_ID}_rs_afit value = 0 }}
\t\t\t\tset_global_variable = {{ name = {MOD_ID}_rs_bfit value = 0 }}
{read_b}{read_a}\t\t\t\t# What the pair is worth now, and what it would be worth traded.
\t\t\t\tset_global_variable = {{ name = {MOD_ID}_rs_now value = global_var:{MOD_ID}_rs_aa }}
\t\t\t\tchange_global_variable = {{ name = {MOD_ID}_rs_now add = global_var:{MOD_ID}_rs_bb }}
\t\t\t\tset_global_variable = {{ name = {MOD_ID}_rs_new value = global_var:{MOD_ID}_rs_ab }}
\t\t\t\tchange_global_variable = {{ name = {MOD_ID}_rs_new add = global_var:{MOD_ID}_rs_ba }}

\t\t\t\t# **Why a pair was not traded, counted.** «Traded nothing» has three
\t\t\t\t# causes that look identical on the map: both rooms hold the same
\t\t\t\t# good (a trade is a no-op), one of the two locations may not hold
\t\t\t\t# the other's good, or the trade is simply not worth anything.
\t\t\t\t# Every location of one province scores the same for a good, so the
\t\t\t\t# third is the common one and the numbers have to show it.
\t\t\t\tif = {{
\t\t\t\t\tlimit = {{ global_var:{MOD_ID}_rs_bg = global_var:{MOD_ID}_rs_ag }}
\t\t\t\t\tchange_global_variable = {{ name = {MOD_ID}_rs_same add = 1 }}
\t\t\t\t}}
\t\t\t\telse_if = {{
\t\t\t\t\tlimit = {{
\t\t\t\t\t\tOR = {{
\t\t\t\t\t\t\tglobal_var:{MOD_ID}_rs_afit = 0
\t\t\t\t\t\t\tglobal_var:{MOD_ID}_rs_bfit = 0
\t\t\t\t\t\t}}
\t\t\t\t\t}}
\t\t\t\t\tchange_global_variable = {{ name = {MOD_ID}_rs_nofit add = 1 }}
\t\t\t\t}}
\t\t\t\telse_if = {{
\t\t\t\t\tlimit = {{ NOT = {{ global_var:{MOD_ID}_rs_new > global_var:{MOD_ID}_rs_now }} }}
\t\t\t\t\tchange_global_variable = {{ name = {MOD_ID}_rs_worse add = 1 }}
\t\t\t\t}}
\t\t\t\tif = {{
\t\t\t\t\tlimit = {{
\t\t\t\t\t\tglobal_var:{MOD_ID}_rs_bg > 0
\t\t\t\t\t\tNOT = {{ global_var:{MOD_ID}_rs_bg = global_var:{MOD_ID}_rs_ag }}
\t\t\t\t\t\tglobal_var:{MOD_ID}_rs_afit = 1
\t\t\t\t\t\tglobal_var:{MOD_ID}_rs_bfit = 1
\t\t\t\t\t\tglobal_var:{MOD_ID}_rs_new > global_var:{MOD_ID}_rs_now
\t\t\t\t\t}}
\t\t\t\t\t# **Out before in, on both sides.** The placement asks the cap for
\t\t\t\t\t# itself, and the room it needs is the one being freed a line above.
{swap_b}\t\t\t\t\tset_variable = {{ name = {MOD_ID}_fillg value = global_var:{MOD_ID}_rs_ag }}
\t\t\t\t\tscope:{MOD_ID}_rs_a = {{
{swap_a}\t\t\t\t\t\tset_variable = {{ name = {MOD_ID}_fillg value = global_var:{MOD_ID}_rs_bg }}
\t\t\t\t\t}}
\t\t\t\t\t# One trade per location per round: A's parked row still holds, but
\t\t\t\t\t# what A may hold does not — it carries B's good now.
\t\t\t\t\t# **A swap is this press's work too.** Two locations change after the
\t\t\t\t\t# walk has left them, and without a stamp they would sort with whatever
\t\t\t\t\t# press put the building there first.
\t\t\t\t\tset_variable = {{ name = {MOD_ID}_chg_seq value = global_var:{MOD_ID}_edit_presses }}
\t\t\t\t\tscope:{MOD_ID}_rs_a = {{ set_variable = {{ name = {MOD_ID}_chg_seq value = global_var:{MOD_ID}_edit_presses }} }}
\t\t\t\t\tset_global_variable = {{ name = {MOD_ID}_rs_stop value = 1 }}
\t\t\t\t\tset_global_variable = {{ name = {MOD_ID}_rs_did value = 1 }}
\t\t\t\t\tchange_global_variable = {{ name = {MOD_ID}_ps_swaps add = 1 }}
\t\t\t\t}}
\t\t\t}}
\t\t}}
\t}}
}}
""")

    # ---- «Перетасовать»: тот же обмен, но по всему плану ---------------------
    #
    # **Механизм готов и узок был только по входу.** `_edit_reshuffle_round`
    # торгует парами из `_edit_fillset`, где у каждой локации `_fillg` называет
    # товар, которым она торгует. Долив ставит один домик и метит его; план
    # ставит три-четыре, и метить надо не «последний поставленный», а **худший
    # стоящий** — тот, ради которого обмен и затевается.
    #
    # **Провинция за провинцией, и это не только про цену.** Пары берутся из
    # `_edit_fillset`, а копия в `_edit_fillset2` делается из него же: загружая
    # по одной провинции, мы ограничиваем обмен провинцией даром. По всей земле
    # это 416² пар за круг, внутри провинции — тридцать.
    #
    # **Владелец, 2026-09-09:** «сделай кнопку „Перетасовать“, чтобы оно
    # работало ручным этапом после создания плана». Ручным — потому что зонд
    # намерил потолок в два процента: платить за это на каждом «Пересчитать»
    # незачем, а нажать, когда захотелось, — можно.
    own = own_sides(rows, split, game)
    villages_ = village_entities(rows, split, game)
    # **Домик, поставленный грамотой, обмен не трогает.** Владелец, 2026-09-09:
    # «у городских прав отбираются их домики и меняются с ними местами... не
    # трогать домики городских прав». Грамота ставится пачкой и переезжает
    # пачкой; вынуть из неё один домик значит сломать её же инвариант.
    #
    # **Признак -- грамота этого города и её набор.** Локация с грамотой k
    # держит `_plan_right = k`; если k выдаёт этот товар, домик тут её, и он
    # неприкосновенен. Товар, которого не выдаёт ни одна грамота, оговорки не
    # получает вовсе.
    charter_of = {}
    for k, right in enumerate(output_rights(rows, game), start=1):
        for g in right.output:
            charter_of.setdefault(g, []).append(k)

    def not_charter(good: str, tab: str) -> str:
        ks = charter_of.get(good) or []
        if not ks:
            return ""
        tests = " ".join(f"var:{MOD_ID}_plan_right = {k}" for k in ks)
        return f"{tab}NOT = {{ OR = {{ {tests} }} }}\n"

    worst = ""
    for index, good in enumerate(order, start=1):
        has_town, has_rural = own[good]
        for kind, ok, gvar in (("t", has_town, "p"), ("r", has_rural, "pr")):
            if not ok:
                continue
            # **Своё здание, а не только свой товар в списке.** Деревня кладёт
            # в `_plan_goods` то, что она делает, а `_edit_remove_*` сняло бы с
            # локации саму деревню: пиво «стоит» в торговой деревне, но домик
            # там не пивной. Меняем только то, что действительно своё.
            side = "t" if kind == "t" else "r"
            mine = sorted(b for b in (groups.get((good, side)) or {})
                          if b not in villages_)
            builds = " ".join(
                f"is_target_in_variable_list = {{ name = {MOD_ID}_plan_builds "
                f"target = building_type:{b} }}" for b in mine)
            worst += f"""\tif = {{
\t\tlimit = {{
\t\t\t{MOD_ID}_plan_is_town = {'yes' if kind == 't' else 'no'}
\t\t\tis_target_in_variable_list = {{ name = {MOD_ID}_plan_goods target = goods:{good} }}
\t\t\tOR = {{ {builds} }}
{not_charter(good, chr(9) * 3)}\t\t\tvar:{MOD_ID}_{gvar}{index} < global_var:{MOD_ID}_fillv
\t\t}}
\t\tset_variable = {{ name = {MOD_ID}_fillg value = {index} }}
\t\tset_global_variable = {{ name = {MOD_ID}_fillv value = var:{MOD_ID}_{gvar}{index} }}
\t}}
"""
    out.append(f"""
# Которым товаром эта локация торгует: **худшим стоящим здесь своим домиком.**
# Бегущий минимум лежит в глобалке, а не в переменной локации: `var:x < var:y`
# в этом моде нигде не доказан, `var:x < global_var:y` доказан везде.
# Scope: location
{MOD_ID}_plan_pick_worst = {{
\tremove_variable = {MOD_ID}_fillg
\tset_global_variable = {{ name = {MOD_ID}_fillv value = {RANK_SCALE * 10} }}
{worst}}}
""")

    # ---- деревня как партнёр обмена -----------------------------------------
    #
    # **Его правило, 2026-09-09, и оно намеренно грубое:** «просто разреши любому
    # сельскому сооружению меняться с любой деревней, при условии конечно что они
    # вообще могут поменяться... Не смотри на выгоду деревни, пусть стоят где
    # хотят и похер будет ли кормить земля деревни. Это хороший компромисс,
    # который вредит не всей земле, а только деревням».
    #
    # Значит условие обмена -- **только выгода товара**, она проверена выше
    # (`_mv_bv > _mv_wv`). Деревня едет на освободившееся место, если она там
    # вообще может стоять; что земля ей платит, не спрашивается.
    vills = village_entities(rows, split, game)
    shared_all = shared_buildings(rows, split, game)
    vmakes = {k: [i for i, g in enumerate(order, start=1)
                  if b in (groups.get((g, "r")) or {})]
              for k, b in enumerate(vills, start=1)}
    for k, building in enumerate(vills, start=1):
        vb = shared_all.index(building) + 1
        drops = "".join(
            f"\t\tif = {{\n"
            f"\t\t\tlimit = {{ var:{MOD_ID}_vw{k} = {i} }}\n"
            f"\t\t\tremove_list_variable = {{ name = {MOD_ID}_plan_goods "
            f"target = goods:{order[i - 1]} }}\n"
            f"\t\t}}\n" for i in vmakes[k])
        out.append(f"""
# {building} с локации долой -- обратное к `{MOD_ID}_plan_try_village_{k}`, строка
# в строку. Без него деревня, однажды поставленная, стоит вечно: снять её было
# нечем, и обмен обойти её не мог.
# Scope: location
{MOD_ID}_plan_drop_village_{k} = {{
\tif = {{
\t\tlimit = {{ is_target_in_variable_list = {{ name = {MOD_ID}_plan_builds target = building_type:{building} }} }}
\t\tremove_list_variable = {{ name = {MOD_ID}_plan_builds target = building_type:{building} }}
{drops}\t\tchange_variable = {{ name = {MOD_ID}_load subtract = 1 }}
\t\tchange_global_variable = {{ name = {MOD_ID}_plan_placed subtract = 1 }}
\t\tchange_global_variable = {{ name = {MOD_ID}_plan_pr subtract = 1 }}
\t\tchange_global_variable = {{ name = {MOD_ID}_bn{vb} subtract = 1 }}
\t\tchange_global_variable = {{ name = {MOD_ID}_plan_gain subtract = var:{MOD_ID}_vb{k} }}
\t\tif = {{
\t\t\tlimit = {{ var:{MOD_ID}_vb{k} > 0 }}
\t\t\tchange_global_variable = {{ name = {MOD_ID}_plan_fed subtract = 1 }}
\t\t}}
\t}}
}}
""")

    def village_goods_or(k: int) -> str:
        """Что деревня здесь сделает и не стоит ли этот товар уже тут."""
        return "".join(
            f"\t\t\t\t\tAND = {{\n"
            f"\t\t\t\t\t\tvar:{MOD_ID}_vw{k} = {i}\n"
            f"\t\t\t\t\t\tNOT = {{ is_target_in_variable_list = {{ "
            f"name = {MOD_ID}_plan_goods target = goods:{order[i - 1]} }} }}\n"
            f"\t\t\t\t\t}}\n" for i in vmakes[k])

    find_v = "".join(
        f"\tif = {{\n"
        f"\t\tlimit = {{ is_target_in_variable_list = {{ name = {MOD_ID}_plan_builds "
        f"target = building_type:{b} }} }}\n"
        f"\t\tset_global_variable = {{ name = {MOD_ID}_mv_vk value = {k} }}\n"
        f"\t}}\n" for k, b in enumerate(vills, start=1))
    # **Та же проверка, что `_plan_can_village_<k>`, но без строки про комнату.**
    # Комнату освободит снятие товара, которое случится следом; спрашивать её до
    # снятия значит всегда получать «нет» на полном плане.
    fits_v = "".join(
        f"\t\tif = {{\n"
        f"\t\t\tlimit = {{\n"
        f"\t\t\t\tglobal_var:{MOD_ID}_mv_vk = {k}\n"
        f"\t\t\t\tvar:{MOD_ID}_vw{k} > 0\n"
        f"\t\t\t\t{MOD_ID}_plan_is_town = no\n"
        f"\t\t\t\tNOT = {{ is_target_in_variable_list = {{ name = {MOD_ID}_plan_builds "
        f"target = building_type:{b} }} }}\n"
        f"\t\t\t\tOR = {{\n"
        f"{village_goods_or(k)}"
        f"\t\t\t\t}}\n"
        f"\t\t\t}}\n"
        f"\t\t\tset_global_variable = {{ name = {MOD_ID}_mv_vfit value = 1 }}\n"
        f"\t\t}}\n" for k, b in enumerate(vills, start=1))
    drop_v = "".join(
        f"\tif = {{ limit = {{ global_var:{MOD_ID}_mv_vk = {k} }} "
        f"{MOD_ID}_plan_drop_village_{k} = yes }}\n"
        for k in range(1, len(vills) + 1))
    put_v = "".join(
        f"\tif = {{ limit = {{ global_var:{MOD_ID}_mv_vk = {k} }} "
        f"{MOD_ID}_plan_try_village_{k} = yes }}\n"
        for k in range(1, len(vills) + 1))
    out.append(f"""
# Какая деревня стоит на этой локации, номером.
# Scope: location
{MOD_ID}_mv_find_village = {{
\tset_global_variable = {{ name = {MOD_ID}_mv_vk value = 0 }}
{find_v}}}

# Встанет ли сюда деревня `_mv_vk`, если освободить одну комнату.
# Scope: location
{MOD_ID}_mv_village_fits = {{
\tset_global_variable = {{ name = {MOD_ID}_mv_vfit value = 0 }}
\tif = {{
\t\tlimit = {{ global_var:{MOD_ID}_mv_vk > 0 }}
{fits_v}\t}}
}}

# Scope: location
{MOD_ID}_mv_drop_village = {{
{drop_v}}}

# Scope: location
{MOD_ID}_mv_put_village = {{
{put_v}}}
""")
    # ---- переезд между провинциями: общий переключатель и по одному на товар
    read_b = "".join(
        f"""\tif = {{
\t\tlimit = {{ global_var:{MOD_ID}_mv_bg = {i} }}
\t\tif = {{
\t\t\tlimit = {{ {MOD_ID}_plan_is_town = yes }}
\t\t\tset_global_variable = {{ name = {MOD_ID}_mv_bgain value = var:{MOD_ID}_p{i} }}
\t\t}}
\t\telse = {{
\t\t\tset_global_variable = {{ name = {MOD_ID}_mv_bgain value = var:{MOD_ID}_pr{i} }}
\t\t}}
\t\tif = {{
\t\t\tlimit = {{ OR = {{ {MOD_ID}_edit_fits_town_{i} = yes {MOD_ID}_edit_fits_rural_{i} = yes }} }}
\t\t\tset_global_variable = {{ name = {MOD_ID}_mv_bfit value = 1 }}
\t\t}}
\t}}
"""
        for i in range(1, len(order) + 1))
    moves = ""
    for index, good in enumerate(order, start=1):
        has_town, has_rural = own[good]
        for kind, ok in (("t", has_town), ("r", has_rural)):
            if ok:
                moves += f"\t{MOD_ID}_plan_move_{kind}{index} = yes\n"
    out.append(f"""
# Общее для обмена: всё про **чужой** товар, у которого мы отбираем место. Его
# номер лежит в `_mv_bg`, а по номеру-переменной ни выгоду, ни «влезет ли» не
# прочитать -- отсюда один переключатель на всех, а не по одному на пару.
# Scope: location
{MOD_ID}_mv_read_b = {{
\tset_global_variable = {{ name = {MOD_ID}_mv_bgain value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_mv_bfit value = 0 }}
{read_b}}}

# «Перетасовать»: обмен местами **между провинциями**.
#
# **Внутри провинции обменивать нечего, и это факт из файлов игры.** Выгода
# считается `province_definition = {{ any_location_in_province_definition = {{
# raw_material = goods:X }} }}`: одно РГО где угодно в провинции кормит каждую её
# локацию одинаково. Первая версия торговала внутри провинции и не могла дать
# ничего; владелец поймал это с одного взгляда, 2026-09-09: «у них везде будет
# один и тот же бонус от земли».
#
# **Пар не перебираем.** Обмен всех со всеми -- это 416² за круг. Вместо этого
# на каждый товар и сторону один обход земли: где ему платят больше всего и где
# стоит его худший домик. Партнёром берётся тот, кем помечена цель --
# `_plan_pick_worst` метит локацию худшим стоящим там своим домиком. Это
# `товары × локации`, а не `локации²`.
#
# **Домиков не меняет ни у кого**: у обоих товаров как было, так и осталось.
# Scope: country
{MOD_ID}_plan_shuffle = {{
\t# **Свои счётчики, а не `_rs_*`.** Те стирает открытие окна редактора
\t# (`_edit_clear_fillset`), и прогон 2026-09-09 напечатал `rounds=0 swaps=0`
\t# после перетасовки, которая переставила 36 локаций.
\tset_global_variable = {{ name = {MOD_ID}_ps_swaps value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_ps_rounds value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_ps_gain0 value = global_var:{MOD_ID}_plan_gain }}
\tset_global_variable = {{ name = {MOD_ID}_ps_rswaps value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_ps_rrounds value = 0 }}
\tchange_global_variable = {{ name = {MOD_ID}_edit_presses add = 1 }}
\t# **Сначала грамоты, потом всё остальное** -- его порядок, 2026-09-09.
\t# Грамота везёт с собой пачку домиков, так что её переезд меняет землю под
\t# ногами у товарного обмена: считать товарам есть смысл только по уже
\t# переставленным грамотам.
\t#
\t# `_edit_right_prepare` -- то же, с чего начинается любое нажатие на
\t# грамоте: доли, разрешения и `_edit_strict = 0`, без которого выравнивание
\t# загрузки города отказалось бы отдавать домик и город остался бы выше
\t# своего потолка.
\t{MOD_ID}_edit_right_prepare = yes
\t{MOD_ID}_plan_shuffle_rights = yes
\tif = {{
\t\tlimit = {{ global_var:{MOD_ID}_ps_did = 1 }}
\t\t{MOD_ID}_plan_shuffle_rights = yes
\t}}
\tif = {{
\t\tlimit = {{ global_var:{MOD_ID}_ps_did = 1 }}
\t\t{MOD_ID}_plan_shuffle_rights = yes
\t}}
\t{MOD_ID}_plan_shuffle_round = yes
\tif = {{
\t\tlimit = {{ global_var:{MOD_ID}_ps_did = 1 }}
\t\t{MOD_ID}_plan_shuffle_round = yes
\t}}
\tif = {{
\t\tlimit = {{ global_var:{MOD_ID}_ps_did = 1 }}
\t\t{MOD_ID}_plan_shuffle_round = yes
\t}}
\tevery_in_global_list = {{
\t\tvariable = {MOD_ID}_plan_touched
\t\tremove_variable = {MOD_ID}_fillg
\t}}
\tset_global_variable = {{ name = {MOD_ID}_ps_gain value = global_var:{MOD_ID}_plan_gain }}
\tchange_global_variable = {{ name = {MOD_ID}_ps_gain subtract = global_var:{MOD_ID}_ps_gain0 }}
\tset_global_variable = {{ name = {MOD_ID}_ps_ran value = 1 }}
\t{MOD_ID}_plan_rank = yes
}}

# Один круг: пометить землю и дать каждому товару по одному переезду на сторону.
# Scope: country
{MOD_ID}_plan_shuffle_round = {{
\tset_global_variable = {{ name = {MOD_ID}_ps_did value = 0 }}
\tchange_global_variable = {{ name = {MOD_ID}_ps_rounds add = 1 }}
\tevery_in_global_list = {{
\t\tvariable = {MOD_ID}_plan_touched
\t\tlimit = {{ has_variable = {MOD_ID}_load }}
\t\t{MOD_ID}_plan_pick_worst = yes
\t}}
{moves}}}
""")
    for index, good in enumerate(order, start=1):
        has_town, has_rural = own[good]
        for kind, ok, gvar in (("t", has_town, "p"), ("r", has_rural, "pr")):
            if not ok:
                continue
            sidename = "town" if kind == "t" else "rural"
            istown = "yes" if kind == "t" else "no"
            sfx, big = kind, RANK_SCALE * 10
            mine = sorted(b for b in (groups.get((good, kind)) or {})
                          if b not in villages_)
            builds = " ".join(
                f"is_target_in_variable_list = {{ name = {MOD_ID}_plan_builds "
                f"target = building_type:{b} }}" for b in mine)
            mvar = "pm" if kind == "t" else "prm"
            ownm = " ".join(
                f"var:{MOD_ID}_{mvar}{index} = {m}"
                for m in sorted(m for b, ms in (groups.get((good, kind)) or {}).items()
                                if b not in villages_ for m in ms))
            # **Обмен с деревней, и он спрашивает только выгоду товара.** Его
            # правило: «не смотри на выгоду деревни, пусть стоят где хотят».
            # Деревня -- партнёр там, где своего домика в цели нет вовсе
            # (`_fillg` пуст), а `_mv_bv > _mv_wv` уже проверено выше.
            village = ""
            if kind == "r":
                village = f"""\t\tif = {{
\t\t\tlimit = {{ NOT = {{ global_var:{MOD_ID}_ps_traded = 1 }} }}
\t\t\tscope:{MOD_ID}_mv_to = {{ {MOD_ID}_mv_find_village = yes }}
\t\t\tscope:{MOD_ID}_mv_from = {{ {MOD_ID}_mv_village_fits = yes }}
\t\t\tif = {{
\t\t\t\tlimit = {{
\t\t\t\t\tglobal_var:{MOD_ID}_mv_vk > 0
\t\t\t\t\tglobal_var:{MOD_ID}_mv_vfit = 1
\t\t\t\t}}
\t\t\t\tscope:{MOD_ID}_mv_to = {{
\t\t\t\t\t{MOD_ID}_mv_drop_village = yes
\t\t\t\t\t{MOD_ID}_edit_place_rural_{index} = yes
\t\t\t\t\tset_variable = {{ name = {MOD_ID}_chg_seq value = global_var:{MOD_ID}_edit_presses }}
\t\t\t\t}}
\t\t\t\tscope:{MOD_ID}_mv_from = {{
\t\t\t\t\t{MOD_ID}_edit_remove_rural_{index} = yes
\t\t\t\t\t{MOD_ID}_mv_put_village = yes
\t\t\t\t\tset_variable = {{ name = {MOD_ID}_chg_seq value = global_var:{MOD_ID}_edit_presses }}
\t\t\t\t}}
\t\t\t\tset_global_variable = {{ name = {MOD_ID}_ps_did value = 1 }}
\t\t\t\tchange_global_variable = {{ name = {MOD_ID}_ps_swaps add = 1 }}
\t\t\t}}
\t\t}}
"""
            out_b = dispatch("edit_remove", f"global_var:{MOD_ID}_mv_bg", "\t" * 4)
            in_a = dispatch("edit_place", f"global_var:{MOD_ID}_mv_ag", "\t" * 4)
            out_a = dispatch("edit_remove", f"global_var:{MOD_ID}_mv_ag", "\t" * 4)
            in_b = dispatch("edit_place", f"global_var:{MOD_ID}_mv_bg", "\t" * 4)
            out.append(f"""
# {good}, {sidename}: один переезд за круг -- из худшей своей провинции в
# лучшую чужую, обменом с тем, кто там стоит.
# Scope: country
{MOD_ID}_plan_move_{sfx}{index} = {{
\tset_global_variable = {{ name = {MOD_ID}_mv_bv value = -1 }}
\tset_global_variable = {{ name = {MOD_ID}_mv_wv value = {big} }}
\tset_global_variable = {{ name = {MOD_ID}_mv_ag value = {index} }}
\tremove_global_variable = {MOD_ID}_mv_hasto
\tremove_global_variable = {MOD_ID}_mv_hasfrom
\tevery_in_global_list = {{
\t\tvariable = {MOD_ID}_plan_touched
\t\tlimit = {{
\t\t\thas_variable = {MOD_ID}_load
\t\t\t{MOD_ID}_plan_is_town = {istown}
\t\t}}
\t\t# Куда: лучшее место, где его домик мог бы стоять и ещё не стоит.
\t\tif = {{
\t\t\tlimit = {{
\t\t\t\t{MOD_ID}_edit_fits_{sidename}_{index} = yes
\t\t\t\t# **И только под своё здание.** `_edit_fits_rural_<n>` пускает и
\t\t\t\t# деревенский рецепт: украшения «влезли бы» в торговую деревню, а
\t\t\t\t# постановка добавила бы саму деревню -- ровно тот двойной счёт,
\t\t\t\t# который убирали всю сессию.
\t\t\t\tOR = {{ {ownm} }}
\t\t\t\tvar:{MOD_ID}_{gvar}{index} > global_var:{MOD_ID}_mv_bv
\t\t\t}}
\t\t\tset_global_variable = {{ name = {MOD_ID}_mv_bv value = var:{MOD_ID}_{gvar}{index} }}
\t\t\tsave_scope_as = {MOD_ID}_mv_to
\t\t\tset_global_variable = {{ name = {MOD_ID}_mv_hasto value = 1 }}
\t\t}}
\t\t# Откуда: худшее место, где стоит его **своё** здание.
\t\tif = {{
\t\t\tlimit = {{
\t\t\t\tis_target_in_variable_list = {{ name = {MOD_ID}_plan_goods target = goods:{good} }}
\t\t\t\tOR = {{ {builds} }}
{not_charter(good, chr(9) * 4)}\t\t\t\tvar:{MOD_ID}_{gvar}{index} < global_var:{MOD_ID}_mv_wv
\t\t\t}}
\t\t\tset_global_variable = {{ name = {MOD_ID}_mv_wv value = var:{MOD_ID}_{gvar}{index} }}
\t\t\tsave_scope_as = {MOD_ID}_mv_from
\t\t\tset_global_variable = {{ name = {MOD_ID}_mv_hasfrom value = 1 }}
\t\t}}
\t}}
\tif = {{
\t\tlimit = {{
\t\t\thas_global_variable = {MOD_ID}_mv_hasto
\t\t\thas_global_variable = {MOD_ID}_mv_hasfrom
\t\t\tglobal_var:{MOD_ID}_mv_bv > global_var:{MOD_ID}_mv_wv
\t\t}}
\t\t# Кто стоит в цели и что он там получает.
\t\tset_global_variable = {{ name = {MOD_ID}_mv_bg value = 0 }}
\t\tset_global_variable = {{ name = {MOD_ID}_ps_traded value = 0 }}
\t\tscope:{MOD_ID}_mv_to = {{
\t\t\tif = {{
\t\t\t\tlimit = {{ has_variable = {MOD_ID}_fillg }}
\t\t\t\tset_global_variable = {{ name = {MOD_ID}_mv_bg value = var:{MOD_ID}_fillg }}
\t\t\t}}
\t\t\t{MOD_ID}_mv_read_b = yes
\t\t\tset_global_variable = {{ name = {MOD_ID}_mv_bto value = global_var:{MOD_ID}_mv_bgain }}
\t\t}}
\t\t# Что он получит там, куда поедет, и влезет ли он туда вообще.
\t\tscope:{MOD_ID}_mv_from = {{
\t\t\t{MOD_ID}_mv_read_b = yes
\t\t\tset_global_variable = {{ name = {MOD_ID}_mv_bfrom value = global_var:{MOD_ID}_mv_bgain }}
\t\t\tset_global_variable = {{ name = {MOD_ID}_mv_bfitf value = global_var:{MOD_ID}_mv_bfit }}
\t\t}}
\t\t# Паре вместе должно стать лучше, а не одному из двоих.
\t\tset_global_variable = {{ name = {MOD_ID}_mv_new value = global_var:{MOD_ID}_mv_bv }}
\t\tchange_global_variable = {{ name = {MOD_ID}_mv_new add = global_var:{MOD_ID}_mv_bfrom }}
\t\tset_global_variable = {{ name = {MOD_ID}_mv_now value = global_var:{MOD_ID}_mv_wv }}
\t\tchange_global_variable = {{ name = {MOD_ID}_mv_now add = global_var:{MOD_ID}_mv_bto }}
\t\tif = {{
\t\t\tlimit = {{
\t\t\t\tglobal_var:{MOD_ID}_mv_bg > 0
\t\t\t\tglobal_var:{MOD_ID}_mv_bfitf = 1
\t\t\t\tglobal_var:{MOD_ID}_mv_new > global_var:{MOD_ID}_mv_now
\t\t\t}}
\t\t\t# **Сначала в цель, потом из источника.** Товар на миг стоит дважды и
\t\t\t# возвращается к своему числу; постановка квоты не спрашивает, только
\t\t\t# «влезет ли» и «есть ли комната», а комнату освобождает строка выше.
\t\t\tscope:{MOD_ID}_mv_to = {{
{out_b}{in_a}\t\t\t\tset_variable = {{ name = {MOD_ID}_chg_seq value = global_var:{MOD_ID}_edit_presses }}
\t\t\t}}
\t\t\tscope:{MOD_ID}_mv_from = {{
{out_a}{in_b}\t\t\t\tset_variable = {{ name = {MOD_ID}_chg_seq value = global_var:{MOD_ID}_edit_presses }}
\t\t\t}}
\t\t\tset_global_variable = {{ name = {MOD_ID}_ps_did value = 1 }}
\t\t\tset_global_variable = {{ name = {MOD_ID}_ps_traded value = 1 }}
\t\t\tchange_global_variable = {{ name = {MOD_ID}_ps_swaps add = 1 }}
\t\t}}
{village}\t}}
}}
""")

    # ---- «Перетасовать», проход первый: сами грамоты ------------------------
    #
    # **Его слово, 2026-09-09:** «Перетасовка должна сначала проработать
    # городские права, перетасовать именно их, потом всё остальное и не трогать
    # домики городских прав». Второе сделано оговоркой `not_charter`, первое --
    # здесь.
    #
    # **Почему грамоты идут первыми.** Грамота приезжает пачкой в один-три
    # домика и уводит столько же чужих: её переезд меняет землю под ногами у
    # товарного обмена. Значит товарный обмен должен считать уже по
    # переставленным грамотам, а не наоборот.
    #
    # **Это перестановка, а не раздача.** Ни одна грамота не появляется и не
    # исчезает: пара городов меняется грамотами целиком, `_rn<k>` у обоих
    # остаётся прежним. Поэтому доли грамот (`_rsh<k>`) проход не спрашивает --
    # он их не может нарушить.
    #
    # **Условие -- пара вместе, как и у товаров.** Города A (держит k) и B
    # (держит j) меняются, если `rq_k(B) + rq_j(A) > rq_k(A) + rq_j(B)`; каждый
    # `_rq` -- средняя выгода набора грамоты в этом городе, шкала у всех одна.
    # Сумма при каждом обмене строго растёт, так что круг не может зациклиться.
    read_right = "".join(
        f"""\tif = {{
\t\tlimit = {{ global_var:{MOD_ID}_mv_rj = {k} }}
\t\tset_variable = {{ name = {MOD_ID}_psrq value = {MOD_ID}_rq{k} }}
\t\tset_global_variable = {{ name = {MOD_ID}_mv_rjv value = var:{MOD_ID}_psrq }}
\t\tif = {{
\t\t\tlimit = {{ {MOD_ID}_edit_right_fits_{k} = yes }}
\t\t\tset_global_variable = {{ name = {MOD_ID}_mv_rjfit value = 1 }}
\t\t}}
\t}}
"""
        for k in range(1, len(rights) + 1))
    out.append(f"""
# Общее для обмена грамотами: всё про **чужую** грамоту, с которой меняемся. Её
# номер лежит в `_mv_rj`, а по номеру-переменной ни выгоду (`_rq<k>`), ни
# «влезет ли сюда» (`_edit_right_fits_<k>`) не прочитать -- отсюда один
# переключатель на всех, ровно как `_mv_read_b` у товаров.
# Scope: location
{MOD_ID}_mv_read_right = {{
\tset_global_variable = {{ name = {MOD_ID}_mv_rjv value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_mv_rjfit value = 0 }}
{read_right}}}
""")

    rmoves = ""
    for k, right in enumerate(rights, start=1):
        if not [good for good in right.output if groups.get((good, "t"))]:
            # `_edit_right_fits_<k>` у такой грамоты -- `always = no`: ей некуда
            # ехать, и обход земли ради неё ничего не найдёт.
            continue
        rmoves += f"\t{MOD_ID}_plan_move_right_{k} = yes\n"
        out.append(f"""
# {right.key}: один переезд за круг -- из худшего своего города в лучший чужой,
# обменом грамотами с тем, кто там сидит.
# Scope: country
{MOD_ID}_plan_move_right_{k} = {{
\tset_global_variable = {{ name = {MOD_ID}_mv_rbv value = -1 }}
\tset_global_variable = {{ name = {MOD_ID}_mv_rwv value = {RANK_SCALE * 10} }}
\tremove_global_variable = {MOD_ID}_mv_rhasto
\tremove_global_variable = {MOD_ID}_mv_rhasfrom
\tevery_in_global_list = {{
\t\tvariable = {MOD_ID}_plan_touched
\t\tlimit = {{
\t\t\thas_variable = {MOD_ID}_load
\t\t\t{MOD_ID}_plan_is_town = yes
\t\t\thas_variable = {MOD_ID}_plan_right
\t\t}}
\t\t# Выгода грамоты здесь -- в переменную локации: бегущий минимум и
\t\t# максимум лежат в глобалках, а `var:x > global_var:y` -- единственная
\t\t# форма сравнения, доказанная в этом моде везде.
\t\tset_variable = {{ name = {MOD_ID}_psrq value = {MOD_ID}_rq{k} }}
\t\t# Куда: чужой город, где ей платят больше всего и где она может стоять.
\t\tif = {{
\t\t\tlimit = {{
\t\t\t\tNOT = {{ var:{MOD_ID}_plan_right = {k} }}
\t\t\t\t{MOD_ID}_edit_right_fits_{k} = yes
\t\t\t\tvar:{MOD_ID}_psrq > global_var:{MOD_ID}_mv_rbv
\t\t\t}}
\t\t\tset_global_variable = {{ name = {MOD_ID}_mv_rbv value = var:{MOD_ID}_psrq }}
\t\t\tsave_scope_as = {MOD_ID}_mv_rto
\t\t\tset_global_variable = {{ name = {MOD_ID}_mv_rhasto value = 1 }}
\t\t}}
\t\t# Откуда: свой город, где ей платят меньше всего.
\t\tif = {{
\t\t\tlimit = {{
\t\t\t\tvar:{MOD_ID}_plan_right = {k}
\t\t\t\tvar:{MOD_ID}_psrq < global_var:{MOD_ID}_mv_rwv
\t\t\t}}
\t\t\tset_global_variable = {{ name = {MOD_ID}_mv_rwv value = var:{MOD_ID}_psrq }}
\t\t\tsave_scope_as = {MOD_ID}_mv_rfrom
\t\t\tset_global_variable = {{ name = {MOD_ID}_mv_rhasfrom value = 1 }}
\t\t}}
\t}}
\tif = {{
\t\tlimit = {{
\t\t\thas_global_variable = {MOD_ID}_mv_rhasto
\t\t\thas_global_variable = {MOD_ID}_mv_rhasfrom
\t\t\tglobal_var:{MOD_ID}_mv_rbv > global_var:{MOD_ID}_mv_rwv
\t\t}}
\t\t# Чья грамота сидит в цели, что она там получает и что получит у нас.
\t\tscope:{MOD_ID}_mv_rto = {{
\t\t\tset_global_variable = {{ name = {MOD_ID}_mv_rj value = var:{MOD_ID}_plan_right }}
\t\t\t{MOD_ID}_mv_read_right = yes
\t\t\tset_global_variable = {{ name = {MOD_ID}_mv_rjb value = global_var:{MOD_ID}_mv_rjv }}
\t\t}}
\t\tscope:{MOD_ID}_mv_rfrom = {{
\t\t\t{MOD_ID}_mv_read_right = yes
\t\t\tset_global_variable = {{ name = {MOD_ID}_mv_rja value = global_var:{MOD_ID}_mv_rjv }}
\t\t\tset_global_variable = {{ name = {MOD_ID}_mv_rjfa value = global_var:{MOD_ID}_mv_rjfit }}
\t\t}}
\t\t# Паре вместе должно стать лучше, а не одному из двоих.
\t\tset_global_variable = {{ name = {MOD_ID}_mv_rnew value = global_var:{MOD_ID}_mv_rbv }}
\t\tchange_global_variable = {{ name = {MOD_ID}_mv_rnew add = global_var:{MOD_ID}_mv_rja }}
\t\tset_global_variable = {{ name = {MOD_ID}_mv_rnow value = global_var:{MOD_ID}_mv_rwv }}
\t\tchange_global_variable = {{ name = {MOD_ID}_mv_rnow add = global_var:{MOD_ID}_mv_rjb }}
\t\tif = {{
\t\t\tlimit = {{
\t\t\t\tglobal_var:{MOD_ID}_mv_rjfa = 1
\t\t\t\tglobal_var:{MOD_ID}_mv_rnew > global_var:{MOD_ID}_mv_rnow
\t\t\t}}
\t\t\t# **Обе стороны через `_edit_right_swap`**, а не своим кодом: он
\t\t\t# снимает пачку целиком, освобождает комнату под приезжающую и
\t\t\t# выравнивает загрузку города -- то же, что делают «+1» и «−1».
\t\t\tscope:{MOD_ID}_mv_rto = {{
\t\t\t\tset_global_variable = {{ name = {MOD_ID}_edit_rfrom value = global_var:{MOD_ID}_mv_rj }}
\t\t\t\tset_global_variable = {{ name = {MOD_ID}_edit_rto value = {k} }}
\t\t\t\t{MOD_ID}_edit_right_swap = yes
\t\t\t}}
\t\t\tscope:{MOD_ID}_mv_rfrom = {{
\t\t\t\tset_global_variable = {{ name = {MOD_ID}_edit_rfrom value = {k} }}
\t\t\t\tset_global_variable = {{ name = {MOD_ID}_edit_rto value = global_var:{MOD_ID}_mv_rj }}
\t\t\t\t{MOD_ID}_edit_right_swap = yes
\t\t\t}}
\t\t\tset_global_variable = {{ name = {MOD_ID}_ps_did value = 1 }}
\t\t\tchange_global_variable = {{ name = {MOD_ID}_ps_rswaps add = 1 }}
\t\t}}
\t}}
}}
""")
    out.append(f"""
# Один круг грамот: каждой по одному переезду.
# Scope: country
{MOD_ID}_plan_shuffle_rights = {{
\tset_global_variable = {{ name = {MOD_ID}_ps_did value = 0 }}
\tchange_global_variable = {{ name = {MOD_ID}_ps_rrounds add = 1 }}
{rmoves}}}
""")

    # ---- step 5: the charters, moved from one town to another ---------------
    #
    # **A charter is not a building and «+1» on one cannot mean «one more».**
    # Every town of a finished plan holds exactly one charter -- the grant pass
    # walks empty towns and gives each the best it may have -- so there is no
    # free town to put another in. What he asked for, 2026-09-04, is a *move*:
    # «снять грамоту с города вместе со всеми её домиками и посадить в другой».
    #
    # So both presses are the same machine seen from two ends:
    #
    # - **«+1» on charter K** takes the town where K would earn most away from
    #   whatever charter it has now, and gives it to K. Strictly: among towns
    #   whose own charter is at or above its share; if none is, among all towns.
    #   The same two passes «+1» on a good already uses, and the same reason --
    #   the counts must come out level, which is what he has asked for three
    #   times: «относительно одинаковое количество каждого городского права».
    # - **«−1» on charter K** takes K off the town where it earns least and
    #   hands that town to whichever charter is furthest below its share and can
    #   stand there. The town keeps a charter either way: a town without one is
    #   a state the plan never produces and nothing else here knows how to read.
    #
    # **The bundle goes whole, and the rooms are squared up afterwards.** A
    # bundle is one to three buildings and the two bundles of a swap need not be
    # the same size, so the swap plants first and then fixes the load: over the
    # cap, the worst ordinary building gives way; under it, the good furthest
    # below its share takes the room. Three of each is the bound, because three
    # is the largest bundle in the game.
    substitute = market_inputs(game)

    # **The plan's `_plan_right_fits_<k>` is the wrong question here, and asking
    # it cost the run of 2026-09-06.** It is built out of `_plan_can_town_<n>`,
    # which requires a *free room* -- true of the empty towns the grant pass
    # walks, false of every town of a finished plan. So «+1» found no candidate
    # anywhere and «−1» found no charter to hand the town to: one cause, both
    # symptoms, and both read on screen as «кнопка не работает».
    #
    # What the editor has to ask is whether the ground can make one of the
    # charter's goods at all -- `_pm<n>` is the method that won here, and it does
    # not care what already stands. A bundle good that is already standing is not
    # a refusal: the swap plants what is missing, and `_edit_locked_<n>` takes the
    # rest into the bundle once `_plan_right` says so.
    for k, right in enumerate(rights, start=1):
        wanted_t = [good for good in sorted(right.output) if groups.get((good, "t"))]
        if not wanted_t:
            gate.append(f"\n# {right.key}: no town building at all.\n"
                        f"# Scope: location\n"
                        f"{MOD_ID}_edit_right_fits_{k} = {{ always = no }}\n")
            continue
        inside = ""
        for good in wanted_t:
            i = order.index(good) + 1
            mis = right_methods(right, good, rows)
            inside += ("".join(f"\t\tvar:{MOD_ID}_pm{i} = {mi}\n" for mi in mis)
                       if mis else f"\t\tvar:{MOD_ID}_pm{i} > 0\n")
        gate.append(f"""
# {right.key}: {", ".join(sorted(right.output))}. **A method, not a free room** --
# see the comment in `editor_file`; this is what «+1» and «−1» on a charter ask.
# Scope: location
{MOD_ID}_edit_right_fits_{k} = {{
\t{MOD_ID}_plan_is_town = yes
\tOR = {{
{inside}\t}}
}}
""")

    def charter(k: int, right: eu5data.TownRight, prefix: str, tab: str) -> str:
        """A charter's bundle, planted or removed, exactly as the plan plants it.

        **The substitution is mirrored and not re-decided.** Where the ground
        refuses a bundle good the grant pass plants its market input instead
        (`glass` -> `sand`, the one pair in the game), so a removal that asked
        the question differently would leave the substitute standing for ever.
        """
        lines = []
        for good in sorted(right.output):
            if not groups.get((good, "t")):
                continue
            index = order.index(good) + 1
            feeder = substitute.get(good)
            other = order.index(feeder) + 1 if feeder in order else 0
            if other and groups.get((feeder, "t")):
                lines.append(
                    f"{tab}# The substitute goes in only where the ground cannot make\n"
                    f"{tab}# the bundle good at all. **`_plan_can_town_<n>` is not that\n"
                    f"{tab}# question**: it also wants a free room, so on a full town it\n"
                    f"{tab}# would plant the substitute every time and the removal would\n"
                    f"{tab}# take out the wrong building.\n"
                    f"{tab}if = {{\n"
                    f"{tab}\tlimit = {{ var:{MOD_ID}_pm{index} > 0 }}\n"
                    f"{tab}\t{MOD_ID}_{prefix}_town_{index} = yes\n"
                    f"{tab}}}\n"
                    f"{tab}else = {{ {MOD_ID}_{prefix}_town_{other} = yes }}\n")
            else:
                lines.append(f"{tab}{MOD_ID}_{prefix}_town_{index} = yes\n")
        return "".join(lines)

    def charter_need(k: int, right: eu5data.TownRight) -> str:
        """How many rooms this charter's bundle actually wants in this town.

        **Counted before anything is planted, because the placement can say no.**
        `_edit_place_town_<n>` carries `var:_load < cap` as its last line -- the
        invariant that stopped 27 buildings going in over the cap on 2026-09-04 --
        so a bundle bigger than the one it replaces loses its extra building
        silently. He caught it in the window: «ювелирный домик уходит, а
        стекольному праву надо два, и для кладки места не нашлось».

        A good already standing here needs no room, which is what
        `_edit_fits_town_<n>` answers; the same effect run *after* the plant
        therefore counts what did not get in.
        """
        lines = []
        for good in sorted(right.output):
            if not groups.get((good, "t")):
                continue
            index = order.index(good) + 1
            feeder = substitute.get(good)
            other = order.index(feeder) + 1 if feeder in order else 0
            count = (lambda i, tab: f"{tab}if = {{ limit = {{ {MOD_ID}_edit_fits_town_{i} = yes }} "
                     f"change_variable = {{ name = {MOD_ID}_esrn add = 1 }} }}\n")
            if other and groups.get((feeder, "t")):
                lines.append(f"\tif = {{\n"
                             f"\t\tlimit = {{ var:{MOD_ID}_pm{index} > 0 }}\n"
                             f"{count(index, chr(9) * 2)}"
                             f"\t}}\n"
                             f"\telse = {{\n{count(other, chr(9) * 2)}\t}}\n")
            else:
                lines.append(count(index, chr(9)))
        return "".join(lines)

    for k, right in enumerate(rights, start=1):
        out.append(f"""
# {right.key}: how many rooms its bundle wants here, and afterwards how many it
# did not get. Read `charter_need` for why both readings are the same effect.
# Scope: location
{MOD_ID}_edit_right_need_{k} = {{
\tset_variable = {{ name = {MOD_ID}_esrn value = 0 }}
{charter_need(k, right)}}}

# {right.key}: {", ".join(sorted(right.output))} -- off this town, bundle and all.
# Scope: location
{MOD_ID}_edit_right_out_{k} = {{
{charter(k, right, "edit_remove", chr(9))}\tremove_variable = {MOD_ID}_plan_right
\tchange_global_variable = {{ name = {MOD_ID}_rn{k} subtract = 1 }}
\tchange_global_variable = {{ name = {MOD_ID}_rgiven{k} subtract = 1 }}
\tchange_global_variable = {{ name = {MOD_ID}_plan_rightn subtract = 1 }}
}}

# {right.key}: onto this town, bundle and all.
# Scope: location
{MOD_ID}_edit_right_in_{k} = {{
{charter(k, right, "edit_place", chr(9))}\tset_variable = {{ name = {MOD_ID}_plan_right value = {k} }}
\tchange_global_variable = {{ name = {MOD_ID}_rn{k} add = 1 }}
\tchange_global_variable = {{ name = {MOD_ID}_rgiven{k} add = 1 }}
\tchange_global_variable = {{ name = {MOD_ID}_plan_rightn add = 1 }}
}}
""")

    worst_one = "".join(
        f"\tif = {{ limit = {{ var:{MOD_ID}_esg = {i} }}\n"
        f"{call('edit_remove', i, chr(9) * 2)}\t}}\n"
        for i in range(1, len(order) + 1))
    out.append(f"""
# The worst ordinary building here, given up. **`_edit_worst` refuses a charter's
# own bundle** (`_edit_locked_<n>`) and a good the player pinned, so squaring up
# the load after a swap cannot eat the charter that was just planted.
# Scope: location
{MOD_ID}_edit_take_worst = {{
\t{MOD_ID}_edit_worst = yes
{worst_one}}}

# **One room made for the arriving bundle, if it still needs one.** Called three
# times: three is the largest bundle in the game, so a swap can be short by no
# more than that.
#
# `_esrn` is how many rooms the bundle wants and `_load` how many are taken, so
# their sum against the cap is the whole question. It is recomputed each time
# because `_edit_take_worst` moves `_load`.
# Scope: location
{MOD_ID}_edit_right_make_room = {{
\tset_variable = {{ name = {MOD_ID}_esrneed value = var:{MOD_ID}_load }}
\tchange_variable = {{ name = {MOD_ID}_esrneed add = var:{MOD_ID}_esrn }}
\tif = {{
\t\tlimit = {{ var:{MOD_ID}_esrneed > global_var:{MOD_ID}_plan_cap_urban }}
\t\t{MOD_ID}_edit_take_worst = yes
\t}}
}}

# The load, squared up after a swap. Three each way: three is the largest bundle
# in the game, so the two sides of a swap can differ by no more than that.
# Scope: location
{MOD_ID}_edit_right_fix_load = {{
""" + "".join(
        f"\tif = {{ limit = {{ var:{MOD_ID}_load > global_var:{MOD_ID}_plan_cap_urban }}\n"
        f"\t\t{MOD_ID}_edit_take_worst = yes }}\n" for _ in range(3))
    + "".join(
        f"\tif = {{ limit = {{ var:{MOD_ID}_load < global_var:{MOD_ID}_plan_cap_urban }}\n"
        f"\t\t{MOD_ID}_edit_fill_room = yes }}\n" for _ in range(3))
    + "}\n")

    swap_out = "".join(
        f"\tif = {{ limit = {{ global_var:{MOD_ID}_edit_rfrom = {k} }} "
        f"{MOD_ID}_edit_right_out_{k} = yes }}\n" for k in range(1, len(rights) + 1))
    swap_need = "".join(
        f"\tif = {{ limit = {{ global_var:{MOD_ID}_edit_rto = {k} }} "
        f"{MOD_ID}_edit_right_need_{k} = yes }}\n" for k in range(1, len(rights) + 1))
    swap_in = "".join(
        f"\tif = {{ limit = {{ global_var:{MOD_ID}_edit_rto = {k} }} "
        f"{MOD_ID}_edit_right_in_{k} = yes }}\n" for k in range(1, len(rights) + 1))
    out.append(f"""
# One town's charter exchanged for another. **Out before in**, because the rooms
# the old bundle frees are the ones the new one wants, and the load is squared up
# only once both have moved.
# Scope: location
{MOD_ID}_edit_right_swap = {{
{swap_out}\t# **Room first, then the bundle.** `_edit_place_town_<n>` refuses on a
\t# full town -- the invariant that stopped 27 buildings going over the cap
\t# on 2026-09-04 -- so a bundle bigger than the one it replaces used to
\t# lose its extra building without a word. He caught it: «ювелирный домик
\t# уходит, а стекольному праву надо два, и для кладки места не нашлось».
{swap_need}\t{MOD_ID}_edit_right_make_room = yes
\t{MOD_ID}_edit_right_make_room = yes
\t{MOD_ID}_edit_right_make_room = yes
{swap_in}\t# **And the same count again, which is now what did not get in.** Zero is
\t# the answer the press line wants; anything else means the town had
\t# nothing left it was allowed to give up, and that is worth saying out
\t# loud rather than leaving a charter standing with half a bundle.
\tset_variable = {{ name = {MOD_ID}_esrn value = 0 }}
{swap_need}\tset_global_variable = {{ name = {MOD_ID}_edit_rshort value = var:{MOD_ID}_esrn }}
\t{MOD_ID}_edit_right_fix_load = yes
\tset_variable = {{ name = {MOD_ID}_chg_seq value = global_var:{MOD_ID}_edit_presses }}
}}

""")

    # The share, the country's gate and «is this charter over its share» -- all
    # three are the same for every location, so they are read once a press.
    # **The counts a charter press divides by are the plan's, and before a plan
    # they are not there at all.** A `limit` that reads a global which does not
    # exist fails silently, so the press would refuse and say nothing -- the one
    # failure this repository names first.
    prepare = "".join(
        f"\tif = {{\n"
        f"\t\tlimit = {{ NOT = {{ has_global_variable = {MOD_ID}_rn{k} }} }}\n"
        f"\t\tset_global_variable = {{ name = {MOD_ID}_rn{k} value = 0 }}\n"
        f"\t\tset_global_variable = {{ name = {MOD_ID}_rgiven{k} value = 0 }}\n"
        f"\t}}\n"
        for k in range(1, len(rights) + 1)) + "".join(
        f"\t# **Not floored at zero, and that is the point.** With a share of 5, a\n"
        f"\t# charter holding 6 towns and one holding 5 both have «no shortfall»,\n"
        f"\t# and a floor would make them equal -- so «−1» could hand a town to the\n"
        f"\t# charter that already has the most. Negative reads «over its share by\n"
        f"\t# that much», and the walk prefers the larger number.\n"
        f"\tset_global_variable = {{ name = {MOD_ID}_rsh{k} value = global_var:{MOD_ID}_rquota }}\n"
        f"\tchange_global_variable = {{ name = {MOD_ID}_rsh{k} "
        f"subtract = global_var:{MOD_ID}_rn{k} }}\n"
        f"\tset_global_variable = {{ name = {MOD_ID}_rover{k} value = 0 }}\n"
        f"\tif = {{\n"
        f"\t\tlimit = {{ NOT = {{ global_var:{MOD_ID}_rquota > global_var:{MOD_ID}_rn{k} }} }}\n"
        f"\t\tset_global_variable = {{ name = {MOD_ID}_rover{k} value = 1 }}\n"
        f"\t}}\n"
        f"\tset_global_variable = {{ name = {MOD_ID}_rok{k} value = 0 }}\n"
        f"\tif = {{\n"
        f"\t\tlimit = {{ {MOD_ID}_plan_right_gate_{k} = yes }}\n"
        f"\t\tset_global_variable = {{ name = {MOD_ID}_rok{k} value = 1 }}\n"
        f"\t}}\n"
        for k in range(1, len(rights) + 1))
    mark_over = "".join(
        f"\t\tif = {{ limit = {{ var:{MOD_ID}_plan_right = {k} }} "
        f"set_variable = {{ name = {MOD_ID}_esover value = global_var:{MOD_ID}_rover{k} }} }}\n"
        for k in range(1, len(rights) + 1))
    out.append(f"""
# Everything a charter press reads that does not vary by location.
#
# `_rsh<k>` is how far charter k is below its share and `_rover<k>` says it is at
# or above it -- **the same share the plan itself granted by**, `_rquota`, which
# is towns divided by the charters this country may grant. `_rok<k>` is that
# permission, asked once at country scope because `_plan_right_gate_<k>` is a
# country trigger and a walk cannot ask one from a location.
#
# `_esover` is the answer carried onto each town: whether the charter it holds
# now is one that has more than its share. Thirteen branches once, rather than
# thirteen inside every charter's own block.
# Scope: country
{MOD_ID}_edit_right_prepare = {{
\tif = {{
\t\tlimit = {{ NOT = {{ has_global_variable = {MOD_ID}_rquota }} }}
\t\tset_global_variable = {{ name = {MOD_ID}_rquota value = 1 }}
\t}}
{prepare}\t# The fill is not to be steered by whatever the goods picker points at.
\tset_global_variable = {{ name = {MOD_ID}_edit_nofill value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_edit_strict value = 0 }}
\t{MOD_ID}_edit_set_quota = yes
\tevery_in_global_list = {{
\t\tvariable = {MOD_ID}_candidates
\t\tset_variable = {{ name = {MOD_ID}_esover value = 0 }}
\t\tset_variable = {{ name = {MOD_ID}_esc value = 0 }}
\t\tset_variable = {{ name = {MOD_ID}_esv value = 0 }}
{mark_over}\t}}
}}

""")

    def scan(k: int, strict: bool, tab: str) -> str:
        """Towns charter k could take, scored by what it would earn there."""
        over = (f"{tab}\t\tvar:{MOD_ID}_esover = 1\n" if strict else "")
        return (f"{tab}every_in_global_list = {{\n"
                f"{tab}\tvariable = {MOD_ID}_candidates\n"
                f"{tab}\tlimit = {{\n"
                f"{tab}\t\t{MOD_ID}_plan_is_town = yes\n"
                f"{tab}\t\thas_variable = {MOD_ID}_plan_right\n"
                f"{tab}\t\tNOT = {{ var:{MOD_ID}_plan_right = {k} }}\n"
                f"{tab}\t\t{MOD_ID}_edit_right_fits_{k} = yes\n"
                f"{over}{tab}\t}}\n"
                f"{tab}\tset_variable = {{ name = {MOD_ID}_esc value = 1 }}\n"
                f"{tab}\tset_variable = {{ name = {MOD_ID}_esv value = {MOD_ID}_rq{k} }}\n"
                f"{tab}}}\n")

    add_blocks = "".join(
        f"\t\tif = {{\n"
        f"\t\t\tlimit = {{ global_var:{MOD_ID}_edit_right = {k} "
        f"global_var:{MOD_ID}_rok{k} = 1 }}\n"
        f"{scan(k, True, chr(9) * 3)}"
        f"\t\t\t{MOD_ID}_edit_right_count = yes\n"
        f"\t\t\tif = {{\n"
        f"\t\t\t\tlimit = {{ global_var:{MOD_ID}_edit_cands = 0 }}\n"
        f"{scan(k, False, chr(9) * 4)}"
        f"\t\t\t\t{MOD_ID}_edit_right_count = yes\n"
        f"\t\t\t}}\n"
        f"\t\t}}\n"
        for k in range(1, len(rights) + 1))
    out.append(f"""
# How many towns the scan found. Its own effect because «+1» runs the scan twice
# -- strict, then open -- and the count has to mean the same thing both times.
# Scope: country
{MOD_ID}_edit_right_count = {{
\tset_global_variable = {{ name = {MOD_ID}_edit_cands value = 0 }}
\tevery_in_global_list = {{
\t\tvariable = {MOD_ID}_candidates
\t\tlimit = {{ var:{MOD_ID}_esc = 1 }}
\t\tchange_global_variable = {{ name = {MOD_ID}_edit_cands add = 1 }}
\t}}
}}

# **«+1» on a charter: one more town for it, taken from a charter that has more
# than its share.** Two passes, strict then open, exactly as «+1» on a good.
# Scope: country
{MOD_ID}_edit_right_add = {{
\tchange_global_variable = {{ name = {MOD_ID}_edit_presses add = 1 }}
\t{MOD_ID}_edit_clear_trace = yes
\tset_global_variable = {{ name = {MOD_ID}_edit_done value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_edit_fail value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_edit_norefill value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_edit_op value = 3 }}
\t{MOD_ID}_edit_right_prepare = yes
\t# **`_edit_strict` stays 0 through a charter press.** It steers
\t# `_edit_worst`, which is what squares the load up after the swap;
\t# left at 1 it would refuse to shed a building unless some good were
\t# over its share, and the town would stay above its cap. The charter
\t# scan has its own two passes and reads `_esover` instead.
\tset_global_variable = {{ name = {MOD_ID}_edit_cands value = 0 }}
\tif = {{
\t\tlimit = {{ global_var:{MOD_ID}_edit_right > 0 }}
{add_blocks}\t\tordered_in_global_list = {{
\t\t\tvariable = {MOD_ID}_candidates
\t\t\tlimit = {{ var:{MOD_ID}_esc = 1 }}
\t\t\torder_by = {MOD_ID}_edit_order
\t\t\tmax = 1
\t\t\tcheck_range_bounds = no
\t\t\tset_global_variable = {{ name = {MOD_ID}_ev_hit value = 1 }}
\t\t\tset_global_variable = {{ name = {MOD_ID}_ev_town value = 1 }}
\t\t\tset_global_variable = {{ name = {MOD_ID}_ev_load value = var:{MOD_ID}_load }}
\t\t\tsave_scope_as = {MOD_ID}_ev_where
\t\t\tset_global_variable = {{ name = {MOD_ID}_ev_loc value = scope:{MOD_ID}_ev_where }}
\t\t\t# Whose town it was, for the swap and for the press line.
\t\t\tset_global_variable = {{ name = {MOD_ID}_edit_rfrom value = var:{MOD_ID}_plan_right }}
\t\t\tset_global_variable = {{ name = {MOD_ID}_edit_rto value = global_var:{MOD_ID}_edit_right }}
\t\t\t{MOD_ID}_edit_right_swap = yes
\t\t\tset_global_variable = {{ name = {MOD_ID}_ev_load2 value = var:{MOD_ID}_load }}
\t\t\tset_global_variable = {{ name = {MOD_ID}_edit_done value = 1 }}
\t\t}}
\t}}
\tif = {{
\t\tlimit = {{ global_var:{MOD_ID}_edit_done = 0 }}
\t\tchange_global_variable = {{ name = {MOD_ID}_edit_idle add = 1 }}
\t}}
\t{MOD_ID}_edit_reshuffle = yes
\t{MOD_ID}_edit_journal = yes
\t{MOD_ID}_plan_rank = yes
\t{MOD_ID}_plan_show = yes
}}

""")

    best_here = "".join(
        f"\tset_variable = {{ name = {MOD_ID}_rtry value = {MOD_ID}_rq{k} }}\n"
        f"\tif = {{\n"
        f"\t\tlimit = {{\n"
        f"\t\t\tNOT = {{ global_var:{MOD_ID}_edit_rfrom = {k} }}\n"
        f"\t\t\t{MOD_ID}_edit_right_fits_{k} = yes\n"
        f"\t\t\tglobal_var:{MOD_ID}_rok{k} = 1\n"
        f"\t\t\tOR = {{\n"
        f"\t\t\t\tvar:{MOD_ID}_esrd < global_var:{MOD_ID}_rsh{k}\n"
        f"\t\t\t\tAND = {{\n"
        f"\t\t\t\t\tvar:{MOD_ID}_esrd = global_var:{MOD_ID}_rsh{k}\n"
        f"\t\t\t\t\tvar:{MOD_ID}_rtry > var:{MOD_ID}_esrv\n"
        f"\t\t\t\t}}\n"
        f"\t\t\t}}\n"
        f"\t\t}}\n"
        f"\t\tset_variable = {{ name = {MOD_ID}_esrd value = global_var:{MOD_ID}_rsh{k} }}\n"
        f"\t\tset_variable = {{ name = {MOD_ID}_esrv value = var:{MOD_ID}_rtry }}\n"
        f"\t\tset_variable = {{ name = {MOD_ID}_esrj value = {k} }}\n"
        f"\t}}\n"
        for k in range(1, len(rights) + 1))
    drop_blocks = "".join(
        f"\t\tif = {{\n"
        f"\t\t\tlimit = {{ global_var:{MOD_ID}_edit_right = {k} }}\n"
        f"\t\t\tevery_in_global_list = {{\n"
        f"\t\t\t\tvariable = {MOD_ID}_candidates\n"
        f"\t\t\t\tlimit = {{ has_variable = {MOD_ID}_plan_right "
        f"var:{MOD_ID}_plan_right = {k} }}\n"
        f"\t\t\t\tset_variable = {{ name = {MOD_ID}_esc value = 1 }}\n"
        f"\t\t\t\t# Worst first: the ordered walk reads highest, and there is no\n"
        f"\t\t\t\t# other way to ask it for a minimum -- the same inversion «−1»\n"
        f"\t\t\t\t# on a good already uses.\n"
        f"\t\t\t\tset_variable = {{ name = {MOD_ID}_esv value = {RANK_SCALE} }}\n"
        f"\t\t\t\tchange_variable = {{ name = {MOD_ID}_esv "
        f"subtract = {MOD_ID}_rq{k} }}\n"
        f"\t\t\t}}\n"
        f"\t\t}}\n"
        for k in range(1, len(rights) + 1))
    out.append(f"""
# **Which charter this town should get instead**, of those below their share and
# able to stand here. Shortfall first, what the ground pays for it as the
# tie-break -- the same two keys, in the same order, as the fill uses for goods.
#
# `_esrj` is 0 when nothing qualifies, and **that is a refusal and not a
# default**: a town with no charter at all is a state the plan never produces.
# Scope: location
{MOD_ID}_edit_right_best_here = {{
\tset_variable = {{ name = {MOD_ID}_esrj value = 0 }}
\t# Below any shortfall a real ground can produce: a charter over its share
\t# by every town of the realm would still beat this.
\tset_variable = {{ name = {MOD_ID}_esrd value = -9999 }}
\tset_variable = {{ name = {MOD_ID}_esrv value = -1 }}
{best_here}}}

# **«−1» on a charter: off the town where it earns least, and that town goes to
# whichever charter is furthest below its share.** The town keeps a charter --
# the plan grants one to every town it can, and «снять и посадить в другой» is
# what he asked for, not «снять».
# Scope: country
{MOD_ID}_edit_right_drop = {{
\tchange_global_variable = {{ name = {MOD_ID}_edit_presses add = 1 }}
\t{MOD_ID}_edit_clear_trace = yes
\tset_global_variable = {{ name = {MOD_ID}_edit_done value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_edit_fail value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_edit_norefill value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_edit_op value = 4 }}
\t{MOD_ID}_edit_right_prepare = yes
\tset_global_variable = {{ name = {MOD_ID}_edit_cands value = 0 }}
\tif = {{
\t\tlimit = {{ global_var:{MOD_ID}_edit_right > 0 }}
{drop_blocks}\t\t{MOD_ID}_edit_right_count = yes
\t\tordered_in_global_list = {{
\t\t\tvariable = {MOD_ID}_candidates
\t\t\tlimit = {{ var:{MOD_ID}_esc = 1 }}
\t\t\torder_by = {MOD_ID}_edit_order
\t\t\tmax = 1
\t\t\tcheck_range_bounds = no
\t\t\tset_global_variable = {{ name = {MOD_ID}_ev_hit value = 1 }}
\t\t\tset_global_variable = {{ name = {MOD_ID}_ev_town value = 1 }}
\t\t\tset_global_variable = {{ name = {MOD_ID}_ev_load value = var:{MOD_ID}_load }}
\t\t\tsave_scope_as = {MOD_ID}_ev_where
\t\t\tset_global_variable = {{ name = {MOD_ID}_ev_loc value = scope:{MOD_ID}_ev_where }}
\t\t\tset_global_variable = {{ name = {MOD_ID}_edit_rfrom value = global_var:{MOD_ID}_edit_right }}
\t\t\t{MOD_ID}_edit_right_best_here = yes
\t\t\tset_global_variable = {{ name = {MOD_ID}_edit_rto value = var:{MOD_ID}_esrj }}
\t\t\tif = {{
\t\t\t\tlimit = {{ var:{MOD_ID}_esrj > 0 }}
\t\t\t\t{MOD_ID}_edit_right_swap = yes
\t\t\t\tset_global_variable = {{ name = {MOD_ID}_edit_done value = 1 }}
\t\t\t}}
\t\t\telse = {{ set_global_variable = {{ name = {MOD_ID}_edit_fail value = 1 }} }}
\t\t\tset_global_variable = {{ name = {MOD_ID}_ev_load2 value = var:{MOD_ID}_load }}
\t\t}}
\t}}
\tif = {{
\t\tlimit = {{ global_var:{MOD_ID}_edit_done = 0 }}
\t\tchange_global_variable = {{ name = {MOD_ID}_edit_idle add = 1 }}
\t}}
\t{MOD_ID}_edit_reshuffle = yes
\t{MOD_ID}_edit_journal = yes
\t{MOD_ID}_plan_rank = yes
\t{MOD_ID}_plan_show = yes
}}

""")

    out.append("".join(
        f"""
# «+1» on {right.key}: one more town for it.
# Scope: country
{MOD_ID}_edit_right_plus_{k} = {{
\tset_global_variable = {{ name = {MOD_ID}_edit_right value = {k} }}
\tset_global_variable = {{ name = {MOD_ID}_edit_reached value = 1 }}
\t{MOD_ID}_edit_right_add = yes
}}

# «−1» on {right.key}: its worst town goes to a charter that has fewer.
# Scope: country
{MOD_ID}_edit_right_minus_{k} = {{
\tset_global_variable = {{ name = {MOD_ID}_edit_right value = {k} }}
\tset_global_variable = {{ name = {MOD_ID}_edit_reached value = 1 }}
\t{MOD_ID}_edit_right_drop = yes
}}
"""
        for k, right in enumerate(rights, start=1)))

    # ---- the save slot ------------------------------------------------------
    save_copy = "".join(
        f"\t\tif = {{ limit = {{ is_target_in_variable_list = "
        f"{{ name = {MOD_ID}_plan_goods target = goods:{good} }} }} "
        f"add_to_variable_list = {{ name = {MOD_ID}_save_goods target = goods:{good} }} }}\n"
        for good in order)
    # **И деревни, по зданию, а не по товару.** Деревня кладёт свой товар в
    # `_plan_goods` только ради строки; сравнение по товарам поэтому показывало
    # её приход и уход как «встал товар / ушёл товар», и владелец назвал это
    # 2026-09-13: «в списке изменений это выглядит базово как товар встал товар
    # ушёл. А должно быть деревня встала, товар ушёл». Значит в слепке должно
    # лежать и то, какие деревни стояли.
    save_vill = "".join(
        f"\t\tif = {{\n"
        f"\t\t\tlimit = {{ is_target_in_variable_list = {{ name = {MOD_ID}_plan_builds "
        f"target = building_type:{b} }} }}\n"
        f"\t\t\tadd_to_variable_list = {{ name = {MOD_ID}_save_vill "
        f"target = building_type:{b} }}\n"
        f"\t\t}}\n" for b in villages_)
    out.append(f"""
# **The baseline every «изменено» is measured against.**
#
# Written by `{MOD_ID}_plan_run` as well, so a fresh plan is its own baseline and
# the changes list right after one is empty -- which is the true answer, since a
# new plan has not been edited. Saving a slot re-bases it too, and so does
# loading one: «показать изменения» always answers «что я поменял с тех пор, как
# сохранил или загрузил», and never «чем этот план отличается от какого-то
# другого».
#
# Only the goods are kept. The building each good used is `_pm<n>`, which the
# scoring pass writes and no edit touches, so restoring puts it back from the
# good alone and the baseline needs no second list.
# Scope: country
{MOD_ID}_edit_save = {{
\tclear_global_variable_list = {MOD_ID}_save_locs
\tevery_in_global_list = {{
\t\tvariable = {MOD_ID}_plan_touched
\t\tclear_variable_list = {MOD_ID}_save_goods
\t\tclear_variable_list = {MOD_ID}_save_vill
{save_copy}{save_vill}\t\tset_variable = {{ name = {MOD_ID}_save_load value = var:{MOD_ID}_load }}
\t\tremove_variable = {MOD_ID}_save_right
\t\tif = {{
\t\t\tlimit = {{ has_variable = {MOD_ID}_plan_right }}
\t\t\tset_variable = {{ name = {MOD_ID}_save_right value = var:{MOD_ID}_plan_right }}
\t\t}}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_save_locs target = this }}
\t}}
\tset_global_variable = {{ name = {MOD_ID}_save_n value = global_var:{MOD_ID}_plan_placed }}
}}
""")

    # **There is no «вернуть сохранённое» of its own any more.** It was a button
    # on the settings page and the slots do the same thing better: loading slot N
    # is restoring, and there are three of them. The baseline `_save_*` stays --
    # it is what «показать изменения» counts against -- but nothing puts it back
    # on the map, so the effect that did was removed rather than left unreachable.

    # ---- one pair of effects per good --------------------------------------
    #
    # **The good is named, not carried.** A picker cell is written out, so it
    # knows its own number and can call an effect that knows it too. The
    # datamodel cell it replaces had to hand the good over as a saved scope --
    # `AddScope('bag_wtp_good', Goods.MakeScope)` -- and a scope reaches no
    # numbered counter, so the count could never be drawn beside it. One fewer
    # thing between the press and the plan, and the number arrives with it.
    out.append("".join(
        f"""
# «+1» for {good}.
# Scope: country
{MOD_ID}_edit_plus_{i} = {{
\t# **Asking for more of a good contradicts «не нужен», so the flag goes.**
\t# The alternative is a «+1» that silently refuses, and a button that does
\t# nothing is the thing this mod has already paid for twice. He reported the
\t# opposite defect on 2026-09-05 -- the flag set and the good still growing --
\t# and this is the honest reading of the two presses together: the last one
\t# wins, and it is visible because the checkbox clears.
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_skip{i} }}
\t\tremove_global_variable = {MOD_ID}_skip{i}
\t}}
\tset_global_variable = {{ name = {MOD_ID}_edit_good value = {i} }}
\t# The same good as a scope, because the press line has to name it and a
\t# number has no name. Here it is free: the cell is written out per good, so
\t# the good is known without a dispatch.
\tset_global_variable = {{ name = {MOD_ID}_edit_good_s value = goods:{good} }}
\tset_global_variable = {{ name = {MOD_ID}_edit_reached value = 1 }}
\t{MOD_ID}_edit_add = yes
\t# **A press is a statement, and it sticks.** `_lock<n>` becomes the count the
\t# good ended on, so the share below is computed for the goods the player has
\t# not spoken about and this one keeps what it was given. Written after the
\t# operation and unconditionally: a press that was refused still says «I want
\t# this good here», and pinning it where it stands is the honest reading.
\t{MOD_ID}_edit_pin_{i} = yes
}}

# {good} pinned where the press left it, or released if it stands nowhere.
#
# **Set or absent, never zero.** The pin is drawn in the picker by
# `GetGlobalVariable(...).IsSet`, the same form the game uses for its own flags,
# and a variable holding 0 is «set» to that reader. It still carries the count it
# was pinned at, for the day a new ground has to ask whether the share has
# outgrown it.
# Scope: country
{MOD_ID}_edit_pin_{i} = {{
\tif = {{
\t\tlimit = {{ global_var:{MOD_ID}_pn{i} > 0 }}
\t\tset_global_variable = {{ name = {MOD_ID}_lock{i} value = global_var:{MOD_ID}_pn{i} }}
\t}}
\telse = {{
\t\tremove_global_variable = {MOD_ID}_lock{i}
\t}}
}}

# «не нужен» for {good}: the standing instruction, toggled.
#
# **It removes nothing.** «Держит товар на одном домике, не на нуле», and it
# only forbids the fill from topping the good up again -- the player presses
# «−1» down to one himself, once, and the flag is what stops it coming back on
# this ground and on every ground after. Its whole purpose is «чтобы не кликать
# их в минус при каждом добавлении земли».
#
# Absent means off, which is why this sets and removes rather than writing 0.
# Scope: country
{MOD_ID}_edit_skip_{i} = {{
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_skip{i} }}
\t\tremove_global_variable = {MOD_ID}_skip{i}
\t}}
\telse = {{
\t\tset_global_variable = {{ name = {MOD_ID}_skip{i} value = 1 }}
\t}}
\t# The share below is computed for the goods still free, and this press just
\t# changed which those are.
\t{MOD_ID}_edit_set_quota = yes
}}

# «−1» for {good}.
# Scope: country
{MOD_ID}_edit_minus_{i} = {{
\tset_global_variable = {{ name = {MOD_ID}_edit_good value = {i} }}
\tset_global_variable = {{ name = {MOD_ID}_edit_good_s value = goods:{good} }}
\tset_global_variable = {{ name = {MOD_ID}_edit_reached value = 1 }}
\t{MOD_ID}_edit_drop = yes
\t{MOD_ID}_edit_pin_{i} = yes
}}
"""
        for i, good in enumerate(order, start=1)))

    # **И та же пара на каждую деревню.** Отличий от товара ровно три: нет
    # «не нужен» (деревню доливка не возвращает -- она ходит по товарам), нет
    # замка (`_lock<n>` читает тот же обход) и код операции свой, 5 и 6, чтобы
    # строка нажатия называла домик, а не товар: у деревни товара нет, у неё
    # есть здание.
    out.append("".join(
        f"""
# «+1» на {building}.
# Scope: country
{MOD_ID}_edit_plus_{len(order) + k} = {{
\tset_global_variable = {{ name = {MOD_ID}_edit_good value = {len(order) + k} }}
\tset_global_variable = {{ name = {MOD_ID}_edit_vill_s value = building_type:{building} }}
\tset_global_variable = {{ name = {MOD_ID}_edit_reached value = 1 }}
\t{MOD_ID}_edit_add = yes
\t# **После, а не до**: `_edit_add` ставит `_edit_op = 1` сам, и код деревни
\t# обязан пережить его, иначе строка нажатия назовёт товар, которого нет.
\tset_global_variable = {{ name = {MOD_ID}_edit_op value = 5 }}
}}

# «−1» на {building}.
# Scope: country
{MOD_ID}_edit_minus_{len(order) + k} = {{
\tset_global_variable = {{ name = {MOD_ID}_edit_good value = {len(order) + k} }}
\tset_global_variable = {{ name = {MOD_ID}_edit_vill_s value = building_type:{building} }}
\tset_global_variable = {{ name = {MOD_ID}_edit_reached value = 1 }}
\t{MOD_ID}_edit_drop = yes
\tset_global_variable = {{ name = {MOD_ID}_edit_op value = 6 }}
}}
"""
        for k, building in enumerate(villages_, start=1)))

    # **Локация очищается от всего планового разом, и это нужно житнице.**
    #
    # Его слово 2026-09-13: «если я нажму на эту кнопку в режиме редактора --
    # изменения должны произойти сразу же, т.е. исчезнуть из локации домики
    # плана и встать домики житницы». Значит нужен обратный ход для всего, что
    # план на локацию кладёт: товары, деревни и грамота.
    #
    # **Каждая половина снимается тем же, чем ставилась**, а не голым
    # `clear_variable_list`: счётчики товара, доли и грамоты иначе остались бы
    # такими, будто домики на месте, и сводка врала бы до следующего
    # «Пересчитать». `_edit_remove_*` и `_plan_drop_village_*` сами спрашивают,
    # стоит ли тут то, что они снимают, поэтому зовутся без обёрток.
    wipe_goods = "".join(call("edit_remove", i, "\t")
                         for i in range(1, len(order) + 1))
    wipe_vill = "".join(f"\t{MOD_ID}_plan_drop_village_{k} = yes\n"
                        for k in range(1, len(villages_) + 1))
    wipe_right = "".join(f"""\tif = {{
\t\tlimit = {{ has_variable = {MOD_ID}_plan_right var:{MOD_ID}_plan_right = {k} }}
\t\tchange_global_variable = {{ name = {MOD_ID}_rgiven{k} subtract = 1 }}
\t\tchange_global_variable = {{ name = {MOD_ID}_rn{k} subtract = 1 }}
\t\tchange_global_variable = {{ name = {MOD_ID}_plan_rightn subtract = 1 }}
\t}}
""" for k in range(1, len(rights) + 1))
    out.append(f"""
# Всё плановое с этой локации долой: товары, деревни, грамота.
# Scope: location
{MOD_ID}_edit_wipe_here = {{
{wipe_goods}{wipe_vill}{wipe_right}\tremove_variable = {MOD_ID}_plan_right
}}
""")

    # ---- the numbered slots -------------------------------------------------
    #
    # **Three plans kept side by side**, and the reason is his: «я проебу свой
    # сохранённый план, если захочу посмотреть какой-то план на другой земле».
    # A slot holds what the baseline holds -- the goods on each location the plan
    # touched, the load, the charter -- under a name of its own, and writing one
    # re-bases the changes list as well, so «показать изменения» after a save is
    # empty and after an edit is the edit.
    #
    # **A slot is restored through `_plan_try_*` and not by writing the lists
    # back.** The building a good uses is `_pm<n>`, which the scoring pass wrote
    # and no edit touches, so the good alone is enough to put the building back --
    # and a restored plan is then counted by the very same effects that counted
    # the planned one, with no second accounting to drift. The price is that a
    # slot saved on ground that has since been re-scored comes back scored the new
    # way, which is the honest answer rather than a stale one.
    for slot in range(1, EDIT_SLOTS + 1):
        keep = "".join(
            f"\t\tif = {{ limit = {{ is_target_in_variable_list = "
            f"{{ name = {MOD_ID}_plan_goods target = goods:{good} }} }} "
            f"add_to_variable_list = {{ name = {MOD_ID}_sl{slot}_goods target = goods:{good} }} }}\n"
            for good in order)
        # **A slot keeps what was said as well as what was built.** His rule,
        # 2026-09-05: «в загрузке сохранённого плана точно не должно быть того,
        # что было сделано после сохранения плана». The «не нужен» flags are his
        # own choice -- he chose that the slot remember them -- and the pins get
        # the same treatment, because they are the other half of the same
        # sentence and he had no reason to hold an opinion about a mechanism
        # nothing on screen had ever shown him.
        #
        # Absent stays absent: both are existence flags, so the slot stores
        # «there was one» and the load sets or removes to match. A slot never
        # written holds neither, and loading it releases everything -- which is
        # the honest reading of «this plan was saved before any of that».
        keep_marks = "".join(
            f"\tif = {{ limit = {{ has_global_variable = {MOD_ID}_skip{i} }}\n"
            f"\t\tset_global_variable = {{ name = {MOD_ID}_sl{slot}_skip{i} value = 1 }} }}\n"
            f"\telse = {{ remove_global_variable = {MOD_ID}_sl{slot}_skip{i} }}\n"
            f"\tif = {{ limit = {{ has_global_variable = {MOD_ID}_lock{i} }}\n"
            f"\t\tset_global_variable = {{ name = {MOD_ID}_sl{slot}_lock{i} "
            f"value = global_var:{MOD_ID}_lock{i} }} }}\n"
            f"\telse = {{ remove_global_variable = {MOD_ID}_sl{slot}_lock{i} }}\n"
            for i in range(1, len(order) + 1))
        load_marks = "".join(
            f"\t\tif = {{ limit = {{ has_global_variable = {MOD_ID}_sl{slot}_skip{i} }}\n"
            f"\t\t\tset_global_variable = {{ name = {MOD_ID}_skip{i} value = 1 }} }}\n"
            f"\t\telse = {{ remove_global_variable = {MOD_ID}_skip{i} }}\n"
            f"\t\tif = {{ limit = {{ has_global_variable = {MOD_ID}_sl{slot}_lock{i} }}\n"
            f"\t\t\tset_global_variable = {{ name = {MOD_ID}_lock{i} "
            f"value = global_var:{MOD_ID}_sl{slot}_lock{i} }} }}\n"
            f"\t\telse = {{ remove_global_variable = {MOD_ID}_lock{i} }}\n"
            for i in range(1, len(order) + 1))
        given = "".join(
            f"\t\t\t\tif = {{ limit = {{ var:{MOD_ID}_sl{slot}_right = {k} }} "
            f"change_global_variable = {{ name = {MOD_ID}_rgiven{k} add = 1 }} }}\n"
            for k in range(1, len(rights) + 1))
        put = "".join(
            f"\t\t\tif = {{ limit = {{ is_target_in_variable_list = "
            f"{{ name = {MOD_ID}_sl{slot}_goods target = goods:{good} }} }}\n"
            f"{call('plan_try', i, chr(9) * 4)}\t\t\t}}\n"
            for i, good in enumerate(order, start=1))
        out.append(f"""
# Slot {slot}: the plan as it stands now, kept under a name of its own.
# Scope: country
{MOD_ID}_edit_store_{slot} = {{
\tclear_global_variable_list = {MOD_ID}_sl{slot}_locs
\tevery_in_global_list = {{
\t\tvariable = {MOD_ID}_plan_touched
\t\tclear_variable_list = {MOD_ID}_sl{slot}_goods
{keep}\t\tset_variable = {{ name = {MOD_ID}_sl{slot}_load value = var:{MOD_ID}_load }}
\t\tremove_variable = {MOD_ID}_sl{slot}_right
\t\tif = {{
\t\t\tlimit = {{ has_variable = {MOD_ID}_plan_right }}
\t\t\tset_variable = {{ name = {MOD_ID}_sl{slot}_right value = var:{MOD_ID}_plan_right }}
\t\t}}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_sl{slot}_locs target = this }}
\t}}
{keep_marks}\tset_global_variable = {{ name = {MOD_ID}_sl{slot}_n value = global_var:{MOD_ID}_plan_placed }}
\tset_global_variable = {{ name = {MOD_ID}_sl{slot}_locn value = global_var:{MOD_ID}_plan_shown }}
\t# The saved plan is what the next «показать изменения» is measured against.
\t{MOD_ID}_edit_save = yes
}}

# Slot {slot} back onto the map, in place of whatever the plan holds now.
# Scope: country
{MOD_ID}_edit_load_{slot} = {{
\tif = {{
\t\tlimit = {{ global_var:{MOD_ID}_sl{slot}_n > 0 }}
\t\t{MOD_ID}_edit_clear_plan = yes
\t\tevery_in_global_list = {{
\t\t\tvariable = {MOD_ID}_sl{slot}_locs
\t\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_plan_touched target = this }}
\t\t\tif = {{
\t\t\t\tlimit = {{ has_variable = {MOD_ID}_sl{slot}_right }}
\t\t\t\tset_variable = {{ name = {MOD_ID}_plan_right value = var:{MOD_ID}_sl{slot}_right }}
\t\t\t\t# **The charter counters are rebuilt and not left where the last plan
\t\t\t\t# put them.** `_rgiven<k>` is what the diagnosis prints as «выдано» and
\t\t\t\t# `_plan_rightn` is the number on the window; a slot loaded over a plan
\t\t\t\t# for other ground would otherwise report that ground's charters, which
\t\t\t\t# is a wrong number rather than a missing one.
\t\t\t\tchange_global_variable = {{ name = {MOD_ID}_plan_rightn add = 1 }}
{given}\t\t\t}}
{put}\t\t}}
{load_marks}\t\t{MOD_ID}_plan_rank = yes
\t\t{MOD_ID}_plan_show = yes
\t\t# The share follows the pins and the flags, and both just changed.
\t\t{MOD_ID}_edit_set_quota = yes
\t\t# The loaded plan is the baseline, so the changes list starts empty here.
\t\t{MOD_ID}_edit_save = yes
\t}}
}}
""")
    zero_counts = "".join(
        f"\tset_global_variable = {{ name = {MOD_ID}_pn{i} value = 0 }}\n"
        for i in range(1, len(order) + 1))
    zero_counts += "".join(
        f"\tset_global_variable = {{ name = {MOD_ID}_rgiven{k} value = 0 }}\n"
        for k in range(1, len(rights) + 1))
    out.append(f"""
# Every location the plan stands on emptied, and every counter with it. Shared by
# the restore and by each slot's load, because a plan half-cleared is the failure
# that shows up as a number rather than as an error.
# Scope: country
{MOD_ID}_edit_clear_plan = {{
\t# **The reshuffle's markers go with the plan they belong to.** A slot
\t# loaded is a different set of buildings, and a marker left behind would
\t# trade something the fill never put there.
\t{MOD_ID}_edit_clear_fillset = yes
\tevery_in_global_list = {{
\t\tvariable = {MOD_ID}_plan_touched
\t\tclear_variable_list = {MOD_ID}_plan_goods
\t\tclear_variable_list = {MOD_ID}_plan_builds
\t\tset_variable = {{ name = {MOD_ID}_load value = 0 }}
\t\tremove_variable = {MOD_ID}_plan_right
\t}}
\tclear_global_variable_list = {MOD_ID}_plan_touched
\tset_global_variable = {{ name = {MOD_ID}_plan_placed value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_plan_gain value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_plan_fed value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_plan_rightn value = 0 }}
{zero_counts}}}
""")

    # ---- the editor window's own two lists ----------------------------------
    #
    # **The picker offers what this ground can make and nothing else, and every
    # row of it carries its own «−1» and «+1».** 47 icons of which half are
    # impossible here is a worse picker than 20 that are all real, and `_ng<n>` --
    # how many candidates can make the good, counted by the plan's own scan -- is
    # the number that says which.
    #
    # **There is no second list of «goods being worked on» any more.** There was,
    # and clicking a good's icon put it there with the buttons beside it; he
    # opened the window and found no way in, 2026-09-03: «там только их иконки и
    # ничего больше, что могло бы дать мне инструмент влияния, никаких кнопочек
    # +1 или -1». Controls you have to discover by clicking are controls that are
    # not there. Now every good the ground can make has its buttons in place, one
    # row each, and nothing is hidden behind a first click.
    #
    # **`has_global_variable` before the comparison.** `_ng<n>` is written by the
    # scoring pass and by nothing else, so before the first plan of a save it does
    # not exist -- and a `limit` reading a global that is not there is the failure
    # this repository names first. Here the wrong answer and the right one happen
    # to agree (no plan, nothing to edit), which is how such a thing survives.
    # **The picker is dealt into rows here, in script, and not by the window.**
    # `EDIT_ROW` goods to a row, `EDIT_ROWS` rows, each its own list. That is
    # what lets the window draw the picker with an `hbox` over a datamodel --
    # the one horizontal list this mod has drawn correctly since its first
    # build, in every location's goods row -- instead of a wrapping widget.
    #
    # Two wrapping widgets were tried and both failed on their first load. A
    # `flowcontainer` with a datamodel killed the game outright, four builds
    # running, silently (`docs/pitfalls/interface.md`). A `fixedgridbox` did not
    # crash but laid the cells out wrong -- some past the window's right edge,
    # some underneath each other -- and its `addcolumn`/`addrow` are a pitch or
    # an increment depending on who you ask. **A row is a row.**
    rows = "".join(
        f"\tif = {{\n"
        f"\t\tlimit = {{ has_global_variable = {MOD_ID}_ng{i} "
        f"global_var:{MOD_ID}_ng{i} > 0 }}\n"
        f"\t\tchange_global_variable = {{ name = {MOD_ID}_edit_pooln add = 1 }}\n"
        f"\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_edit_pool "
        f"target = goods:{good} }}\n"
        f"\t\tset_variable = {{ name = {MOD_ID}_pool{i} value = 1 }}\n"
        f"\t}}\n\telse = {{ remove_variable = {MOD_ID}_pool{i} }}\n"
        for i, good in enumerate(order, start=1))
    clears = ""
    out.append(f"""
# The goods the editor offers, rebuilt whenever its window opens.
#
# `_edit_pool` is the whole of them, for the count and the empty state.
# `_pool<n>` is the same answer as a country flag, one a good, and **that is
# what the picker's cells ask**: the cells are written out rather than drawn
# from the list, because only a written cell can print `_pn<n>` beside the good.
# A cell whose flag is unset is invisible and its row closes the gap.
# Scope: country
{MOD_ID}_edit_fill_pool = {{
\t# The header prints the share, so it has to be current before the window is
\t# drawn and not only after the first press.
\t{MOD_ID}_edit_set_quota = yes
\tclear_global_variable_list = {MOD_ID}_edit_pool
{clears}\tset_global_variable = {{ name = {MOD_ID}_edit_pooln value = 0 }}
{rows}}}

""")

    # ---- what the editing changed ------------------------------------------
    changed = "".join(
        f"\t\t\t\tAND = {{ is_target_in_variable_list = {{ name = {MOD_ID}_save_goods target = goods:{good} }} "
        f"NOT = {{ is_target_in_variable_list = {{ name = {MOD_ID}_plan_goods target = goods:{good} }} }} }}\n"
        f"\t\t\t\tAND = {{ is_target_in_variable_list = {{ name = {MOD_ID}_plan_goods target = goods:{good} }} "
        f"NOT = {{ is_target_in_variable_list = {{ name = {MOD_ID}_save_goods target = goods:{good} }} }} }}\n"
        for good in order)
    lines2 = "".join(
        f'\t\tif = {{ limit = {{ is_target_in_variable_list = {{ name = {MOD_ID}_save_goods target = goods:{good} }} '
        f'NOT = {{ is_target_in_variable_list = {{ name = {MOD_ID}_plan_goods target = goods:{good} }} }} }} '
        f'debug_log = "WTP LD -{good}" }}\n'
        f'\t\tif = {{ limit = {{ is_target_in_variable_list = {{ name = {MOD_ID}_plan_goods target = goods:{good} }} '
        f'NOT = {{ is_target_in_variable_list = {{ name = {MOD_ID}_save_goods target = goods:{good} }} }} }} '
        f'debug_log = "WTP LD +{good}" }}\n'
        for good in order)
    # **Приход и уход деревни -- это здание, а не товар.** Деревня кладёт товар в
    # `_plan_goods` только ради строки локации, поэтому по товарам её появление
    # читалось как «встал товар», и владелец это назвал, 2026-09-13: «должно
    # быть деревня встала, товар ушёл».
    #
    # Две пары списков: `_chg_out`/`_chg_in` -- товары, `_chg_bout`/`_chg_bin` --
    # здания. Окно рисует их одну за другой в том же столбце.
    #
    # **И товар-призрак из строки гасится.** Товар, которым деревня «торгует»,
    # приходит и уходит вместе с ней; строка про него была бы вторым сообщением
    # об одном событии. `_vw<k>` -- какой это товар, и он пишется оценкой, а не
    # постановкой, так что верен и для ушедшей деревни.
    def phantom(good: str, side: str) -> str:
        """Условие «этот товар пришёл (ушёл) не сам, а с деревней»."""
        i = order.index(good) + 1
        arms = []
        for k, building in enumerate(villages_, start=1):
            here = (f"is_target_in_variable_list = {{ name = {MOD_ID}_plan_builds "
                    f"target = building_type:{building} }}")
            was = (f"is_target_in_variable_list = {{ name = {MOD_ID}_save_vill "
                   f"target = building_type:{building} }}")
            moved = (f"AND = {{ {here} NOT = {{ {was} }} }}" if side == "in"
                     else f"AND = {{ {was} NOT = {{ {here} }} }}")
            arms.append(f"AND = {{ var:{MOD_ID}_vw{k} = {i} {moved} }}")
        return "NOT = { OR = { %s } }" % " ".join(arms) if arms else ""

    rows = "".join(
        f"\t\tif = {{ limit = {{ is_target_in_variable_list = {{ name = {MOD_ID}_save_goods target = goods:{good} }} "
        f"NOT = {{ is_target_in_variable_list = {{ name = {MOD_ID}_plan_goods target = goods:{good} }} }} "
        f"{phantom(good, 'out')} }}\n"
        f"\t\t\tadd_to_variable_list = {{ name = {MOD_ID}_chg_out target = goods:{good} }}\n"
        f"\t\t\tchange_variable = {{ name = {MOD_ID}_chg_n add = 1 }}\n"
        f"\t\t}}\n"
        f"\t\tif = {{ limit = {{ is_target_in_variable_list = {{ name = {MOD_ID}_plan_goods target = goods:{good} }} "
        f"NOT = {{ is_target_in_variable_list = {{ name = {MOD_ID}_save_goods target = goods:{good} }} }} "
        f"{phantom(good, 'in')} }}\n"
        f"\t\t\tadd_to_variable_list = {{ name = {MOD_ID}_chg_in target = goods:{good} }}\n"
        f"\t\t\tchange_variable = {{ name = {MOD_ID}_chg_n add = 1 }}\n"
        f"\t\t}}\n"
        for good in order) + "".join(
        f"\t\tif = {{ limit = {{ is_target_in_variable_list = {{ name = {MOD_ID}_save_vill target = building_type:{b} }} "
        f"NOT = {{ is_target_in_variable_list = {{ name = {MOD_ID}_plan_builds target = building_type:{b} }} }} }}\n"
        f"\t\t\tadd_to_variable_list = {{ name = {MOD_ID}_chg_bout target = building_type:{b} }}\n"
        f"\t\t\tchange_variable = {{ name = {MOD_ID}_chg_n add = 1 }}\n"
        f"\t\t}}\n"
        f"\t\tif = {{ limit = {{ is_target_in_variable_list = {{ name = {MOD_ID}_plan_builds target = building_type:{b} }} "
        f"NOT = {{ is_target_in_variable_list = {{ name = {MOD_ID}_save_vill target = building_type:{b} }} }} }}\n"
        f"\t\t\tadd_to_variable_list = {{ name = {MOD_ID}_chg_bin target = building_type:{b} }}\n"
        f"\t\t\tchange_variable = {{ name = {MOD_ID}_chg_n add = 1 }}\n"
        f"\t\t}}\n"
        for b in villages_)
    out.append(f"""
# «Показать изменения»: every location where the plan now differs from the saved
# one, and nothing else.
#
# **It fills a window and writes the same report to the log.** The window is what
# he asked for -- «кнопка показать список изменений, которое откроет ещё одно
# окно» -- and the log line stays because `mods.bat -> «Забрать диагностику из игры»` and `tools/diag.py`
# already fold a location's `LD` lines into «изменено: убрано X; добавлено Y»,
# which is how a change gets into a session without a screenshot.
#
# **Two lists on the location and a count beside them.** `_chg_out` is what left,
# `_chg_in` is what arrived, and `_chg_n` is how many of both -- the count is
# there because a `limit` cannot ask whether a variable list is empty, and
# `{MOD_ID}_chg_locs` must hold only the locations that really moved. Only those
# are printed, so after one edit the whole report is two lines, which is the
# point of the thing.
# Scope: country
{MOD_ID}_edit_changes = {{
\tset_global_variable = {{ name = {MOD_ID}_edit_moved value = 0 }}
\tclear_global_variable_list = {MOD_ID}_chg_locs
\tdebug_log_date = yes
\terror_log = "WTP the changes list is in debug.log, tag WTP. mods.bat -> «Забрать диагностику из игры» takes it out."
\tdebug_log = "WTP ==== BEGIN v{DIAG_VERSION} ==== the plan against the saved one"
\t# **Первый проход считает разницу, второй раскладывает её по порядку.**
\t# `_chg_rank` -- ключ сортировки: `10000 − номер нажатия`, потому что
\t# `order_by` читает от большего к меньшему, а нужен порядок нажатий.
\t# Локация, изменённая не нажатием (новый план против старого слота),
\t# ранга не получает и уходит в конец списка -- у неё номера нет.
\tevery_in_global_list = {{
\t\tvariable = {MOD_ID}_plan_touched
\t\tclear_variable_list = {MOD_ID}_chg_out
\t\tclear_variable_list = {MOD_ID}_chg_in
\t\tclear_variable_list = {MOD_ID}_chg_bout
\t\tclear_variable_list = {MOD_ID}_chg_bin
\t\tset_variable = {{ name = {MOD_ID}_chg_n value = 0 }}
\t\tset_variable = {{ name = {MOD_ID}_chg_rank value = 0 }}
\t\t# **A moved charter is a change even when no building moved.** Two
\t\t# charters can share a whole bundle -- royal_naval_rights and
\t\t# scandinavian_tar_privileges are both naval_supplies and tar -- and
\t\t# without this the town would be missing from the list it belongs in.
\t\tif = {{
\t\t\tlimit = {{
\t\t\t\tOR = {{
\t\t\t\t\tAND = {{ has_variable = {MOD_ID}_plan_right NOT = {{ has_variable = {MOD_ID}_save_right }} }}
\t\t\t\t\tAND = {{ has_variable = {MOD_ID}_save_right NOT = {{ has_variable = {MOD_ID}_plan_right }} }}
\t\t\t\t\tAND = {{
\t\t\t\t\t\thas_variable = {MOD_ID}_plan_right
\t\t\t\t\t\thas_variable = {MOD_ID}_save_right
\t\t\t\t\t\tNOT = {{ var:{MOD_ID}_plan_right = var:{MOD_ID}_save_right }}
\t\t\t\t\t}}
\t\t\t\t}}
\t\t\t}}
\t\t\tchange_variable = {{ name = {MOD_ID}_chg_n add = 1 }}
\t\t}}
{rows}\t\tif = {{
\t\t\tlimit = {{ var:{MOD_ID}_chg_n > 0 }}
\t\t\tchange_global_variable = {{ name = {MOD_ID}_edit_moved add = 1 }}
\t\t\tset_variable = {{ name = {MOD_ID}_chg_rank value = 1 }}
\t\t\tif = {{
\t\t\t\tlimit = {{ has_variable = {MOD_ID}_chg_seq }}
\t\t\t\tset_variable = {{ name = {MOD_ID}_chg_rank value = 10000 }}
\t\t\t\tchange_variable = {{ name = {MOD_ID}_chg_rank subtract = var:{MOD_ID}_chg_seq }}
\t\t\t}}
\t\t}}
\t}}
\t# **Список строится вторым проходом, в порядке нажатий.** До 2026-09-06
\t# он строился первым и шёл по `_plan_touched`, то есть по номерам
\t# локаций: десять «+1» по коже приходили вперемешку с тем, что было
\t# изменено раньше. Его слова: «в начале списка я могу увидеть что-то
\t# другое, а потом кожу-кожу, другое, кожу-кожу».
\t#
\t# `max` больше любого правдоподобного числа изменённых локаций, а
\t# `check_range_bounds = no` -- потому что список почти всегда короче.
\tordered_in_global_list = {{
\t\tvariable = {MOD_ID}_plan_touched
\t\tlimit = {{ var:{MOD_ID}_chg_n > 0 }}
\t\torder_by = {MOD_ID}_chg_order
\t\tmax = 1000
\t\tcheck_range_bounds = no
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_chg_locs target = this }}
\t\tdebug_log_scopes = no
\t\tdebug_log = "WTP L rank=0 town=0 load=0"
{lines2}\t}}
\tdebug_log = "WTP ==== END v{DIAG_VERSION} ===="
}}
"""

)

    # ---- the windows, and the counters they read ---------------------------
    row_inits = ""
    # ---- шаг 6: новая земля, долитая к готовому плану -----------------------
    #
    # **Одно правило на все три его случая**, и оно написано целиком в
    # `docs/investigations/wtp_editor_design.md` -> «Решение: новая земля»:
    # **замок морозит то, что стоит на земле X; новые комнаты земли Y заливаются
    # под новую долю; замок спадает, когда доля его перерастает.** Сравнение
    # замка с долей происходит **только когда земля изменилась** -- то есть
    # ровно здесь, на одно нажатие, а не на каждой правке.
    #
    # **Форма -- одна кнопка, и это его выбор, а не догадка.** Земля и так
    # набирается по клику: `_picked_locations` растёт кнопками карты, которые
    # теперь стоят и в окне редактора. Значит «вторая земля» не нуждается ни в
    # каком новом понятии -- она есть то, что выбрано сейчас, минус то, на чём
    # план уже стоит. Три формы, из которых выбиралось (вторая пара кнопок
    # земли; слот с заливкой поверх; эта), -- в практическом плане шага 6.
    #
    # **Это функция 4, а не 3.** «Пересчитать» сносит все `_lock<n>` и считает с
    # нуля; доливка их читает. Поэтому кнопка в окне редактора, рядом с тем, что
    # она уважает, а не рядом с тем, что их стирает.
    lift = "".join(
        f"""\tif = {{
\t\tlimit = {{
\t\t\thas_global_variable = {MOD_ID}_lock{i}
\t\t\tglobal_var:{MOD_ID}_pq{i} > global_var:{MOD_ID}_pn{i}
\t\t}}
\t\tremove_global_variable = {MOD_ID}_lock{i}
\t\tchange_global_variable = {{ name = {MOD_ID}_ext_lifted add = 1 }}
\t}}
"""
        for i in range(1, len(order) + 1))
    # **Незамороженный товар идёт по своей плановой квоте, а не по редакторской.**
    # `_plan_set_quota` только что посчитан по всей земле Z = X + Y: две доли
    # сторон, перелив, скидка за РГО. Доливка кладёт новую землю к старой,
    # стремясь к тому же плану, каким он был бы на Z целиком, — значит и квота
    # ей нужна та же. Раньше здесь стояло `_pqt = _pqr = _eq<i>` — одно
    # редакторское число в обе стороны, — и вся арифметика долей, выправленная
    # 2026-09-08, до доливки не доезжала.
    freeze = "".join(
        f"""\tif = {{
\t\tlimit = {{ OR = {{ has_global_variable = {MOD_ID}_lock{i} has_global_variable = {MOD_ID}_skip{i} }} }}
\t\tset_global_variable = {{ name = {MOD_ID}_frz{i} value = 1 }}
\t\tset_global_variable = {{ name = {MOD_ID}_pqt{i} value = global_var:{MOD_ID}_pnt{i} }}
\t\tset_global_variable = {{ name = {MOD_ID}_pqr{i} value = global_var:{MOD_ID}_pnr{i} }}
\t}}
\telse = {{
\t\tremove_global_variable = {MOD_ID}_frz{i}
\t}}
"""
        for i in range(1, len(order) + 1))
    thaw = "".join(f"\tremove_global_variable = {MOD_ID}_frz{i}\n"
                   for i in range(1, len(order) + 1))
    out.append(f"""
# Что из выбранной земли план ещё не видел.
#
# **`_plan_touched` -- это и есть «земля X»**: план кладёт туда каждую свою
# локацию и ничего оттуда не убирает, кроме как на «Пересчитать». Значит
# «новое» -- это кандидат, которого в этом списке нет, и второго признака
# заводить не нужно.
# Scope: country
{MOD_ID}_ext_split = {{
\tclear_global_variable_list = {MOD_ID}_ext_locs
\tset_global_variable = {{ name = {MOD_ID}_ext_new value = 0 }}
\tevery_in_global_list = {{
\t\tvariable = {MOD_ID}_candidates
\t\tlimit = {{
\t\t\tNOT = {{ is_target_in_global_variable_list = {{ name = {MOD_ID}_plan_touched target = this }} }}
\t\t}}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_ext_locs target = this }}
\t\tchange_global_variable = {{ name = {MOD_ID}_ext_new add = 1 }}
\t}}
}}

# Кандидаты -- только новая земля.
#
# **Это единственное, что не даёт доливке тронуть старую.** Всё, что ставит
# здания -- `_plan_grant_pass`, `_plan_pick_<n>` и весь `_plan_allocate` -- ходит
# по `_candidates` и никуда больше; сузить список значит сузить их все разом, не
# трогая ни одной их строки. Обратно список собирает `{MOD_ID}_collect_candidates`
# из того же выбора, из которого собрал бы его план.
# Scope: country
{MOD_ID}_ext_only = {{
\tclear_global_variable_list = {MOD_ID}_candidates
\tset_global_variable = {{ name = {MOD_ID}_candidate_count value = 0 }}
\tevery_in_global_list = {{
\t\tvariable = {MOD_ID}_ext_locs
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_candidates target = this }}
\t\tchange_global_variable = {{ name = {MOD_ID}_candidate_count add = 1 }}
\t}}
}}

# Новая земля, приведённая в то же состояние, в каком план держит свою.
#
# **Ровно тот же блок, что в `{MOD_ID}_plan_prepare`, но по одному списку.** Он
# не «готовит к плану» -- он вносит локацию в учёт плана: комнаты в
# `_plan_rooms`, город в `_plan_towns`, провинцию в `_plan_prov_locs`. Без этого
# доля считалась бы по старой земле, а свёрнутый список не показал бы новых
# провинций.
#
# **`_plan_seen` метит всю провинцию целиком**, поэтому провинция, наполовину
# бывшая в X, вторым своим куском в список провинций не попадёт -- что и нужно.
# Scope: country
{MOD_ID}_ext_prepare = {{
\tevery_in_global_list = {{
\t\tvariable = {MOD_ID}_ext_locs
\t\tset_variable = {{ name = {MOD_ID}_load value = 0 }}
\t\tset_variable = {{ name = {MOD_ID}_plan_prank value = 9999 }}
\t\t# **Продовольственный потенциал -- в переменную, а не в строку.** Он не
\t\t# зависит от плана вовсе, только от локации, поэтому считается один раз
\t\t# на обходе: `visible` в ряду умеет читать переменную и не умеет звать
\t\t# значение, а сорок строк со своим счётом на кадр -- это `panel_hitch`.
\t\tset_variable = {{ name = {MOD_ID}_food_pot value = {MOD_ID}_food_potential }}
\t\tif = {{
\t\t\tlimit = {{ NOT = {{ var:{MOD_ID}_food_pot > 0 }} }}
\t\t\tremove_variable = {MOD_ID}_food_pot
\t\t}}
\t\tremove_variable = {MOD_ID}_plan_right
\t\tclear_variable_list = {MOD_ID}_plan_goods
\t\tclear_variable_list = {MOD_ID}_plan_builds
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_plan_touched target = this }}
\t\tif = {{
\t\t\tlimit = {{ {MOD_ID}_plan_is_town = yes }}
\t\t\tset_variable = {{ name = {MOD_ID}_plan_town_row value = 1 }}
\t\t}}
\t\telse = {{
\t\t\tremove_variable = {MOD_ID}_plan_town_row
\t\t}}
\t\tif = {{
\t\t\tlimit = {{ NOT = {{ has_variable = {MOD_ID}_plan_seen }} }}
\t\t\tprovince_definition = {{
\t\t\t\tevery_location_in_province_definition = {{
\t\t\t\t\tset_variable = {{ name = {MOD_ID}_plan_seen value = 1 }}
\t\t\t\t}}
\t\t\t}}
\t\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_plan_prov_locs target = this }}
\t\t}}
\t}}
}}

# Комнаты, города и провинции — пересчитаны по земле, а не досчитаны к прошлому.
#
# **Копить их было ошибкой, и она стоила прогона 2026-09-06.** `_plan_rooms`
# обнуляет только `_plan_prepare`, которого доливка не зовёт, — а загрузка слота
# перестраивает `_plan_touched`, ничего не вычитая. Владелец увидел «358 зданий
# на 690 мест (52% заполнено)» там, где земля была забита целиком: 55 городов по
# 4 плюс 46 сёл по 3 — это ровно 358. Раздутыми оказались и `_plan_towns` (69
# против настоящих 55), и доля: 690÷38 дало 18 вместо 9, то есть квота не
# ограничивала никого и раздачу решала одна выгода.
#
# **Три числа считаются по списку, поэтому расходиться им больше не с чем.**
# Один обход по `_plan_touched` и один по `_plan_prov_locs`; на 101 локации это
# ничто рядом с самим счётом.
# Scope: country
{MOD_ID}_ext_recount = {{
\tset_global_variable = {{ name = {MOD_ID}_plan_rooms value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_prooms_t value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_prooms_r value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_plan_towns value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_plan_provn value = 0 }}
\tevery_in_global_list = {{
\t\tvariable = {MOD_ID}_plan_touched
\t\tif = {{
\t\t\tlimit = {{
\t\t\t\t{MOD_ID}_is_granary = no
\t\t\t\t{MOD_ID}_plan_is_town = yes
\t\t\t}}
\t\t\tchange_global_variable = {{ name = {MOD_ID}_plan_rooms add = {MOD_ID}_show_plan_cap_urban }}
\t\t\tchange_global_variable = {{ name = {MOD_ID}_prooms_t add = {MOD_ID}_show_plan_cap_urban }}
\t\t\tchange_global_variable = {{ name = {MOD_ID}_plan_towns add = 1 }}
\t\t}}
\t\telse_if = {{
\t\t\tlimit = {{ {MOD_ID}_is_granary = no }}
\t\t\tchange_global_variable = {{ name = {MOD_ID}_plan_rooms add = {MOD_ID}_show_plan_cap_rural }}
\t\t\tchange_global_variable = {{ name = {MOD_ID}_prooms_r add = {MOD_ID}_show_plan_cap_rural }}
\t\t}}
\t}}
\tevery_in_global_list = {{
\t\tvariable = {MOD_ID}_plan_prov_locs
\t\tchange_global_variable = {{ name = {MOD_ID}_plan_provn add = 1 }}
\t}}
}}

# Замок, который переросла доля.
#
# Его случай целиком: **железо закреплено на 15 при доле 5; земля выросла так,
# что доля стала 20 -- замок спадает, и железо идёт к 20.** А если новая доля
# всего 10, замок держится: добирать нечего, товар и так выше доли.
#
# **Сравнивается `_pq<n>`, а не `_eq<n>`.** `_pq<n>` только что написан
# `{MOD_ID}_plan_set_quota` и означает простую долю всей новой земли -- ту самую,
# «которая переросла». `_eq<n>` -- доля редактора, посчитанная **с вычетом
# закреплённых**: спрашивать у неё, переросла ли она закрепление, значит
# спрашивать число, из которого это закрепление вычтено.
#
# **И «не нужен» не снимается никогда.** Это не замок, а стоячее распоряжение:
# «один домик всегда, доля его не поднимает».
# Scope: country
{MOD_ID}_ext_lift = {{
\tset_global_variable = {{ name = {MOD_ID}_ext_lifted value = 0 }}
{lift}}}

# Квоты на одну доливку: свободным -- доля, замороженным -- то, что у них есть.
#
# `_frz<n>` -- ворота в `{MOD_ID}_plan_pick_<n>`, и они нужны отдельно от квоты:
# открытая лестница поднимает всякую квоту на единицу за круг, так что равенство
# `_pq = _pn` удержало бы товар ровно один круг.
# Scope: country
{MOD_ID}_ext_quotas = {{
{freeze}}}

# Заморозка снята. **Ничего от доливки не переживает саму доливку.**
# Scope: country
{MOD_ID}_ext_thaw = {{
{thaw}}}

# «Расширить» -- новая земля, долитая к плану, который уже стоит.
#
# Порядок здесь -- это и есть правило, и каждый шаг стоит там, где стоит:
#
# 1. земля собирается заново из выбора и делится на «уже в плане» и «новое»;
# 2. новое вносится в учёт плана -- комнаты, города, провинции;
# 3. **счёт идёт только по новому**, а три числа обо всей земле (`_ng`, `_nrgo`,
#    `_pbest`) наращиваются: флаг `_ext` снимает обнуление в обходе;
# 4. грамоты -- новым городам, потому что **город без грамоты нарушает
#    инвариант**, на котором держится вся их машина: «в каждом городе ровно
#    одна»;
# 5. доля считается по **всей** земле, и замок, который она переросла, спадает;
# 6. заливается **только новая земля**, и это единственное, что не даёт тронуть
#    старую: всё, что ставит здания, ходит по `_candidates`;
# 7. считается, что вышло, -- и **сколько домиков на старой земле сдвинулось.
#    Это число обязано быть нулём**, и оно на экране, а не в рассуждении.
#
# **Ничего не делает, пока плана нет.** Без него «новое» -- это вся земля, и
# кнопка молча превратилась бы в кривой план.
# Scope: country
{MOD_ID}_edit_extend = {{
\tsave_scope_as = {MOD_ID}_country
\tset_global_variable = {{ name = {MOD_ID}_ext_ran value = 1 }}
\tset_global_variable = {{ name = {MOD_ID}_ext_new value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_ext_rooms value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_ext_added value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_ext_moved value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_ext_lifted value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_ext_was value = 0 }}
\tif = {{
\t\tlimit = {{
\t\t\thas_global_variable = {MOD_ID}_plan_rooms
\t\t\tglobal_var:{MOD_ID}_plan_rooms > 0
\t\t}}
\t\tset_global_variable = {{ name = {MOD_ID}_ext_was value = global_var:{MOD_ID}_plan_rooms }}
\t\tset_global_variable = {{ name = {MOD_ID}_ext_placed0 value = global_var:{MOD_ID}_plan_placed }}
\t\t{MOD_ID}_collect_candidates = yes
\t\t{MOD_ID}_ext_split = yes
\t\tif = {{
\t\t\tlimit = {{ global_var:{MOD_ID}_ext_new > 0 }}
\t\t\t# **Снимок старой земли, снятый до того, как новая войдёт в список.**
\t\t\t# Новые локации `_ext_load0` не получают, поэтому обход в конце их и
\t\t\t# не считает: «сдвинулось» -- вопрос только про X.
\t\t\tevery_in_global_list = {{
\t\t\t\tvariable = {MOD_ID}_plan_touched
\t\t\t\tset_variable = {{ name = {MOD_ID}_ext_load0 value = var:{MOD_ID}_load }}
\t\t\t}}
\t\t\t{MOD_ID}_ext_prepare = yes
\t\t\t{MOD_ID}_ext_recount = yes
\t\t\tset_global_variable = {{ name = {MOD_ID}_ext_rooms value = global_var:{MOD_ID}_plan_rooms }}
\t\t\tchange_global_variable = {{ name = {MOD_ID}_ext_rooms subtract = global_var:{MOD_ID}_ext_was }}

\t\t\tset_global_variable = {{ name = {MOD_ID}_ext value = 1 }}
\t\t\t{MOD_ID}_ext_only = yes
\t\t\t# **`_plan_scored` пересчитывается, а не наращивается**: обход
\t\t\t# прибавляет единицу за товар, у которого `_ng<n> > 0`, а `_ng<n>` к
\t\t\t# этому моменту уже про всю землю. Наращивание сложило бы товар с
\t\t\t# самим собой и урезало долю вдвое.
\t\t\tset_global_variable = {{ name = {MOD_ID}_plan_scored value = 0 }}
\t\t\t{MOD_ID}_plan_score = yes
\t\t\tif = {{
\t\t\t\tlimit = {{ has_global_variable = {MOD_ID}_plan_rights }}
\t\t\t\t{MOD_ID}_plan_place_rights = yes
\t\t\t}}
\t\t\t# Доля -- по всей земле, поэтому список кандидатов на время её счёта
\t\t\t# снова полный.
\t\t\t{MOD_ID}_collect_candidates = yes
\t\t\t{MOD_ID}_plan_set_quota = yes
\t\t\t{MOD_ID}_ext_lift = yes
\t\t\t{MOD_ID}_edit_set_quota = yes
\t\t\t{MOD_ID}_ext_quotas = yes
\t\t\t{MOD_ID}_ext_only = yes
\t\t\t{MOD_ID}_plan_allocate = yes
\t\t\t{MOD_ID}_collect_candidates = yes
\t\t\tremove_global_variable = {MOD_ID}_ext
\t\t\t{MOD_ID}_ext_thaw = yes

\t\t\tset_global_variable = {{ name = {MOD_ID}_ext_added value = global_var:{MOD_ID}_plan_placed }}
\t\t\tchange_global_variable = {{ name = {MOD_ID}_ext_added subtract = global_var:{MOD_ID}_ext_placed0 }}
\t\t\t# **Проба, ради которой шаг и считается закрытым или нет.** Ноль
\t\t\t# значит «на старой земле не сдвинулось ничего»; всё, кроме нуля, --
\t\t\t# что доливка потрогала X, и тогда виновата не догадка, а это число.
\t\t\t# **Разность, а не сравнение двух переменных.** `var:x = var:y`
\t\t\t# внутри `limit` эффекта в этом моде нигде не доказано, а
\t\t\t# `change_variable = {{ subtract = var:y }}` и `var:x = 0` доказаны
\t\t\t# оба. Проба, которая молча читается ложью, хуже отсутствующей.
\t\t\tevery_in_global_list = {{
\t\t\t\tvariable = {MOD_ID}_plan_touched
\t\t\t\tlimit = {{ has_variable = {MOD_ID}_ext_load0 }}
\t\t\t\tset_variable = {{ name = {MOD_ID}_ext_dl value = var:{MOD_ID}_load }}
\t\t\t\tchange_variable = {{ name = {MOD_ID}_ext_dl subtract = var:{MOD_ID}_ext_load0 }}
\t\t\t\tif = {{
\t\t\t\t\tlimit = {{ NOT = {{ var:{MOD_ID}_ext_dl = 0 }} }}
\t\t\t\t\tchange_global_variable = {{ name = {MOD_ID}_ext_moved add = 1 }}
\t\t\t\t}}
\t\t\t\tremove_variable = {MOD_ID}_ext_dl
\t\t\t\tremove_variable = {MOD_ID}_ext_load0
\t\t\t}}
\t\t\t# Новая земля может уметь то, чего старая не умела: набор товаров в
\t\t\t# пикере считается из `_ng<n>` и должен быть пересобран.
\t\t\t{MOD_ID}_edit_fill_pool = yes
\t\t\t{MOD_ID}_plan_rank = yes
\t\t\t# **И строки окна заново.** Новые локации не лежат в `_plan_results`, и
\t\t\t# без этого доливка видна только после закрытия и повторного открытия
\t\t\t# редактора — его слова 2026-09-06: «в список не добавляется расширенная
\t\t\t# земля». Ровно та же строчка и по той же причине стоит в конце нажатия.
\t\t\t{MOD_ID}_plan_show = yes
\t\t}}
\t}}
}}

""")

    inits = "".join(
        f"\tif = {{\n"
        f"\t\tlimit = {{ NOT = {{ has_global_variable = {MOD_ID}_sl{n}_n }} }}\n"
        f"\t\tset_global_variable = {{ name = {MOD_ID}_sl{n}_n value = 0 }}\n"
        f"\t\tset_global_variable = {{ name = {MOD_ID}_sl{n}_locn value = 0 }}\n"
        f"\t}}\n"
        for n in range(1, EDIT_SLOTS + 1))
    out.append(f"""
# The slots' counters, created before anything can read one.
#
# **`_sl<n>_n` is what «загрузить» tests before it throws the plan away**, and a
# `limit` that reads a global which is not there fails silently -- so an
# uninitialised slot would either read as empty for ever or clear a good plan for
# nothing. Written with `has_global_variable` so a save from an older build gains
# the slots without losing the one plan it had.
# Scope: country
{MOD_ID}_edit_init_slots = {{
{inits}\t# `_edit_done` and `_edit_good` are read by `{MOD_ID}_edit_last_label` every
\t# frame the editor is open, and the pool is read by its datamodel. A list is created by
\t# clearing it, and it must be cleared only once ever: doing it on every open
\t# would throw away the goods he had picked.
\tif = {{
\t\tlimit = {{ NOT = {{ has_global_variable = {MOD_ID}_edit_done }} }}
\t\tset_global_variable = {{ name = {MOD_ID}_edit_done value = 0 }}
\t}}
\tif = {{
\t\tlimit = {{ NOT = {{ has_global_variable = {MOD_ID}_edit_reached }} }}
\t\tset_global_variable = {{ name = {MOD_ID}_edit_reached value = 0 }}
\t}}
\tif = {{
\t\tlimit = {{ NOT = {{ has_global_variable = {MOD_ID}_edit_pooln }} }}
\t\tset_global_variable = {{ name = {MOD_ID}_edit_pooln value = 0 }}
\t}}
\t# **Шесть чисел доливки, созданные до того, как строка их прочтёт.**
\t# `{MOD_ID}_edit_ext_label` разбирает ветки по `global_var:`, а глобалка,
\t# которой нет, читается как ложь молча -- то есть «не нажимали» никогда бы
\t# не выпало, и окно печатало бы нули как результат.
\tif = {{
\t\tlimit = {{ NOT = {{ has_global_variable = {MOD_ID}_ext_ran }} }}
\t\tset_global_variable = {{ name = {MOD_ID}_ext_ran value = 0 }}
\t\tset_global_variable = {{ name = {MOD_ID}_ext_new value = 0 }}
\t\tset_global_variable = {{ name = {MOD_ID}_ext_was value = 0 }}
\t\tset_global_variable = {{ name = {MOD_ID}_ext_rooms value = 0 }}
\t\tset_global_variable = {{ name = {MOD_ID}_ext_added value = 0 }}
\t\tset_global_variable = {{ name = {MOD_ID}_ext_moved value = 0 }}
\t\tset_global_variable = {{ name = {MOD_ID}_ext_lifted value = 0 }}
\t}}
\tif = {{
\t\tlimit = {{ NOT = {{ has_global_variable = {MOD_ID}_edit_op }} }}
\t\tset_global_variable = {{ name = {MOD_ID}_edit_op value = 0 }}
\t\tset_global_variable = {{ name = {MOD_ID}_edit_fitn value = 0 }}
\t\tset_global_variable = {{ name = {MOD_ID}_edit_cands value = 0 }}
\t}}
\tif = {{
\t\tlimit = {{ NOT = {{ has_global_variable = {MOD_ID}_edit_presses }} }}
\t\tset_global_variable = {{ name = {MOD_ID}_edit_presses value = 0 }}
\t\tset_global_variable = {{ name = {MOD_ID}_edit_idle value = 0 }}
\t\t# **Свёрнутый вид — то, с чего оба окна открываются**, его слова
\t\t# 2026-09-06. Ставится один раз рядом с остальными умолчаниями, а
\t\t# не на каждом открытии: снятую галочку надо помнить.
\t\tset_variable = {{ name = {MOD_ID}_plan_folded value = 1 }}
\t\tset_global_variable = {{ name = {MOD_ID}_edit_right value = 0 }}
\t\tset_global_variable = {{ name = {MOD_ID}_edit_rfrom value = 0 }}
\t\tset_global_variable = {{ name = {MOD_ID}_edit_rto value = 0 }}
\t\t{MOD_ID}_edit_clear_trace = yes
\t}}
\tif = {{
\t\tlimit = {{ NOT = {{ has_global_variable = {MOD_ID}_edit_fail }} }}
\t\tset_global_variable = {{ name = {MOD_ID}_edit_fail value = 0 }}
\t\tset_global_variable = {{ name = {MOD_ID}_edit_norefill value = 0 }}
\t\tset_global_variable = {{ name = {MOD_ID}_edit_evicted value = 0 }}
\t\tset_global_variable = {{ name = {MOD_ID}_edit_mark value = 0 }}
\t}}
\tif = {{
\t\tlimit = {{ NOT = {{ has_global_variable_list = {MOD_ID}_edit_pool }} }}
\t\tclear_global_variable_list = {MOD_ID}_edit_pool
{row_inits}\t}}
\tif = {{
\t\tlimit = {{ NOT = {{ has_global_variable_list = {MOD_ID}_chg_locs }} }}
\t\tclear_global_variable_list = {MOD_ID}_chg_locs
\t}}
}}

# The editor's window. **The plan on the map is what it edits**, so opening it
# neither plans nor loads: it fills the picker from the ground the last plan
# scored and shows whatever the plan holds now.
# Scope: country
{MOD_ID}_open_edit_window_effect = {{
\t# **The probe that lived here is gone and `check_script.py` holds its answer.**
\t# It logged one line a press, to separate "the button never reached the effect"
\t# from "the effect ran and the window did not draw". The log said the effect
\t# ran, the `.gui` had no error of any kind, and the window still did not exist:
\t# nothing had registered it in `gui/scripted_widgets/`, and the engine creates
\t# only what is registered there. That is a rule a checker can enforce, so it
\t# does, and a line in `error.log` on every press is noise once the answer is in.
\t# **Земля редактора — своя, и она сбрасывается на землю плана.** Его слова
\t# 2026-09-06: «я хочу, чтобы эти две карты были независимыми друг от друга»
\t# — расширение увеличивало выбор и в окне плана, а выбор в окне плана менял
\t# то, что доливал редактор. Выбор плана откладывается целиком и возвращается
\t# при выходе; редактор начинает с того, на чём план стоит сейчас.
\t{MOD_ID}_sel_keep_plan = yes
\t{MOD_ID}_sel_load_plan_ground = yes
\t{MOD_ID}_edit_init_slots = yes
\t# **The last-press line starts blank, and the press counter starts at zero.**
\t# Both are globals and both survive a save, so a «сделано» from an hour ago
\t# used to greet him on opening the window -- and it masked the branch that
\t# would have said the press never arrived. A window that opens is a window
\t# that has taken no presses yet, and it must say so.
\tset_global_variable = {{ name = {MOD_ID}_edit_presses value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_edit_idle value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_edit_op value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_edit_done value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_edit_fail value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_edit_norefill value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_edit_reached value = 1 }}
\t# **И строка доливки тоже начинает пустой**, по той же причине, что строка
\t# последнего нажатия: «расширение: локаций +48» от прошлого часа встречает
\t# открытое окно как отчёт о том, чего в нём ещё не делали.
\tset_global_variable = {{ name = {MOD_ID}_ext_ran value = 0 }}
\t{MOD_ID}_edit_fill_pool = yes
\t{MOD_ID}_edit_clear_fillset = yes
\t{MOD_ID}_plan_show = yes
\tremove_variable = {MOD_ID}_result_open
\tremove_variable = {MOD_ID}_right_open
\tremove_variable = {MOD_ID}_plan_open
\t{MOD_ID}_hide_results = yes
\tset_variable = {{ name = {MOD_ID}_edit_open value = 1 }}
}}

# Scope: country
{MOD_ID}_close_edit_window_effect = {{
\t# Выбор плана возвращается целиком; земля, набранная в редакторе, уходит с
\t# окном. Возврат идёт и отсюда, и из открытия окна плана или поиска: путей
\t# наружу больше одного, а вернуть надо по любому.
\t{MOD_ID}_sel_restore_plan = yes
\tremove_variable = {MOD_ID}_edit_open
\tremove_variable = {MOD_ID}_chg_open
\t{MOD_ID}_plan_hide = yes
\tclear_global_variable_list = {MOD_ID}_chg_locs
}}

# «Показать изменения», and the window it opens. **The list is built here and
# not by the window**, because a datamodel cannot ask two variable lists to
# differ -- the effect does the comparing and leaves the answer on the locations.
# Scope: country
{MOD_ID}_open_changes_window_effect = {{
\t{MOD_ID}_edit_changes = yes
\tset_variable = {{ name = {MOD_ID}_chg_open value = 1 }}
}}

# Scope: country
{MOD_ID}_close_changes_window_effect = {{
\tremove_variable = {MOD_ID}_chg_open
\tclear_global_variable_list = {MOD_ID}_chg_locs
}}
""")

    return "".join(out), "".join(gate)



# Сколько домиков окно замены предлагает разом.
#
# **Двадцать четыре были потолком, а не ответом.** Его прогон 2026-09-14: «мод
# показывает, что можно поставить 24 вида здания… на самом деле их гораздо
# больше должно отображаться». Ровно 24 в каждой локации -- признак упора в
# потолок, а не совпадение. Круг стоит один проход по зданиям на строку, список
# в скроллбоксе, читать все и не нужно -- нужно, чтобы список кончался там же,
# где кончаются кандидаты.
SWAP_MAX = 80
SWAP_OUT = MOD / "in_game/common/scripted_effects/bag_wtp_generated_swap.txt"
# **Значение живёт только в `script_values`**, ровно как триггер только в
# `scripted_triggers`: выгода здания сначала уехала в файл эффектов вместе с
# остальным окном замены. Ловит `check_script.py`.
SWAP_VALUES_OUT = MOD / "in_game/common/script_values/bag_wtp_generated_swap_values.txt"


COV_OUT = MOD / "in_game/common/scripted_effects/bag_wtp_generated_cov.txt"


def cov_file(rows: list[eu5data.Method], split: dict[str, list[str]],
             game: eu5data.Game) -> str:
    """Покрытие товара сырьём провинции -- **логика карты, наши условия**.

    Его слово, 2026-09-14: «То как работает карта для нас важно, но не
    константа. У нас гораздо больше настроек и условий. Нам нужно логику карты
    перенести и адаптировать к тем условиям, в которых наш мод работает.
    Доступные списки зданий, методов, эпох, уровней. Саму карту трогать не
    надо.»

    Формула его: доля входа рецепта, которую провинция даёт своим РГО; лучший
    вариант среди способов; плюс своё сырьё локации как полное покрытие; плюс
    местный модификатор вывода в единицах `_trmm_rgo_unit`.

    Разница одна и она вся в отборе способов: **CM берёт лучший вариант
    безусловно** (`_trmm_opt_*` -- ни одних ворот по продвижению), а мы берём
    лучший **из доступных**: `_avail_` в режиме «на сейчас», `_reach_` в режиме
    «на конец», и оба уже несут в себе галочку чужого мода. Поэтому наше число
    слушается тумблера эпохи, а число карты -- нет, и сравнивать их в лоб можно
    только «на конец».

    Считается эффектом, а не значением: доля требует
    `any_location_in_province_definition`, то есть триггера, а триггер в
    значении живёт только под `if = {{ limit = ... }}` в эффекте.
    """
    wanted: set[str] = set()
    for right in output_rights(rows, game):
        wanted |= set(right.output)
    by_good: dict[str, list[int]] = {}
    for index, method in enumerate(rows, start=1):
        if method.produced in wanted and method.inputs:
            by_good.setdefault(method.produced, []).append(index)

    out = [HEADER, """#
# Покрытие товара сырьём провинции, по логике карты и нашим воротам.
#
# **Проход пишет не только число, но и его разбор**, потому что число без
# разбора он читать отказался: «я вижу текст "текстиль 100%%" а с чего бы он
# 100%%? Я этого не вижу. Должно быть указано что он там например использует
# предполагаемо шерсть 1/1» (2026-09-14). На товар остаётся пять переменных:
#
# * `_cov_<товар>`  -- само покрытие, как его читает `_rq<k>`;
# * `_covm_<товар>` -- номер победившего способа, по нему подсказка называет
#                      здание и перечисляет сырьё, которое рецепт просит;
# * `_covn_`/`_covd_` -- сколько видов сырья рецепта провинция даёт из скольких.
#
# **Эпоху проход берёт у того, кто его позвал, а не у одной глобалки на всех.**
# Он гейтился на `_plan_by_end` -- тумблере окна плана, -- а звал его и поиск по
# грамоте, у которого свой тумблер (`_rank_by_end`). Значит галочка «Считать на
# конец игры» в поиске не делала для «Пригодности» ничего: столбец всегда считал
# по тумблеру другого окна. Его слово 2026-09-14: «ебучий мод опять не различает
# что он советует на "сейчас" и на "конец"… я уже раз 50 на этой теме правки
# вношу за тобой». Теперь возраст приносит вызывающий -- `%s_cov_end`, -- и
# ставит его из **своего** тумблера.
# Scope: location, ждёт scope:%s_country и %s_cov_age
%s_cov_pass = {
""" % (MOD_ID, MOD_ID, MOD_ID, MOD_ID)]
    for good in sorted(by_good):
        out.append(f"\tset_variable = {{ name = {MOD_ID}_cov_{good} value = 0 }}\n"
                   f"\tset_variable = {{ name = {MOD_ID}_covm_{good} value = 0 }}\n"
                   f"\tset_variable = {{ name = {MOD_ID}_covn_{good} value = 0 }}\n"
                   f"\tset_variable = {{ name = {MOD_ID}_covd_{good} value = 0 }}\n")
        # **Способы сгруппированы по зданию, и вопрос о локации задан один раз
        # на здание.** `_stands_<здание>` спрашивает `can_build_building`, то
        # есть читает состояние игры; 530 таких вопросов на локацию, а зданий
        # под ними сотня с небольшим.
        #
        # **Внутри здания -- по убыванию выхлопа**, потому что сравнение долей
        # строгое и при равенстве побеждает первый: пусть это будет верхняя
        # ступень лестницы, а не первая попавшаяся.
        by_building: dict[str, list[int]] = {}
        for mi in by_good[good]:
            by_building.setdefault(rows[mi - 1].building, []).append(mi)
        for building in sorted(by_building):
            arms = ""
            for mi in sorted(by_building[building],
                             key=lambda m: (-rows[m - 1].output, m)):
                method = rows[mi - 1]
                total = sum(method.inputs.values())
                if total <= 0:
                    continue
                raws = [r for r in sorted(method.inputs) if r in game.raw_goods]
                # **`province_definition = {{ }}` -- не украшение, и его
                # отсутствие стоило всей «Пригодности».**
                # `any_location_in_province_definition` живёт **только** в
                # скоупе определения провинции (`api.py`), а этот эффект --
                # локационный: без перехода триггер не проходил ни разу, все
                # `_cov_<товар>` оставались нулями, `_rq<k>` вместе с ними, и
                # столбец печатал 0 % в каждой строке.
                adds = "".join(
                    f"\t\t\tif = {{\n"
                    f"\t\t\t\tlimit = {{ province_definition = {{ "
                    f"any_location_in_province_definition = "
                    f"{{ raw_material ?= goods:{raw} }} }} }}\n"
                    f"\t\t\t\tchange_variable = {{ name = {MOD_ID}_cov_try add = "
                    f"{round(method.inputs[raw] / total, 3)} }}\n"
                    f"\t\t\t\tchange_variable = {{ name = {MOD_ID}_covn_try add = 1 }}\n"
                    f"\t\t\t}}\n"
                    for raw in raws)
                if not adds:
                    continue
                # **«На конец» -- это «когда-нибудь», а не «сейчас».**
                # `_reach_<n>` выписан только у методов за недостижимым
                # продвижением; у остальных 228 из 241 ответ «достижим» по
                # построению, и подставлять им `_avail_` значило считать конец
                # игры сегодняшним днём. Оттого лесенка прав не менялась от
                # галочки вовсе: «права в расчёте всегда показываются одни и те
                # же», 2026-09-14.
                gate = (f"{MOD_ID}_reach_{mi} = yes" if method_gates(method)
                        else "always = yes")
                # **В конце игры здания, которое сменяет наследник, уже нет.**
                # Подсказка «на конец» предлагала скрипторий -- здание первой
                # эпохи, которое лестница давно заменила. Это статический факт
                # игры (`obsolete` у наследника), и ветка просто не открывается.
                if method.building in game.obsoleted:
                    gate = "always = no"
                arms += f"""\t\t# {method.key}
\t\tif = {{
\t\t\tlimit = {{
\t\t\t\tOR = {{
\t\t\t\t\tAND = {{
\t\t\t\t\t\tNOT = {{ has_global_variable = {MOD_ID}_cov_end }}
\t\t\t\t\t\tscope:{MOD_ID}_country = {{ {MOD_ID}_avail_{mi} = yes }}
\t\t\t\t\t}}
\t\t\t\t\tAND = {{
\t\t\t\t\t\thas_global_variable = {MOD_ID}_cov_end
\t\t\t\t\t\tscope:{MOD_ID}_country = {{ {gate} }}
\t\t\t\t\t}}
\t\t\t\t}}
\t\t\t}}
\t\t\tset_variable = {{ name = {MOD_ID}_cov_try value = 0 }}
\t\t\tset_variable = {{ name = {MOD_ID}_covn_try value = 0 }}
{adds}\t\t\tif = {{
\t\t\t\tlimit = {{ var:{MOD_ID}_cov_try > var:{MOD_ID}_cov_{good} }}
\t\t\t\tset_variable = {{ name = {MOD_ID}_cov_{good} value = var:{MOD_ID}_cov_try }}
\t\t\t\t# Кто победил и чем -- это и есть разбор, который печатает подсказка.
\t\t\t\tset_variable = {{ name = {MOD_ID}_covm_{good} value = {mi} }}
\t\t\t\tset_variable = {{ name = {MOD_ID}_covn_{good} value = var:{MOD_ID}_covn_try }}
\t\t\t\tset_variable = {{ name = {MOD_ID}_covd_{good} value = {len(raws)} }}
\t\t\t}}
\t\t}}
"""
            if not arms:
                continue
            out.append(f"""\t# {building}
\t#
\t# **Локация обязана держать это здание, и без этой строки счёт был бредом.**
\t# Покрытие спрашивало только державу, поэтому лучшим способом города
\t# оказывался «Сельский стекольщик», а в Вестфалии -- японский «Сёэн» (его
\t# прогон 2026-09-14). `_stands_<здание>` -- ровно тот вопрос: ранг локации,
\t# её `location_potential` и тумблер город/село.
\tif = {{
\t\tlimit = {{ {MOD_ID}_stands_{building} = yes }}
{arms}\t}}
""")
        # **Своё сырьё усредняется только у `dyes` и `wine`, и это не выбор.**
        # У него ровно два таких товара (`_trmm_cov_dyes`, `_trmm_cov_wine`), и
        # причина написана там же: модификатор вывода грамоты поднимает и
        # собственное РГО этого сырья, поэтому на его локации оно входит ещё
        # одним полностью покрытым поставщиком. У остальных восемнадцати товаров
        # такого нет.
        own_rgo = ""
        if good in TRMM_RGO_AVERAGED:
            own_rgo = f"""\tif = {{
\t\tlimit = {{ raw_material ?= goods:{good} }}
\t\tchange_variable = {{ name = {MOD_ID}_cov_{good} add = 1 }}
\t\tset_variable = {{ name = {MOD_ID}_cov_{good} value = {{
\t\t\tvalue = var:{MOD_ID}_cov_{good}
\t\t\tdivide = 2
\t\t}} }}
\t}}
"""
        # **Местного модификатора вывода в счёте нет, и это его решение.**
        # 2026-09-14: «наш мод интересует только то, что даёт провинция по РГО
        # бонусу, а тот модификатор какой-то костыль для той карты, он нам не
        # нужен». У CM он есть (`_trmm_lm_<товар>`, последним слагаемым в
        # `_trmm_cov_<товар>`), и там же из него вычитается уже выданная
        # грамота; у нас его нет вовсе.
        out.append(own_rgo)
    out.append("}\n")
    # **Возраст ставит окно, и обе формы стоят рядом**, чтобы разойтись они
    # могли только вместе. Планом правит `_plan_by_end` (галочка окна плана),
    # поиском по грамоте -- `_rank_by_end` (галочка окна поиска), и это разные
    # тумблеры: одно окно ищет место под одну грамоту, другое раздаёт весь план.
    for name, switch in (("plan", "plan_by_end"), ("rank", "rank_by_end")):
        out.append(f"""
# Возраст для `_cov_pass`, из тумблера окна «{name}».
# Scope: country
{MOD_ID}_cov_age_{name} = {{
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_{switch} }}
\t\tset_global_variable = {{ name = {MOD_ID}_cov_end value = 1 }}
\t}}
\telse = {{ remove_global_variable = {MOD_ID}_cov_end }}
}}
""")
    # **Лесенка прав на локации -- один эффект на оба окна.** Она нужна и
    # поиску по грамоте, и подсказке строки плана, а считаться обязана одинаково:
    # два экземпляра одного расчёта -- ровно то, из-за чего подсказка и столбец
    # разошлись в первый раз.
    rights = output_rights(rows, game)
    # **В лесенке только то, что этой державе и правда светит.** Его прогон
    # 2026-09-14: «там появились права Константинополя, которых быть не должно.
    # А вот фламандское должно, ибо я играю за нидерландскую культуру. Права у
    # которых бонус в провинции 0% вообще не должны показываться». Оба вопроса
    # закрывает `_plan_right_gate_<k>` -- тот самый триггер, которым раздача
    # решает, кому какая грамота доступна (`has_or_had_tag = BYZ` у
    # константинопольской, культурная группа у фламандской), -- и ноль.
    park = "".join(
        "\tset_variable = { name = %s_rqv%d value = { value = %s_rq%d divide = %d } }\n"
        "\tif = {\n"
        "\t\tlimit = {\n"
        # Порог, а не ноль: `|%1` округляет до десятой, и всё, что печатается
        # «0.0 %», в лесенке -- мусор («фламандское суконное 0.0%» на его
        # экране 2026-09-14).
        "\t\t\tvar:%s_rqv%d > 0.0005\n"
        "\t\t\tscope:%s_country = { %s_plan_right_gate_%d = yes }\n"
        "\t\t}\n"
        "\t\tset_variable = { name = %s_rqok%d value = 1 }\n"
        "\t}\n"
        "\telse = { remove_variable = %s_rqok%d }\n"
        % (MOD_ID, j, MOD_ID, j, RANK_SCALE,
           MOD_ID, j, MOD_ID, MOD_ID, j, MOD_ID, j, MOD_ID, j)
        for j in range(1, len(rights) + 1))
    ranks = ""
    for k in range(1, len(rights) + 1):
        body = "\t\tset_variable = { name = %s_rqr%d value = 0 }\n" % (MOD_ID, k)
        for j in range(1, len(rights) + 1):
            if j == k:
                continue
            # Ничья ломается номером: нестрогое сравнение оставило бы две
            # грамоты на одном месте, и вторая не нарисовалась бы вовсе.
            op = ">=" if j < k else ">"
            body += ("\t\tif = { limit = { has_variable = %s_rqok%d"
                     " var:%s_rqv%d %s var:%s_rqv%d }"
                     " change_variable = { name = %s_rqr%d add = 1 } }\n"
                     % (MOD_ID, j, MOD_ID, j, op, MOD_ID, k, MOD_ID, k))
        # **Место считается только среди показанных**, иначе выброшенные права
        # оставляли бы в лесенке дыры: место есть, а рисовать в нём нечего.
        ranks += ("\tif = {\n\t\tlimit = { has_variable = %s_rqok%d }\n%s\t}\n"
                  "\telse = { remove_variable = %s_rqr%d }\n"
                  % (MOD_ID, k, body, MOD_ID, k))
    out.append(f"""
# Наш счёт каждой грамоты на этой локации, долей.
# Scope: location, после `_cov_pass`
{MOD_ID}_rq_park = {{
{park}}}

# Место каждой грамоты в лесенке -- по тому, что лежит в `_rqv<k>`.
#
# **Отдельно от укладки, потому что укладок две.** Обычно `_rqv<k>` -- счёт этой
# локации; в режиме специализации раздача кладёт туда среднее по городам
# провинции -- то самое число, которым она грамоту и выбрала, -- и лесенка в
# подсказке обязана быть той же, иначе она снова объясняет не то, что стоит
# рядом (его прогон 2026-09-14: «текстиль показывается как самая подходящая, мод
# всё равно поставил суд. материалы»).
# Scope: location, ждёт scope:{MOD_ID}_country
{MOD_ID}_rq_rank = {{
{ranks}}}
""")
    return "".join(out)


def swap_values_file(rows: list[eu5data.Method], split: dict[str, list[str]],
                     game: eu5data.Game) -> str:
    """Что провинция платит каждому зданию здесь -- по значению на здание.

    **Здание, а не товар.** Список окна замены сортируется по зданиям, и здание,
    делающее два товара, стоит столько, сколько лучший из них. Раньше список
    мерил выгоду ТОВАРА и потому ставил рядом четыре ступени одной лестницы как
    четыре разных ответа.

    **`min` -- это пол, и несколько полов дают максимум.** `value = 0` и по
    `min = var:<выгода>` на каждый товар здания -- это max(0, a, b, ...) одной
    формой, без накопителя и без сравнения значения с самим собой.
    """
    order = goods_order(split)
    groups = plan_groups(rows, split, game)
    villages = village_entities(rows, split, game)
    by_building: dict[str, list[tuple[int, str]]] = {}
    for (good, side), buildings in groups.items():
        for building, _mis in buildings.items():
            if side == "r" and building in villages:
                continue
            by_building.setdefault(building, []).append((order.index(good) + 1, side))
    out = [HEADER, "#\n# Выгода локации от одного здания: лучший из его товаров.\n"]
    for building in sorted(b for b in by_building if b not in villages):
        floors = "".join(
            "\tmin = var:%s_%s%d\n" % (MOD_ID, "p" if side == "t" else "pr", index)
            for index, side in sorted(by_building[building]))
        out.append(f"""
# Scope: location
{MOD_ID}_swap_gain_{building} = {{
\tvalue = 0
{floors}}}
""")
    return "".join(out)


def swap_file(rows: list[eu5data.Method], split: dict[str, list[str]],
              game: eu5data.Game) -> str:
    """Окно замены: что стоит в одной локации и что туда можно поставить.

    **Его шестой пункт, 2026-09-13.** «В каждой локации в окне редактора должна
    быть добавлена кнопочка замены. Жму кнопку и открывается окно конкретной
    локации. В нём показаны те домики, которые там стоят. Я могу нажать удалить
    на любой из них. На другой части окна мне показывается список домиков,
    которые я могу туда поставить. Они должны быть сортированы по бонусу от
    РГО… кнопку "отсеять", которая уберёт из списка все домики, которые вообще
    никакого бонуса от РГО провинции не получат.»

    **Списки -- здания, а не товары, и это решает половину задачи.** Строка
    датамодели, которой дан тип здания, рисует его значок и имя сама; товар
    пришлось бы переводить в здание картой переменных на локации, то есть
    формой, которой в этом моде ещё нет. Слева -- `_row_builds`, тот самый
    список, которым рисуется строка плана; справа -- `_swap_can`, собранный
    здесь по убыванию выгоды.

    **Ни одного нового правила постановки и снятия.** «×» и «+» зовут
    `_edit_remove_*` и `_edit_place_*` -- те же эффекты, которыми работают «−1»
    и «+1», со всеми их воротами и счётчиками. Здание умеет несколько товаров,
    поэтому зовутся они по всем его товарам разом: ворота сами решат, о котором
    из них шла речь. **Поэтому окно не может рассинхронизировать план**: оно не
    знает о нём ничего, кроме имён этих эффектов.

    **Житницы сюда не ходят.** Их заполняет свой круг, их места в раздаче не
    участвуют, и «удалить домик житницы» значило бы держать ещё один обратный
    ход к кругу, который и так весь обратим одним нажатием пометки. Кнопка на
    такой строке не показывается вовсе.
    """
    order = goods_order(split)
    groups = plan_groups(rows, split, game)
    villages = village_entities(rows, split, game)
    by_method = {i: m for i, m in enumerate(rows, start=1)}
    shared = shared_buildings(rows, split, game)

    # Здание -> [(номер товара, сторона, [номера методов])], в устойчивом порядке.
    #
    # **Деревня из товарной половины выброшена тем же правилом, что и в
    # редакторе.** `_edit_remove_rural_<n>` у товара, который в селе делает
    # только деревня, не существует вовсе -- редактор его не пишет, -- и вызов
    # несуществующего эффекта здесь ловит `check_script.py`. Деревни снимаются
    # своим `_plan_drop_village_<k>` ниже.
    by_building: dict[str, list[tuple[int, str, list[int]]]] = {}
    for (good, side), buildings in groups.items():
        for building, mis in buildings.items():
            if side == "r" and building in villages:
                continue
            by_building.setdefault(building, []).append(
                (order.index(good) + 1, side, sorted(mis)))
    for building in by_building:
        by_building[building].sort()

    out = [HEADER, f"""#
# Окно замены: одна локация, два списка зданий и две кнопки на каждое.
"""]

    # ---- круг выбора лучшего из ещё не предложенных ------------------------
    #
    # **Кандидат -- здание, и ворота у него свои.** Прежде здесь стояло
    # `_edit_fits_<сторона>_<товар>`, то есть ворота ТОВАРА: «этот товар тут
    # производится». Здание предлагалось, даже если держава его построить не
    # может -- и он это увидел, 2026-09-14: «список домиков справа не полный и
    # вообще не соответствует доступности стране… может показываться 4 вида
    # одного здания просто разного уровня… даже при выключенной галочке справа
    # всё так же отображаются все здания из ND».
    #
    # Теперь ворота спрашивают само здание:
    #
    # * `_stands_<здание>` -- локация его держит (и слушается тумблера ранга);
    # * хотя бы один его способ проходит `_avail_` («на сейчас») или `_reach_`
    #   («на конец») -- **по тому же тумблеру, каким посчитан план**; галочка
    #   мода живёт внутри `_avail_`/`_reach_`, поэтому снятая галочка убирает
    #   здания мода и отсюда тоже;
    # * ступень лестницы отсекается тем же `can_build_building` внутри
    #   `_avail_`: недоступный уровень здания ворота не пройдёт;
    # * его здесь ещё нет (`_plan_builds`) -- иначе одно здание стояло бы в обоих
    #   списках окна сразу;
    # * и **сработает хотя бы одна ветка «+»** (`placeable` ниже): сторона
    #   локации, место своей стороны, свободный товар. Без этого список
    #   предлагал сельское здание в городе, а нажатие молча не делало ничего.
    arms = ""
    for building in sorted(b for b in by_building if b not in villages):
        entries = by_building[building]
        mis = sorted({m for _i, _s, ms in entries for m in ms})
        # **Предлагается только то, что «+» и правда поставит.** Его слово
        # 2026-09-14: «не предлагались те, которые построить нельзя в связи
        # например с тем, что это деревня, а ставим мы в локацию города».
        # Ворота списка не спрашивали сторону вовсе, поэтому сельское здание
        # стояло в списке городской локации, а нажатие на нём молча не делало
        # ничего: у `_swap_put_effect` сторона в каждой ветке есть.
        #
        # Поэтому условие здесь -- буква в букву ворота той же постановки:
        # **существует ветка «+», которая сработает**. Одна ветка -- одна запись
        # (товар, сторона): сторона совпадает, место своей стороны не кончилось,
        # и этот товар здесь ещё не делают. Ни одной такой ветки -- строки нет.
        placeable = " ".join(
            "AND = { %s_plan_is_town = %s var:%s_load < global_var:%s_plan_cap_%s"
            " NOT = { is_target_in_variable_list = { name = %s_plan_goods"
            " target = goods:%s } } }"
            % (MOD_ID, "yes" if side == "t" else "no", MOD_ID, MOD_ID,
               "urban" if side == "t" else "rural", MOD_ID, order[index - 1])
            for index, side, _ms in entries)
        # Выгода здания -- лучшая из выгод его товаров здесь.
        best = f"{MOD_ID}_swap_gain_{building}"
        avail = " ".join(f"{MOD_ID}_avail_{m} = yes" for m in mis)
        # **`_reach_<n>` существует только у методов за недостижимым
        # продвижением** -- остальные достижимы по построению и не выписаны
        # вовсе (`triggers_file`). Спросить несуществующий -- это блок, который
        # молча проходит или молча не делает ничего; поймал `check_script.py`
        # ещё до сборки. Где `_reach_` нет, метод достижим по построению, и
        # ответ «да»: подставлять `_avail_` значило бы считать конец игры
        # сегодняшним днём, и «на конец» ничем не отличалось бы от «на сейчас».
        reach = " ".join(
            f"{MOD_ID}_reach_{m} = yes" if method_gates(rows[m - 1])
            else "always = yes" for m in mis)
        arms += f"""\tif = {{
\t\tlimit = {{
\t\t\tNOT = {{ is_target_in_variable_list = {{ name = {MOD_ID}_swap_can target = building_type:{building} }} }}
\t\t\t# Стоящее здесь -- в левом списке, и в правом ему места нет.
\t\t\tNOT = {{ is_target_in_variable_list = {{ name = {MOD_ID}_plan_builds target = building_type:{building} }} }}
\t\t\t{MOD_ID}_is_granary = no
\t\t\t{MOD_ID}_stands_{building} = yes
\t\t\t# Сторона, место и свободный товар -- ворота самой постановки.
\t\t\tOR = {{ {placeable} }}
\t\t\t# **Ступень лестницы -- только верхняя из открытых.** Его прогон
\t\t\t# 2026-09-14: «мне не надо, чтобы мод предлагал мне на выбор 1 или 2
\t\t\t# уровень здания, должен быть самый высокий из доступных». Игра сама
\t\t\t# знает, какая ступень устарела для этой державы --
\t\t\t# `building_type_is_obsolete`, страновой триггер по типу здания;
\t\t\t# CM спрашивает его той же формой.
\t\t\tscope:{MOD_ID}_country = {{
\t\t\t\tNOT = {{ building_type_is_obsolete = building_type:{building} }}
\t\t\t}}
\t\t\tOR = {{
\t\t\t\tAND = {{
\t\t\t\t\tNOT = {{ has_global_variable = {MOD_ID}_plan_by_end }}
\t\t\t\t\tscope:{MOD_ID}_country = {{ OR = {{ {avail} }} }}
\t\t\t\t}}
\t\t\t\tAND = {{
\t\t\t\t\thas_global_variable = {MOD_ID}_plan_by_end
\t\t\t\t\tscope:{MOD_ID}_country = {{ OR = {{ {reach} }} }}
\t\t\t\t}}
\t\t\t}}
\t\t\t# «Отсеять»: убрать всё, чему провинция не платит ничего.
\t\t\tOR = {{
\t\t\t\tNOT = {{ has_global_variable = {MOD_ID}_swap_sift }}
\t\t\t\t{best} > 0
\t\t\t}}
\t\t\t{best} > global_var:{MOD_ID}_swap_bv
\t\t}}
\t\tset_global_variable = {{ name = {MOD_ID}_swap_bv value = {best} }}
\t\tset_global_variable = {{ name = {MOD_ID}_swap_bb value = building_type:{building} }}
\t}}
"""
    out.append(f"""
# Один круг: лучший из тех, кого здесь ещё не предложили.
#
# **`-1` как начальное лучшее, а не ноль.** Домик, которому провинция не платит
# ничего, -- законный кандидат: без «Отсеять» он обязан быть в списке, и
# сравнение с нулём не пустило бы его туда никогда.
# Scope: location, ждёт scope:{MOD_ID}_country
{MOD_ID}_swap_pass = {{
\tset_global_variable = {{ name = {MOD_ID}_swap_bv value = -1 }}
\tremove_global_variable = {MOD_ID}_swap_bb
{arms}\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tadd_to_variable_list = {{ name = {MOD_ID}_swap_can target = global_var:{MOD_ID}_swap_bb }}
\t}}
}}

# Список заново: {SWAP_MAX} кругов или пока не кончатся кандидаты.
#
# **Локация берётся из глобалки, а не из скоупа.** Кнопки внутри окна живут в
# типе строки датамодели: скоуп там -- здание, а локацию пришлось бы тащить
# через `GetGlobalVariable(...).GetLocation.MakeScope`, и ровно эта цепочка
# 2026-09-13 вернула пустые списки при непустой локации. `global_var:X = {{ }}`
# как переход в скоуп -- форма самой игры (`character_death_pulses.txt`).
# Scope: country
{MOD_ID}_swap_rebuild = {{
\t# Ворота кандидата спрашивают доступность у державы, а стоят в скоупе
\t# локации -- значит державу надо туда занести.
\tsave_scope_as = {MOD_ID}_country
\tglobal_var:{MOD_ID}_swap_loc = {{ clear_variable_list = {MOD_ID}_swap_can }}
\tclear_global_variable_list = {MOD_ID}_swap_slots
\tclear_global_variable_list = {MOD_ID}_swap_here

\t# **Строка -- пронумерованное место, а не безымянный элемент датамодели**,
\t# потому что ей нужен ещё и процент выгоды. Достать число «по зданию из
\t# строки» этому дереву нечем: `BuildingType.GetKey` в дампах нет, переменную
\t# на типе здания не держит никто, `type = building_type` у кастомной
\t# локализации не встречается, а переход в скоуп через `global_var:X = {{ }}`
\t# **внутри значения** не доказан нигде. Доказан способ CMF: датамодель идёт
\t# по флагам, а строка собирает имя переменной через `Concatenate`
\t# (`cmm_list_setting.gui`).
\t#
\t# Раскатан не поиск, а **укладка**: круг определён один раз, здесь на место
\t# приходится вызов и три строки. Восемьдесят мест -- 400 строк, а не 56 000.
\t#
\t# Числа лежат на державе, не на локации: `CMMHomeScope.GetVariable(...)` --
\t# ровно та форма, которой читает себя список модов, а
\t# `GetGlobalVariable(...).GetLocation.MakeScope.Get...` в этом окне уже
\t# однажды вернула пустоту.
\tglobal_var:{MOD_ID}_swap_loc = {{ {MOD_ID}_swap_pass = yes }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot1_bt value = global_var:{MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot1_gain value = {{ value = global_var:{MOD_ID}_swap_bv divide = {RANK_SCALE} }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_slots target = flag:{MOD_ID}_swapslot1 }}
\t}}
\tglobal_var:{MOD_ID}_swap_loc = {{ {MOD_ID}_swap_pass = yes }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot2_bt value = global_var:{MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot2_gain value = {{ value = global_var:{MOD_ID}_swap_bv divide = {RANK_SCALE} }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_slots target = flag:{MOD_ID}_swapslot2 }}
\t}}
\tglobal_var:{MOD_ID}_swap_loc = {{ {MOD_ID}_swap_pass = yes }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot3_bt value = global_var:{MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot3_gain value = {{ value = global_var:{MOD_ID}_swap_bv divide = {RANK_SCALE} }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_slots target = flag:{MOD_ID}_swapslot3 }}
\t}}
\tglobal_var:{MOD_ID}_swap_loc = {{ {MOD_ID}_swap_pass = yes }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot4_bt value = global_var:{MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot4_gain value = {{ value = global_var:{MOD_ID}_swap_bv divide = {RANK_SCALE} }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_slots target = flag:{MOD_ID}_swapslot4 }}
\t}}
\tglobal_var:{MOD_ID}_swap_loc = {{ {MOD_ID}_swap_pass = yes }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot5_bt value = global_var:{MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot5_gain value = {{ value = global_var:{MOD_ID}_swap_bv divide = {RANK_SCALE} }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_slots target = flag:{MOD_ID}_swapslot5 }}
\t}}
\tglobal_var:{MOD_ID}_swap_loc = {{ {MOD_ID}_swap_pass = yes }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot6_bt value = global_var:{MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot6_gain value = {{ value = global_var:{MOD_ID}_swap_bv divide = {RANK_SCALE} }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_slots target = flag:{MOD_ID}_swapslot6 }}
\t}}
\tglobal_var:{MOD_ID}_swap_loc = {{ {MOD_ID}_swap_pass = yes }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot7_bt value = global_var:{MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot7_gain value = {{ value = global_var:{MOD_ID}_swap_bv divide = {RANK_SCALE} }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_slots target = flag:{MOD_ID}_swapslot7 }}
\t}}
\tglobal_var:{MOD_ID}_swap_loc = {{ {MOD_ID}_swap_pass = yes }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot8_bt value = global_var:{MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot8_gain value = {{ value = global_var:{MOD_ID}_swap_bv divide = {RANK_SCALE} }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_slots target = flag:{MOD_ID}_swapslot8 }}
\t}}
\tglobal_var:{MOD_ID}_swap_loc = {{ {MOD_ID}_swap_pass = yes }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot9_bt value = global_var:{MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot9_gain value = {{ value = global_var:{MOD_ID}_swap_bv divide = {RANK_SCALE} }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_slots target = flag:{MOD_ID}_swapslot9 }}
\t}}
\tglobal_var:{MOD_ID}_swap_loc = {{ {MOD_ID}_swap_pass = yes }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot10_bt value = global_var:{MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot10_gain value = {{ value = global_var:{MOD_ID}_swap_bv divide = {RANK_SCALE} }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_slots target = flag:{MOD_ID}_swapslot10 }}
\t}}
\tglobal_var:{MOD_ID}_swap_loc = {{ {MOD_ID}_swap_pass = yes }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot11_bt value = global_var:{MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot11_gain value = {{ value = global_var:{MOD_ID}_swap_bv divide = {RANK_SCALE} }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_slots target = flag:{MOD_ID}_swapslot11 }}
\t}}
\tglobal_var:{MOD_ID}_swap_loc = {{ {MOD_ID}_swap_pass = yes }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot12_bt value = global_var:{MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot12_gain value = {{ value = global_var:{MOD_ID}_swap_bv divide = {RANK_SCALE} }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_slots target = flag:{MOD_ID}_swapslot12 }}
\t}}
\tglobal_var:{MOD_ID}_swap_loc = {{ {MOD_ID}_swap_pass = yes }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot13_bt value = global_var:{MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot13_gain value = {{ value = global_var:{MOD_ID}_swap_bv divide = {RANK_SCALE} }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_slots target = flag:{MOD_ID}_swapslot13 }}
\t}}
\tglobal_var:{MOD_ID}_swap_loc = {{ {MOD_ID}_swap_pass = yes }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot14_bt value = global_var:{MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot14_gain value = {{ value = global_var:{MOD_ID}_swap_bv divide = {RANK_SCALE} }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_slots target = flag:{MOD_ID}_swapslot14 }}
\t}}
\tglobal_var:{MOD_ID}_swap_loc = {{ {MOD_ID}_swap_pass = yes }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot15_bt value = global_var:{MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot15_gain value = {{ value = global_var:{MOD_ID}_swap_bv divide = {RANK_SCALE} }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_slots target = flag:{MOD_ID}_swapslot15 }}
\t}}
\tglobal_var:{MOD_ID}_swap_loc = {{ {MOD_ID}_swap_pass = yes }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot16_bt value = global_var:{MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot16_gain value = {{ value = global_var:{MOD_ID}_swap_bv divide = {RANK_SCALE} }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_slots target = flag:{MOD_ID}_swapslot16 }}
\t}}
\tglobal_var:{MOD_ID}_swap_loc = {{ {MOD_ID}_swap_pass = yes }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot17_bt value = global_var:{MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot17_gain value = {{ value = global_var:{MOD_ID}_swap_bv divide = {RANK_SCALE} }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_slots target = flag:{MOD_ID}_swapslot17 }}
\t}}
\tglobal_var:{MOD_ID}_swap_loc = {{ {MOD_ID}_swap_pass = yes }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot18_bt value = global_var:{MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot18_gain value = {{ value = global_var:{MOD_ID}_swap_bv divide = {RANK_SCALE} }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_slots target = flag:{MOD_ID}_swapslot18 }}
\t}}
\tglobal_var:{MOD_ID}_swap_loc = {{ {MOD_ID}_swap_pass = yes }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot19_bt value = global_var:{MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot19_gain value = {{ value = global_var:{MOD_ID}_swap_bv divide = {RANK_SCALE} }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_slots target = flag:{MOD_ID}_swapslot19 }}
\t}}
\tglobal_var:{MOD_ID}_swap_loc = {{ {MOD_ID}_swap_pass = yes }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot20_bt value = global_var:{MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot20_gain value = {{ value = global_var:{MOD_ID}_swap_bv divide = {RANK_SCALE} }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_slots target = flag:{MOD_ID}_swapslot20 }}
\t}}
\tglobal_var:{MOD_ID}_swap_loc = {{ {MOD_ID}_swap_pass = yes }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot21_bt value = global_var:{MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot21_gain value = {{ value = global_var:{MOD_ID}_swap_bv divide = {RANK_SCALE} }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_slots target = flag:{MOD_ID}_swapslot21 }}
\t}}
\tglobal_var:{MOD_ID}_swap_loc = {{ {MOD_ID}_swap_pass = yes }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot22_bt value = global_var:{MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot22_gain value = {{ value = global_var:{MOD_ID}_swap_bv divide = {RANK_SCALE} }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_slots target = flag:{MOD_ID}_swapslot22 }}
\t}}
\tglobal_var:{MOD_ID}_swap_loc = {{ {MOD_ID}_swap_pass = yes }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot23_bt value = global_var:{MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot23_gain value = {{ value = global_var:{MOD_ID}_swap_bv divide = {RANK_SCALE} }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_slots target = flag:{MOD_ID}_swapslot23 }}
\t}}
\tglobal_var:{MOD_ID}_swap_loc = {{ {MOD_ID}_swap_pass = yes }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot24_bt value = global_var:{MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot24_gain value = {{ value = global_var:{MOD_ID}_swap_bv divide = {RANK_SCALE} }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_slots target = flag:{MOD_ID}_swapslot24 }}
\t}}
\tglobal_var:{MOD_ID}_swap_loc = {{ {MOD_ID}_swap_pass = yes }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot25_bt value = global_var:{MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot25_gain value = {{ value = global_var:{MOD_ID}_swap_bv divide = {RANK_SCALE} }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_slots target = flag:{MOD_ID}_swapslot25 }}
\t}}
\tglobal_var:{MOD_ID}_swap_loc = {{ {MOD_ID}_swap_pass = yes }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot26_bt value = global_var:{MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot26_gain value = {{ value = global_var:{MOD_ID}_swap_bv divide = {RANK_SCALE} }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_slots target = flag:{MOD_ID}_swapslot26 }}
\t}}
\tglobal_var:{MOD_ID}_swap_loc = {{ {MOD_ID}_swap_pass = yes }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot27_bt value = global_var:{MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot27_gain value = {{ value = global_var:{MOD_ID}_swap_bv divide = {RANK_SCALE} }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_slots target = flag:{MOD_ID}_swapslot27 }}
\t}}
\tglobal_var:{MOD_ID}_swap_loc = {{ {MOD_ID}_swap_pass = yes }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot28_bt value = global_var:{MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot28_gain value = {{ value = global_var:{MOD_ID}_swap_bv divide = {RANK_SCALE} }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_slots target = flag:{MOD_ID}_swapslot28 }}
\t}}
\tglobal_var:{MOD_ID}_swap_loc = {{ {MOD_ID}_swap_pass = yes }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot29_bt value = global_var:{MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot29_gain value = {{ value = global_var:{MOD_ID}_swap_bv divide = {RANK_SCALE} }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_slots target = flag:{MOD_ID}_swapslot29 }}
\t}}
\tglobal_var:{MOD_ID}_swap_loc = {{ {MOD_ID}_swap_pass = yes }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot30_bt value = global_var:{MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot30_gain value = {{ value = global_var:{MOD_ID}_swap_bv divide = {RANK_SCALE} }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_slots target = flag:{MOD_ID}_swapslot30 }}
\t}}
\tglobal_var:{MOD_ID}_swap_loc = {{ {MOD_ID}_swap_pass = yes }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot31_bt value = global_var:{MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot31_gain value = {{ value = global_var:{MOD_ID}_swap_bv divide = {RANK_SCALE} }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_slots target = flag:{MOD_ID}_swapslot31 }}
\t}}
\tglobal_var:{MOD_ID}_swap_loc = {{ {MOD_ID}_swap_pass = yes }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot32_bt value = global_var:{MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot32_gain value = {{ value = global_var:{MOD_ID}_swap_bv divide = {RANK_SCALE} }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_slots target = flag:{MOD_ID}_swapslot32 }}
\t}}
\tglobal_var:{MOD_ID}_swap_loc = {{ {MOD_ID}_swap_pass = yes }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot33_bt value = global_var:{MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot33_gain value = {{ value = global_var:{MOD_ID}_swap_bv divide = {RANK_SCALE} }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_slots target = flag:{MOD_ID}_swapslot33 }}
\t}}
\tglobal_var:{MOD_ID}_swap_loc = {{ {MOD_ID}_swap_pass = yes }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot34_bt value = global_var:{MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot34_gain value = {{ value = global_var:{MOD_ID}_swap_bv divide = {RANK_SCALE} }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_slots target = flag:{MOD_ID}_swapslot34 }}
\t}}
\tglobal_var:{MOD_ID}_swap_loc = {{ {MOD_ID}_swap_pass = yes }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot35_bt value = global_var:{MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot35_gain value = {{ value = global_var:{MOD_ID}_swap_bv divide = {RANK_SCALE} }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_slots target = flag:{MOD_ID}_swapslot35 }}
\t}}
\tglobal_var:{MOD_ID}_swap_loc = {{ {MOD_ID}_swap_pass = yes }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot36_bt value = global_var:{MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot36_gain value = {{ value = global_var:{MOD_ID}_swap_bv divide = {RANK_SCALE} }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_slots target = flag:{MOD_ID}_swapslot36 }}
\t}}
\tglobal_var:{MOD_ID}_swap_loc = {{ {MOD_ID}_swap_pass = yes }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot37_bt value = global_var:{MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot37_gain value = {{ value = global_var:{MOD_ID}_swap_bv divide = {RANK_SCALE} }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_slots target = flag:{MOD_ID}_swapslot37 }}
\t}}
\tglobal_var:{MOD_ID}_swap_loc = {{ {MOD_ID}_swap_pass = yes }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot38_bt value = global_var:{MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot38_gain value = {{ value = global_var:{MOD_ID}_swap_bv divide = {RANK_SCALE} }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_slots target = flag:{MOD_ID}_swapslot38 }}
\t}}
\tglobal_var:{MOD_ID}_swap_loc = {{ {MOD_ID}_swap_pass = yes }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot39_bt value = global_var:{MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot39_gain value = {{ value = global_var:{MOD_ID}_swap_bv divide = {RANK_SCALE} }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_slots target = flag:{MOD_ID}_swapslot39 }}
\t}}
\tglobal_var:{MOD_ID}_swap_loc = {{ {MOD_ID}_swap_pass = yes }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot40_bt value = global_var:{MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot40_gain value = {{ value = global_var:{MOD_ID}_swap_bv divide = {RANK_SCALE} }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_slots target = flag:{MOD_ID}_swapslot40 }}
\t}}
\tglobal_var:{MOD_ID}_swap_loc = {{ {MOD_ID}_swap_pass = yes }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot41_bt value = global_var:{MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot41_gain value = {{ value = global_var:{MOD_ID}_swap_bv divide = {RANK_SCALE} }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_slots target = flag:{MOD_ID}_swapslot41 }}
\t}}
\tglobal_var:{MOD_ID}_swap_loc = {{ {MOD_ID}_swap_pass = yes }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot42_bt value = global_var:{MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot42_gain value = {{ value = global_var:{MOD_ID}_swap_bv divide = {RANK_SCALE} }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_slots target = flag:{MOD_ID}_swapslot42 }}
\t}}
\tglobal_var:{MOD_ID}_swap_loc = {{ {MOD_ID}_swap_pass = yes }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot43_bt value = global_var:{MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot43_gain value = {{ value = global_var:{MOD_ID}_swap_bv divide = {RANK_SCALE} }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_slots target = flag:{MOD_ID}_swapslot43 }}
\t}}
\tglobal_var:{MOD_ID}_swap_loc = {{ {MOD_ID}_swap_pass = yes }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot44_bt value = global_var:{MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot44_gain value = {{ value = global_var:{MOD_ID}_swap_bv divide = {RANK_SCALE} }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_slots target = flag:{MOD_ID}_swapslot44 }}
\t}}
\tglobal_var:{MOD_ID}_swap_loc = {{ {MOD_ID}_swap_pass = yes }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot45_bt value = global_var:{MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot45_gain value = {{ value = global_var:{MOD_ID}_swap_bv divide = {RANK_SCALE} }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_slots target = flag:{MOD_ID}_swapslot45 }}
\t}}
\tglobal_var:{MOD_ID}_swap_loc = {{ {MOD_ID}_swap_pass = yes }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot46_bt value = global_var:{MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot46_gain value = {{ value = global_var:{MOD_ID}_swap_bv divide = {RANK_SCALE} }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_slots target = flag:{MOD_ID}_swapslot46 }}
\t}}
\tglobal_var:{MOD_ID}_swap_loc = {{ {MOD_ID}_swap_pass = yes }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot47_bt value = global_var:{MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot47_gain value = {{ value = global_var:{MOD_ID}_swap_bv divide = {RANK_SCALE} }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_slots target = flag:{MOD_ID}_swapslot47 }}
\t}}
\tglobal_var:{MOD_ID}_swap_loc = {{ {MOD_ID}_swap_pass = yes }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot48_bt value = global_var:{MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot48_gain value = {{ value = global_var:{MOD_ID}_swap_bv divide = {RANK_SCALE} }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_slots target = flag:{MOD_ID}_swapslot48 }}
\t}}
\tglobal_var:{MOD_ID}_swap_loc = {{ {MOD_ID}_swap_pass = yes }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot49_bt value = global_var:{MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot49_gain value = {{ value = global_var:{MOD_ID}_swap_bv divide = {RANK_SCALE} }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_slots target = flag:{MOD_ID}_swapslot49 }}
\t}}
\tglobal_var:{MOD_ID}_swap_loc = {{ {MOD_ID}_swap_pass = yes }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot50_bt value = global_var:{MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot50_gain value = {{ value = global_var:{MOD_ID}_swap_bv divide = {RANK_SCALE} }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_slots target = flag:{MOD_ID}_swapslot50 }}
\t}}
\tglobal_var:{MOD_ID}_swap_loc = {{ {MOD_ID}_swap_pass = yes }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot51_bt value = global_var:{MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot51_gain value = {{ value = global_var:{MOD_ID}_swap_bv divide = {RANK_SCALE} }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_slots target = flag:{MOD_ID}_swapslot51 }}
\t}}
\tglobal_var:{MOD_ID}_swap_loc = {{ {MOD_ID}_swap_pass = yes }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot52_bt value = global_var:{MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot52_gain value = {{ value = global_var:{MOD_ID}_swap_bv divide = {RANK_SCALE} }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_slots target = flag:{MOD_ID}_swapslot52 }}
\t}}
\tglobal_var:{MOD_ID}_swap_loc = {{ {MOD_ID}_swap_pass = yes }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot53_bt value = global_var:{MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot53_gain value = {{ value = global_var:{MOD_ID}_swap_bv divide = {RANK_SCALE} }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_slots target = flag:{MOD_ID}_swapslot53 }}
\t}}
\tglobal_var:{MOD_ID}_swap_loc = {{ {MOD_ID}_swap_pass = yes }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot54_bt value = global_var:{MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot54_gain value = {{ value = global_var:{MOD_ID}_swap_bv divide = {RANK_SCALE} }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_slots target = flag:{MOD_ID}_swapslot54 }}
\t}}
\tglobal_var:{MOD_ID}_swap_loc = {{ {MOD_ID}_swap_pass = yes }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot55_bt value = global_var:{MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot55_gain value = {{ value = global_var:{MOD_ID}_swap_bv divide = {RANK_SCALE} }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_slots target = flag:{MOD_ID}_swapslot55 }}
\t}}
\tglobal_var:{MOD_ID}_swap_loc = {{ {MOD_ID}_swap_pass = yes }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot56_bt value = global_var:{MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot56_gain value = {{ value = global_var:{MOD_ID}_swap_bv divide = {RANK_SCALE} }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_slots target = flag:{MOD_ID}_swapslot56 }}
\t}}
\tglobal_var:{MOD_ID}_swap_loc = {{ {MOD_ID}_swap_pass = yes }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot57_bt value = global_var:{MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot57_gain value = {{ value = global_var:{MOD_ID}_swap_bv divide = {RANK_SCALE} }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_slots target = flag:{MOD_ID}_swapslot57 }}
\t}}
\tglobal_var:{MOD_ID}_swap_loc = {{ {MOD_ID}_swap_pass = yes }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot58_bt value = global_var:{MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot58_gain value = {{ value = global_var:{MOD_ID}_swap_bv divide = {RANK_SCALE} }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_slots target = flag:{MOD_ID}_swapslot58 }}
\t}}
\tglobal_var:{MOD_ID}_swap_loc = {{ {MOD_ID}_swap_pass = yes }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot59_bt value = global_var:{MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot59_gain value = {{ value = global_var:{MOD_ID}_swap_bv divide = {RANK_SCALE} }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_slots target = flag:{MOD_ID}_swapslot59 }}
\t}}
\tglobal_var:{MOD_ID}_swap_loc = {{ {MOD_ID}_swap_pass = yes }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot60_bt value = global_var:{MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot60_gain value = {{ value = global_var:{MOD_ID}_swap_bv divide = {RANK_SCALE} }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_slots target = flag:{MOD_ID}_swapslot60 }}
\t}}
\tglobal_var:{MOD_ID}_swap_loc = {{ {MOD_ID}_swap_pass = yes }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot61_bt value = global_var:{MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot61_gain value = {{ value = global_var:{MOD_ID}_swap_bv divide = {RANK_SCALE} }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_slots target = flag:{MOD_ID}_swapslot61 }}
\t}}
\tglobal_var:{MOD_ID}_swap_loc = {{ {MOD_ID}_swap_pass = yes }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot62_bt value = global_var:{MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot62_gain value = {{ value = global_var:{MOD_ID}_swap_bv divide = {RANK_SCALE} }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_slots target = flag:{MOD_ID}_swapslot62 }}
\t}}
\tglobal_var:{MOD_ID}_swap_loc = {{ {MOD_ID}_swap_pass = yes }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot63_bt value = global_var:{MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot63_gain value = {{ value = global_var:{MOD_ID}_swap_bv divide = {RANK_SCALE} }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_slots target = flag:{MOD_ID}_swapslot63 }}
\t}}
\tglobal_var:{MOD_ID}_swap_loc = {{ {MOD_ID}_swap_pass = yes }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot64_bt value = global_var:{MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot64_gain value = {{ value = global_var:{MOD_ID}_swap_bv divide = {RANK_SCALE} }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_slots target = flag:{MOD_ID}_swapslot64 }}
\t}}
\tglobal_var:{MOD_ID}_swap_loc = {{ {MOD_ID}_swap_pass = yes }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot65_bt value = global_var:{MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot65_gain value = {{ value = global_var:{MOD_ID}_swap_bv divide = {RANK_SCALE} }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_slots target = flag:{MOD_ID}_swapslot65 }}
\t}}
\tglobal_var:{MOD_ID}_swap_loc = {{ {MOD_ID}_swap_pass = yes }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot66_bt value = global_var:{MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot66_gain value = {{ value = global_var:{MOD_ID}_swap_bv divide = {RANK_SCALE} }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_slots target = flag:{MOD_ID}_swapslot66 }}
\t}}
\tglobal_var:{MOD_ID}_swap_loc = {{ {MOD_ID}_swap_pass = yes }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot67_bt value = global_var:{MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot67_gain value = {{ value = global_var:{MOD_ID}_swap_bv divide = {RANK_SCALE} }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_slots target = flag:{MOD_ID}_swapslot67 }}
\t}}
\tglobal_var:{MOD_ID}_swap_loc = {{ {MOD_ID}_swap_pass = yes }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot68_bt value = global_var:{MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot68_gain value = {{ value = global_var:{MOD_ID}_swap_bv divide = {RANK_SCALE} }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_slots target = flag:{MOD_ID}_swapslot68 }}
\t}}
\tglobal_var:{MOD_ID}_swap_loc = {{ {MOD_ID}_swap_pass = yes }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot69_bt value = global_var:{MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot69_gain value = {{ value = global_var:{MOD_ID}_swap_bv divide = {RANK_SCALE} }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_slots target = flag:{MOD_ID}_swapslot69 }}
\t}}
\tglobal_var:{MOD_ID}_swap_loc = {{ {MOD_ID}_swap_pass = yes }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot70_bt value = global_var:{MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot70_gain value = {{ value = global_var:{MOD_ID}_swap_bv divide = {RANK_SCALE} }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_slots target = flag:{MOD_ID}_swapslot70 }}
\t}}
\tglobal_var:{MOD_ID}_swap_loc = {{ {MOD_ID}_swap_pass = yes }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot71_bt value = global_var:{MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot71_gain value = {{ value = global_var:{MOD_ID}_swap_bv divide = {RANK_SCALE} }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_slots target = flag:{MOD_ID}_swapslot71 }}
\t}}
\tglobal_var:{MOD_ID}_swap_loc = {{ {MOD_ID}_swap_pass = yes }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot72_bt value = global_var:{MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot72_gain value = {{ value = global_var:{MOD_ID}_swap_bv divide = {RANK_SCALE} }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_slots target = flag:{MOD_ID}_swapslot72 }}
\t}}
\tglobal_var:{MOD_ID}_swap_loc = {{ {MOD_ID}_swap_pass = yes }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot73_bt value = global_var:{MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot73_gain value = {{ value = global_var:{MOD_ID}_swap_bv divide = {RANK_SCALE} }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_slots target = flag:{MOD_ID}_swapslot73 }}
\t}}
\tglobal_var:{MOD_ID}_swap_loc = {{ {MOD_ID}_swap_pass = yes }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot74_bt value = global_var:{MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot74_gain value = {{ value = global_var:{MOD_ID}_swap_bv divide = {RANK_SCALE} }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_slots target = flag:{MOD_ID}_swapslot74 }}
\t}}
\tglobal_var:{MOD_ID}_swap_loc = {{ {MOD_ID}_swap_pass = yes }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot75_bt value = global_var:{MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot75_gain value = {{ value = global_var:{MOD_ID}_swap_bv divide = {RANK_SCALE} }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_slots target = flag:{MOD_ID}_swapslot75 }}
\t}}
\tglobal_var:{MOD_ID}_swap_loc = {{ {MOD_ID}_swap_pass = yes }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot76_bt value = global_var:{MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot76_gain value = {{ value = global_var:{MOD_ID}_swap_bv divide = {RANK_SCALE} }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_slots target = flag:{MOD_ID}_swapslot76 }}
\t}}
\tglobal_var:{MOD_ID}_swap_loc = {{ {MOD_ID}_swap_pass = yes }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot77_bt value = global_var:{MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot77_gain value = {{ value = global_var:{MOD_ID}_swap_bv divide = {RANK_SCALE} }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_slots target = flag:{MOD_ID}_swapslot77 }}
\t}}
\tglobal_var:{MOD_ID}_swap_loc = {{ {MOD_ID}_swap_pass = yes }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot78_bt value = global_var:{MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot78_gain value = {{ value = global_var:{MOD_ID}_swap_bv divide = {RANK_SCALE} }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_slots target = flag:{MOD_ID}_swapslot78 }}
\t}}
\tglobal_var:{MOD_ID}_swap_loc = {{ {MOD_ID}_swap_pass = yes }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot79_bt value = global_var:{MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot79_gain value = {{ value = global_var:{MOD_ID}_swap_bv divide = {RANK_SCALE} }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_slots target = flag:{MOD_ID}_swapslot79 }}
\t}}
\tglobal_var:{MOD_ID}_swap_loc = {{ {MOD_ID}_swap_pass = yes }}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot80_bt value = global_var:{MOD_ID}_swap_bb }}
\t\tset_variable = {{ name = {MOD_ID}_swapslot80_gain value = {{ value = global_var:{MOD_ID}_swap_bv divide = {RANK_SCALE} }} }}
\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_slots target = flag:{MOD_ID}_swapslot80 }}
\t}}

\t# Левый список -- то, что стоит: он без чисел, поэтому остаётся обычной
\t# датамоделью по глобальному списку зданий.
\tglobal_var:{MOD_ID}_swap_loc = {{
\t\tevery_in_list = {{
\t\t\tvariable = {MOD_ID}_row_builds
\t\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_swap_here target = this }}
\t\t}}
\t}}
}}

# Открыть окно на этой локации.
# Scope: country, ждёт scope:wtp_location
{MOD_ID}_swap_open_effect = {{
\tset_global_variable = {{ name = {MOD_ID}_swap_loc value = scope:wtp_location }}
\t{MOD_ID}_swap_rebuild = yes
\tset_variable = {{ name = {MOD_ID}_swap_open value = 1 }}
}}

# Scope: country
{MOD_ID}_swap_close_effect = {{
\tremove_variable = {MOD_ID}_swap_open
}}
""")

    # ---- «−» и «+», обе через эффекты редактора ----------------------------
    #
    # **Одно нажатие -- один домик, и именно тот, по которому нажали.** Прежде
    # здесь звались эффекты редактора по ВСЕМ товарам здания разом: здание,
    # умеющее два товара, ставило два домика, а `_edit_place_<товар>` ставил не
    # ту ступень лестницы, по которой нажали, а ту, которой этот товар
    # выигрывает. Его прогон 2026-09-14: «нажал +1 на какой-то домик из ND…
    # добавилось сразу аж два домика: Тонкое сукно лвл4 и спиртовые лвл4»,
    # «нажал +1 на пиво лвл1, но добавилось пиво лвл4».
    #
    # Лечится без единого нового правила постановки: вызов гейтится тем, что
    # `_pm<товар>` -- выигравший здесь способ -- принадлежит **этому** зданию.
    # Тогда `_edit_place_<товар>` поставит именно его, потому что здание он
    # выбирает по тому же `_pm`. А `_swap_once` держит счёт: сработать может
    # только первый подошедший товар.
    # **Сторона спрашивается здесь, и её отсутствие держало «каменную кладку»
    # намертво.** Его прогон 2026-09-14: «убрал всё, потом поставил каменную
    # кладку и попытался её снова убрать -- она встала там намертво… остальные
    # домики ставятся и убираются как надо». `mason` -- одно из немногих зданий,
    # которое игра пускает и в село, и в город (`rural_settlement = yes`
    # **и** `town = yes`), поэтому у него в этом списке две записи на один
    # товар. Ворота обеих читали `_pm<n>` -- **городскую** переменную -- и
    # перечисляли **те же** номера способов, так что в городе первой срабатывала
    # сельская: `_edit_remove_rural_<n>` внутри себя спрашивает
    # `_plan_is_town = no`, молча не делал ничего, а `_swap_once` уже был
    # потрачен, и городская ветка не получала хода никогда.
    #
    # Лечится двумя словами: у сельской стороны своя переменная (`_prm<n>`, как
    # у `_edit_remove_rural_*`), и сторона стоит в воротах, поэтому чужая ветка
    # не может съесть нажатие.
    def once(kind: str, building: str) -> str:
        calls = ""
        for index, side, mis in by_building.get(building, []):
            listname = "town" if side == "t" else "rural"
            method_var = "pm" if side == "t" else "prm"
            is_town = "yes" if side == "t" else "no"
            same = " ".join(f"var:{MOD_ID}_{method_var}{index} = {m}" for m in mis)
            calls += f"""\t\t\tif = {{
\t\t\t\tlimit = {{
\t\t\t\t\tvar:{MOD_ID}_swap_once = 0
\t\t\t\t\t{MOD_ID}_plan_is_town = {is_town}
\t\t\t\t\tOR = {{ {same} }}
\t\t\t\t}}
\t\t\t\t{MOD_ID}_edit_{kind}_{listname}_{index} = yes
\t\t\t\tset_variable = {{ name = {MOD_ID}_swap_once value = 1 }}
\t\t\t}}
"""
        return calls

    drop = ""
    for building in sorted(set(by_building) | set(villages)):
        calls = once("remove", building)
        if building in villages:
            calls += (f"\t\t\t{MOD_ID}_plan_drop_village_{villages.index(building) + 1}"
                      f" = yes\n")
        drop += f"""\t\tif = {{
\t\t\tlimit = {{ scope:wtp_bt = building_type:{building} }}
{calls}\t\t}}
"""
    # **«+» ставит именно это здание, и для этого у него свой эффект.**
    #
    # Прошлый заход гейтил вызов `_edit_place_<товар>` тем, что `_pm<товар>` --
    # выигравший здесь способ -- принадлежит нажатому зданию. Это чинило «одно
    # нажатие -- один домик», но ломало всё остальное: список нарочно предлагает
    # здания, которые победителями **не** являются, поэтому у почти каждой строки
    # ворота не совпадали и «+» молча не делал ничего (его прогон 2026-09-14).
    #
    # Значит эффект свой. Он повторяет ровно то, что делает постановка плана --
    # те же списки, те же счётчики, тот же потолок, -- и добавляет одно: **клик
    # объявляет это здание ответом для своего товара здесь**, то есть пишет
    # `_pm<товар>`. Тогда и «−» на нём потом сработает: снятие ищет товар по
    # тому же `_pm`.
    put = ""
    for building in sorted(b for b in by_building if b not in villages):
        arms = ""
        for index, side, mis in by_building[building]:
            good = order[index - 1]
            cap = "urban" if side == "t" else "rural"
            method_var = "pm" if side == "t" else "prm"
            gain_var = "p" if side == "t" else "pr"
            best_mi = max(mis, key=lambda m: by_method[m].output)
            out_n = int(round(by_method[best_mi].output * 100))
            is_town = "yes" if side == "t" else "no"
            # `%`-форматирование, а не f-строка: удвоенные скобки остались бы
            # удвоенными, и движок прочёл бы блок одним ключом (поймал чекер).
            bcount = ("\t\t\tchange_global_variable = { name = %s_bn%d add = 1 }\n"
                      % (MOD_ID, shared.index(building) + 1)
                      if building in shared else "")
            arms += f"""\t\tif = {{
\t\t\tlimit = {{
\t\t\t\tvar:{MOD_ID}_swap_once = 0
\t\t\t\t{MOD_ID}_plan_is_town = {is_town}
\t\t\t\t{MOD_ID}_is_granary = no
\t\t\t\tvar:{MOD_ID}_load < global_var:{MOD_ID}_plan_cap_{cap}
\t\t\t\tNOT = {{ is_target_in_variable_list = {{ name = {MOD_ID}_plan_goods target = goods:{good} }} }}
\t\t\t}}
\t\t\tset_variable = {{ name = {MOD_ID}_{method_var}{index} value = {best_mi} }}
\t\t\tchange_global_variable = {{ name = {MOD_ID}_pout{index} add = {out_n} }}
\t\t\tadd_to_variable_list = {{ name = {MOD_ID}_plan_goods target = goods:{good} }}
\t\t\tadd_to_variable_list = {{ name = {MOD_ID}_plan_builds target = building_type:{building} }}
\t\t\tchange_variable = {{ name = {MOD_ID}_load add = 1 }}
\t\t\tchange_global_variable = {{ name = {MOD_ID}_plan_placed add = 1 }}
\t\t\tchange_global_variable = {{ name = {MOD_ID}_plan_added add = 1 }}
\t\t\tchange_global_variable = {{ name = {MOD_ID}_pn{index} add = 1 }}
\t\t\tchange_global_variable = {{ name = {MOD_ID}_pn{side}{index} add = 1 }}
\t\t\tchange_global_variable = {{ name = {MOD_ID}_plan_p{side} add = 1 }}
{bcount}\t\t\tchange_global_variable = {{ name = {MOD_ID}_plan_gain add = var:{MOD_ID}_{gain_var}{index} }}
\t\t\tif = {{
\t\t\t\tlimit = {{ var:{MOD_ID}_{gain_var}{index} > 0 }}
\t\t\t\tchange_global_variable = {{ name = {MOD_ID}_plan_fed add = 1 }}
\t\t\t}}
\t\t\tset_variable = {{ name = {MOD_ID}_swap_once value = 1 }}
\t\t}}
"""
        put += f"""\t\tif = {{
\t\t\tlimit = {{ scope:wtp_bt = building_type:{building} }}
{arms}\t\t}}
"""
    out.append(f"""
# Снять этот домик с этой локации.
#
# **Зовутся все товары здания сразу.** Здание, которое умеет несколько товаров,
# стоит здесь ради одного из них, и какого именно -- знает `_edit_remove_*`
# через `_pm<n>`. Спрашивать это здесь значило бы держать второй экземпляр того
# же знания.
# Scope: country, ждёт scope:wtp_bt
{MOD_ID}_swap_drop_effect = {{
\tglobal_var:{MOD_ID}_swap_loc = {{
\t\tset_variable = {{ name = {MOD_ID}_swap_once value = 0 }}
{drop}\t}}
\t{MOD_ID}_plan_rows = yes
\t{MOD_ID}_swap_rebuild = yes
}}

# Поставить этот домик в свободное место этой локации.
#
# `_edit_place_*` сам спрашивает и ворота (`_edit_fits_*`), и комнату, поэтому
# нажатие в полной локации просто ничего не делает -- места освобождает «×».
# Scope: country, ждёт scope:wtp_bt
{MOD_ID}_swap_put_effect = {{
\tglobal_var:{MOD_ID}_swap_loc = {{
\t\tset_variable = {{ name = {MOD_ID}_swap_once value = 0 }}
{put}\t}}
\t{MOD_ID}_plan_rows = yes
\t{MOD_ID}_swap_rebuild = yes
}}

# «Отсеять» -- тумблер, и список пересобирается тут же.
# Scope: country
{MOD_ID}_swap_sift_effect = {{
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_swap_sift }}
\t\tremove_global_variable = {MOD_ID}_swap_sift
\t}}
\telse = {{ set_global_variable = {{ name = {MOD_ID}_swap_sift value = 1 }} }}
\t{MOD_ID}_swap_rebuild = yes
}}
""")
    return "".join(out)


def rows_file() -> str:
    """The ranking pass. One row per province definition, best first.

    There is no Mod Menu table any more: it said the same thing as the window in
    one line each, and it was the only thing holding the answer to fifty rows.
    What is left is the list the window repeats over.
    """
    out = [HEADER, f"""#
# Ranking is the engine's: `ordered_in_global_list` takes `order_by` as a script
# value and sorts highest first -- vanilla proves the direction by writing
# `multiply = -1` on the one place it wants the weakest -- and pairs `max` with
# `check_range_bounds = no` when the list may be shorter than asked for.
#
# Scope: country
{MOD_ID}_clear_rows = {{
\tset_global_variable = {{ name = {MOD_ID}_found value = 0 }}
\tevery_in_global_list = {{
\t\tvariable = {MOD_ID}_row_taken_locations
\t\tremove_variable = {MOD_ID}_row_taken
\t\tremove_variable = {MOD_ID}_rank
\t}}
\tclear_global_variable_list = {MOD_ID}_row_taken_locations
\t# `_ranked` is the answer and survives; `_results` is the copy the window
\t# repeats over, and it only exists while the window is open -- emptying the
\t# datamodel is the only thing that frees a scripted widget's rows.
\tclear_global_variable_list = {MOD_ID}_ranked
\tclear_global_variable_list = {MOD_ID}_results
\t# Both windows' lists, and forgetting the second one is what left the rights
\t# window drawing rows whose rank had just been taken off them.
\tclear_global_variable_list = {MOD_ID}_right_results
}}

# Scope: country
{MOD_ID}_fill_rows = {{
\t# `max` counts locations walked, not rows produced. Every location of a
\t# province scores the same and only the first of them takes a row, so fifty
\t# would have stopped at about a dozen provinces -- which is what the fifth run
\t# showed. Eight locations per province is above the game's widest.
\tordered_in_global_list = {{
\t\tvariable = {MOD_ID}_candidates
\t\torder_by = {MOD_ID}_score
\t\tmax = {RESULT_ROWS * 8}
\t\tcheck_range_bounds = no
\t\t{MOD_ID}_store_row = yes
\t}}
}}

# Park one province's answer on the location the ranking kept, and remember that
# location in rank order.
#
# One row per province definition -- the province as the map draws it, whole,
# rather than the piece of it one country owns. The game splits a province by
# ownership: half of Bessarabia under Moldavia is its own `province`, named
# "Moldavian province Bessarabia", and the other half is another. Every location
# of one piece scores the same, so a row per piece is several ways of saying one
# thing -- and worse, the number itself would move on the day the pieces join,
# which is exactly the day this mod is planning for.
#
# Taken is marked on the locations rather than on the definition: a location
# certainly holds a variable, and this pass already has every one of them.
# Scope: location
{MOD_ID}_store_row = {{
\tif = {{
\t\tlimit = {{
\t\t\tglobal_var:{MOD_ID}_found < {RESULT_ROWS}
\t\t\t# Nothing won here on either side and in neither age -- which now means
\t\t\t# the good is made in no building this location could ever hold. A row
\t\t\t# for it would have no building and no method to print.
\t\t\t#
\t\t\t# The endgame halves are in the OR on purpose: in the first age most
\t\t\t# goods have nothing available yet, and dropping those rows would empty
\t\t\t# the second column exactly where it is worth most.
\t\t\tOR = {{
\t\t\t\tvar:{MOD_ID}_best_method > 0
\t\t\t\tvar:{MOD_ID}_best_method_rural > 0
\t\t\t\tvar:{MOD_ID}_mid_best_method > 0
\t\t\t\tvar:{MOD_ID}_mid_best_method_rural > 0
\t\t\t\tvar:{MOD_ID}_end_best_method > 0
\t\t\t\tvar:{MOD_ID}_end_best_method_rural > 0
\t\t\t}}
\t\t\tNOT = {{ has_variable = {MOD_ID}_row_taken }}
\t\t}}
\t\tprovince_definition = {{
\t\t\tevery_location_in_province_definition = {{
\t\t\t\tset_variable = {{ name = {MOD_ID}_row_taken value = 1 }}
\t\t\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_row_taken_locations target = this }}
\t\t\t}}
\t\t}}
\t\t# The winners are parked first and the row decided afterwards, because
\t\t# «is this province worth a row» is a question about the bonus, and the
\t\t# bonus is not known until the method that won is.
\t\t# Which of the three the row *names* follows the button. Ranked for the
\t\t# last age and still reading «Гильдия портных» off the near column is what
\t\t# the twenty-third run saw: the order was right and the building was the one
\t\t# you can build today. A variable on the row rather than a global read from
\t\t# the window, because a location variable is the one thing the GUI is proven
\t\t# to read.
\t\tif = {{
\t\t\tlimit = {{ has_global_variable = {MOD_ID}_rank_by_end }}
\t\t\tset_variable = {{ name = {MOD_ID}_row_end value = 1 }}
\t\t}}
\t\telse = {{
\t\t\tremove_variable = {MOD_ID}_row_end
\t\t}}
\t\t# **How many of the province's locations can actually hold this answer.**
\t\t# Every location of a province scores the same -- the bonus is the whole
\t\t# province's -- but they do not all pass `can_build_building`: the owner
\t\t# found a quarry offered for Sauerland where one of its seven locations is
\t\t# flat. The scoring pass has already asked that question of every
\t\t# candidate, so the count is free: the locations whose own winner is the
\t\t# same method as this row's are the ones the building may stand in.
\t\tset_global_variable = {{ name = {MOD_ID}_fit_method value = var:{MOD_ID}_best_method }}
\t\tset_global_variable = {{ name = {MOD_ID}_fit_method_rural value = var:{MOD_ID}_best_method_rural }}
\t\tset_global_variable = {{ name = {MOD_ID}_fit_n value = 0 }}
\t\tset_global_variable = {{ name = {MOD_ID}_fit_all value = 0 }}
\t\tprovince_definition = {{
\t\t\tevery_location_in_province_definition = {{
\t\t\t\tlimit = {{ has_variable = {MOD_ID}_best_method }}
\t\t\t\tchange_global_variable = {{ name = {MOD_ID}_fit_all add = 1 }}
\t\t\t\tif = {{
\t\t\t\t\tlimit = {{
\t\t\t\t\t\tOR = {{
\t\t\t\t\t\t\tAND = {{
\t\t\t\t\t\t\t\tglobal_var:{MOD_ID}_fit_method > 0
\t\t\t\t\t\t\t\tvar:{MOD_ID}_best_method = global_var:{MOD_ID}_fit_method
\t\t\t\t\t\t\t}}
\t\t\t\t\t\t\tAND = {{
\t\t\t\t\t\t\t\tglobal_var:{MOD_ID}_fit_method_rural > 0
\t\t\t\t\t\t\t\tvar:{MOD_ID}_best_method_rural = global_var:{MOD_ID}_fit_method_rural
\t\t\t\t\t\t\t}}
\t\t\t\t\t\t}}
\t\t\t\t\t}}
\t\t\t\t\tchange_global_variable = {{ name = {MOD_ID}_fit_n add = 1 }}
\t\t\t\t}}
\t\t\t}}
\t\t}}
\t\tset_variable = {{ name = {MOD_ID}_fit value = global_var:{MOD_ID}_fit_n }}
\t\tset_variable = {{ name = {MOD_ID}_fit_of value = global_var:{MOD_ID}_fit_all }}
\t\t{MOD_ID}_store_winner_now_town = yes
\t\t{MOD_ID}_store_winner_now_rural = yes
\t\t{MOD_ID}_store_winner_mid_town = yes
\t\t{MOD_ID}_store_winner_mid_rural = yes
\t\t{MOD_ID}_store_winner_end_town = yes
\t\t{MOD_ID}_store_winner_end_rural = yes
\t\tif = {{
\t\t\tlimit = {{ {MOD_ID}_row_is_worth_it = yes }}
\t\t\tchange_global_variable = {{ name = {MOD_ID}_found add = 1 }}
\t\t\t# The place in the ranking, written down where the row can print it. The
\t\t\t# order a list is built in is not an order anything downstream promises
\t\t\t# to keep, so the answer says its own rank rather than where it sits.
\t\t\tset_variable = {{ name = {MOD_ID}_rank value = global_var:{MOD_ID}_found }}
\t\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_ranked target = this }}
\t\t}}
\t}}
}}
"""]
    return "".join(out)


def excluded_rights() -> dict[str, str]:
    """Right the game forbids -> the right that forbids it, off the `allow` blocks.

    **Read for the check below and not for a rule.** The condition is
    `scope:target = { NOT = { has_town_rights = ... } }`, and `scope:target` is
    the *town*: it says a town may not hold both, and says nothing whatever about
    which of them a country should grant. The plan gives every town exactly one
    right, so **no pair in this map can ever bind on a plan**.
    """
    out: dict[str, str] = {}
    for path in sorted((refs.GAME_COMMON / "town_rights").glob("*.txt")):
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        for block in re.finditer(r"^([a-z0-9_]+) = \{(.*?)^\}", text, re.S | re.M):
            allow = re.search(r"allow\s*=\s*\{(.*?)\n\t\}", block.group(2), re.S)
            if not allow:
                continue
            for victim in re.findall(
                    r"NOT\s*=\s*\{\s*has_town_rights\s*=\s*town_rights_type:([a-z0-9_]+)",
                    allow.group(1)):
                out[victim] = block.group(1)
    return out


# **The one charter the mod drops in favour of another, and it is the owner's
# ruling and not the game's rule.** 2026-09-03, on Flemish cloth against royal
# textile: «оно должно по сути заменять собой базовое текстильное право в расчёте
# везде, если оно вдруг становится доступным». Five levels of a guild beat +20%
# of its output until the guild's cap passes 25
# (`docs/investigations/town_rights.md`), and a cap that high wants a megalopolis,
# so in towns the level right is the better of the two nearly always. The mod
# scores no right by the size of its bonus -- settled 2026-09-02 -- so it cannot
# derive this, and a preference it cannot derive is written down as one.
#
# **It used to be derived, from `excluded_rights()`, and that was a real fault in
# the shipped build.** The game's `allow` is a *town* condition and eight pairs
# carry one; read as "the country grants the excluder instead" it also threw away
# `royal_naval_rights` (+30% naval supplies, +30% tar) and `royal_tooling_rights`
# (+30% tools) for every Scandinavian country, in favour of the two privileges
# that exclude them -- +20%/+20% and +10%. Scandinavia is the ground those two
# royal charters are best on, and no country that had them could be given one.
PREFERRED_RIGHT = {"royal_textile_rights": "flemish_cloth_industries_right"}


def right_methods(right: eu5data.TownRight, good: str,
                  rows: list[eu5data.Method]) -> list[int]:
    """Номера городских методов, которым право этого товара и адресовано.

    Пусто -- право поднимает товар целиком, годится любое его здание. Не пусто --
    бонус на лимит домиков конкретного здания, и «любое здание того же товара»
    тут неправда: `flemish_cloth_industries_right` поднимает гильдию портных, а
    не тибетское ателье, которое делает то же тонкое сукно. Владелец поймал это
    на прогоне 2026-09-09.
    """
    names = right.only.get(good)
    if not names:
        return []
    return sorted(i for i, m in enumerate(rows, start=1)
                  if m.building in names and m.urban and m.produced == good)


def output_rights(rows: list[eu5data.Method], game: eu5data.Game) -> list[eu5data.TownRight]:
    """The urban rights this mod answers for: every one that helps a good.

    **Output and levels alike, and scored the same way**, at the owner's word,
    2026-09-02: «не важно право это на бонус производительности или на лимит
    домиков — все полезны и все по идее должны использоваться». A right is
    scored on *which goods it favours* and never on the size of the favour, so
    the two kinds need no common unit -- which is what had kept the level half
    out. The mod must never read a building's levels either way
    (`docs/investigations/town_rights.md`): the cap moves as a location grows.

    In practice this admits exactly one more, `flemish_cloth_industries_right`.
    The four marketplace charters grant levels to a marketplace, which no method
    produces, so they fall out here as they always did -- trade and not
    production, and «вообще не про то».

    A good the game makes no method for would be an empty slot on every row, so
    it is dropped from the bundle, and a right left with nothing is dropped
    whole.
    """
    made = {m.produced for m in rows}
    by_key = {r.key: r for r in game.town_rights}
    # **The one preference the mod holds, checked against the game every build.**
    # It is a preference only because the game forbids the pair in one town; if a
    # patch drops that `allow`, the two stop being alternatives and the reason to
    # prefer either is gone with it.
    forbidden = excluded_rights()
    for victim, winner in PREFERRED_RIGHT.items():
        assert forbidden.get(victim) == winner or forbidden.get(winner) == victim, (
            f"the game no longer forbids {victim} beside {winner}; "
            f"`PREFERRED_RIGHT` is a ruling about a pair that has gone")
    keep = []
    # **Здание -> товары, которые оно делает в городе.** Право на лимит домиков
    # адресовано зданию (`local_fine_cloth_guild_building_levels` -- гильдии
    # портных), и товар из него выводится, а не читается: на чужое здание того
    # же товара бонус не действует, и план не должен считать иначе.
    building_goods: dict[str, set[str]] = {}
    for method in rows:
        if method.urban:
            building_goods.setdefault(method.building, set()).add(method.produced)

    for right in game.town_rights:
        only: dict[str, list[str]] = {}
        by_levels: dict[str, float] = {}
        for building, amount in right.levels.items():
            for good in building_goods.get(building, ()):
                by_levels[good] = max(by_levels.get(good, 0.0), amount)
                only.setdefault(good, []).append(building)
        favoured = {**by_levels, **right.output}
        bundle = {g: v for g, v in favoured.items() if g in made}
        # Товар, который право поднимает целиком, оговорки не получает.
        only = {g: sorted(set(bs)) for g, bs in only.items()
                if g in bundle and g not in right.output}
        if not bundle:
            continue
        # **One charter stands aside for another, and only where the owner said
        # so.** `PREFERRED_RIGHT` carries the reasoning; the rest of the game's
        # excluding pairs are a town's rule and not a country's, and the plan --
        # which gives a town one right -- can never break it.
        potential = right.potential
        winner = by_key.get(PREFERRED_RIGHT.get(right.key, ""))
        if winner is not None and winner.potential:
            gate = f"NOT = {{ {winner.potential} }}"
            potential = f"{potential} {gate}" if potential else gate
        keep.append(eu5data.TownRight(key=right.key, output=bundle, only=only,
                                      levels=right.levels, penalty=right.penalty,
                                      advance=right.advance, potential=potential))
    return keep


def rights_file(rows: list[eu5data.Method], split: dict[str, list[str]],
                game: eu5data.Game) -> str:
    """Ranking ground for a whole urban right rather than for one good.

    **A right's percentage re-ranks nothing.** `+20% books` is the same +20% in
    every location on the map, and so is the efficiency penalty eleven of the
    seventeen share: multiply every candidate by one number and the order is
    what it was. What re-ranks is the *bundle*. Eight of the nine general rights
    favour two or three goods at once and a province's RGO bonus is per good --
    it can supply lumber and not dyes -- so «where do Printing Rights go» has a
    different answer from «where do I make books», and it is the only question
    here worth a pass of its own.

    **Goods are added through their price.** Four books a level and 0.3 masonry
    a level are not one number, which is the same mistake as ranking a forest
    village above a weapon guild. `default_market_price` is the weight, so the
    total a row carries is what the ground would earn a level rather than how
    many things it would make.

    Per candidate the pass reuses the per-good scorers already generated: each
    good of the bundle in turn, the better of its built-up and village answers
    kept in a slot, the slot values summed. The winning method is resolved into
    a building and a bonus only for the provinces that take a row, because the
    dispatch over 218 methods is far too wide to run per candidate.
    """
    rights = output_rights(rows, game)
    # **The split into «everybody's» and «this country's» was two CMM lists and
    # is now one number a cell reads**, `_right_ok<n>`: the window draws every
    # right this country may ever hold, in one block, and `unlock_town_rights`
    # is no longer what decides which list a right lands in -- `potential` is
    # what decides whether it is drawn at all.
    index_of_right = {r.key: i for i, r in enumerate(rights, start=1)}
    order = [good for kind in ("raw", "made") for good in split[kind]]
    index_of = {good: i for i, good in enumerate(order, start=1)}
    by_good_index: dict[str, list[int]] = {}
    for i, method in enumerate(rows, start=1):
        by_good_index.setdefault(method.produced, []).append(i)
    slots = range(1, RIGHT_SLOTS + 1)

    out = [HEADER, """#
# The right the search answers for, and which rights this country is offered.
#
# **This was two CMM lists and their tick-parsing until 2026-09-06.** Both are
# gone with the mod page's «Товар» tab: a right is picked in the ranking window
# now, on a cell that knows its own number, exactly as a good is. What survived
# the move is the one thing the lists did that a cell cannot -- deciding whether
# this country may be shown a unique right at all -- and it is a variable per
# right now, because a window can read a variable and cannot ask a trigger.
"""]

    # Every right's circle off. One press writes one on again.
    out.append(f"""
# Scope: country
{MOD_ID}_clear_right_sel = {{
""")
    for i in range(1, len(rights) + 1):
        out.append(f"\tremove_global_variable = {MOD_ID}_rsel{i}\n")
    out.append("}\n")

    for right in rights:
        index = index_of_right[right.key]
        out.append(f"""
# {right.key}
# Scope: country
{MOD_ID}_set_right_{index} = {{
\t{MOD_ID}_clear_good_sel = yes
\t{MOD_ID}_clear_right_sel = yes
\tset_variable = {{ name = {MOD_ID}_right_index value = {index} }}
\tset_global_variable = {{ name = {MOD_ID}_right_index value = {index} }}
\tset_global_variable = {{ name = {MOD_ID}_rsel{index} value = 1 }}

\t# A good and a right are two answers to one question.
\tset_variable = {{ name = {MOD_ID}_good_index value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_good_index value = 0 }}

\t{MOD_ID}_clear_rows = yes
}}
""")

    out.append(f"""
# The right's circle from the stored answer, for the first load after the cells
# replaced the lists. Called by `{MOD_ID}_sync_sel`, which clears both blocks
# first, so this only ever writes the one that is chosen.
# Scope: country
{MOD_ID}_sync_right_sel = {{
""")
    for right in rights:
        index = index_of_right[right.key]
        keyword = "if" if index == 1 else "else_if"
        out.append(f"\t{keyword} = {{ limit = {{ var:{MOD_ID}_right_index = {index} }} "
                   f"set_global_variable = {{ name = {MOD_ID}_rsel{index} value = 1 }} }}\n")
    out.append("}\n")

    out.append(f"""
# What this country is offered, as one variable a cell can read.
#
# The nine general ones stay whatever the age: they are everybody's, one advance
# away, and this mod is for planning ahead -- hiding them until age three would
# leave a gap where the answer belongs. **A unique right is another matter.**
# Wallachia has no business being shown Constantinople's silk monopoly, and the
# game already says so: the monopoly carries
# `potential = {{ OR = {{ has_or_had_tag = BYZ has_or_had_tag = ROM }} }}`. That
# is asked here, and it is not this mod's opinion about who owns what.
#
# **A `visible` in a window cannot call a scripted trigger**, which is why this
# is an effect leaving a flag rather than a trigger the cell asks. It runs on
# the registration hook, which fires on load and again every time the mod page
# is opened.
# Scope: country
{MOD_ID}_refresh_rights = {{
""")
    for right in rights:
        index = index_of_right[right.key]
        shown = ("always = yes" if not right.potential
                 else "AND = { %s }" % right.potential)
        out.append(f"""\tif = {{
\t\tlimit = {{ {shown} }}
\t\tset_variable = {{ name = {MOD_ID}_right_ok{index} value = 1 }}
\t}}
\telse = {{
\t\tremove_variable = {MOD_ID}_right_ok{index}
\t\t# A right that is no longer offered is no longer the answer either.
\t\tif = {{
\t\t\tlimit = {{ var:{MOD_ID}_right_index = {index} }}
\t\t\t{MOD_ID}_drop_right = yes
\t\t}}
\t}}
""")
    # **And the same answer packed into slots, which is what the editor draws.**
    #
    # Его слова 2026-09-06: «я не понимаю почему ты вообще не можешь выкинуть
    # "фантомные" грамоты из окна… мод должен сначала узнать какие грамоты
    # доступны, а потом загружать доступные в окна». Он прав про механизм: ячейка
    # написана под номер грамоты, невидимая ячейка держала своё место в колонке, и
    # девять грамот из тринадцати вставали рваными столбцами.
    #
    # **Слот — это место в окне, а не грамота.** `_rslot<p>` говорит, какая грамота
    # сидит на месте p, и заполняется он подряд, без дыр. Ячейка написана под
    # *место*: имя, счётчик и обе кнопки спрашивают `_rslot<p>` и попадают в свою
    # грамоту через диспетчер. Дыр не остаётся вовсе, и строка из пяти мест
    # заполнена ровно настолько, сколько грамот держава может выдать.
    slot_reset = "".join(
        f"\tset_global_variable = {{ name = {MOD_ID}_rslot{p} value = 0 }}\n"
        f"\tremove_variable = {MOD_ID}_rslotok{p}\n"
        for p in range(1, len(rights) + 1))
    fill = "".join(
        f"\tif = {{\n"
        f"\t\tlimit = {{ has_variable = {MOD_ID}_right_ok{index_of_right[right.key]} }}\n"
        f"\t\tchange_global_variable = {{ name = {MOD_ID}_rslotn add = 1 }}\n"
        + "".join(
            f"\t\tif = {{\n"
            f"\t\t\tlimit = {{ global_var:{MOD_ID}_rslotn = {p} }}\n"
            f"\t\t\tset_global_variable = {{ name = {MOD_ID}_rslot{p} "
            f"value = {index_of_right[right.key]} }}\n"
            f"\t\t\tset_variable = {{ name = {MOD_ID}_rslotok{p} value = 1 }}\n"
            f"\t\t}}\n"
            for p in range(1, len(rights) + 1))
        + f"\t}}\n"
        for right in rights)
    out.append(f"""\t# Места пересобираются целиком: грамота, которую держава потеряла,
\t# не должна оставить за собой дыру.
{slot_reset}\tset_global_variable = {{ name = {MOD_ID}_rslotn value = 0 }}
{fill}}}
""")

    # ---- the pass -------------------------------------------------------
    out.append(f"""
# Score every candidate for the ticked right.
#
# **Возраст ставится здесь, из тумблера ЭТОГО окна.** Галочка «Считать на конец
# игры» в поиске пишет `_rank_by_end`, а покрытие раньше гейтилось на
# `_plan_by_end` -- тумблере окна плана, -- так что в поиске она не делала
# ничего.
# Scope: country
{MOD_ID}_score_right = {{
\t{MOD_ID}_cov_age_rank = yes
""")
    for index in range(1, len(rights) + 1):
        keyword = "if" if index == 1 else "else_if"
        out.append(f"\t{keyword} = {{ limit = {{ var:{MOD_ID}_right_index = {index} }} "
                   f"{MOD_ID}_score_right_{index} = yes }}\n")
    out.append("}\n")

    for index, right in enumerate(rights, start=1):
        bundle = sorted(right.output)
        pretty = ", ".join("%s +%g%%" % (g, right.output[g] * 100) for g in bundle)
        out.append(f"""
# {right.key} -- {pretty}
# Scope: country
{MOD_ID}_score_right_{index} = {{
\tsave_scope_as = {MOD_ID}_country
\tevery_in_global_list = {{
\t\tvariable = {MOD_ID}_candidates
\t\tset_variable = {{ name = {MOD_ID}_r_total value = 0 }}
\t\tset_variable = {{ name = {MOD_ID}_r_mid_total value = 0 }}
\t\t# **Чем этот поиск сортирует -- то же, чем красит карта.** Его слово,
\t\t# 2026-09-14: «функция поиска по одному городскому праву… я ожидаю, что
\t\t# она будет тоже ориентироваться по аналогии карты городских прав».
\t\t# `_rq<k>` и есть тот счёт. Кладём его на кандидата здесь, внутри обхода,
\t\t# который и так идёт: `_r_score` считается в скоупе локации, а номер
\t\t# отмеченной грамоты живёт на державе, и дотянуться туда оттуда нечем.
\t\t# Покрытие считается здесь же, до того как его прочтёт `_rq<k>`:
\t\t# доля входа требует триггера по провинции, то есть эффекта.
\t\t{MOD_ID}_cov_pass = yes
\t\tset_variable = {{ name = {MOD_ID}_r_fit value = {MOD_ID}_rq{index} }}
\t\t# **Лесенка прав и разбор в подсказке -- наши, а были карты.** В подсказке
\t\t# столбца стоял разбор CM (`_trmm_ur_rank_bd_slot_*`), а в самом столбце
\t\t# наш `_rq<k>`; сойтись они не могли -- карта не знает про эпоху, -- и на
\t\t# его экране 2026-09-14 подсказка говорила 76.1 %, а столбец 236.1 %.
\t\t{MOD_ID}_rq_park = yes
\t\t{MOD_ID}_rq_rank = yes
\t\tset_variable = {{ name = {MOD_ID}_rqsel value = {index} }}
""")
        for k in slots:
            out.append(f"\t\tset_variable = {{ name = {MOD_ID}_r_method_{k} value = 0 }}\n")
        out.append("\t}\n")

        for k, good in enumerate(bundle, start=1):
            weight = (game.prices.get(good, 1.0) * (1 + right.output[good])
                      * RIGHT_SCALE / RANK_SCALE)
            out.append(f"""
\t# {good}: price {game.prices.get(good, 1.0):g} x (1 + {right.output[good]:g})
\t{MOD_ID}_score_{index_of[good]} = yes
\tevery_in_global_list = {{
\t\tvariable = {MOD_ID}_candidates
\t\t# **A right obeys the same two buttons as a good.** «Считать» reads the
\t\t# answer available today, «На конец» the one that survives every advance.
\t\t# The twenty-second run pressed the second and got the first, because this
\t\t# read `_best_method` and nothing else.
\t\t#
\t\t# The fallbacks are the same too: a slot the ground feeds nothing keeps its
\t\t# building and its icon and says 0.00%, and `_val` stays 0, so it is worth
\t\t# nothing to the ranking and a row of nothing but those still goes.
\t\tif = {{
\t\t\tlimit = {{ NOT = {{ has_global_variable = {MOD_ID}_rank_by_end }} }}
			set_variable = {{ name = {MOD_ID}_r_method_{k} value = var:{MOD_ID}_best_method }}
			set_variable = {{ name = {MOD_ID}_r_val_{k} value = var:{MOD_ID}_best }}
			if = {{
				limit = {{ var:{MOD_ID}_best_rural > var:{MOD_ID}_best }}
				set_variable = {{ name = {MOD_ID}_r_method_{k} value = var:{MOD_ID}_best_method_rural }}
				set_variable = {{ name = {MOD_ID}_r_val_{k} value = var:{MOD_ID}_best_rural }}
			}}
			if = {{
				limit = {{ var:{MOD_ID}_r_method_{k} = 0 }}
				set_variable = {{ name = {MOD_ID}_r_method_{k} value = var:{MOD_ID}_any_best_method }}
			}}
			if = {{
				limit = {{ var:{MOD_ID}_r_method_{k} = 0 }}
				set_variable = {{ name = {MOD_ID}_r_method_{k} value = var:{MOD_ID}_any_best_method_rural }}
			}}
\t\t}}
\t\telse = {{
			set_variable = {{ name = {MOD_ID}_r_method_{k} value = var:{MOD_ID}_end_best_method }}
			set_variable = {{ name = {MOD_ID}_r_val_{k} value = var:{MOD_ID}_end_best }}
			if = {{
				limit = {{ var:{MOD_ID}_end_best_rural > var:{MOD_ID}_end_best }}
				set_variable = {{ name = {MOD_ID}_r_method_{k} value = var:{MOD_ID}_end_best_method_rural }}
				set_variable = {{ name = {MOD_ID}_r_val_{k} value = var:{MOD_ID}_end_best_rural }}
			}}
			if = {{
				limit = {{ var:{MOD_ID}_r_method_{k} = 0 }}
				set_variable = {{ name = {MOD_ID}_r_method_{k} value = var:{MOD_ID}_end_any_best_method }}
			}}
			if = {{
				limit = {{ var:{MOD_ID}_r_method_{k} = 0 }}
				set_variable = {{ name = {MOD_ID}_r_method_{k} value = var:{MOD_ID}_end_any_best_method_rural }}
			}}
\t\t}}
\t\t# And the road there, summed the same way. It only ever breaks a tie, and
\t\t# the ties it breaks are the ones «На конец» leaves: where nothing that
\t\t# survives can be fed, every province in the table is worth exactly zero.
\t\tset_variable = {{ name = {MOD_ID}_r_mid_{k} value = var:{MOD_ID}_mid_best }}
\t\tif = {{
\t\t\tlimit = {{ var:{MOD_ID}_mid_best_rural > var:{MOD_ID}_mid_best }}
\t\t\tset_variable = {{ name = {MOD_ID}_r_mid_{k} value = var:{MOD_ID}_mid_best_rural }}
\t\t}}
\t\tchange_variable = {{ name = {MOD_ID}_r_mid_{k} multiply = {weight:.4f} }}
\t\tchange_variable = {{ name = {MOD_ID}_r_mid_total add = var:{MOD_ID}_r_mid_{k} }}
\t\tchange_variable = {{ name = {MOD_ID}_r_val_{k} multiply = {weight:.4f} }}
\t\tchange_variable = {{ name = {MOD_ID}_r_total add = var:{MOD_ID}_r_val_{k} }}
\t}}
""")
        out.append("}\n")

    # ---- resolving one winning method into what a row prints ------------
    out.append(f"""
# One method, read out of `{MOD_ID}_w_method` into scratch. A dispatch over every
# method in the game is too wide to run per candidate, so it runs only for the
# provinces that took a row -- fifty of them, three slots each.
# Scope: location
{MOD_ID}_store_scratch = {{
\tclear_variable_list = {MOD_ID}_w_goods
\tremove_variable = {MOD_ID}_w_bt
\tremove_variable = {MOD_ID}_w_pm
\tset_variable = {{ name = {MOD_ID}_w_bonus value = 0 }}
\tset_variable = {{ name = {MOD_ID}_w_out value = 0 }}
\tset_variable = {{ name = {MOD_ID}_w_goods_all value = 0 }}
""")
    for i, method in enumerate(rows, start=1):
        raw = sorted(method.raw_inputs(game.raw_goods))
        out.append(f"\tif = {{\n"
                   f"\t\tlimit = {{ var:{MOD_ID}_w_method = {i} }}\n"
                   f"\t\tset_variable = {{ name = {MOD_ID}_w_bt value = building_type:{method.building} }}\n"
                   f"\t\tset_variable = {{ name = {MOD_ID}_w_pm value = production_method:{method.parts[0].key} }}\n"
                   f"\t\tset_variable = {{ name = {MOD_ID}_w_bonus value = {MOD_ID}_b{i} }}\n"
                   f"\t\tset_variable = {{ name = {MOD_ID}_w_out value = {method.output:.4f} }}\n"
                   f"\t\tset_variable = {{ name = {MOD_ID}_w_goods_all value = {len(raw)} }}\n")
        for good in raw:
            out.append(f"""\t\tif = {{
\t\t\tlimit = {{ province_definition = {{ any_location_in_province_definition = {{ raw_material = goods:{good} }} }} }}
\t\t\tadd_to_variable_list = {{ name = {MOD_ID}_w_goods target = goods:{good} }}
\t\t}}
""")
        out.append("\t}\n")
    out.append("}\n")

    for k in slots:
        out.append(f"""
# Scratch into slot {k}.
# Scope: location
{MOD_ID}_slot_{k}_from_scratch = {{
\tclear_variable_list = {MOD_ID}_r_goods_{k}
\tremove_variable = {MOD_ID}_r_bt_{k}
\tremove_variable = {MOD_ID}_r_pm_{k}
\tset_variable = {{ name = {MOD_ID}_r_bonus_{k} value = 0 }}
\tset_variable = {{ name = {MOD_ID}_r_out_{k} value = 0 }}
\tset_variable = {{ name = {MOD_ID}_r_goods_all_{k} value = 0 }}
\tif = {{
\t\tlimit = {{ has_variable = {MOD_ID}_w_bt }}
\t\tset_variable = {{ name = {MOD_ID}_r_bt_{k} value = var:{MOD_ID}_w_bt }}
\t\tset_variable = {{ name = {MOD_ID}_r_pm_{k} value = var:{MOD_ID}_w_pm }}
\t\tset_variable = {{ name = {MOD_ID}_r_bonus_{k} value = var:{MOD_ID}_w_bonus }}
\t\tset_variable = {{ name = {MOD_ID}_r_out_{k} value = var:{MOD_ID}_w_out }}
\t\tset_variable = {{ name = {MOD_ID}_r_goods_all_{k} value = var:{MOD_ID}_w_goods_all }}
\t\tevery_in_list = {{
\t\t\tvariable = {MOD_ID}_w_goods
\t\t\tprev = {{ add_to_variable_list = {{ name = {MOD_ID}_r_goods_{k} target = prev }} }}
\t\t}}
\t}}
}}
""")

    # Which good sits in which slot, per right -- the row prints its name.
    out.append(f"""
# The goods of the ticked right, parked on the winning location so the row can
# name them. Written per row rather than per candidate, like everything else
# here.
# Scope: location
{MOD_ID}_store_right_goods = {{
""")
    for index, right in enumerate(rights, start=1):
        bundle = sorted(right.output)
        out.append(f"\tif = {{\n\t\tlimit = {{ global_var:{MOD_ID}_right_index = {index} }}\n")
        for k in slots:
            if k <= len(bundle):
                out.append(f"\t\tset_variable = {{ name = {MOD_ID}_r_good_{k} value = goods:{bundle[k - 1]} }}\n")
            else:
                out.append(f"\t\tremove_variable = {MOD_ID}_r_good_{k}\n")
        out.append("\t}\n")
    out.append("}\n")

    out.append(f"""
# Park the whole answer for one province, slot by slot.
# Scope: location
{MOD_ID}_store_right_row = {{
""")
    for k in slots:
        out.append(f"""\tset_variable = {{ name = {MOD_ID}_w_method value = var:{MOD_ID}_r_method_{k} }}
\t{MOD_ID}_store_scratch = yes
\t{MOD_ID}_slot_{k}_from_scratch = yes
""")
    out.append(f"""\t{MOD_ID}_store_right_goods = yes
\t# What the row prints: the ranking number back in the unit it names, which is
\t# what one level of the whole bundle would earn here.
\tset_variable = {{ name = {MOD_ID}_r_value value = var:{MOD_ID}_r_total }}
\tchange_variable = {{ name = {MOD_ID}_r_value divide = {RIGHT_SCALE} }}
}}

# The ranking pass for a right. One row per province definition, as for a good,
# and the same fifty.
# Scope: country
{MOD_ID}_fill_rows_right = {{
\tordered_in_global_list = {{
\t\tvariable = {MOD_ID}_candidates
\t\torder_by = {MOD_ID}_r_score
\t\tmax = {RESULT_ROWS * 8}
\t\tcheck_range_bounds = no
\t\t{MOD_ID}_store_right_row_if_worth_it = yes
\t}}
}}

# Scope: location
{MOD_ID}_store_right_row_if_worth_it = {{
\tif = {{
\t\tlimit = {{
\t\t\tglobal_var:{MOD_ID}_found < {RESULT_ROWS}
\t\t\t# Nothing in the bundle can be made here at all.
\t\t\tvar:{MOD_ID}_r_total > 0
\t\t\tNOT = {{ has_variable = {MOD_ID}_row_taken }}
\t\t}}
\t\tprovince_definition = {{
\t\t\tevery_location_in_province_definition = {{
\t\t\t\tset_variable = {{ name = {MOD_ID}_row_taken value = 1 }}
\t\t\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_row_taken_locations target = this }}
\t\t\t}}
\t\t}}
\t\t# The winners are parked before the province is judged: «is this ground
\t\t# worth a row» is a question about the bonuses, and a bonus is not known
\t\t# until the method that won it is.
\t\t{MOD_ID}_store_right_row = yes
\t\tif = {{
\t\t\tlimit = {{ {MOD_ID}_right_row_is_worth_it = yes }}
\t\t\tchange_global_variable = {{ name = {MOD_ID}_found add = 1 }}
\t\t\tset_variable = {{ name = {MOD_ID}_rank value = global_var:{MOD_ID}_found }}
\t\t\tadd_to_global_variable_list = {{ name = {MOD_ID}_ranked target = this }}
\t\t}}
\t}}
}}
""")
    return "".join(out)


def list_settings(by_continent) -> list[tuple[str, str, str, bool]]:
    """Every list this mod registers: tab, id, what a tick runs, folded at first.

    One table, two readers -- the `_on_changed` callbacks and the collapse pass
    below both have to name every list, and a list named in one and not the
    other is the kind of omission nothing reports. **It went unreported for two
    builds**: the mod list was registered without being named here, so it had no
    `_on_changed`, and CMM draws a list row only while that GUI is shown. The
    group header rendered, the list under it did not, and nothing logged
    anything (`check_script.py` catches it now).
    """
    return ([("zone", f"region_{c}", f"{MOD_ID}_zone_changed = yes", True)
             for c in by_continent]
            + [("zone", "continent", f"{MOD_ID}_zone_changed = yes", True),
               # Один мод в списке -- не повод сворачивать: свёрнутый он выглядит
               # ровно как пустой, а пустым он и был.
               ("tech", "source", f"{MOD_ID}_rebuild_sources = yes", False)])


def layout_file(by_continent) -> str:
    """The pickers, folded shut the first time the mod page is built.

    Seven region lists and two goods lists, all open, is a page the owner scrolls
    through to reach anything -- and the answer he wants is two ticks in it.
    CMM keeps a group's folded state in `cmm_group_collapsed`, a variable map on
    the player keyed by `<mod>__<tab>__<group>`, and a list is filed under a
    group named after itself, so the key is knowable from here. `_on_changed`'s
    table is the same table, which is why both read `list_settings`.

    **This writes into CMF's own data, which no macro covers.** The map is
    documented in `cmm_settings_pane.gui` as what the header button toggles, and
    CMM_ToggleGroupCollapsed writes it exactly this way; it is a contract with a
    comment rather than with a macro, and a CMF that renames it would leave the
    groups open rather than break anything.

    Once, and then never again: `bag_wtp_folded_once` is what makes it a default
    rather than a decision retaken at every save load.
    """
    out = [HEADER, f"""#
# Scope: country
{MOD_ID}_fold_pickers = {{
\tif = {{
\t\tlimit = {{ NOT = {{ has_variable = {MOD_ID}_folded_once }} }}
\t\tset_variable = {{ name = {MOD_ID}_folded_once value = 1 }}
"""]
    for tab, setting, _, fold in list_settings(by_continent):
        if not fold:
            continue
        out.append(f"\t\tadd_to_variable_map = {{ name = cmm_group_collapsed "
                   f"key = flag:{MOD_ID}__{tab}__{setting} value = 1 }}\n")
    out.append("\t}\n}\n")
    return "".join(out)


def guis_file(by_continent) -> str:
    """One `_on_changed` per list, and they are not optional.

    Registering a list marks the setting as having a scripted GUI, and CMM then
    draws the row only while `CMMGuiIsShown('<setting>_on_changed')`. Without one
    the whole widget is hidden, header included -- and because a list is filed
    under a group named after itself, the group header still renders, so a
    missing callback looks like an empty list rather than a missing one.
    """
    out = [HEADER, """#
# A list reaches nothing but its own `_on_changed`: bool, dropdown, numeric,
# slider and button settings auto-apply and reach `cmf_on_callback`, and a list
# reaches neither until `cmm_apply_list_change` is called here.
"""]
    for _, setting, after, _fold in list_settings(by_continent):
        body = f"\t\t{after}\n" if after else ""
        out.append(f"""
{MOD_ID}__{setting}_on_changed = {{
\tscope = country

\tis_shown = {{
\t\talways = yes
\t}}

\teffect = {{
\t\tcmm_apply_list_change = {{
\t\t\tsetting = {MOD_ID}__{setting}
\t\t}}
{body}\t}}
}}
""")
    return "".join(out)


def loc_file(language: str, rows: list[eu5data.Method], split: dict[str, list[str]],
             game: eu5data.Game) -> str:
    """The generated keys, identical in every language.

    Every name in here is the game's own, reached through `$key$` substitution or
    a data function, so this file needs no translating and cannot drift from what
    the game calls things.

    The fifty result-row keys are gone with the table they labelled: the window
    reads its row off the location's own scope and needs no key per row.
    """
    out = [f"l_{language}:\n"]

    # **Имя мода-источника, как его пишет он сам.** Строка списка в настройках
    # берёт своё имя из флага, а флаг -- ключ локализации; имя читается из
    # `.metadata/metadata.json` того мода, чтобы в настройках стояло то, что
    # игрок видит в лаунчере.
    used = sorted({source_of(m.building) for m in rows} - {0})
    named = {n: (folder, name) for n, (folder, name, _c)
             in enumerate(refs.mod_sources(), start=1)}
    for number in used:
        folder, name = named[number]
        out.append(f' {MOD_ID}_src_{folder}: "{name}"\n')

    for kind in ("raw", "made"):
        for good in split[kind]:
            out.append(f" {MOD_ID}_good_{good}: "
                       f'"@{good}! [ShowGoodsName(\'{good}\')]"\n')

    # **The picker's cell: the good's icon and how many buildings of it stand on
    # the ground.** He asked for the number three times -- «Я до сих пор не вижу
    # в редакторе сколько домиков какова вида стоит сейчас» -- and it could not
    # be drawn while the cells came from a datamodel, because a goods scope
    # reaches no numbered counter. A written cell reads `_pn<n>` straight.
    #
    # A texticon in a localization value is the game's own way of drawing a good
    # (`hint_eco_hint_text_2`), and it needs no scope at all -- which is the
    # whole reason the cell can be static.
    for i, good in enumerate(goods_order(split), start=1):
        out.append(f" {MOD_ID}_cell_{i}: "
                   f'"@{good}! [GuiScope.SetRoot(GetPlayer.MakeScope)'
                   f".ScriptValue('{MOD_ID}_show_pn{i}')|0]\"\n")
        # **The same cell once the good is pinned, marked with a character and
        # not a colour.** It was `#Y …#!` and he had already said what he
        # wanted: «добавлять какой-то символ к цифре и всё, он будет мне виден
        # и понятен, есть там замок или нет» — twice, before and after the
        # colour went in. A `*` is ASCII, so unlike `✔` there is no question
        # whether the font has it, and unlike a colour it survives being
        # printed, screenshotted and looked at sideways.
        out.append(f" {MOD_ID}_cell_pin_{i}: "
                   f'"@{good}! [GuiScope.SetRoot(GetPlayer.MakeScope)'
                   f".ScriptValue('{MOD_ID}_show_pn{i}')|0]*\"\n")

    # **Ячейка деревни -- значок и счётчик, ровно как у товара.** Его слово
    # 2026-09-13: «нет иконок, нужно добавить. Не нужно писать название, нужна
    # только иконка, аналогично как с простыми товарами. Таких домиков может
    # быть очень много в модах».
    #
    # **Значок здания достаётся только через переменную.** У товара есть
    # тексикона `@wheat!`, у здания её нет, а превратить строку в тип здания в
    # интерфейсе нечем: глобального промоута из имени в `BuildingType` в дампах
    # игры нет вовсе. Поэтому `_vbt<k>` -- глобалка с самим типом, поставленная
    # при регистрации, и значок берётся с неё.
    for k, building in enumerate(village_entities(rows, split, game), start=1):
        b = shared_buildings(rows, split, game).index(building) + 1
        out.append(f" {MOD_ID}_cell_{len(goods_order(split)) + k}: "
                   f"\"[GetGlobalVariable('{MOD_ID}_vbt{k}').GetBuildingType.GetIcon] "
                   f"[GuiScope.SetRoot(GetPlayer.MakeScope)"
                   f".ScriptValue('{MOD_ID}_show_bn{b}')|0]\"\n")

    # **Строка сводки: пять чисел и ни одного слова.** Слова стоят в заголовках
    # столбцов, поэтому сами клетки одинаковы на всех языках и живут здесь.
    for i, good in enumerate(goods_order(split), start=1):
        sv = f"[GuiScope.SetRoot(GetPlayer.MakeScope).ScriptValue('{MOD_ID}_show_%s{i}')|0]"
        # **`#Y ` со своим пробелом, а не `#Y[`.** Разметка игры отделяет тег
        # от текста пробелом -- 652 её собственных ключа, и ни одного без него.
        # **Столбец «Всего» -- это домики плюс РГО, и он такой с 2026-09-07.**
        # Владелец: «показывай сразу со счётчиком РГО, чтобы оно складывалось в
        # итоге в адекватные цифры»; сами домики видны в столбце «город / село»,
        # а РГО -- в своём.
        out.append(f' {MOD_ID}_sum_n_{i}: "#Y {sv % "tot"}#!"\n')
        # **Чистое число домиков и стороны по отдельности.** «Всего» — это
        # домики плюс РГО; чтобы видеть, что из чего сложилось, рядом стоят три
        # числа без РГО: сколько построено всего, сколько в городах, сколько в
        # сёлах.
        # **Потолки сторон — то, к чему домик стремится в городе и в селе.**
        # Его слова 2026-09-08: «я не вижу, к какому лимиту стремятся домики
        # отдельно в городах и отдельно в сёлах».
        out.append(f' {MOD_ID}_sum_qt_{i}: "{sv % "pqt"}"\n')
        out.append(f' {MOD_ID}_sum_qr_{i}: "{sv % "pqr"}"\n')
        out.append(f' {MOD_ID}_sum_nb_{i}: "{sv % "pn"}"\n')
        out.append(f' {MOD_ID}_sum_town_{i}: "{sv % "pnt"}"\n')
        out.append(f' {MOD_ID}_sum_rural_{i}: "{sv % "pnr"}"\n')
        out.append(f' {MOD_ID}_sum_places_{i}: "{sv % "ng"}"\n')
        # **РГО отдельным столбцом, потому что он объясняет почти каждое
        # «почему у него меньше».** Доля товара -- это доля земли минус одно за
        # каждое своё РГО, и без этого числа строка выглядит просто урезанной.
        out.append(f' {MOD_ID}_sum_rgo_{i}: "{sv % "nrgo"}"\n')
        # **Доля до скидки и после.** Его вопрос 2026-09-08: «что это блядь за
        # доля? С рго, без рго?». Теперь обе стоят рядом, и «без РГО» -- это
        # ровно три числа на всю таблицу: доля города, доля села и их сумма
        # для тех, кто умеет обе стороны.
        out.append(f' {MOD_ID}_sum_qraw_{i}: "{sv % "pqraw"}"\n')
        # **«19-1» вместо «19», и это два готовых значения, а не одно с
        # условием.** Выбор между ними делает `{MOD_ID}_quota_<i>` -- диспетчер
        # той же формы, что «почему остановился» в этом же окне. Условие внутри
        # значения (`SelectLocalization` с вложенным сравнением) сломало столбец
        # целиком, 2026-09-09; **и цвета здесь нет намеренно** -- «ломаешь ты
        # цветом что-то почти всегда».
        out.append(f' {MOD_ID}_sum_quotaA_{i}: "{sv % "pq"}-{sv % "short"}"\n')
        out.append(f' {MOD_ID}_sum_quotaB_{i}: "{sv % "pq"}"\n')
        out.append(f' {MOD_ID}_sum_gain_{i}: "{sv % "gain"}%"\n')

    # **The search picker's cell: the good's icon and nothing else.** Forty-seven
    # names side by side would be four windows wide, so the name is the tooltip
    # and `{MOD_ID}_good_<good>` above is what it draws.
    for i, good in enumerate(goods_order(split), start=1):
        out.append(f" {MOD_ID}_pick_{i}: \"@{good}!\"\n")

    # A right is named by the game and iconed by the first good it favours, so
    # this needs no translating either.
    for right in output_rights(rows, game):
        icon = sorted(right.output)[0]
        out.append(f" {MOD_ID}_right_{right.key}: "
                   f'"@{icon}! [ShowTownRightsName(\'{right.key}\')]"\n')

    # **How many towns hold this charter**, in its own cell in the editor, for
    # the same reason the goods cells carry `_pn<n>`: «мне нужно видеть в
    # редакторе сколько домиков какова вида стоит сейчас», and a charter is the
    # same question asked of towns.
    for k, right in enumerate(output_rights(rows, game), start=1):
        out.append(f" {MOD_ID}_edit_rcount_{k}: "
                   f'"[GuiScope.SetRoot(GetPlayer.MakeScope)'
                   f".ScriptValue('{MOD_ID}_show_rgiven{k}')|0]\"\n")

    # ---- разбор покрытия: лесенка прав и «с чего бы 100 %» -----------------
    #
    # **Слова здесь -- только ссылки `$ключ$`**, потому что этот файл одинаков
    # во всех языках: всё, что он печатает, -- имена самой игры и числа. Три
    # подписи (`_cov_of`, `_cov_mod`, `_cov_none`) лежат в
    # `bag_wtp_l_<язык>.yml` рядом с остальным человеческим текстом.
    ref = "$%s"   # ссылка на другой ключ; в f-строке скобку доллара проще так

    out.append(' %s_cov_no_method: "%s"\n'
               % (MOD_ID, ref % (MOD_ID + "_cov_none$")))

    # Одна строка на способ: здание, способ и «сырья n из d».
    #
    # **Сырьё поимённо здесь не печатается, и это его слово**: значки сырья и
    # то же `n/d` уже стоят в самой строке результата
    # (`_right_goods_count_<k>` и датамодель `_r_goods_<k>`), так что подсказка
    # повторяла бы строку. «Какой ещё чип? Ты чё?» -- 2026-09-14.
    for mi, method in enumerate(rows, start=1):
        if method.produced not in COV_GOODS or not method.inputs:
            continue
        raws = [r for r in sorted(method.inputs) if r in game.raw_goods]
        if not raws:
            continue
        # **`Method.key` -- это склейка частей через `+`, а не имя из игры.**
        # Один рецепт может состоять из нескольких способов (`base+improvement`),
        # и `ShowProductionMethodName` на склейке пишет в `error.log`
        # «unknown db name definition from loc/ux
        # 'wool_weavers_maintenance+base_fine_cloth_guild_maintenance'» -- в его
        # логе 2026-09-14 это 3 077 строк, по одной на кадр отрисовки, а на
        # экране вместо имени стояло `ERROR`. Печатаем части поимённо, и каждую
        # -- ссылкой `$ключ$`, а не запросом в базу: ключ у них есть
        # (`goods_l_<язык>.yml` самой игры), а определения может не быть.
        names = ", ".join(ref % (part.key + "$") for part in method.parts)
        # **Одна строка на товар, а не две.** Его слово 2026-09-14: «читается
        # очень сложно, идут как будто бы одним смешанным списком». Здание и
        # способ дописываются к строке товара, а не начинают свою.
        out.append(
            f' {MOD_ID}_covm_{mi}: " — [ShowBuildingTypeName(\'{method.building}\')]'
            f', {names} '
            f'[Location.MakeScope.GetVariable(\'{MOD_ID}_covn_{method.produced}\').GetValue|0]'
            f'/[Location.MakeScope.GetVariable(\'{MOD_ID}_covd_{method.produced}\').GetValue|0]"\n')

    # Строка товара в разборе: товар, его покрытие и чем оно взято.
    for good in sorted(COV_GOODS):
        out.append(
            f' {MOD_ID}_cov_line_{good}: "\\n  @{good}! [ShowGoodsName(\'{good}\')]: '
            f'[Location.MakeScope.GetVariable(\'{MOD_ID}_cov_{good}\').GetValue|%1]'
            f'[Location.Custom(\'{MOD_ID}_cov_why_{good}\')]"\n')

    # Строка грамоты в лесенке: её имя со значком (ключ уже есть) и наш процент.
    for k, right in enumerate(output_rights(rows, game), start=1):
        line = (f'\\n{ref % (MOD_ID + "_right_" + right.key + "$")}: '
                f'[Location.MakeScope.GetVariable(\'{MOD_ID}_rqv{k}\').GetValue|%1]')
        out.append(f' {MOD_ID}_rq_line_{k}: "{line}"\n')
        # В разборе то же имя, но с пустой строкой перед ним: три права подряд
        # без неё читались одним списком.
        # **Разбор начинается с имени права**: их теперь три подряд, и без имени
        # они слиплись бы в одну кучу товаров.
        # **`$ключ$`, а не `Custom()`.** Строка товара -- обычный ключ
        # локализации; `Custom()` зовёт `customizable_localization`, которого с
        # этим именем больше нет. Перепутать их -- напечатать имя ключа вместо
        # текста; ловит `unresolved_localization_refs`.
        bd = "".join(ref % (MOD_ID + "_cov_line_" + g + "$")
                     for g in sorted(right.output) if g in COV_GOODS)
        out.append(f' {MOD_ID}_rq_bd_{k}: "\\n{line}{bd}"\n')

    return "".join(out)


# ---------------------------------------------------------------- the diagnosis

def diag_file(rows: list[eu5data.Method], split: dict[str, list[str]],
              game: eu5data.Game,
              core_rows: list[eu5data.Method] | None = None) -> str:
    """«Диагностика»: one press, everything the mod knows, as text in the log.

    **This is an instrument, not a fix.** Four of the owner's runs went on four
    theories about one symptom and none of them on a measurement
    (`docs/pitfalls/diagnosis.md`); the rule that came out of it is that a cause
    nobody can name is measured rather than guessed. So this reads state and
    writes none of the plan's own, and every number it prints is uncompressed:
    a screenshot has to be read off pixels and a column has one cell, but text
    has no width.

    **It costs the plan nothing.** Everything except the per-pass counters is
    read back afterwards from what the plan parked on the locations, so the
    expensive button is exactly as expensive as it was and this one is pressed
    when there is something to look at.

    Four things about `debug_log` were measured on 2026-09-02 and all four shape
    this file:

    - `debug_log` writes on a normal build. So does `error_log`; the headline
      goes to both and the detail to `debug.log` alone, which halves a dump that
      the owner has to paste into a chat.
    - a global is reachable from the string, as
      `[GuiScope.SetRoot(GetPlayer.MakeScope).ScriptValue('<sv>')|0]`;
    - **the item a walk is standing on is not reachable at all** -- `THIS.MakeScope`
      fails and the bracket is echoed literally -- so every number is parked in
      one of fourteen scratch globals first and printed from there, and
      `debug_log_scopes` names the row;
    - and a script value of the form `value = 0` with `if = { ... add = ... }`
      reads zero in silence. Every reader here is `value = global_var:x` and
      every guard is in an effect, where `if` demonstrably works.
    """
    order = [good for kind in ("raw", "made") for good in split[kind]]
    kinds = {good: kind for kind in ("raw", "made") for good in split[kind]}
    groups = plan_groups(rows, split, game)
    last = endgame(rows, game)
    rights = output_rights(rows, game)
    # The unmerged rights, for the advance each one carries. `output_rights`
    # rewrites `potential` and the advance is not on its side of that.
    by_key = {r.key: r for r in game.town_rights}

    def read(slot: int) -> str:
        """One number, as the string sees it."""
        return f"[GuiScope.SetRoot(GetPlayer.MakeScope).ScriptValue('{MOD_ID}_dg{slot}')|0]"

    def park(slot: int, source: str, scope: str = "global", tab: str = "\t") -> str:
        """Copy a number into a scratch global, or leave 0 where there is none.

        The guard is an `if` in an effect and not a fallback inside a script
        value: the value form that guards itself reads zero in silence, which is
        how the first dump reported nothing on a plan that had placed 417
        buildings.
        """
        has = {"global": f"has_global_variable = {source}",
               "var": f"has_variable = {source}"}[scope]
        get = {"global": f"global_var:{source}", "var": f"var:{source}"}[scope]
        return (f"{tab}set_global_variable = {{ name = {MOD_ID}_dv{slot} value = 0 }}\n"
                f"{tab}if = {{ limit = {{ {has} }} "
                f"set_global_variable = {{ name = {MOD_ID}_dv{slot} value = {get} }} }}\n")

    def flag(slot: int, trigger: str, tab: str = "\t") -> str:
        """1 or 0 for something that is a condition rather than a number."""
        return (f"{tab}set_global_variable = {{ name = {MOD_ID}_dv{slot} value = 0 }}\n"
                f"{tab}if = {{ limit = {{ {trigger} }} "
                f"set_global_variable = {{ name = {MOD_ID}_dv{slot} value = 1 }} }}\n")

    def say(text: str, both: bool = False, tab: str = "\t") -> str:
        """One line into the log, and **exactly one**.

        `error_log` writes into `debug.log` as well as `error.log` -- measured
        2026-09-02, when every line marked "both sinks" arrived in the report
        twice. So the detail goes to `debug_log` alone and `error.log` gets one
        pointer, at the top, saying where the report is.

        `both` is kept in the signature because a line worth duplicating may come
        back; today nothing sets it.
        """
        line = f'{tab}debug_log = "WTP {text}"\n'
        if both:
            line += f'{tab}error_log = "WTP {text}"\n'
        return line

    out = [f"""#
# «Диагностика» -- one press, everything the mod knows, as text.
#
# Generated. What it prints and why each block is here:
# `docs/pitfalls/diagnosis.md`. **No `[THIS...]` anywhere below**: a `debug_log`
# string cannot reach the item a walk stands on. Numbers come from the sixteen
# `_dv` scratch globals through the `_dg` readers; names are baked in here.
#
# Scope: country
{MOD_ID}_diag = {{
"""]
    out.append("".join(f"\tset_global_variable = {{ name = {MOD_ID}_dv{i} value = 0 }}\n"
                       for i in range(1, DIAG_SCRATCH + 1)))
    # **Кнопка должна сама сказать, что она сработала.** 2026-09-02: он нажал её
    # и не увидел ничего -- отчёт ушёл в лог, а на экране не изменилось ничто, и
    # это неотличимо от кнопки, которая не работает. Счётчик нажатий и итоги
    # сбора печатаются в её собственном описании, тем же способом, каким это
    # делают «Считать» и «План».
    out.append(f"\tif = {{ limit = {{ NOT = {{ has_global_variable = {MOD_ID}_diag_runs }} }} "
               f"set_global_variable = {{ name = {MOD_ID}_diag_runs value = 0 }} }}\n")
    out.append(f"\tchange_global_variable = {{ name = {MOD_ID}_diag_runs add = 1 }}\n")
    out.append("\tdebug_log_date = yes\n")
    out.append(f'\terror_log = "WTP the report is in debug.log, tag WTP, '
               f'version {DIAG_VERSION}. mods.bat -> «Забрать диагностику из игры» takes it out."\n')
    out.append(say(f"==== BEGIN v{DIAG_VERSION} ==== everything to the next END is one "
                   "press. Take it out with mods.bat -> «Забрать диагностику из игры», or tools/diag.py."))
    out.append(f"""\t{MOD_ID}_diag_build = yes
\t{MOD_ID}_diag_state = yes
\t{MOD_ID}_diag_scan = yes
\t{MOD_ID}_diag_goods = yes
\t{MOD_ID}_diag_laps = yes
\t{MOD_ID}_diag_rights = yes
\t{MOD_ID}_diag_locations = yes
\t{MOD_ID}_diag_ranking = yes
\t{MOD_ID}_diag_shuffle = yes
""")
    out.append(say(f"==== END v{DIAG_VERSION} ===="))
    out.append("}\n")

    # ---------------------------------------------------------------- the build
    #
    # What the generator decided, so a number in the log is never read against
    # the wrong constant. All of it static: nothing here can go stale between
    # the rebuild and the run.
    rural = sum(1 for m in rows if m.building_category in RURAL_CATEGORIES)
    bands = "/".join(str(b) for b in PLAN_BANDS)
    # Ступени печатаются процентами: числа — это пол, а не сама ступень.
    tiers = "/".join("%g%%" % (100 / d) for d in TIER_DIVISORS) + \
        " floors " + "/".join(str(t) for t in PLAN_TIERS)
    out.append(f"""
# The generator's own numbers. Static, so that a reading is never checked
# against the wrong constant.
# Scope: country
{MOD_ID}_diag_build = {{
""")
    out.append(say(f"BUILD methods={len(rows)} rural={rural} goods={len(order)} "
                   f"raw={len(split['raw'])} made={len(split['made'])} "
                   f"rights={len(rights)} gated={len(UNLOCKS)}"))
    out.append(say(f"BUILD laps={PLAN_LAPS} rungs={len(PLAN_RUNGS)} bands={bands} "
                   f"tiers={tiers} rows={PLAN_ROWS} ranked={PLAN_RANKED} "
                   f"result_rows={RESULT_ROWS} "
                   f"rank_scale={RANK_SCALE} right_slots={RIGHT_SLOTS}"))
    out.append(say("BUILD rungs in order: "
                   + ", ".join(f"{i}={rung_name(band, tier)}"
                               for i, (band, tier) in enumerate(PLAN_RUNGS, start=1))))
    # **Two self-tests, and there were four.** The other two asked what else a
    # `debug_log` string resolves, and the 2026-09-02 run answered both: a
    # localization key comes out as the key, and `ROOT.GetName` / `SCOPE.GetName`
    # do not exist ("Could not find data system function 'GetName'"). They are in
    # `docs/research/engine.md` now and out of here. What is left is the canary --
    # if this number is not 12345 nothing below it can be believed -- and the one
    # that names the scope, which every row depends on.
    out.append(f"\tset_global_variable = {{ name = {MOD_ID}_dv1 value = 12345 }}\n")
    out.append(say(f"SELFTEST 1 global-through-player={read(1)} (expect 12345; "
                   "anything else and every number below is wrong)"))
    out.append("\tdebug_log_scopes = no\n")
    out.append(say("SELFTEST 2 the line above this one names the country -- that is "
                   "debug_log_scopes, and it is how every row below says which "
                   "location it is"))
    out.append("}\n")

    # ---------------------------------------------------------------- the state
    out.append(f"""
# Everything chosen and everything the last plan counted. **A zero here is an
# answer**: pressed before a plan it prints zeros throughout, which says the pass
# never ran rather than that it found nothing.
# Scope: country
{MOD_ID}_diag_state = {{
""")
    for slot, (name, source, scope) in enumerate((
            ("good", f"{MOD_ID}_good_index", "var"),
            ("right", f"{MOD_ID}_right_index", "var"),
            ("continents", f"{MOD_ID}_zone_count", "global"),
            ("regions", f"{MOD_ID}_region_count", "global"),
            ("picked", f"{MOD_ID}_picked_count", "global"),
            ("provinces_picked", f"{MOD_ID}_browse_count", "global"),
            ("candidates", f"{MOD_ID}_candidate_count", "global"),
            ("runs", f"{MOD_ID}_live_runs", "global")), start=1):
        out.append(park(slot, source, scope))
    out.append(say("PICK good=%s right=%s continents=%s regions=%s picked=%s "
                   "provinces_picked=%s candidates=%s runs=%s"
                   % tuple(read(i) for i in range(1, 9))))
    for slot, (name, source) in enumerate((
            ("cap_rural", f"{MOD_ID}_plan_cap_rural"),
            ("cap_urban", f"{MOD_ID}_plan_cap_urban")), start=1):
        out.append(park(slot, source))
    out.append(flag(3, f"has_global_variable = {MOD_ID}_plan_rights"))
    out.append(flag(4, f"has_global_variable = {MOD_ID}_plan_by_end"))
    out.append(flag(5, f"has_global_variable = {MOD_ID}_rank_by_end"))
    # `buildable_only` was the sixth of these and is gone with the tick itself,
    # 2026-09-06.
    out.append(say("SET cap_rural=%s cap_urban=%s rights=%s "
                   "plan_by_end=%s rank_by_end=%s"
                   % tuple(read(i) for i in range(1, 6))))
    # **`ranked_provs` read `{MOD_ID}_found` for three builds**, which is the
    # single-good *ranking*'s province count and has nothing to do with a plan:
    # every report of 2026-09-03 printed `ranked_provs=0` beside `provs=8`,
    # because no ranking had been asked for. The number the line means is
    # `_plan_prov_n`, how many provinces `_plan_rank` put in order -- and a
    # province past `PLAN_PROVS` keeps the 9999 the reset gave it, so the two
    # differing is the one way that cap can be seen.
    for slot, source in enumerate((
            f"{MOD_ID}_plan_placed", f"{MOD_ID}_plan_rooms", f"{MOD_ID}_plan_found",
            f"{MOD_ID}_plan_shown", f"{MOD_ID}_plan_towns", f"{MOD_ID}_plan_provn",
            f"{MOD_ID}_plan_scored", f"{MOD_ID}_plan_quota", f"{MOD_ID}_plan_rightn",
            f"{MOD_ID}_plan_laps", f"{MOD_ID}_plan_prov_n",
            f"{MOD_ID}_plan_opensw", f"{MOD_ID}_rquota", f"{MOD_ID}_rlevel",
            f"{MOD_ID}_plan_lvl", f"{MOD_ID}_plan_mode"), start=1):
        out.append(park(slot, source))
    # `rquota` is the towns each charter may end with, `rlevels` how many heights
    # the ladder actually climbed to. The two apart is the guard having cut it
    # short -- the one thing about the charter round that leaves no other trace.
    out.append(say("PASS placed=%s rooms=%s used_locs=%s drawn=%s towns=%s provs=%s "
                   "goods_scored=%s quota=%s rights_given=%s laps=%s "
                   "ordered_provs=%s dry_laps=%s rquota=%s rlevels=%s level=%s "
                   "mode=%s"
                   % tuple(read(i) for i in range(1, 17))))
    # **What the ground actually pays**, and it is the owner's own question:
    # «какой процент из них получит выгоду от своего положения на карте».
    # `fed` is how many placed buildings earn any bonus at all; `gain` is the
    # sum of what they earn, out of RANK_SCALE apiece, so the average is one
    # division and `tools/diag.py` does it.
    for slot, source in enumerate((f"{MOD_ID}_plan_fed", f"{MOD_ID}_plan_gain",
                                   f"{MOD_ID}_plan_placed"), start=1):
        out.append(park(slot, source))
    out.append(say("GAIN fed=%s of placed=%s | gain_total=%s out of %d a building "
                   "-- fed is how many earn any bonus where they stand, gain is "
                   "what they earn in all" % (read(1), read(3), read(2), RANK_SCALE)))

    # **The editor, in three lines**, and it is here because he asked for it
    # after a session where 27 buildings went in over the cap and nothing in the
    # report could say how: «Добавляй скан информации для себя в диагностике на
    # функцию редактора, чтобы ты видел чё там происходит.»
    #
    # The three lines are the three stages of a press: what was asked, what the
    # scan found, and what the walk did where it stood. `_ev_*` are parked by the
    # walk itself, because a `debug_log` cannot reach the item a walk is on.
    out.append(say("EDIT legend: one press, three stages. asked -> scan -> walk. "
                   "op 1=«+1» 2=«−1» 0=nothing pressed yet. hit=0 means the walk "
                   "found no candidate at all, so load/esg/esw below are stale. "
                   "esg is the good that moved and esw its gain — on «+1» the one "
                   "evicted, on «−1» the one that took the freed room (0 = none)."))
    for slot, source in enumerate((f"{MOD_ID}_edit_presses", f"{MOD_ID}_edit_op",
                                   f"{MOD_ID}_edit_good", f"{MOD_ID}_edit_reached",
                                   f"{MOD_ID}_edit_done", f"{MOD_ID}_edit_fail",
                                   f"{MOD_ID}_edit_norefill", f"{MOD_ID}_edit_right",
                                   f"{MOD_ID}_edit_idle"), start=1):
        out.append(park(slot, source))
    # **`op` 3 and 4 are the charters** -- «+1» and «−1» on an urban right, which
    # move a charter between towns rather than add one. `right=` is the charter
    # the press was pointed at, `idle=` how many presses since the window opened
    # did nothing at all: «отсутствие изменений -- тоже изменение», 2026-09-06.
    out.append(say("EDIT asked presses=%s op=%s good=%s right=%s reached=%s | outcome "
                   "done=%s fail=%s norefill=%s idle=%s"
                   % (read(1), read(2), read(3), read(8), read(4),
                      read(5), read(6), read(7), read(9))))
    # **`strict` says which of «+1»'s two passes chose the victim**, and it is
    # the one number that separates «the share decided» from «nobody was over
    # their share, so it fell back to the cheapest». 1 = the strict pass found
    # candidates, 0 = it did not and the open pass answered.
    for slot, source in enumerate((f"{MOD_ID}_edit_fitn", f"{MOD_ID}_edit_cands",
                                   f"{MOD_ID}_ev_hit", f"{MOD_ID}_ev_town",
                                   f"{MOD_ID}_ev_load", f"{MOD_ID}_ev_esg",
                                   f"{MOD_ID}_ev_esw", f"{MOD_ID}_edit_strict"),
                                  start=1):
        out.append(park(slot, source))
    out.append(say("EDIT scan fitn=%s cands=%s strict=%s | walk hit=%s town=%s "
                   "load=%s esg=%s esw=%s"
                   % (read(1), read(2), read(8), read(3), read(4),
                      read(5), read(6), read(7))))
    for slot, source in enumerate((f"{MOD_ID}_edit_evicted", f"{MOD_ID}_edit_room",
                                   f"{MOD_ID}_edit_mark", f"{MOD_ID}_ev_load2",
                                   f"{MOD_ID}_plan_placed", f"{MOD_ID}_plan_cap_urban",
                                   f"{MOD_ID}_plan_cap_rural"), start=1):
        out.append(park(slot, source))
    # Field names have to be unique across the whole line: `tools/diag.py` reads
    # them by name, and a bare `after=` matched the wrong one first time out.
    out.append(say("EDIT walk evicted=%s room=%s | placed_before=%s placed_after=%s | "
                   "load_after=%s | cap_urban=%s cap_rural=%s"
                   % (read(1), read(2), read(3), read(5), read(4),
                      read(6), read(7))))
    # **The share, and it is a probe before it is a feature.** «Товар не долился»
    # and «товару не досталось, потому что доля уже выбрана» look the same on
    # screen -- nothing moved -- and telling them apart needs the three numbers
    # the share is made of. `free=0` means every good this ground can make is
    # pinned or flagged, which is a real state and reads as «правило отказало»
    # without this line.
    for slot, source in enumerate((f"{MOD_ID}_edit_quota", f"{MOD_ID}_edit_free",
                                   f"{MOD_ID}_edit_pool_rooms",
                                   f"{MOD_ID}_plan_rooms", f"{MOD_ID}_plan_quota"),
                                  start=1):
        out.append(park(slot, source))
    out.append(say("EDIT share quota=%s free=%s pool_rooms=%s | rooms=%s "
                   "plan_quota=%s"
                   % tuple(read(i) for i in range(1, 6))))
    # **Доля по трём классам товара, и это главная строка про равномерность.**
    # Комнаты города и села не смешиваются, а товары бывают трёх видов: только
    # город, только село, где угодно. Одна доля на общий котёл обещала городским
    # товарам то, чего земля не имеет -- 13 городов на 15 «только городских»
    # товаров дают 3.47, а формула говорила 8. `bind` называет, кто упёрся
    # первым: 0 = никто, вся земля кончилась разом; 1 = городская сторона;
    # 2 = сельская. `rest` -- уровень для всех остальных после насыщения.
    for slot, source in enumerate((f"{MOD_ID}_prooms_t", f"{MOD_ID}_prooms_r",
                                   f"{MOD_ID}_qgt", f"{MOD_ID}_qgr",
                                   f"{MOD_ID}_qcapt", f"{MOD_ID}_qcapr",
                                   f"{MOD_ID}_plan_quota", f"{MOD_ID}_plan_pt",
                                   f"{MOD_ID}_plan_pr"), start=1):
        out.append(park(slot, source))
    # **`filled` -- комнаты, занятые на этой стороне.** Сухой круг поднимает долю
    # только той стороны, где `filled < rooms`; если сторона полна, а товары
    # стоят ниже своего потолка, её потолок и не должен расти -- делится
    # неделимое, 528 комнат на 35 товаров.
    out.append(say("SHARE quota=%s is what a good is owed in all | town: rooms=%s "
                   "filled=%s goods=%s -> cap=%s | village: rooms=%s filled=%s "
                   "goods=%s -> cap=%s "
                   "-- a cap adds no buildings, it stops one good draining the "
                   "scarce side"
                   % (read(7), read(1), read(8), read(3), read(5),
                      read(2), read(9), read(4), read(6))))
    # **Доливка новой земли, и `moved` -- единственное число здесь, у которого
    # есть неправильное значение.** Ноль значит, что на старой земле не сдвинулся
    # ни один домик, то есть замок сработал; всё остальное -- что доливка полезла
    # в X, и тогда виновата не догадка, а это число. `ran=0` -- кнопку не
    # нажимали, и остальные пять чисел тогда ничего не значат.
    for slot, source in enumerate((f"{MOD_ID}_ext_ran", f"{MOD_ID}_ext_new",
                                   f"{MOD_ID}_ext_was", f"{MOD_ID}_ext_rooms",
                                   f"{MOD_ID}_ext_added", f"{MOD_ID}_ext_moved",
                                   f"{MOD_ID}_ext_lifted"), start=1):
        out.append(park(slot, source))
    out.append(say("EXT ran=%s new_locs=%s rooms_before=%s rooms_added=%s "
                   "placed=%s moved_on_old=%s pins_lifted=%s "
                   "-- moved_on_old must be 0"
                   % tuple(read(i) for i in range(1, 8))))
    # **Столбики строк плана: товар обязан стоять над своим домиком.**
    # Окно рисует два списка двумя датамоделями — строка датамодели видит один
    # скоуп, и другого способа нет, — а в пары их складывает только то, что
    # `_row_goods` и `_row_builds` идут индекс в индекс. Расхождение длин
    # сдвинуло бы каждый следующий товар на чужой домик, и **на экране это
    # выглядит как правильная строка**. Поэтому оно считается здесь, а не
    # проверяется глазом. `mismatched` обязан быть нулём.
    out.append(f"""\tset_global_variable = {{ name = {MOD_ID}_dv1 value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_dv2 value = 0 }}
\tevery_in_global_list = {{
\t\tvariable = {MOD_ID}_plan_touched
\t\tlimit = {{ has_variable = {MOD_ID}_load var:{MOD_ID}_load > 0 }}
\t\tchange_global_variable = {{ name = {MOD_ID}_dv1 add = 1 }}
\t\tset_variable = {{ name = {MOD_ID}_rpg value = 0 }}
\t\tset_variable = {{ name = {MOD_ID}_rpb value = 0 }}
\t\tevery_in_list = {{
\t\t\tvariable = {MOD_ID}_row_goods
\t\t\tprev = {{ change_variable = {{ name = {MOD_ID}_rpg add = 1 }} }}
\t\t}}
\t\tevery_in_list = {{
\t\t\tvariable = {MOD_ID}_row_builds
\t\t\tprev = {{ change_variable = {{ name = {MOD_ID}_rpb add = 1 }} }}
\t\t}}
\t\tset_variable = {{ name = {MOD_ID}_rpd value = var:{MOD_ID}_rpg }}
\t\tchange_variable = {{ name = {MOD_ID}_rpd subtract = var:{MOD_ID}_rpb }}
\t\tif = {{
\t\t\tlimit = {{ NOT = {{ var:{MOD_ID}_rpd = 0 }} }}
\t\t\tchange_global_variable = {{ name = {MOD_ID}_dv2 add = 1 }}
\t\t}}
\t\tremove_variable = {MOD_ID}_rpg
\t\tremove_variable = {MOD_ID}_rpb
\t\tremove_variable = {MOD_ID}_rpd
\t}}
""")
    out.append(say("ROWPAIR rows=%s mismatched=%s -- the plan row draws the good "
                   "over its own building only while these two lists are the same "
                   "length; mismatched must be 0"
                   % (read(1), read(2))))

    # **The reshuffle, and it needs three numbers rather than one.** `rounds` at
    # zero says the pass never ran at all — the one failure that looks exactly
    # like «there was nothing to trade» on the map and in the window.
    for slot, source in enumerate((f"{MOD_ID}_rs_rounds", f"{MOD_ID}_rs_swaps",
                                   f"{MOD_ID}_rs_gain", f"{MOD_ID}_rs_pairs",
                                   f"{MOD_ID}_rs_same", f"{MOD_ID}_rs_nofit",
                                   f"{MOD_ID}_rs_worse", f"{MOD_ID}_ps_rounds",
                                   f"{MOD_ID}_ps_swaps", f"{MOD_ID}_ps_gain",
                                   f"{MOD_ID}_ps_rrounds",
                                   f"{MOD_ID}_ps_rswaps"), start=1):
        out.append(park(slot, source))
    # **У «Перетасовать» счётчики свои.** `_rs_*` принадлежат доливке и их
    # стирает открытие окна редактора: прогон 2026-09-09 напечатал `rounds=0
    # swaps=0` после перетасовки, переставившей 36 локаций.
    out.append(say("EDIT shuffle rounds=%s swaps=%s gain=%s | pairs=%s same=%s "
                   "nofit=%s worse=%s || button rounds=%s swaps=%s gain=%s "
                   "| rights rounds=%s swaps=%s"
                   % tuple(read(i) for i in range(1, 13))))

    # **Шаг 7: записала ли панель локацию.** Фишка «Из плана — сюда» стоит на
    # `bag_view_location`, и если проба в панели не сработала, фишка не оставит
    # в списке ничего -- симптом, неотличимый от «план сюда ничего не ставит».
    # Одно число разделяет эти два случая без второго прогона.
    # **Шаг 8 -- одна отмашка, поэтому и числа от неё одноразовые.** Что сделало
    # последнее нажатие: сколько галочек группы нашлось, сколько из них уже
    # стояло и сколько переключено. Ноль в первом при нажатой кнопке -- значит в
    # группе нечему стоять, а не «кнопка не работает».
    for slot, source in enumerate((f"{MOD_ID}_cm_all", f"{MOD_ID}_cm_on",
                                   f"{MOD_ID}_cm_did", f"{MOD_ID}_cm_off"), start=1):
        out.append(park(slot, source))
    out.append(flag(5, "has_variable_list = cm_priority_features_list"))
    # **Житницы CM, одним числом.** Они остаются в земле и в РГО, но мест не
    # дают и домиков не берут: если их много, «мест» в шапке станет меньше, и
    # это не потеря, а вычет, который надо уметь отличить от ошибки.
    out.append(f"\tset_global_variable = {{ name = {MOD_ID}_dv6 value = 0 }}\n"
               f"\tif = {{\n"
               f"\t\tlimit = {{ has_global_variable_list = {MOD_ID}_plan_touched }}\n"
               f"\t\tevery_in_global_list = {{\n"
               f"\t\t\tvariable = {MOD_ID}_plan_touched\n"
               f"\t\t\tlimit = {{ {MOD_ID}_is_granary = yes }}\n"
               f"\t\t\tchange_global_variable = {{ name = {MOD_ID}_dv6 add = 1 }}\n"
               f"\t\t}}\n"
               f"\t}}\n")
    # **Сколько зданий чужих модов эта страна может строить.** Прогон 2026-09-09
    # показал Вестфалии японскую кузню: пул чужих зданий был общий, а не её.
    # Гейты чинены, и теперь число должно быть маленьким и своим -- а «ноль»
    # значит «этой стране чужие моды здания не дают», а не «мод их не увидел».
    foreign = sorted({m.building for m in rows}
                     - {m.building for m in (core_rows or rows)})
    out.append(f"\tset_global_variable = {{ name = {MOD_ID}_dv8 value = 0 }}\n"
               + "".join(f"\tif = {{ limit = {{ can_build_building = building_type:{b} }} "
                         f"change_global_variable = {{ name = {MOD_ID}_dv8 add = 1 }} }}\n"
                         for b in foreign))
    # **И число, которого не хватило 2026-09-09.** `mine` говорит, сколько чужих
    # зданий стране доступно, и по нему я решил, что лишних в плане нет; лишние
    # были, просто ни одно из них не попадало в строки `BLDG` -- те пишутся
    # только про многотоварные здания. Считаем прямо: сколько зданий стоит в
    # плане при том, что построить их страна не может. Это должно быть ноль
    # всегда, и любое другое число -- дыра в воротах, а не особенность.
    out.append(f"\tset_global_variable = {{ name = {MOD_ID}_dv9 value = 0 }}\n"
               + "".join(
                   f"\tif = {{\n"
                   f"\t\tlimit = {{\n"
                   f"\t\t\tNOT = {{ can_build_building = building_type:{b} }}\n"
                   f"\t\t\tany_in_global_list = {{\n"
                   f"\t\t\t\tvariable = {MOD_ID}_plan_touched\n"
                   f"\t\t\t\tis_target_in_variable_list = {{ name = {MOD_ID}_plan_builds "
                   f"target = building_type:{b} }}\n"
                   f"\t\t\t}}\n"
                   f"\t\t}}\n"
                   f"\t\tchange_global_variable = {{ name = {MOD_ID}_dv9 add = 1 }}\n"
                   f"\t}}\n" for b in foreign))
    used_src = sorted({source_of(m.building) for m in rows} - {0})
    if used_src:
        out.append("".join(park(10 + n, f"{MOD_ID}_src{number}")
                           for n, number in enumerate(used_src)))
        out.append(say("SOURCES " + " ".join(
            "%d=%s" % (number, read(10 + n)) for n, number in enumerate(used_src))
            + " -- галочка «читать этот мод» в настройках: 0 значит, что его "
              "здания в план не идут вовсе"))

    # **Зонд под пустой список на «Технической».** Строк там нет, а `SOURCES 4=1`
    # не отличает «CMF список построил, галочка стоит» от «списка нет вовсе»:
    # `_rebuild_sources` ставит 1 и тогда, когда `cmm_list_items_...` не
    # существует. Считаем сами обе стороны -- наш список и заведомо рабочий
    # континентальный контролем.
    out.append(f"\tset_global_variable = {{ name = {MOD_ID}_dv26 value = 0 }}\n"
               f"\tset_global_variable = {{ name = {MOD_ID}_dv27 value = 0 }}\n"
               f"\tevery_in_list = {{\n"
               f"\t\tvariable = cmm_list_items_{MOD_ID}__source\n"
               f"\t\tchange_global_variable = {{ name = {MOD_ID}_dv26 add = 1 }}\n"
               f"\t}}\n"
               f"\tevery_in_list = {{\n"
               f"\t\tvariable = cmm_list_items_{MOD_ID}__continent\n"
               f"\t\tchange_global_variable = {{ name = {MOD_ID}_dv27 add = 1 }}\n"
               f"\t}}\n")
    out.append(say("CMMLIST source=%s continent=%s -- строк, которые CMF построил "
                   "для списка модов и для списка континентов. Континент -- "
                   "контроль, он рисуется: если там 5, а в source 0, список "
                   "не собран; если в source 1, а строки на экране нет, "
                   "виновато рисование" % (read(26), read(27))))

    out.append(say("FOREIGN pool=%d mine=%%s unbuildable=%%s -- зданий чужих модов "
                   "в пуле плана, из них доступных этой державе, и сколько видов "
                   "стоит в плане, не будучи ей доступными: последнее обязано "
                   "быть нулём" % len(foreign) % (read(8), read(9))))

    out.append(park(7, f"{MOD_ID}_raze_n"))
    out.append(say("RAZE last=%s -- сколько производственных зданий снесло "
                   "последнее нажатие «снести лишнее»" % read(7)))
    # **`put` -- зонд круга житниц, и он нужен ровно потому, что их комнаты в
    # счёте мест не участвуют**: «житниц нет» и «житницы есть и пустые» на всех
    # прочих числах выглядят одинаково. `put=0` при `n>0` -- пометки стоят, а
    # ни один домик не встал, и спрашивать тогда надо `can_build_building`, а
    # не пометку.
    out.append(park(5, f"{MOD_ID}_gran_put"))
    out.append(say("GRANARY n=%s put=%s -- локаций, помеченных житницей, и "
                   "домиков, которые круг житниц в них поставил. Их мест план "
                   "не считает и товарами за них никто не спорил; РГО они дают "
                   "как прежде"
                   % (read(6), read(5))))

    out.append(say("CM found=%s were_on=%s touched=%s off=%s present=%s -- "
                   "present=0 значит Construction Manager не в игре и кнопок "
                   "автостроя нет; found=0 после нажатия значит в группе нет ни "
                   "одного домика плана, который тут может стоять"
                   % tuple(read(i) for i in range(1, 6))))

    # **Ванильный костыль, пять чисел, и каждое отделяет одну поломку.**
    # `pairs` -- сколько пар «локация × здание» насчитал скрипт; ноль значит,
    # что плану строить нечего, а не что кнопка не работает. `costed` -- сколько
    # из них успел спросить движок: `costed < pairs` означает, что скрытый привод
    # окна не дошёл до конца, и это единственный симптом, который иначе выглядит
    # как «цена занижена». `built` и `flagged` -- что сделало последнее нажатие.
    for slot, source in enumerate((f"{MOD_ID}_b1_pairs", f"{MOD_ID}_b1_cadd",
                                   f"{MOD_ID}_b1_cost_all", f"{MOD_ID}_b1_fire_n",
                                   f"{MOD_ID}_ax_n"), start=1):
        out.append(park(slot, source))
    out.append(say("VANILLA pairs=%s costed=%s gold=%s | tried=%s flagged=%s -- "
                   "costed обязан равняться pairs, иначе привод окна не дошёл до "
                   "конца и цена занижена; tried -- сколько стройк движку "
                   "предложено, а не сколько он принял (отказ он не возвращает), "
                   "и flagged=0 после нажатия значит, что стройки, которой можно "
                   "поставить галочку, не нашлось"
                   % tuple(read(i) for i in range(1, 6))))

    out.append(flag(1, f"has_global_variable = bag_view_location"))
    out.append(say("FILTER view_location=%s -- 1 значит, что панель "
                   "производства локации записала, какую локацию показывает; "
                   "0 -- что фишка «Из плана — сюда» не может работать "
                   "(её проба не сработала или панель ещё не открывали)"
                   % read(1)))
    out.append("}\n")

    # ----------------------------------------------------------------- the scan
    #
    # **The funnel, read back off the map rather than counted during the pass.**
    # One walk over the locations the plan touched, and for each good on each
    # side four questions: did a method win here, would the placement gate open
    # here *now*, did this good end up here, and what is the best this good could
    # have been ordered at. The four together say which stage a good is lost at
    # and how many locations it was lost at -- and the gate read afterwards is
    # what separates «the ground filled up» from «the allocator never gave it a
    # turn», which reading it on empty ground cannot do.
    out.append(f"""
# The funnel. One walk, and the plan pays nothing for it: everything here is
# what the plan already parked on the locations.
#
# `w` a method won, `g` the gate would still open, `p` it was placed, `o` the
# best ordering it ever had -- against `{MOD_ID}_plan_band`, which is what a
# band admits. A good whose `o` never reaches 200 has only the last band.
# Scope: country
{MOD_ID}_diag_scan = {{
\tset_global_variable = {{ name = {MOD_ID}_diag_locs value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_diag_towns value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_diag_freet value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_diag_vill value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_diag_rural value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_diag_freer value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_diag_realt value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_diag_forced value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_diag_forcedr value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_diag_moved value = 0 }}
""")
    # **How many locations this plan put something different in.** One `OR` a
    # location over the two lists, in the walk the scan already makes, so the
    # count costs nothing the diagnosis was not already paying.
    moved_count = ("\t\tif = {\n\t\t\tlimit = { OR = {\n"
                   + "".join(
                       "\t\t\t\tAND = { is_target_in_variable_list = { name = %s_save_goods target = goods:%s } "
                       "NOT = { is_target_in_variable_list = { name = %s_plan_goods target = goods:%s } } }\n"
                       "\t\t\t\tAND = { is_target_in_variable_list = { name = %s_plan_goods target = goods:%s } "
                       "NOT = { is_target_in_variable_list = { name = %s_save_goods target = goods:%s } } }\n"
                       % (MOD_ID, good, MOD_ID, good, MOD_ID, good, MOD_ID, good)
                       for good in order)
                   + "\t\t\t} }\n\t\t\tchange_global_variable = { name = %s_diag_moved add = 1 }\n\t\t}\n"
                   % MOD_ID)
    for index in range(1, len(order) + 1):
        for side in ("t", "r"):
            for what in ("w", "r", "g", "p", "o"):
                out.append(f"\tset_global_variable = {{ name = {MOD_ID}_f{what}{side}{index} value = 0 }}\n")
    out.append(f"""\tevery_in_global_list = {{
\t\tvariable = {MOD_ID}_plan_touched
\t\tchange_global_variable = {{ name = {MOD_ID}_diag_locs add = 1 }}
{moved_count}
\t\t# **Тумблеры считаются здесь, до разделения на стороны**, и это
\t\t# сознательно: 2026-09-02 он сбросил их в «авто», а окно показало города
\t\t# снова. Счёт по обеим сторонам различает «переменная вернулась» и «окно
\t\t# врёт» -- по стороне это было бы неразличимо, потому что сброшенная
\t\t# локация уходит на сельскую сторону вместе со своим счётчиком.
\t\tif = {{
\t\t\tlimit = {{ has_variable = {MOD_ID}_force_town }}
\t\t\tchange_global_variable = {{ name = {MOD_ID}_diag_forced add = 1 }}
\t\t}}
\t\tif = {{
\t\t\tlimit = {{ has_variable = {MOD_ID}_force_rural }}
\t\t\tchange_global_variable = {{ name = {MOD_ID}_diag_forcedr add = 1 }}
\t\t}}
\t\tif = {{
\t\t\tlimit = {{ {MOD_ID}_plan_is_town = yes }}
\t\t\tchange_global_variable = {{ name = {MOD_ID}_diag_towns add = 1 }}
\t\t\t# **Городская сторона и городской ранг -- разные вещи.** Тумблер
\t\t\t# «сделать городом» переносит локацию на городскую сторону расчёта,
\t\t\t# но ранга в игре не меняет -- а гильдия объявлена `town = yes` и в
\t\t\t# `rural_settlement` не встанет никогда. 2026-09-02 весь симптом
\t\t\t# оказался в этом зазоре, и это число его называет.
\t\t\tif = {{
\t\t\t\tlimit = {{ NOT = {{ location_rank = location_rank:rural_settlement }} }}
\t\t\t\tchange_global_variable = {{ name = {MOD_ID}_diag_realt add = 1 }}
\t\t\t}}
\t\t\tif = {{
\t\t\t\tlimit = {{ var:{MOD_ID}_load < global_var:{MOD_ID}_plan_cap_urban }}
\t\t\t\tchange_global_variable = {{ name = {MOD_ID}_diag_freet add = 1 }}
""")
    # **`r` is what separates a full ground from a starved good**, and it is the
    # one distinction the gate cannot draw on its own: the gate is a conjunction,
    # so `g = 0` means "no room" and "already here" and "that building is taken"
    # at once. Counted inside the room test, so a location with no room costs
    # nothing.
    for index in range(1, len(order) + 1):
        out.append(f"\t\t\t\tif = {{ limit = {{ var:{MOD_ID}_pm{index} > 0 }} "
                   f"change_global_variable = {{ name = {MOD_ID}_frt{index} add = 1 }} }}\n")
    out.append("\t\t\t}\n")
    for index, good in enumerate(order, start=1):
        out.append(f"""\t\t\tif = {{ limit = {{ var:{MOD_ID}_pm{index} > 0 }} change_global_variable = {{ name = {MOD_ID}_fwt{index} add = 1 }} }}
\t\t\tif = {{ limit = {{ {MOD_ID}_plan_can_town_{index} = yes }} change_global_variable = {{ name = {MOD_ID}_fgt{index} add = 1 }} }}
\t\t\tif = {{ limit = {{ is_target_in_variable_list = {{ name = {MOD_ID}_plan_goods target = goods:{good} }} }} change_global_variable = {{ name = {MOD_ID}_fpt{index} add = 1 }} }}
\t\t\tif = {{
\t\t\t\tlimit = {{ {MOD_ID}_ord{index} > global_var:{MOD_ID}_fot{index} }}
\t\t\t\tset_global_variable = {{ name = {MOD_ID}_fot{index} value = 0 }}
\t\t\t\tchange_global_variable = {{ name = {MOD_ID}_fot{index} add = {MOD_ID}_ord{index} }}
\t\t\t}}
""")
    # **Сколько деревень стоит и сколько сельских локаций есть.** Игра помечает
    # четыре здания `is_village = yes` -- рыночная, земледельческая, лесная,
    # рыбацкая, -- и **локация держит по одной каждого вида**: владелец,
    # 2026-09-07, «в сельской локации при большом желании может стоять
    # одновременно все 4 деревни». Значит деревень законно больше, чем локаций,
    # и число здесь -- не проверка, а мера того, насколько плотно они стоят.
    # Считается обходом, а не счётчиком: счётчик разошёлся бы с правками
    # редактора, а `_plan_builds` -- это то, что стоит сейчас.
    village_tests = "".join(
        f"\t\t\tif = {{ limit = {{ is_target_in_variable_list = {{ name = {MOD_ID}_plan_builds "
        f"target = building_type:{b} }} }} change_global_variable = "
        f"{{ name = {MOD_ID}_diag_vill add = 1 }} }}\n"
        for b in sorted({m.building for m in rows if m.is_village}))
    out.append(f"""\t\t}}
\t\telse = {{
\t\t\tchange_global_variable = {{ name = {MOD_ID}_diag_rural add = 1 }}
{village_tests}\t\t\tif = {{
\t\t\t\tlimit = {{ var:{MOD_ID}_load < global_var:{MOD_ID}_plan_cap_rural }}
\t\t\t\tchange_global_variable = {{ name = {MOD_ID}_diag_freer add = 1 }}
""")
    for index in range(1, len(order) + 1):
        out.append(f"\t\t\t\tif = {{ limit = {{ var:{MOD_ID}_prm{index} > 0 }} "
                   f"change_global_variable = {{ name = {MOD_ID}_frr{index} add = 1 }} }}\n")
    out.append("\t\t\t}\n")
    for index, good in enumerate(order, start=1):
        out.append(f"""\t\t\tif = {{ limit = {{ var:{MOD_ID}_prm{index} > 0 }} change_global_variable = {{ name = {MOD_ID}_fwr{index} add = 1 }} }}
\t\t\tif = {{ limit = {{ {MOD_ID}_plan_can_rural_{index} = yes }} change_global_variable = {{ name = {MOD_ID}_fgr{index} add = 1 }} }}
\t\t\tif = {{ limit = {{ is_target_in_variable_list = {{ name = {MOD_ID}_plan_goods target = goods:{good} }} }} change_global_variable = {{ name = {MOD_ID}_fpr{index} add = 1 }} }}
\t\t\tif = {{
\t\t\t\tlimit = {{ {MOD_ID}_ordr{index} > global_var:{MOD_ID}_for{index} }}
\t\t\t\tset_global_variable = {{ name = {MOD_ID}_for{index} value = 0 }}
\t\t\t\tchange_global_variable = {{ name = {MOD_ID}_for{index} add = {MOD_ID}_ordr{index} }}
\t\t\t}}
""")
    out.append("\t\t}\n\t}\n}\n")

    # ---------------------------------------------------------------- the goods
    out.append(f"""
# One line per good, town and village apart, every counter uncompressed. The
# ladder is m -> a -> w -> g/p: the first zero is the stage the good is lost at,
# and the number before it is how many locations got that far.
# Scope: country
{MOD_ID}_diag_goods = {{
""")
    out.append(say("GOODS legend: T=town R=village | m=methods(of them last-age) "
                   "a=country has the advance w=a method won here r=of those, "
                   "still has room g=the gate would still open p=placed "
                   "o=best ordering it ever had (a band admits >= its own number) "
                   "| ng=candidates that can make it q=quota n=placed both sides "
                   "rgo=locations already yielding it as an RGO"))
    # **`q` is read after the plan, and the open ladder raised it.** It is the
    # only number in the report that is not what the pass it belongs to saw:
    # `_plan_set_quota` writes `quota + charters - RGOs` with a floor of one, and
    # then every sweep of the open ladder adds one to all of them. Without this
    # line the two are read against each other and neither makes sense --
    # Westphalia's `PASS quota=2` beside `clay q=2 rgo=2`, which looks like the
    # RGO discount doing nothing and is the open ladder having added one back.
    out.append(say("GOODS reading q: it is `PASS quota` + what the charters "
                   "placed for this good - `rgo`, floored at 1, and then + 1 for "
                   "each sweep of the open ladder -- which is `PASS open_sweeps`. "
                   "So the quota the allocator enforced is q - open_sweeps, and a "
                   "good with n at that number was stopped by its quota and not "
                   "by the ground."))
    out.append(say("GOODS reading it: the first zero left to right is the stage. "
                   "w>0 r=0 -- the ground filled up. w>0 r>0 g=0 -- the good or "
                   "its building is already in every place that has room. "
                   "g>0 p=0 -- the allocator never gave it a turn, so look at "
                   "q, ng against the tiers, and o against the bands."))
    # **Одно здание, за которое спорят несколько товаров — и это то, чего в
    # отчёте не было.** Локация держит одно здание каждого вида, поэтому
    # рыбацкая деревня на побережье -- это один слот на три товара: рыбу,
    # судовые припасы и гончарку. Товар с виду «недобрал», а на деле его место
    # занял сосед по зданию, и никакая раздача этого не создаст.
    #
    # **Строки статические**: список товаров на здание генератор знает и так, а
    # числа читаются из строк `G<n>` того же отчёта. `slots=` называет товар,
    # которому это здание -- единственная дорога на своей стороне: его `w` и
    # есть, скольким локациям здание вообще годится. `only=` -- те, кому оно
    # единственное (их `p` складываются без двойного счёта), `also=` -- те, кто
    # может уйти и в другое здание.
    for side, name in (("t", "T"), ("r", "R")):
        share: dict[str, list[str]] = {}
        for good in order:
            for building in (groups.get((good, side)) or {}):
                share.setdefault(building, []).append(good)
        for building, goods in sorted(share.items()):
            if len(goods) < 2:
                continue
            only = [g for g in goods if len(groups[(g, side)]) == 1]
            also = [g for g in goods if g not in only]
            out.append(say("SHARED %s %s slots=%s only=%s also=%s"
                           % (name, building, only[0] if only else "-",
                              ",".join(only) or "-", ",".join(also) or "-")))
    # **И сколько каждое общее здание в итоге встало против своего потолка.**
    # Без этой пары чисел «торговых деревень 62» не отличить от «торговых
    # деревень 62, потому что больше не пустила земля»: первое -- потолок
    # работает, второе -- он ни при чём.
    for k, building in enumerate(shared_buildings(rows, split, game), start=1):
        out.append(park(1, f"{MOD_ID}_bn{k}"))
        out.append(park(2, f"{MOD_ID}_bq{k}"))
        out.append(say(f"BLDG {building} built=%s cap=%s -- здание, за которое "
                       f"спорят несколько товаров: у него свой потолок, равный "
                       f"общей доле" % (read(1), read(2))))
    for index in range(1, len(order) + 1):
        out.append(f"\t{MOD_ID}_diag_good_{index} = yes\n")
    out.append(f"""\t{MOD_ID}_diag_free = yes
}}

# Room left over when the plan stopped, which is what tells a starved good from
# a full ground.
# Scope: country
{MOD_ID}_diag_free = {{
""")
    for slot, source in enumerate((f"{MOD_ID}_diag_locs", f"{MOD_ID}_diag_towns",
                                   f"{MOD_ID}_diag_freet", f"{MOD_ID}_diag_freer",
                                   f"{MOD_ID}_diag_realt", f"{MOD_ID}_diag_forced",
                                   f"{MOD_ID}_diag_forcedr", f"{MOD_ID}_diag_moved",
                                   f"{MOD_ID}_diag_vill", f"{MOD_ID}_diag_rural"), start=1):
        out.append(park(slot, source))
    out.append(say("ROOM walked=%s towns=%s towns_with_room=%s villages_with_room=%s "
                   "| town rank or above=%s | ticks now set: town=%s village=%s "
                   "-- read live, so this says what the ticks are at this moment "
                   "and not what the last plan saw | moved=%s locations differ from "
                   "the plan before this one | villages=%s rural_locs=%s "
                   "-- four buildings are `is_village`, and a location takes one "
                   "of each kind, so this may exceed the locations by design"
                   % tuple(read(i) for i in range(1, 11))))
    out.append("}\n")

    for index, good in enumerate(order, start=1):
        town = [i for methods_ in groups.get((good, "t"), {}).values() for i in methods_]
        village = [i for methods_ in groups.get((good, "r"), {}).values() for i in methods_]
        town_end = sum(1 for i in town if i in last)
        village_end = sum(1 for i in village if i in last)
        out.append(f"""
# Scope: country
{MOD_ID}_diag_good_{index} = {{
""")
        for slot, source in ((1, f"{MOD_ID}_fwt{index}"), (2, f"{MOD_ID}_fgt{index}"),
                             (3, f"{MOD_ID}_fpt{index}"), (4, f"{MOD_ID}_fot{index}"),
                             (5, f"{MOD_ID}_fwr{index}"), (6, f"{MOD_ID}_fgr{index}"),
                             (7, f"{MOD_ID}_fpr{index}"), (8, f"{MOD_ID}_for{index}"),
                             (9, f"{MOD_ID}_ng{index}"), (10, f"{MOD_ID}_pq{index}"),
                             (11, f"{MOD_ID}_pn{index}"), (12, f"{MOD_ID}_nrgo{index}"),
                             (15, f"{MOD_ID}_frt{index}"), (16, f"{MOD_ID}_frr{index}"),
                             # The editor's own share for this good, which is the
                             # plan's arithmetic applied to the editor's quota:
                             # `_edit_quota - rgo`, floored at 1. It is here so a
                             # run can check the two against each other.
                             (17, f"{MOD_ID}_eq{index}"),
                             # **Выхлоп этого товара, в сотых единицы.** Домик
                             # домику не равен: городская пивоварня-мельница
                             # даёт 4.00, сельская 0.50. Пока это не посчитано,
                             # «равномерно» проверить нечем — а `n` про
                             # равномерность врёт в восемь раз.
                             (18, f"{MOD_ID}_pout{index}"),
                             # **Домики по сторонам, и это то, ради чего квота
                             # разделена.** «15 стекла» из 13 сельских и двух
                             # городских и «15 текстиля» из пятнадцати городских
                             # — разные планы, а одно число `n` их не различало.
                             (19, f"{MOD_ID}_pnt{index}"),
                             (20, f"{MOD_ID}_pnr{index}"),
                             # **РГО по сторонам, потому что вычитаются они по
                             # сторонам.** Городской потолок вычитает `_nrgot`,
                             # сельский `_nrgor`, и деление идёт по тому, **где
                             # РГО стоит**, а не по тому, **где товар умеет
                             # строить**. У односторонней краски РГО на сельской
                             # локации срезает сельский потолок, которым она
                             # никогда не пользуется, и скидка пропадает: без
                             # этих двух чисел такое не отличить от формулы,
                             # которая просто не работает.
                             (21, f"{MOD_ID}_nrgot{index}"),
                             (22, f"{MOD_ID}_nrgor{index}"),
                             # **Сами потолки, а не только общая доля.** Его
                             # слова, 2026-09-08: «проблема реально в том, что
                             # я не вижу потолка». Потолок растёт с каждым сухим
                             # кругом, поэтому единого числа на всех нет — оно
                             # своё у каждого товара, и без него не отличить
                             # «связал потолок» от «кончились комнаты».
                             (23, f"{MOD_ID}_pqt{index}"),
                             (24, f"{MOD_ID}_pqr{index}"),
                             (25, f"{MOD_ID}_pqraw{index}")):
            out.append(park(slot, source))
        # Availability is the country's advance and not the location's ground:
        # `can_build_building` asked here answers the advance, asked in a
        # location it answers the rank and the terrain. Two different questions
        # and the first dump conflated them, which put three goods the country
        # had not unlocked in the column that means "our scoring dropped it".
        for slot, side in ((13, town), (14, village)):
            if side:
                condition = " ".join(f"{MOD_ID}_avail_{i} = yes" for i in sorted(set(side)))
                out.append(flag(slot, f"OR = {{ {condition} }}"))
            else:
                out.append(f"\tset_global_variable = {{ name = {MOD_ID}_dv{slot} value = 0 }}\n")
        out.append(say(f"G{index} {good} {kinds[good]} "
                       f"| T m={len(town)}({town_end}) a={read(13)} w={read(1)} "
                       f"r={read(15)} g={read(2)} p={read(3)} o={read(4)} "
                       f"| R m={len(village)}({village_end}) a={read(14)} w={read(5)} "
                       f"r={read(16)} g={read(6)} p={read(7)} o={read(8)} "
                       f"| ng={read(9)} q={read(10)} n={read(11)} rgo={read(12)} "
                       f"eq={read(17)} out={read(18)} "
                       f"nt={read(19)} nr={read(20)} "
                       f"rgot={read(21)} rgor={read(22)} "
                       f"qt={read(23)} qr={read(24)} qraw={read(25)}"))
        out.append("}\n")

    # ----------------------------------------------------------------- the laps
    #
    # **The one thing the dump cannot read back afterwards.** How the allocation
    # was shaped -- level by level -- leaves nothing behind on the map; one
    # counter per lap in `_plan_allocate` is what makes it visible, and it costs
    # one write a lap.
    #
    # **A flat run is an even plan and a cliff is not.** Lap one is the covering
    # level and should be very nearly «every good the ground can make»; each lap
    # after it is one more building for everyone who still has a place. A lap of
    # 0 is a dry lap -- the share was spent and every quota rose by one.
    out.append(f"""
# What each level of the draft placed. `L1` is coverage; a 0 is a dry lap, which
# opened every quota by one. `laps=` on the PASS line is how many ran in all, and
# `laps={PLAN_LAPS}` there is the guard cutting the draft off with work still to do.
# Scope: country
{MOD_ID}_diag_laps = {{
""")
    for lap in range(1, DIAG_LAPS + 1):
        out.append(park(1, f"{MOD_ID}_lapn{lap}"))
        out.append(say(f"L{lap} placed={read(1)}"))
    out.append("}\n")

    # --------------------------------------------------------------- the rights
    #
    # `_rgiven<k>` has counted how many towns each right took since the day
    # rights were added -- the plan divides a right's score by it -- and nothing
    # ever showed it. One charter holding most of the towns is a fault a level
    # above any single good's row, and that is the level the reported symptom
    # lives on.
    out.append(f"""
# How many towns each urban right was granted in, and what it grants. A charter
# in twenty-one towns whose second good is nowhere is a plan-level fault and not
# a good's.
# Scope: country
{MOD_ID}_diag_rights = {{
""")
    for number, right in enumerate(rights, start=1):
        # **Круглые скобки, не квадратные.** `[glass, masonry]` в строке -- это
        # синтаксис data-функции: 2026-09-02 движок попытался вызвать функцию
        # `glass`, не нашёл, и `given=` уехало отдельной записью лога. Правило
        # записано в корневом CLAUDE.md, и оно про любую строку, а не только
        # про локализацию.
        goods = ", ".join(sorted(right.output))
        out.append(park(1, f"{MOD_ID}_rgiven{number}"))
        # **`given=0` had two meanings and they are not the same fault.** A
        # charter this country may grant and did not is the allocator's problem;
        # one it may never grant -- somebody else's tag, somebody else's culture
        # -- is not a problem at all. Four of the thirteen read `given=0` on every
        # report of 2026-09-03 and the report could not tell them apart.
        out.append(flag(2, f"{MOD_ID}_plan_right_gate_{number} = yes"))
        # **And `unlocked=` is the advance, which the plan deliberately ignores.**
        # The plan grants every charter the country could ever hold, because it is
        # a target to build towards and the nine general ones arrive at one fixed
        # age (`plan_right_gates`). That leaves a real question the owner can only
        # answer from here: *may I grant this today?* Gating the plan on it was
        # tried on 2026-09-03 and cost the plan a quarter of its ground; printing
        # it costs one flag.
        advance = by_key[right.key].advance
        out.append(flag(3, f"has_advance = {advance}" if advance else "always = yes"))
        out.append(say(f"RIGHT {number} {right.key} ({goods}) "
                       f"given={read(1)} grantable={read(2)} unlocked={read(3)}"))
    out.append("}\n")

    # ------------------------------------------------------------ the locations
    out.append(f"""
# One block per location the plan filled, best first. The line above each block
# is the location itself, from `debug_log_scopes`; the `LG` lines under it are
# what was put there, one good a line -- which is the whole of the reported
# symptom in the one place it can be read.
# Scope: country
{MOD_ID}_diag_locations = {{
\tset_global_variable = {{ name = {MOD_ID}_diag_n value = 0 }}
""")
    # **The key before the numbers it unlocks.** It used to be printed after the
    # last location, where `tools/diag.py` swallowed it whole; and even reaching
    # the page it would have been a legend under two hundred rows of the thing it
    # explains.
    out.append(say("RQ legend: what the ground would pay for each charter in that "
                   "town, out of %d -- " % RANK_SCALE + ", ".join(
                       f"{number}={right.key}" for number, right in enumerate(rights, start=1))
                   + ". Each bundle good the town can make adds its own gain, each it "
                   "cannot adds nothing, and the sum is divided by the whole bundle. The "
                   "largest is the one the town took, unless its quota was already spent."))
    out.append(f"""\tordered_in_global_list = {{
\t\tvariable = {MOD_ID}_plan_ranked
\t\torder_by = {MOD_ID}_plan_rank_order
\t\tmax = {DIAG_LOCS}
\t\tcheck_range_bounds = no
\t\tchange_global_variable = {{ name = {MOD_ID}_diag_n add = 1 }}
""")
    for slot, source in ((1, f"{MOD_ID}_plan_rank"), (2, f"{MOD_ID}_load"),
                         (3, f"{MOD_ID}_plan_right"), (4, f"{MOD_ID}_plan_prank"),
                         (5, f"{MOD_ID}_plan_prov_load")):
        out.append(park(slot, source, "var", tab="\t\t"))
    out.append(flag(6, f"{MOD_ID}_plan_is_town = yes", tab="\t\t"))
    # **The gap the whole 2026-09-02 symptom lives in**, printed per row: which
    # side the plan put this location on, what rank the *game* thinks it is, and
    # whether the player's tick is what moved it. A guild is `town = yes` and
    # will not stand in a `rural_settlement` however the plan scores it.
    out.append(flag(7, "NOT = { location_rank = location_rank:rural_settlement }",
                    tab="\t\t"))
    out.append(flag(8, f"has_variable = {MOD_ID}_force_town", tab="\t\t"))
    out.append(flag(9, f"has_variable = {MOD_ID}_force_rural", tab="\t\t"))
    out.append("\t\tdebug_log_scopes = no\n")
    out.append(say(f"L rank={read(1)} town={read(6)} town_rank={read(7)} "
                   f"forced_town={read(8)} forced_village={read(9)} load={read(2)} "
                   f"right={read(3)} prov_rank={read(4)} prov_load={read(5)}",
                   tab="\t\t"))
    # **Why this town got this charter and not another one**, which is the one
    # question the report could not answer: the plan prints the winner and never
    # the field it beat. `_rq<k>` is what this ground would pay for the whole
    # charter, out of `RANK_SCALE`, so the line is the whole comparison the grant
    # made and a one-good right's number is that good's gain read off directly.
    #
    # Towns only, because a village never holds one. A script value is added into
    # the scratch global rather than parked: `park` asks `has_variable`, and a
    # script value is not a variable.
    out.append(f"\t\tif = {{\n\t\t\tlimit = {{ {MOD_ID}_plan_is_town = yes }}\n")
    for number in range(1, len(rights) + 1):
        out.append(f"\t\t\tset_global_variable = {{ name = {MOD_ID}_dv{number} value = 0 }}\n"
                   f"\t\t\tchange_global_variable = {{ name = {MOD_ID}_dv{number} "
                   f"add = {MOD_ID}_rq{number} }}\n")
    # **No second `debug_log_scopes` here, and the reports of 2026-09-03 are
    # why.** The effect writes one line naming the scope, and this block called
    # it again inside the same iteration -- so every location's name reached the
    # log twice, and `tools/diag.py`, which reads the unlabelled line before a
    # row as that row's name, gave every row from the second onwards **two**
    # names: «WTP L Район Липпштадт (980) Район Зост (981) rank=2». The owner,
    # looking for one town in it: «Понятия не имею где конкретно искать строку
    # Гослара». The `L` line above names this location already and `RQ` is the
    # next line of the same block.
    out.append(say("RQ " + " ".join(f"{number}={read(number)}"
                                    for number in range(1, len(rights) + 1)),
                   tab="\t\t\t"))
    out.append("\t\t}\n")
    for good in order:
        out.append(f"\t\tif = {{ limit = {{ is_target_in_variable_list = "
                   f"{{ name = {MOD_ID}_plan_goods target = goods:{good} }} }} "
                   f'debug_log = "WTP LG {good}" }}\n')
    # **And what this plan moved against the one before it.** `_save_goods` is the
    # previous plan's list, copied off the location before `_plan_prepare`
    # cleared it. Printed only for the locations that take a row, so a large
    # ground pays for at most `DIAG_LOCS` comparisons rather than all of them.
    for good in order:
        out.append(
            f"\t\tif = {{ limit = {{ "
            f"is_target_in_variable_list = {{ name = {MOD_ID}_save_goods target = goods:{good} }} "
            f"NOT = {{ is_target_in_variable_list = {{ name = {MOD_ID}_plan_goods target = goods:{good} }} }} "
            f'}} debug_log = "WTP LD -{good}" }}\n')
        out.append(
            f"\t\tif = {{ limit = {{ "
            f"is_target_in_variable_list = {{ name = {MOD_ID}_plan_goods target = goods:{good} }} "
            f"NOT = {{ is_target_in_variable_list = {{ name = {MOD_ID}_save_goods target = goods:{good} }} }} "
            f'}} debug_log = "WTP LD +{good}" }}\n')
    out.append("\t}\n")
    out.append(park(1, f"{MOD_ID}_diag_n"))
    out.append(park(2, f"{MOD_ID}_plan_found"))
    out.append(say(f"LOCS printed={read(1)} of={read(2)} cap={DIAG_LOCS} "
                   "-- a cap is never silently the answer"))
    out.append("}\n")

    # -------------------------------------------------------------- the ranking
    out.append(f"""
# The single-good ranking's own answer, for the case where the plan is right and
# the table it is read against is not. A row is a province definition.
# Scope: country
{MOD_ID}_diag_ranking = {{
\tset_global_variable = {{ name = {MOD_ID}_diag_n value = 0 }}
\tordered_in_global_list = {{
\t\tvariable = {MOD_ID}_ranked
\t\torder_by = {MOD_ID}_rank_order
\t\tmax = {DIAG_ROWS}
\t\tcheck_range_bounds = no
\t\tchange_global_variable = {{ name = {MOD_ID}_diag_n add = 1 }}
""")
    for slot, source in ((1, f"{MOD_ID}_rank"), (2, f"{MOD_ID}_bonus"),
                         (3, f"{MOD_ID}_out"), (4, f"{MOD_ID}_bonus_rural"),
                         (5, f"{MOD_ID}_out_rural"), (6, f"{MOD_ID}_end_bonus"),
                         (7, f"{MOD_ID}_end_out"), (8, f"{MOD_ID}_mid_bonus"),
                         (9, f"{MOD_ID}_mid_age")):
        out.append(park(slot, source, "var", tab="\t\t"))
    out.append("\t\tdebug_log_scopes = no\n")
    out.append(say(f"R rank={read(1)} now_town={read(2)}/{read(3)} "
                   f"now_village={read(4)}/{read(5)} end_town={read(6)}/{read(7)} "
                   f"mid={read(8)} mid_age={read(9)}", tab="\t\t"))
    out.append("\t}\n")
    out.append(park(1, f"{MOD_ID}_diag_n"))
    out.append(park(2, f"{MOD_ID}_found"))
    out.append(say(f"ROWS printed={read(1)} of={read(2)} cap={DIAG_ROWS}"))
    out.append("}\n")

    # ---------------------------------------------------- the reshuffle's probe
    #
    # **Выгода от земли — свойство ПРОВИНЦИИ, а не локации.** `_g<n>` спрашивает
    # `province_definition = {{ any_location_in_province_definition = {{
    # raw_material = goods:X }} }}`: одно РГО где угодно в провинции кормит
    # каждую её локацию одинаково. Значит **обмен внутри провинции не может
    # изменить ничего**, и первый зонд, считавший именно его, мерил пустоту.
    # Владелец, 2026-09-09: «какой смысл мусолить домики внутри своих же
    # провинций? У них везде будет один и тот же бонус от земли». Он прав.
    #
    # **Откуда тогда взялись 18 244.** Тот зонд брал лучшее по провинции, не
    # различая сторон: городской домик сравнивался с сельским лучшим. Это разные
    # рецепты с разными потолками, и разница между ними — не запас, а ошибка.
    # Здесь стороны считаются раздельно, и число «внутри провинции» осталось
    # **проверкой**: оно обязано быть нулём, иначе врёт и этот зонд тоже.
    #
    # **Настоящий вопрос — между провинциями.** Товар переезжает из провинции,
    # где ему платят мало, в ту, где платят много; кто там стоял, едет обратно.
    # Граница считается так: лучшая провинция для товара на его стороне минус то,
    # что каждый его домик получает там, где стоит. Верхняя, и очень щедрая:
    # все домики товара в одну провинцию не влезут.
    out.append(f"""
# What a reshuffle could add, as an upper bound. Дорого и считается только здесь.
# Scope: country
{MOD_ID}_diag_shuffle = {{
\tset_global_variable = {{ name = {MOD_ID}_rp_bound value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_rp_moves value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_rp_right value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_rp_pbound value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_rp_vbound value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_rp_vmoves value = 0 }}
""")
    own = own_sides(rows, split, game)
    villages_ = village_entities(rows, split, game)
    for index, good in enumerate(order, start=1):
        # **Сторона считается по СВОИМ зданиям.** У пива в селе только торговая
        # деревня: сельской стороны у него нет, и мерить её через деревенский
        # рецепт значит мерить чужой домик. Владелец, 2026-09-09: «ты учёл, что у
        # сёл теперь нет рыбы, пива и т.п.»
        town, rural = own[good]
        if not town and not rural:
            continue
        # Свои рецепты стороны: `_prm<n>` -- лучший сельский, и он может быть
        # деревенским даже у товара, у которого своё здание есть (украшения:
        # торговая деревня против `pounamou_carver`).
        own_m = {}
        for kind, side in (("t", "t"), ("r", "r")):
            own_m[kind] = sorted(
                m for b, ms in (groups.get((good, side)) or {}).items()
                if b not in villages_ for m in ms)

        def best(kind: str, tab: str) -> str:
            """Лучшее, что земля платит этому товару на этой стороне."""
            g, m = ("p", "pm") if kind == "t" else ("pr", "prm")
            acc = "rp_bt" if kind == "t" else "rp_br"
            mine = " ".join(f"var:{MOD_ID}_{m}{index} = {x}" for x in own_m[kind])
            return (f"{tab}if = {{\n"
                    f"{tab}\t{MOD_ID}_plan_is_town = {'yes' if kind == 't' else 'no'}\n"
                    .replace(f"{tab}\t{MOD_ID}", f"{tab}\tlimit = {{ {MOD_ID}")
                    .replace(f"= {'yes' if kind == 't' else 'no'}\n",
                             f"= {'yes' if kind == 't' else 'no'} }}\n")
                    + f"{tab}\tif = {{\n"
                      f"{tab}\t\tlimit = {{\n"
                      f"{tab}\t\t\tOR = {{ {mine} }}\n"
                      f"{tab}\t\t\tvar:{MOD_ID}_{g}{index} > global_var:{MOD_ID}_{acc}\n"
                      f"{tab}\t\t}}\n"
                      f"{tab}\t\tset_global_variable = {{ name = {MOD_ID}_{acc} "
                      f"value = var:{MOD_ID}_{g}{index} }}\n"
                      f"{tab}\t}}\n"
                      f"{tab}}}\n")

        def gap(kind: str, tab: str, acc: str) -> str:
            """Насколько ниже лучшего стоит **свой** домик этого товара здесь."""
            g = "p" if kind == "t" else "pr"
            b = "rp_bt" if kind == "t" else "rp_br"
            side = kind
            builds = " ".join(
                f"is_target_in_variable_list = {{ name = {MOD_ID}_plan_builds "
                f"target = building_type:{x} }}"
                for x in sorted(x for x in (groups.get((good, side)) or {})
                                if x not in villages_))
            return (f"{tab}if = {{\n"
                    f"{tab}\tlimit = {{\n"
                    f"{tab}\t\t{MOD_ID}_plan_is_town = {'yes' if kind == 't' else 'no'}\n"
                    f"{tab}\t\tOR = {{ {builds} }}\n"
                    f"{tab}\t\tvar:{MOD_ID}_{g}{index} < global_var:{MOD_ID}_{b}\n"
                    f"{tab}\t}}\n"
                    f"{tab}\tset_global_variable = {{ name = {MOD_ID}_rp_d "
                    f"value = global_var:{MOD_ID}_{b} }}\n"
                    f"{tab}\tchange_global_variable = {{ name = {MOD_ID}_rp_d "
                    f"subtract = var:{MOD_ID}_{g}{index} }}\n"
                    f"{tab}\tchange_global_variable = {{ name = {MOD_ID}_{acc} "
                    f"add = global_var:{MOD_ID}_rp_d }}\n"
                    + (f"{tab}\tchange_global_variable = {{ name = {MOD_ID}_rp_moves add = 1 }}\n"
                       f"{tab}\tif = {{\n"
                       f"{tab}\t\tlimit = {{ has_variable = {MOD_ID}_plan_right }}\n"
                       f"{tab}\t\tchange_global_variable = {{ name = {MOD_ID}_rp_right "
                       f"add = global_var:{MOD_ID}_rp_d }}\n"
                       f"{tab}\t}}\n" if acc == "rp_bound" else "")
                    + f"{tab}}}\n")

        sides = [k for k, ok in (("t", town), ("r", rural)) if ok]
        zero = (f"\tset_global_variable = {{ name = {MOD_ID}_rp_bt value = 0 }}\n"
                f"\tset_global_variable = {{ name = {MOD_ID}_rp_br value = 0 }}\n")
        stands = (f"\t\t\thas_variable = {MOD_ID}_load\n"
                  f"\t\t\tis_target_in_variable_list = {{ name = {MOD_ID}_plan_goods "
                  f"target = goods:{good} }}\n")
        out.append(f"""\t# {good}: по всей земле — что и есть «между провинциями».
{zero}\tevery_in_global_list = {{
\t\tvariable = {MOD_ID}_plan_touched
\t\tlimit = {{ has_variable = {MOD_ID}_load }}
{"".join(best(k, chr(9) * 2) for k in sides)}\t}}
\tevery_in_global_list = {{
\t\tvariable = {MOD_ID}_plan_touched
\t\tlimit = {{
{stands}\t\t}}
{"".join(gap(k, chr(9) * 2, "rp_bound") for k in sides)}\t}}
\t# Он же внутри провинции — проверка, и она обязана дать ноль.
\tevery_in_global_list = {{
\t\tvariable = {MOD_ID}_plan_prov_locs
{zero}\t\tprovince_definition = {{
\t\t\tevery_location_in_province_definition = {{
\t\t\t\tlimit = {{ has_variable = {MOD_ID}_load }}
{"".join(best(k, chr(9) * 4) for k in sides)}\t\t\t}}
\t\t}}
\t\tprovince_definition = {{
\t\t\tevery_location_in_province_definition = {{
\t\t\t\tlimit = {{
\t{stands}\t\t\t\t}}
{"".join(gap(k, chr(9) * 4, "rp_pbound") for k in sides)}\t\t\t}}
\t\t}}
\t}}
""")
    # **Деревни считаются отдельно, потому что они — отдельная сущность.** У них
    # своя выгода `_vb<k>` (лучший из их собственных рецептов здесь), и она у
    # каждой провинции своя, как у товаров. Владелец, 2026-09-09: «у них выгода
    # вообще почти от любой провинции и везде разная». **Обмен её не спрашивает**
    # — «пусть стоят где хотят», — а число здесь говорит, чего это стоит.
    for k, building in enumerate(village_entities(rows, split, game), start=1):
        out.append(f"""\t# {building}
\tset_global_variable = {{ name = {MOD_ID}_rp_br value = 0 }}
\tevery_in_global_list = {{
\t\tvariable = {MOD_ID}_plan_touched
\t\tlimit = {{
\t\t\thas_variable = {MOD_ID}_load
\t\t\t{MOD_ID}_plan_is_town = no
\t\t\t{MOD_ID}_stands_{building} = yes
\t\t\tvar:{MOD_ID}_vb{k} > global_var:{MOD_ID}_rp_br
\t\t}}
\t\tset_global_variable = {{ name = {MOD_ID}_rp_br value = var:{MOD_ID}_vb{k} }}
\t}}
\tevery_in_global_list = {{
\t\tvariable = {MOD_ID}_plan_touched
\t\tlimit = {{
\t\t\thas_variable = {MOD_ID}_load
\t\t\tis_target_in_variable_list = {{ name = {MOD_ID}_plan_builds target = building_type:{building} }}
\t\t\tvar:{MOD_ID}_vb{k} < global_var:{MOD_ID}_rp_br
\t\t}}
\t\tset_global_variable = {{ name = {MOD_ID}_rp_d value = global_var:{MOD_ID}_rp_br }}
\t\tchange_global_variable = {{ name = {MOD_ID}_rp_d subtract = var:{MOD_ID}_vb{k} }}
\t\tchange_global_variable = {{ name = {MOD_ID}_rp_vbound add = global_var:{MOD_ID}_rp_d }}
\t\tchange_global_variable = {{ name = {MOD_ID}_rp_vmoves add = 1 }}
\t}}
""")
    out.append(park(1, f"{MOD_ID}_rp_bound"))
    out.append(park(2, f"{MOD_ID}_rp_moves"))
    out.append(park(3, f"{MOD_ID}_rp_right"))
    out.append(park(4, f"{MOD_ID}_plan_gain"))
    out.append(park(5, f"{MOD_ID}_plan_placed"))
    out.append(park(6, f"{MOD_ID}_rp_pbound"))
    out.append(park(7, f"{MOD_ID}_rp_vbound"))
    out.append(park(8, f"{MOD_ID}_rp_vmoves"))
    out.append(say(f"SHUFFLE bound={read(1)} moves={read(2)} in_charter_towns={read(3)}"
                   f" | villages={read(7)} village_moves={read(8)} (what the villages"
                   f" themselves stand to gain -- the trade ignores it on purpose)"
                   f" | same_province={read(6)} (must be 0 -- the gain is a province's,"
                   f" not a location's)"
                   f" | gain_now={read(4)} placed={read(5)} -- bound is the ceiling a"
                   f" reshuffle across provinces could add, out of {RANK_SCALE} a"
                   f" building, counted per side; it ignores that a good's buildings"
                   f" cannot all crowd into one province, so a real trade is far less"))
    out.append("}\n")
    return "".join(out)


# ------------------------------------------------------------------ the summary
#
# **Одно окно, в котором план видно целиком, а не по локациям.** Его слова
# 2026-09-07: «сам план как таковой довольно жирный, подробный — но вот какой-то
# сводки я не вижу по товарам… мне важно сравнивать. И тогда я смогу более
# наглядно делать тесты на разной земле».
#
# **Строка на товар, выписанная, а не из датамодели** — по той же причине, что
# ячейки редактора: строка датамодели несёт скоуп товара, а скоуп не достаёт до
# нумерованной глобалки `_pn<n>`.
#
# **И причина остановки у каждой.** Это половина просьбы и та, ради которой
# окно вообще стоит строить: число без причины не говорит, землю ли не хватило,
# долю ли выбрали или товар закреплён рукой.

SUMMARY_OUT = MOD / "in_game/common/scripted_effects/bag_wtp_generated_summary.txt"
SUM_CELLS_OUT = MOD / "in_game/gui/bag_wtp_sum_cells.gui"

# Ширины столбцов сводки. Сумма плюс промежутки не должна превышать ширину окна
# минус рамку -- `docs/pitfalls/windows.md`, правило 3.
# **Город и село — отдельные столбцы, и рядом с «всего» стоит чистое число
# домиков.** Его просьба 2026-09-08: «стоит разделить в таблице на отдельные
# город и село вместо одной город/село и так же столбик с общим реальным
# количеством без РГО».
SUM_COLS = ((180, "name"), (52, "n"), (56, "nb"), (50, "town"), (50, "rural"),
            (52, "places"), (44, "rgo"), (58, "qraw"), (66, "quota"),
            (66, "qt"), (66, "qr"), (52, "gain"), (420, "why"))
SUM_SPACING = 6
# **Вторая страница сводки: столбцы грамоты.** Не те же, что у товара, и не
# могут быть теми же: у грамоты нет ни сторон, ни РГО, ни потолков — есть
# сколько выдано, сколько положено, скольким городам она вообще подходит и
# сколько платит лучший из них.
# **Значка карты в строке грамоты нет, и он тут был зря.** Девять детских карт
# открываются полосой значков над баннером режима карты -- ровно так, как у него
# в CM dev (`bag_wtp_trmm_search_panel.gui`): включил «Лучшее городское право» из
# флайаута, и полоса появилась. Его слово, 2026-09-14: «Ну… это работает. Хотя я
# не особо понимаю зачем. Почему ты не сделал так, как оно было в CM DEV?»
RSUM_COLS = ((300, "rname"), (70, "rgiven"), (70, "rquota"), (80, "rfit"),
             (80, "rtop"), (420, "rwhy"))
SUM_ROW_W = sum(w for w, _ in SUM_COLS) + SUM_SPACING * (len(SUM_COLS) - 1)
RSUM_ROW_W = sum(w for w, _ in RSUM_COLS) + SUM_SPACING * (len(RSUM_COLS) - 1)
SUM_WINDOW_W = 1460
assert SUM_ROW_W <= SUM_WINDOW_W - 40, (SUM_ROW_W, SUM_WINDOW_W)
assert RSUM_ROW_W <= SUM_WINDOW_W - 40, (RSUM_ROW_W, SUM_WINDOW_W)


def summary_file(rows: list[eu5data.Method], split: dict[str, list[str]],
                 game: eu5data.Game) -> str:
    """Что сводка считает: причину остановки на товар и четыре числа в шапку."""
    order = goods_order(split)
    groups = plan_groups(rows, split, game)
    sides = own_sides(rows, split, game)
    out = [HEADER, "#\n# The plan's summary: one row a good, and why each stopped\n# where it did.\n"]
    out.append(f"""
# **Считается на открытие окна и больше нигде.** Один обход по кандидатам на
# товар -- это единственное дорогое, что здесь есть, и платить за него на каждом
# «+1» незачем: сводка отвечает на вопрос, который задают глазами.
#
# **Причина -- число, а рисует её `{MOD_ID}_why_<n>`**, диспетчер локализации на
# товар. Флаг на каждую причину стоил бы шести глобалок на товар вместо одной, а
# `visible` всё равно умеет только `.IsSet`.
#
# 1 -- земля этого не производит вовсе; 2 -- стоит во всех своих местах;
# 10 -- мест не осталось, но его места разобрали другие;
# 3 -- выбрана своя доля; 4 -- выбран городской потолок; 5 -- сельский;
# 6 -- закреплён в редакторе; 7 -- помечен «не нужен»; 9 -- специализация
# перебила его в каждой свободной ячейке; 8 -- ничего из этого, то есть
# раздача встала раньше, чем товар упёрся хоть во что-то.
# Scope: country
{MOD_ID}_plan_summary = {{
\tset_global_variable = {{ name = {MOD_ID}_sum_min value = 9999 }}
\tset_global_variable = {{ name = {MOD_ID}_sum_max value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_sum_zero value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_sum_full value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_sum_goods value = 0 }}
\t# **Разрыв считается по сторонам отдельно, и это его правка 2026-09-07.**
\t# «Меньше всех 12, больше всех 63» на одной шкале -- это не разброс, а
\t# разница между «только городским» и «умеющим в село»: у первых потолок в
\t# городских комнатах, у вторых в сельских, и сравнивать их между собой
\t# нечего. Два числа на сторону отвечают на «ровно ли вышло» по-настоящему.
\tset_global_variable = {{ name = {MOD_ID}_sum_tmin value = 9999 }}
\tset_global_variable = {{ name = {MOD_ID}_sum_tmax value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_sum_tg value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_sum_rmin value = 9999 }}
\tset_global_variable = {{ name = {MOD_ID}_sum_rmax value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_sum_rg value = 0 }}
\tremove_global_variable = {MOD_ID}_sum_any
""")
    for index, good in enumerate(order, start=1):
        town, rural = sides[good]
        can = " ".join(f"{MOD_ID}_plan_can_{side}_{index} = yes"
                       for side, has in (("town", town), ("rural", rural)) if has)
        # **Товар, у которого нет ни одного своего здания, в сводку не
        # попадает вовсе** -- у него `_ng = 0`, как у шёлка. Строку всё равно
        # надо собрать, а пустой `OR` спрашивать нельзя.
        noside = ""
        if not town and not rural:
            can = "always = no"
        caps = ""
        if town:
            caps += f"""\t\telse_if = {{
\t\t\tlimit = {{ NOT = {{ global_var:{MOD_ID}_pnt{index} < global_var:{MOD_ID}_pqt{index} }} }}
\t\t\tset_global_variable = {{ name = {MOD_ID}_wr{index} value = 4 }}
\t\t}}
"""
        if rural:
            caps += f"""\t\telse_if = {{
\t\t\tlimit = {{ NOT = {{ global_var:{MOD_ID}_pnr{index} < global_var:{MOD_ID}_pqr{index} }} }}
\t\t\tset_global_variable = {{ name = {MOD_ID}_wr{index} value = 5 }}
\t\t}}
"""
        out.append(f"""\t# {good}
\tremove_global_variable = {MOD_ID}_sum{index}
\tremove_global_variable = {MOD_ID}_wsp{index}
\tset_global_variable = {{ name = {MOD_ID}_wr{index} value = 8 }}
\tif = {{
\t\tlimit = {{ global_var:{MOD_ID}_ng{index} = 0 }}
\t\tset_global_variable = {{ name = {MOD_ID}_wr{index} value = 1 }}
\t}}
\telse = {{
\t\tset_global_variable = {{ name = {MOD_ID}_sum{index} value = 1 }}
\t\tset_global_variable = {{ name = {MOD_ID}_sum_any value = 1 }}
\t\tchange_global_variable = {{ name = {MOD_ID}_sum_goods add = 1 }}
\t\tif = {{
\t\t\tlimit = {{ global_var:{MOD_ID}_pn{index} < global_var:{MOD_ID}_sum_min }}
\t\t\tset_global_variable = {{ name = {MOD_ID}_sum_min value = global_var:{MOD_ID}_pn{index} }}
\t\t}}
\t\tif = {{
\t\t\tlimit = {{ global_var:{MOD_ID}_pn{index} > global_var:{MOD_ID}_sum_max }}
\t\t\tset_global_variable = {{ name = {MOD_ID}_sum_max value = global_var:{MOD_ID}_pn{index} }}
\t\t}}
\t\tif = {{
\t\t\tlimit = {{ global_var:{MOD_ID}_pn{index} = 0 }}
\t\t\tchange_global_variable = {{ name = {MOD_ID}_sum_zero add = 1 }}
\t\t}}
\t\t# Сторона учитывается, только если земля даёт товару хоть одно место на
\t\t# ней: иначе «минимум по городу» ловил бы нули чисто сельских товаров.
\t\tif = {{
\t\t\tlimit = {{ global_var:{MOD_ID}_ngt{index} > 0 }}
\t\t\tchange_global_variable = {{ name = {MOD_ID}_sum_tg add = 1 }}
\t\t\tif = {{
\t\t\t\tlimit = {{ global_var:{MOD_ID}_pnt{index} < global_var:{MOD_ID}_sum_tmin }}
\t\t\t\tset_global_variable = {{ name = {MOD_ID}_sum_tmin value = global_var:{MOD_ID}_pnt{index} }}
\t\t\t}}
\t\t\tif = {{
\t\t\t\tlimit = {{ global_var:{MOD_ID}_pnt{index} > global_var:{MOD_ID}_sum_tmax }}
\t\t\t\tset_global_variable = {{ name = {MOD_ID}_sum_tmax value = global_var:{MOD_ID}_pnt{index} }}
\t\t\t}}
\t\t}}
\t\tif = {{
\t\t\tlimit = {{ global_var:{MOD_ID}_ngr{index} > 0 }}
\t\t\tchange_global_variable = {{ name = {MOD_ID}_sum_rg add = 1 }}
\t\t\tif = {{
\t\t\t\tlimit = {{ global_var:{MOD_ID}_pnr{index} < global_var:{MOD_ID}_sum_rmin }}
\t\t\t\tset_global_variable = {{ name = {MOD_ID}_sum_rmin value = global_var:{MOD_ID}_pnr{index} }}
\t\t\t}}
\t\t\tif = {{
\t\t\t\tlimit = {{ global_var:{MOD_ID}_pnr{index} > global_var:{MOD_ID}_sum_rmax }}
\t\t\t\tset_global_variable = {{ name = {MOD_ID}_sum_rmax value = global_var:{MOD_ID}_pnr{index} }}
\t\t\t}}
\t\t}}
\t\t# **Осталось ли товару хоть одно свободное место.** Тот же вопрос, что
\t\t# задаёт себе раздача, но заданный сейчас: `_px<s><n>` живёт внутри
\t\t# `{MOD_ID}_plan_allocate` и о правках редактора не знает.
\t\t#
\t\t# **По `_plan_touched`, а не по `_candidates`.** Земля плана -- это то, на
\t\t# чём план стоит, а список кандидатов идёт за текущим выбором на карте:
\t\t# клик по соседней провинции после расчёта переписал бы его, и сводка
\t\t# начала бы отвечать про землю, которой в плане нет.
\t\tevery_in_global_list = {{
\t\t\tvariable = {MOD_ID}_plan_touched
\t\t\tlimit = {{ OR = {{ {can} }} }}
\t\t\tset_global_variable = {{ name = {MOD_ID}_wsp{index} value = 1 }}
\t\t}}
\t\t# **«Мест не осталось» -- это два разных ответа, и владелец поймал их
\t\t# слитыми 2026-09-07: «у всех одна причина остановки, которая по сути
\t\t# говорит что кончилось место».** Товар, стоящий во всех своих местах,
\t\t# и товар, чьи места разобрали другие, остановились по разным причинам,
\t\t# и вопрос «почему рыбы 18, а железа 39» отвечается только вторым.
\t\tif = {{
\t\t\tlimit = {{
\t\t\t\tNOT = {{ has_global_variable = {MOD_ID}_wsp{index} }}
\t\t\t\tNOT = {{ global_var:{MOD_ID}_pn{index} < global_var:{MOD_ID}_ng{index} }}
\t\t\t}}
\t\t\tset_global_variable = {{ name = {MOD_ID}_wr{index} value = 2 }}
\t\t\tchange_global_variable = {{ name = {MOD_ID}_sum_full add = 1 }}
\t\t}}
\t\telse_if = {{
\t\t\tlimit = {{ NOT = {{ has_global_variable = {MOD_ID}_wsp{index} }} }}
\t\t\tset_global_variable = {{ name = {MOD_ID}_wr{index} value = 10 }}
\t\t}}
\t\t# **В специализации доли и потолков не было, поэтому и причины такой
\t\t# быть не может.** Товар, у которого места есть, а домиков нет, там
\t\t# проиграл соревнование за каждую свободную ячейку -- и это отдельный
\t\t# ответ, а не «ни во что не упёрся».
\t\telse_if = {{
\t\t\tlimit = {{ has_global_variable = {MOD_ID}_spec_ran }}
\t\t\tset_global_variable = {{ name = {MOD_ID}_wr{index} value = 9 }}
\t\t}}
\t\telse_if = {{
\t\t\tlimit = {{ NOT = {{ global_var:{MOD_ID}_pn{index} < global_var:{MOD_ID}_pq{index} }} }}
\t\t\tset_global_variable = {{ name = {MOD_ID}_wr{index} value = 3 }}
\t\t}}
{caps}\t}}
{noside}\t# Пометки редактора перекрывают всё: это ответ игроку про его же решение.
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_lock{index} }}
\t\tset_global_variable = {{ name = {MOD_ID}_wr{index} value = 6 }}
\t}}
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_skip{index} }}
\t\tset_global_variable = {{ name = {MOD_ID}_wr{index} value = 7 }}
\t}}
""")
    # ---- вторая страница сводки: грамоты ----------------------------------
    #
    # **Столько же чисел на грамоту, сколько на товар, и по той же причине.**
    # Его слово 2026-09-12: «в общую сводку нужно добавить вторую страницу, в
    # которой будет списком показана статистика по городским правам в области,
    # аналогично сводке по товарам из плана».
    #
    # Считается тем же нажатием, что и товарная половина. Один обход по городам
    # на грамоту: `_rq<k>` уже посчитан планом, `_plan_right_fits_<k>` -- готовый
    # триггер локации, и оба читаются, а не считаются заново.
    #
    # **Причина у грамоты своя, пять веток**, и ни одна не повторяет товарную:
    # 1 -- держава её выдать не может вовсе; 2 -- ни один город этой земли ей не
    # подходит; 3 -- грамоты в этом плане не раздавались (галочка снята);
    # 4 -- выбрала свою квоту; 5 -- квота не выбрана, значит на остальных городах
    # её перебили те, кому земля платит больше.
    rights_calc = "".join(f"""\t# {right.key}
\tset_global_variable = {{ name = {MOD_ID}_rfit{k} value = 0 }}
\tset_global_variable = {{ name = {MOD_ID}_rtop{k} value = 0 }}
\tevery_in_global_list = {{
\t\tvariable = {MOD_ID}_candidates
\t\tlimit = {{
\t\t\t{MOD_ID}_plan_is_town = yes
\t\t\t{MOD_ID}_plan_right_won_{k} = yes
\t\t}}
\t\tchange_global_variable = {{ name = {MOD_ID}_rfit{k} add = 1 }}
\t\tif = {{
\t\t\tlimit = {{ {MOD_ID}_rq{k} > global_var:{MOD_ID}_rtop{k} }}
\t\t\tset_global_variable = {{ name = {MOD_ID}_rtop{k} value = {MOD_ID}_rq{k} }}
\t\t}}
\t}}
\tset_global_variable = {{ name = {MOD_ID}_rwhy{k} value = 5 }}
\tif = {{
\t\tlimit = {{ NOT = {{ has_global_variable = {MOD_ID}_plan_rights }} }}
\t\tset_global_variable = {{ name = {MOD_ID}_rwhy{k} value = 3 }}
\t}}
\telse_if = {{
\t\tlimit = {{ NOT = {{ global_var:{MOD_ID}_rgiven{k} < global_var:{MOD_ID}_rquota }} }}
\t\tset_global_variable = {{ name = {MOD_ID}_rwhy{k} value = 4 }}
\t}}
\tif = {{
\t\tlimit = {{ global_var:{MOD_ID}_rfit{k} = 0 }}
\t\tset_global_variable = {{ name = {MOD_ID}_rwhy{k} value = 2 }}
\t}}
\tif = {{
\t\tlimit = {{ NOT = {{ {MOD_ID}_plan_right_gate_{k} = yes }} }}
\t\tset_global_variable = {{ name = {MOD_ID}_rwhy{k} value = 1 }}
\t}}
""" for k, right in enumerate(output_rights(rows, game), start=1))
    out.append(f"""{rights_calc}\t# Пустая земля оставила бы 9999 на экране.
\tif = {{
\t\tlimit = {{ NOT = {{ has_global_variable = {MOD_ID}_sum_any }} }}
\t\tset_global_variable = {{ name = {MOD_ID}_sum_min value = 0 }}
\t}}
\tif = {{
\t\tlimit = {{ global_var:{MOD_ID}_sum_tg = 0 }}
\t\tset_global_variable = {{ name = {MOD_ID}_sum_tmin value = 0 }}
\t}}
\tif = {{
\t\tlimit = {{ global_var:{MOD_ID}_sum_rg = 0 }}
\t\tset_global_variable = {{ name = {MOD_ID}_sum_rmin value = 0 }}
\t}}
}}

# Scope: country
{MOD_ID}_open_summary_window_effect = {{
\t{MOD_ID}_plan_summary = yes
\tset_variable = {{ name = {MOD_ID}_sum_open value = 1 }}
}}

# Scope: country
{MOD_ID}_close_summary_window_effect = {{
\tremove_variable = {MOD_ID}_sum_open
}}
""")
    return "".join(out)


def sum_cells_file(rows: list[eu5data.Method], split: dict[str, list[str]],
                   game: eu5data.Game) -> str:
    """Строки сводки, по одной на товар, и одна коробка, которая держит их все."""
    order = goods_order(split)
    out = ["""# Generated by mods/where_to_produce/tools/generate.py. Do not edit by hand.
#
# Одна строка на товар для окна сводки. `bag_wtp_summary_window.gui` рисует
# рамку, шапку и заголовки столбцов; здесь только строки, поэтому `window` тут
# нет и в `gui/scripted_widgets/` этот файл не нужен.
#
# **Строка выписана, а не взята из датамодели.** Строка датамодели несёт скоуп
# товара, а скоуп не достаёт до нумерованной глобалки: `_pn<n>`, `_pq<n>` и
# причина остановки рисуются только отсюда.

types BagWtpSumCells {
"""]
    villages = village_entities(rows, split, game)
    shared_all = shared_buildings(rows, split, game)
    sides = own_sides(rows, split, game)
    for index, good in enumerate(order, start=1):
        # **Прочерк там, где товар не может стоять вовсе.** Его слова
        # 2026-09-08: «куча нулей меня напрягает... очевидно бумага не может
        # производится в сёлах». Ноль значит «может, но не встал»; прочерк --
        # «такой стороны у него нет». Село считается по своим зданиям: пиво в
        # селе делает торговая деревня, и это её домик.
        has_town, has_rural = sides[good]
        dashes = set()
        if not has_town:
            dashes |= {"town", "qt"}
        if not has_rural:
            dashes |= {"rural", "qr"}
        if not has_town and not has_rural:
            dashes |= {"qraw", "quota"}
        # **И прочерк в «РГО» у товара, у которого РГО не бывает.** Готовые
        # товары сырьём не лежат нигде и никогда: столбец нулей у двадцати
        # двух строк «отвлекает от чтения таблицы», 2026-09-08.
        if good not in game.raw_goods:
            dashes.add("rgo")
        cells = ""
        for width, kind in SUM_COLS:
            if kind in dashes:
                text, align, size = '"—"', "center|vcenter", 13
            elif kind == "why":
                text = f'"[GetPlayer.Custom(\'{MOD_ID}_why_{index}\')]"'
                align, size = "left|vcenter", 13
            elif kind == "quota":
                # **Тоже диспетчер**: «19» или «19-1», смотря добрал ли товар до
                # своего потолка. Условие внутри значения ключа сломало столбец
                # целиком, 2026-09-09.
                text = f'"[GetPlayer.Custom(\'{MOD_ID}_quota_{index}\')]"'
                align, size = "center|vcenter", 13
            elif kind == "name":
                text = f'"{MOD_ID}_good_{good}"'
                align, size = "left|vcenter", 14
            else:
                text = f'"{MOD_ID}_sum_{kind}_{index}"'
                align, size = ("center|vcenter", 15) if kind == "n" else ("center|vcenter", 13)
            cells += f"""\t\ttext_single = {{
\t\t\tsize = {{ {width} 26 }}
\t\t\tautoresize = no
\t\t\tmaximumsize = {{ {width} 26 }}
\t\t\talign = {align}
\t\t\tfontsize = {size}
\t\t\tfontsize_min = 10
\t\t\telide = right
\t\t\ttooltip = "{MOD_ID}_sum_{kind}_tt"
\t\t\ttext = {text}
\t\t}}

"""
        out.append(f"""\t# {good}
\ttype {MOD_ID}_sum_row{index} = hbox {{
\t\tsize = {{ {SUM_ROW_W} 26 }}
\t\tspacing = {SUM_SPACING}
\t\tvisible = "[GetGlobalVariable('{MOD_ID}_sum{index}').IsSet]"
\t\tusing = bg_number_container_bckg

{cells}\t}}

""")
    # **Деревня — такая же строка, как товар.** Его правило: «деревня = товар,
    # оно ничего не производит кроме самого себя». Числа берутся из её
    # собственных счётчиков: `_bn<b>` домиков, `_bq<b>` доля, `_ngv<k>` мест.
    for k, building in enumerate(villages, start=1):
        b = shared_all.index(building) + 1
        cells = ""
        for width, kind in SUM_COLS:
            if kind == "name":
                text, align, size = f'"{MOD_ID}_village_{building}"', "left|vcenter", 14
            elif kind == "why":
                text, align, size = f'"{MOD_ID}_why_village"', "left|vcenter", 13
            elif kind in ("n", "nb", "town", "rural", "places", "qraw",
                          "quota", "qt", "qr"):
                sv = ("[GuiScope.SetRoot(GetPlayer.MakeScope)"
                      ".ScriptValue('%s_show_%s')|0]")
                body = {"n": "#Y " + sv % (MOD_ID, "bn%d" % b) + "#!",
                        "nb": sv % (MOD_ID, "bn%d" % b),
                        "town": "—",
                        "rural": sv % (MOD_ID, "bn%d" % b),
                        "places": sv % (MOD_ID, "ngv%d" % k),
                        # Доля деревни -- сельская доля, и вычитать из неё
                        # нечего: РГО у деревни нет. Её собственный потолок --
                        # в столбце «доля село».
                        "qraw": sv % (MOD_ID, "qcapr"),
                        "quota": sv % (MOD_ID, "qcapr"),
                        "qt": "—",
                        "qr": sv % (MOD_ID, "bq%d" % b)}[kind]
                text = '"%s"' % body
                align = "center|vcenter"
                size = 15 if kind == "n" else 13
            else:
                text, align, size = '"—"', "center|vcenter", 13
            cells += f"""\t\ttext_single = {{
\t\t\tsize = {{ {width} 26 }}
\t\t\tautoresize = no
\t\t\tmaximumsize = {{ {width} 26 }}
\t\t\talign = {align}
\t\t\tfontsize = {size}
\t\t\tfontsize_min = 10
\t\t\telide = right
\t\t\ttooltip = "{MOD_ID}_sum_{kind}_tt"
\t\t\ttext = {text}
\t\t}}

"""
        out.append(f"""\t# {building}
\ttype {MOD_ID}_sum_vrow{k} = hbox {{
\t\tsize = {{ {SUM_ROW_W} 26 }}
\t\tspacing = {SUM_SPACING}
\t\tvisible = "[GreaterThan_int32(GuiScope.SetRoot(GetPlayer.MakeScope).ScriptValue('{MOD_ID}_show_ngv{k}'),'(int32)0')]"
\t\tusing = bg_number_container_bckg

{cells}\t}}

""")
    # **Заголовки столбцов — тоже отсюда.** Они были выписаны в окне руками, и
    # при первом же изменении `SUM_COLS` разъехались со строками: восемь
    # заголовков над десятью столбцами. Теперь у обоих один источник.
    head = ""
    for width, kind in SUM_COLS:
        align = "left|vcenter" if kind in ("name", "why") else "center|vcenter"
        head += f"""\t\ttext_single = {{
\t\t\tsize = {{ {width} 22 }}
\t\t\tautoresize = no
\t\t\tmaximumsize = {{ {width} 22 }}
\t\t\talign = {align}
\t\t\tfontsize = 13
\t\t\tfontsize_min = 10
\t\t\telide = right
\t\t\ttooltip = "{MOD_ID}_sum_{kind}_tt"
\t\t\ttext = "{MOD_ID}_sum_col_{kind}"
\t\t}}

"""
    out.append(f"""\t# Заголовки столбцов, теми же ширинами, что и строки.
\ttype {MOD_ID}_sum_head_row = hbox {{
\t\tsize = {{ {SUM_ROW_W} 22 }}
\t\tspacing = {SUM_SPACING}

{head}\t}}

""")
    # ---- вторая страница: строка на грамоту --------------------------------
    #
    # **Та же форма, что у товара, и ни одного общего столбца.** Грамота не
    # стоит в локации домиком: она свойство города, поэтому «город/село»,
    # «РГО» и потолки сторон у неё пусты по смыслу, а не по данным -- и
    # рисовать их прочерками значило бы половину таблицы прочерков.
    rights_all = output_rights(rows, game)
    for k, right in enumerate(rights_all, start=1):
        cells = ""
        for width, kind in RSUM_COLS:
            sv = ("[GuiScope.SetRoot(GetPlayer.MakeScope).ScriptValue('%s_show_%s')|0]")
            if kind == "rname":
                # Имя грамоты -- тот же ключ, которым её называет всё остальное
                # в моде (`_right_<key>`), а не второй его экземпляр.
                text, align, size = f'"{MOD_ID}_right_{right.key}"', "left|vcenter", 14
            elif kind == "rwhy":
                text = f'"[GetPlayer.Custom(\'{MOD_ID}_rwhy_{k}\')]"'
                align, size = "left|vcenter", 13
            else:
                body = {"rgiven": "#Y " + sv % (MOD_ID, f"rgiven{k}") + "#!",
                        "rquota": sv % (MOD_ID, "rquota"),
                        "rfit": sv % (MOD_ID, f"rfit{k}"),
                        "rtop": sv % (MOD_ID, f"rtop{k}")}[kind]
                text = '"%s"' % body
                align = "center|vcenter"
                size = 15 if kind == "rgiven" else 13
            cells += f"""\t\ttext_single = {{
\t\t\tsize = {{ {width} 26 }}
\t\t\tautoresize = no
\t\t\tmaximumsize = {{ {width} 26 }}
\t\t\talign = {align}
\t\t\tfontsize = {size}
\t\t\tfontsize_min = 10
\t\t\telide = right
\t\t\ttooltip = "{MOD_ID}_sum_{kind}_tt"
\t\t\ttext = {text}
\t\t}}

"""
        out.append(f"""\t# {right.key}
\ttype {MOD_ID}_sumr_row{k} = hbox {{
\t\tsize = {{ {RSUM_ROW_W} 26 }}
\t\tspacing = {SUM_SPACING}
\t\tusing = bg_number_container_bckg
\t\t# **Грамота, которой этой державе не видать, в сводку не идёт вовсе.**
\t\t# Его слово 2026-09-13: «у него как ни странно не должно быть никаких
\t\t# прав Константинополя и остальных не для его державы». `_right_ok<k>` --
\t\t# та же переменная, которой окно поиска гасит клетку недоступной грамоты;
\t\t# ставит её `_refresh_rights` по `potential` самой грамоты.
\t\tvisible = "[GetPlayer.MakeScope.GetVariable('{MOD_ID}_right_ok{k}').IsSet]"

{cells}\t}}

""")
    rhead = ""
    for width, kind in RSUM_COLS:
        align = "left|vcenter" if kind in ("rname", "rwhy") else "center|vcenter"
        rhead += f"""\t\ttext_single = {{
\t\t\tsize = {{ {width} 22 }}
\t\t\tautoresize = no
\t\t\tmaximumsize = {{ {width} 22 }}
\t\t\talign = {align}
\t\t\tfontsize = 13
\t\t\tfontsize_min = 10
\t\t\telide = right
\t\t\ttooltip = "{MOD_ID}_sum_{kind}_tt"
\t\t\ttext = "{MOD_ID}_sum_col_{kind}"
\t\t}}

"""
    out.append(f"""\t# Заголовки второй страницы, теми же ширинами, что и её строки.
\ttype {MOD_ID}_sumr_head_row = hbox {{
\t\tsize = {{ {RSUM_ROW_W} 22 }}
\t\tspacing = {SUM_SPACING}

{rhead}\t}}

""")
    rrowlist = "".join(f"\t\t{MOD_ID}_sumr_row{k} = {{}}\n"
                       for k in range(1, len(rights_all) + 1))
    out.append(f"""\t# Все строки грамот одной коробкой.
\ttype {MOD_ID}_sumr_all = vbox {{
\t\tspacing = 2
\t\tignoreinvisible = yes
{rrowlist}\t}}

""")

    rowlist = "".join(f"\t\t{MOD_ID}_sum_row{i} = {{}}\n"
                      for i in range(1, len(order) + 1))
    rowlist += "".join(f"\t\t{MOD_ID}_sum_vrow{k} = {{}}\n"
                       for k in range(1, len(villages) + 1))
    out.append(f"""\t# **Все строки одной коробкой, потому что окно написано руками.**
\t# `ignoreinvisible = yes` -- строка товара, которого эта земля не умеет,
\t# должна пропадать вместе со своим местом, иначе список весь в дырах.
\ttype {MOD_ID}_sum_all = vbox {{
\t\tspacing = 2
\t\tignoreinvisible = yes
{rowlist}\t}}
}}
""")
    return "".join(out)

def village_icons(rows, split, game) -> str:
    """`_vbt<k>` -- сам тип здания деревни, в глобалке, ради значка.

    **Значок здания в интерфейсе достаётся только со скоупа.** У товара есть
    тексикона в тексте (`@wheat!`), у здания её нет, а глобального промоута из
    имени в `BuildingType` в дампах игры нет вовсе -- значит нужен носитель, и
    им может быть только переменная. Ставится при регистрации, то есть на
    загрузке сохранения и при открытии страницы мода, и больше не меняется.
    """
    out = ["# Scope: country\n%s_init_vbt = {\n" % MOD_ID]
    for k, building in enumerate(village_entities(rows, split, game), start=1):
        out.append(f"\tset_global_variable = {{ name = {MOD_ID}_vbt{k} "
                   f"value = building_type:{building} }}\n")
    out.append("}\n")
    return "".join(out)


def village_values(rows, split, game) -> str:
    """Читалки для строк деревень в сводке: домиков, доля, мест."""
    out = []
    shared_all = shared_buildings(rows, split, game)
    for k, building in enumerate(village_entities(rows, split, game), start=1):
        b = shared_all.index(building) + 1
        out.append(f"# {building}\n"
                   f"{MOD_ID}_show_bn{b} = {{ value = global_var:{MOD_ID}_bn{b} }}\n"
                   f"{MOD_ID}_show_bq{b} = {{ value = global_var:{MOD_ID}_bq{b} }}\n"
                   f"{MOD_ID}_show_ngv{k} = {{ value = global_var:{MOD_ID}_ngv{k} }}\n")
    return "".join(out)


# ----------------------------------------------------------- the specialisation
#
# **Второй режим плана, и в нём нет ни одного правила равномерности.** Его слова
# 2026-09-07: «Это будет максимально специализированный режим заполнения. Тут
# равномерность и лимиты не значат ничего. Только максимально эффективная
# выжимка из провинции всех её бонусов. Если провинция идеально подходит для
# ремесленных прав — все города в ней будут ремесленных прав + лучший по бонусу
# РГО домики в свободные ячейки. Никаких правил, только выгода.»
#
# **Что он всё-таки сохраняет — «правила технического характера»**, его же
# оговорка: выбор земли, сохранение в слот, домиков на город и на село, пометка
# «не нужен», редактор поверх. Ровно они и остались.
#
# **Разница с обычным планом ровно в двух местах:**
#
# 1. **Грамоты выдаются по провинции, а не по городу.** Обычный проход обходит
#    города и держит лестницу уровней, чтобы счёта вышли ровными. Здесь провинция
#    считает среднюю оценку каждой грамоты по своим городам, берёт лучшую и даёт
#    её всем городам сразу -- это и есть «все города в ней будут ремесленных
#    прав».
# 2. **Комнаты заполняются от локации, а не от товара.** Обычная раздача ходит по
#    товарам и спрашивает «где моё лучшее место»; здесь ходит по локациям и
#    спрашивает «кто здесь платит больше всех». Ни квоты, ни ступеней, ни полос:
#    в каждую свободную ячейку встаёт лучший из тех, кто в неё влезает.
#
# **Ноль тоже ставится.** Товар, которому эта земля не платит ничего, всё равно
# занимает комнату, если лучше него никого нет: пустая комната -- это не
# специализация, а неиспользованная земля, и «эффективное использование земли»
# он назвал главным ещё 2026-09-07.

SPEC_OUT = MOD / "in_game/common/scripted_effects/bag_wtp_generated_spec.txt"

# Сколько раз проход обходит землю. Больше комнат в одной локации, чем позволяет
# больший из двух лимитов, не бывает, а лимит сверху -- 8; круг, который ничего
# не положил, выходит сам.
SPEC_ROUNDS = 12


def spec_file(rows: list[eu5data.Method], split: dict[str, list[str]],
              game: eu5data.Game) -> str:
    order = goods_order(split)
    groups = plan_groups(rows, split, game)
    rights = output_rights(rows, game)
    substitute = market_inputs(game)
    out = [HEADER, """#
# The specialisation plan: the ground squeezed for everything it pays, with no
# evenness of any kind. `docs/investigations/plan_specialisation.md`.
"""]

    # ---- грамоты по провинции ----------------------------------------------
    picks = ""
    for k, right in enumerate(rights, start=1):
        picks += f"""\t\t# {right.key}
\t\tset_global_variable = {{ name = {MOD_ID}_sprt value = 0 }}
\t\tset_global_variable = {{ name = {MOD_ID}_sprn value = 0 }}
\t\tprovince_definition = {{
\t\t\tevery_location_in_province_definition = {{
\t\t\t\tlimit = {{
\t\t\t\t\tis_target_in_global_variable_list = {{ name = {MOD_ID}_candidates target = this }}
\t\t\t\t\t{MOD_ID}_plan_is_town = yes
\t\t\t\t\t{MOD_ID}_plan_right_fits_{k} = yes
\t\t\t\t}}
\t\t\t\tchange_global_variable = {{ name = {MOD_ID}_sprt add = {MOD_ID}_rq{k} }}
\t\t\t\tchange_global_variable = {{ name = {MOD_ID}_sprn add = 1 }}
\t\t\t}}
\t\t}}
\t\tif = {{
\t\t\tlimit = {{
\t\t\t\tglobal_var:{MOD_ID}_sprn > 0
\t\t\t\tscope:{MOD_ID}_country = {{ {MOD_ID}_plan_right_gate_{k} = yes }}
\t\t\t}}
\t\t\t# Средняя по городам провинции, а не сумма: иначе крупная провинция
\t\t\t# выбирала бы грамоту числом городов, а не тем, что под ними лежит.
\t\t\tchange_global_variable = {{ name = {MOD_ID}_sprt divide = {MOD_ID}_sprn_value }}
\t\t\tif = {{
\t\t\t\tlimit = {{ global_var:{MOD_ID}_sprt > global_var:{MOD_ID}_sprv }}
\t\t\t\tset_global_variable = {{ name = {MOD_ID}_sprv value = global_var:{MOD_ID}_sprt }}
\t\t\t\tset_global_variable = {{ name = {MOD_ID}_sprk value = {k} }}
\t\t\t}}
\t\t\t# **И это же число -- в лесенку подсказки.** Она обязана показывать то,
\t\t\t# чем грамота выбрана, а выбрана она средним по городам провинции: пока
\t\t\t# в лесенке стоял счёт одной локации, она называла лучшей одну грамоту,
\t\t\t# а раздача ставила другую, и объяснить это было нечем.
\t\t\tprovince_definition = {{
\t\t\t\tevery_location_in_province_definition = {{
\t\t\t\t\t# Долей, как всюду: `_sprt` -- среднее из `_rq<k>`, а те из
\t\t\t\t\t# {RANK_SCALE}. Без деления лесенка печатала 90650 %.
\t\t\t\t\tset_variable = {{ name = {MOD_ID}_rqv{k} value = {{
\t\t\t\t\t\tvalue = global_var:{MOD_ID}_sprt
\t\t\t\t\t\tdivide = {RANK_SCALE}
\t\t\t\t\t}} }}
\t\t\t\t}}
\t\t\t}}
\t\t}}
\t\t# Не прошла ворота или ни один город не подошёл -- ноль, и лесенка её не
\t\t# покажет вовсе, потому что и получить её эта земля не может.
\t\telse = {{
\t\t\tprovince_definition = {{
\t\t\t\tevery_location_in_province_definition = {{
\t\t\t\t\tset_variable = {{ name = {MOD_ID}_rqv{k} value = 0 }}
\t\t\t\t}}
\t\t\t}}
\t\t}}
"""
    out.append(f"""
# Грамоты, выданные провинцией целиком.
#
# **Провинция выбирает одну грамоту и отдаёт её каждому своему городу.** Обычный
# проход (`{MOD_ID}_plan_grant_pass`) обходит города поодиночке и держит
# лестницу уровней, чтобы у каждой грамоты вышло примерно поровну городов; здесь
# лестницы нет вовсе -- есть только «что этой земле подходит лучше всего».
#
# **Оценка -- средняя по городам провинции**, а не сумма: сумма выбирала бы
# грамоту по числу городов, а не по тому, что под ними лежит.
#
# **`-1`, а не ноль, как начальное лучшее.** Земля, на которой ни одна грамота не
# стоит ничего, всё равно получает ту, что ей хоть как-то подходит: `_rq<k>`
# честно равен нулю на всей Вестфалии для ювелирки, и сравнение с нулём не дало
# бы ей ни одного города (это уже стоило прогона 2026-09-03).
# Scope: country
{MOD_ID}_plan_spec_rights = {{
\t# Лесенка в подсказке спрашивает ворота грамоты у державы.
\tsave_scope_as = {MOD_ID}_country
\tevery_in_global_list = {{
\t\tvariable = {MOD_ID}_plan_prov_locs
\t\tset_global_variable = {{ name = {MOD_ID}_sprv value = -1 }}
\t\tset_global_variable = {{ name = {MOD_ID}_sprk value = 0 }}
{picks}\t\t# Числа в `_rqv<k>` теперь провинции, значит и места пересчитываются
\t\t# по ним: иначе лесенка показывала бы новые проценты в старом порядке.
\t\tprovince_definition = {{
\t\t\tevery_location_in_province_definition = {{ {MOD_ID}_rq_rank = yes }}
\t\t}}
\t\t# И раздать выбранную всем городам провинции разом.
\t\tif = {{
\t\t\tlimit = {{ global_var:{MOD_ID}_sprk > 0 }}
\t\t\tprovince_definition = {{
\t\t\t\tevery_location_in_province_definition = {{
\t\t\t\t\tlimit = {{
\t\t\t\t\t\tis_target_in_global_variable_list = {{ name = {MOD_ID}_candidates target = this }}
\t\t\t\t\t\t{MOD_ID}_plan_is_town = yes
\t\t\t\t\t\tvar:{MOD_ID}_load = 0
\t\t\t\t\t}}
\t\t\t\t\t# Тот же ключ, что читает выкладка связки, -- и та же выкладка.
\t\t\t\t\tset_variable = {{ name = {MOD_ID}_rbest_k value = global_var:{MOD_ID}_sprk }}
{grant_bundle_blocks(rights, order, groups, substitute, chr(9) * 5)}\t\t\t\t\tremove_variable = {MOD_ID}_rbest_k
\t\t\t\t}}
\t\t\t}}
\t\t}}
\t}}
}}
""")

    # ---- лучший товар для этой локации --------------------------------------
    tries = ""
    for index, good in enumerate(order, start=1):
        for side, listname, score in (("t", "town", "p"), ("r", "rural", "pr")):
            if not groups.get((good, side)):
                continue
            tries += f"""\tif = {{
\t\tlimit = {{
\t\t\t{MOD_ID}_plan_can_{listname}_{index} = yes
\t\t\tvar:{MOD_ID}_{score}{index} > var:{MOD_ID}_specv
\t\t\tNOT = {{ has_global_variable = {MOD_ID}_skip{index} }}
\t\t}}
\t\tset_variable = {{ name = {MOD_ID}_specv value = var:{MOD_ID}_{score}{index} }}
\t\tset_variable = {{ name = {MOD_ID}_speck value = {index} }}
\t}}
"""
    places = ""
    for index, good in enumerate(order, start=1):
        inner = ""
        for side, listname in (("t", "town"), ("r", "rural")):
            if not groups.get((good, side)):
                continue
            inner += (f"\t\tif = {{\n"
                      f"\t\t\tlimit = {{ {MOD_ID}_plan_can_{listname}_{index} = yes }}\n"
                      f"\t\t\t{MOD_ID}_plan_try_{listname}_{index} = yes\n"
                      f"\t\t}}\n")
        if not inner:
            continue
        places += f"""\tif = {{
\t\tlimit = {{ var:{MOD_ID}_speck = {index} }}
{inner}\t}}
"""
    out.append(f"""
# Одна свободная ячейка этой локации -- лучшему из тех, кто в неё влезает.
#
# **Вопрос повёрнут наоборот, и в этом весь режим.** Обычная раздача ходит по
# товарам («где моё лучшее место?»); эта ходит по локациям («кто здесь платит
# больше всех?»). Поэтому здесь нет ни квот, ни ступеней, ни полос -- их незачем
# сравнивать: сравниваются сами выгоды, прямо в этой локации.
#
# **`-1` как начальное лучшее, а не ноль.** Товар с нулевой выгодой всё равно
# занимает комнату, если лучше него тут никого нет. Пустая комната -- это не
# специализация, а неиспользованная земля.
#
# **`_skip<n>` соблюдается.** «Не нужен» -- это стоячее указание игрока, а не
# правило равномерности, и режим «никаких правил» его не отменяет.
#
# **Сторона не спрашивается отдельно:** `_plan_can_town_<n>` уже несёт
# `{MOD_ID}_plan_is_town = yes`, а `_plan_can_rural_<n>` -- `= no`, так что
# городская и сельская ветки одного товара исключают друг друга сами.
# Scope: location
{MOD_ID}_plan_spec_best = {{
\tset_variable = {{ name = {MOD_ID}_specv value = -1 }}
\tset_variable = {{ name = {MOD_ID}_speck value = 0 }}
{tries}{places}\tremove_variable = {MOD_ID}_specv
\tremove_variable = {MOD_ID}_speck
}}

# Заполнение: круг за кругом, пока хоть одна ячейка берёт хоть что-то.
#
# **Круг кладёт не больше одного домика в локацию**, поэтому число кругов -- это
# самая заполненная локация, а не число домиков. Верхний предел -- больший из
# двух лимитов, то есть 8; {SPEC_ROUNDS} с запасом, и круг, ничего не положивший,
# выходит сам.
# Scope: country
{MOD_ID}_plan_spec_fill = {{
\tset_global_variable = {{ name = {MOD_ID}_plan_go value = 1 }}
\tset_global_variable = {{ name = {MOD_ID}_plan_laps value = 0 }}
\twhile = {{
\t\tlimit = {{
\t\t\tglobal_var:{MOD_ID}_plan_go = 1
\t\t\tglobal_var:{MOD_ID}_plan_laps < {SPEC_ROUNDS}
\t\t}}
\t\tchange_global_variable = {{ name = {MOD_ID}_plan_laps add = 1 }}
\t\tchange_global_variable = {{ name = {MOD_ID}_plan_sweeps add = 1 }}
\t\tset_global_variable = {{ name = {MOD_ID}_plan_added value = 0 }}
\t\tevery_in_global_list = {{
\t\t\tvariable = {MOD_ID}_candidates
\t\t\t{MOD_ID}_plan_spec_best = yes
\t\t}}
{"".join(f"		if = {{ limit = {{ global_var:{MOD_ID}_plan_laps = {lap} }} set_global_variable = {{ name = {MOD_ID}_lapn{lap} value = global_var:{MOD_ID}_plan_added }} }}" + chr(10) for lap in range(1, min(DIAG_LAPS, SPEC_ROUNDS) + 1))}\t\tif = {{
\t\t\tlimit = {{ global_var:{MOD_ID}_plan_added = 0 }}
\t\t\tset_global_variable = {{ name = {MOD_ID}_plan_go value = 0 }}
\t\t}}
\t}}
\tset_global_variable = {{ name = {MOD_ID}_plan_lvl value = global_var:{MOD_ID}_plan_laps }}
}}

# «Специализация» с страницы мода: тот же конвейер, две другие середины.
#
# **Всё остальное -- то же самое, и это его оговорка**: выбор земли, пометки
# город/село, лимиты домиков, сохранение в слот, редактор поверх и «Показать
# изменения» работают ровно как с обычным планом, потому что это тот же план,
# просто заполненный другим правилом.
#
# **`_plan_set_quota` вызывается, хотя раздача её не читает.** Числа доли нужны
# всему, что идёт после плана -- редактору, доливке и сводке, -- а сводка ещё и
# показывает их рядом с пометкой «режим специализации», чтобы было с чем
# сравнить обычный план на той же земле.
# Scope: country
{MOD_ID}_spec_run = {{
\tsave_scope_as = {MOD_ID}_country
\t{MOD_ID}_collect_candidates = yes
\t{MOD_ID}_rebuild_browse = yes
\t{MOD_ID}_plan_prepare = yes
\t{MOD_ID}_plan_score = yes
\tif = {{
\t\tlimit = {{ has_global_variable = {MOD_ID}_plan_rights }}
\t\t{MOD_ID}_plan_spec_rights = yes
\t}}
\t{MOD_ID}_plan_set_quota = yes
\t{MOD_ID}_plan_spec_fill = yes
\t# **И житницы, последними.** Их комнаты в раздаче не участвуют вовсе, и
\t# домики, которые сюда встанут, ни с кем за места не спорили: круг ходит
\t# только по помеченным локациям и ставит то, что растит еду или сам РГО.
\t{MOD_ID}_plan_fill_granaries = yes
\t{MOD_ID}_plan_rank = yes
\t# Свежий план -- своя же точка отсчёта для «Показать изменения».
\t{MOD_ID}_edit_save = yes
\t# **Ставится после `_plan_prepare`, который его снимает.** Так любой обычный
\t# «Пересчитать» гасит пометку сам, и окно не может назвать специализацией то,
\t# что ею не является.
\tset_global_variable = {{ name = {MOD_ID}_spec_ran value = 1 }}
\tset_global_variable = {{ name = {MOD_ID}_plan_mode value = 1 }}
\tcmf_log = {{ action = {MOD_ID}_log_plan }}
}}
""")
    return "".join(out)

def main() -> int:
    # **Здания чужих модов идут в план наравне со своими -- но не их товары.**
    #
    # Владелец, 2026-09-09: «нужно, чтобы мод сканировал другие моды на наличие
    # производственных зданий... и вставлял их в план наравне со всеми». Читает
    # их `eu5data.load_game`, кладя `common/` каждого мода из `reference/mods`
    # поверх игровой -- ровно как их кладёт сама игра.
    #
    # **Товар, которого нет у игры, в список не входит, и это не выбор, а
    # потолок.** CMM обрабатывает клик по строке списка до пятидесятой и дальше
    # нет; у игры 47 товаров, а моды этого дерева довели бы список до 64. Поэтому
    # чужое здание попадает в план тогда, когда делает товар, который план и так
    # знает: соляная мастерская чужого мода -- да, товар, которого в игре нет, --
    # нет. Сколько таких отброшено, генератор печатает, чтобы это не было тихо.
    game = eu5data.load_game()
    core = eu5data.load_game(refs.GAME_COMMON, [])
    known = {good for method in methods(core) for good in method.produced.split()}
    rows_all = methods(game)
    rows = [m for m in rows_all if set(m.produced.split()) & known]
    dropped = sorted({m.building for m in rows_all} - {m.building for m in rows})
    split = goods_split(rows, game)

    # **What the generator would otherwise get wrong quietly**, checked once here
    # rather than found in a log. Every one of these is a number the game supplies
    # and the mod caps; a patch that raises the game's side has to raise the cap
    # with it, and a build that says so is cheaper than a run that does not.
    rights = output_rights(rows, game)
    assert len(rights) <= DIAG_SCRATCH, (
        f"{len(rights)} urban rights and only {DIAG_SCRATCH} scratch globals: the "
        f"`WTP RQ` line parks one score per charter, so raise `DIAG_SCRATCH`")
    assert len(split["raw"]) + len(split["made"]) <= LIST_CAP, (
        f"{len(split['raw']) + len(split['made'])} goods against a list of "
        f"{LIST_CAP}: CMM handles a row click to fifty and no further")
    # **The two pickers are rows of a fixed count and the windows name them one
    # by one**, so a game with more goods or more rights than the rows hold
    # would simply stop drawing the extra ones -- silently, since a cell that is
    # never written is a cell nothing complains about.
    assert edit_rows(len(goods_order(split))
                     + len(village_entities(rows, split, game))) <= 5, (
        "the editor's picker needs more than five rows, and "
        "`bag_wtp_edit_window.gui` names them one by one")
    assert len(goods_order(split)) <= PICK_ROW * PICK_ROWS, (
        f"{len(goods_order(split))} goods and only {PICK_ROW * PICK_ROWS} cells "
        f"in the search picker: raise `PICK_ROWS` and add the row to both "
        f"ranking windows")
    assert len(rights) <= RIGHT_PICK_COL * RIGHT_PICK_COLS, (
        f"{len(rights)} urban rights and only "
        f"{RIGHT_PICK_COL * RIGHT_PICK_COLS} cells in the search picker: raise "
        f"`RIGHT_PICK_COL` and make both ranking windows taller")
    assert max(len(r.output) for r in rights) <= RIGHT_SLOTS, (
        f"a charter favours more than {RIGHT_SLOTS} goods the mod can make; a row "
        f"holds a fixed number of answers, so raise `RIGHT_SLOTS`")

    by_continent = regions()
    write(ZONE_OUT, zone_file() + clear_ticks_effect())
    write(SOURCES_OUT, sources_file(rows))
    write(FOODPOT_OUT, food_potential_file())
    write(REGION_OUT, region_file(by_continent))
    write(TRIGGERS_OUT, triggers_file(rows, split, game))
    write(PICKER_OUT, picker_file(split, rows))
    write(VALUES_OUT, values_file(rows, split, game) + village_values(rows, split, game) + "".join(
        f"# How many buildings of {good} the plan holds. Printed in the picker's\n"
        f"# own cell, which is why the cells are written out: a datamodel row\n"
        f"# carries a goods scope and a scope reaches no numbered counter.\n"
        f"# Scope: country\n"
        f"{MOD_ID}_show_pn{i} = {{ value = global_var:{MOD_ID}_pn{i} }}\n"
        f"# Домики плюс уже стоящие РГО -- то число, по которому судят о\n"
        f"# равномерности. Складывает его `{MOD_ID}_plan_rank`, здесь только чтение.\n"
        f"{MOD_ID}_show_tot{i} = {{ value = global_var:{MOD_ID}_tot{i} }}\n"
        f"# Недобор до своего потолка: комнат на стороне на все потолки не хватает.\n"
        f"{MOD_ID}_show_short{i} = {{ value = global_var:{MOD_ID}_short{i} }}\n"
        for i, good in enumerate(goods_order(split), start=1))
        + "".join(
        f"# How many towns hold {right.key} right now, printed in its own cell.\n"
        f"# Scope: country\n"
        f"{MOD_ID}_show_rgiven{k} = {{ value = global_var:{MOD_ID}_rgiven{k} }}\n"
        f"# Сколько городов этой земли ей вообще подходят, и сколько платит\n"
        f"# лучший из них -- вторая страница сводки.\n"
        f"{MOD_ID}_show_rfit{k} = {{ value = global_var:{MOD_ID}_rfit{k} }}\n"
        f"{MOD_ID}_show_rtop{k} = {{ value = global_var:{MOD_ID}_rtop{k} }}\n"
        for k, right in enumerate(output_rights(rows, game), start=1))
        + f"# Квота грамот: сколько городов (или провинций) приходится на одну.\n"
          f"# Scope: country\n"
          f"{MOD_ID}_show_rquota = {{ value = global_var:{MOD_ID}_rquota }}\n"
        # **Пять чисел строки сводки.** Всё, что нужно, чтобы сравнить товар с
        # товаром: сколько стоит, где стоит, сколько мест есть, сколько
        # положено и что земля за него платит.
        + "".join(
        f"# {good} в сводке: город, село, мест на земле, доля, лучшая выгода.\n"
        f"# Scope: country\n"
        f"{MOD_ID}_show_pnt{i} = {{ value = global_var:{MOD_ID}_pnt{i} }}\n"
        f"# Потолки сторон: к чему домик стремится в городе и в селе.\n"
        f"{MOD_ID}_show_pqt{i} = {{ value = global_var:{MOD_ID}_pqt{i} }}\n"
        f"{MOD_ID}_show_pqr{i} = {{ value = global_var:{MOD_ID}_pqr{i} }}\n"
        f"{MOD_ID}_show_pnr{i} = {{ value = global_var:{MOD_ID}_pnr{i} }}\n"
        f"{MOD_ID}_show_ng{i} = {{ value = global_var:{MOD_ID}_ng{i} }}\n"
        f"{MOD_ID}_show_nrgo{i} = {{ value = global_var:{MOD_ID}_nrgo{i} }}\n"
        f"{MOD_ID}_show_pq{i} = {{ value = global_var:{MOD_ID}_pq{i} }}\n"
        f"# Та же доля до скидки за РГО: сумма долей сторон, где товар умеет.\n"
        f"{MOD_ID}_show_pqraw{i} = {{ value = global_var:{MOD_ID}_pqraw{i} }}\n"
        # `_pbest` -- доля от `RANK_SCALE`; на экране это проценты.
        f"{MOD_ID}_show_gain{i} = {{ value = global_var:{MOD_ID}_pbest{i} "
        f"divide = {RANK_SCALE // 100} }}\n"
        for i, good in enumerate(goods_order(split), start=1))
        # И шапка сводки: ровность одной строкой.
        + "".join(
        f"# Scope: country\n{MOD_ID}_show_{name} = {{ value = global_var:{MOD_ID}_{name} }}\n"
        for name in ("sum_min", "sum_max", "sum_zero", "sum_full", "sum_goods",
                     "sum_tmin", "sum_tmax", "sum_tg",
                     "sum_rmin", "sum_rmax", "sum_rg",
                     # Что дала последняя «Перетасовка».
                     "ps_gain", "ps_swaps", "ps_rswaps",
                     # Шаг 8: сколько локаций помечено под автострой и сколько
                     # ушло в очередь CM в прошлый месяц.
                     "cm_all", "cm_did")))
    write(SCORE_OUT, score_file(rows, split, game))
    write(ROWS_OUT, rows_file())
    write(GUIS_OUT, guis_file(by_continent) + "".join(
        f"""
# «{{'plus': '+1', 'minus': '−1'}}.get(what, 'не нужен')» for {good}, from the picker's own cell.
#
# **No saved scope.** The cell is written out and knows its number, so the
# bridge that carried `goods:{good}` as a scope is gone -- and with it the one
# thing between the press and the plan that could quietly not arrive.
{MOD_ID}_pick_{what}_{i} = {{
\tscope = country

\tis_shown = {{
\t\talways = yes
\t}}

\teffect = {{
\t\t{MOD_ID}_edit_{what}_{i} = yes
\t\t{MOD_ID}_recompute_live = yes
\t}}
}}
"""
        for i, good in enumerate(goods_order(split), start=1)
        for what in ("plus", "minus", "skip")) + "".join(
        f"""
# «{{'plus': '+1', 'minus': '−1'}}[what]» на {building}, из его собственной ячейки
# редактора. Деревня -- сущность, а не товар, поэтому у неё своя строка и свой
# номер в том же `_edit_good`.
{MOD_ID}_pick_{what}_{len(goods_order(split)) + k} = {{
\tscope = country

\tis_shown = {{
\t\talways = yes
\t}}

\teffect = {{
\t\t{MOD_ID}_edit_{what}_{len(goods_order(split)) + k} = yes
\t\t{MOD_ID}_recompute_live = yes
\t}}
}}
"""
        for k, building in enumerate(village_entities(rows, split, game), start=1)
        for what in ("plus", "minus")) + "".join(
        f"""
# «{{'plus': '+1', 'minus': '−1'}}[what]» on the {right.key} charter, from its own
# cell in the editor. **A charter is moved, never added**: «+1» takes the town
# where it would earn most away from a charter that has more than its share,
# «−1» hands its worst town to whichever charter is furthest below its own.
{MOD_ID}_right_{what}_{k} = {{
\tscope = country

\tis_shown = {{
\t\talways = yes
\t}}

\teffect = {{
\t\t{MOD_ID}_edit_right_{what}_{k} = yes
\t\t{MOD_ID}_recompute_live = yes
\t}}
}}
"""
        for k, right in enumerate(output_rights(rows, game), start=1)
        for what in ("plus", "minus")) + "".join(
        f"""
# «{{'plus': '+1', 'minus': '−1'}}[what]» на месте {p_slot} блока грамот. **Ячейка
# написана под место, а не под грамоту**: какая грамота на нём сидит, говорит
# `_rslot{p_slot}`, и диспетчер ниже попадает в её собственный эффект. Без этого
# невидимая ячейка держала бы своё место в ряду, а девять грамот из тринадцати
# вставали бы рваными столбцами -- 2026-09-06.
{MOD_ID}_right_{what}_slot_{p_slot} = {{
\tscope = country

\tis_shown = {{
\t\talways = yes
\t}}

\teffect = {{
""" + "".join(
            f"\t\tif = {{ limit = {{ global_var:{MOD_ID}_rslot{p_slot} = {k} }} "
            f"{MOD_ID}_edit_right_{what}_{k} = yes }}\n"
            for k in range(1, len(output_rights(rows, game)) + 1)) + f"""\t\t{MOD_ID}_recompute_live = yes
\t}}
}}
"""
        for p_slot in range(1, len(output_rights(rows, game)) + 1)
        for what in ("plus", "minus")) + "".join(
        f"""
# {good} in the ranking window's picker. One circle, one number.
{MOD_ID}_pick_good_{i} = {{
\tscope = country

\tis_shown = {{
\t\talways = yes
\t}}

\teffect = {{
\t\t{MOD_ID}_set_good_{i} = yes
\t}}
}}
"""
        for i, good in enumerate(goods_order(split), start=1)) + "".join(
        f"""
# {right.key} in the ranking window's picker.
{MOD_ID}_pick_right_{i} = {{
\tscope = country

\tis_shown = {{
\t\talways = yes
\t}}

\teffect = {{
\t\t{MOD_ID}_set_right_{i} = yes
\t}}
}}
"""
        for i, right in enumerate(output_rights(rows, game), start=1)))
    write(LAYOUT_OUT, layout_file(by_continent))
    write(RIGHTS_OUT, rights_file(rows, split, game))
    write(PLAN_OUT, plan_file(rows, split, game) + village_icons(rows, split, game))
    write(SWAP_OUT, swap_file(rows, split, game))
    write(SWAP_VALUES_OUT, swap_values_file(rows, split, game))
    write(COV_OUT, cov_file(rows, split, game))
    write(PLAN_TRIGGERS_OUT, plan_triggers_file(rows, split, game))
    write(PLAN_LOC_OUT, plan_loc_file(rows, split, game))
    write(DIAG_OUT, diag_file(rows, split, game, methods(core)))
    effects, triggers = editor_file(rows, split, game)
    write(EDITOR_OUT, effects)
    write(EDITOR_TRIGGERS_OUT, triggers)
    write(EDIT_CELLS_OUT, edit_cells_file(goods_order(split), output_rights(rows, game),
                                         village_entities(rows, split, game)))
    write(PICK_CELLS_OUT, pick_cells_file(goods_order(split), rights))
    write(SUMMARY_OUT, summary_file(rows, split, game))
    write(SUM_CELLS_OUT, sum_cells_file(rows, split, game))
    write(SPEC_OUT, spec_file(rows, split, game))
    for language in LOC_LANGUAGES:
        write(Path(str(LOC_OUT) % (language, language)),
              loc_file(language, rows, split, game))

    # ---- the build stamp, and it is a probe before it is a nicety -----------
    #
    # **«Правка не работает» and «он запускал прошлую сборку» look identical
    # from here**, and on 2026-09-05 two reports could not be told apart: the
    # aligned columns and the yellow pin were correct in the tree and absent on
    # his screen. Asking him to prove which build he ran costs him a round trip
    # every time; a stamp on the window costs nothing and every screenshot
    # carries it.
    #
    # **Hashed from the built files, not from git.** A commit id would change on
    # every commit and make `refresh.py` report a change that means nothing; a
    # content hash moves only when the mod itself does, which is exactly the
    # question. The stamp's own file is written after the hash is taken, so it
    # cannot hash itself.
    stamped = sorted(
        q for q in list((MOD / "in_game").rglob("*"))
        + list((MOD / "main_menu").rglob("*"))
        if q.is_file() and q.suffix in (".txt", ".gui", ".yml")
        and not q.name.startswith(f"{MOD_ID}_build"))
    digest = hashlib.sha256()
    for q in stamped:
        digest.update(q.relative_to(MOD).as_posix().encode())
        digest.update(q.read_bytes())
    stamp = digest.hexdigest()[:6]
    for language in LOC_LANGUAGES:
        write(MOD / f"main_menu/localization/{language}/{MOD_ID}_build_l_{language}.yml",
              f"l_{language}:\n {MOD_ID}_build: \"{stamp}\"\n")
    print(f"build {stamp}, hashed from {len(stamped)} files")

    print(f"{sum(len(v) for v in by_continent.values())} regions in "
          f"{len(by_continent)} lists, {len(UNLOCKS)} methods gated by an advance")
    rural = sum(1 for m in rows if m.building_category in RURAL_CATEGORIES)
    if dropped:
        print(f"{len(dropped)} building(s) of other mods left out: they make no "
              f"good the game itself has, and the picker list stops at {LIST_CAP}")
    # **Чужой `allow`, который никто не перевёл, обязан быть виден.** Он
    # заперт для игрока и открыт для мода -- ровно та тишина, которой в этом
    # моде уже стоила «Мериносовая шерсть». Гадать за него нельзя, молчать о
    # нём тоже.
    if UNREAD_ALLOWS:
        print(f"{len(UNREAD_ALLOWS)} method allow(s) not translated into a gate "
              f"-- the method is offered to everyone:")
        for key, body in sorted(UNREAD_ALLOWS.items()):
            print(f"  {key}: {body}")
    print(f"{len(rows)} methods scored, {rural} of them in a village, "
          f"{len(split['raw'])} raw + {len(split['made'])} made goods, "
          f"{len(CONTINENTS)} continents, {RESULT_ROWS} provinces ranked, "
          f"{len(output_rights(rows, game))} urban rights")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
