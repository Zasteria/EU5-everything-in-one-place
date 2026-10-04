#!/usr/bin/env python3
"""Every word this mod puts on screen, in each of the eleven EU5 languages.

Privileges, reforms and policies are not worded here: those lines are worded by
Glorp UI's own hint files, read out of the reference tree at build time
(`generate.py`), so the mod says them in the words Glorp UI says them.

The mod's Russian is over a thousand keys, but a language does not cost that
many translations.
Almost every hint line is an opener, a `$key$` reference the game resolves in
whatever language the player runs, and a number — so what a language actually
needs is the openers. That is the table below, and it is about fifty short
strings.

**The fourteen category nouns are not in it.** "Religious aspect", "Advance",
"Subject type" and the rest are *game concepts*: the game defines
`game_concept_religious_aspect` in all eleven of its localization folders, and
`[religious_aspect|e]` renders that in the player's language with the
encyclopedia link attached. So the category is not translated here at all — it
is asked of the game, which also means the mod uses the game's own word rather
than a synonym. That fixed seven Russian terms that were synonyms: the game
calls an advance «Улучшение», not «Достижение», and a subject type «Тип
ленника», not «Тип вассала».

The eleven languages are the folders every mod in `reference/mods/` ships:
Community Mod Framework, Glorp UI and Construction Manager all carry exactly
these, and the game's own `main_menu/localization/` is a subset of them.

`russian` is the language the mod shipped in and the only one confirmed on
screen. The other ten have never been seen in game by anybody; they are written
against the game's own terminology where a concept exists and are otherwise a
careful translation of the Russian. The openers are the *only* place a language
may differ, so a correction belongs here rather than in a generated `.yml`.
"""

from __future__ import annotations

# In the order the folders are listed; `english` first because it is the
# language every other one is derived from.
LANGUAGES = [
    "english", "french", "german", "spanish", "braz_por", "polish",
    "russian", "turkish", "simp_chinese", "japanese", "korean",
]

# The category a catalogue line opens with, as a game concept rather than as a
# translated noun. Every id here is a `game_concept_<id>` key the game defines
# in all eleven of its localization folders — checked by generate.py against
# `reference/game/main_menu/localization/`, so a concept the game renames fails
# the run instead of printing a raw token on screen.
#
# `building_types` is the one exception and is not in this table: its pushes are
# all `capital_country_modifier`, so the line has to say *build it in the
# capital* rather than merely "building type", and that is a real phrase in
# `build_in_capital` below.
CATALOG_CONCEPTS = {
    "employment_systems": "employment_system",
    "religious_aspects": "religious_aspect",
    "religious_schools": "religious_school",
    "parliament_issues": "parliament_issue",
    "chivalric_orders": "chivalric_order",
    "subject_types": "subject_type",
    "estates": "estate",
    "cabinet_actions": "cabinet_action",
    "international_organizations": "international_organization",
    "international_organization_special_statuses": "special_status",
    "advances": "advance",
    "missions": "mission",
    "parliament_types": "parliament_type",
    "bureaucracies": "bureaucracy",
}

# The tooltip registry each catalogue source lives in, which is what makes the
# object name hoverable. Registry names are the game's own `#TOOLTIP:` tokens.
CATALOG_REGISTRIES = {
    "employment_systems": "EMPLOYMENT_SYSTEM",
    "building_types": "BUILDING_TYPE",
    "religious_aspects": "RELIGIOUS_ASPECT",
    "religious_schools": "RELIGIOUS_SCHOOL",
    "parliament_issues": "PARLIAMENT_ISSUE",
    "chivalric_orders": "CHIVALRIC_ORDER",
    "subject_types": "SUBJECT_TYPE",
    "estates": "ESTATE_TYPE",
    "cabinet_actions": "CABINET_ACTION",
    "international_organizations": "INTERNATIONAL_ORGANIZATION",
    "international_organization_special_statuses": "SPECIAL_STATUS",
    "advances": "ADVANCE_DEFINITION",
    "missions": "MISSION",
    "parliament_types": "PARLIAMENT_TYPE",
    "bureaucracies": "BUREAUCRACY_TYPE",
}

# What a scaled modifier is called. Always in force, magnitude growing with the
# state of the country, so the number printed is the maximum.
SCALED_KEYS = [
    "fort_maintenance_mod", "army_maintenance_mod", "navy_maintenance_mod",
    "army_experience", "navy_experience", "army_tradition", "navy_tradition",
    "current_army_size", "current_navy_size", "average_control",
    "average_development", "average_literacy", "num_of_market_centers_in_country",
    "trade_vs_tax", "burghers_percentage_in_country",
    "peasants_percentage_in_country", "soldier_percentage_in_country",
    "state_religion_clergy_ratio", "proper_culture_nobles_ratio",
]

# Switched on whole by a condition, so the number printed is exact and the
# label is the condition itself.
CONDITIONAL_KEYS = [
    "is_bankrupt", "at_peace", "at_war", "attacker_in_war", "defender_in_war",
    "over_fort_limit", "below_half_fort_limit", "larger_than_expected_army",
    "high_legitimacy", "high_republican_tradition", "positive_self_control",
    "negative_self_control", "parliament_in_capital", "parliament_outside_capital",
    "ruler_is_general", "ruler_is_admiral", "ruler_has_general_trait",
    "ruler_has_admiral_trait", "heir_is_general", "heir_is_admiral",
    "regent_is_general", "regent_is_admiral",
]


