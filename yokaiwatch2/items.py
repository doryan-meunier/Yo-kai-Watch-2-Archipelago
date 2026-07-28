# -*- coding: utf-8 -*-
"""
Item tables for the Yo-kai Watch 2 Archipelago world (French names).

The full item list lives in ALL_ITEMS. IDs are assigned from the order of
insertion, so the table is APPEND-ONLY after release (see constants.py).

Progression overview (see rules.py):
  * Vélo / Vélo (progressif)            -> La Corniche et déplacements
  * Rang de Yo-kai Watch                -> portes de combat, examens, donjons
  * Chapitre d'histoire (progressif)    -> portes de chapitres (story_shuffle)
  * Billets, tickets et clés            -> accès aux régions
  * Outils (Canne à pêche, Filet...)    -> collections et requêtes dédiées
  * Médailles légendaires               -> sceaux légendaires (legendary_shuffle)
"""

import json
import pkgutil
from typing import Dict, List, Tuple

from BaseClasses import Item, ItemClassification

from .constants import (
    BASE_ID,
    DISTRICTS,
    GAME_NAME,
    LEGENDARY_YOKAI,
    PROGRESSIVE_CHAPTER_ITEM,
    PROGRESSIVE_RANK_ITEM,
    RANK_ITEM_NAMES,
    district_pass_name,
    legendary_medal_name,
)
from .data import YKW2ItemData


class YKW2Item(Item):
    game: str = GAME_NAME


# ---------------------------------------------------------------------------
# Item table (APPEND-ONLY after release).
# ---------------------------------------------------------------------------
ALL_ITEMS: Dict[str, YKW2ItemData] = {}
_next_code = BASE_ID


def _add(name: str, classification: ItemClassification, category: str,
         count: int = 0) -> None:
    global _next_code
    assert name not in ALL_ITEMS, f"duplicate item name: {name}"
    ALL_ITEMS[name] = YKW2ItemData(_next_code, classification, category, count)
    _next_code += 1


_P = ItemClassification.progression
_U = ItemClassification.useful
_F = ItemClassification.filler
_T = ItemClassification.trap

# --- Transport ---------------------------------------------------------------
_add("Vélo", _P, "transport", 1)                # progressive_bicycle désactivé
_add("Vélo (progressif)", _P, "transport", 2)   # progressive_bicycle activé
_add("Sonnette de vélo", _U, "transport", 1)

# --- Rangs de Yo-kai Watch ----------------------------------------------------
_add(PROGRESSIVE_RANK_ITEM, _P, "watch_rank", 5)
for _rank in range(1, 6):
    _add(RANK_ITEM_NAMES[_rank], _P, "watch_rank", 1)

# --- Histoire -----------------------------------------------------------------
# Dans le pool uniquement avec story_shuffle (10 objets ouvrent les
# chapitres 2 à 11 ; le chapitre 1 est toujours ouvert).
_add(PROGRESSIVE_CHAPTER_ITEM, _P, "story", 10)

# --- Clés (accès aux régions) ---------------------------------------------------
# NB : les billets/tickets de train (Ourcival, San Fantastico, passé « rétro »)
# s'achètent nativement en jeu -> aucun objet-clé de gating (accès par chapitre).
_add("Clé du tunnel abandonné", _P, "key", 1)   # tunnels Est/Ouest du Mont Sylvestre
_add("Clé de cabane", _P, "key", 1)             # Limbes éternelles (source : Mme Roch)
_add("Clé du Paradis divin", _P, "key", 1)      # donjon de Spectres Psychiques

# --- Outils / aptitudes ---------------------------------------------------------
# Les OUTILS (Filet, Canne, Modèle zéro) sont désormais de VRAIS gates : leur
# capacité est verrouillée en mémoire tant que l'objet AP n'est pas reçu
# (memory_map.STORY_GATES, bits vérifiés en jeu). Ils viennent tous du registre
# data/important_key_items.json -> pas de _add explicite ici (sinon doublon).
# (« Yo-kai Watch Modèle Zéro » retiré : doublon legacy du vrai objet « Modèle zéro ».)

# --- Médailles légendaires -------------------------------------------------------
for _yokai in LEGENDARY_YOKAI:
    _add(legendary_medal_name(_yokai), _P, "legendary_medal", 1)

# --- Passes de quartier (option starting_region ; jamais dans le pool) -----------
for _district in DISTRICTS:
    _add(district_pass_name(_district), _P, "district_pass", 0)

