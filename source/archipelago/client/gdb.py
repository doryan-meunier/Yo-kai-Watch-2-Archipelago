"""Pont GDB persistant vers le stub d'Azahar (asyncio, bibliothèque standard seulement).

Ce que ce module sait du stub d'Azahar (2124.3), et comment il s'y adapte (docs/systemes/archipelago_boite.md
§7 et « Test en jeu », CONCEPTION.md §8.4) :

- Le stub **se ferme dès que son client se déconnecte** (il faut alors relancer Azahar). Donc :
  * UNE seule connexion TCP, ouverte une fois et gardée : l'attente du port se fait par des tentatives
    de connexion qui échouent (port fermé) ; dès qu'une tentative réussit, c'est LA connexion. Aucune
    connexion « sonde » qui s'ouvrirait puis se fermerait ;
  * aucune erreur de protocole (délai dépassé, paquet inattendu) ne ferme la connexion : on se
    resynchronise (purge du flux) et on continue ;
  * jamais de paquet 'D' (détachement) tant que le jeu doit être suivi : seulement `fermer(detacher=True)`.
- À la connexion, le stub **arrête le processeur** (et peut envoyer un paquet d'arrêt spontané) ; avec
  « Enable GDB stub », le jeu attend même le débogueur pour démarrer : `connecter()` relance l'émulation.
  Tant que le jeu n'a pas démarré, les lectures répondent « E00 » (`AccesRefuse`).
- Les écritures 'M' ne sont acceptées **que jeu interrompu**. Toute écriture passe par une
  `transaction()` : interruption (0x03) CONFIRMÉE par un paquet d'arrêt T/S (sinon interrogation par
  « ? », deux essais), écritures, puis reprise ('c'). Si l'arrêt n'est pas confirmé, rien n'est écrit
  (`ArretNonConfirme`) et l'émulation est relancée (jamais de jeu laissé figé).
- Lectures : soit jeu interrompu (sûr, provoque un micro-arrêt), soit jeu en marche si le stub les sert
  (le stub de Citra/Azahar traite les paquets dans sa boucle processeur ; à confirmer par J8). Mode
  `lectures_en_marche=None` (automatique) : sondé à la première lecture réussie ; un silence fait revenir
  au mode interrompu, et une réponse tardive est jetée par la purge.
- Chaque paquet est traité par l'émulateur entre deux tranches d'exécution (il fige le jeu le temps du traitement) et
  chaque arrêt fige le jeu jusqu'à la reprise : le client lit le moins possible (docs/systemes/archipelago_boite.md
  §23). `lot()` regroupe les écritures d'un tour dans UN arrêt (pris à la première écriture seulement) ; la purge
  du flux (paquets d'arrêt en double, réponses tardives) se fait AVANT l'interruption, jeu en marche, jamais pendant
  l'arrêt. `stats` compte les paquets, octets et arrêts (mesures du §23).
- Relancement du jeu (ou d'Azahar) : la connexion reçoit une fin de flux ; l'appelant rappelle
  `connecter()`, qui attend la réouverture du port. `sessions` compte les connexions (une nouvelle session
  = le jeu a pu être relancé : réécrire les tables de la boîte).

Usage :
    pont = PontGdb()
    await pont.connecter()                     # attend le port, relance l'émulation
    donnees = await pont.lire(0x0091C000, 0x100)
    async with pont.transaction():             # jeu arrêté (confirmé) pendant le bloc
        await pont.ecrire(adresse, octets)
    await pont.fermer()                        # fin du suivi (le stub d'Azahar se ferme alors)
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from typing import AsyncIterator, Callable

PORT_AZAHAR = 24689            # port par défaut du stub GDB d'Azahar / Citra
TAILLE_BLOC = 0x400            # taille max d'une lecture/écriture par paquet (le tampon du stub est limité)
_HEX = frozenset("0123456789abcdefABCDEF")


class ErreurGdb(Exception):
    """Erreur du pont GDB."""


class Deconnecte(ErreurGdb):
    """Pas de connexion au stub, ou connexion perdue (jeu ou émulateur fermé / relancé)."""


class DelaiDepasse(ErreurGdb):
    """Le stub n'a pas répondu à temps. La connexion est gardée ; le flux sera purgé avant l'échange suivant."""


class ArretNonConfirme(ErreurGdb):
    """L'émulateur n'a pas confirmé l'arrêt : rien n'a été écrit, l'émulation a été relancée."""


