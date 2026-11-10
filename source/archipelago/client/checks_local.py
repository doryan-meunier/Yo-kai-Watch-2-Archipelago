"""Suivi des checks pour l'onglet « Checks » du lanceur : fichier local `checks.json`, logique « accessible », spoiler log.

Bibliothèque standard seulement, sans asyncio ni tkinter : importé par le client (`synchro.py`, qui écrit les fichiers)
et par le lanceur (`lanceur/checks.py`, qui les lit). Aucune lecture GDB : tout vient du serveur Archipelago (Connected,
RoomUpdate, ReceivedItems, LocationScouts, indices du data storage `_read_hints_{team}_{slot}`).

**Aucun spoiler par le fichier** (exigence de l'humain) : `construire_checks` ne recopie le contenu d'une location
(objet, destinataire) que si elle est FAITE ou si elle a fait l'objet d'un indice (hint) Archipelago ; le contenu de
toutes les locations n'est écrit que dans le spoiler log `.txt`, sur demande explicite du joueur (bouton du lanceur,
fichier `spoiler_demande.json` -> `spoiler_log.txt` + `spoiler_reponse.json`), jamais ailleurs.

Logique : celle de l'APWorld (`apworld/yokaiwatch2/logique.py`, pure, embarquée telle quelle dans le paquet avec
`donnees.py` et les JSON), importée à travers un paquet factice (le `__init__.py` du monde importe Archipelago). Le
plan de la graine est reconstruit à partir des options de `slot_data` (`options_de_slot_data`) ; les locations
réelles de la graine sont celles du serveur (checked + missing), le plan ne sert qu'aux zones, aux types et aux règles.

Accessibilité d'une location non faite (`evaluer`) :
- « logique » (sens d'Archipelago) : atteignable avec les objets reçus, les évènements « Chapitre N terminé » ramassés
  dès que leur règle est remplie (point fixe, comme le remplissage) ;
- « maintenant » : mêmes règles, mais les chapitres terminés sont ceux de la VRAIE progression (sauvegarde liée,
  `progression.json`, et checks « Histoire : chapitre N terminé » faits) ; sans progression connue, « maintenant » =
  « logique ».
États : `fait`, `accessible` (maintenant), `plus_tard` (en logique, mais il faut avancer dans l'histoire),
`bloque` (objets manquants), `inconnu` (location absente du plan local : APWorld d'une autre version).
"""
from __future__ import annotations

import collections
import importlib
import json
import os
import sys
import time
import types
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

NOM_CHECKS = "checks.json"
NOM_DEMANDE = "spoiler_demande.json"      # lanceur -> client : « écris le spoiler log » (nonce, langue)
NOM_REPONSE = "spoiler_reponse.json"      # client -> lanceur : {nonce, ok, fichier | erreur}
NOM_SPOILER = "spoiler_log.txt"
FORMAT_CHECKS = 1
# Location « Ami : Ovide » : la première des 16 des armées (apworld `amis_criminels.ID_ARMEES`) ; sa présence dans la
# liste `amis` d'une graine dit que la graine a ces 16 checks (mélange des Yo-kai par rencontre).
ID_AMI_ARMEES = 59420881
ID_BOSS_ESPECES = (59423031, 59423041)      # V3, lot 10 : places de boss d'après-jeu sans marqueur (check par espèce)
ID_BOSS_VOIE = (59423042, 59423045)         # ap/boss-voie-mystere : places de boss de la Voie du mystère
ID_TRIPTYK = 59423053                       # V3, lot 22 : terrain 3 de Ψ Blasters (graine générée depuis le lot 22)
ID_N045 = (59423797, 59423799)              # V3, lot 22 : articles de la boutique N045 (Château de Sawayama)
# V3, lot 22-bis : « Ami : Jiganyan » / « Ami : Komak » (terrains 11 / 12 de Ψ Blasters) et articles de la boutique
# N047 de l'Entrain Express (déjà dans le mode `toutes` depuis la V2 ; dans les autres modes depuis le lot 22-bis)
IDS_AMIS_BLASTERS = (59420950, 59420951)
ID_N047 = (59423780, 59423796)

DOSSIER_APWORLD = Path(__file__).resolve().parents[1] / "apworld" / "yokaiwatch2"
PAQUET_PUR = "ykw2_apworld_pur"           # même nom que les tests (archipelago/tests/apworld_pur.py) : même dossier

# Types de location affichés (filtres du lanceur) ; genre du plan -> type
TYPES = ("coffre", "objet_cle", "boss", "requete", "tablo", "chapitre", "velo", "ami", "criminel", "boutique",
         "distributeur")                  # (V3, lot C1 : distributeurs de soda)


def type_de(loc) -> str:
    """Type affiché d'une LocationPlan (genre du plan ; le Vélo est une « quete »)."""
    g = loc.genre
    if g == "emplacement":
        return "objet_cle"
    if g in ("histoire", "rang"):         # checks d'histoire (chapitres, Montée de rang : D)
        return "chapitre"
    if g == "quete":
        return "velo"
    if g == "blasters":                   # V3, lot 3 : terrain de Ψ Blasters fini = boss du terrain vaincu
        return "boss"
    if g == "invite":                     # invité de l'Auberge des voyageurs : check « Ami : <Yo-kai> »
        return "ami"
    return g if g in TYPES else "coffre"


