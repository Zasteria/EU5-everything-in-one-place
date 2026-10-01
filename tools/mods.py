#!/usr/bin/env python3
"""The mod manager: the workshop, the game's own copies, and this repository.

Everything the owner has to do by hand for a mod update, in one place and with
no session of mine in the loop:

    python3 tools/mods.py           the menu
    python3 tools/mods.py check     just the answer, for a script or a shortcut

What it can do, in the order the work actually happens:

1. **Look at every mod he is subscribed to** — not the five this repository
   tracks — and say which ones the workshop has moved on since Steam last
   downloaded them. That comparison is between Steam's own record of what is
   installed (`appworkshop_3450310.acf`) and Steam's public
   `GetPublishedFileDetails`, **by build id** — the `manifest` on one side
   against `hcontent_file` on the other — rather than by dates. Dates are what
   made this loop untrustworthy: Steam stamps an item as updated when it
   notices the update, which is not the same as having downloaded it, so a mod
   could read as current and load as the old version in game. Two build ids
   that differ are two different sets of files, and nothing about that is a
   guess. Anything Steam has no build id for falls back to the dates, and the
   report says which of the two answered.

2. **Download the ones he picks, into the game's own workshop folder**, so the
   next launch loads them. Steam itself will not be told to do this on demand —
   hence the unsubscribe-and-resubscribe dance this replaces — so it is done
   with `steamcmd` under his own account and the result is copied over
   `steamapps/workshop/content/3450310/<id>/`, which is where the game reads
   mods from. Anonymous does not work for this app; that was measured. Any mod
   can be re-fetched on demand, whether or not the check thinks it is behind —
   "ничего не отстаёт" is exactly the answer that used to be wrong. What
   steamcmd actually brought back is checked against what the workshop serves,
   and written down here, because Steam's own record still names the build
   *Steam* downloaded.

3. **Update the copies in this repository**, either kind: `reference/mods/` for
   the mods something here is built against (whole, unedited) and
   `reference/playset/` for the rest (text only). Then rebuild everything
   generated from them and say what moved. This copies out of the Steam folder,
   so a mod Steam has not actually fetched would be copied in stale and every
   generator would rebuild against the old files without a word — it stops and
   offers to download first instead.

4. **Move a mod between those two**, which is the only decision in here that
   changes what this repository watches: promoting one adds it to
   `tools/workshop_mods.txt` and it starts arriving whole and getting checked
   daily on GitHub; demoting one puts it back in the text-only tree; forgetting
   one deletes the copy and the daily check, leaving the Steam subscription
   alone.

5. **Commit and push**, to whatever branch he says, `main` included.

6. **After a game update, everything at once** (menu item 9): the workshop
   mods, the game's files with what the patch removed taken out too, every game
   file a mod replaces whole, the engine layers, the API dumps, the rebuild.

Nothing here needs the repository to be checked out anywhere in particular and
nothing needs a session: steps 1 and 2 do not touch git at all, so it is
usable as a mod updater on a day when modding is the last thing on his mind.

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
        if found:
            in_playset[found.group(1)] = mod

    for folder in sorted(content.iterdir()):
        if not folder.is_dir() or not folder.name.isdigit():
            continue
        stamp, manifest = versions.get(folder.name, (0, ""))
        mod = Mod(id=folder.name, installed=stamp, installed_manifest=manifest)
        if folder.name in tracked:
            mod.where, mod.key = REFERENCE, tracked[folder.name].key
            copy = in_reference.get(folder.name)
            if copy:
                mod.folder, mod.version = copy.path, copy.version
        elif folder.name in in_playset:
            mod.where = PLAYSET
            mod.folder = in_playset[folder.name].path
            mod.version = in_playset[folder.name].version
        world.mods.append(mod)

    # A tracked mod whose copy is here but which Steam has not downloaded still
    # belongs in the list — it is exactly the case worth seeing.
    for item in workshop.tracked():
        if world.by_id(item.id) is None:
            copy = in_reference.get(item.id)
            world.mods.append(Mod(id=item.id, where=REFERENCE, key=item.key,
                                  folder=copy.path if copy else None,
                                  version=copy.version if copy else None))

    if ask_steam:
        with Doing("спрашиваю мастерскую про %d мод(ов)" % len(world.mods)) as step:
            try:
                details = workshop.steam_details([m.id for m in world.mods])
                world.asked_steam = True
                step.finish("ответила")
            except SystemExit:
                details = {}
                step.finish("Steam не ответил — версии покажу по тому, что записано")
        for mod in world.mods:
            detail = details.get(mod.id, {})
            mod.title = detail.get("title", "")
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
        return default
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


def reference_is_current(mod: Mod) -> bool:
    """Is the copy under `reference/mods/` already the workshop's version?

    Copying a mod that has not moved costs nothing in git — identical files are
    no diff — but it reads as though the tool were rewriting things nobody
    touched, and National Destinies alone is a hundred megabytes of it. So the
    same test the update check uses answers here too: a folder committed after
    the workshop last moved cannot be behind, and one with uncommitted changes
    was just copied.
    """
    if mod.folder is None or not mod.folder.exists():
        return False
    if not mod.published:
        return True                      # Steam did not answer; do not churn on a guess
    if workshop.committed_at(mod.folder) > mod.published:
        return True
    return workshop.copied_since_commit(mod.folder)


def update_reference(world: World, chosen: list[Mod] | None = None) -> list[str]:
    """Replace the whole copies under `reference/mods/` from the workshop."""
    if world.content is None:
        say("папка мастерской не найдена.")
        return []
    tracked = {item.id: item for item in workshop.tracked()}
    wanted = [m for m in (chosen or world.mods) if m.id in tracked]
    if not wanted:
        say("нечего обновлять: ни один из выбранных модов не в reference.")
        return []

    here = workshop.local_copies()
    done: list[str] = []
    for mod in wanted:
        source = world.content / mod.id
        if not source.is_dir():
            say("  %-44s Steam его не скачал" % mod.name[:44])
            continue
        item = tracked[mod.id]
        existing = here.get(mod.id)
        folder = workshop.folder_for(item, source, existing)
        # National Destinies is a hundred megabytes; a copy of it is not instant
        # and the line has to appear before the wait, not after it.
        with Doing("копирую %s" % item.key) as step:
            files, size = workshop.copy_in(source, refs.MODS / folder)
            note = ""
            if existing is not None and existing.folder != folder:
                shutil.rmtree(existing.path, ignore_errors=True)
                note = ", заменил %s" % existing.folder
            step.finish("%s: %d файлов, %s%s"
                        % (folder, files, workshop.human(size), note))
        done.append(item.key)
    return done


def update_playset(world: World) -> None:
    """The text-only copies. Told where the workshop is, because this machine's
    Steam may be on a drive the default search does not know about."""
    if world.content is None:
        say("папка мастерской не найдена.")
        return
    run_python("tools/workshop.py", "playset", "--from", str(world.content))


def rebuild() -> None:
    """Rebuild what this repository compiles *from* the reference copies.

    Worth being plain about, because the output looks alarming otherwise: this
    touches only the `*_generated_*` files inside our own mods. Those are
    compiled from the reference copies — a translation is built against the base
    mod's English — so a base mod moving has to be followed here or the mod ships
    against a version that is gone. Nothing hand-written is read or rewritten.
    """
    say()
    say("--- пересобираю файлы *_generated_* в наших модах ---")
    say("    (они компилируются из reference; руками написанное не трогается)")
    run_python("tools/refresh.py", "--brief")
    if run_python("tools/workshop.py", "record") != 0:
        say("    отметку о версиях записать не удалось — это не страшно:")
        say("    проверка обновлений всё равно определит их по истории git.")


# ---------------------------------------------------------- moving mods around


def slug(text: str) -> str:
    made = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return made or "mod"


def promote(mod: Mod, world: World) -> None:
    """Track this mod: whole copy in `reference/mods/`, watched for updates."""
    default = slug(mod.title or mod.id)
    key = ask("Короткое имя для него [%s]: " % default, default)
    reason = ask("Зачем он здесь (одна строка): ", "")

    text = workshop.MANIFEST.read_text(encoding="utf-8").rstrip("\n")
    line = "%-11s %s" % (mod.id, key)
    if reason:
        line = "%-34s # %s" % (line, reason)
    text += "\n" + line + "\n"
    workshop.MANIFEST.write_text(text, encoding="utf-8")

    if mod.where == PLAYSET and mod.folder is not None:
        shutil.rmtree(mod.folder, ignore_errors=True)
    if world.content is not None and (world.content / mod.id).is_dir():
        item = workshop.Tracked(id=mod.id, key=key, reason=reason)
        source = world.content / mod.id
        folder = workshop.folder_for(item, source, None)
        files, size = workshop.copy_in(source, refs.MODS / folder)
        say("  %s: %d файлов, %s" % (folder, files, workshop.human(size)))
    say()
    say("%s теперь в reference — целиком, и за его обновлениями следит" % key)
    say("ежедневная проверка на GitHub.")


def demote(mod: Mod, world: World) -> None:
    """Stop tracking: text-only copy in the playset, no daily check."""
    lines = workshop.MANIFEST.read_text(encoding="utf-8").splitlines()
    kept = [line for line in lines if not line.strip().startswith(mod.id)]
    workshop.MANIFEST.write_text("\n".join(kept) + "\n", encoding="utf-8")

    if mod.folder is not None and mod.folder.exists():
        shutil.rmtree(mod.folder, ignore_errors=True)
    if world.content is not None and (world.content / mod.id).is_dir():
        item = workshop.Tracked(id=mod.id, key=slug(mod.title or mod.id), reason="")
        source = world.content / mod.id
        folder = workshop.folder_for(item, source, None)
        refs.PLAYSET.mkdir(parents=True, exist_ok=True)
        files, size = workshop.copy_slim(source, refs.PLAYSET / folder)
        say("  %s: %d файлов текста, %s" % (folder, files, workshop.human(size)))
    say()
    say("Готово. Помни: если на него что-то здесь опиралось — оно сломается,")
    say("потому что в playset лежит только текст.")


def forget(mod: Mod, world: World) -> None:
    """Убрать копию мода из репозитория совсем -- и из reference, и из playset.

    **Третья дверь рядом с `promote` и `demote`, и она никуда не ведёт.** Те две
    перекладывают копию между двумя деревьями; эта удаляет её. Нужна была ровно
    затем, зачем и появилась: 2026-09-12 владелец убрал Advanced Auto Build --
    «он говнище и больше не пригодится, всё самое нужное из него давно было
    взято», -- и сделать это из меню было нечем.

    **Подписка Steam не трогается.** Файлы в `steamapps/workshop/content` --
    его, не наши: мод остаётся установленным и играется как играл. Удаляется
    копия в этом репозитории и строка в `tools/workshop_mods.txt`, то есть
    ежедневная проверка обновлений.

    **Что на него опиралось, сломается**, и молча: генератор, читающий чужие
    английские ключи, после этого не соберётся. Поэтому спрашивается имя, а не
    «да/нет», -- то же, что делает сама мастерская, когда удаляет предмет.
    """
    say()
    say("Это удалит копию %s из репозитория:" % mod.name)
    if mod.folder is not None:
        say("  %s" % mod.folder)
    if mod.key:
        say("  и строку «%s» из tools/workshop_mods.txt — проверка обновлений прекратится" % mod.key)
    say()
    say("Подписка Steam не трогается: мод останется установленным и в игре.")
    say("Всё, что читало его файлы отсюда, сломается — генераторы переводов в том числе.")
    say()
    if ask("Впиши имя мода, чтобы подтвердить (Enter — отмена): ").strip() != mod.name.strip():
        say("Отменено.")
        return

    if mod.key or mod.id:
        lines = workshop.MANIFEST.read_text(encoding="utf-8").splitlines()
        kept = [line for line in lines if not line.strip().startswith(mod.id)]
        if len(kept) != len(lines):
            workshop.MANIFEST.write_text("\n".join(kept) + "\n", encoding="utf-8")
            say("  убрано из tools/workshop_mods.txt")

    if mod.folder is not None and mod.folder.exists():
        shutil.rmtree(mod.folder, ignore_errors=True)
        say("  удалено: %s" % mod.folder)
    else:
        say("  копии в репозитории и не было")

    say()
    say("Готово. Проверь `python3 tools/refresh.py`: генератор, который читал")
    say("этот мод, теперь падает, и его надо убрать из списка или вернуть копию.")


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


def screen_install(configured: dict) -> None:
    target = game_mods_dir(configured, make=True)
    if target is None:
        say()
        say("Не нашёл папку модов игры. Обычно она здесь:")
        say(r"  C:\Users\<ты>\Documents\Paradox Interactive\Europa Universalis V\mod")
        say("Укажи её один раз:")
        say('  mods.bat --game-mods "<путь>"')
        return

    say()
    say("Папка модов игры: %s" % target)
    say("Репозиторий: %s" % here())
    if yes("Сначала подтянуть свежее из GitHub (git pull)?"):
        was = workshop.git("rev-parse", "HEAD", check=False).stdout.strip()
        with Doing("git pull") as step:
            done = workshop.git("pull", check=False)
            step.finish("готово" if done.returncode == 0 else "не вышло")
        if done.returncode != 0:
            say((done.stdout + done.stderr).strip())
            say()
            say("Дальше ставится то, что лежит здесь сейчас — то есть старое.")
        else:
            now = workshop.git("rev-parse", "HEAD", check=False).stdout.strip()
            say("  %s" % ("подтянулось до %s" % here() if now != was
                          else "и так последнее — %s" % here()))

    mods = our_mods()
    say()
    # **«версия» and «в игре» are not the same question, and the pair read as one
    # on 2026-09-06**: he took «отличается» for a version mismatch and asked why
    # the version had changed. It had not — the column is the number in this
    # repository's `.metadata`, and the one beside it compares the *files* that
    # would be installed, byte for byte. Saying so in the headings is cheaper
    # than saying it again.
    # «в игре» is the version in the game's own copy of `.metadata`; the note
    # beside it compares the two, so a branch older than the game says so.
    say("  %-3s %-18s %-13s %-13s %-12s %s"
        % ("#", "мод", "версия тут", "версия в игре", "файлы в игре", "заметка"))
    older: set[str] = set()
    for number, mod in enumerate(mods, 1):
        state = installed_state(mod, target)
        in_game = installed_version(mod, target) if state != "нет в игре" else ""
        note = version_note(mod.version, in_game, state)
        if note == "ТУТ СТАРЕЕ":
            older.add(mod.path.name)
        say("  %-3d %-18s %-13s %-13s %-12s %s"
            % (number, mod.path.name[:18], (mod.version or "—")[:13],
               (in_game or "—")[:13], state, note))
    say()
    if older:
        say("ТУТ СТАРЕЕ — в этой ветке версия ниже, чем уже стоит в игре.")
        say("Поставишь — откатишь мод назад. Сначала переключись на нужную ветку.")
        say()
    say("Enter — поставить все, номера через запятую — только их,")
    answer = ask("«у» + номера — убрать из игры, 0 — назад: ")
    if answer == "0":
        return

    remove = answer.lower().startswith(("у", "y"))
    if remove:
        answer = answer[1:].strip()
    chosen: list[refs.Mod] = []
    if not answer:
        chosen = list(mods)
    else:
        for part in re.split(r"[,\s]+", answer):
            if part.isdigit() and 1 <= int(part) <= len(mods):
                chosen.append(mods[int(part) - 1])
    if not chosen:
        return
    downgrade = [mod.path.name for mod in chosen if mod.path.name in older]
    if not remove and downgrade and not yes(
            "Откатить к старой версии из этой ветки: %s?" % ", ".join(downgrade), default=False):
        chosen = [mod for mod in chosen if mod.path.name not in older]
        if not chosen:
            return

    say()
    trouble = False
    for mod in chosen:
        if remove:
            there = target / mod.path.name
            if there.is_dir():
                shutil.rmtree(there, ignore_errors=True)
                say("  %-22s убран из игры" % mod.path.name)
            else:
                say("  %-22s его там и не было" % mod.path.name)
            continue
        _, unknown = game_files(mod.path)
        with Doing("ставлю %s" % mod.path.name) as step:
            files, size = install(mod, target)
            step.finish("%d файлов, %s" % (files, workshop.human(size)))
        if unknown:
            say("     не знаю, что это, и потому не копировал: %s" % ", ".join(unknown))
        # Read back rather than trust the loop above. Everything that has gone
        # wrong here was silent — a folder the game does not read, a copy that
        # half happened — and this is the one line that would have caught it.
        state = installed_state(mod, target)
        if state != "совпадает":
            trouble = True
            say("     ПРОВЕРКА НЕ ПРОШЛА: в игре «%s», а не «совпадает»." % state)
            say("     Смотри сам: %s" % (target / mod.path.name))

    say()
    if trouble:
        say("Что-то не доехало. Пока это не сойдётся, игра грузит старую версию,")
        say("и по ней ничего проверять нельзя. Логи потом читай через")
        say("  python3 tools/which_build.py <папка с логами>")
        say("— он скажет, какую сборку игра взяла на самом деле.")
        return
    if not remove:
        say("Поставлено из %s." % here())
        say("Готово. В игру уехало только то, что она читает — .metadata и папки")
        say("монтирования; генераторы, переводы-исходники и README остались здесь.")
        say("Если мод ставится впервые, включи его в лаунчере один раз; дальше")
        say("обновления подхватываются сами, папка та же.")


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
        % (len(world.mods),
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


def screen_updates(world: World, configured: dict) -> None:
    outdated = show_updates(world)
    if outdated:
        say()
        chosen = pick(outdated,
                      "Что скачать? [Enter — все, номера через запятую, 0 — назад]: ")
    else:
        # There is always something to do here, because "ничего не отстаёт" is
        # exactly the answer that used to be wrong: Steam marks a mod updated
        # when it notices the update, and the files may not have followed. So a
        # mod can be re-fetched on demand whatever the check thinks — which is
        # what unsubscribing and resubscribing was for.
        if world.content is None or not world.mods:
            return
        say()
        if not yes("Всё равно перекачать какой-нибудь мод заново?", default=False):
            return
        say()
        for number, mod in enumerate(world.mods, 1):
            say("  %-3d %-46s %-10s %s"
                % (number, mod.name[:46], mod.where, when(mod.installed)))
        say()
        chosen = pick(world.mods, "Какие? [номера через запятую, 0 — назад]: ",
                      default_all=False)
    if not chosen:
        return
    got = download(configured, chosen, world.content)
    if not got:
        return
    say()
    if yes("Обновить и копии в репозитории для тех из них, что там есть?"):
        say()
        update_reference(world, got)
        if any(m.where == PLAYSET for m in got):
            update_playset(world)
        rebuild()


def screen_repository(world: World, configured: dict) -> None:
    say()
    say("Что обновить в репозитории из того, что уже скачано Steam:")
    say("  1  reference — пять модов целиком, те, на которых всё здесь держится")
    say("  2  playset — все остальные, только текст")
    say("  3  и то, и другое")
    say("  0  назад")
    choice = ask("> ")
    if choice not in {"1", "2", "3"}:
        return
    say()
    copied: list[str] = []
    if choice in {"1", "3"}:
        tracked = {item.id for item in workshop.tracked()}
        mine = [m for m in world.mods if m.id in tracked]
        behind = [m for m in mine if not reference_is_current(m)]
        if behind:
            say("Отстают от мастерской копии в reference:")
            for mod in behind:
                say("  %s%s" % (mod.name,
                                "   ← и в папке Steam тоже старая сборка"
                                if mod.outdated else ""))
            # The trap this walks into otherwise: this copies out of the Steam
            # workshop folder, so a mod Steam has not actually fetched is copied
            # in stale, the generators rebuild against the old files, and
            # everything reads as done. Caught here rather than in a git diff.
            stale = [mod for mod in behind if mod.outdated]
            if stale:
                say()
                say("Копировать их сейчас — значит принести в репозиторий ту же")
                say("старую версию: reference берётся из папки Steam, а не из сети.")
                if yes("Сначала скачать свежие (%d)?" % len(stale)):
                    got = download(configured, stale, world.content)
                    if got:
                        world.mods = gather(configured).mods
                        behind = [m for m in world.mods
                                  if m.id in {b.id for b in behind}]
            say()
            copied = update_reference(world, behind)
        else:
            say("Копии в reference уже те же, что в мастерской — копировать нечего.")
            if yes("Всё равно перекопировать все %d?" % len(mine), default=False):
                copied = update_reference(world)
    if choice in {"2", "3"}:
        update_playset(world)
    # Only a changed reference copy can change anything generated: nothing here
    # compiles from the playset, and a rebuild that had no input to react to is
    # ten seconds of output saying so.
    if copied:
        rebuild()


def screen_list(world: World, configured: dict) -> None:
    while True:
        say()
        say("  %-3s %-46s %-10s %-10s %s" % ("#", "мод", "где", "версия", "обновление"))
        for number, mod in enumerate(world.mods, 1):
            say("  %-3d %-46s %-10s %-10s %s"
                % (number, mod.name[:46], mod.where, (mod.version or "—")[:10],
                   "есть" if mod.outdated else ""))
        say()
        answer = ask("Номер мода (0 — назад): ")
        if not answer or answer == "0":
            return
        if not answer.isdigit() or not 1 <= int(answer) <= len(world.mods):
            continue
        mod = world.mods[int(answer) - 1]

        say()
        say("%s  (id %s)" % (mod.name, mod.id))
        say("  сейчас: %s" % mod.where)
        if mod.where == REFERENCE:
            say("  1  вернуть в playset (только текст, без ежедневной проверки)")
        else:
            say("  1  отправить в reference (целиком, с проверкой обновлений)")
        say("  2  скачать свежую версию в Steam")
        if mod.where != UNTRACKED:
            say("  3  убрать копию из репозитория совсем (подписку Steam не трогает)")
        say("  0  назад")
        choice = ask("> ")
        if choice == "1":
            if mod.where == REFERENCE:
                if yes("Убрать %s из reference?" % mod.name, default=False):
                    demote(mod, world)
            else:
                promote(mod, world)
            world.mods = gather(configured).mods
        elif choice == "2":
            download(configured, [mod], world.content)
        elif choice == "3" and mod.where != UNTRACKED:
            forget(mod, world)
            world.mods = gather(configured).mods


def screen_publish() -> None:
    """Готов ли наш мод к мастерской — и что вставлять на её страницу."""
    import publish

    mods = our_mods()
    say()
    say("Проверяю то, на что мастерская не ругается, а просто молча роняет:")
    say("теги, картинку, версию, BOM. Как загружать — docs/WORKSHOP.md.")
    say()
    publish.main(["publish"])
    say()
    say("Номер мода — подробности и текст для страницы,")
    say("«к» + номер — сделать manager-config.json для загрузчика, Enter — назад.")
    for number, mod in enumerate(mods, 1):
        say("  %-3d %s" % (number, mod.path.name))
    answer = ask("> ").strip()

    config = answer.lower().startswith(("к", "k"))
    if config:
        answer = answer[1:].strip()
    if not (answer.isdigit() and 1 <= int(answer) <= len(mods)):
        return
    mod = mods[int(answer) - 1]

    if not config:
        publish.main(["publish", mod.path.name])
        ask("Enter — назад ")
        return

    # The uploader takes the *installed* copy, not this repository: the folder
    # in the repository also holds tools/ and workshop/, which are not the mod.
    target = game_mods_dir(configured)
    if target is None or not (target / mod.path.name).is_dir():
        say()
        say("Сначала поставь мод в игру — пункт 4. Загружается именно та папка,")
        say("а не эта: здесь рядом лежат tools/ и workshop/, они не часть мода.")
        ask("Enter — назад ")
        return
    say()
    say(publish.write_manager_config(mod.path, target / mod.path.name,
                                     target / "manager-config.json"))
    say("Открой его загрузчиком: https://github.com/kaiser-chris/pdx-workshop-manager")
    say("Steam должен быть запущен и залогинен. Подробности — docs/WORKSHOP.md.")
    ask("Enter — назад ")


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


def screen_from_game(configured: dict) -> None:
    """Забрать из установленной игры то, чего нет в репозитории.

    **Существует потому, что сессия не видит игру, а видит только репозиторий.**
    Она читает то, что закоммичено, и то, что приложено к сообщению — больше
    ничего. Пока файла нет ни там, ни там, любой вопрос про него сессия может
    только угадать, и 2026-09-03 это стоило двух кругов: окно мода не
    открывалось, потому что его надо назвать в `gui/scripted_widgets/`, а всей
    этой папки в `reference/game/` не было — `in_game/gui` никто не выкачивал.

    Две половины, и они попадают к сессии по-разному:

    - **файлы игры** ложатся в `reference/game/` и уезжают коммитом;
    - **логи** весят слишком много для репозитория, поэтому они собираются в
      маленький архив, который остаётся приложить к сообщению.
    """
    while True:
        say()
        say("  1  Файлы игры → reference/game/  (по списку tools/game_files_manifest.txt)")
        say("  2  Логи игры → маленький архив, который можно приложить в чат")
        say("  0  назад")
        choice = ask("> ")
        if choice == "1":
            say()
            given = configured.get("game")
            run_python("tools/extract_game_files.py", *(["--game", given] if given else []))
            say()
            say("Скопировано в reference/game/. Пока это не закоммичено —")
            say("в GitHub Desktop — сессия этих файлов не видит.")
            say()
            ask("Enter — назад ")
        elif choice == "2":
            screen_logs()
        elif choice in {"0", "q", "в", "назад"}:
            return


# --------------------------------------------------- после обновления игры

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


def screen_full_update(world: World, configured: dict) -> World:
    """Всё, что в reference пришло извне, — заново, после обновления игры.

    Один проход вместо четырёх пунктов, которые надо помнить: моды из
    мастерской, файлы игры (с локализацией, окнами и слоями движка), дампы API —
    и пересборка того, что из них компилируется. Удаляет то, что игра убрала:
    без этого файл, которого в игре больше нет, лежал бы здесь как живой.

    Моды идут первыми: шаг с файлами игры ищет, какие файлы игры моды заменяют
    целиком, и искать это надо в обновлённых модах, а не во вчерашних.
    """
    say()
    say("Полное обновление reference после обновления игры. Четыре шага:")
    say("  1  моды из мастерской: скачать отстающие, обновить reference и playset")
    say("  2  файлы игры: скрипты, события, окна, локализация, слои движка,")
    say("     и каждый файл игры, который какой-нибудь мод заменяет целиком;")
    say("     то, что игра убрала, удаляется и отсюда")
    say("  3  дампы API движка (script_docs, dump_data_types)")
    say("  4  пересобрать файлы *_generated_* в наших модах")
    if not yes("Начать?"):
        return world

    say()
    say("--- 1. Моды из мастерской ---")
    if world.content is None:
        say("Папка мастерской не найдена — моды пропускаю.")
    else:
        outdated = show_updates(world)
        if outdated and yes("Скачать свежие (%d) через steamcmd?" % len(outdated)):
            if download(configured, outdated, world.content):
                world = gather(configured)
        tracked = {item.id for item in workshop.tracked()}
        mine = [m for m in world.mods if m.id in tracked]
        # Без ответа Steam не видно, кто отстал, — тогда копируются все.
        behind = ([m for m in mine if not reference_is_current(m)]
                  if world.asked_steam else mine)
        say()
        if behind:
            update_reference(world, behind)
        else:
            say("Копии в reference/mods те же, что в мастерской.")
        update_playset(world)

    say()
    say("--- 2. Файлы игры ---")
    game, updated = game_install(configured, world.content)
    if game is None:
        say("Steam не сказал, где стоит игра.")
        given = ask("Путь к папке Europa Universalis V (Enter — искать самому): ").strip().strip('"')
        if given:
            configured["game"] = given
            settings_write(configured)
            game = Path(given)
    args = ["--prune"]
    if game is not None:
        args += ["--game", str(game)]
    if world.content is not None:
        args += ["--mods-from", str(world.content)]
    taken = run_python("tools/extract_game_files.py", *args) == 0

    say()
    say("--- 3. Дампы API движка ---")
    fresh = update_api_dumps(updated)
    if not fresh:
        say("Их снимает только сама игра. Один раз:")
        say("  Steam → EU5 → Свойства → Параметры запуска: -debug_mode")
        say("  в игре открой консоль (~) и введи  script_docs  затем  dump_data_types")
        say("  выйди из игры, убери -debug_mode и снова выбери этот пункт:")
        say("  остальное повторится без изменений, а дампы лягут в reference/game/docs.")

    say()
    say("--- 4. Пересборка ---")
    rebuild()
    say()
    say("Строки FAIL после пересборки коммиту не мешают: это проверки наших модов")
    say("(например, «версия та же, а файлы изменены» — их пересобрали под новую")
    say("игру). Их разбирает сессия, когда подгоняет моды.")

    say()
    say("=" * 62)
    say("Готово. Что дальше:")
    say("  GitHub Desktop → закоммить всё одним коммитом и запушь,")
    say("  потом напиши в тред — сессия сравнит новую версию со старой.")
    if not taken:
        say("  !! Шаг 2 с файлами игры не прошёл — выше написано, что он сказал.")
    if not fresh:
        say("  !! Дампы API старые — шаг 3 выше говорит, как снять новые.")
    say()
    ask("Enter — назад ")
    return gather(configured)


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


def menu(configured: dict) -> int:
    world = gather(configured)
    while True:
        outdated = len(world.outdated)
        say()
        say("=" * 62)
        say("  МОДЫ EU5")
        say("  подписка: %-3d   reference: %-3d   playset: %-3d   обновлений: %d"
            % (len(world.mods),
               sum(1 for m in world.mods if m.where == REFERENCE),
               sum(1 for m in world.mods if m.where == PLAYSET),
               outdated))
        say("=" * 62)
        say("  1  Обновить моды в Steam: сверить сборки, скачать, заменить")
        say("  2  Обновить копии в репозитории (reference / playset)")
        say("  3  Мои моды: список, что где лежит, перенос между ними и удаление")
        say("  4  Поставить наши моды в игру")
        say("  5  Готов ли наш мод к мастерской")
        say("  6  Забрать диагностику из игры")
        say("  7  Забрать из игры файлы или логи")
        say("  8  Перечитать всё заново")
        say("  9  После обновления игры: обновить в репозитории всё — игру,")
        say("     локализацию, дампы API, моды, — и пересобрать")
        say("  0  Выход")
        say()
        say("  Коммит и пуш — в GitHub Desktop; отсюда репозиторий не пишется.")
        choice = ask("> ")

        if choice == "1":
            screen_updates(world, configured)
            world = gather(configured)
        elif choice == "2":
            screen_repository(world, configured)
            world = gather(configured)
        elif choice == "3":
            screen_list(world, configured)
        elif choice == "4":
            screen_install(configured)
        elif choice == "5":
            screen_publish()
        elif choice == "6":
            screen_diag()
        elif choice == "7":
            screen_from_game(configured)
        elif choice == "8":
            world = gather(configured)
        elif choice == "9":
            world = screen_full_update(world, configured)
        elif choice in {"0", "q", "в", "выход"}:
            return 0


# ------------------------------------------------------------------- the shell


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="mods.py",
        description="Обновление модов EU5: мастерская, папка игры и этот репозиторий.")
    parser.add_argument("command", nargs="?", default="menu",
                        choices=["menu", "check", "full"],
                        help="menu — меню (по умолчанию); check — только отчёт; "
                             "full — пункт 9, полное обновление после патча")
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
            say("ней нечего: mods.bat → 4 ставит заново.")
        return 1 if (behind or wrong) else 0

    if parsed.command == "full":
        screen_full_update(gather(configured), configured)
        return 0

    try:
        return menu(configured)
    except KeyboardInterrupt:
        say()
        return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
