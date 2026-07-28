# -*- coding: utf-8 -*-
"""Génère le pack PopTracker de l'apworld Yo-kai Watch 2.

Source de vérité = les données de l'apworld (locations, items, régions,
AccessReq). À relancer après tout ajout de coffre/quête : le pack reste
synchro. Sortie : tracker/ykw2-poptracker/ + zip prêt pour PopTracker.

Technique : les modules de l'apworld importent BaseClasses/Options
(Archipelago) -> on les STUBBE, puis on importe le package SANS exécuter
__init__.py (namespace package artisanal).
"""
import importlib
import importlib.machinery
import json
import shutil
import sys
import types
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "yokaiwatch2"
OUT = ROOT / "tracker" / "ykw2-poptracker"

# ---------------------------------------------------------------------------
# 1. Stubs Archipelago + import du package sans __init__
# ---------------------------------------------------------------------------
def _stub_ap_modules() -> None:
    base = types.ModuleType("BaseClasses")

    class _Flag(int):
        def __new__(cls, v):
            return super().__new__(cls, v)

    class ItemClassification:
        filler = _Flag(0)
        progression = _Flag(1)
        useful = _Flag(2)
        trap = _Flag(4)
        skip_balancing = _Flag(8)
        progression_skip_balancing = _Flag(9)

    class _Any:  # Location / Item / Region / Tutorial...
        def __init__(self, *a, **k):
            pass

    class LocationProgressType:
        DEFAULT = 0
        PRIORITY = 1
        EXCLUDED = 2

    base.ItemClassification = ItemClassification
    base.Location = _Any
    base.Item = _Any
    base.Region = _Any
    base.Tutorial = _Any
    base.LocationProgressType = LocationProgressType
    base.MultiWorld = _Any
    base.CollectionState = _Any
    sys.modules.setdefault("BaseClasses", base)

    opts = types.ModuleType("Options")
    for name in ("Choice", "DeathLink", "DefaultOnToggle", "OptionGroup",
                 "PerGameCommonOptions", "Range", "StartInventoryPool",
                 "Toggle", "Option", "FreeText", "OptionSet"):
        setattr(opts, name, type(name, (), {
            "__init__": lambda self, *a, **k: None}))
    sys.modules.setdefault("Options", opts)

    for extra in ("worlds", "worlds.AutoWorld"):
        m = types.ModuleType(extra)
        m.World = type("World", (), {})
        m.WebWorld = type("WebWorld", (), {})
        sys.modules.setdefault(extra, m)


def _import_pkg():
    _stub_ap_modules()
    pkg = types.ModuleType("yokaiwatch2")
    pkg.__path__ = [str(PKG)]
    # __spec__ complet avec un vrai loader : pkgutil.get_data (utilisé par
    # items.py/memory_map.py pour lire data/*.json) en a besoin.
    loader = importlib.machinery.SourceFileLoader(
        "yokaiwatch2", str(PKG / "__init__.py"))
    spec = importlib.machinery.ModuleSpec("yokaiwatch2", loader,
                                          origin=str(PKG / "__init__.py"),
                                          is_package=True)
    spec.submodule_search_locations = [str(PKG)]
    pkg.__spec__ = spec
    pkg.__file__ = str(PKG / "__init__.py")  # requis par pkgutil.get_data
    sys.modules["yokaiwatch2"] = pkg
    mods = {}
    for name in ("constants", "data", "memory_map", "items", "locations",
                 "regions"):
        mods[name] = importlib.import_module(f"yokaiwatch2.{name}")
    # rules.py peut échouer à s'importer (dépend de BaseClasses) : optionnel.
    try:
        mods["rules"] = importlib.import_module("yokaiwatch2.rules")
    except Exception:
        mods["rules"] = types.SimpleNamespace(
            DISTRICT_REQUIRED_ITEMS={
                "Centre-ville de Granval": ("Indications de Maman",)})
    return mods


# ---------------------------------------------------------------------------
# 2. Utilitaires
# ---------------------------------------------------------------------------
def slug(name: str) -> str:
    s = unicodedata.normalize("NFKD", name)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    out = []
    for c in s:
        out.append(c if c.isalnum() else "_")
    r = "".join(out)
    while "__" in r:
        r = r.replace("__", "_")
    return r.strip("_")


def region_requirements(regions_mod, district_chapters, district_items=None):
    """Exigences cumulées par région (BFS avec relaxation depuis Menu).

    Les entrées Menu -> quartier n'ont PAS d'AccessReq dans CONNECTIONS (la
    règle est posée par nom dans rules.py) -> on injecte ici le seuil de
    chapitre du quartier + la « Pile ou passe » (les quartiers autres que
    Les Hauts ne s'ouvrent qu'après la pile, début Ch2 — réalité Doteos)."""
    # Quartiers ouverts par la « Pile ou passe » (chap 2). Seule La Corniche
    # est un district ; les égouts/ruelle sont des zones de coffres gérées
    # via CHEST_ZONE_ACCESS (héritées par la location, pas ici).
    PILE_DISTRICTS = {"La Corniche"}
    district_items = district_items or {}
    conns = getattr(regions_mod, "CONNECTIONS", [])
    graph = {}
    for c in conns:
        req = c.req
        if c.source == "Menu" and c.target in district_chapters:
            gate = district_chapters[c.target]
            extra = ("Pile ou passe",) if c.target in PILE_DISTRICTS else ()
            # Objets-clés hard-gate d'un quartier (ex. Indications de Maman ->
            # Centre-ville) : posés dans rules.make_district_rule, pas dans la
            # connexion -> on les injecte ici pour que le tracker les reflète.
            extra += tuple(district_items.get(c.target, ()))
            req = types.SimpleNamespace(
                min_chapter=max(req.min_chapter, gate),
                combat_rank=req.combat_rank,
                items=tuple(req.items) + extra)
        graph.setdefault(c.source, []).append((c.target, req))
    best = {"Menu": (0, 0, frozenset())}
    frontier = ["Menu"]
    while frontier:
        cur = frontier.pop()
        ch, rk, items = best[cur]
        for target, req in graph.get(cur, []):
            cand = (max(ch, req.min_chapter), max(rk, req.combat_rank),
                    items | frozenset(req.items))
            old = best.get(target)
            key = (cand[0], cand[1], len(cand[2]))
            if old is None or key < (old[0], old[1], len(old[2])):
                best[target] = cand
                frontier.append(target)
    return best


def rules_for(req, region_req):
    """AccessReq (+exigences région) -> règle PopTracker unique (AND)."""
    parts = []
    ch = max(req.min_chapter, region_req[0])
    rk = max(req.combat_rank, region_req[1])
    if ch:
        parts.append(f"chapitre:{ch}")
    if rk:
        parts.append(f"rang:{rk}")
    for it in sorted(set(req.items) | set(region_req[2])):
        parts.append(slug(it))
    return [",".join(parts)] if parts else []


# ---------------------------------------------------------------------------
# 3. Images (Pillow) : icônes + carte schématique
# ---------------------------------------------------------------------------
def short_label(name: str) -> str:
    """Abréviation courte et distincte pour l'icône d'un objet-clé."""
    skip = {"de", "du", "des", "la", "le", "les", "l", "a", "à", "aux", "d"}
    words = [w for w in name.replace(":", " ").replace("-", " ").split()
             if w.lower() not in skip]
    label = "".join(w[0].upper() if not w[0].isdigit() else w[0]
                    for w in words)[:4]
    digits = "".join(c for c in name if c.isdigit())
    if digits and digits not in label:
        label = (label[:2] + digits)[:4]
    return label or name[:3]


# Positions des régions sur la VRAIE carte de Granval (Granvalentier.webp,
# 1480x992, fournie par Doteos dans « map yo kai watch/ »). Les régions
# absentes de cette carte vont sur la carte schématique « autres ».
GRANVAL_MAP_SRC = ROOT / "map yo kai watch" / "Granvalentier.webp"
GRANVAL_COORDS = {
    "Mont Sylvestre":           (580, 110),
    "Les Hauts de Granval":     (860, 290),
    "Coteau fleuri":            (350, 470),
    "Quartier des boutiques":   (330, 620),
    "Clinique du Crépuscule":   (450, 690),
    "Centre-ville de Granval":  (730, 660),
    "La Corniche":              (1210, 430),
    "Tour Excellence":          (1330, 220),
    # Ourcival = campagne au nord-ouest (flèche Doteos) ; Mont de l'Ours
    # posé « dans » la zone d'Ourcival sur la carte monde.
    "Ourcival":                 (100, 220),
    "Mont de l'Ours":           (180, 160),
    # San Fantastico : hameau au bout de la route du sud-ouest (flèche Doteos)
    "San Fantastico":           (60, 590),
}

# Région d'affichage des spots natifs « Objet-clé : X » sur le tracker
# (= zone où on récupère l'objet en jeu ; fallback « Menu » si inconnue).
# À COMPLÉTER avec Doteos.
KEYITEM_SPOT_ZONES = {
    # Objets-clés (re)mis au pool en 2026-07-20 (hard-gates) — zones à confirmer
    # avec Doteos pour un placement précis au picker.
    "Filet à insectes":         "Les Hauts de Granval",
    "Indications de Maman":     "Les Hauts de Granval",   # chez maman (à confirmer)
    "Clés de l'école":          "Les Hauts de Granval",    # école jour (à placer)
    "Herbe ancestrale":         "Coteau fleuri",  # Doteos 2026-07-19
    "Clé appartement C-303":    "San Fantastico",
    "Clé appartement B-301":    "Vieil Ourcival",
    # dictée Doteos 2026-07-16 (soir)
    "Pile ou passe":            "Mont Sylvestre",
    "Canne à pêche":            "Ourcival",
    "Documents perdus":         "Coteau fleuri",  # Doteos 2026-07-19
    "Clé de derrière":          "Coteau fleuri",  # récup manoir (Doteos 2026-07-19)
    "Montre de luxe":           "Vieux Granval",  # Granval du passé (Doteos 2026-07-19)
    "Cartes d'Ultramax":        "Ourcival",
    "Modèle zéro":              "Vieil Ourcival",  # Ourcival passé (Doteos 2026-07-19)
    "Capsule de lait":          "Vieil Ourcival",  # Ourcival passé (Doteos 2026-07-19)
    "Jolie petite clé":         "Coteau fleuri",
    "Foli-pili":                "Centre-ville de Granval",
    "Lettre de Komasan":        "Vieux Granval",
    "Grelot de félin":          "Vieux Granval",  # Mont Sylvestre passé
    "Bille mystérieuse":        "Vieux Granval",
    "Tenue de rocker":          "Vieux Granval",
    "Clé appartement C-101":    "Tour Excellence",
    "Jolie grande clé":         "Coteau fleuri",
    "Super tournevis":          "Quartier des boutiques",
    "Clé magnétique or":        "Égouts",   # donnée par une femme, fin « La base
                                            # secrète » (441,253) — Doteos 2026-07-24
    "Clé salle du trésor":      "Mont Sylvestre",  # tunnel abandonné (Doteos 2026-07-24)
}

# Hors tracker v1 (post-game) : ni la location, ni l'item dans la grille.
TRACKER_SKIP_LOCATIONS = {"Objet-clé : Clé de cabane"}
TRACKER_SKIP_ITEMS = {"Clé de cabane"}

# Items AFFICHÉS dans la colonne d'objets du tracker sans être des « objets-clés »
# du jeu (KEY_ITEM_GAME_ORDER). Le Vélo est une CAPACITÉ (bit 0x086CFAB9 b0), pas
# une entrée de la liste d'objets-clés, mais c'est un item AP de progression que
# Doteos veut suivre (demande 2026-07-27). Icône : déposer tracker_assets/icons/
# velo.png (sinon abréviation générée automatiquement).
TRACKER_EXTRA_ITEMS = ["Vélo"]

# Taille des marqueurs de check sur les CARTES DÉTAILLÉES de zone (px) — réglage
# demandé par Doteos 2026-07-27 (« moins gros » : 16/2 -> 10/1). Baisser encore
# ces deux valeurs si besoin ; ne concerne PAS les photos chapitres/criminels
# (grp_*, 64 px) ni les cartes de groupe.
DETAILED_MARKER_SIZE = 10
DETAILED_MARKER_BORDER = 1

# Carte monde du PASSÉ (Vieux_Granvalmapmonde.webp, 1200x991) : les régions
# du passé y sont posées (positions à affiner avec Doteos).
PAST_MAP_SRC = ROOT / "map yo kai watch" / "Vieux_Granvalmapmonde.webp"
PAST_COORDS = {
    "Vieux Granval":            (620, 470),
    # route du nord-ouest (flèche Doteos) : la sortie vers Ourcival du passé
    "Vieil Ourcival":           (250, 190),
    # maison/sanctuaire de la forêt NO (flèche 1 Doteos)
    "Plaines Plinpot":          (400, 95),
    # cœur de l'usine (flèche 2 Doteos)
    "Repaire de Lady Démona":   (370, 730),
}
# Cartes de zone dédiées (images Doteos) : la région a AUSSI sa propre carte,
# marqueur au centre (les coordonnées par coffre viendront plus tard).
# Cartes de zone RETIRÉES (demande Doteos : seules les 2 cartes monde) —
# dict conservé vide pour réactivation facile plus tard.
ZONE_IMAGES = {}

