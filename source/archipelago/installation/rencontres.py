"""Base locale des rencontres de Yo-kai (randomizer de Yo-kai, étape R2), générée CHEZ LE JOUEUR depuis SA ROM.

    python archipelago/installation/rencontres.py --romfs <ROM déchiffrée | dossier du RomFS> [--sortie <dossier>]
           [--rapport] [--audit] [--langues fr,engb]

Produit `yokai_local.json` dans le dossier de données du client (`%APPDATA%/ykw2-ap/`), à l'installation / réparation
du mod (lanceur) ou à la demande du client. Ce fichier contient des données tirées du jeu (hachages, niveaux, noms des
Yo-kai dans la langue du joueur) : il n'est JAMAIS versionné ni distribué (règle 6 de `CLAUDE.md`) ; il est refait
depuis la ROM du joueur. `--rapport` affiche (console seulement) les espèces fixées par raison ; `--audit` l'audit
anti-softlock complet (chaque exigence, les sources de chaque espèce exigée, boss figés ; code de sortie 1 s'il reste
un trou).

Ce que le module calcule (analyse et preuves : `docs/systemes/archipelago_rando_yokai.md` §2, §3.4 et §8) :
- les rencontres (`ENCOUNT_TABLE` / `ENCOUNT_CHARA` de `common_enc` et des `<carte>_enc_0` des `<carte>.pck`) et, pour
  chacune, qui la cite (toutes les entrées de tous les `.cfg.bin`, arguments des scripts `.xq`) ;
- les rencontres SAUVAGES (citées seulement par la loupe `WM_YOKAI_ENCOUNT` / les errants `SET_PATH_POP`, sans script
  de combat), leurs lieux (carte, méthode, condition) et l'ensemble W que le randomizer peut modifier : sauvages moins
  celles qu'une condition d'histoire ou de quête limite, qu'un script cite, dont un combattant est partagé avec une
  rencontre hors W, ou dont le point de loupe mélange W et hors W ;
- les espèces fixées F (exigence anti-softlock de l'humain, §3.4) : Yo-kai à vaincre N fois ou à posséder
  (`QUEST_NECESSARY_CONDITION` 1 et 2), réponses des Tablo-blabla, déclencheurs d'histoire ou de quête, positions
  d'objectif de quête, règles de combat, missions, conditions compilées, arguments de scripts, entrées inconnues,
  bases à plusieurs variantes sauvages, et (format 3) espèces NON RECRUTABLES en combat (taux d'amitié nul : ni
  nourriture ni amitié, `recrutable`) ou légendaires ; le domaine du mélange est D = espèces des combattants de W moins
  F (que des espèces recrutables normalement en combat sauvage, `archipelago_rando_yokai.md` §3.5) ;
- rang (E..S), tribu, n° du Médaillium (`CHARA_PARAM_INFO` v[49], par espèce), nom affiché (langues demandées) de
  chaque espèce citée ;
- pour chaque lieu sauvage, la condition décodée (notation polonaise inverse et résumé : rang de montre exigé, après-jeu,
  bornes de phase d'histoire, créneaux horaires, autres fonctions), pour le filtre « Accessibles maintenant » du tracker.

Format 2 (depuis le format 1 : `medaille` = v[49] de l'espèce au lieu de v[2] de la base, faux ; 4e élément des lieux =
condition décodée ; W, D, F identiques). Format 3 : espèces non recrutables et légendaires fixées (F et D changent,
donc l'empreinte du mélange aussi), champs `recrutable` / `rare` / `legendaire` des espèces. Format 4 (randomizer des
boss, `docs/systemes/archipelago_rando_boss.md` §9) : pour chaque rencontre à script de combat, `s` (nom du script),
`r` (règle `BTL_RULE_INFO`) et `fs` (index des fichiers qui la définissent) ; 5e élément de chaque combattant = nombre
de rencontres du même fichier qui le citent ; W, D, F et l'empreinte du mélange de Yo-kai inchangés. Les lecteurs
acceptent tous les formats (`FORMATS_LUS`, tracker). Format 5 (anti-softlock, `archipelago_rando_yokai.md` §3.4) :
`exigees` = toutes les espèces exigées par le jeu (quêtes, histoire, Tablo-blabla, requêtes, PNJ, sceaux légendaires)
et leurs SOURCES (évolution, fusion, récursivement), `exigees_boss` = celles qu'un combat de boss ne doit pas cesser
de fournir ; F gagne les raisons `source_evolution`, `source_fusion`, `sceau_legendaire` (D et l'empreinte changent).
Format 6 (périmètre « avant l'après-jeu », `archipelago_rando_yokai.md` §3.7) : les rencontres sauvages dont aucun lieu
n'est d'avant la fin (cartes d'après-jeu, réseau caché fermé à une partie normale, condition GameClear / rang S / phase
>= 11-0) sortent de W (raisons `apres_jeu`, `hors_partie`) ; Yo-kai d'évènement (`evenement` : rencontres « enc_day_* »
lancées par un dialogue et toutes les variantes de leurs espèces) jamais dans W ni D. W, D et l'empreinte changent.
Le client ne mélange les Yo-kai et les boss qu'avec une base au format 6 (une plus ancienne est régénérée depuis la
ROM).
Format 7 (mélange par rencontre, §11) : `emplacements`, `em`, `wp`, place j des combattants.
Format 10 (facilité d'amitié, `archipelago_rando_yokai.md` §15.5) : `amitie` (table `CHARA_FRIEND_RATE_INFO` : clé et
bonus d'aliment, coefficient de l'aliment préféré) et `amitie` de chaque espèce (lignes visées pour k = 0..5 Yo-kai de
même base possédés) ; lus par le tracker du lanceur seulement : W, D, F et les empreintes des mélanges inchangés.
Format 9 (loupe jamais vide, `archipelago_rando_yokai.md` §14 ; le n° 8 est laissé à la branche `ap/boss-adaptes`) :
`loupe` de chaque espèce = masque de positions `WM_YOKAI_INFO` de sa base (0 : absente, jamais montrable par la loupe),
`decors_loupe` = pour chaque emplacement de loupe, les décors [positions réelles, positions de `WM_MAP_ATTR`] des types
de point qui tirent ce `WM_YOKAI_APPEAR` (positions réelles = emplacements de Yo-kai du script `<décor>_pnt.xs`),
`decors_bases` = idem par base de loupe du mélange σ. W, D, F inchangés ; les empreintes des mélanges changent.
Format 11 (portails mystères, type de point de loupe, aliment préféré : §16, §17) : tracker seulement.
Format 12 (Yo-kai épinglé sur la carte du lanceur, `archipelago_rando_yokai.md` §18) : `pos` de chaque rencontre
sauvage = pour chaque élément de `lieux` (même ordre), les POSITIONS MONDE où la rencontre peut sortir : points de loupe
[x, z, type de point] (`OP_WATCH_POINT` de la carte dont le type et la colonne de taux tirent ce `WM_YOKAI_APPEAR`),
errants [x, z] (point d'apparition du `SET_PATH`). Tracker seulement : `lieux`, `emplacements`, W et mélanges inchangés.
Format 13 (moments des lieux, §19) : `mom` de chaque rencontre sauvage = pour chaque élément de `lieux`, un masque de
moments (1 jour sec, 2 jour pluie, 4 nuit sec, 8 nuit pluie ; 0 : jamais dans cette version du jeu) ; point de loupe de
`pos` : [x, z, type, masque du point]. Le mode d'une entrée `WM_YOKAI_WATCHMAP` est jour / nuit, les deux jeux de taux
d'un `WM_YOKAI_APPEAR` sont temps sec / pluie, les deux poids d'un `SET_PATH_POP` sont une colonne par version du jeu
[C, désassembleur]. Tracker seulement : `lieux`, `emplacements`, W et mélanges inchangés.
Format 14 (§20) : bloc `melange2` (rencontres qui ne sortent jamais hors de W), lu par la version 2 du mélange.
Format 15 (§21) : bloc `melange3` = rencontres sauvages à lieu NORMAL (hors portail mystère, qui sort dans cette
version du jeu, d'avant la fin), lu par la version 3 du mélange seulement. Les champs lus par les versions 1 et 2 sont
inchangés (une base 15 = une base 14 hors `format`, `genere` et `melange3`).
Format 16 (§22) : bloc `melange4` = espèces INVITÉES du mélange version 4 (Yo-kai du Médaillium recrutables qu'aucune
rencontre sauvage ne contient : armées du chapitre 8 et leurs proches, `INVITEES_MEDAILLIUM`), lu par la version 4
seulement. Les champs lus par les versions 1 à 3 sont inchangés (une base 16 = une base 15 hors `format`, `genere` et
`melange4`).
Format 17 (`docs/systemes/archipelago_v3_melange_partout.md`) : bloc `melange5` = W' du mélange version 5 « partout »
(lieux à condition d'histoire, coffres piégés, trains, missions du gymnase, et rencontres sauvages d'après-jeu dans le
périmètre « apres_jeu »), drapeaux « partagé » relatifs à ce W', espèces fixées, raisons d'exclusion, rencontres sans
amitié possible, lieux normaux de la version 5 ; lu par la version 5 seulement (une base 17 = une base 16 hors
`format`, `genere` et `melange5`).
Format 18 (force des boss adaptée à leur place, V3 `ap/v3-boss-force`, reprise du format 8 de la branche
`ap/boss-adaptes` ; `archipelago_rando_boss.md` §15-§16 ; après le format 17 de `ap/v3-melange-partout`) :
`stats` de chaque espèce (`CHARA_PARAM_INFO` v2..v11 : PV, For, Esp, Déf, Vit minimales puis maximales), `m` de chaque
rencontre dont les multiplicateurs de stats (v17..v21) ne valent pas tous 100, `nr` de celles qui ont des niveaux
imposés par rang (v24..v29). Lus par la force des boss seulement : W, D, F, les blocs `melange2..5` et les empreintes
des deux randomizers sont inchangés (une base 18 = une base 17 hors `format`, `genere`, `stats`, `m` et `nr`).
Format 19 (V3, lot M2a-bis, `docs/systemes/archipelago_v3_melange_partout.md` §8) : bloc `melange6` = même schéma que
`melange5`, pour la version 6 du mélange : le W' s'étend aussi aux rencontres des SPOTS de Yo-kai (`YS_YOKAI`) ; lu par
la version 6 seulement (une base 19 = une base 17 hors `format`, `genere` et `melange6`). Le format 18 est celui de la
branche `ap/v3-boss-force` (stats des espèces), non fusionnée : sauté.
Format 20 (fusion de la force des boss et du lot M2a-bis) : une base 20 porte À LA FOIS le bloc `melange6` du format 19
et les champs `stats` / `m` / `nr` du format 18 (une base 20 = une base 19 + `stats`, `m`, `nr` = une base 18 +
`melange6`, hors `format` et `genere`). Les bases 17, 18 et 19 sont à refaire (format < FORMAT) : aucune ne porte les
deux.

Bibliothèque standard seulement (module distribué avec l'installateur, comme `level5.py`).
"""
from __future__ import annotations

import argparse
import base64
import collections
import datetime
import hashlib
import json
import os
import struct
import sys
import zlib
from pathlib import Path

try:
    from . import level5 as L
except ImportError:                     # lancé comme script
    import level5 as L  # type: ignore[no-redef]

FORMAT = 20                                  # 8 : ancienne branche ap/boss-adaptes (non fusionnée) ; 17 : bloc
                                             # `melange5` (V3 M2a) ; 18 : force des boss (stats, m, nr) ; 19 : bloc
                                             # `melange6` (V3 M2a-bis) ; 20 : les deux (fusion)
FORMATS_LUS = (1, 2, 3, 4, 5, 6, 7, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20)   # formats de yokai_local.json encore lisibles (tracker) ; < FORMAT : à refaire
NOM_FICHIER = "yokai_local.json"
AUCUN = 0xFFFFFFFF
RANGS = "EDCBAS"
LANGUES_DEFAUT = ("fr", "engb")


def crc(s: str) -> int:
    return zlib.crc32(s.encode("ascii")) & 0xFFFFFFFF


# Entrées qui citent une rencontre sauvage : loupe (point de recherche) et errant (Yo-kai visible sur un chemin).
SAUVAGE = {"WM_YOKAI_ENCOUNT": "loupe", "SET_PATH_POP": "errant"}
# Format 11 (archipelago_rando_yokai.md §16) : un `<carte>_enc_pos_gate.cfg.bin` n'est chargé que lorsque la carte sert
# de SALLE D'UN PORTAIL MYSTÈRE (salle tirée au sort parmi GATE_ENTER_INFO) : ses errants sont invisibles en visite
# normale. Méthode « portail » dans `lieux` des rencontres (tracker seulement) ; `emplacements` garde « errant » : le
# mélange et ses empreintes ne changent pas.
METHODE_PORTAIL = "portail"
SUFFIXE_PORTAIL = "_enc_pos_gate.cfg.bin"


# Format 12 (positions des lieux, §18) : `<carte>_layout.bin` (même format qu'un .cfg.bin : POINT_DATA_ITEM /
# SHAPE_DATA_ITEM(id, x, y, z, …)) porte la position de presque tous les points de loupe. Il n'est lu QUE pour ces
# positions (`Analyse.lire` s'arrête là) : ses valeurs n'entrent ni dans les citations ni dans les exigences.
SUFFIXE_LAYOUT = "_layout.bin"
ENTREES_POSITION = ("SHAPE_DATA_ITEM", "POINT_DATA_ITEM")


def _coordonnee(v) -> float | None:
    """Valeur d'un .cfg.bin (entier non signé sur 32 bits ou flottant) -> coordonnée."""
    if isinstance(v, float):
        return v
    if isinstance(v, int) and not isinstance(v, bool):
        return float(v - (1 << 32) if v >= 0x80000000 else v)
    return None


# Moments où un lieu donne sa rencontre (format 13, archipelago_rando_yokai.md §19) [C, désassembleur] : masque de 4
# bits. Jour = 6 h à 18 h, nuit = 18 h à 6 h (`FUN_0040E594(3)` : 0 le jour, 3 la nuit ; mêmes bornes que
# `GetTimeNow` == 3) ; pluie = `GetWeatherNow()` != 0 (détails de météo 4 à 7 : pluie et tempête).
JOUR_SEC, JOUR_PLUIE, NUIT_SEC, NUIT_PLUIE = 1, 2, 4, 8
MOMENT_TOUJOURS = JOUR_SEC | JOUR_PLUIE | NUIT_SEC | NUIT_PLUIE
MOMENT_JAMAIS = 0
# Mode d'une entrée WM_YOKAI_WATCHMAP / WM_YOKAI_EACH_WATCHMAP (v1, octet +4 ; `FUN_0064DB1C`) : 0 = toujours,
# 1 = seulement le jour, 2 = seulement la nuit (toute autre valeur : jamais retenue).
MODE_TOUJOURS, MODE_JOUR, MODE_NUIT = 0, 1, 2
# Poids d'un SET_PATH_POP : v1, ou v2 quand `GetGameVersion()` (`FUN_00415698`) vaut 1 (`FUN_00505454`). Le binaire du
# projet passe la constante 1 (`FUN_00104780` -> `FUN_00104BC0` -> application + 0x4C58 -> sauvegarde) : colonne v2.
VERSION_JEU = 1
V_POIDS_ERRANT = 2 if VERSION_JEU == 1 else 1


