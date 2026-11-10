"""Randomizer de Yo-kai (étape R3) : calcul du mélange σ, de W et de l'empreinte, commun au client, aux tests et au
tracker du lanceur (R5). Bibliothèque standard seulement.

Le mélange est calculé CHEZ LE JOUEUR, de façon déterministe, depuis :
- la graine de `slot_data["rando_yokai"]` (APWorld, 31 bits) et le mode (« par_rang » ou « total ») ;
- la base locale `yokai_local.json` (générée depuis la ROM du joueur par `archipelago/installation/rencontres.py`,
  jamais versionnée ni distribuée), qui donne les rencontres de W, le domaine D (rang de chaque espèce) et les
  espèces fixées F.
Même graine + même ROM (même empreinte) = même mélange chez tous les joueurs de la graine. Une base différente de la
référence (autre version du jeu, RomFS modifié) est REFUSÉE : le mélange serait différent de celui des autres joueurs.

Périmètre (base au format 6, doc §3.7) : W ne contient que des rencontres dont au moins un lieu est d'avant l'après-jeu,
D aucune espèce qu'on ne trouve qu'après la fin ni aucun Yo-kai d'évènement.
σ : permutation des espèces de D (hachages CHARA_PARAM) à l'intérieur d'une même classe (le rang E..S en mode
« par_rang », toutes ensemble en mode « total ») ; les espèces fixées F n'y sont jamais (ni départ ni arrivée). D ne
contient que des espèces RECRUTABLES en combat sauvage (nourriture acceptée, amitié possible : champ `recrutable` de
la base au format 3, doc §3.5) ; une base plus ancienne est refusée (à régénérer depuis la ROM).
β : même permutation sur les bases (CHARA_BASE) des espèces de D (Yo-kai montré par la loupe).
Modes « par rencontre » (`par_rencontre_rang`, défaut de l'APWorld depuis le 2026-09-30, et `par_rencontre_total` ;
base au format 7, boîte v10, doc §11) : chaque combattant modifiable de W' reçoit sa propre espèce du réservoir ; une
espèce exigée en possession reste à chacun de ses emplacements d'origine, une exigence de lieu ou non comprise garde
tous ses combattants ; voir la section « mélange par rencontre » plus bas.
Loupe jamais vide (base au format 9, doc §14) : une espèce que la loupe doit MONTRER à un point (1ers combattants des
rencontres d'un point de loupe ; image β d'une base de loupe pour les modes σ) n'est tirée que parmi celles que le décor
du point peut afficher (`posable` : masque `WM_YOKAI_INFO` de l'espèce / positions de Yo-kai du décor).
Version du mélange (§20) : l'ALGORITHME est choisi par la graine, pas par le client. Version 1 = graines d'avant le
2026-10-04 (`slot_data.rando_yokai.mode` = nom du mode seul) : calcul et empreintes inchangés pour toujours. Version 2
(mode « <nom>#2 », base au format 14) : les rencontres qui ne sortent jamais dans cette version du jeu (tous leurs
`mom` nuls) sont hors de W et de W' (`vue_base`). Une version inconnue de ce client est refusée (Yo-kai d'origine).
Version 3 (mode « <nom>#3 », base au format 15, §21) : la version 2, et chaque espèce du réservoir (de D pour les modes
σ) a au moins un lieu NORMAL : hors salle de portail mystère (§16), qui sort dans cette version du jeu, d'avant la fin
(bloc `melange3` de la base). Repli défini quand c'est impossible : `stats["sans_lieu_normal"]`, `Melange.sans_normal`.
Version 4 (mode « <nom>#4 », base au format 16, §22) : la version 3, et les espèces INVITÉES (bloc `melange4` : Yo-kai
recrutables qu'aucune rencontre sauvage ne contient, armées du chapitre 8 et leurs proches) entrent dans le réservoir
avec la même garantie d'un lieu normal ; les espèces du réservoir d'origine passent avant elles (couplage). Modes σ :
une invitée est seulement une IMAGE (σ n'est plus une permutation : pour chaque invitée placée, une espèce de D qui
garde un lieu normal sans réécriture cesse d'être une image). Le jeu ne change pas (il applique les tables écrites).
Référence : `docs/systemes/archipelago_rando_yokai.md` §3 et « Implémentation ».
"""
from __future__ import annotations

import collections
import hashlib
import json
import os
import random
import time
import zlib
import dataclasses
from dataclasses import dataclass, field
from pathlib import Path

FORMAT_BASE = 20                # (20 : les deux suivants ensemble, fusion de la force des boss et du lot M2a-bis ;
                                # 19 : bloc `melange6`, version 6 (spots), lu par la version 6 seulement ;
                                # 18 : stats et multiplicateurs, force des boss adaptée seulement : mélanges et
                                # empreintes inchangés ;
                                # 17 : bloc `melange5`, version 5 « partout », lu par la version 5 seulement ;
                                # 16 : bloc `melange4`, §22, lu par la version 4 seulement : versions 1 à 3 inchangées)
                                # format de yokai_local.json écrit par installation/rencontres.py (7 : emplacements ;
                                # 9 : masques et décors de loupe ; 8 : réservé à la branche ap/boss-adaptes ;
                                # 10 : taux d'amitié, pour le tracker seulement : mélanges et empreintes inchangés ;
                                # 11 : méthode « portail » des `lieux` (§16), tracker seulement : idem ;
                                # 12 : positions monde des lieux (`pos`, §18), tracker seulement : idem ;
                                # 13 : moments des lieux (`mom`, §19), tracker seulement : idem ;
                                # 14 : bloc `melange2` (§20), lu par la version 2 du mélange seulement : les champs de
                                # la version 1, ses mélanges et ses empreintes sont inchangés ;
                                # 15 : bloc `melange3` (§21), lu par la version 3 seulement : versions 1 et 2 inchangées)
FORMATS_BASE = (1, 2, 3, 4, 5, 6, 7, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20)  # formats lisibles (tracker ; le format 2 ajoute n° du Médaillium et conditions)
FORMAT_MELANGE = 9              # format minimal pour mélanger : 3 fixe les non recrutables, 5 les sources des espèces
                                # exigées (évolution, fusion) et les membres des sceaux (anti-softlock, doc §3.4), 6 retire
                                # de W les rencontres d'après-jeu / hors partie et fixe les Yo-kai d'évènement (§3.7),
                                # 9 donne les masques et décors de loupe (loupe jamais vide, §14)
FORMAT_MELANGE_RENCONTRE = 9    # format minimal pour le mélange par rencontre (§11 : 7 ; loupe jamais vide, §14 : 9)
# Version de l'algorithme du mélange (§20), portée par la graine (`slot_data.rando_yokai.mode` = « <mode>#<version> »,
# sans suffixe = 1). Ne JAMAIS changer le calcul d'une version publiée : toute évolution = nouvelle version.
VERSION_MELANGE = 6             # version écrite par l'APWorld distribué avec ce client (nouvelles graines)
VERSIONS_MELANGE = (1, 2, 3, 4, 5, 6, 7)  # versions que ce client sait calculer
# Version 7 (V3, lots M2b, docs/systemes/archipelago_v3_melange_zones.md) : la version 6, et chaque Yo-kai DEMANDÉ reçu
# avec une zone par la graine (`slot_data.yokai_zones`, table `apworld/yokaiwatch2/zones.py`) est placé à K endroits
# de cette zone (couplage), ses lieux d'origine libérés ; par rencontre seulement. Graines avec l'option seulement.
VERSION_ZONES = 7
FORMAT_MELANGE_VERSION = {1: 9, 2: 14, 3: 15, 4: 16, 5: 17, 6: 19, 7: 19}  # format minimal de la base locale (2 :
                                                        # bloc `melange2` ; 3 : + `melange3` ; 4 : + `melange4` ;
                                                        # 5 : + `melange5` ; 6 : + `melange6`)
# Version 6 (V3, lot M2a-bis, décisions de l'humain du 2026-10-18, archipelago_v3_melange_partout.md §8) : la version 5
# + les rencontres des SPOTS de Yo-kai dans le W' (bloc `melange6` de la base, même schéma que `melange5`), et les
# espèces citées seulement par les dialogues des spots (CATEGORIES_SPOT) LIBÉRÉES : politique décidée sans elles (une
# espèce aussi demandée par une requête, un Tablo-blabla… garde la politique « emplacements » ou « tout »).
CATEGORIES_SPOT = frozenset(("condition:YS_CheckYokaiBaseID", "condition:YS_SetCurrentInfo",
                             "condition:YS_IsFind_Yokai"))
# Version 5 (« partout », docs/systemes/archipelago_v3_melange_partout.md) : deux PÉRIMÈTRES, choisis par la graine
# (`slot_data.rando_yokai.apres_jeu`) : « base » (sans les rencontres sauvages d'après-jeu) et « apres_jeu ».
PERIMETRES = ("base", "apres_jeu")
METHODE_PORTAIL = "portail"     # `lieux` d'une rencontre : lieu venu d'un `_enc_pos_gate` (salle de portail, §16)
RAISON_MORTE = "jamais_version"  # exclusion de W (version 2) : aucun lieu de la rencontre ne sort dans cette version
FORMAT_EMPREINTE = 2            # version de la forme canonique de l'empreinte (indépendante du format du fichier) ;
                                # 2 : masques et décors de loupe des espèces de D
FORMAT_EMPREINTE_RENCONTRE = 2  # idem pour le mélange par rencontre (données canoniques de DonneesRencontre) ; 2 : idem
FORMAT_FICHIER = 1              # format de rando_yokai.json (lu par le tracker du lanceur)
FORMAT_MEDAILLIUM = 2           # medaillium.json : 1 = « vu » + « Comp » (P+0x40C..0x48B) ; 2 = + « ami » (CompEx)
FORMAT_PROGRESSION = 1          # progression.json (filtre « Accessibles maintenant » du tracker)
MODES = ("aucun", "par_rang", "total", "par_rencontre_rang", "par_rencontre_total")
# Mélange par rencontre (§11) : chaque combattant modifiable reçoit sa propre espèce ; classe = rang ou toutes
MODES_RENCONTRE = {"par_rencontre_rang": "rang", "par_rencontre_total": "tout"}
NOM_BASE = "yokai_local.json"
NOM_FICHIER = "rando_yokai.json"
NOM_MEDAILLIUM = "medaillium.json"
NOM_PROGRESSION = "progression.json"
# Médaillium dans le bloc P de la sauvegarde [C, archipelago_rando_yokai.md §10.3, §10.6] : bit n (n° du Médaillium de
# l'espèce, CHARA_PARAM_INFO v[49]) = bit n & 7 de l'octet n >> 3, 512 bits (0x40 octets) par zone.
P_VU = 0x40C                    # « vu / rencontré » (FUN_0041550C ; posé à chaque combat et à l'obtention)
P_COMP = 0x44C                  # « ami » (GetGlobalCharaCompFlagCRC), Yo-kai obtenu dont le champ (+88 >> 11) & 7 != 2
P_COMPEX = 0x604                # « ami » (GetGlobalCharaCompExFlagCRC), Yo-kai obtenu dont ce champ vaut 2
TAILLE_MEDAILLIUM = 0x40        # octets par zone
# Une seule lecture groupée P+0x40C .. P+0x643 (0x238 octets) couvre les trois zones. « Ami » = COMP | COMPEX :
# FUN_004AAA98 (enregistrement d'obtention) pose le bit dans l'une ou l'autre, FUN_0041B2B4 teste l'union.
LECTURE_MEDAILLIUM = (P_VU, P_COMPEX + TAILLE_MEDAILLIUM - P_VU)
CAP_SIGMA, CAP_BETA, CAP_W = 256, 256, 2048   # capacités de la boîte v6 (src/archipelago/boite.h)
CAP_ESPECES, CAP_P = 256, 2048                # capacités de la boîte v10 (mélange par rencontre, §11)
CAP_P_ETENDU = 3072                           # V3 : entrées P avec le bit RANDO_P_ETENDU du jeu (suite dans σ / β)
CAP_ESPECES_ETENDU = 288                      # V3 (M2a-bis) : espèces avec le bit RANDO_ESPECES_ETENDU du jeu (version 6)
# Empreinte (W, D avec rangs et bases, F) de la base générée depuis la ROM européenne de référence (SHA-1 de code.bin
# 66143fcb…) par installation/rencontres.py format 6 (périmètre avant l'après-jeu, Yo-kai d'évènement ; format 5 :
# 94754b46…, format 3 : d100a253…, format 2 : 35b3cc0b… ; forme canonique 2, masques et décors de loupe, base au format 9 : avant 842b431a…). Une valeur dérivée (condensat), pas une donnée du jeu. Tous les joueurs d'une graine doivent
# avoir la même : un client d'une version antérieure refuse une base au format 6 (et inversement), avec un message.
EMPREINTE_REFERENCE = "aa31fa9f90d243c49e17ccc0496cebd9a01c43a3"
# Empreinte des données du mélange PAR RENCONTRE (DonneesRencontre : W, combattants modifiables et leur politique,
# combattants gardés, groupes de loupe et leurs décors, réservoir et ses masques de loupe) de la base au format 9 de la
# même ROM (§11, §14 ; forme canonique 1, base au format 7 : 1ffcda13…).
EMPREINTE_REFERENCE_RENCONTRE = "c022e476a1d6a7b8f3139077c45ee148fed3f363"
# Empreintes de référence par version du mélange (σ, par rencontre) ; version 2 : base au format 14 de la même ROM, les 2
# rencontres mortes (t104d11, t104d13) hors de W et de W' (§20).
EMPREINTES_REFERENCE = {1: (EMPREINTE_REFERENCE, EMPREINTE_REFERENCE_RENCONTRE),
                        2: ("f4c7d8a548f09e5ab61b68435e37013c56860170",
                            "cc7a17dd729ef8f16847f28617b7f4b9815298b7"),
                        # version 3 (§21) : base au format 15 de la même ROM (rencontres à lieu normal, `melange3`)
                        3: ("fec63da9d9e949021c67f2a3592e00162be9c6a7",
                            "1a3b0edde5ffee2076caf55b7141b34cafe9b41b"),
                        # version 4 (§22) : base au format 16 de la même ROM (16 espèces invitées, `melange4`)
                        4: ("9d73110968cbcddd24bd6897385fce33f9680a60",
                            "0bf2242526dcecb77d855190ca5450deb2ba7883")}
