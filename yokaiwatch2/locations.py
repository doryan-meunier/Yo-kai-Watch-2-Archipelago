# -*- coding: utf-8 -*-
"""
Location tables for the Yo-kai Watch 2 Archipelago world (French names).

Most tables are built from game_data.py, which is generated from the
Supersoluce guide (real French quest/hideout/collection names, zones and
chapter gates). Hand-curated tables (boss, légendaires, évolutions,
coffres/objets au sol) are marked "à confirmer" where the community should
double-check against the game.

IDs derive from the category offsets (constants.py) plus the position in the
category table: APPEND-ONLY after release.
"""

from typing import Dict, List, Optional, Tuple

from BaseClasses import Location

from .constants import (
    BASE_ID,
    BOSS_OFFSET,
    CHAPTER_COMBAT_RANKS,
    CHAPTER_COUNT,
    CHAPTER_REGIONS,
    CHEST_OFFSET,
    CRIMINEL_MILESTONES,
    CRIMINEL_OFFSET,
    EVOLUTION_OFFSET,
    FUSION_OFFSET,
    GAME_NAME,
    GROUND_OFFSET,
    INSECTE_OFFSET,
    KOMASAN_OFFSET,
    LEGENDARY_OFFSET,
    LEGENDARY_YOKAI,
    EVENT_OFFSET,
    NATIVE_KEY_OFFSET,
    PLANQUE_OFFSET,
    POISSON_OFFSET,
    QUEST_OFFSET,
    RANK_OFFSET,
    STORY_OFFSET,
    TABLO_OFFSET,
    WATCH_RANKS,
    YOKAI_OFFSET,
)
from .data import AccessReq, FREE, LocationCategory, YKW2LocationData
from .items import KEY_ITEM_GAME_ORDER, NATIVE_CHEST_ITEM_BY_LOCATION
from .memory_map import CHEST_BIT_TO_LOCATION, chest_region_of, chest_zone_of
from .game_data import (
    CHAPITRES,
    FUSIONS_OBJETS,
    INSECTES,
    KOMASAN,
    MEDALLIUM,
    PLANQUES,
    POISSONS,
    REQUETES,
    SERVICES,
    TABLOS,
)


class YKW2Location(Location):
    game: str = GAME_NAME


# ===========================================================================
# Histoire - "Chapitre N : <titre>"
# ===========================================================================
STORY_LOCATIONS: Dict[str, YKW2LocationData] = {
    f"Chapitre {n} : {CHAPITRES[n]}": YKW2LocationData(
        code=BASE_ID + STORY_OFFSET + (n - 1),
        region=CHAPTER_REGIONS[n],
        category=LocationCategory.STORY,
        req=AccessReq(min_chapter=n - 1, combat_rank=CHAPTER_COMBAT_RANKS[n]),
    )
    for n in range(1, CHAPTER_COUNT + 1)
}

# ===========================================================================
# Requêtes de rang de montre (extraites des requêtes du guide)
# ===========================================================================
# rang visé -> nom de la requête ; le rang D s'obtient pendant l'histoire.
RANK_QUEST_NAMES: Dict[int, str] = {
    2: "Obtenons le rang C !",
    3: "Obtenons le rang B !",
    4: "Obtenons le rang A !",
    5: "Obtenons le rang S !",
}
_REQUETE_INFO = {name: (region, chap) for name, region, chap in REQUETES}
for _rank_quest in RANK_QUEST_NAMES.values():
    assert _rank_quest in _REQUETE_INFO, f"requête de rang absente: {_rank_quest}"

# ---------------------------------------------------------------------------
# CORRECTIONS LIVE (capture aventure 2026-07-14) — chapitre TERMINÉS réel où la
# quête est RÉALISABLE, écrasant game_data/Supersoluce qui SOUS-GATE 11 quêtes
# (risque soft-lock) : Trouvons* gd Ch5 vs réel Ch6 · rang C gd Ch4 vs Ch6 ·
# Nyada IV-VI / rang A gd Ch8 vs Ch9 · Musée gd Ch2 vs Ch5. Règle : on prend la
# valeur LIVE quand on l'a (mesurée), game_data sinon. completed = (compteur − 1).
# ---------------------------------------------------------------------------
LIVE_QUEST_CHAPTERS: Dict[str, int] = {
    "Officiellement officiel !": 2, "Les portails mystère": 2, "Bam boum ! Fusion !": 2,
    "Secrets de l'Âmechimie": 3, "Pas le temps de pêcher !": 3, "Vrai cache-cache": 3,
    "Pièce Au Phil du temps": 4, "Pièce sanctuaire": 4, "Pièce ferronnerie": 4,
    "Musée en détresse": 4,
    "Trouvons Parasolal !": 5, "Trouvons Lulutin !": 5, "Trouvons Métaureaulog !": 5,
    "Trouvons Sirénée !": 5, "Trouvons Faux Kappa !": 5, "Obtenons le rang C !": 5,
    "Le secret de Jibanyan": 6, "Sur les traces de Papa": 6, "Obtenons le rang B !": 6,
    "Épreuves de Nyada IV": 8, "Épreuves de Nyada V": 8, "Épreuves de Nyada VI": 8,
    "Obtenons le rang A !": 8,
}
# Gates additionnels captés : (combat_rank requis, (objets-clés requis...)).
# Appliqués aux quêtes NON-rang (les rangs ont déjà leur combat_rank via RANK_LOCATIONS).
LIVE_QUEST_GATES: Dict[str, Tuple[int, Tuple[str, ...]]] = {
    "Pas le temps de pêcher !": (1, ()),                 # rang D
    "Trouvons Sirénée !": (2, ()),                       # rang C
    "Épreuves de Nyada VI": (4, ()),                     # rang A
    "Musée en détresse": (0, ("Tenue de rocker",)),
    # Les gates par Cartes d'Ultramax / Bille mystérieuse / Lettre de Komasan /
    # Foli-pili / Documents perdus ont été RETIRÉS (2026-07-20) : ces objets ne
    # bloquent rien en jeu (RE au scanner) -> sortis de l'apworld, donc plus
    # utilisables comme gate (sinon ces quêtes deviendraient inatteignables).
    # Ces quêtes restent gatées par leur chapitre.
}


