"""Напоминалка об откатах: таблица, ворота и тексты из файлов игры.

    python3 mods/rulers_toolkit/tools/gen_cooldowns.py

Читает `reference/game/in_game/common/{generic_actions,country_interactions}/*.txt`,
берёт действия с блоком `cooldown`, по строке списка CMF на тип отката, и пишет:
  in_game/common/scripted_effects/bag_rtk_cd_generated.txt   регистрация, проверка, клик
  in_game/common/scripted_triggers/bag_rtk_cd_gates_generated.txt   «можно ли тебе это»
  in_game/common/scripted_guis/bag_rtk_cd_generated_sgui.txt   `_on_changed` списков
  main_menu/localization/{russian,english}/bag_rtk_cd_l_*.yml

Ворота строки — копия условий самого действия: его `potential` и `visible`
выбора получателя (религия, ситуация, бедствие, организация), обёрнутые в то,
что это за получатель. Где их нет или они ссылаются на то, чего вне действия
нет (`scope:target`, `root`, `prev`), ворот нет — строка видна всегда.
"""
import glob, os, re, sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
MOD = os.path.join(ROOT, 'mods', 'rulers_toolkit')
GAME = os.path.join(ROOT, 'reference', 'game')
GEN = 'СГЕНЕРИРОВАНО mods/rulers_toolkit/tools/gen_cooldowns.py — руками не править.'

# Вкладки: id, ru, en.
TABS = [('faith', 'Религия', 'Faith'), ('realm', 'Держава', 'Realm'),
        ('orgs', 'Организации', 'Organizations'), ('crisis', 'Ситуации и бедствия', 'Situations and disasters')]
# Списки: id, вкладка, цвет алерта (палитра CMF), вкладка игры по клику (или None), ru, en.
LISTS = [
    ('cd_orders', 'faith', 'purple', 'country_religion', 'Религиозные ордена', 'Religious orders'),
    ('cd_christian', 'faith', 'purple', 'country_religion', 'Христианство', 'Christianity'),
    ('cd_islam', 'faith', 'purple', 'country_religion', 'Ислам', 'Islam'),
    ('cd_dharma', 'faith', 'purple', 'country_religion', 'Индуизм и буддизм', 'Hinduism and Buddhism'),
    ('cd_japan', 'faith', 'purple', 'country_religion', 'Япония', 'Japan'),
    ('cd_americas', 'faith', 'purple', 'country_religion', 'Америка', 'Americas'),
    ('cd_relother', 'faith', 'purple', 'country_religion', 'Прочее', 'Other'),
    ('cd_own', 'realm', 'blue', 'government', 'Своя держава и парламент', 'Own country and parliament'),
    ('cd_diplo', 'realm', 'green', 'diplomacy', 'Действия с другими державами', 'Actions with other countries'),
    ('cd_io', 'orgs', 'yellow', None, 'Международные организации', 'International organizations'),
    ('cd_sit1', 'crisis', 'orange', None, 'Ситуации (1)', 'Situations (1)'),
    ('cd_sit2', 'crisis', 'orange', None, 'Ситуации (2)', 'Situations (2)'),
    ('cd_dis', 'crisis', 'red', None, 'Бедствия', 'Disasters'),
]
RELIGION_FILE = {
    'religious_orders.txt': 'cd_orders',
    'catholic.txt': 'cd_christian', 'orthodox.txt': 'cd_christian', 'church_power.txt': 'cd_christian',
    'muslim.txt': 'cd_islam', 'ibadi.txt': 'cd_islam',
    'hindu_branches.txt': 'cd_dharma', 'sects.txt': 'cd_dharma',
    'religious_factions.txt': 'cd_japan',
    'mayan.txt': 'cd_americas', 'nahuatl.txt': 'cd_americas', 'yanantin.txt': 'cd_americas',
}
COLOR_RU = {'purple': 'фиолетовые', 'blue': 'синие', 'green': 'зелёные', 'yellow': 'жёлтые',
            'orange': 'оранжевые', 'red': 'красные'}
