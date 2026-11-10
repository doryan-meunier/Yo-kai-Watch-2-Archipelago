# -*- coding: utf-8 -*-
"""V3, lots M2b-1 et M2b-2 : mélange des Yo-kai lié à la logique, « conception (b) »
(docs/systemes/archipelago_v3_melange_zones.md, conception : archipelago_v3_conception_b.md).

Chaque Yo-kai DEMANDÉ (à posséder ou à vaincre N fois par une requête ou un service, à appeler pour un Tablo-blabla)
reçoit à la génération une ZONE (clé de région de l'APWorld), toujours différente de ses zones d'origine ; la logique
exige l'accès à cette zone (`regle_zone`) pour toute location qui le demande (et pour l'évènement « Chapitre N terminé »
quand l'histoire attend une requête qui le demande) ; chez le joueur, le client le place à `K` endroits de la zone lors
du mélange par rencontre (version 7) et refuse proprement si c'est impossible.

Règle 6 de CLAUDE.md : ce fichier ne contient que des identifiants saisis à la main (identifiants de cartes, clés de
régions, n° du Médaillium, n° de requêtes et de Tablo-blabla, numéros de phase), jamais une table de rencontres.
La table est VÉRIFIÉE sur la ROM de référence par `archipelago/outils/audit_cartes.py` (audit A : parcours des routes du
jeu ; capacité des zones ; liste des Yo-kai demandés) et par le modèle d'`audit_logique.py` (audit B).
Bibliothèque standard seulement.
"""
import hashlib
import json
from typing import Dict, FrozenSet, List, Optional, Tuple


def ph(chapitre: int, pas: int = 10) -> int:
    """Phase « chapitre-pas » au format du jeu (condition GetPhase : chapitre x 10000 + pas)."""
    return chapitre * 10000 + pas


VERSION_TABLE = 1           # forme de la table (entre dans l'empreinte)
K = 2                       # endroits garantis par Yo-kai demandé (décision de l'humain du 2026-10-17)
PLAFOND = 6                 # Yo-kai demandés au plus par zone (décision de l'humain du 2026-10-17)
VERSION_MELANGE_ZONES = 7   # version du mélange des Yo-kai des graines à zones (client/rando_yokai.py)
CLE_SLOT_DATA = "yokai_zones"
FONCTION_CLIENT_13 = 74     # n° « client » jamais publié par le jeu : un client d'avant ce lot refuse la graine
MODES_RANDO_ZONES = ("par_rencontre_rang", "par_rencontre_total")   # seul le mélange par rencontre place un Yo-kai

