# -*- coding: utf-8 -*-
"""Après-jeu de la V3 (lot 3) : objectifs, régions, objets d'accès et checks d'après la fin de l'histoire, sans Archipelago.

Données seulement (saisies à la main, règle 6 de CLAUDE.md : identifiants AP, index de flags, n° de quêtes et du
Médaillium, noms de lieux et de Yo-kai FR / EN relus dans la ROM européenne, archives `fr` et `engb`) ; le plan est
construit par `logique.construire_plan` (options `objectif`, `apres_jeu`, `blasters`). Sources :
`docs/systemes/archipelago_v3_zones_postgame.md`, `archipelago_v3_boss_objectifs.md`, `archipelago_v3_blasters.md`,
et `docs/systemes/archipelago_v3_apres_jeu.md` (ce lot : ce qui a été revérifié, classement de chaque location).

RIEN de ce module n'entre dans une graine dont l'objectif est « finir_chapitre_10 » (décision de l'humain, 2026-10-10 :
l'après-jeu ne compte pas, exactement comme en V2) : `apres_jeu` y est forcé à « aucun ».

Options (décision du lot, à valider) :
- `objectif` : « finir_chapitre_10 » (défaut, V2), « battre_potofeu », « battre_filomene », « battre_extrabuki ».
  Victoire des trois nouveaux = flag « partie terminée » ET bit du Médaillium du boss (n° 414 / 422 / 448 : posé par le
  moteur pour chaque ennemi vaincu de cette espèce, où qu'il soit).
- `apres_jeu` : étendue des CHECKS d'après-jeu.
  - « aucun » (défaut) : aucun check d'après-jeu. Avec un des trois nouveaux objectifs, seuls entrent les objets d'accès
    de l'objectif (Clé de cabane) et leur emplacement d'origine (remplissage) : le joueur va au boss sans rien y chercher.
  - « necessaire » : + les checks du CHEMIN de l'objectif (ce qu'on traverse pour aller au boss).
  - « complet » : + tous les autres checks d'après-jeu, EXCLUS de la progression (remplissage seulement) : rien de ce
    que l'objectif ne fait pas traverser ne peut retenir un objet nécessaire (règle de softlock du lot).
- `blasters` : « aucun » (défaut), « debut », « tous » (indépendante ; ses terrains d'après-jeu suivent `apres_jeu`).
"""
from typing import Dict, FrozenSet, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Objectifs
# ---------------------------------------------------------------------------
OBJECTIF_V2 = "finir_chapitre_10"
OBJECTIF_MEDAILLIUM = "medaillium_complet"      # V3, lot 18 (medaillium.py)
OBJECTIFS = (OBJECTIF_V2, "battre_potofeu", "battre_filomene", "battre_extrabuki", OBJECTIF_MEDAILLIUM)
MODES_APRES_JEU = ("aucun", "necessaire", "complet")
APRES_JEU_PAR_DEFAUT = "aucun"

# Verrous livrés par les lots côté jeu (lots 2 et 4), BRANCHÉS au lot 6 (docs/systemes/archipelago_v3_branchement.md).
# Une valeur False refermerait la région : aucune location n'y serait créée, son objet d'accès n'entrerait pas dans le
# pool (état du lot 3 ; interrupteur de repli : avec « pass_sortilege » à False, l'objectif « battre_extrabuki »,
# dont la région est le train, est refusé par `construire_plan`).
# - « pass_sortilege » (verrou étendu k = 47, archipelago_v3_acces_postgame.md §2) : trains de nuit de t100s22 fermés
#   sans l'objet « Pass sortilège » ; objet reçu : la requête 121 est proposée sans attendre la fin ni le rang S ;
# - « voie_du_mystere » (k = 43..46, §1 du même document) : flags 536, 538, 539, 537 lus « clé reçue » : Clé terrifiante
#   (porte, tronc et ligne principale), Clé sanglier (Route des farceurs), Clé cerf (Route des bouffis), Clé papillon
#   (Grand-route dorée) ;
# - « transfert » (fonction étendue 37, option étendue 25, archipelago_v3_transfert.md) : requêtes 107 à 116 proposées
#   dans la même partie, sans transfert de sauvegarde. C'est une OPTION du joueur (`requetes_transfert`, désactivée par
#   défaut : `construire_plan(transfert=True)`), pas un objet.
VERROUS_DISPONIBLES: Dict[str, bool] = {"pass_sortilege": True, "voie_du_mystere": True, "transfert": True}
# Verrous étendus du jeu portés par un objet d'après-jeu (entrées de `slot_data.verrous_actifs`, zone ApVerrous2 : le
# client les écrit génériquement, `recu[k - 40]` = objet reçu). Jamais des valeurs de l'option `verrous_actifs` du
# joueur : un verrou est dans la graine si, et seulement si, son objet est dans le pool (objectif × `apres_jeu`).
# AUCUN de ces objets ne donne d'objet du jeu (don « aucun ») : la Clé cerf du jeu est lue par 3 points de loupe de
# t101d03, les quatre clés n'ont pas de place sûre dans le sac, le Pass du jeu n'a aucun lecteur.
VERROUS_JEU: Dict[str, dict] = {
    "cle_terrifiante": {"k": 43, "mecanisme": "flag_lu_recu", "flag": 536, "code_jeu": True},
    "cle_sanglier": {"k": 44, "mecanisme": "flag_lu_recu", "flag": 538, "code_jeu": True},
    "cle_cerf": {"k": 45, "mecanisme": "flag_lu_recu", "flag": 539, "code_jeu": True},
    "cle_papillon": {"k": 46, "mecanisme": "flag_lu_recu", "flag": 537, "code_jeu": True},
    "pass_sortilege": {"k": 47, "mecanisme": "train_de_nuit", "quete": 121, "code_jeu": True},
}
CLES_VOIE: Tuple[str, ...] = ("cle_terrifiante", "cle_sanglier", "cle_cerf", "cle_papillon")
# Requêtes à transfert de sauvegarde : fonction étendue du patch, option étendue (bit de ApVerrous2::actifs que le
# client pose), et n° « client » jamais publié par le jeu (un client qui ne sait pas poser le bit refuse la graine).
FONCTION_TRANSFERT = 37
OPTION2_TRANSFERT = 25
FONCTION_CLIENT_6 = 67

