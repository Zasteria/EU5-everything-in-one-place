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
import glob, json, os, re, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', 'tools'))
import quiet_logs  # noqa: E402  строки журнала — под галочкой «Журнал»


def _tag_safe(m):
    """`this = c:ENG` errors when England is gone (1773, 10-20). `this ?=` is the
    game's own form; any other trigger takes no `?=` (the 1.4.2 load check:
    «Trigger is simple assign»), so it waits on `exists` instead. Field names
    (`target =`, `region =`) and `country_exists` stay as they are."""
    trig, tag = m.group(1), m.group(2)
    if trig == 'this':
        return f'this ?= {tag}'
    if trig in ('country_exists', 'target', 'region', 'actor', 'recipient', 'name', 'value'):
        return m.group(0)
    return f'AND = {{ exists = {tag} {trig} = {tag} }}'

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
MOD = os.path.join(ROOT, 'mods', 'rulers_toolkit')
GAME = os.path.join(ROOT, 'reference', 'game')
GEN = 'СГЕНЕРИРОВАНО mods/rulers_toolkit/tools/gen_cooldowns.py — руками не править.'

# Вкладка-родитель и её подвкладки (`cmm_register_subtab`): id, ru, en.
PARENT = ('cooldowns', 'Перезарядки', 'Cooldowns')
TABS = [('cd_faith', 'Религия', 'Faith'), ('cd_realm', 'Держава', 'Realm'),
        ('cd_orgs', 'Организации', 'Organizations'), ('cd_crisis', 'Ситуации и бедствия', 'Situations and disasters')]
# Списки: id, вкладка, цвет алерта (палитра CMF), вкладка игры по клику (или None), ru, en.
# Религия — один список, но в CMF потолок 50 строк: второй держит то, что бывает
# только у своих вер (Индия, Япония, Америка), так что держава видит один.
# Список без видимых строк прячется целиком, с заголовком.
LISTS = [
    ('cd_rel1', 'cd_faith', 'purple', 'country_religion', 'Религиозные действия', 'Religious actions'),
    ('cd_rel2', 'cd_faith', 'purple', 'country_religion', 'Религиозные действия', 'Religious actions'),
    ('cd_estate', 'cd_realm', 'blue', 'government', 'Сословные действия', 'Estate actions'),
    ('cd_state', 'cd_realm', 'blue', 'government', 'Своя держава', 'Own country'),
    ('cd_foreign', 'cd_realm', 'green', 'diplomacy', 'Действия с другими державами', 'Actions with other countries'),
    ('cd_io', 'cd_orgs', 'yellow', None, 'Международные организации', 'International organizations'),
    ('cd_hre', 'cd_orgs', 'yellow', None, 'Священная Римская империя', 'Holy Roman Empire'),
    ('cd_sit1', 'cd_crisis', 'orange', None, 'Ситуации', 'Situations'),
    ('cd_sit2', 'cd_crisis', 'orange', None, 'Ситуации', 'Situations'),
    ('cd_dis', 'cd_crisis', 'red', None, 'Бедствия', 'Disasters'),
]
# Строки списка не переставлять и не убирать: галочка CMF хранится по номеру
# строки. Генератор сверяет с `cd_lists.json` и останавливается, если старые
# строки списка — не начало новых: тогда списку новое имя (так `cd_own` стал
# `cd_country`, а 0.6.4 — `cd_state`).
MANIFEST = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cd_lists.json')
# Всё про Империю и императора — во вкладке организаций (его слова 10-19).
HRE_FILES = {'hre.txt', 'imperial_circles.txt', 'hre_circle_actions.txt'}
# Религиозный файл игры -> список; чего нет — `cd_rel1`.
RELIGION_FILE = {
    'hindu_branches.txt': 'cd_rel2', 'sects.txt': 'cd_rel2', 'religious_factions.txt': 'cd_rel2',
    'mayan.txt': 'cd_rel2', 'nahuatl.txt': 'cd_rel2', 'yanantin.txt': 'cd_rel2',
}
# Сословные действия: откат у каждого сословия свой (его слова 10-19), кроме
# созыва парламента, — строка на пару «действие, сословие». Действие -> сословия.
ESTATES = ['nobles', 'clergy', 'burghers', 'peasants', 'dhimmi', 'tribes', 'cossacks']
ESTATE_ACTIONS = {
    'ask_for_extra_levies': ESTATES, 'extraordinary_taxes': ESTATES,
    'ask_clergy_for_legitimacy': ['clergy'], 'ask_nobility_for_diplomats': ['nobles'],
    'ask_burghers_for_loan': ['burghers'], 'ask_commoners_for_stability': ['peasants', 'dhimmi'],
    'ask_tribes_for_manpower': ['tribes', 'cossacks'], 'press_estate_private_regiments_action': ESTATES,
}
ESTATE_FILE = 'estate_emergency_actions.txt'
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
    # Один откат у голосования в парламенте организации и у предложений округа.
    'vote_in_organization_parliament': ('Голосование в парламенте организации или округа', 'Vote in an organization or circle parliament'),
}
# `prev` в условиях игры — всегда внутри своего блока, и копия сохраняет его смысл.
# В `visible` выбора получателя `root` и `scope:<target_flag>` — сам кандидат
# (`is_member_of_international_organization = root` у лиги): копия запоминает его.
CAND = 'scope:bag_rtk_cd_cand'


