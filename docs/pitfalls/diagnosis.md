# Pitfalls — finding a fault that logs nothing

Split out of [`../PITFALLS.md`](../PITFALLS.md), which stays the list of
mistakes; this is the method for the ones the engine does not report. Only the
player can run the game, so every entry here is about spending one run instead
of three.

## Diagnosing without a signal

**Two suspects and one round trip is a wasted round trip.** A monthly log line
that never appeared could have meant the pulse never fired, the setting read
errored, or CMF's log would not render what it was handed. Fixing all three
blind answered nothing: the next run still showed one number, and it was still
ambiguous. What works is a probe whose failure modes are *separable* — a counter
that only the pulse can increment, shown through a path already proven to work,
so the reading distinguishes "never ran" from "ran and could not be displayed".

**Check which build answered before believing what a run showed.** Twice a
report has been read as a fault in a mod whose files on disk were already right:
the folder the game loads,
`Documents/Paradox Interactive/Europa Universalis V/mod/<mod>/`, held an older
build, so the run reproduced the bug the fix had removed. Nothing says so — a
stale build is not an error, it is a different mod, and `error.log` is clean
because the old mod was valid. `gui.log` gives it away by accident: it prints the
file *and line* of every template that overrides another, and line numbers are a
fingerprint. `python3 tools/which_build.py <logs folder>` matches them against
this tree and every revision `git log` has, and names the commit that ran. Do
that first, before reading anything else into a run.

**Ask for the logs before theorising.** `error.log` being empty of your mod is
itself a finding: it rules out every failure the engine notices and leaves only
the silent classes — a missing localization key, an effect never called, a value
never read. Two of the four faults in `goods_target` were identified from the
logs plus `reference/` in one pass, without a further run.

## Instrument before the third theory

**2026-09-04, the plan editor.** Four sessions and eleven of his runs went on a
part of the mod the report could not see. Every press was invisible: «ничего не
изменилось» covered a button that never fired, a rule that refused, a placement
that silently failed and a walk that evicted and restored. Each session picked a
theory, built a fix, and spent a run on it.

**He ended it himself**: «Добавляй скан информации для себя в диагностике на
функцию редактора, чтобы ты видел чё там происходит.» Three lines went into the
report — what was asked, what the scan found, what the walk saw where it stood —
and **the very next press named the cause**, which no amount of reading the code
had:

    EDIT asked  presses=40 op=1 good=… reached=1 | outcome done=0 fail=1
    EDIT scan   fitn=42 cands=42 | walk hit=1 town=1 load=4 esg=9 esw=0
    EDIT walk   evicted=1 room=1 | placed_before=191 placed_after=192

Evicted, room found, placement refused, victim restored — `_edit_good` was a
country variable being read in a location's scope. **The rule: the second time a
part of the mod cannot be seen from the report, stop fixing and instrument it.**
Not the fourth.

**Three things make an instrumented press readable.** A counter that separates
«the button never fired» from «a rule refused». State reset when the window
opens, or a global from an hour ago reads as this press's result. And a `hit`
flag, because 0 and «no walk happened» must not look alike.

**A `debug_log` string cannot reach the item a walk stands on** — park the
location's numbers into globals inside the walk, and print those.

## Four theories, three fixes, and the cause still unknown

**The episode this whole instrument came out of**, and the rule it produced is in
the root `CLAUDE.md`: *a cause you cannot name is not a cause — do not guess it,
measure it.* Four of the owner's runs went on four theories about one symptom and
none on a measurement. The narrative, and what each theory cost, is in
[`../archive/diagnosis_four_theories.md`](../archive/where_to_produce/diagnosis_four_theories.md).

## «Диагностика»: одна кнопка, всё, текстом

Построена, прогнана, подтверждена. **Как её строили, чем читают и что она
ответила с первого нажатия** — [`../archive/diagnostics_built.md`](../archive/where_to_produce/diagnostics_built.md).
Правила, которые из этого остались, — ниже.

## What a `debug_log` string can and cannot reach