# Régions d'après-jeu (clés de `regions.json`, exclusion « apres_jeu ») : source, objets d'accès, rang de montre, verrou
# du lot parallèle. Toutes les LOCATIONS d'après-jeu portent en plus « 10 chapitres terminés » dans leur propre règle.
# « rang S » : aucun objet AP ne donne le rang S ; il vient de la requête 28 (« Obtenons le rang S ! » : phase >= 11-10,
# rang A, trois combats), que le mode « rang réel » laisse passer (verrous.cpp : seule montée de rang d'un script encore
# écrite) : la région exige donc le rang A (4 exemplaires avec le verrou « rangs »).
# - apres_jeu : la ville après la fin (flag 1 « partie terminée », phase 11-10) : règle de l'objectif de la V2 ;
# - limbes_eternelles : point de t103i33, IsHaveItem(Clé de cabane) (c11_trigger n° 7, puis t103i33_trigger n° 1) [C] ;
# - sanctuaire_divin : suite de la même chaîne, après Potofeu (flag 582 posé par sa première victoire) [C] ;
# - origines : requêtes 91 à 95 (rang S ET flag 1619 = scène ev13_0900, jouée par un PNJ de t103d49 qui n'apparaît
#   qu'une fois la requête 96 finie [C, t103d49_quest_trigger n° 3, NPC_APPEAR]) : derrière le Château de Sawayama ;
# - yokai_world : 3 blocs MAP_MESH de t102g00, IsHaveItem(Clé du Yo-kai World) [C]. Le jeu n'y met AUCUNE condition de
#   phase : la clé reçue l'ouvrirait avant la fin ; la logique exige quand même la fin (plus stricte, jamais moins) ;
# - chateau_de_sawayama : miroir de Vieux Granval, requête 96 en phase >= 3 (rang S, requêtes 119 et 125 finies) [C].
#   Revérifié pour ce lot : la requête 96 s'ACCEPTE au Théâtre Kaibuki (t001d08_quest_trigger n° 1, type 52), donc
#   dans les stations du train de Gera Gera, et passe par t103d49 (Limbes, Pièce hors du temps : Clé de cabane) : la
#   région dépend du verrou « pass_sortilege » (FERMÉE tant qu'il n'est pas branché) et de la Clé de cabane ;
# - entrain_express : train tiré au sort (10 % par entrée en gare) ET IsHaveItem(Pass Entrain Exp.) [C] ; gares
#   ouvertes dès le chapitre 4 : pas d'exigence de fin d'histoire dans le jeu ; région « longue » (jamais de progression) ;
# - sortilege_express (lot 6, décision de l'humain du 2026-10-10) : le train et Gera Gera Land s'ouvrent physiquement
#   dès réception du Pass sortilège, mais la LOGIQUE exige « le Pass ET la fin de l'histoire » pour tout ce qui est
#   derrière le train (le boss du trajet est d'après-jeu) : source « apres_jeu », sans rang. Bellesource, Val Vorace
#   et le Théâtre Kaibuki restent derrière la requête 122 (fin de l'histoire + rang S : t001d01_trigger n° 1,
#   t001d03_trigger n° 1) : leurs coffres exigent en plus le rang S (COFFRES_STATIONS_RANG_S) ;
# - chateau_de_sawayama : train (la requête 96 s'accepte au Théâtre Kaibuki) + rang S + Clé de cabane (t103d49) +
#   requête 125 finie (d'avant la fin) ; la requête 119 (rang A, après-jeu) n'exige aucun objet ;
# - voie_du_mystere : porte de San Fantastico (Clé terrifiante) ; trois embranchements à sens unique dans la bretelle
#   t121d25 (une clé chacun), sortie par script : aucune clé de branche n'est exigée pour le tronc ni pour la fin
#   commune t121d29.
# Une région dont un objet d'accès n'est pas dans la graine n'est PAS créée (logique.construire_plan) : son verrou
# n'est alors pas actif, le jeu garde son comportement d'origine et aucune location n'y existe.
REGIONS: Dict[str, dict] = {
    "apres_jeu": {"source": "repaire_de_lady_demona", "objectif_v2": True},
    "rang_s": {"source": "apres_jeu", "rang": "A"},
    "limbes_eternelles": {"source": "apres_jeu", "objets": ("cle_de_cabane",)},
    "sanctuaire_divin": {"source": "limbes_eternelles"},
    "yokai_world": {"source": "apres_jeu", "objets": ("cle_du_yokai_world",)},
    "entrain_express": {"source": "centre_ville_de_granval", "objets": ("pass_entrain_exp",)},
    "sortilege_express": {"source": "apres_jeu", "objets": ("pass_sortilege",), "verrou": "pass_sortilege"},
    "chateau_de_sawayama": {"source": "sortilege_express", "objets": ("cle_de_cabane",), "rang": "A",
                            "requetes": (125,)},
    "origines": {"source": "chateau_de_sawayama"},
    "voie_du_mystere": {"source": "san_fantastico", "objets": ("cle_terrifiante",), "verrou": "voie_du_mystere"},
    "route_des_farceurs": {"source": "voie_du_mystere", "objets": ("cle_sanglier",), "verrou": "voie_du_mystere"},
    "route_des_bouffis": {"source": "voie_du_mystere", "objets": ("cle_cerf",), "verrou": "voie_du_mystere"},
    "grand_route_doree": {"source": "voie_du_mystere", "objets": ("cle_papillon",), "verrou": "voie_du_mystere"},
}
EXCLUSION_COFFRES = "apres_jeu"         # champ `exclusion` des coffres d'après-jeu de `coffres.json`
# Coffres des stations du Sortilège Express hors de Gera Gera Land (index TBox) : Bellesource (t001d05 : 538, 539), Val
# Vorace (t001d07 : 548 à 552), Théâtre Kaibuki (t001d09 : 553, 554) : derrière la requête 122 (rang S) [C pour les
# entrées de Bellesource et de Val Vorace ; S prudent pour le Théâtre, lieu des requêtes 123 et 96].
COFFRES_STATIONS_RANG_S: FrozenSet[int] = frozenset((538, 539, 548, 549, 550, 551, 552, 553, 554))


def region_ouverte(cle: str) -> bool:
    """La région (et toute sa chaîne de sources) ne dépend d'aucun verrou du lot parallèle encore absent."""
    while cle in REGIONS:
        v = REGIONS[cle].get("verrou")
        if v is not None and not VERROUS_DISPONIBLES[v]:
            return False
        cle = REGIONS[cle]["source"]
    return True


# Objectifs d'après-jeu. La VICTOIRE est décrite par une structure GÉNÉRIQUE : flag « partie terminée » ET tous les
# bits du Médaillium de `medailles` (de 1 à N n° ; slot_data `objectif_medailles`, lus par le client dans la lecture
# groupée du Médaillium) : un boss = un n°.
# POINT D'EXTENSION (demande de l'humain du 2026-10-10 : objectif « medaillium_complet », non fait dans ce lot) : une
# entrée de plus de cette table, avec `medailles` = la liste des n° exigés, `chemin` = CHEMIN_TOUT (tout l'après-jeu
# est alors « nécessaire » : `sur_le_chemin` rend toujours vrai), `objets` = tous les objets d'accès, et sans `boss` ;
# rien d'autre n'est à refondre (plan, slot_data, client, tracker lisent cette structure).
# `medailles` = n° du Médaillium exigés (bits lus par le client dans P+0x44C | P+0x604) ; `region` =
# région de la place d'ORIGINE du boss ; `chemin` = régions que l'objectif fait traverser (leurs checks sont
# « nécessaires ») ; `objets` = objets d'accès de l'objectif (dans le pool dès le mode « aucun »).
# Lot 10 (mélange des boss tiré à la génération) : `region`, `chemin`, `objets` et `requetes` de la graine sont ceux
# de la PLACE qui contient le boss : `objectif_effectif(objectif, sigma)` (table PLACES_BOSS) ; cette table-ci décrit
# le cas sans mélange (boss chez lui) ; la victoire, par le bit de l'espèce, ne change pas.
# Extrabuki (lot 6) : sa requête 123 est derrière le train de Gera Gera : règle = Pass sortilège + fin de l'histoire +
# rang S (requête 28) + requêtes 121, 122, 123 ; le Pass est son objet d'accès (dans le pool dès le mode « aucun ») ;
# son chemin traverse le train et les trois stations.
OBJECTIFS_BOSS: Dict[str, dict] = {
    "battre_potofeu": {"medailles": (414,), "nom_fr": "Objectif : battre Potofeu", "nom_en": "Goal: defeat Wobblewok",
                       "region": "limbes_eternelles", "chemin": ("limbes_eternelles",), "objets": ("cle_de_cabane",),
                       "boss": "potofeu"},
    "battre_filomene": {"medailles": (422,), "nom_fr": "Objectif : battre Filomène", "nom_en": "Goal: defeat Kat Kraydel",
                        "region": "sanctuaire_divin", "chemin": ("limbes_eternelles", "sanctuaire_divin"),
                        "objets": ("cle_de_cabane",), "boss": "filomene"},
    "battre_extrabuki": {"medailles": (448,), "nom_fr": "Objectif : battre Extrabuki", "nom_en": "Goal: defeat Kabuking",
                         "region": "sortilege_express", "chemin": ("sortilege_express",),
                         "objets": ("pass_sortilege",), "boss": "extrabuki", "requetes": (28, 121, 122, 123)},
}


CHEMIN_TOUT = "tout"                    # valeur de `chemin` d'un objectif qui fait traverser tout l'après-jeu
# Objectifs d'après-jeu SANS boss (V3, lot 18 : « medaillium_complet », medaillium.py) : tout l'après-jeu est sur
# le chemin ; la victoire (seuil de n° du Médaillium) et la règle de l'évènement sont celles de `medaillium.py`.
# Régions « longues » (accès tiré au sort) : jamais de progression, même quand tout est sur le chemin.
OBJECTIFS_AUTRES: Dict[str, dict] = {
    OBJECTIF_MEDAILLIUM: {"medailles": (), "nom_fr": "Objectif : compléter le Médaillium",
                          "nom_en": "Goal: complete the Medallium", "region": "apres_jeu", "chemin": CHEMIN_TOUT,
                          "objets": ()},
}
REGIONS_LONGUES: FrozenSet[str] = frozenset({"entrain_express"})