# ---------------------------------------------------------------------------------------------------- cartes
# Toutes les cartes qui portent un lieu de rencontre sauvage (point de loupe, chemin d'errants ; hors salle de portail
# mystère), d'avant ET d'après la fin -> clé de région. Régions de l'APWorld (`donnees/regions.json`), plus « granval »
# (égouts de Granval, `t100` : aucune région de l'APWorld) ; les lignes d'après la fin ou hors de la partie (réseau des
# tronçons « c » de la Voie du mystère, Gera Gera Land) ne sont jamais des zones. Complétude contrôlée par l'audit A.
CARTES_REGIONS: Dict[str, str] = {
    # Hauts de Granval
    "t101g00": "les_hauts_de_granval", "t101d01": "les_hauts_de_granval", "t101d02": "les_hauts_de_granval",
    "t101d03": "les_hauts_de_granval", "t101d05": "les_hauts_de_granval",
    "t100d00": "granval",
    # Mont Sylvestre (t102d31 / t102d32 : tunnel abandonné, Tablo-blabla n° 4 et 5)
    "t102g00": "mont_sylvestre", "t102d01": "mont_sylvestre", "t102d02": "mont_sylvestre", "t102d03": "mont_sylvestre",
    "t102d31": "tunnel_abandonne", "t102d32": "tunnel_abandonne",
    # Coteau fleuri (t103d31 / t103d35 : Manoir, derrière le verrou de montre D de t103g00)
    "t103g00": "coteau_fleuri", "t103d01": "coteau_fleuri", "t103d03": "coteau_fleuri", "t103d11": "coteau_fleuri",
    "t103d31": "coteau_fleuri", "t103d35": "coteau_fleuri", "t103i33": "coteau_fleuri",
    # Centre-ville
    "t104g00": "centre_ville_de_granval", "t104d01": "centre_ville_de_granval", "t104d03": "centre_ville_de_granval",
    "t104d05": "centre_ville_de_granval", "t104d11": "centre_ville_de_granval", "t104d13": "centre_ville_de_granval",
    "t104d33": "centre_ville_de_granval",
    # Quartier des boutiques ; Clinique du Crépuscule (derrière le verrou de montre B de t105g00)
    "t105g00": "quartier_des_boutiques", "t105d01": "quartier_des_boutiques",
    "t105d41": "clinique_du_crepuscule", "t105d43": "clinique_du_crepuscule", "t105d45": "clinique_du_crepuscule",
    # La Corniche (t106d46 et suivants : donjon des portails mystères)
    "t106g00": "la_corniche", "t106d31": "la_corniche", "t106d32": "la_corniche", "t106d46": "la_corniche",
    "t106d53": "la_corniche", "t106d57": "la_corniche", "t106d58": "la_corniche", "t106d61": "la_corniche",
    "t106d63": "la_corniche",
    # Tour Excellence
    "t107g00": "tour_excellence", "t107i03": "tour_excellence",
    # San Fantastico (t121d03 / t121d11 : grottes derrière les verrous de montre C de t121g00)
    "t121g00": "san_fantastico", "t121d03": "san_fantastico", "t121d11": "san_fantastico",
    # Ourcival ; Mont de l'Ours
    "t131g00": "ourcival", "t132g00": "ourcival", "t132d01": "ourcival", "t131d01": "ourcival",
    "t131d03": "mont_de_l_ours", "t131d04": "mont_de_l_ours", "t131d05": "mont_de_l_ours",
    # Vieux Granval ; Vieil Ourcival (passé)
    "t201g00": "vieux_granval", "t202g00": "vieux_granval", "t206g00": "vieux_granval", "t201d01": "vieux_granval",
    "t201d03": "vieux_granval",
    "t231g00": "vieil_ourcival", "t232g00": "vieil_ourcival", "t231d01": "vieil_ourcival", "t231d03": "vieil_ourcival",
    "t231d04": "vieil_ourcival",
    # après la fin, hors de la partie (jamais des zones)
    "t001d05": "sortilege_express", "t001d06": "sortilege_express", "t001d07": "sortilege_express",
    "t001d43": "yokai_world", "t001d44": "yokai_world",
    "t103d41": "limbes_eternelles", "t103d42": "limbes_eternelles", "t103d43": "limbes_eternelles",
    "t103d44": "limbes_eternelles", "t103d45": "limbes_eternelles", "t103d46": "limbes_eternelles",
    "t103d47": "limbes_eternelles",
    "t103d50": "sanctuaire_divin", "t103d51": "sanctuaire_divin", "t103d52": "sanctuaire_divin",
    "t103d53": "sanctuaire_divin", "t103d54": "sanctuaire_divin",
    "t301g00": "chateau_de_sawayama", "t302g00": "chateau_de_sawayama",
    "t101d02c": "voie_du_mystere", "t101d03c": "voie_du_mystere", "t101d05c": "voie_du_mystere",
    "t102d01c": "voie_du_mystere", "t102d03c": "voie_du_mystere", "t103d03c": "voie_du_mystere",
    "t103d11c": "voie_du_mystere", "t104d03c": "voie_du_mystere", "t105d01c": "voie_du_mystere",
    "t106d11c": "voie_du_mystere", "t121d03c": "voie_du_mystere", "t131d01c": "voie_du_mystere",
    "t131d03c": "voie_du_mystere", "t132d01c": "voie_du_mystere", "t201d01c": "voie_du_mystere",
    "t121d21": "voie_du_mystere", "t121d23": "voie_du_mystere", "t121d27": "voie_du_mystere",
    "t121d27a": "voie_du_mystere", "t121d27b": "voie_du_mystere", "t121d31": "grand_route_doree",
    "t121d33": "grand_route_doree",
}

