# -*- coding: utf-8 -*-
"""
Constants for the Yo-kai Watch 2 Archipelago world.

All player-facing names use the FRENCH localization of the game, sourced
from the Supersoluce guide (see game_data.py) and the maintainer's own
knowledge of the French version.

IMPORTANT - ID stability:
    Archipelago item/location IDs must NEVER change once a world has been
    released. All IDs derive from BASE_ID + a category offset + the position
    inside the data table. Data tables are APPEND-ONLY after release.
"""

GAME_NAME = "Yo-kai Watch 2"

# Base ID for every item and location of this world.
BASE_ID = 59_420_000

# ---------------------------------------------------------------------------
# Location ID offsets (added to BASE_ID). Each category owns a reserved range.
# ---------------------------------------------------------------------------
STORY_OFFSET = 0          # 0    - 49   : chapitres d'histoire
RANK_OFFSET = 50          # 50   - 99   : requêtes de rang de montre
BOSS_OFFSET = 100         # 100  - 199  : boss vaincus
QUEST_OFFSET = 200        # 200  - 449  : requêtes et services
FUSION_OFFSET = 450       # 450  - 499  : objets de fusion
EVOLUTION_OFFSET = 500    # 500  - 549  : évolutions notables
LEGENDARY_OFFSET = 550    # 550  - 599  : sceaux légendaires
YOKAI_OFFSET = 600        # 600  - 999  : amitiés Yo-kai
CHEST_OFFSET = 1000       # 1000 - 1599 : coffres
GROUND_OFFSET = 1600      # 1600 - 2199 : objets au sol
PLANQUE_OFFSET = 2200     # 2200 - 2299 : planques Yo-kai
TABLO_OFFSET = 2300       # 2300 - 2399 : Tablo-blabla
KOMASAN_OFFSET = 2400     # 2400 - 2449 : aventures de Komasan
CRIMINEL_OFFSET = 2450    # 2450 - 2499 : paliers de Yo-criminels
INSECTE_OFFSET = 2500     # 2500 - 2599 : collection d'insectes
POISSON_OFFSET = 2600     # 2600 - 2699 : collection de poissons
NATIVE_KEY_OFFSET = 2700  # 2700 - 2999 : spots natifs des objets-clés (checks)
EVENT_OFFSET = 3000       # 3000 - 3099 : events détectés par FLAG mémoire

# ---------------------------------------------------------------------------
# Watch ranks - Rangs de Yo-kai Watch
# ---------------------------------------------------------------------------
# Le joueur commence au rang E. Cinq améliorations : D, C, B, A, S.
# En interne un rang est un entier : E=0, D=1, C=2, B=3, A=4, S=5.
WATCH_RANKS = ["E", "D", "C", "B", "A", "S"]
MAX_WATCH_RANK = 5  # rang S
RANK_ITEM_NAMES = {
    1: "Rang de Yo-kai Watch : D",
    2: "Rang de Yo-kai Watch : C",
    3: "Rang de Yo-kai Watch : B",
    4: "Rang de Yo-kai Watch : A",
    5: "Rang de Yo-kai Watch : S",
}
PROGRESSIVE_RANK_ITEM = "Rang de Yo-kai Watch (progressif)"

# ---------------------------------------------------------------------------
# Chapitres d'histoire (titres français dans game_data.CHAPITRES)
# ---------------------------------------------------------------------------
# "min_chapter = N" dans une AccessReq signifie « N chapitres terminés »
# (0 = disponible dès le début).
CHAPTER_COUNT = 11
PROGRESSIVE_CHAPTER_ITEM = "Chapitre d'histoire (progressif)"

def chapter_event_name(chapter: int) -> str:
    """Nom de l'événement logique marquant un chapitre comme terminé."""
    return f"Chapitre {chapter} terminé"

# Région dans laquelle chaque chapitre se conclut.
CHAPTER_REGIONS = {
    1: "Les Hauts de Granval",
    2: "Mont Sylvestre",
    3: "Les Hauts de Granval",
    4: "Mont de l'Ours",
    5: "Vieux Granval",
    6: "Vieux Granval",
    7: "Les Hauts de Granval",
    8: "Plaines Plinpot",
    9: "Vieil Ourcival",
    10: "Centre-ville de Granval",
    11: "Repaire de Lady Démona",
}

