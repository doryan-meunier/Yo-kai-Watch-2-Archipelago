"""Cartes du tracker de checks (sous-onglet « Carte » de l'onglet « Checks » du lanceur), générées CHEZ LE JOUEUR
depuis SA ROM : minicartes de l'écran tactile en PNG et position de chaque location de l'APWorld sur ces images.

    python -m installation.cartes --rom <ROM déchiffrée | dossier du RomFS> --sortie <dossier>   (depuis archipelago/)

Écrit `<dossier>/cartes/<carte>.png` et `<dossier>/cartes/cartes_local.json` (dossier de données du client,
`%APPDATA%/ykw2-ap/`). Images et coordonnées sont des données du jeu : elles ne sont JAMAIS versionnées ni distribuées
(règle 6 de `CLAUDE.md`) ; seule la table des RÉFÉRENCES (identifiants : fichier de déclencheurs et n°, n° de quête)
est dans ce fichier. Analyse et preuves : `docs/systemes/archipelago_tracker_cartes.md` (§1, §2) ; outil de preuve
`tools/romfs/tracker_cartes.py`.

Chaîne (§2 de l'analyse) :
- image : `yw2_a.fa:data/map/<carte>/<carte>.xi` (IMGC, ETC1 surtout), rognée à (Vw, Vh) ;
- transformation : `px = (x − x0)·Vw/(x1 − x0)`, `py = (z − z0)·Vh/(z1 − z0)`, (x0, z0, x1, z1) = `MMModelPos`,
  (Vw, Vh) = `MMViewSize` sinon taille de l'image (`data/map/<carte>/mapenv.pck:<carte>_mapenv.bin`) [C] ;
- positions : coffre (index TBox → `OP_TBOX_POINT` → `SHAPE_DATA_ITEM`) et Tablo (flag → `OP_TERRITORY_POINT`) [C,
  précision « point »] ; requête / Vélo (1re phase à objectif de `quest_config`), objet-clé et boss (déclencheur de
  la table `REFERENCES_*` → `DATA_ITEM` → zone, PNJ ou carte) [S, précision « approx »] ; identifiant qui n'est pas un
  lieu : carte seulement (précision « carte ») ; chapitres : sans lieu.
Bibliothèque standard seulement (lecteurs de `level5.py` et `rencontres.py`).
"""
from __future__ import annotations

import argparse
import base64
import datetime
import hashlib
import json
import os
import re
import struct
import sys
import threading
import zlib
from collections import defaultdict
from pathlib import Path
from typing import Callable

ARCHIPELAGO = Path(__file__).resolve().parents[1]
if str(ARCHIPELAGO) not in sys.path:
    sys.path.insert(0, str(ARCHIPELAGO))

from installation import level5 as L5  # noqa: E402
from installation import objets_voyage as OV  # noqa: E402
from installation.rencontres import CfgBin, decoder_condition, resumer_condition  # noqa: E402

FORMAT = 6                                  # 2 : icônes du Vélo, du Rang de montre et des chapitres ; 3 : suivi de
#                                             la carte du jeu (rectangle monde de chaque carte, cartes parentes) ;
#                                             4 : image aussi pour les cartes à Yo-kai sauvages (Yo-kai épinglé) ;
#                                             5 : boutiques placées (vendeur, entrées du bâtiment : `boutiques`)
#                                             6 : conditions d'apparition de chaque vendeur (`app` : moment,
#                                                 condition décodée, tirage d'un étal ambulant ; §12)
FORMATS_LUS = (1, 2, 3, 4, 5, 6)            # un fichier plus ancien reste affiché le temps de sa régénération
DOSSIER = "cartes"                         # sous-dossier du dossier de données du client
NOM_FICHIER = "cartes_local.json"
PRECISIONS = ("point", "approx", "carte")   # [C] au point ; [S] au point (à vérifier en jeu, T5) ; carte seulement
DOSSIER_ICONES = "icones"                   # sous-dossier de DOSSIER : icônes 32×32 des objets de l'APWorld
# chemins assemblés : le paquet ne recopie aucune chaîne de code.bin (contrôle de fabriquer_paquet.py)
ATLAS_ICONES = "data/menu/item_icon/" + "item_icon.xi"
ITEM_CONFIG = "data/res/item/" + "item_config_0.04b.cfg.bin"
FLAG_CONFIG = "data/res/sys/" + "flag_config_0.01.cfg.bin"
MAP_CONFIG = "data/res/map/" + "map_config.cfg.bin"   # MAP_INFO : +0 hachage, +3 zone (101 = t101…), +9 nom, +11 groupe
CASE_ICONE = 32                             # cases 32×32 de l'atlas, (colonne v12, ligne v13) de l'entrée ITEM_*
FAMILLES_ICONES = ("objet_cle", "rang", "capacite")    # objets montrés dans la colonne du sous-onglet « Carte »
# Objets des Yo-kai d'évènement (option `objets_evenement` de l'APWorld) : section à part sous les précédents, montrée
# seulement pour une graine qui les contient. Leurs icônes s'ajoutent au même dossier (clés et hachages de l'APWorld) ;
# la structure du fichier ne change pas (FORMAT inchangé) : la signature des références (icônes comprises) change,
# un fichier fait sans elles est donc régénéré seul (« references », `raison_generation`).
FAMILLE_EVENEMENT = "evenement"
# V3 : objets à verrou étendu (Yo-kai Watch, Documents perdus, Cartes d'Ultramax) : dans la colonne seulement pour une
# graine qui a leur verrou (`ModeleChecks.objets_v3`) ; leurs icônes s'ajoutent au même dossier, comme ci-dessus.
FAMILLE_CLE_V3 = "objet_cle_v3"
FAMILLE_CLE_AJ = "objet_cle_aj"             # V3, lot 3 : objets d'accès de l'après-jeu (objets réels du jeu : icône de la ROM)
# V3, lot 21 : pièces spéciales du Crank-a-kai (option `pieces_speciales` ; la Pile ou passe est déjà un objet-clé) :
# rubrique « Pièces spéciales » de la colonne d'objets, une icône par pièce avec le nombre reçu. Objets réels du jeu :
# icône de la ROM du joueur, extraite comme les autres (aucune image dans le dépôt ni dans le paquet).
FAMILLE_PIECE = "piece"
FAMILLES_AVEC_ICONE = FAMILLES_ICONES + (FAMILLE_EVENEMENT, FAMILLE_CLE_V3, FAMILLE_CLE_AJ, FAMILLE_PIECE)
# Cases de la colonne sans hachage d'objet propre dans l'APWorld : icône d'un objet du jeu qui les représente
# (identifiants seulement, règle 6 ; l'image est extraite chez le joueur comme les autres). Vélo : « Vélo du vent »
# (iky0011, 1er modèle de la boutique de `qs0009`) ; Rang de montre : « Yo-kai Watch » (iky0001, lettre du rang en
# surimpression dans le lanceur) ; chapitres : « Cahier de vacances » (iky0013, compteur N/10 en surimpression).
CLE_CHAPITRES = "__chapitres__"            # case des chapitres (pas un objet de l'APWorld)
ICONES_SANS_HACHAGE: dict[str, int] = {
    "velo": 0x5670B1D6,
    "rang_de_montre": 0x4F6B8097,
    CLE_CHAPITRES: 0xB87ED0FA,
    # V3, lot 6 : objets à verrou étendu sans objet du jeu donné (don « aucun », donc sans hachage dans objets.json) :
    # icône de l'objet du jeu du même nom (Pass sortilège, 4 clés de la Voie du mystère)
    "pass_sortilege": 0x0B6C2930, "cle_terrifiante": 0x04815AB1, "cle_sanglier": 0x77CA9EEB,
    "cle_cerf": 0xE775837A, "cle_papillon": 0x73866A27,
    # (ap/lanceur-trousseau : les 5 clés du donjon des portails n'ont plus de case à elles : `ICONES_TROUSSEAU`)
}
# V3 : objets de voyage SANS objet du jeu d'origine (Abonnement de train, Voyage dans le temps, Miroirs) : icône
# DESSINÉE en code (`installation/objets_voyage.py`, aucune image du jeu), la même que celle de l'objet que
# l'installation ajoute au jeu ; clé -> hachage de cet objet ajouté (crc32("ap_" + clé), absent de la ROM d'origine).
# Le hachage entre dans la signature des références : un fichier de cartes fait sans ces icônes est régénéré seul.
# ap/objets-mirapo-trousseau : « Miroirs progressifs » a l'icône du Mirapo de poche (objet du jeu ajouté par
# l'installation, crc32("ap_mirapo_de_poche") ; `objets_voyage.ICONES_LANCEUR`).
ICONES_DESSINEES: dict[str, int] = {cle: zlib.crc32(("ap_" + objet).encode("ascii")) & 0xFFFFFFFF
                                    for cle, (objet, _dessin) in OV.ICONES_LANCEUR.items()}
# ap/lanceur-trousseau : les 5 clés du donjon des portails (`objets_voyage.CLES_AP_DONJON`, une par porte, dans
# n'importe quel ordre) sont montrées par UNE case « Trousseau du donjon » dont l'image suit le NOMBRE n de clés reçues,
# comme l'objet que le jeu met dans le sac : icônes « <CLE_CASE_TROUSSEAU>_n<n> » = dessin du trousseau à n clés
# (`objets_voyage.dessin_trousseau`, aucune image du jeu) ; hachage = celui de la version « n premières clés » de
# l'objet ajouté au jeu (crc32("ap_trousseau_donjon_<masque>")), qui a ce même dessin. Présentes seulement si
# l'APWorld a ces clés.
CLE_CASE_TROUSSEAU = OV.GROUPE_TROUSSEAU
ICONES_TROUSSEAU: dict[str, int] = {
    "%s_n%d" % (CLE_CASE_TROUSSEAU, n): zlib.crc32(("ap_" + OV.trousseau((1 << n) - 1)[0]).encode("ascii")) & 0xFFFFFFFF
    for n in range(1, 6)}