def _positif(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and x > 0


def fichier_portail(nom: str) -> bool:
    """Fichier d'errants du mode portail (`<carte>_enc_pos_gate.cfg.bin`, y compris dans un `.pck`)."""
    return nom.endswith(SUFFIXE_PORTAIL)

# Fonctions de condition qui ne dépendent ni de l'histoire ni d'une quête (rang de montre du joueur, après-jeu, heure) :
# une rencontre dont tous les lieux n'ont que celles-ci reste dans W. Toute autre fonction (GetPhase, GetQuestPhase,
# GetGlobalBitFlag, GetGlobalByteFlag — posés par c01/c08_trigger —, IsHaveItem, inconnue) exclut la rencontre.
CONDITIONS_PERMISES = {crc("GetWatchRank"): "rang", crc("GameClear"): "apres_jeu", crc("GetTimeNow"): "heure"}
# Périmètre des randomizers (demande de l'humain, 2026-09-29, `archipelago_rando_yokai.md` §3.7) : seulement ce qui est
# obtenable AVANT l'après-jeu. Un lieu sauvage est « d'avant la fin » sauf si sa condition exige l'après-jeu
# (GameClear == 1), le rang de montre S (donné par la requête 28, après-jeu) ou une phase >= 11-0, ou si sa carte est
# d'après-jeu ou hors d'une partie normale (identifiants de cartes saisis à la main, preuves en §3.7) :
#   Yo-kai World t001d41-45 (Clé du Yo-kai World : quête 73, >= 11-10, rang S) [C] ; labyrinthe t103d41-56 (Clé de
#   cabane, c11_trigger n° 6) [C] ; Limbes éternelles t301-t303 (route t201g00 -> t301g00 fermée tant que qs0096 <= 2,
#   quête 96 >= 11-10, rang S) [C] ; Gera Gera Land t001d05/07/09 (aucune route dans map_route, seulement le réseau de
#   guidage des quêtes 121-123, toutes >= 11-10, rang S) [S fort] ;
#   réseau caché de San Fantastico (t121i10, t121d21-39, cartes « c ») : seule entrée t121g00 -> t121i10, porte du
#   flag 536 que seule une donnée d'un autre logiciel ouvre (`archipelago_couverture.md` §9.2) [C] : « hors_partie ».
# Une rencontre sauvage dont AUCUN lieu n'est d'avant la fin n'entre pas dans W (elle garde ses Yo-kai d'origine) ;
# une espèce qu'on ne trouve que là n'est donc jamais dans D (ni placée avant la fin, ni remplaçante).
PHASE_APRES_JEU = 110000                # GetPhase : chapitre 11 (après la victoire)
RANG_S = 5                              # GetWatchRank : 0 = E .. 5 = S
_CARTES_APRES_JEU = (
    [f"t001d{n}" for n in (41, 42, 43, 44, 45, "05", "07", "09")]
    + [f"t103d{n}" for n in range(41, 57)]
)
_PREFIXES_APRES_JEU = ("t301", "t302", "t303")
_CARTES_HORS_PARTIE = ["t121i10"] + [f"t121d{n}" for n in range(21, 40)] + [f"t121d27{s}" for s in "ab"]


def carte_hors_avant_fin(carte: str) -> str | None:
    """« apres_jeu » (carte d'après-jeu), « hors_partie » (réseau caché, fermé à une partie normale) ou None."""
    c = carte or ""
    if c in _CARTES_APRES_JEU or c.startswith(_PREFIXES_APRES_JEU):
        return "apres_jeu"
    # cartes « c » du réseau caché (t101d02c, t121d03c…) : toutes de la forme tNNNdNNc
    if c in _CARTES_HORS_PARTIE or (len(c) == 8 and c[4] == "d" and c.endswith("c")):
        return "hors_partie"
    return None


def lieu_hors_avant_fin(carte: str, condition: dict | None) -> str | None:
    """Raison pour laquelle un lieu sauvage (carte, condition décodée `condition_lieu`) n'est PAS d'avant la fin
    (« apres_jeu », « hors_partie »), ou None s'il l'est."""
    r = carte_hors_avant_fin(carte)
    if r:
        return r
    c = condition or {}
    ph = c.get("phase") or [None, None]
    if c.get("apres_jeu") is True or c.get("rang", 0) >= RANG_S or (ph[0] is not None and ph[0] >= PHASE_APRES_JEU):
        return "apres_jeu"
    return None


# Yo-kai d'évènement (demande de l'humain, 2026-09-29, `archipelago_amis_criminels.md` §7) : combats du jour lancés par
# un dialogue (commande 0x352C avec une rencontre « enc_day_* »), liés à un objet ou non ; ni leurs espèces (toutes les
# variantes CHARA_PARAM de leur base) ni ces rencontres ne sont dans le randomizer (raison « evenement »). Détectés
# depuis les scripts de la ROM ; en plus, bases saisies à la main (hachages CHARA_BASE, règle 6) des Yo-kai d'évènement
# liés à un objet-clé, dont Darknyan (combat de la quête 124, sans rencontre « enc_day_* ») :
PREFIXE_EVENEMENT = "enc_day_"
LANCER_COMBAT = 0x352C                  # commande de script : lancer le combat (nom de rencontre, arène)
BASES_EVENEMENT = frozenset((
    0x3175B841, 0x0BDD8D1B, 0xB361EA7E, 0xA1D44590, 0x196822F5, 0x84BF1A4C,   # 6 robots (Rouages)
    0x62047527, 0x226C131D,                                                   # Jetnyan, Boucanyan
    0x3C037D29, 0x25184C68, 0x0E351FAB, 0x172E2EEA, 0x586FB82D, 0x4174896C,   # 6 fruits (Graines)
    0x28D2CA9F, 0x3A676571, 0x82DB0214,                                       # Robonyan F, Sailornyan, Maskonyan
    0xAD0E844A, 0x15B2E32F,                                                   # Ultramax N, Ultramax K
    0xB505F226, 0x431B6AC4,                                                   # Darknyan, Hovernyan (après-jeu)
))

NOMS_FONCTIONS = {crc(n): n for n in (
    "GetGlobalBitFlag", "GetGlobalByteFlag", "IsHaveItem", "GetChapter", "GetPhase", "GetQuestPhase", "SetQuestPhase",
    "GetTempBitFlag", "GetPlayerVarID", "GameClear", "GetTBoxFlag", "GetWatchRank", "GetTimeNow",
    "CheckQuestNecessaryCondition", "YS_IsFind_Yokai", "GetInsectCompNum", "GetFishCompNum",
    # fonctions de condition dont un argument est un Yo-kai (audit anti-softlock, format 5)
    "InPartyMember", "GetPartyInNum", "GetGlobalCharaCompFlagAnyOneCRC", "YS_CheckYokaiBaseID", "YS_SetCurrentInfo",
    "IsNpcUtil", "Guest_MatchChara")}

# Entrées de .cfg.bin qui, si elles citent une espèce sauvage (hachage CHARA_PARAM ou CHARA_BASE), la FIXENT : elle ne
# change pas et ne remplace aucune autre espèce (§3.4, exigence de l'humain : aucun softlock).
RAISONS_ENTREES = {
    "TERRITORY_INFO": "tablo",                   # réponse d'un Tablo-blabla (il faut posséder le Yo-kai et l'appeler)
    "DATA_ITEM": "declencheur",                  # déclencheur d'histoire / de quête (type 11 : Yo-kai à appeler)
    "QUEST_PURPOSE_POS": "quete_position",       # position d'objectif d'une quête
    "BTL_RULE_INFO_RULE_DATA": "regle_combat",   # règle de combat spéciale
}
# QUEST_NECESSARY_CONDITION(type, hachage, nombre) : 1 = vaincre N fois (ex. « Pas le temps de pêcher ! », n° 99,
# trois Pachycoul, donne la Canne à pêche), 2 = posséder / rapporter ; 3 objet, 4 rencontre, 8 phase, 9 quête.
RAISONS_QNC = {1: "quete_vaincre", 2: "quete_posseder"}
# exclusions de W propres à la base de loupe du mélange σ : levées pour W' (mélange par rencontre, §11)
RAISONS_W_PRIME = frozenset(("premier_partage", "point_mixte"))
# Mélange version 2 (format 14, §20) : une rencontre sauvage dont AUCUN lieu ne sort jamais dans cette version du jeu
# (tous ses `mom` nuls : errants dont tous les SET_PATH_POP ont un poids nul dans la colonne de la version, §19.4) est
# exclue de W et de W' ; elle n'est ni un emplacement de tirage, ni un emplacement d'origine à garder, ni une source.
RAISON_MORTE = "jamais_version"
# Mélange version 4 (§22, décision de l'humain du 2026-10-05) : n° du Médaillium des Yo-kai qu'aucune voie ne permet
# de recruter dans une partie normale (combats d'histoire du chapitre 8, requête 73, tournoi : tous sous la règle « pas
# d'amitié » ; `docs/systemes/archipelago_yokai_evenement.md` §4.5). Ils entrent dans le réservoir du mélange comme
# espèces INVITÉES, chacune seulement si la ROM du joueur confirme les critères d'`Analyse.invitees` (sinon écartée,
# avec sa raison dans le bloc `melange4`).
INVITEES_MEDAILLIUM = (50, 67, 88, 89, 90, 91, 105, 106, 134, 207, 208, 209, 210, 227, 298, 299)
# Mélange version 5 (« partout », décisions de l'humain du 2026-10-17, `archipelago_v3_melange_partout.md`) : W' s'étend
# à toutes les rencontres de Yo-kai qu'on peut mettre dans l'équipe, sauf les Yo-kai d'évènement :
# - rencontres sauvages dont les lieux n'ont que des conditions d'HISTOIRE : `GetPhase` (et rang de montre, heure,
#   après-jeu), ou un octet global d'état d'histoire de FLAGS_HISTOIRE5 (écrit seulement par les déclencheurs de
#   chapitre : `c01_trigger` phases 9 / 10, `c08_trigger` phases 6 à 9 [C, xq_cherche --hash]) ; une condition de quête
#   (`GetQuestPhase`, `IsHaveItem`…) ou un autre flag reste fixe (Yo-kai d'une requête à un lieu précis) ;
# - rencontres NON sauvages citées par une seule catégorie de AJOUTS5 : coffres piégés (`ITABLE_DATA_MORE` seul : les
#   `DATA_ITEM+ITABLE_DATA_MORE` sont scénarisés), trains (`TRAIN_EVENT_DATA`), missions du gymnase
#   (lignes `_DATA` de GYM_MISSION_BATTLE_ENC_INFO) ; ni script, ni condition de quête, un seul fichier ;
# - rencontres sauvages d'après-jeu, seulement dans le périmètre « apres_jeu » (graine avec l'après-jeu activé) ;
# - JAMAIS une rencontre dont la règle de combat (`ENCOUNT_TABLE` v[22] -> `BTL_RULE_INFO`) a l'entrée type 3 / n° 5
#   « pas d'amitié » (drapeau 0x4000, `FUN_00560CA8` / `FUN_0065ED4C`) : tournois, Yo-criminels, et 58 rencontres
#   sauvages scénarisées (siège du chapitre 10…) : on ne peut pas y recruter, un Yo-kai placé là serait perdu.
# Le bloc `melange5` de la base porte les deux périmètres ; les champs lus par les versions 1 à 4 ne changent pas.
FLAGS_HISTOIRE5 = frozenset((0xDF0B0383, 0xA6D7BB27))
FONCTIONS_LIEU5 = frozenset(("GetWatchRank", "GameClear", "GetTimeNow", "GetPhase"))
AJOUTS5 = {"ITABLE_DATA_MORE": "coffre", "TRAIN_EVENT_DATA": "train", "GYM_MISSION_BATTLE_ENC_" "INFO_DATA": "gymnase"}
PERIMETRES5 = ("base", "apres_jeu")
# Mélange version 6 (V3, lot M2a-bis, décisions de l'humain du 2026-10-18, `archipelago_v3_melange_partout.md` §8) : la
# version 5 + les rencontres des SPOTS de Yo-kai (`YS_YOKAI` v[2] : combat lancé par le système des spots, scripts
# `ev77_*` sans espèce ni don ; le Yo-kai MONTRÉ au spot et ses dialogues viennent de `YS_YOKAI` v[0], jamais changé :
# dialogue et combat peuvent ne plus correspondre, accepté). Une rencontre de spot est aussi le nom d'un flag
# (`FLAG_INFO` du même hachage : « combat du spot gagné », posé par le jeu à la victoire quel que soit le Yo-kai) :
# cette citation-là ne l'exclut pas. Mêmes exclusions que les autres catégories (script, condition de quête, plusieurs
# fichiers, règle « pas d'amitié », évènement).
AJOUTS6 = dict(AJOUTS5, YS_YOKAI="spot")
CITATIONS_NEUTRES_SPOT6 = frozenset(("FLAG_INFO",))
REGLE_SANS_AMITIE = (3, 5)              # BTL_RULE_INFO_RULE_DATA : (v[0], v[12]) = type 3, n° 5 -> drapeau 0x4000
# Entrées qui citent des espèces sans rien exiger du joueur (catalogues, modèles, PNJ, dialogues de PNJ, fusions,
# évolutions, Crank-a-kai, Yo-kai des spots, points spéciaux, courses, Terreur) : ignorées. Toute entrée ABSENTE des
# deux listes qui cite une espèce sauvage la fixe (raison « entree:<nom> ») : une donnée nouvelle ou mal comprise ne
# peut pas ouvrir un softlock.
ENTREES_SANS_EXIGENCE = frozenset((
    "ENCOUNT_TABLE", "ENCOUNT_CHARA", "CHARA_PARAM_INFO", "CHARA_BASE_YOKAI_INFO", "CHARA_BASE_INFO",
    "CHARA_SCALE_INFO", "CHARA_COLLISION_INFO", "CHARA_SAME_KIND_INFO", "CHARA_EVOLVE_INFO", "COMBINE_INFO",
    "YOUKAI_SUMMON_INFO", "SOUL_NORMAL_CONFIG_INFO_DATA", "ENC_ACT_PARAM_INFO", "EFFECT_PLACING_CONFIG",
    "FACE_YOKAI", "FACE_YOKAI_OFS", "TEXT_WASHA_MAP", "NPC_BASE", "NPC_PRESET", "TALK_INFO", "BASE_TALK_INFO",
    "WM_YOKAI_APPEAR", "WM_YOKAI_INFO", "CAPSULE_ITEM_INFO", "YS_YOKAI", "OP_WATCH_POINT", "LEGEND_DATA_CONFIG",
    "ITEM_EQUIP_COND_CHARA", "RACE_BARRIER_PARAM", "RACE_INFO_DATA", "ORGE_CHARA_PARAM", "ORGE_PARA_PARAM",
    "ORGE_HELP_PARAM", "BTL_YOKAI_FAMILY_INFO", "BATTLE_COMMAND_STEFF_INFO",
    # jeu de la caméra (face_config : FACE_FEATURE traits du visage, FACE_MISSION(type, base, 0, objet, nombre)
    # récompenses) : facultatif, sans lien avec l'histoire ni les quêtes
    "FACE_MISSION", "FACE_PRESENT",
    # format 5 : catalogues de modèles et d'effets (parties de boss, nœuds d'effets, parties de modèle), surveillants de
    # la Terreur : aucune exigence (ne citaient aucune espèce de W : F inchangé)
    # (nom de clé coupé en deux littéraux : aucune fenêtre de 32 octets de code.bin dans le paquet, fabriquer_paquet.py)
    "BOSS_PARTS_INFO", "BOSS_PARTS_INFO_BEGIN", "EFFECT_PLACING_CONFIG" "_PARTS_NODE_MAPPING", "CHARA_BASE_PART",
    "ORGE_CONFIG",
))


# Recrutement en combat [C, archipelago_rando_yokai.md §3.5] : un ennemi peut devenir ami (FUN_00659cd4), et la
# nourriture peut être lancée (FUN_00566014 : au moins un ennemi recrutable), si FUN_0065ed4c renvoie 0 : la ligne n de
# CHARA_FRIEND_RATE_INFO existe et a une clé (u16 +0) non nulle, avec n = quartet k du mot CHARA_PARAM_INFO v[31]
# (+0x20 de l'enregistrement natif, FUN_006521e0) et k = nombre de Yo-kai de même base déjà possédés (FUN_004100dc).
# Une espèce NON RECRUTABLE a un quartet 0 qui vise la ligne 0 (clé 0) : elle refuse la nourriture et ne devient jamais
# amie après un combat (ex. Shogunyan : v[31] = 0 pour ses 4 CHARA_PARAM). Critère retenu : premier recrutement (k = 0).
V_AMITIE = 31                           # CHARA_PARAM_INFO : quartets des lignes de taux d'amitié
V_STATS = 2                             # CHARA_PARAM_INFO : v2..v6 stats minimales, v7..v11 maximales (format 18)
# Format 10 (affichage de la facilité d'amitié dans le lanceur, archipelago_rando_yokai.md §15.5) : coefficient du bonus
# d'aliment quand sa catégorie est la préférée de la base (`battle_variable_config`, VALUE_INFO(hachage, flottant))
P_ALIMENT_PREFERE = 0xD854C36D
NB_QUARTETS_AMITIE = 6                  # k = 0..5 Yo-kai de même base déjà possédés (k > 5 : jamais ami)
V_ALIMENT = 17                          # CHARA_BASE_YOKAI_INFO : catégorie d'aliment préférée (octet +28, §15.1) ;
                                        # = champ 3 des ITEM_CONSUME de type 10 (1..19 ; 0 : aucune)
V_RARE, V_LEGENDAIRE = 15, 16           # CHARA_BASE_YOKAI_INFO : bits 4 / 5 de l'octet +0x18 (FUN_004bb9ec)
V_EVOLUTION = 48                        # CHARA_PARAM_INFO : n° de l'évolution dans CHARA_EVOLVE_INFO(niveau, espèce)

# ------------------------------------------------------------------------------------------------ exigences (format 5)
# Anti-softlock (demande de l'humain, 2026-09-29, archipelago_rando_yokai.md §3.4) : tout Yo-kai qu'une quête,
# l'histoire, un Tablo-blabla, une requête, un PNJ ou un sceau exige de posséder, vaincre, rencontrer ou appeler doit
# rester obtenable EXACTEMENT comme dans le jeu d'origine, ainsi que ses SOURCES (espèce qui évolue vers lui, ingrédients
# d'une fusion qui le donne, récursivement). Catégories d'exigences (1er élément des triplets de `Analyse.exigences`) :
#   quete_vaincre / quete_posseder     QUEST_NECESSARY_CONDITION types 1 / 2 (base)
#   quete_rencontre                    QUEST_NECESSARY_CONDITION type 4 (rencontre : jamais dans W ; hachage de boss
#                                      inchangé par le mélange des boss) — ses combattants ne sont pas « exigés »
#   tablo, declencheur, quete_position, regle_combat, entree:<nom>   valeur d'une entrée de .cfg.bin (RAISONS_ENTREES
#                                      ou entrée inconnue)
#   condition:<fonction>               nom cité par une condition compilée (InPartyMember, GetPartyInNum,
#                                      GetGlobalCharaCompFlagAnyOneCRC, YS_CheckYokaiBaseID, Guest_MatchChara… ;
#                                      « - » : hors de tout appel)
#   script:<instruction>               argument d'une instruction de script .xq autre qu'un don
#   sceau_legendaire                   espèce d'un sceau du Médaillium (LEGEND_DATA_CONFIG) : la posséder débloque le
#                                      légendaire
# Sources ajoutées par la fermeture : source_evolution (espèce qui évolue vers une espèce exigée), source_fusion
# (ingrédient Yo-kai d'une fusion qui donne une espèce exigée).
QNC_EXIGENCES = {1: "quete_vaincre", 2: "quete_posseder", 4: "quete_rencontre"}
# Exigences FAIBLES : une mention qui n'exige ni de posséder ni de vaincre l'espèce (repère d'objectif de quête,
# Yo-kai révélé à la loupe par un déclencheur de type 11 — ex. boss avant leur combat —, système des spots). Elles
# fixent quand même l'espèce sauvage (prudence, comme avant), mais ne figent pas un boss (voir `exigences_boss`).
CATEGORIES_FAIBLES = frozenset(("quete_position", "declencheur", "quete_rencontre", "condition:YS_CheckYokaiBaseID",
                                "condition:YS_SetCurrentInfo", "condition:YS_IsFind_Yokai"))
# Un boss (mélange des boss) est figé si l'une de ses espèces est exigée fortement ET recrutable après le combat (le
# combat est une source d'ami), ou quelle que soit sa recrutabilité pour ces catégories (le combat lui-même compte).
CATEGORIES_BOSS_TOUJOURS = frozenset(("quete_vaincre", "regle_combat"))
RAISONS_FERMETURE = ("source_evolution", "source_fusion", "sceau_legendaire")


def recrutable_en_combat(amitie, lignes: list[int]) -> bool:
    """Recrutement possible au premier combat : `amitie` = CHARA_PARAM_INFO v[31] (None : pas de CHARA_PARAM, refus du
    jeu), `lignes` = clés (1er champ) des lignes de CHARA_FRIEND_RATE_INFO dans l'ordre du fichier."""
    if not isinstance(amitie, int):
        return False
    n = amitie & 0xF
    return n < len(lignes) and lignes[n] != 0


# ------------------------------------------------------------------------------------- décors de loupe
# Écran de loupe [C, archipelago_rando_yokai.md §13.2 et §14.1] : le loop charge `data/res/map/watchmap/<décor>_pnt.xs`
# (chaîne 0x008075B0 ; <décor> = nom dont le CRC-32 est le type du point, clé de WM_MAP_ATTR). Ce script XSCR crée les
# emplacements : instruction 0x044C (nombres par genre), 0x044D = un emplacement de YO-KAI (commande native
# FUN_0046E2B4 : genre 0 en +4, POSITION = 2e argument en +5). FUN_00472B28 ne crée le Yo-kai que si le masque
# WM_YOKAI_INFO de sa base a le bit d'une de ces positions.
DOSSIER_DECORS = "/res/map/watchmap/"
SUFFIXE_DECOR = "_pnt.xs"
OP_EMPLACEMENT_YOKAI = 0x044D


def decor_de_script(chemin: str) -> str | None:
    """Nom du décor d'un script `…/res/map/watchmap/<décor>_pnt.xs`, None pour un autre fichier."""
    if not chemin.endswith(SUFFIXE_DECOR) or DOSSIER_DECORS not in "/" + chemin:
        return None
    return chemin.rsplit("/", 1)[-1][:-len(SUFFIXE_DECOR)]


def positions_yokai_xs(data: bytes) -> int | None:
    """Masque des positions de Yo-kai d'un script de décor XSCR (bit p pour chaque instruction 0x044D de position p),
    None si le fichier n'est pas lisible. En-tête : « XSCR », u16 instructions, u16 offset / 4, u32 arguments, u32
    offset / 4 ; deux blocs compressés Level-5 : instructions {u16 opcode, u16 nombre, u32 1er argument} et arguments
    {u8 type (1 = entier), 3 octets, 4 octets de valeur}."""
    try:
        if data[:4] != b"XSCR":
            return None
        ni, oi, na, oa = struct.unpack_from("<HHII", data, 4)
        ins, args = L.decompresser(data, 4 * oi), L.decompresser(data, 4 * oa)
        masque = 0
        for i in range(ni):
            op, n, a = struct.unpack_from("<HHI", ins, 8 * i)
            if op != OP_EMPLACEMENT_YOKAI:
                continue
            if n < 2 or a + 1 >= na or args[8 * (a + 1)] != 1:
                return None
            pos = struct.unpack_from("<i", args, 8 * (a + 1) + 4)[0]
            if not 0 <= pos < 16:
                return None
            masque |= 1 << pos
        return masque
    except (L.ErreurFormat, struct.error, IndexError, ValueError):
        return None


# ------------------------------------------------------------------------------------------------ formats
class CfgBin:
    """Lecteur minimal des .cfg.bin Level-5 (T2B) : entrées (nom de clé, valeurs). Voir tools/romfs/cfgbin.py."""
    __slots__ = ("entrees",)

    def __init__(self, data: bytes):
        nb, off_ch, taille_ch, _n = struct.unpack_from("<4I", data, 0)
        chaines = data[off_ch:off_ch + taille_ch]
        noms = {}
        k = (off_ch + taille_ch + 15) & ~15
        if k + 16 <= len(data):
            _t, nk, off_n, taille_n = struct.unpack_from("<4I", data, k)
            tn = data[k + off_n:k + off_n + taille_n]
            for i in range(nk):
                c, o = struct.unpack_from("<2I", data, k + 16 + 8 * i)
                if o < len(tn):
                    noms[c] = tn[o:tn.index(b"\0", o)].decode("ascii", "replace")
        self.entrees = []
        p = 0x10
        for _ in range(nb):
            cle, n = struct.unpack_from("<IB", data, p)
            p += 5
            nt = (n + 3) // 4
            ot = data[p:p + nt]
            p = (p + nt + 3) & ~3
            vals = []
            for i in range(n):
                t = (ot[i // 4] >> (2 * (i % 4))) & 3
                if t == 0:
                    o = struct.unpack_from("<i", data, p)[0]
                    if o < 0:
                        vals.append(None)
                    else:
                        fin = chaines.find(b"\0", o)
                        vals.append(chaines[o:fin if fin >= 0 else len(chaines)].decode("utf-8", "replace"))
                elif t == 2:
                    vals.append(struct.unpack_from("<f", data, p)[0])
                else:
                    vals.append(struct.unpack_from("<I", data, p)[0])
                p += 4
            self.entrees.append((noms.get(cle, "%08X" % cle), vals))


# Fonctions de script qui DONNENT un Yo-kai (arguments : hachage du Yo-kai…) : le Yo-kai est donné par l'histoire ou
# la quête, quel que soit le mélange des rencontres sauvages ; ces arguments ne fixent pas l'espèce (raison « don »,
# informative). Tout autre argument de script égal à une espèce la fixe.
FONCTIONS_DON = frozenset(crc(n) for n in ("AddPartyEx", "AddParty"))
# Sources « don de script » pour l'audit (format 5) : AddPartyEx2 donne aussi un Yo-kai, mais ses arguments restent
# comptés comme citations (ils fixent l'espèce, comme avant : prudence, empreinte inchangée sur ce point).
FONCTIONS_DON_SOURCES = FONCTIONS_DON | {crc("AddPartyEx2")}
APPEL_FONCTION = 0x0014      # instruction « appel de fonction de script » : 1er argument = crc32 du nom
# Noms de fonctions de script qui reçoivent un Yo-kai (audit, affichage seulement ; les autres : crc32 en hexadécimal)
NOMS_FONCTIONS_SCRIPT = {crc(n): n for n in (
    "AddPartyEx", "AddParty", "AddPartyEx2", "AssignCharacterBaseLQ4", "PlayCharge_Ex", "Menu_MedalIconImgSetupByCRC")}


def instructions_xq(data: bytes):
    """Instructions d'un script XQ32 : (clé, [(type, valeur)] des arguments), clé = « fn:<nom> » pour un appel de
    fonction de script (1er argument = crc32 du nom), « op:0x<type> » sinon. Format : tools/romfs/xq32.py (instruction
    de 12 octets : u16 premier argument, u16 nombre, u16 retour, u16 type ; argument de 8 octets : u32 type, u32
    valeur ; type 24 = chaîne)."""
    if data[:4] != b"XQ32":
        return
    h = struct.unpack_from("<10H", data, 4)
    offs = sorted([h[1] << 2, h[2] << 2, h[4] << 2, h[6] << 2, h[9] << 2, len(data)])

    def table(off):
        return L.decompresser(data[:offs[offs.index(off) + 1]], off)
    try:
        ti, ta = table(h[4] << 2), table(h[6] << 2)
    except (L.ErreurFormat, IndexError, struct.error, zlib.error, ValueError):
        return
    args = [struct.unpack_from("<II", ta, 8 * k) for k in range(min(h[7], len(ta) // 8))]
    for k in range(min(h[5], len(ti) // 12)):
        a0, n, _r, typ = struct.unpack_from("<4H", ti, 12 * k)
        a = args[a0:a0 + n]
        if typ == APPEL_FONCTION and a:
            cle = "fn:" + NOMS_FONCTIONS_SCRIPT.get(a[0][1], "%08X" % a[0][1])
        else:
            cle = "op:0x%04X" % typ
        yield cle, a


def valeurs_xq(data: bytes, detail: dict | None = None,
               dons_sources: set | None = None) -> tuple[set[int], set[int]]:
    """Arguments d'instructions d'un script XQ32 (sauf les chaînes, type 24) : (valeurs citées, valeurs passées à une
    fonction qui donne un Yo-kai, FONCTIONS_DON). Facultatifs (audit, format 5) : `detail` = valeur (> 0xFFFF) ->
    {clé d'instruction} des citations ; `dons_sources` reçoit les valeurs passées à FONCTIONS_DON_SOURCES."""
    cites, dons = set(), set()
    for cle, a in instructions_xq(data):
        fn = a[0][1] if cle.startswith("fn:") else None
        don = fn in FONCTIONS_DON
        for t, v in a:
            if t != 24:
                (dons if don else cites).add(v)
                if not don and detail is not None and v > 0xFFFF and v != fn:
                    detail.setdefault(v, set()).add(cle)
                if dons_sources is not None and fn in FONCTIONS_DON_SOURCES and v != fn:
                    dons_sources.add(v)
    return cites, dons


def combats_lances_xq(data: bytes) -> set[str]:
    """Noms des rencontres lancées par la commande 0x352C d'un script XQ32 (1er argument, chaîne : type 24 = offset
    dans la table des chaînes, u16 +0x16 de l'en-tête >> 2, tools/romfs/xq32.py)."""
    if data[:4] != b"XQ32":
        return set()
    h = struct.unpack_from("<10H", data, 4)
    offs = sorted([h[1] << 2, h[2] << 2, h[4] << 2, h[6] << 2, h[9] << 2, len(data)])

    def table(off):
        return L.decompresser(data[:offs[offs.index(off) + 1]], off)
    try:
        ti, ta, tc = table(h[4] << 2), table(h[6] << 2), table(h[9] << 2)
    except (L.ErreurFormat, IndexError, struct.error, zlib.error, ValueError):
        return set()
    out = set()
    for k in range(min(h[5], len(ti) // 12)):
        a0, n, _r, typ = struct.unpack_from("<4H", ti, 12 * k)
        if typ != LANCER_COMBAT or n < 1 or 8 * (a0 + 1) > len(ta):
            continue
        t, v = struct.unpack_from("<II", ta, 8 * a0)
        if t == 24 and v < len(tc):
            fin = tc.find(b"\0", v)
            out.add(tc[v:fin if fin >= 0 else len(tc)].decode("utf-8", "replace"))
    return out


def jetons_condition(texte) -> tuple[set[int], set[int]] | None:
    """Condition compilée (base64 « AAAA… ») -> (fonctions appelées, hachages cités) ; None si ce n'en est pas une.
    Jetons (docs/systemes/archipelago_objets_cles.md §2) : 0x35 appel (crc32 BE + 5 octets), 0x34 nom (crc32 BE),
    0x32 entier (BE) ; autres : opérateurs d'un octet."""
    if not (isinstance(texte, str) and texte.startswith("AAAA")):
        return None
    try:
        b = base64.b64decode(texte)[4:]
    except (ValueError, TypeError):
        return set(), set()
    fonctions, noms = set(), set()
    i = 0
    while i < len(b):
        c = b[i]
        if c in (0x34, 0x35) and i + 5 <= len(b):
            v = struct.unpack(">I", b[i + 1:i + 5])[0]
            (fonctions if c == 0x35 else noms).add(v)
            i += 10 if c == 0x35 else 5
        elif c == 0x32 and i + 5 <= len(b):
            i += 5
        else:
            i += 1
    return fonctions, noms


# Conditions compilées, décodage complet [C : évaluateur FUN_005B8D68 et ses comparateurs, `archipelago_rando_yokai.md`
# §10.6] : octets 0..3 nuls, octet 4 = taille du reste, octet 5 (non utilisé ici), puis des jetons en notation
# polonaise inverse :
#   0x35 <crc32 BE de la fonction> <u16 BE L> <L octets : u8 nombre d'arguments, puis par argument
#        0x28 <u16 BE taille> <u8, jetons de l'argument>>        appel (ex. GetGlobalByteFlag(nom))
#   0x34 <crc32 BE> nom (flag, objet, quête) ; 0x32 <s32 BE> entier ;
#   opérateurs (cas de l'évaluateur -> comparateur) : 0x6E « < » (FUN_005B7B5C), 0x6F « <= » (FUN_005B7868),
#   0x70 « > » (FUN_005B76B4), 0x71 « >= » (FUN_005B7500), 0x78 « == » (FUN_005B734C), 0x79 « != »,
#   0x8F « et » (FUN_005B6BB0), 0x90 « ou » (FUN_005B837C) ; « a b OP » = a OP b.
OPERATEURS = {0x6E: "<", 0x6F: "<=", 0x70: ">", 0x71: ">=", 0x78: "==", 0x79: "!=", 0x8F: "et", 0x90: "ou"}
COMPARAISONS = ("<", "<=", ">", ">=", "==", "!=")
_INVERSE = {"<": ">", "<=": ">=", ">": "<", ">=": "<=", "==": "==", "!=": "!="}
FONCTIONS_RESUMEES = ("GetWatchRank", "GameClear", "GetPhase", "GetTimeNow")


def _jetons(b: bytes, i: int, fin: int) -> list:
    out: list = []
    while i < fin:
        c = b[i]
        if c == 0x35 and i + 7 <= fin:
            f = struct.unpack(">I", b[i + 1:i + 5])[0]
            n = struct.unpack(">H", b[i + 5:i + 7])[0]
            out.append(["f", NOMS_FONCTIONS.get(f, "%08X" % f), _arguments(b, i + 7, min(i + 7 + n, fin))])
            i += 7 + n
        elif c in (0x32, 0x34) and i + 5 <= fin:
            v = struct.unpack(">i" if c == 0x32 else ">I", b[i + 1:i + 5])[0]
            out.append(["i" if c == 0x32 else "n", v])
            i += 5
        elif c in OPERATEURS:
            out.append(["o", OPERATEURS[c]])
            i += 1
        else:
            out.append(["?", "%02X" % c])
            i += 1
    return out


def _arguments(b: bytes, i: int, fin: int) -> list:
    args: list = []
    if i >= fin:
        return args
    nombre, i = b[i], i + 1
    for _ in range(nombre):
        if i + 3 > fin or b[i] != 0x28:
            args.append([["?", "arg"]])
            break
        n = struct.unpack(">H", b[i + 1:i + 3])[0]
        args.append(_jetons(b, i + 4, min(i + 3 + n, fin)))
        i += 3 + n
    return args


def decoder_condition(texte) -> list | None:
    """Condition compilée (base64 « AAAA… ») -> jetons en notation polonaise inverse : ["f", fonction, [arguments]],
    ["i", entier], ["n", hachage], ["o", opérateur], ["?", octet inconnu] ; None si ce n'est pas une condition."""
    if not (isinstance(texte, str) and texte.startswith("AAAA")):
        return None
    try:
        b = base64.b64decode(texte)
    except (ValueError, TypeError):
        return [["?", "base64"]]
    return _jetons(b, 6, len(b)) if len(b) > 6 else []


def resumer_condition(rpn: list) -> dict:
    """Résumé lisible d'une condition décodée : rang de montre exigé (« rang » : minimum, E = 0 … S = 5), après-jeu
    (« apres_jeu » : True exigé, False interdit), bornes de phase d'histoire (« phase » : [min, max], chapitre × 10000
    + pas, None = sans borne), créneaux horaires (« heure » : valeurs de GetTimeNow acceptées), autres fonctions
    (« autres » : histoire, quête, objet… ; « ? » : jeton ou forme inconnus). Descriptif seulement (une condition en
    « ou » n'y est pas exacte) : le tracker évalue les jetons eux-mêmes (`lanceur/tracker.evaluer`)."""
    r: dict = {}
    autres: set = set()
    pile: list = []
    for j in rpn:
        if j[0] != "o":
            if j[0] == "?":
                autres.add("?")
            elif j[0] == "f" and j[1] not in FONCTIONS_RESUMEES:
                autres.add(j[1])
            pile.append(j)
            continue
        if len(pile) < 2:
            autres.add("?")
            pile = [["c"]]
            continue
        b, a = pile.pop(), pile.pop()
        pile.append(["c"])
        if j[1] not in COMPARAISONS:
            continue
        if a[0] == "f" and b[0] == "i":
            nom, op, v = a[1], j[1], b[1]
        elif b[0] == "f" and a[0] == "i":
            nom, op, v = b[1], _INVERSE[j[1]], a[1]
        else:
            continue
        if nom == "GetWatchRank" and op in (">=", ">", "=="):
            r["rang"] = max(r.get("rang", 0), v + (op == ">"))
        elif nom == "GameClear" and op in ("==", "!="):
            r["apres_jeu"] = (v != 0) == (op == "==")
        elif nom == "GetPhase":
            lo, hi = r.get("phase", [None, None])
            if op in (">=", ">", "=="):
                lo = max(lo if lo is not None else v, v + (op == ">"))
            if op in ("<=", "<", "=="):
                hi = min(hi if hi is not None else v, v - (op == "<"))
            r["phase"] = [lo, hi]
        elif nom == "GetTimeNow" and op == "==":
            r["heure"] = sorted(set(r.get("heure", [])) | {v})
        elif nom in FONCTIONS_RESUMEES:
            autres.add(nom)
    if rpn and len(pile) != 1:
        autres.add("?")
    if autres:
        r["autres"] = sorted(autres)
    return r


def condition_lieu(*conds) -> dict | None:
    """Condition d'un lieu (loupe : celle du point ; errant : celle du Yo-kai ET celle de son chemin), décodée :
    {"e": jetons (conjonction des conditions présentes), + résumé} ; None s'il n'y en a aucune."""
    rpn: list = []
    for c in conds:
        j = decoder_condition(c)
        if not j:
            continue
        rpn = j if not rpn else rpn + j + [["o", "et"]]
    if not rpn:
        return None
    return {"e": rpn, **resumer_condition(rpn)}


def condition_portail(conds_lieu, salles) -> dict | None:
    """Condition d'un lieu de portail : celle du lieu (Yo-kai ET chemin) ET celle de la salle. `salles` = conditions
    compilées des entrées GATE_ENTER_INFO de la carte (None : entrée sans condition) ; plusieurs entrées : « ou » ;
    une entrée sans condition (ou carte hors GATE_ENTER_INFO) : pas de condition de salle."""
    lieu = condition_lieu(*conds_lieu)
    rpn = list(lieu["e"]) if lieu else []
    decodees = [decoder_condition(c) for c in salles or ()]
    if decodees and all(decodees):
        uniques = []
        for j in decodees:
            if j not in uniques:
                uniques.append(j)
        salle = list(uniques[0])
        for j in uniques[1:]:
            salle += j + [["o", "ou"]]
        rpn = salle if not rpn else rpn + salle + [["o", "et"]]
    if not rpn:
        return None
    return {"e": rpn, **resumer_condition(rpn)}


def _cle_cond(*conds) -> str:
    """Condition décodée d'un lieu en JSON canonique (clé de dédoublonnage des lieux ; "null" sans condition)."""
    return json.dumps(condition_lieu(*conds), sort_keys=True, separators=(",", ":"))


# ------------------------------------------------------------------------------------------------ sources
class Source:
    """Fichiers de `yw2_a.fa` : .cfg.bin et .xq, archives .pck ouvertes en mémoire. `ouvrir_fa(nom)` : archive."""

    def __init__(self, romfs: str | Path):
        self.src = L.SourceRomfs(romfs)
        self.empreinte = hashlib.sha1()

    def archive(self, nom: str):
        f, off, _t = self.src.ouvrir(nom)
        return f, L.Arc0(f, off)

    def fichiers(self):
        """(nom, carte ou '', octets) des .cfg.bin et .xq de yw2_a.fa (et des scripts `_pnt.xs` des décors de loupe) ;
        l'empreinte du RomFS couvre tout ce qui est lu."""
        f, arc = self.archive("yw2_a.fa")
        with f:
            for chemin in sorted(arc.entrees):
                if not (chemin.endswith((".cfg.bin", ".xq", ".pck")) or decor_de_script(chemin)):
                    continue
                d = arc.lire(chemin)
                self.empreinte.update(chemin.encode() + b"\0" + hashlib.sha1(d).digest())
                if chemin.endswith(".pck"):
                    if d[:4] != b"XPCK":
                        continue
                    try:
                        x = L.Xpck(d)
                    except (L.ErreurFormat, struct.error, IndexError, ValueError):
                        continue
                    carte = chemin.rsplit("/", 1)[-1][:-4]
                    for nom, _o, _t in x.fichiers:
                        if nom.endswith((".cfg.bin", ".xq", SUFFIXE_LAYOUT)):
                            yield carte + ".pck::" + nom, carte, x.lire(nom)
                else:
                    yield chemin, "", d

    def noms(self, langue: str) -> dict[int, str]:
        """NOUN_INFO de chara_text_<LG> (hachage de nom -> nom affiché), depuis yw2_lg_<LG>.fa."""
        try:
            f, arc = self.archive(f"yw2_lg_{langue}.fa")
        except (L.ErreurFormat, OSError):
            return {}
        with f:
            cible = [c for c in arc.entrees if c.endswith(f"/chara_text_{langue}.cfg.bin")]
            if not cible:
                return {}
            out = {}
            for nom, v in CfgBin(arc.lire(cible[0])).entrees:
                if nom == "NOUN_INFO" and len(v) > 5 and isinstance(v[0], int) and isinstance(v[5], str):
                    out[v[0]] = v[5]
            return out


# ------------------------------------------------------------------------------------------------ analyse
class Analyse:
    def __init__(self):
        self.tables: dict[str, tuple[list, list]] = {}          # fichier -> (ENCOUNT_TABLE, ENCOUNT_CHARA)
        self.par_hachage: dict[int, list] = collections.defaultdict(list)
        self.valeurs_par_entree: dict[str, set[int]] = collections.defaultdict(set)
        self.noms_conditions: set[int] = set()
        self.valeurs_scripts: set[int] = set()
        self.dons_scripts: set[int] = set()
        self.lieux: dict[int, list] = collections.defaultdict(list)    # rencontre -> [(carte, méthode, cond, permis)]
        self.points: list[tuple[str, int, list[int]]] = []             # (fichier, base, rencontres) des points de loupe
        self.qnc: list[tuple[int, int, int]] = []
        self.param_base: dict[int, int] = {}
        self.param_medaille: dict[int, int] = {}                        # espèce -> n° du Médaillium (v[49])
        self.param_amitie: dict[int, int] = {}                          # espèce -> quartets de taux d'amitié (v[31])
        self.param_stats: dict[int, list[int]] = {}                     # espèce -> v2..v11 (minimales, maximales)
        self.lignes_amitie: dict[str, list[int]] = {}                   # fichier -> clés de CHARA_FRIEND_RATE_INFO
        # format 10 : fichier -> lignes [clé, bonus d'aliment de valeur 1..4] ; coefficient de l'aliment préféré
        self.lignes_amitie_bonus: dict[str, list[list[int]]] = {}
        self.coef_aliment_prefere: float | None = None
        self.bases: dict[int, dict] = {}
        # format 5 (anti-softlock, exigences et leurs sources) --------------------------------------------------
        self.scripts_detail: dict[int, set[str]] = {}                   # valeur -> {instruction de script qui la cite}
        self.dons_sources: set[int] = set()                             # valeurs données par un script (AddParty*)
        self.conditions_detail: dict[int, set[str]] = collections.defaultdict(set)  # nom -> {« Fonction@ENTREE »}
        self.evolutions: dict[str, list[tuple[int, int]]] = {}          # fichier -> [(niveau, espèce obtenue)]
        self.param_evolution: dict[int, tuple[str, int]] = {}           # espèce -> (fichier, n° d'évolution)
        self.fusions: list[tuple[tuple[tuple[int, int], ...], tuple[int, int]]] = []   # ((genre, hachage)…), résultat
        self.capsules: set[int] = set()                                  # Yo-kai du Crank-a-kai (CAPSULE_ITEM_INFO)
        self.spots: set[int] = set()                                     # Yo-kai des spots (YS_YOKAI)
        self.legendes: list[tuple[int, list[int]]] = []                  # (légendaire, espèces du sceau)
        self.quetes: list[list] = []                                     # QUEST_CONFIG
        self.phases_quetes: list[list] = []                              # QUEST_PHASE
        self.qnc_fichier: list[tuple[str, int]] = []                     # (fichier, rang dans le fichier) de self.qnc
        self.combats_lances: set[str] = set()                            # rencontres lancées par script (0x352C)
        # format 7 (mélange par rencontre, archipelago_rando_yokai.md §11) : emplacement précis de chaque lieu sauvage
        # = point de loupe (WM_YOKAI_APPEAR n° i du fichier) ou chemin d'errants (SET_PATH n° i du fichier), avec sa
        # condition ; rencontre -> {(carte, méthode, fichier, n°, condition JSON)}
        self.emplacements: dict[int, set[tuple[str, str, str, int, str]]] = collections.defaultdict(set)
        # format 9 (loupe jamais vide, §14) : masque WM_YOKAI_INFO par base, champ « positions de Yo-kai » de
        # WM_MAP_ATTR par type de point, positions réelles par type (script du décor), types de point qui tirent
        # chaque WM_YOKAI_APPEAR (WM_YOKAI_WATCHMAP : type, …, 1er appear, nombre) ; n° dans le fichier de self.points
        self.loupe_masques: dict[int, int] = {}
        self.loupe_attr: dict[int, int] = {}
        self.loupe_reel: dict[int, int] = {}
        self.loupe_types: dict[tuple[str, int], set[int]] = collections.defaultdict(set)
        self.points_n: list[int] = []
        # format 11 (§16) : salles des portails mystères, crc32(carte) -> conditions compilées de ses entrées
        # GATE_ENTER_INFO (None : entrée sans GATE_ENTER_INFO_COND)
        self.salles: dict[int, list] = {}
        # format 12 (§18) : positions monde des lieux. Par carte : positions des points (`_layout.bin`, `_oneplace_pos` ;
        # jamais les fichiers `_gate`), points de loupe OP_WATCH_POINT (id, id de position, colonne de taux, type,
        # contenu fixe) ; par fichier de loupe : entrées WM_YOKAI_WATCHMAP (type, 1er appear, nombre) et
        # WM_YOKAI_EACH_WATCHMAP (id du point, 1er appear, nombre), taux de chaque WM_YOKAI_APPEAR ; par (fichier
        # d'errants, n° du SET_PATH) : (x, z) ; par rencontre et lieu brut : ses points / chemins (fichier, n°).
        self.pos_points: dict[str, dict[int, tuple[float, float]]] = collections.defaultdict(dict)
        self.points_loupe: dict[str, list[tuple[int, int, int, int, bool]]] = collections.defaultdict(list)
        self.loupe_plages: dict[str, list[tuple[int, int, int]]] = collections.defaultdict(list)
        self.loupe_plages_point: dict[str, list[tuple[int, int, int]]] = collections.defaultdict(list)
        self.loupe_taux: dict[tuple[str, int], list] = {}
        self.pos_chemins: dict[tuple[str, int], tuple[float, float]] = {}
        self.refs_pos: dict[int, dict[tuple, set]] = collections.defaultdict(lambda: collections.defaultdict(set))
        # format 13 (§19) : entrées de loupe DANS L'ORDRE du fichier, avec leur mode (clé, mode, 1er appear, nombre) :
        # par type de point et par point ; par rencontre et lieu brut d'errant : vrai si l'un de ses SET_PATH_POP a
        # un poids non nul dans la colonne de la version du jeu.
        self.loupe_entrees: dict[str, list[tuple[int, int, int, int]]] = collections.defaultdict(list)
        self.loupe_entrees_point: dict[str, list[tuple[int, int, int, int]]] = collections.defaultdict(list)
        self.errants_tires: dict[int, dict[tuple, bool]] = collections.defaultdict(dict)
        # format 17 (mélange version 5) : règles de combat BTL_RULE_INFO(hachage) -> [(v[0], v[12])] de ses
        # BTL_RULE_INFO_RULE_DATA (type, n° : (3, 5) = pas d'amitié)
        self.regles: dict[int, list[tuple[int, int]]] = {}

    def decors(self, nom: str, i_point: int) -> list[tuple[int, int]]:
        """Décors (positions réelles, positions de WM_MAP_ATTR) des types de point qui tirent l'appear n° i du fichier
        (type sans script de décor lu : positions réelles 0, rien n'y est posable)."""
        return sorted({(self.loupe_reel.get(t, 0), self.loupe_attr.get(t, 0))
                       for t in self.loupe_types.get((nom, i_point), ())})

    def lire(self, nom: str, carte: str, d: bytes) -> None:
        decor = decor_de_script(nom)
        if decor is not None:
            m = positions_yokai_xs(d)
            if m is not None:
                self.loupe_reel[crc(decor)] = m
            return
        if nom.endswith(".xq"):
            c, dn = valeurs_xq(d, self.scripts_detail, self.dons_sources)
            self.valeurs_scripts |= c
            self.dons_scripts |= dn
            self.combats_lances |= combats_lances_xq(d)
            return
        try:
            cfg = CfgBin(d).entrees
        except (struct.error, IndexError, ValueError, UnicodeDecodeError):
            return
        court = nom.rsplit("::", 1)[-1]
        if carte and "_gate" not in court and (court.endswith(SUFFIXE_LAYOUT) or "_oneplace_pos" in court):
            for n, v in cfg:                    # positions des points de la carte (format 12)
                if n in ENTREES_POSITION and len(v) > 3 and isinstance(v[0], int):
                    x, z = _coordonnee(v[1]), _coordonnee(v[3])
                    if x is not None and z is not None:
                        self.pos_points[carte].setdefault(v[0], (x, z))
        if court.endswith(SUFFIXE_LAYOUT):
            return                              # lu pour les positions seulement (rien d'autre n'en dépend)
        rang_qnc = 0
        table = [v for n, v in cfg if n == "ENCOUNT_TABLE"]
        if table:
            self.tables[nom] = (table, [v for n, v in cfg if n == "ENCOUNT_CHARA"])
            for i, v in enumerate(table):
                self.par_hachage[v[0]].append((nom, i))
        appar, enc, chemin, n_chemin = [], [], None, -1
        portail, salle, regle = fichier_portail(nom), None, None
        for n, v in cfg:
            if n != "ENCOUNT_TABLE":
                s = self.valeurs_par_entree[n]
                for x in v:
                    if isinstance(x, int) and x > 0xFFFF:
                        s.add(x)
                    else:
                        j = jetons_condition(x)
                        if j:
                            self.noms_conditions |= j[1]
                            self._detail_condition(decoder_condition(x) or [], None, n)
            if n == "WM_YOKAI_APPEAR" and len(v) >= 4:
                self.loupe_taux[(nom, len(appar))] = v[4:]
                appar.append(v)
            elif n == "WM_YOKAI_WATCHMAP" and len(v) >= 4 and all(isinstance(x, int) for x in v[:4]):
                for i in range(v[2], v[2] + v[3]):
                    self.loupe_types[(nom, i)].add(v[0])
                self.loupe_plages[nom].append((v[0], v[2], v[3]))
                self.loupe_entrees[nom].append((v[0], v[1], v[2], v[3]))
            elif n == "WM_YOKAI_EACH_WATCHMAP" and len(v) >= 4 and all(isinstance(x, int) for x in v[:4]):
                self.loupe_plages_point[nom].append((v[0], v[2], v[3]))
                self.loupe_entrees_point[nom].append((v[0], v[1], v[2], v[3]))
            elif n == "OP_WATCH_POINT" and len(v) >= 5 and carte and "_gate" not in court \
                    and all(isinstance(x, int) for x in (v[0], v[1], v[3], v[4])):
                fixe = len(v) > 8 and bool(v[8]) and not (len(v) > 9 and isinstance(v[9], str) and v[9])
                self.points_loupe[carte].append((v[0], v[1], v[3], v[4], fixe))
            elif n == "WM_YOKAI_INFO" and len(v) >= 2 and isinstance(v[0], int) and isinstance(v[1], int):
                self.loupe_masques[v[0]] = v[1]
            elif n == "WM_MAP_ATTR" and len(v) >= 3 and isinstance(v[0], int) and isinstance(v[2], int):
                self.loupe_attr[v[0]] = v[2]
            elif n == "WM_YOKAI_ENCOUNT" and v:
                enc.append(v[0])
            elif n == "SET_PATH":
                chemin = v[12] if len(v) > 12 else None
                n_chemin += 1
                xz = [_coordonnee(x) for x in v[1:4]] if len(v) > 3 else []
                if len(xz) == 3 and None not in xz and any(xz):        # (0, 0, 0) : pas de position dans le fichier
                    self.pos_chemins[(nom, n_chemin)] = (xz[0], xz[2])
            elif n == "SET_PATH_POP_LIST_END":
                chemin = None
            elif n == "SET_PATH_POP" and v and isinstance(v[0], int):
                c = v[12] if len(v) > 12 else None
                # 6e élément (lieu de portail seulement) : conditions brutes, jointes à celle de la salle à la
                # génération (`lieux_base`) ; les 5 premiers sont ceux du format 10 (W et mélange inchangés)
                self.lieux[v[0]].append((carte, "errant", *self._condition(c, chemin), _cle_cond(c, chemin))
                                        + (((c, chemin),) if portail else ()))
                self.emplacements[v[0]].add((carte, "errant", nom, n_chemin, _cle_cond(c, chemin)))
                self.refs_pos[v[0]][self.lieux[v[0]][-1][:5]].add((nom, n_chemin))
                cle_lieu = self.lieux[v[0]][-1][:5]
                self.errants_tires[v[0]][cle_lieu] = self.errants_tires[v[0]].get(cle_lieu, False) or (
                    len(v) > V_POIDS_ERRANT and _positif(v[V_POIDS_ERRANT]))
            elif n == "BTL_RULE_INFO" and v and isinstance(v[0], int):
                regle = self.regles.setdefault(v[0], [])
            elif n == "BTL_RULE_INFO_RULE_DATA" and regle is not None and len(v) > 12                     and isinstance(v[0], int) and isinstance(v[12], int):
                regle.append((v[0], v[12]))
            elif n == "GATE_ENTER_INFO" and v and isinstance(v[0], int):
                salle = self.salles.setdefault(v[0], [])
                salle.append(None)
            elif n == "GATE_ENTER_INFO_COND" and salle:
                salle[-1] = next((x for x in v if isinstance(x, str) and x.startswith("AAAA")), None)
            elif n == "QUEST_NECESSARY_CONDITION" and len(v) >= 3:
                self.qnc.append((v[0], v[1], v[2]))
                self.qnc_fichier.append((nom, rang_qnc))
                rang_qnc += 1
            elif n == "QUEST_CONFIG" and len(v) > 7:
                self.quetes.append(v)
            elif n == "QUEST_PHASE" and len(v) > 4:
                self.phases_quetes.append(v)
            elif n == "CHARA_EVOLVE_INFO" and len(v) > 1:
                self.evolutions.setdefault(nom, []).append((v[0], v[1]))
            elif n == "COMBINE_INFO" and len(v) > 5:
                self.fusions.append((((v[0], v[1]), (v[2], v[3])), (v[4], v[5])))
            elif n == "CAPSULE_ITEM_INFO" and len(v) > 2 and isinstance(v[2], int):
                self.capsules.add(v[2])
            elif n == "YS_YOKAI" and v and isinstance(v[0], int):
                self.spots.add(v[0])
            elif n == "LEGEND_DATA_CONFIG" and len(v) > 17:
                self.legendes.append((v[1], [x for x in v[2:18:2] if isinstance(x, int)]))
            elif n == "CHARA_PARAM_INFO" and len(v) > 1:
                self.param_base[v[0]] = v[1]
                # n° d'évolution (CHARA_EVOLVE_INFO du même fichier, dans l'ordre ; 0xFFFFFFFF : aucune) [C : 39
                # valeurs distinctes pour 39 entrées d'évolution, archipelago_rando_yokai.md §3.6]
                if len(v) > V_EVOLUTION and isinstance(v[V_EVOLUTION], int) and v[V_EVOLUTION] != AUCUN:
                    self.param_evolution[v[0]] = (nom, v[V_EVOLUTION])
                # n° du Médaillium (u16 +100 de l'enregistrement natif, FUN_004D6B0C ; FUN_0041103C) : index des bits
                # « vu » P+0x40C et « ami » P+0x44C | P+0x604 [C, archipelago_rando_yokai.md §10.6] ; 0 : hors Médaillium
                if len(v) > 49 and isinstance(v[49], int) and 0 < v[49] < 512:
                    self.param_medaille[v[0]] = v[49]
                if len(v) > V_AMITIE and isinstance(v[V_AMITIE], int):
                    self.param_amitie[v[0]] = v[V_AMITIE]
                # format 18 (force des boss adaptée, archipelago_rando_boss.md §15.1) : v2..v6 PV, For, Esp, Déf, Vit
                # minimales, v7..v11 maximales (u16 +0x08..+0x1A de l'enregistrement natif, FUN_004D6B0C) [C]
                st = v[V_STATS:V_STATS + 10]
                if len(st) == 10 and all(isinstance(x, int) for x in st):
                    self.param_stats[v[0]] = list(st)
            elif n == "CHARA_FRIEND_RATE_INFO":
                self.lignes_amitie.setdefault(nom, []).append(v[0] if v and isinstance(v[0], int) else 0)
                self.lignes_amitie_bonus.setdefault(nom, []).append(
                    [x if isinstance(x, int) and 0 <= x <= 0x7FFF else 0 for x in (list(v) + [0] * 5)[:5]])
            elif n == "VALUE_INFO" and len(v) >= 2 and v[0] == P_ALIMENT_PREFERE and isinstance(v[1], (int, float)):
                self.coef_aliment_prefere = float(v[1])
            elif n == "CHARA_BASE_YOKAI_INFO" and len(v) > 24:
                self.bases[v[0]] = {"rang": v[14], "tribu": v[24], "nom": v[4], "yokai": True,
                                    "rare": bool(v[V_RARE]), "legendaire": bool(v[V_LEGENDAIRE]),
                                    "aliment": v[V_ALIMENT] if isinstance(v[V_ALIMENT], int)
                                    and 0 < v[V_ALIMENT] < 256 else 0}
            elif n == "CHARA_BASE_INFO" and len(v) > 4:
                self.bases.setdefault(v[0], {"rang": None, "tribu": None, "nom": v[4], "yokai": False})
        for i_point, a in enumerate(appar):
            base, debut, nb = a[0], a[1], a[2]
            rencontres = enc[debut:debut + nb] if isinstance(debut, int) and isinstance(nb, int) else []
            self.points.append((nom, base, rencontres))
            self.points_n.append(i_point)
            for h in rencontres:
                # 6e élément (format 11) : point de loupe (fichier, n°), pour le type de décor (`lieux_base`)
                self.lieux[h].append((carte, "loupe", *self._condition(a[3], None), _cle_cond(a[3], None),
                                      (nom, i_point)))
                self.emplacements[h].add((carte, "loupe", nom, i_point, _cle_cond(a[3], None)))

    def table_amitie(self) -> dict | None:
        """Table de taux d'amitié de la base locale (format 10) : `lignes` = [clé, bonus d'aliment de valeur 1..4] par
        ligne de CHARA_FRIEND_RATE_INFO (probabilité par combat = 1 / clé + bonus × `prefere` / 10 000 pour un aliment
        de la catégorie préférée), ou None si le jeu n'a pas exactement une table (prudence : rien n'est affiché)."""
        if len(self.lignes_amitie_bonus) != 1:
            return None
        (lignes,) = self.lignes_amitie_bonus.values()
        return {"lignes": lignes, "prefere": self.coef_aliment_prefere}

    def quartets_amitie(self, p: int) -> list[int] | None:
        """Lignes de taux visées par l'espèce pour k = 0..5 Yo-kai de même base déjà possédés (quartets de v[31]) ;
        None : pas de CHARA_PARAM."""
        v = self.param_amitie.get(p)
        return None if v is None else [(v >> (4 * k)) & 15 for k in range(NB_QUARTETS_AMITIE)]

    def recrutable(self, p: int) -> bool:
        """Espèce recrutable en combat (nourriture acceptée, amitié possible) selon TOUTES les tables de taux d'amitié
        lues (une seule dans le jeu ; aucune : rien n'est recrutable, par prudence)."""
        return bool(self.lignes_amitie) and all(recrutable_en_combat(self.param_amitie.get(p), l)
                                                for l in self.lignes_amitie.values())

    def evenement(self) -> tuple[set[int], set[int]]:
        """(rencontres, espèces) d'évènement : rencontres « enc_day_* » lancées par script (0x352C) ; espèces = toutes
        les variantes CHARA_PARAM des bases de leurs combattants et de BASES_EVENEMENT ; puis toute rencontre dont un
        combattant est une de ces espèces (ex. les deux combats de Darknyan)."""
        renc = {crc(n) for n in self.combats_lances if n.startswith(PREFIXE_EVENEMENT)} & set(self.par_hachage)
        bases = set(BASES_EVENEMENT)
        for h in renc:
            bases |= {self.param_base.get(p, p) for _n, _k, p, _l in self.combattants(h)}
        especes = {p for p, b in self.param_base.items() if b in bases}
        renc |= {h for h in self.par_hachage if any(p in especes for _n, _k, p, _l in self.combattants(h))}
        return renc, especes

    def _detail_condition(self, rpn: list, fonction: str | None, entree: str) -> None:
        """Noms (0x34) d'une condition décodée, avec la fonction qui les reçoit en argument (audit)."""
        for j in rpn:
            if j[0] == "n":
                self.conditions_detail[j[1]].add(f"{fonction or '-'}@{entree}")
            elif j[0] == "f":
                for arg in j[2]:
                    self._detail_condition(arg, j[1], entree)

    # -------------------------------------------------------------------------------- exigences (format 5)
    def yokai(self) -> set[int]:
        """Hachages de Yo-kai : espèces (CHARA_PARAM) et bases de Yo-kai (CHARA_BASE_YOKAI_INFO)."""
        return set(self.param_base) | {b for b, i in self.bases.items() if i.get("yokai")}

    def especes_de(self, h: int) -> set[int]:
        """Espèces (CHARA_PARAM) désignées par un hachage : l'espèce elle-même, ou toutes les espèces d'une base."""
        if h in self.param_base:
            return {h}
        return {p for p, b in self.param_base.items() if b == h}

    def quete_de_qnc(self) -> dict[int, tuple[int, int, int]]:
        """Rang de self.qnc -> (hachage de la quête, genre, numéro), par QUEST_CONFIG (v6 1re phase, v7 nombre) et
        QUEST_PHASE (v3 1re condition, v4 nombre) du fichier des quêtes [C, tools/romfs/quetes.py]."""
        out = {}
        rang_global = {(f, r): i for i, (f, r) in enumerate(self.qnc_fichier)}
        fichier = next((f for f, _r in self.qnc_fichier), None)
        for q in self.quetes:
            if not all(isinstance(q[k], int) for k in (0, 1, 3, 6, 7)):
                continue
            for ph in range(q[6], min(q[6] + q[7], len(self.phases_quetes))):
                p = self.phases_quetes[ph]
                if not (isinstance(p[3], int) and isinstance(p[4], int)) or p[4] > 64:
                    continue
                for r in range(p[3], p[3] + p[4]):
                    i = rang_global.get((fichier, r))
                    if i is not None:
                        out.setdefault(i, (q[0], q[1], q[3]))
        return out

    def exigences(self) -> list[tuple[str, int, str]]:
        """Toutes les exigences du jeu portant sur un Yo-kai : (catégorie, hachage cité — espèce, base ou rencontre —,
        où). Voir les catégories en tête du module."""
        yk = self.yokai()
        out: list[tuple[str, int, str]] = []
        quetes = self.quete_de_qnc()
        for i, (t, h, nb) in enumerate(self.qnc):
            if t in QNC_EXIGENCES:
                q = quetes.get(i)
                ou = f"quête n° {q[2]} (genre {q[1]}, 0x{q[0]:08X}), nombre {nb}" if q else f"condition n° {i}"
                out.append((QNC_EXIGENCES[t], h, ou))
        for n, s in sorted(self.valeurs_par_entree.items()):
            if n in ENTREES_SANS_EXIGENCE or n == "QUEST_NECESSARY_CONDITION":
                continue
            r = RAISONS_ENTREES.get(n, "entree:" + n)
            out += [(r, h, n) for h in sorted(s & yk)]
        for h in sorted(set(self.conditions_detail) & yk):
            for d in sorted(self.conditions_detail[h]):
                f, _, e = d.partition("@")
                out.append(("condition:" + f, h, e))
        for h in sorted(self.valeurs_scripts & yk):
            for c in sorted(self.scripts_detail.get(h, {"?"})):
                out.append(("script:" + c, h, ""))
        for leg, membres in self.legendes:
            out += [("sceau_legendaire", m, f"légendaire 0x{leg:08X}") for m in membres if m in yk]
        return out

    def predecesseurs(self) -> dict[int, set[tuple[str, int]]]:
        """Espèce -> {(« source_evolution » | « source_fusion », espèce source)} : qui évolue vers elle, quels Yo-kai
        entrent dans une fusion qui la donne (genre 0 = Yo-kai, 1 = objet : les objets ne sont pas des Yo-kai)."""
        out: dict[int, set[tuple[str, int]]] = collections.defaultdict(set)
        for q, (f, i) in self.param_evolution.items():
            ev = self.evolutions.get(f, [])
            if 0 <= i < len(ev) and isinstance(ev[i][1], int):
                out[ev[i][1]].add(("source_evolution", q))
        for mats, (tr, res) in self.fusions:
            if tr != 0:
                continue
            for tm, m in mats:
                if tm == 0 and isinstance(m, int):
                    out[res].add(("source_fusion", m))
        return out

    def fermeture(self, exig: list[tuple[str, int, str]] | None = None, fortes: bool = False) -> dict[int, set[str]]:
        """Espèces exigées ET leurs sources, récursivement : espèce -> raisons (catégories d'exigence, puis
        source_evolution / source_fusion). Les combattants d'une rencontre exigée (quete_rencontre) n'y sont pas : la
        rencontre elle-même ne change jamais (hors W, hachage de boss conservé). `fortes` : exigences fortes seulement
        (CATEGORIES_FAIBLES écartées)."""
        exig = self.exigences() if exig is None else exig
        raisons: dict[int, set[str]] = collections.defaultdict(set)
        for cat, h, _ou in exig:
            if cat == "quete_rencontre" or (fortes and cat in CATEGORIES_FAIBLES):
                continue
            for p in self.especes_de(h):
                raisons[p].add(cat)
        pred = self.predecesseurs()
        pile = list(raisons)
        while pile:
            p = pile.pop()
            for r, q in pred.get(p, ()):
                nouveau = q not in raisons
                raisons[q].add(r)
                if nouveau:
                    pile.append(q)
        return dict(raisons)

    def exigences_boss(self, exig: list[tuple[str, int, str]] | None = None) -> dict[int, list[str]]:
        """Espèces qu'un combat de boss ne doit pas cesser de fournir (le mélange des boss n'échange jamais un boss qui
        en a une) : exigées fortement (ou source d'une espèce exigée fortement) et recrutables en combat (amitié après
        la victoire), ou exigées à vaincre / citées par une règle de combat quelle que soit leur recrutabilité."""
        out = {}
        for p, r in self.fermeture(exig, fortes=True).items():
            if self.recrutable(p) or r & CATEGORIES_BOSS_TOUJOURS:
                out[p] = sorted(r) + ([] if self.recrutable(p) else ["non_recrutable"])
        return out

    @staticmethod
    def _condition(*conds) -> tuple[str, bool]:
        """(texte court de la condition, permise pour W)."""
        mots, permis = [], True
        for c in conds:
            j = jetons_condition(c)
            if j is None:
                continue
            for f in sorted(j[0]):
                mots.append(NOMS_FONCTIONS.get(f, "%08X" % f))
                permis &= f in CONDITIONS_PERMISES
        return " ".join(dict.fromkeys(mots)), permis

    def lieux_base(self, h: int) -> list[list]:
        """`lieux` d'une rencontre sauvage dans la base : [carte, méthode, texte de condition, condition décodée] ;
        lieu de portail (format 11, §16) : méthode « portail », condition du lieu ET de la salle, 5e élément = 1 si
        la carte est une salle de GATE_ENTER_INFO, 0 sinon (carte à `_enc_pos_gate` atteinte depuis une salle : non
        confirmé) ; lieu de loupe (format 11, §17) : 5e élément = types de point (crc32 du nom du décor, clé de
        WM_MAP_ATTR) des points de la carte qui tirent cette rencontre à cette condition."""
        return self._lieux(h)[0]

    def positions_base(self, h: int) -> list[list[list]]:
        """`pos` d'une rencontre sauvage (format 12, §18) : pour chaque élément de `lieux_base(h)`, dans le même ordre,
        les positions monde où la rencontre peut sortir : [x, z, type de point] (loupe), [x, z] (errant, portail)."""
        return self._lieux(h)[1]

    def moments_base(self, h: int) -> list[int]:
        """`mom` d'une rencontre sauvage (format 13, §19) : masque de moments de chaque élément de `lieux_base(h)`."""
        return self._lieux(h)[2]

    def moments_de_loupe(self, carte: str, nom: str, i_point: int) -> tuple[dict[tuple[float, float, int], int], int]:
        """Points de loupe de `carte` où le `WM_YOKAI_APPEAR` n° i du fichier `nom` peut être tiré, et QUAND [C,
        désassembleur : `FUN_004900DC` -> `FUN_0064DC34` -> `FUN_0064DB1C`, §18.1 et §19] : ({(x, z, type) : masque de
        moments} des points à position connue, masque de tous les points de la carte, position connue ou non).

        Pour un point ordinaire (`OP_WATCH_POINT` sans contenu fixe) et chaque moitié de la journée, le jeu retient LA
        PREMIÈRE entrée de la table par point (`WM_YOKAI_EACH_WATCHMAP`, clé = identifiant du point), sinon de la table
        par type (`WM_YOKAI_WATCHMAP`, clé = type du point), dont le mode vaut 0 ou celui du moment (1 jour, 2 nuit) ;
        il tire parmi ses appears au taux de la COLONNE du point (v3) : 1er jeu de taux par temps sec, 2e jeu sous la
        pluie (`GetWeatherNow`) ; un taux nul n'est jamais tiré. Position = `SHAPE_DATA_ITEM` / `POINT_DATA_ITEM`."""
        taux = self.loupe_taux.get((nom, i_point)) or []
        n = len(taux) // 2                  # deux jeux de n colonnes : v[4 : 4 + n] et v[4 + n : 4 + 2n] (FUN_005183F8)
        par_point, par_type = self.loupe_entrees_point.get(nom, ()), self.loupe_entrees.get(nom, ())

        def entree(liste, cle: int, mode: int):
            return next(((d, k) for c, m, d, k in liste if c == cle and m in (MODE_TOUJOURS, mode)), None)
        out: dict[tuple[float, float, int], int] = {}
        tous = 0
        for ident, id_pos, col, typ, fixe in self.points_loupe.get(carte, ()):
            if fixe or not 0 <= col < n:    # colonne absente du fichier : aucun Yo-kai
                continue
            meteo = (JOUR_SEC | NUIT_SEC if _positif(taux[col]) else 0) | (
                JOUR_PLUIE | NUIT_PLUIE if _positif(taux[n + col]) else 0)
            masque = 0
            for mode, bits in ((MODE_JOUR, JOUR_SEC | JOUR_PLUIE), (MODE_NUIT, NUIT_SEC | NUIT_PLUIE)):
                e = entree(par_point, ident, mode) or entree(par_type, typ, mode)
                if e is not None and e[0] <= i_point < e[0] + e[1]:
                    masque |= bits & meteo
            if not masque:
                continue
            tous |= masque
            p = self.pos_points.get(carte, {}).get(id_pos)
            if p is not None:
                k = (round(p[0], 1), round(p[1], 1), typ)
                out[k] = out.get(k, 0) | masque
        return out, tous

    def points_de_loupe(self, carte: str, nom: str, i_point: int) -> set[tuple[float, float, int]]:
        """Points de loupe (x, z, type) de `carte` où l'appear n° i du fichier `nom` peut être tiré à un moment au
        moins (`moments_de_loupe`)."""
        return set(self.moments_de_loupe(carte, nom, i_point)[0])

    def _lieux(self, h: int) -> tuple[list[list], list[list[list]], list[int]]:
        """(`lieux`, `pos`, `mom`) d'une rencontre sauvage, trois listes parallèles. `mom` (format 13, §19) : masque de
        moments du lieu (JOUR_SEC | JOUR_PLUIE | NUIT_SEC | NUIT_PLUIE) : loupe = union de ses points (0 : aucun point
        ordinaire de la carte ne la tire) ; errant et portail = 15 si l'un de ses SET_PATH_POP a un poids non nul dans
        la colonne de la version du jeu, 0 sinon (jamais tiré dans cette version). La condition du lieu (créneau
        horaire `GetTimeNow`…) n'y entre pas : elle est dans `lieux`."""
        out = set()
        types: dict[tuple, set[int]] = collections.defaultdict(set)
        pos: dict[tuple, dict[tuple, int]] = collections.defaultdict(dict)
        mom: dict[tuple, int] = collections.defaultdict(int)
        refs = self.refs_pos.get(h, {})
        tires = self.errants_tires.get(h, {})
        for l in self.lieux.get(h, ()):
            if l[1] == "loupe":
                x = (l[0], l[1], l[2], l[4])
                if len(l) > 5:
                    types[x] |= self.loupe_types.get(l[5], set())
                    points, tous = self.moments_de_loupe(l[0], *l[5])
                    for k, m in points.items():
                        pos[x][k] = pos[x].get(k, 0) | m
                    mom[x] |= tous
                out.add(x)
                continue
            if len(l) > 5:
                salles = self.salles.get(crc(l[0]))
                conds = [c for c in (salles or ()) if c] if salles and all(salles) else []
                k = json.dumps(condition_portail(l[5], conds), sort_keys=True, separators=(",", ":"))
                x = (l[0], METHODE_PORTAIL, self._condition(*l[5], *conds)[0], k, int(bool(salles)))
            else:
                x = (l[0], l[1], l[2], l[4])
            out.add(x)
            if tires.get(l[:5]):
                mom[x] = MOMENT_TOUJOURS
            for ref in refs.get(l[:5], ()):
                p = self.pos_chemins.get(ref)
                if p is not None:
                    pos[x][(round(p[0], 1), round(p[1], 1))] = 0
        ordre = sorted(out)
        return ([[x[0], x[1], x[2], json.loads(x[3]), *x[4:], *([sorted(types[x])] if x in types else [])]
                 for x in ordre],
                [[[*p, pos[x][p]] if len(p) > 2 else list(p) for p in sorted(pos.get(x, ()))] for x in ordre],
                [mom.get(x, MOMENT_JAMAIS) for x in ordre])

    # -------------------------------------------------------------------------------- résultat
    def combattants(self, h: int) -> list[tuple[str, int, int, int]]:
        return [x[:4] for x in self.combattants_places(h)]

    def combattants_places(self, h: int) -> list[tuple[str, int, int, int, int]]:
        """(fichier, index d'ENCOUNT_CHARA, espèce, niveau, place j) : place = n° de l'index (+0x10 + 2j de la rencontre
        native, 0..5) ; le jeu accède au combattant par la place (FUN_0064B600)."""
        out = []
        for n, i in self.par_hachage.get(h, ()):
            tt, cc = self.tables[n]
            for j, k in enumerate(tt[i][1:7]):
                if isinstance(k, int) and k != AUCUN and k < len(cc):
                    out.append((n, k, cc[k][0], cc[k][1], j))
        return out

    def references(self) -> dict[tuple[str, int], int]:
        """(fichier, index d'ENCOUNT_CHARA) -> nombre de rencontres du fichier qui le citent (randomizer des boss : le
        combattant d'un boss sans script ne doit pas être partagé)."""
        out: dict[tuple[str, int], int] = collections.Counter()
        for n, (tt, _cc) in self.tables.items():
            for v in tt:
                for k in {k for k in v[1:7] if isinstance(k, int) and k != AUCUN}:
                    out[(n, k)] += 1
        return out

    def script(self, h: int) -> tuple[str, int, list[str]] | None:
        """(nom du script de combat, règle, fichiers) de la rencontre h si l'une de ses définitions a un script."""
        occ = self.par_hachage.get(h, ())
        for n, i in occ:
            v = self.tables[n][0][i]
            if len(v) > 7 and isinstance(v[7], str) and v[7]:
                return v[7], v[22] if len(v) > 22 and isinstance(v[22], int) else 0, sorted({x for x, _j in occ})
        return None

    def categoriser(self) -> tuple[dict[int, set[str]], set[int]]:
        cite: dict[int, set[str]] = collections.defaultdict(set)
        hachages = set(self.par_hachage)
        for n, s in self.valeurs_par_entree.items():
            for h in s & hachages:
                cite[h].add(n)
        sauvages = set()
        for h, occ in self.par_hachage.items():
            script = any(isinstance(self.tables[n][0][i][7], str) and self.tables[n][0][i][7] for n, i in occ
                         if len(self.tables[n][0][i]) > 7)
            if not script and cite.get(h) and cite[h] <= set(SAUVAGE):
                sauvages.add(h)
        return cite, sauvages

    def morte(self, h: int) -> bool:
        """Rencontre sauvage qui a des lieux mais dont aucun ne sort jamais dans cette version du jeu (§19, §20)."""
        mom = self.moments_base(h)
        return bool(mom) and not any(mom)

    def normale(self, h: int) -> bool:
        """Rencontre sauvage qui a au moins un lieu NORMAL (mélange version 3, §21) : hors portail mystère (§16), qui
        sort dans cette version du jeu (`mom` non nul, §19) et d'avant la fin (`lieu_hors_avant_fin`, §3.7)."""
        lieux, _pos, mom = self._lieux(h)
        return any(l[1] != METHODE_PORTAIL and m and lieu_hors_avant_fin(l[0], l[3]) is None
                   for l, m in zip(lieux, mom))

    def invitees(self, sauvages: set[int]) -> tuple[list[int], dict[str, str]]:
        """Espèces invitées du mélange version 4 (§22) : (espèces retenues triées, {n° du Médaillium : raison} des
        écartées). Retenue = l'unique CHARA_PARAM recrutable en combat (ligne de taux d'amitié non nulle pour k = 0,
        §3.5) du n°, Yo-kai à rang E..S, non légendaire, hors évènement, absent de TOUTE rencontre sauvage (une espèce
        déjà sauvage suit les règles ordinaires du réservoir, jamais celles-ci)."""
        par_n = collections.defaultdict(list)
        for p, n in self.param_medaille.items():
            par_n[n].append(p)
        des_sauvages = {p for h in sauvages for _n, _k, p, _l in self.combattants(h)}
        evenement = self.evenement()[1]
        retenues, ecartees = [], {}
        for n in INVITEES_MEDAILLIUM:
            cands = sorted(p for p in par_n.get(n, ()) if self.recrutable(p))
            info = self.bases.get(self.param_base.get(cands[0])) if len(cands) == 1 else None
            if not par_n.get(n):
                raison = "absente"
            elif not cands:
                raison = "non_recrutable"
            elif len(cands) > 1:
                raison = "variantes"
            elif not info or not info.get("yokai") or info.get("rang") not in (0, 1, 2, 3, 4, 5):
                raison = "sans_rang"
            elif info.get("legendaire"):
                raison = "legendaire"
            elif cands[0] in evenement:
                raison = "evenement"
            elif cands[0] in des_sauvages:
                raison = "deja_sauvage"
            else:
                retenues.append(cands[0])
                continue
            ecartees[str(n)] = raison
        return sorted(retenues), ecartees

    def exclure(self, sauvages: set[int], mortes: bool = False) -> tuple[set[int], dict[int, list[str]]]:
        """W = sauvages moins les exclusions (raisons par rencontre), jusqu'au point fixe (partage, points mixtes).
        `mortes` (mélange version 2, §20) : exclut aussi les rencontres qui ne sortent jamais dans cette version."""
        raisons: dict[int, list[str]] = collections.defaultdict(list)
        quetes = {h for t, h, _n in self.qnc if t == 4}
        evenement = self.evenement()[0]
        for h in sauvages:
            # périmètre (§3.7) : aucun lieu d'avant la fin -> hors de W (raison(s) : apres_jeu, hors_partie)
            hors = [lieu_hors_avant_fin(l[0], json.loads(l[4])) for l in self.lieux.get(h, ())]
            if hors and all(hors):
                raisons[h] += sorted(set(hors))
            if h in evenement:
                raisons[h].append("evenement")
            if mortes and self.morte(h):
                raisons[h].append(RAISON_MORTE)
            if not self.combattants(h):
                raisons[h].append("sans_combattant")
            if h in self.valeurs_scripts:
                raisons[h].append("script")
            if h in quetes:
                raisons[h].append("quete")
            if any(not l[3] for l in self.lieux.get(h, ())):
                raisons[h].append("condition")
            if len(self.par_hachage[h]) != 1:
                raisons[h].append("plusieurs_fichiers")
        w = {h for h in sauvages if not raisons.get(h)}
        while True:
            partages = self.partages(w)
            retires = set()
            # point de loupe : sa base (le Yo-kai montré par la loupe, FUN_00519154) n'est réécrite que si toutes ses
            # rencontres sont dans W et que leur 1er combattant (celui de la base) est réécrit, c.-à-d. non partagé
            for _f, _b, rs in self.points:
                if not any(h in w for h in rs):
                    continue
                for h in rs:
                    if h not in w:
                        continue
                    if not all(x in w for x in rs):
                        retires.add(h)
                        raisons[h].append("point_mixte")
                    else:
                        c = self.combattants(h)
                        if c and (c[0][0], c[0][1]) in partages:
                            retires.add(h)
                            raisons[h].append("premier_partage")
            if not retires:
                break
            w -= retires
        return w, raisons

    # -------------------------------------------------------------------------------- mélange version 5 (format 17)
    def sans_amitie(self, h: int) -> bool:
        """Une définition de la rencontre a une règle de combat « pas d'amitié » (type 3 / n° 5, REGLE_SANS_AMITIE)."""
        for n, i in self.par_hachage.get(h, ()):
            v = self.tables[n][0][i]
            if len(v) > 22 and isinstance(v[22], int) and REGLE_SANS_AMITIE in self.regles.get(v[22], ()):
                return True
        return False

    @staticmethod
    def lieu_permis5(cond: dict | None) -> bool:
        """Condition décodée d'un lieu sauvage acceptée par le mélange version 5 : seulement des fonctions de
        FONCTIONS_LIEU5 (rang de montre, heure, après-jeu, phase d'histoire) et `GetGlobalByteFlag` d'un octet d'état
        d'histoire (FLAGS_HISTOIRE5) ; tout autre jeton (quête, objet, autre flag, jeton inconnu) : refusée."""
        def ok(rpn) -> bool:
            for j in rpn:
                if j[0] == "?":
                    return False
                if j[0] != "f":
                    continue
                if j[1] == "GetGlobalByteFlag":
                    noms = [x for arg in j[2] for x in arg]
                    if not noms or any(x[0] != "n" or x[1] not in FLAGS_HISTOIRE5 for x in noms):
                        return False
                elif j[1] not in FONCTIONS_LIEU5 or not all(ok(arg) for arg in j[2]):
                    return False
            return True
        return cond is None or ok(cond.get("e") or [])

    @staticmethod
    def lieu_permanent5(cond: dict | None) -> bool:
        """Condition d'un lieu qui, une fois vraie, le reste (mélange version 5, couverture « lieu normal ») : rang de
        montre, heure, phase d'histoire MINIMALE seulement (aucune borne haute, aucun flag, aucun « ou ») ; « avant
        l'après-jeu » (GameClear == 0) est permis : la garantie porte sur l'avant la fin."""
        if cond is None:
            return True
        rpn = cond.get("e") or []
        if any(j[0] == "?" or (j[0] == "o" and j[1] == "ou") or (j[0] == "f" and j[1] not in FONCTIONS_LIEU5)
               for j in rpn):
            return False
        r = resumer_condition(rpn)
        ph = r.get("phase") or [None, None]
        return not r.get("autres") and ph[1] is None

    def exclure5(self, sauvages: set[int], cite: dict[int, set[str]], apres_jeu: bool, version: int = 5
                 ) -> tuple[set[int], dict[int, list[str]], dict[int, str]]:
        """(W' du mélange version 5, raisons d'exclusion par rencontre, catégorie des rencontres de W' non sauvages)
        pour le périmètre « base » (`apres_jeu` faux) ou « apres_jeu ». Raisons : celles d'`exclure` (sans le point
        fixe de la base de loupe σ, inutile au mélange par rencontre ; rencontres mortes toujours exclues),
        `condition` remplacée par la règle de `lieu_permis5`, plus `sans_amitie` ; une rencontre non sauvage hors de
        AJOUTS5 n'a pas de raison (sa catégorie `cat` suffit au tracker). `version` 6 : catégories de AJOUTS6 (spots
        en plus ; le flag de même nom d'une rencontre de spot ne compte pas comme une citation)."""
        raisons: dict[int, list[str]] = collections.defaultdict(list)
        quetes = {h for t, h, _n in self.qnc if t == 4}
        evenement = self.evenement()[0]
        ajouts: dict[int, str] = {}
        categories = AJOUTS6 if version >= 6 else AJOUTS5
        for h in self.par_hachage:
            if h in sauvages:
                hors = [lieu_hors_avant_fin(l[0], json.loads(l[4])) for l in self.lieux.get(h, ())]
                if hors and all(hors) and not (apres_jeu and "apres_jeu" in hors):
                    raisons[h] += sorted(set(hors))
                if self.morte(h):
                    raisons[h].append(RAISON_MORTE)
                if any(not self.lieu_permis5(json.loads(l[4])) for l in self.lieux.get(h, ())):
                    raisons[h].append("condition")
            else:
                cats = cite.get(h, set())
                if version >= 6 and "YS_YOKAI" in cats:
                    cats = cats - CITATIONS_NEUTRES_SPOT6
                if len(cats) != 1 or next(iter(cats)) not in categories:
                    continue
                ajouts[h] = categories[next(iter(cats))]
                if self.script(h) is not None:
                    raisons[h].append("script_de_combat")
            if h in evenement:
                raisons[h].append("evenement")
            if not self.combattants(h):
                raisons[h].append("sans_combattant")
            if h in self.valeurs_scripts:
                raisons[h].append("script")
            if h in quetes:
                raisons[h].append("quete")
            if len(self.par_hachage[h]) != 1:
                raisons[h].append("plusieurs_fichiers")
            if self.sans_amitie(h):
                raisons[h].append("sans_amitie")
        wp = {h for h in sauvages | set(ajouts) if not raisons.get(h)}
        return wp, {h: sorted(set(r)) for h, r in raisons.items() if r}, {h: c for h, c in ajouts.items() if h in wp}

    def partages(self, w: set[int]) -> set[tuple[str, int]]:
        """(fichier, index d'ENCOUNT_CHARA) cités à la fois par une rencontre de W et par une rencontre hors W du même
        fichier : le jeu ne les réécrit pas (marquage de FUN_00506098), le tracker non plus."""
        out = set()
        for n, (tt, _cc) in self.tables.items():
            dans, hors = set(), set()
            for v in tt:
                idx = {k for k in v[1:7] if isinstance(k, int) and k != AUCUN}
                (dans if v[0] in w else hors).update(idx)
            out |= {(n, k) for k in dans & hors}
        return out

    def fixer(self, candidats: set[int]) -> dict[int, list[str]]:
        """Espèces (CHARA_PARAM) fixées parmi `candidats`, avec leurs raisons."""
        base_de = self.param_base
        par_base = collections.defaultdict(set)
        for p in candidats:
            par_base[base_de.get(p, p)].add(p)
        raisons: dict[int, list[str]] = collections.defaultdict(list)
        especes_evenement = self.evenement()[1]
        for t, h, _n in self.qnc:
            r = RAISONS_QNC.get(t, "quete_condition_%d" % t)
            for p in par_base.get(h, set()) | ({h} & candidats):
                raisons[p].append(r)
        for n, s in self.valeurs_par_entree.items():
            if n in ENTREES_SANS_EXIGENCE or n == "QUEST_NECESSARY_CONDITION":
                continue
            r = RAISONS_ENTREES.get(n, "entree:" + n)
            for p in candidats:
                if p in s or base_de.get(p) in s:
                    raisons[p].append(r)
        for p in candidats:
            if p in self.noms_conditions or base_de.get(p) in self.noms_conditions:
                raisons[p].append("condition")
            if p in self.valeurs_scripts or base_de.get(p) in self.valeurs_scripts:
                raisons[p].append("script")
            if len(par_base[base_de.get(p, p)]) > 1:
                raisons[p].append("variantes")      # base à plusieurs espèces sauvages : base de loupe ambiguë
            b = self.bases.get(base_de.get(p))
            if b is None or b["rang"] is None:
                raisons[p].append("sans_rang")
            # exigence de l'humain (2026-09-28) : D ne contient que des espèces recrutables normalement en combat sauvage
            if not self.recrutable(p):
                raisons[p].append("non_recrutable")    # taux d'amitié nul : ni nourriture ni amitié (Shogunyan…)
            if b is not None and b.get("legendaire"):
                raisons[p].append("legendaire")        # sceau du Médaillium ; aucune dans les rencontres sauvages
            if p in especes_evenement:
                raisons[p].append("evenement")         # Yo-kai d'évènement (combat du jour lancé par un dialogue)
        # format 5 (anti-softlock) : espèces exigées et leurs sources (évolution, fusion), membres des sceaux
        ferm = self.fermeture()
        for p in candidats:
            if p not in ferm:
                continue
            raisons[p] += [r for r in ferm[p] if r in RAISONS_FERMETURE]
            if not raisons[p]:                          # garde-fou : exigée sans aucune des raisons ci-dessus
                raisons[p].append("exigee:" + sorted(ferm[p])[0])
        return {p: sorted(set(r)) for p, r in raisons.items() if r}


def analyser(source: Source) -> Analyse:
    a = Analyse()
    for nom, carte, d in source.fichiers():
        a.lire(nom, carte, d)
    return a


def generer(romfs: str | Path, langues=LANGUES_DEFAUT) -> dict:
    """Base locale complète (dictionnaire JSON) depuis la ROM déchiffrée ou le dossier du RomFS du joueur."""
    return generer_avec_analyse(romfs, langues)[0]


def generer_avec_analyse(romfs: str | Path, langues=LANGUES_DEFAUT) -> tuple[dict, "Analyse", dict]:
    """(base locale, analyse, noms par langue) : pour l'audit (`--audit`) et les tests sur la vraie ROM."""
    src = Source(romfs)
    a = analyser(src)
    cite, sauvages = a.categoriser()
    w, raisons_w, wp, partages, partages_p, fixes = _variante(a, sauvages, False)
    exig = a.exigences()
    exigees = a.fermeture(exig)
    exig_boss = a.exigences_boss(exig)
    evt_renc, evt_esp = a.evenement()
    noms = {lg: src.noms(lg) for lg in langues}

    fichiers = sorted(a.tables)
    idx_fichier = {n: i for i, n in enumerate(fichiers)}
    refs = a.references()
    rencontres = []
    # format 7 : emplacements précis des lieux sauvages (point de loupe / chemin d'errants + condition), index globaux
    emplacements = sorted({x for h in sauvages for x in a.emplacements.get(h, ())})
    idx_emplacement = {x: i for i, x in enumerate(emplacements)}
    # format 9 : décors des emplacements de loupe (et des bases de loupe du mélange σ : points dont toutes les
    # rencontres sont dans W, ceux dont le jeu réécrit la base par β)
    decors_loupe = {}
    for i, (_c, m, f, n, _k) in enumerate(emplacements):
        if m == "loupe" and a.decors(f, n):
            decors_loupe[str(i)] = [list(x) for x in a.decors(f, n)]
    decors_bases = _decors_bases(a, w)
    for h in sorted(a.par_hachage):
        occ = a.par_hachage[h]
        cat = "sauvage" if h in sauvages else "+".join(sorted(cite.get(h, ()))) or "script_ou_aucune"
        sc = a.script(h)
        if sc:
            cat = "script_de_combat"
        e = {"h": h, "f": idx_fichier[occ[0][0]], "cat": cat,
             "c": [[k, p, niv, int((n, k) in partages), refs[(n, k)], j, int((n, k) in partages_p)]
                   for n, k, p, niv, j in a.combattants_places(h)]}
        # format 18 (force des boss adaptée) : multiplicateurs de stats v17..v21 et niveaux par rang v24..v29 (1re
        # définition ; les copies d'une même rencontre ont les mêmes champs)
        v0 = a.tables[occ[0][0]][0][occ[0][1]]
        mult = [x if isinstance(x, int) else 100 for x in v0[17:22]]
        if len(mult) == 5 and mult != [100] * 5:
            e["m"] = mult
        nr = [x if isinstance(x, int) else 0 for x in v0[24:30]]
        if any(nr):
            e["nr"] = nr
        if sc:
            e.update(s=sc[0], r=sc[1], fs=[idx_fichier[n] for n in sc[2]])
        elif len({n for n, _i in occ}) > 1:
            e["fs"] = sorted(idx_fichier[n] for n in {n for n, _i in occ})
        if h in sauvages:
            e["w"] = h in w
            e["lieux"], e["pos"], e["mom"] = a._lieux(h)
            if not e["w"]:
                e["exclusion"] = sorted(set(raisons_w.get(h, ["?"])))
            e["em"] = sorted(idx_emplacement[x] for x in a.emplacements.get(h, ()))
            if h in wp:
                e["wp"] = True
        rencontres.append(e)
    melange2 = _melange2(a, sauvages, rencontres, w, fixes, decors_bases)
    invitees, ecartees = a.invitees(sauvages)
    especes = {}
    # (les invitées sont déjà des combattants de rencontres scénarisées sur la ROM : l'union ne change rien)
    for p in sorted({c[1] for e in rencontres for c in e["c"]} | set(fixes) | set(exigees) | evt_esp | set(invitees)):
        b = a.param_base.get(p)
        info = a.bases.get(b, {})
        especes[str(p)] = {"base": b, "rang": info.get("rang"), "tribu": info.get("tribu"),
                           "loupe": a.loupe_masques.get(b, 0),
                           "medaille": a.param_medaille.get(p), "yokai": info.get("yokai", False),
                           "recrutable": a.recrutable(p), "rare": bool(info.get("rare")),
                           "amitie": a.quartets_amitie(p),
                           "aliment": info.get("aliment", 0),
                           "legendaire": bool(info.get("legendaire")),
                           "noms": {lg: noms[lg].get(info.get("nom"), "") for lg in langues}}
        if p in a.param_stats:
            especes[str(p)]["stats"] = a.param_stats[p]          # format 18 : v2..v11 (force des boss adaptée)
    base = {
        "format": FORMAT,
        "genere": datetime.datetime.now().isoformat(timespec="seconds"),
        "empreinte_romfs": src.empreinte.hexdigest(),
        "fichiers": fichiers,
        "rencontres": rencontres,
        "especes": especes,
        "fixees": {str(p): r for p, r in sorted(fixes.items())},
        # format 5 : toutes les espèces exigées (quêtes, histoire, Tablo-blabla, PNJ, sceaux…) et leurs sources
        # (évolution, fusion), sauvages ou non ; le mélange des boss n'échange jamais un boss qui en contient une
        "exigees": {str(p): sorted(r) for p, r in sorted(exigees.items())},
        "exigees_boss": {str(p): r for p, r in sorted(exig_boss.items())},
        "bases_loupe": sorted({b for _f, b, rs in a.points if rs and all(h in w for h in rs)}),
        # format 6 : Yo-kai d'évènement (combats du jour lancés par un dialogue) : jamais dans W, D ni le mélange des
        # boss (le client les ajoute à F par défense en profondeur)
        "evenement": {"rencontres": sorted(evt_renc), "especes": sorted(evt_esp)},
        # format 7 (mélange par rencontre, archipelago_rando_yokai.md §11) : emplacements [carte, méthode, n° dans le
        # fichier, condition décodée] (index de `em` des rencontres sauvages) ; 6e élément des combattants = place j,
        # 7e = partagé avec une rencontre hors de W' (`wp` des rencontres sauvages)
        "emplacements": [[c, m, i, json.loads(k)] for c, m, _f, i, k in emplacements],
        # format 9 (loupe jamais vide, §14) : décors [positions réelles, positions de WM_MAP_ATTR] par emplacement de
        # loupe (index de `emplacements`) et par base de loupe du mélange σ ; `loupe` des espèces = masque WM_YOKAI_INFO
        "decors_loupe": decors_loupe,
        "decors_bases": {str(b): [list(x) for x in sorted(v)] for b, v in sorted(decors_bases.items())},
        # format 10 (facilité d'amitié affichée par le lanceur, §15.5) : table des taux ; `amitie` des espèces = n° de
        # ligne pour k = 0..5 Yo-kai de même base déjà possédés. Lu par le tracker seulement (mélange inchangé).
        "amitie": a.table_amitie(),
        # format 11 (§16) : `lieux` des rencontres = méthode « portail » pour un lieu venu d'un `_enc_pos_gate` (salle
        # d'un portail mystère : [carte, "portail", texte, condition du lieu ET de la salle, 1 = salle de
        # GATE_ENTER_INFO / 0 = non confirmé]) ; lieu de loupe : 5e élément = types de point (crc32 du nom du décor) ;
        # `aliment` des espèces = catégorie d'aliment préférée (1..19, 0 : aucune). Tracker seulement : `emplacements`,
        # W et mélanges inchangés.
        # format 12 (§18) : `pos` des rencontres sauvages = positions monde de chaque élément de `lieux` (loupe :
        # [x, z, type de point] ; errant / portail : [x, z]). Tracker seulement.
        # format 13 (§19) : `mom` des rencontres sauvages = masque de moments de chaque élément de `lieux` (1 jour
        # sec, 2 jour pluie, 4 nuit sec, 8 nuit pluie ; 0 : jamais dans cette version du jeu) ; point de loupe de
        # `pos` : [x, z, type de point, masque du point]. Tracker seulement.
        "version_jeu": VERSION_JEU,
        # format 14 (§20) : `melange2` = ce qui change dans les champs lus par le mélange quand les rencontres qui ne
        # sortent jamais dans cette version sont exclues de W (mélange version 2, graines nouvelles) ; les champs
        # ci-dessus restent ceux de la version 1 (graines anciennes : mélange et empreintes inchangés). Lu par
        # client/rando_yokai.vue_base.
        "melange2": melange2,
        # format 15 (§21) : `melange3` = rencontres sauvages qui ont au moins un lieu NORMAL (hors portail mystère, qui
        # sort dans cette version du jeu, d'avant la fin). Lu par la version 3 du mélange seulement (avec `melange2`) :
        # chaque espèce du réservoir y garde ou y reçoit un lieu normal. Versions 1 et 2 : rien de changé.
        "melange3": {"version": 3, "normales": sorted(h for h in sauvages if a.normale(h))},
        # format 16 (§22) : `melange4` = espèces INVITÉES (recrutables, absentes de toute rencontre sauvage : armées du
        # chapitre 8 et leurs proches) que la version 4 du mélange ajoute au réservoir ; `ecartees` : n° du Médaillium
        # de la liste que cette ROM ne confirme pas, avec la raison. Versions 1 à 3 : rien de changé.
        "melange4": {"version": 4, "invitees": invitees, "ecartees": ecartees},
        # format 17 : `melange5` = périmètre « partout » du mélange version 5 (deux périmètres : sans et avec les
        # rencontres sauvages d'après-jeu) ; versions 1 à 4 : rien de changé
        "melange5": _melange5(a, sauvages, cite, rencontres, melange2, len(emplacements)),
        # format 19 (V3, lot M2a-bis) : `melange6` = même schéma pour la version 6 (rencontres des spots en plus) ;
        # versions 1 à 5 : rien de changé
        "melange6": _melange5(a, sauvages, cite, rencontres, melange2, len(emplacements), version=6),
    }
    return base, a, noms


def _variante(a: "Analyse", sauvages: set[int], mortes: bool):
    """(W, raisons d'exclusion, W', partages relatifs à W, à W', espèces fixées) ; `mortes` : mélange version 2."""
    w, raisons_w = a.exclure(sauvages, mortes)
    partages = a.partages(w)
    # format 7 : W' du mélange par rencontre (§11) = W + les rencontres exclues SEULEMENT pour la base de loupe du
    # mélange σ (premier_partage, point_mixte) : le mélange par rencontre garde alors le 1er combattant tel quel
    wp = w | {h for h in sauvages if raisons_w.get(h) and set(raisons_w[h]) <= RAISONS_W_PRIME}
    partages_p = a.partages(wp)
    candidats = {p for h in w for n, k, p, _l in a.combattants(h) if (n, k) not in partages}
    return w, raisons_w, wp, partages, partages_p, a.fixer(candidats)


def _decors_bases(a: "Analyse", w: set[int]) -> dict[int, set]:
    out: dict[int, set] = {}
    for (f, b, rs), n in zip(a.points, a.points_n):
        if rs and all(h in w for h in rs):
            out.setdefault(b, set()).update(a.decors(f, n))
    return out


def _melange2(a: "Analyse", sauvages: set[int], rencontres: list[dict], w1: set[int], fixes: dict,
              decors_bases: dict) -> dict:
    """Bloc `melange2` de la base (format 14, §20) : différences avec la version 1, calculées par les MÊMES expressions.
    `rencontres` : {hachage : {w, wp, exclusion, p (partagé W par combattant), pp (partagé W')}} pour les seules
    rencontres sauvages dont l'un de ces champs change ; `fixees`, `bases_loupe`, `decors_bases` : valeurs complètes de
    la version 2 (absentes si identiques à la version 1) ; `mortes` : les rencontres exclues pour cette raison."""
    w, raisons_w, wp, partages, partages_p, fixes2 = _variante(a, sauvages, True)
    assert w <= w1, "W de la version 2 hors de W"
    diff = {}
    for e in rencontres:
        h = e["h"]
        if h not in sauvages:
            continue
        cs = a.combattants_places(h)
        v1 = (bool(e["w"]), bool(e.get("wp")), e.get("exclusion", []), [c[3] for c in e["c"]], [c[6] for c in e["c"]])
        v2 = (h in w, h in wp, [] if h in w else sorted(set(raisons_w.get(h, ["?"]))),
              [int((n, k) in partages) for n, k, _p, _niv, _j in cs],
              [int((n, k) in partages_p) for n, k, _p, _niv, _j in cs])
        if v1 != v2:
            diff[str(h)] = dict(zip(("w", "wp", "exclusion", "p", "pp"), v2))
    out = {"version": 2, "mortes": sorted(h for h in sauvages if RAISON_MORTE in raisons_w.get(h, ())),
           "rencontres": diff}
    f2 = {str(p): r for p, r in sorted(fixes2.items())}
    if f2 != {str(p): r for p, r in sorted(fixes.items())}:
        out["fixees"] = f2
    bl1 = sorted({b for _f, b, rs in a.points if rs and all(h in w1 for h in rs)})
    bl2 = sorted({b for _f, b, rs in a.points if rs and all(h in w for h in rs)})
    if bl1 != bl2:
        out["bases_loupe"] = bl2
    db2 = _decors_bases(a, w)
    if db2 != decors_bases:
        out["decors_bases"] = {str(b): [list(x) for x in sorted(v)] for b, v in sorted(db2.items())}
    return out


def _melange5(a: "Analyse", sauvages: set[int], cite: dict, rencontres: list[dict], melange2: dict,
              nb_emplacements: int, version: int = 5) -> dict:
    """Bloc `melange5` de la base (format 17). Par périmètre (« base », « apres_jeu ») : `wp` = W' de la version 5
    (hachages triés), `pp` = drapeaux « partagé » de chaque combattant (ordre de `c`) des rencontres de ce W' (cité
    aussi par une rencontre hors de ce W' du même fichier : le jeu ne le réécrit pas), `fixees` = espèces fixées
    parmi ses combattants modifiables (`Analyse.fixer`), `exclusion` = raisons des rencontres sauvages ou des
    catégories de AJOUTS5 hors de ce W', `ajouts` = catégorie des rencontres de ce W' absentes du W' de la version 4
    (« histoire », « apres_jeu », « coffre », « train », « gymnase »). Commun : `normales` = rencontres à lieu normal de
    la version 5 (celles de la version 3, moins les rencontres sans amitié ; une rencontre sauvage ajoutée ne l'est
    que par un lieu PERMANENT, `lieu_permanent5`), `sans_amitie` = rencontres sauvages à règle « pas d'amitié » (leurs
    combattants ne rendent aucune espèce présente), `emplacements` = emplacement VIRTUEL (index à partir du nombre
    d'emplacements de la base) de chaque rencontre non sauvage des W' : une espèce exigée en possession y reste comme
    à un point de loupe. `version` 6 : bloc `melange6` (même schéma ; catégorie « spot » en plus, `exclure5`)."""
    d2 = melange2.get("rencontres", {})
    w4 = {e["h"] for e in rencontres if "w" in e and d2.get(str(e["h"]), e).get("wp")}
    normales3 = {h for h in sauvages if a.normale(h)}
    sans = {h for h in sauvages if a.sans_amitie(h)}
    out: dict = {"version": version, "perimetres": {}, "sans_amitie": sorted(sans)}
    nouvelles: set[int] = set()
    virtuels: set[int] = set()
    for nom in PERIMETRES5:
        wp, raisons, cats = a.exclure5(sauvages, cite, nom == "apres_jeu", version)
        assert w4 <= wp, "W' de la version 5 sans une rencontre du W' de la version 4"
        partages = a.partages(wp)
        cand = {p for h in wp for n, k, p, _l in a.combattants(h) if (n, k) not in partages}
        ajouts = {}
        for h in sorted(wp - w4):
            if h in cats:
                ajouts[str(h)] = cats[h]
                virtuels.add(h)
            else:
                hors = [lieu_hors_avant_fin(l[0], json.loads(l[4])) for l in a.lieux.get(h, ())]
                ajouts[str(h)] = "apres_jeu" if hors and all(hors) else "histoire"
                if nom == "base":
                    nouvelles.add(h)
        out["perimetres"][nom] = {
            "wp": sorted(wp),
            "pp": {str(h): [int((n, k) in partages) for n, k, _p, _niv, _j in a.combattants_places(h)]
                   for h in sorted(wp)},
            "fixees": {str(p): r for p, r in sorted(a.fixer(cand).items())},
            "exclusion": {str(h): r for h, r in sorted(raisons.items())},
            "ajouts": ajouts}

    def permanente(h: int) -> bool:
        lieux, _pos, mom = a._lieux(h)
        return any(l[1] != METHODE_PORTAIL and m and lieu_hors_avant_fin(l[0], l[3]) is None
                   and Analyse.lieu_permanent5(l[3]) for l, m in zip(lieux, mom))
    out["normales"] = sorted(h for h in normales3 - sans if h not in nouvelles or permanente(h))
    out["emplacements"] = {str(h): nb_emplacements + i for i, h in enumerate(sorted(virtuels))}
    return out


def ecrire(base: dict, dossier: str | Path) -> Path:
    """Écrit `yokai_local.json` (atomique) dans le dossier de données du client."""
    d = Path(dossier)
    d.mkdir(parents=True, exist_ok=True)
    p = d / NOM_FICHIER
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(base, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    os.replace(tmp, p)
    return p


def generer_fichier(romfs: str | Path, dossier: str | Path, langues=LANGUES_DEFAUT) -> Path:
    return ecrire(generer(romfs, langues), dossier)


def charger(dossier: str | Path) -> dict | None:
    """Base locale d'un format lisible (`FORMATS_LUS`), ou None."""
    p = Path(dossier) / NOM_FICHIER
    try:
        b = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return b if isinstance(b, dict) and b.get("format") in FORMATS_LUS else None


def a_refaire(dossier: str | Path) -> bool:
    """Base absente, illisible ou d'un format antérieur (format 1 : n° du Médaillium faux, lieux sans condition
    décodée ; format 2 : espèces non recrutables dans D) : à régénérer depuis la ROM du joueur."""
    p = Path(dossier) / NOM_FICHIER
    try:
        b = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return True
    return not isinstance(b, dict) or not isinstance(b.get("format"), int) or b["format"] < FORMAT


def rapport(base: dict, langue: str = "fr") -> str:
    """Espèces fixées par raison, rencontres exclues par raison (console seulement : noms du jeu)."""
    esp = base["especes"]

    def nom(p):
        e = esp.get(str(p), {})
        return "%s (0x%08X, rang %s)" % (e.get("noms", {}).get(langue) or "?", int(p),
                                        RANGS[e["rang"]] if isinstance(e.get("rang"), int) and 0 <= e["rang"] < 6
                                        else "?")
    lignes = []
    w = [e for e in base["rencontres"] if e.get("w")]
    sauv = [e for e in base["rencontres"] if "w" in e]
    cand = {c[1] for e in w for c in e["c"] if not c[3]}
    fixes = {int(p): r for p, r in base["fixees"].items()}
    d = sorted(cand - set(fixes))
    lignes.append(f"Rencontres sauvages : {len(sauv)} ; dans W : {len(w)} ; espèces de W : {len(cand)} ; "
                  f"fixées : {len(fixes)} ; domaine D : {len(d)}")
    ex = collections.Counter(r for e in sauv if not e.get("w") for r in e.get("exclusion", []))
    lignes.append("Rencontres sauvages exclues de W, par raison : " + ", ".join(f"{k} {v}" for k, v in ex.most_common()))
    m2 = base.get("melange2")
    if isinstance(m2, dict):
        d2 = m2.get("rencontres", {})
        lignes.append(f"Mélange version 2 (§20, graines nouvelles) : {len(m2.get('mortes', []))} rencontres sauvages ne "
                      f"sortent jamais dans cette version du jeu (exclues de W et de W', raison {RAISON_MORTE}) ; W : "
                      f"{len(w) - sum(1 for e in w if not d2.get(str(e['h']), {'w': True})['w'])} rencontres ; "
                      f"{len(d2)} rencontres à champs différents ; fixées "
                      f"{'identiques' if 'fixees' not in m2 else 'DIFFÉRENTES'}")
    m3 = base.get("melange3")
    if isinstance(m3, dict):
        nor = {int(h) for h in m3.get("normales", [])}
        esp_n = {c[1] for e in sauv if e["h"] in nor for c in e["c"]}
        seul = {c[1] for e in sauv for c in e["c"]} - esp_n
        lignes.append(f"Mélange version 3 (§21) : {len(nor)} rencontres sauvages à lieu normal (hors portail mystère, "
                      f"qui sort, d'avant la fin) sur {len(sauv)} ; dans W : {sum(1 for e in w if e['h'] in nor)} ; "
                      f"espèces sauvages sans aucun lieu normal dans le jeu d'origine : {len(seul)}")
    m4 = base.get("melange4")
    if isinstance(m4, dict):
        lignes.append(f"Mélange version 4 (§22) : {len(m4.get('invitees', []))} espèces invitées (recrutables, dans "
                      f"aucune rencontre sauvage) ; écartées : {m4.get('ecartees') or 'aucune'}")
        lignes += ["   " + nom(p) + f" ; amitié {esp.get(str(p), {}).get('amitie')} ; masque de loupe "
                   f"{esp.get(str(p), {}).get('loupe', 0):#x}" for p in m4.get("invitees", [])]
    if base.get("format", 0) >= 7:
        lignes.append(f"W' (mélange par rencontre, §11 : W + exclues seulement pour la base de loupe σ) : "
                      f"{sum(1 for e in sauv if e.get('wp'))} rencontres")
    par_raison = collections.defaultdict(list)
    for p, rs in fixes.items():
        for r in rs:
            par_raison[r].append(p)
    for r in sorted(par_raison):
        lignes.append(f"-- F : {r} ({len(par_raison[r])})")
        lignes += ["   " + nom(p) for p in sorted(par_raison[r], key=lambda x: nom(x))]
    rangs = collections.Counter(esp[str(p)]["rang"] for p in d)
    lignes.append("D par rang : " + ", ".join(f"{RANGS[k]} {rangs[k]}" for k in range(6)))
    if base.get("format", 0) < 3:
        lignes.append("Recrutement en combat : base d'un format antérieur (champ absent), à régénérer")
        return "\n".join(lignes)
    nr = [p for p in d if not esp[str(p)].get("recrutable")]
    lignes.append(f"Espèces non recrutables dans D : {len(nr)} (doit être 0)")
    sauv_nr = sorted({c[1] for e in sauv for c in e["c"] if not esp.get(str(c[1]), {}).get("recrutable")})
    lignes.append(f"Espèces des rencontres sauvages non recrutables en combat : {len(sauv_nr)} ([W] : fixées ; les "
                  "autres sont hors W)")
    lignes += ["   " + nom(p) + (" [W]" if p in cand else "") for p in sorted(sauv_nr, key=lambda x: nom(x))]
    rares = [p for p in d if esp[str(p)].get("rare")]
    lignes.append(f"Espèces rares dans D (recrutables en combat sauvage) : {len(rares)}")
    if base.get("format", 0) < 5:
        lignes.append("Espèces exigées et leurs sources : base d'un format antérieur (champ absent), à régénérer")
        return "\n".join(lignes)
    ex = {int(p) for p in base["exigees"]}
    lignes.append(f"Espèces exigées par le jeu + leurs sources (évolution, fusion) : {len(ex)} ; dans W : "
                  f"{len(ex & cand)} ; dans D : {len(ex & set(d))} (doit être 0) ; qui figent un boss : "
                  f"{len(base.get('exigees_boss', {}))}")
    if base.get("format", 0) >= 6:
        hors = [e for e in sauv if {"apres_jeu", "hors_partie"} & set(e.get("exclusion", []))]
        ids_hors = {int(e["h"]) for e in hors}
        esp_hors = {c[1] for e in hors for c in e["c"]} - {c[1] for e in sauv if int(e["h"]) not in ids_hors
                                                           for c in e["c"]}
        lignes.append(f"Périmètre avant l'après-jeu : rencontres sauvages exclues (après-jeu / hors partie normale) : "
                      f"{len(hors)} ; espèces qu'on ne trouve (en sauvage) que là : {len(esp_hors)} ; dans D : "
                      f"{len(esp_hors & set(d))} (doit être 0)")
        evt = base.get("evenement", {})
        ee, er = {int(p) for p in evt.get("especes", [])}, {int(h) for h in evt.get("rencontres", [])}
        lignes.append(f"-- evenement : {len(ee)} espèces (toutes variantes), {len(er)} rencontres ; rencontres dans W : "
                      f"{len(er & {int(e['h']) for e in w})} ; espèces dans D : {len(ee & set(d))} (doivent être 0)")
        lignes += ["   " + nom(p) for p in sorted(ee, key=lambda x: nom(x))]
    don = _donnees_boss(base)
    if don is not None:
        figes = sorted([f"{don.boss[k].nom} ({', '.join(r)})" for k, r in don.figes.items()]
                       + [f"{don.noms_sans_script[p]} ({', '.join(r)})" for p, r in don.figes_n.items()])
        lignes.append(f"Boss figés (ni déplacés ni remplacés par le mélange des boss) : {len(figes)}")
        lignes += ["   " + x for x in figes]
    return "\n".join(lignes)


def _module_client(nom: str):
    racine = Path(__file__).resolve().parents[1] / "client"
    if str(racine) not in sys.path:
        sys.path.insert(0, str(racine))
    return __import__(nom)


def _module_zones():
    """Table des zones des Yo-kai demandés de l'APWorld distribué à côté (`apworld/yokaiwatch2/zones.py`), ou None."""
    import importlib
    import types
    nom = "ykw2_apworld_pur"
    if nom not in sys.modules:
        p = types.ModuleType(nom)
        p.__path__ = [str(Path(__file__).resolve().parents[1] / "apworld" / "yokaiwatch2")]
        sys.modules[nom] = p
    try:
        return importlib.import_module(nom + ".zones")
    except Exception:  # noqa: BLE001
        return None


def audit_par_rencontre(base: dict, noms_especes, graines: int = 20, version: int = 1,
                        apres_jeu: bool = False) -> tuple[list[str], int]:
    """Audit du mélange PAR RENCONTRE (client/rando_yokai.py, archipelago_rando_yokai.md §11) : pour chaque espèce d'un
    combattant modifiable de W exigée par le jeu, sa politique (« tout » : tous ses combattants gardés ; « emplacements » :
    elle reste à chacun de ses emplacements d'origine) vérifiée sur les combattants gardés, puis sur `graines` graines x
    2 modes : aucun combattant gardé changé, chaque emplacement d'origine d'une espèce « emplacements » la contient
    encore, chaque espèce du réservoir trouvable avant la fin, les 1ers combattants d'un point de loupe d'une même base,
    classe (rang) respectée, et (format 9, §14) aucun point de loupe dont le 1er combattant reçoit une espèce que la loupe
    ne peut pas montrer dans son décor (« Il n'y a rien ici » alors que le radar vise le point) ; même contrôle pour les
    bases β des modes σ. `version` : version du mélange (§20) ; version 2 : une rencontre qui ne sort jamais dans
    cette version du jeu n'est ni dans W ni comptée comme emplacement ou source ; version 3 (§21) : en plus, chaque
    espèce du réservoir (de D pour les modes σ) est dans une rencontre à lieu NORMAL, sauf repli annoncé par le mélange
    (`sans_normal`, compté et affiché ; un écart entre l'annonce et le constat est un trou) ; version 4 (§22) : les
    espèces invitées sont dans le réservoir (mêmes contrôles), celles que le mélange n'a placées nulle part sont
    comptées (annonce = constat) ; modes σ : σ injective, images dans D ou invitées, rang respecté, une espèce de D
    évincée (plus l'image de personne) garde un lieu normal ; version 5 (« partout », périmètre `apres_jeu`) : les
    rencontres non sauvages du W' (coffres, trains, gymnase : emplacements virtuels) gardent leurs espèces exigées,
    une espèce n'est « trouvable » que dans une rencontre où l'amitié est possible, une espèce de rang A ou S peut
    changer de classe, et la table des espèces tient dans la boîte (borne structurelle). Renvoie (lignes, trous)."""
    try:
        ry = _module_client("rando_yokai")
        brute = base
        base = ry.vue_base(base, version, apres_jeu)
        don = ry.DonneesRencontre.depuis(base, version, apres_jeu)
        zmod, liberes, zone_de = None, frozenset(), {}
        if version >= ry.VERSION_ZONES:
            # version 7 (zones des Yo-kai demandés, lots M2b) : TOUS les Yo-kai demandés reçoivent une zone à chaque
            # graine : leurs espèces sont libérées (constantes) ; zones tirées comme à la génération
            zmod = _module_zones()
            if zmod is None:
                raise RuntimeError("table des zones de l'APWorld absente")
            tout = ry.zones_client({d["medaille"]: next(iter(zmod.ZONES)) for d in zmod.DEMANDES},
                                   zmod.cartes_par_zone(), zmod.K)
            liberes = frozenset(p for _m, p, _z in ry.cibles_zones(base, don, tout))
            zone_de = {p: m for m, p, _z in ry.cibles_zones(base, don, tout)}
            don = ry.DonneesRencontre.depuis(base, version, apres_jeu, liberes=liberes)
    except Exception as e:  # noqa: BLE001
        return [f"=== Mélange par rencontre (version {version}) : non vérifié ({e}) ==="], 1
    exi = {int(p): r for p, r in base.get("exigees", {}).items()}
    fix = {int(p): r for p, r in base.get("fixees", {}).items()}
    out = [f"=== Mélange par rencontre (§11), version {version} du mélange (§20)"
           + (f", périmètre {don.perimetre}" if version >= 5 else "")
           + " : politique des espèces exigées des combattants modifiables ==="]
    trous = 0
    if version >= 5:
        ajouts = collections.Counter(c for c in ((ry.bloc_partout(base, version) or {}).get("perimetres") or {}).get(
            don.perimetre, {}).get("ajouts", {}).values())
        orig_mod = {p for r, p in don.origine.items() if r not in don.gardes}
        borne = len(set(don.reservoir) | orig_mod)
        # version 6 (spots) : table des espèces étendue (ids en jeu sur 9 bits) ; les espèces d'ORIGINE (id sur 8 bits)
        # doivent tenir dans les CAP_ESPECES premières
        cap = ry.CAP_ESPECES_ETENDU if version >= 6 else ry.CAP_ESPECES
        out.append(f"   « partout » : W' {len(don.w)} rencontres (ajoutées : " + ", ".join(
            f"{k} {v}" for k, v in sorted(ajouts.items())) + f") ; réservoir {len(don.reservoir)} ; rencontres sans "
            f"amitié possible : {len(don.sans_amitie)} ; borne de la table des espèces {borne} / {cap}"
            + (f" (espèces d'origine {len(orig_mod)} / {ry.CAP_ESPECES})" if version >= 6 else ""))
        if borne > cap or len(orig_mod) > ry.CAP_ESPECES or any(
                int(e["h"]) in don.sans_amitie for e in base["rencontres"] if e.get("wp")):
            out.append("   TROU : table des espèces trop grande, ou rencontre sans amitié dans W'")
            trous += 1
    if version != 1:
        mortes = [e for e in base["rencontres"] if "w" in e and ry.morte(e)]
        dans = [e for e in mortes if e.get("w") or e.get("wp") or int(e["h"]) in don.w]
        out.append(f"   rencontres qui ne sortent jamais dans cette version du jeu : {len(mortes)} ; dans W ou W' : "
                   f"{len(dans)} (doit être 0)")
        trous += bool(dans)
    pol = collections.Counter(don.politiques[p] for p in don.politiques if p in exi or p in fix)
    out.append("   " + ", ".join(f"{k} {v}" for k, v in sorted(pol.items())) + f" ; combattants gardés "
               f"{len(don.gardes)} / {len(don.origine)} (" + ", ".join(
                   f"{k} {v}" for k, v in sorted(collections.Counter(don.gardes.values()).items())) + ")")
    par_espece = collections.defaultdict(list)
    for r, p in don.origine.items():
        par_espece[p].append(r)
    for p, rs in sorted(par_espece.items()):
        exigee = p in exi or bool(set(fix.get(p, ())) - {"non_recrutable", "legendaire", "evenement", "variantes"})
        if version >= 6:          # version 6 : une espèce citée seulement par les dialogues des spots est libérée
            exigee = bool(ry.categories_exigence(set(exi.get(p, ())) | set(fix.get(p, ())), version))
        if not exigee or p in liberes:           # (version 7 : Yo-kai demandé placé dans sa zone, contrôlé plus bas)
            continue
        if don.politiques[p] == "libre":
            out.append(f"   TROU : espèce exigée {noms_especes(p)} libre")
            trous += 1
        elif don.politiques[p] == "tout":
            manque = [r for r in rs if r not in don.gardes]
            if manque:
                out.append(f"   TROU : {noms_especes(p)} : {len(manque)} combattant(s) non gardé(s)")
                trous += 1
        else:
            besoin = set().union(*(don.emplacements_de[r] for r in rs)) - don.couverts.get(p, set())
            garde = set().union(*(don.emplacements_de[r] for r in rs if r in don.gardes), set())
            if besoin - garde:
                out.append(f"   TROU : {noms_especes(p)} : {len(besoin - garde)} emplacement(s) d'origine perdus")
                trous += 1
    sauv = [e for e in base["rencontres"] if "w" in e]
    bruts = [e for e in brute["rencontres"] if "w" in e]
    vivantes = [e for e in sauv if ry.RAISON_MORTE not in e.get("exclusion", ())]
    if version >= 5:          # emplacements virtuels des rencontres non sauvages du W' (coffres, trains, gymnase)
        vivantes += [e for e in base["rencontres"] if "w" not in e and e.get("wp")]
        sauv_v5 = sauv + [e for e in base["rencontres"] if "w" not in e and e.get("wp")]
        bruts_v5 = [e for e in brute["rencontres"] if "w" in e or int(e["h"]) in set(don.w)]
    else:
        sauv_v5, bruts_v5 = sauv, bruts
    normales = ry.normales_de(base, version)               # version 3 (§21) ; vide avant
    orig_n = {int(c[1]) for e in sauv if int(e["h"]) in normales for c in e["c"]}
    replis = collections.Counter()
    if version >= 3:
        out.append(f"   lieu normal (§21) : {len(normales)} rencontres à lieu normal ; combattants modifiables dans "
                   f"l'une d'elles {len(don.normaux)} / {len(don.origine)} ; réservoir sans lieu normal dans le jeu "
                   f"d'origine : {len(set(don.reservoir) - orig_n)} ; sans lieu normal hors tirage : "
                   f"{len(set(don.reservoir) - don.presentes_normales)}")
    inv_abs = collections.Counter()
    if version >= 4:
        deja = {int(c[1]) for e in sauv for c in e["c"]} & don.invitees
        out.append(f"   espèces invitées (§22) : {len(don.invitees)} (réservoir : {len(don.reservoir)}) ; par rang : "
                   + ", ".join(f"{RANGS[k]} {v}" for k, v in sorted(collections.Counter(
                       don.reservoir[p] for p in don.invitees).items()))
                   + f" ; montrables par la loupe (masque WM_YOKAI_INFO) : "
                   f"{sum(1 for p in don.invitees if don.masques.get(p))} ; déjà sauvages : {len(deja)} (doit être 0)")
        trous += bool(deja)
    stats = collections.defaultdict(list)
    p_max: dict[str, int] = {}
    loupe = collections.defaultdict(lambda: [0, 0, 0, 0])      # points changés / incompatibles, sans puis avec le décor
    sans_info = sum(1 for p in don.reservoir if not don.masques.get(p))
    contraints = sum(1 for d in don.decors if d)
    out.append(f"   loupe (§14) : {len(don.points)} points à 1er combattant modifiable ; {contraints} groupes contraints "
               f"par un décor sur {len(don.groupes)} ; espèces du réservoir sans WM_YOKAI_INFO : {sans_info} / "
               f"{len(don.reservoir)} (jamais 1er combattant d'un point de loupe)")
    zones_ok = collections.Counter()
    if zmod is not None:
        out.append(f"   zones (version 7) : {len(liberes)} Yo-kai demandés libérés, {len(zmod.ZONES)} zones, K = "
                   f"{zmod.K}, plafonds " + ", ".join(f"{r} {zmod.plafond(r)}" for r in sorted(zmod.ZONES)))
    for mode in ry.MODES_RENCONTRE:
        for g in range(graines):
            import random as _random
            zc = ry.zones_client(zmod.tirer(_random.Random(g)), zmod.cartes_par_zone(), zmod.K) if zmod else None
            m = ry.calculer(brute, g, mode, None, version=version, apres_jeu=apres_jeu, zones=zc)
            stats[mode].append(m.stats["rencontres_changees"] / max(1, len(m.w)))
            avant = ry._calculer_par_rencontre(brute, g, mode, None, loupe=False, version=version,
                                               apres_jeu=apres_jeu, zones=zc).affectation
            vides = ry.points_incompatibles(don, m.affectation)
            for k, aff in ((0, avant), (2, m.affectation)):
                loupe[mode][k] += sum(1 for rs, _d in don.points.values() if any(r in aff for r in rs))
            loupe[mode][1] += len(ry.points_incompatibles(don, avant))
            loupe[mode][3] += len(vides)
            en_jeu = {(int(e["f"]), int(c[0])): m.en_jeu(e, c) for e in sauv_v5 for c in e["c"]}
            # le mélange appliqué aux entrées BRUTES de la base (ce que fait le tracker du lanceur) = à la vue
            if en_jeu != {(int(e["f"]), int(c[0])): m.en_jeu(e, c) for e in bruts_v5 for c in e["c"]}:
                out.append(f"   TROU : graine {g} {mode} : la base brute et la vue ne donnent pas le même jeu")
                trous += 1
            changes = [r for r in don.gardes if en_jeu[r] != don.origine[r]]
            present = {p: set() for p in don.politiques}
            for e in vivantes:                         # une rencontre qui ne sort jamais ne garde aucun emplacement
                for c in e["c"]:
                    present.setdefault(en_jeu[(int(e["f"]), int(c[0]))], set()).update(int(i) for i in e.get("em", ()))
            perdus = [p for p, rs in par_espece.items() if don.politiques[p] == "emplacements"
                      and set().union(*(don.emplacements_de[r] for r in rs)) - present.get(p, set())]
            trouvees = {en_jeu[(int(e["f"]), int(c[0]))] for e in sauv if ry.avant_fin(e)
                        and int(e["h"]) not in don.sans_amitie for c in e["c"]}
            absentes = set(don.reservoir) - trouvees
            if version >= 4:                           # invitée sans aucune place : repli annoncé, pas un trou
                constat = sorted(don.invitees - {x for x in en_jeu.values()})
                inv_abs[mode] += len(constat)
                if constat != m.invitees_absentes or sorted(don.invitees) != m.invitees:
                    out.append(f"   TROU : graine {g} {mode} : invitées absentes {len(constat)}, annoncées "
                               f"{len(m.invitees_absentes)}")
                    trous += 1
                absentes -= set(constat)
            if version >= 3:                           # constat indépendant = annonce du mélange
                sans = sorted(set(don.reservoir) - {en_jeu[(int(e["f"]), int(c[0]))] for e in sauv
                                                    if int(e["h"]) in normales for c in e["c"]})
                replis[mode] += len(sans)
                if sans != m.sans_normal:
                    out.append(f"   TROU : graine {g} {mode} : espèces sans lieu normal {len(sans)}, annoncées "
                               f"{len(m.sans_normal)}")
                    trous += 1
            if zmod is not None:
                # version 7 : chaque Yo-kai demandé à K unités ÉLIGIBLES (critère du client) de SA zone, distinctes, et
                # présent en jeu à des lieux de ces cartes ; constat indépendant de l'annonce du mélange
                defauts = []
                cartes = zc["cartes"]
                for p, med in zone_de.items():
                    z = zc["especes"].get(med)
                    annonce = m.zones.get(p)
                    if annonce is None or annonce[1] != z or len(annonce[2]) != zmod.K:
                        defauts.append(f"n° {med} : annonce {annonce}")
                        continue
                    en_zone = [e for e in sauv for c in e["c"]
                               if en_jeu[(int(e["f"]), int(c[0]))] == p and e.get("lieux") and all(
                                   l[0] in cartes[z] and l[1] in ("loupe", "errant")
                                   and ry.condition_temps_seulement(l[3])
                                   for l, mo in zip(e["lieux"], e.get("mom") or ()) if mo)]
                    # K unités annoncées, toutes dans la zone, et au moins K combattants en jeu de cette espèce
                    # à des lieux éligibles de la zone (après la réduction de la boîte)
                    if len({(int(e["f"]), int(c[0])) for e in sauv for c in e["c"]
                            if e in en_zone and en_jeu[(int(e["f"]), int(c[0]))] == p}) < zmod.K \
                            or not all(set(cs) <= set(cartes[z]) for cs in annonce[2]):
                        defauts.append(f"n° {med} : moins de {zmod.K} lieux dans sa zone {z}")
                if defauts:
                    out.append(f"   TROU : graine {g} {mode} : zones : " + " ; ".join(defauts[:5]))
                    trous += 1
                else:
                    zones_ok[mode] += 1
            hors = {x for r, x in m.affectation.items() if x not in don.reservoir}
            rang = [r for r, x in m.affectation.items() if ry.MODES_RENCONTRE[mode] == "rang"
                    and don.especes[x]["rang"] != don.especes[don.origine[r]]["rang"]
                    and not (version >= 5 and don.especes[x]["rang"] >= ry.RANG_HAUT)
                    and x not in liberes]               # (version 7 : Yo-kai demandé dans sa zone, rang libre)
            if version >= 5 and len(m.entrees) > ry.CAP_P_ETENDU:
                out.append(f"   TROU : graine {g} {mode} : {len(m.entrees)} entrées P")
                trous += 1
            p_max[mode] = max(p_max.get(mode, 0), len(m.entrees))
            incoherents = [g_ for g_ in don.groupes if len({m.affectation.get(r, don.origine[r]) for r in g_}) != 1]
            for nom_, liste in (("combattants gardés changés", changes), ("emplacements perdus", perdus),
                                ("espèces du réservoir introuvables", absentes), ("espèces hors réservoir", hors),
                                ("rangs changés", rang), ("groupes de loupe incohérents", incoherents),
                                ("points de loupe vides (espèce non posable dans le décor)", vides)):
                if liste:
                    out.append(f"   TROU : graine {g} {mode} : {len(liste)} {nom_}")
                    trous += 1
    for mode, v in stats.items():
        if version >= 5:
            out.append(f"   {mode} : entrées P au plus {p_max.get(mode, 0)} (boîte : {ry.CAP_P} sans l'extension du jeu, "
                       f"{ry.CAP_P_ETENDU} avec)")
        out.append(f"   {mode} : {graines} graines, rencontres de W changées {100 * min(v):.1f} % à {100 * max(v):.1f} %"
                   + (f" ; espèces du réservoir sans lieu normal (repli) : {replis[mode]} au total" if version >= 3
                      else "")
                   + (f" ; invitées sans aucune place : {inv_abs[mode]} au total" if version >= 4 else ""))
        if zmod is not None:
            out.append(f"      zones : {zones_ok[mode]} / {graines} graines, chaque Yo-kai demandé à {zmod.K} lieux "
                       "éligibles de sa zone")
        a, b, c, d = (x / graines for x in loupe[mode])
        out.append(f"      loupe : points à 1er combattant changé {c:.1f} par graine, VIDES {d:.1f} (doit être 0) ; sans "
                   f"la contrainte de décor (avant) : {a:.1f} changés, {b:.1f} vides")
    # modes σ : la base β(b) d'un point dont le jeu réécrit la base doit être posable dans les décors de b (version 5 :
    # mêmes σ que la version 4, déjà vérifiés)
    try:
        if version >= 5:
            raise StopIteration
        ds = ry.Donnees.depuis(base, version)
        for mode in ("par_rang", "total"):
            vides = paires = identites = sans_n = absentes_n = evincees_n = 0
            for g in range(graines):
                m = ry.calculer(brute, g, mode, None, version=version)
                paires += len(m.sigma)
                identites += len(ds.d) - len(m.sigma)
                if version >= 4:                       # §22 : σ n'est plus une permutation (invitées = images seules)
                    images = list(m.sigma.values())
                    partout = {m.en_jeu(e, c) for e in bruts for c in e["c"]}
                    evincees = sorted(set(m.sigma) - set(images))
                    defauts = [
                        ("σ non injective", len(images) != len(set(images))),
                        ("image hors de D et des invitées", bool(set(images) - set(ds.d) - set(ds.invitees))),
                        ("origine hors de D", bool(set(m.sigma) - set(ds.d))),
                        ("rang changé", mode == "par_rang" and any(
                            ds.d[x] != (ds.d.get(y, ds.invitees.get(y))) for x, y in m.sigma.items())),
                        ("invitées absentes ≠ annonce", sorted(set(ds.invitees) - partout) != m.invitees_absentes),
                        ("évincées ≠ annonce", evincees != m.evincees),
                        ("plus d'évincées que d'invitées placées",
                         len(evincees) != len(ds.invitees) - len(m.invitees_absentes))]
                    for texte, faux in defauts:
                        if faux:
                            out.append(f"   TROU : graine {g} {mode} : {texte}")
                            trous += 1
                    absentes_n += len(m.invitees_absentes)
                    evincees_n += len(evincees)
                if version >= 3:
                    vus = {m.en_jeu(e, c) for e in bruts if int(e["h"]) in normales for c in e["c"]}
                    sans = sorted((set(ds.d) | set(ds.invitees)) - vus)
                    sans_n += len(sans)
                    if sans != m.sans_normal:
                        out.append(f"   TROU : graine {g} {mode} : espèces de D sans lieu normal {len(sans)}, annoncées "
                                   f"{len(m.sans_normal)}")
                        trous += 1
                vides += sum(1 for x, y in m.sigma.items() if not ry.posable(ds.masques.get(y, 0), ds.decors.get(x, ())))
            out.append(f"   {mode} : {graines} graines, espèces déplacées {paires / graines:.1f} / {len(ds.d)}, bases de "
                       f"loupe non posables {vides} (doit être 0)"
                       + (f" ; espèces de D sans lieu normal (repli) : {sans_n} au total" if version >= 3 else "")
                       + (f" (invitées comprises) ; invitées sans aucune place : {absentes_n} au total ; espèces de D "
                          f"évincées (elles gardent un lieu normal) : {evincees_n}" if version >= 4 else ""))
            if vides:
                trous += 1
    except StopIteration:
        out.append(f"   modes σ : version {version} = version 4 (vérifiés avec elle)")
    except Exception as e:  # noqa: BLE001
        out.append(f"   TROU : modes σ non vérifiés ({e})")
        trous += 1
    return out, trous


def _donnees_boss(base: dict):
    """Boss du mélange (client/rando_boss.py, distribué à côté), ou None s'il est absent ou refuse la base."""
    racine = Path(__file__).resolve().parents[1] / "client"
    if str(racine) not in sys.path:
        sys.path.insert(0, str(racine))
    try:
        import rando_boss  # type: ignore[import-not-found]
        return rando_boss.DonneesBoss.depuis(base)
    except Exception:  # noqa: BLE001  (audit : le mélange des boss est facultatif)
        return None


def audit(a: Analyse, base: dict, noms: dict[int, str]) -> tuple[str, int]:
    """Audit anti-softlock (console seulement : noms du jeu) : fonctions de condition et instructions de script qui
    portent sur un Yo-kai, exigences par catégorie, puis pour CHAQUE espèce exigée (et chaque source d'une espèce exigée)
    toutes ses sources dans le jeu d'origine et ce que les deux mélanges en font. Renvoie (texte, nombre de trous) ; un
    trou = espèce exigée dans D (mélange des Yo-kai) ou boss non figé alors qu'il fournit une espèce exigée fortement."""
    yk = a.yokai()
    exig = a.exigences()
    ferm = a.fermeture(exig)
    fortes = a.exigences_boss(exig)
    w = {int(e["h"]) for e in base["rencontres"] if e.get("w")}
    sauvages = {int(e["h"]) for e in base["rencontres"] if "w" in e}
    cat_renc = {int(e["h"]): e["cat"] for e in base["rencontres"]}
    par_h = {int(e["h"]): e for e in base["rencontres"]}
    cand = {int(c[1]) for e in base["rencontres"] if e.get("w") for c in e["c"] if not c[3]}
    fixes = {int(p) for p in base["fixees"]}
    don = _donnees_boss(base)
    boss_de: dict[int, list[tuple[str, bool]]] = collections.defaultdict(list)      # espèce -> [(boss, figé)]
    if don is not None:
        for cle, b in don.boss.items():
            for e in set(b.membres) | {int(c[1]) for p in b.places for c in par_h[p]["c"]}:
                boss_de[e].append((b.nom, cle in don.figes))
        for p, e in don.sans_script.items():
            boss_de[e].append((don.noms_sans_script[p], p in don.figes_n))
    renc_de: dict[int, set[int]] = collections.defaultdict(set)
    for h in a.par_hachage:
        for _n, _k, p, _l in a.combattants(h):
            renc_de[p].add(h)
    evol_de: dict[int, list[tuple[int, int]]] = collections.defaultdict(list)
    for q, (f, i) in a.param_evolution.items():
        ev = a.evolutions.get(f, [])
        if 0 <= i < len(ev):
            evol_de[ev[i][1]].append((q, ev[i][0]))
    fusions_de = collections.defaultdict(list)
    for mats, (tr, res) in a.fusions:
        if tr == 0:
            fusions_de[res].append(mats)
    legendes = {leg for leg, _m in a.legendes}

    def nom(h: int) -> str:
        b = h if h in a.bases else a.param_base.get(h)
        n = noms.get(a.bases.get(b, {}).get("nom"), "") or "?"
        return f"{n} (0x{h:08X})"

    out: list[str] = ["=== Fonctions de condition dont un argument est un Yo-kai (toutes les tables) ==="]
    fn = collections.Counter(d.partition("@")[0] for h in set(a.conditions_detail) & yk for d in a.conditions_detail[h])
    out += [f"   {f} : {n} citations" for f, n in fn.most_common()]
    out.append("=== Instructions de script (.xq) dont un argument est un Yo-kai (hors dons AddPartyEx / AddParty) ===")
    ins = collections.Counter(c for h in a.valeurs_scripts & yk for c in a.scripts_detail.get(h, {"?"}))
    out += [f"   {c} : {n} espèces" for c, n in ins.most_common()]
    out.append("=== Exigences par catégorie (espèces désignées ; rencontres pour quete_rencontre) ===")
    par_cat = collections.defaultdict(set)
    for c, h, _o in exig:
        par_cat[c] |= {h} if c == "quete_rencontre" else a.especes_de(h)
    out += [f"   {c} : {len(v)}{' (faible)' if c in CATEGORIES_FAIBLES else ''}" for c, v in sorted(par_cat.items())]
    out.append(f"   fermeture (exigées + sources) : {len(ferm)} espèces ; exigées fortement pour les boss : {len(fortes)}")
    q4 = [h for c, h, _o in exig if c == "quete_rencontre"]
    trous = sum(1 for h in q4 if h in w)
    out.append(f"   rencontres exigées (type 4) dans W : {trous} (doit être 0)")

    ou_de = collections.defaultdict(set)
    for c, h, o in exig:
        if c != "quete_rencontre":
            for p in a.especes_de(h):
                ou_de[p].add(f"{c}{' : ' + o if o else ''}")
    par_base = collections.defaultdict(list)
    for p in ferm:
        par_base[a.param_base.get(p, p)].append(p)
    out.append("=== Espèces exigées (et sources), par base : exigences, sources dans le jeu d'origine, statut ===")
    for b in sorted(par_base, key=nom):
        out.append(f"-- {nom(b)}")
        for p in sorted(par_base[b]):
            raisons = sorted(ou_de.get(p, ())) or sorted(ferm[p])
            suite = f" (+{len(raisons) - 8})" if len(raisons) > 8 else ""
            out.append(f"   espèce 0x{p:08X}{' [recrutable]' if a.recrutable(p) else ''} : "
                       + " ; ".join(raisons[:8]) + suite)
            rs = renc_de.get(p, set())
            src = []
            if rs & w:
                src.append(f"sauvage dans W ×{len(rs & w)}")
            if rs & (sauvages - w):
                src.append(f"sauvage hors W ×{len(rs & (sauvages - w))}")
            autres = collections.Counter(cat_renc.get(h, "?") for h in rs - sauvages)
            src += [f"rencontre {k} ×{n}" for k, n in sorted(autres.items())]
            src += [f"boss {n}{' (figé)' if f else ''}" for n, f in boss_de.get(p, [])]
            src += ["Crank-a-kai"] * (p in a.capsules) + ["spot"] * (p in a.spots)
            src += ["don de script"] * (p in a.dons_sources or b in a.dons_sources)
            src += [f"évolution de {nom(q)} niv. {lv}" for q, lv in evol_de.get(p, [])]
            src += ["fusion " + " + ".join(nom(m) if t == 0 else f"objet 0x{m:08X}" for t, m in mats)
                    for mats in fusions_de.get(p, [])]
            src += ["sceau légendaire"] * (p in legendes)
            out.append("      sources : " + (", ".join(src) or "aucune lue"))
            statut = []
            if p in cand:
                statut.append("fixée (F)" if p in fixes else "TROU : dans D")
                trous += p not in fixes
            else:
                statut.append("hors du mélange sauvage")
            for n, f in boss_de.get(p, []):
                if p in fortes and not f:
                    statut.append(f"TROU : boss {n} non figé")
                    trous += 1
            out.append("      statut : " + ", ".join(statut))
    if don is not None:
        out.append("=== Boss figés : " + ", ".join(sorted([don.boss[k].nom for k in don.figes]
                                                        + [don.noms_sans_script[p] for p in don.figes_n])) + " ===")
    else:
        out.append("=== Boss : client/rando_boss.py absent ou base refusée : non vérifiés ===")
    versions = (1,)
    for v, bloc in ((2, "melange2"), (3, "melange3"), (4, "melange4"), (5, "melange5"), (6, "melange6"),
                    (7, "melange6")):
        if not isinstance(base.get(bloc), dict):
            break
        versions += (v,)
    for version in versions:
        for aj in ((False, True) if version >= 5 else (False,)):
            lignes, t2 = audit_par_rencontre(base, nom, version=version, apres_jeu=aj)
            out += lignes
            trous += t2
    out.append(f"=== Trous : {trous} (doit être 0) ===")
    return "\n".join(out), trous


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--romfs", required=True, help="ROM déchiffrée (.3ds/.cci/.cxi) ou dossier contenant yw2_a.fa")
    ap.add_argument("--sortie", help="dossier où écrire yokai_local.json (défaut : aucun fichier écrit)")
    ap.add_argument("--rapport", action="store_true", help="espèces fixées et exclusions par raison (console)")
    ap.add_argument("--audit", action="store_true",
                    help="audit anti-softlock complet : exigences, sources de chaque espèce exigée, trous (console)")
    ap.add_argument("--langues", default=",".join(LANGUES_DEFAUT))
    a = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    langues = tuple(x for x in a.langues.split(",") if x)
    base, analyse, noms = generer_avec_analyse(a.romfs, langues)
    if a.sortie:
        print("écrit :", ecrire(base, a.sortie))
    if a.rapport or (not a.sortie and not a.audit):
        print(rapport(base, langues[0]))
    if a.audit:
        texte, trous = audit(analyse, base, noms.get(langues[0], {}))
        print(texte)
        return 1 if trous else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