def _quest_chapter(name: str, gd_chap: int) -> int:
    """Chapitres TERMINÉS effectif : override live (mesuré) sinon game_data."""
    return LIVE_QUEST_CHAPTERS.get(name, gd_chap)


RANK_LOCATIONS: Dict[str, YKW2LocationData] = {
    name: YKW2LocationData(
        code=BASE_ID + RANK_OFFSET + i,
        region=_REQUETE_INFO[name][0],
        category=LocationCategory.WATCH_RANK,
        req=AccessReq(min_chapter=_quest_chapter(name, _REQUETE_INFO[name][1]),
                      combat_rank=rank - 1),
    )
    for i, (rank, name) in enumerate(sorted(RANK_QUEST_NAMES.items()))
}

# --- Montées de rang (Doteos 2026-07-26) -----------------------------------
# Un check AU MOMENT où la montre monte de rang EN JEU, EN PLUS du check de la
# requête de rang. Signal déjà en place : le client neutralise le gain natif
# (clamp au plancher AP) -> il détecte l'instant exact de la montée. D = montée
# d'HISTOIRE (fin du chapitre 2, aucune requête associée) ; C..S = fin de leur
# requête de rang (mêmes région/chapitre/rang requis que la requête).
# Codes : RANK_OFFSET+4 (D) puis +5..+8 (C..S) — la plage 50-99 est réservée.
RANK_LOCATIONS.update({
    "Montée de rang : D": YKW2LocationData(
        code=BASE_ID + RANK_OFFSET + 4,
        region=CHAPTER_REGIONS[2],
        category=LocationCategory.WATCH_RANK,
        req=AccessReq(min_chapter=1),       # pendant le chapitre 2 (histoire)
    ),
    **{
        f"Montée de rang : {WATCH_RANKS[rank]}": YKW2LocationData(
            code=BASE_ID + RANK_OFFSET + 4 + rank - 1,   # C=+5 B=+6 A=+7 S=+8
            region=_REQUETE_INFO[name][0],
            category=LocationCategory.WATCH_RANK,
            req=AccessReq(
                min_chapter=_quest_chapter(name, _REQUETE_INFO[name][1]),
                combat_rank=rank - 1),
        )
        for rank, name in sorted(RANK_QUEST_NAMES.items())
    },
})

# ===========================================================================
# Boss - "Boss : X" (noms FR du guide ; "à confirmer" = déduits)
# ===========================================================================
# Boss d'HISTOIRE — noms FR + N° Médallium VÉRIFIÉS en jeu (aventure de zéro,
# 2026-07-14, cf. scratchpad/boss_table.json). Détection : bitfield « enregistré »
# du Médallium (memory_map.MEDALLIUM_BIT_TO_LOCATION, base 0x086CFEBC, bit = N°).
# min_chapter = (chapitre capturé − 1) : le compteur STORY_CHAPTER vaut le chapitre
# COURANT, alors que min_chapter compte les chapitres TERMINÉS.
# ⚠️ Régions de Tourbœillon / Laure / Marge = « à confirmer » (le gate réel est le
# min_chapter ; la région choisie est atteignable à ce stade).
_BOSSES: List[Tuple[str, str, AccessReq]] = [
    ("Grolos",         "Les Hauts de Granval",     AccessReq(2, 0)),   # N388, fin Ch3 (école de nuit)
    ("Méganyan",       "Ourcival",                 AccessReq(3, 1)),   # N389, fin Ch4 (à Ourcival — corr. Doteos)
    ("Barbefrousse",   "San Fantastico",           AccessReq(5, 2)),   # N390, Ch6 (Grotte du littoral)
    ("Laure",          "San Fantastico",           AccessReq(5, 2)),   # N392, fin Ch6 (région à confirmer)
    ("Marge",          "San Fantastico",           AccessReq(5, 2)),   # N393, fin Ch6 (région à confirmer)
    ("Tourbœillon",    "Les Hauts de Granval",     AccessReq(6, 2)),   # N391, fin Ch7 (région à confirmer)
    ("Lady Perpétua",  "Repaire de Lady Démona",   AccessReq(9, 4)),   # N394, Ch10 (1re forme)
    ("Lady Démona",    "Repaire de Lady Démona",   AccessReq(9, 4)),   # N395, Ch10 (boss final = goal)
    # NB : Potofeu (Limbes éternelles) et Filomène (Paradis divin) NE sont PAS des
    # boss-checks ici — ce sont des ÉVÉNEMENTS de goal (regions.BOSS_EVENTS) et leur
    # N° Médallium n'est pas encore capturé (post-game). Les rajouter comme checks
    # créerait des locations non détectables. À réintégrer quand leur détection sera
    # faite en post-game.
]
BOSS_LOCATIONS: Dict[str, YKW2LocationData] = {
    f"Boss : {name}": YKW2LocationData(
        code=BASE_ID + BOSS_OFFSET + i,
        region=region,
        category=LocationCategory.BOSS,
        req=req,
    )
    for i, (name, region, req) in enumerate(_BOSSES)
}

# ===========================================================================
# Requêtes et services (données réelles du guide, via game_data.py)
# ===========================================================================
# Seuil post-game : une quête qui exige >= 10 chapitres TERMINÉS n'est dispo qu'au
# Ch11 (« Danger au vieux Granval », après la défaite de Lady Démona). DÉCISION
# Doteos (2026-07-14) : pour l'instant on NE garde QUE les quêtes d'avant le
# post-game (chap < 10). Les quêtes post-game (Nyada I-III, Retour au Yo-kai World,
# etc.) seront réintégrées avec le tag story/post-game (activation selon le goal).
POSTGAME_MIN_CHAPTERS = 10