# ------------------------------------------------------------------------------------------------ APWorld pur
_LOGIQUE: Any = None


def logique_apworld(dossier: Path | None = None):
    """Module `logique` de l'APWorld sans Archipelago (paquet factice sur son dossier) ; None s'il est absent."""
    global _LOGIQUE
    if _LOGIQUE is not None and dossier is None:
        return _LOGIQUE
    d = Path(dossier) if dossier else DOSSIER_APWORLD
    if not (d / "logique.py").is_file() or not (d / "donnees.py").is_file():
        return None
    if PAQUET_PUR not in sys.modules:
        p = types.ModuleType(PAQUET_PUR)
        p.__path__ = [str(d)]
        sys.modules[PAQUET_PUR] = p
    try:
        mod = importlib.import_module(PAQUET_PUR + ".logique")
    except Exception:                                      # noqa: BLE001 - le tracker reste utilisable sans logique
        return None
    if dossier is None:
        _LOGIQUE = mod
    return mod


def zones_apworld(dossier: Path | None = None):
    """Module `zones` de l'APWorld (V3, lots M2b), même paquet factice que `logique_apworld` ; None s'il est absent."""
    if logique_apworld(dossier) is None:
        return None
    try:
        return importlib.import_module(PAQUET_PUR + ".zones")
    except Exception:                                      # noqa: BLE001
        return None


def zones_de_slot_data(sd: dict | None) -> dict | None:
    """Zones des Yo-kai demandés de la graine ({n° du Médaillium: zone}) ; None : graine sans zones, ou table d'une
    autre version (le client refuse alors le mélange ; le tracker montre la règle d'avant)."""
    sd = sd if isinstance(sd, dict) else {}
    z = zones_apworld()
    if z is None or not sd.get(getattr(z, "CLE_SLOT_DATA", "yokai_zones")):
        return None
    try:
        return z.lire_slot_data(sd[z.CLE_SLOT_DATA])
    except (ValueError, TypeError, KeyError, IndexError):
        return None