DESSINS_TROUSSEAU = {"%s_n%d" % (CLE_CASE_TROUSSEAU, n): OV.trousseau((1 << n) - 1)[5] for n in range(1, 6)}
# ap/icones-images : l'Abonnement de train et les trousseaux sont devenus les images dessinées par l'humain, à hachages
# inchangés ; ce numéro entre dans la signature des références quand l'une de ces icônes est demandée, pour qu'un
# fichier de cartes fait avec les anciens dessins soit régénéré seul (icônes PNG du lanceur refaites).
# ap/icones-voyage-miroirs : Voyage dans le temps, Miroirs et Mirapo de poche (Miroirs progressifs) aussi : version 3,
# toutes les icônes dessinées en sont.
VERSION_IMAGES = 3
CLES_IMAGES_HUMAIN = frozenset(set(ICONES_DESSINEES) | set(ICONES_TROUSSEAU))


def cle_icone_trousseau(n: int) -> str:
    """Clé d'icône de la case du trousseau pour n clés reçues (0 : l'image à une clé, grisée par le lanceur)."""
    return "%s_n%d" % (CLE_CASE_TROUSSEAU, min(max(int(n), 1), 5))

# ------------------------------------------------------------------------------------------------ références (T2)
# Table saisie à la main (identifiants seulement, règle 6) : fichier de déclencheurs (`cNN_trigger` de
# `data/res/phs/cNN/`, ou `<carte>_quest_trigger` de l'archive de la carte) et n° de `RunCmd_*N` (= champ n du
# `DATA_ITEM`), ou n° de quête (« quete », position = 1re phase à objectif de `quest_config`).
# Objets-clés : commentaires d'`EMPLACEMENTS` (logique.py) ; boss : déclencheur qui lance le combat (sortie de
# `tools/romfs/combats.py` résolue par `tools/romfs/tracker_cartes.py`, 2026-09-28), ou quête quand le combat n'a pas
# de lanceur trouvé. Clés : `objet` des emplacements / `cle` des boss de logique.py.
REFERENCES_OBJETS_CLES: dict[str, tuple[str, int]] = {
    "filet_a_insectes": ("c01_trigger", 16),
    "pile_ou_passe": ("c02_trigger", 11),
    "cles_de_l_ecole": ("c03_trigger", 3),
    "herbe_ancestrale": ("c03_trigger", 20),            # type 39, identifiant introuvable : sans position [?]
    "super_tournevis": ("c03_trigger", 26),
    "indications_de_maman": ("c04_trigger", 10),
    "modele_zero": ("c06_trigger", 1),                   # type 71 : sans position [?]
    "cle_de_derriere": ("t103d31_quest_trigger", 5),     # type 73 : carte seulement
    "cle_magnetique_or": ("t100d00_quest_trigger", 6),   # type 13 : carte seulement
    "cle_salle_du_tresor": ("t102d31_quest_trigger", 4),
    "poignee_etrange": ("t105d45_quest_trigger", 5),     # type 78 : carte seulement
    "canne_a_peche": ("quete", 99),
    # objets-clés de quête (archipelago_objets_cles_v11.md §16) : PNJ (type 13, dialogue) : carte seulement ; point de
    # la loupe (type 39) : au point ; fin de combat (type 78) : carte seulement
    "cle_magnetique_rouge": ("t100d00_trigger", 22),
    "poster_de_film": ("t201g00_quest_trigger", 107),
    "bobine_de_film": ("t201g00_quest_trigger", 108),
    "bouteille_de_y_cola": ("t201g00_quest_trigger", 109),
    "affiche_de_restaurant": ("t104g00_quest_trigger", 1),
    "louloutre": ("t105i35_quest_trigger", 4),
    "pot_canard": ("t102d03_quest_trigger", 1),
    "figurine_de_photortue": ("t106i02_quest_trigger", 12),
    "robe_de_star": ("t104g00_quest_trigger", 22),
}
REFERENCES_BOSS: dict[str, tuple[str, int]] = {
    "grolos": ("c03_trigger", 39),
    "meganyan": ("c04_trigger", 57),
    "laure": ("c06_trigger", 16),
    "marge": ("c06_trigger", 16),
    "tourboeillon": ("c07_trigger", 9),
    "injustin": ("c09_trigger", 10),                     # type 73 : carte seulement
    "cyrustre": ("c10_trigger", 33),
    "fielippine": ("c10_trigger", 36),
    "maudicko": ("c10_trigger", 39),
    "ronean": ("c10_trigger", 43),
    "lady_perpetua": ("c10_trigger", 60),
    "lady_demona": ("c10_trigger", 65),
    "barbefrousse": ("quete", 16),
    "didgeai": ("t103d36_quest_trigger", 2),
    "sabroclair": ("t106d33_quest_trigger", 5),
    "ombraptor": ("t104d33_quest_trigger", 8),
    "inamygal": ("t101i51_quest_trigger", 5),
    "volteface": ("t102d31_quest_trigger", 5),
    "misterre": ("t102i21_quest_trigger", 2),
    "firmain": ("t105d48_quest_trigger", 2),
    "demophage": ("quete", 21),
    "crocho": ("t103i38_quest_trigger", 1),
    "tromploeil": ("quete", 8),
    # boss du mélange ajoutés (logique.BOSS_MELANGE, archipelago_boss.md §11) : déclencheur qui lance le combat
    "fumella": ("t201d11_quest_trigger", 6),            # type 11 (point), requête 12 en phase 9
    "draconfus": ("t107i01_quest_trigger", 3),          # type 11 (point), requête 15 en phase 4
    "faux_kappa": ("t131g00_quest_trigger", 22),        # type 11 (point), requête 17 en phase 2
    "sabrille": ("c09_trigger", 2),                     # type 11 (point), étape 9-20
    "anguigne": ("c10_trigger", 2),                     # type 21 (zone), étape 10-20
    # Taprice : l'ENTRÉE du Tunnel sans fin (point de recherche de t131g00, type 39), pas la salle du combat (t131d33,
    # n° 5) : c'est là que le joueur doit aller, cinq fois, avant le combat
    "taprice": ("t131g00_trigger", 29),
}

# V3 (lot « carte des checks », 2026-10-19) : références des checks ajoutés en V3. Formes de plus que celles de la V2
# (toutes résolues dans la ROM du joueur par `resoudre_references`, identifiants seulement ici) :
#   (fichier, n, carte)            déclencheur de phase dont le point existe dans plusieurs cartes : carte où il sert ;
#   ("quete_phase", n, phase, carte) objectif de la phase `phase` de la requête n (`QUEST_PURPOSE_POS`) situé dans
#                                  `carte` (la carte du don), à défaut cette carte seulement ;
#   ("warp", flag)                 miroir dont le flag bit global est `flag` (`WARP_INFO` de `warp_config`) ;
#   ("pnj", carte, identifiant)    PNJ de la carte (`NPC_PRESET` -> `.npcbin`) ;
#   ("entree", source, cible)      porte de `source` qui mène à `cible` (`map_route`, zone du `_layout`).
# Déclencheurs de type 13 (action d'un dialogue), 52 (acceptation) et 73 (entrée dans la carte) : carte seulement.
# Emplacements d'objets-clés de la V3 (`logique.EMPLACEMENTS_V3`, dons relus dans les scripts : commentaires de la table
# et archipelago_v3_objets_cles_2.md §5, archipelago_v3_lettre_bille_deathlink.md §A) :
REFERENCES_OBJETS_CLES_V3: dict[str, tuple] = {
    # c01 n° 35 (garçon) / 36 (fille) : point de recherche 0x30B23B77, présent dans t101g00 ET t101i35 ; la chaîne qui
    # y mène est dans t101i35 (n° 30 : porte sur t101g00, n° 31 : entrée dans t101i35, n° 32 à 34 : même pièce)
    "yokai_watch": ("c01_trigger", 35, "t101i35"),
    "documents_perdus": ("quete_phase", 9, 7, "t103g00"),         # t103g00_quest n° 6 (type 13) en phase 7
    "cartes_ultramax": ("t131g00_quest_trigger", 7),              # point de recherche (type 39)
    "lettre_de_komasan": ("t201d01_quest_trigger", 1),            # point de recherche (type 39)
    "bille_mysterieuse": ("t201g00_quest_trigger", 7),            # PNJ (type 11)
    "capsules_de_lait": ("c06_trigger", 4),                       # point de recherche de t231g00 (type 39)
    "grelot_felin": ("t202g00_quest_trigger", 4),                 # PNJ (type 11), fin de la requête 11
    "montre_de_luxe": ("t201i03_quest_trigger", 2),               # PNJ (type 11), fin de la requête 10
    "miroirs": ("warp", 1777),                                    # marqueur : flag 1777, miroir de t131i01
    "ceinture_de_force": ("quete_phase", 44, 2, "t105i33"),       # t105i33_quest n° 1 (type 13) en phase 2
    "robot_retro_neuf": ("quete_phase", 48, 3, "t201i10"),        # t201i10_quest n° 3 (type 13) en phase 3
    "robot_mecanique_use": ("t131i01_quest_trigger", 6),          # point de recherche (type 39)
    "serviette_douce": ("quete_phase", 80, 4, "t104i30"),         # t104i30_quest n° 3 (type 13) en phase 4
    "dance_revolution": ("t106g00_quest_trigger", 23),            # type 73 (phase 9, sans objectif) : carte seulement
    "carte_a_tamponner": ("quete_phase", 90, 1, "t100s17"),       # t100s17_quest n° 2 (type 52, acceptation)
    "voyage_dans_le_temps": ("c05_trigger", 8),                   # « Passage du temps » : PNJ de t232g00 (type 11)
}
# Emplacements d'après-jeu (`apres_jeu.EMPLACEMENTS`) :
REFERENCES_OBJETS_CLES_AJ: dict[str, tuple] = {
    "cle_de_cabane": ("c11_trigger", 6),                          # zone de t106i05 (type 21), scène ev11_0300
    "cle_du_yokai_world": ("quete", 73),                          # t102g00_quest n° 26 (type 52) : donneur de la 73
    "pass_entrain_exp": ("t001t03_quest_trigger", 35),            # type 73 (phase 11) : carte seulement
    # t101i02_quest n° 12 (type 73, phase 2) : carte seulement ; même don dans t101i04 (maison de l'autre personnage)
    "pass_sortilege": ("t101i02_quest_trigger", 12),
}
# Boss d'après-jeu (`apres_jeu.BOSS` et `BOSS_MEDAILLE`, clés de PLACE) : déclencheur dont le script lance le combat
# (commande 0x352C, CRC-32 du nom de la rencontre = hachage de la place, relu dans les scripts) :
REFERENCES_BOSS_AJ: dict[str, tuple] = {
    # chaîne des Limbes (c11_trigger) : zones de type 21, Potofeu : point de t103d48 (type 39)
    "hydreux": ("c11_trigger", 9), "porcinator": ("c11_trigger", 12), "styx_vi": ("c11_trigger", 14),
    "nebulor": ("c11_trigger", 16), "pr_letripe": ("c11_trigger", 18), "hagacuree": ("c11_trigger", 20),
    "rancornet": ("c11_trigger", 22), "potofeu": ("c11_trigger", 24), "barbebluff": ("c11_trigger", 29),
    "mariotte_et_maribass": ("c11_trigger", 32), "lady_maggie": ("c11_trigger", 34), "filomene": ("c11_trigger", 36),
    "mckraken": ("t001d42_trigger", 4),                           # point de t001d42 (type 39), edy_x171000_01
    "thenuki": ("t102i01_quest_trigger", 2),                      # PNJ (type 11), btl_qs0120_01
    "dr_jobard": ("quete_phase", 77, 3, "t105d41"),               # t105d41_quest n° 14 (type 13) en phase 3
    "extrabuki": ("t001d08_quest_trigger", 6),                    # type 73 (phase 5, sans objectif) : carte
    "infiniris": ("t202g00_quest_trigger", 17),                   # type 73 (phase 9, sans objectif) : carte
    "chomino": ("t001t01_quest_trigger", 1),                      # type 73 : carte
    "ambronzio": ("t103d56_quest_trigger", 1),                    # type 73 : carte (place « laure_marge_ambronzio »)
    # Voie du mystère (ap/boss-voie-mystere) : zone de combat de la fin de chaque ligne (type 21, zone 0xB682F7CA ;
    # t121d29 : n° 1 / 2 / 3 selon la ligne d'arrivée, RunCmd_Map1 / 2 / 3 ; t121d35 : n° 3, RunCmd_Map3)
    "blingos": ("t121d29_trigger", 1), "cycloptique": ("t121d29_trigger", 2), "maximain": ("t121d29_trigger", 3),
    "bogos": ("t121d35_trigger", 3),
}
# Invités de l'Auberge des voyageurs (archipelago_invites.md §2, §18) : Pandanoko a la Suite (t103i69, PNJ
# `npc_sasurai`) ; les invités à invitation prennent la première chambre libre (101 à 109 = t103i60 à t103i68, ordre de
# la partie) : porte de la chambre 101 sur t103g00, précision « approx ». Les 28 qui QUITTENT l'Auberge avec
# `pieces_speciales` (`pieces.QUITTENT_AUBERGE`, même identifiant devenu un check « Ami » de pièce) restent sans
# position : leur lieu dépend des options de la graine, que les cartes locales ignorent.
NPC_SASURAI = 0x95C2369D                    # crc32("npc_sasurai")
REFERENCE_INVITE_SUITE: tuple = ("pnj", "t103i69", NPC_SASURAI)
REFERENCE_INVITE_CHAMBRE: tuple = ("entree", "t103g00", "t103i60")