# Тип отката -> своё имя (ru, en), когда у действий общий откат.
FIX = {
    'elect_imam': ('Избрание имама', 'Elect an imam'),
    'prepare_for_katun': ('Подготовка к Катуну (любая)', 'Prepare for the Katun (any)'),
    'inti_ceremonial_festivals': ('Провести церемонию', 'Hold a ceremony'),
    # В игре имя собрано из данных (`[GetCountry('FRA')…]`) — своё.
    'demand_autonomy': ('Потребовать автономии от Франции', 'Demand autonomy from France'),
    'request_papal_delegates': ('Запросить папских делегатов', 'Request papal delegates'),
    'influence_french_subject': ('Повлиять на французского ленника', 'Influence a French subject'),
    'join_the_imperial_side_hw_action': ('Занять сторону императора', 'Join the imperial side'),
    'seek_relations_with_the_byzantines': ('Поиск связей с Византией', 'Seek relations with the Byzantines'),
    'invite_turkic_migration': ('Поддержать тюркскую миграцию', 'Invite Turkic migration'),
    'violate_treaty_of_tordesillas': ('Нарушить Тордесильясский договор', 'Violate the Treaty of Tordesillas'),
    'reform_imperial_armies': ('Реформа византийской армии', 'Reform the Byzantine armies'),
    'pw_push_for_serfdom': ('Продвигать крепостничество', 'Push for serfdom'),
    'pw_push_for_aristocracy': ('Продвигать аристократию', 'Push for aristocracy'),
    'rt_push_for_spiritualist': ('Продвигать духовность', 'Push for spiritualism'),
    'rt_push_for_humanist': ('Продвигать гуманизм', 'Push for humanism'),
    'grant_latin_merchants_privileges': ('Расширение привилегий итальянских купцов', 'Grant Italian merchants privileges'),
    'accept_catholic_delegation': ('Приём католической делегации', 'Accept a Catholic delegation'),
    'attract_italian_engineer': ('Привлечение итальянских инженеров', 'Attract an Italian engineer'),
    'demand_appanage_promotion': ('Потребовать повышение до апанажа', 'Demand promotion to appanage'),
    'pilgrimage_to_cholula': ('Паломничество в Чолольян', 'Pilgrimage to Cholula'),
    'become_shogun_from_imperial_court': ('Титул сёгуна', 'Become shogun'),
    'favor_buddhist_schools_from_religious_sects': ('Поддержка буддизма', 'Favor Buddhist schools'),
    'create_uc_bey': ('Создать удж-бея', 'Create an uc bey'),
    'break_the_yoke': ('Освобождение от татарского ига', 'Break free from the Tatar yoke'),
}
OUTSIDE = re.compile(r'scope:(?!actor\b)\w+|\broot\b|\bprev\b|\bROOT\b|\bPREV\b')


def loadloc(lang):
    loc = {}
    for f in glob.glob(os.path.join(GAME, 'main_menu', 'localization', lang, '**', '*.yml'), recursive=True):
        for line in open(f, encoding='utf-8-sig', errors='ignore'):
            m = re.match(r'\s+([\w.]+):\d*\s+"(.*)"\s*$', line)
            if m:
                loc.setdefault(m.group(1), m.group(2))
    return loc


def plain(text, loc, depth=0):
    """Имя игры без разметки: `$ключ$` раскрыт, `#…#!` и `[…]` сняты; None — не вышло."""
    if text is None or depth > 3:
        return None
    text = re.sub(r'\$(\w+)\$', lambda m: plain(loc.get(m.group(1)), loc, depth + 1) or '\0', text)
    text = re.sub(r'#TOOLTIP:[^ ]+ ', '', text)
    text = re.sub(r'#\w+ ', '', text).replace('#!', '')
    text = text.strip().rstrip('.')
    if '\0' in text or re.search(r'[\[\]$#]', text) or not text:
        return None
    return text


def block(body, key, indent):
    m = re.search(r'^' + indent + key + r' = \{(.*?)^' + indent + r'\}', body, re.M | re.S)
    return m.group(1) if m else None


def strip_comments(text):
    return re.sub(r'#[^\n]*', '', text)


def gate(body):
    """Условие «это действие тебе доступно» (scope: держава, scope:actor — она же) или None."""
    parts = []
    pot = block(body, 'potential', '\t')
    if pot is not None:
        pot = strip_comments(pot)
        if not OUTSIDE.search(pot):
            parts.append(pot)
    st = block(body, 'select_trigger', '\t')
    if st is not None:
        kind = re.search(r'looking_for_a = (\w+)', st).group(1)
        vis = block(st, 'visible', '\t\t')
        vis = strip_comments(vis) if vis is not None else None
        if vis and vis.strip() and not OUTSIDE.search(vis):
            if kind == 'religion':
                parts.append('scope:actor.religion ?= {%s}' % vis)
            elif kind == 'disaster':
                parts.append('any_active_disaster = {%s}' % vis)
            elif kind == 'international_organization':
                parts.append('any_international_organization = {%s}' % vis)
            elif kind == 'situation':
                sit = re.search(r'situation:(\w+)', vis)
                if sit:
                    parts.append('situation:%s ?= {%s}' % (sit.group(1), vis))
    if not parts:
        return None
    return 'AND = {\n' + '\n'.join('\t\t' + ' '.join(p.split()) for p in parts) + '\n\t}'