def options_de_slot_data(sd: dict | None) -> dict:
    """Options de la graine utiles au plan, lues dans `slot_data` (formats 1 à 15 ; clé absente : valeur d'un format
    antérieur, sans ces locations). Aucune donnée du jeu."""
    sd = sd if isinstance(sd, dict) else {}
    verrous = []
    for v in sd.get("verrous_actifs") or []:
        cle = v.get("cle") if isinstance(v, dict) else None
        if isinstance(cle, str) and cle not in verrous:
            verrous.append(cle)
    apw = sd.get("apworld") if isinstance(sd.get("apworld"), dict) else {}
    return {
        "langue": apw.get("langue") if apw.get("langue") in ("fr", "en") else "fr",
        "objets_cles_melanges": bool(sd.get("objets_cles_melanges", True)),
        "verrous_actifs": verrous,
        "boss": sd.get("boss_mode") if isinstance(sd.get("boss_mode"), str) else ("histoire" if sd.get("boss") else
                                                                                   "aucun"),
        "tablos": sd.get("tablos_mode") if isinstance(sd.get("tablos_mode"), str) else "aucun",
        "quetes": sd.get("quetes_mode") if isinstance(sd.get("quetes_mode"), str) else "aucune",
        "chapitres": bool(sd.get("chapitres_mode", False)),
        "amis": sd.get("amis_mode") if isinstance(sd.get("amis_mode"), str) else "aucun",
        "yo_criminels": sd.get("criminels_mode") if isinstance(sd.get("criminels_mode"), str) else "aucun",
        "boutiques": sd.get("boutiques_mode") if isinstance(sd.get("boutiques_mode"), str) else "aucune",
        # classe de prix maximale en progression : sans effet sur les noms ni sur l'accessibilité (exclusion seulement)
        "boutiques_prix_max": int(sd.get("boutiques_prix_max", 2)) if str(sd.get("boutiques_prix_max", 2)).isdigit()
        else 2,
        # objets des Yo-kai d'évènement dans le pool (format 18) ; None : graine plus ancienne, inconnu (le tracker
        # montre alors leur section seulement si l'un d'eux a été reçu)
        "objets_evenement": bool(sd["objets_evenement"]) if "objets_evenement" in sd else None,
        # invités de l'Auberge à invitation (`invites_mode`, archipelago_invites.md §15) ; graine antérieure : aucun
        "invites": bool(sd.get("invites_mode", False)),
        # V3, lot 14 : armées à l'Auberge (objectif « medaillium_complet »), ordre d'arrivée des invités
        # (« reception » : ordre de réception des invitations ; clé absente d'une graine de la V2 : ordre de la liste)
        "invites_armees": bool(sd.get("invites_armees", False)),
        # V3, lot 20 : pièces spéciales du Crank-a-kai (clés absentes d'une graine sans l'option) et ordre de sortie
        # des 16 Yo-kai de la Pièce 5 étoiles de CETTE graine (n° du Médaillium)
        "pieces_speciales": sd.get("pieces_speciales") is True,
        "pieces_ordre": [n for n in sd["pieces_ordre"] if isinstance(n, int)]
        if isinstance(sd.get("pieces_ordre"), list) else None,
        # V3, lot 21 : graine à pièces générée depuis ce lot (Bananar et sa Pièce bleu ciel, fusions régionales non
        # exclues, Médaillium à 448 comptés) : reconnue à la fonction étendue 47 dans `fonctions_exigees`
        "lot21": isinstance(sd.get("fonctions_exigees"), list) and 47 in sd["fonctions_exigees"],
        # V3, lot 22 : graine générée depuis ce lot : fonction 48 exigée (pièces spéciales), terrain 3 de Ψ Blasters
        # (59423053) dans `blasters`, ou article de la boutique N045 (59423797..59423799) dans `boutiques` ; une graine
        # d'avant n'a aucun des trois (et le plan ne dépend du lot 22 que par eux)
        "lot22": (isinstance(sd.get("fonctions_exigees"), list) and 48 in sd["fonctions_exigees"])
        or any(isinstance(e, dict) and e.get("location") == ID_TRIPTYK for e in sd.get("blasters") or [])
        or any(isinstance(e, dict) and isinstance(e.get("location"), int)
               and ID_N045[0] <= e["location"] <= ID_N045[1] for e in sd.get("boutiques") or []),
        # V3, lot 22-bis : graine générée depuis ce lot : « Ami : Jiganyan / Komak » dans `amis`, ou article de N047
        # dans `boutiques` hors du mode `toutes` (qui les avait déjà) ; une graine d'avant n'a ni l'un ni l'autre (et le
        # plan ne dépend du lot 22-bis que par eux)
        "lot22bis": any(isinstance(e, dict) and e.get("location") in IDS_AMIS_BLASTERS for e in sd.get("amis") or [])
        or (sd.get("boutiques_mode") != "toutes"
            and any(isinstance(e, dict) and isinstance(e.get("location"), int)
                    and ID_N047[0] <= e["location"] <= ID_N047[1] for e in sd.get("boutiques") or [])),
        # V3 (2026-10-25) : étages de la Tour du commerce exclus (clé `tour_commerce_exclus` : graine générée depuis
        # ce lot ; absente d'une graine d'avant : ses locations restent non exclues, comme à sa génération)
        "tour_commerce": sd.get("tour_commerce_exclus") is True,
        # V3 (2026-10-27) : Tablo-blabla sans voie non créés (clé `tablos_apparition` : graine générée depuis ce lot)
        "tablos_apparition": sd.get("tablos_apparition") is True,
        # ap/portails-donjon : clés du donjon des portails (clé `donjon_portails` : graine générée avec l'option)
        "donjon_portails": sd.get("donjon_portails") is True,
        # ap/blasters-terrains-apworld : un objet par terrain de Ψ Blasters (clé `blasters_terrains` : graine générée
        # avec l'option) ; terrains d'autres éditions jouables seul (clé `blasters_autres_editions` : absente d'une
        # graine d'avant, dont les checks de Jiganyan / Komak sont infaisables seul : marqués par le tracker)
        "blasters_terrains": sd.get("blasters_terrains") is True,
        "blasters_editions": sd.get("blasters_autres_editions") is True,
        "invites_ordre": "reception" if sd.get("invites_ordre") == "reception" else "liste",
        # Yo-kai d'évènement à leur emplacement d'origine (liste `evenement_places`) ; graine antérieure : son pool
        # n'a ni les trois invitations ni la Capsule favorite
        "places": isinstance(sd.get("evenement_places"), list),
        # checks « Ami » des 16 Yo-kai des armées (graine à mélange des Yo-kai par rencontre générée depuis la branche
        # `ap/checks-fusions-armees`) : reconnus à la location « Ami : Ovide » dans la liste `amis` de la graine
        "armees": any(isinstance(e, dict) and e.get("location") == ID_AMI_ARMEES for e in sd.get("amis") or [])
        if isinstance(sd.get("amis"), list) else False,
        # identifiants des locations de boutique de la graine : une graine générée avant le retrait de N042 les contient
        # V3, lot 3 : objectif, étendue des checks d'après-jeu, mode Blasters (graine antérieure : valeurs de la V2)
        "objectif": sd.get("objectif") if isinstance(sd.get("objectif"), str) else "finir_chapitre_10",
        # V3, lot 18 : seuil de l'objectif « medaillium_complet » (absent pour tout autre objectif)
        "medaillium_seuil": sd.get("objectif_seuil") if isinstance(sd.get("objectif_seuil"), int) else None,
        "apres_jeu": sd.get("apres_jeu_mode") if isinstance(sd.get("apres_jeu_mode"), str) else "aucun",
        "blasters": sd.get("blasters_mode") if isinstance(sd.get("blasters_mode"), str) else "aucun",
        # V3, lot 6 : requêtes à transfert de sauvegarde dans la graine = fonction 37 du patch exigée (seul signal)
        "transfert": isinstance(sd.get("fonctions_exigees"), list) and 37 in sd["fonctions_exigees"],
        # audit softlock (2026-10-26) : graine générée depuis la fonction 52 du patch (chantier du Centre-ville sans
        # attente : zone de Sumochi exigée par les requêtes 45 / 58 et ce qui en dépend) : seul signal
        "chantier": isinstance(sd.get("fonctions_exigees"), list) and 52 in sd["fonctions_exigees"],
        # V3, lot 9 : les trois Parchemins au pool (clé `parchemins` ; graine antérieure : non)
        "parchemins": bool(sd.get("parchemins", False)),
        # V3, lot 17 : revanches de requêtes finies et boss de la Voie du mystère sans limite de jour réel (clé
        # absente d'une graine sans l'option : jeu d'origine). Sans effet sur le plan : mention du tracker seulement.
        "revanches_sans_limite": sd.get("revanches_sans_limite") is True,
        # V3, lot 10 : mélange des boss tiré à la génération (`rando_boss.sigma` d'une graine de version 2) : la place
        # du boss de l'objectif et les checks de boss par espèce en dépendent ; autre graine : aucun
        "boss_sigma": {k: v for k, v in sd["rando_boss"]["sigma"].items() if isinstance(k, str) and isinstance(v, str)}
        if isinstance(sd.get("rando_boss"), dict) and isinstance(sd["rando_boss"].get("sigma"), dict) else None,
        # V3, lot 10 : places de boss d'après-jeu sans marqueur (check par espèce) : reconnues à leurs identifiants
        # (59423031..59423041) dans la liste `amis` de la graine ; une graine d'avant n'en a aucune
        "boss_especes": any(isinstance(e, dict) and isinstance(e.get("location"), int)
                            and ID_BOSS_ESPECES[0] <= e["location"] <= ID_BOSS_ESPECES[1] for e in sd.get("amis") or [])
        if isinstance(sd.get("amis"), list) else False,
        # ap/boss-voie-mystere : places de boss de la Voie du mystère (check par espèce) : reconnues à leurs identifiants
        # (59423042..59423045) dans la liste `amis` ; une graine d'avant n'en a aucune (Voie dans la graine ou non)
        "boss_voie": any(isinstance(e, dict) and isinstance(e.get("location"), int)
                         and ID_BOSS_VOIE[0] <= e["location"] <= ID_BOSS_VOIE[1] for e in sd.get("amis") or [])
        if isinstance(sd.get("amis"), list) else False,
        # V3, lot C1 : distributeurs de soda (clé absente d'une graine sans l'option : aucun)
        "distributeurs": "tous" if sd.get("distributeurs_mode") == "tous" else "aucun",
        # V3, lot L1 : légendaires mélangés entre eux ([[sceau, légendaire donné], …] ; clé absente : aucun mélange)
        "legendaires": [[int(x[0]), int(x[1])] for x in sd["legendaires"]
                        if isinstance(x, (list, tuple)) and len(x) == 2 and all(isinstance(v, int) for v in x)]
        if isinstance(sd.get("legendaires"), list) else None,
        "boutiques_ids": sorted({x["location"] for x in sd["boutiques"] if isinstance(x, dict)
                                 and isinstance(x.get("location"), int)}) if isinstance(sd.get("boutiques"), list)
        else None,
        # V3, lots M2b : zones des Yo-kai demandés (clé `yokai_zones` ; graine d'avant, ou table d'une autre version :
        # None, règles d'avant)
        "yokai_zones": zones_de_slot_data(sd),
    }


