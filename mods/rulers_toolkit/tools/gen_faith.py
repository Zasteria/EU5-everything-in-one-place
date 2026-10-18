"""Напоминалка о религиозных действиях: таблица из файлов игры.

    python3 mods/rulers_toolkit/tools/gen_faith.py

Читает `reference/game/in_game/common/generic_actions/*.txt`, берёт действия
`type = religious | religiousfaction` с блоком `cooldown`, по одной галочке на
тип отката, и пишет:
  in_game/common/scripted_effects/bag_rtk_faith_generated.txt
  main_menu/localization/{russian,english}/bag_rtk_faith_l_*.yml
Имена — из локализации игры; где в ней разметка или `$ключ$`, имя своё (FIX).
"""
import glob, os, re, sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
MOD = os.path.join(ROOT, 'mods', 'rulers_toolkit')
GAME = os.path.join(ROOT, 'reference', 'game')

# Файл игры -> группа на вкладке.
GROUP = {
    'religious_orders.txt': 'orders',
    'catholic.txt': 'christian', 'orthodox.txt': 'christian', 'church_power.txt': 'christian',
    'muslim.txt': 'islam', 'ibadi.txt': 'islam',
    'hindu_branches.txt': 'dharma', 'sects.txt': 'dharma',
    'religious_factions.txt': 'japan',
    'mayan.txt': 'americas', 'nahuatl.txt': 'americas', 'yanantin.txt': 'americas',
}
GROUPS = [  # порядок групп на вкладке и их имена
    ('orders', 'Религиозные ордена', 'Religious orders'),
    ('christian', 'Христианство', 'Christianity'),
    ('islam', 'Ислам', 'Islam'),
    ('dharma', 'Индуизм и буддизм', 'Hinduism and Buddhism'),
    ('japan', 'Япония', 'Japan'),
    ('americas', 'Америка', 'Americas'),
    ('other', 'Прочее', 'Other'),
]
# Тип отката -> своё имя (ru, en): общий для нескольких действий или с разметкой в игре.
FIX = {
    'elect_imam': ('Избрание имама', 'Elect an imam'),
    'prepare_for_katun': ('Подготовка к Катуну (любая)', 'Prepare for the Katun (any)'),
    'inti_ceremonial_festivals': ('Провести церемонию', 'Hold a ceremony'),
    'mobilize_the_shurat_action': ('Мобилизация аш-Шурат', 'Mobilize the Shurat'),
    'call_jihad': ('Объявление джихада', 'Call jihad'),
    'pilgrimage_to_cholula': ('Паломничество в Чолольян', 'Pilgrimage to Cholula'),
    'become_shogun_from_imperial_court': ('Титул сёгуна', 'Become shogun'),
    'increase_tax_income_from_shogun_court': ('Повышение налогов', 'Increase tax income'),
    'crackdown_their_strongholds': ('Уничтожение оплотов Икко-икки', 'Crack down on Ikko-ikki strongholds'),
    'increase_literacy_from_religious_sects': ('Распространение грамотности', 'Increase literacy'),
    'favor_buddhist_schools_from_religious_sects': ('Поддержка буддизма', 'Favor Buddhist schools'),
    'recently_requested_cardinal': ('Просьба о кафедре кардинала', 'Request a cardinal seat'),
}


def loadloc(lang):
    loc = {}
    for f in glob.glob(os.path.join(GAME, 'main_menu', 'localization', lang, '**', '*.yml'), recursive=True):
        for line in open(f, encoding='utf-8-sig', errors='ignore'):
            m = re.match(r'\s+([\w.]+):\d*\s+"(.*)"\s*$', line)
            if m:
                loc.setdefault(m.group(1), m.group(2))
    return loc


def actions():
    rows = []
    for f in sorted(glob.glob(os.path.join(GAME, 'in_game', 'common', 'generic_actions', '*.txt'))):
        text = open(f, encoding='utf-8-sig').read()
        for m in re.finditer(r'^([a-z_0-9]+) = \{(.*?)^\}', text, re.M | re.S):
            name, body = m.groups()
            t = re.search(r'^\ttype = (\w+)', body, re.M)
            if not t or t.group(1) not in ('religious', 'religiousfaction'):
                continue
            cd = re.search(r'^\tcooldown = \{(.*?)^\t\}', body, re.M | re.S) or \
                re.search(r'^\tcooldown = \{([^}]*)\}', body, re.M)
            if not cd:
                continue
            ty = re.search(r'type = (\w+)', cd.group(1))
            rows.append((os.path.basename(f), name, ty.group(1) if ty else name))
    return rows