# --- Utiles (VRAIS objets du jeu, noms exacts -> hash direct, cf. ITEM_GAME_HASH) -
_add("EXPorbe moyen", _U, "useful", 6)
_add("Grand EXPorbe", _U, "useful", 4)
_add("Staminum Alpha", _U, "useful", 6)
_add("Remède puiss.", _U, "useful", 6)

# --- Remplissage (VRAIS consommables du jeu ; quantités gérées dynamiquement) -----
_add("Riz à la prune", _F, "filler")
_add("Thé de l'âme", _F, "filler")
_add("Hamburger", _F, "filler")
_add("Y-Cola", _F, "filler")
_add("Riz à la crevette", _F, "filler")
_add("Remède amer", _F, "filler")
_add("Mini EXPorbe", _F, "filler")
_add("Petit EXPorbe", _F, "filler")

# --- Pièges ------------------------------------------------------------------------
_add("Piège : porte-monnaie percé", _T, "trap")  # perte d'argent
_add("Piège : envoûtement", _T, "trap")          # altération d'état temporaire
_add("Piège : embuscade", _T, "trap")            # combat forcé
_add("Piège : objet factice", _T, "trap")        # faux objet

# --- Objets importants du jeu (RE 2026-07-12, décision Doteos) ---------------
# Les 124 VRAIS objets importants du jeu (catégorie item_config 0x3c, dédup par
# nom) : montres, outils, vélos, tickets/pass de zone, clés, + objets de quête/
# collection. Ajoutés au pool (shufflés), livrés dans la liste d'objets-clés et
# retirés en natif (shuffle DUR). Data-driven : data/important_key_items.json.
# Catégorie "important" -> incluse dans SHUFFLABLE_KEY_ITEMS. Skippe ceux déjà
# définis (Filet, Canne, Clé de cabane).
_IMPORTANT_KEY_ITEMS = json.loads(pkgutil.get_data(
    __package__, "data/important_key_items.json").decode("utf-8"))
# Objets-clés CRITIQUES pour la progression (classification Doteos, RE 2026-07-12)
# : chapitre où l'objet devient NÉCESSAIRE. Ils sont PROGRESSION (_P) pour que le
# fill garantisse leur atteignabilité AVANT ce chapitre (cf. rules.has_chapter,
# actif si key_item_shuffle). Les autres importants sont USEFUL (placement libre).
# Objets-clés REQUIRED captés dans l'aventure (Ch1-7, scratchpad/keyitem_capture.json,
# 2026-07-14). Clé = chapitre où l'objet est NÉCESSAIRE pour progresser (has_chapter
# l'exige). REFONTE 2026-07-20 (RE des gates au scanner) : seuls les objets dont on a
# PROUVÉ le blocage en jeu restent dans l'apworld. Les objets Ch5-7 d'origine (Bille
# mystérieuse, Lettre de Komasan, Foli-pili, Cartes d'Ultramax, Documents perdus) +
# Montre de luxe / Capsule de lait / Grelot de félin ne bloquent RIEN (vérifié) ->
# RETIRÉS. Cf. memory_map.STORY_GATES pour les objets à hard-gate (bits/compteur).
CRITICAL_KEY_ITEMS_BY_CHAPTER: Dict[int, Tuple[str, ...]] = {
    # Filet requis DÈS Ch1 (Doteos 2026-07-21 : bloque la progression au tout début
    # -> le fill DOIT le placer en sphère 0 : son check natif ou un check précoce
    # d'un autre joueur). Son check natif est dé-EXCLU (cf. regions.py) pour être
    # plaçable en solo.
    1: ("Filet à insectes",),
    2: ("Pile ou passe",),
    3: ("Clés de l'école", "Herbe ancestrale", "Super tournevis"),
    4: ("Canne à pêche",),
}
_CRITICAL_NAMES = {n for _ns in CRITICAL_KEY_ITEMS_BY_CHAPTER.values() for n in _ns}
# Objets NON critiques pour l'histoire mais utilisés comme GATE d'une quête
# optionnelle (cf. locations.LIVE_QUEST_GATES) -> PROGRESSION, pour que le fill
# garantisse leur atteignabilité avant la quête gatée.
_GATE_ITEMS = {"Tenue de rocker",
               # Clés qui GATENT des coffres (CHEST_ZONE_ACCESS) -> progression
               # pour que le fill garantisse leur atteignabilité (Doteos 2026-07-19).
               "Clé de derrière",            # Manoir arrière (Coteau fleuri)
               # Clés du manoir requises par le boss « Boss : Didgeai » (Doteos
               # 2026-07-24) -> progression sinon Didgeai inaccessible.
               "Jolie petite clé", "Jolie grande clé",
               # Clé salle du trésor requise par « Boss : Volteface » (Doteos
               # 2026-07-24) -> progression sinon Volteface inaccessible.
               "Clé salle du trésor",
               # Huile de Tendino requise par « Boss : Misterre » (Doteos 2026-07-24)
               # -> progression sinon Misterre inaccessible.
               "Huile de Tendino",
               # Poignée étrange requise par « Boss : Firmain » (Doteos 2026-07-24)
               # -> progression sinon Firmain inaccessible.
               "Poignée étrange",
               "Clé appartement C-303",      # Quartier des boutiques (C-303)
               # HARD-GATES mémoire (memory_map.STORY_GATES) : ces objets verrouillent
               # une capacité/zone RÉELLE en jeu -> progression obligatoire, sinon le
               # fill pourrait les rendre inatteignables (Doteos 2026-07-20).
               "Filet à insectes",           # capacité attraper insectes
               "Modèle zéro",                # fonctions de combat de la montre
               "Indications de Maman"}       # débloque Centre-ville + train