# Cartes d'une région qui ne reçoivent JAMAIS un Yo-kai demandé (elles restent dans le mélange libre), avec la raison.
# Les cartes d'après la fin et hors de la partie, et celles des régions sans zone, ne sont pas répétées ici.
EXCLUES: Dict[str, str] = {
    "t100d00": "égouts de Granval : vannes et verrou de montre C internes ; Granval n'est pas une région",
    "t101d01": "verrou de montre C interne",
    "t101d02": "jamais atteinte par le parcours (seule entrée par t101d01, derrière son verrou C)",
    "t101d05": "verrou de montre A interne (Allée sinistre)",
    "t102d31": "tunnel abandonné : partie fermée par l'Huile de Tendino (IsHaveItem, tables de la carte)",
    "t102d32": "tunnel abandonné : levier de l'Huile de Tendino (IsHaveItem)",
    "t103d03": "verrou de montre B interne",
    "t103d11": "verrou de montre C interne",
    "t103d31": "Manoir : derrière le verrou de montre D de t103g00",
    "t103d35": "Manoir : derrière le verrou de montre D de t103g00",
    "t104d11": "verrou de montre A interne",
    "t104d13": "verrou de montre S interne",
    "t104d33": "route t104i39 -> t104d33 ouverte par la requête 58 seulement (audit_logique : coffres 454..458)",
    "t105d01": "égouts du Quartier des boutiques : obstacles internes non relevés",
    "t105d41": "Clinique : derrière le verrou de montre B de t105g00",
    "t105d43": "Clinique : derrière le verrou de montre B de t105g00",
    "t105d45": "Clinique : verrou de montre B interne",
    "t106d46": "donjon des portails mystères (requête 6, globes)",
    "t106d53": "donjon des portails mystères", "t106d57": "donjon des portails mystères",
    "t106d58": "donjon des portails mystères", "t106d61": "donjon des portails mystères",
    "t106d63": "donjon des portails mystères",
    "t121d03": "grotte derrière un verrou de montre C de t121g00",
    "t121d11": "grotte derrière un verrou de montre C de t121g00",
    "t231d03": "Vieux Mont de l'Ours : ouvert seulement en 9-60 (zone bien plus tardive que le Vieil Ourcival)",
    "t231d04": "verrou de montre A interne",
}
# Cartes EXTÉRIEURES à verrou de montre interne admises : chaque lieu sauvage de la carte a au moins une position à plus
# de RAYON_HORS_VERROU unités de tout verrou de montre de la carte et de toute route située derrière l'un d'eux
# (contrôlé par l'audit A sur la ROM de référence, que le client exige) : le Yo-kai y reste trouvable du côté ouvert.
CARTES_VERROU_POSITIONS: FrozenSet[str] = frozenset({"t103g00", "t105g00", "t121g00"})
RAYON_HORS_VERROU = 400.0

# Zones admises : phase du jeu à laquelle TOUTES leurs cartes admises sont ouvertes (audit A : plus tardive des
# premières phases du parcours, jamais refermées jusqu'à la fin du chapitre 9 hors fenêtres acceptées) et chapitre de
# la règle (`regle_zone`) : le chapitre de cette phase, ou le suivant quand la phase dépasse l'ATTENTE de requêtes clés
# de son chapitre (le joueur n'atteint cette phase qu'en ayant fini ces requêtes).
ZONES: Dict[str, dict] = {
    "les_hauts_de_granval": {"phase": ph(2, 85), "chapitre": 3},      # t101d03 en 2-85, après l'attente de 2-75
    "mont_sylvestre": {"phase": ph(3, 10), "chapitre": 3},
    "la_corniche": {"phase": ph(3, 10), "chapitre": 3},
    "coteau_fleuri": {"phase": ph(4, 10), "chapitre": 4},
    "quartier_des_boutiques": {"phase": ph(4, 10), "chapitre": 4},
    "centre_ville_de_granval": {"phase": ph(4, 50), "chapitre": 4},
    "ourcival": {"phase": ph(4, 135), "chapitre": 4},
    "mont_de_l_ours": {"phase": ph(4, 160), "chapitre": 5},          # après l'attente de 4-135
    "vieil_ourcival": {"phase": ph(5, 10), "chapitre": 5},
    "vieux_granval": {"phase": ph(5, 110), "chapitre": 5},
    "tour_excellence": {"phase": ph(7, 10), "chapitre": 7},
    "san_fantastico": {"phase": ph(7, 10), "chapitre": 7},
}
# Plafond par zone : au plus PLAFOND, et assez bas pour que le placement soit TOUJOURS possible : pour chaque Yo-kai
# qui peut y être tiré, au moins K x plafond unités éligibles de la zone l'acceptent (décor de loupe compris) ; les
# (plafond - 1) autres en prennent au plus K x (plafond - 1), il en reste K pour lui (lemme de Hall). Mesuré et
# contrôlé par l'audit A sur la ROM de référence (minimum 7 à la Tour Excellence, 11 aux Hauts de Granval).
PLAFONDS: Dict[str, int] = {"tour_excellence": 3, "les_hauts_de_granval": 5}