# Rang de combat attendu par la logique pour terminer chaque chapitre
# (avant l'ajustement de la difficulté logique).
CHAPTER_COMBAT_RANKS = {
    1: 0, 2: 0, 3: 0,
    4: 1, 5: 1,
    6: 2, 7: 2,
    8: 3, 9: 3,
    10: 4, 11: 4,
}

# ---------------------------------------------------------------------------
# Quartiers de Granval (option starting_region)
# ---------------------------------------------------------------------------
DISTRICTS = [
    "Les Hauts de Granval",
    "Quartier des boutiques",
    "Centre-ville de Granval",
    "Coteau fleuri",
    "La Corniche",
]

def district_pass_name(district: str) -> str:
    return f"Passe de quartier : {district}"

# Nombre de chapitres terminés qui ouvre chaque quartier en logique vanilla.
# Une passe de quartier (option starting_region) court-circuite ce seuil.
# Valeurs = chapitres TERMINÉS requis (min_chapter). CORRIGÉ via capture live
# (2026-07-14) : min_chapter = (chapitre où la zone s'ouvre) − 1. Le compteur
# STORY_CHAPTER donne le chapitre COURANT ; min_chapter compte les TERMINÉS.
#   Corniche : ouverte Ch2 -> 1 · Coteau fleuri : Ch3 -> 2 ·
#   Quartier des boutiques : Ch3 -> 2 · Centre-ville : Ch4 -> 3.
DISTRICT_CHAPTERS = {
    "Les Hauts de Granval": 0,
    "Coteau fleuri": 2,
    "Quartier des boutiques": 2,
    "Centre-ville de Granval": 3,
    "La Corniche": 1,
}
# Vélo NON requis (Doteos, 2026-07-14) : 1 vélo gratuit à la quête + les autres
# s'achètent -> le vélo ne gate AUCUNE zone. None = aucun quartier n'attend le vélo.
BICYCLE_DISTRICT = None

# ---------------------------------------------------------------------------
# Boss liés aux objectifs (événements toujours créés).
# Noms de la localisation française : Lady Démona (boss final), Potofeu
# (Limbes éternelles), Filomène (Paradis divin).
# ---------------------------------------------------------------------------
FINAL_BOSS_EVENT = "Lady Démona vaincue"
INFERNO_BOSS_EVENT = "Potofeu vaincu"
PARADISE_BOSS_EVENT = "Filomène vaincue"

# ---------------------------------------------------------------------------
# Yo-kai légendaires
# ---------------------------------------------------------------------------
# NOTE (données communautaires) : liste à vérifier contre la version FR de
# Spectres Psychiques ; ajuster en append-only si besoin.
LEGENDARY_YOKAI = [
    "Shogunyan",
    "Komashura",
    "Gilgaros",
    "Elder Bloom",
    "Spoilerina",
    "Dandoodle",
    "Slurpent",
    "Poofessor",
]

def legendary_medal_name(yokai: str) -> str:
    return f"Médaille légendaire : {yokai}"

# ---------------------------------------------------------------------------
# Yo-criminels : paliers de captures devenant des checks.
# L'application est remise par l'inspecteur Giraud au chapitre 3.
# ---------------------------------------------------------------------------
CRIMINEL_MILESTONES = [1, 5, 10, 20, 30]

# ---------------------------------------------------------------------------
# Client / ROM (voir rom.py et client.py)
# ---------------------------------------------------------------------------
# Title ID 3DS de Yo-kai Watch 2 : Spectres Psychiques.
# EU vérifié en lisant l'en-tête NCSD/NCCH de la cartouche dumpée
# (code produit CTR-P-BYSP, Europe multi-langues dont français).
TITLE_ID_EU = "00040000001B2900"
TITLE_ID_US = "TODO"  # à vérifier sur un dump US

# Port par défaut du stub GDB de Citra / Azahar (pont mémoire du client).
CITRA_GDB_PORT = 24689
