# -*- coding: utf-8 -*-
"""Légendaires mélangés entre eux (V3, lot L1 : docs/systemes/archipelago_v3_legendaires.md), sans Archipelago.

Décisions de l'humain (2026-10-17) : chaque SCEAU du Médaillium donne un AUTRE légendaire ; les huit Yo-kai demandés
par chaque sceau ne changent pas ; les sceaux POSSIBLES dans la graine se mélangent entre eux, les sceaux IMPOSSIBLES
entre eux (rien d'obtenable ne devient inobtenable) ; le lanceur dit quel sceau donne quel légendaire. Option du YAML
`legendaires_melanges` (désactivée par défaut).

Données saisies à la main (règle 6 de CLAUDE.md) : n° du Médaillium des huit légendaires (322 à 329) ; le sceau d'un
légendaire est désigné par le n° de son légendaire D'ORIGINE (sceau 322 = celui dont les huit membres donnent
Shogunyan dans le jeu d'origine). Membres : `medaillium.SCEAUX` (relus sur la ROM par `outils/medaillium_voies.py`).

FAISABILITÉ D'UN SCEAU dans une graine (classes du mélange) [C : archipelago_v3_boss_objectifs.md §5.1,
archipelago_v3_objectif_medaillium.md] : tout sceau est possible dans le jeu (après-jeu, Tunnel sans fin, Crank-a-kai,
Bingo-kai, au hasard ou non) SAUF :
- Komashura (323) : deux membres (Scolérique 299, Parantonn 106) sont des Yo-kai des ARMÉES, sans lieu dans cette
  version du jeu ; possible seulement si la graine leur en donne un (mélange des Yo-kai par rencontre de version >= 4 :
  `amis_criminels.armees_garanties`, ou les armées à l'Auberge : `invites_armees`, posé par l'objectif Médaillium) ;
- Savantard (327) : Kyubi (80) et Octorgone (320) n'existent que par les requêtes à TRANSFERT de sauvegarde ; possible
  seulement avec l'option `requetes_transfert` (que l'objectif Médaillium force).
Gorgouille (324) et Slurpent (329) : leurs membres sont les 16 Yo-kai de la Pièce 5 étoiles, trouvables sans l'option
`pieces_speciales` au Tunnel sans fin et au Crank-a-kai (pièces de couleur, Pandanoko, gymnase) [S : chance faible,
mais pas nulle] : classés possibles.

RÈGLES : le check « Ami : L » (bit « ami » du n° L, exclu comme avant) prend la règle, la région et l'existence de
l'entrée d'origine du SCEAU qui donne L dans cette graine (`apres_jeu.AMIS`, origine « legendaire ») : seul le
légendaire au bout change. Objectif Médaillium : la voie de L est le sceau qui le donne (même classe : 448 / 448).
Sans l'option : exactement le plan d'avant.
"""
from typing import Dict, FrozenSet, Iterable, Optional, Sequence, Tuple

from . import medaillium as MD

OPTION_PAR_DEFAUT = False
LEGENDAIRES: Tuple[int, ...] = tuple(range(322, 330))
KOMASHURA, SAVANTARD = 323, 327
# Fonction étendue 50 du patch (bit 18 de ApPnj::fonctions : `src/archipelago/legendaires.cpp`) et n° « client » 76,
# JAMAIS publié par le jeu : un client d'avant accepterait la graine sans écrire la permutation dans ApLegendes (le
# tracker dirait « tel sceau donne tel légendaire » sans que le jeu le fasse) ; il la refuse sur ce n° (et sur le 22).
FONCTION_JEU = 50
FONCTION_CLIENT = 76
CLE_SLOT_DATA = "legendaires"


def possibles(armees: bool, transfert: bool) -> FrozenSet[int]:
    """Sceaux (n° du légendaire d'origine) dont les huit membres sont obtenables dans la graine."""
    out = set(LEGENDAIRES)
    if not armees:
        out.discard(KOMASHURA)
    if not transfert:
        out.discard(SAVANTARD)
    return frozenset(out)