# ---------------------------------------------------------------------------
# Places des boss d'après-jeu (V3, lot 10 : docs/systemes/archipelago_v3_boss_generation.md §3)
# ---------------------------------------------------------------------------
# Clé = clé du boss d'ORIGINE de la place dans le mélange (`boss_generation.py`, `client/rando_boss.py`). Le mélange
# (tiré à la génération, version 2) peut y mettre un autre boss d'après-jeu : la place garde son lieu, ses conditions
# d'accès, son hachage, ses déclencheurs et son marqueur ; seul l'occupant change.
# - `rang` : n° du combat dans la chaîne des Limbes éternelles (c11_trigger) : il faut vaincre les occupants des rangs
#   précédents ; les rangs 9 à 12 sont derrière la première victoire à la place de Potofeu (flag 582) : région
#   « sanctuaire_divin » ;
# - `quete` : requête dont le combat est la place ; sa règle (rang de montre, requêtes d'avant la fin, objets) vaut
#   pour la place ; `requetes` : requêtes du chemin (elles précèdent le combat, ou le contiennent) ;
# - `chemin` : régions que la place fait traverser ; `objets` : objets d'accès (dans le pool dès le mode « aucun »
#   quand la place contient le boss de l'objectif).
# Sans mélange, ces valeurs redonnent exactement `OBJECTIFS_BOSS` pour les trois boss d'objectif (vérifié par
# test_v3_boss_generation).
_LIMBES = ("limbes_eternelles",)
_SANCTUAIRE = ("limbes_eternelles", "sanctuaire_divin")
PLACES_BOSS: Dict[str, dict] = {
    "hydreux": {"rang": 1}, "porcinator": {"rang": 2}, "styx_vi": {"rang": 3}, "nebulor": {"rang": 4},
    "pr_letripe": {"rang": 5}, "hagacuree": {"rang": 6}, "rancornet": {"rang": 7}, "potofeu": {"rang": 8},
    "barbebluff": {"rang": 9}, "mariotte_et_maribass": {"rang": 10}, "lady_maggie": {"rang": 11},
    "filomene": {"rang": 12},
    "thenuki": {"quete": 120, "region": "apres_jeu", "chemin": (), "objets": ("paquet_spirituel",),
                "requetes": (120,)},
    "infiniris": {"quete": 81, "region": "apres_jeu", "chemin": (), "objets": (), "requetes": (81,)},
    "chomino": {"quete": 121, "region": "sortilege_express", "chemin": (), "objets": ("pass_sortilege",),
                "requetes": (121,)},
    "extrabuki": {"quete": 123, "region": "sortilege_express", "chemin": ("sortilege_express",),
                  "objets": ("pass_sortilege",), "requetes": (28, 121, 122, 123)},
    "laure_marge_ambronzio": {"quete": 96, "region": "chateau_de_sawayama", "chemin": (),
                              "objets": ("pass_sortilege", "cle_de_cabane"), "requetes": (28, 121, 122, 96)},
    "dr_jobard": {"quete": 77, "region": "apres_jeu", "chemin": (), "objets": (), "requetes": (77,)},
}
for _k, _p in PLACES_BOSS.items():
    if "rang" in _p:
        _p.update(region="limbes_eternelles" if _p["rang"] <= 8 else "sanctuaire_divin",
                  chemin=_LIMBES if _p["rang"] <= 8 else _SANCTUAIRE, objets=("cle_de_cabane",), requetes=())
# Places de la Voie du mystère (ap/boss-voie-mystere, version 3 du mélange : docs/systemes/archipelago_v3_boss_generation.md
# §10) [C, t121d29_trigger / t121d35_trigger, scripts des cartes] : la fin commune t121d29 a TROIS rencontres, une par
# ligne : la zone de combat (déclencheur 21 n° 1 / 2 / 3, zone 0xB682F7CA) n'est active que si le flag de LIGNE posé
# par la dernière carte traversée vaut 1 (t103d03c : principale, t102d01c : farceurs, t102d03c : bouffis) et le bit
# « vaincu aujourd'hui » de la place vaut 0 ; RunCmd_Map1 / 2 / 3 lancent ev30_btl0040 / 0070 / 0080 (0x352C, CRC-32
# = hachage de la place). t121d35 (Grand-route dorée) : une rencontre, ev30_btl0050. Accès d'une place = la ligne qui y
# mène : Clé terrifiante (porte) + la clé de la ligne. Aucune requête ; jamais la place du boss d'un objectif.
PLACES_BOSS.update({
    "blingos": {"region": "voie_du_mystere", "chemin": ("voie_du_mystere",), "objets": ("cle_terrifiante",)},
    "cycloptique": {"region": "route_des_farceurs", "chemin": ("voie_du_mystere", "route_des_farceurs"),
                    "objets": ("cle_terrifiante", "cle_sanglier")},
    "maximain": {"region": "route_des_bouffis", "chemin": ("voie_du_mystere", "route_des_bouffis"),
                 "objets": ("cle_terrifiante", "cle_cerf")},
    "bogos": {"region": "grand_route_doree", "chemin": ("voie_du_mystere", "grand_route_doree"),
              "objets": ("cle_terrifiante", "cle_papillon")},
})
for _k in ("blingos", "cycloptique", "maximain", "bogos"):
    PLACES_BOSS[_k].update(requetes=(), voie=True)
# N° du Médaillium PROPRE à chaque boss d'après-jeu (bit posé par le moteur à la VICTOIRE pour chaque ennemi présent
# de cette espèce, où qu'il soit : FUN_005579A8, relu dans l'assembleur). Trio de la requête 96 : Ambronzio (Laure et
# Marge sont aussi des boss d'avant la fin) ; Mariotte et Maribass : Mariotte. Voie du mystère : n° porté par le
# combattant principal de chaque rencontre (base locale de la ROM européenne : 423, 426, 425, 424) [C].
MEDAILLE_BOSS: Dict[str, int] = {
    "hydreux": 397, "porcinator": 399, "styx_vi": 401, "nebulor": 403, "pr_letripe": 408, "hagacuree": 405,
    "rancornet": 411, "potofeu": 414, "barbebluff": 418, "mariotte_et_maribass": 419, "lady_maggie": 421,
    "filomene": 422, "thenuki": 445, "infiniris": 446, "chomino": 447, "extrabuki": 448,
    "laure_marge_ambronzio": 444, "dr_jobard": 407, "mckraken": 409,
    "blingos": 423, "cycloptique": 426, "maximain": 425, "bogos": 424,
}
# Occupants dont le bit n'est PAS prouvé posé par leur combat : les six combattants de la rencontre d'Infiniris n'ont
# pas de n° du Médaillium (le n° 446 est porté par un autre CHARA_PARAM, sans doute le 7e ennemi du script [S]) : une
# place sans marqueur qui le contient n'est jamais de progression.
BOSS_BIT_NON_PROUVE: FrozenSet[str] = frozenset({"infiniris"})


def place_du_boss(boss: str, sigma=None) -> str:
    """Clé de la place où le mélange (`sigma[place] = occupant`, identités omises) met ce boss."""
    for place, occupant in (sigma or {}).items():
        if occupant == boss:
            return place
    return boss


def occupant(place: str, sigma=None) -> str:
    return (sigma or {}).get(place, place)


def objectif_effectif(objectif: str, sigma=None) -> Optional[dict]:
    """Objectif d'après-jeu de CETTE graine : entrée d'`OBJECTIFS_BOSS` dont `region`, `chemin`, `objets` et `requetes`
    sont ceux de la PLACE qui contient le boss (`place`), connue à la génération. None : objectif de la V2."""
    o = OBJECTIFS_BOSS.get(objectif) or OBJECTIFS_AUTRES.get(objectif)
    if o is None:
        return None
    if "boss" not in o:
        return dict(o, place=None)
    place = place_du_boss(o["boss"], sigma)
    p = PLACES_BOSS[place]
    eff = dict(o, place=place, region=p["region"], chemin=p["chemin"], objets=p["objets"], requetes=p["requetes"])
    if not eff["requetes"]:
        del eff["requetes"]
    return eff


def objets_objectif(objectif: str, sigma=None) -> Tuple[str, ...]:
    o = objectif_effectif(objectif, sigma)
    if o is None:
        return ()
    return o["objets"]


def region_objectif(objectif: str, sigma=None) -> str:
    return objectif_effectif(objectif, sigma)["region"]


def sur_le_chemin(objectif: str, region: Optional[str] = None, quete: Optional[int] = None,
                  boss: Optional[str] = None, sigma=None) -> bool:
    """Le check est-il sur le chemin de l'objectif (mode « necessaire », et progression permise en mode « complet ») ?
    `boss` : clé de la PLACE d'un boss (clé du mélange) ; `sigma` : mélange des boss d'après-jeu de la graine."""
    o = objectif_effectif(objectif, sigma)
    if o is None:
        return False
    if o["chemin"] == CHEMIN_TOUT:
        return region not in REGIONS_LONGUES
    if quete is not None and quete in o.get("requetes", ()):
        return True
    if boss is not None:
        # place que le chemin fait vaincre AVANT celle qui contient le boss de l'objectif : rang inférieur dans la
        # chaîne des Limbes (Potofeu pour Filomène), ou boss d'une requête du chemin (Chomino, requête 121, pour la
        # place d'Extrabuki). Pas la place de l'objectif elle-même (elle coïncide avec la victoire : exclue).
        b, cible = PLACES_BOSS.get(boss), PLACES_BOSS.get(o["place"])
        if b is None or cible is None or boss == o["place"]:
            return False
        if "rang" in b:
            return "rang" in cible and b["rang"] < cible["rang"]
        if b.get("voie"):
            return False        # (Voie du mystère : jamais sur le chemin d'un boss d'objectif, qui n'y est jamais mis)
        return b["quete"] in o.get("requetes", ())
    return quete is None and region in o["chemin"]


