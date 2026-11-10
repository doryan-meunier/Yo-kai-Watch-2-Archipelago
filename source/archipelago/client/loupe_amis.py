"""Point de loupe visé par le radar et « déjà ami » pour la fenêtre de la loupe du lanceur : fichier local `loupe.json`.

Le jeu (patch `YKW2_AP`, `src/archipelago/loupe.cpp`) publie sur le terrain le point de loupe que vise le RADAR de la
montre et ce qu'il contient à cet instant (base montrée par la loupe ; pour chaque rencontre que la loupe peut lancer
depuis ce point, le 1er combattant après le mélange, son n° du Médaillium, « déjà ami » et son poids sur 100) dans la
zone `ApLoupe` (0x40 octets) et, dans l'EN-TÊTE que le client lit déjà à chaque tour, deux bits d'`etat` et un numéro
(`loupe_numero`, 0xFC) qui change avec le contenu (`docs/systemes/archipelago_boite.md` §54,
`docs/systemes/archipelago_loupe_amis.md`). Ce module :
- ne lit RIEN quand le radar ne vise aucun point (bit ETAT_LOUPE_CIBLE absent) ni quand le numéro n'a pas changé : un
  paquet GDB par changement de point visé ou de contenu ;
- recopie le contenu dans `<dossier>/loupe.json`, lu par le lanceur (`lanceur/fenetre_loupe.py`).

Un seul écrivain (le client), écriture atomique. Rappel du même contenu toutes les `PERIODE_RAPPEL` secondes tant que le
radar vise un point (le lanceur ignore un fichier de plus de `AGE_MAX` secondes : client tué). « Aucune donnée » une
fois quand le jeu est détaché, déconnecté, que le patch ne publie pas la loupe, ou à l'arrêt.

Contenu : `{"format": 1, "horodatage": time.time(), "publie": bool, "cible": bool, "numero": n, "point": n,
"identifiant": n, "base": hachage CHARA_BASE, "genre": 0 (point tiré) | 1 (base fixe), "autres": n,
"especes": [{"param": hachage CHARA_PARAM, "medaille": n° (0 : aucun), "ami": true | false | null, "poids": n}]}`.
Aucun texte du jeu : le lanceur résout les espèces en noms par la base locale générée chez le joueur
(`yokai_local.json`).
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

NOM_FICHIER = "loupe.json"
FORMAT = 1
PERIODE_RAPPEL = 10.0         # s : rappel du même contenu tant que le radar vise un point (nouvel horodatage)
AGE_MAX = 30.0                # s : au-delà, le lanceur ignore le fichier (client arrêté)

Lecteur = Callable[[int, int], Awaitable[bytes]]

_VIDE = {"point": 0, "identifiant": 0, "base": 0, "genre": 0, "autres": 0}


def lire(dossier: str | Path) -> dict | None:
    """`loupe.json` (None : absent, illisible ou d'un autre format)."""
    try:
        d = json.loads((Path(dossier) / NOM_FICHIER).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(d, dict) or d.get("format") != FORMAT:
        return None
    return d


def _ami(v: int) -> bool | None:
    return True if v == bp.AMI_OUI else False if v == bp.AMI_NON else None


class SuiviLoupe:
    """Recopie du point visé par le radar publié par le jeu dans `loupe.json` (voir la docstring du module)."""

    def __init__(self, dossier: str | Path, horloge: Callable[[], float] = time.monotonic):
        self.fichier = Path(dossier) / NOM_FICHIER
        self.horloge = horloge
        self.ecritures = 0                                   # depuis le lancement (tests, diagnostic)
        self.lectures = 0                                    # paquets GDB lus (zone ApLoupe)
        self.rejets = 0                                      # lectures écartées (écriture du jeu en cours, cible perdue)
        self._vu: int | None = None                          # loupe_numero dont le contenu est dans le fichier
        self._ecrit: tuple | None = None                     # (publie, cible, numero, champs, especes) écrit par CE client
        self._t = 0.0
        ancien = lire(self.fichier.parent) or {}
        if ancien.get("publie") or ancien.get("cible"):     # fichier laissé par un client tué : « aucune donnée »
            self._ecrire(False, False, 0, (), ())

    def _ecrire(self, publie: bool, cible: bool, numero: int, champs: tuple, especes: tuple) -> bool:
        d = {"format": FORMAT, "horodatage": time.time(), "publie": bool(publie), "cible": bool(cible),
             "numero": int(numero), **_VIDE, **dict(champs),
             "especes": [{"param": p, "medaille": m, "ami": _ami(a), "poids": w} for p, m, a, w in especes]}
        tmp = self.fichier.with_name(self.fichier.name + ".tmp")
        try:
            self.fichier.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(json.dumps(d, separators=(",", ":")), encoding="utf-8")
            os.replace(tmp, self.fichier)
        except OSError:
            return False                                     # réessayé au prochain tour (rien n'est noté écrit)
        self._ecrit = (bool(publie), bool(cible), int(numero), tuple(champs), tuple(especes))
        self._t = self.horloge()
        self.ecritures += 1
        return True

    async def suivre(self, etat: int, loupe_numero: int, lecteur: Lecteur) -> bool:
        """Un tour : `etat` et `loupe_numero` de l'en-tête de CE tour ; `lecteur(adresse, taille)` : lecture GDB (jeu en
        marche). True si le fichier a été écrit."""
        if not etat & bp.ETAT_LOUPE:
            return self.oublier()                            # patch qui ne publie pas la loupe
        if not etat & bp.ETAT_LOUPE_CIBLE:
            self._vu = None
            if self._ecrit is not None and self._ecrit[:2] == (True, False):
                return False
            return self._ecrire(True, False, loupe_numero, (), ())   # aucun point visé : rien à lire
        if self._vu == loupe_numero and self._ecrit is not None and self._ecrit[1]:
            if self.horloge() - self._t >= PERIODE_RAPPEL:
                return self._ecrire(*self._ecrit)            # rappel : même contenu, nouvel horodatage
            return False
        b = await lecteur(bp.ZONE + bp.OFF_LOUPE, bp.TAILLE_LOUPE)
        self.lectures += 1
        d = bp.lire_loupe(b)
        if not bp.loupe_accepte(d, loupe_numero) or not d["cible"]:
            self.rejets += 1                                 # écriture en cours ou cible perdue entre-temps : au
            return False                                     # tour suivant (l'en-tête aura changé)
        champs = tuple((k, d[k]) for k in ("point", "identifiant", "base", "genre", "autres"))
        especes = tuple((e["param"], e["medaille"], e["ami"], e["poids"]) for e in d["especes"])
        if self._ecrire(True, True, loupe_numero, champs, especes):
            self._vu = loupe_numero
            return True
        return False

    def oublier(self) -> bool:
        """Plus de données (jeu détaché ou déconnecté, patch sans la loupe, arrêt) : « aucune donnée » une seule fois."""
        self._vu = None
        if self._ecrit is None or not (self._ecrit[0] or self._ecrit[1]):
            return False
        return self._ecrire(False, False, 0, (), ())
