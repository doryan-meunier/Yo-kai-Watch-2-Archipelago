"""Client Archipelago INVISIBLE de Yo-kai Watch 2 (option B : saisie dans le lanceur, état dans le jeu et le lanceur).

Démarrable sans fenêtre :
    pythonw archipelago/client/principal.py                    # attend le jeu indéfiniment
    pythonw archipelago/client/principal.py --quitter-avec 1234   # s'arrête quand le processus 1234 (Azahar) se termine
    pythonw archipelago/client/principal.py --quitter-avec-fichier F   # idem, PID d'Azahar lu dans F (lanceur)
    python  archipelago/client/principal.py --console          # même chose, journal aussi sur la console
    pythonw archipelago/client/principal.py --suivi --lanceur-pid 1234   # suivi seul (lanceur), jeu attaché sur demande

Il attend que le stub GDB d'Azahar soit ouvert (port 24689 par défaut), puis fait tout seul : lecture de la
configuration (config.json du lanceur), connexion au serveur, dons, checks, victoire
(`synchro.Synchro`). Il n'ouvre aucune fenêtre et n'affiche rien : tout va dans le journal
`<dossier>/journaux/client.log` (voir `config_locale` pour le dossier : `%APPDATA%\\ykw2-ap` sous Windows).
Une seule instance à la fois (verrou `<dossier>/client.verrou`).

Fichier d'état `<dossier>/etat.json` (lu par le lanceur, `archipelago/lanceur/`), réécrit atomiquement à chaque
changement et au moins toutes les 5 s : `pid`, `horodatage`, `phase` (`attente_jeu`, `jeu`, `arrete`), `etat`
(code de l'état de connexion au serveur, §5.2 : 1 non configuré, 2 connexion, 3 connecté, 4 erreur,
5 déconnecté), `etat_nom`, `message`, `erreur` (§5.2 : 1 serveur injoignable, 2 slot inconnu, 3 mot de passe
refusé, 4 version incompatible, 5 mauvais jeu, 6 autre), `serveur`, `slot`, `sauvegarde` (aucune, attente, liee,
liaison, non_liee, autre, jeu_ancien, verrous_incompatibles, boss_attente, boss_rom, boss_refuse, boss_jeu,
yokai_attente, yokai_rom, yokai_refuse, yokai_jeu),
`revision_connexion` et `source_connexion` (dernière
saisie appliquée : « lanceur » ; « jeu » dans un config.json d'une version antérieure), `mdp_defini` (booléen : un mot
de passe est connu du client), `raison_non_liee` (sauvegarde chargée non liée : pourquoi ce n'est pas une partie
neuve ; le lanceur dit alors de commencer une nouvelle partie), `session_chat` (session de ce client : l'onglet
« Discussion » du lanceur vise ses commandes, `chat_local.py`). Aucun mot de passe.
Configuration : saisie dans le lanceur seulement (config.json, surveillé ; `config_locale`).
`--quitter-avec-fichier` : le lanceur démarre le client AVANT Azahar (avec le stub GDB, Azahar attend le
débogueur pour lancer le jeu), puis écrit le PID d'Azahar dans ce fichier ; sans PID au bout de
`--delai-pid` secondes, le client s'arrête.

Mode « suivi seul » (`--suivi`, démarré par le lanceur dès que la connexion est enregistrée) : connexion au serveur
seulement, SANS le jeu (aucun paquet GDB, aucune connexion au stub, aucun check envoyé : les checks ne viennent que du
jeu) ; `checks.json`, `messages.jsonl`, `rando_yokai.json` / `rando_boss.json` sont tenus à jour. Le lanceur pilote ce
même client par `client_demande.json` (`{nonce, action, fichier_pid, port}`, chaque nonce traité une fois, recopié
dans `etat.json` `demande` ; refus dans `refus`) : `jouer` attache le jeu (attente du stub GDB, puis du PID d'Azahar
dans `fichier_pid` ; Azahar fermé : retour au suivi seul, sans reconnexion au serveur), `arreter` arrête le client
(refusé tant que le jeu est attaché). Le client de suivi s'arrête quand le lanceur se ferme (PID lu dans
`lanceur.pid`, sinon `--lanceur-pid`), sauf si le jeu est attaché : il s'arrête alors à la fermeture d'Azahar.
`etat.json` : `phase` `suivi` (jeu non attaché), `mode` (`suivi` / `jeu`), `demande`, `refus`, `azahar_pid`.
Bibliothèque standard seulement.
"""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import logging
import logging.handlers
import os
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import boite_protocole as bp  # noqa: E402
from config_locale import StockageConfig  # noqa: E402
from gdb import PontGdb  # noqa: E402
from synchro import Synchro  # noqa: E402

log = logging.getLogger("ykw2ap")