# « Montée de rang : D » (RANG_D_CHECK, flag 201) : scène lancée par c03_trigger n° 33 (commentaire de logique.py) ;
# DATA_ITEM de type 73 (pas un lieu) : carte seulement (t103i21 sur la ROM de l'humain, 2026-09-28).
REFERENCE_RANG_D: tuple[str, int] = ("c03_trigger", 33)
# Yo-criminels (archipelago_amis_criminels.md §3) : emplacement tiré au hasard parmi 30 points de 5 cartes ; référence =
# déclencheur des indices (t103g00_trigger n° 38, RunCmd_Map38 -> ev76_0500) : type 13, carte seulement (t103g00 sur la
# ROM de l'humain, 2026-09-29).
REFERENCE_CRIMINELS: tuple[str, int] = ("t103g00_trigger", 38)
# Boutiques (archipelago_tracker_cartes.md §11) : le déclencheur de type 81 de la carte a pour identifiant le hachage
# de la boutique, pas un lieu. Le lieu est celui du PNJ VENDEUR, lu dans la ROM du joueur : `<carte>_npc_talk` :
# `TALK_INFO(PNJ, 1re config, nombre)` -> `TALK_CONFIG` (champs 4 / 5 : 1er choix, nombre) -> `TALK_SELECT` dont la
# commande pose l'octet temporaire `tmp_shop_id` = N (et `tmp_shop_type` = 0 : boutique en euros) avant d'ouvrir le menu
# [C, données]. Identifiants seulement ici (règle 6) : hachages de la fonction de pose et des deux octets temporaires
# (archipelago_boutiques.md §1.1), et pour la boutique ouverte par un script (N008, `RunCheapSweetsShop`) le déclencheur
# de type 11 (parler au PNJ) dont le `RunCmd_MapN` appelle ce script [C, script].
POSE_TEMPORAIRE = 0x73EB11DC                # fonction de commande « poser un octet temporaire » (hachage, valeur)
TMP_SHOP_ID = 0xADBA2641
TMP_SHOP_TYPE = 0xDEDC17BC
REFERENCES_BOUTIQUES_SCRIPT: dict[str, tuple[str, int]] = {"N008": ("t103i23_trigger", 11)}
MAP_ROUTE = "data/res/map/" + "map_route_"  # MAP_ROUTE_CONFIG(carte, début, nombre) -> MAP_ROUTE_INFO(+1 zone, +2 cible)
SAUTS_ENTREE = 2                            # galerie marchande : extérieur -> galerie -> boutique


def references(LQ) -> dict[int, tuple]:
    """Toutes les locations possibles de l'APWorld (module `logique`, `LQ`) -> référence :
    ("tbox", index) | ("tablo", flag) | ("quete", n) | ("declencheur", fichier, n[, carte]) | ("carte", carte) |
    ("quete_phase", n, phase, carte) | ("warp", flag) | ("pnj", carte, identifiant) | ("entree", source, cible) |
    ("boutique", code) | ("distributeur", carte, rang) | ("aucun",)."""
    out: dict[int, tuple] = {}
    for co in LQ.coffres_possibles():
        out[int(co["id_ap"])] = ("tbox", int(co["index_tbox"]))
    for t in LQ.TABLOS_CREES:
        out[int(t["id_ap"])] = ("tablo", int(t["flag"]))
    for q in LQ.QUETES:
        out[int(q["id_ap"])] = ("quete", int(q["n"]))
    v = getattr(LQ, "QUETE_VELO", None)
    if v:
        out[int(v["id_ap"])] = ("quete", int(v["quete"]))
    for e in LQ.donnees().emplacements:
        ref = REFERENCES_OBJETS_CLES.get(e["objet"])
        out[int(e["id_ap"])] = _ref(ref)
    for cle, e in getattr(LQ, "EMPLACEMENTS_V3", {}).items():   # V3 : objets-clés à emplacement d'évènement
        out[int(e["id_ap"])] = _ref(REFERENCES_OBJETS_CLES_V3.get(cle))
    for b in LQ.TOUS_LES_BOSS:
        out[int(b["id_ap"])] = _ref(REFERENCES_BOSS.get(b["cle"]))
    rd = getattr(LQ, "RANG_D_CHECK", None)
    if rd:                                                   # scène de la montée de rang D (c03_trigger n° 33)
        out[int(rd["id_ap"])] = _ref(REFERENCE_RANG_D)
    for ch in getattr(LQ, "CHAPITRES_CHECKS", []):
        out[int(ch["id_ap"])] = ("aucun",)
    for a in getattr(LQ, "AMIS", []):                        # lieux selon le mélange du joueur : sans position
        out[int(a["id_ap"])] = ("aucun",)
    PS = getattr(LQ, "PS", None)
    quittent = getattr(PS, "QUITTENT_AUBERGE", frozenset())
    for a in getattr(LQ, "INVITES", []):                     # invités de l'Auberge : Suite ou porte des chambres
        if a.get("declencheur") == "requetes":
            out[int(a["id_ap"])] = REFERENCE_INVITE_SUITE
        elif a["medaille"] in quittent:
            out[int(a["id_ap"])] = ("aucun",)
        else:
            out[int(a["id_ap"])] = REFERENCE_INVITE_CHAMBRE
    for c in getattr(LQ, "CRIMINELS", []):                   # emplacement tiré au hasard : carte des indices
        out[int(c["id_ap"])] = _ref(REFERENCE_CRIMINELS)
    for a in getattr(LQ, "BOUTIQUES_ARTICLES", []):          # PNJ vendeur de la boutique (`resoudre_boutiques`)
        out[int(a["id_ap"])] = ("boutique", str(a["boutique"]))
    # V3, lot C1 : distributeurs de soda : point OP_VENDING_POINT de rang `rang` du fichier `_oneplace` de la carte
    DI = getattr(LQ, "DI", None)
    for x in getattr(DI, "LOCATIONS", []):
        out[int(x["id_ap"])] = ("distributeur", str(x["carte"]), int(x["rang"]))
    # V3, lot 3 : après-jeu (les coffres sont déjà dans `coffres_possibles`) : requêtes par leur n° (et requêtes à
    # transfert d'avant la fin), Tablo-blabla n° 24 par son flag ; emplacements et boss (lot « carte des checks ») :
    # tables ci-dessus ; amis et terrains de Blasters : sans position
    AJ = getattr(LQ, "AJ", None)
    if AJ is not None:
        for q in list(AJ.QUETES) + list(getattr(AJ, "QUETES_TRANSFERT", [])):
            out[int(q["id_ap"])] = ("quete", int(q["n"]))
        for t in LQ.TABLOS:
            if t.get("apres_jeu"):
                out[int(t["id_ap"])] = ("tablo", int(t["flag"]))
        for cle, x in AJ.EMPLACEMENTS.items():
            out[int(x["id_ap"])] = _ref(REFERENCES_OBJETS_CLES_AJ.get(cle))
        for x in list(AJ.BOSS) + list(getattr(AJ, "BOSS_MEDAILLE", [])):
            out[int(x["id_ap"])] = _ref(REFERENCES_BOSS_AJ.get(x["cle"]))
        for x in list(AJ.AMIS) + list(AJ.BLASTERS):
            out[int(x["id_ap"])] = ("aucun",)
    return out