# ---------------------------------------------------------------------------
# Objets d'après-jeu (famille « objet_cle_aj » d'objets.json)
# ---------------------------------------------------------------------------
FAMILLE = "objet_cle_aj"
# Objets testés par possession par le jeu (IsHaveItem) [C] : exigibles dès qu'ils sont dans le pool.
# - Clé de cabane : don de la scène ev11_0300 (c11_trigger n° 6, RunCmd_Phase6) ; testée par c11_trigger n° 7 et
#   t103i33_trigger n° 1 ; la scène se joue toujours (elle pose le flag que le n° 7 exige) : seul le don est substitué ;
# - Clé du Yo-kai World : don de t102g00_quest RunCmd_Quest26 (requête 73, rang S) ; testée par 3 MAP_MESH de t102g00 ;
# - Pass Entrain Exp. : don de t001t03_quest RunCmd_Quest35 (premier trajet de la requête 121 : dans le train de Gera
#   Gera) : emplacement d'origine dans la région « sortilege_express » (lot 6) ; testé par TRAIN_DATA 0xE8ED5E40 ;
# - Pass sortilège : don de t101i02_quest / t101i04_quest RunCmd_Quest12 (chambre : SetQuestPhase('qs0121', 3) puis
#   le don [C, script relu]) ; l'objet du jeu n'a AUCUN lecteur : c'est le verrou étendu k = 47 qui ferme le train ;
#   l'objet AP ne donne rien dans le jeu ; son emplacement se fait sans le Pass (requête 121 d'origine : fin + rang S) ;
# - 4 clés de la Voie du mystère : aucun emplacement d'origine sur émulateur (le passant ev51_2800 ne donne rien sans
#   les données d'une autre version) : toujours dans le pool ; verrous étendus k = 43..46 ;
# - Clés d'appartement A-203 / B-102 : contenus des coffres 489 (Yo-kai World) et 490 (13e étage, verrou de montre S) ;
#   testées par les portes de t105g00 ; B-102 ouvre le coffre 208, A-203 n'ouvre aucun coffre ;
# - Paquet spirituel : donné seulement par un QR code dans le jeu d'origine ; ici objet AP donné réellement ; testé par
#   la condition d'apparition de la requête 120 (retiré par son script).
OBJETS_COFFRES: Dict[str, int] = {"cle_appartement_a_203": 489, "cle_appartement_b_102": 490}
OBJETS_SANS_EMPLACEMENT: Tuple[str, ...] = ("paquet_spirituel",) + CLES_VOIE
# Objets à emplacement d'origine (don de script substitué), dans l'ordre du pool du mode « complet »
OBJETS_A_EMPLACEMENT: Tuple[str, ...] = ("cle_de_cabane", "cle_du_yokai_world", "pass_sortilege", "pass_entrain_exp")
# Emplacements d'origine (dons de script par 0x3B0D, substitution par hachage, sans bit de la réserve) : la détection
# est une entrée de `boss` de slot_data ({location, flag} ou {location, quete, phase_min}).
# - Clé de cabane : flag 391 « évènement vu » de ev11_0300 (crc32 0xCE2ACF91), posé par le RunEvent qui suit le don
#   dans la même fonction ; seul écrivain ; pas dans la liste que la victoire contre Filomène remet à 0 [C] ;
# - Clé du Yo-kai World : flag 561 (0x2866BE19), posé juste avant le don par la même fonction (acceptation de la
#   requête 73, t102g00_quest_trigger n° 26, sans combat avant) ; seul écrivain, jamais remis à 0 [C] ;
# - Pass Entrain Exp. : phase de qs0121 >= 12 (posée par la fonction du don, puis 255) [C].
EMPLACEMENTS: Dict[str, dict] = {
    "cle_de_cabane": {"id_ap": 59422733, "nom_fr": "Objet-clé : Clé de cabane", "nom_en": "Key Item: Shack Key",
                      "flag": 391, "region": "apres_jeu"},
    "cle_du_yokai_world": {"id_ap": 59422734, "nom_fr": "Objet-clé : Clé du Yo-kai World",
                           "nom_en": "Key Item: Yo-kai World Key", "flag": 561, "region": "rang_s"},
    # train de Gera Gera (lot 6) : le Pass Entrain Exp. est donné à la fin du premier trajet (phase 12 de la requête
    # 121) ; le Pass sortilège dans la chambre (phase 3 posée juste avant le don)
    "pass_entrain_exp": {"id_ap": 59422735, "nom_fr": "Objet-clé : Pass Entrain Exp.",
                         "nom_en": "Key Item: Happy-Go-Lucky Pass", "quete": 121, "phase_min": 12,
                         "region": "sortilege_express"},
    "pass_sortilege": {"id_ap": 59422736, "nom_fr": "Objet-clé : Pass sortilège", "nom_en": "Key Item: Hexpress Pass",
                       "quete": 121, "phase_min": 3, "region": "rang_s", "verrou": "pass_sortilege",
                       # hachage du don d'origine à substituer (l'objet AP n'a pas de hachage : il ne donne rien)
                       "hachages": (0x0B6C2930,)},
}

# ---------------------------------------------------------------------------
# Requêtes et services d'après-jeu (QUEST_CONFIG : phase >= 11-10, ou flag 1 pour les services) [C, quetes.py]
# ---------------------------------------------------------------------------
# (n°, identifiant AP, FR, EN, région, rang de montre exigé « A » / « S », objets testés sur le chemin, requêtes
# exigées finies d'AVANT la fin (leur règle s'ajoute), verrou du lot parallèle, service)
# Rang S = région « rang_s » (requête 28 faite). Toutes EXCLUES de la progression sauf celles du chemin de l'objectif
# (28 pour Extrabuki) : aucune n'est traversée par les objectifs des Limbes ; services : toujours exclus (255 transitoire).
QUETES: List[dict] = []


def _q(n, id_ap, fr, en, region, rang, objets=(), requetes=(), verrou=None, service=False, hasard=False):
    QUETES.append({"n": n, "id_ap": id_ap, "region": region, "rang_reel": rang, "objets": tuple(objets),
                   "requetes": tuple(requetes), "verrou": verrou, "service": service, "hasard": hasard,
                   "nom_fr": ("Service : " if service else "Requête : ") * (n != 28) + fr,
                   "nom_en": ("Service: " if service else "Request: ") * (n != 28) + en})


# rang A (ville)
_q(22, 59420292, "Épreuves de Nyada I", "Nyada's Trials I", "apres_jeu", "A")      # + Tuyau (deux dons : d'origine)
_q(28, 59420053, "Obtenons le rang S !", "Go for Rank S!", "apres_jeu", "A")       # identifiant réservé de l'ancien mod
_q(36, 59420293, "C-1 Grand Prix X", "C-1 Grand Prix X", "apres_jeu", "A")
_q(43, 59420294, "Regarder les cieux", "Watch the Skies", "apres_jeu", "A")
_q(61, 59420295, "Devoirs d'été - 3e partie", "Independent Study, Pt. 3", "apres_jeu", "A", requetes=(60,))
_q(75, 59420296, "L'histoire de M. Loiseau", "Mr. Byrd's Tragic Tale", "apres_jeu", "A")
_q(77, 59420297, "Le prix du monde", "The Price of the World", "apres_jeu", "A", requetes=(57,))
_q(81, 59420298, "Aider Mamie", "Little Grandma's Helper", "apres_jeu", "A")       # + flag 1342 (ev70_8110) [?]
_q(117, 59420299, "Leçon d'Whistoire 1", "Whistory Lesson, Part 1", "apres_jeu", "A")   # + flags 1238, 1273 [?]
_q(118, 59420300, "Leçon d'Whistoire 2", "Whistory Lesson, Part 2", "apres_jeu", "A")
_q(119, 59420301, "Leçon d'Whistoire 3", "Whistory Lesson, Part 3", "apres_jeu", "A")
_q(120, 59420302, "La maison de Jibanyan", "Jibanyan's Own Home", "apres_jeu", "A", objets=("paquet_spirituel",),
   requetes=(71,))
