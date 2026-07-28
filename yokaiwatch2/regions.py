# -*- coding: utf-8 -*-
"""
Region graph for the Yo-kai Watch 2 Archipelago world (French zone names).

Zones sourced from the Supersoluce guide: Granval (Springdale) and its five
districts, Ourcival, the past (Vieux Granval / Vieil Ourcival), the postgame
dungeons (Tunnel sans fin, Limbes éternelles) and the Psychic-Specters-only
Paradis divin. Rules are applied afterwards by rules.py, keyed on
entrance/location names.
"""

from typing import Dict

from BaseClasses import ItemClassification, LocationProgressType, Region

from .constants import (
    CHAPTER_COMBAT_RANKS,
    CHAPTER_COUNT,
    CHAPTER_REGIONS,
    DISTRICTS,
    FINAL_BOSS_EVENT,
    INFERNO_BOSS_EVENT,
    PARADISE_BOSS_EVENT,
    chapter_event_name,
)
from .data import AccessReq, ConnectionData, LocationCategory, YKW2LocationData
from .items import YKW2Item
from .locations import ALL_LOCATIONS, YKW2Location
from .memory_map import TABLO_BIT_TO_LOCATION
from .options import Goal, YokaiShuffle

# Tablos RE'd (détectables) -> actifs même sans tablo_shuffle.
_DETECTABLE_TABLOS = set(TABLO_BIT_TO_LOCATION.values())

# ---------------------------------------------------------------------------
# Régions
# ---------------------------------------------------------------------------
REGION_NAMES = [
    "Menu",
    # Quartiers de Granval (présent)
    "Les Hauts de Granval",
    "Quartier des boutiques",
    "Centre-ville de Granval",
    "Coteau fleuri",
    "La Corniche",
    "Tour Excellence",
    # Nature et donjons (présent)
    "Mont Sylvestre",
    "Tunnel abandonné",
    "Clinique du Crépuscule",
    # Campagne et bord de mer (présent)
    "Ourcival",
    "Mont de l'Ours",
    "San Fantastico",
    # 60 ans en arrière
    "Vieux Granval",
    "Vieil Ourcival",
    "Gera Gera Land",
    "Plaines Plinpot",
    # Spécial / post-game
    "Heure funeste",
    "Tunnel sans fin",
    "Limbes éternelles",
    "Paradis divin",
    "Repaire de Lady Démona",
]

# ---------------------------------------------------------------------------
# Connexions. Les entrées Menu -> quartier utilisent la règle de quartier
# (Passe de quartier OU seuil de chapitre) ; les autres leur AccessReq.
# ---------------------------------------------------------------------------
CONNECTIONS = [
    # Quartiers de Granval, tous accessibles depuis le hub Menu.
    *[ConnectionData(f"Menu -> {d}", "Menu", d) for d in DISTRICTS],
    # Présent
    ConnectionData("Les Hauts de Granval -> Mont Sylvestre",
                   "Les Hauts de Granval", "Mont Sylvestre", AccessReq(1)),
    ConnectionData("Mont Sylvestre -> Tunnel abandonné",
                   "Mont Sylvestre", "Tunnel abandonné",
                   AccessReq(2, 1, ("Clé du tunnel abandonné",))),
    ConnectionData("Centre-ville de Granval -> Tour Excellence",
                   "Centre-ville de Granval", "Tour Excellence", AccessReq(3, 0)),  # Ch4, pas de rang (capture)
    ConnectionData("Quartier des boutiques -> Clinique du Crépuscule",
                   "Quartier des boutiques", "Clinique du Crépuscule",
                   AccessReq(8, 3)),   # Ch9 (min_chapter=8) + rang B ; PAS de clé (dixit Doteos)
    ConnectionData("Les Hauts de Granval -> Heure funeste",
                   "Les Hauts de Granval", "Heure funeste", AccessReq(2, 1)),
    # Trains vers la campagne / le bord de mer
    ConnectionData("Centre-ville de Granval -> Ourcival",
                   "Centre-ville de Granval", "Ourcival",
                   AccessReq(3, 0)),   # Ch4 = min_chapter 3 ; billets achetables nativement (pas de gate objet)
    ConnectionData("Centre-ville de Granval -> San Fantastico",
                   "Centre-ville de Granval", "San Fantastico",
                   AccessReq(3, 0)),  # Ch4 = min_chapter 3 ; billets achetables nativement (pas de gate objet)
    ConnectionData("Ourcival -> Mont de l'Ours",
                   "Ourcival", "Mont de l'Ours", AccessReq(3, 1)),
    # Voyage temporel (60 ans en arrière) : débloqué par l'histoire (pas d'objet).
    ConnectionData("Les Hauts de Granval -> Vieux Granval",
                   "Les Hauts de Granval", "Vieux Granval",
                   AccessReq(4, 0)),
    ConnectionData("Ourcival -> Vieil Ourcival",
                   "Ourcival", "Vieil Ourcival",
                   AccessReq(4, 0)),
    ConnectionData("Vieux Granval -> Gera Gera Land",
                   "Vieux Granval", "Gera Gera Land", AccessReq(7, 2)),
    ConnectionData("Vieux Granval -> Plaines Plinpot",
                   "Vieux Granval", "Plaines Plinpot", AccessReq(7, 3)),
    # Fin de partie et post-game
    # Le Repaire de Lady Démona (boss final = goal) exige la Yo-kai Watch Modèle Zéro
    # (Doteos 2026-07-22 : sans elle on ne peut pas finir l'aventure) -> objet requis
    # pour le goal, le fill le place forcément avant la fin.
    ConnectionData("Vieux Granval -> Repaire de Lady Démona",
                   "Vieux Granval", "Repaire de Lady Démona",
                   AccessReq(10, 4, ("Modèle zéro",))),
    ConnectionData("Ourcival -> Tunnel sans fin",
                   "Ourcival", "Tunnel sans fin", AccessReq(10, 4)),
    ConnectionData("Coteau fleuri -> Limbes éternelles",
                   "Coteau fleuri", "Limbes éternelles",
                   AccessReq(10, 4, ("Clé de cabane",))),
    ConnectionData("Vieil Ourcival -> Paradis divin",
                   "Vieil Ourcival", "Paradis divin",
                   AccessReq(10, 0, ("Clé du Paradis divin",))),
]

