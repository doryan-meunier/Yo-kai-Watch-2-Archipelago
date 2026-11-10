"""Discussion du serveur Archipelago pour l'onglet « Discussion » du lanceur (à la manière du TextClient d'Archipelago).

Bibliothèque standard seulement, sans asyncio ni tkinter : importé par le client (`synchro.py`, qui a la connexion
websocket) et par le lanceur (`lanceur/vue_texte.py`). **Aucune lecture ni écriture GDB** : tout passe par deux
fichiers locaux du dossier du client (`%APPDATA%/ykw2-ap/`), chacun avec un seul écrivain.

1. `messages.jsonl` (écrit par le CLIENT seulement, ajout en fin de fichier) : une ligne JSON par message
   {n, session, t, type, parties | cle + params, commande?}. `n` croît d'une ligne à l'autre (repris du fichier au
   démarrage du client) ; `session` = identifiant aléatoire du client en cours ; `type` = type du PrintJSON
   (ItemSend, Hint, Chat, Join, Goal, Release, Collect, CommandResult…) ou « systeme » (connexion, déconnexion,
   refus, commande envoyée / non envoyée : `cle` + `params`, traduits par le lanceur). `parties` = [{x: texte,
   g: genre}] : les identifiants (joueur, objet, lieu) sont déjà résolus en noms par le client (DataPackage) ; le genre
   donne la couleur (`genre_objet`, `GENRES`). Journal BORNÉ : au-delà de `TAILLE_MAX` octets, il devient
   `messages.1.jsonl` (l'ancien est remplacé) et un nouveau commence ; le lanceur lit les deux.
2. `chat_commandes.json` (écrit par le LANCEUR seulement, relire-modifier-écrire sous le verrou `chat_commandes.verrou`)
   : {format, fichier, commandes: [{rev, id, session, texte, horodatage}]}. `rev` = révision du disque + 1,
   `id` aléatoire, `session` = session du client visé (lue dans `etat.json`, `session_chat`), `fichier` = identifiant
   du fichier (nouveau s'il est recréé). Le client n'exécute qu'une commande de SA session, jamais vue (`id`), de
   révision plus grande que la dernière exécutée pour ce fichier et de moins de `DUREE_VIE` s : aucune commande
   n'est envoyée deux fois, ni après un redémarrage du client (nouvelle session : les anciennes sont ignorées). Les
   `COMMANDES_MAX` plus récentes seulement sont gardées. Une commande peut porter une `action` (dict) au lieu d'un
   message : paquet autre que Say (changement de priorité d'un indice, `indices_local.action_statut`) ; le client la
   valide lui-même (`indices_local.valider_action`) et `texte` n'en est que la description.

3. `chat_noms.json` (écrit par le CLIENT seulement, une fois par connexion quand son contenu change) : noms que
   propose l'autocomplétion de la console : {format, jeu, objets: [noms], lieux: [noms]}, pour le SEUL jeu du slot
   (le serveur ne répond à `!hint` et `!hint_location` que pour lui), tirés du DataPackage que le client a déjà (rien
   de plus n'est demandé au serveur, aucun paquet GDB). Le lanceur ne le lit que quand on tape une commande qui en a
   besoin (`lanceur/autocompletion.py`).

Anti-divulgâchage : rien d'autre que ce que le serveur envoie lui-même (PrintJSON, dont les indices demandés par le
joueur) ; aucun LocationScouts affiché ; `chat_noms.json` donne tous les noms du jeu, sans lien avec ce que contient
une location.
"""
from __future__ import annotations

import json
import os
import secrets
import time
from pathlib import Path
from typing import Callable, Iterable

try:
    from .config_locale import VerrouConfig
except ImportError:                                          # pragma: no cover - selon le mode d'import
    from config_locale import VerrouConfig                  # type: ignore[no-redef]

