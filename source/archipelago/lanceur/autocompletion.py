"""Autocomplétion de la console (onglet « Discussion »), SANS affichage : commandes du serveur à partir de « ! », noms
d'objets après `!hint`, noms de lieux après `!hint_location`, du seul jeu du slot : le serveur (MultiServer 0.6.7,
`get_hints`) ne répond pas pour un autre jeu, et le client de base ne propose rien d'autre.

Noms : `chat_noms.json`, écrit par le client (`client/chat_local.py`, DataPackage déjà reçu), lu ici seulement quand on
tape une commande qui en a besoin, et relu seulement si sa date ou sa taille a changé (`Catalogue.actualiser`).

Le texte complet du champ est la requête : tout message qui ne commence pas par « ! » ne propose rien.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

from .tracker import replier

_CLIENT = Path(__file__).resolve().parents[1] / "client"
if str(_CLIENT) not in sys.path:
    sys.path.insert(0, str(_CLIENT))
import chat_local as ch  # noqa: E402  (client/, distribué avec le lanceur)

LIGNES = 8                                  # propositions montrées
# commandes de joueur de MultiServer 0.6.7 (clients) ; vrai : elle attend un argument (une espace suit la complétion)
# (dans l'ordre des propositions : les plus utiles d'abord)
COMMANDES = {"!hint": True, "!hint_location": True, "!remaining": False, "!missing": False, "!checked": False,
             "!status": False, "!players": False, "!help": False, "!release": False, "!collect": False, "!alias": True,
             "!countdown": True, "!getitem": True, "!license": False, "!admin": True}
SOURCES = {"!hint": "objets", "!hint_location": "lieux"}   # commande -> noms proposés après elle


@dataclass(frozen=True)
class Proposition:
    nom: str                                # ce qui est montré
    complet: str                            # texte du champ après complétion
    exact: bool = False                     # déjà tapé en entier


@dataclass(frozen=True)
class Liste:
    entrees: tuple[Proposition, ...]
    total: int                              # correspondances, montrées ou non
    choix: int | None                       # ligne choisie d'avance (rien sans caractère tapé : Entrée envoie)


@dataclass
class Catalogue:
    """Noms prêts à filtrer : listes de (nom replié, nom), par ordre alphabétique."""
    objets: list[tuple[str, str]] = field(default_factory=list)
    lieux: list[tuple[str, str]] = field(default_factory=list)
    signature: tuple | None = None

    @classmethod
    def depuis(cls, d: dict | None, signature: tuple | None = None) -> "Catalogue":
        if not isinstance(d, dict):
            return cls(signature=signature)
        return cls(_preparer(d.get("objets")), _preparer(d.get("lieux")), signature)

    def actualiser(self, dossier: Path) -> "Catalogue":
        """Le même catalogue si `chat_noms.json` n'a pas changé (un seul stat), sinon le nouveau."""
        try:
            st = (Path(dossier) / ch.NOM_NOMS).stat()
            signature = (st.st_mtime_ns, st.st_size)
        except OSError:
            signature = None
        if signature == self.signature:
            return self
        return Catalogue.depuis(ch.lire_noms(dossier) if signature else None, signature)


_PLI_ASCII = {i: (chr(i).lower() if chr(i).isalnum() else " ") for i in range(128)}


def plier(nom: str) -> str:
    """`replier`, en voie rapide pour un nom ASCII."""
    return " ".join(nom.translate(_PLI_ASCII).split()) if nom.isascii() else replier(nom)


def _preparer(noms) -> list[tuple[str, str]]:
    if not isinstance(noms, list):
        return []
    return sorted((plier(n), n) for n in set(noms) if isinstance(n, str))


def filtrer(entrees: list[tuple[str, str]], requete: str) -> tuple[list[tuple[str, str]], int]:
    """(correspondances, nombre), recherche sans casse ni accents : le début du nom avant l'intérieur, l'ordre de
    `entrees` gardé ensuite."""
    q = replier(requete)
    if not q:
        return list(entrees), len(entrees)
    trouves = [e for e in entrees if q in e[0]]
    return sorted(trouves, key=lambda e: not e[0].startswith(q)), len(trouves)


def _commandes(texte: str, limite: int) -> Liste | None:
    q = texte.lower()
    trouves = sorted((c for c in COMMANDES if q[1:] in c), key=lambda c: not c.startswith(q))
    if not trouves or trouves == [q] and not COMMANDES[q]:
        return None
    return Liste(tuple(Proposition(c, c + " " if COMMANDES[c] else c, c == q) for c in trouves[:limite]),
                 len(trouves), 0 if len(q) > 1 else None)


def proposer(texte: str, cat: Catalogue, limite: int = LIGNES) -> Liste | None:
    """Liste pour le texte du champ, ou None : rien à proposer (la saisie reste libre)."""
    if not texte.startswith("!"):
        return None
    commande, espace, reste = texte.partition(" ")
    if not espace:
        return _commandes(texte, limite)
    source = SOURCES.get(commande.lower())
    if source is None:
        return None
    reste = reste.lstrip()
    base = texte[:len(texte) - len(reste)]
    trouves, total = filtrer(getattr(cat, source), reste)
    if not trouves or (total == 1 and trouves[0][1].casefold() == reste.casefold()):
        return None
    pr = tuple(Proposition(n, base + n, n.casefold() == reste.casefold()) for _p, n in trouves[:limite])
    return Liste(pr, total, 0 if replier(reste) else None)