# Added with game 1.4. Written out rather than referenced as the game's own
# `$STATIC_MODIFIER_NAME_<key>$`: a label that is nothing but a reference came
# out blank for some keys that exist (docs/pitfalls/localization.md), so every
# label carries words of its own. Filled in per language at the bottom.
NEW_SCALED_KEYS = ["num_of_foreign_markets_with_merchants"]
NEW_CONDITIONAL_KEYS = ["coastal_capital", "inland_capital"]
NEW_LABELS = {
    "num_of_foreign_markets_with_merchants": {
        "english": "Foreign markets with a merchant", "russian": "Иностранные рынки с купцом",
        "french": "Marchés étrangers avec un marchand", "german": "Fremde Märkte mit Händler",
        "spanish": "Mercados extranjeros con mercader", "braz_por": "Mercados estrangeiros com mercador",
        "polish": "Obce rynki z kupcem", "turkish": "Tüccarlı yabancı pazarlar",
        "simp_chinese": "派驻商人的外国市场", "japanese": "商人のいる外国市場", "korean": "상인이 있는 외국 시장"},
    "coastal_capital": {
        "english": "Coastal capital", "russian": "Приморская столица", "french": "Capitale côtière",
        "german": "Küstenhauptstadt", "spanish": "Capital costera", "braz_por": "Capital costeira",
        "polish": "Nadmorska stolica", "turkish": "Kıyı başkenti", "simp_chinese": "沿海首都",
        "japanese": "沿岸の首都", "korean": "해안 수도"},
    "inland_capital": {
        "english": "Inland capital", "russian": "Внутренняя столица", "french": "Capitale intérieure",
        "german": "Binnenhauptstadt", "spanish": "Capital interior", "braz_por": "Capital interior",
        "polish": "Śródlądowa stolica", "turkish": "İç bölge başkenti", "simp_chinese": "内陆首都",
        "japanese": "内陸の首都", "korean": "내륙 수도"},
}


def _language(catalog, build_in_capital, scales, up_to, cabinet, cabinet_scales,
              io_policy, estate_power, titles, menu, scaled,
              conditional):
    """One language's table, with the two list orders checked as it is built."""
    assert list(scaled) == SCALED_KEYS, "scaled labels out of order"
    assert list(conditional) == CONDITIONAL_KEYS, "conditional labels out of order"
    return {
        "catalog": catalog,
        "build_in_capital": build_in_capital,
        "scales": scales,
        "up_to": up_to,
        "cabinet": cabinet,
        "cabinet_scales": cabinet_scales,
        "io_policy": io_policy,
        "estate_power": estate_power,
        "titles": titles,
        "menu": menu,
        "scaled": scaled,
        "conditional": conditional,
    }


def _pairs(keys, values):
    return dict(zip(keys, values))


PHRASES: dict[str, dict] = {}

# --- english ---------------------------------------------------------------
PHRASES["english"] = _language(
    catalog="[{concept}|e] {ref}",
    build_in_capital="Build in the capital",
    scales="scales",
    up_to="up to ",
    cabinet="Point the cabinet at this value",
    cabinet_scales="scales with cabinet efficiency",
    io_policy="Have your [international_organization|e] adopt the {ref} [policy]",
    estate_power="{ref} above the threshold",
    titles={
        "SVX_EVERYTHING": "Also pushes towards this (unfiltered):",
        "SVX_NEVER": "Not available to this country:",
    },
    menu={
        "svx_name": "Societal Value Hints",
        "svx_desc": "Lists in the societal value tooltip everything that pushes the value: privileges, reforms, policies and every other source, split into what your country can take now and what it can reach later. Works on top of Glorp UI or on its own.",
        "svx__main_name": "Lists",
        "svx__main__lists_name": "Filtering",
        "svx__show_all_name": "Show everything",
        "svx__show_all_desc": "Also lists, after the two filtered lists, what this country can never take, each with its age and what it takes, and every other source unfiltered. Glorp UI's “show unavailable suggestions” switch does the same.",
    },
    scaled=_pairs(SCALED_KEYS, [
        "Fort maintenance", "Army maintenance", "Navy maintenance",
        "Army experience", "Navy experience", "Army tradition", "Navy tradition",
        "Army size", "Navy size", "Average control", "Average development",
        "Average literacy", "Number of market centres",
        "Share of trade in income", "Share of burghers in the population",
        "Share of peasants in the population", "Share of soldiers in the population",
        "Share of state religion clergy", "Share of primary culture nobles",
    ]),
    conditional=_pairs(CONDITIONAL_KEYS, [
        "While bankrupt",
        "In peacetime",
        "In wartime",
        "Attacker in a war",
        "Defender in a war",
        "Over the fort limit",
        "Below half the fort limit",
        "Army larger than expected",
        "High legitimacy",
        "High republican tradition",
        "[self_control|e] above 10",
        "[self_control|e] below -10",
        "Parliament in the capital",
        "Parliament outside the capital",
        "Ruler is a general",
        "Ruler is an admiral",
        "Ruler has a general's trait",
        "Ruler has an admiral's trait",
        "Heir is a general",
        "Heir is an admiral",
        "Regent is a general",
        "Regent is an admiral",
    ]),
)

