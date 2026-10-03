# The honest market balance, for one country's own land

**Dropped on 2026-08-31, by the owner, on reading this file: «я думаю это пока
того не стоит».** What was built instead is a fourth picker — «Выбрать рынок» —
so that the mod's own question can be asked over one market's ground. The market
panel's «Local balance» column, which he had been misreading as including
imports, answers the rest.

Kept because the survey below is the expensive part and the next person to want
this will want it again, not because anything here is planned.

What the owner asked for on 2026-08-31: a table saying how much of each good
**his own territory** makes and eats, with imports and exports taken out — so
that "no shortage of masonry" cannot mean "no shortage as long as the neighbour
who supplies it stays in my market".

This file is the survey that has to come before any of it is built. Nothing here
has been in the game; every claim is from `reference/game/docs/` or from the
game's own files, and the fidelity risks are named as risks.

## The part the game already answers, exactly

`Market.GetBalanceWithoutTrades(goods)` is **local production minus local
demand, imports and exports excluded** — the number the owner wanted, for the
whole market. Vanilla prints it in the market panel as a sortable «Local
balance» column, between «Stockpile» and «Imports»
(`panels/market/market_goods.gui:93`). Its four parts are separately readable
and all are `CFixedPoint`:

| what | function |
| --- | --- |
| local supply | `Market.GetProduced(goods)`, label `GetProducedLabel` |
| local demand | `Market.GetDemandNoTrades(goods)`, label `GetDemandLabelNoTrades` |
| supply from imports | `Market.GetSupplyImportOnly(goods)` |
| demand from exports | `Market.GetDemandExportOnly(goods)` |
| the balance of the first two | `Market.GetBalanceWithoutTrades(goods)` |

**Where the market is entirely one country's, that number already is the
answer.** Which is why it is also the yardstick: everything computed below has
to reproduce it, and cannot be trusted until it does.

## The part the game does not answer

**No per-country split of any of it exists as a number.** Every breakdown the
interface offers — `GetDemandInfoNoTradesByCountries`, `GetProducedInfo`,
`GetSupplyInfo`, `GetSurplusInformation` — returns `CString`, a formatted
tooltip. Script has `goods_supply_in_market(goods:x)` and
`goods_demand_in_market(goods:x)` as script values (Construction Manager uses
both, `cm_market_shortage_script_values.txt`), and those are market-wide and
include trade.

So a country-only figure has to be **rebuilt from the ground**, and the only
question worth asking about each piece is whether the engine hands it over as a
number.

## What can be counted, and how

| piece | how | confidence |
| --- | --- | --- |
| **which of the market is even mine** | `every_location_in_market`, ask each its owner | exact |
| **RGO output** | per owned location: its raw material, and `goods_output` — "how much goods the scope location produces" | exact, if `goods_output` means the RGO's own output |
| **building output** | `every_owned_building` (country scope) → `building_level`, the method it runs, and the per-level output this repository already parses out of `common/production_methods` | good, minus efficiency and staffing |
| **building input** | the same walk, the method's inputs per level. `building_goods_input` exists but is a total with no goods argument | same |
| **pop demand** | `demand_add` / `demand_multiply` per pop type, straight out of `common/goods` (56 goods carry one), times `pop_type_population_in_country` | **the risk.** See below |
| **army and navy upkeep** | `Country.GetArmyGoodsCostImpact`, `GetNavyGoodsCostImpact` | unchecked |
| **construction materials** | `every_construction_material_for_building_type`, `Location.GetUpgradeRGOConstructionDemand` | unchecked |

### Why pop demand is the risk

The data is right there in `common/goods` — `demand_add = { all = x nobles = y }`
and `demand_multiply` — but so are `winter_demand_modifier`,
`wealth_impact_threshold`, `development_threshold`,
`no_demand_if_no_market_availability`, and on top of them whatever country,
estate and law modifiers scale needs. `Pop.GetNeedsScaling` returns a `CString`,
so the engine will not simply say what the scaling came to.

**This is a reimplementation of the game's demand model, and it will be wrong
before it is right.** What makes it survivable is that the game prints the
answer: in a market whose locations are all the player's,
`Market.GetDemandNoTrades(goods)` **is** the number our sum has to equal.

## How to build it so that each step can be checked

Three slices, each one verifiable against a number already on screen, and none
of them worth starting before the one before it lines up.

1. **How much of the market is mine, and the game's own honest numbers.** No
   invented arithmetic at all: local balance, imports, exports per good, plus
   the share of the market's locations that the player owns. This alone answers
   the fear that started it — a neighbour's weapon smiths propping up the
   balance — because it says how exposed the market is.
2. **My buildings and my RGOs.** Add computed production and building
   consumption. **Check:** in a market that is entirely the player's, our
   production must equal `GetProducedLabel`. A gap is a missing source, and its
   size names it.
3. **My pops.** Add pop demand. **Check:** our consumption against
   `GetDemandLabelNoTrades`, same market. Whatever is still missing is one of
   the unchecked rows above, and the difference will say which.

**Do not skip to 3.** The whole reason this can be built at all is that slices 2
and 3 have an answer key; jumping to the end throws it away and leaves a table
of numbers nobody can falsify.
