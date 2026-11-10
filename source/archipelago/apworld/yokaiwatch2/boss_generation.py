# -*- coding: utf-8 -*-
"""Mélange des boss tiré À LA GÉNÉRATION (V3, lot 10 : docs/systemes/archipelago_v3_boss_generation.md), sans Archipelago.

VERSION 2 du mélange des boss. La version 1 (V2 publiée, `rando_boss` = {"mode", "graine"}) est calculée chez le
joueur par `client/rando_boss.py` et n'est pas touchée. La version 2 n'existe que pour une graine dont l'objectif est
d'après-jeu : l'APWorld tire ici la permutation (la LOGIQUE doit savoir à quelle place se trouve le boss de
l'objectif) et l'écrit dans `slot_data.rando_boss` ; le client ne tire rien : il contrôle la permutation sur la ROM du
joueur (empreinte de référence, clés, classes, boss figés) puis calcule ses tables comme avant.

Table saisie à la main (règle 6 de CLAUDE.md : clés seulement, aucune donnée du jeu) : les mêmes clés que
`client/rando_boss.py` (`BOSS_SCRIPT`, `BOSS_SANS_SCRIPT`), vérifié par `test_v3_boss_generation`. La liste des boss
FIGÉS par l'anti-softlock dépend de la ROM ; elle est constante pour toute partie où le mélange s'applique, puisque le
client refuse toute ROM dont l'empreinte des boss diffère de la référence (ROM européenne : Triptyk, Carpitaine ;
Draconfus, Faux Kappa, Misterre, Sabrille, Démophage, Anguigne).

`sigma[x] = y` : le boss `y` prend la place du boss `x` (identités omises).

VERSION 3 (ap/boss-voie-mystere, 2026-11-06 : docs/systemes/archipelago_v3_boss_generation.md §10) : graine NOUVELLE
dont la Voie du mystère est dans la partie (objectif d'après-jeu et `apres_jeu` = complet, ou objectif
« medaillium_complet ») : les 4 boss de la Voie (Blingos, Cycloptique, Maximain à la fin commune t121d29, une place
par ligne ; Bogos à t121d35) ne sont plus figés. Mode « meme_classe » : entre eux (groupe « voie ») ; mode « total » :
avec les 18 autres boss d'après-jeu (22), SAUF avec l'objectif « medaillium_complet » : entre eux (la pièce de chaque
machine de la Voie est le butin de l'ESPÈCE du boss de la ligne, 100 % : à une place jouable une seule fois, une
requête, le boss ne donnerait plus assez de pièces pour les 7 Yo-kai des machines que cet objectif compte). Les places
de la Voie ne reçoivent jamais le boss d'un objectif « battre X » (accès jamais essayé en jeu). La version 2 est
inchangée (paramètre `version` à 2 par défaut : mêmes tirages, même entrée de slot_data).
"""
import hashlib
import random
from typing import Dict, Mapping, Optional, Tuple

VERSION = 2
VERSION_VOIE = 3                # version du tirage qui mélange aussi les 4 boss de la Voie du mystère
VERSIONS = (VERSION, VERSION_VOIE)
MODES = ("meme_classe", "total")
FONCTION_CLIENT_8 = 69          # n° « client » de `fonctions_exigees`, jamais publié par le jeu : un client qui ne sait
#                                 pas appliquer une permutation portée par la graine refuse la partie
FONCTION_CLIENT_VOIE = 82       # idem pour la version 3 (un client d'avant contrôle les groupes de la version 2 :
#                                 il refuserait le mélange, partie bloquée « Mélange boss refusé »)

# Boss à script d'AVANT la fin (classes de la version 1) : classe 1 = chapitres 3 à 7, classe 2 = chapitres 8 à 10
AVANT: Dict[str, int] = {
    "grolos": 1, "didgeai": 1, "barbefrousse": 1, "inamygal": 1, "volteface": 1, "laure_et_marge": 1,
    "tourboeillon": 1, "crocho": 1,
    "sabroclair": 2, "firmain": 2, "ombraptor": 2, "lady_perpetua_3": 2, "tromploeil": 2, "lady_demona": 2,
    "taprice": 2, "triptyk": 2, "carpitaine": 2,
}
# Boss d'APRÈS-JEU mélangés entre eux : les 12 de la chaîne des Limbes éternelles, dans l'ordre des combats, et 6 boss
# de requête
LIMBES: Tuple[str, ...] = ("hydreux", "porcinator", "styx_vi", "nebulor", "pr_letripe", "hagacuree", "rancornet",
                           "potofeu", "barbebluff", "mariotte_et_maribass", "lady_maggie", "filomene")