# --- russian ---------------------------------------------------------------
# The language the mod shipped in and the only one confirmed on screen. Only the
# fourteen category nouns changed when the concept tokens went in, and they
# changed towards the game's own vocabulary rather than away from it.
PHRASES["russian"] = _language(
    catalog="[{concept}|e] {ref}",
    build_in_capital="Построить в столице",
    scales="масштабируется",
    up_to="до ",
    cabinet="Направить совет на эту ценность",
    cabinet_scales="масштабируется от эффективности совета",
    io_policy="Добиться в [Concept('international_organization', 'объединении')|e] [Concept('policy', 'политики')] «{ref}»",
    estate_power="{ref} выше порога",
    titles={
        "SVX_EVERYTHING": "Также влияет на смещение (без фильтра):",
        "SVX_NEVER": "Недоступно этой державе:",
    },
    menu={
        "svx_name": "Подсказки общественных ценностей",
        "svx_desc": "Перечисляет в подсказке общественной ценности всё, что её сдвигает: привилегии, реформы, политики и прочие источники — отдельно то, что держава может взять сейчас, и то, что станет доступно позже. Работает поверх Glorp UI и без него.",
        "svx__main_name": "Списки",
        "svx__main__lists_name": "Фильтрация",
        "svx__show_all_name": "Показывать всё",
        "svx__show_all_desc": "Под двумя отфильтрованными списками показывает ещё то, что этой державе недоступно, — у каждого эпоха и что нужно, чтобы получить, — и все прочие источники без фильтра. То же делает переключатель Glorp UI «Показать недоступные предложения».",
    },
    scaled=_pairs(SCALED_KEYS, [
        "Содержание крепостей", "Содержание армии", "Содержание флота",
        "Опыт армии", "Опыт флота", "Традиции армии", "Традиции флота",
        "Размер армии", "Размер флота", "Средний контроль", "Среднее развитие",
        "Средняя грамотность", "Число рыночных центров",
        "Доля торговли в доходах", "Доля горожан в населении",
        "Доля крестьян в населении", "Доля солдат в населении",
        "Доля духовенства госрелигии", "Доля знати основной культуры",
    ]),
    conditional=_pairs(CONDITIONAL_KEYS, [
        "Во время банкротства",
        "В мирное время",
        "Во время войны",
        "Нападающая сторона в войне",
        "Обороняющаяся сторона в войне",
        "Превышен лимит крепостей",
        "Крепостей меньше половины лимита",
        "Армия больше ожидаемой",
        "Высокая легитимность",
        "Высокие республиканские традиции",
        "[self_control|e] выше 10",
        "[self_control|e] ниже −10",
        "Парламент в столице",
        "Парламент вне столицы",
        "Правитель — генерал",
        "Правитель — адмирал",
        "У правителя черта генерала",
        "У правителя черта адмирала",
        "Наследник — генерал",
        "Наследник — адмирал",
        "Регент — генерал",
        "Регент — адмирал",
    ]),
)

# --- french ----------------------------------------------------------------
PHRASES["french"] = _language(
    catalog="[{concept}|e] {ref}",
    build_in_capital="Construire dans la capitale",
    scales="variable",
    up_to="jusqu'à ",
    cabinet="Orienter le cabinet vers cette valeur",
    cabinet_scales="varie avec l'efficacité du cabinet",
    io_policy="Faire adopter la [policy] {ref} par votre [international_organization|e]",
    estate_power="{ref} au-dessus du seuil",
    titles={
        "SVX_EVERYTHING": "Pousse également dans ce sens (sans filtre) :",
        "SVX_NEVER": "Indisponible pour ce pays :",
    },
    menu={
        "svx_name": "Indices de valeurs sociétales",
        "svx_desc": "Liste dans l'infobulle de valeur sociétale tout ce qui la fait évoluer : privilèges, réformes, politiques et toutes les autres sources, en séparant ce que votre pays peut obtenir maintenant de ce qu'il pourra atteindre plus tard. Fonctionne avec ou sans Glorp UI.",
        "svx__main_name": "Listes",
        "svx__main__lists_name": "Filtrage",
        "svx__show_all_name": "Tout afficher",
        "svx__show_all_desc": "Affiche aussi, après les deux listes filtrées, ce que ce pays ne peut jamais obtenir, chacun avec son âge et ce qu'il demande, ainsi que toutes les autres sources sans filtre. L'option « afficher les suggestions non disponibles » de Glorp UI fait de même.",
    },
    scaled=_pairs(SCALED_KEYS, [
        "Entretien des forts", "Entretien de l'armée", "Entretien de la flotte",
        "Expérience de l'armée", "Expérience de la flotte",
        "Tradition militaire", "Tradition navale",
        "Taille de l'armée", "Taille de la flotte", "Contrôle moyen",
        "Développement moyen", "Alphabétisation moyenne",
        "Nombre de centres commerciaux", "Part du commerce dans les revenus",
        "Part des bourgeois dans la population",
        "Part des paysans dans la population",
        "Part des soldats dans la population",
        "Part du clergé de la religion d'État",
        "Part des nobles de la culture principale",
    ]),
    conditional=_pairs(CONDITIONAL_KEYS, [
        "En cas de banqueroute",
        "En temps de paix",
        "En temps de guerre",
        "Assaillant dans une guerre",
        "Défenseur dans une guerre",
        "Au-dessus de la limite de forts",
        "En dessous de la moitié de la limite de forts",
        "Armée plus grande que prévu",
        "Légitimité élevée",
        "Tradition républicaine élevée",
        "[self_control|e] supérieure à 10",
        "[self_control|e] inférieure à -10",
        "Parlement dans la capitale",
        "Parlement hors de la capitale",
        "Le souverain est un général",
        "Le souverain est un amiral",
        "Le souverain a un trait de général",
        "Le souverain a un trait d'amiral",
        "L'héritier est un général",
        "L'héritier est un amiral",
        "Le régent est un général",
        "Le régent est un amiral",
    ]),
)

