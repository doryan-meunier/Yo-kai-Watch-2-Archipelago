# -*- coding: utf-8 -*-
"""Multiplicateur d'XP (ap/multiplicateur-xp, demande de l'humain du 2026-11-06), côté APWorld. Module pur (aucun
import d'Archipelago). Conception et preuves : `docs/systemes/archipelago_multiplicateur_xp.md`.

Objet AP PROGRESSIF « Multiplicateur d'XP » (« Progressive EXP Multiplier »), 3 exemplaires, « utile » (aucune règle
ne le cite) : 1 reçu = expérience de combat x2, 2 = x3, 3 = x4. Option `multiplicateur_xp` (désactivée par défaut) :
les 3 exemplaires REMPLACENT 3 objets de remplissage (`__init__.create_items`) ; hors du plan (comme les pièges) : le
plan d'une graine est le même avec ou sans l'option, et sans elle `slot_data` est celui d'avant (ni don, ni verrou,
ni n° exigé).

Côté jeu (xp.cpp) et client : trois entrées de `slot_data.verrous_actifs` de même objet, k = 81, 82, 83 de la zone
ApVerrous3, `exemplaires` 1, 2, 3 (le client écrit déjà tout k >= 56 et sait lire `exemplaires`) ; n° exigés : 68
(verrou de la zone ApVerrous3, ajouté par `construire_slot_data`), 77 (client qui lit `exemplaires`) et 22.
"""
from typing import List

CLE = "multiplicateur_xp"            # clé d'objet de `donnees/objets.json`
FAMILLE = "multiplicateur_xp"        # famille d'`objets.json` : jamais dans le plan
EXEMPLAIRES = 3
OPTION_PAR_DEFAUT = False
VERROUS = (81, 82, 83)               # k de ApVerrous3 (xp.cpp, AP_VERROU_XP_1..3) ; exemplaires = rang + 1
MECANISME = "multiplicateur_xp"
FONCTION_CLIENT_EXEMPLAIRES = 77     # n° « client » du Mirapo de poche : le client lit `exemplaires`


def verrous_slot_data(id_ap: int) -> List[dict]:
    """Entrées de `slot_data.verrous_actifs` (une par k, même objet)."""
    return [{"objet": id_ap, "k": k, "cle": CLE, "hachage": 0, "melange": True, "mecanisme": MECANISME,
             "code_jeu": True, "exemplaires": i + 1} for i, k in enumerate(VERROUS)]


def nombre_ajoute(nb_remplissage: int) -> int:
    """Exemplaires mis au pool à la place d'autant d'objets de remplissage (jamais plus que le remplissage)."""
    return max(0, min(EXEMPLAIRES, int(nb_remplissage)))