def plafond(region: str) -> int:
    return min(PLAFOND, PLAFONDS.get(region, PLAFOND))


# Attentes de requêtes clés : chapitre -> (phase où l'histoire attend, requêtes exigées finies) [C : QUEST_CONFIG des
# quêtes de chapitre 172..179, QUEST_NECESSARY_CONDITION de type 9 ; phase_set_cNN]. Vérifié par l'audit A.
ATTENTES: Dict[int, Tuple[int, Tuple[int, ...]]] = {
    2: (ph(2, 75), (1, 2, 68)), 3: (ph(3, 95), (3, 4, 6)), 4: (ph(4, 135), (5, 29, 99)),
    5: (ph(5, 110), (10, 11, 12)), 6: (ph(6, 40), (13, 14, 15, 16, 17)), 7: (ph(7, 20), (9, 18, 26)),
    9: (ph(9, 60), (19, 20, 21)),
}
# Fenêtres où une zone peut être fermée sans dommage : le joueur est envoyé ailleurs par l'histoire et en revient sans
# objet ni requête (contrôle « reste ouverte » de l'audit A).
FENETRES_ACCEPTEES: Tuple[Tuple[int, int, str], ...] = (
    (ph(5, 10), ph(5, 99), "chapitre 5 : envoi scénarisé au Vieil Ourcival ; retour A sans objet dès 5-100 "
                           "(archipelago_v3_train_temps.md §3.3)"),
)
# Prérequis des requêtes (« quête N finie » de leur condition de QUEST_CONFIG [C, tools/romfs/quetes.py]), et requête
# 40 (Musée) : la Silhouette de héros ne vient que de la requête 46 (prudence : exigée même quand l'objet est mélangé).
PREALABLES: Dict[int, Tuple[int, ...]] = {
    33: (9,), 39: (90,), 40: (46,), 45: (44,), 46: (45, 49), 48: (47,), 49: (48, 65), 51: (50,), 52: (51,),
    54: (53,), 55: (54,), 57: (56,), 58: (57,), 60: (59,), 61: (60,), 65: (64,), 67: (66,), 69: (71,), 74: (73,),
    77: (57,), 96: (119, 125), 101: (33, 34, 35, 36), 103: (85,), 105: (104,), 106: (105,), 111: (73,),
    118: (117,), 119: (118,), 120: (71,), 122: (121,), 123: (122,), 124: (121,),
}

# ---------------------------------------------------------------------------------------------- Yo-kai demandés
# Yo-kai demandés qui ont un lieu sauvage dans le mélange (W' de la version 6) et que le mélange déplace : n° du
# Médaillium -> requêtes / services qui l'exigent (n°, « posseder » | « vaincre », nombre), Tablo-blabla dont il est la
# réponse (n°), zones d'origine (régions de ses points de loupe et chemins d'errants d'origine, hors salles de portail :
# la zone tirée est toujours une autre).
# Source : `rencontres.Analyse.exigences()` sur la ROM européenne (contrôle : audit A). Non déplacés (politique de la
# version 6) : Faux Kappa (158 : condition InPartyMember d'un déclencheur de quête, requête 109 de transfert), Ivanupieds
# (177) et Triptic-tac (70) (aucun lieu sauvage).
# Tranchés d'après les données (les 7 « à revoir » de la conception, et Vampiloc) : leurs autres citations sont des
# affichages ou un PNJ, jamais un lieu sauvage : Tortico (204) et Supernoël (193) : déclencheur de type 11 = parler au
# PNJ de cette base (npc_set), sans lien avec leurs rencontres ; Espi (75) : repère d'objectif (QUEST_PURPOSE_POS, la
# flèche de la carte) : seul le guidage reste au lieu d'origine ; Angélik (155) : icône d'un menu
# (Menu_MedalIconImgSetupByCRC) ; Tontonerre (196) : modèle d'une scène (AssignCharacterBaseLQ4) ; Jacquasseur (313),
# Feulion (24) et Vampiloc (222) : comparaisons (op 0x0082) qui choisissent un dialogue de train, de coffre ou un effet
# d'apparition. Jacquasseur est aussi un don de quête (AddPartyEx) : source en plus, sans effet sur le placement.
def _d(medaille, quetes=(), tablos=(), origines=()):
    return {"medaille": medaille, "quetes": tuple(quetes), "tablos": tuple(tablos), "origines": tuple(origines)}