QUEST_LOCATIONS: Dict[str, YKW2LocationData] = {}
_code = BASE_ID + QUEST_OFFSET
for _name, _region, _chap in REQUETES:
    if _name in RANK_QUEST_NAMES.values():
        continue  # portées par la catégorie WATCH_RANK
    _eff_chap = _quest_chapter(_name, _chap)   # override live si dispo
    if _eff_chap >= POSTGAME_MIN_CHAPTERS:
        continue  # post-game : exclu pour l'instant (cf. Doteos)
    _rank, _items = LIVE_QUEST_GATES.get(_name, (0, ()))
    QUEST_LOCATIONS[f"Requête : {_name}"] = YKW2LocationData(
        code=_code, region=_region, category=LocationCategory.QUEST,
        req=AccessReq(min_chapter=_eff_chap, combat_rank=_rank, items=_items))
    _code += 1
for _name, _region, _chap in SERVICES:
    if _chap >= POSTGAME_MIN_CHAPTERS:
        continue  # post-game : exclu pour l'instant
    QUEST_LOCATIONS[f"Service : {_name}"] = YKW2LocationData(
        code=_code, region=_region, category=LocationCategory.QUEST,
        req=AccessReq(min_chapter=_chap))
    _code += 1

# ===========================================================================
# Objets de fusion (page « Les objets de fusion » du guide)
# ===========================================================================
FUSION_LOCATIONS: Dict[str, YKW2LocationData] = {}
_code = BASE_ID + FUSION_OFFSET
for _nom, _empl, _region in FUSIONS_OBJETS:
    FUSION_LOCATIONS[f"Objet de fusion : {_nom}"] = YKW2LocationData(
        code=_code,
        region=_region or "Quartier des boutiques",
        category=LocationCategory.FUSION,
        req=AccessReq(min_chapter=3, combat_rank=1),
    )
    _code += 1

# ===========================================================================
# Évolutions notables (paires du Médallium ; à confirmer)
# ===========================================================================
_EVOLUTIONS: List[Tuple[str, str, AccessReq]] = [
    ("Onigirix (depuis Agonigiri)",     "Quartier des boutiques", AccessReq(3)),
    ("Samoussrai (depuis Samoumouraï)", "Les Hauts de Granval",   AccessReq(4)),
    ("Mochimacho (depuis Sumochi)",     "Coteau fleuri",          AccessReq(4)),
    ("Scarnage (depuis Scarmouche)",    "Centre-ville de Granval", AccessReq(5)),
    ("Zerberker (depuis Trépigno)",     "Ourcival",               AccessReq(5)),
]
EVOLUTION_LOCATIONS: Dict[str, YKW2LocationData] = {
    f"Évolution : {name}": YKW2LocationData(
        code=BASE_ID + EVOLUTION_OFFSET + i,
        region=region,
        category=LocationCategory.EVOLUTION,
        req=req,
    )
    for i, (name, region, req) in enumerate(_EVOLUTIONS)
}

# ===========================================================================
# Sceaux légendaires - "Sceau légendaire : X"
# ===========================================================================
# La médaille (« Médaille légendaire : X ») n'est exigée par la logique que
# lorsque legendary_shuffle est actif (voir rules.py).
_LEGENDARY_GATES: Dict[str, Tuple[str, AccessReq]] = {
    "Shogunyan":   ("Coteau fleuri",           AccessReq(6, 3)),
    "Komashura":   ("Mont Sylvestre",          AccessReq(6, 3)),
    "Gilgaros":    ("Centre-ville de Granval", AccessReq(9, 5)),
    "Elder Bloom": ("Ourcival",                AccessReq(7, 3)),
    "Spoilerina":  ("La Corniche",             AccessReq(7, 3)),
    "Dandoodle":   ("San Fantastico",          AccessReq(7, 3)),
    "Slurpent":    ("Vieux Granval",           AccessReq(8, 4)),
    "Poofessor":   ("Les Hauts de Granval",    AccessReq(8, 4)),
}
LEGENDARY_LOCATIONS: Dict[str, YKW2LocationData] = {
    f"Sceau légendaire : {yokai}": YKW2LocationData(
        code=BASE_ID + LEGENDARY_OFFSET + i,
        region=_LEGENDARY_GATES[yokai][0],
        category=LocationCategory.LEGENDARY,
        req=_LEGENDARY_GATES[yokai][1],
    )
    for i, yokai in enumerate(LEGENDARY_YOKAI)
}

def legendary_yokai_of(location_name: str) -> str:
    """'Sceau légendaire : Shogunyan' -> 'Shogunyan'."""
    return location_name.split(": ", 1)[1]

# ===========================================================================
# Amitiés Yo-kai - "Amitié : X" (noms FR du Médallium)
# ===========================================================================
# 7 Yo-kai par tribu ; régions et rangs répartis heuristiquement (à affiner
# par la communauté : la position exacte de chaque Yo-kai n'est pas dans les
# pages parsées). Rangs croissants au fil de la tribu, dernier = rang S.
_YOKAI_REGIONS = [
    "Les Hauts de Granval", "Quartier des boutiques", "Centre-ville de Granval",
    "Coteau fleuri", "La Corniche", "Mont Sylvestre", "Ourcival",
    "San Fantastico", "Vieux Granval", "Vieil Ourcival",
]
_YOKAI_SLOTS = [("E", 0), ("D", 1), ("D", 2), ("C", 3), ("B", 5), ("A", 7), ("S", 9)]

YOKAI_LOCATIONS: Dict[str, YKW2LocationData] = {}
_YOKAI_COMBAT_RANK = {"E": 0, "D": 0, "C": 1, "B": 2, "A": 3, "S": 4}
_code = BASE_ID + YOKAI_OFFSET
for _t_i, (_tribe, _names) in enumerate(MEDALLIUM.items()):
    for _s_i, (_rank, _mc) in enumerate(_YOKAI_SLOTS):
        if _s_i >= len(_names):
            continue
        _name = _names[_s_i]
        if f"Amitié : {_name}" in YOKAI_LOCATIONS:
            continue
        YOKAI_LOCATIONS[f"Amitié : {_name}"] = YKW2LocationData(
            code=_code,
            region=_YOKAI_REGIONS[(_t_i + _s_i) % len(_YOKAI_REGIONS)],
            category=LocationCategory.YOKAI,
            req=AccessReq(min_chapter=_mc, combat_rank=_YOKAI_COMBAT_RANK[_rank]),
            yokai_rank=_rank,
        )
        _code += 1