NOM_MESSAGES = "messages.jsonl"
NOM_MESSAGES_ANCIEN = "messages.1.jsonl"
NOM_COMMANDES = "chat_commandes.json"
NOM_VERROU = "chat_commandes.verrou"
NOM_NOMS = "chat_noms.json"
FORMAT_NOMS = 1
FORMAT = 1
TAILLE_MAX = 256 * 1024          # octets de messages.jsonl avant rotation (≈ 1000 à 2000 messages)
COMMANDES_MAX = 32               # commandes gardées dans chat_commandes.json
DUREE_VIE = 120.0                # s : une commande plus vieille n'est plus envoyée
TEXTE_MAX = 1000                 # caractères d'un message saisi
PARTIES_MAX = 200                # parties d'un PrintJSON gardées (message anormalement long : tronqué)

# NetworkItem.flags (mêmes valeurs que ap_reseau)
PROGRESSION, UTILE, PIEGE = 0b001, 0b010, 0b100
# HintStatus (Archipelago 0.6) : non précisé, sans priorité, à éviter, prioritaire, trouvé
INDICE_NON_PRECISE, INDICE_SANS_PRIORITE, INDICE_EVITER, INDICE_PRIORITAIRE, INDICE_TROUVE = 0, 10, 20, 30, 40
GENRES_INDICE = {INDICE_TROUVE: "indice_trouve", INDICE_PRIORITAIRE: "indice_prioritaire",
                 INDICE_EVITER: "indice_eviter", INDICE_SANS_PRIORITE: "indice_sans_priorite",
                 INDICE_NON_PRECISE: "indice_non_trouve"}
# genres d'une partie de message (couleur choisie par le lanceur)
GENRES = ("texte", "moi", "joueur", "objet_progression", "objet_utile", "objet_piege", "objet", "lieu", "entree",
          "indice_trouve", "indice_non_trouve", "indice_prioritaire", "indice_eviter", "indice_sans_priorite",
          "gras", "rouge", "vert", "jaune", "bleu", "magenta", "cyan", "blanc", "noir", "violet", "orange")
COULEURS_JSON = {"red": "rouge", "green": "vert", "yellow": "jaune", "blue": "bleu", "magenta": "magenta",
                 "cyan": "cyan", "white": "blanc", "black": "noir", "plum": "objet_progression",
                 "slateblue": "objet_utile", "salmon": "objet_piege", "orange": "orange", "bold": "gras",
                 "purple": "violet"}


def genre_objet(flags: int) -> str:
    """Couleur d'un objet selon ses drapeaux, comme le TextClient : progression, utile, piège, sinon remplissage."""
    flags = int(flags or 0)
    if flags & PROGRESSION:
        return "objet_progression"
    if flags & UTILE:
        return "objet_utile"
    if flags & PIEGE:
        return "objet_piege"
    return "objet"


def _entier(v, defaut: int | None = None) -> int | None:
    try:
        return int(v)
    except (TypeError, ValueError):
        return defaut


def parties_printjson(paquet: dict, *, slot_soi: int | None, nom_soi: str = "",
                      nom_joueur: Callable[[int], str] = lambda s: f"Joueur {s}",
                      nom_objet: Callable[[int, int | None], str] = lambda i, s: f"Objet {i}",
                      nom_location: Callable[[int, int | None], str] = lambda l, s: f"Lieu {l}") -> list[dict]:
    """Parties colorées d'un PrintJSON : [{x, g}]. Identifiants résolus en noms ; parties voisines de même genre fusionnées.
    `nom_objet(item, joueur qui le reçoit)`, `nom_location(location, joueur dans le monde duquel elle est)`."""
    out: list[dict] = []
    for part in list(paquet.get("data") or [])[:PARTIES_MAX]:
        if not isinstance(part, dict):
            continue
        t = part.get("type") or "text"
        x = str(part.get("text", ""))
        g = "texte"
        joueur = _entier(part.get("player"))
        if t == "player_id":
            s = _entier(x)
            if s is not None:
                x = nom_joueur(s)
                g = "moi" if slot_soi is not None and s == slot_soi else "joueur"
        elif t == "player_name":
            g = "moi" if nom_soi and x == nom_soi else "joueur"
        elif t in ("item_id", "item_name"):
            if t == "item_id":
                i = _entier(x)
                if i is not None:
                    x = nom_objet(i, joueur)
            g = genre_objet(_entier(part.get("flags"), 0) or 0)
        elif t in ("location_id", "location_name"):
            if t == "location_id":
                l = _entier(x)
                if l is not None:
                    x = nom_location(l, joueur)
            g = "lieu"
        elif t == "entrance_name":
            g = "entree"
        elif t == "hint_status":
            g = GENRES_INDICE.get(_entier(part.get("hint_status"), 0), "indice_non_trouve")
        elif t == "color":
            couleurs = [c for c in str(part.get("color", "")).split(";") if c]
            g = next((COULEURS_JSON[c.split("_")[0]] for c in couleurs if c.split("_")[0] in COULEURS_JSON), "texte")
        if not x:
            continue
        if out and out[-1]["g"] == g:
            out[-1]["x"] += x
        else:
            out.append({"x": x, "g": g})
    return out