**Measured 2026-09-02, by a dump failing.** Three presses produced 632 `WTP`
lines in `debug.log` and 306 in `error.log`, every number in them zero. All four
of these shape the file that is built now.

- **`debug_log` writes on a normal build.** Construction Manager guards its own
  behind `debug_only`; that is their choice, not a requirement. `error_log`
  lands too, which is why the headline goes to both sinks and the detail to one.
- **A global is reachable**:
  `[GuiScope.SetRoot(GetPlayer.MakeScope).ScriptValue('<sv>')|0]` resolves inside
  a `debug_log` string exactly as it does in a localization.
- **The item a walk is standing on is not reachable at all.** `THIS.MakeScope`
  gives «Failed to convert statement for argument '0' for call 'SetRoot'», once
  per reader per row, and the bracket is echoed literally into the log. **Park a
  per-row number in a scratch global and print that**; `debug_log_scopes = no`
  logs the current scope, which is what names the row.
- **And a scope parks in a global just as a number does**, which is what lets a
  label say «+1 сукно → Мюнстер» instead of «сделано». `set_global_variable =
  { name = x value = scope:y }` after a `save_scope_as` inside the walk, then
  `[GetGlobalVariable('x').GetLocation.GetName]` in the localization —
  `GetGlobalVariable` is a global promote returning a `Scope`, so the same cast
  chain works on it that `mods/where_to_produce` already uses one scope down
  (`[Location.MakeScope.GetVariable('bag_wtp_r_good_1').GetGoods.GetName]`), and
  that CMF's own log uses for `cmf_log_loc`. **A number has no name**: an index
  in a global can only be turned into words by a `customizable_localization`
  with a branch per value, so park the scope where the name is wanted and the
  number where the report is. Built 2026-09-04, not yet seen in game.
- **And one script-value form reads zero in silence.** `value = 0` with
  `if = { limit = { has_global_variable = x } add = global_var:x }` returned 0
  for every reader, with nothing in any log — on a plan that had just placed 417
  buildings. **`value = global_var:x` is the form that prints real numbers**, and
  a guard belongs in the effect, where `if` demonstrably works.

## Разница — не журнал: хронологию держит только лог

**Его слова 2026-09-06:** «В окне изменений — всё смешивается. Там нет хронологии
изменений. Если были изменения в одной и той же локации — она смешивается с
прошлым изменением… Так что сам проверяй всё в диагностике.»

**Он описал устройство, а не поломку.** Окно изменений сравнивает нынешний план
с сохранённым, и разница по определению не помнит порядка: два нажатия по одной
локации — одна строка, а какое было первым, из неё не достать. Никакая правка
этого окна хронологии не вернёт; её там нет и быть не может.

**Ответ — писать строку в момент нажатия, а не собирать её потом.** `debug.log`
хронологичен по устройству: строки лежат в нём в том порядке, в каком их
написали, и помнить ничего не надо — ни кольцевого буфера, ни счётчика слотов, ни
диспетчера на 47 веток. `bag_wtp_edit_journal` печатает
`WTP PRESS n= op= good= hit= | done= fail= norefill= | esg= evicted=` на каждое
нажатие; имя локации пишет `debug_log_scopes`, вызванный **изнутри** её скоупа
(`global_var:bag_wtp_ev_loc = { debug_log_scopes = no }`), потому что строка
`debug_log` до скоупа не дотягивается.

**Товары в этой строке — номера, и это правильно.** Имена ей взять неоткуда без
диспетчера на каждое нажатие; отчёт называет их сам в строках `G<n>`, и
`tools/diag.py` складывает одно с другим.

