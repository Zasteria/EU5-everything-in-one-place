# Conventions, and how the loop around the mods works

Read this when the task is about the repository itself — a generator, the
reference tree, an upload, the owner's menu. A task inside one mod does not need
it; [`../CLAUDE.md`](../CLAUDE.md) already carries the rules that fail silently.

## Files

- Script and localization files carry a **UTF-8 BOM**.
- Localization: one leading space per key under the `l_<language>:` header, and
  every language folder a mod ships stays in step with the others. **The player
  plays in Russian**, so a key missing there shows as the raw key on screen.
  `glorpui_hints` ships all eleven languages the game has; the rest ship Russian.
- **A word the game already has a name for is not translated by hand.**
  `[religious_aspect|e]` resolves `game_concept_religious_aspect` in the player's
  language for free, and is right where a synonym would be wrong.
  `python3 mods/nd_ru/tools/term.py <word>` says what the game calls it.
- Anything named `*_generated_*` is written by a tool and must not be hand
  edited.
- Prefer adding to `gui/filters/` or to CMF's action bar over copying a vanilla
  `.gui`. When a copy is unavoidable, copy the **window**, not the file's `types`
  block — other mods restyle those types, and carrying vanilla's copies clobbers
  them.

## The reference tree

`reference/` holds 253 MB of EU5's own files and the mods worth imitating.
**Grep it instead of asking for uploads or guessing.**

    reference/game/in_game/gui/              panels, widget types, gui/filters
    reference/game/in_game/common/           building_types, production_methods, goods,
                                             scripted_effects, scripted_triggers, on_action
    reference/game/main_menu/localization/   what the game calls its own concepts
    reference/game/docs/                     the engine's own API dump — ask it with tools/api.py
    reference/mods/                          CMF, Construction Manager, Glorp UI, the two
                                             mods being translated
    reference/playset/                       the owner's other subscribed mods, text only

**Do not hardcode a mod's folder name, and do not trust a version written in
prose.** These are refreshed whenever a mod updates, and the folder name arrives
however the upload produced it — `community_mod_framework` one time,
`3692202776_community_mod_framework` the next. Ask the tree instead:

    python3 tools/refs.py                    what is there, with versions
    python3 tools/refs.py --path cmf         where it is right now

In a tool, `import refs` and call `refs.known("cmf")`, which resolves a mod by
the `id` inside its `metadata.json`.

`reference/playset/` is copied text only and nothing builds against it —
`refs.mods()` does not see it and no generator reads it, and a mod there can
vanish at the next sync. It is for questions that need the whole load order:
`tools/guicost.py` counts it, and it is where a mod nobody has looked at goes.

What is deliberately absent: `gfx`, `events`, `decisions`, map data, and most of
`common/`. Ask for those if a task needs them, and add them here afterwards.

## Rebuilding after a refresh

    python3 tools/refresh.py           rebuild everything, report what moved
    python3 tools/refresh.py --check   report and revert, when you only want to know

Run it at the start of a session too: it is cheaper than believing a document.
Nothing anywhere records a version by hand.

## The tools

Every generator and checker lives in `mods/*/tools/` and is committed. **Nothing
about them is carried in a session's head.** When a session learns a rule the
hard way, the cheapest place to put it is inside the checker that would have
caught it, not only in prose.