# rang S
# 23 et 24 : la requête ne finit que par la branche « devenu ami » de son combat du jour (Démophage, Maître Nyada)
# [C : seul QuestComplete de chaque script] : hasard ; 74 : exige la Glu spectrale, butin au hasard du boss Potofeu
_q(23, 59420303, "Épreuves de Nyada II", "Nyada's Trials II", "rang_s", "S", hasard=True)
_q(24, 59420304, "Épreuves de Nyada III", "Nyada's Trials III", "rang_s", "S", hasard=True)
_q(39, 59420305, "En train légendaire", "A Legend's Loco Motive", "rang_s", "S", requetes=(90,))
# requête 73 : le don de la Clé du Yo-kai World est au milieu ; la suite est derrière la porte : la finir exige la clé
_q(73, 59420306, "Retour au Yo-kai World", "Back to Yo-kai World", "rang_s", "S", objets=("cle_du_yokai_world",))
_q(74, 59420307, "Vision du cauchemar", "Nightmare Revelation", "rang_s", "S",
   objets=("cle_du_yokai_world", "cle_de_cabane"), hasard=True)
_q(84, 59420308, "Le dieu de l'océan", "The God of the Sea", "rang_s", "S")
_q(91, 59420309, "Injustin : les origines", "Unfairy: Origins", "origines", "S")
_q(92, 59420310, "Fielippine : les origines", "Unkaind: Origins", "origines", "S")
_q(93, 59420311, "Cyrustre : les origines", "Untidy: Origins", "origines", "S")
_q(94, 59420312, "Maudicko : les origines", "Unpleasant: Origins", "origines", "S")
_q(95, 59420313, "Ronéan : les origines", "Unkeen: Origins", "origines", "S")
_q(96, 59420314, "Temps suspendu", "Tamer of Time", "chateau_de_sawayama", "S", requetes=(125,))
_q(101, 59420315, "C-1 Grand Prix Y", "C-1 Grand Prix Y", "rang_s", "S", requetes=(33, 34, 35))
_q(102, 59420316, "Héritage légendaire", "Legendary Legacy", "rang_s", "S")
_q(103, 59420317, "Pauvre Barbefrousse", "Cap'n Crash...'n' Burn", "rang_s", "S", requetes=(85,))
# train de Gera Gera et stations (verrou « pass_sortilege », région « sortilege_express » : Pass + fin de l'histoire).
# 121 : avec le Pass reçu le jeu la propose sans condition : aucun rang ; 122, 123, 124 : rang S (QUEST_CONFIG) ;
# 124 exige aussi la requête 73 en phase >= 2 (acceptée : rang S, sans la Clé du Yo-kai World)
_q(121, 59420318, "Direction Gera Gera !", "Getting to Gera Gera", "sortilege_express", None)
_q(122, 59420319, "Exploration de Gera Gera", "Getting Gera Gera Going", "sortilege_express", "S")
_q(123, 59420320, "Au revoir Gera Gera", "Gera Gera Good-Byes", "sortilege_express", "S")
_q(124, 59420321, "Le Darknyan", "The Darknyan", "sortilege_express", "S")
# requêtes à transfert d'après-jeu (option `requetes_transfert` : fonction 37 du patch, archipelago_v3_transfert.md §6).
# 110 et 115 exigent le même objet important `iky1001` (un seul en sac), butin de deux Yo-kai sauvages des Limbes et
# du Sanctuaire divin (Clé de cabane) dont le lieu dépend du mélange des Yo-kai calculé chez le joueur : `hasard`
# (jamais de progression) et règle prudente (Clé de cabane). 111 exige la requête 73 finie (Clé du Yo-kai World).
_q(110, 59420322, "Le général des farceurs", "The Bony General", "rang_s", "S", objets=("cle_de_cabane",),
   verrou="transfert", hasard=True)
_q(111, 59420323, "Enma et le Serpent", "Enma and the Serpent", "rang_s", "S", objets=("cle_du_yokai_world",),
   verrou="transfert")
_q(115, 59420324, "Le général des bouffis", "Fleshy Souls General", "rang_s", "S", objets=("cle_de_cabane",),
   verrou="transfert", hasard=True)
_q(116, 59420325, "Le sanctuaire du renard", "The Old Fox Shrine", "rang_s", "S", verrou="transfert")
# services d'après-jeu (flag 1 ET rang ; 159 / 169 : le soir ou la nuit ; 160 / 170 : rang == S)
_q(159, 59420326, "Tout ce qui brille", "All That Glitters", "apres_jeu", "A", service=True)
_q(160, 59420327, "Une superbe prise", "A Swell Catch", "rang_s", "S", service=True)
_q(169, 59420328, "Lunettes spectrales", "Specter Spectacles", "apres_jeu", "A", service=True)
_q(170, 59420329, "Donne-toi à fond !", "Reach Your Potential!", "rang_s", "S", service=True)
QUETES_PAR_NUMERO: Dict[int, dict] = {q["n"]: q for q in QUETES}


def quete_ouverte(q: dict, transfert: bool = False) -> bool:
    """`transfert` : option `requetes_transfert` de la graine (les requêtes à transfert n'existent qu'avec elle)."""
    if q["verrou"] == "transfert" and not transfert:
        return False
    return region_ouverte(q["region"]) and (q["verrou"] is None or VERROUS_DISPONIBLES[q["verrou"]])


# ---------------------------------------------------------------------------
# Requêtes à transfert d'AVANT la fin (option `requetes_transfert`, archipelago_v3_transfert.md §3 et §6)
# ---------------------------------------------------------------------------
# Format des requêtes de `logique.QUETES` (chapitre de la règle « Chapitre N terminé », région du donneur, rang).
# Progression possible seulement si l'accès est SÛR : 108 (aucune exigence : un combat le soir). Les cinq autres sont
# EXCLUES (remplissage) : elles exigent des objets dont la source n'a pas été relue (107 : deux livres ; 112 : 20
# boulettes de riz ; 113 : une poupée de fer), un Yo-kai à faire évoluer (107 : Rugis ; 112 : Onigirix) ou dont la
# source dépend du mélange des Yo-kai (109 : Faux Kappa, et une créature à pêcher ; 114 : Parantonn, un des 16 des
# armées). Identifiants : 112, 113, 114 = ceux que la V2 réservait (`logique.QUETES_NON_CREEES`) ; 107 à 109 nouveaux.
QUETES_TRANSFERT: List[dict] = [
    {"n": 107, "id_ap": 59420330, "fr": "Entraînons Roupilion", "en": "Train Lie-in with Pride", "chapitre": 4,
     "region": "ourcival", "rang_reel": "D", "exclue": True},
    {"n": 108, "id_ap": 59420331, "fr": "Le sceau du mal", "en": "Seal No Evil", "chapitre": 6,
     "region": "quartier_des_boutiques", "rang_reel": "C", "exclue": False},
    {"n": 109, "id_ap": 59420332, "fr": "Le véritable Kappa", "en": "The Realest Kappa", "chapitre": 8,
     "region": "ourcival", "rang_reel": "B", "objets": ("canne_a_peche",), "exclue": True},
    {"n": 112, "id_ap": 59420212, "fr": "Agonigiri a des soucis", "en": "Slicenrice Under Fire", "chapitre": 4,
     "region": "quartier_des_boutiques", "rang_reel": "D", "exclue": True},
    {"n": 113, "id_ap": 59420240, "fr": "Le prix du fer", "en": "The Price of Iron", "chapitre": 6,
     "region": "mont_sylvestre", "rang_reel": "C", "exclue": True},
    {"n": 114, "id_ap": 59420255, "fr": "Tout droit sorti du futur !", "en": "From the Future!", "chapitre": 8,
     "region": "menu", "rang_reel": "B", "exclue": True},
]
for _t in QUETES_TRANSFERT:
    _t.setdefault("objets", ())
    _t.update(verrou_montre=None, service=False, nom_fr="Requête : " + _t["fr"], nom_en="Request: " + _t["en"])
QUETES_TRANSFERT_PAR_NUMERO: Dict[int, dict] = {q["n"]: q for q in QUETES_TRANSFERT}
# Amis des requêtes à transfert d'avant la fin : le Yo-kai ne vient qu'à 7,5 % par REVANCHE gagnée (déclencheur 78 de
# la rencontre : quête à 255 ET Random(7,5)) : checks « Ami » EXCLUS (hasard), avec l'option `amis` = tous.
AMIS_TRANSFERT: List[dict] = [
    {"medaille": 232, "id_ap": 59420923, "yokai_fr": "Triptyk", "yokai_en": "Slimamander", "quete": 108},
    {"medaille": 316, "id_ap": 59420924, "yokai_fr": "Carpitaine", "yokai_en": "SV Snaggerjag", "quete": 113},
]
for _t in AMIS_TRANSFERT:
    _t.update(nom_fr="Ami : " + _t["yokai_fr"], nom_en="Friend: " + _t["yokai_en"])