**Имя локации -- строка над меткой, а не над нажатием.** Первая версия брала
строку прямо над `WTP PRESS`, и прогон 2026-09-06 подписал первое нажатие
строкой `Important assertion failed: <file>:0 (Getting player in synchronous
state, likely to cause a desync)`. **Это ругань движка на `GetPlayer` внутри
`debug_log`**, один раз за сессию, и приходит она ровно между именем и строкой,
потому что имя пишется до вычисления строки, а ругань -- во время. Отчёт ею не
испорчен: в одиночной игре десинхронизировать нечего, и весь отчёт печатается
через тот же `GetPlayer` с 2026-09-02. **Лечится меткой:** мод пишет
`WTP PRESSAT` сразу за именем, изнутри скоупа локации, и метка не читает ничего
-- встать между ними нечему.

**Читалке пришлось узнать, чей это журнал.** Нажатия ложатся в лог **до** кнопки,
которая пишет отчёт, — и «Показать изменения» тоже пишет свой кусок между `BEGIN`
и `END`. Первая версия отдавала нажатия тому куску, который случился раньше, так
что «Показать изменения» перед «Диагностикой» уносила хронологию с собой. Кусок
узнаётся по строке `EDIT asked`, которую пишет только диагностика.

## Почему сессия забывает то, что репозиторий знает

**Измерено 2026-09-05, после его прямого вопроса** — не из ощущений.

- **Архивирование ни при чём:** `docs/archive/*.md` стоит в `SOURCES` у
  `kb.py`, вынесенное находится поиском. Проверено.
- **А `in_game/gui/*.gui` не индексировалось ничем**, хотя пять рукописных окон
  несут 516 строк оплаченных комментариев. Правило про `§` лежало там с первой
  сборки: окно — 4 000 токенов, никто не читает его ради абзаца. **Теперь
  `code.py` индексирует сами комментарии.**
- **`CLAUDE.md` обещал `--map` за «~1 400 токенов»**, а это 4 000 у `kb.py` и
  13 000 у `code.py`. Исправлено.

**«Буду внимательнее» — не механизм, и он сказал это прямо:** «вряд ли это
решается простым ай-ай-ай… ты регулярно что-то делаешь на основании того, что не
работает, не существует, вне контекста воспринято». Решение то же, что у всего
здесь — **правило, которое может проверять инструмент, ему и принадлежит**:

- `api.py --says «текст»` — какой ключ держит надпись и что её рисует.
  «Пересчитать» → `bag_wtp_plan_refresh`, `bag_wtp_plan_window.gui`, один вызов.
- `api.py --where имя` — по файлам `reference/` и `mods/`, где дампы бессильны:
  типы виджетов, текстуры, текстиконы.
- **Каждый ответ кончается тем, чего он не искал.** В этом механизм:
  предупреждение стоит не в прочитанном и забытом документе, а в выводе — там,
  где иначе делается вывод «значит, этого нет».

**Но три отказа из четырёх были не про доступность.** Правило про `hbox` стояло
в файле, который я в тот момент правил; имя кнопки утверждалось по памяти;
«в игре нет такого символа» — вывод из одного поиска. **Инструмент чинит
недостижимое, но не непрочитанное** — остаток честнее назвать, чем спрятать.

**Состояние, которого не видно, — это не состояние игрока, а долг мода.**
`_lock<n>` ставится каждым «+1» и «−1», решает, кто участвует в дележе мест, и
съедает комнаты из общего котла — и ничего на экране о нём не говорило. Владелец,
2026-09-05, на прямой вопрос: «я вообще не ебу что за замки, как они работают,
могу ли я ими управлять». **Это не ответ «мне всё равно», а отчёт об отказе
интерфейса**, и его надо читать так. Тем же самым до этого оказался флаг «не
нужен»: «что есть галочка, что нет — это ничего не меняет на деле».

Правило, которое из двух случаев складывается: **у механизма, который меняет
результат, должны быть видимое состояние и способ его снять.** Иначе игрок
описывает симптомы вокруг него — «опустил товары, лимит не поднялся» — и обе
стороны ищут причину не там. И **флаг существования читается интерфейсом, а
число нет**: `GetGlobalVariable('x').IsSet` — форма самой игры, а «больше нуля»
в `visible` потребовало бы догадок про сигнатуры, так что переменная, которую
надо рисовать, ставится и удаляется, а не обнуляется.

