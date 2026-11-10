"""Zakuro intégré : l'émulateur fourni avec le lanceur (jeu recompilé en code PC chez le joueur).

Zakuro (https://github.com/fearkov/zakuro, licence MIT) exécute le jeu recompilé à l'avance par 3dsrecomp. Le
projet en livre une version adaptée (`tools/zakuro/`, `docs/systemes/version_pc.md`) qui ajoute :
- `--gdb <port>` : stub GDB minimal (lectures / écritures de mémoire) ; le client se connecte comme à Azahar ;
- `--recompile` : recompilation du jeu AVEC le mod du dossier de données, sans fenêtre (`progress N …`) ;
- `svcOpenProcess` / `svcControlProcessMemory`, utilisés par le chargeur de zone d'extension du mod.

Dossier de données propre au lanceur : `<dossier du lanceur>/zakuro` (`--data`) : mods dans
`mods/00040000001B2900/` (même disposition qu'Azahar, même installation), sauvegardes dans `user/savedata/…`.
Le code recompilé (C puis DLL, `%APPDATA%/3dsrecomp/<titre>.dll`) est produit chez le joueur, jamais distribué.
Une recompilation est nécessaire après chaque installation ou mise à jour du mod (`a_recompiler`). Depuis
`ap/v3-zakuro-rapide` (patch 0002 de 3dsrecomp, `docs/systemes/version_pc.md` §5), elle est incrémentale : ~4-5 min la
première fois (24 cœurs), puis seuls les fichiers C qui changent sont recompilés (~12-20 s pour un petit changement
du mod) ; les objets sont gardés par 3dsrecomp dans `%LOCALAPPDATA%/3dsrecomp/<titre>` (cache à lui, pas le nôtre).

Bibliothèque standard seulement ; tout ce qui touche au système est injectable (tests).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

NOM = "zakuro"
EXE = "zakuro.exe" if os.name == "nt" else "zakuro"
TITLE_ID = "00040000001B2900"
MARQUEUR = "recompilation.json"          # dans le dossier de données : ce qui a été recompilé
_RE_PROGRES = re.compile(r"^progress (\d+)")


class ErreurZakuro(Exception):
    pass


def candidats_executable(dossier_application: Path | None = None, racine_paquet: Path | None = None) -> list[Path]:
    """Où chercher `zakuro.exe` : variable YKW2AP_ZAKURO (fichier), puis `zakuro/` du paquet (à côté de l'exécutable
    empaqueté, ou du dossier `archipelago/` du paquet `.pyw`). Pas `build/zakuro` du dépôt : en développement, poser
    YKW2AP_ZAKURO (les tests ne doivent pas changer d'émulateur selon ce qui est construit)."""
    c = []
    if os.environ.get("YKW2AP_ZAKURO"):
        c.append(Path(os.environ["YKW2AP_ZAKURO"]))
    for d in (dossier_application, racine_paquet):
        if d is not None:
            c.append(Path(d) / NOM / EXE)
    return c


def trouver_executable(candidats: list[Path]) -> Path | None:
    for p in candidats:
        if p.is_file():
            return p
    return None


def dossier_donnees(dossier_lanceur: Path) -> Path:
    return Path(dossier_lanceur) / NOM


def dossier_mods(dossier_lanceur: Path) -> Path:
    """Équivalent du `load/mods` d'Azahar (le dossier du titre est en dessous, `installer.dossier_titre`)."""
    return dossier_donnees(dossier_lanceur) / "mods"


def dll_recompilee() -> Path | None:
    """Emplacement où 3dsrecomp installe le code recompilé et où Zakuro le cherche (Windows : %APPDATA%)."""
    if os.name == "nt":
        base = os.environ.get("APPDATA")
        return Path(base) / "3dsrecomp" / f"{TITLE_ID}.dll" if base else None
    base = os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share")
    return Path(base) / "3dsrecomp" / f"{TITLE_ID}.so"


def _sha1(p: Path) -> str | None:
    try:
        return hashlib.sha1(p.read_bytes()).hexdigest()
    except OSError:
        return None


def empreinte(dossier_lanceur: Path, executable: Path | None) -> dict:
    """Ce dont dépend le code recompilé : code et exheader du mod installé, et la version de Zakuro (taille et date de
    l'exécutable : une nouvelle version peut changer le générateur de code)."""
    titre = dossier_mods(dossier_lanceur) / TITLE_ID
    e = {"code.bin": _sha1(titre / "code.bin"), "exheader.bin": _sha1(titre / "exheader.bin")}
    if executable is not None:
        try:
            st = Path(executable).stat()
            e["zakuro"] = f"{st.st_size}:{int(st.st_mtime)}"
        except OSError:
            e["zakuro"] = None
    return e


def a_recompiler(dossier_lanceur: Path, executable: Path | None, dll: Path | None = None) -> bool:
    """Vrai si le code recompilé manque ou ne correspond plus au mod installé (ou à cette version de Zakuro)."""
    dll = dll if dll is not None else dll_recompilee()
    if dll is None or not dll.is_file():
        return True
    try:
        fait = json.loads((dossier_donnees(dossier_lanceur) / MARQUEUR).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return True
    return fait != empreinte(dossier_lanceur, executable)


def commande_recompilation(executable: Path, rom: Path, dossier_lanceur: Path) -> list[str]:
    return [str(executable), "--data", str(dossier_donnees(dossier_lanceur)), "--recompile", str(rom)]


def commande_jeu(executable: Path, rom: Path, dossier_lanceur: Path, port: int) -> list[str]:
    return [str(executable), "--data", str(dossier_donnees(dossier_lanceur)), "--gdb", str(port), str(rom)]


def options_sans_console() -> dict:
    if os.name == "nt":
        return {"creationflags": subprocess.CREATE_NO_WINDOW}
    return {}


def recompiler(executable: Path, rom: Path, dossier_lanceur: Path, *,
               progression: Callable[[int, str], None] | None = None,
               lancer: Callable[..., subprocess.Popen] | None = None) -> None:
    """`zakuro --recompile` (télécharge d'abord Zig, ~100 Mo, si l'ordinateur n'a pas de compilateur C), avec la
    progression lue sur sa sortie ; écrit le marqueur en cas de succès. Lève ErreurZakuro sinon."""
    donnees = dossier_donnees(dossier_lanceur)
    donnees.mkdir(parents=True, exist_ok=True)
    (donnees / MARQUEUR).unlink(missing_ok=True)
    cmd = commande_recompilation(executable, rom, dossier_lanceur)
    lancer = lancer or (lambda c: subprocess.Popen(c, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                                   stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                                                   errors="replace", **options_sans_console()))
    try:
        p = lancer(cmd)
    except OSError as e:
        raise ErreurZakuro(f"Zakuro n'a pas pu être lancé : {e}") from e
    dernieres: list[str] = []
    for ligne in p.stdout:
        ligne = ligne.rstrip()
        if not ligne:
            continue
        dernieres = (dernieres + [ligne])[-20:]
        m = _RE_PROGRES.match(ligne)
        if m and progression is not None:
            progression(int(m.group(1)), ligne[m.end():].strip())
    code = p.wait()
    if code != 0:
        detail = next((x for x in reversed(dernieres) if x.startswith("failed") or "zakuro:" in x),
                      dernieres[-1] if dernieres else f"code {code}")
        raise ErreurZakuro(f"recompilation échouée : {detail}")
    (donnees / MARQUEUR).write_text(json.dumps(empreinte(dossier_lanceur, executable), indent=1), encoding="utf-8")


def en_cours(noms_processus: Callable[[], list[str] | None] | None = None) -> bool | None:
    """Un Zakuro tourne-t-il ? None si on ne sait pas (autre système)."""
    if noms_processus is None:
        from installation import azahar as az
        noms_processus = az.processus_windows
    noms = noms_processus()
    if noms is None:
        return None
    return EXE.lower() in noms


@dataclass
class InfoZakuro:
    executable: Path | None
    dossier_mods: Path


def detecter(dossier_lanceur: Path, candidats: list[Path]) -> InfoZakuro:
    return InfoZakuro(trouver_executable(candidats), dossier_mods(dossier_lanceur))


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Recompile le jeu moddé pour Zakuro (lanceur, en ligne de commande).")
    ap.add_argument("--zakuro", type=Path, required=True)
    ap.add_argument("--rom", type=Path, required=True)
    ap.add_argument("--dossier", type=Path, required=True, help="dossier de données du lanceur")
    a = ap.parse_args()
    recompiler(a.zakuro, a.rom, a.dossier, progression=lambda n, t: print(f"{n:3d} % {t}", flush=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