BOUTIQUE_ENTRAIN = "N047"               # boutique du wagon-restaurant de l'Entrain Express (déjà « x_train » en V2)


# ---------------------------------------------------------------------------
# Boss d'après-jeu à marqueur persistant de PLACE (archipelago_v3_boss_objectifs.md §2.1, §3.6)
# ---------------------------------------------------------------------------
# `mode` : mode minimal de l'option `boss` (« histoire » : chaîne des Limbes et Yo-kai World ; « quetes » : boss de
# requête). Marqueur : flag bit global du hachage de la rencontre (moteur, victoire seulement), quête à 255, ou octet
# global. Le check suit la PLACE (comme en V2).
# `place` : clé de la place dans le mélange des boss (PLACES_BOSS), quand elle diffère de `cle`.
# Places SANS marqueur persistant (lot 10) : BOSS_MEDAILLE, plus bas.
BOSS: List[dict] = [
    {"cle": "potofeu", "id_ap": 59423023, "nom_fr": "Boss : Potofeu", "nom_en": "Boss: Wobblewok",
     "flag": 1322, "region": "limbes_eternelles", "mode": "histoire"},
    {"cle": "filomene", "id_ap": 59423024, "nom_fr": "Boss : Filomène", "nom_en": "Boss: Kat Kraydel",
     "flag": 2, "region": "sanctuaire_divin", "mode": "histoire"},
    {"cle": "extrabuki", "id_ap": 59423025, "nom_fr": "Boss : Extrabuki", "nom_en": "Boss: Kabuking",
     "quete": 123, "region": "sortilege_express", "mode": "quetes"},
    {"cle": "thenuki", "id_ap": 59423026, "nom_fr": "Boss : Thénuki", "nom_en": "Boss: Teastroyer",
     "quete": 120, "region": "apres_jeu", "mode": "quetes"},
    {"cle": "infiniris", "id_ap": 59423027, "nom_fr": "Boss : Infiniris", "nom_en": "Boss: Infinipea",
     "quete": 81, "region": "apres_jeu", "mode": "quetes"},
    {"cle": "chomino", "id_ap": 59423028, "nom_fr": "Boss : Chomino", "nom_en": "Boss: Headasteam",
     "quete": 121, "region": "sortilege_express", "mode": "quetes"},
    {"cle": "ambronzio", "id_ap": 59423029, "nom_fr": "Boss : Ambronzio", "nom_en": "Boss: Bronzlow",
     "quete": 96, "region": "chateau_de_sawayama", "mode": "quetes", "place": "laure_marge_ambronzio"},
    {"cle": "dr_jobard", "id_ap": 59423030, "nom_fr": "Boss : Dr Jobard", "nom_en": "Boss: Dr. Maddiman",
     "quete": 77, "region": "apres_jeu", "mode": "quetes"},
]
BOSS_PAR_CLE: Dict[str, dict] = {b["cle"]: b for b in BOSS}
for _b in BOSS:
    _b.setdefault("place", _b["cle"])
# Marqueurs revérifiés pour ce lot [C] : 255 n'est posé qu'après la victoire pour les requêtes 120 (t102i01 n° 3, type
# 78), 81 (phase 10, qui ne survit qu'à une victoire), 121, 96 (phase 6 posée par la victoire seulement) et 77 (t105d41
# n° 15, type 78) ; flags 1322 et 2 : jamais écrits ni remis à 0 par un script.
# McKraken (Yo-kai World, t001d42) : AUCUN marqueur persistant : son octet global (catégorie 6, index 600) vaut 1 après
# la victoire mais la réinitialisation quotidienne le remet à 0 (combat « du jour ») ; il exige en plus le Yo-kai du
# Tablo-blabla n° 24 appelé (flag 2144).
#
# Places SANS marqueur persistant (V3, lot 10) : le check est le BIT DU MÉDAILLIUM DE L'OCCUPANT de la place (le boss
# que le mélange de la graine y met ; sans mélange : le boss d'origine), posé par le moteur à la victoire seulement
# (FUN_005579A8). Entrée {location, medaille} de la liste `amis` de slot_data (mêmes bits, même lecture groupée du
# client). Dix places de la chaîne des Limbes (combats 1 à 7 et 9 à 11) et McKraken (figé : toujours le n° 409 ; exclu :
# Tablo-blabla n° 24 = posséder un Yo-kai précis). Noms anglais relus dans l'archive `engb` de la ROM européenne.
# Identifiants : la réserve du lot 3 (59423031..59423040) en avait dix pour onze places ; 59423041 était libre.
BOSS_MEDAILLE: List[dict] = [
    {"cle": "mckraken", "id_ap": 59423031, "nom_fr": "Boss : McKraken", "nom_en": "Boss: McKraken",
     "region": "yokai_world", "mode": "histoire", "objets": ("cle_du_yokai_world",), "fige": True},
    {"cle": "hydreux", "id_ap": 59423032, "nom_fr": "Boss : Hydreux", "nom_en": "Boss: Eyedra"},
    {"cle": "porcinator", "id_ap": 59423033, "nom_fr": "Boss : Porcinator", "nom_en": "Boss: Hoggles"},
    {"cle": "styx_vi", "id_ap": 59423034, "nom_fr": "Boss : Styx VI", "nom_en": "Boss: Styx Mk.VI"},
    {"cle": "nebulor", "id_ap": 59423035, "nom_fr": "Boss : Nébulor", "nom_en": "Boss: Clipso"},
    {"cle": "pr_letripe", "id_ap": 59423036, "nom_fr": "Boss : Pr Létripe", "nom_en": "Boss: Dr. Nogut"},
    {"cle": "hagacuree", "id_ap": 59423037, "nom_fr": "Boss : Hagacurée", "nom_en": "Boss: Spooklunk"},
    {"cle": "rancornet", "id_ap": 59423038, "nom_fr": "Boss : Rancornet", "nom_en": "Boss: Squisker"},
    {"cle": "barbebluff", "id_ap": 59423039, "nom_fr": "Boss : Barbebluff", "nom_en": "Boss: Cap'n Rex"},
    {"cle": "mariotte_et_maribass", "id_ap": 59423040, "nom_fr": "Boss : Mariotte et Maribass",
     "nom_en": "Boss: Flippa and Floppa"},
    {"cle": "lady_maggie", "id_ap": 59423041, "nom_fr": "Boss : Lady Maggie", "nom_en": "Boss: Dame Dredful"},
    # ap/boss-voie-mystere (graines générées depuis : `logique.construire_plan(boss_voie=True)`) : les 4 places de la
    # Voie du mystère, dans la région de leur ligne (Clé terrifiante + clé de la ligne). Aucun marqueur persistant de
    # place : les bits « vaincu » 2524..2527 sont remis à 0 par la réinitialisation du jour réel (common_trigger
    # n° 131) [C] ; le check est le bit du Médaillium de l'occupant, comme les Limbes. Noms anglais relus dans `engb`.
    {"cle": "blingos", "id_ap": 59423042, "nom_fr": "Boss : Blingos", "nom_en": "Boss: Goldy Bones", "voie": True},
    {"cle": "cycloptique", "id_ap": 59423043, "nom_fr": "Boss : Cycloptique", "nom_en": "Boss: Retinado",
     "voie": True},
    {"cle": "maximain", "id_ap": 59423044, "nom_fr": "Boss : Maximain", "nom_en": "Boss: Hans Galore", "voie": True},
    {"cle": "bogos", "id_ap": 59423045, "nom_fr": "Boss : Bogos", "nom_en": "Boss: Glitzy Bones", "voie": True},
]
for _b in BOSS_MEDAILLE:
    if not _b.get("fige"):
        _b.update(region=PLACES_BOSS[_b["cle"]]["region"], mode="histoire", objets=(), fige=False)
    _b.setdefault("voie", False)
    _b["place"] = _b["cle"]
BOSS_RESERVES = tuple(b["id_ap"] for b in BOSS_MEDAILLE if not b["voie"])
BOSS_VOIE_IDS = tuple(b["id_ap"] for b in BOSS_MEDAILLE if b["voie"])       # (59423042..59423045)

# Tablo-blabla n° 24 (Yo-kai World, t001d42) : flag « Yo-kai appelé » 2144, identifiant réservé de la V2 (59422323) ;
# exclu comme les autres (posséder un Yo-kai précis).
TABLO_24_REGION = "yokai_world"

