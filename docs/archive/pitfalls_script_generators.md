# Pitfalls: script — генераторы, читающие файлы игры

Перенесено из `docs/pitfalls/script.md` 10-18 по бюджету; правила в силе.

## Чтение игровых файлов генератором

**Numeric-looking keys are not all goods.** `debug_max_profit = -1` on the
plantations was being counted as an input, turning four recipes' total input
weight negative. Match keys against the goods catalogue rather than against
"is it a number".

**A method with no `produced` outputs nothing.** A monastery burns clay for
upkeep, so it has no production efficiency for local clay to improve — which is
why the game gates its own shovel badge on `IsProducing`. Counting upkeep
methods put castles and monasteries in a list of things to build for their raw
materials.

## Нежадная скобка в начале строки — это не конец блока

**`^\tX = {(.*?)^\t}` ловит закрывающую скобку СЛЕДУЮЩЕГО блока**, если
искомый написан одной строкой. `nd_drr_jezail_tradition` пишет `potential = {
has_or_had_tag = DRR }` в строку, а ниже несёт `ai_weight = {` … `\n\t}` — и
разбор отдал в ворота всё содержимое продвижения целиком, вместе с `requires`,
`icon`, `unlock_unit` и `ai_weight`. Игра писала «Unknown trigger type:
ai_weight» шестнадцать раз за загрузку, ворота были мусором, и на экране это не
проявлялось ничем. **Однострочную форму пробуют первой**, и она обязана
требовать, чтобы скобки сошлись в той же строке (`[^{}\n]*`).