def texte_parties(parties: Iterable[dict]) -> str:
    return "".join(str(p.get("x", "")) for p in parties if isinstance(p, dict))


def _lire_lignes(p: Path) -> list[dict]:
    try:
        brut = p.read_bytes()
    except OSError:
        return []
    out = []
    for ligne in brut.split(b"\n"):
        if not ligne.strip():
            continue
        try:
            d = json.loads(ligne.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            continue
        if isinstance(d, dict) and isinstance(d.get("n"), int):
            out.append(d)
    return out


# ------------------------------------------------------------------------------------------------ journal (client)
class JournalMessages:
    """Écrivain unique de `messages.jsonl` (le client). Ajout en fin de fichier, rotation au-delà de `taille_max`.
    Les erreurs d'écriture sont ignorées (le journal ne doit jamais arrêter le client)."""

    def __init__(self, dossier: str | Path, session: str | None = None, taille_max: int = TAILLE_MAX):
        self.dossier = Path(dossier)
        self.fichier = self.dossier / NOM_MESSAGES
        self.ancien = self.dossier / NOM_MESSAGES_ANCIEN
        self.session = session or secrets.token_hex(8)
        self.taille_max = taille_max
        self.n = 0
        for f in (self.fichier, self.ancien):              # numérotation reprise du journal existant
            lignes = _lire_lignes(f)
            if lignes:
                self.n = max(d["n"] for d in lignes)
                break
        self.ecrits = 0
        self.rotations = 0

    def ajouter(self, type_: str, parties: list[dict] | None = None, *, cle: str | None = None,
                params: dict | None = None, commande: str | None = None) -> dict | None:
        self.n += 1
        d: dict = {"n": self.n, "session": self.session, "t": round(time.time(), 3), "type": str(type_ or "")}
        if parties is not None:
            d["parties"] = parties
        if cle:
            d["cle"] = cle
            d["params"] = params or {}
        if commande:
            d["commande"] = commande
        ligne = (json.dumps(d, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
        try:
            self.dossier.mkdir(parents=True, exist_ok=True)
            try:
                taille = self.fichier.stat().st_size
            except OSError:
                taille = 0
            if taille and taille + len(ligne) > self.taille_max:
                try:
                    os.replace(self.fichier, self.ancien)     # le lanceur lisait peut-être : réessayé au suivant
                    self.rotations += 1
                except OSError:
                    pass
            with open(self.fichier, "ab") as f:
                f.write(ligne)
            self.ecrits += 1
        except OSError:
            return None
        return d

    def systeme(self, cle: str, commande: str | None = None, **params) -> dict | None:
        return self.ajouter("systeme", cle=cle, params=params, commande=commande)


# ------------------------------------------------------------------------------------------------ lecture (lanceur)
class LecteurMessages:
    """Lecture incrémentale de `messages.jsonl` (+ `messages.1.jsonl` au premier passage et après une rotation).
    `lire()` -> (nouveaux messages, `remis_a_zero` : journal recréé, l'affichage doit repartir de zéro)."""

    def __init__(self, dossier: str | Path, garder: int = 2000):
        self.dossier = Path(dossier)
        self.fichier = self.dossier / NOM_MESSAGES
        self.ancien = self.dossier / NOM_MESSAGES_ANCIEN
        self.garder = garder
        self.offset = 0
        self.tete = b""                       # première ligne du fichier lu (détecte une rotation)
        self.dernier_n = 0
        self.premiere = True

    def _tout(self) -> list[dict]:
        vus: dict[int, dict] = {}
        for f in (self.ancien, self.fichier):
            for d in _lire_lignes(f):
                vus[d["n"]] = d
        return [vus[n] for n in sorted(vus)]

    def _positionner(self) -> None:
        try:
            brut = self.fichier.read_bytes()
        except OSError:
            self.offset, self.tete = 0, b""
            return
        fin = brut.rfind(b"\n") + 1
        self.offset = fin
        self.tete = brut[:brut.find(b"\n") + 1] if fin else b""

    def lire(self) -> tuple[list[dict], bool]:
        if self.premiere:
            self.premiere = False
            tout = self._tout()
            self._positionner()
            if tout:
                self.dernier_n = tout[-1]["n"]
            return tout[-self.garder:], False
        try:
            taille = self.fichier.stat().st_size
        except OSError:
            if self.offset:                   # fichier disparu (rotation en cours, effacé) : relu au prochain passage
                self.offset, self.tete = 0, b""
            return [], False
        rotation = taille < self.offset
        if not rotation and self.tete:
            try:
                with open(self.fichier, "rb") as f:
                    rotation = f.read(len(self.tete)) != self.tete
            except OSError:
                return [], False
        if rotation or (self.offset == 0 and taille):
            tout = self._tout()
            self._positionner()
            if tout and tout[-1]["n"] < self.dernier_n:         # journal recréé (numérotation repartie de 1)
                self.dernier_n = tout[-1]["n"]
                return tout[-self.garder:], True
            nouveaux = [d for d in tout if d["n"] > self.dernier_n]
            if nouveaux:
                self.dernier_n = nouveaux[-1]["n"]
            return nouveaux[-self.garder:], False
        if taille == self.offset:
            return [], False
        try:
            with open(self.fichier, "rb") as f:
                f.seek(self.offset)
                brut = f.read(taille - self.offset)
        except OSError:
            return [], False
        fin = brut.rfind(b"\n") + 1                             # ligne en cours d'écriture : lue au prochain passage
        if not fin:
            return [], False
        self.offset += fin
        nouveaux = []
        for ligne in brut[:fin].split(b"\n"):
            if not ligne.strip():
                continue
            try:
                d = json.loads(ligne.decode("utf-8"))
            except (UnicodeDecodeError, ValueError):
                continue
            if isinstance(d, dict) and isinstance(d.get("n"), int) and d["n"] > self.dernier_n:
                nouveaux.append(d)
                self.dernier_n = d["n"]
        return nouveaux, False


# ------------------------------------------------------------------------------------------------ noms (autocomplétion)
def _noms_valides(noms: Iterable) -> list[str]:
    """Noms triés, sans ceux qu'on ne peut pas encoder (substitution isolée, permise par JSON) : ils ne seraient pas
    envoyables au serveur."""
    out = []
    for n in noms:
        try:
            n.encode("utf-8")
        except (AttributeError, UnicodeEncodeError):
            continue
        out.append(n)
    return sorted(out)


def construire_noms(jeu: str, donnees) -> dict:
    """Contenu de `chat_noms.json`, toujours encodable. `donnees` : noms du jeu du slot (`ap_reseau.DonneesJeu` : `objets`
    et `locations`, identifiant -> nom), ou None : aucun nom (rien d'une partie précédente ne reste)."""
    return {"format": FORMAT_NOMS, "jeu": str(jeu).encode("utf-8", "replace").decode("utf-8"),
            "objets": _noms_valides(donnees.objets.values()) if donnees else [],
            "lieux": _noms_valides(donnees.locations.values()) if donnees else []}


def ecrire_noms(dossier: str | Path, contenu: dict) -> None:
    """Client : écriture atomique de `chat_noms.json` (OSError si le fichier est pris : à refaire plus tard). Après
    un échec, aucun `.tmp` ne reste."""
    f = Path(dossier) / NOM_NOMS
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_name(f.name + ".tmp")
    try:
        tmp.write_bytes(json.dumps(contenu, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        os.replace(tmp, f)
    except Exception:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def lire_noms(dossier: str | Path) -> dict | None:
    """Lanceur : contenu de `chat_noms.json`, ou None (absent, illisible, format inconnu)."""
    try:
        d = json.loads((Path(dossier) / NOM_NOMS).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return d if isinstance(d, dict) and d.get("format") == FORMAT_NOMS else None


# ------------------------------------------------------------------------------------------------ commandes
def _lire_commandes(p: Path) -> dict:
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return d if isinstance(d, dict) else {}


def deposer_commande(dossier: str | Path, texte: str, session: str, action: dict | None = None) -> dict:
    """Lanceur : ajoute une commande (message ou « !commande », ou `action` décrite par `texte`) pour le client de la
    session `session`, sous le verrou (relire-modifier-écrire, révision du disque + 1). Renvoie la commande écrite."""
    d_ = Path(dossier)
    texte = str(texte).strip()[:TEXTE_MAX]
    if not texte:
        raise ValueError("message vide")
    f = d_ / NOM_COMMANDES
    with VerrouConfig(d_ / NOM_VERROU):
        d = _lire_commandes(f)
        cmds = [c for c in d.get("commandes", []) if isinstance(c, dict)] if isinstance(d.get("commandes"), list) else []
        fichier = d.get("fichier") if isinstance(d.get("fichier"), str) else secrets.token_hex(8)
        rev = max([_entier(c.get("rev"), 0) or 0 for c in cmds] + [_entier(d.get("revision"), 0) or 0]) + 1
        c = {"rev": rev, "id": secrets.token_hex(8), "session": str(session or ""), "texte": texte,
             "horodatage": round(time.time(), 3)}
        if action is not None:
            if not isinstance(action, dict):
                raise ValueError("action invalide")
            c["action"] = action
        cmds = (cmds + [c])[-COMMANDES_MAX:]
        d_.mkdir(parents=True, exist_ok=True)
        tmp = f.with_name(f.name + ".tmp")
        tmp.write_text(json.dumps({"format": FORMAT, "fichier": fichier, "revision": rev, "commandes": cmds},
                                  ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, f)
    return c


class SuiviCommandes:
    """Client : commandes du lanceur à exécuter (voir la docstring du module). `nouvelles()` ne relit le fichier que
    si sa date ou sa taille a changé."""

    def __init__(self, dossier: str | Path, session: str, duree_vie: float = DUREE_VIE):
        self.fichier = Path(dossier) / NOM_COMMANDES
        self.session = session
        self.duree_vie = duree_vie
        self._signature = None
        self._fichier_id: str | None = None
        self._rev = 0
        self._vus: list[str] = []

    def nouvelles(self) -> list[dict]:
        try:
            st = self.fichier.stat()
        except OSError:
            return []
        sig = (st.st_mtime_ns, st.st_size)
        if sig == self._signature:
            return []
        self._signature = sig
        d = _lire_commandes(self.fichier)
        fichier = d.get("fichier")
        if fichier != self._fichier_id:          # fichier recréé : les révisions repartent (les `id` vus protègent)
            self._fichier_id, self._rev = fichier, 0
        cmds = d.get("commandes") if isinstance(d.get("commandes"), list) else []
        maintenant = time.time()
        out = []
        for c in sorted((c for c in cmds if isinstance(c, dict)), key=lambda c: _entier(c.get("rev"), 0) or 0):
            rev, ident = _entier(c.get("rev"), 0) or 0, str(c.get("id", ""))
            if rev <= self._rev or not ident or ident in self._vus:
                continue
            self._rev = rev
            self._vus = (self._vus + [ident])[-4 * COMMANDES_MAX:]
            texte = str(c.get("texte", "")).strip()[:TEXTE_MAX]
            age = maintenant - (float(c.get("horodatage", 0)) if isinstance(c.get("horodatage"), (int, float)) else 0)
            if c.get("session") != self.session or not texte or not -5 <= age <= self.duree_vie:
                continue                         # autre client (dont un client arrêté), vide ou périmée : jamais
            o = {"id": ident, "rev": rev, "texte": texte}
            if isinstance(c.get("action"), dict):
                o["action"] = c["action"]
            out.append(o)
        return out