def boutiques_apworld(LQ) -> dict[str, dict]:
    """Boutiques de l'APWorld : code N0xx -> {"numero": N, "cartes": [sa carte, puis celles de ses déclencheurs]}."""
    out: dict[str, dict] = {}
    for code, b in sorted(getattr(LQ, "BOUTIQUES_PAR_CODE", {}).items()):
        m = re.match(r"N(\d+)$", str(code))
        if not m:
            continue
        cartes = [b["carte"]] if b.get("carte") else []
        for d in b.get("declencheurs") or ():
            c = str(d).split("#")[0]
            if c and c not in cartes:
                cartes.append(c)
        out[str(code)] = {"numero": int(m.group(1)), "cartes": cartes}
    return out


def _ref(ref) -> tuple:
    """Entrée d'une table de références -> référence (`references`). (fichier, n[, carte]) : déclencheur."""
    if not ref:
        return ("aucun",)
    if ref[0] == "quete":
        return ("quete", int(ref[1]))
    if ref[0] in ("quete_phase", "warp", "pnj", "entree", "carte"):
        return tuple(ref)
    return ("declencheur", ref[0], int(ref[1])) + tuple(ref[2:])


def hachages_objets(LQ) -> dict[str, int]:
    """Cases de la colonne des objets de progression et de la section des objets d'évènement qui ont une icône du jeu :
    clé -> hachage d'objet (le sien, ou celui d'`ICONES_SANS_HACHAGE`), chapitres compris (`CLE_CHAPITRES`)."""
    out = {CLE_CHAPITRES: ICONES_SANS_HACHAGE[CLE_CHAPITRES]}
    for o in LQ.donnees().objets:
        h = o.get("hachage")
        if h is None:
            h = ICONES_SANS_HACHAGE.get(o.get("cle"), ICONES_DESSINEES.get(o.get("cle")))
        if o.get("famille") not in FAMILLES_AVEC_ICONE or h is None:
            continue
        try:
            out[o["cle"]] = int(h, 0) if isinstance(h, str) else int(h)
        except (TypeError, ValueError):
            continue
    if any(o.get("cle") in OV.CLES_AP_DONJON for o in LQ.donnees().objets):
        out.update(ICONES_TROUSSEAU)
    return out


def signature_references(refs: dict[int, tuple], icones: dict[str, int] | None = None) -> str:
    """Empreinte de la table des références et des icônes (le fichier local est refait si l'APWorld ou la table
    change)."""
    tab = [sorted((k, list(v)) for k, v in refs.items()), sorted((icones or {}).items())]
    if CLES_IMAGES_HUMAIN & set(icones or {}):           # images de l'humain (ap/icones-images) : régénération une fois
        tab.append(["images", VERSION_IMAGES])
    brut = json.dumps(tab, separators=(",", ":"))
    return hashlib.sha1(brut.encode()).hexdigest()


# ------------------------------------------------------------------------------------------------ lecture du jeu
def _sv(v):
    return struct.unpack("<i", struct.pack("<I", v))[0] if isinstance(v, int) and v >= 0x80000000 else v


def _crc(s: str) -> int:
    return zlib.crc32(s.encode()) & 0xFFFFFFFF


def _num(v) -> float | None:
    v = _sv(v)
    return float(v) if isinstance(v, (int, float)) else None


class Jeu:
    """Index des données utiles de `yw2_a.fa` (lecture paresseuse, archive gardée ouverte : `fermer()`)."""

    def __init__(self, rom: str | Path):
        src = L5.SourceRomfs(rom)
        self._f, off, _t = src.ouvrir("yw2_a.fa")
        self.a = L5.Arc0(self._f, off)
        self.e = self.a.entrees
        self.cartes = sorted({k.split("/")[3] for k in self.e if re.match(r"data/res/map/([^/]+)/\1\.pck$", k)})
        self.nom_carte = {_crc(c): c for c in {k.split("/")[3] for k in self.e
                                              if k.startswith("data/res/map/") and k.count("/") >= 4}}
        self.points: dict[str, dict[int, tuple[float, float]]] = {}
        self.op: dict[str, dict[str, list]] = {}
        self.pck: dict[str, dict[str, bytes]] = {}
        self._pnj = None
        self._env: dict[str, dict] = {}
        self.flags: dict[tuple[int, int], int] = {}
        # cartes à Yo-kai sauvages (format 4, Yo-kai épinglé du lanceur) : chemin d'errants à position connue
        # (`SET_PATH` de `<carte>_enc_pos`) ou table de loupe (`WM_YOKAI_ENCOUNT` de `<carte>_watchmap`)
        self.cartes_yokai: set[str] = set()

    def fermer(self) -> None:
        try:
            self._f.close()
        except OSError:
            pass

    def indexer(self, progression: Callable[[int, int], object] | None = None) -> None:
        for k, c in enumerate(self.cartes):
            if progression:
                progression(k, len(self.cartes))
            try:
                x = L5.Xpck(self.a.lire("data/res/map/%s/%s.pck" % (c, c)))
            except (L5.ErreurFormat, OSError):
                continue
            fp = {n[0]: x.lire(n[0]) for n in x.fichiers}
            self.pck[c] = {n: d for n, d in fp.items() if "_trigger" in n}
            pts, op = {}, defaultdict(list)
            for n, d in fp.items():
                if n.endswith("_enc_pos.cfg.bin") or "_watchmap_" in n:
                    if any((nom == "SET_PATH" and len(v) > 3 and any(_num(a) for a in v[1:4]))
                           or nom == "WM_YOKAI_ENCOUNT" for nom, v in _entrees(d)):
                        self.cartes_yokai.add(c)
                    continue
                if n.endswith("_layout.bin") or "_oneplace_pos" in n:
                    for nom, v in _entrees(d):
                        if nom in ("SHAPE_DATA_ITEM", "POINT_DATA_ITEM") and len(v) > 3:
                            x_, z_ = _num(v[1]), _num(v[3])
                            if x_ is not None and z_ is not None:
                                pts.setdefault(v[0], (x_, z_))
                elif "_oneplace_0" in n:
                    for nom, v in _entrees(d):
                        if nom.startswith("OP_") and not nom.endswith(("_BEGIN", "_END")):
                            op[nom].append(v)
            self.points[c], self.op[c] = pts, op
        cat = None
        for nom, v in _entrees(self.a.lire(FLAG_CONFIG)):
            if nom == "FLAG_INFO_BEGIN":
                cat = v[0]
            elif nom == "FLAG_INFO":
                self.flags[(cat, v[0])] = v[1]

    # --- PNJ : NPC_BASE id -> [(carte, nom du .npcbin)] ---
    def pnj(self) -> dict[int, list[tuple[str, str]]]:
        if self._pnj is None:
            self._pnj = defaultdict(list)
            for k in self.e:
                m = re.match(r"data/res/map/([^/]+)/[^/]+_npc_set_0\.[0-9a-z]+\.cfg\.bin$", k)
                if not m:
                    continue
                E = _entrees(self.a.lire(k))
                ap = [v for nom, v in E if nom == "NPC_APPEAR"]
                for nom, v in E:
                    if nom == "NPC_PRESET" and len(v) >= 3:
                        i, d, n = v[:3]
                        for a in ap[d:d + n]:
                            self._pnj[i].append((m.group(1), a[0]))
        return self._pnj

    def pos_npcbin(self, c: str, nom: str):
        k = "data/res/map/%s/%s.npcbin" % (c, nom)
        if k not in self.e:
            return None
        for n, v in _entrees(self.a.lire(k)):
            if n == "POINT" and len(v) > 2:
                x, z = _num(v[0]), _num(v[2])
                if x is not None and z is not None:
                    return x, z
        return None

    def resoudre(self, ident, carte: str | None = None):
        """Identifiant de zone / point / PNJ / carte -> (carte, x, z) (x, z à None : carte seulement) ou None."""
        if carte and ident in self.points.get(carte, {}):
            return (carte,) + self.points[carte][ident]
        if carte is None:
            g = [(c, p[ident]) for c, p in self.points.items() if ident in p]
            if g and len({c for c, _p in g}) == 1:
                return (g[0][0],) + g[0][1]
        for c, nb in self.pnj().get(ident, []):
            if carte and c != carte:
                continue
            p = self.pos_npcbin(c, nb)
            if p:
                return c, p[0], p[1]
        if ident in self.nom_carte:
            return self.nom_carte[ident], None, None
        if carte:
            return carte, None, None
        return None

    # --- minicarte ---
    def env(self, c: str) -> dict:
        if c not in self._env:
            r: dict = {}
            k = "data/map/%s/mapenv.pck" % c
            if k in self.e:
                try:
                    x = L5.Xpck(self.a.lire(k))
                    for f in x.fichiers:
                        if f[0].endswith("_mapenv.bin"):
                            E = _entrees(x.lire(f[0]))
                            for i, (nom, v) in enumerate(E):
                                if nom == "PTREE" and v and v[0] in ("MMModelPos", "MMViewSize"):
                                    vals, j = [], i + 1
                                    while j < len(E) and E[j][0] != "_PTREE":
                                        vals += list(E[j][1])
                                        j += 1
                                    r[v[0]] = [_sv(a) for a in vals]
                except (L5.ErreurFormat, OSError, ValueError, IndexError, struct.error):
                    pass
            xi = "data/map/%s/%s.xi" % (c, c)
            if xi in self.e:
                d = self.a.lire(xi)
                if d[:4] == b"IMGC":
                    r["image"] = xi
                    r["taille"] = struct.unpack_from("<HH", d, 0x10)
            self._env[c] = r
        return self._env[c]

    def vue(self, c: str):
        """(Vw, Vh) affichés de la minicarte, bornés à l'image ; None sans image ni MMModelPos."""
        r = self.env(c)
        if "image" not in r or len(r.get("MMModelPos") or ()) != 4:
            return None
        w, h = r["taille"]
        vv = r.get("MMViewSize") or ()
        vw, vh = (int(vv[0]), int(vv[1])) if len(vv) == 2 and vv[0] > 0 and vv[1] > 0 else (w, h)
        return min(vw, w), min(vh, h)

    def monde(self, c: str):
        """(x0, z0, x1, z1, Vw, Vh) : rectangle monde (`MMModelPos`) couvert par les (Vw, Vh) texels affichés
        (`MMViewSize`, sinon taille de l'image, NON bornés : mêmes nombres que le jeu) ; None sans image."""
        r = self.env(c)
        if "image" not in r or len(r.get("MMModelPos") or ()) != 4:
            return None
        x0, z0, x1, z1 = (float(v) for v in r["MMModelPos"])
        if x1 == x0 or z1 == z0:
            return None
        vv = r.get("MMViewSize") or ()
        vw, vh = (vv[0], vv[1]) if len(vv) == 2 and vv[0] > 0 and vv[1] > 0 else r["taille"]
        return x0, z0, x1, z1, vw, vh

    def pixel(self, c: str, x: float, z: float):
        m = self.monde(c)
        return None if m is None else monde_vers_pixel(m, x, z)

    def infos_cartes(self) -> dict[str, tuple[int | None, str | None]]:
        """`MAP_INFO` de `map_config` : {carte: (zone, carte de son groupe ou None)} pour toutes les cartes du jeu
        (groupe : ex. les salles de l'école sous `t101i51`) [S fort, archipelago_tracker_cartes.md §3]. Vide si le
        fichier manque ou n'a pas cette forme (le lanceur se rabat alors sur l'identifiant)."""
        if MAP_CONFIG not in self.e:
            return {}
        brut = []
        for nom, v in _entrees(self.a.lire(MAP_CONFIG)):
            if nom != "MAP_INFO" or len(v) < 12 or not isinstance(v[0], int):
                continue
            c = v[9] if isinstance(v[9], str) else next((x for x in v if isinstance(x, str)), None)
            if not c or _crc(c) != v[0] & 0xFFFFFFFF:        # nom et hachage de la même carte, sinon forme inconnue
                continue
            brut.append((c, v[3] if isinstance(v[3], int) else None, v[11] if isinstance(v[11], int) else None))
        par_hachage = {_crc(c): c for c, _z, _g in brut}
        return {c: (z, par_hachage.get(g & 0xFFFFFFFF) if g is not None else None) for c, z, g in brut}