# Version 5 (« partout ») : empreintes du mélange par rencontre par périmètre, base au format 17 de la même ROM (les
# modes σ de la version 5 sont ceux de la version 4 : même empreinte).
EMPREINTES_REFERENCE_5 = {"base": "0291838c19e0a8c1add5874c1988de3bfeb8936d",
                          "apres_jeu": "6432f339f1fb27ebdabeb2591eecb8e57db5f094"}
# Version 6 (spots) : idem, base au format 19 de la même ROM.
EMPREINTES_REFERENCE_6 = {"base": "07ea82f35bd12d50547d96b37744e6c84543fb6c",
                          "apres_jeu": "6b744f339efdb331e5591e40f19aeadd263d3a1a"}
# Version 7 : données de la version 6 (même bloc `melange6`), forme canonique marquée 7, AVANT la libération des
# Yo-kai demandés (qui dépend de la graine) : une valeur par périmètre, comme les versions 5 et 6.
EMPREINTES_REFERENCE_7 = {"base": "5a8a0924924fb7256268f83fd978f1694f6f12b3",
                          "apres_jeu": "d8ed048416fb0135479d5f85976b802d61e39c87"}
EMPREINTES_PARTOUT = {5: EMPREINTES_REFERENCE_5, 6: EMPREINTES_REFERENCE_6, 7: EMPREINTES_REFERENCE_7}


class RandoImpossible(Exception):
    """Mélange refusé (message destiné au journal du client et au tracker)."""


def posable(masque, decors) -> bool:
    """La loupe peut-elle MONTRER une espèce de masque `WM_YOKAI_INFO` `masque` (0 : base absente de la table) à un
    point dont les décors sont `decors` ([(positions réelles, positions de WM_MAP_ATTR)…], base au format 9) ?
    Critère exact du jeu (FUN_00472B28 : un emplacement de Yo-kai du décor n'est retenu que si le masque de la base a
    le bit de sa position ; emplacements = instructions 0x044D du script `<décor>_pnt.xs`) : un bit commun avec les
    positions réelles de CHAQUE décor. Et un bit commun avec le champ de WM_MAP_ATTR, seul connu du garde-fou du jeu
    (FUN_00519154) : une espèce acceptée ici n'y est jamais refusée (les deux champs diffèrent pour 6 décors sur 39)."""
    m = int(masque or 0)
    return all(m & int(r) and m & int(t) for r, t in decors)


def _decors(liste) -> tuple:
    return tuple(sorted({(int(r), int(t)) for r, t in liste or ()}))


def _couplage(gauche: list, droite: list, permis, depart: dict | None = None) -> dict:
    """Couplage maximum (chemins augmentants, déterministe) : chaque élément de `gauche`, dans l'ordre, reçoit un
    élément distinct de `droite` (essayés dans l'ordre) tel que permis(g, d) ; `depart` : couplage partiel gardé comme
    point de départ. Renvoie {gauche: droite} (un élément de gauche sans partenaire possible est absent)."""
    de_g: dict = dict(depart or {})
    de_d: dict = {d: g for g, d in de_g.items()}

    def augmenter(g, vus: set) -> bool:
        for d in droite:
            if d in vus or not permis(g, d):
                continue
            vus.add(d)
            if d not in de_d or augmenter(de_d[d], vus):
                de_g[g], de_d[d] = d, g
                return True
        return False
    for g in gauche:
        if g not in de_g:
            augmenter(g, set())
    return de_g


def mode_et_version(texte) -> tuple[str, int] | None:
    """`slot_data.rando_yokai.mode` -> (mode, version du mélange) ; « <mode> » = version 1, « <mode>#<n> » = version n
    (n >= 2). None : texte illisible. Une version inconnue de ce client est rendue telle quelle (à refuser par
    l'appelant : `VERSIONS_MELANGE`)."""
    if not isinstance(texte, str):
        return None
    mode, sep, v = texte.partition("#")
    if mode not in MODES:
        return None
    if not sep:
        return mode, 1
    if not (v.isascii() and v.isdigit()) or int(v) < 2 or mode == "aucun":
        return None
    return mode, int(v)


def mode_slot_data(mode: str, version: int = VERSION_MELANGE) -> str:
    """Inverse de `mode_et_version` (APWorld). Un client d'avant les versions ne connaît pas « <mode>#2 » : il garde
    les Yo-kai d'origine et avertit (APWorld plus récent), jamais l'ancien calcul sur une nouvelle graine."""
    return mode if version == 1 or mode == "aucun" else f"{mode}#{int(version)}"


def format_requis(mode: str, version: int = 1) -> int:
    """Format minimal de la base locale pour calculer ce mélange."""
    return max(FORMAT_MELANGE_RENCONTRE if mode in MODES_RENCONTRE else FORMAT_MELANGE,
               FORMAT_MELANGE_VERSION.get(version, FORMAT_BASE))


def morte(e: dict) -> bool:
    """Rencontre sauvage dont aucun lieu ne sort jamais dans cette version du jeu (base au format 13 : `mom`)."""
    mom = e.get("mom")
    return isinstance(mom, list) and bool(mom) and not any(mom)


def vue_base(base: dict, version: int = 1, apres_jeu: bool = False) -> dict:
    """Base locale telle que la version `version` du mélange la lit. Version 1 : la base elle-même. Version 2 (§20) :
    copie superficielle où les champs lus par le mélange (`w`, `wp`, `exclusion`, drapeaux « partagé » des
    combattants, `fixees`, `bases_loupe`, `decors_bases`) sont ceux du bloc `melange2` (calculés par
    installation/rencontres.py avec les rencontres mortes hors de W). Version 5 : la vue de la version 4, puis le
    périmètre « partout » du bloc `melange5` (`apres_jeu` : périmètre avec les rencontres sauvages d'après-jeu ; ignoré
    avant la version 5). La base n'est jamais modifiée. Une vue garde la base brute (`_brute`) : la vue d'une autre
    version (ou d'un autre périmètre) se calcule depuis elle."""
    if isinstance(base, dict) and isinstance(base.get("_brute"), dict):
        if base.get("_vue_melange") == version and (version < 5 or base.get("_perimetre") == _perimetre(apres_jeu)):
            return base
        base = base["_brute"]
    if version == 1:
        return base
    if version >= 5 and version in VERSIONS_MELANGE:
        return dict(_vue_melange5(vue_base(base, 4), version, apres_jeu), _brute=base)
    if version not in VERSIONS_MELANGE:
        raise RandoImpossible(f"mélange de version {version} inconnu de ce client (client et patch du mod à mettre à "
                              "jour)")
    if not isinstance(base, dict) or base.get("format") not in FORMATS_BASE:
        raise RandoImpossible("base locale absente ou d'un autre format (réparer le mod)")
    m2 = base.get("melange2")
    if base["format"] < FORMAT_MELANGE_VERSION[version] or not isinstance(m2, dict) or m2.get("version") != 2:
        raise RandoImpossible("base locale d'un format antérieur, sans les rencontres absentes de cette version du jeu : "
                              "à régénérer (ROM configurée, ou « Réparer le mod » dans le lanceur)")
    normales = None
    if version >= 3:                                      # §21 : la version 2 + les rencontres à lieu normal
        m3 = base.get("melange3")
        if not isinstance(m3, dict) or m3.get("version") != 3 or not isinstance(m3.get("normales"), list):
            raise RandoImpossible("base locale d'un format antérieur, sans les lieux normaux (hors portail mystère) des "
                                  "rencontres : à régénérer (ROM configurée, ou « Réparer le mod » dans le lanceur)")
        normales = {int(h) for h in m3["normales"]}
    if version >= 4:                                      # §22 : la version 3 + les espèces invitées
        _controler_invitees(base)
    diff = m2.get("rencontres", {})
    renc = []
    for e in base["rencontres"]:
        d = diff.get(str(e["h"]))
        if d is not None and "w" in e:
            e = dict(e, w=bool(d["w"]),
                     c=[[*c[:3], int(x), *c[4:6], int(y), *c[7:]] for c, x, y in zip(e["c"], d["p"], d["pp"])])
            e.pop("wp", None)
            e.pop("exclusion", None)
            if d["wp"]:
                e["wp"] = True
            if not e["w"]:
                e["exclusion"] = list(d["exclusion"])
        # défense en profondeur : une rencontre morte n'est jamais dans W ni W', même si le bloc l'oublie
        if "w" in e and morte(e) and (e.get("w") or e.get("wp") or RAISON_MORTE not in e.get("exclusion", ())):
            raise RandoImpossible("base locale incohérente (rencontre absente de cette version du jeu dans W) : "
                                  "« Réparer le mod »")
        # idem (§21) : une rencontre « à lieu normal » est sauvage, sort dans cette version et a un lieu hors portail
        if normales is not None and int(e["h"]) in normales:
            normales.discard(int(e["h"]))
            if "w" not in e or morte(e) or not lieu_normal_possible(e):
                raise RandoImpossible("base locale incohérente (rencontre sans lieu normal donnée comme normale) : "
                                      "« Réparer le mod »")
        renc.append(e)
    if normales:
        raise RandoImpossible("base locale incohérente (rencontre à lieu normal inconnue) : « Réparer le mod »")
    vue = dict(base, rencontres=renc, _vue_melange=version, _brute=base)
    for k in ("fixees", "bases_loupe", "decors_bases"):
        if k in m2:
            vue[k] = m2[k]
    return vue


def _perimetre(apres_jeu: bool) -> str:
    return PERIMETRES[1 if apres_jeu else 0]


def bloc_partout(base: dict, version: int) -> dict | None:
    """Bloc du périmètre « partout » lu par la version `version` (>= 5) : `melange5` (version 5), `melange6` (version 6 :
    spots en plus). Même schéma."""
    return base.get("melange6" if version >= 6 else "melange5") if isinstance(base, dict) else None


def _vue_melange5(v4: dict, version: int, apres_jeu: bool) -> dict:
    """Vue de la version 5 (« partout ») sur la vue de la version 4 `v4` : W' = `wp` du périmètre (rencontres
    sauvages ET non sauvages : coffres piégés, trains, gymnase), drapeaux « partagé » (7e élément des combattants)
    relatifs à ce W', `fixees` du périmètre, lieux normaux de la version 5 (`melange3.normales` de la vue),
    rencontres sans amitié (`_sans_amitie`), emplacement virtuel (`em`) des rencontres non sauvages. Les rencontres
    sauvages gardent `w` / `exclusion` de la version 4 (lus par les modes σ et par `avant_fin`) ; `exclusion5` porte
    la raison de la version 5 (tracker)."""
    m5 = bloc_partout(v4, version)               # version 6 : bloc `melange6` (spots), même schéma
    # (version 7 : le bloc de la version 6, inchangé)
    if v4.get("format", 0) < FORMAT_MELANGE_VERSION[version] or not isinstance(m5, dict) \
            or m5.get("version") != min(version, 6):
        raise RandoImpossible("base locale d'un format antérieur, sans le périmètre « partout » du mélange : à "
                              "régénérer (ROM configurée, ou « Réparer le mod » dans le lanceur)")
    per = (m5.get("perimetres") or {}).get(_perimetre(apres_jeu))
    if not isinstance(per, dict) or not all(isinstance(per.get(k), t) for k, t in (
            ("wp", list), ("pp", dict), ("fixees", dict), ("exclusion", dict), ("ajouts", dict))) \
            or not isinstance(m5.get("normales"), list) or not isinstance(m5.get("sans_amitie"), list) \
            or not isinstance(m5.get("emplacements"), dict):
        raise RandoImpossible("base locale incohérente (périmètre « partout » du mélange illisible) : « Réparer le "
                              "mod »")
    wp = {int(h) for h in per["wp"]}
    sans = {int(h) for h in m5["sans_amitie"]}
    normales = {int(h) for h in m5["normales"]}
    virtuels = {int(h): int(i) for h, i in m5["emplacements"].items()}
    nb_em = len(v4.get("emplacements") or ())
    evt = {int(h) for h in (v4.get("evenement") or {}).get("rencontres", [])}
    vus: set[int] = set()
    renc = []
    for e in v4["rencontres"]:
        h = int(e["h"])
        sauvage = "w" in e
        if h in wp:
            pp = per["pp"].get(str(h))
            # défense en profondeur : drapeaux pour chaque combattant, ni rencontre morte, d'évènement ou sans amitié,
            # une rencontre non sauvage a son emplacement virtuel (au-delà des emplacements réels)
            if (not isinstance(pp, list) or len(pp) != len(e["c"]) or h in evt or h in sans
                    or (sauvage and morte(e)) or (not sauvage and not virtuels.get(h, -1) >= nb_em)):
                raise RandoImpossible("base locale incohérente (rencontre du périmètre « partout » invalide) : "
                                      "« Réparer le mod »")
            e = dict(e, wp=True, c=[[*c[:6], int(x), *c[7:]] for c, x in zip(e["c"], pp)])
            if not sauvage:
                e["em"] = [virtuels[h]]
            vus.add(h)
        elif e.get("wp"):
            e = dict(e)
            e.pop("wp")
        if str(h) in per["exclusion"]:
            e = dict(e, exclusion5=list(per["exclusion"][str(h)]))
        if h in normales:
            if not sauvage or morte(e) or not lieu_normal_possible(e) or h in sans:
                raise RandoImpossible("base locale incohérente (rencontre sans lieu normal donnée comme normale) : "
                                      "« Réparer le mod »")
        renc.append(e)
    if vus != wp:
        raise RandoImpossible("base locale incohérente (rencontre du périmètre « partout » inconnue) : « Réparer le "
                              "mod »")
    m3 = dict(v4["melange3"], normales=sorted(normales))
    return dict(v4, rencontres=renc, fixees=per["fixees"], melange3=m3, _vue_melange=version,
                _perimetre=_perimetre(apres_jeu), _sans_amitie=sorted(sans))