| | |
| --- | --- |
| `refs.py` | where the reference tree is, resolved by mod id rather than folder name |
| `refresh.py` | the one command to run after `reference/` is refreshed |
| `api.py` | what the engine actually has: effects, triggers, on_actions, GUI functions |
| `kb.py` | this repository's own documents, asked rather than read |
| `extract_game_files.py` | copy the game directories a task needs out of an EU5 install into `reference/game/`; the `.ps1` twin is for the Windows box that has the game. Both read `game_files_manifest.txt` |
| `mods.py` | **the owner's own tool, and the one he runs.** A menu over the whole mod loop. `mods.bat` is what he double-clicks |
| `workshop.py` | the same work without the menu, and the daily check on GitHub |
| `check_cmm.py` | every CMM call in a mod against CMF's declared arguments, and every localization key CMM will look for |
| `check_docs.py` | the documents still describe files that exist, and stay inside their size budget |
| `check_script.py` | every way a mod file or a window has died quietly here: an effect's `if` inside a trigger, a doubled byte order mark, a name nothing defines, a script value defined twice, a window missing from `scripted_widgets/`, a window without its frame line, a row wider than the window holding it. Each check carries the run it cost in its docstring. Runs from `refresh.py` |
| `guicost.py` | what the interface costs before anybody clicks |
| `playset.py` | which mods the player actually runs, from the mount table in his `debug.log` |
| `which_build.py` | which *build* of them ran, fingerprinted from the template line numbers in his `gui.log` |
| `publish.py` | whether a mod is fit to upload |

**Editing a generator is not editing its output.** `generate.py` writes game
files out of f-strings, and those f-strings carry literal `\t` and doubled
braces. A replacement built in a shell heredoc has to escape both — `\\t`, and
`{{` where the string is *substituted into* an outer f-string rather than
processed by one. Three edits running on 2026-09-06 put `{{ }}` into the
generated file, and one put `{MOD_ID}` there verbatim because the key was built
with `%` on a plain string instead of an f-string. **Read the generated file
after the edit, not the generator.**

`.claude/hooks/session-start.sh` runs the first checkers at the start of every
session, so a session begins knowing the state of the tree rather than what a
document last remembered.

## Where things come from, and who runs what

Everything a session needs is in `reference/` — the game's `gui` and the parts
of `common` that matter, plus Community Mod Framework, Construction Manager,
Glorp UI and the two mods being translated. Grep it rather than asking for
uploads, and run `python3 tools/refs.py` rather than believing a version written
in prose.

The one thing that still has to come from the player is `logs/` after a test
run, because only they can run the game. After any refresh of `reference/`:

```
python3 tools/refresh.py
```

**Whether a refresh is owed** is answered without asking him: `python3
tools/workshop.py` compares the tracked workshop items against what the last
sync wrote down, needs nothing but the network, and runs daily on GitHub as
well. The workshop itself will never hand the files to GitHub: an anonymous
steamcmd download of an item for this game is refused, so the files only move
from a machine that owns it.

**The menu has been run end to end, on 2026-08-25, and it works.** Advanced Auto
Build 0.9.3 was found, fetched with steamcmd under his account, copied into
`steamapps/workshop/content/3450310/` — the folder the game reads mods from —
and then into `reference/`, rebuilt, committed and pushed, all from the menu.
The playset came in the same evening: **17 mods, 18 MB of text**, which is the
first time anything here could see more than five of the twenty-two.

**He brings them over from a menu — `mods.bat` in the repository root.** Rebuilt
2026-10-03 to his list, four items, and **it never rebuilds or checks anything**:
«любые обновления идут через тебя, и я не хочу сталкиваться с генераторами
лично — совсем». After he pushes a reference update, `tools/refresh.py`, the
generators and the checkers are the session's to run.

1. **Мастерская.** His whole subscription out of Steam's own
   `appworkshop_3450310.acf`, compared by build id; the ones he picks are
   fetched with steamcmd into the game's workshop folder, and their copies here
   follow at once — `reference/mods/` whole, `reference/playset/` text only.
2. **Все моды.** One list: ours in `mods/`, everything from the workshop,
   anything else in `Documents/.../mod/`. Per mod: download, put in reference
   or playset (rewrites `tools/workshop_mods.txt`), install into the game,
   remove from the game, remove from the repository — the copy, its manifest
   line, its build notes in `mods.local.json` and its entry in
   `workshop_generated_state.json`, so no «нет подписки» row outlives it.
3. **Всё сразу.** Update every copy; drop everything he is no longer subscribed
   to; reinstall our mods whose game copy differs.