# Événements de boss liés aux objectifs :
# (nom de location, item d'événement, région, requirement).
BOSS_EVENTS = [
    ("Événement : Lady Démona", FINAL_BOSS_EVENT,
     "Repaire de Lady Démona", AccessReq(10, 4)),
    ("Événement : Potofeu", INFERNO_BOSS_EVENT,
     "Limbes éternelles", AccessReq(10, 5)),
    ("Événement : Filomène", PARADISE_BOSS_EVENT,
     "Paradis divin", AccessReq(10, 5)),
]


# ---------------------------------------------------------------------------
# Sélection des locations selon les options
# ---------------------------------------------------------------------------
def include_legendary_locations(world) -> bool:
    opts = world.options
    return bool(opts.legendary_shuffle) \
        or opts.yokai_shuffle.value in (YokaiShuffle.option_legendary,
                                        YokaiShuffle.option_all) \
        or opts.goal.value == Goal.option_all_legendaries


# Régions et seuil du POST-GAME (après la défaite de Lady Démona, chapitre >= 11).
# DÉCISION Doteos (2026-07-14) : si le goal est le boss final, le post-game « ne
# sert à rien » -> on retire ses locations du seed (aucune progression au-delà du
# goal, pas de checks morts). Les autres goals (Potofeu, Filomène, légendaires,
# all_checks) le gardent. Story_100 le garde aussi (chapitre 11 = dernier chapitre).
POSTGAME_REGIONS = {"Tunnel sans fin", "Limbes éternelles", "Paradis divin"}
POSTGAME_MIN_CHAPTER = 10   # min_chapter >= 10 (= 10 chapitres terminés = Ch11)


def _is_postgame_location(data: YKW2LocationData) -> bool:
    return (data.region in POSTGAME_REGIONS
            or data.req.min_chapter >= POSTGAME_MIN_CHAPTER)


def get_active_location_data(world) -> Dict[str, YKW2LocationData]:
    """Locations activées par les options du joueur.

    Fonction pure des options (plus les drapeaux force_chests / force_ground
    posés par generate_early si le pool ne tiendrait pas), appelable depuis
    generate_early comme depuis create_regions.
    """
    opts = world.options
    force_chests = getattr(world, "force_chests", False)
    force_ground = getattr(world, "force_ground", False)
    yokai_mode = opts.yokai_shuffle.value
    # Le goal « boss final » n'a pas besoin du post-game -> on l'exclut.
    keep_postgame = opts.goal.value != Goal.option_final_boss

    enabled = {
        LocationCategory.STORY: True,
        LocationCategory.WATCH_RANK: True,
        LocationCategory.BOSS: bool(opts.boss_shuffle),
        LocationCategory.QUEST: bool(opts.quest_shuffle),
        LocationCategory.CHEST: bool(opts.chest_shuffle) or force_chests,
        LocationCategory.GROUND: bool(opts.ground_item_shuffle) or force_ground,
        LocationCategory.FUSION: bool(opts.fusion_shuffle),
        LocationCategory.EVOLUTION: bool(opts.evolution_shuffle),
        LocationCategory.LEGENDARY: include_legendary_locations(world),
        LocationCategory.PLANQUE: bool(opts.planque_shuffle),
        LocationCategory.TABLO: bool(opts.tablo_shuffle),
        LocationCategory.KOMASAN: bool(opts.komasan_shuffle),
        LocationCategory.CRIMINEL: bool(opts.criminel_shuffle),
        LocationCategory.INSECTE: bool(opts.collection_shuffle),
        LocationCategory.POISSON: bool(opts.collection_shuffle),
        # Spots natifs des objets-clés : seulement avec le shuffle dur activé.
        LocationCategory.NATIVE_KEY: bool(opts.key_item_shuffle),
        # Events détectés par FLAG mémoire (ex. choix des beignets du Ch4) :
        # toujours actifs, la détection ne dépend d'aucune option.
        LocationCategory.EVENT: True,
    }

    active: Dict[str, YKW2LocationData] = {}
    for name, data in ALL_LOCATIONS.items():
        if not keep_postgame and _is_postgame_location(data):
            continue   # post-game exclu quand le goal est le boss final
        if data.category == LocationCategory.YOKAI:
            if yokai_mode == YokaiShuffle.option_all \
                    or (yokai_mode == YokaiShuffle.option_s_rank
                        and data.yokai_rank == "S"):
                active[name] = data
        elif data.category == LocationCategory.TABLO:
            # Tablos : l'option tablo_shuffle commande VRAIMENT la catégorie
            # (Doteos 2026-07-29), mais on n'active QUE ceux qui sont RE'd
            # (détectables via TABLO_BIT_TO_LOCATION). Les non mappés resteraient
            # des checks que le client ne peut JAMAIS envoyer -> run bloquée en
            # multi si un objet de progression y tombe.
            if enabled[data.category] and name in _DETECTABLE_TABLOS:
                active[name] = data
        elif enabled[data.category]:
            active[name] = data
    return active