# ===========================================================================
# Coffres et objets au sol, générés par région (quantités à confirmer)
# ===========================================================================
# (région, nombre de coffres, nombre d'objets au sol)
CHEST_GROUND_COUNTS: List[Tuple[str, int, int]] = [
    # Les Hauts de Granval : 17 coffres confirmés par RE (7 violets + 10
    # jaunes), voir memory_map.CHEST_BIT_TO_LOCATION. Les autres comptes
    # restent provisoires (à confirmer zone par zone).
    ("Les Hauts de Granval",    17, 8),
    ("Quartier des boutiques",  10, 6),
    ("Centre-ville de Granval", 12, 8),
    ("Coteau fleuri",           10, 6),
    ("La Corniche",             10, 6),
    ("Tour Excellence",          6, 0),
    ("Mont Sylvestre",          10, 6),
    ("Tunnel abandonné",         6, 3),
    ("Heure funeste",            5, 0),
    ("Ourcival",                10, 6),
    ("Mont de l'Ours",           8, 4),
    ("San Fantastico",           8, 5),
    ("Vieux Granval",           12, 8),
    ("Vieil Ourcival",           8, 5),
    ("Gera Gera Land",           6, 3),
    ("Plaines Plinpot",          6, 3),
    ("Clinique du Crépuscule",   6, 3),
    ("Tunnel sans fin",          6, 0),
    ("Limbes éternelles",       10, 4),
    ("Paradis divin",            8, 3),
    ("Repaire de Lady Démona",   3, 0),
]

def _build_numbered(category: LocationCategory, offset: int,
                    label: str, index: int) -> Dict[str, YKW2LocationData]:
    """Locations numérotées par région ('<Région> - <Label> NN')."""
    table: Dict[str, YKW2LocationData] = {}
    code = BASE_ID + offset
    for region, chests, ground in CHEST_GROUND_COUNTS:
        count = chests if index == 1 else ground
        for i in range(1, count + 1):
            table[f"{region} - {label} {i:02d}"] = YKW2LocationData(
                code=code, region=region, category=category)
            code += 1
    return table

# Coffres : source de vérité = rétro-ingénierie mémoire (memory_map). Chaque
# coffre réellement mappé (bit du bitfield 0x086CFE00) devient une location, avec
# son nom RE détaillé et sa région parente (chest_region_of). Ordre d'insertion
# = ordre de CHEST_BIT_TO_LOCATION (par zone) -> IDs stables tant qu'on ajoute
# en fin de zone. (Les zones non encore mappées n'ont pas de coffres ; à
# compléter au fil de la RE.)
# Override du gate CHAPITRE par zone de coffres : certaines zones sont
# physiquement dans une région accessible tôt mais ne s'ouvrent qu'à un chapitre
# plus tardif en JEU (ex. l'école LA NUIT au Ch3). Sans ça, la logique sous-gate
# la zone et un objet critique pourrait y tomber -> soft-lock. (Complété avec
# Doteos ; par défaut la zone hérite du chapitre de sa région.)
# Override d'accès par ZONE de coffres (chapitre TERMINÉS, rang de combat) quand
# la zone exige PLUS que l'accès de sa région : école LA NUIT (Ch3), coffres
# gate rang C/D, retour tardif Ch10. Sinon la zone hérite de l'accès de sa région
# (via la connexion). (min_chapter, combat_rank) ; min_chapter = (capture) − 1.
CHEST_ZONE_ACCESS: Dict[str, Tuple[int, int]] = {
    "École élémentaire de Granval (nuit)":  (3, 0),   # école la nuit (Ch3)
    "Manoir (Coteau fleuri)":               (2, 1),   # Ch3 + rang D
    "San Fantastico (rang C)":              (5, 2),   # Ch6 + rang C (coffre 1287)
    "Grotte du littoral":                   (5, 2),   # Ch6 + rang C
    "Coteau fleuri (rang C)":               (5, 2),   # Ch6 + rang C
    "Vieux Hauts de Granval (retour Ch10)": (9, 0),   # retour tardif Ch10
    # Zone des portails (Doteos 2026-07-27) : accès depuis La Corniche une fois la
    # quête « Les portails mystère » terminée (chapitre 2 dans LIVE_QUEST_CHAPTERS).
    # ⚠️ En jeu il faut AUSSI des GLOBES DE PORTAIL (10 pour le coffre 01) : coût
    # NON modélisable en V1 (consommable hors pool) -> prévu pour la V2.
    "Zone des portails":                    (2, 0),   # quête Les portails mystère
    # Tour du commerce (Centre-ville) : chapitre 4 + rang C ; le coffre isolé
    # du 3e étage exige le rang A (capture Doteos 2026-07-16).
    "Tour du commerce (3e étage)":          (3, 2),   # Ch4 + rang C
    "Tour du commerce (3e étage, rang A)":  (3, 4),   # Ch4 + rang A
    "Tour du commerce (12e étage)":         (3, 2),   # Ch4 + rang C
    # 3e élément optionnel = items requis (portes à clé).
    "Quartier des boutiques (appartement C-303)":
        (0, 0, ("Clé appartement C-303",)),
    "Manoir arrière (Coteau fleuri)":
        (0, 0, ("Clé de derrière",)),
    # Corniche > Musée (nuit) : accès via Télémire (débloqué Ch4 Ourcival) -> exige
    # Indications de Maman + Ch4 (Doteos 2026-07-24).
    "Corniche (Musée)":
        (3, 0, ("Indications de Maman",)),
    # Mont Sylvestre > Tunnel abandonné (salle du trésor) : accès via la quête
    # « Chasseurs de trésors 2 » (Ch6) (Doteos 2026-07-24).
    "Tunnel abandonné (salle du trésor)":
        (5, 0),
    # Mont Sylvestre > Tunnel abandonné EST : accès via « Chasseurs de trésors 3 »
    # (Ch8, après le Tablo Draconfus) (Doteos 2026-07-24).
    "Tunnel abandonné est":
        (7, 0),
    # Chapitre = celui qui débloque le Coteau fleuri (le rang B vient des
    # items AP, plus d'attache de chapitre — correction Doteos).
    "Coteau fleuri (rang B)":               (2, 3),   # accès quartier + rang B
    # Égouts + Allée sinistre : dans Les Hauts, mais ouverts par la « Pile ou
    # passe » vers la fin du chapitre 2 (Doteos 2026-07-17).
    "Égouts":                               (0, 0, ("Pile ou passe",)),
    "Allée sinistre":                       (0, 0, ("Pile ou passe",)),
    "Ruelle obscure":                       (0, 0, ("Pile ou passe",)),
    "Canal isolé":                          (0, 2, ("Pile ou passe",)),  # + rang C
    "Mont Sylvestre (accès égouts)":        (0, 2, ("Pile ou passe",)),  # égouts + rang C
}
# ACCÈS PAR COFFRE des égouts (RE Doteos 2026-07-21) : chaque coffre est ENTRÉ
# depuis un quartier DIFFÉRENT -> gaté par le chapitre (+ objet) de CE quartier,
# EN PLUS de la « Pile ou passe » (pour être dans les égouts). Sans ça, tous les
# coffres étaient traités comme accessibles dès Les Hauts -> soft-lock (ex. les
# Clés de l'école placées au Coffre 08 = Centre-ville, atteignable bien plus tard).
# Numéro de coffre -> (min_chapter, combat_rank, items). Chapitres = DISTRICT_CHAPTERS.
_POP = ("Pile ou passe",)
EGOUTS_COFFRE_ACCESS: Dict[int, Tuple] = {
    1:  (0, 0, _POP), 2: (0, 0, _POP),   # Passage des matous (Les Hauts, Ch0)
    3:  (0, 0, _POP),                    # entrée B (Les Hauts)
    4:  (0, 0, _POP), 5: (0, 0, _POP),   # Ruelle obscure (Les Hauts)
    6:  (1, 0, _POP), 7: (1, 0, _POP),   # La Corniche (Ch2 -> min_chapter 1)
    8:  (3, 0, _POP + ("Indications de Maman",)),  # Centre-ville (Ch4 + Indications)
    9:  (3, 0, _POP + ("Indications de Maman",)),
    10: (2, 0, _POP), 11: (2, 0, _POP),  # Quartier des boutiques (Ch3 -> 2)
    12: (2, 0, _POP), 13: (2, 0, _POP),  # Coteau fleuri (Ch3 -> 2)
}