def construire_plan(options: dict | None, langue: str = "fr", logique=None):
    """Plan de la graine (`logique.construire_plan`) pour ces options, noms dans `langue` ; None si impossible."""
    L = logique or logique_apworld()
    if L is None or not isinstance(options, dict):
        return None
    try:
        verrous = [k for k in options.get("verrous_actifs", []) if k in L.VERROUS_A_ACTIVER]
        return L.construire_plan(langue if langue in L.NOM_JEU else "fr", bool(options.get("objets_cles_melanges", True)),
                                 verrous, options.get("boss", "aucun"), options.get("tablos", "aucun"),
                                 options.get("quetes", "aucune"), bool(options.get("chapitres", False)),
                                 **_options_recentes(L, options))
    except (ValueError, KeyError, TypeError):
        return None


def _options_recentes(L, options: dict) -> dict:
    """Options ajoutées après la première version de `construire_plan` (amis, Yo-criminels : slot_data format 11),
    passées seulement si la logique chargée les connaît."""
    out = {}
    if hasattr(L, "normaliser_amis"):
        out["amis"] = options.get("amis", "aucun")
    if hasattr(L, "normaliser_criminels"):
        out["yo_criminels"] = options.get("yo_criminels", "aucun")
    if hasattr(L, "normaliser_boutiques"):
        out["boutiques"] = options.get("boutiques", "aucune")
        out["boutiques_prix_max"] = options.get("boutiques_prix_max", 2)
    if hasattr(L, "OBJETS_EVENEMENT_PAR_DEFAUT") and options.get("objets_evenement") is not None:
        out["objets_evenement"] = bool(options["objets_evenement"])     # pool seulement : aucune location n'en dépend
    if hasattr(L, "INVITES_PAR_DEFAUT"):
        out["invites"] = bool(options.get("invites", False))   # 30 objets et 30 checks « Ami : <invité> » de plus
    if hasattr(L, "INVITES_ARMEES"):                            # V3, lot 14 : les 16 des armées à l'Auberge
        out["invites_armees"] = bool(options.get("invites_armees", False))
    if hasattr(L, "PS"):                                        # V3, lot 20 : pièces spéciales du Crank-a-kai
        out["pieces_speciales"] = bool(options.get("pieces_speciales", False))
        if out["pieces_speciales"] and options.get("pieces_ordre"):
            out["pieces_ordre"] = list(options["pieces_ordre"])
        if hasattr(L.PS, "FONCTION_LOT21"):                     # V3, lot 21 (graine d'avant : faux)
            out["lot21"] = bool(options.get("lot21", False))
    if hasattr(L, "PS") and hasattr(L.PS, "FONCTION_LOT22"):    # V3, lot 22 (graine d'avant : faux)
        out["lot22"] = bool(options.get("lot22", False))
    if hasattr(L, "AJ") and hasattr(L.AJ, "AMIS_BLASTERS"):    # V3, lot 22-bis (graine d'avant : faux)
        out["lot22bis"] = bool(options.get("lot22bis", False))
    if hasattr(L, "PLACES_PAR_DEFAUT"):
        out["places"] = bool(options.get("places", False))     # 3 invitations + Capsule favorite au pool
    if "armees" in getattr(L.Plan, "__dataclass_fields__", {}):
        out["armees"] = bool(options.get("armees", False))     # 16 checks « Ami » des Yo-kai des armées
    if hasattr(L, "ids_retires") and options.get("boutiques_ids") is not None:
        # graine générée avant le retrait de N042 : ses locations restent dans le plan (tracker, carte)
        out["boutiques_retirees"] = not (set(options["boutiques_ids"]) & set(L.ids_retires()))
    if hasattr(L, "AJ"):
        # V3, lot 3 : valeurs inconnues de cette logique (APWorld plus récent) : celles de la V2
        if options.get("objectif") in L.AJ.OBJECTIFS:
            out["objectif"] = options["objectif"]
            if options.get("apres_jeu") in L.AJ.MODES_APRES_JEU:
                out["apres_jeu"] = options["apres_jeu"]
        if hasattr(L, "MD") and options.get("objectif") == L.MD.OBJECTIF \
                and isinstance(options.get("medaillium_seuil"), int):
            out["medaillium_seuil"] = options["medaillium_seuil"]    # V3, lot 18 : seuil du Médaillium
        if options.get("blasters") in L.AJ.MODES_BLASTERS:
            out["blasters"] = options["blasters"]
        if "transfert" in getattr(L.Plan, "__dataclass_fields__", {}):
            out["transfert"] = bool(options.get("transfert", False))   # V3, lot 6 : requêtes à transfert
        if "parchemins" in getattr(L.Plan, "__dataclass_fields__", {}):
            out["parchemins"] = bool(options.get("parchemins", False))  # V3, lot 9 : Parchemins au pool
        if "boss_sigma" in getattr(L.Plan, "__dataclass_fields__", {}):
            if options.get("boss_sigma"):
                out["boss_sigma"] = dict(options["boss_sigma"])         # V3, lot 10 : boss tirés à la génération
            out["boss_especes"] = bool(options.get("boss_especes", False))  # places sans marqueur : check par espèce
        if hasattr(L.AJ, "BOSS_VOIE_IDS"):                      # ap/boss-voie-mystere (graine d'avant : faux)
            out["boss_voie"] = bool(options.get("boss_voie", False))
    if "yokai_zones" in getattr(L.Plan, "__dataclass_fields__", {}) and options.get("yokai_zones"):
        out["yokai_zones"] = dict(options["yokai_zones"])           # V3, lots M2b : zones des Yo-kai demandés
    if "distributeurs" in getattr(L.Plan, "__dataclass_fields__", {}):
        out["distributeurs"] = options.get("distributeurs", "aucun")    # V3, lot C1 : 108 checks de distributeur
    if "legendaires" in getattr(L.Plan, "__dataclass_fields__", {}) and options.get("legendaires"):
        out["legendaires"] = [list(x) for x in options["legendaires"]]  # V3, lot L1 : légendaires mélangés
    if "chantier" in getattr(L.Plan, "__dataclass_fields__", {}):
        out["chantier"] = bool(options.get("chantier", False))      # audit softlock : graine d'avant = faux
    if hasattr(L, "TOUR_COMMERCE_COFFRES"):                    # V3 : Tour du commerce (graine d'avant : faux)
        out["tour_commerce"] = bool(options.get("tour_commerce", False))
    if hasattr(L, "TABLOS_YOKAI"):                             # V3 : Tablo-blabla (graine d'avant : faux)
        out["tablos_apparition"] = bool(options.get("tablos_apparition", False))
    if "donjon_portails" in getattr(L.Plan, "__dataclass_fields__", {}):
        out["donjon_portails"] = bool(options.get("donjon_portails", False))   # ap/portails-donjon
    if hasattr(L, "AJ") and hasattr(L.AJ, "VERROUS_TERRAINS"):    # ap/blasters-terrains-apworld (graine d'avant : faux)
        out["blasters_terrains"] = bool(options.get("blasters_terrains", False))
    if hasattr(L, "CLE_RANG_REEL"):
        # sémantique du verrou « rangs » de CETTE graine (slot_data format 20 : entrée « rangs_reel » = rang réel de la
        # montre donné par l'objet ; graine antérieure : rang AP exigé en plus du rang réel du jeu)
        out["rangs_reel"] = L.CLE_RANG_REEL in options.get("verrous_actifs", [])
    if hasattr(L, "CLE_RANG_S"):
        # ap/rang-s-objet : rang S = 5e « Rang de montre » (entrée « rangs_s ») ; graine d'avant : rang S par la requête 28
        out["rang_s_objet"] = L.CLE_RANG_S in options.get("verrous_actifs", [])
    return out