def configurer_journal(dossier: Path, console: bool, niveau: int = logging.INFO) -> Path:
    dossier.mkdir(parents=True, exist_ok=True)
    fichier = dossier / "client.log"
    h = logging.handlers.RotatingFileHandler(fichier, maxBytes=1 << 20, backupCount=3, encoding="utf-8")
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(name)s : %(message)s"))
    racine = logging.getLogger("ykw2ap")
    racine.setLevel(niveau)
    racine.addHandler(h)
    if console and sys.stderr is not None:
        c = logging.StreamHandler(sys.stderr)
        c.setFormatter(logging.Formatter("%(asctime)s %(message)s", "%H:%M:%S"))
        racine.addHandler(c)
    return fichier


class Verrou:
    """Verrou d'instance unique (fichier verrouillé tant que le client tourne)."""

    def __init__(self, fichier: Path):
        self.fichier = fichier
        self._f = None

    def prendre(self) -> bool:
        self.fichier.parent.mkdir(parents=True, exist_ok=True)
        f = open(self.fichier, "a+b")                     # noqa: SIM115 (gardé ouvert)
        try:
            if os.name == "nt":
                import msvcrt
                f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            f.close()
            return False
        self._f = f
        return True

    def rendre(self) -> None:
        if self._f is not None:
            with contextlib.suppress(OSError):
                self._f.close()
            self._f = None


def processus_vivant(pid: int) -> bool:
    if os.name == "nt":
        import ctypes
        k = ctypes.windll.kernel32
        h = k.OpenProcess(0x00100000 | 0x1000, False, pid)     # SYNCHRONIZE | QUERY_LIMITED_INFORMATION
        if not h:
            return False
        try:
            return k.WaitForSingleObject(h, 0) == 0x102            # WAIT_TIMEOUT : toujours en vie
        finally:
            k.CloseHandle(h)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


async def surveiller(pid: int, sync: Synchro, intervalle: float = 2.0) -> None:
    while processus_vivant(pid):
        await asyncio.sleep(intervalle)
    log.info("Azahar (processus %d) s'est terminé : arrêt du client", pid)
    sync.arreter()


def lire_pid(fichier: Path) -> int | None:
    try:
        v = int(fichier.read_text(encoding="ascii").strip())
    except (OSError, ValueError):
        return None
    return v if v > 0 else None


async def surveiller_fichier(fichier: Path, sync: Synchro, delai: float = 120.0, intervalle: float = 0.25) -> None:
    """Attend le PID d'Azahar dans `fichier` (écrit par le lanceur), puis le surveille."""
    debut = time.monotonic()
    while (pid := lire_pid(fichier)) is None:
        if time.monotonic() - debut >= delai:
            log.info("Aucun PID d'Azahar dans %s après %.0f s : arrêt du client", fichier, delai)
            sync.arreter()
            return
        await asyncio.sleep(intervalle)
    log.info("Azahar suivi : processus %d", pid)
    await surveiller(pid, sync)


def _abandon(fichier: Path) -> bool:
    try:
        return fichier.read_text(encoding="ascii").strip() == "0"
    except (OSError, ValueError):
        return False


FICHIER_DEMANDE = "client_demande.json"  # écrit par le lanceur (mode suivi) : {nonce, action, fichier_pid, port}
FICHIER_LANCEUR = "lanceur.pid"           # PID du lanceur ouvert (écrit par le lanceur, effacé à sa fermeture)