for _iki in _IMPORTANT_KEY_ITEMS:
    if _iki["name"] not in ALL_ITEMS:
        _add(_iki["name"],
             _P if _iki["name"] in _CRITICAL_NAMES or _iki["name"] in _GATE_ITEMS
             else _U, "important", 1)

# ---------------------------------------------------------------------------
# POOL v1 (demande Doteos 2026-07-15) : objets-clés de combat Yo-kai (1x/jour)
# + pièces YKW2. 1 de chaque dans le pool. Hash via data/item_hashes.json.
# ---------------------------------------------------------------------------
# Objets-clés « combat Yo-kai 1x/jour » (graines/grelots/rouages/Marque) : invoquent
# un Yo-kai à combattre. Livrés dans la liste d'objets-clés ; PAS de check natif.
COMBAT_YOKAI_HASHES: Dict[str, int] = {
    "Marque d'Ultramax": 0xF2A2F16F,
    "Graines d'orange": 0xA7CA4F95, "Graines de fraise": 0x20B5EB77,
    "Graines de kiwi": 0x37755204, "Graines de melon": 0xD0CD7F03,
    "Graines de pastèque": 0x57B2DBE1, "Graines de raisin": 0x40726292,
    "Grelot aérien": 0xE596D998, "Grelot de série F": 0x2E6E6345,
    "Grelot gris": 0x7BF24C3B, "Grelot marin": 0x596953D3,
    "Grelot masqué": 0x0B98B8B4, "Grelot voyageur": 0x7C9F8822,
    "Rouage de Corniot": 0x50DF1FF8, "Rouage de Dracounet": 0xBED17ED4,
    "Rouage de Granpapéti": 0x27D82F6E, "Rouage de Kappacap": 0xCEBB8A5B,
    "Rouage de Komasan": 0xB9BCBACD, "Rouage de Noko": 0xC9D64E42,
}
# Pièces Yo-kai Watch 2 (Crank-a-kai) : 1 de chaque dans le pool.
COIN_HASHES: Dict[str, int] = {
    "Pièce 5 étoiles": 0xCB567D2C, "Pièce clinquante": 0xFE0DDBB7,
    "Pièce du nord": 0x60694E14, "Pièce du nordet": 0x176E7E82,
    "Pièce du levant": 0x8E672F38, "Pièce du centre": 0xF9601FAE,
    "Pièce du ponant": 0x69DF023F, "Pièce des montagnes": 0x1ED832A9,
    "Pièce du sud": 0x7E1FBB4C, "Pièce du centre-ouest": 0x09188BDA,
    "Pièce des îles": 0x9011DA60, "Super pile ou passe": 0x21778140,
}
# Post-game : enregistrés (hash connu) mais HORS pool v1 (count 0). À activer
# quand on fera le post-game (déblocage de zone / combat Yo-kai).
POSTGAME_EXTRA_HASHES: Dict[str, int] = {
    "Glu spectrale": 0x87BD137D,   # item-clé combat Yo-kai (post-game)
    "Orbe Noko": 0x883C1092,       # déverrouille le Village Noko (post-game)
}
for _n in COMBAT_YOKAI_HASHES:
    _add(_n, _U, "combat_yokai", 1)