def classes(armees: bool, transfert: bool) -> Tuple[Tuple[int, ...], Tuple[int, ...]]:
    """(sceaux possibles, sceaux impossibles), triés : la permutation ne mélange qu'à l'intérieur de chaque classe."""
    p = possibles(armees, transfert)
    return tuple(sorted(p)), tuple(sorted(set(LEGENDAIRES) - p))


def tirer(alea, armees: bool, transfert: bool) -> Tuple[Tuple[int, int], ...]:
    """Permutation d'une graine : ((sceau, légendaire donné), …) triée par sceau, tirée UNE fois à la génération avec
    `alea` (le générateur du monde ; appelé seulement pour une graine qui a l'option : le flux des autres ne change pas).
    Chaque classe est mélangée à part (possibles d'abord) : dans une classe de deux sceaux ou plus, AUCUN sceau ne
    garde son légendaire (« un sceau donne un AUTRE légendaire » : tirages répétés jusqu'à une permutation sans point
    fixe, bornés, puis décalage d'un cran) ; une classe d'un seul sceau reste forcément en place."""
    out: Dict[int, int] = {}
    for c in classes(armees, transfert):
        dest = list(c)
        if len(c) >= 2:
            for _ in range(200):
                alea.shuffle(dest)
                if all(a != b for a, b in zip(c, dest)):
                    break
            else:
                dest = list(c[1:]) + [c[0]]
        out.update(zip(c, dest))
    return tuple(sorted(out.items()))


def valider(paires, armees: bool, transfert: bool) -> Tuple[Tuple[int, int], ...]:
    """Permutation lue (slot_data, tracker) : ((sceau, légendaire), …) triée ; ValueError si ce n'est pas une
    permutation des huit, ou si elle fait passer un légendaire d'une classe à l'autre."""
    try:
        p = tuple(sorted((int(s), int(l)) for s, l in paires))
    except (TypeError, ValueError):
        raise ValueError(f"légendaires : permutation illisible {paires!r}")
    if [s for s, _ in p] != list(LEGENDAIRES) or sorted(l for _, l in p) != list(LEGENDAIRES):
        raise ValueError(f"légendaires : pas une permutation des huit sceaux : {p!r}")
    ok = possibles(armees, transfert)
    for s, l in p:
        if (s in ok) != (l in ok):
            raise ValueError(f"légendaires : le sceau {s} (possible : {s in ok}) donnerait {l} (possible : {l in ok})")
    return p


def sceau_de(paires) -> Dict[int, int]:
    """Légendaire -> sceau qui le donne (identité sans permutation)."""
    if not paires:
        return {n: n for n in LEGENDAIRES}
    return {l: s for s, l in paires}


def membres_de(paires) -> Dict[int, Tuple[int, ...]]:
    """Légendaire -> les huit membres du sceau qui le donne (`medaillium.SCEAUX` si aucune permutation)."""
    s = sceau_de(paires)
    return {l: MD.SCEAUX[s[l]] for l in LEGENDAIRES}


def slot_data(paires) -> list:
    """`slot_data.legendaires` = [[sceau, légendaire donné], …] (n° du Médaillium, triés par sceau)."""
    return [[int(s), int(l)] for s, l in sorted(paires)]


def depuis_slot_data(valeur) -> Optional[Tuple[Tuple[int, int], ...]]:
    """Permutation de `slot_data.legendaires` (forme seulement ; None si la clé est absente ou illisible)."""
    if not isinstance(valeur, list):
        return None
    try:
        p = tuple(sorted((int(x[0]), int(x[1])) for x in valeur))
    except (TypeError, ValueError, IndexError, KeyError):
        return None
    if [s for s, _ in p] != list(LEGENDAIRES) or sorted(l for _, l in p) != list(LEGENDAIRES):
        return None
    return p