def _egouts_num(cname: str) -> Optional[int]:
    """Numéro de coffre pour 'Égouts - Coffre NN' (sinon None)."""
    if chest_zone_of(cname) != "Égouts":
        return None
    try:
        return int(cname.rsplit("Coffre", 1)[1].strip())
    except (IndexError, ValueError):
        return None


CHEST_LOCATIONS: Dict[str, YKW2LocationData] = {}
_code = BASE_ID + CHEST_OFFSET
for _bit, _cname in CHEST_BIT_TO_LOCATION.items():
    _en = _egouts_num(_cname)
    _acc = EGOUTS_COFFRE_ACCESS.get(_en) if _en is not None \
        else CHEST_ZONE_ACCESS.get(chest_zone_of(_cname))
    CHEST_LOCATIONS[_cname] = YKW2LocationData(
        code=_code, region=chest_region_of(_cname),
        category=LocationCategory.CHEST,
        req=AccessReq(min_chapter=_acc[0], combat_rank=_acc[1],
                      items=_acc[2] if len(_acc) > 2 else ())
        if _acc else FREE)
    _code += 1

# Objets au sol : encore sur des comptes provisoires (pas de RE mémoire dédiée).
GROUND_LOCATIONS = _build_numbered(LocationCategory.GROUND, GROUND_OFFSET,
                                   "Objet au sol", 2)

