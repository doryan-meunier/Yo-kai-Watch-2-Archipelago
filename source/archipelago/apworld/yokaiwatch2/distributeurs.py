# -*- coding: utf-8 -*-
"""Checks des distributeurs de soda : V3, lot C1 (docs/systemes/archipelago_v3_distributeurs.md), sans Archipelago.

Décision de l'humain (2026-10-17) : TOUS les distributeurs, un check par BOISSON et par MACHINE, en option du YAML.
Mécanisme (jeu : fonction étendue 49, zone ApDistrib de la boîte, §50 de archipelago_boite.md) : SANS bit de
sauvegarde. Le client écrit pour chaque machine de la graine les boissons dont la location n'est pas encore cochée sur
le SERVEUR ; le jeu reconnaît la machine ouverte par (carte, identifiant du point regardé) et montre l'objet
Archipelago à la place de ces boissons (130 €, quantité 1) ; l'achat publie l'évènement DISTRIBUTEUR, le client envoie
la location. Achat perdu (jeu fermé avant que le client lise le journal) : l'article AP revient, il suffit de racheter.

Données (règle 6 de CLAUDE.md) : identifiants seulement, saisis à la main d'après `tools/romfs/cfg_entrees.py --nom
OP_VENDING_POINT` (lecture locale, jamais versionnée) : pour chaque carte, le NOMBRE de points OP_VENDING_POINT de son
fichier `_oneplace` et, par machine, son RANG dans ce fichier (0 = premier). **Aucun identifiant de point** (CRC-32 des
noms des points, champ 1) ni réglage : le client les lit dans la ROM DU JOUEUR (`archipelago/installation/
distributeurs.py`, fichier local `distributeurs_local.json`, jamais versionné ni distribué) et contrôle la lecture par
`EMPREINTE_DISTRIBUTEURS` (SHA-1 de la liste, pas la liste). Noms des locations saisis à la main.

ROM européenne [C, 54 points `OP_VENDING_POINT` sur 12 cartes, aucun dans un `_oneplace_gate`] : réglages
`shop_shpM001` / `M002` / `M003` (`_0.01n`) à 2 entrées SHOP_CONFIG_INFO sans condition (130 €) : 54 × 2 = 108 checks.
Identité stable d'une machine = (carte, identifiant du point), unique dans la carte [C] ; un même identifiant générique
se retrouve d'une carte à l'autre (la carte fait partie de la clé).

Règles : région de la carte et « Chapitre 2 terminé » au moins (comme les boutiques : prudent pour le début de partie,
130 € à payer) ; deux machines EXCLUES (remplissage seulement) :
- `t104g00` rang 1 : absente dès que le flag global 584 vaut 1 (condition du point) ; il est posé par la remise à
  zéro quotidienne (`RunCmdRpd_Common131`) quand le flag 2111 (repaire du Centre-ville, point OP_TERRITORY_POINT
  voisin) est posé et qu'un compteur de jours (octet global n° 602) est écoulé, et jamais remis à 0 : la machine peut
  disparaître pour toujours [C, scripts et données] (check ratable) ;
- `t103i27` : aucune route ni téléportation trouvée vers cette carte (`map_route`, `map_route_quest`, scripts) [C pour
  l'absence, ? pour l'accès] : accès non prouvé.
Les 14 machines de `t101g00` sont absentes pendant les phases 4 et 5 de la requête qs0120 (temporaire, sans effet).
"""
from typing import Dict, List, Tuple

from .boutiques import REGIONS_EN, REGIONS_FR