# --- german ----------------------------------------------------------------
PHRASES["german"] = _language(
    catalog="[{concept}|e] {ref}",
    build_in_capital="In der Hauptstadt bauen",
    scales="skaliert",
    up_to="bis zu ",
    cabinet="Das Kabinett auf diesen Wert ausrichten",
    cabinet_scales="skaliert mit der Kabinettseffizienz",
    io_policy="Eure [international_organization|e] die [policy] „{ref}“ erlassen lassen",
    estate_power="{ref} über der Schwelle",
    titles={
        "SVX_EVERYTHING": "Treibt ebenfalls in diese Richtung (ungefiltert):",
        "SVX_NEVER": "Für dieses Land nicht verfügbar:",
    },
    menu={
        "svx_name": "Hinweise zu gesellschaftlichen Werten",
        "svx_desc": "Listet im Tooltip eines gesellschaftlichen Werts alles, was ihn verschiebt: Privilegien, Reformen, Politiken und alle anderen Quellen, getrennt nach dem, was Euer Land jetzt nehmen kann, und dem, was es später erreichen kann. Funktioniert mit oder ohne Glorp UI.",
        "svx__main_name": "Listen",
        "svx__main__lists_name": "Filterung",
        "svx__show_all_name": "Alles zeigen",
        "svx__show_all_desc": "Zeigt unter den beiden gefilterten Listen auch, was dieses Land nie erhalten kann, jeweils mit Zeitalter und Voraussetzungen, sowie alle anderen Quellen ungefiltert. Der Schalter „Nicht verfügbare Vorschläge anzeigen“ von Glorp UI tut dasselbe.",
    },
    scaled=_pairs(SCALED_KEYS, [
        "Festungsunterhalt", "Heeresunterhalt", "Flottenunterhalt",
        "Heereserfahrung", "Flottenerfahrung", "Heerestradition",
        "Flottentradition", "Heeresgröße", "Flottengröße",
        "Durchschnittliche Kontrolle", "Durchschnittliche Entwicklung",
        "Durchschnittliche Alphabetisierung", "Anzahl der Handelszentren",
        "Anteil des Handels an den Einnahmen",
        "Anteil der Bürger an der Bevölkerung",
        "Anteil der Bauern an der Bevölkerung",
        "Anteil der Soldaten an der Bevölkerung",
        "Anteil des Klerus der Staatsreligion",
        "Anteil des Adels der Hauptkultur",
    ]),
    conditional=_pairs(CONDITIONAL_KEYS, [
        "Während des Staatsbankrotts",
        "In Friedenszeiten",
        "In Kriegszeiten",
        "Angreifer in einem Krieg",
        "Verteidiger in einem Krieg",
        "Über der Festungsgrenze",
        "Unter der halben Festungsgrenze",
        "Heer größer als erwartet",
        "Hohe Legitimität",
        "Hohe republikanische Tradition",
        "[self_control|e] über 10",
        "[self_control|e] unter -10",
        "Parlament in der Hauptstadt",
        "Parlament außerhalb der Hauptstadt",
        "Herrscher ist General",
        "Herrscher ist Admiral",
        "Herrscher hat eine Generalseigenschaft",
        "Herrscher hat eine Admiralseigenschaft",
        "Thronfolger ist General",
        "Thronfolger ist Admiral",
        "Regent ist General",
        "Regent ist Admiral",
    ]),
)

# --- spanish ---------------------------------------------------------------
PHRASES["spanish"] = _language(
    catalog="[{concept}|e] {ref}",
    build_in_capital="Construir en la capital",
    scales="escala",
    up_to="hasta ",
    cabinet="Orientar el gabinete hacia este valor",
    cabinet_scales="escala con la eficiencia del gabinete",
    io_policy="Hacer que tu [international_organization|e] adopte la [policy|l] {ref}",
    estate_power="{ref} por encima del umbral",
    titles={
        "SVX_EVERYTHING": "También empuja en esta dirección (sin filtro):",
        "SVX_NEVER": "No disponible para este país:",
    },
    menu={
        "svx_name": "Pistas de valores sociales",
        "svx_desc": "Muestra en la descripción de un valor social todo lo que lo desplaza: privilegios, reformas, políticas y cualquier otra fuente, separando lo que tu país puede tomar ahora de lo que podrá alcanzar más adelante. Funciona con o sin Glorp UI.",
        "svx__main_name": "Listas",
        "svx__main__lists_name": "Filtrado",
        "svx__show_all_name": "Mostrar todo",
        "svx__show_all_desc": "Muestra también, tras las dos listas filtradas, lo que este país nunca podrá obtener, cada cosa con su era y lo que requiere, y todas las demás fuentes sin filtro. El interruptor «mostrar sugerencias no disponibles» de Glorp UI hace lo mismo.",
    },
    scaled=_pairs(SCALED_KEYS, [
        "Mantenimiento de fuertes", "Mantenimiento del ejército",
        "Mantenimiento de la armada", "Experiencia del ejército",
        "Experiencia de la armada", "Tradición militar", "Tradición naval",
        "Tamaño del ejército", "Tamaño de la armada", "Control medio",
        "Desarrollo medio", "Alfabetización media",
        "Número de centros de mercado", "Proporción del comercio en los ingresos",
        "Proporción de burgueses en la población",
        "Proporción de campesinos en la población",
        "Proporción de soldados en la población",
        "Proporción del clero de la religión estatal",
        "Proporción de nobles de la cultura principal",
    ]),
    conditional=_pairs(CONDITIONAL_KEYS, [
        "Durante la bancarrota",
        "En tiempos de paz",
        "En tiempos de guerra",
        "Atacante en una guerra",
        "Defensor en una guerra",
        "Por encima del límite de fuertes",
        "Por debajo de la mitad del límite de fuertes",
        "Ejército mayor de lo esperado",
        "Legitimidad alta",
        "Tradición republicana alta",
        "[self_control|e] por encima de 10",
        "[self_control|e] por debajo de -10",
        "Parlamento en la capital",
        "Parlamento fuera de la capital",
        "El gobernante es general",
        "El gobernante es almirante",
        "El gobernante tiene un rasgo de general",
        "El gobernante tiene un rasgo de almirante",
        "El heredero es general",
        "El heredero es almirante",
        "El regente es general",
        "El regente es almirante",
    ]),
)

