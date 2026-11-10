"""Ennemis du combat en cours et « déjà ami » pour la fenêtre d'amitié du lanceur : fichier local `amis_combat.json`.

Le jeu (patch `YKW2_AP`, `src/archipelago/amis_combat.cpp`) publie pendant un combat la liste des Yo-kai ennemis
(espèce CHARA_PARAM, n° du Médaillium, déjà ami ou non) dans la zone `ApAmisCombat` (0x40 octets) et, dans l'EN-TÊTE
que le client lit déjà à chaque tour, deux bits d'`etat` et un numéro (`amis_numero`) qui change avec la liste
(`docs/systemes/archipelago_boite.md` §53, `docs/systemes/archipelago_fenetre_amitie.md`). Ce module :
- ne lit RIEN hors combat (bit ETAT_EN_COMBAT absent) ni quand le numéro n'a pas changé : un paquet GDB par
  changement de la liste (début du combat, ennemi remplacé, ami obtenu), quelques-uns par combat ;
- recopie la liste dans `<dossier>/amis_combat.json`, lu par le lanceur (`lanceur/fenetre_amitie.py`).

Un seul écrivain (le client), écriture atomique. Rappel du même contenu toutes les `PERIODE_RAPPEL` secondes pendant un
combat (le lanceur ignore un fichier de plus de `AGE_MAX` secondes : client tué). « Aucune donnée » une fois quand le
jeu est détaché, déconnecté, que le patch ne publie pas la liste, ou à l'arrêt.

Contenu : `{"format": 1, "horodatage": time.time(), "publie": bool, "combat": bool, "numero": n,
"ennemis": [{"param": hachage CHARA_PARAM, "medaille": n° (0 : aucun), "ami": true | false | null, "emplacement": i}]}`.
Aucun texte du jeu : le lanceur résout l'espèce en nom par la base locale générée chez le joueur (`yokai_local.json`).
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Awaitable, Callable

try:
    from . import boite_protocole as bp
except ImportError:                                          # pragma: no cover - selon le mode d'import
    import boite_protocole as bp                            # type: ignore[no-redef]

NOM_FICHIER = "amis_combat.json"
FORMAT = 1
PERIODE_RAPPEL = 10.0         # s : rappel du même contenu pendant un combat (nouvel horodatage)
AGE_MAX = 30.0                # s : au-delà, le lanceur ignore le fichier (client arrêté)

Lecteur = Callable[[int, int], Awaitable[bytes]]


def lire(dossier: str | Path) -> dict | None:
    """`amis_combat.json` (None : absent, illisible ou d'un autre format)."""
    try:
        d = json.loads((Path(dossier) / NOM_FICHIER).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(d, dict) or d.get("format") != FORMAT:
        return None
    return d


def _ami(v: int) -> bool | None:
    return True if v == bp.AMI_OUI else False if v == bp.AMI_NON else None


class SuiviAmisCombat:
    """Recopie de la liste d'ennemis publiée par le jeu dans `amis_combat.json` (voir la docstring du module)."""

    def __init__(self, dossier: str | Path, horloge: Callable[[], float] = time.monotonic):
        self.fichier = Path(dossier) / NOM_FICHIER
        self.horloge = horloge
        self.ecritures = 0                                   # depuis le lancement (tests, diagnostic)
        self.lectures = 0                                    # paquets GDB lus (zone ApAmisCombat)
        self.rejets = 0                                      # lectures écartées (écriture du jeu en cours)
        self._vu: int | None = None                          # amis_numero dont la liste est dans le fichier
        self._ecrit: tuple | None = None                     # (publie, combat, numero, ennemis) écrit par CE client
        self._t = 0.0
        ancien = lire(self.fichier.parent) or {}
        if ancien.get("publie") or ancien.get("combat"):     # fichier laissé par un client tué : « aucune donnée »
            self._ecrire(False, False, 0, ())

    def _ecrire(self, publie: bool, combat: bool, numero: int, ennemis: tuple) -> bool:
        d = {"format": FORMAT, "horodatage": time.time(), "publie": bool(publie), "combat": bool(combat),
             "numero": int(numero),
             "ennemis": [{"param": p, "medaille": m, "ami": _ami(a), "emplacement": e} for p, m, a, e in ennemis]}
        tmp = self.fichier.with_name(self.fichier.name + ".tmp")
        try:
            self.fichier.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(json.dumps(d, separators=(",", ":")), encoding="utf-8")
            os.replace(tmp, self.fichier)
        except OSError:
            return False                                     # réessayé au prochain tour (rien n'est noté écrit)
        self._ecrit, self._t = (bool(publie), bool(combat), int(numero), tuple(ennemis)), self.horloge()
        self.ecritures += 1
        return True

    async def suivre(self, etat: int, amis_numero: int, lecteur: Lecteur) -> bool:
        """Un tour : `etat` et `amis_numero` de l'en-tête de CE tour ; `lecteur(adresse, taille)` : lecture GDB (jeu en
        marche). True si le fichier a été écrit."""
        if not etat & bp.ETAT_AMIS_COMBAT:
            return self.oublier()                            # patch qui ne publie pas la liste
        if not etat & bp.ETAT_EN_COMBAT:
            self._vu = None
            if self._ecrit is not None and self._ecrit[:2] == (True, False):
                return False
            return self._ecrire(True, False, amis_numero, ())   # hors combat : rien à lire
        if self._vu == amis_numero and self._ecrit is not None and self._ecrit[1]:
            if self.horloge() - self._t >= PERIODE_RAPPEL:
                return self._ecrire(*self._ecrit)            # rappel : même contenu, nouvel horodatage
            return False
        b = await lecteur(bp.ZONE + bp.OFF_AMIS_COMBAT, bp.TAILLE_AMIS_COMBAT)
        self.lectures += 1
        d = bp.lire_amis_combat(b)
        if not bp.amis_combat_accepte(d, amis_numero) or not d["en_combat"]:
            self.rejets += 1                                 # écriture en cours ou combat fini entre-temps : au
            return False                                     # tour suivant (l'en-tête aura changé)
        ennemis = tuple((e["param"], e["medaille"], e["ami"], e["emplacement"]) for e in d["ennemis"])
        if self._ecrire(True, True, amis_numero, ennemis):
            self._vu = amis_numero
            return True
        return False

    def oublier(self) -> bool:
        """Plus de données (jeu détaché ou déconnecté, patch sans la liste, arrêt) : « aucune donnée » une seule fois."""
        self._vu = None
        if self._ecrit is None or not (self._ecrit[0] or self._ecrit[1]):
            return False
        return self._ecrire(False, False, 0, ())