# ------------------------------------------------------------------------------------------------ boutiques
_POSE = b"\x35" + struct.pack(">I", POSE_TEMPORAIRE)
_ARG_HACHAGE = b"\x28\x00\x06\x02\x34"
_ARG_ENTIER = b"\x28\x00\x06\x02\x32"


def poses_temporaires(v) -> dict[int, int]:
    """Commande compilée (base64 « AAAA… ») -> {hachage de l'octet temporaire: valeur posée} pour chaque appel de
    `POSE_TEMPORAIRE(hachage, constante)` ; autre valeur : {}."""
    if not (isinstance(v, str) and v.startswith("AAAA")):
        return {}
    try:
        b = base64.b64decode(v)
    except (ValueError, TypeError):
        return {}
    out: dict[int, int] = {}
    i = 0
    while True:
        i = b.find(_POSE, i)
        if i < 0:
            return out
        # 35 <fonction> <taille u16> <nombre d'arguments> | 28 00 06 02 34 <hachage> | 28 00 06 02 32 <constante>
        a = b[i + 8:i + 26]
        if len(a) == 18 and a[:5] == _ARG_HACHAGE and a[9:14] == _ARG_ENTIER:
            out[struct.unpack_from(">I", a, 5)[0]] = struct.unpack_from(">I", a, 14)[0]
        i += 1


def vendeurs_carte(jeu: "Jeu", carte: str) -> dict[int, list[tuple[int, bool]]]:
    """N de boutique en euros -> [(PNJ, version « portails » de la carte)] : PNJ de `carte` dont un choix de dialogue
    ouvre la boutique N (`TALK_INFO` -> `TALK_CONFIG` -> `TALK_SELECT`, ou commande du `TALK_CONFIG` lui-même)."""
    out: dict[int, list[tuple[int, bool]]] = defaultdict(list)
    motif = re.compile(r"data/res/map/%s/%s_npc_talk(_gate)?_0\.[0-9a-z]+\.cfg\.bin$" % (carte, carte))
    for k in sorted(jeu.e):
        m = motif.match(k)
        if not m:
            continue
        E = _entrees(jeu.a.lire(k))
        conf = [v for nom, v in E if nom == "TALK_CONFIG"]
        sel = [v for nom, v in E if nom == "TALK_SELECT"]
        for nom, v in E:
            if nom != "TALK_INFO" or len(v) < 3 or not all(isinstance(x, int) for x in v[:3]):
                continue
            for cf in conf[v[1]:v[1] + v[2]]:
                valeurs = list(cf)
                if len(cf) > 5 and isinstance(cf[4], int) and isinstance(cf[5], int):
                    for s in sel[cf[4]:cf[4] + cf[5]]:
                        valeurs += list(s)
                for x in valeurs:
                    p = poses_temporaires(x)
                    cle = (v[0], bool(m.group(1)))
                    if TMP_SHOP_ID in p and p.get(TMP_SHOP_TYPE) == 0 and cle not in out[p[TMP_SHOP_ID]]:
                        out[p[TMP_SHOP_ID]].append(cle)
    return out


def positions_pnj(jeu: "Jeu", carte: str, ident: int, portails: bool = False) -> list[tuple[float, float]]:
    """Positions monde (x, z) du PNJ `ident` sur `carte` : `NPC_PRESET` -> `NPC_APPEAR` -> `.npcbin` (toutes ses
    variantes d'apparition, sans doublon)."""
    motif = re.compile(r"data/res/map/%s/%s_npc_set%s_0\.[0-9a-z]+\.cfg\.bin$"
                       % (carte, carte, "_gate" if portails else ""))
    out: list[tuple[float, float]] = []
    for k in sorted(jeu.e):
        if not motif.match(k):
            continue
        E = _entrees(jeu.a.lire(k))
        ap = [v for nom, v in E if nom == "NPC_APPEAR"]
        for nom, v in E:
            if nom == "NPC_PRESET" and len(v) >= 3 and v[0] == ident:
                for a in ap[v[1]:v[1] + v[2]]:
                    p = jeu.pos_npcbin(carte, a[0]) if a and isinstance(a[0], str) else None
                    if p and p not in out:
                        out.append(p)
    return out


# Conditions d'apparition d'un vendeur (format 6, archipelago_tracker_cartes.md §12) : chaque `NPC_APPEAR(nom du
# .npcbin, moment, météo, condition, …)` d'un PNJ est une VARIANTE (le PNJ est là si l'une d'elles est vraie). Un étal
# ambulant a une condition `GetGlobalByteFlag(octet) == k` dont l'octet est tiré par le jeu d'après `random_event`
# (`RANDOM_EVENT_ELEMENT(octet, min, max)` d'un `RANDOM_EVENT_CONFIG`, taux et condition de son `RANDOM_EVENT_RATE`).
# Identifiants et nombres lus dans la ROM du joueur, écrits dans son fichier local seulement (règle 6).
EVENEMENTS_ALEATOIRES = "data/res/map/" + "random_event_"
OCTET_GLOBAL = "GetGlobalByteFlag"


def evenements_aleatoires(jeu: "Jeu") -> dict[int, dict]:
    """Hachage d'octet global tiré -> {"min", "max", "taux", "e" (condition du taux, jetons), "creneaux" (masque du
    CONFIG), "mode" (2e champ du CONFIG), "groupe" (nombre de CONFIG de son groupe), "cartes" (nombre de cartes)}."""
    out: dict[int, dict] = {}
    for k in sorted(jeu.e):
        if not (k.startswith(EVENEMENTS_ALEATOIRES) and k.endswith(".cfg.bin")):
            continue
        E = _entrees(jeu.a.lire(k))
        taux = [v for nom, v in E if nom == "RANDOM_EVENT_RATE"]
        elements = [v for nom, v in E if nom == "RANDOM_EVENT_ELEMENT"]
        groupe = 1
        for nom, v in E:
            if nom == "RANDOM_EVENT_CONFIG_BEGIN" and len(v) > 1 and isinstance(v[1], int):
                groupe = v[1]
            if nom != "RANDOM_EVENT_CONFIG" or len(v) < 9 or not all(isinstance(x, int) for x in v[:9]):
                continue
            t = taux[v[2]] if 0 <= v[2] < len(taux) else None
            for el in elements[v[7]:v[7] + v[8]]:
                if len(el) < 3 or not all(isinstance(x, int) for x in el[:3]):
                    continue
                out.setdefault(el[0], {
                    "min": el[1], "max": el[2], "taux": t[0] if t and isinstance(t[0], int) else None,
                    "e": (decoder_condition(t[1]) if t and len(t) > 1 else None) or [],
                    "creneaux": v[6], "mode": v[1], "groupe": groupe, "cartes": v[5]})
    return out


def octet_compare(rpn) -> tuple[int, int] | None:
    """Condition décodée qui contient `GetGlobalByteFlag(octet) == k` -> (hachage de l'octet, k) (la première)."""
    for i in range(len(rpn or ()) - 2):
        a, b, c = rpn[i:i + 3]
        if a[:2] == ["f", OCTET_GLOBAL] and b[0] == "i" and c == ["o", "=="] and len(a) > 2 and len(a[2]) == 1 \
                and len(a[2][0]) == 1 and a[2][0][0][0] == "n":
            return a[2][0][0][1], b[1]
    return None


def _signe(v):
    return v - (1 << 32) if isinstance(v, int) and v >= 1 << 31 else v


