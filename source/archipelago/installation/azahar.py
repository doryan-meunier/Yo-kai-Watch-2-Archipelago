"""Détection d'Azahar et réglage du stub GDB (tâche I3). Bibliothèque standard seulement.

    python archipelago/installation/azahar.py            # affiche ce qui est détecté (lecture seule)

- Exécutable : `%ProgramFiles%\\Azahar\\azahar.exe` (installateur officiel), `%LOCALAPPDATA%\\Programs\\Azahar`,
  ou `azahar` dans le PATH.
- Dossier utilisateur : `user/` à côté de l'exécutable s'il existe (mode portable), sinon `%APPDATA%\\Azahar`
  (Windows) ou `$XDG_DATA_HOME/azahar-emu` / `~/.local/share/azahar-emu` (Linux).
- Version : ligne « Azahar Version: 2124.3 | HEAD-54f35a7 » du journal `log/azahar_log.txt` (écrite à chaque
  lancement) ; à défaut, chaînes de version compilées dans l'exécutable (azahar.exe n'a pas de ressource de
  version Windows : recherche heuristique de « <date>Z\\0<version>\\0 »).
- Configuration : `config/qt-config.ini`, section `[Debugging]` : `use_gdbstub` (et `use_gdbstub\\default`),
  `gdbstub_port` (24689 par défaut).

`activer_stub_gdb` ne modifie le fichier QUE si l'appelant passe `accord=True` (le lanceur demande l'accord du
joueur) ; il fait d'abord une copie de sauvegarde datée, ne change que les lignes nécessaires et laisse tout le
reste du fichier octet pour octet. Azahar réécrit sa configuration en quittant : il doit être fermé.
"""
from __future__ import annotations

import datetime as _dt
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

VERSION_REFERENCE = "2124.3"          # seule version validée (archipelago/CONCEPTION.md, décisions)
PORT_GDB_DEFAUT = 24689
SECTION_DEBUG = "Debugging"


# ------------------------------------------------------------------------------------------------
# Emplacements
# ------------------------------------------------------------------------------------------------
def candidats_executable() -> list[Path]:
    out = []
    for var in ("ProgramFiles", "ProgramW6432", "ProgramFiles(x86)"):
        v = os.environ.get(var)
        if v:
            out.append(Path(v) / "Azahar" / "azahar.exe")
    v = os.environ.get("LOCALAPPDATA")
    if v:
        out.append(Path(v) / "Programs" / "Azahar" / "azahar.exe")
    for nom in ("azahar", "azahar.exe"):
        w = shutil.which(nom)
        if w:
            out.append(Path(w))
    vus, res = set(), []
    for p in out:
        k = str(p).lower()
        if k not in vus:
            vus.add(k)
            res.append(p)
    return res


def trouver_executable(candidats: list[Path] | None = None) -> Path | None:
    for p in (candidats if candidats is not None else candidats_executable()):
        if p.is_file():
            return p
    return None


def dossier_utilisateur(executable: Path | None = None) -> Path | None:
    """Dossier utilisateur d'Azahar existant (portable d'abord), ou None."""
    exe = executable if executable is not None else trouver_executable()
    if exe is not None and (exe.parent / "user").is_dir():
        return exe.parent / "user"
    cands = []
    if os.environ.get("APPDATA"):
        cands.append(Path(os.environ["APPDATA"]) / "Azahar")
    xdg = os.environ.get("XDG_DATA_HOME")
    cands.append((Path(xdg) if xdg else Path.home() / ".local" / "share") / "azahar-emu")
    for c in cands:
        if c.is_dir():
            return c
    return None


# ------------------------------------------------------------------------------------------------
# Version
# ------------------------------------------------------------------------------------------------
_RE_JOURNAL = re.compile(r"Azahar Version:\s*([^\s|]+)\s*\|\s*(\S+)")
_RE_EXE = re.compile(rb"([0-9a-f]{7,40})\x00+(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ)\x00(\d{3,5}(?:\.\d+)*)\x00")


def version_depuis_journal(dossier_util: Path) -> tuple[str, str] | None:
    """(version, révision) lues dans le journal du dernier lancement (puis l'avant-dernier)."""
    for n in ("azahar_log.txt", "azahar_log.old.txt"):
        p = dossier_util / "log" / n
        try:
            with open(p, encoding="utf-8", errors="replace") as f:
                for _, ligne in zip(range(200), f):
                    m = _RE_JOURNAL.search(ligne)
                    if m:
                        return m.group(1), m.group(2)
        except OSError:
            continue
    return None


def version_depuis_executable(exe: Path) -> tuple[str, str] | None:
    """(version, révision) : chaînes compilées dans l'exécutable (heuristique)."""
    try:
        d = exe.read_bytes()
    except OSError:
        return None
    m = _RE_EXE.search(d)
    if not m:
        return None
    return m.group(3).decode(), m.group(1).decode()