def outside(text):
    """Ссылается ли условие на то, чего вне действия нет; то, что оно само запомнило
    (`save_temporary_scope_as = actor_culture` у поселенцев), — своё."""
    own = set(re.findall(r'save_temporary_scope_as = (\w+)', text))
    return any(m.group(1) not in own if m.group(1) else True
               for m in re.finditer(r'scope:(?!actor\b|bag_rtk_cd_cand\b)(\w+)|\broot\b|\bROOT\b', text))


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
    """Тело `key = { … }`, начатого с отступом `indent`, по парным скобкам (0.6.0 брал
    до первой `}` с тем же отступом и при однострочном блоке захватывал соседний
    `allow` — «Unknown trigger type: allow» в его логе 10-19)."""
    m = re.search(r'^' + indent + key + r' = \{', body, re.M)
    if not m:
        return None
    depth, i = 1, m.end()
    while depth and i < len(body):
        depth += {'{': 1, '}': -1}.get(body[i], 0)
        i += 1
    return body[m.end():i - 1]


def strip_comments(text):
    return re.sub(r'#[^\n]*', '', text)


def gate(body):
    """Условие «это действие тебе доступно» (scope: держава, scope:actor — она же) или None."""
    parts = []
    pot = block(body, 'potential', '\t')
    st = block(body, 'select_trigger', '\t')
    if pot is not None and st is not None and 'looking_for_a = religion' in st:
        # Эллинские действия: `scope:recipient ?= religion:…` — выбранная вера, она же своя.
        flag = re.search(r'target_flag = (\w+)', st)
        if flag:
            pot = pot.replace('scope:' + flag.group(1), 'scope:actor.religion')
    if pot is not None:
        # `is_member_of_circle = scope:target` и такие же: без выбранного получателя
        # условие снимаем — ворота шире, но не врут (круги Империи, 0.6.1).
        pot = re.sub(r'\b\w+ \??= scope:(?!actor\b)\w+', '', pot)
        if pot.strip() and not outside(pot):
            parts.append(pot)
    if st is not None:
        kind = re.search(r'looking_for_a = (\w+)', st).group(1)
        vis = block(st, 'visible', '\t\t')
        if vis and vis.strip():
            flag = re.search(r'target_flag = (\w+)', st)
            vis = re.sub(r'\b(root|ROOT)\b', CAND, vis)
            if flag:
                vis = vis.replace('scope:' + flag.group(1), CAND)
            vis = 'save_temporary_scope_as = bag_rtk_cd_cand ' + vis
        if vis and vis.strip() and not outside(vis):
            if kind == 'religion':
                parts.append('scope:actor.religion ?= {%s}' % vis)
            elif kind == 'disaster':
                parts.append('any_active_disaster = {%s}' % vis)
            elif kind == 'international_organization':
                parts.append('any_international_organization = {%s %s}' % (IO_MEMBER, vis))
            elif kind == 'country':
                # Есть ли сейчас хоть один получатель: округа Империи без округов — нет.
                parts.append('any_country = {%s}' % vis)
            elif kind == 'situation':
                sit = re.search(r'situation:(\w+)', vis)
                if sit:
                    parts.append('situation:%s ?= {%s}' % (sit.group(1), vis))
    if st is not None and 'looking_for_a = international_organization' in st and 'source = actor' in st \
            and not any(p.startswith('any_international_organization') for p in parts):
        # Без своих условий — хотя бы своя организация («Перехват лидерства в лиге»).
        parts.append('any_international_organization = { %s }' % IO_MEMBER)
    if not parts:
        return None
    return 'AND = {\n' + '\n'.join('\t\t' + ' '.join(p.split()) for p in parts) + '\n\t}'


