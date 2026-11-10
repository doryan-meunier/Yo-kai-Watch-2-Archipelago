"""Lieu du joueur pour le sous-onglet « Carte » du lanceur (suivi de la carte du jeu) : fichier local `lieu.json`.

Le jeu publie dans l'EN-TÊTE de la boîte (docs/systemes/archipelago_boite.md §29) la carte courante (CRC-32 de son nom
interne, ex. `t101g00`) et la position (x, z) du joueur ; le client lit déjà cet en-tête à chaque tour : aucun paquet
GDB en plus (`archipelago/tests/charge_gdb.py`). Ce module recopie ce lieu dans `<dossier>/lieu.json`, lu par le
lanceur (`lanceur/carte_checks.py`).

Un seul écrivain (le client), écriture atomique ; le lanceur ne fait que lire. Fréquence d'écriture bornée :
- changement de carte (ou carte perdue / retrouvée) : tout de suite ;
- position seule : au plus une fois par `PERIODE_POSITION` secondes, et seulement si le joueur s'est déplacé d'au
  moins `DEPLACEMENT_MIN` unités ;
- rien ne change : un rappel toutes les `PERIODE_RAPPEL` secondes (même contenu, nouvel horodatage) tant que le jeu
  publie un lieu, pour que le lanceur distingue un jeu en marche d'un fichier laissé par un client tué
  (`AGE_MAX` : au-delà, le lanceur ignore le fichier) ;
- jeu détaché, déconnecté, patch qui ne publie pas le lieu, arrêt du client : `oublier()` écrit « aucun lieu » une fois.

Contenu : `{"format": 1, "horodatage": time.time(), "publie": bool, "carte": hachage | 0, "x": float | null,
"z": float | null, "changement": n}` ; `changement` augmente à chaque changement de carte publié (diagnostic). Le
hachage est résolu en nom de carte par le lanceur (noms de `cartes_local.json`, généré chez le joueur) : aucune donnée
du jeu ici.
"""
from __future__ import annotations

import json
import math
import os
import time
from pathlib import Path
from typing import Callable

NOM_LIEU = "lieu.json"
FORMAT_LIEU = 1
PERIODE_POSITION = 2.0        # s : au plus une écriture de position par période
DEPLACEMENT_MIN = 3.0         # unités monde : en dessous, la position écrite n'est pas refaite
PERIODE_RAPPEL = 15.0         # s : rappel « le jeu publie toujours ce lieu » (même contenu, nouvel horodatage)
AGE_MAX = 45.0                # s : fichier plus ancien = jeu arrêté (côté lanceur)


def lire(dossier: str | Path) -> dict | None:
    """`lieu.json` (None : absent, illisible ou d'un autre format)."""
    try:
        d = json.loads((Path(dossier) / NOM_LIEU).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(d, dict) or d.get("format") != FORMAT_LIEU:
        return None
    return d


class SuiviLieu:
    """Recopie bornée du lieu publié par le jeu dans `lieu.json` (voir la docstring du module)."""

    def __init__(self, dossier: str | Path, horloge: Callable[[], float] = time.monotonic):
        self.fichier = Path(dossier) / NOM_LIEU
        self.horloge = horloge
        self.ecritures = 0                                   # depuis le lancement (tests, diagnostic)
        ancien = lire(dossier) or {}
        c = ancien.get("changement")
        self.changement = c if isinstance(c, int) and c >= 0 else 0
        # dernier contenu écrit par CE client : (publie, carte, position) ; None : rien écrit (fichier d'avant inconnu)
        self._ecrit: tuple | None = None
        self._t = 0.0
        if ancien.get("publie") or ancien.get("carte"):       # fichier laissé par un client tué : « aucun lieu »
            self._ecrire(False, 0, None)

    def _ecrire(self, publie: bool, carte: int, pos: tuple[float, float] | None) -> bool:
        d = {"format": FORMAT_LIEU, "horodatage": time.time(), "publie": bool(publie), "carte": int(carte),
             "x": round(pos[0], 2) if pos else None, "z": round(pos[1], 2) if pos else None,
             "changement": self.changement}
        tmp = self.fichier.with_name(self.fichier.name + ".tmp")
        try:
            self.fichier.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(json.dumps(d, separators=(",", ":")), encoding="utf-8")
            os.replace(tmp, self.fichier)
        except OSError:
            return False                                     # réessayé au prochain tour (rien n'est noté écrit)
        self._ecrit, self._t = (bool(publie), int(carte), pos), self.horloge()
        self.ecritures += 1
        return True

    def suivre(self, lieu: tuple[int, tuple[float, float] | None] | None) -> bool:
        """`lieu` : `Entete.lieu` de ce tour (None : le jeu ne publie pas le lieu). True si le fichier a été écrit."""
        if lieu is None:
            return self.oublier()
        carte, pos = lieu
        if not carte:
            pos = None
        avant = self._ecrit
        if avant is None or not avant[0] or avant[1] != carte:
            if avant is not None and avant[1] != carte or avant is None and carte:
                self.changement += 1
            return self._ecrire(True, carte, pos)            # changement de carte : tout de suite
        ecoule = self.horloge() - self._t
        if pos != avant[2]:
            if avant[2] is None or pos is None:
                return self._ecrire(True, carte, pos)        # position apparue / disparue
            if ecoule >= PERIODE_POSITION and math.hypot(pos[0] - avant[2][0], pos[1] - avant[2][1]) >= DEPLACEMENT_MIN:
                return self._ecrire(True, carte, pos)
        if carte and ecoule >= PERIODE_RAPPEL:
            return self._ecrire(True, carte, avant[2])       # rappel : même contenu, nouvel horodatage
        return False

    def oublier(self) -> bool:
        """Plus de lieu (jeu détaché ou déconnecté, patch sans lieu, arrêt) : écrit « aucun lieu » une seule fois."""
        if self._ecrit is None or not (self._ecrit[0] or self._ecrit[1]):
            return False
        return self._ecrire(False, 0, None)