# ---------------------------------------------------------------------------
# Création des régions
# ---------------------------------------------------------------------------
def _make_event(world, region: Region, location_name: str, item_name: str,
                req: AccessReq) -> None:
    """Crée une location d'événement portant un item de progression verrouillé."""
    location = YKW2Location(world.player, location_name, None, region)
    location.place_locked_item(
        YKW2Item(item_name, ItemClassification.progression, None, world.player))
    region.locations.append(location)
    world.event_reqs[location_name] = req


def create_ykw2_regions(world) -> None:
    multiworld, player = world.multiworld, world.player

    regions = {name: Region(name, player, multiworld) for name in REGION_NAMES}
    multiworld.regions.extend(regions.values())

    # Locations réelles (checks), filtrées par les options.
    world.active_location_data = get_active_location_data(world)
    for name, data in world.active_location_data.items():
        region = regions[data.region]
        location = YKW2Location(player, name, data.code, region)
        # Filler UNIQUEMENT (jamais de progression) pour :
        #  - les spots natifs d'objets-clés (chapitre exact inconnu) ;
        #  - les Tablo-blabla (détection encore INCOMPLÈTE : seuls les 3 de la
        #    Grotte du littoral sont détectés via 0x086CFB1C ; en EXCLUDED, aucun
        #    objet de progression n'y tombe -> zéro soft-lock même si un check
        #    Tablo reste non collecté). À repasser en check normal quand la
        #    détection Tablo sera complète.
        # EXCEPTION : le check natif du Filet à insectes N'est PAS exclu -> le fill
        # peut y placer une progression (le Filet lui-même). Nécessaire car le Filet
        # est requis en sphère 0 (Ch1) et son spot natif est bien atteignable au tout
        # début (Doteos 2026-07-21) -> évite le soft-lock en solo.
        if (data.category in (LocationCategory.NATIVE_KEY, LocationCategory.TABLO)
                and name != "Objet-clé : Filet à insectes"):
            location.progress_type = LocationProgressType.EXCLUDED
        region.locations.append(location)

    # Événements logiques.
    world.event_reqs = {}
    if not world.options.story_shuffle:
        # Histoire vanilla : chaque chapitre terminé est un événement chaîné
        # sur le précédent (voir rules.has_chapter). FINIR le chapitre N exige
        # aussi SES objets-clés critiques (nécessaires PENDANT le chapitre en
        # jeu — corrige l'incohérence de sphères vue à l'audit du 2026-07-16 :
        # « Chapitre 3 terminé » apparaissait avant les Clés de l'école).
        from .items import CRITICAL_KEY_ITEMS_BY_CHAPTER as _CRIT
        for chapter in range(1, CHAPTER_COUNT + 1):
            _crit_items = (_CRIT.get(chapter, ())
                           if world.options.key_item_shuffle else ())
            _make_event(
                world, regions[CHAPTER_REGIONS[chapter]],
                f"Événement : Chapitre {chapter}", chapter_event_name(chapter),
                AccessReq(min_chapter=chapter - 1,
                          combat_rank=CHAPTER_COMBAT_RANKS[chapter],
                          items=_crit_items))
    for location_name, item_name, region_name, req in BOSS_EVENTS:
        _make_event(world, regions[region_name], location_name, item_name, req)

    # Entrées (les règles sont posées par nom dans rules.py).
    for connection in CONNECTIONS:
        regions[connection.source].connect(
            regions[connection.target], name=connection.name)
        if connection.bidirectional:
            regions[connection.target].connect(
                regions[connection.source], name=f"{connection.name} (retour)")
