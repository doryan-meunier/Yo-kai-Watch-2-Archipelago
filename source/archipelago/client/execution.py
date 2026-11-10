"""Mode d'exécution du mod : scripts Python (dépôt, paquet `.pyw`) ou exécutable empaqueté (« gelé », PyInstaller).

Une seule source pour trois questions, dans les deux modes :

- où sont les fichiers du mod : `dossier_archipelago()` (dossier `archipelago/` : code, `ressources/`, données de
  l'APWorld) et `ressource(...)` ;
- où sont les fichiers visibles du paquet (`patch/`, `apworld/`, `LISEZMOI.txt`) : `dossier_application()` ;
- comment relancer une partie du mod comme PROCESSUS séparé : `commande(role, *args)`.

Mode normal : `archipelago/` est le dossier parent de `client/`, les fichiers visibles sont à côté de lui, et un
rôle se lance par `python <script.py>` (ou `pythonw` : pas de console), exactement comme avant ce module.

Mode gelé (`sys.frozen`, `archipelago/outils/fabriquer_exe.py`) : l'exécutable embarque Python et la bibliothèque
standard ; le dossier `archipelago/` du paquet est copié TEL QUEL (fichiers `.py` compris) dans
`sys._MEIPASS/archipelago` (`_internal/archipelago` à côté de l'exécutable) et mis sur `sys.path` par
`archipelago/exe/entree.py` : tous les `Path(__file__)` du mod gardent donc leur sens, sans rien changer aux
modules. Les fichiers visibles sont à côté de l'exécutable, et un rôle se lance par
`<exécutable> --role <rôle> …` (`lanceur/demarrage.py`) : il n'y a pas de `python.exe` chez le joueur.

Bibliothèque standard seulement ; aucun import du reste du mod (importable de partout : `client/` est sur
`sys.path` dès que `lanceur.logique` ou `client/principal.py` est chargé).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ARGUMENT_ROLE = "--role"
# rôle -> (script relatif à `archipelago/`, sans console par défaut ?)
ROLES: dict[str, tuple[str, bool]] = {
    "lanceur": ("lanceur", True),                       # fenêtre (`python archipelago/lanceur`)
    "client": ("client/principal.py", True),            # client invisible
    "diagnostic": ("lanceur", False),                   # `python archipelago/lanceur --diagnostic`
    "installer": ("installation/installer.py", False),  # installation en ligne de commande
    "reparer": ("lanceur", False),                      # bouton « Installer » / « Réparer », sans fenêtre
    "maj": ("lanceur", True),                           # remplacement du lanceur (lanceur/maj_outil.py)
}
# mode normal : arguments propres au script
ARGUMENTS_FIXES = {"diagnostic": ("--diagnostic",), "reparer": (ARGUMENT_ROLE, "reparer"),
                   "maj": (ARGUMENT_ROLE, "maj")}


def gele() -> bool:
    """Exécutable empaqueté (PyInstaller) ?"""
    return bool(getattr(sys, "frozen", False))


def dossier_archipelago() -> Path:
    """Dossier `archipelago/` du mod (code, ressources, données)."""
    if gele():
        interne = getattr(sys, "_MEIPASS", None)
        if interne and (Path(interne) / "archipelago").is_dir():
            return Path(interne).resolve() / "archipelago"
    return Path(__file__).resolve().parents[1]


def dossier_application() -> Path:
    """Dossier des fichiers visibles du paquet (`patch/`, `apworld/`, `LISEZMOI.txt`) : celui de l'exécutable
    en mode gelé, sinon le parent de `archipelago/` (paquet `.pyw`, ou racine du dépôt)."""
    if gele():
        return Path(sys.executable).resolve().parent
    return dossier_archipelago().parent


def ressource(*parties: str) -> Path:
    """Chemin d'un fichier du mod, relatif à `archipelago/` : `ressource("lanceur", "ressources", "icone.ico")`."""
    return dossier_archipelago().joinpath(*parties)


def interpreteur_sans_fenetre() -> str:
    """`pythonw.exe` à côté de l'interpréteur courant (Windows), sinon l'interpréteur courant."""
    exe = Path(sys.executable)
    if os.name == "nt":
        w = exe.with_name("pythonw.exe")
        if w.is_file():
            return str(w)
    return str(exe)


def commande(role: str, *args: str, console: bool = False) -> list[str]:
    """Ligne de commande qui lance `role` comme processus séparé, suivie de `args`.

    Mode normal : `[python | pythonw, <script du rôle>, …]` (`pythonw` pour les rôles sans console, sauf
    `console=True`). Mode gelé : `[<exécutable>, "--role", <rôle>, …]`."""
    if role not in ROLES:
        raise ValueError(f"rôle inconnu : {role!r}")
    if gele():
        return [sys.executable, ARGUMENT_ROLE, role, *args]
    script, sans_console = ROLES[role]
    exe = interpreteur_sans_fenetre() if sans_console and not console else sys.executable
    return [exe, str(ressource(*script.split("/"))), *ARGUMENTS_FIXES.get(role, ()), *args]