class ArretRequis(ErreurGdb):
    """Écriture demandée hors transaction (jeu en marche) : refusée côté client."""


class AccesRefuse(ErreurGdb):
    """Le stub a répondu « Exx » (mémoire pas encore montée au démarrage du jeu, ou adresse hors segment)."""

    def __init__(self, message: str, code: str):
        super().__init__(message)
        self.code = code


def somme_controle(charge: bytes) -> bytes:
    return b"%02x" % (sum(charge) % 256)


def encoder_paquet(charge: str | bytes) -> bytes:
    b = charge.encode() if isinstance(charge, str) else charge
    return b"$" + b + b"#" + somme_controle(b)


def decoder_rle(charge: bytes) -> bytes:
    """Décode la compression « x*n » du protocole GDB (le caractère x répété ord(n) - 29 fois de plus)."""
    if b"*" not in charge:
        return charge
    out = bytearray()
    i = 0
    while i < len(charge):
        c = charge[i]
        if c == 0x2A and out and i + 1 < len(charge):     # '*'
            out += out[-1:] * (charge[i + 1] - 29)
            i += 2
            continue
        out.append(c)
        i += 1
    return bytes(out)


def est_arret(p: str) -> bool:
    """Paquet d'arrêt (T05…, S05)."""
    return bool(p) and p[0] in "TS" and len(p) >= 3 and all(c in _HEX for c in p[1:3])


def est_fin_processus(p: str) -> bool:
    """Paquet W (processus terminé) ou X (tué)."""
    return bool(p) and p[0] in "WX" and len(p) >= 3 and all(c in _HEX for c in p[1:3])


def est_erreur(p: str) -> bool:
    return len(p) == 3 and p[0] == "E" and all(c in _HEX for c in p[1:])


