"""Russian goods cases without the game's 75 `AddTextIf` tests.

The game declines a goods name through helper keys
(`EU5_customizable_localization_ru_goods_l_russian.yml`), each holding one
`AddTextIf(EqualTo_string('<name>', X.GetNameWithNoTooltip), '<form>')` per good.
On 1.4 every one of those tests fails (`FetchData failed`, 75 lines per use, and
the name is gone): his Lüneburg session 2026-10-27 logged 26 000 lines a second
for eight seconds while a goods tooltip was open.

This writes the same forms as plain keys, `bag_ru_goods_<case>_<goods key>`, into
`fixes/additions.yml` (between the markers), and the helpers as one lookup each,
`[Localize(Concatenate('bag_ru_goods_<case>_', X.GetKey))]`, into
`fixes/goods_cases.yml`, with their line in `fixes/observed.txt`. The forms are
the game's own translation, read from its file, so nothing is re-translated.

    python3 mods/ru_loc_fix/tools/goods_cases.py     then tools/generate.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

MOD = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(MOD / "tools"))
import locscan  # noqa: E402

FIXES = MOD / "fixes"
HELPERS = FIXES / "goods_cases.yml"
ADDITIONS = FIXES / "additions.yml"
OBSERVED = FIXES / "observed.txt"
BEGIN = "# --- goods_cases.py: begin ---"
END = "# --- goods_cases.py: end ---"
NAME = "EU5_customizable_localization_ru_goods_l_russian.yml"
PAIR = re.compile(r"AddTextIf\(EqualTo_string\('([^']*)', ([A-Za-z_.]+)\.GetNameWithNoTooltip\), '([^']*)'\)")
HELPER = re.compile(r"^(.+)_GetNameWithNoTooltip_RU_([A-Za-z]+?)(_lower)?$")
WHY = ("pdx_data_localize_helper.cpp:315 FetchData failed for 'AddTextIf(EqualTo_string(...))', "
       "every test of the helper, ~26 000 lines/s with a goods tooltip open (his session 2026-10-27, 1.4.4)")


def game_file() -> Path:
    for root in locscan.game_roots() if hasattr(locscan, "game_roots") else []:
        hit = list(Path(root).rglob(NAME))
        if hit:
            return hit[0]
    hit = Path(r"C:/Program Files (x86)/Steam/steamapps/common/Europa Universalis V/game/main_menu/localization/russian") / NAME
    if hit.exists():
        return hit
    sys.exit("cannot find " + NAME)


def main() -> None:
    keys: dict[str, str] = {}
    for line in game_file().read_text(encoding="utf-8-sig").splitlines():
        match = locscan.KEY_LINE.match(line)
        if match:
            keys[match.group(1)] = match.group(2)
    to_key = {name: key for name, _, key in PAIR.findall(keys["GOODS_GetName_RU_tt"])}

    table: dict[tuple[str, str], str] = {}
    helpers: list[tuple[str, str]] = []
    for key, value in keys.items():
        pairs = PAIR.findall(value)
        if not pairs:
            continue
        root = pairs[0][1]
        if key.endswith("_GetName_RU_tt"):
            helpers.append((key, "[%s.GetKey]" % root))
            continue
        match = HELPER.match(key)
        if not match:
            sys.exit("unexpected helper " + key)
        case = match.group(2).lower()
        for name, _, form in pairs:
            table[(case, to_key[name])] = form
        lookup = "Localize(Concatenate('bag_ru_goods_%s_', %s.GetKey))" % (case, root)
        helpers.append((key, "[%s|l]" % lookup if match.group(3) else "[%s]" % lookup))

    HELPERS.write_text(
        "\ufeffl_russian:\n# Written by tools/goods_cases.py — do not edit by hand.\n"
        "# One lookup per helper instead of 75 failing AddTextIf tests; the forms are in additions.yml.\n"
        + "".join(' %s:0 "%s"\n' % pair for pair in sorted(helpers)), encoding="utf-8")

    block = [BEGIN, "# The game's own goods cases as plain keys, for goods_cases.yml's lookups."]
    block += [' bag_ru_goods_%s_%s:0 "%s"' % (case, key, form) for (case, key), form in sorted(table.items())]
    block.append(END)
    text = ADDITIONS.read_text(encoding="utf-8-sig")
    if BEGIN in text:
        text = text[:text.index(BEGIN)] + text[text.index(END) + len(END):].lstrip("\n")
    ADDITIONS.write_text("\ufeff" + text.rstrip("\n") + "\n\n" + "\n".join(block) + "\n", encoding="utf-8")

    observed = OBSERVED.read_text(encoding="utf-8").rstrip("\n").splitlines()
    observed = [l for l in observed if not l.startswith(tuple(k + " " for k, _ in helpers))]
    observed += ["%-45s %s" % (k, WHY) for k, _ in sorted(helpers)]
    OBSERVED.write_text("\n".join(observed) + "\n", encoding="utf-8")
    print("%d helpers, %d forms" % (len(helpers), len(table)))


if __name__ == "__main__":
    main()