# CARTES DÉTAILLÉES PAR ZONE (tracker_assets/map asset/) : la région a son
# propre onglet, et CHAQUE check y est un marqueur cliquable individuel
# (positionné via CHECK_COORDS ; les non-positionnés sont auto-répartis en
# grille pour rester visibles). La région n'apparaît alors PLUS sur la carte
# monde. Format : région -> nom de fichier dans "tracker_assets/map asset/".
DETAILED_ZONE_MAPS = {
    "Les Hauts de Granval": "Hauts_de_granval.webp",
    "École élémentaire de Granval": "ecole.png",
    "Égouts": "égout.jpg",
    "La Corniche": "la corniche.jpg",
    "Mont Sylvestre": "mont sylvestre.jpg",
    "Centre-ville de Granval": "centre-ville.jpg",
    "Quartier des boutiques": "quartier des boutique.png",
    "Coteau fleuri": "coteau fleuri.jpg",
    "Tour Excellence": "tour exelence.jpg",
    "Ourcival": "ourcival.jpg",
    "Vieil Ourcival": "vieux ourcival.jpg",
    "Vieux Granval": "vieux granval.jpg",
    "San Fantastico": "san fantastico.jpg",
}
# Checks qui PARTAGENT le marqueur d'un autre (même point sur la carte -> un
# seul marqueur, plusieurs checks dans le popup). Clé = check invité,
# valeur = check hôte (qui, lui, a une position dans CHECK_COORDS).
MERGE_INTO = {
    # Objets-clés récupérés au même endroit que le Coffre 10 (Doteos 2026-07-20)
    "Objet-clé : Filet à insectes": "Les Hauts de Granval - Coffre 10",
    "Objet-clé : Indications de Maman": "Les Hauts de Granval - Coffre 10",
    # quêtes au même endroit que le Coffre 10 (Doteos 2026-07-17)
    "Requête : Le secret de Jibanyan": "Les Hauts de Granval - Coffre 10",
    "Requête : Sur les traces de Papa": "Les Hauts de Granval - Coffre 10",
    "Requête : La faim justifie le moyen": "Les Hauts de Granval - Coffre 10",
    # trilogie Chasseurs de trésors au même endroit que « Courage, Max ! »
    "Requête : Chasseurs de trésors 1": "Requête : Courage, Max !",
    "Requête : Chasseurs de trésors 2": "Requête : Courage, Max !",
    "Requête : Chasseurs de trésors 3": "Requête : Courage, Max !",
    # Canal isolé (sous-zone Ruelle obscure) fusionné au marqueur Ruelle obscure
    "Canal isolé - Coffre 01": "Ruelle obscure - Coffre 01",
    "Canal isolé - Coffre 02": "Ruelle obscure - Coffre 01",
    # (Égouts 04/05 accès Ruelle obscure : passés en MULTI_MAP_COORDS, plus fiable
    #  que le ref — vrais marqueurs sur Les Hauts G11 + carte Égouts H9/G9.)
    # Mont Sylvestre accès égouts : les 2 coffres au même endroit (Doteos 2026-07-19)
    "Mont Sylvestre (accès égouts) - Coffre 02": "Mont Sylvestre (accès égouts) - Coffre 01",
    # Tunnel abandonné : coffres 04/05 + la Clé salle du trésor au MÊME marqueur que
    # le coffre 03 (Doteos 2026-07-24).
    "Tunnel abandonné (salle du trésor) - Coffre 04": "Tunnel abandonné (salle du trésor) - Coffre 03",
    "Tunnel abandonné (salle du trésor) - Coffre 05": "Tunnel abandonné (salle du trésor) - Coffre 03",
    "Objet-clé : Clé salle du trésor": "Tunnel abandonné (salle du trésor) - Coffre 03",
    # Boss Crocho au même repère que le Tablo Ronimpec (Doteos 2026-07-25).
    "Boss : Crocho": "Tablo-blabla n°08 : Ronimpec",
    # Quêtes La Corniche au même marqueur que « Les portails mystère »
    "Requête : Le portail final": "Requête : Les portails mystère",
    "Requête : Une armure sinistre": "Requête : Les portails mystère",
    # La reine des cigales au même marqueur que Spécialiste des cigales
    "Requête : La reine des cigales": "Requête : Spécialiste des cigales",
    # Coteau fleuri : rang C Coffre 02 (Pièce verte) au même endroit que présent Coffre 01
    "Coteau fleuri (rang C) - Coffre 02": "Coteau fleuri (présent) - Coffre 01",
    # Quêtes de rang C/B/A au même marqueur (Doteos 2026-07-19)
    "Obtenons le rang B !": "Obtenons le rang C !",
    "Obtenons le rang A !": "Obtenons le rang C !",
    # Super Balaise : le retour au même marqueur que l'origine
    "Requête : Super Balaise : le retour": "Requête : Super Balaise : l'origine",
    # Tour Excellence : coffre de la Clé C-101 au même endroit que le Coffre 05
    "Tour Excellence - Coffre 06": "Tour Excellence - Coffre 05",
    # Ourcival : Faux Kappa + Canne à pêche au même marqueur que Pas le temps de pêcher
    "Requête : Trouvons Faux Kappa !": "Requête : Pas le temps de pêcher !",
    "Objet-clé : Canne à pêche": "Requête : Pas le temps de pêcher !",
    # Plaines Plinpot : Coffre 03 au même marqueur que le Coffre 02
    "Plaines Plinpot - Coffre 03": "Plaines Plinpot - Coffre 02",
    # Objets-clés Vieux Granval fusionnés sur leur quête (Doteos 2026-07-19)
    "Objet-clé : Bille mystérieuse": "Requête : Pièce ferronnerie",
    "Objet-clé : Montre de luxe": "Requête : Pièce Au Phil du temps",
    "Objet-clé : Grelot de félin": "Requête : Pièce sanctuaire",
    # Jouets d'antan à la Corniche (musée) = marqueur des trois quêtes Corniche
    "Requête : Jouets d'antan": "Requête : Les portails mystère",
    # Boss finaux : Lady Perpétua au même marqueur que Lady Démona (Vieux Granval)
    "Boss : Lady Perpétua": "Boss : Lady Démona",
    # Boss Laure/Marge au même marqueur (Vieil Ourcival)
    "Boss : Marge": "Boss : Laure",
    # Capsule de lait au même endroit que la Canne à pêche (Pas le temps de pêcher)
    "Objet-clé : Capsule de lait": "Requête : Pas le temps de pêcher !",
    # Oden de l'âme 1/2/3 à la Corniche, marqueur de Ectoplasmes à l'école
    "Requête : Oden de l'âme 1": "Requête : Ectoplasmes à l'école",
    "Requête : Oden de l'âme 2": "Requête : Ectoplasmes à l'école",
    "Requête : Oden de l'âme 3": "Requête : Ectoplasmes à l'école",
    # Musée en détresse au même marqueur que les quêtes Corniche (Doteos 2026-07-19)
    "Requête : Musée en détresse": "Requête : Les portails mystère",
    # Clinique du Crépuscule : coffres fusionnés sur le Coffre 01 (Doteos 2026-07-19).
    # La quête « La clinique hantée » est au Centre-ville (placée à part).
    "Clinique du Crépuscule - Coffre 02": "Clinique du Crépuscule - Coffre 01",
    "Clinique du Crépuscule - Coffre 03": "Clinique du Crépuscule - Coffre 01",
    "Clinique du Crépuscule - Coffre 04": "Clinique du Crépuscule - Coffre 01",
    "Clinique du Crépuscule - Coffre 05": "Clinique du Crépuscule - Coffre 01",
    "Clinique du Crépuscule - Coffre 06": "Clinique du Crépuscule - Coffre 01",
    "Clinique du Crépuscule - Coffre 07": "Clinique du Crépuscule - Coffre 01",
    "Clinique du Crépuscule - Coffre 08": "Clinique du Crépuscule - Coffre 01",
    "Clinique du Crépuscule - Coffre 09": "Clinique du Crépuscule - Coffre 01",
    # Poignée étrange + boss Firmain (quête « La clinique hantée ») au même repère
    # que la clinique (Doteos 2026-07-24).
    "Objet-clé : Poignée étrange": "Clinique du Crépuscule - Coffre 01",
    "Boss : Firmain": "Clinique du Crépuscule - Coffre 01",
}
# Marqueur SUPPLÉMENTAIRE (« ref ») d'un check déjà placé/fusionné ailleurs :
# le même check apparaît en plus sur une autre carte. Clé = check ;
# valeur = (map_id, x, y). Le check doit exister par ailleurs (CHECK_COORDS
# ou MERGE_INTO) ; ici on ne fait qu'ajouter un point cliquable lié.
SECONDARY_MARKERS = {}
# Région d'AFFICHAGE forcée sur le tracker (le check apparaît sur cette
# carte/popup au lieu de sa région logique). Pour les quêtes que Doteos
# situe dans un autre quartier que ce que disent les données.
DISPLAY_REGION_OVERRIDE = {
    # Choix des beignets du Ch4 : la location est en région « Les Hauts » mais
    # l'événement se passe au Quartier des boutiques (Doteos 2026-07-20).
    "Beignets du chapitre 4": "Quartier des boutiques",
    "Requête : La star de Granval 1":   "Centre-ville de Granval",
    "Requête : Prix de Gastronomie":    "Quartier des boutiques",
    "Requête : Super Balaise : le retour": "Coteau fleuri",
    "Requête : C1- Grand Prix":         "Les Hauts de Granval",  # Doteos 2026-07-19
    # CT1/CT2 sont en Mont Sylvestre dans les données mais physiquement à
    # E4 des Hauts (avec CT3) -> on les ramène sur la carte des Hauts.
    "Requête : Chasseurs de trésors 1": "Les Hauts de Granval",
    "Requête : Chasseurs de trésors 2": "Les Hauts de Granval",
    # École : carte dédiée (les 13 coffres nuit gérés par préfixe en code)
    "Boss : Grolos":               "École élémentaire de Granval",
    "Boss : Inamygal":             "École élémentaire de Granval",
    # Tablo-blabla capturés -> sur la carte de la zone RE'd (Doteos 2026-07-24/25) :
    "Tablo-blabla n°01 : Granpapéti": "Les Hauts de Granval",
    "Tablo-blabla n°02 : Feulion": "Les Hauts de Granval",
    "Tablo-blabla n°03 : Triptic-tac": "Les Hauts de Granval",
    "Tablo-blabla n°04 : Robonyan": "Mont Sylvestre",
    "Tablo-blabla n°05 : Draconfus": "Mont Sylvestre",
    "Tablo-blabla n°08 : Ronimpec": "Coteau fleuri",
    "Tablo-blabla n°09 : Sumochi": "Centre-ville de Granval",
    "Tablo-blabla n°11 : Hiblusion": "Centre-ville de Granval",
    "Tablo-blabla n°12 : Maître Oden": "Quartier des boutiques",
    "Tablo-blabla n°16 : Grégrigry": "La Corniche",
    "Tablo-blabla n°17 : Chaipô": "Tour Excellence",
    "Tablo-blabla n°18 : Croquin": "San Fantastico",
    "Tablo-blabla n°19 : Supernoël": "San Fantastico",
    "Requête : Méga cache-cache":  "École élémentaire de Granval",
    "Objet-clé : Clés de l'école": "École élémentaire de Granval",
    # Service en Mont Sylvestre dans les données mais physiquement aux Hauts (Doteos)
    "Service : A la chasse aux insectes !": "Mont Sylvestre",  # sentier de randonnée (Doteos 2026-07-24)
    # Quête donnée au Centre-ville dans les données mais physiquement à la Corniche
    "Requête : Tout droit sorti du futur !": "La Corniche",
    # Plaines Plinpot affichées sur la carte Vieux Granval (Doteos 2026-07-19)
    **{f"Plaines Plinpot - Coffre {i:02d}": "Vieux Granval" for i in range(1, 12)},
    # Mont de l'Ours (présent) affiché sur la carte Ourcival (même zone) :
    # présent + Rochers de face + Canyon de la cigale (région logique Mont de l'Ours)
    "Mont de l'Ours (présent) - Coffre 01": "Ourcival",
    "Ourcival (Rochers de face) - Coffre 01": "Ourcival",
    "Ourcival (Rochers de face) - Coffre 02": "Ourcival",
    "Ourcival (Rochers de face) - Coffre 03": "Ourcival",
    "Ourcival (Canyon de la cigale) - Coffre 01": "Ourcival",
    "Ourcival (Canyon de la cigale) - Coffre 02": "Ourcival",
    "Ourcival (Canyon de la cigale) - Coffre 03": "Ourcival",
    # Services du Quartier des boutiques situés ailleurs (Doteos 2026-07-19)
    "Service : Le ventre vide": "La Corniche",
    "Service : Espiégleries": "Ourcival",
    # Vieil Ourcival : quête + service situés au Vieux Granval (Doteos 2026-07-19)
    "Requête : Pièce Au Phil du temps": "Vieux Granval",
    "Service : Un entraînement de star": "Vieux Granval",
    # Vieux Granval : Un amour perdu situé à Ourcival (Doteos 2026-07-19)
    "Requête : Un amour perdu": "Ourcival",
    # Boss finaux affichés sur la carte Vieux Granval (Doteos 2026-07-19)
    "Boss : Lady Démona": "Vieux Granval",
    # Boss Laure/Marge situés à Vieil Ourcival (passé) — Doteos 2026-07-19
    "Boss : Laure": "Vieil Ourcival",
    "Boss : Marge": "Vieil Ourcival",
    # Clinique du Crépuscule : marqueur hôte affiché sur la carte Quartier des boutiques
    "Clinique du Crépuscule - Coffre 01": "Quartier des boutiques",
    # Quête La clinique hantée : au Centre-ville (Doteos 2026-07-19)
    "Requête : La clinique hantée": "Centre-ville de Granval",
}
# Checks affichés sur PLUSIEURS cartes à la fois (un marqueur par carte, même
# check). Clé = check ; valeur = liste de (map_id, x, y). map_id = "det_<slug
# de région>" ; ex. "det_les_hauts_de_granval", "det_egouts".
MULTI_MAP_COORDS = {
    # Égouts entrée B : accessible depuis Les Hauts -> marqueur sur les 2 cartes
    "Égouts - Coffre 03": [
        ("det_les_hauts_de_granval", 120, 477),  # B9 coin haut-droit
        ("det_egouts", 330, 425),                # F8 milieu-droit
    ],
    # Coffre 01/02 : accès Passage des matous -> Les Hauts (près E6) + Égouts
    "Égouts - Coffre 01": [
        ("det_les_hauts_de_granval", 250, 320),  # près Passage des matous
        ("det_egouts", 500, 443),                # (à recaler avec le picker)
    ],
    "Égouts - Coffre 02": [
        ("det_les_hauts_de_granval", 290, 320),  # près Passage des matous
        ("det_egouts", 344, 305),                # picker Doteos 2026-07-19
    ],
    # Égouts côté Corniche : 06 et 07 séparés sur la carte Égouts (pins distincts,
    # picker Doteos), côte à côte sur la Corniche (léger décalage).
    "Égouts - Coffre 06": [
        ("det_egouts", 440, 242),                # picker Doteos 2026-07-19
        ("det_la_corniche", 435, 424),
    ],
    "Égouts - Coffre 07": [
        ("det_egouts", 298, 289),                # picker Doteos 2026-07-19
        ("det_la_corniche", 435, 424),           # MÊME point que 06 -> 1 marqueur
    ],
    # Méga toboggan (relie Corniche <-> Mont Sylvestre) : marqueur sur les 2 cartes
    # (Coffre 01 fusionné dessus via MERGE_INTO).
    "Corniche (Méga toboggan) - Coffre 02": [
        ("det_la_corniche", 468, 351),           # entrée toboggan (Corniche)
        ("det_mont_sylvestre", 586, 424),        # picker Doteos 2026-07-19
    ],
    "Corniche (Méga toboggan) - Coffre 01": [
        ("det_la_corniche", 468, 351),           # MÊME point Corniche que le 02
        ("det_mont_sylvestre", 538, 359),        # picker Doteos 2026-07-19
    ],
    "Corniche (Méga toboggan) - Coffre 03": [
        ("det_la_corniche", 468, 351),           # MÊME point Corniche
        ("det_mont_sylvestre", 541, 379),        # picker Doteos 2026-07-19
    ],
    # Égouts accès Centre-ville : pins séparés sur Égouts, même point Centre-ville
    "Égouts - Coffre 08": [
        ("det_egouts", 476, 555),                # Pièce mauve
        ("det_centre_ville_de_granval", 794, 595),
    ],
    "Égouts - Coffre 09": [
        ("det_egouts", 410, 511),                # La vie en tête
        ("det_centre_ville_de_granval", 794, 595),  # MÊME point que le 08
    ],
    # Égouts accès Quartier des boutiques
    "Égouts - Coffre 10": [
        ("det_egouts", 173, 549),                # Pièce bleue
        ("det_quartier_des_boutiques", 266, 169),  # même endroit que le Coffre 06
    ],
    "Égouts - Coffre 11": [
        ("det_egouts", 220, 490),                # Tech. tip-top
        ("det_quartier_des_boutiques", 266, 169),  # même endroit que le Coffre 06
    ],
    # Égouts accès Coteau fleuri
    "Égouts - Coffre 12": [
        ("det_egouts", 252, 432),                # Coups secrets
        ("det_coteau_fleuri", 410, 399),
    ],
    "Égouts - Coffre 13": [
        ("det_egouts", 153, 422),                # Billet de loterie (sous-zone Coteau)
        ("det_coteau_fleuri", 239, 514),
    ],
    # Ruelle obscure : Les Hauts (G11) + Égouts (picker)
    "Égouts - Coffre 04": [
        ("det_les_hauts_de_granval", 405, 630),  # G11, léger gauche
        ("det_egouts", 441, 479),                # picker Doteos 2026-07-19
    ],
    "Égouts - Coffre 05": [
        ("det_les_hauts_de_granval", 441, 630),  # G11, léger droite
        ("det_egouts", 344, 484),                # picker Doteos 2026-07-19
    ],
}