REQUETES: Tuple[str, ...] = ("thenuki", "infiniris", "chomino", "extrabuki", "laure_marge_ambronzio", "dr_jobard")
APRES_JEU: Tuple[str, ...] = LIMBES + REQUETES
# Version 3 : boss de la Voie du mystère, dans l'ordre des lignes (principale, farceurs, bouffis : fin commune t121d29,
# une rencontre et une place par ligne ; Grand-route dorée : t121d35)
VOIE: Tuple[str, ...] = ("blingos", "cycloptique", "maximain", "bogos")
# Figés (ni déplacés, ni remplacés) : anti-softlock de la ROM de référence (Triptyk : espèce à vaincre N fois ;
# Carpitaine : source d'une fusion exigée) ; réseau caché de San Fantastico (fermé à une partie normale) ; McKraken
# (décision du lot 10 : sa place exige le Tablo-blabla n° 24, marqueur remis à 0 chaque jour, victoire non relue)
FIGES: Dict[str, str] = {
    "triptyk": "anti_softlock", "carpitaine": "anti_softlock",
    "blingos": "hors_partie", "cycloptique": "hors_partie", "maximain": "hors_partie", "bogos": "hors_partie",
    "mckraken": "mckraken",
}
# Boss sans script : seule l'espèce change ; mélangés entre eux dans les deux modes
SANS_SCRIPT: Tuple[str, ...] = ("meganyan", "fumella", "injustin", "cyrustre", "fielippine", "maudicko", "roneen")
SANS_SCRIPT_FIGES: Tuple[str, ...] = ("draconfus", "faux_kappa", "misterre", "sabrille", "demophage", "anguigne")
# Places où le boss d'un OBJECTIF n'est jamais mis (accès non prouvé, voir le document §1.3) ; elles restent mélangées
# pour les autres boss
PLACES_SANS_OBJECTIF: Tuple[str, ...] = ("infiniris", "laure_marge_ambronzio")
PLACES_SANS_OBJECTIF_VOIE: Tuple[str, ...] = PLACES_SANS_OBJECTIF + VOIE     # version 3


def _version(version: int) -> int:
    if version not in VERSIONS:
        raise ValueError(f"version du mélange des boss inconnue : {version!r}")
    return version


def figes(version: int = VERSION) -> Dict[str, str]:
    """Boss à script figés de cette version (version 3 : la Voie du mystère n'en est plus)."""
    return {k: v for k, v in FIGES.items() if _version(version) == VERSION or k not in VOIE}


def places_sans_objectif(version: int = VERSION) -> Tuple[str, ...]:
    return PLACES_SANS_OBJECTIF_VOIE if _version(version) == VERSION_VOIE else PLACES_SANS_OBJECTIF


def groupes(mode: str, version: int = VERSION, voie_separee: bool = False) -> Dict[str, Tuple[str, ...]]:
    """Groupes de boss à script permutés entre eux (boss figés retirés), pour ce mode (et cette version : la 3 ajoute
    les boss de la Voie du mystère ; `voie_separee` : en mode « total », la Voie reste un groupe à part, objectif
    « medaillium_complet »). Les groupes que le CLIENT contrôle sont ceux de `voie_separee` faux : une permutation de
    groupes plus fins en est aussi une."""
    if mode not in MODES:
        raise ValueError(f"mode de mélange des boss inconnu : {mode!r}")
    v3 = _version(version) == VERSION_VOIE
    libres = [k for k in AVANT if k not in FIGES]
    if mode == "meme_classe":
        g = {"classe1": tuple(k for k in libres if AVANT[k] == 1),
             "classe2": tuple(k for k in libres if AVANT[k] == 2), "limbes": LIMBES, "requetes": REQUETES}
        if v3:
            g["voie"] = VOIE
        return g
    if v3 and voie_separee:
        return {"avant": tuple(libres), "apres": APRES_JEU, "voie": VOIE}
    return {"avant": tuple(libres), "apres": APRES_JEU + (VOIE if v3 else ())}