def apparitions_pnj(jeu: "Jeu", carte: str, ident: int, portails: bool = False,
                    tirages: dict[int, dict] | None = None) -> list[tuple[float, float, dict]]:
    """Variantes d'apparition du PNJ `ident` sur `carte` : [(x, z, {"h": champ « moment » (-1 : tous), "m": champ
    « météo », "e": condition décodée (absente : aucune), "r": son résumé (`rencontres.resumer_condition`), "tirage": étal ambulant (`evenements_aleatoires` + "k")})]."""
    motif = re.compile(r"data/res/map/%s/%s_npc_set%s_0\.[0-9a-z]+\.cfg\.bin$"
                       % (carte, carte, "_gate" if portails else ""))
    out: list[tuple[float, float, dict]] = []
    for k in sorted(jeu.e):
        if not motif.match(k):
            continue
        E = _entrees(jeu.a.lire(k))
        ap = [v for nom, v in E if nom == "NPC_APPEAR"]
        for nom, v in E:
            if nom == "NPC_PRESET" and len(v) >= 3 and v[0] == ident:
                for a in ap[v[1]:v[1] + v[2]]:
                    p = jeu.pos_npcbin(carte, a[0]) if a and isinstance(a[0], str) else None
                    if not p:
                        continue
                    d: dict = {"h": _signe(a[1]) if len(a) > 1 and isinstance(a[1], int) else -1,
                               "m": _signe(a[2]) if len(a) > 2 and isinstance(a[2], int) else -1}
                    rpn = decoder_condition(a[3]) if len(a) > 3 else None
                    if rpn:
                        d["e"] = rpn
                        d["r"] = resumer_condition(rpn)
                        oc = octet_compare(rpn)
                        if oc and tirages and oc[0] in tirages:
                            d["tirage"] = dict(tirages[oc[0]], k=oc[1])
                    if (p[0], p[1], d) not in out:
                        out.append((p[0], p[1], d))
    return out


def routes_vers(jeu: "Jeu") -> dict[str, list[tuple[str, int]]]:
    """Carte cible -> [(carte source, zone de la source)] d'après `map_route` (`MAP_ROUTE_CONFIG(carte, début,
    nombre)` -> `MAP_ROUTE_INFO` : +1 zone, +2 carte cible) ; la table du guidage (`map_route_quest`) est ignorée."""
    out: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for k in sorted(jeu.e):
        if not k.startswith(MAP_ROUTE) or "quest" in k or not k.endswith(".cfg.bin"):
            continue
        E = _entrees(jeu.a.lire(k))
        info = [v for nom, v in E if nom == "MAP_ROUTE_INFO"]
        for nom, v in E:
            if nom != "MAP_ROUTE_CONFIG" or len(v) < 3:
                continue
            src = jeu.nom_carte.get(v[0])
            for r in info[v[1]:v[1] + v[2]] if src else ():
                cible = jeu.nom_carte.get(r[2]) if len(r) > 2 else None
                if cible and cible != src and (src, r[1]) not in out[cible]:
                    out[cible].append((src, r[1]))
    return out


def entrees_batiment(jeu: "Jeu", carte: str,
                     routes: dict[str, list[tuple[str, int]]]) -> list[tuple[str, float, float, str]]:
    """Portes qui mènent à l'intérieur `carte` depuis l'extérieur : [(carte source, x, z, carte où l'on entre)].
    Une porte = une route `map_route` dont la zone a une position dans la carte source. Routes directes depuis un
    extérieur si elles existent ; sinon par un autre intérieur lui-même relié à l'extérieur (au plus `SAUTS_ENTREE`
    sauts : extérieur -> galerie -> boutique), jamais par un donjon. Carte d'extérieur ou sans route : []."""
    out: list[tuple[str, float, float, str]] = []
    if genre_carte(carte) != "interieur":
        return out

    def ajouter(src, zone, cible):
        p = jeu.points.get(src, {}).get(zone)
        if p is not None and (src, p[0], p[1], cible) not in out:
            out.append((src, p[0], p[1], cible))

    def portes(c, reste, vus) -> bool:
        sources = [(s, z) for s, z in routes.get(c, ()) if s not in vus]
        dehors = [(s, z) for s, z in sources if genre_carte(s) == "exterieur"]
        if dehors:
            for s, z in dehors:
                ajouter(s, z, c)
            return True
        if reste <= 1:
            return False
        trouve = False
        for s, z in sources:
            if genre_carte(s) == "interieur" and portes(s, reste - 1, vus | {s}):
                ajouter(s, z, c)
                trouve = True
        return trouve
    portes(carte, SAUTS_ENTREE, {carte})
    return out


def resoudre_boutiques(jeu: "Jeu", LQ) -> dict[str, dict]:
    """Code N0xx -> {"vendeurs": [(carte, x, z)], "entrees": [(carte source, x, z, carte où l'on entre)]}, positions
    monde. Boutique sans PNJ vendeur trouvé : absente (ses articles restent « sur cette carte, position inconnue »)."""
    out: dict[str, dict] = {}
    cache: dict[str, dict] = {}
    routes = None
    try:                                     # format 6 : "apparitions" = {(carte, x, z): [variantes d'apparition]}
        tirages = evenements_aleatoires(jeu)
    except (L5.ErreurFormat, OSError, ValueError, IndexError, KeyError, TypeError, struct.error):
        tirages = {}
    for code, b in boutiques_apworld(LQ).items():
        apparitions: dict[tuple, list] = {}
        vendeurs: list[tuple[str, float, float]] = []
        script = REFERENCES_BOUTIQUES_SCRIPT.get(code)
        for c in b["cartes"]:
            if c not in cache:
                cache[c] = vendeurs_carte(jeu, c)
            pnjs = list(cache[c].get(b["numero"], ()))
            if script and script[0].split("_")[0] == c:      # déclencheur de type 11 (parler au PNJ) -> script
                t = declencheurs(jeu, script[0]).get(script[1])
                if t and t[0] == 11 and (t[1], False) not in pnjs:
                    pnjs.append((t[1], False))
            for ident, portails in pnjs:
                for x, z, variante in apparitions_pnj(jeu, c, ident, portails, tirages):
                    if (c, x, z) not in vendeurs:
                        vendeurs.append((c, x, z))
                    if variante not in apparitions.setdefault((c, x, z), []):
                        apparitions[(c, x, z)].append(variante)
        if not vendeurs:
            continue
        if routes is None:
            routes = routes_vers(jeu)
        entrees: list[tuple[str, float, float, str]] = []
        for c in dict.fromkeys(v[0] for v in vendeurs):
            for e in entrees_batiment(jeu, c, routes):
                if e not in entrees:
                    entrees.append(e)
        out[code] = {"vendeurs": vendeurs, "entrees": entrees, "apparitions": apparitions}
    return out


def monde_vers_pixel(monde, x: float, z: float) -> tuple[float, float]:
    """Monde -> pixel de la minicarte (archipelago_tracker_cartes.md §2.1, `FUN_003C33E4`) : `monde` =
    (x0, z0, x1, z1, Vw, Vh). La MÊME formule place les checks (à la génération) et le joueur (dans le lanceur)."""
    x0, z0, x1, z1, vw, vh = monde
    return (x - x0) * vw / (x1 - x0), (z - z0) * vh / (z1 - z0)


def carte_parente(carte: str, infos: dict[str, tuple[int | None, str | None]], avec_image) -> str | None:
    """Carte À IMAGE à montrer quand le joueur est sur `carte`, qui n'en a pas (intérieur sans check) : la carte de
    son groupe (`MAP_INFO` +11), sinon l'extérieur de sa zone (`t<zone>g00`, zone de `MAP_INFO` +3, sinon celle de
    l'identifiant). None : aucune (le lanceur garde la carte affichée)."""
    zone, groupe = infos.get(carte, (None, None))
    if groupe and groupe != carte and groupe in avec_image:
        return groupe
    candidats = []
    if isinstance(zone, int) and 0 < zone < 1000:
        candidats.append("t%03dg00" % zone)
    if re.match(r"t\d{3}[a-z]\d{2}", carte):
        candidats.append(carte[:4] + "g00")
    for c in candidats:
        if c != carte and c in avec_image:
            return c
    return None


def _entrees(data: bytes) -> list:
    try:
        return CfgBin(data).entrees
    except (ValueError, IndexError, KeyError, struct.error):
        return []


def declencheurs(jeu: Jeu, fichier: str) -> dict[int, list]:
    """« c03_trigger » ou « t103d31_quest_trigger » -> {n: valeurs du DATA_ITEM}."""
    if re.match(r"c\d\d_", fichier):
        donnees = [jeu.a.lire(k) for k in jeu.e if k.startswith("data/res/phs/%s/%s_" % (fichier[:3], fichier))]
    else:
        donnees = [d for n, d in jeu.pck.get(fichier.split("_")[0], {}).items() if n.startswith(fichier)]
    r: dict[int, list] = {}
    for d in donnees:
        for nom, v in _entrees(d):
            if nom == "DATA_ITEM" and len(v) >= 2:
                r.setdefault(v[-1], v)
    return r


class Quetes:
    def __init__(self, jeu: Jeu):
        k = [k for k in jeu.e if k.startswith("data/res/quest/quest_config")]
        E = _entrees(jeu.a.lire(k[0])) if k else []
        self.config = {v[3]: v for nom, v in E if nom == "QUEST_CONFIG" and len(v) > 7}
        self.phases = [v for nom, v in E if nom == "QUEST_PHASE"]
        self.objectifs = [v for nom, v in E if nom == "QUEST_PURPOSE_POS"]

    def position(self, jeu: Jeu, n: int):
        q = self.config.get(n)
        if not q:
            return None
        for p in self.phases[q[6]:q[6] + q[7]]:
            if len(p) > 2 and p[2] > 0 and p[1] < len(self.objectifs):        # 1re phase avec un objectif
                pp = self.objectifs[p[1]]
                return jeu.resoudre(pp[1], jeu.nom_carte.get(pp[0]))
        return None

    def position_phase(self, jeu: Jeu, n: int, phase: int, carte: str):
        """Premier objectif de la phase `phase` (1er champ de `QUEST_PHASE`) de la requête n situé dans `carte` ;
        sinon `carte` seule (la carte du don, connue par son déclencheur)."""
        q = self.config.get(n)
        for p in self.phases[q[6]:q[6] + q[7]] if q else ():
            if len(p) > 2 and p[0] == phase and p[2] > 0:
                for pp in self.objectifs[p[1]:p[1] + p[2]]:
                    if jeu.nom_carte.get(pp[0]) == carte:
                        r = jeu.resoudre(pp[1], carte)
                        if r is not None and r[1] is not None:
                            return r
        return (carte, None, None)


WARP_CONFIG = "data/res/map/" + "warp_config.cfg.bin"