# --- braz_por --------------------------------------------------------------
PHRASES["braz_por"] = _language(
    catalog="[{concept}|e] {ref}",
    build_in_capital="Construir na capital",
    scales="escala",
    up_to="até ",
    cabinet="Direcionar o gabinete para este valor",
    cabinet_scales="escala com a eficiência do gabinete",
    io_policy="Fazer sua [international_organization|e] promulgar a [policy] {ref}",
    estate_power="{ref} acima do limite",
    titles={
        "SVX_EVERYTHING": "Também empurra nesta direção (sem filtro):",
        "SVX_NEVER": "Indisponível para este país:",
    },
    menu={
        "svx_name": "Dicas de valores sociais",
        "svx_desc": "Lista na dica de um valor social tudo o que o desloca: privilégios, reformas, políticas e todas as outras fontes, separando o que seu país pode adotar agora do que poderá alcançar mais tarde. Funciona com ou sem o Glorp UI.",
        "svx__main_name": "Listas",
        "svx__main__lists_name": "Filtragem",
        "svx__show_all_name": "Mostrar tudo",
        "svx__show_all_desc": "Mostra também, após as duas listas filtradas, o que este país nunca pode obter, cada item com sua era e o que exige, e todas as outras fontes sem filtro. A opção “mostrar sugestões indisponíveis” do Glorp UI faz o mesmo.",
    },
    scaled=_pairs(SCALED_KEYS, [
        "Manutenção de fortes", "Manutenção do exército",
        "Manutenção da marinha", "Experiência do exército",
        "Experiência da marinha", "Tradição militar", "Tradição naval",
        "Tamanho do exército", "Tamanho da marinha", "Controle médio",
        "Desenvolvimento médio", "Alfabetização média",
        "Número de centros de mercado", "Parcela do comércio na receita",
        "Parcela de burgueses na população",
        "Parcela de camponeses na população",
        "Parcela de soldados na população",
        "Parcela do clero da religião oficial",
        "Parcela de nobres da cultura principal",
    ]),
    conditional=_pairs(CONDITIONAL_KEYS, [
        "Durante a bancarrota",
        "Em tempos de paz",
        "Em tempos de guerra",
        "Atacante numa guerra",
        "Defensor numa guerra",
        "Acima do limite de fortes",
        "Abaixo de metade do limite de fortes",
        "Exército maior do que o esperado",
        "Legitimidade alta",
        "Tradição republicana alta",
        "[self_control|e] acima de 10",
        "[self_control|e] abaixo de -10",
        "Parlamento na capital",
        "Parlamento fora da capital",
        "O governante é general",
        "O governante é almirante",
        "O governante tem um traço de general",
        "O governante tem um traço de almirante",
        "O herdeiro é general",
        "O herdeiro é almirante",
        "O regente é general",
        "O regente é almirante",
    ]),
)

# --- polish ----------------------------------------------------------------
PHRASES["polish"] = _language(
    catalog="[{concept}|e] {ref}",
    build_in_capital="Zbuduj w stolicy",
    scales="skaluje się",
    up_to="do ",
    cabinet="Skieruj gabinet na tę wartość",
    cabinet_scales="skaluje się z efektywnością gabinetu",
    io_policy="Doprowadź do przyjęcia [Concept('policy','polityki')] „{ref}” w [Concept('international_organization','organizacji')|e]",
    estate_power="{ref} powyżej progu",
    titles={
        "SVX_EVERYTHING": "Również przesuwa w tę stronę (bez filtra):",
        "SVX_NEVER": "Niedostępne dla tego państwa:",
    },
    menu={
        "svx_name": "Podpowiedzi wartości społecznych",
        "svx_desc": "Wymienia w podpowiedzi wartości społecznej wszystko, co ją przesuwa: przywileje, reformy, polityki i wszystkie inne źródła, osobno to, co państwo może przyjąć teraz, i to, co stanie się dostępne później. Działa z Glorp UI i bez niego.",
        "svx__main_name": "Listy",
        "svx__main__lists_name": "Filtrowanie",
        "svx__show_all_name": "Pokaż wszystko",
        "svx__show_all_desc": "Pod dwiema przefiltrowanymi listami pokazuje też to, czego to państwo nigdy nie zdobędzie, każde z erą i wymaganiami, oraz wszystkie inne źródła bez filtra. Przełącznik Glorp UI „Pokaż niedostępne sugestie” robi to samo.",
    },
    scaled=_pairs(SCALED_KEYS, [
        "Utrzymanie fortów", "Utrzymanie armii", "Utrzymanie floty",
        "Doświadczenie armii", "Doświadczenie floty", "Tradycja armii",
        "Tradycja floty", "Wielkość armii", "Wielkość floty",
        "Średnia kontrola", "Średni rozwój", "Średnia piśmienność",
        "Liczba centrów handlowych", "Udział handlu w dochodach",
        "Udział mieszczan w ludności", "Udział chłopów w ludności",
        "Udział żołnierzy w ludności",
        "Udział duchowieństwa religii państwowej",
        "Udział szlachty kultury głównej",
    ]),
    conditional=_pairs(CONDITIONAL_KEYS, [
        "W czasie bankructwa",
        "W czasie pokoju",
        "W czasie wojny",
        "Strona atakująca w wojnie",
        "Strona broniąca się w wojnie",
        "Powyżej limitu fortów",
        "Poniżej połowy limitu fortów",
        "Armia większa niż oczekiwana",
        "Wysoka legitymizacja",
        "Wysoka tradycja republikańska",
        "[self_control|e] powyżej 10",
        "[self_control|e] poniżej -10",
        "Parlament w stolicy",
        "Parlament poza stolicą",
        "Władca jest generałem",
        "Władca jest admirałem",
        "Władca ma cechę generała",
        "Władca ma cechę admirała",
        "Następca jest generałem",
        "Następca jest admirałem",
        "Regent jest generałem",
        "Regent jest admirałem",
    ]),
)