# Les coffres des ÉGOUTS ne gardent QUE leur marqueur sur la carte Égouts
# (Doteos 2026-07-27 : « les double check des égouts sur les autres maps,
# c'est pas une bonne idée »). Les doublons sur les cartes des quartiers
# d'accès (Les Hauts, Corniche, Centre-ville, Boutiques, Coteau) sont donc
# retirés à la génération — les coordonnées restent ci-dessus si on veut les
# rétablir un jour. Le Méga toboggan garde ses 2 cartes (Corniche <-> Mont
# Sylvestre) : c'est un vrai passage entre deux zones, pas un doublon.
for _mk, _mv in list(MULTI_MAP_COORDS.items()):
    if _mk.startswith("Égouts - "):
        MULTI_MAP_COORDS[_mk] = [_t for _t in _mv if _t[0] == "det_egouts"]
# Position (x, y) de chaque check sur sa carte de zone détaillée. À remplir
# avec Doteos (il pointe, on note). Clé = nom EXACT du check.
CHECK_COORDS = {
    # Les Hauts de Granval — 10 coffres placés d'après les PINGS de
    # l'annotation Doteos (2026-07-17, relecture cases). Carte 586x700.
    "Les Hauts de Granval - Coffre 01": (250, 67),   # D2 coin haut-droit
    "Les Hauts de Granval - Coffre 02": (380, 185),  # F4 coin haut-droit
    "Les Hauts de Granval - Coffre 03": (293, 379),  # E7 milieu
    "Les Hauts de Granval - Coffre 04": (488, 573),  # H10 milieu-bas
    "Les Hauts de Granval - Coffre 05": (335, 379),  # F7 milieu-gauche
    "Les Hauts de Granval - Coffre 06": (400, 458),  # G8 coin bas-gauche
    "Les Hauts de Granval - Coffre 07": (140, 360),  # C7 haut-gauche
    "Les Hauts de Granval - Coffre 08": (510, 612),  # H11 milieu-droit
    "Les Hauts de Granval - Coffre 09": (358, 632),  # F11 milieu-bas
    "Les Hauts de Granval - Coffre 10": (335, 437),  # F8 milieu-gauche
    # Quêtes des Hauts (cases Doteos 2026-07-17)
    "Requête : Courage, Max !":            (270, 204),  # E4 milieu-gauche
    "Requête : Ça attire les clients !":   (270, 340),  # E6 coin bas-gauche
    "Requête : Officiellement officiel !": (315, 282),  # E5 coin bas-droit
    "Service : Sous un soleil de plomb":   (465, 496),  # H9 milieu-gauche
    "Service : A la chasse aux insectes !": (264, 304),  # Mont Sylvestre (Doteos 2026-07-24)
    "Requête : C1- Grand Prix":            (183, 237),  # picker Doteos 2026-07-19
    # Tour Excellence — carte tour exelence.jpg 680x525 (picker Doteos 2026-07-19)
    "Tour Excellence - Coffre 01": (343, 226),  # Carte cadeau musique x2 (bit 1207)
    "Tour Excellence - Coffre 03": (360, 298),  # Sec. hors-série (livre combat, bit 1209)
    "Tour Excellence - Coffre 02": (346, 371),  # Curry de la mer (bit 1208)
    "Tour Excellence - Coffre 05": (267, 367),  # Grand EXPorbe (bit 1211)
    "Tour Excellence - Coffre 04": (235, 319),  # Badge brillant (bit 1210)
    # Quêtes Tour Excellence (picker Doteos 2026-07-19)
    "Requête : Tous à bord": (322, 369),
    "Requête : Un look trop sophistiqué": (334, 356),
    "Requête : La star de Granval 2": (62, 249),
    # Ourcival — carte ourcival.jpg 1182x1161 (picker Doteos 2026-07-19)
    "Ourcival - Coffre 01": (508, 316),  # Remède amer (bit 1218)
    "Ourcival - Coffre 05": (518, 364),  # Concombre x10 (bit 1222)
    "Ourcival - Coffre 03": (491, 394),  # Étoile dansante (bit 1220)
    "Ourcival - Coffre 04": (514, 463),  # Poupée bronze x2 (bit 1221)
    "Ourcival - Coffre 02": (614, 461),  # Lait merveilleux (bit 1219)
    "Ourcival - Coffre 07": (625, 504),  # Carotte x10 (bit 1224)
    "Ourcival - Coffre 08": (691, 491),  # Pomme d'amour x2 (bit 1225)
    "Ourcival - Coffre 10": (487, 545),  # Granité x2 (bit 1227)
    "Ourcival - Coffre 09": (425, 515),  # Pièce mauve (bit 1226)
    "Ourcival - Coffre 06": (424, 322),  # EXPorbe moyen x2 (bit 1223)
    "Ourcival - Coffre 11": (96, 460),  # EXPorbe moyen (bit 1241)
    "Ourcival - Coffre 12": (144, 461),  # Talisman de force x2 (bit 1242)
    # Mont de l'Ours (présent) = Rochers de face + Canyon de la cigale (carte Ourcival)
    "Ourcival (Rochers de face) - Coffre 02": (1081, 988),  # Amul. protectrice (bit 1245)
    "Ourcival (Rochers de face) - Coffre 03": (992, 1004),  # Mélasse x5 (bit 1246)
    "Ourcival (Rochers de face) - Coffre 01": (1033, 939),  # Talisman d'esprit x2 (bit 1244)
    "Ourcival (Canyon de la cigale) - Coffre 02": (1045, 814),  # Sec. hors-série (bit 1248)
    "Ourcival (Canyon de la cigale) - Coffre 01": (955, 769),  # Staminum Alpha x2 (bit 1247)
    "Ourcival (Canyon de la cigale) - Coffre 03": (1098, 830),  # Poupée d'argent (bit 1249)
    "Mont de l'Ours (présent) - Coffre 01": (1057, 509),  # Docteur Tit'ange (bit 1250, carte Ourcival)
    "Parvis de la gare d'Ourcival - Coffre 01": (634, 1127),  # Lait merveilleux (bit 1258)
    "Parvis de la gare d'Ourcival - Coffre 02": (719, 1103),  # Bague mimi (bit 1257)
    "Parvis de la gare d'Ourcival - Coffre 03": (610, 933),  # Clé appartement C-302 (bit 1256)
    "Parvis de la gare d'Ourcival - Coffre 04": (680, 844),  # Vivez Karaté (livre combat, bit 1251)
    "Parvis de la gare d'Ourcival - Coffre 05": (716, 799),  # Morceau de lard (bit 1252)
    # Vieil Ourcival (passé) — carte vieux ourcival.jpg 460x680 (picker Doteos 2026-07-19)
    "Vieil Ourcival - Coffre 07": (339, 532),  # Badge mignon (bit 1339)
    "Vieil Ourcival - Coffre 08": (342, 567),  # Pièce verte (bit 1335)
    "Vieil Ourcival - Coffre 04": (271, 566),  # EXPorbe moyen (bit 1336)
    "Vieil Ourcival - Coffre 05": (203, 534),  # Anneau arc-en-ciel (bit 1337)
    "Vieil Ourcival - Coffre 09": (218, 497),  # Pièce rose (bit 1340, Temple des songes)
    "Vieil Ourcival - Coffre 02": (246, 505),  # Étoile dansante x2 (bit 1334)
    "Vieil Ourcival - Coffre 06": (190, 415),  # Concombre x10 (bit 1338)
    "Vieil Ourcival - Coffre 03": (282, 459),  # Lait aux fruits x3 (bit 1332)
    "Vieil Ourcival - Coffre 01": (301, 506),  # Carotte x10 (bit 1333)
    # Vieux Granval (passé) — carte vieux granval.jpg 680x583 (picker Doteos 2026-07-19)
    "Vieux Mont Sylvestre - Coffre 01": (411, 90),  # Pièce verte (bit 1326)
    "Vieux Hauts de Granval - Coffre 03": (423, 248),  # Pièce rouge (bit 1303)
    "Vieux Hauts de Granval - Coffre 04": (415, 292),  # Tenue de rocker (objet-clé, bit 1304)
    "Vieux Hauts de Granval - Coffre 02": (464, 327),  # Grelot brisé (bit 1302)
    "Vieux Hauts de Granval - Coffre 01": (462, 366),  # Bracelet de force (bit 1299)
    "Vieux Hauts de Granval - Coffre 05": (447, 405),  # EXPorbe moyen (bit 1300)
    "Vieille Ferronnerie de Granval - Coffre 02": (655, 413),  # Remède amer (bit 1325)
    "Vieille Ferronnerie de Granval - Coffre 01": (534, 436),  # Poupée d'argent (bit 1324)
    "Vieux Hauts de Granval (retour Ch10) - Coffre 01": (406, 460),  # Grand EXPorbe (bit 1301)
    "Chemin du Puits - Coffre 01": (518, 187),  # EXPorbe moyen (bit 1321)
    "Vieux Coteau Fleuri - Coffre 02": (360, 329),  # Pièce jaune (bit 1306)
    "Vieux Coteau Fleuri - Coffre 04": (347, 398),  # Remède amer (bit 1308)
    "Vieux Coteau Fleuri - Coffre 03": (313, 387),  # Badge brillant (bit 1307)
    "Chemin du Sanctuaire du Renard - Coffre 01": (309, 537),  # Amul. protectrice (bit 1319)
    "Lac des Coloquintes (passé) - Coffre 01": (587, 276),  # Pièce orange (bit 1329)
    "Vieux Coteau Fleuri - Coffre 01": (293, 275),  # Poupée bronze x3 (bit 1305)
    # Plaines Plinpot (sur la carte Vieux Granval, picker Doteos 2026-07-19)
    "Plaines Plinpot - Coffre 01": (151, 315),  # Anneau illusion (bit 1361)
    "Plaines Plinpot - Coffre 04": (151, 351),  # Tech. tip-top (livre combat, bit 1364)
    "Plaines Plinpot - Coffre 02": (195, 381),  # Méga EXPorbe (bit 1362)
    "Plaines Plinpot - Coffre 05": (147, 370),  # Bracelet de bouffi (bit 1365)
    "Plaines Plinpot - Coffre 06": (101, 409),  # Remède puiss. (bit 1366)
    "Plaines Plinpot - Coffre 07": (52, 407),  # Secrets de l'âme (livre combat, bit 1367)
    "Plaines Plinpot - Coffre 10": (49, 383),  # Bracelet majest. (bit 1370)
    "Plaines Plinpot - Coffre 08": (45, 359),  # Bracelet de farceur (bit 1368)
    "Plaines Plinpot - Coffre 09": (25, 322),  # Coups secrets (livre combat, bit 1369)
    "Plaines Plinpot - Coffre 11": (127, 326),  # Grand EXPorbe (bit 1371)
    # Quêtes / service / objets-clés Vieux Granval (picker Doteos 2026-07-19)
    "Service : Un entraînement de star": (448, 332),
    "Objet-clé : Lettre de Komasan": (373, 518),
    "Requête : Querelles gourmandes": (374, 338),
    "Requête : Pièce sanctuaire": (407, 130),  # + Grelot de félin
    "Requête : Pièce ferronnerie": (464, 416),  # + Bille mystérieuse
    "Requête : Blues du déménagement": (362, 301),
    "Requête : Pièce Au Phil du temps": (316, 179),  # + Montre de luxe
    "Requête : Un amour perdu": (532, 470),  # sur la carte Ourcival
    "Boss : Lady Démona": (446, 448),  # boss final (+ Lady Perpétua fusionnée)
    # San Fantastico — carte san fantastico.jpg 680x514 (picker Doteos 2026-07-19)
    "San Fantastico - Coffre 12": (236, 198),  # Poupée d'argent (bit 1271)
    "San Fantastico - Coffre 14": (244, 260),  # Anneau féérique (bit 1270)
    "San Fantastico - Coffre 15": (236, 302),  # Thon 1er choix (bit 1272)
    "San Fantastico - Coffre 02": (253, 301),  # Sushi thon rouge (bit 1260)
    "San Fantastico - Coffre 01": (199, 353),  # Pièce bleue (bit 1259)
    "San Fantastico (rang C) - Coffre 01": (78, 452),  # Talisman de déf. x2 (bit 1287)
    "San Fantastico - Coffre 03": (300, 349),  # Talisman d'esprit x2 (bit 1261)
    "San Fantastico - Coffre 05": (319, 327),  # Lait merveilleux (bit 1263)
    "San Fantastico - Coffre 06": (320, 304),  # Secrets de l'âme (livre combat, bit 1264)
    "San Fantastico - Coffre 07": (283, 322),  # Billet de loterie x2 (bit 1265)
    "San Fantastico - Coffre 08": (298, 317),  # EXPorbe moyen x2 (bit 1266)
    "San Fantastico - Coffre 04": (374, 321),  # Teigne parfaite (livre combat, bit 1262)
    "San Fantastico - Coffre 10": (433, 337),  # Oursin cru (bit 1268)
    "San Fantastico - Coffre 09": (412, 362),  # Curry de la mer (bit 1267)
    "San Fantastico - Coffre 11": (412, 307),  # Remède amer (bit 1269)
    "Grotte du littoral - Coffre 02": (618, 297),  # Étoile dansante x2 (bit 1291)
    "Grotte du littoral - Coffre 01": (594, 359),  # Poupée de fuite x3 (bit 1290)
    "Grotte du littoral - Coffre 03": (567, 349),  # Grand EXPorbe (bit 1292)
    "Grotte du littoral - Coffre 04": (496, 372),  # Crevette piment (bit 1293)
    "Grotte du littoral - Coffre 07": (487, 309),  # Techni-clopédie (livre combat, bit 1296)
    "Grotte du littoral - Coffre 08": (482, 338),  # Sériole x3 (bit 1297)
    "Grotte du littoral - Coffre 06": (542, 293),  # Oursin cru x2 (bit 1295)
    "Grotte du littoral - Coffre 05": (588, 326),  # Poupée d'argent (bit 1294)
    "Grotte du littoral - Coffre 09": (644, 305),  # Bracelet majest. (bit 1298)
    "San Fantastico - Coffre 13": (309, 130),  # Grand EXPorbe (bit 1285)
    "San Fantastico - Coffre 16": (345, 174),  # Clé appartement C-303 (bit 1420)
    # Boss / quêtes / service San Fantastico (picker Doteos 2026-07-19)
    "Boss : Barbefrousse": (563, 273),
    "Requête : Virée en mer !": (217, 335),
    "Requête : Super cache-cache": (413, 340),
    "Requête : C1- Grand Prix A": (292, 337),
    "Service : Un matou en détresse": (244, 282),
    "Boss : Laure": (135, 325),  # Vieil Ourcival (+ Marge fusionnée)
    # Quêtes / objet-clé Vieil Ourcival (picker Doteos 2026-07-19)
    "Requête : Le meilleur scarabée": (321, 537),
    "Requête : Épreuves de Nyada IV": (222, 278),
    "Requête : Épreuves de Nyada V": (203, 164),
    "Requête : Épreuves de Nyada VI": (229, 87),
    "Objet-clé : Modèle zéro": (134, 253),
    "Objet-clé : Clé magnétique or": (441, 253),  # égouts, fin « La base secrète »
    "Boss : Didgeai": (336, 276),  # Coteau fleuri, fin « Chasse nocturne » (Doteos)
    "Boss : Sabroclair": (388, 846),  # La Corniche, quête « Une armure sinistre » (Doteos)
    "Boss : Ombraptor": (208, 491),   # Centre-ville, quête « Le géant fantôme » (Doteos)
    "Boss : Inamygal": (793, 441),    # école élémentaire, quête « Ectoplasmes à l'école »
    # Corniche > Musée (nuit), RE Doteos 2026-07-24 :
    "Corniche (Musée) - Coffre 01": (472, 952),
    "Corniche (Musée) - Coffre 02": (367, 1041),
    "Corniche (Musée) - Coffre 03": (315, 1061),
    "Corniche (Musée) - Coffre 04": (262, 1005),
    "Corniche (Musée) - Coffre 05": (495, 1001),
    "Corniche (Musée) - Coffre 06": (495, 1047),
    "Corniche (Musée) - Coffre 07": (630, 1059),
    "Corniche (Musée) - Coffre 08": (706, 1051),
    # Tunnel abandonné (salle du trésor), Mont Sylvestre, RE Doteos 2026-07-24 :
    "Tunnel abandonné (salle du trésor) - Coffre 01": (189, 108),
    "Tunnel abandonné (salle du trésor) - Coffre 02": (185, 81),
    "Tunnel abandonné (salle du trésor) - Coffre 03": (150, 84),
    "Tunnel abandonné (salle du trésor) - Coffre 06": (165, 120),
    "Tunnel abandonné (salle du trésor) - Coffre 07": (155, 137),
    "Tunnel abandonné (salle du trésor) - Coffre 08": (201, 133),
    "Boss : Volteface": (172, 85),
    # Tunnel abandonné est (après Draconfus), RE Doteos 2026-07-24 :
    "Tunnel abandonné est - Coffre 01": (326, 153),
    "Tunnel abandonné est - Coffre 02": (368, 107),
    "Tunnel abandonné est - Coffre 03": (372, 143),
    "Tunnel abandonné est - Coffre 04": (308, 74),
    "Tunnel abandonné est - Coffre 05": (357, 81),
    "Tunnel abandonné est - Coffre 06": (338, 89),
    "Boss : Misterre": (235, 192),
    "Boss : Démophage": (227, 85),   # Vieil Ourcival, quête « Épreuves de Nyada VI » (Doteos)
    "Boss : Injustin": (100, 367),   # Vieux Granval, Ch9 (Doteos)
    "Boss : Fielippine": (409, 253), # Vieux Granval, Ch9 (Doteos)
    "Boss : Cyrustre": (633, 292),   # Vieux Granval, Ch9 (Doteos)
    "Boss : Maudicko": (345, 399),   # Vieux Granval, Ch9 (Doteos)
    "Boss : Ronéan": (473, 418),     # Vieux Granval, Ch9 (Doteos)
    # Tablo-blabla capturés (RE Doteos 2026-07-24/25) :
    "Tablo-blabla n°01 : Granpapéti": (261, 350),
    "Tablo-blabla n°02 : Feulion": (496, 656),
    "Tablo-blabla n°03 : Triptic-tac": (292, 296),
    "Tablo-blabla n°04 : Robonyan": (366, 162),
    "Tablo-blabla n°05 : Draconfus": (206, 118),
    "Tablo-blabla n°08 : Ronimpec": (409, 359),
    "Tablo-blabla n°09 : Sumochi": (466, 374),
    "Tablo-blabla n°11 : Hiblusion": (500, 426),
    "Tablo-blabla n°12 : Maître Oden": (616, 211),
    "Tablo-blabla n°16 : Grégrigry": (480, 391),
    "Tablo-blabla n°17 : Chaipô": (75, 399),
    "Tablo-blabla n°18 : Croquin": (196, 202),
    "Tablo-blabla n°19 : Supernoël": (324, 128),
    "Tablo-blabla n°20 : Noripop": (625, 324),      # Grotte du littoral (Doteos)
    "Tablo-blabla n°21 : Wakapoeira": (548, 378),   # Grotte du littoral (Doteos)
    "Tablo-blabla n°22 : Salsalga": (495, 293),     # Grotte du littoral (Doteos)
    # Zone des portails : donjons atteints depuis La Corniche (marqueurs sur sa carte)
    "Zone des portails - Coffre 01": (850, 918),    # 10 globes (Doteos)
    "Zone des portails - Coffre 02": (885, 913),    # 20 globes (Doteos)
    "Zone des portails - Coffre 03": (879, 772),    # 20 globes (Doteos)
    "Zone des portails - Coffre 04": (1095, 948),   # 30 globes (Doteos)
    "Zone des portails - Coffre 05": (1091, 914),   # 30 globes (Doteos)
    "Zone des portails - Coffre 06": (1090, 878),   # 30 globes (Doteos)
    "Zone des portails - Coffre 07": (1096, 846),   # 30 globes (Doteos)
    "Zone des portails - Coffre 08": (1097, 819),   # 30 globes (Doteos)
    "Zone des portails - Coffre 09": (1090, 790),   # 30 globes (Doteos)
    "Zone des portails - Coffre 10": (1168, 843),   # 40 globes, Salle des portails
    # Tablos de la Salle des portails (40 globes) — carte La Corniche
    "Tablo-blabla n°13 : Cupistol": (1166, 967),    # quiz rdc (Doteos)
    "Tablo-blabla n°14 : Cigalopin": (1169, 827),   # quiz 1er étage (Doteos)
    "Tablo-blabla n°15 : Chiperpiou": (1167, 733),  # quiz 2e étage (Doteos)
    "Boss : Tromplœil": (987, 928),                 # Zone des portails, 100 globes
    "Vieil Ourcival - Coffre 10": (102, 523),  # Clé appartement B-301 (bit 1351)
    "Vieux Mont de l'Ours - Coffre 04": (208, 362),  # Pièce mauve (bit 1353)
    "Vieux Mont de l'Ours - Coffre 01": (252, 339),  # Carte cadeau musique x2 (bit 1354)
    "Vieux Mont de l'Ours - Coffre 02": (201, 320),  # Bracelet rocker (bit 1355)
    "Vieux Mont de l'Ours - Coffre 03": (264, 202),  # Pièce bleu ciel (bit 1357)
    "Vieux Mont de l'Ours - Coffre 05": (226, 178),  # Remède puiss. (bit 1356)
    # Quêtes / boss / services / objets-clés Ourcival (picker Doteos 2026-07-19)
    "Boss : Méganyan": (581, 381),
    "Requête : Secrets de l'Âmechimie": (441, 452),
    "Requête : Pas le temps de pêcher !": (452, 308),  # + Faux Kappa + Canne à pêche
    "Requête : Vrai cache-cache": (596, 458),
    "Requête : Trouvons Parasolal !": (1066, 823),
    "Requête : Trouvons Lulutin !": (706, 170),
    "Requête : Trouvons Métaureaulog !": (441, 474),
    "Requête : Trouvons Sirénée !": (965, 281),
    "Requête : Votre mascotte locale": (659, 772),
    "Service : Espiégleries": (560, 406),
    "Service : Coup de foudre": (702, 812),
    "Objet-clé : Cartes d'Ultramax": (613, 381),
    "Boss : Tourbœillon":                  (33, 321),   # A6 milieu
    # Passage des matous (+ Égouts fusionnés) et Allée sinistre
    "Les Hauts de Granval (Passage des matous) - Coffre 01": (270, 302),  # E6 h-g
    "Allée sinistre - Coffre 01":          (270, 48),   # E1 coin bas-gauche
    "Ruelle obscure - Coffre 01":          (423, 613),  # G11 milieu-haut
    # --- École élémentaire (nuit) : carte 1230x540, 18 cols A-R x 8 rows ---
    # centre de case : x=(col+0.5)*68.33, y=(row-0.5)*67.5
    "École élémentaire de Granval (nuit) - Coffre 01": (1059, 417),  # P7
    "École élémentaire de Granval (nuit) - Coffre 02": (922, 417),   # N7
    "École élémentaire de Granval (nuit) - Coffre 03": (695, 417),   # K7
    "École élémentaire de Granval (nuit) - Coffre 04": (1059, 287),  # P5
    "École élémentaire de Granval (nuit) - Coffre 05": (666, 169),   # J3
    "École élémentaire de Granval (nuit) - Coffre 06": (939, 180),   # N3
    "École élémentaire de Granval (nuit) - Coffre 07": (1059, 169),  # P3
    "École élémentaire de Granval (nuit) - Coffre 08": (1042, 45),   # P1
    "École élémentaire de Granval (nuit) - Coffre 09": (125, 485),   # B8
    "École élémentaire de Granval (nuit) - Coffre 11": (359, 456),   # F7
    "École élémentaire de Granval (nuit) - Coffre 12": (466, 518),   # G8
    "École élémentaire de Granval (nuit) - Coffre 13": (466, 326),   # G5
    "École élémentaire de Granval (nuit) - Coffre 10": (283, 462),   # E7 bas-g
    "Boss : Grolos":               (376, 169),  # F3 milieu
    "Requête : Méga cache-cache":  (683, 169),  # entre J3 et K3 milieu
    "Objet-clé : Clés de l'école": (1059, 462),  # P7 milieu-bas
    # --- Égouts : Coffre 01/02 (matous) + 08/09 (Centre-ville) -> MULTI_MAP (plus bas) ---
    # --- La Corniche : carte 1200x1138, 12 cols A-L x 11 rows (cw=100, ch=103.5) ---
    # Positions pixel exactes (outil coord_picker.html, Doteos 2026-07-19)
    "Corniche - Coffre 01": (603, 631),  # Fraisier
    "Corniche - Coffre 02": (556, 491),  # La déf. de A à Z
    "Corniche - Coffre 04": (504, 474),  # Poupée bronze
    "Corniche - Coffre 05": (544, 447),  # Petit EXPorbe
    "Corniche - Coffre 03": (550, 336),  # Étoile dansante
    "Corniche - Coffre 06": (647, 580),  # Docteur Tit'ange (livre combat)
    # Mont Sylvestre accès égouts (rang C) — carte mont sylvestre.jpg 639x680
    "Mont Sylvestre (accès égouts) - Coffre 01": (282, 341),  # Grand EXPorbe
    "Mont Sylvestre - Coffre 01": (348, 293),  # Din's Pearl (Capt.)
    "Sommet du Mont Sylvestre - Coffre 01": (487, 267),  # Étoile dansante
    "Sentier de randonnée - Coffre 01": (427, 360),  # Piece of Heart (C.)
    # Quêtes Mont Sylvestre (picker Doteos 2026-07-19)
    "Requête : Spécialiste des cigales": (316, 412),  # + La reine des cigales
    "Requête : Voyage de l'envoûtement": (305, 376),
    "Requête : Le prix du fer": (482, 263),
    "Objet-clé : Pile ou passe": (312, 344),  # Mont Sylvestre (picker Doteos)
    # Coteau fleuri — carte coteau fleuri.jpg 680x680 (picker Doteos 2026-07-19)
    "Côté fleuri - Coffre 03": (371, 321),  # Billet de loterie (bit 1015)
    "Côté fleuri - Coffre 02": (418, 367),  # Pomme d'amour (bit 1014)
    "Côté fleuri - Coffre 01": (410, 395),  # Amulette antique (bit 1013)
    "Côté fleuri - Coffre 05": (338, 402),  # Tout sur la déf. (livre combat, bit 1017)
    "Côté fleuri - Coffre 04": (343, 366),  # Talisman d'esprit (bit 1016)
    "Côté fleuri - Coffre 06": (279, 374),  # Pièce bleu ciel (bit 1019)
    "Coteau fleuri (rang B) - Coffre 01": (301, 462),  # Amulette armure (bit 1035)
    "Côté fleuri - Coffre 07": (397, 183),  # Poupée bronze (bit 1033)
    "Coteau fleuri (présent) - Coffre 01": (166, 402),  # Anneau horrible (bit 1037)
    "Coteau fleuri (rang C) - Coffre 01": (331, 353),  # Anneau illusion (bit 1018, rang C)
    "Manoir (Coteau fleuri) - Coffre 02": (292, 664),  # Riz œufs saumon (bit 1045)
    "Manoir (Coteau fleuri) - Coffre 05": (473, 586),  # Techni-clopédie (livre combat, bit 1050)
    "Manoir (Coteau fleuri) - Coffre 01": (179, 559),  # Riz à la crevette (bit 1042)
    "Manoir (Coteau fleuri) - Coffre 04": (459, 618),  # Billet de loterie (bit 1049)
    "Manoir (Coteau fleuri) - Coffre 06": (516, 635),  # Jolie petite clé (objet-clé natif, bit 1051)
    "Manoir (Coteau fleuri) - Coffre 03": (286, 592),  # Amul. protectrice (bit 1046)
    "Manoir arrière (Coteau fleuri) - Coffre 01": (153, 609),  # Billet de loterie (bit 1041, Clé de derrière)
    "Manoir arrière (Coteau fleuri) - Coffre 02": (414, 568),  # Bracelet majest. (bit 1047)
    "Manoir arrière (Coteau fleuri) - Coffre 03": (411, 623),  # Vivez Karaté (livre combat, bit 1048)
    "Manoir arrière (Coteau fleuri) - Coffre 04": (171, 622),  # Jolie grande clé (objet-clé natif, bit 1043)
    "Manoir arrière (Coteau fleuri) - Coffre 05": (215, 598),  # Pièce jaune (bit 1044)
    # Quêtes / rangs / service / objets-clés Coteau fleuri (picker Doteos 2026-07-19)
    "Obtenons le rang C !": (404, 377),  # + rang B + rang A fusionnés
    "Requête : Bam boum ! Fusion !": (201, 282),
    "Requête : Super Balaise : l'origine": (579, 376),  # + le retour fusionné
    "Requête : Soirée chaotique": (389, 400),
    "Requête : Chasse nocturne": (379, 312),
    "Requête : Les sources de l'amitié": (412, 358),
    "Service : Une envie de bonbons": (387, 322),
    "Objet-clé : Herbe ancestrale": (368, 417),
    "Objet-clé : Documents perdus": (404, 417),
    "Objet-clé : Clé de derrière": (237, 660),
    # Centre-ville de Granval — carte centre-ville.jpg 873x900 (coords rescalées
    # x0.773 depuis le picker sur l'ancienne map 1129x1164, Doteos 2026-07-19)
    "Centre-ville de Granval - Coffre 04": (532, 295),  # Talisman de vitesse (bit 1085)
    "Centre-ville de Granval - Coffre 07": (589, 350),  # EXPorbe moyen (bit 1088)
    "Centre-ville de Granval - Coffre 06": (632, 418),  # Crêpes nappées (bit 1087)
    "Centre-ville de Granval - Coffre 05": (533, 392),  # Pièce orange (bit 1086)
    "Centre-ville de Granval - Coffre 03": (482, 410),  # Secours mag #7 (livre combat, bit 1084)
    "Centre-ville de Granval - Coffre 01": (441, 418),  # Badge noir (bit 1082)
    "Centre-ville de Granval - Coffre 02": (406, 377),  # Petits pois neige (bit 1083)
    "Centre-ville de Granval - Coffre 08": (759, 578),  # Bracelet en toc (bit 1105)
    "Centre-ville de Granval (sous-zone) - Coffre 01": (244, 435),  # Double burger (bit 1103)
    # Quêtes / service / objet-clé Centre-ville (rescalées x0.773)
    "Requête : La star de Granval 1": (824, 151),
    "Requête : Je veux grandir": (605, 425),
    "Requête : Un super fan-club": (676, 100),
    "Requête : Qui est cette fille": (508, 338),
    "Service : La malade imaginaire": (346, 101),
    "Objet-clé : Foli-pili": (297, 345),
    # Quartier des boutiques — carte quartier des boutique.png 757x541 (picker Doteos)
    "Granval (Quartier des boutiques) - Coffre 03": (626, 212),  # Pièce jaune (bit 1117)
    "Granval (Quartier des boutiques) - Coffre 05": (453, 181),  # Amul. vieillotte (bit 1119)
    "Granval (Quartier des boutiques) - Coffre 04": (721, 102),  # Oursin cru (bit 1118)
    "Granval (Quartier des boutiques) - Coffre 02": (388, 327),  # Petite teigne (livre combat, bit 1116)
    "Granval (Quartier des boutiques) - Coffre 01": (166, 386),  # Progressive Magic Me (bit 1115)
    "Quartier des boutiques (appartement C-303) - Coffre 01": (180, 428),  # Sabre déchaîné (bit 1138)
    "Granval (Quartier des boutiques) - Coffre 06": (266, 169),  # Vivez Karaté (livre combat, bit 1133)
    # Clinique du Crépuscule : tous ses checks sur UN marqueur (Doteos 2026-07-19)
    "Clinique du Crépuscule - Coffre 01": (528, 445),
    "Requête : La clinique hantée": (410, 423),  # Centre-ville (picker Doteos 2026-07-19)
    # Quêtes / services / objets-clés Quartier des boutiques (picker Doteos 2026-07-19)
    "Requête : Nouveau look": (346, 149),
    "Requête : Agonigiri a des soucis": (423, 172),
    "Requête : Prix de Gastronomie": (239, 215),
    "Requête : Triangle amoureux": (542, 227),
    "Requête : Coup de bluff": (67, 405),
    "Service : Que de balivernes": (231, 120),
    "Objet-clé : Super tournevis": (306, 165),
    "Beignets du chapitre 4": (290, 229),
    "Objet-clé : Vélo": (405, 417),  # spot vélo, Coteau fleuri (Doteos)
    "Tour du commerce (3e étage, rang A) - Coffre 01": (486, 654),  # Clé magnétique bleue (bit 1107)
    "Tour du commerce (3e étage) - Coffre 01": (554, 682),  # Staminum Alpha (bit 1108)
    "Tour du commerce (3e étage) - Coffre 03": (551, 660),  # Poupée d'argent (bit 1110)
    "Tour du commerce (3e étage) - Coffre 02": (517, 667),  # Anneau arc-en-ciel (bit 1109)
    "Tour du commerce (12e étage) - Coffre 03": (713, 664),  # La vie en tête (livre combat, bit 1113)
    "Tour du commerce (12e étage) - Coffre 02": (686, 658),  # EXPorbe moyen (bit 1112)
    "Tour du commerce (12e étage) - Coffre 01": (645, 680),  # Delivery Bag (Cap.) (bit 1111)
    "Corniche (Maison des Roch) - Coffre 01": (538, 313),  # Poupée d'argent
    # Quêtes de La Corniche (Doteos 2026-07-19)
    "Requête : Les portails mystère": (560, 511),  # + Portail final + Armure sinistre
    "Requête : La base secrète":      (450, 440),  # E5 milieu-haut
    "Requête : Ectoplasmes à l'école": (590, 505),  # F5 coin bas-droite
    "Requête : Tout droit sorti du futur !": (576, 414),  # picker Doteos 2026-07-19
    "Service : Le ventre vide": (522, 551),  # picker Doteos 2026-07-19
}