4. **Забрать из игры** — logs, game files, API dumps — because a session sees
   the repository and nothing else:
   - **логи** — `error.log`, `gui.log`, `warning.log`,
     `database_conflicts.log`, `system.log` and the last 4 MB of `debug.log` in
     one gitignored zip in the repository root, for him to attach (111 KB
     against 12 MB for the folder on 2026-09-03);
   - **файлы игры** — `extract_game_files.py --prune` over
     `tools/game_files_manifest.txt` into `reference/game/`, with every game
     file a workshop mod replaces whole; `in_game/gui` was missing until
     2026-09-03, and two rounds went on guessing at `gui/scripted_widgets/`;
   - **дампы API** — copied only if taken after the last Steam update.

**Only the game's half of a mod folder goes.** `.metadata/` and the mount
directories (`in_game`, `main_menu`, `loading_screen`, …); never `tools/`,
`translations/`, `fixes/` or the READMEs, which are this repository's business.
A top-level directory that is in neither list is **reported and not copied** —
so a mount nobody has heard of cannot be dropped in silence, and a new source
folder cannot end up inside a live mod.

That shape is deliberate and was asked for in those words: **nothing about
updating his mods may require a session of ours.** `workshop.py` is the
machinery under the menu.

**The first real sync ran on 2026-08-25**, and brought both mods this repository
translates up to date in one command. It also showed what the loop is worth:
Advanced Auto Build had gained 28 keys and quietly rewritten two, and National
Destinies had added a formable to a sentence. All of it is translated now, and
both generators are clean.

**A sync from a box without Python rebuilds nothing.** That is what the first
run did: the reference copies were committed and pushed, `refresh.py` never ran,
and so nothing said the translations had drifted. The update check survives it —
`workshop.py status` works out from git that a folder committed after the
workshop's last update cannot be behind, so it does not need `record` to have
run — but the generators do not run themselves. After a sync, make sure someone
ran `python3 tools/refresh.py` and read its report.

## Два мода, которых в `reference/` не хватает — его предложение, 2026-09-05

Он предложил положить в дерево ещё два и спросил, нужно ли. **Нужно, и вот
зачем — иначе это просто чужие файлы.**

**Пришли 2026-09-05 как `sakuya` 1.6.0 и `sakuya_afterburner` 1.6.0** — чит-меню
и его зависимость, 199 и 16 файлов, 22 скриптовых файла в `common/`.
`fixedgridbox` у них нет, так что за живой сеткой по datamodel идти всё равно в
игру. Ценность — в другом, ниже.

**Чит-меню — потому что дампы говорят, что существует, и молчат о том, как
этим пользуются.** Мод, который влияет почти на все аспекты игры, — это каталог
эффектов, **применённых и работающих**: `api.py` показывает сигнатуру
`set_subsidized`, но не показывает, в каком скоупе её зовут и что рядом с ней
приходится ставить, чтобы она сработала. Ровно этот разрыв стоил здесь редизайна
(«subsidies were written off as GUI-only»). И у него большой интерфейс — то
есть живые примеры `fixedgridbox` с datamodel, а это прямо то, что нужно
[шагу 2б](archive/where_to_produce/wtp_practice_plan.md).

**`Advanced Auto Build` из дерева убран, 2026-09-12** — его слово: «он говнище
и больше не пригодится, всё самое нужное из него давно было взято». Что из него
успели измерить, осталось в `docs/research/interface.md` и
`investigations/panel_hitch.md`; самих файлов нет.

**И его надо закоммитить.** `reference/` лежит в git — 9 325 файлов, — но
последний коммит по нему старый, так что мод, положенный в дерево локально, до
сессии не доезжает вовсе. 2026-09-05 чит-меню было добавлено и его в дереве не
оказалось. **Положить в `reference/` — это `git add` и `git push`, иначе для
сессии этого мода не существует.**

**Чего это не отменяет.** Дерево остаётся неполным: в нём нет ни `.dds`, ни
шрифтов, ни половины типов виджетов игры — **«не нашёл здесь» и «не существует»
разные утверждения**, и `api.py` печатает это под каждым ответом. Два лишних
мода делают дерево полнее, а не полным.