def actions():
    for kind in ('generic_actions', 'country_interactions'):
        for f in sorted(glob.glob(os.path.join(GAME, 'in_game', 'common', kind, '*.txt'))):
            text = open(f, encoding='utf-8-sig').read()
            for m in re.finditer(r'^([a-z_0-9]+) = \{(.*?)^\}', text, re.M | re.S):
                name, body = m.groups()
                cd = block(body, 'cooldown', '\t') or (re.search(r'^\tcooldown = \{([^}]*)\}', body, re.M) or [None, None])[1]
                if cd is None:
                    continue
                ty = re.search(r'type = (\w+)', cd)
                du = re.search(r'(years|months|days) = ([\d.]+)', cd)
                t = re.search(r'^\ttype = (\w+)', body, re.M)
                t = t.group(1) if t else 'diplomacy'
                yield os.path.basename(f), kind, t, name, ty.group(1) if ty else name, du, body


def list_of(fname, kind, t):
    if kind == 'country_interactions':
        return 'cd_diplo'
    return {'religious': RELIGION_FILE.get(fname, 'cd_relother'), 'religiousfaction': 'cd_japan',
            'owncountry': 'cd_own', 'parliament': 'cd_own', 'internationalorganization': 'cd_io',
            'situation': 'cd_sit', 'disaster': 'cd_dis'}.get(t)


def duration(du, ru):
    if not du:
        return ''
    n, unit = du.group(2), du.group(1)
    if ru:
        return {'years': f'{n} г.', 'months': f'{n} мес.', 'days': f'{n} дн.'}[unit]
    return f'{n} {unit}'


