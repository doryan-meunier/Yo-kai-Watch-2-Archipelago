"""Outil de remplacement du lanceur (`--role maj`) : la dernière étape d'une mise à jour (README du lanceur, « Mise à
jour du lanceur »).

Un exécutable ne peut pas s'écraser, et le dossier `_internal/` (Python, DLL) est verrouillé tant qu'un processus en
tourne. Le lanceur prépare donc tout dans `<dossier du lanceur>/.maj/` (`maj.py`) :

    .maj/neuf/    le nouveau paquet, complet et vérifié
    .maj/outil/   COPIE de l'exécutable et de `_internal/` en cours : c'est elle qui exécute ce module
    .maj/ancien/  créé ici : ce qui a été retiré, gardé jusqu'à la réussite

puis lance `.maj/outil/<exe> --role maj --application <dossier> --pid <lanceur> --donnees <dossier de données>` et
se ferme. Cet outil :
1. attend la fin du lanceur ;
2. échange UNE par une les entrées du paquet (`ENTREES`) : retrait vers `.maj/ancien`, puis nouvelle à sa place. Le
   dossier lui-même ne bouge pas : ce qu'il contient d'autre (une ROM posée à côté du lanceur…) n'est jamais touché,
   le nom du dossier et les raccourcis restent justes, et il n'y a pas besoin d'écrire dans le dossier parent ;
3. contrôle la nouvelle version en la lançant (`--role diagnostic`, sans fenêtre, sur un dossier de données
   temporaire) ;
4. réussite : `.maj/ancien` est effacé ; échec à n'importe quelle étape : retour arrière (chaque entrée reprend sa
   place), l'ancienne version reste celle qui marche ;
5. écrit le résultat (`maj_resultat.json` du dossier de données, montré par le lanceur à son ouverture) et relance
   le lanceur, nouveau ou ancien.

Arrêt brutal (processus tué, coupure de courant) : `.maj/echange.json`, écrit de façon atomique avant chaque renommage,
garde les entrées présentes au départ et la phase. Au lancement suivant, `avant_lanceur` confie la suite à la copie
`.maj/outil` : échange incomplet -> ancienne version ; échange complet -> contrôle : saine, la nouvelle est gardée, sinon
ancienne version. Le retour arrière se déduit des FICHIERS (renommages atomiques), il se rejoue sans risque. Si l'échange
a cassé l'exécutable du dossier au point qu'il ne démarre plus, double-cliquer sur `.maj\\outil\\<exe>` fait la même chose
(LISEZMOI). Reste impossible à rattraper : un disque qui perd des fichiers, ou `.maj/` supprimé à la main ; le zip suffit
alors (données du joueur dans `%APPDATA%`, jamais ici).

Les données du joueur ne sont jamais touchées : seul `maj_resultat.json` et `journaux/maj.log` y sont écrits.
Bibliothèque standard seulement, aucun import du reste du mod.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Callable

NOM_EXE = "Lanceur Yo-kai Watch 2 Archipelago.exe"
DOSSIER_MAJ = ".maj"
INTERNE = "_internal"
# tout ce qui appartient au paquet exe, à la racine de son dossier (`fabriquer_exe.py`, vérifié par un test)
ENTREES = (INTERNE, "apworld", "patch", "zakuro", "LISEZMOI.txt", "version.json", "exe.json", NOM_EXE)
FICHIER_RESULTAT = "maj_resultat.json"
FICHIER_MARQUE = "en_cours.pid"
FICHIER_JOURNAL = "echange.json"        # état de l'échange (reprise après un arrêt brutal)
FORMAT_JOURNAL = 1
ATTENTE_LANCEUR = 60.0                  # s : fermeture du lanceur
ATTENTE_VERROU = 30.0                   # s : client de suivi qui s'arrête, antivirus qui lit un fichier neuf…
ATTENTE_SANTE = 120.0                   # s : `--role diagnostic` de la nouvelle version
PAUSE_REPRISE = 600.0                   # s : après un retour arrière impossible, pas de reprise automatique


class Echec(Exception):
    """Échec de l'échange ; `raison` : suite de la clé de texte `maj_echec_<raison>`."""

    def __init__(self, raison: str, detail: str = ""):
        super().__init__(f"{raison} {detail}".strip())
        self.raison, self.detail = raison, detail


def env_independant() -> dict[str, str]:
    """Environnement d'un exécutable PyInstaller lancé depuis un AUTRE dossier : sans cette variable (documentée par
    PyInstaller), l'enfant reprendrait pour lui les chemins hérités du processus gelé qui le lance."""
    env = dict(os.environ)
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    return env


