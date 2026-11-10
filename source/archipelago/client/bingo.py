"""Bingo-kai (Crank-a-kai) aléatoire, côté client (V3, lot B1, `docs/systemes/archipelago_v3_bingo_aleatoire.md` ;
zone ApBingo, §52 de `docs/systemes/archipelago_boite.md`).

Option de la graine `slot_data.bingo_aleatoire` = {"graine": entier 31 bits, "version": 1} (clé absente : Bingo-kai
d'origine, rien n'est jamais écrit). Le mélange se calcule CHEZ LE JOUEUR (règle 6 : les lots sont une table du RomFS) :

1. lots du Bingo-kai lus dans la ROM du joueur (`installation/bingo_lots.py`, fichier local `bingo_local.json`, généré en
   tâche de fond s'il manque) ;
2. lots MÉLANGEABLES (`unites`) : lots Yo-kai des tables des deux machines ordinaires (présent, passé) que le tirage
   dirigé du jeu ne vise PAS (`TABLES_DIRIGEES` = celles de `k_cibles` de voie.cpp, Pièce bleu ciel, Pile ou passe,
   Super pile ou passe), sans rang de montre exigé, absents de toute table dirigée et de toute table d'une autre
   machine (Voie du mystère, Bingo-kai gagnant, tutoriel) et de toute table à plafond ; les pièces spéciales du lot 19
   et leurs Yo-kai ne bougent donc jamais ;
3. CLASSES : un lot ne s'échange qu'avec un lot de même « signature » = ensemble des (machine, sorte de pièce) qui le
   donnent, sorte = pièce ordinaire (7 pièces de couleur, pièces de jeu) ou pièce rare (pièce spéciale, mystère,
   frisson oiseau / vent / lune, clinquante, joyeuse : QR, mots de passe, tickets à gratter). Chaque Yo-kai du Bingo-kai
   reste donc obtenable aux mêmes machines et par la même sorte de pièce (seuls la pièce et le taux changent) : aucune
   voie du Médaillium ni aucune règle (requête 44 : Sumochi, Pièce rouge du présent) ne se perd ; tous rangs confondus
   (décision de l'humain du 2026-10-17) ;
4. dans chaque classe (au moins deux lots dans la ROM européenne), un DÉRANGEMENT tiré par une suite SHA-256 de (graine,
   version, empreinte des classes) : aucun lot mélangeable ne garde sa place. Même graine + même ROM = même mélange chez
   tous les joueurs ; l'empreinte des classes doit être `EMPREINTE_REFERENCE` (ROM européenne de référence), sinon le
   mélange est refusé (avertissement, rien n'est écrit : le jeu garde son Bingo-kai d'origine) ;
5. écrit dans la boîte (sauvegarde LIÉE seulement) : les lots déplacés en cycles, puis l'en-tête (`valide` en dernier) ;
   `valide` = 0 si la sauvegarde n'est plus liée ; rien n'est écrit si rien ne change ;
6. écrit `bingo.json` pour le lanceur (ce que chaque pièce de chaque machine peut donner dans cette partie).

Option de CONFORT : aucune location n'en dépend ; patch sans la fonction 51 : avertissement (`options_absentes`),
jamais de refus. Aucune lecture périodique : `compile` de la zone est lu une fois par instance du jeu.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sys
import time
from pathlib import Path

try:
    from . import boite_protocole as bp
except ImportError:                                          # module chargé hors paquet (tests, outils)
    import boite_protocole as bp

VERSIONS = (1,)                    # versions du mélange que ce client sait calculer (portées par la graine)
NOM_BASE = "bingo_local.json"     # installation/bingo_lots.py
NOM_FICHIER = "bingo.json"        # écrit pour le lanceur
FORMAT_FICHIER = 1
MACHINES = ("present", "passe")
# Tables que le tirage dirigé du jeu garde (voie.cpp : `k_cibles`, AP_TABLE_BLEU_PRESENT) et tables « au choix » (mode 2,
# lot posé tel quel) : leurs lots ne sont jamais mélangés. Contrôlé contre voie.cpp par `ap_boite_test.py --selftest`.
TABLES_VOIE = (0x15B35EA5, 0x62B46E33, 0x54294050, 0x232E70C6)
TABLES_PIECES_SPECIALES = (0xB73A21B6, 0x27853C27,                               # Pièce 5 étoiles
                           0xEB1042E3,                                           # Pièce frisson (fleur)
                           0x0CA86FE4, 0x7BAF5F72, 0x1B68D697, 0x6C6FE601, 0xF566B7BB, 0x8261872D, 0x1C05128E,
                           0x6B022218, 0xF20B73A2,                               # 9 pièces régionales
                           0x2443B4DF)                                           # Pièce B-k gagnant
TABLES_BLEU_CIEL = (0x3E9E0D66, 0xC03D1120)                                      # Pièce bleu ciel (Bananar)
TABLES_CHOIX = (0x377BE3C6, 0xAE72B27C)                                          # Pile ou passe, Super pile ou passe
TABLES_DIRIGEES = frozenset(TABLES_VOIE + TABLES_PIECES_SPECIALES + TABLES_BLEU_CIEL + TABLES_CHOIX)
# Pièces « ordinaires » (obtenues dans une partie normale : boutiques, butins) : les 7 pièces de couleur hors bleu ciel
# et les pièces de jeu (pièce 0 : 10 pièces de jeu par tour) ; toute autre pièce d'une table non dirigée est « rare ».
PIECES_ORDINAIRES = frozenset((0x9A89BF7C, 0x0380EEC6, 0x7487DE50, 0xEAE34BF3, 0x9DE47B65, 0x04ED2ADF, 0x73EA1A49, 0))
ORDINAIRE, RARE = "o", "r"
# Empreinte des classes (lots et signatures, forme canonique de `empreinte`) de la ROM européenne de référence
# (SHA-1 de code.bin 66143fcb…) : une valeur dérivée (condensat), pas une donnée du jeu.
EMPREINTE_REFERENCE = "25d7392766017e443cea03bffab282ee33ae8339"


class BingoImpossible(Exception):
    """Mélange refusé (message destiné au journal du client et au lanceur)."""


def lire_slot_data(sd: dict) -> tuple[dict | None, str]:
    """({"graine", "version"} ou None sans mélange ; erreur de forme, "" si aucune)."""
    v = sd.get("bingo_aleatoire") if isinstance(sd, dict) else None
    if v is None:
        return None, ""
    try:
        g, ver = int(v["graine"]), int(v.get("version", 1))
    except (KeyError, TypeError, ValueError):
        return None, f"slot_data.bingo_aleatoire illisible : {v!r}"[:120]
    if not 0 <= g < 1 << 31:
        return None, f"graine du Bingo-kai hors bornes : {g}"
    return {"graine": g, "version": ver}, ""


def unites(base: dict) -> dict[int, tuple]:
    """{lot : signature} des lots mélangeables (voir le point 2 du docstring) ; signature = tuple trié des
    (machine, sorte de pièce)."""
    tables = {int(t): x for t, x in base["tables"].items()}
    lots = {int(l): x for l, x in base["lots"].items()}
    interdits = set()
    for t in set(TABLES_DIRIGEES) | {int(x) for x in base.get("autres_tables") or ()}:
        interdits |= {l for l, _p, _c in tables.get(t, ())}
    for t, x in tables.items():
        if any(c for _l, _p, c in x):                      # table à plafond : le jeu n'y applique jamais le mélange
            interdits |= {l for l, _p, _c in x}
    sig: dict[int, set] = {}
    for m in MACHINES:
        for piece, _cout, t in base["machines"][m]:
            if t in TABLES_DIRIGEES:
                continue
            sorte = ORDINAIRE if piece in PIECES_ORDINAIRES else RARE
            for l, _p, _c in tables.get(t, ()):
                g = lots.get(l)
                if g is None or g[0] != 0 or g[2] != 0 or l in interdits or not l:
                    continue
                sig.setdefault(l, set()).add((m, sorte))
    return {l: tuple(sorted(s)) for l, s in sig.items()}


def classes(u: dict[int, tuple]) -> list[tuple[tuple, list[int]]]:
    """Classes (signature, lots triés), dans l'ordre des signatures."""
    par: dict[tuple, list[int]] = {}
    for l, s in u.items():
        par.setdefault(s, []).append(l)
    return [(s, sorted(par[s])) for s in sorted(par)]