_HG, _MS, _CF, _CV = "les_hauts_de_granval", "mont_sylvestre", "coteau_fleuri", "centre_ville_de_granval"
_QB, _LC, _TE, _OU = "quartier_des_boutiques", "la_corniche", "tour_excellence", "ourcival"
_MO, _SF, _VG, _VO = "mont_de_l_ours", "san_fantastico", "vieux_granval", "vieil_ourcival"
_CL, _GR = "clinique_du_crepuscule", "granval"
DEMANDES: List[dict] = [
    _d(14, [(44, "posseder", 1)], [9], []),                                 # Sumochi (salles de portail seulement)
    _d(16, [(163, "vaincre", 4)], [], [_VG]),                               # Sale de bain
    _d(24, [], [2], [_TE]),                                                 # Feulion
    _d(27, [(69, "posseder", 1), (164, "vaincre", 3)], [], [_SF]),          # Bonneto
    _d(34, [(170, "vaincre", 1)], [], [_OU]),                               # Kapunki
    _d(41, [(163, "vaincre", 5)], [], [_VG]),                               # Gastong
    _d(42, [(162, "vaincre", 4)], [], [_CF]),                               # Morvobec
    _d(43, [(165, "vaincre", 5)], [], [_GR]),                               # Matchou
    _d(47, [], [17], [_CV, _LC, _VG]),                                      # Chaipô
    _d(52, [(166, "vaincre", 5)], [], [_CF]),                               # Violette
    _d(56, [], [13], [_CV, _LC]),                                           # Cupistol
    _d(58, [(168, "vaincre", 5)], [], [_LC]),                               # Nonjuan
    _d(61, [(163, "vaincre", 4)], [], [_VO]),                               # Brumette
    _d(71, [], [24], [_LC]),                                                # Nuiroir
    _d(72, [], [11], [_CV, _LC, _MO, _OU]),                                 # Hiblusion
    _d(75, [(167, "vaincre", 4)], [], [_CL]),                               # Espi
    _d(76, [(167, "vaincre", 4)], [], [_LC, _SF]),                          # Étassivilia
    _d(85, [(162, "vaincre", 4)], [], [_CV]),                               # Darabajoie
    _d(102, [(99, "vaincre", 3)], [], [_MO, _OU, _VO]),                     # Pachycoul
    _d(124, [(64, "posseder", 1)], [], [_LC, _HG]),                         # Squarlett
    _d(127, [], [14], [_CF, _LC, _HG, _MS, _OU, _QB, _SF, _VO, _VG]),       # Cigalopin
    _d(130, [(162, "vaincre", 4)], [], [_CF]),                              # Chihuaglagla
    _d(149, [(166, "vaincre", 3)], [7], [_MS]),                             # Sabruine
    _d(150, [(45, "posseder", 1)], [], [_LC]),                              # Vito
    _d(151, [(66, "posseder", 1)], [], [_CV]),                              # Pitou
    _d(155, [(166, "vaincre", 4)], [], [_HG]),                              # Angélik
    _d(163, [(161, "vaincre", 3)], [20], [_QB, _SF]),                       # Noripop
    _d(165, [(161, "vaincre", 3)], [21], [_QB, _SF]),                       # Wakapoeira
    _d(166, [], [22], [_QB, _SF]),                                          # Salsalga
    _d(167, [], [1], [_CV]),                                                # Granpapéti
    _d(181, [(71, "posseder", 1)], [], [_MS, _VG]),                         # Papiltation
    _d(188, [(98, "posseder", 1)], [6], [_OU]),                             # Sabrille
    _d(192, [(167, "vaincre", 4)], [], [_TE]),                              # Ratatam
    _d(193, [(167, "vaincre", 4)], [19], [_MO]),                            # Supernoël
    _d(194, [(168, "vaincre", 5)], [], [_LC]),                              # Dédé
    _d(195, [(169, "vaincre", 3)], [], [_QB]),                              # Dédestin
    _d(196, [(169, "vaincre", 3)], [], [_MS]),                              # Tontonerre
    _d(204, [(4, "posseder", 1)], [], [_CF, _LC]),                          # Tortico
    _d(213, [(170, "vaincre", 1)], [], [_TE]),                              # Grattoptère
    _d(222, [(170, "vaincre", 1)], [], [_GR]),                              # Vampiloc
    _d(231, [(168, "vaincre", 3)], [], [_CL, _LC]),                         # Snobéa
    _d(244, [(162, "vaincre", 4)], [], [_CV, _GR, _HG, _SF, _VG]),          # Malmidal
    _d(248, [(161, "vaincre", 3)], [], [_CF, _GR, _LC, _HG, _MS, _QB, _VG]),    # Fryzeur
    _d(251, [], [15], [_CF, _LC, _HG, _QB]),                                # Chiperpiou
    _d(262, [(163, "vaincre", 5)], [], [_VO]),                              # Poilux
    _d(267, [(166, "vaincre", 5)], [], [_TE]),                              # Umilie
    _d(269, [(164, "vaincre", 3)], [], [_SF]),                              # Adolfo Jeton
    _d(271, [(169, "vaincre", 3)], [], [_HG]),                              # Méphito
    _d(276, [(169, "vaincre", 3)], [], [_CV]),                              # Flopito
    _d(288, [(161, "vaincre", 3)], [], [_CF, _LC, _HG, _MS, _OU, _QB]),     # Maudieuse
    _d(292, [(165, "vaincre", 4)], [], [_GR]),                              # Urnaconda
    _d(293, [(165, "vaincre", 5)], [], [_GR]),                              # Murhaine
    _d(295, [(170, "vaincre", 1)], [], [_SF]),                              # Vexturgeon
    _d(296, [(9, "posseder", 1), (164, "vaincre", 4)], [], [_LC, _SF]),     # Yvantouse
    _d(309, [(164, "vaincre", 3)], [18], [_SF]),                            # Croquin
    _d(313, [(165, "vaincre", 4)], [], [_MS, _TE]),                         # Jacquasseur
    _d(315, [], [5], [_CV]),                                                # Draconfus
]
DEMANDES_PAR_MEDAILLE: Dict[int, dict] = {d["medaille"]: d for d in DEMANDES}
# Objets-clés donnés par une requête qui demande un Yo-kai à zone, sans « quete » dans `logique.EMPLACEMENTS` : la
# Canne à pêche (fin de la requête 99, après les trois Pachycoul) [C, audit_logique MODELE].
DONS_DE_REQUETE: Dict[str, int] = {"canne_a_peche": 99}