def miroirs(jeu: Jeu) -> dict[int, tuple]:
    """Miroirs (`WARP_INFO` de `warp_config` : +0 hachage du flag bit global, +1 CRC-32 de la carte, +2 x, +3 y, +4 z)
    -> {hachage du flag: (carte, x, z)}. Vide si le fichier manque ou n'a pas cette forme."""
    out: dict[int, tuple] = {}
    if WARP_CONFIG not in jeu.e:
        return out
    for nom, v in _entrees(jeu.a.lire(WARP_CONFIG)):
        if nom != "WARP_INFO" or len(v) < 5 or not isinstance(v[0], int):
            continue
        c, x, z = jeu.nom_carte.get(v[1]), _num(v[2]), _num(v[4])
        if c and x is not None and z is not None:
            out.setdefault(v[0], (c, x, z))
    return out


def resoudre_references(jeu: Jeu, refs: dict[int, tuple]) -> dict[int, tuple]:
    """{id_ap: (carte, x, z, précision)} pour les références résolues (x, z à None : carte seulement)."""
    qs = Quetes(jeu)
    tflag = {h: i for (cat, i), h in jeu.flags.items() if cat == 1}
    tbox: dict[int, tuple[str, int]] = {}
    for c, op in jeu.op.items():
        for v in op.get("OP_TBOX_POINT", []):
            i = tflag.get(v[6]) if len(v) > 6 else None
            if i is not None and i not in tbox:
                tbox[i] = (c, v[1] if v[1] in jeu.points.get(c, {}) else v[0])
    cache_decl: dict[str, dict] = {}
    warps, routes = None, None
    out: dict[int, tuple] = {}
    for ident, ref in refs.items():
        r, precision = None, "approx"
        if ref[0] == "tbox":
            if ref[1] in tbox:
                r = jeu.resoudre(tbox[ref[1]][1], tbox[ref[1]][0])
            precision = "point"
        elif ref[0] == "tablo":
            h = jeu.flags.get((0, ref[1]))
            l = [(c, v[1]) for c, op in sorted(jeu.op.items()) for v in op.get("OP_TERRITORY_POINT", [])
                 if v and v[0] == h and len(v) > 1]
            r = jeu.resoudre(l[0][1], l[0][0]) if l else None
            precision = "point"
        elif ref[0] == "quete":
            r = qs.position(jeu, ref[1])
        elif ref[0] == "carte":
            r = (ref[1], None, None)
        elif ref[0] == "boutique":                           # placée par `resoudre_boutiques` (voir `generer`)
            continue
        elif ref[0] == "distributeur":                       # V3, lot C1 : point du distributeur dans sa carte
            pts = jeu.op.get(ref[1], {}).get("OP_VENDING_POINT", [])
            if 0 <= ref[2] < len(pts) and pts[ref[2]]:
                r = jeu.resoudre(pts[ref[2]][0], ref[1])
            precision = "point"
        elif ref[0] == "declencheur":
            if ref[1] not in cache_decl:
                cache_decl[ref[1]] = declencheurs(jeu, ref[1])
            t = cache_decl[ref[1]].get(ref[2])
            if t:
                carte = None if re.match(r"c\d\d_", ref[1]) else ref[1].split("_")[0]
                if len(ref) > 3:                             # V3 : carte où sert un point de phase ambigu
                    carte = ref[3]
                r = jeu.resoudre(t[1], carte)
        elif ref[0] == "quete_phase":                        # V3 : objectif d'une phase dans la carte du don
            r = qs.position_phase(jeu, ref[1], ref[2], ref[3])
        elif ref[0] == "warp":                               # V3 : miroir (`WARP_INFO` : flag, carte, x, y, z)
            if warps is None:
                warps = miroirs(jeu)
            r = warps.get(jeu.flags.get((0, ref[1])))
            precision = "point"
        elif ref[0] == "pnj":                                # V3 : PNJ d'une carte (invité de la Suite)
            r = jeu.resoudre(ref[2], ref[1])
            precision = "point"
        elif ref[0] == "entree":                             # V3 : porte (route) de la source vers la cible
            if routes is None:
                routes = routes_vers(jeu)
            for src, zone in routes.get(ref[2], ()):
                p = jeu.points.get(src, {}).get(zone) if src == ref[1] else None
                if p is not None:
                    r = (src,) + p
                    break
        if r is None:
            continue
        c, x, z = r
        if x is None or z is None:
            out[ident] = (c, None, None, "carte")
        else:
            out[ident] = (c, x, z, precision)
    return out