def empreinte(cl) -> str:
    canon = json.dumps({"format": 1, "classes": [[list(map(list, s)), ls] for s, ls in cl]}, separators=(",", ":"))
    return hashlib.sha1(canon.encode("ascii")).hexdigest()


class _Alea:
    """Suite pseudo-aléatoire déterministe (SHA-256 en mode compteur) : la même chez tous les joueurs et quelle que
    soit la version de Python (pas le module `random`)."""

    def __init__(self, graine: int, version: int, emp: str):
        self.cle = f"ykw2ap-bingo:{graine}:{version}:{emp}".encode("ascii")
        self.n = 0
        self.tampon = b""

    def _octets(self, k: int) -> bytes:
        while len(self.tampon) < k:
            self.tampon += hashlib.sha256(self.cle + self.n.to_bytes(8, "little")).digest()
            self.n += 1
        out, self.tampon = self.tampon[:k], self.tampon[k:]
        return out

    def sous(self, n: int) -> int:
        """Entier uniforme dans [0, n) (rejet : aucun biais)."""
        if n <= 1:
            return 0
        bits = (n - 1).bit_length()
        while True:
            x = int.from_bytes(self._octets(4), "little") & ((1 << bits) - 1)
            if x < n:
                return x


_REFERENCE = object()


def calculer(base: dict, graine: int, version: int = 1, reference=_REFERENCE) -> dict:
    """Mélange de la graine : {"sigma": {lot : image} (lots déplacés seulement), "classes": [...], "empreinte"}.
    BingoImpossible : version inconnue, base illisible, empreinte différente de `reference` (None : pas de contrôle,
    bases synthétiques des tests)."""
    if version not in VERSIONS:
        raise BingoImpossible(f"version {version} du mélange du Bingo-kai inconnue de ce client (client trop ancien)")
    try:
        u = unites(base)
    except (KeyError, TypeError, ValueError) as e:
        raise BingoImpossible(f"table locale du Bingo-kai illisible ({e})")
    cl = classes(u)
    emp = empreinte(cl)
    if reference is _REFERENCE:
        reference = EMPREINTE_REFERENCE
    if reference is not None and emp != reference:
        raise BingoImpossible("lots du Bingo-kai différents de ceux de la ROM de référence (empreinte "
                              f"{emp[:12]}… au lieu de {reference[:12]}…) : ROM européenne de Yo-kai Watch 2 attendue")
    alea = _Alea(graine, version, emp)
    sigma = {}
    for _s, ls in cl:
        if len(ls) < 2:
            continue
        while True:                                       # dérangement uniforme : Fisher-Yates, rejet des points fixes
            perm = list(ls)
            for i in range(len(perm) - 1, 0, -1):
                j = alea.sous(i + 1)
                perm[i], perm[j] = perm[j], perm[i]
            if all(a != b for a, b in zip(ls, perm)):
                break
        sigma.update(zip(ls, perm))
    return {"sigma": sigma, "classes": cl, "empreinte": emp}