def empreinte() -> str:
    """Condensat de la table (cartes admises par zone, zones, K, PLAFOND, Yo-kai demandés) : écrit dans slot_data,
    comparé par le client à SA copie (paquet de l'APWorld) : une graine d'une autre table est refusée."""
    canon = {"v": VERSION_TABLE, "k": K, "plafond": PLAFOND, "plafonds": PLAFONDS, "rayon": RAYON_HORS_VERROU,
             "zones": {r: [z["phase"], z["chapitre"], sorted(cartes_admises(r))] for r, z in sorted(ZONES.items())},
             "verrou": sorted(CARTES_VERROU_POSITIONS),
             "demandes": [[d["medaille"], [list(q) for q in d["quetes"]], list(d["tablos"])] for d in DEMANDES]}
    return hashlib.sha1(json.dumps(canon, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:16]


def cartes_admises(region: str) -> FrozenSet[str]:
    """Cartes où un Yo-kai demandé de cette zone peut être placé (vide hors des zones admises)."""
    if region not in ZONES:
        return frozenset()
    return frozenset(c for c, r in CARTES_REGIONS.items() if r == region and c not in EXCLUES)


def cartes_par_zone() -> Dict[str, List[str]]:
    return {r: sorted(cartes_admises(r)) for r in sorted(ZONES)}


def quetes_closes(quetes) -> FrozenSet[int]:
    """Requêtes et toutes celles qu'elles exigent finies (PREALABLES), transitivement."""
    out, pile = set(), list(quetes)
    while pile:
        q = pile.pop()
        if q in out:
            continue
        out.add(q)
        pile.extend(PREALABLES.get(q, ()))
    return frozenset(out)


def especes_de_quete(n: int) -> Tuple[int, ...]:
    """N° du Médaillium des Yo-kai demandés par la requête n OU par l'une de ses requêtes préalables."""
    qs = quetes_closes((n,))
    return tuple(sorted(d["medaille"] for d in DEMANDES if any(q[0] in qs for q in d["quetes"])))


def especes_de_tablo(n: int) -> Tuple[int, ...]:
    return tuple(sorted(d["medaille"] for d in DEMANDES if n in d["tablos"]))


def contraintes(medaille: int) -> Tuple[int, int]:
    """(phase maximale, chapitre maximal de la règle) d'une zone pour ce Yo-kai : la plus stricte des attentes de
    requêtes clés qui le demandent (directement ou par un préalable) ; sans attente : pas de limite."""
    d = DEMANDES_PAR_MEDAILLE[medaille]
    phase, chap = ph(99, 0), 99
    for ch, (p, reqs) in sorted(ATTENTES.items()):
        if medaille in {m for n in reqs for m in especes_de_quete(n)}:
            phase, chap = min(phase, p), min(chap, ch)
    del d
    return phase, chap


def candidats(medaille: int) -> List[str]:
    """Zones permises pour ce Yo-kai (avant le plafond) : jamais une zone d'origine ; phase et chapitre compatibles
    avec les requêtes clés qui l'attendent."""
    d = DEMANDES_PAR_MEDAILLE[medaille]
    phase, chap = contraintes(medaille)
    return [r for r, z in sorted(ZONES.items())
            if r not in d["origines"] and z["phase"] <= phase and z["chapitre"] <= chap]


def tirer(rng, valide=None) -> Dict[int, str]:
    """Tirage de la génération (`rng` = `self.random` d'Archipelago, graines à zones seulement) : n° -> zone. Les Yo-kai
    les plus contraints d'abord (moins de candidats, puis n° croissant) ; plafond PLAFOND par zone. `valide(zones)` :
    contrôle de la logique (évènements de chapitre atteignables) ; un Yo-kai dont le choix le rend faux est retiré au
    hasard parmi les autres candidats (le contrôle se refait à chaque choix). ValueError si aucun choix ne convient.
    Plafond par zone : `plafond`."""
    ordre = sorted(DEMANDES, key=lambda d: (len(candidats(d["medaille"])), d["medaille"]))
    zones: Dict[int, str] = {}
    charge: Dict[str, int] = {}
    for d in ordre:
        m = d["medaille"]
        cands = [r for r in candidats(m) if charge.get(r, 0) < plafond(r)]
        rng.shuffle(cands)
        for r in cands:
            zones[m] = r
            if valide is None or valide(zones):
                charge[r] = charge.get(r, 0) + 1
                break
            del zones[m]
        else:
            raise ValueError(f"zones des Yo-kai demandés : aucune zone possible pour le n° {m}")
    return dict(sorted(zones.items()))


def valider_zones(zones) -> Dict[int, str]:
    """Zones lues dans slot_data (ou passées au plan) : {n°: clé de zone}, n° demandés et zones admises seulement."""
    out = {}
    for m, r in (zones.items() if isinstance(zones, dict) else zones):
        m = int(m)
        if m not in DEMANDES_PAR_MEDAILLE or r not in ZONES:
            raise ValueError(f"zone inconnue pour le n° {m} : {r!r}")
        out[m] = r
    return dict(sorted(out.items()))


def slot_data(zones: Dict[int, str]) -> dict:
    return {"v": empreinte(), "k": K, "zones": [[m, r] for m, r in sorted(zones.items())]}


def lire_slot_data(sd) -> Optional[Dict[int, str]]:
    """Entrée `yokai_zones` de slot_data -> {n°: zone} ; None si absente. ValueError si illisible ou d'une autre table."""
    if not sd:
        return None
    if not isinstance(sd, dict) or sd.get("v") != empreinte() or sd.get("k") != K:
        raise ValueError("zones des Yo-kai demandés d'une autre version de la table (mettre le mod à jour)")
    return valider_zones([(e[0], e[1]) for e in sd.get("zones") or ()])