for _n in COIN_HASHES:
    _add(_n, _U, "coin", 1)
for _n in POSTGAME_EXTRA_HASHES:
    if _n not in ALL_ITEMS:
        _add(_n, _U, "postgame", 0)   # count 0 = défini mais HORS pool v1
COMBAT_YOKAI_POOL: List[str] = list(COMBAT_YOKAI_HASHES)
COIN_POOL: List[str] = list(COIN_HASHES)

# ---------------------------------------------------------------------------
# Items NATIFS des coffres (Doteos 2026-07-19)
# ---------------------------------------------------------------------------
# Tous les contenus natifs des coffres sont catalogués -> le POOL contribue
# désormais le VRAI contenu de chaque coffre actif (au lieu du filler
# générique). Data-driven : data/native_chest_items.json (nom de location ->
# nom d'item natif, déjà filtré aux items dont le hash est connu). Les coffres
# sans item natif connu (noms patchés par le mod) retombent sur du filler
# aléatoire (géré dans create_items). Les items sont enregistrés en filler +
# leur hash de livraison. APPEND-ONLY.
NATIVE_CHEST_ITEM_BY_LOCATION: Dict[str, str] = json.loads(pkgutil.get_data(
    __package__, "data/native_chest_items.json").decode("utf-8"))
_ITEM_HASH_BY_NAME: Dict[str, int] = {}
for _k, _v in json.loads(pkgutil.get_data(
        __package__, "data/item_hashes.json").decode("utf-8")).items():
    _ITEM_HASH_BY_NAME[_v] = int(_k, 16)
_NATIVE_ITEM_NAMES = set(NATIVE_CHEST_ITEM_BY_LOCATION.values())
for _it in sorted(_NATIVE_ITEM_NAMES):
    if _it not in ALL_ITEMS:
        _add(_it, _F, "native")

# ---------------------------------------------------------------------------
# Tables dérivées
# ---------------------------------------------------------------------------
ITEM_NAME_TO_ID: Dict[str, int] = {
    name: data.code for name, data in ALL_ITEMS.items()
}

# Livraison en jeu (étape 3) : nom d'item AP -> hash CRC32 de l'objet du jeu.
# Ces items sont de VRAIS objets (noms exacts), donc le client peut les écrire
# dans l'inventaire (consommables/utiles) ou la liste d'objets-clés (outils/clé).
# Hash vérifiés dans data/item_hashes.json. Les items ABSTRAITS (rangs,
# chapitres, billets, vélo, médailles) ne sont pas ici : leur livraison passe
# par des flags/mécanismes dédiés (voir client.py à l'étape 3).
ITEM_GAME_HASH: Dict[str, int] = {
    # Remplissage (consommables)
    "Riz à la prune": 0x6B85C07A,
    "Thé de l'âme": 0xF585391C,
    "Hamburger": 0x6D4E0291,
    "Y-Cola": 0x6C8C68A6,
    "Riz à la crevette": 0x1BEF34F5,
    "Remède amer": 0x8D2013A6,
    "Mini EXPorbe": 0x8D447F63,
    "Petit EXPorbe": 0x1320EAC0,
    # Utiles
    "EXPorbe moyen": 0x8A29BB7A,
    "Grand EXPorbe": 0xFD2E8BEC,
    "Staminum Alpha": 0x8EA4C7C8,
    "Remède puiss.": 0xFA272330,
    # Outils / clé qui existent comme objets du jeu (livraison via liste d'objets-clés)
    "Canne à pêche": 0xD10F1534,
    "Clé de cabane": 0xE454B3AF,
    # (« Yo-kai Watch Modèle Zéro » est désormais couvert par le vrai objet
    #  « Modèle zéro » 0x1D9A6BF0 ajouté avec les 123 objets importants.)
}

# Type d'onglet d'inventaire (offset 2 de l'entrée) requis pour CRÉER une entrée
# (voir memory_map, recette de livraison). Dérivé de la catégorie item_config :
# nourriture/boisson (cat 10) -> 7 ; boost/soin/EXPorbe (cat 20) -> 5. Le type
# exact varie un peu (Riz à la prune est 6) mais l'objet apparaît sans crash.
ITEM_GAME_TYPE: Dict[str, int] = {
    "Riz à la prune": 7, "Thé de l'âme": 7, "Hamburger": 7, "Y-Cola": 7,
    "Riz à la crevette": 7,
    "Remède amer": 5, "Mini EXPorbe": 5, "Petit EXPorbe": 5,
    "EXPorbe moyen": 5, "Grand EXPorbe": 5, "Staminum Alpha": 5,
    "Remède puiss.": 5,
}
DEFAULT_INVENTORY_TYPE = 7  # repli si le type d'un objet n'est pas connu