**There is no clipboard.** The whole copy surface the engine exposes is
`LobbyView.CopyServerID` and `ChildItem.CopyDnaToClipboard`, neither taking a
string — checked against the game's own `data_types_gui.txt`. Text leaves the
game through the log, which is why `tools/diag.py` exists.

**The lesson under all of it is the one this file already carries**: the probe
found the fault in the probe. A dump that had only been reasoned about would have
been believed.

## Working blind

**Building a whole mod before loading it once is the expensive mistake, and it
has been made here.** `where_to_produce` was finished — four CMM lists, pickers,
scoring, tooltips — and then abandoned without ever running, leaving six
independent suspects and no way to tell which was in play, because an effect
that never runs logs nothing. One `cmf_log` on the first list, one round trip,
would have cut that to one. Only the player can run the game, so the size of an
untested increment is the whole risk: the smallest thing that produces a visible
signal beats the complete feature every time.

## Diagnosis

**`error.log` is the fastest tool here** and names the file and line. Every bug
found in this repo was found in it, usually in one pass. It also carries a
callstack for script errors, which is what points at the effect that swallowed
the rest of its body.

**An effect that never runs logs nothing at all.** That is the failure mode this
repo hits most. When the symptom is "nothing happened and the log is clean", do
not guess twice — put a `cmf_log` on the path in question and have the player
look at CMF's log panel.

**`game.log` carries load-time macro expansion errors** that `error.log` does
not.

**`reference/` is not the playset, and mistaking it for one produces a confident
wrong answer.** A session counted what every mod in `reference/` costs the
interface, found one mod far outside the range, and led with it. The owner's
reply was that he does not run that mod. `reference/` holds the five mods
somebody thought to upload; his `debug.log` of the same week mounts **22**, of
which 17 touch `in_game`. The mount table is right there in the log —
`virtualfilesystem_physfs.cpp: Mounted Data: .../workshop/content/3450310/<id>/<part>`,
one line per folder, in load order — and `python3 tools/playset.py <logs>` reads
it. Run that before any sentence beginning "the playset".

**A static widget count says nothing about a window built on `datamodel`.** The
same session reported `cm_hidden_window` as 23 widgets. It declares 23 and binds
a datamodel over every building type in the game, so what lives is that subtree
465 times over, with two more datamodels nested per row. Whenever a count is
about cost rather than about files, check what the window repeats over first —
`guicost.py --drivers` prints it.

**A budget subtracted from the pool and again from each share charges twice.**
2026-09-03. `where_to_produce`'s plan spends the ground in two phases: the town
charters go in first, then the goods fill what is left. `_plan_quota` is
`(rooms − what the charters spent) ÷ goods`, which is right — every good pays for
the charters once, together. But `_pn<n>`, the good's own counter that the
allocator reads against that share, is incremented by the very effect the charter
round calls to place a building, and nothing cleared it. So a good the charters
favoured arrived at the allocator already over its share and was frozen out of the
ground it is best at — `tools` at `_pn = 6` against a cap of **2**, unable to take
a free room paying it 799 out of 1000. **The symptom is a good that has exactly as
many buildings as some other phase gave it and none of its own**, and it looks
like a scoring fault, which is where three theories went first. When two phases
share a counter, say in one place which of them the budget is for.

**A safety net that fires on every report is a broken tool, not a careful one.**
2026-09-03. `tools/diag.py` folds the log and then checks that no `WTP` line was
lost, falling back to the raw log if any was. The rights line added that day is
rendered as «права: …» — **without the tag** — so every report with one counted 48
lines as lost, the net fired every time, and the owner got the raw log for days
without either of us noticing. Worse: the fallback then ran the summary over
**all five presses at once**, so «Права: выдано 263» was 48+48+48+71+48 across
five different runs, and any conclusion drawn from that header was nonsense. The
tell is that the tool's own warning line becomes routine — read the warning it
prints, and if it prints on every honest input, the check is the thing to fix.