# --- turkish ---------------------------------------------------------------
PHRASES["turkish"] = _language(
    catalog="[{concept}|e] {ref}",
    build_in_capital="Başkentte inşa et",
    scales="ölçeklenir",
    up_to="en fazla ",
    cabinet="Kabineyi bu değere yönlendir",
    cabinet_scales="kabine verimliliğine göre ölçeklenir",
    io_policy="[international_organization|e] {ref} [policy] kabul etsin",
    estate_power="Eşiğin üzerinde {ref}",
    titles={
        "SVX_EVERYTHING": "Bu yöne de iter (filtresiz):",
        "SVX_NEVER": "Bu ülke için kullanılamaz:",
    },
    menu={
        "svx_name": "Toplumsal Değer İpuçları",
        "svx_desc": "Toplumsal değer ipucunda değeri kaydıran her şeyi listeler: ayrıcalıklar, reformlar, politikalar ve diğer tüm kaynaklar; ülkenizin şimdi alabildikleri ile daha sonra ulaşabilecekleri ayrı ayrı. Glorp UI ile veya onsuz çalışır.",
        "svx__main_name": "Listeler",
        "svx__main__lists_name": "Filtreleme",
        "svx__show_all_name": "Her şeyi göster",
        "svx__show_all_desc": "İki filtrelenmiş listenin altında bu ülkenin asla alamayacaklarını, her birinin çağı ve gereklilikleriyle, ve diğer tüm kaynakları filtresiz gösterir. Glorp UI'ın “kullanılamayan önerileri göster” anahtarı da aynısını yapar.",
    },
    scaled=_pairs(SCALED_KEYS, [
        "Kale bakımı", "Ordu bakımı", "Donanma bakımı", "Ordu tecrübesi",
        "Donanma tecrübesi", "Ordu geleneği", "Donanma geleneği",
        "Ordu büyüklüğü", "Donanma büyüklüğü", "Ortalama kontrol",
        "Ortalama gelişim", "Ortalama okuryazarlık", "Pazar merkezi sayısı",
        "Gelirde ticaretin payı", "Nüfusta burjuvaların payı",
        "Nüfusta köylülerin payı", "Nüfusta askerlerin payı",
        "Devlet dini ruhban sınıfının payı", "Ana kültür soylularının payı",
    ]),
    conditional=_pairs(CONDITIONAL_KEYS, [
        "İflas sırasında",
        "Barış zamanında",
        "Savaş zamanında",
        "Savaşta saldıran taraf",
        "Savaşta savunan taraf",
        "Kale sınırının üzerinde",
        "Kale sınırının yarısının altında",
        "Ordu beklenenden büyük",
        "Yüksek meşruiyet",
        "Yüksek cumhuriyetçi gelenek",
        "[self_control|e] 10'un üzerinde",
        "[self_control|e] -10'un altında",
        "Başkentte parlamento",
        "Başkent dışında parlamento",
        "Hükümdar general",
        "Hükümdar amiral",
        "Hükümdarda general özelliği var",
        "Hükümdarda amiral özelliği var",
        "Veliaht general",
        "Veliaht amiral",
        "Naip general",
        "Naip amiral",
    ]),
)

# --- simp_chinese ----------------------------------------------------------
PHRASES["simp_chinese"] = _language(
    catalog="[{concept}|e]{ref}",
    build_in_capital="在首都建造",
    scales="按比例变化",
    up_to="最多 ",
    cabinet="让内阁推动该价值观",
    cabinet_scales="随内阁效率变化",
    io_policy="让你的[international_organization|e]颁布{ref}[policy]",
    estate_power="{ref}高于阈值",
    titles={
        "SVX_EVERYTHING": "同样推动该方向（未筛选）：",
        "SVX_NEVER": "此国家无法获得：",
    },
    menu={
        "svx_name": "社会价值观提示",
        "svx_desc": "在社会价值观提示中列出所有推动该价值观的来源：特权、改革、政策及其他一切来源，并分开列出你的国家现在可以采取的和以后可以达成的。可与Glorp UI一同使用，也可单独使用。",
        "svx__main_name": "列表",
        "svx__main__lists_name": "筛选",
        "svx__show_all_name": "显示全部",
        "svx__show_all_desc": "在两个筛选列表之下，另外列出此国家永远无法获得的项目（各附时代与所需条件），以及所有其他来源（未筛选）。Glorp UI的“显示不可用建议”开关效果相同。",
    },
    scaled=_pairs(SCALED_KEYS, [
        "堡垒维护费", "陆军维护费", "海军维护费", "陆军经验", "海军经验",
        "陆军传统", "海军传统", "陆军规模", "海军规模", "平均控制度",
        "平均发展度", "平均识字率", "市场中心数量", "贸易收入占比",
        "市民人口占比", "农民人口占比", "士兵人口占比",
        "国教神职人员占比", "主流文化贵族占比",
    ]),
    conditional=_pairs(CONDITIONAL_KEYS, [
        "破产期间",
        "和平时期",
        "战争时期",
        "战争中的进攻方",
        "战争中的防守方",
        "超出堡垒上限",
        "低于堡垒上限的一半",
        "陆军规模超出预期",
        "高正统性",
        "高共和传统",
        "[self_control|e]高于10",
        "[self_control|e]低于-10",
        "议会位于首都",
        "议会不在首都",
        "统治者是将军",
        "统治者是海军将领",
        "统治者拥有将军特质",
        "统治者拥有海军将领特质",
        "继承人是将军",
        "继承人是海军将领",
        "摄政是将军",
        "摄政是海军将领",
    ]),
)