# Pièces (jetons Crank-a-kai) : onglet « Objets » du sac, TYPE 10 (0x0a) — relevé
# EN JEU au scanner (Pièce rouge 0x9a89bf7c -> type 10 ; Doteos 2026-07-20). Livrées
# en type 7 (nourriture) elles étaient INVISIBLES (le jeu rejette une pièce hors de
# son onglet). Vaut pour les pièces colorées (contenu de coffres) ET les pièces
# gacha (COIN_HASHES). NB : l'EXPorbe (type 5) est aussi dans l'onglet « Objets »,
# mais chaque famille a son propre octet de type -> les pièces = 10, pas 5.
COIN_INVENTORY_TYPE = 10
for _cn in (list(COIN_HASHES)
            + [n for n in NATIVE_CHEST_ITEM_BY_LOCATION.values()
               if n.startswith("Pièce") or n.startswith("Éclat de pièce")]):
    ITEM_GAME_TYPE[_cn] = COIN_INVENTORY_TYPE

# --- Fusion du POOL DE FILLER (data/placeholder_pool.json) --------------------
# Sans fusion, un filler reçu absent de la petite table ITEM_GAME_HASH (ex.
# « Coups secrets ») partait en no-op « abstrait » et n'arrivait jamais en jeu
# (bug Doteos 2026-07-25). Le TYPE d'inventaire dépend de la CATÉGORIE item_config
# (data/item_categories.json, extrait du romfs comme les 124 objets-clés) :
#   cat 10 = nourriture/boisson -> type 7
#   cat 20 = soin/boost/utilisable/poupée -> type 5 (SAUF pièces -> type 10, déjà
#            posé ci-dessus ; setdefault le préserve)
#   cat 50 = ÉQUIPEMENT (bracelet/anneau/amulette/badge/arme/armure…) : inventaire
#            SÉPARÉ non RE'd. Écrit en type conso -> entrée invisible/mauvais onglet
#            (bug « La vie en tête »). -> NON fusionné : livraison équipement = À FAIRE.
_ITEM_CATEGORIES: Dict[str, int] = json.loads(pkgutil.get_data(
    __package__, "data/item_categories.json").decode("utf-8"))
_CAT_TO_INV_TYPE = {10: 7, 20: 5}
for _pn, _ph in json.loads(pkgutil.get_data(
        __package__, "data/placeholder_pool.json").decode("utf-8")):
    _phx = (_ph if isinstance(_ph, str) else f"0x{_ph:08x}").lower()
    _inv = _CAT_TO_INV_TYPE.get(_ITEM_CATEGORIES.get(_phx))
    if _inv is None:
        continue                      # cat 50 (équip.) ou inconnue -> pas livrable
    ITEM_GAME_HASH.setdefault(_pn, int(_phx, 16))
    ITEM_GAME_TYPE.setdefault(_pn, _inv)  # pièces déjà en type 10 -> préservé

# Objets livrés dans la LISTE D'OBJETS-CLÉS (outils/clés), PAS l'inventaire.
# VALIDÉ en jeu (2026-07-11) : Canne à pêche ET Clé de cabane ajoutées sans
# crash, et la Clé de cabane est FONCTIONNELLE (Doteos a pu l'utiliser) — pour
# une clé, l'avoir dans la liste suffit (pas de flag séparé). Le `data.haut`
# n'est PAS une catégorie : c'est l'ORDRE D'ACQUISITION (varie selon la save,
# prouvé sur 2 saves), calculé à la livraison = max(haut existants)+1. Donc
# ici on ne garde qu'un ENSEMBLE de noms (ceux à router vers la liste).
# Ordre d'insertion STABLE (3 originaux + objets importants dans l'ordre du
# fichier) -> sert d'ordre canonique pour les IDs des checks natifs
# (locations.KEY_ITEM_NATIVE_LOCATIONS). APPEND-ONLY : ne jamais réordonner.
KEY_ITEM_GAME_ORDER: List[str] = [
    "Canne à pêche",
    "Clé de cabane",
]
KEY_ITEM_GAME: set = set(KEY_ITEM_GAME_ORDER)
# Les objets importants du jeu -> tous livrés dans la liste d'objets-clés
# (shuffle dur) + leur hash de livraison.
for _iki in _IMPORTANT_KEY_ITEMS:
    if _iki["name"] not in KEY_ITEM_GAME:
        KEY_ITEM_GAME_ORDER.append(_iki["name"])
    KEY_ITEM_GAME.add(_iki["name"])
    ITEM_GAME_HASH.setdefault(_iki["name"], int(_iki["hash"], 16))