class PontGdb:
    """Session GDB persistante avec le stub d'Azahar (voir le docstring du module)."""

    def __init__(self, hote: str = "127.0.0.1", port: int = PORT_AZAHAR, *, delai: float = 2.0,
                 delai_lecture_en_marche: float = 1.0, lectures_en_marche: bool | None = None,
                 delai_connexion: float = 20.0, journal: logging.Logger | None = None):
        self.hote, self.port = hote, port
        self.delai = delai                                  # réponse attendue du stub (jeu arrêté)
        # réponse d'arrêt attendue à la connexion : la connexion TCP aboutit dès que le port est ouvert, mais
        # l'émulateur peut n'accueillir le client qu'après son démarrage (Zakuro : chargement du code recompilé
        # avant la 1re image, plus de 2 s ; bug « frame 0 » du 2026-10-25)
        self.delai_connexion = delai_connexion
        self.delai_lecture_en_marche = delai_lecture_en_marche
        self.mode_lectures = lectures_en_marche             # None : automatique
        self.lectures_en_marche: bool | None = lectures_en_marche   # mode effectif (None : pas encore sondé)
        self.log = journal or logging.getLogger("ykw2ap.gdb")
        self._lecteur: asyncio.StreamReader | None = None
        self._ecrivain: asyncio.StreamWriter | None = None
        self._tampon = b""
        self._dernier = b""                                 # dernier paquet envoyé (retransmission sur '-')
        self._desynchro = False
        self._verrou = asyncio.Lock()
        self._proprietaire: asyncio.Task | None = None
        self.en_marche = False
        self.sessions = 0                                   # connexions établies depuis la création
        self.echecs_arret = 0                               # interruptions non confirmées consécutives
        self.echecs_lecture_en_marche = 0
        self.stats = {"interruptions": 0, "arrets_refuses": 0, "lectures": 0, "ecritures": 0, "purges": 0,
                      "delais": 0, "parasites": 0, "paquets": 0, "octets": 0, "arrets": 0, "duree_arret": 0.0,
                      "lectures_arretees": 0}
        self.numero_arret = 0                               # +1 à chaque arrêt confirmé (en-tête relu une fois par arrêt)
        self._t_arret = 0.0
        self._lot = False                                   # dans un `lot()` : l'arrêt est gardé jusqu'à sa fin
        self._lot_arret = False                             # le lot a arrêté le jeu (reprise à sa fin)

    # ------------------------------------------------------------------ connexion
    @property
    def connecte(self) -> bool:
        return self._ecrivain is not None and not self._ecrivain.is_closing()

    async def connecter(self, attente_max: float | None = None, intervalle: float = 0.5,
                        arreter: Callable[[], bool] | None = None) -> None:
        """Attend que le port du stub s'ouvre et s'y connecte (une seule connexion, gardée), puis relance
        l'émulation (toujours : voir `_initialiser`). `attente_max` None = attendre indéfiniment ; `arreter()`
        vrai = abandonner (pendant l'attente de la réponse d'arrêt : reprise envoyée sans attendre plus).
        Les tentatives refusées (port fermé) ne comptent pas comme des clients pour le stub."""
        if self.connecte:
            return
        debut = time.monotonic()
        premiere = True
        while True:
            try:
                lecteur, ecrivain = await asyncio.wait_for(
                    asyncio.open_connection(self.hote, self.port), timeout=max(self.delai, 1.0))
                break
            except (OSError, asyncio.TimeoutError) as e:
                if premiere:
                    self.log.info("Stub GDB %s:%d pas encore ouvert (%s) : attente…", self.hote, self.port, e)
                    premiere = False
                if arreter and arreter():
                    raise Deconnecte("attente du stub abandonnée") from e
                if attente_max is not None and time.monotonic() - debut >= attente_max:
                    raise Deconnecte(f"stub GDB {self.hote}:{self.port} injoignable après {attente_max} s") from e
                await asyncio.sleep(intervalle)
        self._lecteur, self._ecrivain = lecteur, ecrivain
        self._tampon = b""
        self._desynchro = False
        self.sessions += 1
        self.echecs_arret = 0
        self.echecs_lecture_en_marche = 0
        self.lectures_en_marche = self.mode_lectures        # re-sondé à chaque session (mode automatique)
        self.log.info("Connecté au stub GDB %s:%d (session %d)", self.hote, self.port, self.sessions)
        async with self._acces():
            await self._initialiser(arreter)

    async def _initialiser(self, arreter: Callable[[], bool] | None = None) -> None:
        """Le stub arrête le processeur à la connexion (paquet d'arrêt spontané possible) : on le confirme
        par « ? » (attente jusqu'à `delai_connexion`), puis on relance l'émulation. Dans TOUS les cas la
        reprise ('c') est envoyée : un stub qui n'a pas encore accueilli le client la traitera après le « ? »
        (Zakuro arrête le jeu en accueillant le client et attend 'c' : sans elle, jeu figé à la 1re image) ;
        un stub dont l'émulation tourne déjà l'ignore (Zakuro : `halted = false` ; Citra / Azahar :
        `Continue()`, rien envoyé), comme la reprise forcée qui suit une interruption non confirmée."""
        await self._purger(0.3)
        self.en_marche = False
        await self._envoyer("?")
        fin = time.monotonic() + max(self.delai_connexion, self.delai)
        r = None
        while r is None:
            reste = fin - time.monotonic()
            if reste <= 0 or (arreter and arreter()):
                break
            try:
                r = await self._attendre(est_arret, min(reste, 0.5))
            except DelaiDepasse:
                pass
        if r is None:
            # pas de motif d'arrêt : stub pas encore prêt, ou émulation déjà en marche ; la reprise part quand
            # même, une réponse d'arrêt tardive sera jetée comme parasite (aucune écriture sans arrêt confirmé)
            self.log.warning("Le stub n'a pas confirmé l'arrêt à la connexion : reprise envoyée quand même")
            self._desynchro = True
        await self._continuer()

    async def fermer(self, detacher: bool = False) -> None:
        """Termine le suivi : relance l'émulation, puis ferme la connexion. ATTENTION : sur Azahar, fermer
        la connexion arrête le stub (il faudra relancer Azahar pour se reconnecter). `detacher=True`
        envoie en plus 'D' (détachement propre) : seulement quand le jeu n'a plus à être suivi."""
        if not self.connecte:
            self._oublier()
            return
        try:
            async with self._acces():
                with contextlib.suppress(ErreurGdb, OSError):
                    await self._continuer()
                    if detacher:
                        await self._envoyer("D")
                        with contextlib.suppress(ErreurGdb):
                            await self._attendre(lambda p: p == "OK", 0.3)
        finally:
            ecrivain = self._ecrivain
            self._oublier()
            if ecrivain is not None:
                ecrivain.close()
                with contextlib.suppress(Exception):
                    await ecrivain.wait_closed()

    def _oublier(self) -> None:
        self._lecteur = self._ecrivain = None
        self._tampon = b""
        self.en_marche = False

    def _perdre(self, raison: str) -> Deconnecte:
        self.log.warning("Connexion au stub GDB perdue : %s", raison)
        if self._ecrivain is not None:
            self._ecrivain.close()
        self._oublier()
        return Deconnecte(raison)

    # ------------------------------------------------------------------ verrou (réentrant par tâche)
    @contextlib.asynccontextmanager
    async def _acces(self) -> AsyncIterator[None]:
        tache = asyncio.current_task()
        if self._proprietaire is tache:
            yield
            return
        async with self._verrou:
            self._proprietaire = tache
            try:
                yield
            finally:
                self._proprietaire = None

    # ------------------------------------------------------------------ paquets
    async def _envoyer(self, charge: str, brut: bool = False) -> None:
        if not self.connecte:
            raise Deconnecte("pas de connexion au stub GDB")
        donnees = charge.encode() if brut else encoder_paquet(charge)
        if not brut:
            self._dernier = donnees
        self.stats["paquets"] += 1
        self.stats["octets"] += len(donnees)
        try:
            self._ecrivain.write(donnees)
            await self._ecrivain.drain()
        except (OSError, ConnectionError) as e:
            raise self._perdre(f"envoi impossible ({e})") from e

    async def _recevoir(self, fin: float) -> None:
        reste = fin - time.monotonic()
        if reste <= 0:
            raise DelaiDepasse("pas de réponse du stub")
        try:
            morceau = await asyncio.wait_for(self._lecteur.read(65536), timeout=reste)
        except asyncio.TimeoutError:
            raise DelaiDepasse("pas de réponse du stub") from None
        except (OSError, ConnectionError) as e:
            raise self._perdre(f"lecture impossible ({e})") from e
        if not morceau:
            raise self._perdre("fin de flux (jeu ou émulateur fermé, ou relancé)")
        self._tampon += morceau

    async def _paquet(self, fin: float) -> str:
        """Paquet suivant du stub (accusé '+' envoyé), en gérant '+', '-' (retransmission), les sommes
        de contrôle fausses et la compression « * »."""
        while True:
            if not self.connecte:
                raise Deconnecte("pas de connexion au stub GDB")
            t = self._tampon
            i = 0
            while i < len(t) and t[i] != 0x24:                # '$'
                if t[i] == 0x2D and self._dernier:            # '-' : le stub redemande le dernier paquet
                    self._ecrivain.write(self._dernier)
                i += 1
            t = t[i:]
            self._tampon = t
            d = t.find(b"#")
            if t and d >= 0 and len(t) >= d + 3:
                charge, cs = t[1:d], t[d + 1:d + 3]
                self._tampon = t[d + 3:]
                if cs.lower() != somme_controle(charge):
                    self._ecrivain.write(b"-")
                    continue
                self._ecrivain.write(b"+")
                self.stats["octets"] += len(charge) + 4
                return decoder_rle(charge).decode("latin-1")
            await self._recevoir(fin)

    async def _attendre(self, accepte: Callable[[str], bool], delai: float, erreurs: bool = False) -> str:
        """Lit des paquets jusqu'à un paquet `accepte` ; ignore les parasites (O…, arrêts, réponses
        tardives). Avec `erreurs`, un « Exx » est aussi rendu."""
        fin = time.monotonic() + delai
        while True:
            p = await self._paquet(fin)
            if accepte(p) or (erreurs and est_erreur(p)):
                return p
            if est_fin_processus(p):
                raise self._perdre(f"processus du jeu terminé ({p})")
            self.stats["parasites"] += 1

    async def _purger(self, duree: float) -> None:
        """Jette tout ce qui est en attente (paquets d'arrêt, réponses tardives) : resynchronise le flux."""
        self.stats["purges"] += 1
        self._tampon = b""
        fin = time.monotonic() + duree
        while True:
            try:
                await self._recevoir(fin)
            except DelaiDepasse:
                break
            self._tampon = b""
        self._desynchro = False

    async def _echange(self, charge: str, accepte: Callable[[str], bool], delai: float | None = None) -> str:
        if self._desynchro:
            await self._purger(0.1)
        await self._envoyer(charge)
        try:
            return await self._attendre(accepte, self.delai if delai is None else delai, erreurs=True)
        except DelaiDepasse:
            self.stats["delais"] += 1
            self._desynchro = True                  # une réponse tardive pourrait décaler la suivante
            raise

    # ------------------------------------------------------------------ exécution
    async def _continuer(self) -> None:
        if not self.en_marche:
            await self._envoyer("c")                # pas de réponse tant que le jeu tourne
            self.en_marche = True
            if self._t_arret:
                self.stats["duree_arret"] += time.monotonic() - self._t_arret
                self._t_arret = 0.0

    async def _interrompre(self) -> bool:
        if not self.en_marche:
            return True
        self.stats["interruptions"] += 1
        # purge AVANT l'arrêt (jeu en marche : ne gèle rien) : un paquet d'arrêt en double d'un arrêt précédent ne doit
        # pas passer pour la confirmation de celui-ci ; un paquet d'arrêt en double de CELUI-CI, arrivé pendant les
        # échanges qui suivent, est ignoré comme parasite (réponses attendues : hexadécimal ou « OK »)
        await self._purger(0.05)
        self._t_arret = time.monotonic()
        for _ in range(2):
            await self._envoyer("\x03", brut=True)
            for question in (False, True):
                try:
                    if question:
                        await self._envoyer("?")
                    await self._attendre(est_arret, self.delai)
                except DelaiDepasse:
                    continue
                self.en_marche = False
                self.echecs_arret = 0
                self.numero_arret += 1
                self.stats["arrets"] += 1
                return True
        # arrêt NON confirmé : état incertain -> purge, reprise forcée, et rien ne doit être écrit
        self.stats["arrets_refuses"] += 1
        self.echecs_arret += 1
        await self._purger(0.05)
        self.en_marche = False
        await self._continuer()
        if self.lectures_en_marche and self.mode_lectures is None and self.echecs_arret >= 3:
            self.log.info("Interruptions refusées en mode lectures en marche : retour au mode arrêté")
            self.lectures_en_marche = False
        return False

    async def interrompre(self) -> bool:
        """Arrête l'émulation ; True seulement si l'arrêt est confirmé (sinon l'émulation est relancée)."""
        async with self._acces():
            return await self._interrompre()

    async def continuer(self) -> None:
        async with self._acces():
            await self._continuer()

    @contextlib.asynccontextmanager
    async def transaction(self) -> AsyncIterator["PontGdb"]:
        """Jeu arrêté (arrêt confirmé) pendant le bloc, puis relancé. Réentrante dans une même tâche.
        Lève ArretNonConfirme si l'émulateur ne confirme pas l'arrêt (rien n'est alors exécuté)."""
        async with self._acces():
            if not self.connecte:
                raise Deconnecte("pas de connexion au stub GDB")
            relancer = self.en_marche
            if relancer and not await self._interrompre():
                raise ArretNonConfirme("l'émulateur n'a pas confirmé l'arrêt : rien n'est écrit")
            if relancer and self._lot:
                self._lot_arret, relancer = True, False             # reprise à la fin du lot
            try:
                yield self
            finally:
                if relancer and self.connecte:
                    with contextlib.suppress(Deconnecte):
                        await self._continuer()

    @contextlib.asynccontextmanager
    async def lot(self) -> AsyncIterator["PontGdb"]:
        """Regroupe les transactions du bloc dans UN arrêt : le jeu n'est arrêté qu'à la première transaction (aucun
        arrêt si le bloc n'écrit rien), reste arrêté pour les suivantes, et est relancé à la fin du bloc. Le bloc ne
        doit contenir aucune attente longue (réseau, disque) : le jeu est figé de la première écriture à la fin du
        bloc. Réentrant (un lot dans un lot ne fait rien de plus)."""
        async with self._acces():
            if self._lot:
                yield self
                return
            self._lot, self._lot_arret = True, False
            try:
                yield self
            finally:
                self._lot = False
                if self._lot_arret:
                    self._lot_arret = False
                    if self.connecte:
                        with contextlib.suppress(Deconnecte):
                            await self._continuer()

    # ------------------------------------------------------------------ mémoire
    async def _lire_brut(self, adr: int, n: int, delai: float | None = None) -> bytes:
        out = bytearray()
        for o in range(0, n, TAILLE_BLOC):
            k = min(TAILLE_BLOC, n - o)
            r = await self._echange(f"m{adr + o:x},{k:x}",
                                    lambda p, k=k: len(p) == 2 * k and all(c in _HEX for c in p), delai)
            if est_erreur(r):
                raise AccesRefuse(f"lecture refusée à {adr + o:#x} : {r}", r)
            out += bytes.fromhex(r)
        self.stats["lectures"] += 1
        return bytes(out)

    async def lire(self, adr: int, n: int) -> bytes:
        """Lit n octets. Jeu déjà arrêté (transaction) : lecture directe. Sinon, selon le mode : lecture jeu
        en marche, ou interruption confirmée -> lecture -> reprise (ArretNonConfirme si refusée)."""
        async with self._acces():
            if not self.connecte:
                raise Deconnecte("pas de connexion au stub GDB")
            if not self.en_marche:
                return await self._lire_brut(adr, n)
            if self.lectures_en_marche is not False:
                try:
                    r = await self._lire_brut(adr, n, self.delai_lecture_en_marche)
                except DelaiDepasse:
                    self.echecs_lecture_en_marche += 1
                    if self.lectures_en_marche is None or self.echecs_lecture_en_marche >= 2:
                        if self.lectures_en_marche:
                            self.log.info("Lectures jeu en marche sans réponse : retour au mode arrêté")
                        self.lectures_en_marche = False
                else:
                    self.echecs_lecture_en_marche = 0
                    if self.lectures_en_marche is None:
                        self.lectures_en_marche = True
                        self.log.info("Le stub sert les lectures jeu en marche : plus d'arrêt pour lire")
                    return r
            if not await self._interrompre():
                raise ArretNonConfirme("l'émulateur n'a pas confirmé l'arrêt : lecture non faite")
            self.stats["lectures_arretees"] += 1
            try:
                return await self._lire_brut(adr, n)
            finally:
                if self.connecte:
                    await self._continuer()

    async def ecrire(self, adr: int, donnees: bytes) -> None:
        """Écrit des octets, jeu arrêté seulement (dans une `transaction()`), par blocs dans l'ordre des
        adresses. Un mot de validation doit être écrit par un appel séparé, APRÈS le contenu."""
        async with self._acces():
            if not self.connecte:
                raise Deconnecte("pas de connexion au stub GDB")
            if self.en_marche:
                raise ArretRequis(f"écriture à {adr:#x} hors transaction (jeu en marche) : refusée")
            for o in range(0, len(donnees), TAILLE_BLOC):
                bloc = donnees[o:o + TAILLE_BLOC]
                r = await self._echange(f"M{adr + o:x},{len(bloc):x}:{bloc.hex()}", lambda p: p == "OK")
                if est_erreur(r):
                    raise AccesRefuse(f"écriture refusée à {adr + o:#x} : {r}", r)
            self.stats["ecritures"] += 1
