"""Indices (hints) du slot pour le sous-onglet « Indices » de l'onglet « Discussion » du lanceur (à la manière de
l'onglet « Hints » du TextClient d'Archipelago).

Bibliothèque standard seulement : importé par le client (`synchro.py`, qui a la connexion websocket) et par le lanceur
(`lanceur/vue_indices.py`). **Aucune lecture ni écriture GDB**, aucune seconde connexion au serveur :

1. Source : le client lit une fois puis suit (Get + SetNotify, `ap_reseau.ClientAP._p_Connected`) la clé du data storage
   `_read_hints_{team}_{slot}` que le serveur 0.6.x tient à jour : TOUS les indices où le slot est le trouveur (un
   objet de quelqu'un est dans son monde) ou le destinataire (un de ses objets est chez quelqu'un), y compris les
   indices créés automatiquement (LocationScouts `create_as_hint`, boutiques), avec leur état (`found`, `status`).
2. `indices.json` (écrit par le CLIENT seulement, atomique, seulement s'il a changé : `ecrire_indices`) : noms déjà
   résolus (DataPackage), une ligne par indice (`construire_indices`).
3. Changement de priorité (UpdateHint, serveur 0.6) : le lanceur dépose une commande dans `chat_commandes.json`
   (`chat_local.deposer_commande(..., action=action_statut(...))`, même canal, mêmes règles : une fois, session du
   client, durée de vie) ; le client la valide (`valider_action`) et envoie le paquet. Le serveur n'accepte que les
   indices dont le slot est le DESTINATAIRE et pas encore trouvés, et jamais l'état « trouvé » (`modifiable`).

Anti-divulgâchage : rien d'autre que ce que le serveur donne lui-même au joueur (ses indices).
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Callable, Iterable

NOM_INDICES = "indices.json"
FORMAT = 1
INDICES_MAX = 5000                   # garde-fou (une partie normale en a quelques dizaines)

# HintStatus (Archipelago 0.6)
NON_PRECISE, SANS_PRIORITE, EVITER, PRIORITAIRE, TROUVE = 0, 10, 20, 30, 40
STATUTS = (NON_PRECISE, SANS_PRIORITE, EVITER, PRIORITAIRE, TROUVE)
STATUTS_CHOISIS = (PRIORITAIRE, NON_PRECISE, SANS_PRIORITE, EVITER)     # ceux que le joueur peut demander (menu)
# ordre d'affichage par défaut (comme le TextClient : priorité d'abord, trouvés en dernier)
RANG_STATUT = {PRIORITAIRE: 0, NON_PRECISE: 1, SANS_PRIORITE: 2, EVITER: 3, TROUVE: 4}


def _entier(v, defaut: int | None = None) -> int | None:
    if isinstance(v, bool):
        return int(v)
    try:
        return int(v)
    except (TypeError, ValueError):
        return defaut


def statut_de(h: dict) -> int:
    """État d'un indice : `status` (0.6) ; un serveur plus ancien n'a que `found`."""
    if h.get("found"):
        return TROUVE
    s = _entier(h.get("status"), NON_PRECISE)
    return s if s in STATUTS else NON_PRECISE


def construire_indices(indices: Iterable[dict], *, slot: int | None, team: int | None = None, graine: str = "",
                       joueur: str = "", connecte: bool = True,
                       nom_joueur: Callable[[int], str] = lambda s: f"Joueur {s}",
                       nom_objet: Callable[[int, int | None], str] = lambda i, s: f"Objet {i}",
                       nom_location: Callable[[int, int | None], str] = lambda l, s: f"Lieu {l}") -> dict:
    """Contenu de `indices.json` à partir des Hint du serveur (`receiving_player`, `finding_player`, `location`, `item`,
    `found`, `entrance`, `item_flags`, `status`). Les indices mal formés sont ignorés, les doublons (même trouveur et
    même location) fusionnés (le dernier gagne, comme le serveur qui remplace un indice)."""
    lignes: dict[tuple[int, int], dict] = {}
    for h in indices:
        if not isinstance(h, dict):
            continue
        dest, trouveur = _entier(h.get("receiving_player")), _entier(h.get("finding_player"))
        loc, item = _entier(h.get("location")), _entier(h.get("item"))
        if None in (dest, trouveur, loc, item):
            continue
        st = statut_de(h)
        lignes[(trouveur, loc)] = {
            "destinataire": nom_joueur(dest), "destinataire_slot": dest,
            "objet": nom_objet(item, dest), "item": item, "flags": _entier(h.get("item_flags"), 0) or 0,
            "trouveur": nom_joueur(trouveur), "trouveur_slot": trouveur,
            "lieu": nom_location(loc, trouveur), "location": loc,
            "entree": str(h.get("entrance") or "")[:200], "trouve": st == TROUVE, "statut": st,
        }
        if len(lignes) >= INDICES_MAX:
            break
    return {"format": FORMAT, "horodatage": round(time.time(), 3), "graine": str(graine or ""), "team": team,
            "slot": slot, "joueur": str(joueur or ""), "connecte": bool(connecte), "indices": list(lignes.values())}


def modifiable(ligne: dict, slot: int | None) -> bool:
    """Le serveur n'accepte UpdateHint que du DESTINATAIRE, et jamais pour un indice déjà trouvé."""
    return slot is not None and _entier(ligne.get("destinataire_slot")) == slot and not ligne.get("trouve") \
        and _entier(ligne.get("statut")) != TROUVE


# ------------------------------------------------------------------------------------------------ fichier
def _sans_date(d: dict) -> str:
    return json.dumps({k: v for k, v in d.items() if k != "horodatage"}, ensure_ascii=False, sort_keys=True)


def ecrire_indices(dossier: str | Path, d: dict, precedent: str | None = None) -> str | None:
    """Écrit `indices.json` (atomique) s'il a changé depuis `precedent` (empreinte de l'appel précédent) ; renvoie la
    nouvelle empreinte, ou `precedent` si rien n'a changé (aucune écriture « pour rien »)."""
    empreinte = _sans_date(d)
    if empreinte == precedent:
        return precedent
    p = Path(dossier) / NOM_INDICES
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, p)
    return empreinte


def lire_indices(dossier: str | Path) -> dict | None:
    try:
        d = json.loads((Path(dossier) / NOM_INDICES).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(d, dict) or not isinstance(d.get("indices"), list):
        return None
    d["indices"] = [h for h in d["indices"] if isinstance(h, dict)]
    return d


# ------------------------------------------------------------------------------------------------ actions
def action_statut(trouveur_slot: int, location: int, statut: int) -> dict:
    """Action « changer la priorité d'un indice » déposée par le lanceur (paquet UpdateHint : `player` = slot dans le
    monde duquel est la location, c'est-à-dire le TROUVEUR)."""
    return {"cmd": "UpdateHint", "player": int(trouveur_slot), "location": int(location), "status": int(statut)}


def valider_action(a) -> dict | None:
    """Action reçue du lanceur -> paquet sûr à envoyer, ou None (inconnue, mal formée, état interdit)."""
    if not isinstance(a, dict) or a.get("cmd") != "UpdateHint":
        return None
    joueur, loc, st = _entier(a.get("player")), _entier(a.get("location")), _entier(a.get("status"))
    if joueur is None or loc is None or st not in STATUTS_CHOISIS or joueur < 0:
        return None
    return action_statut(joueur, loc, st)
