#!/usr/bin/env python3
"""The mod manager: the workshop, the game's own copies, and this repository.

Everything the owner has to do by hand for a mod update, in one place and with
no session of mine in the loop:

    python3 tools/mods.py           the menu
    python3 tools/mods.py check     just the answer, for a script or a shortcut

The menu, as he asked for it on 2026-10-03:

1. **Мастерская** — every mod he is subscribed to, compared with what the
   workshop serves **by build id** (`manifest` in Steam's own
   `appworkshop_3450310.acf` against `hcontent_file` from the public
   `GetPublishedFileDetails`), not by dates: Steam stamps an item as updated
   when it *notices* the update, not when it has fetched it. The ones he picks
   are downloaded with `steamcmd` under his account (anonymous does not work for
   this app — measured) into the game's own workshop folder, and the copies in
   this repository follow at once: `reference/mods/` whole, `reference/playset/`
   text only.

2. **Все моды** — one list: ours in `mods/`, everything from the workshop,
   anything else in the game's local mod folder. Pick one and choose what to do
   with it: download, put it in reference or in the playset, install into the
   game, remove from the game, remove from the repository — copy, line in
   `tools/workshop_mods.txt` and every note this menu keeps, so no row of
   «нет подписки» is left behind.

3. **Всё сразу** — the same for everything: update all, drop everything he is no
   longer subscribed to, reinstall our mods whose game copy differs.

4. **Забрать из игры** — the `where_to_produce` diagnosis, a zip of the logs, the
   game's own files into `reference/game/`, the engine's API dumps.

**Nothing here rebuilds or checks anything**, and nothing commits: generators,
`tools/refresh.py` and the checkers are a session's job, and commit and push
are his, in GitHub Desktop.

Settings that are his rather than the repository's — where steamcmd lives, which
Steam account, which branch — go in `tools/mods.local.json`, which is ignored by
git.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import refs  # noqa: E402
import workshop  # noqa: E402

APP_ID = workshop.APP_ID
SETTINGS = Path(__file__).resolve().parent / "mods.local.json"
STEAMCMD_ZIP = "https://steamcdn-a.akamaihd.net/client/installer/steamcmd.zip"


# ------------------------------------------------------------------- settings


def settings_read() -> dict:
    if not SETTINGS.is_file():
        return {}
    try:
        return json.loads(SETTINGS.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def settings_write(values: dict) -> None:
    SETTINGS.write_text(json.dumps(values, indent=1, ensure_ascii=False) + "\n",
                        encoding="utf-8")


# ------------------------------------------------------------ where Steam is

STEAM_ROOTS = {
    "win32": [r"C:\Program Files (x86)\Steam", r"C:\Program Files\Steam", r"C:\Steam"],
    "darwin": ["~/Library/Application Support/Steam"],
    "linux": ["~/.steam/steam", "~/.local/share/Steam",
              "~/snap/steam/common/.local/share/Steam"],
}


def steam_roots(configured: str | None = None) -> list[Path]:
    """Every Steam library on this machine, the registry's answer first."""
    roots: list[Path] = []
    if configured:
        roots.append(Path(configured).expanduser())

    if sys.platform == "win32":
        try:
            import winreg
            for hive, key in ((winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam"),
                              (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam")):
                try:
                    with winreg.OpenKey(hive, key) as handle:
                        for name in ("SteamPath", "InstallPath"):
                            try:
                                roots.append(Path(winreg.QueryValueEx(handle, name)[0]))
                            except OSError:
                                pass
                except OSError:
                    pass
        except ImportError:
            pass

    roots += [Path(p).expanduser() for p in STEAM_ROOTS.get(sys.platform, STEAM_ROOTS["linux"])]

    # Every library folder Steam knows about, not just the one it installed into.
    found: list[Path] = []
    for root in roots:
        if root not in found and root.is_dir():
            found.append(root)
        vdf = root / "steamapps/libraryfolders.vdf"
        if vdf.is_file():
            for match in re.finditer(r'"path"\s+"([^"]+)"', vdf.read_text(encoding="utf-8", errors="replace")):
                library = Path(match.group(1).replace("\\\\", "\\"))
                if library.is_dir() and library not in found:
                    found.append(library)
    return found


def workshop_content(configured: str | None = None) -> Path | None:
    """`steamapps/workshop/content/<app>/`, wherever this machine keeps it."""
    if configured:
        given = Path(configured).expanduser()
        for candidate in (given / APP_ID, given):
            if candidate.is_dir():
                return candidate
        return None
    for root in steam_roots():
        candidate = root / "steamapps/workshop/content" / APP_ID
        if candidate.is_dir():
            return candidate
    return None


# --------------------------------------------------------- what Steam installed


def parse_vdf(text: str) -> dict:
    """Steam's text key-value format, enough of it to read an `.acf`."""
    tokens = re.finditer(r'"((?:[^"\\]|\\.)*)"|([{}])', text)
    stack: list[dict] = [{}]
    pending: str | None = None
    for token in tokens:
        quoted, brace = token.group(1), token.group(2)
        if brace == "{":
            child: dict = {}
            stack[-1][pending or ""] = child
            stack.append(child)
            pending = None
        elif brace == "}":
            if len(stack) > 1:
                stack.pop()
        elif pending is None:
            pending = quoted
        else:
            stack[-1][pending] = quoted
            pending = None
    return stack[0]


def installed_versions(content: Path) -> dict[str, tuple[int, str]]:
    """Workshop id -> (when Steam says the copy on disk was updated, its manifest).

    Steam keeps both in `appworkshop_<app>.acf` beside the content folder, and
    the manifest is the one that actually answers the question. A manifest id
    names a *build*: the one Steam downloaded here, against the one
    `GetPublishedFileDetails` says the workshop serves now. Two that differ mean
    a different version on disk, and two that match mean the same files, whatever
    either side's dates say.

    The dates alone were never enough, and that is the owner's own complaint
    rather than a worry: Steam stamps an item as updated when it *notices* the
    update, which is not the same as having fetched it — so a mod could read as
    current here and load as the old version in game, and the only way out was
    to unsubscribe and resubscribe.
    """
    acf = content.parent.parent / ("appworkshop_%s.acf" % APP_ID)
    found: dict[str, tuple[int, str]] = {}
    if acf.is_file():
        data = parse_vdf(acf.read_text(encoding="utf-8", errors="replace"))
        for section in ("WorkshopItemsInstalled", "WorkshopItemDetails"):
            block = data.get("AppWorkshop", {}).get(section, {})
            for item, fields in block.items():
                if not isinstance(fields, dict):
                    continue
                stamp, manifest = found.get(item, (0, ""))
                try:
                    stamp = stamp or int(fields.get("timeupdated") or 0)
                except (TypeError, ValueError):
                    pass
                manifest = manifest or str(fields.get("manifest") or "")
                if stamp or manifest:
                    found[item] = (stamp, manifest)
    # Anything downloaded but not in the record falls back to the folder's date,
    # and has no manifest — so it is compared by date, as before.
    for folder in content.iterdir():
        if folder.is_dir() and folder.name.isdigit() and folder.name not in found:
            newest = max((p.stat().st_mtime for p in folder.rglob("*") if p.is_file()),
                         default=folder.stat().st_mtime)
            found[folder.name] = (int(newest), "")
    return found


# ------------------------------------------------------------------- the model

REFERENCE = "reference"
PLAYSET = "playset"
UNTRACKED = "—"


@dataclass
class Mod:
    """One subscribed mod, and everything known about it from all three places."""

    id: str
    title: str = ""
    installed: int = 0            # what Steam has on disk
    published: int = 0            # what the workshop has now
    installed_manifest: str = ""  # the build on disk, per Steam's own record
    published_manifest: str = ""  # the build the workshop serves now
    where: str = UNTRACKED        # reference / playset / not copied here
    folder: Path | None = None    # the copy in this repository
    version: str | None = None
    key: str = ""                 # the name tools/workshop_mods.txt gives it
    on_disk: bool = False         # Steam has it, i.e. he is subscribed

    @property
    def by_manifest(self) -> bool:
        """Can this be answered by build id rather than by date?"""
        return bool(self.installed_manifest and self.published_manifest)

    @property
    def outdated(self) -> bool:
        # Build ids when both sides have one: two that differ are two different
        # sets of files, which is the question, and dates are a proxy for it that
        # Steam gets wrong in both directions.
        if self.by_manifest:
            return self.installed_manifest != self.published_manifest
        return bool(self.published and self.installed and self.published > self.installed)

    @property
    def name(self) -> str:
        return self.title or self.key or self.id


@dataclass
class World:
    """Everything the menu needs to know, gathered once."""

    content: Path | None
    mods: list[Mod] = field(default_factory=list)
    asked_steam: bool = False

    @property
    def outdated(self) -> list[Mod]:
        return [m for m in self.mods if m.outdated]

    def by_id(self, item: str) -> Mod | None:
        return next((m for m in self.mods if m.id == item), None)


def meta_name(folder: Path) -> str:
    """What the mod calls itself, for a list Steam did not answer for."""
    try:
        return str(refs._metadata(folder).get("name") or "")
    except SystemExit:
        return ""


def gather(configured: dict, ask_steam: bool = True) -> World:
    with Doing("ищу папку мастерской Steam") as step:
        content = workshop_content(configured.get("workshop"))
        step.finish(str(content) if content else "не нашёл")
    world = World(content=content)
    if content is None:
        return world

    with Doing("читаю, что Steam установил") as step:
        versions = installed_versions(content)
        step.finish("%d мод(ов)" % len(versions))
    # What this tool put there itself. Steam's own record still names the build
    # *Steam* downloaded, so without this a mod updated from here reads as
    # outdated for ever — right up until Steam happens to fetch it again.
    ours: dict[str, int] = {}
    for item, stamp in (configured.get("installed") or {}).items():
        try:
            ours[item] = int(stamp)
        except (TypeError, ValueError):
            continue
    for item, manifest in (configured.get("installed_manifest") or {}).items():
        stamp, steam = versions.get(item, (0, ""))
        # Unless Steam has fetched the item since — then its record is the newer
        # one and this note is about a build that is no longer on disk.
        if steam and stamp > ours.get(item, 0):
            continue
        versions[item] = (stamp, str(manifest))
    for item, stamp in ours.items():
        was, manifest = versions.get(item, (0, ""))
        versions[item] = (max(was, stamp), manifest)
    tracked = {item.id: item for item in workshop.tracked()}
    with Doing("сверяю с копиями в репозитории") as step:
        in_reference = workshop.local_copies()
        step.finish("reference: %d" % len(in_reference))
    in_playset = {}
    for mod in refs.playset():
        found = re.search(r"(\d{6,})", mod.folder)
        in_playset[found.group(1) if found else mod.folder] = mod
    # A folder in reference/mods that no line of workshop_mods.txt claims:
    # still a copy, still his to move or delete.
    claimed = {copy.path for copy in in_reference.values()}
    loose: dict[str, Path] = {}
    for mod in refs.mods():
        if mod.path not in claimed:
            found = re.search(r"(\d{6,})", mod.folder)
            loose[found.group(1) if found else mod.folder] = mod.path

    for folder in sorted(content.iterdir()):
        if not folder.is_dir() or not folder.name.isdigit():
            continue
        stamp, manifest = versions.get(folder.name, (0, ""))
        mod = Mod(id=folder.name, installed=stamp, installed_manifest=manifest, on_disk=True,
                  title=meta_name(folder))
        if folder.name in tracked:
            mod.where, mod.key = REFERENCE, tracked[folder.name].key
            copy = in_reference.get(folder.name)
            if copy:
                mod.folder, mod.version = copy.path, copy.version
        elif folder.name in in_playset:
            mod.where = PLAYSET
            copy = in_playset.pop(folder.name)
            mod.folder, mod.version = copy.path, copy.version
        elif folder.name in loose:
            mod.where, mod.folder = REFERENCE, loose.pop(folder.name)
        world.mods.append(mod)

    # A tracked mod whose copy is here but which Steam has not downloaded still
    # belongs in the list — it is exactly the case worth seeing.
    for item in workshop.tracked():
        if world.by_id(item.id) is None:
            copy = in_reference.get(item.id)
            world.mods.append(Mod(id=item.id, where=REFERENCE, key=item.key,
                                  folder=copy.path if copy else None,
                                  version=copy.version if copy else None))
    # Copies of mods he is no longer subscribed to: the rows «убрать
    # отсутствующее» is for.
    for item, copy in in_playset.items():
        world.mods.append(Mod(id=item, where=PLAYSET, folder=copy.path,
                              version=copy.version, title=copy.name or copy.folder))
    for item, path in loose.items():
        world.mods.append(Mod(id=item, where=REFERENCE, folder=path, title=path.name))

    if ask_steam:
        with Doing("спрашиваю мастерскую про %d мод(ов)" % len(world.mods)) as step:
            try:
                details = workshop.steam_details([m.id for m in world.mods if m.id.isdigit()])
                world.asked_steam = True
                step.finish("ответила")
            except SystemExit:
                details = {}
                step.finish("Steam не ответил — версии покажу по тому, что записано")
        for mod in world.mods:
            detail = details.get(mod.id, {})
            mod.title = detail.get("title", "") or mod.title
            mod.published = int(detail.get("time_updated") or 0)
            mod.published_manifest = str(detail.get("hcontent_file") or "")

    world.mods.sort(key=lambda m: (m.where != REFERENCE, m.where != PLAYSET, m.name.lower()))
    return world


# --------------------------------------------------------------------- talking


def say(text: str = "") -> None:
    print(text, flush=True)


class Doing:
    """Say what is happening *before* it happens, and spin while it does.

    The first thing this tool does is read a Steam folder, parse Steam's own
    installed-items record and ask the workshop about twenty-two mods over the
    network — several seconds in which the old version printed nothing at all,
    which is indistinguishable from a hang.
    """

    FRAMES = "|/-\\"

    def __init__(self, text: str) -> None:
        self.text = text
        self.done = False
        self.thread: object | None = None

    def __enter__(self) -> "Doing":
        self.live = sys.stdout.isatty()
        if not self.live:
            print("  %s ..." % self.text, flush=True)
            return self
        import threading
        # Two trailing spaces: the spinner eats one and the answer that replaces
        # it still has a space in front of it.
        print("  %s ...  " % self.text, end="", flush=True)
        self.thread = threading.Thread(target=self._spin, daemon=True)
        self.thread.start()
        return self

    def _spin(self) -> None:
        frame = 0
        while not self.done:
            print("\b%s" % self.FRAMES[frame % len(self.FRAMES)], end="", flush=True)
            frame += 1
            time.sleep(0.12)

    def finish(self, note: str = "готово") -> None:
        """The answer replaces the spinner, so the line ends up worth reading."""
        self.note = note

    def __exit__(self, *exception: object) -> None:
        self.done = True
        if self.thread is not None:
            self.thread.join(timeout=0.5)          # type: ignore[union-attr]
        note = getattr(self, "note", "готово")
        if exception and exception[0] is not None:
            note = "не вышло"
        if self.live:
            print("\b%s" % note, flush=True)
        else:
            print("  %s: %s" % (self.text, note), flush=True)


def ask(prompt: str, default: str = "") -> str:
    try:
        answer = input(prompt).strip()
    except EOFError:
        # The console closed: every menu here loops until "0", and an input
        # that never comes again would spin it for ever.
        raise SystemExit(0)
    return answer or default


def yes(prompt: str, default: bool = True) -> bool:
    suffix = " [Д/н] " if default else " [д/Н] "
    answer = ask(prompt + suffix).lower()
    if not answer:
        return default
    return answer[0] in "yдd"


def when(stamp: int) -> str:
    return workshop.when(stamp) if stamp else "—"


def pick(mods: list[Mod], prompt: str, default_all: bool = True) -> list[Mod]:
    """Numbers, ranges, or Enter for all of them.

    `default_all=False` where "all of them" is not a sane default — re-fetching
    the whole subscription is a gigabyte of downloads, and Enter should not be
    how it starts.
    """
    answer = ask(prompt)
    if answer in {"0", "н", "n"}:
        return []
    if not answer:
        return list(mods) if default_all else []
    chosen: list[Mod] = []
    for part in re.split(r"[,\s]+", answer):
        if not part:
            continue
        if "-" in part:
            start, _, end = part.partition("-")
            if start.isdigit() and end.isdigit():
                for number in range(int(start), int(end) + 1):
                    if 1 <= number <= len(mods):
                        chosen.append(mods[number - 1])
            continue
        if part.isdigit() and 1 <= int(part) <= len(mods):
            chosen.append(mods[int(part) - 1])
    seen: set[str] = set()
    return [m for m in chosen if not (m.id in seen or seen.add(m.id))]


# ------------------------------------------------------------------- steamcmd


def steamcmd_path(configured: dict) -> str | None:
    """Where steamcmd is, offering to fetch it if it is nowhere."""
    given = configured.get("steamcmd")
    if given and Path(given).expanduser().is_file():
        return str(Path(given).expanduser())

    names = ["steamcmd.exe"] if sys.platform == "win32" else ["steamcmd.sh", "steamcmd"]
    for candidate in [Path(p) / name for p in ("C:/steamcmd", "~/steamcmd", ".")
                      for name in names]:
        if candidate.expanduser().is_file():
            return str(candidate.expanduser())
    found = shutil.which("steamcmd")
    if found:
        return found

    say()
    say("steamcmd не найден. Он нужен, чтобы скачивать моды по требованию —")
    say("именно это заменяет отписку и подписку.")
    if not yes("Скачать его сейчас?"):
        return None
    where = ask("Куда положить [C:\\steamcmd]: ", "C:\\steamcmd" if sys.platform == "win32"
                else str(Path.home() / "steamcmd"))
    target = Path(where).expanduser()
    target.mkdir(parents=True, exist_ok=True)
    say("качаю %s ..." % STEAMCMD_ZIP)
    try:
        with urllib.request.urlopen(STEAMCMD_ZIP, timeout=120) as answer:
            payload = answer.read()
    except Exception as exc:                      # noqa: BLE001 - report and go on
        say("не вышло: %s" % exc)
        return None
    if sys.platform == "win32":
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            archive.extractall(target)
        binary = target / "steamcmd.exe"
    else:
        say("на этой системе steamcmd ставится из архива для Linux — пропускаю.")
        return None
    if not binary.is_file():
        say("в архиве нет steamcmd — что-то поменялось на стороне Valve.")
        return None
    configured["steamcmd"] = str(binary)
    settings_write(configured)
    say("готово: %s" % binary)
    return str(binary)


def steam_login(configured: dict) -> str | None:
    login = configured.get("login")
    if login:
        return login
    say()
    say("Нужен твой аккаунт Steam — тот, на котором куплена игра.")
    say("Пароль этот скрипт не видит и не хранит: его спросит сам steamcmd,")
    say("и после первого раза он логинится сам.")
    login = ask("Логин Steam: ")
    if not login:
        return None
    configured["login"] = login
    settings_write(configured)
    return login


def steamcmd_state(downloaded: Path, ids: list[str]) -> dict[str, tuple[bool, int, str]]:
    """What steamcmd's own download folder holds right now, per workshop id.

    `(folder exists, newest file mtime, manifest steamcmd recorded)`. Taken
    before and after a run, this is what separates "steamcmd fetched a new
    build" from "steamcmd exited and left last week's copy exactly where it
    was" — which look identical if all you ask is whether the folder is there.
    """
    known = installed_versions(downloaded) if downloaded.is_dir() else {}
    state: dict[str, tuple[bool, int, str]] = {}
    for item in ids:
        folder = downloaded / item
        if not folder.is_dir():
            state[item] = (False, 0, "")
            continue
        newest = max((p.stat().st_mtime for p in folder.rglob("*") if p.is_file()),
                     default=folder.stat().st_mtime)
        state[item] = (True, int(newest), known.get(item, (0, ""))[1])
    return state


def download(configured: dict, chosen: list[Mod], content: Path | None) -> list[Mod]:
    """Fetch these mods with steamcmd and put them where the game looks."""
    binary = steamcmd_path(configured)
    if not binary:
        return []
    login = steam_login(configured)
    if not login:
        say("без логина скачать нечего — Steam не отдаёт моды этой игры анонимно.")
        return []

    downloaded = Path(binary).resolve().parent / "steamapps/workshop/content" / APP_ID

    # steamcmd is happy to exit successfully having reused what it fetched last
    # time, and this tool used to read "the folder is there" as "the download
    # worked" — so a login that never completed still copied last week's files
    # over the workshop folder, and the game went on loading the old version.
    # Two things stop that: the cached copy goes first, and what came back is
    # judged by what changed on disk rather than by what exists on it.
    before = steamcmd_state(downloaded, [m.id for m in chosen])
    cached = [m for m in chosen if before[m.id][0]]
    if cached and yes("У steamcmd уже лежат %d из них. Стереть, чтобы он точно "
                      "скачал заново?" % len(cached)):
        for mod in cached:
            shutil.rmtree(downloaded / mod.id, ignore_errors=True)
        before = steamcmd_state(downloaded, [m.id for m in chosen])

    command = [binary, "+login", login]
    for mod in chosen:
        command += ["+workshop_download_item", APP_ID, mod.id]
    command += ["+quit"]

    say()
    say("steamcmd: качаю %d мод(ов) под аккаунтом %s" % (len(chosen), login))
    say("(если он спросит код Steam Guard — введи его прямо здесь)")
    say()
    # Not captured on purpose: steamcmd asks for the Guard code on the console,
    # and a captured run would hang with the prompt invisible. The exit code is
    # read, which the old version threw away.
    code = subprocess.run(command).returncode

    after = steamcmd_state(downloaded, [m.id for m in chosen])
    fetched = installed_versions(downloaded) if downloaded.is_dir() else {}

    got: list[Mod] = []
    unchanged: list[Mod] = []
    missing: list[Mod] = []
    for mod in chosen:
        was, was_when, was_manifest = before[mod.id]
        now, now_when, now_manifest = after[mod.id]
        if not now:
            missing.append(mod)
        elif not was or now_when != was_when or now_manifest != was_manifest:
            got.append(mod)
        elif mod.published_manifest and now_manifest == mod.published_manifest:
            # Untouched, but it is already the build the workshop serves.
            got.append(mod)
        else:
            unchanged.append(mod)

    say()
    if code != 0:
        say("steamcmd вышел с кодом %d — то есть с ошибкой." % code)
    for mod in missing:
        say("  %-46s не скачался вовсе" % mod.name[:46])
    for mod in unchanged:
        say("  %-46s steamcmd оставил то, что уже лежало" % mod.name[:46])
    if missing or unchanged:
        say()
        say("Смотри вывод steamcmd выше. Чаще всего это незавершённый вход:")
        say("логин без пароля, отменённый код Steam Guard, или аккаунт, на")
        say("котором игра не куплена. Ничего из этого не копируется дальше.")
    if not got:
        return []

    if content is None:
        say("папка мастерской Steam не найдена, копировать некуда.")
        return got
    say()
    say("Скачалось: %d" % len(got))
    say("Куда: %s" % content)
    say("Это та папка, из которой игра читает моды мастерской — не копия репозитория.")
    if not yes("Скопировать туда %d, чтобы игра увидела новые версии?" % len(got)):
        return got

    stale: list[Mod] = []
    for mod in got:
        target = content / mod.id
        with Doing("копирую %s" % mod.name[:40]) as step:
            if target.exists():
                shutil.rmtree(target, ignore_errors=True)
            shutil.copytree(downloaded / mod.id, target)
            size = sum(p.stat().st_size for p in target.rglob("*") if p.is_file())
            mod.installed = mod.published or int(time.time())
            configured.setdefault("installed", {})[mod.id] = mod.installed
            # Steam's own `appworkshop_*.acf` still names the build *it* last
            # downloaded, and nothing here may rewrite that file. So what this
            # tool put on disk is written down on this side instead, and the
            # next check reads it back — otherwise a mod updated from here goes
            # on reading as outdated for ever.
            manifest = fetched.get(mod.id, (0, ""))[1]
            if manifest:
                mod.installed_manifest = manifest
                configured.setdefault("installed_manifest", {})[mod.id] = manifest
                if mod.published_manifest and manifest != mod.published_manifest:
                    stale.append(mod)
            step.finish("%s -> %s" % (workshop.human(size), target))
    settings_write(configured)
    say()
    say("Готово. Игра берёт моды из этой папки, так что следующий запуск —")
    say("уже с новыми версиями. Лаунчер иногда показывает старый номер версии,")
    say("пока Steam не сверится сам; на то, что грузится, это не влияет.")
    if stale:
        # Worth saying out loud: it means the download succeeded and still did
        # not bring the current build, which is the one case where a session of
        # unsubscribing and resubscribing is still the answer.
        say()
        say("Но вот что скачалось не тем, что сейчас в мастерской:")
        for mod in stale:
            say("  %-46s steamcmd отдал сборку %s, в мастерской %s"
                % (mod.name[:46], mod.installed_manifest, mod.published_manifest))
        say("Обычно это кэш steamcmd. Повтори загрузку; если повторится —")
        say("тогда и только тогда помогает отписка и подписка в Steam.")
    return got


# ------------------------------------------------------- the repository's side


def run_python(script: str, *args: str) -> int:
    done = subprocess.run([sys.executable, str(refs.REPO / script), *args], cwd=refs.REPO)
    return done.returncode


# ---------------------------------------------------------- moving mods around
#
# **Ни один пункт меню ничего не пересобирает и не проверяет** — его слова
# 2026-10-03: «любые обновления идут через тебя, и я не хочу сталкиваться с
# какими-либо генераторами лично — совсем». Меню только носит файлы между
# мастерской, игрой и репозиторием; `tools/refresh.py` запускает сессия.


def slug(text: str) -> str:
    made = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return made or "mod"


def manifest_drop(item: str) -> bool:
    """Убрать строку мода из `tools/workshop_mods.txt`. True — строка была."""
    lines = workshop.MANIFEST.read_text(encoding="utf-8").splitlines()
    kept = [line for line in lines
            if line.lstrip().startswith("#") or line.split()[:1] != [item]]
    if len(kept) == len(lines):
        return False
    workshop.MANIFEST.write_text("\n".join(kept) + "\n", encoding="utf-8")
    return True


def manifest_add(item: str, key: str) -> None:
    text = workshop.MANIFEST.read_text(encoding="utf-8").rstrip("\n")
    workshop.MANIFEST.write_text(text + "\n%-11s %s\n" % (item, key), encoding="utf-8")


def forget_records(item: str, configured: dict) -> None:
    """Всё, что меню и ежедневная проверка помнят про мод, — кроме его файлов.

    Без этого удалённый мод оставался строкой «отсутствует» в списке: запись
    о сборке в `mods.local.json` и отметка в `workshop_generated_state.json`
    переживали и подписку, и копию.
    """
    changed = False
    for section in ("installed", "installed_manifest"):
        if item in (configured.get(section) or {}):
            del configured[section][item]
            changed = True
    if changed:
        settings_write(configured)
    state_drop(item)


def state_drop(item: str) -> None:
    """Убрать отметку ежедневной проверки на GitHub: мода в reference больше нет."""
    entries = dict(workshop.state_read().get("mods", {}))
    if item in entries:
        del entries[item]
        workshop.state_write(entries)


def record_quietly(ids: list[str]) -> None:
    """Отметить для проверки на GitHub, что копии в reference свежие. Без шума:
    это не его забота, и без сети она догадается сама по истории git."""
    if not ids:
        return
    try:
        workshop.record(ids)
    except (SystemExit, OSError):
        pass


def inventory() -> None:
    try:
        refs.INVENTORY.write_text(refs.table(), encoding="utf-8")
    except (SystemExit, OSError):
        pass


def copy_from_steam(mod: Mod, world: World, kind: str) -> bool:
    """Положить мод из папки мастерской в reference (целиком) или playset (текст)."""
    if world.content is None or not (world.content / mod.id).is_dir():
        say("  %-44s Steam его не скачал — сначала «скачать свежую версию»" % mod.name[:44])
        return False
    source = world.content / mod.id
    if kind == REFERENCE:
        key = mod.key or slug(mod.title or mod.id)
        item = workshop.Tracked(id=mod.id, key=key, reason="")
        existing = workshop.local_copies().get(mod.id)
        folder = workshop.folder_for(item, source, existing)
        with Doing("reference ← %s" % mod.name[:40]) as step:
            files, size = workshop.copy_in(source, refs.MODS / folder)
            if existing is not None and existing.folder != folder:
                shutil.rmtree(existing.path, ignore_errors=True)
            step.finish("%d файлов, %s" % (files, workshop.human(size)))
        mod.folder = refs.MODS / folder
    else:
        item = workshop.Tracked(id=mod.id, key=mod.id, reason="")
        folder = workshop.folder_for(item, source, None)
        refs.PLAYSET.mkdir(parents=True, exist_ok=True)
        with Doing("playset ← %s" % mod.name[:40]) as step:
            files, size = workshop.copy_slim(source, refs.PLAYSET / folder)
            step.finish("%d файлов текста, %s" % (files, workshop.human(size)))
        if mod.folder is not None and mod.folder != refs.PLAYSET / folder:
            shutil.rmtree(mod.folder, ignore_errors=True)
        mod.folder = refs.PLAYSET / folder
    return True


def to_reference(mod: Mod, world: World) -> None:
    """Целиком в `reference/mods/`, и проверка на GitHub начинает за ним следить."""
    if world.content is None or not (world.content / mod.id).is_dir():
        say("Steam его не скачал — сначала «скачать свежую версию».")
        return
    old = mod.folder if mod.where == PLAYSET else None
    if not mod.key:
        mod.key = slug(mod.title or mod.id)
        manifest_add(mod.id, mod.key)
    if copy_from_steam(mod, world, REFERENCE) and old is not None:
        shutil.rmtree(old, ignore_errors=True)
    record_quietly([mod.id])
    inventory()


def to_playset(mod: Mod, world: World) -> None:
    """Только текст в `reference/playset/`, без проверки на GitHub."""
    if world.content is None or not (world.content / mod.id).is_dir():
        say("Steam его не скачал — сначала «скачать свежую версию».")
        return
    old = mod.folder if mod.where == REFERENCE else None
    manifest_drop(mod.id)
    mod.folder = None
    if copy_from_steam(mod, world, PLAYSET) and old is not None:
        shutil.rmtree(old, ignore_errors=True)
    state_drop(mod.id)
    mod.key = ""
    inventory()


# ------------------------------------------------- our own mods, into the game

# A mod folder here is two things at once: what the game loads, and what this
# repository needs to build it. Only the first half may be installed — the game
# has no use for a generator, and a `translations/` folder inside a live mod is
# just something to wonder about later.
GAME_PARTS = {".metadata", "in_game", "main_menu", "loading_screen", "jomini",
              "gfx", "sound", "music"}
REPO_ONLY = {"tools", "translations", "fixes", "docs", "workshop",
             ".git", ".claude", "__pycache__"}

# Where the game keeps mods that did not come from the workshop.
GAME_FOLDER = "Paradox Interactive/Europa Universalis V/mod"


def documents_dir() -> list[Path]:
    r"""Every plausible Documents folder, the registry's answer first.

    Windows lets Documents be moved, and OneDrive moves it without asking, so
    the literal `%USERPROFILE%\Documents` is a guess rather than an answer.
    """
    found: list[Path] = []
    if sys.platform == "win32":
        try:
            import winreg
            key = r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as handle:
                found.append(Path(winreg.QueryValueEx(handle, "Personal")[0]))
        except (ImportError, OSError):
            pass
    home = Path.home()
    found += [home / "Documents", home / "OneDrive/Documents", home / "OneDrive - Personal/Documents"]
    return [p for p in found if p.is_dir()]


def game_mods_dir(configured: dict, make: bool = False) -> Path | None:
    """`Documents/Paradox Interactive/Europa Universalis V/mod`, or None."""
    given = configured.get("game_mods")
    if given:
        # Deliberately not created. A path set once with a typo in it would
        # otherwise be made real on the next run, and every install after that
        # would land in a folder the game never reads — reporting success each
        # time. It has to already exist, or it is not the game's folder.
        target = Path(given).expanduser()
        return target if target.is_dir() else None

    for documents in documents_dir():
        target = documents / GAME_FOLDER
        if target.is_dir():
            return target
        # The game's own folder existing without `mod/` inside it just means he
        # has never installed a local mod: that is ours to create, once.
        if target.parent.is_dir() and make:
            target.mkdir(parents=True, exist_ok=True)
            return target
    return None


def here() -> str:
    """The branch and commit this repository is on, for saying what was installed."""
    branch = workshop.git("rev-parse", "--abbrev-ref", "HEAD", check=False).stdout.strip()
    commit = workshop.git("rev-parse", "--short", "HEAD", check=False).stdout.strip()
    return "%s %s" % (branch or "?", commit or "?")


def our_mods() -> list[refs.Mod]:
    """The mods this repository builds, in `mods/`."""
    found = []
    for folder in sorted((refs.REPO / "mods").iterdir()):
        if not folder.is_dir() or not (folder / ".metadata/metadata.json").is_file():
            continue
        data = json.loads((folder / ".metadata/metadata.json").read_text(encoding="utf-8-sig"))
        found.append(refs.Mod(path=folder, id=data.get("id"), name=data.get("name"),
                              version=str(data.get("version") or ""),
                              game_version=data.get("supported_game_version")))
    return found


def game_files(folder: Path) -> tuple[list[Path], list[str]]:
    """The parts of a mod folder the game wants, and anything unrecognised.

    Unrecognised is reported rather than guessed at in either direction: a mount
    this tool has not heard of would otherwise be dropped silently, and a new
    repository-only folder would otherwise be installed into the game.
    """
    wanted: list[Path] = []
    unknown: list[str] = []
    for entry in sorted(folder.iterdir()):
        if entry.is_dir() and entry.name in GAME_PARTS:
            wanted.append(entry)
        elif entry.is_dir() and entry.name not in REPO_ONLY:
            unknown.append(entry.name)
    return wanted, unknown


def tree_digest(paths: list[Path], root: Path) -> str:
    """A digest of exactly what would be installed, so "same" means the same."""
    from hashlib import sha1
    digest = sha1()
    for part in paths:
        for path in sorted(part.rglob("*")):
            if not path.is_file():
                continue
            digest.update(str(path.relative_to(root)).replace("\\", "/").encode("utf-8"))
            digest.update(path.read_bytes())
    return digest.hexdigest()


def installed_state(mod: refs.Mod, target: Path) -> str:
    there = target / mod.path.name
    if not there.is_dir():
        return "нет в игре"
    mine, _ = game_files(mod.path)
    theirs, _ = game_files(there)
    if tree_digest(mine, mod.path) == tree_digest(theirs, there):
        return "совпадает"
    return "отличается"


def installed_version(mod: refs.Mod, target: Path) -> str:
    """The `version` in the game's copy of this mod, "" when there is none."""
    meta = target / mod.path.name / ".metadata/metadata.json"
    try:
        return str(json.loads(meta.read_text(encoding="utf-8-sig")).get("version") or "")
    except (OSError, ValueError):
        return ""


def version_key(text: str) -> tuple:
    """"2.3.0+perf2" -> ((2, 3, 0), (2,)): numbers compared as numbers."""
    main, _, suffix = text.partition("+")
    return (tuple(int(n) for n in re.findall(r"\d+", main)),
            tuple(int(n) for n in re.findall(r"\d+", suffix)))


def version_note(here_version: str, game_version: str, state: str) -> str:
    """What the two versions say together — above all, a branch older than the game.

    **He switches branches often** (2026-09-27), so the branch checked out can
    carry an older build of a mod than the one already in the game. Installing
    it then is a silent downgrade; this is the one place that sees both.
    """
    if not here_version or not game_version:
        return ""
    ours, theirs = version_key(here_version), version_key(game_version)
    if ours < theirs:
        return "ТУТ СТАРЕЕ"
    if ours > theirs:
        return "тут новее"
    if state == "отличается":
        return "версию не подняли"
    return ""


def install(mod: refs.Mod, target: Path) -> tuple[int, int]:
    """Replace the game's copy of this mod with the one here."""
    parts, _ = game_files(mod.path)
    there = target / mod.path.name
    if there.exists():
        shutil.rmtree(there)
    files = size = 0
    for part in parts:
        for path in sorted(part.rglob("*")):
            if not path.is_file():
                continue
            destination = there / path.relative_to(mod.path)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)
            files += 1
            size += path.stat().st_size
    return files, size


# **Nothing here commits or pushes, and that is his rule.** 2026-09-03: «на самом
# деле модс.бат не должен ничего комитить и пушить. Комичу и пушу любые изменения
# в папке репозитория я через соответствующее десктопное приложение гитхаба.»
# A menu item that did it was removed rather than left as a second way in --
# two things writing the same working tree is how a half-finished change gets
# pushed by the one that was not looking.


# ---------------------------------------------------------------------- screens


def show_updates(world: World) -> list[Mod]:
    if world.content is None:
        say("Папка мастерской Steam не найдена.")
        say("Укажи её:  python3 tools/mods.py --workshop \"D:\\SteamLibrary\\steamapps\\workshop\\content\"")
        return []
    if not world.asked_steam:
        say("Steam не ответил — без сети сказать, что обновилось, нельзя.")
        return []

    outdated = world.outdated
    by_date = [m for m in world.mods if m.installed and not m.by_manifest]
    say()
    say("Подписка: %d мод(ов). В reference: %d, в playset: %d."
        % (sum(1 for m in world.mods if m.on_disk),
           sum(1 for m in world.mods if m.where == REFERENCE),
           sum(1 for m in world.mods if m.where == PLAYSET)))
    if by_date:
        # Sharpness worth naming: for the rest the answer is exact, and for
        # these it is a date, which is the weaker question.
        say("У %d мод(ов) Steam не записал номер сборки — они сверены по дате."
            % len(by_date))
    if not outdated:
        say("Обновлять нечего: у тебя стоят те же сборки, что и в мастерской.")
        return []

    say()
    say("Отстают от мастерской:")
    say("  %-3s %-46s %-17s %-17s %s"
        % ("#", "мод", "у тебя", "в мастерской", "почему"))
    for number, mod in enumerate(outdated, 1):
        # Said out loud because the dates can be identical and the mod still be
        # a different build — which is precisely the case Steam gets wrong.
        say("  %-3d %-46s %-17s %-17s %s"
            % (number, mod.name[:46], when(mod.installed), when(mod.published),
               "другая сборка" if mod.by_manifest else "мастерская новее по дате"))
    return outdated


def screen_diag() -> None:
    """Забрать отчёт «Диагностика» из логов игры и положить в буфер обмена.

    Существует, чтобы прогон стоил один раз. Только игрок может запустить игру,
    и раньше ответ приходил скриншотами -- по одному вопросу за прогон; отчёт
    отвечает на весь вопрос сразу, и этот пункт нужен, чтобы достать его из
    `debug.log` не разбираясь, где игра держит логи.
    """
    say()
    say("Отчёт пишется по кнопке «Диагностика» на вкладке «Расчёт» в меню мода,")
    say("сразу после «Считать план». Здесь он достаётся из логов игры.")
    say()
    say("Файл каждый раз перезаписывается, а лог игры копит: если нужно сравнить")
    say("два нажатия подряд — ответь «в», и в файл попадут все отчёты из лога.")
    every = ask("все отчёты? (в/Enter — только последний) ").strip().lower()
    say()
    run_python("tools/diag.py", *(["--all"] if every in {"в", "v", "y", "д", "да"} else []))
    say()
    ask("Enter — назад ")


# ------------------------------------------------------------- из игры

# Где игра держит свои папки в «Документах»: логи, дампы API, моды.
GAME_DOCUMENTS = "Paradox Interactive/Europa Universalis V"


def game_install(configured: dict, content: Path | None) -> tuple[Path | None, int]:
    """Папка игры и когда Steam её последний раз обновил — по записи самого Steam.

    `appmanifest_<app>.acf` лежит в той библиотеке Steam, куда поставлена игра,
    и это не обязательно та же, где мастерская, — поэтому смотрятся все.
    """
    given = configured.get("game")
    libraries = steam_roots()
    if content is not None and len(content.parents) > 3:
        libraries.insert(0, content.parents[3])
    for library in libraries:
        acf = library / "steamapps" / ("appmanifest_%s.acf" % APP_ID)
        if not acf.is_file():
            continue
        data = parse_vdf(acf.read_text(encoding="utf-8", errors="replace")).get("AppState", {})
        folder = library / "steamapps/common" / str(data.get("installdir") or "")
        try:
            updated = int(data.get("LastUpdated") or 0)
        except (TypeError, ValueError):
            updated = 0
        if data.get("installdir") and folder.is_dir():
            return (Path(given) if given else folder), updated
    return (Path(given) if given else None), 0


def api_dumps() -> tuple[Path | None, list[tuple[Path, str]]]:
    """Дампы `script_docs` и `dump_data_types`: (папка игры в «Документах»,
    [(файл, его путь в reference/game/docs)])."""
    for documents in documents_dir():
        base = documents / GAME_DOCUMENTS
        if not base.is_dir():
            continue
        found = [(p, p.name) for p in sorted((base / "docs").glob("*.log"))]
        found += [(p, "data_types/" + p.name)
                  for p in sorted((base / "logs/data_types").glob("*.txt"))]
        return base, found
    return None, []


def say_how_to_dump(then: str) -> None:
    say("Их снимает только сама игра. Один раз:")
    say("  Steam → EU5 → Свойства → Параметры запуска: -debug_mode")
    say("  в игре открой консоль (~) и введи  script_docs  затем  dump_data_types")
    say("  выйди из игры, убери -debug_mode и %s." % then)


def update_api_dumps(updated: int) -> bool:
    """Скопировать дампы API, если они сняты после обновления игры. True — свежие."""
    base, found = api_dumps()
    target = refs.GAME / "docs"
    if not found:
        say("Дампов API в «Документах» нет%s." % (" (%s)" % base if base else ""))
        return False
    taken = min(int(path.stat().st_mtime) for path, _ in found)
    say("Дампы API сняты %s, игра обновлена %s."
        % (when(taken), when(updated) if updated else "— Steam не сказал когда"))
    if updated and taken < updated:
        return False
    changed = 0
    for path, name in found:
        destination = target / name
        before = destination.read_bytes() if destination.is_file() else None
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
        changed += before != path.read_bytes()
    record = refs.GAME / "version.json"
    data = {}
    if record.is_file():
        try:
            data = json.loads(record.read_text(encoding="utf-8"))
        except ValueError:
            data = {}
    data["api_dumps"] = time.strftime("%Y-%m-%d %H:%M", time.localtime(taken))
    record.write_text(json.dumps(data, indent=1, ensure_ascii=False, sort_keys=True) + "\n",
                      encoding="utf-8")
    say("Скопировал в reference/game/docs файлов: %d, изменилось: %d." % (len(found), changed))
    return True


# Что кладётся в архив логов, и почему именно это. `game.log` и `data_types/`
# намеренно не берутся: вместе они мегабайт шесть, а отвечают на вопросы,
# которые и так закрыты дампами в `reference/`. Хвост `debug.log` берётся
# целиком — там лежит отчёт «Диагностика».
LOG_FILES = ("error.log", "gui.log", "warning.log", "database_conflicts.log",
             "system.log")
DEBUG_TAIL_MB = 4


def screen_logs() -> None:
    """Собрать логи игры в один небольшой архив рядом с репозиторием.

    **Папку логов ищет `diag.py`, а не этот файл.** `GAME_FOLDER` здесь
    кончается на `/mod` -- это папка модов, а логи лежат рядом с ней, — и второй
    экземпляр той же догадки разошёлся бы с первым в тот день, когда Paradox
    что-нибудь переименует.
    """
    from datetime import datetime
    import diag

    say()
    folder = diag.logs_folder()
    if folder is None:
        say("Не нашёл папку логов игры. Обычно она здесь:")
        say(r"  C:\Users\<ты>\Documents\Paradox Interactive\Europa Universalis V\logs")
        say()
        ask("Enter — назад ")
        return

    out = refs.REPO / ("eu5-logs-%s.zip" % datetime.now().strftime("%m%d-%H%M"))
    written = []
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in LOG_FILES:
            path = folder / name
            if path.is_file():
                archive.write(path, name)
                written.append("%s — %s" % (name, workshop.human(path.stat().st_size)))
        debug = folder / "debug.log"
        if debug.is_file():
            # Только хвост: лог копит между запусками, а нужен последний прогон.
            size = debug.stat().st_size
            with io.open(debug, "rb") as handle:
                if size > DEBUG_TAIL_MB * 1024 * 1024:
                    handle.seek(size - DEBUG_TAIL_MB * 1024 * 1024)
                    handle.readline()
                data = handle.read()
            archive.writestr("debug.log", data)
            written.append("debug.log — последние %s" % workshop.human(len(data)))
    if not written:
        out.unlink(missing_ok=True)
        say("В папке логов нет ни одного нужного файла: %s" % folder)
        say()
        ask("Enter — назад ")
        return
    say("Собрано в %s — %s" % (out.name, workshop.human(out.stat().st_size)))
    for line in written:
        say("  " + line)
    say()
    say("Лежит в корне репозитория. Приложи его к сообщению: в git он не поедет,")
    say("он в .gitignore, и весит слишком много для репозитория.")
    say()
    ask("Enter — назад ")


# ------------------------------------------------- every mod, wherever it is


@dataclass
class Entry:
    """Один мод, где бы он ни лежал: мастерская, репозиторий, папка модов игры."""

    name: str
    workshop: Mod | None = None       # подписка или строка в workshop_mods.txt
    ours: refs.Mod | None = None      # наш, mods/<папка>
    in_game: Path | None = None       # Documents/.../mod/<папка>
    game_state: str = ""              # для нашего: совпадает / отличается
    game_version: str = ""

    @property
    def missing(self) -> bool:
        """Мод мастерской, на который больше нет подписки, а записи и копии остались."""
        return self.workshop is not None and not self.workshop.on_disk

    def steam_column(self) -> str:
        if self.workshop is None:
            return "—"
        if not self.workshop.on_disk:
            return "нет подписки"
        return "ОТСТАЁТ" if self.workshop.outdated else "есть"

    def repo_column(self) -> str:
        if self.ours is not None:
            return "наш %s" % (self.ours.version or "")
        mod = self.workshop
        if mod is None:
            return "—"
        if mod.folder is not None and mod.folder.exists():
            return mod.where
        return "НЕТ КОПИИ" if mod.key else "—"

    def game_column(self) -> str:
        if self.in_game is None:
            return "—"
        if self.ours is None:
            return "лежит"
        if self.game_state == "отличается":
            note = version_note(self.ours.version or "", self.game_version, self.game_state)
            return "отличается" + (" (%s)" % note if note else "")
        return self.game_state


def entries(world: World, configured: dict) -> list[Entry]:
    """Наши моды, потом мастерская, потом всё остальное в папке модов игры."""
    target = game_mods_dir(configured)
    local = {p.name: p for p in sorted(target.iterdir()) if p.is_dir()} if target else {}

    ours: list[Entry] = []
    for mod in our_mods():
        entry = Entry(name=mod.path.name, ours=mod)
        there = local.pop(mod.path.name, None)
        if there is not None and target is not None:
            entry.in_game = there
            entry.game_state = installed_state(mod, target)
            entry.game_version = installed_version(mod, target)
        ours.append(entry)

    steam = [Entry(name=mod.name, workshop=mod) for mod in world.mods]
    other = [Entry(name=name, in_game=path) for name, path in local.items()]
    return ours + steam + other


def show_entries(found: list[Entry]) -> None:
    say()
    say("  %-3s %-40s %-13s %-18s %s" % ("#", "мод", "мастерская", "репозиторий", "в игре (локально)"))
    titles = {0: "наши", 1: "из мастерской", 2: "прочее в папке модов игры"}
    group = -1
    for number, entry in enumerate(found, 1):
        kind = 0 if entry.ours is not None else 1 if entry.workshop is not None else 2
        if kind != group:
            group = kind
            say("  --- %s" % titles[kind])
        say("  %-3d %-40s %-13s %-18s %s"
            % (number, entry.name[:40], entry.steam_column(), entry.repo_column()[:18],
               entry.game_column()))


def install_ours(chosen: list[refs.Mod], target: Path) -> None:
    """Поставить наши моды в папку модов игры и перечитать, что доехало."""
    for mod in chosen:
        _, unknown = game_files(mod.path)
        with Doing("в игру ← %s" % mod.path.name) as step:
            files, size = install(mod, target)
            step.finish("%d файлов, %s" % (files, workshop.human(size)))
        if unknown:
            say("     не знаю, что это, и потому не копировал: %s" % ", ".join(unknown))
        # Read back rather than trust the copy: everything that has gone wrong
        # here was silent — a folder the game does not read, a half copy.
        state = installed_state(mod, target)
        if state != "совпадает":
            say("     ПРОВЕРКА НЕ ПРОШЛА: в игре «%s». Смотри сам: %s"
                % (state, target / mod.path.name))
    say("Поставлено из %s. Новый мод включи в лаунчере один раз." % here())


def remove_from_game(entry: Entry) -> None:
    if entry.in_game is not None and entry.in_game.is_dir():
        shutil.rmtree(entry.in_game, ignore_errors=True)
        say("  %s убран из папки модов игры" % entry.name)
        entry.in_game = None


def remove_from_repository(entry: Entry, world: World, configured: dict) -> None:
    """Удалить мод из репозитория — копию, строку в списке и все записи меню.

    Подписка Steam и папка модов игры не трогаются: для них свои пункты.
    """
    say()
    if entry.ours is not None:
        say("Это удалит наш мод целиком: %s" % entry.ours.path)
        say("Вернуть можно только из истории git (GitHub Desktop → Discard).")
        if ask("Впиши имя папки, чтобы подтвердить (Enter — отмена): ").strip() != entry.name:
            say("Отменено.")
            return
        shutil.rmtree(entry.ours.path, ignore_errors=True)
        say("  удалено: mods/%s" % entry.name)
        return

    mod = entry.workshop
    if mod is None:
        return
    if not yes("Удалить %s из репозитория?" % mod.name, default=False):
        return
    if mod.folder is not None and mod.folder.exists():
        shutil.rmtree(mod.folder, ignore_errors=True)
        say("  удалено: %s" % mod.folder.relative_to(refs.REPO))
    if manifest_drop(mod.id):
        say("  убрано из tools/workshop_mods.txt")
    forget_records(mod.id, configured)
    inventory()


def screen_mod(entry: Entry, world: World, configured: dict) -> bool:
    """Что сделать с одним модом. True — что-то поменялось, список перечитать."""
    mod = entry.workshop
    target = game_mods_dir(configured, make=True)
    actions: list[tuple[str, object]] = []
    if mod is not None:
        actions.append(("скачать свежую версию из мастерской в игру",
                        lambda: download(configured, [mod], world.content)))
        if mod.on_disk and (mod.where != REFERENCE or mod.folder is None):
            actions.append(("положить в reference — целиком", lambda: to_reference(mod, world)))
        if mod.on_disk and mod.where != PLAYSET:
            actions.append(("положить в playset — только текст", lambda: to_playset(mod, world)))
        if mod.folder is not None and mod.folder.exists() and mod.on_disk:
            actions.append(("обновить копию в репозитории из папки мастерской",
                            lambda: copy_from_steam(mod, world, mod.where)))
    if entry.ours is not None and target is not None:
        actions.append(("поставить в игру", lambda: install_ours([entry.ours], target)))
    if entry.in_game is not None:
        actions.append(("удалить из игры (папка модов игры)", lambda: remove_from_game(entry)))
    if entry.ours is not None or (mod is not None and (mod.key or mod.folder is not None)):
        actions.append(("удалить из репозитория",
                        lambda: remove_from_repository(entry, world, configured)))

    say()
    say("%s%s" % (entry.name, "  (id %s)" % mod.id if mod else ""))
    say("  мастерская: %s   репозиторий: %s   в игре: %s"
        % (entry.steam_column(), entry.repo_column(), entry.game_column()))
    for number, (text, _) in enumerate(actions, 1):
        say("  %d  %s" % (number, text))
    say("  0  назад")
    choice = ask("> ")
    if not choice.isdigit() or not 1 <= int(choice) <= len(actions):
        return False
    say()
    actions[int(choice) - 1][1]()          # type: ignore[operator]
    return True


def screen_mods(world: World, configured: dict) -> World:
    while True:
        found = entries(world, configured)
        show_entries(found)
        say()
        answer = ask("Номер мода (Enter — назад): ")
        if not answer.isdigit() or not 1 <= int(answer) <= len(found):
            return world
        if screen_mod(found[int(answer) - 1], world, configured):
            world = gather(configured)


def screen_workshop(world: World, configured: dict) -> World:
    """Пункт 1: сверить с мастерской, скачать в игру, обновить копии в репозитории."""
    outdated = show_updates(world)
    if outdated:
        say()
        chosen = pick(outdated, "Что скачать? [Enter — все, номера через запятую, 0 — назад]: ")
    else:
        # «Ничего не отстаёт» — ровно тот ответ, который бывал неправдой: Steam
        # помечает мод обновлённым, когда заметил обновление, а не когда скачал.
        if world.content is None or not world.mods:
            return world
        say()
        if not yes("Всё равно перекачать какой-нибудь мод заново?", default=False):
            return world
        say()
        on_disk = [m for m in world.mods if m.on_disk]
        for number, mod in enumerate(on_disk, 1):
            say("  %-3d %-46s %-10s %s" % (number, mod.name[:46], mod.where, when(mod.installed)))
        say()
        chosen = pick(on_disk, "Какие? [номера через запятую, 0 — назад]: ", default_all=False)
    if not chosen:
        return world
    got = download(configured, chosen, world.content)
    copied = [m for m in got if m.where in (REFERENCE, PLAYSET)
              and m.folder is not None and m.folder.exists()]
    if copied:
        say()
        say("Копии в репозитории:")
        for mod in copied:
            copy_from_steam(mod, world, mod.where)
        record_quietly([m.id for m in copied if m.where == REFERENCE])
        inventory()
    return gather(configured)


def screen_bulk(world: World, configured: dict) -> World:
    """Пункт 3: то же, что в списке, но сразу для всех."""
    say()
    say("  1  Обновить всё: скачать отстающие из мастерской в игру и обновить")
    say("     все копии в репозитории (reference целиком, playset текстом)")
    say("  2  Убрать отсутствующее: из репозитория и записей меню — всё,")
    say("     на что больше нет подписки")
    say("  3  Обновить наши моды в игре: переставить те, что там отличаются")
    say("  0  назад")
    choice = ask("> ")
    say()
    if choice == "1":
        if world.outdated and yes("Отстают от мастерской: %d. Скачать?" % len(world.outdated)):
            download(configured, world.outdated, world.content)
            world = gather(configured)
        copies = [m for m in world.mods if m.on_disk and m.folder is not None and m.folder.exists()]
        say()
        say("Копии в репозитории: %d" % len(copies))
        for mod in copies:
            copy_from_steam(mod, world, mod.where)
        record_quietly([m.id for m in copies if m.where == REFERENCE])
        inventory()
    elif choice == "2":
        if world.content is None:
            say("Папка мастерской не найдена — не видно, на что есть подписка.")
            return world
        gone = [m for m in world.mods if not m.on_disk]
        stale = set(configured.get("installed") or {}) | set(configured.get("installed_manifest") or {})
        stale -= {m.id for m in world.mods if m.on_disk}
        if not gone and not stale:
            say("Отсутствующего нет.")
            return world
        for mod in gone:
            say("  %-46s %s" % (mod.name[:46],
                                mod.folder.relative_to(refs.REPO) if mod.folder else "только запись"))
        if stale - {m.id for m in gone}:
            say("  и записи меню о %d мод(ах), которых нет нигде" % len(stale - {m.id for m in gone}))
        say()
        say("Подписка взята из %s." % world.content)
        copies = sum(1 for m in world.mods if m.folder is not None)
        if copies and len(gone) * 2 > copies:
            say("Это %d из %d копий. Если подписка на них есть, меню смотрит не в ту" % (len(gone), copies))
            say("папку Steam — тогда ответь «н» и укажи её: mods.bat --workshop \"<путь>\".")
        if not yes("Удалить это из репозитория?", default=False):
            return world
        for mod in gone:
            if mod.folder is not None and mod.folder.exists():
                shutil.rmtree(mod.folder, ignore_errors=True)
            manifest_drop(mod.id)
        for item in stale | {m.id for m in gone}:
            forget_records(item, configured)
        inventory()
        say("Готово.")
    elif choice == "3":
        target = game_mods_dir(configured)
        if target is None:
            say("Папка модов игры не найдена.")
            return world
        found = [e for e in entries(world, configured)
                 if e.ours is not None and e.game_state == "отличается"]
        if not found:
            say("Наши моды в игре совпадают с репозиторием.")
            return world
        older = [e.name for e in found
                 if version_note(e.ours.version or "", e.game_version, e.game_state) == "ТУТ СТАРЕЕ"]
        if older and not yes("В этой ветке старее, чем в игре: %s. Откатить и их?"
                             % ", ".join(older), default=False):
            found = [e for e in found if e.name not in older]
        install_ours([e.ours for e in found if e.ours is not None], target)
    else:
        return world
    return gather(configured)


def screen_collect(world: World, configured: dict) -> None:
    """Пункт 4: забрать из игры то, чего сессия не видит."""
    while True:
        say()
        say("  1  Диагностика where_to_produce → в буфер обмена")
        say("  2  Логи игры → маленький архив, приложить в чат")
        say("  3  Файлы игры → reference/game/ (то, что игра убрала, удаляется и здесь)")
        say("  4  Дампы API движка → reference/game/docs")
        say("  0  назад")
        choice = ask("> ")
        if choice == "1":
            screen_diag()
        elif choice == "2":
            screen_logs()
        elif choice == "3":
            say()
            game, _ = game_install(configured, world.content)
            args = ["--prune"]
            if game is not None:
                args += ["--game", str(game)]
            if world.content is not None:
                args += ["--mods-from", str(world.content)]
            run_python("tools/extract_game_files.py", *args)
            say()
            ask("Enter — назад ")
        elif choice == "4":
            say()
            _, updated = game_install(configured, world.content)
            if not update_api_dumps(updated):
                say_how_to_dump("снова выбери этот пункт")
            say()
            ask("Enter — назад ")
        else:
            return


def menu(configured: dict) -> int:
    world = gather(configured)
    while True:
        say()
        say("=" * 62)
        say("  МОДЫ EU5")
        say("  подписка: %-3d   reference: %-3d   playset: %-3d   отстают: %d"
            % (sum(1 for m in world.mods if m.on_disk),
               sum(1 for m in world.mods if m.where == REFERENCE),
               sum(1 for m in world.mods if m.where == PLAYSET),
               len(world.outdated)))
        say("=" * 62)
        say("  1  Мастерская: проверить, скачать свежие в игру, обновить копии")
        say("  2  Все моды: выбрать мод и решить, что с ним делать")
        say("  3  Всё сразу: обновить всё, убрать отсутствующее, наши в игру")
        say("  4  Забрать из игры: диагностика, логи, файлы игры, дампы API")
        say("  0  Выход")
        say()
        say("  Коммит и пуш — в GitHub Desktop; отсюда репозиторий не пишется.")
        choice = ask("> ")

        if choice == "1":
            world = screen_workshop(world, configured)
        elif choice == "2":
            world = screen_mods(world, configured)
        elif choice == "3":
            world = screen_bulk(world, configured)
        elif choice == "4":
            screen_collect(world, configured)
        elif choice in {"0", "q", "в", "выход"}:
            return 0


# ------------------------------------------------------------------- the shell


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="mods.py",
        description="Обновление модов EU5: мастерская, папка игры и этот репозиторий.")
    parser.add_argument("command", nargs="?", default="menu",
                        choices=["menu", "check"],
                        help="menu — меню (по умолчанию); check — только отчёт")
    parser.add_argument("--workshop", metavar="DIR",
                        help="папка steamapps/workshop/content, если она не там, где обычно")
    parser.add_argument("--steamcmd", metavar="PATH", help="путь к steamcmd")
    parser.add_argument("--login", metavar="USER", help="аккаунт Steam")
    parser.add_argument("--game-mods", metavar="DIR", dest="game_mods",
                        help="папка модов игры (Documents/Paradox Interactive/...)")
    parser.add_argument("--game", metavar="DIR",
                        help="папка самой игры, если Steam её не называет")
    parsed = parser.parse_args(argv[1:])

    configured = settings_read()
    for name in ("workshop", "steamcmd", "login", "game_mods", "game"):
        given = getattr(parsed, name)
        if given:
            configured[name] = given
    if any(getattr(parsed, n) for n in ("workshop", "steamcmd", "login", "game_mods", "game")):
        settings_write(configured)

    if parsed.command == "check":
        world = gather(configured)
        behind = show_updates(world)
        # The half nothing used to report without the menu. Twice a run has been
        # read as a mod fault when the game was simply loading an older copy, so
        # this is the line to paste into a chat before anybody theorises.
        say()
        target = game_mods_dir(configured)
        if target is None:
            say("Папка модов игры не найдена — наши моды в игру не поставлены.")
            return 1
        say("Наши моды в игре (%s), против репозитория на %s:" % (target, here()))
        wrong = []
        for mod in our_mods():
            state = installed_state(mod, target)
            say("  %-22s %s" % (mod.path.name, state))
            if state != "совпадает":
                wrong.append(mod.path.name)
        if wrong:
            say()
            say("Игра грузит не то, что лежит здесь. Пока это так, проверять по")
            say("ней нечего: mods.bat → 2 → мод → «поставить в игру».")
        return 1 if (behind or wrong) else 0

    try:
        return menu(configured)
    except KeyboardInterrupt:
        say()
        return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