def main():
    ru, en = loadloc('russian'), loadloc('english')
    seen, table = set(), {g[0]: [] for g in GROUPS}
    for fname, name, ty in actions():
        if ty in seen:
            continue
        seen.add(ty)
        r, e = FIX.get(ty, (ru.get(name), en.get(name)))
        if not r or not e or re.search(r'[\[\]$#]', r + e):
            sys.exit(f'{ty}: имя с разметкой или без перевода — добавь в FIX')
        table[GROUP.get(fname, 'other')].append((ty, r, e))

    out = ['﻿# СГЕНЕРИРОВАНО mods/rulers_toolkit/tools/gen_faith.py — руками не править.\n'
           '# Напоминалка о религиозных действиях: по галочке на тип отката.\n\n'
           '# Регистрация галочек. Scope: country.\n'
           'bag_rtk_faith_register = {\n']
    for g, _, _ in GROUPS:
        for ty, _, _ in table[g]:
            out.append(f'\tcmm_register_bool_setting = {{ mod_id = bag_rtk setting_id = rel_{ty} '
                       f'tab_id = faith group_id = {g} default_value = 0 }}\n')
    out.append('}\n\n# Каждая отмеченная. Scope: country.\nbag_rtk_faith_check_all = {\n')
    for g, _, _ in GROUPS:
        for ty, _, _ in table[g]:
            out.append(f'\tbag_rtk_faith_check_one = {{ type = {ty} }}\n')
    out.append('}\n\n# Клик по напоминанию — убрать его. Scope: country, внутри switch на var:cmf_callback.\n'
               'bag_rtk_faith_callback = {\n\tswitch = {\n\t\ttrigger = var:cmf_callback\n')
    for g, _, _ in GROUPS:
        for ty, _, _ in table[g]:
            out.append(f'\t\tflag:bag_rtk_rel_ready_{ty} = {{ cmf_remove_alert = {{ alert = bag_rtk_rel_ready_{ty} }} }}\n')
    out.append('\t}\n}\n')
    open(os.path.join(MOD, 'in_game', 'common', 'scripted_effects', 'bag_rtk_faith_generated.txt'),
         'w', encoding='utf-8').write(''.join(out))

    for lang, idx, head, tab, ready, tip, sname, sdesc in (
        ('russian', 1, 'l_russian', 'Религия', 'доступно', 'Откат закончился: действие «{n}» можно сделать снова.',
         '{n}', 'Напоминать, когда у действия «{n}» закончится откат.'),
        ('english', 2, 'l_english', 'Faith', 'available', 'The cooldown is over: «{n}» can be used again.',
         '{n}', 'Remind me when «{n}» comes off cooldown.')):
        lines = [f'﻿{head}:\n', ' # СГЕНЕРИРОВАНО mods/rulers_toolkit/tools/gen_faith.py — руками не править.\n',
                 f' bag_rtk__faith_name: "{tab}"\n']
        for g in GROUPS:
            lines.append(f' bag_rtk__faith__{g[0]}_name: "{g[idx]}"\n')
        for g, _, _ in GROUPS:
            for row in table[g]:
                ty, n = row[0], row[idx]
                lines.append(f' bag_rtk__rel_{ty}_name: "{sname.format(n=n)}"\n')
                lines.append(f' bag_rtk__rel_{ty}_desc: "{sdesc.format(n=n)}"\n')
                lines.append(f' bag_rtk_rel_ready_{ty}_color: "green"\n')
                lines.append(f' bag_rtk_rel_ready_{ty}_icon: "@time!"\n')
                lines.append(f' bag_rtk_rel_ready_{ty}_name: "{n} — {ready}"\n')
                lines.append(f' bag_rtk_rel_ready_{ty}_tooltip: "{tip.format(n=n)}"\n')
        open(os.path.join(MOD, 'main_menu', 'localization', lang, f'bag_rtk_faith_l_{lang}.yml'),
             'w', encoding='utf-8').write(''.join(lines))
    print(sum(len(v) for v in table.values()), 'cooldown types:',
          ', '.join(f'{g} {len(table[g])}' for g, _, _ in GROUPS))


main()