# --- japanese --------------------------------------------------------------
PHRASES["japanese"] = _language(
    catalog="[{concept}|e]{ref}",
    build_in_capital="首都に建設",
    scales="規模に応じて変動",
    up_to="最大 ",
    cabinet="内閣をこの価値観に向ける",
    cabinet_scales="内閣の効率に応じて変動",
    io_policy="[international_organization|e]に[policy]「{ref}」を制定させる",
    estate_power="閾値を超えた{ref}",
    titles={
        "SVX_EVERYTHING": "この方向にも推進（フィルターなし）：",
        "SVX_NEVER": "この国では利用不可：",
    },
    menu={
        "svx_name": "社会的価値観のヒント",
        "svx_desc": "社会的価値観のツールチップに、その価値観を動かすすべてのもの（特権、改革、政策、その他すべての要因）を、今すぐ採用できるものと後で手が届くものに分けて表示します。Glorp UIと併用しても単独でも動作します。",
        "svx__main_name": "リスト",
        "svx__main__lists_name": "フィルター",
        "svx__show_all_name": "すべて表示",
        "svx__show_all_desc": "2つのフィルター済みリストの下に、この国が決して得られないもの（それぞれ時代と必要条件付き）と、その他すべての要因をフィルターなしで表示します。Glorp UIの「利用できない提案を表示」スイッチも同じ働きをします。",
    },
    scaled=_pairs(SCALED_KEYS, [
        "要塞維持費", "陸軍維持費", "海軍維持費", "陸軍経験", "海軍経験",
        "陸軍伝統", "海軍伝統", "陸軍規模", "海軍規模", "平均統制",
        "平均開発度", "平均識字率", "市場中心地の数", "収入に占める交易の割合",
        "人口に占める市民の割合", "人口に占める農民の割合",
        "人口に占める兵士の割合", "国教聖職者の割合", "主要文化の貴族の割合",
    ]),
    conditional=_pairs(CONDITIONAL_KEYS, [
        "破産中",
        "平時",
        "戦時",
        "戦争の攻撃側",
        "戦争の防衛側",
        "要塞上限を超過",
        "要塞上限の半分未満",
        "陸軍が想定より大きい",
        "高い正統性",
        "高い共和制伝統",
        "[self_control|e]が10より上",
        "[self_control|e]が-10より下",
        "首都に議会",
        "首都外に議会",
        "統治者が将軍",
        "統治者が提督",
        "統治者が将軍の特性を持つ",
        "統治者が提督の特性を持つ",
        "後継者が将軍",
        "後継者が提督",
        "摂政が将軍",
        "摂政が提督",
    ]),
)

# --- korean ----------------------------------------------------------------
PHRASES["korean"] = _language(
    catalog="[{concept}|e] {ref}",
    build_in_capital="수도에 건설",
    scales="규모에 따라 변동",
    up_to="최대 ",
    cabinet="내각을 이 가치에 집중",
    cabinet_scales="내각 효율에 따라 변동",
    io_policy="[international_organization|e]에서 {ref} [policy] 채택",
    estate_power="문턱을 넘은 {ref}",
    titles={
        "SVX_EVERYTHING": "이 방향으로도 이동 (필터 없음):",
        "SVX_NEVER": "이 국가는 이용 불가:",
    },
    menu={
        "svx_name": "사회적 가치 힌트",
        "svx_desc": "사회적 가치 툴팁에 그 가치를 움직이는 모든 것(특권, 개혁, 정책 및 기타 모든 원천)을 지금 취할 수 있는 것과 나중에 도달할 수 있는 것으로 나누어 보여줍니다. Glorp UI와 함께 또는 단독으로 작동합니다.",
        "svx__main_name": "목록",
        "svx__main__lists_name": "필터",
        "svx__show_all_name": "모두 표시",
        "svx__show_all_desc": "필터된 두 목록 아래에 이 국가가 결코 얻을 수 없는 것(각각 시대와 필요 조건 포함)과 다른 모든 원천을 필터 없이 보여줍니다. Glorp UI의 ‘사용할 수 없는 제안 표시’ 스위치도 같은 역할을 합니다.",
    },
    scaled=_pairs(SCALED_KEYS, [
        "요새 유지비", "육군 유지비", "해군 유지비", "육군 경험", "해군 경험",
        "육군 전통", "해군 전통", "육군 규모", "해군 규모", "평균 통제도",
        "평균 발전도", "평균 문해율", "시장 중심지 수", "수입 중 교역 비중",
        "인구 중 시민 비중", "인구 중 농민 비중", "인구 중 병사 비중",
        "국교 성직자 비중", "주 문화 귀족 비중",
    ]),
    conditional=_pairs(CONDITIONAL_KEYS, [
        "파산 중",
        "평시",
        "전시",
        "전쟁의 공격 측",
        "전쟁의 방어 측",
        "요새 한도 초과",
        "요새 한도의 절반 미만",
        "예상보다 큰 육군",
        "높은 정통성",
        "높은 공화정 전통",
        "[self_control|e] 10 초과",
        "[self_control|e] -10 미만",
        "수도에 의회",
        "수도 밖에 의회",
        "통치자가 장군",
        "통치자가 제독",
        "통치자가 장군 특성 보유",
        "통치자가 제독 특성 보유",
        "후계자가 장군",
        "후계자가 제독",
        "섭정이 장군",
        "섭정이 제독",
    ]),
)