def contenu_pieces(base: dict, sigma: dict, langue: str = "fr") -> list[dict]:
    """Ce que chaque pièce de chaque machine peut donner (Yo-kai seulement) sous `sigma` (vide : jeu d'origine) :
    [{machine, piece, nom, dirigee, yokai: [{param, medaille, nom, poids, total, change}]}], dans l'ordre des machines
    puis des lignes du fichier."""
    tables = {int(t): x for t, x in base["tables"].items()}
    lots = {int(l): x for l, x in base["lots"].items()}
    yk = base.get("yokai") or {}
    pieces = base.get("pieces") or {}
    lg = "engb" if langue.startswith("en") else langue
    out = []
    for m in MACHINES:
        for piece, _cout, t in base["machines"][m]:
            x = tables.get(t, ())
            total = sum(p for _l, p, _c in x)
            ligne = {"machine": m, "piece": piece, "nom": (pieces.get(str(piece)) or {}).get(lg, ""),
                     "dirigee": t in TABLES_DIRIGEES, "yokai": []}
            for l, p, _c in x:
                image = sigma.get(l, l)
                g = lots.get(image)
                if g is None or g[0] != 0:
                    continue
                info = yk.get(str(g[1])) or {}
                ligne["yokai"].append({"param": g[1], "medaille": int(info.get("medaille") or 0),
                                       "nom": (info.get("noms") or {}).get(lg, ""), "poids": p, "total": total,
                                       "change": image != l})
            if ligne["yokai"]:
                out.append(ligne)
    return out


