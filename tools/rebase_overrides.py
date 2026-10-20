#!/usr/bin/env python3
"""Перенести наши правки в копиях ванильных файлов на новую версию игры.

Многие моды здесь держат *целую* копию ванильного файла (окно, действие
кабинета, локаторы) с нашими правками внутри. После патча Paradox меняют
оригинал, и копия молча откатывает их изменения: исправления пропадают, а то и
окно ломается. Руками это вечер на каждый патч.

Здесь это трёхстороннее слияние, как у git:
  база   — ванильный файл той версии, с которой делалась копия
           (`reference/game` на коммите `--base`);
  новое  — ванильный файл сейчас (`reference/game` в рабочем дереве, после
           `extract_game_files.py`);
  наше   — файл мода.
Что поменяли Paradox, переносится в копию; что поменяли мы, остаётся. Где обе
стороны тронули одни и те же строки — конфликт: файл получает метки
`<<<<<<<` / `>>>>>>>`, и его надо разобрать руками (список в конце).

    python3 tools/rebase_overrides.py --base <коммит до обновления reference>
    python3 tools/rebase_overrides.py --base <коммит> --dry-run   только отчёт
    python3 tools/rebase_overrides.py --base <коммит> --mod rulers_toolkit

Копией считается файл мода, путь которого (от `in_game/` или `main_menu/`)
совпадает с ванильным в `reference/game`. Сгенерированные копии (CM, ворота
перезарядок) лучше пересобирать их генераторами: слияние здесь — для правленых
руками.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REF = ROOT / "reference" / "game"
LAYERS = ("in_game", "main_menu")


def git_show(rev: str, path: Path) -> bytes | None:
    rel = path.relative_to(ROOT).as_posix()
    r = subprocess.run(["git", "show", f"{rev}:{rel}"], cwd=ROOT, capture_output=True)
    return r.stdout if r.returncode == 0 else None


def overrides(mod: Path):
    for layer in LAYERS:
        top = mod / layer
        if not top.is_dir():
            continue
        for f in top.rglob("*"):
            if f.is_file() and f.suffix in (".gui", ".txt", ".yml"):
                rel = f.relative_to(mod)
                van = REF / rel
                if van.is_file():
                    yield f, van


def strip_bom(b: bytes) -> tuple[bool, bytes]:
    return (True, b[3:]) if b.startswith(b"\xef\xbb\xbf") else (False, b)


def norm(b: bytes) -> bytes:
    return b.replace(b"\r\n", b"\n")


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True, help="коммит, где reference/game ещё старой версии")
    ap.add_argument("--mod", action="append", help="только эти моды")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv[1:])

    mods = sorted(p for p in (ROOT / "mods").iterdir() if p.is_dir() and (not a.mod or p.name in a.mod))
    tmp = ROOT / ".rebase_tmp"
    tmp.mkdir(exist_ok=True)
    same = changed = conflicts = 0
    conflict_list = []
    try:
        for mod in mods:
            for ours_p, van in overrides(mod):
                base = git_show(a.base, van)
                if base is None:
                    print(f"  {mod.name}: {ours_p.relative_to(mod)} — в базе нет ванильного файла, пропуск")
                    continue
                new = van.read_bytes()
                bom, ours = strip_bom(ours_p.read_bytes())
                base, new, ours = norm(strip_bom(base)[1]), norm(strip_bom(new)[1]), norm(ours)
                if base == new:
                    same += 1
                    continue
                (tmp / "ours").write_bytes(ours)
                (tmp / "base").write_bytes(base)
                (tmp / "new").write_bytes(new)
                r = subprocess.run(["git", "merge-file", "-p", "-L", "наше", "-L", "старая ваниль", "-L", "новая ваниль",
                                    str(tmp / "ours"), str(tmp / "base"), str(tmp / "new")], capture_output=True)
                merged, n = r.stdout, r.returncode
                rel = ours_p.relative_to(ROOT).as_posix()
                if n < 0:
                    print(f"  ОШИБКА слияния: {rel}")
                    continue
                if n:
                    conflicts += 1
                    conflict_list.append(f"{rel} — {n} конфл.")
                else:
                    changed += 1
                print(f"  {'КОНФЛИКТ' if n else 'перенесено'}: {rel}")
                if not a.dry_run:
                    ours_p.write_bytes((b"\xef\xbb\xbf" if bom else b"") + merged)
    finally:
        for f in tmp.iterdir():
            f.unlink()
        tmp.rmdir()
    print(f"\nкопий без изменений ванили: {same}; перенесено чисто: {changed}; с конфликтами: {conflicts}")
    for c in conflict_list:
        print("  ", c)
    return 1 if conflicts else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