# ===========================================================================
# Planques Yo-kai (52, guide) - "Planque : X"
# ===========================================================================
PLANQUE_LOCATIONS: Dict[str, YKW2LocationData] = {}
_code = BASE_ID + PLANQUE_OFFSET
for _num, _nom, _region in PLANQUES:
    PLANQUE_LOCATIONS[f"Planque : {_nom}"] = YKW2LocationData(
        code=_code, region=_region, category=LocationCategory.PLANQUE,
        req=AccessReq(min_chapter=min(9, 1 + (_num - 1) // 6)))
    _code += 1

# ===========================================================================
# Tablo-blabla (26, guide) - "Tablo-blabla n°NN : <réponse>"
# ===========================================================================
TABLO_LOCATIONS: Dict[str, YKW2LocationData] = {
    f"Tablo-blabla n°{num:02d} : {reponse}": YKW2LocationData(
        code=BASE_ID + TABLO_OFFSET + i,
        region=region,
        category=LocationCategory.TABLO,
        req=AccessReq(min_chapter=min(9, 1 + (num - 1) // 5)),
    )
    for i, (num, region, _empl, reponse) in enumerate(TABLOS)
}

# ===========================================================================
# Les aventures de Komasan (9 rencontres, guide)
# ===========================================================================
_KOMASAN_CHAPTERS = [1, 1, 2, 2, 3, 3, 4, 4, 5]
KOMASAN_LOCATIONS: Dict[str, YKW2LocationData] = {
    f"Komasan : rencontre {num}": YKW2LocationData(
        code=BASE_ID + KOMASAN_OFFSET + i,
        region=region,
        category=LocationCategory.KOMASAN,
        req=AccessReq(min_chapter=_KOMASAN_CHAPTERS[i]),
    )
    for i, (num, region) in enumerate(KOMASAN)
}

# ===========================================================================
# Yo-criminels : paliers de captures (application remise au chapitre 3)
# ===========================================================================
_CRIMINEL_CHAPTERS = [2, 3, 4, 6, 8]
CRIMINEL_LOCATIONS: Dict[str, YKW2LocationData] = {
    (f"Yo-criminels : {n} capture" + ("s" if n > 1 else "")): YKW2LocationData(
        code=BASE_ID + CRIMINEL_OFFSET + i,
        region="Les Hauts de Granval",
        category=LocationCategory.CRIMINEL,
        req=AccessReq(min_chapter=_CRIMINEL_CHAPTERS[i]),
    )
    for i, n in enumerate(CRIMINEL_MILESTONES)
}

# ===========================================================================
# Collections (guide) : insectes (Filet à insectes) et poissons (Canne à pêche)
# ===========================================================================
def _build_collection(entries, offset: int, prefix: str, tool: Optional[str],
                      category: LocationCategory) -> Dict[str, YKW2LocationData]:
    table: Dict[str, YKW2LocationData] = {}
    code = BASE_ID + offset
    for name, region in entries:
        key = f"{prefix} : {name}"
        if key in table:  # même espèce dans plusieurs zones
            key = f"{prefix} : {name} ({region})"
            if key in table:
                continue
        # tool=None (Filet retiré, toujours natif) -> gate par la région seule.
        table[key] = YKW2LocationData(
            code=code, region=region, category=category,
            req=AccessReq(items=(tool,)) if tool else FREE)
        code += 1
    return table

# Insectes : le Filet est TOUJOURS natif (retiré du pool) -> pas de gate objet,
# seulement la région (tool=None).
INSECTE_LOCATIONS = _build_collection(
    INSECTES, INSECTE_OFFSET, "Insecte", None,
    LocationCategory.INSECTE)
POISSON_LOCATIONS = _build_collection(
    POISSONS, POISSON_OFFSET, "Poisson", "Canne à pêche",
    LocationCategory.POISSON)

# ===========================================================================
# Spots natifs des objets-clés (shuffle dur) - "Objet-clé : X"
# ===========================================================================
# Chaque objet-clé RÉEL (KEY_ITEM_GAME_ORDER) a un check représentant le moment
# où l'histoire te le donnait nativement. Le client déclenche ce check quand il
# détecte le don natif (même détection que la neutralisation). Région "Menu"
# (toujours atteignable en logique) + marquées EXCLUDED dans __init__ -> ne
# reçoivent QUE du filler -> pas besoin de connaître le chapitre exact de chaque
# objet, aucun risque de soft-lock. Actives seulement si key_item_shuffle (cf.
# get_active_location_data). Ordre = KEY_ITEM_GAME_ORDER (append-only).
# (Les beignets ET le Filet ont été RETIRÉS entièrement — toujours natifs, ni items
# ni checks AP ; il n'y a donc plus de check « Objet-clé : Beignets/Filet ».)

# Objets-clés dont l'ACQUISITION en jeu EST un coffre (ils figurent comme contenu
# natif d'un coffre) : leur check « Objet-clé : X » ferait DOUBLON avec le check du
# coffre -> on le SUPPRIME (décision Doteos 2026-07-19 : « si les item clé sont dans
# des coffre pas besoin du check des item clé puisque l'on a celui du coffre »).
# L'ITEM reste au pool (gating/livraison). Détecté auto (coffres ∩ objets-clés) :
# couvre tout futur cas sans liste à maintenir. Ex. : Jolie petite/grande clé,
# Tenue de rocker, Clés appart C-101/C-303/B-301.
_CHEST_ACQUIRED_KEY_ITEMS: set = (
    set(NATIVE_CHEST_ITEM_BY_LOCATION.values()) & set(KEY_ITEM_GAME_ORDER))


def native_key_check_name(item_name: str) -> Optional[str]:
    """Nom du check natif « Objet-clé : … » représentant le don en jeu d'un
    objet-clé, ou None s'il n'y a PAS de check (objet obtenu via un coffre ->
    doublon supprimé, cf. _CHEST_ACQUIRED_KEY_ITEMS)."""
    if item_name in _CHEST_ACQUIRED_KEY_ITEMS:
        return None
    return "Objet-clé : " + item_name


# Code = index dans KEY_ITEM_GAME_ORDER (append-only, IDs stables).
KEY_ITEM_NATIVE_LOCATIONS: Dict[str, YKW2LocationData] = {}
for i, name in enumerate(KEY_ITEM_GAME_ORDER):
    _loc_name = native_key_check_name(name)
    if _loc_name is None:
        continue  # objet obtenu via coffre -> pas de check objet-clé (doublon)
    KEY_ITEM_NATIVE_LOCATIONS[_loc_name] = YKW2LocationData(
        code=BASE_ID + NATIVE_KEY_OFFSET + i,
        region="Menu",
        category=LocationCategory.NATIVE_KEY,
        req=FREE,
    )

# ===========================================================================
# Tables agrégées
# ===========================================================================
# ===========================================================================
# Events d'histoire détectés par FLAG mémoire - "check d'événement"
# ===========================================================================
# Certains moments ne correspondent à AUCUN objet gardable : on les détecte par
# un flag posé en mémoire quand le joueur FAIT l'événement (memory_map.
# EVENT_CHECK_FLAGS). Ex. le choix des beignets du Ch4 : le bit est commun aux
# DEUX beignets (vérifié en jeu en testant les deux choix), donc le check part
# quel que soit le beignet choisi -> jamais manquable.
EVENT_LOCATIONS: Dict[str, YKW2LocationData] = {
    # (« Beignets du chapitre 4 » RETIRÉ le 2026-07-26 : scène scénaristique linéaire
    #  non gateable proprement — aucun bit de capacité ne la verrouille, seul le
    #  compteur de pas partagé bouge. Décision Doteos : ni check ni gate. Le code
    #  EVENT_OFFSET+0 est donc libre.)
    # Récupération du VÉLO : spot dédié pendant « Sur les traces de Papa » (Ch6),
    # SÉPARÉ de la récompense de fin de quête (Doteos 2026-07-22). Détecté par le
    # flag « peut faire du vélo » (0x086CFAB9 b0). Coteau fleuri (405,417).
    "Objet-clé : Vélo": YKW2LocationData(
        code=BASE_ID + EVENT_OFFSET + 1,
        region="Coteau fleuri",
        category=LocationCategory.EVENT,
        req=AccessReq(5),          # « Sur les traces de Papa » = Ch6
    ),
    # Boss OPTIONNEL Didgeai : fin de la quête « Chasse nocturne » (manoir hanté,
    # Coteau fleuri, nuit, Ch5). Exige les 3 clés du manoir. Détecté par le flag de
    # défaite 0x086CFFC9 b5 (RE 2026-07-24, miroir 0x086D0019 b5 confirme). (Doteos)
    "Boss : Didgeai": YKW2LocationData(
        code=BASE_ID + EVENT_OFFSET + 2,
        region="Coteau fleuri",
        category=LocationCategory.EVENT,
        req=AccessReq(4, 0, ("Jolie petite clé", "Jolie grande clé",
                             "Clé de derrière")),
    ),
    # Boss OPTIONNEL Sabroclair : fin de la quête « Une armure sinistre » (Ch7 « La
    # grande bataille Yo-kai », nuit, musée du lac des Coloquintes ; requiert « Les
    # portails mystère »). Détecté par le bit Médallium N°404 (0x086CFEEE b4, Doteos
    # 2026-07-24). Mappé à La Corniche (388,846) au choix de Doteos.
    "Boss : Sabroclair": YKW2LocationData(
        code=BASE_ID + EVENT_OFFSET + 3,
        region="La Corniche",
        category=LocationCategory.EVENT,
        req=AccessReq(6),          # Ch7
    ),
    # Boss OPTIONNEL Ombraptor : fin de la quête « Le géant fantôme » (Ch10 « Maître
    # Nyada le défi », centre sportif du Centre-ville). Médallium N°402 (0x086CFEEE b2).
    # Doteos 2026-07-24 -> Centre-ville (208,491).
    "Boss : Ombraptor": YKW2LocationData(
        code=BASE_ID + EVENT_OFFSET + 4,
        region="Centre-ville de Granval",
        category=LocationCategory.EVENT,
        req=AccessReq(9),          # Ch10
    ),
    # Boss OPTIONNEL Inamygal : fin de la quête « Ectoplasmes à l'école » (Ch6, école
    # élémentaire de Granval / Les Hauts, nuit). Médallium N°406 (0x086CFEEE b6).
    # Doteos 2026-07-24 -> école (793,441).
    "Boss : Inamygal": YKW2LocationData(
        code=BASE_ID + EVENT_OFFSET + 5,
        region="Les Hauts de Granval",
        category=LocationCategory.EVENT,
        req=AccessReq(5),          # Ch6 (min_chapter du tuple « Ectoplasmes »)
    ),
    # Boss OPTIONNEL Volteface : fin de « Chasseurs de trésors 2 » (tunnel abandonné,
    # Mont Sylvestre). Exige la « Clé salle du trésor ». Médallium N°412 (0x086CFEEF
    # b4). Doteos 2026-07-24 -> Mont Sylvestre (172,85).
    "Boss : Volteface": YKW2LocationData(
        code=BASE_ID + EVENT_OFFSET + 6,
        region="Mont Sylvestre",
        category=LocationCategory.EVENT,
        req=AccessReq(5, 0, ("Clé salle du trésor",)),
    ),
    # Misterre (Yo-kai amicable, fin « Chasseurs de trésors 3 », tunnel abandonné est,
    # Ch8). Exige Huile de Tendino (levier -> Tablo Robonyan -> Misterre). Médallium
    # N°119 (0x086CFECA b7). Doteos 2026-07-24 -> Mont Sylvestre (235,192).
    "Boss : Misterre": YKW2LocationData(
        code=BASE_ID + EVENT_OFFSET + 7,
        region="Mont Sylvestre",
        category=LocationCategory.EVENT,
        req=AccessReq(7, 0, ("Huile de Tendino",)),
    ),
    # Boss Firmain : quête « La clinique hantée » (Ch8, Clinique du Crépuscule, Quartier
    # des boutiques). Exige la Poignée étrange. Médallium N°415 (0x086CFEEF b7). Doteos
    # 2026-07-24 -> fusionné sur le repère clinique.
    "Boss : Firmain": YKW2LocationData(
        code=BASE_ID + EVENT_OFFSET + 8,
        region="Quartier des boutiques",
        category=LocationCategory.EVENT,
        req=AccessReq(7, 0, ("Poignée étrange",)),
    ),
    # Boss Démophage : quête « Épreuves de Nyada VI » (Ch8, Vieil Ourcival). Médallium
    # N°38 (0x086CFEC0 b6, RE Doteos 2026-07-25). Tracker (227,85).
    "Boss : Démophage": YKW2LocationData(
        code=BASE_ID + EVENT_OFFSET + 9,
        region="Vieil Ourcival",
        category=LocationCategory.EVENT,
        req=AccessReq(7),          # Ch8
    ),
    # Boss Injustin : Ch9, Vieux Granval. Médallium N°355 (0x086CFEE8 b3, RE Doteos
    # 2026-07-25). Tracker (100,367).
    "Boss : Injustin": YKW2LocationData(
        code=BASE_ID + EVENT_OFFSET + 10,
        region="Vieux Granval",
        category=LocationCategory.EVENT,
        req=AccessReq(8),          # Ch9
    ),
    # Boss d'aventure Fielippine : Ch9, Vieux Granval. Médallium N°356 (0x086CFEE8 b4,
    # RE Doteos 2026-07-25). Tracker (409,253).
    "Boss : Fielippine": YKW2LocationData(
        code=BASE_ID + EVENT_OFFSET + 11,
        region="Vieux Granval",
        category=LocationCategory.EVENT,
        req=AccessReq(8),          # Ch9
    ),
    # Boss d'aventure Cyrustre : Ch9, Vieux Granval. Médallium N°357 (0x086CFEE8 b5,
    # RE Doteos 2026-07-25). Tracker (633,292).
    "Boss : Cyrustre": YKW2LocationData(
        code=BASE_ID + EVENT_OFFSET + 12,
        region="Vieux Granval",
        category=LocationCategory.EVENT,
        req=AccessReq(8),          # Ch9
    ),
    # Boss d'aventure Maudicko : Ch9, Vieux Granval. Médallium N°358 (0x086CFEE8 b6,
    # RE Doteos 2026-07-25). Tracker (345,399).
    "Boss : Maudicko": YKW2LocationData(
        code=BASE_ID + EVENT_OFFSET + 13,
        region="Vieux Granval",
        category=LocationCategory.EVENT,
        req=AccessReq(8),          # Ch9
    ),
    # Boss d'aventure Ronéan : Ch9, Vieux Granval. Médallium N°359 (0x086CFEE8 b7,
    # RE Doteos 2026-07-25). Tracker (473,418).
    "Boss : Ronéan": YKW2LocationData(
        code=BASE_ID + EVENT_OFFSET + 14,
        region="Vieux Granval",
        category=LocationCategory.EVENT,
        req=AccessReq(8),          # Ch9
    ),
    # Boss Crocho : quête « Les sources de l'amitié » (Ch7, Coteau fleuri, sources).
    # Médallium N°398 (0x086CFEED b6). Doteos 2026-07-25 -> même repère que Tablo Ronimpec.
    "Boss : Crocho": YKW2LocationData(
        code=BASE_ID + EVENT_OFFSET + 15,
        region="Coteau fleuri",
        category=LocationCategory.EVENT,
        req=AccessReq(6),          # Ch7
    ),
    # Boss Tromplœil (Doteos 2026-07-27) : boss de la ZONE DES PORTAILS, accès
    # depuis La Corniche après la quête « Les portails mystère ». Médallium N°416
    # (0x086CFEBC + 416//8 = 0x086CFEF0, bit 416%8 = b0).
    # ⚠️ Il faut 100 GLOBES DE PORTAIL en jeu — coût NON modélisable en V1
    # (consommable hors pool) ; prévu pour la V2 (globes dans le pool).
    "Boss : Tromplœil": YKW2LocationData(
        code=BASE_ID + EVENT_OFFSET + 16,
        region="La Corniche",
        category=LocationCategory.EVENT,
        req=AccessReq(2),          # quête Les portails mystère (= zone portails)
    ),
}


ALL_LOCATIONS: Dict[str, YKW2LocationData] = {
    **STORY_LOCATIONS,
    **RANK_LOCATIONS,
    **BOSS_LOCATIONS,
    **QUEST_LOCATIONS,
    **FUSION_LOCATIONS,
    **EVOLUTION_LOCATIONS,
    **LEGENDARY_LOCATIONS,
    **YOKAI_LOCATIONS,
    **CHEST_LOCATIONS,
    **GROUND_LOCATIONS,
    **PLANQUE_LOCATIONS,
    **TABLO_LOCATIONS,
    **KOMASAN_LOCATIONS,
    **CRIMINEL_LOCATIONS,
    **INSECTE_LOCATIONS,
    **POISSON_LOCATIONS,
    **KEY_ITEM_NATIVE_LOCATIONS,
    **EVENT_LOCATIONS,
}

LOCATION_NAME_TO_ID: Dict[str, int] = {
    name: data.code for name, data in ALL_LOCATIONS.items()
    if data.code is not None
}

# Garde-fous : IDs uniques, pas de collision de noms entre catégories.
assert len(set(LOCATION_NAME_TO_ID.values())) == len(LOCATION_NAME_TO_ID), \
    "duplicate location IDs detected"
_expected = (len(STORY_LOCATIONS) + len(RANK_LOCATIONS) + len(BOSS_LOCATIONS)
             + len(QUEST_LOCATIONS) + len(FUSION_LOCATIONS)
             + len(EVOLUTION_LOCATIONS) + len(LEGENDARY_LOCATIONS)
             + len(YOKAI_LOCATIONS) + len(CHEST_LOCATIONS)
             + len(GROUND_LOCATIONS) + len(PLANQUE_LOCATIONS)
             + len(TABLO_LOCATIONS) + len(KOMASAN_LOCATIONS)
             + len(CRIMINEL_LOCATIONS) + len(INSECTE_LOCATIONS)
             + len(POISSON_LOCATIONS) + len(KEY_ITEM_NATIVE_LOCATIONS)
             + len(EVENT_LOCATIONS))
assert len(ALL_LOCATIONS) == _expected, "location name collision across categories"

# Groupes d'indices : un par catégorie plus un par région.
LOCATION_GROUPS: Dict[str, set] = {
    "Histoire": set(STORY_LOCATIONS),
    "Rangs de montre": set(RANK_LOCATIONS),
    "Boss": set(BOSS_LOCATIONS),
    "Requêtes et services": set(QUEST_LOCATIONS),
    "Objets de fusion": set(FUSION_LOCATIONS),
    "Évolutions": set(EVOLUTION_LOCATIONS),
    "Sceaux légendaires": set(LEGENDARY_LOCATIONS),
    "Amitiés Yo-kai": set(YOKAI_LOCATIONS),
    "Coffres": set(CHEST_LOCATIONS),
    "Objets au sol": set(GROUND_LOCATIONS),
    "Planques": set(PLANQUE_LOCATIONS),
    "Tablo-blabla": set(TABLO_LOCATIONS),
    "Komasan": set(KOMASAN_LOCATIONS),
    "Yo-criminels": set(CRIMINEL_LOCATIONS),
    "Insectes": set(INSECTE_LOCATIONS),
    "Poissons": set(POISSON_LOCATIONS),
    "Objets-clés (spots natifs)": set(KEY_ITEM_NATIVE_LOCATIONS),
}
for _name, _data in ALL_LOCATIONS.items():
    LOCATION_GROUPS.setdefault(_data.region, set()).add(_name)