def main():
    ru, en = loadloc('russian'), loadloc('english')
    rows = {}  # type -> dict
    order = []
    missing = []
    for fname, kind, t, name, ty, du, body in actions():
        lst = list_of(fname, kind, t)
        if lst is None:
            continue
        g = gate(body)
        if ty not in rows:
            r, e = FIX.get(ty) or FIX.get(name) or (plain(ru.get(name), ru), plain(en.get(name), en))
            if not r or not e:
                missing.append(f'{ty} ({name}): ru={ru.get(name)!r} en={en.get(name)!r}')
            rows[ty] = {'list': lst, 'ru': r, 'en': e, 'gates': [], 'open': False, 'du': du}
            order.append(ty)
        row = rows[ty]
        if g is None:
            row['open'] = True
        else:
            row['gates'].append(g)
    if missing:
        sys.exit('имя не собрано — добавь в FIX:\n' + '\n'.join(missing))
    # Ситуации — два списка по 50.
    sit = [ty for ty in order if rows[ty]['list'] == 'cd_sit']
    for k, ty in enumerate(sit):
        rows[ty]['list'] = 'cd_sit1' if k < 50 else 'cd_sit2'
    table = {l[0]: [ty for ty in order if rows[ty]['list'] == l[0]] for l in LISTS}
    for lid, tys in table.items():
        if len(tys) > 50:
            sys.exit(f'{lid}: {len(tys)} строк, у списка CMF потолок 50')
    lists = [l for l in LISTS if table[l[0]]]

    # --- ворота
    trig = ['﻿# ' + GEN + '\n# Ворота строк напоминалки: копия условий действия. Scope: держава, scope:actor — она же.\n\n']
    for ty in order:
        row = rows[ty]
        if row['open'] or not row['gates']:
            body = '\talways = yes'
        else:
            body = '\tOR = {\n' + '\n'.join('\t' + g.replace('\n', '\n\t') for g in row['gates']) + '\n\t}'
        trig.append(f'bag_rtk_cd_gate_{ty} = {{\n{body}\n}}\n')
    open(os.path.join(MOD, 'in_game', 'common', 'scripted_triggers', 'bag_rtk_cd_gates_generated.txt'),
         'w', encoding='utf-8').write(''.join(trig))

    # --- эффекты
    out = ['﻿# ' + GEN + '\n\n# Регистрация списков. Scope: country.\nbag_rtk_cd_register_lists = {\n']
    for lid, tab, *_ in lists:
        out.append(f'\tcmm_register_global_settings_list = {{ mod_id = bag_rtk setting_id = {lid} tab_id = {tab} '
                   f'item_count = {len(table[lid])} is_ordered = 0 }}\n')
    for lid, *_ in lists:
        out.append(f'\tcmm_register_list_bool_field = {{ mod_id = bag_rtk setting_id = {lid} field_id = watch default_value = 0 }}\n')
    out.append('}\n\n# Показать или спрятать каждую строку по воротам. Scope: country.\nbag_rtk_cd_gate_all = {\n'
               '\tsave_scope_as = actor\n')
    for lid, *_ in lists:
        for i, ty in enumerate(table[lid], 1):
            out.append(f'\tbag_rtk_cd_gate_row = {{ sid = {lid} i = {i} type = {ty} }}\n')
    out.append('}\n\n# Каждая отмеченная строка, 1-го числа. Scope: country.\nbag_rtk_cd_check_all = {\n')
    for lid, tab, color, view, *_ in lists:
        for i, ty in enumerate(table[lid], 1):
            if view:
                out.append(f'\tbag_rtk_cd_check_row = {{ sid = {lid} i = {i} type = {ty} view = {view} }}\n')
            else:
                out.append(f'\tbag_rtk_cd_check_row_noview = {{ sid = {lid} i = {i} type = {ty} }}\n')
    out.append('}\n\n# Клик по напоминанию — убрать его. Scope: country.\nbag_rtk_cd_callback = {\n\tswitch = {\n'
               '\t\ttrigger = var:cmf_callback\n')
    for ty in order:
        out.append(f'\t\tflag:bag_rtk_rel_ready_{ty} = {{ cmf_remove_alert = {{ alert = bag_rtk_rel_ready_{ty} }} }}\n')
    out.append('\t}\n}\n')
    open(os.path.join(MOD, 'in_game', 'common', 'scripted_effects', 'bag_rtk_cd_generated.txt'),
         'w', encoding='utf-8').write(''.join(out))

    # --- _on_changed списков
    sg = ['﻿# ' + GEN + '\n# Без `_on_changed` CMF прячет список целиком; правка строки применяется здесь.\n\n']
    for lid, *_ in lists:
        sg.append(f'bag_rtk__{lid}_on_changed = {{\n\tscope = country\n\teffect = {{\n'
                  f'\t\tcmm_apply_list_change = {{ setting = bag_rtk__{lid} }}\n\t}}\n}}\n\n')
    open(os.path.join(MOD, 'in_game', 'common', 'scripted_guis', 'bag_rtk_cd_generated_sgui.txt'),
         'w', encoding='utf-8').write(''.join(sg))

    # --- локализация
    for lang, idx, head in (('russian', 'ru', 'l_russian'), ('english', 'en', 'l_english')):
        isru = lang == 'russian'
        L = [f'﻿{head}:\n', f' # {GEN}\n']
        for tid, tru, ten in TABS:
            L.append(f' bag_rtk__{tid}_name: "{tru if isru else ten}"\n')
        for lid, tab, color, view, lru, len_ in lists:
            title = lru if isru else len_
            if isru:
                desc = (f'Отметь действие — когда его откат закончится, 1-го числа на панели CMF появится '
                        f'напоминание ({COLOR_RU[color]}). Видны только действия, доступные твоей державе.')
            else:
                desc = (f'Tick an action and a CMF alert ({color}) appears on the 1st once its cooldown ends. '
                        f'Only actions your country can use are listed.')
            L.append(f' bag_rtk__{tab}__{lid}_name: "{title}"\n')
            L.append(f' bag_rtk__{tab}__{lid}_desc: "{desc}"\n')
            L.append(f' bag_rtk__{lid}_name: "{title}"\n')
            L.append(f' bag_rtk__{lid}_desc: "{desc}"\n')
            L.append(f' bag_rtk__{lid}_item_column_name: "{"Действие" if isru else "Action"}"\n')
            L.append(f' bag_rtk__{lid}__watch_name: "{"Напоминать" if isru else "Remind"}"\n')
            for i, ty in enumerate(table[lid], 1):
                n, d = rows[ty][idx], duration(rows[ty]['du'], isru)
                L.append(f' bag_rtk__{lid}_i{i}_name: "{n}"\n')
                L.append(f' bag_rtk__{lid}_i{i}_desc: "{("Откат " + d + ".") if isru else ("Cooldown " + d + ".")}"\n')
                L.append(f' bag_rtk_rel_ready_{ty}_color: "{color}"\n')
                L.append(f' bag_rtk_rel_ready_{ty}_icon: "@time!"\n')
                L.append(f' bag_rtk_rel_ready_{ty}_name: "{n} — {"доступно" if isru else "available"}"\n')
                tip = (f'Откат закончился: «{n}» можно сделать снова.' if isru
                       else f'The cooldown is over: «{n}» can be used again.')
                L.append(f' bag_rtk_rel_ready_{ty}_tooltip: "{tip}"\n')
        open(os.path.join(MOD, 'main_menu', 'localization', lang, f'bag_rtk_cd_l_{lang}.yml'),
             'w', encoding='utf-8').write(''.join(L))

    gated = sum(1 for ty in order if not rows[ty]['open'] and rows[ty]['gates'])
    print(len(order), 'cooldown types,', gated, 'gated,', len(order) - gated, 'always shown')
    print(', '.join(f'{l[0]} {len(table[l[0]])}' for l in lists))


main()