# ---------------------------------------------------------------------------
# Amis d'après-jeu (bit « ami » du Médaillium) : TOUS exclus de la progression (amitié au hasard, action de menu)
# ---------------------------------------------------------------------------
# (n° du Médaillium, identifiant AP, FR, EN, région, origine, objets, requête, verrou)
# - « sauvage » : espèces sauvages seulement après la fin (identifiants réservés par `AMIS_RETIRES_AVANT_FIN`) ;
# - « don » : don du script d'une requête d'après-jeu ;
# - « legendaire » : sceau du Médaillium brisé par le joueur (menu) quand ses 8 membres sont amis ;
# - « transfert » : Kyubi et Octorgone (requêtes 116 et 111 du lot parallèle).
AMIS: List[dict] = []


def _a(medaille, id_ap, fr, en, region, origine, objets=(), quete=None, verrou=None, raison=""):
    AMIS.append({"medaille": medaille, "id_ap": id_ap, "region": region, "origine": origine, "objets": tuple(objets),
                 "quete": quete, "verrou": verrou, "raison": raison, "yokai_fr": fr, "yokai_en": en,
                 "nom_fr": "Ami : " + fr, "nom_en": "Friend: " + en})


# Sauvages [C, rencontres de la ROM : errants de fichiers normaux, sans condition, recrutables] : Chymère et Vénaldo
# dans les Limbes ; Tengu, Kyryn, Nimpégase et Satandre (rare) au Sanctuaire divin ; Timidémon au Yo-kai World ;
# Donjouant sur la Grand-route dorée seulement (fermée).
_a(57, 59420690, "Donjouant", "Casanuva", "grand_route_doree", "sauvage")
_a(78, 59420704, "Tengu", "Tengu", "sanctuaire_divin", "sauvage")
_a(82, 59420705, "Chymère", "Chymera", "limbes_eternelles", "sauvage")
_a(153, 59420736, "Satandre", "Pookivil", "sanctuaire_divin", "sauvage")
_a(200, 59420765, "Kyryn", "Kyryn", "sanctuaire_divin", "sauvage")
_a(234, 59420785, "Nimpégase", "Negasus", "sanctuaire_divin", "sauvage")
_a(236, 59420786, "Timidémon", "Timidevil", "yokai_world", "sauvage")
_a(241, 59420787, "Vénaldo", "Greesel", "limbes_eternelles", "sauvage")
# Dons de script (AddPartyEx avec fenêtre « nouvel ami ») [C] : Millyeux après la victoire de la requête 22 ; Volatriste
# dans la fonction qui finit la requête 75 ; Potofeu dans celle qui finit la requête 74, qui exige la Glu spectrale,
# butin au hasard du boss Potofeu (Limbes) : hasard.
_a(239, 59420910, "Millyeux", "Eyesoar", "apres_jeu", "don", quete=22)
_a(243, 59420911, "Potofeu", "Wobblewok", "rang_s", "don", objets=("cle_de_cabane",), quete=74)
_a(258, 59420912, "Volatriste", "Skreek", "apres_jeu", "don", quete=75)
# Légendaires (sceau brisé dans le Médaillium quand ses 8 membres sont amis) : règle prudente = la fin de l'histoire et
# ce que leurs membres d'après-jeu exigent ; plusieurs membres ne s'obtiennent qu'au hasard (Bingo-kai, Tunnel sans
# fin, Yo-kai de Pièce 5 étoiles) : « long », jamais de progression.
# Déballerine : Maître Nyada et Démophage (requêtes 24 et 23, rang S) ; Cabotin : Volatriste (requête 75).
_a(322, 59420913, "Shogunyan", "Shogunyan", "apres_jeu", "legendaire")
_a(323, 59420914, "Komashura", "Komashura", "apres_jeu", "legendaire")
_a(324, 59420915, "Gorgouille", "Gilgaros", "apres_jeu", "legendaire")
_a(325, 59420916, "Déballerine", "Spoilerina", "rang_s", "legendaire", quete=24)
_a(326, 59420917, "Camaïeul", "Elder Bloom", "apres_jeu", "legendaire")
_a(328, 59420919, "Cabotin", "Dandoodle", "apres_jeu", "legendaire", quete=75)
_a(329, 59420920, "Slurpent", "Slurpent", "apres_jeu", "legendaire")
# (option `requetes_transfert`) : Kyubi et Octorgone n'ont AUCUNE source hors des requêtes à transfert [C] : don de
# script à 7,5 % par victoire de la revanche de la requête 116 (Kyubi, t101i58) / 111 (Octorgone, t102d02), après la
# requête finie ; Savantard (sceau : Kyubi et Octorgone) en dépend : règle de la requête 111 (la plus exigeante).
_a(80, 59420921, "Kyubi", "Kyubi", "rang_s", "transfert", quete=116, verrou="transfert")
_a(320, 59420922, "Octorgone", "Venoct", "rang_s", "transfert", quete=111, verrou="transfert")
_a(327, 59420918, "Savantard", "Poofessor", "rang_s", "legendaire", quete=111, verrou="transfert")

# ---------------------------------------------------------------------------
# Mode « YO-KAI WATCH Blasters » : terrains finis de Ψ Blasters (archipelago_v3_blasters.md)
# ---------------------------------------------------------------------------
# Check = bit n (n° du terrain) du mot P + 0x64C, posé par le jeu à la fin du Bingo-kai oni d'une partie gagnée sur un
# terrain que le joueur a débloqué, jamais remis à 0 [C]. Lu par le client à la suite de la lecture groupée du
# Médaillium (16 octets de plus dans le même paquet). Aucun code du jeu. Le mode s'ouvre à la phase 4-10 (flag 75) :
# règle « Chapitre 3 terminé ». Le joueur y joue seul (confirmé par l'humain).
# - « court » : Gargaros (aucune condition), Crocho (300 orbes au total) : progression possible ;
# - « long » : total d'orbes de 1 000 à 6 000 : EXCLUS (jamais de progression), marqués pour le lanceur ;
# - après-jeu (avec `apres_jeu` = complet seulement, exclus) : Lady Perpétua (requête 96 finie), Potofeu (boss vaincu) ;
# - Jiganyan / Komak : exigent la rencontre de Jibanyan S / Komasan S (flags 2104 / 2105), que seule leur invitation
#   rend possible : créés seulement si l'invitation est dans le pool ;
# - Triptyk (terrain 3 : 30 photos de Yo-kai, appareil photo de la console) et Domniscian (terrain 13 : terrains 1 à 10
#   finis, donc le 3) : V3, lot 22 (décision de l'humain du 2026-10-17) : avec `blasters` = tous, le client pose l'option
#   étendue 33 du jeu (photos tenues pour prises, lot 21 : `Plan.photos`) et ces deux terrains sont des checks EXCLUS
#   (« lot22 ») : Triptyk « long » ; Domniscian d'après-jeu (`apres_jeu` = complet, Château de Sawayama ET Limbes
#   éternelles ouverts : terrains 9 et 10 ; Canne et Filet du terrain 4), et son check « Ami » (`AMI_DOMNISCIAN`)
#   avec `amis` = tous : la première victoire sur le terrain 13 pose le bit « ami » du n° 443 [C, FUN_0040AD40]. Une
#   graine d'avant le lot 22 ne les a pas (`construire_plan(lot22=False)`, reconnue par le tracker à l'absence du
#   terrain 3 dans `slot_data.blasters`).
BLASTERS: List[dict] = [
    {"terrain": 1, "id_ap": 59423051, "fr": "Gargaros", "en": "Gargaros", "classe": "court"},
    {"terrain": 2, "id_ap": 59423052, "fr": "Crocho", "en": "Sproink", "classe": "court"},
    {"terrain": 3, "id_ap": 59423053, "fr": "Triptyk", "en": "Slimamander", "classe": "long", "lot22": True},
    {"terrain": 4, "id_ap": 59423054, "fr": "Carpitaine", "en": "SV Snaggerjag", "classe": "long",
     "objets": ("canne_a_peche", "filet_a_insectes")},              # 30 créatures différentes
    {"terrain": 5, "id_ap": 59423055, "fr": "Ogralos", "en": "Ogralus", "classe": "long"},
    {"terrain": 6, "id_ap": 59423056, "fr": "McKraken", "en": "McKraken", "classe": "long"},
    {"terrain": 7, "id_ap": 59423057, "fr": "Démophage", "en": "Demuncher", "classe": "long"},
    {"terrain": 8, "id_ap": 59423058, "fr": "Orqanos", "en": "Orcanos", "classe": "long"},
    {"terrain": 9, "id_ap": 59423059, "fr": "Lady Perpétua", "en": "Dame Dedtime", "classe": "apres_jeu",
     "region": "chateau_de_sawayama"},
    {"terrain": 10, "id_ap": 59423060, "fr": "Potofeu", "en": "Wobblewok", "classe": "apres_jeu",
     "region": "limbes_eternelles"},
    {"terrain": 11, "id_ap": 59423061, "fr": "Jiganyan", "en": "Rubeus J", "classe": "long",
     "invitation": "invitation_jibanyan_s"},
    {"terrain": 12, "id_ap": 59423062, "fr": "Komak", "en": "Hardy Hound", "classe": "long",
     "invitation": "invitation_komasan_s"},
    {"terrain": 13, "id_ap": 59423063, "fr": "Domniscian", "en": "Hinozall", "classe": "apres_jeu",
     "region": "chateau_de_sawayama", "regions_aussi": ("limbes_eternelles",),
     "objets": ("canne_a_peche", "filet_a_insectes"), "lot22": True},
]
for _b in BLASTERS:
    _b["nom_fr"] = "Ψ Blasters : " + _b["fr"]
    _b["nom_en"] = "Psychic Blasters: " + _b["en"]