def _installation():
    racine = Path(__file__).resolve().parents[1]          # archipelago/
    if str(racine) not in sys.path:
        sys.path.insert(0, str(racine))
    from installation import bingo_lots as ib               # noqa: E402
    return ib


def ecrire_fichier(dossier, d: dict) -> None:
    p = Path(dossier)
    try:
        p.mkdir(parents=True, exist_ok=True)
        tmp = p / (NOM_FICHIER + ".tmp")
        tmp.write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        os.replace(tmp, p / NOM_FICHIER)
    except OSError:
        pass


def lire_fichier(dossier) -> dict | None:
    try:
        d = json.loads((Path(dossier) / NOM_FICHIER).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return d if isinstance(d, dict) and d.get("format") == FORMAT_FICHIER else None


class SuiviBingo:
    """État du client pour le Bingo-kai aléatoire (une instance par `Synchro`)."""

    def __init__(self, synchro):
        self.s = synchro
        self.option: dict | None = None
        self.erreur = ""
        self.sigma: dict | None = None      # σ calculée (lots déplacés) ; None : pas encore, ou refusée
        self.statut = "aucun"               # aucun | calcul | pret | refuse | base_absente
        self.message = ""
        self._tache: asyncio.Task | None = None
        self._compile: tuple[int, bool] | None = None   # (instance, ApBingo publiée et compilée)
        self._ecrite: tuple | None = None    # (instance, sauvegarde) du dernier mélange écrit
        self._valide_instance: int | None = None

    # ------------------------------------------------------------------ graine
    def appliquer(self, sd: dict) -> None:
        self.option, self.erreur = lire_slot_data(sd)
        self.sigma, self._ecrite = None, None
        self.statut = "aucun" if self.option is None else "calcul"
        if self.erreur:
            self.s.log.warning("Bingo-kai aléatoire : %s ; Bingo-kai d'origine", self.erreur)
        if self.option is not None:
            self.preparer()

    @property
    def actif(self) -> bool:
        return self.option is not None

    def nouvelle_instance(self) -> None:
        self._compile = None
        self._ecrite = None
        self._valide_instance = None

    def oublier(self) -> None:
        self._ecrite = None

    # ------------------------------------------------------------------ calcul (ROM du joueur)
    def preparer(self) -> str:
        if self.option is None or self.statut in ("pret", "refuse"):
            return self.statut
        if self._tache is not None and not self._tache.done():
            return "calcul"
        try:
            ib = _installation()
        except Exception as e:  # noqa: BLE001 - module distribué avec le client
            return self._refus("base_absente", f"module installation/bingo_lots.py introuvable ({e})")
        base = ib.charger(self.s.stockage.dossier)
        if base is None:
            rom = self.s.config.rom
            if not rom or not Path(rom).is_file():
                return self._refus("base_absente", "lots du Bingo-kai absents et ROM non configurée (« Réparer le mod » "
                                   "dans le lanceur)")
            if self.statut == "base_absente":
                return self.statut
            self.s.log.info("Bingo-kai aléatoire : lots lus dans la ROM…")
            self.statut = "calcul"
            try:
                self._tache = asyncio.get_running_loop().create_task(
                    asyncio.to_thread(ib.generer_fichier, rom, self.s.stockage.dossier))
            except RuntimeError:                         # hors boucle (tests) : tout de suite
                ib.generer_fichier(rom, self.s.stockage.dossier)
                return self.preparer()
            self._tache.add_done_callback(self._generee)
            return "calcul"
        try:
            r = calculer(base, self.option["graine"], self.option["version"])
        except BingoImpossible as e:
            return self._refus("refuse", str(e))
        self.sigma, self.statut, self.message = r["sigma"], "pret", ""
        self.s.log.info("Bingo-kai aléatoire : %d Yo-kai échangés dans %d classe(s)", len(self.sigma),
                        sum(1 for _s, ls in r["classes"] if len(ls) > 1))
        self._publier(base)
        return "pret"

    def _generee(self, t: asyncio.Task) -> None:
        if t.cancelled():
            return
        e = t.exception()
        if e is not None:
            self._refus("refuse", f"ROM refusée : {e}")
        else:
            self.statut = "calcul"
            self.preparer()

    def _refus(self, etat: str, message: str) -> str:
        if self.statut != etat or self.message != message:
            self.s.log.warning("Bingo-kai aléatoire : %s ; le jeu garde son Bingo-kai d'origine", message)
        self.statut, self.message = etat, message
        self._publier(None)
        return etat

    def _publier(self, base: dict | None) -> None:
        d = {"format": FORMAT_FICHIER, "horodatage": time.time(), "ident_partie": self.s.ident_partie,
             "statut": self.statut, "message": self.message,
             "version": (self.option or {}).get("version"), "deplaces": len(self.sigma or {})}
        if base is not None and self.sigma is not None:
            d["pieces"] = {lg: contenu_pieces(base, self.sigma, lg) for lg in ("fr", "en")}
        ecrire_fichier(self.s.stockage.dossier, d)

    # ------------------------------------------------------------------ jeu
    async def compilee(self, h) -> bool:
        if self._compile is None or self._compile[0] != self.s._instance:
            lu = False
            if h is not None and bp.bingo_disponible(h):
                lu = bp.bingo_compile(await self.s.pont.lire(bp.ZONE + bp.OFF_BINGO, 8))
            self._compile = (self.s._instance, lu)
            self.s.log.info("Bingo-kai aléatoire compilé dans le jeu : %s", "oui" if lu else
                            "non (patch d'avant le lot B1, ou compilé sans)")
        return self._compile[1]

    async def ecrire(self, h) -> None:
        """σ (cycles) puis l'en-tête (`valide` en dernier) pour la sauvegarde liée ; `valide` = 0 si elle ne l'est
        plus. Aucune écriture si rien ne change."""
        if self.option is None or self.preparer() != "pret" or not self.sigma:
            return
        if self._compile is None or self._compile[0] != self.s._instance or not self._compile[1]:
            return
        if self.s.sauvegarde == "liee":
            cle = (self.s._instance, h.ident_sauvegarde)
            if cle == self._ecrite:
                return
            ecritures, texte = bp.ecritures_bingo(self.sigma, self.s.ident_partie or 0), "écrit (sauvegarde liée)"
            self._ecrite, self._valide_instance = cle, self.s._instance
        else:
            self._ecrite = None
            if self._valide_instance != self.s._instance:
                return
            ecritures, texte = bp.ecritures_bingo_retrait(), "retiré (sauvegarde non liée)"
            self._valide_instance = None
        async with self.s.pont.transaction():
            for off, octets in ecritures:
                await self.s.pont.ecrire(bp.ZONE + off, octets)
        self.s.log.info("Bingo-kai aléatoire : mélange %s", texte)
