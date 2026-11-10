# -*- coding: utf-8 -*-
"""Donjon des portails de La Corniche et récompense des coffres de fin de portail (V3, décisions de l'humain du
2026-10-27 ; docs/systemes/archipelago_portails_donjon.md). Module pur (sans Archipelago), importé par `logique.py`.

1. Option `donjon_portails` (désactivée par défaut, graines nouvelles seulement) : cinq objets AP « Clé du donjon des
   portails 1..5 », UNE PAR PORTE (et non une clé progressive) : les quatre portes à 10, 20, 30 et 40 globes partent
   toutes de la salle centrale t106d41 vers quatre sous-donjons INDÉPENDANTS (routes de `map_route` : t106d41 ->
   t106d45, t106d51, t106d56, t106d61 ; aucune route d'un sous-donjon à un autre) [C] ; une clé progressive imposerait
   un ordre que le jeu n'impose pas (les coffres derrière la porte à 30 globes exigeraient quatre clés au lieu de deux).
   Dans le jeu, une clé reçue relève l'octet global du compteur de sa porte au besoin (verrous k = 62..66, donjon.cpp) :
   la porte s'ouvre ; sans la clé, les globes l'ouvrent toujours (aucun masque).
   Règles (en plus de celle de la requête 6, `logique.QUETE_PORTAILS`, qui ouvre la porte à 5 globes) :
     coffre 444 (t106d46) : clés 1 + 2 ; coffres 445 (t106d52), 446 (t106d53) : clés 1 + 3 ; coffres 447 à 452
     (t106d58) : clés 1 + 4 ; coffre 453 (t106d62) : clés 1 + 5. Ces coffres ne sont plus exclus, SAUF le 453 : la
     route t106d61 -> t106d62 est refusée tant que le Yo-kai du Tablo-blabla n° 13 n'est pas APPELÉ (t106d61_trigger
     n° 4, type 23, GetGlobalBitFlag(2127) != 1 [C]) : posséder un Yo-kai précis n'est pas modélisable.
   Tromplœil (boss) et la requête 8 : la porte de Tromplœil (genre 1, octet 376, 4 « globes ») avance d'un à la fin de
   chaque sous-donjon (ev98_1260 après le boss de t106d49, t106d54, t106d59, t106d64) ; t106d64 est derrière les
   Tablo-blabla n° 13, 14 et 15 appelés (t106d61 n° 4, t106d62 n° 3, t106d63 n° 3) : ils restent EXCLUS, avec les cinq
   clés dans leur règle. Tablo-blabla n° 13 à 15 (t106d61..t106d63) : exclus comme avant (Yo-kai à posséder), clés
   1 + 5 dans leur règle.
   Le donjon ne dépend pas des portails mystères : on y entre par La Corniche (t106g00 -> t106d31 -> t106d33, routes
   sans condition), la porte à 5 globes exige la requête 6 finie (t106d33_trigger n° 1), dont le portail est scénarisé
   (salle fixée par la commande 0x3699) ; les fermetures des portails (4-35 à la fin du chapitre 4, tempête, siège)
   ne touchent que le tirage des portails, pas le donjon. Les locations ne portent donc plus la marque « portail ».
2. Option `portails_recompenses` (désactivée par défaut) : la récompense du coffre de fin de portail (1 à 5 globes à
   l'origine) devient l'entrée suivante d'une liste de NOMBRE objets du jeu tirée à la génération (slot_data
   `portails_recompenses` = [[hachage, quantité], …]), lue dans l'ordre par le jeu (zone ApPortails écrite par le
   client) ; les globes tirés par le jeu sont donnés EN PLUS, sans fenêtre : le joueur garde exactement le revenu de
   globes d'origine et peut toujours payer les portes sans les clés (105 globes pour les cinq portes, soit une
   trentaine de portails comme dans le jeu d'origine). Garder « une part » de globes dans la liste aurait au contraire
   allongé ce chemin (une entrée sur trois en globes : environ trois fois plus de portails).
   Aucun nom ni texte du jeu ici (règle 6) : hachages des objets saisis à la main (objets ordinaires et équipements des
   coffres du jeu), commentés par leur nom interne.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

# ------------------------------------------------------------------------------------------------ clés du donjon
OPTION_DONJON_PAR_DEFAUT = False
CLE_SLOT_DATA = "donjon_portails"            # true : graine générée avec l'option (plan du tracker)
CLES: Tuple[str, ...] = tuple("cle_donjon_portails_%d" % i for i in range(1, 6))
# Verrous étendus de la zone ApVerrous3 (k = 62..66 ; 61 réservé à ap/mirapo-poche) : entrées de
# `slot_data.verrous_actifs` (le client écrit tout k >= 56 génériquement), mécanisme « compteur de porte ».
VERROUS: Dict[str, dict] = {
    cle: {"k": 62 + i, "mecanisme": "porte_donjon", "code_jeu": True, "besoin": besoin, "octet": 371 + i}
    for i, (cle, besoin) in enumerate(zip(CLES, (5, 10, 20, 30, 40)))
}
REGION = "la_corniche"


def _cles(*n: int) -> Tuple[str, ...]:
    return tuple(CLES[i - 1] for i in n)


TOUTES = _cles(1, 2, 3, 4, 5)
# Coffres (index TBox) -> clés exigées
COFFRES: Dict[int, Tuple[str, ...]] = {444: _cles(1, 2), 445: _cles(1, 3), 446: _cles(1, 3),
                                       **{i: _cles(1, 4) for i in range(447, 453)}, 453: _cles(1, 5)}
# Restent EXCLUS : coffre 453, Tromplœil, requête 8, Tablo-blabla n° 13 à 15 (Yo-kai de Tablo-blabla à posséder et
# appeler sur le chemin) ET coffres 447 à 452 (t106d58) : `map_route` donne t106d56 -> t106d52 et t106d57 -> t106d51, et
# aucune route n'entre dans t106d57 : l'accès à t106d58 n'est PAS prouvé (revue verif/portails-donjon). À rendre non
# exclus (retirer 447..452 d'ici) quand l'essai en jeu T-PD4 aura montré que t106d56 mène à t106d57.
COFFRES_EXCLUS = frozenset(range(447, 454))   # 447..452 : revue verif/portails-donjon, accès non prouvé (voir ci-dessous)
TABLOS: Dict[int, Tuple[str, ...]] = {13: _cles(1, 5), 14: _cles(1, 5), 15: _cles(1, 5)}
BOSS: Dict[str, Tuple[str, ...]] = {"tromploeil": TOUTES}
QUETES: Dict[int, Tuple[str, ...]] = {8: TOUTES}


def cles_location(genre: str, index_tbox, cle) -> Tuple[Tuple[str, ...], bool] | None:
    """(clés exigées, reste exclue) d'une location du donjon, None si elle n'en est pas."""
    if genre == "coffre" and index_tbox in COFFRES:
        return COFFRES[index_tbox], index_tbox in COFFRES_EXCLUS
    if genre == "tablo" and cle is not None and str(cle).isdigit() and int(cle) in TABLOS:
        return TABLOS[int(cle)], True
    if genre == "boss" and cle in BOSS:
        return BOSS[cle], True
    if genre == "requete" and cle is not None and str(cle).isdigit() and int(cle) in QUETES:
        return QUETES[int(cle)], True
    return None


# ------------------------------------------------------------------------------------------------ récompenses
OPTION_RECOMPENSES_PAR_DEFAUT = False
CLE_SLOT_DATA_RECOMPENSES = "portails_recompenses"
NOMBRE = 28                                   # capacité de la zone ApPortails (boite.h, AP_CAP_PORTAILS)
FONCTION_CLIENT = 78                          # n° « client » (jamais publié) : client qui écrit la liste
# (hachage, quantité min, quantité max, poids) : objets ordinaires et équipements des coffres dorés du jeu
RECOMPENSES: Tuple[Tuple[int, int, int, int], ...] = (
    (0x6B85C07A, 1, 3, 6),   # nourriture (objets.json : riz_a_la_prune)
    (0x8162B121, 1, 3, 6),   # nourriture (barre_de_chocolat)
    (0xF585391C, 1, 2, 5),   # objets.json : the_de_l_ame
    (0x6D4E0291, 1, 3, 6),   # nourriture (hamburger)
    (0x6C8C68A6, 1, 3, 6),   # ifd0401 : boisson (y_cola)
    (0x1BEF34F5, 1, 3, 6),   # nourriture (riz_a_la_crevette)
    (0x8D2013A6, 1, 3, 6),   # itl0102 : remède
    (0x8EA4C7C8, 1, 2, 4),   # itl0302 : fortifiant
    (0x8D447F63, 1, 3, 6),   # itl0506 : orbe d'expérience (mini)
    (0x1320EAC0, 1, 3, 6),   # itl0501 : orbe d'expérience (petit)
    (0x8A29BB7A, 1, 2, 5),   # itl0502 : orbe d'expérience (moyen)
    (0xFD2E8BEC, 1, 1, 3),   # itl0503 : orbe d'expérience (grand)
    (0x634A1E4F, 1, 1, 1),   # itl0504 : orbe d'expérience (méga)
    (0x11665499, 1, 1, 3),   # itl0601 : objet à revendre (bronze)
    (0x886F0523, 1, 1, 2),   # itl0602 : objet à revendre (argent)
    (0x10A43EAE, 1, 1, 2),   # itl0701 : livre de techniques
    (0x89AD6F14, 1, 1, 2),   # itl0702 : livre de techniques
    (0xDC18FB9C, 1, 1, 2),   # ieq0002 : bracelet
    (0x4BCA2214, 1, 1, 1),   # ieq0009 : bracelet
    (0xDF9C2FF2, 1, 1, 2),   # ieq0202 : amulette
    (0x36FF8AC7, 1, 1, 1),   # ieq0204 : amulette
    (0x3E8BACDB, 1, 1, 1),   # ieq0308 : badge
)


def tirer_recompenses(rnd) -> List[List[int]]:
    """Liste de NOMBRE [hachage, quantité] tirée avec `rnd` (random.Random de la graine), au poids."""
    poids = [p for _h, _a, _b, p in RECOMPENSES]
    out = []
    for _ in range(NOMBRE):
        h, a, b, _p = rnd.choices(RECOMPENSES, weights=poids)[0]
        out.append([h, rnd.randint(a, b)])
    return out


def valider_recompenses(v) -> List[List[int]]:
    """Contrôle de forme (APWorld et client) : 1 à NOMBRE paires [hachage non nul sur 32 bits, quantité 1..99]."""
    if not isinstance(v, (list, tuple)) or not 1 <= len(v) <= NOMBRE:
        raise ValueError("liste des récompenses des portails : 1 à %d entrées" % NOMBRE)
    out = []
    for e in v:
        if not isinstance(e, (list, tuple)) or len(e) != 2:
            raise ValueError("entrée de récompense invalide : %r" % (e,))
        h, q = e
        if isinstance(h, bool) or isinstance(q, bool) or not isinstance(h, int) or not isinstance(q, int) \
                or not 0 < h < 1 << 32 or not 1 <= q <= 99:
            raise ValueError("entrée de récompense invalide : %r" % (e,))
        out.append([h, q])
    return out