BLASTERS_PAR_TERRAIN: Dict[int, dict] = {b["terrain"]: b for b in BLASTERS}
# Terrains absents des graines générées avant le lot 22 (identifiants réservés depuis le lot 3)
BLASTERS_ABSENTS: Dict[int, str] = {59423053: "Triptyk (terrain 3)", 59423063: "Domniscian (terrain 13)"}
# V3, lot 22 : check « Ami : Domniscian » (n° 443 du Médaillium), avec `blasters` = tous, `amis` = tous et le terrain 13
# dans la graine : même règle et même région que le terrain 13, exclu. Identifiant à la suite d'« Ami : Bananar ».
AMI_DOMNISCIAN: dict = {"medaille": 443, "id_ap": 59420949, "yokai_fr": "Domniscian", "yokai_en": "Hinozall",
                        "nom_fr": "Ami : Domniscian", "nom_en": "Friend: Hinozall", "terrain": 13}
# V3, lot 22-bis (décision de l'humain du 2026-10-18) : « Ami : Jiganyan » (n° 441) et « Ami : Komak » (n° 442), sur le
# modèle d'« Ami : Domniscian » : la première victoire sur le terrain 11 / 12 pose le bit « ami » sans donner le Yo-kai
# [C, FUN_0040AD40, boss n° 13 / 14]. Créés avec le terrain (`blasters` = tous, invitation de Jibanyan S / Komasan S dans
# la graine) et `amis` = tous : même règle, même région, même marque, EXCLUS. Une graine d'avant ne les a pas
# (`construire_plan(lot22bis=False)`, reconnue par le tracker à l'absence de ces deux identifiants dans `amis`).
AMIS_BLASTERS: List[dict] = [
    {"medaille": 441, "id_ap": 59420950, "yokai_fr": "Jiganyan", "yokai_en": "Rubeus J", "terrain": 11},
    {"medaille": 442, "id_ap": 59420951, "yokai_fr": "Komak", "yokai_en": "Hardy Hound", "terrain": 12},
]
for _t in AMIS_BLASTERS:
    _t.update(nom_fr="Ami : " + _t["yokai_fr"], nom_en="Friend: " + _t["yokai_en"])
# Check « Ami » posé par la première victoire sur un terrain : n° du terrain -> entrée (lot 22 : 13 ; lot 22-bis : 11, 12)
AMIS_PAR_TERRAIN: Dict[int, dict] = {a["terrain"]: a for a in [AMI_DOMNISCIAN] + AMIS_BLASTERS}
MODES_BLASTERS = ("aucun", "debut", "tous")
BLASTERS_PAR_DEFAUT = "aucun"
BLASTERS_CHAPITRE = 4                    # règle de « Chapitre 3 terminé » : chapitre 4 commencé (phase 4-10)
BLASTERS_REGION = "les_hauts_de_granval"  # menu du Yo-kai Pad : sans lieu ; région d'origine de l'histoire
# N° « client » de `fonctions_exigees` (jamais publié par le jeu) pour les lectures et la victoire nouvelles du client
# de ce lot (mot des terrains de Blasters, victoire par le bit du Médaillium) : un client d'avant refuse la graine.
FONCTION_CLIENT_5 = 66

# ap/blasters-terrains-apworld (docs/systemes/archipelago_v3_blasters_terrains.md §7, §10 ; côté jeu : blasters.cpp) :
# option `blasters_terrains` (désactivée par défaut, graines nouvelles seulement, sans effet avec `blasters` = aucun) :
# un objet AP « Terrain : <boss> » par terrain à condition de déblocage (n = 2..13, 12 objets ; Ruée de triple boss 0 et
# Gargaros 1 restent ouverts d'office, décision de l'humain du 2026-11-05), famille `terrain_blasters`, don « aucun »,
# identifiant 59429650 + n (59429650 / 59429651 réservés, jamais créés). Verrou k = 66 + n de la zone ApVerrous3 (68..79 ;
# 67 réservé, jamais compilé), écrit génériquement par le client : en vigueur, le jeu tient le terrain pour débloqué SI
# ET SEULEMENT SI l'objet est reçu (au menu ET pour le bit « terrain fini »). Avec l'option, les 13 terrains (1 à 13,
# quel que soit le mode `debut` / `tous`) sont des checks NORMAUX : règle « Chapitre 3 terminé » + l'objet du terrain
# (Gargaros : le chapitre seul) ; « Ami : Domniscian / Jiganyan / Komak » (avec `amis` = tous) : même règle que le
# terrain, non exclus.
FAMILLE_TERRAINS = "terrain_blasters"
TERRAINS_A_OBJET: Tuple[int, ...] = tuple(range(2, 14))
ID_AP_TERRAINS_BASE = 59429650
VERROU_TERRAINS_BASE = 66
OBJET_TERRAIN: Dict[int, str] = {n: "terrain_blasters_%d" % n for n in TERRAINS_A_OBJET}
TERRAIN_DE_OBJET: Dict[str, int] = {v: n for n, v in OBJET_TERRAIN.items()}
VERROUS_TERRAINS: Dict[str, dict] = {
    OBJET_TERRAIN[n]: {"k": VERROU_TERRAINS_BASE + n, "mecanisme": "terrain_blasters", "code_jeu": True, "terrain": n}
    for n in TERRAINS_A_OBJET}
BLASTERS_TERRAINS_PAR_DEFAUT = False
CLE_SLOT_DATA_TERRAINS = "blasters_terrains"
# Terrains d'AUTRES ÉDITIONS (Jiganyan 11, Komak 12 : masques de version 1 / 2, jamais listés seul dans cette édition,
# archipelago_v3_blasters_terrains.md §2.6, §9) : le client pose l'option étendue 35 du jeu (bit 3 de
# ApPieces::options) pour toute graine NOUVELLE qui a leur terrain ou leur « Ami » par cette voie, ou l'objectif
# « medaillium_complet » (voies 441 / 442 comptées) : clé `blasters_autres_editions` = true de slot_data, n° « client »
# 80 (jamais publié par le jeu : un client d'avant ne poserait pas le bit) + 22. Une graine d'avant ne l'a pas : ces
# checks y sont infaisables seul (le tracker les marque).
TERRAINS_AUTRES_EDITIONS: Tuple[int, ...] = (11, 12)
MEDAILLES_AUTRES_EDITIONS: Tuple[int, ...] = (441, 442)
CLE_SLOT_DATA_EDITIONS = "blasters_autres_editions"
FONCTION_CLIENT_EDITIONS = 80
OPTION_EDITIONS = 35

# Marque des locations d'après-jeu pour le lanceur (`LocationPlan.apres_jeu`) : clé de la région ; « blasters » pour
# les terrains longs du mode Blasters.
MARQUE_BLASTERS_LONG = "blasters_long"
# Lot 6 : marque des requêtes à transfert d'AVANT la fin et de leurs amis (mention du lanceur ; pas de l'après-jeu)
MARQUE_TRANSFERT = "transfert"
# Marques de `LocationPlan.apres_jeu` qui ne désignent PAS une location d'après-jeu (elles existent avec tout objectif)
MARQUES_HORS_APRES_JEU = frozenset({MARQUE_BLASTERS_LONG, MARQUE_TRANSFERT})


def tous_les_noms(langue: str) -> Dict[str, int]:
    """nom -> identifiant AP de toutes les locations d'après-jeu DÉCLARÉES (ouvertes ou non) : le paquet de données
    ne dépend pas des options ; les coffres sont dans `coffres.json`."""
    t: Dict[str, int] = {}
    for e in EMPLACEMENTS.values():
        t[e["nom_" + langue]] = e["id_ap"]
    for x in QUETES + BOSS + BOSS_MEDAILLE + AMIS + BLASTERS + QUETES_TRANSFERT + AMIS_TRANSFERT + [AMI_DOMNISCIAN] \
            + AMIS_BLASTERS:
        t[x["nom_" + langue]] = x["id_ap"]
    return t