# Кому-то из действий нужно больше, чем «доступно вообще»: орден, которому можно
# дать владение (его скрин 10-20: напоминание пришло, а дать некому).
READY_EXTRA = {
    'invite_religious_order': 'scope:actor.religion = { any_religious_order_in_religion = '
                              '{ order_type = { religious_order_type_foundable_by = scope:actor } } }',
}


def ready(body, name):
    """«Сделать можно сейчас» (scope: держава, scope:actor — она же): ворота и `allow`
    самого действия. Напоминание ждёт его, а не только конца отката: западный раскол
    кончился, а напоминания шли (10-20). None — проверять нечего."""
    parts = []
    g = gate(body)
    if g:
        parts.append(g)
    allow = block(body, 'allow', '\t')
    if allow and allow.strip() and not outside(allow):
        # `c:PAP = { gold > 500 }`: Папы может не быть в мире.
        allow = re.sub(r'\b(c:[A-Z0-9_]+) = \{', r'\1 ?= {', allow)
        parts.append('AND = { ' + ' '.join(allow.split()) + ' }')
    if name in READY_EXTRA:
        parts.append(READY_EXTRA[name])
    if not parts:
        return None
    return 'AND = {\n' + '\n'.join('\t\t' + ' '.join(p.split()) for p in parts) + '\n\t}'


# Организации выбираются из своих (`source = actor`): 0.6.1 проверял любую в мире, и
# у него стояли действия верховного королевства и ирландского лордства (10-19).
IO_MEMBER = 'scope:actor = { is_member_of_international_organization = prev }'


def estate_gate(body, est):
    """Ворота пары «действие, сословие»: условия действия и это сословие у державы."""
    pot = block(body, 'potential', '\t')
    st = block(body, 'select_trigger', '\t')
    parts = [pot] if pot and pot.strip() and not outside(pot) else []
    # `visible` и `enabled` выбора сословия: без налоговой базы, без частных полков,
    # священники у католика для налогов — такой пары в игре нет.
    inner = ''
    for key in ('visible', 'enabled'):
        b = block(st, key, '\t\t') if st else None
        if b and b.strip() and not outside(b):
            inner += ' ' + b
    parts.append('scope:actor = { any_estate = { estate_type = estate_type:%s_estate %s } }' % (est, inner))
    return 'AND = {\n' + '\n'.join('\t\t' + ' '.join(p.split()) for p in parts) + '\n\t}'


def actions():
    for kind in ('generic_actions', 'country_interactions'):
        for f in sorted(glob.glob(os.path.join(GAME, 'in_game', 'common', kind, '*.txt'))):
            text = strip_comments(open(f, encoding='utf-8-sig').read())
            for m in re.finditer(r'^([a-z_0-9]+) = \{(.*?)^\}', text, re.M | re.S):
                name, body = m.groups()
                t = re.search(r'^\ttype = (\w+)', body, re.M)
                t = t.group(1) if t else 'diplomacy'
                cd = block(body, 'cooldown', '\t')
                if cd is not None:
                    ty = re.search(r'type = (\w+)', cd)
                    du = re.search(r'(years|months|days) = ([\d.]+)', cd)
                    yield os.path.basename(f), kind, t, name, ty.group(1) if ty else name, du, body, 'has_cooldown'
                    continue
                # Откат модификатором: `allow` не пускает, пока держится модификатор, который
                # вешает само действие («Привлечь чужеземного священнослужителя», его скрин 10-19).
                if kind != 'generic_actions':
                    continue
                allow, eff = block(body, 'allow', '\t') or '', block(body, 'effect', '\t') or ''
                for mod in re.findall(r'NOT = \{\s*has_country_modifier = (\w+)\s*\}', allow):
                    add = re.search(r'modifier = ' + mod + r'\b[^}]*?(years|months|days) = ([\d.]+)', eff)
                    if re.search(r'modifier = ' + mod + r'\b', eff):
                        yield os.path.basename(f), kind, t, name, mod, add, body, 'has_country_modifier'