# ------------------------------------------------------------------------------------------------ accessibilité
def _jeton(n: int) -> str:
    return f"__chapitre_{n}__"


def regle_ok(plan, regle, etat: collections.Counter, prologue: bool = False) -> bool:
    """Même règle que `__init__._regle` de l'APWorld (objets, évènement « Chapitre N terminé », rangs, Filet)."""
    if regle.chapitres > 0 and etat[_jeton(regle.chapitres)] <= 0:
        return False
    if any(etat[k] <= 0 for k in regle.objets):
        return False
    if regle.rangs and etat[_objet_rang(plan)] < regle.rangs:
        return False
    if any(etat[k] < n for k, n in getattr(regle, "nombres", ())):      # V3, lot 20 : « k Pièces 5 étoiles »…
        return False
    if prologue and plan.objet_prologue and etat[plan.objet_prologue] <= 0:
        return False
    return True


def _objet_rang(plan) -> str:
    return "rang_de_montre"


def balayer(plan, objets: Iterable[str] | collections.Counter, chapitres_reels: int | None = None,
            region_origine: str = "menu") -> tuple[set[str], set[str], collections.Counter]:
    """(régions atteintes, noms des locations atteintes, état final). `objets` : clés reçues (avec répétition pour
    le Rang de montre). `chapitres_reels` None : évènements de chapitre ramassés par la logique (point fixe) ; sinon
    exactement les chapitres 1..chapitres_reels (vraie progression), jamais ramassés par la logique."""
    etat = collections.Counter(objets)
    if chapitres_reels is not None:
        for n in range(1, max(0, chapitres_reels) + 1):
            etat[_jeton(n)] += 1
    atteintes: set[str] = set()
    while True:
        regions = {region_origine}
        change = True
        while change:
            change = False
            for s, c, r in plan.connexions:
                if s in regions and c not in regions and regle_ok(plan, r, etat):
                    regions.add(c)
                    change = True
        nouveau = False
        for loc in plan.locations:
            if loc.nom in atteintes or loc.region not in regions:
                continue
            if not regle_ok(plan, loc.regle, etat, loc.prologue):
                continue
            atteintes.add(loc.nom)
            if loc.genre == "chapitre" and chapitres_reels is None:
                etat[_jeton(int(loc.cle))] += 1
                nouveau = True
            elif loc.genre == "objectif":
                etat["__but__"] += 1
        if not nouveau:
            return regions, atteintes, etat