def lieu_normal_possible(e: dict) -> bool:
    """La rencontre a un lieu hors portail mystère qui sort dans cette version du jeu (`lieux`, `mom` de la base) :
    condition NÉCESSAIRE d'un lieu normal (le bloc `melange3` ajoute « d'avant la fin », calculé à l'installation)."""
    lieux, mom = e.get("lieux") or (), e.get("mom")
    if not isinstance(mom, list) or len(mom) != len(lieux):
        return False
    return any(len(l) > 1 and l[1] != METHODE_PORTAIL and m for l, m in zip(lieux, mom))


def normales_de(base: dict, version: int) -> frozenset[int]:
    """Rencontres sauvages à lieu NORMAL lues par la version `version` (vue de la base) ; vide avant la version 3."""
    if version < 3:
        return frozenset()
    return frozenset(int(h) for h in base["melange3"]["normales"])


def _controler_invitees(base: dict) -> None:
    """Bloc `melange4` de la base (§22) : présent, et chaque espèce invitée est un Yo-kai RECRUTABLE en combat, à rang
    E..S et n° du Médaillium, non légendaire, hors évènement, absent de toute rencontre sauvage (défense en profondeur :
    la base le calcule déjà ; une invitée qui serait aussi sauvage fausserait les emplacements gardés)."""
    m4 = base.get("melange4")
    if not isinstance(m4, dict) or m4.get("version") != 4 or not isinstance(m4.get("invitees"), list):
        raise RandoImpossible("base locale d'un format antérieur, sans les Yo-kai invités du mélange : à régénérer (ROM "
                              "configurée, ou « Réparer le mod » dans le lanceur)")
    esp = base.get("especes", {})
    evt = {int(p) for p in base.get("evenement", {}).get("especes", [])}
    sauvages = {int(c[1]) for e in base["rencontres"] if "w" in e for c in e["c"]}
    for p in m4["invitees"]:
        info = esp.get(str(p)) if isinstance(p, int) and not isinstance(p, bool) else None
        if (not isinstance(info, dict) or info.get("recrutable") is not True or not info.get("yokai")
                or info.get("rang") not in (0, 1, 2, 3, 4, 5) or isinstance(info.get("rang"), bool)
                or not info.get("medaille") or info.get("legendaire") or info.get("base") is None
                or p in evt or p in sauvages):
            raise RandoImpossible("base locale incohérente (Yo-kai invité non recrutable ou déjà sauvage) : « Réparer "
                                  "le mod »")
    if len(set(m4["invitees"])) != len(m4["invitees"]):
        raise RandoImpossible("base locale incohérente (Yo-kai invité en double) : « Réparer le mod »")


def invitees_de(base: dict, version: int) -> dict[int, int]:
    """Espèces invitées lues par la version `version` (vue de la base) -> rang ; vide avant la version 4."""
    if version < 4:
        return {}
    return {int(p): int(base["especes"][str(p)]["rang"]) for p in sorted(base["melange4"]["invitees"])}