class _Alea:
    """Tirages déterministes, indépendants de la version de Python (`getrandbits` seulement)."""

    def __init__(self, graine: int, mode: str, version: int = VERSION):
        h = hashlib.sha256(f"ykw2ap-boss-generation:{version}:{int(graine)}:{mode}".encode()).digest()
        self.r = random.Random(int.from_bytes(h[:16], "little"))

    def sous(self, n: int) -> int:
        k = max(1, n.bit_length())
        while True:
            v = self.r.getrandbits(k)
            if v < n:
                return v

    def permuter(self, orig) -> list:
        perm = list(orig)
        for i in range(len(perm) - 1, 0, -1):             # Fisher-Yates
            j = self.sous(i + 1)
            perm[i], perm[j] = perm[j], perm[i]
        return perm


def tirer(graine: int, mode: str, boss_objectif: Optional[str] = None, version: int = VERSION,
          voie_separee: bool = False) -> Tuple[Dict[str, str], Dict[str, str]]:
    """(σ, σ_N) de la graine : σ sur les boss à script (par groupe de `groupes(mode, version, voie_separee)`), σ_N sur
    les boss sans script. `boss_objectif` : boss que l'objectif fait vaincre ; un groupe est retiré tant qu'il le met à
    une place de `places_sans_objectif(version)` (tirage à rejet, déterministe). Version 2 : tirage d'avant, inchangé."""
    alea = _Alea(graine, mode, _version(version))
    interdites = places_sans_objectif(version)
    sigma: Dict[str, str] = {}
    for nom, orig in sorted(groupes(mode, version, voie_separee).items()):
        orig = sorted(orig)
        while True:
            perm = alea.permuter(orig)
            if boss_objectif is None or all(y != boss_objectif or x not in interdites
                                            for x, y in zip(orig, perm)):
                break
        sigma.update({x: y for x, y in zip(orig, perm) if x != y})
    orig_n = sorted(SANS_SCRIPT)
    sigma_n = {x: y for x, y in zip(orig_n, alea.permuter(orig_n)) if x != y}
    return sigma, sigma_n


def controler(mode: str, sigma: Mapping[str, str], sigma_n: Mapping[str, str], version: int = VERSION) -> None:
    """Lève ValueError si (σ, σ_N) n'est pas un mélange de cette version pour ce mode (permutation de chaque groupe,
    aucun boss figé)."""
    reste = dict(sigma)
    for nom, membres in groupes(mode, version).items():
        part = {x: reste.pop(x) for x in list(reste) if x in membres}
        if sorted(part) != sorted(part.values()) or any(x == y for x, y in part.items()):
            raise ValueError(f"mélange des boss : le groupe {nom} n'est pas permuté dans lui-même")
    if reste:
        raise ValueError(f"mélange des boss : boss figés ou inconnus déplacés ({sorted(reste)})")
    if set(sigma_n) - set(SANS_SCRIPT) or sorted(sigma_n) != sorted(sigma_n.values()) \
            or any(x == y for x, y in sigma_n.items()):
        raise ValueError("mélange des boss sans script invalide")


def apres_jeu(sigma: Optional[Mapping[str, str]]) -> Dict[str, str]:
    """Partie de σ qui porte sur les places d'après-jeu (la seule dont la logique dépend) ; places de la Voie du
    mystère comprises (version 3 : une permutation de version 2 n'en a jamais)."""
    return {x: y for x, y in (sigma or {}).items() if x in APRES_JEU or x in VOIE}


def version_de(sigma: Optional[Mapping[str, str]]) -> int:
    """Version minimale d'une permutation : 3 dès qu'un boss de la Voie y est déplacé."""
    return VERSION_VOIE if any(x in VOIE or y in VOIE for x, y in (sigma or {}).items()) else VERSION


def slot_data(mode: str, graine: int, sigma: Mapping[str, str], sigma_n: Mapping[str, str],
              version: int = VERSION) -> dict:
    """Entrée `rando_boss` d'une graine de version 2 (ou 3 : mode « <mode>#3 »)."""
    controler(mode, sigma, sigma_n, version)
    return {"mode": f"{mode}#{_version(version)}", "graine": int(graine) & 0x7FFFFFFF,
            "sigma": dict(sorted(sigma.items())), "sigma_n": dict(sorted(sigma_n.items()))}