def make_images(regions_order, key_items):
    from PIL import Image, ImageDraw, ImageFont
    img_dir = OUT / "images"
    img_dir.mkdir(parents=True, exist_ok=True)
    try:
        font = ImageFont.truetype("arialbd.ttf", 22)
        font_icon = ImageFont.truetype("arialbd.ttf", 20)
        font_icon_sm = ImageFont.truetype("arialbd.ttf", 15)
    except OSError:
        font = font_icon = font_icon_sm = ImageFont.load_default()

    def icon(fname, text, bg, fg="#ffffff"):
        im = Image.new("RGBA", (64, 64), bg)
        d = ImageDraw.Draw(im)
        d.rectangle([0, 0, 63, 63], outline="#15181d", width=3)
        f = font_icon if len(text) <= 3 else font_icon_sm
        bbox = d.textbbox((0, 0), text, font=f)
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        d.text(((64 - w) / 2 - bbox[0], (64 - h) / 2 - bbox[1]),
               text, fill=fg, font=f)
        im.save(img_dir / fname)

    icon("rang.png", "R", "#7e57c2")
    icon("chapitre.png", "Ch", "#1e88e5")
    # étapes du rang de montre : images Doteos (tracker_assets/Rang_X.webp)
    # avec fallback lettre générée si absente (ex. C manquant)
    rank_colors = {"E": "#9e9e9e", "D": "#8d6e63", "C": "#43a047",
                   "B": "#fb8c00", "A": "#e53935", "S": "#5e35b1"}
    for letter, color in rank_colors.items():
        placed = False
        for src in [ROOT / "tracker_assets" / f"Rang_{letter}.{ext}"
                    for ext in ("webp", "png", "jpg")] +                    [ROOT / "tracker_assets" / "icons" / f"Rang_{letter}.{ext}"
                    for ext in ("webp", "png", "jpg")]:
            if src.exists():
                raw = Image.open(src).convert("RGBA")
                ratio = min(64 / raw.width, 64 / raw.height)
                raw = raw.resize((max(1, int(raw.width * ratio)),
                                  max(1, int(raw.height * ratio))))
                canvas = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
                canvas.paste(raw, ((64 - raw.width) // 2,
                                   (64 - raw.height) // 2), raw)
                canvas.save(img_dir / f"rang_{letter.lower()}.png")
                placed = True
                break
        if not placed:
            icon(f"rang_{letter.lower()}.png", letter, color)
    # une icône par objet-clé : VRAIE image si fournie dans
    # tracker_assets/icons/<slug>.png, sinon abréviation colorée.
    key_palette = ["#f9a825", "#ef6c00", "#c62828", "#2e7d32", "#00838f",
                   "#4527a0", "#ad1457", "#558b2f", "#6d4c41", "#0277bd"]
    assets = ROOT / "tracker_assets" / "icons"
    for i, key in enumerate(key_items):
        src = assets / f"{slug(key)}.png"
        if src.exists():
            Image.open(src).convert("RGBA").resize((64, 64)).save(
                img_dir / f"key_{slug(key)}.png")
        else:
            icon(f"key_{slug(key)}.png", short_label(key),
                 key_palette[i % len(key_palette)])
    # icônes chapitres 1-11 (rangée du bas) + image vide pour les stats
    Image.new("RGBA", (64, 64), (0, 0, 0, 0)).save(img_dir / "blank.png")
    # tuiles de stats : étiquette dessinée dans l'image, chiffre en overlay
    try:
        f_lbl = ImageFont.truetype("arialbd.ttf", 17)
    except OSError:
        f_lbl = ImageFont.load_default()
    for code, label in (("stat_checked", "Locations Checked"),
                        ("stat_accessible", "Locations Accessible"),
                        ("stat_remaining", "Locations Remaining"),
                        ("stat_chapitres", "Chapitres"),
                        ("stat_criminels", "Yo-criminels")):
        tile = Image.new("RGBA", (210, 58), "#262b33")
        dt = ImageDraw.Draw(tile)
        dt.rounded_rectangle([0, 0, 209, 57], 9, outline="#46505c", width=2)
        dt.text((12, 6), label, fill="#9fb2c0", font=f_lbl)
        tile.save(img_dir / f"{code}.png")

    # Cartes monde (Granval / Vieux Granval) retirées (Doteos 2026-07-19) :
    # tout est sur les cartes détaillées de zone.

    # cartes détaillées par zone (webp -> png, taille conservée)
    detailed = {}
    for region, fname in DETAILED_ZONE_MAPS.items():
        if region not in regions_order:
            continue
        src = ROOT / "tracker_assets" / "map asset" / fname
        im = Image.open(src).convert("RGBA")
        bg = Image.new("RGBA", im.size, "#20242c")
        bg.alpha_composite(im)
        mid = f"det_{slug(region)}"
        bg.convert("RGB").save(img_dir / f"{mid}.png")
        detailed[region] = (mid, im.size[0], im.size[1])

    # cartes de zone dédiées (jpg copiés + marqueur au centre)
    zone_maps = {}
    for region, fname in ZONE_IMAGES.items():
        if region not in regions_order:
            continue
        src = ROOT / "map yo kai watch" / fname
        im = Image.open(src).convert("RGB")
        mid = f"zone_{slug(region)}"
        im.save(img_dir / f"{mid}.png")
        zone_maps[region] = (mid, im.size[0] // 2, im.size[1] // 2)

    # Cartes monde + schéma « autres » retirés (Doteos 2026-07-19) : les
    # checks non positionnés individuellement sont regroupés au coin de leur
    # carte détaillée (voir branche `unplaced`). coords ne sert plus qu'aux
    # éventuelles cartes de zone dédiées (ZONE_IMAGES, actuellement vide).
    coords = {}
    for region, (mid, x, y) in zone_maps.items():
        coords.setdefault(region, []).append((mid, x, y))
    zone_map_pairs = [(mid, region)
                      for region, (mid, _, _) in zone_maps.items()]
    return coords, zone_map_pairs, detailed


# ---------------------------------------------------------------------------
# 4. Génération
# ---------------------------------------------------------------------------
def main():
    mods = _import_pkg()
    loc_mod, items_mod = mods["locations"], mods["items"]
    consts = mods["constants"]

    ALL = loc_mod.ALL_LOCATIONS
    LOC_IDS = loc_mod.LOCATION_NAME_TO_ID
    ITEM_IDS = items_mod.ITEM_NAME_TO_ID
    KEY_ORDER = list(items_mod.KEY_ITEM_GAME_ORDER) + [
        _x for _x in TRACKER_EXTRA_ITEMS
        if _x not in items_mod.KEY_ITEM_GAME_ORDER]
    PROG_RANK = consts.PROGRESSIVE_RANK_ITEM
    RANKS = consts.RANK_ITEM_NAMES
    PROG_CHAP = getattr(consts, "PROGRESSIVE_CHAPTER_ITEM", None)

    reg_req = region_requirements(
        mods["regions"], getattr(consts, "DISTRICT_CHAPTERS", {}),
        getattr(mods["rules"], "DISTRICT_REQUIRED_ITEMS", {}))

    # catégories v1 (tablo/collections/post-game exclus)
    KEEP = {"STORY", "WATCH_RANK", "BOSS", "QUEST", "CHEST", "NATIVE_KEY",
            "CRIMINEL", "EVENT", "TABLO"}
    _DETECTABLE_TABLO_LOCS = set(
        getattr(mods["memory_map"], "TABLO_BIT_TO_LOCATION", {}).values())
    POSTGAME_REGIONS = {"Tunnel sans fin", "Limbes éternelles",
                        "Paradis divin"}

    # Chaîne anti-soft-lock des chapitres (rules.py) : terminer le chapitre N
    # exige ses objets-clés critiques -> reflété sur les checks « Chapitre N ».
    CRITICAL = getattr(items_mod, "CRITICAL_KEY_ITEMS_BY_CHAPTER", {})

    per_region = {}
    for name, data in ALL.items():
        cat = getattr(data.category, "name", str(data.category))
        if cat not in KEEP:
            continue
        # Tablos : ne garder que ceux RE'd (détectables) — les autres ne sont pas
        # dans la seed (inactifs) -> pas de marqueur fantôme.
        if cat == "TABLO" and name not in _DETECTABLE_TABLO_LOCS:
            continue
        if data.region in POSTGAME_REGIONS:
            continue
        if name not in LOC_IDS or name in TRACKER_SKIP_LOCATIONS:
            continue
        region = data.region
        # spots « Objet-clé : X » : affichés dans leur zone de récupération
        # réelle (demande Doteos), plus dans « Menu ».
        if cat == "NATIVE_KEY" and name.startswith("Objet-clé : "):
            region = KEYITEM_SPOT_ZONES.get(name[len("Objet-clé : "):],
                                            region)
        # override d'affichage générique (quêtes déplacées par Doteos)
        region = DISPLAY_REGION_OVERRIDE.get(name, region)
        # les coffres de l'école (nuit) -> carte École dédiée
        if name.startswith("École élémentaire de Granval (nuit)"):
            region = "École élémentaire de Granval"
        # les coffres des égouts -> carte Égouts dédiée
        if name.startswith("Égouts - Coffre"):
            region = "Égouts"
        per_region.setdefault(region, []).append((name, data, cat))

    regions_order = sorted(per_region, key=lambda r: (
        reg_req.get(r, (99, 0, frozenset()))[0], r))

    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "items").mkdir(parents=True)
    (OUT / "locations").mkdir()
    (OUT / "layouts").mkdir()
    (OUT / "maps").mkdir()
    (OUT / "scripts").mkdir()

    coords, zone_map_pairs, detailed = make_images(regions_order, KEY_ORDER)
    zone_map_ids = [mid for mid, _ in zone_map_pairs]

    # --- manifest ----------------------------------------------------------
    (OUT / "manifest.json").write_text(json.dumps({
        "name": "Yo-kai Watch 2 (Archipelago)",
        "game_name": "Yo-kai Watch 2",
        "package_uid": "ykw2_ap_doteos",
        "package_version": "0.1.0",
        "author": "Doteos",
        "min_poptracker_version": "0.26.2",
        "variants": {"standard": {"display_name": "Standard",
                                  "flags": ["ap"]}},
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    # --- items -------------------------------------------------------------
    items_json = [
        # « rang » = compteur CACHÉ pour la logique (rang:N dans les règles)
        {"name": "Rang (logique)", "type": "consumable",
         "codes": "rang", "min_quantity": 0, "max_quantity": 5,
         "img": "images/rang.png"},
        # affichage : lettre du rang qui évolue E->D->C->B->A->S
        {"name": "Rang de Yo-kai Watch", "type": "progressive",
         "allow_disabled": False, "initial_stage_idx": 0, "loop": False,
         "stages": [
             {"img": f"images/rang_{letter}.png",
              "codes": f"rang_{letter}",
              "inherit_codes": False,
              "name": f"Rang {letter.upper()}"}
             for letter in ("e", "d", "c", "b", "a", "s")]},
        {"name": "Chapitre d'histoire", "type": "consumable",
         "codes": "chapitre", "min_quantity": 0, "max_quantity": 11,
         "img": "images/chapitre.png"},
    ]
    key_codes = {}
    for key in KEY_ORDER:
        if key in TRACKER_SKIP_ITEMS:
            continue
        code = slug(key)
        key_codes[key] = code
        items_json.append({"name": key, "type": "toggle", "codes": code,
                           "img": f"images/key_{code}.png"})
    # items de stats (chiffres en overlay mis à jour en Lua) : 3 globales +
    # compteurs « fait/total » sous les photos Chapitres / Yo-criminels
    for code, label in (("stat_checked", "Locations Checked"),
                        ("stat_accessible", "Locations Accessible"),
                        ("stat_remaining", "Locations Remaining"),
                        ("stat_chapitres", "Chapitres faits"),
                        ("stat_criminels", "Yo-criminels faits")):
        img = (f"images/{code}.png" if code.startswith("stat_l") or code in
               ("stat_checked", "stat_accessible", "stat_remaining")
               else "images/blank.png")
        items_json.append({"name": label, "type": "static", "codes": code,
                           "img": img})
    (OUT / "items" / "items.json").write_text(
        json.dumps(items_json, ensure_ascii=False, indent=2),
        encoding="utf-8")

    # --- maps ---------------------------------------------------------------
    # Cartes monde (granval / vieux_monde) et schéma « autres » retirés
    # (Doteos 2026-07-19) : seules les cartes détaillées de zone subsistent.
    maps_json = []
    for mid in sorted(zone_map_ids):
        maps_json.append({"name": mid, "location_size": 48,
                          "location_border_thickness": 3,
                          "img": f"images/{mid}.png"})
    for region, (mid, mw, mh) in detailed.items():
        maps_json.append({"name": mid,
                          "location_size": DETAILED_MARKER_SIZE,
                          "location_border_thickness": DETAILED_MARKER_BORDER,
                          "img": f"images/{mid}.png"})
    for mid in ("grp_chapitres", "grp_criminels"):
        maps_json.append({"name": mid, "location_size": 64,
                          "location_border_thickness": 3,
                          "img": f"images/{mid}.png"})
    (OUT / "maps" / "maps.json").write_text(
        json.dumps(maps_json, ensure_ascii=False, indent=2),
        encoding="utf-8")

    # --- locations ----------------------------------------------------------
    loc_json = []
    lua_locs = {}          # ap_location_id -> chemin @Region/Region/Section
    lua_chapters = {}      # ap_location_id -> numéro de chapitre
    group_chapitres = []   # groupe « photo » du bas : chapitres
    group_criminels = []   # groupe « photo » du bas : yo-criminels
    _filet_slug = slug("Filet à insectes")

    def check_rules(name, data):
        """Règles d'un check = req de la location + req de sa RÉGION LOGIQUE
        (data.region, PAS la carte d'affichage : un check DISPLAY_REGION_OVERRIDE
        garde le gate de sa vraie région, ex. Lady Démona -> Repaire = Modèle zéro).
        PROLOGUE FILET : tout le requiert sauf son propre check natif."""
        r = rules_for(data.req, reg_req.get(data.region, (0, 0, frozenset())))
        if name != "Objet-clé : Filet à insectes":
            r = [(r[0] + "," if r else "") + _filet_slug]
        return r

    # invités (MERGE_INTO) collectés GLOBALEMENT : un invité peut être dans une
    # région différente de son hôte (ex. coffres Égouts fusionnés sur le marqueur
    # Ruelle obscure). On les attache à l'hôte quel que soit son bucket région.
    all_guests = {}
    for _region in regions_order:
        for _n, _d, _cat in per_region.get(_region, []):
            if _n in MERGE_INTO:
                all_guests.setdefault(MERGE_INTO[_n], []).append((_n, _d))

    for region in regions_order:
        rreq = reg_req.get(region, (0, 0, frozenset()))
        region_rules = rules_for(
            types.SimpleNamespace(min_chapter=0, combat_rank=0, items=()),
            rreq)
        # checks « normaux » (hors chapitres/yo-criminels traités en bas)
        checks = []
        for name, data, cat in sorted(per_region[region],
                                      key=lambda x: x[1].code):
            if cat == "STORY":
                import re as _re
                m = _re.match(r"Chapitre (\d+)", name)
                if m:
                    lua_chapters[LOC_IDS[name]] = int(m.group(1))
                group_chapitres.append((name, data))
                continue
            if cat == "CRIMINEL":
                group_criminels.append((name, data))
                continue
            checks.append((name, data))

        if region in detailed:
            # CARTE DÉTAILLÉE : seuls les checks POSITIONNÉS (CHECK_COORDS)
            # deviennent des marqueurs individuels sur la carte de zone. Les
            # non-positionnés restent dans le popup de région sur la carte
            # monde (on les migre au fur et à mesure — demande Doteos).
            mid, mw, mh = detailed[region]
            # invités (fusionnés) : map globale hôte -> invités (cross-région)
            guests = all_guests
            placed = [(n, d) for n, d in checks
                      if (n in CHECK_COORDS or n in MULTI_MAP_COORDS)
                      and n not in MERGE_INTO]
            unplaced = [(n, d) for n, d in checks
                        if n not in CHECK_COORDS and n not in MULTI_MAP_COORDS
                        and n not in MERGE_INTO]
            for name, data in placed:
                # marqueur(s) : un seul (CHECK_COORDS) ou plusieurs cartes
                # (MULTI_MAP_COORDS : le check apparaît sur 2 cartes).
                if name in MULTI_MAP_COORDS:
                    mlocs = [{"map": m, "x": x, "y": y}
                             for m, x, y in MULTI_MAP_COORDS[name]]
                else:
                    x, y = CHECK_COORDS[name]
                    mlocs = [{"map": mid, "x": x, "y": y}]
                sections = [{"name": name, "item_count": 1,
                             "access_rules": check_rules(name, data)}]
                lua_locs[LOC_IDS[name]] = f"@{name}/{name}/{name}"
                for gname, gdata in guests.get(name, []):
                    sections.append({"name": gname, "item_count": 1,
                                     "access_rules": check_rules(gname, gdata)})
                    lua_locs[LOC_IDS[gname]] = f"@{name}/{name}/{gname}"
                node = {"name": name, "children": [{
                    "name": name,
                    "map_locations": mlocs,
                    "sections": sections,
                }]}
                if region_rules:
                    node["access_rules"] = region_rules
                loc_json.append(node)
            if unplaced:
                sections = []
                for name, data in unplaced:
                    sections.append({"name": name, "item_count": 1,
                                     "access_rules": check_rules(name, data)})
                    lua_locs[LOC_IDS[name]] = f"@{region}/{region}/{name}"
                # marqueur regroupé au coin haut-gauche de la carte détaillée de
                # la zone (plus de carte monde) — ce sont les checks pas encore
                # positionnés individuellement (doublons objet-clé/coffre + rang S).
                node = {"name": region, "children": [{
                    "name": region,
                    "map_locations": [{"map": mid, "x": 30, "y": 30}],
                    "sections": sections,
                }]}
                if region_rules:
                    node["access_rules"] = region_rules
                loc_json.append(node)
        else:
            # popup unique de région sur la/les carte(s) monde (comportement
            # standard). Les invités MERGE_INTO sont exclus (rendus sur leur hôte).
            sections = []
            for name, data in checks:
                if name in MERGE_INTO:
                    continue
                sections.append({"name": name, "item_count": 1,
                                 "access_rules": check_rules(name, data)})
                lua_locs[LOC_IDS[name]] = f"@{region}/{region}/{name}"
            if sections:
                node = {"name": region, "children": [{
                    "name": region,
                    "map_locations": [{"map": m, "x": x, "y": y}
                                      for m, x, y in coords.get(region, [])],
                    "sections": sections,
                }]}
                if region_rules:
                    node["access_rules"] = region_rules
                loc_json.append(node)
    # marqueurs SECONDAIRES : un check déjà fusionné (MERGE_INTO) réapparaît en
    # plus sur une autre carte via une section « ref » liée à l'originale — même
    # état, même clic, deux points cliquables (Doteos : coffres égouts visibles
    # à la fois sur Les Hauts en G11 et sur la carte Égouts).
    for check, (mid2, sx, sy) in SECONDARY_MARKERS.items():
        host = MERGE_INTO.get(check, check)
        loc_json.append({"name": f"{check} ⇒", "children": [{
            "name": f"{check} ⇒",
            "map_locations": [{"map": mid2, "x": sx, "y": sy}],
            "sections": [{"ref": f"@{host}/{host}/{check}"}],
        }]})

    # groupes « photo » du bas : une mini-carte cliquable par groupe (le
    # marqueur central ouvre la liste complète des checks du groupe)
    for gname, gitems, mid in (
            ("Chapitres", group_chapitres, "grp_chapitres"),
            ("Yo-criminels", group_criminels, "grp_criminels")):
        gsections = []
        for name, data in sorted(gitems, key=lambda x: x[1].code):
            sec = {"name": name, "item_count": 1}
            req = data.req
            # « Chapitre N » exige aussi ses objets-clés critiques
            import re as _re
            m = _re.match(r"Chapitre (\d+)", name)
            if m and int(m.group(1)) in CRITICAL:
                req = types.SimpleNamespace(
                    min_chapter=req.min_chapter,
                    combat_rank=req.combat_rank,
                    items=tuple(req.items) + tuple(CRITICAL[int(m.group(1))]))
            rules = rules_for(req, (0, 0, frozenset()))
            sec["access_rules"] = rules
            gsections.append(sec)
            lua_locs[LOC_IDS[name]] = f"@{gname}/{gname}/{name}"
        loc_json.append({"name": gname, "children": [{
            "name": gname,
            "map_locations": [{"map": mid, "x": 210, "y": 110}],
            "sections": gsections,
        }]})
    (OUT / "locations" / "locations.json").write_text(
        json.dumps(loc_json, ensure_ascii=False, indent=2), encoding="utf-8")

    # images des groupes (tracker_assets/chapitres.png / yo_criminels.png si
    # fournies par Doteos, sinon tuile générée)
    from PIL import Image as _Img, ImageDraw as _Draw, ImageFont as _Font
    for mid, title, src_name in (
            ("grp_chapitres", "Chapitres", "chapitres.png"),
            ("grp_criminels", "Yo-criminels", "yo_criminels.png")):
        src = ROOT / "tracker_assets" / src_name
        if src.exists():
            # « contain » : ratio préservé, centré sur fond sombre (pas
            # d'étirement, pas de fond noir moche sur les PNG transparents)
            raw = _Img.open(src).convert("RGBA")
            ratio = min(420 / raw.width, 220 / raw.height)
            new_size = (int(raw.width * ratio), int(raw.height * ratio))
            raw = raw.resize(new_size)
            canvas = _Img.new("RGB", (420, 220), "#20242c")
            canvas.paste(raw, ((420 - new_size[0]) // 2,
                               (220 - new_size[1]) // 2), raw)
            canvas.save(OUT / "images" / f"{mid}.png")
        else:
            im = _Img.new("RGB", (420, 220), "#2b3440")
            dr = _Draw.Draw(im)
            try:
                f = _Font.truetype("arialbd.ttf", 36)
            except OSError:
                f = _Font.load_default()
            dr.rounded_rectangle([6, 6, 414, 214], 16,
                                 outline="#8fa6b3", width=4)
            dr.text((40, 90), title, fill="#eeeeee", font=f)
            im.save(OUT / "images" / f"{mid}.png")

    # --- layouts : objets-clés en haut, carte au centre, compteurs par
    # région à droite, rangée des chapitres en bas (façon pack TWW)
    # objets-clés en COLONNE à gauche (rangées de 3) -> la carte prend
    # toute la largeur restante (demande Doteos)
    flat_items = ["rang_e", "chapitre"] + \
        [key_codes[k] for k in KEY_ORDER if k in key_codes]
    grid_rows = [flat_items[i:i + 3] for i in range(0, len(flat_items), 3)]
    # un ONGLET par carte + panneau de stats à droite (façon pack TWW)
    def _map_tab(title, mid):
        return {"title": title, "content": {
            "type": "map", "maps": [mid],
            "h_alignment": "stretch", "v_alignment": "stretch"}}
    # Cartes MONDE (Granval / Vieux Granval) + schéma « Autres » RETIRÉS
    # (demande Doteos 2026-07-19) : tous les checks sont désormais sur les
    # cartes détaillées de zone -> un onglet par carte détaillée uniquement.
    map_tabs = []
    for region, (mid, mw, mh) in detailed.items():
        map_tabs.append(_map_tab(region, mid))
    for mid, region in sorted(zone_map_pairs, key=lambda p: p[1]):
        map_tabs.append(_map_tab(region, mid))
    stats_rows = [
        {"type": "item", "item": "stat_checked", "item_size": "210,58",
         "margin": "4,4"},
        {"type": "item", "item": "stat_accessible", "item_size": "210,58",
         "margin": "4,4"},
        {"type": "item", "item": "stat_remaining", "item_size": "210,58",
         "margin": "4,4"},
    ]
    (OUT / "layouts" / "tracker.json").write_text(json.dumps({
        "tracker_default": {
            "type": "dock",
            "h_alignment": "stretch",
            "v_alignment": "stretch",
            "content": [
                    {"type": "itemgrid", "dock": "left",
                     "item_size": "56,56", "item_margin": "5,5",
                     "v_alignment": "top",
                     "rows": grid_rows},
                    {"type": "array", "dock": "bottom",
                     "orientation": "horizontal", "max_height": 185,
                     "content": [
                         {"type": "canvas", "width": 330, "height": 175,
                          "content": [
                              {"type": "map", "maps": ["grp_chapitres"],
                               "canvas_left": 0, "canvas_top": 0,
                               "width": 320, "height": 168},
                              {"type": "item", "item": "stat_chapitres",
                               "canvas_left": 245, "canvas_top": 118,
                               "width": 80, "height": 50}]},
                         {"type": "canvas", "width": 330, "height": 175,
                          "content": [
                              {"type": "map", "maps": ["grp_criminels"],
                               "canvas_left": 0, "canvas_top": 0,
                               "width": 320, "height": 168},
                              {"type": "item", "item": "stat_criminels",
                               "canvas_left": 245, "canvas_top": 118,
                               "width": 80, "height": 50}]},
                         {"type": "container"},
                     ]},
                    {"type": "array", "dock": "right",
                     "orientation": "vertical", "max_width": 260,
                     "content": stats_rows},
                    # PAS de "dock" : dernier enfant sans dock = remplit tout
                    # l'espace restant (cf. exemple officiel PopTracker).
                    {"type": "tabbed",
                     "h_alignment": "stretch", "v_alignment": "stretch",
                     "tabs": map_tabs},
            ],
        },
        "tracker_broadcast": {
            "type": "itemgrid", "item_size": "40,40",
            "rows": grid_rows,
        },
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    # --- scripts ------------------------------------------------------------
    item_map = {}
    item_map[ITEM_IDS[PROG_RANK]] = {"action": "rang_inc"}
    for lvl, rname in RANKS.items():
        if rname in ITEM_IDS:
            item_map[ITEM_IDS[rname]] = {"action": "rang_set", "n": lvl}
    if PROG_CHAP and PROG_CHAP in ITEM_IDS:
        item_map[ITEM_IDS[PROG_CHAP]] = {"action": "chapitre_inc"}
    for key, code in key_codes.items():
        if key in ITEM_IDS:
            item_map[ITEM_IDS[key]] = {"action": "toggle", "code": code}
    # Vélo progressif (option progressive_bicycle) : 2 exemplaires d'un item au
    # nom DIFFÉRENT -> les router vers la MÊME case « Vélo » du tracker.
    _velo_code = key_codes.get("Vélo")
    if _velo_code and "Vélo (progressif)" in ITEM_IDS:
        item_map[ITEM_IDS["Vélo (progressif)"]] = {
            "action": "toggle", "code": _velo_code}

    lua = ["-- GÉNÉRÉ par tools/generate_tracker_pack.py — ne pas éditer.",
           "AP_ITEMS = {"]
    for iid, spec in sorted(item_map.items()):
        if spec["action"] == "toggle":
            lua.append(f'  [{iid}] = {{action="toggle", code="{spec["code"]}"}},')
        elif spec["action"] == "rang_set":
            lua.append(f'  [{iid}] = {{action="rang_set", n={spec["n"]}}},')
        else:
            lua.append(f'  [{iid}] = {{action="{spec["action"]}"}},')
    lua.append("}")
    lua.append("AP_LOCATIONS = {")
    for lid, path in sorted(lua_locs.items()):
        esc = path.replace('"', '\\"')
        lua.append(f'  [{lid}] = "{esc}",')
    lua.append("}")
    lua.append("AP_CHAPTER_LOCATIONS = {")
    for lid, n in sorted(lua_chapters.items()):
        lua.append(f"  [{lid}] = {n},")
    lua.append("}")
    lua.append("AP_ALL_SECTIONS = {")
    for p in sorted(set(lua_locs.values())):
        lua.append(f'  "{p}",')
    lua.append("}")
    (OUT / "scripts" / "ap_ids.lua").write_text("\n".join(lua),
                                                encoding="utf-8")

    (OUT / "scripts" / "init.lua").write_text(
        'Tracker:AddItems("items/items.json")\n'
        'Tracker:AddMaps("maps/maps.json")\n'
        'Tracker:AddLocations("locations/locations.json")\n'
        'Tracker:AddLayouts("layouts/tracker.json")\n'
        'ScriptHost:LoadScript("scripts/ap_ids.lua")\n'
        'ScriptHost:LoadScript("scripts/autotracking.lua")\n',
        encoding="utf-8")

    (OUT / "scripts" / "autotracking.lua").write_text(r"""-- Autotracking Archipelago pour Yo-kai Watch 2 (généré une fois, stable).
-- synchronise le compteur logique « rang » ET la lettre affichée (E..S)
local function setRang(n)
    local o = Tracker:FindObjectForCode("rang")
    if o then o.AcquiredCount = n end
    local d = Tracker:FindObjectForCode("rang_e")
    if d then d.CurrentStage = n end
end

local function resetAll()
    setRang(0)
    local chap = Tracker:FindObjectForCode("chapitre")
    if chap then chap.AcquiredCount = 0 end
    for _, spec in pairs(AP_ITEMS) do
        if spec.action == "toggle" then
            local o = Tracker:FindObjectForCode(spec.code)
            if o then o.Active = false end
        end
    end
    for _, path in pairs(AP_LOCATIONS) do
        local s = Tracker:FindObjectForCode(path)
        if s then
            s.AvailableChestCount = s.ChestCount
            -- surlignage de hint remis à zéro (il sera reposé par onHints)
            if Highlight and s.Highlight ~= nil then
                s.Highlight = Highlight.None
            end
        end
    end
end

local function setStat(code, n)
    local o = Tracker:FindObjectForCode(code)
    if o then
        o:SetOverlay(tostring(n))
        o:SetOverlayFontSize(26)
        o:SetOverlayAlign("center")
    end
end

-- sections ABSENTES de la seed (options YAML off) : exclues des comptes
local ABSENT = {}

local function updateStats()
    local checked, accessible, remaining = 0, 0, 0
    local groups = {
        ["@Chapitres/"] = {done = 0, total = 0, code = "stat_chapitres"},
        ["@Yo-criminels/"] = {done = 0, total = 0, code = "stat_criminels"},
    }
    for _, p in ipairs(AP_ALL_SECTIONS) do
        local s = Tracker:FindObjectForCode(p)
        if s and not ABSENT[p] then
            local done = s.ChestCount - s.AvailableChestCount
            checked = checked + done
            remaining = remaining + s.AvailableChestCount
            if s.AvailableChestCount > 0
               and s.AccessibilityLevel >= AccessibilityLevel.Normal then
                accessible = accessible + s.AvailableChestCount
            end
            for prefix, g in pairs(groups) do
                if p:sub(1, #prefix) == prefix then
                    g.done = g.done + done
                    g.total = g.total + s.ChestCount
                end
            end
        end
    end
    setStat("stat_checked", checked)
    setStat("stat_accessible", accessible)
    setStat("stat_remaining", remaining)
    for _, g in pairs(groups) do
        local o = Tracker:FindObjectForCode(g.code)
        if o then
            o:SetOverlay(g.done .. "/" .. g.total)
            o:SetOverlayFontSize(34)
            o:SetOverlayAlign("center")
        end
    end
end

local function markLocation(id)
    local path = AP_LOCATIONS[id]
    if path then
        local s = Tracker:FindObjectForCode(path)
        if s then s.AvailableChestCount = 0 end
    end
    local chapN = AP_CHAPTER_LOCATIONS[id]
    if chapN then
        local chap = Tracker:FindObjectForCode("chapitre")
        if chap and chap.AcquiredCount < chapN then
            chap.AcquiredCount = chapN
        end
    end
end

-- ---------------------------------------------------------------------------
-- HINTS : un check dont l'item a été « hint » par quelqu'un est SURLIGNÉ
-- (demande Doteos 2026-07-27). Le serveur AP publie les hints du monde du joueur
-- dans la clé de data storage « _read_hints_<team>_<slot> ». On s'y abonne
-- (SetNotify) + on la lit une fois (Get) à la connexion, et on traduit le statut
-- du hint en LocationSection.Highlight (supporté depuis PopTracker 0.32).
-- ⚠️ Ces fonctions DOIVENT être définies AVANT les handlers qui les utilisent
-- (une closure Lua ne voit pas un `local` déclaré plus bas).
-- ---------------------------------------------------------------------------
local HINT_STATUS_TO_HIGHLIGHT = {}
if Highlight then
    HINT_STATUS_TO_HIGHLIGHT = {
        [0]  = Highlight.Unspecified,   -- non spécifié
        [10] = Highlight.NoPriority,    -- sans priorité
        [20] = Highlight.Avoid,         -- à éviter
        [30] = Highlight.Priority,      -- prioritaire
        [40] = Highlight.None,          -- trouvé -> plus de surlignage
    }
end

local function hintsKey()
    if Archipelago.TeamNumber == nil or Archipelago.PlayerNumber == nil
            or Archipelago.TeamNumber < 0 or Archipelago.PlayerNumber < 0 then
        return nil
    end
    return string.format("_read_hints_%s_%s",
                         Archipelago.TeamNumber, Archipelago.PlayerNumber)
end

local function onHints(hints)
    if not Highlight or type(hints) ~= "table" then return end
    local me = Archipelago.PlayerNumber
    for _, hint in ipairs(hints) do
        -- on ne surligne que les hints portant sur NOTRE monde
        if hint.finding_player == me then
            local hl = hint.status and HINT_STATUS_TO_HIGHLIGHT[hint.status]
            if hl == nil then                 -- serveur AP sans hint.status
                if hint.found == true then hl = Highlight.None
                elseif hint.found == false then hl = Highlight.Unspecified end
            end
            local path = AP_LOCATIONS[hint.location]
            if hl ~= nil and path then
                local s = Tracker:FindObjectForCode(path)
                if s and s.Highlight ~= nil then s.Highlight = hl end
            end
        end
    end
end

local function onDataStorage(key, value)
    if key == hintsKey() then onHints(value) end
end

Archipelago:AddClearHandler("ykw2_clear", function(slot_data)
    Tracker.BulkUpdate = true
    local ok, err = pcall(function()
        resetAll()
        -- checks ABSENTS de la seed (options désactivées côté YAML) :
        -- neutralisés pour ne pas fausser Accessible/Remaining.
        local valid = {}
        if Archipelago.MissingLocations then
            for _, id in ipairs(Archipelago.MissingLocations) do
                valid[id] = true
            end
        end
        if Archipelago.CheckedLocations then
            for _, id in ipairs(Archipelago.CheckedLocations) do
                valid[id] = true
            end
        end
        ABSENT = {}
        if next(valid) ~= nil then
            for id, path in pairs(AP_LOCATIONS) do
                if not valid[id] then
                    ABSENT[path] = true
                    local s = Tracker:FindObjectForCode(path)
                    if s then s.AvailableChestCount = 0 end
                end
            end
        end
        if Archipelago.CheckedLocations then
            for _, id in ipairs(Archipelago.CheckedLocations) do
                markLocation(id)
            end
        end
    end)
    Tracker.BulkUpdate = false
    updateStats()
    -- HINTS : s'abonner à la clé de data storage du slot + la lire une fois
    -- (les hints déjà émis avant la connexion sont ainsi récupérés).
    local hk = hintsKey()
    if hk then
        Archipelago:SetNotify({hk})
        Archipelago:Get({hk})
    end
end)

-- recompte à chaque changement de section (auto OU clic manuel)
ScriptHost:AddOnLocationSectionChangedHandler("ykw2_stats", function(_)
    updateStats()
end)

-- affichage initial (avant toute connexion AP)
updateStats()

Archipelago:AddItemHandler("ykw2_item", function(index, item_id, item_name)
    local spec = AP_ITEMS[item_id]
    if not spec then return end
    if spec.action == "toggle" then
        local o = Tracker:FindObjectForCode(spec.code)
        if o then o.Active = true end
    elseif spec.action == "rang_inc" then
        local o = Tracker:FindObjectForCode("rang")
        if o then setRang(o.AcquiredCount + 1) end
    elseif spec.action == "rang_set" then
        local o = Tracker:FindObjectForCode("rang")
        if o and o.AcquiredCount < spec.n then setRang(spec.n) end
    elseif spec.action == "chapitre_inc" then
        local o = Tracker:FindObjectForCode("chapitre")
        if o then o.AcquiredCount = o.AcquiredCount + 1 end
    end
end)

Archipelago:AddLocationHandler("ykw2_loc", function(location_id, name)
    markLocation(location_id)
end)

Archipelago:AddRetrievedHandler("ykw2_hints_get", onDataStorage)
Archipelago:AddSetReplyHandler("ykw2_hints_set", onDataStorage)
""", encoding="utf-8")

    # --- zip ----------------------------------------------------------------
    zip_path = ROOT / "tracker" / "ykw2-poptracker"
    archive = shutil.make_archive(str(zip_path), "zip", OUT)

    n_locs = sum(len(v) for v in per_region.values())
    print(f"OK : {n_locs} checks, {len(regions_order)} régions, "
          f"{len(items_json)} items trackés")
    print(f"Pack : {OUT}")
    print(f"Zip  : {archive}")


if __name__ == "__main__":
    main()