def manquants(plan, loc, etat: collections.Counter, regions: set[str]) -> tuple[list[str], int, int]:
    """Ce qui manque à une location non atteinte : (clés d'objets, exemplaires de Rang de montre manquants, chapitres
    terminés exigés) d'après sa règle et les connexions vers sa région (depuis une région atteinte)."""
    objets: list[str] = []
    rangs = 0
    chap = loc.regle.chapitres
    regles = [(loc.regle, loc.prologue)]
    if loc.region not in regions:
        regles += [(r, False) for s, c, r in plan.connexions if c == loc.region and s in regions]
        if not any(c == loc.region and s in regions for s, c, _r in plan.connexions):
            # région atteinte par une autre région encore fermée : règles de toute la chaîne
            cible, vus = loc.region, set()
            while cible not in regions and cible not in vus:
                vus.add(cible)
                entree = next(((s, r) for s, c, r in plan.connexions if c == cible), None)
                if entree is None:
                    break
                regles.append((entree[1], False))
                cible = entree[0]
    chap = max([chap] + [r.chapitres for r, _p in regles])
    # chapitres exigés que la logique n'atteint pas : ce que LEUR règle exige (objets critiques, exemplaires de Rang de
    # montre des requêtes clés des chapitres 4 / 7 / 9) manque aussi à cette location
    regles += [(l.regle, False) for l in plan.locations
               if l.genre == "chapitre" and int(l.cle) <= chap and etat[_jeton(int(l.cle))] <= 0]
    for r, prologue in regles:
        for k in r.objets:
            if etat[k] <= 0 and k not in objets:
                objets.append(k)
        if r.rangs:
            rangs = max(rangs, r.rangs - etat[_objet_rang(plan)])
        for k, n in getattr(r, "nombres", ()):       # V3, lot 20 : exemplaires qui manquent (la pièce est nommée)
            if etat[k] < n and k not in objets:
                objets.append(k)
        if prologue and plan.objet_prologue and etat[plan.objet_prologue] <= 0 and plan.objet_prologue not in objets:
            objets.append(plan.objet_prologue)
    return objets, max(0, rangs), chap