# ------------------------------------------------------------------------------------------------
# qt-config.ini
# ------------------------------------------------------------------------------------------------
@dataclass
class ReglagesGdb:
    fichier: Path
    actif: bool
    port: int


def _decouper(texte: str) -> list[str]:
    return texte.splitlines(keepends=True)


def _section(lignes: list[str], nom: str) -> tuple[int, int] | None:
    """(indice de l'en-tête, indice de fin exclu) de la section, ou None."""
    deb = None
    for i, l in enumerate(lignes):
        s = l.strip()
        if s.startswith("[") and s.endswith("]"):
            if deb is not None:
                return deb, i
            if s[1:-1] == nom:
                deb = i
    return (deb, len(lignes)) if deb is not None else None


def _valeur(lignes: list[str], sec: tuple[int, int] | None, cle: str) -> str | None:
    if sec is None:
        return None
    for l in lignes[sec[0] + 1:sec[1]]:
        k, sep, v = l.partition("=")
        if sep and k.strip() == cle:
            return v.strip().strip('"')
    return None


def fichier_config(dossier_util: Path) -> Path:
    return dossier_util / "config" / "qt-config.ini"


def lire_reglages_gdb(fichier: Path) -> ReglagesGdb:
    """Lit l'état du stub GDB (valeurs par défaut d'Azahar si absentes : inactif, port 24689)."""
    lignes = _decouper(fichier.read_text(encoding="utf-8"))
    sec = _section(lignes, SECTION_DEBUG)
    actif = (_valeur(lignes, sec, "use_gdbstub") or "false").lower() == "true"
    try:
        port = int(_valeur(lignes, sec, "gdbstub_port") or PORT_GDB_DEFAUT)
    except ValueError:
        port = PORT_GDB_DEFAUT
    return ReglagesGdb(fichier, actif, port)


def texte_avec_stub_gdb(texte: str, port: int = PORT_GDB_DEFAUT) -> str:
    """Renvoie le texte de qt-config.ini avec le stub actif sur `port` ; ne change que les lignes utiles."""
    lignes = _decouper(texte)
    fin_ligne = "\r\n" if lignes and lignes[0].endswith("\r\n") else "\n"
    voulu = {"use_gdbstub\\default": "false", "use_gdbstub": "true",
             "gdbstub_port\\default": "true" if port == PORT_GDB_DEFAUT else "false",
             "gdbstub_port": str(port)}
    sec = _section(lignes, SECTION_DEBUG)
    if sec is None:
        if lignes and not lignes[-1].endswith(("\n", "\r")):
            lignes[-1] += fin_ligne
        if lignes and lignes[-1].strip():
            lignes.append(fin_ligne)
        lignes.append(f"[{SECTION_DEBUG}]{fin_ligne}")
        lignes += [f"{k}={v}{fin_ligne}" for k, v in voulu.items()]
        return "".join(lignes)
    deb, fin = sec
    restant = dict(voulu)
    for i in range(deb + 1, fin):
        k, sep, v = lignes[i].partition("=")
        k = k.strip()
        if sep and k in restant:
            fl = lignes[i][len(lignes[i].rstrip("\r\n")):]
            if v.strip() != restant[k]:
                lignes[i] = f"{k}={restant[k]}{fl}"
            del restant[k]
    if restant:
        # insérer après la dernière ligne non vide de la section
        j = fin
        while j > deb + 1 and not lignes[j - 1].strip():
            j -= 1
        if not lignes[j - 1].endswith(("\n", "\r")):
            lignes[j - 1] += fin_ligne
        lignes[j:j] = [f"{k}={v}{fin_ligne}" for k, v in restant.items()]
    return "".join(lignes)


def activer_stub_gdb(fichier: Path, port: int = PORT_GDB_DEFAUT, *, accord: bool = False) -> Path | None:
    """Active le stub GDB dans qt-config.ini. Sans `accord=True`, lève PermissionError sans rien toucher.

    Renvoie le chemin de la copie de sauvegarde, ou None si le stub était déjà actif sur ce port (fichier
    inchangé). Azahar doit être fermé (il réécrit sa configuration en quittant)."""
    if not accord:
        raise PermissionError("Modification de la configuration d'Azahar refusée : accord du joueur requis.")
    brut = fichier.read_bytes()
    texte = brut.decode("utf-8")
    nouveau = texte_avec_stub_gdb(texte, port)
    if nouveau == texte:
        return None
    horo = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    sauvegarde = fichier.with_name(f"{fichier.name}.ykw2ap-{horo}.bak")
    shutil.copy2(fichier, sauvegarde)
    tmp = fichier.with_name(fichier.name + ".ykw2ap-tmp")
    tmp.write_bytes(nouveau.encode("utf-8"))
    os.replace(tmp, fichier)
    return sauvegarde