def charger_base(dossier: str | Path) -> dict | None:
    try:
        b = json.loads((Path(dossier) / NOM_BASE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return b if isinstance(b, dict) and b.get("format") in FORMATS_BASE else None


def base_a_refaire(dossier: str | Path) -> bool:
    """Base locale d'un format antérieur (lisible, mélange identique, mais n° du Médaillium faux et conditions non
    décodées pour le tracker) : à régénérer quand la ROM est connue."""
    b = charger_base(dossier)
    return b is not None and b.get("format", 0) < FORMAT_BASE


@dataclass
class Donnees:
    """Ce que le mélange utilise de la base locale (canonique, trié)."""
    w: list[int]                       # rencontres de W (hachages)
    d: dict[int, int]                  # espèce de D -> rang (0..5)
    base_de: dict[int, int]            # espèce -> base (CHARA_BASE)
    f: list[int]                       # espèces fixées (parmi les espèces de W)
    # loupe jamais vide (format 9, §14) : masque WM_YOKAI_INFO des espèces de D ; décors des points de loupe dont le
    # jeu réécrit la base par β (points dont toutes les rencontres sont dans W), par espèce d'origine de D
    masques: dict[int, int] = field(default_factory=dict)
    decors: dict[int, tuple] = field(default_factory=dict)
    version: int = 1                   # version du mélange (§20) ; entre dans l'empreinte à partir de 2
    # version 3 (§21 ; vides avant) : espèces de D dont un combattant RÉÉCRIT par le jeu (σ) est dans une rencontre à
    # lieu normal (l'image σ(a) y sera) ; espèces de D qui ont un lieu normal SANS réécriture (combattant partagé ou
    # rencontre hors de W)
    source_normale: frozenset = frozenset()
    fixe_normale: frozenset = frozenset()
    # version 4 (§22 ; vide avant) : espèces invitées -> rang. Jamais dans D (elles n'ont aucun combattant sauvage) :
    # seulement des IMAGES possibles de σ, dans la classe de leur rang
    invitees: dict[int, int] = field(default_factory=dict)

    @classmethod
    def depuis(cls, base: dict, version: int = 1) -> "Donnees":
        if not isinstance(base, dict) or base.get("format") not in FORMATS_BASE:
            raise RandoImpossible("base locale absente ou d'un autre format (réparer le mod)")
        if version >= 5:                                  # modes σ : la version 5 ne change que le mélange par
            version = 4                                   # rencontre (σ de la version 5 = σ de la version 4)
        base = vue_base(base, version)
        if base["format"] < FORMAT_MELANGE:
            raise RandoImpossible("base locale d'un format antérieur, sans le contrôle des Yo-kai exigés et de leurs "
                                  "sources : à régénérer (ROM configurée, ou « Réparer le mod » dans le lanceur)")
        evt = base.get("evenement", {})
        # défense en profondeur (format 6, §3.7) : une rencontre d'évènement n'est jamais dans W, même si la base le dit
        evt_renc = {int(h) for h in evt.get("rencontres", [])}
        w = sorted(int(e["h"]) for e in base["rencontres"] if e.get("w") and int(e["h"]) not in evt_renc)
        cand = {int(c[1]) for e in base["rencontres"] if e.get("w") and int(e["h"]) not in evt_renc
                for c in e["c"] if not c[3]}
        f = {int(p) for p in base.get("fixees", {})}
        f |= cand & {int(p) for p in evt.get("especes", [])}         # Yo-kai d'évènement : jamais dans D
        esp = base["especes"]
        # défense en profondeur : une espèce dont la base ne dit pas qu'elle est recrutable n'entre jamais dans D (la
        # base au format 3 la met déjà dans les fixées, raison « non_recrutable » : l'empreinte ne change pas)
        f |= {p for p in cand if esp.get(str(p), {}).get("recrutable") is not True}
        # idem (format 5) : une espèce exigée par le jeu ou source d'une espèce exigée n'entre jamais dans D
        f |= cand & {int(p) for p in base.get("exigees", {})}
        d = {}
        for p in sorted(cand - f):
            r = esp.get(str(p), {}).get("rang")
            if not isinstance(r, int):
                raise RandoImpossible(f"espèce 0x{p:08X} sans rang dans la base locale")
            d[p] = r
        base_de = {int(k): int(v["base"]) for k, v in esp.items() if v.get("base") is not None}
        db = base.get("decors_bases", {})
        invitees = invitees_de(base, version)             # version 4 (§22) ; vide avant
        masques = {p: int(esp[str(p)].get("loupe") or 0) for p in [*d, *invitees]}
        decors = {p: _decors(db.get(str(base_de.get(p)))) for p in d}
        src, fixe = set(), set()
        if version >= 3:
            ws, normales = set(w), normales_de(base, version)
            for e in base["rencontres"]:
                if int(e["h"]) in normales:
                    for c in e["c"]:
                        (src if int(e["h"]) in ws and not c[3] else fixe).add(int(c[1]))
        return cls(w, d, base_de, sorted(cand & f), masques, decors, version,
                   frozenset(src & set(d)), frozenset(fixe & set(d)), invitees)

    def empreinte(self) -> str:
        canon = {"format": FORMAT_EMPREINTE, "w": self.w,
                 "d": [[p, r, self.base_de.get(p), self.masques.get(p, 0), [list(x) for x in self.decors.get(p, ())]]
                       for p, r in sorted(self.d.items())],
                 "f": self.f}
        if self.version != 1:                             # version 1 : forme canonique inchangée
            canon["melange"] = self.version
        if self.version >= 3:                             # versions 1 et 2 : formes canoniques inchangées
            canon["n"] = [sorted(self.source_normale), sorted(self.fixe_normale)]
        if self.version >= 4:                             # versions 1 à 3 : formes canoniques inchangées
            canon["i"] = [[p, r, self.base_de.get(p), self.masques.get(p, 0)] for p, r in sorted(self.invitees.items())]
        return hashlib.sha1(json.dumps(canon, separators=(",", ":")).encode()).hexdigest()


@dataclass
class Melange:
    mode: str
    graine: int
    empreinte: str
    generation: int                    # identifiant non nul du mélange dans la boîte (valide / table_gen)
    sigma: dict[int, int]              # espèce -> espèce (identités exclues)
    beta: dict[int, int]               # base -> base (identités exclues)
    w: list[int]
    d: dict[int, int]
    classes: dict[str, list[int]] = field(default_factory=dict)
    # mélange par rencontre (§11 ; vides pour les modes σ) : combattant (index du fichier dans la base, index
    # d'ENCOUNT_CHARA) -> espèce en jeu (identités exclues) ; entrées P de la boîte v10 ; table des espèces (param, base)
    affectation: dict[tuple[int, int], int] = field(default_factory=dict)
    entrees: list[int] = field(default_factory=list)
    especes: list[tuple[int, int]] = field(default_factory=list)
    gardes: dict[tuple[int, int], str] = field(default_factory=dict)     # combattants gardés -> raison
    stats: dict = field(default_factory=dict)
    # version du mélange (§20) ; version 2 : rencontres de W / W' de la version 1 qui n'y sont plus (mortes) et
    # combattants (fichier, index) des rencontres restantes devenus partagés avec elles (jamais réécrits par le jeu),
    # pour appliquer le mélange aux entrées BRUTES de la base (`en_jeu`, tracker du lanceur)
    version: int = 1
    hors_w: list[int] = field(default_factory=list)
    figes: list[tuple[int, int]] = field(default_factory=list)
    # version 3 (§21) : espèces du réservoir (de D pour les modes σ) restées SANS lieu normal (repli : la contrainte
    # était infaisable pour elles) ; vide quand la garantie est tenue pour toutes
    sans_normal: list[int] = field(default_factory=list)
    # version 4 (§22 ; vides avant) : espèces invitées de ce mélange ; celles qu'il n'a placées nulle part (repli) ;
    # modes σ : espèces de D qui ne sont plus l'image de personne (une par invitée placée ; elles gardent un lieu
    # normal sans réécriture)
    invitees: list[int] = field(default_factory=list)
    invitees_absentes: list[int] = field(default_factory=list)
    evincees: list[int] = field(default_factory=list)
    # version 5 (« partout » ; vides avant) : périmètre de la graine ; rencontres du W' de la version 5 absentes du W'
    # de la base brute (catégorie : histoire, apres_jeu, coffre, train, gymnase) ; combattants (fichier, index) dont le
    # drapeau « partagé » brut est levé mais que le W' de la version 5 rend modifiables (`en_jeu` sur la base BRUTE)
    perimetre: str = ""
    ajout_w: dict[int, str] = field(default_factory=dict)
    liberes: list[tuple[int, int]] = field(default_factory=list)
    # version 7 (zones des Yo-kai demandés ; vide avant) : espèce placée -> (n° du Médaillium, zone, [cartes de chacune
    # de ses K unités])
    zones: dict[int, tuple] = field(default_factory=dict)

    @property
    def par_rencontre(self) -> bool:
        return self.mode in MODES_RENCONTRE

    @property
    def empreinte32(self) -> int:
        return int(self.empreinte[:8], 16)

    def en_jeu(self, e: dict, c: list) -> int:
        """Espèce en jeu du combattant `c` de la rencontre `e` de la base (ce que fait le jeu, FUN_00506098) : combattant
        modifiable (non partagé avec une rencontre hors W) d'une rencontre de W seulement."""
        orig = int(c[1])
        if self.figes and int(e["h"]) in self._ws() and (int(e["f"]), int(c[0])) in self._figes():
            return orig                                 # version 2 : partagé avec une rencontre retirée de W
        if self.par_rencontre:                          # W' et partage relatif à W' (7e élément, base au format 7)
            if len(c) < 7 or int(e["h"]) not in self._ws():
                return orig
            if c[6] and not (self.liberes and (int(e["f"]), int(c[0])) in self._liberes()):
                return orig
            return self.affectation.get((int(e["f"]), int(c[0])), orig)
        if c[3] or int(e["h"]) not in self._ws():
            return orig
        return self.sigma.get(orig, orig)

    def _liberes(self) -> set:
        fs = self.__dict__.get("_liberes_ens")
        if fs is None or len(fs) != len(self.liberes):
            fs = self.__dict__["_liberes_ens"] = {tuple(x) for x in self.liberes}
        return fs

    def _figes(self) -> set:
        fs = self.__dict__.get("_figes_ens")
        if fs is None or len(fs) != len(self.figes):
            fs = self.__dict__["_figes_ens"] = {tuple(x) for x in self.figes}
        return fs

    def _ws(self) -> set[int]:
        ws = self.__dict__.get("_w_ens")
        if ws is None or len(ws) != len(self.w):
            ws = self.__dict__["_w_ens"] = set(self.w)
        return ws

    def deplacees(self) -> set[int]:
        """Espèces d'origine dont au moins un emplacement change."""
        if self.par_rencontre:
            return set(self.stats.get("origines_changees", ()))
        return set(self.sigma)

    def inverse(self) -> dict[int, int]:
        return {v: k for k, v in self.sigma.items()}


class _Alea:
    """Tirages déterministes indépendants de la version de Python : `getrandbits` du Mersenne Twister (initialisé
    par un entier : stable) et tirage par rejet."""

    def __init__(self, graine: int, mode: str, empreinte: str):
        h = hashlib.sha256(f"ykw2ap-rando-yokai:{graine}:{mode}:{empreinte}".encode()).digest()
        self.r = random.Random(int.from_bytes(h[:16], "little"))

    def sous(self, n: int) -> int:
        k = max(1, n.bit_length())
        while True:
            v = self.r.getrandbits(k)
            if v < n:
                return v


def generation(graine: int, mode: str, empreinte: str) -> int:
    return zlib.crc32(f"{graine}:{mode}:{empreinte}".encode()) & 0xFFFFFFFF or 1


_REFERENCE = object()


def _ecarts(base: dict, vue: dict, cle: str, drapeau: int) -> tuple[list[int], list[tuple[int, int]]]:
    """(rencontres de W — `cle` « w » ou « wp » — de la base brute absentes de celui de la vue, combattants des
    rencontres restantes dont le drapeau « partagé » n° `drapeau` est levé par la vue) ; vides pour la version 1."""
    if vue is base:
        return [], []
    hors, figes = [], set()
    for e, v in zip(base["rencontres"], vue["rencontres"]):
        if e is v or not e.get(cle):
            continue
        if not v.get(cle):
            hors.append(int(e["h"]))
        else:
            figes |= {(int(e["f"]), int(c[0])) for c, x in zip(e["c"], v["c"]) if x[drapeau] and not c[drapeau]}
    return sorted(hors), sorted(figes)


def _ajouts(base: dict, vue: dict) -> tuple[dict[int, str], list[tuple[int, int]]]:
    """Version 5 : (rencontres du W' de la vue absentes du W' brut -> catégorie, combattants des rencontres du W' de la
    vue dont le drapeau « partagé » brut est levé et que la vue rend modifiables)."""
    per = bloc_partout(vue, vue["_vue_melange"])["perimetres"][vue["_perimetre"]]
    cats = {int(h): c for h, c in per["ajouts"].items()}
    ajout, liberes = {}, set()
    for e, v in zip(base["rencontres"], vue["rencontres"]):
        if not v.get("wp"):
            continue
        if not e.get("wp"):
            ajout[int(e["h"])] = cats.get(int(e["h"]), "histoire")
        liberes |= {(int(e["f"]), int(c[0])) for c, x in zip(e["c"], v["c"]) if c[6] and not x[6]}
    return ajout, sorted(liberes)


def calculer(base: dict, graine: int, mode: str, reference=_REFERENCE, version: int = 1,
             apres_jeu: bool = False, zones: dict | None = None) -> Melange:
    """Mélange de la graine (voir le docstring du module). `reference` : empreinte exigée (défaut : celle de la
    version, EMPREINTE_REFERENCE* pour la version 1, lue à l'appel ; None : pas de contrôle, pour les tests sur des
    bases synthétiques). `version` : version du mélange de la GRAINE (§20 ; défaut 1 = graines sans suffixe).
    `apres_jeu` (version 5) : périmètre avec les rencontres sauvages d'après-jeu (graine à l'après-jeu activé).
    `zones` (version 7, obligatoire) : {"especes": {n° du Médaillium: zone}, "cartes": {zone: [cartes admises]},
    "k": endroits par Yo-kai} (`zones_client`, depuis `slot_data.yokai_zones` et la table de l'APWorld)."""
    if mode not in MODES or mode == "aucun":
        raise RandoImpossible(f"mode de mélange inconnu : {mode!r}")
    if version not in VERSIONS_MELANGE:
        raise RandoImpossible(f"mélange de version {version} inconnu de ce client (client et patch du mod à mettre à "
                              "jour)")
    if version >= VERSION_ZONES and (mode not in MODES_RENCONTRE or not isinstance(zones, dict)):
        raise RandoImpossible("mélange de version 7 sans les zones des Yo-kai demandés (ou par espèce) : graine "
                              "illisible")
    if mode in MODES_RENCONTRE:
        if reference is _REFERENCE:
            reference = (EMPREINTE_REFERENCE_RENCONTRE if version == 1 else
                         EMPREINTES_PARTOUT[version][_perimetre(apres_jeu)] if version >= 5 else
                         EMPREINTES_REFERENCE[version][1])
        return _calculer_par_rencontre(base, graine, mode, reference, version=version, apres_jeu=apres_jeu,
                                       zones=zones)
    if version >= 5:
        # modes σ (par espèce) : la version 5 ne change que le mélange par rencontre ; même calcul que la version 4
        # (mêmes σ, β, W, empreinte et génération), seule la version annoncée change
        m = calculer(base, graine, mode, EMPREINTES_REFERENCE[4][0] if reference is _REFERENCE else reference,
                     version=4)
        m.version = version
        return m
    if reference is _REFERENCE:
        reference = EMPREINTE_REFERENCE if version == 1 else EMPREINTES_REFERENCE[version][0]
    vue = vue_base(base, version)
    don = Donnees.depuis(vue, version)
    emp = don.empreinte()
    if reference is not None and emp != reference:
        raise RandoImpossible(f"base locale différente de la référence (empreinte {emp[:12]}… au lieu de "
                              f"{reference[:12]}…) : ROM d'une autre version ou RomFS modifié ; mélange refusé")
    if len(don.w) > CAP_W:
        raise RandoImpossible(f"{len(don.w)} rencontres dans W (boîte : {CAP_W} au plus)")
    classes: dict[str, list[int]] = {}
    for p, r in sorted(don.d.items()):
        classes.setdefault(f"rang{r}" if mode == "par_rang" else "tout", []).append(p)
    alea = _Alea(graine, mode, emp)
    sigma: dict[int, int] = {}

    def permis(a: int, b: int) -> bool:
        # loupe jamais vide (§14) : l'image b de a doit pouvoir être montrée par la loupe à tous les points dont le jeu
        # réécrit la base de a (β) ; l'identité est toujours permise (rien ne change)
        return a == b or posable(don.masques.get(b, 0), don.decors.get(a, ()))
    sans_normal: list[int] = []
    invitees_c: dict[str, list[int]] = {}                 # version 4 (§22) ; vide avant
    for p, r in sorted(don.invitees.items()):
        invitees_c.setdefault(f"rang{r}" if mode == "par_rang" else "tout", []).append(p)
    absentes: list[int] = [p for c, ps in sorted(invitees_c.items()) if c not in classes for p in ps]
    evincees: list[int] = []
    for c in sorted(classes):
        orig = classes[c]
        perm = list(orig)
        for i in range(len(perm) - 1, 0, -1):             # Fisher-Yates
            j = alea.sous(i + 1)
            perm[i], perm[j] = perm[j], perm[i]
        if version >= 4 and invitees_c.get(c):            # §22 ; classe sans invitée : tirage de la version 3
            couple, sans, evi = _images_avec_invitees(don, alea, orig, invitees_c[c], permis)
            sans_normal += sans
            evincees += evi
            absentes += [b for a, b in couple.items() if a < 0 and b in don.invitees]
            sigma.update({a: b for a, b in couple.items() if a >= 0 and a != b})
            continue
        if version >= 3:                                  # §21 ; versions 1 et 2 : suite inchangée
            couple, sans = _permutation_lieu_normal(don, alea, orig, perm, permis)
            sans_normal += sans
            sigma.update({a: b for a, b in couple.items() if a != b})
            continue
        # les paires permises du tirage sont gardées ; les autres espèces sont recouplées (chemins augmentants, images
        # essayées dans un ordre tiré au hasard) : une permutation de la classe existe toujours (l'identité)
        ordre = _melanger(alea, orig)
        couple = _couplage(orig, ordre, permis, {a: b for a, b in zip(orig, perm) if permis(a, b)})
        if len(couple) != len(orig):
            raise RandoImpossible("permutation des espèces impossible (loupe)")
        sigma.update({a: b for a, b in couple.items() if a != b})
    beta = {don.base_de[a]: don.base_de[b] for a, b in sigma.items()
            if a in don.base_de and b in don.base_de and don.base_de[a] != don.base_de[b]}
    if len(sigma) > CAP_SIGMA or len(beta) > CAP_BETA:
        raise RandoImpossible("mélange trop grand pour la boîte")
    hors, figes = _ecarts(base, vue, "w", 3)
    # invitée d'une classe sans espèce de D (aucune place possible) : absente, et donc sans lieu normal
    sans_normal += [p for p in absentes if p not in sans_normal]
    return Melange(mode, graine, emp, generation(graine, mode, emp), sigma, beta, don.w, don.d, classes,
                   version=version, hors_w=hors, figes=figes, sans_normal=sorted(sans_normal),
                   invitees=sorted(don.invitees), invitees_absentes=sorted(absentes), evincees=sorted(evincees))


def _images_avec_invitees(don: Donnees, alea: "_Alea", orig: list[int], inv: list[int], permis):
    """Images d'une classe pour la version 4 (§22) : (σ de la classe avec ses sources fantômes, images restées sans
    lieu normal, espèces évincées).

    Les invitées n'ont aucun combattant sauvage : elles ne peuvent être que des IMAGES. Une source FANTÔME (entier
    négatif, « personne ») par invitée rend le problème carré : sources = espèces de la classe + fantômes, images =
    espèces de la classe + invitées. L'image d'un fantôme n'est l'image de personne :
    - une espèce z de D : z est ÉVINCÉE de ses combattants réécrits ; permis seulement si z garde un lieu normal sans
      réécriture (`fixe_normale`) : aucune espèce du réservoir d'origine ne perd sa garantie ;
    - une invitée : elle n'est placée nulle part (REPLI, annoncé : `invitees_absentes`, `sans_normal`).
    Le reste est la règle de la version 3 : l'image b de a doit être posable (loupe, §14) et avoir un lieu normal (b en
    a un sans réécriture, ou a est réécrite dans une rencontre à lieu normal). Tirage direct (toutes les invitées
    placées, toutes les images à lieu normal) ; sinon repli : les images sont tenues une à une, celles des espèces de D
    AVANT les invitées, chacune seulement si une affectation complète existe encore ; puis chaque invitée restée sans
    lieu normal reçoit, si c'est possible, au moins les places d'une espèce (de portail : présente, mais annoncée)."""
    fant = [-(k + 1) for k in range(len(inv))]
    sources, images = orig + fant, orig + inv
    d_fixes = {z for z in orig if z in don.fixe_normale}
    ens_inv = set(inv)
    perm = _melanger(alea, images)
    ordre = _melanger(alea, images)
    large = {a: {b for b in images if permis(a, b)} for a in orig}
    strict = {a: {b for b in large[a] if b in don.fixe_normale or a in don.source_normale} for a in orig}
    for f in fant:
        strict[f] = d_fixes
        large[f] = d_fixes | ens_inv

    def bilan(couple):
        return (couple, sorted(b for a, b in couple.items() if b not in strict[a]),
                sorted(b for a, b in couple.items() if a < 0 and b not in ens_inv))
    couple = _couplage(sources, ordre, lambda a, b: b in strict[a],
                       {a: b for a, b in zip(sources, perm) if b in strict[a]})
    if len(couple) == len(sources):
        return bilan(couple)
    tenues: set[int] = set()                              # images à lieu normal exigé
    placees: set[int] = set()                             # invitées à placer au moins quelque part (source réelle)

    def ok(a, b):
        if b in tenues:
            return b in strict[a]
        return b in large[a] and (a >= 0 or b not in placees)
    prioritaires = set(couple.values())
    couple = _couplage(sources, ordre, ok, {a: b for a, b in zip(sources, perm) if b in large[a]})
    if len(couple) != len(sources):
        raise RandoImpossible("permutation des espèces impossible (loupe)")
    # 1. lieu normal : espèces de D d'abord, puis invitées ; 2. invitées restantes : au moins une place (de portail)
    for palier, liste in ((tenues, sorted(ordre, key=lambda x: (x in ens_inv, x not in prioritaires))),  # tri stable
                          (placees, [x for x in ordre if x in ens_inv])):
        for b in liste:
            if b in tenues:
                continue
            palier.add(b)
            essai = _couplage(sources, ordre, ok, {a: x for a, x in couple.items() if ok(a, x)})
            if len(essai) == len(sources):
                couple = essai
            else:
                palier.discard(b)
    return bilan(couple)


def _permutation_lieu_normal(don: Donnees, alea: "_Alea", orig: list[int], perm: list[int], permis):
    """Permutation d'une classe pour la version 3 (§21) : (σ de la classe, images restées sans lieu normal).

    L'image b = σ(a) a un lieu normal si b en a un sans réécriture (`fixe_normale`) ou si a est réécrite dans une
    rencontre à lieu normal (`source_normale`). Une permutation d'espèces ne crée pas de lieu : si la classe a plus
    d'espèces « source de portail seulement » que d'espèces à lieu normal fixe, la garantie est infaisable pour
    quelques images. D'abord le tirage direct (toutes les images tenues : paires permises du Fisher-Yates gardées,
    le reste recouplé) ; s'il n'est pas complet, REPLI : les images sont tenues une à une (celles du couplage strict
    maximum d'abord, puis les autres, dans un ordre tiré au hasard), chacune seulement si une permutation complète
    existe encore ; les images non tenues sont rendues (elles n'ont de lieux que de portail, ou hors du périmètre)."""
    ordre = _melanger(alea, orig)
    large = {a: {b for b in orig if permis(a, b)} for a in orig}
    strict = {a: {b for b in large[a] if b in don.fixe_normale or a in don.source_normale} for a in orig}
    couple = _couplage(orig, ordre, lambda a, b: b in strict[a], {a: b for a, b in zip(orig, perm) if b in strict[a]})
    if len(couple) == len(orig):
        return couple, []
    tenues: set[int] = set()

    def ok(a, b):
        return b in (strict[a] if b in tenues else large[a])
    prioritaires = set(couple.values())
    couple = _couplage(orig, ordre, ok, {a: b for a, b in zip(orig, perm) if b in large[a]})
    if len(couple) != len(orig):
        raise RandoImpossible("permutation des espèces impossible (loupe)")
    for b in [x for x in ordre if x in prioritaires] + [x for x in ordre if x not in prioritaires]:
        tenues.add(b)
        essai = _couplage(orig, ordre, ok, {a: x for a, x in couple.items() if ok(a, x)})
        if len(essai) == len(orig):
            couple = essai
        else:
            tenues.discard(b)
    return couple, sorted(b for a, b in couple.items() if b not in strict[a])


# ------------------------------------------------------------------------------------------ mélange par rencontre (§11)
# Chaque combattant MODIFIABLE (celui d'une rencontre de W qui n'est cité par aucune rencontre hors W du même fichier)
# reçoit sa propre espèce, tirée dans le RÉSERVOIR (espèces recrutables en combat sauvage, trouvables à l'état sauvage
# avant la fin, hors évènement et légendaires) de la même classe (rang d'origine, ou toutes). Anti-softlock, selon la
# RAISON pour laquelle une espèce est exigée (catégories de `fixees` / `exigees` de la base) :
# - exigence de POSSESSION (posséder, vaincre N fois, réponse de Tablo, sceau, source d'évolution / de fusion, équipe,
#   ami du Médaillium) : l'espèce reste à CHAQUE emplacement (point de loupe / chemin d'errants, avec sa condition) où
#   elle était dans le jeu d'origine : au moins un de ses combattants par emplacement est gardé ; elle reste donc
#   obtenable aux mêmes lieux et aux mêmes moments que dans le jeu d'origine, quel que soit le moment de l'exigence ;
# - toute autre exigence (lieu : déclencheur, repère d'objectif, règle de combat ; argument de script ou fonction de
#   condition non comprise ; espèce sans rang) : TOUS ses combattants sont gardés (règle des modes σ) ;
# - raisons de F qui ne sont pas des exigences du jeu (non recrutable, légendaire, évènement, variantes) : combattants
#   libres (remplacés par une espèce du réservoir ; ces espèces ne sont jamais tirées).
# Point de loupe : la loupe montre la base du 1er combattant de chacune de ses rencontres (§9.1) : les 1ers
# combattants des rencontres d'un même point forment un groupe qui reçoit UNE espèce (ou reste d'origine en entier).
# Couverture : chaque espèce du réservoir reste trouvable à l'état sauvage avant la fin (checks « Ami »).
POLITIQUE_POSSESSION = frozenset((
    "quete_vaincre", "quete_posseder", "tablo", "sceau_legendaire", "source_evolution", "source_fusion",
    "condition:InPartyMember", "condition:GetPartyInNum", "condition:GetGlobalCharaCompFlagAnyOneCRC",
    # Yo-kai des spots et Yo-kai PNJ (dialogues TALK_CONFIG, apparitions NPC_APPEAR) : leurs sources (YS_YOKAI, rencontres
    # des spots) sont hors du mélange ; garder quand même chaque emplacement sauvage d'origine (prudence, §11.3)
    "condition:YS_CheckYokaiBaseID", "condition:YS_SetCurrentInfo", "condition:YS_IsFind_Yokai"))
RAISONS_LIBRES = frozenset(("non_recrutable", "legendaire", "evenement", "variantes"))
# Catégories d'exigence d'une DEMANDE (requête ou service : posséder, vaincre N fois ; réponse de Tablo-blabla) : celles
# qui désignent l'espèce citée par le jeu pour un Yo-kai demandé (version 7, `cibles_zones`)
CATEGORIES_DEMANDE = frozenset(("quete_vaincre", "quete_posseder", "tablo"))
P_BITS_J = 3                                      # entrée P : place j (bits 0-2), index dans W (bits 3-13)
P_PREMIER = 1 << 14                               # entrée P : la place est celle du 1er combattant de la rencontre
P_CLE = 0x3FFF                                    # clé de tri et de recherche du jeu (dichotomie sur ces bits)
P_EN_JEU_HAUT = 1 << 15                           # V3 (M2a-bis) : entrée P, bit 8 de l'id de l'espèce en jeu


def categories_exigence(categories, version: int = 1) -> set[str]:
    """Catégories d'exigence qui comptent pour la version `version` (raisons libres retirées). Version 6 : les
    catégories des dialogues des spots (CATEGORIES_SPOT) ne comptent plus ; si elles étaient les seules conditions
    détaillées de l'espèce, la raison générique « condition » de F (nom cité par une condition compilée) venait d'elles
    et tombe aussi."""
    cats = set(categories) - RAISONS_LIBRES
    if version >= VERSION_ZONES:
        # version 7 (lots M2b, décision de l'humain du 2026-10-19) : un sceau de légendaire n'exige plus de garder les
        # emplacements d'origine de ses membres : la couverture (un lieu normal d'avant la fin pour toute espèce du
        # réservoir) suffit au sceau, comme à tout check « Ami » ; une autre exigence de l'espèce garde son effet
        cats.discard("sceau_legendaire")
    if version >= 6 and cats & CATEGORIES_SPOT:
        cats -= CATEGORIES_SPOT
        if not any(c.startswith("condition:") for c in cats):
            cats.discard("condition")
    return cats


def politique(categories, version: int = 1) -> str:
    """« libre » (aucune exigence du jeu), « emplacements » (exigence de possession : un combattant gardé par
    emplacement d'origine) ou « tout » (tous les combattants gardés). Version 6 : voir `categories_exigence`."""
    cats = categories_exigence(categories, version)
    if not cats:
        return "libre"
    if "sans_rang" in cats:
        return "tout"
    if "condition" in cats:                       # raison générique de F : décidée par le détail des exigences
        cats.discard("condition")
        if not any(c.startswith("condition:") for c in cats):
            return "tout"
    return "emplacements" if cats <= POLITIQUE_POSSESSION else "tout"


def avant_fin(e: dict) -> bool:
    """Rencontre sauvage dont au moins un lieu est d'avant la fin (W, ou exclue pour une autre raison, §3.7). Une
    rencontre exclue parce qu'elle ne sort jamais dans cette version du jeu (version 2 du mélange, §20) n'en est pas
    une : on n'y trouve rien (cette raison n'existe pas dans les champs de la version 1)."""
    return "w" in e and (bool(e.get("w"))
                         or not {"apres_jeu", "hors_partie", RAISON_MORTE} & set(e.get("exclusion", ())))


def _melanger(alea: "_Alea", liste: list) -> list:
    out = list(liste)
    for i in range(len(out) - 1, 0, -1):          # Fisher-Yates
        j = alea.sous(i + 1)
        out[i], out[j] = out[j], out[i]
    return out


@dataclass
class DonneesRencontre:
    """Ce que le mélange par rencontre utilise de la base locale (format 7)."""
    w: list[int]                                          # rencontres de W' (hachages triés, champ `wp` de la base)
    rencontres: dict[int, dict]                           # hachage -> entrée de la base (rencontres sauvages)
    especes: dict[int, dict]                              # espèce -> {rang, base}
    reservoir: dict[int, int]                             # espèce -> rang
    politiques: dict[int, str]                            # espèce d'un combattant modifiable -> politique
    gardes: dict[tuple[int, int], str]                    # combattant gardé -> raison (tout, emplacement, loupe)
    groupes: list[list[tuple[int, int]]]                  # unités de tirage (combattants qui reçoivent la même espèce)
    origine: dict[tuple[int, int], int]                   # combattant modifiable (fichier, index) -> espèce d'origine
    presentes: set[int]                                   # espèces trouvables avant la fin sans tirage
    emplacements_de: dict[tuple[int, int], set[int]] = field(default_factory=dict)
    couverts: dict[int, set[int]] = field(default_factory=dict)
    # loupe jamais vide (format 9, §14) : masque WM_YOKAI_INFO des espèces du réservoir ; décors des points de loupe
    # dont un combattant du groupe est le 1er combattant (parallèle à `groupes` ; vide : aucune contrainte) ; points de
    # loupe (index d'emplacement) -> (1ers combattants modifiables, décors), pour l'audit
    masques: dict[int, int] = field(default_factory=dict)
    decors: list[tuple] = field(default_factory=list)
    points: dict[int, tuple] = field(default_factory=dict)
    version: int = 1                                      # version du mélange (§20) ; dans l'empreinte à partir de 2
    # version 3 (§21 ; vides avant) : combattants modifiables cités par une rencontre à lieu NORMAL (hors portail
    # mystère, qui sort, d'avant la fin) ; espèces qui ont un lieu normal sans tirage (combattant non modifiable ou
    # gardé d'une rencontre à lieu normal)
    normaux: set[tuple[int, int]] = field(default_factory=set)
    presentes_normales: set[int] = field(default_factory=set)
    # version 4 (§22 ; vide avant) : espèces invitées (dans `reservoir`, avec leur rang) : recrutables, dans aucune
    # rencontre sauvage ; elles n'ont donc ni emplacement d'origine ni lieu sans tirage
    invitees: set[int] = field(default_factory=set)
    # version 5 (« partout » ; vides avant) : périmètre (« base » ou « apres_jeu ») ; rencontres à règle « pas
    # d'amitié » (aucune espèce n'y est présente)
    perimetre: str = ""
    sans_amitie: set[int] = field(default_factory=set)

    @classmethod
    def depuis(cls, base: dict, version: int = 1, apres_jeu: bool = False,
               liberes: frozenset = frozenset()) -> "DonneesRencontre":
        """`liberes` (version 7) : espèces placées par zone : politique « libre » (aucun combattant gardé pour elles :
        leurs lieux d'origine changent ; le tirage les place dans leur zone)."""
        if not isinstance(base, dict) or base.get("format") not in FORMATS_BASE:
            raise RandoImpossible("base locale absente ou d'un autre format (réparer le mod)")
        base = vue_base(base, version, apres_jeu)
        if base["format"] < FORMAT_MELANGE_RENCONTRE:
            raise RandoImpossible("base locale d'un format antérieur, sans les emplacements des rencontres : à "
                                  "régénérer (ROM configurée, ou « Réparer le mod » dans le lanceur)")
        Donnees.depuis(base, version)                     # mêmes contrôles de la base que les modes σ
        v5 = version >= 5
        # version 5 : rencontres dont la règle de combat interdit l'amitié : leurs combattants fixes ne rendent aucune
        # espèce présente (on ne peut pas l'y recruter) ni ne couvrent un emplacement d'une espèce exigée
        sans_amitie = set(base.get("_sans_amitie", ())) if v5 else set()
        evt = base.get("evenement", {})
        evt_esp = {int(p) for p in evt.get("especes", [])}
        # W' : W + les rencontres exclues seulement pour la base de loupe du mélange σ (premier_partage, point_mixte) ;
        # défense en profondeur : jamais une rencontre d'évènement
        evt_renc = {int(h) for h in evt.get("rencontres", [])}
        w = sorted(int(e["h"]) for e in base["rencontres"] if e.get("wp") and int(e["h"]) not in evt_renc)
        ws = set(w)
        esp = {int(k): v for k, v in base["especes"].items()}
        # (version 5 : aussi les rencontres NON sauvages de W' : coffres piégés, trains, gymnase ; elles n'ont pas de
        # `w` : jamais « d'avant la fin » au sens de la couverture, `em` = leur emplacement virtuel)
        renc = {int(e["h"]): e for e in base["rencontres"] if "w" in e or (v5 and e.get("wp"))}
        fix = {int(p): r for p, r in base.get("fixees", {}).items()}
        exi = {int(p): r for p, r in base.get("exigees", {}).items()}

        # combattants modifiables, leurs emplacements ; emplacements où une espèce reste sans tirage
        origine: dict[tuple[int, int], int] = {}
        em_de: dict[tuple[int, int], set[int]] = {}
        premier_loupe: set[tuple[int, int]] = set()
        couverts: dict[int, set[int]] = {}
        presentes: set[int] = set()
        loupes = {i for i, x in enumerate(base.get("emplacements", ())) if x[1] == "loupe"}
        normales = normales_de(base, version)             # version 3 (§21) ; vide avant
        normaux: set[tuple[int, int]] = set()
        presentes_n: set[int] = set()
        par_point: dict[int, list[tuple[int, int]]] = {}
        point_fige: set[int] = set()                      # point dont un 1er combattant ne peut pas changer
        for h, e in sorted(renc.items()):
            em = {int(i) for i in e.get("em", ())}
            for n, c in enumerate(e["c"]):
                r, p = (int(e["f"]), int(c[0])), int(c[1])
                modifiable = h in ws and not c[6]
                if n == 0:
                    for i in sorted(em & loupes):
                        if modifiable:
                            par_point.setdefault(i, []).append(r)
                            premier_loupe.add(r)
                        else:
                            point_fige.add(i)       # rencontre hors de W' ou 1er combattant partagé : base d'origine
                if modifiable:
                    origine[r] = p
                    em_de.setdefault(r, set()).update(em)
                    if h in normales:
                        normaux.add(r)
                elif RAISON_MORTE in e.get("exclusion", ()):
                    pass        # version 2 (§20) : rencontre qui ne sort jamais : ni emplacement couvert ni source
                elif h in sans_amitie:
                    pass        # version 5 : rencontre sans amitié possible : ni emplacement couvert ni source
                else:
                    couverts.setdefault(p, set()).update(em)
                    if avant_fin(e):
                        presentes.add(p)
                        if h in normales:
                            presentes_n.add(p)
        # version 5 : combattants modifiables cités par une rencontre sauvage d'avant la fin (sources fiables : un
        # combattant gardé dans un coffre, un train ou une mission du gymnase ne rend pas son espèce « présente »)
        fiables = {(int(e["f"]), int(c[0])) for h, e in renc.items() if avant_fin(e) and h not in sans_amitie
                   for c in e["c"]} if v5 else set()

        def valide(p: int) -> bool:
            info = esp.get(p, {})
            return (info.get("recrutable") is True and bool(info.get("yokai")) and isinstance(info.get("rang"), int)
                    and 0 <= info["rang"] <= 5 and bool(info.get("medaille")) and not info.get("legendaire")
                    and p not in evt_esp)

        politiques = {}
        for p in sorted(set(origine.values())):
            cats = set(fix.get(p, ())) | set(exi.get(p, ()))
            if p in evt_esp:
                cats.add("evenement")
            if not isinstance(esp.get(p, {}).get("rang"), int):
                cats.add("sans_rang")                     # jamais remplacé sans rang connu (classe inconnue)
            politiques[p] = "libre" if version >= VERSION_ZONES and p in liberes else politique(cats, version)
        gardes: dict[tuple[int, int], str] = {}
        par_espece: dict[int, list[tuple[int, int]]] = {}
        for r, p in sorted(origine.items()):
            par_espece.setdefault(p, []).append(r)
        for p, rs in sorted(par_espece.items()):
            pol = politiques[p]
            if pol == "tout":
                gardes.update({r: "tout" for r in rs})
            elif pol == "emplacements":
                besoin = set().union(*(em_de[r] for r in rs)) - couverts.get(p, set())
                while besoin:                                # couverture gloutonne, déterministe
                    r = max(rs, key=lambda x: (len(em_de[x] & besoin), x not in premier_loupe, -x[0], -x[1]))
                    if not em_de[r] & besoin:
                        break
                    gardes[r] = "emplacement"
                    besoin -= em_de[r]
        if v5:
            # version 5 : une espèce RECRUTABLE ou du MÉDAILLIUM qui ne peut pas entrer dans le réservoir (sans n°, sans
            # rang, légendaire, non recrutable : Oni, maléfiques… dont le bit du Médaillium se pose à la VICTOIRE) n'est
            # jamais remplacée : ce serait la perdre (aucun tirage ne la remettrait ailleurs ; objectif Médaillium)
            for r, p in sorted(origine.items()):
                info = esp.get(p, {})
                if (info.get("recrutable") is True or info.get("medaille")) and not valide(p) and p not in evt_esp:
                    gardes.setdefault(r, "hors_reservoir")

        # point de loupe figé (une de ses rencontres hors de W', ou 1er combattant partagé) : la loupe montre la base
        # d'origine, les 1ers combattants de ses rencontres de W' restent d'origine (le reste de ces rencontres change)
        for i in sorted(point_fige & set(par_point)):
            for r in par_point[i]:
                gardes.setdefault(r, "loupe")
        # groupes des points de loupe (union des 1ers combattants des rencontres d'un même point)
        parent: dict[tuple[int, int], tuple[int, int]] = {}

        def racine(x):
            while parent.get(x, x) != x:
                x = parent[x]
            return x
        for i in sorted(par_point):
            rs = par_point[i]
            for r in rs[1:]:
                a, b = racine(rs[0]), racine(r)
                if a != b:
                    parent[max(a, b)] = min(a, b)
        membres: dict[tuple[int, int], list[tuple[int, int]]] = {}
        for r in sorted(origine):
            membres.setdefault(racine(r), []).append(r)
        # décors des points de loupe (format 9) : ceux que l'espèce d'un groupe doit pouvoir occuper
        dl = base.get("decors_loupe", {})
        points = {i: (tuple(rs), _decors(dl.get(str(i)))) for i, rs in sorted(par_point.items())}
        decors_de: dict[tuple[int, int], set] = {}
        for rs, dec in points.values():
            for r in rs:
                decors_de.setdefault(racine(r), set()).update(dec)
        groupes, decors = [], []
        for k, g in membres.items():
            rangs = {esp.get(origine[r], {}).get("rang") for r in g}
            if any(r in gardes for r in g) or len(rangs) != 1:
                for r in g:
                    gardes.setdefault(r, "loupe")          # le point montre la base d'origine : groupe entier gardé
            else:
                groupes.append(g)
                decors.append(tuple(sorted(decors_de.get(k, ()))))
        presentes |= {origine[r] for r in gardes if not v5 or r in fiables}
        presentes_n |= {origine[r] for r in gardes if r in normaux}

        # réservoir : espèces recrutables trouvables à l'état sauvage avant la fin
        sauvages_avant_fin = {int(c[1]) for e in renc.values() if avant_fin(e) for c in e["c"]}
        reservoir = {}
        for p in sorted(sauvages_avant_fin):
            if valide(p):
                reservoir[p] = esp[p]["rang"]
        invitees = invitees_de(base, version)             # version 4 (§22) ; vide avant
        reservoir.update(invitees)
        if v5:
            # version 5 : toute espèce valide d'un combattant MODIFIABLE (coffre, train, gymnase, après-jeu…) entre
            # dans le réservoir : remplacée là, elle reçoit un lieu normal ailleurs (couverture), jamais perdue
            for p in sorted(set(origine.values())):
                if valide(p):
                    reservoir.setdefault(p, esp[p]["rang"])
        especes = {p: {"rang": v.get("rang"), "base": v.get("base")} for p, v in esp.items()}
        masques = {p: int(esp[p].get("loupe") or 0) for p in reservoir}
        return cls(w, renc, especes, reservoir, politiques, gardes, groupes, origine, presentes, em_de, couverts,
                   masques, decors, points, version, normaux, presentes_n, set(invitees),
                   base.get("_perimetre", "") if v5 else "", sans_amitie)

    def empreinte(self) -> str:
        canon = {"format": FORMAT_EMPREINTE_RENCONTRE, "w": self.w,
                 "c": [[r[0], r[1], p, self.politiques[p], self.gardes.get(r, "")]
                       for r, p in sorted(self.origine.items())],
                 "g": sorted([sorted(map(list, g)), [list(x) for x in d]] for g, d in zip(self.groupes, self.decors)),
                 "r": [[p, k, self.especes.get(p, {}).get("base"), self.masques.get(p, 0)]
                       for p, k in sorted(self.reservoir.items())],
                 "pr": sorted(self.presentes)}
        if self.version != 1:                             # version 1 : forme canonique inchangée
            canon["melange"] = self.version
        if self.version >= 3:                             # versions 1 et 2 : formes canoniques inchangées
            canon["n"] = [sorted(map(list, self.normaux)), sorted(self.presentes_normales)]
        if self.version >= 4:                             # versions 1 à 3 : formes canoniques inchangées
            canon["i"] = sorted(self.invitees)
        if self.version >= 5:                             # versions 1 à 4 : formes canoniques inchangées
            canon["p"] = [self.perimetre, sorted(self.sans_amitie)]
        return hashlib.sha1(json.dumps(canon, separators=(",", ":")).encode()).hexdigest()


def _calculer_par_rencontre(base: dict, graine: int, mode: str, reference, loupe: bool = True,
                            version: int = 1, apres_jeu: bool = False, zones: dict | None = None) -> Melange:
    """`loupe` = False : tirage SANS la contrainte de décor (ancien comportement, pour l'audit « avant / après »
    seulement ; jamais écrit dans le jeu). `apres_jeu` : périmètre de la version 5 (ignoré avant). `zones` : version 7."""
    vue = vue_base(base, version, apres_jeu)
    don = DonneesRencontre.depuis(vue, version, apres_jeu)
    emp = don.empreinte()
    if reference is not None and emp != reference:
        raise RandoImpossible(f"base locale différente de la référence (empreinte {emp[:12]}… au lieu de "
                              f"{reference[:12]}…) : ROM d'une autre version ou RomFS modifié ; mélange refusé")
    cibles: list[tuple[int, int, str]] = []
    if version >= VERSION_ZONES:
        # version 7 : les Yo-kai demandés de la graine, libérés de leurs lieux d'origine (données recalculées APRÈS le
        # contrôle de l'empreinte, qui ne dépend pas de la graine)
        cibles = cibles_zones(vue, don, zones)
        don = DonneesRencontre.depuis(vue, version, apres_jeu, liberes=frozenset(p for _m, p, _r in cibles))
    if len(don.w) > CAP_W:
        raise RandoImpossible(f"{len(don.w)} rencontres dans W (boîte : {CAP_W} au plus)")
    par_rang = MODES_RENCONTRE[mode] == "rang"

    def classe(p: int) -> str:
        return f"rang{don.especes[p]['rang']}" if par_rang else "tout"
    reservoir: dict[str, list[int]] = {}
    for p in sorted(don.reservoir):
        reservoir.setdefault(classe(p), []).append(p)
    unites: dict[str, list[tuple[list[tuple[int, int]], tuple]]] = {}
    for g, dec in sorted(zip(don.groupes, don.decors)):
        unites.setdefault(classe(don.origine[g[0]]), []).append((g, dec if loupe else ()))
    alea = _Alea(graine, mode, emp)
    affectation: dict[tuple[int, int], int] = {}
    manquantes: list[int] = []
    sans_candidat = contraintes = 0
    zones_m: dict[int, tuple] = {}
    if version >= VERSION_ZONES:                          # version 7 : zones d'abord, puis la version 6 sur le reste
        affectation, manquantes, sans_candidat, contraintes, zones_m = _tirage7(don, alea, classe, reservoir, unites,
                                                                                cibles, zones)
    elif version >= 5:                                    # versions 1 à 4 : boucle par classe ci-dessous, inchangée
        affectation, manquantes, sans_candidat, contraintes = _tirage5(don, alea, classe, reservoir, unites)
    for c in (() if version >= 5 else sorted(set(unites) | set(reservoir))):
        us, res = unites.get(c, []), reservoir.get(c, [])
        a_couvrir = [p for p in res if p not in don.presentes]
        if not us or not res:
            manquantes += [p for p in a_couvrir if p not in don.invitees]     # (invitée sans unité : absente, annoncée)
            continue
        # loupe jamais vide (§14) : candidats d'une unité = espèces de la classe que la loupe peut montrer dans le
        # décor de TOUS les points dont un de ses combattants est le 1er (unité sans point de loupe : toute la classe)
        cands = [res if not dec else [p for p in res if posable(don.masques.get(p, 0), dec)] for _g, dec in us]
        ens = [None if not dec else set(k) for (_g, dec), k in zip(us, cands)]
        contraintes += sum(1 for e in ens if e is not None)
        # couverture : chaque espèce du réservoir absente sans tirage reçoit une unité distincte qui l'accepte, tirée au
        # hasard (les espèces les plus contraintes d'abord, puis chemins augmentants : couplage maximum)
        ordre = _melanger(alea, list(range(len(us))))
        if version >= 3:
            # §21 : chaque espèce sans lieu normal hors tirage reçoit une unité NORMALE (un de ses combattants est dans
            # une rencontre à lieu normal) distincte qui l'accepte : couplage maximum. REPLI pour une espèce qu'aucune
            # unité normale libre n'accepte : garantie de la version 2 (une unité quelconque, si elle n'est présente
            # nulle part sans tirage) ; elle est rendue dans `sans_lieu_normal`.
            norm = [any(r in don.normaux for r in g) for g, _dec in us]
            a_normal = _melanger(alea, [p for p in res if p not in don.presentes_normales])
            nb_ok = {p: sum(1 for n, e in enumerate(ens) if norm[n] and (e is None or p in e)) for p in a_normal}
            a_normal.sort(key=lambda p: nb_ok[p])            # tri stable : ordre du tirage à égalité
            if version >= 4:
                # §22 : les espèces du réservoir d'origine AVANT les invitées (tri stable). Le couplage par chemins
                # augmentants ne défait jamais un couple acquis : les espèces d'origine gardent tout ce qu'un couplage
                # maximum sans invitée leur donnait ; les invitées prennent des unités normales restantes.
                a_normal.sort(key=lambda p: p in don.invitees)
            couple = _couplage(a_normal, ordre, lambda p, n: norm[n] and (ens[n] is None or p in ens[n]))
            repli = [p for p in a_normal if p not in couple]
            libres = set(repli)
            a_couvrir = [p for p in repli if p not in don.presentes]
            couple = _couplage(a_couvrir, ordre, lambda p, n: (p in libres or norm[n])
                               and (ens[n] is None or p in ens[n]), couple)
        else:
            a_couvrir = _melanger(alea, a_couvrir)
            nb_ok = {p: sum(1 for e in ens if e is None or p in e) for p in a_couvrir}
            a_couvrir.sort(key=lambda p: nb_ok[p])               # tri stable : ordre du tirage à égalité
            couple = _couplage(a_couvrir, ordre, lambda p, n: ens[n] is None or p in ens[n])
        # (version 4, §22 : une invitée sans aucune unité possible n'est pas une erreur : elle reste absente, annoncée)
        manquantes += [p for p in a_couvrir if p not in couple and p not in don.invitees]
        choix = {n: p for p, n in couple.items()}
        for n, (g, _dec) in enumerate(us):
            p = choix.get(n)
            if p is None:
                if not cands[n]:                          # aucun candidat posable : l'unité garde son espèce d'origine
                    sans_candidat += 1
                    continue
                orig = {don.origine[r] for r in g}
                for _essai in range(4):                  # préférer une autre espèce que l'origine (effet visible)
                    p = cands[n][alea.sous(len(cands[n]))]
                    if p not in orig:
                        break
            for r in g:
                if p != don.origine[r]:
                    affectation[r] = p
    if manquantes:
        raise RandoImpossible(f"{len(manquantes)} espèce(s) du réservoir sans emplacement possible (classe sans combattant "
                              "libre)")
    rendus = 0
    if version >= VERSION_ZONES:
        affectation, rendus = _tenir_dans_la_boite(don, affectation, base, vue)
    entrees, especes = entrees_boite(don, affectation)
    changees = {don.origine[r] for r in affectation}
    renc_changees = {h for h in don.w for c in don.rencontres[h]["c"]
                     if not c[6] and (int(don.rencontres[h]["f"]), int(c[0])) in affectation}
    stats = {"combattants": len(don.origine), "gardes": len(don.gardes), "changes": len(affectation),
             "rencontres": len(don.w), "rencontres_changees": len(renc_changees), "reservoir": len(don.reservoir),
             "loupe_unites": contraintes, "loupe_sans_candidat": sans_candidat,
             "origines_changees": sorted(changees)}
    sans_normal: list[int] = []
    if version >= 3:                                      # versions 1 et 2 : `stats` (et rando_yokai.json) inchangés
        # constat exact, après le tirage : espèces du réservoir sans lieu normal (ni hors tirage, ni dans une rencontre
        # à lieu normal après affectation) ; vide sauf repli
        en_normal = {affectation.get(r, don.origine[r]) for r in don.normaux}
        sans_normal = sorted(p for p in don.reservoir if p not in don.presentes_normales and p not in en_normal)
        stats["sans_lieu_normal"] = sans_normal
    inv_abs: list[int] = []
    if version >= 4:                                      # §22 ; versions 1 à 3 : `stats` inchangés
        en_jeu = set(affectation.values())
        inv_abs = sorted(p for p in don.invitees if p not in en_jeu)
        stats["invitees"] = sorted(don.invitees)
        stats["invitees_absentes"] = inv_abs
    hors, figes = _ecarts(base, vue, "wp", 6)
    ajout, liberes = ({}, []) if version < 5 else _ajouts(vue["_brute"] if "_brute" in vue else base, vue)
    if version >= 5:                                      # versions 1 à 4 : `stats` inchangés
        # par catégorie de rencontre (sauvage d'origine, histoire, après-jeu, coffre, train, gymnase) : combattants
        # modifiables et changés ; raisons des combattants gardés
        par_cat: dict[str, list[int]] = {}
        cat_de = {}
        for h in don.w:
            for c in don.rencontres[h]["c"]:
                r = (int(don.rencontres[h]["f"]), int(c[0]))
                if r in don.origine:
                    cat_de.setdefault(r, ajout.get(h, "sauvage"))
        for r, k in cat_de.items():
            x = par_cat.setdefault(k, [0, 0])
            x[0] += 1
            x[1] += r in affectation
        stats["categories"] = {k: v for k, v in sorted(par_cat.items())}
        stats["gardes_raisons"] = dict(sorted(collections.Counter(don.gardes.values()).items()))
        stats["perimetre"] = don.perimetre
    if version >= VERSION_ZONES:                          # versions 1 à 6 : `stats` inchangés
        stats["zones"] = {str(m): [z, list(cs)] for _p, (m, z, cs) in sorted(zones_m.items())}
        stats["apres_jeu_rendus"] = rendus
    return Melange(mode, graine, emp, generation(graine, mode, emp), {}, {}, don.w, dict(don.reservoir), reservoir,
                   affectation, entrees, especes, dict(don.gardes), stats, version=version, hors_w=hors, figes=figes,
                   sans_normal=sans_normal, invitees=sorted(don.invitees), invitees_absentes=inv_abs,
                   perimetre=don.perimetre, ajout_w=ajout, liberes=liberes, zones=zones_m)


RANG_HAUT = 4                                     # version 5 : rangs A (4) et S (5) couverts dans n'importe quelle classe


def _tirage5(don: DonneesRencontre, alea: "_Alea", classe, reservoir: dict[str, list[int]],
             unites: dict[str, list[tuple[list, tuple]]]) -> tuple[dict, list[int], int, int]:
    """Tirage de la version 5 (« partout ») : (affectation, espèces du réservoir sans aucune place, unités sans
    candidat posable, unités contraintes par un décor de loupe).

    Comme la version 4 (couverture « lieu normal » par couplage maximum, espèces d'origine avant les invitées, repli
    annoncé, puis tirage libre DANS la classe), mais sur TOUTES les unités à la fois : une espèce de rang A ou S
    (RANG_HAUT) peut être couverte par une unité de n'importe quelle classe (décision de l'humain du 2026-10-17 : « un
    Yo-kai de rang A ou S peut atterrir n'importe où », niveau du lieu), après les unités de sa classe. Sans cela, les
    espèces de rang S que le périmètre « partout » fait entrer (missions du gymnase, coffres du Tunnel sans fin : 36)
    n'auraient que 20 unités de rang S, presque aucune à lieu normal. Le tirage libre reste dans la classe (le mélange
    « même rang » garde son équilibre)."""
    us: list[tuple[str, list, tuple]] = [(c, g, dec) for c in sorted(unites) for g, dec in unites[c]]
    especes = sorted(don.reservoir)
    cl = {p: classe(p) for p in especes}
    haut = {p for p in especes if don.reservoir[p] >= RANG_HAUT}
    norm = [any(r in don.normaux for r in g) for _c, g, _d in us]

    def accepte(p: int, n: int) -> bool:
        c, _g, dec = us[n]
        return (cl[p] == c or p in haut) and (not dec or posable(don.masques.get(p, 0), dec))
    cands = [[p for p in reservoir.get(c, []) if not dec or posable(don.masques.get(p, 0), dec)] for c, _g, dec in us]
    contraintes = sum(1 for _c, _g, dec in us if dec)
    ordre = _melanger(alea, list(range(len(us))))
    # 1. lieu normal, unités de la classe de l'espèce ; 2. espèces de rang A / S restées sans unité : unités normales de
    # toute classe ; 3. repli (annoncé par le constat `sans_normal`) : une unité quelconque, de sa classe puis de toute
    # classe pour les rangs A / S, pour une espèce présente nulle part sans tirage
    a_normal = _melanger(alea, [p for p in especes if p not in don.presentes_normales])
    nb_ok = {p: sum(1 for n in range(len(us)) if norm[n] and us[n][0] == cl[p] and accepte(p, n)) for p in a_normal}
    a_normal.sort(key=lambda p: nb_ok[p])
    a_normal.sort(key=lambda p: p in don.invitees)
    couple = _couplage(a_normal, ordre, lambda p, n: norm[n] and us[n][0] == cl[p] and accepte(p, n))
    # (point de départ : le couplage de l'étape 1 ; les chemins augmentants n'en défont aucun couple et rendent un
    # couplage MAXIMUM du graphe « unité normale qui accepte l'espèce », sa classe ou toute classe pour A / S)
    couple = _couplage(a_normal, ordre, lambda p, n: norm[n] and accepte(p, n), couple)
    repli = [p for p in a_normal if p not in couple and p not in don.presentes]
    ens_repli = set(repli)
    couple = _couplage(repli, ordre, lambda p, n: accepte(p, n) and (p in ens_repli or norm[n]), couple)
    manquantes = [p for p in repli if p not in couple and p not in don.invitees]
    choix = {n: p for p, n in couple.items()}
    affectation: dict[tuple[int, int], int] = {}
    sans_candidat = 0
    for n, (_c, g, _dec) in enumerate(us):
        p = choix.get(n)
        if p is None:
            if not cands[n]:                              # aucun candidat posable : l'unité garde son espèce d'origine
                sans_candidat += 1
                continue
            orig = {don.origine[r] for r in g}
            for _essai in range(4):                      # préférer une autre espèce que l'origine (effet visible)
                p = cands[n][alea.sous(len(cands[n]))]
                if p not in orig:
                    break
        for r in g:
            if p != don.origine[r]:
                affectation[r] = p
    return affectation, manquantes, sans_candidat, contraintes


# ------------------------------------------------------------------------------------------ zones (version 7)
def zones_client(zones_graine: dict, cartes_par_zone: dict, k: int) -> dict:
    """Paramètre `zones` de `calculer` : {n° : zone} de la graine (`zones.lire_slot_data`), cartes admises par zone
    (`zones.cartes_par_zone()` de l'APWorld du paquet, même table que la génération : empreinte contrôlée par
    l'appelant), K."""
    return {"especes": {int(m): str(r) for m, r in zones_graine.items()},
            "cartes": {str(r): sorted(cs) for r, cs in cartes_par_zone.items()}, "k": int(k)}


def cibles_zones(vue: dict, don: DonneesRencontre, zones: dict) -> list[tuple[int, int, str]]:
    """[(n° du Médaillium, espèce, zone)] des Yo-kai à placer : l'espèce du réservoir qui porte ce n° ; quand
    plusieurs espèces portent le même n° (bases distinctes : Chihuaglagla, Granpapéti), celle que le jeu CITE pour la
    demande d'abord (catégorie `quete_vaincre`, `quete_posseder` ou `tablo` de `exigees` dans la base), puis une espèce
    d'origine d'un combattant modifiable, puis le plus petit hachage. Refus si un n° n'a aucune espèce du réservoir ou
    si sa zone n'a aucune carte (table d'une autre version)."""
    origines = set(don.origine.values())
    exi = vue.get("exigees") or {}

    def demandee(p: int) -> bool:
        return bool(set(exi.get(str(p), ())) & CATEGORIES_DEMANDE)
    par_m: dict[int, list[int]] = collections.defaultdict(list)
    for p in don.reservoir:
        m = (vue.get("especes") or {}).get(str(p), {}).get("medaille")
        if isinstance(m, int):
            par_m[m].append(p)
    out = []
    for m, z in sorted(zones.get("especes", {}).items()):
        ps = sorted(par_m.get(int(m), ()), key=lambda p: (not demandee(p), p not in origines, p))
        if not ps:
            raise RandoImpossible(f"zones de la graine impossibles sur cette ROM : Yo-kai n° {m} hors du mélange")
        if not zones.get("cartes", {}).get(z):
            raise RandoImpossible(f"zones de la graine impossibles : zone {z!r} inconnue de ce client")
        out.append((int(m), ps[0], str(z)))
    return out


def condition_temps_seulement(c) -> bool:
    """Condition d'un lieu permise pour un Yo-kai demandé : aucune, ou l'heure seulement (créneau GetTimeNow : le lieu
    revient chaque jour ou chaque nuit) ; jamais une phase, un rang, un flag, une quête ni l'après-jeu."""
    return c is None or (isinstance(c, dict) and set(c) <= {"e", "heure"})


def lieux_unite(don: DonneesRencontre, g, renc_de: dict) -> list | None:
    """Lieux (sortant dans cette version : `mom` non nul) de toutes les rencontres de W' qui citent un combattant de
    l'unité ; None si l'une n'est pas une rencontre sauvage (coffre, train, gymnase, spot) ou si rien ne sort."""
    out = []
    for h in sorted(set().union(*(renc_de.get(r, ()) for r in g))):
        e = don.rencontres[h]
        lieux, mom = e.get("lieux"), e.get("mom")
        if "w" not in e or not isinstance(lieux, list) or not isinstance(mom, list) or len(mom) != len(lieux):
            return None
        out += [l for l, mo in zip(lieux, mom) if mo]
    return out or None


def zone_unite(lieux, cartes_zone: dict) -> str | None:
    """Zone où l'unité est ÉLIGIBLE pour un Yo-kai demandé : tous ses lieux sont des points de loupe ou des chemins
    d'errants (jamais une salle de portail), sans autre condition que l'heure, sur les cartes admises d'une MÊME zone."""
    if not lieux:
        return None
    zs = set()
    for l in lieux:
        if len(l) < 4 or l[1] not in ("loupe", "errant") or not condition_temps_seulement(l[3]):
            return None
        z = next((z for z, cs in cartes_zone.items() if l[0] in cs), None)
        if z is None:
            return None
        zs.add(z)
    return zs.pop() if len(zs) == 1 else None


def unites_eligibles(don: DonneesRencontre, cartes_zone: dict, us: list) -> dict[int, tuple[str, frozenset, frozenset]]:
    """Unité (rang dans `us`) -> (zone, cartes, emplacements) des unités éligibles (`zone_unite`)."""
    renc_de: dict[tuple[int, int], set[int]] = collections.defaultdict(set)
    for h in don.w:
        e = don.rencontres[h]
        for c in e["c"]:
            if not c[6]:
                renc_de[(int(e["f"]), int(c[0]))].add(h)
    sets = {z: set(cs) for z, cs in cartes_zone.items()}
    out = {}
    for n, (_c, g, _dec) in enumerate(us):
        lieux = lieux_unite(don, g, renc_de)
        z = zone_unite(lieux, sets)
        if z is not None:
            places = frozenset(i for r in g for i in don.emplacements_de.get(r, ()))
            out[n] = (z, frozenset(l[0] for l in lieux), places)
    return out


def _tirage7(don: DonneesRencontre, alea: "_Alea", classe, reservoir: dict[str, list[int]],
             unites: dict[str, list[tuple[list, tuple]]], cibles: list[tuple[int, int, str]], zones: dict):
    """Tirage de la version 7 : (affectation, manquantes, sans_candidat, contraintes, zones placées).

    1. Chaque Yo-kai demandé reçoit K unités ÉLIGIBLES de sa zone (`unites_eligibles`) que la loupe peut lui faire
       montrer (décor), distinctes : couplage maximum (chemins augmentants), une copie après l'autre ; la 2e et les
       suivantes sur d'AUTRES cartes que les précédentes de ce Yo-kai quand c'est possible, sinon à d'autres
       emplacements. Couplage incomplet : RandoImpossible (refus propre, cause publiée).
    2. Le reste : tirage de la version 5 / 6 (`_tirage5`) sur les unités restantes, les Yo-kai placés tenus pour
       présents à un lieu normal (leurs unités le sont : sauvages, d'avant la fin, sortant dans cette version)."""
    us = [(c, g, dec) for c in sorted(unites) for g, dec in unites[c]]
    elig = unites_eligibles(don, zones.get("cartes", {}), us)
    k = max(1, int(zones.get("k", 2)))
    ordre = _melanger(alea, list(range(len(us))))
    pris: set[int] = set()
    choix: dict[int, list[int]] = {i: [] for i in range(len(cibles))}

    def ok(i: int, n: int, strict: bool) -> bool:
        m, p, z = cibles[i]
        if n in pris or n not in elig or elig[n][0] != z:
            return False
        dec = us[n][2]
        if dec and not posable(don.masques.get(p, 0), dec):
            return False
        for prec in choix[i]:
            if (elig[n][1] & elig[prec][1]) if strict else (elig[n][2] & elig[prec][2]):
                return False
        return True
    gauche = list(range(len(cibles)))
    for _copie in range(k):
        couple = _couplage(gauche, ordre, lambda i, n: ok(i, n, True))
        if len(couple) != len(gauche):
            couple = _couplage(gauche, ordre, lambda i, n: ok(i, n, False), couple)
        if len(couple) != len(gauche):
            sans = sorted(cibles[i][0] for i in gauche if i not in couple)
            raise RandoImpossible("zones de la graine impossibles sur cette ROM : pas assez de lieux libres pour les "
                                  "Yo-kai n° " + ", ".join(map(str, sans)))
        for i, n in couple.items():
            choix[i].append(n)
            pris.add(n)
    affectation: dict[tuple[int, int], int] = {}
    places: dict[int, tuple] = {}
    for i, (m, p, z) in enumerate(cibles):
        for n in choix[i]:
            for r in us[n][1]:
                if p != don.origine[r]:
                    affectation[r] = p
        places[p] = (m, z, [sorted(elig[n][1]) for n in choix[i]])
    restes: dict[str, list] = {}
    for n, (c, g, dec) in enumerate(us):
        if n not in pris:
            restes.setdefault(c, []).append((g, dec))
    tenues = {p for _m, p, _z in cibles}
    don2 = dataclasses.replace(don, presentes=set(don.presentes) | tenues,
                               presentes_normales=set(don.presentes_normales) | tenues)
    aff2, manquantes, sans_candidat, contraintes = _tirage5(don2, alea, classe, reservoir, restes)
    affectation.update(aff2)
    contraintes += sum(1 for n in pris if us[n][2])
    return affectation, manquantes, sans_candidat, contraintes, places


def _tenir_dans_la_boite(don: DonneesRencontre, affectation: dict, base: dict, vue: dict) -> tuple[dict, int]:
    """Version 7 : les Yo-kai demandés libérés font beaucoup plus de places changées ; avec l'après-jeu, le total
    dépasse la boîte (3 321 entrées P au plus pour 3 072 ; sans l'après-jeu : 2 905 au plus) [C, ROM européenne].
    Règle fixe : des unités dont TOUTES les rencontres sont d'après-jeu (catégorie « apres_jeu » du périmètre) gardent
    leur espèce d'origine, dans l'ordre des unités, jusqu'à ce que tout tienne. Elles ne sont jamais des lieux normaux
    (ni couverture ni zone ne s'y appuient). (affectation, unités rendues) ; RandoImpossible si cela ne suffit pas."""
    places: dict[tuple[int, int], int] = collections.Counter()
    for h in don.w:
        e = don.rencontres[h]
        for c in e["c"]:
            if not c[6]:
                places[(int(e["f"]), int(c[0]))] += 1
    total = sum(places[r] for r in affectation)
    if total <= CAP_P_ETENDU:
        return affectation, 0
    ajout, _lib = _ajouts(vue["_brute"] if "_brute" in vue else base, vue)
    citees: dict[tuple[int, int], set[int]] = collections.defaultdict(set)
    for h in don.w:
        e = don.rencontres[h]
        for c in e["c"]:
            if not c[6]:
                citees[(int(e["f"]), int(c[0]))].add(h)
    aff = dict(affectation)
    rendus = 0
    for g in sorted(don.groupes):
        if total <= CAP_P_ETENDU:
            break
        if not any(r in aff for r in g) or not all(ajout.get(h) == "apres_jeu" for r in g for h in citees[r]):
            continue
        for r in g:
            if r in aff:
                total -= places[r]
                del aff[r]
        rendus += 1
    if total > CAP_P_ETENDU:
        raise RandoImpossible(f"mélange trop grand pour la boîte ({total} places)")
    return aff, rendus


def points_incompatibles(don: DonneesRencontre, affectation: dict[tuple[int, int], int]) -> list[int]:
    """Points de loupe (index d'emplacement) dont un 1er combattant modifiable reçoit une espèce que la loupe ne peut pas
    montrer dans le décor du point (§14 : loupe « Il n'y a rien ici » alors que le radar vise le point). Toujours vide
    pour un mélange calculé avec la contrainte de décor."""
    return [i for i, (rs, dec) in sorted(don.points.items())
            if any(r in affectation and not posable(don.masques.get(affectation[r], 0), dec) for r in rs)]


def entrees_boite(don: DonneesRencontre, affectation: dict[tuple[int, int], int]) -> tuple[list[int], list[tuple[int, int]]]:
    """Entrées P de la boîte v10 (u32 triés : place j | index dans W << 3 | P_PREMIER | id d'origine << 16 | id en jeu
    << 24), une par place d'une rencontre de W dont le combattant change (un combattant cité par plusieurs rencontres
    de W a une entrée par place : le jeu le réécrit une fois), et table des espèces [(CHARA_PARAM, CHARA_BASE)] (id =
    rang dans la table)."""
    idx_w = {h: i for i, h in enumerate(don.w)}
    brutes, ens = [], set()
    for h in don.w:
        e = don.rencontres[h]
        for n, c in enumerate(e["c"]):
            r = (int(e["f"]), int(c[0]))
            if c[6] or r not in affectation:
                continue
            brutes.append((idx_w[h], int(c[5]), n == 0, don.origine[r], affectation[r]))
            ens |= {don.origine[r], affectation[r]}
    base_de = lambda p: int(don.especes.get(p, {}).get("base") or 0)  # noqa: E731
    if don.version >= 6:
        # V3, lot M2a-bis : jusqu'à CAP_ESPECES_ETENDU espèces ; les espèces d'ORIGINE d'abord (leur id reste sur 8
        # bits), puis les espèces seulement tirées (id en jeu sur 9 bits : bit 15 de l'entrée, P_EN_JEU_HAUT)
        origines = {o for _wi, _j, _p, o, _x in brutes}
        especes = ([(p, base_de(p)) for p in sorted(origines)]
                   + [(p, base_de(p)) for p in sorted(ens - origines)])
        cap = CAP_ESPECES_ETENDU if len(origines) <= CAP_ESPECES else -1
    else:
        especes = sorted((p, base_de(p)) for p in ens)
        cap = CAP_ESPECES
    if len(especes) > cap or len(brutes) > (CAP_P_ETENDU if don.version >= 5 else CAP_P) or len(don.w) > CAP_W:
        raise RandoImpossible(f"mélange trop grand pour la boîte ({len(especes)} espèces, {len(brutes)} places)")
    id_de = {p: i for i, (p, _b) in enumerate(especes)}
    entrees = sorted(((wi << P_BITS_J) | j | (P_PREMIER if prem else 0) | (id_de[o] << 16)
                      | ((id_de[x] & 0xFF) << 24) | (P_EN_JEU_HAUT if id_de[x] >> 8 else 0)
                      for wi, j, prem, o, x in brutes), key=lambda v: v & P_CLE)
    return entrees, especes


def appliquer(base: dict, m: Melange) -> dict[int, list[tuple[int, int, int]]]:
    """Ce que le jeu fait (FUN_00506098) : pour chaque rencontre de W, ses combattants [(espèce d'origine, espèce en jeu,
    niveau)] ; un combattant partagé avec une rencontre hors W (drapeau de la base) n'est pas réécrit."""
    ws = set(m.w)
    out = {}
    for e in base["rencontres"]:
        if int(e["h"]) in ws:
            out[int(e["h"])] = [(int(c[1]), m.en_jeu(e, c), int(c[2])) for c in e["c"]]
    return out


def ou_trouver(base: dict, m: Melange | None, espece: int) -> list[dict]:
    """Lieux sauvages d'une espèce sous le mélange (tracker) : [{rencontre, carte, methode, condition, niveau,
    a_la_place_de}]."""
    out = []
    for e in base["rencontres"]:
        if "lieux" not in e:
            continue
        for c in e["c"]:
            orig = int(c[1])
            en_jeu = m.en_jeu(e, c) if m else orig
            if en_jeu == espece:
                for l in e["lieux"]:
                    carte, methode, cond = l[:3]
                    out.append({"rencontre": int(e["h"]), "carte": carte, "methode": methode, "condition": cond,
                                "niveau": int(c[2]), "a_la_place_de": orig if orig != espece else None,
                                "condition_decodee": l[3] if len(l) > 3 else None})
    return out


def _ecrire_json(p: Path, d: dict) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, p)


def ecrire_fichier_local(dossier: str | Path, m: Melange | None, ident_partie: int | None, etat: str,
                         jeu: dict | None = None) -> Path:
    """`rando_yokai.json` pour le tracker du lanceur : ce que le client a calculé (et écrit dans le jeu). Hachages
    seulement (les noms sont dans la base locale). `etat` : « actif », « aucun » (graine sans mélange), « refuse »
    (message), « attente » (sauvegarde non liée, jeu sans support…)."""
    d = {"format": FORMAT_FICHIER, "horodatage": time.time(), "ident_partie": ident_partie, "etat": etat,
         "jeu": jeu or {}}
    if m is not None:
        # `melange` (version, §20), `hors_w`, `figes` : absents pour la version 1 (fichier identique à avant)
        if m.version != 1:
            d.update({"melange": m.version, "hors_w": m.hors_w, "figes": [list(x) for x in m.figes]})
        if m.version >= 3:                              # §21 : espèces restées sans lieu normal (repli), en hachages
            d["sans_lieu_normal"] = list(m.sans_normal)
        if m.version >= 4:                              # §22 : espèces invitées, et celles restées sans place (repli)
            d.update({"invitees": list(m.invitees), "invitees_absentes": list(m.invitees_absentes)})
        d.update({"mode": m.mode, "graine": m.graine, "empreinte": m.empreinte, "generation": m.generation,
                  "sigma": {f"{a:#010x}": f"{b:#010x}" for a, b in sorted(m.sigma.items())},
                  "beta": {f"{a:#010x}": f"{b:#010x}" for a, b in sorted(m.beta.items())},
                  "classes": {c: len(v) for c, v in m.classes.items()}, "nb_w": len(m.w), "nb_d": len(m.d)})
        if m.version >= 5:                              # « partout » : périmètre, rencontres ajoutées au W', libérées
            d.update({"perimetre": m.perimetre,
                      "ajout_w": [[h, c] for h, c in sorted(m.ajout_w.items())],
                      "liberes": [list(x) for x in m.liberes]})
        if m.version >= VERSION_ZONES:                  # version 7 : zones des Yo-kai demandés (tracker « garanti à »)
            d["zones"] = [[f"{p:#010x}", mz[0], mz[1], mz[2]] for p, mz in sorted(m.zones.items())]
        if m.par_rencontre:
            # mélange par rencontre (§11) : combattant (index du fichier dans la base, index d'ENCOUNT_CHARA) -> espèce en
            # jeu, identités exclues ; « nb_d » = espèces d'origine dont au moins un emplacement change ; « gardes » (V3,
            # lot M1) : combattants modifiables gardés et leur raison (tout, emplacement, loupe, hors_reservoir), pour
            # que le tracker dise pourquoi un Yo-kai est resté à sa place (toutes versions : le calcul ne change pas)
            d.update({"affectation": [[f, k, f"{x:#010x}"] for (f, k), x in sorted(m.affectation.items())],
                      "nb_d": len(m.deplacees()),
                      "stats": {k: v for k, v in m.stats.items() if k != "origines_changees"},
                      "gardes": [[f, k, r] for (f, k), r in sorted(m.gardes.items())]})
    p = Path(dossier) / NOM_FICHIER
    _ecrire_json(p, d)
    return p


def lire_fichier_local(dossier: str | Path) -> dict | None:
    try:
        d = json.loads((Path(dossier) / NOM_FICHIER).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return d if isinstance(d, dict) and d.get("format") == FORMAT_FICHIER else None


def zones_medaillium(octets: bytes) -> dict[str, bytes]:
    """Octets lus à P+0x40C (au moins jusqu'à P+0x643) -> zones « vu », « comp », « compex » et « ami » (union)."""
    def zone(off):
        z = octets[off - P_VU:off - P_VU + TAILLE_MEDAILLIUM]
        return z if len(z) == TAILLE_MEDAILLIUM else b""
    vu, comp, compex = zone(P_VU), zone(P_COMP), zone(P_COMPEX)
    ami = bytes(a | b for a, b in zip(comp, compex)) if comp and compex else b""
    return {"vu": vu, "comp": comp, "compex": compex, "ami": ami}


def ecrire_medaillium(dossier: str | Path, ident_partie: int | None, octets: bytes,
                      ident_sauvegarde: int | None = None) -> Path:
    """`medaillium.json` (format 2) : zones du Médaillium de la sauvegarde liée, en hexadécimal, indexées par le n° du
    Médaillium (bit n & 7 de l'octet n >> 3) : « vu » (P+0x40C), « ami » (P+0x44C | P+0x604), et les deux zones brutes ;
    « octets » garde P+0x40C..0x48B (champ du format 1). `octets` : lecture groupée à P+0x40C (LECTURE_MEDAILLIUM)."""
    z = zones_medaillium(octets)
    p = Path(dossier) / NOM_MEDAILLIUM
    _ecrire_json(p, {"format": FORMAT_MEDAILLIUM, "horodatage": time.time(), "ident_partie": ident_partie,
                     "ident_sauvegarde": ident_sauvegarde, "p_offset": P_VU, "octets": octets[:0x80].hex(),
                     **{k: v.hex() for k, v in z.items()}})
    return p


def ecrire_progression(dossier: str | Path, ident_partie: int | None, progression: dict) -> Path:
    """`progression.json` : progression utile de la sauvegarde liée pour le filtre « Accessibles maintenant » du tracker
    (lue par le client : en-tête de la boîte et rang de montre réel) : `chapitre`, `pas_scenario`, `phase` (valeur de la
    condition GetPhase : chapitre × 10000 + pas, FUN_00646A68), `rang_montre` (0 = E … 5 = S, valeur de GetWatchRank ;
    None si illisible), `apres_jeu` (flag « partie terminée », valeur de GameClear)."""
    p = Path(dossier) / NOM_PROGRESSION
    _ecrire_json(p, {"format": FORMAT_PROGRESSION, "horodatage": time.time(), "ident_partie": ident_partie,
                     **progression})
    return p


def generer_base(rom: str | Path, dossier: str | Path) -> Path:
    """Génère `yokai_local.json` depuis la ROM du joueur (installation/rencontres.py), dans `dossier`."""
    import sys
    racine = Path(__file__).resolve().parents[1]          # archipelago/
    if str(racine) not in sys.path:
        sys.path.insert(0, str(racine))
    from installation import rencontres                    # noqa: E402  (module distribué avec le client)
    return rencontres.generer_fichier(rom, dossier)