# --- Glorp UI keys this mod repairs -----------------------------------------
# Not hints: four keys of Glorp UI's own interface whose Russian is broken
# grammar. Glorp UI marks all four `# LOCK`, so they are not going to be fixed
# by whatever produced them. Only Russian is affected - the other nine
# translations of these keys are grammatical, so nothing overrides them and
# Glorp UI keeps ownership of its own text there.
#
# `Средняя значение` is a feminine adjective on a neuter noun; `Обновить Средняя
# расстояние` is a nominative adjective where an accusative belongs, on a noun
# the rest of the file calls «досягаемость» rather than «расстояние». The two
# `[concept|e]` lines are rewritten to put the concept first, so the game's own
# capitalised term opens the phrase instead of landing mid-sentence.
GLORP_UI_FIXES = {
    "russian": {
        # "Average [max_control|e]"  -  was "Средняя значение [max_control|e]"
        "GLORP_UI_AVG_CONTROL": "[max_control|e] в среднем",
        # "Average [proximity|e]"  -  was "Средняя [proximity|e]"
        "GLORP_UI_AVG_PROXIMITY": "[proximity|e] в среднем",
        # "Swap to Average Control"  -  was "Переключиться на режим «Средняя»".
        # Glorp UI's own sibling key reads "Переключиться на режим
        # «Максимальный контроль»", so this is the shape it wants.
        "SWAP_TO_AVG_CONTROL": "Переключиться на режим «Средний контроль»",
        # "Refresh Average Proximity"  -  was "Обновить Средняя расстояние"
        "REFRESH_AVG_PROX": "Обновить среднюю досягаемость",
    },
}

for _key, _labels in NEW_LABELS.items():
    for _lang, _phrases in PHRASES.items():
        _table = "scaled" if _key in NEW_SCALED_KEYS else "conditional"
        _phrases[_table][_key] = _labels[_lang]

assert set(GLORP_UI_FIXES) <= set(LANGUAGES), "a fix for a language that is not one"
assert set(PHRASES) == set(LANGUAGES), "a language is in one list and not the other"


# How a gate that is only a game variable is worded instead (generate.py,
# flag_sources): the decision, event, disaster or rebel demand that sets it,
# and whose it is. {name} is a game key's text, {tags} country names.
FLAG_WORDS = {
    "english": {"decision_country": "A decision of {tags}", "decision": "Decision «{name}» taken ({tags})", "event": "Event «{name}» ({tags})",
                "event_country": "An event of {tags}", "disaster": "Outcome of the disaster «{name}»",
                "rebels": "A concession to rebels ({tags})"},
    "russian": {"decision_country": "Решение державы {tags}", "decision": "Принято решение «{name}» ({tags})", "event": "Было событие «{name}» ({tags})",
                "event_country": "Событие державы {tags}", "disaster": "Исход бедствия «{name}»",
                "rebels": "Уступка мятежникам ({tags})"},
    "french": {"decision_country": "Une décision de {tags}", "decision": "Décision « {name} » prise ({tags})", "event": "Événement « {name} » ({tags})",
               "event_country": "Un événement de {tags}", "disaster": "Issue de la catastrophe « {name} »",
               "rebels": "Une concession aux rebelles ({tags})"},
    "german": {"decision_country": "Eine Entscheidung von {tags}", "decision": "Entscheidung „{name}“ getroffen ({tags})", "event": "Ereignis „{name}“ ({tags})",
               "event_country": "Ein Ereignis von {tags}", "disaster": "Ausgang der Katastrophe „{name}“",
               "rebels": "Ein Zugeständnis an Rebellen ({tags})"},
    "spanish": {"decision_country": "Una decisión de {tags}", "decision": "Decisión «{name}» tomada ({tags})", "event": "Evento «{name}» ({tags})",
                "event_country": "Un evento de {tags}", "disaster": "Desenlace del desastre «{name}»",
                "rebels": "Una concesión a los rebeldes ({tags})"},
    "braz_por": {"decision_country": "Uma decisão de {tags}", "decision": "Decisão «{name}» tomada ({tags})", "event": "Evento «{name}» ({tags})",
                 "event_country": "Um evento de {tags}", "disaster": "Desfecho do desastre «{name}»",
                 "rebels": "Uma concessão aos rebeldes ({tags})"},
    "polish": {"decision_country": "Decyzja państwa {tags}", "decision": "Podjęta decyzja „{name}” ({tags})", "event": "Wydarzenie „{name}” ({tags})",
               "event_country": "Wydarzenie państwa {tags}", "disaster": "Wynik katastrofy „{name}”",
               "rebels": "Ustępstwo wobec buntowników ({tags})"},
    "turkish": {"decision_country": "{tags} kararı", "decision": "«{name}» kararı alındı ({tags})", "event": "«{name}» olayı ({tags})",
                "event_country": "{tags} olayı", "disaster": "«{name}» felaketinin sonucu",
                "rebels": "İsyancılara verilen taviz ({tags})"},
    "simp_chinese": {"decision_country": "{tags}的决议", "decision": "已执行决议「{name}」（{tags}）", "event": "事件「{name}」（{tags}）",
                     "event_country": "{tags}的事件", "disaster": "灾难「{name}」的结局",
                     "rebels": "对叛军的让步（{tags}）"},
    "japanese": {"decision_country": "{tags}の決定", "decision": "決定「{name}」を実行（{tags}）", "event": "イベント「{name}」（{tags}）",
                 "event_country": "{tags}のイベント", "disaster": "災厄「{name}」の結末",
                 "rebels": "反乱軍への譲歩（{tags}）"},
    "korean": {"decision_country": "{tags}의 결정", "decision": "결정 「{name}」 실행 ({tags})", "event": "이벤트 「{name}」 ({tags})",
               "event_country": "{tags}의 이벤트", "disaster": "재난 「{name}」의 결말",
               "rebels": "반란군에 대한 양보 ({tags})"},
}
