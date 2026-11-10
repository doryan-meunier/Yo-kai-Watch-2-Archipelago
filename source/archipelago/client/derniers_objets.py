"""Derniers objets reçus et envoyés par CE joueur, pour la fenêtre du lanceur : fichier local `derniers_objets.json`.

Bibliothèque standard seulement, sans asyncio ni tkinter : importé par le client (`synchro.py`) et par le lanceur
(`lanceur/fenetre_derniers_objets.py`). **Aucune lecture ni écriture GDB, rien de nouveau demandé au serveur** :
la source est le PrintJSON que le serveur envoie déjà à chaque objet trouvé (type `ItemSend`, `ItemCheat` pour un
objet donné par la console du serveur), celui que l'onglet « Discussion » affiche (`chat_local.py`). Il porte
`receiving` (slot qui reçoit) et `item` = {item, location, player (slot qui a trouvé), flags} : un objet n'est gardé
que s'il concerne ce slot (`evenement_printjson`) :
- reçu : `receiving` = soi et `player` ≠ soi (objet trouvé par un autre joueur, ou donné par le serveur) ;
- envoyé : `player` = soi et `receiving` ≠ soi (objet de ce monde parti chez un autre joueur) ;
- trouvé : les deux = soi (objet de ce monde pour soi-même).
Les échanges entre deux autres joueurs, que le serveur diffuse aussi, sont écartés. Le serveur n'envoie ces messages
qu'au moment où l'objet est trouvé : rien n'est rejoué à la reconnexion (ReceivedItems, lui, rejoue tout), donc pas
d'avalanche de vieux objets à chaque démarrage du client.

`derniers_objets.json` (écrit par le CLIENT seulement, écriture atomique, un écrit par évènement retenu) :
{format: 1, horodatage, session, evenements: [{n, t, sens: "recu" | "envoye" | "trouve", objet, flags, joueur,
serveur, lieu, jeu}]} ; les `GARDER` plus récents seulement, `n` croissant (repris du fichier au démarrage), `t` =
time.time() de la réception. Noms (objet, joueur, lieu) résolus par le client avec le DataPackage du serveur ; `joueur`
= l'autre joueur (expéditeur d'un objet reçu, destinataire d'un objet envoyé ; null pour « trouvé » et pour un don de
la console : `serveur` vrai) ; `flags` = NetworkItem.flags (1 progression, 2 utile, 4 piège) ; `jeu` = le jeu était
attaché au client à ce moment (la fenêtre ne montre que ceux-là : elle est faite pour être au-dessus du jeu).
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Callable

NOM_FICHIER = "derniers_objets.json"
FORMAT = 1
GARDER = 20                    # évènements gardés dans le fichier (la fenêtre en montre 5 au plus)
TYPES = ("ItemSend", "ItemCheat")
SENS = ("recu", "envoye", "trouve")
MIN_INTERVALLE = 0.25          # s entre deux écritures : une avalanche (`!release`) est regroupée en une écriture
TEXTE_MAX = 120                # caractères gardés par texte (borne de taille du fichier)
ESSAIS = 3                     # écriture refusée (le lanceur lit le fichier au même instant, Windows) : réessayée
PAUSE_ESSAI = 0.02             # s entre deux essais


def _entier(v) -> int | None:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def evenement_printjson(p: dict, slot: int | None, *,
                        nom_joueur: Callable[[int], str] = lambda s: f"Joueur {s}",
                        nom_objet: Callable[[int, int | None], str] = lambda i, s: f"Objet {i}",
                        nom_location: Callable[[int, int | None], str] = lambda l, s: f"Lieu {l}") -> dict | None:
    """Évènement {sens, objet, flags, joueur, serveur, lieu} d'un PrintJSON qui concerne le slot `slot` ; None pour
    tout autre message (discussion, indice, échange entre deux autres joueurs, paquet incomplet)."""
    if not isinstance(p, dict) or p.get("type") not in TYPES or slot is None:
        return None
    it = p.get("item")
    if not isinstance(it, dict):
        return None
    recoit, trouve, item = _entier(p.get("receiving")), _entier(it.get("player")), _entier(it.get("item"))
    if recoit is None or trouve is None or item is None:
        return None
    if recoit == slot and trouve == slot:
        sens, autre = "trouve", None
    elif recoit == slot:
        sens, autre = "recu", trouve
    elif trouve == slot:
        sens, autre = "envoye", recoit
    else:
        return None                                       # entre deux autres joueurs : pas pour cette fenêtre
    # console du serveur : `!getitem` envoie ItemCheat avec NetworkItem(objet, -1, slot qui reçoit) (MultiServer
    # 0.6.7, `_cmd_getitem` : `player` = le destinataire, pas un expéditeur) ; autre == 0 : cas d'un serveur qui
    # nommerait le slot 0 comme expéditeur
    cheat = p.get("type") == "ItemCheat"
    serveur = cheat or autre == 0
    if serveur:
        sens, autre = "recu", None
    loc = _entier(it.get("location"))
    lieu = nom_location(loc, trouve) if loc is not None and loc > 0 and not serveur else ""
    return {"sens": sens, "objet": str(nom_objet(item, recoit)), "flags": _entier(it.get("flags")) or 0,
            "joueur": None if autre is None or serveur else str(nom_joueur(autre)), "serveur": serveur,
            "lieu": str(lieu)}


def lire(dossier: str | Path) -> dict | None:
    """`derniers_objets.json` (None : absent, illisible ou d'un autre format)."""
    try:
        d = json.loads((Path(dossier) / NOM_FICHIER).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(d, dict) or d.get("format") != FORMAT or not isinstance(d.get("evenements"), list):
        return None
    return d


class JournalDerniersObjets:
    """Écrivain unique de `derniers_objets.json` (le client). Les erreurs d'écriture sont ignorées après `ESSAIS`
    essais (la fenêtre n'est qu'un confort : elle ne doit jamais arrêter le client) ; l'évènement reste en mémoire et
    part avec l'écriture suivante."""

    def __init__(self, dossier: str | Path, session: str = "", garder: int = GARDER,
                 horloge: Callable[[], float] = time.time,
                 planifier: Callable[[float, Callable[[], None]], object] | None = None,
                 mono: Callable[[], float] = time.monotonic):
        self.fichier = Path(dossier) / NOM_FICHIER
        self.session, self.garder, self.horloge = str(session or ""), garder, horloge
        ancien = lire(self.fichier.parent) or {}
        self.evenements: list[dict] = [e for e in ancien.get("evenements", []) if isinstance(e, dict)
                                       and isinstance(e.get("n"), int)][-garder:]
        self.n = max((e["n"] for e in self.evenements), default=0)
        self.ecritures = 0
        self.echecs = 0
        # regroupement : `planifier(delai, fonction)` (client : loop.call_later) ; absent, chaque évènement est écrit
        self.planifier, self.mono = planifier, mono
        self._derniere = float("-inf")
        self._en_attente = False

    def ajouter(self, ev: dict, jeu: bool) -> dict:
        """Ajoute un évènement de `evenement_printjson` et réécrit le fichier. Renvoie l'entrée écrite."""
        self.n += 1
        joueur = ev.get("joueur")
        e = {"n": self.n, "t": round(self.horloge(), 3), "sens": ev["sens"], "objet": str(ev["objet"])[:TEXTE_MAX],
             "flags": int(ev.get("flags") or 0), "joueur": None if joueur is None else str(joueur)[:TEXTE_MAX],
             "serveur": bool(ev.get("serveur")), "lieu": str(ev.get("lieu") or "")[:TEXTE_MAX], "jeu": bool(jeu)}
        self.evenements = (self.evenements + [e])[-self.garder:]
        reste = self._derniere + MIN_INTERVALLE - self.mono()
        if self.planifier is None or reste <= 0:
            self.ecrire()
        elif not self._en_attente:                          # avalanche : une seule écriture à la fin de l'intervalle
            try:
                self.planifier(reste, self.vider)
                self._en_attente = True
            except Exception:                                # noqa: BLE001  (pas de boucle d'évènements : écrire)
                self.ecrire()
        return e

    def vider(self) -> None:
        """Écrit ce qui attend (fin de l'intervalle de regroupement, ou arrêt du client)."""
        if self._en_attente:
            self._en_attente = False
            self.ecrire()

    def ecrire(self) -> bool:
        self._derniere = self.mono()
        d = {"format": FORMAT, "horodatage": round(self.horloge(), 3), "session": self.session,
             "evenements": self.evenements}
        brut = json.dumps(d, ensure_ascii=False, separators=(",", ":"))
        tmp = self.fichier.with_name(self.fichier.name + ".tmp")
        for essai in range(ESSAIS):
            try:
                self.fichier.parent.mkdir(parents=True, exist_ok=True)
                tmp.write_text(brut, encoding="utf-8")
                os.replace(tmp, self.fichier)
                self.ecritures += 1
                return True
            except OSError:
                if essai + 1 < ESSAIS:
                    time.sleep(PAUSE_ESSAI)
        self.echecs += 1
        return False