@dataclass
class Acces:
    """Accessibilité calculée pour une location du plan (identifiant AP)."""
    etat: str                                  # accessible | plus_tard | bloque
    chapitres: int = 0                         # chapitres terminés exigés (règle et connexions)
    objets: tuple[str, ...] = ()               # clés d'objets manquants (bloque)
    rangs: int = 0                             # exemplaires de « Rang de montre » manquants (bloque)


def evaluer(plan, objets_recus: Iterable[str], chapitres_reels: int | None) -> dict[int, Acces]:
    """Accessibilité de chaque location (identifiant AP) du plan : voir la docstring du module."""
    recus = collections.Counter(objets_recus)
    regions_l, atteintes_l, etat_l = balayer(plan, recus, None)
    if chapitres_reels is None:
        regions_m, atteintes_m = regions_l, atteintes_l
    else:
        regions_m, atteintes_m, _e = balayer(plan, recus, chapitres_reels)
    out: dict[int, Acces] = {}
    for loc in plan.locations:
        if loc.id_ap is None:
            continue
        objets, rangs, chap = manquants(plan, loc, etat_l, regions_l)
        if loc.nom in atteintes_m:
            out[loc.id_ap] = Acces("accessible", chap)
        elif loc.nom in atteintes_l:
            out[loc.id_ap] = Acces("plus_tard", chap)
        else:
            out[loc.id_ap] = Acces("bloque", chap, tuple(objets), rangs)
    return out


def chapitres_termines(progression: dict | None, chapitres_faits: Iterable[int] = ()) -> int | None:
    """Chapitres vraiment terminés : progression de la sauvegarde liée (chapitre courant − 1 ; après-jeu : 10) et
    checks « Histoire : chapitre N terminé » faits ; None si rien n'est connu."""
    n: int | None = None
    if isinstance(progression, dict):
        ch = progression.get("chapitre")
        if isinstance(ch, int) and not isinstance(ch, bool) and ch >= 1:
            n = min(ch - 1, 10)
        if progression.get("apres_jeu") is True:
            n = 10
    faits = [int(x) for x in chapitres_faits]
    if faits:
        n = max(n or 0, max(faits))
    return n


# ------------------------------------------------------------------------------------------------ checks.json
def _nom_propre(texte: Any) -> str:
    return " ".join(str(texte or "").split())[:120]


def contenu_texte(objet: str, joueur: str | None, soi: bool, langue: str = "fr") -> str:
    """« <objet> » (pour soi) ou « <objet> (pour <joueur>) »."""
    if soi or not joueur:
        return objet
    return f"{objet} ({'for' if langue == 'en' else 'pour'} {joueur})"


def construire_checks(*, ident_partie: int | None, graine: str, slot: int | None, team: int | None, joueur: str,
                      options: dict, locations: Iterable[int], faites: Iterable[int],
                      contenus: dict[int, dict], indices: dict[int, dict], recus: list[dict],
                      connecte: bool, contenus_complets: bool) -> dict:
    """Contenu de `checks.json`. `contenus` : location -> {objet, joueur, soi, flags} pour TOUTES les locations connues
    du client (LocationScouts) : seul le contenu des locations FAITES est recopié (`contenus_faits`). `indices` :
    location de CE monde -> {objet, joueur, soi, trouve} (hints du serveur) : recopiés (contenu connu du joueur par
    l'indice). Le contenu d'une location non faite et sans indice n'est jamais écrit (aucun spoiler par le fichier)."""
    toutes = sorted({int(x) for x in locations})
    ensemble = set(toutes)
    faites_s = sorted({int(x) for x in faites} & ensemble) if ensemble else sorted({int(x) for x in faites})
    contenus_faits = {str(l): {k: contenus[l][k] for k in ("objet", "joueur", "soi", "flags") if k in contenus[l]}
                      for l in faites_s if l in contenus}
    ind = {str(int(l)): {k: v[k] for k in ("objet", "joueur", "soi", "trouve", "flags") if k in v}
           for l, v in sorted(indices.items()) if not ensemble or int(l) in ensemble}
    return {
        "format": FORMAT_CHECKS,
        "horodatage": time.time(),
        "ident_partie": ident_partie,
        "graine": str(graine or ""),
        "slot": slot,
        "team": team,
        "joueur": _nom_propre(joueur),
        "connecte": bool(connecte),
        "spoiler_disponible": bool(contenus_complets),
        "options": options,
        "locations": toutes,
        "faites": faites_s,
        "contenus_faits": contenus_faits,
        "indices": ind,
        "recus": recus,
    }


def _sans_date(d: dict) -> str:
    return json.dumps({k: v for k, v in d.items() if k != "horodatage"}, ensure_ascii=False, sort_keys=True)


def ecrire_checks(dossier: str | Path, d: dict, precedent: str | None = None) -> str | None:
    """Écrit `checks.json` (atomique) s'il a changé depuis `precedent` (empreinte renvoyée par l'appel précédent) ;
    renvoie la nouvelle empreinte, ou `precedent` si rien n'a changé (aucune écriture « pour rien »)."""
    empreinte = _sans_date(d)
    if empreinte == precedent:
        return precedent
    _ecrire_json(Path(dossier) / NOM_CHECKS, d)
    return empreinte


def _ecrire_json(p: Path, d: dict) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, p)


