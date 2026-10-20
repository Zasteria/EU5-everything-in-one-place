#!/usr/bin/env python3
"""Наши строки в `debug.log` — только под галочкой «Журнал» мода.

Его слово 10-20: месячные записи модов («month, peace pass», «handing out every
seat»…) нужны были для отладки, а сейчас просто шум. Каждый `debug_log` и
`debug_log_scopes` мода оборачивается в проверку глобального флага, который
ставит галочка CMF этого мода:

    debug_log = "x"   →   if = { limit = { has_global_variable = <флаг> } debug_log = "x" }

Флаг глобальный, а не переменная страны, потому что запись бывает в любом
масштабе (персонаж, область, кабинет). Уже обёрнутое не трогается, так что
прогон можно повторять.

    python3 tools/quiet_logs.py <флаг> <файл>...     обернуть на месте
    import quiet_logs; quiet_logs.quiet(text, flag)  из генератора
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

EFFECT = re.compile(r"debug_log(?:_scopes)?\s*=\s*(?:\"[^\"\n]*\"|\w+)")


def quiet(text: str, flag: str) -> str:
    guard = f"if = {{ limit = {{ has_global_variable = {flag} }} "

    def wrap(m: re.Match) -> str:
        if text.endswith(guard, 0, m.start()):
            return m.group(0)
        # A comment line keeps its text as it is.
        line_start = text.rfind("\n", 0, m.start()) + 1
        if "#" in text[line_start:m.start()]:
            return m.group(0)
        return f"{guard}{m.group(0)} }}"

    return EFFECT.sub(wrap, text)


def main(argv: list[str]) -> int:
    flag, files = argv[1], argv[2:]
    for f in files:
        p = Path(f)
        raw = p.read_bytes()
        bom = raw.startswith(b"\xef\xbb\xbf")
        text = raw.decode("utf-8-sig")
        new = quiet(text, flag)
        if new != text:
            p.write_bytes((b"\xef\xbb\xbf" if bom else b"") + new.encode("utf-8"))
            print(f"{f}: guarded")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
