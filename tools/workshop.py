#!/usr/bin/env python3
"""What the Steam Workshop has now, and how it gets from there into git.

The mods in `reference/` are other people's, and they update whenever their
authors feel like it. Until now that loop was entirely manual and entirely in
the owner's head: notice an update somehow, unsubscribe and resubscribe to make
Steam actually fetch it, find the folder, copy it in, commit, push, and only
then find out whether the update moved anything a mod here compiles from.

This tool is that loop, minus the parts a machine can do.

    python3 tools/workshop.py                    what the workshop has vs what is here
    python3 tools/workshop.py sync               copy the newer ones in, rebuild, commit
    python3 tools/workshop.py record             stamp the copies here as current
    python3 tools/workshop.py playset            the rest of the playset, text only

`status` needs no Steam, no account and no game — it asks Steam's public
`GetPublishedFileDetails` for the tracked ids and compares the answer against
`reference/workshop_generated_state.json`, which is what the last sync wrote
down. A GitHub workflow used to run it daily and keep an issue open; the owner
had no use for it and it was removed 2026-10-12.

`sync` needs the files, and the files only exist on a machine that owns the
game. **Anonymous download does not work** — `steamcmd +login anonymous
+workshop_download_item 3450310 <id>` answers `ERROR! Download item failed
(Failure)` for this app, which was measured, not assumed. So nothing can pull a
workshop mod straight into GitHub; the shortest honest loop is: the owner's box
already has the files, and this copies them in and pushes in one command.

    python3 tools/workshop.py sync --commit --push

Without `--from` it looks for `steamapps/workshop/content/3450310/` in the usual
Steam locations. With `--steamcmd` it runs steamcmd first, logged in as the
owner, which fetches the current version of each tracked id without touching
subscriptions — that is the answer to having to unsubscribe and resubscribe to
make Steam notice an update.

There is a PowerShell twin, `tools/sync_workshop.ps1`, for the Windows box: same
copy, same commit, no Python needed.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import refs  # noqa: E402

# Europa Universalis V on Steam. Its workshop items live under
# steamapps/workshop/content/<this>/<item id>/, which is also the path the game
# writes into debug.log when it mounts one — tools/playset.py reads those.
APP_ID = "3450310"

MANIFEST = Path(__file__).resolve().parent / "workshop_mods.txt"
STATE = refs.REFERENCE / "workshop_generated_state.json"

# Steam answers this one without a key and without an account. It is the only
# part of the loop that works from anywhere.
DETAILS_URL = "https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/"

# Where Steam usually keeps workshop content, per platform. First hit wins.
CANDIDATES = {
    "win32": [
        r"C:\Program Files (x86)\Steam\steamapps\workshop\content",
        r"C:\Program Files\Steam\steamapps\workshop\content",
        r"C:\Steam\steamapps\workshop\content",
        r"D:\Steam\steamapps\workshop\content",
        r"D:\SteamLibrary\steamapps\workshop\content",
        r"E:\SteamLibrary\steamapps\workshop\content",
        r"F:\SteamLibrary\steamapps\workshop\content",
    ],
    "darwin": [
        "~/Library/Application Support/Steam/steamapps/workshop/content",
    ],
    "linux": [
        "~/.steam/steam/steamapps/workshop/content",
        "~/.local/share/Steam/steamapps/workshop/content",
        "~/snap/steam/common/.local/share/Steam/steamapps/workshop/content",
    ],
}


# ------------------------------------------------------------------ the tracked


@dataclass(frozen=True)
class Tracked:
    """One line of `tools/workshop_mods.txt`."""

    id: str
    key: str
    reason: str


def tracked() -> list[Tracked]:
    out: list[Tracked] = []
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        body, _, reason = line.partition("#")
        parts = body.split()
        if len(parts) < 2:
            raise SystemExit("%s: cannot read %r — expected `<id> <key>`" % (MANIFEST, line))
        out.append(Tracked(id=parts[0], key=parts[1], reason=reason.strip()))
    return out


def local_copies() -> dict[str, refs.Mod]:
    """Workshop id -> the copy in `reference/mods/`, where there is one.

    Matched on the id in the folder name first, because that is unambiguous, and
    on the mod's identity second, because a folder copy arrives without the
    number — that is exactly how National Destinies got in here.
    """
    found: dict[str, refs.Mod] = {}
    here = refs.mods()
    for item in tracked():
        by_folder = [m for m in here if item.id in m.folder]
        if len(by_folder) == 1:
            found[item.id] = by_folder[0]
            continue
        hints = refs.KNOWN.get(item.key, (item.key,))
        matched = [m for m in here if any(m.matches(h) for h in hints)]
        if len(matched) == 1:
            found[item.id] = matched[0]
    return found


# ------------------------------------------------------------------- what Steam


def steam_details(ids: list[str], timeout: float = 20.0) -> dict[str, dict]:
    """Ask Steam about these items. Raises `SystemExit` when the network says no."""
    if not ids:
        return {}
    body = urllib.parse.urlencode(
        [("itemcount", str(len(ids)))]
        + [("publishedfileids[%d]" % n, item) for n, item in enumerate(ids)]
    ).encode("ascii")
    request = urllib.request.Request(DETAILS_URL, data=body)
    # Steam's public endpoint drops a connection now and again — a TLS handshake
    # that times out once is not an answer, and treating it as one turned a
    # perfectly good run into a red line about the network.
    for attempt in (1, 2, 3):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as answer:
                payload = json.load(answer)
            break
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            if attempt == 3:
                raise SystemExit(
                    "could not ask Steam what the workshop has: %s\n"
                    "`--offline` reports what is written down here instead." % exc
                ) from exc
            time.sleep(2 * attempt)
    out = {}
    for detail in payload.get("response", {}).get("publishedfiledetails", []):
        if detail.get("result") != 1:
            continue
        out[str(detail["publishedfileid"])] = detail
    return out


def when(stamp: object) -> str:
    if not stamp:
        return "—"
    return time.strftime("%Y-%m-%d %H:%M", time.gmtime(int(stamp)))


# -------------------------------------------------------------------- the state


def state_read() -> dict:
    if not STATE.is_file():
        return {"mods": {}}
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit("%s: %s — delete it and run `record`" % (STATE, exc)) from exc


def state_write(entries: dict) -> None:
    STATE.write_text(
        json.dumps(
            {
                "_written_by": "tools/workshop.py — do not edit by hand",
                "app_id": APP_ID,
                "recorded": when(time.time()),
                "mods": entries,
            },
            indent=1,
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def committed_at(folder: Path) -> int:
    """When git last recorded a change to this folder, as a unix time.

    This is the one honest way to stamp a copy that arrived before this tool
    existed: a folder committed *after* the workshop last updated cannot be
    older than that update, because the owner copied it in from the workshop
    after it happened. A folder committed before it may or may not be behind,
    and this refuses to guess — see `record`.
    """
    done = subprocess.run(
        ["git", "log", "-1", "--format=%ct", "--", str(folder)],
        cwd=refs.REPO, capture_output=True, text=True,
    )
    try:
        return int(done.stdout.strip())
    except ValueError:
        return 0


def copied_since_commit(folder: Path) -> bool:
    """Is there a copy in the working tree that git has not recorded yet?

    Nothing under `reference/` is ever edited by hand — every file in it arrived
    by being copied wholesale out of the workshop folder — so an uncommitted
    change there means exactly one thing: the copy was refreshed and not
    committed yet. Without this, a sync followed by `record` in the same breath
    stamps the mod it has just brought in as `behind`, because git still has
    only the old copy and `committed_at` is the old commit's date. That is what
    told the owner two freshly copied mods were still out of date.
    """
    return bool(git("status", "--porcelain", "--", str(folder),
                    check=False).stdout.strip())


def record(ids: list[str] | None = None, synced: set[str] | None = None) -> dict:
    """Write down what the workshop has, and whether the copy here is that.

    Three ways an entry can come to be, and the state file says which:

    - `sync` — this tool copied the folder in, so the two are the same thing;
    - `committed_after` — git recorded the copy here after the workshop's last
      update, so it cannot be behind;
    - `uncommitted` — git has not recorded the copy that is there, so something
      copied it in and has not committed yet;
    - `behind` — none of those, and the workshop has moved since the copy here
      was committed. That is not a stamp, it is a finding: `status` reports it.

    Without this, a copy brought in the old way goes on being reported as an
    update that has not arrived yet.
    """
    entries = dict(state_read().get("mods", {}))
    here = local_copies()
    synced = synced or set()
    wanted = ids or [item.id for item in tracked()]
    details = steam_details(wanted)
    for item in tracked():
        if item.id not in wanted:
            continue
        detail = details.get(item.id, {})
        mod = here.get(item.id)
        moved = int(detail.get("time_updated") or 0)

        if item.id in synced:
            basis = "sync"
        elif mod is None:
            basis = "missing"
        elif moved and committed_at(mod.path) > moved:
            basis = "committed_after"
        elif copied_since_commit(mod.path):
            basis = "uncommitted"
        else:
            basis = "behind"

        entries[item.id] = {
            "key": item.key,
            "title": detail.get("title"),
            "time_updated": detail.get("time_updated"),
            "file_size": detail.get("file_size"),
            "hcontent_file": detail.get("hcontent_file"),
            "basis": basis,
            "folder": mod.folder if mod else None,
            "mod_id": mod.id if mod else None,
            "version": mod.version if mod else None,
        }
    state_write(entries)
    return entries


# ------------------------------------------------------------------- the status

CURRENT = "current"
STALE = "workshop moved"
BEHIND = "behind"
UNCOMMITTED = "copied, not committed"
UNRECORDED = "never recorded"
HAND_COPIED = "copied by hand since"
MISSING = "not in reference/"


def verdicts(offline: bool = False) -> list[tuple[Tracked, dict, dict, refs.Mod | None, str]]:
    """One row per tracked mod: what Steam says, what is written down, and so what."""
    items = tracked()
    here = local_copies()
    written = state_read().get("mods", {})
    details = {} if offline else steam_details([item.id for item in items])

    rows = []
    for item in items:
        mod = here.get(item.id)
        detail = details.get(item.id, {})
        note = written.get(item.id, {})

        moved = int((detail or note).get("time_updated") or 0)

        if mod is None:
            verdict = MISSING
        elif moved and committed_at(mod.path) > moved:
            # git settles it without anything having to be written down: the
            # copy here was committed after the workshop last moved, so it
            # cannot be behind. This is what makes a sync from a box with no
            # Python — one that never got to run `record` — still come out
            # current on the next check.
            verdict = CURRENT
        elif copied_since_commit(mod.path):
            # Copied in and not committed yet — which git cannot date, so it is
            # said out loud rather than counted as either current or behind.
            verdict = UNCOMMITTED
        elif not note.get("time_updated"):
            verdict = UNRECORDED
        elif note.get("basis") == "behind" and not (
                detail and int(detail.get("time_updated", 0)) > int(note["time_updated"])):
            # Recorded as behind and the workshop has not moved again since.
            verdict = BEHIND
        elif note.get("version") and mod.version and note["version"] != mod.version:
            # The copy here moved without this tool watching, so what is written
            # down is about some older copy and cannot answer the question.
            verdict = HAND_COPIED
        elif detail and int(detail.get("time_updated", 0)) > int(note["time_updated"]):
            verdict = STALE
        elif offline:
            verdict = "not asked"
        else:
            verdict = CURRENT
        rows.append((item, detail, note, mod, verdict))
    return rows


def status(argv: argparse.Namespace) -> int:
    rows = verdicts(offline=argv.offline)
    stale = [row for row in rows if row[-1] in (STALE, BEHIND, UNRECORDED, HAND_COPIED, MISSING)]

    if not argv.quiet:
        print("%-22s %-10s %-16s %-16s %s" % ("mod", "here", "workshop", "recorded", ""))
        for item, detail, note, mod, verdict in rows:
            print("%-22s %-10s %-16s %-16s %s" % (
                item.key,
                (mod.version if mod and mod.version else "—")[:10],
                when(detail.get("time_updated")),
                when(note.get("time_updated")),
                verdict,
            ))
        print()

    for item, detail, note, mod, verdict in rows:
        if verdict == UNCOMMITTED:
            print("%s was copied in and is not committed — `git status` for what it"
                  " brought, then commit it" % item.key)

    for item, detail, note, mod, verdict in stale:
        if verdict == STALE:
            print("%s updated on the workshop %s — here since %s%s" % (
                item.key, when(detail.get("time_updated")), when(note.get("time_updated")),
                "\n    %s" % item.reason if item.reason else ""))
        elif verdict == MISSING:
            print("%s is tracked but has no copy in reference/" % item.key)
        elif verdict == UNRECORDED:
            print("%s has never been recorded — run `python3 tools/workshop.py record`" % item.key)
        elif verdict == BEHIND:
            print("%s is behind: the workshop moved on %s, after the copy here was committed%s" % (
                item.key, when(note.get("time_updated")),
                "\n    %s" % item.reason if item.reason else ""))
        elif verdict == HAND_COPIED:
            print("%s was copied in by hand since the last record (%s here, %s written down)"
                  " — run `python3 tools/workshop.py record`" % (
                      item.key, mod.version, note.get("version")))

    if not stale:
        if not argv.quiet:
            print("every tracked mod here is the version the workshop has.")
        return 0

    if any(row[-1] in (STALE, BEHIND) for row in stale):
        print()
        print("to bring them in, on the machine that has Steam:")
        print("  python3 tools/workshop.py sync --commit --push")
    return 1


# --------------------------------------------------------------------- the sync


def find_content(given: str | None) -> Path:
    """The folder that holds `<workshop id>/` folders for this game."""
    if given:
        root = Path(given).expanduser()
        # Point it at either the content root or the app's folder inside it.
        for candidate in (root / APP_ID, root):
            if candidate.is_dir():
                return candidate
        raise SystemExit("no such folder: %s" % root)

    tried = []
    for path in CANDIDATES.get(sys.platform, CANDIDATES["linux"]):
        candidate = Path(path).expanduser() / APP_ID
        tried.append(candidate)
        if candidate.is_dir():
            return candidate
    print("no workshop content for app %s found. Looked in:" % APP_ID, file=sys.stderr)
    for path in tried:
        print("  %s" % path, file=sys.stderr)
    print("\nPass it explicitly:\n"
          "  python3 tools/workshop.py sync --from \"<...>/steamapps/workshop/content\"",
          file=sys.stderr)
    raise SystemExit(2)


def steamcmd_fetch(steamcmd: str, login: str | None, ids: list[str]) -> Path:
    """Have steamcmd download these items, and say where it put them.

    This is the part that replaces unsubscribing and resubscribing: steamcmd
    fetches the current version on demand, whatever the Steam client thinks it
    already has. It needs the owner's own login — anonymous is refused for this
    app, which was tried.
    """
    binary = Path(steamcmd).expanduser()
    if not binary.exists():
        raise SystemExit("no steamcmd at %s" % binary)
    command = [str(binary), "+login", login or "anonymous"]
    for item in ids:
        command += ["+workshop_download_item", APP_ID, item]
    command += ["+quit"]
    print("steamcmd: fetching %d item(s)%s" % (len(ids), " as %s" % login if login else ""))
    done = subprocess.run(command)
    if done.returncode != 0:
        print("steamcmd exited %d — see its output above. A login it cannot complete"
              " without a Steam Guard code has to be run once by hand." % done.returncode,
              file=sys.stderr)
    return binary.resolve().parent / "steamapps/workshop/content" / APP_ID


def folder_for(item: Tracked, source: Path, existing: refs.Mod | None) -> str:
    """What to call this mod's folder under `reference/mods/`.

    A folder that already carries the workshop id keeps its name: renaming it
    churns the whole tree in git for nothing. Anything else is renamed to
    `<workshop id>_<what the mod calls itself>`, which is the shape a workshop
    copy arrives in — and which does not carry a version number that stops being
    true at the next update, the way a hand-copied folder's name does.
    """
    if existing is not None and item.id in existing.folder:
        return existing.folder
    name = None
    for candidate in (source / ".metadata/metadata.json", source / "metadata/metadata.json"):
        if candidate.is_file():
            try:
                data = json.loads(candidate.read_text(encoding="utf-8-sig"))
            except json.JSONDecodeError:
                data = {}
            name = data.get("id") or data.get("name")
            break
    slug = "".join(c if c.isalnum() else "_" for c in (name or item.key).lower())
    while "__" in slug:
        slug = slug.replace("__", "_")
    return "%s_%s" % (item.id, slug.strip("_"))


def copy_in(source: Path, target: Path) -> tuple[int, int]:
    """Replace `target` with `source`, wholesale. Returns (files, bytes).

    Wholesale, not merged: an update that *deletes* a file has to delete it here
    too, or the tree grows a file the mod no longer ships and a generator goes on
    compiling from it.
    """
    if target.exists():
        shutil.rmtree(target)
    files = size = 0
    for path in sorted(source.rglob("*")):
        if not path.is_file():
            continue
        destination = target / path.relative_to(source)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
        files += 1
        size += path.stat().st_size
    return files, size


def human(size: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return "%.0f %s" % (size, unit) if unit == "B" else "%.1f %s" % (size, unit)
        size /= 1024
    return "%.1f GB" % size


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    done = subprocess.run(["git", *args], cwd=refs.REPO, capture_output=True, text=True)
    if check and done.returncode != 0:
        raise SystemExit("git %s failed:\n%s" % (" ".join(args), (done.stdout + done.stderr).strip()))
    return done


def sync(argv: argparse.Namespace) -> int:
    items = tracked()
    if argv.only:
        wanted = {name.lower() for name in argv.only}
        items = [i for i in items if i.id in wanted or i.key.lower() in wanted]
        if not items:
            raise SystemExit("nothing tracked matches %s" % ", ".join(argv.only))

    if argv.steamcmd:
        source_root = steamcmd_fetch(argv.steamcmd, argv.login, [i.id for i in items])
    else:
        source_root = find_content(argv.source)
    print("from:   %s" % source_root)
    print("into:   %s" % refs.MODS)
    print()

    here = local_copies()
    copied: list[tuple[Tracked, str, int, int]] = []
    for item in items:
        source = source_root / item.id
        if not source.is_dir():
            print("  %-22s not in the workshop folder — Steam has not downloaded it" % item.key)
            continue
        existing = here.get(item.id)
        folder = folder_for(item, source, existing)
        target = refs.MODS / folder

        if argv.dry_run:
            print("  %-22s would replace %s" % (item.key, folder))
            continue

        files, size = copy_in(source, target)
        copied.append((item, folder, files, size))
        note = ""
        # A folder copy and a workshop copy of the same mod would both answer to
        # refs.mod(), and then every tool that asks for that mod fails on the
        # ambiguity. The one that is not the folder just written goes.
        if existing is not None and existing.folder != folder and not argv.keep_old:
            shutil.rmtree(existing.path, ignore_errors=True)
            note = "   (replaced %s)" % existing.folder
        print("  %-22s %-40s %4d files %9s%s" % (item.key, folder, files, human(size), note))

    if argv.dry_run:
        print("\n--dry-run: nothing written.")
        return 0
    if not copied:
        print("\nnothing copied.")
        return 1

    if not argv.no_refresh:
        print()
        subprocess.run([sys.executable, str(refs.REPO / "tools/refresh.py")], cwd=refs.REPO)

    print()
    try:
        ids_copied = {item.id for item, *_ in copied}
        record(list(ids_copied), synced=ids_copied)
        print("recorded what the workshop has in %s" % STATE.relative_to(refs.REPO))
    except SystemExit as exc:
        print("could not record the workshop side (%s) — run `record` when there is network." % exc)

    if argv.commit or argv.push:
        names = ", ".join(item.key for item, *_ in copied)
        message = argv.message or "reference: %s from the workshop" % names
        git("add", "--", "reference", "mods")
        if not git("diff", "--cached", "--quiet", check=False).returncode:
            print("nothing changed — the copies here were already the current ones.")
            return 0
        git("commit", "-m", message)
        print("committed: %s" % message)

    if argv.push:
        branch = argv.branch or git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        for attempt, wait in enumerate((2, 4, 8, 16, 0)):
            done = git("push", "-u", "origin", branch, check=False)
            if done.returncode == 0:
                print("pushed to %s" % branch)
                break
            print((done.stdout + done.stderr).strip())
            if wait:
                print("push failed, retrying in %ds" % wait)
                time.sleep(wait)
        else:
            return 1
    elif argv.commit:
        print("push it with: git push -u origin <branch>")
    else:
        print("\nnot committed. `git status` for what the update brought;"
              " add --commit --push to do it in one go.")
    return 0


def stamped(argv: argparse.Namespace) -> int:
    entries = record()
    print("wrote %s" % STATE.relative_to(refs.REPO))
    for item in tracked():
        entry = entries.get(item.id, {})
        if entry.get("basis") == "behind":
            print("  %-22s recorded as behind — the copy here predates the workshop's %s"
                  % (item.key, when(entry.get("time_updated"))))
        elif entry.get("basis") == "uncommitted":
            print("  %-22s copied in, not committed yet — that is what will be recorded"
                  % item.key)
    return 0


# ------------------------------------------------------------------ the playset

# What a playset copy keeps. These mods are here to be read and measured — what
# a `.gui` declares, what a `scripted_widget` keeps alive, how many filter chips
# land on a busy tag — and none of that is in a texture. A whole playset copied
# whole would be gigabytes of `.dds` nobody opens.
PLAYSET_KEEP = {
    ".txt", ".yml", ".yaml", ".gui", ".json", ".info", ".md",
    ".gfx", ".asset", ".shader", ".fxh", ".csv", ".lua", ".toml", ".cfg",
}
PLAYSET_SKIP_DIRS = {"gfx", "sound", "music", "soundtrack", "map_data", ".git", "__pycache__"}
# Localization in eleven languages is most of what a big mod weighs, and nine of
# them answer no question anybody here asks.
PLAYSET_LANGUAGES = {"english", "russian"}
LANGUAGE_PARENT = "localization"


def wanted_in_playset(path: Path, root: Path) -> bool:
    """Is this one of the files a playset copy is for?"""
    if path.suffix.lower() not in PLAYSET_KEEP:
        return False
    parts = path.relative_to(root).parts
    if PLAYSET_SKIP_DIRS.intersection(parts):
        return False
    for index, part in enumerate(parts[:-1]):
        if part == LANGUAGE_PARENT and index + 1 < len(parts) - 1:
            if parts[index + 1].lower() not in PLAYSET_LANGUAGES:
                return False
    return True


def copy_slim(source: Path, target: Path) -> tuple[int, int]:
    """Copy the readable half of a mod. Returns (files, bytes)."""
    if target.exists():
        shutil.rmtree(target)
    files = size = 0
    for path in sorted(source.rglob("*")):
        if not path.is_file() or not wanted_in_playset(path, source):
            continue
        destination = target / path.relative_to(source)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
        files += 1
        size += path.stat().st_size
    return files, size


def playset(argv: argparse.Namespace) -> int:
    """Copy everything else the owner is subscribed to, text only."""
    source_root = find_content(argv.source)
    known = {item.id for item in tracked()}
    refs.PLAYSET.mkdir(parents=True, exist_ok=True)

    print("from:   %s" % source_root)
    print("into:   %s" % refs.PLAYSET)
    print()

    seen: set[str] = set()
    total_files = total_size = 0
    for source in sorted(source_root.iterdir()):
        if not source.is_dir() or not source.name.isdigit():
            continue
        if source.name in known:
            continue     # these live in reference/mods/, whole
        item = Tracked(id=source.name, key=source.name, reason="")
        folder = folder_for(item, source, None)
        seen.add(folder)
        if argv.dry_run:
            print("  %-46s would be copied" % folder)
            continue
        files, size = copy_slim(source, refs.PLAYSET / folder)
        if not files:
            shutil.rmtree(refs.PLAYSET / folder, ignore_errors=True)
            seen.discard(folder)
            print("  %-46s nothing readable in it, skipped" % folder)
            continue
        mounts = sorted(p.name for p in (refs.PLAYSET / folder).iterdir()
                        if p.is_dir() and not p.name.startswith("."))
        total_files += files
        total_size += size
        print("  %-46s %4d files %9s   %s" % (folder, files, human(size), ", ".join(mounts)))

    if argv.dry_run:
        print("\n--dry-run: nothing written.")
        return 0

    # A mod that left the playset leaves the tree: this is a picture of what the
    # owner runs, and a copy nobody is subscribed to any more is a lie in it.
    for folder in sorted(refs.PLAYSET.iterdir()):
        if folder.is_dir() and folder.name not in seen:
            shutil.rmtree(folder, ignore_errors=True)
            print("  %-46s gone from the workshop folder, removed" % folder.name)

    print()
    print("%d mods, %s of text." % (len(seen), human(total_size)))
    refs.INVENTORY.write_text(refs.table(), encoding="utf-8")

    if argv.commit or argv.push:
        git("add", "--", "reference")
        if git("diff", "--cached", "--quiet", check=False).returncode:
            git("commit", "-m", argv.message or "reference: the rest of the playset, text only")
            print("committed.")
        else:
            print("nothing changed.")
    if argv.push:
        branch = argv.branch or git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        git("push", "-u", "origin", branch)
        print("pushed to %s" % branch)
    return 0


# --------------------------------------------------------------------- the shell


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="workshop.py",
        description=__doc__.strip().splitlines()[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Tracked mods live in tools/workshop_mods.txt.",
    )
    sub = parser.add_subparsers(dest="command")

    check = sub.add_parser("status", help="what the workshop has vs what is here")
    check.add_argument("--offline", action="store_true", help="do not ask Steam")
    check.add_argument("--quiet", action="store_true", help="say nothing when nothing moved")
    check.set_defaults(run=status)

    stamp = sub.add_parser("record", help="stamp the copies here as the current ones")
    stamp.set_defaults(run=stamped)

    bring = sub.add_parser("sync", help="copy the workshop copies in, rebuild, commit")
    bring.add_argument("--from", dest="source", metavar="DIR",
                       help="steamapps/workshop/content (or .../content/%s)" % APP_ID)
    bring.add_argument("--steamcmd", metavar="PATH",
                       help="fetch with steamcmd first, instead of relying on Steam having done it")
    bring.add_argument("--login", metavar="USER", help="the Steam account for --steamcmd")
    bring.add_argument("--only", nargs="+", metavar="MOD", help="ids or keys, instead of all of them")
    bring.add_argument("--keep-old", action="store_true",
                       help="do not delete a differently named folder of the same mod")
    bring.add_argument("--no-refresh", action="store_true", help="skip tools/refresh.py")
    bring.add_argument("--commit", action="store_true")
    bring.add_argument("--push", action="store_true")
    bring.add_argument("--branch", metavar="NAME", help="branch to push to; default is the current one")
    bring.add_argument("--message", metavar="TEXT", help="commit message")
    bring.add_argument("--dry-run", action="store_true")
    bring.set_defaults(run=sync)

    rest = sub.add_parser("playset", help="copy the rest of the subscribed mods in, text only")
    rest.add_argument("--from", dest="source", metavar="DIR",
                      help="steamapps/workshop/content (or .../content/%s)" % APP_ID)
    rest.add_argument("--commit", action="store_true")
    rest.add_argument("--push", action="store_true")
    rest.add_argument("--branch", metavar="NAME")
    rest.add_argument("--message", metavar="TEXT")
    rest.add_argument("--dry-run", action="store_true")
    rest.set_defaults(run=playset)

    known = argv[1:] or ["status"]
    if known[0] not in {"status", "record", "sync", "playset", "-h", "--help"}:
        known = ["status", *known]
    parsed = parser.parse_args(known)
    if not hasattr(parsed, "run"):
        parser.print_help()
        return 2
    return parsed.run(parsed) or 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