def processus_windows() -> list[str] | None:
    """Noms d'image (minuscules) des processus en cours, lus par l'API Toolhelp32 de Windows (~1 ms, aucun
    sous-processus) ; None si l'API n'est pas utilisable (autre système, erreur)."""
    if os.name != "nt":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class Entree(ctypes.Structure):                       # PROCESSENTRY32W
            _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD), ("th32ProcessID", wintypes.DWORD),
                        ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", wintypes.DWORD),
                        ("cntThreads", wintypes.DWORD), ("th32ParentProcessID", wintypes.DWORD),
                        ("pcPriClassBase", wintypes.LONG), ("dwFlags", wintypes.DWORD),
                        ("szExeFile", wintypes.WCHAR * 260)]

        k = ctypes.WinDLL("kernel32", use_last_error=True)
        k.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
        k.CreateToolhelp32Snapshot.argtypes = (wintypes.DWORD, wintypes.DWORD)
        for f in (k.Process32FirstW, k.Process32NextW):
            f.restype = wintypes.BOOL
            f.argtypes = (wintypes.HANDLE, ctypes.POINTER(Entree))
        k.CloseHandle.argtypes = (wintypes.HANDLE,)
        instantane = k.CreateToolhelp32Snapshot(0x00000002, 0)          # TH32CS_SNAPPROCESS
        if instantane in (None, ctypes.c_void_p(-1).value):
            return None
        try:
            e = Entree()
            e.dwSize = ctypes.sizeof(Entree)
            noms = []
            suite = k.Process32FirstW(instantane, ctypes.byref(e))
            while suite:
                noms.append(e.szExeFile.lower())
                suite = k.Process32NextW(instantane, ctypes.byref(e))
            return noms or None
        finally:
            k.CloseHandle(instantane)
    except (OSError, AttributeError, ValueError):
        return None


def azahar_en_cours() -> bool | None:
    """True si un processus azahar.exe tourne (Windows) ; None si on ne sait pas. Appelée dans le fil de la fenêtre
    du lanceur à chaque rafraîchissement : liste des processus lue directement (`processus_windows`) ; `tasklist`
    (65 à 200 ms, plus quand la machine est chargée) ne sert plus que de repli."""
    if os.name != "nt":
        return None
    noms = processus_windows()
    if noms is not None:
        return "azahar.exe" in noms
    try:
        r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq azahar.exe", "/NH", "/FO", "CSV"],
                           capture_output=True, text=True, timeout=10,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.SubprocessError):
        return None
    return "azahar.exe" in r.stdout.lower()


# ------------------------------------------------------------------------------------------------
@dataclass
class InfoAzahar:
    executable: Path | None
    dossier_utilisateur: Path | None
    portable: bool
    version: str | None
    revision: str | None
    source_version: str | None            # "journal", "executable" ou None
    reglages_gdb: ReglagesGdb | None

    @property
    def version_validee(self) -> bool:
        return self.version == VERSION_REFERENCE

    @property
    def dossier_mods(self) -> Path | None:
        return self.dossier_utilisateur / "load" / "mods" if self.dossier_utilisateur else None


def detecter(executable: Path | None = None, dossier_util: Path | None = None) -> InfoAzahar:
    """Détection complète, en lecture seule."""
    exe = executable if executable is not None else trouver_executable()
    util = dossier_util if dossier_util is not None else dossier_utilisateur(exe)
    version = revision = source = None
    if util is not None:
        v = version_depuis_journal(util)
        if v:
            version, revision, source = v[0], v[1], "journal"
    if version is None and exe is not None:
        v = version_depuis_executable(exe)
        if v:
            version, revision, source = v[0], v[1], "executable"
    reg = None
    if util is not None and fichier_config(util).is_file():
        reg = lire_reglages_gdb(fichier_config(util))
    portable = bool(exe is not None and util is not None and util == exe.parent / "user")
    return InfoAzahar(exe, util, portable, version, revision, source, reg)


def main() -> int:
    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    i = detecter()
    print(f"exécutable          : {i.executable or 'introuvable'}")
    print(f"dossier utilisateur : {i.dossier_utilisateur or 'introuvable'}" + (" (portable)" if i.portable else ""))
    print(f"version             : {i.version or 'inconnue'} {i.revision or ''} (source : {i.source_version or '-'})"
          + ("" if i.version is None or i.version_validee else f"  ATTENTION : seule la {VERSION_REFERENCE} est validée"))
    if i.reglages_gdb:
        g = i.reglages_gdb
        print(f"stub GDB            : {'actif' if g.actif else 'INACTIF'}, port {g.port} ({g.fichier})")
    else:
        print("stub GDB            : configuration introuvable")
    print(f"dossier mods        : {i.dossier_mods or '-'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