# ------------------------------------------------------------------------------------------------ images
def decoder_minicarte(data: bytes, vw: int, vh: int) -> bytes:
    """IMGC -> pixels RGB (3 octets) des (vw, vh) premiers texels seulement (rognage du §2 : le reste de la texture
    est hors de la vue ; les tuiles hors du rectangle ne sont pas décodées)."""
    im = data
    fmt = im[0xA]
    w, h = struct.unpack_from("<HH", im, 0x10)
    ot = struct.unpack_from("<H", im, 0xE)[0]
    t_pad = struct.unpack_from("<I", im, 0x38)[0]
    if fmt not in L5.FORMATS_PIXELS:
        raise L5.ErreurFormat("format de pixels IMGC non pris en charge : 0x%X" % fmt)
    table = L5.decompresser(im, 0x48)
    tuiles = L5.decompresser(im, 0x48 + t_pad)
    table = struct.unpack("<%dH" % (len(table) // 2), table)
    tl = (w + 7) // 8
    vw, vh = min(vw, w), min(vh, h)
    pix = bytearray(vw * vh * 3)
    for ty in range((vh + 7) // 8):
        for tx in range((vw + 7) // 8):
            n = ty * tl + tx
            if n >= len(table) or table[n] == 0xFFFF:
                continue
            b = tuiles[table[n] * ot:(table[n] + 1) * ot]
            if len(b) < ot:
                continue
            x0, y0 = tx * 8, ty * 8
            if fmt in L5.FORMATS_ETC:
                it = ((x0 + (i & 7), y0 + (i >> 3), p) for i, p in enumerate(L5.decoder_tuile_etc(fmt, b)))
            else:
                it = ((x0 + dx, y0 + dy, L5._decoder_pixel(fmt, b, i)) for i, (dx, dy) in enumerate(L5.MORTON))
            for x, y, p in it:
                if x < vw and y < vh:
                    o = (y * vw + x) * 3
                    a = p[3] if len(p) > 3 else 255
                    if a >= 255:
                        pix[o:o + 3] = bytes(p[:3])
                    else:                                  # transparence : sur un fond sombre (comme le jeu)
                        pix[o:o + 3] = bytes((p[k] * a + 30 * (255 - a)) // 255 for k in range(3))
    return bytes(pix)


def ecrire_png_rgb(chemin: str | Path, largeur: int, hauteur: int, rgb: bytes) -> None:
    """PNG 8 bits RGB non entrelacé (lu par `tk.PhotoImage`, Tk 8.6)."""
    ligne = largeur * 3
    brut = b"".join(b"\0" + rgb[y * ligne:(y + 1) * ligne] for y in range(hauteur))

    def morceau(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    Path(chemin).write_bytes(b"\x89PNG\r\n\x1a\n" +
                             morceau(b"IHDR", struct.pack(">IIBBBBB", largeur, hauteur, 8, 2, 0, 0, 0)) +
                             morceau(b"IDAT", zlib.compress(brut, 6)) + morceau(b"IEND", b""))


def genre_carte(carte: str) -> str:
    """Genre d'après l'identifiant (`tNNN` + g extérieur / i intérieur / d donjon) ; `map_config` (MAP_INFO +2) le
    confirmerait, pas nécessaire pour ranger les cartes [S fort, §3 de l'analyse]."""
    lettre = carte[4:5]
    return {"g": "exterieur", "i": "interieur", "d": "donjon"}.get(lettre, "autre")


GRIS = "_gris.png"                          # variante « objet pas encore reçu » de chaque icône


def griser(p) -> tuple[int, int, int, int]:
    """Pixel RGBA -> gris clair (luminance rapprochée du blanc), alpha gardé."""
    y = (299 * p[0] + 587 * p[1] + 114 * p[2]) // 1000
    y = 150 + y * 90 // 255
    return (y, y, y, p[3])


def extraire_icones(jeu: Jeu, hachages: dict[str, int], dossier: Path) -> dict[str, str]:
    """Icônes 32×32 des objets (atlas d'origine de la ROM, RGBA) -> {clé: chemin relatif du PNG}. Objet absent
    d'`item_config` ou case hors de l'atlas : pas d'icône (le lanceur dessine une abréviation). Objets de voyage de la
    V3 (`ICONES_DESSINEES`, absents de la ROM d'origine) : icône dessinée en code, même dossier, même variante grise."""
    if not hachages:
        return {}
    out = {}
    dessinees = {cle for cle, h in hachages.items()
                 if ICONES_DESSINEES.get(cle) == h or ICONES_TROUSSEAU.get(cle) == h}
    if dessinees:
        (dossier / DOSSIER_ICONES).mkdir(parents=True, exist_ok=True)
    for cle in sorted(dessinees):
        dessin = DESSINS_TROUSSEAU[cle] if cle in ICONES_TROUSSEAU else OV.ICONES_LANCEUR[cle][1]
        pix = dessin(CASE_ICONE)
        rel = "%s/%s.png" % (DOSSIER_ICONES, cle)
        L5.ecrire_png(dossier / rel, CASE_ICONE, CASE_ICONE, pix)
        L5.ecrire_png(dossier / rel.replace(".png", GRIS), CASE_ICONE, CASE_ICONE, [griser(p) for p in pix])
        out[cle] = rel
    if ITEM_CONFIG not in jeu.e or ATLAS_ICONES not in jeu.e:
        return out
    cases: dict[int, tuple[int, int]] = {}
    for nom, v in _entrees(jeu.a.lire(ITEM_CONFIG)):
        if nom.startswith("ITEM_") and len(v) > 13 and isinstance(v[12], int) and isinstance(v[13], int):
            cases.setdefault(v[0], (v[12], v[13]))
    voulues = {cle: cases[h] for cle, h in hachages.items() if h in cases and cle not in dessinees}
    if not voulues:
        return out
    im = L5.Imgc(jeu.a.lire(ATLAS_ICONES))
    (dossier / DOSSIER_ICONES).mkdir(parents=True, exist_ok=True)
    for cle, (col, lig) in sorted(voulues.items()):
        x0, y0 = col * CASE_ICONE, lig * CASE_ICONE
        if x0 + CASE_ICONE > im.largeur or y0 + CASE_ICONE > im.hauteur:
            continue
        pix = [im.pixels[(y0 + y) * im.largeur + x0 + x] for y in range(CASE_ICONE) for x in range(CASE_ICONE)]
        rel = "%s/%s.png" % (DOSSIER_ICONES, cle)
        L5.ecrire_png(dossier / rel, CASE_ICONE, CASE_ICONE, pix)
        L5.ecrire_png(dossier / rel.replace(".png", GRIS), CASE_ICONE, CASE_ICONE, [griser(p) for p in pix])
        out[cle] = rel
    return out


# ------------------------------------------------------------------------------------------------ génération
class Interrompu(Exception):
    pass


def generer(rom: str | Path, dossier: str | Path, logique, *,
            progression: Callable[[float, str], object] | None = None,
            arret: threading.Event | None = None) -> Path:
    """Génère `<dossier>/cartes/` (PNG + cartes_local.json) depuis la ROM. `logique` : module `logique` de l'APWorld.
    `progression(fraction, étape)` ; `arret` : interruption propre (rien n'est remplacé). Écriture atomique du JSON en
    dernier : un fichier présent est toujours complet."""
    def avance(f, texte):
        if arret is not None and arret.is_set():
            raise Interrompu()
        if progression:
            progression(max(0.0, min(1.0, f)), texte)

    refs = references(logique)
    hachages = hachages_objets(logique)
    sortie = Path(dossier) / DOSSIER
    sortie.mkdir(parents=True, exist_ok=True)
    avance(0.0, "lecture")
    jeu = Jeu(rom)
    try:
        jeu.indexer(lambda k, n: avance(0.10 * k / max(1, n), "lecture"))
        avance(0.10, "positions")
        pos = resoudre_references(jeu, refs)
        try:                                               # boutiques (format 5) : vendeurs et entrées des bâtiments
            bout = resoudre_boutiques(jeu, logique)
        except (L5.ErreurFormat, OSError, ValueError, IndexError, KeyError, TypeError, struct.error):
            bout = {}
        par_code = boutiques_apworld(logique)
        # cartes des locations, et (format 4) cartes à Yo-kai sauvages : le lanceur y montre le Yo-kai épinglé
        cartes_utiles = sorted({p[0] for p in pos.values()} | jeu.cartes_yokai
                               | {b["cartes"][0] for b in par_code.values() if b["cartes"]}
                               | {v[0] for b in bout.values() for v in b["vendeurs"]}
                               | {e[0] for b in bout.values() for e in b["entrees"]})
        cartes: dict[str, dict] = {}
        locations: dict[str, dict] = {}
        for k, c in enumerate(cartes_utiles):
            avance(0.12 + 0.85 * k / max(1, len(cartes_utiles)), "images")
            v = jeu.vue(c)
            if v is None:
                continue
            vw, vh = v
            rgb = decoder_minicarte(jeu.a.lire(jeu.env(c)["image"]), vw, vh)
            nom = "%s.png" % c
            tmp = sortie / (nom + ".tmp")
            ecrire_png_rgb(tmp, vw, vh, rgb)
            os.replace(tmp, sortie / nom)
            cartes[c] = {"png": nom, "taille": [vw, vh], "genre": genre_carte(c)}
            m = jeu.monde(c)
            if m is not None:                              # suivi du jeu : position du joueur -> pixel (format 3)
                cartes[c]["monde"] = [round(float(v), 3) for v in m]
        for ident, (c, x, z, precision) in sorted(pos.items()):
            if c not in cartes:
                continue
            e = {"carte": c, "precision": precision}
            if precision != "carte":
                p = jeu.pixel(c, x, z)
                vw, vh = cartes[c]["taille"]
                if p is None or not (0 <= p[0] < vw and 0 <= p[1] < vh):
                    e["precision"] = "carte"
                else:
                    e["px"], e["py"] = round(p[0], 1), round(p[1], 1)
            locations[str(ident)] = e
        # boutiques : lieux en pixels (vendeur sur sa carte, portes sur les cartes d'où l'on entre), puis position de
        # chaque article = 1er lieu « vendeur » de sa boutique ; sans vendeur placé : carte seulement (comme avant)
        boutiques: dict[str, list] = {}

        def lieu(c, x, z, genre, vers=None, app=None):
            p = jeu.pixel(c, x, z) if c in cartes else None
            if p is None or not (0 <= p[0] < cartes[c]["taille"][0] and 0 <= p[1] < cartes[c]["taille"][1]):
                return None
            d = {"carte": c, "px": round(p[0], 1), "py": round(p[1], 1), "genre": genre}
            if vers:
                d["vers"] = vers
            if app is not None:                            # format 6 : variantes d'apparition du vendeur à ce point
                d["app"] = app
            return d
        for code, b in sorted(bout.items()):
            lieux = [l for l in (lieu(c, x, z, "vendeur", app=(b.get("apparitions") or {}).get((c, x, z), []))
                                 for c, x, z in b["vendeurs"]) if l]
            if not lieux:
                continue
            lieux += [l for l in (lieu(c, x, z, "entree", vers) for c, x, z, vers in b["entrees"] if vers in cartes)
                      if l]
            boutiques[code] = lieux
        for ident, ref in sorted(refs.items()):
            if ref[0] != "boutique":
                continue
            lieux = boutiques.get(ref[1])
            if lieux:
                locations[str(ident)] = {"carte": lieux[0]["carte"], "precision": "point", "px": lieux[0]["px"],
                                         "py": lieux[0]["py"], "boutique": ref[1]}
            else:
                c = ((par_code.get(ref[1]) or {}).get("cartes") or [None])[0]
                if c in cartes:
                    locations[str(ident)] = {"carte": c, "precision": "carte"}
        avance(0.98, "icones")
        try:
            icones = extraire_icones(jeu, hachages, sortie)
        except (L5.ErreurFormat, OSError, ValueError, IndexError, struct.error):
            icones = {}                                    # facultatives : abréviations dans le lanceur
        avance(1.0, "ecriture")
        # suivi du jeu (format 3) : toute carte du jeu SANS image -> carte à image à montrer à sa place ("" : aucune) ;
        # ses clés donnent aussi au lanceur les noms de toutes les cartes (le jeu publie le CRC-32 du nom)
        try:
            infos = jeu.infos_cartes()
        except (L5.ErreurFormat, OSError, ValueError, IndexError, struct.error):
            infos = {}
        parents = {c: carte_parente(c, infos, cartes) or "" for c in sorted(set(infos) | set(jeu.cartes))
                   if c not in cartes}
        d = {"format": FORMAT, "genere": datetime.datetime.now().isoformat(timespec="seconds"),
             "references": signature_references(refs, hachages), "cartes": cartes, "locations": locations,
             "icones": icones, "parents": parents, "boutiques": boutiques}
        p = sortie / NOM_FICHIER
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        os.replace(tmp, p)
        return p
    finally:
        jeu.fermer()


def charger(dossier: str | Path) -> dict | None:
    """`cartes_local.json` du dossier de données (None : absent, illisible ou d'un autre format)."""
    try:
        d = json.loads((Path(dossier) / DOSSIER / NOM_FICHIER).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(d, dict) or d.get("format") not in FORMATS_LUS or not isinstance(d.get("cartes"), dict) \
            or not isinstance(d.get("locations"), dict):
        return None
    return d


def raison_generation(dossier: str | Path, logique) -> str | None:
    """Pourquoi les cartes seraient à (re)générer, None si elles sont à jour. SEULS cas (génération ~1 min, une fois) :
    « absentes » (cartes_local.json manquant ou illisible, ou une image qu'il cite manquante), « format » (fichier d'un
    autre FORMAT : le lanceur a changé ce qu'il y met), « references » (table des références / icônes de l'APWorld
    changée : nouvelle version de l'APWorld ou de cette table). Rien d'autre n'y entre : ni la graine, ni le slot, ni
    checks.json, ni le client, ni la date : deux ouvertures successives du lanceur ne régénèrent rien. « Réparer » le
    mod force la génération (lanceur/vue.py)."""
    d = charger(dossier)
    if d is None:
        return "absentes"
    if d.get("format") != FORMAT:                           # ancien format : lu, mais à régénérer
        return "format"
    base = Path(dossier) / DOSSIER
    for c in d["cartes"].values():
        if not isinstance(c, dict) or not (base / str(c.get("png", ""))).is_file():
            return "absentes"
    if logique is None:
        return None
    try:
        ok = d.get("references") == signature_references(references(logique), hachages_objets(logique))
    except Exception:                                      # noqa: BLE001 - logique d'une autre version
        ok = False
    return None if ok else "references"


def a_jour(dossier: str | Path, logique) -> bool:
    """Fichier présent, au bon format et fait pour la table de références actuelle (APWorld compris)."""
    return raison_generation(dossier, logique) is None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--rom", required=True)
    ap.add_argument("--sortie", required=True)
    a = ap.parse_args(argv)
    sys.path.insert(0, str(ARCHIPELAGO / "client"))
    import checks_local as ck
    LQ = ck.logique_apworld()
    if LQ is None:
        print("logique de l'APWorld introuvable")
        return 1
    dernier = [-1]

    def prog(f, etape):
        pc = int(f * 100)
        if pc // 10 != dernier[0] // 10:
            print(f"  {pc:3d} % {etape}")
        dernier[0] = pc
    p = generer(a.rom, a.sortie, LQ, progression=prog)
    d = charger(a.sortie) or {}
    locs = d.get("locations", {})
    par = defaultdict(int)
    for e in locs.values():
        par[e["precision"]] += 1
    print("écrit :", p, len(d.get("cartes", {})), "cartes,", dict(par), "sur", len(references(LQ)), "locations,",
          len(d.get("icones", {})), "icônes")
    tous = boutiques_apworld(LQ)
    places = d.get("boutiques", {})
    print("boutiques placées : %d sur %d ; non placées : %s"
          % (len(places), len(tous), " ".join(sorted(set(tous) - set(places))) or "aucune"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