class Pilote:
    """Mode suivi seul : demandes du lanceur (`client_demande.json`) et vie du lanceur. Fichiers locaux seulement."""

    def __init__(self, dossier: Path, sync: Synchro, lanceur_pid: int | None = None, delai_pid: float = 120.0,
                 intervalle: float = 0.25):
        self.dossier, self.sync, self.lanceur_pid = dossier, sync, lanceur_pid
        self.delai_pid, self.intervalle = delai_pid, intervalle
        self.etat: FichierEtat | None = None
        self.refus = ""
        self.azahar_pid: int | None = None
        self._tache_jeu: asyncio.Task | None = None
        d = self.lire_demande()
        self.demande_traitee = str(d.get("nonce", "")) if d else ""     # demande antérieure au démarrage : ignorée

    def lire_demande(self) -> dict | None:
        try:
            d = json.loads((self.dossier / FICHIER_DEMANDE).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return d if isinstance(d, dict) and d.get("nonce") else None

    def lanceur_vivant(self) -> bool:
        pid = lire_pid(self.dossier / FICHIER_LANCEUR) or self.lanceur_pid
        return pid is None or processus_vivant(pid)

    async def boucle(self) -> None:
        while not self.sync._arret.is_set():
            d = self.lire_demande()
            if d is not None and str(d["nonce"]) != self.demande_traitee:
                await self.traiter(d)
            if not self.sync.jeu_attache and not self.lanceur_vivant():
                log.info("Lanceur fermé : arrêt du client de suivi")
                self.sync.arreter()
                return
            await asyncio.sleep(self.intervalle)

    async def traiter(self, d: dict) -> None:
        action = str(d.get("action", ""))
        self.refus = ""
        if action == "jouer":
            if self.sync.jeu_attache:
                self.refus = "jeu_deja_attache"
            else:
                port = d.get("port")
                if isinstance(port, int) and 0 < port < 65536 and not self.sync.pont.connecte:
                    self.sync.pont.port = port
                fichier = Path(d["fichier_pid"]) if d.get("fichier_pid") else self.dossier / "azahar.pid"
                self.azahar_pid = None
                self.sync.attacher_jeu()
                self._tache_jeu = asyncio.create_task(self.suivre_jeu(fichier))
        elif action == "arreter":
            if self.sync.jeu_attache:
                self.refus = "jeu_attache"
            else:
                log.info("Arrêt demandé par le lanceur (« Déconnecter »)")
                self.sync.arreter()
        else:
            self.refus = "action_inconnue"
        if self.refus:
            log.info("Demande du lanceur « %s » refusée : %s", action, self.refus)
        self.demande_traitee = str(d["nonce"])
        if self.etat is not None:
            self.etat.ecrire(force=True)

    async def suivre_jeu(self, fichier: Path) -> None:
        """PID d'Azahar attendu dans `fichier`, puis suivi ; Azahar fermé (ou jamais lancé) : retour au suivi seul, ou
        arrêt si le lanceur est fermé."""
        debut = time.monotonic()
        while (pid := lire_pid(fichier)) is None:
            if _abandon(fichier):                     # « 0 » : Azahar n'a pas pu être lancé
                log.info("Lancement d'Azahar abandonné par le lanceur : retour au suivi seul")
                break
            if time.monotonic() - debut >= self.delai_pid:
                log.info("Aucun PID d'Azahar dans %s après %.0f s : retour au suivi seul", fichier, self.delai_pid)
                break
            await asyncio.sleep(self.intervalle)
        if pid is not None:
            self.azahar_pid = pid
            log.info("Azahar suivi : processus %d", pid)
            while processus_vivant(pid):
                await asyncio.sleep(1.0)
            log.info("Azahar (processus %d) s'est terminé : retour au suivi seul", pid)
        self.azahar_pid = None
        await self.sync.detacher_jeu()
        if not self.lanceur_vivant():
            log.info("Lanceur fermé : arrêt du client")
            self.sync.arreter()
        if self.etat is not None:
            self.etat.ecrire(force=True)


class FichierEtat:
    """`etat.json` pour le lanceur (voir la docstring du module). Écriture atomique ; erreurs ignorées."""

    def __init__(self, fichier: Path, sync: Synchro, pont: PontGdb, rafraichir: float = 5.0,
                 pilote: Pilote | None = None):
        self.fichier, self.sync, self.pont, self.rafraichir = fichier, sync, pont, rafraichir
        self.pilote = pilote
        self._dernier: dict | None = None
        self._t = 0.0

    def contenu(self, phase: str | None = None) -> dict:
        if phase is None:
            phase = "suivi" if not self.sync.jeu_attache else ("jeu" if self.pont.connecte else "attente_jeu")
        d = {"format": 1, "pid": os.getpid(), "phase": phase,
             "mode": "jeu" if self.sync.jeu_attache else "suivi",
             "etat": 0, "etat_nom": "", "message": "", "serveur": self.sync.config.serveur,
             "slot": self.sync.config.slot, "sauvegarde": self.sync.sauvegarde, "erreur": 0,
             "revision_connexion": self.sync.config.revision_connexion,
             "source_connexion": self.sync.config.source_connexion,
             "mdp_defini": bool(self.sync.config.mot_de_passe),
             "raison_non_liee": self.sync.raison_non_liee if self.sync.sauvegarde == "non_liee" else "",
             "session_chat": self.sync.session_chat}
        if self.pilote is not None:
            d.update(demande=self.pilote.demande_traitee, refus=self.pilote.refus, azahar_pid=self.pilote.azahar_pid)
        try:
            e = self.sync.etat_voulu()
            d["etat"], d["message"], d["erreur"] = e.etat, e.message, e.erreur
            d["etat_nom"] = bp.ETATS_CONNEXION.get(e.etat, "")
        except Exception as ex:                          # noqa: BLE001 - l'état ne doit jamais arrêter le client
            log.debug("État non calculable : %s", ex)
        return d

    def ecrire(self, phase: str | None = None, force: bool = False) -> None:
        d = self.contenu(phase)
        maintenant = time.monotonic()
        if not force and d == self._dernier and maintenant - self._t < self.rafraichir:
            return
        self._dernier, self._t = d, maintenant
        tmp = self.fichier.with_name(self.fichier.name + ".tmp")
        try:
            tmp.write_text(json.dumps(dict(d, horodatage=time.time()), ensure_ascii=False), encoding="utf-8")
            os.replace(tmp, self.fichier)
        except OSError as ex:
            log.debug("etat.json non écrit : %s", ex)

    async def boucle(self, intervalle: float = 0.5) -> None:
        while True:
            self.ecrire()
            await asyncio.sleep(intervalle)


async def executer(args: argparse.Namespace) -> int:
    stockage = StockageConfig(args.dossier)
    config = stockage.charger()
    if args.hote:
        config.hote_gdb = args.hote
    if args.port:
        config.port_gdb = args.port
    pont = PontGdb(config.hote_gdb, config.port_gdb)
    sync = Synchro(pont, stockage, config, attacher_jeu=not args.suivi)
    pilote = Pilote(stockage.dossier, sync, args.lanceur_pid, args.delai_pid) if args.suivi else None
    etat = FichierEtat(stockage.dossier / "etat.json", sync, pont, pilote=pilote)
    if pilote is not None:
        pilote.etat = etat
    etat.ecrire(force=True)
    taches = [asyncio.create_task(etat.boucle())]
    if pilote is not None:
        taches.append(asyncio.create_task(pilote.boucle()))
    elif args.quitter_avec:
        taches.append(asyncio.create_task(surveiller(args.quitter_avec, sync)))
    elif args.quitter_avec_fichier:
        taches.append(asyncio.create_task(surveiller_fichier(args.quitter_avec_fichier, sync, args.delai_pid)))
    if args.suivi:
        log.info("Client invisible démarré en suivi seul (configuration : %s ; serveur %s, slot %s) : sans le jeu, "
                 "jusqu'à « Jouer » dans le lanceur", stockage.fichier, config.serveur or "-", config.slot or "-")
    else:
        log.info("Client invisible démarré (configuration : %s ; serveur %s, slot %s) ; attente du jeu sur %s:%d",
                 stockage.fichier, config.serveur or "-", config.slot or "-", config.hote_gdb, config.port_gdb)
    try:
        await sync.executer()
    finally:
        for t in taches:
            t.cancel()
        if pilote is not None and pilote._tache_jeu is not None:
            pilote._tache_jeu.cancel()
        await pont.fermer()
        etat.ecrire("arrete", force=True)
        log.info("Client arrêté (%s)", sync.stats)
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Client Archipelago invisible de Yo-kai Watch 2")
    p.add_argument("--dossier", type=Path, help="dossier de configuration et de journaux (défaut : %%APPDATA%%\\ykw2-ap)")
    p.add_argument("--hote", help="hôte du stub GDB (défaut : 127.0.0.1)")
    p.add_argument("--port", type=int, help="port du stub GDB (défaut : 24689)")
    p.add_argument("--quitter-avec", type=int, metavar="PID", help="s'arrêter quand ce processus (Azahar) se termine")
    p.add_argument("--quitter-avec-fichier", type=Path, metavar="FICHIER",
                   help="attendre le PID d'Azahar dans ce fichier (écrit par le lanceur), puis le surveiller")
    p.add_argument("--delai-pid", type=float, default=120.0,
                   help="avec --quitter-avec-fichier ou « jouer » en suivi : attente maximale du PID d'Azahar (s)")
    p.add_argument("--suivi", action="store_true",
                   help="suivi seul : serveur Archipelago sans le jeu ; le lanceur attache le jeu sur demande")
    p.add_argument("--lanceur-pid", type=int, metavar="PID",
                   help="avec --suivi : s'arrêter à la fermeture de ce lanceur (sauf jeu attaché ; lanceur.pid prioritaire)")
    p.add_argument("--console", action="store_true", help="journal aussi sur la console")
    p.add_argument("--debug", action="store_true", help="journal détaillé")
    args = p.parse_args(argv)
    stockage = StockageConfig(args.dossier)
    fichier = configurer_journal(stockage.dossier_journaux, args.console, logging.DEBUG if args.debug else logging.INFO)
    verrou = Verrou(stockage.dossier / "client.verrou")
    if not verrou.prendre():
        log.warning("Un autre client est déjà lancé (%s) : abandon", verrou.fichier)
        return 1
    try:
        return asyncio.run(executer(args))
    except KeyboardInterrupt:
        return 0
    except Exception:                                   # pragma: no cover - journalisé pour le joueur
        log.exception("Erreur fatale du client (journal : %s)", fichier)
        return 2
    finally:
        verrou.rendre()


if __name__ == "__main__":
    sys.exit(main())