def list_of(fname, kind, t):
    if fname in HRE_FILES:
        return 'cd_hre'
    if kind == 'country_interactions':
        return 'cd_foreign'
    # Парламентские (`type = parliament`) — только пока идёт парламент, и он их не
    # отслеживает (10-19); экстренный созыв — в сословных.
    return {'religious': RELIGION_FILE.get(fname, 'cd_rel1'), 'religiousfaction': 'cd_rel2',
            'owncountry': 'cd_state', 'internationalorganization': 'cd_io',
            'situation': 'cd_sit', 'disaster': 'cd_dis'}.get(t)


def duration(du, ru):
    if not du:
        return ''
    n, unit = du.group(2), du.group(1)
    if ru:
        return {'years': f'{n} г', 'months': f'{n} мес', 'days': f'{n} дн'}[unit]
    return f'{n} {unit}'


def main():
    ru, en = loadloc('russian'), loadloc('english')
    rows = {}  # type -> dict
    order = []
    missing = []
    later = []  # строки-модификаторы — в конец списков, чтобы старые не сдвинулись (галочка — по номеру)
    for item in actions():
        if item[-1] == 'has_country_modifier':
            later.append(item)
    for fname, kind, t, name, ty, du, body, test in [a for a in actions() if a[-1] == 'has_cooldown'] + later:
        if fname == ESTATE_FILE and name in ESTATE_ACTIONS:
            for est in ESTATE_ACTIONS[name]:
                key = f'{name}__{est}'
                r = '%s: %s' % (plain(ru.get(name), ru), ru[est + '_estate'].lower())
                e = '%s: %s' % (plain(en.get(name), en), en[est + '_estate'].lower())
                rows[key] = {'list': 'cd_estate', 'ru': r, 'en': e, 'gates': [estate_gate(body, est)],
                             'open': False, 'du': du, 'action': name, 'est': est, 'type': ty}
                order.append(key)
            continue
        lst = 'cd_estate' if fname == ESTATE_FILE else list_of(fname, kind, t)
        if lst is None:
            continue
        g = gate(body)
        if ty not in rows:
            r, e = FIX.get(ty) or FIX.get(name) or (plain(ru.get(name), ru), plain(en.get(name), en))
            if not r or not e:
                missing.append(f'{ty} ({name}): ru={ru.get(name)!r} en={en.get(name)!r}')
            rows[ty] = {'list': lst, 'ru': r, 'en': e, 'gates': [], 'open': False, 'du': du, 'test': test,
                        'ready': [], 'ready_open': False}
            order.append(ty)
        row = rows[ty]
        rd = ready(body, name)
        if rd is None:
            row['ready_open'] = True
        else:
            row['ready'].append(rd)
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
    old = json.load(open(MANIFEST, encoding='utf-8')) if os.path.exists(MANIFEST) else {}
    moved = [lid for lid, tys in table.items() if lid in old and tys[:len(old[lid])] != old[lid]]
    if moved:
        sys.exit('строки сдвинулись или пропали (галочки съедут) — дай этим спискам новое имя: ' + ', '.join(moved))
    old.update({lid: tys for lid, tys in table.items() if tys})
    json.dump(old, open(MANIFEST, 'w', encoding='utf-8'), ensure_ascii=False, indent=1, sort_keys=True)
    lists = [l for l in LISTS if table[l[0]]]

    # --- ворота
    trig = ['﻿# ' + GEN + '\n# Ворота строк напоминалки: копия условий действия; `_ready_` — ещё и его `allow`. Scope: держава, scope:actor — она же.\n\n']
    for ty in order:
        row = rows[ty]
        if row['open'] or not row['gates']:
            body = '\talways = yes'
        else:
            body = '\tOR = {\n' + '\n'.join('\t' + g.replace('\n', '\n\t') for g in row['gates']) + '\n\t}'
        trig.append(f'bag_rtk_cd_gate_{ty} = {{\n{body}\n}}\n')
        if 'action' in row:
            continue
        if row['ready_open'] or not row['ready']:
            body = '\talways = yes'
        else:
            body = '\tOR = {\n' + '\n'.join('\t' + g.replace('\n', '\n\t') for g in row['ready']) + '\n\t}'
        trig.append(f'bag_rtk_cd_ready_{ty} = {{\n{body}\n}}\n')
    open(os.path.join(MOD, 'in_game', 'common', 'scripted_triggers', 'bag_rtk_cd_gates_generated.txt'),
         # Страны может не быть в мире (Англия к 1773-му): `?=`, как в ванили
         # (situation_triggers.txt), а не ошибка «Invalid right side 'c'» (10-20).
         'w', encoding='utf-8').write(re.sub(r'\b(\w+) = (c:[A-Z0-9_]+)\b', _tag_safe, ''.join(trig)))

    # --- эффекты
    out = ['﻿# ' + GEN + '\n\n# Регистрация подвкладок и списков. Scope: country.\nbag_rtk_cd_register_lists = {\n']
    for tid, *_ in TABS:
        out.append(f'\tcmm_register_subtab = {{ mod_id = bag_rtk tab_id = {tid} parent_tab_id = {PARENT[0]} }}\n')
    for lid, tab, *_ in lists:
        out.append(f'\tcmm_register_global_settings_list = {{ mod_id = bag_rtk setting_id = {lid} tab_id = {tab} '
                   f'item_count = {len(table[lid])} is_ordered = 0 }}\n')
    for lid, *_ in lists:
        out.append(f'\tcmm_register_list_bool_field = {{ mod_id = bag_rtk setting_id = {lid} field_id = watch default_value = 0 }}\n')
    out.append('\tbag_rtk_cd_repair_lists = yes\n}\n\n')
    # Строка `ERROR_FLAG_INDEX` без галочки (0.6.0, 0.6.3, его скрины 10-19) — строка без
    # своих переменных CMF: подпись `<строка>_name` и владелец
    # `cmm_list_item_owner_setting_<строка>`, по которому считаются поля. 0.6.4 вернул
    # подпись — галочки не было: нет владельца. Почему CMF их не записал строке,
    # добавленной к списку, не мерено; здесь они пишутся каждой строке заново, как
    # `_cmm_initialize_list_item_metadata`, а хранилище строк сверяется с 1..N
    # (зонд `list … rebuilt` в debug.log).
    out.append('# Хранилище строк каждого списка — ровно 1..N; подписи строк. Scope: country.\nbag_rtk_cd_repair_lists = {\n')
    for lid, *_ in lists:
        n = len(table[lid])
        store = f'cmm_list_items_bag_rtk__{lid}'
        known = ' '.join(f'this = flag:bag_rtk__{lid}_i{i}' for i in range(1, n + 1))
        out.append(f'\tset_global_variable = {{ name = bag_rtk_cd_total value = 0 }}\n'
                   f'\tset_global_variable = {{ name = bag_rtk_cd_foreign value = 0 }}\n'
                   f'\tevery_in_global_list = {{\n\t\tvariable = {store}\n'
                   f'\t\tchange_global_variable = {{ name = bag_rtk_cd_total add = 1 }}\n'
                   f'\t\tif = {{\n\t\t\tlimit = {{ NOT = {{ OR = {{ {known} }} }} }}\n'
                   f'\t\t\tchange_global_variable = {{ name = bag_rtk_cd_foreign add = 1 }}\n'
                   f'\t\t\tset_global_variable = {{ name = bag_rtk_cd_bad value = this }}\n\t\t}}\n\t}}\n'
                   f'\tif = {{\n\t\tlimit = {{ OR = {{ global_var:bag_rtk_cd_foreign > 0 NOT = {{ global_var:bag_rtk_cd_total = {n} }} }} }}\n'
                   f'\t\tdebug_log = "bag_rtk: list {lid} rebuilt, entries [GetGlobalVariable(\'bag_rtk_cd_total\').GetValue|0] of {n}, '
                   f'foreign [GetGlobalVariable(\'bag_rtk_cd_foreign\').GetValue|0], last foreign [GetGlobalVariable(\'bag_rtk_cd_bad\').GetFlagName]"\n'
                   f'\t\tclear_global_variable_list = {store}\n')
        for i in range(1, n + 1):
            out.append(f'\t\tadd_to_global_variable_list = {{ name = {store} target = flag:bag_rtk__{lid}_i{i} }}\n')
        out.append('\t}\n')
        for i in range(1, n + 1):
            # Владелец строки: по нему CMF считает поля строки — без него нет галочки
            # (0.6.4: подпись вернулась, галочки у выросшей строки нет, его скрин 10-19).
            out.append(f'\tset_variable = {{ name = cmm_list_item_owner_setting_bag_rtk__{lid}_i{i} value = flag:bag_rtk__{lid} }}\n')
            for suf in ('name', 'desc'):
                out.append(f'\tset_variable = {{ name = bag_rtk__{lid}_i{i}_{suf} value = flag:bag_rtk__{lid}_i{i}_{suf} }}\n')
    out.append('}\n\n# Показать или спрятать каждую строку по воротам; список, где не видно ни одной,\n'
               '# прячет его `_on_changed` (`bag_rtk_cd_shown_<список>`). Scope: country.\nbag_rtk_cd_gate_all = {\n'
               '\tsave_scope_as = actor\n')
    for lid, *_ in lists:
        out.append(f'\tremove_variable = bag_rtk_cd_shown_{lid}\n')
    for lid, *_ in lists:
        for i, ty in enumerate(table[lid], 1):
            if 'action' in rows[ty]:
                out.append(f'\tbag_rtk_cd_gate_est_row = {{ sid = {lid} i = {i} key = {ty} }}\n')
            else:
                out.append(f'\tbag_rtk_cd_gate_row = {{ sid = {lid} i = {i} type = {ty} }}\n')
    # Ворота «можно снова» (`bag_rtk_cd_ready_*`) читают scope:actor, как и при
    # регистрации: без него «Undefined event target 'actor'» (hands-off 10-25).
    out.append('}\n\n# Каждая отмеченная строка, 1-го числа. Scope: country.\nbag_rtk_cd_check_all = {\n'
               '\tsave_scope_as = actor\n')
    for lid, tab, color, view, *_ in lists:
        for i, ty in enumerate(table[lid], 1):
            row = rows[ty]
            if 'action' in row:
                out.append(f'\tbag_rtk_cd_check_est = {{ sid = {lid} i = {i} key = {ty} action = {row["action"]} '
                           f'est = {row["est"]} type = {row["type"]} view = {view} }}\n')
            elif view:
                out.append(f'\tbag_rtk_cd_check_row = {{ sid = {lid} i = {i} type = {ty} test = {row["test"]} view = {view} }}\n')
            else:
                out.append(f'\tbag_rtk_cd_check_row_noview = {{ sid = {lid} i = {i} type = {ty} test = {row["test"]} }}\n')
    out.append('}\n\n# Клик по напоминанию — убрать его. Scope: country.\nbag_rtk_cd_callback = {\n\tswitch = {\n'
               '\t\ttrigger = var:cmf_callback\n')
    for ty in order:
        out.append(f'\t\tflag:bag_rtk_rel_ready_{ty} = {{ cmf_remove_alert = {{ alert = bag_rtk_rel_ready_{ty} }} }}\n')
    out.append('\t}\n}\n')
    open(os.path.join(MOD, 'in_game', 'common', 'scripted_effects', 'bag_rtk_cd_generated.txt'),
         'w', encoding='utf-8').write(quiet_logs.quiet(''.join(out), 'bag_rtk_log'))

    # --- _on_changed списков
    sg = ['﻿# ' + GEN + '\n# Без `_on_changed` CMF прячет список целиком; правка строки применяется здесь,\n# а `is_shown` прячет список без видимых строк.\n\n']
    for lid, *_ in lists:
        sg.append(f'bag_rtk__{lid}_on_changed = {{\n\tscope = country\n'
                  f'\tis_shown = {{ has_variable = bag_rtk_cd_shown_{lid} }} # check-script: never set — `bag_rtk_cd_gate_row`\n'
                  f'\teffect = {{\n'
                  f'\t\tcmm_apply_list_change = {{ setting = bag_rtk__{lid} }}\n\t}}\n}}\n\n')
    open(os.path.join(MOD, 'in_game', 'common', 'scripted_guis', 'bag_rtk_cd_generated_sgui.txt'),
         'w', encoding='utf-8').write(''.join(sg))

    # --- локализация
    for lang, idx, head in (('russian', 'ru', 'l_russian'), ('english', 'en', 'l_english')):
        isru = lang == 'russian'
        L = [f'﻿{head}:\n', f' # {GEN}\n']
        for tid, tru, ten in [PARENT] + TABS:
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
                if rows[ty].get('test') == 'has_country_modifier':
                    tail = (f' ({d})' if d else '')
                    text = (f'Своего отката нет: не пускает модификатор, который вешает само действие{tail}.' if isru
                            else f'No cooldown of its own: the modifier the action applies blocks it{tail}.')
                else:
                    text = f'Откат {d}.' if isru else f'Cooldown {d}.'
                L.append(f' bag_rtk__{lid}_i{i}_desc: "{text}"\n')
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