def lire_json(p: Path) -> dict | None:
    try:
        d = json.loads(Path(p).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return d if isinstance(d, dict) else None


# ------------------------------------------------------------------------------------------------ spoiler log
TEXTES_SPOILER = {
    "fr": {"titre": "Spoiler log - Yo-kai Watch 2 Archipelago",
           "avert": "ATTENTION : ce fichier révèle le contenu de tous vos checks.",
           "partie": "Graine : {graine} - joueur : {joueur} (slot {slot})",
           "date": "Généré le {date} par le client, d'après le serveur (LocationScouts).",
           "legende": "[x] fait   [ ] pas fait",
           "zone": "{zone} ({faits}/{total})", "autres": "Autres locations", "inconnu": "?",
           "total": "Total : {faits}/{total} checks faits."},
    "en": {"titre": "Spoiler log - Yo-kai Watch 2 Archipelago",
           "avert": "WARNING: this file reveals the contents of all your checks.",
           "partie": "Seed: {graine} - player: {joueur} (slot {slot})",
           "date": "Generated on {date} by the client, from the server (LocationScouts).",
           "legende": "[x] done   [ ] not done",
           "zone": "{zone} ({faits}/{total})", "autres": "Other locations", "inconnu": "?",
           "total": "Total: {faits}/{total} checks done."},
}


def texte_spoiler(*, langue: str, graine: str, joueur: str, slot: int | None, options: dict,
                  locations: Iterable[int], faites: Iterable[int], contenus: dict[int, dict],
                  noms_serveur: dict[int, str] | None = None, logique=None) -> str:
    """Spoiler log lisible, par zone (régions de l'APWorld) : chaque location de CE monde et son contenu (objet et
    destinataire). Écrit seulement sur demande du joueur (voir la docstring du module)."""
    lg = langue if langue in TEXTES_SPOILER else "fr"
    T = TEXTES_SPOILER[lg]
    faites_s = {int(x) for x in faites}
    toutes = sorted({int(x) for x in locations})
    plan = construire_plan(options, lg, logique)
    zones: dict[str, list[tuple[str, int]]] = collections.OrderedDict()
    noms_zones: dict[str, str] = {}
    places: set[int] = set()
    if plan is not None:
        noms_zones = dict(plan.regions)
        for cle, _nom in plan.regions:
            zones[cle] = []
        for loc in plan.locations:
            if loc.id_ap is not None and loc.id_ap in set(toutes):
                zones.setdefault(loc.region, []).append((loc.nom, loc.id_ap))
                places.add(loc.id_ap)
    autres = [((noms_serveur or {}).get(l) or f"#{l}", l) for l in toutes if l not in places]
    if autres:
        zones["__autres__"] = autres
        noms_zones["__autres__"] = T["autres"]
    lignes = [T["titre"], "=" * len(T["titre"]), "", T["avert"], "",
              T["partie"].format(graine=graine or "?", joueur=joueur or "?", slot=slot if slot is not None else "?"),
              T["date"].format(date=time.strftime("%Y-%m-%d %H:%M")), T["legende"], ""]
    for cle, locs in zones.items():
        if not locs:
            continue
        n = sum(1 for _n, l in locs if l in faites_s)
        titre = T["zone"].format(zone=noms_zones.get(cle, cle), faits=n, total=len(locs))
        lignes += [titre, "-" * len(titre)]
        for nom, l in locs:
            c = contenus.get(l)
            txt = contenu_texte(c.get("objet", "?"), c.get("joueur"), bool(c.get("soi")), lg) if c else T["inconnu"]
            lignes.append(f"  [{'x' if l in faites_s else ' '}] {nom} : {txt}")
        lignes.append("")
    lignes.append(T["total"].format(faits=len(faites_s & set(toutes)), total=len(toutes)))
    return "\n".join(lignes) + "\n"


def ecrire_spoiler(dossier: str | Path, texte: str) -> Path:
    p = Path(dossier) / NOM_SPOILER
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(texte, encoding="utf-8-sig")               # BOM : accents lisibles dans le Bloc-notes
    os.replace(tmp, p)
    return p


def demander_spoiler(dossier: str | Path, langue: str) -> str:
    """Lanceur : dépose une demande de spoiler log ; renvoie son nonce (à retrouver dans la réponse du client)."""
    nonce = os.urandom(8).hex()
    d = Path(dossier)
    try:
        (d / NOM_REPONSE).unlink()
    except OSError:
        pass
    _ecrire_json(d / NOM_DEMANDE, {"nonce": nonce, "langue": langue, "horodatage": time.time()})
    return nonce


def lire_reponse(dossier: str | Path, nonce: str) -> dict | None:
    """Lanceur : réponse du client à la demande `nonce` ({ok, fichier | erreur}), None tant qu'elle n'est pas là."""
    r = lire_json(Path(dossier) / NOM_REPONSE)
    return r if r and r.get("nonce") == nonce else None


def repondre(dossier: str | Path, nonce: str, ok: bool, fichier: Path | None = None, erreur: str = "") -> None:
    d = Path(dossier)
    _ecrire_json(d / NOM_REPONSE, {"nonce": nonce, "ok": bool(ok), "fichier": str(fichier) if fichier else None,
                                   "erreur": erreur, "horodatage": time.time()})
    try:
        (d / NOM_DEMANDE).unlink()
    except OSError:
        pass