# POOL v1 (Doteos 2026-07-15) : hash de livraison des combat/pièces/post-game.
# Les objets « combat Yo-kai » vont dans la LISTE D'OBJETS-CLÉS (comme les outils)
# mais SANS check natif (pas ajoutés à KEY_ITEM_GAME_ORDER). Les pièces + post-game
# se livrent dans l'inventaire (bag). À valider en jeu (onglet exact).
for _n, _h in COMBAT_YOKAI_HASHES.items():
    ITEM_GAME_HASH.setdefault(_n, _h)
    KEY_ITEM_GAME.add(_n)
for _n, _h in {**COIN_HASHES, **POSTGAME_EXTRA_HASHES}.items():
    ITEM_GAME_HASH.setdefault(_n, _h)
# Hash de livraison des items natifs des coffres (Doteos 2026-07-19).
for _it in _NATIVE_ITEM_NAMES:
    if _it in _ITEM_HASH_BY_NAME:
        ITEM_GAME_HASH.setdefault(_it, _ITEM_HASH_BY_NAME[_it])

# Clés et outils concernés par l'option key_item_shuffle.
SHUFFLABLE_KEY_ITEMS: List[str] = [
    name for name, data in ALL_ITEMS.items()
    if data.category in ("key", "tool", "important")
]

# Placements vanilla utilisés quand key_item_shuffle est désactivé.
# item -> nom de location. Si la location n'existe pas dans la seed
# (catégorie désactivée), l'objet est donné au départ à la place.
VANILLA_KEY_PLACEMENTS: Dict[str, str] = {
    "Vélo": "Requête : Courage, Max !",
    "Canne à pêche": "Requête : Pas le temps de pêcher !",
    "Modèle zéro": "Chapitre 6 : Yo-kai Watch Modèle Zéro",
    "Clé du tunnel abandonné": "Chapitre 7 : La tempête arrive !",
    "Clé de cabane": "Chapitre 11 : Danger au vieux Granval !",
    "Clé du Paradis divin": "Obtenons le rang S !",
}

# Placements vanilla des rangs de montre (rang D pendant l'histoire,
# rangs C à S sur les requêtes de rang).
VANILLA_RANK_PLACEMENTS: Dict[int, str] = {
    1: "Chapitre 2 : Cache-cache high-tech",
    2: "Obtenons le rang C !",
    3: "Obtenons le rang B !",
    4: "Obtenons le rang A !",
    5: "Obtenons le rang S !",
}
VANILLA_BICYCLE_PLACEMENT = "Requête : Courage, Max !"

# Distribution pondérée du remplissage (vrais consommables du jeu).
FILLER_WEIGHTS: List[Tuple[str, int]] = [
    ("Riz à la prune", 20),
    ("Thé de l'âme", 18),
    ("Hamburger", 14),
    ("Y-Cola", 14),
    ("Riz à la crevette", 12),
    ("Remède amer", 10),
    ("Mini EXPorbe", 8),
    ("Petit EXPorbe", 4),
]

# Distribution pondérée des pièges.
TRAP_WEIGHTS: List[Tuple[str, int]] = [
    ("Piège : porte-monnaie percé", 30),
    ("Piège : envoûtement", 30),
    ("Piège : embuscade", 20),
    ("Piège : objet factice", 20),
]

# Groupes d'indices (hints).
ITEM_GROUPS: Dict[str, set] = {
    "Rangs de montre": {PROGRESSIVE_RANK_ITEM, *RANK_ITEM_NAMES.values()},
    "Transport": {"Vélo", "Vélo (progressif)", "Sonnette de vélo"},
    "Clés": {
        "Clé du tunnel abandonné",
        "Clé de cabane", "Clé du Paradis divin",
    },
    "Outils": {"Canne à pêche", "Filet à insectes", "Modèle zéro"},
    "Médailles légendaires": {legendary_medal_name(y) for y in LEGENDARY_YOKAI},
    "Pièges": {name for name, d in ALL_ITEMS.items() if d.category == "trap"},
}