def lancer_detache(cmd: list[str]) -> subprocess.Popen:
    """Processus qui survit à son parent, sans console, hors du dossier à échanger."""
    drapeaux = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    return subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            cwd=tempfile.gettempdir(), env=env_independant(), close_fds=True,
                            creationflags=drapeaux)


# ------------------------------------------------------------------------------------------------ processus
def pid_vivant(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name != "nt":
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        return True
    import ctypes
    from ctypes import wintypes
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.OpenProcess.restype = wintypes.HANDLE
    k.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    k.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    k.CloseHandle.argtypes = (wintypes.HANDLE,)
    h = k.OpenProcess(0x00100000, False, pid)            # SYNCHRONIZE
    if not h:
        return False
    try:
        return k.WaitForSingleObject(h, 0) == 0x102      # WAIT_TIMEOUT : toujours là
    finally:
        k.CloseHandle(h)


def chemin_processus(pid: int) -> str | None:
    """Chemin de l'exécutable d'un processus vivant, ou None."""
    if pid <= 0 or os.name != "nt":
        return None
    import ctypes
    from ctypes import wintypes
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.OpenProcess.restype = wintypes.HANDLE
    k.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    k.QueryFullProcessImageNameW.argtypes = (wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                                             ctypes.POINTER(wintypes.DWORD))
    k.CloseHandle.argtypes = (wintypes.HANDLE,)
    h = k.OpenProcess(0x1000, False, pid)                # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return None
    try:
        n = wintypes.DWORD(32768)
        tampon = ctypes.create_unicode_buffer(n.value)
        return tampon.value if k.QueryFullProcessImageNameW(h, 0, tampon, ctypes.byref(n)) else None
    finally:
        k.CloseHandle(h)


def outil_actif(d: Path) -> bool:
    """Un AUTRE outil travaille-t-il dans `.maj/` ? Le PID du marqueur doit être celui d'un processus lancé depuis
    `.maj/outil` : celui d'un outil tué peut avoir été réutilisé par n'importe quel programme."""
    try:
        pid = int((d / FICHIER_MARQUE).read_text(encoding="ascii").strip())
    except (OSError, ValueError):
        return False
    if pid == os.getpid():
        return False
    c = chemin_processus(pid)
    return c is not None and os.path.normcase(c) == os.path.normcase(str(d.resolve() / "outil" / NOM_EXE))


def attendre_fin(pid: int, attente: float = ATTENTE_LANCEUR) -> None:
    fin = time.monotonic() + attente
    while pid_vivant(pid):
        if time.monotonic() >= fin:
            raise Echec("lanceur_ouvert")
        time.sleep(0.1)


# ------------------------------------------------------------------------------------------------ échange
def marquer(d: Path) -> None:
    try:
        (d / FICHIER_MARQUE).write_text(str(os.getpid()), encoding="ascii")
    except OSError:
        pass


def deplacer(a: Path, b: Path, attente: float = ATTENTE_VERROU, renommer: Callable = os.replace) -> None:
    """Renommage qui patiente : le client de suivi met quelques secondes à s'arrêter et un antivirus peut lire un
    fichier neuf (accès refusé passager)."""
    fin = time.monotonic() + attente
    while True:
        try:
            renommer(a, b)
            return
        except PermissionError:
            if time.monotonic() >= fin:
                raise
            time.sleep(0.2)


def ecrire_journal(d: Path, journal_: dict) -> None:
    """`.maj/echange.json`, atomique : le fichier est toujours entier, ancien ou nouveau."""
    t = d / (FICHIER_JOURNAL + ".tmp")
    t.write_text(json.dumps(journal_, ensure_ascii=False), encoding="utf-8")
    os.replace(t, d / FICHIER_JOURNAL)


def lire_journal(d: Path) -> dict | None:
    try:
        j = json.loads((d / FICHIER_JOURNAL).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return j if isinstance(j, dict) and j.get("format") == FORMAT_JOURNAL else None


def retour_arriere(app: Path, neuf: Path, ancien: Path, retirees: list[str], attente: float = ATTENTE_VERROU,
                   renommer: Callable = os.replace) -> None:
    """Remet l'ancienne version, D'APRÈS LES FICHIERS, donc depuis n'importe quel point de l'échange (les renommages sont
    atomiques) et autant de fois qu'il le faut : `retirees` = entrées présentes avant l'échange. Une entrée dans `ancien`
    a été retirée (ce qui est à sa place est nouveau) ; une entrée absente de `retirees` n'existait pas (ce qui est à sa
    place est nouveau) ; sinon elle n'a pas encore été touchée."""
    for e in reversed(ENTREES):
        if (ancien / e).exists():
            if (app / e).exists():
                deplacer(app / e, neuf / e, attente, renommer)
            deplacer(ancien / e, app / e, attente, renommer)
        elif e not in retirees and (app / e).exists():
            deplacer(app / e, neuf / e, attente, renommer)


def echanger(app: Path, neuf: Path, ancien: Path, jr: dict, attente: float = ATTENTE_VERROU,
             renommer: Callable = os.replace) -> None:
    """Échange les entrées de `ENTREES`, journal à jour AVANT chaque renommage. Échec : tout est remis en place, puis
    `Echec`. Processus tué : `reprendre` finit le travail."""
    d = ancien.parent
    ancien.mkdir(parents=True, exist_ok=True)
    jr.update(phase="echange", retirees=[e for e in ENTREES if (app / e).exists()])
    ecrire_journal(d, jr)
    try:
        for e in ENTREES:
            if (app / e).exists():
                jr["etape"] = [e, "retrait"]
                ecrire_journal(d, jr)
                deplacer(app / e, ancien / e, attente, renommer)
            if (neuf / e).exists():
                jr["etape"] = [e, "pose"]
                ecrire_journal(d, jr)
                deplacer(neuf / e, app / e, attente, renommer)
    except OSError as x:
        annuler(app, neuf, ancien, jr, "fichiers_ouverts", str(x), attente, renommer)
    jr.update(phase="controle", etape=None)
    ecrire_journal(d, jr)


def annuler(app: Path, neuf: Path, ancien: Path, jr: dict, raison: str, detail: str, attente: float,
            renommer: Callable) -> None:
    """Retour arrière, puis `Echec(raison)` ; impossible : `Echec("retour_impossible")`, journal et `ancien` gardés,
    avec l'heure de l'échec (`avant_lanceur` laisse alors la fenêtre s'ouvrir ; une reprise pourra réessayer plus tard)."""
    jr.update(phase="retour", etape=None)
    try:
        ecrire_journal(ancien.parent, jr)
        retour_arriere(app, neuf, ancien, jr["retirees"], attente, renommer)
    except OSError as y:
        jr["echec_reprise"] = time.time()
        try:
            ecrire_journal(ancien.parent, jr)
        except OSError:
            pass
        raise Echec("retour_impossible", f"{detail} ; {y}") from y
    raise Echec(raison, detail)


def sante(app: Path, travail: Path, attente: float = ATTENTE_SANTE) -> str | None:
    """La version en place démarre-t-elle ? `--role diagnostic` : aucune fenêtre, dossier de données temporaire.
    Rend None si oui, sinon la raison."""
    travail.mkdir(parents=True, exist_ok=True)
    sortie = travail / "diagnostic.txt"
    cmd = [str(app / NOM_EXE), "--role", "diagnostic", "--sortie", str(sortie), "--dossier", str(travail / "donnees")]
    try:
        r = subprocess.run(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           cwd=tempfile.gettempdir(), env=env_independant(), timeout=attente)
    except (OSError, subprocess.SubprocessError) as e:
        return repr(e)
    try:
        texte = sortie.read_text(encoding="utf-8")
    except OSError:
        texte = ""
    if r.returncode != 0 or "exécutable empaqueté" not in texte:
        return f"code {r.returncode}"
    return None


# ------------------------------------------------------------------------------------------------ résultat
def journal(donnees: Path, texte: str) -> None:
    try:
        d = donnees / "journaux"
        d.mkdir(parents=True, exist_ok=True)
        with open(d / "maj.log", "a", encoding="utf-8") as f:
            f.write(f"{datetime.datetime.now().isoformat(timespec='seconds')} {texte}\n")
    except OSError:
        pass


def ecrire_resultat(donnees: Path, resultat: dict) -> None:
    try:
        donnees.mkdir(parents=True, exist_ok=True)
        t = donnees / (FICHIER_RESULTAT + ".tmp")
        t.write_text(json.dumps(resultat, ensure_ascii=False), encoding="utf-8")
        os.replace(t, donnees / FICHIER_RESULTAT)
    except OSError as e:
        journal(donnees, f"résultat non écrit : {e!r}")


def lire_resultat(donnees: Path) -> dict | None:
    """Résultat de la dernière mise à jour, une seule fois (le fichier est effacé)."""
    p = donnees / FICHIER_RESULTAT
    try:
        r = json.loads(p.read_text(encoding="utf-8"))
        p.unlink()
    except (OSError, ValueError):
        return None
    return r if isinstance(r, dict) else None


def version_de(dossier: Path) -> str:
    try:
        return str(json.loads((dossier / "version.json").read_text(encoding="utf-8")).get("version", "?"))
    except (OSError, ValueError, AttributeError):
        return "?"


# ------------------------------------------------------------------------------------------------ déroulement
def terminer(d: Path, jr: dict | None) -> None:
    """Fin du travail, réussi ou annulé. Le journal part EN DERNIER : tué ici, tout se refait. `outil/` reste (il
    s'exécute peut-être) : effacé par le prochain lanceur (`maj.nettoyer_restes`)."""
    if jr is not None:
        jr["phase"] = "fin"
        ecrire_journal(d, jr)
    for x in ("ancien", "neuf", "sante"):
        shutil.rmtree(d / x, ignore_errors=True)
    (d / FICHIER_JOURNAL).unlink(missing_ok=True)


def mettre_a_jour(app: Path, donnees: Path, pid: int, *, controle: Callable[[Path, Path], str | None] | None = None,
                  attente_lanceur: float = ATTENTE_LANCEUR, attente_verrou: float = ATTENTE_VERROU,
                  renommer: Callable = os.replace) -> dict:
    """Étapes 1 à 4 du module ; rend le résultat (aucune exception ordinaire ne sort)."""
    controle = controle or sante
    d = app / DOSSIER_MAJ
    neuf, ancien = d / "neuf", d / "ancien"
    avant = version_de(app)
    attendue = version_de(neuf)
    journal(donnees, f"mise à jour {avant} -> {attendue} dans {app}")
    marquer(d)
    jr = {"format": FORMAT_JOURNAL, "donnees": str(donnees), "version": avant, "attendue": attendue, "phase": "attente",
          "retirees": [], "etape": None}
    try:
        attendre_fin(pid, attente_lanceur)
        echanger(app, neuf, ancien, jr, attente_verrou, renommer)
        raison = controle(app, d / "sante")
        if raison is not None:
            journal(donnees, f"contrôle de la nouvelle version : {raison}")
            annuler(app, neuf, ancien, jr, "controle", raison, attente_verrou, renommer)
    except Echec as e:
        journal(donnees, f"ÉCHEC : {e}")
        if e.raison != "retour_impossible":          # sinon journal et `.maj/ancien` : une reprise pourra réessayer
            terminer(d, None)
        return {"ok": False, "raison": e.raison, "detail": e.detail, "version": avant, "attendue": attendue}
    except Exception as e:                           # noqa: BLE001 - un bug ici ne doit pas laisser le joueur sans rien
        journal(donnees, f"ERREUR : {e!r}")
        if jr["phase"] == "attente":
            terminer(d, None)
            return {"ok": False, "raison": "inattendue", "detail": repr(e), "version": avant, "attendue": attendue}
        try:
            annuler(app, neuf, ancien, jr, "inattendue", repr(e), attente_verrou, renommer)
        except Echec as x:
            if x.raison != "retour_impossible":
                terminer(d, None)
            return {"ok": False, "raison": x.raison, "detail": x.detail, "version": avant, "attendue": attendue}
    terminer(d, jr)
    journal(donnees, f"réussie : {version_de(app)}")
    return {"ok": True, "version": version_de(app), "avant": avant}


def reprendre(app: Path, *, controle: Callable[[Path, Path], str | None] | None = None,
              attente_verrou: float = ATTENTE_VERROU, renommer: Callable = os.replace) -> dict | None:
    """Finit une mise à jour interrompue (processus tué, coupure), d'après le journal ; None s'il n'y en a pas.
    `controle` : échange complet, à contrôler : saine, elle est gardée ; sinon, ou échange incomplet : ancienne version."""
    d = app / DOSSIER_MAJ
    jr = lire_journal(d)
    if jr is None:
        return None
    marquer(d)
    donnees = Path(jr.get("donnees") or tempfile.gettempdir())
    neuf, ancien = d / "neuf", d / "ancien"
    phase, avant, attendue = jr.get("phase"), jr.get("version", "?"), jr.get("attendue", "?")
    journal(donnees, f"reprise d'une mise à jour interrompue (phase {phase}, {avant} -> {attendue})")
    if phase in ("controle", "fin"):
        raison = None if phase == "fin" else (controle or sante)(app, d / "sante")
        if raison is None:
            terminer(d, jr)
            journal(donnees, f"reprise : version gardée : {version_de(app)}")
            return {"ok": True, "version": version_de(app), "avant": avant}
        journal(donnees, f"reprise : contrôle : {raison}")
    try:
        annuler(app, neuf, ancien, jr, "interrompue", str(phase), attente_verrou, renommer)
    except Echec as e:
        journal(donnees, f"reprise : {e}")
        if e.raison != "retour_impossible":
            terminer(d, None)
        return {"ok": False, "raison": e.raison, "detail": e.detail, "version": version_de(app), "attendue": attendue}
    return None                                      # jamais atteint : `annuler` lève toujours


def relancer(app: Path, donnees: Path) -> int:
    try:
        lancer_detache([str(app / NOM_EXE)])
    except OSError as e:
        journal(donnees, f"relance impossible : {e!r}")
        return 1
    return 0


def reprise_et_relance(app: Path, sans_relance: bool = False) -> int:
    """Reprise, résultat pour le prochain lanceur, relance si l'exécutable est là, y compris après un retour arrière
    impossible : `echec_reprise` fait alors ouvrir la fenêtre, qui montre le résultat, au lieu de reboucler."""
    jr = lire_journal(app / DOSSIER_MAJ)
    donnees = Path((jr or {}).get("donnees") or tempfile.gettempdir())
    r = reprendre(app)
    if r is not None:
        ecrire_resultat(donnees, r)
    if sans_relance or not (app / NOM_EXE).is_file():
        return 0 if r is None or r["ok"] else 1
    return relancer(app, donnees) or (0 if r is None or r["ok"] else 1)


def avant_lanceur(exe: Path | None = None, gele: bool | None = None, lancer: Callable = None,
                  actif: Callable[[Path], bool] = outil_actif, maintenant: float | None = None) -> int | None:
    """Tout début du rôle lanceur. Rend un code de sortie si la fenêtre ne doit PAS s'ouvrir, sinon None.
    - lancé depuis `.maj/outil` (double-clic de secours : LISEZMOI) : reprise ici même ;
    - journal présent à côté de l'exécutable : mise à jour interrompue : la copie `.maj/outil` la finit (nous tenons
      `_internal/`), puis rouvre le lanceur ;
    - dans les deux cas, rien si un autre outil y travaille déjà.
    Après un retour arrière impossible, aucune reprise automatique pendant `PAUSE_REPRISE` : sans cela, fichier verrouillé
    = lanceur et outil qui se relancent sans fin, sans fenêtre ni message. La fenêtre s'ouvre donc et montre l'échec ; le
    lancement suivant, une fois la pause passée (après un redémarrage, par exemple), réessaie. Le double-clic de secours
    réessaie à tout moment."""
    gele = bool(getattr(sys, "frozen", False)) if gele is None else gele
    if not gele:
        return None
    exe = Path(sys.executable).resolve() if exe is None else exe
    if exe.parent.name == "outil" and exe.parent.parent.name == DOSSIER_MAJ:
        return 0 if actif(exe.parent.parent) else reprise_et_relance(exe.parents[2])
    d = exe.parent / DOSSIER_MAJ
    if not (d / FICHIER_JOURNAL).is_file():
        return None
    if actif(d):
        return 0                                     # il rouvrira le lanceur
    echec = (lire_journal(d) or {}).get("echec_reprise")
    ecart = (time.time() if maintenant is None else maintenant) - echec if isinstance(echec, (int, float)) else None
    if ecart is not None and 0 <= ecart < PAUSE_REPRISE:
        return None
    outil = d / "outil" / NOM_EXE
    if not outil.is_file():
        return None
    try:
        (lancer or lancer_detache)([str(outil), "--role", "maj", "--reprendre", "--application", str(exe.parent),
                                    "--pid", str(os.getpid())])
    except OSError:
        return None
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="--role maj", description="Remplace le lanceur par la version préparée")
    p.add_argument("--application", type=Path, required=True)
    p.add_argument("--donnees", type=Path)
    p.add_argument("--pid", type=int, default=0)
    p.add_argument("--reprendre", action="store_true", help="finir une mise à jour interrompue")
    p.add_argument("--sans-relance", action="store_true", help="essais : ne pas rouvrir le lanceur")
    a = p.parse_args(argv)
    if a.reprendre:
        try:
            attendre_fin(a.pid)
        except Echec:
            return 1
        return reprise_et_relance(a.application, a.sans_relance)
    if a.donnees is None:
        p.error("--donnees exigé")
    r = mettre_a_jour(a.application, a.donnees, a.pid)
    ecrire_resultat(a.donnees, r)
    if not a.sans_relance and relancer(a.application, a.donnees):
        return 1
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
