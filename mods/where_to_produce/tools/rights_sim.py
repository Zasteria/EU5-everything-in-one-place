#!/usr/bin/env python3
"""Прогнать раздачу городских прав на числах из его дампа, не заходя в игру.

**Зачем это есть.** Раздача грамот -- единственная часть мода, про которую
нельзя сказать «правило верное» и на этом успокоиться: результат зависит от
того, что земля платит каждой грамоте, а это тринадцать чисел на провинцию,
которых в файлах нет. Два захода 2026-09-14 были потрачены на правки, которые
выглядели верными и на его земле не меняли ничего: сперва добавка отставшей
грамоте, которую не пускала полоса, потом та же добавка, одинаковая для шести
отставших сразу. Обе видны за секунду, если прогнать их на его числах.

**Дамп их печатает.** `WTP L <локация> ... prov_rank=<N>` и следующая строка
«права: <имя> <число> | ...» -- это `_rq<k>` каждой грамоты в этом городе, из
`RANK_SCALE`. Больше ничего и не нужно: провинциальная раздача берёт среднее по
городам провинции, и всё остальное -- лестница, полосы, отставание -- считается
здесь так же, как в `generate.py`.

    python3 tools/rights_sim.py <дамп>            # что было и что будет
    python3 tools/rights_sim.py <дамп> --ceilings # потолок каждой грамоты

**Считает, а не доказывает.** Совпало с реальным прогоном 2026-09-14 город в
город на режиме специализации (6/5/15/4/0/0/9/0/0); это и есть та проверка,
ради которой файл написан. Разойдётся с игрой -- значит разошёлся с
`generate.py`, и чинить надо здесь, а не верить числам.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

RANK_SCALE = 1000
BANDS = (800, 600, 400, 200, 0)
LAG_STEP = RANK_SCALE * 10

LOC = re.compile(r"WTP L (.+?) \((\d+)\) rank=\d+ town=(\d).*?prov_rank=(\d+)")
RIGHT = re.compile(r"(.+?)\s+(\d+)$")


def read(path: Path):
    """Провинции дампа: (номер, сколько городов, {грамота: средняя выгода})."""
    towns, cur = [], None
    for line in path.read_text(encoding="utf-8", errors="replace").split("\n"):
        hit = LOC.match(line)
        if hit:
            cur = {"town": hit.group(3) == "1", "prov": int(hit.group(4)), "rq": {}}
            towns.append(cur)
        elif line.strip().startswith("права:") and cur is not None:
            for part in line.split("права:", 1)[1].split("|"):
                # **«← выдано» помечает ту, что город и получил**, и без этой
                # строки парсер терял её у каждого города разом: маркер стоит
                # после числа, а число ищется до конца строки.
                part = part.replace("← выдано", "").strip()
                # «(не для этой державы)» -- грамота, которую раздача не тронет.
                if "(не для" in part:
                    continue
                named = RIGHT.match(part)
                if named:
                    cur["rq"][named.group(1).strip()] = int(named.group(2))
    by_prov: dict[int, list] = {}
    for town in towns:
        if town["town"]:
            by_prov.setdefault(town["prov"], []).append(town)
    keys = sorted({k for t in towns for k in t["rq"]})
    return keys, [(p, len(ts), {k: sum(t["rq"].get(k, 0) for t in ts) / len(ts)
                                for k in keys})
                  for p, ts in sorted(by_prov.items())]


def grant(keys, provs, ladder: bool, lag: str, fair: bool):
    """Та же раздача, что в `_plan_place_rights`, провинциальной стороной.

    `ladder` -- лестница уровней и полосы (их нет у старой специализации);
    `lag`    -- none / binary (обрыв «меньше половины») / graded (уклон);
    `fair`   -- галочка «Грамоты — поровну»: отставшей достаётся и та земля,
                которая ей не платит.
    """
    given = {k: 0 for k in keys}
    nprov = {k: 0 for k in keys}
    taken: dict[int, str] = {}
    quota = len(provs) / max(1, len(keys))

    def step(band: int, level: int, opening: bool) -> None:
        for number, size, pays in provs:
            if number in taken:
                continue
            most = max(given.values())
            best, winner = -1, None
            for k in keys:
                value = pays[k]
                if not opening and nprov[k] >= level:
                    continue
                behind = lag != "none" and given[k] * 2 < most
                earns = value > 0 or fair
                # Полоса отставшую не держит -- но только ту, у которой
                # провинция уже есть: не получившая ничего стоит в очереди.
                if value < band and not (behind and earns and nprov[k] > 0):
                    continue
                key = value
                if behind and earns:
                    key += (most - given[k]) * LAG_STEP if lag == "graded" else RANK_SCALE * 100
                if key > best:
                    best, winner = key, k
            if winner is None:
                continue
            taken[number] = winner
            given[winner] += size
            nprov[winner] += 1

    if ladder:
        level = 0
        while level < quota and level < 12:
            level += 1
            for band in BANDS:
                step(band, level, False)
        step(0, level, True)
    else:
        step(0, 0, True)
    return given


def show(name: str, keys, given) -> None:
    zero = sum(1 for k in keys if given[k] == 0)
    spread = max(given.values()) - min(given.values())
    body = "  ".join(f"{k[:6]}={given[k]:>2}" for k in keys)
    print(f"  {name:<34}{body}   нулей={zero} разброс={spread}")


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    keys, provs = read(Path(sys.argv[1]))
    if not provs:
        print("в дампе нет строк «WTP L ... права:» -- это не дамп плана")
        return 1
    print(f"провинций {len(provs)}, городов {sum(n for _, n, _ in provs)}, "
          f"грамот {len(keys)}")
    if "--ceilings" in sys.argv:
        print("\nпотолок земли -- сколько городов грамота может взять там, где ей вообще платят:")
        for k in keys:
            reach = [(n, p) for p, n, v in provs if v[k] > 0]
            print(f"   {k:>26}: {sum(n for n, _ in reach):>3} городов "
                  f"в {len(reach)} провинциях")
        return 0
    print()
    show("специализация, как была:", keys,
         grant(keys, provs, ladder=False, lag="none", fair=False))
    show("общая раздача, без отставания:", keys,
         grant(keys, provs, ladder=True, lag="none", fair=False))
    show("+ отставание обрывом:", keys,
         grant(keys, provs, ladder=True, lag="binary", fair=False))
    show("+ отставание уклоном:", keys,
         grant(keys, provs, ladder=True, lag="graded", fair=False))
    show("+ уклон и «поровну» (как сейчас):", keys,
         grant(keys, provs, ladder=True, lag="graded", fair=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