# Identifiants : nouvelle plage, jamais utilisée (59424000 + 2 × rang de la machine + boisson) ; l'ordre est celui de
# DISTRIBUTEURS (rang de la machine = index de son entrée dans la table du jeu, ApDistrib).
DISTRIBUTEUR_ID_BASE = 59424000
# Fonction étendue 49 du patch (bit 17 de ApPnj::fonctions, src/archipelago/verrous.h AP_FONCTION_DISTRIBUTEURS) et n°
# « client » 75 (jamais publié : un client d'avant, qui n'écrit pas la table, refuse la graine) : exigés par toute
# graine qui a l'option (avec le n° 22 des fonctions étendues).
FONCTION_DISTRIBUTEURS = 49
FONCTION_CLIENT_C1 = 75
BOISSONS = 2                         # lignes du menu d'un distributeur (= AP_DISTRIB_LIGNES)
CAP_JEU = 56                         # = AP_CAP_DISTRIB (boite.h)
# Empreinte de la lecture de la ROM du joueur (installation/distributeurs.py) : SHA-1 de la concaténation, dans l'ordre
# de DISTRIBUTEURS, de (CRC-32 du nom de la carte, identifiant du point, réglage) en u32 petit-boutistes. Contrôle de
# la lecture chez le joueur (ROM européenne attendue) ; la liste elle-même n'est dans aucun fichier du dépôt.
EMPREINTE_DISTRIBUTEURS = "a22c510b5ae4cda3bd2dba8c9cca658d2fa348ca"
NB_MACHINES = 54

# Carte -> (région de logique, nombre de points OP_VENDING_POINT du fichier `<carte>_oneplace`)
CARTES: Dict[str, Tuple[str, int]] = {
    "t101g00": ("les_hauts_de_granval", 14),
    "t103g00": ("coteau_fleuri", 9),
    "t103i27": ("coteau_fleuri", 1),
    "t103i37": ("coteau_fleuri", 1),
    "t104d05": ("centre_ville_de_granval", 1),
    "t104g00": ("centre_ville_de_granval", 13),
    "t104i61": ("centre_ville_de_granval", 2),
    "t105g00": ("quartier_des_boutiques", 6),
    "t106g00": ("la_corniche", 4),
    "t107g00": ("tour_excellence", 1),
    "t121g00": ("san_fantastico", 1),
    "t132g00": ("ourcival", 1),
}
# Machines EXCLUES (remplissage seulement) : (carte, rang) -> classe
EXCLUES: Dict[Tuple[str, int], str] = {("t104g00", 1): "x_territoire", ("t103i27", 0): "x_acces"}
# N de la règle « Chapitre N terminé » (au moins 2, comme les boutiques)
CHAPITRE_MIN = 2

MODES = ("aucun", "tous")
PAR_DEFAUT = "aucun"

DISTRIBUTEURS: List[dict] = []          # une entrée par machine, dans l'ordre des identifiants
LOCATIONS: List[dict] = []              # une entrée par (machine, boisson)


def _construire() -> None:
    for carte, (region, n) in CARTES.items():
        for rang in range(n):
            m = len(DISTRIBUTEURS)
            d = {"index": m, "carte": carte, "rang": rang, "nb_points": n, "region": region,
                 "classe": EXCLUES.get((carte, rang), "")}
            DISTRIBUTEURS.append(d)
            for i in range(BOISSONS):
                LOCATIONS.append({
                    "machine": m, "carte": carte, "rang": rang, "nb_points": n, "boisson": i, "region": region,
                    "classe": d["classe"], "id_ap": DISTRIBUTEUR_ID_BASE + BOISSONS * m + i,
                    "cle": "%s/%d/%d" % (carte, rang, i),
                    "nom_fr": "Distributeur : %s (%s) n° %d — boisson %d" % (REGIONS_FR[region], carte, rang + 1, i + 1),
                    "nom_en": "Vending machine: %s (%s) #%d — drink %d" % (REGIONS_EN[region], carte, rang + 1, i + 1)})


_construire()
LOCATIONS_PAR_ID: Dict[int, dict] = {x["id_ap"]: x for x in LOCATIONS}


def normaliser(mode) -> str:
    """Option `distributeurs` : nom du mode, ou booléen (True = tous)."""
    if mode is True:
        return "tous"
    if mode is False or mode is None:
        return "aucun"
    if mode not in MODES:
        raise ValueError(f"mode de distributeurs inconnu : {mode!r}")
    return mode


def locations_du_mode(mode: str) -> List[dict]:
    return list(LOCATIONS) if normaliser(mode) == "tous" else []


def exclue(x: dict) -> bool:
    return bool(x["classe"])
